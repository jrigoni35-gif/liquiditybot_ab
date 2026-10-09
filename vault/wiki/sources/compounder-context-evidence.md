---
title: Compounder Context Evidence (2026-07-24)
category: source
summary: Evidence-graded adjudication of every candidate macro/cycle/flow/sentiment input, each with a grade, encoding, DoF cost, and where killed the citation that killed it — partially superseded 2026-08-08 (ETF-flows rejection REVERSED on its own revisit terms; COT reinterpreted as basis-trade mechanics; the stablecoin 1-DoF adoption demoted to a never-graduating 0-DoF dial; the ledger now treated as CLOSED)
tags: [evidence-grading, dof-budget, macro, psychology, literature]
sources: 2
updated: 2026-08-08
---

# Compounder Context Evidence (2026-07-24)

**Raw source:** `raw/research/2026-07-24_compounder_context_evidence.md`

**Status: FILED.** Two passes: literature adjudication of 8 candidate input families, plus an addendum
on participant psychology, LLM frameworks, and a database inventory.

## Governing rules
- **REJECTED entries are part of the record: future sessions must not re-propose them without new
  evidence.**
- Honesty rule: "~3 complete 4-year cycles exist; **nothing is learned at that horizon** — inputs
  enter only as deterministic structural context."
- Everything graded against what the repo already enforces (purged walk-forward, shuffle nulls, PBO on
  the deployed rule, DSR).

## The DoF ledger
Corpus 3,628 rows; 62 deployed features -> ~58.5 rows/feature. "The binding constraint is not OF-7's
floor but the program-wide 'handful' cap and the dead-feature check." **Central encoding principle:
"slow context belongs in structural gates and the long book's admission rule, not in the 5m model
matrix."** Structural gates cost **zero model DoF**. See [[concepts/dof-budget]].

## What was adopted
**3-4 model-adjacent features max**: a composite FRED stress dial (1 DoF, fixed-clip z-scores, no
fitted weights, down-only), a CFTC COT net-positioning delta (1 DoF), a stablecoin aggregate-supply
delta (1 DoF).
**At 0 model DoF**: the halving phase clock as a structural gate (buckets are labeled **CONVENTIONS,
not findings**); CME-expiry and FOMC **cadence-pause** gates (vol evidence real, direction
contradictory -> pause, never sign); ladder-placement hygiene; point-in-time discipline as a process
rule; deterministic retention tiers in the A1 digest.

## Notable kills, each with its killing citation
- **On-chain MVRV-Z** (reported Sharpe 1.28 vs 0.45 buy-and-hold): "an in-sample rule fit over exactly
  3 cycles with no purged walk-forward, no shuffle null, no PBO, no DSR — precisely the artifact
  OF-3/OF-5 exist to catch. **The Sharpe is a red flag, not a benchmark.**"
- **ETF flows** — MODERATE evidence but **no keyless machine-readable source**. Rejected on
  [[concepts/availability-failure-mode]] regardless of evidence.
- **Day-of-week** — in-sample effects published, but a 2024 study shows the Monday effect diminished
  and the **Friday sign flipped**. "Anything more is seasonality mining."
- **AI-investment wave** — rejected **by absence** of any peer-reviewed study; the NVDA-BTC
  correlation "is the shared risk-appetite factor already established by the macro literature and
  already present as `equity_risk_z`."
- **Social sentiment as direction** — tweet *volume* predicts volume and volatility, **not returns**;
  robustness fails once controls change; the authors themselves document bot contamination.

## Pass 2 — participant psychology
Zero new model features. Disposition effect (STRONG): "the repo's exit machinery IS the inversion" —
the ratchet rides winners, protocol stops cut losers. Overtrading/attention (STRONG): price rises
recruit NEW retail cohorts across 95 countries, ~3/4 estimated to have lost money -> **"NEVER add a
chase/urgency path to the long book."** Insider information: the **routine vs opportunistic** split is
"the most transferable" — never fade, never join late. Institutional herding (STRONG): the discipline
is **DON'T FADE** — "fading it = trading against informed flow."

## "Who loses to us, mechanically"
We monetize (1) attention-recruited late-cohort retail — "the loser pool is **replenished, not
educated**"; (2) forced sellers in stop cascades — "flow is forced, hence uninformed at execution";
(3) disposition-effect holders capping rallies at magnets. We stand down before insiders and herding
institutions, and veto entries aligned with spoofers. **"The classifier between them is priced adverse
selection plus THALES, not confidence."** See [[concepts/who-loses-to-us]].

## 2026-08-08 supersessions — the follow-up adjudication
([[sources/session-20260808-institutional-data-adjudication]]; recorded per the vault rule
*what was claimed → what changed → what stands*.)

- **The ETF-flows rejection is REVERSED — the revisit trigger fired on its own terms.**
  Claimed: MODERATE evidence, no keyless source, rejected on
  [[concepts/availability-failure-mode]]. Changed: a published study arrived (Lim SSRN
  6592830) and usable sources exist (Farside with browser UA; SoSoValue free API). Stands:
  ADOPT, telemetry-first at 0 DoF, with a publication-time lookahead hazard.
- **The COT net-positioning adoption is REINTERPRETED, not withdrawn.** Claimed: a COT
  net-positioning delta worth 1 model DoF. Changed: CME **leveraged-fund net shorts are
  basis-trade mechanics, NOT bearishness** — reading COT directionally is a **category
  error**; the directional information lives in the live basis itself, and the crypto
  categories live in the **TFF report (Socrata `gpe5-46if`), not Disaggregated** (zero
  crypto rows). Stands: a **weekly regime dial only, 0 DoF, never directional, never a
  model feature**.
- **The stablecoin aggregate-supply delta (1 DoF) is DEMOTED.** Changed: **Lyons &
  Viswanath-Natraj** — issuance is **endogenous to demand**. Stands: the existing
  `stable_wk_pct` dial at **0 DoF, never graduating** to the model matrix.
- **The "3-4 model-adjacent features max" allowance is moot in practice.** The ledger this
  page opened is now treated as **CLOSED** — at 64 features vs ~61 fresh-era labels,
  effective-DoF arithmetic funds ~2-5 context features *total*, already spent
  ([[concepts/dof-budget]]). Zero new model features until the label corpus funds them.

What is **not** touched: every other kill on this page stands (MVRV-Z, day-of-week,
AI-wave, social-sentiment-as-direction), as do the psychology pass, the who-loses taxonomy,
and the central encoding principle — which the 08-08 adjudication re-applied unchanged.

## LLM frameworks verdict
Adopt Qlib's **point-in-time discipline** as a 0-DoF process rule; reject its factor mining ("instant
OF-7 death"). Adapt FinMem's decay-tiered memory as deterministic retention tiers. Reject DDG-DA,
FinGPT, FinRL-Meta. FinAgent's +36% is "INADMISSIBLE" (no purge/null/PBO). StockAgent is filed as
**"negative evidence FOR us"** — LLM agents' decisions vary by underlying model, i.e. not replayable.
RD-Agent(Q)'s ">70% FEWER factors" headline is kept as external support for our own cap.
