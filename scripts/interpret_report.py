"""
scripts/interpret_report.py — post-hoc interpretability report (offline,
REPORT-ONLY: reads the deployed champion + training corpus, writes
outputs/interpret_report.{md,json}, never touches config or state).

Four sections, each the survivor of an argued school (ml/interpret.py
docstring + docs/INTERPRET.md):
  1. Grouped permutation importance (Hooker/de-Prado clustered MDA) on a
     time-ordered held-out tail — can honestly report "nothing matters".
  2. Exact attribution fingerprint (interventional SHAP for gbt, exact
     linear for logistic, refusal for mlp) — where the model's margin
     actually comes from, feature by feature.
  3. Additivity audit — machine-precision proof the explainer is exact
     on THIS model (the anti-fooling check: no sampler to attack).
  4. Attribution drift — fingerprint rotation between the two halves of
     the evaluation window; reasons can rotate before scores move.

Usage: python scripts/interpret_report.py [--config config.json]
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ml.features import FEATURE_NAMES                       # noqa: E402
from ml.history import HistoryStore                         # noqa: E402
from ml.interpret import (attribution_profile,              # noqa: E402
                          cluster_features, explain, gbt_margin,
                          grouped_permutation_importance, profile_rotation)
from ml.meta_model import MetaModelService                  # noqa: E402

DEFAULTS = {"corr_cluster_thr": 0.7, "eval_frac": 0.3, "purge_rows": 24,
            "n_repeats": 5, "topk": 15, "profile_rows": 200,
            "drift_cos_warn": 0.8, "background_rows": 64}


def _names(g: list) -> str:
    return " + ".join(FEATURE_NAMES[j] if j < len(FEATURE_NAMES) else f"f{j}"
                      for j in g)


def build_report(model, calibrator, X, y, cfg: dict,
                 background=None) -> tuple:
    """Pure core: (markdown, json-dict). Split is time-ordered with a
    purge gap so evaluation rows never overlap the correlation-structure
    / fingerprint-baseline window."""
    c = {**DEFAULTS, **(cfg or {})}
    n = len(X)
    n_eval = max(int(n * float(c["eval_frac"])), 10)
    gap = int(c["purge_rows"])
    n_train = max(n - n_eval - gap, 10)
    Xtr, Xev, yev = X[:n_train], X[n - n_eval:], y[n - n_eval:]
    rep: dict = {"rows": int(n), "train_rows": int(n_train),
                 "eval_rows": int(n_eval),
                 "kind": getattr(model, "kind", "?")}
    md = ["# Interpretability report", "",
          f"model: **{rep['kind']}** · corpus {n} rows · eval tail "
          f"{n_eval} rows (purge gap {gap})", ""]

    def predict(A):
        p = model.predict_proba(A)
        return calibrator.transform(p) if calibrator is not None else p

    # 1 — clustered permutation importance (held-out tail only)
    groups = cluster_features(Xtr, float(c["corr_cluster_thr"]))
    imp = grouped_permutation_importance(predict, Xev, yev, groups,
                                         n_repeats=int(c["n_repeats"]))
    rep["clusters"] = len(groups)
    rep["importance"] = [{**r, "names": _names(r["features"])} for r in imp]
    md += ["## Clustered permutation importance (OOS tail, Brier delta)",
           "", "positive = model needs it out-of-sample; ~0 = decorative; "
           "negative = actively hurts", "",
           "| cluster | dBrier | ±std |", "|---|---|---|"]
    for r in rep["importance"][:int(c["topk"])]:
        md.append(f"| {r['names']} | {r['delta_brier_mean']:+.5f} "
                  f"| {r['delta_brier_std']:.5f} |")
    useless = sum(1 for r in imp if r["delta_brier_mean"] <= 0)
    md += ["", f"{useless}/{len(imp)} clusters show zero-or-negative OOS "
           f"contribution — candidates for removal at the next conscious "
           f"schema revision (never mid-flight).", ""]

    # 2 — exact attribution fingerprint
    rows = Xev[-int(c["profile_rows"]):]
    prof = attribution_profile(model, rows, background)
    rep["fingerprint"] = {FEATURE_NAMES[j]: round(float(v), 6)
                          for j, v in enumerate(prof)
                          if j < len(FEATURE_NAMES)}
    md += ["## Attribution fingerprint (exact, share of mean |phi|)", ""]
    if prof.sum() <= 0:
        e = explain(model, X[0], background)
        md += [f"refused: {e.get('refusal', 'no exact attribution')}", ""]
        rep["refusal"] = e.get("refusal")
    else:
        order = np.argsort(-prof)[:int(c["topk"])]
        md += ["| feature | share |", "|---|---|"]
        md += [f"| {FEATURE_NAMES[j]} | {prof[j]:.1%} |" for j in order]
        md.append("")

    # 3 — additivity audit (gbt only: margin is reconstructible exactly)
    gm = model.b if getattr(model, "kind", "") == "blend" else model
    if getattr(gm, "kind", "") == "gbt" and background is not None:
        gaps = []
        for row in rows[:25]:
            e = explain(gm, row, background)
            gaps.append(abs(e["base"] + e["contrib"].sum()
                            - gbt_margin(gm, row)))
        rep["additivity_max_gap"] = float(max(gaps))
        ok = rep["additivity_max_gap"] < 1e-9
        rep["additivity_ok"] = bool(ok)
        md += ["## Additivity audit",
               f"max |base + sum(phi) - margin| = "
               f"{rep['additivity_max_gap']:.2e} -> "
               f"{'EXACT' if ok else 'BROKEN - do not trust this report'}",
               ""]

    # 4 — attribution drift across the eval window
    half = len(Xev) // 2
    if half >= 5 and prof.sum() > 0:
        p1 = attribution_profile(model, Xev[:half], background)
        p2 = attribution_profile(model, Xev[half:], background)
        cos = profile_rotation(p1, p2)
        rep["attribution_drift_cos"] = round(cos, 4)
        warn = cos < float(c["drift_cos_warn"])
        rep["attribution_drift_warn"] = bool(warn)
        md += ["## Attribution drift",
               f"fingerprint cosine (early vs late eval half): {cos:.3f}"
               + (f" — ROTATED below {c['drift_cos_warn']}: the model is "
                  f"leaning on different features than it just was; "
                  f"treat the next retrain gate with suspicion"
                  if warn else " — stable"), ""]
    return "\n".join(md) + "\n", rep


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=str(ROOT / "config.json"))
    args = ap.parse_args()
    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    ml_cfg = config.get("ml", {})
    svc = MetaModelService(ml_cfg)
    if svc.model is None:
        print("no trained champion - nothing to interpret")
        return 0
    store = HistoryStore(ml_cfg.get("history_path",
                                    "outputs/signal_history.csv"))
    # era-gated training exclusion (docs/quant/2026-07-26_era_exclusion.md):
    # interpretability must attribute over the SAME rows the deployed model
    # trained on, or a feature's SHAP/permutation story reflects data the
    # champion never saw (docs/quant/pbo_admission_policy.md cross-consumer
    # prerequisite).
    era_cfg = ml_cfg.get("era_exclusion", {})
    X, y, _w = store.load_training_data(era_cfg=era_cfg)
    if len(X) < 60:
        print(f"only {len(X)} rows - too few for an honest held-out tail")
        return 0
    background = None
    try:
        art = json.loads(Path(svc.model_path).read_text(encoding="utf-8"))
        bg = art.get("background")
        background = np.asarray(bg, float) if bg else None
    except (OSError, json.JSONDecodeError, ValueError):
        pass
    if background is None:
        from ml.interpret import background_sample
        cut = max(len(X) - int(len(X) * 0.3), 1)
        background = np.asarray(background_sample(
            X[:cut], int(ml_cfg.get("interpret", {})
                         .get("background_rows", 64))), float)
    md, rep = build_report(svc.model, svc.calibrator, X, y,
                           ml_cfg.get("interpret", {}), background)
    out_md = ROOT / "outputs" / "interpret_report.md"
    out_js = ROOT / "outputs" / "interpret_report.json"
    out_md.parent.mkdir(exist_ok=True)
    out_md.write_text(md, encoding="utf-8")
    out_js.write_text(json.dumps(rep, indent=1), encoding="utf-8")
    print(md)
    print(f"written: {out_md} / {out_js}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
