"""
data/binanceus_feed.py

Read-only market data client for Binance.US. Uses public REST endpoints
only — no API keys, no signed requests, no trading. This module must
never place orders; Kraken (execution/) is the sole execution venue.

Notes:
  * Binance.US is a SPOT venue: there are no perpetuals and therefore no
    funding rates here. get_funding_rate() returns None by design and
    the liquidity model skips None values, so funding-based logic
    (signal gate 4, the funding feature) is driven by the OKX perp feed
    alone.
  * Spot USD pairs ("ETHUSD", "BTCUSD") are used rather than USDT pairs
    so the fair-value blend has no USDT/USD basis noise against the
    Kraken USD execution books.
  * 24h volume is returned in BASE units (ETH, BTC) to match the OKX
    convention; downstream ADV estimation multiplies by price.
"""

import logging
from typing import Optional

from core.sanitize import (clean_book, clean_candles, safe_float)
from data._http import ThrottledRestClient

BASE_URL = "https://api.binance.us"
log = logging.getLogger("liquiditybot.data.binanceus")

# /api/v3/depth only accepts these limit values
_VALID_DEPTH_LIMITS = (5, 10, 20, 50, 100, 500, 1000, 5000)


class BinanceUSFeed(ThrottledRestClient):
    def __init__(self, config: dict, ws=None):
        super().__init__(config.get("rate_limit_per_sec", 5))
        self.symbols = config.get("symbols", [])
        # optional push-based book source (data.ws_feed.WebSocketFeedManager,
        # duck-typed on get_order_book). When it has a FRESH cached book the
        # order-book read serves that instead of a REST round-trip; a stale
        # or absent cache (or a disabled manager) returns None and we fall
        # straight back to REST, so this is pure latency upside with no new
        # failure mode.
        self.ws = ws

    def _get(self, path: str, params: Optional[dict] = None):
        data = self._get_json(f"{BASE_URL}{path}", params, log, "Binance.US")
        # Binance signals errors as {"code": <negative>, "msg": ...}
        if isinstance(data, dict) and data.get("code", 0) < 0:
            log.warning(f"Binance.US API error for {path}: {data.get('msg')}")
            return None
        return data

    # --- Public read-only data -------------------------------------------------
    def get_order_book(self, symbol: str, depth: int = 20) -> Optional[dict]:
        # push-based fresh book first (sub-second); None means stale/absent/
        # disabled -> REST, the always-available source of truth
        if self.ws is not None:
            try:
                live = self.ws.get_order_book(symbol)
            except Exception:
                live = None
            if live is not None:
                return live
        limit = next((v for v in _VALID_DEPTH_LIMITS if v >= depth),
                    _VALID_DEPTH_LIMITS[-1])
        data = self._get("/api/v3/depth", {"symbol": symbol, "limit": limit})
        if not data or "bids" not in data:
            return None
        return clean_book({
            "bids": [list(lvl) for lvl in data.get("bids", [])],
            "asks": [list(lvl) for lvl in data.get("asks", [])],
        })

    def get_candles(self, symbol: str, interval: str = "5m",
                    limit: int = 100) -> list:
        """interval: 1m,3m,5m,15m,30m,1h,2h,4h,6h,8h,12h,1d,3d,1w,1M"""
        data = self._get("/api/v3/klines",
                        {"symbol": symbol, "interval": interval,
                        "limit": min(limit, 1000)})
        if not data:
            return []
        # Binance returns oldest-first already:
        # [openTime, open, high, low, close, volume(base), closeTime, ...]
        raw = [
            # Binance openTime is milliseconds; normalize to SECONDS to match
            # Kraken's unit (no cross-source candle-time mismatch)
            {"time": int(row[0]) // 1000, "open": row[1], "high": row[2],
            "low": row[3], "close": row[4], "volume": row[5]}
            for row in data
        ]
        return clean_candles(raw)

    def get_daily_candles(self, symbol: str, limit: int = 720) -> list:
        """Daily OHLCV, oldest-first. Feeds the macro regime engine (HMM/TSMOM)."""
        return self.get_candles(symbol, interval="1d", limit=min(limit, 1000))

    def get_funding_rate(self, symbol: str) -> Optional[float]:
        """Binance.US is spot-only: no perps, no funding. Returns None so the
        liquidity model's merge skips this source for funding; OKX's perp
        funding rate remains the sole funding input."""
        return None

    def get_24h_volume(self, symbol: str) -> Optional[float]:
        data = self._get("/api/v3/ticker/24hr", {"symbol": symbol})
        if not data:
            return None
        try:
            return safe_float(data.get("volume"), default=0.0, lo=0.0)
        except (KeyError, TypeError, ValueError):
            return None

    def get_market_data(self) -> dict:
        """Aggregate order book, candles, funding, and volume for all symbols."""
        result = {}
        for symbol in self.symbols:
            order_book = self.get_order_book(symbol)
            if order_book is None:
                log.warning(f"Binance.US: skipping {symbol}, order book unavailable")
                continue
            result[symbol] = {
                "order_book": order_book,
                "candles": self.get_candles(symbol),
                "funding_rate": self.get_funding_rate(symbol),
                "volume_24h": self.get_24h_volume(symbol),
            }
        return result
