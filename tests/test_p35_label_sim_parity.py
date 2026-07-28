"""tests/test_p35_label_sim_parity.py — P3.5: the label sim must mirror the
P1 tier-1 cost floor and the P2 time-stop (PT-060) via SHARED implementations
with the live engine (W2-1 doctrine), and the tier-exit reason code must
reach the exit order's meta.

Sub-task A (P1 cost floor): risk/profit_tiers.tier1_cost_floor_pct is the
SINGLE implementation ProfitTierEngine._tier_trigger_pct and
ml.labeling.ExitPolicy._tier_trigger both call. The live engine's own
estimate (execution/pretrade.py's PreTradeDecision.est_cost_bps) is genuinely
UNAVAILABLE at the only CandidateLabeler.register() call site (main.py: it
runs before execution/pretrade.py's PreTradeGate.evaluate() computes the cost
stack) and at the bootstrap path (no pretrade decision exists for an
EMA-cross pseudo-signal). These pins exercise the mechanism directly via
explicit est_cost_bps kwargs (default 0.0 = the pre-Task-1 shipped state).
Task 1 (#103, tests/test_t1_label_cost_floor_input.py) closes the input gap
at both real call sites with a register-time cost estimate instead — see
that file for the caller-side wiring and the ml.labeling docstrings for the
current (post-Task-1) documented approximation.

Sub-task B (P2 time-stop): risk/profit_tiers.time_stop_fires is the SINGLE
predicate ProfitTierEngine._time_stop_hit and ml.labeling.simulate_exit_policy
both evaluate. Every input the sim needs (bar index, running MFE, the
cost-floored tier-1 trigger) already exists in the replay, so this is a TRUE
mirror — no residual.

Sub-task D(1): main.py's tier-exit caller threads TierAction.reason_code into
_submit_exit's meta so a PT-060 scratch is identifiable without string-
matching the log line.

These pins CALL the live engine's own helpers/methods to compute expected
values — never re-derived constants.
"""
import types
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import numpy as np
import pytest

import main as main_mod
from core.codes import Code
from core.state import Position
from ml.labeling import ExitPolicy, simulate_exit_policy
from risk.profit_tiers import (ProfitTierEngine, tier1_cost_floor_mult,
                              tier1_cost_floor_pct, time_stop_fires)


def _bars(path):
    """path: list of (high, low, close) -> arrays with a leading entry bar."""
    highs = [100.0] + [h for h, _, _ in path]
    lows = [100.0] + [ll for _, ll, _ in path]
    closes = [100.0] + [c for _, _, c in path]
    return np.array(closes), np.array(highs), np.array(lows)


# ============================================================================
# Sub-task A: P1 tier-1 cost floor — shared helper parity
# ============================================================================

def test_exit_policy_from_config_parses_min_trigger_cost_mult_like_engine():
    cfg = {"profit_taking": {"min_trigger_cost_mult": 5.0,
                             "tier_1": {"trigger_pct_gain": 1.0,
                                       "close_pct_of_position": 25}}}
    eng = ProfitTierEngine(cfg["profit_taking"])
    pol = ExitPolicy.from_config(cfg)
    assert pol.min_trigger_cost_mult == pytest.approx(eng.min_trigger_cost_mult)
    assert pol.min_trigger_cost_mult == pytest.approx(
        tier1_cost_floor_mult(cfg["profit_taking"]))


def test_sim_tier_trigger_floor_matches_live_engine_exactly():
    """ExitPolicy._tier_trigger's floored trigger (tier_index=0) must equal
    the LIVE engine's floored trigger for the SAME (mult, est_cost_bps,
    legacy) inputs — computed by CALLING the real ProfitTierEngine, never a
    copied constant."""
    eng = ProfitTierEngine({"tier_1": {"trigger_pct_gain": 0.05,
                                       "close_pct_of_position": 25},
                            "min_trigger_cost_mult": 3.0,
                            "vol_scaled": False})
    live_trigger_pct = eng._tier_trigger_pct(eng.tiers[0], None, tier_index=0,
                                             est_cost_bps=20.0)
    pol = ExitPolicy(tiers=[(0.0005, 0.0, 0.25)], vol_scaled=False,
                     min_trigger_cost_mult=3.0)
    sim_trigger_frac = pol._tier_trigger(0.0005, 0.0, 0.0, tier_index=0,
                                         est_cost_bps=20.0)
    assert sim_trigger_frac == pytest.approx(live_trigger_pct / 100.0)
    assert sim_trigger_frac > 0.0005          # the floor actually bound it


def test_cost_floor_scoped_to_tier_index_zero_in_sim_too():
    """Mirrors test_tier1_cost_floor.py's
    test_cost_floor_does_not_apply_to_tier_two: the sim's floor is tier-1
    only, exactly like the live engine's."""
    pol = ExitPolicy(tiers=[(0.0005, 0.0, 0.25)], vol_scaled=False,
                     min_trigger_cost_mult=3.0)
    tier2_trigger = pol._tier_trigger(0.0010, 0.0, 0.0, tier_index=1,
                                      est_cost_bps=20.0)
    assert tier2_trigger == pytest.approx(0.0010)    # untouched by the floor


def _isolated_tier1_policy(mult=3.0, tier1_frac=0.0005):
    """An ExitPolicy isolating ONLY the tier-1 trigger + hard stop: no BE, no
    trail, no give-back — the sole exit geometry is the (possibly floored)
    tier-1 trigger, closing 100% in one shot."""
    return ExitPolicy(
        base_stop_frac=0.20, stop_vol_mult=0.0,
        tiers=[(tier1_frac, 0.0, 1.0)],
        vol_scaled=False, be_after_tier=999, trail_after_tier=999,
        trail_frac=0.01, gb_enabled=False, min_trigger_cost_mult=mult)


def test_default_est_cost_bps_is_inert_byte_identical():
    """est_cost_bps=0.0 — the default every real candidate/bootstrap caller
    uses today (documented residual) — must be exactly inert: omitting the
    kwarg and passing 0.0 explicitly must be byte-identical."""
    pol = _isolated_tier1_policy()
    c, h, ll = _bars([(100.10, 100.05, 100.08)])
    default = simulate_exit_policy(c, h, ll, 0, +1, 0.0, pol, max_bars=96,
                                   cost_pct=0.5)
    explicit_zero = simulate_exit_policy(c, h, ll, 0, +1, 0.0, pol,
                                        max_bars=96, cost_pct=0.5,
                                        est_cost_bps=0.0)
    assert default == explicit_zero
    assert default.barrier == "tier"          # sanity: the cheap trigger fired


def test_divergence_sim_now_exits_at_the_floored_trigger():
    """THE point of sub-task A: a candidate whose CONFIGURED (legacy) trigger
    sits below its own cost floor must be labeled at the FLOORED trigger, not
    the cheap configured one — the sim-vs-live divergence the P1 fix exists
    to close. Bar 1 alone clears the un-floored 0.05% trigger but NOT the
    0.6% cost floor (3x 20bps); bar 2 clears the floor."""
    pol = _isolated_tier1_policy(mult=3.0, tier1_frac=0.0005)
    c, h, ll = _bars([(100.10, 100.00, 100.05),    # +0.10%: > 0.05%, < 0.6%
                      (100.70, 100.60, 100.65)])    # +0.70%: clears the floor
    unfloored = simulate_exit_policy(c, h, ll, 0, +1, 0.0, pol, max_bars=96,
                                     cost_pct=0.5)               # bps default 0
    floored = simulate_exit_policy(c, h, ll, 0, +1, 0.0, pol, max_bars=96,
                                   cost_pct=0.5, est_cost_bps=20.0)
    assert unfloored.barrier == "tier" and unfloored.bars_held == 1
    assert floored.barrier == "tier" and floored.bars_held == 2
    expected_floor_frac = tier1_cost_floor_pct(3.0, 20.0) / 100.0   # LIVE helper
    assert abs(floored.ret_pct / 100.0 - expected_floor_frac) < 1e-12
    assert floored.ret_pct < unfloored.ret_pct * 100.0    # sanity: not the same exit


# ============================================================================
# Sub-task B: P2 time-stop (PT-060) — shared predicate parity
# ============================================================================

def _ts_policy(ts_enabled=True, ts_max=5, ts_min_frac=0.5, tier1_trigger=0.02,
              n_tiers=1):
    tiers = [(tier1_trigger, 0.0, 0.25)]
    if n_tiers > 1:
        tiers.append((tier1_trigger * 10, 0.0, 0.25))   # far-away tier 2
    return ExitPolicy(
        base_stop_frac=0.20, stop_vol_mult=0.0, tiers=tiers,
        vol_scaled=False, be_after_tier=999, trail_after_tier=999,
        trail_frac=0.01, gb_enabled=False,
        ts_enabled=ts_enabled, ts_max_bars_no_progress=ts_max,
        ts_min_mfe_frac=ts_min_frac)


def test_time_stop_scratches_no_progress_candidate_at_the_right_bar():
    """THE point of sub-task B: a candidate with no favorable progress is
    labeled a time-stop scratch at EXACTLY ts_max_bars_no_progress bars —
    mirrors the live PT-060 lever. threshold = 0.5 * 2% = 1%; every bar
    drifts <= 0.3% -> never close to progress, no tier, no stop breach."""
    pol = _ts_policy(ts_max=5, ts_min_frac=0.5, tier1_trigger=0.02)
    c, h, ll = _bars([(100.3, 99.8, 100.1)] * 5)
    out = simulate_exit_policy(c, h, ll, 0, +1, 0.0, pol, max_bars=96,
                               cost_pct=0.5)
    assert out.barrier == "time_stop"
    assert out.bars_held == 5
    assert out.final is True                  # a decisive, resolved exit


def test_time_stop_does_not_fire_one_bar_early():
    pol = _ts_policy(ts_max=5, ts_min_frac=0.5, tier1_trigger=0.02)
    c, h, ll = _bars([(100.3, 99.8, 100.1)] * 4)     # only 4 bars available
    out = simulate_exit_policy(c, h, ll, 0, +1, 0.0, pol, max_bars=96,
                               cost_pct=0.5)
    assert out.barrier != "time_stop"


def test_time_stop_inert_when_disabled():
    pol = _ts_policy(ts_enabled=False, ts_max=5)
    c, h, ll = _bars([(100.3, 99.8, 100.1)] * 20)
    out = simulate_exit_policy(c, h, ll, 0, +1, 0.0, pol, max_bars=96,
                               cost_pct=0.5)
    assert out.barrier != "time_stop"


def test_time_stop_virgin_only_gate_mirrors_live_review_fix():
    """VIRGIN-ONLY gate mirror (P2 review fix): once ANY tier fires in the
    replay (tier_idx > 0 — a candidate is virgin by construction only up to
    its first tier fire), the time-stop must never fire again even with no
    further progress past ts_max_bars_no_progress — mirrors the live engine's
    position.tier_closed == 0 gate exactly."""
    pol = _ts_policy(ts_max=3, ts_min_frac=0.5, tier1_trigger=0.005)
    # bar1 spikes +1% -> fires tier 1 (25% close, tier_idx -> 1); the
    # remaining bars go nowhere further (flat repeat) well past ts_max(3)
    path = [(101.0, 100.9, 100.95)] * 7
    c, h, ll = _bars(path)
    out = simulate_exit_policy(c, h, ll, 0, +1, 0.0, pol, max_bars=96,
                               cost_pct=0.5)
    assert out.barrier != "time_stop"


def test_sim_time_stop_bar_matches_live_engine_firing_decision():
    """Cross-check: a REAL ProfitTierEngine with the identical time_stop/
    tier_1 config and a Position aged exactly ts_max_bars_no_progress bars
    with the SAME (sub-threshold) MFE the sim path produces must fire PT-060
    at exactly the bar the sim scratches at — computed by calling the live
    engine's evaluate(), never re-derived."""
    ts_max, ts_min_frac, tier1_pct = 5, 0.5, 2.0
    pol = _ts_policy(ts_max=ts_max, ts_min_frac=ts_min_frac,
                     tier1_trigger=tier1_pct / 100.0)
    c, h, ll = _bars([(100.3, 99.8, 100.1)] * ts_max)
    sim_out = simulate_exit_policy(c, h, ll, 0, +1, 0.0, pol, max_bars=96,
                                   cost_pct=0.5)
    assert sim_out.barrier == "time_stop" and sim_out.bars_held == ts_max

    now = 1_700_000_000.0
    eng = ProfitTierEngine({
        "tier_1": {"trigger_pct_gain": tier1_pct, "close_pct_of_position": 25},
        "vol_scaled": False,
        "time_stop": {"enabled": True, "max_bars_no_progress": ts_max,
                     "min_mfe_frac_of_tier1": ts_min_frac}})
    pos = Position(position_id="p35", symbol="T/USD", direction="long",
                  entry_price=100.0, size=1.0, original_size=1.0,
                  opened_at=(datetime.fromtimestamp(now, tz=timezone.utc)
                            - timedelta(minutes=ts_max * 5.0)))
    pos.high_water = 100.3          # SAME peak (0.3%) the sim path produced
    action = eng.evaluate(pos, 100.0, now=now)
    assert action.reason_code == Code.PT_TIME_STOP.value


def test_time_stop_hit_returns_bars_for_log_line_reuse():
    """P2 review minor (sub-task D2): _time_stop_hit returns (fired, bars) so
    evaluate()'s log line reuses the value instead of a second
    _bars_in_trade call."""
    now = 1_700_000_000.0
    eng = ProfitTierEngine({
        "tier_1": {"trigger_pct_gain": 2.0, "close_pct_of_position": 25},
        "vol_scaled": False,
        "time_stop": {"enabled": True, "max_bars_no_progress": 5,
                     "min_mfe_frac_of_tier1": 0.5}})
    pos = Position(position_id="p35b", symbol="T/USD", direction="long",
                  entry_price=100.0, size=1.0, original_size=1.0,
                  opened_at=(datetime.fromtimestamp(now, tz=timezone.utc)
                            - timedelta(minutes=25.0)))
    fired, bars = eng._time_stop_hit(pos, None, now=now)
    assert fired is True
    assert bars == pytest.approx(5.0)


def test_time_stop_fires_predicate_is_the_shared_implementation():
    """The live engine and the sim resolve the PT-060 firing decision through
    the SAME pure function — no parallel formula to drift."""
    for bars, mfe, frac, trig, virgin, expected in [
            (5, 0.3, 0.5, 2.0, True, True),
            (4, 0.3, 0.5, 2.0, True, False),      # too early
            (5, 1.0, 0.5, 2.0, True, False),      # progress cleared
            (5, 0.3, 0.5, 2.0, False, False),     # non-virgin
    ]:
        assert time_stop_fires(True, virgin, bars, 5, mfe, frac, trig) \
            == expected


# ============================================================================
# Sub-task C parity sanity: production config.json parses identically for
# both consumers (the single-source-of-truth this whole insert exists for)
# ============================================================================

def test_from_config_matches_live_engine_on_shipped_config():
    import json
    from pathlib import Path
    cfg = json.loads((Path(__file__).resolve().parents[1] / "config.json")
                     .read_text(encoding="utf-8"))
    pol = ExitPolicy.from_config(cfg)
    eng = ProfitTierEngine(cfg.get("profit_taking", {}))
    assert pol.min_trigger_cost_mult == pytest.approx(eng.min_trigger_cost_mult)
    assert pol.ts_enabled == eng.ts_enabled
    assert pol.ts_max_bars_no_progress == eng.ts_max_bars_no_progress
    assert pol.ts_min_mfe_frac == pytest.approx(eng.ts_min_mfe_frac)


# ============================================================================
# Sub-task D(1): TierAction.reason_code threaded into _submit_exit's meta
# ============================================================================

def _run_exit_capture(reason_code=""):
    """Drive the REAL main._submit_exit against a stub self (same idiom as
    test_maker_first_exit.py) and return the captured orders.submit kwargs."""
    captured = {}

    def fake_submit(**kw):
        captured.update(kw)
        return SimpleNamespace(order_id="o1", position_id="p1", purpose="exit")

    fake = SimpleNamespace(
        _asset_of=lambda sym: "ETH",
        kraken=SimpleNamespace(kraken_pair=lambda sym: "XETHZUSD"),
        orders=SimpleNamespace(open_orders=lambda: [],
                               _ordermin=lambda pair: 0.0,
                               submit=fake_submit),
        _exit_attempts={},
        max_slip_pct=0.5, esc_widen_mult=2.0,
        esc_max_slip_pct=3.0, esc_market_after=3,
        kraken_books={"ETH": {"bids": [(99.0, 5.0)], "asks": [(101.0, 5.0)]}},
        marks={"ETH/USD": 100.0},
        maker_first_profit_exits=False,
        _mark_fresh=lambda sym, now: True,
        fv=SimpleNamespace(state=lambda a: SimpleNamespace(fair_value=100.0)),
        _equity=lambda: 1000.0,
        vol=SimpleNamespace(state=lambda a: SimpleNamespace(sigma_bar_pct=0.3)),
    )
    pos = Position(position_id="p1", symbol="ETH/USD", direction="long",
                  entry_price=100.0, size=1.0, original_size=1.0,
                  opened_at=datetime.now(timezone.utc))
    kwargs = {"reason_code": reason_code} if reason_code else {}
    main_mod.LiquidityBot._submit_exit(fake, pos, close_pct=100.0,
                                       reason="tier 1", tier_fired=1,
                                       now=1000.0, profit_take=True, **kwargs)
    return captured


def test_submit_exit_default_reason_code_is_empty_every_legacy_caller_safe():
    k = _run_exit_capture()
    assert k["meta"]["reason_code"] == ""


def test_submit_exit_threads_reason_code_into_meta():
    k = _run_exit_capture(reason_code=Code.PT_TIME_STOP.value)
    assert k["meta"]["reason_code"] == Code.PT_TIME_STOP.value
    assert k["meta"]["reason_code"] == "PT-060"


def test_manage_open_position_threads_tier_action_reason_code_end_to_end():
    """The tier-exit caller (main.py ~1873-1885) must NOT drop
    TierAction.reason_code on the floor: a PT-060 time-stop scratch must be
    identifiable in the submitted exit's meta without string-matching the
    'tier N' reason text."""
    now = 1_700_000_000.0
    eng = ProfitTierEngine({
        "tier_1": {"trigger_pct_gain": 2.0, "close_pct_of_position": 25},
        "vol_scaled": False,
        "time_stop": {"enabled": True, "max_bars_no_progress": 5,
                     "min_mfe_frac_of_tier1": 0.5}})
    captured = {}

    def fake_submit(**kw):
        captured.update(kw)
        return SimpleNamespace(order_id="o1", position_id="p1", purpose="exit")

    fake = SimpleNamespace(
        marks={"ETH/USD": 100.0},
        state=SimpleNamespace(),
        _asset_of=lambda sym: "ETH",
        _stop_ok={},
        _mark_fresh=lambda sym, now: True,
        vol=SimpleNamespace(state=lambda a: SimpleNamespace(sigma_bar_pct=None)),
        inventory=SimpleNamespace(
            inventory_ratio=lambda *a, **k: 0.0,
            soft_cap_pct=1.0, hard_cap_pct=1.0),
        last_signals={},
        _tier_engine=lambda scale: eng,
        kraken=SimpleNamespace(kraken_pair=lambda sym: "XETHZUSD"),
        orders=SimpleNamespace(open_orders=lambda: [],
                               _ordermin=lambda pair: 0.0,
                               submit=fake_submit),
        _exit_attempts={},
        max_slip_pct=0.5, esc_widen_mult=2.0,
        esc_max_slip_pct=3.0, esc_market_after=3,
        kraken_books={"ETH": {"bids": [(99.0, 5.0)], "asks": [(101.0, 5.0)]}},
        maker_first_profit_exits=False,
        fv=SimpleNamespace(state=lambda a: SimpleNamespace(fair_value=100.0)),
        _equity=lambda: 1000.0,
    )
    # bind the REAL _submit_exit onto the stub so the whole chain (tier-exit
    # caller -> _submit_exit -> orders.submit) is exercised, not just the caller
    fake._submit_exit = types.MethodType(main_mod.LiquidityBot._submit_exit,
                                        fake)
    # T5 sub-25s reclamp sliver: the caller now also consults this predicate
    # before a PT-060 submission (empty open_orders() above -> never
    # suppressed here; the suppression itself is pinned in
    # tests/test_t5_riding_minors.py)
    fake._has_resting_profit_take = types.MethodType(
        main_mod.LiquidityBot._has_resting_profit_take, fake)
    # real cold-sigma gate over the stub vol (duck-typed state has no
    # `measured` -> the stub's sigma_bar_pct passes through unchanged)
    fake._exit_sigma = types.MethodType(main_mod.LiquidityBot._exit_sigma,
                                        fake)
    pos = Position(position_id="p1", symbol="ETH/USD", direction="long",
                  entry_price=100.0, size=1.0, original_size=1.0,
                  tier_closed=0, high_water=100.0,
                  opened_at=(datetime.fromtimestamp(now, tz=timezone.utc)
                            - timedelta(minutes=25.0)))
    macro_states = {"ETH": SimpleNamespace(playbook={"tier_scale": 1.0})}
    main_mod.LiquidityBot._manage_open_position(fake, pos, now, 1000.0,
                                                macro_states)
    assert captured, "no exit was submitted — time-stop did not fire"
    assert captured["meta"]["reason_code"] == Code.PT_TIME_STOP.value
