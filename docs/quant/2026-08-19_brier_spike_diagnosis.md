# Brier spike 2026-08-19 06:10-11:10Z — diagnosed base-rate surge, no fix

*Dated measurement (SAFE). Question: champion Brier 0.181->0.339 and
calib gap 0.035->0.307 overnight — bug or data? Operator directive:
fix if broken, otherwise let it ride.*

## Diagnosis: label base-rate regime shift, arithmetically confirmed

- 547 candidate labels resolved in 18h with base rate **0.415** vs
  **0.236** over the prior 5 days (overnight bull drift resolved the
  counterfactual corpus as wins; same move put the open book green).
- Arithmetic check: a ~0.2-predicting model against 0.415 outcomes
  scores Brier ~0.29-0.34. Measured: 0.306 (10:10Z) / 0.330 (11:10Z)
  challenger OOF, 0.339 live judge. The spike IS the base-rate term.
- Integrity clean: probe share 0.5% (normal), influx spread across 8
  assets, arrivals follow the 36h barrier-resolution rhythm (peak
  08:00Z = prior day's entries maturing), dedup/import counts normal,
  3 live closes among 547 candidates (normal ratio).

## The guards worked (why no fix is needed)

- ML-031 drift vote fired (33% > 30%) — the leading indicator led.
- BOTH mid-shift challengers were REFUSED deployment (bar held).
- The judge degraded the champion's score honestly instead of hiding it.

## Disposition

LET IT RIDE (operator-directed, evidence-supported). If the base rate
holds near 0.4, retrains will re-calibrate within the deployed loop; if
it mean-reverts, scores recover on their own. Either way this is
regime-sensitivity evidence FOR the era-4 docket (regime[bull_quiet]
live-coverage flag), never grounds for mid-era tuning. Re-read at the
next retrain rows; escalate only if degradation persists across a full
barrier horizon (~36h) with the base rate back near 0.2.
