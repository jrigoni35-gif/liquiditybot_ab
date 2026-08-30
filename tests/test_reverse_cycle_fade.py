"""Pins for scripts/reverse_cycle_fade.py — the reverse-cycle FADE instrument.

Each pin guards a property the fade VERDICT rests on; comments name the
mutation each one kills (verified by hand-mutation, restored). These are
synthetic-data pins: the instrument's arithmetic is proven on constructed
inputs where the right answer is known, independent of the live corpus.
"""
from __future__ import annotations

import math

import numpy as np
import pytest

from scripts import reverse_cycle_fade as rcf

H = 3600  # a 1h horizon for all synthetic scenarios


def _linear_exp_asset(dsign: float, c: float, n: int = 40):
    """An asset whose H-forward return is EXACTLY c on every row: samples at
    ts = k*H, price = (1+c)^k, so (p_{k+1}-p_k)/p_k = c. dir_sign = dsign."""
    ts = np.array([k * H for k in range(n)], float)
    px = np.array([(1.0 + c) ** k for k in range(n)], float)
    rows = [(k * H, (1.0 + c) ** k, dsign) for k in range(n)]
    return {"rows": rows, "path_ts": ts, "path_px": px}


def test_antisymmetry_fade_is_negated_follow():
    """fade == -follow at every aggregation. This IS the hard arithmetic
    gate: a blanket fade cannot beat the follow, only mirror it.
    KILLS a mutation that computes fade as anything other than -follow
    (e.g. fade = follow, or an independent sign)."""
    data = {"AAA": _linear_exp_asset(+1.0, 0.02)}
    r = rcf.sweep_horizon(data, H)
    for base in ("nom", "nom_dm", "eff", "eff_dm"):
        f = r[f"follow_{base}"]["mean"]
        g = r[f"fade_{base}"]["mean"]
        assert f is not None and g is not None
        assert g == pytest.approx(-f, abs=1e-12), base


def test_demean_removes_beta_drift():
    """Pure market drift (all-long, monotone rise) gives a large POSITIVE raw
    follow but a ZERO demeaned follow — the demean strips beta so only timing
    survives. KILLS a mutation that drops the per-asset demean (the demeaned
    row would then equal the raw row and this fails)."""
    data = {"AAA": _linear_exp_asset(+1.0, 0.02)}
    r = rcf.sweep_horizon(data, H)
    assert r["follow_nom"]["mean"] == pytest.approx(0.02, abs=1e-9)   # raw beta
    assert r["follow_nom_dm"]["mean"] == pytest.approx(0.0, abs=1e-9)  # neutral
    # and the effective (non-overlapping) demeaned is likewise zeroed
    assert r["follow_eff_dm"]["mean"] == pytest.approx(0.0, abs=1e-9)


def test_short_direction_signs_follow_negative():
    """A SHORT into a rising market: follow must be NEGATIVE (bot on the wrong
    side of the drift), fade POSITIVE. KILLS a mutation that ignores dir_sign
    or flips the short convention (would read follow positive)."""
    data = {"AAA": _linear_exp_asset(-1.0, 0.02)}
    r = rcf.sweep_horizon(data, H)
    assert r["follow_nom"]["mean"] == pytest.approx(-0.02, abs=1e-9)
    assert r["fade_nom"]["mean"] == pytest.approx(+0.02, abs=1e-9)


def test_non_overlap_subsample_deflates_n():
    """Densely-sampled overlapping rows inflate nominal n; the non-overlapping
    subsample (gap >= H) must keep far fewer. This is the autocorrelation-
    mirage deflation the whole verdict turns on. KILLS a mutation that drops
    the >= horizon spacing guard (n_eff would then equal n_nom)."""
    # samples every H/5 -> ~5x denser than the horizon; forward return exists
    # because target t0+H lands on a later sample.
    step = H // 5
    n = 100
    ts = np.array([k * step for k in range(n)], float)
    px = np.array([1.0 + 0.0001 * k for k in range(n)], float)  # slow drift
    rows = [(k * step, 1.0 + 0.0001 * k, +1.0) for k in range(n)]
    data = {"AAA": {"rows": rows, "path_ts": ts, "path_px": px}}
    r = rcf.sweep_horizon(data, H)
    n_nom = r["follow_nom"]["n"]
    n_eff = r["follow_eff"]["n"]
    assert n_nom >= 50           # dense overlapping sample is large
    assert n_eff <= n_nom // 3   # disjoint windows are far fewer
    assert n_eff >= 8            # but enough to report


def test_forward_ret_tolerance_drop():
    """A row whose only forward sample sits beyond 0.5*H is dropped, not
    matched to a far price. KILLS a mutation that widens/removes the tolerance
    gate (the far match would inject a spurious return)."""
    # one early sample, then a gap far exceeding the tolerance window
    path_ts = np.array([0.0, H * 3.0], float)
    path_px = np.array([1.0, 2.0], float)
    # target = 0 + H; nearest forward is at 3H, |3H - H| = 2H > 0.5H -> drop
    out = rcf.forward_ret(path_ts, path_px, 0.0, 1.0, H, rcf.TOL_FRAC * H)
    assert out is None


def test_mean_t_matches_hand_calc():
    """_mean_t is the significance kernel. Pin it against a hand computation so
    a broken SE cannot silently pass every downstream t. KILLS a ddof or
    sqrt(n) mutation."""
    vals = np.array([1.0, 2.0, 3.0, 4.0], float)  # mean 2.5, sd(ddof1)=~1.291
    m, t, n = rcf._mean_t(vals)
    assert n == 4
    assert m == pytest.approx(2.5)
    sd = math.sqrt(sum((v - 2.5) ** 2 for v in vals) / 3)
    assert t == pytest.approx(2.5 / (sd / math.sqrt(4)))
