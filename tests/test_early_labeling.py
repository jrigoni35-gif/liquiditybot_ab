"""
Regression for early-decidable candidate labeling: a pt/sl barrier hit
inside the available candle window is FINAL (triple_barrier scans
chronologically and stops at the first touch), so the primary row must
be written immediately - not 8h later at the full horizon. Only 'time'
labels wait. The old always-wait behavior delayed every label by the
full horizon and turned any registration gap into an equal-width label
drought 8h later (observed live 2026-07-14: 80 candidates, zero
conversions for hours).
"""
import csv

import numpy as np

from ml.features import FEATURE_NAMES
from ml.history import CandidateLabeler, HistoryStore

CFG = {"label_max_bars": 96, "label_pt_vol_mult": 8.0,
       "label_sl_vol_mult": 6.0, "label_round_trip_cost_pct": 0.1,
       "label_include_spread": False}


def _bars(n, start_px=100.0, jump_at=None, jump_to=None):
    return [{"time": k * 300, "open": start_px, "close": start_px,
             "high": jump_to if (jump_at is not None and k >= jump_at)
             else start_px * 1.0001,
             "low": start_px * 0.9999}
            for k in range(n)]


def _labeler(tmp_path):
    store = HistoryStore(str(tmp_path / "h.csv"))
    return CandidateLabeler(store, CFG), store


def test_barrier_hit_labels_immediately(tmp_path):
    lab, store = _labeler(tmp_path)
    feats = np.zeros(len(FEATURE_NAMES))
    lab.register("BTC", "long", feats, 0.005, 0)   # sigma 0.5%/bar, pt=4%
    # only 10 of 96 bars exist, but bar 5 jumps +5% -> pt hit, decidable
    lab.update_candles("BTC", _bars(10, jump_at=5, jump_to=105.5))
    assert lab.poll() == 1, "pt hit inside the window must label NOW"
    rows = list(csv.DictReader(open(store.path)))
    assert len(rows) == 1 and rows[0]["label"] == "1"
    # candidate stays for shadow completion, but never re-labels
    assert len(lab._cands) == 1 and lab._cands[0]["labeled"]
    assert lab.poll() == 0
    assert len(list(csv.DictReader(open(store.path)))) == 1


def test_undecided_short_window_waits(tmp_path):
    lab, store = _labeler(tmp_path)
    lab.register("BTC", "long", np.zeros(len(FEATURE_NAMES)), 0.005, 0)
    lab.update_candles("BTC", _bars(10))           # flat: nothing hit
    assert lab.poll() == 0, "'time' cannot be decided on a short window"
    assert len(lab._cands) == 1 and not lab._cands[0].get("labeled")


def test_timeout_labels_exactly_once_at_full_horizon(tmp_path):
    lab, store = _labeler(tmp_path)
    lab.register("BTC", "long", np.zeros(len(FEATURE_NAMES)), 0.005, 0)
    lab.update_candles("BTC", _bars(97))           # full horizon, flat path
    assert lab.poll() == 1
    rows = list(csv.DictReader(open(store.path)))
    assert len(rows) == 1
    assert len(lab._cands) == 0, "fully-resolved candidate must be removed"


def test_early_labeled_candidate_removed_at_horizon_without_dup(tmp_path):
    lab, store = _labeler(tmp_path)
    lab.register("BTC", "long", np.zeros(len(FEATURE_NAMES)), 0.005, 0)
    lab.update_candles("BTC", _bars(10, jump_at=5, jump_to=105.5))
    assert lab.poll() == 1                         # early label
    lab.update_candles("BTC", _bars(97, jump_at=5, jump_to=105.5))
    assert lab.poll() == 0                         # horizon pass: no dup
    assert len(lab._cands) == 0
    assert len(list(csv.DictReader(open(store.path)))) == 1
