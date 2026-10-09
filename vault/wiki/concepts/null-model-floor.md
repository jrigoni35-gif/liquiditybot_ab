---
title: Null-Model Floor
category: concept
summary: A proposed battery gate requiring every model rung to beat a constant base-rate predictor, because nothing in the battery currently reports that they do not
tags: [gates, measurement, owed]
sources: 2
updated: 2026-08-01
---

# Null-Model Floor

## The finding that motivates it
Two independent analyses converged: **every model rung loses to a base-rate constant.**

| Model | Brier | Constant-prior Brier |
|---|---|---|
| deployed logistic (OOF) | 0.2736 | 0.1936 |
| gbt (the option-A unlock) | 0.2355 | 0.1959 |
| tb-model scored on live rows | 0.2124 | 0.1393 |

A live-only model scores **OOS AUC 0.4375 — worse than random**.

> **"Nothing in the battery currently reports this."**

## The gate
Require every rung to beat a constant/base-rate predictor before it is admissible. Adjudicated
**SHIP** — "the gate cannot keep hiding that every rung loses to a constant."

## Why the existing battery missed it
[[concepts/overfit-battery|OF-1..OF-8]] measures memorization gaps, selection luck, leakage, and
degrees of freedom — all *relative* quantities. None of them asks the absolute question "is this better
than predicting the base rate?" A battery can be 5-passed-of-8 green while every candidate is worse
than a constant.

## The economic explanation
Supplied a day later by [[concepts/cost-to-volatility-ratio]]: at cost/sigma = 0.82 there is no
learnable edge to find, so the null-model failure is a *symptom*, not a modelling error.

## Status
**Adjudicated SHIP; not yet shipped** as of the last document in the corpus.
