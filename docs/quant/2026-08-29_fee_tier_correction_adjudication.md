# Fee-tier correction — operator adjudication

**Date:** 2026-08-29
**Class:** the config change is **COHORT-RESETTING** (reverses/supersedes
cut #8; mints a new execution era; restarts accrual). **This document, the
re-derivation, the walk-forward re-run, and the re-pricing are SAFE.** No
config was touched producing it.
**Authority to act:** OPERATOR ONLY. This doc produces the analysis and a
recommendation; it does not ship a config edit.
**Re-derive with:** `./.venv/Scripts/python.exe scripts/fee_tier_rederive.py`
(entry bar / b_net / give-back buffer, both fee schedules, two routes).

---

## 0. TL;DR

- **The account is Kraken Tier 3 (maker 0.22% / taker 0.38% = 22/38 bps).**
  The live config books **40/80 bps** (assumed Tier-1). Config **over-states
  the venue-true fee by ~2x.**
- This is a textbook **the-method #1 recurrence** — "a struck fee schedule
  asserting itself the conservative check." Cut #8 (2026-08-28) wrote 40/80
  as "venue-true" without ever reading the account's actual tier row
  (OM-080 fee-recon has fired **n=0** — no live credentials).
- **Correcting the fee collapses the derived entry bar 0.8335 -> 0.6772**
  (double-derived, both routes agree). At 40/80 the bar sits ABOVE the
  entire live model-confidence band (0.60–0.77) — conviction entries stop by
  construction. At real 22/38 the bar falls back INSIDE the band; conviction
  entries resume.
- **BUT the founding hypothesis — "the fee error manufactured COST_BOUND" —
  is REFUTED on the completed cohort.** It was arithmetically true only
  against a stale n=33 melt-up snapshot (gross tolerance +118 bps). On the
  completed era-4 cohort (n=61) the gross edge decayed to **+41.3 bps**, so
  real ~60 bps fees still yield a **negative net point estimate**. The fee
  fix moves the POINT estimate across the old line; it does not change the
  **readout class** (COST-BOUND holds at both 120 bps and 60 bps), and it
  does not move the confidence interval across zero.
- **Honest sign: UNDETERMINED, leaning NEGATIVE at the point estimate.**
  Correcting the fee removes a *confidently-negative* config artifact; it
  does not deliver a *confidently-positive* strategy.

---

## 1. THE FINDING — account is Tier 3, config is Tier 1

**Ground truth** (operator's Kraken app screenshot, 2026-08-29 14:58): the
account is **Tier 3 = maker 0.22% / taker 0.38%**, on **$17,482.46** 30-day
spot volume. Kraken's published spot ladder (maker/taker | min 30d spot vol):

| tier | maker/taker | min 30d spot vol |
|---|---|---|
| T1 | 0.40 / 0.80 | — |
| T2 | 0.30 / 0.60 | 2,501 |
| **T3 (CURRENT)** | **0.22 / 0.38** | **10,001** |
| T4 | 0.20 / 0.35 | 25,001 |
| … | … | … |

Next tier (T4) needs +$7,518.54 more 30d volume. [K, operator screenshot
2026-08-29 14:58]

**The defect.** Cut #8 (2026-08-28) set `pretrade.*_fee_bps` and
`order_manager.*_fee_bps` to **40/80** as "venue-true Kraken Tier-1," set
`ml.label_round_trip_cost_pct = 1.2`, and derived the entry bar 0.8335. The
real account pays **22/38**. The config over-states fees ~2x. Live config at
`config.json@c1882728` read 2026-08-29 15:05 CDT confirms pretrade 40/80,
order_manager 40/80, `pretrade.allow_sub_floor_fees` unset (False),
`position_sizer.p_bar_mode = derived`, `p_bar_edge_margin = 0.0`,
`ml.label_round_trip_cost_pct = 1.2`, `ml.label_pt_cost_mult = 4.0`,
`ml.exploration.p_win = 0.85`. [K]

**Why this is a the-method #1 recurrence.** The decision path is the
most-governed code in the repo; the measurement plane that anchors its costs
is the least-governed. Cut #8's cost anchor was set from Kraken's *published*
schedule (the highest, min-volume tier), never from the account's *verified*
tier row — and both the decision side (`pretrade`) and the booking side
(`order_manager`) read the SAME understated-then-overstated constant, so the
loop cannot self-detect it (`docs/quant/2026-08-22_loop_alignment_audit.md`).
The struck schedule asserted itself as "the conservative check."

**Cross-checks that the 40/80 assumption was never account-verified:**

- **Booked median round-trip ~65 bps** (fee_anatomy §2 booked median RT
  65.4 bps; pre-cut config 25/40). That is ~real Tier-3 (60 bps), NOT
  config Tier-1 (120 bps). [K]
- **OM-080 fee reconciliation has fired n=0.** `data/kraken_feed.py:376`
  `get_trade_volume()` and `execution/order_manager.py` `check_fee_
  reconciliation` (OM_FEE_RECON_MISMATCH, default enabled, 24h interval,
  1 bps tolerance) *exist and are report-only by design* — but never ran,
  because there are no live Kraken credentials, so `TradeVolume` was never
  called. The n=0 was the unheeded warning that 40/80 was unverified.
  (`TradeVolume` is deliberately OFF the withdrawal deny-list.) [K,
  `scripts/cost_truth_report.py:337`]

---

## 2. THE CASCADE — every fee-dependent decision number, 40/80 -> 22/38

Round-trip cost: config **1.20%** (40+80) -> real **0.60%** (22+38).
All numbers double-derived; the entry bar reproduced by both the shipped
`PositionSizer` object and a hand recompute (`fee_tier_rederive.py`, agree=True).

| quantity | config 40/80 (rt 1.20%) | real 22/38 (rt 0.60%) | source |
|---|---|---|---|
| **derived entry bar** `p_bar_base` | **0.8335** | **0.6772** | position_sizer.py:191-193; helper R1==R2 [K] |
| `b_net` (payoff ratio net of fees) | 0.1998 | 0.4766 | position_sizer.py:162-165 [K] |
| `b` (gross payoff ratio) | 0.9196 | 0.9196 (fee-invariant) | [K] |
| label round-trip cost | 1.20% | 0.60% | config `ml.label_round_trip_cost_pct` [K] |
| barrier target (4.0× cost) | 4.80% | 2.40% | `ml.label_pt_cost_mult=4.0` [K] |
| give-back buffer `be_buffer + 2·est_fee` | 166 bps | 82 bps | config_guard.py:2373-2378 [K] |
| PT-041 EV-gate fee leg | 40/80 | 22/38 (halved) | config_guard.py:631-636 [K] |

**Headline — the entry bar collapses 0.8335 -> 0.6772.** The 40/80 cut
raised the required p(win) so far it exceeds the ENTIRE live model-confidence
band (0.60–0.77 per `docs/quant/2026-08-25_boundary5_adjudication.md`
consequence #1 [I]), i.e. conviction entries stop and the book becomes
probe-only. At real 22/38 the bar (0.6772) falls back INSIDE the band, so the
top of the confidence distribution clears and **conviction entries resume**.
Note the real bar (0.6772) is even BELOW the pre-cut 0.690, because real taker
38 < pre-cut config taker 40. [K, `fee_tier_rederive.py`]

**Label geometry (COHORT-RESETTING).** `label_round_trip_cost_pct` 1.2 -> 0.6,
and because `label_pt_cost_mult=4.0` floors the barrier target at 4× cost, the
labeled/traded profit target is inflated **4.8% -> 2.4%** at real fees. This
changes both the label geometry the retrain loop trains on and the live
bracket engine's target — the shared `barrier_geometry()` helper. Note
config_guard's label-cost WARN compares the label round-trip against 2·maker:
at config maker 40 that is 0.80% (silent, though 1.2% > 0.80%); at real maker
22 that is 0.44%, and a corrected 0.60% label round-trip still exceeds 0.44%,
so a truthful 0.60% label cost stays clean. [K, config_guard.py:674-680,
:716-724]

**Give-back / GB-1 shrinks but does not dissolve.** `profit_taking.est_fee_bps`
80 -> 38 halves the give-back arm-vs-breakeven buffer **166 bps -> 82 bps**.
The config_guard WARN (arm_gain 0.6% = 60 bps arms INSIDE the buffer) **still
fires at real fees** (60 <= 82), so GB-1 stays a legitimate docket item — the
buffer just goes from "arm at 36% of buffer" to "arm at 73% of buffer." [K,
config_guard.py:2373-2378; helper confirms WARN=True at both schedules]

**PT-041 EV gate.** `min_edge_cost_ratio` (1.3) is UNCHANGED; the fee leg of
the cost stack halves, so more signals clear net-EV without weakening the bar.
`exploration.p_win` (0.85, raised by cut #8 specifically to clear the 0.8335
net-Kelly breakeven) stays clean at real fees (0.85 >> 0.6772, no FATAL) — it
is now a benign over-margin (headroom 0.173 vs 0.017 at the config breakeven).
[K, config_guard.py:3371-3394]

**The KRAKEN_SPOT_FLOOR must NOT move.** `core/config_guard.py`
KRAKEN_SPOT_FLOOR (40/80) is Kraken's published Tier-1 (highest-fee,
min-volume) — the "you're understating unless you have volume discounts"
tripwire. No spot account pays MORE than it. The truthful real-tier config
(22/38) legitimately sits BELOW the floor and therefore **REQUIRES
`pretrade.allow_sub_floor_fees=true`** as a companion edit, or it FATALs the
guard when live (WARN in dry-run). **Do NOT lower the floor to 22/38** — that
defeats the tripwire for a fresh/low-volume account whose tier can drift back
up if volume falls. [K, config_guard.py:39-51, :574-591]

---

## 3. THE STAKES — does the fee error decide the era-4 verdict?

**The founding hypothesis** (from the dispatch): WF-5's cost tolerance is
118.20 bps by point estimate; config 120 bps sits **2 bps above** it (point
estimate negative = the COST_BOUND verdict), while real ~60 bps sits below it
(point estimate positive). So the fee error may have **manufactured** the
"bot can't win" conclusion.

**The hypothesis is arithmetically correct ONLY against a stale snapshot.**
The 118.20 bps tolerance was a property of the **n=33** cohort, not of the
strategy. As the era-4 cohort completed, mean gross per trip decayed
**monotonically** (verified by reproducing WF-5's exact value at n=33):

| n (close-ts order) | mean gross / trip |
|---|---|
| 33 | **+118.20 bps** (== WF-5 exactly — instrument confirmed) |
| 50 | +62.70 bps |
| 54 (readout) | +51.72 bps |
| 61 (complete) | **+41.32 bps** |

[K, growth-curve run over era-4 trips ordered by close-ts; n=33 reproduces
`docs/quant/2026-08-22_walkforward_resampling_tranche2.md` WF-5 to 4 dp]

**On the completed cohort the point-estimate breakeven is +41.3 bps, BELOW
even the cheapest achievable real round-trip (44 bps, both-maker).** So at
real Tier-3 fees the NET point estimate is negative at every realistic fill
bracket:

| fill assumption | Tier-3 round-trip | net / trip (n=61) |
|---|---|---|
| both-maker | 22+22 = 44 bps | −2.68 bps |
| maker-in / taker-out (realistic) | 22+38 = 60 bps | **−18.68 bps** |
| all-taker | 38+38 = 76 bps | −34.68 bps |

Sign double-derived at 60 bps: `mean(G) − 0.60 = −0.1868%` == `mean(G−0.60)
= −0.1868%` (AGREE). Entries are limit-only=maker (OM-011 hard invariant);
exits are maker (PT limit) or taker (escalation final rung) — realistic case
is maker-in/taker-out = 60 bps. [K, fee re-run on realized fills]

**The distinguishability questions are moot on the completed cohort.** The
43.44 bps bootstrap-95%-lower breakeven belonged to the n=33 snapshot. At
n=61 the gross edge ITSELF is no longer distinguishable from zero: raw 95%
bootstrap lower bound breakeven = **−12.44 bps**, concurrency-deflated =
**−59.86 bps**. No tier — not even a zero-fee venue — makes net provably
positive. `n_eff = 25.83` of 61 (SE ×1.54); do NOT read nominal n. [K,
stationary bootstrap b=1.65 reps=20000 seed=7; independent `cohort_
effective_n`]

**REFUTATION on the record.** Both instruments in the founding chain were
reading the same melt-up-era snapshot: the understated config fee AND the
inflated +118 bps gross tolerance. Correcting only the fee (120 -> 44/60/76)
while the gross reverts (118 -> 41) leaves net negative at all brackets. **The
fee error did NOT manufacture COST_BOUND.** [I, synthesis vs WF-5 + WHY-1]

**Two constructive nuances (adversarial against the pessimism):**

1. **The MEDIAN trip grosses +72.6 bps and WOULD clear real Tier-3 60 bps
   (net +12.6 bps).** The MEAN is dragged to +41 bps by fat-tail losers
   (gross sd 246 bps, left-skew). The strategy's failure at real fees is a
   **tail-control problem (ALGO-5 stop/exit geometry), not a dead central
   tendency.** That is the opposite lever from the fee correction. [K]
2. **The dollar aggregation disagrees in sign** with the equal-weighted
   readout. WHY-1's dollar decomposition (n=54) is gross +$8.23, net
   +$1.36 booked / −$5.36 at assumed-Tier-1 true fees; re-priced at real
   Tier-3, the cohort dollar net flips to **~+$1.4**. But the registered
   instrument is **equal-weighted per-trip**, and there the same n=54 reads
   net **−8.28 bps** (negative). This is the known dollar-vs-equal-weight
   sign-flip hazard — the +$1.4 reading is real but is NOT the registered
   gate's verdict. [K, WHY-1; equal-weighted re-run]

---

## 4. THE DECISION — for the operator

The question in front of you is **which fee schedule the live cost manifold
should book.** Three options.

### Option A — correct config to real Tier-3 (22/38), with tier tracking

Set `pretrade` and `order_manager` fees to 22/38 (they must move together —
config_guard fee-mismatch FATAL requires `pretrade == order_manager`), set
`pretrade.allow_sub_floor_fees = true` (required: 22/38 is below the
KRAKEN_SPOT_FLOOR tripwire, which stays 40/80), set
`ml.label_round_trip_cost_pct = 0.6`, and leave `exploration.p_win = 0.85`
(a benign over-margin at the lower bar). Arm OM-080 with a **read-only**
`TradeVolume` credential so the account's tier is tracked going forward and a
future drift re-fires the mismatch alarm.

- **Merit:** the cost manifold matches the account. Conviction entries resume
  (bar 0.6772 inside the 0.60–0.77 band). The book stops being probe-only for
  a fee it does not pay. OM-080 closes the FEE-3 hole permanently.
- **Cost:** COHORT-RESETTING — mints a new execution era, restarts accrual
  from zero on the pre-registered gate. The tier is a **live, volume-dependent
  value**; if 30d volume falls below $10,001 the account drops to Tier-2
  (30/60) and 22/38 becomes an *under*-statement until OM-080 catches it.

### Option B — keep 40/80 as deliberate conservatism

- **Merit:** 40/80 is Kraken's published worst-case; it can never under-state.
  If account volume falls, the tier drifts UP toward 40/80 and the config is
  already there. It is the safe direction for a veto's cost anchor (a stricter
  cost only rejects more marginal trades).
- **Cost:** it suppresses net-positive trades by construction. The entry bar
  0.8335 exceeds the entire live confidence band, so conviction entries stop
  and the book is probe-only. And it **manufactured a confidently-negative
  reading** at the config point estimate (net −78.7 bps at 120 bps) that the
  account's real economics do not support — the very artifact this doc exists
  to flag. Conservatism on a decision knob that *gates entries* is not free;
  it is a systematic short of the strategy's real opportunity set.

### Option C — correct AND re-baseline the cohort gate at real fees

Option A, plus consciously re-registering the cohort gate's cost bands at
real Tier-3 fees (the gate machinery is untouched; only the cost overlay it is
read against changes). This is the honest end-state if you accept that the
era-4 numbers were accrued against a wrong cost anchor and the era-5 accrual
should be evaluated against the true one from its first trip.

### RECOMMENDATION — **Option A + C (correct to real fees, re-baseline, arm OM-080).**

Reasoning:

1. **A wrong cost anchor on a decision knob is a bug, not conservatism.** The
   config books a fee the account does not pay, on both the decision side and
   the booking side, and it gates real entries. CLAUDE.md's own loop-alignment
   finding says protecting the veto RULES does not mean freezing their COST
   ANCHOR — and here the anchor is not merely frozen, it is *wrong by 2x*.
2. **The KRAKEN_SPOT_FLOOR already provides the conservatism Option B wants**,
   without poisoning the decision path. Keep the floor at 40/80 as the
   understatement tripwire; book the truth below it via `allow_sub_floor_fees`.
   You get both: a correct decision anchor AND a standing alarm if the account
   ever drifts back toward the published tier.
3. **Do not oversell the upside.** Correcting the fee does NOT flip era-4 to a
   winner (Section 3: real 60 bps still yields a negative point estimate on the
   completed cohort; the readout class stays COST-BOUND). What it buys is an
   *honest* readout — the era-5 cohort will be measured against the fee it
   actually pays, and the real lever (tail control, ALGO-5) can be worked
   without a phantom fee suppressing the entries that would populate the
   cohort. Correcting the anchor is necessary for an honest measurement; it is
   not sufficient for a profitable strategy.
4. **Arm OM-080.** The whole incident traces to n=0 fee-recon. One read-only
   `TradeVolume` credential makes the account's tier a *measured* value, not an
   *assumed* one, and turns the next tier drift into an alarm instead of
   another silent 2x error.

**The decision is the operator's.** This document names which decision has
become decidable; it does not make it.

---

## 5. CLASSIFICATION

- **SAFE (shipped / shippable without adjudication):** this document; the
  re-derivation helper `scripts/fee_tier_rederive.py`; the walk-forward re-run
  at real fees; the realized-record re-pricing. None alters which orders are
  placed or how they fill.
- **COHORT-RESETTING (operator ARM required):** the config change itself.
  Editing `pretrade`/`order_manager` fees, `label_round_trip_cost_pct`,
  `allow_sub_floor_fees`, or the label barrier geometry **reverses/supersedes
  cut #8** — itself an operator adjudication — and therefore **mints a new
  execution era and restarts era-5 accrual from zero**, exactly as cut #8 did.
  It touches entry decisioning (the derived bar), the fill/cost manifold (fee
  booking), and the label geometry the retrain loop trains on. It is
  inadmissible mid-era without operator adjudication, and it must be applied
  through the stager (`scripts/boundary5_stage.py`-class mechanism: single
  writer, drift-check, backup, `validate()` on the applied file, `exec_era`
  minted in the SAME commit as the behavior change) — no repeat of cut #7's
  late-bump debt. `dry_run` is never touched.

---

## 6. WHAT THIS COULD NOT SEE

- **n_eff keeps the sign undetermined.** The era-4 completed cohort carries
  n_eff ≈ 25.83 of 61 nominal (era-4 readout window n_eff was 9.92). The 95%
  bootstrap CI on gross mean spans zero ([−17.26, +104.25] bps raw;
  [−48.71, +138.02] concurrency-widened); P(net ≤ 0 | 60 bps) ≈ 0.733. The
  fee fix moves the POINT estimate, not the INTERVAL. "Leaning negative" is a
  point-estimate statement, not a significance claim either way.
- **The tier is a live, volume-dependent value.** Snapshot 2026-08-29 14:58
  ($17,482.46 30d spot volume, Tier 3). It can change with volume; there is
  **no in-repo corroboration** — OM-080 is still n=0, so "22/38" is [I] from
  the operator screenshot, not [K] from a `TradeVolume` read. Arming OM-080
  (Option A) is what would make it [K] and keep it current.
- **The walk-forward rests on reconstructed prices.** The fee re-pricing runs
  on realized fills via `fee_anatomy_report.build_trips` (validated to
  reproduce the published Tier-1 aggregates), but the WF-5 breakevens and the
  bootstrap intervals rest on the walk-forward's reconstructed price paths,
  not on an independent tick record.
- **Instrument hazards honored:** never used `ml.corpus.gross_ret_pct` on live
  rows (its exit≤0 guard hole returns ±100% on `exit_price=0.0` live rows);
  never pooled gross across disjoint `label_era` populations; effective-n
  reported, not nominal; live files snapshot-stamped (fills snapshot
  2026-08-29T06:27:45Z; config read 2026-08-29 15:05 CDT). The pooled
  464-trip record stays deeply negative at ANY fee schedule (pooled gross
  ≈ 0, spans ≥5 eras) — the sign discussion is SPECIFIC to the era-4 n=54/61
  cohort and must not be read as a pool result.

---

## 7. Provenance ledger

| claim | value | tag | source |
|---|---|---|---|
| account tier | Tier 3, 22/38 bps, $17,482.46 30d vol | [K] | operator screenshot 2026-08-29 14:58 |
| config fees | pretrade 40/80, om 40/80 | [K] | config.json@c1882728, read 2026-08-29 15:05 CDT |
| entry bar 40/80 | 0.8335 | [K] | fee_tier_rederive.py R1==R2 |
| entry bar 22/38 | 0.6772 | [K] | fee_tier_rederive.py R1==R2 |
| b_net 40/80 -> 22/38 | 0.1998 -> 0.4766 | [K] | fee_tier_rederive.py |
| give-back buffer | 166 -> 82 bps, WARN both | [K] | fee_tier_rederive.py; config_guard.py:2373-2378 |
| WF-5 tolerance (n=33) | 118.20 / 43.44 bps | [K] | docs/quant/2026-08-22_walkforward_resampling_tranche2.md |
| gross-mean decay | 118.2(33) / 62.7(50) / 51.7(54) / 41.3(61) bps | [K] | growth-curve re-run |
| net/trip @ 60 bps, n=61 | −18.68 bps (double-derived AGREE) | [K] | fee re-run on realized fills |
| median gross / trip | +72.6 bps (clears 60) | [K] | growth-curve re-run |
| n_eff (n=61) | 25.83 | [K] | cohort_effective_n |
| booked median RT | 65.4 bps (~real 60, not config 120) | [K] | fee_anatomy §2 |
| OM-080 fired | n=0 (no live credentials) | [K] | cost_truth_report.py:337 |
| real ~60 bps | 22+38 | [I] | Tier-3 sum, no venue corroboration in-repo |

---

*Filed SAFE. The config change this document analyzes is COHORT-RESETTING and
awaits operator ARM. Companion re-derivation: `scripts/fee_tier_rederive.py`.*
