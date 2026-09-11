"""The overfit battery's exit code must distinguish DARK from PASS.

THE DEFECT THIS KILLS. scripts/overfit_check.py ended in
`return 0 if FAIL_N == 0 else 1`. That is blind to how many rungs ARMED, so a
run where four of seven gates could not fire returned the same 0 as a run
where all seven fired and passed. CLAUDE.md's definition-of-done consumes this
script by exit code, and its own text warns "the number to read is the ARMED
count, never the exit code" — a warning that existed precisely because the
exit code could not carry it. Now it can.

WHY A RATCHET AND NOT "ALL SEVEN MUST ARM". Demanding every rung arm would
exit non-zero today and stay there: OF-5's own text documents it as UNPASSABLE
at N=7, and OF-4 is inert on a zero-entry recording. A permanently red gate is
a brick, not a gate. The invariant is MONOTONE ARMING — a family that arms
today must not stop arming tomorrow.

WHY A SET AND NOT A COUNT. Measured 2026-09-10: two runs about an hour apart
reported 3 then 4 armed. (The CAUSE was mis-attributed to `dof: not starved`
arming as the corpus grew - red-team OBJ-14, conceded. `dof` calls check()
unconditionally so it is ALWAYS armed and has no dark state; the observation
stands, the mechanism does not, and the runs are gone. The derivable
fragility is `pbo`, evidence-gated at min_live_rows=60 against a measured
n_live=63 - a three-row margin.)  The original text continued: as the corpus grew
past its rows-per-feature floor. A hardcoded count was stale within the hour;
a set names WHICH families, so growth reads as NEWLY ARMED rather than drift.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "scripts"))

from overfit_check import (EXPECTED_ARMED, armed_families,  # noqa: E402
                           arming_exit_code)


def _quiet(*_a, **_k):
    return None


def _all_armed():
    return [("PASS", f"{fam}: something measured", "") for fam in EXPECTED_ARMED]


# --------------------------------------------------------------------------
# armed_families: INFO is not armed
# --------------------------------------------------------------------------

def test_info_lines_are_not_armed_gates():
    """The whole point: a gate that COULD NOT FIRE is not a gate that passed."""
    report = [("INFO", "purge: could not fire", "no evidence"),
              ("PASS", "shuffle: fired", "")]
    assert armed_families(report) == {"shuffle"}


def test_failed_gates_still_count_as_ARMED():
    """A gate that fired and FAILED is armed — it measured something. Only
    the fail_n argument decides pass/fail; arming is a separate axis."""
    assert armed_families([("FAIL", "pbo: fired and failed", "")]) == {"pbo"}


def test_family_key_is_the_token_before_the_colon():
    report = [("PASS", "dof: not starved (>=10 rows per feature)", "")]
    assert armed_families(report) == {"dof"}


# --------------------------------------------------------------------------
# the exit-code policy
# --------------------------------------------------------------------------

def test_green_when_everything_armed_and_nothing_failed():
    assert arming_exit_code(_all_armed(), EXPECTED_ARMED, 0, _quiet) == 0


def test_a_real_failure_returns_1():
    assert arming_exit_code(_all_armed(), EXPECTED_ARMED, 1, _quiet) == 1


@pytest.mark.parametrize("dark", sorted(EXPECTED_ARMED))
def test_any_family_going_dark_returns_3(dark):
    """Parametrized over every expected family: none of them may go dark
    silently. Without this the test would only pin whichever one was typed."""
    report = [r for r in _all_armed() if not r[1].startswith(dark + ":")]
    assert arming_exit_code(report, EXPECTED_ARMED, 0, _quiet) == 3


def test_a_dark_gate_reported_as_INFO_still_returns_3():
    """The exact laundering shape: the rung is present in the report, but as
    an informational line. Before this change that returned 0."""
    report = [r for r in _all_armed() if not r[1].startswith("purge:")]
    report.append(("INFO", "purge: evidence-gated, could not fire", ""))
    assert arming_exit_code(report, EXPECTED_ARMED, 0, _quiet) == 3


def test_failure_outranks_arming_regression():
    """1 and 3 are both non-zero; a real failure is the more urgent fact."""
    report = [r for r in _all_armed() if not r[1].startswith("purge:")]
    assert arming_exit_code(report, EXPECTED_ARMED, 1, _quiet) == 1


def test_a_newly_armed_family_is_green_but_announced():
    """Corpus growth arms new rungs. That must not be a failure — it must be
    a prompt to ratchet the floor UP."""
    said = []
    report = _all_armed() + [("PASS", "newgate: just started firing", "")]
    assert arming_exit_code(report, EXPECTED_ARMED, 0, said.append) == 0
    assert any("NEWLY ARMED" in s for s in said)
    assert any("newgate" in s for s in said)


def test_the_regression_message_names_the_dark_family():
    """A code with no name sends the reader back into a 2-minute battery."""
    said = []
    report = [r for r in _all_armed() if not r[1].startswith("shuffle:")]
    assert arming_exit_code(report, EXPECTED_ARMED, 0, said.append) == 3
    assert any("shuffle" in s and "ARMING REGRESSED" in s for s in said)


# --------------------------------------------------------------------------
# the baseline itself
# --------------------------------------------------------------------------

# --------------------------------------------------------------------------
# the silent-synthetic case an adversarial audit found the ratchet missing
# --------------------------------------------------------------------------

def test_a_silent_synthetic_substitution_returns_4():
    """The corpus fell under the row floor and nobody asked for it.

    Found by an audit re-testing the ratchet: forcing the corpus under the
    floor with no CLI flag still exited 0. The ratchet alone cannot catch it
    because the synthetic fixture arms MORE rungs than the live corpus, so
    the roster check is satisfied by the substitution.
    """
    said = []
    rc = arming_exit_code(_all_armed(), EXPECTED_ARMED, 0, said.append,
                          on_synthetic=True, forced_synthetic=False)
    assert rc == 4
    assert any("SILENT SYNTHETIC" in s for s in said)


def test_a_DELIBERATE_synthetic_run_stays_green():
    """--force-synthetic is how CI exercises the machinery on purpose. If
    this returned non-zero the flag would be unusable and someone would
    delete the guard."""
    assert arming_exit_code(_all_armed(), EXPECTED_ARMED, 0, _quiet,
                            on_synthetic=True, forced_synthetic=True) == 0


def test_the_roster_check_does_not_apply_to_a_forced_synthetic_run():
    """Regression pin for a real break this change caused on its first run.

    tests/test_audit_ml_offline.py runs main() with --force-synthetic and
    STUBS `pbo` for speed. The first cut of the ratchet read that stub as an
    arming regression and returned 3 against a test asserting 0. Which
    families arm against a planted-signal fixture is a property of the
    FIXTURE, so the roster check must not run there at all.
    """
    stubbed = [r for r in _all_armed() if not r[1].startswith("pbo:")]
    assert arming_exit_code(stubbed, EXPECTED_ARMED, 0, _quiet,
                            on_synthetic=True, forced_synthetic=True) == 0
    # ...but the same roster gap on the LIVE corpus is still a regression
    assert arming_exit_code(stubbed, EXPECTED_ARMED, 0, _quiet,
                            on_synthetic=False, forced_synthetic=False) == 3


def test_silent_synthetic_outranks_an_arming_regression():
    """It invalidates every rung at once — 'which armed' is then a fact
    about the fixture, not the strategy."""
    report = [r for r in _all_armed() if not r[1].startswith("purge:")]
    assert arming_exit_code(report, EXPECTED_ARMED, 0, _quiet,
                            on_synthetic=True, forced_synthetic=False) == 4


def test_a_real_failure_still_outranks_silent_synthetic():
    assert arming_exit_code(_all_armed(), EXPECTED_ARMED, 1, _quiet,
                            on_synthetic=True, forced_synthetic=False) == 1


def test_live_corpus_is_unaffected_by_the_synthetic_guard():
    """The default path must be untouched: no synthetic, no change."""
    assert arming_exit_code(_all_armed(), EXPECTED_ARMED, 0, _quiet,
                            on_synthetic=False, forced_synthetic=False) == 0


def test_expected_armed_is_not_empty():
    """An empty EXPECTED_ARMED would make the ratchet vacuous — every report
    would satisfy it. That is how this guard would rot into decoration."""
    assert EXPECTED_ARMED, "the ratchet has no floor to hold"
    assert len(EXPECTED_ARMED) >= 4


def test_expected_families_are_bare_keys_not_full_names():
    """EXPECTED_ARMED holds the token before ':'. A full check() name here
    would never match armed_families() and the ratchet would silently pass."""
    for fam in EXPECTED_ARMED:
        assert ":" not in fam and fam == fam.strip() and fam


# --------------------------------------------------------------------------
# CORPUS ABSENT != SILENT SUBSTITUTION — red-team OBJ-13, conceded
#
# test_windows.bat:57 vetoes on ANY non-zero exit, so returning 4 on a tree with
# no corpus at all printed "OVERFIT GATES FAILED - do not arm" for every
# worktree-resident agent, with zero defect in the code. That is a permanently
# red gate, which this module's own docstring calls a brick rather than a gate.
#
# The hazard exit 4 exists for is a corpus that EXISTS and got silently swapped
# out under the row floor - something was there and nobody chose to ignore it.
# Nothing was substituted when there is nothing to substitute.
# --------------------------------------------------------------------------

_OK_REPORT = [("PASS", "shuffle", ""), ("PASS", "pbo", ""),
              ("PASS", "purge", ""), ("PASS", "dof", "")]
_EXPECTED = {"shuffle", "pbo", "purge", "dof"}


def _quiet(*_a, **_k):
    return None


def test_an_absent_corpus_does_not_brick_the_gate():
    from scripts.overfit_check import arming_exit_code
    rc = arming_exit_code(_OK_REPORT, _EXPECTED, 0, _quiet,
                          on_synthetic=True, forced_synthetic=False,
                          corpus_absent=True)
    assert rc == 0, (
        "a tree with no corpus exits non-zero, so every worktree agent reads "
        "OVERFIT GATES FAILED with nothing wrong")


def test_a_THIN_corpus_still_vetoes():
    """The other half. If this ever returns 0 the silent-substitution hazard is
    unguarded again, and that is the case exit 4 was created for."""
    from scripts.overfit_check import arming_exit_code
    rc = arming_exit_code(_OK_REPORT, _EXPECTED, 0, _quiet,
                          on_synthetic=True, forced_synthetic=False,
                          corpus_absent=False)
    assert rc == 4


def test_an_absent_corpus_cannot_mask_a_real_failure():
    """Precedence must hold: something measured and said no outranks an
    environment note."""
    from scripts.overfit_check import arming_exit_code
    rc = arming_exit_code(_OK_REPORT, _EXPECTED, 1, _quiet,
                          on_synthetic=True, forced_synthetic=False,
                          corpus_absent=True)
    assert rc == 1


def test_forced_synthetic_is_still_deliberate_and_green():
    from scripts.overfit_check import arming_exit_code
    assert arming_exit_code(_OK_REPORT, _EXPECTED, 0, _quiet,
                            on_synthetic=True, forced_synthetic=True,
                            corpus_absent=False) == 0
