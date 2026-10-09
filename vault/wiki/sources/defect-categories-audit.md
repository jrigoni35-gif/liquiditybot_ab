---
title: Defect Categories Audit (2026-07-29)
category: source
summary: Seven defect categories graded against canonical peer-reviewed anchors; two actionable findings fixed same day, two known-deviations bounded
tags: [audit, estimators, leakage, literature]
sources: 1
updated: 2026-08-01
---

# Defect Categories Audit (2026-07-29)

**Raw source:** `raw/quant/2026-07-29_defect_categories_audit.md`

## Method
Seven defect categories adjacent to the unit/time-scaling class, each graded against **canonical
peer-reviewed anchors** at specific code sites, with CONFORMS / ACTIONABLE / KNOWN-DEVIATION
verdicts. See [[concepts/defect-category-audit]].

## Results by category
1. **Numerical stability** (Welford; Chan-Golub-LeVeque; Higham; Kahan) — mostly CONFORMS; PnL
   accumulators bounded ~1e-7 USD. **ACTIONABLE: OF-5 DSR population moments (ddof=0) inflated SR
   ~+1.7% at n=30**, anti-conservative on a hard gate -> FIXED (ddof=1 across SR/skew/kurt).
2. **Data leakage** (Kaufman-Rosset-Perlich-Stitelman) — CONFORMS throughout. No post-fill feature;
   mark-out is telemetry-only; `signal_ts` is conservative (over-purges).
3. **Survivorship/selection** (Brown-Goetzmann-Ibbotson-Ross RFS 1992; Bailey-Borwein-Lopez de
   Prado-Zhu) — CONFORMS. The skimmer selects on **LIQUIDITY not outcome**; demoted assets' rows stay
   forever; the candidate labeler (labels every confirmed signal, taken or vetoed) is the
   anti-selection instrument by design.
4. **Ratio-aggregation bias** (Cochran ch.6) — **ACTIONABLE**: `avg_slip_bps` was a per-fill
   unweighted mean, so $10 probe fills outvoted 4x conviction notional, ~0.3-0.5 bps rosy -> FIXED
   with `slip_bps_notional_weighted`. Markout has the same shape but its deque is snapshot-persisted
   -> deferred.
5. **Missing-data conventions** (Rubin 1976; Little & Rubin) — KNOWN-DEVIATION, bounded. The hazard
   is only at the feed-alive TRANSITION. An indicator column is a schema bump **not earned at 253
   live rows**; shipped instead an extras-liveness diagnostic as the Rubin-honest promotion trigger.
6. **Point-in-time / off-by-one-bar** (AFML ch.2-3) — CONFORMS. Entry bar's own high/low never
   tested; adverse-extreme-first in both labelers; purge strictly conservative.
7. **Quantization/serialization** (IEEE-754; Higham; Goldberg) — CONFORMS. No float equality across
   the `%.6f` rendering anywhere.

## Citation hygiene
Live-verified vs canonical-from-knowledge split recorded, and the tasking's "Brown, Goetzmann, Ross &
Ross" corrected to Brown, Goetzmann, **Ibbotson** & Ross.

## Related
[[concepts/defect-category-audit]] · [[concepts/ratio-aggregation-bias]] ·
[[concepts/variance-domain-averaging]] · [[entities/overfit-check]]
