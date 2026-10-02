# Forward-data setup: the paper target book and the weekly forward reads (2026-10-02)

**Class: SAFE.** Two measurement jobs on the PC supervisor, writing only
under `outputs/`. No decision-module file is touched; the decision
fingerprint is unchanged (`target_book` stays in `NON_DECISION_SECTIONS`,
`tests/test_target_book_shadow_pin.py` green); no order is placed, no private
endpoint is called, `dry_run` is untouched. Operator direction, verbatim:
*"Set everything up to gain data for the bots purposes and configure it like
it's not anything different then a real instance yet we are running dry."*

## 0. The defect this fixed first

Every hypothesis registered on 2026-10-02 was to be promoted only on data
after its `forward_from`. That data could never have arrived:

- the registered windows ENDED at 2026-08 (`PANEL_MONTHS`, `QH_MONTHS`);
- every download cache was keyed by the whole month RANGE, so a window
  reaching the current month would have frozen the month at its first
  fetch (`BOT_MONTHS` already ended in 2026-10: its 5m cache on the cloud
  box held October as of 2026-10-02 and would have stayed that way);
- the stablecoin-supply and GPR series were cached once, forever.

Forward n would have stayed 0 for every hypothesis indefinitely - the
ledger would have looked like "no evidence yet", never like a broken
instrument. Fixed in `scripts/alpha_decay_report.py`: per-month caches;
a month is cached forever only once it ended >= 3 days ago (archive files
final); the forming month is re-fetched once per UTC day; `--through now`
rolls every window's END to the current month (starts and definitions stay
as registered); whole-history external series refresh daily in that mode,
and a failed refresh keeps the last copy. Pinned in
`tests/test_alpha_decay_report.py` (clock-injected).

## 1. Paper target book - `scripts/target_book_paper.py` (hourly)

The real instance's terms, unchanged: the bot's paper capital
(`capital_management.starting_capital_usd`), the booked maker fee
(`pretrade.maker_fee_bps`), Kraken (the execution venue) PUBLIC 4h OHLC, the
`target_book` config, maker limit at the decision close filled only on a
trade-through. Fills are simulated by the shadow book's own fill model, NOT
routed through `OrderManager`: routing it there would fork the decision
cohort (sizing/lifecycle axes) and mix basket legs into the trip book's
labels - that remains the TARGET BOOK WIRING docket item.

**Registered before any forward bar existed:** `PAPER_FROM`
2026-10-03T00:00Z (bars before it are warm-up only, never graded); arms
`buy_hold`, `target_book`, `target_book_vol40` (vol targeting at 40%/yr),
plus the idea lab (never promotes); read points n = 180 steps (30 days) the
lean, n = 540 steps (90 days) the verdict, each arm vs `buy_hold`, paired
block bootstrap; readouts never decide.

**State:** an append-merge bar store plus a deterministic replay from
`PAPER_FROM` on every run, so a restart, a crash or a missed hour changes
nothing, and a closed bar's result never moves (pinned). Gaps longer than
Kraken's 720-bar memory are counted, never filled. Instrument check on real
bars (60-day dry run of the replay, scratch only): basket +36.3% =
0.9 x mean(BTC +37.1, ETH +47.4, PAXG +3.3, LINK +74.3)% - consistent.

## 2. Forward reads - `scripts/forward_reads.py` (weekly)

`alpha_decay_report --through now --skip-controls --reps 1000` → evidence
ledger → sticky statuses in `outputs/reports/forward/registry_status.json`
(an ELIMINATED status is never overwritten; kept in `outputs/`, not the
repo, so the deployed checkout stays clean for the test-gated updater) →
knowledge plan → `outputs/reports/forward/forward_reads.json` with a CS-1
reconcile line (unit: hypothesis; blocks = independent weeks). The
instrument controls ran at registration and are not repeated weekly. A
lock prevents overlapping runs (stale after 12 h).

Known lag, stated: Binance publishes perp funding only as monthly files, so
L3 and C2 receive forward data up to a month late.

## 3. Wiring and visibility

`scripts/pc_supervisor.py`: `LB_TARGET_PAPER_SEC` (3600) and
`LB_FORWARD_READ_SEC` (604800), stamp-gated like the candle collector;
kill switches `LB_NO_TARGET_PAPER=1`, `LB_NO_FORWARD_READS=1`; both stamps
registered in `tests/conftest.py` on introduction. `scripts/session_export.py`
carries `target_book_paper.json` and `forward_reads.json` in the hourly
pc-live bundle, so both read off-box from
`outputs/imported_sessions/pc-live/` on any clone.

## 4. First forward read (cloud, 2026-10-02)

Pending: the first end-to-end run on live data was in progress when this
record was committed; its numbers are added in the next commit.
