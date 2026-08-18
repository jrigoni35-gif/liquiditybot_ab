# Elimination-learning read — gate efficacy on the 11.3k corpus (2026-08-18)

*Dated measurement (SAFE class). Source: `scripts/gate_efficacy_report.py`
run 2026-08-18 ~22:30Z on the merged corpus (11,312 rows: 10,979
candidate / 333 live). Context: operator asked whether the bot is
"doubling down on when not to trade" — this is the tool that grades
exactly that, because the CandidateLabeler labels every gate-confirmed
signal, admitted or vetoed, so the corpus already contains the
counterfactual for every trade NOT taken.*

## Headline

- Baseline (no verdict): win rate **26.5%** [24.7, 28.5] n=2061
- Admitted by the gate: **24.7%** [22.9, 26.6] n=2100
- Separation **−1.9pp — the gate currently selects AGAINST itself**
  (not significant; intervals overlap). Net selection ≈ zero.

## Veto grades (elimination working vs not)

Healthy vetoes (removing losers — win rate far below baseline):

| rule | n | win rate | vs baseline |
|---|---:|---:|---:|
| SZ-030 net-Kelly f*≤0 (p 0.56 class) | 1052 | 6.0% | −20.6pp |
| SZ-023 low-p rungs (0.23–0.31 vs bar 0.69) | ~1000 | 5–14% | −10..−21pp |
| SZ-020 entry cooldown | 288 | 15.3% | −11.3pp |
| SZ-046 | 487 | 16.0% | −10.5pp |
| SZ-022 bear blocks long | 1657 | 22.0% | −4.6pp |

Anti-selective (rejecting winners):

| rule | n | win rate | vs baseline |
|---|---:|---:|---:|
| SZ-023 `p 0.28 below bar 0.55` | 243 | 44.0% [37.9, 50.3] | **+17.5pp** |

**Era caveat on the anti-selective row:** `bar 0.55` is the RETIRED
absolute p-bar; the deployed bar is derived (0.63–0.69, the 2026-07-27
de-phantomization). These 243 rows are historical-era vetoes and do NOT
indict the current rule. Current-bar (0.69) rungs are almost uniformly
healthy. Do not retune on this row.

## Calibration of the gated quantity

p(win) is biased HIGH across nearly every predicted bucket (errors
−0.07..−0.22; e.g. predicted 0.29 → realized 0.07 n=211). Consistent
with the 2026-08-18 overfit-battery live-corpus read (models lose to the
base-rate null OOF) and the Grafana claimed-vs-actual panel. The retrain
loop is actively tightening it (retrain calib gap 0.079 → 0.031 over
2026-08-17→18). A bar can only be as good as the p it thresholds; the
calibration trajectory is therefore the binding constraint on gate
quality — not the bar values.

## Tunnel vision

Admitted HHI is BELOW corpus HHI on both asset (−0.031) and direction
(−0.029): no concentration; the gate is not narrowing onto a pocket.

## Disposition (repo law applied)

- Elimination learning is ALREADY the architecture: 97% of the corpus is
  not-taken candidates, every veto is outcome-labeled, and this report
  grades each rule. Nothing structural is missing.
- Every lever this measurement could motivate (SZ bar margins, veto
  thresholds, exploration probe share/p) is entry decisioning —
  **cohort-resetting under the era-4 moratorium** and gate-tightening
  under the overfit discipline (net-profit ladder, never a backtest
  peak). At 44/50 accrued toward the pre-registered verdict, a reset now
  costs the experiment more than any plausible tuning gain.
- The one number that must keep improving for the whole gate stack to
  work — p(win) calibration — is owned by the retrain loop, which the
  freeze deliberately keeps running, and it is moving the right way.
- Re-run this read at the era-4 gate readout; if the current-bar rungs
  have developed an anti-selective row by then, THAT is the adjudication
  evidence, alongside the pre-named ALGO-5.
