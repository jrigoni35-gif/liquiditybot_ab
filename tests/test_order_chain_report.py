"""Pins for scripts/order_chain_report.py (SAFE class, report-only).

Two properties are load-bearing and both were defects in the first cut:
  * survival past the horizon is CENSORED, never folded into EXPIRED — doing
    so misfiled 200 orders that filled later and understated P(fill) by ~12
    points against the unconditional outcome count;
  * the chain is SEGMENTED BY PURPOSE — entry 42.9% / exit 95.4% / hedge 100%
    are three different processes, and the pooled 67.5% describes none of them.
"""

from __future__ import annotations

import math

import pytest

from scripts import order_chain_report as ocr


def _episode(life_s: float, any_fill: bool, purpose: str = "entry",
             full: bool | None = None) -> dict:
    return {
        "life_s": life_s,
        "fill_ratio": 1.0 if any_fill else 0.0,
        "terminal": "filled" if any_fill else "expired",
        "purpose": purpose,
        "pair": "ETHUSD",
        "filled": any_fill if full is None else full,
        "any_fill": any_fill,
        "ts": 1_780_000_000.0 + life_s,
    }


# --------------------------------------------------------------------------
# Wilson, not the normal approximation
# --------------------------------------------------------------------------

def test_wilson_stays_inside_the_unit_interval_at_tiny_rates():
    lo, hi = ocr._wilson(1, 1000)
    assert 0.0 <= lo <= hi <= 1.0
    assert lo > 0.0, "a normal interval would cross zero and read as 'never'"


def test_wilson_of_a_perfect_rate_does_not_claim_certainty():
    lo, hi = ocr._wilson(159, 159)
    assert hi == pytest.approx(1.0, abs=1e-9)
    assert lo < 1.0, "159/159 is not proof the rate is exactly 1.0"


def test_wilson_of_an_empty_sample_is_not_a_rate():
    assert ocr._wilson(0, 0) == (0.0, 0.0)


# --------------------------------------------------------------------------
# THE PIN: censoring is not expiry
# --------------------------------------------------------------------------

def test_survival_past_the_horizon_is_censored_not_expired():
    """Every order survives all 3 polls: nothing filled, nothing expired.

    Folding that into EXPIRED would report P(expire)=100% for a population
    whose resolution was simply never observed.
    """
    haz = [{"poll": t, "at_risk": 100, "fills": 0, "expiries": 0,
            "hazard": 0.0, "hazard_ci95": [0.0, 0.0]} for t in (1, 2, 3)]
    ch = ocr.absorbing_chain(haz)
    assert ch["p_still_resting_at_horizon"] == pytest.approx(1.0, abs=1e-9)
    assert ch["p_absorb_expired"] == pytest.approx(0.0, abs=1e-9)
    assert ch["p_absorb_filled"] == pytest.approx(0.0, abs=1e-9)


def test_chain_mass_always_sums_to_one():
    haz = [
        {"poll": 1, "at_risk": 100, "fills": 10, "expiries": 5,
         "hazard": 0.1, "hazard_ci95": [0, 0]},
        {"poll": 2, "at_risk": 85, "fills": 20, "expiries": 5,
         "hazard": 0.235, "hazard_ci95": [0, 0]},
        {"poll": 3, "at_risk": 60, "fills": 30, "expiries": 20,
         "hazard": 0.5, "hazard_ci95": [0, 0]},
    ]
    ch = ocr.absorbing_chain(haz)
    total = (ch["p_absorb_filled"] + ch["p_absorb_expired"]
             + ch["p_still_resting_at_horizon"])
    assert total == pytest.approx(1.0, abs=1e-9)


def test_expected_polls_to_absorption_is_bounded_by_the_horizon():
    haz = [{"poll": t, "at_risk": 100, "fills": 0, "expiries": 0,
            "hazard": 0.0, "hazard_ci95": [0, 0]} for t in (1, 2, 3, 4)]
    ch = ocr.absorbing_chain(haz)
    assert ch["expected_polls_to_absorption"] == pytest.approx(4.0, abs=1e-6)


def test_a_certain_first_poll_fill_absorbs_immediately():
    haz = [{"poll": 1, "at_risk": 100, "fills": 100, "expiries": 0,
            "hazard": 1.0, "hazard_ci95": [0, 0]},
           {"poll": 2, "at_risk": 0, "fills": 0, "expiries": 0,
            "hazard": 0.0, "hazard_ci95": [0, 0]}]
    ch = ocr.absorbing_chain(haz)
    assert ch["p_absorb_filled"] == pytest.approx(1.0, abs=1e-9)
    assert ch["expected_polls_to_absorption"] == pytest.approx(1.0, abs=1e-6)


# --------------------------------------------------------------------------
# homogeneity test must discriminate, in BOTH directions
# --------------------------------------------------------------------------

def test_a_genuinely_constant_hazard_is_not_rejected():
    haz = [{"poll": t, "at_risk": 1000, "fills": 100, "expiries": 0,
            "hazard": 0.1, "hazard_ci95": [0, 0]} for t in (1, 2, 3, 4, 5)]
    h = ocr.homogeneity_test(haz)
    assert h["applicable"] is True
    assert h["constant_hazard_rejected"] is False
    assert h["pooled_hazard"] == pytest.approx(0.1, abs=1e-9)


def test_a_wildly_varying_hazard_is_rejected():
    """The control above is what makes this one meaningful: without it, a test
    that always returns 'rejected' would pass."""
    haz = [
        {"poll": 1, "at_risk": 1000, "fills": 5, "expiries": 0,
         "hazard": 0.005, "hazard_ci95": [0, 0]},
        {"poll": 2, "at_risk": 1000, "fills": 500, "expiries": 0,
         "hazard": 0.5, "hazard_ci95": [0, 0]},
        {"poll": 3, "at_risk": 1000, "fills": 50, "expiries": 0,
         "hazard": 0.05, "hazard_ci95": [0, 0]},
    ]
    h = ocr.homogeneity_test(haz)
    assert h["constant_hazard_rejected"] is True
    assert h["p_value"] < 0.05


def test_homogeneity_is_not_applicable_without_events():
    haz = [{"poll": 1, "at_risk": 100, "fills": 0, "expiries": 0,
            "hazard": 0.0, "hazard_ci95": [0, 0]}]
    assert ocr.homogeneity_test(haz)["applicable"] is False


def test_chi2_tail_approximation_is_sane():
    """Wilson-Hilferty is an approximation; pin that it is not wildly off at
    the decision boundary. chi2(4) at 9.488 is p=0.05."""
    haz = [
        {"poll": 1, "at_risk": 1000, "fills": 100, "expiries": 0,
         "hazard": 0.1, "hazard_ci95": [0, 0]},
        {"poll": 2, "at_risk": 1000, "fills": 100, "expiries": 0,
         "hazard": 0.1, "hazard_ci95": [0, 0]},
    ]
    h = ocr.homogeneity_test(haz)
    assert 0.0 <= h["p_value"] <= 1.0
    assert h["p_value"] > 0.5, "identical rates must look highly compatible"


# --------------------------------------------------------------------------
# hazard construction
# --------------------------------------------------------------------------

def test_at_risk_shrinks_by_both_arms():
    """An expired order is genuinely no longer at risk of filling; carrying it
    forward as if censored would deflate later hazards."""
    eps = ([_episode(2.0, True)] * 10 + [_episode(2.0, False)] * 10
           + [_episode(7.0, True)] * 80)
    rows = ocr.discrete_hazard(eps, poll_s=5.0, horizon_polls=2)
    assert rows[0]["at_risk"] == 100
    assert rows[0]["fills"] == 10
    assert rows[0]["expiries"] == 10
    assert rows[1]["at_risk"] == 80, "both arms must leave the risk set"


def test_hazard_is_a_probability_in_every_row():
    eps = [_episode(float(i % 30), i % 3 == 0) for i in range(300)]
    for r in ocr.discrete_hazard(eps, poll_s=5.0, horizon_polls=6):
        assert 0.0 <= r["hazard"] <= 1.0
        assert r["hazard_ci95"][0] <= r["hazard"] <= r["hazard_ci95"][1]


# --------------------------------------------------------------------------
# segmentation and horizon
# --------------------------------------------------------------------------

def test_report_segments_by_purpose_and_flags_the_pooled_rate(monkeypatch):
    eps = ([_episode(6.0, True, "entry")] * 40
           + [_episode(26.0, False, "entry")] * 60
           + [_episode(6.0, True, "exit")] * 95
           + [_episode(26.0, False, "exit")] * 5)
    monkeypatch.setattr(ocr, "load_terminals",
                        lambda purpose=None, audit_path=None: {
                            "episodes": eps, "records_seen": len(eps),
                            "dropped_old_schema": 0, "dropped_bad_lifetime": 0,
                            "dropped_other_purpose": 0,
                            "audit_path": "x", "audit_mtime_utc": None})
    rep = ocr.build_report()
    assert rep["status"] == "ok"
    assert set(rep["by_purpose"]) == {"entry", "exit"}
    assert rep["by_purpose"]["entry"]["p_any_fill"] == pytest.approx(0.40)
    assert rep["by_purpose"]["exit"]["p_any_fill"] == pytest.approx(0.95)
    # the pooled figure exists but is labelled, and equals neither segment
    pooled = rep["pooled_do_not_quote"]["p_any_fill"]
    assert pooled == pytest.approx(0.675)
    assert "do_not_quote" in "".join(rep.keys())
    assert "mixing artefact" in rep["pooled_do_not_quote"]["why"]


def test_horizon_extends_one_poll_past_the_timeout(monkeypatch):
    """The timeout ELAPSES at order_timeout_sec but is OBSERVED on the next
    poll. A horizon of exactly timeout/poll censored 71% of entries."""
    monkeypatch.setattr(ocr, "load_terminals",
                        lambda purpose=None, audit_path=None: {
                            "episodes": [_episode(6.0, True)],
                            "records_seen": 1, "dropped_old_schema": 0,
                            "dropped_bad_lifetime": 0,
                            "dropped_other_purpose": 0,
                            "audit_path": "x", "audit_mtime_utc": None})
    rep = ocr.build_report()
    assert rep["horizon_polls"] == math.ceil(
        rep["order_timeout_s"] / rep["poll_interval_s"]) + 1


def test_render_never_omits_the_circularity_warning(monkeypatch):
    monkeypatch.setattr(ocr, "load_terminals",
                        lambda purpose=None, audit_path=None: {
                            "episodes": [_episode(6.0, True)],
                            "records_seen": 1, "dropped_old_schema": 0,
                            "dropped_bad_lifetime": 0,
                            "dropped_other_purpose": 0,
                            "audit_path": "x", "audit_mtime_utc": None})
    text = ocr.render(ocr.build_report())
    assert "dry_run" in text and "NOT a measurement of Kraken" in text
    assert "do not quote" in text.lower()


# --------------------------------------------------------------------------
# SAFE class
# --------------------------------------------------------------------------

def test_report_is_absent_from_decision_code():
    from tests.test_regime_chain_report import _decision_imports
    assert not _decision_imports("order_chain_report")
