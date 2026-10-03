"""scripts/forward_reads.py - the job that turns calendar time into forward
evidence. Pinned: eliminations stick across runs, nothing is written into the
repo, the summary reconciles, and a fresh lock is respected."""
import json
import time

from scripts import forward_reads as fr


def test_eliminations_stick_and_new_ids_are_added(tmp_path):
    p = tmp_path / "s.json"
    fr.sticky_statuses(p, [{"id": "a", "status": "ELIMINATED FOR TRIPS"},
                           {"id": "b", "status": "UNDECIDED"}])
    out = fr.sticky_statuses(p, [{"id": "a", "status": "LIVE"},
                                 {"id": "b", "status": "LIVE"},
                                 {"id": "c", "status": "UNDECIDED"}])
    assert out == {"a": "ELIMINATED FOR TRIPS", "b": "LIVE", "c": "UNDECIDED"}
    assert json.loads(p.read_text(encoding="utf-8")) == out


def _row(i, st):
    return {"id": i, "use": "trip", "status": st,
            "all": {"n": 40, "db_dead": 1.0}, "forward": {"n": 2, "db_exist": 0.5}}


def test_summary_reconciles_against_the_registry():
    led = {"rows": [_row("a", "UNDECIDED"), _row("b", "UNDECIDED")], "missing": ["c"]}
    doc = fr.summarise(led, {"a": "ELIMINATED FOR TRIPS"}, [], {}, 3)
    assert doc["reconcile"].endswith("[OK]")
    assert doc["rows"][0]["status"] == "ELIMINATED FOR TRIPS"     # sticky wins
    assert doc["rows"][0]["this_run"] == "UNDECIDED"
    assert fr.summarise(led, {}, [], {}, 4)["reconcile"].endswith("[MISMATCH]")


def test_end_to_end_writes_only_under_out(tmp_path, monkeypatch):
    rep = {"registered": {"panel_months": ["2023-01", "2026-10"]}}
    calls = {}

    def fake_ad(argv):
        calls["ad"] = argv
        d = tmp_path / "out" / "alpha_decay"
        d.mkdir(parents=True, exist_ok=True)
        (d / "alpha_decay_20261009T000000Z.json").write_text(json.dumps(rep), encoding="utf-8")
        return 0

    def fake_el(argv):
        calls["el"] = argv
        d = tmp_path / "out" / "ledger"
        d.mkdir(parents=True, exist_ok=True)
        (d / "ledger_20261009T000000Z.json").write_text(json.dumps(
            {"rows": [_row(f"h{i}", "UNDECIDED") for i in range(21)], "missing": []}),
            encoding="utf-8")
        return 0
    monkeypatch.setattr(fr.ad, "main", fake_ad)
    monkeypatch.setattr(fr.el, "main", fake_el)
    reg_before = fr.el.REGISTRY.read_text(encoding="utf-8")
    assert fr.run_once(tmp_path / "out") == 0
    assert calls["ad"][:2] == ["--through", "now"] and "--write-status" not in calls["el"]
    doc = json.loads((tmp_path / "out" / fr.SUMMARY_NAME).read_text(encoding="utf-8"))
    assert doc["reconcile"].endswith("[OK]") and doc["window"] == ["2023-01", "2026-10"]
    assert fr.el.REGISTRY.read_text(encoding="utf-8") == reg_before
    assert not (tmp_path / "out" / ".forward_reads.lock").exists()


def test_a_fresh_lock_skips_and_a_stale_one_is_reclaimed(tmp_path, monkeypatch):
    out = tmp_path / "out"
    out.mkdir()
    lock = out / ".forward_reads.lock"
    lock.write_text("x", encoding="utf-8")
    monkeypatch.setattr(fr.ad, "main", lambda argv: (_ for _ in ()).throw(AssertionError("ran")))
    assert fr.run_once(out) == 0                         # fresh: skipped
    old = time.time() - fr.LOCK_STALE_S - 10
    import os
    os.utime(lock, (old, old))
    monkeypatch.setattr(fr.ad, "main", lambda argv: 1)
    assert fr.run_once(out) == 1                         # stale: reclaimed, ran
    assert not lock.exists()


def test_every_run_appends_a_timestamped_evidence_line(tmp_path, monkeypatch):
    """The view-blend arms must use, at each past bar, only the evidence that
    existed THEN - so each forward read appends (ts, id, status, dB) to an
    append-only log rather than only overwriting the summary."""
    rep = {"registered": {"panel_months": ["2023-01", "2026-10"]}}

    def fake_ad(argv):
        d = tmp_path / "out" / "alpha_decay"
        d.mkdir(parents=True, exist_ok=True)
        (d / "alpha_decay_20261009T000000Z.json").write_text(json.dumps(rep), encoding="utf-8")
        return 0

    def fake_el(argv):
        d = tmp_path / "out" / "ledger"
        d.mkdir(parents=True, exist_ok=True)
        (d / "ledger_20261009T000000Z.json").write_text(json.dumps(
            {"rows": [_row(f"h{i}", "UNDECIDED") for i in range(21)], "missing": []}),
            encoding="utf-8")
        return 0
    monkeypatch.setattr(fr.ad, "main", fake_ad)
    monkeypatch.setattr(fr.el, "main", fake_el)
    out = tmp_path / "out"
    assert fr.run_once(out) == 0 and fr.run_once(out) == 0
    lines = [json.loads(x) for x in (out / fr.EVIDENCE_LOG).read_text(encoding="utf-8").splitlines()]
    assert len(lines) == 42                                   # 21 ids x 2 runs, appended
    assert {"ts", "id", "status", "db_exist_forward"} <= set(lines[0])
    assert all(isinstance(x["ts"], float) for x in lines)
