"""Vol-scaled give-back arm (2026-07-20 tuning pass, peak-performance rev).

A static arm is fitted to ONE vol regime's MFE envelope and goes stale when
vol moves — the 1.5% arm sat above MFE p90 (0.72%) and armed once in 55
trades. arm_vol_mult arms at mult * sigma_bar (the same rev-3 calculus the
tiers use), so the ratchet tracks the envelope it protects; the static
arm_gain_pct stays as the fallback when sigma is unavailable. Plateau-
verified in the quant sim (static/1.5/2.0/2.5/3.0 sigma all within noise —
no peak to overfit, OF-4 clean).
"""
from datetime import datetime, timezone

from core.state import Position
from ml.labeling import ExitPolicy
from risk.profit_tiers import ProfitTierEngine


def _engine(mult, arm_static=0.6):
    return ProfitTierEngine({
        "vol_scaled": False, "est_fee_bps": 40, "be_buffer_bps": 6,
        "give_back": {"enabled": True, "arm_gain_pct": arm_static,
                      "arm_vol_mult": mult, "giveback_frac": 0.4,
                      "tighten_gain_pct": 4.0, "tight_frac": 0.25}})


def _pos(peak_pct):
    p = Position(position_id="p1", symbol="ETH/USD", direction="long",
                 entry_price=100.0, size=1.0, original_size=1.0,
                 opened_at=datetime.now(timezone.utc))
    p.high_water = 100.0 * (1 + peak_pct / 100.0)
    return p


def test_vol_scaled_arm_tracks_sigma():
    eng = _engine(2.0)
    # sigma 0.3%/bar -> arm at 0.6%: a 0.7% peak arms, a 0.5% peak does not
    assert eng._give_back_candidate(_pos(0.7), sigma_bar_pct=0.3) is not None
    assert eng._give_back_candidate(_pos(0.5), sigma_bar_pct=0.3) is None
    # high-vol regime, sigma 1.0 -> arm 2.0%: the same 0.7% peak is noise
    assert eng._give_back_candidate(_pos(0.7), sigma_bar_pct=1.0) is None
    assert eng._give_back_candidate(_pos(2.1), sigma_bar_pct=1.0) is not None


def test_missing_sigma_falls_back_to_static_arm():
    eng = _engine(2.0, arm_static=0.6)
    assert eng._give_back_candidate(_pos(0.7), sigma_bar_pct=None) is not None
    assert eng._give_back_candidate(_pos(0.5), sigma_bar_pct=None) is None


def test_mult_zero_is_pure_legacy():
    eng = _engine(0.0, arm_static=0.6)
    # sigma present but mult off -> static arm decides
    assert eng._give_back_candidate(_pos(0.7), sigma_bar_pct=5.0) is not None


def test_armed_ratchet_locks_the_configured_share():
    eng = _engine(2.0)
    px = eng._give_back_candidate(_pos(1.0), sigma_bar_pct=0.3)
    # peak 1% on entry 100 -> hw 101; lock 60% of the move -> 100.6
    assert abs(px - 100.6) < 1e-9


def test_labeler_mirrors_the_vol_scaled_arm():
    pol = ExitPolicy.from_config({
        "profit_taking": {"give_back": {"enabled": True,
                                        "arm_gain_pct": 0.6,
                                        "arm_vol_mult": 2.0}},
        "risk": {}})
    assert pol.gb_arm_vol_mult == 2.0
    assert abs(pol.gb_arm_frac - 0.006) < 1e-12       # fallback preserved


def test_guard_bounds():
    from core.config_guard import validate

    def _sev(cfg, sev):
        return [m for s, m in validate(cfg) if s == sev]

    def _cfg(mult):
        return {"system": {"dry_run": True},
                "profit_taking": {"give_back": {"enabled": True,
                                                "giveback_frac": 0.4,
                                                "tight_frac": 0.25,
                                                "arm_gain_pct": 0.6,
                                                "arm_vol_mult": mult}}}
    assert not any("arm_vol_mult" in m for m in _sev(_cfg(2.0), "FATAL"))
    assert not any("arm_vol_mult" in m for m in _sev(_cfg(0.0), "FATAL"))
    assert any("arm_vol_mult" in m for m in _sev(_cfg(0.2), "FATAL"))
    assert any("arm_vol_mult" in m for m in _sev(_cfg(9.0), "FATAL"))
