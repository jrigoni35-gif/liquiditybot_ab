# THALES registry — exploitable human mistakes, governed

Contract: `docs/thales/README.md`. Schema enforced by
`tests/test_thales_registry.py`.

last_boundary: 2026-08-11 (execution-era cut #7, `e7d5ca1a`, geometry epoch)

Statuses: REGISTERED | EVIDENCED | STAGED | INCORPORATED | DORMANT | REJECTED.
Non-terminal entries must carry a `reviewed` stamp >= last_boundary and a
non-empty trigger. Detail blocks below the table are mandatory.

## Summary

| id | human mistake | status | trigger | reviewed |
|---|---|---|---|---|
| TH-R-001 | clustered stops at round numbers and swing extremes | INCORPORATED | advise promotion at freeze-lift adjudication (double-count hazard must resolve first) | 2026-08-27 |
| TH-R-002 | metronome cancel/replace on a timer (vendor default cadence) | DORMANT | review each boundary; re-arms if watched universe changes | 2026-08-27 |
| TH-R-003 | uniform evenly-spaced grid ladders (grid-bot defaults) | DORMANT | review each boundary; re-arms if watched universe changes | 2026-08-27 |
| TH-R-004 | clock-bucket herding (time-driven entries/exits) | INCORPORATED | shuffle-null upgrade of the detector (SAFE-NOW instrument fix) | 2026-08-27 |
| TH-R-005 | spoof flicker at the touch (painted then pulled) | INCORPORATED | doc reconciliation (code ships what the doc says is unbuilt) | 2026-08-27 |
| TH-R-006 | bar-close herding (candle-close crowd behavior) | INCORPORATED | SAFE-NOW hygiene: emit TH-015 or demote the feature | 2026-08-27 |
| TH-R-007 | mechanical grid-bot order-flow signature (periodicity, cancel-to-fill, replenishment) | REGISTERED | recording-capability adjudication (trade prints), then report-only study | 2026-08-27 |
| TH-R-008 | funding-rate crowding (naive carry herd) | EVIDENCED | SAFE report-only series now; feature columns at freeze lift | 2026-08-27 |
| TH-R-009 | perp-spot basis dislocation (naive basis crowd) | EVIDENCED | SAFE derivation report now; feature columns at freeze lift | 2026-08-27 |
| TH-R-010 | leveraged-crowd liquidation cascades (OI blindness) | REGISTERED | new read-only adapter capability = operator adjudication | 2026-08-27 |
| TH-R-011 | disposition effect (ours, epoch-4 ground truth) | INCORPORATED | none pending; stands as tier-1 archetype calibration trace | 2026-08-27 |
| TH-R-012 | fee blindness (ours: booked half the true tier) | STAGED | era-4 readout adjudication (COST_BOUND arm 2D + staged fee-truth package) | 2026-08-27 |
| TH-R-013 | overtrading / action bias (ours, deliberate but fee-underpriced) | STAGED | era-4 readout adjudication (2D fewer-larger, CONC-1, ALGO-5) | 2026-08-27 |
| TH-R-014 | fear-herding gate that fired backwards (ours: anti-selective crisis veto) | STAGED | boundary adjudication of REG-8 v2 dissolution (cost overlay first) | 2026-08-27 |
| TH-R-015 | per-counterparty exit timing (minimal_roi ladders) | REJECTED | reopen only if an entry-time-cohort data source appears read-only | 2026-08-27 |

## Section A — other participants' mistakes (capture as edge)

#### TH-R-001 — clustered stops at round numbers and swing extremes
- Footprint: stop orders herd at round-number grid levels and prior swing extremes; sweeps pierce then revert (Osler). The only THALES footprint firing live on Kraken BTC/ETH — 100% of shadow advice events (docs/THALES_FRAMEWORKS.md, live-calibration note).
- Capture: TH-013 detector -> `th_stopzone` model feature (live in every p_win); `LB-020` long-book bid hygiene shifts our resting bids off magnet zones (risk/long_book.py:508-544); defensive-cadence lens (scripts/defensive_cadence_report.py).
- Evidence: strategies/thales.py:617-725; docs/quant/2026-07-29_thales_unit_audit.md (A-2 geometric-null subtraction); docs/quant/2026-08-14_edge_training_design.md:60-62 (th_* wf-importance under prior champion).
- Falsifier: reliability ledger Wilson LCB falls to the base-rate null (probation mute, strategies/thales.py:215-292).
- Notes: doc-promised book-thinness weighting (`liq.depth_ratio`) never built — divergence, not defect; advise-channel promotion is blocked by the double-count hazard (docs/quant/2026-08-14_edge_training_design.md:129-131).

#### TH-R-002 — metronome cancel/replace on a timer
- Footprint: top-of-book replaced at near-constant cadence with low interval variance (Hummingbot PMM `order_refresh_time`, template 30s).
- Capture: TH-011 detector -> `th_metronome` feature.
- Evidence: strategies/thales.py:483-507; docs/THALES_FRAMEWORKS.md live finding: ~0 events on Kraken BTC/ETH — calibration working, population absent.
- Falsifier: remains ~0 across two consecutive execution eras on the full (skimmer-widened) universe -> REJECT as venue-absent.

#### TH-R-003 — uniform evenly-spaced grid ladders
- Footprint: N-per-side evenly spaced, size-uniform resting ladders that persist across snapshots (Pionex/3Commas/Hummingbot `order_levels` defaults).
- Capture: TH-010 detector -> `th_grid` feature.
- Evidence: strategies/thales.py:441-481; docs/THALES_FRAMEWORKS.md live finding ~0 on Kraken majors.
- Falsifier: same as TH-R-002.

#### TH-R-004 — clock-bucket herding
- Footprint: entries/exits clustered in intraday clock buckets (bots acting on timers, not events).
- Capture: TH-012 detector -> `th_clockwork` feature; ranked #1 walk-forward importance under the prior champion.
- Evidence: strategies/thales.py:592-615; docs/quant/2026-08-14_edge_training_design.md:60-62.
- Falsifier: the doc-mandated shuffled-null (docs/THALES.md, TH-012 spec) kills the score where the shipped pooled-variance z-gate passed it.
- Notes: code implements a z-gate where the doctrine mandates a shuffle null — the trigger is that upgrade; until then this entry's evidence quality is capped.

#### TH-R-005 — spoof flicker at the touch
- Footprint: large near-touch levels painted and pulled young, side-asymmetric (Cartea-Jaimungal-Wang signature).
- Capture: TH-017 detector, defensive shade DOWN only (safety, never graded as alpha); consumed-level innocence pinned in tests.
- Evidence: strategies/thales.py:371-439; tests/test_thales_spoof.py; config.json `thales.spoof`.
- Falsifier: flicker score fails to separate from feed noise on lapse-clean windows.
- Notes: docs/THALES.md still lists TH-017 as "not built" — the doc, not the code, is wrong; reconciliation is the trigger.

#### TH-R-006 — bar-close herding
- Footprint: crowd behavior concentrated at candle closes (bar-watching humans and bots alike).
- Capture: TH-015 scorer -> `th_barclose` feature (live in the corpus).
- Evidence: strategies/thales.py:894-927; tests/test_barclose_and_osler.py.
- Falsifier: herding score indistinguishable from uniform across two eras.
- Notes: `Code.TH_BARCLOSE_HERD` is registered but NEVER emitted (core/codes.py:408, zero call sites) — the feature influences p_win while invisible to the audit trail; flagged in docs/quant/2026-08-20_learning_symmetry_result.json as registry hygiene.

#### TH-R-007 — mechanical grid-bot order-flow signature
- Footprint: level periodicity, fixed-spacing replenishment, high cancel-to-fill, order-arrival autocorrelation — the actual event-level fingerprint of a naive automated counterparty.
- Capture: none today. Recordings carry NO order events and NO trade prints (kraken feed records book snapshots only — scripts/fill_hazard_report.py header states it directly). Detection would need trade-print capture first.
- Evidence: absence documented by the counterparty-flow survey (docs/quant/2026-08-27_thales_ladder_analysis.md).
- Falsifier: with prints captured, no periodicity/replenishment structure found on our Kraken pairs at spot scale.

#### TH-R-008 — funding-rate crowding
- Footprint: naive carry herds crowd positive-funding sides; funding sign-persistence and dispersion carry crowd-positioning information.
- Capture: today funding is a magnitude veto (`if_4_funding_sanity`) plus a settlement-clock feature (`funding_dist`) — never a series. Per-symbol funding is already live from OKX (data/okx_feed.py:168-177); history/dispersion/persistence are derivable from existing read-only calls.
- Evidence: strategies/informed_flow.py:387-391; ml/features.py:121,133; ATTR-2 (docs/HANDOFF.md) names the adjacent blindness.
- Falsifier: funding series adds no out-of-sample information for SPOT fills net of costs (we pay no funding; the channel is informational only).
- Candidate columns at freeze lift: funding sign-persistence, cross-venue dispersion (pre-register before any build).

#### TH-R-009 — perp-spot basis dislocation
- Footprint: naive basis crowds push perp-spot spread; dislocations mark leveraged-crowd stress.
- Capture: none as signal. Both legs are already fetched every cycle and only ever price-merged; basis appears in the codebase solely as a CONTAMINANT (regime/liquidity_regime.py:281-291 — the SD-003 false-spoofy cause; :84-90 crossed-book sentinel).
- Evidence: regime/liquidity_regime.py:84-90,281-291.
- Falsifier: derived basis series is noise at our horizons (no predictive content for spot outcomes).
- Candidate columns at freeze lift: basis level/z per asset (pre-register first). SAFE now: report-only derivation.

#### TH-R-010 — leveraged-crowd liquidation cascades
- Footprint: OI build-ups and liquidation cascades (the $1.44B cascade of 2026-08-20 was invisible to this bot — ATTR-2).
- Capture: none; no adapter fetches OI or liquidations anywhere (repo-wide: `fetchOpenInterest` zero hits).
- Evidence: docs/quant/2026-08-20_event_record_surge_outlier.md; docs/HANDOFF.md ATTR-2.
- Falsifier: cascade markers do not move our entry-horizon outcomes on spot.
- Notes: requires genuinely NEW read-only capability — operator adjudication before any code.

#### TH-R-015 — per-counterparty exit timing (minimal_roi ladders)
- Footprint: freqtrade `minimal_roi` exits N minutes after each trade's OWN entry — real, but the clock starts at a timestamp we cannot observe.
- Capture: REJECTED — not observable from public market data without counterparty entry-time cohorts; "left uncovered on purpose rather than faked" (docs/THALES_FRAMEWORKS.md, TH-012 gap note).
- Evidence: docs/THALES_FRAMEWORKS.md coverage table.
- Falsifier: n/a (terminal). Reopen condition: a read-only data source exposing entry-time cohorts.

## Section B — our own mistakes (capture as correction + archetype ground truth)

#### TH-R-011 — disposition effect (ours)
- Footprint: epoch-4 ($5,000, 25.1d, -7.93%): win 3.8%, MFE capture -3.341 while 87% of trades HAD upside, cost drag +0.437% — the classic cut-winners-ride-losers signature, recorded in our own ledger.
- Capture: corrected by the h432 geometry re-cut (post-432 capture -0.652); retained as the CALIBRATION TRACE for the naive-tier archetype in any ladder study — a real bad-bot recording, not an invention.
- Evidence: scripts/cohort_eval.py pre/post-432 sections (reproduced 2026-08-27); pc-live equity.csv epoch scan.
- Falsifier: MFE capture < -1 recurring in era-4+ postmortems would reopen this as uncorrected.

#### TH-R-012 — fee blindness (ours)
- Footprint: configured 25/40 bps vs true Kraken tier 40/80 (injection-verified); fees consumed ~83-87% of gross realized at BOOKED schedule; probe tuition resolved negative at TRUE fees. The #1 naive-bot mistake, found in our own config by an independent instrument (cost_truth_report), invisible to the loop that used it.
- Capture: fee-truth package STAGED (docs/quant/2026-08-25_boundary5_adjudication.md); decision-table COST_BOUND arm 2D executes it with ALGO-5 at the readout adjudication.
- Evidence: docs/quant/2026-08-26_why_losing_deep_dive.md; docs/quant/2026-08-16_era4_readout_decision_table.md (2D).
- Falsifier: FEE-3 — one read-only TradeVolume call returning a different tier row.

#### TH-R-013 — overtrading / action bias (ours, deliberate but fee-underpriced)
- Footprint: 91% of the era-4 cohort are probes; median ticket $18 (below any fee floor); ~89% of all 68,982 audit dispositions are the probe machinery (SZ-047 32.3%, ML-070 30.3%, SZ-051 26.7%). Deliberate label-buying — but priced against understated fees, so tuition ran ~2x its book price.
- Capture: STAGED remedies: arm 2D (fewer, larger), CONC-1 (concurrency/uniqueness 0.301-0.399), ALGO-5 (stop widths + time-decay ladder).
- Evidence: audit census 2026-08-27 (this session); cohort_eval SELECTION-ERA section; probe-budget governor (main.py:3645-3790) as the existing cap.
- Falsifier: post-fee-truth, the probe lane clearing the TRUE-fee EV bar would retire this as a mistake (it becomes correctly-priced exploration).

#### TH-R-014 — fear-herding gate that fired backwards (ours)
- Footprint: SZ-021 crisis vetoes ANTI-SELECTIVE at significance — vetoed candidates won 0.509 [0.439, 0.580] vs baseline 0.265 [0.192, 0.354] (n=2,032, n_eff 189) — the bot herded with the fear it was built to exploit; the turbulence trigger fires ~7% on stationary noise by construction (TURB-1).
- Capture: REG-8 v2 dissolution designed (predicates 2->1, turbulence -> governor shrinkage, stress -> RiskProtocolStack); label-win caveat stands: cost overlay required before the probe tier opens.
- Evidence: docs/HANDOFF.md REG-6 update (gate_efficacy by_code); docs/quant/2026-08-22_REG8_crisis_predicate_algorithm.md; docs/quant/2026-08-22_turbulence_instrument_verification.md.
- Falsifier: a second independent melt-up with the vetoed cohort BELOW baseline net of costs.
