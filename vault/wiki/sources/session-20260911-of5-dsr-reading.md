---
title: "OF-5 armed and failed — what that FAIL does and does not say (2026-09-11)"
category: sources
status: SETTLED - the measurement AND the operator decision it fed ("Keep pooling", 2026-09-11)
summary: "OF-5's DSR gate reached its 30-trip conviction floor and returned FAIL (dsr=0.006, sr=-0.24). Four findings, all measured by RUNNING the shipped code: (1) the gate's label was FALSE - it read 'P(true SR > 0)' while computing P(true SR > sr0) with sr0=0.253, so 'dsr=0.006' was being read as evidence against a positive edge when it meant 'beats the best of 7 tries'; the sign reading is PSR(SR*=0)=0.111 -> P(true SR<0)=0.889, short of the 0.95 the same battery demands in the other direction. (2) The gate is underpowered at this n: minimum detectable effect SR=0.506, so a genuinely profitable book at SR=+0.24 fails it 92.5% of the time. (3) The CI on SR spans zero under every correction: [-0.606,+0.120] nominal, [-0.733,+0.247] at the measured n_eff=16.47. (4) THE BIG ONE - the sample is not era-scoped and cannot be from its own source: signal_history.csv has NO exec_era column. 28 of the 30 conviction trips closed BEFORE cut #10, and the 2 that touch era-9 are STRADDLERS - under cohort_eval's wholly-inside rule the deployed era holds ZERO conviction trips. OF-5's FAIL is a statistic about superseded configurations. OPERATOR DECIDED same day, verbatim 'Keep pooling' - SETTLED, do not reopen; then 'put something in place to make sure if it is regressive then it's not silenced', answered with a deployed-era regression sentinel and 11 mutation-verified anti-silencing pins. FIXED same session: label corrected at 4 sites, psr_zero added to the return, corpus+sign disclosure printed beside the verdict, 12 tests, 4/4 mutants caught. NO FLOOR AND NO THRESHOLD MOVED."
tags: [overfit, gates, dsr, measurement, the-method, era-comparability, underpowered]
sources: 1
ingested: 2026-09-11
updated: 2026-09-11
---

# OF-5 armed and failed — what that FAIL does and does not say (2026-09-11)

Trigger: a literature pass on the DSR small-n decision problem. It read the
code before the papers, which is why it found the defect the papers could not.
**the-method #1 — the instrument was the first suspect, and the instrument was
wrong.**

## The four findings

All re-derived by RUNNING `ml.overfit.deflated_sharpe` and
`scripts/cohort_eval.cohort_effective_n`, not by reading them. The literature
pass could not execute (its session had Bash disabled) and every figure it
returned was hand-derived; all of them reproduced.

### 1. The label was false — and it inverted how the number reads

`ml/overfit.py:857` and both OF-5 gate labels read **`P(true SR > 0)`**. The
code computes `z = (sr_observed - sr0) / denom` where `sr0` is the **expected
maximum Sharpe under the null across N trials** — strictly positive for N > 1.

So `dsr = 0.006` never meant "0.6% chance the edge is positive". It meant
**"0.6% chance the true per-trip Sharpe exceeds sr0"**, and sr0 is not small.
The quantity the label described is PSR at SR\*=0, which was not being
computed at all. Measured: `PSR(SR*=0) = 0.111`, so `P(true SR < 0) = 0.889`.

**Roughly 8:1 against a positive edge, where the DSR rung's own bar of 0.90
is 9:1.** (This page first said "19:1 (95%)". No 0.95 bar exists anywhere in
the battery; the error inflated apparent strictness 2.1x in the direction
that supported the thesis it introduced — red-team OBJ-9, conceded. And the
two quantities sit on different scales: PSR is at SR*=0, the bar is on the
sr0=0.2532 null.) That asymmetry is the whole finding. An operator
reading the old label saw a number that looked like proof and was in fact
short of the bar in its own direction.

### 2. The gate is underpowered at this n, by a wide margin

Minimum detectable effect at n=30, N=7: **SR = 0.506**. Operating
characteristics, computed from the shipped function:

| true per-trip SR | P(OF-5 passes) |
|---|---|
| 0.00 (the null) | 0.28% |
| +0.24 | **7.55%** |
| +0.40 | 28.8% |
| +0.60 | 68.2% |

**A genuinely profitable book at SR +0.24 fails this gate about 92 times in
100.** FAIL is the modal outcome under the null *and* under a materially
positive alternative. At n=30 the gate separates "enormous edge" from
"everything else"; it does not separate "no edge" from "negative edge".

This is the gate working as designed — `sr0 = k(N)/sqrt(n)` rises as n falls,
which is the deflation doing its job. The error is reading its failure as a
measurement.

### 3. The CI spans zero under every correction

| route | SE | 95% CI on SR |
|---|---|---|
| Lo (2002), gaussian | 0.1852 | [-0.606, +0.120] |
| Opdyke (2007), measured moments (skew +0.493, kurt 2.700) | 0.1953 | [-0.626, +0.140] |
| at the measured **n_eff = 16.47 (over the 26 joinable trips)** | 0.250 | **[-0.733, +0.247]** |

`t = -1.331` on 29 df, one-sided p ~ 0.097. MinTRL for this |SR| at 95% is
**48.2 trips** on gaussian moments and **53.5** carrying the measured skew
with its actual sign (positive skew makes a NEGATIVE Sharpe *harder* to
establish — the bracket grows). We have 30.

**Effective n had never been measured for this sample.** `cohort_effective_n`
gives effective_n 16.4718 over the **26** conviction trips whose position_id joins outputs/fills.csv (mean uniqueness 0.63353, se_inflation 1.25637 — BOTH over 26). Four of the 30 do not join and are unmeasurable for concurrency. Relative to nominal n=30 the inflation is x1.3496. This page first said "16.47 of 30 nominal", mixing two samples in one sentence — red-team OBJ-5, 2026-09-12, conceded.
CLAUDE.md mandates effective n for any statistic over concurrent trips; OF-5
was exempt from a standard `gate_truth_report` has enforced since 2026-07-29.

### 4. The sample is not era-scoped, and CANNOT be from its own source

This is the one that decides how the FAIL should be read.

| bucket | conviction trips | net |
|---|---|---|
| closed **before cut #10** (pre 09-06) | **28** | -$12.22 |
| cut #10 / cut #11 | 0 | — |
| **era-9 / cut #12 (the deployed config)** | **2** (both STRADDLERS; **0** wholly inside) | +$1.16 |

Span: **2026-07-20 .. 2026-09-11, 53.2 days.** 17 of the 30 are from July.

**OF-5's "conviction sample" is 93% pre-cut-#10 trades** — a statistic about
fee bookings and barrier geometries that have been superseded twice, presented
as a verdict on the deployed one. CLAUDE.md: trips are *"all citable AS their
era, none poolable across a cut"*; reading-discipline rule (c): a series that
crosses a corpus reset is not one series.

**Why it cannot simply be fixed by reading a column.** The literature pass
recommended era-scoping via `label_era`. That is wrong, and the refutation was
verified rather than assumed:

- `label_era` holds `exit_sim` (25), `triple_barrier` (4),
  `triple_barrier_h432` (1) — **labeling schemes**, not fee eras. CLAUDE.md
  says so directly: the label-era name "encodes the horizon only".
- `signal_history.csv` has **no `exec_era` column at all**.
  `core/session_digest.py:697` already states this in as many words. The stamp
  lives in `core/fill_ledger.py` -> `outputs/fills.csv`, keyed by
  `position_id`.

So era-scoping OF-5 would need either a **join** to the fill ledger or a
**schema addition** (which only helps future rows). **It was put to the
operator and REFUSED: "Keep pooling."** The graded sample stays pooled.
The join is used only by the report-only sentinel described below, which
narrows nothing.

**And the pooling is not unique to OF-5.** `scripts/cohort_eval.py` prints, of
its own era-4 gate: *"this figure POOLS every execution era below... Do not
read it as the accruing cohort's readiness."* The pre-registered gate has the
same property **and already discloses it**. OF-5 did not. That asymmetry, not
the pooling itself, was the defect worth fixing.

## Reconciling the era-9 trip counts (three numbers, one population)

They look contradictory and are not — each has a different denominator:

| count | denominator |
|---|---|
| **10** | trips **wholly inside** era-9 (both legs stamped) — `cohort_eval`'s registered accrual, **10/50** |
| **19** | positions with **any** era-9 leg (includes straddlers); independently, 19 live labeled closes on/after 09-08 |
| **2** | era-9 trips that are **conviction** (`probe == "0"`) - OF-5's denominator |
| **0** | era-9 conviction trips **wholly inside** the era - what the regression sentinel can actually measure; those 2 straddle the cut |

Two routes agreed on 19 (fill-ledger `position_id`s, and `signal_history`
closes). Anyone quoting an era-9 count must say which of the three they mean.

## What shipped, and what deliberately did not

**Fixed** — all SAFE class, report-only, no order-placement path touched:

- label corrected at 4 sites (`ml/overfit.py:28`, `:857`,
  `scripts/overfit_check.py` x2) -> `P(true SR > sr0)`
- `psr_zero` added to `deflated_sharpe`'s return (additive key, invariant 7)
- `dsr_sample_span()` + `dsr_disclosure()` — the gate now prints the sign
  reading and the corpus span **beside** the verdict
- `tests/test_dsr_label_and_corpus.py`: 12 tests, **4/4 mutants caught**
  (remove the deflation; conflate psr_zero with dsr; let probes into the span;
  invent a span when ts is missing)

**NOT done, on purpose:**

- **No floor moved. No threshold moved.** The n=30 conviction floor and the
  0.90 bar are measurement standards ([[concepts/the-method]]); the fix is
  disclosure, never a bar.
- **OF-5 was NOT era-scoped — and the operator has now RULED.** Put the
  finding to them with the measurement in hand and the answer came back
  verbatim: **"Keep pooling."** The sample definition is SETTLED; this is
  not a pending item and must not be reopened as one. Era-scoped, OF-5
  would DEFER rather than FAIL — and the deferral is worse than first
  recorded here: the two era-9 conviction trips are STRADDLERS (stamps
  {9-16ec821e, 10-a5acfe2d, 12-10d4d0c2}), so under cohort_eval's
  wholly-inside rule the deployed era holds **ZERO** conviction trips, not
  2. The operator chose a graded red over an honest silence at 0/30.
- **The red is now GUARDED rather than merely documented**, on the
  operator's follow-up instruction: *"Put something in place to make sure
  if it is regressive then it's not silenced."* See the section below.

## Standing reading

**The FAIL is honest and should stay red.** It correctly reports that the
deployed strategy has not demonstrated a Sharpe clearing the multiple-testing
deflation. What it must never be read as: evidence the edge is negative, or a
verdict on the cut-#12 configuration — which contributes **2 trips** to it.

The pre-registration is well-calibrated for this effect size: MinTRL 48-54
trips sits almost exactly between the registered **n=50 lean** and **n=100
verdict**, and **n=30 is not one of its readout points.**

Re-derive every number here from `python scripts/overfit_check.py` (prints the
sign reading and corpus span) and `python scripts/cohort_eval.py` (per-era
segmentation). They move with the corpus.

Related: [[concepts/overfit-battery]] · [[concepts/false-strategy-theorem-and-minbtl]] ·
[[concepts/the-method]] · [[concepts/partial-identification]]

## The red is GUARDED, not just documented (operator follow-up)

Immediately after "Keep pooling" the operator added, verbatim: *"Put
something in place to make sure if it is regressive then it's not silenced."*

**The hazard being defended against.** A documented red is a red nobody
reads. Once "OF-5 fails, that's the known legacy pooling" is in the record it
becomes a ready-made dismissal for ANY OF-5 failure - including a real one.
Documenting a failure is how a genuine regression gets waved through.

### 1. A separately-named deployed-era sentinel

`scripts/overfit_check.py` now emits `dsr: deployed-era regression sentinel`
beside the pooled verdict. It answers a DIFFERENT question - *is what we are
running right now losing money* - over the conviction trips **wholly inside**
the current `exec_era`, joined `signal_history.position_id` ->
`fills.csv.position_id`.

- It **FAILS only when the 95% UPPER bound on mean net PnL per trip is below
  zero** - a demonstrated loss, not a failure to demonstrate a profit. OF-5
  already owns the second; an alarm that fired on ordinary statistical
  silence would be cried wolf until ignored, which is the silencing it exists
  to prevent.
- SE is computed on **effective n** (`cohort_effective_n`), because a nominal
  SE is optimistic by `sqrt(n/n_eff)` and a too-narrow CI makes the alarm fire
  early.
- The current era is read from `core.fill_ledger.EXEC_ERA` - the module that
  **writes** the stamps being matched - so it follows future cuts instead of
  rotting on a frozen sha.
- It **DEFERS** below 10 trips and reports **INDETERMINATE** when it cannot
  measure. Neither is a pass. A quiet all-clear from a blind instrument is the
  worst possible outcome here.
- It does **not** era-scope OF-5. The graded pooled verdict is untouched.

**As of 2026-09-11 it reads DEFERRED at n=0** - the deployed configuration has
no conviction trips wholly inside it yet (17 of its 19 closes are probes). So
OF-5's pooled FAIL currently says *nothing whatsoever* about what is running.

### 2. Eleven mutation-verified anti-silencing pins

`tests/test_of5_not_silenced.py`. Every one was planted as a live mutation and
**11/11 went red**:

| planted silencing | caught by |
|---|---|
| raise the conviction floor 30 -> 60 (gate defers, red vanishes) | floor pin |
| lower the dsr bar 0.90 -> 0.10 | behavioural bar pin |
| era-scope the graded sample (overturns "Keep pooling") | pooling pin |
| downgrade OF-5 from a graded verdict to an info line | grading pin |
| delete the sentinel call site | wiring pin |
| sentinel reports CLEAN when it cannot measure | indeterminate pin |
| sentinel counts straddlers (imports legacy drag) | wholly-inside pin |
| sentinel counts probe trips | probe pin |
| n_eff allowed to exceed n (alarm fires early) | clamp pin |
| hardcode a superseded era | live-era pin |
| drop `dsr` from EXPECTED_ARMED | ratchet pin |

**Two pins were VACUOUS on the first pass and mutation is what exposed them.**
The bar pin asserted `"0.90" in inspect.getsource(dsr_verdict)` and survived
the bar being lowered to 0.10, because the docstring discusses `dsr >= 0.90`
four times - *"a test pin satisfied by a comment"*, the-method's own
registered recurrence, committed by the pin written to prevent silencing. It
is now behavioural: grade 0.91 and 0.89 and assert the verdict flips. The
`n_eff` pin was vacuous because the real estimator caps uniqueness at 1 and
could never produce the value the clamp defends against; it now stubs the
estimator to return an absurd figure.

**A third "survivor" was the harness, not a pin:** `str.replace(old, new, 1)`
hit the first `dsr >= 0.90` in the file, which is prose. "0 findings" and "the
scan is broken" are the same observation until separated.

### 3. What the adversarial pass corrected in this very page

An adversarial agent attacked the consequence claims before they were written
down, and **amended two of them**:

- **"Permanently red" is FALSE.** `sr0 = k(N)/sqrt(n)` is independent of the
  statistic and legacy drag dilutes at `1/n`, so the gate is escapable by
  evidence. Illustrative single-seed first-crossings from the current 30-trip
  base: the triple "~41 / ~57 / ~80" published here is **WITHDRAWN** (red-team
  OBJ-6, 2026-09-12): it reproduces under no dilution model, ~70 variants were
  swept, and it was taken from a subagent and published without re-derivation,
  which USAGE rule (g) forbids. Two panels got [69, 93, 188] holding the pooled
  mean and sd. The CONCLUSION stands and is what matters: the pre-2026-09-11
  bomb was *unsatisfiable*; this is merely *unmet*. Different animals.
- **The blast radius is narrower than "the definition of done".**
  `scripts/auto_update.py:488` lists `overfit` in `_ADVISORY_GATES` -
  *"Never vetoes."* A red OF-5 does **not** block the deploy updater. It
  blocks `test_windows.bat:57` and the human checklist only.

**One open tension, named and NOT acted on:** `test_windows.bat` now vetoes on
a condition no change under test controls - the shape CLAUDE.md's coordination
rules call out (*"a gate's release condition must never depend on the thing it
blocks"*). The repo's established handling for a known, adjudicated, unfixed
red is `@pytest.mark.xfail(strict=True)` (`tests/test_fail_open_pins.py`) plus
a pin that the marker comes off when the fix lands. **No such encoding was
added here, deliberately** - it is indistinguishable from silencing without an
explicit operator instruction, and the operator's instruction pointed the
other way. Flagged as an operator docket item.
