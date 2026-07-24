"""tests/test_euphoria_giveback.py — Compounder Phase C, task C5 item 5
(C4-review adjudication): the long tier engine tightens give-back to
`euphoria_giveback_frac` while the context halving phase == "euphoria",
down-only (only applies when strictly tighter than the base
`giveback_frac`) - evidence pass 2 Section 1.1a's disposition-effect
inversion. `risk.profit_tiers.ProfitTierEngine.set_phase` is the wired
seam (main._long_book_cycle calls it once per cycle on the LONG tier
engine instance only - tests/test_long_book_integration.py covers that
wiring; this file tests the engine method itself, mirroring
tests/test_giveback_vol_arm.py's structure)."""
from datetime import datetime, timezone

from core.config_guard import validate
from core.state import Position
from risk.profit_tiers import ProfitTierEngine


def _engine(giveback_frac=0.35, euphoria_frac=0.25):
    return ProfitTierEngine({
        "vol_scaled": False, "est_fee_bps": 0, "be_buffer_bps": 6,
        "give_back": {"enabled": True, "arm_gain_pct": 5.0,
                      "giveback_frac": giveback_frac,
                      "euphoria_giveback_frac": euphoria_frac}})


def _pos(peak_pct):
    p = Position(position_id="p1", symbol="ETH/USD", direction="long",
                 entry_price=100.0, size=1.0, original_size=1.0,
                 opened_at=datetime.now(timezone.utc))
    p.high_water = 100.0 * (1 + peak_pct / 100.0)
    return p


# ---------------------------------------------------------------------
# set_phase: down-only tightening
# ---------------------------------------------------------------------

def test_default_phase_uses_base_giveback_frac():
    eng = _engine()
    assert eng.gb_frac == 0.35
    px = eng._give_back_candidate(_pos(10.0))
    # peak 10% on entry 100 -> hw 110; lock (1-0.35)=65% of the move
    assert abs(px - (100.0 + 0.65 * 10.0)) < 1e-9


def test_euphoria_phase_tightens_to_euphoria_frac():
    eng = _engine(giveback_frac=0.35, euphoria_frac=0.25)
    eng.set_phase("euphoria")
    assert eng.gb_frac == 0.25
    px = eng._give_back_candidate(_pos(10.0))
    assert abs(px - (100.0 + 0.75 * 10.0)) < 1e-9


def test_non_euphoria_phase_restores_base():
    eng = _engine(giveback_frac=0.35, euphoria_frac=0.25)
    eng.set_phase("euphoria")
    eng.set_phase("expansion")
    assert eng.gb_frac == 0.35


def test_set_phase_is_idempotent_across_repeated_calls():
    eng = _engine(giveback_frac=0.35, euphoria_frac=0.25)
    eng.set_phase("euphoria")
    eng.set_phase("euphoria")
    eng.set_phase("euphoria")
    assert eng.gb_frac == 0.25


def test_never_called_engine_is_byte_identical_legacy():
    # a caller that never heard of set_phase (the 5m book's own engine
    # instance, run_trials' harness) must be untouched.
    eng = _engine(giveback_frac=0.35, euphoria_frac=0.25)
    assert eng.gb_frac == 0.35
    assert eng.gb_euphoria_frac == 0.25


def test_down_only_euphoria_looser_than_base_is_inert():
    # a euphoria_giveback_frac LOOSER than the base (config_guard FATALs
    # this combination live - see test below) must still never loosen
    # protection at the engine level: defense in depth.
    eng = _engine(giveback_frac=0.25, euphoria_frac=0.35)
    eng.set_phase("euphoria")
    assert eng.gb_frac == 0.25, \
        "a looser euphoria fraction must never override the base"


def test_absent_euphoria_frac_defaults_to_base_exactly_inert():
    eng = ProfitTierEngine({
        "give_back": {"enabled": True, "arm_gain_pct": 5.0,
                      "giveback_frac": 0.35}})
    assert eng.gb_euphoria_frac == 0.35
    eng.set_phase("euphoria")
    assert eng.gb_frac == 0.35


def test_tight_frac_rederived_against_currently_armed_base():
    # tight_frac (the tighten_gain_pct escalation's OWN share) is clamped
    # to whatever base is currently armed - never stranded above a
    # tightened euphoria base.
    eng = ProfitTierEngine({
        "give_back": {"enabled": True, "arm_gain_pct": 5.0,
                      "giveback_frac": 0.35, "euphoria_giveback_frac": 0.10,
                      "tight_frac": 0.25, "tighten_gain_pct": 4.0}})
    assert eng.gb_tight_frac == 0.25          # 0.25 <= base 0.35
    eng.set_phase("euphoria")
    assert eng.gb_tight_frac == 0.10          # reclamped to the new 0.10 base
    eng.set_phase("expansion")
    assert eng.gb_tight_frac == 0.25          # restored


# ---------------------------------------------------------------------
# config_guard: down-only coherence FATAL
# ---------------------------------------------------------------------

def _fatals(cfg):
    return [m for s, m in validate(cfg) if s == "FATAL"]


def _lb_cfg(giveback_frac, euphoria_frac):
    return {
        "exchanges": {"kraken": {"trading_pairs": ["BTC/USD", "ETH/USD"]}},
        "risk_protocols": {"heat": {"max_portfolio_heat_frac": 0.35}},
        "long_book": {
            "enabled": True, "assets": ["BTC"],
            "add_usd_frac_of_ceiling": 0.2, "add_min_spacing_hours": 24.0,
            "add_offset_pct": 0.5, "zone_tol_pct": 0.15,
            "zone_buffer_pct": 0.2, "order_ttl_hours": 6.0,
            "retry_backoff_minutes": 30.0, "thesis_stop_pct": 12.0,
            "ladder": {
                "r1": {"ceiling_frac": 0.10, "min_closed_paper": 10},
                "r2": {"ceiling_frac": 0.20, "min_closed_live": 15,
                      "pf_floor": 1.2},
                "r3": {"ceiling_frac": 0.30, "min_closed_live": 30,
                      "adverse_transitions_survived": 1},
                "dd_downgrade_pct": 6.0,
            },
            "profit_taking": {
                "give_back": {"enabled": True, "giveback_frac": giveback_frac,
                             "euphoria_giveback_frac": euphoria_frac},
                "time_stop": {"enabled": False},
            },
        },
    }


def test_config_guard_fatals_looser_euphoria_frac():
    assert any("euphoria_giveback_frac" in m
              for m in _fatals(_lb_cfg(0.35, 0.40)))


def test_config_guard_clean_when_euphoria_tighter():
    assert not any("euphoria_giveback_frac" in m
                  for m in _fatals(_lb_cfg(0.35, 0.25)))


def test_config_guard_clean_when_euphoria_equal_to_base():
    assert not any("euphoria_giveback_frac" in m
                  for m in _fatals(_lb_cfg(0.35, 0.35)))


def test_config_guard_clean_when_euphoria_absent():
    cfg = _lb_cfg(0.35, 0.25)
    del cfg["long_book"]["profit_taking"]["give_back"]["euphoria_giveback_frac"]
    assert not any("euphoria_giveback_frac" in m for m in _fatals(cfg))
