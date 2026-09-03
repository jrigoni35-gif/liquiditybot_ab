"""Planted-defect tests for the champion skill report.

Backpack rule 2: a check that READS correct is worth nothing until it is
shown to FAIL on a planted defect. Each test plants a predictor whose true
skill is known by construction and asserts the report recovers its sign.
"""
import json
import os

import numpy as np

from scripts.champion_skill_report import (MIN_WINDOW_ROWS, capacity_ladder,
                                          skill_ci,
                                           skill_score, window_report)


def _labels(n=400, base=0.4, seed=7):
    rng = np.random.default_rng(seed)
    return (rng.random(n) < base).astype(float)


def test_constant_predictor_scores_zero_skill():
    """The oracle constant IS the null: it must score exactly 0, not >0."""
    y = _labels()
    p = np.full(y.size, y.mean())
    r = window_report(p, y)
    assert "SKILL" in r["verdict"] and "NO SKILL" not in "SKILL (CI"
    assert r["skill_score"] <= 0.0        # semantics, not vocabulary
    assert abs(r["skill_score"]) < 1e-9
    assert abs(r["excess_over_oracle"]) < 1e-9


def test_informative_predictor_scores_positive_skill():
    """A predictor that leaks the label must read as skill (guard against a
    detector that says NO SKILL for everything)."""
    y = _labels()
    p = np.where(y > 0.5, 0.9, 0.1)
    r = window_report(p, y)
    assert r["verdict"].startswith("SKILL")
    assert r["skill_score"] > 0.5
    assert r["excess_over_oracle"] < 0


def test_anti_skilled_predictor_scores_negative():
    """Inverted predictions must go NEGATIVE - the planted defect this
    report exists to catch (a model worse than a constant)."""
    y = _labels()
    p = np.where(y > 0.5, 0.1, 0.9)
    r = window_report(p, y)
    assert r["skill_score"] <= 0.0        # semantics, not vocabulary
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
    assert out[0]["verdict"].startswith("SKILL")
    assert out[-1]["rung"] == "inverted"
    # semantics, not vocabulary: every non-leaky rung fails to beat a constant
    assert all(r["skill_score"] is not None and r["skill_score"] <= 0.0
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


# --- corpus calendar span (2026-08-31): the MinBTL denominator ------------
# Re-derived from the loaded rows every run, never quoted from a doc.

def test_corpus_span_planted_three_rows_to_two_dp():
    """Three planted signal times spanning exactly 50.25 days, unsorted:
    the span must read the extremes, not first/last-by-position."""
    from scripts.champion_skill_report import corpus_span
    t0 = 1_783_946_147.0                          # 2026-07-13T12:35:47Z
    r = corpus_span(np.array([t0 + 3 * 86400.0, t0, t0 + 50.25 * 86400.0]))
    assert r["corpus_rows"] == 3 and r["sig_missing"] == 0
    assert r["corpus_first_ts"] == "2026-07-13T12:35:47Z"
    assert r["corpus_last_ts"] == "2026-09-01T18:35:47Z"
    assert r["corpus_span_days"] == 50.25


def test_corpus_span_excludes_nonfinite_and_counts_them():
    from scripts.champion_skill_report import corpus_span
    t0 = 1_783_946_147.0
    r = corpus_span([t0, np.nan, 0.0, t0 + 86400.0 * 2.5])
    assert r["corpus_rows"] == 4 and r["sig_missing"] == 2
    assert r["corpus_span_days"] == 2.5
    empty = corpus_span([])
    assert empty["corpus_span_days"] is None
    assert empty["corpus_first_ts"] is None and empty["corpus_rows"] == 0


def test_main_prints_span_from_loaded_rows_and_json_carries_it(
        monkeypatch, tmp_path, capsys):
    """The span on the report must come from what _load_live() returned
    (planted here), and reach both the text line and the --json payload -
    with and without a deployed champion."""
    import scripts.champion_skill_report as csr
    t0 = 1_783_946_147.0
    sig = np.array([t0, t0 + 86400.0, t0 + 50.25 * 86400.0])
    y = np.array([1.0, 0.0, 1.0])
    X = np.zeros((3, 2))
    missing = tmp_path / "no_meta.json"
    monkeypatch.setattr(csr, "_load_live", lambda: {
        "X": X, "y": y, "sig": sig, "w": np.ones(3), "meta_path": missing})
    assert csr.main([]) == 0
    out = capsys.readouterr().out
    assert ("corpus span (signal_ts of the 3 rows loaded): "
            "2026-07-13T12:35:47Z -> 2026-09-01T18:35:47Z = 50.25 d") in out
    assert csr.main(["--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["corpus_first_ts"] == "2026-07-13T12:35:47Z"
    assert payload["corpus_last_ts"] == "2026-09-01T18:35:47Z"
    assert payload["corpus_span_days"] == 50.25
    # with a (minimal) champion present the keys ride the full report
    from ml.models import LogisticModel
    m = LogisticModel()
    m.fit(np.vstack([X, X]), np.concatenate([y, 1 - y]))
    meta = m.to_dict()
    meta["rows"] = 2
    meta_path = tmp_path / "meta.json"
    meta_path.write_text(json.dumps(meta), encoding="utf-8")
    monkeypatch.setattr(csr, "_load_live", lambda: {
        "X": X, "y": y, "sig": sig, "w": np.ones(3), "meta_path": meta_path})
    assert csr.main(["--json"]) == 0
    full = json.loads(capsys.readouterr().out)
    assert full["corpus_span_days"] == 50.25 and "windows" in full
    assert csr.main([]) == 0
    assert "= 50.25 d" in capsys.readouterr().out


def test_corpus_span_survives_millisecond_epoch():
    """A ms-epoch cell (the unit-mixing class) must DEGRADE, never crash the
    report over one bad value.

    PLATFORM-SPLIT, not skipped - the 2026-08-22 "wrong OS, not wrong code"
    precedent. The invariants that carry the defect (no raise, first stamp
    intact, span arithmetic still reported) are asserted EVERYWHERE; only
    the far-future stamp branches, because Windows gmtime raises OSError on
    a year-58501 epoch while POSIX gmtime formats it happily. Asserting the
    Windows outcome unconditionally made this red on every Linux workspace,
    which is the host-dependent green this suite is supposed to not have.
    """
    from scripts.champion_skill_report import corpus_span
    t0 = 1_783_946_147.0
    r = corpus_span([t0, t0 * 1000.0])
    assert r["corpus_first_ts"] == "2026-07-13T12:35:47Z"
    assert r["corpus_span_days"] is not None
    if os.name == "nt":
        assert r["corpus_last_ts"] is None       # unrepresentable, said so
    else:
        assert r["corpus_last_ts"] == "58501-01-01T20:23:20Z"


# --- skill interval + resolution floor (2026-09-02 focused-fix) -------------
# WHY: the verdict used to be `skill <= 0 -> "NO SKILL"`, a bare sign test on
# a point estimate. It could not separate "no skill" from "a window too weak
# to see skill" - the Harvey & Liu Type-II shape. These pin the repair.

def test_skill_ci_uses_day_blocks_when_timestamps_supplied():
    rng = np.random.default_rng(3)
    n = 1200
    ts = np.repeat(np.arange(30), 40) * 86400.0
    y = (rng.random(n) < 0.4).astype(float)
    ci = skill_ci(np.full(n, 0.4), y, ts)
    assert ci["available"] and ci["basis"] == "day-block"
    assert ci["blocks"] == 30            # blocks are DAYS, not rows
    assert ci["mde_2se"] > 0.0


def test_skill_ci_without_timestamps_declares_itself_optimistic():
    """A row resample is narrower than a day resample on clustered rows. The
    caller must be TOLD which basis produced the interval."""
    rng = np.random.default_rng(4)
    n = 1200
    ts = np.repeat(np.arange(30), 40) * 86400.0
    # rows correlated within a day: day effect shifts the label rate
    day_shift = np.repeat(rng.normal(0, 0.25, 30), 40)
    y = (rng.random(n) < np.clip(0.4 + day_shift, 0.05, 0.95)).astype(float)
    p = np.full(n, 0.4)
    row_ci = skill_ci(p, y, None)
    day_ci = skill_ci(p, y, ts)
    assert "OPTIMISTIC" in row_ci["basis"]
    assert day_ci["mde_2se"] > row_ci["mde_2se"]


def test_verdict_reports_resolution_not_a_bare_sign_test():
    """An effect SMALLER than the window can resolve must not read as a finding.

    NOTE the premise this test was first written with was WRONG and the code
    was right: a constant predictor set to the window's own mean scores
    RELIABLY negative, not zero, because the oracle is refit per resample
    while the predictor is fixed - a measured -1/n bias (see the module
    docstring). So the noise-floor case is a genuinely weak signal on few
    blocks, not a perfect constant."""
    rng = np.random.default_rng(5)
    n, ndays = 600, 10
    ts = np.repeat(np.arange(ndays), n // ndays) * 86400.0
    y = (rng.random(n) < 0.4).astype(float)
    # a WHISPER of real signal - far below what 10 day-blocks can resolve
    p = np.clip(0.4 + 0.004 * (y - 0.4), 0.01, 0.99)
    r = window_report(p, y, ts=ts)
    assert r["skill_ci"]["available"]
    assert not r["skill_ci"]["excludes_zero"], r["skill_ci"]
    assert "NO SKILL DETECTED" in r["verdict"]
    assert "resolves" in r["verdict"]      # the floor travels with the verdict
    # the CI spanning zero is the load-bearing assertion; the point estimate
    # may sit just outside a symmetric 2-SE floor because the interval is a
    # PERCENTILE, not a symmetric band. Both are reported; neither is a finding.
    assert r["skill_ci"]["mde_2se"] > 0.0


def test_real_skill_is_still_detected_as_skill():
    """The floor must not swallow a real effect - a null that never fires is
    as useless as a verdict that always fires."""
    rng = np.random.default_rng(6)
    n = 1200
    ts = np.repeat(np.arange(30), 40) * 86400.0
    y = (rng.random(n) < 0.4).astype(float)
    p = np.clip(0.4 + 0.35 * (y - 0.4) / 0.4, 0.01, 0.99)
    r = window_report(p, y, ts=ts)
    assert r["skill_score"] > 0.5
    assert r["skill_ci"]["excludes_zero"]
    assert r["verdict"].startswith("SKILL")


def test_degenerate_window_reports_unavailable_interval_not_a_verdict():
    y = np.ones(200)                       # all one class: no denominator
    r = window_report(np.full(200, 0.9), y, ts=np.arange(200) * 86400.0)
    assert r["skill_score"] is None
    assert r["verdict"].startswith("UNDEFINED")


def test_mde_is_two_standard_errors_not_one():
    """The resolution floor is 2 SE. Halving it silently widens every verdict
    (a skill inside the noise would start reading as a finding) - the exact
    gate-widening CLAUDE.md forbids, so it gets its own pin."""
    rng = np.random.default_rng(7)
    n = 900
    ts = np.repeat(np.arange(30), 30) * 86400.0
    y = (rng.random(n) < 0.45).astype(float)
    ci = skill_ci(np.full(n, 0.45), y, ts)
    assert ci["available"]
    # both sides are rounded to 6dp independently, so compare with a
    # tolerance that is still far tighter than the factor-2 mutation
    assert abs(ci["mde_2se"] - 2.0 * ci["bootstrap_sd"]) < 1e-5
    assert ci["mde_2se"] > 1.5 * ci["bootstrap_sd"]   # kills the 1-SE mutant


def test_report_passes_timestamps_so_the_interval_is_day_blocked(
        monkeypatch, tmp_path, capsys):
    """THE WIRING IS THE POINT. window_report defaults ts=None, so a caller
    that forgets to pass it gets a row resample and a too-narrow interval
    with no error and no warning. This pins the real report's call site:
    a mutation that drops ts=s[m] must go red here."""
    import scripts.champion_skill_report as csr
    from ml.models import LogisticModel
    rng = np.random.default_rng(8)
    ndays, per_day = 12, 60
    n = ndays * per_day
    sig = (np.repeat(np.arange(ndays), per_day) * 86400.0
           + 1_783_946_147.0)
    y = (rng.random(n) < 0.45).astype(float)
    X = rng.normal(size=(n, 2))
    m = LogisticModel()
    m.fit(X, y)
    meta = m.to_dict()
    meta["rows"] = n // 2                      # a real train/fresh split
    meta_path = tmp_path / "meta.json"
    meta_path.write_text(json.dumps(meta), encoding="utf-8")
    monkeypatch.setattr(csr, "_load_live", lambda: {
        "X": X, "y": y, "sig": sig, "w": np.ones(n), "meta_path": meta_path})
    assert csr.main(["--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    windows = payload["windows"]
    assert windows, "no windows scored"
    for name, w in windows.items():
        ci = w.get("skill_ci") or {}
        assert ci.get("available"), f"{name}: no interval"
        assert ci["basis"] == "day-block", (
            f"{name}: interval is {ci['basis']} - the call site stopped "
            f"passing timestamps, so the report is optimistic and silent")
        assert 1 < ci["blocks"] <= ndays
