"""T3.6 loader seam: config-gated candidate epoch filter in
ml/history.py's load_training_data (SHIPPED OFF - config ml.epoch.
exclude_old_candidates defaults false). Extends the T3.6a report-only
--epoch-ab experiment arm (ml/overfit.py build_epoch_ab_mask, tested in
tests/test_pbo_variants.py) with a PRODUCTION-path consumer of the same
ml.epoch.candidate_cutoff_ts: when exclude_old_candidates is truthy,
CANDIDATE rows resolved before the cutoff are dropped from training.

Binding invariants under test:
  * filter OFF (default, and any epoch_cfg that doesn't turn it on) ->
    byte-identical X/y/w to no epoch_cfg at all (pin).
  * filter ON -> candidate rows resolved before cutoff are dropped;
    candidate rows resolved at/after cutoff survive.
  * filter ON -> LIVE rows are NEVER dropped, even when their resolve ts
    is far before the cutoff (the operator's live-rows-never rule,
    structural per ml/history.py's _row_epoch_excluded docstring - not
    merely "usually true").
  * last_load_stats["epoch_excluded"] counts exactly the dropped rows.
"""
import numpy as np

from ml.features import FEATURE_NAMES
from ml.history import HistoryStore

CUTOFF = 5000.0


def _feats(seed: float) -> np.ndarray:
    return np.full(len(FEATURE_NAMES), seed)


def _store(tmp_path):
    return HistoryStore(path=str(tmp_path / "hist.csv"))


def _write_mixed_corpus(hs, monkeypatch, history_mod):
    """4 rows spanning every (source, before/after cutoff) combination,
    none sharing a candidate_id or exact feature vector with another (so
    the SYNTHETIC-vs-REAL clash-dedup never fires and every drop/keep
    observed in these tests is attributable to the epoch filter alone)."""
    monkeypatch.setattr(history_mod.time, "time", lambda: 1000.0)   # < cutoff
    hs._append_row("cand-old", "ETH", "long", _feats(1.0), 1, 0.0,
                   "candidate", signal_ts=100.0)
    hs._append_row("live-old", "ETH", "short", _feats(2.0), 0, -3.0,
                   "live", signal_ts=200.0)
    monkeypatch.setattr(history_mod.time, "time", lambda: 9000.0)   # >= cutoff
    hs._append_row("cand-new", "BTC", "long", _feats(3.0), 1, 0.0,
                   "candidate", signal_ts=300.0)
    hs._append_row("live-new", "BTC", "short", _feats(4.0), 1, 5.0,
                   "live", signal_ts=400.0)


def test_filter_off_by_default_byte_identical(tmp_path, monkeypatch):
    import ml.history as history_mod
    hs = _store(tmp_path)
    _write_mixed_corpus(hs, monkeypatch, history_mod)

    # pin `now` for the LOAD calls too (recency-decay weight is a
    # function of wall-clock at load time - unrelated to this filter,
    # must not introduce a confounding difference between the two calls)
    monkeypatch.setattr(history_mod.time, "time", lambda: 9500.0)
    X0, y0, w0 = hs.load_training_data()
    stats0 = dict(hs.last_load_stats)

    X1, y1, w1 = hs.load_training_data(epoch_cfg=None)
    X2, y2, w2 = hs.load_training_data(
        epoch_cfg={"exclude_old_candidates": False,
                  "candidate_cutoff_ts": CUTOFF})

    assert len(X0) == 4
    assert np.array_equal(X0, X1) and np.array_equal(y0, y1) \
        and np.array_equal(w0, w1)
    assert np.array_equal(X0, X2) and np.array_equal(y0, y2) \
        and np.array_equal(w0, w2)
    assert stats0["epoch_excluded"] == 0
    assert hs.last_load_stats["epoch_excluded"] == 0


def test_filter_on_drops_old_candidate_keeps_new_candidate(
        tmp_path, monkeypatch):
    import ml.history as history_mod
    hs = _store(tmp_path)
    _write_mixed_corpus(hs, monkeypatch, history_mod)
    monkeypatch.setattr(history_mod.time, "time", lambda: 9500.0)

    X, y, w = hs.load_training_data(
        epoch_cfg={"exclude_old_candidates": True,
                  "candidate_cutoff_ts": CUTOFF})

    # 4 rows in -> cand-old dropped, the other 3 (live-old, cand-new,
    # live-new) survive
    assert len(X) == 3
    assert hs.last_load_stats["epoch_excluded"] == 1
    surviving_seeds = sorted(row[0] for row in X)
    assert 1.0 not in surviving_seeds        # cand-old excluded
    assert surviving_seeds == [2.0, 3.0, 4.0]


def test_filter_on_never_drops_live_rows_before_cutoff(tmp_path, monkeypatch):
    """THE operator's live-rows-never rule, pinned: a LIVE row resolved
    far below the cutoff must survive with the filter ON. This is the
    structural guarantee - the epoch check only ever runs inside
    load_training_data's `source == "candidate"` branch, so this must
    hold no matter how old the live row is."""
    import ml.history as history_mod
    hs = _store(tmp_path)
    monkeypatch.setattr(history_mod.time, "time", lambda: 1.0)   # far < cutoff
    hs._append_row("ancient-live", "ETH", "long", _feats(9.0), 1, 7.0,
                   "live", signal_ts=1.0)

    monkeypatch.setattr(history_mod.time, "time", lambda: 9500.0)
    X, y, w = hs.load_training_data(
        epoch_cfg={"exclude_old_candidates": True,
                  "candidate_cutoff_ts": CUTOFF})

    assert len(X) == 1, "an ancient LIVE row must survive the epoch filter"
    assert hs.last_load_stats["epoch_excluded"] == 0
    assert hs.last_load_stats["live_clean"] == 1


def test_filter_on_missing_cutoff_fails_open(tmp_path, monkeypatch):
    """Defense in depth (core/config_guard.py FATALs this combination in
    a real config before the process ever starts): a malformed epoch_cfg
    handed straight to the loader - exclude_old_candidates true with no
    candidate_cutoff_ts - must not crash and must not filter anything."""
    import ml.history as history_mod
    hs = _store(tmp_path)
    _write_mixed_corpus(hs, monkeypatch, history_mod)
    monkeypatch.setattr(history_mod.time, "time", lambda: 9500.0)

    X, y, w = hs.load_training_data(
        epoch_cfg={"exclude_old_candidates": True})

    assert len(X) == 4
    assert hs.last_load_stats["epoch_excluded"] == 0


def test_epoch_excluded_stat_counts_multiple_drops(tmp_path, monkeypatch):
    import ml.history as history_mod
    hs = _store(tmp_path)
    monkeypatch.setattr(history_mod.time, "time", lambda: 1000.0)
    for i in range(3):
        hs._append_row(f"cand-old-{i}", "ETH", "long", _feats(10.0 + i),
                       1, 0.0, "candidate", signal_ts=100.0 + i)
    monkeypatch.setattr(history_mod.time, "time", lambda: 9000.0)
    hs._append_row("cand-new", "ETH", "long", _feats(20.0), 1, 0.0,
                   "candidate", signal_ts=500.0)

    X, y, w = hs.load_training_data(
        epoch_cfg={"exclude_old_candidates": True,
                  "candidate_cutoff_ts": CUTOFF})

    assert len(X) == 1
    assert hs.last_load_stats["epoch_excluded"] == 3


# ---------------------------------------------------------------------------
# Whole-phase review Fix 2: clash-dedup must run BEFORE the epoch check, or
# (a) a pre-cutoff candidate that is a live row's lineage twin never reaches
# the dedup branch that populates pair_flags -> lineage_agreement collapses
# to n_pairs=0 the moment the epoch filter is on, and (b) epoch_excluded
# double-counts rows dedup would have dropped anyway, so it no longer equals
# the true number of rows the epoch filter itself removed. Both fixtures
# below use CLASHING candidate/live pairs (via candidate_id lineage) -
# test_epoch_excluded_stat_counts_multiple_drops above uses only
# non-clashing rows and structurally cannot catch either regression.
# ---------------------------------------------------------------------------
def test_epoch_filter_on_still_populates_lineage_pair_flags(
        tmp_path, monkeypatch):
    import ml.history as history_mod
    hs = _store(tmp_path)
    # every candidate/live pair appended BEFORE the cutoff - the epoch
    # filter alone would want every one of these candidate rows dropped.
    monkeypatch.setattr(history_mod.time, "time", lambda: 1000.0)
    for i in range(5):
        cid = f"cand-{i}"
        hs._append_row(cid, "ETH", "long", _feats(float(i)), 1, 0.0,
                       "candidate", signal_ts=100.0 + i)
        hs._append_row(f"live-{i}", "ETH", "long",
                       _feats(float(1000 + i)), 1, 5.0, "live",
                       signal_ts=100.0 + i, candidate_id=cid)

    monkeypatch.setattr(history_mod.time, "time", lambda: 9500.0)
    X, y, w = hs.load_training_data(
        epoch_cfg={"exclude_old_candidates": True,
                  "candidate_cutoff_ts": CUTOFF})

    la = hs.last_load_stats["lineage_agreement"]
    assert la["n_pairs"] == 5, (
        "clash-dedup must run before the epoch check so every pre-cutoff "
        "lineage-twin candidate still reaches the pair_flags branch "
        "instead of the ML-077 lineage instrument going dark")
    assert la["agreement"] == 1.0
    assert hs.last_load_stats["dropped_clash"] == 5
    # dedup caught every one of these before the epoch check ever saw
    # them - the epoch filter itself removed nothing here
    assert hs.last_load_stats["epoch_excluded"] == 0
    assert len(X) == 5   # the 5 live rows only; every candidate twin deduped


def test_epoch_excluded_counts_only_true_epoch_removals(
        tmp_path, monkeypatch):
    """epoch_excluded must equal exactly the rows the epoch filter itself
    removes - not rows clash-dedup would have dropped anyway. Mixes 2
    pre-cutoff candidates with a live lineage twin (dedup drops these),
    3 pre-cutoff candidates with NO live twin (only the epoch filter
    removes these), and 1 post-cutoff candidate (survives both)."""
    import ml.history as history_mod
    hs = _store(tmp_path)
    monkeypatch.setattr(history_mod.time, "time", lambda: 1000.0)  # < cutoff
    for i in range(2):
        cid = f"clash-{i}"
        hs._append_row(cid, "ETH", "long", _feats(float(i)), 1, 0.0,
                       "candidate", signal_ts=100.0 + i)
        hs._append_row(f"live-{i}", "ETH", "long",
                       _feats(float(1000 + i)), 1, 5.0, "live",
                       signal_ts=100.0 + i, candidate_id=cid)
    for i in range(3):
        hs._append_row(f"solo-old-{i}", "BTC", "long",
                       _feats(float(50 + i)), 1, 0.0,
                       "candidate", signal_ts=200.0 + i)
    monkeypatch.setattr(history_mod.time, "time", lambda: 9000.0)  # >= cutoff
    hs._append_row("solo-new", "SOL", "long", _feats(99.0), 1, 0.0,
                   "candidate", signal_ts=500.0)

    monkeypatch.setattr(history_mod.time, "time", lambda: 9500.0)
    X, y, w = hs.load_training_data(
        epoch_cfg={"exclude_old_candidates": True,
                  "candidate_cutoff_ts": CUTOFF})

    stats = hs.last_load_stats
    assert stats["dropped_clash"] == 2
    assert stats["lineage_agreement"]["n_pairs"] == 2
    # true epoch-filter removals: only the 3 solo pre-cutoff candidates -
    # NOT the 2 clash rows dedup already accounted for (the pre-fix bug
    # counted 5 here: 2 clash + 3 solo, because the epoch check ran first
    # and never let the clash rows reach dedup at all)
    assert stats["epoch_excluded"] == 3
    assert len(X) == 3   # 2 surviving live rows + 1 post-cutoff candidate
