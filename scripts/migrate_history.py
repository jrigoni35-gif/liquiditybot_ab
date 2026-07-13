"""
scripts/migrate_history.py

Migrate labeled training rows from an older signal-history schema into the
CURRENT schema, padding feature columns that did not exist yet with their
documented neutral values (strategies/smc.py NEUTRAL for the SMC block;
0.0 for anything else, loudly reported). Never runs automatically -
schema changes orphan old rows silently otherwise (observed 2026-07-11:
the 36->43 SMC bump left every accumulated live row unreadable by
load_training_data, which skips rows missing a feature column).

Rows keep their original source tag ("live"/"candidate") so training
sample-weighting semantics are unchanged; provenance of the migration is
this script's console output plus the untouched input file.

Usage:
    python scripts/migrate_history.py --src outputs/archive/old.csv \
        [--dest outputs/signal_history.csv] [--dry-run]
"""

import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ml.features import FEATURE_NAMES  # noqa: E402
from ml.history import HistoryStore  # noqa: E402
from ml.features import PATTERN_NEUTRAL  # noqa: E402
from strategies.smc import NEUTRAL as SMC_NEUTRAL  # noqa: E402

# every feature family with a documented migration neutral
KNOWN_NEUTRAL = {**SMC_NEUTRAL, **PATTERN_NEUTRAL}

META_COLS = ("position_id", "asset", "side", "label", "net_pnl_usd",
             "source", "ts")


def migrate_rows(src_path: str) -> tuple[list, list]:
    """Returns (new_schema_rows, padded_feature_names)."""
    with open(src_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        src_rows = [r for r in reader if None not in r.values()]
        src_cols = set(reader.fieldnames or [])

    missing_meta = [c for c in META_COLS if c not in src_cols]
    if missing_meta:
        raise SystemExit(f"source is not a signal-history file - missing "
                         f"meta columns {missing_meta}")

    padded = [n for n in FEATURE_NAMES if n not in src_cols]
    out = []
    for r in src_rows:
        feats = []
        for n in FEATURE_NAMES:
            if n in src_cols:
                feats.append(r[n])
            else:
                feats.append(f"{float(KNOWN_NEUTRAL.get(n, 0.0)):.6f}")
        out.append([r["position_id"], r["asset"], r["side"], *feats,
                    r["label"], r["net_pnl_usd"], r["source"], r["ts"]])
    return out, padded


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True,
                    help="old-schema CSV (a .bak_* rotation or archive copy)")
    ap.add_argument("--dest", default="outputs/signal_history.csv")
    ap.add_argument("--dry-run", action="store_true",
                    help="report what would migrate, write nothing")
    args = ap.parse_args()

    rows, padded = migrate_rows(args.src)
    unknown = [n for n in padded if n not in KNOWN_NEUTRAL]
    print(f"source rows: {len(rows)}")
    print(f"padded features ({len(padded)}): {padded}")
    if unknown:
        print(f"WARNING: no documented neutral for {unknown} - padded 0.0")
    if not rows:
        print("nothing to migrate")
        return 0
    if args.dry_run:
        print("dry-run: nothing written")
        return 0

    store = HistoryStore(args.dest)
    dest = Path(args.dest)
    # rotate-or-create FIRST: reading dedupe ids from a dest that is
    # about to be rotated away compared the migrated rows against their
    # own old-schema selves - every row skipped as a "duplicate", zero
    # written (observed on the 43->46 candle-pattern bump; the 36->43
    # migrations never hit it because their dest was already rotated).
    store._ensure_schema()
    existing_ids = set()
    if dest.exists():
        with open(dest, newline="", encoding="utf-8") as f:
            existing_ids = {r.get("position_id") for r in csv.DictReader(f)}
    written = skipped = 0
    with open(dest, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        for row in rows:
            if row[0] in existing_ids:
                skipped += 1
                continue
            w.writerow(row)
            written += 1
    print(f"migrated {written} rows -> {dest}"
          + (f" ({skipped} duplicates skipped)" if skipped else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
