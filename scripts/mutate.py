"""scripts/mutate.py - plant a defect, watch the pin go red, restore.

WHY THIS EXISTS. `docs/INSTRUMENT_VERIFICATION_STANDARD.md` check 2 says
"green tests are not evidence until the suite is shown to fail... plant a
defect, watch the pin go red, restore byte-identically, report the table."
That standard is PROSE, so every caller hand-rolls the harness. Roughly thirty
test files record in docstrings that mutation was done; none shares code.

Hand-rolling it produced two measured failures in one session (2026-09-12/13):

  * A run reported CAUGHT that was really **pytest exit 5 - no tests
    collected**, because `-k` selected pins that did not exist yet. Exit 5 and
    a real red are the same observation until separated, and `rc != 0` does
    not separate them.
  * A crashed harness left a mutant on disk (2026-09-07), because restore was
    not in a `finally`.

Both are mechanical, so they belong in code, not in a memory. This module is
the one place that knows:

  1. BASELINE MUST BE GREEN FIRST. Mutating a red suite proves nothing.
  2. THE PIN MUST SELECT SOMETHING. A selection pre-check runs before every
     mutant and refuses exit 5, so "the pin does not exist" can never read as
     "the pin caught it".
  3. RESTORE IN `finally`, THEN VERIFY THE BYTES. sha256 before and after; a
     mismatch is a hard failure, not a warning.
  4. A SURVIVING MUTANT IS A NON-ZERO EXIT. A harness that reports a decorative
     pin and exits 0 is itself a decorative pin.

Usage:
    python scripts/mutate.py --test tests/test_foo.py \\
        --mutant "core/foo.py :: old text :: new text :: pin_substring" \\
        --mutant "core/bar.py :: a :: b :: other_pin"

    python scripts/mutate.py --spec mutants.json      # same, from a file

Exit: 0 every mutant caught; 1 any survived, any restore mismatch, or the
baseline was not green.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import subprocess  # nosec B404 - running pytest IS this tool's job
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SEP = "::"

CAUGHT = "CAUGHT"
SURVIVED = "SURVIVED"
NOT_SELECTED = "PIN-NOT-SELECTED"
NEEDLE_ABSENT = "NEEDLE-ABSENT"
RESTORE_FAILED = "RESTORE-FAILED"
AMBIGUOUS = "AMBIGUOUS-NEEDLE"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _drop_pyc(path: Path) -> None:
    """Delete cached bytecode for a file we just rewrote.

    WHY, and this is the subtlest failure in the whole module. CPython decides
    a .pyc is current from (source mtime, source size) at 1-second
    granularity. A mutation like `return 1` -> `return 2` is the SAME SIZE,
    and plant+restore usually land in the SAME SECOND - so after a
    byte-identical restore the stale .pyc still validates and the interpreter
    KEEPS RUNNING THE MUTANT. Measured here: a restored tree whose suite was
    still red, with sha256 matching.

    That makes every verdict from a naive harness suspect in both directions -
    a later mutant can be scored against the previous mutant's bytecode. Every
    hand-rolled harness in this session had this hole.
    """
    try:
        import importlib.util as _ilu
        cached = _ilu.cache_from_source(str(path))
        Path(cached).unlink(missing_ok=True)
    except (OSError, ValueError, ImportError):      # pragma: no cover
        pass
    # belt and braces: a sibling __pycache__ entry under any tag
    try:
        pd = path.parent / "__pycache__"
        if pd.is_dir():
            for f in pd.glob(path.stem + ".*.pyc"):
                f.unlink(missing_ok=True)
    except OSError:                                  # pragma: no cover
        pass


_LOCK_REL = "outputs/.mutating"


def lock_path() -> Path:
    """Derived from REPO at CALL time, never frozen at import.

    tests/conftest.py fails any test that writes into the production
    `outputs/` tree, and it is right to: a test that scribbles there is
    indistinguishable from the bot doing it. A module-level constant would
    have meant every CLI pin here wrote a real lock file into the live tree -
    the guard caught exactly that on the first run. Deriving it from REPO
    means the redirect the tests ALREADY do moves the lock with it, which is
    the fix that guard's own docstring asks for: point the path at tmp_path,
    do not widen the allowlist.
    """
    return REPO / _LOCK_REL
MUTATION_ENV = "LIQBOT_MUTATION_RUN"
_LOCK_STALE_SEC = 3600.0


def lock_held_by_other() -> str:
    """Non-empty reason if another mutation run owns the tree right now.

    WHY A LOCK AT ALL. This harness EDITS FILES IN THE WORKING TREE and
    restores them. Anything else reading the repo while that is true gets
    garbage, in both directions: the other reader fails on code nobody wrote,
    and this harness scores a verdict against a tree someone else is changing.

    MEASURED 2026-09-13, on the author, within an hour of writing the sweep: a
    full `pytest tests/` run and a `mutation_sweep --all` smoke test overlapped
    for a few seconds. tests/test_probe_budget.py failed on a mutant planted in
    core/audit.py, the suite reported 1 failed / 5365 passed, and the test
    passed in isolation immediately afterwards. Nothing in either tool said a
    word. A silent corruption that looks exactly like a real failure is the
    worst artifact this repo can produce, so it is now loud.
    """
    try:
        raw = lock_path().read_text(encoding="utf-8").strip()
    except OSError:
        return ""
    try:
        pid_s, ts_s = raw.split(None, 1)
        age = time.time() - float(ts_s)
    except ValueError:
        return f"a malformed lock at {lock_path()}"
    if age > _LOCK_STALE_SEC:
        return ""                      # stale: a crashed run, take the tree
    return (f"pid {pid_s} has been mutating this tree for {age:.0f}s "
            f"({lock_path()})")


@contextlib.contextmanager
def tree_lock():
    """Own the working tree for the duration of a mutation run."""
    reason = lock_held_by_other()
    if reason:
        raise RuntimeError(
            f"REFUSING TO MUTATE: {reason}. Two mutation runs on one tree "
            f"score each other's edits. Wait, or delete the lock if that run "
            f"is dead.")
    lk = lock_path()
    lk.parent.mkdir(parents=True, exist_ok=True)
    lk.write_text(f"{os.getpid()} {time.time()}", encoding="utf-8")
    print(f"[mutate] THE WORKING TREE IS BEING MUTATED ({lk}).")
    print("[mutate] Do not run tests, builds or git operations against this "
          "repo until this finishes.")
    try:
        yield
    finally:
        lk.unlink(missing_ok=True)


def _pytest(test: str, k: str = "") -> tuple:
    """Return (rc, last_line). rc 5 means NO TESTS COLLECTED, which is the
    single most important distinction this module exists to make."""
    cmd = [sys.executable, "-m", "pytest", test, "-q"]
    if k:
        cmd += ["-k", k]
    # nosec B603 - argv is built here from a repo-relative
    # test path and sys.executable; no shell, no user input.
    # The child pytest runs WHILE the lock is held - by design, it is this
    # harness's own measurement. conftest.py refuses a locked tree unless this
    # marker is set, so the guard stops everyone EXCEPT the tool that took the
    # lock.
    env = dict(os.environ, **{MUTATION_ENV: "1"})
    r = subprocess.run(  # nosec B603
        cmd, cwd=str(REPO), capture_output=True, text=True, env=env)
    out = (r.stdout or "").strip().splitlines()
    return r.returncode, (out[-1] if out else "")


def parse_mutant(spec: str) -> dict:
    """`path :: old :: new :: pin` -> dict. Whitespace around SEP is stripped,
    which is why `old`/`new` must not rely on leading or trailing spaces."""
    parts = [p.strip() for p in spec.split(SEP)]
    if len(parts) != 4:
        raise ValueError(
            f"expected 4 {SEP}-separated fields (path{SEP}old{SEP}new{SEP}pin),"
            f" got {len(parts)}: {spec!r}")
    path, old, new, pin = parts
    if not path or not old or not pin:
        raise ValueError(f"path, old and pin must be non-empty: {spec!r}")
    if old == new:
        raise ValueError(f"old == new is not a mutation: {spec!r}")
    return {"path": path, "old": old, "new": new, "pin": pin}


def classify(rc_selected: int, rc_mutated: int) -> str:
    """The whole point of this module.

    A pin that selects nothing returns 5 both times, and `rc != 0` would read
    that as CAUGHT. It is not a result at all.
    """
    if rc_selected == 5:
        return NOT_SELECTED
    if rc_mutated == 5:
        return NOT_SELECTED
    return CAUGHT if rc_mutated != 0 else SURVIVED


def run_one(m: dict, test: str, verbose: bool = True) -> dict:
    path = REPO / m["path"]
    res = dict(m, verdict=None, detail="")
    if not path.is_file():
        res["verdict"] = NEEDLE_ABSENT
        res["detail"] = f"no such file: {m['path']}"
        return res

    rc_sel, sel_line = _pytest(test, m["pin"])
    if rc_sel == 5:
        res["verdict"] = NOT_SELECTED
        res["detail"] = f"-k {m['pin']!r} selected no tests ({sel_line})"
        return res
    if rc_sel != 0:
        res["verdict"] = SURVIVED
        res["detail"] = f"pin is ALREADY red before mutating ({sel_line})"
        return res

    # BYTES, NOT TEXT, ON BOTH SIDES. Reading with universal newlines and
    # writing back with newline="" silently rewrites CRLF as LF, so `restore`
    # would not restore - it would normalise line endings on every file the
    # harness touched. Caught by this module's own byte-identity pin, which is
    # the outcome the standard's check 2 is for. On a repo whose files are
    # already LF the mismatch is invisible, which is exactly why it needs a
    # test rather than a code read.
    raw = path.read_bytes()
    before = _sha(path)
    try:
        original = raw.decode("utf-8")
    except UnicodeDecodeError:
        res["verdict"] = NEEDLE_ABSENT
        res["detail"] = f"{m['path']} is not utf-8 text"
        return res
    if m["old"] not in original:
        res["verdict"] = NEEDLE_ABSENT
        res["detail"] = f"old text not found in {m['path']}"
        return res

    # A NEEDLE THAT MATCHES MORE THAN ONCE IS REFUSED, not planted at the
    # first hit. This harness exists because hand-rolled copies scored
    # verdicts against the wrong edit, and `replace(old, new, 1)` is another
    # way to do exactly that: the plant lands somewhere the author did not
    # mean, the pin does not fire, and the run reports SURVIVED - a clean
    # blind-spot claim about code that was never touched.
    #
    # MEASURED 2026-09-13. Injecting `"ADA/USD",` into config.json to test a
    # watch-lane pin landed on skimmer.candidates (line 1132) instead of
    # watch_lane.pairs (line 1378) - the same string, two blocks apart - and
    # the harness reported SURVIVED for a pin whose input never changed.
    # build_mutants() in scripts/mutation_sweep.py already refuses ambiguous
    # anchors; a hand-written --mutant spec was getting no such check.
    hits = original.count(m["old"])
    if hits != 1:
        res["verdict"] = AMBIGUOUS
        res["detail"] = (f"old text occurs {hits}x in {m['path']} - refusing "
                         f"to guess which. Extend the needle until unique.")
        return res

    try:
        path.write_bytes(
            original.replace(m["old"], m["new"], 1).encode("utf-8"))
        _drop_pyc(path)          # same reason as on restore, other direction
        rc_mut, mut_line = _pytest(test, m["pin"])
        res["verdict"] = classify(rc_sel, rc_mut)
        res["detail"] = mut_line
    finally:
        # ALWAYS, on every path including KeyboardInterrupt - a crashed
        # harness left a mutant on disk on 2026-09-07.
        path.write_bytes(raw)
        _drop_pyc(path)
        if _sha(path) != before:
            res["verdict"] = RESTORE_FAILED
            res["detail"] = "sha256 differs after restore"
    if verbose:
        print(f"  {res['verdict']:<18} {m['path']} :: {m['pin']}")
        if res["detail"]:
            print(f"    {res['detail'][:100]}")
    return res


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--test", required=True, help="test file or node id")
    ap.add_argument("--mutant", action="append", default=[],
                    help=f"'path {SEP} old {SEP} new {SEP} pin', repeatable")
    ap.add_argument("--spec", help="JSON file: [{path, old, new, pin}, ...]")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)

    mutants = [parse_mutant(s) for s in args.mutant]
    if args.spec:
        mutants += json.loads(Path(args.spec).read_text(encoding="utf-8"))
    if not mutants:
        print("no mutants given")
        return 1

    try:
        lock = tree_lock()
        lock.__enter__()
    except RuntimeError as exc:
        print(f"[mutate] {exc}")
        return 2

    try:
        return _run_all(args, mutants)
    finally:
        lock.__exit__(None, None, None)


def _run_all(args, mutants) -> int:
    rc, line = _pytest(args.test)
    print(f"BASELINE  {args.test}  rc={rc}  {line}")
    if rc != 0:
        print("  baseline is NOT green - mutating a red suite proves nothing")
        return 1

    print(f"\n{len(mutants)} mutant(s):")
    results = [run_one(m, args.test, verbose=not args.quiet)
               for m in mutants]

    rc, line = _pytest(args.test)
    print(f"\nRESTORED  rc={rc}  {line}")
    if rc != 0:
        print("  suite is RED after restore - the tree was not put back")
        return 1

    bad = [r for r in results if r["verdict"] != CAUGHT]
    print(f"\n{len(results) - len(bad)}/{len(results)} caught")
    if bad:
        for r in bad:
            print(f"  !! {r['verdict']}: {r['path']} :: {r['pin']}"
                  f"{' - ' + r['detail'] if r['detail'] else ''}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
