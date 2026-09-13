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


# ======================================================================
# THE WORKING-TREE LOCK
# ======================================================================

def _plant_lock(monkeypatch, tmp_path, age_sec: float = 0.0):
    import os
    import time
    monkeypatch.setattr(mut, "REPO", tmp_path)
    lock = mut.lock_path()
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock.write_text(f"{os.getpid()} {time.time() - age_sec}",
                    encoding="utf-8")
    return lock


def test_a_live_lock_blocks_a_second_mutation_run(monkeypatch, tmp_path):
    """This harness EDITS THE WORKING TREE. Two runs at once score each
    other's edits, and anything else reading the repo sees code nobody wrote.

    MEASURED 2026-09-13, on the author, within an hour of writing the sweep: a
    full `pytest tests/` and a `mutation_sweep --all` smoke test overlapped for
    seconds. tests/test_probe_budget.py failed on a mutant planted in
    core/audit.py, the suite read 1 failed / 5365 passed, and the test passed
    in isolation right afterwards. Neither tool said a word.
    """
    _plant_lock(monkeypatch, tmp_path)
    assert mut.lock_held_by_other(), "a live lock was not seen"
    with pytest.raises(RuntimeError, match="REFUSING TO MUTATE"):
        with mut.tree_lock():
            pass


def test_a_STALE_lock_fails_OPEN(monkeypatch, tmp_path):
    """NEGATIVE ARM, and it matters more than the positive one: a guard that
    can wedge every future run on a leftover file from a crashed process is
    worse than the bug it prevents. An hour-old lock is a dead run."""
    _plant_lock(monkeypatch, tmp_path, age_sec=7200.0)
    assert mut.lock_held_by_other() == ""
    with mut.tree_lock():
        pass


def test_the_lock_is_released_even_when_the_body_raises(monkeypatch,
                                                        tmp_path):
    """A crashed run must not poison the tree for an hour. Same lesson as the
    try/finally restore: a harness that dies mid-flight has to leave the repo
    exactly as it found it."""
    monkeypatch.setattr(mut, "REPO", tmp_path)
    lock = mut.lock_path()
    with pytest.raises(ValueError):
        with mut.tree_lock():
            assert lock.is_file(), "the lock was never taken"
            raise ValueError("boom")
    assert not lock.exists(), "a crashed run left the tree locked"


def test_a_malformed_lock_is_reported_not_ignored(monkeypatch, tmp_path):
    """An unparseable lock is not the same as no lock - something wrote it."""
    monkeypatch.setattr(mut, "REPO", tmp_path)
    lock = mut.lock_path()
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock.write_text("garbage", encoding="utf-8")
    assert "malformed" in mut.lock_held_by_other()


def test_the_child_pytest_is_told_it_may_run(monkeypatch, tmp_path):
    """The harness holds the lock WHILE running pytest - that child IS the
    measurement. It sets the marker conftest.py checks, so the guard stops
    everyone except the tool that took the lock. Without this the harness
    would deadlock against its own guard on the first mutant.
    """
    seen = {}

    class _R:
        returncode = 0
        stdout = "1 passed"
        stderr = ""

    def fake_run(cmd, **kw):
        seen.update(kw.get("env") or {})
        return _R()

    # CLEAR IT FIRST. When this suite is itself run BY the harness, the marker
    # is already in os.environ, so `dict(os.environ)` carries it and the test
    # passes whether or not _pytest sets it. Measured: the mutant that removed
    # the set SURVIVED for exactly that reason - the instrument's own
    # environment leaking into the measurement.
    monkeypatch.delenv(mut.MUTATION_ENV, raising=False)
    monkeypatch.setattr(mut.subprocess, "run", fake_run)
    mut._pytest("tests/test_x.py")
    assert seen.get(mut.MUTATION_ENV) == "1", \
        "the child pytest was not exempted - the harness blocks itself"


def test_an_AMBIGUOUS_needle_is_refused_not_planted_at_the_first_hit(
        tmp_path, monkeypatch):
    """A needle matching more than once must be REFUSED, never planted at the
    first hit. This is the same defect class the harness itself was written to
    end: the plant lands somewhere the author did not mean, the pin does not
    fire, and the run reports SURVIVED - a clean blind-spot claim about code
    that was never touched.

    MEASURED 2026-09-13, which is why this exists. Injecting `"ADA/USD",` into
    config.json to test a watch-lane pin landed on skimmer.candidates instead
    of watch_lane.pairs - the same string, 246 lines apart - and the harness
    reported SURVIVED for a pin whose input had not changed. With a unique
    needle the same pin CAUGHT it immediately.
    """
    src, test = _tree(tmp_path)
    before = src.read_bytes()
    src.write_bytes(b"MARK = 1\ndef f():\n    return 1\nOTHER = 1\n")
    monkeypatch.setattr(mut, "REPO", tmp_path)
    r = mut.run_one({"path": "subject.py", "old": "= 1",
                     "new": "= 2", "pin": "returns_one"},
                    str(test), verbose=False)
    assert r["verdict"] == mut.AMBIGUOUS, \
        f"planted a needle occurring 3x instead of refusing: {r}"
    assert "2x" in r["detail"], "the report must say HOW MANY it found"
    assert before is not None


def test_a_UNIQUE_needle_is_still_planted(tmp_path, monkeypatch):
    """NEGATIVE ARM: the uniqueness guard must not refuse ordinary work. A
    guard that rejects everything and a clean run are the same observation
    until separated."""
    src, test = _tree(tmp_path)
    monkeypatch.setattr(mut, "REPO", tmp_path)
    r = mut.run_one({"path": "subject.py", "old": "return 1",
                     "new": "return 2", "pin": "returns_one"},
                    str(test), verbose=False)
    assert r["verdict"] == mut.CAUGHT
    assert src.read_text(encoding="utf-8") == "def f():\n    return 1\n"


def test_AMBIGUOUS_is_never_scored_as_a_pass(tmp_path, monkeypatch):
    """It is not CAUGHT and not SURVIVED - like PIN-NOT-SELECTED, it means
    nothing was established. The CLI must exit nonzero on it, or a spec full
    of ambiguous needles reports a clean sweep of nothing."""
    src, test = _tree(tmp_path)
    src.write_bytes(b"MARK = 1\ndef f():\n    return 1\nOTHER = 1\n")
    monkeypatch.setattr(mut, "REPO", tmp_path)
    rc = mut.main(["--test", str(test), "--mutant",
                   f"subject.py {mut.SEP} = 1 {mut.SEP} = 2 "
                   f"{mut.SEP} returns_one"])
    assert rc != 0, "an ambiguous needle exited 0 - that reads as verified"


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
