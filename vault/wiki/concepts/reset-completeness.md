---
title: "Reset Completeness (a reset script's sweep list is a schema)"
category: concept
summary: "A capital-reset script's list of what to zero/re-anchor is a SCHEMA that must be maintained with the state it resets — and membership is discovered by incident unless enumerated. Three members in three days, each harder to see than the last: (1) monthly_realized_pnl, which predated the script and survived EVERY prior reset (found 2026-08-10, by audit); (2) entry_fees_total + the dollar-denominated perf window, which would have carried $185.94 and a 6.25x-blended population into the fresh base (same audit — persistence backfill only fires when a key is ABSENT, so a persisted stale value WINS); (3) the risk_protocols loss-budget anchors (day_anchor/week_anchor), found 2026-08-12 by CASUALTY — 25 hours of production silence under RP-041 — because a stale counter shows a wrong number but a stale anchor vetoes silently. The class-closing fix is a completeness test enumerating every calendar/dollar-anchored persisted section and asserting reset_portfolio() handles each (owed 72); until it exists the class is expected to keep yielding"
tags: [reset, capital-epoch, persistence, state, schema, incident-class, testing]
sources: 2
updated: 2026-08-11
---

# Reset Completeness

## The claim

A reset script's sweep list — what it zeroes, what it re-anchors, what it deliberately
preserves — **is a schema, and it must be maintained with the state it resets**. The rule was
first stated in miniature at the $800 stressor reset
([[sources/session-20260810-stressor-epoch]] §6: *"a reset script's zero-list is a SCHEMA"*);
what three days of members have added is the harder half: **membership is discovered by
incident unless it is enumerated.** "We swept everything" and "nothing unswept can exist" are
different claims — [[concepts/adoption-is-not-enforcement]], applied to a state sweep.

The structural trap underneath (same audit): **persistence's backfill only fires when a key is
ABSENT — a persisted stale value WINS.** So a reset that misses a section does not produce a
default; it produces a confidently wrong number wearing valid schema.

## The members, in discovery order — each harder to see than the last

| # | member | found | how it surfaced |
|---|---|---|---|
| 1 | `monthly_realized_pnl` | 2026-08-10, **by audit** of the $800 reset | predated the script; **survived EVERY prior reset** — a wrong number on a board |
| 2 | `entry_fees_total` + the dollar-denominated **perf window** | same audit | would have carried **$185.94** of old-regime fees (breaking `net_pnl_all_time = equity − start` on day one) and a **6.25x**-blended window ([[concepts/pooled-populations]] on live boards) |
| 3 | the `risk_protocols` **loss-budget anchors** (`day_anchor`/`week_anchor`) | 2026-08-12, **by casualty** | **25 hours of production silence** — RP-041 hard-vetoed all new risk off a phantom 82.7% "loss" ([[sources/session-20260812-weekly-anchor-lockout]]) |

The gradient across the members is the lesson: a stale **counter** shows a wrong number
(visible whenever someone looks); a stale **total** breaks an identity on day one (visible the
first time the identity is checked); a stale **anchor** **vetoes silently** — it produces
*absence* of behavior, discoverable only by noticing that nothing happened
([[concepts/zero-is-not-a-reading]], [[concepts/calendar-anchored-state]]).

## The fix that closes the class, not the instance

Members 1-3 were each fixed at discovery (`_MONEY_ZERO` extended; the perf-window sweep; the
anchor re-anchor now shipped in `reset_portfolio()` with keys preserved, pinned by
`tests/test_reset_paper_capital.py`). But per-member fixes are the instance-level move. The
class-level move — registered as **owed 72** ([[synthesis/owed-measurements]]) — is a
**completeness test that enumerates every calendar/dollar-anchored persisted section** and
asserts the reset handles each: sweep it, re-anchor it, or name it as deliberately preserved
(the corpus, the fills ledger, and learning artifacts are preserved **by governance rule 8**,
not by omission — the enumeration must distinguish *decided* from *forgotten*).

Membership signature to enumerate against: *persisted* + (*denominated in dollars of OUR
capital* or *anchored at a calendar key roll*). Anything added later with that signature is
born a member; until the enumeration exists, the class — three members in three days — is
expected to keep yielding.

## Related

[[sources/session-20260810-stressor-epoch]] · [[sources/session-20260812-weekly-anchor-lockout]] ·
[[concepts/calendar-anchored-state]] · [[concepts/adoption-is-not-enforcement]] ·
[[concepts/default-path-fallback-writes]] · [[concepts/pooled-populations]] ·
[[concepts/zero-is-not-a-reading]] · [[synthesis/owed-measurements]] ·
[[synthesis/governance-doctrine]]
