# Boardroom brief — does the money path exist, and what is the stopping rule?

**Status: BRIEF ONLY. No decision taken.** Every figure is [MEASURED] with
its source, [ASSERTED] if quoted from a prior document, or [UNKNOWN].
Nothing here is modelled, projected, or assumed.

## The question

The operator has run this bot for ~5 weeks in DRY_RUN. The engineering is
in unusually good order — hard invariants hold under adversarial probing,
the audit chain is sound, the instruments have been repaired repeatedly.
The question is no longer *is it built correctly*. It is:

> **Is there a configuration in which this strategy nets positive after
> costs — and if the answer is not yes, what is the pre-committed rule
> for stopping?**

## The measured case AGAINST a money path

**1. Fees are 32.8x the gross edge.** [ASSERTED, 2026-08-09 unbiased
economic finding, `docs/quant` + vault `synthesis/the-money-path-thesis`]
Gross P&L before any fees **−$11.66**; fees **−$382.59**; net all-in
**−$394.25 (−7.89%)**. The strategy is not losing to the market. It is
losing to its own cost stack by a factor of 33.

**2. The geometry cannot pay, with no model in it.** [ASSERTED, vault
`the-money-path-thesis`, 2026-08-14] Breakeven target-hit rate =
`sl/(pt+sl)`. On h432: median pt 2.064%, median sl 1.548%, payoff 1.333 →
**breakeven 0.429 vs realized 0.225** → **−0.734% per barrier-resolved
path GROSS, pre-cost**. This is arithmetic on the label geometry — it is
model-independent and upstream of every ML question.

**3. Cost-to-volatility is the binding constraint.** [MEASURED
2026-08-01, this session] Round-trip cost 0.50% against a 2-hour sigma of
0.61% → **cost/sigma = 0.82**. You pay 82% of one standard deviation in
fees per round trip. Reaching cost/sigma 0.20 needs a ~34-hour hold;
0.10 needs ~5.6 days.

**4. Entry selection is anti-predictive at the labeled geometry.**
[MEASURED, this session] Among resolved candidate rows, P(hit target
first) = 0.258 against a driftless gambler's-ruin expectation of 0.429 —
**z = −3.24**. Measured at BOTH horizons (h24 z=−4.31, h432 z=−4.14), so
it is not an artifact of the barrier width. Scope: candidate/simulated
rows; live rows have too few resolutions to test.

**5. Three independent refutations already retired "better model" as a
lever.** [ASSERTED, 2026-08-05] Random-entry MFE 0.516 [0.439, 0.594] (no
timing signal); a 48-combination Bonferroni-corrected geometry grid in
which **no geometry survives** (best −0.400%, LB −1.124%); and break-even
win rate `p=(cost+L)/(W+L)` **> 1 at every real fee schedule**.

## The measured case FOR continuing

> **TWO OF THESE FOUR PILLARS WERE RETRACTED ON 2026-08-16** under
> adversarial review by the panel this brief convened. Pillars 2 and 3 did
> not survive; pillars 1 and 4 did. Both retractions were errors by the
> brief's own author, and both pointed the same way — toward continuing.
> The case FOR is materially weaker than this document originally claimed.

**1. The corpus is now honest, and it was not before.** Two fill-model
corrections landed: `passive_base_prob` 0.45 → **0.048** (measured by
inverting the market's own trade-through rate over 22,854 trials on 2.4 GB
of book frames), and `aeeaae36` removed a double-counted crossing. Prior
results were earned under flattered fills. **Everything measured before
2026-08-10 describes a simulator that no longer exists.**

**2. ~~The learning curve is still climbing.~~ RETRACTED 2026-08-16.**
This cited `delta_auc = +0.033` / "data-starved: more rows are still buying
skill". **That figure exists in no artifact on this machine** — grep across
all of `outputs/` and `docs/` returns nothing. The only real-data reading
(cloud-mirror, 2026-07-31, 2,141 rows) carries the **opposite sign**:
`learning curve trend FLAG — DECLINING (delta_auc=-0.034 < -0.03) — later
rows are HURTING skill`. Both of today's reports decline to measure it at
all: *"SYNTHETIC benchmark dataset — corpus-size trend has no market
meaning; skipped"*, on **347 rows against a 640 floor**.

A false green inside the document written to adjudicate false greens.

**3. ~~The cost stack has never been optimised.~~ RETRACTED 2026-08-16.**
This cited a 10bps Kraken volume tier. **No such tier exists.** The vault's
own triple-confirmed schedule (2026-08-07,
`sources/session-20260807-institutional-review` §C) is Tier 1 ($0+)
**40/80**, Tier 2 30/60, Tier 3 22/38, **Tier 5 ($50k+) ~15/30 is the
deepest row** — and an $800 book sits at **Tier 1**.

So the cost stack is not un-optimised, it is **UNDER-STATED**, and this
pillar points the OPPOSITE way:

| premise | round trip | cost/sigma | breakeven hit |
|---|---|---|---|
| this brief's original 25bps maker/maker | 0.50% | 0.82 | 0.567 |
| **Tier 1 maker/maker (40bps)** | **0.80%** | **1.31** | 0.650 |
| **Tier 1 @ observed 60.6% taker** | **1.285%** | **2.11** | 0.784 |
| zero fees | 0.00% | 0.00 | **0.4286** |

The fee-constant work remains adjudicated and **HELD behind the h432
verdict**. That part stands.

**4. Nothing has been risked.** DRY_RUN throughout, invariant #1 verified
by execution. The entire loss is paper.

## What CANNOT be decided from the current evidence

**The verdict instrument cannot resolve its own question.** [MEASURED
2026-08-15T22:07:30Z] Era-4 gate at **14/50**; effective n **4.287 of 14**
(uniqueness 0.306, SE inflation ×1.807). `cohort_eval` assumes per-trade
sd ~0.5%; **measured sd is 2.7341% — 5.5x**. Projected to n=50:
n_eff ≈ 15, resolvable-edge floor **1.40–1.73%** gross per trade against
an observed gross mean of **+0.64%**.

> **At n=50 the gate will fire a verdict on a quantity two to three times
> smaller than its own noise.** Waiting for it, as specified, buys a
> coin flip dressed as a decision.

Compounding: the cohort is `MIXED(both)` — 93% probe admissions, 7/14
straddle a model deploy, 4/14 carry stale-binary legs, two label eras. And
the fee-free gross **disagrees in sign between populations**, so
COST_BOUND can be confirmed or refuted depending on which is read.

## The structural facts a decision must survive

- **DL-1**: cold-start prior 0.56 < entry bar 0.690239, and `min_p_win`
  0.55 is also below it. Only the probe lane clears, by +0.0098. **The
  gate is total the instant `dry_run=false`.** Clearing it is
  cohort-resetting.
- **Zero fills** at the honest fill rate: `maker_fills 0, taker_fills 0`.
  The config predicted it: *"paper entry rate will drop sharply — that is
  the honest fill rate, and starving is the truthful outcome."*
- **Accrual is a queue service rate, not a market rate**:
  `max_concurrent_positions = 5`, with 332 "max concurrent positions
  reached" blocks in 2.8h.

## The three decisions actually on the table

1. **The stopping rule.** What measured result, at what n, ends this? It
   must be written before the readout, not after.
2. **Is the cost stack the experiment?** Every measurement points at costs
   rather than signal. Running that experiment means fee-tier work and a
   longer horizon — and the fee constants are currently HELD behind the
   very verdict that cannot resolve.
3. **Does the gate get repaired before it fires?** n=50 was pre-registered
   against an assumed sd 5.5x too small. Raising n is a change to a
   pre-registration and can only be decided BEFORE the readout.
