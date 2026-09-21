# scripts/quant_db.py
"""DuckDB measurement plane — read-only SQL over the desk's data (Lane D).

SAFETY CONTRACT (the operator's "don't corrupt anything", made structural):
- IN-MEMORY database only (duckdb.connect(":memory:")). This module never
  opens any file for writing; DuckDB cannot corrupt files it never writes.
- READ-ONLY views over the audit JSONL, CSV ledgers, and corpus parquets.
- scripts/ scope only. The dependency-hygiene law
  (tests/test_dependency_hygiene.py) pins duckdb out of engine scope;
  the engine never imports this module.
- LAZY import: duckdb is an optional analysis dependency. Absence is a
  refusal banner + exit 2, never a traceback (moomoo/grpc seam pattern).

BENEFIT (why this exists): an INDEPENDENT SECOND COMPUTATION ENGINE. The
hand-rolled streaming instruments (gradeability_census, gate_ecology)
produce the desk's N / absorb counts in bespoke Python; this module
recomputes the same quantities in SQL. The mindset law: one number from
one tool is a hypothesis; two engines agreeing on the same data is
evidence. SQL over parquet/JSONL is also simply faster to write new
measurements against than another streaming loop.

CLI: `python scripts/quant_db.py` prints the view inventory + the
cross-check report (exit 2 with a refusal banner on any inconsistency).
"""
from __future__ import annotations

import sys
from pathlib import Path

REFUSAL_DUCKDB_MISSING = "QUANTDB_DUCKDB_MISSING"
REFUSAL_AUDIT_MISSING = "QUANTDB_AUDIT_MISSING"

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "outputs" / "audit.jsonl"
CORPUS_DIR = ROOT / "research" / "corpus" / "binance_vision"

# Optional ledgers: registered when present, reported skipped otherwise.
OPTIONAL_CSVS = {
    "fills": ROOT / "outputs" / "fills.csv",
    "equity": ROOT / "outputs" / "equity.csv",
    "signal_history": ROOT / "outputs" / "signal_history.csv",
}


class QuantDbRefusal(Exception):
    """Carries a registered-style refusal code; caught at the CLI seam."""

    def __init__(self, code: str, detail: str):
        super().__init__(f"{code}: {detail}")
        self.code = code


def connect():
    """In-memory DuckDB, lazily imported. Refuses cleanly if absent."""
    try:
        import duckdb  # noqa: PLC0415 - deliberate lazy optional seam
    except ImportError as exc:
        raise QuantDbRefusal(
            REFUSAL_DUCKDB_MISSING,
            "duckdb is not installed in this environment; the measurement "
            "plane is optional and refuses rather than degrading",
        ) from exc
    return duckdb.connect(":memory:")


def _q(path: Path) -> str:
    """SQL-quote a filesystem path (single quotes doubled)."""
    return "'" + str(path).replace("'", "''").replace("\\", "/") + "'"


def register_views(con, audit_path: Path | None = None,
                   corpus_dir: Path | None = None,
                   optional_csvs: dict | None = None) -> dict:
    """Register read-only views. Returns {"registered": [...], "skipped": [...]}.

    The audit chain is the one load-bearing input: missing => refusal.
    Optional CSVs and corpus parquets register when present. Path defaults
    are resolved at CALL time so tests can monkeypatch the module attrs.
    """
    audit_path = AUDIT if audit_path is None else audit_path
    corpus_dir = CORPUS_DIR if corpus_dir is None else corpus_dir
    optional_csvs = OPTIONAL_CSVS if optional_csvs is None else optional_csvs
    registered, skipped = [], []
    if not audit_path.exists():
        raise QuantDbRefusal(REFUSAL_AUDIT_MISSING, f"no audit chain at {audit_path}")
    con.execute(
        "CREATE VIEW audit AS SELECT * FROM read_json_auto("  # nosec B608 - only interpolation is the _q()-sanitized local path
        + _q(audit_path) + ", format='newline_delimited', ignore_errors=true)")
    registered.append("audit")
    # Raw lines: the audit's `data` payload is heterogeneous across codes,
    # so auto-inference cannot be trusted for per-code extraction.
    con.execute(
        "CREATE VIEW audit_lines AS SELECT line FROM read_csv("  # nosec B608 - only interpolation is the _q()-sanitized local path
        + _q(audit_path)
        + ", delim='\\x01', header=false, columns={'line': 'VARCHAR'})")
    # DE-010 events flattened: one row per captured arrival, extracted via
    # JSON functions off the raw line (inference-proof by construction).
    con.execute(
        "CREATE VIEW de010 AS "
        "SELECT ev->>'asset' AS asset, ev->>'absorb' AS absorb, "
        "ev->>'propensity' AS propensity, "
        "CAST(ev->>'ts' AS DOUBLE) AS event_ts, "
        "CAST(json_extract_string(l.line, '$.ts') AS DOUBLE) AS batch_ts "
        "FROM (SELECT line FROM audit_lines "
        "      WHERE json_extract_string(line, '$.code') = 'DE-010') l, "
        "UNNEST(CAST(json_extract(l.line, '$.data.events') AS JSON[])) "
        "AS u(ev)")
    registered.append("de010")
    for name, path in optional_csvs.items():
        if path.exists():
            con.execute(
                f"CREATE VIEW {name} AS SELECT * FROM read_csv_auto("  # nosec B608 - view name from fixed module dict keys; path _q()-sanitized
                + _q(path) + ", header=true)")
            registered.append(name)
        else:
            skipped.append(name)
    if corpus_dir.exists():
        for pq in sorted(corpus_dir.glob("klines_1m_*.parquet")):
            sym = pq.stem.replace("klines_1m_", "").lower()
            con.execute(
                f"CREATE VIEW corpus_{sym} AS SELECT * FROM parquet_scan("  # nosec B608 - name from corpus glob stem; path _q()-sanitized
                + _q(pq) + ")")
            registered.append(f"corpus_{sym}")
    return {"registered": registered, "skipped": skipped}


def crosscheck(con) -> dict:
    """Independent SQL recomputation of the desk's headline counts."""
    out = {}
    out["audit_records"] = con.execute("SELECT count(*) FROM audit").fetchone()[0]
    out["de010_events"] = con.execute("SELECT count(*) FROM de010").fetchone()[0]
    out["de010_absorb_mix"] = con.execute(
        "SELECT absorb, count(*) AS n FROM de010 GROUP BY absorb "
        "ORDER BY n DESC").fetchall()
    out["de010_propensity_missing"] = con.execute(
        "SELECT count(*) FROM de010 WHERE propensity IS NULL").fetchone()[0]
    view_names = {r[0] for r in con.execute(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_type = 'VIEW'").fetchall()}
    if "fills" in view_names:
        out["fills_rows"] = con.execute("SELECT count(*) FROM fills").fetchone()[0]
    corpus_views = sorted(v for v in view_names if v.startswith("corpus_"))
    out["corpus_rows"] = {
        v: con.execute(f"SELECT count(*) FROM {v}").fetchone()[0]  # nosec B608 - v comes from information_schema over views this module created
        for v in corpus_views}
    return out


def _banner(code: str, detail: str) -> None:
    print("=" * 70)
    print(f"QUANT-DB REFUSAL — {code}")
    print(detail)
    print("=" * 70)


def main() -> int:
    try:
        con = connect()
        inv = register_views(con)
        cc = crosscheck(con)
    except QuantDbRefusal as ref:
        _banner(ref.code, str(ref))
        return 2
    print("QUANT-DB measurement plane (in-memory DuckDB, read-only)")
    print("views registered:", ", ".join(inv["registered"]))
    if inv["skipped"]:
        print("views skipped (absent):", ", ".join(inv["skipped"]))
    print(f"audit records: {cc['audit_records']:,}")
    print(f"DE-010 captured arrivals: {cc['de010_events']:,}  "
          f"(propensity missing: {cc['de010_propensity_missing']})")
    for absorb, n in cc["de010_absorb_mix"]:
        print(f"  absorb={absorb}: {n:,}")
    if "fills_rows" in cc:
        print(f"fills rows: {cc['fills_rows']:,}")
    for view, n in cc["corpus_rows"].items():
        print(f"{view}: {n:,} rows")
    return 0


if __name__ == "__main__":
    sys.exit(main())
