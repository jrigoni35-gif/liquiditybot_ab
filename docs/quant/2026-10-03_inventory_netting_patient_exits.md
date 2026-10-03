# Inventory netting (NET-1) + patient time exits (PATIENT-1) — decision-cohort fork (2026-10-03)

**Class: COHORT FORK under operator direction** (CLAUDE.md COHORT-FORKING:
entry decisioning + order lifecycle axes). Operator, verbatim: *"Let's take
the steps towards gaining our own edge considering the bot has to have
control and conscious of the inventory to improve upon the fees cutting into
profits."* Hard invariants 1–7 untouched: dry_run stays true, Kraken only,
entries stay limit orders, **exits are always allowed** (a risk-off exit
still pre-empts any resting maker exit), every disposition carries a
registered code. Two changes, batched into ONE fork (the moratorium's
"batch changes rather than trickle them").

## 1. Why — the fee bill, from the bot's own fills (pc-live `fills.csv`)

Since cut #12 (2026-09-08), 241 legs, $12,279 traded, **$28.98 fees**:

| leg | fills | fees | rate |
|---|---|---|---|
| entry, maker | 110 | $7.43 | 15 bps |
| entry, taker | 18 | $3.36 | 30 bps |
| **exit, taker** | **108** | **$17.77** | 30 bps |
| exit, maker | 5 | $0.42 | 15 bps |

Slippage vs arrival over the whole history is $3.01 on $114,920 (0.26 bps)
— latency is not the leak; fees are.

**Self-cancelling inventory.** Every trip is its own bracketed position, but
`InventoryManager.can_add` allowed opposite-side entries on the premise
"opposite-side adds reduce net inventory". They do not: they open a SECOND
trade paying a full round trip for exposure that cancels the first.
Measured since cut #12: **36 of 112 entries (32%) opened against an open
opposite position on the same asset, paying $9.07 of $27.81 trip fees.**
Pairs are mostly inside the 5m book (median 11.9 h after the first leg,
inside its 36 h horizon) — the signal flipped while the first bet still ran.
The research record (`2026-10-02_alpha_decay_mu0_tau.md`) finds no feature
with a market-relative edge, so holding both sides is fee burn by
construction.

## 2. What changed

| lever | code | config | behaviour |
|---|---|---|---|
| NET-1 | `execution/inventory.py` `can_add` | `inventory.refuse_opposite_side: true` | refuse an entry OPPOSITE any open non-hedge position on the same asset — **SZ-062** `SZ_OPPOSES_INVENTORY`. Covers every path that sizes through the inventory manager (5m sizer, long-book sizer). Code default false. |
| PATIENT-1 | `main.py` `_submit_exit(patient=)` | `risk.exit_escalation.maker_first_time_exits: true` | time-based exits — bracket vertical barrier `tb_time`, PT-060 time-stop scratch, non-urgent stale-inventory purge, ML-073 label realization — rest post-only at the touch on their FIRST attempt, then escalate into the unchanged marketable ladder. A patient exit never pre-empts; a risk-off exit pre-empts it. Stops, trails, floors and urgent hard-cap derisk stay marketable-first. Code default false. |

Both switches `false` restore the pre-fork behaviour exactly.

## 3. Expected effect (stated before any forward data; NOT a prediction to tune on)

- NET-1: the 32% of entries that opposed open inventory stop being placed;
  their fees ($9.07 of $27.81 since cut #12) are the upper bound of the
  saving. It also lowers entry count (fewer labels per day) — the price.
- PATIENT-1: time-based exits since cut #12 paid ~$2.9 at taker; where the
  maker attempt fills, the rate halves (30 → 15 bps) minus adverse selection
  after a maker fill (−5.5 bps at 60 min, `2026-10-02_feature_program.md`
  §5). Modest; it is the safe half of the exit-fee lever. Protective exits
  (tb_sl $7.12, tier trail $7.09) are deliberately NOT patient.

## 4. Fork record

- Decision fingerprint (same interpreter, Python 3.11): `6709bbf766b8` →
  **`5753862e53ca`** (cfg `6709bb70f73d` → `575386c7659b`; code
  `f766b86ab726` → `2e53ca3498f8`). The PC computes its own at boot.
- **Instrument finding:** `core.cohort.code_fingerprint` hashes
  `ast.dump`, whose output differs across Python versions — the cloud box
  (3.11) computes `6709bbf766b8` for the SAME commit the PC stamps
  `6709bbc2778d`. Verified PR #7 did not fork (pre-PR-#7 commit gives the
  same cloud value). A fork must be judged on ONE interpreter; the PC's
  boot stamp is the authority for its own fills.
- The running cohort `6709bbc2778d` (7/50 at 2026-10-03) closes at this
  restart; its trips keep their own read. Read points for the new cohort
  are the registered ones (n=50 lean, n=100 verdict, `scripts/era_readout.py`).
- Price of the fork: in-flight trips of `6709bbc2778d` keep their entry
  stamp (a trip belongs to its ENTRY leg's fingerprint), so nothing banked
  is lost; the new cohort's count starts at zero.

## 5. Conduct standard (`docs/law/conduct_standard.md`)

- **F1 (spoofs): no breach.** A patient exit is placed to fill; it is only
  removed by its order timeout or an audited risk-off pre-emption
  (OM_EXIT_PREEMPT), the same paths the shipped maker-first profit exit uses.
- **F3 (self-trades): risk REDUCED.** A resting maker exit can only be
  crossed by our own marketable order on the opposite side, which needs a
  long and a short open on the same asset - exactly what NET-1 stops
  creating (pre-existing pairs and hedges excepted). Kraken's default
  `stptype=cancel-newest` (VG-8) still applies.
- **OD-3 (order footprint): slightly UP for exits.** An unfilled patient
  attempt adds one order before the marketable ladder. Exits are ~1/6 of
  orders (era-9: 90 exits vs 561 entry orders), so the order-to-fill ratio
  moves little. No cap is introduced.

## 6. Known gap (stated, not widened)

NET-1 checks open POSITIONS. A grid-ladder rung resting before an opposite
position opened can still fill after it. Measure with this record's pair
count per fingerprint before widening the check to resting orders.

## 7. Re-derive

Pair count and fee split: the queries in this record's commit message
(`fills.csv`, positions by `position_id`, opposite-direction overlap on the
same asset). Tests: `tests/test_inventory_netting.py`,
`tests/test_patient_exits.py`.
