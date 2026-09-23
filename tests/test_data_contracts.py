"""Integration / data-contract tests: the serialized contracts that cross a
process or restart boundary must round-trip byte-faithfully, and the loaders
must fail SAFE (never crash the engine) on a missing or malformed artifact.

These are the "contracts between services" for a single-process, file-state
bot: the model artifact (trainer -> runner/inference), the calibrator inside
it (Kelly reads it literally), and the history CSV schema (engine -> trainer).
"""
import json

import numpy as np

from ml.calibration import IsotonicCalibrator
from ml.features import FEATURE_NAMES
from ml.history import SG_COMPONENT_KEYS, HistoryStore
from ml.models import GradientBoostedStumps, LogisticModel, load_model, save_model


def _xy(n=400, seed=2):
    rng = np.random.default_rng(seed)
    X = rng.normal(0, 1, (n, len(FEATURE_NAMES)))
    y = (X[:, 0] + rng.normal(0, 1, n) > 0).astype(float)
    return X, y


# --- model artifact round-trip (trainer -> inference) ----------------------
def test_logistic_artifact_round_trips_predictions(tmp_path):
    X, y = _xy()
    m = LogisticModel(seed=1).fit(X, y)
    p = tmp_path / "m.json"
    save_model(m, str(p))
    back = load_model(str(p))
    assert back is not None
    assert np.allclose(back.predict_proba(X), m.predict_proba(X))


def test_gbt_artifact_round_trips_predictions(tmp_path):
    X, y = _xy()
    m = GradientBoostedStumps(seed=1).fit(X, y)
    p = tmp_path / "g.json"
    save_model(m, str(p))
    back = load_model(str(p))
    assert back is not None
    assert np.allclose(back.predict_proba(X), m.predict_proba(X))


def test_artifact_stamps_self_describing_schema_and_extras(tmp_path):
    X, y = _xy()
    m = LogisticModel(seed=1).fit(X, y)
    p = tmp_path / "m.json"
    save_model(m, str(p), extra={"oof_brier": 0.19, "rows": len(X),
                                 "calibration": {"x": [0.1, 0.9],
                                                 "y": [0.2, 0.8]}})
    d = json.loads(p.read_text())
    assert "feature_schema_version" in d and d["kind"] == "logistic"
    assert d["oof_brier"] == 0.19 and d["rows"] == len(X)
    assert d["calibration"]["x"] == [0.1, 0.9]


def test_missing_artifact_loads_none_not_crash(tmp_path):
    assert load_model(str(tmp_path / "nope.json")) is None


# --- calibrator contract (Kelly consumes this literally) -------------------
def test_isotonic_calibrator_serialization_round_trips_transform():
    rng = np.random.default_rng(4)
    p_raw = rng.random(200)
    y = (rng.random(200) < p_raw).astype(float)
    cal = IsotonicCalibrator().fit(p_raw, y)
    assert cal.fitted
    back = IsotonicCalibrator.from_dict(cal.to_dict())
    grid = np.linspace(0, 1, 50)
    assert np.allclose(cal.transform(grid), back.transform(grid))


def test_unfitted_calibrator_is_identity_and_serializes_to_none():
    cal = IsotonicCalibrator()                    # <20 pts never fitted
    cal.fit(np.array([0.4, 0.6]), np.array([0.0, 1.0]))
    assert not cal.fitted
    assert cal.to_dict() is None
    grid = np.linspace(0, 1, 10)
    assert np.allclose(cal.transform(grid), grid)  # identity


# --- history CSV schema contract (engine -> trainer) -----------------------
def test_history_header_contract_is_stable(tmp_path):
    hs = HistoryStore(str(tmp_path / "h.csv"))
    # barrier joined 2026-07-19 (AFML corrections: time-barrier zeros are
    # distinguished from stop-hit zeros at load time) — a conscious,
    # migration-backed schema extension, appended last so meta order is stable
    # probe joined 2026-07-20 (task #48): bookkeeping-only marker so OF-5
    # can grade the conviction-only sample mid-exploration — appended last
    # candidate_id joined 2026-07-23 (W2-4): twin-dedup lineage join key —
    # appended last so meta order (and every past bump) stays stable
    # book joined 2026-07-24 (Compounder Phase C, Task C1): 5m/long strategy
    # book tag — appended last so meta order (and every past bump) stays
    # stable
    # label_era joined 2026-07-26 (label-era instrumentation, DEEP DIVE
    # progress.md): which label DEFINITION produced the row's barrier —
    # appended last so meta order (and every past bump) stays stable
    # pt_frac, sl_frac joined 2026-07-27 (geometry-alignment T3): the
    # barrier_geometry() bracket a row's label was decided under —
    # appended last so meta order (and every past bump) stays stable
    # sg_flow..sg_conc joined 2026-07-28 (gate-truth instrumentation T2):
    # the informed-flow engine's component scores at signal time —
    # appended last so meta order (and every past bump) stays stable
    # entry_price, exit_price joined 2026-08-04 (price anchor): the
    # absolute price a row's bet was anchored at / resolved at, so rows
    # can be re-examined in price space (relabelling at a new horizon,
    # external-tape alignment, realized-return audits) - appended last
    # so meta order (and every past bump) stays stable
    # avail_web..quotes_frozen joined 2026-08-08 (owed 41b): which context
    # feeds were LIVE when the row's features were built - a dark feed's
    # neutrals are byte-identical to genuine neutral, so without these no
    # consumer can separate "feed down" from "flat" from "predates the
    # feature". "" = unknown (legacy/uncarried), "1"/"0" = recorded.
    # BOOKKEEPING ONLY, never features (the 2026-08-08 DoF adjudication
    # keeps the ledger closed) - appended last so meta order stays stable
    expected = ["position_id", "asset", "side", *FEATURE_NAMES,
                "label", "net_pnl_usd", "source", "ts", "signal_ts",
                "barrier", "probe", "disp", "candidate_id", "book",
                "label_era", "pt_frac", "sl_frac",
                *[f"sg_{k}" for k in SG_COMPONENT_KEYS],
                "entry_price", "exit_price",
                "avail_web", "avail_equity", "avail_options",
                "quotes_frozen",
                # avail_darkpool joined 2026-09-21 (schema 95->96, same
                # bump as FEATURE_SCHEMA_VERSION 9->10): the v10 dark-pool
                # mirror's availability at signal time - bookkeeping only,
                # same "" = UNKNOWN convention as the other avail_* flags
                # - appended last so meta order stays stable
                "avail_darkpool",
                # label_ret_pct joined 2026-08-24 (schema 94): the labeled
                # outcome's realized return in percent - before it,
                # _emit_label computed BarrierOutcome.ret_pct and discarded
                # it, so no candidate label could ever be re-adjudicated at
                # a corrected cost. "" = UNKNOWN, appended last (until the
                # next bump below).
                "label_ret_pct",
                # control_arm joined 2026-08-27 (schema 95, sandbox
                # prototype): deterministic 5% signal-time stratification
                # tag (ml/history.py CONTROL_ARM_FRACTION) - cures the
                # frozen-baseline defect (gate_efficacy_report's baseline
                # arm has been n=0 since 2026-07-20) by minting a fresh
                # contemporaneous control cohort going forward. "1"/"0" on
                # every new row, "" for rows written before this column -
                # appended last.
                "control_arm"]
    assert hs._header == expected


def test_written_row_reads_back_through_the_same_contract(tmp_path):
    hs = HistoryStore(str(tmp_path / "h.csv"))
    feats = np.arange(len(FEATURE_NAMES), dtype=float)
    hs._append_row("pid", "BTC", "long", feats, 1, 4.2, "live")
    X, y, w = hs.load_training_data()
    assert len(X) == 1 and X.shape[1] == len(FEATURE_NAMES)
    assert y[0] == 1.0
    assert hs.source_counts() == {"live": 1}
