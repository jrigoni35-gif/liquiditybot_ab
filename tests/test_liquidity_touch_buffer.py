"""Filled-vs-pulled fix for the spoof detector, plus traceback capture in the
JSONL log handler.

At ~30s book sampling, a large level that vanishes NEAR the sampled mid path
was plausibly consumed by trades between snapshots. Counting those as spoof
events saturated the score near 1.0 on healthy live books (observed: spoof
p50 0.93-0.96 on 0.5bps-spread Kraken books), making the gate an always-on
veto. The touched test now carries a proximity buffer
(spoof_touch_buffer_bps, default 5): near-touch vanishes are forgiven,
painted walls away from the touch still count.
"""
import json
import logging

from core.runtime import JsonlLogHandler
from regime.liquidity_regime import LiquidityRegimeEngine

MID = 2000.0


def _book(mid=MID, extra_bid=None):
    bids = [[mid - 0.1 * (i + 1), 5.0] for i in range(15)]
    asks = [[mid + 0.1 * (i + 1), 5.0] for i in range(15)]
    if extra_bid is not None:
        bids.insert(3, list(extra_bid))
    return {"bids": bids, "asks": asks}


def _engine():
    return LiquidityRegimeEngine({"spoof_max_lifetime_sec": 90,
                                  "spoof_touch_buffer_bps": 5.0})


def test_near_touch_vanish_is_forgiven_as_filled():
    eng = _engine()
    eng.update("ETH", _book(), _book(), now=0.0)
    # large level ~2.5bps below mid (inside the 5bps buffer), then it vanishes
    near = (MID * (1 - 2.5 / 1e4), 400.0)
    eng.update("ETH", _book(extra_bid=near), _book(extra_bid=near), now=30.0)
    eng.update("ETH", _book(), _book(), now=60.0)
    assert eng.state("ETH").spoof_events_total == 0     # plausibly consumed


def test_far_pulled_wall_still_counts_as_spoof():
    eng = _engine()
    eng.update("ETH", _book(), _book(), now=0.0)
    # large wall 30bps below mid (mid path never near it), pulled young
    far = (MID * (1 - 30.0 / 1e4), 400.0)
    eng.update("ETH", _book(extra_bid=far), _book(extra_bid=far), now=30.0)
    eng.update("ETH", _book(), _book(), now=60.0)
    assert eng.state("ETH").spoof_events_total == 1     # painted liquidity


def test_long_resting_wall_is_not_spoof():
    eng = _engine()
    far = (MID * (1 - 30.0 / 1e4), 400.0)
    eng.update("ETH", _book(extra_bid=far), _book(extra_bid=far), now=0.0)
    eng.update("ETH", _book(extra_bid=far), _book(extra_bid=far), now=60.0)
    eng.update("ETH", _book(extra_bid=far), _book(extra_bid=far), now=120.0)
    eng.update("ETH", _book(), _book(), now=150.0)      # vanishes at 150s age
    assert eng.state("ETH").spoof_events_total == 0     # rested past 90s


def test_jsonl_handler_captures_traceback(tmp_path):
    log_path = tmp_path / "events.jsonl"
    h = JsonlLogHandler(path=str(log_path))
    logger = logging.getLogger("test.exc.capture")
    logger.addHandler(h)
    logger.setLevel(logging.DEBUG)
    try:
        try:
            raise ValueError("the actual root cause")
        except ValueError:
            logger.exception("cycle error - continuing")
    finally:
        logger.removeHandler(h)
    rec = json.loads(log_path.read_text(encoding="utf-8").splitlines()[-1])
    assert rec["msg"] == "cycle error - continuing"
    assert "ValueError" in rec.get("exc", "")
    assert "the actual root cause" in rec["exc"]
