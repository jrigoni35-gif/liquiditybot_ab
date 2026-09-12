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
                      returns P(true SR > SR0 | trials), where SR0 is
                      the EXPECTED MAXIMUM Sharpe under the null across
                      those trials — NOT zero. `psr_zero` in the same
                      result is the P(true SR > 0) reading.

Everything here is pure computation over arrays already produced by the
existing pipeline — no network, deterministic under seed, replay-safe.
"""

import csv
import itertools
import json
import logging
import math
from pathlib import Path

import numpy as np

from ml.calibration import brier_score
from ml.models import (AdaptiveGBT, GradientBoostedStumps, LogisticModel,
                       NumpyMLP, auc_score)
from ml.walkforward import (BAR_SECONDS, BRIER_MARGIN, admissible_families,
                            pbo_family, purged_walk_forward)

log = logging.getLogger("liquiditybot.ml.overfit")

# Model complexity order used by the PBO ladder — mirrors walkforward._LADDER
# over the hyperparameter grid. A step up must beat the INCUMBENT by
# BRIER_MARGIN. Experiment arms (schema_ab, epoch_ab) insert after their base.
_BASE_ORDER = ("logistic", "gbt_d2_lr05", "gbt_d2_lr10", "gbt_d3_lr05",
               "gbt_d3_lr10", "gbt_d4_lr05", "gbt_mono", "mlp_small",
               "adaptive_gbt")


# ---------------------------------------------------------------------------
# 1) train-vs-OOF gap
# ---------------------------------------------------------------------------
def train_test_gap(X, y, label_span: int = 96, n_splits: int = 5,
                   seed: int = 7, sample_weight=None, sig=None,
                   return_oof: bool = False, res=None) -> dict:
    """Per candidate: mean train AUC/Brier vs mean OOF AUC/Brier over the
    purged folds, plus the gaps. Interpretation guide (empirical, this
    data scale): gap_auc < 0.05 healthy, 0.05-0.12 watch, > 0.12 the
    model is memorizing.

    return_oof: also capture the per-fold (test-index, predicted-prob)
    pairs per candidate, concatenated across folds in test order, under
    'oof_idx'/'oof_pred' - the SAME fitted models this function already
    trains for the gap check, no additional fit. Consumed by
    scripts/overfit_check.py's regime-stratified diagnostic (report-only)
    so it never retrains separately from OF-1. Default False keeps every
    existing caller's return dict byte-identical (no new keys added).

    `res` (per-row label RESOLUTION time, default None = unchanged): the
    DEPLOYED selector passes it (main.py:5734 -> evaluate_and_select(res=
    res)), and purged_walk_forward then purges on "did this label actually
    resolve before the test block opens" instead of the fixed
    signal+label_span horizon - which it IGNORES entirely in that branch.
    That is why OF-1's `label_span` literal drifting from ml.label_max_bars
    is NOT the defect it looks like and wiring the config knob in here
    would be WRONG: measured deployed fold train sizes [303,579,925,1259,
    1608] vs span-96 [207,532,914,1248,1613] vs span-24 [308,652,1009,1376,
    1743] - the config value UNDER-purges every fold. Threading `res` is
    what actually makes this instrument measure the deployed process."""
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
        oof_idx_parts, oof_pred_parts = [], []
        for tr, te in purged_walk_forward(len(X), n_splits, label_span,
                                          sig=sig, res=res):
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
            if return_oof:
                oof_idx_parts.append(np.asarray(te))
                oof_pred_parts.append(np.asarray(p_te))
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
        if return_oof:
            out[name]["oof_idx"] = np.concatenate(oof_idx_parts)
            out[name]["oof_pred"] = np.concatenate(oof_pred_parts)
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
                         z_limit: float = 3.0, sig=None) -> dict:
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
        for tr, te in purged_walk_forward(len(X), n_splits, label_span,
                                          sig=sig):
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
             seed: int = 7, select=None, sig=None,
             label_span: float = 0.0) -> dict:
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
    which is exactly the mitigation PBO is meant to police.

    `sig`/`label_span` (Debate-1 item E, 2026-07-30): contiguous CSCV
    blocks share label windows at their edges — at mean uniqueness ~0.16
    a row straddling an IS/OOS boundary carries the SAME return path on
    both sides, so the IS winner's OOS rank reads correlated-lucky and
    PBO reads optimistic (anti-conservative on our own gate; AFML ch.12
    purges between CPCV groups for exactly this reason). With `sig` (row
    timestamps, same order as M) and `label_span` (seconds a label may
    remain open), each combo PURGES from its TRAIN blocks every row
    whose label window [s, s+span] intersects a TEST block's effective
    span [start, end+span] — two-sided, per combo. OOS block means are
    untouched (the BBLZ convention purges train). Omitting sig or a zero
    span is byte-identical legacy behavior."""
    M = np.asarray(M, float)
    T, N = M.shape
    if N < 2 or T < n_blocks:
        return {"pbo": None, "reason": f"need >=2 configs and T>=blocks "
                                       f"(got N={N}, T={T})"}
    n_blocks -= n_blocks % 2                     # even split required
    edges = np.linspace(0, T, n_blocks + 1).astype(int)
    block_rows = [np.arange(edges[i], edges[i + 1])
                  for i in range(n_blocks)]
    block_means = np.stack([M[r].mean(axis=0) for r in block_rows])  # (S, N)
    purge = sig is not None and float(label_span) > 0.0
    sig_arr = np.empty(0)
    span = 0.0
    blo = bhi = np.empty(0)
    if purge:
        sig_arr = np.asarray(sig, float)
        if len(sig_arr) != T:
            return {"pbo": None, "reason": f"sig length {len(sig_arr)} != "
                                           f"T {T}"}
        span = float(label_span)
        blo = np.array([float(sig_arr[r[0]]) for r in block_rows])
        bhi = np.array([float(sig_arr[r[-1]]) for r in block_rows])
    combos = list(itertools.combinations(range(n_blocks), n_blocks // 2))
    if len(combos) > max_combos:
        rng = np.random.default_rng(seed)
        idx = rng.choice(len(combos), size=max_combos, replace=False)
        combos = [combos[i] for i in idx]
    if select is None:
        select = lambda p: int(np.argmax(p))          # noqa: E731
    lambdas = []
    purged_frac_sum = 0.0
    combos_dropped = 0
    for train_blocks in combos:
        test_blocks = [b for b in range(n_blocks) if b not in train_blocks]
        if purge:
            # equal-block-weight IS mean over PURGED per-block means (the
            # same weighting structure as the unpurged path); a fully
            # purged train block drops out of the average.
            per_block, kept, dropped = [], 0, 0
            for b in train_blocks:
                rows = block_rows[b]
                s = sig_arr[rows]
                keep = np.ones(len(rows), bool)
                for tb in test_blocks:
                    keep &= ~((s <= bhi[tb] + span)
                              & (s + span >= blo[tb]))
                dropped += int((~keep).sum())
                kept += int(keep.sum())
                if keep.any():
                    per_block.append(M[rows[keep]].mean(axis=0))
            if not per_block:
                # degenerate combo (label_span spans its whole train side):
                # DROP this combo, never the whole measurement - review
                # policy 2026-07-31: OF-3 must not silently downgrade from
                # a measured gate to a skipped one because one split is
                # unusable. combos_dropped_purged reports the loss.
                combos_dropped += 1
                continue
            is_perf = np.mean(per_block, axis=0)
            purged_frac_sum += dropped / max(kept + dropped, 1)
        else:
            is_perf = block_means[list(train_blocks)].mean(axis=0)
        oos_perf = block_means[test_blocks].mean(axis=0)
        star = int(select(is_perf))
        # OOS relative rank of the in-sample winner in (0,1)
        omega = (np.sum(oos_perf <= oos_perf[star])) / (N + 1.0)
        omega = min(max(omega, 1.0 / (N + 1.0)), N / (N + 1.0))
        lambdas.append(math.log(omega / (1.0 - omega)))
    if not lambdas:
        return {"pbo": None,
                "reason": "edge purge left no usable combos "
                          "(label_span spans whole blocks everywhere)",
                "combos_dropped_purged": combos_dropped}
    lambdas = np.array(lambdas)
    n_used = len(lambdas)
    out = {"pbo": float(np.mean(lambdas <= 0.0)),
           "n_combos": n_used, "n_configs": N, "n_blocks": n_blocks,
           "median_lambda": float(np.median(lambdas))}
    if purge:
        out["edge_purged_frac"] = round(purged_frac_sum / n_used, 4)
        out["combos_dropped_purged"] = combos_dropped
    return out


# ---------------------------------------------------------------------------
# T3.2/T3.6a — opt-in variant axes (schema/row) inside model_space_pbo
# ---------------------------------------------------------------------------
# Both experiment arms pair with this SAME base family: identical model
# class/hyperparameters/seed as the plain "gbt_d3_lr05" rung already in the
# default space, so the ONLY thing that differs between an arm and its base
# is the training INPUT (schema-pruned columns, or epoch-masked rows) — any
# measured delta is attributable to the data change alone, never a
# confounded architecture change too. Report-only, never gating (CLAUDE.md
# "PBO measures the DEPLOYED rule, never argmax" + "no default-behavior
# flips": these arms exist only when the caller opts in via
# schema_ab_cols/epoch_ab_mask).
_SCHEMA_AB_BASE_FAMILY = "gbt_d3_lr05"
_EPOCH_AB_BASE_FAMILY = "gbt_d3_lr05"

# Per-fold floor for a row-masked arm's TRAINING subset (tr ∩ mask).
# _ARM_MIN_CLASS=5 IS the same per-fold class-balance floor purged_walk_
# forward's callers apply everywhere else in this file (train_test_gap,
# shuffled_label_check, model_space_pbo's own `folds` filter above at
# lines 581/803) — not a new invented number. _ARM_MIN_TRAIN_ROWS=30 is a
# DIFFERENT quantity with a different referent: it matches REGIME_MIN_N
# (below) — OF-5's "how many labeled outcomes before a point statistic
# means anything" evidence floor — reused here as the same bare row-count
# question applied to a row-masked arm's training subset, not the
# per-fold class-balance check.
_ARM_MIN_TRAIN_ROWS = 30
_ARM_MIN_CLASS = 5


def load_schema_ab_cols(prunefile_path: "str | Path", feature_names) -> np.ndarray:
    """Resolves scripts/feature_stability.py's (T3.1) dated snapshot into
    the column-index array model_space_pbo's --schema-ab experiment arm
    trains on: every FEATURE_NAMES column NOT in the snapshot's
    `always_dead` list. `always_dead` is the ONLY binding key this reads —
    `candidate_prune_list`/`ever_dead`/`flip_features`/`combos`/
    `stability_ratio` are Task 1's own diagnostics, not this contract.

    The five regime one-hots (ml.features.REGIME_ONE_HOT_FEATURES) are
    re-subtracted here defensively even though Task 1's snapshot already
    excludes them from always_dead (module docstring there: "dead by
    coverage, not uselessness") — belt-and-suspenders, never rely on a
    dated file from an older build having honored the exemption.

    Fails loudly (ValueError, so a bad --schema-ab path crashes the audit
    script immediately rather than silently running on a wrong prune set)
    when the file has no `always_dead` key at all, or when always_dead
    names a feature absent from `feature_names` (a stale snapshot from a
    different FEATURE_SCHEMA_VERSION)."""
    from ml.features import REGIME_ONE_HOT_FEATURES
    feature_names = list(feature_names)
    prunefile_path = Path(prunefile_path)
    with prunefile_path.open(encoding="utf-8") as fh:
        snap = json.load(fh)
    if "always_dead" not in snap:
        raise ValueError(
            f"{prunefile_path}: missing required 'always_dead' key - not a "
            f"valid Task 1 feature-stability snapshot (scripts/"
            f"feature_stability.py)")
    dead = set(snap["always_dead"])
    unknown = dead - set(feature_names)
    if unknown:
        raise ValueError(
            f"{prunefile_path}: always_dead names feature(s) not in "
            f"FEATURE_NAMES: {sorted(unknown)} - stale snapshot (schema "
            f"version mismatch?)")
    dead -= set(REGIME_ONE_HOT_FEATURES)   # defensive re-exemption
    keep = [i for i, name in enumerate(feature_names) if name not in dead]
    return np.asarray(keep, dtype=int)


def build_epoch_ab_mask(history_path: "str | Path", sig, res,
                        cutoff_ts: float) -> np.ndarray:
    """Row mask for model_space_pbo's --epoch-ab experiment arm: True =
    include in the arm's TRAINING subset. Keeps every LIVE-source row plus
    every CANDIDATE-source row whose label resolved (res — the loader's
    per-row `ts`) at/after cutoff_ts; drops only candidate rows resolved
    strictly before it (config ml.epoch.candidate_cutoff_ts — the
    config-derivation-boundary marker, guarded in core/config_guard.py).

    `sig`/`res` must be the exact arrays HistoryStore.load_training_data(
    return_label_times=True) returned for `history_path` (sig-sorted,
    survivor order) — this function does NOT call into or modify that
    loader (no production-path row exclusion anywhere; the mask lives only
    in this experiment). Instead it takes its OWN pass over the raw CSV,
    mirroring scripts/learning_curve.py's `_scan_live_upto` idiom: the
    loader deliberately drops the raw 'source'/'book' bookkeeping columns
    from its X/y/w/sig/res return, so recovering 'source' needs a fresh
    read. The two passes are joined on (signal_ts, ts) — the same
    ordering key load_training_data itself sorts and purges by (ml/
    history.py: sig/res, argsort(sig)) — because `sig`/`res` are the ONLY
    two values load_training_data hands back per row; there is no richer
    per-row identity to join on from the OUTPUT side no matter how the
    RAW-CSV side keys itself.

    T3.2 review CRITICAL fix: (signal_ts, ts) alone is NOT guaranteed
    unique — candidates from several assets are routinely written in the
    same poll() batch (shared append-time `ts`, and 5m candles land on a
    shared wall-clock grid, so `signal_ts`/bar_time collides too), and the
    production corpus measurably collides on this key ~15% of the time.
    A naive last-write-wins dict (the pre-fix behavior) could therefore
    resolve a LIVE row's key to a `"candidate"` row's source and wrongly
    drop it from the arm's training set — never acceptable (a live label
    must NEVER be excluded, in any era, for any reason). The fix: track
    every DISTINCT source seen at each (signal_ts, ts) key (using
    `position_id` — HistoryStore's own per-row primary key, unique for
    every row it ever appends, live trade id or CandidateLabeler's salted
    `cand-{salt}-{seq}` id alike — to tell genuinely distinct rows apart
    at a shared key; `candidate_id` is a LIVE row's back-reference to its
    origin candidate, never a row's own identity, so it is not used for
    this). A key is resolved to a single source ONLY when every row
    mapped to it agrees; a key where sources DISAGREE (a live row and a
    candidate row truly sharing (signal_ts, ts)) is AMBIGUOUS and is
    never resolved to "candidate" — it fails OPEN (kept), exactly like a
    lookup miss. This makes misclassifying a live row as a candidate
    structurally impossible: the only way a row gets dropped is an
    UNAMBIGUOUS "candidate" verdict. A blank/missing `position_id` (older
    rows, or a minimal fixture) still counts as its own anonymous row for
    collision detection — it just can't be named in the warning.
    A colliding key (regardless of whether it resolves) is logged once as
    an aggregate warning rather than silently overwritten. Any row this
    scan cannot match at all (lookup miss), or an unreadable/missing
    history file, still fails OPEN — included, never silently dropped —
    since this is a report-only diagnostic, not a correctness-critical
    production filter."""
    sig = np.asarray(sig, float)
    res = np.asarray(res, float)
    # key -> {"sources": set of distinct source values seen,
    #         "ids": set of distinct non-blank position_ids seen,
    #         "n_blank": count of rows at this key with no position_id}
    seen: dict = {}
    try:
        with Path(history_path).open(encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if (row.get("book") or "5m") == "long":
                    continue
                try:
                    s = float(row.get("signal_ts") or row.get("ts") or "nan")
                    t = float(row.get("ts") or "nan")
                except ValueError:
                    continue
                if not (np.isfinite(s) and np.isfinite(t)):
                    continue
                key = (round(s, 6), round(t, 6))
                entry = seen.setdefault(
                    key, {"sources": set(), "ids": set(), "n_blank": 0})
                entry["sources"].add(row.get("source") or "")
                rid = (row.get("position_id") or "").strip()
                if rid:
                    entry["ids"].add(rid)
                else:
                    entry["n_blank"] += 1
    except (OSError, csv.Error):
        return np.ones(len(sig), dtype=bool)

    n_ambiguous = 0
    n_collided = 0
    for entry in seen.values():
        n_distinct_rows = len(entry["ids"]) + entry["n_blank"]
        if n_distinct_rows > 1:
            n_collided += 1
            if len(entry["sources"]) > 1:
                n_ambiguous += 1
    if n_collided:
        log.warning(
            "epoch-ab mask: %d/%d (signal_ts, ts) key(s) in %s were shared "
            "by more than one row (candidates from several assets commonly "
            "share a poll-cycle append time) - %d of them mixed live and "
            "candidate sources and were left UNRESOLVED (kept, never "
            "dropped, since a live row must never be excluded); the rest "
            "agreed on source and were resolved normally",
            n_collided, len(seen), history_path, n_ambiguous)

    mask = np.ones(len(sig), dtype=bool)
    for i in range(len(sig)):
        key = (round(float(sig[i]), 6), round(float(res[i]), 6))
        entry = seen.get(key)
        if entry is None:
            continue                       # lookup miss -> fail open, keep
        sources = entry["sources"]
        if len(sources) != 1:
            continue                       # ambiguous/ unknown -> keep
        source = next(iter(sources))
        if source == "candidate" and res[i] < cutoff_ts:
            mask[i] = False
    return mask


def _fit_predict_arm(name: str, factory, X_arm: np.ndarray, y: np.ndarray,
                     folds: list, oof_idx: np.ndarray,
                     row_mask: "np.ndarray | None" = None,
                     sample_weight: "np.ndarray | None" = None) -> tuple:
    """model_space_pbo's per-arm fit/predict step, factored out so every
    arm — baseline (row_mask=None) and the opt-in schema-ab/epoch-ab
    variants alike — shares ONE code path. With row_mask=None this is
    byte-for-byte the pre-T3.2 inline loop (tr/te unmodified, X_arm is the
    caller's X unsliced) — the byte-identity pin depends on that.

    row_mask (bool, aligned to X_arm's ORIGINAL row order, i.e. BEFORE OOF
    concatenation) restricts TRAINING ONLY: a row-masked arm trains on
    `tr ∩ mask` but ALWAYS predicts/scores the FULL, unmasked `te` for
    every fold — the binding "evaluation rows identical across arms"
    invariant (test rows are never masked; only training data varies).

    If `tr ∩ mask` is too thin to fit at all (fewer than
    _ARM_MIN_TRAIN_ROWS rows, or fewer than _ARM_MIN_CLASS rows of either
    label class) this fold degrades GRACEFULLY: it falls back to the full
    unmasked `tr` for that fold only, rather than crashing the whole OF-3
    run, and a human-readable reason is appended to the returned notes.

    sample_weight (default None = the historical UNIFORM fit): the de
    Prado weights the deployed selector fits every rung with
    (ml/walkforward.py:302-303). None keeps the byte-identity pin.

    Returns (preds, degraded_notes): preds is (len(oof_idx),) float in the
    same fold-concatenation order oof_idx was built in."""
    w = None if sample_weight is None else np.asarray(sample_weight, float)
    preds = np.empty(len(oof_idx))
    notes: list = []
    pos = 0
    for fi, (tr, te) in enumerate(folds):
        tr_use = tr
        if row_mask is not None:
            tr_masked = tr[row_mask[tr]]
            n_pos = float(y[tr_masked].sum()) if len(tr_masked) else 0.0
            n_neg = len(tr_masked) - n_pos
            if (len(tr_masked) >= _ARM_MIN_TRAIN_ROWS
                    and n_pos >= _ARM_MIN_CLASS and n_neg >= _ARM_MIN_CLASS):
                tr_use = tr_masked
            else:
                notes.append(
                    f"{name}: fold {fi} row-masked training set too thin "
                    f"(n={len(tr_masked)}, pos={n_pos:.0f}, neg={n_neg:.0f}) "
                    f"- degraded to the full unmasked training window for "
                    f"this fold only")
        m = factory().fit(X_arm[tr_use], y[tr_use],
                          sample_weight=None if w is None else w[tr_use])
        preds[pos:pos + len(te)] = m.predict_proba(X_arm[te])
        pos += len(te)
    return preds, notes


def model_space_pbo(X, y, label_span: int = 96, n_splits: int = 5,
                    seed: int = 7, n_blocks: int = 8, sig=None,
                    include_adaptive: bool = False,
                    adaptive_cfg: dict | None = None,
                    n_live: int | None = None,
                    select_cfg: dict | None = None,
                    schema_ab_cols: "np.ndarray | None" = None,
                    epoch_ab_mask: "np.ndarray | None" = None,
                    include_gbt_mono: bool = False,
                    gbt_mono_cfg: dict | None = None,
                    sample_weight=None, res=None) -> dict:
    """PBO over the model/hyperparameter space this pipeline actually
    selects from. All configs share ONE OOF index (same purged folds),
    per-period metric is per-block negative Brier — exactly the quantity
    walkforward selection maximizes, so the PBO measures the real
    selection step.

    include_adaptive mirrors ml.adaptive_gbt.enabled: when the opt-in
    rung is live in the deployed ladder it MUST be in the measured space
    too, or OF-3 certifies a selection rule the bot no longer runs (the
    'PBO measures the DEPLOYED rule' invariant). It is appended LAST —
    the most complex step — so the simplicity ladder only elects it when
    it out-earns every simpler config by the Brier margin.

    include_gbt_mono/gbt_mono_cfg (T3.4) mirror include_adaptive/
    adaptive_cfg for the monotone-constrained GBT rung: gbt_mono_cfg
    carries {"constraints": {feature_index: sign}} already resolved from
    config names by the caller. Both default False/None, so this rung is
    absent from the measured space unless a caller explicitly opts in -
    same "PBO measures the DEPLOYED rule" invariant as adaptive_gbt.
    Placed directly after the gbt_* hyperparameter block in `order` (its
    own complexity tier, not "most complex" by default placement), NOT
    appended last like adaptive_gbt.

    n_live / select_cfg apply the SAME evidence gate as evaluate_and_select:
    a family the label evidence can't support is not in the deployed ladder,
    so it must not be in the measured space either. When the gate collapses
    the space to a single family (e.g. logistic-only at low live-row counts),
    there is NO selection happening — PBO is returned None with an explicit
    'no selection' reason rather than a fabricated number.

    schema_ab_cols / epoch_ab_mask (T3.2/T3.6a, both default None): OPT-IN
    experiment arms, report-only. Both default None -> the space/order/M
    and every returned value are BYTE-IDENTICAL to the pre-T3.2 function
    (regression-pinned in tests/test_pbo_variants.py) — no new dict key is
    ever added when neither is given.

    schema_ab_cols: column indices to KEEP (already resolved against
    FEATURE_NAMES by the caller, e.g. via load_schema_ab_cols) — adds a
    "<base>_schema_ab" arm that trains _SCHEMA_AB_BASE_FAMILY's exact
    model/hyperparameters on X[:, schema_ab_cols] instead of the full
    corpus.
    epoch_ab_mask: boolean row mask (aligned to X, len(X)) — adds a
    "<base>_epoch_ab" arm that trains _EPOCH_AB_BASE_FAMILY's exact
    model/hyperparameters on tr ∩ mask per fold (see build_epoch_ab_mask).

    Each active arm is inserted into `order` directly after its base
    family (the ladder treats it as that family's next-complex step) and
    participates in the SAME ladder-selected PBO/argmax-stress run as
    every other config — still the deployed selection RULE, never argmax,
    just measured over a caller-widened space. A per-arm pairwise report
    (vs its base, using the SAME BRIER_MARGIN ladder-climb logic) lands in
    the returned 'experiments' dict, added ONLY when at least one arm was
    actually requested.

    Passing BOTH schema_ab_cols and epoch_ab_mask in the same call chains
    the arms in insertion order: <base> -> <base>_schema_ab ->
    <base>_epoch_ab -> <next base rung> (today: gbt_d3_lr05 ->
    gbt_d3_lr05_schema_ab -> gbt_d3_lr05_epoch_ab -> gbt_d3_lr10). The
    epoch arm's ladder-climb INCUMBENT is therefore whatever sits directly
    before it in `order`, which is the schema arm, not the plain base, once
    both are active. Each arm's own 'experiments' entry is still computed
    against ITS OWN base family via the same pairwise BRIER_MARGIN logic
    regardless (unaffected by what else is in the space), so no per-arm
    pairwise number is contaminated — but the WIDENED-SPACE pbo/
    argmax-stress read this function returns is only interpretable ONE ARM
    AT A TIME: measure schema_ab_cols and epoch_ab_mask in separate calls
    (as this phase's adjudication did) if you need to attribute the
    widened-space aggregate to a single experiment.

    sample_weight (2026-08-01 audit, default None = the historical uniform
    fit): the de Prado weights the DEPLOYED selector fits every rung with
    (ml/walkforward.py:302-303, main.py:5728). Fitting the measured space
    uniformly while the shipped space is weighted breaks the one invariant
    this instrument exists to hold - "PBO measures the DEPLOYED rule".
    Measured on the live corpus (weights span 43x, Kish ESS 1013/2141):
    per-family Brier shifts of 0.0012-0.0121 against a BRIER_MARGIN of
    0.002, i.e. the climb decision rides on a threshold 6x smaller than
    the perturbation the missing weights introduce; with the evidence gate
    lifted the ladder winner itself moved (gbt_d3_lr10 -> gbt_d4_lr05) and
    PBO 0.743 -> 0.557 against a gate that fires at 0.5. WEIGHT THE FIT,
    NOT THE METRIC: deployed selection ranks on UNWEIGHTED Brier, so M
    below stays unweighted - weighting the score would introduce a second,
    opposite divergence. Per docs/quant/pbo_admission_policy.md rule 2
    this is a CONSCIOUS CSCV re-baseline on real corpora; the synthetic
    byte-identity pin (tests/test_pbo_variants.py::_PINNED) passes no
    weights and is therefore unmoved.

    res (per-row label RESOLUTION time, default None = unchanged): same
    deployed-parity argument as train_test_gap's - see that docstring for
    why threading `res` (and NOT ml.label_max_bars) is the correct fix for
    the label_span literal drift."""
    X = np.asarray(X, float)
    y = np.asarray(y, float)
    ac = adaptive_cfg or {}
    gm = gbt_mono_cfg or {}
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
    }
    if include_gbt_mono:
        # inserted BEFORE mlp_small (dict insertion order == the reported
        # 'configs' listing order) so it reads as the gbt_* block's own
        # next-complex step, not a bolt-on after every hyperparameter
        # variant - matching its `order`/_BASE_ORDER placement below.
        space["gbt_mono"] = lambda: GradientBoostedStumps(
            seed=seed, monotone_constraints=gm.get("constraints") or None)
    space["mlp_small"] = lambda: NumpyMLP(hidden=(16, 8), seed=seed)
    if include_adaptive:
        space["adaptive_gbt"] = lambda: AdaptiveGBT(
            k=int(ac.get("bags", 4)),
            warm_rounds=int(ac.get("warm_rounds", 25)),
            max_total_trees=int(ac.get("max_total_trees", 800)),
            seed=seed)
    # evidence gate mirror: drop hyperparameter variants whose family the
    # ladder would not admit at this live-row count. logistic always survives.
    _nl = len(X) if n_live is None else int(n_live)
    admitted = admissible_families(_nl, len(X), select_cfg)
    space = {k: v for k, v in space.items() if pbo_family(k) in admitted}
    if len(space) < 2:
        out = {"pbo": None, "n_configs": len(space),
               "configs": list(space),
               "reason": "evidence-gated to a single family (no model "
                         "selection to overfit at this live-row count)"}
        if schema_ab_cols is not None or epoch_ab_mask is not None:
            out["experiment_notes"] = [
                "experiment arm(s) skipped: evidence-gated to a single "
                "family - no selection to A/B at this live-row count"]
        return out

    # ---- T3.2/T3.6a: opt-in experiment arms (never touched when both
    # schema_ab_cols and epoch_ab_mask are None — the byte-identity pin) --
    arm_space: dict[str, tuple] = {
        name: (factory, None, None) for name, factory in space.items()}
    space = arm_space
    experiment_bases: dict = {}          # arm name -> base family name
    experiment_notes: list = []
    if schema_ab_cols is not None:
        if _SCHEMA_AB_BASE_FAMILY in space:
            arm = f"{_SCHEMA_AB_BASE_FAMILY}_schema_ab"
            base_factory = space[_SCHEMA_AB_BASE_FAMILY][0]
            space[arm] = (base_factory, np.asarray(schema_ab_cols, int), None)
            experiment_bases[arm] = _SCHEMA_AB_BASE_FAMILY
        else:
            experiment_notes.append(
                f"schema-ab arm skipped: base family "
                f"'{_SCHEMA_AB_BASE_FAMILY}' evidence-gated out at this "
                f"live-row count")
    if epoch_ab_mask is not None:
        if _EPOCH_AB_BASE_FAMILY in space:
            arm = f"{_EPOCH_AB_BASE_FAMILY}_epoch_ab"
            base_factory = space[_EPOCH_AB_BASE_FAMILY][0]
            space[arm] = (base_factory, None, np.asarray(epoch_ab_mask, bool))
            experiment_bases[arm] = _EPOCH_AB_BASE_FAMILY
        else:
            experiment_notes.append(
                f"epoch-ab arm skipped: base family "
                f"'{_EPOCH_AB_BASE_FAMILY}' evidence-gated out at this "
                f"live-row count")

    folds = [f for f in purged_walk_forward(len(X), n_splits, label_span,
                                            sig=sig, res=res)
             if y[f[0]].sum() >= 5 and (len(y[f[0]]) - y[f[0]].sum()) >= 5]
    if not folds:
        return {"pbo": None, "reason": "no viable folds"}
    oof_idx = np.concatenate([te for _, te in folds])
    y_oof = y[oof_idx]
    cols, names = [], []
    degraded_notes: list = []
    for name, (factory, arm_cols, row_mask) in space.items():
        X_arm = X if arm_cols is None else X[:, arm_cols]
        # per-observation performance: negative squared error (higher better),
        # blocked later by pbo_cscv. RAW (uncalibrated) on purpose: isotonic
        # calibration is a MONOTONE, same-for-all-configs post-transform - it
        # changes neither which configs exist nor the ladder's margin
        # structure, which is what PBO measures. Fitting it on the full OOF
        # here would instead LEAK across the CSCV train/test block split (a
        # config's test-block score set by a calibrator that saw that block),
        # deflating OOS variance and corrupting the PBO. Selection still runs
        # on calibrated Brier (evaluate_and_select); the luck-chasing this
        # instrument polices lives in the family/margin structure, unchanged.
        preds, notes = _fit_predict_arm(name, factory, X_arm, y, folds,
                                        oof_idx, row_mask=row_mask,
                                        sample_weight=sample_weight)
        degraded_notes.extend(notes)
        cols.append(-(preds - y_oof) ** 2)
        names.append(name)
    M = np.stack(cols, axis=1)                    # (T_oof, N_configs)

    # complexity order for the ladder: simple -> complex, mirrors
    # walkforward._LADDER extended over the hyperparameter grid. A step
    # up must beat the INCUMBENT by BRIER_MARGIN (perf here is negative
    # Brier, so cand wins iff perf[cand] > perf[inc] + margin). Any active
    # experiment arm is inserted directly after its base family (T3.2/
    # T3.6a: "the ladder treats it as the next-complex step") — a no-op
    # when experiment_bases is empty, which is exactly the byte-identity
    # baseline.
    order = []
    for k in _BASE_ORDER:
        if k in names:
            order.append(names.index(k))
        for arm_name, base_name in experiment_bases.items():
            if base_name == k and arm_name in names:
                order.append(names.index(arm_name))

    def ladder(is_perf):
        inc = order[0]
        for cand in order[1:]:
            if is_perf[cand] > is_perf[inc] + BRIER_MARGIN:
                inc = cand
        return inc

    # Debate-1 item E: OOF rows keep their signal timestamps so pbo_cscv
    # can purge label-window overlap at its block edges (sig=None keeps
    # the legacy unpurged behavior for callers without timestamps).
    # UNIT SEAM (2026-07-31 review Critical #1): label_span HERE is in
    # BARS (purged_walk_forward multiplies by BAR_SECONDS itself);
    # pbo_cscv's purge compares against epoch-second sig - convert ONCE
    # at this seam. Passing bars raw shipped a 96-second window (~300x
    # too narrow, purge silently inert).
    sig_oof = np.asarray(sig, float)[oof_idx] if sig is not None else None
    span_sec = float(label_span) * BAR_SECONDS
    # NAMED `out` (was `res`): `res` is now this function's per-row
    # label-resolution-time PARAMETER, threaded to purged_walk_forward
    # above. Shadowing it here would work by accident of ordering only.
    out = pbo_cscv(M, n_blocks=n_blocks, seed=seed, select=ladder,
                   sig=sig_oof, label_span=span_sec)
    raw = pbo_cscv(M, n_blocks=n_blocks, seed=seed,          # argmax stress
                   sig=sig_oof, label_span=span_sec)
    out["configs"] = names
    out["pbo_argmax"] = raw.get("pbo")
    out["selection_rule"] = "simplicity_ladder"
    if out.get("pbo") is not None:
        best = int(np.argmax(M.mean(axis=0)))
        out["is_winner"] = names[best]

    # ---- T3.2/T3.6a: per-arm pairwise report (INFO-only material for the
    # caller; never gates) — added ONLY when at least one arm was actually
    # requested, preserving the no-flags byte-identity pin.
    if experiment_bases:
        full_perf = M.mean(axis=0)
        experiments: dict = {}
        for arm_name, base_name in experiment_bases.items():
            if arm_name not in names or base_name not in names:
                continue        # noted in experiment_notes above already
            bi, ai = names.index(base_name), names.index(arm_name)
            # pair_M below is sliced to exactly [base, arm] -> pbo_cscv's
            # `select` sees a length-2 is_perf in that SAME order, so
            # column 0 is always the base and column 1 always the arm -
            # no bi/ai remapping needed inside the closure.
            def _pair_ladder(is_perf):
                return 1 if is_perf[1] > is_perf[0] + BRIER_MARGIN else 0

            pair_M = M[:, [bi, ai]]
            pair_pbo = pbo_cscv(pair_M, n_blocks=n_blocks, seed=seed,
                               select=_pair_ladder,
                               sig=sig_oof, label_span=span_sec)
            ladder_winner = (arm_name if full_perf[ai] >
                            full_perf[bi] + BRIER_MARGIN else base_name)
            mean_winner = arm_name if full_perf[ai] > full_perf[bi] \
                else base_name
            experiments[arm_name] = {
                "base": base_name,
                "pbo": pair_pbo.get("pbo"),
                "ladder_winner": ladder_winner,
                "mean_winner": mean_winner,
            }
        if experiments:
            out["experiments"] = experiments
    if experiment_notes:
        out["experiment_notes"] = experiment_notes
    if degraded_notes:
        out["degraded_folds"] = degraded_notes
    return out


# ---------------------------------------------------------------------------
# 4) deflated Sharpe ratio
# ---------------------------------------------------------------------------
def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _norm_ppf(p: float) -> float:
    """Exact inverse of _norm_cdf via bisection (stdlib-only, keeping the
    module's no-scipy stance). 60 halvings of [-10, 10] give ~2e-17
    interval width — far past float precision for every p we use."""
    p = min(max(p, 1e-15), 1.0 - 1e-15)
    lo, hi = -10.0, 10.0
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        if _norm_cdf(mid) < p:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def deflated_sharpe(sr_observed: float, n_returns: int, skew: float = 0.0,
                    kurtosis: float = 3.0, n_trials: int = 1,
                    var_trial_sr: float | None = None) -> dict:
    """Bailey & López de Prado (2014). Returns DSR = P(true SR > SR0)
    after correcting for track length, non-normality and the number of
    strategy trials that produced the observed SR. SR units: per period
    of the return series. Needs n_returns >= ~20 to mean anything.

    SR0 IS NOT ZERO, AND THIS DOCSTRING SAID IT WAS until 2026-09-11.
    The returned probability is measured against `sr0_threshold` = the
    EXPECTED MAXIMUM Sharpe under the null across `n_trials` tries, which
    is strictly positive for trials > 1 (0.2532 at n=30, N=7). The two
    coincide only at n_trials == 1, where e_max is set to 0.0 below.

    The mislabel is not cosmetic: it inverts how the number reads. A
    reader seeing "dsr=0.006" under the old label concluded "0.6% chance
    the edge is positive". The true statement was "0.6% chance the true
    per-trip Sharpe exceeds +0.2532" — a far weaker claim, and not the
    one an operator would act on. The quantity the old label described is
    now returned alongside as `psr_zero` (Bailey & LdP's PSR at SR*=0),
    and OF-5 prints it next to the graded number — read it there, per
    run. NO SAMPLE FIGURE IS WRITTEN HERE ON PURPOSE: this docstring is
    the wrong place for a number that moves with the corpus, which is the
    decay `scripts/audit_quarantine.py` had to delete a table over.
    Found by a literature pass that read the code before the papers;
    the-method #1, the instrument was the first suspect."""
    n = int(n_returns)
    if n < 3:
        return {"dsr": None, "reason": "track too short"}
    trials = max(int(n_trials), 1)
    if var_trial_sr is None:
        # V is the VARIANCE OF SR ACROSS TRIALS, and it is unidentified here -
        # no ledger records per-trial SR. The fallback until 2026-09-11 was
        # max(sr_observed**2, 0.01), which is not a null dispersion at all: it
        # sets sqrt(V) = |SR|, so sr0 = k(N)*|SR| becomes PROPORTIONAL TO THE
        # STATISTIC BEING TESTED. Two consequences, both measured:
        #
        #   * for every N >= 4, k(N) >= 1, so sr0 >= |SR| for any sample and
        #     DSR < 0.5 always - OF-5's `dsr >= 0.90` was unsatisfiable by
        #     construction (exhaustive sweep, 518,616 combinations, 0 passing);
        #   * worse, it is INVERTED. At n=30, N=7 the old fallback scored
        #     SR 0.20 -> DSR 0.340, SR 0.50 -> 0.163, SR 0.75 -> 0.084. A
        #     BETTER track scored WORSE. That is a sign error in behaviour, not
        #     a conservative choice.
        #
        # The principled null substitute is the SAMPLING VARIANCE of a Sharpe
        # estimate under H0: Var(SR_hat) ~ (1 + SR^2/2)/n -> 1/n as SR -> 0.
        # Under the null the trial SRs ARE that dispersion, so 1/n is what the
        # deflation should scale by when the trials were not recorded.
        # Restores monotonicity (n=30, N=7: SR 0.30 -> 0.597, 0.50 -> 0.895,
        # 0.75 -> 0.991) and leaves the 0.90 gate untouched - the bar did not
        # move, it became meetable by evidence instead of by nothing.
        #
        # Pass `var_trial_sr` explicitly the moment a trial ledger records
        # per-trial SR; a measured dispersion beats any null substitute.
        var_trial_sr = 1.0 / max(n, 1)
    # expected max SR under H0 across `trials` tries — Bailey & LdP's own
    # form: sqrt(V)*[(1-gamma)*Z^-1(1-1/N) + gamma*Z^-1(1-1/(N*e))] with
    # exact inverse-normal quantiles. The previous sqrt(2 ln N)
    # asymptotics overstated SR0 by +12-17% at N=10-100 (+67% at N=2) —
    # conservative direction, but off the published formula (2026-07-29
    # literature audit, Danielsson-class scaling review).
    if trials > 1:
        em = 0.5772156649
        e_max = math.sqrt(var_trial_sr) * (
            (1.0 - em) * _norm_ppf(1.0 - 1.0 / trials)
            + em * _norm_ppf(1.0 - 1.0 / (trials * math.e)))
    else:
        e_max = 0.0
    sr0 = e_max
    denom = math.sqrt(max(
        1.0 - skew * sr_observed +
        (kurtosis - 1.0) / 4.0 * sr_observed ** 2, 1e-9) / (n - 1))
    z = (sr_observed - sr0) / denom
    # psr_zero = PSR at SR*=0: the SAME statistic with the trials deflation
    # removed, i.e. what the gate's label claimed to be reporting until
    # 2026-09-11. Additive key (invariant 7) - no caller's behaviour changes,
    # and it is deliberately NOT what dsr_verdict grades. It exists so the
    # sign question ("is the edge positive at all?") and the multiple-testing
    # question ("does it clear the best of N tries?") stop being conflated.
    return {"dsr": float(_norm_cdf(z)), "sr0_threshold": float(sr0),
            "z": float(z), "n": n, "trials": trials,
            "psr_zero": float(_norm_cdf(sr_observed / denom))}


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
                       n_splits: int = 5, seed: int = 7, sig=None,
                       rows_per_feature_floor: float = 10.0,
                       dead_importance_eps: float = 0.002,
                       sample_weight=None) -> dict:
    """Effective degrees of freedom of the fit: rows per feature, and the
    fraction of features whose OOS permutation importance is
    indistinguishable from zero (they only add estimation variance). Uses
    the highest-capacity candidate (gbt) on the last purged OOS fold for
    the importance read. Starved (rows/feature below floor) or a large
    dead fraction both flag overfitting surface that pruning would
    reduce.

    sample_weight (2026-08-01 audit, default None = the historical uniform
    fit): OF-7 answers "which features does the DEPLOYED model actually
    use", so the gbt whose importances are permuted must be the gbt the
    deployed trainer fits - weighted (ml/walkforward.py:302-303). An
    unweighted fit reads the dead list off a model nobody ships. Note
    permutation_importance itself stays unweighted: the deployed path
    scores it unweighted too, so only the MODEL BEING PERMUTED diverged."""
    from ml.walkforward import permutation_importance
    X = np.asarray(X, float)
    y = np.asarray(y, float)
    w = None if sample_weight is None else np.asarray(sample_weight, float)
    n, d = X.shape
    folds = [f for f in purged_walk_forward(n, n_splits, label_span, sig=sig)
             if y[f[0]].sum() >= 5 and (len(y[f[0]]) - y[f[0]].sum()) >= 5]
    dead, imp = [], []
    if folds:
        tr, te = folds[-1]
        if len(te) >= 20:
            m = GradientBoostedStumps(seed=seed).fit(
                X[tr], y[tr], sample_weight=None if w is None else w[tr])
            imp = permutation_importance(m, X[te], y[te], list(feature_names),
                                         n_top=len(feature_names))
            dead = [name for name, drop in imp
                    if abs(drop) <= dead_importance_eps]
    # COVERAGE (2026-08-31): a permutation-importance zero is only evidence
    # about a feature the fitted model actually CONSULTED. Early stopping can
    # leave this GBT a handful of stumps (measured: one seed produced a
    # single tree splitting on 2 features; union across a 3x3 seed/split
    # sweep touched 15 of 64), and every never-split feature then returns an
    # AUC drop of exactly 0.0 - the signature of a blind model, not a dead
    # feature. dead_feature_frac stays byte-identical for existing readers;
    # the new keys let the caller tell "measured dead" from "never looked".
    used: set = set()

    def _walk(node):
        if isinstance(node, dict) and "f" in node:
            used.add(int(node["f"]))
            for k in ("L", "R"):
                if isinstance(node.get(k), dict):
                    _walk(node[k])

    if folds and len(folds[-1][1]) >= 20:
        try:
            for t in m.trees:          # m exists iff the fit above ran
                _walk(t)
        except (AttributeError, NameError):
            pass
    unseen = [nm for i, nm in enumerate(feature_names) if i not in used]
    rpf = n / max(d, 1)
    return {"n_rows": int(n), "n_features": int(d),
            "rows_per_feature": round(float(rpf), 2),
            "dead_feature_frac": round(len(dead) / max(d, 1), 3),
            "dead_features": dead,
            "starved": bool(rpf < rows_per_feature_floor),
            "importance_top": imp[:8],
            "features_consulted": len(used),
            "dead_but_never_consulted": len([f for f in dead if f in unseen]),
            # informative iff the dead list is mostly features the model
            # actually consulted and measured to ~zero - NOT features it
            # never split on. A raw consulted-count threshold was tried
            # first and rejected by its own planted-defect test: the live
            # blind case consulted 15/64 yet 41/48 of its "dead" were
            # never-consulted, while a healthy sparse fit can consult few
            # features and still measure its dead list honestly.
            "scan_informative": (not dead) or (
                len([f for f in dead if f in unseen]) * 2 <= len(dead))}


# ---------------------------------------------------------------------------
# 7) regime-stratified OOF diagnostic (report-only; #103 T3)
# ---------------------------------------------------------------------------
# A literature gap-analysis flagged that pooled OOF metrics can hide a model
# that only works in one regime — this instrument answers that, but it is
# DIAGNOSTIC, not a gate: scripts/overfit_check.py's regime section reports
# every line through info(), never check(), so nothing here can move PASS_N/
# FAIL_N or the exit code. It slices the OOF predictions train_test_gap(...,
# return_oof=True) already produced for OF-1's gbt candidate — no separate
# fit, same folds, same numbers OF-1's pooled gap[gbt] line reports.
REGIME_STRATA = ("bull_quiet", "bull_vol", "range", "bear", "crisis")

# Evidence floor for scoring a stratum's OOF AUC/Brier at all. No existing
# check in this file expresses a bare per-bucket row-count floor (train_test_
# gap/shuffled_label_check gate on FOLD class balance >=5/side,
# feature_dof_report gates on rows/feature) — the closest fit is
# scripts/overfit_check.py's OWN OF-5 evidence floor, which already treats 30
# labeled outcomes as the minimum a point statistic (there: deflated Sharpe)
# can be trusted on (`len(conviction) >= 30` / `len(mixed) < 30`). Reused
# verbatim rather than invented: same question — how many outcomes before a
# rate/score means anything — same file, same answer.
REGIME_MIN_N = 30

# "Materially degrades vs pooled" reuses OF-1's own memorization-band
# threshold (train_test_gap docstring: "gap_auc ... > 0.12 the model is
# memorizing") as the degrade margin. The file already treats a >0.12 AUC
# gap as the line between "watch" and "broken" for a train-vs-OOF
# comparison; a stratum whose OOF AUC sits more than that same margin below
# the POOLED OOF AUC is held to the identical bar, applied to a different
# pair of numbers (stratum-OOF vs pooled-OOF instead of train vs OOF).
REGIME_DEGRADE_MARGIN_AUC = 0.12


# --------------------------------------------------------- learning curve
# Standing plateau-vs-climb instrument (operator-approved 2026-07-29,
# Brownlee/MLM's empirical sample-size method): score expanding
# CHRONOLOGICAL prefixes of the corpus with the same time-purged
# walk-forward the deployed selector uses, and call the trend. A CLIMBING
# curve means the model is data-starved (more rows still buy skill); a
# FLAT one means representation-limited (more rows alone buy nothing —
# improve features/labels instead). Report-only in scripts/
# overfit_check.py: whatever the verdict, it never moves PASS_N/FAIL_N.
LC_FRACTIONS = (0.25, 0.40, 0.55, 0.70, 0.85, 1.00)
# Same evidence floor family as REGIME_MIN_N's rationale (how many scored
# outcomes before a point statistic means anything), scaled up because a
# curve POINT is compared against its neighbors, not just reported: with
# fewer than ~40 OOF rows the AUC standard error alone (~0.09 at the
# corpus base rate) exceeds the trend margin below, making every
# comparison noise by construction.
LC_MIN_OOF = 40
# Climb/decline needs the last-vs-first delta to clear the AUC standard
# error at typical full-prefix n_oof (~0.03 at 700+ scored rows) — below
# it the honest read is "flat within noise".
LC_TREND_MARGIN_AUC = 0.03


def learning_curve(X, y, w, sig, res, model_factory,
                   fractions=LC_FRACTIONS, n_splits: int = 5,
                   label_span: int = 96, min_oof: int = LC_MIN_OOF) -> list:
    """Skill vs corpus size on expanding chronological prefixes.

    Rows are sorted by `sig` (signal time) INTERNALLY, so callers may hand
    the corpus in any order; each prefix is then genuinely "the corpus as
    it stood earlier", and every prefix is scored with purged_walk_forward
    (time purge via the sorted sig/res slices — the deployed selector's
    own leak-free protocol). One model family per call (`model_factory`
    returns a fresh unfitted model); the runner passes gbt, the ladder's
    workhorse. Returns one dict per fraction: {n, scored, n_oof, auc,
    brier} — a prefix whose pooled OOF coverage is under `min_oof` (or
    single-class) reports scored=False with None metrics, never a noisy
    point estimate."""
    X = np.asarray(X, float)
    y = np.asarray(y, float)
    sig = np.asarray(sig, float)
    w = None if w is None else np.asarray(w, float)
    res = None if res is None else np.asarray(res, float)
    order = np.argsort(sig, kind="stable")
    X, y, sig = X[order], y[order], sig[order]
    w = None if w is None else w[order]
    res = None if res is None else res[order]
    points = []
    for frac in fractions:
        n = max(int(round(len(X) * frac)), 1)
        Xp, yp, sp = X[:n], y[:n], sig[:n]
        wp = None if w is None else w[:n]
        rp = None if res is None else res[:n]
        preds = np.full(n, np.nan)
        for tr, te in purged_walk_forward(n, n_splits, label_span,
                                          sig=sp, res=rp):
            if len(tr) < 20 or not 0 < yp[tr].sum() < len(tr):
                continue
            m = model_factory()
            if wp is None:
                m.fit(Xp[tr], yp[tr])
            else:
                m.fit(Xp[tr], yp[tr], sample_weight=wp[tr])
            preds[te] = np.asarray(m.predict_proba(Xp[te]), float)
        mask = ~np.isnan(preds)
        n_oof = int(mask.sum())
        point = {"n": n, "scored": False, "n_oof": n_oof,
                 "auc": None, "brier": None}
        if n_oof >= min_oof and 0 < yp[mask].sum() < n_oof:
            point["scored"] = True
            point["auc"] = float(auc_score(yp[mask], preds[mask]))
            point["brier"] = float(brier_score(yp[mask], preds[mask]))
        points.append(point)
    return points


def learning_curve_trend(points: list,
                         margin: float = LC_TREND_MARGIN_AUC) -> dict:
    """Call the curve: 'climbing' | 'flat' | 'declining' | 'insufficient'.

    Compares the mean AUC of the last two SCORED points against the first
    two (pairs, not endpoints, so one lucky fold can't flip the verdict);
    fewer than 3 scored points is 'insufficient' — no trend claim on two
    dots. Returns {trend, delta_auc, n_scored} with delta_auc None when
    insufficient."""
    scored = [p for p in points if p.get("scored")]
    if len(scored) < 3:
        return {"trend": "insufficient", "delta_auc": None,
                "n_scored": len(scored)}
    head = float(np.mean([p["auc"] for p in scored[:2]]))
    tail = float(np.mean([p["auc"] for p in scored[-2:]]))
    delta = tail - head
    if delta > margin:
        trend = "climbing"
    elif delta < -margin:
        trend = "declining"
    else:
        trend = "flat"
    return {"trend": trend, "delta_auc": delta, "n_scored": len(scored)}


def regime_stratum_labels(one_hot) -> np.ndarray:
    """Stratum = argmax over the five regime one-hot columns (column order:
    REGIME_STRATA, matching ml.features.FEATURE_NAMES' regime_bull_quiet,
    regime_bull_vol, regime_range, regime_bear, regime_crisis block).
    All-zero rows (no active regime label — padded/migrated history, or a
    macro state the labeler never assigned) get "unknown" rather than a
    false argmax(all-zero) == bull_quiet."""
    oh = np.asarray(one_hot, float)
    labels = np.full(len(oh), "unknown", dtype=object)
    active = oh.sum(axis=1) > 0
    if active.any():
        labels[active] = np.asarray(REGIME_STRATA, dtype=object)[
            np.argmax(oh[active], axis=1)]
    return labels


def regime_stratified_oof(y, oof_idx, oof_pred, one_hot_oof,
                          pooled_auc: "float | None" = None,
                          pooled_brier: "float | None" = None,
                          min_n: int = REGIME_MIN_N,
                          degrade_margin: float = REGIME_DEGRADE_MARGIN_AUC
                          ) -> dict:
    """Per-regime-stratum OOF AUC/Brier sliced from predictions ALREADY
    produced by train_test_gap(..., return_oof=True) — no retraining, the
    exact same fitted folds/predictions OF-1 reports pooled numbers for,
    just grouped by stratum. `one_hot_oof` is the (len(oof_idx), 5) regime
    one-hot block for those same rows — feature-column lookup stays with
    the caller, so this function has no opinion on feature layout.

    Below min_n, OR with fewer than 2 rows in either label class, a
    stratum is NEVER scored (no auc/brier computed at all): reported as
    insufficient evidence, not a noisy point estimate off a handful of
    rows."""
    y = np.asarray(y, float)
    oof_idx = np.asarray(oof_idx, int)
    oof_pred = np.asarray(oof_pred, float)
    y_oof = y[oof_idx]
    strata = regime_stratum_labels(one_hot_oof)
    out = {}
    for s in (*REGIME_STRATA, "unknown"):
        mask = strata == s
        n = int(mask.sum())
        row: dict = {"n_oof": n, "scored": False, "auc": None,
                    "brier": None, "degrade": None}
        if n >= min_n and 0 < y_oof[mask].sum() < n:
            auc = float(auc_score(y_oof[mask], oof_pred[mask]))
            brier = float(brier_score(y_oof[mask], oof_pred[mask]))
            row["scored"] = True
            row["auc"] = auc
            row["brier"] = brier
            if pooled_auc is not None:
                row["degrade"] = bool(pooled_auc - auc > degrade_margin)
        out[s] = row
    return out
