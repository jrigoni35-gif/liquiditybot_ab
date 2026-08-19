"""scripts/ground_truth_metrics.py — classifier ground-truth battery (report-only).

Operator request 2026-08-20: the sklearn/scipy metrics catalog, implemented
where it ALIGNS and rejected where it misleads. This repo is numpy-only by
design (ml/models.py hand-rolls its models; sklearn/scipy are absent and
import-integrity forbids requiring them), so every metric here is
implemented from its definition and pinned by tests against hand-computed
fixtures.

STRATEGIC ALIGNMENT (the triage, recorded where the code lives):
  ADOPT  confusion matrix + precision/recall/F1 — but ONLY at the DEPLOYED
         operating point (the derived p-bar), never a floating 0.5: a
         threshold metric without a declared threshold is theater.
  ADOPT  PR-AUC (average precision) — at base rate ~0.21 it, not ROC-AUC,
         is the headline discrimination number (Saito & Rehmsmeier 2015);
         ROC-AUC is still printed beside it (ml.models.auc_score, the
         battery's own implementation) for continuity with OF-1.
  ADOPT  KS two-sample per feature, train-era vs recent window — the
         continuous complement to the deployed PSI drift vote (PSI bins,
         KS doesn't; small-n power caveat printed with every table).
  ADOPT  chi-square GoF on the triple-barrier reason mix (tb_pt/tb_sl/
         tb_time) recent vs corpus expectation — the p-value companion to
         the era_mix_drift TVD alarm; expected-count floor (>=5) enforced,
         test withheld below it (validity condition, not a formality).
  ADAPT  Bland-Altman — its literature use is METHOD agreement (Bland &
         Altman 1986), not prediction accuracy. Adapted to the referee
         lattice: paired per-trip gross% from the Python reconstruction vs
         the C++ diode report when one exists; mean bias + limits of
         agreement. Absent diode output -> section honestly skipped.
  REJECT accuracy — at 0.21 prevalence "always predict loss" scores 0.79;
         a number that rewards saying nothing is not a metric here.
  REJECT MAE/RMSE/R^2 — regression scores with no regression target: the
         model emits win PROBABILITIES, and the Brier score the judge
         already runs IS the mean squared error of those probabilities
         (proper scoring rule; Harrell). RMSE would be sqrt(Brier) wearing
         a costume, R^2 its renormalization; nothing is added.

Report-only: reads the SAME corpus the overfit battery loads
(scripts.overfit_check.load_dataset — era fence, hygiene, weights included)
and the SAME purged walk-forward OOF machinery (ml.overfit.train_test_gap
return_oof=True), so no new evaluation convention is invented. Corpus
provenance prints on the summary line, per the read-what-it-measured law.
Writes outputs/ground_truth_metrics.{md,json}; never touches config,
state, or any decision path.
"""
import json
import math
import os
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

OUT = ROOT / "outputs"
# rebindable module attrs (LOG_PATH lesson): tests point these at tmp
REPORT_MD = OUT / "ground_truth_metrics.md"
REPORT_JSON = OUT / "ground_truth_metrics.json"
DIODE_JSON = OUT / "diode_report.json"      # optional: C++ referee output


# --- metric implementations (numpy-only, each pinned by tests) -------------

def confusion(y_true, y_pred):
    """[[tn, fp], [fn, tp]] — sklearn's layout for labels (0, 1)."""
    y_true = np.asarray(y_true).astype(int)
    y_pred = np.asarray(y_pred).astype(int)
    tp = int(np.sum((y_true == 1) & (y_pred == 1)))
    tn = int(np.sum((y_true == 0) & (y_pred == 0)))
    fp = int(np.sum((y_true == 0) & (y_pred == 1)))
    fn = int(np.sum((y_true == 1) & (y_pred == 0)))
    return [[tn, fp], [fn, tp]]


def prf1(cm):
    """precision, recall, F1 for the positive class from confusion()."""
    (_tn, fp), (fn, tp) = cm
    prec = tp / (tp + fp) if (tp + fp) else 0.0
    rec = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
    return prec, rec, f1


def average_precision(y_true, y_score):
    """PR-AUC as average precision: sum over positives of precision at each
    positive's rank (the sklearn 'AP' estimator, no interpolation)."""
    y_true = np.asarray(y_true).astype(int)
    y_score = np.asarray(y_score, float)
    order = np.argsort(-y_score, kind="stable")
    yt = y_true[order]
    n_pos = int(yt.sum())
    if n_pos == 0:
        return 0.0
    tp_cum = np.cumsum(yt)
    ranks = np.arange(1, len(yt) + 1)
    precision_at = tp_cum / ranks
    return float(np.sum(precision_at * yt) / n_pos)


def ks_2samp(a, b):
    """Two-sample Kolmogorov–Smirnov: (D, p) with the asymptotic p of the
    Kolmogorov distribution (Massey 1951). Small-n caveat: below ~25 per
    sample the asymptotic p is rough — the caller prints n beside it."""
    a = np.sort(np.asarray(a, float))
    b = np.sort(np.asarray(b, float))
    n1, n2 = len(a), len(b)
    if n1 == 0 or n2 == 0:
        return 0.0, 1.0
    both = np.concatenate([a, b])
    cdf1 = np.searchsorted(a, both, side="right") / n1
    cdf2 = np.searchsorted(b, both, side="right") / n2
    d = float(np.max(np.abs(cdf1 - cdf2)))
    en = math.sqrt(n1 * n2 / (n1 + n2))
    lam = (en + 0.12 + 0.11 / en) * d
    # Q_KS(lam->0) = 1 exactly; the alternating series oscillates +/-2
    # there and converges to garbage (caught by the identical-samples
    # test pin) - the same small-lambda guard Numerical Recipes uses.
    if lam < 0.2:
        return d, 1.0
    # Kolmogorov survival function, alternating series (standard 100-term cap)
    p = 0.0
    for k in range(1, 101):
        term = 2 * (-1) ** (k - 1) * math.exp(-2 * (k * lam) ** 2)
        p += term
        if abs(term) < 1e-10:
            break
    return d, float(min(max(p, 0.0), 1.0))


def _gammainc_upper_reg(s, x):
    """Regularized upper incomplete gamma Q(s, x) via series/continued
    fraction (Numerical Recipes 6.2) — for the chi-square survival
    function. math.lgamma keeps it dependency-free."""
    if x < 0 or s <= 0:
        return float("nan")
    if x == 0:
        return 1.0
    if x < s + 1.0:
        # lower series -> P, return 1-P
        term = 1.0 / s
        total = term
        a = s
        for _ in range(500):
            a += 1.0
            term *= x / a
            total += term
            if abs(term) < abs(total) * 1e-14:
                break
        p = total * math.exp(-x + s * math.log(x) - math.lgamma(s))
        return 1.0 - p
    # continued fraction for Q directly
    b = x + 1.0 - s
    c = 1e300
    d = 1.0 / b
    h = d
    for i in range(1, 500):
        an = -i * (i - s)
        b += 2.0
        d = an * d + b
        if abs(d) < 1e-300:
            d = 1e-300
        c = b + an / c
        if abs(c) < 1e-300:
            c = 1e-300
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < 1e-14:
            break
    return h * math.exp(-x + s * math.log(x) - math.lgamma(s))


def chisquare(f_obs, f_exp):
    """(chi2, p, valid) — GoF with the expected-count>=5 validity flag."""
    f_obs = np.asarray(f_obs, float)
    f_exp = np.asarray(f_exp, float)
    valid = bool(np.all(f_exp >= 5.0))
    with np.errstate(divide="ignore", invalid="ignore"):
        chi2 = float(np.sum(np.where(f_exp > 0,
                                     (f_obs - f_exp) ** 2 / f_exp, 0.0)))
    df = max(len(f_obs) - 1, 1)
    p = _gammainc_upper_reg(df / 2.0, chi2 / 2.0)
    return chi2, float(p), valid


def bland_altman(x, y):
    """Method-agreement stats on paired measurements: mean bias, sd of
    differences, 95% limits of agreement (Bland & Altman 1986)."""
    x = np.asarray(x, float)
    y = np.asarray(y, float)
    d = x - y
    bias = float(np.mean(d))
    sd = float(np.std(d, ddof=1)) if len(d) > 1 else 0.0
    return {"n": int(len(d)), "bias": bias, "sd_diff": sd,
            "loa_low": bias - 1.96 * sd, "loa_high": bias + 1.96 * sd}


# --- report ----------------------------------------------------------------

def _deployed_bar(cfg) -> float:
    """The DEPLOYED operating threshold: derived p-bar (net-Kelly breakeven
    + margin) exactly as position_sizer computes it, floored by min_p_win.
    Mirrors the config doc's formula; if the mode is 'absolute', the
    literal bar. Falls back to 0.5 with a loud tag only if config is
    unreadable (never silently)."""
    try:
        ps = cfg.get("position_sizer", {})
        if str(ps.get("p_bar_mode", "derived")) != "derived":
            return float(ps.get("min_p_win", 0.5))
        pt = cfg.get("profit_taking", {})
        # b_net: reward/risk after round-trip fees, from the same knobs the
        # sizer reads. Kept intentionally simple: tp/sl distance ratio.
        tp = float(pt.get("target_pct", 2.0))
        sl = float(cfg.get("risk", {}).get("stop_loss_pct", 1.5))
        fee_bps = 2.0 * float(cfg.get("order_manager", {})
                              .get("maker_fee_bps", 25.0))
        b_net = max((tp - fee_bps / 100.0) / max(sl + fee_bps / 100.0, 1e-9),
                    1e-9)
        bar = 1.0 / (1.0 + b_net) + float(ps.get("p_bar_edge_margin", 0.0))
        return max(bar, float(ps.get("min_p_win", 0.0)))
    except Exception:                                    # noqa: BLE001
        return 0.5


def build_report() -> dict:
    from ml.overfit import train_test_gap
    from ml.models import auc_score
    from scripts.overfit_check import load_dataset

    t0 = time.time()
    X, y, w, sig, res, corpus_note, _n_live = load_dataset()
    on_synth = "SYNTHETIC" in str(corpus_note)
    cfg = {}
    try:
        cfg = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        pass
    span = int(cfg.get("ml", {}).get("label_max_bars", 432))

    gaps = train_test_gap(X, y, label_span=span, sample_weight=w, sig=sig,
                          res=res, return_oof=True)
    fam = None
    try:
        st = json.loads((OUT / "status.json").read_text(encoding="utf-8"))
        fam = st.get("ml", {}).get("model_kind")
    except (OSError, ValueError):
        pass
    if fam not in gaps:
        fam = next((k for k in ("logistic", "gbt", "mlp") if k in gaps), None)
    g = gaps.get(fam) or {}
    oof_idx = np.asarray(g.get("oof_idx", []), int)
    oof_pred = np.asarray(g.get("oof_pred", []), float)

    rep: dict = {"generated_at": time.time(),
                 "corpus": str(corpus_note).strip(),
                 "on_synthetic": bool(on_synth),
                 "family": fam, "n_rows": int(len(y)),
                 "n_oof": int(len(oof_idx)),
                 "rejected": {
                     "accuracy": "misleads at 0.21 prevalence",
                     "mae_rmse_r2": "RMSE=sqrt(Brier), zero new content; MAE "
                                    "improper on probabilities (Gneiting&"
                                    "Raftery 2007); R2 ill-posed on 0/1"}}

    if len(oof_idx):
        yt = np.asarray(y, int)[oof_idx]
        bar = _deployed_bar(cfg)
        yp = (oof_pred >= bar).astype(int)
        cm = confusion(yt, yp)
        prec, rec, f1 = prf1(cm)
        rep["operating_point"] = {
            "threshold": round(bar, 4),
            "threshold_kind": "deployed derived p-bar",
            "confusion": cm,
            "precision": round(prec, 4), "recall": round(rec, 4),
            "f1": round(f1, 4),
            "base_rate": round(float(yt.mean()), 4)}
        rep["discrimination"] = {
            "pr_auc": round(average_precision(yt, oof_pred), 4),
            "pr_auc_null": round(float(yt.mean()), 4),
            "roc_auc": round(float(auc_score(yt, oof_pred)), 4),
            "headline": "pr_auc (base rate ~0.21: Saito&Rehmsmeier 2015)"}

    # KS drift: first vs last third of the (time-ordered) corpus, per feature
    ks_rows = []
    n = len(X)
    if n >= 60 and not on_synth:
        a_sl, b_sl = slice(0, n // 3), slice(2 * n // 3, n)
        try:
            from ml.features import FEATURE_NAMES
            names = list(FEATURE_NAMES)
        except Exception:                                # noqa: BLE001
            names = [f"f{i}" for i in range(X.shape[1])]
        for j in range(min(X.shape[1], len(names))):
            d, p = ks_2samp(X[a_sl, j], X[b_sl, j])
            ks_rows.append({"feature": names[j], "D": round(d, 4),
                            "p": round(p, 6)})
        ks_rows.sort(key=lambda r: -r["D"])
    rep["ks_train_vs_recent"] = {
        "note": "first vs last third of corpus, asymptotic p; complements "
                "the deployed PSI vote (PSI bins, KS does not). MULTIPLE-"
                "TESTING caveat: ~60 features tested, expect ~3 false "
                "p<0.05 flags per run - a lone KS flag corroborates, "
                "never concludes.",
        "n_first_third": n // 3, "n_last_third": n - 2 * (n // 3),
        "top": ks_rows[:10]}

    # chi-square: recent barrier-reason mix vs whole-corpus expectation
    chi = {"available": False}
    try:
        st = json.loads((OUT / "status.json").read_text(encoding="utf-8"))
        le = (st.get("ml", {}).get("load_stats", {})
                .get("label_era", {}))
        cur = le.get("triple_barrier_h432", {}).get("by_reason", {})
        obs = [cur.get(k, {}).get("rows", 0)
               for k in ("tb_pt", "tb_sl", "tb_time")]
        tot = sum(obs)
        # expectation: the corpus-lifetime h432 mix is itself the era under
        # test, so expectation comes from the RETIRED tb era's mix — the
        # same comparison era_mix_drift's TVD makes, now with a p-value.
        old = le.get("triple_barrier", {}).get("by_reason", {})
        old_counts = [old.get(k, {}).get("rows", 0)
                      for k in ("tb_pt", "tb_sl", "tb_time")]
        old_tot = sum(old_counts)
        if tot >= 15 and old_tot > 0:
            f_exp = [tot * c / old_tot for c in old_counts]
            chi2v, p, valid = chisquare(obs, f_exp)
            chi = {"available": True, "obs_pt_sl_time": obs,
                   "exp_from_prior_era": [round(e, 1) for e in f_exp],
                   "chi2": round(chi2v, 3), "p": round(p, 8),
                   "expected_count_floor_met": valid,
                   "read_as": "companion p-value to era_mix_drift TVD; a "
                              "tiny p here is EXPECTED after a geometry "
                              "change - it confirms the fence matters"}
    except (OSError, ValueError):
        pass
    rep["chi_square_barrier_mix"] = chi

    # Bland-Altman: python-vs-C++ per-trip gross agreement, when diode ran
    ba = {"available": False,
          "note": "method agreement across the referee lattice (Bland& "
                  "Altman 1986 adapted to differential testing); needs a "
                  "diode JSON with per-trip output beside a fills.csv"}
    try:
        dj = json.loads(Path(DIODE_JSON).read_text(encoding="utf-8"))
        trips_cpp = {t["pid"]: t for t in dj.get("era4", {}).get("trips", [])}
        if trips_cpp:
            from scripts.cohort_eval import era4_trips
            trips_py = {t["pid"]: t
                        for t in era4_trips(str(OUT / "fills.csv"))}
            common = sorted(set(trips_cpp) & set(trips_py))
            if common:
                ba = {"available": True,
                      "gross_pct": bland_altman(
                          [trips_py[p]["gross_pct"] for p in common],
                          [trips_cpp[p]["gross_pct"] for p in common])}
    except (OSError, ValueError, KeyError):
        pass
    rep["bland_altman_referees"] = ba

    # Walk-forward robustness (operator 2026-08-20: "as much walk-forwards
    # as logical"): the SAME purged machinery at fold counts 3/5/8 - a
    # SENSITIVITY sweep, never a selection (picking the best fold count
    # would be the argmax-tuning OF-3/OF-4 forbid; the spread is the
    # deliverable, a lift that vanishes at a different split is noise).
    wf = []
    if len(oof_idx) and not on_synth:
        for ns in (3, 5, 8):
            try:
                gs = train_test_gap(X, y, label_span=span, n_splits=ns,
                                    sample_weight=w, sig=sig, res=res,
                                    return_oof=True)
                gg = gs.get(fam) or {}
                gi = np.asarray(gg.get("oof_idx", []), int)
                gp = np.asarray(gg.get("oof_pred", []), float)
                if len(gi):
                    yy = np.asarray(y, int)[gi]
                    wf.append({"n_splits": ns, "n_oof": int(len(gi)),
                               "pr_auc": round(average_precision(yy, gp), 4),
                               "pr_null": round(float(yy.mean()), 4),
                               "roc_auc": round(float(auc_score(yy, gp)), 4)})
            except Exception:                            # noqa: BLE001
                wf.append({"n_splits": ns, "error": "fit failed"})
    lifts = [r["pr_auc"] - r["pr_null"] for r in wf if "pr_auc" in r]
    rep["walk_forward_sensitivity"] = {
        "configs": wf,
        "pr_lift_min": round(min(lifts), 4) if lifts else None,
        "pr_lift_max": round(max(lifts), 4) if lifts else None,
        "read_as": "lift robust across fold counts = real ranking signal; "
                   "sign flips across configs = noise. Feeds the OPERATOR "
                   "and the vault, never a tuner (alarms-not-autotune law)."}
    rep["runtime_sec"] = round(time.time() - t0, 1)
    return rep


def render_md(rep: dict) -> str:
    lines = ["# Ground-truth metrics battery",
             "",
             f"corpus: {rep['corpus']}",
             f"family: {rep['family']}  rows: {rep['n_rows']}  "
             f"oof: {rep['n_oof']}", ""]
    if rep.get("on_synthetic"):
        lines += ["**SYNTHETIC corpus — numbers validate machinery, not "
                  "market. Stop reading here for market claims.**", ""]
    op = rep.get("operating_point")
    if op:
        (tn, fp), (fn, tp) = op["confusion"]
        lines += [f"## Operating point (deployed bar {op['threshold']})",
                  "|  | pred 0 | pred 1 |", "|---|---|---|",
                  f"| true 0 | {tn} | {fp} |",
                  f"| true 1 | {fn} | {tp} |",
                  f"precision {op['precision']}  recall {op['recall']}  "
                  f"F1 {op['f1']}  (base rate {op['base_rate']})", ""]
    d = rep.get("discrimination")
    if d:
        lines += ["## Discrimination (OOF)",
                  f"PR-AUC **{d['pr_auc']}** vs null {d['pr_auc_null']} "
                  f"(headline) · ROC-AUC {d['roc_auc']}", ""]
    ks = rep.get("ks_train_vs_recent", {})
    if ks.get("top"):
        lines += ["## KS drift, top features (first vs last corpus third)"]
        lines += [f"- {r['feature']}: D={r['D']} p={r['p']}"
                  for r in ks["top"]]
        lines += [""]
    chi = rep.get("chi_square_barrier_mix", {})
    if chi.get("available"):
        lines += ["## Barrier-mix chi-square (vs retired-era expectation)",
                  f"chi2 {chi['chi2']}  p {chi['p']}  floor_met "
                  f"{chi['expected_count_floor_met']} — {chi['read_as']}",
                  ""]
    ba = rep.get("bland_altman_referees", {})
    if ba.get("available"):
        g = ba["gross_pct"]
        lines += ["## Referee agreement (Bland-Altman, gross% per trip)",
                  f"n {g['n']}  bias {g['bias']:.6f}  "
                  f"LoA [{g['loa_low']:.6f}, {g['loa_high']:.6f}]", ""]
    wf = rep.get("walk_forward_sensitivity", {})
    if wf.get("configs"):
        lines += ["## Walk-forward sensitivity (fold-count sweep, no argmax)"]
        for r in wf["configs"]:
            if "pr_auc" in r:
                lines += [f"- n_splits {r['n_splits']}: PR-AUC {r['pr_auc']} "
                          f"vs null {r['pr_null']} (oof {r['n_oof']})"]
            else:
                lines += [f"- n_splits {r['n_splits']}: {r.get('error')}"]
        lines += [f"PR lift range [{wf.get('pr_lift_min')}, "
                  f"{wf.get('pr_lift_max')}] - {wf.get('read_as')}", ""]
    lines += ["## Rejected metrics (alignment)",
              f"- accuracy: {rep['rejected']['accuracy']}",
              f"- MAE/RMSE/R2: {rep['rejected']['mae_rmse_r2']}", ""]
    return "\n".join(lines)


def main() -> int:
    rep = build_report()
    md = render_md(rep)
    try:
        Path(REPORT_JSON).parent.mkdir(parents=True, exist_ok=True)
        tmp = Path(str(REPORT_JSON) + f".{os.getpid()}.tmp")
        tmp.write_text(json.dumps(rep, indent=1), encoding="utf-8")
        os.replace(tmp, REPORT_JSON)
        Path(REPORT_MD).write_text(md, encoding="utf-8")
    except OSError as e:
        print(f"report write failed: {e}")
        return 1
    print(md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
