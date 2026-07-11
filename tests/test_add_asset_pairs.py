"""Adding trading pairs (SUI/ARB/MINA/FLOW) must flow end to end:

1. the base->Kraken-pair map is derived from config, not a hardcoded
   literal that silently drops any asset missing from it;
2. each new pair carries its REAL Kraken price precision (MINA=5,
   ARB/FLOW/SUI=4) - the generic 2-decimal default would be rejected by
   AddOrder;
3. a Kraken-only pair (no OKX/Binance.US listing, e.g. MINA) still warms
   up: the Kraken intraday-candle fallback fills its view entry so it can
   emit vol/liq/candidates instead of sitting tradeable-but-inert;
4. the fallback never overrides an asset the multi-venue view already
   covers (ETH/BTC cross-venue imbalance stays untouched).
"""
import types

from strategies.liquidity_model import LiquidityModel


def _cfg(pairs):
    return {"exchanges": {"kraken": {"trading_pairs": pairs}}}


def test_base_to_pair_derived_from_config():
    lm = LiquidityModel(_cfg(["ETH/USD", "BTC/USD", "MINA/USD", "ARB/USD"]))
    assert lm.base_to_pair["MINA"] == "MINA/USD"
    assert lm.base_to_pair["ARB"] == "ARB/USD"


def test_bare_construction_keeps_default_map():
    lm = LiquidityModel({})
    assert lm.base_to_pair == {"ETH": "ETH/USD", "BTC": "BTC/USD"}


def test_build_view_includes_newly_configured_asset():
    lm = LiquidityModel(_cfg(["SUI/USD"]))
    okx = {"SUI-USDT-SWAP": {"order_book": {"bids": [[1.0, 10.0]],
                                            "asks": [[1.01, 10.0]]},
                             "candles": [{"time": 1, "open": 1, "high": 1,
                                          "low": 1, "close": 1,
                                          "volume": 5}],
                             "funding_rate": 0.0, "volume_24h": 100.0}}
    view = lm.build_view(okx)
    assert "SUI" in view and view["SUI"]["kraken_symbol"] == "SUI/USD"


def test_build_view_drops_unconfigured_asset():
    lm = LiquidityModel(_cfg(["ETH/USD"]))          # DOGE not configured
    payload = {"DOGE-USDT-SWAP": {"order_book": {"bids": [], "asks": []},
                                  "candles": [], "funding_rate": 0.0,
                                  "volume_24h": 0.0}}
    assert "DOGE" not in lm.build_view(payload)


def test_pair_meta_fallback_precision(monkeypatch):
    from data.kraken_feed import KrakenFeed
    feed = KrakenFeed({"rate_limit_per_sec": 99})
    monkeypatch.setattr(feed, "_public_get", lambda *a, **k: None)  # offline
    meta = feed.get_pair_meta(["MINAUSD", "ARBUSD", "FLOWUSD", "SUIUSD"])
    assert meta["MINAUSD"]["price_decimals"] == 5
    assert meta["ARBUSD"]["price_decimals"] == 4
    assert meta["FLOWUSD"]["price_decimals"] == 4
    assert meta["SUIUSD"]["price_decimals"] == 4
    assert meta["MINAUSD"]["ordermin"] == 120.0


def _fake_bot(view, symbol_map, kraken_candles):
    from main import LiquidityBot
    kraken = types.SimpleNamespace(
        kraken_pair=lambda s: s.replace("/", ""),
        get_candles=lambda pair: kraken_candles.get(pair, []))
    bot = types.SimpleNamespace(
        view=view, symbol_map=symbol_map, kraken=kraken,
        kraken_books={"MINA": {"bids": [[0.5, 100.0]],
                               "asks": [[0.51, 100.0]]}})
    # call the real method unbound against the stand-in (duck-typed: the
    # method only touches view/symbol_map/kraken/kraken_books)
    LiquidityBot._augment_view_with_kraken(bot)  # type: ignore[arg-type]
    return bot


def test_kraken_fallback_warms_data_cold_pair():
    candles = [{"time": i, "open": 0.5, "high": 0.5, "low": 0.5,
                "close": 0.5, "volume": 1.0} for i in range(3)]
    bot = _fake_bot(
        view={"ETH": {"candles": [{"time": 1, "close": 3000}]}},
        symbol_map={"ETH": "ETH/USD", "MINA": "MINA/USD"},
        kraken_candles={"MINAUSD": candles})
    assert bot.view["MINA"]["candles"] == candles          # filled
    assert bot.view["MINA"]["order_book"]["bids"] == [[0.5, 100.0]]


def test_kraken_fallback_does_not_override_covered_pair():
    eth_candles = [{"time": 1, "close": 3000}]
    bot = _fake_bot(
        view={"ETH": {"candles": eth_candles, "imbalance_ratio": 1.2}},
        symbol_map={"ETH": "ETH/USD"},
        kraken_candles={"ETHUSD": [{"time": 9, "close": 1}]})
    assert bot.view["ETH"]["candles"] == eth_candles       # untouched
    assert bot.view["ETH"]["imbalance_ratio"] == 1.2
