# tests/test_intake_dataset.py
"""Synthetic-inbox tests for scripts/intake_dataset.py (Lane B)."""
import hashlib
import json

import pytest

from scripts.intake_dataset import (  # noqa: E402
    IntakeRefusal,
    main,
    verify_drop,
    verify_receipt_chain,
)
from core.codes import Code  # noqa: E402


def _drop(inbox, name="darkpool_ats", rows=2, cols=("symbol", "volume"),
          payload_text=None, tamper=None):
    payload = inbox / f"{name}.csv"
    body = payload_text
    if body is None:
        body = ",".join(cols) + "\n" + "\n".join(
            f"MSTR,{1000 + i}" for i in range(rows)) + "\n"
    payload.write_text(body, encoding="utf-8")
    man = {
        "name": name, "version": "1",
        "content_sha256": hashlib.sha256(
            payload.read_bytes()).hexdigest(),
        "rows": rows,
        "schema": [{c: "varchar"} for c in cols],
        "time_range": ["2026-04-20", "2026-05-11"],
        "source": "FINRA ATS weeklySummary mirror",
        "ingested_at": "2026-09-21T00:00:00Z",
        "grid_seconds": None,
        "domain": {"venue_mpid": "passthrough"},
    }
    if tamper:
        tamper(man, payload)
    (inbox / f"{name}.manifest.json").write_text(
        json.dumps(man), encoding="utf-8")
    return payload, man


def test_verified_drop_receipts(tmp_path):
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    _drop(inbox)
    assert main(["--inbox", str(inbox)]) == 0
    recs = verify_receipt_chain(inbox / "receipts.jsonl")
    assert len(recs) == 1
    assert recs[0]["code"] == "DI-000"
    assert recs[0]["data"]["rows"] == 2
    assert recs[0]["data"]["domain"] == {"venue_mpid": "passthrough"}


def test_receipt_chain_links_across_runs(tmp_path):
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    _drop(inbox)
    assert main(["--inbox", str(inbox)]) == 0
    _drop(inbox, name="second_set")
    assert main(["--inbox", str(inbox)]) == 0
    recs = verify_receipt_chain(inbox / "receipts.jsonl")
    assert [r["seq"] for r in recs] == [1, 2, 3]
    assert recs[1]["prev"] == recs[0]["h"]
    assert recs[2]["prev"] == recs[1]["h"]


def test_hash_mismatch(tmp_path):
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    _drop(inbox, tamper=lambda man, payload: man.update(
        content_sha256="0" * 64))
    code, detail = verify_drop(inbox / "darkpool_ats.manifest.json")
    assert code is Code.DI_HASH_MISMATCH
    assert main(["--inbox", str(inbox)]) == 2
    recs = verify_receipt_chain(inbox / "receipts.jsonl")
    assert recs[0]["code"] == "DI-030"  # the failure is receipted, not lost


def test_payload_missing(tmp_path):
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    payload, _ = _drop(inbox)
    payload.unlink()
    code, _ = verify_drop(inbox / "darkpool_ats.manifest.json")
    assert code is Code.DI_PAYLOAD_MISSING


def test_rows_mismatch(tmp_path):
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    _drop(inbox, tamper=lambda man, payload: man.update(rows=99))
    code, detail = verify_drop(inbox / "darkpool_ats.manifest.json")
    assert code is Code.DI_ROWS_MISMATCH
    assert detail["actual_rows"] == 2


def test_schema_mismatch(tmp_path):
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    _drop(inbox, tamper=lambda man, payload: man.update(
        schema=[{"symbol": "varchar"}, {"nonexistent_col": "double"}]))
    code, detail = verify_drop(inbox / "darkpool_ats.manifest.json")
    assert code is Code.DI_SCHEMA_MISMATCH
    assert detail["missing_columns"] == ["nonexistent_col"]


def test_manifest_invalid_json(tmp_path):
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    (inbox / "darkpool_ats.manifest.json").write_text("{nope",
                                                      encoding="utf-8")
    code, _ = verify_drop(inbox / "darkpool_ats.manifest.json")
    assert code is Code.DI_MANIFEST_INVALID


def test_manifest_name_must_match_filename(tmp_path):
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    _drop(inbox, tamper=lambda man, payload: man.update(name="renamed"))
    code, _ = verify_drop(inbox / "darkpool_ats.manifest.json")
    assert code is Code.DI_MANIFEST_INVALID


def test_torn_receipt_chain_refuses(tmp_path):
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    _drop(inbox)
    assert main(["--inbox", str(inbox)]) == 0
    receipts = inbox / "receipts.jsonl"
    receipts.write_text(receipts.read_text(encoding="utf-8").replace(
        '"rows": 2', '"rows": 3'), encoding="utf-8")  # tamper the body
    with pytest.raises(IntakeRefusal):
        verify_receipt_chain(receipts)
    assert main(["--inbox", str(inbox)]) == 2  # banner, no append


def test_empty_inbox_ok(tmp_path, capsys):
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    assert main(["--inbox", str(inbox)]) == 0
    assert "inbox empty" in capsys.readouterr().out


def test_parquet_payload(tmp_path):
    duckdb = pytest.importorskip("duckdb")  # optional analysis stack
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    pq = inbox / "darkpool_ats.parquet"
    con = duckdb.connect(":memory:")
    con.execute(f"COPY (SELECT * FROM (VALUES ('MSTR', 1000),"
                f" ('MSTR', 2000)) v(symbol, volume)) TO "
                f"'{str(pq).replace(chr(92), '/')}' (FORMAT parquet)")
    con.close()
    _drop(inbox, tamper=lambda man, payload: (
        man.update(content_sha256=hashlib.sha256(
            pq.read_bytes()).hexdigest(),
                   payload_file=pq.name),
        payload.unlink()))
    code, detail = verify_drop(inbox / "darkpool_ats.manifest.json")
    assert code is Code.DI_INTAKE_VERIFIED
    assert detail["rows"] == 2
