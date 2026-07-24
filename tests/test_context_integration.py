"""tests/test_context_integration.py — Compounder Phase B, Task B4: wiring
`data.context_engine.ContextFeed` into `main.py`'s slow_cycle poll cluster
and `runner.py`'s status assembly. TELEMETRY-ONLY (spec §3, Global
Constraints): no entry/exit/sizing/gate path may read the context state
this phase; the only consumers are status, audit logs, and gc_pusher —
report-first, exactly like Phase A's conviction formula (`ConvictionFormula`
wiring, `tests/test_conviction_integration.py`).

Four pins:
  1. wiring proof — the REAL `LiquidityBot.slow_cycle` (driven through the
     established mocked-feeds harness, `scripts/smoke_test.py`'s
     MockOKX/MockBinanceUS/MockKraken — reused, not rebuilt) actually calls
     `self.context.maybe_poll(now)` every cycle.
  2. SOURCE PIN — `main.py`'s only two references to `self.context` /
     `self._context_state` are the init line and the one poll line; the
     trading pipeline reads NOTHING from context.
  3. status — `runner.py`'s `build_status` carries a serializable "context"
     section, placed directly after "webdata" (source pin + a real
     end-to-end check that it matches `bot.context.status()`).
  4. dark-everything invariance — a fully dark context source
     (`fetch=lambda *a, **k: None`) produces byte-identical trading
     behavior (same orders, same equity, same realized PnL) to context
     disabled outright.

No test in this module ever touches the network: `ContextFeed`'s default
construction does none (init only warm-starts from a local PIT file — see
`data/context_engine.py`'s `_warm_start`), and every bot built here has
its `context.fetch` monkeypatched to a no-op immediately after
construction, before the first `slow_cycle` call (the only place a real
poll — and thus a real fetch — could fire). Every bot also runs inside a
freshly `chdir`'d tmp dir: this codebase's file defaults are all bare
"outputs/..." paths, including `ContextFeed`'s own hardcoded
`_DEFAULT_HISTORY_PATH` (main.py's wiring constructs `ContextFeed` with
no `history_path` override, per the brief), so isolating CWD is what
keeps a real poll's PIT-append out of the actual repo tree.
"""
import json
import re
from pathlib import Path

import numpy as np
import pytest

from main import LiquidityBot, load_config
from runner import BotRunner
from scripts.smoke_test import MockBinanceUS, MockKraken, MockOKX
from strategies.signal_gates import SignalResult

_ROOT = Path(__file__).resolve().parents[1]
_MAIN_SRC = (_ROOT / "main.py").read_text(encoding="utf-8")
_RUNNER_SRC = (_ROOT / "runner.py").read_text(encoding="utf-8")

_POLL_LINE = "self._context_state = self.context.maybe_poll(now)"
_STATUS_LINE = '"context": bot.context.status() if hasattr(bot, "context") else {},'


# ---------------------------------------------------------------------------
# harness (mirrors scripts/smoke_test.py's test_integration/test_persistence_
# roundtrip cfg shape: real config.json, mocked exchange feeds, other
# telemetry feeds disabled so this module's assertions are about context and
# nothing else)
# ---------------------------------------------------------------------------

def _cfg(context_enabled: bool = True, force_fill: bool = False) -> dict:
    cfg = load_config(str(_ROOT / "config.json"))
    cfg["capital_management"]["starting_capital_usd"] = 10_000
    cfg["system"]["dry_run"] = True
    cfg["sentiment"]["enabled"] = False
    cfg["webdata"]["enabled"] = False
    cfg["moomoo"]["enabled"] = False
    cfg["context"]["enabled"] = context_enabled
    cfg["position_sizer"] = dict(cfg.get("position_sizer", {}),
                                 entry_cooldown_min=0, min_p_win=0.50)
    if force_fill:
        # clear net-Kelly + fill realism knobs so a forced confirmed signal
        # (test 4) reliably produces a real order/fill, giving the dark-vs-
        # disabled comparison actual teeth instead of an all-zero no-op.
        # Same override smoke_test.py's own test_entry_fill_exit_path uses
        # ("let the forced signal through").
        cfg["ml"]["cold_start_prior_p"] = 0.66
        cfg["pretrade"]["min_edge_cost_ratio"] = 0.1
        cfg["pretrade"]["price_exit_leg"] = False
        cfg.setdefault("order_manager", {}).setdefault(
            "sim_fill", {})["queue_aware"] = False
    return cfg


def _bot(cfg: dict, prices: dict) -> LiquidityBot:
    bot = LiquidityBot(cfg, okx=MockOKX(prices), binanceus=MockBinanceUS(prices),
                       kraken=MockKraken(prices), resume=False)
    # the ONLY network-touching default on this object; every test stubs it
    # before the first slow_cycle call ever runs
    if hasattr(bot, "context"):
        bot.context.fetch = lambda *a, **k: None
    return bot


# ---------------------------------------------------------------------------
# 1. wiring proof: slow_cycle's poll cluster actually calls maybe_poll(now)
# ---------------------------------------------------------------------------

def test_context_polled_from_slow_cycle_poll_cluster(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    prices = {"ETH": 2000.0, "BTC": 60000.0}
    bot = _bot(_cfg(), prices)

    calls = []
    real_maybe_poll = bot.context.maybe_poll

    def _recording(now=None):
        calls.append(now)
        return real_maybe_poll(now)

    bot.context.maybe_poll = _recording

    t = 1_700_000_000.0
    bot.slow_cycle(t)
    assert calls == [t], \
        "slow_cycle must call self.context.maybe_poll(now) with the " \
        "cycle's own injected now"

    bot.slow_cycle(t + 5.0)
    assert calls == [t, t + 5.0], \
        "every slow_cycle invocation must poll context again (ContextFeed " \
        "itself owns the cadence early-return, tested in " \
        "tests/test_context_feed.py - the wiring must call it every cycle)"


def test_context_state_assigned_from_the_poll_return_value(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    prices = {"ETH": 2000.0, "BTC": 60000.0}
    bot = _bot(_cfg(), prices)
    t = 1_700_000_000.0
    bot.slow_cycle(t)
    assert bot._context_state is bot.context._state
    assert bot._context_state.ts == t


# ---------------------------------------------------------------------------
# 2. SOURCE PIN — main.py: exactly init + one poll line, nothing else reads
#    context. This is the load-bearing telemetry-only invariant.
# ---------------------------------------------------------------------------

def test_main_source_pins_context_wiring_to_init_and_poll_line():
    assert "from data.context_engine import ContextFeed" in _MAIN_SRC

    init_hits = re.findall(r"self\.context\s*=\s*ContextFeed\(", _MAIN_SRC)
    assert len(init_hits) == 1, \
        f"main.py must construct self.context exactly once; found " \
        f"{len(init_hits)}"

    assert _POLL_LINE in _MAIN_SRC
    assert _MAIN_SRC.count(_POLL_LINE) == 1

    # exhaustive count: every reference to `self.context` (attribute access,
    # not just the init assignment) must be ONE of the two lines above -
    # never a third site reading context inside a gate/entry/exit/sizing
    # path. This is the actual grep-style assertion the brief calls for.
    context_refs = re.findall(r"self\.context\b", _MAIN_SRC)
    assert len(context_refs) == 2, (
        f"main.py must reference `self.context` in EXACTLY 2 places (the "
        f"ContextFeed init + the one slow_cycle poll line) - found "
        f"{len(context_refs)}. TELEMETRY-ONLY invariant: no entry/exit/"
        f"sizing/gate path may read context state this phase.")

    state_refs = re.findall(r"self\._context_state\b", _MAIN_SRC)
    assert len(state_refs) == 1, (
        f"main.py must assign `self._context_state` exactly once (the "
        f"poll line) and never read it back anywhere else - found "
        f"{len(state_refs)} references.")


def test_main_context_poll_line_sits_in_the_established_poll_cluster():
    # must land in the SAME cluster as the sentiment/web/risk polls
    # (directly after _maybe_realize_mature_label), never scattered
    # elsewhere in the method
    realize_idx = _MAIN_SRC.index("self._maybe_realize_mature_label(now)")
    sentiment_idx = _MAIN_SRC.index("sentiment = self.xscan.maybe_poll(now)")
    web_idx = _MAIN_SRC.index("web = self.webdata.maybe_poll(now)")
    risk_idx = _MAIN_SRC.index("risk = self.moomoo.maybe_poll(now)")
    ctx_idx = _MAIN_SRC.index(_POLL_LINE)

    assert realize_idx < sentiment_idx < web_idx < risk_idx < ctx_idx, \
        "context poll line must come after the existing sentiment/web/risk " \
        "cluster, preserving established ordering"
    # tight cluster, not merely "somewhere later in the file"
    assert ctx_idx - risk_idx < 200


# ---------------------------------------------------------------------------
# 3. status: runner.py source pin + a real end-to-end serializable check
# ---------------------------------------------------------------------------

def test_runner_source_pins_context_status_directly_after_webdata():
    assert _STATUS_LINE in _RUNNER_SRC
    assert _RUNNER_SRC.count(_STATUS_LINE) == 1
    webdata_idx = _RUNNER_SRC.index('"webdata": {')
    moomoo_idx = _RUNNER_SRC.index('"moomoo": {')
    ctx_idx = _RUNNER_SRC.index(_STATUS_LINE)
    assert webdata_idx < ctx_idx < moomoo_idx, \
        '"context" must sit directly after the "webdata" entry, before ' \
        '"moomoo"'


def test_runner_build_status_includes_serializable_context_section(
        tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    prices = {"ETH": 2000.0, "BTC": 60000.0}
    bot = _bot(_cfg(), prices)
    t = 1_700_000_000.0
    bot.slow_cycle(t)                      # a real poll: non-default state

    runner = BotRunner(bot.config, bot=bot)
    status = runner.build_status(t)

    assert "context" in status
    assert status["context"] == bot.context.status()
    assert status["context"]["halving_phase"] != ""
    dumped = json.dumps(status)            # the WHOLE payload stays JSON-safe
    assert isinstance(dumped, str)


# ---------------------------------------------------------------------------
# 4. dark-everything invariance: context enabled+dark vs context disabled
#    must be byte-identical for the trading pipeline (telemetry-only).
# ---------------------------------------------------------------------------

def _force_confirmed_signals(bot: LiquidityBot) -> None:
    bot.gates.evaluate_asset = lambda base_asset, view: SignalResult(
        symbol=f"{base_asset}/USD", direction="long", confidence=1.0,
        size=0.0, all_confirmed=True, gates_passed={})


def _run_book(cfg: dict, prices: dict, n: int = 24, seed: int = 21):
    bot = _bot(cfg, prices)
    _force_confirmed_signals(bot)
    t = 1_700_000_000.0
    bot.hourly_cycle(t)
    for a in ("ETH", "BTC"):
        st = bot.macro.state(a)
        st.label = "bull_quiet"
        st.playbook = dict(bot.macro.playbooks["bull_quiet"])
        bot.macro._states[a] = st

    rng = np.random.default_rng(seed)
    for cycle in range(n):
        for a in prices:
            prices[a] *= float(np.exp(rng.normal(0.0006, 0.0035)))
        bot.fast_cycle(t)
        if cycle % 3 == 0:
            bot.slow_cycle(t)
        t += 5.0
    return bot


def _order_snapshot(bot: LiquidityBot):
    return sorted(
        (o.symbol, o.side, o.purpose, o.status, round(o.price, 6),
         round(o.size, 8))
        for o in bot.orders._orders.values())


def test_dark_context_source_produces_no_behavioral_delta(tmp_path, monkeypatch):
    off_dir = tmp_path / "off"
    off_dir.mkdir()
    dark_dir = tmp_path / "dark"
    dark_dir.mkdir()

    monkeypatch.chdir(off_dir)
    bot_off = _run_book(_cfg(context_enabled=False, force_fill=True),
                        {"ETH": 2000.0, "BTC": 60000.0})

    monkeypatch.chdir(dark_dir)
    bot_dark = _run_book(_cfg(context_enabled=True, force_fill=True),
                         {"ETH": 2000.0, "BTC": 60000.0})

    # sanity: the "dark" run genuinely exercised a live-but-blacked-out
    # context feed, never an accidentally-disabled one
    assert bot_dark.context.enabled is True
    dark_status = bot_dark.context.status()
    assert dark_status["stress_known"] is False
    assert dark_status["flow_known"] is False
    assert all(dark_status["sources"][s] is False
              for s in ("dff", "t10y2y", "vix", "cot", "stablecoins"))
    # honest unknown, never a fabricated value
    assert dark_status["stress"] is None
    assert dark_status["cot_z"] is None
    assert dark_status["stable_wk_pct"] is None
    # purely local components stay known even with every network source dark
    assert dark_status["sources"]["halving"] is True

    assert _order_snapshot(bot_off) == _order_snapshot(bot_dark)
    assert bot_off.state.open_position_count() == \
        bot_dark.state.open_position_count()
    assert bot_off.state.realized_pnl_total == \
        pytest.approx(bot_dark.state.realized_pnl_total)
    assert bot_off._equity() == pytest.approx(bot_dark._equity())
