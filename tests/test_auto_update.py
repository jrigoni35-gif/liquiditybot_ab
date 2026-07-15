"""tests/test_auto_update.py — the test-gated self-updater's decision core.

decide() is the whole safety gate expressed as pure logic, so it is the piece
worth pinning: a bad branch here is the difference between "protect the
operator's local config edits" and "silently clobber them," or between "only
touch the live checkout after the incoming code is battery-green" and "pull
blindly." The subprocess/worktree plumbing is exercised live on the PC; this
locks the branch table.
"""
from scripts.auto_update import decide


def test_no_remote_is_current():
    # offline / failed rev-parse -> empty remote -> never act
    assert decide("abc123", "", False) == "current"


def test_equal_heads_is_current():
    assert decide("abc123", "abc123", False) == "current"


def test_equal_heads_current_even_when_dirty():
    # nothing to pull -> local edits are irrelevant, no action
    assert decide("abc123", "abc123", True) == "current"


def test_new_commits_clean_tree_gates_on_battery():
    assert decide("abc123", "def456", False) == "test"


def test_new_commits_dirty_tree_is_skipped():
    # operator has uncommitted edits (e.g. the debug flag) -> protect them
    assert decide("abc123", "def456", True) == "dirty"
