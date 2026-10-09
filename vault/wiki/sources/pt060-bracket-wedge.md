---
title: PT-060 Bracket Wedge (2026-07-29)
category: source
summary: A live bleed incident traced to a design interaction that suppressed the no-progress time stop fleet-wide, leaving positions unprotected in a 36-to-96-bar gap
tags: [incident, pt-060, exits, seniority]
sources: 1
updated: 2026-08-01
---

# PT-060 Bracket Wedge (2026-07-29)

**Raw source:** `raw/quant/2026-07-29_pt060_bracket_wedge.md`

## The incident
Position `3ea2a851` — LINK/USD short, paper probe, ~$12 notional. From bar 42 the feed logged
`PT-060: LINK/USD time-stop: no favorable progress` **every ~5s for ~2 hours (~1,900 lines) with
ZERO exit order submissions**. The first exit order was created **1.4 seconds after a restart**.
Realized **-1.69% vs expected -0.08%**; the PT-060 scratch at bar 36 would have taken **~-0.2%**.

## Root cause — the wedge
`_manage_open_position` suppressed **BOTH** the scheduled profit-take AND the PT-060 time stop for
bracket positions, handing the time dimension to the bracket deadline leg. But PT-060 fires at
`max_bars_no_progress = 36` bars (3h) while the bracket deadline is `label_max_bars = 96` bars (8h).
**The 60-bar gap is the wedge.** Since probes are ~all model-lane flow, this disabled no-progress
protection **fleet-wide**; fake-out entries pay ~8-20x the intended scratch cost.

The PT-060 cohort derivation: MFE 0.16% / MAE -1.44%, `recovered_after_stop` **0/17**.

## Fix
`suppressed_for_bracket` now covers **only** the scheduled profit-take. PT-060 is reclassified as a
**[[concepts/protective-senior-overlay]]** — same seniority class as the give-back ratchet and hard
stop, per the invariant "exits always allowed; blocks never escapes."

Log hygiene fixed separately: PT-060 announces once per position while the ACTION still fires every
cycle; correlation-shift logs a compact top-3 once per episode; probe-throttle logs at most once per
asset per 10 min while the audit record stays per-event.

## The design choice that backfired
PT-060 closes deliberately keep `barrier="realized"`, never `tb_*`, "so there is no tb-era
contamination." Two days later [[sources/live-label-era-deadlock]] identifies exactly this as the
[[concepts/clock-inversion]] starving the tb era of live labels — PT-060 at bar 36 vs the vertical at
bar 96. Resolution: don't move PT-060, move the vertical.
