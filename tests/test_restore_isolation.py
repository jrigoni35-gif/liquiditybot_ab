"""
tests/test_restore_isolation.py — StateStore.restore() is per-section
isolated end-to-end (W1-3 / W1-4).

W1-3: `bot.sizer._last_entry.update(...)` and `bot._pos_realized.update(...)`
sat outside every try/except in restore() (and the call site in
LiquidityBot.__init__ has none either) — a snapshot where either field is a
non-mapping (schema drift, hand-edited state.json) raised straight through
__init__ on EVERY launch, exactly the crash restore()'s own module docstring
("best-effort per section... a malformed section is skipped with a warning")
promises can't happen.

W1-4: monitor/postmortem/perf/breaker/candidates/gate_stats/_stop_hit/
risk_protocols shared ONE try/except. If bot.monitor.restore() raised, the
circuit breaker's trip and the risk-protocol day/week loss-budget anchors
were silently skipped — the exact "trip laundered by a reboot" risk that
risk/circuit_breaker.py's docstring says the module exists to prevent.
"""
from types import SimpleNamespace

from core.persistence import SNAPSHOT_VERSION, StateStore
from ml.monitor import ModelMonitor
from risk.circuit_breaker import CircuitBreaker
from risk.protocols import RiskProtocolStack


def _base_bot(**over):
    """Minimal bot double covering every attribute restore() touches,
    following the SimpleNamespace idiom in test_persistence_bak.py."""
    odict = {}
    kw = dict(
        dry_run=True,
        orders=SimpleNamespace(_orders=odict,
                               open_orders=lambda: list(odict.values())),
        sizer=SimpleNamespace(_last_entry={}),
        _pos_realized={},
        monitor=SimpleNamespace(restore=lambda d: None),
        postmortem=SimpleNamespace(restore=lambda d: None),
        candidates=SimpleNamespace(restore=lambda d: None),
        gate_stats=SimpleNamespace(restore=lambda d: None),
        _stop_hit={}, perf=None, breaker=None, risk_protocols=None,
        thales=None,
        state=SimpleNamespace(open_position_count=lambda: 0,
                              cash_balance=0.0, savings_balance=0.0),
        history=SimpleNamespace(_pending={}))
    kw.update(over)
    return SimpleNamespace(**kw)


def _valid_portfolio():
    return {"starting_capital": 10_000.0, "cash_balance": 9_500.0,
            "savings_balance": 500.0, "realized_pnl_total": 100.0,
            "daily_realized_pnl": 10.0}


# --- W1-3 -------------------------------------------------------------
def test_corrupt_sizer_last_entry_does_not_crash_restore(tmp_path):
    """A non-mapping sizer_last_entry must be skipped, not crash restore(),
    and unrelated sections (portfolio) must still land."""
    s = StateStore(str(tmp_path / "state.json"))
    snap = {"version": SNAPSHOT_VERSION, "dry_run": True,
            "portfolio": _valid_portfolio(),
            "sizer_last_entry": "corrupt-string"}
    assert s.write_raw(snap)

    bot = _base_bot()
    ok = s.restore(bot)     # must not raise

    assert ok is True
    assert bot.state.cash_balance == 9_500.0, \
        "portfolio section must still restore despite the corrupt sizer field"


def test_corrupt_pos_realized_does_not_crash_restore(tmp_path):
    """Same corruption on the other unguarded line."""
    s = StateStore(str(tmp_path / "state.json"))
    snap = {"version": SNAPSHOT_VERSION, "dry_run": True,
            "portfolio": _valid_portfolio(),
            "pos_realized": "corrupt-string"}
    assert s.write_raw(snap)

    bot = _base_bot()
    ok = s.restore(bot)     # must not raise

    assert ok is True
    assert bot.state.cash_balance == 9_500.0


# --- W1-4 -------------------------------------------------------------
def test_malformed_monitor_does_not_launder_circuit_breaker_trip(tmp_path):
    """A monitor section shaped to make ModelMonitor.restore() raise must
    not skip the breaker restore (a real trip) or the risk_protocols
    anchors (real day/week loss-budget state) that come after it in the
    shared try/except."""
    s = StateStore(str(tmp_path / "state.json"))

    breaker = CircuitBreaker({"enabled": True, "loss_streak": 3,
                              "cooldown_hours": 6.0})
    # drive a real trip so to_dict() below carries a genuine tripped_at
    for i in range(3):
        breaker.record_close("BTC", won=False, now=float(i))
    assert breaker.is_tripped("BTC", now=4.0) is True

    snap = {
        "version": SNAPSHOT_VERSION, "dry_run": True,
        "portfolio": _valid_portfolio(),
        # ModelMonitor.restore: `tuple(r) for r in d.get("records", [])` -
        # an int element is not iterable -> TypeError inside restore().
        "monitor": {"records": [5]},
        "circuit_breaker": breaker.to_dict(),
        "risk_protocols": {"day_key": "2026-07-22", "day_anchor": 10_000.0,
                           "week_key": "2026-W30", "week_anchor": 9_800.0},
    }
    assert s.write_raw(snap)

    live_monitor = ModelMonitor({})
    live_breaker = CircuitBreaker({"enabled": True, "loss_streak": 3,
                                   "cooldown_hours": 6.0})
    live_risk_protocols = RiskProtocolStack({})

    bot = _base_bot(monitor=live_monitor, breaker=live_breaker,
                    risk_protocols=live_risk_protocols)

    ok = s.restore(bot)     # must not raise despite the malformed monitor

    assert ok is True
    assert live_breaker.is_tripped("BTC", now=4.0) is True, \
        "a real circuit-breaker trip must survive a malformed monitor section"
    assert live_risk_protocols._day_anchor == 10_000.0, \
        "day loss-budget anchor must survive a malformed monitor section"
    assert live_risk_protocols._week_anchor == 9_800.0, \
        "week loss-budget anchor must survive a malformed monitor section"
