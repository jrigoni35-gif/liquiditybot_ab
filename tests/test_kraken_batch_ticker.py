"""KrakenFeed.get_tickers: batch the fast cycle's per-pair mark fetch into
one Ticker call (6 -> 1) without threading the execution-carrying REST
client past its rate limit, and never be less correct than per-pair
get_ticker_price (unmapped pairs fall back to single fetches)."""
from data.kraken_feed import KrakenFeed


def _feed():
    return KrakenFeed({"rate_limit_per_sec": 3, "trading_pairs": []})


def test_batch_maps_internal_names_and_returns_prices(monkeypatch):
    f = _feed()
    # legacy pairs echo internal names; the AssetPairs map resolves them
    f._internal_to_alt = {"XETHZUSD": "ETHUSD", "XXBTZUSD": "XBTUSD"}
    calls = []

    def fake_get(endpoint, params=None):
        calls.append((endpoint, params))
        return {
            "XETHZUSD": {"c": ["2000.5", "1.0"]},
            "XXBTZUSD": {"c": ["64000.0", "0.1"]},
            "SUIUSD": {"c": ["1.2345", "10"]},   # newer: internal == altname
        }

    monkeypatch.setattr(f, "_public_get", fake_get)
    out = f.get_tickers(["ETHUSD", "XBTUSD", "SUIUSD"])

    assert out == {"ETHUSD": 2000.5, "XBTUSD": 64000.0, "SUIUSD": 1.2345}
    assert len(calls) == 1                       # ONE batched request
    assert calls[0][0] == "Ticker"
    assert calls[0][1]["pair"] == "ETHUSD,XBTUSD,SUIUSD"


def test_btc_requested_as_BTCUSD_maps_despite_kraken_XBT(monkeypatch):
    """The live bug: config requests BTCUSD, Kraken denominates Bitcoin as
    XBT so the response keys XXBTZUSD -> altname XBTUSD. Without XBT<->BTC
    aliasing, BTC silently missed the batch and hit a per-cycle fallback
    every fast cycle. It must now resolve straight from the batch."""
    f = _feed()
    f._internal_to_alt = {"XXBTZUSD": "XBTUSD"}          # as AssetPairs sets it
    single = []
    monkeypatch.setattr(f, "get_ticker_price",
                        lambda pair: single.append(pair) or None)
    monkeypatch.setattr(f, "_public_get",
                        lambda e, p=None: {"XXBTZUSD": {"c": ["64000.0", "1"]}})

    out = f.get_tickers(["BTCUSD"])                       # caller's spelling

    assert out == {"BTCUSD": 64000.0}                    # mapped to BTCUSD
    assert single == []                                  # NO fallback fetch


def test_unmapped_pair_falls_back_to_single_fetch(monkeypatch):
    f = _feed()
    # batch returns only ETH; FLOW must be backfilled via get_ticker_price
    monkeypatch.setattr(f, "_public_get",
                        lambda e, p=None: {"ETHUSD": {"c": ["2000", "1"]}})
    single = []
    monkeypatch.setattr(f, "get_ticker_price",
                        lambda pair: single.append(pair) or 5.55)
    out = f.get_tickers(["ETHUSD", "FLOWUSD"])

    assert out["ETHUSD"] == 2000.0
    assert out["FLOWUSD"] == 5.55                # correctness backstop hit
    assert single == ["FLOWUSD"]                 # only the unmapped one


def test_empty_and_dead_endpoint_are_safe(monkeypatch):
    f = _feed()
    assert f.get_tickers([]) == {}
    # dead Ticker endpoint -> every pair backstops; still never raises
    monkeypatch.setattr(f, "_public_get", lambda e, p=None: None)
    monkeypatch.setattr(f, "get_ticker_price", lambda pair: None)
    assert f.get_tickers(["ETHUSD"]) == {}


def test_zero_or_bad_price_is_dropped_not_zeroed(monkeypatch):
    f = _feed()
    f._internal_to_alt = {"SUIUSD": "SUIUSD"}
    monkeypatch.setattr(f, "_public_get",
                        lambda e, p=None: {"SUIUSD": {"c": ["0", "0"]}})
    monkeypatch.setattr(f, "get_ticker_price", lambda pair: None)
    out = f.get_tickers(["SUIUSD"])
    assert "SUIUSD" not in out                    # 0 is not a valid mark
