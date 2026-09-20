# tests/test_gradeability_census.py
import json

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
