# Lens 05 — bot-amplified sentiment -> flow (the PNAS 2018 bridge)

Seed: Stella, Ferrara & De Domenico 2018, PNAS 115(49):12435-12440, doi
10.1073/pnas.1803470115 (bots authored 23.6% of posts — confirmed
2026-08-27, replies 38.8%; strategically target influential humans with
valence-matched inflammatory content — confirmed. The companion "bots ~1/3
of users" account-share figure was NOT confirmed against the paper this
pass; the bridge framing carries the posts share only until the
account-share number is verified against the paper body). Bridge
hypothesis: bot-amplified narrative -> predictable retail emotional flow ->
swings and cascades patient capital harvests. Compliance fence applies
throughout: detection targets only. See README for legend and bars.

---

## bot-prev-1 — bot prevalence concentrates at the manipulation surface [B]

**Claim:** 36.4% (2,710 of 7,441) of accounts broadcasting Telegram/Discord
invite links classified as bots by Botometer, 56.3% deceptive including
suspended accounts, versus 1-14% bot share of general crypto tweets; corpus
16.8M posts / 5.7M users.

**Citations:** Nizzoli, Tardelli, Avvenuti, Cresci, Tesconi, Ferrara, IEEE
Access 8:113230-113245, 2020, doi:10.1109/ACCESS.2020.3003370
(arxiv.org/pdf/2001.10289); Kraaijeveld & De Smedt, JIFMIM 65, 2020,
doi:10.1016/j.intfin.2020.101188 (1-14% heuristic).

**Mechanism:** Bot operators profit from recruited retail flow funneled via
invite links into pump channels; deception cost borne by late joiners — the
"replenished, not educated" pool (who-loses-to-us.md).

**Testable:** Not with current data — no X/Telegram feed. Our scanner
(sentiment/scanner.py:10-25) reads Google News RSS + crypto-outlet RSS +
Hacker News only: zero exposure to the surface where the 36.4% lives. A
bot-share feature requires a platform-native feed (owed, extends ATTR-1).

---

## pnd-anatomy-1 — pumps resolve in seconds-to-minutes [B]

**Claim:** Telegram-organized pumps (n=412, Jun 2018-Feb 2019): in the
dissected case price peaked 18 s after announcement, insiders exited within
3.5 min, participants entering >18 s late could hardly profit; a pre-pump
likelihood model returned 60% over 2.5 months by front-running the
announcement.

**Citations:** Xu & Livshits, "The Anatomy of a Cryptocurrency Pump-and-Dump
Scheme", USENIX Security 2019, pp.1609-1625.

**Mechanism:** Admins and pre-informed insiders accumulate before
announcement, distribute into the recruited spike; profit is pure latency
ordering — last-in retail is the funding counterparty.

**Testable:** NOT monetizable for us, tagged so: an 18-second window on thin
non-Kraken alts cannot clear the 43-118 bps bar at our cycle cadence.
Detection-target only: pre-pump accumulation signature (volume/quote
anomalies before any news) is a THALES-shaped detector candidate
(shadow-first), testable on OKX/Binance.US read-only books. We do not
trade ahead of detected pumps — detection informs stand-aside/shade-down
only (compliance fence, README; tightened 2026-08-27 per conduct review).

---

## pnd-wealth-1 — pumps distort 65% on average; participant EV negative [A]

**Claim:** Pumps generate average price distortions of 65% with abnormal
volumes in the millions of dollars; expected returns for participating small
investors are negative; participation persists via overconfidence and
gambling preferences despite openly pre-announced intent.

**Citations:** Dhawan & Putniņš, Review of Finance 27(3):935-975, 2023,
doi:10.1093/rof/rfac051; convergent lineage: Xu & Livshits USENIX 2019;
Kamps & Kleinberg, Crime Science 7:18, 2018 (already graded in
docs/research/2026-07-26_criminology_manipulation_lens.md — cited, not
re-derived).

**Mechanism:** Organizers and early insiders extract from late retail
joiners; the loser pool self-replenishes exactly as who-loses-to-us predicts
(self-attribution defeats learning) — emotional-flow supply is durable.

**Testable:** Partial — pump aftermath (post-distortion mean reversion on
thin alts) surfaces as transient cross-venue divergence; the
main.py:292-313 divergence flag (per criminology doc) is the existing
instrument. Test = correlate flag firings with subsequent reversion in
recorded feeds. See 06 spec T16.

---

## sent-ret-1 — Twitter sentiment Granger-causality [B in-sample; D at our horizon] [FLAGSHIP — AMENDED]

**Amended claim (verdict text, use this):** Kraaijeveld & De Smedt (2020,
JIFMIM 65:101188) find IN-SAMPLE Granger causality from Twitter sentiment to
returns on a 61-day 2018 sample (4 Jun-4 Aug 2018 daily; authors call n
"close to suboptimal"): LTC daily lags 1-3; BTC daily lags 1-3 under
original-Granger only (Toda-Yamamoto finds none); BCH hourly lags 1&3 only
(no daily effect); bullishness adds EOS (hourly) and TRON (daily); tweet
volume predicts only LTC/XRP. No multiple-testing correction, bot tweets
(>=1-14% of corpus) not removed, and the authors disclaim practical/trading
significance. Grade B, in-sample only. Counter-weight: Guegan & Renault (FRL
38, 2021) find the Bitcoin sentiment-return relation survives only at
<=15-minute frequency and disappears at daily, concentrated in the bubble
regime — so the 1-2 day retail-flow bridge is a D-grade hypothesis for our
horizon, not a B-grade fact.

**Verdict: AMENDED.** Primary full text verified (open PDF, extracted
2026-08-27). Defects: (1) lag/coin structure of the original claim wrong
("1-2 day lags" appears nowhere in the paper; BCH is hourly-only; BTC daily
fails Toda-Yamamoto); (2) fragility undisclosed (61 daily obs, single 2018
bear regime, ~dozens of bilateral tests at p<0.05 uncorrected, bots not
removed); (3) counter-evidence at the claimed horizon: Guegan & Renault,
"Does investor sentiment on social media provide robust information for
Bitcoin returns predictability?", Finance Research Letters 38:101494 (2021),
hal-03205154 — 988,622 StockTwits messages 2017-2019, relation significant
only up to 15 MINUTES, magnitude too small for trading profits. Direction
survives; the "horizon our cycle scale can use" leg of the mechanism is
gutted.

**Mechanism (as amended):** Attention-recruited retail reads platform-native
sentiment and trades it; the best-replicated sentiment-return horizon is
<=15 min, not 1-2 days. Patient resting capital may still receive the flow,
but the bridge at our cycle horizon is unproven (grade D).

**Testable:** Yes, instrument-first: our sentiment score + volume_z are
logged features; lagged-IC of recorded SentimentSnapshot.score
(scanner.py:54-64) vs forward returns. Caveat: our RSS/HN proxy is not their
platform-native signal — a null measures OUR instrument, not the hypothesis
(the-method: instrument first). Any deployment must clear OF-1..7 and the
43-118 bps bar. See 06 spec T15.

---

## sent-ret-2 — StockTwits sentiment index predicts daily CRIX OOS [C] [FLAGSHIP — AMENDED]

**Amended claim (verdict text, use this):** Chen, Despres, Guo & Renault
(IRTG 1792 DP 2019-016, working paper — never verified as peer-reviewed)
find a StockTwits crypto-lexicon sentiment index positively predicts daily
excess CRIX returns out-of-sample vs the historical-average benchmark:
Campbell-Thompson R2_OS 0.66% whole sample (2015-2018), 0.97% bubble
(2015-2017), 8.76% post-bubble (Jun-Dec 2018), CW-test significant in all
three. The oft-quoted IS 2.74%/OOS 3.15% appear only in an inaccessible SSRN
draft and are unverified. Regime structure is load-bearing: sentiment effect
is prolonged WITHOUT reversal during the bubble, but shows a significant
lag-2 REVERSAL after the collapse (S_t-2 = -0.2031, p=0.008) — i.e., in
post-bubble regimes (the one resembling ours) sentiment-chasing flow is
overreaction-then-reversal fodder, not persistent directional flow.
Fundamental vs non-fundamental split: unverifiable in accessible text —
treat as a TASK, not a fact. Grade C.

**Verdict: AMENDED.** The only verifiable full text (econstor.eu IRTG 1792
DP 2019-016, extracted 2026-08-27) does not contain the claimed 2.74%/3.15%
(SSRN-abstract-only figures, unstable across drafts); "without short-horizon
reversal" contradicted by the paper's own abstract and post-bubble VAR
(Table 9: S_t-1 = +0.1557 p=0.019, S_t-2 = -0.2031 p=0.008, Feb-Dec 2018,
344 obs); "robust across regimes" survives only as "OOS predictability
positive and CW-significant in both". Same-author tension: Guegan & Renault
(FRL 38, 2021). Direction survives — AMENDED not REFUTED.

**Mechanism (as amended):** Noise-trader market lets sentiment drive price;
but in post-bubble regimes the flow is overreaction-then-reversal — a
mean-reversion counterparty shape, not a positioning-ahead shape.

**Testable:** Yes — daily OOS R² of our logged sentiment feature vs next-day
return, judged against the simplicity ladder and shuffle null (OF-2), never
argmax. If OUR proxy shows ~0 (ATTR-1 says it will), the gap indicts the
feed, not the hypothesis. See 06 spec T15.

---

## bot-flow-1 — bot tweets relate to returns/volatility/volume [B] [FLAGSHIP — STANDS]

**Claim:** Bot tweets are significantly related to returns, volatility and
trading volume at both daily and intraday frequencies (FTSE 100, 55 firms —
equities, not crypto); crypto-specific extension shows social bots active in
manipulation around the LUNA crash.

**Verdict: STANDS — referee's own strongest refutation attempt failed on
inspection.** The April 2018 working paper says "we do not observe
significant influence of Twitter-bots on stock returns" daily and intraday
impact "vanishes within 30 minutes" — but the ACCEPTED version (EFM
26(3):753-777, 2020) supersedes it: Table 4 shows significant bot-tweet
SENTIMENT->daily-return relation (1% bot positiveness ~ +0.0165% return vs
+0.0206% human), bot volume related to volatility and volume daily; 5-min
intraday (Aug 2015-Jul 2018, 1,408,538 obs) and lagged regressions (Table 8)
confirm; event study corroborates. The WP null was volume->returns; the
published sentiment-channel result is what the claim asserts — refutation
withdrawn. LUNA leg verified: Yu, Zhou, Jiang & Liu, Electronic Markets
35(1), 2025, doi:10.1007/s12525-025-00849-w — 33,281 tweets, 1,032 price
points, 15 Apr-27 May 2022, 15 ML algorithms; bot-expressed sentiment MORE
predictive of LUNA price than human accounts. Referee's added record notes:
daily EFM evidence is contemporaneous association (paper's own word);
predictive form only at 5-min lags + event study; LUNA is a single-event
(n=1) study whose "manipulation" attribution is the authors' interpretive
framing — detection target per the compliance fence. Neither changes content
or grade B.

**Citations:** Fan, Talavera & Tran, "Social media bots and stock markets",
European Financial Management 26(3):753-777, 2020, doi:10.1111/eufm.12245;
Yu et al., Electronic Markets 35(1), 2025, doi:10.1007/s12525-025-00849-w.

**Mechanism:** Bot posting volume moves the attention channel retail trades
through; whoever times against the induced volatility profits from the
bot-recruited flow. Direct evidence the bot->flow leg of the PNAS bridge
carries to markets; crypto leg still single-study.

**Testable:** Not with current data (no bot-classified social feed).
Cheapest partial: HN story-volume z (scanner.py:22-24) as a bot-free
attention proxy vs realized volatility — tests the attention->volatility leg
only. See 06 spec T20.

---

## pnas-shape-1 — the PNAS shape only PARTIALLY replicates in finance [B]

**Claim:** The strategic-amplification shape (bots 23.6% of posts — the
"~1/3 of users" account-share companion figure is unconfirmed as of
2026-08-27, see header — preferentially targeting influential humans with
valence-matched content) is only PARTIALLY confirmed in finance/crypto: coordinated bots
demonstrably piggyback high-attention tickers to promote low-value ones (9M
tweets, 5 US markets) and mass-broadcast invite links, but valence-matched
targeting of influential human accounts specifically has no crypto
replication found.

**Citations:** Stella, Ferrara & De Domenico, PNAS 115(49):12435-12440,
2018, doi:10.1073/pnas.1803470115 (seed); Cresci, Lillo, Regoli, Tardelli &
Tesconi, "Cashtag Piggybacking", ACM Transactions on the Web 13(2), 2019,
doi:10.1145/3313184; Nizzoli et al., IEEE Access 2020; Tardelli, Avvenuti,
Tesconi & Cresci, "Detecting inorganic financial campaigns on Twitter",
Information Systems 103, 2022, doi:10.1016/j.is.2021.101769 *(year corrected
2026-08-27: article is vol 103, 2022; the DOI's 2021 string reflects
acceptance)*.

**Mechanism:** Attention-hub free-riding replaces hub-persuasion: crypto
bots exploit the audience of high-value tickers rather than converting
influencers — same amplification economics, different graph tactic. The
hub-targeting leg of the bridge remains an owed literature/measurement item.

**Testable:** Not with current data (no social-graph feed). Detection
framing: piggyback bursts should appear as cross-asset attention contagion
(major-coin news followed by thin-alt volume) in read-only OKX/Binance.US
feeds.

---

## enforce-1 — influencer coordination at scale, in court records [C]

**Claim:** SEC/DOJ charged 8 influencers (Dec 2022) with a $100M scheme
($114M per DOJ, Jan 2020-Apr 2022) — buy first, post price targets to
hundreds of thousands of followers via Twitter and the 150,000-member Atlas
Trading Discord, then sell undisclosed into the induced demand.

**Citations:** SEC Press Release 2022-221; SEC Litigation Release LR-25591 —
allegations/charges, equities not crypto; grade C per court-record rule.

**Mechanism:** Influencer buys -> valenced posts to captive audience ->
follower flow lifts price/volume -> undisclosed distribution into that flow.
Human-influencer analog of the bot amplification loop; the loser is the
follower cohort who-loses-to-us classifies as emotional flow.

**Testable:** Not directly (equities). Transferable signature — attention
spike preceding distribution — is what THALES-class detectors and the
euphoria fade (sentiment/fear_filter.py:110-113 per criminology doc) point
at; owed: does euphoria_spike (scanner.py:60) ever coincide with subsequent
adverse selection in our fills. See 06 spec T17.

---

## narrative-1 — only the compressed pump cycle is measured [D]

**Claim:** Of the folklore narrative cycle (accumulation -> amplification ->
distribution), only the compressed pump version is actually measured —
pre-announcement insider accumulation and post-peak distribution within
minutes (Xu & Livshits n=412; Dhawan & Putniņš 65% distortion) — while
multi-week "narrative cycles" in crypto have no peer-reviewed measurement
found in this pass.

**Citations:** Xu & Livshits, USENIX Security 2019; Dhawan & Putniņš, Review
of Finance 27(3), 2023; multi-week form: no peer-reviewed measurement
located — the citation gap is itself the claim; owed a dedicated literature
pass before any "narrative regime" feature is proposed.

**Mechanism:** If the long form existed and were measurable, the
distribution phase would be the harvestable leg for patient capital;
asserting it from folklore without measurement is exactly the orphan-claim
pattern the vault forbids.

**Testable:** Not with current data at multi-week scale: our labeled corpus
(343 live labels, uniqueness 0.152 per LS-2) cannot resolve multi-week
regimes; evidence-gated capacity rule applies.

---

## attr1-design-1 — the ATTR-1 flatline is structural, an instrument defect [D]

**Claim:** The literature-supported sentiment signal design is
platform-native text (X/StockTwits/Telegram) with a bullishness ratio,
message volume, and a bot-share filter at hourly-to-2-day horizons; our
ATTR-1 flatline (0.002 through the 2026-08-20 policy melt-up) is structural,
because the deployed scanner reads only Google News RSS, crypto-outlet RSS
and Hacker News through a lexicon (scanner.py:10-31) — none of which is the
channel any predictive study measured.

**Citations:** Design inputs: Kraaijeveld & De Smedt 2020; Chen, Guo &
Renault SSRN 3398423; Renault, J. Banking & Finance 84:25-40, 2017,
doi:10.1016/j.jbankfin.2017.07.002 (intraday half-hour sentiment-return
evidence, equities). Gap record: docs/HANDOFF.md ATTR-1 (lines 97-116).

**Mechanism:** A lexicon over headline nouns cannot register policy valence
the way trader-authored posts do; the instrument, not the market, produced
the 0.002 — the-method's first suspect confirmed by reading the instrument.

**Testable:** Yes, NOW: replay the 2026-08-20 archived headlines through
sentiment/lexicon.py score_text and inspect per_source/volume_z
(scanner.py:57-63) — separates "lexicon blind to policy vocabulary" from
"feeds returned nothing" (currently the SAME OBSERVATION). Any feed upgrade
is SAFE-class measurement until it touches sizing; it must not become a new
fitted knob outside config.json. See 06 spec T15a.
