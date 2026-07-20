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

**Open item (pre-live checklist):** there is no explicit mechanical guard
asserting that a resting BUY entry and a resting SELL exit can never
coexist on the same pair. Today's flow makes it unlikely (per-asset entry
dedupe; exits attach to positions), but before ARM LIVE this should become
a firewall invariant with a registered reason code, not an emergent
property.

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
