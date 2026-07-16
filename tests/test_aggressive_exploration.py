"""tests/test_aggressive_exploration.py — conviction-scaled aggressive
exploration.

Normal exploration always min-sizes, so the model only sees fill outcomes on
timid marginal trades. When the model is reasonably confident AND the book is
clean (low manip, non-crisis regime), an occasional FULL-conviction ticket
(size on sizing_p, no shrink, no min floor) lets it learn from confident calls
at real size. Still dry-run only and bounded by every risk-stack veto. This
pins the eligibility predicate and the config wiring.
"""
from main import LiquidityBot


def _bot(**over):
    b = LiquidityBot.__new__(LiquidityBot)
    b._explore_aggr_enabled = over.get("enabled", True)
    b._explore_aggr_min_p = over.get("min_conviction", 0.55)
    b._explore_aggr_max_manip = over.get("max_manip", 0.6)
    b._explore_aggr_p = over.get("sizing_p", 0.72)
    b._explore_aggr_frac = over.get("frac", 0.15)
    return b


def test_eligible_when_confident_clean_and_calm():
    b = _bot()
    assert b._explore_aggressive_eligible(0.60, manip=0.1, regime_label="bull_quiet")


def test_not_eligible_when_model_is_unsure():
    b = _bot()
    assert not b._explore_aggressive_eligible(0.50, 0.1, "bull_quiet")  # < 0.55


def test_not_eligible_when_book_is_painted():
    b = _bot()
    assert not b._explore_aggressive_eligible(0.70, 0.8, "bull_quiet")  # manip>0.6


def test_not_eligible_in_a_crisis_regime():
    b = _bot()
    assert not b._explore_aggressive_eligible(0.70, 0.1, "crisis")


def test_disabled_is_never_eligible():
    b = _bot(enabled=False)
    assert not b._explore_aggressive_eligible(0.90, 0.0, "bull_quiet")


def test_boundaries_are_inclusive_on_conviction_and_manip():
    b = _bot()
    assert b._explore_aggressive_eligible(0.55, 0.6, "range")   # exactly at edges
    assert not b._explore_aggressive_eligible(0.5499, 0.6, "range")


def test_shipped_config_wires_the_aggressive_knobs():
    import json
    from pathlib import Path
    cfg = json.loads((Path(__file__).resolve().parents[1] / "config.json")
                     .read_text(encoding="utf-8"))
    ag = cfg["ml"]["exploration"]["aggressive"]
    assert ag["enabled"] is True
    assert 0.0 <= ag["frac"] <= 1.0
    assert 0.0 <= ag["min_conviction"] <= 1.0
    assert 0.0 <= ag["sizing_p"] <= 0.95
    assert 0.0 <= ag["max_manip"] <= 1.0
