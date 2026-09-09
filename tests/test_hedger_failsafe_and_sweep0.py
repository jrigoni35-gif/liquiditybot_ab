"""Two holes closed in the hedger's OFF-state and churn accounting.

1. FAIL-SAFE DEFAULT. `HedgeEngine.__init__` defaulted `enabled` to True, so
   the era-8 hedger-OFF state (cut #11, 2026-09-07) rested entirely on one
   config literal: deleting or renaming the `hedging` block re-armed a
   COHORT-RESETTING subsystem with no code diff and no failing test. The
   default is now OFF, and a config block that is PRESENT but silent about
   `enabled` is a config_guard FATAL - an absent block stays clean, per the
   repo convention that module defaults apply to an absent block.

2. SWEEP-0 (docs/quant/2026-08-20_codebase_sweep_docket.md:30, HANDOFF.md:464).
   `inventory.derisk_actions` force-closes positions through main.py's derisk
   loop, which calls `_submit_exit` directly and never touches the hedge
   engine. A derisk-forced close of a HEDGE position therefore armed no
   re-hedge cooldown and never reached the FW-070 counter, leaving the churn
   backstop blind to the exact re-open loop it exists to stop. Such closes are
   now accounted through the same path as an emitted unwind.
"""
import json
import types
from datetime import datetime, timezone
from pathlib import Path

from core.config_guard import validate
from core.state import PortfolioState, Position
from execution.hedging import HedgeEngine
from main import LiquidityBot
from regime.correlation import CorrState

SYMS = {"ETH": "ETH/USD", "ADA": "ADA/USD"}
ROOT = Path(__file__).resolve().parents[1]
PAIR = "XETHZUSD"


# --------------------------------------------------------------- 1. default
def test_absent_enabled_key_defaults_OFF():
    # the whole point: no config -> no hedging, never the reverse
    assert HedgeEngine({}, SYMS).enabled is False
    assert HedgeEngine(None, SYMS).enabled is False


def test_explicit_enable_still_works():
    assert HedgeEngine({"enabled": True}, SYMS).enabled is True
    assert HedgeEngine({"enabled": False}, SYMS).enabled is False


def test_defaulted_engine_emits_nothing_on_a_book_over_cap():
    eng = HedgeEngine({}, SYMS)          # defaulted -> OFF
    pos = types.SimpleNamespace(position_id="s1", symbol="ETH/USD",
                                direction="long", size=1.0,
                                entry_price=2000.0, is_hedge=False)
    state = types.SimpleNamespace(open_positions=lambda: [pos])
    corr = CorrState(corr_fast={("ETH", "ADA"): 0.9})
    assert eng.evaluate(state, {"ETH/USD": 2000.0}, 1000.0, corr,
                        now=1000.0) == []


# ----------------------------------------------------------- 2. config_guard
def _hedging_fatals(cfg) -> list:
    return [m for sev, m in validate(cfg)
            if sev == "FATAL" and "hedging block" in m]


def test_present_block_without_enabled_is_fatal():
    assert _hedging_fatals({"hedging": {"min_hedge_usd": 15}})


def test_present_block_with_enabled_is_clean():
    assert _hedging_fatals({"hedging": {"enabled": False}}) == []
    assert _hedging_fatals({"hedging": {"enabled": True}}) == []


def test_absent_block_stays_clean():
    # repo convention (cf. _conviction_checks): an absent block is clean.
    # Safe here precisely BECAUSE the engine default is now OFF.
    assert _hedging_fatals({"system": {"dry_run": True}}) == []


def test_shipped_config_passes():
    cfg = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    assert _hedging_fatals(cfg) == []


# --------------------------------------------------------------- 3. SWEEP-0
def _engine(**over):
    cfg = {"enabled": True, "max_net_delta_pct_of_equity": 10.0,
           "rebalance_band_pct": 4.0, "min_hedge_usd": 5.0,
           "corr_min_samples": 12, "rehedge_cooldown_sec": 600.0,
           "churn_max_unwinds": 3, "churn_window_sec": 900.0}
    cfg.update(over)
    return HedgeEngine(cfg, SYMS)


def test_external_unwind_arms_the_rehedge_cooldown():
    eng = _engine()
    assert eng._open_blocked("ADA", warm=True, now=1000.0) is None
    eng.note_external_unwind("ADA", 1000.0)
    assert eng._open_blocked("ADA", warm=True, now=1100.0) == "re-hedge cooldown"


def test_external_unwinds_reach_the_FW070_latch():
    eng = _engine()
    for i in range(3):
        eng.note_external_unwind("ADA", 1000.0 + i)
    assert "ADA" in eng._latched
    # cooldown expired, latch still holds the OPEN
    assert eng._open_blocked("ADA", warm=True, now=1700.0) == "churn-latched"
    # and it auto-releases on warm + window, independent of the gated action.
    # The latch stamps at the THIRD unwind, so the window runs from there.
    release_at = eng._latched["ADA"] + eng.churn_window_sec + 1
    assert eng._open_blocked("ADA", warm=True, now=release_at) is None
    # release is time + evidence only: a cold estimator holds it shut
    eng2 = _engine()
    for i in range(3):
        eng2.note_external_unwind("ADA", 1000.0 + i)
    cold = eng2._latched["ADA"] + eng2.churn_window_sec + 1
    assert eng2._open_blocked("ADA", warm=False, now=cold) == "churn-latched"


def test_external_unwind_never_gates_an_unwind():
    # invariant 5: escapes are never blocked, whoever initiated them
    eng = _engine()
    for i in range(5):
        eng.note_external_unwind("ADA", 1000.0 + i)
    hedge = types.SimpleNamespace(position_id="h1", symbol="ADA/USD",
                                  direction="short", size=100.0,
                                  entry_price=1.0, is_hedge=True)
    state = types.SimpleNamespace(open_positions=lambda: [hedge])
    acts = eng.evaluate(state, {"ADA/USD": 1.0}, 10_000.0,
                        CorrState(corr_fast={}), now=2000.0)
    assert [a.kind for a in acts] == ["unwind"]


# ------------------------------------------------- 4. SWEEP-0 wired in main
def _noop(*a, **k):
    return None


def _bot():
    b = LiquidityBot.__new__(LiquidityBot)
    b.dry_run = True
    b._halted = False
    b.symbol_map = {"ETH": "ETH/USD"}
    b._pair_of = {"ETH": PAIR}
    b._pair_list = [PAIR]
    b.marks, b._mark_ts, b._stop_ok, b.book_ts, b.kraken_books = {}, {}, {}, {}, {}
    b.last_signals = {}
    b._stop_hit = {}
    b._mark_stale_sec = 20.0
    b._exit_eval_failures = 0
    b.state = PortfolioState(starting_capital=10_000.0)
    b.watchdog = types.SimpleNamespace(
        evaluate=_noop, filter_mark=lambda asset, px: (px, True))
    b.kraken = types.SimpleNamespace(
        get_tickers=lambda pairs: {PAIR: 1900.0},
        get_order_book=lambda pair: {"bids": [[1899.5, 1.0]],
                                     "asks": [[1900.5, 1.0]]},
        kraken_pair=lambda s: PAIR)
    b.kraken_ws = None
    b.thales = types.SimpleNamespace(observe_feed_health=_noop,
                                     observe_fast=_noop)
    b._step_exec_algos = _noop
    b._apply_sim = _noop
    b._handle_fill = _noop
    b._equity = lambda: 10_000.0
    b.orders = types.SimpleNamespace(poll=lambda *a, **k: [],
                                     open_orders=lambda: [],
                                     has_open=lambda *a, **k: False)
    b.store = types.SimpleNamespace(snapshot=_noop)
    b.vol = types.SimpleNamespace(
        state=lambda a: types.SimpleNamespace(sigma_bar_pct=0.5))
    b.fv = types.SimpleNamespace(
        state=lambda a: types.SimpleNamespace(fair_value=1900.0))
    b.macro = types.SimpleNamespace(
        state=lambda a: types.SimpleNamespace(playbook={"tier_scale": 1.0}))
    b.inventory = types.SimpleNamespace(
        inventory_ratio=lambda *a, **k: 0.0, soft_cap_pct=50.0,
        hard_cap_pct=100.0, derisk_actions=lambda *a, **k: [])
    b.corr = types.SimpleNamespace(state=CorrState(corr_fast={}))
    b.postmortem = types.SimpleNamespace(record_marks=_noop,
                                         poll=lambda now: [])
    b.markout = types.SimpleNamespace(poll=_noop, record_fill=_noop,
                                      snapshot=lambda: {})
    b.risk_protocols = types.SimpleNamespace(observe=_noop)
    b.monitor = types.SimpleNamespace(record_close=_noop)
    b.capital = types.SimpleNamespace(
        hard_stop_triggered=lambda *a, **k: False)
    b._tier_engine = lambda scale: types.SimpleNamespace(
        evaluate=lambda *a, **k: types.SimpleNamespace(
            tier=None, close_pct=0.0, reason=""))
    # REAL engine: this test is about the accounting seam, not a stub
    b.hedger = _engine()
    # The hedge pass is NEUTRALISED on purpose. With it live, evaluate()
    # unwinds the lone hedge position itself ("signal delta normalized") and
    # records the unwind - so the assertions below would pass whether or not
    # the derisk seam works at all. Measured: they DID, before the fix. Only
    # the derisk path may reach the accounting in these three tests.
    b._run_hedge_pass = _noop
    return b


def _add_pos(b, pid, hedge):
    p = Position(pid, "ETH/USD", "long", 2000.0, 1.0, 1.0,
                 datetime.now(timezone.utc))
    p.stop_price = 1.0          # far below the 1900 mark: no stop fires
    p.tier_closed = 0
    p.is_hedge = hedge
    b.state.add_position(p)


def test_derisk_forced_close_of_a_hedge_is_accounted():
    b = _bot()
    _add_pos(b, "h1", hedge=True)
    b.inventory.derisk_actions = lambda *a, **k: [
        types.SimpleNamespace(position_id="h1", close_pct=100.0,
                              reason="inventory derisk")]
    b._submit_exit = _noop
    b.fast_cycle(5000.0)
    assert b.hedger._last_unwind.get("ETH") == 5000.0, \
        "SWEEP-0: a derisk-forced hedge close must arm the re-hedge cooldown"
    assert b.hedger._open_blocked("ETH", warm=True, now=5001.0) \
        == "re-hedge cooldown"


def test_derisk_close_of_a_NON_hedge_is_not_accounted():
    b = _bot()
    _add_pos(b, "p1", hedge=False)
    b.inventory.derisk_actions = lambda *a, **k: [
        types.SimpleNamespace(position_id="p1", close_pct=50.0,
                              reason="inventory derisk")]
    b._submit_exit = _noop
    b.fast_cycle(5000.0)
    assert b.hedger._last_unwind == {}


def test_a_failed_derisk_submit_records_no_unwind():
    # the accounting must follow the close, not the intent to close
    b = _bot()
    _add_pos(b, "h1", hedge=True)
    b.inventory.derisk_actions = lambda *a, **k: [
        types.SimpleNamespace(position_id="h1", close_pct=100.0,
                              reason="inventory derisk")]

    def boom(*a, **k):
        raise RuntimeError("submit blew up")
    b._submit_exit = boom
    b.fast_cycle(5000.0)
    assert b.hedger._last_unwind == {} and b._exit_eval_failures >= 1


# ------------------------------------------- 5. feedback-loop self-tests
# CLAUDE.md: "A gate's release condition must never depend on the thing it
# blocks (four separate incidents share that shape)." note_external_unwind
# can arm FW-070, so it inherits that obligation and is pinned here.
def test_FW070_release_is_reachable_without_ever_opening_a_hedge():
    """The deadlock question, answered against the REAL estimator.

    If warmth accrued only while a hedge existed, arming the latch would be
    a one-way door: latch blocks the open -> no hedge -> estimator never
    warms -> latch never releases. It does not: CorrelationEngine.
    update_intraday() folds PRICE closes (main.py:4438, every cycle) and
    increments samples per asset, with no reference to positions, hedges,
    or the latch. Driven here with prices only and an empty book.
    """
    from regime.correlation import CorrelationEngine
    eng = _engine()
    for i in range(3):
        eng.note_external_unwind("ADA", 1000.0 + i)
    assert eng._open_blocked("ADA", warm=False, now=1002.0) == "churn-latched"

    corr = CorrelationEngine({})
    px = {"ETH": 2000.0, "ADA": 1.0}
    for i in range(1, 40):                      # no positions, no hedges
        px = {"ETH": 2000.0 * (1 + 0.001 * i), "ADA": 1.0 * (1 - 0.0005 * i)}
        corr.update_intraday(dict(px))
    warm = corr.state.pair_samples("ETH", "ADA") >= eng.corr_min_samples
    assert warm, "estimator must warm on price flow alone"

    release_at = eng._latched["ADA"] + eng.churn_window_sec + 1
    assert eng._open_blocked("ADA", warm=warm, now=release_at) is None


def test_derisk_close_cannot_immediately_rehedge():
    """The positive-feedback loop this fix exists to break.

    Before: derisk force-closes the hedge -> net delta breaches the cap ->
    evaluate() re-opens it on the very next cycle -> derisk closes it again,
    at cycle cadence, paying two fee legs a lap. That is the 2026-08-07 ADA
    shape with the churn guard bypassed. The accounting now damps it.
    """
    eng = _engine()
    book = [types.SimpleNamespace(position_id="s1", symbol="ETH/USD",
                                  direction="long", size=1.0,
                                  entry_price=2000.0, is_hedge=False)]
    state = types.SimpleNamespace(open_positions=lambda: book)
    corr = CorrState(corr_fast={("ETH", "ADA"): 0.9})
    corr.samples = {"ETH": 999, "ADA": 999}
    marks = {"ETH/USD": 2000.0}

    # over the cap and warm: an open is available on this book
    assert [a.kind for a in eng.evaluate(state, marks, 10_000.0, corr,
                                         now=1000.0)] == ["open"]
    # a derisk-forced close of that hedge is now accounted...
    eng.note_external_unwind("ADA", 1001.0)
    # ...so the very next cycle cannot re-open it
    assert eng.evaluate(state, marks, 10_000.0, corr, now=1002.0) == []


def test_disabled_engine_does_not_unwind_an_open_hedge():
    """CHARACTERISATION, not an endorsement — the residual of the fail-safe
    default, recorded so it cannot surprise anyone.

    `evaluate()` returns [] on `not self.enabled` BEFORE the unwind branch,
    so a disabled hedger will not unwind a hedge that is already open. That
    predates this change; what changed is that DELETING the config block now
    reaches the disabled state (it used to re-arm the hedger instead). The
    stranded position keeps its stop, `derisk_actions`, and `flatten_all` —
    it is not un-exitable — but its dedicated unwind path is gone.
    scripts/cut11_stage.py refuses to disable over an open hedge for exactly
    this reason; block DELETION has no such interception. Docketed, not
    fixed here: changing it is hedger behaviour, which is COHORT-RESETTING.
    """
    eng = HedgeEngine({}, SYMS)                 # deleted block -> OFF
    hedge = types.SimpleNamespace(position_id="h1", symbol="ADA/USD",
                                  direction="short", size=100.0,
                                  entry_price=1.0, is_hedge=True)
    state = types.SimpleNamespace(open_positions=lambda: [hedge])
    assert eng.evaluate(state, {"ADA/USD": 1.0}, 10_000.0,
                        CorrState(corr_fast={}), now=2000.0) == []


def test_the_two_asset_of_implementations_agree():
    """The SWEEP-0 seam keys the cooldown with LiquidityBot._asset_of while
    the open path checks it with HedgeEngine._asset_of. Two implementations
    of one rule is the 2026-08-06 thrash shape (two paths asking different
    questions); if they ever diverge the guard silently keys under a name
    nothing checks. They agree today — pinned so they keep agreeing.
    """
    bot_asset_of = LiquidityBot._asset_of
    for sym in ["ADA/USD", "ETH/USD", "BTC/USD", "PAXG/USD", "LINK/USD",
                "ADA", "", "A/B/C", "XETHZUSD"]:
        assert bot_asset_of(None, sym) == HedgeEngine._asset_of(sym), sym
