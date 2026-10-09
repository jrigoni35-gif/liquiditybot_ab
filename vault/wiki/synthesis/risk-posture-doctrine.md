---
title: Risk-Posture Doctrine
category: synthesis
summary: "Operator directive 2026-08-02: trade as if real rent-money is on the line at all times — the survival floor is inviolable and already mechanized, AND idle capital also fails the rent test; rent gets paid through profitable trades, so calculated (EV-positive by measurement) risk is mandatory — never a loosened floor"
tags: [doctrine, risk, posture, operator-directive, rent, paper-mode]
sources: 3
updated: 2026-08-07
---

# Risk-Posture Doctrine

## The directive
Issued by the operator 2026-08-02, filed same-session under
[[synthesis/governance-doctrine|governance rule 12]] ([[sources/session-20260802-digest]] third
addendum). Verbatim intent:

> The bot must trade as if **real rent-money is on the line at all times** — vigilant to never
> miss rent because of a bad trade — **AND** it must know that rent gets paid **through
> profitable trades**, so it cannot be afraid of calculated risk.

This is a **two-sided mandate**. Either side alone is a failure mode: survival-only produces a
bot too frightened to earn the rent; deployment-only produces a bot that loses it.

## Side 1 — survival is inviolable, and already mechanized
The survival side is not aspiration; each clause is enforced in code:

- **Daily 5% loss brake**, sitting *below* the **15% hard-stop parachute** —
  [[entities/config-guard]] enforces the ladder ordering as a FATAL startup check: **"the daily
  brake must engage before the parachute."**
- **Weekly loss budget.**
- **Portfolio heat hard-veto.**
- **Give-back ratchet** (banked profit is defended).
- **Loss-streak cooldown.**

These sit on top of the seven hard invariants ([[entities/liquiditybot]]): kill switches block
new risk and never block escapes ([[concepts/protective-senior-overlay]]).

## Side 2 — idle capital also fails the rent test
Never losing is not the goal; **paying the rent is**. The deployment side is equally concrete:

- The goals ledger's **`monthly_profit_goal_usd` IS the rent number** — and it must be
  qualified by capital regime: 110 at the 2026-07-24 [[sources/goals-mindset-review]], raised
  to 350, and **since 2026-08-10T23:05:27Z (the $800 stressor,
  [[sources/session-20260810-stressor-epoch]]) it is `100` on `starting_capital_usd = 800`,
  escalated by the RP-072 ladder** — effective goal = 100 × persisted `goal_ladder_mult`, a
  month closing ≥100% of its effective goal ratchets ×1.5, never de-escalates, graded before
  escalated. Grading/telemetry only; no trading decision reads the multiplier.
- **Gates learn from realized P&L — money, not barrier touches — since commits
  `07d38a51`/`162c595c`.** "Profit is the ground truth" is implemented in code, not aspiration:
  a gate that starves the book of EV-positive trades is a defect on this side of the mandate,
  symmetric to a gate that admits EV-negative ones. **Proven working end-to-end in production
  2026-08-04 late:** `ml.gate_stats.realized_closed` moved **0 → 1** on the first organic
  post-restart close — gates → `order.meta` → position → close → era-keyed ledger, with
  `realized_active` correctly False at 1/25 toward activation
  ([[sources/session-20260804-deploy-gate]] §6). *Accruing as of 08-05:* `realized_closed`
  **3**, `realized_base_rate` **0.3333**, **3/25 toward activation**.
- A bot that idles when measured EV-positive trades exist is missing rent exactly as surely as
  one that donates it in bad trades.

## What "calculated risk" means here
**EV-positive by measurement, under the survival constraints — never loosening the floor to make
trades happen.** Deployment pressure is answered by *finding measured edge* (the cost stack,
pooling — [[synthesis/the-money-path-thesis]]), not by relaxing brakes; relaxing a brake to
generate activity is exactly the move [[concepts/never-widen-a-gate]] forbids.

## The tension it currently governs
As of 2026-08-02 the measured reality is: per-trade EV is **negative**
([[concepts/payoff-asymmetry]], n=217), no entry-timing signal, no surviving bracket geometry.
Under this doctrine, the paper book **starving under honest fills**
(`passive_base_prob` 0.45 → 0.048, commit `8e5455e8`) is a **truthful outcome, not a failure to
deploy** — the rent test is failed by bad trades *and* by idle capital, and only measurement can
say which failure you are in. Re-flattering the simulator to restore activity would fail both
sides at once.

**First measurement of the starving prediction (2026-08-03,
[[sources/session-20260803-bug-sweep]]):** the first full day under honest fills produced
**~8 positions/day vs ~16 before** — the book starves to **half** rate, it does not die — with
exits flowing (2 stale-loser purges including a 100h ETH position; `tb_time` verticals firing)
and equity at **$4,930.79**. The truthful-outcome reading holds on day one: reduced activity,
functioning exits, no re-flattering.

## The $800 stressor regime (2026-08-10) — the rent test, made harder on purpose

Operator-adjudicated 2026-08-10 (verbatim: *"putting it through this stressor will see what we
have right and what is completely wrong"*; *"as it starts to succeed, scale the profits to the
most it can stress every month"*): capital 5000 → **800** at 2026-08-10T23:05:27Z, goals
25/week and 100/month with the ×1.5 ratchet, **venue floors deliberately UNSCALED** — the $15
minimum ticket is now **1.9% of equity per ticket, and the bite IS the stressor**. Percentage
knobs are scale-invariant and unchanged; the survival ladder (daily brake below the parachute,
weekly budget, heat veto, give-back ratchet, streak cooldown) rescales with equity by
construction.

**The honesty line travels with the regime** ([[sources/session-20260810-stressor-epoch]] §6):
config can point the goals ledger at $100/month and measure against it honestly — **nothing in
the config makes a book with no measured gross edge EARN it.** The expected outcome, stated in
the commit itself, is the truth arriving faster and louder. This doctrine's two-sided mandate
is unchanged: a book that starves at $800 under honest floors is a truthful outcome; a book
that donates its equity to 1.9% floors is the measured answer to "what is completely wrong."
The verdict instrument is the pre-registered era-4 gate
([[synthesis/governance-doctrine]] rule 17), not this page.

## The frame this doctrine lives inside (2026-08-07)

**No real rent-money is on the line — and that is precisely why this doctrine exists.** The
bot executes no real bids or positions ([[concepts/paper-real-boundary]], operator directive,
governance rule 13): every fill, fee and dollar here is simulated. The "as if real rent-money"
posture is a **deliberate rehearsal** — it only earns its keep if the paper environment is
never allowed to flatter (honest fills, honest absence) and its numbers are never mistaken
for venue truth. Both sides of the mandate are rehearsal targets: the survival mechanisms are
real code that will carry over unchanged; the "rent" being earned is, for now, evidence.

## Sibling doctrines
[[synthesis/governance-doctrine]] — *how* change is allowed to happen ·
[[synthesis/manipulation-defense-doctrine]] — *whom* we trade against ·
[[concepts/paper-real-boundary]] — *where* the evidence for all three lives ·
this page — *why* we trade at all, and how much risk is mandatory.

## Related
[[sources/session-20260802-digest]] · [[entities/config-guard]] ·
[[sources/goals-mindset-review]] · [[concepts/payoff-asymmetry]] ·
[[concepts/never-widen-a-gate]] · [[entities/liquiditybot]]
