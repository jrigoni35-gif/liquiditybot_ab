"""T2.2a divergence score: only windows containing BOTH live and candidate
labels contribute (weighted by candidate count); coverage = candidate rows
in live-covered windows / all candidate rows. Pure function + loader
capture. Report-only."""
import numpy as np
import pytest

from ml.features import FEATURE_NAMES
from ml.history import HistoryStore, sim_live_divergence


def _feats(seed):
    # _append_row's `feats` must be array-like in FEATURE_NAMES order (it
    # does np.asarray(feats, dtype=float) and writes it positionally) -
    # not a name->value dict.
    rng = np.random.default_rng(seed)
    return rng.normal(0, 1, len(FEATURE_NAMES))


def _store(tmp_path):
    return HistoryStore(path=str(tmp_path / "hist.csv"))


def test_two_windows_weighted_score_and_coverage():
    # window 0 (t<3600): live mean 1.0, cand mean 0.5, 2 cand rows
    # window 1: live mean 0.0, cand mean 0.0, 1 cand row
    # window 2: candidate-only - excluded from score, dilutes coverage
    times = [0, 10, 20, 30, 3700, 3800, 7300, 7400]
    srcs = ["live", "cand", "cand", "live", "live", "cand", "cand", "cand"]
    labels = [1.0, 1.0, 0.0, 1.0, 0.0, 0.0, 1.0, 1.0]
    d = sim_live_divergence(times, srcs, labels, 3600.0)
    assert d["windows_both"] == 2
    assert d["n_cand"] == 5
    # weighted: (0.5*2 + 0.0*1) / 3, rounded to 4 places per the score/
    # coverage rounding contract (round(1/3, 4) == 0.3333, ~3.3e-5 off
    # the untruncated 1/3 - too coarse for a 1e-9 tolerance, hence round()
    # itself as the expected value rather than the raw fraction).
    assert d["score"] == round(1.0 / 3.0, 4)
    assert d["coverage"] == pytest.approx(3 / 5)


def test_no_overlap_yields_none_score_zero_coverage():
    d = sim_live_divergence([0, 5000], ["live", "cand"], [1.0, 0.0], 3600.0)
    assert d == {"score": None, "coverage": 0.0, "windows_both": 0,
                 "n_cand": 1}


def test_empty_inputs():
    assert sim_live_divergence([], [], [], 3600.0)["score"] is None


def test_loader_captures_sim_live_divergence(tmp_path):
    store = _store(tmp_path)
    # all 4 rows share one hour-bucket (signal_ts all under 3600s of each
    # other): 2 live (labels 1.0, 0.0 -> mean 0.5), 2 candidate (labels
    # 0.0, 0.0 -> mean 0.0). hand-computed score = |0.5 - 0.0| * 2 / 2 = 0.5
    store._append_row("live-1", "ETH", "long", _feats(1), 1.0, 5.0, "live",
                      signal_ts=1000.0)
    store._append_row("live-2", "ETH", "long", _feats(2), 0.0, -5.0, "live",
                      signal_ts=1100.0)
    store._append_row("cand-1", "ETH", "long", _feats(3), 0.0, 0.0,
                      "candidate", signal_ts=1200.0)
    store._append_row("cand-2", "ETH", "long", _feats(4), 0.0, 0.0,
                      "candidate", signal_ts=1300.0)
    store.load_training_data(telemetry_cfg={"divergence_window_h": 1.0})
    div = store.last_load_stats["sim_live_divergence"]
    assert div["window_h"] == 1.0
    assert div["windows_both"] == 1
    assert div["n_cand"] == 2
    assert div["score"] == pytest.approx(0.5)
    assert div["coverage"] == pytest.approx(1.0)
