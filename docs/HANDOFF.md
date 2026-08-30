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

Topical routing: `docs/INDEX.md` — issue-labeled router to the prepared
documents and instruments per issue (FEES, EXPLORATION, ERA4-GATE, …).
It labels and points, never substitutes; primary sources always win.

---

## ERA-6 BEGINS HERE — cut #9, the Tier-3 fee correction (2026-08-30)

**Cut #8 OVER-stated fees ~2x. Cut #9 corrects them.** Cut #8 booked
venue-true Kraken **Tier-1 40/80 bps** as "conservative", assuming a
zero-volume account. The operator's Kraken app (2026-08-29) proved the
account is **Tier 3 = 22/38 bps** on $17,482 30-day spot volume — the
account genuinely holds the volume discount. Cut #8's "COST_BOUND, can't
win at true fees" verdict was therefore built on a fee schedule ~2x too
high: **the-method #1 recurrence** (a struck fee schedule asserting itself
as truth; the booked median ~65bps and OM-080 n=0 were the unheeded
warnings). Decision record + re-derivation:
`docs/quant/2026-08-29_fee_tier_correction_adjudication.md`. Applied by
`scripts/fee_correction_stage.py --apply` under operator ARM 2026-08-30
**"fee correction only"**; `dry_run` STAYS true (paper).

`exec_era` is now **`9-16ec821e`** (cut #9 on the all-cuts counter). Config
moved: pricing+booking fees **40/80 → 22/38**, PT break-even floor **80 →
38**, label round-trip cost **1.2% → 0.6%**, `allow_sub_floor_fees` **→
true** (22/38 sits below the 40/80 `KRAKEN_SPOT_FLOOR` tripwire, which
stays put as the understated-fee guard; the account genuinely has a Tier-3
discount, which is exactly what that flag is for). Exploration `p_win` is
**LEFT at 0.85** (coherent at the lower cost — guard sweep confirms no
FATAL; reverting it is a separate exploration decision, out of this cut).

**What REVERSES from cut #8, so it is not misread:** the derived entry bar
recomputes **0.8335 → 0.6772** (b_net 0.1998 → 0.4766). **Conviction
RESUMES** — cut #8's "probe-dominated book, conviction entries effectively
stop" consequence is UNWOUND, because it was an artifact of the ~2x-too-high
fee. The give-back break-even buffer drops **166bps → 82bps** (2·38+6), back
below the pre-cut-8 86bps, so GB-1's "arms inside 166bps" premise no longer
holds (see docket). **ALGO-5 tail-control is EXCLUDED** from this cut (its
net-CI spans zero on fills alone — needs candle re-sim before it earns a
boundary).

**Era-6 accrual starts at zero from the cut #9 runner restart.** The
pre-registered gate machinery (`scripts/cohort_eval.py`, its bands, its
selection rule) is **untouched**. Cut-8 rows stay citable AS cut-8; nothing
under `9-16ec821e` may be pooled with them (or with era-4).

**THE CUT #9 INSTANT — STAMPED: 2026-08-30T15:32:36Z** (era-6 accrual zero
point = new runner process creation). Full chain, all measured same session:
`59bdcf87` merged+pushed to `origin/main`; the updater could NEVER restart
the runner for it (locally-born deploy reads "local is AHEAD … runner
untouched" — auto_update restarts only on outcome `updated`), so the restart
was operator-side via the control plane, the cut-#8 mechanism: `stop` sent
15:30:24Z (cid `1788103824.226997-67a8f6`), runner acked `control: stop ->
ok` 15:30:25Z, pc_supervisor `runner stale/absent -> relaunching` 15:32:36Z,
new runner worker **PID 7692** (venv shim 25488, parent = supervisor 14776)
created **15:32:36Z**, first RUNNING line 15:32:37Z. Corroborated by the new
process's own startup log: `runner starting: DRY … fees=22/38bps` and
`sizer payoff b=0.92 gross / 0.48 net of 0.60% rt cost (net p(win) breakeven
0.677) … p(win) bar=0.677 (derived, floor 0.55)` — the cut-9 constants,
bit-for-bit with the pre-derivation. Vault boundary row 9 stamped same
session. Rows written from this instant carry `9-16ec821e`.

---

## ~~ERA-5~~ **SUPERSEDED BY CUT #9** — cut #8, the fee-truth epoch (2026-08-28)

*Cut #8's 40/80 fee booking was ~2x too high (real tier is 22/38); the entry
bar 0.8335 and probe-dominated book below are cut #8's numbers, CORRECTED by
cut #9 above (bar 0.6772, conviction resumes). Kept for the record; do not
cite cut #8's fee/bar figures as current.*

**The era-4 cohort is CLOSED at its readout state** (COST_BOUND, n=54,
`docs/quant/2026-08-26_why_losing_deep_dive.md`). Boundary #5 — the
fee-truth cut — was **APPLIED** under the 2026-08-27 operator adjudication
("both: full bundle"), together with the control-arm merge. `exec_era` is
now **`8-ca55e2ba`** (cut #8 on the all-cuts counter, boundary #5 on the
fill-axis counter; both name this cut, see the vault's comparability
table). Config went to venue-true Kraken Tier-1 **40/80 bps** on both the
pricing and booking sides, the PT break-even floor to 80, the label
round-trip cost to **1.2%**, exploration `p_win` to **0.85**.

**Era-5 accrual starts at zero from the cut #8 runner restart.** Nothing
from era-4 may be pooled with it. The pre-registered gate machinery
(`scripts/cohort_eval.py`, its bands, its selection rule) was **not
touched** by the cut — deliberately.

**THE CUT #8 INSTANT — the number the boundary table needs.** Config
applied 2026-08-28T02:34:42Z; the era **begins at the deploy**, because a
running process keeps the fee constants it read at init. Stop issued via
`outputs/control/` at 03:11:58Z, runner reported STOPPED at 03:12:13Z, the
new runner process (PID 9108) started **2026-08-28T03:14:13Z** and was
first observed RUNNING at 03:14:51Z. **Cut #8 instant =
2026-08-28T03:14:13Z.** Corroborated by the new process's own startup log:
`runner starting: DRY … fees=40/80bps` and
`sizer payoff … net of 1.20% rt cost (net p(win) breakeven 0.833) …
p(win) bar=0.833 (derived, floor 0.55)`. *(The vault's
`wiki/synthesis/comparability-boundaries.md` row 8 was FILED same session
— prestige filing, deploy-instant 03:14:13Z; the OWED is discharged.
Control-arm rotation verified live 03:50:41Z: 18,658 rows zero-loss,
accrual at n=1. Grafana boards rebuilt to era-8 semantics in `034e6aa6`:
123→98 data panels, execution board retired, confound bargauge live.)*

**What to expect, so it is not misread as a fault:** the derived entry bar
is now **0.8335** (was 0.6902). Model confidences run 0.60–0.77, so
conviction entries effectively stop and the book becomes probe-dominated.
That is the strategy's honest position at true costs, not a malfunction —
it is consequence #1 of `docs/quant/2026-08-25_boundary5_adjudication.md`,
chosen with eyes open.

**Also live from this bundle:** the control-arm stratification tag
(`ml/history.py`, schema **94→95**, `CONTROL_ARM_FRACTION` 5%) — a
deterministic `sha256(asset|hour-bucket)` tag written at the single
`_append_row` choke point so the corpus grows its own contemporaneous
baseline. It is **written and never read**: no gate, sizer or order path
touches it (repo-wide grep guard,
`tests/test_control_arm_tag.py::test_control_arm_absent_from_decision_code`).
It does not bypass a veto and it changes no decision — "control arm at 5%"
means 5% of new rows are TAGGED, not 5% of trades are unguarded. The
`gate_efficacy_report` consumer that would turn those rows into a live
era-current baseline is **not built yet** (see CTRL-2 on the docket).

**The 94→95 rotation FIRED LIVE at 2026-08-28T03:50:41Z and is verified
clean — do not re-derive this.** The write-path rotation ran on the first
real label append (not at init: the 2026-07-11 discipline held), and
`corpus_sync` recovered within ~3s off the `.corpus_rotated` marker rather
than waiting out the hourly cadence. Row count double-derived three ways
and agreeing: 18,657 rows in `signal_history.bak_1787889040.recovered` + 1
new append = **18,658** in the live corpus = 18,658 in `status.json`.
**Zero rows lost.** Legacy rows carry `control_arm = ""` (UNKNOWN), never a
fabricated `0` — a blank means "written before the design existed", a `0`
means "actually drawn into the majority arm", and conflating them would
poison every comparison the arm exists to enable. Control-arm accrual is
live at **n=1**.

---

## AS OF 2026-08-22T15:00Z — verify before citing

**CURRENCY NOTE 2026-08-28:** the table below predates the era-4 READOUT
(WHY-1, n=54) and the 2026-08-27/28 session — re-derive every row. Freshest
session state: `docs/quant/2026-08-28_session_synthesis_T5.md` (T5) and the
vault source page `session-20260827-sdd-verification-and-era-confound`.

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

**Ranked head of this docket + the vault owed-register:**
`docs/quant/2026-08-30_longterm_improvement_map.md` — 40 items,
fence-labeled (NOW-SAFE / boundary batch / freeze / research), every one
provenance-cited, asset-universe answer included (recommended net
additions: ZERO — three measured caps). Unlisted register items stay
owed, not cancelled.

One boundary, one docket (the generational rule: batching amendments
means one execution-era reset instead of seven). Each item below alters
entry decisioning, geometry, fills, or model schema — **all
cohort-resetting, none shippable mid-era.**

**BOUNDARY PRINCIPLE (2026-08-22, measured):** the regime-invariant
edge is the **cost-aware rejection stack** — `SZ-030` net-Kelly f*<=0
and `SZ-046` held 6.0% / 16.0% at identical n and identical separation
straight through the 08-20 melt-up, while every admission-side number
moved with the tape (admitted 24.7% -> 35.8%). Boundary #5 PROTECTS
SZ-030 / SZ-023-derived-bar / SZ-046 and spends its budget on the
volatile side. Deletions of rules shown to measure the wrong thing rank
above additions. Authority:
`docs/quant/2026-08-22_boundary_around_the_invariant_edge.md`.
(numbering corrected 2026-08-27 fix-wave, I2: this section originally
said "#6" while `scripts/fee_reprice.py`'s docstring, commit `ca55e2ba`,
and the later WHY-1 entry above all name the SAME fee-truth cut
"boundary #5" - reconciled to the one the shipped code and the later
entry use.)

**LOOP ALIGNMENT (2026-08-22):** the operator->bot->market->analysis loop
is structurally sound and internally consistent, and mis-anchored at ONE
point: decision-side (`pretrade.*_fee_bps` -> SZ-030 / derived p-bar) and
booking-side (`order_manager.*_fee_bps`) read the SAME understated
constant, so the loop cannot self-detect it — only the independent
measurement route (`cost_truth_report`) could, and did. Protecting the
veto RULES does not mean freezing their COST ANCHOR; correcting it makes
them stricter, which is the safe direction. Boundary #5 order: FEE-1+FEE-2
bundled FIRST, then REG-8 v2, then SWEEP-0/1. Authority:
`docs/quant/2026-08-22_loop_alignment_audit.md`. (numbering corrected
2026-08-27, same reconciliation as above.)

| id | one line | authority |
|---|---|---|
| ALGO-5 | stop widths + time-decay ladder at ~30 uncensored paths | CLAUDE.md (pre-named) |
| ~~REG-6~~ **SUPERSEDED** | momentum-sign split — **discriminator FALSIFIED** (`crisis_down` longs 91.3% > `crisis_up` 78.4%); scope must be rewritten before adjudication | `docs/quant/2026-08-22_crisis_block_synthesis.md` |
| **REG-8 v2** | **dissolve** the crisis gate rather than replace it: DELETE the turbulence clause (predicates 2→1), ROUTE turbulence → existing governor `shrinkage` (uncertainty, not veto), ROUTE breadth+absolute stress → existing `RiskProtocolStack` (which already owns the hard stops). Zero new gates, zero new modules. Phase 0 SAFE now | `docs/quant/2026-08-22_REG8_crisis_predicate_algorithm.md` |
| **TURB-1** | the crisis trigger is DEFECTIVE AS DEPLOYED: fires ~7% by construction on stationary noise, measures co-movement atypicality not stress (a correlated crash never fires; one decoupling asset blacks out the book), broadcast as one scalar | `docs/quant/2026-08-22_turbulence_instrument_verification.md` |
| REG-7 | taxonomy vs measured occupancy: retire extinct `bull_volatile`, split `range`, rename `bear`→`drift_down` | `docs/quant/2026-08-20_REG7_taxonomy_occupancy_prereg.md` |
| SWEEP-0 | **CRITICAL** `derisk_actions` can force-close a HEDGE with zero hedge coordination (no cooldown arm, no FW-070) | `docs/quant/2026-08-20_codebase_sweep_docket.md` |
| SWEEP-1 | **CRITICAL** margin-health veto FAILS OPEN — **RE-CONFIRMED by injection 2026-08-29** (`risk/leverage.py:75`: a 0.0/failed `TradeBalance` read takes the `elif margin_level_pct > 0:` no-constraint path → full ladder to region_cap 10× authorized on the fetch failure the buffer exists to survive; reason list byte-identical to healthy). Happy-path-only test coverage let it persist. **xfail pin waiting** (`tests/test_fail_open_pins.py`). Fix is COHORT-RESETTING **and non-trivial**: in dry-run the fetch never runs so margin is always 0.0 — a naive 0.0→block caps ALL dry-run leverage; the real fix must separate dry-run-unknown from live-fetch-failed | same + stated-vs-real audit (session cdb03d59) |
| **SWEEP-1b** | **book-staleness sibling of SWEEP-1** (`core/watchdog.py:140`): a never-delivered book reads as fresh (age 0) instead of stale — a never-delivered book is not flagged in `stale_assets`. Symptom injection-confirmed; xfail pin waiting (`tests/test_fail_open_pins.py`). COHORT-RESETTING (staleness gates entry). Sibling live paths (main.py:4356/4779) use the fail-closed default | same |
| SWEEP-3/5/8 | watchdog PNL-velocity input, CVaR buffer lookup, fast_cycle fetch loop | same |
| LS-1 | honest feature importance (MDA/clustered) — the 29/64 dead-feature list rests on an unverified ranking; **measure before pruning** | `docs/quant/2026-08-20_learning_symmetry_synthesis.md` |
| LS-2 | Bayesian uncertainty-aware sizing (spec-on-paper; the right answer to 343 live labels at uniqueness 0.152) | same |
| ATTR-1 | sentiment feed read 0.002-flat through the most newsworthy policy day of the quarter | `docs/quant/2026-08-20_event_record_surge_outlier.md` |
| ATTR-2 | no liquidation/OI awareness; context calendar knows only *scheduled* events | same |

| **POWER-1** | **gate power analysis (MinTRL/PSR)**: NET needs 62 trades at configured fees (gate stops at 50) and **1,603 or INFINITE at true Kraken T1**. Two of three fee worlds are the pre-registered COST_BOUND arm. ~~GROSS edge already established~~ **— that half is WITHDRAWN by POWER-2** | `docs/quant/2026-08-22_gate_power_analysis_mintrl.md` |
| **POWER-2** | **resampling tranche 2 corrects POWER-1's headline.** Cohort n=33 carries **n_eff=9.92** (mean uniqueness 0.301); gross MinTRL is **9.94** — the gross edge is **precisely undetermined**, not established. Sequential dependence is unresolvable at this n (Politis-White block 1.3); **concurrency is the binding deflation** (SE x1.82). New: **cost tolerance** = 118 bps by point estimate, **43 bps** demanding distinguishability — below the 67.04 bps already booked. Also **walks back tranche 1's "independent confirmation" of the 66.76 bps cost**: both routes are anchored on the same configured 65 bps, so their agreement proves booking==config, not venue truth (`cost_truth_report` §1: OM-080 n_records=0) | `docs/quant/2026-08-22_walkforward_resampling_tranche2.md`, `scripts/walkforward_lab.py` |
| **TRIALS-1** *(SAFE)* | no ledger of how many strategy configurations were evaluated before the deployed one, and none of their SR dispersion. Without it DSR cannot be computed — only tabulated against hypotheses about N (`deflated_sharpe` falls back to var=SR^2). Cheap, purely additive | same |
| **WHY-1** | **era-4 dollar decomposition at readout (n=54)**: gross +$8.23, fees $6.87 booked / $13.59 true -> net +$1.36 / **-$5.36**. The split that matters: **conviction n=5 nets +1.46%/trip at TRUE fees; probes n=49 net -1.05%** - 91% of trades are tuition whose gross (+0.28%) sits below the round trip. Alt tail (DOGE/ARB/LTC/ADA/SUI) -$3.67 on 27 trips; BTC/ETH/LINK +$4.56 on 18. Median ticket **$18** - unbeatable fee floor. Verdict machinery worked: COST_BOUND shape + old gate STAND DOWN. Remedies all staged/docketed: boundary #5, ALGO-5, CONC-1, asset discipline | `docs/quant/2026-08-26_why_losing_deep_dive.md` |
| **CONC-1** *(cohort-resetting — do NOT act before readout)* | mean uniqueness 0.301 means the cohort buys information at ~1/3 of nominal rate. Raising it is a **sizing/concurrency** decision, inadmissible under the moratorium. Logged for boundary #6 | same |
| ~~**FEE-1**~~ **SHIPPED at cut #8 (2026-08-28)** | **configured fees are ~half the venue's real bottom tier** (Kraken T1 = 40/80, config = 25/40). Worth **−$4.04 of the accrued +$5.04** in the cohort window. Writing the true number produces a **config_guard FATAL** — the bot will not start, because exploration `p_win 0.700` falls below the net-Kelly breakeven `0.833` | `raw/quant/` cost-stack report; injection-verified |
| ~~**FEE-2**~~ **SHIPPED at cut #8 (2026-08-28)** | at true fees the entry bar moves **p 0.690 → 0.834** (+14.3 pts), so the probe lane that generates 85% of the cohort stops clearing by construction. Re-derived independently at apply time: b_net 0.4488 → 0.1998, breakeven 0.6902 → **0.8335** — the adjudication doc's number, confirmed by a second route | same |
| **QT-1** *(NEW 2026-08-28, needs its own adjudication — do NOT flip it in a passing commit)* | `scripts/quant_trials.py`'s harness-owned `TIER_CFG["est_fee_bps"]` is **40** and the deployed config is now **80** — the harness's declared "mirrors config.json's shipped block" property is DRIFTED by cut #8. Measured before deciding (200×1200, seed 7, runtime-proven config-independent: **0** config.json reads at import or during `run_trials`): as-is **G1–G5 all pass, byte-identical to pre-cut**; mirroring the cut (est_fee_bps 80) makes **G5 capture FAIL, 0.57 vs baseline 0.61**, and collapses G1's margin to 4.84% vs cap 4.91%. Same shape as the adjudicated #103 T6 enablement finding. Left UNCHANGED and NOT widened; the standing gates are honest about the harness world they were baselined in, and now demonstrably *not* about the deployed cost world. **UPDATE cut #9 (08-30):** deployed `est_fee_bps` corrected **80 → 38**, so the harness-40-vs-deployed drift narrowed from 40bps to **2bps** (near-coherent again); the G5-fails-at-80 result was an artifact of cut #8's ~2x-too-high fee. Harness still runtime-proven config-independent, so `test_quant_trials.py` stays green byte-identically — the harness's 40 is now an honest near-mirror of the deployed 38. Not re-measured at 38 (out of this cut); the 80-mirror finding is superseded, not re-run | `scripts/quant_trials.py:73-82`, this session's boundary-#5 report |
| **CTRL-2** *(SAFE, unblocked by the cut #8 merge)* | the control-arm tag is now WRITTEN but nothing consumes it. `gate_efficacy_report.py` needs its second, era-current baseline arm sourced from the tag's minority-arm rows — the only route out of the universal CONFOUNDED_BASELINE/PARTIAL_OVERLAP state. Two drifts the original TODO must absorb: the era-current arm must clear `ERA_OVERLAP_MAJORITY` by construction (not merely the floor), and any new `comparison` value must route through the two-vocabulary verdict function at `gate_efficacy_report.py:228-237` or it reintroduces the F1 inversion `0084c16d` killed. Needs accrual first (~usable n=30 in 0.85–1.6d of live rows) | sandbox report §5, `scripts/gate_efficacy_report.py` |
| **FEE-3** | OM-080 fee reconciliation has **never fired** — the account's actual tier row is unverified. One read-only `TradeVolume` call settles it; needs the first real credential on the box, so scope query-only and prefer post-readout | `execution/order_manager.py:767` |
| **THALES-R** *(SAFE)* | exploitable-human-mistake registry established: 15 entries (A: counterparty mistakes incl. the 3 dormant/absent footprints + funding/basis/OI blindness; B: our own measured biases as archetype ground truth), lifecycle contract with staleness-vs-boundary enforcement in the suite. Founding cautionary case: THALES itself — frozen at `shadow` since 07-29 while its th_* features shipped live ungated | `docs/thales/README.md`, `docs/thales/REGISTRY.md`, `tests/test_thales_registry.py` |
| **TRIALS-1 build** *(SAFE, shipped)* | archetype null battery + trial ledger v0.1: measured trial N feeds OF-5 under a ratchet (max(configured, measured); var stays legacy behind TRIPS_FLOOR=20); 8 entry-only rungs + deployed member on venue-coherent multi-seed tapes; activity floor + liveness pin close the confident-zero hole; run `python scripts/archetype_battery.py` then `python scripts/trial_ledger.py --report` | `docs/superpowers/specs/2026-08-27-archetype-null-battery-design.md`, `docs/superpowers/plans/2026-08-27-archetype-null-battery.md` |
**REG-6 UPDATE (2026-08-26, veto-quality instrument):** the pre-registered
readout condition now has its number. Pooled by code with effective-n
Wilson intervals (`gate_efficacy_report` `by_code`, on glass via
`liquiditybot_veto_cf_rate`): SZ-021 crisis vetoes are **ANTI-SELECTIVE at
significance** - vetoed candidates won 0.509 [0.439, 0.580] vs baseline
0.265 [0.192, 0.354], n=2,032 (n_eff 189). Disjoint intervals, the
instrument's own bar. CAVEAT the pre-registration requires: this is the
LABEL win rate, not net-of-costs - the "above baseline net of costs" arm
needs the cost overlay before it opens the probe tier, and one melt-up is
still one event. Also measured: SZ-030 net-Kelly EARNS ITS KEEP (0.060
[0.040, 0.089]); SZ-023 pooled across 87 variants sits AT baseline (0.278
[0.257, 0.299], n_eff 1,721) - the deployed bar neither saves nor costs.

**REG-6 CAVEAT (2026-08-27, era-confound):** the baseline these numbers
compare against is **frozen** - every blank-`disp` row is a
2026-07-20-migration backfill onto pre-existing rows, 0 rows since,
label_era mix 84.1% `legacy` / 15.9% `exit_sim`, **zero `triple_barrier*`
rows**. SZ-021's own population is **100% `triple_barrier_h432`** - zero
`label_era` overlap with the baseline it was scored against. Against a
**contemporaneous, same-window comparator** instead (everything else the
pipeline saw in SZ-021's own active window, `signal_ts` 2026-08-19T22:10 -
2026-08-25T01:35, n=1,772, rate 0.440 [0.369, 0.514]), SZ-021's interval
[0.439, 0.580] **overlaps** - "significant" does not survive. `SZ-023`
(quoted above as "sits AT baseline") is now separately measurable as the
**same defect**: pooled `label_era` overlap with baseline is 0.8% (below
the 5% floor `gate_efficacy_report.ERA_OVERLAP_FLOOR` now enforces), so
its "AT baseline" read is *also* confounded, not confirmed. **Direction
is unresolved, not refuted** - both readings above stay on the record;
neither the frozen-baseline "significant" verdict nor a clean "not
significant" verdict is established, because the comparator itself was
the wrong population. `gate_efficacy_report.py` now refuses to render
`anti_selective`/`selective` at all when a code's own rows share less
than 5% `label_era` overlap with the baseline sample (`ERA_OVERLAP_FLOOR`)
- the `by_code` **and** per-disposition **JSON** both carry a
`comparison: "CONFOUNDED_BASELINE"` field for SZ-021, SZ-023, and every
other disjoint-era code instead (**correction, 2026-08-27 fix-wave**:
this sentence previously claimed the Per-rule **markdown** table also
carried the literal `comparison` field - it does not and never has;
markdown renders the SAME verdict as prose in the flag column instead,
e.g. `(baseline CONFOUNDED - 0% label_era overlap, no significance claim
made)`); rates/CIs stay printed, unsuppressed. Vault:
`wiki/synthesis/open-contradictions-register.md` (2026-08-15 OPEN item,
2026-08-27 addition).

**REG-6 CAVEAT, fix-wave hardening (2026-08-27, ~22:48 UTC, live corpus
re-run):** the guard above used SET-membership overlap ("does the
baseline have any row of this era, at any count"), which had two holes:
a single contaminating baseline row bought a code full credit, and a
code that was 90%+ drawn from an era the baseline never touches could
still clear the flat 5% floor on its own small shared-era slice alone.
Replaced with WEIGHTED (histogram-intersection) overlap plus a 50%
majority line (`ERA_OVERLAP_MAJORITY`; `PARTIAL_OVERLAP` between the two
floors, `gate_efficacy_report.py`). Re-running against the live corpus
under the hardened guard surfaces a finding NOT anticipated when this
CAVEAT was first written: **every current `by_code` row, and the
admitted-vs-baseline headline itself, now reads CONFOUNDED_BASELINE or
PARTIAL_OVERLAP - none clears to a full "COMPARABLE" verdict**, including
`SZ-030` (previously the one clean "selective, earns its keep" read:
membership-overlap reported 0.685, weighted overlap is **0.159** -
`PARTIAL_OVERLAP`) and the admitted-set headline (weighted overlap
**0.159**, `PARTIAL_OVERLAP`). This is the guard working as intended, not
over-tuned: baseline's own composition (84.1% `legacy`, 15.9% `exit_sim`,
zero `triple_barrier*`) caps every code's MAXIMUM possible weighted
overlap near 0.159 (baseline's own `exit_sim` share) unless a code is
itself majority-`legacy` - which no currently active veto code is. The
frozen 2026-07-20 baseline cannot honestly vouch for ANY of today's
corpus, not just SZ-021/SZ-023; the report now says so instead of
printing partial confidence. **Not fixed here** (out of this fix-wave's
scope): the structural remedy is a live/contemporaneous baseline, the
same recommendation the original CAVEAT already named.

**REG-6's tier is decided by evidence already in flight**: the ~1,132
probe/candidate decisions logged inside the 2026-08-20 crisis window
resolve one barrier horizon later. Run `gate_efficacy` over
crisis-stamped candidates at readout — below baseline means the block
earned its keep (rename only); above baseline *net of costs* opens the
probe tier; a second independent melt-up is required before real
entries. One event never decides.

---

**DOCKET ADDITIONS 2026-08-28 (adjudicate with the boundary bundle):**
GB-1 `give_back.arm_gain_pct=0.6` arms inside the break-even buffer — bundle with ALGO-5. **UPDATE cut #9 (08-30):** the buffer is back to **82bps** (2·38+6), below the pre-cut-8 86bps; cut #8's 166bps widening is UNWOUND, so GB-1's "arms inside 166bps" premise no longer holds — re-assess the arm level against 82bps at the ALGO-5 boundary, not 166. CTRL-1 control-arm stratification tag + shadow gate-weight learner (sandbox `sandbox/control-arm-shadow-weights` @ `11eafb97`+`f0f3c370`; REBASE+RETEST required — base is stale): the only route to a live in-era veto comparator; schema 94→95, cohort-resetting, operator-only. CFG-B config BOUNDARY class from the 08-28 audit (fee stack, use_margin value) — in the audit report.

## STANDING FENCES (why your change may be refused)

- **Era-5 moratorium** (era-4's, re-fenced at cut #8) — anything touching entry decisioning, sizing,
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

- ~~PAGER-1~~ **RESOLVED same day (2026-08-30) — instrument artifact, the
  pager is fine.** The ">9h push gaps" came from parsing DATELESS pusher-log
  timestamps across midnight (the extraction agent had itself tagged its
  date inference [I]). Venue truth via the cloud's own series
  (`count_over_time(liquiditybot_status_age_sec[5m])`, 48h, 577 points,
  queried 2026-08-30 ~20:45Z): **zero gaps >15min** — telemetry was
  continuous through the entire alleged window, so the dead-man was
  CORRECTLY silent (state history confirms: no lb-telemetry-stale
  transitions in 3d; today's 2-min restart staleness sat under its
  3min+5m-for threshold by design). The-method recurrence shape: surprising
  number from the least-governed instrument, killed by a second route.
  Still unexplained (minor, real): one `Permission denied:
  outputs/status.json` (08-30 12:00:12 local) and 603 gc_log_offset.tmp
  file-contention incidents in gc_log_pusher.log.
- **ALERT-DRIFT (2026-08-30, real, SAFE to fix): the cloud alert plane and
  `docs/grafana/*.yaml` have diverged in BOTH directions.** Cloud holds
  exactly two rules ({lb-telemetry-stale, "manipulation suspicion high"},
  read via `/api/prometheus/grafana/api/v1/rules`); the repo's
  **Brier-degraded and drift-stuck YAMLs were never provisioned** (no such
  rules in cloud), and the manipulation rule exists ONLY in cloud (no YAML —
  unversioned, unreviewed). It also flaps Normal→Pending ~2x/day without
  ever firing (pending window doing its job, but it lives near its line).
  Fix = provision the two YAMLs + export the manip rule to a YAML, all
  measurement-plane.

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
| Numba on the sim kernels (08-30) | **REFUTED by microbenchmark — deliberate NO-FIX.** The "hot sim loops" premise measured cold: `simulate_exit_policy` 19µs/call typical, 352µs worst-case full 432-bar walk; `triple_barrier` 15µs/146µs — the whole 10k corpus relabels in ~0.2s and a 300k-sim candle re-sim is minutes single-core. A JIT twin would add a copied-formula drift surface against labeling's seven shared-discipline mirrors for ~zero wall-time gain. numba 0.67.0 IS installed + verified working on py3.14 (scripts-scope legal per test_dependency_hygiene) as contingency for a future genuinely-hot lane. Do not re-litigate without a NEW consumer whose measured wall-time is kernel-bound | this row; benchmark commands re-derivable from the numbers here |
| Pyth Network as a data source (08-30) | **REFUTED keyless — nothing wired.** Hermes metadata 200 (12/12 asset coverage) but real-time 401, benchmarks OHLC 404, point-in-time 401: every price sits behind a paid "Pyth Pro" token; the org's MCP README "no auth" rows don't match its backing REST. Clone parked at `..\pyth-plugin` (deletable). Re-probe before ever citing access | vault `wiki/sources/pyth-evaluation-2026-08-30.md` |
| Liquid glass REMOVED from Grafana; console born (08-30) | **EXECUTED** on operator directive ("delete the liquid glass 100% and rebuild it") after three same-day display incidents all traced to the CSS-injection mechanism (SPA style leak → black Alert History `b8a673ce`; `:has()` remount flicker → "glitching" `42560be0`; stripped-board bare skin → black alert-inputs `51b261af`). Boards now NATIVE Grafana dark, ZERO script-executing panels — one-way pin (`test_glass_removal_is_total` + `test_no_panel_executes_javascript`); generator carries a tombstone where `GLASS_RULES`/`_injector()` lived; `liquid-glass` tag dropped; Business Text plugin unused (operator may uninstall). The design language lives natively in **`scripts/glass_console.py` → `outputs/console.html`** (box-rendered presentation layer over the shared state files, SAFE class, 5 tests incl. injection pin; `--loop` documented in README Scripting inputs). Architecture: Grafana = pager + forensics; console = the glass | `README_glass.md` (retirement record), `.claude/skills/grafana-dashboard-architect/SKILL.md`, this row |
| Cut #9 — the Tier-3 fee correction (08-30) | **EXECUTED** under operator ARM "fee correction only", `dry_run` never touched. Cut #8 booked 40/80 (assumed Tier-1); the account is real **Tier 3 = 22/38** (operator Kraken screenshot), so cut #8 over-stated fees ~2x — the-method #1 recurrence. `fee_correction_stage.py --apply` owned every config write (drift-check green, backup `config.json.pre-cut9-*`, `validate()` on the applied file = 0 FATAL / 4 WARN); `exec_era` minted **`9-16ec821e`** in the same commit as the behavior change. Derived entry bar **0.8335 → 0.6772** (conviction resumes; cut #8's probe-dominated consequence UNWOUND). Full DoD green (4422 pytest / 220 smoke / 51 assurance / 3 overfit on live 9468-row corpus / ruff / bandit 0 / pyright 0). 5 suite re-baselines, each named + runtime-verified, none widened; the sub-floor tripwire re-baseline PROVES the mechanism still fires (flag-off arm) + pins the opt-out. Restart DISCHARGED same day: era-6 began **2026-08-30T15:32:36Z** (PID 7692, startup log `fees=22/38bps … bar=0.677` — see the era-6 section's stamped chain) | this row + `core/fill_ledger.py:71-87`, `docs/quant/2026-08-29_fee_tier_correction_adjudication.md`, `scripts/fee_correction_stage.py` |
| Boundary #5 / cut #8 — the fee-truth cut (08-28) | **EXECUTED** under operator adjudication. Stager owned every config write (drift-check green, backup written, `validate()` on the APPLIED file = 0 FATAL / 4 WARN, all four documented consequences); `exec_era` minted `8-ca55e2ba` in the SAME commit as the behavior change — no repeat of cut #7's late-bump debt. `dry_run` never touched. 7 suite pins re-baselined, each named in the report; none widened | this row + `core/fill_ledger.py:30-78`, `docs/quant/2026-08-25_boundary5_adjudication.md` |
| CTRL-1 control-arm merge (08-28) | **MERGED** (ff, `7b19181d`+`d64ad030`). Schema 95 live on the write path only (rotation in `_ensure_schema` ← `_append_row`, never `__init__` — the 2026-07-11 discipline); both conftest leak-registrations intact after the union rebase; 38 pins green in the MAIN tree | sandbox rebase report, `tests/test_control_arm_tag.py` |
| Brier spike 0.181→0.339 (08-19) | base-rate surge 0.24→0.42, guards held, recovered within one horizon. **No fix.** | `docs/quant/2026-08-19_brier_spike_diagnosis.md` |
| BTC/ETH +11%/+20% surge (08-20) | operator-adjudicated OUTLIER; bot measured it perfectly, cannot attribute it; no corpus surgery | `docs/quant/2026-08-20_event_record_surge_outlier.md` |
| C++ diode 16-vs-21 accrual disagreement | diode's strict ingest was stricter than the pre-registered reference; fills now mirror DictReader; **full agreement at 1e-9** | `diode/README.md` |
| Deploy channel | pinned to `main` via `system.deploy_branch`; per-box override is `LB_UPDATE_BRANCH`, never a config edit on the box | `scripts/auto_update.py` |
| "fees are 10x the gross edge" (2026-08-21) | **REFUTED by its own instrument.** The `+0.0733%` gross was equal-weighted; dollar-weighted is −0.0062%, median −0.0282%, day-clustered t≈1.0, and dropping 5 of 434 trades flips it. The ratio divided by a number whose CI contains zero. `cost_attribution.py` now prints all of that and refuses the framing | `scripts/cost_attribution.py` §1b |
| manip detector harming P&L | **REFUTED.** Deleting the gate entirely = ≈3.4 more entries at −$0.151 each ≈ **−$0.51**. 99.6% of vetoes are FLOW+MINA; BTC has **zero**. Real defect is observational: honest maker and layering attacker score byte-identically | `wiki/concepts/observational-equivalence` |
| Multi-agent "hive mind" | ships as a **lattice**, not a mesh: blind analysts → consensus diff → operator head → one learner. No evaluator ever feeds the learner. | `docs/quant/2026-08-19_referee_lattice.md` |
| Crisis block / "copious volatile data" (08-22) | Three-agent audit: instrument DEFECTIVE as deployed, block costs **+0.7pp vs a fair control**, n_eff **11.89** not 1,485. The 08-21 read of this data was too generous. | `docs/quant/2026-08-22_crisis_block_synthesis.md` |
| ADA hedge churn (08-07) | DONE and deployed at `cf454d5`. Unwinds never gated; re-hedge opens need warm correlation + cooldown. | `docs/quant/2026-08-07_ada_hedge_churn_HANDOFF.md` |
| DoD ruff line red on an untouched tree (08-22) | **The gate, not the code.** `extend-select` inherited ruff's defaults; ruff broadened them, so 0.16.3 reported **958 errors** across the shipped scope with zero changes — all of them rules this project never selected. Rule set is now pinned explicitly (`select = [E4,E7,E9,F,B,C901]`), tree verified green, pin tested. **Do not 'fix' those 958 findings; they were never in scope.** | `pyproject.toml`, `tests/test_lint_gate_pin.py` |
| 4 suite reds on an untouched tree, cloud box (08-22) | **Wrong OS, not wrong code.** 3 `test_battery_gate` pins exec `cmd.exe` (absent on Linux); `test_child_log_rotation`'s held-handle assertion encodes NT rename refusal. Reproduced on clean HEAD in a detached worktree before touching anything. cmd pins now `skipif(os.name != 'nt')` — **unskipped on Windows, where the battery gates**; the rotation test is platform-SPLIT, not skipped: never-raises is asserted everywhere, only the outcome branches | `tests/test_battery_gate.py`, `tests/test_child_log_rotation.py` |
| Archetype null battery + trial ledger BUILT (08-27) | **Shipped and merge-ready on `claude/remote-control-hds2hd`**: 18 commits, all SAFE-class, subagent-driven with per-task adversarial review (5 fix rounds — incl. the CLAUDE.md 7(a) netting trap caught in the ledger's own columns, a 9th QA-leak-class instance closed canonically, and the durable-append gate satisfied by routing). Final whole-branch review: MERGE-READY WITH FOLLOWUPS (ledger in the plan doc's addendum); full suite 4,092/4 skipped rc=0; OF-5 stays in its self-labeled "assumed N" world until the operator runs the battery on the PC (instructions in the addendum). DISCLOSURE: a fix subagent deleted this clone's leaked `outputs/trade_paths.csv` instead of quarantine-renaming — proven contamination-only by provenance (fresh container, whitelist-built outputs, guard-observed creation; the PC's real ALGO-5 ledger untouched), but the quarantine rule was not followed and that stands on the record | `docs/superpowers/plans/2026-08-27-archetype-null-battery.md` (addendum), `docs/superpowers/specs/2026-08-27-archetype-null-battery-design.md` |
| Session misread postmortem (08-27) | **Five failure shapes narrowed, fixes shipped**: digest spoofy line now names its NON-LIQUID denominator (`liq_lens` key added), realized/fees headline carries netting labels, ruff_on_edit made cross-platform, INDEX gained KNOWN TRAPS, CLAUDE.md mindset rule 7 (reading discipline). Hook WIRING into settings.json is classifier-blocked — operator snippet in the postmortem. NOTE: "boundary #5" (08-25/26 staged docs) and "boundary #6" (08-22 rows above) name the SAME next adjudication — reconcile numbering at readout | `docs/quant/2026-08-27_session_error_postmortem.md` |
| Digest false alarms: equity + chain headline (08-25) | **Fixed, display-honest.** `_pnl_section` read the whole equity.csv across 4 capital resets — the "$25,000 → $803 (range $99,208)" headline was a lens artifact, same family as the audit-count windowing. `equity_*` keys are now CURRENT-EPOCH (reset = >50% sample-to-sample jump; real resets moved 83–530%, worst transient 0.8%), `lifetime_*` added; SD-008 un-broke as a side effect (lifetime range kept it permanently dead post-reset). Headline chain field now prints a word per state (OK/SEAMS/TAMPER/TORN_TAIL/UNREADABLE) instead of `chain_ok=False` for benign seams — JSON keys untouched, checkin.py unaffected | `core/session_digest.py`, `tests/test_session_digest.py` |
| Veto-efficacy instrument era-confound (08-27/28) | **Fixed + hardened, then honestly silent.** Frozen baseline (84% legacy, 0 rows since 07-20) confounded every comparison; `a94b5751` refuses (CONFOUNDED_BASELINE), `62ab10c0` hardens (weighted overlap + majority floor + PARTIAL_OVERLAP + UNKNOWN excluded + headline guarded), `0084c16d` gives the admitted headline its own vocabulary (`selects_winners`/`adverse_selection`). Consequence: EVERY row now reads confounded/partial until a live comparator exists — the control-arm sandbox is the cure, awaiting adjudication | `scripts/gate_efficacy_report.py`, T5 doc |
| Main-inherited fresh-checkout suite reds (08-28) | 10th leak-class stamp registered, veto fixture rebound, boundary5 stager pinned; fresh-worktree acceptance green; fee-recon flake triple-checked unreproducible (serial scope) | `0257fd59`, vault `concepts/host-state-dependent-green` |
| config.json full audit (08-28) | 758 keys, 0 FATAL, guard injection-proven; SAFE batch applied (5 doc drifts, dead keys, 2 knob lifts runtime-proven byte-equal); BOUNDARY items docketed, not touched | `cd84c2aa`, audit report in session raw/ |
| Research corpus citation integrity (08-28) | 5 graded folders live-search verified: 19 defects + 19 overreach corrected in place, 0 hallucinated sources; conduct review PASS | `f17e28b5`, `docs/research/*` |
| C++ diode on this box (08-28) | **PERMANENTLY 8-skip under Smart App Control** — SAC blocks locally-built unsigned binaries; signed-compiler route exhausted (LLVM installed+parked, BuildTools installed). Diode verification belongs to the fresh-worktree CI leg or an operator SAC decision (irreversible) | T5 §5, ledger |
| `label_ret_pct` schema 93→94 (08-24, commit `8a9cc087`) | Candidate/live rows now carry a real-valued outcome instead of the destroyed `net_pnl_usd=0.0` for 5,923 rows; UNKNOWN (`""`) never a fabricated 0. **Correction (2026-08-27, I3):** the commit message overclaims its own verification — says "13 new pins" (re-derived by counting `+def test_` in the diff: **12**) and lists `tests/test_migrate_history.py` among updated pins (zero diff there; the diff only touches `tests/test_history_migration.py` — likely confusion between the two similarly-named files). History is pushed, not amended; this row is the correction of record so the false tally cannot be cited as settled. | `ml/history.py`, `tests/test_label_ret_persistence.py` |

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
