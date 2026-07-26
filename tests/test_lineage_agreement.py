"""T2.2b lineage-pair agreement: dedup-discarded candidate twins carry a
proxy label; their live twin carries the realized label. Agreement rate +
Wilson CI must surface in last_load_stats - and the dedup DROP behavior
itself must stay byte-identical (pairs are captured, rows still dropped)."""
import numpy as np
import pytest

from ml.features import FEATURE_NAMES
from ml.history import HistoryStore, wilson_interval


def _feats(seed):
    # _append_row's `feats` must be array-like in FEATURE_NAMES order (it
    # does np.asarray(feats, dtype=float) and writes it positionally) -
    # not a name->value dict.
    rng = np.random.default_rng(seed)
    return rng.normal(0, 1, len(FEATURE_NAMES))


def _store(tmp_path):
    return HistoryStore(path=str(tmp_path / "hist.csv"))


def _pair(store, i, cand_label, live_label):
    cid = f"cand-{i}"
    store._append_row(cid, "ETH", "long", _feats(i), cand_label, 0.0,
                      "candidate", signal_ts=1000.0 + i)
    store._append_row(f"live-{i}", "ETH", "long", _feats(1000 + i),
                      live_label, 5.0, "live", signal_ts=1000.0 + i,
                      probe="0", candidate_id=cid)


def test_wilson_interval_known_values():
    lo, hi = wilson_interval(8, 10)
    assert 0.49 < lo < 0.51 and 0.93 < hi < 0.95
    assert wilson_interval(0, 0) == (0.0, 1.0)


def test_agreement_captured_and_rows_still_dropped(tmp_path):
    store = _store(tmp_path)
    for i in range(8):
        _pair(store, i, 1.0, 1.0)      # 8 agreeing twins
    for i in range(8, 10):
        _pair(store, i, 1.0, 0.0)      # 2 disagreeing twins
    X, y, w = store.load_training_data()
    la = store.last_load_stats["lineage_agreement"]
    assert la["n_pairs"] == 10
    assert la["agreement"] == pytest.approx(0.8)
    lo, hi = la["wilson95"]
    assert 0.0 <= lo <= 0.8 <= hi <= 1.0
    # twins still deduped: 10 live rows survive, 10 candidate twins drop
    assert len(X) == 10
    assert store.last_load_stats["dropped_clash"] == 10


def test_no_pairs_yields_none_fields(tmp_path):
    store = _store(tmp_path)
    store._append_row("solo-1", "ETH", "long", _feats(1), 1.0, 0.0,
                      "candidate", signal_ts=1000.0)
    store.load_training_data()
    la = store.last_load_stats["lineage_agreement"]
    assert la == {"n_pairs": 0, "agreement": None, "wilson95": None}


def test_missing_file_label_times_returns_five_empty(tmp_path):
    """Whole-phase review follow-up: the missing-file early return must
    honor return_label_times (it only special-cased return_sig, so a
    5-way unpack on a fresh checkout raised ValueError - latent hazard
    shared by main.py's retrain path, masked only by _retrain_gate)."""
    store = HistoryStore(path=str(tmp_path / "never_written.csv"))
    X, y, w, sig, res = store.load_training_data(return_label_times=True)
    for arr in (X, y, w, sig, res):
        assert len(arr) == 0
