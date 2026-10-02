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


def test_daily_z_uses_only_days_before_the_event():
    """External series (funding, OI, supply) enter at the LAST COMPLETE day
    before the event: poisoning the event day and after changes nothing."""
    day = 86400.0
    t = np.arange(400) * day
    v = np.exp(np.cumsum(np.random.default_rng(2).normal(0, 0.01, 400)))
    at = np.array([300 * day, 350 * day])
    z0 = ad._daily_z(t, v, at, "chg7")
    v2 = v.copy()
    v2[300:] *= 50.0
    z1 = ad._daily_z(t, v2, at[:1], "chg7")
    assert np.isfinite(z0[0]) and z0[0] == pytest.approx(z1[0])
    assert np.isnan(ad._daily_z(t, v, np.array([50 * day]), "chg7")[0])   # needs history


def test_long_signals_sample_daily_and_follow_registered_signs():
    n = 24 * 400
    t = np.arange(n) * 3600.0
    x = np.linspace(0, 1, n)                                   # steady uptrend
    ext = {"funding": {"BTC": {"t": t[::8], "rate": np.full(n // 8, 1e-4)}},
           "oi": {}, "stables": {"t": np.array([]), "usd": np.array([])}}
    s = ad.long_signals({"BTC": x}, {"BTC": t}, ext)
    idx, sig = s["btc_tsmom_168"]["BTC"]
    assert np.all(t[idx] % 86400 == 0) and np.all(sig == 1)    # uptrend -> +1
    idx2, sig2 = s["funding_crowd"]["BTC"]
    assert np.all(sig2 == 0)                                   # flat funding: no crowding


def test_analyse_exports_per_block_series_for_the_ledger():
    rng = np.random.default_rng(5)
    t = np.sort(rng.uniform(0, 30 * ad.WEEK, 3000))
    X = rng.normal(0, 0.01, (3000, 2))
    r = ad.analyse(t, X, (1, 2), 100, rng, 1.0)
    s = r["series"]
    assert len(s["t"]) == r["weeks"] == len(s["x_bps"])
    assert len(s["x_bps"][0]) == 2                       # one value per horizon
    assert all(s["t"][i] < s["t"][i + 1] for i in range(len(s["t"]) - 1))


def _minutes(n, seed=6):
    rng = np.random.default_rng(seed)
    t = 1_730_419_200.0 + np.arange(n) * 60.0          # 2024-11-01 00:00 UTC
    vol = rng.uniform(1, 2, n)
    tb = vol * rng.uniform(0, 1, n)
    return t, vol, tb


def test_quarter_hour_signal_fires_only_at_the_marks_and_follows_flow():
    t, vol, tb = _minutes(60 * 24 * 40)
    idx, s = ad.qh_signal(t, vol, tb, window_marks=96 * 7, q=0.9)
    assert np.all(t[idx] % 900 == 0)
    imb = (2 * tb[idx] - vol[idx]) / vol[idx]
    on = s != 0
    assert on.any() and np.all(s[on] == np.sign(imb[on]))   # registered: continuation


def test_quarter_hour_signal_reads_nothing_after_the_mark():
    t, vol, tb = _minutes(60 * 24 * 40)
    idx, s = ad.qh_signal(t, vol, tb, window_marks=96 * 7, q=0.9)
    k = len(t) // 2
    vol2, tb2 = vol.copy(), tb.copy()
    tb2[k:] = vol2[k:]                                   # poison the future: all buys
    idx2, s2 = ad.qh_signal(t, vol2, tb2, window_marks=96 * 7, q=0.9)
    m = t[idx] < t[k]
    assert np.array_equal(idx[m], idx2[: m.sum()]) and np.array_equal(s[m], s2[: m.sum()])


def test_entry_close_index_prices_at_the_requested_time():
    """Bars are OPEN-stamped: the bar whose close equals ts opens at ts-1h."""
    t = 1_730_419_200.0 + np.arange(48) * 3600.0
    j = ad.entry_close_index(t, np.array([t[10], t[0]]), 3600.0)
    assert j[0] == 9 and j[1] == -1                      # no bar closes at t[0]


def test_funding_settle_enters_one_hour_before_and_exits_at_settlement():
    t = 1_730_419_200.0 + np.arange(24 * 30) * 3600.0
    ft = 1_730_419_200.0 + np.arange(3 * 30) * 8 * 3600.0
    rate = np.where(np.arange(len(ft)) % 2 == 0, 1e-4, -1e-4)
    idx, s = ad.funding_settle_signal(t, ft, rate)
    close_hours = (((t[idx] + 3600) % 86400) // 3600).astype(int)
    assert set(close_hours) == {7, 15, 23}               # entry price = 1 h before
    exit_hours = (((t[idx + 1] + 3600) % 86400) // 3600).astype(int)
    assert set(exit_hours) == {0, 8, 16}                 # 1-h horizon ends AT settlement
    for i, si in zip(idx, s):
        last = rate[np.searchsorted(ft, t[i] + 3600, side="right") - 1]
        assert si == -np.sign(last)
    rate2 = rate.copy()
    rate2[45:] *= -1
    idx2, s2 = ad.funding_settle_signal(t, ft, rate2)
    early = t[idx] + 3600 < ft[45]
    assert np.array_equal(s[early], s2[early])


FOMC_HTML = """
<div class="panel-heading"><h4><a id="1">2025 FOMC Meetings</a></h4></div>
<div class="fomc-meeting__month col-xs-5 col-sm-3 col-md-2"><strong>January</strong></div>
<div class="fomc-meeting__date col-xs-4 col-sm-9 col-md-10 col-lg-1">28-29</div>
<div class="fomc-meeting__month col-xs-5 col-sm-3 col-md-2"><strong>Apr/May</strong></div>
<div class="fomc-meeting__date col-xs-4 col-sm-9 col-md-10 col-lg-1">30-1*</div>
<div class="fomc-meeting__month col-xs-5 col-sm-3 col-md-2"><strong>July</strong></div>
<div class="fomc-meeting__date col-xs-4 col-sm-9 col-md-10 col-lg-1">29-30</div>
"""


def test_fomc_statement_times_parse_to_2pm_new_york_in_utc():
    ts = ad.parse_fomc(FOMC_HTML)
    import datetime as dt
    got = [dt.datetime.fromtimestamp(t, dt.timezone.utc) for t in ts]
    assert [g.strftime("%Y-%m-%d %H:%M") for g in got] == [
        "2025-01-29 19:00",          # EST: 14:00 ET = 19:00 UTC
        "2025-05-01 18:00",          # Apr/May straddle -> statement on May 1, EDT
        "2025-07-30 18:00"]


def test_gpr_signal_follows_spikes_and_reads_only_completed_days():
    day = 86400.0
    t = np.arange(400) * day
    v = 100.0 + np.random.default_rng(9).normal(0, 5, 400)   # a noisy, calm index
    v[300:307] = 400.0                                  # a geopolitical spike
    at = np.array([303 * day, 310 * day, 250 * day])
    s = ad.gpr_signal(at, t, v)
    assert s[0] == 1.0 and s[2] == 0.0                  # spike seen; calm day silent
    v2 = v.copy()
    v2[303:] = 0.0                                      # poison the event day onward
    assert ad.gpr_signal(at[:1], t, v2)[0] == ad.gpr_signal(at[:1], t, v)[0]


def test_gpr_dates_load_as_unix_seconds(tmp_path):
    """Units trap: Stata dates may arrive as datetime64[s] or [ns]; both must
    land on true UNIX seconds (an empty-looking join is the failure mode)."""
    import pandas as pd
    df = pd.DataFrame({"date": pd.to_datetime(["2026-09-30", "2026-10-01"]),
                       "GPRD": [100.0, 120.0]})
    df.to_stata(tmp_path / "gpr_daily.dta", write_index=False)
    g = ad.load_gpr(tmp_path)
    assert g["t"][1] == pytest.approx(1790812800.0)        # 2026-10-01 00:00 UTC
    assert list(g["v"]) == [100.0, 120.0]


def test_pre_event_window_ends_exactly_at_the_event():
    """M1: entry 24 h before the statement, 24-h horizon ends AT it."""
    t = 1_730_419_200.0 + np.arange(24 * 10) * 3600.0
    s_ = t[100]                                          # an event at a bar boundary
    j = ad.entry_close_index(t, np.array([s_ - 24 * 3600.0]), 3600.0)[0]
    assert t[j] + 3600 == s_ - 24 * 3600                 # entry close = event - 24 h
    assert t[j + 24] + 3600 == s_                        # +24 bars closes at the event


def test_relative_return_drift_adjusts_both_legs():
    a = np.array([[0.010, 0.020]])
    da = np.array([[0.004, 0.008]])
    basket = [np.array([0.006, 0.012]), np.array([0.002, 0.004])]
    dbasket = [np.array([0.001, 0.002]), np.array([0.001, 0.002])]
    rel = ad.relative_drift_adjusted(a[0] - da[0], basket, dbasket)
    assert rel == pytest.approx([0.006 - 0.003, 0.012 - 0.006])
