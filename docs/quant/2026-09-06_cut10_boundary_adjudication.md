# Cut #10 — the verified-defects boundary (era-7) — operator adjudication

**Date:** 2026-09-06
**Class:** COHORT-RESETTING. Mints `exec_era` `10-a5acfe2d`; era-7 accrual begins
from zero at the runner restart. Era-6 rows stay citable AS era-6 and may not
be pooled across this cut.
**Authority:** operator, 2026-09-06 — "Approve all", then the bundled-boundary
option, then "finish any changes pending". The reset consequence was stated
explicitly before the bundle option was chosen.
**Stage:** `scripts/cut10_stage.py --apply` (config half); this commit (code
half). Both in one boundary, per the cut-#8/#9 pattern.

---

## 0. TL;DR

Six defects, each **CONFIRMED by making the running system demonstrate it**
and then adversarially re-verified (`docs/quant/2026-09-05_verified_findings_batch.md`),
sat behind the moratorium's cohort-resetting fences. They land here as one
boundary, together with the fee-booking correction that E1 — the cheapest
experiment on the docket — surfaced the same day.

**Two pre-named items were deliberately NOT bundled**, and the reasoning is
the most important part of this record (§3): ALGO-5 is already adjudicated
*"do not arm"*, and GB-1 is refuted at HEAD by a guard that has been live
since 2026-07-30. Bundling either would have re-litigated settled evidence.

## 1. What lands — the code half

| | file | defect (verified) | fix |
|---|---|---|---|
| **B1** | `core/watchdog.py` | `book_ts.get(a, now)` read a **never-delivered** book as age 0 — neither warn- nor critical-stale. Pinned as a strict xfail since creation. | `get(a, 0.0)`; the xfail marker comes off in this commit. |
| **B2** | `risk/profit_tiers.py`, `core/config_guard.py` | absent `est_fee_bps` defaulted **0.0** → break-even floor **6 bps** vs 76 booked. Latent (key present; 0 divergences over a 1,921-point sweep) but real. | absent → venue's worst published taker; guard **FATALs** on absence; explicit 0 stays legal. |
| **B3** | `risk/protocols.py` | NaN equity: `max(nan,0)` keeps NaN → `budget_taper_mult` NaN → both comparisons False → **multiplier 1.0, no reason**. The "fails CLOSED, never open" veto failed open. | non-finite/non-positive → **0.0** + `RP-052`. |
| **B4** | `main.py` | execution feed is an unchecked injectable; venue-adapter layer not on the path; a submit on a non-Kraken feed **PLACED**. | deny-list assertion before `OrderManager`: any read-only venue class (unwrapped through `FeedRecorder`) → `RuntimeError` `VN-020`. |
| **B5** | `core/fill_ledger.py` | unloadable dedup cache → **empty set cached** → replayed fill re-landed in P&L (rows=3, zero log). | load failure → `None` → direct on-disk scan → if that fails too, **refuse the row** + `OM-086`. `new_file` recomputed after load (rotation window). |
| **B6** | `core/config_guard.py`, config | `_CAND_REF_PEAK_ARRIVALS_PER_H = 18.3` was **2.4× stale**; cap 1,200 saturated. | constant → **43.7**; `max_open_candidates` 1200 → **1800**. |

## 2. What lands — the config half (`cut10_stage.py`)

```
ml.max_open_candidates          1200 -> 1800     (B6)
pretrade.maker_fee_bps          22.0 -> 20.0     (E1)
pretrade.taker_fee_bps          38.0 -> 35.0
order_manager.maker_fee_bps     22.0 -> 20.0
order_manager.taker_fee_bps     38.0 -> 35.0
profit_taking.est_fee_bps         38 -> 35
ml.label_round_trip_cost_pct    0.60 -> 0.55     (= (20+35)/100)
```

**Derived entry bar** (`risk/position_sizer` `p_bar_mode=derived`, the same
helper cut #9 used): **0.6772 → 0.6642**. `allow_sub_floor_fees` stays true —
20/35 is a genuine published discount row below the 25/40 zero-volume
tripwire, which is what that flag exists for.

### 2a. E1 — why the fee moves

`scripts/fee_drift_report.py --volume-30d 17482` (2026-09-06T21:19Z):

> config books 22/38, which is **NOT a row in the venue's schedule** … binding
> tier at $17,482/30d: **maker 20 / taker 35** … OVER-stating the round trip by
> **5 bps (9.1%)**.

Cut #9 read 22/38 off a Kraken-app screenshot; 20/35 is the published row the
account actually binds to. Leaving a known-wrong booking in place through a
fresh era would make era-7 accrue on a 9.1%-overstated cost — the reset would
be spent and the cost manifold still wrong.

### 2b. E1 — what else it found (full population, entry AND hedge legs)

`outputs/fills.csv` 196,642 B, 1,245 rows, read 2026-09-06T21:20Z:

| | n | fees | bps/fill |
|---|---|---|---|
| **entry** (maker) | 557 | $31.60 | 27.58 |
| **exit** (taker) | 529 | **$203.22** | 39.94 |
| **hedge** (taker) | 159 | **$157.84** | 40.00 |

**92% of fees ($361 of $393) land on exit and hedge legs at taker rates.** The
entry-only instruments (`breakeven_test.py:126`) saw 8%. Liquidity mix is
**60% taker** on a book whose cost thesis is passive execution. And in paper,
`fees_delta_usd` reproduces the configured bps to the basis point (24.90 /
39.99 against 25/40; 31.78 blended on era-9 rows) — the fee number is a
restatement of config, exactly as the Simons pass warned. Slippage and spread
are the measurements; fees are not.

**E1's null did not obtain.** The fee lever is not retired: the booked row was
wrong (corrected here), and the maker/taker mix contradicts the thesis. The
exit/hedge taker share is the next cost question, and it is an execution
question, not a signal one.

## 3. What was NOT bundled, and why — read this before the next boundary

**ALGO-5 (stop widths + time-decay ladder).** Pre-named in CLAUDE.md as the
next adjudication — and **already adjudicated "do not arm" on 2026-09-02**,
`docs/quant/2026-09-02_sustainability_arm_package.md` row B, verbatim:
*"Do not arm — confirmed at two independent resolutions. Reversal equals the
base rate, and the 5-minute sweep depth/duration is also placebo."* Being
pre-named is a queue position, not a mandate. It was initially proposed for
this bundle on a stale reading of the docket; retracted before any code was
written.

**GB-1 (`arm_gain_pct=0.6` arms inside the break-even buffer).** **Refuted at
HEAD.** `risk/profit_tiers.py:_give_back_candidate` carries an **arm cost
floor** since 2026-07-30: `arm = max(arm, cost_pct / (1 − gb_frac))`. At the
new 76 bps buffer and `giveback_frac=0.4` the effective arm is
**0.76 / 0.6 = 1.27%**, not 0.6%, and the locked share `0.6 × 1.27% = 0.76%`
clears cost by construction. Both live open positions carry the input
(`ETH/USD est_cost_bps=60.02`, `BTC/USD 60.01`). Residual: the floor is inert
at `est_cost_bps == 0` (legacy / restored / quant-trials) by documented
design. **The `config_guard` WARN that still fires on the static 0.6% is a
stale instrument reading the raw knob, not the effective arm.**

**Consequence for the fence:** with ALGO-5 refused and GB-1 refuted, **there
is no second reset queued behind this one.** CONC-1 becomes the next
pre-named adjudication.

**B7 (backfilling historical `candidate_id`s)** — not bundled: it rewrites
past corpus rows and the causal share is unrecoverable anyway. The
forward-only fix (S6) shipped SAFE on 2026-09-05.

**QT-1** — not bundled: its own docket row forbids flipping it in a passing
commit, and it was never re-measured at the new fee.

## 4. Measurements that settled B6

The check is Little's law over the label horizon, so its statistic is the
**horizon-window sustained rate**. Re-derived the same way the constant's own
docstring demands — max seq-span over a rolling 36 h window (432 bars × 5 m),
per lineage, full-width windows only — on `outputs/signal_history.csv`
(25,840 rows, 337 lineages, 7,528 qualifying windows):

```
max 43.7/h (lineage 97211d06)  ·  p99 43.1  ·  p95 42.5  ·  median 37.5
demand = ceil(43.7 × 36) = 1574 slots   vs cap 1200   →  cap 1800 (~15% headroom)
```

Two independent derivations (the 2026-09-05 verification pass and this one)
agree on **43.7 to the tenth.** What was settled first: an hourly **bin** of
the same data reads peak 75 / median 17 and made 18.3 look like "the median
mislabelled as a peak" — wrong lens; on the horizon window 18.3 was simply
stale (measured on one 36 h window three weeks earlier, corpus grew 2.4×). A
sliding window that floored its span at 1 s produced 21,600/h and was
discarded as a broken scan.

## 5. Classification

COHORT-RESETTING on every axis the moratorium names: entry decisioning (B1,
B3), position sizing (B3), stop/exit geometry (B2), order lifecycle (B4), fee
booking (B5 by consequence, E1 directly), and the candidate pipeline (B6).
One boundary. `dry_run` **stays true**; nothing here is a road to live.

## 6. What this could not see

- The B4 assertion is a **deny-list** (read-only venue classes), not an
  allow-list, so test doubles keep working. A novel non-Kraken feed class not
  on the list would pass. The adapter layer is still not wired onto the order
  path; that remains a larger lifecycle change and is not attempted here.
- E1's fee figures are paper: `fees_delta_usd` is the configured constant by
  construction. The 60%-taker mix and the exit/hedge share are real; the
  dollar amounts are what config says they are.
- B6's 43.7 is a maximum over one corpus; a busier regime moves it. The cap
  carries ~15% headroom, and the guard now re-arms if demand crosses it.
- Nothing here changes the era-7 gate machinery (`scripts/cohort_eval.py`,
  its bands, its selection rule) — untouched, as registered.

## 7. Provenance ledger

| claim | source | tag |
|---|---|---|
| 22/38 not a published row; binding 20/35 at $17,482 | `fee_drift_report.py --volume-30d 17482`, 2026-09-06T21:19Z | [K] |
| 92% of fees on exit+hedge; 60% taker | `outputs/fills.csv`, 1,245 rows, 2026-09-06T21:20Z | [K] |
| derived bar 0.6772 → 0.6642 | `risk/position_sizer.PositionSizer`, both configs, this session | [K] |
| B6 43.7/h, demand 1574 | `signal_history.csv` rolling-36h, this session; agrees with 09-05 pass | [K] ×2 |
| ALGO-5 "do not arm" | `2026-09-02_sustainability_arm_package.md` row B, read directly | [K] |
| GB-1 effective arm 1.27%; both live positions carry est_cost_bps | `profit_tiers.py:576-620` + `outputs/state.json`, this session | [K] |
| B1–B6 defects | `vault/raw/audits/2026-09-05_deferred_findings_verification.json` | [K] |
| stage sweep 0 FATAL / 4 WARN | `cut10_stage.py` dry run, this session | [K] |
