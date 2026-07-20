"""Adding trading pairs (SUI/ARB/MINA/FLOW) must flow end to end:

1. the base->Kraken-pair map is derived from config, not a hardcoded
   literal that silently drops any asset missing from it;
2. each new pair carries its REAL Kraken price precision (MINA=5,
   ARB/FLOW/SUI=4) - the generic 2-decimal default would be rejected by
   AddOrder;
3. a Kraken-only pair (no OKX/Binance.US listing, e.g. MINA) still warms
   up: the Kraken intraday-candle fallback fills its view entry so it can
   emit vol/liq/candidates instead of sitting tradeable-but-inert;
4. (re-pinned for v8 venue-grounded candles) Kraken bars now GROUND every
   mapped asset's candles when at least as long as the external history
   (wash-trading hygiene) - but a SHORTER Kraken history below the 97-bar
   builder window must never replace a longer external one, and non-candle
   view fields (cross-venue imbalance etc.) stay untouched either way.
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
                               "asks": [[0.51, 100.0]]}},
        # v8 venue-grounded candle cache + cadence (fresh -> fetch now)
        _kr_candles={}, _kr_candle_refresh_sec=150.0)
    # call the real method unbound against the stand-in (duck-typed: the
    # method only touches view/symbol_map/kraken/kraken_books/_kr_*)
    LiquidityBot._augment_view_with_kraken(bot, 1_000.0)  # type: ignore[arg-type]
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


def test_kraken_shorter_history_never_degrades_covered_pair():
    # re-pinned for v8: Kraken bars GROUND covered assets too now, but only
    # when >= the 97-bar builder window or >= the external length - a
    # shorter venue history must never shrink the feature windows, and
    # non-candle view fields survive the merge either way
    eth_candles = [{"time": i, "close": 3000} for i in range(5)]
    bot = _fake_bot(
        view={"ETH": {"candles": eth_candles, "imbalance_ratio": 1.2}},
        symbol_map={"ETH": "ETH/USD"},
        kraken_candles={"ETHUSD": [{"time": 9, "close": 1}]})
    assert bot.view["ETH"]["candles"] == eth_candles       # kept: 1 < 5 < 97
    assert bot.view["ETH"]["imbalance_ratio"] == 1.2


def test_kraken_equal_history_grounds_covered_pair():
    # v8 wash-trading hygiene: at >= external length the execution venue's
    # bars win, and the rest of the view entry is untouched
    kr = [{"time": 10 + i, "close": 2999} for i in range(5)]
    bot = _fake_bot(
        view={"ETH": {"candles": [{"time": i, "close": 3000}
                                  for i in range(5)],
                      "imbalance_ratio": 1.2}},
        symbol_map={"ETH": "ETH/USD"},
        kraken_candles={"ETHUSD": kr})
    assert bot.view["ETH"]["candles"] == kr                # grounded
    assert bot.view["ETH"]["imbalance_ratio"] == 1.2
