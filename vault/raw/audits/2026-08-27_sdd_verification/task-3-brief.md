# Task 3 — verify commit 5e785c16 "feat(telemetry): the veto counters learn whether the vetoes were right"

Read context-common.md in this directory FIRST — it is binding.

## What shipped (verify, don't trust this summary)
`git show 5e785c16` — veto counterfactual telemetry: counters that grade whether vetoes (SZ-021 crisis, SZ-030 net-Kelly, SZ-023 p-bar, SZ-046, liquidity/spoofy vetoes) were RIGHT, i.e. counterfactual win-rate of vetoed candidates vs baseline. HANDOFF's REG-6 UPDATE already cites its numbers (`gate_efficacy_report` `by_code`, glass metric `liquiditybot_veto_cf_rate`): SZ-021 anti-selective 0.509 [0.439,0.580] vs baseline 0.265 [0.192,0.354], n=2032 (n_eff 189); SZ-030 earns its keep 0.060 [0.040,0.089]; SZ-023 at baseline 0.278 [0.257,0.299] n_eff 1721.

## Questions to answer, each with evidence
1. WIRING: trace the counter from veto site → counterfactual label resolution → exported metric. Which process resolves the counterfactual outcome, at what horizon, and what happens to a vetoed candidate whose outcome window has not closed yet (counted as loss? excluded? pending)? Pending-as-loss or pending-as-win would bias the rate — establish which by reading the resolution code AND by running it on a synthetic pending candidate.
2. THE INSTRUMENT'S OWN BAR: effective-n Wilson intervals are claimed. Double-derive one published number by an independent route: recompute SZ-021's 0.509 [0.439, 0.580] (or whichever code has data on this box) directly from the underlying candidate/counterfactual rows with your own script, boundaries exact, and compare. Disagreement = finding.
3. SELECTION BIAS CHECK: is "baseline" the admitted cohort's win rate? Admitted and vetoed candidates differ by construction (that's what the veto does) — does the report say what baseline conditions on? A baseline computed on a different mix of assets/regimes than the vetoed set makes the comparison confounded. Report what the code actually conditions on [K], not what would be ideal.
4. SD-003 CROSS-CHECK: today's digest shows liquidity 'spoofy' vetoes on 57% of classified cycles (last 48h). Do the new counters cover the liquidity/spoofy veto path (SZ-045/size_mult=0 family)? If yes, what do they say — were the spoofy vetoes right? If the counters don't cover that path, say so explicitly: that is a coverage gap worth reporting, not a defect.
5. Covering tests: name, run with ./.venv/Scripts/python.exe -m pytest <files> -q, exact counts.

## Report path
Write full report to: C:\Users\haird\AppData\Local\Temp\claude\c--Users-haird-Documents-liquiditybot-liquiditybot-ab\cdb03d59-62a4-41ee-8c1c-00feb1307464\scratchpad\sdd\task-3-report.md
