---
title: "The 25-Hour No-Trade Lockout (2026-08-12 UTC) — the Capital Epoch Poisons the Weekly Loss-Budget Anchor, RP-041 Vetoes Everything, and the Reset Sweep Grows a Third Member"
category: source
summary: "Operator-triggered ('it didnt even trade'): from the $800 capital epoch (2026-08-10T23:05:27Z) to repair (2026-08-12T00:14:10Z = 2026-08-11 19:14 −05:00), 25h 9m, 118 entry candidates, ZERO entry orders. ROOT CAUSE: the weekly loss budget measures from a persisted equity anchor (risk/protocols.py spent_fracs); ISO week key W33 rolled Monday 2026-08-10T00:00Z stamping week_anchor=4614.22 (pre-reset equity), the 23:05Z reset zeroed money ledgers but never re-anchored, so (4614−800)/4614 = 82.7% read as an in-week trading loss = 1378% of the 6% weekly budget → RP-041 hard veto (0.0 multiplier) on ALL new risk. Persistence restored the anchor on every restart; no natural re-seed until Monday 2026-08-17 — the stressor's whole first week would have been lost. Confirmed LIVE, not reconstructed: 1,026 RP-041 events, the last ('day 0%, week 1378%') 75s before the repair. REPAIR: budget_reanchor_week (the verb built for this class's FIRST instance, 2026-08-08) with bug-attribution reason, RP-042 audit seq 44429, week_anchor=800.0 verified persisted. PREVENTION: reset_paper_capital.py reset_portfolio() now re-anchors day_anchor/week_anchor (keys preserved), pinned in tests/test_reset_paper_capital.py — the reset-completeness class's THIRD member, first found by casualty rather than audit. CLASS: calendar-anchored state straddling a capital epoch (sibling of pooled-populations). SECONDARY: veto-stack dispositions 60 capped (source unpinned, owed 70) / 22 SZ-022 / 21 SZ-023 (p_win 0.34–0.40 vs 0.69 breakeven bar — survives the repair) / 9 SZ-060 / 1 SZ-050 anomaly (dd 7.9% while flat, MTM base ~737 — owed 71); buckets sum 113 of 118. 118 candidates' h432 sim labels 62W/56L = 52.5% — lead only. SPB-R board mirror: probe tokens pinned 4.88/5.00, labels/day 0."
tags: [session, incident, risk-protocols, budgets, capital-epoch, stressor, control-channel, reset-completeness, veto-stack, ops]
sources: 1
source_path: none — live-box incident record (events.jsonl, audit.jsonl, status.json), re-verified against the box at filing
source_date: 2026-08
authors: [operator, claude-session]
ingested: 2026-08-11
updated: 2026-08-11
---

# The 25-Hour No-Trade Lockout (2026-08-12 UTC)

## Provenance and boundary statement

Operator-triggered — verbatim: **"it didnt even trade."** Every claim below **re-verified against
the box at this filing**: `outputs/events.jsonl` (1,026 RP-041 lines; last at ts 1786493575.184 =
2026-08-12T00:12:55Z), `outputs/audit.jsonl` seq 44429 (RP-042, hash-chained
`h b4e9a7275f4299f8` / `prev bead383d96c8808f`), `outputs/status.json`
(`weekly_budget_used_frac` 0.0 at filing), `risk/protocols.py` (:190-191, :210-211, :238-254,
:257-264, :381-390), `scripts/reset_paper_capital.py` (:75-101), and
`tests/test_reset_paper_capital.py` (:85-102, fixture carrying the exact incident numbers).

**Paper/real boundary** ([[concepts/paper-real-boundary]]): every dollar is **sim-side** (the
$800 is simulated capital; the phantom "loss" doubly so — it never existed on ANY axis). The
mechanism and prevention are **repo-side**; the repair is **box-side ops** on the real process.
As with the first instance: **the lockout itself was real** — RP-041 blocked genuine entry
decisions of the running system for 25 hours regardless of which side the dollars live on.

**Zone stamps** (domain rule 9): capital epoch `2026-08-10T23:05:27Z` = 18:05:27 −05:00; W33
key roll `2026-08-10T00:00Z` (Monday) = 2026-08-09 19:00 −05:00; repair
`2026-08-12T00:14:10Z` = 2026-08-11 19:14:10 −05:00. The incident is UTC-dated 08-12; the
filing session is local 08-11.

---

## 1. The mechanism — a regime change read as a trading loss

The weekly loss budget ([[sources/session-20260808-budget-reanchor]] §1 has the arithmetic
template) measures **spent fraction = (anchor − equity) / anchor / budget_pct** from a
**persisted week-open equity anchor** (`risk/protocols.py:257-264 spent_fracs`; anchor stamped
at ISO-week key roll, :210-211; persisted and restored in the `risk_protocols` section,
:381/:388-390).

The timeline that poisoned it:

1. **Monday 2026-08-10T00:00Z** — natural W32→W33 rollover stamps `week_anchor` at the
   pre-reset equity: **4614.22** (persisted value `4614.224876076544`, now immortalized in the
   pin test's fixture).
2. **Monday 2026-08-10T23:05:27Z** — the operator-adjudicated **$800 capital reset**
   ([[sources/session-20260810-stressor-epoch]] §6-8) zeroes every money ledger — **but the
   sweep did not know about the `risk_protocols` anchors.** The anchor stays 4614.22.
3. From that instant: `(4614.22 − 800) / 4614.22 = 82.7%` reads as an **in-week trading
   loss** = **1378% of the 6% weekly budget** → **RP-041 hard veto (0.0 multiplier) on ALL
   new risk**. Exits unaffected (the [[concepts/protective-senior-overlay]] seniority held).
4. **Restarts cannot clear it** — persistence faithfully restores the poisoned anchor every
   boot. The natural re-seed is the **next** key roll: **Monday 2026-08-17T00:00Z**. Without
   intervention, **the stressor's entire first week would have produced zero entries** — and
   with it zero era-4 accrual.

**Result: 118 entry candidates, ZERO entry orders, 25h 9m** (23:05:27Z → 00:14:10Z).

**The calendar horizon is the blast radius**: the DAY anchor was equally poisoned and
self-healed at its next daily key roll — which is why the incident reading shows **"day 0%,
week 1378%"**. A week key holds poison for up to ~7 days; a month-anchored budget would have
held it for weeks. The quieter the calendar, the longer poisoned state governs
([[concepts/calendar-anchored-state]]).

## 2. Confirmed live, not reconstructed

The veto was **caught firing**, minutes before the repair — the last of 1,026 RP-041 event
lines (ts 1786493575.184, 75 seconds before the repair ack):

> `[ADA] sizer veto: SZ-060: x1.10 (book u_long=0.00 u_short=0.00); RP-041: loss budget spent
> (day 0%, week 1378%) — no new risk today; exits unaffected`

This matters for the record: the diagnosis is not a post-hoc reconstruction from state files —
the mechanism was observed **in the act**, then repaired, then observed to stop.

## 3. The class — second instance of the weekly-budget-poisoned class

**[[concepts/calendar-anchored-state]]** — calendar-anchored state straddling a capital epoch,
sibling of [[concepts/pooled-populations]]: a dollar-denominated anchor read across the epoch
is a one-number pool of two capital regimes, and where pooling produces a mean that describes
neither, the straddled anchor produced **a loss that never happened**.

| | First instance (2026-08-08) | Second instance (2026-08-12) |
|---|---|---|
| poisoned side | **consumption** — a dead bug's real ~$303 of W32 fees | **anchor** — a capital reset the sweep missed |
| the anchor | true ($4,940.59 Monday equity) | false (4614.22 pre-reset vs $800 regime) |
| the "loss" | real fees, bug-attributable | **phantom — no trade lost anything** |
| duration | hours (caught same day) | **25h 9m** (caught by the operator noticing silence) |
| natural expiry | W33 roll (would have lost the weekend) | W34 roll 08-17 (would have lost the stressor's first week) |
| repair | `budget_reanchor_week` **first use**, seq 37983 | `budget_reanchor_week` **second use**, seq 44429 |

Both times the protective layer **worked exactly as designed, on poisoned input** — the mirror
of [[concepts/protective-senior-overlay]] noted at the first instance, now a pattern of the
class rather than a property of the incident. And the first instance is **why the repair took
one minute instead of one emergency**: the audited control verb `budget_reanchor_week`
([[sources/session-20260808-budget-reanchor]] §3, `f07d60f8`) existed, reason-required,
RP-042-audited, absent from REST — built for bug-attributable budget consumption, and exactly
fitted to bug-attributable anchor poisoning three days later.

## 4. The repair — live, 2026-08-12T00:14:10Z

Control-channel `budget_reanchor_week`, reason (verbatim, now in the hash chain):

> *"reset-sweep miss: the 2026-08-10T23:05:27Z $800 capital epoch zeroed the money ledgers but
> never re-anchored the weekly loss budget; W33 anchor stayed 4614.22 (pre-reset Monday
> equity), so (4614-800)/4614 = 82.7pct reads as a trading loss = 1378pct of the 6pct weekly
> budget - RP-041 hard-vetoed ALL new risk since the epoch (25h, 0 entries from 118
> candidates). Same BUG-ATTRIBUTABLE class as first use 2026-08-08. Completes the
> operator-adjudicated stressor reset; reset_paper_capital.py patched same session so the
> class dies."*

- **Ack** (runner, ts 1786493650.664): `weekly loss budget re-anchored at $800.00` — full
  reason carried, as designed.
- **Audit**: `audit.jsonl` seq **44429**, code **RP-042**, `data.equity` **800.0**,
  hash-chained (`h b4e9a7275f4299f8` / `prev bead383d96c8808f`).
- **Verified**: `week_anchor = 800.0` persisted; `weekly_budget_used_frac` **0.0** at filing;
  **RP-041 stopped firing** (no lines after the repair ack at filing).

The verb's design constraints all paid on second use: no state-file surgery, the natural W34
rollover keeps working (key refreshed with the anchor), `weekly_pnl` and pools untouched, and
the reason in the audit trail is the incident's own root-cause statement.

## 5. The prevention — the reset sweep grows its third member

`scripts/reset_paper_capital.py reset_portfolio()` now **re-anchors `day_anchor` and
`week_anchor` to the new capital in the same sweep** (:87-92; keys preserved so natural
rollover keeps working), with the incident narrated in the shipped comment — the correction
travels with the code, not just the vault. **Pinned** by
`tests/test_reset_paper_capital.py::test_loss_budget_anchors_reanchor_with_the_capital`
(:85-102), whose fixture carries the exact incident numbers (`week_anchor 4614.224876076544`,
`day_key "2026-08-12"`).

This is the **[[concepts/reset-completeness]] class's THIRD member** in three days — after the
money counters (`monthly_realized_pnl`, `entry_fees_total`) and the performance window
([[sources/session-20260810-stressor-epoch]] §6) — and the first found **by casualty rather
than by audit**: a stale counter shows a wrong number; a stale anchor **vetoes silently**, and
is discovered only when someone notices nothing happened
([[concepts/zero-is-not-a-reading]]). The class-closing move — a completeness test that
**enumerates every calendar/dollar-anchored persisted section** and asserts the reset handles
each — is registered as **owed 72**.

## 6. Secondary findings — the layered veto stack, read while it was dead

The 118 candidate dispositions during the window (session analysis of the incident window;
sim-side):

| disposition | n | reading |
|---|---|---|
| "capped" (`can_enter=False`) | 60 | **source not yet pinned — residual diagnosis owed (owed 70)** |
| SZ-022 bear-regime-blocks-long | 22 | regime gate doing its stated job |
| SZ-023 p_win below breakeven | 21 | p_win **0.34–0.40** vs the **0.69** breakeven bar — honest cost math ([[concepts/cost-truth]]); **remains after the repair**, consistent with [[synthesis/the-money-path-thesis]] |
| SZ-060 | 9 | book-utilization sizer multiplier |
| SZ-050 anomaly | 1 | **dd 7.9% while flat at $800 — MTM base ~737 unexplained**; single occurrence; **owed 71** |

⚠️ *Arithmetic note (filed per the vault's correction discipline): the buckets sum to **113 of
118**; the residual 5 are not broken out in the incident record. The buckets name co-firing
layers observed beside the universal RP-041 veto — they are dispositions, not a partition
proof.*

**The layered stack read correctly through the incident**: RP-041 was wrong (poisoned input),
but SZ-023's breakeven refusals are the same honest arithmetic after the repair as before it —
removing the false veto does not manufacture entries the cost math refuses.

**Label-side lead, filed where mid-accrual reads go**: the 118 candidates' h432 sim labels
resolve **62W/56L = 52.5%** (62+56=118, exact). Small n, sim-side, **a lead only** — no
mid-accrual read is a trend ([[synthesis/governance-doctrine]] rule 17); the era-4 gate remains
sole arbiter.

## 7. The board mirror — SPB-R, and the recovery signature named in advance

The Grafana SPB-R board showed the incident from the **exploration side**: **probe tokens
pinned 4.88/5.00** and **labels/day 0** — tokens accumulate to capacity because nothing is
admitted to spend them, and labels cannot accrue when nothing enters. Not a probe-side defect:
the probe ladder was healthy and starved ([[concepts/probe-livelock]] is the contrast case —
there the cap *causes* the starvation; here the starvation was imposed from the risk layer).

**Recovery signature, named in advance**: tokens **falling** + labels/day **lifting**. At
filing the tokens still read 4.9224/5.00 — recovery not yet visible on the board; verifying it
is part of confirming the repair, not a new owed item.

**Era-4 gate impact**: accrual stands **0/50, unchanged** — the gate population is untouched
(nothing traded, so nothing joined or was excluded); the cost was **calendar** — 25 of the
stressor's first ~168 hours produced no evidence.

## 8. Owed-register deltas from this filing

- **70** — the 60 "capped" (`can_enter=False`) dispositions: pin the source.
- **71** — the SZ-050 anomaly: dd 7.9% while flat at $800, MTM base ~737 unexplained.
- **72** — the reset-completeness test: enumerate every calendar/dollar-anchored persisted
  section; assert the reset sweeps each.

## Related

[[concepts/calendar-anchored-state]] · [[concepts/reset-completeness]] ·
[[sources/session-20260808-budget-reanchor]] · [[sources/session-20260810-stressor-epoch]] ·
[[concepts/pooled-populations]] · [[concepts/protective-senior-overlay]] ·
[[concepts/zero-is-not-a-reading]] · [[concepts/paper-real-boundary]] ·
[[entities/reason-code-registry]] · [[synthesis/owed-measurements]] ·
[[synthesis/the-money-path-thesis]] · [[synthesis/comparability-boundaries]]
