"""tests/test_gc_trace_pusher.py — order-lifecycle spans for the Traces
drilldown. span_of is the contract: exactly one span per order terminal
audit record, ERROR only when the venue gave us nothing, deterministic
ids (restart-safe dedup), and pre-upgrade records skipped cleanly. tick()
mirrors the log pusher's never-drop offset discipline.
"""
import json

import pytest

import scripts.gc_trace_pusher as tp


def _terminal_line(oid="ord1", code="OM-000", terminal="filled",
                   fill_ratio=1.0, created=1000.0, ts=1025.0, **extra):
    d = {"purpose": "entry", "avg_price": 100.0, "fees_usd": 0.016,
         "order_id": oid, "pair": "ETHUSD", "side": "buy",
         "terminal": terminal, "created_ts": created,
         "fill_ratio": fill_ratio, "reprices": 0}
    d.update(extra)
    return json.dumps({"code": code, "src": "order_manager", "ts": ts,
                       "msg": "x", "data": d}) + "\n"


def test_filled_order_becomes_ok_span():
    sp = tp.span_of(_terminal_line())
    assert sp is not None
    assert sp["status"]["code"] == 1                      # OK
    assert sp["name"] == "order.entry"
    assert int(sp["endTimeUnixNano"]) - int(sp["startTimeUnixNano"]) == \
        pytest.approx(25e9)
    assert len(sp["traceId"]) == 32 and len(sp["spanId"]) == 16


def test_unfilled_reject_is_error_span():
    sp = tp.span_of(_terminal_line(terminal="expired", fill_ratio=0.0,
                                   code="OM-040"))
    assert sp["status"]["code"] == 2                      # ERROR


def test_partial_fill_cancel_is_ok():
    # the venue DID trade with us; a partial that timed out is not an error
    sp = tp.span_of(_terminal_line(terminal="cancelled", fill_ratio=0.4))
    assert sp["status"]["code"] == 1


def test_deterministic_ids_for_dedup():
    a = tp.span_of(_terminal_line())
    b = tp.span_of(_terminal_line())
    assert a["traceId"] == b["traceId"] and a["spanId"] == b["spanId"]
    c = tp.span_of(_terminal_line(oid="other"))
    assert c["spanId"] != a["spanId"]


def test_pre_upgrade_and_foreign_records_skipped():
    old = json.dumps({"code": "OM-000", "src": "order_manager",
                      "ts": 5.0, "data": {"purpose": "entry"}}) + "\n"
    assert tp.span_of(old) is None                        # no lifecycle
    assert tp.span_of('{"code": "SZ-000", "src": "sizer", "ts": 1}\n') is None
    assert tp.span_of("not json\n") is None
    assert tp.span_of(_terminal_line(created=2000.0, ts=1000.0)) is None


def test_tick_ships_and_never_drops(tmp_path, monkeypatch):
    audit = tmp_path / "audit.jsonl"
    audit.write_text(
        '{"code": "CG-000", "src": "startup", "ts": 1}\n'
        + _terminal_line(oid="a") + _terminal_line(oid="b"),
        encoding="utf-8")
    cfg = {"url": "https://x", "auth": "z", "audit": str(audit),
           "state": str(tmp_path / "state.json"), "period": 60}
    got = []
    monkeypatch.setattr(tp, "_push", lambda c, spans: got.extend(spans))
    assert tp.tick(cfg) == 2
    assert {s["name"] for s in got} == {"order.entry"}
    # idempotent: nothing new -> nothing shipped
    assert tp.tick(cfg) == 0
    # a push failure must NOT advance the offset
    audit.write_text(audit.read_text(encoding="utf-8")
                     + _terminal_line(oid="c"), encoding="utf-8")

    def boom(c, spans):
        raise RuntimeError("gateway down")
    monkeypatch.setattr(tp, "_push", boom)
    with pytest.raises(RuntimeError):
        tp.tick(cfg)
    monkeypatch.setattr(tp, "_push", lambda c, spans: got.extend(spans))
    assert tp.tick(cfg) == 1                              # retried, not lost
    assert len(got) == 3


def test_tick_partial_line_waits(tmp_path, monkeypatch):
    audit = tmp_path / "audit.jsonl"
    full = _terminal_line(oid="a")
    audit.write_text(full + _terminal_line(oid="b").rstrip("\n"),
                     encoding="utf-8")                     # torn tail
    cfg = {"url": "https://x", "auth": "z", "audit": str(audit),
           "state": str(tmp_path / "state.json"), "period": 60}
    got = []
    monkeypatch.setattr(tp, "_push", lambda c, spans: got.extend(spans))
    assert tp.tick(cfg) == 1                              # only the whole line
    audit.write_text(audit.read_text(encoding="utf-8") + "\n",
                     encoding="utf-8")                     # tail completes
    assert tp.tick(cfg) == 1
    assert len(got) == 2
