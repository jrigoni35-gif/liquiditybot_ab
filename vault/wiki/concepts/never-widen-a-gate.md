---
title: Never Widen a Gate
category: concept
summary: "The governing constitutional rule: when a measurement fails an acceptance gate, change the thing being measured or stop, but never relax the gate — with the boundary it finally needed (2026-08-09): a gate may be DISCONNECTED from a verdict it was never evidence for, provided the move is fail-closed, keeps printing the number, stays hard where the instrument itself is being validated, and self-terminates. Anything short of all four is widening wearing a different word — and, later the same day, the MIRROR boundary: the doctrine does not authorize silently TIGHTENING a gate either, recorded when an agent declined to make the consecutive-loss breaker start counting hedge losses (changing what a breaker counts changes when it fires), while noting that the permissive status quo is also a choice"
tags: [governance, discipline, constitutional]
sources: 9
updated: 2026-08-16
---

# Never Widen a Gate

## Definition
When a change makes a measurement fail an acceptance gate, the admissible responses are: revert the
change, shrink the search space, re-derive the mechanism, or file the failure and stop. **Relaxing the
gate is never one of them.**

## Canonical phrasings across the corpus
- "Shrink the space, never the gate." — [[sources/of3-pbo-data-shift]]
- "Do not tune the gate to it." — on a noisy single-point `dead_frac` reading
- "Never widen a gate to silence CI."
- "Nothing here was stretched to manufacture an ADOPT." — [[sources/phase3-adjudication]]
- "OF-3 FAIL filed honestly rather than gate-adjusted" — praised as evidence of discipline in
  [[sources/goals-mindset-review]]

## How it hardened over time
1. **2026-07-23** — invoked ad hoc by a coordinator when the harness enablement broke G1
   ([[sources/harness-enablement-g1-finding]]); the enablement is reverted and the diff preserved.
2. **2026-07-24** — becomes an explicit watch-condition heading in the PBO watch doc.
3. **2026-07-26** — hardens into written BINDING policy with named rules and an explicit burden-of-proof
   allocation ([[concepts/gort-rule]]).
4. **By 07-26** — becomes the default reporting frame: [[concepts/defer-verdict|DEFER]] is reclassified
   as "a successful, informative outcome," not a failure.

## The operational form
Every ranked improvement lever in [[sources/goals-mindset-review]] carries an explicit **disqualifier**
naming the gate-widening move that would be forbidden — e.g. "Disqualifier: widening G1's cap",
"Disqualifier: flipping conviction early or deriving from a backtest", "Disqualifier: ANY manual floor
override."

## The boundary the rule needed — SCOPING is not WIDENING (2026-08-09)

The overfit-gate adjudication (`8e9d7e6f`,
[[sources/session-20260809-gate-policy-and-self-heal]] §3) forced this rule to state a
distinction it had never had to make, because the honest reading of the situation was
*"a gate is failing and we are about to change something."*

**The diagnosis that makes it legitimate:** OF-1 and OF-7's dead-feature check are
**MODEL-READINESS** gates that were wired to a **CODE-DEPLOY** consumer
(`auto_update.battery_passes`). A data-starved corpus was therefore blocking **code-safety
fixes** — including, the night before, a critical staleness fix. **The gate was not too
strict; it was pointed at the wrong verdict.**

| | Widening (forbidden) | Scoping (what happened) |
|---|---|---|
| The threshold | moved | **unchanged — 0.12 and 0.55, pinned by `test_thresholds_are_untouched`** |
| The measurement | weakened or dropped | **unchanged — computed and printed every run** |
| The reported number | disappears or softens | **still printed with the gap value AND the re-arm condition, pinned by test** |
| What changes | how hard it is to pass | **which verdict the result is allowed to stop** |
| Reversibility | needs a conscious re-baseline to undo | **self-terminating — flip exploration off and it re-arms; no stamp, no operator memory** |

**Three properties are what keep the distinction honest, and each is the answer to an
obvious abuse of it:**

- **FAIL-CLOSED** — an unreadable config yields the **full** gate. Scoping must never be the
  default that a missing input falls into.
- **HARD on the SYNTHETIC benchmark, always** — where the check validates the **instrument**
  against a planted signal with a known answer. *An instrument may not grade itself
  leniently.* This is the clause that stops "scoping" from becoming a way to never test the
  measurement at all.
- **The number must keep printing.** *A softened gate that stops printing its measurement is
  how a red goes invisible* — pinned by `test_informational_lines_still_report_the_number`,
  which asserts the **value** and the **re-arm condition**, not merely that something was
  emitted.

> **The rule, restated with its boundary:** *when a measurement fails an acceptance gate,
> change the thing being measured or stop — never relax the gate.* **A gate may, however,
> be disconnected from a verdict it was never evidence for** — and that move must be
> fail-closed, must keep reporting, must stay hard wherever the instrument is being
> validated rather than the subject, and must terminate itself when its premise expires.
> Anything short of all four is widening wearing a different word.

**Precedents this rests on:** the **OF-5/DSR** precedent (informational-not-gating during
exploration) and the [[concepts/conscious-re-baseline]] discipline. **What it does not
buy:** nothing about model trust changed — [[concepts/evidence-floors]] still gate selection
to `logistic` at live=6, and [[entities/ml-governor]] still kills a confidently-wrong model
on realized outcomes.

## The other boundary — a gate that is too NARROW is still the operator's call (2026-08-09)

([[sources/session-20260809-adversarial-audits]] §4.2; [[synthesis/owed-measurements]] item 52.)

The 08-09 boundary above handles a gate that is **too strict for the verdict it was attached to**.
The same day produced the mirror question and it deserves the same discipline.

`main.py:1671`'s `if not pos.is_hedge:` gates **both** the performance ledger **and** the
consecutive-loss circuit breaker. **The entire −325.70 hedge book is invisible to both** — which
is **why 159 consecutive losing hedge round trips over 10.4h never tripped the breaker: they were
never recorded as losses.**

The tempting move is obvious and was **deliberately not taken**:

> **Changing what a circuit breaker COUNTS changes WHEN IT FIRES.** That is a gate-semantics
> change in the same family as widening one, and **the filing agent declined to make it.**

The reasoning, recorded so the refusal is auditable rather than merely cautious:

- **A hedge is risk-reducing insurance that often loses BY DESIGN.** Counting hedge losses could
  trip the breaker **during correct operation** — i.e. the "fix" could manufacture a false
  positive on a healthy book.
- **The 159-loss run was a churn bug** (FW-070, since fixed —
  [[sources/session-20260807-hedge-churn-guards]]), **not** normal behaviour. Retuning a breaker
  around a defect that no longer exists is fitting to an artefact.
- **But the current state is the PERMISSIVE one**, so *doing nothing is also a choice*, and it is
  the flattering one ([[concepts/self-flattery-gradient]]). This is why the item is **registered
  as owed adjudication with a named decider**, not left as a note.

**Rule extracted:** *this doctrine forbids loosening a gate on deployment pressure; it does not
authorize silently TIGHTENING one either.* Both directions change when the machine stops the
book, and both belong to the operator, **with the reasoning written down**
([[concepts/conscious-re-baseline]]). What an agent may do unilaterally is the **half that is not
a gate at all** — the performance ledger **should** see hedges, that is bookkeeping, and it ships
separately.

## A THIRD road into the forbidden move: widening reachable through a CONFIG FLAG, not a floor (2026-08-16)

The doctrine, and `CLAUDE.md`'s own paragraph enforcing it, are both written in the vocabulary of
**floors**: *do not lower the overfit row floor, do not lower `SG_MIN_ROWS`, do not lower the era-4
`n=50` — these are measurement standards, not tunables.* That vocabulary has a hole in it.

**`ml.era_exclusion.forced_off` is a boolean that produces the identical effect without touching
any floor.** Flipping it moves the overfit battery's loaded corpus **365 → 10,534 rows** (measured
2026-08-15 on the 10,671-row corpus) and its verdict **SYNTHETIC → REAL** — over a corpus **mixing
five label eras whose base rates span ~40x** (`exit_sim_time_stop` **0.65%** … `legacy` **26.1%**).
The number on the report goes up and the banner stops saying *"validating machinery, not market"*.

> [!success] **FIXED — and the fix is itself a worked example of this page's boundary.** `7f48f6ea`, 2026-08-15T22:35:06Z, **inside the gap window**, verified at head `c4272391`.
> The asymmetry was real when it was found: `forced_on` carried a semantic check and `forced_off`
> carried **only a type check**, which the commit's own comment calls *"an asymmetry with no
> justification: `forced_off` is the lever with the larger blast radius of the two, because it is
> the one that silently makes the corpus BIGGER"* (`core/config_guard.py:985-993`).
>
> **The remedy was parity as a WARN, not a FATAL — deliberately** (`:994`), and the reasoning is
> exactly this doctrine's own boundary: `true` is a **legitimate rollback mode**, and *"a FATAL
> would make the pre-exclusion view unreachable, which is the one thing a rollback lever may never
> be."* The guard now names the mechanism on the operator's screen: *"It is a ROLLBACK lever,
> never a way to recover corpus size or entry volume … a REAL-corpus green bought this way is
> worth **less** than the synthetic one it replaced."*
>
> ⚠️ **The vault's own catch-up filing carried this as UN-FENCED.** It was reading a pre-`7f48f6ea`
> state — a state that had already been repaired **by a commit inside the very window the catch-up
> existed to cover**. Recorded per [[synthesis/governance-doctrine]] rule 16 and
> [[concepts/session-identity-is-not-stable]]: **a finding is as stale as the tree it was measured
> on**, and *"still broken"* needs re-derivation just as much as *"now fixed"* does.

**What survives, and it is the durable half:** the *shape* of the hole is real and general, even
though this instance is closed.

> **Rule extracted:** *the protected quantity is the STANDARD, not the number that expresses it.*
> A guard that fences the floor and leaves the switch that makes the floor irrelevant has fenced a
> spelling, not a rule. Ask of every gate: **what else, besides moving this number, produces the
> same relief?**

**The structural companion — DISCLOSED, deliberately not "fixed".** `ml.era_exclusion.min_new_era_rows
= 150` (`config.json`, verified at head) sits **BELOW** the overfit floor
`len(FEATURE_NAMES) * _OVERFIT_ROWS_PER_FEATURE` = **64 × 10 = 640** (AST count, `ml/features.py:116`),
which **guarantees** a window `150 ≤ new_era_rows < 640` in which the era filter is **armed** and
the battery is **simultaneously below its floor**. **The system is inside that window now**
(`outputs/overfit_report.md`, 2026-08-15 16:13 UTC: *"SYNTHETIC benchmark (loaded rows=347 <
640)"*), and it **reopens at every horizon migration** — a designed-in gap, not an accident.

The same commit `7f48f6ea` added a startup **WARN** rather than a FATAL, and its text is the
doctrine quoted back verbatim (`core/config_guard.py:947-970`):

> *"BOTH numbers are MEASUREMENT STANDARDS, not tunables — do NOT raise `min_new_era_rows` and do
> NOT lower the overfit floor to silence this warning; moving either one so a gate reads 'real' is
> the widening the overfit discipline forbids. The correct response is to read the overfit
> battery's corpus line on EVERY run and to treat a SYNTHETIC green as UNPROVEN until the loaded
> corpus clears 640 rows on its own."*

And the WARN-not-FATAL choice is itself argued in-code: *"this is the SHIPPED, intentional
configuration (150 < 640 as shipped) … refusing to start the bot over a known, correct config
would be strictly worse than trading with the instrument honestly labelled."*

> **This is what "a gate may be DISCONNECTED but never WIDENED" looks like when it goes right.**
> Neither standard moved. What changed is that the condition is now **announced at the boundary
> where a human can act on it** instead of living in a log entry. **Disposition remains OPERATOR
> adjudication** on whether the window is acceptable; **registered as owed, not started.**

*(First recorded 2026-08-15 as OBJ-8 in the log's docket entry; it never reached this page or
[[concepts/overfit-battery]]. Filed here by
[[sources/session-20260816-catchup-08-12-to-08-16]] — **a rule recorded only in a chronological
log is not filed** — with the un-fenced half CORRECTED against head.)*

## Open tension
The corpus contains one live case of a config knowingly running a geometry that fails the harness's own
G1 gate — resolved not by widening but by arguing the harness overstates the effect. See
[[comparisons/harness-vs-live-cost-stack]]. **No document records the verdict that was supposed to
settle it.**
