"""
data/_http.py — shared REST plumbing for the market-data feeds.

One place for the requests.Session, the per-instance rate-limit
throttle, and the GET→raise_for_status→JSON skeleton that the Kraken,
OKX and Binance.US clients previously each carried a private copy of.
Venue-specific error envelopes stay in the venue modules (each API
signals failure differently); everything transport-shaped lives here.

This class is transport only: it never signs, never POSTs, and holds no
credentials — signed private calls remain exclusively in
data/kraken_feed.py next to the withdrawal deny-list.
"""

import logging
import math
import socket
import threading
import time
from typing import Any, Optional

import requests
from requests.adapters import HTTPAdapter

_MAX_BODY_BYTES = 16 * 1024 * 1024   # feeds return KBs; 16MB = something is wrong


def _keepalive_socket_options() -> list:
    """Latency + connection-warmth socket options for a long-lived polling
    client. TCP_NODELAY disables Nagle so a small request/response isn't held
    for a delayed-ACK (a classic tens-of-ms tax on tiny GETs). SO_KEEPALIVE +
    tuned idle probes keep the TCP connection from being silently reaped during
    the seconds-long idle between polls, so the next poll reuses the warm
    connection (one RTT) instead of paying a fresh TCP+TLS handshake (2-3 RTT).
    Every option is feature-detected: Windows (the target runtime) has
    TCP_NODELAY + SO_KEEPALIVE but not TCP_KEEPIDLE/INTVL/CNT, which are simply
    skipped."""
    opts = [(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1),
            (socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)]
    for name, value in (("TCP_KEEPIDLE", 15), ("TCP_KEEPINTVL", 15),
                        ("TCP_KEEPCNT", 4)):
        opt = getattr(socket, name, None)
        if opt is not None:
            opts.append((socket.IPPROTO_TCP, opt, value))
    return opts


class _KeepAliveAdapter(HTTPAdapter):
    """HTTPAdapter that stamps every pooled connection with the keep-alive /
    no-delay socket options above. Retries are handled by the caller's own
    bounded transport-retry loop, so the adapter never re-tries on its own."""

    def init_poolmanager(self, *args, **kwargs):
        kwargs["socket_options"] = _keepalive_socket_options()
        super().init_poolmanager(*args, **kwargs)


class ThrottledRestClient:
    """requests.Session + min-interval throttle + JSON GET helper."""

    def __init__(self, rate_limit_per_sec: float = 1,
                 transport_retries: int = 1):
        self.rate_limit_per_sec = rate_limit_per_sec
        # bounded in-place retry for INSTANT transport drops (proxy flap:
        # ProxyError/RemoteDisconnected). Never retries timeouts (each
        # would stall a full extra timeout inside the cycle) or HTTP
        # errors (4xx/5xx do not heal by hammering). Keeps every cycle's
        # loads complete through a flaky egress instead of serving the
        # engine a one-cycle-stale book.
        self.transport_retries = max(int(transport_retries), 0)
        self.retries_recovered = 0
        self._min_interval = 1.0 / max(rate_limit_per_sec, 1)
        self._last_call = 0.0
        # EWMA of COMPLETED-request wire RTT (throttle wait excluded, so a
        # rate-limit queue can't masquerade as network latency). In dry-run
        # this is the only real latency signal: order latency_ms measures
        # private POSTs that paper mode never makes.
        self.latency_ms: float = 0.0
        self.session = requests.Session()
        # keep-alive + no-delay on a warm pooled connection: the biggest
        # code-side lever on per-poll REST latency (avoids a fresh TLS
        # handshake every idle cycle). pool sized for the shared client's
        # concurrent callers (market-data loop + order path + ws REST fallback
        # thread). Our own transport-retry loop owns retries -> adapter does 0.
        _adapter = _KeepAliveAdapter(pool_connections=4, pool_maxsize=8,
                                     max_retries=0)
        self.session.mount("https://", _adapter)
        self.session.mount("http://", _adapter)
        # The Kraken client is SHARED between the market-data cycle and the
        # order path, and a websocket REST-fallback can call it off the main
        # thread. Without this lock, concurrent callers each read a stale
        # _last_call, all pass the interval check, and fire together - a
        # burst that blows the venue rate limit (a ban risk on the execution
        # venue). The lock spaces every caller by min_interval, globally.
        self._throttle_lock = threading.Lock()

    def _note_rtt(self, t0: float):
        # monotonic delta: a wall-clock step (NTP correction) mid-request could
        # otherwise inject a negative or huge RTT and poison the EWMA. Test the
        # RAW sample for finiteness BEFORE clamping (max(0.0, nan) would swallow
        # a NaN into a spurious 0.0), then floor a backward step at 0.
        raw = (time.monotonic() - t0) * 1000.0
        if not math.isfinite(raw):
            return                                 # bad sample: ignore entirely
        rtt = max(0.0, raw)
        self.latency_ms = 0.7 * self.latency_ms + 0.3 * rtt \
            if self.latency_ms else rtt

    def _throttle(self):
        # Held across the sleep on purpose: waiting threads queue here, which
        # IS the rate limiter serializing them. The network GET runs AFTER
        # this returns (lock released), so requests still overlap on the wire.
        # monotonic clock so a backward wall-clock step can't compute a
        # negative elapsed and either burst past the rate limit or sleep for a
        # very long time.
        with self._throttle_lock:
            now = time.monotonic()
            elapsed = now - self._last_call
            if 0.0 <= elapsed < self._min_interval:
                time.sleep(self._min_interval - elapsed)
            self._last_call = time.monotonic()

    @staticmethod
    def _retryable(e: Exception) -> bool:
        """Instant connection-layer drops only: ProxyError and friends are
        ConnectionError subclasses; ConnectTimeout is BOTH ConnectionError
        and Timeout and is excluded (a retry would stall another full
        timeout inside the cycle)."""
        return isinstance(e, requests.exceptions.ConnectionError) and \
            not isinstance(e, requests.exceptions.Timeout)

    def _request(self, url, params, log, venue, timeout, decode_json) -> Any:
        last_err: Optional[Exception] = None
        for attempt in range(self.transport_retries + 1):
            self._throttle()               # every attempt is rate-limited
            t0 = time.monotonic()
            try:
                resp = self.session.get(url, params=params, timeout=timeout)
                resp.raise_for_status()
                # DL-7: bound the decoded body - a mis-routed/proxied
                # response (HTML error page, runaway payload) must not
                # balloon memory or stall the feed thread mid-decode
                _hdrs = getattr(resp, "headers", None) or {}
                # DL-7 (hardened 2026-08-20): the content-length HEADER guard
                # is bypassable by a server that omits the header (chunked
                # transfer, or a hostile/mis-routed origin), so ALSO bound the
                # actual decoded byte length - a response with no length
                # header no longer skips the cap. (The body is already
                # resident here under stream=False; a true streaming cap is
                # the deeper v2, tracked - this closes the header-absent
                # bypass the security sweep flagged.)
                _clen = int(_hdrs.get("content-length") or 0)
                _blen = len(getattr(resp, "content", b"") or b"")
                if decode_json and max(_clen, _blen) > _MAX_BODY_BYTES:
                    log.warning("%s: response body %s bytes > cap - "
                                "discarded", venue, max(_clen, _blen))
                    return None
                out = resp.json() if decode_json else resp
                self._note_rtt(t0)
                if attempt:
                    self.retries_recovered += 1
                    log.info(f"{venue} transport retry recovered "
                             f"{url.split('?')[0]} (attempt {attempt + 1}, "
                             f"{self.retries_recovered} total recoveries)")
                return out
            except requests.RequestException as e:
                last_err = e
                if self._retryable(e) and attempt < self.transport_retries:
                    log.debug(f"{venue} transport drop, retrying: {e}")
                    continue
                break                      # timeout/HTTP/decode: no hammer
        log.error(f"{venue} request failed for {url}: {last_err}")
        return None

    def _get_raw(self, url: str, params: Optional[dict],
                 log: logging.Logger, venue: str, timeout: float = 10):
        """Throttled GET returning the Response, or None on transport
        failure. Callers decode/validate the venue's own envelope."""
        return self._request(url, params, log, venue, timeout,
                             decode_json=False)

    def _get_json(self, url: str, params: Optional[dict],
                  log: logging.Logger, venue: str,
                  timeout: float = 10) -> Optional[Any]:
        """Throttled GET returning decoded JSON, or None on any
        transport/decode failure (requests>=2.27 JSONDecodeError is a
        RequestException, so one except covers both)."""
        return self._request(url, params, log, venue, timeout,
                             decode_json=True)
