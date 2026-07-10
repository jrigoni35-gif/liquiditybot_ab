"""
scripts/train_meta.py

Trains/retrains the meta-labeling model and writes outputs/meta_model.json,
which the running bot picks up (restart it or it reloads on next start).

Data priority:
  1. Live labeled history (outputs/signal_history.csv) once it has at
     least ml.min_train_rows rows - the bot's own fills and costs.
  2. Otherwise a bootstrap dataset from OKX 5m candle history:
     EMA-cross pseudo-signals through the triple-barrier labeler.
     Weaker data, clearly reported as such.

Model selection is purged walk-forward (see ml/walkforward.py): the MLP
must beat the logistic baseline out-of-sample to ship.

Usage:
    python scripts/train_meta.py            # auto data selection
    python scripts/train_meta.py --bootstrap  # force bootstrap
"""

import argparse
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402

from ml.history import HistoryStore, bootstrap_dataset  # noqa: E402
from ml.walkforward import evaluate_and_select  # noqa: E402
from ml.models import save_model  # noqa: E402
from ml.calibration import IsotonicCalibrator, brier_score, feature_deciles  # noqa: E402
from ml.features import FEATURE_NAMES  # noqa: E402

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("train_meta")


def _deploy_challenger(config: dict, model, challenger_brier: float,
                       extra: dict, model_path: str) -> bool:
    """Champion/challenger deploy gate for a manually-trained model. Mirrors
    the gate main.py's in-process auto-retrain already enforces (ModelMonitor
    .should_deploy/.note_deployed) so a CLI retrain cannot silently swap in
    a worse model - previously this script called save_model() unconditionally.
    Returns True if the model was deployed."""
    from ml.monitor import ModelMonitor
    from core.persistence import StateStore

    ml_cfg = config.get("ml", {})
    state_path = config.get("system", {}).get("state_path",
                                               "outputs/state.json")
    store = StateStore(state_path)
    state_data = store.load_raw()
    monitor = ModelMonitor(ml_cfg.get("monitor", {}))
    if state_data:
        monitor.restore(state_data.get("monitor"))
    prev_champion = monitor.champion_brier

    if not monitor.should_deploy(challenger_brier):
        log.error(f"REJECTED: challenger OOF Brier {challenger_brier:.4f} "
                  f"does not beat champion {prev_champion:.4f} by the "
                  f"required margin ({monitor.deploy_margin:.4f}) - "
                  f"{model_path} left unchanged. This mirrors the bot's "
                  f"own auto-retrain deploy gate.")
        return False

    save_model(model, model_path, extra=extra)
    monitor.note_deployed(challenger_brier)
    if state_data is not None:
        state_data["monitor"] = monitor.to_dict()
        if not store.write_raw(state_data):
            log.warning("model deployed, but failed to persist the "
                       "updated champion baseline to state.json - a "
                       "running bot will still show the old baseline "
                       "until restarted")
    else:
        log.info("no state.json snapshot yet - champion baseline starts "
                "fresh from this deploy on next bot start")
    log.warning(f"DEPLOYED: challenger brier {challenger_brier:.4f} "
               f"(previous champion {prev_champion:.4f}) -> {model_path}. "
               f"Restart the running bot to load the new model.")
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.json")
    ap.add_argument("--bootstrap", action="store_true",
                    help="force bootstrap data even if live history exists")
    args = ap.parse_args()

    with open(args.config, encoding="utf-8") as f:
        config = json.load(f)
    ml_cfg = config.get("ml", {})
    min_rows = int(ml_cfg.get("min_train_rows", 150))
    model_path = ml_cfg.get("model_path", "outputs/meta_model.json")

    store = HistoryStore(ml_cfg.get("history_path", "outputs/signal_history.csv"))
    sw_cfg = ml_cfg.get("sample_weights", {})
    X, y, w = store.load_training_data(
        half_life_days=float(sw_cfg.get("half_life_days", 30)),
        candidate_weight=float(sw_cfg.get("candidate_weight", 0.4)))
    source = "live history"

    if args.bootstrap or len(X) < min_rows:
        log.info(f"live rows={len(X)} (<{min_rows}) - building bootstrap dataset "
                 f"from OKX 5m candles")
        from data.okx_feed import OKXFeed
        okx = OKXFeed(config["exchanges"]["okx"])
        Xb, yb = [], []
        for sym in config["exchanges"]["okx"].get("symbols", []):
            # deep paginated history (~10 days of 5m bars): the plain candles
            # endpoint caps at 300 bars, which yields too few EMA-cross
            # events to train on (observed: 18 samples < the 60 floor)
            candles = okx.get_history_candles(sym, bar="5m", total=2880)
            if len(candles) < 300:
                candles = okx.get_candles(sym, bar="5m", limit=300)
            xs, ys = bootstrap_dataset(candles,
                                       pt_mult=float(ml_cfg.get("label_pt_vol_mult", 8)),
                                       sl_mult=float(ml_cfg.get("label_sl_vol_mult", 6)),
                                       max_bars=int(ml_cfg.get("label_max_bars", 96)),
                                       cost_pct=float(ml_cfg.get("label_round_trip_cost_pct", 0.5)))
            if len(xs):
                Xb.append(xs)
                yb.append(ys)
        if Xb:
            Xb, yb = np.vstack(Xb), np.concatenate(yb)
            X = np.vstack([X, Xb]) if len(X) else Xb
            y = np.concatenate([y, yb]) if len(y) else yb
            wb = np.full(len(yb), float(sw_cfg.get("candidate_weight", 0.4)))
            w = np.concatenate([w, wb]) if len(w) else wb
            source = f"live({len(X) - len(Xb)}) + bootstrap({len(Xb)})"

    if len(X) < 60:
        log.error(f"only {len(X)} samples - not enough to train anything honest. "
                  f"Run the bot in dry_run to collect history, or fetch more candles.")
        return 1

    log.info(f"training on {len(X)} samples ({source}), "
             f"base rate={y.mean():.2%} wins")
    results = evaluate_and_select(
        X, y, label_span=int(ml_cfg.get("label_max_bars", 96)),
        sample_weight=w, feature_names=FEATURE_NAMES,
        ensemble_k=int(ml_cfg.get("ensemble_seeds", 3)))
    sel = results[results["selected"]]
    cal = IsotonicCalibrator().fit(sel["oof_p"], sel["oof_y"])
    oof_cal = cal.transform(sel["oof_p"]) if len(sel["oof_p"]) else sel["oof_p"]
    oof_brier = brier_score(sel["oof_y"], oof_cal) if len(oof_cal) else 0.25
    log.info(f"OOF Brier (calibrated): {oof_brier:.4f} "
             f"(calibrator fitted={cal.fitted})")
    if results.get("importance"):
        log.info("feature importance (OOS AUC drop): " +
                 ", ".join(f"{n}={v:+.3f}" for n, v in results["importance"]))
    log.info(f"selected={results['selected']} "
             f"logistic brier={results['logistic']['mean_brier']:.4f} "
             f"gbt brier={results['gbt']['mean_brier']:.4f} "
             f"blend brier={results['blend']['mean_brier']:.4f} "
             f"mlp brier={results['mlp']['mean_brier']:.4f}")
    log.info("NOTE: walk-forward AUC on bootstrap data is a weak prior, not "
             "proof of edge. The model improves as live labeled trades accrue.")
    extra = {"calibration": cal.to_dict(), "oof_brier": oof_brier,
             "feature_deciles": feature_deciles(X),
             # walk-forward importance under its OWN key: "importance"
             # would overwrite the gbt model's internal per-feature dict
             # and crash from_dict on the next load
             "wf_importance": results.get("importance", [])}
    if not _deploy_challenger(config, results["model"], oof_brier, extra,
                              model_path):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
