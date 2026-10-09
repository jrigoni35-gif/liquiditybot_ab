---
title: "Deep research #3 (PARTIAL) — consequences of acting on an edge/skill measurement"
date: 2026-09-01
type: raw/research
workflow: deep-research wf_c5fac112-377 (task wyby2yq0y), 108 agents, 86 done / 22 FAILED on account session limit, synthesis FAILED
status: PARTIAL — 16 confirmed, 2 refuted, 7 unverified (verification votes never ran); angles 4 (LLM-in-the-loop) and 5 (model-risk doctrine, JPM CIO VaR, SR 11-7) produced ZERO surviving claims = UNRUN, not null
resume: Workflow({scriptPath: ".../workflows/scripts/deep-research-wf_c5fac112-377.js", resumeFromRunId: "wf_c5fac112-377", args: <same question>}) after the limit reset (2026-09-01 19:50 America/Chicago)
---

# Question (abridged)
What are the consequences — for capital, strategy, process — of acting on the bot's edge/skill measurement
(skill ≈ −0.006 on 23.73 d champion-scored / 50 d raw; N nominal 512 trials; pre-registered n=50 cohort gate;
LLM-written measurement instruments) under each outcome; what does the primary-source record say.
Five angles: (1) acting on a wrong measurement both directions; (2) alpha decay + reflexivity of measurement;
(3) capital consequences of estimation error; (4) LLM-in-the-loop — verify the pasted "LLM inconsistency"
claims + reliability of LLM-written analysis code; (5) the measurement regime itself (SR 11-7, JPM CIO VaR,
peeking, kill/extend/change-target).

# CONFIRMED (3-vote adversarial; vote shown)

| # | angle | claim | source | vote |
|---|---|---|---|---|
| 1 | 1 | Suhonen, Lennkh & Perez: across 215 investment-bank alternative-beta strategies the **median backtest→live Sharpe deterioration is 73%** (live ≈ 27% of backtest). The pasted "~50–70% haircut" UNDERSTATES the paper. | research.aalto.fi/en/publications/quantifying-backtest-overfitting-in-alternative-beta-strategies | 3-0 |
| 2 | 1 | Same paper: deterioration rises with complexity — most-complex strategies' live-vs-backtest Sharpe reduction exceeds the simplest by **>30 percentage points**. Quantified argument for condensation. | same | 2-1 |
| 3 | 3 | Bailey & López de Prado DSR: E[max SR] = μ + σ·[(1−γ)Z⁻¹(1−1/N) + γZ⁻¹(1−1/(Ne))], γ=0.5772; strictly positive, grows in N. | davidhbailey.com/dhbpapers/deflated-sharpe.pdf | 3-0 |
| 4 | 3 | Worked DSR example: SR 2.5 over T=1250 daily obs, negative skew/excess kurtosis, N=100 trials → DSR ≈ 0.90, REJECTED at 95%; passes at N=46; Normal returns pass up to N=88. Trial count and non-normality jointly decide. | same | 3-0 |
| 5 | 1 | Under memory effects (mean reversion) backtest overfitting yields systematically NEGATIVE OOS performance ("loss maximization"), attributed to Bailey et al 2014 Notices AMS for the proof. (NB: earlier session verdict — this needs memory in the series; cite as "zero-edge null not contradicted", not as a mechanism we have shown.) | same | 3-0 |
| 6 | 1 | Arnott, Harvey & Markowitz 2019: the ONLY quantified decay figure is a footnote citing Arnott, Beck & Kalesnik 2016 — eight popular factors 5.8%/yr pre-publication vs 2.4%/yr post (≈60% alpha loss, before costs). The paper contains NO "50–70% Sharpe haircut". | people.duke.edu/~charvey/Research/Published_Papers/P138_A_backtesting_protocol.pdf | 3-0 |
| 7 | 2 | Same paper: tweaking a live model underperforming its backtest generally produces further overfitting; a modified model re-fit to OOS data is no longer an OOS test. **Primary-source basis for the accrual moratorium.** | same | 3-0 |
| 8 | 1 | Same paper: 20 random strategies → one exceeds t=2 by chance; count trials and their correlations; 20 variables with pairwise interactions = 190 tests, not 22. | same | 3-0 |
| 9 | 5 | Johari, Pekelis & Walsh (arXiv 1512.04922): continuous monitoring of a fixed-horizon test with no correction inflates Type I error ~5× even at n=10,000 — a nominal α=0.05 gate read repeatedly yields ~25% false positives. | arxiv.org/abs/1512.04922 | 3-0 |
| 10 | 5 | Same: an A/A test crosses the 95% "chance to beat" threshold under continuous monitoring — the null-effect analogue of a zero-skill signal reading as edge on an oft-inspected gate. | same | 3-0 |
| 11 | 3 | Bailey & LdP "stop-out": triple-penance rule — under IID Normal cashflows with μ>0, MaxQL_α=(Z_α σ)²/(4μ) at t*=(Z_α σ/2μ)², TuW_α=4t*; recovery takes 3× the time to reach bottom, independent of Sharpe. A stop-out firing sooner fires at a higher false-positive rate than nominal. | davidhbailey.com/dhbpapers/stop-out.pdf | 2-1 |
| 12 | 3 | Same: stop-out formalized as a hypothesis test at α against "performance consistent with skill"; MaxQL/TuW limits encode tolerance for firing a skilled PM; implied TuW = π²/(μ²t) − 2π/μ + t (Prop. 3). | same | 3-0 |
| 13 | 2 | McLean & Pontiff 2016 (J. Finance): 97 predictors — returns **26% lower out-of-sample, 58% lower post-publication** vs in-sample. | onlinelibrary.wiley.com/doi/10.1111/jofi.12365 | 3-0 |
| 14 | 2 | Same: the 26% OOS decline is an UPPER bound on data-mining bias; the remaining 32 pp is publication-informed trading — decay is reflexive to the edge becoming known. | same | 3-0 |
| 15 | 2 | Dwork et al 2015 (Science): reusing a holdout adaptively manufactures edge from noise — n=d=10,000, labels independent of attributes, k=500 selected by sign agreement → **>63% reported accuracy on train AND holdout, 50% on fresh data**. The exact mechanism by which retuning a gate on accruing data overfits the gate. | science.org/doi/10.1126/science.aaa9375 | 3-0 |
| 16 | 2 | Thresholdout mechanism: answer with training value unless |holdout − train| > T+η; then holdout + Laplace noise, decrement budget B; stop when exhausted. | same | 3-0 |

# REFUTED
- (0-3) "Always-valid p-values from the mixture SPRT control Type I under ANY stopping rule — the fix for peeking is a sequential test, not a moratorium." Refuted as stated (the paper's guarantee is narrower; verifiers could not confirm the blanket claim from the text).
- (1-2) The stop-out worked example (SR=1 → 2.706 yr under water / $6.76M loss limit; SR=1.5 → 1.2 yr / $4.51M) and the inference "for SR→0 the TuW limit diverges, no finite drawdown can reject skill". Numbers not verified against the PDF; do not cite.

# UNVERIFIED (verification votes never ran — session limit)
- Thresholdout Theorem 25 sizing (holdout n = O(ln(m/β)/τ² · …); tolerance still ~1/√n → a small cohort holdout cannot certify a small edge however reused).
- Liu, Tsyvinski & Wu (J. Finance, jofi.13119): ~3%/week long-short crypto factor returns are GROSS, costs excluded.
- Crypto momentum survives in larger coins but alpha eroded by costs and comes largely from the SHORT leg (sciencedirect S1057521924001509) — a long-only limit-entry spot bot cannot capture most of it.
- Crypto abnormal returns regime-dependent (bull) and decaying (same source).
- arXiv 2512.11913 (crowding-timed factors, Sharpe 0.22 vs 0.39 naive): author WITHDREW v2 2025-12-27; equities only; cite nothing from it.
- Baker & McHale 2013 (Decision Analysis 10(3)): raw Kelly with plug-in estimates degrades OOS — the overbetting mechanism. Abstract only (INFORMS 403).

# UNRUN (zero surviving claims — a failed scan, not a null)
- **Angle 4 entirely**: the pasted "41% fabrication", fact-subjectivity crypto agent, sign reversals under window shifts, belief homogenization / mini-crashes, "Strict Separation Framework" provenance, temperature-0 non-determinism, and — most important — published error rates of LLM-written data-analysis code (DS-1000 / DA-Code / InfiAgent-DABench / BLADE). None of the five pasted LLM-inconsistency claims is verified OR refuted here.
- **Angle 5 doctrine/incidents**: SR 11-7 / OCC 2011-12 effective challenge; JPM CIO 2012 VaR spreadsheet mechanism and magnitude; Reinhart–Rogoff; kill/extend/change-target desk practice with citations.
- The synthesis (decision table under each readout, minimum verification standard for an LLM-written instrument).

# What survives for the bot, from what DID run
1. The moratorium is primary-sourced (claims 7, 15, 9/10): retuning on the accruing gate is the Dwork mechanism; reading it repeatedly is the Johari mechanism.
2. Condensation has a quantified motive (claim 2) — but the same-session feature-concentration scan shows the feature list is not the lever; the target is.
3. A measured "edge" on this corpus must be deflated by E[max SR] at N≈512 (claims 3–4) — no in-sample number here can pass a DSR at 95%.
4. Backtest→live decay: 26%/58% (equities, McLean–Pontiff) and a 73% median Sharpe haircut (bank alt-beta). Any positive readout should be planned at ≤ one-third of its measured size.
5. The pasted LLM text remains UNSOURCED. Treat as hypotheses.
