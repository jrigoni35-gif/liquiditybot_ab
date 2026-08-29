"""
scripts/candle_store_resolve.py — OPERATOR-INVOKED conflict resolution.

THE ONE PATH IN THIS BUILD THAT REWRITES AN EXISTING BYTE. Every other
code path is strictly append-only: no rotation, no truncation, no rename.
This script exists because a venue can legitimately CORRECT a bar, and
first-committed-wins would otherwise pin the store to the wrong value
forever with no escape hatch.

It follows the repo's migration discipline exactly
(scripts/migrate_fills_schema.py — "resolve by hand, never by overwrite"):

  * --dry-run IS THE DEFAULT. Nothing is written without --apply.
  * A `.preschema_<ts>` COPY of every segment it touches is made BEFORE
    any write, with shutil.copy2 (a copy, not a rename - the original
    segment keeps its name and its place in the read order).
  * It REFUSES anything it cannot interpret: a segment whose header is not
    the schema, a key whose conflict set it cannot pair up, a schema
    generation newer than this code. It never guesses.
  * It never invents a value. Resolution only changes WHICH already-stored
    row is authoritative, by flipping `record_kind` between BAR and
    CONFLICT. Both values stay on disk, so the disagreement remains
    auditable after the decision.

Usage:
    python scripts/candle_store_resolve.py                       # list
    python scripts/candle_store_resolve.py --accept latest --apply
    python scripts/candle_store_resolve.py --symbol ETH --interval 300 \\
        --accept latest --apply
"""

from __future__ import annotations

import argparse
import csv
import shutil
import sys
import time
from pathlib import Path
from typing import Sequence

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from data import candle_journal as cj             # noqa: E402

_KEY = ("symbol", "interval_s", "source", "quote", "t_open_s")


def _load(root: Path | str | None) -> list[tuple[Path, int, int, dict]]:
    """(segment, version, line index within the segment, row) for all bars."""
    out: list[tuple[Path, int, int, dict]] = []
    for path, version in cj._segments(cj.journal_dir(root)):
        rows = cj._read_segment(path, version, cj._BAR_COLUMNS_BY_VERSION)
        for i, row in enumerate(rows):
            out.append((path, version, i, row))
    return out


def conflicts(root: Path | str | None = None,
              symbol: str | None = None,
              interval_s: int | None = None) -> dict[tuple, list]:
    """Keys holding a CONFLICT record, with every row that claims them."""
    grouped: dict[tuple, list] = {}
    for path, version, i, row in _load(root):
        key = tuple(row[c] for c in _KEY)
        grouped.setdefault(key, []).append((path, version, i, row))
    out = {}
    for key, rows in grouped.items():
        if not any(r[3]["record_kind"] == "CONFLICT" for r in rows):
            continue
        if symbol is not None and key[0] != symbol:
            continue
        if interval_s is not None and int(key[1]) != interval_s:
            continue
        out[key] = rows
    return dict(sorted(out.items()))


def _rewrite(path: Path, version: int, edits: dict[int, str]) -> None:
    """Rewrite one segment with `record_kind` flipped on the named lines.

    Backs the segment up FIRST, then writes through a PID-scoped tmp in the
    same directory and an atomic replace. Refuses a header it does not
    recognise (_read_segment already raised in that case)."""
    columns = cj._BAR_COLUMNS_BY_VERSION[version]
    rows = cj._read_segment(path, version, cj._BAR_COLUMNS_BY_VERSION)
    backup = path.with_suffix(path.suffix + f".preschema_{int(time.time())}")
    shutil.copy2(path, backup)
    tmp = path.with_suffix(path.suffix + ".resolve.tmp")
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(columns)
        for i, row in enumerate(rows):
            if i in edits:
                row = {**row, "record_kind": edits[i]}
            w.writerow([row[c] for c in columns])
    from core.runtime import replace_with_retry
    replace_with_retry(tmp, path)
    print(f"  rewrote {path.name} ({len(edits)} record_kind flips); "
          f"backup {backup.name}")


def resolve(root: Path | str | None = None, *, accept: str = "latest",
            symbol: str | None = None, interval_s: int | None = None,
            apply: bool = False) -> int:
    """List, and with apply=True flip, the authoritative row per key."""
    found = conflicts(root, symbol, interval_s)
    if not found:
        print("no conflicted keys")
        return 0
    edits: dict[Path, tuple[int, dict[int, str]]] = {}
    for key, rows in found.items():
        rows = sorted(rows, key=lambda r: (r[0].name, r[2]))
        if accept == "latest":
            winner = len(rows) - 1
        elif accept == "first":
            winner = 0
        else:
            print(f"REFUSED: unknown --accept {accept!r}")
            return 1
        print(f"{'/'.join(str(k) for k in key)}: {len(rows)} rows -> "
              f"accepting #{winner}")
        for n, (path, version, i, row) in enumerate(rows):
            want = "BAR" if n == winner else "CONFLICT"
            print(f"    [{n}] {path.name}:{i} {row['record_kind']:<8} "
                  f"close={row['close']:<12} -> {want}")
            if row["record_kind"] != want:
                slot = edits.setdefault(path, (version, {}))
                slot[1][i] = want
    if not apply:
        print("\nDRY RUN - nothing written. Re-run with --apply to commit.")
        return 0
    for path, (version, flips) in edits.items():
        _rewrite(path, version, flips)
    print("\nrun `python scripts/candle_store.py rebuild` to refresh the "
          "parquet index")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__ or "",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=None)
    ap.add_argument("--symbol", default=None)
    ap.add_argument("--interval", type=int, default=None)
    ap.add_argument("--accept", default="latest", choices=("latest", "first"))
    ap.add_argument("--apply", action="store_true",
                    help="commit the flips; without it this is a dry run")
    args = ap.parse_args(argv)
    return resolve(args.root, accept=args.accept, symbol=args.symbol,
                   interval_s=args.interval, apply=args.apply)


if __name__ == "__main__":
    raise SystemExit(main())
