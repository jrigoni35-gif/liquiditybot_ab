"""The label's barriers, cost-floored (spec D2): sigma_eff floors the
SIGMA INPUT so pt and sl scale together and the 8:6 ratio is preserved
by construction — a single knob, no per-barrier distortion."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np

from ml.features import FEATURE_NAMES
from ml.history import CandidateLabeler, HistoryStore, bootstrap_dataset
from ml.labeling import barrier_geometry  # noqa: E402


def test_high_vol_is_pure_sigma_scaling():
    # sigma above the floor: identical to legacy 8σ/6σ
    pt, sl = barrier_geometry(0.005, 0.5, 8.0, 6.0, 4.0)
    assert abs(pt - 0.04) < 1e-12 and abs(sl - 0.03) < 1e-12


def test_low_vol_hits_the_cost_floor_ratio_preserved():
    # floor: sigma_eff = 4.0 * 0.005 / 8 = 0.0025 -> pt 2%, sl 1.5%
    pt, sl = barrier_geometry(0.0005, 0.5, 8.0, 6.0, 4.0)
    assert abs(pt - 0.02) < 1e-12 and abs(sl - 0.015) < 1e-12
    assert abs(pt / sl - 8.0 / 6.0) < 1e-9


def test_floor_boundary_is_continuous():
    boundary = 4.0 * (0.5 / 100.0) / 8.0
    lo = barrier_geometry(boundary * 0.999, 0.5, 8.0, 6.0, 4.0)
    hi = barrier_geometry(boundary * 1.001, 0.5, 8.0, 6.0, 4.0)
    assert abs(lo[0] - hi[0]) < 1e-4


def test_zero_cost_mult_disables_the_floor():
    pt, sl = barrier_geometry(0.0005, 0.5, 8.0, 6.0, 0.0)
    assert abs(pt - 0.004) < 1e-12          # bare 8σ, legacy


# ============================================================================
# Step 6: labeler-level wiring — proves barrier_geometry() actually reaches
# the persisted label, not just the pure function in isolation. Synthetic
# path: sigma_bar=0.0005 (tiny), cost=0.5% (label_round_trip_cost_pct,
# label_include_spread off so cost is exactly rt_cost_pct), pt_mult=8,
# sl_mult=6. Unfloored pt = 8*0.0005 = 0.4%; floored pt (pt_cost_mult=4.0)
# = 4.0*0.5%/8 * 8 = 2%. The path rises to +0.55% by the second bar and
# never drops — that clears the unfloored 0.4% pt (tb_pt) but stays well
# under the floored 2% pt for the rest of the horizon (tb_time, vertical).
# ============================================================================

def _candle(t, price, hi, lo):
    return {"time": t, "close": price, "high": hi, "low": lo, "volume": 1.0}


_PATH = [
    _candle(0, 100.0, 100.0, 100.0),     # entry bar
    _candle(1, 100.10, 100.15, 99.90),   # up 0.15%, dn 0.10% — no barrier yet
    _candle(2, 100.45, 100.50, 100.10),  # up 0.50% >= unfloored pt (0.4%)
    _candle(3, 100.40, 100.55, 100.20),  # up 0.55%, still < floored pt (2%)
    _candle(4, 100.50, 100.55, 100.30),  # up 0.55%
    _candle(5, 100.50, 100.55, 100.30),  # horizon exhausts here (5 bars)
]


def _labeler(tmp_path, pt_cost_mult):
    store = HistoryStore(str(tmp_path / "hist.csv"))
    ml_cfg = {"label_max_bars": 5, "label_pt_vol_mult": 8.0,
              "label_sl_vol_mult": 6.0, "label_round_trip_cost_pct": 0.5,
              "label_include_spread": False, "label_mode": "triple_barrier",
              "label_pt_cost_mult": pt_cost_mult}
    return store, CandidateLabeler(store, ml_cfg)


def _labeled_barrier(tmp_path, pt_cost_mult):
    store, lab = _labeler(tmp_path, pt_cost_mult)
    feats = np.zeros(len(FEATURE_NAMES))
    lab.register("BTC", "long", feats, sigma_bar=0.0005, bar_time=0)
    lab.update_candles("BTC", _PATH)
    assert lab.poll() == 1
    import csv
    with open(store.path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    return rows[0]["barrier"]


def test_unfloored_labeler_hits_tb_pt(tmp_path):
    assert _labeled_barrier(tmp_path, 0.0) == "tb_pt"


def test_floored_labeler_never_reaches_pt_hits_tb_time(tmp_path):
    assert _labeled_barrier(tmp_path, 4.0) == "tb_time"


# ============================================================================
# bootstrap_dataset cost floor (T2 review finding): the cold-start EMA-cross
# corpus scripts/train_meta.py vstacks with the live candidate corpus must
# use the SAME cost-floored bet geometry as CandidateLabeler._label, or one
# training call mixes two bet geometries. pt_cost_mult threads the floor
# into bootstrap_dataset's triple_barrier branch only (the exit_policy
# branch mirrors the exit-policy labeler and has its own, unrelated floor).
# ============================================================================

def _synthetic_low_vol_path(seed=20260741, n=900, sigma=0.0015):
    # a fixed-seed GBM-like random walk (NOT the global numpy RNG - a local
    # np.random.default_rng(seed), so this is exactly reproducible run to
    # run/machine to machine) at a per-bar vol (0.15%) chosen so the
    # trailing-60-bar sigma_bar bootstrap_dataset computes at its EMA
    # crosses lands ABOVE cost_frac/pt_mult (the unfloored pt clears
    # round-trip cost, so at least one cross can WIN unfloored) and BELOW
    # the floor's sigma_eff = pt_cost_mult*cost_frac/pt_mult (so the same
    # cross's floored barrier is far enough out that its path often times
    # out or resolves differently instead) - i.e., squarely in the regime
    # the T2 review finding says training was mixing. A tight synthetic
    # intrabar wick (0.03%) keeps barrier touches driven by the actual
    # closes path, not an incidental wick artifact.
    rng = np.random.default_rng(seed)
    rets = rng.normal(0.0, sigma, n - 1)
    closes = [100.0]
    for r in rets:
        closes.append(closes[-1] * np.exp(r))
    return [{"time": 1000 + 300 * i, "close": c, "high": c * 1.0003,
             "low": c * 0.9997, "volume": 100.0}
            for i, c in enumerate(closes)]


def test_bootstrap_dataset_cost_floor_flips_a_cold_start_label():
    candles = _synthetic_low_vol_path()
    X0, y0 = bootstrap_dataset(candles, pt_cost_mult=0.0, max_bars=40,
                               cost_pct=0.5)
    X4, y4 = bootstrap_dataset(candles, pt_cost_mult=4.0, max_bars=40,
                               cost_pct=0.5)
    assert len(y0) > 0 and len(y4) > 0, "the synthetic path must still cross"
    assert len(y0) == len(y4), \
        "the floor changes the LABEL, never which crosses register"
    assert np.array_equal(X0, X4), \
        "features never depend on pt_cost_mult, only out.label does"
    assert not np.array_equal(y0, y4), \
        "the floor must change >=1 cold-start label vs the unfloored bet"


def test_bootstrap_dataset_pt_cost_mult_omitted_is_legacy_default():
    candles = _synthetic_low_vol_path()
    X_default, y_default = bootstrap_dataset(candles, max_bars=40,
                                             cost_pct=0.5)
    X0, y0 = bootstrap_dataset(candles, pt_cost_mult=0.0, max_bars=40,
                               cost_pct=0.5)
    assert np.array_equal(X_default, X0)
    assert np.array_equal(y_default, y0)
