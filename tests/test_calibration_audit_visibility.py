"""
Regression: ml/calibration.py's IsotonicCalibrator silently no-ops to
identity when fit on <20 OOF points (calibration.py:61-62) - a model can
ship uncalibrated with only a quiet log.info buried in the training
console output, invisible to session_digest/the audit chain/anyone
checking later. Both places that fit a calibrator during a real deploy
decision (main.py's in-process auto-retrain and scripts/train_meta.py's
CLI retrain) now also emit a loud warning AND a registered audit-chain
entry (Code.ML_CALIBRATION_SKIPPED / "ML-014") when this happens.

This test drives scripts/train_meta.py's actual main() end-to-end (not a
reimplementation) with evaluate_and_select monkeypatched to return a
fixed <20-OOF-point result, so the walk-forward/model-fitting cost stays
out of the test and only the code path this change touches is exercised.
"""
import json
import sys

import numpy as np

import scripts.train_meta as train_meta
from core.audit import get_audit
from ml.features import FEATURE_NAMES
from ml.models import GradientBoostedStumps


def _write_history_csv(path, n_rows=60):
    # must match HistoryStore's own header exactly (ml/history.py:43-44) or
    # it treats the file as a schema change and rotates it away, dropping
    # to 0 rows and triggering the (network-hitting) bootstrap path.
    cols = ["position_id", "asset", "side", *FEATURE_NAMES,
           "label", "net_pnl_usd", "source", "ts"]
    lines = [",".join(cols)]
    for i in range(n_rows):
        feats = ["0.0"] * len(FEATURE_NAMES)
        label = "1" if i % 2 == 0 else "0"
        lines.append(",".join([f"pos{i}", "BTC", "long"] + feats +
                              [label, "0.5", "live", str(1_700_000_000 + i)]))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_config(path, history_path, model_path):
    cfg = {
        "ml": {"min_train_rows": 20, "history_path": str(history_path),
              "model_path": str(model_path),
              # this test's subject is the ML-014 skipped-calibration audit,
              # exercised via a deliberately tiny (12-point) OOF set. The
              # LP-6 evidence floor (deploy_min_oof, default 30) would now
              # correctly refuse that deploy - opt out so the calibration
              # path still completes; the floor has its own pins in
              # tests/test_audit_batch_51.py.
              "monitor": {"deploy_min_oof": 0}},
        "system": {"state_path": str(model_path.parent / "state.json")},
    }
    path.write_text(json.dumps(cfg), encoding="utf-8")


def _small_oof_results():
    """A fixed evaluate_and_select()-shaped result with 12 OOF points
    (<20) so the calibrator is guaranteed to no-op, without paying for a
    real walk-forward run."""
    rng = np.random.default_rng(9)
    X = rng.normal(size=(40, 4))
    y = (X[:, 0] > 0).astype(float)
    model = GradientBoostedStumps(seed=3).fit(X, y)
    oof_p = np.clip(model.predict_proba(X[:12]), 0.05, 0.95)
    oof_y = y[:12]
    stub = {"aucs": [0.6], "mean_auc": 0.6, "mean_brier": 0.25,
           "oof_p": np.array([]), "oof_y": np.array([])}
    return {
        "selected": "gbt",
        "logistic": stub, "blend": stub, "mlp": stub,
        "gbt": {"aucs": [0.6], "mean_auc": 0.6, "mean_brier": 0.2,
               "oof_p": oof_p, "oof_y": oof_y},
        "model": model,
        "importance": [],
    }


def test_train_meta_logs_and_audits_skipped_calibration(tmp_path, monkeypatch):
    history_csv = tmp_path / "signal_history.csv"
    model_path = tmp_path / "meta_model.json"
    config_path = tmp_path / "config.json"
    _write_history_csv(history_csv)
    _write_config(config_path, history_csv, model_path)

    monkeypatch.setattr(train_meta, "evaluate_and_select",
                        lambda *a, **kw: _small_oof_results())
    monkeypatch.setattr(sys, "argv",
                        ["train_meta.py", "--config", str(config_path)])

    audit_path = get_audit().path
    before = audit_path.read_text(encoding="utf-8") if audit_path.exists() else ""

    rc = train_meta.main()

    assert rc == 0
    after = audit_path.read_text(encoding="utf-8")
    new_lines = after[len(before):].strip().splitlines()
    records = [json.loads(line) for line in new_lines if line.strip()]
    calib_records = [r for r in records if r.get("code") == "ML-014"]
    assert len(calib_records) == 1, (
        f"expected exactly one ML-014 audit record, got {len(calib_records)}: "
        f"{records}")
    assert calib_records[0]["data"]["oof_points"] == 12


def test_calibrator_still_unfitted_below_20_points_baseline():
    # sanity: the underlying no-op threshold this whole test depends on
    from ml.calibration import IsotonicCalibrator
    cal = IsotonicCalibrator().fit(np.linspace(0.1, 0.9, 12),
                                   np.array([0, 1] * 6, float))
    assert cal.fitted is False
