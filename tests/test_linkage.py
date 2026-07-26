"""FS-EM port: synthetic-truth recovery, determinism, refit guard, edge
shapes. Counts are EXPECTED (deterministic) counts from a planted model -
no sampling noise, so recovery tolerances are tight."""
import csv
import json

import numpy as np
import pytest

from ml.features import FEATURE_NAMES
from ml.history import HistoryStore
from ml.linkage import FellegiSunterEM, discretize_fuzzy, discretize_exact
from scripts import corpus_linkage_report


def _planted_counts(lam=0.25, n=100_000):
    # 1 fuzzy var (3 levels), 1 exact var (2 levels)
    pi_m = [np.array([0.05, 0.15, 0.80]), np.array([0.10, 0.90])]
    pi_u = [np.array([0.70, 0.20, 0.10]), np.array([0.85, 0.15])]
    est = FellegiSunterEM(1, 1, np.zeros(6))
    pats = est.patterns
    counts = np.zeros(len(pats))
    for i, g in enumerate(pats):
        pm = pi_m[0][g[0]] * pi_m[1][g[1]]
        pu = pi_u[0][g[0]] * pi_u[1][g[1]]
        counts[i] = n * (lam * pm + (1 - lam) * pu)
    return counts


def test_synthetic_truth_recovery():
    est = FellegiSunterEM(1, 1, _planted_counts(), seed=7).fit()
    assert est.converged
    assert est.lam == pytest.approx(0.25, abs=0.05)
    pats = est.patterns
    post = est.match_posterior
    # most-similar pattern (2, 1) must dominate least-similar (0, 0)
    hi = post[np.flatnonzero((pats == [2, 1]).all(axis=1))[0]]
    lo = post[np.flatnonzero((pats == [0, 0]).all(axis=1))[0]]
    assert hi > 0.9 > 0.1 > lo


def test_determinism_same_seed():
    a = FellegiSunterEM(1, 1, _planted_counts(), seed=7).fit()
    b = FellegiSunterEM(1, 1, _planted_counts(), seed=7).fit()
    assert np.array_equal(a.match_posterior, b.match_posterior)
    assert a.lam == b.lam


def test_refit_raises():
    est = FellegiSunterEM(1, 1, _planted_counts()).fit()
    with pytest.raises(RuntimeError):
        est.fit()


def test_discretizers():
    f = discretize_fuzzy(np.array([0.0, 0.1, 5.0]), near=0.05, far=1.0)
    assert f.tolist() == [2, 1, 0]
    e = discretize_exact(np.array(["ETH", "ETH"]), np.array(["ETH", "BTC"]))
    assert e.tolist() == [1, 0]


def test_exact_only_and_fuzzy_only_shapes():
    assert len(FellegiSunterEM(0, 2, np.zeros(4)).patterns) == 4
    assert len(FellegiSunterEM(2, 0, np.zeros(9)).patterns) == 9


def _row(header, **overrides):
    base = {h: "" for h in header}
    for n in FEATURE_NAMES:
        base[n] = "0.0"
    base.update(overrides)
    return [base[h] for h in header]


def _base_rows(header, t):
    """~6 live + 8 candidate rows: one exact-lineage pair (Task 3
    candidate_id join, excluded from the EM set), a handful of fuzzy
    same-asset/side/window pairs (some near-identical -> pattern (2,2),
    some far apart in time+features -> pattern (0,0)), and several rows
    deliberately excluded by the asset/side/window filters (SOL live
    with no SOL candidate, BTC-short live against BTC-long candidates,
    a same-asset/side candidate parked far outside the pairing
    window)."""
    a_feats = dict.fromkeys(FEATURE_NAMES, "1.0")
    a_feats_near = dict.fromkeys(FEATURE_NAMES, "1.01")
    far_feats = dict.fromkeys(FEATURE_NAMES, "5.0")
    return [
        # --- live rows ---
        _row(header, position_id="live-1", asset="BTC", side="long",
            label="1", source="live", ts=str(t), signal_ts=str(t),
            candidate_id="cand-1"),
        _row(header, position_id="live-2", asset="BTC", side="long",
            label="1", source="live", ts=str(t + 300),
            signal_ts=str(t + 300)),
        _row(header, position_id="live-3", asset="ETH", side="short",
            label="0", source="live", ts=str(t), signal_ts=str(t),
            **a_feats),
        _row(header, position_id="live-4", asset="ETH", side="short",
            label="1", source="live", ts=str(t + 108000),
            signal_ts=str(t + 108000)),
        _row(header, position_id="live-5", asset="SOL", side="long",
            label="1", source="live", ts=str(t), signal_ts=str(t)),
        _row(header, position_id="live-6", asset="BTC", side="short",
            label="0", source="live", ts=str(t), signal_ts=str(t)),
        # --- candidate rows ---
        _row(header, position_id="cand-1", asset="BTC", side="long",
            label="1", source="candidate", ts=str(t), signal_ts=str(t)),
        _row(header, position_id="cand-2", asset="BTC", side="long",
            label="1", source="candidate", ts=str(t + 600),
            signal_ts=str(t + 600)),
        _row(header, position_id="cand-3", asset="BTC", side="long",
            label="0", source="candidate", ts=str(t + 7200),
            signal_ts=str(t + 7200), **far_feats),
        _row(header, position_id="cand-4", asset="ETH", side="short",
            label="0", source="candidate", ts=str(t + 120),
            signal_ts=str(t + 120), **a_feats_near),
        _row(header, position_id="cand-5", asset="ETH", side="short",
            label="1", source="candidate", ts=str(t + 108100),
            signal_ts=str(t + 108100)),
        _row(header, position_id="cand-6", asset="ETH", side="long",
            label="1", source="candidate", ts=str(t), signal_ts=str(t)),
        _row(header, position_id="cand-7", asset="XRP", side="long",
            label="1", source="candidate", ts=str(t), signal_ts=str(t)),
        _row(header, position_id="cand-8", asset="BTC", side="long",
            label="1", source="candidate", ts=str(t + 400_000),
            signal_ts=str(t + 400_000)),
    ]


def _write_history(hist_path, header, rows):
    with open(hist_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def test_corpus_linkage_report_end_to_end(tmp_path):
    hist_path = tmp_path / "signal_history.csv"
    header = HistoryStore(str(hist_path))._header
    t = 1_700_000_000.0
    _write_history(hist_path, header, _base_rows(header, t))

    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(json.dumps({"ml": {
        "linkage": {"posterior_threshold": 0.9, "seed": 7}}}),
        encoding="utf-8")

    def _run(out_dir):
        rc = corpus_linkage_report.main(
            ["--config", str(cfg_path), "--history", str(hist_path),
             "--out-dir", str(out_dir)])
        assert rc == 0
        js = out_dir / "corpus_linkage_report.json"
        assert js.exists()
        assert (out_dir / "corpus_linkage_report.md").exists()
        return json.loads(js.read_text(encoding="utf-8"))

    rep = _run(tmp_path / "out1")
    for key in ("n_exact_pairs", "n_linked_pairs", "lambda",
               "agreement_linked"):
        assert key in rep
    assert rep["n_exact_pairs"] == 1        # live-1 <-> cand-1
    assert rep["n_fuzzy_pairs"] == 7        # every other same-asset/side/
                                            # window (live, candidate) pair

    rep2 = _run(tmp_path / "out2")
    assert rep == rep2                      # determinism: byte-identical json


def test_long_book_rows_excluded_from_pairing(tmp_path):
    """book=='long' rows are risk/long_book.py's own closes - a
    different trading process (patient, ladder-gated accumulation, no
    p(win)/edge signal) from the 5m scalping flow this linkage is built
    for, exactly like the exclusion ml/history.py already applies at
    load time. A long-book live row and a long-book candidate row,
    sharing an asset/side/timestamp with the existing BTC-long 5m group
    (so they'd otherwise both exact- and fuzzy-pair against it and each
    other), must land in NEITHER n_exact_pairs, the fuzzy pool, NOR the
    linked set: the report is byte-identical (pairing-wise) with or
    without them."""
    header = HistoryStore(str(tmp_path / "signal_history.csv"))._header
    t = 1_700_000_000.0
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(json.dumps({"ml": {
        "linkage": {"posterior_threshold": 0.9, "seed": 7}}}),
        encoding="utf-8")

    def _report(hist_path, out_dir):
        rc = corpus_linkage_report.main(
            ["--config", str(cfg_path), "--history", str(hist_path),
             "--out-dir", str(out_dir)])
        assert rc == 0
        rep = json.loads((out_dir / "corpus_linkage_report.json")
                         .read_text(encoding="utf-8"))
        rep.pop("history_path")   # differs by construction (different file)
        return rep

    baseline_hist = tmp_path / "baseline.csv"
    _write_history(baseline_hist, header, _base_rows(header, t))
    baseline = _report(baseline_hist, tmp_path / "out_baseline")

    # same asset/side/ts as live-1 <-> cand-1 (the exact-lineage pair)
    # and the rest of the BTC-long 5m group - would otherwise both
    # exact-pair (candidate_id join) with each other AND fuzzy-pair
    # with every existing BTC-long live/candidate row in the fixture.
    long_rows = _base_rows(header, t) + [
        _row(header, position_id="long-live-1", asset="BTC", side="long",
            label="1", source="live", ts=str(t), signal_ts=str(t),
            candidate_id="long-cand-1", book="long"),
        _row(header, position_id="long-cand-1", asset="BTC", side="long",
            label="1", source="candidate", ts=str(t), signal_ts=str(t),
            book="long"),
    ]
    long_hist = tmp_path / "with_long.csv"
    _write_history(long_hist, header, long_rows)
    with_long = _report(long_hist, tmp_path / "out_with_long")

    assert with_long == baseline
