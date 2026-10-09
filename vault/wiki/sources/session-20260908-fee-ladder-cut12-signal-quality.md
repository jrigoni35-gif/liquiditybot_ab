---
title: Session 2026-09-08 — the fee ladder was the legacy one; cut #12 (FEE-4, era-9); the skills scout; the signal-quality battery
type: source
status: IN PROGRESS at filing — §5 and §6 fill when the background workflows return; every number here is as-of and re-derivable from the named artifact
---

# 0. Where this session started

Era-8 (cut #11, the COMMIT configuration) one day old; a morning watch
read the heat cap as binding the accrual rate ("34/34 vetoes since 02h";
operator: *"I'll just wait it out"*) — corrected at 23:38Z: those were the
LONG BOOK's hourly add denials, the 5 m book placed 3 entries that day (§4
and the-method rule (b′)); the beta/alpha attribution filed the day before
([[sources/session-20260905-06-verification-and-cut10]] §7,
[[concepts/treynor-black-alpha-isolation]]).

# 1. The skills scout — nothing installed, on evidence

Operator: *"Look up any good crypto skills that would help you."* 11
sources, 13-agent workflow (judge + refuter) + 12 direct raw fetches. Every
INSTALL verdict refuted on re-read: kraken-cli's read-only `-s market` MCP
is real (10 tools, 0 dangerous) but the README default is `-s all` and its
skills summarize fetchable canonical docs; agiprolabs duplicates the vault's
Avellaneda–Stoikov page and `overfit_check.py`; ccxt read-only already in
the venv at zero toll; the best quant-vocabulary skill 404s on its own
scripts. Gaps NO skill fills: MinTRL/MinBTL, n_eff deflation, cluster-robust
inference, mutation/injection. Harvested: the canonical Kraken rate-limit
URLs (our feed uses a flat bucket, not the counter/decay model), the quant
vocabulary, the-method #12 consequence (e). Raw:
`raw/research/2026-09-08_crypto_skills_scout.md`.

# 2. The fee ladder was the legacy one — [[concepts/the-method]] #13

A vendor skill's "0.16/0.26 starter" matched nothing → the venue's fee page
read as RAW TEXT (2026-09-08T20:15:29Z): Tier 1 40/80 · Tier 2 30/60 at
$2.5K · **Tier 3 22/38 at $10K or $20k AoP** · **Tier 4 20/35 at $25K or
$50k AoP** · Tier 5 15/30 at $50K/$100k … 0/5 at $500M, tier = best of
30-day volume OR assets on platform. `core/venue_fees.py` (09-05) had read
the LEGACY ladder (25/40, 20/35 at $10k, 14/24 …) from `/0/public/AssetPairs`
— which by 09-08 returns `fees: []`. Cut #10's E1 (22/38 → 20/35) was
booked on that module's word; cut #9's 22/38 from the app was right; my own
09-07 caveat invented a "25/40 below $10k" row. Instrument corrected the
same session (ladder + AoP, caption-anchored page parser, browser UA — the
page 403s Python's default — two-route drift report, derived guard WARN and
fallback, 5 false comments dated and corrected; 23 pins, mutation 7/7 red;
guard sweep identical). Commit `7971ab4b`. Record
`docs/quant/2026-09-08_fee_ladder_correction.md`.

# 3. The operator's reading — and the bias flips

Kraken app 17:51 (device time): **Tier 5, 30-day spot $69,652.65, AoP
$822.24** (`raw/quant/2026-09-08_kraken_fee_tier_reading.md` + screenshot).
`binding_row(69652.65, aop_usd=822.24)` → 15/30; the app's next-tier
distances (30,348.35 volume / 199,178.76 AoP) reproduce from the table to
the cent — third route, AoP column confirmed. So the booked 20/35
OVER-states the round trip by 10 bps (22.2%), $0.06 per $60 ticket; the
era-8 readout was conservative, not optimistic. The tier ROLLS on the
operator's real trading (×4 since 08-29). Commit `68586af0`
(`fee_drift_report --aop-usd`).

# 4. Cut #12 — FEE-4, era-9 (operator: "Re-book now … Yes do a reset")

Record committed alone as **`10d4d0c2`** = `EXEC_ERA "12-10d4d0c2"`.
`scripts/cut12_stage.py --apply`: pretrade/order_manager 20/35 → **15/30**,
`est_fee_bps` 35 → **30**, `label_round_trip_cost_pct` 0.55 → **0.45**;
derived entry bar 0.6642 → **0.6381**; guard 0 FATAL / 3 WARN (pre-existing).
Stage refuses unless `binding_row` at the reading equals the staged row, on
any FROM drift, and (after the review) on an incoherent cascade. No other
KEY moved (universe, hedger OFF, skimmer OFF, $60 floor, budget, time-stop,
give-back, model, heat cap 0.35) — **but the barrier geometry moves with
the cost by construction**: `barrier_geometry` floors σ at
`pt_cost_mult·cost/pt_mult`, so label PT 220 → 180 bps, SL 165 → 135 at
σ_bar 0.10%, the live bracket likewise, BE/trail floor 76 → 66 bps, under
the same `label_era` — the cut-#9/#10 shape, said this time. The
adversarial review of the diff (BLOCK → fixed the same session) also caught
era-8 counts RECALLED from the morning watch: re-derived at staging (ledger
+ `cohort_eval`, two routes) era-8 holds 4 entries and 1 closed trip, with
the closing count deferred to `cohort_eval` at the restart; a `p_bar`
fixture re-baselined (0.183 → 0.209); `main()` refusal paths pinned; a
config_guard FATAL for a label cost below the booked round trip (the
half-applied-stage hazard). Pins 11, mutation red. **Go-live came early,
by load, not by the procedure:** `pc_supervisor` relaunched the runner at
23:41Z ("runner stale/absent" — the old runner's `status.json` heartbeat
exceeded STALE_SEC 120 s under the DoD + two workflows' agents), the
relaunch booted from the applied working tree and printed `fees=15/30bps`
at 23:47:45Z; the second spawn backed off; the old runner exited on the
forfeited lock. Era-8 FINAL: 4 entries, 1 closed trip. Lesson to memory
`era-cut-procedure` #7 (run the battery at below-normal priority; never
beside agent fan-outs). The final DoD ran at BelowNormal; a deliberate
restart on the merged commit followed;
world-stamp pins moved (provenance, cut11 fee literal → published-row
check, boundary5 layered TO map cut10→11→12, exit-policy 35 → 30). CLAUDE.md
moratorium → era-9; HANDOFF ERA-9 header; FEE-4 marked ADOPTED with its
standing rule: **book the tier from a fresh reading at the boundary that
adopts it; re-read at every readout; never chase mid-era.** DoD running on
branch `cut12`; live only after merge + runner restart verified from the
boot line `fees=15/30bps`.

# 5. The signal-quality battery (operator: "run number theories … see what happens when quality of signals are focused on"; approved beyond read-only)

`wf_b11a8349-ceb`: prior-art inventory → T1 IC/ICIR/Fundamental Law ·
T2 resolution-vs-direction · T3 stationarity/PSI/IC half-life · T4
redundancy/effective breadth · T5 mutual information with block nulls ·
T6 champion calibration (Brier/Murphy) + overfit battery ARMED count · T7
the quality-focus walk-forward experiment (confidence deciles, feature
agreement, IC-weighted composite, regime filters; thresholds on the first
60% of days, evaluated on the last 40%; trial counts named; MinBTL/DSR) ·
T8 cost/geometry at 15/30 → judge → three refuters (look-ahead,
multiplicity/power, instrument-first). **Results** (record
`docs/quant/2026-09-08_signal_quality_battery.md`): a measured null on
skill — 0/63 features survive BH for direction, the two survivors are
anti-predictive; the champion out of sample is at its base rate to within
the resolution (Brier skill +0.002 [−0.026, +0.017]; AUC 0.553, MDE80
0.60); what looks like skill is the long side (0.545 vs 0.286) — beta;
**focusing on quality does nothing**: 27 pre-registered walk-forward rules,
baseline −42 bps/trip @15/30 [−73, −13], 0 BH survivors, the one positive
cell loses to plain long-only; on the ledger the highest-confidence probes
are the worst (−108). The fee row moves every number +10 bps and no verdict.
**The finding both refuters made and no task named: the stale-entry
anchor** — the labeler enters at close[k] of the last committed bar while
the decision and every live-book feature are taken ~150 s later (audit
phase uniform, n=25,055); live rows show a side-signed +3 bps mean / 18.9
bps sd head start (~45% of a bar's variance realised at decision); it
flatters the two "reversal" survivors and every gross level, not the null.
Fixing it is model-side (frozen, cohort-resetting); the SAFE precursor
(log the registration wall-clock) and a re-mint at the decision-time price
are docketed. Also docketed: `sent_dir` as the ONE pre-registered test;
the `regime_*` dummy trap (VIF ∞) regularisation check; ML-031's
unreproducible live alarm. The signal-quality gate is STRUCK as a boundary
candidate.

# 6. config.json debug (operator: "look over my json file and debug and mutate it based on any new findings")

`wf_74b30a86-ba5` (4 lenses, 64 findings, judge): **no VALUE in
config.json needs to move** — guard 0 FATAL / 3 known WARN, the six fee
keys agree, derived bar 0.6381, probe p 0.85 clears it. Signed into the
record: the fee re-book IS a TP/SL change via the cost floor (§4). SAFE
batch riding cut #12: ~25 stale `_doc` strings (8h/7-pair/40-80 era;
volatile literals → dated pointers), hedger/skimmer "OFF since cut #11"
notes, a `_dead_keys_doc` for 11 unread keys (no deletions), and the
absent-key FATAL list extended for six keys that would boot silently if
deleted (label cost, fill simulator, min ticket, size_scale, hedger switch,
engine). **Surfaced: the LONG BOOK** (`long_book.enabled`, BTC/ETH
accumulation, 12% thesis stops, tiers +8/15/25/40%, no time stop) runs
inside era-9 holding 2 of 5 slots and ~$78 heat, attempting an add every
hour that the heat cap denies — it was in no cut's "untouched" list; its
exits run in the general exit loop (`enabled` gates adds only), and the
ledger's blank `book` column means `cohort_eval` would pool its trips. Parked
for the operator (all cohort-resetting, none recommended now): long book
on/off or explicit accounting; fixed $60 ticket vs Kelly-sized probes
($67–86 observed at p_win 0.85); CVaR horizon 24 vs 432 bars; stale-purge
36 h vs time-stop race; the funding gate's unit (structurally unreachable);
quoter floor 26. Judge output: `outputs/reports/config_debug_2026-09-08/`
(scratch), `scratchpad/config_debug.json`.

# 7. Queued (operator: "use any other tools or skills … add pandas … mutate this code to be more solid")

After merge: adversarial review of the cut diff (running), then a
hardening workflow over the new measurement modules (venue_fees parser,
beta_alpha tool, cut12 stage, drift report): pandas/pyarrow-backed loaders
with schema checks, typed inputs, property-style pins, mutation sweeps;
data-quality-auditor over the corpora; statistical-analyst over the study's
methods. The venv has pandas 3.0.5, numpy 2.5.1, pyarrow 24, polars 1.44,
numba 0.67; NOT scipy, statsmodels, sklearn, hypothesis, pydantic.
