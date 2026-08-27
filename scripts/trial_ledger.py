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
import io
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
    """Append-invariant gate: routed through core.runtime.durable_append
    (crash-safe - torn-tail isolation + fsync) instead of a bare
    open(path, "a") - this ledger is a durable measurement artifact OF-5
    trusts, not a throwaway log.

    Rows are rendered with plain csv.writer into an in-memory buffer using
    the SAME default 'excel' dialect (comma delimiter, \\r\\n terminator,
    QUOTE_MINIMAL) the old csv.DictWriter used, in the same LEDGER_COLUMNS
    order DictWriter would reorder to - byte-identical output, so on-disk
    format and read_ledger are unchanged. durable_append writes `header`
    only on a genuinely new/empty file (never mid-file), matching the old
    `if new: w.writeheader()` - see its docstring for why size-0 must
    count as new."""
    from core.runtime import durable_append
    # Validate every row BEFORE building any write: a batch is
    # all-or-nothing, so a missing-column row anywhere must not leave
    # earlier rows of the same batch flushed, nor touch existing content.
    for r in rows:
        missing = set(LEDGER_COLUMNS) - set(r)
        if missing:
            raise LedgerInvalid(f"row missing columns: {sorted(missing)}")
    header_buf = io.StringIO(newline="")
    csv.writer(header_buf).writerow(LEDGER_COLUMNS)
    body_buf = io.StringIO(newline="")
    w = csv.writer(body_buf)
    for r in rows:
        w.writerow([r[k] for k in LEDGER_COLUMNS])
    body = body_buf.getvalue()
    durable_append(Path(ledger_path), lambda f: f.write(body),
                   header=header_buf.getvalue())


def _coerce(r: dict) -> dict:
    out = dict(r)
    out["schema_version"] = int(r["schema_version"])
    out["seed"] = int(r["seed"])
    out["cycles"] = int(r["cycles"])
    out["entries"] = int(r["entries"])
    out["exits"] = int(r["exits"])
    raw_count = r["count"]
    if raw_count is None:
        raise ValueError("count missing (truncated row)")
    out["count"] = int(raw_count) if str(raw_count).strip() != "" else 1
    deg_raw = str(r["degenerate"]).strip().lower()
    if deg_raw not in ("true", "false"):
        raise ValueError(
            f"degenerate must be 'true' or 'false', got {r['degenerate']!r}")
    out["degenerate"] = deg_raw == "true"
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
    ledger_path = Path(ledger_path)
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    ledger_path.with_suffix(".meta.json").write_text(
        json.dumps(meta, indent=1), encoding="utf-8")


def _harvest_row(strategy_id: str, count: int) -> dict:
    return {"schema_version": SCHEMA_VERSION, "strategy_id": strategy_id,
            "source": "harvest", "seed": 0, "fee_anchor": "n/a",
            "harness_profile": "n/a", "cycles": 0, "entries": 0, "exits": 0,
            "gross_pct": "", "net_pct": "", "sr": "", "max_dd": "",
            "n_eff": "", "degenerate": False, "exit_profile": "n/a",
            "count": count}


def harvest(outputs_dir: Path) -> tuple:
    """Count trials ALREADY evaluated by historical search tools.

    Objective-only sources: these yield N, never SR dispersion (spec
    [SEV-3]). An absent source is returned in `absent` and NEVER counted
    as zero trials — absence of a record is not a record of absence.
    Static sources (geometry grid, OF-3 model space) are read from the
    module constants that define them, so they track code, not memory.
    """
    outputs_dir = Path(outputs_dir)
    rows, absent = [], []

    ts = outputs_dir / "tune_search_state.json"
    if ts.exists():
        try:
            state = json.loads(ts.read_text(encoding="utf-8"))
            n = len(state.get("evaluated") or [])
            if n:
                rows.append(_harvest_row("tune_search", n))
        except (OSError, json.JSONDecodeError):
            absent.append("tune_search_state.json (unreadable)")
    else:
        absent.append("tune_search_state.json")

    sweeps = sorted((outputs_dir / "sweeps").glob("sweep_*.csv"))
    if sweeps:
        for sw in sweeps:
            with open(sw, newline="", encoding="utf-8") as fh:
                n = sum(1 for _ in csv.DictReader(fh))
            if n:
                rows.append(_harvest_row(f"sweep:{sw.name}", n))
    else:
        absent.append("sweeps/*.csv")

    from scripts.geometry_search import HORIZON_BARS, SL_PCT, TP_PCT
    rows.append(_harvest_row("geometry_search_grid",
                             len(TP_PCT) * len(SL_PCT) * len(HORIZON_BARS)))

    from ml.overfit import _BASE_ORDER
    rows.append(_harvest_row("of3_model_space", len(_BASE_ORDER)))
    return rows, absent


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--ledger", default="outputs/trial_ledger.csv")
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--harvest", action="store_true",
                    help="append harvest rows from outputs/ search records")
    ns = ap.parse_args()
    p = Path(ns.ledger)
    if ns.harvest:
        rows, absent = harvest(Path("outputs"))
        append_rows(rows, p)
        for a in absent:
            print(f"harvest source ABSENT (not zero): {a}")
        print(f"harvested {sum(r['count'] for r in rows)} trials "
              f"from {len(rows)} sources -> {p}")
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
