"""config_guard coverage for the websockets block: an enabled live feed
with an incoherent staleness gate or unsupported depth must be caught
before it can serve the engine bad data."""
from core.config_guard import validate


def _cfg(**ws):
    base = {"enabled": True, "binanceus_symbols": ["BTCUSD"],
            "depth": 20, "interval_ms": 100, "max_book_age_sec": 2.0}
    base.update(ws)
    return {"system": {"polling_interval_sec": 5}, "websockets": base}


def _fatals(cfg):
    return [m for sev, m in validate(cfg) if sev == "FATAL"]


def _warns(cfg):
    return [m for sev, m in validate(cfg) if sev == "WARN"]


def test_disabled_websockets_produce_no_findings():
    cfg = {"websockets": {"enabled": False, "max_book_age_sec": -1,
                          "depth": 99}}
    assert not any("websockets" in m for _, m in validate(cfg))


def test_nonpositive_staleness_gate_is_fatal():
    assert any("max_book_age_sec" in m
               for m in _fatals(_cfg(max_book_age_sec=0)))


def test_unsupported_depth_is_fatal():
    assert any("depth" in m for m in _fatals(_cfg(depth=15)))


def test_empty_symbols_when_enabled_is_fatal():
    assert any("binanceus_symbols" in m
               for m in _fatals(_cfg(binanceus_symbols=[])))


def test_stale_gate_beyond_poll_interval_warns():
    assert any("max_book_age_sec" in m
               for m in _warns(_cfg(max_book_age_sec=9.0)))


def test_coherent_config_has_no_websocket_fatal():
    assert not any("websockets" in m for m in _fatals(_cfg()))
