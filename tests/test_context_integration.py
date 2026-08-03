"""tests/test_context_integration.py — Compounder Phase B, Task B4: wiring
`data.context_engine.ContextFeed` into `main.py`'s slow_cycle poll cluster
and `runner.py`'s status assembly. TELEMETRY-ONLY as of B4 (spec §3,
Global Constraints): no entry/exit/sizing/gate path read the context
state that phase; the only consumers were status, audit logs, and
gc_pusher — report-first, exactly like Phase A's conviction formula
(`ConvictionFormula` wiring, `tests/test_conviction_integration.py`).

RETIRED CONSCIOUSLY by Task C4 (Compounder Phase C engine integration,
`tests/test_long_book_integration.py`): `_context_state` is no longer
telemetry-only. `main.LiquidityBot._long_book_cycle` (called from the end
of `slow_cycle`) reads it ONCE per cycle (`ctx_state = self._context_state`)
to gate long-book ADDS on context alignment (known + stress dial <=
`long_book.context.stress_max_for_add`) — a real, documented new-risk
gate, per the Phase C spec's "context before conviction" Global
Constraint. Pin 2 below is updated to allow exactly this one new site
(count-based, still strict: a THIRD site would still fail it) rather than
dropped — the B4 exclusivity clause (a hard "nothing but init+poll reads
this" invariant) is what's retired, not the pin itself.

Four pins:
  1. wiring proof — the REAL `LiquidityBot.slow_cycle` (driven through the
     established mocked-feeds harness, `scripts/smoke_test.py`'s
     MockOKX/MockBinanceUS/MockKraken — reused, not rebuilt) actually calls
     `self.context.maybe_poll(now)` every cycle.
  2. SOURCE PIN — `main.py` references `self.context` in exactly 2 places
     (the init line and the one poll line — UNCHANGED by C4, which never
     reads the ContextFeed object itself) and `self._context_state` in
     exactly 2 places (the poll-line assignment, plus C4's one
     `_long_book_cycle` read — the sole legitimate consumer this task
     adds). No other line in main.py may reference either.
  3. status — `runner.py`'s `build_status` carries a serializable "context"
     section, placed directly after "webdata" (source pin + a real
     end-to-end check that it matches `bot.context.status()`).
  4. dark-everything invariance — a fully dark context source
     (`fetch=lambda *a, **k: None`) produces byte-identical trading
     behavior (same orders, same equity, same realized PnL) to context
     disabled outright. Still holds post-C4: `long_book.enabled` is
     forced off in this module's `_cfg()` (below) precisely so this
     invariance check keeps exercising ONLY the context-dark-vs-disabled
     delta B4 designed it for, not conflated with the long book's own
     (separately tested) context gating.

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
    # Task C4 (Compounder Phase C): config.json ships long_book.enabled=
    # true by default, and _long_book_cycle is now the one place in
    # main.py that reads self._context_state as a real consumer (see the
    # module docstring's RETIRED note). Disabled here so this module's
    # dark-vs-disabled invariance test (4) isolates the context delta it
    # was built for, never the long book's own (separately tested in
    # tests/test_long_book_integration.py) context-gated add behavior.
    cfg["long_book"]["enabled"] = False
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
        # deterministic fill, not just queue-gate off: the shipped
        # passive_base_prob is now the MEASURED market rate (0.048,
        # XV-021) and force_fill's whole point is that the fill is not a
        # coin flip. Realism is tested in test_sim_fill_queue.
        _sf = cfg.setdefault("order_manager", {}).setdefault("sim_fill", {})
        _sf["queue_aware"] = False
        _sf["passive_base_prob"] = 1.0
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
# 2. SOURCE PIN — main.py: `self.context` stays exactly init + one poll
#    line (UNCHANGED, B4's own invariant). `self._context_state` is now
#    the poll-line assignment PLUS exactly the enumerated new read
#    site(s) Task C4 (Compounder Phase C) legitimately adds - still a
#    strict, count-based pin, consciously widened rather than dropped
#    (module docstring's RETIRED note explains why).
# ---------------------------------------------------------------------------

# Task C4: the ONE new `self._context_state` consumer read site
# (_long_book_cycle gating long-book adds on context alignment - the
# sole enumerated addition this pin now allows).
_LONG_BOOK_CTX_READ_LINE = "ctx_state = self._context_state"


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
    # C4 never reads the ContextFeed object itself, only the parsed
    # ContextState it already polls (self._context_state, checked below).
    context_refs = re.findall(r"self\.context\b", _MAIN_SRC)
    assert len(context_refs) == 2, (
        f"main.py must reference `self.context` in EXACTLY 2 places (the "
        f"ContextFeed init + the one slow_cycle poll line) - found "
        f"{len(context_refs)}. No consumer may need the ContextFeed "
        f"object itself; every C4 long-book read goes through the "
        f"already-polled self._context_state instead.")

    # self._context_state: the poll-line assignment PLUS Task C4's ONE
    # enumerated long-book consumer read - exactly 2, never a 3rd
    # unenumerated site (a still-strict count, consciously widened by C4
    # from B4's original exclusive "1" per the module docstring's
    # RETIRED note - this is the literal "enumerate the NEW allowed sites
    # explicitly" the C4 brief calls for).
    assert _LONG_BOOK_CTX_READ_LINE in _MAIN_SRC
    assert _MAIN_SRC.count(_LONG_BOOK_CTX_READ_LINE) == 1
    state_refs = re.findall(r"self\._context_state\b", _MAIN_SRC)
    assert len(state_refs) == 2, (
        f"main.py must reference `self._context_state` in EXACTLY 2 "
        f"places (the poll-line assignment + Task C4's one "
        f"_long_book_cycle read, {_LONG_BOOK_CTX_READ_LINE!r}) - found "
        f"{len(state_refs)}. Any OTHER read site is an unenumerated "
        f"consumer and must be added here consciously, not silently.")


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
    # status() derives last_poll_age_sec from wall-clock time.time() rounded
    # to 0.1s; the equality below calls status() twice, so an unfrozen clock
    # flakes whenever the two reads straddle a rounding boundary.
    monkeypatch.setattr("time.time", lambda: t + 60.0)
    status = runner.build_status(t)

    assert "context" in status
    assert status["context"] == bot.context.status()
    assert status["context"]["halving_phase"] != ""
    dumped = json.dumps(status)            # the WHOLE payload stays JSON-safe
    assert isinstance(dumped, str)


def test_status_ml_retrain_calib_gap_key(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    bot = _bot(_cfg(), {"ETH": 2000.0, "BTC": 60000.0})
    runner = BotRunner(bot.config, bot=bot)
    status = runner.build_status(1_700_000_000.0)
    assert status["ml"]["retrain_calib_gap"] == {}      # pre-first-retrain
    bot._last_retrain_calib_gap = {"gbt": 0.05}
    status = runner.build_status(1_700_000_000.0)
    assert status["ml"]["retrain_calib_gap"] == {"gbt": 0.05}
    json.dumps(status)                                   # stays JSON-safe


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
