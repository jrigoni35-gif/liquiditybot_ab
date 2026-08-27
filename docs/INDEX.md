# INDEX — the affordable reading layer (issue-labeled router)

Purpose: make any session's first read CHEAP. Each issue label below
routes to the prepared documents, the instruments that re-derive its
numbers, and the docket/registry entry that owns its future. Built
2026-08-27 at operator direction.

**Contract (binding, enforced by `tests/test_issue_index.py`):**

1. **This router never substitutes for primary sources.** It labels
   and points; it does not summarize numbers (numbers decay — the
   HANDOFF freshness rule). If a row here disagrees with the primary
   source, the primary source wins and the row is a bug.
2. **Nothing is locked out.** Reading beyond this index is always
   correct; the read order stays CLAUDE.md (law) → docs/HANDOFF.md
   (state) → this file (topical routing) → primary sources.
3. **An issue never folds.** A row leaves this index only by pointing
   to its settlement record (HANDOFF "RECENTLY SETTLED" or a registry
   REJECTED entry with evidence). Deleting a row without a settlement
   pointer is the forbidden move.
4. Every path referenced here must exist — the test enforces it, so a
   renamed or deleted document breaks the suite instead of silently
   orphaning its issue.

| label | the issue in one line | prepared documents | re-derive with | owned by |
|---|---|---|---|---|
| FEES | config booked half the true tier; fees dominate gross | `docs/quant/2026-08-26_why_losing_deep_dive.md`, `docs/quant/2026-08-27_exploration_economics.md` | `scripts/cost_attribution.py`, `scripts/cost_truth_report.py`, `scripts/fee_reprice.py` | HANDOFF FEE-1/2/3; registry TH-R-012 |
| EXPLORATION | 91% of trips are probes; tuition mispriced at booked fees; label unit economics | `docs/quant/2026-08-27_exploration_economics.md`, `docs/quant/2026-08-26_why_losing_deep_dive.md` | `scripts/cohort_eval.py` (SELECTION-ERA), audit census (`core/codes.py` SZ-047/ML-070/SZ-051) | registry TH-R-013; boundary arm 2D |
| ERA4-GATE | the pre-registered verdict gate; accrual, homogeneity, readout arms | `docs/quant/2026-08-16_era4_readout_decision_table.md`, `docs/quant/2026-08-22_gate_power_analysis_mintrl.md`, `docs/quant/2026-08-22_walkforward_resampling_tranche2.md` | `scripts/cohort_eval.py`, `scripts/walkforward_lab.py` | CLAUDE.md moratorium; HANDOFF THE GATE |
| SIZING-CAP | Kelly stack, protocol stack, no cross-strategy allocator; overlay refuted at this n | `docs/quant/2026-08-27_thales_ladder_analysis.md` (§4-5) | `risk/position_sizer.py`, `risk/protocols.py`, `core/config_guard.py` | HANDOFF CONC-1/ALGO-5/LS-2 |
| REGIME-CRISIS | turbulence trigger defective as deployed; crisis gate anti-selective | `docs/quant/2026-08-22_crisis_block_synthesis.md`, `docs/quant/2026-08-22_turbulence_instrument_verification.md`, `docs/quant/2026-08-22_REG8_crisis_predicate_algorithm.md` | `scripts/gate_efficacy_report.py` | HANDOFF REG-6/REG-8/TURB-1; registry TH-R-014 |
| MANIP-SPOOFY | liquidity classifier and manip gate: two stacks, one label; observational equivalence; SD-003 denominator | `docs/quant/2026-07-29_thales_unit_audit.md`, `docs/research/2026-07-26_criminology_manipulation_lens.md` | `regime/liquidity_regime.py`, `core/session_digest.py` (spoofy_frac lens) | HANDOFF watch list; vault observational-equivalence |
| THALES | counterparty-footprint capture: detector bank state, registry, ladder proposal | `docs/thales/README.md`, `docs/thales/REGISTRY.md`, `docs/THALES.md`, `docs/THALES_FRAMEWORKS.md`, `docs/quant/2026-08-27_thales_ladder_analysis.md` | `scripts/thales_report.py`, `strategies/thales.py` | registry TH-R-001..010 |
| ML-CALIB | retrain loop, champion selection, calibration gap lenses, model freeze scope | `docs/quant/2026-08-14_edge_training_design.md`, `docs/quant/2026-08-19_referee_lattice.md` | `ml/walkforward.py`, `ml/overfit.py`, retrain ledger (`ml/retrain_log.py`) | HANDOFF model freeze; TRIALS-1 |
| DATA-BLIND | no OI/liquidations, sentiment read flat, basis never differenced, no trade prints | `docs/quant/2026-08-20_event_record_surge_outlier.md`, `docs/quant/2026-08-27_thales_ladder_analysis.md` (§3) | `data/okx_feed.py`, `sentiment/scanner.py` | HANDOFF ATTR-1/2; registry TH-R-007..010 |
| EXITS-GEOM | stop channel composition, giveback ratchet, geometry sized to false fee world | `docs/quant/2026-08-26_why_losing_deep_dive.md` (rows 6b/6c/6d) | `scripts/geometry_search.py`, `scripts/breakeven_test.py`, `risk/profit_tiers.py` | ALGO-5 (pre-named, cohort-resetting) |
| INSTRUMENT-TRUST | the instrument is the first suspect; every referee is an instrument too | CLAUDE.md THE MINDSET, `docs/quant/2026-08-22_loop_alignment_audit.md`, `docs/quant/2026-08-27_session_error_postmortem.md` | second-route derivation, injection tests | standing law |
| OPS-CONTROL | one-bot mode, remote control plane, deploy channel, telemetry | `docs/ONBOARDING.md`, `docs/PC_ALWAYS_ON.md` | `scripts/remote_control.py`, `scripts/pc_supervisor.py`, `scripts/auto_update.py` | CLAUDE.md coordination rules |

## KNOWN TRAPS — misreads that already happened, labeled so they cannot recur

Each trap below was walked into by a session and caught by adversarial
review; the instrument or label has been fixed where possible, and the
trap stays listed regardless (a fixed instrument still has old records).

- **FEES**: `realized_pnl_total` is net of the CLOSING fee leg only,
  while `fees_paid_total` carries both legs — never ratio the two raw
  lines (misread 2026-08-27; digest labels now carry the netting).
- **MANIP-SPOOFY**: the digest's `spoofy_frac` denominator is
  NON-LIQUID cycles only — liquid cycles are never logged
  (`regime/liquidity_regime.py:358`). 54% there is compatible with 1/12
  assets spoofy in the same status snapshot; cross-check
  `status.regimes` for absolute prevalence (misread 2026-08-27; now
  labeled, `liq_lens` key added).
- **ML-CALIB**: `family_calib_gap` exists only after the 07-26 schema
  change and the ledger spans a corpus reset — compare within one
  family AND one corpus epoch; a cross-family/cross-reset "best on
  record" is void (misread 2026-08-27).
- **ERA4-GATE**: pc_status `era4.signed_continue_n = 100` binds arms
  1D/3A ONLY. The fired arm's action comes from the signed decision
  table (COST_BOUND -> 2D), never from the status field (misread
  2026-08-27).
- **OPS-CONTROL**: a test run piped through `tail`/`head`/`grep`
  reports the FILTER's exit code, and a "green" whose runtime is
  implausible for its corpus (5s for a 4,000-test suite) is unread.
  Redirect to a file, echo the real `$?` (incidents 2026-08-24 x2,
  recurrence 2026-08-27; `pytest_pipe_guard.py` exists — wiring needs
  operator approval, see the postmortem).
- **General**: severity and confidence are different rollups (bandit
  prints both; "High: 2" under confidence is not two high-severity
  findings — misread 2026-08-27). And any deflation (effective n,
  concurrency) applies to claims you like at the same rate as claims
  you doubt.

Maintenance: add a row when a new issue earns a prepared document; move
a row out only with its settlement pointer (contract §3). Keep rows to
one line each — affordability is the product. Traps are append-mostly:
one leaves only when its old records can no longer be read.
