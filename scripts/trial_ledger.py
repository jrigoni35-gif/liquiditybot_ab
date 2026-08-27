"""scripts/trial_ledger.py — the TRIALS-1 artifact (spec 2026-08-27 v0.1).

One CSV of every strategy trial actually evaluated (battery runs +
harvested historical searches) + a meta sidecar with attempted/accepted/
refused counters so refusals are never a silent cap. OF-5 reads
measured_trials() under a ratchet: max(configured, measured) — a ledger
can only DEEPEN deflation. sr/max_dd/n_eff are nullable ('' in CSV) in
v0.1: per-run SR is undefined below TRIPS_FLOOR=20 uncensored trips.
Report-only; never touches config or engine state.
"""
import csv
import json
import sys
from pathlib import Path

SCHEMA_VERSION = 1
TRIPS_FLOOR = 20          # sr stays '' below this (spec §1; measurement standard)
SOURCES = ("battery", "harvest")
ANCHORS = ("booked", "true")

LEDGER_COLUMNS = ("schema_version", "strategy_id", "source", "seed",
                  "fee_anchor", "harness_profile", "cycles", "entries",
                  "exits", "gross_pct", "net_pct", "sr", "max_dd",
                  "n_eff", "degenerate", "exit_profile", "count")


class LedgerInvalid(ValueError):
    pass


def append_rows(rows: list, ledger_path: Path) -> None:
    ledger_path = Path(ledger_path)
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    new = not ledger_path.exists()
    with open(ledger_path, "a", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(LEDGER_COLUMNS))
        if new:
            w.writeheader()
        for r in rows:
            missing = set(LEDGER_COLUMNS) - set(r)
            if missing:
                raise LedgerInvalid(f"row missing columns: {sorted(missing)}")
            w.writerow({k: r[k] for k in LEDGER_COLUMNS})


def _coerce(r: dict) -> dict:
    out = dict(r)
    out["schema_version"] = int(r["schema_version"])
    out["seed"] = int(r["seed"])
    out["cycles"] = int(r["cycles"])
    out["entries"] = int(r["entries"])
    out["exits"] = int(r["exits"])
    out["count"] = int(r.get("count") or 1)
    out["degenerate"] = str(r["degenerate"]).strip().lower() == "true"
    for k in ("gross_pct", "net_pct"):
        out[k] = float(r[k]) if str(r[k]).strip() != "" else None
    for k in ("sr", "max_dd", "n_eff"):
        out[k] = float(r[k]) if str(r[k]).strip() != "" else None
    return out


def read_ledger(ledger_path: Path) -> list:
    ledger_path = Path(ledger_path)
    with open(ledger_path, newline="", encoding="utf-8") as fh:
        raw = list(csv.DictReader(fh))
    rows = []
    for i, r in enumerate(raw):
        if set(r) != set(LEDGER_COLUMNS):
            raise LedgerInvalid(f"row {i}: columns {sorted(r)} != schema")
        try:
            row = _coerce(r)
        except (TypeError, ValueError) as e:
            raise LedgerInvalid(f"row {i}: {e}") from e
        if row["schema_version"] != SCHEMA_VERSION:
            raise LedgerInvalid(f"row {i}: schema_version "
                                f"{row['schema_version']} != {SCHEMA_VERSION}")
        if row["source"] not in SOURCES:
            raise LedgerInvalid(f"row {i}: source {row['source']!r}")
        if row["fee_anchor"] not in ANCHORS and row["source"] == "battery":
            raise LedgerInvalid(f"row {i}: fee_anchor {row['fee_anchor']!r}")
        rows.append(row)
    return rows


def measured_trials(rows: list) -> dict:
    battery = {(r["source"], r["strategy_id"], r["harness_profile"])
               for r in rows if r["source"] == "battery"}
    harvest_n = sum(r["count"] for r in rows if r["source"] == "harvest")
    by_source = {}
    for r in rows:
        by_source[r["source"]] = by_source.get(r["source"], 0) + 1
    deg = sum(1 for r in rows if r["degenerate"])
    return {"n_trials": len(battery) + harvest_n, "by_source": by_source,
            "degenerate": deg, "non_degenerate": len(rows) - deg}


def write_meta(ledger_path: Path, attempted: int, accepted: int,
               refused: int, notes: list) -> None:
    meta = {"schema_version": SCHEMA_VERSION, "attempted": attempted,
            "accepted": accepted, "refused": refused, "notes": list(notes)}
    Path(ledger_path).with_suffix(".meta.json").write_text(
        json.dumps(meta, indent=1), encoding="utf-8")


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--ledger", default="outputs/trial_ledger.csv")
    ap.add_argument("--report", action="store_true")
    ns = ap.parse_args()
    p = Path(ns.ledger)
    if not p.exists():
        print(f"no ledger at {p} (ABSENT, not zero trials)")
        return 0
    try:
        rows = read_ledger(p)
    except LedgerInvalid as e:
        print(f"LEDGER INVALID: {e}")
        return 1
    m = measured_trials(rows)
    print(f"trial ledger: {len(rows)} rows | measured n_trials="
          f"{m['n_trials']} | by_source={m['by_source']} | "
          f"degenerate={m['degenerate']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
