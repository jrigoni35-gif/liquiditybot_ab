"""Scratch: DE-010 flush vs a FAILING audit write (AuditTrail.log returns 0, never raises)."""
import json
from types import SimpleNamespace
import core.audit as audit_mod
from core.audit import configure_audit
from main import LiquidityBot


def _stub():
    s = SimpleNamespace(_de_events=[{"asset": "ETH", "absorb": "EN-030"}] * 5,
                        _de_emitted=0.0)
    return s


def test_control_success_clears(tmp_path):
    configure_audit(tmp_path / "audit.jsonl")
    s = _stub()
    LiquidityBot._flush_decision_events(s, 10_000.0)
    recs = [json.loads(x) for x in (tmp_path / "audit.jsonl").read_text().splitlines()]
    assert [r["code"] for r in recs] == ["DE-010"]
    assert s._de_events == [] and s._de_emitted == 10_000.0


def test_failed_write_keeps_buffer_per_docstring(tmp_path):
    # audit path is a DIRECTORY -> open() raises OSError inside log() -> log returns 0
    bad = tmp_path / "isdir"
    bad.mkdir()
    configure_audit(bad)
    s = _stub()
    LiquidityBot._flush_decision_events(s, 10_000.0)
    assert audit_mod.get_audit().dropped >= 1, "injection did not fire"
    # docstring: "_de_emitted stamps only on SUCCESS, so a failed emit keeps the buffer"
    assert len(s._de_events) == 5, "buffer was DISCARDED on a failed audit write"
    assert s._de_emitted == 0.0, "hourly gate re-armed on a failed write"


def test_failed_write_is_counted(tmp_path):
    """FIX PIN: a dropped batch is counted, never silent."""
    import main
    print("main from", main.__file__)
    bad = tmp_path / "isdir"; bad.mkdir()
    configure_audit(bad)
    s = _stub()
    LiquidityBot._flush_decision_events(s, 10_000.0)
    assert getattr(s, "_de_dropped", 0) == 5
    assert s._de_events == []
