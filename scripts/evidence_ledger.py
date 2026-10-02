"""scripts/evidence_ledger.py - one Banburismus sheet for every hypothesis the
research plane has ever tested (SAFE: reads tool outputs, decides nothing).

    python scripts/evidence_ledger.py                  # score the registry
    python scripts/evidence_ledger.py --write-status   # store statuses (memory)

Reads docs/quant/hypothesis_registry.json (what was registered, when, why)
and the newest outputs/reports/alpha_decay/alpha_decay_*.json (the per-block
observations). For each hypothesis it runs two anytime-valid e-processes
(core/evidence.py) at the registered primary horizon:

    e_exist  evidence the edge is above 0
    e_dead   evidence the edge is below the round trip 2c

THE ASYMMETRIC RULE (registered 2026-10-02, before the first ledger run):
the PAST may ELIMINATE, only the FUTURE may PROMOTE. Hindsight - a paper's,
the bot's, or the AI's that proposed the idea - inflates positives and
cannot fake a failure. So e_dead is taken over all data, e_exist only over
blocks dated on or after the hypothesis's forward_from. Both are read at
their running maximum (Ville: deciding at the first crossing is valid) and
an elimination is never overwritten. A tilt is judged against 0, a trip
against 2c. LIVE additionally requires e-BH (alpha 0.05) across the
hypothesis's family. [Corrected 2026-10-02 after code review: max(back,
forward) terminal e-values, stride overlap, e-BH demotion, use-blind bars.]

Observations overlap when the horizon spans several blocks; the series is
thinned to one block per horizon so consecutive bets do not share a
forward window (the e-process assumes each bet is placed before its
outcome is known).
"""
from __future__ import annotations

import argparse
import datetime as dt
import glob
import json
import math
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core import evidence as ev  # noqa: E402

REGISTRY = ROOT / "docs" / "quant" / "hypothesis_registry.json"
THRESHOLD = 20.0          # 1/alpha at alpha 0.05 = 13.0 dB
TWO_C = 45.0


def thin(t, horizon_h: float, block_h: float) -> np.ndarray:
    """One block per (block + horizon): a block's events have outcomes up to
    block_end + horizon, so the next bet may only start after that
    (review finding 8 - ceil(horizon / block) still overlapped)."""
    stride = max(1, math.ceil((block_h + horizon_h) / block_h))
    return np.arange(0, len(t), stride)


def _ts(day: str) -> float:
    return dt.datetime.fromisoformat(day).replace(tzinfo=dt.timezone.utc).timestamp()


def _sup(x: np.ndarray, null: float, bound: float, side: str) -> float:
    if len(x) == 0:
        return 1.0
    return float(np.max(ev.betting_eprocess(x, null, bound, side)))


def evaluate(h: dict, series: dict, two_c: float = TWO_C) -> dict:
    """e_dead: ONE e-process over the whole time-ordered series (the past may
    eliminate). e_exist: over forward blocks only (only the future may
    promote). Both read at their running maximum (first crossing). A tilt
    is judged against 0, a trip against the round trip 2c."""
    hh = [float(v) for v in series["h_hours"]]
    if float(h["horizon_h"]) not in hh:
        raise KeyError(f"{h['id']}: horizon {h['horizon_h']} h not in {hh}")
    use = h.get("use", "trip")
    bar = 0.0 if use == "tilt" else two_c
    k = hh.index(float(h["horizon_h"]))
    t = np.asarray(series["t"], float)
    x = np.array([row[k] if row[k] is not None else np.nan for row in series["x_bps"]], float)
    ok = np.isfinite(x)
    t, x = t[ok], x[ok]
    if len(t) > 1:
        block_h = float(np.min(np.diff(t))) / 3600.0
        keep = thin(t, float(h["horizon_h"]), block_h)
        t, x = t[keep], x[keep]
    fwd = t >= _ts(h["forward_from"])
    B = float(h["bound_bps"])
    e_dead = _sup(x, bar, B, "less")
    e_exist = _sup(x[fwd], 0.0, B, "greater")
    return {"id": h["id"], "use": use, "bar_bps": bar,
            "all": {"n": int(len(x)), "e_dead_sup": e_dead, "db_dead": ev.decibans(e_dead),
                    "mean_bps": float(np.mean(x)) if len(x) else None},
            "forward": {"n": int(fwd.sum()), "e_exist": e_exist,
                        "db_exist": ev.decibans(e_exist)},
            "e_dead_used": e_dead,
            "status": ev.status(e_exist, e_dead, THRESHOLD, use)}


def apply_e_bh(rows: list) -> None:
    """Promotion needs e-BH within the family; a demoted row keeps whatever
    its elimination evidence says (review finding 4)."""
    for fam in sorted({r["family"] for r in rows}):
        fam_rows = [r for r in rows if r["family"] == fam]
        keep = ev.e_bh({r["id"]: r["forward"]["e_exist"] for r in fam_rows})
        for r in fam_rows:
            if r["status"] in ("LIVE", "EDGE BELOW ROUND TRIP") and r["id"] not in keep:
                r["status"] = ev.status(0.0, r["e_dead_used"], THRESHOLD, r.get("use", "trip"))
                if r["status"] == "UNDECIDED":
                    r["status"] = "UNDECIDED (fails e-BH)"


def merge_status(registry: list, new: dict) -> None:
    """Failure memory is sticky: an ELIMINATED status is never overwritten."""
    for h in registry:
        if h["id"] in new and not str(h.get("status", "")).startswith("ELIMINATED"):
            h["status"] = new[h["id"]]


def _series_for(h: dict, report: dict):
    node = report.get(h["section"], {}).get(h["key"])
    return None if not isinstance(node, dict) else node.get("series")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--registry", default=str(REGISTRY))
    ap.add_argument("--report", default=None, help="alpha_decay JSON (default: newest)")
    ap.add_argument("--write-status", action="store_true")
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)
    reg_doc = json.loads(Path(args.registry).read_text(encoding="utf-8"))
    path = args.report or sorted(glob.glob(str(
        ROOT / "outputs" / "reports" / "alpha_decay" / "alpha_decay_*.json")))[-1]
    report = json.loads(Path(path).read_text(encoding="utf-8"))
    rows, missing = [], []
    for h in reg_doc["hypotheses"]:
        s = _series_for(h, report)
        if s is None:
            missing.append(h["id"])
            continue
        rows.append({**evaluate(h, s), "family": h["family"], "source": h["source"]})
    apply_e_bh(rows)
    print(f"evidence ledger - report {Path(path).name}; threshold {THRESHOLD:g} "
          f"(= {ev.decibans(THRESHOLD):.1f} dB); 2c {TWO_C:g} bps; "
          f"rule: past eliminates, only forward data promotes")
    print(f"{'hypothesis':<30}{'source':<11}{'use':<6}{'bar':>5}{'n':>6}{'dB below bar':>13}"
          f"{'fwd n':>7}{'dB exist':>10}  status")
    for r in sorted(rows, key=lambda r: (r["status"], r["id"])):
        a, f = r["all"], r["forward"]
        print(f"{r['id']:<30}{r['source']:<11}{r['use']:<6}{r['bar_bps']:>5.0f}{a['n']:>6}"
              f"{a['db_dead']:>+13.1f}{f['n']:>7}{f['db_exist']:>+10.1f}  {r['status']}")
    counts = {}
    for r in rows:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    print(f"reconcile: n={len(reg_doc['hypotheses'])} = scored {len(rows)} "
          f"({counts}) + no series {len(missing)} {missing} "
          f"[{'OK' if len(rows) + len(missing) == len(reg_doc['hypotheses']) else 'MISMATCH'}]")
    out_dir = Path(args.out) if args.out else ROOT / "outputs" / "reports" / "evidence_ledger"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    (out_dir / f"ledger_{stamp}.json").write_text(
        json.dumps({"report": Path(path).name, "rows": rows, "missing": missing},
                   indent=1), encoding="utf-8")
    if args.write_status:
        merge_status(reg_doc["hypotheses"], {r["id"]: r["status"] for r in rows})
        Path(args.registry).write_text(json.dumps(reg_doc, indent=1) + "\n", encoding="utf-8")
        print(f"statuses written to {args.registry}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
