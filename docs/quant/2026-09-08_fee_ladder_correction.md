# The fee ladder was the legacy one — cut #10's E1 booked a tier the account does not hold (2026-09-08)

**Class:** measurement-instrument correction, SAFE (no booking, no order path,
no fill path changed; the shipped config validates identically — guard sweep
before/after: 0 FATAL / 3 WARN, same messages). **Booking correction:**
COHORT-RESETTING, docketed as **FEE-4**, not applied.
**Found while:** scouting Claude Code skills (vault
`raw/research/2026-09-08_crypto_skills_scout.md`); a vendor skill quoted a
fee row that matched nothing we had, which sent me to the venue's page.

## 1. What the venue publishes — three routes, no summarizer

| route | read | rows |
|---|---|---|
| kraken.com/features/fee-schedule, **raw page text** (tags stripped, regex; no LLM in the loop) | 2026-09-08T20:15:29Z | "Cross-platform Fee Tiers", captioned "Spot Crypto": **Tier 1 $0+ 0.40/0.80 · Tier 2 $2.5K+ 0.30/0.60 · Tier 3 $10K+ or $20k AoP 0.22/0.38 · Tier 4 $25K+ or $50k AoP 0.20/0.35 · Tier 5 $50K+/$100k 0.15/0.30 · T6 $100K+ 0.12/0.25 · T7 $250K+ 0.10/0.22 · T8 $500K+ 0.08/0.20 · T9 $1M+ 0.06/0.18 · T10 $2.5M+ 0.04/0.15 · T11 $5M+ 0.02/0.12 · T12 $10M+ 0.0/0.10 · Pro 1–5 $50M–$500M 0.0/0.09→0.05** |
| operator's Kraken-app screenshot (recorded in `2026-08-29_fee_tier_correction_adjudication.md`) | 2026-08-29 14:58 | T1 0.40/0.80 · T2 0.30/0.60 at $2,501 · **T3 0.22/0.38 at $10,001 — the account, on $17,482.46** · T4 0.20/0.35 at $25,001 |
| `/0/public/AssetPairs` `fees` / `fees_maker` (what `core/venue_fees.py` read on 09-05) | 2026-09-05 | **legacy ladder**: 25/40 at $0, 20/35 at $10k, 14/24 at $50k, 12/22, … 0/5 |
| same endpoint | 2026-09-08T20:12:46Z | `fees: []`, `fees_maker: []` for XBT/ETH/PAXG/LINK — **no fee arrays at all** |

Two independent routes on two dates agree on the current ladder. The JSON
endpoint served a ladder the venue had already replaced, then stopped
serving one. **The venue also now grants a tier by the best of 30-day spot
volume OR assets on platform (AoP)** — a second qualifier nothing in this
repo knew about.

## 2. What we did with the wrong ladder

- **2026-09-05:** `core/venue_fees.py` was built to end "struck fee literals"
  and read its reference table from AssetPairs. Its docstring, the config
  guard, `fee_drift_report`, `fee_anatomy_report`, `cost_attribution` and two
  test suites then all asserted: *"40/80 is not a row; neither is 22/38."*
- **2026-09-06, cut #10 E1:** `fee_drift_report --volume-30d 17482` said
  *"config books 22/38, NOT a row … binding tier 20/35 … OVER-stating by
  5 bps"*, and the booking moved 22/38 → 20/35 (`pretrade`, `order_manager`,
  `est_fee_bps` 38 → 35, `label_round_trip_cost_pct` 0.60 → 0.55, derived
  entry bar 0.6772 → 0.6642). Every one of those premises was the legacy
  ladder talking. **Cut #9's 22/38, read from the app, was right.**
- **2026-09-07, my FEE-TIER caveat** on HANDOFF said "if < $10k the true row
  is 25/40". There is no 25/40 row. Same source, same error, third author.

The-method recurrence #1 (a struck fee schedule asserting itself as truth),
fourth instance — and this time inside the module built to end it, because it
trusted the one source the venue no longer keeps current and its tests pinned
that source's output as the property.

## 3. What the corrected instrument says

`python scripts/fee_drift_report.py --volume-30d 17482` (2026-09-08):

    config books      : maker 20 / taker 35 bps   (round trip 55 bps)
    is a published row: YES                        (Tier 4)
    binding tier at $17,482/30d : maker 22 / taker 38 bps (round trip 60 bps)
    live venue        : AGREES with the reference table (fee page)
    DRIFT FOUND — config books 20/35 but the binding tier is 22/38 —
    UNDER-stating the round trip by 5 bps (8.3%).

Volume alone is a **lower bound** on the discount: if the real account holds
≥ $50k on platform it IS Tier 4 and 20/35 is right; ≥ $20k AoP guarantees
Tier 3. If the real 30-day volume has decayed below $10k with < $20k AoP
(the sim's own trailing-30d is $5,185; the real account's is unknown here —
no credentials resolve on this box), the row is **Tier 2 30/60** and the
booking under-states the round trip by **35 bps (64%)**.

**Effect on the era-8 readout** ("net $/trip at booked fees"): optimistic by
≥ 5 bps per round trip (≈ $0.03 on a $60 ticket) at Tier 3; by 35 bps
(≈ $0.21, most of the −$0.33 H0 expectation) at Tier 2. Read the n=50 lean
with this bias named; re-booking waits for the boundary.

## 4. Changes (SAFE) — file map

| file | change |
|---|---|
| `core/venue_fees.py` | schedule → the current 17-row ladder + aligned `KRAKEN_SPOT_AOP_USD`; `binding_row(volume, aop_usd=None)` = best of the two (volume still required — unknown stays unknown); `parse_fee_page()` (pure; anchors on the "Spot Crypto" caption so the maker-rebate and stablecoin tables, which also start at $0+, cannot be mistaken) and `fetch_page_schedule()` (browser UA — the page 403s Python's default; URL stays a module constant); `fetch_live_schedule()` kept as the second route, documented as serving nothing; register rewritten |
| `core/config_guard.py` | comment block corrected; the not-a-row WARN's row list derived from the schedule (was a literal of the legacy ladder) |
| `scripts/fee_drift_report.py` | two routes — page = authority, JSON = must agree or DIFFERS; register corrected |
| `scripts/fee_anatomy_report.py` | unreadable-config fallback `(25.0, 40.0)` literal → `worst_row()` derived; comment corrected |
| `scripts/cost_attribution.py`, `core/fill_ledger.py`, `scripts/cut10_stage.py`, `tests/test_exit_policy_label.py` | false claims in comments corrected, history kept verbatim and dated |
| `tests/test_config_guard_fee_floor.py` | rewritten: 40/80 and 22/38 ARE rows; legacy 25/40 and 14/24 and struck 16/26 must stay dead; ladder/AoP shape; sub-floor params extended; live-page pin (skips honestly); JSON-endpoint pin (must agree if it ever serves again); planted three-ladder page for the parser in both orders; `binding_row` at every boundary incl. $17,482 → 22/38 and $25,000 → 20/35; AoP improves never worsens; WARN text derived |
| `tests/test_no_attacker_directed_fetch.py` | SSRF pin now covers BOTH fetchers; accepts `Request(CONST, headers=…)` |
| `tests/test_verified_findings_batch2.py`, `tests/test_cost_attribution_dispersion.py` | pin the property (fallback is a published row, derived), not the legacy literal |

Mutation 7/7 red: Tier 3 → legacy row; AoP ignored; caption anchor removed;
$0-reset removed; fallback literal restored; row tolerance 5 bps; page fetch
opens a non-constant. Guard sweep on the shipped config identical before and
after.

## 5. Docket — FEE-4 (cohort-resetting, next boundary)

Re-book fees to the row the REAL account qualifies for, read live: the
operator reads the Kraken app's fee tier, 30-day volume **and assets on
platform** (or supplies a query-only key so OM-080/`TradeVolume` binds it).
Then `fee_drift_report --volume-30d <v>` (and AoP once the report takes it)
names the row; the boundary books it with the same cascade cut #10 used
(`est_fee_bps`, `label_round_trip_cost_pct`, derived bar). Until then nothing
moves: era-8 accrues at 20/35 with the bias in §3 named on every readout.

## 6. What this check could not see
Whether the account's AoP crosses $20k/$50k; whether the real 30-day volume
is above $10k today; whether Kraken applies the "Spot Maker Rebate" table to
any pair this bot trades (page: "a select number of low-liquidity pairs" —
not the majors, [I]). The page parser is pinned on a planted page and on the
live page as of 09-08; a redesign of the page reads as UNREACHABLE (skip),
never as agreement.
