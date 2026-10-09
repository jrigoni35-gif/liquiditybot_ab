---
title: Cost Imposition
category: concept
summary: Devaluing the cheap version of an adversary's tactic so it stops paying against your book specifically, rather than merely detecting it
tags: [manipulation, defense, game-theory]
sources: 1
updated: 2026-08-01
---

# Cost Imposition

## Definition
Rather than only *detecting* a manipulative tactic, structure your own valuation so the **cheap** form
of the tactic stops working against you — forcing the adversary toward the **expensive** form.

## The instance
Rational-choice theory predicts a manipulator prefers resting size **away from the touch**: nearly free
to place and cancel, never at execution risk. Size **at the touch** carries real fill risk.

The distance-decayed order-book imbalance weights notional far from the touch toward zero. So:

> "Painting a wall away from the touch — the RCT-optimal, low-cost tactic — stops paying off against
> this bot specifically. **That is cost-imposition, not just detection**: the manipulator is pushed
> toward painting *at* the touch, where the tactic becomes expensive."

## The scoping insight
> "The bot cannot change other actors' detection probability, only its own exposure — **the only lever a
> single market participant actually has over another actor's calculus** is zeroing the manipulator's
> expected gain *from this specific counterparty*."

This is why the whole defense posture is **exposure-limiting, not group-detecting**: the bot is a
counterparty, not a surveillance system.

## The model it protects
[[entities/avellaneda-stoikov]] quoting rests on book state that this posture keeps honest;
[[entities/read-only-venues]] supply the cross-venue corroboration.

## The convergence worth noting
This posture was derived **twice, from two epistemic directions** — bottom-up from microstructure
papers, and top-down from criminology — and both landed on veto-only, shadow-first, self-muting, with
the regulated execution venue as trust anchor. See [[synthesis/manipulation-defense-doctrine]].
