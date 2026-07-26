"""tests/test_feature_stability.py — T3.1 dead-list stability screen.

Pins scripts/feature_stability.py's behavior on a small SYNTHETIC corpus
(not the real ~4.7k-row history — feature_dof_report fits one GBT per
combo, so real-corpus coverage happens once, live, in the operator run):
the regime-one-hot exemption, the intersection/union/flip math, no-
overwrite snapshot naming, determinism, and the cross-date persistence /
candidate-prune-list rules. Kept to 2 seeds x 1 n_splits and small row
counts throughout so the whole file runs in well under a minute.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.feature_stability import (                # noqa: E402
    _parse_int_list, _unique_stem, compute_candidate_prune_list,
    compute_persistence, compute_snapshot, load_corpus, load_prior_snapshots,
    render_markdown, run_snapshot)

SEEDS = [7, 11]
N_SPLITS = [4]
LABEL_SPAN = 10


def _synthetic_corpus(n: int = 400, seed: int = 3, d_noise: int = 2):
    """regime_bull_quiet / regime_range held constant-zero (simulating the
    live corpus's near-single-regime coverage — shuffling a constant
    column is a no-op, so its permutation-importance drop is EXACTLY 0.0
    in every combo, regardless of model/seed: a model-independent
    guarantee these two columns test as dead every time). sig_0/sig_1
    carry the planted logit; sig_2/sig_3 and the noise columns carry
    none."""
    rng = np.random.default_rng(seed)
    names = (["regime_bull_quiet", "regime_range",
             "sig_0", "sig_1", "sig_2", "sig_3"]
            + [f"noise_{i}" for i in range(d_noise)])
    d = len(names)
    X = np.zeros((n, d))
    live = rng.normal(size=(n, d - 2))
    X[:, 2:] = live
    logit = 0.6 * X[:, 2] + 1.5 * X[:, 3] * (X[:, 4] > 0) - 0.3
    y = (rng.random(n) < 1 / (1 + np.exp(-logit))).astype(float)
    return X, y, names


@pytest.fixture(scope="module")
def synth_snapshot():
    X, y, names = _synthetic_corpus()
    return compute_snapshot(X, y, names, SEEDS, N_SPLITS,
                            label_span=LABEL_SPAN, corpus_rows=len(X),
                            n_live=len(X))


# ---------------------------------------------------------------- exemption
def test_regime_one_hots_are_structurally_dead_in_every_raw_combo(
        synth_snapshot):
    for combo in synth_snapshot["combos"]:
        assert "regime_bull_quiet" in combo["dead"], combo
        assert "regime_range" in combo["dead"], combo


def test_regime_one_hots_excluded_from_aggregate_sets(synth_snapshot):
    for name in ("regime_bull_quiet", "regime_range"):
        assert name not in synth_snapshot["always_dead"]
        assert name not in synth_snapshot["ever_dead"]
        assert name not in synth_snapshot["flip_features"]
    assert set(synth_snapshot["regime_one_hots_excluded"]) == {
        "regime_bull_quiet", "regime_range"}


# ----------------------------------------------------------------- math
def test_intersection_union_flip_math(synth_snapshot):
    always = set(synth_snapshot["always_dead"])
    ever = set(synth_snapshot["ever_dead"])
    flip = set(synth_snapshot["flip_features"])
    assert always <= ever
    assert flip == ever - always
    expected_ratio = round(len(always) / len(ever), 4) if ever else 1.0
    assert synth_snapshot["stability_ratio"] == expected_ratio


def test_stability_ratio_vacuous_case_is_one_not_a_crash():
    # too few rows for purged_walk_forward to yield any fold at all -> no
    # combo ever fits a model -> dead=[] everywhere -> ever_dead empty ->
    # stability_ratio must default to 1.0 (vacuously stable), never a
    # ZeroDivisionError.
    X = np.zeros((5, 2))
    y = np.array([0.0, 1.0, 0.0, 1.0, 0.0])
    snap = compute_snapshot(X, y, ["a", "b"], [7], [4], label_span=1)
    assert snap["ever_dead"] == []
    assert snap["always_dead"] == []
    assert snap["stability_ratio"] == 1.0


# ------------------------------------------------------------ determinism
def test_determinism_identical_inputs_identical_dead_sets():
    X, y, names = _synthetic_corpus()
    s1 = compute_snapshot(X, y, names, SEEDS, N_SPLITS, label_span=LABEL_SPAN)
    s2 = compute_snapshot(X, y, names, SEEDS, N_SPLITS, label_span=LABEL_SPAN)
    assert s1["combos"] == s2["combos"]
    assert s1["always_dead"] == s2["always_dead"]
    assert s1["ever_dead"] == s2["ever_dead"]
    assert s1["flip_features"] == s2["flip_features"]
    assert s1["stability_ratio"] == s2["stability_ratio"]


# ------------------------------------------------------------ no-overwrite
def test_run_snapshot_never_overwrites(tmp_path, monkeypatch):
    X, y, names = _synthetic_corpus(n=200, seed=5)
    monkeypatch.setattr("scripts.feature_stability._utc_stamp",
                        lambda: "20260101-000000")
    p1_json, _p1_md, _snap1 = run_snapshot(X, y, names, [7], [4], tmp_path,
                                           label_span=LABEL_SPAN)
    before = p1_json.read_text(encoding="utf-8")
    p2_json, _p2_md, _snap2 = run_snapshot(X, y, names, [7], [4], tmp_path,
                                           label_span=LABEL_SPAN)
    assert p1_json != p2_json
    assert p1_json.exists() and p2_json.exists()
    assert p1_json.read_text(encoding="utf-8") == before
    assert p2_json.name == "stability_20260101-000000-1.json"


def test_unique_stem_increments_on_collision(tmp_path):
    (tmp_path / "stability_20260101-000000.json").write_text(
        "{}", encoding="utf-8")
    assert _unique_stem(tmp_path, "20260101-000000") == \
        "stability_20260101-000000-1"


# ------------------------------------------------------- prior-snapshot IO
def test_load_prior_snapshots_skips_corrupt(tmp_path):
    (tmp_path / "stability_20260101-000000.json").write_text(
        json.dumps({"always_dead": []}), encoding="utf-8")
    (tmp_path / "stability_20260102-000000.json").write_text(
        "{not valid json", encoding="utf-8")
    snaps = load_prior_snapshots(tmp_path)
    assert len(snaps) == 1


# ---------------------------------------------------- persistence / prune
def test_compute_candidate_prune_list_no_priors():
    current = {"always_dead": ["a", "b"]}
    assert compute_candidate_prune_list([], current) == ["a", "b"]


def test_compute_candidate_prune_list_with_priors():
    current = {"always_dead": ["a", "b", "c"]}
    prior = [{"always_dead": ["a", "c", "d"]},
             {"always_dead": ["a", "b", "c"]}]
    assert compute_candidate_prune_list(prior, current) == ["a", "c"]


def test_compute_persistence_fractions():
    current = {"always_dead": ["a", "b"]}
    prior = [{"always_dead": ["a"]}, {"always_dead": ["a", "b"]}]
    p = compute_persistence(prior, current)
    assert p["dates_considered"] == 3
    assert p["always_dead_persistence"]["a"] == 1.0
    assert p["always_dead_persistence"]["b"] == round(2 / 3, 4)


def test_persistence_and_candidate_prune_list_wired_through_run_snapshot(
        tmp_path, monkeypatch):
    prior1 = {"always_dead": ["noise_0", "noise_1", "sig_2"],
             "generated_utc": "20260101-000000"}
    prior2 = {"always_dead": ["noise_0", "sig_2", "sig_3"],
             "generated_utc": "20260102-000000"}
    (tmp_path / "stability_20260101-000000.json").write_text(
        json.dumps(prior1), encoding="utf-8")
    (tmp_path / "stability_20260102-000000.json").write_text(
        json.dumps(prior2), encoding="utf-8")

    X, y, names = _synthetic_corpus(n=200, seed=9)
    monkeypatch.setattr("scripts.feature_stability._utc_stamp",
                        lambda: "20260103-000000")
    _json_path, _md_path, snap = run_snapshot(
        X, y, names, [7], [4], tmp_path, label_span=LABEL_SPAN)

    assert snap["prior_snapshot_count"] == 2
    assert "persistence" in snap
    assert snap["persistence"]["dates_considered"] == 3
    expected = (set(snap["always_dead"])
               & set(prior1["always_dead"]) & set(prior2["always_dead"]))
    assert set(snap["candidate_prune_list"]) == expected


# ------------------------------------------------------------------- misc
def test_parse_int_list():
    assert _parse_int_list("7,11,13") == [7, 11, 13]
    assert _parse_int_list("4, 5, 6") == [4, 5, 6]


def test_render_markdown_contains_sections(synth_snapshot):
    snap = dict(synth_snapshot)
    snap["generated_utc"] = "20260101-000000"
    snap["candidate_prune_list"] = []
    md = render_markdown(snap)
    assert "# Feature-stability screen" in md
    assert "always_dead" in md
    assert "Candidate prune list" in md


class _FakeStore:
    def __init__(self, path):
        self.path = path
        self.last_load_stats = {"live_clean": 42}

    def load_training_data(self, return_sig=True, weights_cfg=None):
        n = 5
        X = np.zeros((n, 3))
        y = np.zeros(n)
        sig = np.arange(n, dtype=float)
        return X, y, None, sig

    def source_counts(self):
        return {"live": 42}


def test_load_corpus_below_floor_returns_none(tmp_path):
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(json.dumps(
        {"ml": {"history_path": "x", "sample_weights": {}}}),
        encoding="utf-8")
    X, _y, _sig, rows, n_live = load_corpus(
        str(cfg_path), min_rows=100, store_factory=_FakeStore)
    assert X is None
    assert rows == 5
    assert n_live == 0


def test_load_corpus_above_floor_returns_data(tmp_path):
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(json.dumps(
        {"ml": {"history_path": "x", "sample_weights": {}}}),
        encoding="utf-8")
    X, _y, _sig, rows, n_live = load_corpus(
        str(cfg_path), min_rows=1, store_factory=_FakeStore)
    assert X is not None
    assert rows == 5
    assert n_live == 42
