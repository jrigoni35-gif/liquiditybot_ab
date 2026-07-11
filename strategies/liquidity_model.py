"""
strategies/liquidity_model.py

Merges read-only market data from OKX and Binance.US into a single unified
per-asset view for the signal gate engine to evaluate. Each exchange
uses a different symbol format (OKX: 'ETH-USDT-SWAP', Binance.US: 'ETHUSD'),
so this module normalizes both down to a canonical base asset (e.g. 'ETH')
and maps that asset to the Kraken pair that will actually be traded.
"""

import logging
from typing import Optional

log = logging.getLogger("liquiditybot.strategies.liquidity_model")

# Canonical base asset -> Kraken trading pair. Keep in sync with
# config.json's exchanges.kraken.trading_pairs list.
# Default base-asset -> Kraken pair map. Kept for callers that construct
# LiquidityModel without config (tests, offline tools); the live engine
# passes the real map derived from config exchanges.kraken.trading_pairs
# so adding a pair there needs no edit here. Adding a pair to trade meant
# editing this literal too, which silently dropped any asset missing from
# it at the view-merge layer.
BASE_ASSET_TO_KRAKEN_PAIR = {
    "ETH": "ETH/USD",
    "BTC": "BTC/USD",
}


def extract_base_asset(symbol: str) -> Optional[str]:
    """
    Normalizes exchange-specific symbol formats to a canonical base asset:
        OKX:    'ETH-USDT-SWAP'  -> 'ETH'
        Binance.US: 'ETHUSD'     -> 'ETH'
        CCXT unified: 'ETH/USDT:USDT' (perp) or 'ETH/USD' (spot) -> 'ETH'
        (USDT/USDC-quoted symbols normalize the same way)
    """
    symbol = symbol.upper()
    # CCXT unified: strip the settle-currency suffix, then take the base
    # ('ETH/USDT:USDT' -> 'ETH/USDT' -> 'ETH'); previously this fell through
    # to the dash branch and produced garbage, so the wired ccxt feed's data
    # was silently dropped at the merge layer
    if ":" in symbol:
        symbol = symbol.split(":")[0]
    if "/" in symbol:
        return symbol.split("/")[0] or None
    if "-" in symbol:
        return symbol.split("-")[0] or None
    for quote in ("USDT", "USDC", "USD"):
        if symbol.endswith(quote):
            return symbol[: -len(quote)] or None
    return None


class LiquidityModel:
    def __init__(self, config: dict):
        self.gate_1_config = config.get("gate_1_liquidity_pool", {})
        # base -> kraken pair map, derived from the configured execution
        # pairs so a new trading_pair is picked up automatically; falls
        # back to the module default when config carries no kraken block
        # (bare LiquidityModel({}) in tests/offline tools).
        pairs = (config.get("exchanges", {}).get("kraken", {})
                 .get("trading_pairs")) or []
        self.base_to_pair = {p.split("/")[0].upper(): p for p in pairs} \
            or dict(BASE_ASSET_TO_KRAKEN_PAIR)

    def _combine_order_books(self, books: list) -> dict:
        """Concatenates bids/asks from multiple exchanges, best price first."""
        if not books:
            return {"bids": [], "asks": []}
        all_bids = [b for book in books for b in book.get("bids", [])]
        all_asks = [a for book in books for a in book.get("asks", [])]
        all_bids.sort(key=lambda x: -x[0])  # highest bid first
        all_asks.sort(key=lambda x: x[0])   # lowest ask first
        return {"bids": all_bids, "asks": all_asks}

    def _order_book_depth_usd(self, order_book: dict, levels: int = 10) -> float:
        """Sum of (price * size) across top N levels on both sides, in quote currency."""
        bids = order_book.get("bids", [])[:levels]
        asks = order_book.get("asks", [])[:levels]
        return sum(p * s for p, s in bids) + sum(p * s for p, s in asks)

    # imbalance is scale-invariant only WITHIN one venue's book. Clamp so a
    # one-sided book can't saturate the downstream log() feature / flow gate.
    _IMB_CAP = 5.0

    def _imbalance_ratio(self, order_book: dict, levels: int = 10) -> float:
        """bid depth / ask depth across top N levels of ONE venue's book.
        >1 means buy-side heavier. Clamped to [1/cap, cap]."""
        bids = order_book.get("bids", [])[:levels]
        asks = order_book.get("asks", [])[:levels]
        bid_depth = sum(p * s for p, s in bids)
        ask_depth = sum(p * s for p, s in asks)
        if ask_depth <= 0:
            return self._IMB_CAP if bid_depth > 0 else 1.0
        return max(1.0 / self._IMB_CAP, min(bid_depth / ask_depth, self._IMB_CAP))

    def _combined_imbalance(self, books: list, levels: int = 10) -> float:
        """Average of PER-VENUE imbalance ratios. Computing it on the
        concatenated multi-venue book is invalid: OKX (SWAP, contract-unit
        sizes, perp price) and BinanceUS (spot, coin-unit sizes) don't share
        size units, so summing price*size across them yields a garbage ratio
        (observed live 22-112x -> the log() feature pinned at its clip ceiling
        and the informed-flow flow gate mis-driven). A ratio is unit-consistent
        only within one book, so average per-venue ratios instead."""
        ratios = [self._imbalance_ratio(b, levels) for b in books
                  if b and b.get("bids") and b.get("asks")]
        return sum(ratios) / len(ratios) if ratios else 1.0

    def _ingest(self, merged: dict, source_data: dict):
        for symbol, data in source_data.items():
            base = extract_base_asset(symbol)
            if base is None:
                log.warning(f"Could not determine base asset for symbol {symbol}, skipping.")
                continue
            entry = merged.setdefault(base, {
                "order_books": [],
                "candles": [],
                "funding_rates": [],
                "volume_24h_total": 0.0,
            })
            if data.get("order_book"):
                entry["order_books"].append(data["order_book"])
            if data.get("candles") and len(data["candles"]) > len(entry["candles"]):
                entry["candles"] = data["candles"]  # prefer the longer history
            if data.get("funding_rate") is not None:
                entry["funding_rates"].append(data["funding_rate"])
            if data.get("volume_24h"):
                entry["volume_24h_total"] += data["volume_24h"]

    def build_view(self, *sources: dict) -> dict:
        """
        Returns a dict keyed by canonical base asset (e.g. 'ETH'), each
        holding combined order book depth, imbalance, candles, funding
        rate, volume, and the Kraken pair to trade if a signal confirms.

        Accepts any number of feed payloads (OKX, Binance.US, and the
        optional CCXT adapter) - previously hardcoded to exactly two, which
        left the config-declared ccxt feed silently unwired.
        """
        merged = {}
        for source_data in sources:
            self._ingest(merged, source_data or {})

        view = {}
        for base, entry in merged.items():
            kraken_symbol = self.base_to_pair.get(base)
            if kraken_symbol is None:
                log.warning(f"No Kraken pair mapping for base asset {base}, skipping.")
                continue

            combined_book = self._combine_order_books(entry["order_books"])
            avg_funding = (
                sum(entry["funding_rates"]) / len(entry["funding_rates"])
                if entry["funding_rates"] else 0.0
            )

            view[base] = {
                "kraken_symbol": kraken_symbol,
                "order_book": combined_book,
                "liquidity_pool_usd": self._order_book_depth_usd(combined_book),
                "imbalance_ratio": self._combined_imbalance(entry["order_books"]),
                "candles": entry["candles"],
                "funding_rate": avg_funding,
                "volume_24h": entry["volume_24h_total"],
            }
        return view
