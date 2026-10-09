---
title: Carol Osler
category: entity
summary: The stop-cluster and price-cascade literature underpinning both the herding detector and the bot's own stop placement — re-graded ESTABLISHED at the 2026-08-10 academic sweep as THE peer-reviewed kernel under the stop-hunt folklore, and the evidence base for ALGO-7's off-round-number placement; at cut #7 (2026-08-11, e7d5ca1a) the bot's existing implementation turned out to hold the OPPOSITE semantics (tighten-above), nearly dormant and reading a phantom config block — flipped to widen-beyond in risk/stop_placement.py, on the bracket path, direction-only; residue swept at the 2026-08-11 since-6am audit (stop_placement + test docstring drift fixed, config_guard now checks the stop_round knobs at the declaration-consumer join)
tags: [person, external, microstructure]
sources: 6
updated: 2026-08-10
---

# Carol Osler

The authority behind the round-number and stop-cascade work that appears on **both sides** of this
system.

## The finding used
Orders cluster heavily at round numbers (~10% of FX orders ending in "00"), and stop-loss clusters
generate **self-reinforcing price cascades** that are **stronger and longer-lived than take-profit
responses**.

## Used defensively
The stop-herding detector shades **down** entries whose protective stop would land inside a hot cluster
— "we stop being the lemming." ~~And the bot's own stops are nudged **off** round numbers.~~

> ⚠️ **Corrected at cut #7 (2026-08-11, [[sources/session-20260811-cut7-geometry-epoch]]).** The
> struck claim was wrong twice. **Direction:** the shipped nudge (`main.py
> nudge_stop_off_round_number`) held the **opposite** reading of "off round numbers" —
> tighten-above, "exit before the cascade detonates" — under which any sweep TO a round level
> ejects the position: the exact shakeout the bull-readiness directive names. **Coverage:** it was
> nearly dormant — only the rare non-bracket fallback path called it; the bracket sl leg
> (virtually every trade since geometry-alignment) was stamped raw. It also read a phantom config
> block (`config["risk_management"]` does not exist), so its knob was never actually read.
> **What stands now:** `risk/stop_placement.py` (cut #7, operator-adjudicated) — **widen-beyond**:
> a stop within band bps of a half-step round level rests offset bps **past** it (long below /
> short above), the herd's clustered stops fire first, ours only if the level actually breaks;
> wired at **both** stop sites, only ever widening, with the cost stated on its face (a genuine
> break exits into the cascade; the escalation ladder owns that path). The four Osler tests
> flipped sign as the record of the change.

## Used offensively (bounded)
A confirmed sweep-and-revert shades mean-reversion confidence up, opposite the sweep, for a short decay
window. Failure mode acknowledged: **genuine breakouts look like sweeps at first.**

## Its role in the counterparty thesis
Forced sellers in stop cascades are one of the three flows the system aims to monetize: **"flow is
forced, hence uninformed at execution,"** and it persists because "anchor stops are a coordination
equilibrium." See [[concepts/who-loses-to-us]].

## Corroboration added later
A crypto-native price-clustering study upgraded the anchoring evidence, so "ladder-placement hygiene now
stands on two independent literatures." Notably, a crypto-native **sweep** study could not be verified —
so the hardening shipped as **no new detector**, only a placement rule. See
[[concepts/honest-coverage-gap]].

## Re-graded at the Grand Synthesis academic sweep (2026-08-10)
The 2026-08-10 sweep ([[sources/sweep-20260811-academic-stops]]) confirmed **Osler JIMF 2005
as ESTABLISHED** — and sharpened its role: it is **the peer-reviewed kernel under the
stop-hunt folklore**. The ICT/liquidity-sweep corpus is graded FOLKLORE, but the mechanism
that corpus gestures at — stop clustering at round numbers generating self-reinforcing
cascades — is exactly Osler's result. This makes the entity the citation boundary between
what the folklore gets right (the mechanism) and what it invents (the narrative). Direct
design input to [[synthesis/grand-synthesis-algorithm-package|ALGO-7]]: stops placed **off
round-number clusters**, unpredictable within the evidence-derived band — **landed at cut #7**
(2026-08-11T01:33:50Z, `e7d5ca1a`): the direction shipped as widen-beyond (see the correction
above); the evidence-derived **band widths** wait on the ALGO-5 replay amendment. The flip is
this entity's sharpest lesson: "place stops off round numbers" admits two opposite
implementations, and the bot had shipped the anti-Osler one — an evidence citation is not a
semantics pin ([[sources/session-20260811-cut7-geometry-epoch]] §1).

## Audit follow-through (2026-08-11 since-6am audit)

([[sources/session-20260811-operator-audit]] §5, §7.) The cut-#7 commits were among the **14
verified claim-vs-diff clean**, and the residue the flip left behind was swept the same
audit: the `risk/stop_placement.py` docstring's stale phantom-block reference and the Osler
**test docstring** were fixed (two [[synthesis/documentation-drift-register]] rows —
docstrings describing the retired implementation over the shipped one), and
[[entities/config-guard]] now **checks the `stop_round` knobs at the declaration-consumer
join**, so the phantom-config-block defect that hid inside the original nudge cannot silently
recur. The widths remain direction-only pending the ALGO-5 amendment (owed 67).
