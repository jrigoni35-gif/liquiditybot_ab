"""scripts/shadow_policy_report.py - grade the shadow traded-value rule.

Items 1b + 3 (operator ruling 2026-09-29). Report-only: reads
outputs/shadow_policy.csv (model p at every real candidate registration) and
outputs/signal_history.csv (outcomes), writes nothing under outputs/, touches
no decision path.

THE RULE UNDER TEST: enter iff the predicted value of this candidate is > 0,
where the prediction is the mean realized label return of PAST candidates in
the same model-p bin. Since 1a the label bet IS the bracket bet (same
geometry function, same cost input), so the label return is the bracket's
value before the give-back overlay; traded outcomes of candidates the live
bot actually took are reported beside it.

NO LOOK-AHEAD. For each shadow row, bins are fitted only on shadow rows whose
label RESOLVED (signal_history `ts`) strictly before that row's `ts`. A bin
with fewer than --min-bin past outcomes makes NO decision (never a guess).

CS-1: every shadow row lands in exactly one bucket, reconciled to n.
Promotion: docs/law/shadow_policy_promotion.md - this report never decides.

    python scripts/shadow_policy_report.py [--shadow P] [--history P] [--json]
"""
from __future__ import annotations

import argparse
import bisect
import csv
import json
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
from core.cohort import COUNTING_STANDARD, reconcile  # noqa: E402

N_BINS = 10
MIN_BIN = 20
PROMOTE_MIN_N = 200          # docs/law/shadow_policy_promotion.md


def _f(x):
    try:
        v = float(x)
        return v if v == v else None
    except (TypeError, ValueError):
        return None


def _day(ts: float) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%d")


def load(shadow_path: Path, history_path: Path):
    shadow = []
    if shadow_path.exists():
        with open(shadow_path, newline="", encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                ts, p = _f(r.get("ts")), _f(r.get("model_p"))
                if ts is not None and p is not None and r.get("candidate_id"):
                    shadow.append({"ts": ts, "cid": r["candidate_id"],
                                   "p": p, "fp": r.get("decision_fp", "")})
    label, traded = {}, {}
    if history_path.exists():
        with open(history_path, newline="", encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                cid, ret = r.get("candidate_id") or "", _f(r.get("label_ret_pct"))
                res = _f(r.get("ts"))
                if not cid or ret is None or res is None:
                    continue
                (traded if r.get("source") == "live" else label)[cid] = (
                    ret * 100.0, res)                  # percent -> bps
    return sorted(shadow, key=lambda s: s["ts"]), label, traded


def _bin_edges(ps: list) -> list:
    s = sorted(ps)
    return [s[int(len(s) * k / N_BINS)] for k in range(1, N_BINS)]


def grade(shadow: list, label: dict, traded: dict, min_bin: int = MIN_BIN):
    """Walk-forward decisions + CS-1 buckets. Pure."""
    resolved = sorted(((label[s["cid"]][1], s["p"], label[s["cid"]][0])
                       for s in shadow if s["cid"] in label))
    res_ts = [r[0] for r in resolved]
    rows, buckets = [], {"unresolved": 0, "undecided": 0,
                         "would-enter": 0, "would-skip": 0}
    for s in shadow:
        out = label.get(s["cid"])
        if out is None:
            buckets["unresolved"] += 1
            continue
        k = bisect.bisect_left(res_ts, s["ts"])      # strictly-before only
        past = resolved[:k]
        pred = None
        if len(past) >= min_bin * 2:
            edges = _bin_edges([p for _, p, _ in past])
            b = bisect.bisect_right(edges, s["p"])
            same = [v for _, p, v in past
                    if bisect.bisect_right(edges, p) == b]
            if len(same) >= min_bin:
                pred = statistics.fmean(same)
        if pred is None:
            buckets["undecided"] += 1
            continue
        enter = pred > 0
        buckets["would-enter" if enter else "would-skip"] += 1
        rows.append({"cid": s["cid"], "p": s["p"], "pred": pred,
                     "enter": enter, "net": out[0], "close_day": _day(out[1]),
                     "traded": traded.get(s["cid"], (None,))[0]})
    return rows, reconcile(len(shadow), buckets)


def summarize(rows: list, counting: dict, reps: int = 4000,
              seed: int = 7) -> dict:
    import era_readout as er                       # the registered bootstrap
    ent = [r for r in rows if r["enter"]]
    live = [r for r in rows if r["traded"] is not None]

    def block(rs, key="net"):
        if not rs:
            return {"n": 0}
        vals = [r[key] for r in rs]
        ci = er.day_block_bootstrap(rs, key, reps=reps, seed=seed)
        return {"n": len(rs), "mean_bps": round(statistics.fmean(vals), 2),
                "ci": [round(ci.get("lo", float("nan")), 2),
                       round(ci.get("hi", float("nan")), 2)],
                "days": ci.get("days")}
    out = {"standard": COUNTING_STANDARD, "counting": counting,
           "all_decided_label": block(rows),
           "would_enter_label": block(ent),
           "live_taken_traded": block(
               [dict(r, net=r["traded"]) for r in live])}
    we = out["would_enter_label"]
    lo = (we.get("ci") or [None])[0]
    if we.get("n", 0) < PROMOTE_MIN_N:
        verdict = f"NOT YET - {we.get('n', 0)}/{PROMOTE_MIN_N} would-enter outcomes"
    elif lo is None or not lo > 0:
        verdict = "NOT PROMOTABLE - would-enter CI does not clear zero"
    else:
        verdict = ("EVIDENCE MET for the report's part - promotion still needs "
                   "the overfit battery + an operator decision record")
    out["promotion"] = verdict
    return out


def render(s: dict) -> str:
    L = ["shadow traded-value rule - REPORT ONLY (docs/law/shadow_policy_promotion.md)",
         s["counting"]["line"]]
    for k in ("all_decided_label", "would_enter_label", "live_taken_traded"):
        b = s[k]
        L.append(f"  {k:<20} n={b.get('n', 0):<5}"
                 + (f" mean {b['mean_bps']:+.1f} bps  95% CI [{b['ci'][0]:+.1f}, "
                    f"{b['ci'][1]:+.1f}]  day-blocks {b.get('days')}"
                    if b.get("n") else ""))
    L.append(f"  promotion: {s['promotion']}")
    return "\n".join(L)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--shadow", default=str(ROOT / "outputs" / "shadow_policy.csv"))
    ap.add_argument("--history", default=str(ROOT / "outputs" / "signal_history.csv"))
    ap.add_argument("--min-bin", type=int, default=MIN_BIN)
    ap.add_argument("--json", action="store_true")
    ns = ap.parse_args(argv)
    shadow, label, traded = load(Path(ns.shadow), Path(ns.history))
    rows, counting = grade(shadow, label, traded, ns.min_bin)
    s = summarize(rows, counting)
    print(json.dumps(s, indent=1, default=str) if ns.json else render(s))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
