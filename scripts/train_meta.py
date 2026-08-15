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
import time
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402

from core.audit import configure_audit, get_audit  # noqa: E402
from core.codes import Code  # noqa: E402

# SIDE-CAR AUDIT: this script can run beside a LIVE runner (operator
# retrain). Two processes appending to the prod chain each hold their own
# in-memory seq/prev and fork it — observed live 2026-07-13: a manual run's
# ML-041 landed as a duplicate seq 227, breaking verification from record
# 228 and tripping the check-in watchdog every 4h (SD-007). The runner's
# own in-process records remain the chain of record for deploys.
configure_audit(Path(__file__).resolve().parents[1]
                / "outputs" / "audit_train_meta.jsonl")
from ml.history import (bootstrap_dataset, load_for_config,  # noqa: E402
                        store_for_config)
from ml.labeling import ExitPolicy  # noqa: E402
from ml.walkforward import evaluate_and_select  # noqa: E402
from ml.models import save_model  # noqa: E402
from ml.calibration import IsotonicCalibrator, brier_score, feature_deciles  # noqa: E402
from ml.features import FEATURE_NAMES  # noqa: E402

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("train_meta")


def _deploy_challenger(config: dict, model, challenger_brier: float,
                       extra: dict, model_path: str,
                       n_oof: int | None = None,
                       X=None, y=None, oof_idx=None) -> bool:
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
        monitor.restore(state_data.get("monitor") or {})
    # STALE-BADGE GUARD, CLI lane (ML-042 parity, 2026-07-28): the
    # restored champion_brier is a birth certificate from an older corpus
    # era. The engine's auto-retrain rescored the frozen champion on the
    # same fresh OOF rows before gating (main.py, 8b91f69) — but this CLI
    # gate kept comparing against the badge, reproducing the exact squat
    # that fix removed: a stale-low badge rejects every honestly-scored
    # CLI challenger forever. When the caller supplies the OOF context,
    # rescore the on-disk champion on it and realign; any load/score
    # failure keeps the badge (rescore_frozen is fail-safe by contract).
    if X is not None and y is not None and oof_idx is not None:
        try:
            from ml.meta_model import MetaModelService
            champ = MetaModelService({"model_path": model_path,
                                      **({} if not isinstance(ml_cfg, dict)
                                         else ml_cfg)})
            champ.reload()
            champ_fresh = ModelMonitor.rescore_frozen(
                champ.model, champ.calibrator, X, y, oof_idx,
                champ.trained_rows, monitor.deploy_min_oof)
        except Exception:                # noqa: BLE001 - fail-safe realign
            champ_fresh = None
        if champ_fresh is not None and \
                abs(champ_fresh - monitor.champion_brier) > 1e-9:
            log.warning("champion badge realigned on fresh OOF: "
                        "%.4f -> %.4f (frozen champion rescored on the "
                        "challenger's own OOF rows — ML-042 parity)",
                        monitor.champion_brier, champ_fresh)
            monitor.champion_brier = champ_fresh
    prev_champion = monitor.champion_brier

    # W2-2 stale-gate CAS: snapshot the on-disk champion's identity right
    # here, before the gate decision - the runner's in-process auto-retrain
    # can be racing this exact deploy against the SAME champion. save_model()
    # re-checks this immediately before its write and refuses if a
    # concurrent writer already deployed since.
    from ml.registry import sha256_file
    _model_path_p = Path(model_path)
    try:
        _prior_hash = sha256_file(_model_path_p) if _model_path_p.exists() else None
    except OSError:
        _prior_hash = None

    # LP-6: pass the OOF count so the deploy_min_oof evidence floor binds
    # for CLI retrains exactly as it does for the runner's auto path - a
    # Brier on a handful of points beats a coin by luck, never by skill.
    if not monitor.should_deploy(challenger_brier, n_oof=n_oof):
        log.error(f"REJECTED: challenger OOF Brier {challenger_brier:.4f} "
                  f"does not beat champion {prev_champion:.4f} by the "
                  f"required margin ({monitor.deploy_margin:.4f}) - "
                  f"{model_path} left unchanged. This mirrors the bot's "
                  f"own auto-retrain deploy gate.")
        return False

    if not save_model(model, model_path, extra=extra,
                      expect_prior_sha256=_prior_hash):
        log.error(f"REJECTED: a concurrent writer (the running bot's own "
                  f"auto-retrain, or another CLI run) already deployed to "
                  f"{model_path} since this gate read the champion - "
                  f"discarding this challenger rather than clobbering the "
                  f"newer artifact. Re-run against the current champion if "
                  f"this challenger should still compete.")
        return False
    monitor.note_deployed(challenger_brier)
    # ML-060 lineage, same gap the in-process auto-retrain had: this CLI path
    # also makes an artifact champion, and the registry recorded neither the
    # promotion nor the retirement it causes. `_prior_hash` was already taken
    # above for the stale-gate CAS, so the outgoing identity is in hand — its
    # first 12 hex ARE the model_id (ml/registry.register).
    try:
        from ml.registry import get_registry, sha256_file as _sha
        _reg = get_registry()
        _new_id = _sha(str(model_path))[:12]
        _reg.note("deployed", _new_id,
                  {"oof_brier": float(challenger_brier),
                   "prev_champion_brier": (None if prev_champion is None
                                           else float(prev_champion)),
                   "source": "cli_train_meta"})
        _old_id = None if _prior_hash is None else str(_prior_hash)[:12]
        if _old_id and _old_id != _new_id:
            _reg.note("retired", _old_id,
                      {"superseded_by": _new_id,
                       "reason": "cli_train_meta_promotion"})
    except Exception:                                # noqa: BLE001
        log.debug("registry deploy/retire note failed", exc_info=True)
    # Persist the new baseline onto the FRESHEST snapshot, never the
    # gate-time copy: this script runs beside a LIVE runner (side-car audit
    # note above) whose 30s snapshot cadence can land a newer book between
    # this function's load_raw() and here. Writing the gate-time dict back
    # published that stale book as the primary generation - positions
    # closed during the gate resurrected and executed fills vanished from
    # balances whenever the runner died before its next snapshot (e.g.
    # auto_update's taskkill escalation). Re-reading shrinks the exposure
    # from the whole rescore+gate+save window to one read-write pair, and
    # the runner's next 30s snapshot supersedes even that.
    fresh = store.load_raw()
    if fresh is not None:
        fresh["monitor"] = monitor.to_dict()
        if not store.write_raw(fresh):
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

    # ml.history.store_for_config / load_for_config: the ONE loader seam
    # every offline consumer shares (2026-08-01 audit H12). The bare
    # HistoryStore() here defaulted max_bars to the legacy 96, so
    # current_era resolved to "triple_barrier" while main.py:714 passes
    # ml.label_max_bars (24) -> "triple_barrier_h24". With era exclusion
    # armed on both sides (both counts clear min_new_era_rows) the two
    # filters kept DISJOINT sets: measured on the real corpus, max_bars=96
    # -> 2141 rows / 0 live, max_bars=24 -> 1090 rows / 14 live. This
    # script then DEPLOYED the model fitted on production's complement,
    # and main.py's reload_if_changed adopts it in-cycle (schema-width
    # check only, no era check). config_guard FATALs label_max_bars >=
    # max_bars_no_progress (36), so a valid live config can never be 96 -
    # the drift was structurally guaranteed, not incidental.
    # load_for_config additionally sources half_life_days/candidate_weight/
    # manip_discount from ml.sample_weights instead of literals here
    # (manip_discount was not passed at all, so a retuned value was honored
    # by the in-process retrain and silently ignored by this CLI).
    sw_cfg = ml_cfg.get("sample_weights", {})
    store = store_for_config(ml_cfg)
    # signal-time array too: the deployed selector must purge folds by TIME, not
    # row count. Signals arrive in bursts, so a fixed row count spans a variable
    # amount of time and a dense pre-boundary burst leaks future labels the
    # row-count purge silently keeps (OF-6). overfit_check already measures the
    # TIME-purged process; without this the DEPLOYED selection didn't use it.
    X, y, w, sig, res = load_for_config(store, ml_cfg,
                                        return_label_times=True)
    # LP-4: same training screen as the engine path - see check_matrix
    from ml.contracts import get_contract
    _keep = get_contract().check_matrix(X)["keep"]
    if not _keep.all():
        X, y, w, sig, res = X[_keep], y[_keep], w[_keep], sig[_keep], \
            res[_keep]
    source = "live history"

    if args.bootstrap or len(X) < min_rows:
        log.info(f"live rows={len(X)} (<{min_rows}) - building bootstrap dataset "
                 f"from OKX 5m candles")
        from data.okx_feed import OKXFeed
        okx = OKXFeed(config["exchanges"]["okx"])
        Xb, yb, sigb = [], [], []
        for sym in config["exchanges"]["okx"].get("symbols", []):
            # deep paginated history (~10 days of 5m bars): the plain candles
            # endpoint caps at 300 bars, which yields too few EMA-cross
            # events to train on (observed: 18 samples < the 60 floor)
            candles = okx.get_history_candles(sym, bar="5m", total=2880)
            if len(candles) < 300:
                candles = okx.get_candles(sym, bar="5m", limit=300)
            xs, ys, ss = bootstrap_dataset(
                candles,
                pt_mult=float(ml_cfg.get("label_pt_vol_mult", 8)),
                sl_mult=float(ml_cfg.get("label_sl_vol_mult", 6)),
                max_bars=int(ml_cfg.get("label_max_bars", 96)),
                cost_pct=float(ml_cfg.get("label_round_trip_cost_pct", 0.5)),
                pt_cost_mult=float(ml_cfg.get("label_pt_cost_mult", 0.0)),
                label_mode=str(ml_cfg.get("label_mode", "exit_policy")),
                exit_policy=ExitPolicy.from_config(config),
                return_sig=True)
            if len(xs):
                Xb.append(xs)
                yb.append(ys)
                sigb.append(ss)
        if Xb:
            n_live_rows = len(X)
            Xb, yb = np.vstack(Xb), np.concatenate(yb)
            X = np.vstack([X, Xb]) if len(X) else Xb
            y = np.concatenate([y, yb]) if len(y) else yb
            wb = np.full(len(yb), float(sw_cfg.get("candidate_weight", 0.4)))
            w = np.concatenate([w, wb]) if len(w) else wb
            # M10 (2026-08-01 audit): every symbol's block was vstacked
            # WHOLE, so the matrix's clock RESTARTED at each block boundary
            # and purged_walk_forward's row-count purge (correct only for
            # evenly-spaced rows) trained on ETH labels contemporaneous
            # with - in fact strictly LATER than - the entire BTC test
            # block. Measured OOF-Brier optimism scaled monotonically with
            # cross-asset return correlation (rho=0.85 -> -0.0138, 2.7x
            # challenger_brier_margin; 3 of 8 trials crossed the 0.25
            # no-champion crown threshold that honest scoring did not).
            # Sorting the whole matrix onto ONE global signal clock is what
            # makes the TIME purge meaningful across blocks.
            sig = np.concatenate([np.asarray(sig, float),
                                  np.concatenate(sigb)])
            # bootstrap rows have no measured RESOLUTION time (the barrier
            # sim's exit bar is not the same fact as a live row's append
            # ts), so the mixed matrix drops to the fixed-horizon time
            # purge - sig + label_span. Explicit, not a silent
            # length-mismatch fallback inside purged_walk_forward.
            res = None
            order = np.argsort(sig, kind="mergesort")
            X, y, w, sig = X[order], y[order], w[order], sig[order]
            source = f"live({n_live_rows}) + bootstrap({len(Xb)})"

    if len(X) < 60:
        log.error(f"only {len(X)} samples - not enough to train anything honest. "
                  f"Run the bot in dry_run to collect history, or fetch more candles.")
        return 1

    log.info(f"training on {len(X)} samples ({source}), "
             f"base rate={y.mean():.2%} wins")
    # A cold-start mix now carries a coherent global clock (bootstrap rows
    # return their entry-bar time and the whole matrix is sorted on it), so
    # the leak-free TIME purge stays engaged for EVERY corpus - including
    # `--bootstrap` against a populated corpus, which previously stripped
    # the time purge from all the live/candidate rows too. What remains is
    # the residual alignment invariant: a length disagreement means the
    # arrays are no longer row-aligned, and a MISALIGNED time purge is
    # worse than an honest row-count one.
    if sig is not None and len(sig) != len(X):
        log.warning("signal-time array (%d) is not aligned to X (%d) — "
                    "falling back to the row-count purge this run",
                    len(sig), len(X))
        sig = None
    # opt-in top rung: only enters the deployed selection when the operator
    # turns it on (ml.adaptive_gbt.enabled). Disabled -> extra_models=() ->
    # the historical ladder, byte-for-byte.
    ag_cfg = ml_cfg.get("adaptive_gbt", {}) or {}
    extra_models = ("adaptive_gbt",) if ag_cfg.get("enabled") else ()
    # EVIDENCE GATE: complexity is earned on LIVE (real closed-trade) labels,
    # never on bootstrap/candidate proxies - a bootstrap-padded X can be large
    # yet carry almost no ground truth, so count the store's live split, not
    # len(X). Below the floor the complex families are not trained at all.
    # Count from the load's own CLEAN pass, exactly as main.py:5719-5725
    # does (and overfit_check.py:198 / feature_stability.py:289): a raw
    # header-indexed source_counts() scan applies NONE of the loader's
    # admissibility rules - book=="long" exclusion, dirty drops, era
    # exclusion - so it counts rows that never enter the fit. Measured on
    # the live corpus: source_counts()["live"]=275 vs live_clean=0, and
    # admissible_families(275, ...) admits {adaptive_gbt, blend, gbt,
    # logistic, mlp} where production admits {logistic}. This CLI is the
    # only real-corpus consumer that writes a DEPLOYABLE artifact, so the
    # inflated count fitted mlp/adaptive_gbt (min_live_rows 250, the
    # strictest bar in the system) on a matrix with zero ground-truth live
    # labels and shipped it. Same value feeds retrain_record below, which
    # was writing the inflated count into outputs/retrain_history.jsonl.
    n_live = int((store.last_load_stats or {}).get(
        "live_clean", store.source_counts().get("live", 0)))
    select_cfg = ml_cfg.get("model_selection") or None
    results = evaluate_and_select(
        X, y, label_span=int(ml_cfg.get("label_max_bars", 96)),
        sample_weight=w, feature_names=FEATURE_NAMES,
        ensemble_k=int(ml_cfg.get("ensemble_seeds", 3)), sig=sig,
        extra_models=extra_models, adaptive_cfg=ag_cfg,
        n_live=n_live, select_cfg=select_cfg, res=res)
    if results.get("gated"):
        log.info("selection evidence-gated: trained %s, skipped %s "
                 "(%d live labels, %d total rows)", results.get("admitted"),
                 results["gated"], n_live, len(X))
    sel = results[results["selected"]]
    cal = IsotonicCalibrator().fit(sel["oof_p"], sel["oof_y"])
    if not cal.fitted:
        log.warning(f"ML-014: calibration skipped - only "
                   f"{len(sel['oof_p'])} OOF points (<20 needed) - "
                   f"challenger ships with raw, uncalibrated probabilities")
        get_audit().log("ml_governor", Code.ML_CALIBRATION_SKIPPED,
                        f"isotonic PAV had {len(sel['oof_p'])} OOF points "
                        f"(<20) - manual retrain challenger ships "
                        f"uncalibrated",
                        {"oof_points": int(len(sel["oof_p"]))})
    # CALIBRATION-HONEST GATE SCORE (round-2 finding, 2026-08-05). The
    # shipped artifact keeps its full-pool PAV calibrator above (unchanged),
    # but scoring the challenger with a calibrator fit on the very rows it
    # is then scored on is IN-SAMPLE, while the champion is rescored
    # strictly out-of-sample by rescore_frozen. main.py's auto-retrain lane
    # fixed this in H13 - measured optimism +0.0032..+0.0066, i.e. 25-150%
    # of the 0.005 deploy margin, always pro-challenger - and this CLI lane
    # never got it, so a manual retrain could deploy a strictly worse model
    # (and stamp the optimistic number into the artifact as the next
    # champion badge). Same helper, same folds: one gate, one standard.
    from main import cross_fitted_calibrated_oof
    oof_cal = (cross_fitted_calibrated_oof(sel["oof_p"], sel["oof_y"])
               if len(sel["oof_p"]) else sel["oof_p"])
    if not len(oof_cal):
        # LP-6: a challenger with ZERO out-of-fold predictions has no
        # measured skill - the old path fabricated oof_brier=0.25 and
        # walked it into the champion gate as if observed. Refuse:
        # unmeasured never deploys.
        log.error("no OOF predictions (corpus too small for the fold "
                  "grid) - refusing to deploy an unmeasured challenger")
        return 1
    oof_brier = brier_score(sel["oof_y"], oof_cal)
    log.info(f"OOF Brier (calibrated): {oof_brier:.4f} "
             f"(calibrator fitted={cal.fitted})")
    if results.get("importance"):
        log.info("feature importance (OOS AUC drop): " +
                 ", ".join(f"{n}={v:+.3f}" for n, v in results["importance"]))
    briers = " ".join(f"{k} brier={results[k]['mean_brier']:.4f}"
                      for k in ("logistic", "gbt", "blend", "mlp",
                                "adaptive_gbt") if k in results)
    log.info(f"selected={results['selected']} {briers}")
    log.info("NOTE: walk-forward AUC on bootstrap data is a weak prior, not "
             "proof of edge. The model improves as live labeled trades accrue.")
    from ml.interpret import background_sample
    extra = {"calibration": cal.to_dict(), "oof_brier": oof_brier,
             "feature_deciles": feature_deciles(X),
             # walk-forward importance under its OWN key: "importance"
             # would overwrite the gbt model's internal per-feature dict
             # and crash from_dict on the next load
             "wf_importance": results.get("importance", []),
             # history-spanning background so interventional SHAP
             # (scripts/interpret_report.py) is defined for this artifact
             "background": background_sample(
                 X, int(ml_cfg.get("interpret", {})
                        .get("background_rows", 64)))}
    deployed = _deploy_challenger(config, results["model"], oof_brier,
                                  extra, model_path,
                                  n_oof=int(len(oof_cal)),
                                  X=X, y=y,
                                  oof_idx=results.get("oof_idx"))
    from ml import retrain_log as _rl
    from ml.retrain_log import append_retrain, retrain_record
    append_retrain(
        ml_cfg.get("retrain_history_path",
                   _rl.RETRAIN_HISTORY_PATH_DEFAULT),
        retrain_record(time.time(), "cli", results, len(X),
                       int(n_live), oof_brier, None, deployed))
    return 0 if deployed else 1


if __name__ == "__main__":
    raise SystemExit(main())
