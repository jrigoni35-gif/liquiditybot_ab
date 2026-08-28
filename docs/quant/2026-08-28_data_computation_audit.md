# Data-computation audit — what we exploit, what the wall is, ranked upgrades

Operator questions (2026-08-28): "what are we taking advantage of when it
comes to data computation within the code and where can we improve? …cleaner
and faster… full span of out-of-the-box ideas… load-bearing analysis."

All timings measured this session on the live box (Ryzen, Windows 11, repo
venv, Python 3.14), snapshot 2026-08-28T22:2xZ; benchmark script inline in
session scratchpad `era8_replay.py` + the timing block below. Helpers
installed under standing auto-install approval: polars 1.44.1, orjson,
duckdb 1.5.5 (venv-only; nothing in engine imports them yet).

## 1. What the code already exploits (verified, with receipts)

- **Deterministic step-able engine**: `cycle_once(now)` under injected feeds
  — the entire replay/backtest/battery lane exists because decisions are a
  pure function of fed data. This is the single biggest computational asset.
- **Append-only durable corpus with write-time semantics**: schema-versioned
  CSV, era + control-arm tagged at write, UNKNOWN-as-'' convention,
  durable_append, checksummed snapshots. Rows never need migration to be
  interpretable (the schema-94 magnitude rescue proved why).
- **Hash-chained audit** — every disposition, immutable, replayable.
- **Effective-n machinery** (`gate_truth_report`, `cohort_eval`) — the
  statistics correct for overlap instead of lying with nominal n.
- **Batched venue I/O**: batched ticker won a measured 1.6s/cycle; parallel
  book fetches won 0 (venue rate limit is the wall).
- **The measured constraint that frames everything**: the live cycle is
  ~95% I/O wait, and 83–86% of REST latency is venue-side. **Engine-side
  compute is NOT the bottleneck** — CPU optimizations aimed at the cycle
  loop are optimizing the 5%.

## 2. Measured hot spots (this box, this corpus, 2026-08-28)

| workload | stdlib today | fast lane | factor |
|---|---|---|---|
| corpus parse (19,081×93 CSV, 15.3MB) | 394ms (csv) / 175ms (pandas) | **32ms polars** | 12× |
| era-8 replay aggregation (full corpus) | ~2,400ms row loop | **66ms polars exprs** | 36× |
| parquet mirror read (same data, 4.4MB) | — | **16ms** | 25× vs csv |
| audit.jsonl tail-20k parse (24MB file) | 99ms | 31ms orjson | 3× |
| status.json serialize (32KB) | 0.30ms | 0.06ms orjson | 5.5× — **but trivial per cycle; not load-bearing for the engine** |

Structural finding: **42 files contain a bespoke CSV/DictReader** of the
corpus or its siblings. Every one re-implements type coercion, era
filtering, and UNKNOWN handling — and the era-confound defect class lived in
exactly one such bespoke reader. The fragmentation is a correctness surface,
not just a speed cost.

## 3. Ranked improvements (leverage × correctness, honest about class)

**R1 — canonical corpus accessor (TOP; SAFE).** One module (e.g.
`ml/corpus.py`) exposing the typed polars read (guarded import, stdlib
fallback per import-integrity law), era filters, UNKNOWN semantics, side-
adjusted gross return, true-cost relabel hooks. The 42 readers converge on
it over time. Kills the defect class where era-mixing regrows; 12–36× on
every report/retrain/battery load as a side effect. This is the "cleaner
AND faster" answer — same change.

**R2 — parquet mirror at the write path (SAFE).** 47ms to write, 16ms to
read, 3.5× smaller. CSV stays canonical (append-durability is its job);
mirror refreshes on the write path only — the 2026-07-11 lesson forbids any
init-time rewrite. Consumers that want speed read the mirror through R1.

**R3 — vectorize the measurement lane (SAFE; measurement owed).** The
replay/battery/quant-trials row loops are the workloads that run thousands
of configurations (QT-1 re-baseline is 200×1200). 36× on aggregation turns
hour-scale sweeps into minutes. Owed before building: profile
`quant_trials.py` to confirm it is loop-bound, not sim-bound.

**R4 — duckdb over the mirror for ad-hoc/report SQL (SAFE, optional).**
Gate/cohort reports become auditable SQL against parquet; 576ms CSV-scan
today collapses to ~10ms-scale on the mirror. Adopt opportunistically.

**R5 — orjson in bulk lanes only (SAFE, marginal).** Guarded swap in
digest/report tools that parse audit tails (3×). NOT in the engine status
writer — 0.3ms/cycle is noise against a 4s I/O-bound cycle; claiming it as
a win would be exactly the vacuous optimization this doc exists to prevent.

**R6 — websocket feed enablement (GATED — operator adjudication).** The
only lever that touches the real wall (venue-side REST latency).
`data/ws_feed.py` is built, staleness-gated, ships disabled. Changes what
data feeds decisions → cohort-resetting question, pre-named for the docket,
not a computation tweak.

**R7 — Defender exclusion for `outputs/` (operator, elevated; hypothesis).**
Windows real-time AV taxes hot small-file I/O; unmeasured here. Measure
first (procmon or timed A/B with exclusion), only then decide — goes to the
elevated-signoff list, not into code.

## 4. Fences

- Engine imports of polars/orjson/duckdb must be guarded-optional
  (`tests/test_import_integrity.py` law: our names import everywhere,
  third-party may be absent). They stay out of `requirements.txt` until an
  engine path depends on one.
- R1/R2 change NOTHING about which orders are placed or fill — SAFE class —
  but the accessor's era/UNKNOWN semantics must be pinned by tests in the
  same commit (a wrong shared reader is a shared wrong answer; the
  instrument is the first suspect).
- No number in this doc is current after today — re-run the benchmark
  block; the corpus grows ~400–700 rows/day.

## 5. What this audit could not see

Retrain-loop wall-clock share of corpus load (not profiled end-to-end);
Defender I/O tax (unmeasured hypothesis); GPU lanes (no CUDA on this box —
not evaluated); the sim inner loop's own profile (R3's owed measurement).
