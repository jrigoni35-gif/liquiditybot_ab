# tests/test_gradeability_census.py
import hashlib
import json
import time

from core.audit import configure_audit, get_audit
from core.codes import Code
from scripts.gradeability_census import census, REFUSAL_CHAIN_TORN


def _chain(tmp_path, n_sweeps=3):
    """Real records, real chain, via the engine's own writer."""
    configure_audit(tmp_path / "audit.jsonl")
    a = get_audit()
    a.log("startup", Code.CG_SESSION_START, "session start: config fingerprint",
          {"config_sha256": "x", "dry_run": True}, counted=False)
    # two hourly EN-000 ticks, cumulative: 4 arrivals/hr, 3 absorbed EN-030
    vec1 = {"arrivals": 4, "EN-030": 3}
    vec2 = {"arrivals": 8, "EN-030": 6}
    a.log("entry_sweep", Code.EN_SWEEP_SUMMARY, "v1", vec1, counted=False)
    a.log("entry_sweep", Code.EN_SWEEP_SUMMARY, "v2", vec2, counted=False)
    return tmp_path / "audit.jsonl"


def test_census_reconstructs_arrival_deltas(tmp_path):
    path = _chain(tmp_path)
    out = census(audit_path=path, fills_path=None,
                 since=0.0, doc_path=None)
    assert out["arrivals"] == 8
    assert out["by_key"]["EN-030"] == 6
    assert out["lost_forever"] == 6        # EN-020(0) + EN-030(6)
    assert out["refused"] is None


def test_census_refuses_torn_chain(tmp_path):
    path = _chain(tmp_path)
    lines = path.read_text().splitlines()
    rec = json.loads(lines[-1])
    rec["data"]["arrivals"] = 999          # tamper: breaks its own h
    lines[-1] = json.dumps(rec)
    path.write_text("\n".join(lines) + "\n")
    out = census(audit_path=path, fills_path=None,
                 since=0.0, doc_path=None)
    assert out["refused"] == REFUSAL_CHAIN_TORN


def test_census_adopts_writer_seam(tmp_path):
    """Seam-adoption parity with core.audit.verify_chain: a hash-valid
    second-generation record whose prev is GENESIS (the designed
    unreadable-at-startup refork, SD-007) is a benign writer seam - the
    census must adopt it and keep reading, not refuse."""
    path = _chain(tmp_path)
    rec = {"seq": 1, "ts": 1758000000.0, "src": "startup",
           "code": Code.CG_SESSION_START.value,
           "msg": "session start: config fingerprint",
           "data": {"config_sha256": "y", "dry_run": True},
           "prev": "0" * 16}
    # mirror the writer's hash: sha256 of json.dumps(rec-without-h,
    # sort_keys=True, default=str)
    body = json.dumps(rec, sort_keys=True, default=str)
    rec["h"] = hashlib.sha256(body.encode("utf-8")).hexdigest()[:16]
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, sort_keys=True, default=str) + "\n")
    out = census(audit_path=path, fills_path=None,
                 since=0.0, doc_path=None)
    assert out["refused"] is None
    assert out["arrivals"] == 8          # a seam record adds no sweep keys


def test_census_de010_coverage_end_to_end(tmp_path):
    """DE-010 events reach de010_coverage through the real writer, and the
    counter honors the --since window like its sibling lines."""
    path = _chain(tmp_path)
    a = get_audit()
    events = [{"asset": "BTC", "ts": 1.0}, {"asset": "ETH", "ts": 2.0}]
    a.log("entry_sweep", Code.DE_DECISION_EVENTS, "DE-010: hourly batch",
          {"events": events}, counted=False)
    out = census(audit_path=path, fills_path=None,
                 since=0.0, doc_path=None)
    assert out["refused"] is None
    assert out["de010_coverage"] == 2
    # window the DE-010 record OUT while an EN-000 tick stays IN (else the
    # census rightly refuses NO_EN000_IN_WINDOW before coverage is read)
    de010_ts = json.loads(path.read_text().splitlines()[-1])["ts"]
    time.sleep(0.01)      # cross the writer's ms rounding (ts is 3dp)
    a.log("entry_sweep", Code.EN_SWEEP_SUMMARY, "v3",
          {"arrivals": 12, "EN-030": 9}, counted=False)
    out = census(audit_path=path, fills_path=None,
                 since=de010_ts + 0.001, doc_path=None)
    assert out["refused"] is None
    assert out["de010_coverage"] == 0
    assert out["arrivals"] == 12         # only the post-since tick counts
