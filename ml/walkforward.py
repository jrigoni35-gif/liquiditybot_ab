"""
ml/walkforward.py — purged walk-forward validation + honest model
selection, rev 3

Purged walk-forward with embargo (Lopez de Prado): standard K-fold
leaks future information into training through label overlap — a trade
labeled with a 96-bar barrier "knows" 96 bars past its entry. The
purge drops training samples whose label windows overlap the test
block; expanding windows keep training strictly in the past.

rev-3 changes to SELECTION, not validation:

  * Three candidates: logistic (linear baseline), gbt (Newton-boosted
    shallow trees — the strongest tabular learner at this data scale),
    ensemble-MLP (smooth nonlinear).
  * Winner chosen on mean out-of-fold BRIER, not AUC. Kelly consumes
    probabilities literally; a model that ranks well but lies about
    magnitudes sizes every trade wrong in the same direction. AUC is
    still computed and logged for diagnosis.
  * Simplicity ladder: a more complex model must beat the next-simpler
    one by > brier_margin (default 0.002) to ship. Small live datasets
    should — and will — select the baseline at first. That's the
    system working, not failing.

API is a strict superset of rev 2: results carries 'logistic', 'mlp',
'gbt' blocks ({aucs, mean_auc, mean_brier, oof_p, oof_y}), plus
'selected', 'model', 'importance'.
"""

import logging

import numpy as np

from ml.calibration import brier_score
from ml.models import (BlendModel, EnsembleMLP, GradientBoostedStumps,
                       LogisticModel, auc_score)

log = logging.getLogger("liquiditybot.ml.walkforward")

# simple -> complex; a step right must EARN its complexity. blend
# (logistic+gbt probability average, unfitted 0.5 weight) sits above
# gbt: it contains gbt plus a second learner, so it must beat gbt by
# the margin to ship — the "stronger model" transition is evidence-
# gated, never assumed.
_LADDER = ("logistic", "gbt", "blend", "mlp")
BRIER_MARGIN = 0.002


def purged_walk_forward(n: int, n_splits: int = 5, label_span: int = 96,
                        embargo_frac: float = 0.02):
    """Yields (train_idx, test_idx) with purge + embargo, expanding window."""
    if n < (n_splits + 1) * 30:
        n_splits = max(2, n // 60)
    # NOTE: with an expanding window (train strictly precedes test) the
    # post-test embargo is a no-op — it only matters for combinatorial CV
    # where training data can follow the test block. embargo_frac is kept
    # in the signature for API stability.
    fold = n // (n_splits + 1)
    for k in range(1, n_splits + 1):
        test_start = k * fold
        test_end = min(test_start + fold, n)
        train_end = max(test_start - label_span, 0)          # purge
        train_idx = np.arange(0, train_end)
        test_idx = np.arange(test_start, test_end)
        if len(train_idx) >= 30 and len(test_idx) >= 10:
            yield train_idx, test_idx


def permutation_importance(model, X_te, y_te, names, n_top: int = 10,
                           seed: int = 7) -> list:
    """Shuffle one feature at a time on a true OOS fold; the AUC drop is
    what the model genuinely uses. ~zero or negative = dead weight."""
    rng = np.random.default_rng(seed)
    base = auc_score(y_te, model.predict_proba(X_te))
    drops = []
    for j, name in enumerate(names):
        Xp = X_te.copy()
        rng.shuffle(Xp[:, j])
        drops.append((name, round(base - auc_score(
            y_te, model.predict_proba(Xp)), 4)))
    drops.sort(key=lambda kv: -kv[1])
    return drops[:n_top]


def _factories(seed: int, ensemble_k: int) -> dict:
    return {
        "logistic": lambda: LogisticModel(seed=seed),
        "gbt": lambda: GradientBoostedStumps(seed=seed),
        "blend": lambda: BlendModel(seed=seed),
        "mlp": lambda: EnsembleMLP(k=ensemble_k, seed=seed),
    }


def evaluate_and_select(X: np.ndarray, y: np.ndarray, label_span: int = 96,
                        n_splits: int = 5, seed: int = 7,
                        sample_weight=None, feature_names=None,
                        ensemble_k: int = 3) -> dict:
    """Walk-forward all candidates; ship the Brier winner (simplicity-
    biased), fitted on all data."""
    X = np.asarray(X, float)
    y = np.asarray(y, float)
    w = None if sample_weight is None else np.asarray(sample_weight, float)
    factories = _factories(seed, ensemble_k)
    results = {}
    last_fold_model: dict = {}

    for name in _LADDER:
        factory = factories[name]
        aucs, briers, oof_p, oof_y = [], [], [], []
        for tr, te in purged_walk_forward(len(X), n_splits, label_span):
            if y[tr].sum() < 5 or (len(y[tr]) - y[tr].sum()) < 5:
                continue
            model = factory().fit(
                X[tr], y[tr], sample_weight=None if w is None else w[tr])
            p_te = model.predict_proba(X[te])
            aucs.append(auc_score(y[te], p_te))
            briers.append(brier_score(y[te], p_te))
            oof_p.append(p_te)
            oof_y.append(y[te])
            last_fold_model[name] = (model, te)
        results[name] = {
            "aucs": aucs,
            "mean_auc": float(np.mean(aucs)) if aucs else 0.5,
            "mean_brier": float(np.mean(briers)) if briers else 0.25,
            "oof_p": np.concatenate(oof_p) if oof_p else np.empty(0),
            "oof_y": np.concatenate(oof_y) if oof_y else np.empty(0),
        }
        log.info("%s: fold AUCs=%s mean_auc=%.3f mean_brier=%.4f",
                 name, [f"{a:.3f}" for a in aucs],
                 results[name]["mean_auc"], results[name]["mean_brier"])

    # simplicity-biased Brier selection: climb the ladder only on merit
    winner = _LADDER[0]
    for cand in _LADDER[1:]:
        if results[cand]["mean_brier"] < \
                results[winner]["mean_brier"] - BRIER_MARGIN:
            winner = cand
    final = factories[winner]().fit(X, y, sample_weight=w)
    results["selected"] = winner
    results["model"] = final
    results["importance"] = []
    if feature_names is not None and winner in last_fold_model:
        model_f, te = last_fold_model[winner]
        if len(te) >= 20:
            results["importance"] = permutation_importance(
                model_f, X[te], y[te], feature_names)
            log.info("top features (OOS AUC drop): %s",
                     results["importance"][:5])
    log.info("selected model: %s (brier %s)", winner,
             {k: round(results[k]["mean_brier"], 4) for k in _LADDER})
    return results
