# Signal-quality battery — "run the number theories on the features, and see what happens when quality is focused on" (2026-09-08/09)

**Class:** measurement, SAFE (nothing in the bot changed). **Operator ask,
verbatim:** *"do a run of number theories (all that matter or apply) for the
features my bot is executing its trade decisions from and see what happens
when quality of signals are focused on"*; then *"I approve it to be a deeper
dive then read only."* **Method:** workflow `wf_b11a8349-ceb` — prior-art
inventory (repo + vault) → eight theory batteries, each with a planted-defect
self-test → judge → three refuters (multiplicity/power, instrument-first,
look-ahead/leakage). 14 agents, 519 tool uses. Scratch and per-theory
reports: `outputs/reports/signal_quality_2026-09-08/` (gitignored); judge and
refuter JSON in the session scratchpad. **Corpus (as-of the tasks' read,
2026-09-08T23:07:17Z):** `outputs/signal_history.csv` era
`triple_barrier_h432`, **17,057 rows**, signal_ts 2026-08-09..09-08, 31
signal-day blocks (n_eff 23.5) / 28 ts-day blocks; barriers tb_pt 6,483 /
tb_sl 7,741 / tb_time 2,833; 64 features (`ml/features.py:117-146`); champion
`outputs/meta_model.json` (logistic, 64 weights, isotonic calibration,
trained on 6,729 rows). The live file grew during the study (17,133 era rows
by 00:06Z); every number is as-of.

## 1. What survives the refuters

| claim | evidence | what the refuters changed |
|---|---|---|
| **No deployed feature carries direction skill that survives multiplicity.** | T1: 0 of 63 BH survivors; largest `direction` IC 0.139 [−0.027, +0.305]. T2: 8–9 nominal flags vs 6.4 expected by chance; the two BH survivors (`fv_edge_bps` DIR AUC 0.469, `basis_dir` 0.465) are anti-predictive. T3: 0/63 on the continuous net target. T5: strict form leaves none. Five independent scripts agree. | The NULL stands; the STRENGTH is cut: the power floor is not "|IC| 0.03" (one planted draw on another target) — per-route MDE80 is ~0.05–0.09 at BH-63, so "no measured skill" means "none above that". |
| **The champion out of sample equals its base rate.** | T6 on 10,260 unseen rows, 15 day-blocks: Brier 0.2436 vs oracle 0.2442, skill **+0.0022 [−0.026, +0.017]**; AUC **0.553 [0.484, 0.623]**, exact per-day sign-flip p 0.107; Murphy resolution 1% of uncertainty; top decile 0.473 below the 0.571 cost-floor break-even. In-sample the same artifact reads AUC 0.763 — memorization the isotonic compresses back. | "Equals" over-reads: at 15 blocks the test only detects AUC ≥ 0.60; the honest sentence is "below the instrument's resolution". The split was not a clean 36 h-embargoed deploy cut (the loader is signal_ts-sorted; the champion's exact training set is not locatable — `outputs/models/registry.jsonl` not read). |
| **What looks like skill is trade SIDE.** | Longs hit the profit barrier at 0.545 vs shorts 0.286; the champion's OOS direction AUC 0.582 falls to 0.519 [0.454, 0.587] once side is stratified out (T2). `direction` is the largest weight (+0.568). | Side's DIR AUC 0.618 [0.542, 0.696] DOES exclude 0.5 — it is a real dependence, era beta on a 66%-long book (the 09-07 attribution's finding restated), not period noise as the judge first wrote. |
| **Focusing entries on signal quality does not move net from zero.** | T7, 27 pre-registered walk-forward rules (thresholds on the first 18 days, tested on 12; 8,423 test rows): baseline **−42.3 bps/trip @15/30 [−72.6, −12.8]** (−52.3 @20/35); 23/25 rules negative at 15/30; BH survivors 0 (min p 0.056); DSR of the best rule 0.41; the one positive cell (refit-p top decile, **+14.8 [−55, +103]**, p 0.75, 326 rows, n_eff 4.5, 326/326 long, 79% of rows on three days) underperforms a plain long-only control on the same days (+31.6). Real ledger: lifetime 344 trips net @15/30 [−66, −28]; OOS (opened ≥ 08-27) 47 trips **−114.8 [−159.6, −78.1]**; the forced p_win ≥ 0.75 probes are the WORST subset (−107.8 [−150, −65]). Mutation: a planted +N(0,sd) quality proxy fires (+246 [211, 292]). | Arithmetic reproduced to the second decimal on an independent parse. Strength cut to "no edge ≥ ~60–100 bps" — on n_eff < 10 subsets a true +10 bps rule is invisible. DSR's variance is over nested rules (robust 0.41–0.48 for N 3–27); MinBTL shortfall 84×, not 125×. |
| **The fee row 15/30 vs 20/35 shifts every net figure +10 bps and changes no verdict.** | T8: break-even band [0.4286, 0.5714] is fee-invariant by construction; corpus break-even 0.5644 → 0.5600 vs base rate 0.4561; cost-floor TP 220 → 180 bps; the derived entry bar 0.6642 → 0.6381 crosses the champion's calibrated ceiling 0.6496 and admits 7 of 16,989 rows (2 events). | Stands (closed form). |
| Features are not redundant; the five `regime_*` one-hots are an exact dummy trap. | T4: ~37 independent dimensions of 63 (PR 37.1; 4 pairs at |ρ| ≥ 0.7); `regime_*` row-sum = 1 on 17,057/17,057, VIF ∞, condition number 2e16, fed to a logistic with an intercept. | Stands (identity). Whether the champion's regularisation neutralises the trap: UNKNOWN. |
| Era h432 pools four cost-floor barrier geometries (cost 0.50/1.20/0.60/0.55 by label-close day); a fifth (0.45) began 09-08. | Exact residual identity on 10,044/10,049 rows. | Stands; the cut-#12 geometry point again. |

Refuted as stated: "≈75 independent bets/yr" (day-block n_eff on trips is
bounded by the 44 entry-days — it measures calendar concentration, not
independent bets; the three breadth routes disagree 10×); "sent_dir's
interval touches zero on every route" (two uncorrected intervals exclude
zero: FM FWD_432 [−0.293, −0.008], pooled [−0.43, −0.03]; multiplicity kills
it, not the CI); "the zeros are measured zeros" (planted defects prove the
scans are not broken; only an MDE proves a zero, and none was reported per
route).

## 2. The finding no task named, both refuters found — the stale-entry anchor

The label engine enters every candidate at **close[k] of the last COMMITTED
bar** (`ml/history.py:2652-2658 entry_price = closes[i]`, `ml/labeling.py:455`)
while the decision — and every live-book feature (`basis_dir`, `fv_edge_bps`,
`ofi_dir`, `imbalance_*`, `spread_bps`, `depth_*`) — is taken ~150–160 s
later inside bar k+1 (audit decision-event phase uniform: SZ-051 n=25,055
mean 149.9 s; candle refresh 150 s; forming bar dropped). Measured on the
live rows (`fills.arrival_ref` = decision-time price): the gap is
side-signed, **mean +3.0 bps, sd 18.9 bps — ~45% of a 5-min bar's variance is
already realised at decision.** Consequences: the first bar's return has DIR
AUC 0.568 [0.554, 0.580] against the 36 h label (a head start from a price
the bot could not have traded at); `fv_edge_bps`'s BH survival vanishes when
it is partialled out (0.471 → 0.506) and `basis_dir`'s nearly so (0.459 →
0.482) — the "bar-(k+1) microstructure reversal" the judge described is the
anchor lag, not a market mechanism; every gross/net level from candidate
rows is an upper bound on TWO counts (touch-fill AND stale entry); the
champion's in-sample fit is inflated by the same artefact. Re-anchoring the
label one bar later moves NO feature toward positive skill (direction 0.6065
→ 0.6030), so the null on skill is unaffected — the leak flatters the two
anti-predictive survivors and the levels, not the verdict. Barrier touches
inside the decision bar are 0.27% of resolved rows: the leak is the price
anchor, not the scan. Also mechanical: `spread_bps` enters the label's cost
and barrier width (`history.py:2582-2586`), so its RESOLUTION AUC 0.676 is
partly construction.

**Class:** a fill-simulator / labeler property — changing it is
COHORT-RESETTING (model-side, frozen). **SAFE precursor, docketed:** log the
registration wall-clock per candidate so the true decision instant is
recorded; then re-mint labels at the decision-time price (the tick tape
covers 10,611 of 11,718 anchored rows to 09-02) and re-run T1/T2/T6 as the
second route.

## 3. Answer to the operator, plain

Every theory that applies was run, each one checked against a planted fake
defect first. None finds a feature the bot trades from that predicts
direction better than chance once you count the tests run; the model, out of
sample, is at its base rate to within what 15 days can resolve; what looks
like skill is the long side doing better than the short side in this era —
the market, as the attribution said. Focusing on "high-quality" signals — by
model confidence, by feature agreement, by an information-weighted composite,
by regime — does not move net per trade away from zero at either fee row; the
only positive cell is three days of longs and loses to just being long. On
the real ledger the highest-confidence trades are the worst. The one thing
the battery turned up that changes future work is a timing flaw in how labels
are made: the label enters at a price ~2½ minutes older than the decision,
which flatters two "reversal" features and every gross figure by a few basis
points. Fixing it is a model-side boundary; measuring it fully is the next
step.

## 4. Docket (nothing applied; each names its authority)

1. **Stale-entry anchor** (§2) — SAFE precursor: registration wall-clock
   per candidate; then re-mint at the decision-time price and re-measure.
   Fixing the labeler/fill-simulator entry: COHORT-RESETTING, model-side.
2. **`sent_dir` at the 36 h horizon** — contrarian, uncorrected intervals
   exclude zero, killed by multiplicity: the ONE pre-registered test worth
   running on the next fresh window (2–3-day blocks, precision-weighted
   Fama–MacBeth), not a finding.
3. **`regime_*` dummy trap** — SAFE measurement: does the deployed
   logistic's regularisation make the trap inert; if not, it is a model
   change (frozen).
4. **Take-profit width** — pre-named lever; T8 restates the floor at
   180 bps (15/30), 36 h median oracle move 99–241 bps.
5. **ML-031 live drift alarm (18–26/60 hourly) not reproducible on any
   history slice** (0/56 contiguous blocks; `_feat_buffer` not persisted) —
   the instrument is the first suspect; owed: persist the buffer or log
   the deciles it compares against.
6. **Signal-quality gate:** NOT a boundary candidate — the evidence says
   it would remove trades without changing the sign. Struck from the
   docket.

## 5. What the battery could not see

One era, 31 days, one regime; candidate rows are decisions, not fills (42–55
live rows) — no slippage, partials, queue position or exits are measured;
the champion's own probability on traded rows is unobservable (every live
entry is a forced-p probe); resolution ±60–100 bps on n_eff < 10 subsets;
alt-coin candle lanes end 09-01/02; Fama–MacBeth equal-weights days of
7–862 rows (a precision-weighted FM was not run and is the honest arbiter
between the T1 and T2/T3 routes); block phase moves the exact p 0.09 → 0.32
at ≤ 8 two-day blocks; the era-8/9 read points are untouched by anything
here. Not run: `signal_factory --self-test`, `champion_skill_report`,
`quant_trials`, the 108/216-bar shadow horizons, the `sg_*` gate components.
