"""Learning-curve report (T2.3, learnaccel Phase 2). REPORT-ONLY: refits
the DEPLOYED walkforward selector on time-prefixes of
outputs/signal_history.csv and writes outputs/learning_curve.{md,json} -
never touches config, state, or the registry.

Why prefixes: retrain_history.jsonl is degenerate at this corpus size
(near-identical rows), so the honest curve is oof-Brier / calib-gap vs
corpus size, computed by replaying the deployed selection on each prefix.
Stratified by regime (one-hot argmax) and annotated with the per-prefix
probe share from the raw CSV. Extrapolation is CAPPED at
extrapolate_max_mult x the observed live-N - beyond that is fiction.

Usage: python scripts/learning_curve.py [--config config.json]
       [--history outputs/signal_history.csv] [--fracs 0.4,0.55,0.7,0.85,1.0]
       [--n-splits 5] [--out-dir outputs]
"""
import argparse
import csv
import json
import math
import sys
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ml.contracts import get_contract                       # noqa: E402
from ml.features import FEATURE_NAMES                       # noqa: E402
from ml.history import HistoryStore                          # noqa: E402
from ml.overfit import REGIME_STRATA, regime_stratified_oof   # noqa: E402
from ml.walkforward import evaluate_and_select                # noqa: E402

DEFAULTS = {"fracs": "0.4,0.55,0.7,0.85,1.0", "n_splits": 5,
            "min_prefix_rows": 240, "extrapolate_max_mult": 2.0}

# Mirrors ml.walkforward.evaluate_and_select's own internal per-fold
# class-balance floor (`y[tr].sum() >= 5 and (len(y[tr]) - y[tr].sum())
# >= 5`) - purged_walk_forward's folds are expanding-window subsets of the
# sliced prefix, so if the WHOLE prefix doesn't clear this for BOTH
# classes, no fold carved out of it ever can either. Checking it here lets
# a too-small prefix report an honest "skipped: insufficient labels"
# instead of paying for a fit that evaluate_and_select would silently
# degrade to its folds=[] filler (mean_brier=0.25, empty oof_idx).
_MIN_FOLD_CLASS = 5

# Column index of each regime stratum's one-hot feature, in REGIME_STRATA
# order - computed once (module import time), reused per prefix. Exact
# idiom of scripts/overfit_check.py's regime diagnostic section.
_REGIME_COLS = [FEATURE_NAMES.index(f"regime_{s}") for s in REGIME_STRATA]


def _scan_live_upto(history_path: str, cutoff_sig: float) -> tuple:
    """One raw-CSV pass over `history_path`: (n_live, n_probe) among LIVE
    rows (source=='live', excluding the long-book accumulation process -
    a different trading process entirely, ml/history.py's own book=="long"
    exclusion) with signal_ts <= cutoff_sig. Header-resolved column reads
    only - never positional - so a schema change can't silently misalign
    the count. load_training_data's X/y/w/sig/res can't answer this: it
    drops the raw 'probe'/'book' bookkeeping columns entirely, so a fresh
    scan of the CSV is the designed source for both stats."""
    path = Path(history_path)
    if not path.exists():
        return 0, 0
    n_live = 0
    n_probe = 0
    try:
        with open(path, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if (row.get("book") or "5m") == "long":
                    continue
                if row.get("source") != "live":
                    continue
                try:
                    sig_ts = float(row.get("signal_ts") or row.get("ts")
                                  or "nan")
                except ValueError:
                    continue
                if not np.isfinite(sig_ts) or sig_ts > cutoff_sig:
                    continue
                n_live += 1
                if (row.get("probe") or "") == "1":
                    n_probe += 1
    except (OSError, csv.Error):
        return 0, 0
    return n_live, n_probe


def probe_share_by_cutoff(history_path: str, cutoff_sig: float) -> "float | None":
    """Probe share among live rows with signal_ts <= cutoff (raw CSV scan,
    header-resolved column indices - never positional)."""
    n_live, n_probe = _scan_live_upto(history_path, cutoff_sig)
    return (n_probe / n_live) if n_live else None


def prefix_report(X, y, w, sig, res, frac: float, cfg: dict,
                  n_splits: "int | None", n_live: int,
                  select_cfg: "dict | None" = None,
                  extra_models: tuple = (),
                  adaptive_cfg: "dict | None" = None,
                  ensemble_k: int = 3) -> dict:
    """One curve point: slice the first int(frac*n) rows (sig-ascending
    slices are time-prefixes by construction), require min positives (and
    negatives) per the fold constraint, run evaluate_and_select with
    deployed kwargs (label_span from cfg['label_max_bars'], default 96;
    n_live = count of live rows inside the prefix, supplied by the
    caller from a raw CSV scan - load_training_data's arrays carry no
    'source' column; select_cfg/extra_models/adaptive_cfg/ensemble_k
    mirror main.py's own _maybe_auto_retrain call so the evidence-gate
    and adaptive rung behave IDENTICALLY to the deployed selector, not a
    weaker "everything admissible" approximation of it), and return
    {frac, n_rows, n_live, selected, oof_brier, calib_gap, regime, skipped}.

    A too-small prefix (row-count floor OR class-balance floor) reports an
    explicit skipped="insufficient labels" entry rather than being
    silently dropped from the output - the operator sees every requested
    frac, honestly labeled."""
    n_total = len(X)
    n_rows = max(0, min(n_total, int(round(frac * n_total))))
    point: dict = {"frac": float(frac), "n_rows": int(n_rows),
                  "n_live": int(n_live), "selected": None,
                  "oof_brier": None, "calib_gap": None, "regime": None,
                  "skipped": None}
    min_prefix_rows = int(cfg.get("min_prefix_rows",
                                  DEFAULTS["min_prefix_rows"]))
    if n_rows < min_prefix_rows:
        point["skipped"] = "insufficient labels"
        return point
    yp = y[:n_rows]
    n_pos = int(yp.sum())
    n_neg = n_rows - n_pos
    if n_pos < _MIN_FOLD_CLASS or n_neg < _MIN_FOLD_CLASS:
        point["skipped"] = "insufficient labels"
        return point
    Xp, wp = X[:n_rows], w[:n_rows]
    sigp, resp = sig[:n_rows], res[:n_rows]
    label_span = int(cfg.get("label_max_bars", 96))
    kwargs: dict[str, Any] = dict(
        sample_weight=wp, feature_names=FEATURE_NAMES,
        label_span=label_span, sig=sigp, res=resp, n_live=int(n_live),
        select_cfg=select_cfg, extra_models=extra_models,
        adaptive_cfg=adaptive_cfg, ensemble_k=int(ensemble_k))
    if n_splits is not None:
        kwargs["n_splits"] = int(n_splits)
    results = evaluate_and_select(Xp, yp, **kwargs)
    oof_idx = np.asarray(results.get("oof_idx", []), int)
    if oof_idx.size == 0:
        # evaluate_and_select degrades gracefully (folds=[] -> a filler
        # mean_brier=0.25/calib_gap=0.0, never a crash) rather than
        # raising - reporting that filler as a real number would be
        # dishonest, so this is its own distinct skip reason.
        point["skipped"] = "no valid OOF folds after time-purge"
        return point
    sel = results["selected"]
    point["selected"] = sel
    point["oof_brier"] = round(float(results[sel]["mean_brier"]), 6)
    point["calib_gap"] = round(float(results[sel]["calib_gap"]), 6)
    oof_p = np.asarray(results[sel]["oof_p"], float)
    pooled_auc = float(results[sel]["mean_auc"])
    one_hot = Xp[oof_idx][:, _REGIME_COLS]
    point["regime"] = regime_stratified_oof(
        yp, oof_idx, oof_p, one_hot, pooled_auc=pooled_auc,
        pooled_brier=point["oof_brier"])
    return point


def build_projection(points: list, extrapolate_max_mult: float) -> dict:
    """Least-squares oof_brier ~ a + b*log2(n_live) over scored points with
    n_live >= 2. Projects ONLY to [live_now, extrapolate_max_mult *
    live_now] - live_now is the observed live-N at the LARGEST requested
    frac (the last point once fracs are sorted ascending); beyond the cap
    is fiction. b >= 0 (flat or worsening with more data) is reported
    honestly as no measurable improvement, never dressed up as a
    forecast."""
    live_now = int(points[-1]["n_live"]) if points else 0
    cap_live_n = float(extrapolate_max_mult) * live_now
    proj: dict = {"n_points_used": 0, "live_now": live_now,
                 "cap_live_n": cap_live_n, "a": None, "b": None,
                 "predicted_oof_brier_at_live_now": None,
                 "predicted_oof_brier_at_cap": None, "note": None}
    usable = [p for p in points
             if p.get("oof_brier") is not None and p.get("n_live", 0) >= 2]
    proj["n_points_used"] = len(usable)
    if len(usable) < 2:
        proj["note"] = ("insufficient points for projection (need >=2 "
                       "scored points with n_live >= 2)")
        return proj
    xs = np.log2(np.array([p["n_live"] for p in usable], float))
    ys = np.array([p["oof_brier"] for p in usable], float)
    design = np.vstack([np.ones_like(xs), xs]).T
    (a, b), *_ = np.linalg.lstsq(design, ys, rcond=None)
    a, b = float(a), float(b)
    proj["a"], proj["b"] = round(a, 6), round(b, 6)
    if live_now > 0:
        proj["predicted_oof_brier_at_live_now"] = round(
            a + b * math.log2(live_now), 6)
    if cap_live_n > 0:
        proj["predicted_oof_brier_at_cap"] = round(
            a + b * math.log2(cap_live_n), 6)
    proj["note"] = ("no measurable improvement with corpus growth"
                    if b >= 0 else
                    "directional only - never treat past the cap as fact")
    return proj


def _pct(x) -> str:
    return f"{x:.1%}" if x is not None else "-"


def _probe_price_paragraph(points: list) -> str:
    """Prices the probe label for the operator: what share of the LIVE
    training corpus is PT-050 exploration probes (EV-negative entries
    taken deliberately to buy a label) versus conviction entries, at the
    largest prefix with any live evidence at all."""
    scored = [p for p in points if p.get("n_live", 0) > 0]
    if not scored:
        return ("No live rows observed in any prefix - the probe-label "
                "price cannot be assessed yet.")
    last = scored[-1]
    share = last.get("probe_share")
    if share is None:
        return (f"At the full corpus ({last['n_live']} live labels), no "
                "probe marker survives in the raw CSV (all '' - "
                "pre-PT-050 data) - the probe price cannot be assessed.")
    n_probe = round(share * last["n_live"])
    n_conviction = last["n_live"] - n_probe
    return (
        f"At the current live corpus (N={last['n_live']}), {share:.1%} of "
        f"live labels ({n_probe} of {last['n_live']}) came from PT-050 "
        "exploration probes - EV-negative entries taken deliberately to "
        f"buy label information - versus {n_conviction} conviction "
        "entries. Every additional probe label costs its own expected "
        "value to acquire; at the observed rate, growing the live corpus "
        "further keeps paying that same per-label price, not a one-time "
        "cost.")


def render_markdown(points: list, projection: dict, meta: dict) -> str:
    lines = [
        "# Learning-curve report (T2.3)", "",
        f"Time-prefix refits of the DEPLOYED walk-forward selector on "
        f"`{meta['history_path']}` ({meta['n_total_rows']} rows after the "
        f"poison filter). n_splits={meta['n_splits_effective']} "
        f"(requested={meta['n_splits_requested']}) · "
        f"label_span={meta['label_max_bars']} bars · "
        f"min_prefix_rows={meta['min_prefix_rows']}.", "",
        "| frac | n_rows | n_live | probe_share | selected | oof_brier "
        "| calib_gap |",
        "|---|---|---|---|---|---|---|",
    ]
    for p in points:
        if p["skipped"]:
            lines.append(
                f"| {p['frac']:.2f} | {p['n_rows']} | {p['n_live']} "
                f"| {_pct(p['probe_share'])} | skipped: {p['skipped']} "
                f"| - | - |")
        else:
            lines.append(
                f"| {p['frac']:.2f} | {p['n_rows']} | {p['n_live']} "
                f"| {_pct(p['probe_share'])} | {p['selected']} "
                f"| {p['oof_brier']:.4f} | {p['calib_gap']:.4f} |")
    lines.append("")

    last = points[-1] if points else None
    if last is not None and last.get("regime"):
        lines += [
            f"## Regime detail (largest scored prefix, frac="
            f"{last['frac']:.2f})", "",
            "| stratum | n_oof | scored | auc | brier | degrade |",
            "|---|---|---|---|---|---|",
        ]
        for s in (*REGIME_STRATA, "unknown"):
            r = last["regime"].get(s, {})
            auc = f"{r['auc']:.3f}" if r.get("auc") is not None else "-"
            brier = (f"{r['brier']:.4f}" if r.get("brier") is not None
                     else "-")
            deg = str(r.get("degrade")) if r.get("degrade") is not None \
                else "-"
            lines.append(f"| {s} | {r.get('n_oof', 0)} | {r.get('scored')} "
                        f"| {auc} | {brier} | {deg} |")
        lines.append("")

    lines += [
        f"## Extrapolation (capped at "
        f"{meta['extrapolate_max_mult']:g}x observed live-N)", "",
    ]
    if projection.get("b") is None:
        lines.append(
            f"live_now={projection['live_now']} · "
            f"cap_live_n={projection['cap_live_n']:.0f} · "
            f"{projection['note']}")
    else:
        lines.append(
            f"fit: oof_brier ~ {projection['a']:.4f} + "
            f"{projection['b']:.5f} * log2(n_live) over "
            f"{projection['n_points_used']} point(s)")
        lines.append(
            f"live_now={projection['live_now']} -> predicted oof_brier "
            f"{projection['predicted_oof_brier_at_live_now']}")
        lines.append(
            f"cap_live_n={projection['cap_live_n']:.0f} -> predicted "
            f"oof_brier {projection['predicted_oof_brier_at_cap']} "
            f"({projection['note']})")
    lines.append("")

    lines += ["## Probe-label price", "", _probe_price_paragraph(points), ""]
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="Time-prefix learning-curve report (T2.3, report-only)")
    ap.add_argument("--config", default=str(ROOT / "config.json"))
    ap.add_argument("--history", default="outputs/signal_history.csv")
    ap.add_argument("--fracs", default=DEFAULTS["fracs"])
    ap.add_argument("--n-splits", type=int, default=None,
                    help=f"override the deployed default "
                         f"({DEFAULTS['n_splits']}); omit to match "
                         f"production's evaluate_and_select exactly")
    ap.add_argument("--out-dir", default="outputs")
    args = ap.parse_args(argv)

    cfg_path = Path(args.config)
    full_cfg: dict = {}
    if cfg_path.exists():
        try:
            full_cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            full_cfg = {}
    ml_cfg = full_cfg.get("ml", {}) or {}

    store = HistoryStore(args.history)
    if Path(args.history).exists():
        # era-gated training exclusion (docs/quant/2026-07-26_era_exclusion.md):
        # this report's whole premise is "refits the DEPLOYED walkforward
        # selector" (module docstring) - a curve computed over a different
        # row set than what actually deploys is not a learning curve for
        # the deployed process. Discovered as a 7th load_training_data call
        # site during that task (not one of the 6 docs/quant/
        # pbo_admission_policy.md already enumerates); wired for the same
        # reason as scripts/interpret_report.py and feature_stability.py.
        X, y, w, sig, res = store.load_training_data(
            return_label_times=True,
            weights_cfg=ml_cfg.get("sample_weights", {}),
            era_cfg=ml_cfg.get("era_exclusion", {}))
    else:
        # ml.history.HistoryStore.load_training_data's missing-file early
        # return only special-cases return_sig (a 4-tuple); passing
        # return_label_times=True on a fresh checkout with no
        # signal_history.csv yet (outputs/ is gitignored) gets back a bare
        # 3-tuple and this call's unpack would raise ValueError. Handled
        # here rather than upstream (out of this task's scope): an empty
        # corpus is a legitimate, reportable state, not a crash.
        X = np.empty((0, len(FEATURE_NAMES)))
        y = np.empty(0)
        w = np.empty(0)
        sig = np.empty(0)
        res = np.empty(0)
    # LP-4: the same inference-time feature contract screens the training
    # matrix here too (main.py:4634's own idiom) - a poisoned row must not
    # silently distort the curve.
    keep = get_contract().check_matrix(X)["keep"]
    if not keep.all():
        X, y, w, sig, res = X[keep], y[keep], w[keep], sig[keep], res[keep]
    n_total = len(X)

    fracs = sorted({float(f) for f in args.fracs.split(",") if f.strip()})
    run_cfg = {"label_max_bars": int(ml_cfg.get("label_max_bars", 96)),
              "min_prefix_rows": int(DEFAULTS["min_prefix_rows"])}
    # Deployed-parity selector inputs (main.py:4650-4673's own idiom,
    # mirrored exactly): without these, evaluate_and_select trains and
    # admits every family unconditionally regardless of n_live, which is
    # NOT what production does the moment ml.model_selection.enabled is
    # true - the offline curve must replay the same admission decisions,
    # not a permissive approximation of them.
    _sel_cfg = ml_cfg.get("model_selection") or None
    _ag = ml_cfg.get("adaptive_gbt", {}) or {}
    _extra = ("adaptive_gbt",) if _ag.get("enabled") else ()
    _ensemble_k = int(ml_cfg.get("ensemble_seeds", 3))

    points = []
    for frac in fracs:
        n_rows = max(0, min(n_total, int(round(frac * n_total))))
        cutoff_sig = float(sig[n_rows - 1]) if n_rows > 0 else float("-inf")
        n_live, n_probe = _scan_live_upto(args.history, cutoff_sig)
        point = prefix_report(X, y, w, sig, res, frac, run_cfg,
                             args.n_splits, n_live, select_cfg=_sel_cfg,
                             extra_models=_extra, adaptive_cfg=_ag,
                             ensemble_k=_ensemble_k)
        point["probe_share"] = (n_probe / n_live) if n_live else None
        points.append(point)

    projection = build_projection(points,
                                  float(DEFAULTS["extrapolate_max_mult"]))
    meta = {
        "history_path": str(args.history),
        "n_total_rows": int(n_total),
        "n_splits_requested": args.n_splits,
        "n_splits_effective": (args.n_splits if args.n_splits is not None
                              else int(DEFAULTS["n_splits"])),
        "min_prefix_rows": run_cfg["min_prefix_rows"],
        "extrapolate_max_mult": float(DEFAULTS["extrapolate_max_mult"]),
        "label_max_bars": run_cfg["label_max_bars"],
    }
    out = {"points": points, "projection": projection, "meta": meta}

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_json = out_dir / "learning_curve.json"
    out_md = out_dir / "learning_curve.md"
    out_json.write_text(json.dumps(out, indent=1, sort_keys=True),
                        encoding="utf-8")
    md = render_markdown(points, projection, meta)
    out_md.write_text(md, encoding="utf-8")
    print(md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
