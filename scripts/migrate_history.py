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
from ml.history import HistoryStore, SG_COMPONENT_KEYS, label_era_of  # noqa: E402
from ml.features import (CONTEXT_NEUTRAL, PATTERN_NEUTRAL,  # noqa: E402
                         TOX_NEUTRAL, TRIO_NEUTRAL, V9_NEUTRAL)
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
# TOX_NEUTRAL (v8): flow_tox pads 0.0 = "no toxicity signal read" - a
# padded pre-v8 row is indistinguishable from genuinely balanced flow.
# V9_NEUTRAL: the shadow pair pads 0.0 = "no signed event flow / no
# basis drift observed" - no unsigned twin ever existed, so old bundles
# pad rather than derive (the TRIO precedent).
KNOWN_NEUTRAL = {**SMC_NEUTRAL, **PATTERN_NEUTRAL, **CONTEXT_NEUTRAL,
                 **TRIO_NEUTRAL, **TOX_NEUTRAL, **V9_NEUTRAL,
                 **{k: 0.0 for k in DIR_DERIVED}}

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
                    r.get("disp") or "",
                    # candidate_id joined 2026-07-23 (W2-4 twin-dedup
                    # lineage join key) - pre-bump rows carry no lineage,
                    # the clash guard falls back to exact-vector match
                    r.get("candidate_id") or "",
                    # book joined 2026-07-24 (Compounder Phase C, Task C1):
                    # 5m/long strategy book tag - every bundle this script
                    # can migrate predates the long book, so "5m" is not
                    # just a fallback, it is the FACT of every such row
                    r.get("book") or "5m",
                    # label_era joined 2026-07-26 (label-era instrumentation,
                    # DEEP DIVE progress.md): which label DEFINITION produced
                    # this row's barrier value.
                    #
                    # IDEMPOTENCE (2026-08-09 incident): pass an already-
                    # migrated row's own persisted value through UNCHANGED,
                    # exactly like every other trailing column below. This
                    # line previously recomputed it unconditionally as
                    # `label_era_of(r.get("barrier") or "")` and was the ONLY
                    # non-idempotent column in this function - the rule it
                    # broke is documented in the pt_frac comment immediately
                    # below. label_era_of() has no horizon knowledge and
                    # returns the UNQUALIFIED "triple_barrier" for any tb_*
                    # barrier, while the writer (ml/history.py _row_era ->
                    # triple_barrier_era(max_bars)) persists the QUALIFIED
                    # "triple_barrier_h432". So every migration pass silently
                    # re-tagged era-qualified rows into the pooled bucket,
                    # merging label definitions that must never share a name.
                    # Measured blast radius on 2026-08-08's rotation: 2,729
                    # rows across two rotations (h432->triple_barrier 652,
                    # h24->triple_barrier 2,077). Downstream that collapsed
                    # the current-era count below ml.era_exclusion.
                    # min_new_era_rows, DISARMING the era filter, which
                    # released the whole pooled corpus into training and
                    # promoted the model family on a data bug rather than on
                    # evidence.
                    #
                    # Only a row that genuinely predates the column (no value
                    # to preserve) falls back to the derivation - the same
                    # meaning the loader's own _row_label_era fallback gives
                    # such a row.
                    r.get("label_era") or label_era_of(r.get("barrier") or ""),
                    # pt_frac, sl_frac joined 2026-07-27 (geometry-alignment
                    # T3): the barrier_geometry() bracket a row's label was
                    # decided under. Pass an already-migrated row's own real
                    # value through UNCHANGED (idempotence: a second
                    # migration pass must never clobber real geometry with
                    # the neutral default) - only a row that predates this
                    # column pads "0.000000" = "unknown/legacy geometry",
                    # the same meaning HistoryStore gives an unpopulated
                    # column on a live-written row.
                    r.get("pt_frac") or "0.000000",
                    r.get("sl_frac") or "0.000000",
                    # sg_flow..sg_conc joined 2026-07-28 (gate-truth
                    # instrumentation T2): informed-flow component scores at
                    # signal time. Pass an already-migrated row's own real
                    # value through UNCHANGED (idempotence - same precedent
                    # as pt_frac/sl_frac above); a row that predates this
                    # column pads "0.0000" = pre-instrumentation/
                    # uninstrumented, the same meaning HistoryStore gives an
                    # unpopulated column on a live-written row.
                    *[r.get(f"sg_{k}") or "0.0000" for k in
                      SG_COMPONENT_KEYS],
                    # entry_price, exit_price joined 2026-08-04: the price
                    # anchor. Same idempotence precedent - pass an already-
                    # migrated row's real value through UNCHANGED, pad "0"
                    # for a row that predates the column. NOTHING can
                    # derive a price for a legacy row (the corpus never
                    # stored one anywhere), so 0 is permanent for them and
                    # readers must treat it as "absent", never as a price.
                    r.get("entry_price") or "0",
                    r.get("exit_price") or "0",
                    # avail_web..quotes_frozen joined 2026-08-08 (owed
                    # 41b): context-feed availability at feature-build
                    # time. Same idempotence precedent - pass an already-
                    # migrated row's real value through UNCHANGED; a row
                    # that predates the columns pads "" = UNKNOWN. Never
                    # "0": nothing measured those feeds for a legacy row,
                    # and "0" would claim a measured outage.
                    r.get("avail_web") or "",
                    r.get("avail_equity") or "",
                    r.get("avail_options") or "",
                    r.get("quotes_frozen") or "",
                    # label_ret_pct joined 2026-08-24 (schema 94): the
                    # labeled outcome's realized return in percent. Same
                    # idempotence precedent - a migrated row's real value
                    # passes through UNCHANGED; a row that predates the
                    # column pads "" = UNKNOWN. NEVER "0": the old defect
                    # was precisely a fabricated 0.0 standing in for an
                    # outcome nobody kept, and a migration that re-minted
                    # zeros would rebuild it for the whole legacy corpus.
                    r.get("label_ret_pct") or "",
                    # control_arm joined 2026-08-27 (schema 95, sandbox
                    # prototype - control-arm stratification tag): a
                    # deterministic 5% signal-time stratification tag (see
                    # CONTROL_ARM_FRACTION / _control_arm_tag in
                    # ml/history.py). Same idempotence precedent as every
                    # column above - an already-migrated row's real "1"/"0"
                    # passes through UNCHANGED. A row that predates the
                    # column pads "" = not-designated, NEVER "0": this tag
                    # is deterministic from (asset, signal_ts), and a
                    # migration pass has both inputs available, but
                    # BACKFILLING one anyway would claim the row was drawn
                    # under a control-arm design that did not exist at
                    # write time - the same "retroactive designation is not
                    # the same fact as a contemporaneous one" argument the
                    # column exists to enforce going forward. "" is the
                    # honest read for every row this script can migrate.
                    r.get("control_arm") or ""])
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
