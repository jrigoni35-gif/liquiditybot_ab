"""
data/okx_feed.py

Read-only market data client for OKX. Uses public REST endpoints only —
no trading, no signed requests. This module must never place orders;
Kraken (execution/order_manager.py) is the sole execution venue.
"""

import logging
import math
from typing import Optional

from core.sanitize import (clean_book, clean_candles, drop_forming_candles,
                           interval_str_to_sec, safe_float)
from data._http import ThrottledRestClient

BASE_URL = "https://www.okx.com"
log = logging.getLogger("liquiditybot.data.okx")


class OKXFeed(ThrottledRestClient):
    def __init__(self, config: dict):
        super().__init__(config.get("rate_limit_per_sec", 5))
        self.symbols = config.get("symbols", [])
        self._ctval_cache: dict = {}

    def _ctval(self, symbol: str) -> Optional[float]:
        """SWAP order-book size is in CONTRACTS, not coin units (e.g.
        BTC-USDT-SWAP ctVal=0.01 means 1 contract = 0.01 BTC); spot symbols
        need no conversion. Without this, price*size overstates USD depth
        by 1/ctVal - the same unit-mismatch class that previously corrupted
        the cross-venue imbalance ratio (see strategies/liquidity_model.py
        _combined_imbalance), except the depth/liquidity_pool_usd figure
        has no ratio to cancel it out, so it stayed wrong. Cached per
        symbol - contract specs are static intraday; a failed lookup is
        NOT cached so it retries on the next call instead of silently
        pinning to the unconverted default forever."""
        if "-SWAP" not in symbol.upper():
            return 1.0
        cached = self._ctval_cache.get(symbol)
        if cached is not None:
            return cached
        data = self._get("/api/v5/public/instruments",
                         {"instType": "SWAP", "instId": symbol})
        if not data:
            # DL-8: raw contract units are wrong by 1/ctVal (100x for
            # BTC ctVal=0.01) - a silently mis-scaled book poisons depth
            # and composite-imbalance features. Fail closed: no ctVal,
            # no book from this venue this cycle (the composite
            # tolerates a missing venue; a mis-scaled one it cannot).
            log.warning(f"OKX: ctVal lookup failed for {symbol} - "
                       f"skipping this venue's book this cycle "
                       f"(unscalable contract units)")
            return None
        ct = safe_float(data[0].get("ctVal"), default=1.0, lo=1e-9, hi=1e6)
        self._ctval_cache[symbol] = ct
        return ct

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
        ct = self._ctval(symbol)
        if ct is None:                    # DL-8: unscalable, skip
            return None

        def _scaled(levels):
            out = []
            for lvl in levels:
                try:
                    out.append([float(lvl[0]), float(lvl[1]) * ct])
                except (TypeError, ValueError, IndexError):
                    out.append(lvl)   # malformed row: let clean_book reject it
            return out

        return clean_book({
            "bids": _scaled(book.get("bids", [])),
            "asks": _scaled(book.get("asks", [])),
        })

    def get_candles(self, symbol: str, bar: str = "5m", limit: int = 100,
                    include_forming: bool = False) -> list:
        """Committed bars only by default: OKX's newest row is the forming
        candle (confirm=0) whose H/L/C keep mutating - poison for any
        append-only downstream cache. include_forming=True restores it."""
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
        out = clean_candles(raw)
        if include_forming:
            return out
        # W2-22: `confirm` (row[8]) is already part of every row this
        # endpoint returns - exact committed/forming ground truth, no clock
        # skew possible. Use it when present; fall back to the clock
        # heuristic only if the response omits it.
        if data and len(data[0]) > 8:
            committed_ts = {int(row[0]) // 1000 for row in data if str(row[8]) == "1"}
            return [c for c in out if c.get("time") in committed_ts]
        return drop_forming_candles(out, interval_str_to_sec(bar))

    def get_daily_candles(self, symbol: str, limit: int = 300) -> list:
        """Daily OHLCV, oldest-first. Feeds the macro regime engine
        (HMM/TSMOM). Keeps today's forming bar: regime reads momentum "as
        of now" and the hourly refit self-corrects the partial bar."""
        return self.get_candles(symbol, bar="1D", limit=min(limit, 300),
                                include_forming=True)

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
        # bootstrap training data must be committed bars only too.
        # max_n=len(raw): clean_candles defaults to keeping the last 2000
        # bars, which SILENTLY truncated every deep request past that -
        # train_meta asks for 2880 (~10 days of 5m bars) and received ~7
        # days with no log line, while the docstring promised `total`
        # (round-2 finding 2026-08-05). The cap exists to bound live
        # per-cycle fetches; a deliberate paginated history request is
        # exactly the case it should not silently shrink.
        return drop_forming_candles(clean_candles(raw, max_n=max(len(raw), 1)),
                                    interval_str_to_sec(bar))

    def get_funding_rate(self, symbol: str) -> Optional[float]:
        data = self._get("/api/v5/public/funding-rate", {"instId": symbol})
        if not data:
            return None
        # DL-11: an unparsable rate must surface as UNAVAILABLE (None),
        # never as 0.0 - a fake 'funding is zero' print defeats the
        # funding gate's fail-closed unavailable handling downstream.
        raw = safe_float(data[0].get("fundingRate"),
                         default=float("nan"), lo=-1.0, hi=1.0)
        return None if math.isnan(raw) else raw

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
