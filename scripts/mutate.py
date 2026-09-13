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
import hashlib
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SEP = "::"

CAUGHT = "CAUGHT"
SURVIVED = "SURVIVED"
NOT_SELECTED = "PIN-NOT-SELECTED"
NEEDLE_ABSENT = "NEEDLE-ABSENT"
RESTORE_FAILED = "RESTORE-FAILED"


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


def _pytest(test: str, k: str = "") -> tuple:
    """Return (rc, last_line). rc 5 means NO TESTS COLLECTED, which is the
    single most important distinction this module exists to make."""
    cmd = [sys.executable, "-m", "pytest", test, "-q"]
    if k:
        cmd += ["-k", k]
    r = subprocess.run(cmd, cwd=str(REPO), capture_output=True, text=True)
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
