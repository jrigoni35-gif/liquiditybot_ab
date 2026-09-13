"""Pins for scripts/checked.py and scripts/verify_readonly.py.

Both exist because a claim was made and later measured false. The pins keep
the DISTINCTIONS, which is where both tools earn their keep:

  checked.py       green / red / NO-TESTS is a three-way split. A two-way
                   rc==0 read cannot express "nothing ran", which is how a
                   -k that selects nothing gets scored as a caught mutant.
  verify_readonly  a census DIFF, not a source grep. Grepping
                   scripts/horizon_report.py for write calls found none; the
                   script writes outputs/horizon_report.txt.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str):
    spec = importlib.util.spec_from_file_location(
        name, ROOT / "scripts" / f"{name}.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


chk = _load("checked")
ro = _load("verify_readonly")


# ======================================================================
# checked.py - the three-way verdict
# ======================================================================

def test_pytest_exit_5_is_its_own_verdict():
    """THE LOAD-BEARING PIN. Not a pass, not a failure - nothing ran."""
    assert chk.verdict(5, is_pytest=True) == "no-tests"


def test_exit_5_from_a_NON_pytest_command_is_just_red():
    """NEGATIVE ARM: 5 is only special for pytest. Another tool's 5 is a
    plain failure and must not be excused as 'nothing ran'."""
    assert chk.verdict(5, is_pytest=False) == "red"


@pytest.mark.parametrize("rc,is_pt,want", [
    (0, True, "green"), (0, False, "green"),
    (1, True, "red"), (1, False, "red"),
    (2, True, "red"), (5, True, "no-tests"), (5, False, "red"),
])
def test_verdict_is_exhaustive(rc, is_pt, want):
    assert chk.verdict(rc, is_pt) == want


def test_pytest_detection_looks_at_the_head_of_the_command():
    assert chk.looks_like_pytest(["python", "-m", "pytest", "tests/"])
    assert chk.looks_like_pytest(["pytest", "-q"])
    assert not chk.looks_like_pytest(["ruff", "check", "core"])
    assert not chk.looks_like_pytest([])


def test_a_wrong_expectation_exits_2(tmp_path, capsys):
    """--expect turns 'I believe this is green' into a checked claim."""
    rc = chk.main(["--expect", "red", "--tail", "0", "--",
                   sys.executable, "-c", "pass"])
    assert rc == chk.MISMATCH_RC
    assert "MISMATCH" in capsys.readouterr().out


def test_a_right_expectation_exits_0():
    assert chk.main(["--expect", "green", "--tail", "0", "--",
                     sys.executable, "-c", "pass"]) == 0


def test_a_failing_command_returns_its_own_code():
    """The command's exit code, never a pipeline's - there is no pipeline."""
    assert chk.main(["--tail", "0", "--",
                     sys.executable, "-c", "raise SystemExit(7)"]) == 7


def test_no_command_is_an_error():
    assert chk.main(["--tail", "0"]) == chk.MISMATCH_RC


def test_output_is_never_silently_truncated(capsys):
    """A tail that drops failure names is how two failures became
    unidentifiable on 2026-09-13. Truncation must ANNOUNCE itself."""
    chk.main(["--tail", "2", "--", sys.executable, "-c",
              "print('\\n'.join(str(i) for i in range(40)))"])
    out = capsys.readouterr().out
    assert "earlier lines NOT shown" in out


# ======================================================================
# verify_readonly.py - a census diff, not a source grep
# ======================================================================

def test_a_rewrite_with_the_same_size_AND_mtime_is_still_caught(tmp_path):
    """The hash is why this beats an mtime+size census, and this pin ISOLATES
    it: size is held equal and the original mtime is restored, so mtime and
    size both match and ONLY the content differs. Nothing else in the
    fingerprint can catch it.

    The first version of this test wrote AAAA then BBBB and asserted a diff -
    which passed with the hash removed, because mtime_ns differed between the
    two writes. scripts/mutate.py found that (the mutant SURVIVED). This is
    the same combination that let a stale .pyc validate after a byte-identical
    restore, so the pin has to hold mtime fixed to mean anything.
    """
    import os
    f = tmp_path / "a.txt"
    f.write_bytes(b"AAAA")
    st = f.stat()
    before = ro.census([str(tmp_path)])
    f.write_bytes(b"BBBB")                            # same length
    os.utime(f, ns=(st.st_atime_ns, st.st_mtime_ns))  # same mtime
    after = ro.census([str(tmp_path)])
    assert f.stat().st_size == st.st_size
    assert f.stat().st_mtime_ns == st.st_mtime_ns
    assert ro.diff(before, after)["modified"] == [str(f)], \
        "size and mtime match, so only the content hash can catch this"


def test_creation_and_deletion_are_both_reported(tmp_path):
    a = tmp_path / "a.txt"
    a.write_bytes(b"x")
    before = ro.census([str(tmp_path)])
    a.unlink()
    (tmp_path / "b.txt").write_bytes(b"y")
    d = ro.diff(before, ro.census([str(tmp_path)]))
    assert d["deleted"] == [str(a)]
    assert d["created"] == [str(tmp_path / "b.txt")]


def test_an_untouched_tree_diffs_empty(tmp_path):
    """NEGATIVE ARM: no spurious changes, or the tool cries wolf and is
    ignored."""
    (tmp_path / "a.txt").write_bytes(b"x")
    before = ro.census([str(tmp_path)])
    assert ro.diff(before, ro.census([str(tmp_path)])) == {
        "created": [], "deleted": [], "modified": []}


def test_pycache_is_not_counted_as_a_write(tmp_path):
    """Running any python subject writes bytecode. Counting that would make
    every verdict NOT-read-only and the tool useless."""
    pd = tmp_path / "__pycache__"
    pd.mkdir()
    before = ro.census([str(tmp_path)])
    (pd / "m.cpython-314.pyc").write_bytes(b"junk")
    assert ro.diff(before, ro.census([str(tmp_path)]))["created"] == []


def test_a_writing_subject_is_reported(tmp_path, capsys):
    target = tmp_path / "out.txt"
    rc = ro.main(["--watch", str(tmp_path), "--quiet", "--",
                  sys.executable, "-c",
                  f"open(r'{target}', 'w').write('x')"])
    assert rc == 1
    assert "NOT read-only" in capsys.readouterr().out


def test_a_non_writing_subject_is_verified(tmp_path, capsys):
    rc = ro.main(["--watch", str(tmp_path), "--quiet", "--",
                  sys.executable, "-c", "pass"])
    assert rc == 0
    assert "VERIFIED" in capsys.readouterr().out


def test_a_crashed_subject_is_not_called_read_only(tmp_path, capsys):
    """A script that died before its write is not evidence of anything."""
    rc = ro.main(["--watch", str(tmp_path), "--quiet", "--",
                  sys.executable, "-c", "raise SystemExit(3)"])
    assert rc == 2
    assert "THE SUBJECT FAILED" in capsys.readouterr().out
