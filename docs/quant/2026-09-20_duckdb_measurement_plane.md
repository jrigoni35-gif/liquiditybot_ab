# DuckDB measurement plane (Lane D) — 2026-09-20

**What shipped:** `scripts/quant_db.py` (+ `tests/test_quant_db.py`, 7 tests) —
a read-only SQL layer over the desk's data, in `scripts/` scope, lazy-imported,
in-memory only. Operator directive 2026-09-20 21:03: "add duckdb to the bot,
but make sure it doesn't corrupt anything. It needs to be beneficial."

## Safety contract (non-corruption is structural, not promised)

1. **In-memory database only** (`duckdb.connect(":memory:")`) — the module
   never opens any file for writing. DuckDB cannot corrupt files it never
   writes.
2. **Read-only views** over `outputs/audit.jsonl`, CSV ledgers, and the
   corpus parquets. No state file, no engine file, no config is touched.
3. **scripts/ scope only** — the dependency-hygiene law
   (`tests/test_dependency_hygiene.py`, FORBIDDEN tuple) pins duckdb out of
   engine scope; the engine never imports this module. Engine-side DuckDB
   (state stores, decision paths) would be a **boundary adjudication item**,
   not a session change.
4. **Lazy optional seam** — duckdb absent ⇒ refusal banner + exit 2
   (`QUANTDB_DUCKDB_MISSING`), never a traceback. Test collection works
   without the analysis stack (`importorskip` per the hygiene law).

Refusal family: `QUANTDB_DUCKDB_MISSING`, `QUANTDB_AUDIT_MISSING`.

## Benefit #1 (the reason it exists): independent second engine

The mindset law: one number from one tool is a hypothesis. The desk's
headline counts were computed by ONE hand-rolled streaming engine. quant_db
recomputes them in SQL. First cross-check, run same-minute 2026-09-21T02:12–02:13Z:

| quantity | hand-rolled (`gate_ecology.py`) | DuckDB (`quant_db.py`) | verdict |
|---|---|---|---|
| DE-010 captured arrivals | 9,012 | 9,012 | **exact** |
| absorb = EN-030 | 6,739 | 6,739 | **exact** |
| absorb = passed_gate_stack | 2,273 | 2,273 | **exact** |
| propensity missing | (not computed) | **0** | key holds on all 9,012 |

Two independent engines, exact agreement on the live chain. The streaming
instruments' extraction logic is corroborated, and the propensity key is
verified present on every captured arrival by a second reader.

Context numbers (as-of 02:13Z): audit records 90,111; arrivals N=89,032
(457.5/h); DE-010 absorb mix EN-030 6,739 / passed 2,273 = **74.8% absorbed
among captured** (era rate 77.76%); corpus views 4 × 1,429,920 rows.

## Benefit #2: SQL-speed measurement

New questions against the audit chain / fills / equity / corpus no longer
need a bespoke streaming loop:

```sql
-- hourly capture rate by absorb class, one query
SELECT date_trunc('hour', to_timestamp(batch_ts)) AS h, absorb, count(*)
FROM de010 GROUP BY 1, 2 ORDER BY 1;
```

View inventory: `audit`, `audit_lines`, `de010` (flattened per-arrival),
`fills`, `equity`, `signal_history` (when present), `corpus_<symbol>` ×4.

## Implementation notes

- `audit_lines` + JSON extraction: the audit's `data` payload is
  heterogeneous across codes, so `read_json_auto` schema inference cannot be
  trusted for per-code extraction (real-data BinderException caught by
  `test_main_exit_codes`); the `de010` view extracts off raw lines instead —
  inference-proof by construction.
- Path defaults resolve at call time (monkeypatchable; the first draft's
  def-time binding let a test hit the real 90k-record chain — pinned fixed).

## Boundary

SAFE class under the era-9 moratorium: measurement tooling, no cohort
surface. Nothing here changes which orders are placed or how they fill.
