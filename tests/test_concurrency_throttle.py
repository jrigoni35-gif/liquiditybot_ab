"""Load / concurrency (GIL) hardening for the SHARED REST transport.

The Kraken ThrottledRestClient is shared across three threads - the engine's
market-data cycle, the order path, and the websocket REST-fallback - all
running under one GIL. The real concurrency bottleneck/hazard here is NOT CPU
throughput; it is that concurrent callers must be SERIALIZED by the rate-limit
throttle, or they burst together and blow Kraken's rate limit (a ban risk on
the sole execution venue). These tests prove, under genuine thread contention,
that:

  * the throttle lock spaces every caller by >= min_interval (no burst),
  * no caller is starved or deadlocked (all complete),
  * the latency EWMA stays finite (no torn read poisons it to NaN/inf).

Fast by construction: a high rate limit keeps the whole suite well under 1s.
"""
import threading
import time

import pytest

from data._http import ThrottledRestClient

# timing (whole module): every test here measures wall-clock behavior of
# REAL contending threads. The burst test is the canonical load-marginal
# case: a worker can be descheduled between the throttle releasing and
# the stamp being taken, so a saturated -n 8 battery compresses measured
# gaps below min_interval with no code defect (observed red 2026-08-08,
# 4/4 green solo in 7.7s on the same tree) - serial pass only.
pytestmark = pytest.mark.timing


class _RecordingResponse:
    text = "{}"

    @staticmethod
    def raise_for_status():
        pass

    @staticmethod
    def json():
        return {}


def _client(rate):
    c = ThrottledRestClient(rate_limit_per_sec=rate)
    stamps = []
    lock = threading.Lock()

    def _get(*_a, **_k):
        # timestamp the instant the GET fires (throttle has released the
        # lock), exactly the moment a real request would hit the wire
        with lock:
            stamps.append(time.monotonic())
        return _RecordingResponse()

    c.session.get = _get                     # type: ignore[assignment]
    return c, stamps


def _hammer(client, n_threads, calls_each):
    import logging
    log = logging.getLogger("t")
    barrier = threading.Barrier(n_threads)
    errors = []

    def worker():
        try:
            barrier.wait()                   # maximize real contention
            for _ in range(calls_each):
                client._get_json("http://x", None, log, "T")
        except Exception as e:               # pragma: no cover
            errors.append(e)

    threads = [threading.Thread(target=worker) for _ in range(n_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)
    assert not any(t.is_alive() for t in threads), "throttle deadlock/starvation"
    assert not errors, f"worker errors: {errors}"


def test_concurrent_callers_never_burst_past_rate_limit():
    rate = 100.0                                     # min_interval = 10ms
    min_interval = 1.0 / rate
    client, stamps = _client(rate)
    _hammer(client, n_threads=6, calls_each=2)       # 12 serialized GETs
    assert len(stamps) == 12
    stamps.sort()
    gaps = [b - a for a, b in zip(stamps, stamps[1:])]
    # every consecutive pair spaced by ~min_interval (sleep can wake late,
    # never early, so gaps are >= min_interval modulo tiny measurement slack)
    assert min(gaps) >= min_interval * 0.9, \
        f"burst: min gap {min(gaps)*1000:.2f}ms < {min_interval*1000:.0f}ms"
    # total span proves serialization, not parallel firing
    assert stamps[-1] - stamps[0] >= (len(stamps) - 1) * min_interval * 0.9


def test_no_deadlock_under_heavy_contention():
    client, stamps = _client(rate=500.0)             # 2ms spacing, quick
    _hammer(client, n_threads=8, calls_each=5)       # 40 GETs
    assert len(stamps) == 40


def test_latency_ewma_stays_finite_under_concurrency():
    import math
    client, _ = _client(rate=500.0)
    _hammer(client, n_threads=8, calls_each=5)
    assert math.isfinite(client.latency_ms) and client.latency_ms >= 0.0


def test_throttle_lock_is_actually_held_across_the_wait():
    # single thread: two back-to-back calls must be spaced by >= min_interval,
    # proving the interval is enforced in-process (not just across threads)
    rate = 50.0
    client, stamps = _client(rate)
    import logging
    client._get_json("http://x", None, logging.getLogger("t"), "T")
    client._get_json("http://x", None, logging.getLogger("t"), "T")
    assert stamps[1] - stamps[0] >= (1.0 / rate) * 0.9
