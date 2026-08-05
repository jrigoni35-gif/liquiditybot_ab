"""tests/test_gc_log_pusher.py — W2-25: gc_log_pusher lacked the
advance-on-junk fix gc_trace_pusher already has. When a tick's whole
remaining batch is junk (parses to None every time — no `_record`
matches), the offset must still advance past it; otherwise the same
junk lines are re-read and re-parsed on every tick forever.
"""
import json

import pytest

import scripts.gc_log_pusher as lp


def _event_line(msg="hi", level="INFO", ts=1000.0, logger="bot"):
    return json.dumps({"ts": ts, "level": level, "msg": msg,
                       "logger": logger}) + "\n"


def test_tick_ships_and_never_drops(tmp_path, monkeypatch):
    events = tmp_path / "events.jsonl"
    events.write_text(_event_line("a") + _event_line("b"), encoding="utf-8")
    cfg = {"url": "https://x", "auth": "z", "events": str(events),
          "state": str(tmp_path / "state.json"), "period": 10}
    got = []
    monkeypatch.setattr(lp, "_push", lambda c, recs: got.extend(recs))
    assert lp.tick(cfg) == 2
    assert lp.tick(cfg) == 0                # idempotent


def test_trailing_junk_lines_advance_the_offset(tmp_path, monkeypatch):
    # W2-25: a log containing ONLY junk (no parseable event) after the
    # already-shipped prefix must have its offset advance past the junk
    # after one tick — today it is re-parsed on every tick forever.
    events = tmp_path / "events.jsonl"
    events.write_text("not json at all\n" + "{\"missing\": \"ts\"}\n",
                      encoding="utf-8")
    cfg = {"url": "https://x", "auth": "z", "events": str(events),
          "state": str(tmp_path / "state.json"), "period": 10}
    got = []
    monkeypatch.setattr(lp, "_push", lambda c, recs: got.extend(recs))
    assert lp.tick(cfg) == 0                # nothing shippable
    st = lp._load_state(cfg["state"])
    assert st["offset"] == events.stat().st_size    # offset advanced past junk

    def boom(c, recs):
        raise AssertionError("must not push an empty batch")
    monkeypatch.setattr(lp, "_push", boom)
    assert lp.tick(cfg) == 0                # re-tick: no re-parse, no push


def test_push_failure_does_not_advance_past_real_records(tmp_path,
                                                          monkeypatch):
    events = tmp_path / "events.jsonl"
    events.write_text(_event_line("a"), encoding="utf-8")
    cfg = {"url": "https://x", "auth": "z", "events": str(events),
          "state": str(tmp_path / "state.json"), "period": 10}

    def boom(c, recs):
        raise RuntimeError("gateway down")
    monkeypatch.setattr(lp, "_push", boom)
    with pytest.raises(RuntimeError):
        lp.tick(cfg)
    st = lp._load_state(cfg["state"])
    assert st["offset"] == 0                # never advanced on push failure


def test_rotation_ships_the_renamed_files_tail(tmp_path, monkeypatch):
    """29g rotation gap: JsonlLogHandler renames events.jsonl ->
    events.jsonl.1 at the size cap. Lines appended after the pusher's last
    tick sit in the RENAMED file; resetting offset=0 on the new file drops
    them from Loki forever (a silent hole at every rotation — 'all CRITICAL
    overnight' can miss records that exist on disk). The pusher must drain
    the .1 tail before starting over on the new file."""
    events = tmp_path / "events.jsonl"
    events.write_text(_event_line("a"), encoding="utf-8")
    cfg = {"url": "https://x", "auth": "z", "events": str(events),
          "state": str(tmp_path / "state.json"), "period": 10}
    got = []
    monkeypatch.setattr(lp, "_push", lambda c, recs: got.extend(recs))
    assert lp.tick(cfg) == 1                        # ships "a"
    with open(events, "a", encoding="utf-8") as fh:
        fh.write(_event_line("b"))                  # appended after the tick
    events.rename(tmp_path / "events.jsonl.1")      # the handler's rotation
    events.write_text(_event_line("c"), encoding="utf-8")
    assert lp.tick(cfg) == 2                        # drains "b", then "c"
    assert [r["body"]["stringValue"] for r in got] == ["a", "b", "c"]


def test_drain_failure_does_not_lose_the_rotated_tail(tmp_path, monkeypatch):
    """A push outage during the drain must behave like every other push
    failure: no state advance, full re-ship on recovery — never a drop."""
    import pytest as _pytest
    events = tmp_path / "events.jsonl"
    events.write_text(_event_line("a"), encoding="utf-8")
    cfg = {"url": "https://x", "auth": "z", "events": str(events),
          "state": str(tmp_path / "state.json"), "period": 10}
    got = []
    monkeypatch.setattr(lp, "_push", lambda c, recs: got.extend(recs))
    assert lp.tick(cfg) == 1
    with open(events, "a", encoding="utf-8") as fh:
        fh.write(_event_line("b"))
    events.rename(tmp_path / "events.jsonl.1")
    events.write_text(_event_line("c"), encoding="utf-8")

    def boom(c, recs):
        raise RuntimeError("gateway down")
    monkeypatch.setattr(lp, "_push", boom)
    with _pytest.raises(RuntimeError):
        lp.tick(cfg)                                # outage mid-drain
    monkeypatch.setattr(lp, "_push", lambda c, recs: got.extend(recs))
    assert lp.tick(cfg) == 2                        # recovery re-ships all
    assert [r["body"]["stringValue"] for r in got] == ["a", "b", "c"]


def test_partial_trailing_line_waits(tmp_path, monkeypatch):
    events = tmp_path / "events.jsonl"
    full = _event_line("a")
    events.write_text(full + _event_line("b").rstrip("\n"), encoding="utf-8")
    cfg = {"url": "https://x", "auth": "z", "events": str(events),
          "state": str(tmp_path / "state.json"), "period": 10}
    got = []
    monkeypatch.setattr(lp, "_push", lambda c, recs: got.extend(recs))
    assert lp.tick(cfg) == 1                # only the whole line
    events.write_text(events.read_text(encoding="utf-8") + "\n",
                      encoding="utf-8")
    assert lp.tick(cfg) == 1
    assert len(got) == 2
