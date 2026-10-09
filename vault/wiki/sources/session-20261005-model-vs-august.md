---
title: "Session 2026-10-05 — today's champion vs the August champion, paired out of sample"
type: source
created: 2026-10-05
updated: 2026-10-05
sources: [raw/2026-10-05_model_vs_august_paired_oos.md]
---

# Is the model better than in August? Paired OOS — no detectable improvement

Operator asked whether the model is better now than in August. The only fair test: score the last
August champion (`1ee3ae68c0df`, logistic, v9, deployed 2026-08-25, 6,729 rows) and today's champion
(`3f62ef23f709`, blend, v10, deployed 2026-09-23, 21,706 rows; = served `outputs/meta_model.json`) on
the SAME rows neither trained on — every h432-labeled entry after 2026-09-23 10:09 UTC. That cancels
the regime, base-rate, fee and exit changes that a "then vs now" comparison would absorb
([[synthesis/comparability-boundaries]]).

## Result (4,948 rows, 13 UTC days; snapshot 2026-10-05T17:57:31Z)

| forecast | Brier | log loss | AUC | mean p |
|---|---|---|---|---|
| August champion | 0.2384 | 0.6699 | 0.539 | 0.452 |
| today's champion | 0.2332 | 0.6590 | 0.531 | 0.393 |
| base-rate benchmark (0.4396, known ex ante) | 0.2373 | 0.6676 | — | 0.440 |

- **August − today: +0.0053 [−0.0050, +0.0164]** (day-block 95% CI) — covers 0: no detectable difference.
- Neither model beats the base-rate benchmark: today +0.0041 [−0.0049, +0.0138]; August −0.0012
  [−0.0048, +0.0022]. Brier skill vs benchmark: today +1.7%, August −0.5% (point estimates).
- **Where today's point edge comes from:** calibration, not ranking. The window's win rate fell to
  0.364 from 0.440 historically; today's model predicts lower (mean p 0.393) and is hurt less. Ranking
  is no better — AUC 0.531 vs 0.539, both barely above coin-flip, consistent with the 2026-09-15 survey's
  direction AUC ≈ 0.51 ([[sources/session-20260915-master-survey-and-double-exit]]).
- **Instrument proven:** a planted 10%-toward-truth nudge reads +0.0443 [+0.0416, +0.0467] (excludes 0);
  self-vs-self reads 0. The test can see effects of that size; the observed ~0.005 is ten times
  smaller than the CI can resolve at 13 days.

## Literature (rule 6, verified 2026-10-05)
- Campbell & Thompson (2008), RFS 21(4):1509–1531 (Harvard): the bar is the historical average;
  out-of-sample gains over it are small even when they exist. **Adversary held:** neither model clears it.
- Diebold & Mariano (1995), JBES 13:253–263: compare two forecasts on the same sample by their loss
  differential, robust to serial correlation — the design used.
- Politis & Romano (1994), JASA 89(428):1303–1313: block bootstrap for dependent data (affiliation not checked).

## Limits
13 day-blocks; candidate rows (not trips); v9 input order assumed = v10 minus dp_* [I]; governor
shrinkage excluded; one August model (the last, most-trained champion). Re-run the raw page's script
as the window grows — the CI narrows roughly with √days.

## Addendum — how long to know, and what the past already says (same day)
Power by simulating the MEASUREMENT (the 13 real days resampled, re-centred on a true gap; clustered CI checked against the bootstrap: [-0.0057, +0.0162] vs [-0.0050, +0.0164]; null false-'better' 3.3% vs ~2.5%; script raw/2026-10-05_model_vs_august_power_sim.py):

| true gap | 13d | 30d | 60d | 90d | 120d | days for 80% power |
|---|---|---|---|---|---|---|
| +0.0025 | 9% | 12% | 17% | 23% | 30% | ~472 |
| +0.0053 (observed) | 21% | 34% | 57% | 74% | 84% | ~106 |
| +0.0100 | 50% | 80% | 97% | 100% | 100% | ~31 |

- **Correction of the same day's '~60 days' estimate:** at 60 days a gap the size of the point estimate is caught only 57% of the time; 80% needs ~106 days.
- **Past-as-future already runs daily:** `outputs/learning_curve.json` (2026-10-05 05:40) refits the deployed selector on prefixes of 10,518 -> 26,296 rows; OOF Brier 0.2599 -> 0.2571, tool verdict 'no measurable improvement with corpus growth'; calibration gap 0.030 -> 0.005. More of the same data improves calibration, not skill — the paired test's pattern.
- A recipe-vs-recipe rolling-origin backtest is bounded by the h432 era (from 2026-08-11): at most ~35-40 OOS days, ~35-40% power at the observed gap. Simulating future MARKETS is circular and evidence-closed ([[synthesis/evidence-closed-register]], synthetic corpus data).
