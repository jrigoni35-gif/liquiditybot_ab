"""scripts/forward_reads.py - read every registered hypothesis forward, on
data that did not exist when it was registered (SAFE: measurement only;
places nothing; writes only under outputs/).

    python scripts/forward_reads.py --once        # supervisor: weekly

The registry (docs/quant/hypothesis_registry.json) holds 21 hypotheses with
`forward_from` = their registration day. The ledger's rule is asymmetric:
the past may eliminate, only data after forward_from may promote. This job
is what turns calendar time into that forward data:

  1. scripts/alpha_decay_report.py --through now   every window's END rolls
     to the current month (starts and definitions stay registered; the
     month still forming is re-fetched daily, never frozen)
  2. scripts/evidence_ledger.py on that report      anytime-valid e-values
  3. sticky statuses in outputs/reports/forward/registry_status.json: an
     ELIMINATED status is never overwritten (failure memory) - kept here,
     not in the repo, so the deployed checkout stays clean for the updater
  4. scripts/knowledge_plan.py                      where data buys the most
  5. outputs/reports/forward/forward_reads.json     the summary, carried
     off-box by the pc-live bundle (scripts/session_export.py PORTABLE)

The instrument controls (GBM/shuffle/planted) ran at registration and are
skipped here (--skip-controls); the bootstrap uses 1,000 reps. A lock older
than LOCK_STALE_S is reclaimed; a fresher one means a run is in progress.
"""
from __future__ import annotations

import argparse
import glob
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import alpha_decay_report as ad  # noqa: E402
from scripts import evidence_ledger as el  # noqa: E402
from scripts import knowledge_plan as kp  # noqa: E402

REPS = 1000
LOCK_STALE_S = 12 * 3600
SUMMARY_NAME = "forward_reads.json"


def default_dir() -> Path:
    return ROOT / "outputs" / "reports" / "forward"


def _newest(pattern: str) -> Path | None:
    hits = sorted(glob.glob(pattern))
    return Path(hits[-1]) if hits else None


def sticky_statuses(path: Path, rows: list) -> dict:
    """Merge this run's statuses into the persisted ones; eliminations stick."""
    prior = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    reg = [{"id": k, "status": v} for k, v in prior.items()]
    known = {h["id"] for h in reg}
    reg += [{"id": r["id"]} for r in rows if r["id"] not in known]
    el.merge_status(reg, {r["id"]: r["status"] for r in rows})
    out = {h["id"]: h["status"] for h in reg if "status" in h}
    path.write_text(json.dumps(out, indent=1, sort_keys=True), encoding="utf-8")
    return out


def summarise(ledger: dict, statuses: dict, plan: list, report: dict,
              n_registry: int) -> dict:
    rows = []
    for r in ledger["rows"]:
        rows.append({"id": r["id"], "use": r["use"], "status": statuses.get(r["id"], r["status"]),
                     "this_run": r["status"], "n_blocks": r["all"]["n"],
                     "db_below_bar": r["all"]["db_dead"],
                     "forward_blocks": r["forward"]["n"],
                     "db_exist_forward": r["forward"]["db_exist"]})
    counts: dict = {}
    for r in rows:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    n = len(rows) + len(ledger["missing"])
    ok = "OK" if n == n_registry else "MISMATCH"
    return {"window": report.get("registered", {}).get("panel_months"),
            "unit": "hypothesis (registry entry); blocks = independent weeks",
            "counts": counts, "missing": ledger["missing"],
            "reconcile": f"n={n_registry} = scored {len(rows)} {counts} + no series "
                         f"{len(ledger['missing'])} [{ok}]",
            "rows": rows, "knowledge_plan": plan[:10]}


def run_once(out: Path, reps: int = REPS) -> int:
    out.mkdir(parents=True, exist_ok=True)
    lock = out / ".forward_reads.lock"
    if lock.exists() and time.time() - lock.stat().st_mtime < LOCK_STALE_S:
        print("forward_reads: a run is in progress (lock fresh); skipping")
        return 0
    lock.write_text(str(time.time()), encoding="utf-8")
    try:
        ad_dir = out / "alpha_decay"
        rc = ad.main(["--through", "now", "--skip-controls", "--reps", str(reps),
                      "--out", str(ad_dir)])
        rep_path = _newest(str(ad_dir / "alpha_decay_*.json"))
        if rc != 0 or rep_path is None:
            print(f"forward_reads: alpha_decay_report failed (rc {rc})")
            return 1
        led_dir = out / "ledger"
        el.main(["--report", str(rep_path), "--out", str(led_dir)])
        led_path = _newest(str(led_dir / "ledger_*.json"))
        if led_path is None:
            return 1
        ledger = json.loads(led_path.read_text(encoding="utf-8"))
        statuses = sticky_statuses(out / "registry_status.json", ledger["rows"])
        report = json.loads(rep_path.read_text(encoding="utf-8"))
        reg = json.loads(el.REGISTRY.read_text(encoding="utf-8"))
        doc = summarise(ledger, statuses, kp.plan(reg, report), report,
                        len(reg["hypotheses"]))
        doc["written_at_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        doc["report"], doc["ledger"] = rep_path.name, led_path.name
        (out / SUMMARY_NAME).write_text(json.dumps(doc, indent=1, default=str),
                                        encoding="utf-8")
        print(f"forward_reads: window {doc['window']}; {doc['reconcile']}")
        return 0
    finally:
        lock.unlink(missing_ok=True)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--once", action="store_true", help="one forward read (the only mode)")
    ap.add_argument("--reps", type=int, default=REPS)
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)
    return run_once(Path(args.out) if args.out else default_dir(), args.reps)


if __name__ == "__main__":
    raise SystemExit(main())
