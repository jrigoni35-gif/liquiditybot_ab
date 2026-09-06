"""tests/test_profit_tier_guards.py — Bug 1: NaN entry_price must not poison
the exit floor (risk/profit_tiers.py).

A corrupt/restored Position with entry_price=nan used to poison
_update_high_water via max()/min() (NaN wins both), permanently killing the
trailing floor on the very first evaluate(), and the chandelier anchor
computed off that NaN high_water raised ValueError out of evaluate() once
stop_magnet was enabled (round(nan) in _magnet_grid: "cannot convert float
NaN to integer"). Exits must never be blocked (invariant 5) — a garbage
entry price must degrade safely (fall back to the current price), never
detonate the exit path.
"""
import math
from datetime import datetime, timedelta, timezone

import pytest

from core.codes import Code
from core.state import Position
from risk.profit_tiers import ProfitTierEngine


def _nan_entry_pos(direction="long"):
    return Position(position_id="p1", symbol="ETH/USD", direction=direction,
                    entry_price=float("nan"), size=1.0, original_size=1.0,
                    opened_at=datetime.now(timezone.utc), high_water=None)


def _trail_cfg(**extra):
    return {"trailing_stop": {"enabled": True, "activate_after_tier": 0,
                              "trail_pct": 1.0},
            "be_after_tier": 99, **extra}


def test_nan_entry_price_does_not_poison_high_water():
    eng = ProfitTierEngine(_trail_cfg())
    p = _nan_entry_pos()
    eng.evaluate(p, 100.0)
    assert math.isfinite(p.high_water), \
        "high_water must stay finite even with a NaN entry_price"
    eng.evaluate(p, 101.0)
    assert math.isfinite(p.high_water)
    assert p.trailing_stop_price is None or math.isfinite(p.trailing_stop_price)


def test_nan_entry_price_short_side_high_water_finite():
    eng = ProfitTierEngine(_trail_cfg())
    p = _nan_entry_pos(direction="short")
    eng.evaluate(p, 100.0)
    assert math.isfinite(p.high_water)


def test_nan_entry_price_with_stop_magnet_does_not_raise():
    eng = ProfitTierEngine(_trail_cfg(stop_magnet={"band_bps": 25.0}))
    p = _nan_entry_pos()
    eng.evaluate(p, 100.0)
    eng.evaluate(p, 101.0)   # would raise ValueError: cannot convert NaN to int


# ---- task #89 coverage-pin batch -------------------------------------------

def _pos(direction="long", entry=100.0, tier_closed=0, confidence=0.0,
        opened_at=None):
    return Position(
        position_id=f"p-{direction}", symbol="ETH/USD", direction=direction,
        entry_price=entry, size=1.0, original_size=1.0,
        opened_at=opened_at or datetime.now(timezone.utc),
        confidence=confidence)


# -- 23. short-side tier take mirrors the long side's magnitude -------------
def test_short_side_tier_take_mirrors_long_magnitude():
    # est_fee_bps EXPLICIT (cut #10, B2): the absent-key default moved from
    # 0.0 ("fees are free") to the venue's worst taker row, which arms a
    # break-even floor whose price form is asymmetric between long and short
    # (entry*(1+buf) vs entry*(1-buf)) and broke the mirror by 0.004. This
    # pin's subject is the MIRROR, not fees; explicit 0 is documented-legal.
    cfg = {"tier_1": {"trigger_pct_gain": 2.0, "close_pct_of_position": 25},
           "est_fee_bps": 0}
    long_action = ProfitTierEngine(cfg).evaluate(_pos("long"), 102.0)
    short_action = ProfitTierEngine(cfg).evaluate(_pos("short"), 98.0)
    assert short_action.should_close_partial and short_action.is_profit_take
    assert short_action.tier_fired == 1
    assert short_action.close_pct == pytest.approx(long_action.close_pct)
    assert short_action.realized_pnl == pytest.approx(long_action.realized_pnl)


# -- 24. give-back exact boundaries: arm and tighten thresholds -------------
def _gb_engine(arm=1.5, frac=0.40, tighten=4.0, tight_frac=0.25):
    return ProfitTierEngine({"give_back": {
        "enabled": True, "arm_gain_pct": arm, "giveback_frac": frac,
        "tighten_gain_pct": tighten, "tight_frac": tight_frac}})


def _pos_with_peak(peak_pct, direction="long", entry=100.0):
    p = _pos(direction, entry)
    delta = entry * peak_pct / 100.0
    if direction == "long":
        p.high_water = entry + delta
    else:
        p.high_water = entry - delta
    return p


def test_give_back_arms_exactly_at_the_threshold():
    eng = _gb_engine(arm=1.5)
    below = eng._give_back_candidate(_pos_with_peak(1.4999999999))
    at = eng._give_back_candidate(_pos_with_peak(1.5))
    assert below is None
    assert at is not None


def test_give_back_uses_tighter_frac_exactly_at_tighten_threshold():
    eng = _gb_engine(arm=1.5, frac=0.40, tighten=4.0, tight_frac=0.25)
    entry = 100.0
    just_below_hw = entry + entry * 3.9999999999 / 100.0
    just_below = eng._give_back_candidate(
        _pos_with_peak(3.9999999999))
    at_tighten_hw = entry + entry * 4.0 / 100.0
    at_tighten = eng._give_back_candidate(_pos_with_peak(4.0))
    # below the tighten bar: the LOOSER frac locks (1 - 0.40) of the move
    assert just_below == pytest.approx(entry + 0.60 * (just_below_hw - entry))
    # AT the tighten bar (inclusive): the TIGHTER frac locks (1 - 0.25)
    assert at_tighten == pytest.approx(entry + 0.75 * (at_tighten_hw - entry))


# -- 25. _bars_in_trade clock-skew guards ------------------------------------
def test_bars_in_trade_future_opened_at_clamps_to_zero():
    eng = ProfitTierEngine({})
    opened = datetime(2026, 1, 1, tzinfo=timezone.utc)
    p = _pos(opened_at=opened)
    now_before_open = opened.timestamp() - 3600.0    # 1h BEFORE opened_at
    assert eng._bars_in_trade(p, now=now_before_open) == 0.0


def test_bars_in_trade_non_datetime_opened_at_is_zero_not_raise():
    eng = ProfitTierEngine({})
    p = _pos()
    p.opened_at = "not-a-datetime"          # type: ignore[assignment]
    assert eng._bars_in_trade(p, now=1000.0) == 0.0


# -- 26. exact tier-trigger equality fires (inclusive >=) --------------------
def test_tier_trigger_fires_on_exact_equality():
    cfg = {"tier_1": {"trigger_pct_gain": 3.0, "close_pct_of_position": 50}}
    at = ProfitTierEngine(cfg).evaluate(_pos(entry=100.0), 103.0)
    assert at.should_close_partial and at.is_profit_take
    assert at.tier_fired == 1
    below = ProfitTierEngine(cfg).evaluate(_pos(entry=100.0), 102.9999)
    assert not below.should_close_partial


# -- 27. tier_closed beyond the ladder falls through to pure trail ----------
def test_tier_closed_beyond_ladder_falls_through_to_pure_trail_no_indexerror():
    cfg = {"trailing_stop": {"enabled": True, "activate_after_tier": 0,
                             "trail_pct": 1.0}}
    eng = ProfitTierEngine(cfg)
    p = _pos(entry=100.0)
    p.tier_closed = 7                        # beyond the 4-tier ladder
    eng.evaluate(p, 110.0)                   # sets high_water/stop; no raise
    action = eng.evaluate(p, 108.5)          # 1% trail below hw 110 -> 108.9
    assert action.tier_fired == 7
    assert action.should_close_partial
    assert not action.is_profit_take         # protective floor, not a take


# -- 28. negative confidence mirrors the 0.0 full-leash noop ----------------
def test_negative_confidence_is_full_leash_noop():
    cfg = {"trailing_stop": {"enabled": True, "activate_after_tier": 1,
                             "trail_pct": 1.0},
           "be_after_tier": 99}
    cr = {"conviction_runner": {"enabled": True, "neutral_conf": 0.70,
                                "min_conf": 0.55, "min_trail_mult": 0.6}}
    on = ProfitTierEngine({**cfg, **cr})
    off = ProfitTierEngine(cfg)

    def _conf_pos(conf):
        p = _pos(confidence=conf)
        p.tier_closed = 4
        p.high_water = 110.0
        return p

    px = 109.2   # between the full-leash stop (108.9) and tightened (109.34)
    assert on.evaluate(_conf_pos(-1.0), px).should_close_partial is False
    assert off.evaluate(_conf_pos(-1.0), px).should_close_partial is False


# -- 29. invariant 5: the exit action fires with no entries/disarm flag ----
def test_invariant5_give_back_exit_fires_with_no_entries_flag_consulted():
    """Engine-level pin (full-bot wiring judged disproportionate here):
    ProfitTierEngine.evaluate()'s signature and body (risk/profit_tiers.py)
    consult no entries_enabled/disarm/kill-switch flag anywhere -- confirmed
    by reading the module -- so a position past its give-back floor produces
    the exit action unconditionally. main.py's _manage_open_position (the
    only caller) likewise never gates this call on entries_enabled, only on
    stop_ok / mark-freshness -- exits are never blocked (invariant 5)."""
    eng = ProfitTierEngine({"give_back": {"enabled": True,
                                          "arm_gain_pct": 1.0,
                                          "giveback_frac": 0.5}})
    p = _pos(entry=100.0)
    eng.evaluate(p, 102.0)            # peak +2% arms the give-back floor
    action = eng.evaluate(p, 100.9)   # retrace below the locked 50% floor
    assert action.should_close_partial is True
    assert action.close_pct == pytest.approx(100.0)


# ============================================================================
# Task 2 (P2): time-stop — PT-060 "no favorable progress" scratch
#
# A position that has not reached min_mfe_frac_of_tier1 (shipped 0.5) of the
# tier-1 EFFECTIVE trigger (post vol-scaling/clamp/cost-floor — the exact
# number tier 1 fires on) within max_bars_no_progress (shipped 36 bars = 3h
# at 5m bars) is scratched full-close. Derivation (2026-07-23 P&L diagnosis):
# the no-progress cohort measured MFE 0.16% vs MAE -1.44% and
# recovered_after_stop 0/17 — trades with no early favorable excursion
# overwhelmingly resolve to full-stop losses; scratching them converts a
# -1.4%-class loss into a ~-0.2%-class scratch.
# ============================================================================

_TS_NOW = 1_700_000_000.0     # frozen replay clock (EX-8 discipline)


def _ts_cfg(**overrides):
    ts = {"enabled": True, "max_bars_no_progress": 36,
          "min_mfe_frac_of_tier1": 0.5}
    ts.update(overrides)
    return {"tier_1": {"trigger_pct_gain": 2.0, "close_pct_of_position": 25},
            "time_stop": ts}


def _ts_pos(bars_age, peak_pct=0.0, direction="long", entry=100.0):
    """A position aged exactly `bars_age` bars (5-minute bars) as of
    _TS_NOW, with high_water pre-set to `peak_pct`% favorable excursion
    (reuses the give-back block's _pos_with_peak — the SAME high-water
    machinery, no parallel MFE tracker)."""
    p = _pos_with_peak(peak_pct, direction, entry)
    p.opened_at = (datetime.fromtimestamp(_TS_NOW, tz=timezone.utc)
                  - timedelta(minutes=bars_age * 5.0))
    return p


# -- 30. fires exactly at the bar boundary when MFE < frac x tier-1 ---------
def test_time_stop_fires_exactly_at_boundary_with_no_progress():
    eng = ProfitTierEngine(_ts_cfg())
    at = eng.evaluate(_ts_pos(36, peak_pct=0.0), 100.0, now=_TS_NOW)
    assert at.should_close_partial is True
    assert at.close_pct == pytest.approx(100.0)
    assert at.is_profit_take is False
    assert at.reason_code == Code.PT_TIME_STOP.value

    just_before = eng.evaluate(_ts_pos(35.999, peak_pct=0.0), 100.0,
                               now=_TS_NOW)
    assert just_before.should_close_partial is False


# -- 31. does NOT fire once MFE clears the fraction, even if bars exceeded -
def test_time_stop_does_not_fire_once_mfe_clears_fraction():
    eng = ProfitTierEngine(_ts_cfg())
    # threshold = 0.5 * 2.0% = 1.0% of the tier-1 effective trigger
    at_threshold = eng.evaluate(_ts_pos(200, peak_pct=1.0), 100.0,
                                now=_TS_NOW)
    assert at_threshold.should_close_partial is False   # MFE == threshold, no fire
    just_below = eng.evaluate(_ts_pos(200, peak_pct=0.9999), 100.0,
                              now=_TS_NOW)
    assert just_below.should_close_partial is True
    assert just_below.reason_code == Code.PT_TIME_STOP.value


# -- 32. short-side symmetry --------------------------------------------------
def test_time_stop_short_side_mirrors_long():
    eng = ProfitTierEngine(_ts_cfg())
    long_action = eng.evaluate(_ts_pos(36, peak_pct=0.0, direction="long"),
                               100.0, now=_TS_NOW)
    short_action = eng.evaluate(_ts_pos(36, peak_pct=0.0, direction="short"),
                                100.0, now=_TS_NOW)
    assert short_action.should_close_partial is True
    assert short_action.close_pct == pytest.approx(long_action.close_pct)
    assert short_action.reason_code == Code.PT_TIME_STOP.value


# -- 33. deterministic under injected now (replay discipline, EX-8) --------
def test_time_stop_deterministic_under_injected_now():
    eng = ProfitTierEngine(_ts_cfg())
    pos = _ts_pos(36, peak_pct=0.0)
    first = eng.evaluate(pos, 100.0, now=_TS_NOW)
    # same position, same injected now — later in WALL time must not change
    # the answer (this is exactly the determinism contract the injected
    # clock exists to guarantee)
    second = eng.evaluate(pos, 100.0, now=_TS_NOW)
    assert (first.should_close_partial, first.close_pct, first.tier_fired,
           first.reason_code) == (second.should_close_partial,
                                   second.close_pct, second.tier_fired,
                                   second.reason_code)


# -- 34. invariant 5: fires with no entries/disarm/fault flag consulted ----
def test_time_stop_fires_with_no_entries_flag_consulted():
    """Same engine-level pin as the give-back invariant-5 test above:
    evaluate() takes no entries_enabled/disarm/fault-latch flag anywhere, so
    a no-progress position past max_bars_no_progress is scratched
    unconditionally. The time-stop is an EXIT — it must fire under a
    disarmed / fault-latched posture exactly like every other protective
    close in this module (never gated by anything that blocks NEW risk)."""
    eng = ProfitTierEngine(_ts_cfg())
    action = eng.evaluate(_ts_pos(50, peak_pct=0.0), 100.0, now=_TS_NOW)
    assert action.should_close_partial is True
    assert action.close_pct == pytest.approx(100.0)


# -- 35. enabled: false is fully inert ---------------------------------------
def test_time_stop_disabled_is_fully_inert():
    eng = ProfitTierEngine(_ts_cfg(enabled=False))
    action = eng.evaluate(_ts_pos(500, peak_pct=0.0), 100.0, now=_TS_NOW)
    assert action.should_close_partial is False
    assert action.reason_code == ""


# -- 36. PT-060 is registered and carried on the fired action only ----------
def test_pt_060_registered_and_carried_on_action():
    assert Code.PT_TIME_STOP.value == "PT-060"
    eng = ProfitTierEngine(_ts_cfg())
    action = eng.evaluate(_ts_pos(36, peak_pct=0.0), 100.0, now=_TS_NOW)
    assert action.reason_code == Code.PT_TIME_STOP.value

    # a floor/trail close (not a time-stop) never carries this code
    trail_cfg = {"trailing_stop": {"enabled": True, "activate_after_tier": 0,
                                   "trail_pct": 1.0}, "be_after_tier": 99}
    trail_eng = ProfitTierEngine(trail_cfg)
    p = _pos(entry=100.0)
    trail_eng.evaluate(p, 110.0)
    floor_action = trail_eng.evaluate(p, 108.5)
    assert floor_action.should_close_partial is True
    assert floor_action.reason_code == ""


# ============================================================================
# P2 review fix: time-stop must be gated to VIRGIN positions
# (position.tier_closed == 0). Tier-1's vol-scaled trigger RECLAMPS every
# cycle from CURRENT sigma_bar_pct (not a one-time snapshot at the moment
# tier 1 fired), so a vol spike arriving AFTER tier 1 already banked can
# reclamp the effective trigger above the MFE that was locked in under the
# (lower) vol regime tier 1 actually fired under. An ungated check then
# full-closes (PT-060) a position that already took profit -- contradicting
# the lever's premise ("trades that never work"). Reviewer repro: tier
# fires at low-vol trigger 1.0%; 40 bars later vol spikes -> trigger
# reclamps to 6.0% -> time-stop (pre-fix) fires with close_pct=100.
# ============================================================================

def _ts_cfg_vol(**overrides):
    ts = {"enabled": True, "max_bars_no_progress": 36,
          "min_mfe_frac_of_tier1": 0.5}
    ts.update(overrides)
    return {"tier_1": {"trigger_pct_gain": 2.0, "trigger_vol_mult": 2.0,
                       "close_pct_of_position": 25},
            "time_stop": ts}


# -- 37. reviewer repro: banked tier 1 + post-bank vol spike reclamp must
# NOT scratch the remainder ------------------------------------------------
def test_time_stop_does_not_fire_after_tier1_banked_then_vol_spike_reclamps():
    eng = ProfitTierEngine(_ts_cfg_vol())
    # tier 1 already closed (banked at the low-vol ~1.0% trigger); high_water
    # locked at peak_pct=1.0% favorable excursion -- comfortably past the
    # low-vol trigger, well short of the post-spike reclamped one.
    p = _ts_pos(40, peak_pct=1.0)
    p.tier_closed = 1
    # vol spike: trigger_vol_mult(2.0) * sigma_bar_pct(3.0) = 6.0%, clamped
    # to [0.5x, 3.0x] of legacy 2.0% -> stays at 6.0% (the reviewer's repro
    # number). min_mfe_frac(0.5) * 6.0% = 3.0% > locked MFE 1.0%, which is
    # exactly the condition that (pre-fix) fires the scratch.
    action = eng.evaluate(p, 100.0, sigma_bar_pct=3.0, now=_TS_NOW)
    assert action.should_close_partial is False
    assert action.reason_code != Code.PT_TIME_STOP.value
    assert action.close_pct == pytest.approx(0.0)


# -- 38. complementary pin: identical conditions but VIRGIN (tier_closed=0)
# still fires -- guards the fix from over-gating -----------------------------
def test_time_stop_fires_for_virgin_position_same_vol_spike_conditions():
    eng = ProfitTierEngine(_ts_cfg_vol())
    p = _ts_pos(40, peak_pct=1.0)
    assert p.tier_closed == 0
    action = eng.evaluate(p, 100.0, sigma_bar_pct=3.0, now=_TS_NOW)
    assert action.should_close_partial is True
    assert action.close_pct == pytest.approx(100.0)
    assert action.reason_code == Code.PT_TIME_STOP.value
