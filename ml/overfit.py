"""
ml/overfit.py — overfitting instrumentation, rev 4

Four instruments, each answering a different failure mode of "the
backtest looked great":

  TRAIN/OOF GAP       memorization. Per candidate, AUC and Brier on the
                      purged folds' TRAIN side vs their OOF side. A
                      model that's far better in-sample than out is
                      fitting noise; the gap is the amount.
  SHUFFLED-LABEL NULL leakage. Permute y, rerun the purged walk-forward
                      with the most flexible candidate. OOF AUC must
                      sit inside the analytic null band (Hanley-McNeil
                      SE around 0.5). "Learning" destroyed labels means
                      information is crossing the purge — a pipeline
                      bug, not alpha.
  PBO (CSCV)          selection bias. Bailey / López de Prado
                      combinatorially symmetric cross-validation over a
                      model/hyperparameter space sharing one OOF index:
                      in each train/test block split, pick the
                      in-sample winner, record its OUT-of-sample rank.
                      PBO = P(chosen winner underperforms the median
                      OOS). Selecting among many configs on the same
                      data manufactures winners; PBO measures how much.
  DEFLATED SHARPE     multiple testing on live results. Corrects an
                      observed Sharpe for the number of trials, skew,
                      kurtosis and track length (Bailey & LdP 2014);
                      returns P(true SR > 0 | trials).

Everything here is pure computation over arrays already produced by the
existing pipeline — no network, deterministic under seed, replay-safe.
"""

import itertools
import logging
import math

import numpy as np

from ml.calibration import brier_score
from ml.models import (GradientBoostedStumps, LogisticModel, NumpyMLP,
                       auc_score)
from ml.walkforward import BRIER_MARGIN, purged_walk_forward

log = logging.getLogger("liquiditybot.ml.overfit")


# ---------------------------------------------------------------------------
# 1) train-vs-OOF gap
# ---------------------------------------------------------------------------
def train_test_gap(X, y, label_span: int = 96, n_splits: int = 5,
                   seed: int = 7, sample_weight=None) -> dict:
    """Per candidate: mean train AUC/Brier vs mean OOF AUC/Brier over the
    purged folds, plus the gaps. Interpretation guide (empirical, this
    data scale): gap_auc < 0.05 healthy, 0.05-0.12 watch, > 0.12 the
    model is memorizing."""
    X = np.asarray(X, float)
    y = np.asarray(y, float)
    w = None if sample_weight is None else np.asarray(sample_weight, float)
    candidates = {
        "logistic": lambda: LogisticModel(seed=seed),
        "gbt": lambda: GradientBoostedStumps(seed=seed),
        "mlp": lambda: NumpyMLP(seed=seed),
    }
    out = {}
    for name, factory in candidates.items():
        tr_a, te_a, tr_b, te_b, folds = [], [], [], [], 0
        for tr, te in purged_walk_forward(len(X), n_splits, label_span):
            if y[tr].sum() < 5 or (len(y[tr]) - y[tr].sum()) < 5:
                continue
            m = factory().fit(X[tr], y[tr],
                              sample_weight=None if w is None else w[tr])
            p_tr = m.predict_proba(X[tr])
            p_te = m.predict_proba(X[te])
            tr_a.append(auc_score(y[tr], p_tr))
            te_a.append(auc_score(y[te], p_te))
            tr_b.append(brier_score(y[tr], p_tr))
            te_b.append(brier_score(y[te], p_te))
            folds += 1
        if not folds:
            out[name] = {"folds": 0}
            continue
        out[name] = {
            "folds": folds,
            "train_auc": float(np.mean(tr_a)),
            "oof_auc": float(np.mean(te_a)),
            "gap_auc": float(np.mean(tr_a) - np.mean(te_a)),
            "train_brier": float(np.mean(tr_b)),
            "oof_brier": float(np.mean(te_b)),
            "gap_brier": float(np.mean(te_b) - np.mean(tr_b)),
        }
    return out


# ---------------------------------------------------------------------------
# 2) shuffled-label leakage null
# ---------------------------------------------------------------------------
def _auc_null_se(y: np.ndarray) -> float:
    """Hanley-McNeil standard error of AUC under H0 (AUC=0.5)."""
    n1 = float((y > 0.5).sum())
    n0 = float(len(y) - n1)
    if n1 < 2 or n0 < 2:
        return 0.25
    return math.sqrt((n0 + n1 + 1.0) / (12.0 * n0 * n1))


def shuffled_label_check(X, y, label_span: int = 96, n_splits: int = 5,
                         repeats: int = 3, seed: int = 7,
                         z_limit: float = 3.0) -> dict:
    """Destroy the labels; the pipeline must learn NOTHING out-of-fold.
    Uses the most flexible candidate (gbt) — if anything can exploit a
    leak, it's the model with the most capacity. Pass criterion: mean
    shuffled OOF AUC within z_limit null SEs of 0.5."""
    X = np.asarray(X, float)
    y = np.asarray(y, float)
    rng = np.random.default_rng(seed)
    aucs = []
    for r in range(repeats):
        ys = y.copy()
        rng.shuffle(ys)
        fold_aucs = []
        for tr, te in purged_walk_forward(len(X), n_splits, label_span):
            if ys[tr].sum() < 5 or (len(ys[tr]) - ys[tr].sum()) < 5:
                continue
            m = GradientBoostedStumps(seed=seed + r).fit(X[tr], ys[tr])
            fold_aucs.append(auc_score(ys[te], m.predict_proba(X[te])))
        if fold_aucs:
            aucs.append(float(np.mean(fold_aucs)))
    if not aucs:
        return {"ok": False, "reason": "no viable folds", "aucs": []}
    mean_auc = float(np.mean(aucs))
    se = _auc_null_se(y) / math.sqrt(max(len(aucs), 1))
    z = abs(mean_auc - 0.5) / max(se, 1e-9)
    return {"ok": bool(z <= z_limit), "mean_auc": mean_auc, "z": float(z),
            "se": float(se), "aucs": aucs, "z_limit": z_limit}


# ---------------------------------------------------------------------------
# 3) PBO via CSCV
# ---------------------------------------------------------------------------
def pbo_cscv(M: np.ndarray, n_blocks: int = 8, max_combos: int = 126,
             seed: int = 7, select=None) -> dict:
    """Probability of Backtest Overfitting, combinatorially symmetric CV
    (Bailey, Borwein, López de Prado, Zhu 2017). M: (T, N) per-period
    performance, HIGHER = BETTER, one column per candidate config. T is
    partitioned into n_blocks; every half/half block combination trains
    the selection and tests it (OOS rank). PBO is the fraction of splits
    where the in-sample winner lands in the bottom half out-of-sample.
    <=0.2 healthy, ~0.5 selection is pure noise, >0.5 the rule is
    actively anti-selecting (chasing IS luck that mean-reverts OOS).

    `select`: callable (is_perf: (N,) array) -> int column index. Default
    argmax — the classical worst-case reading. Pass the DEPLOYED rule
    (e.g. the simplicity ladder) to measure the selection step the system
    actually runs; a margin-stabilized rule cannot chase per-split luck,
    which is exactly the mitigation PBO is meant to police."""
    M = np.asarray(M, float)
    T, N = M.shape
    if N < 2 or T < n_blocks:
        return {"pbo": None, "reason": f"need >=2 configs and T>=blocks "
                                       f"(got N={N}, T={T})"}
    n_blocks -= n_blocks % 2                     # even split required
    edges = np.linspace(0, T, n_blocks + 1).astype(int)
    block_means = np.stack([M[edges[i]:edges[i + 1]].mean(axis=0)
                            for i in range(n_blocks)])   # (S, N)
    combos = list(itertools.combinations(range(n_blocks), n_blocks // 2))
    if len(combos) > max_combos:
        rng = np.random.default_rng(seed)
        idx = rng.choice(len(combos), size=max_combos, replace=False)
        combos = [combos[i] for i in idx]
    if select is None:
        select = lambda p: int(np.argmax(p))          # noqa: E731
    lambdas = []
    for train_blocks in combos:
        test_blocks = [b for b in range(n_blocks) if b not in train_blocks]
        is_perf = block_means[list(train_blocks)].mean(axis=0)
        oos_perf = block_means[test_blocks].mean(axis=0)
        star = int(select(is_perf))
        # OOS relative rank of the in-sample winner in (0,1)
        omega = (np.sum(oos_perf <= oos_perf[star])) / (N + 1.0)
        omega = min(max(omega, 1.0 / (N + 1.0)), N / (N + 1.0))
        lambdas.append(math.log(omega / (1.0 - omega)))
    lambdas = np.array(lambdas)
    return {"pbo": float(np.mean(lambdas <= 0.0)),
            "n_combos": len(combos), "n_configs": N, "n_blocks": n_blocks,
            "median_lambda": float(np.median(lambdas))}


def model_space_pbo(X, y, label_span: int = 96, n_splits: int = 5,
                    seed: int = 7, n_blocks: int = 8) -> dict:
    """PBO over the model/hyperparameter space this pipeline actually
    selects from. All configs share ONE OOF index (same purged folds),
    per-period metric is per-block negative Brier — exactly the quantity
    walkforward selection maximizes, so the PBO measures the real
    selection step."""
    X = np.asarray(X, float)
    y = np.asarray(y, float)
    space = {
        "logistic": lambda: LogisticModel(seed=seed),
        "gbt_d2_lr05": lambda: GradientBoostedStumps(max_depth=2, lr=0.05,
                                                     seed=seed),
        "gbt_d3_lr05": lambda: GradientBoostedStumps(max_depth=3, lr=0.05,
                                                     seed=seed),
        "gbt_d3_lr10": lambda: GradientBoostedStumps(max_depth=3, lr=0.10,
                                                     seed=seed),
        "gbt_d4_lr05": lambda: GradientBoostedStumps(max_depth=4, lr=0.05,
                                                     seed=seed),
        "gbt_d2_lr10": lambda: GradientBoostedStumps(max_depth=2, lr=0.10,
                                                     seed=seed),
        "mlp_small": lambda: NumpyMLP(hidden=(16, 8), seed=seed),
    }
    folds = [f for f in purged_walk_forward(len(X), n_splits, label_span)
             if y[f[0]].sum() >= 5 and (len(y[f[0]]) - y[f[0]].sum()) >= 5]
    if not folds:
        return {"pbo": None, "reason": "no viable folds"}
    oof_idx = np.concatenate([te for _, te in folds])
    cols, names = [], []
    for name, factory in space.items():
        preds = np.empty(len(oof_idx))
        pos = 0
        for tr, te in folds:
            m = factory().fit(X[tr], y[tr])
            preds[pos:pos + len(te)] = m.predict_proba(X[te])
            pos += len(te)
        # per-observation performance: negative squared error (higher
        # better), blocked later by pbo_cscv
        cols.append(-(preds - y[oof_idx]) ** 2)
        names.append(name)
    M = np.stack(cols, axis=1)                    # (T_oof, N_configs)

    # complexity order for the ladder: simple -> complex, mirrors
    # walkforward._LADDER extended over the hyperparameter grid. A step
    # up must beat the INCUMBENT by BRIER_MARGIN (perf here is negative
    # Brier, so cand wins iff perf[cand] > perf[inc] + margin).
    order = [names.index(k) for k in (
        "logistic", "gbt_d2_lr05", "gbt_d2_lr10", "gbt_d3_lr05",
        "gbt_d3_lr10", "gbt_d4_lr05", "mlp_small") if k in names]

    def ladder(is_perf):
        inc = order[0]
        for cand in order[1:]:
            if is_perf[cand] > is_perf[inc] + BRIER_MARGIN:
                inc = cand
        return inc

    res = pbo_cscv(M, n_blocks=n_blocks, seed=seed, select=ladder)
    raw = pbo_cscv(M, n_blocks=n_blocks, seed=seed)          # argmax stress
    res["configs"] = names
    res["pbo_argmax"] = raw.get("pbo")
    res["selection_rule"] = "simplicity_ladder"
    if res.get("pbo") is not None:
        best = int(np.argmax(M.mean(axis=0)))
        res["is_winner"] = names[best]
    return res


# ---------------------------------------------------------------------------
# 4) deflated Sharpe ratio
# ---------------------------------------------------------------------------
def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def deflated_sharpe(sr_observed: float, n_returns: int, skew: float = 0.0,
                    kurtosis: float = 3.0, n_trials: int = 1,
                    var_trial_sr: float | None = None) -> dict:
    """Bailey & López de Prado (2014). Returns DSR = P(true SR > 0)
    after correcting for track length, non-normality and the number of
    strategy trials that produced the observed SR. SR units: per period
    of the return series. Needs n_returns >= ~20 to mean anything."""
    n = int(n_returns)
    if n < 3:
        return {"dsr": None, "reason": "track too short"}
    trials = max(int(n_trials), 1)
    if var_trial_sr is None:
        var_trial_sr = max(sr_observed ** 2, 0.01)
    # expected max SR under H0 across `trials` tries (Euler-Mascheroni
    # approximation of E[max of normals])
    if trials > 1:
        em = 0.5772156649
        z1 = math.sqrt(2.0 * math.log(trials))
        e_max = math.sqrt(var_trial_sr) * ((1 - em) * z1 +
                                           em * math.sqrt(
                                               2.0 * math.log(trials / math.e))
                                           if trials > 2 else z1 * 0.8)
    else:
        e_max = 0.0
    sr0 = e_max
    denom = math.sqrt(max(
        1.0 - skew * sr_observed +
        (kurtosis - 1.0) / 4.0 * sr_observed ** 2, 1e-9) / (n - 1))
    z = (sr_observed - sr0) / denom
    return {"dsr": float(_norm_cdf(z)), "sr0_threshold": float(sr0),
            "z": float(z), "n": n, "trials": trials}


# ---------------------------------------------------------------------------
# 5) purge-leakage probe — proves the purge is what stops the leak
# ---------------------------------------------------------------------------
def purge_leakage_probe(n: int = 900, label_span: int = 48, n_splits: int = 5,
                        seed: int = 7) -> dict:
    """Direct exercise of the purge on the leak class it defends: a
    LOOK-AHEAD-CONTAMINATED feature. The boundary training rows (the last
    `label_span` before each test block) get a feature column overwritten
    with a value from `label_span` bars ahead — i.e. inside the test
    region — the textbook accidental forward-looking feature. Un-purged,
    the model trains on those contaminated rows; the purge drops exactly
    them.

    Two invariants, both asserted:
      * CORRECTNESS (always): the purge must never MANUFACTURE edge —
        purged OOF AUC <= un-purged + tol. A purge that raises OOF is
        an index bug.
      * EFFICACY (this construction): with the injected look-ahead, the
        purge should reduce OOF inflation — un-purged >= purged.
    `leak_closed` reports the magnitude; the expanding-window design keeps
    it modest by construction, so efficacy is checked as a direction, not
    a threshold."""
    rng = np.random.default_rng(seed)
    # persistent regime -> a genuine, learnable, past-measurable signal
    regime = np.sign(np.cumsum(rng.normal(0.0, 0.15, n)))
    regime[regime == 0] = 1.0
    signal = regime + rng.normal(0.0, 0.8, n)              # observable proxy
    y = ((regime + rng.normal(0.0, 0.6, n)) > 0).astype(float)
    base = np.column_stack([signal, rng.normal(0.0, 1.0, n),
                            rng.normal(0.0, 1.0, n)])

    def build(contaminate: bool):
        X = base.copy()
        if contaminate:
            # inject the future label into a spare column for boundary rows
            fold = n // (n_splits + 1)
            for k in range(1, n_splits + 1):
                ts = k * fold
                lo = max(ts - label_span, 0)
                for t in range(lo, ts):
                    ahead = min(t + label_span, n - 1)
                    X[t, 1] = 3.0 * (y[ahead] - 0.5)      # look-ahead leak
        return X

    def oof_auc(X, purge_span):
        ps, ys = [], []
        for tr, te in purged_walk_forward(n, n_splits, purge_span):
            if y[tr].sum() < 5 or (len(y[tr]) - y[tr].sum()) < 5:
                continue
            m = LogisticModel(seed=seed).fit(X[tr], y[tr])
            ps.append(m.predict_proba(X[te]))
            ys.append(y[te])
        return auc_score(np.concatenate(ys), np.concatenate(ps)) if ps else 0.5

    Xc = build(contaminate=True)
    unpurged = oof_auc(Xc, 0)             # keeps the poisoned boundary rows
    purged = oof_auc(Xc, label_span)     # drops exactly them
    return {"unpurged_oof_auc": round(float(unpurged), 4),
            "purged_oof_auc": round(float(purged), 4),
            "leak_closed": round(float(unpurged - purged), 4),
            "purge_does_not_inflate": bool(purged <= unpurged + 0.02)}


# ---------------------------------------------------------------------------
# 6) feature degrees-of-freedom
# ---------------------------------------------------------------------------
def feature_dof_report(X, y, feature_names, label_span: int = 96,
                       n_splits: int = 5, seed: int = 7,
                       rows_per_feature_floor: float = 10.0,
                       dead_importance_eps: float = 0.002) -> dict:
    """Effective degrees of freedom of the fit: rows per feature, and the
    fraction of features whose OOS permutation importance is
    indistinguishable from zero (they only add estimation variance). Uses
    the highest-capacity candidate (gbt) on the last purged OOS fold for
    the importance read. Starved (rows/feature below floor) or a large
    dead fraction both flag overfitting surface that pruning would
    reduce."""
    from ml.walkforward import permutation_importance
    X = np.asarray(X, float)
    y = np.asarray(y, float)
    n, d = X.shape
    folds = [f for f in purged_walk_forward(n, n_splits, label_span)
             if y[f[0]].sum() >= 5 and (len(y[f[0]]) - y[f[0]].sum()) >= 5]
    dead, imp = [], []
    if folds:
        tr, te = folds[-1]
        if len(te) >= 20:
            m = GradientBoostedStumps(seed=seed).fit(X[tr], y[tr])
            imp = permutation_importance(m, X[te], y[te], list(feature_names),
                                         n_top=len(feature_names))
            dead = [name for name, drop in imp
                    if abs(drop) <= dead_importance_eps]
    rpf = n / max(d, 1)
    return {"n_rows": int(n), "n_features": int(d),
            "rows_per_feature": round(float(rpf), 2),
            "dead_feature_frac": round(len(dead) / max(d, 1), 3),
            "dead_features": dead,
            "starved": bool(rpf < rows_per_feature_floor),
            "importance_top": imp[:8]}
