"""
Regression for the adversarial-data defense (v5): manip_suspect is a
parameter-free MAX of spoof score, imbalance whiplash, and the
execution-venue-vs-composite book divergence - components a manipulator
cannot cheaply fake in unison. It is a FEATURE (model learns its worth)
and a training-weight DISCOUNT (lessons from painted books count less),
never a new gate. Pins the math, the bounds, and the hygiene weighting.
"""
import numpy as np

from main import _book_imbalance, manip_suspect_score
from ml.features import FEATURE_NAMES
from ml.history import HistoryStore


def test_clean_data_scores_zero():
    assert manip_suspect_score(0.0, 0.0, 0.5, 0.5) == 0.0


def test_max_composition_no_fitted_weights():
    assert manip_suspect_score(0.7, 0.1, 0.0, 0.0) == 0.7    # spoof leads
    assert manip_suspect_score(0.1, 0.9, 0.0, 0.0) == 0.9    # whiplash leads
    # kraken +2 vs composite -2: full divergence -> 1.0
    assert manip_suspect_score(0.0, 0.0, 2.0, -2.0) == 1.0
    assert manip_suspect_score(2.0, 5.0, 0.0, 0.0) == 1.0    # hard ceiling


def test_divergence_scales_linearly():
    assert abs(manip_suspect_score(0.0, 0.0, 1.0, -1.0) - 0.5) < 1e-9


def test_book_imbalance_sign_and_safety():
    bidheavy = {"bids": [[100, 30.0]], "asks": [[101, 10.0]]}
    assert _book_imbalance(bidheavy) > 0
    assert _book_imbalance({"bids": [], "asks": [[101, 1.0]]}) == 0.0
    assert _book_imbalance({}) == 0.0


def _write_history(path, suspects):
    header = HistoryStore(str(path))._header
    idx = header.index("manip_suspect")
    lines = [",".join(header)]
    for i, sus in enumerate(suspects):
        row = ["0.0"] * len(header)
        row[0], row[1], row[2] = f"p{i}", "BTC", "long"
        row[idx] = f"{sus:.6f}"
        row[header.index("label")] = "1"
        row[header.index("net_pnl_usd")] = "1.0"
        row[header.index("source")] = "live"
        row[header.index("ts")] = "9999999999"   # zero age -> recency w = 1
        lines.append(",".join(row))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_training_weights_discount_suspect_rows(tmp_path):
    hist = tmp_path / "signal_history.csv"
    _write_history(hist, [0.0, 1.0, 0.5])
    store = HistoryStore(str(hist))
    X, y, w = store.load_training_data(half_life_days=30,
                                       manip_discount=0.5)
    assert X.shape == (3, len(FEATURE_NAMES))
    assert np.allclose(w, [1.0, 0.5, 0.75])      # 1 - 0.5*suspect
    _, _, w0 = store.load_training_data(manip_discount=0.0)
    assert np.allclose(w0, [1.0, 1.0, 1.0])      # discount off -> no effect
