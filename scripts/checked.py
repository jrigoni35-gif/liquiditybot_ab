"""scripts/checked.py - run a command and refuse a LAUNDERED exit code.

WHY THIS EXISTS. An exit code that passed through a pipe belongs to the
filter, not the command - CLAUDE.md's reading discipline 7(d) says so, and the
repo has three dated incidents of it. Three more happened in one session
(2026-09-12/13), all mechanical:

  * `pytest ... ; git commit ...` - the `;` let a COMMIT THROUGH ON A RED TEST.
  * `RUFF=$?` placed after an intervening `echo`, capturing the echo.
  * `pytest -q | tail -6` - the failure NAMES were discarded above the window,
    so two failures could never be identified at all.

And the one that is not about shells: pytest exit 5 means NO TESTS COLLECTED.
`rc != 0` reads it as a failure and `rc == 0` never fires, so a filtered run
can report "caught" or "clean" when nothing ran.

This wrapper runs a command WITHOUT a shell, captures both streams in full,
and applies the rules that keep being re-learned:

  1. The exit code is the COMMAND's, never a pipeline's - there is no pipeline.
  2. pytest exit 5 is reported as NO-TESTS, distinct from both pass and fail.
  3. Output is never truncated by this tool. `--tail N` prints the last N
     lines but SAVES the whole capture and says where.
  4. `--expect` states what the caller believes, and a mismatch is an error.
     "I expected green" is a claim; this makes it a checked one.

Usage:
    python scripts/checked.py -- pytest tests/test_x.py -q
    python scripts/checked.py --expect green -- ruff check core
    python scripts/checked.py --expect red -- pytest tests/test_x.py -k pin
    python scripts/checked.py --tail 20 --save out.txt -- pytest tests/ -q

Exit: the command's own code, unless --expect is given and mismatched (2), or
a pytest run collected nothing (3).
"""
from __future__ import annotations

import argparse
import subprocess  # nosec B404 - running a command IS this tool's job
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

NO_TESTS_RC = 5
MISMATCH_RC = 2
NOTHING_RAN_RC = 3


def verdict(rc: int, is_pytest: bool) -> str:
    """green | red | no-tests. The three-way split is the point.

    A two-way rc==0/rc!=0 read cannot express "nothing ran", which is how a
    -k that selects nothing gets reported as a caught mutant.
    """
    if is_pytest and rc == NO_TESTS_RC:
        return "no-tests"
    return "green" if rc == 0 else "red"


def looks_like_pytest(argv: list) -> bool:
    return any("pytest" in str(a) for a in argv[:3])


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--expect", choices=("green", "red", "no-tests"),
                    help="what you believe will happen; mismatch is an error")
    ap.add_argument("--tail", type=int, default=12,
                    help="lines to PRINT (the full capture is always kept)")
    ap.add_argument("--save", help="write the full capture here")
    ap.add_argument("cmd", nargs=argparse.REMAINDER,
                    help="-- then the command")
    args = ap.parse_args(argv)

    cmd = [a for a in args.cmd if a != "--"]
    if not cmd:
        print("no command given (use: checked.py -- <cmd> ...)")
        return MISMATCH_RC
    if cmd[0] == "pytest":
        cmd = [sys.executable, "-m"] + cmd

    # nosec B603 - no shell, and that is the entire point of this file:
    # a shell is what turns an exit code into the filter's exit code. The
    # argv comes from this repo's own command line, never from a network
    # or a file.
    r = subprocess.run(cmd, cwd=str(REPO),  # nosec B603
                       capture_output=True, text=True)
    out = (r.stdout or "") + (r.stderr or "")
    lines = out.splitlines()

    save = Path(args.save) if args.save else None
    if save:
        save.parent.mkdir(parents=True, exist_ok=True)
        save.write_text(out, encoding="utf-8")

    is_pt = looks_like_pytest(cmd)
    v = verdict(r.returncode, is_pt)

    shown = lines[-args.tail:] if args.tail > 0 else lines
    for ln in shown:
        print(ln)
    if len(lines) > len(shown):
        where = f" (full capture: {save})" if save else \
                " (pass --save to keep the rest)"
        print(f"... {len(lines) - len(shown)} earlier lines NOT shown{where}")

    print(f"\n[checked] rc={r.returncode} verdict={v} "
          f"cmd={' '.join(str(c) for c in cmd[:6])}")

    if v == "no-tests":
        print("[checked] pytest collected NOTHING. This is not a pass and not "
              "a failure - a -k that selects no tests reports rc=5, and a "
              "harness reading `rc != 0` would call it a caught mutant.")

    if args.expect:
        if v != args.expect:
            print(f"[checked] EXPECTATION MISMATCH: expected {args.expect}, "
                  f"got {v}")
            return MISMATCH_RC
        print(f"[checked] expectation held: {v}")

    if v == "no-tests" and not args.expect:
        return NOTHING_RAN_RC
    return r.returncode


if __name__ == "__main__":
    raise SystemExit(main())
