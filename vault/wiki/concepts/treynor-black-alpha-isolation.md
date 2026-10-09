---
title: Treynor–Black alpha isolation — hedge beta only to isolate a measurable alpha
type: concept
status: filed 2026-09-07
summary: "The theory behind 'hedging systematic risk only makes sense once there is measurable idiosyncratic alpha to isolate' is the Treynor–Black model (1973) on top of the single-index/CAPM decomposition (Sharpe 1963/64, Jensen 1968), generalised by Grinold–Kahn's information ratio and Fundamental Law; practised as alpha–beta separation / portable alpha / market-neutral long-short. Its prescription: the optimal active weight in a bet is proportional to alpha over residual variance; alpha = 0 means zero active position and no hedge to pay for; alpha < 0 means the short of the strategy. The bot's book measured on 2026-09-07: appraisal ratio −0.05 per trip pooled (era-9 −0.59) — the theory's answer is 'hold the index', not 'hedge the book'."
---

# Treynor–Black alpha isolation

**The proposition** (operator, 2026-09-07, reading the attribution in
[[sources/session-20260905-06-verification-and-cut10]] §7): *beta ≈ 1 and
alpha ≈ 0, so the book was market-neutralised around nothing — hedging
systematic risk only makes sense once there is measurable idiosyncratic alpha
to isolate.* That is a correct statement of a named theory, in three layers.

## 1. The decomposition — single-index model / CAPM / Jensen

Sharpe (1963) "A Simplified Model for Portfolio Analysis", *Management
Science* 9(2); Sharpe (1964) and Lintner (1965) CAPM; Jensen (1968) "The
Performance of Mutual Funds in the Period 1945–1964", *J. Finance* 23(2).

    r_i − r_f = α_i + β_i (r_m − r_f) + ε_i

β·r_m is **systematic** (market) return — cheap to obtain, cheap to remove
(sell the index); α is the **idiosyncratic** return the manager adds; ε is
residual noise with variance σ²_ε. Ross (1976) APT generalises to many
factors; the logic is unchanged. This is exactly the regression
`scripts/beta_alpha_decomposition.py` runs per closed trip.

## 2. The prescription — Treynor & Black (1973)

Treynor, J. L. & Black, F. (1973) "How to Use Security Analysis to Improve
Portfolio Selection", *Journal of Business* 46(1): 66–86. The optimal
portfolio is the passive index plus an **active portfolio** whose weight in
each security is

    w_i ∝ α_i / σ²(ε_i)          (the "Treynor–Black weight")

and whose worth is its **appraisal ratio** α_A/σ(ε_A), which adds to the
market's Sharpe ratio in quadrature:  SR² = SR_m² + (α_A/σ_εA)².
Consequences, in order:
- **α = 0 ⇒ w = 0.** No active position, so nothing to hedge. The hedge
  (selling β) is a COST paid to isolate α; with no α it isolates nothing.
- **α < 0 ⇒ w < 0.** The theory's position in a negative-alpha strategy is
  its short. Hedging it strips the market part and KEEPS the negative
  residual.
- The hedge is justified by the ratio α/σ_ε, never by the size of β.
  "Market-neutral" is a means of isolating alpha, not a virtue.

## 3. The generalisation — Grinold–Kahn

Grinold (1989) "The Fundamental Law of Active Management", *J. Portfolio
Management* 15(3); Grinold & Kahn (2000) *Active Portfolio Management*, 2nd
ed. Residual return IS alpha; the object is the **information ratio**
IR = α/σ_ε (the appraisal ratio renamed), and IR ≈ IC·√BR: skill (IC, the
correlation of forecast with outcome) times the square root of the number of
independent bets. IC = 0 ⇒ IR = 0 ⇒ hold the benchmark. Alpha estimates are
shrunk toward zero by skill: α = IC·σ·score — at IC ≈ 0 the forecast alpha
is ≈ 0 whatever the raw signal says. See also [[concepts/false-strategy-
theorem-and-minbtl]] for why a measured α̂ near zero at few trials is not
evidence of α.

## 4. Practice names

Alpha–beta separation / **portable alpha** (Kung & Pohlman 2004, "Portable
Alpha: Philosophy, Process and Performance", *J. Portfolio Management*
30(3)); **market-neutral / long-short equity** (Jacobs & Levy 1993,
"Long/Short Equity Investing", *J. Portfolio Management* 20(1)); beta-neutral,
dollar-neutral, delta-neutral (options); in crypto desks "beta-hedged". All
are implementations of §2: strip β to hold α.

## 5. The bot, plugged in (2026-09-07, 329 trips, crypto basket; re-derive with the tool)

| group | α (bps/trip) | σ_ε (bps) | appraisal ratio α/σ_ε | Treynor–Black verdict |
|---|---|---|---|---|
| ALL | −5.1 [−20, +11] | 104 | **−0.05** | w ≤ 0: no active position, no hedge |
| BTC | −4.6 | 26 | −0.17 | none |
| ETH | −1.0 | 81 | −0.01 | none |
| LINK | +43 (CI spans 0) | 193 | +0.22 (unmeasurable) | none until pre-registered |
| era-9 | −54 [−83, −22] | 92 | **−0.59** | the short |

Trip sd 132 bps = market part 82 ⊕ residual 104 (R² 0.385). The book ran an
active strategy with appraisal ratio ≤ 0 AND paid 80 bps a leg to hedge it
(159 hedges, median hold 0.1 min, net −82.5 bps): the two costs the theory
says not to pay, both paid. Cut #11 removed the second; only a positive,
measured α would ever justify restoring it.

**Where it binds here:** the era-8 read points. If α̂ at n=100 is positive
with its CI clear of zero on all three routes, the Treynor–Black weight is
positive and a beta hedge becomes a question worth costing. Until then the
theory's instruction is the one already in force: no hedge.

## 6. The power problem — who ran into it, and the four answers (operator question, 2026-09-07)

**Diagnosis — Merton (1980)**, "On Estimating the Expected Return on the
Market", *J. Financial Economics* 8: the standard error of a drift estimate
falls with the CALENDAR SPAN T, not the sampling count — sampling more often
sharpens variance, never the mean. Alpha is a drift; no instrument shortens
its clock. Lo (2002) "The Statistics of Sharpe Ratios", *FAJ* 58(4): the SE
of an estimated Sharpe ratio, and why annualising hides it.

**Formalisation — Bailey & López de Prado**, "The Sharpe Ratio Efficient
Frontier" (*J. Risk* 2012) and "The Deflated Sharpe Ratio" (*JPM* 2014):
Minimum Track Record Length MinTRL ≈ 1 + (1 − γ₃SR + (γ₄−1)SR²/4)(z/SR)²
observations to reject SR = 0; the Probabilistic Sharpe Ratio; and the
False Strategy Theorem / MinBTL ([[concepts/false-strategy-theorem-and-
minbtl]]) deflating for the number of trials. Their rule: compute the
required record BEFORE trading; a strategy whose MinTRL exceeds its
plausible life is unfalsifiable and should not be run on statistics alone.

**The four solutions in the literature**
1. **Breadth** — Grinold (1989): IR = IC·√BR. Weak skill is cured by many
   INDEPENDENT bets, which shortens MinTRL in calendar time (Renaissance's
   road). Fails when bets are not independent (concurrent trips on one
   market: the bot's 329 trips ≈ 182 effective) or when each bet pays a fee
   the edge cannot cover.
2. **Don't estimate — shrink or go passive** — Jorion (1986) Bayes–Stein;
   Black & Litterman (1992); DeMiguel, Garlappi & Uppal (2009) "Optimal
   versus Naive Diversification", *RFS* 22(5): the window needed for
   estimated means to beat 1/N is ~3,000 months for 25 assets. Sharpe (1991)
   "The Arithmetic of Active Management". The answer is the index.
3. **Structural edge instead of statistical edge** — Thorp (blackjack
   counting; *Beat the Market* 1967 warrant hedging; Princeton-Newport
   convertible arbitrage): where the edge is an ARITHMETIC identity
   (mispricing against a model, spread capture, rebates) it need not be
   inferred from noisy returns at all. Black (1986) "Noise": in a noisy
   market you cannot tell you are right from returns — so be right by
   construction or not at all.
4. **Pre-registration and patience** — accept Merton's clock: register the
   read point, accrue, read once. The bot's registered n=50/100 gates are
   this answer.

**The bot's clock, from the 2026-09-07 run:** alpha SE ≈ 7.9 bps on 329
trips (CI half-width 15.5 / 1.96) ⇒ (104/7.9)² ≈ 182 effective independent
trips, ~55% efficiency. Resolving a 10 bps alpha at 95% two-sided needs SE
≈ 5 bps ⇒ ≈ 430 effective ⇒ ≈ 780 trips ⇒ ≈ 195 days at ~4 trips/day. At
the era-8 rate the n=100 verdict is powered to detect LOSING (≈ −30 bps),
not to certify a +10 bps win — which is what its registration says.

Related: [[concepts/the-method]] (recurrence #12 — the instrument that
measured this was wrong first), [[concepts/variance-domain-averaging]],
[[sources/lund-meta-labeling]] (information ratio in the meta-labeling
literature).
