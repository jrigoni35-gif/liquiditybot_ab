"""The hedger's open and unwind paths must ask the SAME question.

LIVE INCIDENT, 2026-08-06 20:09-20:31. The bot opened and unwound an
ADA/USD hedge 121 times in 21 minutes - 246 fills, every one paying spread
and fees, and realized P&L went -$43.84 -> -$186.78. The book never
changed; the two code paths simply disagreed forever.

  open   : corr(exposed, hedge_asset)  -> corr(ETH, ADA) = 0.72 >= 0.55, open
  unwind : corr(hedge_asset, others[0]) -> corr(ADA, ARB) = 0.00 <  0.55, unwind
  ...net delta is still over cap, so open again. Forever.

`others[0]` in the unwind path was "the first asset alphabetically that is
not the hedge asset" - an arbitrary pair with no relationship to the
exposure the hedge was created to offset. The open path was right and the
unwind path was asking about two unrelated coins.

This is the SECOND thrash of this shape in this file: evaluate()'s
`signal_net` comment documents an earlier one where the unwind test read
TOTAL net delta, so a correctly-sized hedge unwound itself the moment it
worked. Same failure, different quantity - which is why the fix here is
not just "use the right assets" but a single shared _exposure_by_asset()
helper, so "which asset are we exposed to" has one definition.
"""
from types import SimpleNamespace

import pytest

from execution.hedging import HedgeEngine


class _Corr:
    """corr(a,b) from an explicit table; anything unlisted is 0.0 - the
    same "no data" reading that fired the live unwind."""

    def __init__(self, table: dict):
        self.table = table

    def corr(self, a, b):
        return self.table.get((a, b), self.table.get((b, a), 0.0))

    def beta(self, a, b):
        return 1.0


class _State:
    def __init__(self, positions):
        self._p = positions

    def open_positions(self):
        return self._p


def _pos(symbol, direction, size, px, is_hedge=False, pid="p"):
    return SimpleNamespace(symbol=symbol, direction=direction, size=size,
                           entry_price=px, is_hedge=is_hedge,
                           position_id=pid)


SYMBOLS = {"ETH": "ETH/USD", "ADA": "ADA/USD", "ARB": "ARB/USD"}
MARKS = {"ETH/USD": 2000.0, "ADA/USD": 0.20, "ARB/USD": 1.0}
# ETH is the dominant exposure; ADA is correlated to it and is the hedge.
# ARB is correlated to nothing - the arbitrary pair the old unwind used.
CORR = _Corr({("ETH", "ADA"): 0.72, ("ETH", "ARB"): 0.60})


def _hedger():
    return HedgeEngine({"enabled": True,
                        "min_hedge_correlation": 0.55,
                        "max_net_delta_pct_of_equity": 20.0,
                        "rebalance_band_pct": 10.0,
                        "min_hedge_usd": 10.0,
                        "max_equity_frac": 0.5}, SYMBOLS)


def test_a_live_hedge_is_not_unwound_on_an_unrelated_correlation():
    """The thrash, pinned. A hedge whose OWN pair still clears the floor
    must survive, even though corr(hedge_asset, some_other_asset) is 0."""
    h = _hedger()
    state = _State([
        _pos("ETH/USD", "long", 1.0, 2000.0, pid="signal"),
        _pos("ADA/USD", "short", 2500.0, 0.20, is_hedge=True, pid="hedge"),
    ])
    actions = h.evaluate(state, MARKS, equity=5000.0, corr_state=CORR)
    unwinds = [a for a in actions if a.kind == "unwind"
               and "correlation" in a.reason]
    assert not unwinds, (
        "hedge unwound on a correlation its OPEN never tested "
        f"-> {[a.reason for a in unwinds]}")


def test_a_genuinely_decorrelated_hedge_is_still_unwound():
    """The guard must not become a rubber stamp: when the hedge really has
    decorrelated FROM THE EXPOSURE IT OFFSETS, unwinding is correct."""
    h = _hedger()
    state = _State([
        _pos("ETH/USD", "long", 1.0, 2000.0, pid="signal"),
        _pos("ADA/USD", "short", 2500.0, 0.20, is_hedge=True, pid="hedge"),
    ])
    dead = _Corr({("ETH", "ADA"): 0.10})
    actions = h.evaluate(state, MARKS, equity=5000.0, corr_state=dead)
    assert any(a.kind == "unwind" and "correlation" in a.reason
               for a in actions), "a truly decorrelated hedge must unwind"


def test_open_and_unwind_agree_across_repeated_evaluations():
    """The actual money bug: run the same book many times and the hedger
    must reach a STEADY STATE rather than alternating open/unwind."""
    h = _hedger()
    state = _State([
        _pos("ETH/USD", "long", 1.0, 2000.0, pid="signal"),
        _pos("ADA/USD", "short", 2500.0, 0.20, is_hedge=True, pid="hedge"),
    ])
    seen = set()
    for _ in range(25):
        acts = h.evaluate(state, MARKS, equity=5000.0, corr_state=CORR)
        seen.add(tuple(sorted((a.kind, a.reason[:24]) for a in acts)))
    assert len(seen) == 1, \
        f"hedger oscillates between decisions on a static book: {seen}"


def test_exposure_helper_excludes_hedges_and_is_shared():
    """Both paths must read the SIGNAL book - counting the hedge itself is
    how the first thrash (the signal_net one) happened."""
    h = _hedger()
    state = _State([
        _pos("ETH/USD", "long", 1.0, 2000.0, pid="signal"),
        _pos("ADA/USD", "short", 2500.0, 0.20, is_hedge=True, pid="hedge"),
    ])
    exp = h._exposure_by_asset(state, MARKS)
    assert "ADA" not in exp, "the hedge leg must not count as exposure"
    assert exp["ETH"] == pytest.approx(2000.0)


def test_no_dominant_exposure_defers_to_the_normalized_arm():
    """An empty signal book means the hedge has nothing left to offset.
    That is the 'signal delta normalized' unwind's job - correlation must
    not fabricate a reason (there is no pair left to measure)."""
    h = _hedger()
    state = _State([
        _pos("ADA/USD", "short", 2500.0, 0.20, is_hedge=True, pid="hedge"),
    ])
    actions = h.evaluate(state, MARKS, equity=5000.0, corr_state=CORR)
    corr_unwinds = [a for a in actions if a.kind == "unwind"
                    and "correlation" in a.reason]
    assert not corr_unwinds, \
        "unwound on correlation with no exposure to correlate against"
