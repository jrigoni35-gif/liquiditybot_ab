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
    # gate-truth instrumentation T2 (2026-07-28) appended 7 sg_* columns
    # after sl_frac - every index below shifts left by 7.
    assert "barrier" in header and row[header.index("barrier")] == "time"
    assert "probe" in header and row[header.index("probe")] == ""   # candidates: unmarked
    assert "disp" in header and row[header.index("disp")] == ""    # no pipeline verdict
    assert "candidate_id" in header and row[header.index("candidate_id")] == ""  # no lineage set
    assert "book" in header and row[header.index("book")] == "5m"  # default book
    # label_era joined 2026-07-26 (label-era instrumentation): derived
    # from THIS row's own barrier="time" -> exit_sim (see label_era_of)
    assert "label_era" in header and row[header.index("label_era")] == "exit_sim"
    # pt_frac, sl_frac joined 2026-07-27 (geometry-alignment T3): this
    # call never supplies a bracket -> the documented 0.0 default
    assert "pt_frac" in header and row[header.index("pt_frac")] == "0.000000"
    assert "sl_frac" in header and row[header.index("sl_frac")] == "0.000000"
    # sg_flow..sg_conc joined 2026-07-28 (gate-truth instrumentation T2):
    # this call never supplies gate_components -> the documented 0.0 default
    _sg = ["sg_flow", "sg_delta", "sg_accum", "sg_burst",
           "sg_trend", "sg_evidence", "sg_conc"]
    _i = header.index("sg_flow")
    assert header[_i:_i + 7] == _sg
    assert row[_i:_i + 7] == ["0.0000"] * 7
    # entry_price/exit_price (2026-08-04) trail the sg_* block; the
    # avail_* flags (41b, 2026-08-08) trail THOSE - anchor by name.
    _ip = header.index("entry_price")
    assert header[_ip:_ip + 2] == ["entry_price", "exit_price"]
    assert row[_ip:_ip + 2] == ["0", "0"]  # candidate path: no price supplied
    assert header[-1] == "control_arm"   # schema 95 (2026-08-27, sandbox)
    assert header[-2] == "label_ret_pct"   # schema 94 (2026-08-24)
    assert header[-6:-2] == ["avail_web", "avail_equity", "avail_options",
                           "quotes_frozen"]
    assert row[-6:-1] == ["", "", "", "", ""]  # unmeasured -> blank UNKNOWN
    # (4 avail flags + label_ret_pct, all UNKNOWN on this path)
    # control_arm is NEVER blank for a new row (asset + signal_ts=999_000.0
    # are always present) - computed through the real function, not a
    # hardcoded hash literal.
    assert row[-1] == ("1" if mh._control_arm_tag("BTC", 999_000.0)
                       else "0")


def test_live_close_writes_realized_barrier(tmp_path, monkeypatch):
    hs = _store(tmp_path)
    _freeze(monkeypatch, 1_000_000.0)
    hs.log_entry("p1", "ETH", "long", _feats(2))
    hs.log_close("p1", 12.0)
    with open(hs.path, encoding="utf-8") as f:
        hdr = f.readline().strip().split(",")
        tail = f.readline().strip().split(",")
        # Indexed BY NAME, not by position. These were negative indices
        # off the end of the row, so every trailing-column addition broke
        # them and had to renumber the block (the 2026-07-28 sg_* batch
        # shifted all of them by 7; entry_price/exit_price on 2026-08-04
        # would have shifted them again). Name lookup is immune.
        assert tail[hdr.index('barrier')] == "realized"
        assert tail[hdr.index('probe')] == "0"        # un-flagged live close = conviction
        assert tail[hdr.index('disp')] == "entered"  # a live row IS an entered trade
        assert tail[hdr.index('candidate_id')] == ""         # no matching candidate -> no lineage
        assert tail[hdr.index('book')] == "5m"       # default book
        # label_era joined 2026-07-26: barrier="realized" -> exit_sim
        assert tail[hdr.index('label_era')] == "exit_sim"
        # pt_frac, sl_frac joined 2026-07-27 (geometry-alignment T3): a
        # live close never supplies a bracket -> the documented 0.0 default
        assert tail[hdr.index('pt_frac')] == "0.000000"
        assert tail[hdr.index('sl_frac')] == "0.000000"
        # sg_flow..sg_conc joined 2026-07-28 (gate-truth instrumentation
        # T2): a live close never supplies gate_components -> the
        # documented 0.0 default
        _i2 = hdr.index("sg_flow")
        assert tail[_i2:_i2 + 7] == ["0.0000"] * 7
        # price pair joined 2026-08-04; avail_* joined 2026-08-08 (41b) and
        # now trail it - name-anchored like everything above
        _ip = hdr.index("entry_price")
        assert tail[_ip:_ip + 2] == ["0", "0"]  # live close: no price yet
        # a caller that never measured availability writes blank UNKNOWN
        # (4 avail flags + label_ret_pct); control_arm (schema 95) is
        # NEVER blank for a new row - asset + the captured signal_ts
        # (frozen 1_000_000.0) are always present.
        assert tail[-6:-1] == ["", "", "", "", ""]
        assert tail[-1] == ("1" if mh._control_arm_tag("ETH", 1_000_000.0)
                            else "0")


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


def test_vertical_barrier_downweight_covers_triple_barrier_mode(tmp_path):
    """ml.label_mode="triple_barrier" spells the vertical barrier "tb_time"
    (ml/history.py's era-disambiguating prefix, 2026-07-26), not "time".

    The down-weight targets a POPULATION, not a spelling: per this module's
    own docstring, "price touched NEITHER profit nor stop inside the
    horizon" is a no-move and weaker evidence against the signal than a
    realized stop-out. A tb_time zero is exactly that population, so it must
    receive time_barrier_zero_weight. Matching the bare literal "time" let
    the correction silently lapse for every row written under the new label
    mode."""
    from ml.history import _VERTICAL_BARRIER_REASONS
    assert "time" in _VERTICAL_BARRIER_REASONS
    assert "tb_time" in _VERTICAL_BARRIER_REASONS, (
        "tb_time is the triple_barrier-mode vertical barrier - the same "
        "no-move population as 'time' - and must take the same down-weight")
    # a policy scratch is NOT a vertical barrier: it is "we chose not to
    # wait", not "the market did nothing" - it must stay excluded
    assert "time_stop" not in _VERTICAL_BARRIER_REASONS

# ---- Kish effective sample size (Debate-1 item D, report-only) -------------
def test_kish_ess_reported_beside_uniqueness(tmp_path, monkeypatch):
    """ESS = (sum w)^2 / sum(w^2) over the FINAL weights, in
    last_load_stats. Equal weights -> ESS == n; concentration -> ESS < n."""
    hs = _store(tmp_path)
    _freeze(monkeypatch, 3_000.0)
    for i in range(5):
        hs._append_row(f"k{i}", "BTC", "long", _feats(60 + i), i % 2, 0.0,
                       "candidate", signal_ts=0.0)
    _freeze(monkeypatch, 3_000.0)
    X, y, w = hs.load_training_data(half_life_days=1e6,
                                    weights_cfg=_uniq_cfg())
    ess = hs.last_load_stats["ess_kish"]
    manual = float(np.sum(w)) ** 2 / float(np.sum(np.asarray(w) ** 2))
    assert ess == pytest.approx(manual, abs=0.05)
    assert 0.0 < ess <= len(w) + 1e-9


def test_price_anchor_reaches_the_candidate_row(tmp_path):
    """entry_price/exit_price must carry REAL prices on a labeled
    candidate - the columns existing with permanent zeros would be the
    original defect (no price anywhere) wearing a new header."""
    import numpy as np
    from ml.features import FEATURE_NAMES
    from ml.history import CandidateLabeler, HistoryStore
    hs = HistoryStore(str(tmp_path / "h.csv"))
    cl = CandidateLabeler(hs, {"label_mode": "triple_barrier",
                               "label_max_bars": 4})
    f = np.zeros(len(FEATURE_NAMES))
    cl.register("ETH", "long", f, 0.01, 1000)
    # bar series via the real feed seam: entry bar close=100, then a
    # straight run through the profit barrier so the label resolves
    # inside the window
    cl.update_candles("ETH", [
        {"time": t, "close": c, "high": c * 1.001, "low": c * 0.999}
        for t, c in [(1000, 100.0), (1300, 101.0), (1600, 108.0),
                     (1900, 109.0), (2200, 109.5), (2500, 109.5)]])
    assert cl.poll() >= 1
    import csv
    with open(hs.path, encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    r = rows[-1]
    assert float(r["entry_price"]) == 100.0, r["entry_price"]
    assert float(r["exit_price"]) > 0.0, "exit price must be real, not 0"
