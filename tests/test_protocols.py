"""Acceptance tests for the rev-4 risk protocol stack (risk/protocols.py)
and the give-back exit ratchet (risk/profit_tiers.py). Same discipline
as the overfit suite: every property is checked in BOTH directions —
the mechanism engages when it should and stays out of the way when it
shouldn't."""
from datetime import datetime, timezone

import numpy as np

from core.state import Position
from risk.profit_tiers import ProfitTierEngine
from risk.protocols import (RiskProtocolStack, budget_taper_mult,
                            cvar_cap_frac, give_back_stop,
                            heat_headroom_frac, vol_target_mult)


def _pos(direction="long", entry=100.0, hw=None):
    return Position(position_id="t1", symbol="ETH/USD", direction=direction,
                    entry_price=entry, size=1.0, original_size=1.0,
                    opened_at=datetime.now(timezone.utc), high_water=hw)


def _engine(**gb):
    cfg = {"tier_1": {"trigger_pct_gain": 99.0, "close_pct_of_position": 25},
           "trailing_stop": {"enabled": False},
           "be_after_tier": 9,          # BE + chandelier out of the way
           "est_fee_bps": 40,
           "give_back": {"enabled": True, "arm_gain_pct": 1.5,
                         "giveback_frac": 0.40, "tighten_gain_pct": 4.0,
                         "tight_frac": 0.25, **gb}}
    return ProfitTierEngine(cfg)


# ------------------------------------------------------------ pure function
def test_give_back_stop_math_both_sides():
    # long: entry 100, hw 110, frac .4 -> lock 60% of the 10 move -> 106
    assert float(give_back_stop(100.0, 110.0, True, 0.4)) == 106.0
    # short mirrored: entry 100, hw 90 -> 94
    assert float(give_back_stop(100.0, 90.0, False, 0.4)) == 94.0
    # no favorable move -> stop pinned at entry, never worse
    assert float(give_back_stop(100.0, 95.0, True, 0.4)) == 100.0


# ------------------------------------------------------------- tier engine
def test_give_back_disarmed_below_threshold():
    eng, p = _engine(), _pos()
    a = eng.evaluate(p, 101.0)           # +1.0% peak < 1.5% arm
    assert not a.should_close_partial
    assert p.trailing_stop_price is None


def test_give_back_arms_and_locks_share_of_peak():
    eng, p = _engine(), _pos()
    eng.evaluate(p, 102.0)               # peak +2% >= arm: floor 101.2
    assert p.trailing_stop_price is not None
    assert abs(p.trailing_stop_price - 101.2) < 1e-9
    # price gives back past the floor -> full exit
    a = eng.evaluate(p, 101.1)
    assert a.should_close_partial and a.close_pct == 100.0


def test_give_back_second_rung_tightens():
    eng, p = _engine(), _pos()
    eng.evaluate(p, 105.0)               # peak +5% >= tighten: lock 75%
    assert p.trailing_stop_price is not None
    assert abs(p.trailing_stop_price - 103.75) < 1e-9


def test_give_back_never_loosens():
    eng, p = _engine(), _pos()
    eng.evaluate(p, 105.0)
    hi = p.trailing_stop_price
    assert hi is not None
    eng.evaluate(p, 104.0)               # retrace must not lower the floor
    assert p.trailing_stop_price is not None
    assert p.trailing_stop_price >= hi


def test_give_back_short_side_mirrors():
    eng, p = _engine(), _pos(direction="short")
    eng.evaluate(p, 95.0)                # peak +5% short: lock 75% -> 96.25
    assert p.trailing_stop_price is not None
    assert abs(p.trailing_stop_price - 96.25) < 1e-9
    a = eng.evaluate(p, 96.5)
    assert a.should_close_partial and a.close_pct == 100.0


def test_give_back_restart_reconstruction():
    """The floor is a pure function of (entry, high_water, config): a
    fresh engine fed a resumed Position must land the identical stop."""
    eng1, p1 = _engine(), _pos()
    eng1.evaluate(p1, 103.0)
    p2 = _pos(hw=p1.high_water)          # what persistence restores
    eng2 = _engine()
    eng2.evaluate(p2, 100.5)             # any px below hw, above floor
    assert p1.trailing_stop_price is not None and p2.trailing_stop_price is not None
    assert abs(p1.trailing_stop_price - p2.trailing_stop_price) < 1e-9


def test_give_back_disabled_is_inert():
    eng, p = _engine(enabled=False), _pos()
    eng.evaluate(p, 110.0)
    assert p.trailing_stop_price is None


# --------------------------------------------------------------- stack math
def test_vol_target_mult_bounds_and_direction():
    lo, hi = 0.25, 1.15
    hot = float(vol_target_mult(90.0, 45.0, lo, hi))
    cold = float(vol_target_mult(20.0, 45.0, lo, hi))
    assert lo <= hot < 1.0 < cold <= hi


def test_cvar_cap_shrinks_with_fatter_tail():
    from risk.protocols import es_historical
    thin = np.random.default_rng(0).normal(0, 0.001, 300)
    fat = np.random.default_rng(0).standard_t(2, 300) * 0.004
    f_thin = cvar_cap_frac(es_historical(thin, 0.975), 24, 0.01)
    f_fat = cvar_cap_frac(es_historical(fat, 0.975), 24, 0.01)
    assert f_fat < f_thin


def test_budget_taper_engages_then_hard_zero():
    assert float(budget_taper_mult(0.3, 0.5, 0.15)) == 1.0
    assert 0.15 <= float(budget_taper_mult(0.8, 0.5, 0.15)) < 1.0
    assert float(budget_taper_mult(1.05, 0.5, 0.15)) == 0.0


def test_heat_headroom_monotone():
    a = float(heat_headroom_frac(0.0, 0.35, 0.9))
    b = float(heat_headroom_frac(0.3, 0.35, 0.9))
    assert a == 0.35 and 0.0 <= b < a


# ------------------------------------------------- CVaR return-sample cadence
# 2026-07-29 unit audit (cross-confirmed by two independent auditors): the
# CVaR buffer's parameterization is per-5m-BAR (lookback_bars 288 = one day,
# sqrt(horizon_bars) holding scale, min_obs 120 = 10h) and both CI harnesses
# (scripts/quant_trials.py, scripts/smoke_test.py) feed one observe per 300s
# bar — but live, observe() ran every ~5s poll and appended PER-POLL returns,
# deflating es_bar by ~sqrt(60) and loosening the RP-040 cap ~7.75x. The fix
# samples the buffer on the bar clock regardless of poll cadence.

def test_cvar_returns_sample_on_the_bar_clock_not_the_poll_clock():
    import math
    st = RiskProtocolStack({"enabled": True})
    t0 = 1_700_000_000.0
    st.observe(1000.0, {"ETH/USD": 100.0}, now=t0)             # bar anchor
    # 59 fast polls inside the bar: marks move, buffer must NOT grow
    for i in range(1, 60):
        st.observe(1000.0, {"ETH/USD": 100.0 + i * 0.01}, now=t0 + 5.0 * i)
    assert len(st._rets.get("ETH/USD", [])) == 0
    # bar boundary: exactly ONE compound bar return, anchored bar-close to
    # bar-close — never the last 5s tick return
    st.observe(1000.0, {"ETH/USD": 103.0}, now=t0 + 300.0)
    buf = list(st._rets["ETH/USD"])
    assert len(buf) == 1
    assert abs(buf[0] - math.log(103.0 / 100.0)) < 1e-12
    # next bar continues from the new anchor
    st.observe(1000.0, {"ETH/USD": 103.0}, now=t0 + 355.0)     # intra-bar
    st.observe(1000.0, {"ETH/USD": 101.0}, now=t0 + 600.0)     # boundary
    buf = list(st._rets["ETH/USD"])
    assert len(buf) == 2
    assert abs(buf[1] - math.log(101.0 / 103.0)) < 1e-12


def test_cvar_harness_bar_cadence_appends_every_step():
    # the quant-trials/smoke cadence (one observe per 300s) must behave
    # byte-identically to before the fix: every step appends one return
    st = RiskProtocolStack({"enabled": True})
    t0, px = 1_700_000_000.0, 100.0
    st.observe(1000.0, {"ETH/USD": px}, now=t0)
    for i in range(1, 6):
        px *= 1.001
        st.observe(1000.0, {"ETH/USD": px}, now=t0 + 300.0 * i)
    assert len(st._rets["ETH/USD"]) == 5


def test_cvar_per_asset_bar_clocks_are_independent():
    st = RiskProtocolStack({"enabled": True})
    t0 = 1_700_000_000.0
    st.observe(1000.0, {"ETH/USD": 100.0}, now=t0)
    st.observe(1000.0, {"BTC/USD": 50_000.0}, now=t0 + 100.0)  # later anchor
    st.observe(1000.0, {"ETH/USD": 101.0, "BTC/USD": 50_500.0},
               now=t0 + 300.0)
    # ETH bar elapsed (300s since its anchor); BTC bar has not (200s)
    assert len(st._rets.get("ETH/USD", [])) == 1
    assert len(st._rets.get("BTC/USD", [])) == 0


def test_stack_warmup_is_neutral_and_never_raises():
    st = RiskProtocolStack({"enabled": True})
    m, reasons = st.entry_multiplier(proposed_frac=0.05, equity=10_000.0,
                                     sigma_ann_pct=float("nan"),
                                     asset_symbol="ETH/USD",
                                     open_heat_frac=0.0)
    assert 0.0 < m <= 1.0
    assert any("RP-060" in r for r in reasons) or m == 1.0


# ---------------------------------------------------------- open-heat wiring
def test_open_heat_reads_position_size_not_units():
    """Regression: an earlier draft read a nonexistent `units` attribute,
    which zeroed heat for every real Position and made the RP-050/051
    heat gates unreachable in production.

    2026-08-09 - THIS TEST FAILED AT ITS OWN JOB and the fix is instructive.
    It guards against a nonexistent field on Position while its own double
    exposed `positions`, a nonexistent attribute on STATE (PortfolioState
    keeps `_positions`, read via `open_positions()`). The sizer read
    `getattr(state, "positions", {})`, so the identical bug the docstring
    describes - a nonexistent attribute zeroing heat and making the heat
    gates unreachable - was live one level up, and this test could not see
    it because the double supplied the missing attribute itself. The double
    now mirrors the REAL accessor; a double may only implement API the
    production object actually has."""
    from risk.position_sizer import PositionSizer

    class _State:
        _positions = {"a": _pos(entry=2000.0)}         # size=1.0

        def open_positions(self):
            return list(self._positions.values())

    h = PositionSizer._open_heat_frac(_State(), {"ETH/USD": 2000.0},
                                      equity=10_000.0)
    assert abs(h - 0.2) < 1e-9, f"heat must be notional/equity, got {h}"


def test_open_heat_full_book_hard_vetoes_entry():
    st = RiskProtocolStack({"enabled": True,
                            "cvar": {"enabled": False},
                            "gap": {"enabled": False},
                            "budget": {"enabled": False},
                            "heat": {"enabled": True,
                                     "max_portfolio_heat_frac": 0.35,
                                     "assumed_corr": 1.0}})
    m, reasons = st.entry_multiplier(proposed_frac=0.05, equity=10_000.0,
                                     sigma_ann_pct=45.0,
                                     asset_symbol="ETH/USD",
                                     open_heat_frac=0.40)   # over the cap
    assert m == 0.0
    assert any("RP-051" in r for r in reasons), reasons


def test_guard_bounds_cvar_bar_sec():
    """2026-07-29 wave-1 adversarial-verify coverage gap: cvar.bar_sec
    (the CVaR sampling bar clock shipped in the bar-clock fix) had zero
    config_guard coverage. Bounds keep it a BAR clock: below 60s it
    degenerates back toward the per-poll cadence the fix removed (the
    ~sqrt(60) ES deflation); any non-300 value diverges live measurement
    from the quant-trials/smoke baseline and must warn."""
    from core.config_guard import validate

    def _sev(v, s):
        return [m for sev, m in validate(
            {"risk_protocols": {"cvar": {"bar_sec": v}}}) if sev == s]

    assert not any("bar_sec" in m for m in _sev(300.0, "FATAL"))
    assert not any("bar_sec" in m for m in _sev(300.0, "WARN"))
    assert any("bar_sec" in m for m in _sev(5.0, "FATAL"))
    assert any("bar_sec" in m for m in _sev(3600.0, "FATAL"))
    assert any("bar_sec" in m for m in _sev(600.0, "WARN"))
