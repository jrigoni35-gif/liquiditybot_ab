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
from ml.history import CandidateLabeler, HistoryStore
from ml.monitor import ModelMonitor


def _labeler(tmp_path, cap):
    store = HistoryStore(str(tmp_path / "hist.csv"))
    lab = CandidateLabeler(store, {"exploration": {}})
    lab.max_candidates = cap
    return lab


def test_eviction_keeps_the_ripest_candidate(tmp_path):
    lab = _labeler(tmp_path, cap=3)
    feats = np.zeros(58)
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


def test_first_challenger_must_still_beat_a_coin():
    mon = ModelMonitor({})
    assert mon.champion_brier >= 0.25          # no champion yet
    assert not mon.should_deploy(0.26), \
        "worse-than-coin challenger must NOT ship as first champion"
    assert mon.should_deploy(0.22)             # honest first model ships
