"""Hardening from the 2026-07-13 host I/O storm + audit-fork incident.

1. StatusWriter absorbs status-write PermissionError: an external reader
   (dashboard/Defender/sync) holding status.json past the retry window
   must cost one skipped write and a sparse WARNING - not a full
   cycle-error traceback per collision (476 in one storm, which then
   tripped the check-in's error-volume anomaly and paused the bot).
2. _rows_at_last_train survives the snapshot roundtrip: its init default
   is "rows right now", so every restart deferred the auto-retrain by
   retrain_min_new_rows (observed: keepalive revival moved the trigger
   from 62 to 137 rows mid-recovery).
"""
import logging
import types

import core.runtime as runtime
from core.persistence import StateStore
from core.state import PortfolioState


def test_status_writer_absorbs_permission_error(tmp_path, monkeypatch, caplog):
    w = runtime.StatusWriter(status_path=str(tmp_path / "status.json"),
                             equity_path=str(tmp_path / "equity.csv"))

    def _denied(path, payload, _retries=6):
        raise PermissionError(5, "Access is denied")

    monkeypatch.setattr(runtime, "atomic_write_json", _denied)
    with caplog.at_level(logging.WARNING, logger=runtime.log.name):
        for _ in range(12):
            w.write({"equity": 1.0}, now=1000.0)   # must not raise
    assert w._write_fails == 12
    warns = [r for r in caplog.records if "status write skipped" in
             r.getMessage()]
    assert len(warns) == 2                          # sparse: at 1 and 10

    monkeypatch.setattr(runtime, "atomic_write_json",
                        lambda p, d, _retries=6: None)
    w.write({"equity": 1.0}, now=2000.0)
    assert w._write_fails == 0                      # recovery resets


def _stub_bot(rows_at_last_train):
    b = types.SimpleNamespace()
    b.dry_run = True
    b.state = PortfolioState(starting_capital=800)
    b.orders = types.SimpleNamespace(open_orders=lambda: [], _orders={})
    b.history = types.SimpleNamespace(_pending={})
    b.sizer = types.SimpleNamespace(_last_entry={})
    b._pos_realized = {}
    b._halted = False
    b._stop_hit = {}
    b._rows_at_last_train = rows_at_last_train
    hollow = types.SimpleNamespace(to_dict=lambda: {}, restore=lambda d: None)
    b.monitor = hollow
    b.postmortem = hollow
    b.candidates = hollow
    b.gate_stats = hollow
    b.risk_protocols = None
    return b


def test_rows_at_last_train_survives_snapshot_roundtrip(tmp_path):
    store = StateStore(str(tmp_path / "state.json"))
    assert store.snapshot(_stub_bot(rows_at_last_train=37))
    revived = _stub_bot(rows_at_last_train=999)     # init-time default
    assert store.restore(revived)
    assert revived._rows_at_last_train == 37


def test_old_snapshot_without_key_keeps_init_value(tmp_path):
    store = StateStore(str(tmp_path / "state.json"))
    assert store.snapshot(_stub_bot(rows_at_last_train=37))
    data = store.load_raw()
    assert data is not None
    del data["rows_at_last_train"]                  # simulate old snapshot
    assert store.write_raw(data)
    revived = _stub_bot(rows_at_last_train=112)
    assert store.restore(revived)
    assert revived._rows_at_last_train == 112       # init default retained


def test_cycle_lifetime_survives_snapshot_roundtrip(tmp_path):
    """The lifetime cycle counter is snapshot state: per-process _cycle
    resets on every restart by design, but _cycle_lifetime must carry
    across restarts so the operator can see total engine work."""
    store = StateStore(str(tmp_path / "state.json"))
    bot = _stub_bot(rows_at_last_train=0)
    bot._cycle_lifetime = 12345
    assert store.snapshot(bot)
    revived = _stub_bot(rows_at_last_train=0)
    revived._cycle_lifetime = 0
    assert store.restore(revived)
    assert revived._cycle_lifetime == 12345


def test_old_snapshot_without_lifetime_starts_at_zero(tmp_path):
    store = StateStore(str(tmp_path / "state.json"))
    bot = _stub_bot(rows_at_last_train=0)
    bot._cycle_lifetime = 777
    assert store.snapshot(bot)
    import json as _json
    p = tmp_path / "state.json"
    data = _json.loads(p.read_text(encoding="utf-8"))
    del data["cycle_lifetime"]                  # simulate pre-upgrade snapshot
    data.pop("_sha256", None)                   # pre-checksum-era files pass
    assert store.write_raw(data)
    revived = _stub_bot(rows_at_last_train=0)
    revived._cycle_lifetime = 0
    assert store.restore(revived)
    assert revived._cycle_lifetime == 0
