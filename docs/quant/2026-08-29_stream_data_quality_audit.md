# Stream Data-Quality Audit — signal_history.csv as a non-terminating stream

**Class:** SAFE (reads corpus, writes this doc; no code/config/decision change).
**HEAD:** `122bf8bf` · **Interpreter:** `./.venv/Scripts/python.exe` ·
**Instrument:** `ml.corpus` (the refined canonical accessor) + inline scratchpad
(not committed).
**Framework:** data-quality-auditor DQS dimensions, applied *corpus-aware* per the
READER-TRAPS/era semantics in `ml/history.py` and `ml/corpus.py`.

**Snapshot stamp (the file is mutating — all values are AS-OF):**
`outputs/signal_history.csv` mtime `2026-08-29T20:00:30Z` (15,512,065 bytes),
read at `2026-08-29T20:20:23Z`. **19,343 data rows**, 95 columns.
- Row count double-derived [K]: `wc -l` = 19,344 lines − 1 header = 19,343;
  `csv.DictReader` count = 19,343. Agree.
- Live runner is appending (mtime is ~20 min before read); a re-run past
  20:00:30Z will show more rows. The stream is exactly what this audit treats
  it as: non-terminating.

---

## Bottom Line

**Finite-sample DQS: 95/100 🟢 — the dataset is clean.** Validity, uniqueness
and timeliness are effectively perfect; every "" is honest UNKNOWN, not a silent
null. A generic profiler would stop here and call it production-ready.

**Streaming verdict: the stream CANNOT currently yield precise per-execution-style
probabilities. 🔴** The clean-dataset score is the wrong question, and answering
only it is the trap this repo's mindset file names ("the instrument is the first
suspect"). Three structural facts, none of them a dirtiness defect, defeat precise
per-style estimation:

1. **Effective-n collapse (~270×).** The recoverable gross-return corpus is
   dominated by massively overlapping label windows. The edge-bearing era
   (`triple_barrier_h432`, n=8,988) carries **n_eff ≈ 33** [K, double-derived].
   Every per-style cut lands at **n_eff 3–72**, never thousands. A win-rate CI
   computed on nominal n is optimistic by `sqrt(n/n_eff)` — **16.5×** for h432.
2. **The gross edge lives in ONE 20.8-day era, and it is beta-confounded.** 90.8%
   of recoverable rows are `h432`; its cumulative log-return slope is positive but
   **not stationary** — it flips sign quarter-to-quarter (Q2 +0.0062/trip melt-up,
   Q3 −0.0021/trip pullback). The strong "long +24.8 cumlog / short −11.2" split is
   market drift leaking into unhedged directional *simulated* labels, not a
   tradeable per-style probability.
3. **The live execution styles the operator most wants are barely observable.**
   `probe` is 98.4% UNKNOWN (289 probe / 26 conviction live rows); live rows are
   **0/376 recoverable on the gross/log scale** (exit_price = 0.0 by construction);
   and **maker/taker is not in the corpus at all** (`post_only` lives in fills, not
   `signal_history.csv`).

**One-line verdict:** clean data, wrong shape — the stream is stationary in
*format quality* but non-stationary in *label era, schema coverage, and market
path*, and its concurrency deflation leaves 15–70 independent observations per
style, so per-style probabilities are **noise, not precision**, today.

---

## What (findings, ranked severity × breadth, confidence-tagged)

### F1 — Effective-n collapse dominates every per-style estimate. 🔴 HIGH × corpus-wide. Confidence 🟢
Nominal row counts are 1–2 orders of magnitude larger than the independent-sample
count. Computed as within-stratum mean-uniqueness over `[signal_ts, ts]` label
windows (Lopez de Prado), `n_eff = n · mean_uniqueness` — the same deflation
`scripts/cohort_eval.py` (since 2026-08-15) and `scripts/gate_truth_report.py`
(since 2026-07-29) already apply, and the same standard that read era-4 at
n_eff 9.92.

Double-derived for the edge-bearing era [K]: uniqueness-integral route
n_eff = **33.0**; independent crude route `n / time-avg-concurrency` =
8,988 / 230.5 = **39.0**. Agree at order. Time-avg concurrency **230.5**, sampled
peak **692** — on average ~230 label windows are open simultaneously (36-hour
horizon × ~450 candidates/day × 15 assets).

| effect | h432 era | per-side (long) | per-regime (crisis) |
|---|---|---|---|
| nominal n | 8,988 | 6,095 | 2,187 |
| n_eff [K] | 33.0 | 42.7 | 14.8 |
| nominal-Wilson optimism `sqrt(n/n_eff)` [I] | 16.5× | 11.9× | 12.2× |

**The instrument-first reading:** a per-style win-rate interval that looks tight
(e.g. crisis 0.528 [0.507, 0.549] on nominal n) is a claim about the *nominal
counter*, not the market. At n_eff 14.8 the honest interval is ~12× wider and
straddles 0.5.

### F2 — Recoverable gross edge is one era, and it is beta-confounded, not stationary. 🔴 HIGH × the whole edge story. Confidence 🟢
Gross-return recoverability (`entry_price>0 & exit_price>0`, the `ml.corpus`
route) by source [K]:
- candidate **9,903 / 18,967** (52.2%); of these **8,988 are h432** (90.8%) and
  915 are `triple_barrier`; **0** for `exit_sim` / `legacy` / `exit_sim_time_stop`
  (those eras predate the 2026-08-04 entry/exit columns).
- live **0 / 376** (exit_price = 0.0 on every live row — the exit≤0 hole the
  accessor now guards at `122bf8bf`).

Per-side log-scale cumulative edge, candidate, ordered by ts [K]:
- **long** n=6,095 (n_eff 42.7) win 55.3%, mean gross +0.437%, **log-slope
  +0.736%/trip, R²=0.749, cumlog +24.81**
- **short** n=3,808 (n_eff 37.4) win 38.3%, mean gross −0.319%, **log-slope
  −0.624%/trip, R²=0.718, cumlog −11.17**

That is a straight, high-R² positive slope for longs and a straight negative slope
for shorts — the exact "persistent edge on the log scale" pattern the operator
asked to surface. **But it is not alpha.** h432 by ts-quartile [K]:

| quartile | window | win% | mean gross% | mean log/trip |
|---|---|---|---|---|
| Q1 | 08-12..08-19 | 45.8 | +0.092 | +0.00086 |
| Q2 | 08-19..08-23 | 58.0 | +0.645 | +0.00623 |
| Q3 | 08-23..08-26 | 41.3 | −0.203 | −0.00207 |
| Q4 | 08-26..08-29 | 50.8 | +0.108 | +0.00103 |

The mean log-return **changes sign** across quartiles. The overall positive slope
is carried by Q2 — the 08-19..08-23 melt-up (BTC/ETH +11%/+20%, the operator-
adjudicated outlier of 2026-08-20). The directional split is the market path
printed onto unhedged simulated candidate labels, gross of costs. **A reader who
ships "long edge, R²=0.75" gets the sign that was true for one week.** (the-method
rule 6: the market being boring — a directional drift — is the explanation the
record keeps vindicating.)

### F3 — Live execution styles are near-unobservable; maker/taker is absent. 🟠 HIGH × the operator's primary ask. Confidence 🟢
- `probe`: **98.37% blank** [K] (19,028/19,343); populated only 289 `1` + 26 `0`.
  Matches the operator's "note 98% UNKNOWN".
- probe vs conviction can only be scored on live realized `net_pnl_usd` (booked,
  understated fees), because live rows are 0/376 gross-recoverable:
  - probe n=289 win 15.6% [0.118, 0.202] sum −$41.38 mean −$0.143
  - conviction n=26 win 30.8% [0.165, 0.500] sum −$14.18 mean −$0.545
  - Both net-negative; conviction n=26 is too small to compare. Consistent with
    WHY-1 ("probes are tuition"), but not independently precise here.
- **maker vs taker is unestimable from this corpus** [K]: there is no `post_only`
  (or any maker/taker) column in the 95-column header. That style lives in the
  fills ledger, not `signal_history.csv`. The generic-profiler assumption that the
  requested stratifier exists in the file is false.
- THALES detectors barely fire on recoverable candidates [K]: `th_metronome` n=4
  (n_eff 3.1), `th_clockwork` n=86 (n_eff 22.3). Per-detector probabilities are
  unestimable for those two; `th_stopzone` (n_eff 36.7) and `<none active>`
  (n_eff 41.2) both sit at ~49% — no separation at their effective-n.

### F4 — The process is non-stationary in schema and era, not just market. 🟠 MEDIUM × corpus-wide. Confidence 🟢
Full-range weekly scan (onset claims are full-range, not tail-sampled) [K]:

| week | start | rows | blank-disp% | avail-blank% | cand-win% | mean-g% | dominant era |
|---|---|---|---|---|---|---|---|
| 0 | 07-13 | 2,016 | 100.0 | 100.0 | — | — | legacy (1,781) |
| 1 | 07-20 | 3,235 | 3.6 | 100.0 | — | — | exit_sim (2,459) |
| 2 | 07-27 | 3,975 | 0.0 | 100.0 | — | — | triple_barrier (3,958) |
| 3 | 08-03 | 785 | 0.0 | 100.0 | 49.1 | +0.077 | triple_barrier (777) |
| 4 | 08-10 | 851 | 0.0 | 45.2 | 36.8 | −0.342 | h432 (560) |
| 5 | 08-17 | 5,157 | 0.0 | 0.0 | 51.1 | +0.298 | h432 (5,145) |
| 6 | 08-24 | 3,324 | 0.0 | 0.0 | 48.1 | +0.047 | h432 (3,314) |

Column onsets, full-range first meaningful ts [K]: `entry_price`/`exit_price`
2026-08-04, `avail_web` 2026-08-13, `label_ret_pct` 2026-08-25, `control_arm`
2026-08-28 (cut #8, matches HANDOFF). `label_era` present on all rows (derived at
write). **The dominant non-stationarity is observability**, not feed degradation:
UNKNOWN rates fall over time (avail 100%→45%→0% is a rollout completing), so old
rows are structurally missing columns newer decisioning relies on. A series that
crosses any of these onsets is not one series (the-method rule 7c).

`label_ret_pct` is 87.6% blank and populated only for h432 candidates (2,377/8,988)
plus 15 live — it is **not** a corpus-wide outcome column; the `ml.corpus`
entry/exit gross route is the wider and correct instrument (9,903 rows).

### F5 — Where the finite-sample DQS is genuinely high (the clean part). 🟢 confirms the data is not dirty
- **Validity 20/20** [K]: every READER-TRAPS domain clean, 0 out-of-bounds —
  `sigma_bar_pct` max 1.53 ∈ [0,5]; `vol_percentile`/`drawdown_pct`/`turbulence_pct`
  ∈ [0,1] (turbulence max 0.984, the pinned ceiling); `spread_bps` max 6.0
  (=clip 60/10); `fv_edge_bps` ∈ [−5,5]; `direction` pure ±1. **Regime one-hot
  sums to exactly 1.0 on all 19,343 rows, zero fractional cells** — validates the
  hard-one-hot trap and refutes the earlier session mis-probe that read
  "0.000000" as active.
- **Uniqueness 15/15** (row-level) [K]: 19,343 distinct `position_id`, 0
  duplicates, 0 blank ids, 0 exact full-row duplicates. (Statistical uniqueness is
  F1 — a different axis.)
- **Timeliness 9.5/10** [K]: freshest row ~20 min before read; 47.3-day span
  (2026-07-13T12:35:47Z .. 2026-08-29T20:00:30Z); `signal_ts > ts` = 0 (no causal
  violations); 0 future ts; 16 non-monotone ts steps in row order (benign
  candidate/live append interleaving, not corruption).
- **Consistency 24/25** and **Completeness 27/30** (honest-UNKNOWN interpretation;
  the deductions are the outcome-column coverage F2/F3/F4 describe, not dirtiness).

`control_arm` accrual is live and clean [K]: 686 tagged rows (657 `0` + 29 `1`),
arm rate 29/686 = 4.2% (within noise of the 5% target for 686 draws), 18,657
legacy blanks correctly UNKNOWN not fabricated 0.

---

## Per-style convergence table (the operator's core deliverable)

Candidate rows, gross via entry/exit, ordered by ts. `n_eff` = within-stratum
concurrency uniqueness. **Convergence read** = whether the estimate is precise
(clears its own n_eff-honest interval) or noise. All [K] unless tagged.

| style | group | n | n_eff | win% | log-slope/trip | R² | cumlog | convergence read |
|---|---|---|---|---|---|---|---|---|
| era | h432 | 8,988 | 33.0 | 49.0 | +0.214% | 0.53 | +13.6 | **noise** — slope is Q2 melt-up, not stationary |
| era | triple_barrier | 915 | 9.3 | 46.7 | +0.072% | 0.28 | +0.04 | noise (n_eff 9) |
| side | long | 6,095 | 42.7 | 55.3 | +0.736% | 0.75 | +24.8 | straight slope but **beta-confounded**, not per-style |
| side | short | 3,808 | 37.4 | 38.3 | −0.624% | 0.72 | −11.2 | mirror of long — same confound |
| regime | crisis | 2,187 | 14.8 | 52.8 | +0.429% | 0.54 | +6.1 | noise; nominal CI 12× too tight |
| regime | bear | 3,093 | 45.4 | 49.0 | +0.257% | 0.62 | +6.5 | noise |
| regime | range | 2,124 | 36.8 | 47.6 | +0.012% | 0.01 | +1.4 | no edge |
| regime | bull_quiet | 1,329 | 27.5 | 42.9 | +0.046% | 0.03 | −1.1 | no edge |
| regime | bull_vol | 1,170 | 19.7 | 49.3 | +0.092% | 0.49 | +0.8 | noise |
| THALES | th_stopzone | 3,196 | 36.7 | 49.1 | +0.197% | 0.58 | +5.4 | at baseline |
| THALES | th_grid | 1,105 | 61.4 | 45.4 | +0.143% | 0.31 | +0.7 | at baseline |
| THALES | th_clockwork | 86 | 22.3 | 57.0 | +0.992% | 0.83 | +0.6 | noise (n=86) |
| THALES | th_metronome | 4 | 3.1 | 25.0 | −2.97% | 0.99 | −0.1 | **unestimable** (n=4) |
| probe¹ | probe | 289 | — | 15.6 | (net$ route) | — | −$41.4 | net-negative; not gross-comparable |
| probe¹ | conviction | 289 | — | 30.8 | (net$ route) | — | −$14.2 | n=26, unestimable |

¹ probe/conviction are LIVE-only and 0/376 gross-recoverable — scored on realized
`net_pnl_usd` at booked (understated) fees; not on the same scale as the candidate
rows above.

**Coherence verdict:** the styles do **not** cohere into a precise picture. Each
per-style estimate collapses to its ~15–45 effective observations, and the one
large, straight signal (side) is a market-beta artifact rather than an
execution-style probability. There is no style whose probability is currently
*precise* (clears an n_eff-honest interval away from baseline). They do not
contradict so much as they lack the independent n to say anything — which is the
same answer era-4 gave at n_eff 9.92.

---

## Log-scale slope findings (the compounding view)

- The log scale did its job: on the linear-% view the per-side means (+0.44% /
  −0.32%) look modest; the **cumulative log series makes the directional split
  unmistakable** (long +24.8 vs short −11.2, R²≈0.72–0.75 straight lines). This is
  exactly the "straight positive slope where linear curves" the operator wanted —
  and it is the clearest demonstration that the dominant structure in the
  recoverable stream is **market direction**, not execution style.
- **Straightness (high R²) is not persistence of edge here.** The h432
  by-quartile scan shows the per-trip log return flipping sign; a high whole-era R²
  fits a line through a walk that happened to net positive over one melt-up. Slope
  sign is not stable out-of-window.
- No non-directional style produced a straight, high-R², n_eff-supported positive
  slope. The candidate stream compounds with the market, not with a style.

---

## Stationarity / drift verdict

**Non-stationary on three axes; only one of them is the market.**
1. **Label era** — 5 disjoint definitions (h432 9,019 · triple_barrier 5,328 ·
   exit_sim 2,756 · legacy 1,781 · exit_sim_time_stop 459); `row_era` accessor
   agrees with persisted `label_era` on 100% of rows (no derivation divergence).
   These may never be pooled; the recoverable-gross corpus is effectively h432-only.
2. **Schema / observability** — 5 column onset dates (F4). Older rows are missing
   the outcome columns (entry/exit, label_ret_pct) that per-style estimation needs.
   This drift is *toward* more coverage, so it is not degradation — but it means the
   usable window for gross per-style work is only ~20 days (h432), not 47.
3. **Market path** — win rate and mean gross swing with the tape (Q2 melt-up 58%
   → Q3 pullback 41%). This is the market being non-stationary, correctly measured.

**What it costs a probability estimator:** old probabilities are stale by
construction — a per-style rate fitted on the 08-19..08-23 window mis-signs by
08-23..08-26. Any estimator must (a) stay within one era, (b) carry n_eff not
nominal n, and (c) neutralize direction before reading a style. None of the three
is optional, and with n_eff ~33 in the only usable era, even a correct estimator is
imprecise until far more *independent* (low-concurrency) observations accrue.

**No feed-degradation drift detected** [K]: UNKNOWN rates fall, not rise, over the
stream; validity is clean end-to-end. The drift that matters is structural
(era/schema/beta), not a dirty feed.

---

## How to Act (remediation — refine existing instruments, add nothing)

Ordered by leverage. Per operator directive, every fix names an existing file;
none proposes a new module.

1. **TOP — make n_eff non-optional for every per-style read; never render a
   nominal-n CI.** The deflation is the single most misleading thing in the stream
   (F1). The discipline already exists — `scripts/cohort_eval.py` and
   `scripts/gate_efficacy_report.py` (its `by_code` effective-n Wilson) encode it.
   The gap is that no per-*execution-style* view inherits it. Refine
   `scripts/gate_efficacy_report.py` to add the per-style cut behind its existing
   effective-n Wilson (the `by_code` template), and treat `ml/corpus.py` as the
   home for a shared `mean_uniqueness`/`n_eff` helper so no future consumer
   recomputes a nominal interval. Do not build a new profiler that reports nominal
   Wilson — that instrument would be wrong by 12–16× and look right.
2. **Neutralize direction before reading any style.** The side-edge (F2) proves the
   candidate labels carry market beta. Refine the per-style report to compare a
   style against a *contemporaneous, direction-matched* baseline — the same
   contemporaneous-comparator idea `gate_efficacy_report.py` already uses for the
   era-confound (`ERA_OVERLAP_*`). Report per-style edge net of the same-window
   market drift, or the "long edge" keeps re-appearing as a false positive.
3. **Stop reading gross per-style probabilities across era/schema boundaries.**
   Constrain any gross per-style estimate to the h432 era (the only fully-recoverable
   one); `ml/corpus.read_rows(era=...)` already gives the filter. Everything before
   2026-08-04 has no gross outcome and must be excluded, not imputed.
4. **Close the maker/taker blind spot at the write path, if that style is to be
   estimable.** It is not in `signal_history.csv` today (F3). The refine-existing
   path is to persist the fill's maker/taker (`post_only`) disposition at the single
   `_append_row` choke point in `ml/history.py`, exactly as `control_arm` was added
   (bookkeeping-only, never a feature, never read by decision code). **This is a
   write-path schema change — COHORT-ADJACENT and needs its own review/adjudication**
   (schema rotation is write-path-only per the 2026-07-11 incident; register any new
   `outputs/` path in `tests/conftest.py`). Flagged, not recommended for this SAFE
   pass.
5. **Live gross outcomes are unrecoverable — prefer `net_pnl_usd` for live, and
   label it.** Live rows are 0/376 on the entry/exit route by construction
   (exit_price 0.0). The accessor correctly returns None; a consumer wanting live
   realized edge must use `net_pnl_usd` and state it is at booked (understated,
   FEE-1) fees, not venue truth.

**Verdict for the operator, one line:** the stream is a clean instrument pointed at
a moving target — its data quality is high, but its data-generating process is
non-stationary and its independent sample size per style is ~15–70, so it cannot
yet estimate precise per-execution-style probabilities; the fix is discipline in
the *reading* (n_eff + era-purity + direction-neutral baselines, all in existing
instruments), not more rows of the same overlapping kind.

---

*Method scope (what this audit could not see):* gross per-style edge rests on the
candidate labeler's own simulated `entry_price`/`exit_price` — only as honest as the
fill simulator; live realized outcomes were read at booked fees (understated per
FEE-1), not venue truth. n_eff uses `[signal_ts, ts]` as the label window; if the
true economic horizon differs, the deflation estimate moves with it (both routes
agreed at ~33–39, so the order is robust). All counts are as-of the 20:20:23Z
snapshot of a file that keeps growing.
