"""tests/test_markout.py — the empirical adverse-selection meter.

Mark-out convention: markout_bps = side_sign*(mark-fill)/fill*1e4, side_sign
+1 for a buy / -1 for a sell. POSITIVE = the price moved in our favour after
we filled (healthy); NEGATIVE = it moved against us (we were scalped). Pins the
sign, the per-horizon resolution, the trusted-mark gating (no fabricated
mark-out off a stale/dark feed), and the aggregation.
"""
from execution.markout import MarkoutTracker


def _mk(horizons=(5, 30, 60), **over):
    cfg = {"enabled": True, "horizons_sec": list(horizons), "window": 200,
           "grace_sec": 15}
    cfg.update(over)
    return MarkoutTracker(cfg)


def test_buy_that_rises_is_favourable_falls_is_adverse():
    t = _mk(horizons=(5,))
    t.record_fill("ETH/USD", "ETH", "buy", 100.0, now=0.0)
    t.poll({"ETH/USD": 101.0}, now=6.0)             # +1% after a buy
    snap = t.snapshot()
    assert snap["by_asset"]["ETH"]["5"]["markout_bps"] == 100.0   # favourable

    t2 = _mk(horizons=(5,))
    t2.record_fill("ETH/USD", "ETH", "buy", 100.0, now=0.0)
    t2.poll({"ETH/USD": 99.0}, now=6.0)             # price DROPPED after a buy
    assert t2.snapshot()["by_asset"]["ETH"]["5"]["markout_bps"] == -100.0  # scalped


def test_sell_sign_is_mirrored():
    t = _mk(horizons=(5,))
    t.record_fill("ETH/USD", "ETH", "sell", 100.0, now=0.0)
    t.poll({"ETH/USD": 99.0}, now=6.0)              # sold high, price fell = good
    assert t.snapshot()["by_asset"]["ETH"]["5"]["markout_bps"] == 100.0
    t2 = _mk(horizons=(5,))
    t2.record_fill("ETH/USD", "ETH", "sell", 100.0, now=0.0)
    t2.poll({"ETH/USD": 101.0}, now=6.0)            # sold, price rose = adverse
    assert t2.snapshot()["by_asset"]["ETH"]["5"]["markout_bps"] == -100.0


def test_each_horizon_resolves_once_at_its_time():
    t = _mk(horizons=(5, 30, 60))
    t.record_fill("ETH/USD", "ETH", "buy", 100.0, now=0.0)
    t.poll({"ETH/USD": 101.0}, now=6.0)             # only h5 due
    assert set(t.snapshot()["by_asset"]["ETH"]) == {"5"}
    t.poll({"ETH/USD": 102.0}, now=31.0)            # h30 due
    t.poll({"ETH/USD": 103.0}, now=61.0)            # h60 due -> record retired
    snap = t.snapshot()
    assert set(snap["by_asset"]["ETH"]) == {"5", "30", "60"}
    assert snap["by_asset"]["ETH"]["30"]["markout_bps"] == 200.0
    assert snap["by_asset"]["ETH"]["60"]["markout_bps"] == 300.0
    assert snap["pending"] == 0                     # fully resolved, not leaked


def test_stale_mark_defers_then_drops_never_fabricates():
    t = _mk(horizons=(5,), grace_sec=15)
    t.record_fill("ETH/USD", "ETH", "buy", 100.0, now=0.0)
    t.poll({}, now=6.0)                             # no mark -> defer (in grace)
    assert t.snapshot()["by_asset"] == {} and t.snapshot()["pending"] == 1
    t.poll({}, now=21.0)                            # past horizon+grace -> give up
    assert t.snapshot()["by_asset"] == {} and t.snapshot()["pending"] == 0


def test_is_fresh_predicate_gates_measurement():
    t = _mk(horizons=(5,), grace_sec=100)
    t.record_fill("ETH/USD", "ETH", "buy", 100.0, now=0.0)
    t.poll({"ETH/USD": 101.0}, now=6.0, is_fresh=lambda s, n: False)   # frozen feed
    assert t.snapshot()["pending"] == 1 and t.snapshot()["by_asset"] == {}
    t.poll({"ETH/USD": 101.0}, now=7.0, is_fresh=lambda s, n: True)    # fresh again
    assert t.snapshot()["by_asset"]["ETH"]["5"]["markout_bps"] == 100.0


def test_overall_pools_across_assets_and_worst_is_most_negative():
    t = _mk(horizons=(5,))
    t.record_fill("ETH/USD", "ETH", "buy", 100.0, now=0.0)
    t.record_fill("BTC/USD", "BTC", "buy", 100.0, now=0.0)
    t.poll({"ETH/USD": 101.0, "BTC/USD": 97.0}, now=6.0)   # ETH +100, BTC -300
    snap = t.snapshot()
    assert snap["overall"]["5"]["markout_bps"] == -100.0    # mean of +100,-300
    assert snap["overall"]["5"]["n"] == 2
    assert t.worst_asset_markout(5) == ("BTC", -300.0)


def test_disabled_and_bad_inputs_are_noops():
    off = _mk(enabled=False)
    off.record_fill("ETH/USD", "ETH", "buy", 100.0, now=0.0)
    off.poll({"ETH/USD": 200.0}, now=99.0)
    assert off.snapshot()["by_asset"] == {}
    t = _mk(horizons=(5,))
    t.record_fill("ETH/USD", "ETH", "buy", 0.0, now=0.0)       # zero price
    t.record_fill("ETH/USD", "ETH", "buy", None, now=0.0)      # non-numeric
    t.poll({"ETH/USD": 101.0}, now=6.0)
    assert t.snapshot()["pending"] == 0 and t.snapshot()["by_asset"] == {}


# ---- task #89 coverage-pin batch: exact boundary / dup / NaN ---------------

def test_resolves_exactly_at_horizon_age_inclusive():
    t = _mk(horizons=(5,))
    t.record_fill("ETH/USD", "ETH", "buy", 100.0, now=0.0)
    t.poll({"ETH/USD": 101.0}, now=5.0)              # age == h exactly
    snap = t.snapshot()
    assert snap["by_asset"]["ETH"]["5"]["markout_bps"] == 100.0
    assert snap["pending"] == 0


def test_duplicate_record_fill_is_not_deduped():
    t = _mk(horizons=(5,))
    t.record_fill("ETH/USD", "ETH", "buy", 100.0, now=0.0)
    t.record_fill("ETH/USD", "ETH", "buy", 100.0, now=0.0)
    assert len(t._pending) == 2
    t.poll({"ETH/USD": 101.0}, now=6.0)
    assert t.snapshot()["by_asset"]["ETH"]["5"]["n"] == 2


def test_nan_price_fill_is_noop_and_nan_mark_defers_never_pollutes():
    t = _mk(horizons=(5,), grace_sec=15)
    t.record_fill("ETH/USD", "ETH", "buy", float("nan"), now=0.0)
    assert len(t._pending) == 0                      # NaN price: no-op
    t.record_fill("ETH/USD", "ETH", "buy", 100.0, now=0.0)
    assert len(t._pending) == 1
    t.poll({"ETH/USD": float("nan")}, now=6.0)        # NaN mark: defer only
    snap = t.snapshot()
    assert snap["by_asset"] == {} and snap["pending"] == 1
    t.poll({"ETH/USD": 101.0}, now=7.0)               # real mark arrives
    snap2 = t.snapshot()
    assert snap2["by_asset"]["ETH"]["5"]["markout_bps"] == 100.0
    assert snap2["pending"] == 0
