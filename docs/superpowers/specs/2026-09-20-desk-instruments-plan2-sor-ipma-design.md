# Desk Instruments Plan 2 — SOR-corrected judge instruments (design)

Date: 2026-09-20
Status: APPROVED by operator directive 2026-09-20 01:47 ("criticize this answer and implement all aspects of it to prepare to the sept opening"). Supersedes the unshipped A/B/C/F four-lane sketch from the 2026-09-19 brainstorm thread.
Moratorium compliance: era-9 accrual moratorium in force. Every lane below is SAFE class (measurement/report tools, telemetry-only logging). No cohort-resetting surface is touched: entry decisioning, sizing, stop/exit geometry, fill simulator, fee booking, order lifecycle, universe, hedger, probe ticket, heat cap — all untouched. EXEC_ERA stamp (`12-10d4d0c2`) unchanged. R2 (`fix/decisioning-coupling-r123`) remains held for the 09-22 boundary ruling; nothing here merges it.

## 0. Origin and critique corrections

Origin paper (operator-supplied, identified via Crossref PII S0001691826014812):
Joshi, Baser & Sinthiya (2026), "What drives algo trading intentions? Insights from a stimulus organism response framework and importance performance map analysis", Acta Psychologica, DOI 10.1016/j.actpsy.2026.107680. n=382 retail traders, PLS-SEM + IPMA. Headline: technological infrastructure = strongest adoption driver; risk perception = strongest deterrent.

Self-critique of the first fold-in (binding corrections to the design):

1. Mediation overclaimed. PLS-SEM on cross-sectional self-report cannot establish causal mediation. SOR (Stimulus→Organism→Response) enters this design as a *prior to be tested against our own audit ledger*, never as an imported fact.
2. IPMA imported without its assumptions. PLS-IPMA requires performance scores observed on the full population; our gate stack is serially absorbing (MNAR). Naive importance estimated on survivors is selection-biased (Crook & Banasik null-result failure mode). Therefore IPMA survives only as an *output format*; importance is computed only where identified under explicit bounds, else printed as UNIDENTIFIED.
3. "78% EN-030 absorb = pathology" downgraded to hypothesis. In a fee-dominated regime, high rejection may be correct risk perception. Gate-ecology measurement (Lane F) decides; the paper carries zero causal weight about our bot.
4. Organism re-mapped. Gates are deterministic functions of current features; the true SOR "organism" analog is *persistent state* (heat, drawdown regime, aspiration level). Design consequence: shadow instruments log aspiration/win-loss state per gate (Posch-style memory), and any future judge grades through state-at-decision.
5. Population mismatch. One-shot adoption intention ≠ repeated per-arrival decision quality. Transferred: method (IPMA prioritization) and structure (O-layer). Not transferred: effect sizes.
6. Process. Fold-in language outran evidence; all claims from the paper are treated as direction-consistent headlines only.

## 1. Lane B′ — bounded doubly-robust retro pass (merges former lanes A and B)

New read-only script `scripts/reject_inference_bounds.py` + `tests/test_reject_inference_bounds.py` + dated record `docs/quant/2026-09-20_reject_inference_bounds.md`.

Purpose: answer, with explicit identification width, "could the absorbed strata of the 77,676 pre-DE-010 arrivals (2026-09-08 era start → DE-010 capture) hide net edge?" — the bounded reject-inference question.

Method:
- Input strata exactly as classified by `scripts/gradeability_census.py` (gradeable g, lost-forever L, deep-pipeline D, CV-with-asset); the census script is the seam for audit reading and refusal style (CHAIN_TORN / AUDIT_UNREADABLE / NO_EN000_IN_WINDOW / CENSUS_INCONSISTENT family — script-local, matching census precedent).
- For each arrival record, recover what the record actually carries (ts, asset, direction where present). Where a field is absent, widen the bound accordingly (both directions / all corpus assets) and report the widened stratum separately. Never fabricate a field.
- Counterfactual outcome bounds: Manski-style worst/best net-of-fee outcome over the bot's own evaluation horizon, computed from the corpus (research/corpus/binance_vision, 4 symbols × 1m bars, 2024-01-01→2026-09-18) conditional on the arrival's ts/asset when available; unconditional otherwise. Horizon and fee constants are DERIVED from config.json / existing strategy constants — no invented literals (overfit discipline).
- Where the realized action exists (gradeable stratum), report the doubly-robust estimate of taken-action value alongside the counterfactual bound; propensity of taken actions under the deterministic policy is 1.0, which is stated in the record, and counterfactuals are bounded, never point-estimated.
- Output: per-stratum bounds table + per-gate DR-IPMA table (importance = DR-corrected marginal effect on net edge where identified, else UNIDENTIFIED; performance = absorb rate + bound width) printed to stdout and written into the dated record. Refuse-on-inconsistency: any census mismatch, torn chain, or missing corpus coverage → refusal banner + nonzero exit, census-style.
- Read-only: no writes outside docs/quant record; no engine imports that mutate state; no order-path contact.

## 2. Lane C — propensity logging in DE-010

main.py DE-010 capture payload gains key `propensity: 1.0` (constant; deterministic policy ⇒ propensity of the taken action is 1.0), with a comment citing the anti-Zimbardo rule (propensity logging BEFORE any exploration scaling). Additive payload key with default — hard invariant 7 (extend with defaults). Capture remains guarded/never-raises. No new reason code: existing `Code.DE_DECISION_EVENTS` event; payload keys are not codes. Existing DE-010 tests updated to assert the key; new test asserts the value is 1.0 under the current deterministic policy.

Rationale for landing before the boundary: the runner still runs pre-capture code; DE-010 goes live on next boot. Landing propensity now means the live schema is born complete — no mid-era schema break.

## 3. Lane F (first cut) — gate ecology + desk netting shadow

New read-only script `scripts/gate_ecology.py` + `tests/test_gate_ecology.py` + dated record `docs/quant/2026-09-20_gate_ecology.md`.

Purpose: the echo-feud measurement — test whether gates absorb independently of one another and of market state, or whether absorb patterns are echo-coupled (the 78% EN-030 hypothesis). Advisory print only.

Sections:
1. Per-gate absorb counts/rates over the era window (from EN-020/EN-030/passed_gate_stack dispositions in the audit trail).
2. Conditional absorb structure: P(absorb at gate k | survived to k) per stage; flag stages whose conditional rate is unexplained by the stage's own inputs where those inputs are logged; where inputs are not logged (pre-DE-010), print UNIDENTIFIED rather than imputing.
3. Absorbs vs market state: join absorb timestamps to corpus-derived volatility regime (realized vol of the asset's 1m bars in a trailing window; window derived from existing constants where one exists, else stated as an analysis choice in the record, not a config tunable).
4. WSLS aspiration shadow: per gate, an advisory win/stay–lose/shift log against the fee-floor aspiration (aspiration = net-of-fee edge hurdle already in config; derived, not invented). Prints what a Pavlov rule *would have done*; changes nothing.
5. Desk netting shadow: gross vs net cross-asset exposure from order/position audit records over the era window; prints unrealized-netting opportunities as a report section.

Refusal style, read-only constraint, and test seam: as Lane B′ (census precedent).

## 4. Error handling, interfaces, testing

- Both scripts: stdlib + pandas only; stream the audit JSONL (do not load whole files unboundedly); exit nonzero with a registered-style refusal banner on any inconsistency.
- No changes to public engine interfaces; Lane C is additive-with-default only.
- Tests: synthetic audit/corpus fixtures per lane (small, deterministic); no network; no real outputs/ dependency.
- DoD matrix before done: full pytest (-n 10 --dist loadfile -p no:cacheprovider), smoke_test, assurance_check, overfit_check, ruff (DoD scope), pyright (DoD scope — zero errors; main.py is in scope for Lane C), bandit, compileall.

## 5. Out of scope (explicit)

Any live decisioning change; enabling exploration; merging R2; promoting any shadow instrument beyond advisory print; changing config thresholds; any change that alters which orders are placed or how they fill.

## 6. 09-22 boundary relevance

Lane B′ bounds what the lost 99.93% could hide → informs the n=50/n=100 lean ruling. Lane C closes the propensity-logging hole before any future exploration proposal. Lane F tests the echo-feud hypothesis → direct input to the R2 adjudication (frozen-tier mint precondition).
