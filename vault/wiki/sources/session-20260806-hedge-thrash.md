---
title: "The Hedge Open/Unwind Thrash (2026-08-06) — 147 Round Trips Because Two Code Paths Tested Two Different Pairs"
category: source
summary: "Commit 5c111962. LIVE-PROCESS INCIDENT 20:09:40-20:34:19 LOCAL (= 01:09-01:34Z 08-07 — panel-corrected 2026-08-07: the SAME ledger event the churn-guards page filed as 'incident #2'; this fix was committed 19 minutes AFTER it ended): the hedger opened and unwound an ADA/USD hedge 147 times — 294 fills, $72,433.15 of notional on a $4,933 book (14.7x equity), $289.73 of fees; panel-paired gross -13.37 on 149 laps = ~95.7% fees. The open path gated on corr(exposed, hedge_asset) = corr(ETH,ADA) >= 0.55; the unwind path tested corr(hedge_asset, others[0]) = corr(ADA,ARB) = 0.00 — the alphabetically-first OTHER asset, an unrelated pair. Second thrash of this exact shape in this one file. Fixed with a shared _exposure_by_asset() helper so both paths read one definition of 'which asset are we exposed to'; 12 residual warm-correlation laps outlived it until cf454d5e. Paper mode (system.dry_run=True): the mechanism and the 294 orders are real, the dollars are simulated at a 40 bps taker constant that matches no row of Kraken's current schedule."
tags: [session, incident, hedging, defect-class, thrash, cost, execution, duplicate-computation]
sources: 1
source_path: none — session work product (see Provenance)
source_date: 2026-08
authors: [claude]
ingested: 2026-08-06
updated: 2026-08-07
---

# The Hedge Open/Unwind Thrash (2026-08-06)

> ⚠️ **SUPERSEDED IN PART — 2026-08-07 institutional review + filing-session ledger
> verification ([[sources/session-20260807-institutional-review]] §A/§B).** Three corrections
> travel with this page:
> **(1) The timestamps below are LOCAL (UTC−5), not UTC.** The window "2026-08-06
> 20:09:40–20:34:19" is **01:09:40–01:34:19Z on 2026-08-07** — the *same wall-clock window*
> that [[sources/session-20260807-hedge-churn-guards]] filed as "incident #2". Verified:
> `fills.csv` holds **159 lifetime hedge fills, all 2026-08-07 UTC** (zero on 08-06 UTC), and
> `equity.csv` reads 4,933.68 at 08-06 23:59:50Z — impossible if this event had closed at
> 20:34Z 08-06. **This page and the churn-guards page describe ONE ledger event, filed twice
> under two clock conventions.** The two filings' slightly different tallies ($289.73 vs
> $296.93 fees; 294 vs 290/296 fills) are windowing variants of the same laps; the panel's
> canonical window is **01:09:00–01:34:59Z = 294 fills = 147 laps**.
> **(2) The fix below was committed AFTER the event ended** — `5c111962` at 01:53:17Z
> (nineteen minutes after the last fast lap), deployed 02:08:09Z — and **12 residual laps at
> warm correlations (0.34–0.55) outlived it** until `cf454d5e`'s cooldown/latch: the panel's
> two-mechanism ruling.
> **(3) "Gross price P&L ≈ 0 / fees = 95.6%" refines to: gross −13.37 on 149 paired laps,
> fees 301.31 — ~95.7% fees, ~4.3% crossing cost.** The "40 bps vs Kraken's published 26"
> comparison below is also stale: **25/40 matches no row of Kraken's current schedule**
> (Tier 1 is 40/80) — see [[concepts/cost-truth]].

## Provenance

Session work product — no `raw/` snapshot. **One** commit on the working checkout
`liquiditybot_ab`, **head = `5c111962`**, parent `0e30ca09`. **3 files, +203 / −14**:
`execution/hedging.py`, `tests/test_hedge_thrash.py` (new, 146 lines), and
`tests/test_append_invariant.py` (an unrelated tightening carried in the same commit — see §7).

**Every number on this page below was re-derived from `outputs/fills.csv` and
`outputs/equity.csv` at filing time, not copied from the commit message.** The two agree to the
cent.

> ⚠️ **PAPER MODE.** `system.dry_run = True` and `outputs/force_dry.on` is present. The commit
> message's "LIVE INCIDENT" means **the live running process, not a harness** — it is *not* real
> money. **The 294 orders, the 5-second cadence and the mechanism are real; the $289.73 is
> simulated**, priced at the repo's deliberately overstated `pretrade.taker_fee_bps = 40` against
> Kraken's published 26 ([[concepts/cost-truth]] — paper may only err *against* the strategy).
> At the published rate the same churn is **$188.33**. The dollar figure is therefore an upper
> bound by policy, and the *shape* — near-total capture of the window's equity change by fees —
> is rate-independent.

---

## 1. The incident, measured

**Window:** 2026-08-06 **20:09:40.459 → 20:34:19.303**, **24.65 minutes**.

| Quantity | Measured |
|---|---|
| ADA/USD hedge-cycle fills | **294** — exactly **147 opens** + **147 unwinds** |
| Other fills in the window | **0** — *the entire 25 minutes of trading was the loop* |
| Notional churned | **$72,433.15** — **14.7x** the account's own equity |
| Fees | **$289.73** (median **40.00 bps per fill**, **80 bps per round trip**, **$1.97** per round trip) |
| Equity | **$4,934.22** (20:09:20) → **$4,632.30** (20:34:49); commit's endpoints $4,933.29 → $4,630.22, **drop $303.07** |
| Fees as a share of the drop | **95.60%** |
| Median cycle spacing | **5.0 s** — the fast cycle; the hedger runs every one |
| Median slippage | **2.03 bps** |
| `post_only` | **0 on all 294** — marketable limits by design (F6 Rule 534 self-cross guard), so **both legs pay taker** |
| Hedge notional per fill | decayed **$365.20 → $126.63** as the beta estimate and equity fell |

Verbatim from the ledger's own `reason` column, repeated 147 times each:

```
hedge  sell  reason="net delta +1,086 beyond cap 932, beta=0.18"
exit   buy   reason="hedge unwind: correlation 0.00 below floor"
```

> **The book never changed.** No entry, no exit, no signal fill in 25 minutes. Net delta stayed
> at **+1,086** against a cap that drifted **932 → 927** only because equity was being burned by
> the loop itself. **The two code paths simply disagreed forever.**

---

## 2. The mechanism — the asymmetry, at source

`execution/hedging.py`, before the fix:

| Path | Question it asked | Reading | Verdict |
|---|---|---|---|
| **open** | `corr(exposed, hedge_asset)` — the exposed asset against the asset being hedged with | corr(ETH, ADA) **≥ 0.55** | open |
| **unwind** | `corr(a, others[0])` — the **hedge's own asset** against **the first OTHER asset alphabetically** | corr(ADA, ARB) = **0.00** | unwind |

`others[0]` was *"the alphabetically-first asset that is not the hedge asset."* **It has no
relationship to the exposure the hedge exists to offset.** The open path asked the right
question; the unwind path asked about two unrelated coins. Net delta was still beyond cap after
the unwind, so the open fired again — at the next 5-second cycle, forever.

**Why ADA and why ARB, precisely.** Both are consequences of the same alphabetical tiebreak:
`hedge_asset = others[0]` picks the alphabetically-first **non-exposed** asset (**ADA**), and the
old unwind's `others[0]` then picks the alphabetically-first **non-hedge** asset (**ARB**).
*The hedge was chosen by one alphabetical accident and killed by a different one.*

### The second mechanism underneath: 0.00 was "no data", not "decorrelated"

`regime/correlation.py:40-41` — `corr(a, b)` returns **`0.0` for any pair it has never seen**,
and `_EwmaCov.corr` returns **`0.0`** whenever either variance is `<= EPS` (a cold engine, a
fresh process, an asset with no return history). **The missing-data sentinel is a number that
sits on the failing side of every correlation floor.** `0.00 < 0.55` fires the unwind with the
same force as a genuine decorrelation, and the reason string it writes —
`"correlation 0.00 below floor"` — is *literally true and completely misleading*. Filed as
[[concepts/zero-is-not-a-reading]].

The same file already knew about this hazard **one gate over**: `beta()` also returns `0.0` for
an unknown pair, and the open path has an explicit `beta_floor` that converts an unreliable beta
to `1.0`. **Same file, same class, same day: one call site defended, the other not.**

---

## 3. The fix

The unwind now tests `corr(DOMINANT SIGNAL EXPOSURE, this hedge's asset)` — **the exact quantity
the open gated on** — via a new shared helper:

- **`HedgeEngine._exposure_by_asset(state, marks)`** returns signed **signal-side** USD exposure
  per asset, hedges excluded. **Both paths now call it**, so *"which asset are we exposed to"* has
  **one definition in the file**. `dominant` (unwind) and `exposed` (open) are the same
  `max(|exposure|)` over the same dict, so they cannot differ.
- **`dominant is None` or `dominant == a`** → `corr = 1.0`, i.e. **correlation must not force an
  unwind when there is no pair left to measure**; the *"signal delta normalized"* arm owns the
  empty-book case.

> **The property that matters is not "use the right assets" — it is that the two paths AGREE.**
> When the correlation engine is cold, the old code **opened on a warm reading and unwound on a
> cold one**. The new code reads the same pair on both sides: it either **opens and keeps**, or
> **never opens** ("hedge skipped: corr(...) < floor"). *It cannot oscillate.* Correctness of the
> asset choice is a separate, still-open question (§6).

---

## 4. This is the SECOND thrash of this exact shape in this one file

`evaluate()`'s `signal_net` comment documents the first, still in the source:

> the unwind test used to read **TOTAL** net delta — but *a correctly-sized hedge is exactly what
> pulls total net into the band*, so the hedge **unwound itself the moment it worked** → net back
> out of band → re-open → thrash. Especially whenever beta ≥ 1 (the ETH-hedged-with-BTC case).

**Same file, same function, same failure, different quantity:**

| | Thrash #1 (`signal_net`) | Thrash #2 (`5c111962`) |
|---|---|---|
| Quantity computed two ways | **net delta** — total vs signal-only | **correlation** — which *pair* |
| Open read | total `net` vs cap | `corr(exposed, hedge_asset)` |
| Unwind read | total `net` vs band | `corr(hedge_asset, others[0])` |
| Fix shape | split the quantity, name the two explicitly | **extract one helper both paths call** |

That is why the fix is a **shared helper** and not a corrected pair of asset names: correcting
the arguments fixes the instance, extracting the definition is the only move that addresses the
class. Filed as [[concepts/two-paths-one-quantity]].

> **Note the surviving deliberate asymmetry, so a future reader does not "fix" it.** The open
> still tests **total `net` vs `cap` (20% of equity)** while the unwind's normalization arm tests
> **`signal_net` vs `band` (8%)**. That is **hysteresis on purpose** — two quantities *and* two
> thresholds, documented in the `signal_net` comment, and it is what thrash #1's fix installed.
> **A designed disagreement carrying its reason is not the defect; an undocumented one is.**

---

## 5. Adversarial verification of the tests — one of them is green on the buggy code

The commit ships `tests/test_hedge_thrash.py`, 5 tests. **Filing ran them against the PARENT's
`execution/hedging.py`** (reconstructed in a scratch tree; the live checkout was not touched, the
module imports only `logging` and `dataclasses`). Result: **3 failed, 2 passed** — and against
the fixed module, **5 passed**.

| Test | On the buggy code | Verdict |
|---|---|---|
| `test_a_live_hedge_is_not_unwound_on_an_unrelated_correlation` | **FAILED** | the genuine red-first test; this is the incident, pinned |
| `test_no_dominant_exposure_defers_to_the_normalized_arm` | **FAILED** | real discriminator |
| `test_exposure_helper_excludes_hedges_and_is_shared` | **FAILED** (`AttributeError`) | it tests the helper's **existence**, not that both paths **use** it — see §6.1 |
| `test_a_genuinely_decorrelated_hedge_is_still_unwound` | **passed** | expected: an anti-rubber-stamp guard, never a discriminator |
| `test_open_and_unwind_agree_across_repeated_evaluations` | **passed** | ⚠️ **vacuous — see below** |

> ⚠️ **The test whose docstring says *"The actual money bug"* is green on the code that caused
> the incident.** `evaluate()` is a **pure function of an unmutated state**, and the test **never
> applies the actions it collects** — so `seen` can only ever hold **one** element, for **any**
> implementation. On the buggy code it collects the same single `unwind` action 25 times and
> asserts `len(seen) == 1`. **It passes.** It does not test oscillation; it tests determinism.
>
> This is the repo's own standard from the commit **one earlier**: *"A gate never shown to fail
> is a gate whose passing means nothing"* ([[concepts/adoption-is-not-enforcement]], design rule
> 5 — the append gate was proven to bite by injecting a bare append). **The discipline was
> stated on 08-06 and not applied to the next commit's headline test on 08-06.**
>
> **What would make it real:** apply the returned actions to the state between iterations (open
> → add hedge position, unwind → remove it) and assert the book reaches a fixed point. The other
> three tests do cover the incident, so **the commit is protected — by its supporting tests, not
> by the one named after the bug.**

---

## 6. What this fix does NOT close — residuals, verified not speculated

1. **There is no gate for this class.** The shared helper is a **convention**.
   `test_exposure_helper_excludes_hedges_and_is_shared` **asserts sharing in its name only** — it
   calls `_exposure_by_asset` directly and checks that the hedge leg is excluded and
   `exp["ETH"] == 2000.0`. **Nothing fails if a future author re-inlines a second exposure
   computation** in either path. This is [[concepts/adoption-is-not-enforcement]] **one day after
   that concept was created**, and it is the same distance the append gate closed for its own
   class: *"we fixed both paths"* ≠ *"a third definition cannot appear."*
2. **The hedge asset is still chosen alphabetically.** `hedge_asset = others[0]` — the fix makes
   both paths **agree about an arbitrary choice**; it does not make the choice good. ADA was
   hedged with because **A sorts first**, not because it was the best offset in a
   seven-asset universe (`PAXG, ETH, BTC, SUI, ARB, MINA, FLOW`). The `min_hedge_correlation`
   floor is the only thing standing between the alphabet and the book.
3. **No cooldown, no rate limit, no churn breaker — anywhere.** `_run_hedge_pass` runs **every
   fast cycle (~5 s)**; `self.orders.has_open(act.asset, "hedge")` prevents only **concurrent
   duplicate** opens, never **sequential re-opens** after an unwind. **Any future disagreement
   thrashes at the same 5-second cadence with nothing to stop it.** This commit adds no such
   guard.
4. **The one automated per-asset protection is structurally blind to this.**
   `risk/circuit_breaker.py` trips after 4 **consecutive full-trade losses** on an asset and
   vetoes **new entries** — but `main.py:1588` guards both it and the rolling performance ledger
   with **`if not pos.is_hedge:`** (deliberate: *"a hedge's P&L is not a verdict on the gates that
   opened the position it protects"*). **147 consecutive losing hedge round trips on one symbol
   were invisible to the breaker whose stated purpose is to pull a misbehaving symbol off the
   sheet.** The exclusion is correct for *attribution* and leaves a hole for *churn*.
5. **The thrash fills bypass the honest-fill regime.** All 294 were `post_only=0`, i.e.
   **marketable** — the one order class not subject to the post-`8e5455e8` measured passive fill
   probability (0.048). **The bug spammed precisely the order class that fills at ~100% in
   paper** ([[synthesis/risk-posture-doctrine]]), which is why 25 minutes was enough to move
   equity 6%.
6. **The shipped in-code comment now understates the incident by roughly half** — see §7.

---

## 7. Two documentation notes carried in the same commit

**(a) The comment and test docstring are a mid-incident snapshot.** Both
`execution/hedging.py`'s new unwind comment and `tests/test_hedge_thrash.py`'s module docstring
record **"121 times… 246 fills… ~$143 of spread in 21 minutes"** and realized P&L
**−$43.84 → −$186.78**. The commit message and the ledger record the **final** tally: **147 round
trips, 294 fills, $289.73, 24.65 minutes**. The incident kept running while the fix was being
written. **The shipped source now carries the smaller, superseded numbers** — filed to
[[synthesis/documentation-drift-register]] so the next reader of that comment does not quote it
as the incident. (The docstring's own "121 times / 246 fills" is also internally inconsistent by
two fills.)

**(b) An unrelated tightening rode along.** `tests/test_append_invariant.py` gained three entries
to the positive `durable_append` assertion list — **`scripts/corpus_sync.py`**, `core/runtime.py`
and `main.py` — with a docstring explaining exactly why `corpus_sync` is not merely the
complement of the allowlist: it is **exempt per-FILE for its `:57` text log while being the
corpus's second independent data appender at `:160`**. **That closes residual (a) of
[[sources/session-20260806-append-gate]] / [[synthesis/owed-measurements]] item 31**, the day
after it was written — though the underlying **per-file vs per-call-site** granularity of the
allowlist is unchanged.

---

## 8. What this session changes elsewhere in the wiki

- **New concept — [[concepts/two-paths-one-quantity]].** The root-cause class, with this file's
  two thrashes as the type specimen and the shared-helper fix as the only move that addresses the
  class rather than the instance.
- **New concept — [[concepts/zero-is-not-a-reading]].** A missing-data sentinel that is a valid
  value on the failing side of a gate; `corr()` → `0.0`, and three sibling instances already in
  the corpus.
- **[[concepts/adoption-is-not-enforcement]]** — an immediate second instance, one day old: this
  commit fixed the instances and shipped **no gate for the class**.
- **[[concepts/iron-law-of-debugging]]** — two corollaries: the mechanism was nameable **only
  because the ledger's `reason` column recorded both sides of the disagreement verbatim**, and a
  test named for the money bug can be **green on the buggy code**.
- **[[comparisons/stated-invariants-vs-audited-reality]]** — a new row: `hedging.py`'s own module
  docstring states the unwind rule, and the code measured a pair the docstring never names.
- **[[synthesis/the-money-path-thesis]]** — a live-process demonstration of the cost thesis:
  **95.6% of a 25-minute equity drop was fees**, from a book that took **no position at all**.
- **[[synthesis/owed-measurements]]** — new item 34 (the four residuals of §6); item 31's
  residual (a) closes.
- **[[synthesis/documentation-drift-register]]** — the superseded in-code numbers.

---

## 9. SEQUEL (2026-08-07) — rewritten after the panel's timeline adjudication

~~"The churn recurred the same night with this commit's fix holding — 147 more laps."~~
**CORRECTED ([[sources/session-20260807-institutional-review]] §B): there was no second
147-lap event.** The "01:09:45–01:34:19Z incident" filed the next day **is this page's own
event in UTC** (see the banner). What genuinely happened after this event ended: this fix was
committed 01:53:17Z and deployed 02:08:09Z, and a **12-lap residual tail (01:56Z–11:35Z) ran
at warm, genuine correlations 0.34–0.55 below floor** — proving the *second* mechanism
(open-on-delta vs unwind-on-correlation, no shared deadband) outlived the pair fix and needed
`cf454d5e`'s cooldown/latch. Both mechanisms were live during the one fast event: this page's
wrong-pair defect (pre-fix code) **and** the cold post-restart EWMA (~01:00Z restarts)
flapping |rho|≈1 ↔ 0.0 ([[concepts/zero-is-not-a-reading]]). §6.3's sentence — *"any future
disagreement thrashes at the same cadence with nothing to stop it"* — remains the accurate
prediction the residual tail confirmed. Full guard fix:
[[sources/session-20260807-hedge-churn-guards]].

Dispositions of this page's residuals: **§5/§6-adjacent vacuous test — CLOSED** (`af544d4c`,
the fixed-point rewrite, proven red at 13 opens/12 unwinds against the parent blob);
**§6.3 churn breaker — CLOSED** (`cf454d5e`: warmup evidence gate `corr_min_samples` 12,
per-asset re-hedge cooldown 600s, **FW-070** latch 3-in-900s with auto-release on window+warm —
opens only, unwinds never gated, per [[concepts/deadlock-discipline]]); **§6.1 no gate for the
class — OPEN** (owed 34a); **§6.2 alphabetical hedge-asset choice — OPEN** (owed 34d).

## Re-measured 2026-08-09 — the cost of this event, finally sized

([[sources/session-20260809-turing-test-hedge-verdict]] §2. **Same event.** A fresh ledger sweep
returned this window independently and the double-filing reconciliation
[[synthesis/open-contradictions-register]] entry **19** held on first contact — no third incident
page was opened.)

| | |
|---|---|
| Window | **2026-08-07 01:09–01:34Z** (= this page's "08-06 20:09–20:34" local) |
| Round trips | **147**, ADA/USD hedge, **all 2-leg** |
| Held exactly **5.000s** | **59** |
| Notional | **$36,210** |
| Fees | **$289.73** |
| **Share of ALL lifetime fees** | **77.3%** (denominator **$374.96**) |
| Gross P&L | **−$12.77** |
| Recurrence | **none in 56.5h** |

> **77.3% of everything this book has ever paid in fees was spent here, in 25 minutes.** That is
> the number this page was missing. It was previously sized only in dollars (−$186.78 → the
> commit's final −$303 tally) with no denominator.

⚠️ **Do not merge the fee figures.** **$289.73** covers the **147 matched 2-leg round trips**;
[[sources/session-20260807-hedge-churn-guards]] records **$296.93** over **290 fills** for
**01:09:45–01:34:19Z**. The **$7.20** gap is *consistent with* unmatched/out-of-window legs — **an
inference, not a measurement.** And **77.3%** uses the **$374.96** corrected lifetime-fee total;
at the **$382.59** state-identity total it reads **75.7%** ([[concepts/ratio-aggregation-bias]]).

**The 59 exactly-5.000s holds are also the strongest MECHANICAL machine-tell in the whole corpus**
— a timer-perfect hold time is what a churn loop looks like from the ledger side
([[comparisons/bot-vs-discretionary-vs-algo-trader]]).

**What this does NOT rescue:** removing the churn does not create an edge. The book's gross edge is
**~0 (t = −0.332)** independently, and this event's own gross was only **−$12.77**
([[synthesis/the-money-path-thesis]]).

## Related
[[sources/session-20260809-turing-test-hedge-verdict]] ·
[[comparisons/bot-vs-discretionary-vs-algo-trader]] ·
[[concepts/ratio-aggregation-bias]] · [[synthesis/open-contradictions-register]] ·
[[sources/session-20260807-hedge-churn-guards]] ·
[[sources/session-20260807-institutional-review]] · [[concepts/paper-real-boundary]] ·
[[sources/session-20260806-append-gate]] · [[sources/session-20260806-geometry-filing]] ·
[[concepts/two-paths-one-quantity]] · [[concepts/zero-is-not-a-reading]] ·
[[concepts/adoption-is-not-enforcement]] · [[concepts/iron-law-of-debugging]] ·
[[concepts/adversarial-verification]] · [[concepts/cost-truth]] · [[concepts/priced-bleed]] ·
[[concepts/never-widen-a-gate]] · [[comparisons/stated-invariants-vs-audited-reality]] ·
[[comparisons/harness-vs-live-cost-stack]] · [[synthesis/the-money-path-thesis]] ·
[[synthesis/risk-posture-doctrine]] · [[synthesis/owed-measurements]] ·
[[synthesis/documentation-drift-register]] · [[entities/liquiditybot]] ·
[[entities/pretrade-gate]] · [[entities/reason-code-registry]]
