"""Exploration-phase gating policy for OF-1 / OF-7 (operator adjudication
2026-08-09).

WHAT WAS DECIDED. On the repaired era-3 corpus the overfit audit is
honestly red: OF-1 train/OOF gaps of +0.40..+0.50 across all three
families and a dead-feature fraction of ~0.95-0.97 against 64 features.
That verdict is TRUE and must stay visible. What was wrong was its
BLAST RADIUS: this battery stage gates CODE deploys, so a data-starved
corpus was holding code-safety fixes hostage - conflating model
readiness with code correctness.

WHAT WAS NOT DONE. No threshold moved. 0.12 and 0.55 are unchanged, the
measured numbers are still printed on every run, and model TRUST is
still enforced where it belongs: ml.model_selection's evidence floors
refuse the higher-capacity families at this row count, and the live ML
governor kills a confidently-wrong model on realized outcomes.

These tests pin the three properties that make the policy honest rather
than a quiet gate-widening:
  1. it is CONDITIONAL on a documented, config-derived phase flag,
  2. it FAILS CLOSED - anything that cannot establish the phase gates,
  3. it SELF-TERMINATES - flip ml.exploration.enabled off and the hard
     gates return with no stamp to clear and no operator memory needed.
"""
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.overfit_check import gate_is_informational

_ROOT = Path(__file__).resolve().parents[1]


# ------------------------------------------------------------ the predicate
def test_only_soft_during_exploration_on_live_data():
    assert gate_is_informational(explore_on=True, on_synthetic=False) is True


def test_hard_gate_once_exploration_is_off():
    """The self-termination property: no stamp, no marker, no operator
    memory - switching exploration off re-arms both gates."""
    assert gate_is_informational(explore_on=False, on_synthetic=False) is False


def test_synthetic_benchmark_always_gates():
    """On the planted-signal benchmark OF-1/OF-7 validate the INSTRUMENT
    against a known answer. An instrument that grades itself leniently is
    not an instrument, so the phase flag must not reach it."""
    assert gate_is_informational(explore_on=True, on_synthetic=True) is False
    assert gate_is_informational(explore_on=False, on_synthetic=True) is False


def test_fails_closed_on_unknown_phase():
    """Callers that cannot READ the config pass explore_on=False (see
    main()'s except branch). Falsy/degenerate inputs must gate, never
    soften - the OF-5/DSR convention."""
    for bad in (None, 0, "", []):
        assert gate_is_informational(bad, False) is False  # type: ignore[arg-type]


# ------------------------------------------------------- wiring + reporting
def test_both_gates_use_the_one_predicate():
    """OF-1 and OF-7 must not re-implement the phase test independently -
    two derivations of one predicate is the drift class this repo keeps
    paying for (2026-08-09: label_era, and _explore_on itself, which was
    being derived twice in this same file)."""
    src = (_ROOT / "scripts" / "overfit_check.py").read_text(encoding="utf-8")
    assert src.count("def gate_is_informational") == 1
    # once for OF-1, once for OF-7's dead-feature branch
    assert src.count("gate_is_informational(") >= 3   # def + 2 call sites
    assert "_explore_on = bool(" in src, "phase flag must be derived..."
    assert src.count("_explore_on = bool(") == 1, "...exactly once"


def test_thresholds_are_untouched():
    """The policy scopes what a verdict BLOCKS; it must never move a
    number. If either literal changes, that is a re-baseline and needs
    its own justification - not this test's silence."""
    src = (_ROOT / "scripts" / "overfit_check.py").read_text(encoding="utf-8")
    assert 'g["gap_auc"] <= 0.12' in src
    assert 'dof["dead_feature_frac"] < 0.55' in src


def test_informational_lines_still_report_the_number():
    """A softened gate that stops printing its measurement is how a red
    becomes invisible. The INFO branch must carry the value AND say what
    re-arms it."""
    src = (_ROOT / "scripts" / "overfit_check.py").read_text(encoding="utf-8")
    i = src.index("INFORMATIONAL (")
    window = src[i:i + 600]
    assert "{detail}" in window, "the measured gap must be printed"
    assert "memorization band" in window, "state which band it is over"
    assert "arms when ml.exploration.enabled is false" in window


@pytest.mark.timing
def test_synthetic_run_keeps_hard_pass_fail_verdicts(tmp_path):
    """End-to-end: --force-synthetic must still produce PASS/FAIL gap
    verdicts (never INFO), proving the benchmark path never took the soft
    branch. Guards the machinery-validation contract the whole battery
    leans on when the live corpus is too small to grade."""
    report = tmp_path / "of.md"
    proc = subprocess.run(
        [sys.executable, str(_ROOT / "scripts" / "overfit_check.py"),
         "--quick", "--force-synthetic", "--report-path", str(report)],
        cwd=str(tmp_path), capture_output=True, text=True,
        timeout=180)  # nosec B603 - fixed argv, no shell
    assert proc.returncode == 0, f"{proc.stdout}\n{proc.stderr}"
    text = report.read_text(encoding="utf-8")
    gap_lines = [ln for ln in text.splitlines() if "gap[" in ln]
    assert gap_lines, "the synthetic run must still emit OF-1 gap lines"
    assert all(ln.startswith("- **PASS**") or ln.startswith("- **FAIL**")
               for ln in gap_lines), (
        f"synthetic OF-1 must stay a hard gate, got: {gap_lines}")
