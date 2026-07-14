"""
Regression for the two literature-grounded defenses (schema v6):

TH-015 barclose_herd — no-code/indicator bots evaluate on candle close,
so their activity clusters in the first seconds after bar boundaries
(intraday-periodicity literature: 30s bursts every 5 minutes). The
detector buckets top-of-book change events by phase-of-bar; herding =
excess share in bucket zero.

Osler round-number stop hygiene — stops cluster at 00/50 levels and
cascades fire just AFTER price crosses one (Osler, Stop-Loss Orders and
Price Cascades in Currency Markets). Our stop never rests inside the
cascade band: nudged to the safe side, only ever tightening.
"""
from main import nudge_stop_off_round_number
from strategies.thales import ThalesEngine


def _engine():
    return ThalesEngine({"enabled": True, "influence": "shadow",
                         "barclose": {"buckets": 10, "bar_sec": 300,
                                      "min_events": 20}})


def _feed(eng, times, tops):
    st = eng._st("BTC")
    for t, top in zip(times, tops):
        bids = [[top, 1.0]]
        asks = [[top + 1.0, 1.0]]
        eng._update_barclose(st, bids, asks, t)
    return st


def test_barclose_herding_scores_high():
    eng = _engine()
    # 40 top-of-book changes, all within the first 30s of each bar
    times, tops, p = [], [], 100.0
    for bar in range(40):
        t = bar * 300.0 + 5.0
        p += 1.0
        times.append(t)
        tops.append(p)
    st = _feed(eng, times, tops)
    assert eng._barclose_score(st) > 0.9


def test_uniform_activity_scores_near_zero():
    eng = _engine()
    times, tops, p = [], [], 100.0
    for i in range(200):
        t = (i * 37.0) % 30000            # spread across all phases
        p += 1.0
        times.append(t)
        tops.append(p)
    st = _feed(eng, sorted(times), tops)
    assert eng._barclose_score(st) < 0.25


def test_min_events_gate_returns_zero():
    eng = _engine()
    st = _feed(eng, [5.0, 305.0], [100.0, 101.0])
    assert eng._barclose_score(st) == 0.0


def test_feature_scores_carry_barclose():
    eng = _engine()
    assert "barclose" in eng.feature_scores("NEVER_SEEN", 0.0)


def test_osler_long_stop_nudged_above_round_level():
    # 62998 rests 0.3bps under BTC's 63000 level: inside the cascade band
    out = nudge_stop_off_round_number(62998.0, "long", 5.0)
    assert out > 63000.0
    assert abs(out - 63000.0 * 1.0005) < 1.0


def test_osler_short_stop_nudged_below_round_level():
    out = nudge_stop_off_round_number(1799.5, "short", 5.0)
    assert out < 1800.0


def test_osler_far_stops_and_disabled_are_untouched():
    assert nudge_stop_off_round_number(62711.0, "long", 5.0) == 62711.0
    assert nudge_stop_off_round_number(62998.0, "long", 0.0) == 62998.0


def test_osler_small_price_lattice():
    # MINA ~0.45: lattice every 0.005 -> 0.4501 sits on 0.450's band
    out = nudge_stop_off_round_number(0.4501, "long", 5.0)
    assert out > 0.450 and abs(out - 0.450 * 1.0005) < 1e-4
