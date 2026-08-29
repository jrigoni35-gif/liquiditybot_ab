# Fee anatomy of realized trips — and the maker-exit prize is tiny

**Date:** 2026-08-29 · **Class:** SAFE (pure measurement; no decision-path,
config, or order-lifecycle change) · **Repo HEAD:** `2da0601c` (== main at
dispatch) · **Instrument:** `scripts/fee_anatomy_report.py` (new, this doc)
+ `scripts/cost_attribution.py` + `scripts/cost_truth_report.py`.

## The one-paragraph answer

The operator's hypothesis — *"my flat 1.2% replay cost over-charges because a
maker-exit trip really pays ~40bps not 80"* — is **REFUTED by the fills
themselves**. Exits are **96.3% TAKER** [K], so the flat 1.2% (= 40 maker
entry + 80 taker exit) is not a pessimistic assumption; it is an almost exact
description of the realized mix. The median venue-true round-trip is **120.8
bps** [K] against the flat **120.0** — dead on. The ~−1%/trip bleed is
**real and almost entirely fees**: gross edge is indistinguishable from zero,
so net ≈ −(fees) ≈ −1.2 to −1.34%/trip. And the fix the hypothesis implies (push
exits to maker) has a **capturable ceiling of ~$24 over the entire 40-day,
463-trip history** [K] — the big-notional taker exits are structural (stops
that must be allowed out, hedge unwinds that are never gated). **Not worth an
adjudication.** `label_round_trip_cost_pct = 1.2%` is **correctly calibrated**,
and the entry bar 0.8335 it derives is coherent with reality.

## Population & provenance (contract: exact bounds, named needles)

- **Source:** `outputs/fills.csv` (the per-fill ledger, `core/fill_ledger.py`
  COLS). Snapshot **mtime 2026-08-28T14:48:36Z**, read **2026-08-29T05:36Z**.
  Values are as-of that snapshot; the live runner is probe-dominated post-cut
  so the file has not grown since (last fill ts == mtime).
- **Inclusive row bounds:** 1171 fill rows (file lines 2–1172; line 1 header),
  `ts` ∈ **[1784583391.251, 1787928516.210]** = **[2026-07-20T21:36:31Z,
  2026-08-28T14:48:36Z]** [K].
- **Needle per source:** maker/taker = the `post_only` column (`'1'` → maker,
  booked `maker_fee_bps`; `'0'` → taker, `taker_fee_bps`;
  `execution/order_manager.py:527-528`). Leg = `purpose` ∈ {entry, exit,
  hedge}. Exit type = `reason` column.
- **exec_era mix in the file** [K]: blank 1024, `7-e7d5ca1a` 133, `4-aeeaae36`
  4, `8-ca55e2ba` 4, None 6. Blank = pre-stamp (era-4 and earlier). **The
  file pools ≥5 execution eras.** Fee re-pricing is era-invariant by
  construction (one schedule applied to each fill's own flag); **gross P&L is
  NOT** — see the effective-n caveat before reading any pooled gross number.

## 1. Maker/taker mix on realized fills [K]

| leg | n fills | maker (post_only=1) | taker (post_only=0) |
|---|---|---|---|
| **entry** | 520 | **450 (86.5%)** | 70 (13.5%) |
| **exit**  | 492 | **18 (3.7%)** | **474 (96.3%)** |
| **hedge** | 159 | 0 (0.0%) | 159 (100%) |

The load-bearing row is **EXIT: 96.3% taker**. `ordertype` is `limit` for all
1171 fills [K] — maker/taker is decided by `post_only`, not ordertype; a
taker exit is a marketable/escalated limit, not a "market order" in the
ledger.

**Second route (corroboration, different source):** `cost_truth_report.py`
§3 reads the OM-000 terminal-fill records in `outputs/audit.jsonl` (needle:
`code == OM_CLEAN_TERMINAL`, `terminal=filled`; post-2026-07-28 subset,
n=287 entry legs / 296 exit legs) and reports **booked entry-leg 34.93 bps**
(between maker 25 and taker 40 → mostly maker) and **booked exit-leg 39.31
bps** (≈ taker 40 → ~all taker) [K]. Independent source, same mix.

## 2. Effective booked fee per round-trip [K]

Round-trips deduplicated by **fill pattern** (position_id carries the
restart-replay 16× duplication; same identity rule as `cost_attribution`).
**n_trips = 463**, 6 still-open skipped.

| round-trip cost | min | median | mean | max |
|---|---|---|---|---|
| **BOOKED** (rate in force when written, ~all 25/40 era) | 50.1 | **65.4** | 71.5 | 80.6 |
| **VENUE-TRUE** (re-priced 40/80 per post_only) | 80.2 | **120.8** | 137.8 | 161.2 |

Venue-true histogram (20-bps bins) [K]: [80,100)=3 · [100,120)=141 ·
[120,140)=107 · [140,160)=57 · [160,180)=155.

**Double-derive of BOOKED cost — two independent routes agree:**
- `fee_anatomy_report` / `cost_attribution` (fills.csv): booked mean **71.5
  bps** / median 65.4 [K].
- `cost_truth_report` §3 (audit.jsonl, different file): booked round-trip
  **74.24 bps** [K].
- Agreement within ~4%; both are the OLD 25/40 schedule the fills were booked
  at. The booked per-fill rates are bimodal at exactly **25.0 / 40.0 bps** [K],
  the pre-cut config, confirming `post_only` is honored.

**Where the two cost instruments DISAGREE and why (report both):**
- `cost_truth_report` §2 (postmortem route) = **120.64 bps, "within
  tolerance"**. This is a **broken derivation post-cut** [I]: it adds a +0.64
  bps overrun (measured at the OLD 25/40 config) onto TODAY's 120 config
  baseline. The report's own caveat warns of exactly this config-history
  blindness. Do not read 120.64 as venue truth.
- `cost_truth_report` §3 verdict = **"configured overestimates"** (74 vs 120).
  Artifact of comparing **pre-cut booked fees** (74) against the **post-cut
  config** (120). The 74 is sound as *booked*; the verdict label is stale.
- **OM-080 has NEVER fired (n_records=0)** [K] — no venue-truth reconciliation
  of the account's actual tier exists. 40/80 is the published Tier-1
  *schedule*, not the verified *row* (FEE-3 on the docket).

## 3. Decomposing the −1%/trip [K]

Pooled over the 463 trips (see effective-n caveat):

| term | value |
|---|---|
| mean gross | **+0.0339%** (median −0.0277%, dollar-weighted −0.0108%) |
| mean booked fee | 0.715% |
| mean venue-true fee | 1.378% |
| **net @ booked** | **−0.681%** |
| **net @ venue-true** | **−1.344%** |
| fee understatement (venue-true − booked) | **+66.3 bps/trip** |
| agg (n=463) | gross **−$5.41**, booked $386, venue-true **$764**, notional $49,964 |

- **The bleed is fees, not a losing edge in the price sense.** Gross ≈ 0
  (`cost_attribution` clustered t = 0.51, G=35 day-clusters → **not
  distinguishable from zero**), so net ≈ −(venue-true fee) ≈ −1.2 to −1.34%.
- **Of the fee bill, 95.3% of the dollars are TAKER** [K]: venue-true fees
  split **maker $35.58 (4.7%, n=468) vs taker $729.34 (95.3%, n=703)**. Maker
  fills are numerous but cheap (40 bps, mostly entries); taker fills carry the
  bill (80 bps, exits + hedges). The fee problem *is* a taker problem, and the
  taker legs are exits (474) and hedges (159).
- **Is flat-1.2% over- or under-charging vs the measured mix?** At the
  **median it is exact** (120.8 vs 120.0, +0.8 bps). At the **mean it slightly
  UNDER-charges** by 17.8 bps (137.8 vs 120), because trips with a taker entry
  or hedge-heavy legs run richer. **Direction of any error is toward
  under-, not over-charging** — the opposite of the hypothesis.

## 4. Counterfactual prize of maker exits [K] (bounds the whole idea)

If every taker EXIT leg instead filled maker (rate drop 80→40 = 40 bps):

| bucket | n exit fills | notional | prize @ 40bps |
|---|---|---|---|
| **STRUCTURAL** (cannot be maker) | 245 | $43,828 | $175.31 — **NOT capturable** |
| **DEFERRABLE** (could rest maker) | 229 | $5,985 | **$23.94 — capturable ceiling** |
| MAX (all taker exits, incl. impossible) | 474 | $49,813 | $199.25 |

- **Structural floor = stops + hedge unwinds + forced closes.** Breakdown [K]:
  hedge unwind 159, tb_time 43, tb_sl 18, time-stop scratch 11, stop-N-hit 5,
  stale-loser 5, operator flatten 3, hard-cap 1. A stop MUST be allowed to
  exit (CLAUDE.md invariant #5); a hedge unwind is NEVER gated. These are
  ~$43.8k of the $49.8k taker-exit notional and are **unavoidable taker**.
- **Deferrable = profit-taking exits** [K]: tier trail 154, label-mature
  ML-073 38, tier 1/2/3 33, tb_pt 4. Total notional only **$5,985**, prize
  **$23.94 over the entire 40-day history ≈ $0.05/trip**.
- **The mechanism to capture it already exists and mostly fails.**
  `risk.exit_escalation.maker_first_profit_exits = True` [K] already rests
  profit exits post-only on the first attempt, yet these fills still book
  **taker** — the maker attempt does not fill in the resting window and
  escalates to taker. So the $24 ceiling is already being chased and mostly
  missed; the *accessible* prize is below it.

**Verdict: the maker-exit push is not worth an adjudication.** The prize is
two orders of magnitude below the bleed it is meant to cure.

## 5. Fix map (each classified; prize attached)

| # | fix | class | measured prize / finding |
|---|---|---|---|
| 5.1 | `label_round_trip_cost_pct = 1.2%` re-calibration | **SAFE finding — DO NOT act** | **Correctly calibrated.** Median venue-true RT = 120.8 bps ≈ 1.2%. NOT over-conservative given taker exits. The bar 0.8335 it derives is coherent. *Nuance:* 1.2% is correct *for taker-exit behavior*; it would over-charge only if exits became maker — which §4 shows they structurally cannot. Lever is exit behavior, not the label cost. |
| 5.2 | post_only entry-leakage | **COHORT-RESETTING** (order flag = lifecycle) | 70/520 entries (13.5%) fill taker [K], all attempt=0 (deliberate crossing/urgency, `execution_tactics.allow_taker=True`), notional $1,895 = 17.8% of entry notional. Go-forward prize of forcing them maker = **$7.58 total** [K]. Negligible; not worth minting a boundary. |
| 5.3 | Kraken fee TIER reduction | **UNAVAILABLE at this scale** | Tier is set by **30-day USD volume**, not equity. In **dry-run, real venue volume = $0 → permanently Tier-1 40/80** [I]. Not a reachable lever while paper. *Live-only nuance:* the bot's own churn ($50k/40d) could cross Tier-2 ($2.5k → 30/60); but that is live-only and speculative, and OM-080 (n=0) has never verified the account row. **Do not propose tier reduction as a dry-run fix.** |
| 5.4 | Escalation-ladder taker final rung | **COHORT-RESETTING** | The market final rung is the escalation of the *deferrable* profit exits in §4; its whole prize is inside the **$23.94 ceiling** and is already partly chased by `maker_first_profit_exits`. Deferring/removing the market rung on stops is forbidden (exits always allowed). Prize ≪ adjudication cost. |

## What the measurement could NOT see

- **Effective-n:** n=463 trips is **nominal, not effective**. Trips overlap
  (WHY-1 measured n_eff 9.92 for the era-4 subset at mean uniqueness 0.301;
  `cost_attribution` clusters to G=35 days). The pooled gross mean is inside
  2× its clustered SE — read it as "~zero edge", never as a point estimate.
- **Era pooling of gross:** the 463 trips span ≥5 cost manifolds. Gross P&L
  is pooled only to *size* the bleed; it must not be read as an era-4 (or
  any single-era) result. Fee re-pricing is the only era-invariant half.
- **Venue truth:** 40/80 is the published schedule; **OM-080 has never fired**,
  so the account's actual tier row is unverified (FEE-3). Every venue-true
  number here inherits that one unproven assumption.
- **Counterfactual realism:** the $23.94 deferrable ceiling assumes a resting
  maker exit would have filled at the same price/time — it would not always
  (adverse selection on the unfilled tail). The *accessible* prize is below
  the ceiling, and `maker_first_profit_exits` already demonstrates the miss.
- **Instrument drift (SAFE, flagged not fixed):** `cost_attribution.py`'s
  schedule label `"configured (25/40)"` is stale post-cut #8 (config is now
  40/80); the number it prints (0.715% booked) is real but the label
  misleads — same class as QT-1. Left unchanged; noted for the operator.
