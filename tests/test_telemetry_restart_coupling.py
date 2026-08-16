"""Telemetry restart-coupling (2026-07-20): deploys never reached the
long-lived pusher sidecars — the supervisor relaunches them only when they
DIE, and the auto-updater's restart signal goes to the runner alone. The
profit-pools row showed "No data" all day while the runner carried the
values: the pusher process predated the gauges.

Three coupled fixes, pinned here:
  * every pusher exits when its own source changes on disk (supervisor
    relaunches it on the new code within its stale-heartbeat window);
  * auto_update (spawned FRESH each cadence, so always current code)
    bounces pushers when the deployed rev differs from its marker — the
    migration path for pushers started before the self-exit existed;
  * an unloaded champion exports ml_model_info{kind="prior"} instead of
    silence (post-schema-bump "No data" read as broken telemetry).
"""
import json
import time
from pathlib import Path

import scripts.auto_update as au
import scripts.gc_log_pusher as glp
import scripts.gc_pusher as gp
import scripts.gc_trace_pusher as gtp

ROOT = Path(__file__).resolve().parents[1]


# --- pusher self-exit --------------------------------------------------------
def test_source_change_detection_flips_on_mtime(monkeypatch):
    for mod in (gp, glp, gtp):
        assert mod._source_changed() is False, mod.__name__
        monkeypatch.setattr(mod, "_BOOT_MTIME", mod._BOOT_MTIME - 1.0)
        assert mod._source_changed() is True, mod.__name__


def test_source_read_failure_stays_alive(monkeypatch):
    # fail-safe direction: an unreadable source file must NOT flap the
    # process — the auto_update rev-marker bounce is the backstop
    import os as _os
    real = _os.path.getmtime

    def boom(_):
        raise OSError("transient")
    monkeypatch.setattr(_os.path, "getmtime", boom)
    try:
        assert gp._source_changed() is False
    finally:
        monkeypatch.setattr(_os.path, "getmtime", real)


def test_every_pusher_main_loop_carries_the_guard():
    for name in ("gc_pusher.py", "gc_log_pusher.py", "gc_trace_pusher.py"):
        src = (ROOT / "scripts" / name).read_text(encoding="utf-8")
        body = src[src.index("def main("):]
        assert "_source_changed()" in body, f"{name}: guard not in main loop"


# --- auto_update rev-marker bounce -------------------------------------------
def test_bounce_writes_marker_once_and_short_circuits(tmp_path, monkeypatch):
    monkeypatch.setattr(au, "OUT", tmp_path)
    au._ensure_pushers_current()                 # no marker -> bounce + write
    marker = tmp_path / "pushers_code_rev.txt"
    assert marker.exists()
    rev = marker.read_text(encoding="utf-8").strip()
    assert rev                                   # a real short rev
    # matching marker -> untouched (no re-bounce churn every cadence)
    before = marker.stat().st_mtime_ns
    au._ensure_pushers_current()
    assert marker.stat().st_mtime_ns == before


def test_bounce_never_raises(tmp_path, monkeypatch):
    # fail-safe: a broken git/marker path degrades to a log line, never
    # into the update outcome
    monkeypatch.setattr(au, "OUT", tmp_path / "missing" / "dir")
    monkeypatch.setattr(au, "_git", lambda *a, **k: (1, "boom"))
    au._ensure_pushers_current()


def test_updater_entrypoint_runs_the_bounce():
    src = (ROOT / "scripts" / "auto_update.py").read_text(encoding="utf-8")
    tail = src[src.index('if __name__ == "__main__"'):]
    assert "_ensure_pushers_current()" in tail


# --- model panel: prior is a state, not an outage ----------------------------
def test_model_info_says_prior_when_no_champion_loaded(tmp_path):
    status = {"written_at": time.time(),
              "ml": {"trained": False, "model_kind": None,
                     "history_rows": 100}}
    p = tmp_path / "status.json"
    p.write_text(json.dumps(status), encoding="utf-8")
    infos = [m for m in gp.collect(str(p))
             if m["name"] == "liquiditybot_ml_model_info"]
    assert infos, "prior state must still export the model info gauge"
    attrs = {a["key"]: a["value"]["stringValue"]
             for a in infos[0]["gauge"]["dataPoints"][0]["attributes"]}
    assert attrs["kind"] == "prior"


def test_model_info_still_names_a_loaded_champion(tmp_path):
    status = {"written_at": time.time(),
              "ml": {"trained": True, "model_kind": "logistic"}}
    p = tmp_path / "status.json"
    p.write_text(json.dumps(status), encoding="utf-8")
    infos = [m for m in gp.collect(str(p))
             if m["name"] == "liquiditybot_ml_model_info"]
    attrs = {a["key"]: a["value"]["stringValue"]
             for a in infos[0]["gauge"]["dataPoints"][0]["attributes"]}
    assert attrs["kind"] == "logistic"
