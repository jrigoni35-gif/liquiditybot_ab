# Desk instruments build — design spec (2026-09-19, SAFE-plane)

Approved by operator 2026-09-19 eve. Builds the five seams' remaining
instruments plus the five beyond-the-seams instruments as ONE program,
in dependency order. Umbrella context: `docs/quant/2026-09-19_institutional_integration.md`
(seams + instruments + fences). This spec is the implementation-level
contract; that doc is the architecture.

## Law and fences (binding, restated)

- Era-9 is accruing (n=40/50 at design time; adjudication 09-22). Every
  lane here is measurement/logging/reporting. Nothing in this program
  feeds decisioning.
- Cohort-resetting list applies in full: no entry decisioning, sizing,
  stop/exit geometry, fill simulator, fee booking, order lifecycle,
  universe, hedger, probe ticket, or heat cap change. Any live use of
  anything these lanes produce is boundary-only.
- Invariant 6: every new audit record or refusal gets a registered code
  in `core/codes.py` — never a bare string.
- Oracle/IS numbers are direction, never capturable targets: they ignore
  the 79% non-fill rate and the trail overlay.
- Every new instrument ships with a negative arm or self-test where it
  judges (instrument_contract C2). EN-030-style aggregate-only shortcuts
  are the failure mode Lane 0/A exist to end; no lane may emit an
  unreconciled total.

## Units

| # | Unit | Kind | Reads | Writes |
|---|------|------|-------|--------|
| 0 | `scripts/gradeability_census.py` | report | audit JSONL chain, fills.csv | dated census doc + DE-010 field spec |
| A1 | DE-010 emission at the entry sweep (`main.py:1940` region) | engine log (SAFE) | values already in sweep scope | `DE-010 decision_event` audit records |
| A2 | `book` stamp on fills (`core/fill_ledger.py:239-249`) | engine log (SAFE half of long-book docket row) | desk context at fill time | `fills.csv.book` populated |
| B | `scripts/is_ledger.py` + `scripts/attribution.py` | report | DE-010 events, fills, markout, corpus | IS tables, attribution tables |
| C | benchmark-mid module + report join | report | OKX/Binance.US read-only history, DE-010 | benchmarked execution/delay legs |
| D | `scripts/stress_replay.py` | report | corpus crash windows, inventory rules | drawdown/ES/time-underwater doc |
| E | `scripts/treasury_report.py` | report | equity.csv, fills, fee schedule | idle-cash drag, tier position, mix cost |

## Lane 0 — the hole, measured precisely (builds first)

Walk era-9's full audit chain and decompose the decision population
into three classes, each with named sub-reasons:

- **gradeable** — has decision price and outcome.
- **retro-gradeable** — no explicit record, but the decision mid is
  reconstructable from adjacent records (sub-reason per reconstruction
  path).
- **lost** — unrecoverable (sub-reason per cause).

Hard requirements:

1. Class totals reconcile exactly to the era decision population; an
   unreconciled census is a failed census.
2. The census REFUSES (registered code) on an unreadable/torn chain —
   never emits a partial count.
3. Second output: the **DE-010 field list** — exactly the fields that
   would have made each lost sub-population gradeable. The census
   writes the schema; A1 implements it. No field is added to DE-010
   that the census did not derive, and no derived field is dropped
   without a named reason in the census doc.
4. Deliverable: a dated `docs/quant/` census record (dated the day it
   runs) with the decomposition, the sub-reason tables, and the field
   list, plus a one-line HANDOFF router row.

## Lane A — capture (engine touches, additive only)

- **A1**: one `DE-010 decision_event` audit record per sweep arrival,
  emitted beside the existing EN-000 vector at the entry sweep. Fields:
  the census-derived list (the architecture doc seeds `asset, ts,
  decision_mid, gates_digest`; the census confirms or extends that seed
  — a seed field the census does not confirm is dropped with a named
  reason in the census doc). No gate behavior changes;
  the record serializes what the sweep already computed. Registered
  code `DE-010` in `core/codes.py`. Unit pin: a synthetic sweep emits
  exactly one record per arrival, byte-stable shape.
- **A2**: the fills writer populates `book` (5m book / long book /
  hedger) from desk context at fill time. No schema addition — the
  column exists; the writer starts filling it. Unit pin: a synthetic
  fill per desk stamps the right book; historical rows stay untouched.

## Lane B — TCA desk (consumes A)

- `scripts/is_ledger.py`: per decision event, implementation shortfall
  decomposed as explicit (`fees_delta_usd`) / execution (`slip_bps` +
  MarkoutTracker curves) / delay (decision_mid → arrival → fill) /
  opportunity (oracle grader over unfilled/refused events, promoted
  from `outputs/reports/oracle_regret_2026-09-19.py`). Output: per-era
  IS table cut by asset × lane × regime, dated doc.
- `scripts/attribution.py`: net, fees, heat-hours by asset × book ×
  lane (requires A2); oracle-vs-held inventory mix; the netting report
  (hedger burned $313.51 = 80.5% of lifetime fees, 09-01 measurement —
  price what internal netting across the three desks would have saved
  on our own ledger).

## Lane C — benchmark TCA (consumes A; benchmark chosen from data)

- Step 1 is a **feed-availability census**: which of OKX / Binance.US
  carries our pairs, at what uptime and staleness, over era-9's window.
  The benchmark rule (single venue or best-of-both per timestamp) is
  derived from that census and recorded in its doc — no venue
  assumption baked in (operator decision 2026-09-19 eve).
- Step 2: report-plane join stamping the benchmark mid onto DE-010
  events and fills, so IS execution/delay legs read "Kraken vs
  consolidated mid". Feed gaps stamp `UNAVAILABLE`; never fabricated.

## Lane D — stress replay (independent)

Replay current inventory/heat rules over corpus crash windows
(corpus local: 2024-01→2026-09, 1m, BTC/ETH/LINK/PAXG). Windows are
enumerated in the implementation plan by corpus drawdown ranking — the
top measured drawdown windows per asset plus the 2024-08-05-style
market-wide unwind — never hand-picked after seeing results. Report
drawdown, expected shortfall, time-underwater per window, dated doc.
Rules are read, not modified; any rule change the replay argues for is
boundary docket material.

## Lane E — treasury desk (independent)

`scripts/treasury_report.py`: idle-cash drag per era (cash share vs
deployed), Kraken volume-tier position (30d maker volume vs next fee
boundary), fiat/stablecoin mix cost. Report-plane; acting on it is
boundary (sizing/universe).

## Data flow

`audit chain + fills.csv + corpus + read-only feed history → scripts →
dated docs/quant records → one-line HANDOFF router rows`. Scripts never
write into engine paths. A1/A2 are the only engine touches, both
additive logging beside existing emission points.

## Error handling

Every script refuses with a registered code on unreadable input.
Corpus gaps are reported, never interpolated. Feed gaps stamp
`UNAVAILABLE`. Reconciliation totals are the non-vacuity pins.

## Testing and definition of done

Per lane: unit tests on synthetic fixtures plus a reconciliation pin
against the real era-9 chain where applicable. Full DoD matrix on every
code-touching lane: `python -m pytest tests/ -q`,
`python scripts/smoke_test.py`, `python scripts/assurance_check.py`,
`python scripts/overfit_check.py` (OF-3 pbo 0.69 / OF-5 DSR 0.006 are
the documented guarded reds — untouched by this program),
`ruff check …` (law-listed scope), `pyright …` (zero-error ratchet),
`bandit -c pyproject.toml -r . -x ./.venv,./tests,./outputs`,
`python -m compileall -q . -x '(\.venv|\.claude)'`. Docs lanes get the
era-currency gate (`tests/test_docs_era_currency.py`).

## Land order

**0 → A1+A2 → B ∥ C → D ∥ E**, one commit per lane (A1/A2 may share a
lane commit as two pins). Findings contributed as dated `docs/quant/`
records + HANDOFF one-liners as each lane lands. Program ends with a
closing census re-run proving the hole does not regrow under DE-010.
