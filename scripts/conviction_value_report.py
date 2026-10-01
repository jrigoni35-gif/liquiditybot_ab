"""scripts/conviction_value_report.py - conviction-equivalent evidence NOW,
instead of 2 conviction trades a week. REPORT-ONLY: reads the corpus, writes
nothing (audit isolated to a temp file), decides nothing.

WHY (operator 2026-10-01): "derive new information for conviction labels to
help for the next 2 weeks". A conviction entry is one whose OWN model p
clears the sizer's net-break-even bar (SZ-023 dispositions: e.g. "p 0.28
below bar 0.63"); it fires ~2x/week, so n=50 conviction trades is ~6 months
away. But every candidate is labeled with the SAME bracket a trade uses (the
2026-09-29 1a change: traded geometry = label geometry). What conviction
needs to know - does realized win rate RISE with model p, and does the top
of the range clear break-even - can be read from candidate rows, if each row
is scored by a model that never saw it.

METHOD. The bot's own ml.walkforward.evaluate_and_select on the production
corpus (ml.history.store_for_config + main.py's loader arguments), with the
TIME-based purge (sig, res; label_span = ml.label_max_bars). The SELECTED
family's out-of-fold p (`oof_p`, rows `oof_idx`) is leak-free by
construction. Rows are binned by OOF p QUANTILE (rank, not calibrated
level: the deployed p is calibrated and shrunk, the ranking is not). Per
bin: label win rate vs the fair-game break-even p* = (b + C)/(a + b) at the
corpus's median geometry, with a day-block bootstrap CI (calendar days are
the effective-n unit; day-level trends move whole days).

FORWARD COMPANION: outputs/shadow_policy.csv logs the DEPLOYED model's p at
every real registration since 2026-09-29; scripts/shadow_policy_report.py
grades it walk-forward. That is the clean forward instrument for the next
two weeks; this report is the historical backfill beside it.

Caveat printed with every run: a label win is not a traded win - fills,
slippage and fees differ (lineage agreement candidate-vs-live ~83%).

Usage: python scripts/conviction_value_report.py [--root DIR] [--bins 10]
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

BOOT = 1000
SEED = 5


def load(root: Path):
    from ml.history import store_for_config
    cfg = json.loads((root / "config.json").read_text(encoding="utf-8"))
    ml = cfg.get("ml", {})
    sw = ml.get("sample_weights", {})
    hs = store_for_config(ml, path=str(root / "outputs" / "signal_history.csv"))
    X, y, w, sig, res = hs.load_training_data(
        half_life_days=float(sw.get("half_life_days", 30)),
        candidate_weight=float(sw.get("candidate_weight", 0.4)),
        manip_discount=float(sw.get("manip_discount", 0.5)),
        return_label_times=True, weights_cfg=sw,
        telemetry_cfg=ml.get("telemetry", {}), epoch_cfg=ml.get("epoch", {}),
        era_cfg=ml.get("era_exclusion", {}))
    from ml.contracts import get_contract
    keep = get_contract().check_matrix(X)["keep"]
    X, y, w, sig, res = X[keep], y[keep], w[keep], sig[keep], res[keep]
    return cfg, ml, hs, X, y, w, np.asarray(sig, float), np.asarray(res, float)


def oof(ml: dict, hs, X, y, w, sig, res) -> tuple:
    from ml.walkforward import evaluate_and_select
    n_live = int((hs.last_load_stats or {}).get("live_clean", 0))
    r = evaluate_and_select(
        X, y, label_span=int(ml.get("label_max_bars", 96)), sample_weight=w,
        sig=sig, res=res, n_live=n_live,
        select_cfg=ml.get("model_selection", {}))
    fam = r.get("selected")
    return fam, np.asarray(r[fam]["oof_p"], float), \
        np.asarray(r["oof_idx"], int), r[fam]["mean_auc"]


def fair_p(root: Path) -> tuple:
    """p* at the corpus's median era-h432 label geometry (pt, sl, cost)."""
    import csv
    pts, sls, costs = [], [], []
    with open(root / "outputs" / "signal_history.csv", newline="",
              encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if r.get("label_era") != "triple_barrier_h432" \
                    or r.get("source") == "live":
                continue
            try:
                pt, sl = float(r["pt_frac"]), float(r["sl_frac"])
                ret = float(r["label_ret_pct"])
            except (KeyError, TypeError, ValueError):
                continue
            pts.append(pt)
            sls.append(sl)
            if r.get("barrier") == "tb_pt":
                costs.append(pt - ret / 100.0)
    a, b, c = (float(np.median(pts)), float(np.median(sls)),
               float(np.median(costs)) if costs else 0.0)
    return (b + c) / (a + b), a, b, c


def bins(p, y, day, n_bins, rng):
    order = np.argsort(p, kind="stable")
    edges = np.array_split(order, n_bins)
    out = []
    for k, ix in enumerate(edges):
        days = np.unique(day[ix])
        by = {d: ix[day[ix] == d] for d in days}
        boots = []
        for _ in range(BOOT):
            pick = rng.choice(days, len(days))
            sel = np.concatenate([by[d] for d in pick])
            boots.append(y[sel].mean())
        out.append({"bin": k + 1, "n": int(len(ix)), "days": int(len(days)),
                    "p_lo": float(p[ix].min()), "p_hi": float(p[ix].max()),
                    "win": float(y[ix].mean()),
                    "ci": tuple(float(v) for v in
                                np.percentile(boots, [2.5, 97.5]))})
    return out


def run(root: Path, n_bins: int = 10) -> dict:
    from core.audit import configure_audit
    configure_audit(Path(tempfile.mkdtemp()) / "audit.jsonl")   # never outputs/
    cfg, ml, hs, X, y, w, sig, res = load(root)
    fam, p, idx, mean_auc = oof(ml, hs, X, y, w, sig, res)
    yy, day = y[idx].astype(float), (sig[idx] // 86400).astype(int)
    ps, a, b, c = fair_p(root)
    rng = np.random.default_rng(SEED)
    top = {}
    for q in (0.90, 0.95, 0.99):
        m = p >= np.quantile(p, q)
        top[q] = {"n": int(m.sum()), "days": int(len(np.unique(day[m]))),
                  "win": float(yy[m].mean())}
    return {"family": fam, "oof_rows": int(len(p)), "rows": int(len(y)),
            "oof_mean_auc": float(mean_auc), "p_star": ps,
            "geometry": {"pt": a, "sl": b, "cost": c},
            "bins": bins(p, yy, day, n_bins, rng), "top": top,
            "base_win": float(yy.mean())}


def render(r: dict) -> str:
    L = [f"conviction_value - walk-forward OOF p ({r['family']}, mean OOF "
         f"AUC {r['oof_mean_auc']:.3f}) on {r['oof_rows']} of {r['rows']} "
         f"training rows; base win {r['base_win']:.3f}",
         f"break-even p* = {r['p_star']:.3f} at median geometry pt "
         f"{r['geometry']['pt']:.4f} / sl {r['geometry']['sl']:.4f} / cost "
         f"{r['geometry']['cost']:.4f}",
         "CAVEAT: a label win is not a traded win (fills, slippage, fees; "
         "candidate-vs-live agreement ~83%).", "",
         "bin  n      days  OOF p range        win rate  [95% day-block CI]"
         "   vs p*"]
    for b in r["bins"]:
        flag = ("ABOVE" if b["ci"][0] > r["p_star"] else
                "below" if b["ci"][1] < r["p_star"] else "spans")
        L.append(f"{b['bin']:3d}  {b['n']:5d}  {b['days']:4d}  "
                 f"[{b['p_lo']:.3f}, {b['p_hi']:.3f}]   {b['win']:.3f}   "
                 f"[{b['ci'][0]:.3f}, {b['ci'][1]:.3f}]   {flag}")
    L.append("")
    for q, t in r["top"].items():
        L.append(f"top {100 - 100 * q:.0f}% by OOF p: n {t['n']} over "
                 f"{t['days']} days, win {t['win']:.3f} vs p* {r['p_star']:.3f}")
    return "\n".join(L)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--root", type=Path, default=ROOT)
    ap.add_argument("--bins", type=int, default=10)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    t = time.time()
    r = run(a.root, a.bins)
    print(f"read {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(t))}")
    print(json.dumps(r, indent=1, default=float) if a.json else render(r))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
