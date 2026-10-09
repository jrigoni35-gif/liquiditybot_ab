---
title: The Pre-Trade Gate
category: entity
summary: "The decision-time cost gate requiring edge to clear fees, spread, book-walk, impact and adverse selection, weighted by fill probability — and, as of 2026-08-09, the gate whose staleness veto (PT-020) finally measures real data age, with the CRITICAL-latent VETO BAND that discovery exposed now closed: a cache ceiling ABOVE the veto ceiling served doomed books that preempted fresh REST reads on ~0.6-3% of entry evaluations, worst on the thinnest pairs"
tags: [module, execution, cost, staleness, incident]
sources: 7
updated: 2026-08-09
---

# The Pre-Trade Gate

The last veto before an order is submitted, and the system's cost-truth boundary.

## The cost stack
Edge must clear **fees + spread + book-walk + sqrt-impact + adverse selection**, weighted by fill
probability. Exits are exempt from the edge gate (risk reduction is never blocked) but slippage-capped.

## Named guarantees
- A passive round trip is **never net-negative by construction** — the half-spread floor is at least the
  maker fee plus a margin.
- **Urgency is a placement preference, never an EV bypass** — a taker entry clears the FULL taker cost
  stack.
- Adverse selection is charged explicitly, not assumed away.

## Its role in the counterparty thesis
It is half of the stated classifier between flow we monetize and flow we avoid: **"priced adverse
selection plus THALES, not confidence."** See [[concepts/who-loses-to-us]].

## Audited defects
- With a one-sided venue book but a healthy combined book, the spread veto read the **combined** book,
  the fill probability defaulted to the **optimistic** value, and the participation clamp **silently
  no-op'd at zero depth**.
- Book-walk cost returned **0.0 instead of the veto sentinel** when the walked side was wholly empty —
  so a taker entry against a fully one-sided book got **zero walk cost instead of a veto**.
- A shipped default for the half-spread floor was **4 bps against a configured 26** — which would not
  clear a 25 bps maker fee, undermining the never-net-negative guarantee.

## The staleness veto (PT-020) and the VETO BAND — 2026-08-08/09

The gate's `max_data_staleness_ms` = **4000ms** ceiling was **arithmetically dead for
months** — `book_ts` was stamped with the same cycle-frozen `now` it was compared against,
so `staleness_ms` read ~0 forever ([[concepts/tautological-instrument]]). `36fcfd6e` (owed
42a) resurrected it by making `book_ts` **data time** — the feed's own receive stamp.

**That fix immediately exposed a CRITICAL-latent defect in the layer above it: a VETO
BAND.**

`websockets.kraken_max_book_age_sec` = **5.0s** was **greater than**
`pretrade.max_data_staleness_ms` = **4000ms**. So a ws book aged **4–5s** sits in a band
where it is:

1. **SERVED** by the cache (under the cache's 5.0s ceiling), and then
2. **VETOED** by PT-020 (over the gate's 4.0s ceiling) —

and, because `main.py` falls back to REST **only when the ws returns `None`**, that doomed
book **PREEMPTS a REST read that would have been fresh**. The entry is not delayed; it is
**silently refused**, and a fresh book that was one call away is never fetched.

**Exposure ~0.6–3% of entry evaluations**, concentrated exactly where the book updates
least often: **MINA 3.2% · FLOW 2.9% · PAXG/LINK 1.9% · BTC 0.6%**. The consequence is
worse than the rate suggests — **it skews WHICH ASSETS can accumulate fill labels at all**,
which is a corpus-composition defect wearing a latency costume.

**Masked only because the book was full 5/5** at audit time, making the pre-trade path
unreachable; **it would have armed the moment a position closed.**

**FIX (`3c0debd7`):** `5.0 → 3.5` **plus a `config_guard` FATAL on the relation itself** —
the invariant, not the value, is what is now enforced (verified two-sided: it FATALs the old
config and passes the new). 3.5 leaves headroom for the measured cycle read delay (p50
**0.34s**, p90 **0.68s**) and costs ~**0.6** extra REST book calls/cycle against a **15**/cycle
budget. The knob carries its own directive: **"Lower this knob rather than raising the veto
ceiling"** — [[concepts/never-widen-a-gate]] written into the config file.

> **The general shape, worth carrying to every other gate here:** when a **producer's
> freshness ceiling exceeds a consumer's freshness ceiling**, the difference is not slack —
> it is a **band of data that is guaranteed to be fetched and guaranteed to be rejected**.
> Two independently-reasonable numbers, in two different files, with no relation between
> them asserted anywhere. And the failure is invisible while a *third* condition (a full
> book) keeps the consumer unreachable — so it waits for the system's ordinary operation to
> resume before it starts costing anything.

**Known limit inherited from 42a:** on the **REST path** the new measurement is
**sign-inverted** (`now` frozen at cycle start, `recv_ts` stamped after the blocking fetch →
`staleness_ms <= 0`), so **PT-020's resurrection is real on the WS path only**
([[synthesis/owed-measurements]] item 42(a-i)).

## The unresolved cost question
The gate is configured at 65 bps round trip; measurement says 86 bps; the labeler assumes 50 bps. See
[[concepts/cost-truth]].

## Related
[[concepts/tautological-instrument]] · [[entities/config-guard]] ·
[[concepts/never-widen-a-gate]] · [[concepts/cost-truth]] · [[concepts/who-loses-to-us]] ·
[[concepts/zero-is-not-a-reading]] · [[sources/session-20260809-corpus-corruption]] ·
[[sources/session-20260808-night-staleness-overfit]]
