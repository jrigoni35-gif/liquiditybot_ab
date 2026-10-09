---
title: "Calendar-Anchored State Straddling a Capital Epoch (a regime change is not a loss)"
category: concept
summary: "Persisted state that anchors on CALENDAR keys (ISO day/week/month) while denominating in DOLLARS silently asserts that the dollar regime is constant within the calendar period. A capital epoch breaks that assertion mid-period, and every calendar-anchored dollar statistic read across it books the regime change as trading performance. Sibling of pooled-populations — the straddled anchor is a one-number pool of two capital regimes, and where pooling produces a mean that describes neither, the straddled anchor produced a LOSS that never happened: the 2026-08-12 type specimen read the $800 reset against the W33 anchor of 4614.22 as an 82.7% in-week loss = 1378% of the 6% weekly budget, and RP-041 hard-vetoed all new risk for 25 hours (118 candidates, zero entries), with no restart able to clear it and no natural expiry until the next Monday. The blast radius scales with the calendar horizon remaining: the day anchor self-healed at its next daily key roll ('day 0%, week 1378%'), the week anchor would have held 6.8 days. Rule: a capital reset is a REGIME CHANGE, not a loss — every calendar/dollar-anchored persisted section must re-anchor in the same sweep, keys preserved"
tags: [risk-protocols, budgets, capital-epoch, persistence, state, incident-class, statistics]
sources: 1
updated: 2026-08-11
---

# Calendar-Anchored State Straddling a Capital Epoch

## The claim

State that is **anchored to the calendar** (a value stamped at an ISO day/week/month key roll)
and **denominated in dollars** carries an unstated assumption: *the dollar regime is constant
for the life of the calendar period.* A **capital epoch** — an operator-adjudicated reset of
the money base ([[synthesis/comparability-boundaries]], cut (v)) — breaks that assumption
mid-period. Every calendar-anchored dollar statistic that reads across the epoch then books
the **regime change itself as trading performance**.

This is [[concepts/pooled-populations]]'s sibling, one representation down: the pooled
statistic merges two populations into a mean that describes neither; the straddled anchor
merges two capital regimes into **one number** — and a derived "loss" that occurred in
**neither** regime. Pooling can understate (5.6x), fabricate (7.04x revenge sizing), and now —
in the anchor form — **veto**: the fabricated statistic was wired to a hard protective action.

## The type specimen (2026-08-12, [[sources/session-20260812-weekly-anchor-lockout]])

- Monday `2026-08-10T00:00Z`: W33 key roll stamps `week_anchor = 4614.22` (pre-reset equity).
- Same day `23:05:27Z`: the $800 capital reset zeroes the money ledgers — the sweep does not
  know the `risk_protocols` anchors exist.
- From then: `(4614.22 − 800)/4614.22 = 82.7%` reads as an in-week trading loss = **1378%**
  of the 6% weekly budget → **RP-041 hard veto on ALL new risk**. **118 candidates, zero
  entry orders, 25h 9m.** Persistence restores the poisoned anchor on every restart; the
  natural re-seed was the *next* Monday — the stressor's whole first week would have been
  lost.

**The loss was phantom.** No trade lost anything; the anchor and the equity were measured in
different worlds. Contrast the class's *cousin*, the first weekly-budget poisoning
([[sources/session-20260808-budget-reanchor]]): there the **consumption** was poisoned (real
fees from a dead bug) and the anchor was true; here the **anchor** was poisoned and the
consumption was zero. Both times the protective layer worked exactly as designed on poisoned
input ([[concepts/protective-senior-overlay]]'s mirror).

## The blast-radius rule: the calendar horizon IS the exposure

The same reset poisoned the **day** anchor identically — and it **self-healed at its next
daily key roll**, which is why the incident reading says *"day 0%, week 1378%"*. Poison in
calendar-anchored state persists until the next key roll:

| anchor horizon | poison lifetime after an epoch |
|---|---|
| day | until next midnight (minutes to hours) |
| week | up to ~7 days (6.8 days in the specimen) |
| month | up to ~31 days |

The quieter the calendar, the longer poisoned state governs — and a **veto** produces
*absence* of behavior, the hardest signal to notice ([[concepts/zero-is-not-a-reading]]): this
member of [[concepts/reset-completeness]] was found by 25 hours of production silence, not by
audit.

## The rule

**A capital reset is a REGIME CHANGE, not a loss.** Every persisted section that anchors on
the calendar and denominates in dollars must **re-anchor to the new capital in the same
sweep** — keys preserved, so natural rollover keeps working. Enumerating those sections is the
class-closing fix (owed 72, [[synthesis/owed-measurements]]); handling them one incident at a
time is how the class yielded three members in three days.

Candidates for membership are recognizable by signature: *a value stamped at a key roll* +
*compared against live equity/dollars later*. The weekly/daily loss-budget anchors were the
live instance; the perf window and money counters were swept by design at the same reset
([[sources/session-20260810-stressor-epoch]] §6); anything added later with the same signature
is born a member.

## Related

[[sources/session-20260812-weekly-anchor-lockout]] · [[concepts/pooled-populations]] ·
[[concepts/reset-completeness]] · [[sources/session-20260808-budget-reanchor]] ·
[[sources/session-20260810-stressor-epoch]] · [[concepts/protective-senior-overlay]] ·
[[concepts/zero-is-not-a-reading]] · [[synthesis/comparability-boundaries]] ·
[[synthesis/owed-measurements]]
