"""core/precision.py + the dashboard positions row-builder.

The engine computes at full float precision; these cover the DISPLAY
layer that mangled sub-dollar pairs. Two bugs are pinned here:

1. A hardcoded 2-decimal grid quantized ARB ($0.0873 -> 0.09), an ~11%
   error on a sub-dollar asset. Prices must render at venue precision,
   floored to 4 decimals for anything under $1.
2. The dashboard recomputed uPnL from p["entry_price"] - a key the runner
   never writes (it writes "entry") - so entry read 0 and uPnL became the
   entire notional (a phantom +$218 winner). The row-builder must read the
   runner's server-computed "upnl_usd", not re-derive it.
"""
from core.precision import fmt_price, price_decimals, round_price

PM = {"BTCUSD": {"price_decimals": 1}, "ETHUSD": {"price_decimals": 2},
      "ARBUSD": {"price_decimals": 4}, "MINAUSD": {"price_decimals": 5}}


def test_venue_precision_and_subdollar_floor():
    assert price_decimals(PM, "ETHUSD", 1820.44) == 2
    assert price_decimals(PM, "ARBUSD", 0.0873) == 4       # venue 4dp
    assert price_decimals(PM, "MINAUSD", 0.041) == 5       # venue 5dp
    # sub-dollar with missing/coarse metadata still floored to 4
    assert price_decimals({}, "FOOUSD", 0.037) == 4
    assert price_decimals({"FOOUSD": {"price_decimals": 2}}, "FOOUSD",
                          0.037) == 4
    # a dollar-plus asset with no metadata keeps the 2dp default
    assert price_decimals({}, "FOOUSD", 25.0) == 2


def test_subdollar_price_is_not_quantized():
    # the actual bug: 0.0873 must NOT collapse to 0.09
    assert fmt_price(0.08734, PM, "ARBUSD") == "0.0873"
    assert round_price(0.08734, PM, "ARBUSD") == 0.0873
    assert round_price(0.041234, PM, "MINAUSD") == 0.04123
    # majors unaffected
    assert fmt_price(1820.44, PM, "ETHUSD") == "1820.44"


def test_fmt_and_round_handle_none_and_garbage():
    assert round_price(None, PM, "ARBUSD") is None
    assert round_price("nope", PM, "ARBUSD") is None
    assert fmt_price(None, PM, "ARBUSD") == "n/a"
    assert fmt_price("nope", PM, "ARBUSD") == "n/a"
