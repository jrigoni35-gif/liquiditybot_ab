# tests/test_boundary_payload.py
"""Aggregation/status-discipline tests for scripts/boundary_payload.py."""
import json

from scripts.boundary_payload import collect  # noqa: E402


def _fakes(**over):
    fns = {
        "meta_fn": lambda: {"generated_at": "2026-09-21T00:00:00Z",
                            "git_head": "abc123", "exec_era": "12-x"},
        "era_fn": lambda: {"n": 47, "selected": {"net": 2.9}},
        "census_fn": lambda: {"refused": None, "arrivals": 77676},
        "bounds_fn": lambda: {"refused": None, "strata": {}},
        "ecology_fn": lambda: {"refused": None, "section1": {}},
        "quantdb_fn": lambda: {"views": {}, "crosscheck": {}},
    }
    fns.update(over)
    return fns


def test_all_ok_complete():
    payload = collect(**_fakes())
    assert payload["complete"] is True
    assert payload["sections"]["era_readout"]["data"]["n"] == 47
    assert all(s["status"] == "ok" for s in payload["sections"].values())


def test_refusal_is_recorded_not_dropped():
    payload = collect(**_fakes(
        ecology_fn=lambda: {"refused": "CHAIN_TORN"}))
    sec = payload["sections"]["gate_ecology"]
    assert payload["complete"] is False
    assert sec["status"] == "refused"
    assert sec["code"] == "CHAIN_TORN"


def test_exception_is_recorded_not_raised():
    def boom():
        raise RuntimeError("duckdb exploded")
    payload = collect(**_fakes(quantdb_fn=boom))
    sec = payload["sections"]["quant_db"]
    assert payload["complete"] is False
    assert sec["status"] == "error"
    assert "duckdb exploded" in sec["error"]


def test_payload_roundtrips_json(tmp_path):
    payload = collect(**_fakes())
    out = tmp_path / "payload.json"
    out.write_text(json.dumps(payload, indent=1, sort_keys=True,
                              default=str), encoding="utf-8")
    back = json.loads(out.read_text(encoding="utf-8"))
    assert back["meta"]["exec_era"] == "12-x"
    assert set(back["sections"]) == {
        "era_readout", "gradeability_census", "reject_bounds",
        "gate_ecology", "quant_db"}
