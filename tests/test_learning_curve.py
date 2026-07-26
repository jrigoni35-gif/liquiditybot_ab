"""
scripts/learning_curve.py (T2.3, learnaccel Phase 2): time-prefix
learning-curve report over the DEPLOYED walkforward selector.

Corpora here are built through the real HistoryStore API (`_append_row`,
the same private write path tests/test_history_regime_counts.py and
tests/test_signal_time_ordering.py use directly) - never a hand-rolled
CSV. Two wrinkles a synthetic fixture must respect or the report degrades
silently instead of testing anything:

  * load_training_data's clash-dedup drops any candidate row whose
    (asset, side, feature-vector) exactly matches a live row (W2-4) - a
    corpus built from a handful of all-zero-but-one-hot feature vectors
    collides across the live/candidate split and collapses to just the
    live rows. `_feats` therefore stamps a small per-row unique value
    into ret_1_dir (kept in its [-6, 6] contract range) so every row's
    vector is distinct.
  * purged_walk_forward's res(label-resolution-time)-based purge needs
    `res <= sig[test_start]` to keep any training rows at all; `res` is
    _append_row's own wall-clock `now` at write time (not overridable),
    so signal_ts must be stamped comfortably AHEAD of "now" (never
    behind it) for every synthetic row, or every fold's train slice is
    purged to empty.
"""
import json
import sys
import time
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ml.features import FEATURE_NAMES                       # noqa: E402
from ml.history import HistoryStore                          # noqa: E402
from scripts import learning_curve                            # noqa: E402

_R1 = FEATURE_NAMES.index("ret_1_dir")
_BULL_QUIET = FEATURE_NAMES.index("regime_bull_quiet")
_BEAR = FEATURE_NAMES.index("regime_bear")
_START = time.time() + 10_000.0     # safely ahead of "now" for every row
_STEP = 300.0                       # 5-min bar cadence, strictly increasing


def _feats(i: int, regime: str) -> np.ndarray:
    f = np.zeros(len(FEATURE_NAMES))
    f[_R1] = (i % 1000) / 1000.0 * 2.0 - 1.0     # per-row uniqueness
    f[_BULL_QUIET if regime == "bull_quiet" else _BEAR] = 1.0
    return f


def _build_corpus(path: Path, n: int, n_live: int) -> None:
    """n rows total, sig-ascending; alternating label 0/1, alternating
    regime bull_quiet/bear every 2 rows; the LAST n_live rows are
    source='live' with probe alternating '1'/'0', the rest 'candidate'."""
    store = HistoryStore(str(path))
    for i in range(n):
        sig_ts = _START + i * _STEP
        label = i % 2
        regime = "bull_quiet" if (i // 2) % 2 == 0 else "bear"
        feats = _feats(i, regime)
        if i >= n - n_live:
            probe = "1" if i % 2 == 0 else "0"
            store._append_row(
                f"live-{i}", "BTC", "long", feats, label,
                10.0 if label else -10.0, "live", signal_ts=sig_ts,
                barrier="realized", probe=probe, disp="entered")
        else:
            store._append_row(
                f"cand-{i}", "BTC", "long", feats, label, 0.0,
                "candidate", signal_ts=sig_ts, barrier="profit", probe="")


def _write_config(path: Path, **ml_overrides) -> None:
    cfg = {"ml": {"label_max_bars": 96, "sample_weights": {},
                  **ml_overrides}}
    path.write_text(json.dumps(cfg), encoding="utf-8")


def _run(tmp_path, hist, cfg_path, extra_args):
    return learning_curve.main([
        "--history", str(hist), "--config", str(cfg_path), *extra_args])


def _load_json(tmp_path):
    return json.loads((tmp_path / "outputs" / "learning_curve.json")
                      .read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# brief's two binding tests
# ---------------------------------------------------------------------------

def test_learning_curve_end_to_end(tmp_path, monkeypatch):
    hist = tmp_path / "signal_history.csv"
    _build_corpus(hist, n=160, n_live=30)
    cfg_path = tmp_path / "config.json"
    _write_config(cfg_path)
    monkeypatch.chdir(tmp_path)

    rc = learning_curve.main([
        "--history", str(hist), "--config", str(cfg_path),
        "--fracs", "0.5,1.0", "--n-splits", "3"])
    assert rc == 0

    data = json.loads((tmp_path / "outputs" / "learning_curve.json")
                      .read_text(encoding="utf-8"))
    assert [p["frac"] for p in data["points"]] == [0.5, 1.0]
    assert data["points"][1]["n_rows"] > data["points"][0]["n_rows"]
    for p in data["points"]:
        assert 0.0 <= (p["probe_share"] or 0.0) <= 1.0
        assert p["oof_brier"] is None or 0.0 <= p["oof_brier"] <= 1.0
    assert data["projection"]["cap_live_n"] == \
        2.0 * data["points"][-1]["n_live"]
    assert (tmp_path / "outputs" / "learning_curve.md").exists()


def test_determinism(tmp_path, monkeypatch):
    hist = tmp_path / "signal_history.csv"
    _build_corpus(hist, n=160, n_live=30)
    cfg_path = tmp_path / "config.json"
    _write_config(cfg_path)
    monkeypatch.chdir(tmp_path)
    args = ["--history", str(hist), "--config", str(cfg_path),
           "--fracs", "0.5,1.0", "--n-splits", "3"]

    assert learning_curve.main(args) == 0
    j1 = (tmp_path / "outputs" / "learning_curve.json").read_text(
        encoding="utf-8")
    assert learning_curve.main(args) == 0
    j2 = (tmp_path / "outputs" / "learning_curve.json").read_text(
        encoding="utf-8")
    assert j1 == j2


# ---------------------------------------------------------------------------
# additional focused coverage
# ---------------------------------------------------------------------------

def test_small_corpus_reports_explicit_skip_not_omission(tmp_path,
                                                         monkeypatch):
    """160 rows < DEFAULTS['min_prefix_rows']=240 for BOTH requested
    fracs (80 and 160 rows) - every point must still appear in the
    output, explicitly marked skipped, never silently dropped."""
    hist = tmp_path / "signal_history.csv"
    _build_corpus(hist, n=160, n_live=30)
    cfg_path = tmp_path / "config.json"
    _write_config(cfg_path)
    monkeypatch.chdir(tmp_path)

    assert _run(tmp_path, hist, cfg_path,
               ["--fracs", "0.5,1.0", "--n-splits", "3"]) == 0
    data = _load_json(tmp_path)
    assert len(data["points"]) == 2
    for p in data["points"]:
        assert p["skipped"] == "insufficient labels"
        assert p["oof_brier"] is None
        assert p["selected"] is None
        assert p["regime"] is None
        assert p["n_rows"] > 0            # not omitted - reported with 0 too


def test_min_positives_skip_even_above_the_row_floor(tmp_path, monkeypatch):
    """A prefix that clears min_prefix_rows on raw row count but is
    almost entirely one label (fewer than 5 positives) must still be
    skipped - the row-count floor is necessary, not sufficient."""
    hist = tmp_path / "signal_history.csv"
    store = HistoryStore(str(hist))
    n = 260
    for i in range(n):
        sig_ts = _START + i * _STEP
        label = 1 if i < 3 else 0          # only 3 positives total
        regime = "bull_quiet" if (i // 2) % 2 == 0 else "bear"
        feats = _feats(i, regime)
        store._append_row(f"cand-{i}", "BTC", "long", feats, label, 0.0,
                          "candidate", signal_ts=sig_ts, barrier="profit",
                          probe="")
    cfg_path = tmp_path / "config.json"
    _write_config(cfg_path)
    monkeypatch.chdir(tmp_path)

    assert _run(tmp_path, hist, cfg_path,
               ["--fracs", "1.0", "--n-splits", "3"]) == 0
    data = _load_json(tmp_path)
    assert data["points"][0]["n_rows"] >= 240        # cleared the row floor
    assert data["points"][0]["skipped"] == "insufficient labels"


def test_real_prefix_produces_a_scored_point(tmp_path, monkeypatch):
    """Above min_prefix_rows with balanced labels, the report must
    actually run the deployed selector (not skip) and return real,
    bounded oof_brier/calib_gap plus a per-regime breakdown."""
    hist = tmp_path / "signal_history.csv"
    _build_corpus(hist, n=300, n_live=60)
    cfg_path = tmp_path / "config.json"
    _write_config(cfg_path)
    monkeypatch.chdir(tmp_path)

    assert _run(tmp_path, hist, cfg_path,
               ["--fracs", "1.0", "--n-splits", "3"]) == 0
    data = _load_json(tmp_path)
    p = data["points"][0]
    assert p["skipped"] is None
    assert p["selected"] in ("logistic", "gbt", "blend", "mlp")
    assert 0.0 <= p["oof_brier"] <= 1.0
    assert 0.0 <= p["calib_gap"] <= 1.0
    assert p["regime"] is not None
    assert set(p["regime"]) == {"bull_quiet", "bull_vol", "range", "bear",
                                "crisis", "unknown"}
    assert p["regime"]["bull_quiet"]["n_oof"] > 0
    assert p["regime"]["bear"]["n_oof"] > 0
    # a stratum this system never populated must say so honestly, not 0/0
    assert p["regime"]["crisis"]["scored"] is False


# ---------------------------------------------------------------------------
# unit-level: probe_share_by_cutoff and build_projection's honesty rule
# ---------------------------------------------------------------------------

def test_probe_share_by_cutoff_respects_the_cutoff(tmp_path):
    hist = tmp_path / "h.csv"
    store = HistoryStore(str(hist))
    feats = np.zeros(len(FEATURE_NAMES))
    # two live rows before the cutoff (1 probe, 1 not), one live row after
    store._append_row("a", "BTC", "long", feats, 1, 5.0, "live",
                      signal_ts=100.0, probe="1")
    store._append_row("b", "BTC", "long", feats, 0, -5.0, "live",
                      signal_ts=200.0, probe="0")
    store._append_row("c", "BTC", "long", feats, 1, 5.0, "live",
                      signal_ts=300.0, probe="1")
    share = learning_curve.probe_share_by_cutoff(str(hist), 200.0)
    assert share == pytest.approx(0.5)          # 1 of 2 rows <= cutoff
    assert learning_curve.probe_share_by_cutoff(str(hist), 50.0) is None
    assert learning_curve.probe_share_by_cutoff(str(hist), 300.0) == \
        pytest.approx(2.0 / 3.0)


def test_probe_share_missing_file_is_none(tmp_path):
    assert learning_curve.probe_share_by_cutoff(
        str(tmp_path / "does_not_exist.csv"), 100.0) is None


def test_missing_history_file_does_not_crash(tmp_path, monkeypatch):
    """A fresh checkout has no outputs/signal_history.csv (gitignored).
    HistoryStore.load_training_data(return_label_times=True, ...)'s
    missing-file early return only special-cases return_sig (a 4-tuple),
    so it hands back a bare 3-tuple here - an unguarded 5-way unpack would
    raise ValueError. main() must report an honest empty/skipped corpus
    instead of crashing."""
    cfg_path = tmp_path / "config.json"
    _write_config(cfg_path)
    monkeypatch.chdir(tmp_path)
    rc = learning_curve.main([
        "--history", str(tmp_path / "does_not_exist.csv"),
        "--config", str(cfg_path), "--fracs", "0.5,1.0",
        "--n-splits", "3"])
    assert rc == 0
    data = _load_json(tmp_path)
    assert data["meta"]["n_total_rows"] == 0
    for p in data["points"]:
        assert p["n_rows"] == 0
        assert p["skipped"] == "insufficient labels"
        assert p["oof_brier"] is None


def test_projection_reports_honest_no_improvement_when_slope_nonnegative():
    # oof_brier flat/rising with more data (b >= 0): must NOT be dressed
    # up as an improvement forecast.
    points = [
        {"n_live": 10, "oof_brier": 0.24},
        {"n_live": 40, "oof_brier": 0.24},
        {"n_live": 160, "oof_brier": 0.25},
    ]
    proj = learning_curve.build_projection(points, 2.0)
    assert proj["b"] >= 0
    assert proj["note"] == "no measurable improvement with corpus growth"
    assert proj["cap_live_n"] == 2.0 * points[-1]["n_live"]


def test_projection_improving_slope_is_labeled_directional_only():
    points = [
        {"n_live": 10, "oof_brier": 0.30},
        {"n_live": 40, "oof_brier": 0.24},
        {"n_live": 160, "oof_brier": 0.19},
    ]
    proj = learning_curve.build_projection(points, 2.0)
    assert proj["b"] < 0
    assert "directional only" in proj["note"]
    assert proj["predicted_oof_brier_at_cap"] is not None


def test_projection_insufficient_points_is_still_capped():
    # only one scored point (n_live>=2) - can't fit a line, but cap_live_n
    # must still be reported from the observed live-N, per the brief's
    # cap-rule test.
    points = [{"n_live": 240, "oof_brier": 0.22}]
    proj = learning_curve.build_projection(points, 2.0)
    assert proj["a"] is None and proj["b"] is None
    assert proj["cap_live_n"] == 480.0
    assert "insufficient points" in proj["note"]
