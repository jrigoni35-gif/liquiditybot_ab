---
title: "Observational Equivalence (a detector that cannot separate two generating processes is not evidence about either)"
category: concept
status: SETTLED
summary: "The defect class where a detector's observable is IDENTICAL under a benign and a malicious generating process, so its firing carries no information about which one occurred. Type specimen measured 2026-08-21 by injection into the shipped LiquidityRegimeEngine: honest maker repricing in a +15bps/30s melt-up and true layering both score spoof 0.949 with 79 events and the same 'spoofy' label at matched 30s cadence — and 0.949 clears the live veto_at 0.90, refusing entries (SZ-045). Distinct from a tautological instrument (value fixed by construction) and from a mis-calibrated threshold (right observable, wrong bar): here the OBSERVABLE ITSELF is non-identifying, so no threshold can fix it. Three companion signatures: the detector is DIRECTIONAL (fires on whichever side must chase the trend), EVADABLE by the free parameter it actually keys on (>=120s repost cadence scores 0.000), and BLIND outside its tracking window (the apparent safe zones at 30bps/30s and +100bps are blind spots, not immunity)."
tags: [detectors, identifiability, manipulation, injection, defect-class]
sources: 1
updated: 2026-08-21
---

# Observational Equivalence

## Definition

A detector is **observationally equivalent** across two generating processes
when the quantity it measures takes the same value under both. Its firing then
carries **zero information** about which process produced the tape. No threshold
choice repairs this, because the failure is in the observable, not the bar.

The diagnostic question is not *"does the detector fire on the bad thing?"* but
***"is there anything the good thing does that makes it NOT fire?"***

## Type specimen — the spoof detector, measured 2026-08-21

Injection into the **shipped** `regime.liquidity_regime.LiquidityRegimeEngine`
with the live config (synthetic 15-level book, 2 bps grid, 30 s cadence, 80
snapshots — the real poll cadence):

| scenario | spoof | events | label |
|---|---|---|---|
| MALICIOUS layering, flat mid, wall pulled untouched, repost 30 s | **0.949** | 79 | **spoofy** |
| HONEST maker repricing its offer, +15 bps/30 s melt-up, repost 30 s | **0.949** | 79 | **spoofy** |

Identical score, identical event count, identical label. The engine's own
mechanism explains why: a *large near-touch level that vanished untouched inside
90 s* is exactly what a maker following the mid up produces, every poll.

**It reaches live risk.** `spoof_score` →
`manip_suspect_score = MAX(spoof, whiplash, divergence)` (`main.py:370-392`) →
`risk.manip_gate` `veto_at = 0.90` (`main.py:1287-1298`) → **SZ-045 entry
refusal** (`main.py:4678-4700`). `0.949 ≥ 0.90`. It also clears the `spoofy`
label bar 0.85 → `size_mult 0.0`, `reduce_only`
(`regime/liquidity_regime.py:348-352`).

## The three companion signatures

Each was measured on the same run and each is diagnostic on its own:

1. **DIRECTIONAL.** A melt-up trips the offer side (0.949) and not the bid
   (0.003); a crash trips the bid side (0.949) and not the offer (0.003). The
   side that must chase the trend is the side that reads as manipulation — so
   the detector systematically vetoes entries in exactly the tape where a trend
   exists.
2. **EVADABLE VIA THE PARAMETER IT ACTUALLY KEYS ON.** Repost cadence, not
   intent, is what moves the score: 30 s → 0.949, 60 s → 0.764, 90 s → 0.629,
   **≥120 s → 0.000** against a 0.90 bar. Cadence is the attacker's free
   parameter and costs him nothing.
3. **BLIND OUTSIDE ITS WINDOW.** Non-monotone at both extremes — 30 bps/30 s →
   0.000 and +100 bps distance → 0.000 — because the level leaves the tracked
   `track_levels = 15` window. **An apparent safe zone produced by not looking is
   a blind spot, not immunity**, and reading it as calibration inverts its
   meaning.

## Why it is its own class

| class | what is wrong | can a better threshold fix it? |
|---|---|---|
| [[concepts/tautological-instrument]] | the value is fixed by construction | no — the value is definitional |
| [[concepts/calibration-check]] failure | right observable, wrong bar | **yes** |
| **observational equivalence** | the observable does not separate the hypotheses | **no** — needs a NEW observable |

The repair is therefore never a knob. It is a **discriminating feature**: some
quantity that differs between the two processes. For the spoof case the obvious
candidates are the trade tape (did prints occur at or through the level before
it vanished — a consumed level is already correctly scored 0.000) and
level-lifetime conditioned on mid direction (honest repricing only "vanishes"
levels on the side the mid is moving toward). Adding one changes which orders are
placed → cohort-resetting under the era-4 moratorium → readout docket, never a
mid-era edit.

## How the class is found

Only by **asking the running system**. Static reading of this detector reads as
sound; the docstring, the config `_doc`, and the SD-003 rationale all describe a
mechanism that is correct as far as it goes. What separates it is
**paired injection**: run the benign process and the malicious process through
the *shipped* object at *matched* nuisance parameters and compare. If the outputs
are equal, the detector is not evidence — regardless of how many true positives
it also produces.

Corollary for every future detector: **a detector ships with its benign twin.**
Any scenario that fires it must be paired with the most innocent process that
produces the same shape, and both must be run.

## The honest limit of the specimen

The injection establishes a **capability** — that the two processes are
indistinguishable to this instrument — not a **frequency**. It used a synthetic
book (one large level, regular polls, one asset), so it says nothing about how
often the false positive occurs in production. That count is owed
([[synthesis/owed-measurements]] item 96); the 2026-08-20 melt-up is the natural
window. The corpus is consistent with a real rate: 95.8% of the era's veto band
sits on MINA+FLOW, the two widest-spread assets on the book.

## Related

[[sources/session-20260821-manip-gate-and-live-readiness]] ·
[[entities/thales-engine]] · [[comparisons/thales-engine-vs-manip-suspect]] ·
[[concepts/tautological-instrument]] · [[concepts/calibration-check]] ·
[[concepts/who-loses-to-us]] · [[concepts/shadow-first-adoption]] ·
[[concepts/never-widen-a-gate]]

> [!warning] THIRD INSTANCE, 2026-09-02 — the manipulation score cannot separate "few participants" from "adversarial participants"
> Measured on the Kraken tape (51 d, read 2026-09-02T21:42Z): ETH prints 985.6 trades/h, FLOW 15.0 — a 66× activity gap on the same venue. FLOW's **median** `manip_suspect` is **0.927** against a veto that fires at 0.90, so the median FLOW signal is refused by construction: **470 of 1,065** FLOW rows carry SZ-045, ETH **1 of 3,919**, and FLOW is the only one of 14 assets with **zero fills ever**. This morning's MANIP-2 memo found 735 of 744 refusals concentrated on FLOW and MINA and could not say why; this is why. A thin book and a layered book are observationally identical to a detector built from book shape — the same equivalence this page records for honest repricing vs layering, now visible from the liquidity side. **Consequence:** every SZ-045 efficacy statistic is confounded with liquidity until the score is conditioned on activity, and the gate may be reaching a defensible refusal ("too thin to trade at 22/38 bps") for an indefensible stated reason ("manipulation"). Do not lower the threshold. Repo: `docs/quant/2026-09-02_flow_vs_eth_and_target_decision.md` Part 2; HANDOFF (16b).
