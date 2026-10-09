---
title: Criminology Manipulation Lens (2026-07-26)
category: source
summary: Four criminology theories applied to crypto manipulation to decide which detector to build next; rational choice wins, and the only actionable item is governance
tags: [criminology, manipulation, thales, theory]
sources: 1
updated: 2026-08-01
---

# Criminology Manipulation Lens (2026-07-26)

**Raw source:** `raw/research/2026-07-26_criminology_manipulation_lens.md`

## The question
"A paper-trading bot does not need a theory of crime to survive a spoofed book — it needs a detector.
But *which* detector to build next, and whether today's detectors will still work in a year, depends
on why manipulators do what they do." Each theory predicts a different
[[concepts/persistence-curve]].

## The four lenses
- **Differential association (Sutherland 1947)** — manipulation is *learned* in intimate groups.
  Crypto evidence: hundreds of self-organized Telegram channels running identical scripts (Xu &
  Livshits, USENIX Security 2019); repeat victimization of the same illiquid coins. **Bot angle:
  nothing ingests social feeds — a deliberate scope boundary, not a gap.** Exposure is limited by
  euphoria-fade, cross-venue divergence, and liquidity-tier isolation. "None of this *detects* a
  pump-and-dump group; all of it limits the bot's exposure if one is running."
- **Rational choice (Becker 1968)** — offend when expected utility exceeds cost. Evidence: resting
  size *away* from the touch is nearly free to place and cancel while size *at* the touch carries real
  fill risk; CFTC crypto enforcement actions are *falling* even as the same statute drew nine-figure
  penalties on regulated futures (JPMorgan $920.2M, Deutsche Bank $30M). **"The same statute, wildly
  different realized detection probability."**
- **Strain (Merton 1938; Agnew 1992)** — background conditions producing the *supply* of participants,
  not a tick-by-tick mechanism. **Bot angle: nothing observes it "and nothing should try to."** The
  one honest proxy is the aggregate structural-stress index. Separately, the bot is **structurally
  strain-immune by construction** — dry-run default, ARM LIVE ceremony, and the risk stack mean it
  "never needs a 'recoup losses fast' strategy."
- **Labelling (Becker 1963)** — crypto culture runs it **in reverse**: "degen," originally a
  stigmatizing label, has been reclaimed as an in-group status marker, pre-emptively stripping the
  stigma and **disabling informal shame-based social control**.

## The verdict — RCT wins
"This is also the theory with the tightest bot-side match: **every mechanism it names has a
corresponding file:line**." TH-017 spoof-flicker detects the RCT-predicted footprint; the
distance-decayed order-book imbalance **devalues** far-from-touch notional:

> "That is **cost-imposition, not just detection**: the manipulator is pushed toward painting *at* the
> touch, where the tactic becomes expensive, which is the only lever a single market participant
> actually has over another actor's RCT calculus."

See [[concepts/cost-imposition]].

## Persistence curves (the discriminating predictions)
RCT -> enforcement-gated, roughly constant. ST -> loss-cycle-gated, cyclical. LT -> fades only if
"degen" loses cultural cachet. DAT -> persists and adapts regardless of any venue's countermeasures.
**The ST-vs-RCT divergence is explicitly "a testable divergence" that nobody is scheduled to test.**

## One actionable implication per theory
DAT: nothing (a social-feed scanner would be **mandate creep** past the read-only-venue invariant).
RCT: **already covered structurally; the actionable item is governance, not a new mechanism** — any
retuning of the imbalance/spoof knobs must clear the PBO/DSR gates like any other tunable.
ST: nothing. LT: nothing manipulator-facing; the one real implication is defensive and already
shipped — under an inferred-intent standard the audit trail is the bot's defense against being
mislabelled. **"The answer is a file, not a recollection." "Protect it, don't extend it."**

## Related
[[comparisons/criminology-lenses-compared]] · [[entities/osler]] · [[entities/kraken]]
