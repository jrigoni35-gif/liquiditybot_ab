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

> **FOUR OF THESE FIVE ITEMS WERE CORRECTED OR RETRACTED ON 2026-08-16**
> by the adversarial seat this brief convened. Item 4 — the brief's ONLY
> fresh measurement and the load-bearing evidence for "there is no edge" —
> is **REFUTED**. The honest position after audit is that gross edge is
> **indistinguishable from zero in BOTH directions**, which is not the
> same as "no edge". This brief converted an underdetermined measurement
> into a refutation.

**1. ~~Fees are 32.8x the gross edge.~~ STALE + STATISTICALLY VOID.**
Independently reproduced (gross −$11.89, fees $380.49, net −$392.38 over
415 round trips) — but unusable twice over.

*(a) 98.6% of it predates the simulator it is used to judge.* By close
timestamp: 218 trips pre-passive-fix, 177 under the live double-count, 6
post-double-count, and only **14 on today's simulator** — where gross is
**+$0.82**, i.e. POSITIVE. On the 20 trips after `aeeaae36`, gross is
**+$1.10**. This brief's own FOR-1 says "everything measured before
2026-08-10 describes a simulator that no longer exists"; its lead item
AGAINST is a 2026-08-09 measurement. The document refutes its own headline
four paragraphs later.

*(b) The ratio divides by a statistical zero.* Per-trip gross sd $0.4849,
n=415 → SE of the sum **$9.88**, so gross = −11.89 ± 19.4 (95%), **z =
−1.20**. |gross| spans zero, so `fees/|gross|` has CI **[12.2x, +∞)**.
"32.8x" is 1/x evaluated at x≈0 — no stable magnitude. The vault states it
correctly ("gross ≈ 0"); this brief converted it into "a factor of 33".

**2. The geometry cannot pay, with no model in it.** [ASSERTED, vault
`the-money-path-thesis`, 2026-08-14] Breakeven target-hit rate =
`sl/(pt+sl)`. On h432: median pt 2.064%, median sl 1.548%, payoff 1.333 →
**breakeven 0.429 vs realized 0.225** → −0.734% per path.
**CORRECTED 2026-08-16:** live `cohort_eval.py` now reads realized
**0.291 → −0.4981%**, so the brief overstated the deficit by **47%**. And
its implicit null of 0.000% is wrong for a censored sample: the correct
driftless-with-vertical-barrier null is **−0.152%**, making the real
deficit **−0.35%**, not −0.73%. The direction survives; the magnitude does
not.

**3. Cost-to-volatility is the binding constraint.** [MEASURED
2026-08-01, this session] Round-trip cost 0.50% against a 2-hour sigma of
0.61% → cost/sigma 0.82. **UNDERSTATED 1.6–2.6x** — see the retraction of
FOR-3 below: an $800 book is Kraken Tier 1 (40/80), giving cost/sigma
**1.31**, or **2.11** at the observed 60.6% taker share. Measured
population round trip is **75.58 bps against 65 configured**
(`cost_truth_report.py`, n=479 legs). This item is the brief's most robust
AGAINST, and it is worse than stated.

**4. ~~Entry selection is anti-predictive.~~ REFUTED 2026-08-16 — THE
WRONG NULL.** This was the brief's only fresh measurement and it carried
the entire evidentiary weight of "there is no edge" on current instruments.

`b/(a+b) = 0.4286` is the first-passage probability for an **unbounded-time**
walk. These labels are **censored at a vertical barrier**, and because the
profit target sits FARTHER out (a/b = 1.333) it takes longer to reach — so
censoring removes PT-bound paths **preferentially**. Conditioning on
resolution is not neutral; it manufactures exactly the sign reported.

Verified two independent ways (exact lattice DP, and a re-derivation by
this session's author):

| censoring | correct driftless P(PT \| resolved) |
|---|---|
| ~0% | 0.4396 ≈ 0.4286 *(validates the method)* |
| 48.6% | 0.3758 |
| **86.4%** | **0.2351** |

The h24 case had **87.8% censoring** and observed **0.258** — which is
**ABOVE** the correct null, i.e. weakly **pro**-predictive. Applying the
correct null *and* this project's own effective-n standard (uniqueness
0.245 by de Prado concurrency):

| | brief's null | correct null, n_eff |
|---|---|---|
| h24 | −7.05 | **+0.58** (sign flips) |
| h432 | −4.21 | **−1.47** |
| pooled | **−3.24** | **−0.63 (p = 0.53)** |

**Nothing significant remains.** A residual h432 negative drift (≈ −0.35%
over 36h) may exist but is not significant, is measured on the *candidate*
stream which pays no fees, and has never been shown to transfer to the
live book. If any part of this claim becomes true, that is the piece to
watch.

**5. ~~Three INDEPENDENT refutations~~ — NOT INDEPENDENT, and pre-correction.**
Commit `415af0f9` (2026-08-09) — *"a hedge is an OPENING leg — the go/no-go
tool was answering backwards"* — fixed the SAME one-line defect in five
scripts at once, including all three of these: `breakeven_test.py`,
`geometry_search.py`, `random_entry_control.py`. They share a data path and
it was broken. The brief dates them 2026-08-05, **four days before the tool
that produced them was corrected**; the same commit records that the defect
INVERTED breakeven_test's printed verdict. `geometry_search.py` ran entirely
under the double-counting simulator. The corrected direction is worse for
the strategy so the conclusion likely holds, but these numbers are
pre-correction and the independence claim is false.

The original three, recorded for the record [ASSERTED, 2026-08-05]:
random-entry MFE 0.516 [0.439, 0.594] (no timing signal); a 48-combination
Bonferroni-corrected geometry grid in which no geometry survives (best
−0.400%, LB −1.124%); and break-even win rate `p=(cost+L)/(W+L)` > 1 at
every real fee schedule. **All three need re-running post-`415af0f9`
before they can be cited again.**

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
