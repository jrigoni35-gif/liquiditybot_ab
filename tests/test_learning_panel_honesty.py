"""LEARNING-PANEL HONESTY PINS — the panel must not report success it never had.

Two defects, both measured 2026-09-04 (sweep §3 HIGH). Both are the
measurement-plane failure class CLAUDE.md's MINDSET section names: a confident
instrument, wrong, with nothing flagging it.

DEFECT 1 — exit 0 on total route collapse. `main()` ended in an unconditional
`return 0`, so the process exited green even when EVERY route failed, timed out
or errored. The live `LiquidityBot-LearningPanel-Daily` scheduled task recorded
`LastTaskResult=0` on a run that contained a TIMEOUT. "OK" meant "the process
exited", not "a measurement was made" - and an operator reading Task Scheduler
had no way to tell those apart.

DEFECT 2 — silent tail truncation. `_head_tail` kept only the LAST 15 stdout
lines with no marker, so a reader saw a complete-looking block that had silently
dropped everything above it. 14 of 16 routes were tail-saturated at exactly 15
lines, which meant `cohort_eval`'s entire verdict + homogeneity section - the
gate the whole project waits on - never reached either the .md or the .json.
Truncation is fine; SILENT truncation is the defect.

These pin the PROPERTY (a bad run is visible; a truncated block says so), not
the pattern, so a refactor that keeps the behaviour stays green.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

_spec = importlib.util.spec_from_file_location(
    "learning_panel_under_test", ROOT / "scripts" / "learning_panel.py")
lp = importlib.util.module_from_spec(_spec)
sys.modules["learning_panel_under_test"] = lp
_spec.loader.exec_module(lp)


# --------------------------------------------------------------- defect 1
@pytest.mark.parametrize("counts,expect_nonzero", [
    ({"ok": 16, "failed": 0, "timeout": 0, "error": 0}, False),
    ({"ok": 15, "failed": 0, "timeout": 1, "error": 0}, True),   # the live case
    ({"ok": 15, "failed": 1, "timeout": 0, "error": 0}, True),
    ({"ok": 15, "failed": 0, "timeout": 0, "error": 1}, True),
    ({"ok": 0, "failed": 16, "timeout": 0, "error": 0}, True),   # total collapse
])
def test_exit_code_reflects_route_outcomes(counts, expect_nonzero):
    """A green exit must mean every route produced a measurement."""
    rc = lp.panel_exit_code(counts)
    if expect_nonzero:
        assert rc != 0, (
            f"counts={counts} exited 0 - a failed/timed-out/errored route is "
            f"invisible to Task Scheduler and to any caller that checks rc")
    else:
        assert rc == 0, f"counts={counts} is a clean run but exited {rc}"


def test_total_collapse_is_not_reported_as_success():
    """THE REGRESSION, stated at its worst: every route dead, exit still 0."""
    assert lp.panel_exit_code(
        {"ok": 0, "failed": 0, "timeout": 16, "error": 0}) != 0


# --------------------------------------------------------------- defect 2
def test_truncated_tail_says_it_was_truncated():
    """A block that dropped 200 lines must not look identical to a complete
    one. The reader's only cue is a marker we control."""
    stdout = "\n".join(f"line {i}" for i in range(200))
    _head, tail = lp._head_tail(stdout, "", ok=True)
    joined = "\n".join(tail)
    assert "truncated" in joined.lower(), (
        "a 200-line stdout was cut to a 15-line block with NO marker - the "
        "reader cannot distinguish it from complete output")
    assert "185" in joined, (
        "the marker must name HOW MANY lines were omitted; a bare 'truncated' "
        "does not tell a reader whether they lost 1 line or 1,000")


def test_short_output_is_not_marked_truncated():
    """ANTI-RUBBER-STAMP. If the marker appeared unconditionally the pin above
    would pass on any implementation."""
    _head, tail = lp._head_tail("only\ntwo lines", "", ok=True)
    joined = "\n".join(tail)
    assert "truncated" not in joined.lower(), (
        "output that fit was labelled truncated - the marker is unconditional "
        "and the truncation pin proves nothing")
    assert "only" in joined and "two lines" in joined


def test_full_stdout_survives_into_the_json():
    """The .md may be a summary; the .json is the record. cohort_eval's verdict
    block must be recoverable from SOMEWHERE."""
    stdout = "\n".join(f"line {i}" for i in range(200)) + "\nVERDICT: COST_BOUND"
    route = lp.Route(name="fake", script="learning_panel.py", timeout_sec=5)
    res = lp._package_result(route, stdout=stdout, stderr="", rc=0,
                             duration=0.1, status="OK")
    assert "stdout_full" in res, (
        "the result dict carries only the truncated tail - the dropped lines "
        "are unrecoverable from the JSON too")
    assert "VERDICT: COST_BOUND" in res["stdout_full"]
    assert "line 0" in res["stdout_full"], "the HEAD of the output was lost"


# ------------------------------------------------------ W2: bounded full text
def test_full_text_is_bounded_and_says_when_it_truncated():
    """learning_panel.json is bundled and synced off-box. Retaining unbounded
    route output would grow a synced artifact without limit and widen what
    leaves the machine. Bounded - and marked, because a silent truncation is
    the exact defect the tail marker above exists to fix."""
    small = "fits fine"
    assert lp._bounded(small) == small, "a small payload must pass through whole"

    big = "x" * (lp.FULL_TEXT_CAP + 5000) + "\nVERDICT: COST_BOUND"
    out = lp._bounded(big)
    assert len(out) <= lp.FULL_TEXT_CAP + 200, "the cap did not bind"
    assert "truncated" in out.lower(), "truncation was silent"
    assert out.rstrip().endswith("VERDICT: COST_BOUND"), (
        "the TAIL must be kept - verdict lines are emitted last, and losing "
        "them is why this field exists at all")


def test_bounded_handles_none():
    """_package_result feeds it subprocess output, which can be None."""
    assert lp._bounded(None) == ""
