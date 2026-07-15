"""
data/ws_feed.py — push-based market data over websockets.

The REST feeds (data/_http.ThrottledRestClient subclasses) pull a fresh
order book every slow cycle (~5s), during which stops run on data that
is up to a cycle old. This module streams venue order-book snapshots
into a thread-safe in-memory cache; the existing synchronous
`get_order_book(symbol)` accessors read from that cache when it is
FRESH and fall back to REST when the socket is stale, absent, or the
`websockets` package is not installed. Net effect: sub-second book
freshness with the REST path as an always-available safety net.

Design contract (matches the rest of the data layer):
  * FAIL-SAFE. A dropped connection, a garbage frame, or a missing
    optional dependency degrades to "no cached book" -> REST fallback.
    Nothing here ever raises into the engine.
  * STALENESS-GATED. A cached book older than `max_age_s` is treated as
    absent, so a silently-dead socket can never feed stale depth to the
    firewall or stop logic (same discipline as the venue watchdog).
  * OPTIONAL. `websockets` is not in requirements.txt floors; if it is
    absent the manager still constructs, `.start()` is a no-op, and the
    bot runs exactly as it does today on REST.
  * READ-ONLY. Public market-data streams only. No auth, no order
    entry, no venue on which this could place risk. Kraken execution
    stays exclusively on the hardened REST order path.

The websocket transport runs its own asyncio loop on a daemon thread;
the engine never awaits. Cache reads are plain locked dict lookups.
"""

import json
import logging
import threading
import time
from typing import Callable, Optional

from core.sanitize import clean_book

log = logging.getLogger("liquiditybot.data.ws")

# Binance.US partial-depth snapshot stream: each frame is a COMPLETE
# top-N book, so no local diff-merge / sequence-resync bookkeeping (the
# classic source of order-book desync bugs). 100ms cadence.
_BINANCEUS_WS_BASE = "wss://stream.binance.us:9443/stream"

# Kraken v2 public book channel: one snapshot per (re)subscribe then
# incremental updates. Unlike Binance's full-frame stream this needs local
# book maintenance (see KrakenV2BookStream), but a reconnect re-subscribes
# and Kraken resends a snapshot that RESETS state, so drift self-heals.
_KRAKEN_WS_V2 = "wss://ws.kraken.com/v2"


class LiveMarketCache:
    """Thread-safe latest-snapshot store, keyed by (venue, symbol).

    Writers are websocket handler threads; readers are the engine's slow
    cycle. Every read is staleness-gated and re-sanitized through
    clean_book, so a consumer of this cache gets exactly the same shape
    and guarantees as a fresh REST `get_order_book`."""

    def __init__(self, now: Callable[[], float] = time.time):
        self._now = now
        self._lock = threading.Lock()
        self._books: dict = {}      # (venue, symbol) -> (bids, asks, ts)
        self._marks: dict = {}      # (venue, symbol) -> (price, ts)

    def update_book(self, venue: str, symbol: str, bids: list, asks: list):
        ts = self._now()
        with self._lock:
            self._books[(venue, symbol)] = (bids, asks, ts)
            # keep a mark in lockstep with the book: mid of best levels
            try:
                mid = (float(bids[0][0]) + float(asks[0][0])) / 2.0
                if mid > 0:
                    self._marks[(venue, symbol)] = (mid, ts)
            except (IndexError, TypeError, ValueError):
                pass

    def update_trade(self, venue: str, symbol: str, price: float):
        ts = self._now()
        try:
            px = float(price)
        except (TypeError, ValueError):
            return
        if px <= 0:
            return
        with self._lock:
            self._marks[(venue, symbol)] = (px, ts)

    def get_book(self, venue: str, symbol: str,
                 max_age_s: float) -> Optional[dict]:
        with self._lock:
            entry = self._books.get((venue, symbol))
        if entry is None:
            return None
        bids, asks, ts = entry
        if self._now() - ts > max_age_s:
            return None                      # stale -> caller falls back
        return clean_book({"bids": bids, "asks": asks})

    def get_mark(self, venue: str, symbol: str,
                 max_age_s: float) -> Optional[float]:
        with self._lock:
            entry = self._marks.get((venue, symbol))
        if entry is None:
            return None
        px, ts = entry
        if self._now() - ts > max_age_s:
            return None
        return px

    def age(self, venue: str, symbol: str) -> Optional[float]:
        with self._lock:
            entry = self._books.get((venue, symbol))
        return None if entry is None else self._now() - entry[2]

    def stats(self) -> dict:
        with self._lock:
            return {"books": len(self._books), "marks": len(self._marks)}


def _backoff_delay(attempt: int, base: float, cap: float,
                   jitter: float) -> float:
    """Exponential backoff with a hard cap and additive jitter. Pure and
    deterministic under an injected jitter value, so the reconnect
    schedule is unit-testable without sleeping or opening a socket."""
    raw = base * (2 ** max(attempt, 0))
    return min(raw, cap) + max(jitter, 0.0)


class ResilientWebSocket:
    """Generic reconnecting websocket reader on a daemon asyncio thread.

    Owns nothing venue-specific: it connects to `url`, optionally sends
    `subscribe`, and hands every text frame to `on_message`. Reconnects
    with capped exponential backoff forever until `stop()`. The
    `websockets` dependency is imported lazily so the whole module is
    importable (and testable) without it installed."""

    def __init__(self, url: str, on_message: Callable[[str], None],
                 subscribe: Optional[str] = None,
                 backoff_base: float = 1.0, backoff_cap: float = 30.0,
                 ping_interval: float = 20.0,
                 rng: Optional[Callable[[], float]] = None):
        self.url = url
        self.on_message = on_message
        self.subscribe = subscribe
        self.backoff_base = backoff_base
        self.backoff_cap = backoff_cap
        self.ping_interval = ping_interval
        import random
        # jitter only decorrelates reconnect storms across clients; it
        # guards no secret, so the non-crypto PRNG is the right tool
        self._rng = rng or (lambda: random.uniform(0.0, 1.0))  # nosec B311
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self.connected = False
        self.reconnects = 0

    @staticmethod
    def available() -> bool:
        try:
            import websockets  # noqa: F401
            return True
        except Exception:
            return False

    def start(self):
        if not self.available():
            log.warning("websockets package absent - live stream disabled, "
                        "REST fallback remains in effect")
            return
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run_loop, name="ws-feed", daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 5.0):
        self._stop.set()
        t = self._thread
        if t and t.is_alive():
            t.join(timeout=timeout)
        self.connected = False

    def _run_loop(self):
        import asyncio
        try:
            asyncio.run(self._reader())
        except Exception:
            log.debug("ws reader loop exited", exc_info=True)
        finally:
            self.connected = False

    async def _reader(self):
        import asyncio

        import websockets
        attempt = 0
        while not self._stop.is_set():
            try:
                async with websockets.connect(
                        self.url, ping_interval=self.ping_interval,
                        ping_timeout=self.ping_interval,
                        open_timeout=10, close_timeout=5) as ws:
                    self.connected = True
                    attempt = 0                 # clean connect resets backoff
                    if self.subscribe:
                        await ws.send(self.subscribe)
                    async for raw in ws:
                        if self._stop.is_set():
                            break
                        try:
                            self.on_message(
                                raw if isinstance(raw, str)
                                else raw.decode("utf-8", "replace"))
                        except Exception:
                            log.debug("ws frame handler error - skipped",
                                      exc_info=True)
            except Exception as e:
                self.connected = False
                if self._stop.is_set():
                    break
                self.reconnects += 1
                delay = _backoff_delay(attempt, self.backoff_base,
                                       self.backoff_cap, self._rng())
                attempt += 1
                log.warning("ws disconnect (%s); reconnecting in %.1fs "
                            "(attempt %d)", e, delay, attempt)
                try:
                    await asyncio.wait_for(
                        _stoppable_sleep(self._stop, delay), timeout=delay + 1)
                except Exception:
                    log.debug("ws backoff sleep interrupted", exc_info=True)


async def _stoppable_sleep(stop_event: threading.Event, delay: float):
    """Sleep that wakes early if stop is signalled, so shutdown is prompt
    even mid-backoff."""
    import asyncio
    step = 0.1
    waited = 0.0
    while waited < delay and not stop_event.is_set():
        await asyncio.sleep(step)
        waited += step


class BinanceUSDepthStream:
    """Venue adapter: builds the Binance.US combined partial-depth stream
    URL for a symbol set and parses its frames into a LiveMarketCache.

    Symbols arrive in the feed's format (e.g. 'BTCUSD'); Binance stream
    paths are lowercase concatenated ('btcusd'). The reverse map restores
    the caller's exact symbol string on the cache key so a cache read
    lines up with the matching REST `get_order_book(symbol)`."""

    VENUE = "binanceus"

    def __init__(self, symbols: list, cache: LiveMarketCache,
                 depth: int = 20, interval_ms: int = 100):
        self.cache = cache
        self._symbols = list(symbols)
        self._to_venue = {s: s.lower() for s in self._symbols}
        self._from_venue = {v: s for s, v in self._to_venue.items()}
        self.depth = depth
        self.interval_ms = interval_ms

    def stream_url(self) -> str:
        parts = [f"{v}@depth{self.depth}@{self.interval_ms}ms"
                 for v in self._to_venue.values()]
        return f"{_BINANCEUS_WS_BASE}?streams={'/'.join(parts)}"

    # uniform adapter interface (see WebSocketFeedManager): Binance encodes
    # its subscription in the URL, so there is no post-connect subscribe frame
    def url(self) -> str:
        return self.stream_url()

    def subscribe_msg(self) -> Optional[str]:
        return None

    def handle(self, text: str):
        """Parse one combined-stream frame into a book update. Never
        raises: a malformed frame is dropped, the cache keeps its last
        good snapshot until staleness expires it."""
        try:
            msg = json.loads(text)
        except (ValueError, TypeError):
            return
        stream = msg.get("stream", "") if isinstance(msg, dict) else ""
        data = msg.get("data") if isinstance(msg, dict) else None
        if not isinstance(data, dict):
            return
        venue_sym = stream.split("@", 1)[0]
        symbol = self._from_venue.get(venue_sym)
        if symbol is None:
            return
        bids = data.get("bids") or data.get("b") or []
        asks = data.get("asks") or data.get("a") or []
        if not bids or not asks:
            return
        self.cache.update_book(self.VENUE, symbol, bids, asks)


class KrakenV2BookStream:
    """Venue adapter: Kraken v2 public `book` channel -> LiveMarketCache.

    Kraken streams an INCREMENTAL book: one `snapshot` frame per
    (re)subscribe carrying the full top-N, then `update` frames carrying
    only changed levels (qty>0 sets/replaces a level, qty==0 removes it).
    We keep the book per symbol and republish the top-N levels keyed by the
    caller's Kraken REST *pair* (e.g. 'BTCUSD'), so a cache read lines up
    with get_order_book(pair) exactly like the Binance adapter's symbol key.

    Correctness without checksums: within one connection websocket delivery
    is ordered and lossless, so applying every update in order reproduces
    Kraken's book. A dropped connection makes ResilientWebSocket re-send the
    subscribe; Kraken answers with a fresh snapshot, and `snapshot` RESETS
    local state - so a reconnect can never leave a drifted book. Reads are
    still staleness-gated and clean_book-sanitised, so a crossed/degenerate
    book degrades to None -> REST, same as every other cache read.

    READ-ONLY public market data. Kraken execution stays exclusively on the
    hardened REST order path (invariant 3)."""

    VENUE = "kraken"

    def __init__(self, sym_to_pair: dict, cache: LiveMarketCache,
                 depth: int = 10):
        self.cache = cache
        # v2 symbol ('BTC/USD') -> cache key = Kraken REST pair ('BTCUSD')
        self.sym_to_pair = dict(sym_to_pair or {})
        self._symbols = list(self.sym_to_pair.keys())
        self.depth = max(int(depth), 1)
        # v2 symbol -> {'bids': {price: qty}, 'asks': {price: qty}}
        self._state: dict = {}

    def url(self) -> str:
        return _KRAKEN_WS_V2

    def subscribe_msg(self) -> Optional[str]:
        if not self._symbols:
            return None
        return json.dumps({"method": "subscribe", "params": {
            "channel": "book", "symbol": self._symbols, "depth": self.depth}})

    def _trim(self, st: dict) -> None:
        """Bound each side to the top-`depth` levels (bids highest, asks
        lowest). A depth-N channel need not send a qty=0 remove for a level
        merely PUSHED OUT of the window by a better price, so without this
        the state would grow unbounded AND a stale out-of-window level could
        later resurface as a phantom best bid/ask. Trimming to depth after
        every frame makes local state == Kraken's canonical top-N book."""
        for side, best_first in (("bids", True), ("asks", False)):
            book = st[side]
            if len(book) > self.depth:
                keep = sorted(book, reverse=best_first)[:self.depth]
                st[side] = {p: book[p] for p in keep}

    def _publish(self, sym: str):
        st = self._state.get(sym)
        pair = self.sym_to_pair.get(sym)
        if not st or pair is None:
            return
        # top-N: bids highest-first, asks lowest-first (matches REST shape)
        bids = sorted(st["bids"].items(), reverse=True)[:self.depth]
        asks = sorted(st["asks"].items())[:self.depth]
        if not bids or not asks:
            return
        self.cache.update_book(self.VENUE, pair,
                               [[p, q] for p, q in bids],
                               [[p, q] for p, q in asks])

    def handle(self, text: str):
        """Apply one book frame. Never raises: a malformed frame is dropped
        and the cache keeps its last good snapshot until staleness expires."""
        try:
            msg = json.loads(text)
        except (ValueError, TypeError):
            return
        if not isinstance(msg, dict) or msg.get("channel") != "book":
            return
        typ = msg.get("type")
        data = msg.get("data")
        if not isinstance(data, list):
            return
        for d in data:
            if not isinstance(d, dict):
                continue
            sym = d.get("symbol")
            if sym not in self.sym_to_pair:
                continue
            st = self._state.setdefault(sym, {"bids": {}, "asks": {}})
            if typ == "snapshot":                 # (re)subscribe: hard reset
                st["bids"].clear()
                st["asks"].clear()
            for side in ("bids", "asks"):
                book_side = st[side]
                for lvl in d.get(side) or []:
                    try:
                        # price is the dict key: Kraken echoes each level's
                        # price string identically between set and its later
                        # qty=0 delete, so the float round-trip matches for
                        # pop(); staleness + reconnect-snapshot bound any drift
                        px = float(lvl["price"])
                        qty = float(lvl["qty"])
                    except (KeyError, TypeError, ValueError):
                        continue
                    if qty <= 0.0:
                        book_side.pop(px, None)   # qty 0 removes the level
                    else:
                        book_side[px] = qty
            self._trim(st)                        # bound to top-N (no phantoms)
            self._publish(sym)


class WebSocketFeedManager:
    """Owns one venue's live stream: cache + adapter + resilient socket,
    plus REST-fallback accessors the engine can call synchronously.

    Venue-agnostic: it drives any adapter exposing url() / subscribe_msg() /
    handle() / VENUE. Ships adapters for Binance.US (URL-encoded depth
    stream) and Kraken v2 (post-connect book subscribe). Pass `adapter` to
    select one; the default builds Binance.US from config for back-compat."""

    def __init__(self, config: dict, cache: Optional[LiveMarketCache] = None,
                 adapter=None):
        cfg = config or {}
        self.enabled = bool(cfg.get("enabled", False))
        self.max_age_s = float(cfg.get("max_book_age_sec", 2.0))
        self.cache = cache or LiveMarketCache()
        if adapter is not None:
            self.adapter = adapter
            self._symbols = list(getattr(adapter, "_symbols", []) or [])
        else:
            symbols = cfg.get("binanceus_symbols") or []
            self.adapter = BinanceUSDepthStream(
                symbols, self.cache,
                depth=int(cfg.get("depth", 20)),
                interval_ms=int(cfg.get("interval_ms", 100)))
            self._symbols = list(symbols)
        self.venue = self.adapter.VENUE
        self._ws: Optional[ResilientWebSocket] = None

    def start(self):
        if not self.enabled:
            return
        if not self._symbols:
            log.warning("ws manager enabled but no symbols configured - "
                        "staying on REST")
            return
        self._ws = ResilientWebSocket(self.adapter.url(),
                                      self.adapter.handle,
                                      subscribe=self.adapter.subscribe_msg(),
                                      backoff_cap=float(
                                          self.max_age_s * 15))
        self._ws.start()
        log.info("ws feed started: %s %s", self.venue, self._symbols)

    def stop(self):
        if self._ws is not None:
            self._ws.stop()
            self._ws = None

    def get_order_book(self, symbol: str) -> Optional[dict]:
        """Fresh cached book or None (caller falls back to REST). Disabled
        or stale both return None, so the engine's existing REST path is
        the single source of truth whenever live data is not trustworthy.
        `symbol` is whatever key the adapter caches under (Binance symbol /
        Kraken REST pair)."""
        if not self.enabled:
            return None
        return self.cache.get_book(self.venue, symbol, self.max_age_s)

    def get_mark(self, symbol: str) -> Optional[float]:
        if not self.enabled:
            return None
        return self.cache.get_mark(self.venue, symbol, self.max_age_s)

    def health(self) -> dict:
        return {
            "enabled": self.enabled,
            "connected": bool(self._ws and self._ws.connected),
            "reconnects": self._ws.reconnects if self._ws else 0,
            "lib_available": ResilientWebSocket.available(),
            **self.cache.stats(),
        }
