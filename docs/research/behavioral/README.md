# Behavioral research folder — who loses, who harvests, what we can measure

**Status: DOCKET MATERIAL for the next execution-era boundary adjudication.**
Nothing here wires into decisioning. The 2026-08-10 operator adjudication froze
model-side investment (no new families, features, or meta-labeling); every
feature candidate in `06_sanity_check_spec.md` is PRE-REGISTERED ONLY and
**FORBIDDEN to implement** until operator adjudication at the boundary. All
tests specified here are SAFE class (measurement plane) per the era-4 accrual
moratorium in CLAUDE.md.

## Purpose

Five research lenses on the question behind the bridge hypothesis (Stella,
Ferrara & De Domenico 2018, PNAS 115(49):12435-12440, doi
10.1073/pnas.1803470115: bot-amplified narrative -> retail emotional flow ->
swings and liquidation cascades that patient capital harvests). Extends, never
re-derives: vault `concepts/who-loses-to-us` (monetize forced+emotional flow;
loser pool replenished not educated), vault `concepts/behavioral-isomorphism`
(disposition effect manufactured by exit geometry), repo
`docs/research/2026-07-26_criminology_manipulation_lens.md`, THALES engine
(shadow-first bot-footprint detectors).

## Grading legend

| Grade | Meaning |
|---|---|
| A | Peer-reviewed, replicated |
| B | Peer-reviewed, single study |
| C | Credible industry / regulator / court-record empirical |
| D | Theoretical/plausible — owed a measurement, never a fact |

A claim with no source is a TASK. Adversarially refereed claims carry a
verdict (STANDS / AMENDED / REFUTED); AMENDED claims appear in their amended
form with the referee's reason shown. A REFUTED flagship must appear with both
sides shown, never silently dropped (none in this batch were refuted outright;
several were amended, including statutory-wording and number-provenance
refutations inside otherwise-confirmed claims — read the verdict blocks).

## The monetizability bar

Fee reality (era-4 readout, 2026-08-26): true Kraken tier is 40/80 bps. Any
new edge must clear a cost-tolerance bar of **43 bps (distinguishable) to 118
bps (point-estimate) per round trip** per
`docs/quant/2026-08-22_walkforward_resampling_tranche2.md`. A behavioral
pattern that cannot clear that bar is graded anyway but tagged NOT monetizable
for us.

## Compliance fence

Detecting, measuring, and anticipating other participants' behavior is in
scope. Anything that would CREATE, trigger, or amplify cascades, manipulate
sentiment, or spoof is OUT OF SCOPE. Where the literature describes such
tactics they are framed strictly as detection targets.

## Claims index

| id | lens | grade | verdict | testable now? |
|---|---|---|---|---|
| gov-stablecoin-1 | 01 state | C | AMENDED | no (no reserve feed) |
| gov-offshore-1 | 01 state | C | AMENDED | partial (ATTR-2 owed) |
| gov-outcomes-1 | 01 state | C | — | analog only (WHY-1) |
| gov-lobby-1 | 01 state | C | — | no |
| gov-enforce-1 | 01 state | C | — | yes (manip_suspect trend) |
| gov-tax-1 | 01 state | C | — | analog only |
| gov-etf-1 | 01 state | C | — | no (no ETF-flow feed) |
| gov-mica-1 | 01 state | C | — | no |
| gov-fee-1 | 02 exchange | C | STANDS | yes (cost_attribution) |
| gov-fee-2 | 02 exchange | B | — | yes (maker/taker flags) |
| gov-liq-1 | 02 exchange | C | — | no (ATTR-2) |
| gov-liq-2 | 02 exchange | C | — | no (ATTR-2) |
| gov-fund-1 | 02 exchange | B | — | no (partial via OKX funding) |
| gov-pfof-1 | 02 exchange | C | — | no (scope caveat only) |
| gov-mm-1 | 02 exchange | C | — | partial (THALES shadow) |
| gov-wash-1 | 02 exchange | B | — | yes (Benford/size tests) |
| gov-list-1 | 02 exchange | C | — | yes in principle |
| gov-retail-1 | 02 exchange | C | — | no |
| retail-adverse-selection-1 | 03 retail | A (Taiwan) / B-D (transfer) | AMENDED | yes (fill-ledger decomposition) |
| retail-base-rate-2 | 03 retail | A | — | no (implication via T1) |
| retail-crypto-lossrate-3 | 03 retail | B | — | proxy only |
| retail-learning-failure-4 | 03 retail | B | AMENDED | partial (stationarity proxy) |
| retail-lottery-skew-5 | 03 retail | B | — | yes (low power) |
| retail-leverage-drain-6 | 03 retail | A | — | identity; cascade timing owed |
| retail-attention-buying-7 | 03 retail | B | — | no (ATTR-1) |
| retail-geometric-vs-psych-8 | 03 retail | C | — | yes (replay re-run) |
| retail-crypto-disposition-9 | 03 retail | B | — | partial |
| liq-asym-1 | 04 cascades | B | AMENDED | no (ATTR-2) |
| stop-cluster-1 | 04 cascades | A (clustering) / B (mechanism) | AMENDED | yes (event study) |
| cascade-ews-1 | 04 cascades | C | — | partial (spot OFI variance) |
| stophunt-folklore-1 | 04 cascades | D | — | yes (mechanical form only) |
| carry-decay-1 | 04 cascades | B | — | yes (conditioning only) |
| funding-cond-1 | 04 cascades | C | — | yes (recorded funding) |
| funding-structure-1 | 04 cascades | B | — | yes (cross-venue check) |
| postcascade-rev-1 | 04 cascades | D | — | yes (owed measurement) |
| bot-prev-1 | 05 sentiment | B | — | no (no platform feed) |
| pnd-anatomy-1 | 05 sentiment | B | — | no; detection target only |
| pnd-wealth-1 | 05 sentiment | A | — | partial (divergence flag) |
| sent-ret-1 | 05 sentiment | B in-sample; D at our horizon | AMENDED | yes (instrument first) |
| sent-ret-2 | 05 sentiment | C | AMENDED | yes (instrument first) |
| bot-flow-1 | 05 sentiment | B | STANDS | partial (HN attention leg) |
| pnas-shape-1 | 05 sentiment | B | — | no (no social-graph feed) |
| enforce-1 | 05 sentiment | C | — | partial (euphoria_spike) |
| narrative-1 | 05 sentiment | D | — | no (corpus too small) |
| attr1-design-1 | 05 sentiment | D | — | yes (headline replay) |

Files: `01_state_incentives.md` · `02_exchange_economics.md` ·
`03_retail_loss_mechanics.md` · `04_liquidation_cascades.md` ·
`05_sentiment_bots.md` · `06_sanity_check_spec.md` (the deliverable).
