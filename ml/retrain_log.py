"""Per-retrain history — the continuous learning curve.

Each retrain used to overwrite meta_model.json; the per-family OOF scores,
what was gated, and why a challenger lost survived only as audit one-liners.
One JSONL row per retrain (auto or CLI) makes learning progress a queryable
series: watch challengers converge on the champion bar, plot OOF vs corpus
size over time, audit every promotion and rejection. Capture-only.
"""
import json
import logging

from core.runtime import durable_append

log = logging.getLogger("liquiditybot.ml.retrain_log")

# Where the history lands when ml.retrain_history_path is absent - which is
# the shipped state (config.json does not set the key), so this IS the
# production path. Kept as a REBINDABLE module attribute so tests can point
# it at tmp: measured 2026-07-31, 305 of the 306 records in the operator's
# real outputs/retrain_history.jsonl were suite fixtures, and a prior
# session mistook the resulting degeneracy for a corpus-size problem.
# Referenced through the MODULE by both callers (main.py's auto path and
# scripts/train_meta.py's CLI path) so one rebind covers both.
RETRAIN_HISTORY_PATH_DEFAULT = "outputs/retrain_history.jsonl"

_FAMILIES = ("logistic", "gbt", "blend", "mlp", "adaptive_gbt")


def family_metric(results: dict, metric: str) -> dict:
    """Per-family {name: round(value,5)} for one metric out of the
    evaluate_and_select results dict; families missing the metric (or not
    dicts) are omitted. Report-only accessor - never a decision input."""
    return {k: round(float(results[k][metric]), 5) for k in _FAMILIES
            if isinstance(results.get(k), dict) and metric in results[k]}


def retrain_record(now: float, source: str, results: dict, n_rows: int,
                   n_live: int, oof_brier, champion_bar,
                   deployed: bool, trained_rows=None) -> dict:
    """One history row per retrain. Capture-only; nothing reads it back.

    `trained_rows` (the INCUMBENT champion's row watermark) is optional and
    report-only. It exists because the ML-083 era-orphan unlock keys on
    `trained_rows > n_rows` — and until 2026-08-14 the ratio between those two
    numbers was recoverable only by hand-joining this ledger against
    registry.jsonl, which is why a 48x orphan (10,217 vs 211) fired the unlock
    and promoted a negative-skill model with nothing plotting the condition.
    Recording it makes the firing condition a queryable series instead of a
    forensic exercise. Extended with a DEFAULT so every existing caller keeps
    working unchanged (invariant 7); a caller that omits it simply logs None.
    Neither field is ever a decision input.
    """
    fams = family_metric(results, "mean_brier")
    _tr = None if trained_rows is None else int(trained_rows)
    # ratio, not a difference: the unlock's severity is scale-free, and the
    # 3.2x it was designed for vs the 48x it fired at is the whole finding
    _orphan = (round(_tr / int(n_rows), 4)
               if _tr and int(n_rows) > 0 else None)
    return {"ts": round(float(now), 1), "source": source,
            "rows": int(n_rows), "live": int(n_live),
            "trained_rows": _tr, "orphan_ratio": _orphan,
            "selected": results.get("selected"),
            "admitted": results.get("admitted"),
            "gated": results.get("gated"),
            "family_brier": fams,
            "oof_brier": (None if oof_brier is None
                          else round(float(oof_brier), 5)),
            "champion_bar": (None if champion_bar is None
                             else round(float(champion_bar), 5)),
            "deployed": bool(deployed),
            "family_calib_gap": family_metric(results, "calib_gap")}


def append_retrain(path, record: dict) -> None:
    """Append one JSONL row; never raises into the retrain path.

    durable_append heals a torn tail (a kill mid-write otherwise welds the
    fragment to the NEXT record and json.loads then drops both) and fsyncs.
    Reproduced on this file 2026-08-06: one kill destroyed 2 retrain
    records."""
    line = json.dumps(record, sort_keys=True) + "\n"
    durable_append(path, lambda f: f.write(line), newline="\n",
                   torn_sep="\n")
