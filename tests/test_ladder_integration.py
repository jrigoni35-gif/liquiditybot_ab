"""tests/test_ladder_integration.py — v10 grid-ladder wiring into main.py.

Harness pattern: LiquidityBot.__new__(LiquidityBot) + hand-set stub
attributes (the pattern already used by tests/test_exit_isolation.py),
scoped to exactly what _ladder_entry / _place_ladder / _finalize_position
touch. A full LiquidityBot() construction needs live exchange configs and
feeds (see scripts/smoke_test.py's MockOKX/MockKraken harness) which is
unnecessary weight for these unit-level wiring bugs.

Covers:
  Bug 2 — GridLadderEngine.note_exit is never wired into _finalize_position,
          so a fully-closed ladder-armed asset stays armed and re-entry
          skips the higher p_win_arm bar.
  Bug 3 — _ladder_entry never consults the entry decision's taker verdict,
          so a taker-urgent entry gets forced through the maker-only ladder
          (post_only=True rungs) instead of falling back to the legacy path
          that honors plan.post_only.
  Bug 4 — (a) _ladder_entry returns handled=True even when every rung was
          rejected (placed==0), silently dropping an approved entry instead
          of falling back to the legacy single-entry path.
          (b) _place_ladder registers a rung's TradeThesis BEFORE submit,
          leaving an orphan postmortem thesis for a rung that never rested.
"""
import math
import types
from datetime import datetime, timezone

from core.state import PortfolioState, Position
from execution.grid_ladder import GridLadderEngine
from execution.pretrade import PreTradeGate
from main import LiquidityBot

LADDER_CFG = {"enabled": True, "rungs": 3, "spacing_vol_mult": 0.35,
             "min_spacing_bps": 8.0, "size_decay": 0.7,
             "p_win_arm": 0.60, "p_win_disarm": 0.55}


def _bot(ladder_cfg=None):
    b = LiquidityBot.__new__(LiquidityBot)
    b.ladder = GridLadderEngine(dict(ladder_cfg or LADDER_CFG))
    # W2-10: _place_ladder re-checks each rung past rung 0 against the
    # gate's own p_fill-weighted EV floor -- gentle shipped defaults so
    # existing fixtures (cost=5/edge=10 bps, sigma_bar_pct=0.30) keep
    # passing every rung unless a test deliberately dials the knobs to
    # force a deep-rung veto.
    b.pretrade = PreTradeGate({"maker_fee_bps": 25.0, "taker_fee_bps": 40.0})
    b.capital = types.SimpleNamespace(
        max_concurrent_positions=10,
        can_open_new_position=lambda state, reserved: True)
    b.state = PortfolioState(starting_capital=10_000.0)
    b.inventory = types.SimpleNamespace(max_same_side=5)
    b._registered_theses = []
    b.postmortem = types.SimpleNamespace(
        register_entry=lambda thesis: b._registered_theses.append(thesis),
        on_close=lambda *a, **k: None, poll=lambda now: [])
    b._submitted_orders = []
    b._reject_position_ids = set()

    def submit(**kwargs):
        order = types.SimpleNamespace(**kwargs)
        b._submitted_orders.append(order)
        if kwargs.get("position_id") in b._reject_position_ids:
            return None
        return order
    b.orders = types.SimpleNamespace(submit=submit, pair_meta={})
    b.marks = {}
    b.kraken_books = {}
    b.kraken = types.SimpleNamespace(kraken_pair=lambda s: s.replace("/", ""))
    b._thales_fired = {}
    b.sizer = types.SimpleNamespace(note_entry=lambda asset, now: None)
    b._mark_cand = lambda asset, direction, code: None
    b._last_entry_admit_ts = 0.0
    # ---- _finalize_position deps (Bug 2) ----
    b.history = types.SimpleNamespace(log_close=lambda *a, **k: None)
    b.perf = types.SimpleNamespace(record_close=lambda *a, **k: None)
    b.breaker = types.SimpleNamespace(record_close=lambda *a, **k: False)
    b._pos_thales = {}
    b.thales = types.SimpleNamespace(note_outcome=lambda *a, **k: None)
    b.macro = types.SimpleNamespace(
        state=lambda a: types.SimpleNamespace(label="bull_quiet"))
    b.liq = types.SimpleNamespace(
        state=lambda a: types.SimpleNamespace(label="liquid"))
    b._stop_hit = {}
    b._exit_attempts = {}
    b.monitor = types.SimpleNamespace(use_model=True)
    b.meta = types.SimpleNamespace(trained=True)
    return b


def _kwargs(position_id="p1", asset="ETH", symbol="ETH/USD", p_win=0.65,
           decision_taker=False):
    signal = types.SimpleNamespace(direction="long")
    decision = types.SimpleNamespace(est_cost_bps=5.0, size_units=3.0,
                                     est_edge_bps=10.0, taker=decision_taker)
    sized = types.SimpleNamespace(usd=300.0, units=3.0)
    lev = types.SimpleNamespace(allowed_leverage=1.0)
    # sigma_daily_pct mirrors the real VolState relationship (sigma_bar_pct
    # * sqrt(288) 5m-bars-per-day) so PreTradeGate.sigma_bar_bps recovers
    # exactly the same per-bar vol the ladder's own spacing used -- the
    # EV recheck and the ladder geometry must agree by construction.
    vol_state = types.SimpleNamespace(sigma_bar_pct=0.30,
                                      sigma_daily_pct=0.30 * math.sqrt(288))
    fv_state = types.SimpleNamespace(fair_value=100.0)
    macro_state = types.SimpleNamespace(label="bull_quiet", playbook={})
    liq_state = types.SimpleNamespace(label="liquid")
    verdict = types.SimpleNamespace(label="neutral")
    return dict(position_id=position_id, asset=asset, symbol=symbol,
                side="buy", signal=signal, entry_price=100.0,
                decision=decision, sized=sized, lev=lev, equity=10_000.0,
                vol_state=vol_state, fv_state=fv_state,
                macro_state=macro_state, liq_state=liq_state,
                verdict=verdict, feats=None, explored=False, p_win=p_win,
                model_p=p_win, shadow_p=p_win, ev_pct=1.0,
                stop_pct_eff=1.0, target_pct=1.0, now=1000.0,
                reserved_entries=0, can_enter=True)


# ---------------------------------------------------------------- Bug 2
def test_note_exit_wired_into_finalize_position():
    b = _bot()
    lplan = b.ladder.plan("ETH", "long", 100.0, 0.30, 3.0, 0.65)
    assert lplan.armed and "ETH" in b.ladder._armed

    pos = Position(position_id="p1", symbol="ETH/USD", direction="long",
                   entry_price=100.0, size=1.0, original_size=1.0,
                   opened_at=datetime.now(timezone.utc))
    b.state.add_position(pos)
    b._finalize_position(pos, total_net=10.0, now=1000.0)

    assert "ETH" not in b.ladder._armed, \
        "a fully-closed position must drop the ladder's armed state"


# ---------------------------------------------------------------- Bug 3
def test_taker_decision_bypasses_the_maker_ladder():
    b = _bot()
    kwargs = _kwargs(p_win=0.90, decision_taker=True)   # well above arm bar
    reserved, can_enter, handled = b._ladder_entry(**kwargs)
    assert handled is False, \
        "a taker-urgent entry must fall through to the legacy path, not " \
        "rest as maker-only ladder rungs"
    assert b._submitted_orders == [], \
        "the ladder must not submit any rungs for a taker entry"


def test_maker_decision_still_ladders_normally():
    # control: the SAME p_win with a maker (non-taker) decision must still
    # arm and place the ladder — the fix must not touch this path.
    b = _bot()
    kwargs = _kwargs(p_win=0.90, decision_taker=False)
    reserved, can_enter, handled = b._ladder_entry(**kwargs)
    assert handled is True
    assert len(b._submitted_orders) == 3
    assert all(o.post_only for o in b._submitted_orders)


# ---------------------------------------------------------------- Bug 4a
def test_zero_placed_rungs_falls_back_instead_of_vanishing():
    b = _bot()
    kwargs = _kwargs(position_id="p1", p_win=0.90)
    b._reject_position_ids = {"p1", "p1-r1", "p1-r2"}   # every rung rejected
    reserved, can_enter, handled = b._ladder_entry(**kwargs)
    assert handled is False, \
        "zero rungs placed must fall back to the legacy single-entry path, " \
        "not silently consume the approved entry"


# ---------------------------------------------------------------- Bug 4b
def test_rejected_rung_leaves_no_orphan_thesis():
    b = _bot()
    kwargs = _kwargs(position_id="p1", p_win=0.90)
    b._reject_position_ids = {"p1-r1", "p1-r2"}   # rung 0 fills, deeper rungs don't
    b._ladder_entry(**kwargs)
    registered_ids = {t.position_id for t in b._registered_theses}
    assert "p1-r1" not in registered_ids, \
        "a rung that never rested must not get a postmortem thesis"
    assert "p1-r2" not in registered_ids


# ---------------------------------------------------------------- W2-10
def test_deep_rungs_reject_when_p_fill_weighted_ev_dips_below_the_floor():
    """Rungs past rung 0 must re-run the gate's OWN p_fill-weighted EV
    check at the rung's actual (larger) offset distance, not just inherit
    rung 0's approval. A low per-bar vol combined with grid_ladder's
    min_spacing_bps FLOOR (spacing doesn't shrink with vol) decays p_fill
    fast per rung while "edge" (est_edge_bps + offset_bps) only grows
    linearly and a non-trivial miss_cost_bps penalizes every likely-miss
    rung -- rung 0's own EV stays comfortably positive but rungs 1/2 dip
    negative. Both non-zero rungs must be skipped (not submitted); rung 0
    places normally (no double-charge -- it already cleared the real gate
    upstream of this stub)."""
    b = _bot()
    # tight, gentle-except-miss_cost knobs: everything else at pretrade.py's
    # own shipped defaults (maker_fill_p0=0.45, p_fill_floor=0.05,
    # ev_min_bps=0.0); only miss_cost_bps is raised off its 0.5 default so a
    # near-floored p_fill's (1 - p_fill) * miss_cost drag can flip a rung
    # negative.
    b.pretrade = PreTradeGate({"maker_fee_bps": 25.0, "taker_fee_bps": 40.0,
                              "miss_cost_bps": 5.0})
    b.kraken_books = {"ETH": {"bids": [[99.99, 1000.0]],
                              "asks": [[100.01, 1000.0]]}}   # mid == 100.0
    sigma_bar_pct = 0.02          # LOW per-bar vol
    kwargs = _kwargs(position_id="p1", p_win=0.90)
    kwargs["decision"] = types.SimpleNamespace(
        est_cost_bps=40.0, size_units=3.0, est_edge_bps=50.0, taker=False)
    kwargs["vol_state"] = types.SimpleNamespace(
        sigma_bar_pct=sigma_bar_pct,
        sigma_daily_pct=sigma_bar_pct * math.sqrt(288))

    reserved, can_enter, handled = b._ladder_entry(**kwargs)

    assert handled is True
    placed_ids = {o.position_id for o in b._submitted_orders}
    assert placed_ids == {"p1"}, (
        f"expected only rung 0 to place, got {placed_ids} -- deeper rungs "
        f"must be vetoed once their re-checked p_fill-weighted EV goes "
        f"negative, not armed at full size regardless")
