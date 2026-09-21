# scripts/intake_dataset.py
"""Dataset intake seam — verify research inbox drops, receipt on a hash chain.

Lane B (2026-09-21). Externally-authored datasets (e.g. the dark-pool
session's FINRA ATS exports) land in `research/corpus/inbox/` as a PAIR:
`<name>.manifest.json` + the payload file it describes. This script
verifies every pair against the manifest and appends the verdict to a
hash-chained receipt trail (`receipts.jsonl`, same chain construction as
core/audit.py:_h — sha256, first 16 hex, prev-linked).

MANIFEST (bus spec, docs/session-bus.md 2026-09-21) — one JSON object:
    name, version, content_sha256 (over the payload file), rows,
    schema [{col: dtype}] or {col: dtype}, time_range [first, last],
    source, ingested_at
  optional: grid_seconds (null if irregular), gaps, dupes, domain
    (passthrough, survives intact), payload_file (default: sibling
    `<name>.csv` or `<name>.parquet`).

VERIFIED checks: payload exists (DI-020), sha256 matches (DI-030),
counted rows == manifest rows (DI-040), declared columns all present
(DI-050). NOT verified (stated, not imputed): dtype fidelity, time_range
content, gap/dupe claims — those need a deeper profile pass, which is a
later lane. Verified drop => DI-000 receipt. Any failure => failure-code
receipt, report line, exit 2 after ALL drops are processed (one bad drop
never hides the verdicts of the rest).

SAFETY: verify + receipt only. Payloads are opened read-only and never
modified, moved, or promoted into any engine-visible path. Parquet row
counting uses the lazy optional duckdb seam (refusal, never traceback).
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.codes import Code  # noqa: E402 - after sys.path bootstrap

INBOX = ROOT / "research" / "corpus" / "inbox"

REFUSAL_RECEIPTS_TORN = "INTAKE_RECEIPTS_TORN"
REFUSAL_DUCKDB_MISSING = "INTAKE_DUCKDB_MISSING"

REQUIRED_FIELDS = {
    "name": str,
    "version": (str, int),
    "content_sha256": str,
    "rows": int,
    "schema": (list, dict),
    "time_range": list,
    "source": str,
    "ingested_at": str,
}


class IntakeRefusal(Exception):
    """Script-local refusal (census precedent): banner + exit 2."""

    def __init__(self, code: str, detail: str):
        super().__init__(f"{code}: {detail}")
        self.code = code


def _h(payload: str) -> str:
    # identical construction to core/audit.py:_h (sha256, first 16 hex).
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _iso(ts: float) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts))


def _sha256_file(path: Path) -> str:
    dig = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            dig.update(chunk)
    return dig.hexdigest()


def verify_receipt_chain(receipts_path: Path) -> list:
    """Read + verify the receipt chain. Torn chain => IntakeRefusal."""
    if not receipts_path.exists():
        return []
    records = []
    prev = "0" * 16
    for ln, line in enumerate(receipts_path.read_text(
            encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError as exc:
            raise IntakeRefusal(
                REFUSAL_RECEIPTS_TORN,
                f"{receipts_path}:{ln} unparsable: {exc}") from exc
        body = json.dumps({k: v for k, v in rec.items() if k != "h"},
                          sort_keys=True, default=str)
        if rec.get("prev") != prev or rec.get("h") != _h(body):
            raise IntakeRefusal(
                REFUSAL_RECEIPTS_TORN,
                f"{receipts_path}:{ln} chain break (seq {rec.get('seq')})")
        prev = rec["h"]
        records.append(rec)
    return records


def append_receipt(receipts_path: Path, code: Code, data: dict) -> dict:
    """Append one hash-chained receipt record. Returns the record."""
    records = verify_receipt_chain(receipts_path)
    prev = records[-1]["h"] if records else "0" * 16
    rec = {"seq": (records[-1]["seq"] + 1) if records else 1,
           "ts": time.time(), "src": "intake_dataset",
           "code": code.value, "data": data, "prev": prev}
    rec["h"] = _h(json.dumps(rec, sort_keys=True, default=str))
    receipts_path.parent.mkdir(parents=True, exist_ok=True)
    with receipts_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, sort_keys=True, default=str) + "\n")
    return rec


def _parquet_rows_and_columns(path: Path) -> tuple[int, list[str]]:
    try:
        import duckdb  # noqa: PLC0415 - deliberate lazy optional seam
    except ImportError as exc:
        raise IntakeRefusal(
            REFUSAL_DUCKDB_MISSING,
            "duckdb not installed; parquet payloads cannot be counted "
            "(csv payloads verify without it)") from exc
    q = "'" + str(path).replace("'", "''").replace("\\", "/") + "'"
    con = duckdb.connect(":memory:")
    try:
        rows = con.execute(
            "SELECT count(*) FROM parquet_scan(" + q + ")"  # nosec B608 - only interpolation is the sanitized local path
        ).fetchone()[0]
        cols = [r[0] for r in con.execute(
            "SELECT column_name FROM (DESCRIBE SELECT * FROM "  # nosec B608 - only interpolation is the sanitized local path
            "parquet_scan(" + q + "))").fetchall()]
    finally:
        con.close()
    return int(rows), cols


def _csv_rows_and_columns(path: Path) -> tuple[int, list[str]]:
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.reader(fh)
        header = next(reader, None) or []
        rows = sum(1 for _ in reader)
    return rows, header


def _declared_columns(schema) -> list[str]:
    if isinstance(schema, dict):
        return list(schema)
    cols = []
    for entry in schema:  # [{col: dtype}, ...]
        if isinstance(entry, dict) and entry:
            cols.extend(entry.keys())
    return cols


def verify_drop(manifest_path: Path) -> tuple[Code, dict]:
    """Verify one manifest+payload pair. Returns (receipt code, detail)."""
    try:
        man = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        return Code.DI_MANIFEST_INVALID, {
            "manifest": manifest_path.name, "error": str(exc)}
    if not isinstance(man, dict):
        return Code.DI_MANIFEST_INVALID, {
            "manifest": manifest_path.name, "error": "manifest is not an object"}
    bad = [k for k, t in REQUIRED_FIELDS.items()
           if k not in man or not isinstance(man[k], t)]
    if bad:
        return Code.DI_MANIFEST_INVALID, {
            "manifest": manifest_path.name,
            "error": f"missing/mistyped required fields: {bad}"}
    name = man["name"]
    if name != manifest_path.name[: -len(".manifest.json")]:
        return Code.DI_MANIFEST_INVALID, {
            "manifest": manifest_path.name,
            "error": f"name {name!r} does not match manifest filename stem"}
    payload = (Path(man["payload_file"]) if man.get("payload_file")
               else None)
    if payload is None:
        for ext in (".csv", ".parquet"):
            cand = manifest_path.parent / f"{name}{ext}"
            if cand.exists():
                payload = cand
                break
        else:
            return Code.DI_PAYLOAD_MISSING, {
                "name": name,
                "error": f"no payload_file field and no sibling {name}.csv/"
                         f"{name}.parquet"}
    elif not payload.is_absolute():
        payload = manifest_path.parent / payload
    if not payload.exists():
        return Code.DI_PAYLOAD_MISSING, {"name": name,
                                         "error": f"{payload} not found"}
    sha = _sha256_file(payload)
    if sha != man["content_sha256"]:
        return Code.DI_HASH_MISMATCH, {
            "name": name, "manifest_sha256": man["content_sha256"],
            "actual_sha256": sha}
    if payload.suffix == ".parquet":
        rows, cols = _parquet_rows_and_columns(payload)
    else:
        rows, cols = _csv_rows_and_columns(payload)
    if rows != man["rows"]:
        return Code.DI_ROWS_MISMATCH, {
            "name": name, "manifest_rows": man["rows"], "actual_rows": rows}
    declared = _declared_columns(man["schema"])
    missing = [c for c in declared if c not in cols]
    if missing:
        return Code.DI_SCHEMA_MISMATCH, {
            "name": name, "missing_columns": missing,
            "payload_columns": cols}
    return Code.DI_INTAKE_VERIFIED, {
        "name": name, "version": man["version"], "rows": rows,
        "content_sha256": sha, "payload": payload.name,
        "checks": ["sha256", "rows", "columns"],
        "not_verified": ["dtype fidelity", "time_range", "gaps/dupes"],
        "source": man["source"], "ingested_at": man["ingested_at"],
        "time_range": man["time_range"],
        "grid_seconds": man.get("grid_seconds"),
        "domain": man.get("domain")}


def _banner(code: str, detail: str) -> None:
    print("=" * 70)
    print(f"INTAKE REFUSAL — {code}")
    print(detail)
    print("=" * 70)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--inbox", default=str(INBOX))
    ns = ap.parse_args(argv)
    inbox = Path(ns.inbox)
    receipts = inbox / "receipts.jsonl"
    try:
        verify_receipt_chain(receipts)  # refuse before appending to a torn chain
        manifests = sorted(inbox.glob("*.manifest.json")) \
            if inbox.exists() else []
        failures = 0
        if not manifests:
            print(f"INTAKE: inbox empty ({inbox})")
            return 0
        for mp in manifests:
            code, detail = verify_drop(mp)
            rec = append_receipt(receipts, code, detail)
            ok = code is Code.DI_INTAKE_VERIFIED
            failures += 0 if ok else 1
            mark = "VERIFIED" if ok else "FAILED"
            print(f"{mark} {code.value} seq={rec['seq']} "
                  f"{detail.get('name', mp.name)}: "
                  + (f"rows={detail['rows']} sha={detail['content_sha256'][:12]}…"
                     if ok else detail.get("error", "")))
        print(f"receipts: {receipts}")
        if failures:
            print(f"INTAKE: {failures}/{len(manifests)} drop(s) FAILED")
            return 2
        return 0
    except IntakeRefusal as ref:
        _banner(ref.code, str(ref))
        return 2


if __name__ == "__main__":
    sys.exit(main())
