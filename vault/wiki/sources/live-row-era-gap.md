---
title: Live Row Era Gap (2026-07-27)
category: source
summary: Verifies the era map is a pure source-agnostic function of the barrier string, then quantifies the hole: 100% of in-scope live rows are old-era
tags: [label-era, live-rows, verification]
sources: 1
updated: 2026-08-01
---

# Live Row Era Gap (2026-07-27)

**Raw source:** `raw/quant/2026-07-27_live_row_era_gap.md`

## Verification
`label_era_of` keys only off `barrier`, never `source`. Two pinned tests passed immediately —
**10 runs of 10 (20 executions), all green, 0 flakes, no code change**.
`_TRIPLE_BARRIER_BARRIERS = {tb_pt, tb_sl, tb_time}` and
`_EXIT_SIM_BARRIERS = {trail, realized, tier, floor, sl, time}` form a disjoint-vocabulary
partition — a [[concepts/label-era|source-agnostic era map]], not a per-source rule.

## The hole
Corpus 4,989 rows (4,747 candidate + 242 live). Authoritative loader view: 1 live row is `book=="long"`
and out of scope, leaving **241 in-scope live rows, 100% old-era**. New-era rows = **58, entirely
candidate-side** (`tb_pt` 36, `tb_sl` 22, no `tb_time` yet). Against `min_new_era_rows = 150` the
filter is `armed: false, active: false`.

## Mechanism
`HistoryStore.log_close` **always writes the fixed string `barrier="realized"`** — never the actual
exit reason, never a `tb_*` string, regardless of `ml.label_mode`. Rationale in the code comment: "a
live fill has no barrier vocabulary of its own."

## Disposition
No code, config, or corpus change. Closure delegated to a later task that changes only what
`log_close` *emits* — **the era map must not be touched**. That closure is declared in
[[sources/geometry-alignment-adjudication]] and shown to have failed in
[[sources/live-label-era-deadlock]].
