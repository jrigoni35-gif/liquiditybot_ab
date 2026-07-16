"""tests/test_candidate_exit_policy_wiring.py — the candidate labeler uses the
exit-policy replay and labels EARLY on a resolved outcome.

Two coupled guarantees:
  * with an ExitPolicy + label_mode=exit_policy, a candidate is labeled by the
    live-policy replay (the geometry flip), and
  * a candidate that RESOLVES inside the available window (e.g. a stop-out) is
    labeled immediately via BarrierOutcome.final — not held for the full 96-bar
    (8-hour) horizon. The tight 4σ/2% stop resolves far sooner than the legacy
    8σ barrier, which is what unblocks the "open candidates never turn into
    labels" backlog.
"""
import json
from pathlib import Path

import numpy as np

from ml.features import FEATURE_NAMES
from ml.history import CandidateLabeler, HistoryStore
from ml.labeling import ExitPolicy

_CFG = json.loads((Path(__file__).resolve().parents[1] / "config.json")
                  .read_text(encoding="utf-8"))


def _labeler(tmp_path, mode, with_policy=True):
    store = HistoryStore(str(tmp_path / "hist.csv"))
    ml = {"label_max_bars": 96, "label_mode": mode, "label_include_spread": False}
    pol = ExitPolicy.from_config(_CFG) if with_policy else None
    return store, CandidateLabeler(store, ml, exit_policy=pol)


def _candle(t, price, hi, lo):
    return {"time": t, "close": price, "high": hi, "low": lo, "volume": 1.0}


def _rows(store):
    if not store.path.exists():
        return []
    import csv
    with open(store.path) as f:
        return [r for r in csv.DictReader(f)]


def test_exit_policy_mode_is_selected_when_policy_present():
    _, lab = _labeler(Path("/tmp"), "exit_policy")
    assert lab.label_mode == "exit_policy" and lab.exit_policy is not None


def test_falls_back_to_barrier_without_a_policy():
    _, lab = _labeler(Path("/tmp"), "exit_policy", with_policy=False)
    assert lab.label_mode == "triple_barrier"     # no policy -> safe fallback


def test_stopout_candidate_labels_early_not_after_full_horizon(tmp_path):
    store, lab = _labeler(tmp_path, "exit_policy")
    feats = np.zeros(len(FEATURE_NAMES))
    # entry bar t=0 @100, then a -5% dip that breaches the 4σ/2% hard stop
    lab.update_candles("ETH", [_candle(0, 100.0, 100.0, 100.0)])
    lab.register("ETH", "long", feats, sigma_bar=0.005, bar_time=0)
    # only a handful of bars available (far below the 96-bar horizon)
    lab.update_candles("ETH", [_candle(1, 99.0, 100.2, 98.0),
                               _candle(2, 95.5, 99.0, 95.0),   # -5% low: stop
                               _candle(3, 96.0, 96.5, 95.5)])
    written = lab.poll()
    rows = _rows(store)
    assert written == 1, "a resolved stop-out must label EARLY, not wait 8h"
    assert len(rows) == 1 and rows[0]["source"] == "candidate"
    assert rows[0]["label"] == "0"                # stop-out -> loss
