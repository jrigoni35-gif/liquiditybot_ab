"""
Regression for signal-time ordering (walk-forward leakage defense):
rows land in the CSV at LABEL time, but purged walk-forward must order
and purge by SIGNAL time - candidates ripen in bursts, so label order
scrambles signal order and a row-count purge stops guaranteeing that
no training row's label window overlaps the test block.
"""
import csv

import numpy as np

from ml.features import FEATURE_NAMES
from ml.history import HistoryStore


def test_rows_load_in_signal_time_order(tmp_path):
    store = HistoryStore(str(tmp_path / "hist.csv"))
    feats = np.zeros(len(FEATURE_NAMES))
    # append out of signal order: signal times 300, 100, 200
    for pid, sig in (("a", 300.0), ("b", 100.0), ("c", 200.0)):
        f = feats.copy()
        f[0] = sig            # marker in ret_1_dir (clipped range is ±6,
        f[0] = sig / 100.0    # so use 3.0 / 1.0 / 2.0)
        store._append_row(pid, "BTC", "long", f, 1, 0.0, "candidate",
                          signal_ts=sig)
    X, y, w = store.load_training_data()
    assert list(X[:, 0]) == [1.0, 2.0, 3.0], \
        "load_training_data must return rows in SIGNAL-time order"


def test_pre_upgrade_rows_fall_back_to_label_ts(tmp_path):
    # hand-write an OLD-header file (no signal_ts column)
    path = tmp_path / "hist.csv"
    old_header = ["position_id", "asset", "side", *FEATURE_NAMES,
                  "label", "net_pnl_usd", "source", "ts"]
    with open(path, "w", newline="") as f:
        wtr = csv.writer(f)
        wtr.writerow(old_header)
        for pid, ts in (("x", "200"), ("y", "100")):
            wtr.writerow([pid, "ETH", "long",
                          *["0.0"] * len(FEATURE_NAMES), "1", "0.0",
                          "live", ts])
    X, y, w = HistoryStore(str(path)).load_training_data()
    assert X.shape[0] == 2, "old-schema rows must still load (ts fallback)"


def test_signal_ts_flows_from_log_entry_to_row(tmp_path):
    store = HistoryStore(str(tmp_path / "hist.csv"))
    feats = np.zeros(len(FEATURE_NAMES))
    store.log_entry("p1", "BTC", "long", feats)
    entry = store._pending["p1"]
    assert len(entry) == 5 and entry[3] > 0, "log_entry must stamp signal time"
    sig_ts = entry[3]
    store.log_close("p1", 5.0)
    row = list(csv.DictReader(open(store.path)))[0]
    assert abs(float(row["signal_ts"]) - sig_ts) < 2.0
    assert float(row["ts"]) >= float(row["signal_ts"])
