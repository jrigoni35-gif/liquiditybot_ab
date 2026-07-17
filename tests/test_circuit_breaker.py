"""tests/test_circuit_breaker.py — per-asset consecutive-loss breaker.

Contract: trips at loss_streak CONSECUTIVE losses on ONE asset; a win resets
the streak; the trip auto-clears after cooldown (streak included — the pause
is the fresh start); assets are independent; restart cannot launder a trip
(persistence round-trip); disabled = inert."""
from risk.circuit_breaker import CircuitBreaker


def _cb(**over):
    cfg = {"enabled": True, "loss_streak": 3, "cooldown_hours": 6.0}
    cfg.update(over)
    return CircuitBreaker(cfg)


def test_trips_on_consecutive_losses_only():
    cb = _cb()
    assert cb.record_close("BTC", won=False, now=0.0) is False
    assert cb.record_close("BTC", won=False, now=1.0) is False
    assert cb.record_close("BTC", won=True, now=2.0) is False   # reset
    assert cb.record_close("BTC", won=False, now=3.0) is False
    assert cb.record_close("BTC", won=False, now=4.0) is False
    assert cb.is_tripped("BTC", now=5.0) is False               # 2 < 3
    assert cb.record_close("BTC", won=False, now=6.0) is True   # 3rd: TRIP
    assert cb.is_tripped("BTC", now=7.0) is True


def test_assets_are_independent():
    cb = _cb()
    for i in range(3):
        cb.record_close("BTC", won=False, now=float(i))
    assert cb.is_tripped("BTC", now=4.0) is True
    assert cb.is_tripped("ETH", now=4.0) is False
    assert cb.record_close("ETH", won=False, now=5.0) is False  # own streak


def test_cooldown_autoresets_trip_and_streak():
    cb = _cb(cooldown_hours=1.0)
    for i in range(3):
        cb.record_close("BTC", won=False, now=float(i))
    assert cb.is_tripped("BTC", now=10.0) is True
    assert cb.remaining_s("BTC", now=10.0) > 0
    # past cooldown: cleared, and the streak starts fresh
    assert cb.is_tripped("BTC", now=2.0 + 3600.0) is False
    assert cb.record_close("BTC", won=False, now=3700.0) is False  # streak 1
    assert cb.is_tripped("BTC", now=3701.0) is False


def test_no_double_trip_extension():
    cb = _cb(cooldown_hours=1.0)
    for i in range(3):
        cb.record_close("BTC", won=False, now=float(i))
    t0 = cb.remaining_s("BTC", now=100.0)
    # further losses while tripped must NOT extend the cooldown
    cb.record_close("BTC", won=False, now=200.0)
    assert cb.remaining_s("BTC", now=200.0) < t0


def test_persistence_roundtrip_survives_restart():
    cb = _cb()
    for i in range(3):
        cb.record_close("BTC", won=False, now=1000.0 + i)
    cb.record_close("ETH", won=False, now=1000.0)
    cb2 = _cb()
    cb2.restore(cb.to_dict())
    assert cb2.is_tripped("BTC", now=1010.0) is True    # trip not laundered
    assert cb2._streaks["ETH"] == 1
    # malformed restore starts clean, never raises
    cb3 = _cb()
    cb3.restore({"streaks": "junk", "tripped_at": ["x"]})
    assert cb3.is_tripped("BTC") is False


def test_disabled_is_inert():
    cb = _cb(enabled=False)
    for i in range(10):
        cb.record_close("BTC", won=False, now=float(i))
    assert cb.is_tripped("BTC", now=11.0) is False


def test_snapshot_shape():
    cb = _cb()
    for i in range(3):
        cb.record_close("BTC", won=False, now=float(i))
    cb.record_close("ETH", won=False, now=0.0)
    s = cb.snapshot(now=10.0)
    assert s["tripped"].keys() == {"BTC"}
    assert 5.9 < s["tripped"]["BTC"] <= 6.0             # hours remaining
    assert s["streaks"]["ETH"] == 1
    assert s["loss_streak"] == 3
