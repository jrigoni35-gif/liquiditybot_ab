"""Pins for scripts/mutate.py.

This tool decides whether OTHER pins are trustworthy, so its own failure modes
matter more than most. Both were measured, not imagined:

  * 2026-09-13: a hand-rolled harness reported CAUGHT on a mutation whose `-k`
    selected NO TESTS. pytest exit 5 and a real red are both `rc != 0`, so the
    naive check cannot tell "the pin caught it" from "the pin does not exist".
  * 2026-09-07: a crashed harness left a mutant on disk, because restore was
    not in a `finally`.

The pure decision function is `classify`, and it is pinned exhaustively - if
it ever returns CAUGHT for an unselected pin, every mutation table in this
repo becomes worthless at once.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_SPEC = importlib.util.spec_from_file_location(
    "mutate_harness", ROOT / "scripts" / "mutate.py")
assert _SPEC and _SPEC.loader
mut = importlib.util.module_from_spec(_SPEC)
sys.modules["mutate_harness"] = mut
_SPEC.loader.exec_module(mut)


# ======================================================================
# classify - the reason this module exists
# ======================================================================

def test_an_unselected_pin_is_never_CAUGHT():
    """THE LOAD-BEARING PIN. rc=5 is 'no tests collected'. A harness that
    reads it as a red reports a decorative pin as a real one."""
    assert mut.classify(5, 5) == mut.NOT_SELECTED
    assert mut.classify(5, 1) == mut.NOT_SELECTED
    assert mut.classify(0, 5) == mut.NOT_SELECTED


def test_a_real_red_is_CAUGHT():
    assert mut.classify(0, 1) == mut.CAUGHT


def test_a_green_mutant_SURVIVED():
    """NEGATIVE ARM: if the suite stays green under a planted defect, the pin
    is decorative and must be reported as such."""
    assert mut.classify(0, 0) == mut.SURVIVED


@pytest.mark.parametrize("sel,mutated,want", [
    (0, 1, "CAUGHT"), (0, 2, "CAUGHT"), (0, 0, "SURVIVED"),
    (5, 0, "PIN-NOT-SELECTED"), (5, 5, "PIN-NOT-SELECTED"),
    (0, 5, "PIN-NOT-SELECTED"),
])
def test_classify_is_exhaustive(sel, mutated, want):
    assert mut.classify(sel, mutated) == want


# ======================================================================
# parse_mutant - a malformed spec must not silently become a no-op
# ======================================================================

def test_a_well_formed_spec_parses():
    m = mut.parse_mutant("core/foo.py :: old :: new :: pin_name")
    assert m == {"path": "core/foo.py", "old": "old", "new": "new",
                 "pin": "pin_name"}


def test_a_no_op_mutation_is_refused():
    """old == new plants nothing and would report CAUGHT or SURVIVED on a
    tree that never changed."""
    with pytest.raises(ValueError):
        mut.parse_mutant("core/foo.py :: same :: same :: pin")


@pytest.mark.parametrize("bad", [
    "core/foo.py :: old :: new",                  # too few fields
    "core/foo.py :: old :: new :: pin :: extra",  # too many
    " :: old :: new :: pin",                      # empty path
    "core/foo.py ::  :: new :: pin",              # empty old
    "core/foo.py :: old :: new :: ",              # empty pin
])
def test_a_malformed_spec_raises(bad):
    with pytest.raises(ValueError):
        mut.parse_mutant(bad)


# ======================================================================
# end to end, against a throwaway tree
# ======================================================================

def _tree(tmp_path):
    src = tmp_path / "subject.py"
    src.write_text("def f():\n    return 1\n", encoding="utf-8")
    test = tmp_path / "test_subject.py"
    test.write_text(
        "import importlib.util, sys\n"
        "from pathlib import Path\n"
        "s = importlib.util.spec_from_file_location('subj',\n"
        "    Path(__file__).parent / 'subject.py')\n"
        "m = importlib.util.module_from_spec(s); s.loader.exec_module(m)\n"
        "def test_returns_one():\n"
        "    assert m.f() == 1\n", encoding="utf-8")
    return src, test


def test_a_caught_mutant_restores_the_file_byte_identically(tmp_path,
                                                            monkeypatch):
    src, test = _tree(tmp_path)
    before = src.read_bytes()
    monkeypatch.setattr(mut, "REPO", tmp_path)
    r = mut.run_one({"path": "subject.py", "old": "return 1",
                     "new": "return 2", "pin": "returns_one"},
                    str(test), verbose=False)
    assert r["verdict"] == mut.CAUGHT
    assert src.read_bytes() == before, "the mutant was left on disk"


def test_a_surviving_mutant_is_reported_not_hidden(tmp_path, monkeypatch):
    src, test = _tree(tmp_path)
    src.write_text("def f():\n    return 1\nUNUSED = 0\n", encoding="utf-8")
    monkeypatch.setattr(mut, "REPO", tmp_path)
    r = mut.run_one({"path": "subject.py", "old": "UNUSED = 0",
                     "new": "UNUSED = 99", "pin": "returns_one"},
                    str(test), verbose=False)
    assert r["verdict"] == mut.SURVIVED


def test_an_absent_needle_is_reported_not_treated_as_caught(tmp_path,
                                                            monkeypatch):
    src, test = _tree(tmp_path)
    monkeypatch.setattr(mut, "REPO", tmp_path)
    r = mut.run_one({"path": "subject.py", "old": "not in the file",
                     "new": "x", "pin": "returns_one"},
                    str(test), verbose=False)
    assert r["verdict"] == mut.NEEDLE_ABSENT


def test_an_unselected_pin_is_reported_end_to_end(tmp_path, monkeypatch):
    """The 2026-09-13 false positive, reproduced against a real pytest run."""
    src, test = _tree(tmp_path)
    # Compare against what the fixture ACTUALLY wrote. write_text emits CRLF
    # on Windows, so a hardcoded LF literal fails for a reason that has
    # nothing to do with the harness under test - the same class of mistake
    # the harness itself had before it was moved to bytes.
    before = src.read_bytes()
    monkeypatch.setattr(mut, "REPO", tmp_path)
    r = mut.run_one({"path": "subject.py", "old": "return 1",
                     "new": "return 2", "pin": "no_such_pin_anywhere"},
                    str(test), verbose=False)
    assert r["verdict"] == mut.NOT_SELECTED
    assert src.read_bytes() == before


def test_the_cli_exits_nonzero_when_a_mutant_survives(tmp_path, monkeypatch,
                                                       capsys):
    """A harness that reports a decorative pin and exits 0 is itself one."""
    src, test = _tree(tmp_path)
    src.write_text("def f():\n    return 1\nUNUSED = 0\n", encoding="utf-8")
    monkeypatch.setattr(mut, "REPO", tmp_path)
    rc = mut.main(["--test", str(test), "--quiet", "--mutant",
                   "subject.py :: UNUSED = 0 :: UNUSED = 9 :: returns_one"])
    assert rc == 1
    assert "SURVIVED" in capsys.readouterr().out


def test_the_cli_refuses_a_red_baseline(tmp_path, monkeypatch, capsys):
    """Mutating a red suite proves nothing, so it must not be attempted."""
    src, test = _tree(tmp_path)
    src.write_text("def f():\n    return 999\n", encoding="utf-8")
    monkeypatch.setattr(mut, "REPO", tmp_path)
    rc = mut.main(["--test", str(test), "--quiet", "--mutant",
                   "subject.py :: return 999 :: return 1 :: returns_one"])
    assert rc == 1
    assert "not green" in capsys.readouterr().out.lower()


def test_the_cli_exits_zero_when_every_mutant_is_caught(tmp_path, monkeypatch):
    src, test = _tree(tmp_path)
    monkeypatch.setattr(mut, "REPO", tmp_path)
    assert mut.main(["--test", str(test), "--quiet", "--mutant",
                     "subject.py :: return 1 :: return 2 :: returns_one"]) == 0


def test_a_spec_file_is_accepted(tmp_path, monkeypatch):
    src, test = _tree(tmp_path)
    spec = tmp_path / "m.json"
    spec.write_text(json.dumps([{"path": "subject.py", "old": "return 1",
                                 "new": "return 2", "pin": "returns_one"}]),
                    encoding="utf-8")
    monkeypatch.setattr(mut, "REPO", tmp_path)
    assert mut.main(["--test", str(test), "--quiet",
                     "--spec", str(spec)]) == 0
