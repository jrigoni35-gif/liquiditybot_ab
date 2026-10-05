"""tests/test_conftest_harness.py - pins for the Windows harness fixes in
tests/conftest.py (2026-10-04). Both patch the HARNESS, not the bot: each
one exists because the battery reported red over a passing suite.

1. _tolerant_cleanup_dead_symlinks replaces a PRIVATE pytest function. If a
   pytest upgrade stops calling it through that module global, the patch
   silently stops applying and the session-end crash returns - so pin the
   hook point, not just the assignment.
2. _git_longpaths_on_windows must actually reach git during the session.
"""
import os
import pathlib
import random
import shutil
import subprocess  # nosec B404 - fixed argv, no shell
import sys

import _pytest.pathlib as pytest_pathlib
import pytest


def test_pytest_still_calls_the_cleanup_the_conftest_replaces():
    assert "cleanup_dead_symlinks" in pytest_pathlib.cleanup_numbered_dir.__code__.co_names, (
        "pytest no longer calls cleanup_dead_symlinks from cleanup_numbered_dir; "
        "re-check the conftest patch against the installed pytest")


def test_the_tolerant_cleanup_is_installed():
    assert pytest_pathlib.cleanup_dead_symlinks.__name__ == "_tolerant_cleanup_dead_symlinks"


def test_git_sees_longpaths_during_the_session_on_windows():
    if os.name != "nt":                       # the fixture is a no-op off Windows
        assert "gitcfg" not in os.environ.get("GIT_CONFIG_GLOBAL", "")
        return
    git = shutil.which("git")
    assert os.environ.get("GIT_CONFIG_GLOBAL"), "session git config not installed"
    if git is not None:
        out = subprocess.run([git, "config", "--global", "--get", "core.longpaths"],  # nosec B603
                             capture_output=True, text=True, check=False)
        assert out.stdout.strip() == "true", out


# ===========================================================================
# THE REFUSAL POLICY, SCRUTINIZED BY A MARKOV CHAIN BUILT FOR ITS OWN LINES
# (operator, 2026-10-04: "consistently scrutinized by my Markov chains,
#  specifically built for that line of code")
#
# Two kinds of session touch %TEMP%/pytest-of-<user>: E, the PC's elevated
# scheduled runs, which can create and remove links; N, ordinary runs, which
# can do neither (WinError 1314 / 5, measured 2026-10-04). Each session makes
# one numbered dir and pytest keeps the newest KEEP; at start an E session
# repoints `pytest-current` at its own new dir (pytest 9.1.1 _force_symlink,
# errors swallowed), an N session cannot. So the link is NONE, LIVE k (k dirs
# newer than its target) or DEAD: a finite Markov chain whose states are the
# branches of _tolerant_cleanup_dead_symlinks - none/live -> skip; dead and
# unlink allowed -> the unlink line; unlink refused, rmdir allowed -> the
# rmdir line; both refused -> the warning line.
#
# NOT measured on this box: whether even an ELEVATED unlink removes a
# directory link. H1 says it cannot - then the rmdir line is the only thing
# that ever frees the link, and pytest's own cleanup crashes elevated runs
# (the deploy battery) too. Every assertion runs in both worlds.
#
# The chain drives the REAL functions and reads its next state back from the
# filesystem: what the code did, not what the model assumed. Only the
# filesystem's answers are injected (an N session cannot make a real link).
# The control arm is pytest's own function: it must crash where the tolerant
# one must not, at the rate the chain's stationary distribution predicts.
# A scan that cannot crash proves nothing by reading zero.
# ===========================================================================

KEEP = 3                       # pytest tmp_path_retention_count default; pyproject sets none
NONE, DEAD = "none", "dead"    # LIVE states are ints: dirs newer than the link's target
WORLDS = pytest.mark.parametrize("h1", [False, True],
                                 ids=["unlink-frees-dir-links", "H1-only-rmdir-frees"])


def _conftest_module():
    return next(m for n, m in sys.modules.items()
                if n.endswith("conftest") and hasattr(m, "_tolerant_cleanup_dead_symlinks"))


@pytest.fixture()
def injected_link(tmp_path, monkeypatch):
    """A temp root with one real numbered dir and a placeholder named
    pytest-current whose answers - link? dead? removable? - come from `fs`."""
    root = tmp_path / "pytest-of-x"
    (root / "pytest-7").mkdir(parents=True)
    link = root / "pytest-current"
    link.write_text("placeholder", encoding="utf-8")
    fs = {"kind": "dead", "unlink": "refuse", "rmdir": "refuse"}
    real_is_symlink, real_resolve = pathlib.Path.is_symlink, pathlib.Path.resolve
    real_unlink, real_rmdir = pathlib.Path.unlink, os.rmdir

    def is_symlink(self):
        return self == link or real_is_symlink(self)

    def resolve(self, *a, **k):
        if self != link:
            return real_resolve(self, *a, **k)
        if fs["kind"] == "unresolvable":
            raise PermissionError(13, "Access is denied")
        return root / ("pytest-7" if fs["kind"] == "live" else "pytest-gone")

    def unlink(self, *a, **k):
        if self == link and fs["unlink"] != "ok":
            raise PermissionError(13, "Access is denied")
        return real_unlink(self, *a, **k)

    def rmdir(path, *a, **k):
        if pathlib.Path(path) != link:
            return real_rmdir(path, *a, **k)
        if fs["rmdir"] != "ok":
            raise PermissionError(13, "Access is denied")
        os.remove(link)          # rmdir of a directory LINK removes the link itself

    monkeypatch.setattr(pathlib.Path, "is_symlink", is_symlink)
    monkeypatch.setattr(pathlib.Path, "resolve", resolve)
    monkeypatch.setattr(pathlib.Path, "unlink", unlink)
    monkeypatch.setattr(os, "rmdir", rmdir)
    return root, link, fs


@pytest.mark.parametrize("kind", ["live", "dead", "unresolvable"])
@pytest.mark.parametrize("removal", ["unlink_ok", "rmdir_ok", "refused"])
def test_every_branch_over_every_link_state(injected_link, capsys, kind, removal):
    """Exhaustive enumeration of the finite domain: 3 link states x 3 answers."""
    root, link, fs = injected_link
    fs.update(kind=kind, unlink="ok" if removal == "unlink_ok" else "refuse",
              rmdir="ok" if removal == "rmdir_ok" else "refuse")
    _conftest_module()._tolerant_cleanup_dead_symlinks(root)        # never raises
    err = capsys.readouterr().err
    assert (root / "pytest-7").is_dir(), "a real numbered dir was touched"
    if kind != "dead":                                   # not provably dead: left alone
        assert link.exists() and not err
    elif removal == "refused":                           # stranded: kept, named, fix given
        assert link.exists() and str(link) in err and 'rmdir "' in err
    else:                                                # freed by unlink or by rmdir
        assert not link.exists() and not err


def _start_and_prune(state, elevated, h1):
    """One session of pytest 9.1.1, up to the moment cleanup_dead_symlinks runs."""
    if isinstance(state, int):
        state += 1                     # this session's numbered dir ages the target
    if elevated and (state == NONE or not h1):
        state = 0                      # E repoints the link at its own new dir
    if isinstance(state, int) and state >= KEEP:
        state = DEAD                   # target fell out of the newest KEEP: pruned
    return state


def _after_cleanup(mid, elevated, h1, policy):
    """(next state, crashed) - the chain's model of the cleanup step."""
    if mid != DEAD:
        return mid, False
    if not elevated:                   # N may not remove an E-made link
        return DEAD, policy == "pytest"
    if h1 and policy == "pytest":      # elevated unlink refused, no rmdir fallback
        return DEAD, True
    return NONE, False                 # unlink - or, under H1, the rmdir line - frees it


def _exact_meet_rates(p_e, h1, policy):
    """Stationary P(cleanup meets a dead link | E) and (| N), by power iteration."""
    states = [NONE, *range(KEEP), DEAD]
    pi = dict.fromkeys(states, 1.0 / len(states))
    for _ in range(400):
        nxt = dict.fromkeys(states, 0.0)
        for s, w in pi.items():
            for e, pw in ((True, p_e), (False, 1.0 - p_e)):
                nxt[_after_cleanup(_start_and_prune(s, e, h1), e, h1, policy)[0]] += w * pw
        pi = nxt
    return {e: sum(w for s, w in pi.items() if _start_and_prune(s, e, h1) == DEAD)
            for e in (True, False)}


def _drive(cleanup, injected, h1, p_e=0.2, sessions=12000, seed=7):
    """Run the chain with the REAL cleanup in every session."""
    root, link, fs = injected
    rng, state = random.Random(seed), DEAD             # the state the box was found in
    n, met, crashed = {True: 0, False: 0}, {True: 0, False: 0}, {True: 0, False: 0}
    for _ in range(sessions):
        e = rng.random() < p_e
        n[e] += 1
        state = _start_and_prune(state, e, h1)
        if state != NONE and not link.exists():
            link.write_text("placeholder", encoding="utf-8")
        elif state == NONE and link.exists():
            os.remove(link)
        fs.update(kind="dead" if state == DEAD else "live",
                  unlink="ok" if e and not h1 else "refuse",
                  rmdir="ok" if e else "refuse")
        met[e] += int(state == DEAD)
        try:
            cleanup(root)
        except OSError:
            crashed[e] += 1
        if state == DEAD and not link.exists():
            state = NONE                               # the code under test freed it
    return n, met, crashed


def _assert_rates_match_the_chain(n, met, h1, policy):
    exact = _exact_meet_rates(0.2, h1, policy)
    for e in (True, False):
        assert abs(met[e] / n[e] - exact[e]) < 0.03, (policy, e, met[e] / n[e], exact[e])


@WORLDS
def test_markov_chain_tolerant_cleanup_never_crashes(injected_link, capsys, h1):
    n, met, crashed = _drive(_conftest_module()._tolerant_cleanup_dead_symlinks,
                             injected_link, h1)
    assert crashed == {True: 0, False: 0}
    assert met[False] > 0 and (met[True] > 0) == h1   # warning line always; rmdir line iff H1
    assert capsys.readouterr().err.count('rmdir "') == met[False]   # one per stranded N session
    _assert_rates_match_the_chain(n, met, h1, "tolerant")


@WORLDS
def test_markov_chain_pytest_cleanup_crashes_where_the_chain_predicts(injected_link, h1):
    n, met, crashed = _drive(pytest_pathlib._lb_original_cleanup_dead_symlinks,
                             injected_link, h1)
    assert crashed[False] == met[False] > 0          # every stranded N session crashed
    assert crashed[True] == (met[True] if h1 else 0)  # elevated runs crash only under H1
    _assert_rates_match_the_chain(n, met, h1, "pytest")
