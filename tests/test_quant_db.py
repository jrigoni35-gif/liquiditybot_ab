# tests/test_quant_db.py
"""Synthetic-fixture tests for scripts/quant_db.py (DuckDB measurement plane)."""
import json
import sys

import pytest

duckdb = pytest.importorskip("duckdb")  # optional analysis stack — hygiene law

from pathlib import Path  # noqa: E402

from scripts.quant_db import (  # noqa: E402
    REFUSAL_AUDIT_MISSING,
    REFUSAL_DUCKDB_MISSING,
    QuantDbRefusal,
    connect,
    crosscheck,
    main,
    register_views,
)


def _write_audit(path: Path) -> None:
    recs = [
        {"code": "EN-000", "ts": 1.0, "data": {"arrivals": 100}},
        {"code": "DE-010", "ts": 2.0,
         "data": {"events": [
             {"asset": "BTC", "absorb": "EN-030", "propensity": 1.0,
              "ts": 1.5},
             {"asset": "ETH", "absorb": "passed_gate_stack",
              "propensity": 1.0, "ts": 1.6},
         ]}},
        {"code": "DE-010", "ts": 3.0,
         "data": {"events": [
             {"asset": "PAXG", "absorb": "EN-030", "ts": 2.5},
         ]}},
    ]
    path.write_text("\n".join(json.dumps(r) for r in recs) + "\n",
                    encoding="utf-8")


@pytest.fixture()
def desk(tmp_path):
    audit = tmp_path / "audit.jsonl"
    _write_audit(audit)
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    con = connect()
    con.execute("CREATE TABLE t AS SELECT * FROM (VALUES (1,'2026-09-20'),"
                " (2,'2026-09-21')) AS v(i, d)")
    con.execute(f"COPY t TO '{corpus}/klines_1m_TESTUSDT.parquet'"
                " (FORMAT parquet)")
    con.close()
    csvs = {"fills": tmp_path / "fills.csv"}
    csvs["fills"].write_text("ts,symbol\n1.0,BTC\n2.0,ETH\n", encoding="utf-8")
    return {"audit": audit, "corpus": corpus, "csvs": csvs}


def test_views_and_crosscheck(desk):
    con = connect()
    inv = register_views(con, audit_path=desk["audit"],
                         corpus_dir=desk["corpus"],
                         optional_csvs=desk["csvs"])
    assert set(inv["registered"]) == {
        "audit", "de010", "fills", "corpus_testusdt"}
    cc = crosscheck(con)
    assert cc["audit_records"] == 3
    assert cc["de010_events"] == 3
    assert dict(cc["de010_absorb_mix"]) == {
        "EN-030": 2, "passed_gate_stack": 1}
    assert cc["de010_propensity_missing"] == 1  # the PAXG event has none
    assert cc["fills_rows"] == 2
    assert cc["corpus_rows"] == {"corpus_testusdt": 2}


def test_missing_audit_refuses(tmp_path):
    con = connect()
    with pytest.raises(QuantDbRefusal) as exc:
        register_views(con, audit_path=tmp_path / "nope.jsonl",
                       corpus_dir=tmp_path, optional_csvs={})
    assert exc.value.code == REFUSAL_AUDIT_MISSING


def test_missing_duckdb_refuses(monkeypatch):
    monkeypatch.setitem(sys.modules, "duckdb", None)  # import -> ImportError
    with pytest.raises(QuantDbRefusal) as exc:
        connect()
    assert exc.value.code == REFUSAL_DUCKDB_MISSING


def test_main_exit_codes(desk, monkeypatch, capsys):
    import scripts.quant_db as qdb  # noqa: E402,PLC0415

    monkeypatch.setattr(qdb, "AUDIT", desk["audit"])
    monkeypatch.setattr(qdb, "CORPUS_DIR", desk["corpus"])
    monkeypatch.setattr(qdb, "OPTIONAL_CSVS", desk["csvs"])
    assert main() == 0
    out = capsys.readouterr().out
    assert "DE-010 captured arrivals: 3" in out
    assert "corpus_testusdt: 2 rows" in out

    monkeypatch.setattr(qdb, "AUDIT", desk["audit"].parent / "gone.jsonl")
    assert main() == 2
    assert REFUSAL_AUDIT_MISSING in capsys.readouterr().out
