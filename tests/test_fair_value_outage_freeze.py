"""W2-23 — a frozen Kraken touch must not fabricate basis/edge during a
Kraken outage.

execution/fair_value.py only refreshes kraken_bid/kraken_ask/kraken_mid
`if kraken_book:` is truthy. Once Kraken's book expires (main.py's DL-10
staleness gate hands fair_value.update() kraken_book={} for the whole
outage), those three fields freeze at their last real values FOREVER while
fair_value keeps blending from the still-live external books. basis_bps
and edge_bps() then compute the (frozen touch) vs (drifting fair value)
delta as if it were live market structure - a fabricated stress/edge
signal that grows for the entire duration of the outage.

Fix pins: the Kraken touch is age-stamped; once older than the staleness
bound it is zeroed (not just left stale), so basis_bps/edge_bps read
0.0/neutral and kraken_fresh reads False - matching every other "absent
data reads as absent, never as frozen-fresh" convention in this codebase
(DL-10, DL-2, watchdog stale_critical_sec).
"""
from execution.fair_value import FairValueEngine


def _book(mid, half_spread=0.05, size=10.0):
    return {"bids": [[mid - half_spread, size]],
            "asks": [[mid + half_spread, size]]}


def test_frozen_kraken_touch_zeroes_out_past_the_staleness_bound():
    eng = FairValueEngine({"ema_alpha": 0.5, "kraken_stale_sec": 60.0})
    kraken = _book(100.0)
    ext = _book(100.0)

    st = eng.update("X", [ext], kraken, now=0.0)
    assert st.kraken_mid == 100.0
    assert st.kraken_fresh is True

    # Kraken goes absent; external books keep voting and drag fair value
    # away from the frozen Kraken touch.
    drifted = _book(110.0)
    st = eng.update("X", [drifted], {}, now=90.0)   # 90s > 60s bound

    assert st.kraken_mid == 0.0, "frozen touch must zero past the staleness bound"
    assert st.kraken_bid == 0.0
    assert st.kraken_ask == 0.0
    assert st.basis_bps == 0.0, "basis_bps must not fabricate stress off a stale touch"
    assert st.edge_bps("buy") == 0.0
    assert st.edge_bps("sell") == 0.0
    assert st.kraken_fresh is False


def test_short_kraken_gap_within_the_bound_still_holds_the_touch():
    # a brief drop-out (well within the staleness bound) is not an outage -
    # the touch is allowed to hold so a single missed poll doesn't neutralize
    # every downstream basis/edge read.
    eng = FairValueEngine({"ema_alpha": 0.5, "kraken_stale_sec": 60.0})
    kraken = _book(100.0)
    ext = _book(100.0)
    eng.update("X", [ext], kraken, now=0.0)

    st = eng.update("X", [ext], {}, now=5.0)   # 5s << 60s bound
    assert st.kraken_mid == 100.0
    assert st.kraken_fresh is True


def test_kraken_recovery_after_a_gap_re_freshens_the_touch():
    eng = FairValueEngine({"ema_alpha": 0.5, "kraken_stale_sec": 60.0})
    kraken = _book(100.0)
    ext = _book(100.0)
    eng.update("X", [ext], kraken, now=0.0)
    eng.update("X", [ext], {}, now=90.0)        # goes stale

    recovered = _book(105.0)
    st = eng.update("X", [ext], recovered, now=95.0)
    assert st.kraken_mid == 105.0
    assert st.kraken_fresh is True
