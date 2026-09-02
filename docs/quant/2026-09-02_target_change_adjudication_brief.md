# Adjudication brief — change the TARGET, not the feature list (ALGO-5 / GB-1 bundle)

**Status:** DRAFT for operator adjudication. Nothing here is shipped. This is a
COHORT-RESETTING proposal by construction (it changes what the model is trained to
predict, which changes entry decisioning) and therefore lands in the era-6 docket
beside ALGO-5 (stop widths + time-decay ladder) and GB-1 (give-back ratchet), never
alone and never before the pre-registered readout.

**`[T2]` and `[T3]` are now FILLED from workflow `wf_33d04172-ab9` (2026-09-02) and
strengthen the case below: the 1-bit target's failure is not a feature-coverage
problem. `[R3]` (research angles 4-5) remains OWED and is marked as such.**

**What the 2026-09-02 measurements changed in this brief.** Section 1's table now
carries three measured rows instead of three placeholders, and they point the same
way: no stored feature and no tape feature carries DIRECTION, while volatility and
spread strongly predict RESOLUTION. That is the strongest available evidence for
reading (b) over (a) — the label is spending its single bit on a channel that is
mechanically determined — but it is not proof of (b), because a target with no
directional signal in it would look identical.

---

## 1. The question the model is asked, and why it cannot be answered from this data

The deployed target is one bit: did the path touch the profit barrier before the stop
inside 432 bars. On the champion's own corpus (12,066 rows, 23.73 d, as of
2026-09-01T22:52Z — re-derive with `scripts/champion_skill_report.py --json`):

| evidence | result | where |
|---|---|---|
| Capacity ladder | every family rung scores negative skill vs a constant; capacity monotonically harmful | `champion_skill_report.py --ladder`, HANDOFF CAPACITY LADDER |
| Feature-concentration scan | 0/64 features above the null band; every family ≤ 0; greedy k=6 +0.0034 (search-biased) | HANDOFF EDGE-HUNTER MIRROR (3) |
| Signal-existence gate | instrument validated on planted dose-response; no target clears significance | HANDOFF SIGNAL-EXISTENCE GATE |
| Sample vs MinBTL | 0.065 yr against 2.1–9.4 yr; SE of an annualized Sharpe at true zero ≈ 3.9 | vault `concepts/false-strategy-theorem-and-minbtl` |
| Barrier-geometry decomposition | the one cross-asset tape lead: RESOLUTION 0.616, DIRECTION 0.510, 0/7 pairs significant | vault `concepts/resolution-vs-direction-decomposition` |
| Decomposition of the 64 stored features | **MEASURED 2026-09-02: DIRECTIONAL 5 of 64 against 8.0 expected by chance (realized null rate 12.5%, measured on the real corpus with `--null-calibration 200`; the nominal 5% would say 3.2 and is the wrong comparator). The largest deviation is the feature named `direction` (the trade side) and it does not survive an independent bootstrap. RESOLUTION is where everything loads: sigma_bar_pct 0.750, spread_bps 0.662.** | `scripts/label_decomposition_report.py` |
| Tape features vs the continuous outcome | **MEASURED 2026-09-02: nothing survives — 7 of 72 cells flagged, the placebo flags 9; largest \|Spearman\| 0.067** | `docs/quant/2026-09-02_tape_features_vs_expectancy.md` |
| Tick-horizon markout | **MEASURED 2026-09-02: the apparent seconds-horizon gain is the bid/ask bounce (corr 0.995 with the reflected limit distance); net of it, negative at every horizon** | `scripts/markout_report.py --tick-store` |
| **POWER of the decomposition test** | **MEASURED 2026-09-02, and it changes the STATUS of every row above: planting a known directional effect against the real targets, rows and day blocks, the instrument detects 0.05 SD 100% of the time (0.02 SD half the time). MDE = 0.05 SD at 80% power.** The nulls above are therefore FALSIFIABLE FINDINGS, not underpowered silence. | `scripts/label_decomposition_report.py --power-calibration` |
| Power of the SKILL test | **MEASURED 2026-09-02 and it goes the OTHER way: the champion's fresh window resolves only \|skill\| > 0.0146 against an estimate of -0.0036 - 4.1x too coarse. That number establishes NOTHING in either direction.** | `scripts/champion_skill_report.py` |

Two readings are consistent with all of it. (a) There is no exploitable structure in
these features at this horizon. (b) The 1-bit label throws away the part of the outcome
that might carry structure — magnitude — and folds volatility into the part it keeps.

**UPDATE 2026-09-02, and it weakens the case for changing the target rather than
strengthening it.** Until the power rows above were measured, (a) and (b) were
indistinguishable and the argument for a new target was "the current one cannot lose
informatively". That argument is now half dead: the decomposition test CAN lose
informatively. It detects a 0.05 SD directional effect every time and finds none, so
reading (a) — there is no directional structure in these features at this horizon — is
now a POSITIVE finding rather than an absence of evidence. What remains genuinely
unresolved is narrower: whether the MAGNITUDE channel carries structure that a 1-bit
direction label cannot express. That is a real question, but it is a smaller one than
this brief was originally written to justify, and the honest framing is that the
proposal is now optional rather than forced.

## 2. What the proposal is

**Target → cost-adjusted continuous outcome at the exit policy's own horizon.**
`y = label_ret_pct − c_rt`, where `c_rt` is the round-trip cost the label already
knows (cut #9: 0.6% on a Tier-3 22/38 bps account — re-read from config, never from
this file). Model output = expected net return, not P(win). The entry bar becomes
"E[net] > 0 with margin", which is what the pretrade EV gate already tries to compute
from a probability and a fixed payoff — the proposal moves the payoff INTO the target
instead of assuming it.

**Label → "cleared cost", not "hit barrier."** A correct-sign move that does not clear
`c_rt` stops counting as a win. The barrier geometry stays where ALGO-5 leaves it; the
label no longer rewards resolution.

**Feature set → subtract the dead, add nothing new.** Drop `ofi_dir` (structurally
zero for 13/15 assets — external books carry ETH/BTC only) and `sent_fear` (100% at
neutral per the overfit battery). Do NOT drop the 21 features the instrument flags
RESOLUTION-ONLY: under a magnitude target a volatility loader may become informative,
and dropping them now would bake the 1-bit target's confound into the next one.
**Tape-derived features do NOT enter.** T3 measured them against the continuous
outcome and nothing survived its placebo; the only cell that did is unsigned and so
cannot direct a trade.

**Pre-registration → before the first look.** The gate for the new target is registered
in `scripts/cohort_eval.py` terms BEFORE it is trained: n, effective-n deflation,
selection rule, readout vocabulary. The Dwork reusable-holdout result (63% accuracy from
pure noise when the holdout is reused adaptively, Science 2015, verified `[R3]`) is the
reason this order is not optional.

## 3. What each wrong action costs (primary sources, verified by research #3 where marked)

| action | cost if wrong | source |
|---|---|---|
| Retune the current target on the accruing gate | manufactures an edge from noise (63% from 50% ceiling) | Dwork et al 2015 — VERIFIED 3-0 |
| Read the accruing gate repeatedly and act on a crossing | ~5× Type-I inflation even at n=10,000 | Johari, Pekelis & Walsh — VERIFIED 3-0 |
| Ship a positive readout at face value | median 73% backtest→live Sharpe deterioration (215 bank strategies); 26%/58% return decay OOS/post-publication (97 predictors) | Suhonen et al; McLean & Pontiff — VERIFIED 3-0 |
| Tweak a live model to its OOS performance | no longer an OOS test; further overfitting | Arnott, Harvey & Markowitz 2019 — VERIFIED 3-0 |
| Abandon on an underpowered null | `[R3]` sequential-test / false-negative cost — angle 1 partially UNRUN | owed |
| Size on the measured edge | `[R3]` Kelly under parameter uncertainty (Baker & McHale 2013) — UNVERIFIED (abstract only) | owed |

## 4. What the proposal does NOT claim
- It does not claim an edge exists under the new target. T3 has now measured tape
  features against the continuous outcome and NOTHING survived its placebo, so the
  pre-training evidence is a null, not a promise.
- It does not claim the 1-bit target is the reason for the null. Reading (a) — there
  is simply no structure here at this horizon — remains fully consistent with every
  measurement in section 1, and the sample is too short to separate the two.
- It does not shorten MinBTL. Changing the target adds a trial to N; the sample stays
  0.065 yr. The new target's first readout is a statement about the instrument.
- It does not touch ALGO-5's geometry, GB-1's ratchet, sizing, or the fill simulator.
  It rides in the same adjudication because all three are cohort-resetting and the
  cohort should reset once.

## 4b. The honest case AGAINST this proposal
Stated so the operator is not choosing from a one-sided brief.
1. **It adds a trial.** N rises, MinBTL lengthens, and the sample is already 32-145x
   short. A new target makes the next readout harder to believe, not easier.
2. **The measured evidence is a null, not a lead.** Nothing in section 1 says the
   magnitude channel carries signal; it says the direction channel does not. Those are
   different claims and only the second is measured.
3. **It resets the cohort.** Era-6 accrual restarts from zero, and the era-4 readout
   (COST_BOUND at n=54) took months of wall-clock to reach.
4. **The cheapest alternative is to do nothing and keep accruing.** Time is the one
   input that raises the denominator without raising N. Deferring costs only the
   opportunity of an earlier answer, and the accrual continues either way.
5. **The forcing argument has since been measured away (2026-09-02).** This brief was
   written on "the current target cannot lose informatively". The decomposition test's
   measured power (0.05 SD detected 100% of the time) shows it CAN, and it did: the
   absence of directional signal is now a finding. A target change is therefore a
   research choice about the magnitude channel, not a repair of a broken instrument -
   and research choices at N-plus-one trials against a 0.065 yr sample are exactly what
   MinBTL says to be sparing with.
The case FOR remains: the current target cannot lose informatively, so an indefinite
deferral buys readouts that cannot change a decision.

## 5. Decision requested
Approve / defer / reject the bundling of the target change with ALGO-5/GB-1 at the
next cohort reset. Approval means: pre-register the new gate; then train; then read
out. Nothing is trained before the registration is written down.

> [!important] SUPERSEDED 2026-09-02 — RECOMMENDATION IS NOW **REJECT**, ON EVIDENCE
> The trigger this section named ("a power result on the CONTINUOUS target showing it
> resolves effects the 1-bit target cannot") HAS NOW BEEN RUN, and it came back
> negative on both halves:
> - **Power:** minimum detectable effect is **0.05 for BOTH** targets on the same 6,071
>   rows / 11 day blocks. The continuous target resolves nothing extra — a lateral move.
> - **Finding:** all 64 features scored against `label_ret_pct` give **5 CI-exclusions
>   against 6.3 expected by chance** (measured null, 10.0%) — below chance, exactly as
>   the 1-bit target reads. Largest |Spearman| anywhere 0.1017.
> So the proposal buys no resolution and finds nothing, against a certain cost of a
> cohort reset plus one more trial on N. **Reject.** Full account:
> `docs/quant/2026-09-02_flow_vs_eth_and_target_decision.md` Part 1.
> The DEFER reasoning below is kept as the record of what was believed before the
> measurement, per the both-sides rule.

**My recommendation changed on 2026-09-02 and this section says so rather than
quietly keeping the original.** When this brief was drafted I would have said approve,
because the 1-bit target could not lose informatively. It can, and it did. I now
recommend **DEFER**: keep accruing on the current registration, and revisit only if the
magnitude channel is worth a trial on its own merits. The one measurement that would
change my recommendation back is a power result on the CONTINUOUS target showing it
resolves effects the 1-bit target cannot - that has not been run, and it is the thing
to run before approving, not after.

## 6. Provenance
HANDOFF `EDGE-HUNTER MIRROR` items 1–9; `docs/quant/2026-09-01_edge_hunter_mirror_report.md`;
vault `sources/session-20260901-edge-hunter-mirror`, `concepts/resolution-vs-direction-decomposition`,
`raw/research/2026-09-01_deep_research_measurement_consequences.md`.
