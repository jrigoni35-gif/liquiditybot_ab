"""tests/test_pbo_variants.py — T3.2/T3.6a: opt-in variant axes (schema
column-subset / epoch row-mask) inside ml.overfit.model_space_pbo.

Binding invariants under test (per the task brief):
  1. BYTE-IDENTITY: with schema_ab_cols=epoch_ab_mask=None (the default),
     model_space_pbo's returned structure is unchanged from the pre-T3.2
     function. Pinned against values captured from the ACTUAL pre-refactor
     code on a fixed synthetic corpus (see the literal `_PINNED` dict below
     — captured by running the unmodified ml/overfit.py before this task's
     refactor touched it; the refactor must reproduce it exactly).
  2. EVAL-ROWS-IDENTICAL: a row-masked arm trains on tr ∩ mask but always
     predicts/scores the FULL shared OOF row set — test rows are never
     masked, only training data varies.
  3. GRACEFUL DEGRADE: a row mask that leaves a fold's training subset too
     thin (or single-class) must not crash — it falls back to the full
     unmasked training window for that fold and records a reason.
  4. schema-ab loads Task 1's `always_dead` snapshot, drops exactly those
     columns (regime one-hots re-exempted defensively), and fails loudly
     on a malformed prune file.
  5. epoch-ab keeps every live row and only excludes pre-cutoff candidate
     rows from training.
  6. INFO-only: experiment-arm reporting never becomes a check()/gate.
"""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from ml.features import FEATURE_NAMES, REGIME_ONE_HOT_FEATURES
from ml.history import HistoryStore
from ml.overfit import (_fit_predict_arm, build_epoch_ab_mask,
                        load_schema_ab_cols, model_space_pbo)

_ROOT = Path(__file__).resolve().parents[1]


def _synthetic_corpus(n=800, d=15, seed=13):
    """Deterministic synthetic world, independent of tests/test_overfit.py's
    own generator (own seed/shape) so this pin can never accidentally couple
    to that file's fixtures changing."""
    rng = np.random.default_rng(seed)
    X = rng.normal(size=(n, d))
    logit = 0.5 * X[:, 0] + 1.2 * X[:, 1] * (X[:, 2] > 0) - 0.2 * X[:, 3] + 0.1
    y = (rng.random(n) < 1 / (1 + np.exp(-logit))).astype(float)
    return X, y


# ---------------------------------------------------------------------------
# 1) RED-then-GREEN byte-identity pin
# ---------------------------------------------------------------------------
# Captured by running the UNMODIFIED (pre-T3.2) ml.overfit.model_space_pbo
# on _synthetic_corpus()'s exact output, BEFORE the space/order refactor in
# this task touched the function - see task-2-report.md "how I proved
# byte-identity" for the exact command. This is the ground truth the
# refactor must reproduce bit-for-bit when schema_ab_cols/epoch_ab_mask are
# both left at their default (None).
_PINNED = {
    "pbo": 0.2,
    "n_combos": 20,
    "n_configs": 7,
    "n_blocks": 6,
    "median_lambda": 1.9459101490553132,
    "configs": ["logistic", "gbt_d2_lr05", "gbt_d3_lr05", "gbt_d3_lr10",
               "gbt_d4_lr05", "gbt_d2_lr10", "mlp_small"],
    "pbo_argmax": 0.25,
    "selection_rule": "simplicity_ladder",
    "is_winner": "logistic",
}


def test_model_space_pbo_baseline_is_byte_identical_to_pre_t32_pin():
    X, y = _synthetic_corpus()
    r = model_space_pbo(X, y, label_span=30, n_splits=4, n_blocks=6, seed=13)
    assert set(r.keys()) == set(_PINNED.keys()), (
        f"baseline call must add NO new keys: got {sorted(r.keys())}, "
        f"expected {sorted(_PINNED.keys())}")
    for k, expected in _PINNED.items():
        assert r[k] == expected, f"{k}: {r[k]!r} != pinned {expected!r}"


def test_model_space_pbo_no_flags_means_no_experiment_keys():
    """Structural half of the byte-identity guarantee: schema_ab_cols and
    epoch_ab_mask both default None -> 'experiments'/'experiment_notes'/
    'degraded_folds' must be ABSENT (not just falsy) from the returned
    dict, on any corpus, not just the pinned one."""
    X, y = _synthetic_corpus(n=500, seed=41)
    r = model_space_pbo(X, y, label_span=25, n_splits=4, n_blocks=6, seed=41)
    assert "experiments" not in r
    assert "experiment_notes" not in r
    assert "degraded_folds" not in r


# ---------------------------------------------------------------------------
# 2) eval-rows-identical property (on the factored _fit_predict_arm helper)
# ---------------------------------------------------------------------------
def _toy_folds_and_oof(n=200, seed=3):
    """Two non-overlapping expanding-window-style folds, hand-built (not
    purged_walk_forward) so the property test is independent of that
    generator's own behavior."""
    rng = np.random.default_rng(seed)
    X = rng.normal(size=(n, 4))
    y = (rng.random(n) < 0.5).astype(float)
    folds = [
        (np.arange(0, 100), np.arange(100, 150)),
        (np.arange(0, 150), np.arange(150, 200)),
    ]
    oof_idx = np.concatenate([te for _, te in folds])
    return X, y, folds, oof_idx


def test_fit_predict_arm_row_mask_never_shrinks_or_reorders_eval_rows():
    """The BINDING invariant: regardless of row_mask, the arm must predict
    on the FULL, unmasked te for every fold - so preds always has exactly
    len(oof_idx) entries, aligned 1:1 to oof_idx in fold-concatenation
    order, whether row_mask is None, all-True, a partial mask, or a mask
    that excludes an ENTIRE te block."""
    X, y, folds, oof_idx = _toy_folds_and_oof()

    def factory():
        from ml.models import LogisticModel
        return LogisticModel(seed=5)

    preds_none, notes_none = _fit_predict_arm(
        "base", factory, X, y, folds, oof_idx, row_mask=None)
    assert preds_none.shape == (len(oof_idx),)
    assert notes_none == []

    # mask that zeroes out an entire te block for fold 1 (rows 100-149) -
    # since te is NEVER masked, predictions for that block must still be
    # produced (no NaN, no shrink).
    mask = np.ones(len(X), dtype=bool)
    mask[100:150] = False
    preds_masked, _ = _fit_predict_arm(
        "arm", factory, X, y, folds, oof_idx, row_mask=mask)
    assert preds_masked.shape == preds_none.shape
    assert np.isfinite(preds_masked).all(), (
        "masking an entire te block must not blank out its predictions - "
        "test rows are never masked")

    # a mask that also excludes plenty of TRAINING rows (but leaves enough
    # of each fold's tr intact to fit) must still score every oof row
    mask2 = np.ones(len(X), dtype=bool)
    mask2[10:60] = False
    preds_masked2, notes2 = _fit_predict_arm(
        "arm2", factory, X, y, folds, oof_idx, row_mask=mask2)
    assert preds_masked2.shape == preds_none.shape
    assert notes2 == [], "plenty of rows remain - no degrade expected"


# ---------------------------------------------------------------------------
# 3) graceful degrade on a too-thin row-masked training fold
# ---------------------------------------------------------------------------
def test_fit_predict_arm_degrades_gracefully_when_masked_fold_too_thin():
    """A mask that leaves fold 0's tr ∩ mask with almost nothing (single
    class / near-empty) must not raise - it falls back to the full
    unmasked tr for that fold only, and records a human-readable reason."""
    X, y, folds, oof_idx = _toy_folds_and_oof()

    def factory():
        from ml.models import LogisticModel
        return LogisticModel(seed=5)

    mask = np.zeros(len(X), dtype=bool)   # excludes ALL rows -> every fold's
    mask[150:200] = True                  # tr ∩ mask empty until late rows
    preds, notes = _fit_predict_arm(
        "thin", factory, X, y, folds, oof_idx, row_mask=mask)
    assert preds.shape == (len(oof_idx),)
    assert np.isfinite(preds).all()
    assert len(notes) == 2, f"expected both folds to degrade: {notes}"
    assert all("degraded to the full unmasked" in n for n in notes)
    assert "fold 0" in notes[0] and "fold 1" in notes[1]


def test_model_space_pbo_epoch_ab_degrade_is_visible_and_non_fatal():
    """End-to-end: an epoch_ab_mask that excludes almost all early rows
    must not crash model_space_pbo - it reports degraded_folds and still
    returns a real pbo."""
    X, y = _synthetic_corpus(n=800, seed=13)
    mask = np.ones(len(X), dtype=bool)
    mask[:400] = False
    r = model_space_pbo(X, y, label_span=30, n_splits=4, n_blocks=6, seed=13,
                        epoch_ab_mask=mask)
    assert "gbt_d3_lr05_epoch_ab" in r["configs"]
    assert r.get("degraded_folds"), "expected at least one degrade note"
    assert all("gbt_d3_lr05_epoch_ab" in n for n in r["degraded_folds"])
    assert r["pbo"] is not None


# ---------------------------------------------------------------------------
# 4) schema-ab: load_schema_ab_cols
# ---------------------------------------------------------------------------
def test_load_schema_ab_cols_drops_exactly_the_prune_list(tmp_path):
    dead = ["ret_1_dir", "corr_shift", "th_clockwork"]
    snap = tmp_path / "stability_x.json"
    snap.write_text(json.dumps({"always_dead": dead}), encoding="utf-8")

    cols = load_schema_ab_cols(str(snap), FEATURE_NAMES)
    kept = {FEATURE_NAMES[i] for i in cols}
    assert kept == set(FEATURE_NAMES) - set(dead)
    assert len(cols) == len(FEATURE_NAMES) - len(dead)
    # indices are strictly increasing (stable column order preserved)
    assert list(cols) == sorted(cols)


def test_load_schema_ab_cols_defensively_re_exempts_regime_one_hots(tmp_path):
    """Even if a (stale/foreign) snapshot's always_dead names a regime
    one-hot, load_schema_ab_cols must keep it anyway — the five regime
    concept columns are NEVER pruned, regardless of what any prune file
    claims."""
    dead = ["ret_1_dir", *REGIME_ONE_HOT_FEATURES]
    snap = tmp_path / "stability_y.json"
    snap.write_text(json.dumps({"always_dead": dead}), encoding="utf-8")

    cols = load_schema_ab_cols(str(snap), FEATURE_NAMES)
    kept = {FEATURE_NAMES[i] for i in cols}
    for regime_col in REGIME_ONE_HOT_FEATURES:
        assert regime_col in kept, f"{regime_col} must never be pruned"
    assert "ret_1_dir" not in kept


def test_load_schema_ab_cols_missing_always_dead_key_fails_loudly(tmp_path):
    snap = tmp_path / "bad.json"
    snap.write_text(json.dumps({"ever_dead": ["ret_1_dir"]}), encoding="utf-8")
    with pytest.raises(ValueError, match="always_dead"):
        load_schema_ab_cols(str(snap), FEATURE_NAMES)


def test_load_schema_ab_cols_unknown_feature_fails_loudly(tmp_path):
    snap = tmp_path / "stale.json"
    snap.write_text(json.dumps({"always_dead": ["not_a_real_feature"]}),
                    encoding="utf-8")
    with pytest.raises(ValueError, match="not_a_real_feature"):
        load_schema_ab_cols(str(snap), FEATURE_NAMES)


def test_load_schema_ab_cols_on_the_real_task1_snapshot():
    """Sanity check against the REAL Task 1 artifact this repo shipped
    (outputs/feature_reports/stability_20260726-063915.json) - proves the
    contract reads a genuine snapshot, not just hand-built fixtures."""
    real = (_ROOT / "outputs" / "feature_reports" /
           "stability_20260726-063915.json")
    if not real.exists():
        pytest.skip("real Task 1 snapshot not present in this checkout")
    cols = load_schema_ab_cols(str(real), FEATURE_NAMES)
    kept = {FEATURE_NAMES[i] for i in cols}
    snap = json.loads(real.read_text(encoding="utf-8"))
    for f in snap["always_dead"]:
        if f not in REGIME_ONE_HOT_FEATURES:
            assert f not in kept
    for regime_col in REGIME_ONE_HOT_FEATURES:
        assert regime_col in kept


# ---------------------------------------------------------------------------
# 5) epoch-ab: build_epoch_ab_mask
# ---------------------------------------------------------------------------
def _write_history_csv(path, rows):
    import csv
    header = (["asset", "side"] + list(FEATURE_NAMES) +
             ["label", "signal_ts", "ts", "source", "book", "candidate_id"])
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        for r in rows:
            w.writerow(r)


def _row(asset, side, label, signal_ts, ts, source, feat_val=0.0,
        book="5m"):
    return ([asset, side] + [str(feat_val)] * len(FEATURE_NAMES) +
           [str(label), str(signal_ts), str(ts), source, book, ""])


def test_build_epoch_ab_mask_keeps_all_live_rows_drops_precutoff_candidates(
        tmp_path):
    hist = tmp_path / "hist.csv"
    cutoff = 1000.0
    rows = [
        _row("ETH", "long", 1, 500, 600, "live"),      # live, pre-cutoff res
        _row("ETH", "long", 1, 1500, 1600, "live"),    # live, post-cutoff res
        _row("BTC", "long", 0, 400, 900, "candidate"),  # cand, res < cutoff
        _row("BTC", "long", 1, 1400, 1100, "candidate"),  # cand, res>=cutoff
    ]
    _write_history_csv(hist, rows)
    store = HistoryStore(str(hist))
    X, y, w, sig, res = store.load_training_data(return_label_times=True)
    assert len(X) == 4

    mask = build_epoch_ab_mask(str(hist), sig, res, cutoff)
    assert mask.dtype == bool
    assert mask.sum() == 3   # both live rows + the post-cutoff candidate

    # every row with res >= cutoff must be included regardless of source
    assert bool(mask[res >= cutoff].all())
    # a dropped row must be a candidate with res < cutoff
    for i in np.where(~mask)[0]:
        assert res[i] < cutoff


def test_build_epoch_ab_mask_never_drops_a_live_row_on_key_collision(
        tmp_path):
    """T3.2 review CRITICAL regression. The pre-fix join keyed solely on
    (round(signal_ts, 6), round(ts, 6)) with last-write-wins on collision:
    two rows from DIFFERENT sources sharing that key let the later one's
    source silently overwrite the earlier one's. This is not hypothetical
    - candidates from several assets routinely share a poll-cycle append
    time (`ts`) and land on the same grid-aligned `signal_ts` (5m candle
    boundaries), so a live row and an unrelated candidate row sharing the
    exact key is a matter of when, not if (measured on the real corpus:
    345 distinct keys collide across 714 rows, ~15% of it).

    Setup: a live row and a candidate row share the OLD (signal_ts, ts)
    key; the candidate appears LATER in the file (so last-write-wins would
    resolve the shared key to "candidate"); the live row's own resolve-ts
    sits BELOW the cutoff (so misclassifying it as a pre-cutoff candidate
    would drop it from the arm's training set). A live label must NEVER be
    excluded, in any era, for any reason - this must hold regardless."""
    hist = tmp_path / "collide.csv"
    shared_signal_ts, shared_ts = 500, 600
    cutoff = 700.0   # ABOVE the shared resolve-ts
    rows = [
        _row("ETH", "long", 1, shared_signal_ts, shared_ts, "live"),
        _row("BTC", "short", 0, shared_signal_ts, shared_ts, "candidate"),
    ]
    _write_history_csv(hist, rows)
    store = HistoryStore(str(hist))
    X, y, w, sig, res = store.load_training_data(return_label_times=True)
    assert len(X) == 2, "both rows must survive (different assets, no twin)"

    mask = build_epoch_ab_mask(str(hist), sig, res, cutoff)

    # the live row's output row is the one with label==1 (the candidate's
    # label is 0) - identify it by label rather than assuming sort order,
    # so the assertion doesn't depend on load_training_data's internal
    # tie-breaking among equal signal_ts values.
    live_positions = np.where(y == 1.0)[0]
    assert len(live_positions) == 1
    live_idx = int(live_positions[0])
    assert res[live_idx] < cutoff, "test setup: live row must be pre-cutoff"
    assert mask[live_idx], (
        "a live row must NEVER be dropped, even when it shares a "
        "(signal_ts, ts) join key with a later-appearing candidate row "
        "of a different source")


def test_build_epoch_ab_mask_all_live_history_keeps_everything(tmp_path):
    """No candidate rows at all -> mask is all-True regardless of cutoff."""
    hist = tmp_path / "hist_live_only.csv"
    rows = [_row("ETH", "long", i % 2, 100.0 * i, 100.0 * i + 50, "live")
           for i in range(1, 6)]
    _write_history_csv(hist, rows)
    store = HistoryStore(str(hist))
    X, y, w, sig, res = store.load_training_data(return_label_times=True)
    mask = build_epoch_ab_mask(str(hist), sig, res, cutoff_ts=10_000.0)
    assert mask.all()


def test_build_epoch_ab_mask_fails_open_on_unreadable_history():
    sig = np.array([1.0, 2.0, 3.0])
    res = np.array([1.0, 2.0, 3.0])
    mask = build_epoch_ab_mask("/nonexistent/does/not/exist.csv", sig, res,
                               cutoff_ts=2.0)
    assert mask.all()


# ---------------------------------------------------------------------------
# 6) end-to-end: both experiment arms wired into model_space_pbo together
# ---------------------------------------------------------------------------
def test_model_space_pbo_both_experiment_arms_report_pbo_ladder_mean_winner():
    X, y = _synthetic_corpus(n=800, seed=13)
    d = X.shape[1]
    cols = np.array([i for i in range(d) if i != 3])
    mask = np.ones(len(X), dtype=bool)
    mask[:40] = False   # a mild, non-degrading exclusion

    r = model_space_pbo(X, y, label_span=30, n_splits=4, n_blocks=6, seed=13,
                        schema_ab_cols=cols, epoch_ab_mask=mask)

    assert "gbt_d3_lr05_schema_ab" in r["configs"]
    assert "gbt_d3_lr05_epoch_ab" in r["configs"]
    # both variant arms sit directly after their base in the space, so the
    # deployed selection rule (never argmax) still governs — sanity check
    # the overall run still produced a real pbo, not a fabricated number.
    assert r["pbo"] is not None
    exp = r["experiments"]
    assert set(exp.keys()) == {"gbt_d3_lr05_schema_ab", "gbt_d3_lr05_epoch_ab"}
    for arm_name, e in exp.items():
        assert e["base"] == "gbt_d3_lr05"
        assert e["pbo"] is None or 0.0 <= e["pbo"] <= 1.0
        assert e["ladder_winner"] in (e["base"], arm_name)
        assert e["mean_winner"] in (e["base"], arm_name)


def test_model_space_pbo_experiment_arm_skipped_when_base_evidence_gated():
    """If the evidence gate drops the base family entirely (e.g. a strict
    model_selection config at a low n_live), the experiment arm must be
    SKIPPED with a note, never crash, never silently fabricate an arm from
    a family that isn't even in the measured space."""
    X, y = _synthetic_corpus(n=800, seed=13)
    strict_select_cfg = {
        "enabled": True,
        "min_live_rows": {"gbt": 10_000},
        "min_total_rows": {"gbt": 10_000},
    }
    r = model_space_pbo(X, y, label_span=30, n_splits=4, n_blocks=6, seed=13,
                        n_live=5, select_cfg=strict_select_cfg,
                        schema_ab_cols=np.arange(X.shape[1]))
    assert "gbt_d3_lr05" not in r.get("configs", [])
    assert not any("schema_ab" in c for c in r.get("configs", []))
    assert r.get("experiment_notes") or r.get("pbo") is None


# ---------------------------------------------------------------------------
# 7) CLI-level: INFO-only, gating checks unchanged when opting in
# ---------------------------------------------------------------------------
def _check_names(report_text: str) -> set:
    names = set()
    for line in report_text.splitlines():
        for status in ("PASS", "FAIL"):
            prefix = f"- **{status}** "
            if line.startswith(prefix):
                names.add(line[len(prefix):].split(" — ")[0].strip())
    return names


def _info_lines(report_text: str) -> list:
    return [line for line in report_text.splitlines()
           if line.startswith("- **INFO**")]


def test_schema_ab_flag_adds_no_new_gating_check_and_is_info_only(tmp_path):
    prunefile = tmp_path / "empty_prune.json"
    prunefile.write_text(json.dumps({"always_dead": []}), encoding="utf-8")

    report_baseline = tmp_path / "baseline.md"
    report_schema = tmp_path / "schema.md"

    proc1 = subprocess.run(
        [sys.executable, str(_ROOT / "scripts" / "overfit_check.py"),
         "--quick", "--force-synthetic", "--report-path",
         str(report_baseline)],
        cwd=str(tmp_path), capture_output=True, text=True, timeout=120)
    assert proc1.returncode == 0, f"{proc1.stdout}\n{proc1.stderr}"

    proc2 = subprocess.run(
        [sys.executable, str(_ROOT / "scripts" / "overfit_check.py"),
         "--quick", "--force-synthetic", "--schema-ab", str(prunefile),
         "--report-path", str(report_schema)],
        cwd=str(tmp_path), capture_output=True, text=True, timeout=120)
    assert proc2.returncode == 0, f"{proc2.stdout}\n{proc2.stderr}"

    baseline_text = report_baseline.read_text(encoding="utf-8")
    schema_text = report_schema.read_text(encoding="utf-8")

    # no NEW check()-gated assertion was introduced by opting in
    assert _check_names(schema_text) == _check_names(baseline_text)

    # the experiment arm shows up, and ONLY as INFO
    info_texts = " ".join(_info_lines(schema_text))
    assert "schema-ab" in info_texts
    assert "pbo experiment[gbt_d3_lr05_schema_ab]" in info_texts
    for line in schema_text.splitlines():
        if "schema_ab" in line or "schema-ab" in line:
            assert line.startswith("- **INFO**"), (
                f"experiment-arm line must be INFO-only: {line}")


def test_epoch_ab_flag_is_a_no_op_info_line_on_synthetic_benchmark(tmp_path):
    """--epoch-ab has no signal_history.csv correspondence on the SYNTHETIC
    benchmark path; it must degrade to a single INFO skip line, never crash
    and never add/move a gating check."""
    report_baseline = tmp_path / "baseline2.md"
    report_epoch = tmp_path / "epoch.md"

    proc1 = subprocess.run(
        [sys.executable, str(_ROOT / "scripts" / "overfit_check.py"),
         "--quick", "--force-synthetic", "--report-path",
         str(report_baseline)],
        cwd=str(tmp_path), capture_output=True, text=True, timeout=120)
    assert proc1.returncode == 0

    proc2 = subprocess.run(
        [sys.executable, str(_ROOT / "scripts" / "overfit_check.py"),
         "--quick", "--force-synthetic", "--epoch-ab", "--report-path",
         str(report_epoch)],
        cwd=str(tmp_path), capture_output=True, text=True, timeout=120)
    assert proc2.returncode == 0, f"{proc2.stdout}\n{proc2.stderr}"

    baseline_text = report_baseline.read_text(encoding="utf-8")
    epoch_text = report_epoch.read_text(encoding="utf-8")
    assert _check_names(epoch_text) == _check_names(baseline_text)
    assert "epoch-ab" in epoch_text
    assert "- **INFO** epoch-ab" in epoch_text


def test_schema_ab_malformed_prunefile_fails_loudly_non_zero_exit(tmp_path):
    bad = tmp_path / "bad_prune.json"
    bad.write_text(json.dumps({"ever_dead": []}), encoding="utf-8")
    report = tmp_path / "report.md"
    proc = subprocess.run(
        [sys.executable, str(_ROOT / "scripts" / "overfit_check.py"),
         "--quick", "--force-synthetic", "--schema-ab", str(bad),
         "--report-path", str(report)],
        cwd=str(tmp_path), capture_output=True, text=True, timeout=120)
    assert proc.returncode != 0
    assert "always_dead" in proc.stderr
