"""tests/test_lowsev_durability.py — survey LOW-severity durability/concurrency
cleanups.

  * StateStore._seal_and_write must NOT mutate the caller's dict (a reused dict
    otherwise carries a stale _sha256 into its next write and fails its own
    checksum), and the sealed file must still round-trip through _verify.
  * JsonlLogHandler rotation is isolated: a log line still lands even if the
    rotation step raises, and rotation fires at the size threshold.
"""
import json
import logging

from core.persistence import StateStore
from core.runtime import JsonlLogHandler


def test_seal_does_not_mutate_caller_dict_and_round_trips(tmp_path):
    store = StateStore(str(tmp_path / "state.json"))
    data = {"schema_version": 1, "positions": [], "equity": 800.0}
    assert store._seal_and_write(data) is True
    assert "_sha256" not in data, "caller's dict must not be mutated"
    # the written file verifies (checksum computed over the copy, not `data`)
    raw = json.loads((tmp_path / "state.json").read_text(encoding="utf-8"))
    assert "_sha256" in raw
    assert StateStore._verify(dict(raw)) is True


def test_reused_dict_seals_correctly_twice(tmp_path):
    # the exact hazard the copy fixes: seal the SAME dict twice; the second
    # write must still verify (old in-place mutation left a stale seal).
    store = StateStore(str(tmp_path / "state.json"))
    data = {"schema_version": 1, "equity": 800.0}
    store._seal_and_write(data)
    store._seal_and_write(data)                     # reuse the same dict
    raw = json.loads((tmp_path / "state.json").read_text(encoding="utf-8"))
    assert StateStore._verify(dict(raw)) is True


def test_log_line_survives_a_rotation_error(tmp_path, monkeypatch):
    p = tmp_path / "events.jsonl"
    h = JsonlLogHandler(str(p), max_bytes=10)       # tiny -> rotate every line
    p.write_text("x" * 50, encoding="utf-8")        # over threshold
    monkeypatch.setattr(type(p), "replace",
                        lambda self, other: (_ for _ in ()).throw(OSError("busy")))
    rec = logging.LogRecord("t", logging.INFO, __file__, 1, "hello", (), None)
    h.emit(rec)                                     # rotation raises internally
    # the line still landed despite the rotation error
    lines = [ln for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert any('"msg": "hello"' in ln for ln in lines)


def test_rotation_fires_at_threshold(tmp_path):
    p = tmp_path / "events.jsonl"
    h = JsonlLogHandler(str(p), max_bytes=10)
    p.write_text("y" * 50, encoding="utf-8")
    rec = logging.LogRecord("t", logging.INFO, __file__, 1, "after", (), None)
    h.emit(rec)
    assert p.with_suffix(".jsonl.1").exists()                  # rotated generation
    assert '"msg": "after"' in p.read_text(encoding="utf-8")   # fresh file has the line
