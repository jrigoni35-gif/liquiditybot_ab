"""Pins for auto_update._dod_gates - the automated admission path.

CLAUDE.md's Definition of done names EIGHT commands. Until 2026-08-23 the
battery ran exactly ONE (pytest), so the law mandated a matrix the only
automated admission path never executed. Proven by mutation: deleting
`and liq_label != "spoofy" ` from execution/tactics.py made assurance_check
FAIL rc=1 while the battery still returned green.

What these tests defend is not "more gates ran" - it is the SPLIT, because a
naive fix here has already bricked this box twice:

  HARD     pure functions of the INCOMING CODE. A commit that repairs a ruff
           error passes ruff, so a hard verdict can never refuse its own fix.
  ADVISORY corpus-dependent. If the CORPUS degrades no code change repairs
           it, so blocking would refuse every update forever - the shape
           refused as OBJ-16 and lived on 2026-07-21/22 and 2026-08-01.

and two traps that are easy to reintroduce:
  * a MISSING TOOL is not a finding about the incoming code
  * the blocking assurance run must not inherit LB_OUTPUTS, or it silently
    becomes corpus-dependent again
"""
from __future__ import annotations

import scripts.auto_update as au


def test_dod_names_the_gates_the_law_names():
    hard = {n for n, _ in au._HARD_GATES}
    adv = {n for n, _ in au._ADVISORY_GATES}
    # the four pure-code gates from CLAUDE.md's DoD
    assert {"ruff", "compileall", "bandit", "smoke"} <= hard
    # assurance runs BOTH ways: blocking on its code-only subset, advisory
    # with the live corpus pinned
    assert "assurance-code" in hard
    assert "assurance-corpus" in adv
    assert "overfit" in adv


def test_hard_gate_failure_blocks_the_update(monkeypatch):
    calls = []

    def fake(worktree, py, argv, env, secs):
        calls.append(argv)
        if "scripts/assurance_check.py" in argv:
            return 1, "47 passed, 1 failed", False
        return 0, "ok", False

    monkeypatch.setattr(au, "_run_gate", fake)
    monkeypatch.setattr(au, "log", lambda m: None)
    assert au._dod_gates(au.ROOT, "py") is False
    assert "assurance-code" in au._BATTERY_DETAIL


def test_advisory_failure_does_NOT_block(monkeypatch):
    """A degraded corpus must never refuse the fix that repairs it."""
    def fake(worktree, py, argv, env, secs):
        if env.get("LB_OUTPUTS"):          # the advisory, corpus-pinned pass
            return 1, "corpus is a disaster", False
        return 0, "ok", False

    monkeypatch.setattr(au, "_run_gate", fake)
    monkeypatch.setattr(au, "log", lambda m: None)
    assert au._dod_gates(au.ROOT, "py") is True


def test_missing_tool_is_advisory_not_a_rejection(monkeypatch):
    """"ruff is not installed" is not a finding about the incoming code.
    Treating it as one is how the replay gate bricked deploys."""
    def fake(worktree, py, argv, env, secs):
        if "ruff" in argv:
            return 1, "No module named ruff", True     # could_not_run
        return 0, "ok", False

    monkeypatch.setattr(au, "_run_gate", fake)
    monkeypatch.setattr(au, "log", lambda m: None)
    assert au._dod_gates(au.ROOT, "py") is True


def test_blocking_run_cannot_inherit_a_corpus(monkeypatch):
    """LB_OUTPUTS in the ambient environment must not smuggle a live corpus
    into the HARD run - that would make the blocking verdict
    corpus-dependent again, which is the whole thing this split avoids."""
    monkeypatch.setenv("LB_OUTPUTS", r"C:\somewhere\live\outputs")
    seen = {}

    def fake(worktree, py, argv, env, secs):
        key = "advisory" if env.get("LB_OUTPUTS") else "hard"
        seen.setdefault(key, []).append(argv)
        return 0, "ok", False

    monkeypatch.setattr(au, "_run_gate", fake)
    monkeypatch.setattr(au, "log", lambda m: None)
    au._dod_gates(au.ROOT, "py")
    hard_argvs = seen.get("hard", [])
    assert hard_argvs, "hard gates must run with LB_OUTPUTS cleared"
    assert ["scripts/assurance_check.py"] in hard_argvs
    # and the advisory pass must still carry a pinned corpus
    assert ["scripts/assurance_check.py"] in seen.get("advisory", [])


def test_advisory_pins_the_corpus_to_the_live_tree(monkeypatch):
    got = {}

    def fake(worktree, py, argv, env, secs):
        if env.get("LB_OUTPUTS"):
            got["corpus"] = env["LB_OUTPUTS"]
        return 0, "ok", False

    monkeypatch.setattr(au, "_run_gate", fake)
    monkeypatch.setattr(au, "log", lambda m: None)
    au._dod_gates(au.ROOT, "py")
    assert got.get("corpus") == str(au.OUT.resolve())


def test_run_gate_never_raises_on_a_spawn_failure(monkeypatch):
    """A spawn crash must return could_not_run, not propagate - the replay
    gate's 'could not run -> refusing the update' froze deploys for 19h."""
    def boom(*a, **k):
        raise OSError("spawn exploded")

    monkeypatch.setattr(au.subprocess, "run", boom)
    rc, tail, missing = au._run_gate(au.ROOT, "py", ["-c", "pass"], {}, 5)
    assert missing is True
    assert "could not run" in tail
