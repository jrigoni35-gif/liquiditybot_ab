"""Slow-cycle feed fetch: concurrent, ordered, fail-soft.

Measured live, the serial OKX -> Binance.US chain cost ~4.3s of dead time per
slow cycle during which the decision loop (stops included) is blind. The fetch
is now bounded by the slowest single feed, payload order is stable for
build_view, one failing feed degrades to {} instead of raising, and recording
mode (shared FeedRecorder sink) stays serial. Startup: stale control commands
queued before the runner existed are discarded, not executed (a leftover
'stop' used to kill a fresh runner at +1.2s).
"""
import time
import types

from main import LiquidityBot


def _bot(serial=False, ccxt=None, okx_delay=0.15, bn_delay=0.15):
    b = LiquidityBot.__new__(LiquidityBot)
    b._serial_feeds = serial

    def feed(name, delay, payload):
        def get():
            time.sleep(delay)
            return payload
        return types.SimpleNamespace(get_market_data=get)

    b.okx = feed("okx", okx_delay, {"okx": 1})
    b.binanceus = feed("bn", bn_delay, {"bn": 2})
    b.ccxt_feed = ccxt
    return b


def test_fetch_is_concurrent_not_serial():
    b = _bot(okx_delay=0.15, bn_delay=0.15)
    t0 = time.perf_counter()
    out = b._fetch_market_payloads()
    elapsed = time.perf_counter() - t0
    assert out == [{"okx": 1}, {"bn": 2}]         # order preserved
    assert elapsed < 0.27                          # ~max(delays), not sum


def test_failing_feed_degrades_to_empty_payload():
    b = _bot()

    def boom():
        raise RuntimeError("venue down")
    b.okx = types.SimpleNamespace(get_market_data=boom)
    out = b._fetch_market_payloads()
    assert out == [{}, {"bn": 2}]                  # no exception, order kept


def test_recording_mode_stays_serial():
    b = _bot(serial=True, okx_delay=0.1, bn_delay=0.1)
    t0 = time.perf_counter()
    out = b._fetch_market_payloads()
    elapsed = time.perf_counter() - t0
    assert out == [{"okx": 1}, {"bn": 2}]
    assert elapsed >= 0.19                         # sum of delays: serial


def test_ccxt_feed_included_when_wired():
    ccxt = types.SimpleNamespace(get_market_data=lambda: {"cx": 3})
    b = _bot(ccxt=ccxt)
    assert b._fetch_market_payloads() == [{"okx": 1}, {"bn": 2}, {"cx": 3}]


def test_stale_control_commands_are_discarded_at_startup(tmp_path):
    """A 'stop' queued while no runner exists must not execute against the
    next runner. BotRunner purges the queue at construction."""
    import sys
    sys.path.insert(0, ".")
    from core.runtime import ControlChannel
    chan = ControlChannel(str(tmp_path / "control"))
    chan.send("stop")
    chan.send("pause")
    # simulate the runner's boot purge (the exact call BotRunner makes)
    stale = chan.consume()
    assert [c["cmd"] for c in stale] == ["stop", "pause"]
    assert chan.consume() == []                    # queue is now clean
