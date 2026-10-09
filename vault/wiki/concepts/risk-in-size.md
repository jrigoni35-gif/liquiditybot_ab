---
title: Risk-in-Size
category: concept
summary: Resizing notional inversely with stop distance so dollar risk stays constant as bracket geometry widens
tags: [sizing, risk, brackets]
sources: 1
updated: 2026-08-01
---

# Risk-in-Size

## Definition
When an entry's bracket is computed from its own volatility and cost, the stop distance varies per
trade. **Notional is scaled inversely with `sl_pct`** so the dollar risk of the trade matches the
legacy fixed-stop trade rather than growing with the stop.

## The safety clamp
The pre-trade-approved size is a **hard ceiling** on the geometry-rescaled size: the rescale ratio is
clamped at 1.0, **downscale only**. Geometry may shrink a position but can never grow it past what the
risk stack already approved.

## Why the clamp matters
Without it, a narrow stop would justify a larger notional than the pre-trade gate ever certified —
turning a labeling-alignment change into a silent size increase. The clamp is pinned by an
exact-equality test.

## Adjacent honesty fix
Entry log lines were printing the **uncapped** pre-clamp size rather than the size actually approved —
"display-only dishonesty", corrected in the same task.

## Related
[[sources/geometry-alignment-adjudication]] · [[entities/pretrade-gate]] ·
[[concepts/triple-barrier-labeling]]
