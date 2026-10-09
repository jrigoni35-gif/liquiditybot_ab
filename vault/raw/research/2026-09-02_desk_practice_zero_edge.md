---
title: "Desk practice with a near-zero edge - the three questions prior runs never cleared"
date: 2026-09-02
type: raw/research
scope: item 4 (A) kill/extend/change-the-target primary sources; (B) the base rate; (C) Harvey-Liu 86.9% scope
method: PDFs fetched to scratchpad, text extracted with pymupdf, quotes grepped and read in place. No claim here rests on a search-engine summary.
read_time_utc: 2026-09-02 (all four PDFs fetched and extracted this session; all are static published papers, not live files)
status: (A) ANSWERED both halves. (B) VERDICT DELIVERED - NO PRIMARY SOURCE FOUND. (C) VERIFIED at source and SCOPED. NOT RUN - see "What was not run".
---

# Desk practice with an edge indistinguishable from zero

Six claims. Each carries a verbatim quote, a URL, a locator and a denominator.
Tags: **[K]** read verbatim at the primary source · **[I]** inferred · **[UNKNOWN]**.

---

## (A) What the literature actually offers a desk

### 1. META-LABELING IS A METHOD WITH NO EVIDENCE ATTACHED. [K]

López de Prado's own prose statement of the technique, from the paper he says is drawn
from the book:

> "In practice, it is often better to build two models, one to predict the side, and
> another to predict the size of the position. The goal of the primary model is to
> predict the sign of the position's return. The goal of the secondary model is to
> predict the accuracy of the primary model's prediction. In other words, the secondary
> model does not attempt to predict the market, but to learn from the weaknesses of the
> primary model."

and the problem it claims to solve:

> "Meta-labeling is particularly helpful when you want to achieve higher F1-scores.
> First, we build a primary model that achieves high recall (e.g., in predicting market
> rallies), even if the precision is not particularly high. Second, we correct for the
> low precision by labeling the bets of the primary model according to their outcome
> (positive or negative). The goal of these meta-labels is to increase your F1-score by
> filtering out the false positives, where the positives have already been identified by
> the primary model."

**Locator:** M. López de Prado, *The 10 Reasons Most Machine Learning Funds Fail*, this
version 27 Jan 2018, Pitfall #6 / "SOLUTION #6: META-LABELING", pp. 10-11.
`https://www.garp.org/hubfs/Whitepapers/a1Z1W0000054x6lUAA.pdf`. The paper states on
p. 1: *"This paper is partly based on the book Advances in Financial Machine Learning
(Wiley, 2018)"* - so this is the same author's own statement of the ch.3 §3.6 material.

**EVIDENCE OR METHOD? METHOD ONLY.** The entire evidentiary claim in the section is one
sentence of authorial anecdote:

> "In my experience, meta-labeling ML models can deliver more robust and reliable
> outcomes than standard labeling models." (p. 11)

**Denominator: none. No backtest, no table, no out-of-sample result, no fund, no n.**
The four supporting arguments given (white-box wrapping, limited overfitting because ML
sets only size, decoupled long/short structures, sizing matters more than selection) are
all mechanism arguments, not measurements. Anyone citing meta-labeling as *evidence*
that a weak primary signal can be rescued is citing an assertion.

*Not read directly:* the book's own ch.3 §3.6 text. O'Reilly returned HTTP 403, the
Wikipedia "Meta-Labeling" page 404, SSRN 4032018 403. The substitution above is by the
same author and self-declared as derived from the book, but it is a substitution.
Vault already records a failed fetch of SSRN 4032018 (`raw/research/2026-08-02_ssrn_4032018_FAILED_FETCH.txt`) - that is now a **second** failure on the same URL; stop trying it.

### 2. THE TRIPLE PENANCE RULE, AND ITS ASSUMPTION, VERBATIM. [K]

> "THEOREM 1 (or 'triple penance rule'): Under standard portfolio theory assumptions, a
> strategy's maximum quantile-loss MaxQL_alpha for a significance level alpha occurs
> after t*_alpha observations. Then, the strategy is expected to remain under water for
> an additional 3t*_alpha after the maximum quantile-loss, with a confidence (1-alpha)."

The assumption is named in the very next paragraph, not buried:

> "If we define Penance = TuW_alpha / t*_alpha - 1, then the 'triple penance rule' tells
> us that, **assuming independent delta-pi_tau identically distributed as Normal (which
> is the standard portfolio theory assumption)**, Penance = 3, regardless of the Sharpe
> ratio of the strategy."

**Locator:** D. H. Bailey & M. López de Prado, *Stop-Outs Under Serial Correlation and
"The Triple Penance Rule"*, this version October 2014, Section 6, p. 8.
`https://www.davidhbailey.com/dhbpapers/stop-out.pdf`.

**The operative rule for a desk** is the stop-out, not the ratio: a manager is stopped
out on hitting *either* the max quantile-loss *or* the quantile time-under-water, and
§7 shows the ITuW form lets you enforce it *before* either limit is reached - a
cumulative loss of US$5,000,000 after 2 years under water implies 3.125 years TuW,
exceeding the pre-set 2.706-year limit, so the manager is stopped out early (p. 9).
Note the direction of the Sharpe adjustment, which is counter-intuitive and is the
paper's stated contribution to practice: **the higher the promised Sharpe, the TIGHTER
the stop.** PM1 (SR 1.0) tolerates US$6,763,858.64 / 2.706 yr; PM2 (SR 1.5) only
US$4,509,239.09 / 1.2 yr (§7, Table 1, p. 8-9).

### 3. THE AUTHORS' OWN EMPIRICAL SECTION SHOWS THE ASSUMPTION **FAILING**, NOT HOLDING - AND PRICES THE CONSEQUENCE. [K]

This is the load-bearing half and it goes the opposite way from what "quote the rule"
would suggest. §10 tests the IID premise on real data and rejects it:

> "As we can deduce from the t-Stat values for phi-hat reported in Table 3, phi-hat is
> statistically significantly in 21 out of 26 cases at a 95% confidence level. Despite
> of this overwhelming empirical evidence, let us suppose that phi-hat = 0 in all of the
> above cases. This is of course a misleading assumption..."

**Denominator, exactly:** 26 Hedge Fund Research (HFR) indices, monthly NAVs from
Bloomberg, 1 January 1990 to 1 January 2013, **265 data points per index** (§10, pp.
12-13). Convergence conditions (mu-hat > 0, phi-hat in [0,1)) hold in **24 of 26**.
First-order autocorrelation is significant in **21 of 26**.

The priced consequence, which is the direct answer to "what does a desk do with an edge
it cannot distinguish from zero":

> "For all hedge fund styles, alpha_2 > alpha_1, which means that they are effectively
> firing a greater proportion of truly skillful portfolio managers than they originally
> intended... hedge funds similar to those in the 'HFRI RV: Fixed Income-Convertible
> Arbitrage Index' (code 'HFRICAI Index') may be firing **3.38 times (0.1688 vs. 0.05)**
> the number of truly skillful portfolio managers, compared to the number they were
> willing to accept under the assumption of returns independence." (§10, p. 15, Table 5)

Same index, the downside understatement: MaxQL 3.79% under independence vs 11.60% with
AR(1) - a **67%** understatement; TuW 21.28 vs 74.42 monthly observations - **71%**
(§10, p. 13). Penance across the indices ranges **1.6 to 3** (Table 4, p. 14).

**So the honest reading of the stopping-rule literature is not "here is a clean rule to
kill on."** It is: the clean rule (Penance = 3) is a Normal-IID idealisation; the same
authors measured the idealisation to be false in 21 of 26 real return series; and the
measured cost of applying the idealised rule anyway is **over-killing by up to 3.38x the
intended false-kill rate.** A desk that kills on an IID-based metric kills too much.
*[I] on the transfer to this repo:* our fill-level returns are not HFR monthly index
NAVs, so 3.38x is not our number - the mechanism transfers, the magnitude does not.

---

## (B) THE BASE RATE - VERDICT: **NO PRIMARY SOURCE FOUND.**

### 4. THERE IS NO PUBLISHED FIGURE FOR A DESK'S KILL RATE OR HYPOTHESES-PER-DEPLOYED-STRATEGY. STOP LOOKING. [K on each disqualification]

Searched academic (J. Finance, Rev. Fin. Studies, NBER working papers), industry
(GARP/JPM whitepapers, PM-Research/JFDS), and the standards side (CFA Institute
curriculum + practitioner survey material). **Nothing publishes an observed count of
strategies researched vs. strategies deployed at a real desk.** Three quantities get
quoted as if they were that number. All three are something else:

**(i) "About 20 iterations" - ASSERTED, UNCITED, AND AN ARITHMETIC IDENTITY.**
> "It typically takes about 20 such iterations to discover a (false) investment strategy
> subject to the standard significance level (false positive rate) of 5%."
(López de Prado, *10 Reasons*, Pitfall #2, p. 5, URL above.) **Denominator: none.** No
sample, no firm, no citation. 20 = 1/0.05 - it is the reciprocal of the significance
level restated as a research statistic, not a measurement of anyone's pipeline.

**(ii) Harvey-Liu-Zhu 71.1% "of tried factors are discarded" - A MODEL EXTRAPOLATION
OVER ACADEMIC PUBLICATIONS, NOT A DESK.**
> "Our estimates indicate that the mean absolute value of the t-statistic for the
> underlying factor population is 2.07 and about 71.1% of tried factors are discarded.
> Given that 238 out of the original 316 factors have a t-statistic exceeding 2.57, the
> total number of factor tests is estimated to be 824 (=238/(1-71.1%))..."
(Harvey, Liu & Zhu, *"...and the Cross-Section of Expected Returns"*, Rev. Fin. Studies
29(1), 2016, Appendix A.1, **PDF p. 43** (printed p. ~46; the main-text restatement
*"Based on our estimates, 71% of all tried factors are missing"* is at PDF p. 24, §3.7.2);
`https://people.duke.edu/~charvey/Research/Published_Papers/P118_and_the_cross.PDF`.)
**Denominator: 316 catalogued published factors, of which 238 have |t| > 2.57; the 824
total is INFERRED**, from fitting a truncated exponential to observed t-statistics with
a known cutoff at 2.57 and assuming independence - `P(unobserved) = 1 - exp(-2.57/lambda-hat) = 71.1%`. It measures the academic publication filter, not any firm's research
process, and it is a fitted tail, not a count.

**(iii) Chordia-Goyal-Saretto's ~2 million strategies - A UNIVERSE THE AUTHORS
CONSTRUCTED.** (*Anomalies and False Rejections*, RFS 33(5), 2020, pp. 2134-2179,
`https://academic.oup.com/rfs/article/33/5/2134/5739455`.) The 2.1M strategies are
randomly generated by the researchers from Compustat/CRSP fields to derive t-hurdles
(3.8 time-series / 3.4 cross-sectional). *[I]* it is a synthetic search space, not a
record of what any desk tried and killed. **Read at abstract/summary level only - I did
not extract this PDF.**

**Corroborating negative evidence [K]:** Fabozzi & López de Prado, *"Being Honest in
Backtest Reporting: A Template for Disclosing Multiple Tests"*, J. Portfolio Management
45(1), 2018, pp. 141-147 (`https://jpm.pm-research.com/content/45/1/141`) exists
*because* the number of trials is not disclosed. Two senior practitioners publishing a
template pleading for disclosure is the strongest available evidence that the disclosure
does not exist. **The number people quote is anecdote. Nobody should search for it
again.**

---

## (C) HARVEY & LIU 86.9% - VERIFIED, AND IT DOES NOT TRANSFER

### 5. THE FIGURE IS REAL AND REPRODUCES BY TWO ROUTES. [K]

> "For example, when p0 = 2% of funds are truly outperforming, the chance of the
> best-performing metric (i.e., the 99th percentile in this case, since it has the lowest
> Type II error rate among all seven test statistics) committing a Type II error is 86.9%
> under the 5% significance level. Indeed, even when p0 = 5% of funds are outperforming,
> the lowest Type II error rate across the different test statistics is still 33.6%."
> ... "even when 2% of funds are truly outperforming and are endowed with on average an
> annualized alpha of 10.66%, there is still a 86.9% chance (at the 5% significance
> level) of the Fama and French (2010) approach falsely declaring a zero alpha for all
> funds."

**Locator:** Harvey & Liu, *False (and Missed) Discoveries in Financial Economics*,
J. Finance LXXV(5), Oct 2020, p. 2542, discussing Table VI Panel B.
`https://people.duke.edu/~charvey/Research/Published_Papers/P143_False_and_missed.pdf`

**Double-derived [K]:** route 1 = the prose above (printed p. 2542). Route 2 = Table VI
Panel B itself (printed **p. 2541**, the page the table body and its header note both
sit on): the p0 = 2% block reads avg alpha 10.66, avg t-stat 3.30, and at the 5%
significance row the seven test statistics give 0.976 / 0.994 / 0.993 / **0.869** /
0.937 / 0.938 / 0.948 (Max, 99.9%, 99.5%, 99%, 98%, 95%, 90%). Minimum = 0.869 at the
99th percentile. **The two routes agree exactly.**

**Denominator [K]:** *"All funds with initial AUM exceeding $5 million are included,
resulting in **3,030 funds over the 1984 to 2006 period**"* (Table VI header note,
printed p. 2541), CRSP Mutual Fund database, M = 1,000 perturbations per cell.

### 6. SCOPE: IT IS A **JOINT** NULL ACROSS 3,030 FUNDS. IT DOES **NOT** TRANSFER TO ONE PRE-REGISTERED TEST OF ONE STRATEGY. [K on the scope, [I] on the transfer verdict]

**(a) The null, verbatim:**
> "Fama and French (2010) focus on the overall null hypothesis of zero alpha across
> mutual funds to test a version of the efficient market hypothesis. Therefore, the
> relevant error rates in their context are the probability of rejecting this overall
> null hypothesis when it is true (Type I error) and the probability of not rejecting
> this null hypothesis when some funds have the ability to generate a positive alpha
> (Type II error)." (§I.D, p. 2515)

**(b) The "correction" is not BHY or Bonferroni.** The 86.9% is computed for the
**Fama-French (2010) cross-sectional bootstrap**: alpha estimates are demeaned to build
a pseudo-population Y0 with exactly zero alpha, Y0 is bootstrapped over time periods,
and the *test statistic is a percentile of the cross-section of t-statistics* (Max,
99.9%, 99.5%, 99%, 98%, 95%, 90%) compared against its bootstrapped distribution. Harvey
& Liu's own contribution - a **double-bootstrap** t-hurdle tied to a target FDR, and a
hurdle tied to an acceptable miss-to-false-discovery ratio - is what they propose to
*replace* it (abstract, p. 2503). The 86.9% is the **power of the method being
criticised**, not a property of significance testing in general.

**(c) THE LOAD-BEARING VERDICT: it is a JOINT-SCAN number.** The whole reason the test
is weak is dilution: 2% of 3,030 funds carry alpha and 98% do not, and the evidence from
~61 skilled funds must move a *cross-sectional percentile* of 3,030 t-statistics far
enough to reject a null about the entire population. **A single pre-registered test of
one strategy has no such dilution and therefore no such power loss.** Its power is set
by that strategy's own effect size, n, and variance, and must be computed - not borrowed.

**Consequence for this repo [I]:** citing 86.9% as a general reason not to trust our own
nulls is a **category error and must stop.** It is the miss rate of a *scan across 3,030
candidates*; we run pre-registered single tests. Where one of our instruments has been
power-calibrated - the standing measurement is that it detects a 0.05 SD planted effect
100% of the time - **that calibration is the authority for that instrument, and 86.9%
has nothing to say against it.** The correct use of Harvey & Liu here is the *shape* of
their argument (Type II error is economically expensive and is routinely left
uncomputed), never the digits. The digits belong to a different experiment.

---

## What was NOT run (say it out loud)

- **The book itself.** AFML ch.3 §3.6 was **not** read directly - three paywall/404
  failures (O'Reilly 403, Wikipedia 404, SSRN 4032018 403, the last a repeat of a failure
  already recorded in the vault on 2026-08-02). Claim 1 substitutes the same author's
  JPM/GARP whitepaper, which self-declares as drawn from the book. **If the exact book
  wording is ever load-bearing, this substitution is the gap.**
- **Chordia-Goyal-Saretto** was read at abstract/summary level only; its PDF was not
  fetched or extracted. The 2.1M figure and the 3.8/3.4 hurdles in claim 4(iii) are
  therefore [I] from secondary summary, not [K].
- **No power calculation was performed here.** Claim 6's assertion that a single
  pre-registered test does not inherit 86.9% is an argument from the paper's own stated
  construction, not a re-derivation of our tests' power. The repo's own power
  calibration is cited from the standing measurement, **not re-derived this session** -
  re-derive it before quoting it (`scripts/label_decomposition_report.py
  --power-calibration` is the named worked example).
- **No effective-n / bootstrap statistic was produced**, because nothing here is a
  statistic over our own concurrent rows - this is a literature pass. No day-block
  bootstrap applies.
- **Kill/extend/change-the-target was only partly answered.** The literature supplies a
  *stopping rule* (claim 2) and a *warning that stopping rules over-kill* (claim 3) and
  a *method for changing the target* (claim 1, unevidenced). **No primary source located
  this session prescribes when to abandon a research programme** as opposed to when to
  stop out a running manager. That distinction was not closed and should not be assumed
  closed.
