"""tests/test_era_exclusion.py — era-gated training exclusion (operator
decision, 2026-07-26, docs/quant/2026-07-26_era_exclusion.md).

Two operator decisions under test:
  1. exclusion covers LIVE rows too - overrides ml.epoch's "live rows
     never" term (all measured live rows are themselves old-era).
  2. threshold-armed: ships gated and inert (0 new-era rows measured at
     decision time) and auto-activates once the corpus's new-era
     (LABEL_ERA_TRIPLE_BARRIER) row count reaches ml.era_exclusion.
     min_new_era_rows - never a manual flip.

THE BOUND under test above all others: this is a LOAD-TIME VIEW ONLY.
Every row stays byte-for-byte on disk; flipping the filter off (forced_off,
or falling back below threshold) must restore the pre-exclusion training
set EXACTLY - the round-trip test below is the proof nothing is destroyed.
"""
import numpy as np

from core.codes import Code
from ml.features import FEATURE_NAMES
from ml.history import HistoryStore

_LOGGER = "liquiditybot.ml.history"


def _feats(seed: float) -> np.ndarray:
    return np.full(len(FEATURE_NAMES), seed)


def _store(tmp_path):
    return HistoryStore(path=str(tmp_path / "hist.csv"))


def _write_mixed_corpus(hs, monkeypatch, history_mod):
    """11 rows: 6 old-era (2 exit_sim/candidate, 2 legacy/live, 1
    exit_sim_time_stop/candidate, 1 unknown/candidate) + 5 new-era
    (3 triple_barrier/candidate, 2 triple_barrier/live). Every row a
    distinct feature-vector seed, no candidate_id lineage - clash-dedup
    never fires, so every drop/keep observed below is attributable to the
    era filter alone."""
    monkeypatch.setattr(history_mod.time, "time", lambda: 1000.0)
    # old-era: exit_sim / candidate (barrier in _EXIT_SIM_BARRIERS)
    hs._append_row("old-cand-0", "ETH", "long", _feats(1.0), 1, 0.0,
                   "candidate", signal_ts=100.0, barrier="sl")
    hs._append_row("old-cand-1", "ETH", "long", _feats(2.0), 0, -3.0,
                   "candidate", signal_ts=101.0, barrier="trail")
    # old-era: legacy / live (blank barrier)
    hs._append_row("old-live-0", "BTC", "short", _feats(3.0), 1, 5.0,
                   "live", signal_ts=102.0, barrier="")
    hs._append_row("old-live-1", "BTC", "short", _feats(4.0), 0, -1.0,
                   "live", signal_ts=103.0, barrier="")
    # old-era: exit_sim_time_stop / candidate
    hs._append_row("old-cand-ts", "SOL", "long", _feats(5.0), 0, 0.0,
                   "candidate", signal_ts=104.0, barrier="time_stop")
    # old-era: unknown / candidate (unrecognized barrier string)
    hs._append_row("old-cand-unk", "SOL", "short", _feats(6.0), 1, 2.0,
                   "candidate", signal_ts=105.0, barrier="some-future-barrier")
    # new-era: triple_barrier / candidate x3
    for i in range(3):
        hs._append_row(f"new-cand-{i}", "XRP", "long", _feats(10.0 + i),
                       1, 1.0, "candidate", signal_ts=110.0 + i,
                       barrier="tb_pt")
    # new-era: triple_barrier / live x2
    for i in range(2):
        hs._append_row(f"new-live-{i}", "XRP", "short", _feats(20.0 + i),
                       0, -0.5, "live", signal_ts=120.0 + i,
                       barrier="tb_sl")


# ---------------------------------------------------------------------
# 1. below threshold -> nothing excluded, byte-identical to no era_cfg
# ---------------------------------------------------------------------

def test_below_threshold_byte_identical_to_no_era_cfg(tmp_path, monkeypatch):
    import ml.history as history_mod
    hs = _store(tmp_path)
    _write_mixed_corpus(hs, monkeypatch, history_mod)
    monkeypatch.setattr(history_mod.time, "time", lambda: 9500.0)

    X0, y0, w0 = hs.load_training_data()
    stats0 = dict(hs.last_load_stats)

    X1, y1, w1 = hs.load_training_data(era_cfg=None)
    X2, y2, w2 = hs.load_training_data(
        era_cfg={"min_new_era_rows": 6})   # 5 new-era rows < 6 -> below

    assert len(X0) == 11
    assert np.array_equal(X0, X1) and np.array_equal(y0, y1) \
        and np.array_equal(w0, w1)
    assert np.array_equal(X0, X2) and np.array_equal(y0, y2) \
        and np.array_equal(w0, w2)
    ee0 = stats0["era_exclusion"]
    assert ee0 == {"armed": False, "active": False, "forced_off": False,
                  "forced_on": False, "min_new_era_rows": 150,
                  "new_era_rows": 5,
                  "excluded": {"total": 0, "by_era_source": {}}}
    ee2 = hs.last_load_stats["era_exclusion"]
    assert ee2["armed"] is False and ee2["active"] is False
    assert ee2["new_era_rows"] == 5 and ee2["min_new_era_rows"] == 6
    assert ee2["excluded"] == {"total": 0, "by_era_source": {}}


# ---------------------------------------------------------------------
# 2. at/above threshold -> every old-era row excluded, INCLUDING live
# ---------------------------------------------------------------------

def test_at_threshold_excludes_every_old_era_row_including_live(
        tmp_path, monkeypatch):
    import ml.history as history_mod
    hs = _store(tmp_path)
    _write_mixed_corpus(hs, monkeypatch, history_mod)
    monkeypatch.setattr(history_mod.time, "time", lambda: 9500.0)

    X, y, w = hs.load_training_data(era_cfg={"min_new_era_rows": 5})

    assert len(X) == 5, "only the 5 new-era rows may survive"
    surviving_seeds = sorted(row[0] for row in X)
    assert surviving_seeds == [10.0, 11.0, 12.0, 20.0, 21.0]
    ee = hs.last_load_stats["era_exclusion"]
    assert ee["armed"] is True
    assert ee["active"] is True
    assert ee["new_era_rows"] == 5
    assert ee["excluded"]["total"] == 6
    by_es = ee["excluded"]["by_era_source"]
    assert by_es["exit_sim"] == {"candidate": 2}
    assert by_es["legacy"] == {"live": 2}, (
        "THE overridden term, pinned explicitly: old-era LIVE rows must "
        "be excluded too, not just old-era candidates")
    assert by_es["exit_sim_time_stop"] == {"candidate": 1}
    assert by_es["unknown"] == {"candidate": 1}, (
        "LABEL_ERA_UNKNOWN is treated as OLD-era for exclusion purposes - "
        "an unrecognized barrier is not evidence a row is new-era "
        "(conservative reading, docs/quant/2026-07-26_era_exclusion.md)")


# ---------------------------------------------------------------------
# 3. THE round-trip proof: active, then forced off, restores baseline
# ---------------------------------------------------------------------

def test_round_trip_forced_off_restores_pre_exclusion_baseline(
        tmp_path, monkeypatch):
    import ml.history as history_mod
    hs = _store(tmp_path)
    _write_mixed_corpus(hs, monkeypatch, history_mod)
    monkeypatch.setattr(history_mod.time, "time", lambda: 9500.0)

    X0, y0, w0 = hs.load_training_data()          # baseline: no era_cfg
    assert len(X0) == 11

    X1, y1, w1 = hs.load_training_data(
        era_cfg={"min_new_era_rows": 5})           # ACTIVE: 5 rows survive
    assert len(X1) == 5

    X2, y2, w2 = hs.load_training_data(
        era_cfg={"min_new_era_rows": 5, "forced_off": True})  # ROLLBACK

    assert len(X2) == 11
    assert np.array_equal(X0, X2), "rollback must restore X exactly"
    assert np.array_equal(y0, y2), "rollback must restore y exactly"
    assert np.array_equal(w0, w2), "rollback must restore w exactly"
    ee2 = hs.last_load_stats["era_exclusion"]
    assert ee2["armed"] is True     # threshold still met...
    assert ee2["active"] is False   # ...but forced_off wins
    assert ee2["excluded"] == {"total": 0, "by_era_source": {}}


def test_csv_on_disk_unchanged_after_active_load(tmp_path, monkeypatch):
    import ml.history as history_mod
    hs = _store(tmp_path)
    _write_mixed_corpus(hs, monkeypatch, history_mod)
    monkeypatch.setattr(history_mod.time, "time", lambda: 9500.0)
    before = hs.path.read_bytes()

    X, y, w = hs.load_training_data(era_cfg={"min_new_era_rows": 5})
    assert len(X) == 5

    after = hs.path.read_bytes()
    assert before == after, (
        "exclusion is a LOAD-TIME VIEW ONLY - the file on disk must never "
        "change, regardless of whether the filter is active")


# ---------------------------------------------------------------------
# 4. forced_on: manual override, bypasses the threshold
# ---------------------------------------------------------------------

def test_forced_on_activates_below_threshold(tmp_path, monkeypatch):
    import ml.history as history_mod
    hs = _store(tmp_path)
    _write_mixed_corpus(hs, monkeypatch, history_mod)
    monkeypatch.setattr(history_mod.time, "time", lambda: 9500.0)

    X, y, w = hs.load_training_data(
        era_cfg={"min_new_era_rows": 1000, "forced_on": True})

    assert len(X) == 5      # forced active despite armed=False
    ee = hs.last_load_stats["era_exclusion"]
    assert ee["armed"] is False
    assert ee["active"] is True
    assert ee["forced_on"] is True


def test_forced_off_wins_over_forced_on(tmp_path, monkeypatch):
    """forced_off is the rollback lever and always wins - config_guard
    also FATALs this combination in a real config, but the loader itself
    must degrade safely if it's ever handed to it directly."""
    import ml.history as history_mod
    hs = _store(tmp_path)
    _write_mixed_corpus(hs, monkeypatch, history_mod)
    monkeypatch.setattr(history_mod.time, "time", lambda: 9500.0)

    X, y, w = hs.load_training_data(
        era_cfg={"min_new_era_rows": 1, "forced_on": True,
                 "forced_off": True})

    assert len(X) == 11
    assert hs.last_load_stats["era_exclusion"]["active"] is False


# ---------------------------------------------------------------------
# 5. a corpus lacking the `label_era` column still participates correctly
#    (load-time fallback via barrier - ml/history.py _row_label_era)
# ---------------------------------------------------------------------

def test_pre_task_row_without_label_era_column_still_excludable(
        tmp_path, monkeypatch):
    import csv
    import ml.history as history_mod
    hs = _store(tmp_path)
    old_header = hs._header[:-1]        # schema as it existed pre-instrumentation
    feats = _feats(42.0)
    old_row = ["p-old", "BTC", "long", *[f"{v:.6f}" for v in feats],
              1, "5.00", "candidate", "1700000000", "1700000000",
              "", "", "", "", "5m"]      # barrier="" -> legacy, no label_era col
    assert len(old_row) == len(old_header)
    with open(hs.path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(old_header)
        w.writerow(old_row)

    monkeypatch.setattr(history_mod.time, "time", lambda: 1700000100.0)
    for i in range(5):
        hs._append_row(f"new-{i}", "ETH", "long", _feats(50.0 + i), 1, 1.0,
                       "candidate", signal_ts=1700000000.0 + i,
                       barrier="tb_pt")

    X, y, w = hs.load_training_data(era_cfg={"min_new_era_rows": 5})

    assert len(X) == 5, "the column-less legacy row must be excluded via " \
        "its barrier-derived era, exactly like a persisted-column row"
    assert 42.0 not in sorted(row[0] for row in X)


# ---------------------------------------------------------------------
# 6. ML-081 activation reason code: fires once on transition, not per load
# ---------------------------------------------------------------------

def test_activation_code_fires_once_on_transition_not_per_load(
        tmp_path, monkeypatch, caplog):
    import ml.history as history_mod
    hs = _store(tmp_path)
    _write_mixed_corpus(hs, monkeypatch, history_mod)
    monkeypatch.setattr(history_mod.time, "time", lambda: 9500.0)

    with caplog.at_level("INFO", logger=_LOGGER):
        hs.load_training_data(era_cfg={"min_new_era_rows": 5})
        hs.load_training_data(era_cfg={"min_new_era_rows": 5})
        hs.load_training_data(era_cfg={"min_new_era_rows": 5})

    hits = [r for r in caplog.records
            if Code.ML_ERA_EXCLUSION_ACTIVE.value in r.message]
    assert len(hits) == 1, (
        f"expected exactly one activation log across 3 active loads, "
        f"got {len(hits)}")


def test_activation_code_relogs_after_rollback_and_rearm(
        tmp_path, monkeypatch, caplog):
    """Edge-triggered, not latched forever: OFF (rollback) then ON again
    is a NEW transition and must log again."""
    import ml.history as history_mod
    hs = _store(tmp_path)
    _write_mixed_corpus(hs, monkeypatch, history_mod)
    monkeypatch.setattr(history_mod.time, "time", lambda: 9500.0)

    with caplog.at_level("INFO", logger=_LOGGER):
        hs.load_training_data(era_cfg={"min_new_era_rows": 5})            # ON
        hs.load_training_data(
            era_cfg={"min_new_era_rows": 5, "forced_off": True})          # OFF
        hs.load_training_data(era_cfg={"min_new_era_rows": 5})            # ON again

    hits = [r for r in caplog.records
            if Code.ML_ERA_EXCLUSION_ACTIVE.value in r.message]
    assert len(hits) == 2


# ---------------------------------------------------------------------
# 7. "rows"/"live_clean" must reflect what actually feeds the fit - a
#    widely-read evidence-gate input (main.py's model_selection ladder
#    admission, scripts/overfit_check.py's and scripts/feature_stability.py's
#    n_live mirror, gc_pusher's Grafana export) must never silently disagree
#    with the training arrays this method actually returns.
# ---------------------------------------------------------------------

def test_rows_and_live_clean_reflect_post_exclusion_corpus(
        tmp_path, monkeypatch):
    import ml.history as history_mod
    hs = _store(tmp_path)
    _write_mixed_corpus(hs, monkeypatch, history_mod)
    monkeypatch.setattr(history_mod.time, "time", lambda: 9500.0)

    # inactive (below threshold): unchanged from the full-corpus count
    hs.load_training_data(era_cfg={"min_new_era_rows": 6})
    assert hs.last_load_stats["rows"] == 11
    assert hs.last_load_stats["live_clean"] == 4    # 2 old-era + 2 new-era live

    # active: both must shrink to the surviving new-era-only corpus (3
    # candidate + 2 live = 5 rows, 2 of them live)
    hs.load_training_data(era_cfg={"min_new_era_rows": 5})
    assert hs.last_load_stats["rows"] == 5
    assert hs.last_load_stats["live_clean"] == 2

    # forced off (rollback): restored to the full-corpus count exactly
    hs.load_training_data(
        era_cfg={"min_new_era_rows": 5, "forced_off": True})
    assert hs.last_load_stats["rows"] == 11
    assert hs.last_load_stats["live_clean"] == 4


def test_below_threshold_never_logs_activation(tmp_path, monkeypatch, caplog):
    import ml.history as history_mod
    hs = _store(tmp_path)
    _write_mixed_corpus(hs, monkeypatch, history_mod)
    monkeypatch.setattr(history_mod.time, "time", lambda: 9500.0)

    with caplog.at_level("INFO", logger=_LOGGER):
        hs.load_training_data(era_cfg={"min_new_era_rows": 6})

    hits = [r for r in caplog.records
            if Code.ML_ERA_EXCLUSION_ACTIVE.value in r.message]
    assert not hits
