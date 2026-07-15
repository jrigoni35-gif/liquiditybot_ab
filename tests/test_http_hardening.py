"""tests/test_http_hardening.py — throttle + latency framework hardening.

Two failure modes this pins:
  * per-poll REST latency paying a fresh TLS handshake every idle cycle — the
    shared session now mounts a keep-alive / TCP_NODELAY adapter so the warm
    pooled connection is reused (one RTT, not two-to-three).
  * a wall-clock step (NTP correction) poisoning the rate-limit spacing or the
    latency EWMA — both now read the MONOTONIC clock and clamp the RTT sample,
    so a backward jump can neither burst past the venue rate limit nor drive
    latency_ms negative.
"""
import socket
import time

from data._http import (ThrottledRestClient, _KeepAliveAdapter,
                        _keepalive_socket_options)


def test_keepalive_adapter_is_mounted_for_both_schemes():
    c = ThrottledRestClient(rate_limit_per_sec=5)
    assert isinstance(c.session.get_adapter("https://api.kraken.com"),
                      _KeepAliveAdapter)
    assert isinstance(c.session.get_adapter("http://x"), _KeepAliveAdapter)


def test_socket_options_disable_nagle_and_enable_keepalive():
    opts = _keepalive_socket_options()
    assert (socket.IPPROTO_TCP, socket.TCP_NODELAY, 1) in opts
    assert (socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1) in opts


def test_note_rtt_clamps_a_backward_clock_step():
    c = ThrottledRestClient(rate_limit_per_sec=5)
    c.latency_ms = 100.0
    c._note_rtt(time.monotonic() + 100.0)     # t0 "in the future" -> rtt < 0
    assert c.latency_ms >= 0.0                 # clamp: never driven negative
    assert c.latency_ms == 70.0                # EWMA with a clamped-0 sample


def test_note_rtt_ignores_nonfinite_sample():
    c = ThrottledRestClient(rate_limit_per_sec=5)
    c.latency_ms = 42.0
    c._note_rtt(float("nan"))                   # monotonic()-nan -> nan -> skip
    assert c.latency_ms == 42.0                 # unchanged, not corrupted


def test_throttle_spaces_successive_calls_by_min_interval():
    c = ThrottledRestClient(rate_limit_per_sec=20)   # min_interval = 0.05s
    c._throttle()                                    # primes _last_call
    t0 = time.monotonic()
    c._throttle()                                    # must wait ~0.05s
    assert time.monotonic() - t0 >= 0.04


def test_throttle_survives_a_backward_last_call():
    # a stale/negative elapsed (as a wall-clock step would produce pre-fix)
    # must NOT sleep for a very long time
    c = ThrottledRestClient(rate_limit_per_sec=1)
    c._last_call = time.monotonic() + 5.0            # "future" last call
    t0 = time.monotonic()
    c._throttle()                                    # elapsed<0 -> no long sleep
    assert time.monotonic() - t0 < 1.0
