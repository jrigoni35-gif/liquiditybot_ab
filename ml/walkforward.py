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

from ml.calibration import (IsotonicCalibrator, brier_score,
                            calibration_gap)
from ml.models import (AdaptiveGBT, BlendModel, EnsembleMLP,
                       GradientBoostedStumps, LogisticModel, auc_score)

log = logging.getLogger("liquiditybot.ml.walkforward")

# simple -> complex; a step right must EARN its complexity. blend
# (logistic+gbt probability average, unfitted 0.5 weight) sits above
# gbt: it contains gbt plus a second learner, so it must beat gbt by
# the margin to ship — the "stronger model" transition is evidence-
# gated, never assumed.
_LADDER = ("logistic", "gbt", "blend", "mlp")
# adaptive_gbt (bagged, warm-updatable boosted trees) is the next rung
# UP from mlp, but it is NOT in the default ladder: like every new
# capability in this repo it ships opt-in, entering the deployed
# selection only when the operator passes it as an extra_model (driven
# by ml.adaptive_gbt.enabled in config). So the default selection rule —
# the one overfit_check's PBO measures — is byte-for-byte unchanged.
# _COMPLEXITY is the canonical complexity order for ANY candidate the
# ladder may include, so an appended extra rung is placed by merit-
# earned complexity, not by call order. Names absent here fall to the
# end (treated as most complex).
# gbt_mono (T3.4: monotone-constrained GBT) sits DIRECTLY AFTER gbt - it
# is the same learner class with a priori sign constraints, not a step up
# in raw capacity, so it must earn its place at gbt's own complexity tier,
# never fall through to "most complex" by silent last-placement.
_COMPLEXITY = ("logistic", "gbt", "gbt_mono", "blend", "mlp", "adaptive_gbt")
BRIER_MARGIN = 0.002

# Higher-capacity families that must EARN their place with evidence; logistic
# (the linear baseline) is always admissible and defines the simplicity floor.
# Ordered simple -> complex, same axis as _COMPLEXITY. gbt_mono is NOT
# listed here by name: it shares gbt's evidence floor via pbo_family()
# (below), the same way PBO's hyperparameter-variant names ("gbt_d2_lr05"
# etc.) share it - see evaluate_and_select's admitted-set check.
_GATED_FAMILIES = ("gbt", "blend", "mlp", "adaptive_gbt")


def admissible_families(n_live: int, n_total: int,
                        cfg: dict | None = None) -> set:
    """Which model families the LABEL evidence can support — the "don't try
    to learn every way when there's no chance" gate.

    Model capacity needs a minimum sample-per-effective-parameter to
    generalize rather than memorize (the classic events-per-variable floor;
    Peduzzi 1996). A boosted-tree / MLP / bagged ensemble fit on a handful of
    ground-truth outcomes can only overfit — its out-of-fold score is noise
    and entering it into the selection space just manufactures a lucky winner
    (inflating PBO). So a higher-capacity family is admitted ONLY when BOTH
    floors clear:

      * min_live_rows  — enough LIVE (real closed-trade) labels. Complexity
        is earned on ground truth, not on triple-barrier proxies; this is why
        the split matters, not the proxy-inflated total.
      * min_total_rows — enough TOTAL labeled rows to fit non-degenerate
        purged folds at all.

    logistic is always in the returned set (it is the baseline the ladder
    falls back to). cfg=None or enabled=False -> every family admissible,
    preserving the historical selection exactly for callers that opt out
    (existing tests, replay). Floors live in config.model_selection (guarded
    in core/config_guard.py) — never hardcoded here."""
    admitted = {"logistic"}
    cfg = cfg or {}
    if not cfg.get("enabled", False):
        return set(_GATED_FAMILIES) | admitted
    min_live = cfg.get("min_live_rows", {}) or {}
    min_total = cfg.get("min_total_rows", {}) or {}
    for fam in _GATED_FAMILIES:
        if (n_live >= int(min_live.get(fam, 0))
                and n_total >= int(min_total.get(fam, 0))):
            admitted.add(fam)
    return admitted


def pbo_family(name: str) -> str:
    """Map a PBO-space config name (hyperparameter variant) to its model
    family, so the evidence gate applies identically to the measured
    selection space and the deployed ladder."""
    if name == "logistic":
        return "logistic"
    if name.startswith("gbt"):
        return "gbt"
    if name.startswith("mlp"):
        return "mlp"
    if name == "adaptive_gbt":
        return "adaptive_gbt"
    return name
# canonical bar interval for the triple-barrier horizon (5-minute candles);
# time-based purge converts label_span (bars) -> seconds with this.
BAR_SECONDS = 300.0


def purged_walk_forward(n: int, n_splits: int = 5, label_span: int = 96,
                        embargo_frac: float = 0.02, sig=None, res=None):
    """Yields (train_idx, test_idx) with purge + embargo, expanding window.

    Purge mode:
      - row-count (sig=None, default): drop the last `label_span` training
        ROWS before each test block. Correct ONLY if rows are evenly spaced
        in time.
      - time-based (sig given): drop every training row whose label window
        (sig[i] + label_span * BAR_SECONDS) reaches into the test block's
        first signal. Signals arrive in BURSTS, so a fixed row count spans a
        variable amount of TIME - a dense burst right before the boundary
        leaks future labels that the row-count purge silently keeps (OF-6
        leakage). `sig` is the per-row signal timestamp (seconds), sorted
        ascending as load_training_data returns it; `n` must equal len(sig).
    """
    if n < (n_splits + 1) * 30:
        n_splits = max(2, n // 60)
    use_time = sig is not None and len(sig) == n
    if use_time:
        sig = np.asarray(sig, float)
        horizon_sec = float(label_span) * BAR_SECONDS
        # LP-1: `res` (per-row label RESOLUTION time) supersedes the
        # fixed horizon when given - a live row held past the label
        # window resolves at CLOSE, and assuming signal+span leaked
        # its still-in-the-future label into training folds. The
        # fixed-horizon path remains for callers without res.
        use_res = res is not None and len(res) == n
        if use_res:
            res = np.asarray(res, float)
    # NOTE: with an expanding window (train strictly precedes test) the
    # post-test embargo is a no-op — it only matters for combinatorial CV
    # where training data can follow the test block. embargo_frac is kept
    # in the signature for API stability.
    fold = n // (n_splits + 1)
    for k in range(1, n_splits + 1):
        test_start = k * fold
        test_end = min(test_start + fold, n)
        if use_time and use_res:
            # type-narrowing invariant guard: use_time/use_res imply the
            # arrays exist (set above); assert for the checker, never fires
            assert sig is not None and res is not None
            # keep only rows whose label ACTUALLY resolved before the
            # test opens; res is not monotone in sig (variable holds)
            # so this is a mask, not a prefix
            train_idx = np.where(
                (np.arange(n) < test_start)
                & (res <= sig[test_start]))[0]
        elif use_time:
            assert sig is not None      # implied by use_time (see above)
            # keep only rows whose label fully resolves at/before the test
            # opens: sig[i] + horizon <= sig[test_start]
            cutoff = sig[test_start] - horizon_sec
            train_end = int(np.searchsorted(sig, cutoff, side="right"))
            train_idx = np.arange(0, train_end)
        else:
            train_end = max(test_start - label_span, 0)      # row-count purge
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


def _factories(seed: int, ensemble_k: int,
               adaptive_cfg: dict | None = None,
               gbt_mono_cfg: dict | None = None) -> dict:
    ac = adaptive_cfg or {}
    # gbt_mono_cfg carries constraints ALREADY RESOLVED to {feature_index:
    # sign} by the caller (main.py's retrain wiring has FEATURE_NAMES;
    # this module deliberately does not import it, same reasoning as
    # config_guard's lazy import - see core/config_guard.py's gbt_mono
    # block).
    gm = gbt_mono_cfg or {}
    return {
        "logistic": lambda: LogisticModel(seed=seed),
        "gbt": lambda: GradientBoostedStumps(seed=seed),
        "gbt_mono": lambda: GradientBoostedStumps(
            seed=seed, monotone_constraints=gm.get("constraints") or None),
        "blend": lambda: BlendModel(seed=seed),
        "mlp": lambda: EnsembleMLP(k=ensemble_k, seed=seed),
        "adaptive_gbt": lambda: AdaptiveGBT(
            k=int(ac.get("bags", 4)),
            warm_rounds=int(ac.get("warm_rounds", 25)),
            max_total_trees=int(ac.get("max_total_trees", 800)),
            seed=seed),
    }


def evaluate_and_select(X: np.ndarray, y: np.ndarray, label_span: int = 96,
                        n_splits: int = 5, seed: int = 7,
                        sample_weight=None, feature_names=None,
                        ensemble_k: int = 3, sig=None,
                        extra_models=(), adaptive_cfg=None,
                        n_live: int | None = None,
                        select_cfg: dict | None = None,
                        res=None,
                        gbt_mono_cfg: dict | None = None) -> dict:
    """Walk-forward all candidates; ship the Brier winner (simplicity-
    biased), fitted on all data. When `sig` (per-row signal timestamps) is
    given the fold purge is TIME-based, not row-count - the deployed model
    is selected on genuinely leak-free OOF.

    extra_models appends opt-in rungs (e.g. "adaptive_gbt", "gbt_mono")
    ABOVE the default ladder; the effective ladder is re-sorted into
    canonical complexity order so a step right always costs the model the
    Brier margin. Default extra_models=() reproduces the historical
    selection exactly. gbt_mono_cfg carries {"constraints": {feature_index:
    sign}} already resolved from config feature NAMES to indices by the
    caller (mirrors adaptive_cfg's pass-through of raw hyperparameters).

    n_live / select_cfg drive the EVIDENCE GATE (admissible_families): a
    higher-capacity family is trained and entered into selection only when
    the label evidence can support it. n_live is the count of LIVE (real
    closed-trade) rows; total is len(X). Both default None -> no gating
    (historical behavior). The admitted set is recorded in
    results['admitted']/'gated' for the caller to audit."""
    X = np.asarray(X, float)
    y = np.asarray(y, float)
    w = None if sample_weight is None else np.asarray(sample_weight, float)
    factories = _factories(seed, ensemble_k, adaptive_cfg, gbt_mono_cfg)
    full_ladder = tuple(name for name in _COMPLEXITY
                        if name in _LADDER or name in tuple(extra_models))
    # evidence gate: n_live unknown -> treat as unlimited so nothing is gated
    _nl = len(X) if n_live is None else int(n_live)
    admitted = admissible_families(_nl, len(X), select_cfg)
    # pbo_family() translation (not a bare `name in admitted`): a ladder
    # NAME need not be its own family - gbt_mono is a hyperparameter
    # variant of "gbt" the same way model_space_pbo's "gbt_d2_lr05" etc.
    # are, and must clear (or be gated by) gbt's own evidence floor, not
    # a floor keyed on a name that never appears in _GATED_FAMILIES. A
    # no-op for every pre-T3.4 ladder name (pbo_family(x) == x for all of
    # them), so historical gating is unchanged.
    ladder = tuple(name for name in full_ladder
                  if pbo_family(name) in admitted)
    gated = [name for name in full_ladder if pbo_family(name) not in admitted]
    if gated:
        log.info("selection ladder evidence-gated: training %s, skipping %s "
                 "(live=%s, total=%d) - too little ground truth to justify "
                 "the extra capacity", list(ladder), gated, n_live, len(X))
    results = {}
    results["admitted"] = list(ladder)
    results["gated"] = gated
    last_fold_model: dict = {}
    # folds are identical for every ladder candidate (the class-balance skip
    # depends only on y[tr]); materialize once so the caller can also know
    # WHICH rows were scored out-of-fold (results["oof_idx"] — needed to
    # rescore a frozen incumbent champion on the same fresh evidence)
    folds = [(tr, te) for tr, te in
             purged_walk_forward(len(X), n_splits, label_span, sig=sig,
                                 res=res)
             if y[tr].sum() >= 5 and (len(y[tr]) - y[tr].sum()) >= 5]
    results["oof_idx"] = (np.concatenate([te for _, te in folds])
                          if folds else np.empty(0, int))

    for name in ladder:
        factory = factories[name]
        aucs, briers, oof_p, oof_y = [], [], [], []
        for tr, te in folds:
            model = factory().fit(
                X[tr], y[tr], sample_weight=None if w is None else w[tr])
            p_te = model.predict_proba(X[te])
            aucs.append(auc_score(y[te], p_te))
            briers.append(brier_score(y[te], p_te))
            oof_p.append(p_te)
            oof_y.append(y[te])
            last_fold_model[name] = (model, te)
        cat_p = np.concatenate(oof_p) if oof_p else np.empty(0)
        cat_y = np.concatenate(oof_y) if oof_y else np.empty(0)
        # Calibration DIAGNOSTIC (not the selection metric): fit the same
        # isotonic calibrator the artifact ships, and record the calibrated
        # OOF Brier + residual calibration gap for every candidate so the
        # operator can see each model's miscalibration ("look into the gap").
        # Selection stays on RAW Brier on purpose: raw Brier PENALIZES a
        # model's miscalibration, so it is the stricter, simplicity-preserving
        # bar. Selecting on calibrated Brier instead let isotonic "rescue" a
        # complex model's raw miscalibration and elect it in a pure-linear
        # world (noise-fitting past the margin) - the opposite of the overfit
        # discipline. The deploy gate (main.py) still checks the calibrated
        # challenger beats the champion, so calibration governs the final
        # ship decision; selection just refuses to be rescued into complexity.
        # <20 OOF points -> calibrator is identity, so cal == raw (graceful).
        if len(cat_p):
            cal = IsotonicCalibrator().fit(cat_p, cat_y)
            cat_p_cal = np.asarray(cal.transform(cat_p), float)
            brier_cal = brier_score(cat_y, cat_p_cal)
            gap_cal = calibration_gap(cat_y, cat_p_cal)
        else:
            brier_cal, gap_cal = 0.25, 0.0
        results[name] = {
            "aucs": aucs,
            "mean_auc": float(np.mean(aucs)) if aucs else 0.5,
            "mean_brier": float(np.mean(briers)) if briers else 0.25,
            # calibration diagnostics (reported, not selected on)
            "mean_brier_cal": float(brier_cal),
            "calib_gap": float(gap_cal),
            "oof_p": cat_p,
            "oof_y": cat_y,
        }
        log.info("%s: mean_auc=%.3f brier_raw=%.4f brier_cal=%.4f "
                 "calib_gap=%.4f", name, results[name]["mean_auc"],
                 results[name]["mean_brier"], brier_cal, gap_cal)

    # simplicity-biased selection on RAW OOF Brier: climb the ladder only when
    # a more complex family beats the incumbent by more than the margin. Raw
    # (not calibrated) so a model must earn complexity on genuine skill, never
    # on isotonic rescuing its calibration (see the diagnostic note above).
    winner = ladder[0]
    for cand in ladder[1:]:
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
    log.info("selected model: %s (raw brier %s | calib_gap %s)", winner,
             {k: round(results[k]["mean_brier"], 4) for k in ladder},
             {k: round(results[k]["calib_gap"], 3) for k in ladder})
    return results
