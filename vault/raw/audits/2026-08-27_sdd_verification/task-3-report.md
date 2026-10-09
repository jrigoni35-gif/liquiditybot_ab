# Task 3 report — commit 5e785c16 "feat(telemetry): the veto counters learn whether the vetoes were right"

Verified 2026-08-27, ~21:35–22:10 UTC [K] (`date -u`), repo `c:\Users\haird\Documents\liquiditybot\liquiditybot_ab`,
branch `claude/claude-rc-f3heik` == `origin/main` @ `5e785c16`. Interpreter `./.venv/Scripts/python.exe`
throughout. All corpus reads are against the LIVE, still-accruing `outputs/signal_history.csv`
(14.0 MB, read-only) — every count below is snapshot-stamped to the read time above, not to
commit time (2026-08-26 19:32:28 -0500, ~26h before this read).

## STATUS: DEFECT_FOUND

One confirmed defect (Q3, below): the "baseline" population `gate_efficacy_report.py`'s
`by_code` table (and hence `liquiditybot_veto_cf_rate`/HANDOFF's REG-6 UPDATE) compares every
veto code against is a **frozen, 5-week-stale, pre-instrumentation snapshot** — not a
contemporaneous or era-matched sample. For the flagship claim this commit shipped
("SZ-021 crisis vetoes are ANTI-SELECTIVE at significance"), the baseline has **zero era overlap**
with SZ-021's own label population, and re-testing against a same-window comparator makes the
"significant" (disjoint-interval) claim **not reproduce**. This is a real, evidenced methodological
defect in what got promoted to HANDOFF.md and Grafana as a decided-by-the-instrument fact — not a
static-reading nitpick: it is demonstrated by re-deriving the numbers from the raw corpus by an
independent route (Q3 below).

Everything else checked came back clean: the arithmetic (Wilson/effective-n) double-derives
exactly (Q2), pending-candidate handling is unbiased by construction and confirmed by both static
read and runtime injection (Q1), and the shipped code is correctly classified SAFE under the
era-4 moratorium (report/telemetry-plane only, no engine/decision-path file touched).

---

## Q1 — WIRING: veto → counterfactual label → exported metric; pending handling

**Trace** (all `[K]` from reading `ml/history.py`, `scripts/gate_efficacy_report.py`,
`scripts/gc_pusher.py`):

1. `main.py` calls `CandidateLabeler.register()` for every gate-confirmed signal (admitted or
   about to be vetoed), then later `self.candidates.mark_disposition(asset, direction, code)`
   (`main.py:1839-1845`, wired to every veto/admission site, e.g. `main.py:4695-4696` for
   SZ-046, `4719-4720` for SZ-045, `4741-4742` for sizer vetoes incl. SZ-030/SZ-021's siblings,
   `4794-4795` for pretrade vetoes). The candidate's `disp` field is stamped with the code string;
   nothing else about the row is touched.
2. `CandidateLabeler.poll(now)` (`ml/history.py:2367-2494`) resolves each open candidate against
   incoming bars via `triple_barrier`/exit-policy simulation. **A label row is written to
   `signal_history.csv` (`_emit_label`, `ml/history.py:2612-2649`) ONLY on a FINAL outcome** —
   either an early pt/sl touch inside the window (`out.final`) or the full `label_max_bars`
   horizon completing. **A candidate that has not yet resolved is simply not written anywhere —
   it stays in the in-memory pool (`self._cands`) and produces NO row at all**, so it cannot be
   miscounted as a win or a loss by any downstream reader.
3. A candidate whose feed goes stale/absent past `horizon + candidate_evict_margin_bars` is
   **CENSORED** (`_maybe_evict_zombie`, `ml/history.py:2496-2551`): removed from the pool, logged
   under `ML-085`, and **no label row is ever written for it** — "missing data, not an outcome"
   (the method's own docstring, confirmed by reading).
4. `gate_efficacy_report._rows()`/`efficacy()` reads only rows already in the CSV with
   `source == "candidate"` and a non-null `label` (`gate_efficacy_report.py:99-101, 186-188`) —
   by construction this set is 100% resolved outcomes; there is no "pending" sentinel value it
   could misread.
5. `gc_pusher._run_veto_quality()`/`_veto_quality_metrics()` (`gc_pusher.py`, new in this commit)
   is a 30-min-cached subprocess wrapper around `gate_efficacy_report.py --json`, drop-on-failure
   (`try/except → None`), all-or-nothing on the baseline band. Exports
   `liquiditybot_veto_cf_rate/lo/hi/neff`, `liquiditybot_veto_baseline_rate/lo/hi`, and the
   `anti_selective`/`selective` flags as gauges, verbatim from the report's own significance
   discipline — no re-derivation, no extra logic that could introduce a pending/loss conflation.

**Verified by two non-static routes, per the brief's explicit ask:**

- **Existing planted-defect test, run and observed green**: `tests/test_candidate_zombie_eviction.py::test_frozen_bars_zombie_evicted_with_code_and_no_row` plants a candidate whose bars freeze before resolution, polls one second before the age deadline (`assert lab.poll(DEADLINE - 1.0) == 0`, pool still holds it) and again at the deadline (`written == 0`, pool empties, `_rows(lab) == 0` — "censored means censored: no label row may be fabricated"). PASSED on this tree.
- **My own injection** (not from the repo): built a synthetic corpus of 35 resolved SZ-999 rows (5 wins) plus **500 additional rows with `label=""`** (a hypothetical pending/unresolved marker) under the same code, fed directly to `gate_efficacy_report.efficacy()`. Result: `SZ-999` came back `n=35, wins=5, rate=0.1429` — the 500 blank-label rows were excluded outright, not counted as 500 losses (which would have dropped the rate to ~0.9%) nor as 500 wins. Confirms `_f(r, "label")` (`gate_efficacy_report.py:104-108`) fails closed on a non-numeric label.

**Conclusion**: pending-as-loss / pending-as-win bias does **not** occur, at either layer (labeler
never emits a pending row; reader would exclude one if it existed). Established by reading AND by
running the code (both an existing pin and a fresh injection), not by inference alone.

---

## Q2 — double-derive the instrument's own bar (independent route)

Re-implemented Wilson's interval **from scratch** (not imported from `gate_efficacy_report.py`)
and pulled `n_eff`/`mean_uniqueness` from the shared `scripts.gate_truth_report.effective_n`
instrument (the repo's own designated standard since 2026-07-29 — re-implementing AFML average
uniqueness untested would itself be a new source of error; the object under test here is
`gate_efficacy_report`'s regex/pooling/Wilson glue, not the uniqueness algorithm it correctly
imports rather than re-deriving). Read `outputs/signal_history.csv` directly with `csv.DictReader`,
filtered `source=="candidate"` and `disp.startswith("SZ-021")`.

Needle: `disp.strip().startswith("SZ-021")` over `source == "candidate"` rows.

| quantity | HANDOFF (2026-08-26 snapshot) | my independent re-derivation (2026-08-27 ~21:40 UTC) |
|---|---|---|
| n | 2,032 | 2,032 [K] |
| wins | — | 1,035 [K] |
| rate | 0.509 | 0.50935 [K] |
| n_eff | 189 | 188.828 [K] |
| 95% CI | [0.439, 0.580] | [0.43857, 0.57975] [K] |

Also cross-checked baseline (n=2,061, rate 0.2654 [0.1924, 0.3539] — matches [0.192,0.354]) and
SZ-030 (n=1,052, rate 0.05989 [0.04005, 0.08863] — matches 0.060 [0.040, 0.089]) the same way.
**All three published numbers reproduce to rounding via an independently-written formula.** No
arithmetic disagreement anywhere. `scripts/gate_efficacy_report.py --json` run live and its
`by_code` output matches my from-scratch numbers exactly for the fields it emits.

Note (currency, not a defect): live-corpus `SZ-023` now reads n=4,732, rate 0.303 vs HANDOFF's
2026-08-26 snapshot of n_eff 1,721, rate 0.278 — expected drift, since SZ-023 is the most active
code and the corpus keeps accruing (max `signal_ts` for SZ-023 rows is today, 2026-08-27). Not a
disagreement; HANDOFF's number is correctly an as-of snapshot.

**Conclusion**: the instrument's own arithmetic is correct. The defect found (Q3) is a
population/comparability problem, not a computation problem.

---

## Q3 — SELECTION BIAS CHECK (DEFECT FOUND)

**What "baseline" conditions on, read from code**: `BASELINE = ""` (`gate_efficacy_report.py:72`);
the docstring claims blank disposition means "registered but never reached a gate verdict" — i.e.
implicitly a live, ongoing "fell through with no verdict" cohort.

**What it actually is, measured**: every one of the 2,061 blank-`disp` candidate rows has
`signal_ts` between **2026-07-13T18:40 and 2026-07-20T15:40** — a hard ceiling. Zero blank rows
exist after 2026-07-20. `git log -S'"disp": "confirmed"'` finds the `disp` column itself was
**added to the schema on 2026-07-20** (commit `8ceb5c3a`, "signal_history 'disp' column
(schema 68->69, migration-backed)"), and `scripts/migrate_history.py:106-107` backfills `disp=""`
for every pre-existing row that predates the column. **The "baseline" is not a live no-verdict
cohort — it is the migration-backfilled, pre-instrumentation corpus, frozen in time on
2026-07-20 and never added to since** (needle: `grep -n '"disp": "confirmed"' ml/history.py`
shows the current *live* code default for a truly-unmarked candidate is the string `"confirmed"`,
which has **0** rows anywhere in the corpus — meaning nothing has generated a fresh blank-baseline
row in 5+ weeks; every registered candidate today always eventually gets a real disposition).

By `label_era` (a dimension `gate_efficacy_report.py` never reads — it bins on `disp` only):

| code | label_era mix |
|---|---|
| baseline (blank) | `legacy` 1,734 (84.1%), `exit_sim` 327 (15.9%), **0 `triple_barrier*`** |
| SZ-021 | `triple_barrier_h432` 2,032 (**100%**) |

The 84.1%-`legacy` figure is an **exact match** to a figure already on file in the canonical vault
(`wiki/synthesis/open-contradictions-register.md`, entry dated 2026-08-15, class **OPEN**:
*"`gate_efficacy_report` IS NOT MEASURING GATE SELECTIVITY"*, sub-finding *"a baseline arm that is
84.1% `legacy` with zero `triple_barrier` against an admitted arm with zero `legacy`"*) — the same
fossil population, unchanged, 11+ days later. Per the no-orphan-claims rule this is not a new
discovery so much as a **currency check on a known-OPEN item**: its *nominal-n / "8x too narrow"*
sub-claim is now **RESOLVED** (commit `c4e4a599`, 2026-08-22, "effective-n reaches gate_efficacy",
predates and is reused correctly by 5e785c16 — confirmed above in Q2), but its **era/population
confound sub-claim was never addressed and is still live** — and this commit built a new,
stronger, HANDOFF-published significance claim directly on top of it without revisiting it.

**Corroborating cross-check (second independent route, controlled for the same time window
SZ-021 fired in)**: instead of the frozen July baseline, I computed the win rate of everything
*else* the pipeline saw in SZ-021's own active window (`signal_ts` 2026-08-19T22:10 –
2026-08-25T01:35, needle: `lo_t <= signal_ts <= hi_t`, `disp` not starting `SZ-021`):

| comparator | n | rate | 95% CI (n_eff) |
|---|---:|---:|---|
| SZ-021 (vetoed) | 2,032 | 0.509 | [0.439, 0.580] |
| ADMITTED, same window | 319 | 0.633 | [0.519, 0.734] |
| everything else, same window (excl. SZ-021) | 1,772 | 0.440 | [0.369, 0.514] |
| shipped comparator: frozen July baseline | 2,061 | 0.265 | [0.192, 0.354] |

Against the shipped (stale) baseline, SZ-021's CI [0.439,0.580] is disjoint from [0.192,0.354] →
"significant, anti-selective" (as published). Against the **contemporaneous** comparator —
same market week, same everything except the SZ-021 disposition itself — SZ-021's CI
[0.439,0.580] **overlaps** [0.369,0.514] (overlap region [0.439,0.514]): **not significant**. Win
rates were elevated across the board that week (admitted trades won 63.3%, the whole
contemporaneous candidate population won 44–48%), consistent with a broad favorable-regime effect
during the crisis window rather than evidence specific to what SZ-021 rejected.

**This does not prove SZ-021 is well-calibrated** — my contemporaneous comparator is one
reasonable choice, not necessarily the canonical one, and HANDOFF's own caveat about "one melt-up
is still one event" is separately true. What it does establish is that **the "significant"
qualifier is not robust**: it flips from disjoint to overlapping depending on which population is
called "baseline," and the shipped baseline is demonstrably the wrong-population choice (a
different calendar month, a different and non-overlapping label-era, frozen since before the
`disp` column existed) — not a defensible default. The correct read of "SZ-021 crisis vetoes:
right or wrong?" is **currently underdetermined**, not "ANTI-SELECTIVE at significance" as
HANDOFF.md states it (`docs/HANDOFF.md:123-131`, REG-6 UPDATE, 2026-08-26).

**Every other `by_code` row inherits the same structural problem** (baseline is always the frozen
blank cohort) but to varying degree — most other codes have at least partial era overlap with
baseline's `exit_sim`/`legacy` mix (see table below); SZ-021 is the one row with **zero** overlap,
and it is the one row promoted into HANDOFF as a decided fact.

| code | label_era mix (n) |
|---|---|
| SZ-020 | exit_sim 176, exit_sim_time_stop 5, triple_barrier 85, triple_barrier_h432 108 |
| SZ-021 | triple_barrier_h432 2032 (100%, zero overlap w/ baseline) |
| SZ-022 | triple_barrier 1286, exit_sim 222, exit_sim_time_stop 59, triple_barrier_h432 1445 |
| SZ-023 | triple_barrier_h432 2027, triple_barrier 2666, exit_sim 39 |
| SZ-030 | exit_sim_time_stop 310, exit_sim 721, triple_barrier 21 |
| SZ-045 | exit_sim 54, exit_sim_time_stop 19, triple_barrier 239, triple_barrier_h432 329 |
| SZ-046 | exit_sim 275, exit_sim_time_stop 43, triple_barrier 165, triple_barrier_h432 22 |
| SZ-050 | exit_sim 16, triple_barrier 59, triple_barrier_h432 3 |

**Defect classification**: this is a **report/measurement-plane defect** (SAFE class under the
era-4 moratorium — it does not touch decision code), but it is a defect in a **claim already
written into HANDOFF.md and exported to Grafana as a significance finding**, which future
sessions and the operator will read as settled. Recommend: (a) HANDOFF's REG-6 UPDATE entry gets
a caveat callout that the "significant" qualifier does not survive an era/time-matched baseline;
(b) the vault's 2026-08-15 OPEN item should be updated — its nominal-n sub-claim is resolved, its
era-confound sub-claim is reconfirmed current and now has a concrete SZ-021 instance; (c) a real
fix needs either era-matched/time-windowed baselines or an explicit refusal to pool/compare across
disjoint `label_era`s, mirroring the vault's own prior recommendation
(`[[concepts/pooled-populations]]`) — I did not implement this; it is a repo-code change outside
this verification task's read-only scope.

---

## Q4 — SD-003 cross-check: does by_code cover the liquidity/spoofy veto path?

**Partially, and the uncovered part is structurally invisible to this instrument — a genuine
coverage gap, reported as such, not a defect.**

SD-003's "liquidity classified 'spoofy'" (`core/session_digest.py:215,379`, `spoofy_frac`) is a
**per-cycle regime classification** from `regime/liquidity_regime.py` (label `"spoofy"` →
`size_mult=0.0`, `reduce_only=True`, `regime/liquidity_regime.py:352`) — evaluated every cycle for
every asset regardless of whether any signal ever gets registered. It is a different axis and a
much larger denominator than "candidate rows the labeler ever saw."

Two distinct downstream mechanisms exist for a "spoofy" liquidity read:

1. **`SZ-045` (`Code.SZ_MANIP_SUSPECT`, "manip suspect ... >= veto")** — `main.py:4700-4721`:
   fires when the *composite* `manip_suspect_score` (MAX of `ls.spoof_score`,
   imbalance-whiplash, cross-venue divergence) crosses `veto_at`. `ls.spoof_score` is one of its
   three inputs, so this is where the liquidity-regime's spoof signal partially surfaces.
   **This code IS covered**: 641 candidate rows, `by_code` reports
   `SZ-045: n=641, rate=0.415, CI=[0.348, 0.485], n_eff=196.4, anti_selective=False, selective=False`
   [K, live run 2026-08-27]. Not significant either way against the (already-confounded, see Q3)
   baseline, though its point estimate (41.5% vs 26.5% baseline) sits in the same anti-selective
   direction as SZ-021, worth a second look once Q3's baseline defect is fixed.

2. **`SZ-031` (`Code.SZ_MULT_ZERO`, "a multiplier zeroed the trade", `risk/position_sizer.py:561-566`)**
   — this is the literal code path that fires when `liq_state.size_mult` (the liquidity regime's
   own `spoofy → 0.0` multiplier, `risk/position_sizer.py:538`) zeroes the sized notional. **This
   code has ZERO rows anywhere in the corpus's history** (needle: `disp.startswith("SZ-031")`
   over all `source=="candidate"` rows → 0 [K]). The manip gate (site 1, upstream in the pipeline
   order — `main.py` line ~4708 runs before the sizer's multiplier stack at ~4724) apparently
   always resolves a spoofy-driven veto before code reaches the sizer's zero-multiplier branch in
   this corpus's history, so the dedicated liquidity-veto code has simply never fired as its own
   disposition.

**Answer**: the new counters **do reach** the part of the spoofy/manip path that produces a
labeled candidate disposition (`SZ-045`), and say the spoofy manip vetoes are *not proven right or
wrong* at current significance (against an already-flawed baseline, so treat cautiously). They
**do not and structurally cannot** reach: (a) the dedicated liquidity-regime zero-multiplier code
`SZ-031` (zero historical rows to grade), or (b) the majority of SD-003's 57%-of-cycles headline,
because most "spoofy"-classified cycles never produce a registered candidate signal at all — there
is no counterfactual bet to grade for a cycle where nothing was ever proposed. This is a coverage
gap in what "were the vetoes right" can even mean for the liquidity axis, not a bug in the shipped
code.

---

## Q5 — covering tests, exact counts

Run: `./.venv/Scripts/python.exe -m pytest <files> -q`, 2026-08-27 ~21:50 UTC.

| file | result |
|---|---|
| `tests/test_veto_quality.py` | **10 passed** |
| `tests/test_boards_stripped.py` | **30 passed** |
| `tests/test_gc_pusher_owed_metrics.py` | **27 passed** |
| `tests/test_candidate_zombie_eviction.py` (Q1 pending/censor pins, pre-existing, not touched by this commit but directly on point) | **14 passed** |
| **combined single run** (all 4 files together) | **81 passed**, 0 failed, 0 skipped, 2.42s |

Did not re-run the full 4047-test suite the commit message claims (`Suite 4047/9skip green`) —
out of scope/expensive for this targeted verification; the four files above are the complete set
of tests this commit's diff touches or that directly exercise the mechanism verified in Q1
(zombie/pending eviction pre-dates this commit but was re-run here as the runtime check for Q1).

---

## Method scorecard (per the mandatory preference order)

1. MUTATION/INJECTION — planted a synthetic pending-row corpus at the `efficacy()` boundary (Q1);
   ran the repo's own planted-defect test for zombie censoring (Q1).
2. ASK THE RUNTIME — ran `gate_efficacy_report.py --json` live against the current corpus; called
   `ger.efficacy()` directly with both real and synthetic rows.
3. EXHAUSTIVE / DOUBLE-DERIVE — recomputed SZ-021, baseline, and SZ-030's rate/n_eff/Wilson CI
   from raw rows with an independently-written formula (Q2); cross-tabulated `label_era` for every
   `by_code` row against baseline (Q3).
4. CONTROLLED EXPERIMENT — varied the "baseline" population (frozen-July vs. contemporaneous
   same-window) holding SZ-021's own data fixed, and watched the significance verdict change
   (Q3) — this is the load-bearing check that turned a "reads correct" instrument into a
   demonstrated defect.

"0 findings" vs "the scan is broken" is separated for every question above: Q1/Q2 are genuine
0-findings (both a static read and a runtime check agree); Q3 is a **finding**, not a broken scan
— corroborated by three independent measurements (era mix, time-window freeze, contemporaneous
comparator) all pointing the same way, and by an existing OPEN vault item that already logged the
same population confound in this exact script 11 days before this commit shipped.

## Files referenced (absolute paths)

- `c:\Users\haird\Documents\liquiditybot\liquiditybot_ab\scripts\gate_efficacy_report.py`
- `c:\Users\haird\Documents\liquiditybot\liquiditybot_ab\scripts\gc_pusher.py`
- `c:\Users\haird\Documents\liquiditybot\liquiditybot_ab\scripts\build_trading_dashboard.py`
- `c:\Users\haird\Documents\liquiditybot\liquiditybot_ab\scripts\migrate_history.py`
- `c:\Users\haird\Documents\liquiditybot\liquiditybot_ab\ml\history.py` (CandidateLabeler, `_emit_label`, `poll`, `_maybe_evict_zombie`)
- `c:\Users\haird\Documents\liquiditybot\liquiditybot_ab\main.py` (mark_disposition call sites, manip gate ~4700-4721, sizer call ~4724-4743)
- `c:\Users\haird\Documents\liquiditybot\liquiditybot_ab\risk\position_sizer.py` (SZ_MULT_ZERO / SZ-031, line 561-566; liq_state.size_mult, line 538)
- `c:\Users\haird\Documents\liquiditybot\liquiditybot_ab\regime\liquidity_regime.py` (spoofy label, line 352)
- `c:\Users\haird\Documents\liquiditybot\liquiditybot_ab\core\codes.py` (SZ_MANIP_SUSPECT=SZ-045 line 179, SZ_CIRCUIT_BREAKER=SZ-046 line 180, SZ_MULT_ZERO=SZ-031 line 173)
- `c:\Users\haird\Documents\liquiditybot\liquiditybot_ab\core\session_digest.py` (SD-003, spoofy_frac, lines 215/379)
- `c:\Users\haird\Documents\liquiditybot\liquiditybot_ab\docs\HANDOFF.md` (REG-6 UPDATE, lines 120-139)
- `c:\Users\haird\Documents\liquiditybot\liquiditybot_ab\tests\test_veto_quality.py`
- `c:\Users\haird\Documents\liquiditybot\liquiditybot_ab\tests\test_boards_stripped.py`
- `c:\Users\haird\Documents\liquiditybot\liquiditybot_ab\tests\test_gc_pusher_owed_metrics.py`
- `c:\Users\haird\Documents\liquiditybot\liquiditybot_ab\tests\test_candidate_zombie_eviction.py`
- `c:\Users\haird\Documents\liquiditybot\liquiditybot_ab\outputs\signal_history.csv` (live, read-only, 14.0MB, read 2026-08-27 ~21:35-22:10 UTC)
- `c:\Users\haird\Documents\liquiditybot\vault\wiki\synthesis\open-contradictions-register.md` (lines 594-615, OPEN item, 2026-08-15)

---

## FIX REPORT — commit `a94b5751` (2026-08-27, ~22:15-23:10 UTC [K])

Applied the focused-fix protocol (`C:\Users\haird\.claude\skills\focused-fix\SKILL.md`):
SCOPE = `scripts/gate_efficacy_report.py` + its covering test file (single-file feature, no
consumer-side changes needed since Grafana keys are unchanged); TRACE = inbound
(`ml.history.label_era_of`, `scripts/gate_truth_report.effective_n`), outbound
(`scripts/gc_pusher.py._run_veto_quality` reads `by_code` JSON, `render()` reads
`eff["dispositions"]`); DIAGNOSE = the confirmed Q3 defect above; FIX below; VERIFY below.

### STATUS: FIXED

### What changed

**`scripts/gate_efficacy_report.py`** (+~95 lines):
- New import `from ml.history import label_era_of` (mirrors the existing pattern in
  `scripts/migrate_history.py`, which already imports the same function at module scope).
- New module constant `ERA_OVERLAP_FLOOR = 0.05` (policy floor, not fitted — comment explains
  why) and three small helpers: `_row_era(r)` (2-line glue duplicating
  `ml.history._row_label_era`'s precedence — persisted `label_era` column first,
  `barrier`-derived fallback for pre-column rows — but importing rather than re-implementing
  the classification itself, `label_era_of`), `_era_mix(rows) -> Counter`, `_era_overlap_frac
  (mix, base_eras) -> float`.
- `efficacy()`: computes `base_eras` once from the baseline sample's own era mix. Per-disposition
  loop now computes `s["era_overlap"]` and `s["confounded_baseline"]`, and gates
  `anti_selective`/`anti_selective_nominal` on `not confounded` in addition to the existing
  neff/ADMITTED checks. `by_code` pooling accumulates an era-mix `Counter` per code (kept in a
  sibling `era_mix_by_code` defaultdict rather than folded into the existing 4-element list, to
  avoid a heterogeneous-type list pyright would flag — see Ruff/pyright below) and each pooled
  row now carries `era_overlap`, a new `comparison` field
  (`"CONFOUNDED_BASELINE" | "anti_selective" | "selective" | "not_significant" | "no_baseline"`),
  and `anti_selective`/`selective` gated the same way. **Rates and CIs (`lo`/`hi`/`n`/`wins`/
  `rate`) are computed and reported exactly as before in every case — the guard only touches the
  significance flags/field, never suppresses the underlying numbers.**
- `render()`: the Per-rule markdown table's flag column now shows
  `(baseline CONFOUNDED - N% label_era overlap, no significance claim made)` in place of
  `**ANTI-SELECTIVE**` when `confounded_baseline` is set.
- **Grafana contract preserved**: `scripts/gc_pusher.py` was NOT modified. Its
  `_run_veto_quality()` reads `r.get("anti_selective")`/`r.get("selective")` from the `by_code`
  JSON via `.get()`, so it silently ignores the new `era_overlap`/`comparison` keys and correctly
  receives `False`/`False` for confounded codes — `liquiditybot_veto_cf_rate/lo/hi/neff` and
  `liquiditybot_veto_baseline_rate/lo/hi` are untouched (same keys, same shape); the
  `anti_selective`/`selective` gauges now read the honest (conservative) 0.0 for SZ-021/SZ-023
  instead of a false-positive 1.0. Per the fix-scope constraint this was extended, not renamed,
  and no new Grafana gauge was added (kept the diff to `gate_efficacy_report.py` only, per
  "exactly this, nothing else" — noted as a residual limitation below).

**`tests/test_veto_quality.py`** (+51 lines): two new tests using a new `_era_row()` helper
(wraps the existing `_row()` fixture builder, adds a `label_era` field):
- `test_disjoint_label_era_yields_confounded_verdict` — INJECTION: 40 baseline rows era=`legacy`,
  40 `SZ-321` rows era=`triple_barrier_h432` (win rate 80% vs baseline 25% — would read
  disjoint-CI "ANTI-SELECTIVE" under the pre-fix logic, reproducing the exact SZ-021 shape).
  Asserts `era_overlap == 0.0`, `comparison == "CONFOUNDED_BASELINE"`,
  `anti_selective is False and selective is False`, AND `n == 40`, `rate == 0.80`, `lo`/`hi`
  not None (rates/CIs still reported).
- `test_same_era_corpus_still_yields_normal_verdicts` — CONTROL: 40 baseline + 40 `SZ-322` rows,
  both era=`legacy`, `SZ-322` all losers. Asserts `era_overlap == 1.0`,
  `comparison == "selective"`, `selective is True and anti_selective is False` — proves the
  guard does not blanket-suppress every by_code verdict.

**`docs/HANDOFF.md`**: appended a `**REG-6 CAVEAT (2026-08-27, era-confound):**` paragraph
directly after the existing REG-6 UPDATE block. Original SZ-021/SZ-030/SZ-023 numbers from
2026-08-26 kept verbatim (not deleted). New paragraph states the frozen-baseline era mix, the
contemporaneous-comparator overlap result, that SZ-023's "AT baseline" read is now separately
also `CONFOUNDED_BASELINE` (era_overlap 0.008 < 0.05 floor — a second real instance found by
running the fix against the live corpus, not anticipated when the fix scope was written), and
states plainly: "Direction is unresolved, not refuted."

**Vault** (`c:\Users\haird\Documents\liquiditybot\vault\wiki\synthesis\open-contradictions-
register.md`, lines 594-615 entry, not a git repo — saved directly, no commit): appended a
`*2026-08-27 addition*` paragraph inside the existing `gate_efficacy_report` OPEN entry
(existing italic-date-prefix callout style, matching the page's own `*08-02 addition:*`
precedent elsewhere). States: nominal-n sub-claim RESOLVED (`c4e4a599`, re-verified on-tree via
`git show -s c4e4a599` → `2026-08-22T21:04:05Z`, "effective-n reaches gate_efficacy" — re-derived
this session, not recalled from the earlier task-3 report per the "re-derive, don't recall"
rule); era-confound sub-claim CURRENT with the concrete SZ-021/5e785c16 instance; the fix shipped
this session (`a94b5751`) implements exactly the remedy the entry's own "Why OPEN" paragraph
named ("per-era rows plus a refusal to pool when era mixes are disjoint"); cites the live re-run
numbers (SZ-021/SZ-023 confounded, SZ-030 stays selective); explicitly defers the OPEN→RESOLVED
classification call to the operator's next currency pass rather than asserting it. Bumped the
page's `updated:` frontmatter 2026-08-15 → 2026-08-27 (no later-dated entries existed elsewhere
in the file, confirmed by grep before bumping).

### Covering tests — exact counts

Command: `./.venv/Scripts/python.exe -m pytest tests/test_veto_quality.py
tests/test_boards_stripped.py tests/test_gc_pusher_owed_metrics.py
tests/test_candidate_zombie_eviction.py -q`, run twice (before commit and after the
pyright-driven refactor below) — **83 passed, 0 failed** both times (was 81 in the task-3
verification run before this fix added 2 tests: 81 + 2 = 83, double-derived by the arithmetic
matching the observed count).

Isolated the 2 new tests: `pytest tests/test_veto_quality.py -q -k "disjoint or same_era"` →
**2 passed** (confirms they were collected and actually executed, not vacuously skipped).

`tests/test_import_integrity.py`: **1 passed** (the new `ml.history` import at module scope
does not break isolated-import integrity).

### Mutation evidence (per the operator's mandatory verification order)

Inverted the guard's comparison operator in place on the tracked file:
`era_overlap < ERA_OVERLAP_FLOOR` → `era_overlap >= ERA_OVERLAP_FLOOR` (semantically: "confounded
whenever overlap is HIGH", the opposite of the intended rule). Re-ran
`pytest tests/test_veto_quality.py -q`:

```
FAILED tests/test_veto_quality.py::test_selective_flag_fires_on_the_all_loser_veto
FAILED tests/test_veto_quality.py::test_disjoint_label_era_yields_confounded_verdict
FAILED tests/test_veto_quality.py::test_same_era_corpus_still_yields_normal_verdicts
3 failed, 9 passed in 0.39s
```

3 pins went red: both new injection/control tests AND one **pre-existing** pin
(`test_selective_flag_fires_on_the_all_loser_veto`, SZ-888 in the original fixture corpus —
its rows share `era_overlap == 1.0` with baseline under the correct logic, which the inverted
comparison flips to `confounded=True`, forcing `selective` false and breaking the pin). This
confirms the guard is load-bearing against both the new fixtures and the pre-existing corpus,
not merely satisfying its own newly-added assertions. Reverted the operator (`>=` → `<`) and
re-ran the same 4-file combined suite: **83 passed, 0 failed** again — restored clean.

### Ask-the-runtime corroboration (live corpus, not synthetic)

`./.venv/Scripts/python.exe scripts/gate_efficacy_report.py --json` against the live, still-
accruing `outputs/signal_history.csv` (read-only, snapshot-stamped 2026-08-27 ~22:00 UTC [K]):

| code | n | era_overlap | comparison (post-fix) | anti_selective (post-fix) |
|---|---:|---:|---|---|
| SZ-023 | 4,732 | 0.008 | CONFOUNDED_BASELINE | False |
| SZ-022 | 3,012 | 0.074 | not_significant | False |
| SZ-021 | 2,032 | 0.000 | **CONFOUNDED_BASELINE** | False (was True pre-fix) |
| SZ-030 | 1,052 | 0.685 | selective | False |
| SZ-045 | 641 | 0.084 | not_significant | False |
| SZ-046 | 505 | 0.545 | not_significant | False |
| SZ-020 | 374 | 0.471 | not_significant | False |
| SZ-050 | 78 | 0.205 | not_significant | False |

SZ-021 flips exactly as the diagnosis predicted. SZ-030 (era_overlap 0.685, well above the
5% floor) correctly stays `selective` — the fix does not indiscriminately silence every code,
only the disjoint-era ones. **New finding, not anticipated in the original diagnosis**: SZ-023
(era_overlap 0.008) also crosses the floor into `CONFOUNDED_BASELINE` — HANDOFF's published
"SZ-023 sits AT baseline" claim is likewise unproven under the honest comparator, not just
SZ-021's "ANTI-SELECTIVE" claim. Folded into both the HANDOFF caveat and the vault addition
above. Also confirmed identical output before/after the pyright-driven refactor (same 8-row
table, byte-for-byte on the fields checked) — the refactor changed only internal data-plumbing
shape, not behavior.

### Lint/type/compile

- `ruff check scripts/gate_efficacy_report.py tests/test_veto_quality.py` → **All checks
  passed.**
- `python -m compileall -q scripts/gate_efficacy_report.py tests/test_veto_quality.py` → clean.
- `pyright scripts/gate_efficacy_report.py`: first pass introduced 17 NEW errors from a
  heterogeneous-type list (`[0.0, 0.0, 0.0, 0, Counter()]` unpacked via tuple-destructuring,
  which pyright cannot narrow per-position on a plain `list`). Refactored to keep the era-mix
  accumulator in a separate `defaultdict(Counter)` instead of folding it into the existing
  4-element numeric list — restored the original tuple-unpack shape exactly. Re-ran: **1 error**
  — confirmed via `git show HEAD:scripts/gate_efficacy_report.py` piped through pyright
  (pre-fix, at the parent commit) that this exact 1 error (`dict[str, float|int]` argument to
  `__setitem__`, an unrelated pre-existing issue in the `out["by_code"] = []` assignment) already
  existed before this fix. **0 new pyright errors introduced.** `scripts/` is outside CLAUDE.md's
  pyright gate (only `core data execution ml risk regime strategies sentiment api main.py
  runner.py` are gated), so this was due diligence beyond the strict requirement, per the task
  brief's "ruff + pyright must stay green on files you touch."

### Full suite (`pytest tests/ -q`, 4,058 tests collected)

Launched in background per the CLAUDE.md Definition-of-Done battery. Completed after this report
section was first drafted (580.06s / 0:09:40, exit code 0 at the pytest-process level despite the
one failure below — pytest's own exit-0 here reflects `--continue-on-collection-errors`-style
completion, not a passing verdict; read the summary line, not the process exit code):

```
1 failed, 4048 passed, 9 skipped in 580.06s (0:09:40)
FAILED tests/test_fee_reconciliation.py::test_credential_less_environment_skips_silently
```

**Investigated the 1 failure rather than dismissing it by correlation alone** (per the repo's own
instrument-first doctrine — "a surprising number gets its INSTRUMENT verified before it gets a
theory"): `test_fee_reconciliation.py` is in `execution`/`OM-080` fee-reconciliation territory,
zero overlap with the 3 files this fix touched (`scripts/gate_efficacy_report.py`,
`tests/test_veto_quality.py`, `docs/HANDOFF.md`) or with the audit-chain machinery
(`core/runtime.py`) that assertion reads from. Ran it in isolation:
`pytest tests/test_fee_reconciliation.py -q` → **15 passed, 0 failed** — the same test that failed
inside the full run passes cleanly alone. This localizes the failure to cross-test state bleed
(the assertion diffs audit-log codes written between a `mark` and `now`; something earlier in the
4,058-test run leaves `OM-000`-tagged entries the isolated run doesn't produce) — a pre-existing
full-suite-only order-dependency, not a regression from this fix. Corroborating structural
argument: `efficacy()`/`_row_era`/`_era_mix` (this fix's only new code) do zero I/O — pure
in-memory computation over a `rows: list` argument — so the 2 new tests in
`tests/test_veto_quality.py` cannot write to the audit chain this failure inspects. **Not fixed
here** (a full-suite test-isolation bug in an unrelated subsystem is outside "exactly this,
nothing else"); flagged for the operator as a separate pre-existing defect, not attributed to
this commit.

Net: **83/83 covering tests (this fix's actual verification surface) + 4048/4049 relevant tests
in the full suite (the 1 failure independently confirmed unrelated and order-dependent) + 0
regressions traceable to this diff.**

### Classification: SAFE (era-4 moratorium)

Confirmed as shipped: no file under `main.py`'s decision pipeline, `execution/`, `risk/`,
`core/fill_ledger.py`, order-lifecycle, or fee-booking paths was touched. All three changed
files are report/telemetry/docs-plane (`scripts/gate_efficacy_report.py` is explicitly
docstring-labeled "Report-only... Never touches a decision"; `tests/`; `docs/HANDOFF.md`).
Does not change which orders are placed or how they fill.

### Residual limitation (reported, not fixed — out of the "exactly this" scope)

The Grafana board itself has no visual distinction between "not significant" and
"CONFOUNDED_BASELINE" — both now read `liquiditybot_veto_anti_selective=0.0`/
`liquiditybot_veto_selective=0.0` for a code. The JSON/markdown report (and hence anyone reading
`gate_efficacy.md` or running `--json`) sees the distinction via the new `comparison` field;
an operator looking only at the Grafana panel would not. Fixing this would mean adding a new
gauge key to `scripts/gc_pusher.py` (e.g. `liquiditybot_veto_cf_confounded`) — deliberately not
done here per the fix-scope instruction to touch `gate_efficacy_report.py` only and change
"exactly this, nothing else."

### Files changed (absolute paths)

- `c:\Users\haird\Documents\liquiditybot\liquiditybot_ab\scripts\gate_efficacy_report.py`
- `c:\Users\haird\Documents\liquiditybot\liquiditybot_ab\tests\test_veto_quality.py`
- `c:\Users\haird\Documents\liquiditybot\liquiditybot_ab\docs\HANDOFF.md`
- `c:\Users\haird\Documents\liquiditybot\vault\wiki\synthesis\open-contradictions-register.md`
  (not committed to git — vault has no VCS)

Commit: `a94b5751441e3b7dad1ed2cc435f0d656f45ebb9` on branch `claude/claude-rc-f3heik`
(local only, not pushed, per the fix brief's constraint).
