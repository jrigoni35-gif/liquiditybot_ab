# Market-conduct limits — the CME-benchmarked line the bot must never cross

**Jurisdictional honesty first.** This bot trades **Kraken spot crypto in
DRY_RUN paper mode**. CME rules govern CME markets and do not directly bind
a Kraken spot account. They are used here deliberately anyway: the CME
rulebook is the industry's clearest codification of what regulators treat
as market abuse, the CFTC and DOJ have applied the same manipulation
theories to crypto venues, and Kraken's own terms prohibit the same
conduct classes. This document is the **absolute-legal-limit map**: each
prohibited class, the engineering mechanism that keeps us on the right
side of it, and what remains open before any live arming.

Sources: [CME Rule 575 advisory (RA1516-5)](https://www.cmegroup.com/rulebook/files/cme-group-Rule-575.pdf) ·
[CME disruptive-practices course](https://www.cmegroup.com/education/courses/market-regulation/disruptive-practices-prohibited/disruptive-practices-prohibited-general-information) ·
[Rule 534 wash trades](https://crosstrade.io/blog/cme-rule-534)

## Rule 575 class A — spoofing (bid/offer with intent to cancel before execution)

The legal test: intent **at the time of order entry**; intent may be
inferred from conduct alone ("more likely than not intended to produce a
disruptive consequence").

Our mechanisms:
- Every order is placed to be filled: entries are maker-first limit
  orders sized by the position sizer with a registered reason code, and
  each cancel/reprice is bounded (`order_manager.max_reprices`, default 1)
  and itself audit-coded. There is no code path that places an order whose
  purpose is its own cancellation, and no layered-ladder machinery exists.
- The long-horizon accumulation book (`risk/long_book.py`, Compounder
  Phase C) reprices on its own, wider, separately-bounded cadence — not
  `order_manager.max_reprices`. `main._long_book_cycle` cancels-and-
  replaces a resting bid at most **once per ~30s pass, per asset** (the
  loop body evaluates each asset once), and only once the bid has
  drifted past the `add_offset_pct + zone_buffer_pct + zone_tol_pct`
  staleness band vs. mark (shipped 0.5 + 0.2 + 0.15 = 0.85%, via
  `bid_is_stale`); each resting bid also carries its own
  `order_ttl_hours` lifetime (shipped 6h) instead of the 5m book's ~25s
  timeout, so it cannot orbit indefinitely between reprices either. The
  reprice itself is audit-coded `LB-021` (`Code.LB_BID_REPRICED`,
  main.py's `_long_book_cycle`). `core/config_guard.py`'s
  `_long_book_checks` FATALs a floor under every one of these cadence
  knobs (market-conduct pass, task F4): `order_ttl_hours >= 1.0h`,
  `add_min_spacing_hours >= 1.0h`, `retry_backoff_minutes >= 5.0min`,
  and the staleness-band sum `>= 0.3%` — a config change alone cannot
  turn the patient accumulation book into a touch-hugging flicker
  quoter without first tripping config_guard.
- The hash-chained audit trail + reason codes on every disposition are the
  **intent record**: for any order we can reconstruct why it was placed,
  why it moved, and why it was cancelled. Under an inferred-intent
  standard, a complete truthful decision log is the defense.
- THALES treats spoof footprints (painted walls, flicker at the touch) as
  an **adversary signal to detect**, never a tactic; the v8
  distance-decayed imbalance exists to make OTHER people's painted depth
  worthless to our model.

## Rule 575 class B/C — quote stuffing and reckless disruptive messaging

Our mechanisms: the Kraken REST budget is capped in config
(`rate_limit_per_sec: 3`) and every polling loop is cadence-throttled
(books via websocket; candles at `candle_refresh_sec` with a 3-fetch
per-cycle budget). One resting order per position purpose. There is no
burst-messaging capability in the codebase to misuse.

## Rule 534 — wash trades (self-crossing to fake volume or dodge risk)

The legal test: buy and sell in the same product where the purpose is to
avoid a bona fide position exposed to market risk; includes different
accounts under common beneficial ownership.

Our reality: single account, single execution venue. Entries are deduped
per asset by the risk-firewall duplicate window; exits act only on held
positions (risk-reducing, definitionally bona fide). We also INGEST
wash-trading research defensively (Cong-Li-Tang-Yang 2023): v8 re-grounds
candle volume on the execution venue so the model never learns from
fabricated external volume.

**Open item, now named and closed for the long book (market-conduct pass,
task F6):** the specific mechanism the review identified is the
long-horizon accumulation book (`risk/long_book.py`, Compounder Phase C)
resting a same-pair BUY entry for up to `order_ttl_hours` while the 5m
book's risk-off exit escalation ladder (`main._submit_exit`, touch ×
(1 − slip) widening 0.5% → 3% → a terminal market order) — or a
marketable short-entry/hedge-open SELL (`main._hedge_actions`' "open"
branch) — reaches down through the book far enough to trade against it:
a literal self-fill, or the venue's self-trade-prevention (STP)
cancelling the escape leg instead of the entry.
`main._clear_long_book_bid_before_sell` is now wired into all four call
sites: it cancels our own resting long-book bid on that pair FIRST, before any
non-`post_only` (marketable) sell is submitted, coded `LB-022`
(`Code.LB_BID_CLEARED`) with the exit's `reason_code` carried in the
audit payload. The four wired sites are: (1) exit ladder in `_submit_exit`,
(2) hedge open in `_hedge_actions`, (3) direct taker entry in `cycle_once`,
and (4) algo-child taker entry in `_submit_algo_child`. A `post_only` maker
exit is deliberately exempt — a resting ask can never cross the book, so
passive-passive same-pair quoting (our own bid alongside our own maker exit)
is bona fide two-sided market making, not the wash-trade pattern this rule
targets. Cancel failure never blocks the sell (logged and swallowed); the
venue's own STP remains the documented backstop for the residual race
between the cancel check and the sell landing. This closes the open
item for the one book capable of resting a same-pair entry long enough
to matter (the 5m book's own entries and exits do not coexist on this
timescale); any future book that rests entries for hours must be wired
into the same guard before ARM LIVE.

## Position limits / large-trader analogs

Spot crypto has no CME-style position limits, so we impose our own:
inventory caps, portfolio heat cap, per-asset concentration bounds, and
the CVaR/gap/budget/heat protocol stack — all config-guarded. These are
the self-regulatory analog of exchange position accountability, and they
are enforced in code, not policy.

## Recordkeeping

CFTC-grade reconstruction is the standard the audit layer was built to:
hash-chained JSONL audit trail with registered reason codes on every
disposition, per-fill implementation-shortfall ledger, per-retrain model
history, and checksummed state snapshots. If a regulator asked "why did
the bot do X at time T," the answer is a file, not a recollection.

## Standing invariants that keep all of this true

`system.dry_run` defaults true with a typed ARM LIVE ceremony as the only
path live; Kraken is the sole execution venue; withdrawals are impossible
at the API-deny-list layer; entries are limit-only; exits are always
allowed. Any change that would weaken a mechanism above is a CLAUDE.md
hard-invariant violation and must be refused — including by AI agents
working on this repo (see `.claude/agents/market-conduct-compliance.md`).
