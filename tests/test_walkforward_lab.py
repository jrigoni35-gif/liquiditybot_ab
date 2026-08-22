"""scripts/walkforward_lab.py — the resampling instrument's own pins.

WHY STRUCTURAL PINS. This module exists to widen error bars, and every
failure mode of a widener is the same: it silently NARROWS. A bootstrap
that mis-indexes, a block selector that returns garbage, a deflation that
divides where it should multiply — each produces a confident, tighter,
wrong interval, and a tighter interval is exactly the artifact that gets
believed. So the pins here assert DIRECTION and IDENTITY, not values:
identities that must hold on any corpus (b=1 IS the iid bootstrap; the
deflated interval is never narrower; the point breakeven of a series built
to break even at 2x IS 2x), plus determinism, because an instrument whose
answer moves between runs cannot settle an argument.

They also pin the two things this repo keeps rediscovering the hard way:
the report must never silently swap corpus, and it must never move
MIN_COHORT_N.
"""
import math

import numpy as np
import pytest

import scripts.walkforward_lab as wl


def _series(gross, fee):
    g = np.asarray(gross, dtype=float)
    f = np.asarray(fee, dtype=float)
    return {"t": np.arange(g.size, dtype=float), "gross": g, "fee": f,
            "net": g - f, "n": int(g.size)}


# ---------------------------------------------------------------------------
# resampling identities
# ---------------------------------------------------------------------------
def test_block_length_one_is_exactly_the_iid_bootstrap():
    """b=1 -> p=1 -> every draw starts a new block. If this ever stops
    holding, WF-3 stops being a controlled contrast and becomes a second,
    unvalidated implementation."""
    rng = np.random.default_rng(3)
    idx = wl.sb_indices(40, 1.0, 500, rng)
    assert idx.shape == (500, 40)
    # with p=1 the successor rule never fires, so consecutive columns are
    # independent draws: the share of j where idx[:,j] == idx[:,j-1]+1 must
    # sit at the chance rate 1/n, not the near-1 rate a block bootstrap gives
    cont = np.mean(idx[:, 1:] == (idx[:, :-1] + 1) % 40)
    assert cont < 0.10, f"b=1 produced blocks (continuation rate {cont:.3f})"


def test_large_block_length_actually_produces_blocks():
    rng = np.random.default_rng(3)
    idx = wl.sb_indices(40, 10.0, 500, rng)
    cont = np.mean(idx[:, 1:] == (idx[:, :-1] + 1) % 40)
    assert cont > 0.7, f"b=10 failed to build blocks ({cont:.3f})"


def test_indices_stay_in_range_and_wrap():
    rng = np.random.default_rng(11)
    idx = wl.sb_indices(7, 5.0, 200, rng)
    assert idx.min() >= 0 and idx.max() <= 6


def test_block_selector_separates_iid_from_autocorrelated():
    """Politis-White must return a LONGER block for a dependent series than
    for white noise. The absolute value is not pinned — at small n it is an
    estimate — but the ORDERING is the whole reason to run it."""
    rng = np.random.default_rng(5)
    iid = rng.normal(0.0, 1.0, 400)
    ar = np.empty(400)
    ar[0] = rng.normal()
    for i in range(1, 400):
        ar[i] = 0.8 * ar[i - 1] + rng.normal(0.0, 0.6)
    b_iid = wl.politis_white_block(iid)
    b_ar = wl.politis_white_block(ar)
    assert b_iid["available"] and b_ar["available"]
    assert b_ar["b_opt"] > b_iid["b_opt"], (b_ar["b_opt"], b_iid["b_opt"])


def test_block_selector_refuses_tiny_samples_instead_of_guessing():
    out = wl.politis_white_block(np.array([1.0, 2.0, 3.0]))
    assert out["available"] is False


def test_bootstrap_interval_brackets_the_sample_mean():
    x = np.random.default_rng(2).normal(0.5, 1.0, 200)
    ci = wl.bootstrap_ci(x, 1.0, 4000, seed=7)
    assert ci["mean_lo"] < ci["mean"] < ci["mean_hi"]
    assert math.isclose(ci["mean"], float(x.mean()), abs_tol=1e-6)


# ---------------------------------------------------------------------------
# the deflation must only ever widen
# ---------------------------------------------------------------------------
def test_concurrency_deflation_never_narrows():
    x = np.random.default_rng(4).normal(0.3, 1.0, 120)
    ci = wl.bootstrap_ci(x, 1.0, 4000, seed=7)
    raw_w = ci["mean_hi"] - ci["mean_lo"]
    for infl in (1.0, 1.5, 3.0):
        d = wl.concurrency_deflated(ci, infl)
        assert d["available"]
        w = d["mean_hi"] - d["mean_lo"]
        assert w >= raw_w * 0.98, (infl, w, raw_w)
        assert d["approximate"] is True


def test_deflation_at_factor_one_reproduces_the_bootstrap_width():
    x = np.random.default_rng(6).normal(0.0, 1.0, 300)
    ci = wl.bootstrap_ci(x, 1.0, 6000, seed=7)
    d = wl.concurrency_deflated(ci, 1.0)
    raw_w = ci["mean_hi"] - ci["mean_lo"]
    assert abs((d["mean_hi"] - d["mean_lo"]) - raw_w) < 0.15 * raw_w


# ---------------------------------------------------------------------------
# WF-5 cost tolerance — the number the fee decision will be read off
# ---------------------------------------------------------------------------
def test_point_breakeven_is_exact_on_a_constructed_series():
    """gross = 2 x fee everywhere -> the edge dies at exactly twice the
    booked cost. If this drifts, every bps figure in WF-5 is wrong by the
    same factor and nothing else in the report would show it."""
    s = _series([2.0] * 20, [1.0] * 20)
    ct = wl.cost_tolerance(s, reps=2000, seed=7, b=1.0)
    assert ct["available"]
    assert math.isclose(ct["m_point"], 2.0, rel_tol=1e-6)
    assert math.isclose(ct["booked_round_trip_bps"], 100.0, rel_tol=1e-9)
    assert math.isclose(ct["tolerable_bps_point"], 200.0, rel_tol=1e-4)


def test_lower_bound_breakeven_never_exceeds_the_point_estimate():
    rng = np.random.default_rng(9)
    s = _series(rng.normal(1.0, 1.0, 60), np.full(60, 0.4))
    ct = wl.cost_tolerance(s, reps=4000, seed=7, b=1.0)
    assert ct["m_lower"] is not None
    assert ct["m_lower"] <= ct["m_point"] + 1e-9


def test_deflated_breakeven_is_never_looser_than_the_raw_bound():
    rng = np.random.default_rng(13)
    s = _series(rng.normal(1.0, 1.0, 60), np.full(60, 0.4))
    ct = wl.cost_tolerance(s, reps=4000, seed=7, b=1.0, se_inflation=2.0)
    assert ct["m_deflated"] is not None and ct["m_lower"] is not None
    assert ct["m_deflated"] <= ct["m_lower"] + 1e-9


def test_zero_fee_corpus_is_refused_rather_than_divided_by():
    s = _series([1.0] * 10, [0.0] * 10)
    assert wl.cost_tolerance(s, reps=500, seed=7, b=1.0)["available"] is False


# ---------------------------------------------------------------------------
# WF-4b MinTRL
# ---------------------------------------------------------------------------
def test_mintrl_matches_the_closed_form_it_claims_to_implement():
    rng = np.random.default_rng(21)
    x = rng.normal(0.4, 1.0, 300)
    s = _series(x, np.zeros(300))
    out = wl.mintrl_grid(s, eff_n=100.0)
    row = next(r for r in out["rows"] if r["anchor"] == "gross")
    sr, sk, ku = wl._moments(x)
    z = wl._norm_ppf(0.95)
    expect = 1.0 + (1.0 - sk * sr + (ku - 1.0) / 4.0 * sr ** 2) * (z / sr) ** 2
    assert math.isclose(row["mintrl"], expect, rel_tol=1e-3)


def test_mintrl_is_undefined_not_zero_when_sharpe_is_negative():
    s = _series([-1.0, -0.5, -2.0, -0.2, -1.5, -0.9], [0.0] * 6)
    row = next(r for r in wl.mintrl_grid(s, eff_n=6.0)["rows"]
               if r["anchor"] == "gross")
    assert row["mintrl"] is None
    assert row["cleared_nominal"] is False and row["cleared_effective"] is False


def test_effective_n_clearance_is_strictly_harder_than_nominal():
    """The whole point of WF-4b: n_eff <= n, so a corpus can clear on
    nominal and fail on effective, never the reverse."""
    rng = np.random.default_rng(31)
    s = _series(rng.normal(0.5, 1.0, 80), np.zeros(80))
    out = wl.mintrl_grid(s, eff_n=8.0)
    row = next(r for r in out["rows"] if r["anchor"] == "gross")
    assert row["cleared_nominal"] and not row["cleared_effective"]


# ---------------------------------------------------------------------------
# corpus handling and standards
# ---------------------------------------------------------------------------
def test_fee_anchors_are_exact_tier_ratios_not_rounded_conveniences():
    d = dict(wl.FEE_ANCHORS)
    assert d["configured 25/40"] == 1.0
    assert math.isclose(d["T1 both-maker 40/40"], 80.0 / 50.0)
    assert math.isclose(d["T1 maker-in/taker-out"], 120.0 / 65.0)


def test_net_at_is_linear_in_the_multiplier():
    s = _series([3.0, 4.0], [1.0, 2.0])
    assert list(wl.net_at(s, 0.0)) == [3.0, 4.0]
    assert list(wl.net_at(s, 2.0)) == [1.0, 0.0]


def test_missing_explicit_corpus_is_reported_not_silently_replaced():
    """An explicit --fills that does not exist must NOT fall back to a
    bundle. Silent corpus substitution is the failure this repo has
    repeatedly paid for."""
    assert wl.resolve_fills("/nonexistent/fills.csv") is None


def test_the_report_reads_the_pre_registered_cohort_target():
    from scripts.cohort_eval import ERA4_MIN_N
    assert wl.ERA4_MIN_N == ERA4_MIN_N == 50


def test_report_is_deterministic_under_a_fixed_seed(tmp_path):
    csvp = tmp_path / "fills.csv"
    csvp.write_text(_fixture_fills(), encoding="utf-8")
    a = wl.build(csvp, reps=800, seed=7)
    b = wl.build(csvp, reps=800, seed=7)
    assert a == b


def test_thin_corpus_degrades_honestly_instead_of_printing_a_number(tmp_path):
    csvp = tmp_path / "fills.csv"
    csvp.write_text("ts,order_id,position_id,purpose,symbol,side,ordertype,"
                    "post_only,attempt,fill_size,fill_price,arrival_ref,"
                    "slip_bps,fees_delta_usd,remaining,reason,exec_era\n",
                    encoding="utf-8")
    out = wl.build(csvp, reps=500, seed=7)
    assert out["available"] is False and out["n"] == 0


def _fixture_fills() -> str:
    """Six round trips closing after the era-4 cut, honest-fill stamped."""
    hdr = ("ts,order_id,position_id,purpose,symbol,side,ordertype,post_only,"
           "attempt,fill_size,fill_price,arrival_ref,slip_bps,"
           "fees_delta_usd,remaining,reason,exec_era")
    base = 1786500000.0
    lines = [hdr]
    for i in range(6):
        pid = f"P{i}"
        t0 = base + i * 5000.0
        entry_px = 100.0
        # distinct exit prices per trip: era4_trips de-duplicates on the
        # (purpose, side, size, price) signature, so repeating a price
        # silently drops the trip — a fixture with collisions would test a
        # smaller cohort than it claims to.
        exit_px = 100.0 + (1.0 + 0.13 * i if i % 2 == 0 else -0.5 - 0.11 * i)
        lines.append(f"{t0},o{i}a,{pid},entry,XBTUSD,buy,limit,true,1,"
                     f"1.0,{entry_px},{entry_px},0,0.25,0,OM-011,7-e7d5ca1a")
        lines.append(f"{t0 + 900},o{i}b,{pid},exit,XBTUSD,sell,limit,true,1,"
                     f"1.0,{exit_px},{exit_px},0,0.25,0,PT-010,7-e7d5ca1a")
    return "\n".join(lines) + "\n"


def test_fixture_cohort_produces_a_full_report(tmp_path):
    csvp = tmp_path / "fills.csv"
    csvp.write_text(_fixture_fills(), encoding="utf-8")
    out = wl.build(csvp, reps=800, seed=7)
    assert out["available"] and out["n"] == 6
    assert out["cost_tolerance"]["available"]
    assert out["dsr"]["trials_measured"] is False
    with pytest.raises(KeyError):
        out["verdict"]        # this instrument never emits one
