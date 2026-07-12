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
import threading
import time
from typing import Optional

import requests


class ThrottledRestClient:
    """requests.Session + min-interval throttle + JSON GET helper."""

    def __init__(self, rate_limit_per_sec: float = 1):
        self.rate_limit_per_sec = rate_limit_per_sec
        self._min_interval = 1.0 / max(rate_limit_per_sec, 1)
        self._last_call = 0.0
        self.session = requests.Session()
        # The Kraken client is SHARED between the market-data cycle and the
        # order path, and a websocket REST-fallback can call it off the main
        # thread. Without this lock, concurrent callers each read a stale
        # _last_call, all pass the interval check, and fire together - a
        # burst that blows the venue rate limit (a ban risk on the execution
        # venue). The lock spaces every caller by min_interval, globally.
        self._throttle_lock = threading.Lock()

    def _throttle(self):
        # Held across the sleep on purpose: waiting threads queue here, which
        # IS the rate limiter serializing them. The network GET runs AFTER
        # this returns (lock released), so requests still overlap on the wire.
        with self._throttle_lock:
            elapsed = time.time() - self._last_call
            if elapsed < self._min_interval:
                time.sleep(self._min_interval - elapsed)
            self._last_call = time.time()

    def _get_raw(self, url: str, params: Optional[dict],
                 log: logging.Logger, venue: str, timeout: float = 10):
        """Throttled GET returning the Response, or None on transport
        failure. Callers decode/validate the venue's own envelope."""
        self._throttle()
        try:
            resp = self.session.get(url, params=params, timeout=timeout)
            resp.raise_for_status()
            return resp
        except requests.RequestException as e:
            log.error(f"{venue} request failed for {url}: {e}")
            return None

    def _get_json(self, url: str, params: Optional[dict],
                  log: logging.Logger, venue: str, timeout: float = 10):
        """Throttled GET returning decoded JSON, or None on any
        transport/decode failure (requests>=2.27 JSONDecodeError is a
        RequestException, so one except covers both)."""
        self._throttle()
        try:
            resp = self.session.get(url, params=params, timeout=timeout)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            log.error(f"{venue} request failed for {url}: {e}")
            return None
