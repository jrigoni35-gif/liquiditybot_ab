"""Live-label data hygiene: the ground-truth corpus must be clean BY
CONSTRUCTION. A single NaN/inf feature poisons an entire retrain (it
propagates through every gradient, AUC and Brier), and float('nan') slips
through float() silently - the parse never raises. Guard at BOTH ends:

  * write (ML-015): _append_row refuses a non-finite feature or pnl, so a
    momentary bad feature vector from the engine never enters the file.
  * load  (ML-015): load_training_data drops any already-stored non-finite
    row (legacy build, imported bundle, hand edit) rather than train on it.
"""
import csv

import numpy as np

from ml.features import FEATURE_NAMES
from ml.history import HistoryStore


def _store(tmp_path):
    return HistoryStore(str(tmp_path / "signal_history.csv"))


def _clean_feats():
    return np.arange(len(FEATURE_NAMES), dtype=float) * 0.01


def _rows(path):
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_write_refuses_nan_feature(tmp_path):
    hs = _store(tmp_path)
    feats = _clean_feats()
    feats[3] = float("nan")
    hs._append_row("p_nan", "BTC", "long", feats, 1, 12.0, "live")
    assert _rows(hs.path) == []                       # nothing persisted


def test_write_refuses_inf_pnl(tmp_path):
    hs = _store(tmp_path)
    hs._append_row("p_inf", "ETH", "long", _clean_feats(), 1,
                   float("inf"), "live")
    assert _rows(hs.path) == []


def test_write_accepts_clean_row(tmp_path):
    hs = _store(tmp_path)
    hs._append_row("p_ok", "BTC", "long", _clean_feats(), 1, 8.5, "live")
    rows = _rows(hs.path)
    assert len(rows) == 1 and rows[0]["position_id"] == "p_ok"


def test_load_drops_stored_nonfinite_row(tmp_path):
    """A dirty row that predates the write guard (or arrived in an imported
    bundle) must not reach training - load skips it, keeps the clean rows."""
    hs = _store(tmp_path)
    hs._append_row("clean1", "BTC", "long", _clean_feats(), 1, 5.0, "live")
    hs._append_row("clean2", "ETH", "short", _clean_feats() + 0.5, 0,
                   -3.0, "live")
    # inject a dirty row directly, bypassing the write guard (simulates
    # legacy/imported data)
    with open(hs.path, "a", newline="", encoding="utf-8") as f:
        dirty = ["dirty", "SOL", "long", *["nan"] + [f"{v:.6f}" for v in
                 _clean_feats()[1:]], "1", "2.0", "live", "1700000000",
                 "1700000000"]
        csv.writer(f).writerow(dirty)
    X, y, w = hs.load_training_data()
    assert len(X) == 2                                # dirty row dropped
    assert np.all(np.isfinite(X)) and np.all(np.isfinite(y))


def test_load_all_clean_keeps_everything(tmp_path):
    hs = _store(tmp_path)
    for i in range(4):
        hs._append_row(f"p{i}", "BTC", "long", _clean_feats() + i * 0.1,
                       i % 2, float(i), "live")
    X, y, w = hs.load_training_data()
    assert len(X) == 4 and np.all(np.isfinite(X))
