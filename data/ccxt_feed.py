"""
data/ccxt_feed.py — CCXT read-only market-data adapter, rev 4

Lets any ccxt-supported exchange serve as a DATA source through the
same interface the native OKX/Binance.US feeds expose
(get_market_data() -> {symbol: {order_book, candles, funding_rate,
volume_24h}}), so it drops into strategies/liquidity_model.build_view
and into main via the existing feed-injection seams.

Boundaries, enforced in code not prose:
  * DATA ONLY. This adapter never places, amends or cancels anything —
    only fetch_order_book / fetch_ohlcv / fetch_ticker /
    fetch_funding_rate are ever called. Kraken remains the sole
    execution venue (order_manager path untouched).
  * PUBLIC ENDPOINTS ONLY. If the config block contains anything that
    looks like a credential (api_key/apiKey/secret/password/token),
    __init__ REFUSES to construct — CCXT-001. There is no keyed mode.
  * ccxt is an OPTIONAL dependency (lazy import behind a seam, moomoo
    pattern): absence degrades to an empty feed with one warning.
  * every payload crosses core/sanitize before anything downstream
    sees it — same hostile-input posture as the native feeds.
"""

import logging
import math
import time

from core.sanitize import clean_book, clean_candles

log = logging.getLogger("liquiditybot.data.ccxt")

_CREDENTIAL_KEYS = {"api_key", "apikey", "secret", "api_secret",
                    "password", "token", "uid", "privatekey",
                    "private_key", "walletaddress"}


def _f(x, default=0.0) -> float:
    try:
        v = float(x)
        return v if math.isfinite(v) else default
    except (TypeError, ValueError):
        return default


class CCXTFeed:
    def __init__(self, config: dict, client=None):
        cfg = config or {}
        leaked = {k for k in cfg if k.lower().replace("-", "_")
                  in _CREDENTIAL_KEYS and cfg.get(k)}
        if leaked:
            # fail CLOSED and loud: this adapter has no authorized mode
            raise ValueError(
                f"CCXT-001: credential-like keys {sorted(leaked)} in ccxt "
                f"config — this adapter is public-data-only by design; "
                f"remove them")
        self.exchange_id = str(cfg.get("exchange", "okx")).lower()
        self.symbols = list(cfg.get("symbols", []))
        self.timeframe = str(cfg.get("timeframe", "5m"))
        self.candle_limit = min(max(int(cfg.get("candle_limit", 200)), 30),
                                500)
        self.book_depth = min(max(int(cfg.get("book_depth", 20)), 5), 100)
        self._client = client              # injectable for tests
        self._warned = False

    # ------------------------------------------------------------------
    @staticmethod
    def _import_sdk():
        """Seam (moomoo pattern): tests patch this; production imports
        lazily; absence is handled at the single call site."""
        import ccxt  # type: ignore  # optional dependency; absence handled in _ensure_client
        return ccxt

    def _ensure_client(self):
        if self._client is not None:
            return True
        try:
            ccxt = self._import_sdk()
            klass = getattr(ccxt, self.exchange_id, None)
            if klass is None:
                if not self._warned:
                    log.warning("CCXT-002: exchange id %r unknown to ccxt "
                                "- feed disabled", self.exchange_id)
                    self._warned = True
                return False
            # enableRateLimit: ccxt paces itself under venue limits
            self._client = klass({"enableRateLimit": True})
            log.info("ccxt feed up: %s (public endpoints, data only)",
                     self.exchange_id)
            return True
        except ImportError:
            if not self._warned:
                log.warning("CCXT-003: ccxt not installed (pip install "
                            "ccxt) - feed disabled, bot runs without it")
                self._warned = True
        except Exception as e:
            if not self._warned:
                log.warning("CCXT-004: client init failed (%s) - feed "
                            "disabled", e)
                self._warned = True
        return False

    # ------------------------------------------------------------------
    def _one(self, symbol: str) -> dict:
        c = self._client
        assert c is not None  # _one is only reached after _ensure_client() succeeds
        raw_book = c.fetch_order_book(symbol, limit=self.book_depth)
        book = clean_book({"bids": raw_book.get("bids") or [],
                              "asks": raw_book.get("asks") or []})
        if book is None:
            return {}
        raw = c.fetch_ohlcv(symbol, timeframe=self.timeframe,
                            limit=self.candle_limit) or []
        candles = clean_candles([
            {"time": _f(r[0]) / 1000.0, "open": _f(r[1]), "high": _f(r[2]),
             "low": _f(r[3]), "close": _f(r[4]), "volume": _f(r[5])}
            for r in raw if isinstance(r, (list, tuple)) and len(r) >= 6])
        funding = 0.0
        try:
            if getattr(c, "has", {}).get("fetchFundingRate") and \
                    symbol.endswith(("SWAP", "PERP")) or ":" in symbol:
                fr = c.fetch_funding_rate(symbol)
                funding = _f((fr or {}).get("fundingRate"))
        except Exception:
            funding = 0.0                  # spot venues: fine, neutral
        vol24 = 0.0
        try:
            t = c.fetch_ticker(symbol) or {}
            vol24 = _f(t.get("quoteVolume") or t.get("baseVolume"))
        except Exception:  # read-only enrichment; a dead ticker must not break the feed  # nosec B110
            pass
        return {"order_book": book, "candles": candles,
                "funding_rate": funding, "volume_24h": vol24,
                "ts": time.time()}

    def get_market_data(self) -> dict:
        """OKXFeed-compatible: {exchange_symbol: payload}. Any per-symbol
        fault degrades that symbol only — the loop never breaks."""
        if not self.symbols or not self._ensure_client():
            return {}
        out = {}
        for sym in self.symbols:
            try:
                d = self._one(sym)
                if d:
                    out[sym] = d
            except Exception as e:
                log.warning("CCXT-005: %s fetch failed (%s) - degraded",
                            sym, e)
        return out
