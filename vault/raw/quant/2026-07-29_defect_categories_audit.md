# Defect-category audit #2 — categories adjacent to unit errors (2026-07-29)

Second literature pass (operator-directed): seven defect categories
adjacent to the unit/time-scaling class, each with canonical
peer-reviewed anchors, graded against specific code sites. Citation
hygiene: live-verified vs canonical-from-knowledge split recorded; the
tasking's "Brown, Goetzmann, Ross & Ross" corrected to Brown, Goetzmann,
IBBOTSON & Ross (RFS 1992).

## Verdicts

| # | Category | Anchor | Verdict |
|---|----------|--------|---------|
| 1 | Numerical stability / accumulation | Welford 1962; Chan-Golub-LeVeque 1983; Higham 2002; Kahan 1965 | Mostly CONFORMS (PnL accumulators bounded ~1e-7 USD at scale — Kahan would be ceremony; no naive E[x2]-E[x]2 anywhere). ACTIONABLE: OF-5 DSR population moments (ddof=0) inflated SR ~+1.7% at n=30, anti-conservative on the hard gate -> FIXED (ddof=1 reused across SR/skew/kurt). KNOWN-DEVIATION: segment-price recovery cancellation noise in the slip ledger (self-cancelling in aggregate; fees/PnL exact) -> dust guard added (below). |
| 2 | Data leakage taxonomy | Kaufman-Rosset-Perlich-Stitelman KDD 2011 / TKDD 2012 | CONFORMS across the board: no post-fill feature (mark-out confirmed telemetry-only), X built exclusively from FEATURE_NAMES, funding_dist is a legitimate clock, no position-state features, signal_ts conservative (bar open = 5 min before decidability, over-purges). |
| 3 | Survivorship / selection bias | Brown-Goetzmann-Ibbotson-Ross RFS 1992; Bailey-Borwein-LdP-Zhu AMS 2014 | CONFORMS: skimmer selects on LIQUIDITY not outcome; demoted assets' rows stay in the corpus forever; the candidate labeler (label every confirmed signal, taken or vetoed) is the anti-selection instrument by design. Two second-order residuals noted (newest-eviction pool cap; restart-keyed candle-cache drops — ignorable missingness). |
| 4 | Ratio-aggregation bias | Cochran ch.6; Bessembinder JFM 2003 | ACTIONABLE (telemetry): avg_slip_bps was a per-fill unweighted mean — $10 probe fills outvoted 4x conviction notional, ~0.3-0.5bps rosy -> FIXED: slip ledger stores (slip, notional), status gains slip_bps_notional_weighted beside the legacy key. Markout has the same shape but its deque is SNAPSHOT-PERSISTED -> deferred to a versioned-persistence follow-up rather than rushed. cost_truth per-trade mean = KNOWN-DEVIATION (documented population, per-trade estimand). gate_truth win rates CONFORM (count-weighted Bernoulli is the correct estimator + uniqueness-effective n). |
| 5 | Missing-data conventions | Rubin 1976; Little & Rubin 2019 | KNOWN-DEVIATION, bounded: dark-feed features impute their own neutral (0 z / 0.5) — dead column while dark (no fit distortion), hazard only at feed-alive TRANSITION (mostly-imputed column w/o indicator attenuates the coefficient). Indicator column = schema bump, NOT earned at 253 live rows. SHIPPED instead: extras-liveness diagnostic in overfit report (at-neutral share per feed feature) — the Rubin-honest promotion trigger. VolState placeholder perimeter verified closed on both sides. |
| 6 | Point-in-time / off-by-one-bar | Lopez de Prado AFML ch.2-3 | CONFORMS: entry bar's own high/low never tested (j starts i+1), adverse-extreme-first both labelers, committed-bars-only ts convention end to end (venue-authoritative forming-bar drop), purge strictly conservative. |
| 7 | Quantization / serialization | IEEE-754 round-trip; Higham 2.6 / Goldberg | CONFORMS: no float equality across the %.6f rendering anywhere (dedup compares CSV strings to CSV strings; lineage id is the primary key); snapshot checksums canonicalize identically at seal and verify. One latent note filed (non-string dict keys would change sort order; failure direction safe). |

## Shipped this pass
- OF-5 DSR moment hygiene (ddof=1) — tightens the gate, removes the
  anti-conservative bias.
- slip_bps_notional_weighted status key (additive; legacy key unchanged)
  + dust-segment slip-ledger guard (<1% of order notional; fee/notional
  booking untouched — exact by construction).
- extras-liveness diagnostic (report-only info lines) in overfit_check.

## Deferred (conscious)
- Markout notional weighting: same estimator fix as slippage, but the
  observation deque is snapshot-persisted -> needs a versioned
  persistence migration; standalone small task.
- Missingness-indicator columns for the extras family: schema bump
  gated on the liveness diagnostic showing the feeds actually alive.
