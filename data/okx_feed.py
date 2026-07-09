"""
data/okx_feed.py

Read-only market data client for OKX. Uses public REST endpoints only —
no trading, no signed requests. This module must never place orders;
Kraken (execution/order_manager.py) is the sole execution venue.
"""

import logging
from typing import Optional

from core.sanitize import (clean_book, clean_candles, safe_float)
from data._http import ThrottledRestClient

BASE_URL = "https://www.okx.com"
log = logging.getLogger("liquiditybot.data.okx")


class OKXFeed(ThrottledRestClient):
    def __init__(self, config: dict):
        super().__init__(config.get("rate_limit_per_sec", 5))
        self.symbols = config.get("symbols", [])

    def _get(self, path: str, params: Optional[dict] = None) -> Optional[dict]:
        data = self._get_json(f"{BASE_URL}{path}", params, log, "OKX")
        if not isinstance(data, dict):
            return None
        if data.get("code") != "0":
            log.warning(f"OKX API returned non-zero code for {path}: {data.get('msg')}")
            return None
        return data.get("data")

    def get_order_book(self, symbol: str, depth: int = 20) -> Optional[dict]:
        data = self._get("/api/v5/market/books", {"instId": symbol, "sz": depth})
        if not data:
            return None
        book = data[0]
        return clean_book({
            "bids": [list(lvl) for lvl in book.get("bids", [])],
            "asks": [list(lvl) for lvl in book.get("asks", [])],
        })

    def get_candles(self, symbol: str, bar: str = "5m", limit: int = 100) -> list:
        data = self._get("/api/v5/market/candles", {"instId": symbol, "bar": bar, "limit": limit})
        if not data:
            return []
        # OKX returns newest-first: [ts, o, h, l, c, vol, volCcy, volCcyQuote, confirm]
        raw = [
            # OKX timestamps are milliseconds; normalize to SECONDS so all
            # feeds (Kraken uses seconds) share one unit and no cross-source
            # candle-time comparison can be off by 1000x
            {"time": int(row[0]) // 1000, "open": row[1], "high": row[2],
             "low": row[3], "close": row[4], "volume": row[5]}
            for row in data
        ]
        raw.reverse()  # oldest-first for EMA/indicator calcs
        # same sanitize layer as the Kraken/Binance.US candle paths:
        # numeric coercion + malformed-bar rejection in one place
        return clean_candles(raw)

    def get_daily_candles(self, symbol: str, limit: int = 300) -> list:
        """Daily OHLCV, oldest-first. Feeds the macro regime engine (HMM/TSMOM)."""
        return self.get_candles(symbol, bar="1D", limit=min(limit, 300))

    def get_history_candles(self, symbol: str, bar: str = "5m",
                            total: int = 2880) -> list:
        """Deep OHLCV history via the paginated /market/history-candles
        endpoint (public, read-only; 100 bars/page, newest-first pages walked
        backward with the `after` cursor). Returns up to `total` bars,
        oldest-first, sanitized. The plain get_candles endpoint caps at 300
        bars - too few EMA-cross events to bootstrap a training set."""
        rows: list = []
        after = ""
        pages = (min(max(total, 1), 20_000) + 99) // 100
        for _ in range(pages):
            params = {"instId": symbol, "bar": bar, "limit": 100}
            if after:
                params["after"] = after
            data = self._get("/api/v5/market/history-candles", params)
            if not data:
                break
            rows.extend(data)
            after = data[-1][0]            # oldest ts of this page
            if len(data) < 100 or len(rows) >= total:
                break
        raw = [
            {"time": int(r[0]) // 1000, "open": r[1], "high": r[2],  # ms -> s
             "low": r[3], "close": r[4], "volume": r[5]}
            for r in rows[:total]
        ]
        raw.reverse()                      # oldest-first for indicator calcs
        return clean_candles(raw)

    def get_funding_rate(self, symbol: str) -> Optional[float]:
        data = self._get("/api/v5/public/funding-rate", {"instId": symbol})
        if not data:
            return None
        return safe_float(data[0].get("fundingRate"), default=0.0,
                        lo=-1.0, hi=1.0)

    def get_24h_volume(self, symbol: str) -> Optional[float]:
        data = self._get("/api/v5/market/ticker", {"instId": symbol})
        if not data:
            return None
        return safe_float(data[0].get("volCcy24h"), default=0.0, lo=0.0)

    def get_market_data(self) -> dict:
        """Aggregate order book, candles, funding rate, and 24h volume for all configured symbols."""
        result = {}
        for symbol in self.symbols:
            order_book = self.get_order_book(symbol)
            candles = self.get_candles(symbol)
            funding_rate = self.get_funding_rate(symbol)
            volume_24h = self.get_24h_volume(symbol)

            if order_book is None:
                log.warning(f"OKX: skipping {symbol}, order book unavailable")
                continue

            result[symbol] = {
                "order_book": order_book,
                "candles": candles,
                "funding_rate": funding_rate,
                "volume_24h": volume_24h,
            }
        return result
