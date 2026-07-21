"""Feed-recording retention + reconciliation sidecar (data/recording.py).

Recording used to write one unbounded JSONL per boot with no cleanup and no
tie to the live session's realized P&L. This pins the hardened behavior:
  * session_sink names per boot and creates the dir;
  * SinkRotator rolls to .partNN when a file exceeds the size cap (all feed
    recorders in a boot share ONE rotator, so they roll together);
  * prune_recordings keeps the newest N and drops the too-old, incl. sidecars;
  * the flat-start sidecar round-trips start/end P&L snapshots — the ground
    truth the replay-vs-live reconciliation gate reads.
"""
import os

from data.recording import (
    SinkRotator,
    discover_sessions,
    pnl_snapshot,
    prune_recordings,
    read_sidecar,
    session_part_files,
    session_sink,
    update_sidecar,
)
from data.replay import FeedRecorder, load_session


def test_session_sink_names_and_creates_dir(tmp_path):
    d = tmp_path / "recordings"
    p = session_sink(str(d), 1_700_000_000.0)
    assert p.name == "session_1700000000.jsonl"
    assert d.exists()


def test_sink_rotator_rolls_when_file_exceeds_cap(tmp_path):
    base = session_sink(str(tmp_path), 1000.0)
    rot = SinkRotator(base, max_bytes=1)          # tiny cap: roll after any write
    first = rot.current()
    assert first == base                          # part 0 is the un-suffixed base
    first.write_text("x" * 8, encoding="utf-8")   # exceed the cap
    second = rot.current()
    assert second != first and second.name == "session_1000.part01.jsonl"


def test_prune_keeps_newest_and_drops_the_rest(tmp_path):
    files = []
    for i in range(4):
        p = tmp_path / f"session_{1000 + i}.jsonl"
        p.write_text("{}", encoding="utf-8")
        os.utime(p, (1000 + i, 1000 + i))         # deterministic mtimes
        files.append(p)
    deleted = prune_recordings(str(tmp_path), retain_days=0, retain_files=2,
                               now_ts=2000.0)
    assert set(deleted) == {files[0], files[1]}   # oldest two dropped
    assert files[2].exists() and files[3].exists()


def test_prune_drops_too_old_and_its_sidecar(tmp_path):
    old = tmp_path / "session_100.jsonl"
    old.write_text("{}", encoding="utf-8")
    update_sidecar(old, "start", pnl_snapshot(0.0, 5000.0, 0, 100.0))
    assert read_sidecar(old) is not None
    two_days = 2 * 86400
    os.utime(old, (100.0, 100.0))
    deleted = prune_recordings(str(tmp_path), retain_days=1, retain_files=0,
                               now_ts=100.0 + two_days)
    assert old in deleted
    assert not old.exists()
    assert read_sidecar(old) is None              # orphan sidecar cleaned too


def test_sidecar_round_trips_start_and_end(tmp_path):
    sink = session_sink(str(tmp_path), 1234.0)
    update_sidecar(sink, "start", pnl_snapshot(0.0, 5000.0, 0, 1234.0))
    update_sidecar(sink, "end", pnl_snapshot(-3.4, 4996.6, 1, 9999.0))
    meta = read_sidecar(sink)
    assert meta is not None
    assert meta["start"]["realized_pnl"] == 0.0
    assert meta["start"]["open_positions"] == 0
    assert meta["end"]["realized_pnl"] == -3.4
    assert meta["end"]["equity"] == 4996.6


def _frame_line(feed, method, args, result, t):
    import json
    return json.dumps({"feed": feed, "method": method, "args": args,
                       "kwargs": {}, "result": result, "t": t}) + "\n"


def test_rolled_session_is_one_logical_recording(tmp_path):
    # base + two rotation parts = ONE session, never three recordings
    base = session_sink(str(tmp_path), 1000)
    base.write_text(_frame_line("kraken", "m", [], 1, 1.0), encoding="utf-8")
    (tmp_path / "session_1000.part01.jsonl").write_text(
        _frame_line("kraken", "m", [], 2, 2.0), encoding="utf-8")
    (tmp_path / "session_1000.part02.jsonl").write_text(
        _frame_line("kraken", "m", [], 3, 3.0), encoding="utf-8")
    assert [s.name for s in discover_sessions(str(tmp_path))] == \
        ["session_1000.jsonl"]                       # not double-counted
    assert [p.name for p in session_part_files(base)] == \
        ["session_1000.jsonl", "session_1000.part01.jsonl",
         "session_1000.part02.jsonl"]                # stream order


def test_load_session_reads_all_parts_in_order(tmp_path):
    base = session_sink(str(tmp_path), 2000)
    base.write_text(_frame_line("kraken", "get", ["ETH"], 1, 1.0),
                    encoding="utf-8")
    (tmp_path / "session_2000.part01.jsonl").write_text(
        _frame_line("kraken", "get", ["ETH"], 2, 2.0), encoding="utf-8")
    players = load_session(str(base))
    meta = players.pop("_meta")
    assert meta["frames"] == 2                        # BOTH parts read
    krk = players["kraken"]
    assert krk.get("ETH") == 1 and krk.get("ETH") == 2   # FIFO across parts


def test_prune_treats_rolled_session_as_one(tmp_path):
    old = session_sink(str(tmp_path), 1000)
    old.write_text("{}", encoding="utf-8")
    new = session_sink(str(tmp_path), 2000)
    new.write_text("{}", encoding="utf-8")
    new_part = tmp_path / "session_2000.part01.jsonl"
    new_part.write_text("{}", encoding="utf-8")
    for p, t in ((old, 1000), (new, 2000), (new_part, 2001)):
        os.utime(p, (t, t))
    deleted = prune_recordings(str(tmp_path), retain_days=0, retain_files=1,
                               now_ts=3000.0)
    assert deleted == [old]                           # newest SESSION retained
    assert new.exists() and new_part.exists()         # rolled session kept whole


def test_feed_recorder_writes_through_rotator_and_rolls(tmp_path):
    class _Feed:
        def get_book(self, sym):
            return {"bids": [[1.0, 1.0]], "asks": [[2.0, 1.0]], "sym": sym}

    base = session_sink(str(tmp_path), 1000.0)
    rot = SinkRotator(base, max_bytes=1)          # roll after every write
    rec = FeedRecorder(_Feed(), "kraken", rotator=rot)
    assert rec.get_book("ETHUSD")["sym"] == "ETHUSD"   # pass-through result
    rec.get_book("BTCUSD")
    parts = sorted(p.name for p in tmp_path.glob("session_1000*.jsonl"))
    assert "session_1000.jsonl" in parts
    assert any(".part01." in p for p in parts)         # rolled to a second part
