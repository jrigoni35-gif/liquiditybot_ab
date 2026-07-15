"""
Training-row integrity regressions (information-flow audit, 2026-07-15).

1. Candidate id collision: cand-{seq} reused a previously-written id after a
   filesystem rollback reset the persisted _seq while signal_history.csv kept
   its rows - two distinct signals landed under the same position_id (10 such
   pairs observed live). A per-launch salt makes ids collision-proof across
   restarts/rollbacks.
2. Non-atomic append in load_training_data: X.append ran before y/sig/w, so a
   row with valid features but a bad label cell left X one longer than y and
   the argsort(sig) reindex silently paired X row i with y row j for the whole
   tail.
"""
import csv

import numpy as np

from ml.features import FEATURE_NAMES
from ml.history import CandidateLabeler, HistoryStore


def _labeler(tmp_path):
    store = HistoryStore(str(tmp_path / "hist.csv"))
    return CandidateLabeler(store, {"exploration": {}}), store


def test_candidate_ids_survive_a_seq_reset_without_colliding(tmp_path):
    lab, _ = _labeler(tmp_path)
    feats = np.zeros(len(FEATURE_NAMES))
    for i in range(5):
        lab.register("BTC", "long", feats, 0.01, 1000 + i * 300)
    gen1 = [c["id"] for c in lab._cands]

    # simulate a filesystem-rollback restart: NEW labeler process (fresh salt),
    # restore the OLD (lower) seq, register more candidates
    snap = lab.to_dict()
    snap["seq"] = 0                                   # rolled-back seq
    lab2, _ = _labeler(tmp_path)
    lab2.restore(snap)                                # brings old cands back
    base = {c["id"] for c in lab2._cands}             # restored ids, kept as-is
    for i in range(5):                                # reset seq -> 1..5 again
        lab2.register("ETH", "short", feats, 0.01, 5000 + i * 300)
    new_ids = [c["id"] for c in lab2._cands if c["id"] not in base]

    assert len(set(gen1)) == 5 and len(new_ids) == 5
    # the reset seq (1..5) would have re-minted cand-1..5 under a bare scheme;
    # the fresh salt keeps the new ids disjoint from the pre-rollback ones
    assert not (set(new_ids) & set(gen1)), \
        f"ids collided across a seq reset: {set(new_ids) & set(gen1)}"
    assert lab._id_salt != lab2._id_salt, "each labeler gets a fresh salt"
    # the salt is NOT persisted - a restore must not resurrect the old one
    assert "id_salt" not in snap and "_id_salt" not in snap


def test_load_training_data_stays_aligned_past_a_bad_label_cell(tmp_path):
    store = HistoryStore(str(tmp_path / "h.csv"))
    feats_a = np.arange(len(FEATURE_NAMES), dtype=float)          # row A
    feats_b = feats_a + 1000.0                                    # row B (distinct)
    store._append_row("pA", "BTC", "long", feats_a, 1, 5.0, "live",
                      signal_ts=1000.0)
    store._append_row("pB", "ETH", "short", feats_b, 0, -5.0, "live",
                      signal_ts=2000.0)
    # corrupt row A's label cell in place (truncated write / hand edit)
    rows = list(csv.reader(open(store.path.as_posix())))
    li = rows[0].index("label")
    rows[1][li] = ""                                              # empty label
    with open(store.path, "w", newline="") as f:
        csv.writer(f).writerows(rows)

    X, y, w = store.load_training_data()
    # row A is dropped whole; row B survives INTACT and aligned - not shifted
    assert len(X) == len(y) == len(w) == 1
    assert y[0] == 0.0                                            # row B's label
    assert np.allclose(X[0], feats_b), \
        "surviving row's features must still pair with ITS label"
