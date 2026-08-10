"""scripts/migrate_fills_schema.py - bring fills.csv to the current schema.

ONE-SHOT, EXPLICIT, BACKED-UP. core/fill_ledger.py appends new columns at
the END only, and its appender is header-aware: an old file keeps its own
width until THIS script upgrades it, so the book of record never carries
ragged rows. The current addition is `exec_era` (execution-era provenance,
CDO review 2026-08-10): existing rows get a BLANK value - blank means
"pre-stamp: decide era by ts against the boundary table", and back-filling
a guess would manufacture provenance the rows never had.

Idempotent: a file already at the current schema is left byte-untouched.
A timestamped .preschema backup is written before any rewrite - the same
never-delete discipline as the corpus repairs.

    python scripts/migrate_fills_schema.py [--fills PATH] [--dry-run]
"""
import argparse
import csv
import shutil
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

import sys  # noqa: E402

sys.path.insert(0, str(ROOT))
from core.fill_ledger import COLS  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fills", default=str(ROOT / "outputs" / "fills.csv"))
    ap.add_argument("--dry-run", action="store_true")
    ns = ap.parse_args()
    p = Path(ns.fills)
    if not p.exists() or p.stat().st_size == 0:
        print(f"nothing to migrate at {p}")
        return 0

    with open(p, newline="", encoding="utf-8") as f:
        rd = csv.reader(f)
        hdr = next(rd, None)
        rows = list(rd)
    if hdr is None:
        print("no header - refusing to touch the file")
        return 1
    if hdr == COLS:
        print(f"already at current schema ({len(hdr)} cols) - untouched")
        return 0
    unknown = [c for c in hdr if c not in COLS]
    if unknown:
        print(f"REFUSING: file has columns not in the current schema "
              f"{unknown} - resolve by hand, never by overwrite")
        return 1
    missing = [c for c in COLS if c not in hdr]
    print(f"upgrading {p}: adding {missing} to {len(rows)} rows "
          f"(blank = pre-stamp, era decided by ts)")
    if ns.dry_run:
        print("dry-run: no write")
        return 0

    bak = p.with_suffix(p.suffix + f".preschema_{int(time.time())}")
    shutil.copy2(p, bak)
    print(f"backup: {bak.name}")

    idx = {c: i for i, c in enumerate(hdr)}
    tmp = p.with_suffix(p.suffix + ".tmp")
    with open(tmp, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(COLS)
        kept = 0
        for r in rows:
            if not r:                       # torn-tail junk rows stay junk
                continue
            w.writerow([(r[idx[c]] if c in idx and idx[c] < len(r) else "")
                        for c in COLS])
            kept += 1
    tmp.replace(p)
    print(f"done: {kept} rows at {len(COLS)} cols")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
