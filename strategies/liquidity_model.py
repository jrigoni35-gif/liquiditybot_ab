"""
strategies/liquidity_model.py

Merges read-only market data from OKX and Binance.US into a single unified
per-asset view for the signal gate engine to evaluate. Each exchange
uses a different symbol format (OKX: 'ETH-USDT-SWAP', Binance.US: 'ETHUSD'),
so this module normalizes both down to a canonical base asset (e.g. 'ETH')
and maps that asset to the Kraken pair that will actually be traded.
"""

import logging
import math
import time
from typing import Optional

log = logging.getLogger("liquiditybot.strategies.liquidity_model")

EPS = 1e-9


def _best_level(side: list) -> Optional[tuple]:
    """(price, size) of a side's best level; None when the side is
    absent/malformed/non-finite (fail-closed: an invalid book produces
    no OFI event, mirroring fair_value's no-vote convention)."""
    if not side:
        return None
    try:
        p, s = float(side[0][0]), float(side[0][1])
    except (TypeError, ValueError, IndexError):
        return None
    if not (math.isfinite(p) and p > 0.0 and math.isfinite(s) and s >= 0.0):
        return None
    return p, s


def _ofi_event(prev: tuple, cur: tuple) -> float:
    """Best-level order-flow imbalance event per Cont-Kukanov-Stoikov
    2014 (J. Financial Econometrics 12(1):47-88, eq. 4), prev/cur =
    (Pb, qb, Pa, qa) of consecutive polls:

        e_n = 1{Pb_n>=Pb_n-1}*qb_n - 1{Pb_n<=Pb_n-1}*qb_n-1
            - 1{Pa_n<=Pa_n-1}*qa_n + 1{Pa_n>=Pa_n-1}*qa_n-1

    Positive = net buy pressure (bid adds / ask cancels / prices
    stepping up), negative = net sell pressure. Size units are the
    venue's own - callers normalize by the same venue's depth scale
    before mixing venues (the _combined_imbalance unit lesson)."""
    pb0, qb0, pa0, qa0 = prev
    pb1, qb1, pa1, qa1 = cur
    e = 0.0
    if pb1 >= pb0:
        e += qb1
    if pb1 <= pb0:
        e -= qb0
    if pa1 <= pa0:
        e -= qa1
    if pa1 >= pa0:
        e += qa0
    return e

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
        # v8 anti-layering: SAME knob as regime/liquidity_regime.py (one
        # source of truth - the regime engine and the view imbalance must
        # weigh painted depth identically or manip divergence would flag
        # our own asymmetry). 0 disables (legacy equal-weight).
        self.imbalance_decay_bps = float(
            (config.get("liquidity_regime", {}) or {})
            .get("imbalance_decay_bps", 15.0))
        # v9 SHADOW feature state (ml ofi_dir only - the shadow-purity
        # grep in tests/test_ofi_feature.py proves no gate/sizer/exit/
        # execution module reads the view key this produces). Config
        # under liquidity_regime.ofi (defaults documented there);
        # process-local, never snapshotted - a restart costs one EWMA
        # warmup, same non-persistence class as HistoryStore's rolling
        # telemetry windows.
        ofi_cfg = ((config.get("liquidity_regime", {}) or {})
                   .get("ofi") or {})
        self._ofi_cfg = {
            "ewma_tau_sec": float(ofi_cfg.get("ewma_tau_sec", 60.0)),
            "depth_tau_sec": float(ofi_cfg.get("depth_tau_sec", 300.0)),
            "stale_sec": float(ofi_cfg.get("stale_sec", 120.0)),
        }
        self._ofi_prev: dict = {}    # (base, src, k) -> (Pb, qb, Pa, qa)
        self._ofi_depth: dict = {}   # (base, src, k) -> EWMA best depth
        self._ofi_ewma: dict = {}    # base -> current ofi_event value
        self._ofi_ts: dict = {}      # base -> last build_view ts

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

    @staticmethod
    def _decayed_depth(side: list, levels: int, decay_bps: float) -> float:
        """Top-N notional, each level weighted exp(-dist_bps/decay_bps)
        against the side's OWN best (v8 anti-layering, Stoikov 2018: far
        size is cheap to paint and cancel, near-touch size gets executed
        - the touch carries the information). Own-best reference = shape
        only, the spread is not counted. decay_bps <= 0 is the exact
        legacy equal-weight sum."""
        if decay_bps <= 0.0 or not side or side[0][0] <= 0:
            return sum(p * s for p, s in side[:levels])
        best = side[0][0]
        return sum(p * s * math.exp(-(abs(p - best) / best * 1e4)
                                    / decay_bps)
                   for p, s in side[:levels])

    def _imbalance_ratio(self, order_book: dict, levels: int = 10,
                         decay_bps: float = 0.0) -> float:
        """bid depth / ask depth across top N levels of ONE venue's book.
        >1 means buy-side heavier. Clamped to [1/cap, cap]. decay_bps > 0
        distance-decays each level toward its own best (0 = legacy)."""
        bids = order_book.get("bids", [])
        asks = order_book.get("asks", [])
        bid_depth = self._decayed_depth(bids, levels, decay_bps)
        ask_depth = self._decayed_depth(asks, levels, decay_bps)
        if ask_depth <= 0:
            return self._IMB_CAP if bid_depth > 0 else 1.0
        return max(1.0 / self._IMB_CAP, min(bid_depth / ask_depth, self._IMB_CAP))

    def _combined_imbalance(self, books: list, levels: int = 10,
                            decay_bps: float = 0.0) -> float:
        """Average of PER-VENUE imbalance ratios. Computing it on the
        concatenated multi-venue book is invalid: OKX (SWAP, contract-unit
        sizes, perp price) and BinanceUS (spot, coin-unit sizes) don't share
        size units, so summing price*size across them yields a garbage ratio
        (observed live 22-112x -> the log() feature pinned at its clip ceiling
        and the informed-flow flow gate mis-driven). A ratio is unit-consistent
        only within one book, so average per-venue ratios instead."""
        ratios = [self._imbalance_ratio(b, levels, decay_bps) for b in books
                  if b and b.get("bids") and b.get("asks")]
        return sum(ratios) / len(ratios) if ratios else 1.0

    def _ingest(self, merged: dict, source_data: dict, src_idx: int = 0):
        for symbol, data in source_data.items():
            base = extract_base_asset(symbol)
            if base is None:
                log.warning(f"Could not determine base asset for symbol {symbol}, skipping.")
                continue
            entry = merged.setdefault(base, {
                "order_books": [],
                "book_srcs": [],
                "candles": [],
                "funding_rates": [],
                "volume_24h_total": 0.0,
            })
            if data.get("order_book"):
                entry["order_books"].append(data["order_book"])
                # feed identity, parallel to order_books: the OFI event
                # needs CONSECUTIVE polls of the SAME venue's book (sizes
                # are venue-unit-local; diffing OKX contracts against
                # BinanceUS coins fabricates flow)
                entry["book_srcs"].append(src_idx)
            if data.get("candles") and len(data["candles"]) > len(entry["candles"]):
                entry["candles"] = data["candles"]  # prefer the longer history
            if data.get("funding_rate") is not None:
                entry["funding_rates"].append(data["funding_rate"])
            if data.get("volume_24h"):
                entry["volume_24h_total"] += data["volume_24h"]

    # OFI EWMA output bound, in touch-depth turnovers per minute: a full
    # best-level replacement every 6 seconds saturates it. A structural
    # sanity clamp (same class as _IMB_CAP), not a tunable - the feature
    # clip in ml/features.py is far tighter anyway.
    _OFI_CAP = 10.0

    def _ofi_update(self, base: str, books: list, srcs: list,
                    now: float) -> float:
        """Event-based best-level OFI (Cont-Kukanov-Stoikov 2014) as a
        wall-time EWMA, per the THALES A-3 lesson: every event is
        normalized by the REAL poll gap dt (never per-event/per-poll
        units, which alias with cadence) and by the venue's OWN rolling
        EWMA best-level depth (unit consistency across venues), scaled
        x60 = touch-depth turnover per minute; per-venue rates are
        averaged (the _combined_imbalance lesson), then blended with
        alpha = 1-exp(-dt/tau). A gap beyond stale_sec RESETS to the
        0.0 neutral rather than decaying a fossil; invalid/one-sided
        books produce no event and re-seed on the next valid poll.
        Fail-safe: any degenerate input path lands on 0.0."""
        cfg = getattr(self, "_ofi_cfg", None)
        if cfg is None:      # __new__-built harness instance: self-heal
            return 0.0
        prev_ts = self._ofi_ts.get(base)
        # dt < 0 encodes "no prior poll" (first sight of this asset)
        dt = (now - prev_ts) if prev_ts is not None else -1.0
        live = 0.0 < dt <= cfg["stale_sec"]
        rates: list = []
        counts: dict = {}
        # strict=False deliberately: a book_srcs/order_books length skew
        # (a __new__-built harness passing books with no srcs) degrades
        # to fewer events, never a raise in the view build
        for src, book in zip(srcs, books, strict=False):
            k = counts.get(src, 0)
            counts[src] = k + 1
            key = (base, src, k)
            bid = _best_level((book or {}).get("bids") or [])
            ask = _best_level((book or {}).get("asks") or [])
            if bid is None or ask is None:
                self._ofi_prev.pop(key, None)     # re-seed next poll
                continue
            cur = (bid[0], bid[1], ask[0], ask[1])
            prev = self._ofi_prev.get(key)
            self._ofi_prev[key] = cur
            depth = 0.5 * (bid[1] + ask[1])
            ds = self._ofi_depth.get(key, 0.0)
            if ds <= 0.0 or not live:
                ds = depth                        # (re-)seed the scale
            else:
                beta = 1.0 - math.exp(-dt / max(cfg["depth_tau_sec"], EPS))
                ds = beta * depth + (1.0 - beta) * ds
            self._ofi_depth[key] = ds
            if prev is None or not live or ds <= 0.0:
                continue
            rates.append(_ofi_event(prev, cur) / ds / dt * 60.0)
        out = self._ofi_ewma.get(base, 0.0)
        self._ofi_ts[base] = now
        if dt > cfg["stale_sec"]:
            out = 0.0        # stale feed: neutral, never a fossil
        elif live:
            alpha = 1.0 - math.exp(-dt / max(cfg["ewma_tau_sec"], EPS))
            r = sum(rates) / len(rates) if rates else 0.0
            out = alpha * r + (1.0 - alpha) * out
        if not math.isfinite(out):
            out = 0.0
        out = max(-self._OFI_CAP, min(out, self._OFI_CAP))
        self._ofi_ewma[base] = out
        return out

    def build_view(self, *sources: dict,
                   now: Optional[float] = None) -> dict:
        """
        Returns a dict keyed by canonical base asset (e.g. 'ETH'), each
        holding combined order book depth, imbalance, candles, funding
        rate, volume, and the Kraken pair to trade if a signal confirms.

        Accepts any number of feed payloads (OKX, Binance.US, and the
        optional CCXT adapter) - previously hardcoded to exactly two, which
        left the config-declared ccxt feed silently unwired.

        `now` (engine time, threaded from slow_cycle) drives the OFI
        event clock so replay/sim stay deterministic; omitted (legacy
        callers/offline tools) it falls back to wall-clock.
        """
        if now is None:
            now = time.time()
        merged = {}
        for src_idx, source_data in enumerate(sources):
            self._ingest(merged, source_data or {}, src_idx)

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
                "imbalance_ratio": self._combined_imbalance(
                    entry["order_books"],
                    decay_bps=self.imbalance_decay_bps),
                # v9 SHADOW: event OFI beside the snapshot imbalance -
                # the standing book vs its CHANGES. Feeds ONLY the ml
                # feature vector (ofi_dir); the shadow-purity grep test
                # proves no decision path reads it.
                "ofi_event": self._ofi_update(
                    base, entry["order_books"],
                    entry.get("book_srcs") or [], now),
                # per-venue external books (OKX/Binance.US; Kraken is added
                # separately by the engine). The manip divergence term needs a
                # COHERENT cross-venue imbalance to compare against Kraken -
                # computed per book so its scale matches, never on the merged
                # book whose mixed size units make any cross-book ratio garbage.
                "venue_books": list(entry["order_books"]),
                "candles": entry["candles"],
                "funding_rate": avg_funding,
                # distinguish "genuinely ~0 funding" from "no funding source
                # this cycle" (OKX perp feed down) — avg_funding is 0.0 for
                # BOTH, so consumers that must not silently treat unknown as
                # zero (the funding veto) read this flag instead.
                "funding_available": bool(entry["funding_rates"]),
                "volume_24h": entry["volume_24h_total"],
            }
        return view
