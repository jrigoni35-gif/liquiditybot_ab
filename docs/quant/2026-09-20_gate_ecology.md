# Gate ecology + desk netting shadow (Lane F, first cut)

Date: 2026-09-20 (run 2026-09-20T07:29Z, era-9 = `12-10d4d0c2`, window since 2026-09-08T00:00:00Z)
Lane: SAFE class (measurement/report only). Advisory print; no engine file, config, or order path touched.
Script: `scripts/gate_ecology.py` · Tests: `tests/test_gate_ecology.py` (12 green) · Spec: `docs/superpowers/specs/2026-09-20-desk-instruments-plan2-sor-ipma-design.md` §3.

## Headline

- N = 80,024 arrivals over 175.5h (~456/h). EN-030 absorbs 62,494 (78.09%). EN-020 absorbs 0. EN-010 appears once as an EN-000 vector key. passed_gate_stack residual: 17,529 (21.90%).
- Desk-level absorb rate is nearly FLAT across realized-vol regimes: 74.1% (low), 78.0% (normal), 79.1% (elevated), 77.1% (extreme).
- Conditional per-gate absorb structure is UNIDENTIFIED for the pre-DE-010 window (inputs never logged — census 2026-09-19). The DE-010 capture went live 2026-09-20 ~07:00Z and holds exactly one batch (4 events, all EN-030).
- WSLS aspiration shadow: all 4 captured events UNIDENTIFIED — they sit past the corpus end (2026-09-18 23:59Z), and the corpus never fabricates a horizon.
- Desk netting shadow: 115 era fills; time-weighted gross 89,539 USD·h vs net 83,908 USD·h; offsettable 2,815 USD·h (3.1% of gross); peak offsettable $97.94.

## Method + Assumptions

- Audit reading: streamed, hash-chain verified with `core.audit.verify_chain` semantics (seam-adopting, torn-tail tolerant; tamper → `CHAIN_TORN` refusal), census parity. Refusal family: `CHAIN_TORN` / `AUDIT_UNREADABLE` / `NO_EN000_IN_WINDOW` / `CORPUS_MISSING` / `ECOLOGY_INCONSISTENT` — script-local, census precedent.
- Disposition vocabulary DERIVED, not assumed: every numeric EN-000 key is counted; EN-020/EN-030 are the registered absorb families (core/codes.py); `passed_gate_stack` is the residual (arrivals − absorbs). One EN-010 key appeared in the vector (registered in codes.py as the watchdog whole-sweep block) and is reported as an unregistered-tail key rather than silently folded in.
- Constants derived from config.json (overfit discipline): round-trip cost = maker 15 + taker 30 = 45 bps (`pretrade.*_fee_bps`, cut-#12 booking); aspiration = (min_edge_cost_ratio 1.3 − 1) × 45 = **13.5 bps net**; horizon = `ml.label_max_bars` 432 × 5m = 2,160 min; vol window = `vol_regime.fast_lookback_bars_5m` 100 × 5m = 500 min of 1m bars; regime percentiles 30/70/90 from `vol_regime`.
- ANALYSIS CHOICE (stated, NOT a config tunable): the percentile reference window for vol regimes is the asset's own trailing 30 days of 1m bars, ending at the tick — no lookahead. No existing config constant sizes a reference distribution; `REFERENCE_WINDOW_MIN` lives in the script, documented here.
- Section 3 join is DESK-LEVEL: pre-DE-010 absorbs carry no asset attribution, so each EN-000 tick's absorb delta is joined to the cross-asset max vol percentile at the tick instant. This bounds what the join can say; nothing is imputed to per-asset.
- Section 4 counterfactual: close-to-close horizon return net of 45 bps, entry at `decision_mid` (else corpus close at ts); direction unknown → both directions bounded, disagreement → UNIDENTIFIED. Corpus gap → UNIDENTIFIED.
- Section 5: per-position signed quantity from fills.csv (buy +q / sell −q, any purpose), each asset marked at its own last fill price; offsettable = min(long gross, short gross). Cross-asset netting assumes offsettable risk — a correlation caveat: BTC/ETH/LINK/PAXG offsets are NOT true hedges, so 2,815 USD·h is an upper-bound-style shadow, not a proposal.

## Section 1 — per-gate absorb counts/rates (era window)

| disposition | count | rate |
|---|---|---|
| arrivals N | 80,024 | 456.0/h over 175.5h |
| EN-030 (signal unconfirmed) | 62,494 | 78.094% |
| EN-020 (open entry resting) | 0 | 0.000% |
| EN-010 (watchdog blocks sweep) | 1 | 0.001% (tail key) |
| passed_gate_stack (residual) | 17,529 | 21.905% |

DE-010 captured events: 4 (one batch, 2026-09-20 ~07:00Z), all EN-030.

The 78% headline from the census stands at era scale. EN-020 = 0 is itself notable: with ~21.9% of arrivals passing the stack and entries rationed downstream (probe ticket, EV gate), a resting 5m entry order never once blocked a subsequent arrival in the window.

## Section 2 — conditional absorb structure

Pre-DE-010 window: **UNIDENTIFIED** (per-arrival gate inputs were never logged; the census measured this hole — 77,676 arrivals with counts only). EN-020 stage inputs: **UNIDENTIFIED** (the stage never logs gate inputs at all).

On the captured sample (n=4, one batch — illustrative, not evidence):

| gate | marginal fail | sole-absorber |
|---|---|---|
| if_1_flow_persistence | 100% | 0% |
| if_2_accumulation | 25% | 0% |
| if_3_directional_burst | 50% | 0% |
| if_4_funding_sanity | 0% | 0% |
| if_5_trend_alignment | 25% | 0% |
| v3_agreement | 100% | 0% |
| v3_evidence | 100% | 0% |
| v3_no_absorption | 0% | 0% |

Co-failure: v3_agreement&v3_evidence co-fail on 4/4; if_1_flow_persistence co-fails with both on 4/4. No gate is ever the sole absorber in this batch — every absorption is multi-gate. n=4: direction-consistent with coupled absorbers, far from a measurement.

## Section 3 — absorbs vs market state (desk-level vol join)

179 EN-000 ticks joined, 0 corpus-gap ticks (window ends before the corpus does; ticks past 2026-09-18 23:59Z would gap):

| desk vol regime (max asset percentile) | ticks | arrivals | absorb rate | mean pct |
|---|---|---|---|---|
| low (≤30) | 15 | 6,640 | 74.07% | 18.5 |
| normal (30–70) | 67 | 30,744 | 77.97% | 51.7 |
| elevated (70–90) | 83 | 36,020 | 79.13% | 79.0 |
| extreme (>90) | 14 | 6,620 | 77.10% | 95.5 |

Absorb rate moves ~5 points across the full vol range, non-monotonically. At desk granularity the absorb process is weakly coupled to realized vol at most.

## Section 4 — WSLS aspiration shadow

Aspiration = 13.5 bps net over a 2,160-min horizon. Events evaluated: 0; UNIDENTIFIED: 4 — the only captured batch sits at 2026-09-20 ~07:00Z, past the corpus end (2026-09-18 23:59Z), and the horizon would run further past it. No Pavlov advice printed; nothing imputed. The shadow is plumbed and will produce per-gate STAY/SHIFT advice as post-capture events accumulate inside corpus coverage (re-pull the corpus before the 09-22 boundary read).

## Section 5 — desk netting shadow

115 era-9 fills. Time-weighted gross exposure 89,538.69 USD·h vs net 83,907.76 USD·h; time-weighted offsettable 2,815.46 USD·h (~3.1% of gross) across 39 offsetting fill events; peak gross $562.72, peak offsettable $97.94. Open residual at window end: BTC −0.00050881 (the 2026-09-20 07:23Z entry, still resting) and dust (±1e-08) on PAXG/ETH/LINK. Unrealized netting exists but is small: the desk is net-long almost always, with brief short overlaps (PAXG/BTC shorts) rather than a two-sided book.

## Bottom line — echo-feud evidence, not verdict

The echo-coupling hypothesis is **not confirmed and not refuted** by what is identified:

1. Conditional absorb structure — the decisive test — is UNIDENTIFIED for 99.995% of the era window (pre-DE-010 by construction). The instrument now exists; the data starts accruing with the 2026-09-20 DE-010 go-live.
2. What IS identified cuts against naive echo-coupling: the desk absorb rate is nearly flat across vol regimes (74–79%), i.e. the 78% EN-030 rate is not a vol-regime artifact. That is consistent with gates rejecting independently of market state — and also with a constant-mix ceiling; the desk-level join cannot separate those.
3. The n=4 captured batch shows universal multi-gate co-failure (no sole absorber), direction-consistent with coupled flow/trend/v3 gates — but n=4 is an anecdote, and v3_agreement/v3_evidence are plausibly structurally related.

Evidence, stated flatly: the absorb pattern is consistent with correct independent rejection in a fee-dominated regime; echo-coupling remains UNIDENTIFIED pending post-capture accrual. Read at the 09-22 boundary with a refreshed corpus; the registered read points (n=50 lean / n=100 verdict) apply to the DE-010-captured population, not to this file.


---

## Pass 2 — 2026-09-20 23:17Z, corpus extended + DE-010 accrual

Two things changed since pass 1 (~07:29Z): corpus extended to 2026-09-19 23:59Z (§3 now joins 195 ticks with **0 corpus gaps**), and DE-010 accrual went from 4 events to **7,600** — §2 is now IDENTIFIED on the captured population. (Full stdout archived local-only at `outputs/research/ecology_pass2.txt`; outputs/ is gitignored — the numbers below are the durable copy.)

- §1: N = 87,620 over 191.6 h (~457/h); EN-030 68,158 (**77.79%**); captured-event absorb mix EN-030 5,668 / passed_gate_stack 1,932 → **74.6% absorbed among captured**, mildly below the era rate.
- §2 (now identified, n=7,600): **sole-absorber rates 0–6.0% across all eight gates while marginal fail rates run 30.9–57.9%** — absorption is overwhelmingly multi-gate. Top co-failures: v3_agreement × v3_evidence 37.9%, if_3_directional_burst × v3_agreement 35.1%, if_3 × v3_evidence 32.2%. Echo-coupling read: co-failure dominance is now MEASURED, not hypothesized. What remains unidentified is *why* they co-fail — genuinely correlated market features (correct common signal) vs consuming each other's outputs (echo-feud). Separating those needs per-gate counterfactual re-grading — a candidate instrument for a future adjudicated mint, NOT SAFE-plane today.
- §3: absorb flat across vol regimes stands — 74.07 / 78.43 / 77.59 / 77.10 (low/normal/elevated/extreme).
- §4 WSLS shadow: still UNIDENTIFIED — all 7,600 captured events postdate the coverable window.
- §5 netting shadow: era fills 121; time-weighted gross 96,342 vs net 90,440 USD·h; offsettable **2,951 USD·h (~3.1% of gross)**; peak offsettable $97.94; residual open BTC −0.00050881 still resting.
