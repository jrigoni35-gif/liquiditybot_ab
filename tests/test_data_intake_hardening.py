"""Data-intake hardening: an adversarial or merely-broken venue must not be
able to screw the bot through the values it returns. Covers three gaps found
2026-07-12:

1. clean_book trusted level ORDER - an unsorted book fed a wrong 'best'
   bid/ask into mid/imbalance/STOP logic.
2. clean_candles accepted physically-impossible OHLC (high<low, body outside
   [low,high]) - poison for volatility/ATR/swing features.
3. the live fill path used raw float(), and float("Infinity"/"NaN") SUCCEED,
   injecting an infinite phantom fill / infinite entry price.
"""
import math

from core.sanitize import clean_book, clean_candles, safe_float


# --- 1. book level ordering ------------------------------------------------
def test_unsorted_book_is_sorted_to_true_touch():
    b = clean_book({"bids": [[100, 1], [105, 2], [99, 1]],
                    "asks": [[110, 1], [106, 3], [120, 1]]})
    assert b is not None
    assert b["bids"][0][0] == 105.0        # true best bid, not input[0]
    assert b["asks"][0][0] == 106.0        # true best ask, not input[0]
    assert [lvl[0] for lvl in b["bids"]] == [105.0, 100.0, 99.0]   # desc
    assert [lvl[0] for lvl in b["asks"]] == [106.0, 110.0, 120.0]  # asc


def test_crossed_after_sort_still_rejected():
    # genuinely crossed (best bid >= best ask) must still be refused
    assert clean_book({"bids": [[110, 1]], "asks": [[105, 1]]}) is None


# --- 2. OHLC self-consistency ----------------------------------------------
def test_impossible_ohlc_dropped():
    rows = clean_candles([
        {"time": 1, "open": 100, "high": 90, "low": 110, "close": 105,
         "volume": 5},                              # high < low
        {"time": 2, "open": 100, "high": 101, "low": 99, "close": 200,
         "volume": 5},                              # close above high
        {"time": 3, "open": 100, "high": 101, "low": 99, "close": 100,
         "volume": 5},                              # valid
    ])
    assert len(rows) == 1
    assert rows[0]["time"] == 3


def test_valid_ohlc_survives():
    rows = clean_candles([{"time": 1, "open": 100, "high": 105, "low": 98,
                           "close": 103, "volume": 12}])
    assert len(rows) == 1 and rows[0]["high"] == 105.0


# --- 3. fill-field poison (Infinity/NaN strings) ---------------------------
def test_safe_float_blocks_infinity_and_nan_strings():
    # the exact vectors the live fill path would have float()'d into poison
    assert safe_float("Infinity", default=1.5, lo=0.0) == 1.5
    assert safe_float("-Infinity", default=1.5, lo=0.0) == 1.5
    assert safe_float("NaN", default=2.0, lo=0.0) == 2.0
    # and a real string number still parses
    got = safe_float("1.25", default=0.0, lo=0.0)
    assert got == 1.25 and math.isfinite(got)
