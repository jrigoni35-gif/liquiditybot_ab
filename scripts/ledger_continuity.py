"""scripts/ledger_continuity.py - standing test of a claim I made once.

WHY THIS EXISTS, IN THE WORDS OF THE MISTAKE IT PREVENTS.

On 2026-08-23 the live fills ledger was found to be missing 102 order_ids -
136 rows in a ~23h window (2026-08-01 12:35 -> 2026-08-02 11:44) that sits
INSIDE the ledger's own time range. It was found by accident, 21 days late,
while auditing something else. Asked whether it biased the era-4 verdict, I
answered:

    "It structurally cannot. The missing window is 2026-08-01/02; the cohort
     boundary is 2026-08-10. Nothing in the hole is inside the accruing
     cohort. Don't spend on it."

That answer was correct AND DANGEROUS, because it is a one-time structural
argument about ONE hole. A future hole can land on the other side of the
boundary, and the conclusion above would still be sitting in the record
reading like a settled property of the system. USAGE.md rule (g): recall
must never become the reuse of a cached conclusion as evidence.

So this tool does not remember that answer. IT RE-DERIVES IT, every run:

  * the cohort boundary is IMPORTED from scripts/cohort_eval.py - the
    pre-registered tool that owns it. No date is written here. If the
    operator re-fences the cohort, this check follows automatically and no
    one has to remember that it existed.
  * the hole is recomputed from the artifacts on disk, not read from a
    previous report.
  * the verdict is therefore a function of TODAY's ledger and TODAY's
    boundary, never of what was true in August.

CONTINUOUS, NOT ONE-SHOT. Each run appends its verdict to
outputs/ledger_continuity.jsonl. A single run answers "is the ledger whole
now"; the accumulated file answers the question that actually matters -
"when did it stop being whole, and did anyone notice" - which is exactly the
question nobody could answer about the 2026-08-01 hole.

REPORT-ONLY. Reads, appends one JSONL line, exits. It repairs nothing: the
fills ledger feeds cost attribution and the cohort verdict, so reconstructing
it is an operator decision, never a side effect of a check.

Exit: 0 clean or benign, 1 CONTAMINATING (a hole intersects the live cohort),
2 the check could not run (which is NOT the same as clean, and says so).

    python scripts/ledger_continuity.py [--outputs DIR] [--json] [--no-append]
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEDGER = "fills.csv"
BACKUP_GLOBS = ("fills.csv.bak_*", "fills.csv.preschema_*",
                "archive/**/fills.csv.bak_*", "archive/**/fills.csv.preschema_*")
KEY = "order_id"
TS = "ts"


def _boundary():
    """Import the cohort boundary from the tool that OWNS it.

    Deliberately not a constant in this file. A date copied to a second
    place is a date that will disagree with the first place eventually, and
    the whole point of this check is that it must not go stale when the
    operator re-fences the cohort (which has already happened once, at cut
    #7, the geometry epoch).
    """
    sys.path.insert(0, str(ROOT))
    try:
        import importlib
        ce = importlib.import_module("scripts.cohort_eval")
    except Exception:  # noqa: BLE001 - report, never crash a monitor
        try:
            spec = __import__("importlib.util", fromlist=["util"]).util
            s = spec.spec_from_file_location(
                "cohort_eval", ROOT / "scripts" / "cohort_eval.py")
            ce = spec.module_from_spec(s)
            s.loader.exec_module(ce)  # type: ignore[union-attr]
        except Exception as e:  # noqa: BLE001
            return None, f"cannot import cohort_eval: {str(e)[:120]}"
    ts = getattr(ce, "CAPITAL_EPOCH_TS", None)
    if ts is None:
        return None, "cohort_eval exposes no CAPITAL_EPOCH_TS"
    return float(ts), None


def _rows(p: Path):
    try:
        with p.open(encoding="utf-8", errors="replace", newline="") as f:
            return list(csv.DictReader(f))
    except OSError:
        return []


def _f(row, key):
    try:
        return float(row.get(key) or 0)
    except (TypeError, ValueError):
        return 0.0


def scan(outputs: Path) -> dict:
    live_p = outputs / LEDGER
    if not live_p.exists():
        return {"ok": False, "why": f"no {LEDGER} at {outputs}"}
    live = _rows(live_p)
    if not live:
        return {"ok": False, "why": f"{LEDGER} is empty or unreadable"}
    live_keys = {r.get(KEY) for r in live if r.get(KEY)}

    seen, sources = {}, []
    for g in BACKUP_GLOBS:
        for b in sorted(outputs.glob(g)):
            if not b.is_file():
                continue
            n = 0
            for r in _rows(b):
                k = r.get(KEY)
                if k and k not in live_keys:
                    seen[(k, r.get(TS))] = r
                    n += 1
            sources.append({"file": str(b.relative_to(outputs)), "orphans": n})
    orphans = list(seen.values())

    # GHOST POSITIONS - traded but never labeled (added 2026-08-24, measured
    # instance: 34 ETH positions in the 08-01/02 window, full entry+exit
    # fill sequences, exec_era blank, no corpus row under ANY source - the
    # stale-binary signature). A position that filled but produced no
    # training label is a leak this file's fills-vs-fills reconciliation
    # cannot see, so fills are reconciled against the LABEL corpus too.
    # Closed = has entry AND exit purpose fills; grace excludes positions
    # still inside the label horizon. Report-only, like everything here.
    ghosts: list[str] = []
    corpus_p = outputs / "signal_history.csv"
    if corpus_p.exists():
        labeled = {r.get("position_id") for r in _rows(corpus_p)
                   if r.get("position_id")}
        by_pid: dict = {}
        for r in live:
            pid = r.get("position_id")
            if not pid:
                continue
            d = by_pid.setdefault(pid, {"entry": False, "exit": False,
                                        "last_ts": 0.0})
            purpose = (r.get("purpose") or "").lower()
            if purpose == "entry":
                d["entry"] = True
            elif purpose == "exit":
                d["exit"] = True
            d["last_ts"] = max(d["last_ts"], _f(r, TS))
        import time as _time
        grace = 48 * 3600.0
        ghosts = sorted(pid for pid, d in by_pid.items()
                        if d["entry"] and d["exit"]
                        and pid not in labeled
                        and d["last_ts"] > 0
                        and _time.time() - d["last_ts"] > grace)

    boundary, why = _boundary()
    if boundary is None:
        return {"ok": False, "why": why, "orphans": len(orphans),
                "ghost_positions": len(ghosts)}

    inside = [r for r in orphans if _f(r, TS) >= boundary]
    outside = [r for r in orphans if _f(r, TS) < boundary]

    def _agg(rs):
        notl = sum(abs(_f(r, "fill_size") * _f(r, "fill_price")) for r in rs)
        return {"rows": len(rs), "notional": round(notl, 2),
                "fees": round(sum(_f(r, "fees_delta_usd") for r in rs), 4)}

    def _span(rs):
        t = [_f(r, TS) for r in rs if _f(r, TS)]
        if not t:
            return None
        return [dt.datetime.fromtimestamp(min(t)).isoformat(timespec="minutes"),
                dt.datetime.fromtimestamp(max(t)).isoformat(timespec="minutes")]

    live_agg = _agg(live)
    all_agg = _agg(live + orphans)
    fee_live = (live_agg["fees"] / live_agg["notional"] * 1e4
                if live_agg["notional"] else 0.0)
    fee_all = (all_agg["fees"] / all_agg["notional"] * 1e4
               if all_agg["notional"] else 0.0)

    return {
        "ok": True,
        "read_at": dt.datetime.now().isoformat(timespec="seconds"),
        "boundary_ts": boundary,
        "boundary_iso": dt.datetime.fromtimestamp(boundary).isoformat(
            timespec="seconds"),
        "boundary_source": "scripts/cohort_eval.py CAPITAL_EPOCH_TS (imported)",
        "live_rows": len(live), "live_keys": len(live_keys),
        "live_span": _span(live),
        "orphans_total": len(orphans),
        "orphans_inside_cohort": len(inside),
        "orphans_outside_cohort": len(outside),
        "inside_span": _span(inside), "outside_span": _span(outside),
        "sources": sources,
        "fee_bps_live": round(fee_live, 3),
        "fee_bps_reconstructed": round(fee_all, 3),
        "fee_bps_delta": round(abs(fee_all - fee_live), 3),
        "contaminating": bool(inside),
        "ghost_positions": len(ghosts),
        "ghost_sample": ghosts[:10],
    }


def append_history(outputs: Path, res: dict) -> None:
    """The continuous half. One line per run; the FILE is the instrument.

    A single verdict answers "is it whole now". The accumulated series answers
    "when did it stop, and how long did nobody notice" - the question that
    could not be answered about the 2026-08-01 hole because nothing was
    watching.
    """
    rec = {k: res.get(k) for k in (
        "read_at", "live_rows", "live_keys", "orphans_total",
        "orphans_inside_cohort", "boundary_iso", "fee_bps_delta",
        "contaminating", "ghost_positions")}
    try:
        with (outputs / "ledger_continuity.jsonl").open(
                "a", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")
    except OSError as e:
        print("[warn] could not append history: %s" % e, file=sys.stderr)


def _render(r: dict) -> None:
    print("LEDGER CONTINUITY - does a ledger hole touch the accruing cohort?")
    print("=" * 70)
    if not r.get("ok"):
        print("CHECK COULD NOT RUN: %s" % r.get("why"))
        print("")
        print("This is NOT a clean result. 'no findings' and 'the scan is")
        print("broken' are the same observation until they are separated.")
        return
    print("read at   %s" % r["read_at"])
    print("boundary  %s" % r["boundary_iso"])
    print("          %s" % r["boundary_source"])
    print("          (re-derived every run - never a date written here)")
    print("")
    print("live ledger      %d rows, %d distinct %s"
          % (r["live_rows"], r["live_keys"], KEY))
    print("                 span %s" % (r["live_span"],))
    print("")
    print("ORPHANED RECORDS (in a backup, absent from the live ledger)")
    print("  total                    %d" % r["orphans_total"])
    print("  BEFORE the boundary      %d  span %s"
          % (r["orphans_outside_cohort"], r["outside_span"]))
    print("  INSIDE the cohort        %d  span %s"
          % (r["orphans_inside_cohort"], r["inside_span"]))
    for s in r["sources"]:
        if s["orphans"]:
            print("    %-44s %d" % (s["file"], s["orphans"]))
    print("")
    print("MATERIALITY (measured, not asserted)")
    print("  aggregate fee rate  live %.3f bps -> reconstructed %.3f bps"
          % (r["fee_bps_live"], r["fee_bps_reconstructed"]))
    print("  delta                    %.3f bps" % r["fee_bps_delta"])
    print("")
    if r["contaminating"]:
        print("*** CONTAMINATING: %d orphaned fill(s) fall INSIDE the"
              % r["orphans_inside_cohort"])
        print("*** accruing cohort. The era-4 verdict is computed on a")
        print("*** ledger that is missing them. Do NOT read the gate until")
        print("*** this is reconciled. scripts/cohort_eval.py is governing.")
    elif r["orphans_total"]:
        print("BENIGN AS OF THIS RUN: every orphan predates the boundary, so")
        print("the accruing cohort does not see them. This is a MEASUREMENT,")
        print("not a property of the system - a future hole can land on the")
        print("other side, which is the entire reason this runs continuously.")
    else:
        print("No orphaned fills. The ledger is whole with respect to every")
        print("backup on disk.")
    g = r.get("ghost_positions", 0)
    print("")
    print("GHOST POSITIONS (traded but never labeled - closed >48h, no")
    print("corpus row under any source)")
    if g:
        print("  *** %d position(s): filled on the venue, invisible to" % g)
        print("  *** training. Known cause on record: a stale binary's book")
        print("  *** (34 measured in the 08-01/02 window). Investigate any")
        print("  *** NEW one - it is a label leak, not history.")
        for pid in r.get("ghost_sample", []):
            print("      %s" % pid[:16])
    else:
        print("  none - every closed position produced a label row.")
    print("")
    print("WHAT THIS CANNOT SEE: only rows that survived into a BACKUP. A row")
    print("lost before any rotation leaves no artifact and no trace here.")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--outputs", default="outputs")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--no-append", action="store_true",
                    help="do not append to ledger_continuity.jsonl")
    ns = ap.parse_args()
    outputs = Path(ns.outputs)
    if not outputs.is_dir():
        print("no outputs dir at %s" % outputs)
        return 2
    res = scan(outputs)
    if res.get("ok") and not ns.no_append:
        append_history(outputs, res)
    if ns.json:
        print(json.dumps(res, indent=1))
    else:
        _render(res)
    if not res.get("ok"):
        return 2
    return 1 if res["contaminating"] else 0


if __name__ == "__main__":
    sys.exit(main())
