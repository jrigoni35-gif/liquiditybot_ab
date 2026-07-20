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
from ml.features import CONTEXT_NEUTRAL, PATTERN_NEUTRAL, TRIO_NEUTRAL  # noqa: E402
from strategies.smc import NEUTRAL as SMC_NEUTRAL  # noqa: E402

# side-relative features derivable from an older absolute-encoded file:
# new_value = old_value * direction (the direction FEATURE column, +/-1).
# Derivation preserves the old rows' full information; padding would
# have thrown it away.
DIR_DERIVED = {
    "ret_1_dir": "ret_1", "ret_6_dir": "ret_6", "ret_12_dir": "ret_12",
    "ret_48_dir": "ret_48", "imbalance_dir": "imbalance",
    "basis_dir": "basis_bps", "funding_dir": "funding_bps",
    "mom_dir": "mom_score", "sent_dir": "sent_score",
    "imbalance_delta_dir": "imbalance_delta",
    "other_ret_6_dir": "other_ret_6",
    "pat_engulf_dir": "pat_engulf", "pat_hammer_dir": "pat_hammer",
    "pat_marubozu_dir": "pat_marubozu",
}

# every feature family with a documented migration neutral. TRIO_NEUTRAL
# (v7): mkt_ret_6_dir gets NO DIR_DERIVED entry - no unsigned twin ever
# existed in an older schema, so old bundles pad 0.0 rather than derive.
KNOWN_NEUTRAL = {**SMC_NEUTRAL, **PATTERN_NEUTRAL, **CONTEXT_NEUTRAL,
                 **TRIO_NEUTRAL, **{k: 0.0 for k in DIR_DERIVED}}

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

    def _derivable(n):
        return (n in DIR_DERIVED and DIR_DERIVED[n] in src_cols
                and "direction" in src_cols)

    padded = [n for n in FEATURE_NAMES
              if n not in src_cols and not _derivable(n)]
    out = []
    for r in src_rows:
        feats = []
        for n in FEATURE_NAMES:
            if n in src_cols:
                feats.append(r[n])
            elif _derivable(n):
                sign = 1.0 if float(r["direction"]) >= 0 else -1.0
                feats.append(f"{float(r[DIR_DERIVED[n]]) * sign:.6f}")
            else:
                feats.append(f"{float(KNOWN_NEUTRAL.get(n, 0.0)):.6f}")
        # signal_ts/barrier joined the schema after this script was written;
        # emit them so migrated rows are the FULL current width (else they land
        # short and DictReader None-fills the tail). Pre-signal_ts bundles fall
        # back to ts; pre-barrier bundles get "" (= barrier unknown, which the
        # loader treats as no time-barrier distinction — full weight).
        out.append([r["position_id"], r["asset"], r["side"], *feats,
                    r["label"], r["net_pnl_usd"], r["source"], r["ts"],
                    r.get("signal_ts") or r["ts"], r.get("barrier") or "",
                    # probe joined the schema 2026-07-20: "1" PT-050 probe,
                    # "0" conviction, "" pre-bump unknown (OF-5 counts only
                    # explicit "0" toward the conviction sample)
                    r.get("probe") or "",
                    # disp joined 2026-07-20 (pipeline disposition)
                    r.get("disp") or ""])
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
