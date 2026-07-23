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


def test_synthetic_candidate_never_clashes_with_its_real_live_twin(tmp_path):
    """A taken trade is written twice - a live row (realized label) and the
    candidate it was registered as (barrier counterfactual), IDENTICAL
    features. Training on both double-counts the signal and can teach a
    coin-flip when the two labels disagree. load_training_data must drop the
    synthetic twin (real label wins) while keeping every UNTAKEN candidate
    fully usable."""
    store = HistoryStore(str(tmp_path / "h.csv"))
    taken = np.arange(len(FEATURE_NAMES), dtype=float)           # signal that
    # ...was TAKEN: live realized loss (0) AND its candidate barrier win (1)
    store._append_row("live1", "BTC", "long", taken, 0, -4.0, "live",
                      signal_ts=1000.0)
    store._append_row("cand-x", "BTC", "long", taken, 1, 0.0, "candidate",
                      signal_ts=1000.0)                          # the CLASH
    # an UNTAKEN signal: candidate only, distinct features - must survive
    untaken = taken + 500.0
    store._append_row("cand-y", "ETH", "short", untaken, 1, 0.0, "candidate",
                      signal_ts=2000.0)

    X, y, w = store.load_training_data(candidate_weight=0.4)
    assert len(X) == 2, "the synthetic twin of the live trade must be dropped"
    # the taken signal survives exactly ONCE, with the REAL (realized) label
    taken_rows = [i for i in range(len(X)) if np.allclose(X[i], taken)]
    assert len(taken_rows) == 1
    assert y[taken_rows[0]] == 0.0, "realized label wins over the barrier"
    # the untaken candidate is still there, still usable (candidate weight)
    untaken_rows = [i for i in range(len(X)) if np.allclose(X[i], untaken)]
    assert len(untaken_rows) == 1
    assert y[untaken_rows[0]] == 1.0
    assert w[untaken_rows[0]] < w[taken_rows[0]], \
        "surviving synthetic row keeps its down-weight; real row full weight"


def test_synthetic_twin_still_dropped_when_funding_dist_drifts_across_cycles(
        tmp_path):
    """W2-4. funding_dist (ml/features.py) is a continuous function of
    wall-clock ts, recomputed FRESH every cycle (main.py extras['ts']=now).
    register() only dedups repeats within the SAME 5m bar - so a signal
    confirmed on cycle 1 (candidate row written with feats_A) whose entry
    is deferred by a veto that clears on cycle 2+ gets a live order whose
    meta['features'] is recomputed later (feats_B != feats_A, funding_dist
    drifted). The OLD exact-6-decimal clash guard then fails to match: both
    the counterfactual candidate label and the real fill label survive as
    a near-duplicate - the exact 'coin-flip at that exact X' the guard's
    own comment warns about. Lineage (shared candidate id) must catch what
    an exact vector match cannot."""
    store = HistoryStore(str(tmp_path / "h.csv"))
    feats_a = np.arange(len(FEATURE_NAMES), dtype=float)
    feats_b = feats_a.copy()
    fd_idx = FEATURE_NAMES.index("funding_dist")
    feats_b[fd_idx] += 1e-4                       # cross-cycle clock drift

    # cycle 1: candidate registered under its own id, feats_A
    store._append_row("cand-drift-1", "BTC", "long", feats_a, 1, 0.0,
                      "candidate", signal_ts=1000.0)
    # cycle 2+: veto clears, live order fills with recomputed feats_B, but
    # threads the candidate id it descends from (W2-4 lineage join key)
    store._append_row("live-drift-1", "BTC", "long", feats_b, 0, -4.0,
                      "live", signal_ts=1000.0, candidate_id="cand-drift-1")

    X, y, w = store.load_training_data(candidate_weight=0.4)
    assert len(X) == 1, (
        "the drifted synthetic twin must still be dropped via lineage, "
        "not an exact-vector match that clock drift defeats")
    assert y[0] == 0.0, "the realized (live) label wins"


def test_untaken_candidates_are_fully_kept_when_no_live_rows_exist(tmp_path):
    """Pure-shadow phase (no trades taken yet): every candidate must load -
    the clash guard must not eat synthetic data when there's nothing real to
    clash with."""
    store = HistoryStore(str(tmp_path / "h.csv"))
    for i in range(6):
        f = np.full(len(FEATURE_NAMES), float(i))
        store._append_row(f"cand-{i}", "BTC", "long", f, i % 2, 0.0,
                          "candidate", signal_ts=1000.0 + i)
    X, y, w = store.load_training_data()
    assert len(X) == 6, "all synthetic rows kept when no real twin exists"


def test_restored_bare_ids_are_reminted_onto_the_launch_salt(tmp_path):
    """The salt makes NEW ids collision-proof, but candidates persisted by a
    pre-salt (or foreign-salt) process keep bare `cand-{seq}` ids across
    restore - and when they finally label they write that id as the row's
    position_id, colliding with a `cand-{seq}` already in signal_history.csv
    (the 2026-07-14 rollback collision). Restore must re-mint every restored
    id onto THIS launch's unique salt."""
    lab, _ = _labeler(tmp_path)
    feats = np.zeros(len(FEATURE_NAMES))
    # a snapshot from an OLD process: BARE ids, low seq (rollback-style)
    snap = {"schema_version": lab.to_dict()["schema_version"], "seq": 3,
            "bars": {}, "last_reg": {},
            "cands": [{"id": f"cand-{n}", "asset": "BTC", "direction": "long",
                       "features": list(feats), "sigma_bar": 0.01,
                       "bar_time": 1000 + n, "spread_bps": 0.0,
                       "gates_passed": {}, "labeled": False}
                      for n in (1, 2, 3)]}
    lab2, _ = _labeler(tmp_path)
    lab2.restore(snap)
    ids = [c["id"] for c in lab2._cands]
    assert len(ids) == 3
    # every restored id now carries the launch salt - none stays bare
    assert all(c["id"].startswith(f"cand-{lab2._id_salt}-") for c in lab2._cands), \
        f"restored ids not re-minted onto the salt: {ids}"
    assert not any(i in (f"cand-{n}" for n in (1, 2, 3)) for i in ids), \
        "a bare pre-salt id survived restore -> can still collide with the file"
    # a NEW registration after restore stays disjoint from the re-minted ones
    lab2.register("ETH", "short", feats, 0.01, 9999)
    all_ids = [c["id"] for c in lab2._cands]
    assert len(set(all_ids)) == len(all_ids), "re-mint + new reg must not collide"
