"""tests/test_audit_regime_strategy.py — audit fixes, regime + strategy group.

Covers, one section per finding:

  H9  regime/correlation.update_intraday folded one CALLER INVOCATION as one
      aligned time step. Per-asset candle refresh is budgeted (3 pairs/cycle),
      so half the universe hands back a byte-identical cached close on any
      given call — folded as a real 0.0 return, which meant cross-refresh-group
      covariance entries were never updated together and corr/beta read ~0.00
      forever. hedging.min_hedge_correlation is 0.55, so the hedge gate was
      structurally dead for exactly the assets that carried the exposure.
  M7  update_turbulence stacked daily series by LIST POSITION with no timestamp
      read, so one stale/short venue series sheared every column by a day, and
      every feed's forming bar was scored as if it were a completed day.
  M8  informed_flow's funding_pass_when_unavailable=False was a no-op: the
      "unavailable" case fell through to the numeric branch where the merge's
      0.0 placeholder always satisfied the cap.
  LOW macro_regime's TSMOM bear cut sat on the wrong side of the 3-lookback
      lattice point (-1/3 > -0.34), so the documented "2 of 3 agree" bear
      trigger silently demanded unanimity and the intended asymmetry inverted.
  LOW sentiment's fear/euphoria volume gate was trivially satisfied on the
      second poll after every restart: a population z-score is bounded by
      sqrt(n-1) and is pinned to exactly +-1.0 at n=2.
"""

import logging
import math

import numpy as np
import pytest

from regime.correlation import CorrelationEngine
from regime.macro_regime import (MacroRegimeEngine, MacroRegimeState,
                                 tsmom_lattice, tsmom_threshold_conflict)
from sentiment.scanner import SentimentScanner
from strategies.informed_flow import InformedFlowEngine

DAY = 86400.0


# ===========================================================================
# H9 — intraday correlation must survive staggered per-asset candle refresh
# ===========================================================================
def _correlated_paths(assets, n_bars, rho=0.8, seed=11):
    """Price paths sharing a common factor; pairwise return corr ~= rho."""
    rng = np.random.default_rng(seed)
    common = rng.normal(0.0, 0.01, n_bars)
    out = {}
    for a in assets:
        idio = rng.normal(0.0, 0.01, n_bars)
        r = math.sqrt(rho) * common + math.sqrt(1.0 - rho) * idio
        out[a] = list(100.0 * np.exp(np.cumsum(r)))
    return out


def _staggered_cycles(paths, group_a, group_b, n_bars):
    """Replay the shipped fetch-budget pattern: group A's cache commits a new
    bar on even cycles, group B's on odd ones, and in between each asset hands
    back the SAME cached close. Yields (closes, bar_ts) per cycle."""
    for i in range(2, 2 * n_bars):
        idx = {**{a: i // 2 for a in group_a},
               **{b: (i - 1) // 2 for b in group_b}}
        yield ({a: paths[a][k] for a, k in idx.items()},
               {a: float(k) * 300.0 for a, k in idx.items()})


def _replay(cfg, use_ts, n=260, rho=0.8):
    ga, gb = ["SUI", "MINA", "FLOW"], ["ARB", "BTC", "ETH"]
    paths = _correlated_paths(ga + gb, n, rho=rho)
    eng = CorrelationEngine(cfg)
    for closes, ts in _staggered_cycles(paths, ga, gb, n):
        eng.update_intraday(closes, ts if use_ts else None)
    return eng


def test_h9_cross_group_correlation_survives_staggered_refresh():
    """With bar timestamps the estimator recovers the true structure even
    though the two refresh groups NEVER arrive on the same call."""
    eng = _replay({}, use_ts=True)
    for a in ("SUI", "MINA", "FLOW"):
        for b in ("ARB", "BTC", "ETH"):
            c = eng.state.corr(a, b)
            assert c > 0.60, f"{a}-{b} corr collapsed to {c:.4f}"
            # hedging.py's floor is 0.55 — below it the hedge is skipped
            assert c > 0.55
            assert abs(eng.state.beta(a, b)) > 0.30, f"{a}-{b} beta dead"


def test_h9_old_positional_folding_is_the_defect():
    """Control: the OLD behaviour, reachable via the documented rollback
    knob. Folding by arrival position drives every cross-group pair to ~0 —
    the wrong SIGN here — which is what killed the hedge correlation gate."""
    eng = _replay({"align_intraday_by_bar": False}, use_ts=False)
    assert abs(eng.state.corr("SUI", "ARB")) < 0.20
    assert eng.state.corr("SUI", "ARB") < 0.55       # gate structurally dead


def test_h9_untimestamped_caller_is_improved_but_not_repaired():
    """HONEST BOUND. Without bar_ts the only evidence a series advanced is
    the close changing, which removes the fabricated 0.0 returns but CANNOT
    recover the phase: the two groups learn about the same bar on different
    calls, so their returns stay one bar apart. Cross-group correlation is no
    longer inverted, but it does not clear the 0.55 hedge floor — main.py's
    caller must pass the bar timestamps for that (cross-file dependency)."""
    old = _replay({"align_intraday_by_bar": False}, use_ts=False)
    new = _replay({}, use_ts=False)
    exact = _replay({}, use_ts=True)
    assert new.state.corr("SUI", "ARB") > old.state.corr("SUI", "ARB")
    assert new.state.corr("SUI", "ARB") < exact.state.corr("SUI", "ARB")
    # within a refresh group (which does arrive together) it is exact
    assert new.state.corr("SUI", "MINA") == pytest.approx(
        exact.state.corr("SUI", "MINA"), abs=0.05)


def test_h9_repeated_bar_timestamp_is_not_a_zero_return():
    eng = CorrelationEngine({})
    eng.update_intraday({"A": 100.0, "B": 200.0}, {"A": 0.0, "B": 0.0})
    eng.update_intraday({"A": 101.0, "B": 202.0}, {"A": 300.0, "B": 300.0})
    before = dict(eng.state.corr_fast)
    # same bar re-delivered (cache not refreshed) — and even a drifting close
    # on an unchanged bar is an intrabar tick, not a new observation
    for _ in range(5):
        eng.update_intraday({"A": 101.5, "B": 201.0}, {"A": 300.0, "B": 300.0})
    assert eng.state.corr_fast == before, "a re-delivered bar was folded"


def test_h9_one_dead_series_cannot_stall_the_estimator():
    """The alignment wait is bounded: a frozen feed delays at most
    align_max_wait_evals calls, it never deadlocks the live pairs."""
    eng = CorrelationEngine({"align_max_wait_evals": 3})
    px = {"A": 100.0, "B": 200.0, "DEAD": 50.0}
    ts = {"A": 0.0, "B": 0.0, "DEAD": 0.0}
    eng.update_intraday(px, ts)
    for i in range(1, 30):
        px = {"A": 100.0 + i, "B": 200.0 - 0.4 * i, "DEAD": 50.0}
        ts = {"A": i * 300.0, "B": i * 300.0, "DEAD": 0.0}
        eng.update_intraday(px, ts)
    assert eng.state.corr_fast, "live pairs never folded behind a dead series"
    assert abs(eng.state.corr("A", "B")) > 0.5


def test_h9_signature_stays_backward_compatible():
    eng = CorrelationEngine({})
    for i in range(1, 30):
        eng.update_intraday({"BTC": 100.0 + i, "ETH": 100.0 + 0.5 * i})
    assert eng.state.corr("BTC", "ETH") > 0.5


# ===========================================================================
# M7 — turbulence joins daily series on the bar timestamp, not list position
# ===========================================================================
def _daily(returns, t0=1_600_000_000.0, px0=100.0):
    """Daily candles from a return series; bar 0 is the anchor (no return)."""
    out, px = [], px0
    for i, r in enumerate([0.0] + list(returns)):
        px *= math.exp(r)
        out.append({"time": t0 + i * DAY, "open": px, "high": px * 1.001,
                    "low": px * 0.999, "close": px, "volume": 10.0})
    return out


def _shear_fixture(n=200, shock_day=197, seed=5):
    """Two co-moving assets; the last SHARED day is a violent DIVERGENCE (the
    thing turbulence exists to catch). Asset B's series is one bar short — the
    routine 'one venue polled a beat later' case — which under positional
    stacking shears every column by a day."""
    rng = np.random.default_rng(seed)
    r = rng.normal(0.0, 0.01, n)
    ra, rb = r.copy(), r.copy()
    ra[shock_day], rb[shock_day] = 0.15, -0.15
    a = _daily(ra)
    b = _daily(rb)
    return {"A": a, "B": b[:-1]}


def test_m7_timestamp_join_scores_the_shared_day():
    eng = CorrelationEngine({})
    eng.update_turbulence(_shear_fixture())
    # aligned: the last completed shared day IS the divergence -> extreme
    assert eng.state.turbulence_pct >= 99.0, eng.state.turbulence_pct


def test_m7_positional_stacking_would_miss_it():
    """Control: reproduce the OLD positional stack over the same fixture and
    show the crisis tell lands on the wrong row."""
    fx = _shear_fixture()
    assets = sorted(fx)
    n = min(len(fx[a]) for a in assets)
    R = np.column_stack([
        np.diff(np.log(np.array([c["close"] for c in fx[a][-n:]], float)))
        for a in assets])
    mu, cov = R.mean(axis=0), np.cov(R, rowvar=False)
    cov += np.eye(cov.shape[0]) * (np.trace(cov) / cov.shape[0]) * 0.05
    d = np.einsum("ij,jk,ik->i", R - mu, np.linalg.inv(cov), R - mu)
    assert float((d < d[-1]).mean() * 100.0) < 95.0, \
        "fixture must actually be missed by positional stacking"


def test_m7_forming_bar_is_excluded():
    """Every venue feed requests include_forming=True. Turbulence scores
    exactly ONE row, so a partial day must not reach the estimator: mutating
    the newest bar of each series may not move the reading at all."""
    fx = _shear_fixture()
    eng_a = CorrelationEngine({})
    eng_a.update_turbulence(fx)
    base = eng_a.state.turbulence
    assert base > 0.0
    forming = {k: v[:-1] + [dict(v[-1], close=v[-1]["close"] * 1.30)]
               for k, v in fx.items()}
    eng_b = CorrelationEngine({})
    eng_b.update_turbulence(forming)
    assert eng_b.state.turbulence == pytest.approx(base, rel=1e-12)


def test_m7_unshared_days_are_not_paired():
    """Disjoint calendars produce NO reading rather than a fabricated one."""
    fx = _shear_fixture()
    shifted = [dict(c, time=c["time"] + 500 * DAY) for c in fx["B"]]
    eng = CorrelationEngine({})
    eng.update_turbulence({"A": fx["A"], "B": shifted})
    assert eng.state.turbulence == 0.0 and eng.state.turbulence_pct == 50.0


def test_m7_venue_day_boundary_offset_still_joins():
    """OKX 1D rolls 16:00 UTC, Kraken 1440 rolls 00:00 UTC. The join must
    still pair them (2/3 overlap is the best the data supports) rather than
    silently killing the index on an empty exact-timestamp intersection."""
    fx = _shear_fixture()
    okx = [dict(c, time=c["time"] - 8 * 3600.0) for c in fx["B"]]
    eng = CorrelationEngine({})
    eng.update_turbulence({"A": fx["A"], "B": okx})
    assert eng.state.turbulence_pct >= 99.0


# ===========================================================================
# M8 — informed_flow's strict funding policy must actually veto
# ===========================================================================
def _if_view(**over):
    v = {"kraken_symbol": "ETH/USD", "imbalance_ratio": 1.0,
         "funding_rate": 0.0,
         "candles": [{"time": i * 300, "open": 100.0, "high": 100.6,
                      "low": 99.4, "close": 100.0 + 0.05 * i,
                      "volume": 10.0} for i in range(40)]}
    v.update(over)
    return v


def test_m8_strict_mode_vetoes_on_unavailable_funding():
    eng = InformedFlowEngine({"funding_pass_when_unavailable": False})
    r = eng.evaluate_asset("ETH", _if_view(funding_available=False,
                                           funding_rate=0.0))
    assert r.gates_passed["if_4_funding_sanity"] is False
    assert r.all_confirmed is False


def test_m8_default_mode_still_passes_on_unavailable_funding():
    eng = InformedFlowEngine({})
    r = eng.evaluate_asset("ETH", _if_view(funding_available=False,
                                           funding_rate=0.0))
    assert r.gates_passed["if_4_funding_sanity"] is True


@pytest.mark.parametrize("strict", [True, False])
def test_m8_a_real_rate_is_judged_numerically_in_both_modes(strict):
    eng = InformedFlowEngine({"funding_pass_when_unavailable": not strict})
    ok = eng.evaluate_asset("ETH", _if_view(funding_available=True,
                                            funding_rate=0.0))
    bad = eng.evaluate_asset("ETH", _if_view(funding_available=True,
                                             funding_rate=0.05))
    assert ok.gates_passed["if_4_funding_sanity"] is True
    assert bad.gates_passed["if_4_funding_sanity"] is False


def test_m8_non_numeric_rate_is_unavailable_not_zero():
    """A None/garbage rate on a nominally-available feed is missing data, not
    a real 0% print — the whole point of the disambiguation."""
    strict = InformedFlowEngine({"funding_pass_when_unavailable": False})
    r = strict.evaluate_asset("ETH", _if_view(funding_available=True,
                                              funding_rate=None))
    assert r.gates_passed["if_4_funding_sanity"] is False
    lenient = InformedFlowEngine({})
    r2 = lenient.evaluate_asset("ETH", _if_view(funding_available=True,
                                                funding_rate=float("nan")))
    assert r2.gates_passed["if_4_funding_sanity"] is True


# ===========================================================================
# LOW — TSMOM thresholds are cuts on a LATTICE, not on a continuum
# ===========================================================================
def test_tsmom_lattice_is_the_only_reachable_score_set():
    assert tsmom_lattice(3) == pytest.approx([1.0, 1 / 3, -1 / 3, -1.0])
    assert len(tsmom_lattice(4)) == 5


def test_tsmom_guard_flags_a_threshold_beside_a_lattice_point():
    # the shipped constant: 0.0067 BELOW the -1/3 level it documents including
    assert tsmom_threshold_conflict(-0.34, 3) == pytest.approx(-1 / 3)
    assert tsmom_threshold_conflict(0.34, 3) == pytest.approx(1 / 3)
    # mid-gap cuts are unambiguous
    assert tsmom_threshold_conflict(-0.10, 3) is None
    assert tsmom_threshold_conflict(0.67, 3) is None


def test_tsmom_guard_repairs_the_shipped_value_and_says_so(caplog):
    with caplog.at_level(logging.ERROR, logger="liquiditybot.regime.macro"):
        eng = MacroRegimeEngine({"momentum_bear_max": -0.34})
    assert tsmom_threshold_conflict(eng.mom_bear_max, 3) is None
    assert -1 / 3 < eng.mom_bear_max < 0.0
    assert any("momentum_bear_max" in r.getMessage() for r in caplog.records)


def test_two_of_three_lookbacks_trigger_bear_with_a_drawdown():
    """The documented rule: 2-of-3 bearish votes PLUS a >=20% drawdown is a
    bear regime. Under the old -0.34 cut the -1/3 score failed `<=` and the
    label stayed 'range' — longs allowed, not even flagged counter-trend."""
    eng = MacroRegimeEngine({})
    st = MacroRegimeState(asset="ETH", hmm_label="range",
                          momentum_score=-1 / 3, drawdown_pct=26.0,
                          vol_percentile=50.0)
    assert eng._ensemble_label(st, None) == "bear"
    assert eng.playbooks["bear"]["direction_bias"] == "short"


def test_bear_stays_asymmetrically_cheaper_than_bull():
    eng = MacroRegimeEngine({})
    # 2 of 3 bullish is NOT enough for bull on the momentum path (3/3 is)
    st = MacroRegimeState(asset="ETH", hmm_label="range",
                          momentum_score=1 / 3, drawdown_pct=0.0,
                          vol_percentile=50.0)
    assert eng._ensemble_label(st, None) == "range"
    st.momentum_score = 1.0
    assert eng._ensemble_label(st, None) == "bull_quiet"


def test_two_of_three_without_a_drawdown_is_still_not_bear():
    """The drawdown confirmation is the other half of the rule and must
    survive the threshold fix — this is not a widening."""
    eng = MacroRegimeEngine({})
    st = MacroRegimeState(asset="ETH", hmm_label="range",
                          momentum_score=-1 / 3, drawdown_pct=5.0,
                          vol_percentile=50.0)
    assert eng._ensemble_label(st, None) == "range"


# ===========================================================================
# LOW — sentiment volume spike needs a sample count, not just an sd
# ===========================================================================
def _rss(n_items, title="Crypto crash deepens: panic selling and "
                        "liquidations as market collapses"):
    items = "".join(f"<item><title>{title} {i}</title></item>"
                    for i in range(n_items))
    return ('<?xml version="1.0"?><rss version="2.0"><channel>'
            + items + "</channel></rss>")


def _scanner(counts, **cfg):
    """Scanner whose successive polls see len(counts) headline counts."""
    seq = list(counts)
    state = {"i": 0}

    def fetch(_url):
        k = seq[min(state["i"], len(seq) - 1)]
        state["i"] += 1
        return _rss(k)

    base = {"enabled": True, "poll_minutes": 0,
            "news_feeds": [{"url": "https://x.example/rss", "weight": 1.0}]}
    base.update(cfg)
    return SentimentScanner(base, fetch=fetch)


def test_sentiment_second_poll_after_restart_cannot_spike():
    """n=2 pins the population z-score to exactly +-1.0, so ANY increase
    cleared the >= 1.0 gate. _volume_hist is not persisted, so this fired on
    ~half of all restarts."""
    sc = _scanner([3, 5])
    s0 = sc.maybe_poll(1000.0)
    s1 = sc.maybe_poll(2000.0)
    assert s1.score <= sc.fear_threshold, "fixture must be bearish"
    assert s0.fear_spike is False
    assert s1.volume_z == 0.0
    assert s1.fear_spike is False, "cold history manufactured a fear spike"


def test_sentiment_warmup_is_gated_on_sample_count_not_just_sd():
    sc = _scanner([3, 4, 5, 6, 7, 8, 9, 10])
    for i in range(sc.min_volume_samples - 1):
        snap = sc.maybe_poll(1000.0 * (i + 1))
        assert snap.volume_z == 0.0, f"poll {i} priced a spike on n={i + 1}"
        assert snap.fear_spike is False and snap.euphoria_spike is False
    snap = sc.maybe_poll(1000.0 * (sc.min_volume_samples + 1))
    assert snap.volume_z != 0.0, "gate must open once the history is real"


def test_sentiment_min_samples_floor_cannot_be_configured_away():
    """|z| <= sqrt(n-1): below n = z_gate^2 + 2 the gate is not a spike
    detector, so no config value may take it there."""
    sc = _scanner([3, 5], min_volume_samples=2)
    assert sc.min_volume_samples >= 3
    assert math.sqrt(sc.min_volume_samples - 1) > sc.volume_spike_z


def test_sentiment_a_genuine_spike_still_fires():
    """The fix must not deaden the detector: a real surge on a warm history
    still sets fear_spike."""
    sc = _scanner([5] * 12 + [60])
    for i in range(13):
        snap = sc.maybe_poll(1000.0 * (i + 1))
    assert snap.volume_z >= sc.volume_spike_z
    assert snap.fear_spike is True
