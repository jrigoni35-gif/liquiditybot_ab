"""W2-11 — Kraken-book expiry must not poison regime histories.

main.py's DL-10 staleness gate sets kbook={} once a Kraken book passes
watchdog.stale_critical_sec while external feeds (OKX/Binance.US) stay live
in the combined book. Before this fix, LiquidityRegimeEngine.update() fell
back to `combined_book` for the EXECUTION book whenever kraken_book was
empty, and that combined_book fed straight into the four stateful histories
(depth_hist, imb_hist, mid_hist, large_levels) exactly like a real Kraken
observation. Those histories then carry combined-book (external-scale,
different-venue) samples for their full window (60 samples / ~30min for
depth, 20 for imbalance), producing:
  * a depth/tier read distorted by external-scale notional,
  * false 'spoofy' whiplash from the merged book's square-wave imbalance,
  * a burst of fabricated spoof events when Kraken recovers and the
    combined-book-era "large levels" abruptly vanish from the exec book.

This test pins the fix: a no-fresh-Kraken cycle is a NO-OBSERVATION cycle
for the four histories (they neither append nor get diffed against the
combined book), and Kraken's recovery reseeds large-level tracking from the
fresh book instead of diffing it against combined-era levels.
"""
from regime.liquidity_regime import LiquidityRegimeEngine


def _book(mid=2000.0, size=5.0, half_spread=0.05, n=12):
    bids = [[mid - half_spread - 0.1 * i, size] for i in range(n)]
    asks = [[mid + half_spread + 0.1 * i, size] for i in range(n)]
    return {"bids": bids, "asks": asks}


def _combined_with_painted_wall(mid=2000.0, wall_price=1950.0, wall_size=200.0):
    """A combined (external) book shaped like a healthy book PLUS one huge,
    far-from-touch bid level — the shape that reads as a painted wall once
    it later disappears. wall_price sits far outside the tight kraken-era
    mid_hist band, so if it were tracked and later vanished it would read
    as UNTOUCHED (a spoof event) under the touch-buffer test."""
    book = _book(mid=mid, size=5.0, half_spread=0.05, n=12)
    book["bids"] = book["bids"] + [[wall_price, wall_size]]
    return book


ASSET = "ETH"


def test_no_kraken_cycles_do_not_append_to_the_four_histories():
    eng = LiquidityRegimeEngine({"min_depth_usd": 150_000, "max_spread_bps": 12})
    healthy = _book()

    # warm up on real Kraken observations
    for t in range(5):
        eng.update(ASSET, healthy, healthy, now=float(t))
    trk = eng._trk[ASSET]
    depth_before = list(trk.depth_hist)
    imb_before = list(trk.imb_hist)
    mid_before = list(trk.mid_hist)
    levels_before = dict(trk.large_levels)
    whiplash_before = eng.state(ASSET).imbalance_whiplash
    imb_ratio_before = eng.state(ASSET).imbalance_ratio

    # Kraken expires (main.py sets kbook={}); external combined book stays
    # live and very different in scale/shape (a painted-looking wall).
    combined = _combined_with_painted_wall()
    for t in range(5, 15):
        eng.update(ASSET, combined, {}, now=float(t))

    assert list(trk.depth_hist) == depth_before, "combined-book depth leaked into depth_hist"
    assert list(trk.imb_hist) == imb_before, "combined-book imbalance leaked into imb_hist"
    assert list(trk.mid_hist) == mid_before, "combined-book mid leaked into mid_hist"
    assert dict(trk.large_levels) == levels_before, "combined-book level entered large_levels tracking"
    # the flow scalar / whiplash surfaced to the alpha must hold the last
    # real Kraken reading, not get recomputed off the combined book
    assert eng.state(ASSET).imbalance_whiplash == whiplash_before
    assert eng.state(ASSET).imbalance_ratio == imb_ratio_before


def test_kraken_recovery_does_not_burst_spoof_events_from_combined_era_levels():
    eng = LiquidityRegimeEngine({"min_depth_usd": 150_000, "max_spread_bps": 12})
    healthy = _book()
    for t in range(5):
        eng.update(ASSET, healthy, healthy, now=float(t))

    events_before = eng._trk[ASSET].events

    combined = _combined_with_painted_wall()
    for t in range(5, 15):
        eng.update(ASSET, combined, {}, now=float(t))

    # Kraken recovers with a plain healthy book (no painted wall)
    st = eng.update(ASSET, combined, healthy, now=20.0)

    assert eng._trk[ASSET].events == events_before, (
        "Kraken recovery fabricated spoof events from combined-era large levels"
    )
    assert st.spoof_score < 0.45, "recovery falsely classified the asset as spoofy"
