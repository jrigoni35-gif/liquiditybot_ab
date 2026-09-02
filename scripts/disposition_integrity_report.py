"""Disposition-integrity report: does each SZ-045 stamp in signal_history.csv
match the veto evaluation that actually produced it? (read-only)

WHY THIS EXISTS (2026-09-02, design doc
docs/quant/2026-09-02_labeling_resource_model_design.md section 3). The
disposition writer (ml/history.py mark_disposition) addresses a candidate by
(asset, direction) and overwrites the newest match - a MAPPING write, not a
resource write - so a row can carry a verdict reached ~10^2 cycles after its
own features were frozen (MANIP-2). That was established by CADENCE
arithmetic. This is the PER-EVENT check: the sizer logs every SZ-045 refusal
with a millisecond timestamp, the asset and the LIVE score it compared, so
each stamped row can be joined to the evaluation nearest after its
registration and the two compared directly. It is the "verification node"
of the design - it re-checks the writer's work and has no stake in it.

Sources, both read-only:
  outputs/signal_history.csv  rows with disp == 'SZ-045'
  outputs/runner.log          lines '[ASSET] sizer veto: SZ-045: manip
                              suspect X >= veto Y' (local-time stamps; the
                              conversion offset is printed, never assumed)

COVERAGE IS BOUNDED BY THE LOG, AND THE BOUND IS STRICT ON PURPOSE. runner.log
rotates. A row is auditable only if its signal_ts >= the log's FIRST event -
not merely if its attribution window overlaps the log. The looser rule would
let a row registered just before the log begins count as covered, and then
its "unmatched" would be ambiguous (verdict fell before the log vs. no
verdict at all). With the strict rule an unmatched covered row means exactly
one thing: a log that fully spans its window holds no same-asset veto in it.
Rows in the boundary band are counted under stamped_rows_before_log and
never scored. Pinned in tests/test_disposition_integrity_report.py.

Matching rule, stated once: a stamp is attributed to the nearest veto event
for the SAME asset AT OR AFTER the row's signal_ts (a verdict cannot precede
its candidate) within --window seconds. Rows with no such event are
UNMATCHED and counted, never guessed.

    python scripts/disposition_integrity_report.py
    python scripts/disposition_integrity_report.py --json --window 86400
"""
from __future__ import annotations

import argparse
import bisect
import csv
import datetime as dt
import json
import re
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SIGNAL_PATH = ROOT / "outputs" / "signal_history.csv"
LOG_PATH = ROOT / "outputs" / "runner.log"
STAMP = "SZ-045"
DEFAULT_WINDOW_S = 6 * 3600.0
# a stored feature and the live score that vetoed it should agree to the
# corpus's own 3dp rounding; beyond this the stamp came from a different
# evaluation than the row's snapshot. A measurement standard, not a tunable.
SCORE_TOL = 0.005

LINE_RE = re.compile(
    r"^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d),(\d{3}) .*?\[([A-Z0-9]+)\] sizer veto: "
    r"SZ-045: manip suspect ([0-9.]+) >= veto ([0-9.]+)")


def local_offset_s(when: dt.datetime) -> float:
    """Seconds to ADD to a naive local timestamp to get UTC, for this box
    at that instant (DST-aware). Printed in the report - never assumed."""
    return -float(when.astimezone().utcoffset().total_seconds())


def parse_log_line(line: str) -> dict[str, Any] | None:
    """One sizer-veto line -> {'ts': utc_epoch, 'asset', 'score', 'veto'}
    or None. Pure."""
    m = LINE_RE.match(line)
    if not m:
        return None
    naive = dt.datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S")
    naive = naive.replace(microsecond=int(m.group(2)) * 1000)
    ts = naive.timestamp()          # naive -> local -> epoch (UTC) on this box
    return {"ts": ts, "asset": m.group(3), "score": float(m.group(4)),
            "veto": float(m.group(5))}


def load_events(path: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    with path.open(encoding="utf-8", errors="replace") as f:
        for line in f:
            e = parse_log_line(line)
            if e:
                out.append(e)
    out.sort(key=lambda e: e["ts"])
    return out


def load_stamped_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            if (r.get("disp") or "") != STAMP:
                continue
            try:
                ts = float(r.get("signal_ts") or "")
                ms = float(r.get("manip_suspect") or "")
            except ValueError:
                continue
            rows.append({"id": r.get("position_id") or "",
                         "asset": (r.get("asset") or "").upper(),
                         "signal_ts": ts, "manip_suspect": ms})
    return rows


def match_stamps(rows: list[dict[str, Any]], events: list[dict[str, Any]],
                 window_s: float = DEFAULT_WINDOW_S) -> list[dict[str, Any]]:
    """Attribute each stamped row to the nearest same-asset veto event AT OR
    AFTER its signal_ts within window_s. Pure. Returns one record per row
    with lag_s / event_score / score_delta, or matched=False."""
    by_asset: dict[str, list[dict[str, Any]]] = {}
    for e in events:
        by_asset.setdefault(e["asset"], []).append(e)
    keys = {a: [e["ts"] for e in es] for a, es in by_asset.items()}
    out = []
    for r in rows:
        es = by_asset.get(r["asset"])
        rec = dict(r, matched=False)
        if es:
            k = keys[r["asset"]]
            i = bisect.bisect_left(k, r["signal_ts"])       # at or after
            if i < len(es) and es[i]["ts"] - r["signal_ts"] <= window_s:
                e = es[i]
                rec.update(matched=True, lag_s=e["ts"] - r["signal_ts"],
                           event_score=e["score"], veto=e["veto"],
                           score_delta=e["score"] - r["manip_suspect"])
        out.append(rec)
    return out


def _q(vals: list[float], q: float) -> float | None:
    if not vals:
        return None
    s = sorted(vals)
    return s[min(len(s) - 1, int(q * (len(s) - 1)))]


def build_report(rows, events, window_s: float = DEFAULT_WINDOW_S) -> dict[str, Any]:
    log_start = events[0]["ts"] if events else None
    covered = [r for r in rows if log_start is not None and r["signal_ts"] >= log_start]
    recs = match_stamps(covered, events, window_s)
    m = [x for x in recs if x["matched"]]
    lags = [x["lag_s"] for x in m]
    deltas = [abs(x["score_delta"]) for x in m]
    disagree = [x for x in m if abs(x["score_delta"]) > SCORE_TOL]
    # THE SEAM, per event: the stored feature is BELOW the veto the sizer
    # applied, while the live score that produced the stamp was at/above it
    seam = [x for x in m if x["manip_suspect"] < x["veto"] <= x["event_score"]]
    # verdicts that landed on no row (the silently-dropped side)
    row_ts = {}
    for r in covered:
        row_ts.setdefault(r["asset"], []).append(r["signal_ts"])
    orphan = 0
    for e in events:
        ts = sorted(row_ts.get(e["asset"], []))
        i = bisect.bisect_right(ts, e["ts"]) - 1
        if i < 0 or e["ts"] - ts[i] > window_s:
            orphan += 1
    return {
        "read_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "window_s": window_s, "score_tol": SCORE_TOL,
        "log_events": len(events),
        "log_first_utc": (dt.datetime.fromtimestamp(log_start, dt.timezone.utc)
                          .isoformat(timespec="seconds") if log_start else None),
        "log_local_offset_s": (local_offset_s(dt.datetime.fromtimestamp(log_start))
                               if log_start else None),
        "stamped_rows_total": len(rows),
        "stamped_rows_before_log": len(rows) - len(covered),
        "stamped_rows_covered": len(covered),
        "matched": len(m),
        "unmatched": len(covered) - len(m),
        "lag_s_p50": _q(lags, 0.5), "lag_s_p90": _q(lags, 0.9),
        "lag_s_max": max(lags) if lags else None,
        "abs_score_delta_p50": _q(deltas, 0.5), "abs_score_delta_p90": _q(deltas, 0.9),
        "score_disagrees": len(disagree),
        "seam_rows": len(seam),
        "orphan_events": orphan,
        "records": recs,
    }


def render(rep: dict[str, Any]) -> str:
    L = [f"[K] read {rep['read_utc']}  window={rep['window_s']:.0f}s  "
         f"score_tol={rep['score_tol']}",
         f"[K] veto log: {rep['log_events']} sizer-path SZ-045 events from "
         f"{rep['log_first_utc']} (local->UTC offset applied: "
         f"{rep['log_local_offset_s']}s)",
         f"[K] stamped rows: {rep['stamped_rows_total']} total, "
         f"{rep['stamped_rows_before_log']} BEFORE the log starts (unauditable), "
         f"{rep['stamped_rows_covered']} covered",
         f"[K] matched {rep['matched']} / unmatched {rep['unmatched']}"]
    if rep["matched"]:
        L += [f"  lag registration -> verdict:  p50 {rep['lag_s_p50']:.0f}s  "
              f"p90 {rep['lag_s_p90']:.0f}s  max {rep['lag_s_max']:.0f}s",
              f"  |stored score - live score|:  p50 {rep['abs_score_delta_p50']:.3f}  "
              f"p90 {rep['abs_score_delta_p90']:.3f}",
              f"  stamps whose stored score disagrees with the live score "
              f"(> {rep['score_tol']}): {rep['score_disagrees']} of {rep['matched']} "
              f"= {rep['score_disagrees'] / rep['matched']:.1%}",
              f"  THE SEAM per event (stored < veto <= live): {rep['seam_rows']} "
              f"= {rep['seam_rows'] / rep['matched']:.1%} of matched"]
    L.append(f"[K] orphan verdicts (log events that landed on NO covered row within "
             f"the window): {rep['orphan_events']} of {rep['log_events']}")
    L += ["[D] only stamps after the log's first line are auditable; earlier ones are "
          "counted, not scored.",
          "[D] 'at or after' is the matching rule - a verdict cannot precede its candidate.",
          "[D] read-only; plants nothing; writes nothing."]
    return "\n".join(L)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--window", type=float, default=DEFAULT_WINDOW_S)
    ap.add_argument("--signal", default=str(SIGNAL_PATH))
    ap.add_argument("--log", default=str(LOG_PATH))
    args = ap.parse_args(argv)
    t0 = time.time()
    events = load_events(Path(args.log))
    rows = load_stamped_rows(Path(args.signal))
    rep = build_report(rows, events, args.window)
    rep["elapsed_s"] = round(time.time() - t0, 2)
    if args.json:
        slim = {k: v for k, v in rep.items() if k != "records"}
        print(json.dumps(slim, indent=2))
    else:
        print(render(rep))
    return 0


if __name__ == "__main__":
    sys.exit(main())
