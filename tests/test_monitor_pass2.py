"""tests/test_monitor_pass2.py — the carry-corrected margin barrier.

Pins the bug pass 1 shipped: quoting the margin call as a STATIC price.
Used margin is pinned at open while rollover drains equity, so the call
price translates upward at carry/units per day. A regression that drops
the carry term makes a position look safe for a month that is in fact
called in 28 days at a perfectly flat price.
"""

import pytest

from monitor.pass2 import Position, fee_tier

# the 2026-09-04 account screen, kept as the fixture the numbers below cite
ACCOUNT = Position()


def test_cash_balance_inverts_the_quoted_equity():
    # equity 778.99 quoted at 0.02723 against a 0.02793 basis
    assert ACCOUNT.cash_balance == pytest.approx(842.2237, abs=1e-3)


def test_used_margin_matches_notional_over_leverage():
    assert ACCOUNT.units * ACCOUNT.avg / 3 == pytest.approx(ACCOUNT.used_margin, abs=0.20)


def test_day_zero_call_and_liquidation():
    assert ACCOUNT.threshold_px(0.80, 0) == pytest.approx(0.026053, abs=1e-5)
    assert ACCOUNT.threshold_px(0.40, 0) == pytest.approx(0.022326, abs=1e-5)


def test_the_call_barrier_MOVES_with_carry():
    """The whole point of pass 2: it is a slope, not a level."""
    day0 = ACCOUNT.threshold_px(0.80, 0)
    day31 = ACCOUNT.threshold_px(0.80, 31)
    assert day31 > day0, "carry must translate the barrier UPWARD"
    assert day31 == pytest.approx(0.027350, abs=1e-5)
    slope = ACCOUNT.carry_per_day / ACCOUNT.units
    assert (day31 - day0) / 31 == pytest.approx(slope, rel=1e-9)
    # by the horizon the call has walked through the live bid (0.02740)
    assert day31 > 0.0273


def test_runway_at_a_flat_price_is_finite_and_short():
    assert ACCOUNT.runway_days(0.80) == pytest.approx(28.12, abs=0.05)


# --- repricing: a snapshot is not a current reading ----------------------

def test_equity_at_snapshot_point_reproduces_the_snapshot():
    assert ACCOUNT.equity_at() == pytest.approx(ACCOUNT.equity, abs=1e-6)
    assert ACCOUNT.equity_at(ACCOUNT.equity_px, 0.0) == pytest.approx(ACCOUNT.equity, abs=1e-6)


def test_equity_reprices_with_price_and_ages_with_carry():
    # the 2026-09-05 move: mid 0.02855, one day of carry
    assert ACCOUNT.equity_at(0.02855, 1.0) == pytest.approx(894.45, abs=0.02)
    # carry alone strictly reduces equity
    assert ACCOUNT.equity_at(ACCOUNT.equity_px, 1.0) < ACCOUNT.equity_at(ACCOUNT.equity_px, 0.0)


def test_runway_follows_the_repriced_equity_not_the_snapshot():
    """The bug this pins: quoting a stale cushion against a moved market."""
    stale = ACCOUNT.runway_days(0.80)
    live = ACCOUNT.runway_days(0.80, 0.02855, 1.0)
    assert stale == pytest.approx(28.12, abs=0.05)
    assert live == pytest.approx(58.7, abs=0.2)
    assert live > stale, "a +3.8% move must lengthen the runway"


def test_days_since_snapshot_counts_calendar_days():
    import datetime as dt
    assert ACCOUNT.days_since_snapshot(dt.date(2026, 9, 4)) == 0.0
    assert ACCOUNT.days_since_snapshot(dt.date(2026, 9, 5)) == 1.0
    assert ACCOUNT.days_since_snapshot(dt.date(2026, 10, 5)) == 31.0


def test_halving_the_position_buys_an_order_of_magnitude_of_runway():
    half = Position(
        units=ACCOUNT.units / 2,
        avg=ACCOUNT.avg,
        used_margin=ACCOUNT.used_margin / 2,
        equity=790.02,
        equity_px=0.0274,
        carry_per_day=ACCOUNT.carry_per_day / 2,
    )
    assert half.threshold_px(0.80, 0) == pytest.approx(0.01736, abs=2e-5)
    assert half.runway_days(0.80) > 200


def test_zero_carry_gives_a_static_barrier_and_infinite_runway():
    flat = Position(carry_per_day=0.0)
    assert flat.threshold_px(0.80, 0) == flat.threshold_px(0.80, 999)
    assert flat.runway_days(0.80) == float("inf")


@pytest.mark.parametrize(
    "vol_30d,maker,taker",
    [(0.0, 0.25, 0.40), (17482.0, 0.20, 0.35), (60000.0, 0.14, 0.24), (150000.0, 0.12, 0.22)],
)
def test_fee_tier_reads_the_venue_schedule(vol_30d, maker, taker):
    """Kraken FLOWUSD schedule, verbatim from /public/AssetPairs 2026-09-04.

    Guards the repo's '22/38 bps' note, which is not a row in this table.
    """
    info = {
        "fees_maker": [[0, 0.25], [10000, 0.2], [50000, 0.14], [100000, 0.12]],
        "fees": [[0, 0.4], [10000, 0.35], [50000, 0.24], [100000, 0.22]],
    }
    assert fee_tier(info, vol_30d) == (maker, taker)


# --- chain_check: selectors are load-bearing, so pin the hash ------------

from monitor.chain_check import decode_string, keccak256, selector  # noqa: E402


def test_keccak256_known_vectors():
    assert keccak256(b"").hex() == (
        "c5d2460186f7233c927e7db2dcc703c0e500b653ca82273b7bfad8045d85a470"
    )
    assert keccak256(b"abc").hex() == (
        "4e03657aea45a94fc7d47ba826c8d667c0d1e6e33a64a036ec44f58fa12d6c45"
    )


@pytest.mark.parametrize(
    "sig,sel",
    [
        ("paused()", "0x5c975abb"),
        ("totalSupply()", "0x18160ddd"),
        ("transfer(address,uint256)", "0xa9059cbb"),
        ("symbol()", "0x95d89b41"),
        ("getConfiguration(address)", "0xc44b11f7"),
        ("getReservesList()", "0xd1946dbc"),
        ("ADDRESSES_PROVIDER()", "0x0542975c"),
    ],
)
def test_selector_matches_known_abi(sig, sel):
    assert selector(sig) == sel


def test_ratio_and_getRatioFor_are_different_selectors():
    """The reason selectors are derived and never guessed."""
    assert selector("ratio()") != selector("getRatioFor(address)")
    assert selector("ratio()") == "0x71ca337d"


def test_decode_string_survives_short_and_empty_words():
    assert decode_string(None) == "?"
    assert decode_string("0x") == "?"


def test_fee_tier_empty_schedule_is_nan_not_a_guess():
    """Kraken returned `fees: []` for FLOWUSD on 2026-09-08 and the monitor
    crashed. An unpublished fee is unknown, never a fallback number."""
    import math

    maker, taker = fee_tier({"fees": [], "fees_maker": []}, 17482.0)
    assert math.isnan(maker) and math.isnan(taker)
