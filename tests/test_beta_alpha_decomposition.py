"""Pins for scripts/beta_alpha_decomposition.py - the instrument that tells the
bot what it is hedging against.

THE DEFECTS THIS FILE EXISTS FOR - every one caught on a run, 2026-09-07,
and every one silent (a wrong number that looked exactly like a right one):
  1. alpha reported as the MEAN RESIDUAL of an intercept regression - zero by
     construction - so every group printed "alpha 0.0" for ANY input.
  2. the price "at" a fill was the close of the bar CONTAINING it, which
     prints up to 5 minutes AFTER the fill: look-ahead at both ends of every
     window. The pin named no_look_ahead asserted that behaviour.
  3. 22 trips beyond the tape's end were dropped SILENTLY - the losing recent
     ones (mean gross -52 bps) - and the tool printed a cleaner book.
  4. a basket member with a gap was silently omitted, so some trips were
     measured against a two-member factor.
  5. the day-block percentile CI is ~2x too narrow at <= 15 days, and the
     bootstrap helper the tests exercised was dead code - the live loop was
     an inline copy.
Each pin below plants the defect's exact input and must go red on it.
"""
from __future__ import annotations

import numpy as np
import pytest

from scripts.beta_alpha_decomposition import (BAR_S, DAY, _close_at, _t_crit,
                                              alpha_clear, cr1_intervals,
                                              day_block_ci, decompose,
                                              market_return, ols, signflip_p)

ASSETS = ("BTC", "ETH", "LINK", "PAXG")
T0 = 1_780_000_000.0


def _tape(assets=ASSETS, n=2000, seed=3, hole=None):
    """A synthetic 5m tape: one common market path plus tiny noise per asset.
    `hole` = (asset, i_from, i_to) deletes those bars from one asset."""
    rng = np.random.default_rng(seed)
    t = T0 + BAR_S * np.arange(n)
    mkt = np.cumsum(rng.normal(0, 0.002, n))
    tape = {}
    for a in assets:
        c = 100.0 * np.exp(mkt + np.cumsum(rng.normal(0, 0.0002, n)))
        tt, cc = t.copy(), c
        if hole and hole[0] == a:
            keep = np.ones(n, bool)
            keep[hole[1]:hole[2]] = False
            tt, cc = tt[keep], cc[keep]
        tape[a] = (tt, cc)
    return tape


def _trips(tape, n_trips=120, beta=1.0, alpha=0.0030, noise=0.0005, seed=5,
           day_counts=None, basket=("BTC", "ETH", "LINK")):
    """Trips whose gross return is beta*market + alpha + noise, built from the
    SAME tape (and the SAME anchor rule) the decomposition reads, so the truth
    is known. `day_counts` places that many trips in each of the first UTC
    days of the tape, to control the cluster count."""
    rng = np.random.default_rng(seed)
    t = tape["BTC"][0]
    days = np.floor(t / DAY)
    full_days = [d for d in np.unique(days)[1:-1]]
    slots = []
    if day_counts:
        for k, cnt in enumerate(day_counts):
            lo, hi = np.flatnonzero(days == full_days[k])[[0, -1]]
            slots += [(lo, hi) for _ in range(cnt)]
    else:
        slots = [(10, len(t) - 200)] * n_trips
    out = []
    for i, (lo, hi) in enumerate(slots):
        hold = int(rng.integers(6, 30 if day_counts else 150))
        i0 = int(rng.integers(lo + 2, max(lo + 3, hi - hold - 1)))
        i1 = i0 + hold
        asset = ASSETS[i % 4]
        direction = "long" if i % 3 else "short"
        rm = market_return(tape, asset, t[i0] + 7.0, t[i1] + 7.0, basket)
        signed = rm if direction == "long" else -rm
        r = beta * signed + alpha + rng.normal(0, noise)
        out.append({"position_id": f"p{i}", "symbol": f"{asset}/USD", "asset": asset,
                    "direction": direction, "era": "t", "entry_ts": t[i0] + 7.0,
                    "exit_ts": t[i1] + 7.0, "r_trade": r, "fees_usd": 0.0,
                    "entry_notional": 100.0})
    return out


# ------------------------------------------------------------------ defect 1
def test_alpha_is_the_intercept_not_the_mean_residual():
    """Plant +30 bps of alpha on a beta-1 book. The tool must read ~30 back
    and ALL THREE intervals must agree it is off zero."""
    tape = _tape()
    res = decompose(_trips(tape, alpha=0.0030), tape, min_trips=10, reps=300)
    g = res["groups"]["ALL"]
    assert g["alpha_bps"] == pytest.approx(30.0, abs=8.0), g
    assert g["beta"] == pytest.approx(1.0, abs=0.15), g
    assert g["alpha_ci_bps"][0] > 0 and g["alpha_ci_cr1_bps"][0] > 0, g
    assert g["alpha_signflip_p"] < 0.05 and g["alpha_clear_of_zero"] is True, g


def test_zero_alpha_reads_zero_and_nothing_calls_it_clear():
    tape = _tape(seed=9)
    res = decompose(_trips(tape, alpha=0.0, seed=8), tape, min_trips=10, reps=300)
    g = res["groups"]["ALL"]
    lo, hi = g["alpha_ci_bps"]
    assert lo < 0 < hi and g["alpha_clear_of_zero"] is False, g


def test_the_market_factor_excludes_the_traded_asset():
    tape = _tape()
    t = tape["BTC"][0]
    only_btc = {"BTC": tape["BTC"]}
    assert market_return(only_btc, "BTC", t[10], t[50], ("BTC",)) is None
    assert market_return(tape, "BTC", t[10] + 300, t[50] + 300) is not None


# ------------------------------------------------------------------ defect 2
def test_anchor_is_the_last_closed_bar_never_the_bar_containing_the_fill():
    """Bars open at 0/300/600 and CLOSE at 300/600/900. At t=299 nothing has
    closed; at 300..599 the only known close is bar 0's; bar 1's close is
    known from 600. The first version returned 2.0 at t=300 - a price that
    prints at t=600 - and the old pin asserted exactly that."""
    t = np.array([0.0, 300.0, 600.0])
    c = np.array([1.0, 2.0, 3.0])
    assert _close_at((t, c), 299.0) is None
    assert _close_at((t, c), 300.0) == 1.0
    assert _close_at((t, c), 599.0) == 1.0
    assert _close_at((t, c), 600.0) == 2.0
    assert _close_at((t, c), 5000.0) is None, "far outside the tape must be None"


def test_injection_a_price_move_after_the_fill_cannot_reach_the_factor():
    """Bump every basket close in the bar CONTAINING the fill and the bar
    after it: the market return must not move. Bump the last CLOSED bar and
    it must (so the pin is not vacuous)."""
    tape = _tape()
    t = tape["BTC"][0]
    t0, t1 = t[100] + 10.0, t[140] + 10.0            # inside bars 100 and 140
    base = market_return(tape, "PAXG", t0, t1)
    for i in (100, 101, 140, 141):                   # containing + next, both ends
        bumped = {a: (tt, cc * np.where(np.arange(len(cc)) == i, 1.5, 1.0))
                  for a, (tt, cc) in tape.items()}
        assert market_return(bumped, "PAXG", t0, t1) == pytest.approx(base), i
    seen = {a: (tt, cc * np.where(np.arange(len(cc)) == 99, 1.5, 1.0))
            for a, (tt, cc) in tape.items()}
    assert market_return(seen, "PAXG", t0, t1) != pytest.approx(base)


# ------------------------------------------------------------------ defect 3
def test_trips_beyond_the_tape_are_counted_by_era_with_their_gross():
    tape = _tape()
    trips = _trips(tape, n_trips=40)
    end = tape["BTC"][0][-1] + BAR_S
    trips.append({"position_id": "late", "symbol": "BTC/USD", "asset": "BTC",
                  "direction": "long", "era": "z", "entry_ts": end + 3600,
                  "exit_ts": end + 7200, "r_trade": -0.0052, "fees_usd": 0.0,
                  "entry_notional": 100.0})
    res = decompose(trips, tape, min_trips=10, reps=50)
    assert res["trips_total"] == 41 and res["trips_on_tape"] == 40
    assert res["dropped"] == 1 and res["dropped_by_era"] == {"z": {"beyond_tape": 1}}
    assert res["dropped_mean_gross_bps"] == pytest.approx(-52.0)
    assert set(res["tape_end_utc"]) == {"BTC", "ETH", "LINK"}
    assert res["last_fill_utc"] > res["tape_end_utc"]["BTC"]


# ------------------------------------------------------------------ defect 4
def test_a_gap_in_one_basket_member_drops_the_trip_instead_of_thinning_the_basket():
    tape = _tape(hole=("ETH", 500, 530))
    t = tape["BTC"][0]
    t0, t1 = t[510] + 10.0, t[560] + 10.0              # entry inside ETH's hole
    assert market_return(tape, "BTC", t0, t1) is None
    assert market_return(tape, "BTC", t0, t1, basket=("BTC", "LINK")) is not None
    trip = {"position_id": "g", "symbol": "BTC/USD", "asset": "BTC",
            "direction": "long", "era": "t", "entry_ts": t0, "exit_ts": t1,
            "r_trade": 0.0, "fees_usd": 0.0, "entry_notional": 100.0}
    res = decompose([trip], tape, min_trips=1, reps=10)
    assert res["dropped_by_era"] == {"t": {"basket_gap": 1}}


# ------------------------------------------------------------------ defect 5
def test_few_days_are_flagged_and_the_exact_signflip_p_is_calibrated_under_the_null():
    """8 day-clusters, alpha = 0, 100 bps noise, 40 seeds: the exact p must
    reject at ~5% (never above 15% here), CR1 likewise, and EVERY run must
    carry the n_eff < 10 flag that tells the reader the boot CI is thin."""
    tape = _tape(n=3300, seed=21)
    rej_p = rej_cr1 = 0
    for s in range(40):
        trips = _trips(tape, alpha=0.0, noise=0.01, seed=100 + s,
                       day_counts=[8] * 8)
        g = decompose(trips, tape, min_trips=10, reps=60)["groups"]["ALL"]
        assert g["few_eff_days"] is True and g["n_eff"] < 10, g
        assert g["signflip_method"] == "exact"
        rej_p += g["alpha_signflip_p"] < 0.05
        lo, hi = g["alpha_ci_cr1_bps"]
        rej_cr1 += not (lo < 0 < hi)
    assert rej_p <= 6, f"exact sign-flip rejected {rej_p}/40 under the null"
    assert rej_cr1 <= 6, f"CR1 rejected {rej_cr1}/40 under the null"


def test_one_dominant_day_shows_in_n_eff_and_lodo():
    tape = _tape(n=3300, seed=4)
    trips = _trips(tape, alpha=0.0, noise=0.003, seed=6,
                   day_counts=[40, 2, 2, 2, 2, 2, 2, 2])
    g = decompose(trips, tape, min_trips=10, reps=60)["groups"]["ALL"]
    assert g["days"] >= 8 and g["n_eff"] < 3.0, g
    assert g["lodo_beta"] and g["lodo_alpha_bps"], g


def test_the_bootstrap_in_the_tests_is_the_bootstrap_in_the_tool():
    """day_block_ci must be what decompose() calls: plant a slope only the
    refit can see and check both routes agree."""
    rng = np.random.default_rng(1)
    x = rng.normal(0, 0.01, 200)
    y = 2.0 * x + 0.001 + rng.normal(0, 0.001, 200)
    days = np.arange(200) // 10
    bci, aci = day_block_ci(x, y, days, reps=300)
    assert bci[0] < 2.0 < bci[1] and aci[0] < 0.001 < aci[1]
    tape = _tape()
    trips = _trips(tape, n_trips=60, beta=2.0, alpha=0.0)
    g = decompose(trips, tape, min_trips=10, reps=300)["groups"]["ALL"]
    assert g["beta_ci"][0] < 2.0 < g["beta_ci"][1] and g["beta_ci"][0] > 1.5, g


def test_clear_requires_every_route_to_exclude_zero_on_alphas_own_side():
    """The first cut printed ARB 'clear' on CR1 [-149, +12]: it tested
    min(ci)*sign > 0, which any negative-alpha interval passes. An interval
    excludes zero only when BOTH ends carry alpha's sign."""
    assert alpha_clear(-68.0, [-157.0, -6.0], [-149.0, 12.0], 0.016) is False
    assert alpha_clear(-68.0, [-157.0, -6.0], [-149.0, -12.0], 0.016) is True
    assert alpha_clear(-68.0, [-157.0, 6.0], [-149.0, -12.0], 0.016) is False
    assert alpha_clear(30.0, [5.0, 60.0], [2.0, 58.0], 0.01) is True
    assert alpha_clear(30.0, [-5.0, 60.0], [2.0, 58.0], 0.01) is False
    assert alpha_clear(30.0, [5.0, 60.0], [2.0, 58.0], 0.2) is False
    assert alpha_clear(30.0, None, [2.0, 58.0], 0.01) is None
    assert alpha_clear(0.0, [-1.0, 1.0], [-1.0, 1.0], 0.9) is None


def test_ols_cr1_signflip_and_t_crit_basics():
    x = np.array([0.0, 1.0, 2.0, 3.0])
    y = 2.0 * x + 0.5
    b, a, r2 = ols(x, y)
    assert (b, a) == pytest.approx((2.0, 0.5)) and r2 == pytest.approx(1.0)
    rng = np.random.default_rng(2)
    x = rng.normal(0, 1, 120)
    days = np.arange(120) // 10
    y = 1.0 * x + 0.5 + rng.normal(0, 0.1, 120)
    cr1 = cr1_intervals(x, y, days)
    assert cr1["df"] == 11 and cr1["alpha_ci"][0] < 0.5 < cr1["alpha_ci"][1]
    p, m = signflip_p(x, y, days, 1.0)
    assert m == "exact" and p < 0.01, (p, m)
    p2, m2 = signflip_p(x, y, np.arange(120) // 5, 1.0)
    assert m2 == "mc" and p2 < 0.01
    y0 = 1.0 * x + rng.normal(0, 0.1, 120)
    p3, _ = signflip_p(x, y0, days, 1.0)
    assert p3 > 0.05
    assert _t_crit(7)[0] == pytest.approx(2.365, abs=0.01)
    assert _t_crit(35)[0] == pytest.approx(2.030, abs=0.01)
    assert _t_crit(10_000)[0] == pytest.approx(1.960, abs=0.005)
