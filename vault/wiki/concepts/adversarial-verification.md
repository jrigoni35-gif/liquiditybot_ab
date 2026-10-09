---
title: Adversarial Verification
category: concept
summary: Independent verifiers instructed to refute rather than confirm prior corrections, catching fixes that are correct in shape but inert in effect — extended 2026-08-09 to the practice applied against an AUDIT and against the verifier's own arithmetic, where four corrections landed (the audit cut two of its own claims downward, 84%→~7% and 6.4x→1.16x; the filing agent cut its own −40.9% to −13.7% and caught a NEAR-MISS in which it had nearly declared the audit wrong by adding fees back into a figure that was already the pure notional flow); the rule that follows is verify your own refutation hardest of all, because finding the audit wrong is the most comfortable possible result — and extended 2026-08-11 to the practice applied to the OPERATOR's own claim (the backwards-derivative hypothesis put to three refuters hunting FOR the inversion, 0/3 succeeded, NO-INVERSION-FOUND citable precisely because the refuters tried), with the companion lesson that a failed refutation can still pay (the data-lens refuter surfaced the h432 anti-momentum pattern while failing to refute)
tags: [verification, method, quality]
sources: 4
updated: 2026-08-15
---

# Adversarial Verification

## Definition
After a batch of corrections ships, **independent fresh-eyed verifiers are instructed to REFUTE** each
one — not to confirm it. Findings are graded CONFIRMED-GOOD or SUSPECT.

## The yield
18 of 20 items confirmed; **2 SUSPECT items produced same-day fixes**. Both of the catches are the kind
a confirmatory review misses:
1. A fix that was correctly **fail-closed but inert** — the mechanism worked, but the threshold it
   freed was still unreachable because of a [[concepts/ghost-badge]].
2. A fix whose **estimator was right but never reached the dashboard** — missing from an export
   whitelist, so the corrected metric was invisible while the wrong one kept the panel.

A third find: a config value with **zero guard coverage** at all.

## What verification looked like
Not re-reading the diff — **independent re-derivation**: payoff math to 1e-12, an inverse-normal
implementation checked to <=5e-7 against known quantiles, a bias correction validated on planted
synthetic data (0.919 -> 0.963), and cadence invariance checked under a deliberately stalled poll.

## The general lesson
**"Shipped" is not "working."** The two classes this pass catches — *correct-but-inert* and
*correct-but-unplumbed* — are invisible to tests that assert the code does what the code says. The
question that finds them is "does this change actually reach and move the thing it was supposed to
move?" — the same question as an [[concepts/earning-its-keep-audit]].

## Companion doctrine
Verify rather than assume. The single highest-value find in the corpus — the era filter silently
excluding the very rows a fix had just created — was found **"only because the operator verified
rather than assumed."**

---

## 2026-08-09 — the practice applied to an AUDIT, and to the verifier's own arithmetic

([[sources/session-20260809-adversarial-audits]].) Two 25- and 22-agent adversarial sweeps were
themselves verified before filing. **Four corrections resulted, and the direction of each is the
point.**

### Two corrections the AUDIT made to itself (both DOWNWARD)

| Claim | Verified truth |
|---|---|
| *"hedging is 84% of the loss"* | **True of the LIFETIME ledger** — but it is **one already-fixed incident on one day**, not a standing per-entry cost. **Go-forward unpriced hedge cost ≈ 7% of fees. Do not size a fix off the 84%.** |
| cost attribution understates by **6.4x** | **1.16x.** The printed **0.668%/trade is CORRECT** for the 235 directional trades; the honest blended figure is **0.7766%**. |

### Two corrections the FILING AGENT made to its own numbers

| First stated | Corrected | Why |
|---|---|---|
| the sizer bug inflated tickets by **−40.9%** | **−13.7%** | the reconstruction **stamped every position as opened NOW**, which maximized the clustering term `u_short` and exaggerated the taper. **The bug is unchanged; the magnitude is 3x smaller.** |
| *"the breakeven-tool sign does not flip — the audit is wrong"* | **it flips** | the verification **added fees back into `cash`, which is already the pure notional flow**, producing a *"gross"* that was really **net**. **On that basis the operator would have been told the audit was wrong.** Caught by **re-deriving the terms** instead of trusting the script. |

> **The second row is the important one, and it is a near-miss, not a catch.** It is the same
> error class as `36fcfd6e`'s *"the identical red reproduces on the parent commit"* — a quantity
> **asserted in measurement grammar without checking what it actually contained**
> ([[concepts/false-green]] design rule 8, [[synthesis/governance-doctrine]] rule 14). The
> difference between the two episodes is **not** carefulness; it is that this time the terms were
> **re-derived from their definitions** rather than re-run.

## The rule this session adds

> **Verify the audit as adversarially as the audit verified the code — and verify your own
> refutation hardest of all.** A verifier who finds the audit wrong has produced the most
> comfortable possible result, and comfort is exactly the signal to re-derive.

**Corollary, from the two downward self-corrections:** *a finding that survives having its
magnitude cut by 3x and 5.5x is a stronger finding than one that was never challenged.* Record
the discarded magnitude beside the surviving one — **the discarded half is the evidence that the
surviving half was tested.**

**And the asymmetry that makes this non-trivial:** the bot's own numbers were found to be
**flattering eleven times out of eleven** ([[concepts/self-flattery-gradient]]), while the audit's
numbers needed correcting **downward** twice. **An audit that only ever revised its findings
upward would be exhibiting the same disease it was hunting.**

---

## 2026-08-11 — the practice applied to the OPERATOR's own claim, and the refuter that failed and still paid

([[sources/session-20260811-operator-audit]] §1-§2.) The operator claimed the bot's
derivative features were **backwards** — the most consequential possible claim about the
feature bank. Instead of confirming or arguing, the audit spawned **three adversarial
refuters instructed to FIND the inversion** — a recompute lens, a consumption lens, and a
data lens. **0 of 3 succeeded → NO-INVERSION-FOUND at high confidence.**

Two extensions to this page's doctrine:

1. **The polarity flip is what makes the negative citable.** Verifiers hunting FOR the
   operator's inversion and failing is much stronger evidence than verifiers confirming
   "the code looks right" — the same asymmetry as the original 18-of-20 pass, applied to a
   hypothesis instead of a fix. The refuters *wanted* to find it; the killing citation for
   the closed claim is the 0/3 record, not anyone's assurance. *(And note who the claimant
   was: the practice is symmetric — an operator hypothesis gets the same refutation pass as
   an agent's fix, which is precisely why the operator can trust the negative.)*
2. **A refutation attempt that fails can still pay for itself.** The data-lens refuter,
   failing to find the inversion, surfaced a genuinely new finding instead — the symmetric
   **anti-momentum pattern at h432** (momentum-agreeing trades win LESS in both direction
   cohorts; [[sources/session-20260811-operator-audit]] §2, owed 69). A refuter reads the
   data with hostile attention, and hostile attention finds things confirmatory reads skim
   past. **Budget refuters even when you expect them to fail.**

The claim's decomposition also minted a reading-hazard concept —
[[concepts/side-relative-features]] — so the *mechanism* that generated the false claim is
now on file beside the refutation record, which is what keeps the claim from being
re-litigated from the same raw-row read next month.

## QUALIFIED 2026-08-15 — measured, the refuters killed under 1%

This page's practice was measured at scale for the first time, and the result
narrows it rather than confirming it.

| scan | candidates | killed by the **finders** | killed by the **refuters** |
|---|---:|---:|---:|
| preventive maintenance | 232 | 215 | **2** (0.9%) |
| defect-class recurrence | 507 | 494 | **3** (0.6%) |

**Adversarial verification, as a separate reviewer stage, killed under 1% of
candidates in both runs.** The strictness that did the work lived in the
*finder's* ship-criteria — a schema that refused a finding without an exact
`file:line` read, a concrete failure scenario, and a named guard checked. Two
effects cannot be separated from this data and the page says so rather than
overclaiming: refuters still **corrected severity and fix-class** on survivors
(where a mislabelled SAFE would have skipped adjudication), and the finders may
have been strict *because* a refuter was known to follow.

**What the refuters remained decisively good at is the thing this page was
built for**: they verified *pointers*. Every `file:line` an agent produced held
up; most of the *numbers* did not — see [[concepts/location-not-magnitude]],
which is the delegated form of *verify your own refutation hardest of all*.

The practical consequence is a budget shift toward ship-criteria, **not** a case
for dropping refuters — and, where the author is also the reviewer, a panel that
assigns positions to argue instead of asking for a review, because agreement is
the cheap default (`.claude/workflows/red-team-panel.js`).
— [[sources/session-20260815-scans-and-corrections]] §3

## Related
[[concepts/false-green]] · [[concepts/self-flattery-gradient]] ·
[[concepts/unfalsifiable-explanation]] · [[concepts/iron-law-of-debugging]] ·
[[concepts/earning-its-keep-audit]] · [[concepts/ghost-badge]] ·
[[concepts/location-not-magnitude]] ·
[[synthesis/governance-doctrine]] · [[sources/session-20260809-adversarial-audits]] ·
[[sources/session-20260811-operator-audit]] · [[concepts/side-relative-features]]
