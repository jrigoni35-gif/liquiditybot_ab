"""scripts/alpha_decay_report.py - the instrument is pinned before its
readings are trusted. No network: synthetic data only."""
import numpy as np
import pytest

from scripts import alpha_decay_report as ad


def test_timestamp_units_are_normalised_and_counted():
    s = 1_790_000_000
    t, u = ad.to_seconds(np.array([s, s * 1e3, s * 1e6]))
    assert np.allclose(t, s)
    assert u == {"us": 1, "ms": 1, "s": 1}


def test_forward_returns_and_past_only_drift():
    lp = np.log(np.array([100, 101, 103, 102, 106.0]))
    F = ad.forward(lp, (1, 2))
    assert F[0, 0] == pytest.approx(lp[1] - lp[0])
    assert F[3, 1] != F[3, 1]                       # NaN past the end
    D = ad.expanding_drift(lp, (1,), warm=2)
    assert np.isnan(D[1, 0])
    assert D[3, 0] == pytest.approx((lp[3] - lp[0]) / 3)   # uses bars <= 3 only


def test_fit_recovers_a_known_decay_and_stays_in_window():
    h = np.array(ad.H_PANEL, float)
    A, tau = 0.006, 24.0
    car = A * (1 - np.exp(-h / tau))
    a_hat, t_hat = ad.fit_decay(car, h, np.ones_like(h))
    assert a_hat[0] == pytest.approx(A, rel=0.05)
    assert t_hat[0] == pytest.approx(tau, rel=0.1)
    lin = 1e-5 * h                                   # never decays: no asymptote
    a2, t2 = ad.fit_decay(lin, h, np.ones_like(h))
    assert t2[0] <= h.max() + 1e-9                   # amendment 1: no extrapolation
    assert a2[0] <= lin[-1] / (1 - np.exp(-1)) + 1e-12


def test_week_bootstrap_ci_covers_truth_on_noise():
    rng = np.random.default_rng(1)
    n = 20_000
    t = np.sort(rng.uniform(0, 200 * ad.WEEK, n))
    X = rng.normal(0, 0.01, (n, 3))
    r = ad.analyse(t, X, (1, 2, 4), 400, rng, 1.0)
    assert r["weeks"] == 200
    lo, hi = r["car_ci_bps"][0]
    assert lo < 0 < hi


def test_holm_is_monotone_and_bounded():
    h = ad.holm({"a": 0.01, "b": 0.04, "c": 0.03})
    assert h["a"] == pytest.approx(0.03)
    assert h["c"] == pytest.approx(0.06) and h["b"] == pytest.approx(0.06)
    assert all(0 <= v <= 1 for v in h.values())


def _panel(n=3000, assets=("A", "B", "C", "D", "E", "F"), seed=3):
    rng = np.random.default_rng(seed)
    lp = {a: np.cumsum(rng.normal(0, 0.01, n)) for a in assets}
    vol = {a: rng.uniform(1, 2, n) for a in assets}
    tb = {a: vol[a] * rng.uniform(0, 1, n) for a in assets}
    tt = {a: np.arange(n) * 3600.0 for a in assets}
    return lp, vol, tb, tt


def test_signals_read_nothing_after_t():
    """Poison every bar after k: every signal value at <= k is unchanged."""
    lp, vol, tb, tt = _panel()
    k = 2500
    base = ad.panel_signals(lp, vol, tb, tt)
    lp2 = {a: x.copy() for a, x in lp.items()}
    vol2 = {a: x.copy() for a, x in vol.items()}
    tb2 = {a: x.copy() for a, x in tb.items()}
    for a in lp2:
        lp2[a][k + 1:] += 5.0 * np.sign(np.sin(np.arange(len(lp2[a]) - k - 1)))
        vol2[a][k + 1:] *= 9.0
        tb2[a][k + 1:] = vol2[a][k + 1:]
    pois = ad.panel_signals(lp2, vol2, tb2, tt)
    for name in base:
        for a in base[name]:
            assert np.array_equal(base[name][a][: k + 1], pois[name][a][: k + 1]), name


def test_xs_momentum_ranks_thirds():
    lp, vol, tb, tt = _panel()
    s = ad.panel_signals(lp, vol, tb, tt)["xs_mom_168"]
    i = 500
    col = np.array([s[a][i] for a in sorted(s)])
    assert (col == 1).sum() == 2 and (col == -1).sum() == 2
    rets = np.array([lp[a][i] - lp[a][i - 168] for a in sorted(s)])
    assert rets[col == 1].min() > rets[col == -1].max()


def test_verdict_requires_both_halves_and_holm():
    r = {"A_ci_bps": [60.0, 90.0], "A_bps": 75.0,
         "halves": {"first": {"A_bps": 70.0}, "second": {"A_bps": 30.0}}}
    assert ad._verdict(r, 0.001, 0.001) != "TRADEABLE AS TRIPS"
    r["halves"]["second"]["A_bps"] = 80.0
    assert ad._verdict(r, 0.001, 0.001) == "TRADEABLE AS TRIPS"
    assert ad._verdict(r, 0.001, 0.2) != "TRADEABLE AS TRIPS"


def test_rolling_helpers_equal_an_explicit_past_only_reference():
    """Value at t must equal the statistic of x[t-n : t] exactly - so ANY
    peek at x[t] or later is caught at every index, not just near a cut."""
    rng = np.random.default_rng(8)
    x = rng.normal(0, 1, 400)
    n = 50
    sd = ad.rolling_std_past(x, n)
    qq = ad.rolling_quantile_past(x, n, 0.9)
    for t in range(n, len(x)):
        ref = x[t - n:t]
        assert sd[t] == pytest.approx(ref.std(ddof=1), rel=1e-9)
        assert qq[t] == pytest.approx(np.quantile(ref, 0.9), rel=1e-9)
    assert np.all(np.isnan(sd[:n])) and np.all(np.isnan(qq[:n]))


def test_signals_read_nothing_after_t_at_many_cuts():
    lp, vol, tb, tt = _panel(n=1800)
    base = ad.panel_signals(lp, vol, tb, tt)
    for k in range(900, 1800, 37):
        lp2 = {a: x.copy() for a, x in lp.items()}
        vol2 = {a: x.copy() for a, x in vol.items()}
        tb2 = {a: x.copy() for a, x in tb.items()}
        for a in lp2:
            lp2[a][k + 1:] -= 3.0
            tb2[a][k + 1:] = 0.0
        pois = ad.panel_signals(lp2, vol2, tb2, tt)
        for name in base:
            for a in base[name]:
                assert np.array_equal(base[name][a][: k + 1], pois[name][a][: k + 1]), (name, k)


def test_entry_is_the_close_of_the_bar_opening_at_signal_ts():
    """Amendment 2: signal_ts is a bar-OPEN stamp. A signal stamped at the
    open of bar k is priced at bar k's close - never bar k-1's (one bar
    early = credit for a move the bot had already seen)."""
    opens = np.arange(10) * 300.0 + 1_790_000_000
    j = ad.entry_index(opens, np.array([opens[4], opens[4] + 120.0]))
    assert list(j) == [4, 4]
