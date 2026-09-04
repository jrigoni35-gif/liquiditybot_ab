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
