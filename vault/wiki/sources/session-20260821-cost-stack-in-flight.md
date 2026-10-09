---
title: "Session 2026-08-21 — the cost-stack investigation (IN FLIGHT): gross measured POSITIVE, fees ~10x it, and the tool's own Kraken constants are a struck schedule"
category: source
status: PROVISIONAL
summary: "PROVISIONAL (narrowed 2026-08-26: the question this page tracked reached its readout — era-4 gate COST_BOUND at n=54, gross positive and eaten by costs on the decision-grade cohort, sources/session-20260826-why-losing-deep-dive — so the 434-pool figures below are moot as evidence and only THEY remain provisional; B1/B2 and the mix residuals still stand). Original filing: an OPEN investigation, filed under governance rule 21 so it cannot be read as settled. The reported run of scripts/cost_attribution.py over 434 closed positions measures mean GROSS +0.0733% (POSITIVE) against a configured 25/40bps fee stack costing 0.717%, i.e. net -0.6440%: fees ~10x the gross edge, and the sign of gross flips the framing of the money-path thesis without changing the NOT-READY verdict. THREE items were verified independently this session and are NOT provisional: (1) the tool's KRAKEN_MAKER_BPS/KRAKEN_TAKER_BPS = 16.0/26.0 at scripts/cost_attribution.py:76-77 are the schedule this vault STRUCK on 2026-08-07 (true Tier-1 is 40/80), so its two counterfactual comparison rows are computed against a fee schedule that does not exist, in the flattering direction; (2) that file's :74-75 comment asserts 'lower tiers only reduce these, so using base is the conservative check' — a safety property that is INVERTED if Tier-1 is 40/80; (3) at the true 40/80 the wedge is ~16x, not ~10x, so the correction makes the finding WORSE, not softer. Two owed items registered: the 0.7173% implied fee cost exceeds even a 60%-taker-share model of the configured stack by ~3.7bps (unexplained residual), and a 60% taker share is structurally impossible at 2 legs/trip on a limit-only-entry bot (ceiling 50%), so either entries are booking taker or trips carry more than two legs."
tags: [session, cost, fees, gross-vs-net, provisional, in-flight, money-path]
source_path: "(none — investigation IN FLIGHT; no raw/ snapshot exists yet, see What would settle this)"
source_date: 2026-08
ingested: 2026-08-21
sources: 2
updated: 2026-08-26
---

# Session 2026-08-21 — the cost-stack investigation (IN FLIGHT)

> [!warning] **PROVISIONAL — THIS INVESTIGATION IS STILL RUNNING.**
> The 434-position figures below are **reported, single-route, and not
> re-derived by this filing**. They have not been double-derived (contract
> clause (e)), their population cut against the
> [[synthesis/comparability-boundaries|comparability boundaries]] is
> **unstated**, and **no refuter has been run against them**. They may be
> acted on as a **lead**. They may **not** be cited as evidence, and nothing
> downstream may depend on them. Filed under
> [[concepts/claim-status-discipline]] / governance rule 21 precisely so that
> a reader cannot mistake this page for a result.

> [!success] **2026-08-26 — THE QUESTION THIS PAGE TRACKED HAS ITS READOUT.**
> The era-4 gate crossed its pre-registered n=50 (54 closes) and read
> **COST_BOUND**: on the decision-grade cohort — uniformly post-cut-#7,
> concurrency-deflated (effective n 21.5/54) — **gross IS positive and net at
> the honest fee constant IS what fails**, exactly the reframe this page filed
> as a lead. See [[sources/session-20260826-why-losing-deep-dive]]. That route
> satisfies what refuters **R1** (pooling) and **R2** (noise) demanded: the
> cohort is single-regime by construction and the probe-tuition claim survives
> ×1.58 concurrency deflation (p≈0.027 at true fees). **The 434-position pooled
> numbers below remain unverified and are now MOOT as evidence** — the
> clean-cohort route supersedes the need to verify them; this page stays
> PROVISIONAL for those specific figures only. Still standing from here:
> B1/B2 (the struck 16/26 constants in `cost_attribution.py`, owed 98) and the
> two execution-mix residuals (owed 99) — the deep dive did not touch either.

## Why this page exists at all

Because the alternative was worse. This investigation is **already reframing**
[[synthesis/live-readiness-verdict]], which was filed hours earlier and reads
as a final verdict. Leaving the reframe unfiled meant the settled page kept
being read at face value; filing it as though it were settled would have
committed the exact error rule 21 forbids. **PROVISIONAL is the third option
the vault previously did not have.**

---

## A. The provisional claims — reported, NOT re-derived

Instrument: `scripts/cost_attribution.py`. Population: **434 closed
positions**. **Read time and population cut both [UNKNOWN]** — see *pending
refuters*.

| quantity | value | tag |
|---|---|---|
| mean **gross** (before any fees) | **+0.0733%** — POSITIVE | [REPORTED, unverified] |
| fee cost at the configured 25/40 stack | **0.717%** | [REPORTED, unverified] |
| mean **net** | **−0.6440%** | [REPORTED, unverified] |
| fees ÷ |gross| | **≈ 9.8x** | [I] derived from the row above |
| taker share of legs | **60%** | [REPORTED, unverified] |

**Internal consistency check [K], run by this filing:** `+0.0733 − 0.7173 =
−0.6440` exactly, so the reported triple is arithmetically coherent with the
fee figure rounded from **0.7173%**. This checks the *arithmetic*, not the
*measurement* — it would look identical if all three came from a
mis-scoped population.

**Why the sign matters.** [[synthesis/the-money-path-thesis]] currently stands
at *gross edge indistinguishable from zero in both directions* — which the
same page is careful to say is **not** "there is no edge". A **positive**
measured gross on a 434-position sample is a candidate for the first
directional reading of that quantity. **It is exactly the kind of flattering
result that [[concepts/self-flattery-gradient]] says gets the most scrutiny,
not the least** — which is why it is filed provisional rather than filed as
news.

---

## B. Verified this session — NOT provisional

These three were established directly against the shipped file and the vault's
existing record. They are the reason the provisional numbers above need
re-running rather than merely re-reading.

### B1. The tool's Kraken constants are a STRUCK schedule

`scripts/cost_attribution.py:76-77` **[K]**:

```python
KRAKEN_MAKER_BPS = 16.0
KRAKEN_TAKER_BPS = 26.0
```

**16/26 was falsified by this corpus on 2026-08-07** — triple-confirmed that
25/40 matches **no** current Kraken row and that **Tier 1 ($0+) is 40/80**
([[concepts/cost-truth]]). The repo already carries the correction at its own
source: `config.json:318` records that `min_half_spread_bps=26` "descends from
the **STRUCK** 16/26 fee schedule… the real public floor is 25/40" — a note
added specifically "so the stale premise cannot be re-cited as current."

**It was re-cited as current.** The tool builds its counterfactual comparison
table from these constants (`:201-204` **[K]**):

- `"Kraken taker/taker (26/26)"` → **0.52%** round trip
- `"Kraken maker/maker (16/16)"` → **0.32%** round trip

Both are below the **1.20%** a true Tier-1 40/80 round trip costs. So every
"what would this have cost at Kraken's own rates" row in that output is
computed against **a fee schedule that does not exist**, and the error runs in
the **flattering** direction. This is the **third** recorded recurrence of the
struck-16/26 propagation ([[synthesis/documentation-drift-register]]) — the
first two were config.json's rationale and a 7-agent audit that quoted it.

### B2. The file's own conservatism claim is INVERTED

`scripts/cost_attribution.py:74-75` **[K]**:

> `# Kraken Pro base (highest) tier, 30-day volume < $10k, as of 2026-08.`
> `# Lower tiers only reduce these, so using base is the conservative check.`

If Tier 1 is **40/80**, then 16/26 is not the highest row — it is **below every
row on the ladder**, and the comment asserts a safety property that runs the
wrong way. A reader is told the check errs toward caution while it errs toward
flattery. **This is a claim shipped inside a running instrument and believed
because it runs** — the sharpest class on the drift register.

### B3. At the true schedule the finding gets WORSE, not softer

Holding the reported gross fixed **[I]**:

| fee schedule | round trip | fees ÷ gross (+0.0733%) |
|---|---|---|
| configured (25/40) | 0.65% modelled / **0.7173% implied** | ≈ **9.8x** |
| **true Tier-1 (40/80)** | **1.20%** | ≈ **16.4x** |

The pending fee-constant correction ([[synthesis/owed-measurements]] item 88,
batched at the readout boundary) therefore **strengthens** the cost-bound
reading. Nobody should read the falsified constants as a reason to discount
this investigation.

---

## C. Two residuals registered as owed, not explained

**C1 — the implied fee cost exceeds the model. [I]** The configured stack at
one maker entry + one taker exit is `(25+40)/100 = 0.65%`. Even at the
reported **60% taker share across legs**, a two-leg model gives
`2 × (0.6×40 + 0.4×25) / 100 = 0.68%`. The implied figure is **0.7173%** — a
residual of **≈3.7 bps** the two-leg model does not account for. Candidate
mechanisms (**none established**): the exit-leg spread the EV stack prices in,
multi-leg exits from the escalation ladder, partial fills, or hedge legs
inside the same trips. **Registered, not resolved.**

**C2 — 60% taker is structurally impossible at two legs per trip. [K]+[I]**
Repo `CLAUDE.md` invariant 5: **entries are limit orders only**; market orders
are the exit escalation ladder's final rung. On a strict 1-entry/1-exit trip
the taker share therefore **cannot exceed 50%**, and that ceiling is reached
only if *every* exit is a taker. **60% is above the ceiling**, so at least one
of the following holds and none is established: entry legs are booking taker
rates; trips carry more than two legs; or the 60% is computed over a
population that is not one-entry-one-exit (hedge legs are `_OPEN_PURPOSES =
("entry", "hedge")` in this very file, `:72`).

**Historical comparison [K]:** the same tool's docstring records its 2026-08-02
reading as bimodal — `n=397 post_only=1` at 25.0 bps and `n=286 post_only=0` at
40.0 bps, i.e. a taker share of **41.87%**, *below* the ceiling. If the current
60% is real it is a **+18pp drift** in execution mix and is a finding in its
own right — one that would matter to the fill-side of
[[synthesis/comparability-boundaries]].

---

## What this does NOT change

**The live-readiness verdict stays NOT READY.** None of the five blockers on
[[synthesis/live-readiness-verdict]] is a cost-stack claim, and a positive
gross does not touch any of them — the gate has still not read out, it still
fires below its own noise, the cohort is still 85% probe admissions, two
CRITICAL defects are still inert only because `dry_run` is true, and the
manipulation gate is still not evidence. **What changes is what the verdict is
ABOUT**: a NOT-READY built partly on "no demonstrated edge" reads differently
from a NOT-READY built on "a positive gross edge is being eaten ~10-16x over
by the cost stack." That is a reframe, not a reversal — and it is
**provisional**.

**And it is entirely sim-side.** Every fill, fee, queue and markout behind
these numbers is **simulated** ([[concepts/paper-real-boundary]]); the fee
constants are config constants, not venue truth. A gross measured on the
fill simulator inherits every one of that simulator's biases.

## What would settle this

1. **Re-run `scripts/cost_attribution.py` with the population cut stated** —
   which comparability boundaries the 434 positions straddle (fill axis #1-#4,
   cut #7 the geometry epoch, the capital epoch, the label axis). **434 > the
   era-4 cohort's 33**, so this population is certainly pooled across cuts;
   until the cut is named, the mean is a [[concepts/pooled-populations|pooled
   statistic]] and the sign of gross is not attributable to any regime.
2. **Report effective n, not 434** ([[concepts/average-uniqueness-and-ess]]).
   Concurrent trips share one market path; the era-4 cohort's mean uniqueness
   was 0.301. A +0.0733% mean with no SE and no `n_eff` cannot be distinguished
   from zero, and *"positive"* is a **sign claim**, which is the claim most
   sensitive to this correction.
3. **Double-derive the gross** by a second route (contract clause (e)) — the
   full-book fills reconstruction that previously agreed with the state
   identity to within 1.35 is the obvious independent path.
4. **Correct or quarantine the 16/26 constants** (B1) and re-emit the
   counterfactual table, or delete the table until the fee-constant correction
   lands with owed item 88. Fix the inverted comment (B2) either way — **that
   is a SAFE change** ([[concepts/the-method]] stage 3: it alters no order and
   no fill).
5. **Snapshot-stamp the read** (contract clause (c)). `outputs/fills.csv` has
   **no git history** and has been observed growing between two reads 34
   seconds apart; every figure here is as-of a read time that is currently
   **[UNKNOWN]**.
6. **File the raw snapshot** into `raw/quant/` so this page has a primary
   artifact to point at, per the vault's own source-page contract.

## Pending refuters

**None have been run.** Default disposition is **REFUTED** until they are
([[concepts/the-method]] stage 8). Each is stated as the position a refuter
should be *assigned to argue*:

- **R1 — "the positive gross is a pooling artifact."** Argue that the +0.0733%
  is produced by mixing pre- and post-boundary fill regimes, and that the
  post-cut-#7 subset alone is ≤ 0. *This is the most likely refutation and
  should run first.*
- **R2 — "the positive gross is noise."** Argue that with `n_eff` ≪ 434 the
  observed mean sits inside 1 SE of zero, so the sign is unresolved — the
  [[synthesis/owed-measurements|item 82]] shape recurring at a third n.
- **R3 — "the hedge legs decide the sign."** Argue that including or excluding
  hedge round trips flips it — the precedent is exact: `breakeven_test.py`
  discarded 159 hedge round trips and thereby flipped its median gross from
  −0.0303% to **+0.0505%**, printing the opposite of its own method's answer.
  **The sign of that flip is the same sign this page reports**, and
  `_OPEN_PURPOSES` (`:72`) shows this tool treats `hedge` as an opening leg.
  *This refuter has a named historical mechanism and must be run.*
- **R4 — "the fee figure is the artifact, not the gross."** Argue that the
  0.7173% implied cost (C1's unexplained 3.7 bps) means the fee side is
  mis-attributed, so the ~10x ratio is wrong even if gross is right.
- **R5 — "the instrument is blind."** Argue from precedent: on 2026-08-09
  **both** cost tools filtered out the hedge leg with no skip counter, so the
  project's cost picture was assembled from **59.23 of the 382.59** in fees it
  had actually paid — 235 round trips seen against 394 that existed. Establish
  that this run does not repeat that, rather than assuming the 08-09 repair
  covered it.

## Related

[[synthesis/live-readiness-verdict]] · [[concepts/claim-status-discipline]] ·
[[concepts/the-method]] · [[concepts/cost-truth]] ·
[[synthesis/the-money-path-thesis]] · [[synthesis/comparability-boundaries]] ·
[[synthesis/documentation-drift-register]] · [[synthesis/owed-measurements]] ·
[[concepts/paper-real-boundary]] · [[concepts/average-uniqueness-and-ess]] ·
[[concepts/pooled-populations]] · [[concepts/self-flattery-gradient]]
