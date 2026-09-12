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
    floors = _conviction_floors()
    assert floors == [30], (
        f"the OF-5 conviction floor(s) read {floors}, not [30]. RAISED -> the "
        f"gate defers and its red is silenced; LOWERED -> that is the "
        f"floor-moving CLAUDE.md forbids outright")


def _conviction_floors():
    """Every literal N in an `len(conviction) >= N` test inside main(), read
    from the AST.

    NOT a source-substring check. The substring form was satisfied by a
    COMMENT in this very file: a note added 2026-09-12 quoting
    `len(conviction) >= 30` kept the pin green while the real predicate was
    mutated to 60. That is the fourth instance of the-method's "test pin
    satisfied by a comment" recurrence in one session - the third was this
    file's own dsr-bar pin. The AST carries no comments and no docstring can
    forge a Compare node, so this form cannot repeat it."""
    import ast
    import textwrap
    tree = ast.parse(textwrap.dedent(inspect.getsource(oc.main)))
    out = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Compare) or len(node.ops) != 1:
            continue
        if not isinstance(node.ops[0], ast.GtE):
            continue
        left = node.left
        if not (isinstance(left, ast.Call)
                and getattr(left.func, "id", None) == "len"
                and left.args
                and getattr(left.args[0], "id", None) == "conviction"):
            continue
        rhs = node.comparators[0]
        if isinstance(rhs, ast.Constant) and isinstance(rhs.value, int):
            out.append(rhs.value)
    return sorted(out)


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
    """A segment BUILT BY THE REAL CODE, never hand-assembled.

    The first version of this helper hand-rolled the dict INCLUDING its own
    copy of `ub95 = mean + 1.96*se`. Mutation proved that vacuous: changing
    the shipped z to 0.0 or 19.6 left all 42 pins green, because every
    assertion read the fixture's arithmetic rather than the module's
    (red-team OBJ-12). Synthesising rows and running dsr_deployed_segment is
    the only way these pins can see the shipped constant.

    Rows are laid out strictly sequentially (no overlap) so n_eff == n and
    the dispersion under test is the one asked for."""
    import csv as _csv
    import tempfile
    vals = _spread(n, mean, sd)
    d = Path(tempfile.mkdtemp())
    fills_p = d / "fills.csv"
    with open(fills_p, "w", encoding="utf-8", newline="") as fh:
        w = _csv.writer(fh)
        w.writerow(["ts", "position_id", "exec_era"])
        for i in range(n):
            w.writerow([1_700_000_000.0 + i * 7200.0, f"p{i}", era])
    rows = [{"position_id": f"p{i}", "net_pnl_usd": str(vals[i]),
             "probe": "0", "ts": str(1_700_000_000.0 + i * 7200.0 + 600.0)}
            for i in range(n)]
    return dsr_deployed_segment(rows, fills_p, ERA)


def _spread(n, mean, sd):
    """n values with EXACTLY the requested mean and sample sd (ddof=1)."""
    if n < 2 or sd == 0:
        return [mean] * n
    base = [(-1.0) ** i for i in range(n)]          # alternating +-1
    m = sum(base) / n
    centred = [b - m for b in base]
    cur = (sum(c * c for c in centred) / (n - 1)) ** 0.5
    k = sd / cur if cur else 0.0
    return [round(mean + c * k, 6) for c in centred]


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


# ---------------------------------------------------------------------------
# 5. THE SILENCING CHANNELS THE RED-TEAM PANEL FOUND (2026-09-12)
#
# Every pin below exists because the FIRST cut of this guard could be silenced
# and none of the original 11 pins could see it. Each is an injection.
# ---------------------------------------------------------------------------

def test_one_millisecond_timestamp_cannot_silence_the_alarm(tmp_path):
    """OBJ-8, CONCEDED. n was built from `pnl` and n_eff from `spans`, and a
    trip could enter one without the other. A single close-ts written in
    milliseconds creates a ~54,000-year span that overlaps every other trip,
    halving their uniqueness: n stayed 16, n_eff fell 16.000 -> 8.500, SE
    inflated x1.372 and ub95 moved -0.2151 -> -0.0173 on an UNCHANGED book.
    Any book whose true ub95 lay in [-0.198, 0) was silenced by one row."""
    n = 16
    fills = _write_fills(tmp_path, [(1_700_000_000.0 + i * 7200.0, f"p{i}",
                                     ERA) for i in range(n)])
    vals = _spread(n, -0.95, 1.5)
    good = [_row(f"p{i}", vals[i], 1_700_000_000.0 + i * 7200.0 + 600.0)
            for i in range(n)]
    base = dsr_deployed_segment(good, fills, ERA)

    poisoned = [dict(r) for r in good]
    poisoned[0]["ts"] = str(float(poisoned[0]["ts"]) * 1000.0)   # ms stamp
    after = dsr_deployed_segment(poisoned, fills, ERA)

    assert after["n_eff"] <= after["n"], "n_eff escaped its own population"
    assert abs(after["n_eff"] - after["n"]) < 1e-6, (
        f"n={after['n']} but n_eff={after['n_eff']:.3f}: the deflation is "
        f"computed over a DIFFERENT set of trips than the mean, which is "
        f"the OBJ-8 silencing channel")
    assert after["ub95"] <= base["ub95"] + 1e-9, (
        "a malformed timestamp moved ub95 TOWARD zero - it made the alarm "
        "quieter on an unchanged book")
    assert after["excluded"] >= 1 and after["dropped"]["bad_close"] >= 1, (
        "the malformed row was absorbed silently instead of being counted")


def test_an_unstamped_leg_makes_a_trip_IMPURE(tmp_path):
    """OBJ-1 + OBJ-10, CONCEDED. `cohort_eval.py:557` states the rule this
    guard claimed to reuse: PURITY IS OVER ALL LEGS, NOT OVER STAMPED LEGS.
    Testing `stamps.get(pid) == {era}` only asks whether every leg that
    CARRIED a stamp agreed - so a trip with a blank or absent exec_era leg
    counted as wholly-inside. No original fixture row carried one, so no pin
    could fail on the only case where the two rules diverge."""
    p = tmp_path / "fills.csv"
    with open(p, "w", encoding="utf-8") as fh:
        fh.write("ts,position_id,exec_era\n")
        fh.write(f"100.0,clean,{ERA}\n")
        fh.write(f"100.0,blank_leg,{ERA}\n")
        fh.write("200.0,blank_leg,\n")            # BLANK exec_era
        fh.write(f"100.0,absent_leg,{ERA}\n")
        fh.write("300.0,absent_leg\n")            # SHORT row: field ABSENT
    rows = [_row("clean", +1.0, 1_700_000_000.0),
            _row("blank_leg", -50.0, 1_700_000_100.0),
            _row("absent_leg", -50.0, 1_700_000_200.0)]
    seg = dsr_deployed_segment(rows, p, ERA)
    assert seg["n"] == 1, (
        f"n={seg['n']}: a trip with an unstamped leg was counted as wholly "
        f"inside the era, which overstates the accruing count the moment a "
        f"stale-binary leg lands in the current era")
    assert seg["total"] == 1.0


def test_a_blank_position_id_cannot_merge_trips(tmp_path):
    """OBJ-13, CONCEDED. An empty string is a legal dict key on BOTH sides of
    the join, so every unattributed fill merged into one pseudo-trip that
    then matched every blank-pid history row. Injection returned n=4
    total=-26.00 where the correct answer was n=1 +1.00.
    core/fill_ledger.py writes `order.position_id or ""`, so the blank is
    reachable from the shipped writer, and ml/history.py:1786 already guards
    this exact join on this exact file."""
    p = _write_fills(tmp_path, [(100.0, "real", ERA), (100.0, "", ERA)])
    rows = [_row("real", +1.0, 1_700_000_000.0)] + [
        _row("", -9.0, 1_700_000_100.0 + i) for i in range(3)]
    seg = dsr_deployed_segment(rows, p, ERA)
    assert seg["n"] == 1 and seg["total"] == 1.0, (
        f"blank-pid rows leaked in: n={seg['n']} total={seg['total']}")
    assert seg["dropped"]["blank_pid"] == 3


def test_the_shipped_z_is_one_sided_and_reaches_the_verdict():
    """OBJ-12, CONCEDED. `ok = ub95 >= 0` is a single-tailed question, so a
    two-tailed 1.96 ran it at alpha=0.025 - half the advertised sensitivity,
    in the NOT-FIRING direction. Worse, the old fixture recomputed ub95
    itself, so mutating the shipped z to 0.0 or 19.6 left all 42 pins green.
    This pin reads the constant THROUGH the module."""
    from scripts.overfit_check import SENTINEL_Z
    assert 1.0 < SENTINEL_Z < 2.0
    seg = _seg(20, -0.30, sd=1.0)
    assert abs(seg["z"] - SENTINEL_Z) < 1e-12
    expected = seg["mean"] + SENTINEL_Z * seg["se"]
    assert abs(seg["ub95"] - expected) < 1e-9, (
        "ub95 is not computed from the shipped z - a mutation of the "
        "constant would not be visible to any assertion here")
    assert abs(SENTINEL_Z - 1.645) < 1e-9, (
        "the one-sided 95% z moved; ml/monitor.py:79 wilson_ucb uses 1.645 "
        "for this exact shape and the printed line names alpha=0.05")


def test_the_passing_branch_never_exculpates_the_pooled_red():
    """OBJ-11, CONCEDED. The old passing branch asserted OF-5's pooled FAIL
    was legacy drag - an affirmative all-clear from a test with single-digit
    power at its own arming floor. A guard that says all clear at 6-10%
    power is a silencing device wearing a green badge."""
    armed, ok, detail = dsr_sentinel_verdict(_seg(12, -0.05, sd=1.5))
    assert armed is True and ok is True
    assert "legacy drag" not in detail, (
        "the passing branch still exculpates the pooled FAIL")
    assert "MDE=" in detail, (
        "a passing sentinel must print the loss it could actually have "
        "resolved - a green is only as big as its power")
    assert "NOT an all-clear" in detail


def test_the_MDE_is_worse_than_the_registered_H0_bleed_at_the_floor():
    """The number that justifies the previous pin, computed not asserted: at
    the arming floor the detectable loss is several times the registered H0
    bleed of -$0.27/trip, and that must be printed."""
    seg = _seg(OF5_SENTINEL_MIN_N, -0.05, sd=1.5)
    _, ok, detail = dsr_sentinel_verdict(seg)
    mde = -1.645 * seg["sd"] / (seg["n_eff"] ** 0.5)
    assert ok is True
    assert abs(mde) > 0.27, (
        "if the MDE ever becomes finer than the H0 bleed, the exculpatory "
        "wording may be revisited - until then it may not")
    assert f"{mde:+.3f}" in detail


def test_exclusions_are_counted_and_surfaced_not_dropped(tmp_path):
    """An exclusion that removes losers is itself a silencing channel."""
    p = _write_fills(tmp_path, [(100.0, "a", ERA), (100.0, "b", ERA)])
    rows = [_row("a", -1.0, 1_700_000_000.0),
            _row("b", -99.0, "nan")]           # unusable close
    seg = dsr_deployed_segment(rows, p, ERA)
    assert seg["n"] == 1 and seg["excluded"] == 1
    assert abs(seg["dropped_pnl"] + 99.0) < 1e-9
    _, _, detail = dsr_sentinel_verdict(seg)
    assert "EXCLUDED" in detail and "-99.00" in detail, (
        "a $99 loser left the statistic without appearing in the message")


def test_the_sentinel_is_called_OUTSIDE_the_conviction_branch():
    """OBJ-2, CONCEDED. The call sat inside `if len(conviction) >= 30`, so in
    the file's own designed post-exploration steady state (exploration off,
    conviction < 30, mixed >= 30) the pooled verdict armed the dsr family
    while the sentinel emitted nothing and went_dark stayed empty. The guard
    was silent in exactly the branch the system is heading for."""
    lines = inspect.getsource(oc.main).splitlines()
    calls = [ln for ln in lines if "report_dsr_sentinel(" in ln]
    assert calls, "the sentinel call site is gone"
    for ln in calls:
        indent = len(ln) - len(ln.lstrip())
        assert indent == 4, (
            f"report_dsr_sentinel is nested at indent {indent}, i.e. inside a "
            f"branch of the OF-5 if/elif/else chain. It depends on the fill "
            f"ledger and the era, NOT on the pooled sample, and must fire in "
            f"every branch. Line: {ln.strip()[:80]}")


def test_the_DEFERRED_branch_also_discloses_excluded_PnL(tmp_path):
    """The n==0 early return omitted `dropped_pnl`, so the DEFERRED line
    printed "$+0.00 of PnL is not in this statistic" while 19 unattributable
    conviction trips worth -$18.91 sat outside it - `seg.get("dropped_pnl",
    0.0)` fell back to the default.

    A disclosure that goes silent in the branch the guard spends most of its
    life in is no disclosure at all. Caught by RUNNING the sentinel against
    the live ledger, not by reading it."""
    p = tmp_path / "fills.csv"
    with open(p, "w", encoding="utf-8") as fh:
        fh.write("ts,position_id,exec_era\n")
        fh.write(f"100.0,a,{ERA}\n")
        fh.write("200.0,a,\n")          # unstamped leg -> unattributable
    seg = dsr_deployed_segment([_row("a", -18.91, 1_700_000_000.0)], p, ERA)
    assert seg["n"] == 0
    assert "dropped_pnl" in seg, "the DEFERRED return dropped the key"
    assert abs(seg["dropped_pnl"] + 18.91) < 1e-9
    _, _, detail = dsr_sentinel_verdict(seg)
    assert "-18.91" in detail, (
        "a losing trip left the statistic without appearing in the DEFERRED "
        "message - the exclusion channel is invisible exactly where the "
        "guard sits today")


def test_sentinel_prose_never_leaks_a_STATUS_TOKEN_into_the_report():
    """The sentinel's INFO text lands in outputs/overfit_report.md on EVERY
    run, including the synthetic-benchmark runs that CI gates on.

    `tests/test_overfit_check_ci.py` asserts `"FAIL" not in report` as its
    proxy for "no rung failed". When the sentinel was hoisted out of the
    conviction branch (OBJ-2) its DEFERRED message - which read "OF-5's
    pooled FAIL says NOTHING about it either way" - started reaching that
    report and reddened TWO pre-existing CI tests that had nothing to do
    with this change.

    The prose was reworded rather than the pin loosened: bending an existing
    gate to accommodate a new change is the silencing pattern this whole file
    exists to prevent. This pin keeps the constraint visible so the next
    author does not reintroduce the token and then 'fix' the CI test."""
    for n, mean, sd in ((0, 0.0, 0.0), (3, -5.0, 1.0), (20, -0.05, 1.5),
                        (20, -2.0, 0.5)):
        seg = _seg(n, mean, sd) if n else {"available": True, "n": 0,
                                           "era": ERA, "dropped": {},
                                           "excluded": 0, "dropped_pnl": 0.0}
        _, _, detail = dsr_sentinel_verdict(seg)
        for token in ("FAIL", "PASS"):
            assert token not in detail, (
                f"the sentinel emitted the bare report-status token "
                f"{token!r} at n={n}. It reaches outputs/overfit_report.md "
                f"on every run and trips the report-level substring checks "
                f"in tests/test_overfit_check_ci.py")
    _, _, indet = dsr_sentinel_verdict({"available": False, "reason": "x"})
    assert "FAIL" not in indet and "PASS" not in indet
