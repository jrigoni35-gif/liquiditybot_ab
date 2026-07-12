"""
core/precision.py — per-asset price DISPLAY precision.

The engine computes at full float64 precision throughout (marks, candle
closes, book prices, fair value, PnL, features and labels are never
rounded in any decision or learning path). This module is ONLY about how
a price is rendered for a human or written to the status file, so a
sub-dollar pair is never shown or stored on a coarser grid than its own
venue tick size.

The single source of truth for a pair's precision is Kraken AssetPairs
metadata (`pair_meta[pair]["price_decimals"]`), the exact value the order
path already formats submitted prices to — BTC=1, ETH=2, SUI/ARB/FLOW=4,
MINA=5. A price-magnitude floor guards the case where metadata is absent
or coarse: a $0.09 asset at 2 decimals is an ~11% quantization grid, so
anything under $1 gets at least SUB_DOLLAR_DECIMALS regardless.
"""

from typing import Optional

DEFAULT_DECIMALS = 2
SUB_DOLLAR_DECIMALS = 4


def price_decimals(pair_meta: Optional[dict], pair: str,
                   price: Optional[float] = None) -> int:
    """Decimals to render `pair` at: venue precision, floored so a
    sub-dollar price keeps enough resolution to be meaningful even when
    the metadata is missing or coarser than the asset's own tick."""
    d = DEFAULT_DECIMALS
    meta = (pair_meta or {}).get(pair)
    if isinstance(meta, dict):
        try:
            d = int(meta.get("price_decimals", DEFAULT_DECIMALS))
        except (TypeError, ValueError):
            d = DEFAULT_DECIMALS
    d = max(d, DEFAULT_DECIMALS)
    try:
        if price is not None and 0.0 < abs(float(price)) < 1.0:
            d = max(d, SUB_DOLLAR_DECIMALS)
    except (TypeError, ValueError):
        pass
    return d


def round_price(price, pair_meta: Optional[dict], pair: str):
    """Round a price to its per-asset display precision. None passes
    through (callers distinguish 'no price' from 0.0)."""
    if price is None:
        return None
    try:
        p = float(price)
    except (TypeError, ValueError):
        return None
    return round(p, price_decimals(pair_meta, pair, p))


def fmt_price(price, pair_meta: Optional[dict], pair: str) -> str:
    """Format a price string at its per-asset display precision."""
    if price is None:
        return "n/a"
    try:
        p = float(price)
    except (TypeError, ValueError):
        return "n/a"
    return f"{p:.{price_decimals(pair_meta, pair, p)}f}"
