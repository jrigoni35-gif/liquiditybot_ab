"""Does the DEPLOYED champion have out-of-sample skill? (read-only)

WHY THIS EXISTS (2026-08-31). The deploy gate compares champion vs
challenger. It never asks whether EITHER beats a constant. A model with no
skill still wins every gate forever, because a near-constant predictor is
trivially stable and no challenger can beat it by `deploy_margin` — the
73-cycle reject streak, the pinned drift deciles and PI-2's "structurally
closed" entry path are all the same fact seen from three sides.

Measured the day this shipped: champion `1ee3ae68c0df` scored **-0.0038
skill** (i.e. none) on 4,469 unseen rows while scoring **+0.0536 in
sample** — and its calibrated output on fresh rows spans only
[0.4014, 0.6116], sd 0.018, which is why it cannot emit above the entry
bar. Re-derive with this script; do not quote those numbers as current.

THE NULL THAT MATTERS is the ORACLE CONSTANT: predicting the window's own
base rate `b` forever scores `b(1-b)`. Beating the *training* base rate,
or beating a deliberately handicapped refit, is not skill — the first
session to measure this compared against a twin whose calibrator was fit
in-sample and over-claimed a 0.0397 edge that was 34% its own artifact.

Skill score = 1 - brier / (b*(1-b)).

A NEGATIVE SCORE IS NOT AUTOMATICALLY A FINDING, on two counts measured
2026-09-02.

(1) THE METRIC IS NEGATIVELY BIASED BY ~1/n. The oracle constant b is refit
on whatever window is being scored while the predictor stays fixed, so even
a PERFECTLY calibrated constant scores below zero. Measured over 3,000 draws
per size: mean skill -0.005178 at n=200, -0.000982 at n=1,000, -0.000175 at
n=5,751, -0.000049 at n=20,000, with P(skill<0) at or above 0.978 in every
cell. Subtract ~1/n before reading a small negative as evidence of anything.

(2) THE VERDICT NOW CARRIES ITS OWN RESOLUTION. `skill <= 0 -> "NO SKILL"`
was a bare sign test: it returned the same word for a true zero and for a
window too weak to see an effect, which is the Type-II shape Harvey & Liu
(J. Finance 2020) measure at 86.9% even when real alpha is present. Every
window now reports a day-block bootstrap CI and the |skill| it can resolve,
and says NO SKILL DETECTED - naming the floor - rather than NO SKILL. On the
2026-09-02 corpus the champion's fresh window read skill -0.0036 against a
resolution floor of 0.0146: the estimate is four times smaller than the
smallest effect that window can see, so nothing about skill was established
in either direction. Its in-sample +0.0536 likewise spans zero on 17 day
blocks. Do not quote either number as current - re-derive.

SAFE / measurement-plane: reads only, opens no positions, writes nothing,
alters no order. Run it any time:

    python scripts/champion_skill_report.py
    python scripts/champion_skill_report.py --json
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np

# Brier of the best possible constant is b*(1-b); a window with no label
# variation makes skill undefined rather than infinite.
MIN_WINDOW_ROWS = 30
# Skill-interval settings. These are MEASUREMENT STANDARDS, not tunables:
# raising reps costs time and lowers nothing, and DAY_S defines the block
# over which rows are treated as sharing one market path. Do not "fix" a
# wide interval by shrinking the block - that is the gate-widening
# CLAUDE.md forbids.
SKILL_CI_REPS = 400
SKILL_CI_SEED = 20260902
DAY_S = 86400.0


def corpus_span(sig) -> dict[str, Any]:
    """Calendar span of the rows ACTUALLY LOADED, from their signal times.

    The MinBTL denominator (how many calendar days the corpus covers) was
    quoted from a doc that had it as 50.1d; this re-derives it every run
    from the same `sig` array the skill windows are cut on, so the number
    on the report is the number the report used. Pure: no I/O. Non-finite
    or non-positive times are excluded and counted, never averaged in.
    Keys: corpus_first_ts / corpus_last_ts (ISO UTC, None when empty),
    corpus_span_days (2 dp, None when empty), corpus_rows, sig_missing.
    """
    s = np.asarray(sig, float).reshape(-1)
    ok = np.isfinite(s) & (s > 0.0)
    good = s[ok]
    out: dict[str, Any] = {"corpus_rows": int(s.size),
                           "sig_missing": int(s.size - good.size),
                           "corpus_first_ts": None, "corpus_last_ts": None,
                           "corpus_span_days": None}
    if good.size == 0:
        return out
    lo, hi = float(good.min()), float(good.max())

    def _iso(t: float) -> str | None:
        # Windows gmtime raises OSError on a millisecond epoch (the
        # unit-mixing class the data-quality audit measured); a report
        # must degrade to None, never crash over one bad cell
        try:
            return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t))
        except (OverflowError, OSError, ValueError):
            return None

    out["corpus_first_ts"] = _iso(lo)
    out["corpus_last_ts"] = _iso(hi)
    out["corpus_span_days"] = round((hi - lo) / 86400.0, 2)
    return out


def skill_score(brier: float, base_rate: float) -> float | None:
    """Skill vs the oracle constant predictor. None when undefined.

    A degenerate window (all one class) has oracle brier 0 and no
    meaningful skill denominator - say so instead of dividing by zero.
    """
    oracle = float(base_rate) * (1.0 - float(base_rate))
    if oracle <= 0.0:
        return None
    return 1.0 - float(brier) / oracle


def skill_ci(p: np.ndarray, y: np.ndarray, ts: np.ndarray | None,
             reps: int = SKILL_CI_REPS,
             seed: int = SKILL_CI_SEED) -> dict[str, Any]:
    """Bootstrap interval for the skill score, plus the effect this window
    could actually RESOLVE.

    WHY THIS EXISTS (2026-09-02). The verdict below used to be a bare sign
    test on a point estimate: `skill <= 0 -> "NO SKILL"`. That reads a null
    as a finding, and it is the shape Harvey & Liu (J. Finance 2020) put a
    number on - a joint multiple-testing null carries a Type II error of
    86.9% at p<.05 even when the true performers earn ~10.66%/yr alpha. A
    test that cannot see an effect and a world with no effect produce the
    same word, so the word was unfalsifiable. It now ships with its own
    resolution.

    BLOCKS, NOT ROWS. When `ts` is supplied the resample is over CALENDAR
    DAYS (each day drawn whole), because rows inside a day share the market
    path and are not independent evidence - the same effective-n reasoning
    `cohort_eval.cohort_effective_n` applies to concurrent trips and
    `label_decomposition_report` applies to its day blocks. With `ts=None`
    the resample is over rows and the interval is OPTIMISTIC; the caller is
    told which basis was used so a reader never has to guess.

    `mde_2se` is the half-width the window can resolve at ~2 SE. It is a
    RESOLUTION FLOOR, not a claim about the true effect: a skill score whose
    magnitude is below it is inside the noise this sample can produce.
    """
    y = np.asarray(y, float).reshape(-1)
    p = np.asarray(p, float).reshape(-1)
    n = int(y.size)
    if n < 2:
        return {"available": False, "reason": "n<2"}
    rng = np.random.default_rng(seed)
    if ts is not None and np.asarray(ts).size == n:
        days = (np.asarray(ts, float) // DAY_S).astype("int64")
        blocks = [np.flatnonzero(days == u) for u in np.unique(days)]
        basis = "day-block"
    else:
        blocks = None
        basis = "row (OPTIMISTIC - no timestamps supplied)"
    nb = len(blocks) if blocks is not None else n
    draws: list[float] = []
    for _ in range(int(reps)):
        if blocks is not None:
            idx = np.concatenate([blocks[i] for i in rng.integers(0, nb, nb)])
        else:
            idx = rng.integers(0, n, n)
        yy = y[idx]
        b = float(yy.mean())
        if b <= 0.0 or b >= 1.0:
            continue                       # degenerate resample: no denominator
        s = skill_score(float(np.mean((p[idx] - yy) ** 2)), b)
        if s is not None and math.isfinite(s):
            draws.append(s)
    if len(draws) < max(20, int(reps) // 10):
        return {"available": False, "reason": "too many degenerate resamples",
                "basis": basis, "blocks": nb, "draws": len(draws)}
    arr = np.asarray(draws, float)
    lo, hi = (float(x) for x in np.percentile(arr, [2.5, 97.5]))
    sd = float(arr.std(ddof=1))
    return {"available": True, "basis": basis, "blocks": nb, "reps": len(draws),
            "ci95": [round(lo, 6), round(hi, 6)],
            "bootstrap_sd": round(sd, 6),
            "mde_2se": round(2.0 * sd, 6),
            "excludes_zero": bool(lo > 0.0 or hi < 0.0)}


def window_report(p_cal: np.ndarray, y: np.ndarray,
                  train_base: float | None = None,
                  ts: np.ndarray | None = None) -> dict[str, Any]:
    """Skill of calibrated predictions `p_cal` against labels `y`.

    Pure: no I/O, no globals. `train_base` (the training-window base rate)
    adds the weaker train-constant null for context when supplied. `ts`
    (signal timestamps, same length as `y`) switches the interval to a
    day-block resample - supply it whenever you have it.
    """
    y = np.asarray(y, float).reshape(-1)
    p = np.asarray(p_cal, float).reshape(-1)
    n = int(y.size)
    if n == 0 or p.size != n:
        # SHAPE-STABLE failure: a caller reading ["skill_score"] must not
        # get a KeyError on the error path (it would crash the reader that
        # this report exists to inform).
        return {"n": n, "error": "empty or length-mismatched window",
                "skill_score": None, "verdict": "UNDEFINED (bad window)",
                "insufficient_rows": True}
    base = float(y.mean())
    brier = float(np.mean((p - y) ** 2))
    oracle = base * (1.0 - base)
    out: dict[str, Any] = {
        "n": n,
        "base_rate": round(base, 6),
        "brier": round(brier, 6),
        "oracle_constant_brier": round(oracle, 6),
        "excess_over_oracle": round(brier - oracle, 6),
        "skill_score": None,
        "insufficient_rows": n < MIN_WINDOW_ROWS,
        "p_min": round(float(p.min()), 6),
        "p_max": round(float(p.max()), 6),
        "p_sd": round(float(p.std()), 6),
    }
    sk = skill_score(brier, base)
    out["skill_score"] = None if sk is None else round(sk, 6)
    # THE VERDICT CARRIES ITS OWN RESOLUTION (2026-09-02). A point estimate
    # thresholded at zero cannot separate "no skill" from "a window too weak
    # to see skill" - see skill_ci. Both halves are reported, and the
    # vocabulary now says which one was established.
    ci = skill_ci(p, y, ts)
    out["skill_ci"] = ci
    if sk is None:
        out["verdict"] = "UNDEFINED (degenerate window)"
    elif not ci.get("available"):
        out["verdict"] = ("NO SKILL DETECTED (interval unavailable: %s)"
                          % ci.get("reason", "unknown"))
    elif ci["excludes_zero"]:
        out["verdict"] = ("NEGATIVE SKILL (CI excludes 0)" if sk <= 0.0
                          else "SKILL (CI excludes 0)")
    else:
        # the honest null: the interval spans zero, so this window cannot
        # tell a true zero from an effect smaller than it can resolve
        out["verdict"] = ("NO SKILL DETECTED (CI spans 0; this window "
                          "resolves |skill| > %.4f)" % ci["mde_2se"])
    if train_base is not None:
        out["train_constant_brier"] = round(
            float(np.mean((float(train_base) - y) ** 2)), 6)
    return out


def capacity_ladder(fit_predict, y_test: np.ndarray) -> list[dict[str, Any]]:
    """Skill of each capacity rung on ONE shared test window.

    `fit_predict` maps a rung name -> calibrated test-window probabilities
    (or None if that rung could not be fitted). Injected rather than built
    here so tests can plant predictors of known skill without training
    anything, and so this stays pure.

    WHY A LADDER: if low skill were a CAPACITY limit, a higher rung would
    beat the deployed one. Measured 2026-09-01 on 4,887 unseen rows: all
    eight rungs scored NEGATIVE skill and capacity was monotonically
    HARMFUL (blend -0.004 ... ensemble_mlp -0.194). That is the signature
    of fitting noise: the binding constraint is the TARGET, not the model.
    """
    y_test = np.asarray(y_test, float).reshape(-1)
    rows: list[dict[str, Any]] = []
    for name, p in fit_predict.items():
        if p is None:
            rows.append({"rung": name, "error": "could not fit",
                         "skill_score": None, "verdict": "UNDEFINED (unfit)"})
            continue
        r = window_report(p, y_test)
        r["rung"] = name
        rows.append(r)
    # Explicit None test, NOT `or`: a skill score of exactly 0.0 is FALSY,
    # and `x or default` would sort the perfect-null rung to the bottom as
    # if it were the worst. (Planted-test-caught, 2026-09-01.)
    rows.sort(key=lambda r: (r["skill_score"] is None,
                             -r["skill_score"]
                             if r["skill_score"] is not None else 0.0))
    return rows


def _load_live() -> dict[str, Any]:
    """Production corpus + deployed champion, exactly as main.py loads them.

    The repo-root sys.path insert lives HERE, not at module scope: importing
    this module (a test, another report) must not mutate global import state
    as a side effect - the same side-effectful-init class that rotated the
    training corpus in the 2026-07-11 schema-loss incident.
    """
    root = str(Path(__file__).resolve().parent.parent)
    if root not in sys.path:
        sys.path.insert(0, root)
    cfg = json.loads(Path("config.json").read_text(encoding="utf-8"))
    ml_cfg = cfg.get("ml", {})
    sw = ml_cfg.get("sample_weights", {})
    from ml.contracts import get_contract
    from ml.history import HistoryStore
    hist = HistoryStore(
        ml_cfg.get("history_path", "outputs/signal_history.csv"),
        max_bars=int(ml_cfg.get("label_max_bars", 96)))
    X, y, w, sig, _res = hist.load_training_data(
        half_life_days=float(sw.get("half_life_days", 30)),
        candidate_weight=float(sw.get("candidate_weight", 0.4)),
        manip_discount=float(sw.get("manip_discount", 0.5)),
        return_label_times=True, weights_cfg=sw,
        telemetry_cfg=ml_cfg.get("telemetry", {}),
        epoch_cfg=ml_cfg.get("epoch", {}),
        era_cfg=ml_cfg.get("era_exclusion", {}))
    keep = get_contract().check_matrix(X)["keep"]
    return {"X": X[keep], "y": y[keep], "sig": sig[keep], "w": w[keep],
            "meta_path": Path(ml_cfg.get("model_path",
                                         "outputs/meta_model.json"))}


def _run_ladder(X: np.ndarray, y: np.ndarray, w: np.ndarray,
                wm: int) -> list[dict[str, Any]]:
    """Fit each family on the champion's train window, score on the unseen
    rows. Isotonic is fit on a held-out TAIL OF TRAIN, never on test - the
    in-sample-calibration mistake that produced a retracted claim on
    2026-08-31. Seeds are the family defaults, so this is deterministic.
    """
    import ml.models as families
    from ml.calibration import IsotonicCalibrator
    cal_cut = int(wm * 0.8)
    Xtr, ytr, wtr = X[:cal_cut], y[:cal_cut], w[:cal_cut]
    Xca, yca = X[cal_cut:wm], y[cal_cut:wm]
    Xte, yte = X[wm:], np.asarray(y[wm:], float)
    rungs = {
        "logistic (deployed family)": families.LogisticModel,
        "mlp 32-16": families.NumpyMLP,
        "mlp 128-64": lambda: families.NumpyMLP(hidden=(128, 64)),
        "ensemble_mlp k=3": families.EnsembleMLP,
        "gbt stumps": families.GradientBoostedStumps,
        "gbt depth-4": lambda: families.GradientBoostedStumps(
            max_depth=4, n_estimators=600),
        "adaptive_gbt": families.AdaptiveGBT,
        "blend": families.BlendModel,
    }
    preds: dict[str, np.ndarray | None] = {}
    for name, make in rungs.items():
        try:
            m = make()
            try:
                m.fit(Xtr, ytr, sample_weight=wtr)
            except TypeError:
                m.fit(Xtr, ytr)
            cal = IsotonicCalibrator()
            fitted = False
            try:
                cal.fit(np.asarray(m.predict_proba(Xca), float).reshape(-1),
                        yca)
                fitted = bool(getattr(cal, "fitted", False))
            except Exception:                                # noqa: BLE001
                fitted = False
            p = np.asarray(m.predict_proba(Xte), float).reshape(-1)
            if fitted:
                p = np.asarray(cal.transform(p), float).reshape(-1)
            preds[name] = np.clip(p, 1e-6, 1 - 1e-6)
        except Exception:                                    # noqa: BLE001
            # A family that will not fit is reported as unfit, never as a
            # zero-skill result - those are different observations.
            preds[name] = None
    return capacity_ladder(preds, yte)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true", help="machine-readable")
    ap.add_argument("--ladder", action="store_true",
                    help="also fit every model family on the champion's own "
                         "train window and score each on the same unseen "
                         "rows - answers 'is low skill a CAPACITY limit?'. "
                         "MEASUREMENT ONLY: nothing is deployed or saved.")
    args = ap.parse_args(argv)

    live = _load_live()
    X, y, sig = live["X"], live["y"], live["sig"]
    span = corpus_span(sig)
    span_line = (f"corpus span (signal_ts of the {span['corpus_rows']} rows "
                 f"loaded): {span['corpus_first_ts']} -> "
                 f"{span['corpus_last_ts']} = {span['corpus_span_days']} d"
                 + (f" ({span['sig_missing']} rows without a signal time)"
                    if span["sig_missing"] else ""))
    meta_path: Path = live["meta_path"]
    if not meta_path.exists():
        if args.json:
            print(json.dumps({"champion": None, "error": "no deployed champion",
                              **span}, indent=2))
        else:
            print(span_line)
            print(f"no deployed champion at {meta_path} - nothing to score")
        return 0
    meta = json.loads(meta_path.read_text(encoding="utf-8"))

    from ml.calibration import IsotonicCalibrator
    from ml.models import LogisticModel
    champ = LogisticModel.from_dict(meta)
    cal = (IsotonicCalibrator.from_dict(meta["calibration"])
           if meta.get("calibration") else None)
    p = np.asarray(champ.predict_proba(X), float).reshape(-1)
    if cal is not None and getattr(cal, "fitted", False):
        p = np.asarray(cal.transform(p), float).reshape(-1)
    p = np.clip(p, 1e-6, 1 - 1e-6)

    n = len(X)
    wm = int(meta.get("rows", 0))
    idx = np.arange(n)
    yv = np.asarray(y, float)
    train_base = float(yv[:wm].mean()) if 0 < wm <= n else None

    windows = {"fresh_index": idx >= wm, "train": idx < wm}
    # The index watermark is an APPROXIMATION: the corpus is signal-sorted
    # and late-resolving rows interleave BELOW it, so a wall-clock-defined
    # window is the independent second route. Both are reported; a large
    # divergence means the watermark no longer names the training boundary.
    align: dict[str, Any] = {"watermark": wm, "corpus_rows": n}
    s = np.asarray(sig, float)
    if wm and 0 < wm <= n and s.size == n:
        deploy_ts = float(s[wm - 1])
        windows["fresh_time"] = s > deploy_ts
        align.update({
            "sig_monotone": bool(np.all(np.diff(s) >= 0)),
            "watermark_sig": deploy_ts,
            "rows_before_watermark_sig": int((s <= deploy_ts).sum()),
            "interleave_rows": int((s <= deploy_ts).sum()) - wm,
        })

    report: dict[str, Any] = {
        "champion": meta_path.name,
        "model_kind": meta.get("kind"),
        "trained_rows": wm,
        "alignment": align,
        # the MinBTL denominator, re-derived from the loaded rows every run
        "corpus_first_ts": span["corpus_first_ts"],
        "corpus_last_ts": span["corpus_last_ts"],
        "corpus_span_days": span["corpus_span_days"],
        "corpus_sig_missing": span["sig_missing"],
        # ts=s[m] is load-bearing, not decoration: without it the skill
        # interval resamples ROWS, and rows inside a day share the market
        # path, so the interval comes out too narrow and the verdict too
        # confident. Pass the timestamps whenever the loader has them.
        "windows": {k: window_report(p[m], yv[m], train_base,
                                     ts=(s[m] if s.size == n else None))
                    for k, m in windows.items() if int(m.sum()) > 0},
    }
    fresh = report["windows"].get("fresh_index", {})
    report["headline"] = (
        f"champion skill on unseen rows: {fresh.get('skill_score')} "
        f"({fresh.get('verdict')}, n={fresh.get('n')})")

    if args.ladder and 0 < wm < n:
        report["ladder"] = _run_ladder(X, yv, live["w"], wm)

    if args.json:
        print(json.dumps(report, indent=2))
        return 0

    print(f"champion {report['champion']} ({report['model_kind']}), "
          f"trained_rows={wm}, corpus={n}")
    print(f"  {span_line}")
    il = align.get("interleave_rows")
    if il:
        print(f"  [!] watermark interleave: {il} rows sit in the index-fresh "
              f"window whose signal time predates it (late-resolving labels)")
    for name, r in report["windows"].items():
        if "error" in r:
            print(f"  {name:12s} {r['error']}")
            continue
        note = "  (BELOW MIN ROWS)" if r["insufficient_rows"] else ""
        print(f"\n  {name:12s} n={r['n']} base={r['base_rate']:.4f}{note}")
        print(f"    brier {r['brier']:.5f} vs oracle constant "
              f"{r['oracle_constant_brier']:.5f} "
              f"({r['excess_over_oracle']:+.5f})")
        print(f"    SKILL {r['skill_score']}  -> {r['verdict']}")
        _ci = r.get("skill_ci") or {}
        if _ci.get("available"):
            print(f"    95% CI [{_ci['ci95'][0]:+.5f}, {_ci['ci95'][1]:+.5f}] "
                  f"on {_ci['blocks']} {_ci['basis']} blocks; this window "
                  f"resolves |skill| > {_ci['mde_2se']:.5f}")
        elif _ci:
            print(f"    95% CI unavailable ({_ci.get('reason')}) - the "
                  f"verdict above is a point estimate with no resolution")
        print(f"    calibrated p range [{r['p_min']:.4f}, {r['p_max']:.4f}] "
              f"sd {r['p_sd']:.4f}")
    if report.get("ladder"):
        print("\n  capacity ladder (same unseen rows; nothing deployed):")
        for r in report["ladder"]:
            if r.get("error"):
                print(f"    {r['rung']:26s} {r['error']}")
                continue
            print(f"    {r['rung']:26s} brier {r['brier']:.5f}  "
                  f"skill {r['skill_score']:+.5f}  {r['verdict']}")
        best = next((r for r in report["ladder"]
                     if r.get("skill_score") is not None), None)
        if best is not None and best["skill_score"] <= 0:
            print("    -> NO rung beats a constant: the binding constraint "
                  "is the TARGET, not model capacity.")

    print(f"\n{report['headline']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
