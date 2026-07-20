"""
Regressions for three learning-pipeline defects found in the adversarial
bug hunt (all silent, all dataset-shaping):

1. CandidateLabeler eviction dropped index 0 — the candidate CLOSEST to
   its label horizon (poll() runs before register(), so the head is the
   ripest pending row). Busy signal flow at the cap evicted every
   about-to-label candidate: label starvation + quiet-hours selection
   bias. Eviction now drops the newest.
2. IsotonicCalibrator's PAV left duplicate x-knots (the "merge" comment
   had no code): np.interp over non-increasing xp yields ill-defined
   values exactly at clustered tree-model probabilities.
3. should_deploy's no-champion clause shipped ANY first challenger,
   including one worse than predicting 0.5 forever (Brier > 0.25).
"""
import numpy as np

from ml.calibration import IsotonicCalibrator
from ml.features import FEATURE_NAMES
from ml.history import CandidateLabeler, HistoryStore
from ml.monitor import ModelMonitor


def _labeler(tmp_path, cap):
    store = HistoryStore(str(tmp_path / "hist.csv"))
    lab = CandidateLabeler(store, {"exploration": {}})
    lab.max_candidates = cap
    return lab


def test_eviction_keeps_the_ripest_candidate(tmp_path):
    lab = _labeler(tmp_path, cap=3)
    feats = np.zeros(len(FEATURE_NAMES))
    for i in range(3):
        lab.register("BTC", "long", feats, 0.01, 1000 + i * 300)
    oldest = lab._cands[0]["id"]
    lab.register("ETH", "short", feats, 0.01, 2000)   # cap hit
    ids = [c["id"] for c in lab._cands]
    assert oldest in ids, "ripest (head) candidate must survive eviction"
    assert len(lab._cands) == 3
    assert lab._cands[-1]["asset"] == "ETH"           # newcomer appended


def test_isotonic_merges_duplicate_knots():
    # two clusters of identical raw p with mixed labels force PAV pools
    # sharing a right-edge x; post-fix self.x must be strictly increasing
    rng = np.random.default_rng(7)
    p = np.concatenate([np.full(15, 0.3), np.full(15, 0.7),
                        rng.uniform(0.1, 0.9, 10)])
    y = (rng.uniform(size=len(p)) < p).astype(float)
    cal = IsotonicCalibrator().fit(p, y)
    assert cal.fitted
    assert np.all(np.diff(cal.x) > 0), "duplicate x-knots must be merged"
    out = cal.transform(np.array([0.05, 0.3, 0.7, 0.95]))
    assert np.all(np.isfinite(out))
    assert np.all(np.diff(out) >= 0), "calibration must stay monotone"


def test_stale_causes_decay_instead_of_deadlocking():
    """A +bump raised by cost_overruns can block the very trades whose
    clean exits would decay it (observed live: zero entries for hours,
    causes window frozen). With no new closes for cause_stale_hours,
    each decay call must retire one cause and step the penalties down."""
    import time as _t
    mon = ModelMonitor({"cause_stale_hours": 4.0})
    for _ in range(6):
        mon.record_close(0.6, 0, True, cause="cost_overrun")
    assert mon.edge_ratio_bump > 0
    bump0, win0 = mon.edge_ratio_bump, len(mon._causes_window)
    now = _t.time()
    mon.decay_stale_causes(now + 1800)            # fresh: no-op
    assert mon.edge_ratio_bump == bump0
    mon.decay_stale_causes(now + 5 * 3600)        # stale: one step
    assert mon.edge_ratio_bump < bump0
    assert len(mon._causes_window) == win0 - 1
    for _ in range(30):                           # converges to zero
        mon.decay_stale_causes(now + 6 * 3600)
    assert mon.edge_ratio_bump == 0.0
    d = mon.to_dict()                             # ts survives restarts
    assert "last_cause_ts" in d


def test_first_challenger_must_still_beat_a_coin():
    mon = ModelMonitor({})
    assert mon.champion_brier >= 0.25          # no champion yet
    assert not mon.should_deploy(0.26), \
        "worse-than-coin challenger must NOT ship as first champion"
    assert mon.should_deploy(0.22)             # honest first model ships


def test_deploy_demands_oof_evidence_not_just_score():
    """A lucky Brier on a handful of OOF points must not crown a
    champion: when folds first survive the purge the challenger may
    carry 5-15 points, and 0.20-on-5-points is noise, not evidence."""
    mon = ModelMonitor({"deploy_min_oof": 30})
    assert not mon.should_deploy(0.15, n_oof=5), \
        "great score on 5 OOF points is luck, not evidence"
    assert not mon.should_deploy(0.15, n_oof=29)
    assert mon.should_deploy(0.15, n_oof=30)      # evidence floor met
    assert mon.should_deploy(0.15, n_oof=None)    # legacy callers: score-only
    assert not mon.should_deploy(0.26, n_oof=500) # evidence can't save a coin-loser


def test_cost_bump_applies_once_per_close_not_twice():
    """record_close() applied the cause adjustment, then _evaluate() applied
    it AGAIN. Below min_trades the Brier window is None so _evaluate early-
    returns and only one call lands - which is why every existing test (all
    < 15 closes) passed. But in production steady state (>= min_trades
    model-scored closes) BOTH fired: a cost_overrun raised edge_ratio_bump
    +0.2/close, hitting the cap in 2 closes instead of 4 and doubling the
    entry-suppression the decay exists to relieve. It must raise +0.1 once,
    identically whether or not the Brier window is full."""
    def _bump_step(prefill):
        mon = ModelMonitor({})
        if prefill:                     # fill the Brier window (no causes)
            for i in range(mon.min_trades + 3):
                mon.record_close(0.8 if i % 2 else 0.2, i % 2, True)
            assert mon._windows() is not None
        else:
            assert mon._windows() is None
        for _ in range(4):              # window n<5: no raise yet
            mon.record_close(0.8, 1, True, cause="cost_overrun")
        assert mon.edge_ratio_bump == 0.0
        mon.record_close(0.8, 1, True, cause="cost_overrun")   # n==5: 1 raise
        return round(mon.edge_ratio_bump, 4)

    cold = _bump_step(prefill=False)    # Brier window empty (cold start)
    warm = _bump_step(prefill=True)     # Brier window full (steady state)
    assert cold == 0.1, f"cold-start raise must be +0.1, got {cold}"
    assert warm == 0.1, f"full-window raise must ALSO be +0.1, got {warm}"
    assert cold == warm, "the bump must not depend on Brier-window fullness"


def test_clean_close_decays_bump_during_cold_start():
    """A raised bump must decay on clean closes even before the model trains
    - previously the decay lived only in _evaluate, which early-returns below
    min_trades, so during cold start a clean close never decayed the bump."""
    mon = ModelMonitor({})
    mon.edge_ratio_bump = 0.3
    assert mon._windows() is None                 # cold start
    mon.record_close(0.6, 1, True)                # clean close, no cause
    assert mon.edge_ratio_bump < 0.3, "clean close must decay the bump"


def test_stale_decay_seeds_clock_for_pre_upgrade_windows():
    """Restored snapshots carry a causes window but no last_cause_ts
    (0.0). The decay guard used to skip on ts<=0 - and ts stays 0 until
    a NEW close arrives, which the bump prevents: the deadlock one
    level deeper. First call must seed the clock; staleness then
    decays from there."""
    import time as _t
    mon = ModelMonitor({"cause_stale_hours": 4.0})
    mon._causes_window.extend(["cost_overrun"] * 6)
    mon.edge_ratio_bump = 0.4
    mon._last_cause_ts = 0.0                      # pre-upgrade snapshot
    now = _t.time()
    mon.decay_stale_causes(now)                   # seeds the clock
    assert mon._last_cause_ts == now
    assert mon.edge_ratio_bump == 0.4             # no decay yet
    mon.decay_stale_causes(now + 5 * 3600)        # now provably stale
    assert mon.edge_ratio_bump < 0.4
    assert len(mon._causes_window) == 5
