"""
Regression for the two literature-grounded defenses (schema v6):

TH-015 barclose_herd — no-code/indicator bots evaluate on candle close,
so their activity clusters in the first seconds after bar boundaries
(intraday-periodicity literature: 30s bursts every 5 minutes). The
detector buckets top-of-book change events by phase-of-bar; herding =
excess share in bucket zero.

Osler round-number stop hygiene — stops cluster at 00/50 levels and
cascades fire just AFTER price crosses one (Osler, Stop-Loss Orders and
Price Cascades in Currency Markets). Since cut #7 (2026-08-11) our stop
never rests inside the cascade band: nudged BEYOND the level (widen-only),
so the herd's clustered stops fire first and ours only on a genuine
break. This paragraph's first version still described the retired
tighten-side reading after the tests below were flipped — the flip
comment above the Osler tests is the authoritative record.
"""
from risk.stop_placement import nudge_stop_off_round
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


# SEMANTIC FLIP (cut #7, 2026-08-11, operator-adjudicated): these tests
# previously pinned TIGHTEN-side nudges (long stop moved ABOVE the level -
# "exit before the cascade"), under which any sweep TO a round level ejected
# the position: the shakeout the bull-readiness directive names. They now
# pin WIDEN-BEYOND (long below / short above the level) - the herd's
# clustered stops fire first, ours only if the level actually breaks. The
# flip is deliberate, documented in risk/stop_placement.py, and these
# assertions changing direction IS the record of it.

def test_osler_long_stop_nudged_beyond_round_level():
    # 62998 rests 0.3bps under BTC's 63000 level: inside the cascade band.
    # Widen-beyond: rest BELOW 63000, past the cluster.
    out = nudge_stop_off_round(62998.0, "long", 5.0, 5.0)
    assert out < 63000.0
    assert out < 62998.0, "the nudge may only WIDEN a long stop"
    assert abs(out - (63000.0 - 63000.0 * 5e-4)) < 40.0


def test_osler_short_stop_nudged_beyond_round_level():
    out = nudge_stop_off_round(1799.5, "short", 5.0, 5.0)
    assert out > 1800.0
    assert out > 1799.5, "the nudge may only WIDEN a short stop"


def test_osler_far_stops_and_disabled_are_untouched():
    assert nudge_stop_off_round(62711.0, "long", 5.0, 5.0) == 62711.0
    assert nudge_stop_off_round(62998.0, "long", 0.0, 5.0) == 62998.0
    assert nudge_stop_off_round(62998.0, "long", 5.0, 0.0) == 62998.0


def test_osler_small_price_lattice():
    # MINA ~0.45: half-step lattice every 0.005 -> 0.4501 in 0.450's band;
    # widen-beyond rests below 0.450
    out = nudge_stop_off_round(0.4501, "long", 5.0, 5.0)
    assert out < 0.450
