---
title: "Two Adversarial Audits + Two Shipped Fixes (2026-08-09) — The Sizer Was Reading an Empty Book, the Go/No-Go Tool Printed the Opposite of Its Own Method, and Every Measured Distortion Flatters"
category: source
summary: "47 read-only agents across two audits (22 on the Grafana panel/metric chain, 25 hunting self-flattery) plus two shipped-and-deployed commits. 1fee174e: risk/position_sizer.py read a state attribute PortfolioState does not have, so three risk controls were inert and ALL failed permissive — tickets ran 13.7% larger than designed, and 3,400 tests missed it because the test doubles invented the attribute production lacks. a6334162: 49% of lifetime fees appeared in no readable P&L number. Still open — the drawdown gauge plots a different quantity than the hard stop that fires on it; the go/no-go breakeven tool discards all 159 hedge round trips and prints the OPPOSITE branch (median gross +0.0505% shipped vs −0.0303% corrected); the perf ledger AND the consecutive-loss breaker are both blind to the entire −325.70 hedge book; performance.overall pools 91% EV-gate-bypassed probes with conviction trades. Aggregate direction: every distortion found flatters the bot, zero understate it. Second independent method puts gross P&L at −13.01, agreeing with the state identity's −11.66"
tags: [audit, adversarial, risk, sizing, pnl, telemetry, grafana, hedging, test-doubles, self-flattery, unbiased]
source_path: (session transcript — no raw/ artifact; every headline claim re-verified against the live tree before filing)
source_date: 2026-08
ingested: 2026-08-09
updated: 2026-08-09
---

# Two Adversarial Audits + Two Shipped Fixes (2026-08-09)

> **Verification posture.** Every headline claim below was **re-verified against the live tree
> before filing**. Where a claim could **not** be reproduced, or where a first number was **wrong
> and corrected**, that is stated in place rather than dropped — including **two corrections the
> filing agent made to its own numbers** (§1.3, §4.1) and **two the audit made to itself** (§4.4,
> §4.6). Per [[synthesis/governance-doctrine]] rule 14, a claim in the grammar of a measurement
> must have been measured.

> **Paper/real boundary ([[concepts/paper-real-boundary]], domain rule 9).** Every dollar, fee,
> fill and markout below is **sim-side**: `dry_run`, fill-at-limit RNG, config-constant fees
> (25/40 bps, themselves falsified — [[concepts/cost-truth]]). The **risk-control defect** in §1
> is **repo-side and real** — the code would size real tickets the same wrong way. The
> **directional caveat cuts against the bot**, never for it (§5).

---

## 0. What this session was

Two adversarial sweeps, run as read-only agent fleets over one tree:

| Audit | Fleet | Scope | Yield |
|---|---|---|---|
| **A** | 22 agents | Grafana panel → metric → source-of-truth chain, panel by panel | **11 defects across 15 panels**, 8 decision-grade |
| **B** | 25 agents | *"Where does the bot look better than it is?"* — every reporting surface | the bigger one; see §4 |

**Audit B's aggregate finding is the one that matters and it is not any single defect:**
**every distortion measured runs the same direction — flattering. Zero instances were found of
the bot understating itself.** Filed as [[concepts/self-flattery-gradient]].

Both audits ran against a live runner. Post-fix state: **runner relaunched 11:46:10, RUNNING,
cycle 5**, both commits deployed and verified live.

---

## 1. SHIPPED — `1fee174e`: the sizer was reading an empty book

**Severity: the highest-consequence defect this project has found in the risk lane, because it
was live, silent, and failed permissive in all three of its effects.**

### 1.1 The mechanism

`risk/position_sizer.py` read the open book at **three sites** as:

```python
getattr(state, "positions", {}).values()
```

`PortfolioState` **has no `positions` attribute**. The book is `_positions`, exposed as
`open_positions()`. So the `getattr` **default was taken unconditionally, on every call, for the
life of the module.** Verified directly at filing: a `PortfolioState` holding a real position
returns `{}` from that expression.

The sizer therefore believed the book was **always empty**.

### 1.2 Three risk controls, all inert, ALL failing permissive

| Control | Intended behaviour | Actual behaviour |
|---|---|---|
| **Portfolio-heat veto** (`max_portfolio_heat_frac` **0.35**, reason `RP_HEAT_FULL`) | refuse new risk once aggregate heat reaches the cap | **unreachable** — heat computed as 0.0000 forever |
| **Signed-inventory reservation skew** (`SZ-061`) | reserve capacity against the side the book is already long/short | **never applied** |
| **Inventory-aggression multiplier** | taper from `light_boost` **1.10** toward `heavy_cut` **0.65** as the book fills | **pinned at 1.10** — a permanent **10% size-UP**, as if the book were empty |

Note the direction: **there is no reading of this bug in which the bot was too cautious.** A dead
heat gate cannot veto; a dead skew cannot reserve; and the aggression term's *default* end of the
taper is the *boosting* end. All three failures compound in the same direction, at exactly the
moments when the book is most loaded — i.e. **precisely when risk was already on**.

### 1.3 The measured effect — and a correction to the filing agent's own first number

Measured on the **live book with REAL position ages**:

```
gross heat      0.1176   (the sizer read 0.0000)
signed heat    +0.1052   (the sizer read 0.0000)
multiplier      0.9488   vs the pinned 1.1000
```

**⇒ tickets were 13.7% LARGER than designed.**

> ⚠️ **CORRECTION, made in place by the filing agent.** The first number printed was **−40.9%**.
> That reconstruction stamped **every position as opened NOW**, which **maximized the clustering
> term `u_short`** and exaggerated the taper. With **real ages** the honest figure is **−13.7%**.
> The bug is unchanged; the magnitude is 3x smaller than first stated. Recorded because a
> corrected number that is quietly replaced teaches nothing
> ([[concepts/adversarial-verification]]).

**Post-deploy verification (live, after the bounce):** `status` `heat_frac` now reads **0.1177**,
where it had been **structurally 0.0 for the entire life of the instrument**.

### 1.4 Why it survived ~3,400 tests — the load-bearing lesson

**The test doubles invented the attribute production lacks.**

The sharpest instance is `tests/test_protocols.py::test_open_heat_reads_position_size_not_units`.
Its docstring states its own reason for existing:

> *an earlier draft read a nonexistent `units` attribute, which zeroed heat for every real
> `Position` and made the RP-050/051 heat gates unreachable in production*

**That test missed the identical bug one level up** — because its own fixture,
`class _State: positions = {...}`, **supplied the missing attribute itself**.

> **It guarded a nonexistent field on `Position` while depending on a nonexistent attribute on
> `state`.** The test was written by someone who understood this exact failure class, and the
> double reintroduced it one level higher.

**New rule, filed as a first-class concept ([[concepts/test-double-fidelity]]) and proposed as
governance rule 15:**

> **A TEST DOUBLE MAY ONLY IMPLEMENT API THE PRODUCTION OBJECT ACTUALLY HAS.**

Three doubles were fixed to mirror `open_positions()`.

### 1.5 The fix, and the zero-sentinel it removes

- **One centralised `_open_book()` accessor** replaces the three `getattr` sites — the class fix,
  not three point fixes ([[concepts/two-paths-one-quantity]]).
- **It logs once when a state cannot report its book.** Previously a **dead reader** and a
  **genuinely flat book** produced the **identical benign 0.0** — a textbook
  [[concepts/zero-is-not-a-reading]] instance, and this one sat **on the sizing path**.
- **9 tests**, including an **AST pin**.

> **The pin PARSES rather than greps** — a substring check matched **the module's own prose
> describing the bug** and failed on its first run. This is the third time this repo has needed
> a parsed-AST assertion where a text scan was defeated by the code's own documentation
> ([[concepts/false-green]] discriminator rule).

### 1.6 Panel symptom

Audit A's defect **D3** — the *"Heat vs cap"* panel reading **0.0% forever** — was the
**visible symptom** of this bug. A telemetry audit found a live risk defect. That is the case
for auditing the panel chain at all.

---

## 2. SHIPPED — `a6334162`: honest all-time P&L

**Operator-reported symptom:** *"net pnl all time doesn't match up with equity."*

**No money was missing. The STATEMENT was wrong.**

`core/state.py` `record_realized_pnl` nets the **CLOSING leg only**; `record_entry_fee` debits the
**OPENING leg (entry AND hedge)** straight to cash and **touches no P&L counter**. So **185.94 of
382.59 lifetime fees — 49% — appeared in NO readable number.**

**The change:**

- `entry_fees_total` accumulator.
- **`net_pnl_all_time`, defined as the EQUITY IDENTITY, not a sum of counters** — so a forgotten
  counter cannot hide the same way twice. *(This is the design lesson: the bug existed because a
  P&L number was a sum of the counters someone remembered.)*
- `realized_net_all_in`.
- **4 new status keys** + `gc_pusher` gauges.
- An **EXACT one-time backfill** for pre-upgrade snapshots:
  `start + realized − cash − savings − reserve`.
- **8 tests.**

**Verified live post-bounce** (the previous filing recorded this work as *authored, not
committed* — it is now **shipped and running**):

```
entry_fees_total      185.94
realized_net_all_in  -394.25
net_pnl_all_time     -382.40   (= equity 4617.60 − 5000)
```

> **Snapshot discipline.** `net_pnl_all_time` read **−383.26** at the
> [[sources/session-20260809-unbiased-economics]] snapshot and **−382.40** here; the difference is
> **open unrealized moving between snapshots**, not a discrepancy. `realized_net_all_in`
> **−394.25** is stable across both. Always quote which snapshot
> (domain rule 1).

This closes the reporting half of the gap that page opened. It **does not** change the §5
economics — that decomposition was recovered from the cash identity independently and never
depended on these keys existing.

### Battery — both commits

```
pytest 3490 passed / 19 skipped · smoke 219 · assurance 49 · overfit 3 passed / 0 failed
ruff · pyright 0 · bandit · compileall · quant G1–G5
```

**ALL GREEN on both commits.**

---

## 3. AUDIT A — the Grafana panel / metric chain (22 agents)

**11 defects across 15 panels; 8 decision-grade.** The three that carry consequence:

### D1 — the strongest false claim on any board

The hero tile **"Net P&L (all time)"** plotted `liquiditybot_realized_total` = **−208.31**,
against a true all-in of **−382.34** at audit time. Its own description read:

> *"the true bottom line, never resets, hedges included"*

**All three clauses were false of the series it plotted.** Filed to
[[synthesis/documentation-drift-register]] — a description that ships **inside a running
instrument** and is believed because it renders.

**Status: the underlying number is FIXED by `a6334162`; the BOARD still points at the old
series.** Repointing **requires the new keys to exist in the running process** (`gc_pusher`
**skips absent keys**) — which is **now true post-bounce**, so the board change is **unblocked**.

### D2 — STILL OPEN, decision-grade: the gauge and the trigger read different quantities

**Both drawdown gauges** (command board panel id **23**; problem/solution board panel id **23**)
plot **`drawdown_pct`**:

```
drawdown_pct = (start − cash − savings) / start        # start-to-now, CASH-ONLY
```

while **the 15% hard-stop flatten AND the throttle both read `drawdown_mtm_pct`** (**peak-to-now,
mark-to-market**).

**Reproduced on live code:** a book **−20% on marks** fires `hard_stop_triggered`
(*"20.00% >= 15%"*) **while the gauge reads 0.0, FULL GREEN.**

**The inverse is already pinned in the test suite** — `tests/test_audit_config_risk.py:281-288`,
where a **WINNING account pegs the same gauge at 15.0, red.** The suite already knew the gauge
was not the risk quantity; nothing connected that to the panel.

**Why it persists:** `runner.py:984` **computes `drawdown_mtm_pct` and DISCARDS it as a local**;
`gc_pusher` carries only `drawdown_pct`; **no board references the MTM series at all.**

The audit's headline for this is **THREE DERIVATIONS OF ONE WORD, "drawdown"**. Two have cited
call sites (the gauge's cash-only start-to-now; the hard stop and throttle's peak-to-now MTM);
the third is implied by the proposed retitle below (a **reserve-inclusive** realized-from-start
figure — the gauge omits the `reserve` term). **Recorded as the audit's count, with only the two
cited derivations verified here.**

**Proposed fix:** export `drawdown_mtm_pct`; add it to `gc_pusher`; **repoint both gauges**; and
**retitle the survivor** *"Realized drawdown from start (reserve-inclusive)"* — so the two
quantities keep two names ([[concepts/two-paths-one-quantity]]).

### D3 — the sizer bug

See §1. The panel *"Heat vs cap"* reading **0.0% forever** was the symptom that led to it.

### Board regeneration

**ONE regeneration** covering **D1 repoint + D2 + every other panel finding.**
**Boards are GENERATED — the JSON is never hand-edited** ([[entities/observability-sidecars]]).

---

## 4. AUDIT B — the self-flattery hunt (25 agents)

### 4.1 A1 — the go/no-go tool has been printing the opposite of its own method's answer

**VERIFIED INDEPENDENTLY by the filing agent — and nearly dismissed. See the near-miss below.**

`scripts/breakeven_test.py:126` counts **only `purpose == "entry"`** as the opening leg. So **all
159 COMPLETE hedge round trips are discarded** and filed under **"165 skipped: partial or
malformed."**

**None of them are malformed.** They close to **within 0.0% of opening size**.

Reimplementing **the tool's own accumulation** both ways over `outputs/fills.csv`:

| | Shipped (`purpose == "entry"`) | Corrected (`purpose in {entry, hedge}`) |
|---|---|---|
| closed / skipped | **235 / 165** | **394 / 6** |
| gross | **−3.03** | **−13.01** |
| fees | **59.23** | **374.96** |
| net | **−62.27** | **−387.96** |
| **MEDIAN GROSS** | **+0.0505%** | **−0.0303%** |

**THE SIGN FLIPS — and the sign selects which branch the tool PRINTS:**

| | The tool prints |
|---|---|
| **Shipped** (`:214-230`) | *"This is NOT 'no edge' … that is exit geometry … **fixable without touching the signal**"* |
| **Corrected** (`:231-241`) | *"**GROSS EXPECTANCY IS NEGATIVE** … no execution change, holding period, gate, filter or model creates expectancy that is not in the entries."* |

> **These are not two shadings of one verdict. They are opposite instructions about where to
> spend the next month of work** — and the go/no-go tool has been printing the **wrong one**.

**Fix: ~10 lines**, plus **break the skip counter out by reason** so *"partial"* and
*"deliberately excluded leg type"* can never again share a bucket
([[concepts/uncounted-exclusion]]).

> ⚠️ **THE FILING AGENT'S OWN NEAR-MISS — filed as process evidence, not as an aside.**
> The first verification **added fees back into `cash`** — which is **already the pure notional
> flow** — producing a *"gross"* that was really **net**, and showing **NO flip**. On that basis
> the operator would have been told **the audit was wrong**.
> It was caught by **re-deriving the terms** rather than trusting the script.
> **Same error class as the *"reproduces on the parent commit"* claim earlier this session**
> ([[concepts/false-green]] design rule 8): a quantity asserted in measurement grammar without
> checking what it actually contained. Caught this time.

### 4.2 A4 — LIVE RISK, STILL OPEN: the breaker and the ledger are both blind to the hedge book

`main.py:1671`:

```python
if not pos.is_hedge:      # gates BOTH perf.record_close AND breaker.record_close
```

**One predicate gates two subsystems**, and the entire **−325.70 hedge book** is invisible to
**both**:

1. **The performance ledger** — expectancy, win rate, profit factor, Sharpe.
2. **The consecutive-loss circuit breaker.**

> **This is why 159 consecutive losing hedge round trips over 10.4h never tripped the breaker:
> they were never recorded as losses.**

`status.json` implies **200 trades × −0.2838 = −56.76** against a **true closed book of
−387.96**.

**⚠️ ADJUDICATION NEEDED — AND DELIBERATELY NOT TAKEN HERE.**

- **The performance ledger clearly SHOULD see hedges.** They are real money and they are in the
  P&L. That half is not a design question.
- **Whether the consecutive-loss BREAKER should see them is a genuine design question.** A hedge
  is **risk-reducing insurance that often loses BY DESIGN**; counting hedge losses could trip the
  breaker **during correct operation**. And the 159-loss run was a **churn bug** (FW-070, since
  fixed — [[sources/session-20260807-hedge-churn-guards]]), **not** normal behaviour.

> **Changing what a circuit breaker counts changes WHEN IT FIRES. That is a gate semantics
> change and it belongs to the operator** ([[concepts/never-widen-a-gate]],
> [[concepts/deadlock-discipline]]). Filed as owed, unsplit, with both readings stated.

### 4.3 A3 — `performance.overall` pools two populations that differ by design

`performance.overall` pools **91% EV-gate-BYPASSED probes** with **conviction trades**,
**count-weighted**.

Inside the **exact 200-close window** (197/200 joined):

| Population | n | expectancy |
|---|---|---|
| **probe** | 182 | **−0.1636** |
| **conviction** | 17 | **−1.5840** |
| **reported (pooled)** | 199 | **−0.2838** |

**The reported figure understates the conviction population by 5.6x** — and conviction trades are
the ones the strategy is actually *about*.

`pos.is_probe` **is in scope 22 lines earlier at `main.py:1650`** and is simply **not passed**.

**`sharpe −1.067`, `sortino −0.751`, `max_loss_streak 57` are all computed on the mixed sample
and describe NEITHER population.**

> **THE CODEBASE ALREADY HOLDS THE OPPOSITE DOCTRINE.** `overfit_check.py:1031-1034` **refuses to
> grade DSR on the mixed sample for exactly this reason.** The correction exists in the
> **ML-validation lane** and is **entirely absent from the P&L-reporting lane.**
> Filed as [[concepts/pooled-populations]] — and note the shape: this is not a missing idea, it
> is an idea that **did not travel between lanes**.

> ⚠️ **CORRECTION the audit made to itself.** **Notional weighting does NOT support the
> argument** — return-on-notional is **−0.692% probe vs −0.479% conviction**, i.e. the *opposite*
> ordering. **The probe/conviction SPLIT is what recovers the truth, not a re-weighting.**
> Recorded because the discarded half of an argument is evidence the surviving half was tested.

### 4.4 A2 — `cost_attribution.py` is structurally blind to its own largest cost event

`scripts/cost_attribution.py:126` is a **bare `continue` with NO skip counter** — the same hedge
blindness as A1. The reader sees **n=1019** in one paragraph and a cost computed from **n=235** in
the next, **with no signal that the populations differ.**

> ⚠️ **CORRECTED DOWNWARD from the initial hunt.** The printed **0.668%/trade is CORRECT** for the
> **235 directional trades**. The honest blended figure is **0.7766%** — **1.16x, NOT the 6.4x
> first claimed.**

**Severity: MEDIUM.** The defect is not the number; it is that **a cost-attribution tool is
structurally blind to its own largest cost event.**

### 4.5 Fill sim — resting orders get two chances to fill per modelled event

**22.30% per-order fill against an 11.66% calibration target at the touch.** Mechanism: **resting
maker orders get TWO independent chances to fill per modelled event.**

**⇒ roughly half the near-touch paper entry population describes fills the recorded market never
granted.**

**Bounded: 1.19x at 20bps → 1.91x at the touch**, weighted toward the high end because **57% of
post-only fills rest within 5bps.**

> **Propagation into the 305 live corpus rows and into the 432-bar cohort verdict is
> DIRECTIONALLY SUPPORTED but UNVERIFIED.** Stated as such — this is exactly the boundary rule 14
> exists to enforce. It is a **fourth candidate execution-era boundary** if and when it lands
> (three exist — domain rule, standing question 4).

> ✅ **LANDED 2026-08-10 — `aeeaae36`, EXECUTION-ERA BOUNDARY #4 MINTED, owed 57 CLOSED**
> ([[sources/session-20260810-fill-double-count]]).
>
> **This section's headline number was right and its bound was slightly wide.** The mechanism is
> now derived, not just observed: `calibrate_fills.py` measures `f` = how often the market crossed
> a hypothetical resting limit within its life; `invert_base_prob` solves `passive_base_prob` so
> **the hazard ALONE reproduces `f`**; `_poll_dry` then **also** ran `_sim_maker_cross` on the
> very event `f` counts — and because the hazard **only ever ran inside `if book:`**, it was
> **purely additive**. `1−(1−f)² = 2f−f² = **21.96%**` against the **11.66%** target, versus the
> **22.30%** measured here — **agreement to 0.34 pp**, from two computations with no shared
> mechanism.
>
> **One correction to this section:** the touch-end bound reads **1.88x**, not the **1.91x**
> stated above (`(2f−f²)/f` at the calibrated `f`; the limit as `f → 0` is exactly 2). The
> 20bps end (1.19x) and the **57% within 5bps** weighting both stand — the 57% was independently
> reproduced twice more, at **230/402 = 57.2%**.
>
> **The embargo in the paragraph above is NOT lifted.** Propagation into the 305 live corpus rows
> and the 432-bar cohort verdict remains **UNMEASURED**, and still **may not be cited against the
> hold**. Closing the defect does not close the propagation question.
>
> **Two residuals:** owed **57b** (recalibrate the residual hazard *conditional on no
> deterministic cross* — folds into 40b/XV-023) and **NEW owed 61** (MP-7 queue gating is now
> **inert**, created by this very fix and deliberately left unfixed so the change axis stays
> single).

### 4.6 The framing the audit retracted

> ⚠️ **CORRECTED DOWNWARD by the audit's own verify pass.** *"Hedging is 84% of the loss"* is
> **true of the LIFETIME ledger** — but it is **one already-fixed incident on one day**, not a
> standing per-entry cost. **Go-forward unpriced hedge cost is ~7% of fees.**
> **Do not size a fix off the 84%.**

---

## 5. THE SYNTHESIS THAT MATTERS

**Gross trading P&L before any fees is approximately ZERO, now by TWO independent methods:**

| Method | Gross | Population |
|---|---|---|
| **State identity** (`start + realized − cash − savings − reserve`) | **−11.66** | ~250 closed positions |
| **Full-book `fills.csv` reconstruction** (A1 corrected) | **−13.01** | **394** closed round trips |

against **382.59 of fees**.

**Two methods, no shared mechanism, agreeing to within 1.35 on a book that paid 382.59 in
costs.** The first is an identity over the state file; the second is an independent accumulation
over the fill ledger. [[sources/session-20260809-unbiased-economics]] computed the first; this
session's A1 correction produced the second **as a by-product of a bug fix**, which makes it a
genuinely independent check rather than a re-derivation.

**Independent corroboration, unchanged:**

| Instrument | Reading |
|---|---|
| OOF AUC | **0.43 – 0.48** (at/below chance) |
| Champion Brier | **0.24728** vs **0.25** coin |
| Postmortem MFE | median **0.18%** vs **~0.65%** round trip |

**And the direction of the sim's error is known:** the fill-sim inflation in §4.5 means **REAL
gross would be WORSE, not better.**

> ### The honest statement is: **gross edge ≤ 0.**
>
> The strategy has produced **no measurable gross edge across ~250–394 closed positions**, and
> **the entire loss is costs.**

**And the meta-finding, which is the reason both audits were worth running:**

> **Every distortion found in both audits runs the SAME direction: flattering.**
> **Zero instances were found of the bot understating itself.**

That is not a list of unrelated bugs. A measurement error is a coin flip; **eleven of them
landing on the same face is a process fact**, and it is filed as one:
[[concepts/self-flattery-gradient]].

---

## 6. What this session moves

**Moves:**
- [[synthesis/the-money-path-thesis]] — second independent method for gross ≈ 0 (**−13.01**), and
  the discovery that the **go/no-go tool** was printing the branch that says the problem is
  fixable without touching the signal.
- [[concepts/cost-truth]] — a cost tool blind to its largest cost event; full-book fees **374.96**
  vs the **59.23** the shipped tool sees.
- [[concepts/zero-is-not-a-reading]] — a new instance **on the sizing path**, now fixed with the
  correct discriminator (log once when the book cannot be read).
- [[concepts/false-green]] — 3,400 green tests over a fiction; and a **third** AST-over-grep pin.
- [[concepts/two-paths-one-quantity]] — *"drawdown"* on the **decide** rung: the gauge reports
  one derivation, the flatten fires on another.
- [[concepts/payoff-asymmetry]] — the corrected **median gross −0.0303%** on the full book.
- [[comparisons/stated-invariants-vs-audited-reality]] — three documented risk controls, inert.
- [[synthesis/governance-doctrine]] — **rule 15**, test-double fidelity.
- [[synthesis/owed-measurements]] — items **52–57** (severity-ordered docket).
- [[synthesis/open-contradictions-register]] — entries **22, 23, 24**.
- [[synthesis/documentation-drift-register]] — the D1 panel description; the test docstring that
  named the bug class it embodied.

**Does NOT move:**
- **The 08-02 nulls** (no entry-timing signal; no surviving bracket) — unmoved.
- **Nothing here licenses widening any gate.** In particular, A4's breaker question is filed as
  **owed adjudication**, not resolved ([[concepts/never-widen-a-gate]]).
- **The 432-bar cohort hold** — unmoved; §4.5's fill-sim finding is **unverified** in its
  propagation to the cohort verdict and cannot be cited against the hold.
- **[[concepts/payoff-asymmetry]] is still not refuted** — §5 restates the *mean*; the asymmetry
  describes the *shape*.

## Related
[[concepts/test-double-fidelity]] · [[concepts/self-flattery-gradient]] ·
[[concepts/uncounted-exclusion]] · [[concepts/pooled-populations]] ·
[[concepts/zero-is-not-a-reading]] · [[concepts/false-green]] ·
[[concepts/two-paths-one-quantity]] · [[concepts/adversarial-verification]] ·
[[concepts/cost-truth]] · [[concepts/never-widen-a-gate]] · [[concepts/paper-real-boundary]] ·
[[sources/session-20260809-unbiased-economics]] · [[sources/session-20260807-pnl-reconciliation]] ·
[[sources/session-20260807-hedge-churn-guards]] · [[entities/observability-sidecars]] ·
[[entities/liquiditybot]] · [[synthesis/owed-measurements]] ·
[[synthesis/open-contradictions-register]] · [[synthesis/the-money-path-thesis]]
