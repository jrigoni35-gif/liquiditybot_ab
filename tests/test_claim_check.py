"""Pins for scripts/claim_check.py - the tool that reads commit messages back.

WHAT IT IS FOR. A commit message is a claim, and nothing in this repo ever
reads one back. A wrong path, a stale line number or an invented test name
there outlives the code: it is the artifact a future session greps to find out
what happened, and it is never re-checked.

THE TWO FALSE POSITIVES IT SHIPPED WITH, both pinned below, because the first
run over its own author's seven most recent commits reported three failures
and ALL THREE were the tool's own bug:

  1. `outputs/watch_history.csv` reported as an unresolved path. `outputs/` is
     GITIGNORED runtime state - the bot writes those files - so they are not
     in any tree and never will be.
  2. `tests/test_docs_era_currency.py` reported as an unknown TEST, because
     the file name contains a `test_*` substring. A test file is not a test
     function.

A checker that cries wolf gets turned off, which is the exact failure mode
every other tool in scripts/ was written to avoid - so both arms are held by
NEGATIVE pins here, not just the positive ones.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load():
    spec = importlib.util.spec_from_file_location(
        "claim_check", ROOT / "scripts" / "claim_check.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["claim_check"] = mod
    spec.loader.exec_module(mod)
    return mod


cc = _load()


@pytest.fixture
def fake(monkeypatch):
    """A small, fully controlled world: a two-file tree, one known test, one
    gitignored path. Nothing here touches the real repo or runs git."""
    monkeypatch.setattr(cc, "tree_paths",
                        lambda rev: {"core/thing.py", "docs/notes.md",
                                     "tests/test_docs_era_currency.py",
                                     "tests/test_mutation_sweep.py",
                                     "outputs/.gitkeep", "main.py"})
    monkeypatch.setattr(cc, "ignored",
                        lambda paths: {p for p in paths
                                       if p.startswith("outputs/")})
    monkeypatch.setattr(cc, "test_names", lambda: {"test_a_real_one"})
    monkeypatch.setattr(cc, "test_files", lambda: set())
    monkeypatch.setattr(cc, "file_lines",
                        lambda rev, path: 40 if path == "core/thing.py" else -1)
    monkeypatch.setattr(cc, "symbol_exists", lambda s: s != "core.thing.absent")


def kinds(findings):
    return [k for _, k, _ in findings]


# ======================================================================
# Paths
# ======================================================================

def test_a_MOVED_path_is_a_FALSE_claim(fake):
    """THE DANGEROUS CASE, and the only path finding that is an error.

    A pointer that LOOKS resolvable and is not: a future session greps the
    basename, finds the file somewhere else, and reads the old message against
    the new file. Everything else about absent paths is noise - measured over
    60 commits of this repo's history, every absent path was either a
    HYPOTHETICAL in a worked example ("commit B then changes only
    scripts/util.py's body") or one the message EXPLICITLY disclosed as
    never-shipped. Neither misleads anyone.
    """
    f = cc.check("the guard lives in core/notes.md now")
    assert kinds(f) == ["moved-path"]
    assert f[0][0] == "error"
    assert "docs/notes.md" in f[0][2], "the report must say where it IS"


def test_a_path_the_repo_NEVER_CARRIED_is_only_a_warning(fake):
    """A name that exists nowhere is a hypothetical, an example, or a
    never-shipped disclosure. Calling those false claims is how this tool
    reported 11 failures over 60 commits of which ZERO survived checking -
    a false-alarm rate that gets a checker turned off."""
    f = cc.check("moved the logic into core/ghost.py today")
    assert kinds(f) == ["unknown-path"]
    assert f[0][0] == "warn"


def test_a_path_that_exists_is_silent(fake):
    assert cc.check("touched core/thing.py and docs/notes.md") == []


def test_a_GITIGNORED_path_is_not_a_false_claim(fake):
    """FALSE POSITIVE 1. `outputs/` is runtime state the bot writes; it is in
    no tree and never will be. Reporting it as a false claim is how this tool
    failed its own first run."""
    assert cc.check("the script writes outputs/horizon_report.txt") == []


def test_a_line_number_past_the_end_of_the_file_is_FALSE(fake):
    f = cc.check("see core/thing.py:9999 for the guard")
    assert kinds(f) == ["line-out-of-range"]
    assert "40 lines" in f[0][2]


def test_a_line_number_inside_the_file_is_silent(fake):
    """Including THE LAST LINE. The first version of this pin used :12 against
    a 40-line file, so `>` -> `>=` SURVIVED - it never probed the boundary it
    was testing. Second instance of that exact shape in one session; the other
    was a throttle window in core/watch_lane.py, found the same way.
    """
    assert cc.check("see core/thing.py:12 for the guard") == []
    assert cc.check("see core/thing.py:40 for the guard") == [], \
        "the last line of the file was reported as out of range"
    assert cc.check("see core/thing.py:1 for the guard") == []


def test_an_unreadable_blob_does_not_invent_a_line_finding(fake):
    """file_lines returns -1 when it cannot read. Degrading to 'no finding' is
    correct: a checker must not report a claim FALSE on its own read failure -
    that is an instrument fault wearing a finding's clothes."""
    assert cc.check("see docs/notes.md:9999") == []


# ======================================================================
# Test names
# ======================================================================

def test_an_invented_test_name_is_a_FALSE_claim(fake):
    f = cc.check("pinned by test_something_i_made_up in the suite")
    assert kinds(f) == ["unknown-test"]


def test_a_real_test_name_is_silent(fake):
    assert cc.check("pinned by test_a_real_one") == []


def test_a_bare_test_FILE_basename_is_not_an_unknown_test(fake, monkeypatch):
    """Messages name files without prefix or extension constantly -
    "test_windows" is a .bat, "test_boards_stripped" is a .py. Neither is a
    test FUNCTION. The path regex only blanks a path carrying a DIRECTORY and
    an extension, so these survive it by construction, and they accounted for
    most of this tool's false alarms across 60 commits."""
    monkeypatch.setattr(cc, "test_files",
                        lambda: {"test_windows", "test_boards_stripped"})
    assert cc.check("re-baselined test_windows and test_boards_stripped") == []


def test_a_path_with_a_FILE_as_its_directory_is_prose_not_a_path(fake):
    """`main.py/train_meta.py` is this repo's shorthand for "and". Matched as
    one path it becomes a file that never existed. A directory segment may not
    itself end in a file extension."""
    assert cc.check("touched core/thing.py/train_meta.py in one pass") == [],         "a file used as a directory segment was read as a real path"
    assert cc.check("touched main.py/train_meta.py in the same pass") == []


def test_a_path_the_commit_DELETED_is_not_a_false_claim(fake, monkeypatch):
    """Resolving only against the commit's own tree made every deletion commit
    fail its own honest description. The parent tree is the right reference
    for a path a commit removes."""
    monkeypatch.setattr(cc, "tree_paths",
                        lambda rev: {"core/thing.py"} if rev != "abc^"
                        else {"core/thing.py", "core/gone.py"})
    assert cc.check("removed core/gone.py entirely", "abc") == []


def test_a_test_FILE_name_is_not_read_as_a_test_FUNCTION(fake):
    """FALSE POSITIVE 2. `tests/test_docs_era_currency.py` contains the
    substring `test_docs_era_currency`; a file is not a function. Path matches
    are blanked before function names are looked for."""
    assert cc.check("mirrors tests/test_docs_era_currency.py's helper") == []


def test_a_real_function_named_beside_a_path_is_still_checked(fake):
    """NEGATIVE ARM of the fix: blanking paths must not blank the rest of the
    line, or the check silently stops looking."""
    f = cc.check("tests/test_docs_era_currency.py holds test_made_up_name")
    assert kinds(f) == ["unknown-test"]
    assert f[0][2] == "test_made_up_name"


# ======================================================================
# Symbols
# ======================================================================

# One mutant against scripts/claim_check.py is NOT pinned, recorded here so
# the next reader does not re-investigate it:
#
#   `_PATH.sub(lambda mm: " " * len(mm.group(0)), message)` -> `sub(..., "")`
#
# EQUIVALENT for every property this tool has. Blanking and deleting both
# remove the path text before test names are looked for, and nothing here
# reports a column offset, so no observable answer changes. Padding is kept
# because it preserves offsets if a finding ever carries one - a reason to
# prefer it, not a behaviour a test can hold.


def test_an_unresolved_backticked_symbol_is_a_FALSE_claim(fake):
    f = cc.check("guarded in `core.thing.absent` now")
    assert kinds(f) == ["unresolved-symbol"]


def test_an_UNBACKTICKED_dotted_word_is_left_alone(fake):
    """Prose says 'config.json defaults' far more often than it names code.
    Only backticked symbols are judged - deliberately narrow, because the cost
    of a false alarm here is the whole tool."""
    assert cc.check("core.thing.absent in prose without backticks") == []


def test_symbol_resolution_reads_source_and_does_not_import(tmp_path,
                                                            monkeypatch):
    """Importing a repo module to check a name would give the checker SIDE
    EFFECTS. It resolves textually instead, and a false PASS is the acceptable
    direction: a false FAIL would make the tool noise."""
    monkeypatch.setattr(cc, "REPO", tmp_path)
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "m.py").write_bytes(
        b"BOOM = 1\n\n\ndef real_fn():\n    pass\n\n\nclass RealCls:\n    pass\n")
    assert cc.symbol_exists("pkg.m.real_fn")
    assert cc.symbol_exists("pkg.m.RealCls")
    assert cc.symbol_exists("pkg.m.BOOM")
    assert not cc.symbol_exists("pkg.m.never_defined")
    assert cc.symbol_exists("numpy.array"), \
        "a module outside this repo is not ours to judge"


# ======================================================================
# Volatile numbers - what the tool CANNOT check, said out loud
# ======================================================================

def test_a_bare_measurement_is_flagged_as_UNRUN(fake):
    """Not an accusation. This tool cannot reproduce '5265 passed', so it must
    not imply it verified it - it asks for a pointer instead."""
    f = cc.check("suite green: 5265 passed, 0 failed")
    assert kinds(f) == ["volatile-number", "volatile-number"]
    assert all(sev == "warn" for sev, _, _ in f)


def test_a_measurement_with_a_REDERIVE_POINTER_clears(fake):
    """The rule that applies: if a number is volatile, name where to
    re-derive it rather than freezing it into a permanent file."""
    assert cc.check(
        "37 anchors sat inside prose - re-derive with the census in "
        "tests/test_mutation_sweep.py") == []


def test_a_volatile_number_is_never_an_ERROR_by_default(fake):
    assert all(s == "warn" for s, _, _ in cc.check("133 passed"))


def test_strict_mode_turns_unrun_into_a_failure(fake, monkeypatch, capsys):
    monkeypatch.setattr(cc, "_git", lambda *a: "133 passed\n")
    assert cc.main(["--rev", "HEAD", "--quiet"]) == 0
    assert cc.main(["--rev", "HEAD", "--quiet", "--strict"]) == cc.FAIL_RC


# ======================================================================
# CLI
# ======================================================================

def test_a_false_claim_exits_nonzero(fake, monkeypatch):
    monkeypatch.setattr(cc, "_git", lambda *a: "the guard lives in core/notes.md\n")
    assert cc.main(["--rev", "HEAD", "--quiet"]) == cc.FAIL_RC


def test_a_clean_message_exits_zero(fake, monkeypatch):
    monkeypatch.setattr(cc, "_git", lambda *a: "touched core/thing.py\n")
    assert cc.main(["--rev", "HEAD", "--quiet"]) == 0


def test_exactly_one_source_is_required(capsys):
    assert cc.main([]) == cc.USAGE_RC
    assert cc.main(["--rev", "HEAD", "--message-file", "x"]) == cc.USAGE_RC


def test_a_message_file_is_read(fake, tmp_path):
    p = tmp_path / "COMMIT_EDITMSG"
    p.write_bytes(b"the guard lives in core/notes.md\n")
    assert cc.main(["--message-file", str(p), "--quiet"]) == cc.FAIL_RC


def test_an_unreadable_message_is_a_usage_error_not_a_pass(fake, tmp_path):
    """A checker that cannot read its input must not exit 0 - that is the
    'nothing ran' failure scripts/checked.py exists to separate."""
    missing = tmp_path / "nope" / "COMMIT_EDITMSG"
    assert cc.main(["--message-file", str(missing), "--quiet"]) == cc.USAGE_RC
