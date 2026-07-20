"""Per-retrain history — the continuous learning curve.

Each retrain used to overwrite meta_model.json; the per-family OOF scores,
what was gated, and why a challenger lost survived only as audit one-liners.
One JSONL row per retrain (auto or CLI) makes learning progress a queryable
series: watch challengers converge on the champion bar, plot OOF vs corpus
size over time, audit every promotion and rejection. Capture-only.
"""
import json
import logging
from pathlib import Path

log = logging.getLogger("liquiditybot.ml.retrain_log")


def retrain_record(now: float, source: str, results: dict, n_rows: int,
                   n_live: int, oof_brier, champion_bar,
                   deployed: bool) -> dict:
    fams = {k: round(float(results[k].get("mean_brier", float("nan"))), 5)
            for k in ("logistic", "gbt", "blend", "mlp", "adaptive_gbt")
            if isinstance(results.get(k), dict) and "mean_brier" in results[k]}
    return {"ts": round(float(now), 1), "source": source,
            "rows": int(n_rows), "live": int(n_live),
            "selected": results.get("selected"),
            "admitted": results.get("admitted"),
            "gated": results.get("gated"),
            "family_brier": fams,
            "oof_brier": (None if oof_brier is None
                          else round(float(oof_brier), 5)),
            "champion_bar": (None if champion_bar is None
                             else round(float(champion_bar), 5)),
            "deployed": bool(deployed)}


def append_retrain(path, record: dict) -> None:
    """Append one JSONL row; never raises into the retrain path."""
    try:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, sort_keys=True) + "\n")
    except OSError:
        log.exception("retrain history append failed - row lost, "
                      "retrain unaffected")
