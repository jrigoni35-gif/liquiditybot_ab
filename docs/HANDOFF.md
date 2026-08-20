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

## AS OF 2026-08-20T21:48Z — verify before citing

| fact | value | re-derive with |
|---|---|---|
| era-4 accrual (THE gate) | 30 / 50 | `scripts/cohort_eval.py` or pc_status `era4` |
| deployed head on the PC | `318835c6`, outcome **dirty** | pc_status `deploy` |
| `main` head | `f669e7e9` | `git log origin/main -1` |
| equity / net all-time | $804.89 / +$4.89 | pc_status `status.equity` |
| corpus | 13,152 rows (343 live) | pc_status `status.ml` |
| mode | DRY_RUN, monitor L0 | pc_status |

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
| REG-6 | `crisis` is direction-blind; split `crisis_up`/`crisis_down`, 3 tiers | `docs/quant/2026-08-20_REG6_directional_crisis_prereg.md` |
| REG-7 | taxonomy vs measured occupancy: retire extinct `bull_volatile`, split `range`, rename `bear`→`drift_down` | `docs/quant/2026-08-20_REG7_taxonomy_occupancy_prereg.md` |
| SWEEP-0 | **CRITICAL** `derisk_actions` can force-close a HEDGE with zero hedge coordination (no cooldown arm, no FW-070) | `docs/quant/2026-08-20_codebase_sweep_docket.md` |
| SWEEP-1 | **CRITICAL** margin-health veto FAILS OPEN | same |
| SWEEP-3/5/8 | watchdog PNL-velocity input, CVaR buffer lookup, fast_cycle fetch loop | same |
| LS-1 | honest feature importance (MDA/clustered) — the 29/64 dead-feature list rests on an unverified ranking; **measure before pruning** | `docs/quant/2026-08-20_learning_symmetry_synthesis.md` |
| LS-2 | Bayesian uncertainty-aware sizing (spec-on-paper; the right answer to 343 live labels at uniqueness 0.152) | same |
| ATTR-1 | sentiment feed read 0.002-flat through the most newsworthy policy day of the quarter | `docs/quant/2026-08-20_event_record_surge_outlier.md` |
| ATTR-2 | no liquidation/OI awareness; context calendar knows only *scheduled* events | same |

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

- **PC deploy pipeline is blocked — two causes stacked** (observed
  2026-08-20, VS Code status bar `claude/claude-rc-f3heik*  3↓ 1↑`):
  1. *dirty tree* — the updater never fast-forwards across uncommitted
     changes (it will not clobber operator edits). Current outcome:
     `dirty`.
  2. *a local commit that never reached origin* (`1↑`). Once (1) is
     cleared this becomes the blocker: with a PC-side commit absent
     from `origin/main`, HEAD is not an ancestor of `origin/main` and
     `origin/main` is not an ancestor of HEAD, so the W1-7 guard
     reports **`diverged`** and correctly refuses forever — a
     fast-forward is impossible no matter how many batteries pass.

  Resolution order on the box: handle the uncommitted files (discard a
  regenerated artifact — prime suspect
  `docs/grafana/liquiditybot_learning.json` — or commit a real edit),
  then `git pull --rebase origin claude/claude-rc-f3heik` to replay the
  local commit on top of the 3 incoming ones, then push. The commit
  must also reach `main` (the pinned deploy channel) before the updater
  can move. There is deliberately no remote command for any of this.
  Trading is unaffected throughout.

---

## WATCH LIST (check these, don't assume)

- Crisis-window labels from 2026-08-20 resolving — they arm REG-6.
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
| Multi-agent "hive mind" | ships as a **lattice**, not a mesh: blind analysts → consensus diff → operator head → one learner. No evaluator ever feeds the learner. | `docs/quant/2026-08-19_referee_lattice.md` |
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
