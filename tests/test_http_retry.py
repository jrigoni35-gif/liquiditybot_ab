"""
Regression for bounded transport retries in the shared REST client:
the container's egress proxy drops individual requests (ProxyError /
RemoteDisconnected, ~5/hour observed live), and a single-attempt GET
turned each flap into a lost load - that cycle's book/candles went
one cycle stale, feeding imprecise cross-venue comparisons. Instant
connection drops now retry once in place; timeouts and HTTP errors
never do (a timeout retry stalls another full timeout inside the
cycle; 4xx/5xx don't heal by hammering).
"""
import logging

import requests

from data._http import ThrottledRestClient

log = logging.getLogger("test")


class _FlakySession:
    def __init__(self, failures, exc):
        self.calls = 0
        self._failures = failures
        self._exc = exc

    def get(self, url, params=None, timeout=10):
        self.calls += 1
        if self.calls <= self._failures:
            raise self._exc

        class R:
            # the real requests.Response surface the client reads: decode
            # goes through loads_bounded(resp.text) since the 2026-08-19
            # sanitize-boundary fix (resp.json() is no longer called)
            text = '{"ok": true}'
            content = b'{"ok": true}'
            headers = {"content-length": "12"}

            def raise_for_status(self):
                pass
        return R()


def _client(session):
    c = ThrottledRestClient(rate_limit_per_sec=1000, transport_retries=1)
    c.session = session
    return c


def test_proxy_drop_recovers_on_immediate_retry():
    s = _FlakySession(1, requests.exceptions.ProxyError("remote closed"))
    c = _client(s)
    out = c._get_json("https://x/api", None, log, "test")
    assert out == {"ok": True}
    assert s.calls == 2
    assert c.retries_recovered == 1


def test_persistent_drop_fails_after_bounded_attempts():
    s = _FlakySession(99, requests.exceptions.ProxyError("dead"))
    c = _client(s)
    assert c._get_json("https://x/api", None, log, "test") is None
    assert s.calls == 2                       # 1 retry, never a hammer


def test_timeouts_and_http_errors_are_never_retried():
    for exc in (requests.exceptions.ConnectTimeout("slow"),
                requests.exceptions.ReadTimeout("slow"),
                requests.exceptions.HTTPError("500")):
        s = _FlakySession(99, exc)
        c = _client(s)
        assert c._get_json("https://x/api", None, log, "test") is None
        assert s.calls == 1, f"{type(exc).__name__} must not retry"
