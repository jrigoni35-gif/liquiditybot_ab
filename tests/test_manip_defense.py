"""
Regression for the adversarial-data defense (v5): manip_suspect is a
parameter-free MAX of spoof score, imbalance whiplash, and the
execution-venue-vs-composite book divergence - components a manipulator
cannot cheaply fake in unison. It is a FEATURE (model learns its worth)
and a training-weight DISCOUNT (lessons from painted books count less),
never a new gate. Pins the math, the bounds, and the hygiene weighting.
"""
import numpy as np

from main import _book_imbalance, manip_suspect_score, whiplash_suspicion
from ml.features import FEATURE_NAMES
from ml.history import HistoryStore


def test_clean_data_scores_zero():
    assert manip_suspect_score(0.0, 0.0, 0.5, 0.5) == 0.0


def test_whiplash_normalized_against_calibrated_envelope():
    # raw imbalance-whiplash is a STD (healthy p50~1.1, p95~1.27,
    # 'spoofy' at 1.45): inside the healthy envelope suspicion is ZERO -
    # feeding the raw std saturated manip_suspect at 1.0 on quiet books
    assert whiplash_suspicion(1.10, 1.27, 1.45) == 0.0   # healthy median
    assert whiplash_suspicion(1.27, 1.27, 1.45) == 0.0   # healthy p95
    assert abs(whiplash_suspicion(1.36, 1.27, 1.45) - 0.5) < 1e-9
    assert whiplash_suspicion(1.45, 1.27, 1.45) == 1.0   # spoofy threshold
    assert whiplash_suspicion(9.99, 1.27, 1.45) == 1.0   # clipped ceiling
    assert whiplash_suspicion(0.0, 1.27, 1.45) == 0.0


def test_whiplash_degenerate_span_never_divides_by_zero():
    assert whiplash_suspicion(2.0, 1.45, 1.45) == 1.0
    assert whiplash_suspicion(1.0, 1.45, 1.45) == 0.0


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


def test_composite_imbalance_is_coherent_per_venue_not_merged():
    """SD-003: the manip divergence term compared Kraken to a merged book of
    OKX (perp, contract-unit sizes) + Binance.US (spot, coin-unit sizes). A
    log-ratio over the concatenation is unit-garbage and square-waved a false
    'spoofy'/divergence flag on BTC/ETH. The composite must be the mean of
    PER-VENUE log-imbalances (each unit-coherent within its own book)."""
    from main import _composite_imbalance, _book_imbalance
    # two venues, wildly different SIZE UNITS but each individually balanced
    okx = {"bids": [[100.0, 5.0]], "asks": [[100.1, 5.0]]}        # ~balanced
    bus = {"bids": [[100.0, 900.0]], "asks": [[100.1, 900.0]]}    # ~balanced
    comp = _composite_imbalance([okx, bus])
    assert comp is not None and abs(comp) < 1e-6, \
        "two individually-balanced venues -> composite ~0, not unit-driven skew"
    # a merged-book log-ratio would be ~0 here too, but flip one venue's sizes
    # to show per-venue averaging tracks each book's OWN imbalance
    okx2 = {"bids": [[100.0, 20.0]], "asks": [[100.1, 5.0]]}      # bid-heavy
    bus2 = {"bids": [[100.0, 900.0]], "asks": [[100.1, 900.0]]}   # balanced
    comp2 = _composite_imbalance([okx2, bus2])
    expected = 0.5 * (_book_imbalance(okx2) + _book_imbalance(bus2))
    assert abs(comp2 - expected) < 1e-9, "mean of per-venue log-imbalances"


def test_composite_imbalance_none_when_no_external_book():
    """No coherent external venue this cycle -> composite is unmeasurable.
    Returns None so the caller mirrors kraken_imb (divergence 0), never
    flagging Kraken's own natural imbalance as manipulation."""
    from main import _composite_imbalance
    assert _composite_imbalance([]) is None
    assert _composite_imbalance([{"bids": [], "asks": []}]) is None
    assert _composite_imbalance([{"bids": [[1, 1]]}]) is None      # one side
