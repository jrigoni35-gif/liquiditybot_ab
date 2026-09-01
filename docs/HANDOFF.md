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

## AS OF 2026-08-30T22:08Z — verify before citing

**CURRENCY NOTE 2026-08-30 (general update pass, era-6 in progress):**
re-derived directly this session (repo `9fdbc389` == `origin/main`, clean;
live box: PID 7692, RUNNING). The pre-registered era-4 trigger (WHY-1,
n=54 COST_BOUND readout, `docs/quant/2026-08-26_why_losing_deep_dive.md`)
is CLOSED and its own counter keeps summing regardless — read the row
below as that counter's current value, not a new decision point.

| fact | value | re-derive with |
|---|---|---|
| era-4 trigger's own counter (closed gate, informational only) | 72/50, mixed `exec_era` {7-e7d5ca1a, 8-ca55e2ba, 9-16ec821e} in one cohort (COHORT HOMOGENEITY: MIXED). **This counter is NOT era-scoped and never was**: `era4_trips` selects on FIVE predicates (`cohort_eval.py:301,303,305,313,320-322`) and `exec_era` appears in NONE of them — every `exec_era` reference in the file (L273-287, L327, L447-448, L477, L773-781) is report-only classification, as L270-272 says in as many words. So `72/50 COST-BOUND` pools cuts #7/#8/#9 by construction; it is not a cut-#9 readout | `scripts/cohort_eval.py` |
| era-6 (`exec_era 9-16ec821e`) accrual, gate-join population | **4 closed entry-opened trips** (upper bound 7 if trips merely TOUCHING era-6 are counted — 3 of those entered under cut #8 at the superseded 40/80 booking and only EXITED under cut #9, so the moratorium's "nothing pooled across the fee correction" excludes them). Supersedes the earlier 11-row fill-leg proxy: 11 legs = 7 position_ids = 4 wholly-era-6 trips. Two independent routes agreed exactly (gate's own `era4_trips()` segmented by its own `eras` field; and a from-predicates re-implementation), on a frozen byte-identical snapshot of `fills.csv` (md5 `f972dd36f569369a9dfb78cc06727578`, file mtime 21:10:20Z, read 22:47Z). Verified by a 10-case injection battery incl. 2 positive controls — the counter provably MOVES, so "4" is a measurement, not a dead scan. Era boundary is clean: 0 era-9 legs before the 15:32:36Z restart, 0 era-8 legs after. **Count only — no gross/net/win-rate on an accruing era.** **DECAY NOTE (2026-08-30T23:10Z, re-confirmed 23:17:45Z): the leg/pid chain above is correctly snapshot-stamped but is ALREADY STALE AS LITERAL TEXT — RE-DERIVE, NEVER CITE.** `fills.csv` has since moved to md5 `ef92ef6cd3295b69dff0fcefd39b60fb`, **1,189 rows**, **12** era-9 legs across **8** pids (was 11/7 at the 22:47Z snapshot; md5 + counts double-derived at 23:10Z and again at 23:17:45Z, identical). **The trip count is STILL 4** — the new leg is an unclosed ENTRY, so it joins no closed trip. The "11 → 7 → 4" chain is a historical measurement of the 22:47Z snapshot, not a current reading; only the re-derivation command below yields a citable number | freeze a copy of `outputs/fills.csv`, then `era4_trips(<snap>)` filtered to `t["eras"] == ["9-16ec821e"]` |
| deployed head | `9fdbc389`, branch `main` == `origin/main`, clean | `git log -1`, `git status` |
| runner | PID 7692, `runner_state` RUNNING, `mode` DRY_RUN | `outputs/status.json` (mtime 22:07:54Z) |
| equity | $797.35 | `outputs/status.json.equity` (read 22:07:56Z) |
| calibration gap | `{'logistic': 0.06012}` | `outputs/status.json.ml.retrain_calib_gap` (read 22:07:56Z) |
| drift share | 0.2333 (below the 0.30 retrain-vote line) | `outputs/status.json.ml.drift_share` (read 22:07:56Z) |
| regime | **0/12 assets in `crisis`** (range/bull_quiet/bear/bull_volatile) — book is OPEN, not the 08-22 all-crisis state | `outputs/status.json.regimes` (read 22:07:56Z) |
| turbulence_pct | **16.0 (fraction 0.16)**, fresh (`computed_at` 21:32:49Z, `stale`=False, `hold_reason`="", `sample_count`=250) — see RECENTLY SETTLED, this closes the old watch-list question | `outputs/status.json.correlation` |
| overfit corpus | live history, **10,359 rows** (well above the 640-row synthetic-substitution floor — this was a REAL-market run, not the planted-signal benchmark) | `scripts/overfit_check.py` output tail |
| assurance corpus | training-corpus timestamp check, **20,728 rows** (a different population/filter than the overfit corpus above — do not conflate the two counts) | `scripts/assurance_check.py` §11 |

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
| **MLSEC-1** | **CRITICAL — the ML-011 model-tamper gate is disabled by DELETING its own evidence.** `ml/meta_model.py:83` rejects only on `v.get("ok") is False`; `ml/registry.py:284-287` returns `ok=None` ("unknown provenance") whenever no pedigree is found, and `registry.py:221-222` returns `ok=None` when the ledger is unreadable — so `verify()` never returns False once `registry.jsonl` is gone. **Injection-confirmed 2026-08-30** (control passes: ledger intact → `ok=False`, ML-011 fires, `p_win` falls back to the prior **0.5600**; ledger deleted → `ok=None`, the swapped artifact **LOADS**, `p_win`=**0.9500**, the hard-clip ceiling, on every entry). Worse, an EMPTY ledger makes `verify_chain()` report **`ok=True, "chain intact"`** — 0 rows passes vacuously, so the chain verifier cannot tell "untampered" from "no evidence". The attacker needs no extra privilege: `registry.jsonl` lives in the same `outputs/models/` directory as the artifact being swapped. **This is the fifth instance of the durable rule "a gate's release condition must never depend on the thing it blocks."** **RE-ROOTED 2026-08-30 (adversarial re-verify — the diagnosis above mis-located the root cause and the real defect is WORSE):** the deleted/empty-ledger paths are *symptoms*; the root cause is that **`ml/registry.py` `_record_hash` is an UNKEYED public sha256** — anyone who can write the file can also write a VALID chain over forged content. Measured **forged-chained-row** case: append ONE well-formed `registered` row whose `sha256` is the SWAPPED artifact and whose `prev` is the last row's `h`, and `verify_chain()` returns `{'ok': True, 'rows': 3, 'chained': 3, 'reason': 'chain intact'}` **and** `verify()` returns `{'ok': True, …}` — the swapped artifact is not merely un-rejected, it is **POSITIVELY ATTESTED**. Consequence for the fix: **"reject on `ok is not True`" DOES NOT CLOSE THIS** — that only covers the `ok=None` path; a forged row returns `ok=True` and sails through any such check. A keyed MAC (or an out-of-tree signer) is the class of fix; nothing weaker is a fix. **Threat model on which the [HIGH] rests, stated so it is neither over- nor under-fixed:** the severity is against a **PARTIAL-WRITE** attacker — one who can write `outputs/models/` (a corrupted/hostile artifact drop, a stray process, a botched sync) but does not own the repo. Against an attacker who already owns the repo NO gate here helps, because the ledger lives in the same directory as the artifact it attests and the verifier itself is editable. COHORT-RESETTING (a naive `is not True` refuses every unregistered/hand-trained model). Live state healthy as of 2026-08-30T22:52:02Z (chain ok, 177 rows, deployed artifact `1ee3ae68c0df` verifies ok=True) | GAP-4 read-only adversarial audit of `execution/`+`ml/` (this session) |
| **MLSEC-2** | **the model artifact's `calibration` block is an unvalidated code path into `p_win`.** `ml/calibration.py:112-118` `IsotonicCalibrator.from_dict` copies stored knots with **zero validation** (no monotonicity, no sort, no finiteness, no key check) and `fitted` is true at `len(x)>=2`; `ml/meta_model.py:225` checks `np.isfinite` on the **RAW** model output, line 227 then applies the calibrator, and **nothing re-checks after it** — `np.clip(nan,...)` is `nan`. **Injection-confirmed 2026-08-30**: a NaN knot makes `p_win()` return **nan** with `fallbacks=0, infer_faults=0` (the fail-safe counters that exist for this never move, so `status()` reads healthy); `y` pinned to 0.95 gives an attacker-chosen probability (raw 0.60 → 0.7925); descending `x` maps every probability to 0.02; a `calibration` block missing key `"x"` raises **KeyError out of `MetaModelService.reload()`**, i.e. out of `__init__`. **Severity deflated honestly**: `risk/position_sizer.py:425` does guard `_fin(p_win)`, so the realized outcome is a *silent, uncounted, total entry outage* with the health panel reading green — not mis-sizing. Pairs with MLSEC-1 (which is what lets a swapped artifact land at all) | same |
| **MLGOV-1** | **the governor's calibration-gap clause silently dies below n=5.** `ml/calibration.py:36-37` returns **`0.0` = "perfectly calibrated"** when `len(y) < n_bins` (5) — an absence sentinel inside the domain of the comparison — and `ml/monitor.py:258/274-277` consumes it raw as one of the three `degraded`/`failing` clauses. `core/config_guard.py:2187-2191` bounds `ml.monitor.min_trades_to_judge` **only from above** (`<= window_trades`); nothing forbids a value below 5. **Injection-confirmed verdict FLIP 2026-08-30**: promised p=0.81 with 5/5 wins reads `calib_gap=0.1897 → degraded=True` at n=5, and the identical promise/rate reads `calib_gap=0.0000 → degraded=False` at n=4, with the Brier clause (0.036 vs baseline 0.25) and hit-deficit both silent — the sentinel alone flips it. Latent today (default `min_trades_to_judge`=15, key absent from config.json). Cheapest fix is a config_guard lower bound (SAFE); changing the sentinel to `None` touches the governor verdict = BOUNDARY | same |
| **PT-B1** | **`execution/pretrade.py:165-178` `maker_dist_bps` fails OPEN on an unreadable book touch**: the permissive branch needs a `mid` of exactly 0.0 or non-finite, which `:178`'s `if _fin(mid) and mid > 0` then turns into `dist_bps=0.0` ("at the money") → `p_fill` jumps to its **ceiling** `maker_fill_p0`. **Trigger set, exact (corrected 2026-08-30, see below):** a touch that raises `TypeError`/`ValueError`/`IndexError` at `:176` (non-parseable value, short/malformed row) → `mid=0.0`; a NaN touch → non-finite `mid`; or **BOTH** touches zero. **Injection-confirmed 2026-08-30**: identical inputs, healthy book → `p_fill 0.0500, EV +16.18bps`; bid touch NaN → `p_fill 0.4500, EV +149.65bps` — a **9.25x EV overstatement** on exactly the input the gate should distrust, and both APPROVE. **CORRECTION (2026-08-30, adversarial re-verify — this row previously listed "zero" bid as a trigger; that was FALSE and is struck):** a `bid=0.0` beside a LIVE ask takes the **CONSERVATIVE** branch — `mid = 0.5*(0.0+ask)` is positive, so a 0.0 bid against a 101 ask at price 100 measures `mid=50.5, dist=9801.98bps, p_fill=0.0500`, i.e. maximally distrusted, the opposite of fail-open. The mechanism and the 9.25x figure STAND for the non-parseable / NaN / short-row inputs above. The one-sided-book veto at `pretrade.py:299` only tests list truthiness, never parsability. **Reachability deflated honestly**: all **THREE** shipped `bot.kraken_books[asset]` writers — `main.py:2651`, `main.py:2729`, and **`runner.py:940`** (PAUSED-flatten refresh; *missed by the original reachability grep, count corrected 2026-08-30 — the conclusion survives*) — source from the two production book paths (`data/kraken_feed.py:289` REST and `data/ws_feed.py:107` WS), both of which route through `core/sanitize.clean_book`, which drops bad levels and returns None if a side empties. So this is **unreachable today**, guarded by exactly ONE upstream sanitizer with no defense in depth at the gate. Test doubles inject clean books, so the branch is never exercised in test either (`concepts/test-double-fidelity`) — *note this is "not exercised by the doubles", NOT "untested": no mutation run has established that, see OWED-VERIFY below*. NEW-HIRE hazard: `pretrade.py:34` asserts "Everything is fail-closed: any non-finite input rejects (PT-010)", which is **false for the book** — a maintainer adding a fourth book source re-opens it instantly. BOUNDARY (the gate decides entries) | same |
| **PT-B2** | **`execution/pretrade.py:268-273` participation clamp silently NO-OPS at zero depth** — `if max_units > EPS` means an unreadable depth read is "no clamp needed", not "no depth data". **Injection-confirmed 2026-08-30**: with the trade-direction side's sizes unparseable/0/negative/NaN the full **5.0000** units are approved and the reason list is **`['PT-000']`, byte-identical to healthy** (the SWEEP-1 signature), where a thin-but-readable book correctly clamps to 0.6000 with `PT-030`. The **taker** path is protected by `book_walk_bps`'s 1e6 sentinel (`PT-023` fires); the **maker** path — i.e. every entry, since invariant #5 makes entries limit-only — is not. Same `clean_book` reachability deflation as PT-B1 (**three** shipped `kraken_books` writers, `main.py:2651` / `main.py:2729` / `runner.py:940` — count corrected 2026-08-30, conclusion unchanged); this is the vault's long-documented "participation clamp at zero depth" instance (`concepts/zero-is-not-a-reading`), now localized to the maker path. BOUNDARY (sizing) | same |
| **FEEDOC-1** | **`execution/pretrade.py:6` and `:81` assert a SUPERSEDED fee world as venue truth** — "venue-true 40/80bps as of cut #8" and "config.json 40/80", while `config.json` has carried **22/38** since cut #9 (2026-08-30). Runtime behavior is correct (config is authority; verified `pretrade.maker_fee_bps=22.0 / taker=38.0`), but the stated *reason the 40/80 fallback is "dead in production"* — that `config_guard` FATALs any config below the floor — **no longer holds**: cut #9 set `pretrade.allow_sub_floor_fees=true` (verified live), so `core/config_guard.py:582` skips the floor check entirely, and the guard's own fee defaults (`config_guard.py:570-571`) are **25/40, the explicitly-retired tier**, a third value disagreeing with both. Absent fee keys would now start silently. **FOURTH SITE (added 2026-08-30): `core/config_guard.py:565-566`** — the comment above those defaults asserts "The shipped config carries the keys explicitly at **40/80**, so these fallbacks never fire in production", stating the superseded tier as current AND resting on the same dead floor-FATAL premise. So the stale-40/80 assertion count is **4**: `pretrade.py:6`, `pretrade.py:81`, `config_guard.py:565-566`, plus the retired-25/40 defaults at `config_guard.py:570-571`. This is the-method recurrence #1 (a struck fee schedule asserting itself as truth) in comment form. Comment correction = **SAFE**; changing the 40/80 fallback constants = BOUNDARY (fee booking) | same |

| **POWER-1** | **gate power analysis (MinTRL/PSR)**: NET needs 62 trades at configured fees (gate stops at 50) and **1,603 or INFINITE at true Kraken T1**. Two of three fee worlds are the pre-registered COST_BOUND arm. ~~GROSS edge already established~~ **— that half is WITHDRAWN by POWER-2** | `docs/quant/2026-08-22_gate_power_analysis_mintrl.md` |
| **POWER-2** | **resampling tranche 2 corrects POWER-1's headline.** Cohort n=33 carries **n_eff=9.92** (mean uniqueness 0.301); gross MinTRL is **9.94** — the gross edge is **precisely undetermined**, not established. Sequential dependence is unresolvable at this n (Politis-White block 1.3); **concurrency is the binding deflation** (SE x1.82). New: **cost tolerance** = 118 bps by point estimate, **43 bps** demanding distinguishability — below the 67.04 bps already booked. Also **walks back tranche 1's "independent confirmation" of the 66.76 bps cost**: both routes are anchored on the same configured 65 bps, so their agreement proves booking==config, not venue truth (`cost_truth_report` §1: OM-080 n_records=0) | `docs/quant/2026-08-22_walkforward_resampling_tranche2.md`, `scripts/walkforward_lab.py` |
| **TRIALS-1** *(SAFE)* | no ledger of how many strategy configurations were evaluated before the deployed one, and none of their SR dispersion. Without it DSR cannot be computed — only tabulated against hypotheses about N (`deflated_sharpe` falls back to var=SR^2). Cheap, purely additive | same |
| **WHY-1** | **era-4 dollar decomposition at readout (n=54)**: gross +$8.23, fees $6.87 booked / $13.59 true -> net +$1.36 / **-$5.36**. The split that matters: **conviction n=5 nets +1.46%/trip at TRUE fees; probes n=49 net -1.05%** - 91% of trades are tuition whose gross (+0.28%) sits below the round trip. Alt tail (DOGE/ARB/LTC/ADA/SUI) -$3.67 on 27 trips; BTC/ETH/LINK +$4.56 on 18. Median ticket **$18** - unbeatable fee floor. Verdict machinery worked: COST_BOUND shape + old gate STAND DOWN. Remedies all staged/docketed: boundary #5, ALGO-5, CONC-1, asset discipline | `docs/quant/2026-08-26_why_losing_deep_dive.md` |
| **CONC-1** *(cohort-resetting — do NOT act before readout)* | mean uniqueness 0.301 means the cohort buys information at ~1/3 of nominal rate. Raising it is a **sizing/concurrency** decision, inadmissible under the moratorium. Logged for boundary #6 | same |
| ~~**FEE-1**~~ **SHIPPED at cut #8 (2026-08-28)** | **configured fees are ~half the venue's real bottom tier** (Kraken T1 = 40/80, config = 25/40). Worth **−$4.04 of the accrued +$5.04** in the cohort window. Writing the true number produces a **config_guard FATAL** — the bot will not start, because exploration `p_win 0.700` falls below the net-Kelly breakeven `0.833` | `raw/quant/` cost-stack report; injection-verified |
| ~~**FEE-2**~~ **SHIPPED at cut #8 (2026-08-28)** | at true fees the entry bar moves **p 0.690 → 0.834** (+14.3 pts), so the probe lane that generates 85% of the cohort stops clearing by construction. Re-derived independently at apply time: b_net 0.4488 → 0.1998, breakeven 0.6902 → **0.8335** — the adjudication doc's number, confirmed by a second route | same |
| **QT-1** *(NEW 2026-08-28, needs its own adjudication — do NOT flip it in a passing commit)* | `scripts/quant_trials.py`'s harness-owned `TIER_CFG["est_fee_bps"]` is **40** and the deployed config is now **80** — the harness's declared "mirrors config.json's shipped block" property is DRIFTED by cut #8. Measured before deciding (200×1200, seed 7, runtime-proven config-independent: **0** config.json reads at import or during `run_trials`): as-is **G1–G5 all pass, byte-identical to pre-cut**; mirroring the cut (est_fee_bps 80) makes **G5 capture FAIL, 0.57 vs baseline 0.61**, and collapses G1's margin to 4.84% vs cap 4.91%. Same shape as the adjudicated #103 T6 enablement finding. Left UNCHANGED and NOT widened; the standing gates are honest about the harness world they were baselined in, and now demonstrably *not* about the deployed cost world. **UPDATE cut #9 (08-30):** deployed `est_fee_bps` corrected **80 → 38**, so the harness-40-vs-deployed drift narrowed from 40bps to **2bps** (near-coherent again); the G5-fails-at-80 result was an artifact of cut #8's ~2x-too-high fee. Harness still runtime-proven config-independent, so `test_quant_trials.py` stays green byte-identically — the harness's 40 is now an honest near-mirror of the deployed 38. Not re-measured at 38 (out of this cut); the 80-mirror finding is superseded, not re-run | `scripts/quant_trials.py:73-82`, this session's boundary-#5 report |
| **CTRL-2** *(SAFE, unblocked by the cut #8 merge)* | the control-arm tag is now WRITTEN but nothing consumes it. `gate_efficacy_report.py` needs its second, era-current baseline arm sourced from the tag's minority-arm rows — the only route out of the universal CONFOUNDED_BASELINE/PARTIAL_OVERLAP state. Two drifts the original TODO must absorb: the era-current arm must clear `ERA_OVERLAP_MAJORITY` by construction (not merely the floor), and any new `comparison` value must route through the two-vocabulary verdict function at `gate_efficacy_report.py:228-237` or it reintroduces the F1 inversion `0084c16d` killed. Needs accrual first (~usable n=30 in 0.85–1.6d of live rows) | sandbox report §5, `scripts/gate_efficacy_report.py` |
| **DATA-1** *(BOUNDARY, found 08-30 data-pull audit)* | `MoomooFeed._poll_options` (`data/moomoo_feed.py:372-377`) picks NTM option contracts with `picked = picked[:self.opt_max_contracts]` — an order-dependent truncation on whatever row order `chain.iterrows()` returns, not sorted by distance-to-mid. If an underlying's NTM band ever exceeds `opt_max_contracts` (60) simultaneously-listed contracts, WHICH contracts survive the truncation depends on SDK row order (not proven stable call-to-call), so `opt_pcr_z`/`opt_iv_skew` could vary for reasons unrelated to price. Feeds an ML feature -> BOUNDARY if changed (fix would alter feature values feeding the model). Not observed live yet (crypto-proxy chains rarely exceed 60 in a 10% NTM band) — fix = sort `picked` by `abs(strike-mid)` before truncating, same selection semantics, deterministic order | `data/moomoo_feed.py:341-377`, this row |
| **DATA-2** *(BOUNDARY, found 08-30 data-pull audit)* | `WebDataFeed.maybe_poll`'s CoinGecko-fetch exception path (`data/webdata_feed.py:120-124`) holds `btc_dominance`/`total_mcap_usd` at their last-good value on failure (consistent with the module's own stale-hold design) but hard-resets `dominance_delta` to `0.0` instead of holding ITS last value too — an inconsistency within the same fallback block, not a crash risk. `dominance_delta` is an ML feature -> BOUNDARY if changed. Low severity (CoinGecko fetch failures are rare and the field already defaults neutral) but worth reconciling with the hold-last-value convention the rest of the block uses | `data/webdata_feed.py:99-124`, this row |
| **FEE-3** *(RE-CORRECTED 2026-08-31 by OPERATOR TESTIMONY — the row below is preserved for the record but its "credentials existed" deduction is OVERTURNED)* | **Operator: "I've never put my keys into this bot."** With that as ground truth, the n=1 row CANNOT be a venue reading: `_private_post` requires a valid HMAC (Kraken rejects otherwise → error → None → no row, re-read 2026-08-31), so the process that wrote seq 69754 ran a DOCTORED feed — **planted fixture data in the production audit** (AUDIT-SEAM-0829's 62-second unredirected harness). Consequences: (a) the adjudication doc's original "n=0, no credentials" was RIGHT about production; (b) `cost_truth_report` n_records=1 / XV-033 DANGEROUS was fed by pollution, not the venue; (c) tier evidence = the operator screenshot ONLY — the 40/80 "reading" carries no venue weight. FEE-3's remedy is now an OPERATOR SECURITY DECISION, not a default step: a read-only TradeVolume key would be the FIRST credential this bot has ever held; the zero-key alternative is a periodic manual app-tier check, which is legitimate. the-method recurrence: QA data read as production truth | operator statement 2026-08-31; `data/kraken_feed.py:169-183`; AUDIT-SEAM-0829 |
| **FEE-3-superseded** *(the 2026-08-30 audit row, kept per both-sides rule)* | OM-080 has fired **n=1**: `outputs/audit.jsonl` seq 69754, 2026-08-29T15:47:07.123Z, XBTUSD **40/80 bps** — double-derived (full-range grep n=1; `cost_truth_report.py` `n_records=1`, live verdict **XV-033 DANGEROUS: configured UNDER measured** vs shipped 22/38); record predates the cut-#9 adjudication commit `16ec821e` by 4h40m58s, and the emit path requires a signed non-error `TradeVolume` response, so credentials existed on the box 2026-08-29. **The tier is a 2-element identified set** {40/80 [K, one venue reading — possibly schedule-top for an untraded pair] vs 22/38 [I, operator app screenshot]} and **era-6 accrues at 22/38 while the only venue reading on record says 40/80**. REOPENED remedy (SAFE, measurement-plane, highest value/cost on this docket): `data/kraken_feed.py:415-428` keeps only `fee` and discards `minfee`/`maxfee`/`nextfee`/`nextvolume`/`tiervolume` + 30-day `volume` — log the full tier context and re-run `cost_truth_report.py`; those fields distinguish "account rate" from "schedule top" and confirm/refute the $17,482 volume figure. POWER-2's "OM-080 n_records=0" clause was true when written (08-22) and is superseded by this row | `execution/order_manager.py:767`, `data/kraken_feed.py:406-429`, vault `concepts/partial-identification` |
| **AUDIT-SEAM-0829** *(SAFE detector owed; classification CORRECTED 2026-08-31)* | The OM-080 row rides a **62-second fork**: audit.jsonl holds two lineages both descending from seq 69742 (`prev e1eae5c3`) — segment A = ML-030/ML-050 burst + the OM-080, 15:46:05→15:47:07Z, then gone; segment B (15:57:13Z) is the canonical chain today's rows still descend from. Commit `41e6b9eb`'s message called this "a second stale-config credentialed process… same class as the 2026-07-13 fork" — **that classification is WRONG and this row is the correction of record** (the `8a9cc087` precedent): a 62s lifetime forking from the live tail is an **unredirected SCRIPT** (SD-007 audit-pollution class), almost certainly the 08-29 fee-adjudication session's own verification tooling running with transient operator keys on a pre-cut-8 backup config (its cached 25/40 matches). Systemic: **38 duplicated seqs file-wide across ~10 fork segments**. CORRECTION 2026-09-01, by running the instrument: the "nothing flags it" clause was FALSE — `session_digest` counts the seams (`chain_seams: 10`) and **SD-010 audit_writer_seam FIRES** (info, "benign — nothing committed altered"). The real gap is smaller: no per-seam detail (an operator reading "10 seams, benign" cannot locate the OM-080 that rode one) and no severity escalation when a forked segment carries consequential disposition codes. OWED (SAFE, shrunk): seam detail + payload-aware escalation in SD-010, not a new detector | this row; re-derive: the file-order map of seqs 69735-69760 |
| **ML-DEPLOY-1** *(MECHANISM REFUTED 2026-08-31 late session — statistical adjudication pass; row preserved below per both-sides rule; NO code defect stands, NO adjudication owed on the gate)* | **CORRECTION: the deploy gate has been like-for-like since `8b91f697` (2026-07-26).** The else-branch at main.py:6664-6692 gates on `shared_challenger_brier` (ml/monitor.py:572-616, challenger restricted to the IDENTICAL `oof_idx >= trained_rows` rows `rescore_frozen` scores the champion on) — verified live: ML-042 @ 2026-09-01T01:34:32.531Z rescored the champion fresh (0.2439→0.2443) and ML-041 4ms later gated challenger **0.2442 vs champion 0.2443** on the shared set. Post-08-26 full-range audit scan (n=73 decisions, 0 deploys): shared-window gap mean **+0.00064, SD 0.00236**, challenger better **31/73** (≈coin), by the 0.005 margin **0/73** — a statistical TIE; expected deploys under exchangeability ≈0.6, observed 0, nothing anomalous. The 73-reject streak is the DESIGNED incumbent-wins-ties policy, not a biased exam; champion shared-window brier band 0.2225–0.2549 stable → **input drift WITHOUT performance drift** (benign covariate shift), so lb-drift-stuck is informational. The debug's error: it read `retrain_history.jsonl` columns (`oof_brier` full-span vs `champion_bar`) as the gate's decision variables — a report column mistaken for the authority (the-method rule 7b; the summary field was the instrument). What stands from the original: the window difficulty differential (~0.264 post-08-26 vs ~0.383 pre) is real but UNCROSSED by the gate; diet-poisoning stays refuted; the calibrator-ceiling half lives in PI-2 unchanged and remains bundled at the ALGO-5/GB-1 boundary. Per-decision paired SE MEASURED same session (operator asked to see it; paired-refit second route, scratchpad `paired_se.py`, corpus n=11,191 read 21:16 local): per-row sd(d)=0.185 on n=4,462 fresh rows → SE **0.0028 raw / 0.0037 Kish (ESS 2,525) / 0.0087 worst-case uniqueness (n_eff 458)**; margin 0.005 = **1.8 / 1.4 / 0.6 SE**; the across-decision gap SD 0.00236 corroborates the raw route (two routes agree ~0.0024–0.0028), and the twin refit is LESS prediction-correlated than a production challenger (twin gap −0.0397), so these SEs are upper bounds. Hourly decisions rescore near-identical data — the 73 rejects collapse to roughly ~6 independent draws — so 0/73 margin-clears is consistent with exchangeability under EVERY deflation treatment (even the harshest: 0.72^6≈14%). Champion instrument validated in the same run: superset-window fresh brier 0.24461 vs gate-logged 0.2443. Champion dossier: `1ee3ae68c0df`, logistic 64-feat schema v9, trained 6,729 rows, fresh-score series since deploy n=74 mean 0.2475 sd 0.0061, slightly IMPROVING (0.2529→0.2443) across 4,462 new rows. **RETRACTED SAME SESSION (adversarial-reviewer pass, ~40 min later): "beats a naive same-window refit by 0.0397 (~14 SE) — the freeze is earned, not lucky" was an OVERCLAIM against a strawman I built.** Decomposed (`twin_decomp.py`): 34% of that 0.0397 was the twin's IN-SAMPLE-fitted isotonic (the champion's is cross-fitted) — a handicap of my own construction, not a champion virtue. Against the RIGHT null the result inverts: **skill score vs the oracle constant b(1−b) is −0.00378 on the 4,469-row index-fresh window and −0.00326 on the 4,067-row time-fresh window — NO measurable out-of-sample skill** (champion 0.24459 vs oracle constant 0.24367; the +0.00092 deficit is ~0.33 SE, i.e. indistinguishable from zero, NOT significantly worse). In-sample it does fit something: train-window skill **+0.05363**. Its calibrated output on fresh rows is near-constant — range [0.4014, 0.6116], **sd 0.0184** — which independently REPRODUCES PI-2's 0.6446 ceiling (exact, as the train-window max) and supplies its missing MECHANISM: the isotonic is not capping a good model, it is correctly reporting a model with nothing to say, and a near-constant predictor is trivially "stable", so the 74-cycle stability I reported is VACUOUS. This also re-explains the gate tie ABOVE at a deeper level — both arms converge to the base rate, so no challenger can clear 0.005; the gate verdict (no defect) STANDS, the champion-quality inference does not. **SIGNAL-EXISTENCE GATE (2026-09-01) — NOT PASSED; do NOT build counterfactual/regret machinery yet.** Operator sequencing rule: establish that any exploitable signal exists BEFORE building machinery to exploit it. **Instrument validated two ways first** (this is the rule-3 separation of "0 findings" from "the scan is broken"): planted linear signal on the REAL feature matrix + real split recovers cleanly with a monotone dose-response — noiseless **+0.806**, noise0.5 +0.528, noise1.0 +0.256, noise2.0 +0.096, noise4.0 +0.015, noise8.0 −0.011 — and shuffled labels score **−0.0004** (no fabrication). The live direction target (−0.006) therefore sits between the noise-4 and noise-8 rungs: *if* signal exists it is weaker than a planted signal buried in 4× noise. A forward-volatility positive control FAILED (−0.27) but is attributable to its own construction (corpus is sig-sorted ACROSS ASSETS so "next row" is a different instrument; global-median threshold straddles a regime shift) — a bad control, not a bad scan. **Targets tested on the 5,027 candidate rows carrying `label_ret_pct` (2026-08-24 → 09-01, the only rows whose real-valued outcome survives):** T0 barrier label +0.043 (+1.2 deflated SE), T1 sign(label_ret_pct) +0.043 (+1.2), T2 |ret| top-quartile +0.172 (+1.9), T3 shuffled −0.002. **NOTHING CLEARS SIGNIFICANCE**, and with 4 targets tested even +1.9 is inside multiple-comparison noise. **Two corrections of record:** (a) T0 and T1 agree **1.000** — `label` IS sign(label_ret_pct) (`ml/history.py:1276`), so "the deployed target is a misaligned proxy for the objective" is **REFUTED for SIGN**; the real misalignment is that the target is 1 BIT of a real-valued outcome, so a trade clearing cost by 0.01% weighs the same as one clearing by 3% while expectancy depends on magnitude (the payoff-asymmetry problem in target form). (b) T2 is substantially **TAUTOLOGY, not signal**: corr(|ret|, pt_frac)=**0.4846** and the top quartile is 71% tb_sl, so it largely predicts the volatility-scaled BARRIER GEOMETRY set at entry from features the model can see — verified before it could be reported as a lead. Method caveat: this last run used a hand-rolled CSV feature read, NOT the production loader (no contract screen, clash-dedup, era exclusion, or sample weights) — a weaker instrument than the validated one, deliberately NOT promoted to `scripts/` for that reason; re-derive with the production loader before acting. Counterfactual/regret note: only **5,027 of 21,617** candidate rows (23%) carry the magnitude at all — before schema 93→94 the corpus wrote a literal 0.0 into `net_pnl_usd` for every candidate, so a regret ledger can only be built FORWARD from 2026-08-24 and is currently ~8 days deep.

**CAPACITY LADDER (2026-09-01, `champion_skill_report.py --ladder`, n=4,887 unseen rows, identical split per rung, isotonic on a held-out tail of TRAIN):** every one of the eight family rungs scores NEGATIVE skill, and capacity is monotonically HARMFUL — blend −0.0041, mlp 128-64 −0.0048, logistic (deployed) −0.0059, adaptive_gbt −0.0100, gbt stumps −0.0189, mlp 32-16 −0.0238, gbt depth-4 −0.0270, ensemble_mlp −0.1943. **No rung beats a constant**, so the binding constraint is the TARGET, not model capacity — the signature of fitting noise. This is evidence FOR the 2026-08-10 model freeze, not against it: more network on an unlearnable target is precisely the overfit direction the OF battery and the moratorium exist to prevent. Measurement-only (fits discarded in-memory, nothing deployed/saved/written); does NOT reopen the freeze, and the ALGO-5/GB-1 boundary is unaffected. Watermark alignment measured while checking this: 402 rows sit in the index-fresh window that predate the deploy wall-clock (sig-sorted late-resolving interleave, the exact caveat `rescore_frozen`'s docstring names) — worth +0.00085 of champion Brier, in the ANTI-flattery direction (index window is harder than time window), so the docstring's "never an in-sample flatter" claim survives, now measured rather than assumed. Still owed (SAFE, additive): `n_shared` in the ML-041 detail payload. ORIGINAL ROW (superseded mechanism): **The deploy gate examines incumbent and challenger on DIFFERENT row populations.** `ModelMonitor.rescore_frozen` (ml/monitor.py:535-555) scores the frozen champion ONLY on rows past its training watermark ("only rows past it count as unseen") — the newest ~4k rows — while `challenger_brier = brier_score(sel['oof_y'], oof_cal)` (main.py:6565) averages the FULL OOF, old rows included. Measured (production loader, n=10,976, era_excl active, 2026-08-31 18:21Z): every model scores ~0.264 on post-08-26 rows vs ~0.383 on pre-08-26 rows, so the incumbent's exam is systematically easier by >> deploy_margin 0.005; the stable ~0.009 champion advantage is the WINDOW difference, not model quality. Diet-poisoning REFUTED same run (recent-only diet OOF 0.306 BEST, champion-diet 0.391 WORST, full 0.333). Chain: window-asymmetric gate -> deployed:False x367 -> deciles frozen at 08-26 -> PSI pinned 0.333 -> lb-drift-stuck (a true symptom of a gate defect, not the market). ML-042's 2026-07-18 fix traded badge-squatting for window-squatting — the-method rule 5: the referee was the instrument. Remedy sketch for adjudication (NOT applied): score BOTH arms on the same unseen-region rows (restrict challenger to oof_idx past the same watermark), pre-registered, one boundary. Calibration is symmetric (challenger uses oof_cal) — that hypothesis was tested and died. Residual: the like-for-like sliced comparison (challenger's oof_cal restricted to idx>watermark vs champ_fresh) needs the production trainer to emit it — named, not run | ml/monitor.py:535-555, main.py:6548-6621, retrain_history.jsonl (367 records), the two-diet experiment (session 2026-08-31) |
| **PI-1** *(SAFE — correct the cut-#9 decision record)* | `docs/quant/2026-08-29_fee_tier_correction_adjudication.md:84-90` carries a **[K] tag that is false at authorship** ("OM-080 n=0 ... no credentials": measured n=1, 4h40m58s before the commit) and `:82`'s booked-median-65.4bps cross-check is **circular** (config then in force = 65bps round-trip; POWER-2 already named this shape — agreement proves booking==config, not venue truth). Operator adjudicates striking both clauses with a dated callout; the record is decision-grade and operator-owned, so it was NOT edited by the audit. Does NOT reopen the 22/38 ground truth by itself — see FEE-3 for the evidence route | vault `concepts/partial-identification`, this session's audit register |
| **PI-2** *(SAFE — disclosure that changes what the era-6 readout MEANS)* | the model entry path is **structurally closed at every element of the fee set**: deployed champion `1ee3ae68c0df` raw range [0.0196, 0.9832] but isotonic-calibrated ceiling **0.6446** < bar 0.6772 (live post-shrink 0.5687), **0/21,047 corpus rows clear** — mutation-verified (identity calibrator frees 1,956 rows: the CALIBRATOR closes the path, the scan is live). Every live entry is a synthetic-p probe (exploration 0.85 / aggressive 0.72), so gates reading "the strategy" read the probe lane. Recurrence of `_label_max_bars_migration_doc`'s "structurally unreachable" ceiling (0.2164 vs 0.63) at a new geometry, undetected — record it in the readout's preamble; any calibrator/bar change is COHORT-RESETTING and waits for the boundary | vault `concepts/partial-identification` |
| **PI-3** *(SAFE — the closing veto is unobservable)* | `main.py:4152-4160` logs non-exploration sizer vetoes at DEBUG; `system.log_level` INFO; 0 DEBUG lines persisted; **0** SZ-023/SZ-030 in the full 70,409-line `audit.jsonl` — the system's most-firing veto leaves no record anywhere (why PI-2 went unremarked; the CLAUDE.md asymmetry in pure form). Remedy: raise to INFO or emit a registered audit code — measurement-plane, but touches `main.py`, so ship through a normal DoD-green commit, not an audit session | `main.py:4152-4160` |
| **PI-4** *(BOUNDARY — LS-2 scope extension; CONFIRMS LS-2, does not rebuild it)* | the audit PRICES LS-2 ($50.44–$113.51 ticket set at its own most-favourable assumptions; $0.00–$153.14 jointly; shipped point $81.97 = minimax-regret action at NO rung) and finds three gaps OUTSIDE its scope as written: (a) the entry-bar set [0.6772, 0.8335] is a **cost**-side unidentification Bayesian p-sizing cannot move (belongs with FEE-3, sequence it FIRST — b_net uncertainty dominates p_win uncertainty in the joint set); (b) **admission is not sizing**: the p-bar veto is a 1e-4 step on a point (`position_sizer.py:469`) with no vocabulary for a p-interval straddling the bar — the trade/no-trade decision itself is unidentified at the SMALLER measured calibration error (0.72−0.06647=0.6535 → $0 vs 0.72 → $20.30), and no sizer helps while the ceiling sits below the bar; (c) the governor applies its 3-valued `kelly_mult` AFTER veto and f_star. Operator adjudicates: widen LS-2 to admission or docket separately; bundle with ALGO-5/GB-1 at the boundary | `docs/quant/2026-08-20_learning_symmetry_synthesis.md`, vault `concepts/partial-identification` |
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

- **ERA6-COUNT-1 — no tool counts era-6 accrual; the only gate headline on
  screen pools three cuts.** Measurement-plane (SAFE class), opened
  2026-08-30. CLAUDE.md's moratorium says era-6 accrues "from zero" at the
  cut-#9 restart, but NO script computes that number — a repo-wide scan for
  `16ec821e` finds it only in `core/fill_ledger.py:87`, `scripts/glass_console.py:55`,
  a test pin, and prose. Meanwhile `cohort_eval.py` prints
  `accrual: 72/50 … COST-BOUND` (L718-719, L753-756), which reads like a
  current-regime verdict but is the pre-registered **era-4** population:
  a pure timestamp cut at `max(B4_TS, CAPITAL_EPOCH_TS)` = 2026-08-10T23:05:27Z
  (L320-322), pooling cuts #7/#8/#9.
  **This is NOT a computation defect and must not be "fixed" by filtering the
  gate** — the era-4 population is pre-registered (L75-77) and re-selecting it
  after accrual is precisely what pre-registration forbids (L270-272 states
  this). The tool also already DISCLOSES the pooling (`COHORT HOMOGENEITY:
  MIXED(both)` + `distinct stamped eras present: 7-e7d5ca1a, 8-ca55e2ba,
  9-16ec821e`, L777-778). The real gap is **presentation + coverage**: the
  headline is not era-labelled, and the full era ENUMERATION sits **34
  printed lines** below it (headline at printed line **39**, enumeration at
  printed line **73** — measured 2026-08-30; the earlier "~40" was an
  unmeasured approximation, and rule (a) forbids a "~" boundary in a
  permanent file). **CORRECTION, against this row's own interest
  (2026-08-30):** `COHORT HOMOGENEITY: MIXED(both)` prints at printed line
  **40 — ONE line BELOW the headline**, not 34 lines away. The "a reader
  stops at the headline and never sees the disclosure" argument is therefore
  **materially WEAKER than originally written**: the pooling warning is
  adjacent to the headline; only the which-eras enumeration is distant. What
  survives is the narrower, still-real complaint — the headline itself
  carries no era label, `MIXED(both)` names neither WHICH cuts nor in what
  proportion, and **no tool computes era-6 accrual at all** (the coverage
  half, untouched by this correction). Nearest honest fix, both SAFE: (a) label the
  era-4 headline as era-4/pooled at the point of print, and (b) add a separate
  era-6 accrual counter (reuse `era4_trips()` unchanged and segment on its
  existing report-only `eras` field — no change to any selection predicate).
  Current value while that is owed: **4** (see the AS OF table).

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
- SAFE-NOW observability backlog from TURB-1 (turbulence absent from `status.json` entirely; silent stale-hold; no config_guard coverage) — see the synthesis doc's disposition section.
- Champion Brier / calibration gap after each retrain: a base-rate
  regime shift moves both honestly (see the settled entry below).
  Escalate only if degradation persists a full barrier horizon *after*
  the base rate returns to ~0.2.
- Exploration probe rate (~56/hr in volatile tape) — loud by design,
  budget-capped; it is the corpus flywheel, not a fault.
- Drift share vs the 30% retrain vote line.
- **DELIVERY-1 — alert delivery is VERIFIED to the routing layer, but the
  root-route trap is STILL ARMED for the next rule.** Adversarial re-check of
  the 08-30 notification fix (all reads 2026-08-30T22:38–22:44Z, Grafana
  13.3.0-32244229338.patch1, stack ns `stacks-1722437`): the fix is
  **substantive, not cosmetic** — the suspicion that it "moved the null one
  layer down" is REFUTED by four independent routes. (1)
  `/api/v1/provisioning/contact-points` → exactly ONE contact point,
  `grafana-default-email`, uid `cfs1d30a113b4c`, type email, **1 integration**,
  `addresses` = the operator's real gmail (verified by string equality in
  memory, never printed; len 19, not a placeholder). (2) Full AM config
  (`/api/alertmanager/grafana/config/api/v1/alerts`) shows Grafana's
  **simplified-routing autogen subtree** under root: `__grafana_autogenerated__
  = true` → child `__grafana_receiver__ = grafana-default-email` → that
  receiver. Receiver `empty` is real and has **zero** `grafana_managed_receiver_configs`.
  (3) k8s API `.../namespaces/stacks-1722437/receivers` → `empty`=0
  integrations, `grafana-default-email`=1. (4) **The runtime's own testimony**
  (`/api/prometheus/grafana/api/v1/rules`): live alert instances for all 4
  rules already carry the labels `__grafana_receiver__: grafana-default-email`
  + `__grafana_autogenerated__: true` — i.e. Grafana is attaching the matcher
  labels at evaluation time, not just storing config. All 4 rules
  `isPaused=false`, `health=ok`; zero mute/active time intervals anywhere in
  the tree. **Verdict: an alert firing now DOES reach a human.**
  *Two things this did NOT prove, and one live trap:*
  (a) ~~**SMTP dispatch itself is unproven**~~ **— CLOSED 2026-08-30T23:05Z by
  an ORGANIC firing; nothing artificial was sent.** `GET /api/alertmanager/
  grafana/config/api/v1/receivers` returned, for `grafana-default-email`:
  `lastNotifyAttempt='2026-08-30T23:05:05.164Z'`, `duration='341ms'`,
  `error=None` — the dispatch record of the real `lb-drift-stuck` firing
  (`startsAt` 23:04:30Z), handed to the mailer 35s later with no error.
  **Correct the method claim this lane made, too: "only a real send closes
  that" is FALSE as a general statement.** It was true at 22:44Z, when
  nothing had ever fired and the receivers endpoint therefore held no
  dispatch record; it stopped being true the moment any rule fired. That GET
  is a **ZERO-COST read of the dispatch record** — it sends nothing, and it
  is the check to run FIRST before ever considering the operator-gated
  "DELIVERY TEST" block in `docs/grafana/liquiditybot_deadman_alert.yaml`
  (which does send a real email and stays not-run-unattended).
  **Residual that genuinely survives, unclosed:** `error=None` proves only
  that Grafana Cloud's mailer ACCEPTED the handoff. It does **not** prove
  gmail delivered to the INBOX rather than spam, and does not prove the
  mailbox is monitored. **Zero-cost close, operator-side:** eyeball that
  inbox (and its spam folder) for an `lb-drift-stuck` mail timestamped
  ~2026-08-30T23:05Z.
  (b) ~~root route receiver `empty`~~ **CLOSED 2026-08-31 under operator
  "Go":** root receiver repointed `empty` → `grafana-default-email` via PUT
  /api/v1/provisioning/policies (HTTP 202, GET-verified; group_by preserved,
  per-rule autogen routes untouched). New rules without
  `notification_settings` now page by default; per-rule overrides remain as
  belt-and-braces. Re-derive: GET the policies endpoint, read `receiver`.
  (c) Contact point has `provenance: "api"`, so it is **locked in the Grafana
  UI** — edits to the destination address must go through the API.

---

## OWED-VERIFY — the 2026-08-30 audit wave's NOT-DONE register

**Read this before citing anything from the MLSEC/PT/DATA rows above as a
clean bill of health.** Every line here is a TASK OWED, not a fact; each
names a place the wave did NOT look, or a lane that FAILED. All READ/measure
class (unfenced) unless marked. *A "0 findings" that was never run is not a
0 — CLAUDE.md mindset rule 3.*

**Two lanes FAILED and produced nothing — recorded so they are not
rediscovered as gaps in the record:**
- **GAP-1 (fresh-worktree, host-state-independent suite): FAILED, no
  findings.** Died on a git `core.worktree` redirect — the isolation
  worktree resolved to a path outside itself, so the harness refused to run
  there. **The fresh-worktree green remains UNESTABLISHED.** Re-running
  separately. (Landmine map already warns: the live repo's green depends on
  accumulated on-disk history.)
- **GAP-5 (post-commit DoD re-run + independent review of commit
  `8f27a326`): FAILED, no findings.** Died on a StructuredOutput retry cap —
  **a schema defect in the orchestration, not a repo problem.** The
  post-commit DoD matrix for that commit remains **UNRUN**. Re-running
  separately.

**Coverage the wave never had:**
- **26 of 33 modules in `execution/` + `ml/` were NEVER OPENED.** Not read at
  any depth: `ml/history.py` (**3,052 lines** — the corpus/labeling path),
  `ml/overfit.py` (1,188), `ml/models.py` (969), plus labeling, postmortem,
  walkforward, features, linkage, corpus, interpret, event_sampler,
  foundational_confidence, money_sense, retrain_log; and `execution/` algos,
  fair_value, fix_codec, grid_ladder, hedging, inventory, market_maker,
  markout, routing, tactics, venue_adapters. **A clean result there is NOT
  established — it was not looked at.** Highest-value next slice:
  **`ml/history.py` + `ml/labeling.py`**, where a fail-open corrupts the
  **TRAINING SET** rather than one order.
- **Replay/recording book path UNTRACED.** PT-B1/PT-B2 are called
  "unreachable in production" behind exactly ONE upstream `clean_book`, but
  the replay/recording drivers and the `scripts/` harnesses that build a
  `LiquidityBot` with injected feeds were never traced. **A replay recording
  carrying an unsanitized book RE-OPENS both findings inside the measurement
  plane.**
- **No mutation testing of `tests/`.** Established: shipped code takes the
  permissive branch. **NOT established: that these are untested paths.**
- **MLSEC-2 downstream checked at ONE hop only** (`risk/position_sizer.py:425`
  rejects the NaN). What the engine does with a sizer returning zero size
  every cycle is **[I] INFERRED, not measured**.
- **`_tail_link` concurrent-writer fork UNTESTED** — its own docstring flags
  the hazard.
- **`exec_era` stamp correctness NEVER verified against the binary that
  granted each fill** — only self-consistency. `cohort_eval`'s homogeneity
  section reports **5/72 trips with a STALE-BINARY leg**, so the stamp HAS
  failed before.

**OPERATOR DECISIONS OWED:**
- ~~**Grafana root route.**~~ **EXECUTED 2026-08-31 under operator "Go"** —
  root receiver repointed `empty` → `grafana-default-email` (PUT
  /api/v1/provisioning/policies, HTTP 202, independent GET confirms;
  group_by preserved). **The rule-#5 trap is DISARMED.** Contact point stays
  `provenance: "api"` (UI-locked, API-editable). An adversarial review of
  the operator-decision handoff had found this item was within
  already-exercised authority (same class as the 2026-08-30 rule PUTs) —
  the "Go" confirmed it.
- **Era-6 straddler membership.** **4** trips under stamp-purity AND under
  entry-time (these two are **SET-EQUAL, not merely count-equal**); **7**
  under any-leg AND under close-time. The moratorium's "accrual begins at the
  cut #9 restart, from zero" most directly implies **4**. Operator owns the
  call.

**METHOD NOTE (cost measured this session).** Every lane's injection harness
lived in a session-scoped scratchpad and was **GONE** when the verifier
needed it, forcing a full rewrite from `file:line` citations. **If a claim is
worth docketing, its harness is worth a durable path** — otherwise every
verification is paid for twice.

---

## RECENTLY SETTLED — do not re-litigate, do not re-implement

| what | verdict | record |
|---|---|---|
| `.claude/settings.json` edit flagged UNATTRIBUTED (08-30) | **ATTRIBUTED — owned by the main session, intentional, do NOT revert.** It removed the ORPHAN MCP permission rule `mcp__bf7c680d-5fdc-5ef4-b4a0-abadb619bf0a__list_triggers` after verifying **0 occurrences** of that UUID across `~/.claude.json`, `~/.claude/settings.json`, `.claude/settings.local.json` and `.mcp.json` — i.e. no server config anywhere binds it. Re-parsed after the edit: **PARSE OK, 9 allow entries, `enabledPlugins` preserved**. Rationale: MCP permission rules match on the **name string alone**, with no binding to a server config, so an orphan allow entry is a **standing pre-approval for any tool later registered under that ID**; removing it strictly **NARROWS** permissions. Recorded here so the diff does not read as unowned | this row; re-derive with `git log -p -- .claude/settings.json` |
| General update pass + data-pull determinism/usefulness audit (08-30, post cut-9) | **DoD matrix full green on `9fdbc389` (clean tree, no code changes this pass — Grafana alert-plane + docs only):** pytest 4422 passed/10 skipped/2 xfailed (563.37s) · smoke_test 220/0 · assurance_check 51/0 (corpus 20,728 rows) · overfit_check passed 3/0 (corpus **live history 10,359 rows**, real not synthetic; OF-4 plateau INERT — flat surface, 0 entries on the replay recording; OF-5 DSR DEFERRED — 26 conviction trades < 30 floor) · ruff clean on the exact CLAUDE.md scope · pyright 0/0/0 on the exact CLAUDE.md scope · bandit 0 issues (61,993 LOC, 66 nosec-skipped) · compileall clean. All 8 gates green, numbers match the cut-9 settlement row exactly (4422/220/51/3), confirming no drift since. **Data-pull audit** (Kraken/OKX/Binance.US/ccxt/moomoo/webdata/ws_feed/context_engine/candle_journal, all 8 live ingestion modules read): no determinism defects found beyond 2 pre-existing minor ones (both BOUNDARY-classed below, DATA-1/DATA-2 — they'd change ML feature values if fixed); no wasted-fetch/unused-field findings (every fetched field grep-verified consumed downstream) | this row; DoD outputs captured this session (not persisted — re-derive per CLAUDE.md's own "a number written into law decays" rule) |
| ALERT-DRIFT + a bigger delivery defect found underneath it (08-30) | **FIXED, both halves.** (1) Cloud/repo drift closed both directions: `lb-drift-stuck` + `lb-brier-degraded` PROVISIONED live (POST 201, folderUID `liquiditybot-ops`, group `liquiditybot-ml`, interval 60s — verified via `/api/prometheus/grafana/api/v1/rules`, all 4 rules now present); `lb-manip-high` (live since 2026-07-14, never mirrored) exported to `docs/grafana/liquiditybot_manip_alert.yaml`. (2) **Read-only GET surfaced a live defect nobody had closed**: both pre-existing rules (`lb-telemetry-stale`, `lb-manip-high`) had `notification_settings: null` since creation (2026-07-14) and the root notification policy receiver is `"empty"` (zero integrations, confirmed via `/api/v1/provisioning/policies`) — **any firing since 2026-07-14 paged nobody** (the repo's own `liquiditybot_deadman_alert.yaml` had already found and dated this 2026-08-17 as "MANUAL-APPLY", never applied). Fixed by the documented read-modify-write PUT (`notification_settings.receiver = grafana-default-email`) on both rules, verified live via GET after the PUT; the two new rules were provisioned with the setting attached from creation so they never carry the defect. Root policy receiver is still `"empty"`, untouched (smaller blast radius: per-rule override, not a policy-tree change). All 4 YAML files in `docs/grafana/` updated to record what's live and when | this row; `docs/grafana/liquiditybot_deadman_alert.yaml`, `liquiditybot_drift_alert.yaml`, `liquiditybot_brier_alert.yaml`, `liquiditybot_manip_alert.yaml` (new); read/write timestamps 2026-08-30T22:0x — re-derive via `GET /api/v1/provisioning/alert-rules/<uid>` |
| `turbulence_pct` decay + crisis-book reopen (08-30) | **RESOLVED — it decayed, the book is open.** Live read: `turbulence_pct` = 16.0 (fraction 0.16, well under the 0.95/p95 crisis line), fresh (`computed_at` 21:32:49Z, `stale`=False, `sample_count`=250 — not a held/stale reading). `status.regimes` shows 0/12 assets in `crisis` (range/bull_quiet/bear/bull_volatile instead), vs the 08-22 all-12-crisis reading. Historical N is now 2 (episode 1 ended, this is the second observed decay) | this row; `outputs/status.json.correlation` (read 2026-08-30T22:07:56Z) |
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
