"""OF-5's red is ADJUDICATED. These pins stop it from being SILENCED.

OPERATOR DECISION, 2026-09-11, verbatim: **"Keep pooling."** OF-5's sample
definition is settled — it pools execution eras, its FAIL is expected, and
28 of the 30 conviction trips at the adjudication predated cut #10.

Followed immediately by, verbatim: **"Put something in place to make sure if
it is regressive then it's not silenced."** That is what this file is.

THE HAZARD IT DEFENDS AGAINST. A documented red is a red nobody reads. Once
"OF-5 fails, that's the known legacy pooling" is in the record, it becomes a
ready-made dismissal for ANY OF-5 failure — including a real one. There are
two distinct ways the signal dies, and both are pinned here:

  1. THE GATE IS WEAKENED so the red goes away — the threshold moves, the
     conviction floor moves, the sample gets era-scoped into a DEFER, or the
     verdict is downgraded to an info line. CLAUDE.md forbids all of these in
     prose; prose does not fail a build.

  2. A GENUINE REGRESSION HIDES INSIDE THE EXPECTED ONE — the deployed
     configuration starts losing, and the signal arrives inside a gate already
     agreed to be red. The deployed-era sentinel exists for this, so the
     sentinel itself has to be pinned, including its INDETERMINATE paths: a
     sentinel that quietly measures nothing is worse than none, because it
     reads as an all-clear.

Every pin here is mutation-verified. None of them asserts a live number — the
corpus moves and a pinned number would decay into a false claim.
"""
from __future__ import annotations

import inspect
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

import scripts.overfit_check as oc                          # noqa: E402
from scripts.overfit_check import (                         # noqa: E402
    OF5_SENTINEL_MIN_N, dsr_deployed_segment, dsr_sample_span,
    dsr_sentinel_verdict)

ERA = "12-10d4d0c2"
OTHER = "9-16ec821e"


# ---------------------------------------------------------------------------
# 1. the gate may not be weakened
# ---------------------------------------------------------------------------

def test_the_conviction_floor_is_still_thirty():
    """CLAUDE.md: the n=30 conviction floor is a MEASUREMENT STANDARD, not a
    tunable. Raising it is the cheapest way to silence OF-5 — the gate would
    simply DEFER and the red would vanish with nothing looking broken."""
    src = inspect.getsource(oc.main)
    assert "len(conviction) >= 30" in src, (
        "the OF-5 conviction floor is no longer the literal 30. If it was "
        "RAISED the gate now defers and its red is silenced; if it was "
        "LOWERED that is the floor-moving CLAUDE.md forbids outright")


def _grade(dsr):
    """Run dsr_verdict and report what it actually RECORDED.

    Behavioural, not textual. The first version of this pin asserted
    `"0.90" in inspect.getsource(dsr_verdict)` and MUTATION PROVED IT
    VACUOUS: lowering the live bar to 0.10 left it green, because the
    docstring discusses "dsr >= 0.90" four times. That is precisely the
    "test pin satisfied by a comment" entry in the-method's recurrence
    register, committed by the pin written to prevent silencing."""
    report, passes, fails = oc.REPORT, oc.PASS_N, oc.FAIL_N
    oc.REPORT, oc.PASS_N, oc.FAIL_N = [], 0, 0
    try:
        oc.dsr_verdict("dsr: probe", dsr, "", True, 1.0, 7)
        return [kind for kind, _, _ in oc.REPORT]
    finally:
        oc.REPORT, oc.PASS_N, oc.FAIL_N = report, passes, fails


def test_the_dsr_bar_still_sits_at_ninety_percent():
    """Pins the PREDICATE by exercising it on both sides of the bar."""
    assert _grade(0.91) == ["PASS"], "a dsr above 0.90 no longer passes"
    assert _grade(0.89) == ["FAIL"], (
        "a dsr of 0.89 no longer FAILS - the bar was lowered, which is the "
        "floor-moving CLAUDE.md forbids and the cheapest way to turn OF-5 "
        "green without touching the strategy")
    assert _grade(0.50) == ["FAIL"] and _grade(0.006) == ["FAIL"]


def test_of5_still_GRADES_rather_than_merely_reporting():
    """The subtlest silencing: convert dsr_verdict's call into info(). The
    line would still print, the red would be gone, and the exit code would
    go green with no threshold visibly touched."""
    src = inspect.getsource(oc.main)
    assert "dsr_verdict(" in src, "OF-5 no longer routes through dsr_verdict"
    assert src.count("dsr_verdict(") >= 2, (
        "an OF-5 grading call site disappeared - the conviction branch and "
        "the exploration-off branch must both still grade")
    assert "dsr" in oc.EXPECTED_ARMED, (
        "the dsr family left EXPECTED_ARMED, so the arming ratchet would no "
        "longer notice OF-5 going dark")


def test_the_sample_is_still_POOLED_as_the_operator_decided():
    """The operator chose the graded red over the honest DEFER. Era-scoping
    OF-5 would flip its FAIL to a DEFER - the deployed era's WHOLLY-INSIDE
    conviction count is far under the 30 floor - and that is a red silenced
    by overturning a decision. If this test goes red, someone must go BACK TO
    THE OPERATOR, not adjust the test.

    (No count is written here. An earlier draft said "2 conviction trips";
    an adversarial pass refuted it - those 2 carry legs stamped across three
    eras, so cohort_eval classifies them MIXED and the wholly-inside count
    was ZERO. Re-derive from report_dsr_sentinel, which prints it per run.)"""
    src = inspect.getsource(oc.main)
    i = src.find("[OF-5]")
    assert i >= 0, "the OF-5 block moved; re-anchor this pin deliberately"
    block = src[i:i + 2500]
    assert 'row.get("source") == "live"' in block, (
        "OF-5's loader predicate changed")
    for forbidden in ("exec_era", "label_era"):
        assert forbidden not in block, (
            f"OF-5's GRADED sample now filters on {forbidden}. The operator "
            f"decided 2026-09-11 to KEEP POOLING; narrowing the sample "
            f"silences the adjudicated red by making the gate defer")


def test_split_dsr_samples_does_not_filter_by_era():
    """Second route to the same guarantee: the pure sample-selection function
    must stay era-blind, so era-scoping cannot be smuggled in below main()."""
    src = inspect.getsource(oc.split_dsr_samples)
    assert "exec_era" not in src and "label_era" not in src, (
        "era filtering appeared in OF-5's sample selector")


# ---------------------------------------------------------------------------
# 2. the sentinel must actually be able to fire
# ---------------------------------------------------------------------------

def _seg(n, mean, sd=1.0, era=ERA):
    """A segment dict shaped like dsr_deployed_segment's real return."""
    se = sd / (n ** 0.5)
    return {"available": True, "n": n, "era": era, "mean": mean, "sd": sd,
            "n_eff": float(n), "se": se, "ub95": mean + 1.96 * se,
            "total": mean * n}


def test_sentinel_FAILS_when_the_deployed_era_has_demonstrated_a_loss():
    armed, ok, detail = dsr_sentinel_verdict(_seg(40, -1.0, sd=0.5))
    assert armed is True and ok is False
    assert "REGRESSION" in detail
    assert "not the documented" in detail.lower(), (
        "a firing sentinel must say explicitly that it is NOT the known "
        "pooling red, or it will be dismissed as exactly that")


def test_sentinel_PASSES_on_ordinary_statistical_silence():
    """It must not cry wolf. A small negative mean that the CI cannot
    separate from zero is OF-5's territory, not a regression."""
    armed, ok, _ = dsr_sentinel_verdict(_seg(40, -0.05, sd=1.5))
    assert armed is True and ok is True


def test_sentinel_DEFERS_below_its_own_floor_instead_of_passing():
    """A quiet PASS on 3 trips would be a false all-clear - the single worst
    outcome for an anti-silencing instrument."""
    armed, ok, detail = dsr_sentinel_verdict(_seg(3, -5.0))
    assert armed is False and ok is None
    assert "DEFERRED" in detail
    assert "NOTHING about it" in detail


def test_sentinel_reports_INDETERMINATE_not_clean_when_it_cannot_measure():
    """An unreadable ledger must never read as an all-clear."""
    armed, ok, detail = dsr_sentinel_verdict(
        {"available": False, "reason": "fill ledger unreadable (OSError)"})
    assert armed is False and ok is None
    assert "INDETERMINATE" in detail and "INVISIBLE" in detail


def test_sentinel_floor_is_not_silently_enormous():
    assert 1 <= OF5_SENTINEL_MIN_N <= 30, (
        "a sentinel floor above OF-5's own conviction floor would mean the "
        "deployed era is never separately checked")


# ---------------------------------------------------------------------------
# 3. the segment join must be right, or the sentinel measures the wrong trips
# ---------------------------------------------------------------------------

def _write_fills(tmp_path, rows):
    p = tmp_path / "fills.csv"
    p.write_text("ts,position_id,exec_era\n" + "".join(
        f"{t},{pid},{era}\n" for t, pid, era in rows), encoding="utf-8")
    return p


def _row(pid, pnl, ts, probe="0"):
    return {"position_id": pid, "net_pnl_usd": str(pnl), "probe": probe,
            "ts": str(ts)}


def test_only_trips_WHOLLY_INSIDE_the_current_era_are_counted(tmp_path):
    """cohort_eval's standard. A straddler is half of each era and belongs to
    neither; counting it would import legacy drag into the sentinel and blunt
    the alarm."""
    fills = _write_fills(tmp_path, [
        (100.0, "p_in", ERA),
        (100.0, "p_straddle", OTHER), (200.0, "p_straddle", ERA),
        (100.0, "p_old", OTHER),
    ])
    rows = [_row("p_in", -1.0, 300.0), _row("p_straddle", -99.0, 400.0),
            _row("p_old", -99.0, 500.0)]
    seg = dsr_deployed_segment(rows, fills, ERA)
    assert seg["n"] == 1, f"straddler or legacy trip leaked in: {seg}"
    assert seg["total"] == -1.0


def test_probe_trips_never_enter_the_sentinel(tmp_path):
    """Probes bypass the profit-EV gate by design; including them would make
    the deployed era look worse than it is and cry wolf."""
    fills = _write_fills(tmp_path, [(100.0, "a", ERA), (100.0, "b", ERA)])
    rows = [_row("a", -1.0, 300.0), _row("b", -50.0, 300.0, probe="1")]
    seg = dsr_deployed_segment(rows, fills, ERA)
    assert seg["n"] == 1 and seg["total"] == -1.0


def test_a_missing_ledger_is_unavailable_not_empty(tmp_path):
    seg = dsr_deployed_segment([_row("a", -1.0, 1.0)],
                               tmp_path / "nope.csv", ERA)
    assert seg["available"] is False and "reason" in seg


def test_an_unreadable_era_is_unavailable_not_empty(tmp_path):
    """If core.fill_ledger.EXEC_ERA cannot be read, every stamp comparison
    would fail and the segment would come back n=0 - which reads as 'no
    trips yet', a false all-clear. It must say it is blind instead."""
    fills = _write_fills(tmp_path, [(100.0, "a", ERA)])
    seg = dsr_deployed_segment([_row("a", -1.0, 300.0)], fills, "")
    assert seg["available"] is False
    assert "exec_era" in seg["reason"]


def test_effective_n_never_exceeds_nominal_n(tmp_path):
    """n_eff > n would UNDERSTATE the SE and make the alarm fire EARLY.

    The clamp is DEFENSIVE - the real estimator caps uniqueness at 1 per trip
    so it cannot exceed n on its own. That made the first version of this test
    vacuous: mutation removed the clamp and every assertion stayed green,
    because the fixture could never produce the value the clamp exists to
    catch. So the estimator is stubbed to return an absurd figure, which is
    the only way to exercise a defence against a dependency misbehaving."""
    import scripts.cohort_eval as ce
    fills = _write_fills(tmp_path, [(float(i), f"p{i}", ERA)
                                    for i in range(1, 21)])
    rows = [_row(f"p{i}", -0.5, 1000.0 + i) for i in range(1, 21)]

    real = ce.cohort_effective_n
    ce.cohort_effective_n = lambda spans: {"available": True,
                                           "effective_n": 10_000.0,
                                           "n": len(spans),
                                           "mean_uniqueness": 1.0}
    try:
        seg = dsr_deployed_segment(rows, fills, ERA)
    finally:
        ce.cohort_effective_n = real

    assert seg["n"] == 20
    assert 0 < seg["n_eff"] <= seg["n"], (
        "a runaway effective_n was accepted; the SE would be understated by "
        "sqrt(n_eff/n) and the regression alarm would cry wolf")

    seg_real = dsr_deployed_segment(rows, fills, ERA)
    assert 0 < seg_real["n_eff"] <= seg_real["n"]


def test_the_live_era_resolves_from_the_module_that_stamps_it():
    """Not hardcoded here and not hardcoded there: it must come from
    core.fill_ledger, the writer of the stamps being matched."""
    from core.fill_ledger import EXEC_ERA
    assert oc._exec_era_now() == EXEC_ERA
    assert EXEC_ERA, "the stamping module has no current era"


# ---------------------------------------------------------------------------
# 4. the disclosure that makes the red readable must stay
# ---------------------------------------------------------------------------

def test_the_corpus_disclosure_is_still_wired_into_the_gate():
    """Deleting it would not fail anything - the gate would still grade, and
    the red would go back to being unreadable."""
    src = inspect.getsource(oc.main)
    assert "dsr_disclosure(" in src
    assert "report_dsr_sentinel(" in src, (
        "the deployed-era sentinel call site is gone; a regression in the "
        "live configuration would again be invisible inside OF-5's red")


def test_the_span_still_reports_the_pooling_it_cannot_fix():
    span = dsr_sample_span(
        [{"probe": "0", "ts": "1700000000.0", "net_pnl_usd": "1"},
         {"probe": "0", "ts": "1700864000.0", "net_pnl_usd": "1"}])
    assert span["available"] and abs(span["days"] - 10.0) < 1e-6
