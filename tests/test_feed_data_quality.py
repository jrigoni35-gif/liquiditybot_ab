"""Data-quality fixes found by inspecting live feeds:

1. imbalance_ratio was summed over the CONCATENATED OKX(swap,contract-units)+
   BinanceUS(spot,coin-units) book -> garbage 22-112x live -> the log() feature
   pinned at its clip ceiling and the flow gate mis-driven. Now averaged
   per-venue (unit-consistent within a book) and clamped.
2. OKX/BinanceUS candle timestamps are milliseconds; Kraken is seconds. Feeds
   now normalize to seconds so no cross-source comparison is off by 1000x.
"""
import numpy as np

from data.okx_feed import OKXFeed
from strategies.liquidity_model import LiquidityModel

LM = LiquidityModel({})


def _book(bid_depth_usd, ask_depth_usd, px=2000.0, unit_size=1.0):
    # one level per side; `unit_size` mimics a venue's size unit (coins vs
    # contracts) so depth = px * (usd/px/unit)*unit — the RATIO is unchanged
    return {"bids": [[px, bid_depth_usd / px]], "asks": [[px, ask_depth_usd / px]]}


def test_single_book_ratio_is_clamped():
    # a 100:1 one-sided book must not blow past the cap
    r = LM._imbalance_ratio(_book(100_000, 1_000))
    assert 1.0 <= r <= LM._IMB_CAP
    r2 = LM._imbalance_ratio(_book(1_000, 100_000))
    assert 1.0 / LM._IMB_CAP <= r2 <= 1.0


def test_empty_ask_side_clamps_not_infinite():
    r = LM._imbalance_ratio({"bids": [[2000.0, 5.0]], "asks": []})
    assert r == LM._IMB_CAP        # was float('inf')


def test_combined_averages_per_venue_not_concatenated():
    # venue A balanced 2:1, venue B balanced ~1.5:1 -> average ~1.75
    a = _book(4000, 2000)          # 2.0
    b = _book(3000, 2000)          # 1.5
    assert LM._combined_imbalance([a, b]) == \
        (LM._imbalance_ratio(a) + LM._imbalance_ratio(b)) / 2


def test_unit_mismatch_cannot_saturate_the_feature():
    # OKX-style huge contract sizes on one side + Binance-style tiny coin sizes:
    # concatenated this produced 22-112x; per-venue+clamp keeps it sane so the
    # feature clip(log(r),-2,2) is never pinned
    okx = {"bids": [[2000.0, 5000.0], [1999.0, 5000.0]],   # contract-scale sizes
           "asks": [[2001.0, 10.0]]}
    binance = {"bids": [[2000.0, 1.2]], "asks": [[2001.0, 1.0]]}
    r = LM._combined_imbalance([okx, binance])
    feat = float(np.clip(np.log(max(r, 1e-3)), -2, 2))
    assert 0.2 <= r <= LM._IMB_CAP
    assert abs(feat) < 2.0 - 1e-6          # NOT pinned at the clip ceiling


def test_no_books_returns_neutral():
    assert LM._combined_imbalance([]) == 1.0
    assert LM._combined_imbalance([{"bids": [], "asks": []}]) == 1.0


def test_okx_candle_time_normalized_to_seconds(monkeypatch):
    feed = OKXFeed({})
    ms = 1_783_535_100_000

    def fake_get(path, params=None):
        # OKX newest-first row: [ts_ms, o, h, l, c, vol, ...]
        return [[str(ms), "100", "101", "99", "100.5", "10"],
                [str(ms - 300_000), "100", "101", "99", "100.4", "9"]]

    monkeypatch.setattr(feed, "_get", fake_get)
    out = feed.get_candles("ETH-USDT-SWAP", limit=2)
    assert out and all(c["time"] < 1e11 for c in out)      # seconds, not ms
    assert out[-1]["time"] == ms // 1000
