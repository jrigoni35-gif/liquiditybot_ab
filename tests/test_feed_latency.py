"""Feed-latency EWMA on the shared REST transport.

The dashboard's latency metric read order_manager.latency_ms, an EWMA of
PRIVATE Kraken POSTs - which dry-run never makes, so it showed a dead 0ms
forever. The transport now keeps its own EWMA of completed public-GET
wire RTT (throttle wait excluded); runner publishes it as
feed_latency_ms and the dashboard falls back to it when order latency
is absent.
"""
import types

import requests

from data._http import ThrottledRestClient


class _FakeResponse:
    text = "{}"

    @staticmethod
    def raise_for_status():
        pass

    @staticmethod
    def json():
        return {}


def _client(get=None):
    c = ThrottledRestClient(rate_limit_per_sec=1000)   # negligible throttle
    setattr(c, "session", types.SimpleNamespace(
        get=get or (lambda *a, **k: _FakeResponse())))
    return c


def test_latency_starts_zero_and_updates_on_success():
    import logging
    c = _client()
    assert c.latency_ms == 0.0
    assert c._get_json("http://x", None, logging.getLogger("t"), "T") == {}
    assert c.latency_ms > 0.0


def test_latency_ewma_blends():
    c = _client()
    c.latency_ms = 100.0
    c._note_rtt(__import__("time").time() - 0.2)       # ~200ms sample
    assert 100.0 < c.latency_ms < 200.0                # 0.7*100 + 0.3*~200


def test_failed_request_does_not_pollute_latency():
    import logging

    def _boom(*a, **k):
        raise requests.ConnectionError("down")

    c = _client(get=_boom)
    c.latency_ms = 50.0
    assert c._get_raw("http://x", None, logging.getLogger("t"), "T") is None
    assert c.latency_ms == 50.0
