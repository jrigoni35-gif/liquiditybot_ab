"""tests/test_performance.py — the rolling trade-performance ledger derives the
desk metrics correctly from closed trades, portfolio-wide and per asset, and is
restart-safe. Telemetry only, so the tests assert math, not behavior."""
from core.performance import PerformanceTracker, _wilson_lcb


def _tracker():
    t = PerformanceTracker({"perf_window_trades": 200})
    # BTC: +$100 win (10% ret, 2% stop -> +5R), then -$20 loss (-2% -> -1R)
    t.record_close("BTC", 100.0, 1000.0, entry_price=100.0, stop_price=98.0)
    t.record_close("BTC", -20.0, 1000.0, entry_price=100.0, stop_price=98.0)
    # ETH: +$30 win, then two losses -$10, -$15 (no stop -> R undefined)
    t.record_close("ETH", 30.0, 1000.0)
    t.record_close("ETH", -10.0, 500.0)
    t.record_close("ETH", -15.0, 500.0)
    return t


def test_overall_metrics():
    s = _tracker().snapshot()["overall"]
    assert s["trades"] == 5
    assert s["win_rate"] == 0.4                       # 2 wins / 5
    assert s["profit_factor"] == round(130.0 / 45.0, 3)   # gross_win/gross_loss
    assert s["expectancy_usd"] == 17.0                # net 85 / 5
    assert s["avg_win_usd"] == 65.0                   # 130/2
    assert s["avg_loss_usd"] == -15.0                 # signed
    assert s["payoff_ratio"] == round(65.0 / 15.0, 3)
    assert s["gross_profit_usd"] == 130.0
    assert s["gross_loss_usd"] == 45.0
    assert s["net_usd"] == 85.0


def test_r_multiple_and_streak():
    s = _tracker().snapshot()["overall"]
    # only the 2 BTC trades carried a stop: +5R and -1R -> mean +2R
    assert s["expectancy_r"] == 2.0
    # window ends on two ETH losses
    assert s["cur_loss_streak"] == 2
    assert s["max_loss_streak"] == 2


def test_per_asset_split():
    ba = _tracker().snapshot()["by_asset"]
    assert set(ba) == {"BTC", "ETH"}
    assert ba["BTC"]["win_rate"] == 0.5
    assert ba["BTC"]["profit_factor"] == 5.0          # 100/20
    assert ba["ETH"]["trades"] == 3
    assert round(ba["ETH"]["win_rate"], 3) == round(1 / 3, 3)
    assert ba["ETH"]["max_loss_streak"] == 2


def test_wilson_lcb_below_point_estimate():
    # a small sample's lower bound must sit under the naive rate
    assert _wilson_lcb(3, 3) < 1.0
    assert _wilson_lcb(6, 10) < 0.6
    assert _wilson_lcb(0, 0) == 0.0


def test_profit_factor_capped_when_no_losses():
    t = PerformanceTracker()
    t.record_close("BTC", 10.0, 100.0)
    t.record_close("BTC", 5.0, 100.0)
    s = t.snapshot()["overall"]
    assert s["profit_factor"] == 99.0                 # sentinel, finite/JSON-safe
    assert s["win_rate"] == 1.0
    assert s["cur_loss_streak"] == 0


def test_empty_is_safe():
    s = PerformanceTracker().snapshot()
    assert s["overall"] == {"trades": 0}
    assert s["by_asset"] == {}


def test_window_bounds_and_persistence():
    t = PerformanceTracker({"perf_window_trades": 10})
    for i in range(15):
        t.record_close("BTC", float(i - 7), 100.0)    # mix of +/-
    assert t.snapshot()["overall"]["trades"] == 10    # capped

    t2 = PerformanceTracker({"perf_window_trades": 10})
    t2.restore(t.to_dict())
    assert t2.snapshot() == t.snapshot()              # exact round-trip
    # restore is bounded + garbage-safe
    t3 = PerformanceTracker({"perf_window_trades": 10})
    t3.restore({"trades": [{"bad": 1}, "notadict"]})
    assert t3.snapshot()["overall"]["trades"] == 0
