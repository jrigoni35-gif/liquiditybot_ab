"""AFML ch.4 sample-weight corrections (config ml.sample_weights).

The quiet-weekend incident: 197 overlapping-horizon candidate labels, ~97%
label=0 and mostly vertical/time-barrier, entered training at full weight.
Overlapping labels on one asset share the same return path — they are NOT
independent evidence (Lopez de Prado, AFML ch.4: average uniqueness), a
no-touch time-barrier zero is weaker evidence than a realized stop-out, and a
one-sided batch shifts the class prior under the calibrator. These tests pin
the three corrections: uniqueness weighting, time-barrier-zero down-weight,
and the ML-074 prior-skew detector (detect, never silently reweight).
"""
import numpy as np
import pytest

import ml.history as mh
from ml.features import FEATURE_NAMES
from ml.history import HistoryStore


def _feats(seed):
    rng = np.random.default_rng(seed)
    f = rng.normal(0.0, 1.0, len(FEATURE_NAMES))
    # manip_suspect is a FEATURE that also drives the manip-discount weight
    # leg; zero it so these tests isolate the uniqueness/barrier/skew legs
    f[FEATURE_NAMES.index("manip_suspect")] = 0.0
    return f


def _store(tmp_path):
    return HistoryStore(str(tmp_path / "hist.csv"))


def _freeze(monkeypatch, t):
    monkeypatch.setattr(mh.time, "time", lambda: float(t))


# ---- barrier column round-trip --------------------------------------------
def test_barrier_column_round_trips(tmp_path, monkeypatch):
    hs = _store(tmp_path)
    _freeze(monkeypatch, 1_000_000.0)
    hs._append_row("c1", "BTC", "long", _feats(1), 0, 0.0, "candidate",
                   signal_ts=999_000.0, barrier="time")
    with open(hs.path, encoding="utf-8") as f:
        header = f.readline().strip().split(",")
        row = f.readline().strip().split(",")
    assert header[-3] == "barrier" and row[-3] == "time"
    assert header[-2] == "probe" and row[-2] == ""   # candidates: unmarked
    assert header[-1] == "disp" and row[-1] == ""    # no pipeline verdict


def test_live_close_writes_realized_barrier(tmp_path, monkeypatch):
    hs = _store(tmp_path)
    _freeze(monkeypatch, 1_000_000.0)
    hs.log_entry("p1", "ETH", "long", _feats(2))
    hs.log_close("p1", 12.0)
    with open(hs.path, encoding="utf-8") as f:
        f.readline()
        tail = f.readline().strip().split(",")
        assert tail[-3] == "realized"
        assert tail[-2] == "0"        # un-flagged live close = conviction
        assert tail[-1] == "entered"  # a live row IS an entered trade


# ---- average uniqueness ----------------------------------------------------
def _uniq_cfg(**over):
    cfg = {"uniqueness_enabled": True, "uniqueness_grid_sec": 300,
           "uniqueness_floor": 0.0}
    cfg.update(over)
    return cfg


def test_overlapping_rows_share_weight(tmp_path, monkeypatch):
    hs = _store(tmp_path)
    # three fully-overlapping BTC candidates + one disjoint one
    _freeze(monkeypatch, 3_000.0)
    for i in range(3):
        hs._append_row(f"o{i}", "BTC", "long", _feats(10 + i), 1, 0.0,
                       "candidate", signal_ts=0.0)
    _freeze(monkeypatch, 103_000.0)
    hs._append_row("solo", "BTC", "long", _feats(20), 1, 0.0, "candidate",
                   signal_ts=100_000.0)
    _freeze(monkeypatch, 103_000.0)          # load "now" = last write
    X, y, w = hs.load_training_data(half_life_days=1e6,
                                    weights_cfg=_uniq_cfg())
    assert len(w) == 4
    solo, others = w[-1], w[:-1]             # sig-sorted: solo is newest
    for wv in others:
        assert wv == pytest.approx(solo / 3.0, rel=1e-6)


def test_uniqueness_off_keeps_equal_weights(tmp_path, monkeypatch):
    hs = _store(tmp_path)
    _freeze(monkeypatch, 3_000.0)
    for i in range(3):
        hs._append_row(f"o{i}", "BTC", "long", _feats(30 + i), 1, 0.0,
                       "candidate", signal_ts=0.0)
    X, y, w = hs.load_training_data(half_life_days=1e6, weights_cfg=None)
    assert np.allclose(w, w[0])


def test_uniqueness_floor_bounds_the_discount(tmp_path, monkeypatch):
    hs = _store(tmp_path)
    # 10 fully-overlapped rows + 1 solo: raw uniqueness gives the cluster
    # 1/10 vs solo 1.0 (10x); floor=0.5 bounds the cluster discount to 2x.
    _freeze(monkeypatch, 3_000.0)
    for i in range(10):
        hs._append_row(f"d{i}", "BTC", "long", _feats(40 + i), 1, 0.0,
                       "candidate", signal_ts=0.0)
    _freeze(monkeypatch, 103_000.0)
    hs._append_row("solo", "BTC", "long", _feats(55), 1, 0.0, "candidate",
                   signal_ts=100_000.0)
    _freeze(monkeypatch, 103_000.0)
    X, y, w_fl = hs.load_training_data(
        half_life_days=1e6, weights_cfg=_uniq_cfg(uniqueness_floor=0.5))
    X, y, w_raw = hs.load_training_data(
        half_life_days=1e6, weights_cfg=_uniq_cfg())
    # sig-sorted: solo is last
    assert w_raw[-1] == pytest.approx(10.0 * w_raw[0], rel=1e-6)
    assert w_fl[-1] == pytest.approx(2.0 * w_fl[0], rel=1e-6)


def test_corrections_preserve_total_weight_mass(tmp_path, monkeypatch):
    hs = _store(tmp_path)
    _freeze(monkeypatch, 3_000.0)
    for i in range(6):
        hs._append_row(f"m{i}", "BTC", "long", _feats(80 + i), i % 2, 0.0,
                       "candidate", signal_ts=0.0,
                       barrier="time" if i % 2 == 0 else "sl")
    _freeze(monkeypatch, 3_000.0)
    X, y, w_off = hs.load_training_data(half_life_days=1e6, weights_cfg=None)
    X, y, w_on = hs.load_training_data(
        half_life_days=1e6,
        weights_cfg=_uniq_cfg(time_barrier_zero_weight=0.5))
    # redistribution, not shrinkage: same total loss mass either way
    assert np.sum(w_on) == pytest.approx(np.sum(w_off), rel=1e-9)


def test_different_assets_do_not_share_concurrency(tmp_path, monkeypatch):
    hs = _store(tmp_path)
    _freeze(monkeypatch, 3_000.0)
    hs._append_row("a", "BTC", "long", _feats(50), 1, 0.0, "candidate",
                   signal_ts=0.0)
    hs._append_row("b", "ETH", "long", _feats(51), 1, 0.0, "candidate",
                   signal_ts=0.0)
    X, y, w = hs.load_training_data(half_life_days=1e6,
                                    weights_cfg=_uniq_cfg())
    # same window but different assets -> both fully unique
    assert w[0] == pytest.approx(w[1], rel=1e-6)
    assert hs.last_load_stats["mean_uniqueness"] == pytest.approx(1.0)


# ---- time-barrier zeros ----------------------------------------------------
def test_time_barrier_zero_downweighted_vs_stop_zero(tmp_path, monkeypatch):
    hs = _store(tmp_path)
    _freeze(monkeypatch, 1_000.0)
    hs._append_row("tz", "BTC", "long", _feats(60), 0, 0.0, "candidate",
                   signal_ts=500.0, barrier="time")
    hs._append_row("sz", "ETH", "long", _feats(61), 0, 0.0, "candidate",
                   signal_ts=500.0, barrier="sl")
    hs._append_row("tw", "SOL", "long", _feats(62), 1, 0.0, "candidate",
                   signal_ts=500.0, barrier="time")   # label=1: untouched
    cfg = {"time_barrier_zero_weight": 0.5}
    X, y, w = hs.load_training_data(half_life_days=1e6, weights_cfg=cfg)
    by = {pid: wv for pid, wv in zip(["tz", "sz", "tw"], w)}
    assert by["tz"] == pytest.approx(0.5 * by["sz"], rel=1e-6)
    assert by["tw"] == pytest.approx(by["sz"], rel=1e-6)


def test_legacy_rows_without_barrier_keep_full_weight(tmp_path, monkeypatch):
    hs = _store(tmp_path)
    _freeze(monkeypatch, 1_000.0)
    hs._append_row("z1", "BTC", "long", _feats(70), 0, 0.0, "candidate",
                   signal_ts=500.0)                    # barrier "" (legacy)
    hs._append_row("z2", "ETH", "long", _feats(71), 0, 0.0, "candidate",
                   signal_ts=500.0, barrier="sl")
    X, y, w = hs.load_training_data(
        half_life_days=1e6, weights_cfg={"time_barrier_zero_weight": 0.5})
    assert w[0] == pytest.approx(w[1], rel=1e-6)


# ---- ML-074 one-sided-batch detector ---------------------------------------
def _skew_cfg():
    return {"prior_skew_window_h": 24, "prior_skew_min_rows": 30,
            "prior_skew_threshold": 0.25}


def test_prior_skew_flags_one_sided_recent_batch(tmp_path, monkeypatch):
    hs = _store(tmp_path)
    day = 86_400.0
    # older balanced corpus (10 days back)
    _freeze(monkeypatch, 100 * day)
    for i in range(60):
        hs._append_row(f"old{i}", "BTC", "long", _feats(100 + i), i % 2,
                       0.0, "candidate", signal_ts=100 * day - 300)
    # recent all-zero batch inside the window
    _freeze(monkeypatch, 110 * day)
    for i in range(35):
        hs._append_row(f"new{i}", "BTC", "long", _feats(200 + i), 0,
                       0.0, "candidate", signal_ts=110 * day - 300)
    hs.load_training_data(half_life_days=1e6, weights_cfg=_skew_cfg())
    st = hs.last_load_stats
    assert st["prior_skew"] is True
    assert st["prior_recent"] == pytest.approx(0.0)
    assert st["prior_overall"] == pytest.approx(30 / 95, abs=0.01)


def test_prior_skew_quiet_when_recent_batch_is_balanced(tmp_path, monkeypatch):
    hs = _store(tmp_path)
    day = 86_400.0
    _freeze(monkeypatch, 100 * day)
    for i in range(60):
        hs._append_row(f"old{i}", "BTC", "long", _feats(300 + i), i % 2,
                       0.0, "candidate", signal_ts=100 * day - 300)
    _freeze(monkeypatch, 110 * day)
    for i in range(35):
        hs._append_row(f"new{i}", "BTC", "long", _feats(400 + i), i % 2,
                       0.0, "candidate", signal_ts=110 * day - 300)
    hs.load_training_data(half_life_days=1e6, weights_cfg=_skew_cfg())
    assert hs.last_load_stats["prior_skew"] is False


# ---- clean-live count for the evidence gate --------------------------------
def test_last_load_stats_live_clean_counts_only_clean_live(tmp_path,
                                                           monkeypatch):
    hs = _store(tmp_path)
    _freeze(monkeypatch, 1_000.0)
    hs.log_entry("p1", "BTC", "long", _feats(500))
    hs.log_close("p1", 5.0)                              # clean live row
    hs._append_row("c1", "ETH", "long", _feats(501), 0, 0.0, "candidate",
                   signal_ts=500.0)
    hs.load_training_data(weights_cfg={})
    assert hs.last_load_stats["live_clean"] == 1
    assert hs.last_load_stats["rows"] == 2
