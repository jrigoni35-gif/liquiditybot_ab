# HANDOFF — living state of play

**The three-document read order.** `CLAUDE.md` = the LAW (what may never
change). `docs/ONBOARDING.md` = the MACHINE (how it works, where things
live). **This file = the STATE** (where we are right now, what is
pending, what was already settled). A session that reads only the first
two will re-derive facts it could have inherited — and, worse, may
re-litigate decisions that were already made with evidence.

**Freshness contract, borrowed from CLAUDE.md's own discipline** ("a
number written into law decays into a false claim"): every volatile
number below is stamped AS-OF and paired with the command that
re-derives it. **Re-derive before citing.** Prose decisions and
pointers are durable; numbers are not.

---

## 60-second orientation (run these, don't trust the table below)

```bash
# 1. the live bot, off-box (works from ANY clone)
python -c "import json,subprocess as sp; sp.run(['git','fetch','origin','paper-telemetry'],capture_output=True); \
d=json.loads(sp.run(['git','show','origin/paper-telemetry:control/pc_status.json'],capture_output=True,text=True).stdout); \
print(d['deploy'], d['era4'], d['status']['equity'], d['status']['runner_state'])"

# 2. the gate that everything waits on
python scripts/cohort_eval.py            # verdict gate + era segmentation

# 3. what the learning lenses say, all at once
python scripts/learning_panel.py         # -> outputs/learning_panel.{md,json}
```
In VS Code: **Tasks: Run Task** → `Remote console: PC status (via git)`,
`Bot: era-4 accrual (n/50)`, `Learning panel (all routes, concurrent)`.

---

## AS OF 2026-08-22T15:00Z — verify before citing

| fact | value | re-derive with |
|---|---|---|
| era-4 accrual (THE gate) | 33 / 50 — **STALLED 48h+** | `scripts/cohort_eval.py` or pc_status `era4` |
| deployed head on the PC | `7a63ad1c`, outcome **current** (dirty-block cleared 08-22) | pc_status `deploy` |
| equity / net all-time | $805.04 / +$5.04 (high-water) | pc_status `status.equity` |
| corpus | 14,465 rows (346 live — live labels flat: entries blocked) | pc_status `status.ml` |
| calibration gap | 0.0138 (best on record) | pc_status `status.ml.retrain_calib_gap` |
| regime | **all 12 assets `crisis`** on the shared turbulence scalar | pc_status `status.regimes` |

**Accrual pace ≈ 3–7 closes/day → readout roughly late August.** That
date is an estimate, not a commitment; the gate fires on n, never on a
calendar.

---

## THE GATE — what every open decision is waiting for

The era-4 honest-fill cohort accrues to **n=50** closed entry-opened
trips, then reads out one of three pre-registered verdicts:
**NO_GROSS_EDGE / COST_BOUND / CONTINUE**. The readout *names which
decision has become decidable* — it never decides. Authority:
`docs/quant/2026-08-16_era4_readout_decision_table.md` (signed, and
re-ratified after adversarial provenance review).

Until it fires: **do not read the accruing numbers as a trend, and do
not retune on them.** This is the single most-violated instinct in this
project; it is also the reason the project can ever answer anything.

---

## OPEN DOCKET — adjudicate together at the boundary

One boundary, one docket (the generational rule: batching amendments
means one execution-era reset instead of seven). Each item below alters
entry decisioning, geometry, fills, or model schema — **all
cohort-resetting, none shippable mid-era.**

| id | one line | authority |
|---|---|---|
| ALGO-5 | stop widths + time-decay ladder at ~30 uncensored paths | CLAUDE.md (pre-named) |
| ~~REG-6~~ **SUPERSEDED** | momentum-sign split — **discriminator FALSIFIED** (`crisis_down` longs 91.3% > `crisis_up` 78.4%); scope must be rewritten before adjudication | `docs/quant/2026-08-22_crisis_block_synthesis.md` |
| **REG-8** | the crisis predicate rebuilt: absolute-stress crash gate + turbulence demoted to a size modifier + per-asset extremes stay per-asset. Phase 0 (observability + SHADOW evaluator) is SAFE NOW; Phase 1 is boundary | `docs/quant/2026-08-22_REG8_crisis_predicate_algorithm.md` |
| **TURB-1** | the crisis trigger is DEFECTIVE AS DEPLOYED: fires ~7% by construction on stationary noise, measures co-movement atypicality not stress (a correlated crash never fires; one decoupling asset blacks out the book), broadcast as one scalar | `docs/quant/2026-08-22_turbulence_instrument_verification.md` |
| REG-7 | taxonomy vs measured occupancy: retire extinct `bull_volatile`, split `range`, rename `bear`→`drift_down` | `docs/quant/2026-08-20_REG7_taxonomy_occupancy_prereg.md` |
| SWEEP-0 | **CRITICAL** `derisk_actions` can force-close a HEDGE with zero hedge coordination (no cooldown arm, no FW-070) | `docs/quant/2026-08-20_codebase_sweep_docket.md` |
| SWEEP-1 | **CRITICAL** margin-health veto FAILS OPEN | same |
| SWEEP-3/5/8 | watchdog PNL-velocity input, CVaR buffer lookup, fast_cycle fetch loop | same |
| LS-1 | honest feature importance (MDA/clustered) — the 29/64 dead-feature list rests on an unverified ranking; **measure before pruning** | `docs/quant/2026-08-20_learning_symmetry_synthesis.md` |
| LS-2 | Bayesian uncertainty-aware sizing (spec-on-paper; the right answer to 343 live labels at uniqueness 0.152) | same |
| ATTR-1 | sentiment feed read 0.002-flat through the most newsworthy policy day of the quarter | `docs/quant/2026-08-20_event_record_surge_outlier.md` |
| ATTR-2 | no liquidation/OI awareness; context calendar knows only *scheduled* events | same |

| **FEE-1** | **configured fees are ~half the venue's real bottom tier** (Kraken T1 = 40/80, config = 25/40). Worth **−$4.04 of the accrued +$5.04** in the cohort window. Writing the true number produces a **config_guard FATAL** — the bot will not start, because exploration `p_win 0.700` falls below the net-Kelly breakeven `0.833` | `raw/quant/` cost-stack report; injection-verified |
| **FEE-2** | at true fees the entry bar moves **p 0.690 → 0.834** (+14.3 pts), so the probe lane that generates 85% of the cohort stops clearing by construction | same |
| **FEE-3** | OM-080 fee reconciliation has **never fired** — the account's actual tier row is unverified. One read-only `TradeVolume` call settles it; needs the first real credential on the box, so scope query-only and prefer post-readout | `execution/order_manager.py:767` |
**REG-6's tier is decided by evidence already in flight**: the ~1,132
probe/candidate decisions logged inside the 2026-08-20 crisis window
resolve one barrier horizon later. Run `gate_efficacy` over
crisis-stamped candidates at readout — below baseline means the block
earned its keep (rename only); above baseline *net of costs* opens the
probe tier; a second independent melt-up is required before real
entries. One event never decides.

---

## STANDING FENCES (why your change may be refused)

- **Era-4 moratorium** — anything touching entry decisioning, sizing,
  stop/exit geometry, the fill simulator, fee booking, or order
  lifecycle mints a new execution era and restarts accrual. Requires
  operator adjudication. SAFE: measurement, reports, dashboards, tests,
  telemetry, wiki, and bug fixes that don't change which orders are
  placed or how they fill.
- **Model freeze** (2026-08-10 adjudication) — no new families,
  features, or meta-labeling. The retrain loop itself keeps running by
  design.
- **Hard invariants** — dry_run default true, `arm_live` never remote,
  Kraken sole venue, withdrawals impossible, exits always allowed.
  These are not negotiable at any boundary.

---

## IN FLIGHT / BLOCKED

- **Deploy pipeline: UNBLOCKED 2026-08-21.** The blocker was never a stray
  artifact — it was 15 files of finished sweep-tail work staged and never
  committed. Verified (3881 pass, clean cloud review) and landed as
  `eeff0f7a`; the updater now follows `main` and reads `current`.
- **Cost-stack diagnosis: COMPLETE, fixes PARTIAL.** SAFE items shipped
  (see below). Every fee-constant item is BOUNDARY and waits for readout.

## WATCH LIST (check these, don't assume)

- **Whether `turbulence_pct` decays below 0.95** — the book reopens on its own if it does. Pinned at the series ceiling 0.984 for 23-30h as of 08-22; historical N=1, no base rate to forecast it.
- SAFE-NOW observability backlog from TURB-1 (turbulence absent from `status.json` entirely; silent stale-hold; no config_guard coverage) — see the synthesis doc's disposition section.
- Champion Brier / calibration gap after each retrain: a base-rate
  regime shift moves both honestly (see the settled entry below).
  Escalate only if degradation persists a full barrier horizon *after*
  the base rate returns to ~0.2.
- Exploration probe rate (~56/hr in volatile tape) — loud by design,
  budget-capped; it is the corpus flywheel, not a fault.
- Drift share vs the 30% retrain vote line.

---

## RECENTLY SETTLED — do not re-litigate, do not re-implement

| what | verdict | record |
|---|---|---|
| Brier spike 0.181→0.339 (08-19) | base-rate surge 0.24→0.42, guards held, recovered within one horizon. **No fix.** | `docs/quant/2026-08-19_brier_spike_diagnosis.md` |
| BTC/ETH +11%/+20% surge (08-20) | operator-adjudicated OUTLIER; bot measured it perfectly, cannot attribute it; no corpus surgery | `docs/quant/2026-08-20_event_record_surge_outlier.md` |
| C++ diode 16-vs-21 accrual disagreement | diode's strict ingest was stricter than the pre-registered reference; fills now mirror DictReader; **full agreement at 1e-9** | `diode/README.md` |
| Deploy channel | pinned to `main` via `system.deploy_branch`; per-box override is `LB_UPDATE_BRANCH`, never a config edit on the box | `scripts/auto_update.py` |
| "fees are 10x the gross edge" (2026-08-21) | **REFUTED by its own instrument.** The `+0.0733%` gross was equal-weighted; dollar-weighted is −0.0062%, median −0.0282%, day-clustered t≈1.0, and dropping 5 of 434 trades flips it. The ratio divided by a number whose CI contains zero. `cost_attribution.py` now prints all of that and refuses the framing | `scripts/cost_attribution.py` §1b |
| manip detector harming P&L | **REFUTED.** Deleting the gate entirely = ≈3.4 more entries at −$0.151 each ≈ **−$0.51**. 99.6% of vetoes are FLOW+MINA; BTC has **zero**. Real defect is observational: honest maker and layering attacker score byte-identically | `wiki/concepts/observational-equivalence` |
| Multi-agent "hive mind" | ships as a **lattice**, not a mesh: blind analysts → consensus diff → operator head → one learner. No evaluator ever feeds the learner. | `docs/quant/2026-08-19_referee_lattice.md` |
| Crisis block / "copious volatile data" (08-22) | Three-agent audit: instrument DEFECTIVE as deployed, block costs **+0.7pp vs a fair control**, n_eff **11.89** not 1,485. The 08-21 read of this data was too generous. | `docs/quant/2026-08-22_crisis_block_synthesis.md` |
| ADA hedge churn (08-07) | DONE and deployed at `cf454d5`. Unwinds never gated; re-hedge opens need warm correlation + cooldown. | `docs/quant/2026-08-07_ada_hedge_churn_HANDOFF.md` |

---

## UPDATING THIS FILE (the contract)

Update it **at the end of any session that changes state** — not with
everything you did (git log holds that), but with what the *next*
session must not have to rediscover:

1. Re-stamp the AS-OF table (or delete rows you did not verify — a
   stale number is worse than an absent one).
2. Move anything you settled into **RECENTLY SETTLED** with its record
   path, so it is never re-litigated.
3. Add anything you registered to the **OPEN DOCKET** with its
   authority doc — a decision with no pointer is a decision that will
   be made again, differently.
4. Keep entries one line. This file is a router, not an archive; the
   dated docs in `docs/quant/` are the archive.
5. When the era-4 gate reads out, this file's docket becomes the
   agenda for that adjudication — and then most of it gets cleared.
