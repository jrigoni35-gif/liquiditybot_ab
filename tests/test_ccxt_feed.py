"""CCXT read-only market-data adapter (data/ccxt_feed.py).

ccxt is an OPTIONAL dependency and is absent in this environment, so the
module was never exercised by the suite (test_import_integrity skips
optional-dep modules) — 0% coverage. The adapter is written for exactly
this: an injectable `client` and an `_import_sdk` seam let the whole
contract be tested with no ccxt install and no network. This pins the
boundaries the module enforces IN CODE:

  * DATA-ONLY / PUBLIC-ONLY — credential-like config is refused (CCXT-001);
  * absence of ccxt degrades to an empty feed, never a crash (CCXT-003);
  * an unknown exchange id disables the feed (CCXT-002);
  * per-symbol faults degrade only that symbol (CCXT-005);
  * payloads are shape-correct and pass through core/sanitize.
"""
import pytest

from data.ccxt_feed import CCXTFeed


class _FakeExchange:
    """Minimal public-data ccxt client: only the read methods _one calls."""
    has = {"fetchFundingRate": False}

    def fetch_order_book(self, symbol, limit=20):
        return {"bids": [[100.0, 1.0], [99.5, 2.0]],
                "asks": [[100.5, 1.0], [101.0, 2.0]]}

    def fetch_ohlcv(self, symbol, timeframe="5m", limit=200):
        return [[1_000_000 + i * 300_000, 100.0, 101.0, 99.0, 100.5, 50.0]
                for i in range(40)]

    def fetch_ticker(self, symbol):
        return {"quoteVolume": 1_234_567.0}


# ------------------------------------------------- public-only / data-only
def test_refuses_credential_like_config():
    # any keyed mode is a construction-time refusal (fail closed)
    for bad in ({"api_key": "x"}, {"secret": "y"}, {"apiKey": "z"},
                {"token": "t"}, {"private-key": "p"}):
        with pytest.raises(ValueError):
            CCXTFeed(bad)


def test_clean_config_constructs_and_clamps():
    lo = CCXTFeed({"candle_limit": 5, "book_depth": 1})
    assert lo.candle_limit == 30 and lo.book_depth == 5
    hi = CCXTFeed({"candle_limit": 9999, "book_depth": 9999})
    assert hi.candle_limit == 500 and hi.book_depth == 100


# ------------------------------------------------------ _ensure_client seam
def test_injected_client_short_circuits_ensure():
    f = CCXTFeed({"symbols": ["ETH/USDT"]}, client=_FakeExchange())
    assert f._ensure_client() is True


def test_missing_ccxt_degrades_to_empty_feed(monkeypatch):
    def _boom():
        raise ImportError("no ccxt")
    f = CCXTFeed({"symbols": ["ETH/USDT"]})
    monkeypatch.setattr(f, "_import_sdk", _boom)
    assert f._ensure_client() is False
    assert f.get_market_data() == {}


def test_unknown_exchange_id_disables_feed(monkeypatch):
    class _FakeCcxt:           # module-like object with no such exchange attr
        pass
    f = CCXTFeed({"exchange": "nope_exchange", "symbols": ["ETH/USDT"]})
    monkeypatch.setattr(f, "_import_sdk", lambda: _FakeCcxt())
    assert f._ensure_client() is False


def test_successful_lazy_client_construction(monkeypatch):
    built = {}

    class _Klass:
        def __init__(self, opts):
            built["opts"] = opts

    class _FakeCcxt:
        okx = _Klass

    f = CCXTFeed({"exchange": "okx", "symbols": []})
    monkeypatch.setattr(f, "_import_sdk", lambda: _FakeCcxt())
    assert f._ensure_client() is True
    assert built["opts"] == {"enableRateLimit": True}   # ccxt paces itself


# ----------------------------------------------------------- data normalize
def test_get_market_data_returns_sanitized_payload():
    f = CCXTFeed({"symbols": ["ETH/USDT"]}, client=_FakeExchange())
    data = f.get_market_data()
    assert "ETH/USDT" in data
    p = data["ETH/USDT"]
    assert {"order_book", "candles", "funding_rate", "volume_24h", "ts"} <= set(p)
    assert p["order_book"]["bids"][0][0] == 100.0        # best bid, sorted
    assert p["order_book"]["asks"][0][0] == 100.5        # best ask, sorted
    assert p["volume_24h"] == 1_234_567.0
    assert p["funding_rate"] == 0.0                      # spot: neutral


def test_no_symbols_yields_empty_feed():
    assert CCXTFeed({}, client=_FakeExchange()).get_market_data() == {}


def test_per_symbol_fault_degrades_only_that_symbol():
    class _Flaky(_FakeExchange):
        def fetch_order_book(self, symbol, limit=20):
            if symbol == "BAD/USDT":
                raise RuntimeError("venue down")
            return super().fetch_order_book(symbol, limit)

    f = CCXTFeed({"symbols": ["ETH/USDT", "BAD/USDT"]}, client=_Flaky())
    data = f.get_market_data()
    assert "ETH/USDT" in data and "BAD/USDT" not in data


# --------------------------------------------------- degradation branches
def test_funding_rate_is_read_only_for_perp_symbols():
    class _Perp(_FakeExchange):
        has = {"fetchFundingRate": True}

        def fetch_funding_rate(self, symbol):
            return {"fundingRate": 0.0001}

    f = CCXTFeed({"symbols": ["ETH/USDT:USDT"]}, client=_Perp())   # ':' = perp
    assert f.get_market_data()["ETH/USDT:USDT"]["funding_rate"] == 0.0001


def test_empty_or_crossed_book_drops_the_symbol():
    class _NoBook(_FakeExchange):
        def fetch_order_book(self, symbol, limit=20):
            return {"bids": [], "asks": []}          # clean_book -> None

    f = CCXTFeed({"symbols": ["ETH/USDT"]}, client=_NoBook())
    assert f.get_market_data() == {}                  # symbol dropped, no crash


def test_ticker_failure_is_swallowed_but_payload_survives():
    class _NoTicker(_FakeExchange):
        def fetch_ticker(self, symbol):
            raise RuntimeError("ticker 500")

    p = CCXTFeed({"symbols": ["ETH/USDT"]},
                 client=_NoTicker()).get_market_data()["ETH/USDT"]
    assert p["volume_24h"] == 0.0                     # swallowed -> neutral
    assert p["order_book"]["bids"]                     # book still delivered


def test_client_init_failure_disables_feed(monkeypatch):
    class _BadKlass:
        def __init__(self, opts):
            raise RuntimeError("boom")

    class _FakeCcxt:
        okx = _BadKlass

    f = CCXTFeed({"exchange": "okx", "symbols": ["ETH/USDT"]})
    monkeypatch.setattr(f, "_import_sdk", lambda: _FakeCcxt())
    assert f._ensure_client() is False                # CCXT-004, not a crash
