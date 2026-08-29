"""Mutation-killed tests for scripts/horizon_edge_sweep.py.

The load-bearing claim of the sweep is "the information coefficient recovers a
real forward-return relationship and reports ~null when there is none". These
tests plant a KNOWN signal into a synthetic price path, confirm the IC route
recovers it, then BREAK the relationship and confirm the IC collapses. A
broken IC kernel (e.g. one that ignored the feature, or always returned 0)
fails the recover assertion; a leaky one (that reported signal on shuffled
data) fails the null assertion. Both directions are asserted, so neither
mutation survives.

Also pins the two correctness properties the market-direction reading rests
on: forward matching respects the tolerance, and the four side-relative
`_dir` features are un-signed back to market-absolute on load.
"""
from __future__ import annotations

import csv
import math
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import horizon_edge_sweep as hes  # noqa: E402


# --------------------------------------------------------------------------
# unit: the Spearman kernel
# --------------------------------------------------------------------------
def test_spearman_recovers_monotone_and_nulls_on_shuffle():
    rng = np.random.default_rng(7)
    x = rng.normal(size=500)
    y = x + 0.3 * rng.normal(size=500)          # strong monotone relationship
    ic = hes.spearman(x, y)
    assert ic is not None and ic > 0.85, ic     # kill: kernel must SEE signal

    y_shuf = y.copy()
    rng.shuffle(y_shuf)
    ic0 = hes.spearman(x, y_shuf)
    assert ic0 is not None and abs(ic0) < 0.15, ic0  # kill: must null when broken


def test_spearman_none_on_constant():
    # a dead/padded feature (all one value) has no rank variance -> no IC
    assert hes.spearman(np.zeros(50), np.arange(50.0)) is None


def test_spearman_sign():
    x = np.arange(100.0)
    assert hes.spearman(x, -x) < -0.99            # inverse relationship, negative IC


# --------------------------------------------------------------------------
# unit: forward matching respects tolerance
# --------------------------------------------------------------------------
def test_forward_ret_within_and_outside_tolerance():
    ts = np.array([0.0, 3600.0, 7200.0])
    px = np.array([100.0, 110.0, 121.0])
    # H=3600, tol=1800: t0=0 -> target 3600, exact sample at 3600 -> +10%
    got = hes.forward_ret(ts, px, t0=0.0, p0=100.0, horizon=3600, tol=1800)
    assert got is not None
    assert got[0] == pytest.approx(0.10) and got[1] == pytest.approx(3600.0)
    # target 5400 (H=5400) nearest sample 7200 is 1800 away, tol 900 -> discard
    assert hes.forward_ret(ts, px, t0=0.0, p0=100.0, horizon=5400, tol=900) is None
    # no strictly-forward sample -> None
    assert hes.forward_ret(ts, px, t0=7200.0, p0=121.0, horizon=3600, tol=99999) is None


# --------------------------------------------------------------------------
# the mutation-kill: plant a known signal, then break it
# --------------------------------------------------------------------------
def _planted_asset(rng, coupling: float):
    """One asset, dense 60s price path over ~33h. flow_tox at t0 is coupled to
    the REALIZED 1h-forward return (strength `coupling`); depth_ratio is pure
    noise. coupling=0 destroys the signal."""
    n = 2000
    step = 60.0
    ts = np.arange(n) * step
    logret = rng.normal(0, 0.004, size=n)
    px = 100.0 * np.exp(np.cumsum(logret))
    path_ts = ts.copy()
    path_px = px.copy()
    rows = []
    for i in range(n):
        # true forward return at exactly +1h (20 steps of 60s)
        j = i + 20
        if j >= n:
            fwd = 0.0
        else:
            fwd = (px[j] - px[i]) / px[i]
        feats = {f: math.nan for f in hes.ALL_FEATURES}
        feats["flow_tox"] = coupling * fwd + 0.002 * rng.normal()
        feats["depth_ratio"] = rng.normal()  # control: unrelated to fwd
        feats[hes.FOOTPRINT] = math.nan
        rows.append((float(ts[i]), float(px[i]), feats))
    return {"rows": rows, "path_ts": path_ts, "path_px": path_px}


def test_sweep_recovers_planted_signal():
    rng = np.random.default_rng(11)
    data = {"TEST": _planted_asset(rng, coupling=40.0)}
    res = hes.sweep(data, "1h", 3600)
    sig = res["flow_tox"]
    ctl = res["depth_ratio"]
    # planted feature: strong, significant effective IC, correct (positive) sign
    assert sig["ic_eff"] is not None and sig["ic_eff"] > 0.4, sig
    assert sig["z_eff"] is not None and sig["z_eff"] > 2.0, sig
    assert sig["agree"] is True, sig                       # both routes agree
    # control feature: no edge
    assert abs(ctl["ic_eff"]) < 0.3, ctl


def test_sweep_nulls_when_signal_broken():
    rng = np.random.default_rng(11)
    data = {"TEST": _planted_asset(rng, coupling=0.0)}   # coupling removed
    res = hes.sweep(data, "1h", 3600)
    sig = res["flow_tox"]
    assert sig["ic_eff"] is not None
    assert abs(sig["ic_eff"]) < 0.3, sig                  # collapses to noise
    assert abs(sig["z_eff"]) < 2.5, sig                   # not significant


# --------------------------------------------------------------------------
# correctness: side-relative _dir features are un-signed to market-absolute
# --------------------------------------------------------------------------
def _write_min_csv(path: Path, rows: list[dict]):
    cols = (["asset", "side", "ts", "entry_price", "label_era"]
            + list(hes.ALL_FEATURES[:-1]))  # drop derived footprint_block
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in cols})


def test_signed_feature_unsigned_on_load(tmp_path):
    # imbalance_dir is dir_sign*market; a SHORT row's stored +0.5 is a
    # market-absolute -0.5. load_priced must flip it back.
    p = tmp_path / "sig.csv"
    _write_min_csv(p, [
        {"asset": "AAA", "side": "long", "ts": "1000", "entry_price": "10",
         "imbalance_dir": "0.5", "depth_ratio": "1.0"},
        {"asset": "AAA", "side": "short", "ts": "2000", "entry_price": "11",
         "imbalance_dir": "0.5", "depth_ratio": "1.0"},
    ])
    data, _, kept = hes.load_priced(path=p)
    assert kept == 2
    feats = [r[2] for r in data["AAA"]["rows"]]
    # long row: +0.5 stays +0.5 ; short row: +0.5 -> -0.5 (un-signed)
    assert feats[0]["imbalance_dir"] == pytest.approx(0.5)
    assert feats[1]["imbalance_dir"] == pytest.approx(-0.5)
    # depth_ratio is NOT signed: unchanged regardless of side
    assert feats[1]["depth_ratio"] == pytest.approx(1.0)


def test_nonpositive_entry_price_dropped(tmp_path):
    p = tmp_path / "np.csv"
    _write_min_csv(p, [
        {"asset": "AAA", "side": "long", "ts": "1000", "entry_price": "0",
         "depth_ratio": "1.0"},
        {"asset": "AAA", "side": "long", "ts": "2000", "entry_price": "10",
         "depth_ratio": "1.0"},
    ])
    _, _, kept = hes.load_priced(path=p)
    assert kept == 1   # the entry_price=0 row is not a price sample
