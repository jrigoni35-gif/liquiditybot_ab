"""tests/test_label_signal_quality.py — operator-decided flip of
ml.label_mode to "triple_barrier" so the training label measures SIGNAL
QUALITY, not which exit policy fired (2026-07-26, task-signalquality-brief.md,
consciously overriding c36aa90's "train on the bet we trade" default).

Pins the BINDING BEHAVIOURS from the brief:
  1. under label_mode="triple_barrier" no policy exit reason (time_stop,
     trail, tier, floor, realized) can ever reach the persisted label -
     only the tb_-prefixed market/horizon vocabulary (tb_pt/tb_sl/tb_time)
     triple_barrier() itself can produce.
  2. under label_mode="exit_policy" behaviour is byte-identical to before
     this task (the rollback path / A-B arm stays intact).
  3. end-to-end: CandidateLabeler.poll() -> the persisted CSV row's
     `barrier` + `label_era` columns are both correct for each mode.
  4. determinism: same inputs -> identical labels, repeatably.

See tests/test_label_era.py for the label_era_of vocabulary/collision pins
and tests/test_config_guard_label_mode.py for the config_guard FATAL.
"""
import csv

import numpy as np

from ml.features import FEATURE_NAMES
from ml.history import (LABEL_ERA_EXIT_SIM, LABEL_ERA_TRIPLE_BARRIER,
                        CandidateLabeler, HistoryStore)
from ml.labeling import ExitPolicy

# Barrier strings ONLY simulate_exit_policy() (or log_close's own hardcoded
# live tag) can ever emit - triple_barrier() cannot produce any of these
# (ml/labeling.py:363-404), so their presence in a triple_barrier-mode row
# would mean a policy exit leaked into the label.
_POLICY_ONLY_REASONS = frozenset({"trail", "tier", "floor", "time_stop",
                                  "realized"})


def _store(tmp_path):
    return HistoryStore(str(tmp_path / "hist.csv"))


def _candle(t, price, hi, lo):
    return {"time": t, "close": price, "high": hi, "low": lo, "volume": 1.0}


def _rows(store):
    with open(store.path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _tb_labeler(tmp_path, exit_policy=None, **cfg_over):
    store = _store(tmp_path)
    ml_cfg = {"label_max_bars": 20, "label_pt_vol_mult": 8.0,
             "label_sl_vol_mult": 6.0, "label_round_trip_cost_pct": 0.1,
             "label_include_spread": False, "label_mode": "triple_barrier"}
    ml_cfg.update(cfg_over)
    return store, CandidateLabeler(store, ml_cfg, exit_policy=exit_policy)


# ============================================================================
# 1. no policy exit reason can reach the label under triple_barrier mode
# ============================================================================

def test_pt_hit_labels_tb_pt_never_a_policy_reason(tmp_path):
    # an ExitPolicy IS supplied (as it would be live) to prove label_mode,
    # not the mere absence of a policy object, is what blocks the leak
    store, lab = _tb_labeler(tmp_path, exit_policy=ExitPolicy())
    feats = np.zeros(len(FEATURE_NAMES))
    lab.register("BTC", "long", feats, sigma_bar=0.005, bar_time=0)
    # sigma 0.5%/bar -> pt = 8 * 0.5% = 4%; bar 2 jumps +5%
    lab.update_candles("BTC", [_candle(0, 100.0, 100.0, 100.0),
                               _candle(1, 100.0, 100.1, 99.9),
                               _candle(2, 105.0, 105.5, 104.5)])
    assert lab.poll() == 1
    rows = _rows(store)
    assert rows[0]["barrier"] == "tb_pt"
    assert rows[0]["label_era"] == LABEL_ERA_TRIPLE_BARRIER
    assert rows[0]["barrier"] not in _POLICY_ONLY_REASONS


def test_sl_hit_labels_tb_sl_never_a_policy_reason(tmp_path):
    store, lab = _tb_labeler(tmp_path, exit_policy=ExitPolicy())
    feats = np.zeros(len(FEATURE_NAMES))
    lab.register("BTC", "long", feats, sigma_bar=0.005, bar_time=0)
    # sl = 6 * 0.5% = 3%; bar 2 dips -4%
    lab.update_candles("BTC", [_candle(0, 100.0, 100.0, 100.0),
                               _candle(1, 100.0, 100.1, 99.9),
                               _candle(2, 96.0, 100.1, 96.0)])
    assert lab.poll() == 1
    rows = _rows(store)
    assert rows[0]["barrier"] == "tb_sl"
    assert rows[0]["label_era"] == LABEL_ERA_TRIPLE_BARRIER
    assert rows[0]["barrier"] not in _POLICY_ONLY_REASONS


def test_time_exhaustion_labels_tb_time_never_a_policy_reason(tmp_path):
    store, lab = _tb_labeler(tmp_path, exit_policy=ExitPolicy())
    feats = np.zeros(len(FEATURE_NAMES))
    lab.register("BTC", "long", feats, sigma_bar=0.005, bar_time=0)
    flat = [_candle(k, 100.0, 100.05, 99.95) for k in range(1, 21)]
    lab.update_candles("BTC", [_candle(0, 100.0, 100.0, 100.0)] + flat)
    assert lab.poll() == 1
    rows = _rows(store)
    assert rows[0]["barrier"] == "tb_time"
    assert rows[0]["label_era"] == LABEL_ERA_TRIPLE_BARRIER
    assert rows[0]["barrier"] not in _POLICY_ONLY_REASONS


def test_label_dispatch_never_emits_a_policy_reason_across_random_paths(
        tmp_path):
    """Broader sweep at the _label() dispatch level (bypassing the
    candle/poll plumbing so many paths are cheap to try): whatever the
    price path, triple_barrier mode can only ever emit tb_pt/tb_sl/tb_time
    because CandidateLabeler._label's triple_barrier branch never calls
    simulate_exit_policy at all - the policy-only vocabulary is
    structurally unreachable, not merely unobserved in these samples."""
    store, lab = _tb_labeler(tmp_path, exit_policy=ExitPolicy())
    rng = np.random.default_rng(7)
    n = 30
    for trial in range(50):
        rets = rng.normal(0.0, 0.01, n)
        closes = 100.0 * np.cumprod(np.concatenate([[1.0], 1.0 + rets]))
        highs = closes * (1.0 + rng.uniform(0.0, 0.005, n + 1))
        lows = closes * (1.0 - rng.uniform(0.0, 0.005, n + 1))
        side = 1 if trial % 2 == 0 else -1
        out = lab._label(closes, highs, lows, 0, side, 0.01, 0.1)
        assert out.barrier in ("tb_pt", "tb_sl", "tb_time")
        assert out.barrier not in _POLICY_ONLY_REASONS


# ============================================================================
# 2. exit_policy mode is unchanged (rollback path / A-B arm intact)
# ============================================================================

def test_exit_policy_mode_barrier_stays_unprefixed(tmp_path):
    store = _store(tmp_path)
    ml_cfg = {"label_max_bars": 96, "label_include_spread": False,
             "label_mode": "exit_policy"}
    lab = CandidateLabeler(store, ml_cfg, exit_policy=ExitPolicy())
    assert lab.label_mode == "exit_policy"
    # immediate -3% breach of the default 2% hard stop (sigma_bar=0)
    closes = np.array([100.0, 97.0])
    highs = np.array([100.0, 97.5])
    lows = np.array([100.0, 96.5])
    out = lab._label(closes, highs, lows, 0, +1, 0.0, 0.5)
    assert out.barrier == "sl"          # bare, unprefixed - unchanged


def test_exit_policy_mode_end_to_end_era_is_exit_sim(tmp_path):
    store = _store(tmp_path)
    ml_cfg = {"label_max_bars": 96, "label_include_spread": False,
             "label_mode": "exit_policy"}
    lab = CandidateLabeler(store, ml_cfg, exit_policy=ExitPolicy())
    feats = np.zeros(len(FEATURE_NAMES))
    lab.register("BTC", "long", feats, sigma_bar=0.0, bar_time=0)
    lab.update_candles("BTC", [_candle(0, 100.0, 100.0, 100.0),
                               _candle(1, 97.0, 100.2, 97.0)])
    assert lab.poll() == 1
    rows = _rows(store)
    assert rows[0]["barrier"] == "sl"
    assert rows[0]["label_era"] == LABEL_ERA_EXIT_SIM


# ============================================================================
# 3. determinism: same corpus + seed + mode -> identical labels
# ============================================================================

def test_label_dispatch_is_deterministic(tmp_path):
    _, lab = _tb_labeler(tmp_path)
    closes = np.array([100.0, 101.0, 99.0, 108.5])
    highs = closes * 1.01
    lows = closes * 0.99
    out1 = lab._label(closes, highs, lows, 0, +1, 0.01, 0.1)
    out2 = lab._label(closes, highs, lows, 0, +1, 0.01, 0.1)
    assert out1 == out2


def test_load_training_data_is_deterministic_for_triple_barrier_rows(
        tmp_path, monkeypatch):
    store, lab = _tb_labeler(tmp_path, exit_policy=ExitPolicy())
    feats = np.zeros(len(FEATURE_NAMES))
    lab.register("BTC", "long", feats, sigma_bar=0.005, bar_time=0)
    lab.update_candles("BTC", [_candle(0, 100.0, 100.0, 100.0),
                               _candle(1, 100.0, 100.1, 99.9),
                               _candle(2, 105.0, 105.5, 104.5)])
    assert lab.poll() == 1
    # FREEZE THE CLOCK. load_training_data() stamps `now = time.time()`
    # (ml/history.py) and the recency half-life decays every weight against
    # it, BY DESIGN. Two separately-clocked loads therefore differ in the
    # last bits, and asserting np.array_equal across them is a coin flip —
    # measured 5-6 failures in 12 runs before this freeze, with and without
    # any weighting change. Freeze first, then assert, exactly as 34bb82d
    # did for status()'s last_poll_age_sec. The determinism this pins is
    # "same inputs AND same clock -> same weights", which is the property
    # that actually matters; recency-vs-wall-clock is intended behaviour,
    # not the thing under test.
    monkeypatch.setattr("time.time", lambda: 1785000000.0)
    X1, y1, w1 = store.load_training_data()
    X2, y2, w2 = store.load_training_data()
    assert np.array_equal(X1, X2)
    assert np.array_equal(y1, y2)
    assert np.array_equal(w1, w2)
