# Era-4 readout decision table (pre-registration)

**Status: UNSIGNED. Awaiting operator signature (§4). Amended 2026-08-16:
convention rider §4.1 (owed 82/82(b)) — the signature now names its floor
convention and estimator; no §2 number recomputed.**

## Preamble

### What this document is

A pre-committed map from **readout → action**. `scripts/cohort_eval.py` emits
one of three verdicts when the era-4 cohort reaches n=50 closes. This document
fixes, in advance, what the operator will *do* on each branch.

It decides nothing. The tool decides nothing either — its own docstring
(`scripts/cohort_eval.py:105-106`) states the rule: *"the tool never decides -
it names which decision has become decidable."* The signature in §4 is what
decides.

### Why it must be signed BEFORE the readout

Because a rule chosen after seeing the number is not a rule, it is a fit.

The entire n=50 apparatus exists to prevent exactly one failure mode: reading a
small-sample number, disliking it, and picking the interpretation that keeps the
program funded. `cohort_eval.py:16-21` is explicit — *"The stopping rule is a
constant in this file, committed to git, timestamped… The tool REFUSES to render
a verdict below the threshold."* A decision table written after the readout
inherits none of that protection.

The program has already paid for this lesson twice: the 2026-08-02 registration
was written at cohort n≈0, and the era-4 registration at n=1, both explicitly
*"before the data exists"* (`:84-86`, `:120-121`). This table is the third and
it is being written **late** — at n=14 [MEASURED 2026-08-15T22:07:30Z], with the
accruing numbers already visible. §5 records what that costs.

### The exact instant the cohort is fenced on

| marker | value | source |
|---|---|---|
| Execution-era boundary #4 | `aeeaae36`, **2026-08-10T11:03:35Z** | `cohort_eval.py:112-113` (`B4_TS`) [ASSERTED] |
| Capital epoch (5000 → 800 reset) | **2026-08-10T23:05:27Z** = unix **1786403127** | `cohort_eval.py:123-124` (`CAPITAL_EPOCH_TS`) [ASSERTED] |
| **Effective cohort cut** | **1786403127.0 = 2026-08-10T23:05:27Z** | `max(B4_TS, CAPITAL_EPOCH_TS)`, `cohort_eval.py:320` [MEASURED 2026-08-15T22:07:30Z] |
| Geometry epoch (cut #7) | `e7d5ca1a`, **2026-08-11T01:33:50Z**, `exec_era = "7-e7d5ca1a"` | `CLAUDE.md` § Era-4 accrual moratorium [ASSERTED] |
| Pre-registered n | **`ERA4_MIN_N = 50`** | `cohort_eval.py:125` [MEASURED — read from source] |
| Population | entry-opened closed round trips from `fills.csv`, **exit-time selection only** | `cohort_eval.py:313, 320-322` [MEASURED] |

Cohort membership is decided by **close time ≥ 2026-08-10T23:05:27Z** and
`opened_by == "entry"`. Nothing else. The tool does not filter on `exec_era`
(§5, item 2).

**Tool provenance:** `scripts/cohort_eval.py` at commit `c5ce9d0b`
(2026-08-15T08:15:58-05:00); worktree HEAD `71580182` [MEASURED
2026-08-15T22:10Z]. A different commit of this file may compute a different
number — re-stamp before the readout.

---

## 1. What is being decided

### 1.1 The gate that must fire first

```
cohort_eval.py:339    "verdict_available": n >= ERA4_MIN_N     # 50
cohort_eval.py:360    if not res["verdict_available"]:
cohort_eval.py:361        res["readout"] = "ACCRUING"
```

Below n=50 the tool emits **ACCRUING** and no verdict exists. `ERA4_MIN_N` is a
**measurement standard, not a tunable** (`CLAUDE.md` § Definition of done).
Lowering it to obtain a readout is the widening that file forbids.

### 1.2 The three verdicts, arithmetically

Evaluated in this order, first match wins. `gross_pct` = signed cash flow ÷
entry notional, fees excluded; `net_pct` = same with fees subtracted
(`cohort_eval.py:323-328`).

| # | Verdict | Exact condition | file:line |
|---|---|---|---|
| 1 | **NO_GROSS_EDGE** | `gross_mean_pct <= 0` **AND** `gross_median_pct <= 0` | `cohort_eval.py:362-363` |
| 2 | **COST_BOUND** | *(not #1)* **AND** `net_mean_pct <= 0` | `cohort_eval.py:364-365` |
| 3 | **CONTINUE** | *(not #1, not #2)* → `net_mean_pct > 0` | `cohort_eval.py:366-367` |

Read literally:

- **NO_GROSS_EDGE** — the strategy loses money *before any fee is charged*, on
  both the mean and the median. Both must be ≤ 0; one alone is not enough. The
  registered meaning (`:106-109`): *"the stop-strategy question goes to the
  operator. No execution, cost or model change is on the table, because none of
  them create expectancy."* Costs are not the problem, so cost work cannot be
  the answer.
- **COST_BOUND** — gross is positive on at least one of mean/median, and fees
  turn it negative. Registered meaning (`:109-111`): *"an edge exists and fees
  eat it; the fee levers held behind h432 become the live discussion."*
- **CONTINUE** — net mean is strictly positive after fees.

**Three arithmetic traps in that table.** All three are properties of the code as
written, not opinions:

1. **The mean/median split is asymmetric.** NO_GROSS_EDGE requires *both* ≤ 0.
   COST_BOUND therefore fires on a **positive median with a negative mean**, or
   vice versa. With a 5-slot book and fat tails this is not a corner case.
2. **CONTINUE is decided on the mean alone.** `net_median_pct` appears in the
   printout but in **no** branch condition. A cohort with a negative net median
   and one large winner reads CONTINUE.
3. **Zero is not neutral.** Every boundary is `<= 0`, so an exact zero routes
   *away* from CONTINUE.

### 1.3 The other n=50 gate — scope this signature deliberately

`cohort_eval.py` contains a **second, older** gate with **different arithmetic**,
and it reads out **first**.

| | legacy gate (`_PREREG` 2026-08-02) | era-4 gate (`_PREREG_ERA4` 2026-08-10) |
|---|---|---|
| population | `postmortem_summary.csv`, post-432, **underperformer-censored** | `fills.csv`, entry-opened, **complete** |
| threshold | `MIN_COHORT_N = 50` (`:79`) | `ERA4_MIN_N = 50` (`:125`) |
| outcomes | STAND DOWN / CONTINUE / INCONCLUSIVE (`:696-703`) | NO_GROSS_EDGE / COST_BOUND / CONTINUE (`:362-367`) |
| cut points | `mean_net_pct < -1.0` → STAND DOWN; `> 0.0` → CONTINUE; else INCONCLUSIVE (`:80-81`) | see §1.2 |
| current n | **40/50** [MEASURED 2026-08-15T22:07:30Z] | **14/50** [MEASURED 2026-08-15T22:07:30Z] |

The legacy gate is **26 closes ahead** and will read out first. This table's §3
covers the **era-4 gate**. If the operator intends the legacy readout to be
covered too, say so on the signature line — otherwise the first n=50 event this
program experiences will arrive with no signed table behind it.

---

## 2. Current state, measured

All values below produced by one run:

```
scripts/cohort_eval.py --csv <outputs>/postmortem_summary.csv
                       --fills <outputs>/fills.csv
                       --retrain-history <outputs>/retrain_history.jsonl
                       --signal-history <outputs>/signal_history.csv
```
against `c:\Users\haird\Documents\liquiditybot\liquiditybot_ab\outputs`
(the live data dir — the worktree's own `outputs/` is not the live corpus).
**Run started 2026-08-15T22:06:47Z, exit 0.**

### 2.1 Accrual

| quantity | value | tag |
|---|---|---|
| era-4 cohort n | **14** | [MEASURED 2026-08-15T22:07:30Z] |
| distance to `ERA4_MIN_N = 50` | **36 closes** | [MEASURED 2026-08-15T22:07:30Z] |
| legacy gate n | **40 / 50** (10 short) | [MEASURED 2026-08-15T22:07:30Z] |
| first cohort close | 2026-08-12T03:14:40Z | [MEASURED] |
| last cohort close | **2026-08-15T03:24:38Z** | [MEASURED] |
| time since last close at read | **18.71 h** | [MEASURED 2026-08-15T22:07:30Z] |

Closes per UTC day: **08-12: 4 · 08-13: 5 · 08-14: 4 · 08-15: 1** [MEASURED].

**Double-derived** (`USAGE.md` clause e): route A = `cohort_eval.era4_trips()`;
route B = an independent raw regroup of `fills.csv` (1067 rows) with its own
closure/dedup logic. **Both return n=14 with byte-identical close timestamps.**
No disagreement to report.

### 2.2 Effective n — the cohort is smaller than it looks

| quantity | value | tag |
|---|---|---|
| nominal n | 14 | [MEASURED] |
| **effective n** | **4.287** | [MEASURED 2026-08-15T22:09:48Z] |
| mean uniqueness | **0.3062** | [MEASURED] |
| SE inflation | **×1.807** | [MEASURED] |
| gross mean / SE(nominal) | +0.6393% / 0.7307% | [MEASURED] |
| **per-trade gross sd** | **2.7341%** (double-derived: manual `sqrt(var_pop)` and `statistics.pstdev` agree to 1e-9) | [MEASURED] |
| resolvable-edge floor now (2·SE·inflation) | **2.6409%** | [MEASURED] |

### 2.3 Homogeneity — the cohort is MIXED on all three axes

`COHORT HOMOGENEITY: MIXED(both)` [MEASURED 2026-08-15T22:06:48Z]

- **Fill era:** 4 of 14 trips carry a **stale-binary** leg (`exec_era` field
  absent — written by a binary whose columns predate the stamp, so its fill
  physics is pre-boundary-#4). 0 pre-stamp blanks. Stamped eras present:
  `7-e7d5ca1a`.
- **Model era:** champions `adaptive_gbt` **and** `logistic` both opened trips;
  **7 of 14 trips straddle a mid-flight deploy**. Five deploys land inside the
  accrual window (08-11T15:03:20Z, 08-12T21:56:43Z, 08-14T15:14:13Z,
  08-15T01:57:42Z, 08-15T12:55:03Z).
- **Selection era:** joined 14/14 by `position_id`. **`probe` = {1: 13, 0: 1}**
  → **93% probe admissions**. `label_era` = {`exit_sim`: 8,
  `triple_barrier_h432`: 6} → **two label eras in one cohort**. `source` =
  {live: 14}.

### 2.4 Constraints the readout inherits

- **Label geometry cannot pay, model-independently.** `triple_barrier_h432`,
  n=371 rows: target-hit **ACTUAL 0.291** vs **BREAKEVEN 0.429**, margin
  **−0.138**; gross expectancy **−0.4975%** per barrier-resolved path *before
  any cost*; 144 time-stopped paths excluded from the ratio [MEASURED
  2026-08-15T22:06:48Z]. This is arithmetic on pt/sl, not a fit. `pt`/`sl` are
  frozen (ALGO-5).
- **The fee-free sign is population-dependent.** Entry-only: n=256, gross mean
  **+0.0173%**, median **+0.0533%**. Hedge-inclusive: n=415, gross mean
  **+0.0042%**, median **−0.0293%**. **The two rows disagree in sign**
  [MEASURED 2026-08-15T22:06:48Z]. COST_BOUND asserts a gross edge exists;
  which row is quoted decides whether the wider history agrees.

### 2.5 Accrual rate and expected readout date

**Method.** The bot is **RUNNING**, `mode = DRY_RUN`, equity **799.34**,
**5 open positions**, `status.json` written 2026-08-15T22:08:15Z — 3 s before
read [MEASURED, snapshot-stamped 2026-08-15T22:08:18Z]. Accrual is therefore
live but **stalled**: no fill of any kind since 2026-08-15T03:25:34Z.

**Cause of the stall, measured, not inferred.** `events.jsonl` tail (window
2026-08-15T19:20:21Z → 22:08:39Z) contains **332 occurrences** of
`"Blocked: max concurrent positions reached (filled + pending entries)."` —
`risk/capital_manager.py:50`. `config.json:182` sets
**`"max_concurrent_positions": 5`** and exactly **5** positions are open
[all MEASURED 2026-08-15T22:08:55Z].

**Therefore: accrual is not a market rate. It is the service rate of a
saturated 5-slot queue.** New entries are admitted only as old ones close.
Six entry-opened trips are unclosed and **will** join the cohort on close:
`d4b33f39` (LINK, open 329.1 h — an orphan, absent from `status.json`),
`911f9e88` (ETH, 73.2 h), `9716db79` (ETH, 32.3 h), `c031d650` (SOL, 29.9 h),
`e76c580e` (ADA, 24.1 h), `3cc0e558` (SUI, 18.7 h) [MEASURED
2026-08-15T22:08:18Z].

**Estimates.** Need 36 more closes.

| basis | rate | days | date |
|---|---|---|---|
| Little's law, median hold 10.43 h, 5 slots | 11.51/d | 3.1 | 2026-08-19 |
| Little's law, mean hold 16.34 h, 5 slots | 7.34/d | 4.9 | 2026-08-20 |
| realized, cut → last close | 3.35/d | 10.7 | **2026-08-26** |
| realized, cut → now (includes the 18.7 h stall) | 2.82/d | 12.8 | **2026-08-28** |
| realized, last 7 d wall-clock | 2.00/d | 18.0 | 2026-09-02 |

All [MEASURED 2026-08-15T22:09:48Z]. Holding times over the 14 closed trips:
min 0.95 h, median 10.43 h, mean 16.34 h, max 36.00 h.

**Central estimate: 2026-08-26, range 2026-08-19 → 2026-09-02.**

**Uncertainty, stated honestly.** The two Little's-law rows are an **upper
bound** and are contradicted by the realized rate: they assume a freed slot
refills instantly, and the measured 2.8–3.3/day says it does not (an entry must
also clear the admission bar — see the DL-1 coupling in §5). The realized rows
are the honest ones. The estimate rests on 14 events over 4.18 days and one
regime; a single multi-day stall of the kind already visible on 08-15 moves it
by days. The 7-day wall-clock row spans days when the cohort did not yet exist,
so it understates. **Do not treat any single date here as a schedule.**

The legacy gate (10 short, 2.43/day over its last 7 days of rows) projects
**~4.1 days → 2026-08-19/20** — but its writer is stale: last
`postmortem_summary.csv` row 2026-08-14T13:48:41Z, file mtime
2026-08-14T14:33:42Z, i.e. **32.3 h with no new row** while three cohort closes
occurred [MEASURED 2026-08-15T22:07:30Z]. Treat the legacy date as **[UNKNOWN]
pending an explanation of why that writer stopped.**

---

## 3. THE DECISION TABLE

One row per verdict. Actions within a row are **alternatives**, presented with
consequence. **This document does not choose. §4 chooses.**

Legend: **[CR]** = cohort-resetting under `CLAUDE.md` § Era-4 accrual moratorium
— mints the next execution-era boundary and **restarts accrual at n=0**.
**[SAFE]** = measurement/report/docs only; does not alter which orders are
placed or how they fill.

---

### Row 1 — NO_GROSS_EDGE

| | |
|---|---|
| **Condition** | `gross_mean_pct <= 0` **AND** `gross_median_pct <= 0` at n≥50 (`cohort_eval.py:362`) |
| **What it means** | The strategy loses before any fee is charged, on both centre measures. Costs are not the binding constraint. Per the registration (`:106-109`), **no execution, cost, or model change is on the table — none of them create expectancy.** |
| **Corroboration already on file** | The label geometry independently cannot pay: hit 0.291 vs breakeven 0.429, expectancy −0.4975%/path pre-cost (§2.4) [MEASURED]. A NO_GROSS_EDGE readout would be the *second* independent arrival at the same conclusion, not the first. |
| **Reversibility** | Of the readout: **none** — once seen it cannot be unseen. Of the actions: A is reversible in principle but costly to restart; B/C/D are [CR] and destroy 50 closes of accrual. |

**Actions — pick exactly one in §4:**

| id | action | consequence | class |
|---|---|---|---|
| **1A** | **HALT.** Stop opening new positions; let the book flatten; strategy stands down. | Ends the program's live thesis. Accrual stops. Model freeze becomes permanent by default. Nothing is destroyed — the corpus, vault and instruments survive for a later restart. Reversible only by a new registration on a new era. | [SAFE] |
| **1B** | **RE-SCOPE.** Keep the machinery, change what it trades (instrument set, horizon, or regime filter) and re-register a new cohort at a new era boundary. | [CR]: mints a new execution era, n resets to 0, and a fresh n=50 must accrue (§2.5 rate ⇒ ~11–18 days minimum). The old readout becomes historical. Requires a *new* signed table before the new cohort starts. | **[CR]** |
| **1C** | **COST-REDUCTION PROGRAMME anyway.** Pursue fee tiers / maker-only despite the verdict. | **Directly contradicts the registered meaning of this verdict** (`:107-109`). A cost programme against negative gross reduces the loss rate; it cannot make it positive. Choosing this is choosing to override the pre-registration — permissible, but record it as an override in §4, not as compliance. | **[CR]** (fee booking / order lifecycle) |
| **1D** | **ACCRUE FURTHER** to a larger n stated *now*. | Only defensible if the larger n is written on the signature line **before** the readout. Chosen after seeing NO_GROSS_EDGE it is optional stopping, which inflates the false-continue rate without bound. | [SAFE] if pre-stated; otherwise a fit |

**Explicitly NOT permitted after a NO_GROSS_EDGE readout:**
lowering `ERA4_MIN_N`; re-running the tool on a hand-picked sub-population until
the sign flips; re-reading the verdict on the hedge-inclusive population to
obtain a different answer (§2.4 shows the sign moves); quoting the
entry-only lifetime row (+0.0173% mean) as a refutation of a cohort-level
NO_GROSS_EDGE — different population, different question; unfreezing the model
on the argument that a better model would fix it (settled S1, do not
re-litigate).

---

### Row 2 — COST_BOUND

| | |
|---|---|
| **Condition** | not Row 1, **AND** `net_mean_pct <= 0` (`cohort_eval.py:364`) |
| **What it means** | Gross is positive on at least one of mean/median, and fees take it negative. Registered meaning (`:109-111`): *"the fee levers held behind h432 become the live discussion."* |
| **Population caveat the tool itself prints** | The tool prints a hard warning on this branch (`:752-756`): the sign is **population-sensitive**. §2.4 measures the flip — entry-only median **+0.0533%**, hedge-inclusive median **−0.0293%**. **Read both rows before touching a fee lever.** |
| **Reversibility** | Readout: none. 2A is externally reversible but changes the cost stack mid-programme; 2B/2C/2D are [CR]. |

**Actions — pick exactly one in §4:**

| id | action | consequence | class |
|---|---|---|---|
| **2A** | **FEE-TIER WORK** — pursue a better Kraken volume tier / rebate schedule without touching code. | No code change, so not [CR] by the letter of the moratorium. **But it changes the realized cost stack mid-cohort**, which makes trips before and after non-comparable on the exact axis the verdict turns on. If chosen, record whether it is applied before or after the readout. Note item 37a is **HELD behind the h432 verdict** per the 5-0 judge panel. | [SAFE] by letter, **comparability-breaking in fact** |
| **2B** | **MAKER-ONLY entries.** | [CR]: entry decisioning + order lifecycle. Also collides with the measured passive fill probability **0.048** (S6, XV-021) — maker-only at a 4.8% fill rate collapses throughput, and §2.5 shows throughput *is* the accrual rate. Expect accrual to slow by roughly the fill-rate ratio. | **[CR]** |
| **2C** | **HORIZON CHANGE** (longer holds so the move exceeds the round trip). | [CR]: touches labels, geometry, and time limits. Mints a new era and a new label era. Historically this is the 432-bar migration replayed — which minted `triple_barrier_h432` and orphaned two years of instruments. | **[CR]** |
| **2D** | **FEWER, LARGER trades** (raise the admission bar / raise ticket size). | [CR]: entry decisioning + position sizing. Directly reduces accrual rate; a subsequent cohort would take proportionally longer. Interacts with DL-1 (§5). | **[CR]** |
| **2E** | **ACCRUE FURTHER** to a larger n stated now, before acting on any lever. | Same condition as 1D: the larger n must be on the signature line. | [SAFE] if pre-stated |
| **2F** | **HALT anyway.** | COST_BOUND does not compel continuation. Permitted; record it. | [SAFE] |

**Explicitly NOT permitted after a COST_BOUND readout:**
quoting one fee-free population without naming it (`:837-840` — *"Say which one
you mean, every time"*); treating COST_BOUND as evidence the selector works (it
is a statement about the **cost stack**, and §2.3 shows 93% of the cohort was
admitted by the exploration constant, not the selector); re-tuning pt/sl to
"earn more than the round trip" — that is the pre-named **ALGO-5** adjudication
and requires its own operator sign-off; retuning any gate on the accruing
numbers.

---

### Row 3 — CONTINUE

| | |
|---|---|
| **Condition** | not Row 1, not Row 2 ⇒ `net_mean_pct > 0` (`cohort_eval.py:366-367`) |
| **What it means** | Net mean is strictly positive after fees, on honest fills, at n≥50. **Only the mean** — `net_median_pct` is in no branch condition (§1.2 trap 2). |
| **What it does NOT mean** | It is a **trigger, not a measurement** (`:346-350`). §2.2 projects the resolvable floor at n=50 to **1.3974%** (at measured uniqueness 0.306) or **1.7292%** (at saturated-book uniqueness 0.200). A CONTINUE fired by a mean below that floor is indistinguishable from noise. |
| **Reversibility** | Readout: none. 3A/3B are reversible. **3C (arming live) is the least reversible act available to this program** and is independently blocked (§5). |

**Actions — pick exactly one in §4:**

| id | action | consequence | class |
|---|---|---|---|
| **3A** | **KEEP ACCRUING to a larger n**, stated now (e.g. n=100, n=150). | The only branch that converts a trigger into a measurement. At §2.5's realized 2.8–3.3/day, n=100 is a further ~15–18 days beyond the first readout. Costs time; costs nothing else. **The larger n must be written on the signature line to count.** | [SAFE] |
| **3B** | **UNFREEZE THE MODEL** (the 2026-08-10 freeze names the era-4 readout as its only unfreeze trigger). | Re-opens model families/features. Collides with settled **S1** ("a better model is not the lever", three independent refutations) and **S4** (meta-labeling banned, never re-propose). Model work alone is not [CR], but any change to what is *admitted* is. | [SAFE] for training; **[CR]** if it changes admission |
| **3C** | **ARM LIVE** (`dry_run:false` → restart → typed `ARM LIVE`). | **Blocked on its own merits regardless of this verdict.** DL-1: cold-start prior 0.56 < derived bar 0.690239, `min_p_win` 0.55 also below it; the *only* clearing lane is the probe lane at p=0.70, which does not exist outside DRY_RUN. At `dry_run=false` **nothing clears and the deadlock is total** [ASSERTED, program history P4]. Clearing DL-1 is itself [CR]. Also gated by the deploy runbook: `positions == 0 AND open_orders == 0` — **5 positions are open now**. | **[CR]** to enable |
| **3D** | **SCALE CAPITAL** per the standing directive (*"as it starts to succeed, scale the profits…"*). | A capital change is a **capital epoch**: the 2026-08-10 amendment (`:114-122`) established that sizing floors shift the gross% distribution enough to require a new epoch. Would void the cohort exactly as the 5000→800 reset did. | **[CR]** (capital epoch) |
| **3E** | **HALT / stand down anyway** on the grounds that the trigger is below the resolution floor. | Permitted. CONTINUE does not compel continuation any more than COST_BOUND does. | [SAFE] |

**Explicitly NOT permitted after a CONTINUE readout:**
reporting the gross or net mean as a *measured edge* without its effective-n
interval (`CLAUDE.md`: an SE on nominal n is optimistic by `sqrt(n/n_eff)` —
measured **×1.807** today); arming live without a separate DL-1 adjudication;
scaling capital and continuing to accrue on the same cohort; citing CONTINUE as
evidence the *selector* works while §2.3 shows 93% probe admission; treating a
CONTINUE driven by a positive mean and negative median as a positive result
without saying so.

---

### 3.1 Cross-cutting: what must be recorded on EVERY branch

Independent of which verdict fires, the readout is only interpretable if these
are stated alongside it. All are printed by the tool already:

1. Nominal n **and** effective n, with the SE inflation factor.
2. The homogeneity verdict (`CLEAN` / `MIXED(fill)` / `MIXED(model)` /
   `MIXED(both)`) and the probe share.
3. Which fee-free population is being quoted, named explicitly.
4. The commit SHA of `cohort_eval.py` that produced the number.

---

## 4. Signature block

### 4.1 Convention rider (AMENDMENT 2026-08-16 — owed 82 / 82(b); names, never patches)

Two facts the signature previously did not carry, added above the line so the
signature commits to them explicitly. Nothing in §2 is recomputed — the
registration is a measurement standard and mid-accrual re-derivation is the
widening this repo forbids. The rider NAMES what the numbers are:

1. **Every "resolvable-edge floor" in this document is the 2·SE DETECTION
   convention** (a 2-sigma detection threshold), not a power-calibrated MDE.
   At 80% power, two-sided 5%, the multiplier is 2.8016, not 2 — the two
   conventions differ by **40.1%**. The signature block below now requires
   circling ONE; unsigned convention = uninterpretable readout (owed 82).
2. **Every sd/SE behind those floors uses the POPULATION (pstdev) estimator**
   (§2.2 line "per-trade gross sd" says so itself: `sqrt(var_pop)`), which is
   the optimistic side — the sample estimator widens the floor ~3.3% at this
   n (owed 82(b)). Named here so the readout inherits the caveat; not patched.
3. Restated from §3 so the signature line carries it: at n=50 the registered
   readout is a **TRIGGER, not a measurement** — the projected floor sits
   above the effect it is registered to detect, under EITHER convention.

Fill in, date, sign. One action id per row. Leaving a row blank leaves that
branch un-pre-registered — the readout would then be interpreted after the fact,
which is the failure this document exists to prevent.

```
ERA-4 READOUT DECISION TABLE — OPERATOR SIGNATURE
=================================================

Date signed (UTC) : ____________________________________

Scope of this signature (circle or strike):
    [ ] era-4 gate ONLY (ERA4_MIN_N = 50, cohort_eval.py:125)
    [ ] era-4 gate AND legacy 2026-08-02 gate (MIN_COHORT_N = 50, :79)
        -- the legacy gate is 26 closes AHEAD and reads out FIRST (§1.3)

Pre-committed action, one id per verdict:

    NO_GROSS_EDGE  -> action id ______   (1A halt / 1B re-scope /
                                          1C cost programme (OVERRIDE) /
                                          1D accrue to larger n)

    COST_BOUND     -> action id ______   (2A fee tier / 2B maker-only /
                                          2C horizon / 2D fewer-larger /
                                          2E accrue to larger n / 2F halt)

    CONTINUE       -> action id ______   (3A accrue to larger n /
                                          3B unfreeze model / 3C arm live /
                                          3D scale capital / 3E halt)

If any chosen action is "accrue to a larger n", the larger n is fixed
HERE and may not be revised after the readout:

    larger n = ______      (leave blank if no branch uses it)

Cohort contamination (§2.3) is adjudicated as follows -- required,
because the readout's population is not the one the registration
described:

    4 of 14 trips carry stale-binary legs ..... [ ] accept  [ ] void cohort
    7 of 14 trips straddle a model deploy ..... [ ] accept  [ ] void cohort
    93% probe admissions (13 of 14) ........... [ ] accept  [ ] void cohort
    2 label eras in one cohort ................ [ ] accept  [ ] void cohort

I acknowledge (§2.2) that at n=50 the projected resolvable-edge floor is
1.3974% to 1.7292% gross per trade, and that a verdict triggered by a
mean smaller than that floor is not a measured effect:

    initials ______

Convention rider (§4.1) — REQUIRED, the signature is void without it:

    The floor convention this signature commits to (circle ONE;
    the two differ by 40.1%):
        [ ] 2*SE detection threshold
        [ ] 80%-power MDE (multiplier 2.8016)

    I acknowledge every sd/SE above uses the POPULATION (pstdev)
    estimator - the optimistic side (owed 82(b)) ...... initials ______

I am signing this BEFORE seeing the readout.

    initials ______        signature ______________________________
```

**Note on that last line.** It is true for the **era-4** gate at n=14/50. It is
**not** fully true in the sense the phrase implies — §2 of this document
contains the accruing era-4 numbers, and the tool prints them on every run. §5
item 1 states what that costs. Sign it as what it is: *before the verdict fires*,
not *before any number was visible*.

---

## 5. What would invalidate this pre-registration

Blunt. Any of the following, occurring between signature and readout, voids this
table and requires a fresh one signed before the new cohort completes.

1. **It is already partially compromised, and the compromise is structural.**
   The tool prints the accruing gross and net means on every run — they are in
   §2 of this document. The registration's own instruction (`CLAUDE.md`) is
   *"do not read the accruing gate numbers as a trend"*, but the operator
   **can** see them, so a branch chosen in §4 cannot be proven uninformed by
   them. For the **legacy** gate at 40/50 this is worse: the accruing mean net
   is close enough to its decision boundaries that its outcome is largely
   foreseeable. **The honest disclosure is that this table is a
   pre-registration of the era-4 *verdict trigger*, not of an unseen number.**

2. **`cohort_eval.py` is era-blind, so "the pre-registered population" is not
   what the registration described.** Selection is exit-time only
   (`:320-322`); the string `exec_era` never gates membership. 4 of 14 trips
   carry stale-binary legs whose fill physics predates boundary #4 (§2.3). If
   those trips are later excluded — by any route — the cohort changes and this
   table is void. Adjudicate in §4, before the readout.

3. **Any cohort-resetting change** (`CLAUDE.md` § Era-4 accrual moratorium):
   entry decisioning, position sizing, stop/exit geometry (placement, nudges,
   time limits), the fill simulator, fee booking, the order lifecycle. Each
   mints a new execution era and restarts accrual at n=0. The cut-#7 precedent
   is binding: **geometry changes trip outcomes even when fills do not move.**

4. **A capital reset or any change to equity, `max_order_usd`,
   `engage_notional_usd`, or the RP-072 goal ladder.** The 2026-08-10 amendment
   (`:114-122`) is the precedent: sizing floors moved from 0.3% to 1.9% of
   equity and that alone required a new epoch. Note the RP-072 ratchet is
   **automatic** (×1.5 after a met month, never de-escalates) — a capital-side
   epoch can therefore mint itself with no human in the loop. Watch for it.

5. **Any fill-simulator change**, including a correction. `passive_base_prob`,
   the `exp(-d_bar)` form (XV-022, still owed, band [0.048, 0.082]), TTL hazard
   handling. Fixing a bug is still an epoch.

6. **A change to `ERA4_MIN_N`, `MIN_COHORT_N`, or the readout thresholds in
   `cohort_eval.py:78-81` / `:112-127` / `:362-367`.** These are measurement
   standards. Editing one voids the registration whichever direction it moves.

7. **A change to `max_concurrent_positions` (currently 5, `config.json:182`).**
   Not named in the moratorium list, but §2.5 shows it *is* the accrual rate,
   and §2.2 shows it *is* the uniqueness — hence the effective n and the
   resolution floor. Changing it changes both what the cohort measures and how
   fast. Treat as epoch-minting until adjudicated otherwise.

8. **The champion swapping again mid-cohort.** Five deploys already landed
   inside the accrual window and 7 of 14 trips straddle one (§2.3). The retrain
   loop continues by design, so this **will** recur before n=50 — it is the one
   invalidator that arrives on its own unless §4 accepts it in advance.

9. **A stale binary on the deploy box.** The live tree sat at `21769fb8`
   (2026-08-07) until the 08-12 fast-forward, and boundaries #3/#4 and cut #7
   are **not ancestors** of it. The deploy branch is
   `claude/remote-control-e3h815`, not `main` — pushing to `main` alone deploys
   nothing, and commits authored on the box never deploy themselves. **Verify
   the running binary's SHA at the readout and record it.**

10. **Loss or rewrite of `outputs/fills.csv`.** It is the sole cohort source.
    Quarantine, never delete (standing rule; machine-enforced by
    `.mythos/policy.json`).

### 5.1 One live anomaly to resolve before the readout

`postmortem_summary.csv` has not gained a row since **2026-08-14T13:48:41Z**
(mtime 2026-08-14T14:33:42Z) while **three** era-4 closes occurred after it
[MEASURED 2026-08-15T22:07:30Z]. The legacy gate reads that file. Either the
postmortem writer has stopped, or those three closes did not underperform EV.
**Until that is explained, the legacy gate's 40/50 and its projected readout
date are [UNKNOWN], and §1.3's "reads out first" may be wrong.**

---

### Provenance

Every number in §2 was produced during this session against
`c:\Users\haird\Documents\liquiditybot\liquiditybot_ab\outputs` (the live corpus;
the worktree's own `outputs/` is not it). Read times are stamped per claim.
`scripts/cohort_eval.py` at `c5ce9d0b`; worktree HEAD `71580182`. Source files:
`outputs/fills.csv` (169853 B, mtime 2026-08-15T03:25:34Z),
`outputs/postmortem_summary.csv` (36951 B, mtime 2026-08-14T14:33:42Z),
`outputs/retrain_history.jsonl` (68642 B, mtime 2026-08-15T12:55:03Z),
`outputs/signal_history.csv` (8334954 B, mtime 2026-08-15T21:41:24Z),
`outputs/status.json` (mtime 2026-08-15T22:07:51Z),
`outputs/events.jsonl` (5005 lines, mtime 2026-08-15T22:08:09Z).

This document is report-only. It changes no threshold, no selection, and no
decision path — **SAFE** under the era-4 moratorium.
