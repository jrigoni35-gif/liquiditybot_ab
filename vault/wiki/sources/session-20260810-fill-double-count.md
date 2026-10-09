---
title: "The Fill Sim Counted One Crossing Twice — owed 57 CLOSED, EXECUTION-ERA BOUNDARY #4 (aeeaae36)"
category: source
summary: "Owed 57 CLOSED and execution-era boundary #4 minted by aeeaae36. MECHANISM confirmed three independent ways (own derivation, the calibration source, and the vault's own 2026-08-07 log entry, which had already named it before it was wrongly disposed on 08-08): calibrate_fills.py measures f = how often the MARKET crossed a hypothetical resting limit within its life, invert_base_prob solves passive_base_prob so the HAZARD ALONE reproduces f, and _poll_dry then ALSO called _sim_maker_cross on the very event f counts — and because the hazard only ever ran INSIDE `if book:` it modelled nothing the snapshot could not already show, making it purely additive. Combined 1-(1-f)^2 = 2f-f^2 = 21.96% vs the 11.66% target against a ledger-measured 22.30% — 0.34pp. 1.88x at the touch, approaching 2x as f FALLS, worst exactly where the book rests. BLAST RADIUS measured before any change: 402 post_only fills, 57.2% within 5bps, 154/401 positions (38.4%) opened by a near-touch post_only leg. FIX: the observed book is ground truth; config_guard WARNs (deliberately not FATAL — a FATAL would make the pre-#4 cohort unreproducible hence unauditable). NEW OWED 61: MP-7 queue gating is now INERT and deliberately unfixed. NEW SPECIMEN CLASS, arguably the more valuable half: FOUR FULL-ENGINE TESTS WERE PASSING ON LUCK — an over-generous simulator MASKS test fragility, so making a model honest surfaces flakiness that was always there. Four self-caught agent errors filed."
tags: [fill-model, execution-era-boundary, sim-integrity, retraction, self-flattery, test-fragility, owed-closure]
sources: 1
updated: 2026-08-10
source_path: "repo — commit aeeaae36 (working tree at C:\\Users\\haird\\Documents\\liquiditybot\\liquiditybot_ab)"
source_date: 2026-08
authors: [operator, claude-code]
ingested: 2026-08-10
---

# The Fill Sim Counted One Crossing Twice — owed 57 CLOSED, era boundary #4

**Commit:** `aeeaae36` — *"fix: the fill sim counted one market crossing twice - era boundary #4"*
**8 files, +309/−12.** Pushed; `origin/main == aeeaae36` verified at filing.

> ⚠️ **BOUNDARY TIMESTAMP — ZONE-STAMPED, and it disagrees with the shipped documentation.**
> Git author *and* committer stamp: **`2026-08-10 06:03:35 −05:00` = `2026-08-10T11:03:35Z`.**
> The operator's session framing, `config.json`'s `_passive_hazard_with_book_doc`, and
> `core/config_guard.py`'s comment all say **2026-08-09**. The session is continuous with the
> 08-09 evening work (the two preceding commits are `2026-08-09 16:06:5x −05:00`), so the
> *narrative* date is defensible — but a **cohort cut is an arithmetic operation on a
> timestamp**, and the arithmetic one is 08-10. Filed as a drift row
> ([[synthesis/documentation-drift-register]]); domain rule 9 exists for exactly this
> (one churn was double-filed purely by local-vs-UTC rendering,
> [[synthesis/open-contradictions-register]] entry 19).
>
> **Blast radius of the wrong date is small and measured, not assumed:** a naive
> `2026-08-09T00:00Z` cut would misclassify **4 ledger rows** (0 `post_only`, 2 entries) as
> post-boundary. Use the stamp anyway — [[concepts/exact-or-refuse]].

> **The boundary is a CLEAN CUT: there is no post-boundary fill population yet.** Last row in
> `outputs/fills.csv` is `ts=1786344623.746` = **2026-08-10T06:50:23.746Z**, i.e. **before** the
> commit stamp. **Zero fills at or after `aeeaae36`.** Every fill in the corpus is a pre-#4 fill.
> The runner did bounce onto the corrected code — `runner.log` shows
> `runner starting: DRY state=RUNNING … resumed=True` at **2026-08-10 06:06:01 local**, 2m26s
> after the commit — so the *next* fill is the first honest one.
> (`outputs/pushers_code_rev.txt` still reads `f11b7e32`: the telemetry sidecars lag one
> `auto_update` cadence by design, `scripts/auto_update.py:413-445`. Known mechanism, not a new
> defect — but it means any gauge read right now is emitted by pre-`aeeaae36` pusher code.)

---

## 1. The mechanism — confirmed three independent ways

Owed 57 was registered from the 08-09 adversarial audit as a *measured rate discrepancy*
(22.30% observed vs 11.66% target) with the mechanism stated but not derived. It is now derived,
and the derivation agrees with two prior independent statements of the same thing.

**(i) The calibration source.** `scripts/calibrate_fills.py` measures

> **f = "how often the MARKET actually crossed a hypothetical resting limit within its life"**

from **recorded book frames**. `core.fill_calibration.invert_base_prob` then solves
`passive_base_prob` so that **the hazard ALONE reproduces f** over `n_bar` polls:

```
p_poll  = 1 − (1 − f)^(1/n_bar)
sf_base = p_poll · exp(d_bar)
```

The inversion is the whole point: `sf_base` is *defined* as the value that makes the stochastic
path reproduce the measured crossing frequency by itself.

**(ii) The second path fired on the same event.** `_poll_dry` **also** called `_sim_maker_cross`,
which fills the **full remaining deterministically whenever the book crosses** — *the very event
`f` counts*.

**(iii) The decisive structural fact — and the one that kills the 08-08 "conservative floor"
defence:** the hazard only ever ran **INSIDE `if book:`**. It therefore **modelled nothing a
snapshot could not already show.** It was not a floor under an unobserved event; it was **purely
additive to an observed cross.**

**Combined per-order rate:**

| quantity | value |
|---|---|
| two independent chances at the same event | **1 − (1−f)² = 2f − f²** |
| computed at the calibrated f | **21.96%** |
| calibration target | **11.66%** |
| **ledger-measured realized rate** | **22.30%** |
| **agreement between derivation and ledger** | **0.34 pp** |

**Ratio: 1.88x at the touch, approaching 2x as f FALLS** — i.e. the distortion is **worst exactly
where the book actually rests.** (As f → 0, (2f−f²)/f → 2.)

> **A derived quantity landing within 0.34pp of an independently measured one, with no shared
> mechanism, is the strongest form of confirmation this corpus accepts.** The derivation came
> from the calibrator's algebra; the 22.30% came from counting the fills ledger.

### The vault had already named this — on 2026-08-07 — and then talked itself out of it

[[sources/session-20260807-fleet-findings]] §1, filed 2026-08-07 night, states it exactly:

> *"That crossing condition is **the same trade-through predicate `calibrate_fills.py`
> measured**… so the calibrated trade-through frequency is **spent twice**."*

**The next morning it was disposed of.** [[sources/session-20260808-morning-batch]] §1 recorded
owed 40's sub-item (b) as *"disposed by design"* — `_sim_maker_cross` reframed as *genuine
trade-through*, the hazard as a **conservative floor** on top.

> ⚠️ **THAT DISPOSITION IS RETRACTED.** The hazard was **not a conservative floor**. A floor
> would model something the observation cannot see; this ran *only when the observation was
> present*. And because `invert_base_prob` had already solved `sf_base` so the hazard alone
> reproduces `f`, adding it to the deterministic cross does not add conservatism — **it spends
> the calibrated frequency a second time.** The 08-08 framing was not merely incomplete, it was
> **backwards**, and it kept a 1.88x bias alive for two days after the vault had correctly named
> it. Filed as [[synthesis/open-contradictions-register]] entry 25 and as a first-class
> retraction per domain rule 3.

**The lesson is about disposal, not about fills.** A finding that survives discovery can still be
lost at the *disposition* step, and a disposition written in the same session as a celebrated fix
is written by an author with a motive to close the docket. See
[[concepts/self-flattery-gradient]] — the flattering direction reached the *adjudication*, not
just the measurement.

---

## 2. Blast radius — measured BEFORE any change

Read from `outputs/fills.csv` prior to touching the simulator, and **re-verified independently at
filing time**:

| quantity | value | filing check |
|---|---|---|
| `post_only` fills | **402** | reproduced exactly (402) |
| …resting **within 5 bps** | **57.2%** | reproduced exactly (**230/402 = 57.2%**) |
| positions opened by a near-touch `post_only` leg | **154 of 401 = 38.4%** | as reported |
| …within **1 bps** | **20.4%** | as reported |

The 57.2% independently reproduces the **57%** already on record from the 08-09 audit — two
computations of the same figure agreeing is what licenses using it as the weight in "weighted
toward the high end."

**Why the weighting matters:** the distortion is 1.19x at 20bps and 1.88x at the touch, and
**57.2% of the affected population sits within 5bps of it.** The bias is not a tail effect; it
is concentrated on the modal case.

---

## 3. The fix — the observed book is ground truth

`execution/order_manager.py`:

- **`:275`** — `self.sf_hazard_with_book = bool(sf.get("passive_hazard_with_book", False))`
- **`:1308`** — `if _fin_pos(mid) and queue_ok and self.sf_hazard_with_book:`

With a book in hand, **the cross at `:1288` decides the event and the hazard does not fire.**

**`passive_hazard_with_book: true` restores the pre-boundary simulator EXACTLY** — a *time
machine, not a knob* — so a pre-#4 cohort stays reproducible. `config.json:375` ships it
**`false`**, with `:376` `_passive_hazard_with_book_doc` carrying the full derivation, the
magnitude, and an explicit *"must never be set true to recover entry volume."*

### config_guard WARNs, and the reason it is not FATAL is a doctrine

`core/config_guard.py:471-480` emits a **WARN**, not a FATAL, and the warning **carries the
magnitude** (`2f−f²` vs `f`, `22.0% vs 11.66%`, `~1.88x at the touch`), not just the key name.

> **A FATAL would make the pre-boundary cohort unreproducible — and therefore unauditable.**
> Reproducing a superseded regime is a *legitimate* operation; gating it fatally would trade
> auditability for tidiness. This is the counterweight to [[concepts/never-widen-a-gate]]: the
> rule forbids loosening a gate to admit *results*, not forbidding a documented reproduction
> mode for *past* results. Filed on [[entities/config-guard]].

### The expected consequence, stated in the config so it is not read as a regression

> **The paper fill rate roughly HALVES near the touch.**

That is the **honest rate**, and starving is the truthful outcome — the same warning the
**2026-07-21 `queue_aware`** `_doc` and the **2026-08-02 `passive_base_prob`** change both
carried. Third time this project has shipped a fill-model correction whose visible effect is
*fewer trades*, and third time the expected drop was written down **before** it happened
([[synthesis/risk-posture-doctrine]]).

### Tests

`tests/test_fill_double_count.py` — **7 tests**, count verified by reading the file, not claimed
from the commit message:

1. a crossed book still fills deterministically **at our price, as maker** (the fix must not cost
   the real mechanism)
2. an uncrossed book **no longer grants a second chance** (the defect itself)
3. the legacy path is **exactly reproducible**
4. the double-count is **measurably gone** (crossed-only == combined)
5. the default is corrected **with the key absent** (a silent default flip would re-mint the bias)
6. the shipped `config.json` has the boundary **off**
7. `config_guard` **warns** when the old model is restored

> **Contrast with the 08-08 filing**, where the commit message claimed 8 tests and collection said
> 7 ([[synthesis/owed-measurements]] item 40). This time the count was checked before filing and
> is correct. Same instrument, applied to the same author.

**Battery ALL GREEN:** pytest **3518+19**, smoke **219**, assurance **49**, overfit **3/0**,
quant **G1-G5 all pass**, ruff, pyright 0.

---

## 4. NEW OWED 61 — MP-7 queue gating is now INERT, and was deliberately NOT fixed

`queue_ok` is computed at `order_manager.py:1302-1304` and **consumed at exactly one site**:
`:1308`, the hazard branch. With the hazard no longer firing while a book is present,
**`queue_aware: true` in `config.json` now protects nothing** — `_sim_maker_cross` fills the
**full remaining with no depth constraint**, exactly as it always did.

**Pinned by `tests/test_sim_fill_queue.py:182 test_queue_gate_is_inert_on_the_default_path`**, so
the inertness stays **visible** rather than implied. The gate's own test file now sets
`passive_hazard_with_book=True` in its fixture (`:33`) — *a gate needs the path it gates to
exist*.

> **The reason it was not fixed in the same commit is the filable part.** Wiring the gate onto the
> cross is *physically right* (a trade-through fills the queue in order) — but it is a **second
> uncalibrated change to a learning system's fill model**, and compounding both in one commit
> would make any later corpus change **impossible to attribute**. One era boundary per commit.
> This is [[concepts/lever-coupling]] applied prospectively, and the same discipline as
> [[concepts/inertness-protocol]]: keep the change axis single so the next measurement has a
> clean counterfactual.

**This is a [[comparisons/dormant-vs-inert-features|dormant-vs-inert]] specimen with a twist:**
the feature was *live and load-bearing* until a correctness fix elsewhere removed its only
consumer. **Inertness can be created by a fix, not only by a bug** — and the only thing standing
between "inert" and "silently believed" is the test that names it.

---

## 5. NEW SPECIMEN CLASS — four full-engine tests were passing on luck

**Arguably the more valuable half of this commit.**

The old hazard granted a fill on **essentially any book**. That generosity **hid** the fact that
four full-engine cases in `tests/test_bracket_exits.py` depended on a **random walk happening to
dip through a resting bid**.

**The evidence that it was luck, not design:** one 4-file combination **FAILED once, then PASSED
three times, with only COMMENTS changed between runs.**

**Fix:** a **driftless 90-cycle walk**, so the market gets real opportunities to reach the order.
**Verified stable 3x** in the exact combination that flushed the flake.

> **The rejected alternative is instructive.** A **negative** drift also fills them — but it walks
> price far enough that **FW-050's 100bps collar rejects the entry**. The test would then pass
> **for a reason unrelated to its subject** — a green that proves the collar works, not that the
> bracket exits work. Rejecting a working fix because it passes for the wrong reason is
> [[concepts/tautological-instrument]] caught at the *test-design* step.

**The class, filed as [[concepts/generosity-masks-fragility]]:**

> **An over-generous simulator MASKS test fragility. Making a model honest surfaces flakiness that
> was always there.** The flakiness is not caused by the fix and must not be attributed to it —
> the fix is the *instrument that revealed it*. Budget for a flake wave whenever a fidelity
> improvement lands, and read that wave as **debt being disclosed, not debt being created.**

This is the mirror of [[concepts/false-green]]: there, a gate *could not fire*; here, a test
*could not fail* — because the environment underneath it was too kind to produce the failing
condition.

---

## 6. The pin that silently stopped working

The two smoke fixtures already pinned to the deterministic fill model on **2026-07-21**
(persistence + lifecycle plumbing — subject is persistence/pipeline, not fill realism) had their
pin **silently stop working**, because `passive_base_prob` **became irrelevant once a book is
present**. Extended to the new flag at `scripts/smoke_test.py:571` and `:822`, following that
documented precedent. `tests/test_sim_fill_queue.py` did the same;
`tests/test_exec_quality_stats.py` instead moved to a **crossed book**, because its subject is
maker fee/slip **booking**, which `_note_exec` performs identically on both paths — so it now
exercises the real mechanism rather than a legacy flag.

> **This is the second occurrence of the same shape**, and it is filed on
> [[concepts/default-path-fallback-writes]]. On **2026-08-02** four QA harnesses were found
> declaring "deterministic fill" while **riding the shipped `passive_base_prob`**; the fix was to
> pin the constant explicitly. **The pin itself has now decayed** — pinning a value only works
> while that value remains the mechanism. *Absence of a pinned value is not absence of a
> dependency* — **and presence of a pinned value is not presence of a guarantee.**

**The persistence fixture's failure mode is its own finding:** it failed with **`IndexError` on
`open_positions()[0]`**, not an assertion. **It crashed rather than reporting "no position"** —
which made it **unable to distinguish a broken subject from a setup that never happened.** A
fixture that cannot say *"my precondition did not occur"* converts a setup failure into a
subject failure ([[concepts/zero-is-not-a-reading]], test-plane instance).

---

## 7. Four self-caught agent errors

Filed under [[concepts/adversarial-verification]]. All four were caught by the author before they
reached a conclusion; recording them is the point.

| # | error | why it matters |
|---|---|---|
| 1 | The first measurement tested for **two draws WITHIN one poll**, where they are **mutually exclusive**, and found nothing. | **The register was right and the test was aimed at the wrong level.** A null from a mis-aimed instrument is not evidence of absence. Nearly closed owed 57 as unreproducible. |
| 2 | The same script printed **`sf_base 0.45`**, having **silently fallen through to defaults** when the live value is **0.048**. | A measurement harness **riding a default** — the same class as §6, one plane up. The harness was measuring the *pre-XV-021* simulator. |
| 3 | The **2.22x** seen at `dist_bps=0` was **the harness degenerating**, not the defect. | The true figure is **1.88x**. Reporting 2.22x would have overstated a self-flattery finding — an error in the *unflattering* direction, which is still an error ([[concepts/exact-or-refuse]]). |
| 4 | A test was patched **by LINE NUMBER** (1134) and hit **the wrong test** — 1134 was the *probe* test. Reverted, redone **by test name**. | Line numbers are not identifiers. [[concepts/location-invariant-tests]]. |

> **Errors 1 and 3 point in opposite directions** — one nearly dismissed a real defect, the other
> nearly inflated it. That is what an unbiased error process looks like, and it is worth more than
> a clean record.

---

## What this does and does not change

**Changes:** every paper fill statistic in the corpus is now known to carry a **~1.88x upward
bias near the touch**, and the corpus is **entirely pre-boundary** — there are no post-#4 fills
yet. The 432-bar cohort now contains **three** execution boundaries.

**Does not change:** the economic verdict. [[synthesis/the-money-path-thesis]] already reads
gross edge ≤ 0 **with** the flattered fills; removing flattery moves the number **down**, never
up. The 432-bar hold is unaffected — this is a fill-model change, not a geometry change — and
per [[synthesis/owed-measurements]] item 57's own embargo, propagation into the 305 live corpus
rows and the cohort verdict remains **DIRECTIONALLY SUPPORTED but UNMEASURED** and **may not be
cited against the hold**.

**Boundary statement (domain rule 9):** items 1-6 are **sim-side** (instrument change) and
**repo-side** (tests, config, guard); the 22.30% ledger rate and the blast-radius percentages are
**sim-side numbers about a simulator**, which is the one context where a sim-conditioned figure is
the *subject* rather than a smuggled venue claim. Nothing here is venue truth
([[concepts/paper-real-boundary]]).

## Related
[[synthesis/owed-measurements]] · [[concepts/paper-real-boundary]] ·
[[concepts/generosity-masks-fragility]] · [[concepts/self-flattery-gradient]] ·
[[concepts/two-paths-one-quantity]] · [[concepts/default-path-fallback-writes]] ·
[[concepts/false-green]] · [[entities/config-guard]] · [[entities/long-book]] ·
[[sources/session-20260807-fleet-findings]] · [[sources/session-20260808-morning-batch]] ·
[[sources/session-20260809-adversarial-audits]] ·
[[synthesis/open-contradictions-register]] · [[synthesis/documentation-drift-register]] ·
[[comparisons/horizon-96-vs-24-bars]] · [[comparisons/dormant-vs-inert-features]]
