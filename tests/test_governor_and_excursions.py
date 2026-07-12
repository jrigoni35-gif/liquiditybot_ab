"""Two fixes verified here:

1. GOVERNOR POLLUTION: exploration paper-trades carry a FORCED p_win, not
   the model's own call. They must not score the model's calibration -
   counting them made the governor degrade/throttle the model for
   epsilon-greedy noise. The monitor excludes model_scored=False records;
   the engine now marks exploration entries model_scored=False.

2. MFE OUTLIER: a lone bad-tick print must not define a trade's max
   favorable excursion (observed: MFE 17-24% on minute BTC scalps while
   MAE stayed sane). _excursions now rejects MAD outliers.
"""
from ml.monitor import ModelMonitor
from ml.postmortem import TradeThesis


def _thesis(direction, fill_price, prices):
    t = TradeThesis(
        position_id="p", asset="BTC", symbol="BTC/USD", direction=direction,
        entry_ts=0.0, p_win=0.62, expected_ret_pct=0.1, expected_cost_bps=40,
        stop_pct=1.0, target_pct=1.1, entry_regime="range", entry_liq="liquid",
        narrative_label="none", fair_value=fill_price, quote_price=fill_price,
        model_scored=True)
    t.fill_price = fill_price
    t.marks = [(float(i), px) for i, px in enumerate(prices)]
    return t


def test_excursions_reject_a_lone_bad_tick_spike():
    from ml.postmortem import PostmortemEngine
    book = PostmortemEngine.__new__(PostmortemEngine)     # only need _excursions
    # long from 100; genuine range 100-101, plus ONE 124 bad tick
    t = _thesis("long", 100.0, [100, 100.5, 101, 124, 100.8, 101])
    mfe, mae = book._excursions(t)
    assert mfe < 2.0, f"bad tick leaked into MFE: {mfe}"   # ~1%, not 24%
    assert -2.0 < mae <= 0.0


def test_excursions_keep_a_real_move():
    from ml.postmortem import PostmortemEngine
    book = PostmortemEngine.__new__(PostmortemEngine)
    # a coherent 3% climb (not an outlier) must survive
    t = _thesis("long", 100.0, [100, 100.7, 101.5, 102.2, 103.0])
    mfe, _ = book._excursions(t)
    assert 2.5 < mfe < 3.5


def test_governor_ignores_non_model_scored_losses():
    """A run of exploration losses (model_scored=False) must NOT degrade the
    governor - they are not the model's predictions."""
    m = ModelMonitor({"min_trades_to_judge": 5, "window_trades": 30})
    for _ in range(25):
        m.record_close(0.62, 0, model_scored=False)   # forced-p_win losses
    assert m.level == 0, "exploration noise wrongly degraded the governor"
    assert m.use_model is True


def test_governor_still_degrades_on_real_model_failure():
    """Sanity: genuine model_scored losses that undershoot the promise still
    degrade - the fix narrows WHAT is scored, it doesn't disarm the governor."""
    m = ModelMonitor({"min_trades_to_judge": 5, "window_trades": 30})
    for _ in range(25):
        m.record_close(0.90, 0, model_scored=True)     # promised .9, all lose
    assert m.level >= 1
