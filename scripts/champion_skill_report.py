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

Skill score = 1 - brier / (b*(1-b)).  <= 0 means NO SKILL.

SAFE / measurement-plane: reads only, opens no positions, writes nothing,
alters no order. Run it any time:

    python scripts/champion_skill_report.py
    python scripts/champion_skill_report.py --json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np

# Brier of the best possible constant is b*(1-b); a window with no label
# variation makes skill undefined rather than infinite.
MIN_WINDOW_ROWS = 30


def skill_score(brier: float, base_rate: float) -> float | None:
    """Skill vs the oracle constant predictor. None when undefined.

    A degenerate window (all one class) has oracle brier 0 and no
    meaningful skill denominator - say so instead of dividing by zero.
    """
    oracle = float(base_rate) * (1.0 - float(base_rate))
    if oracle <= 0.0:
        return None
    return 1.0 - float(brier) / oracle


def window_report(p_cal: np.ndarray, y: np.ndarray,
                  train_base: float | None = None) -> dict[str, Any]:
    """Skill of calibrated predictions `p_cal` against labels `y`.

    Pure: no I/O, no globals. `train_base` (the training-window base rate)
    adds the weaker train-constant null for context when supplied.
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
    out["verdict"] = ("UNDEFINED (degenerate window)" if sk is None
                      else "NO SKILL" if sk <= 0.0 else "skill")
    if train_base is not None:
        out["train_constant_brier"] = round(
            float(np.mean((float(train_base) - y) ** 2)), 6)
    return out


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
    return {"X": X[keep], "y": y[keep], "sig": sig[keep],
            "meta_path": Path(ml_cfg.get("model_path",
                                         "outputs/meta_model.json"))}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true", help="machine-readable")
    args = ap.parse_args(argv)

    live = _load_live()
    X, y, sig = live["X"], live["y"], live["sig"]
    meta_path: Path = live["meta_path"]
    if not meta_path.exists():
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
        "windows": {k: window_report(p[m], yv[m], train_base)
                    for k, m in windows.items() if int(m.sum()) > 0},
    }
    fresh = report["windows"].get("fresh_index", {})
    report["headline"] = (
        f"champion skill on unseen rows: {fresh.get('skill_score')} "
        f"({fresh.get('verdict')}, n={fresh.get('n')})")

    if args.json:
        print(json.dumps(report, indent=2))
        return 0

    print(f"champion {report['champion']} ({report['model_kind']}), "
          f"trained_rows={wm}, corpus={n}")
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
        print(f"    calibrated p range [{r['p_min']:.4f}, {r['p_max']:.4f}] "
              f"sd {r['p_sd']:.4f}")
    print(f"\n{report['headline']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
