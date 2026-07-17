"""tests/test_signal_literal_lift.py — §B guessing-code lift is behavior-
preserving: with default config the engine's urgency composition, freshness
decay and opposing-flow tolerance equal the old hardcoded constants exactly
(the existing signal suites then prove the decision path unchanged), and the
lifted knobs steer when configured."""
import pytest

from strategies.informed_flow import InformedFlowEngine


def test_defaults_equal_old_constants():
    e = InformedFlowEngine({})
    assert e.u_base == 0.30
    assert e.u_w_burst == 0.40
    assert e.u_w_fresh == 0.20
    assert e.u_w_delta == 0.10
    assert e.u_fresh_decay == 6.0
    assert e.opp_tol_frac == 0.25
    # max reachable urgency at defaults is exactly 1.0 — the taker rung
    # (0.88) stays reachable, the composition is complete
    assert e.u_base + e.u_w_burst + e.u_w_fresh + e.u_w_delta == \
        pytest.approx(1.0)


def test_knobs_steer_and_clamp():
    e = InformedFlowEngine({"urgency": {"base": 0.5, "w_burst": 0.2,
                                        "w_fresh": 0.1, "w_delta": 0.05,
                                        "fresh_decay_evals": 12},
                            "opp_flow_tol_frac": 0.5})
    assert (e.u_base, e.u_w_burst, e.u_w_fresh, e.u_w_delta) == \
        (0.5, 0.2, 0.1, 0.05)
    assert e.u_fresh_decay == 12.0
    assert e.opp_tol_frac == 0.5
    # hostile values clamp instead of poisoning the composition
    h = InformedFlowEngine({"urgency": {"base": -1, "w_burst": -5,
                                        "fresh_decay_evals": 0},
                            "opp_flow_tol_frac": 9})
    assert h.u_base == 0.0 and h.u_w_burst == 0.0
    assert h.u_fresh_decay == 1.0          # floor: never divide by zero
    assert h.opp_tol_frac == 1.0
