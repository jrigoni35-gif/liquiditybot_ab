"""tests/test_label_era.py — label-era instrumentation (DEEP DIVE,
.superpowers/sdd/progress.md).

The training label silently pooled THREE incompatible definitions in one
corpus (blank-barrier plain triple-barrier -> exit-sim trail/realized/
sl/time -> + time_stop) with nothing recorded to tell them apart:
barrier-alone AUC 0.769 beat the 62-feature model's 0.597 because the
label largely WAS the barrier. This file pins:

  1. era assignment (label_era_of), including the exact 07-19 23:19 ->
     23:32 UTC boundary the DEEP DIVE measured — barrier-driven, not
     time-driven, so the boundary itself is irrelevant to correctness.
  2. an old corpus lacking the `label_era` column still loads (no crash,
     no migration), tagged identically to a fresh write of the same row.
  3. per-era/per-exit-reason row counts + label rates in
     last_load_stats["label_era"].
  4. the ML-080 barrier-mix drift alarm: fires on a synthetic mix shift,
     stays SILENT (not a spurious warning) on a stable mix or a too-thin
     recent window, and never touches a label/weight/row when it fires.
  5. byte-identical X/y/w whether or not the alarm fires — report-only,
     exactly like ML-074's prior-skew detector.
"""
import csv
import logging

import numpy as np
import pytest

from core.codes import Code
from ml.features import FEATURE_NAMES
from ml.history import (LABEL_ERA_EXIT_SIM, LABEL_ERA_LEGACY,
                        LABEL_ERA_TIME_STOP, LABEL_ERA_TRIPLE_BARRIER,
                        LABEL_ERA_UNKNOWN, HistoryStore, label_era_of)

_LOGGER = "liquiditybot.ml.history"


def _feats(seed):
    rng = np.random.default_rng(seed)
    return rng.normal(0.0, 1.0, len(FEATURE_NAMES))


def _store(tmp_path):
    return HistoryStore(str(tmp_path / "hist.csv"))


def _freeze(monkeypatch, t):
    import ml.history as mh
    monkeypatch.setattr(mh.time, "time", lambda: float(t))


# ---------------------------------------------------------------------
# 1. era assignment (pure function) — the barrier vocabulary IS the
#    era signature (task-label-brief.md), never a calendar cutoff.
# ---------------------------------------------------------------------

@pytest.mark.parametrize("barrier,expected", [
    ("", LABEL_ERA_LEGACY),
    (None, LABEL_ERA_LEGACY),
    ("pt", LABEL_ERA_LEGACY),           # triple_barrier()-only value
    ("trail", LABEL_ERA_EXIT_SIM),
    ("realized", LABEL_ERA_EXIT_SIM),   # live row's own hardcoded tag
    ("sl", LABEL_ERA_EXIT_SIM),
    ("time", LABEL_ERA_EXIT_SIM),
    ("tier", LABEL_ERA_EXIT_SIM),
    ("floor", LABEL_ERA_EXIT_SIM),
    ("time_stop", LABEL_ERA_TIME_STOP),
    # 2026-07-26 signal-quality task (task-signalquality-brief.md): the
    # tb_-prefixed vocabulary CandidateLabeler._label emits under
    # ml.label_mode="triple_barrier" is a self-describing, DISJOINT
    # vocabulary from the bare "pt"/"sl"/"time" above - it must tag its
    # own era, never legacy or exit_sim (this parametrize case is the
    # blocker's RED pin: it fails against any code that hasn't added
    # LABEL_ERA_TRIPLE_BARRIER + the tb_* branch in label_era_of).
    ("tb_pt", LABEL_ERA_TRIPLE_BARRIER),
    ("tb_sl", LABEL_ERA_TRIPLE_BARRIER),
    ("tb_time", LABEL_ERA_TRIPLE_BARRIER),
    ("some-future-barrier", LABEL_ERA_UNKNOWN),
])
def test_label_era_of_barrier_vocabulary(barrier, expected):
    assert label_era_of(barrier) == expected


@pytest.mark.parametrize("barrier", ["tb_pt", "tb_sl", "tb_time"])
def test_triple_barrier_vocabulary_never_collides_with_legacy_or_exit_sim(
        barrier):
    """Explicit pin (task-signalquality-brief.md's own phrasing): flipping
    ml.label_mode to triple_barrier without this fix would have re-emitted
    the SAME bare pt/sl/time strings LABEL_ERA_LEGACY/LABEL_ERA_EXIT_SIM
    already claim - a brand-new label era silently masquerading as two OLD
    ones. The tb_ prefix must keep it out of both."""
    era = label_era_of(barrier)
    assert era == LABEL_ERA_TRIPLE_BARRIER
    assert era != LABEL_ERA_LEGACY
    assert era != LABEL_ERA_EXIT_SIM


def test_era_boundary_from_deep_dive_is_barrier_driven_not_time_driven(
        tmp_path, monkeypatch):
    """The DEEP DIVE's measured boundary: blank-barrier rows stop and
    trail/realized/.../sl rows start at 2026-07-19 23:19 -> 23:32 UTC.
    A row one minute either side of that instant must be tagged by its
    OWN barrier value alone - proves the derivation is not secretly
    keyed on a calendar cutoff (which would silently mis-tag a backfill
    or replay run under a different config on some OTHER historical
    date)."""
    from datetime import datetime, timezone
    t_legacy = datetime(2026, 7, 19, 23, 19, 0,
                       tzinfo=timezone.utc).timestamp()
    t_exit_sim = datetime(2026, 7, 19, 23, 32, 0,
                          tzinfo=timezone.utc).timestamp()
    hs = _store(tmp_path)
    _freeze(monkeypatch, t_legacy)
    hs._append_row("legacy-1", "ETH", "long", _feats(1), 0, 0.0,
                   "candidate", signal_ts=t_legacy)          # barrier=""
    _freeze(monkeypatch, t_exit_sim)
    hs._append_row("exitsim-1", "ETH", "long", _feats(2), 1, 5.0,
                   "candidate", signal_ts=t_exit_sim, barrier="trail")

    with open(hs.path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    by_id = {r["position_id"]: r for r in rows}
    assert by_id["legacy-1"]["label_era"] == LABEL_ERA_LEGACY
    assert by_id["exitsim-1"]["label_era"] == LABEL_ERA_EXIT_SIM

    hs.load_training_data()
    era_stats = hs.last_load_stats["label_era"]
    assert era_stats[LABEL_ERA_LEGACY]["rows"] == 1
    assert era_stats[LABEL_ERA_EXIT_SIM]["rows"] == 1


# ---------------------------------------------------------------------
# 2. an old corpus lacking the `label_era` column still loads
# ---------------------------------------------------------------------

def test_old_corpus_without_label_era_column_loads_as_legacy(tmp_path):
    hs = _store(tmp_path)
    # schema as it existed pre-task: drop label_era AND the two
    # geometry-alignment T3 columns that joined after it (pt_frac, sl_frac)
    old_header = hs._header[:-3]
    feats = _feats(42)
    row = ["p1", "BTC", "long", *[f"{v:.6f}" for v in feats],
           1, "5.00", "candidate", "1700000000", "1700000000",
           "", "", "", "", "5m"]            # barrier="" -> legacy
    assert len(row) == len(old_header)
    with open(hs.path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(old_header)
        w.writerow(row)

    X, y, w = hs.load_training_data()        # must not raise
    assert len(X) == 1 and len(y) == 1 and len(w) == 1
    era_stats = hs.last_load_stats["label_era"]
    assert era_stats[LABEL_ERA_LEGACY]["rows"] == 1
    assert era_stats[LABEL_ERA_LEGACY]["label_rate"] == pytest.approx(1.0)
    assert "" in era_stats[LABEL_ERA_LEGACY]["by_reason"]


# ---------------------------------------------------------------------
# 3. per-era/per-exit-reason accounting: exact expected label rates
# ---------------------------------------------------------------------

def test_era_reason_stats_exact_label_rates(tmp_path, monkeypatch):
    hs = _store(tmp_path)
    _freeze(monkeypatch, 1_000_000.0)
    # 2 legacy rows (barrier=""), labels 0, 1 -> rate 0.5
    hs._append_row("leg-0", "BTC", "long", _feats(0), 0, 0.0, "candidate",
                   signal_ts=1000.0)
    hs._append_row("leg-1", "BTC", "long", _feats(1), 1, 5.0, "candidate",
                   signal_ts=1000.0)
    # 3 exit_sim "sl" rows, labels 0,0,0 -> rate 0.0
    for i in range(3):
        hs._append_row(f"sl-{i}", "BTC", "long", _feats(10 + i), 0, -3.0,
                       "candidate", signal_ts=1000.0, barrier="sl")
    # 2 exit_sim "trail" rows, labels 1,1 -> rate 1.0 (same era as sl)
    for i in range(2):
        hs._append_row(f"trail-{i}", "BTC", "long", _feats(20 + i), 1, 8.0,
                       "candidate", signal_ts=1000.0, barrier="trail")
    # 1 time_stop row, label 0 -> its own era
    hs._append_row("ts-0", "BTC", "long", _feats(30), 0, 0.0, "candidate",
                   signal_ts=1000.0, barrier="time_stop")

    hs.load_training_data()
    st = hs.last_load_stats["label_era"]

    assert st[LABEL_ERA_LEGACY] == {
        "rows": 2, "label_rate": 0.5,
        "by_reason": {"": {"rows": 2, "label_rate": 0.5}},
    }
    exit_sim = st[LABEL_ERA_EXIT_SIM]
    assert exit_sim["rows"] == 5
    assert exit_sim["label_rate"] == pytest.approx(2 / 5)
    assert exit_sim["by_reason"]["sl"] == {"rows": 3, "label_rate": 0.0}
    assert exit_sim["by_reason"]["trail"] == {"rows": 2, "label_rate": 1.0}
    assert st[LABEL_ERA_TIME_STOP] == {
        "rows": 1, "label_rate": 0.0,
        "by_reason": {"time_stop": {"rows": 1, "label_rate": 0.0}},
    }


# ---------------------------------------------------------------------
# 4. ML-080 barrier-mix drift alarm — report-only, mirrors ML-074
# ---------------------------------------------------------------------

def _mix_shift_corpus(hs, monkeypatch, n_old=60, n_new=35):
    """Baseline (day 100): n_old rows all barrier='trail'. Recent (day
    110, inside a 24h window): n_new rows all barrier='sl'. Mirrors the
    exact 60/35 shape test_sample_weights.py's ML-074 fixtures use."""
    day = 86_400.0
    _freeze(monkeypatch, 100 * day)
    for i in range(n_old):
        hs._append_row(f"old{i}", "BTC", "long", _feats(100 + i), i % 2,
                       0.0, "candidate", signal_ts=100 * day - 300,
                       barrier="trail")
    _freeze(monkeypatch, 110 * day)
    for i in range(n_new):
        hs._append_row(f"new{i}", "BTC", "long", _feats(200 + i), i % 2,
                       0.0, "candidate", signal_ts=110 * day - 300,
                       barrier="sl")


def _drift_cfg(**overrides):
    cfg = {"era_mix_drift_window_h": 24.0, "era_mix_drift_min_rows": 30,
          "era_mix_drift_tvd_threshold": 0.3}
    cfg.update(overrides)
    return cfg


def test_mix_drift_fires_on_synthetic_shift_and_emits_registered_code(
        tmp_path, monkeypatch, caplog):
    hs = _store(tmp_path)
    _mix_shift_corpus(hs, monkeypatch)
    with caplog.at_level(logging.WARNING, logger=_LOGGER):
        hs.load_training_data(half_life_days=1e6, telemetry_cfg=_drift_cfg())
    drift = hs.last_load_stats["era_mix_drift"]
    assert drift["fired"] is True
    assert drift["tvd"] == pytest.approx(60 / 95, abs=0.01)
    assert any(Code.ML_BARRIER_MIX_DRIFT.value in r.getMessage()
              for r in caplog.records)


def test_mix_drift_stays_quiet_on_stable_mix(tmp_path, monkeypatch, caplog):
    hs = _store(tmp_path)
    day = 86_400.0
    _freeze(monkeypatch, 100 * day)
    for i in range(60):
        hs._append_row(f"old{i}", "BTC", "long", _feats(300 + i), i % 2,
                       0.0, "candidate", signal_ts=100 * day - 300,
                       barrier="trail")
    _freeze(monkeypatch, 110 * day)
    for i in range(35):
        hs._append_row(f"new{i}", "BTC", "long", _feats(400 + i), i % 2,
                       0.0, "candidate", signal_ts=110 * day - 300,
                       barrier="trail")     # SAME reason -> no mix shift
    with caplog.at_level(logging.WARNING, logger=_LOGGER):
        hs.load_training_data(half_life_days=1e6, telemetry_cfg=_drift_cfg())
    drift = hs.last_load_stats["era_mix_drift"]
    assert drift["fired"] is False
    assert drift["tvd"] == pytest.approx(0.0)
    assert not any(Code.ML_BARRIER_MIX_DRIFT.value in r.getMessage()
                  for r in caplog.records)


def test_mix_drift_silent_when_recent_window_too_thin(
        tmp_path, monkeypatch, caplog):
    """Binding spec: too few rows in the recent window -> SILENT, never a
    spurious warning, even though the underlying mix (if trusted) would
    fire."""
    hs = _store(tmp_path)
    _mix_shift_corpus(hs, monkeypatch)
    with caplog.at_level(logging.WARNING, logger=_LOGGER):
        hs.load_training_data(
            half_life_days=1e6,
            telemetry_cfg=_drift_cfg(era_mix_drift_min_rows=1000))
    drift = hs.last_load_stats["era_mix_drift"]
    assert drift["fired"] is False
    assert drift["tvd"] is None
    assert not any(Code.ML_BARRIER_MIX_DRIFT.value in r.getMessage()
                  for r in caplog.records)


def test_mix_drift_firing_changes_no_label_weight_or_row_count(
        tmp_path, monkeypatch):
    """Report-only, exactly like ML-074: whether the alarm fires or not
    must never alter X/y/w."""
    hs = _store(tmp_path)
    _mix_shift_corpus(hs, monkeypatch)
    Xf, yf, wf = hs.load_training_data(
        half_life_days=1e6, telemetry_cfg=_drift_cfg())
    assert hs.last_load_stats["era_mix_drift"]["fired"] is True

    Xq, yq, wq = hs.load_training_data(
        half_life_days=1e6,
        telemetry_cfg=_drift_cfg(era_mix_drift_tvd_threshold=0.99))
    assert hs.last_load_stats["era_mix_drift"]["fired"] is False

    assert len(Xf) == len(Xq) == 95
    assert np.array_equal(Xf, Xq)
    assert np.array_equal(yf, yq)
    assert np.array_equal(wf, wq)


# ---------------------------------------------------------------------
# 5. byte-identity: this task's instrumentation never perturbs X/y/w
# ---------------------------------------------------------------------

def test_load_training_data_xyw_unchanged_by_label_era_instrumentation(
        tmp_path, monkeypatch):
    hs = _store(tmp_path)
    _freeze(monkeypatch, 1_000_000.0)
    hs.log_entry("p1", "BTC", "long", _feats(7))
    hs.log_close("p1", 5.0)                                   # live, label 1
    hs._append_row("c1", "ETH", "long", _feats(8), 0, 0.0,
                   "candidate", signal_ts=999_000.0, barrier="sl")
    hs._append_row("c2", "ETH", "long", _feats(9), 1, 4.0,
                   "candidate", signal_ts=999_000.0, barrier="trail")

    X, y, w = hs.load_training_data(half_life_days=1e6)
    assert X.shape == (3, len(FEATURE_NAMES))
    assert list(y) == [0.0, 1.0, 1.0] or sorted(y) == [0.0, 1.0, 1.0]
    # the alarm never triggers here (default cfg, tiny corpus < min_rows) -
    # confirms X/y/w is exactly what the pre-existing pipeline (feature
    # parse -> dirty guard -> recency/candidate/manip weight -> de Prado
    # corrections -> signal-time sort) would have produced on its own,
    # with the new instrumentation contributing NOTHING to the arrays.
    assert hs.last_load_stats["era_mix_drift"]["fired"] is False
    assert hs.last_load_stats["era_mix_drift"]["tvd"] is None
    # re-running is deterministic and byte-identical
    X2, y2, w2 = hs.load_training_data(half_life_days=1e6)
    assert np.array_equal(X, X2)
    assert np.array_equal(y, y2)
    assert np.array_equal(w, w2)


# ---------------------------------------------------------------------
# 6. V1 (geometry-alignment plan, task-1-brief.md / spec D6): pins the
#    era-mapping foundation later tasks build on. tb_* barrier strings
#    must route to the triple_barrier era regardless of row source (live
#    or candidate) - label_era_of is a pure function of the barrier
#    string alone, never the source column - while today's tier-policy
#    realized reasons must NOT: that is the exact live-row exclusion Task
#    5 closes by changing what live bracket closes EMIT, never by
#    bending this map.
# ---------------------------------------------------------------------

def test_tb_realized_reasons_join_the_triple_barrier_era():
    # Task 5 will make live bracket closes emit the label's own
    # vocabulary; the era map must already route those rows into
    # tb-era training regardless of row source (live or candidate).
    from ml.history import LABEL_ERA_TRIPLE_BARRIER, label_era_of
    for b in ("tb_pt", "tb_sl", "tb_time"):
        assert label_era_of(b) == LABEL_ERA_TRIPLE_BARRIER


def test_tier_policy_realized_reasons_stay_out_of_the_tb_era():
    # the V1 hole, pinned: today's tier-exit live rows are OLD-era by
    # definition of the era map - this is the exclusion Task 5 closes
    # by changing what live closes EMIT, never by bending the map.
    from ml.history import LABEL_ERA_TRIPLE_BARRIER, label_era_of
    for b in ("tier", "trail", "floor", "realized", "time_stop"):
        assert label_era_of(b) != LABEL_ERA_TRIPLE_BARRIER
