"""Planted-defect tests for the champion skill report.

Backpack rule 2: a check that READS correct is worth nothing until it is
shown to FAIL on a planted defect. Each test plants a predictor whose true
skill is known by construction and asserts the report recovers its sign.
"""
import numpy as np

from scripts.champion_skill_report import (MIN_WINDOW_ROWS, capacity_ladder,
                                           skill_score, window_report)


def _labels(n=400, base=0.4, seed=7):
    rng = np.random.default_rng(seed)
    return (rng.random(n) < base).astype(float)


def test_constant_predictor_scores_zero_skill():
    """The oracle constant IS the null: it must score exactly 0, not >0."""
    y = _labels()
    p = np.full(y.size, y.mean())
    r = window_report(p, y)
    assert r["verdict"] == "NO SKILL"
    assert abs(r["skill_score"]) < 1e-9
    assert abs(r["excess_over_oracle"]) < 1e-9


def test_informative_predictor_scores_positive_skill():
    """A predictor that leaks the label must read as skill (guard against a
    detector that says NO SKILL for everything)."""
    y = _labels()
    p = np.where(y > 0.5, 0.9, 0.1)
    r = window_report(p, y)
    assert r["verdict"] == "skill"
    assert r["skill_score"] > 0.5
    assert r["excess_over_oracle"] < 0


def test_anti_skilled_predictor_scores_negative():
    """Inverted predictions must go NEGATIVE - the planted defect this
    report exists to catch (a model worse than a constant)."""
    y = _labels()
    p = np.where(y > 0.5, 0.1, 0.9)
    r = window_report(p, y)
    assert r["verdict"] == "NO SKILL"
    assert r["skill_score"] < 0


def test_near_constant_predictor_is_flagged_by_spread():
    """PI-2's shape: a model whose calibrated output cannot span the entry
    bar. The spread fields must expose it (they are why the ceiling was
    found), and skill must not be credited for tiny wiggle."""
    y = _labels()
    rng = np.random.default_rng(3)
    p = np.clip(y.mean() + rng.normal(0, 0.01, y.size), 1e-6, 1 - 1e-6)
    r = window_report(p, y)
    assert r["p_sd"] < 0.05
    assert r["p_max"] - r["p_min"] < 0.25
    assert r["skill_score"] <= 0


def test_degenerate_window_is_undefined_not_infinite():
    """All-one-class window: oracle brier is 0. Must report UNDEFINED
    rather than divide by zero or claim perfect skill."""
    y = np.ones(100)
    r = window_report(np.full(100, 0.9), y)
    assert r["skill_score"] is None
    assert "UNDEFINED" in r["verdict"]
    assert skill_score(0.01, 1.0) is None
    assert skill_score(0.01, 0.0) is None


def test_short_window_is_flagged_not_silently_scored():
    """A skill number on 5 rows is not evidence - it must carry the flag."""
    y = _labels(n=MIN_WINDOW_ROWS - 1, seed=11)
    r = window_report(np.full(y.size, 0.5), y)
    assert r["insufficient_rows"] is True
    r_big = window_report(np.full(400, 0.5), _labels(400))
    assert r_big["insufficient_rows"] is False


def test_length_mismatch_errors_rather_than_broadcasting():
    """Saboteur: mismatched arrays must not silently numpy-broadcast into a
    fabricated score."""
    r = window_report(np.full(10, 0.5), _labels(400))
    assert "error" in r
    assert r["skill_score"] is None or "error" in r


def test_ladder_ranks_by_skill_and_names_the_no_skill_case():
    """Planted ladder: one leaky rung, one constant, one inverted. The
    ranking must put the leaky rung first and mark the others NO SKILL."""
    y = _labels()
    rungs = {
        "constant": np.full(y.size, y.mean()),
        "leaky": np.where(y > 0.5, 0.9, 0.1),
        "inverted": np.where(y > 0.5, 0.1, 0.9),
    }
    out = capacity_ladder(rungs, y)
    assert [r["rung"] for r in out][0] == "leaky"
    assert out[0]["verdict"] == "skill"
    assert out[-1]["rung"] == "inverted"
    assert all(r["verdict"] == "NO SKILL"
               for r in out if r["rung"] != "leaky")


def test_ladder_reports_unfit_rung_distinctly_from_zero_skill():
    """'The family would not fit' and 'the family has no skill' are
    DIFFERENT observations - a rung that failed must never read as 0."""
    y = _labels()
    out = capacity_ladder({"broken": None,
                           "constant": np.full(y.size, y.mean())}, y)
    broken = [r for r in out if r["rung"] == "broken"][0]
    assert broken["skill_score"] is None
    assert "UNDEFINED" in broken["verdict"]
    assert broken["error"] == "could not fit"
    assert out[0]["rung"] == "constant"


def test_ladder_all_negative_is_representable():
    """The measured production case: every rung at or below zero. The
    ladder must still rank and must not crash on an all-negative field."""
    y = _labels()
    out = capacity_ladder(
        {f"r{i}": np.where(y > 0.5, 0.5 - 0.1 * i, 0.5 + 0.1 * i)
         for i in range(1, 4)}, y)
    assert all(r["skill_score"] < 0 for r in out)
    assert out[0]["skill_score"] >= out[-1]["skill_score"]


def test_train_constant_null_reported_when_supplied():
    y = _labels()
    r = window_report(np.full(y.size, 0.5), y, train_base=0.6)
    assert "train_constant_brier" in r
    assert r["train_constant_brier"] > 0
