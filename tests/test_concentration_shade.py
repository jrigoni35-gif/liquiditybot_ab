"""Evidence-concentration confidence shade (TH-021, docs/THALES.md §Evidence
concentration). The fused informed-flow evidence E = Σ wᵢ·sᵢ is a weighted SUM,
so a diffuse 5-of-weak scores like a 2-of-screaming (the 'averaging trap').
`evidence_concentration` (normalized Herfindahl, 0 diffuse .. 1 pinpointed)
measures which it is. This shade ATTENUATES a diffuse-AND-marginal signal's
confidence toward a floor while leaving concentrated conviction (or a strongly
confident signal) untouched. DOWN-only, bounded, and DISABLED by default —
enabling it is the gated promotion step, not a silent behavior change.
"""
import math

from strategies.signal_gates import concentration_conf_mult

ON = {"enabled": True, "conc_pivot": 0.35, "max_atten": 0.15,
      "marginal_conf": 0.65, "floor_conf": 0.50}


def test_disabled_is_exact_identity():
    for conc in (0.0, 0.1, 0.5, 0.9):
        for conf in (0.5, 0.6, 0.8):
            assert concentration_conf_mult(conc, conf, {"enabled": False}) == 1.0
            assert concentration_conf_mult(conc, conf, {}) == 1.0


def test_diffuse_and_marginal_is_attenuated():
    m = concentration_conf_mult(0.05, 0.52, ON)      # very diffuse, marginal
    assert m < 1.0 and m >= 1.0 - ON["max_atten"] - 1e-9


def test_concentrated_conviction_is_untouched():
    # high concentration -> not diffuse -> no attenuation even when marginal
    assert concentration_conf_mult(0.90, 0.52, ON) == 1.0
    assert concentration_conf_mult(0.35, 0.52, ON) == 1.0   # at the pivot


def test_strong_confidence_is_untouched_even_if_diffuse():
    # a confidently-strong signal is not "marginal" -> left alone
    assert concentration_conf_mult(0.05, 0.80, ON) == 1.0


def test_more_diffuse_attenuates_more_at_fixed_marginality():
    a = concentration_conf_mult(0.20, 0.52, ON)
    b = concentration_conf_mult(0.05, 0.52, ON)
    assert b < a < 1.0        # more diffuse (0.05) -> deeper trim than (0.20)


def test_result_is_always_bounded_down_only():
    for conc in (0.0, 0.01, 0.2, 0.34, 0.4, 0.9, 1.0):
        for conf in (0.0, 0.4, 0.5, 0.55, 0.65, 0.9, 1.0):
            m = concentration_conf_mult(conc, conf, ON)
            assert 1.0 - ON["max_atten"] - 1e-9 <= m <= 1.0


def test_bad_inputs_are_noops():
    for bad in (None, float("nan"), float("inf")):
        assert concentration_conf_mult(bad, 0.52, ON) == 1.0
        assert concentration_conf_mult(0.05, bad, ON) == 1.0
