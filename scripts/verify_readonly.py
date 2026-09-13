"""scripts/verify_readonly.py - does this script actually write anything?

WHY THIS EXISTS. "Read-only" is one of the most-repeated claims in this repo's
tooling, and it is normally established by GREPPING THE SOURCE for `open(`,
`.write(` and friends. That method failed on 2026-09-13: a grep over
`scripts/horizon_report.py` found no write path, the script was declared
read-only in prose, and it then wrote `outputs/horizon_report.txt`. The grep
missed it because the write went through a helper the pattern did not name.

A source scan answers "does this text contain a write call". The question is
"does running this change the tree", and only running it answers that. So this
takes a filesystem census before and after and DIFFERS it - no patterns, no
guessing which helper wraps the write.

WHAT IT WATCHES. By default `outputs/` plus the repo root's tracked files.
The census records (path, size, mtime_ns, sha256-of-first-64KB) so a rewrite
that preserves size and mtime is still caught - the case a naive
mtime-only census misses, and the same 1-second-granularity trap that let a
stale .pyc survive a byte-identical restore in scripts/mutate.py.

IT RUNS THE SCRIPT FOR REAL. There is no sandbox: if the subject writes, the
write happens and this tool reports it. Use it on a copy, or accept the write.
That is stated plainly rather than implied - a tool that claims to prove
read-only-ness by executing a possible writer must not pretend otherwise.

Usage:
    python scripts/verify_readonly.py -- python scripts/horizon_report.py
    python scripts/verify_readonly.py --watch outputs --watch docs -- <cmd>

Exit: 0 nothing changed, 1 something did, 2 the subject itself failed.
"""
from __future__ import annotations

import argparse
import hashlib
import subprocess  # nosec B404 - running a command IS this tool's job
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
_HEAD_BYTES = 64 * 1024
_SKIP_DIRS = {"__pycache__", ".git", ".venv", "node_modules", ".pytest_cache"}


def _fingerprint(p: Path) -> tuple:
    """(size, mtime_ns, sha of the first 64KB).

    The hash is what makes this better than an mtime census: a rewrite inside
    the same second that preserves length is invisible to mtime+size alone,
    and that exact combination is how a stale .pyc survived a restore
    elsewhere in this repo.
    """
    st = p.stat()
    h = ""
    try:
        with open(p, "rb") as fh:
            h = hashlib.sha256(fh.read(_HEAD_BYTES)).hexdigest()[:16]
    except OSError:
        pass
    return (st.st_size, st.st_mtime_ns, h)


def _label(p) -> str:
    """Repo-relative where possible, absolute otherwise.

    `--watch` accepts any path, so a watched tmp dir is not under REPO and
    `relative_to` raises. That crash would land ONLY on the reporting line -
    i.e. only when the tool has something to say - which is the worst place
    for a bug: the census works, and the exception appears exactly when a
    write was found. tests/test_docs_era_currency.py's `_label` carries the
    same lesson from the same mistake.
    """
    try:
        return str(Path(p).relative_to(REPO))
    except ValueError:
        return str(p)


def census(roots: list) -> dict:
    out: dict = {}
    for root in roots:
        base = REPO / root
        if not base.exists():
            continue
        if base.is_file():
            out[str(base)] = _fingerprint(base)
            continue
        for p in base.rglob("*"):
            if any(part in _SKIP_DIRS for part in p.parts):
                continue
            if p.is_file():
                try:
                    out[str(p)] = _fingerprint(p)
                except OSError:
                    pass
    return out


def diff(before: dict, after: dict) -> dict:
    created = sorted(set(after) - set(before))
    deleted = sorted(set(before) - set(after))
    modified = sorted(k for k in set(before) & set(after)
                      if before[k] != after[k])
    return {"created": created, "deleted": deleted, "modified": modified}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--watch", action="append", default=[],
                    help="path to census, repeatable (default: outputs)")
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("cmd", nargs=argparse.REMAINDER)
    args = ap.parse_args(argv)

    cmd = [a for a in args.cmd if a != "--"]
    if not cmd:
        print("no command given (use: verify_readonly.py -- <cmd> ...)")
        return 2
    if cmd[0] == "python":
        cmd = [sys.executable] + cmd[1:]

    roots = args.watch or ["outputs"]
    before = census(roots)
    if not args.quiet:
        print(f"census: {len(before)} files under {roots}")

    # nosec B603 - the subject command is supplied by the operator on this
    # tool's own command line. Running it for real is the method: a source
    # scan is exactly what failed on scripts/horizon_report.py.
    r = subprocess.run(cmd, cwd=str(REPO),  # nosec B603
                       capture_output=True, text=True)
    after = census(roots)
    d = diff(before, after)

    n = sum(len(v) for v in d.values())
    if not args.quiet:
        tail = ((r.stdout or "") + (r.stderr or "")).strip().splitlines()[-3:]
        for ln in tail:
            print(f"  | {ln[:110]}")
        print(f"\n[readonly] subject rc={r.returncode}")

    if r.returncode != 0:
        print(f"[readonly] THE SUBJECT FAILED (rc={r.returncode}) - a crashed "
              f"script that wrote nothing is not evidence of read-only-ness")
        if n == 0:
            return 2

    if n == 0:
        print(f"[readonly] VERIFIED: nothing under {roots} changed")
        return 0

    print(f"[readonly] NOT read-only - {n} change(s):")
    for kind in ("created", "modified", "deleted"):
        for p in d[kind][:12]:
            print(f"    {kind:<9} {_label(p)}")
        if len(d[kind]) > 12:
            print(f"    {kind:<9} ... and {len(d[kind]) - 12} more")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
