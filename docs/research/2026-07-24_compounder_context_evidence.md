# Compounder Phase B — context-input evidence adjudication

Date: 2026-07-24 · Status: FILED — freezes Phase B's design details per
the spec (`docs/superpowers/specs/2026-07-24-compounder-framework-design.md`
§3: "research runs first; freezes Phase B details"). Produced by the
fintech-quant-researcher literature pass (every citation search-verified
during the pass; unverifiable claims are flagged as such) with the
financial-analyst adjudication frame: every candidate input gets an
evidence grade, an encoding recommendation, an explicit DoF cost, and —
where killed — the citation that killed it. REJECTED entries are part of
the record (T6 durable-findings precedent): future sessions must not
re-propose them without new evidence.

## Decision summary (what Phase B builds, per this evidence)

- **Adopt (3–4 model-adjacent features max):** composite FRED stress dial
  (STRONG as risk-dial, never alpha); CFTC COT net-positioning delta
  (MODERATE, keyless weekly CSV); stablecoin aggregate-supply delta
  (MODERATE, DefiLlama keyless); optionally halving-phase position as
  long-horizon label metadata only.
- **Adopt at 0 model DoF:** halving phase clock as structural gate
  (buckets are labeled CONVENTIONS, not findings; down-only influence);
  CME-expiry + FOMC cadence-pause gates (vol evidence real, direction
  contradictory → pause, never sign).
- **Spec correction:** `basis_bps` is a PERP/SPOT basis, not CME basis.
  Real-time CME basis has no keyless source — the existing perp basis
  (with BIS WP 1087 behind it) IS the institutional-flow basis term; do
  not build a CME scraper.
- **Deferred:** MVRV/realized-cap as a single monotone input, only if a
  keyless EOD source verifies at implementation (degrade to `unknown`).
- **Rejected (8 entries, citations below):** AI-wave input, day-of-week
  features, direction-signed expiry, ETF flows (this program), halving
  bucket boundaries as evidence-claims, MVRV threshold gates, influencer
  sentiment as direction, a new crypto stop-hunt detector.
- **THALES candidates (shadow-first, veto-only):** TH-018 signed spoof,
  TH-019 venue volume integrity, TH-020-family pump veto; plus 0-DoF
  ladder-placement hygiene (long-book bids never rest in TH-013 hot
  zones).

---

# Literature adjudication (full research pass)

Scope: adjudicates the eight candidate input families for the Compounder
Framework Phase B cycle/macro context engine (spec §3). Governing honesty
rule: ~3 complete 4-year cycles exist; nothing is *learned* at that
horizon — inputs enter only as deterministic structural context. Every
input is graded against what this repo already enforces: purged
walk-forward, shuffle nulls, PBO on the deployed rule, DSR
(`scripts/overfit_check.py` OF-1..OF-7).

Verification discipline: every citation below was confirmed to exist via
web search during this pass. Where a paper could not be verified, that is
said explicitly. Headline results from unpublished working papers are
flagged as unvalidated by our OOS standard.

## 0. Repo baseline and the DoF ledger this doc spends against

- Corpus: 3,628 labeled rows.
- Deployed feature vector: **62 names** (`ml/features.py:96–131`) →
  ~58.5 rows/feature today. OF-7 fails below 10 rows/feature
  (`scripts/overfit_check.py:532–538`), plus a dead-feature-fraction
  check. The binding constraint is not OF-7's floor but the program-wide
  "handful" cap and the dead-feature check: a context feature that never
  varies within the training window (a 4-year phase barely moves across
  3.6k 5m-labeled rows) reads as near-zero importance and burns
  dead-feature budget. **Consequence: slow context belongs in structural
  gates and the long book's admission rule, not in the 5m model matrix.**
  Structural gates cost zero model DoF but their thresholds are still
  tunables under config-guard + OF-4 plateau discipline.
- Already-existing context plumbing this doc must not duplicate:
  - Perp/spot cross-venue basis: `basis_bps` = fair value minus Kraken
    mid (`execution/fair_value.py:215–218`), already a signed model
    feature (`ml/features.py:100, 347`, clip ±80 bps) and a fear-filter
    component (`sentiment/fear_filter.py:40, 71`; `config.json`
    `basis_extreme_bps: 40`). **A perp/spot basis, not CME basis** — the
    spec's §3.3 wording conflates the two; see §2.
  - Equity-risk context: `equity_risk_z` feature (`ml/features.py:107,
    361`, clip ±4) fed from the read-only moomoo equity feed.
  - Crowd/sentiment context: `fear_greed`, `dominance_delta`
    (`data/webdata_feed.py:38–41, 88–114`); keyless multi-source
    sentiment scanner, FILTER ONLY by config (`sentiment/scanner.py`).
  - Clock features with drift-exclusion semantics already worked out:
    `hour_sin`, `hour_cos`, `weekend`, `funding_dist`.
  - THALES detector bank TH-010..TH-017 with shuffle-null discipline for
    calendar effects (TH-012), Osler-based stop-cluster model (TH-013),
    feed-integrity shading (TH-014), the certificate hierarchy and the
    **asymmetry law** — slow context layers get veto rights, not alpha
    rights (`docs/THALES.md:212–234`). Spoof detection is live
    (`regime/liquidity_regime.py:308` → "spoofy" → reduce-only, PT-022;
    flicker TH-017).

## 1. Bitcoin halving / 4-year cycle phase — grade: MODERATE (as deterministic anchor), WEAK (as phase template)

**What survives peer review.** The peer-reviewed halving literature is
real but thin-journal and recent:

- Lashkaripour, "Some stylized facts about bitcoin halving", *Finance
  Research Letters* 69 (2024): halvings trigger a slight **negative**
  short-run price reaction, *lower* short-run volatility, higher
  transaction fees, lower miner revenue. Distinguishes supply vs
  security effects.
- "Is Bitcoin's Market Maturing? Cumulative Abnormal Returns and
  Volatility in the 2024 Halving and Past Cycles", *JRFM* 18(5):242
  (2025, MDPI — mid/low tier): 240-day post-halving volatility 2.72%
  (2024) vs 3.24% (2012), 2.21% (2016), 3.92% (2020); mean daily returns
  down sharply from 0.92% (2012) and 0.22% (2016). Documents the
  **diminishing-cycle effect** directly. Peak timing ~12–17 months
  post-halving is descriptive across the same 3 samples (also in MDPI
  JRFM 17(6):229, 2024).
- "The effect of the cryptocurrency halving event", *Pacific-Basin
  Finance Journal* (2025) (author list not verified this pass): trading
  dynamics respond to halvings; sensitivity of network characteristics
  diminishes over time.
- arXiv 2511.05512 (unreviewed): estimation of halving price impact —
  WEAK by construction.

**What is folklore.** The named 4-phase template
(accumulation/expansion/euphoria/contraction) with specific boundaries
has **no peer-reviewed support**. All studies condition on 3 events;
every effect size is an n=3 statistic. The one robust cross-paper
regularity is *diminishing amplitude/return per cycle* — which itself
warns against extrapolating any bucket boundary.

**On-chain slow proxies (MVRV / realized cap).** Origin is practitioner
(Mahmudov/Puell 2018; Carter/Le Calvez realized cap — industry, WEAK by
construction). First peer-reviewed treatment: "Using on-chain data to
predict Bitcoin cycles", *Research in International Business and
Finance* (2026): NUPL, MVRV-Z, CVDD backtested Dec 2013–Apr 2025; MVRV-Z
strategy Sharpe 1.28 vs 0.45 buy-and-hold. **Adjudication against our
standard: an in-sample rule fit over exactly 3 cycles with no purged
walk-forward, no shuffle null, no PBO, no DSR — precisely the artifact
OF-3/OF-5 exist to catch.** The Sharpe is a red flag, not a benchmark.
Related but unpublished: Bhambhwani, Delikouras & Korniotis, "Do
Fundamentals Drive Cryptocurrency Prices?" (SSRN/CEPR WP 2019): long-run
cointegration of prices with network fundamentals — supports "slow value
anchor exists," not any threshold.

**Encoding recommendation.**
- ADOPT: **halving phase clock** as deterministic structural context —
  days-since / days-to-next from public chain constants, exactly as spec
  §3.1 frames it. Buckets are *conventions, not findings*: config-lifted
  with a derivation comment that says "descriptive labels over n=3; no
  statistical claim," and under the THALES asymmetry law the phase may
  only tighten (euphoria → tighten give-back ratchet, contraction → slow
  long-book add cadence), never boost. Matches spec Phase C. Cost: 0
  model features if gate-only; 1 max if the long-horizon label pipeline
  snapshots phase position (it should — that is corpus metadata, not a
  5m model input).
- DEFER: MVRV-Z as a single monotone context input (not a threshold
  gate) — admissible only if a keyless source verifies (Coin Metrics
  community endpoints currently keyless for EOD `CapRealUSD`;
  Glassnode/CryptoQuant are keyed — re-verify at implementation; degrade
  to `unknown` when dark).
- REJECT: any evidence-claimed bucket boundary or MVRV entry/exit
  threshold.

**Data:** halving clock — public constants, fully keyless. MVRV —
partially keyless (EOD community data), fragile.

## 2. Institutional flow proxies — grade: MODERATE overall; per-proxy below

**CME/perp basis and carry — MODERATE-STRONG descriptive, weak as
directional alpha.** Schmeling, Schrimpf & Todorov, "Crypto Carry" (BIS
Working Paper No. 1087, 2022, rev. Oct 2025; SSRN 4268371) — note the
correct author set (Schrimpf/Todorov, not Vedolin): crypto carry
(futures−spot, incl. perp funding) reaches >40% p.a., highly
time-varying; driven by leveraged trend-chasing demand meeting limited
arbitrage capital (margin/regulatory frictions). The mechanism reading:
**extreme positive basis = crowded leverage = fragility**, i.e. a
risk-context dial, not an entry signal. This is the evidence base for
the *perp* basis we already compute — the paper covers perps and CME
alike, so the spec's §3.3 "CME futures basis" requirement is best
satisfied by the existing `basis_bps` plus, if wanted, a slower
funding-rate aggregate (`funding_dir`/`funding_dist` already exist).
Real-time CME basis has **no free/keyless source** (CME data licensing;
delayed-quote scraping is fragile) — do not add a scraper; the perp
basis is the keyless proxy with the better paper behind it.

**CFTC COT positioning — MODERATE.** Dunbar & Owusu-Amoako,
"Predictability of crypto returns: The impact of trading behavior",
*Journal of Behavioral and Experimental Finance* 39 (2023): changes in
speculative traders' net-short positioning in CME bitcoin futures
predict crypto returns, robust to attention/uncertainty/sentiment/
prior-return controls. Single study, mid-tier journal, no purged OOS
discipline reported — MODERATE, not STRONG. Weekly cadence fits the
context engine's "hours, not 5m" cycle. Data: CFTC COT reports — free
weekly CSV, fully keyless. Encoding: one slow feature (z-scored
net-positioning delta) OR a flow term inside the institutional-flow
input; 1 DoF.

**Stablecoin aggregate supply — MODERATE.** Griffin & Shams, "Is
Bitcoin Really Untethered?" — *Journal of Finance* 75(4) (2020): Tether
issuance followed by large BTC purchases, consistent with supply-driven
flow supporting prices (contested — treat as flow-hypothesis evidence,
not settled causality). Ante, Fiedler & Strehle, "The influence of
stablecoin issuances on cryptocurrency markets", *Finance Research
Letters* 41 (2021): downturns the week before issuance; positive
abnormal returns ±24h around issuance. Aggregate stablecoin supply
*growth* as a liquidity proxy is a coarser, more defensible object than
issuance timing. Data: DefiLlama stablecoins API — free, keyless.
Encoding: weekly aggregate-supply delta as the second flow term (spec
§3.3 names exactly this); 1 DoF.

**ETF net flows — MODERATE evidence, FAILS availability →
deferred/REJECTED for Phase B.** Lim, "The Price Impact of Spot Bitcoin
ETF Flows" (SSRN WP 6592830): $100M net inflow ↔ ~53 bps same-day BTC
return (74 bps IV), flows explain ~21% of daily return variance, some
next-day predictability, Jan 2024–Apr 2025. Mazur & Polyzos (SSRN
5452994); Economics Letters 2025 one-year flow analysis; *Ledger* 2025
AUM-price cointegration. All working-paper/early-journal, ~18-month
samples, contemporaneous effects dominant (not tradeable), next-day
claims unvalidated by purged-OOS standards. Decisive: **no keyless
machine-readable source** (Farside is a scrape; issuer APIs keyed) — the
spec's keyless rule forbids it. REJECTED-for-now with revisit trigger: a
keyless source plus a published study.

## 3. Structural stress trio (fed funds, 10y–2y, VIX) — grade: STRONG (risk-on/off context; explicitly NOT alpha)

The literature cleanly supports the spec's framing (risk dial only) and
adds a crucial time-variation fact:

- Liu & Tsyvinski, "Risks and Returns of Cryptocurrency", *Review of
  Financial Studies* 34(6) (2021): in the pre-2019 sample, crypto had
  **no exposure** to standard equity/macro factors. Macro beta is not
  intrinsic — it arrived later.
- Karau, "Monetary Policy and Bitcoin" (Bundesbank Discussion Paper
  41/2021; published 2023): high-frequency identification — BTC did
  **not** respond to US monetary policy announcements until late 2020,
  then began responding like other risky assets; sign asymmetries
  between Fed and ECB shocks; FOMC-window volatility elevated
  post-COVID.
- Che, Copestake, Furceri & Terracciano, "The Crypto Cycle and US
  Monetary Policy", IMF WP 2023/163: one "crypto factor" explains ~80%
  of crypto price variation; Fed tightening lowers it via the
  **risk-taking channel**; crypto-equity correlation rose with
  institutional participation (follow-up: Copestake et al., "The Crypto
  Cycle and Institutional Investors", SSRN 4956413).
- Iyer, "Cryptic Connections: Spillovers between Crypto and Equity
  Markets", IMF Global Financial Stability Note 2022/01: BTC↔equity
  volatility spillovers up 12–16pp since COVID.

**Verdict:** crypto's macro beta is real, large post-2020, and
*regime-dependent* — exactly why it must be a structural dial and never
a fitted coefficient (a coefficient learned on post-2020 data assumes
the regime persists; Liu-Tsyvinski shows it hasn't always). Evidence is
specific to policy stance and risk appetite (fed funds path, VIX);
**10y–2y has no crypto-specific predictive literature** — it enters only
as generic recession/stress context and is the first term dropped if
the feature budget tightens.

**Encoding:** one composite stress dial (fixed-clip z-scores, same
pattern as `equity_risk_z` — no fitted weights), consumed as (a)
long-book context-alignment term (Phase A term 4) and (b) at most ONE
model feature if OF-7 headroom allows. Down-only influence per the
asymmetry law. **Data: fully keyless** — FRED
`fredgraph.csv?id=DFF|T10Y2Y|VIXCLS` endpoints require no key.

## 4. Event-calendar effects — grade: MODERATE (volatility/cadence), REJECTED (direction, day-of-week features)

**CME expiry.** "Is there an expiration effect in the bitcoin market?",
*International Review of Economics and Finance* 85 (2023) 647–663:
significant changes in volume, volatility, and returns around futures
maturity, intensifying near the expiry timestamp; heterogeneous across
CME/CBOE/Bakkt; prevailing CME result is *positive* abnormal returns
attributed to short-arb unwinding. Industry prior (Arcane Research
2019): −2.2% pre-settlement drift 2018–19 — WEAK by construction and
**opposite in sign** to the IREF result. Also relevant: FRL 2026 on
option expiry/gamma/intraday reversals; "Is There Any Witching in the
Cryptocurrency Market?", JRFM 15(2):92 (2022). **Adjudication: the
settled fact is elevated vol/volume near expiry; direction is
contradictory across sources → only a cadence pause is admissible.**
Exactly the spec's design (§3.4: calendar gates cadence, never
direction). Expiry timing is deterministic (last Friday of contract
month, 4:00 p.m. London BRR settlement): pure calendar, keyless, 0
model DoF.

**FOMC.** Karau (above) documents pre-FOMC drift (~65 bps, negative
into FOMC in his sample) and post-2020 announcement sensitivity;
"Scheduled FOMC statements and intraday macro event risk in
cryptocurrency markets", *FRL* (2026) confirms elevated intraday event
risk. Drift *direction* is one-sample-regime evidence — pause, don't
sign. FOMC dates published yearly → shipped data file per spec. 0 DoF.

**Day-of-week / turn-of-month.** In-sample effects were published —
Aharon & Qadan (FRL 2019, Monday effect); Caporale & Plastun (FRL
2019); Baur et al. (FRL 2019, time-of-day/DoW/MoY) — but post-2020
evidence shows the anomalies mutated or faded: JRFM 17(8):351 (2024)
(DoW effects differ before/during COVID, Monday effect diminished,
Friday sign flipped); post-COVID BTC/ETH calendar-anomaly study (2024).
**REJECTED as standing calendar features.** The repo already holds the
correct mechanism: `hour_sin/hour_cos/weekend` are model inputs the
learner can use or ignore, and TH-012 `clockwork_flow` admits
time-bucket effects only past a live shuffle-null. Nothing to add;
anything more is seasonality mining (OF-2/OF-4 violation).

## 5. AI-investment wave — grade: REJECTED

Searched for peer-reviewed evidence linking AI-sector investment flows
or narrative intensity to crypto cycles. **None found.** What exists is
industry commentary: NVDA-BTC 90-day correlation >0.8 in 2025
(Yahoo/CoinDesk, CCN, Cointelegraph) and AI-token comovement anecdotes.
That correlation *is* the shared risk-appetite/liquidity factor already
established by the macro literature (IMF WP 2023/163's single crypto
factor; Iyer 2022) and already present as `equity_risk_z`. An AI-flow
input would be a **redundant re-measurement of the stress dial at +1
DoF with zero incremental peer-reviewed evidence**. Rejection citation:
absence of any published study (search-verified July 2026) + redundancy
with Che, Copestake, Furceri & Terracciano (IMF WP 2023/163).

## 6. Influencer/social sentiment — grade: WEAK (returns alpha at daily+), MODERATE (attention → volume/volatility)

- Shen, Urquhart & Wang, "Does twitter predict Bitcoin?", *Economics
  Letters* 174 (2019): tweet **volume** predicts next-day trading
  volume and realized volatility — **not returns**.
- Kraaijeveld & De Smedt, "The predictive power of public Twitter
  sentiment for forecasting cryptocurrency prices", *JIFMIM* 65 (2020):
  predictive content for BTC/BCH/LTC over a short 2018 window; the
  authors themselves document Twitter bot contamination.
- "Does investor sentiment on social media provide robust information
  for Bitcoin returns predictability?", *FRL* (2020) and "On the
  predictive power of tweet sentiments and attention on bitcoin",
  *IREF* (2022): return-predictability robustness fails once
  controls/windows change.
- The strongest attention result remains Liu & Tsyvinski (RFS 2021):
  *attention* proxies forecast weekly returns — attention is not
  influencer sentiment.

**Verdict matches the prior:** mostly noise as a directional signal;
some information as an activity/volatility conditioner. **Adopt nothing
new.** The existing keyless scanner stays FILTER ONLY; `sent_dir`/
`sent_fear` stay as the two model features they already are. StockTwits
remains a read-only *candidate* per the spec — no evidence upgrade
warrants promotion.

## 7. Strongest academic anchors: momentum, factors, seasonality, long-horizon reversion

The five papers worth keeping on file (all verified, all peer-reviewed,
strongest OOS discipline available in this literature):

1. **Liu & Tsyvinski, RFS 34(6) 2021** — Risks and Returns of
   Cryptocurrency: time-series momentum at 1–4 week horizons; attention
   predicts; no exposure to standard stock/macro factors in-sample. The
   momentum result has survived replication better than most crypto
   anomalies.
2. **Liu, Tsyvinski & Wu, JF 77(2) 2022** — Common Risk Factors in
   Cryptocurrency: crypto market/size/momentum 3-factor model prices
   the cross-section; ten characteristic strategies subsumed by three
   factors.
3. **Fieberg, Liedtke, Poddig, Walker & Zaremba, JFQA 2025** — A Trend
   Factor for the Cross Section of Cryptocurrency Returns: multi-horizon
   trend information priced in the cross-section.
4. **Dhawan & Putniņš, Review of Finance 27(3) 2023** — A New Wolf in
   Town? (manipulation; §8).
5. **Cong, Li, Tang & Yang, Management Science 69(11) 2023** — Crypto
   Wash Trading (§8).

**Long-horizon mean reversion:** no robust peer-reviewed multi-month
mean-reversion result for BTC/majors could be verified. The closest
published evidence is short-horizon post-abnormal-day behavior (FMPM
2021) and the diminishing-cycle amplitude descriptives (§1). **The long
book's accumulation thesis must rest on the structural-context gates,
not on a claimed reversion anomaly.**

**Placement:** none of this changes the 5m book (momentum at 1–4 *weeks*
is outside its horizon; `mom_dir` and `ret_*_dir` already cover
intra-horizon drift). For the long book, the momentum literature argues
accumulation adds should not fight multi-week trend — encode, if at
all, as a context-alignment term in the Conviction Formula (Phase A
term 4), not a new model feature. Cross-sectional factors are
inapplicable (a handful of Kraken pairs, not a 1,800-coin
cross-section).

## 8. THALES hardening — manipulation evidence → detector candidates

Each finding, its observable signature, and where it lands in the
existing bank:

1. **Spoofing/layering (crypto-native evidence).** John, Li, Liu &
   Yang, The Impact of Spoofing on Bitcoin Market Microstructure (SSRN
   WP 5771502, Coinbase data): bid-side spoofing intensity → positive
   returns, ask-side → negative; estimated spoofing profits ~27 bps
   (bid) / ~55 bps (ask) per unit intensity; spoofing widens spreads
   and degrades market quality. Also arXiv 2504.15908 (Learning the
   Spoofability of Limit Order Books) for detection methodology. *Repo
   state:* a direction-neutral spoof score already exists and blocks
   new risk when the book labels "spoofy" (PT-022). **Candidate TH-018
   `signed_spoof`:** side-resolved spoof intensity (large transient
   non-executing depth within N bps of the touch, canceled untraded —
   extending TH-017 flicker) that vetoes entries *aligned with* the
   spoof-pushed direction, since the paper documents the push reverting
   after cancellation. Shadow first; working-paper evidence ⇒
   advise-mode only after the V2 vindication ledger beats null.
2. **Wash trading / painted volume (venue-level).** Cong, Li, Tang &
   Yang, *Management Science* 69(11) 2023: >70% of reported volume on
   unregulated exchanges is wash; authentic markets show
   Benford-consistent first significant digits, round-size clustering,
   and power-law trade-size tails — wash venues violate all three.
   Aloosh & Li, Direct Evidence of Bitcoin Wash Trading, *Management
   Science* 70(12) 2024, validates the methodology on leaked Mt. Gox
   internal data. Le Pennec, Fiedler & Ankenbrand (FRL 2021)
   corroborate volume-based detection. **Candidate TH-019
   `venue_volume_integrity`:** per-read-only-venue rolling
   first-digit/size-clustering score, used to *weight the venue's
   contribution to fair value and volume features down* (defensive
   complement to TH-014). Never a direction. Kraken (regulated,
   execution venue) is the trust anchor; OKX/Binance read-only feeds
   are the objects of suspicion.
3. **Pump-and-dump (alt protection).** Dhawan & Putniņš, *Review of
   Finance* 27(3) 2023: 355 pumps in 6 months on two exchanges; ~$350M
   manipulation-day volume; ~$6M extracted; price spikes ~65% in
   minutes on illiquid coins, full reversal within days. **Candidate
   TH-020-family `pump_veto`:** minutes-scale conjunction of extreme
   volume z + extreme return z on a thin alt *without cross-venue price
   confirmation* → entry veto + "not a structural level" flag for the
   long book (a spoofed level is not a structural level). Defensive
   only; majors exempt by liquidity threshold.
4. **Stop-hunt / sweep-revert.** The peer-reviewed base remains FX:
   Osler, Currency Orders and Exchange Rate Dynamics (JF 2003) and
   Stop-Loss Orders and Price Cascades in Currency Markets (*JIMF*
   24(2) 2005; NY Fed SR 150): stop clusters generate self-reinforcing
   cascades, stronger and longer-lived than take-profit responses.
   Crypto-native peer-reviewed sweep studies: **not verified** —
   liquidation-cascade mechanics appear in the BIS Crypto Carry
   margin-spiral discussion but not as a standalone microstructure
   result. *Repo state:* TH-013 already implements exactly Osler's
   signature with close-back-inside confirmation. **Hardening candidate
   (no new detector):** the long book's bid ladders must not REST
   inside TH-013 hot cluster zones — reuse the existing zone
   computation for ladder placement hygiene at Phase C. 0 new DoF.
5. **Exchange-operator manipulation (historical).** Gandal, Hamrick,
   Moore & Oberman, Price Manipulation in the Bitcoin Ecosystem,
   *Journal of Monetary Economics* 95 (2018): Mt. Gox bots
   (Willy/Markus); +4% average on suspicious-activity days vs slight
   decline otherwise. Motivates venue-integrity monitoring (candidate
   2) rather than a live detector — the venue itself can be the
   manipulator, which is why detection must run on *our* observed
   books, not venue-reported aggregates.
6. **"Painting the book" beyond the above:** no additional
   crypto-specific peer-reviewed anchor verified this pass; none is
   claimed.

All candidates obey the existing hard boundaries: detect-and-react
only, shadow-first, registered TH-* codes, bounded shades.

## Summary table

| # | Input | Grade | Encoding recommendation | Model DoF cost | Data source (keyless?) |
|---|---|---|---|---|---|
| 1a | Halving phase clock | MODERATE (anchor) / WEAK (phase template) | Structural gate + long-book context term; buckets config-lifted as *conventions*; down-only influence | 0 (gate) – 1 (long-book label metadata) | Chain constants — yes |
| 1b | MVRV / realized cap | MODERATE (proxy), WEAK (thresholds) | Deferred: single monotone context input only if keyless EOD source verified; never a threshold gate | 0–1 | Coin Metrics community EOD — conditionally yes; verify, degrade to `unknown` |
| 2a | Perp/CME basis (carry) | MODERATE-STRONG (fragility context) | Keep existing `basis_bps` + slow funding aggregate as crowded-leverage dial; no new alpha use | 0 (exists) | Existing feeds — yes. CME real-time — **no** (skip) |
| 2b | CFTC COT net-positioning delta | MODERATE | Weekly flow term in institutional-flow input | 1 | CFTC CSV — yes |
| 2c | Stablecoin aggregate-supply delta | MODERATE | Weekly flow term in institutional-flow input (spec §3.3 as written) | 1 | DefiLlama — yes |
| 2d | ETF net flows | MODERATE evidence / fails availability | REJECTED for Phase B; revisit on keyless source + published study | — | None keyless — no |
| 3 | Stress trio (FF, 10y–2y, VIX) | STRONG (risk dial), never alpha | One composite fixed-clip z dial → long-book context alignment; ≤1 model feature; 10y–2y first to drop | 1 (composite) | FRED fredgraph.csv — yes |
| 4a | CME expiry calendar | MODERATE (vol), REJECTED (direction) | Cadence pause gate on long-book adds | 0 | Deterministic rule — yes |
| 4b | FOMC calendar | MODERATE-STRONG (event vol) | Cadence pause gate; shipped yearly data file | 0 | Fed schedule — yes |
| 4c | Day-of-week / turn-of-month | REJECTED | Nothing; TH-012 shuffle-null + existing clock features already correct | 0 | — |
| 5 | AI-investment wave | REJECTED | Nothing; redundant with stress dial / `equity_risk_z` | 0 | — |
| 6 | Influencer/social sentiment | WEAK (returns) / MODERATE (activity) | Status quo: FILTER ONLY; StockTwits stays read-only candidate | 0 (exists) | Existing keyless scanner — yes |
| 7 | Momentum/factor literature | STRONG (published) | Long-book context-alignment term only (don't fight multi-week trend); nothing for 5m book | 0 | Own price data — yes |
| 8 | THALES candidates (signed spoof, venue volume integrity, pump veto, ladder-placement hygiene) | MODERATE (papers real; detectors need shadow evidence) | Shadow-first detectors, defensive/veto-only, V2 vindication ledger before advise | 0 (advice channel) | Own L2/candle observation — yes |

Proposed spend against the "handful" cap: **3–4 new model-adjacent
features max** (stress dial, COT delta, stablecoin delta, optionally
halving-phase position for the long-horizon label pipeline), everything
else gates/pauses at 0 model DoF. At 62 features today this keeps
rows/feature ≈ 55+, far above the OF-7 floor — but each must still clear
the dead-feature check and earn admission like every existing feature.

## REJECTED list (with the citation that killed each)

1. **AI-investment wave input** — killed by absence: no peer-reviewed
   study exists (search-verified July 2026); the observed NVDA-BTC
   comovement is the common risk factor already established by Che,
   Copestake, Furceri & Terracciano (IMF WP 2023/163) and already
   measured by `equity_risk_z`.
2. **Day-of-week / turn-of-month calendar features** — killed by
   post-2020 instability: JRFM 17(8):351 (2024) and post-COVID
   follow-ups show the Aharon-Qadan (FRL 2019) / Caporale-Plastun (FRL
   2019) effects mutated or vanished; classic OF-4 bait.
3. **Direction-signed expiry effect** — killed by sign contradiction:
   IREF 85 (2023) finds *positive* CME expiry abnormal returns; Arcane
   (2019, industry) found *negative* pre-settlement drift. Only the
   volatility/cadence fact survives.
4. **ETF net-flow input (this program)** — killed by the spec's own
   keyless rule + evidence recency: only working papers (Lim, SSRN
   6592830; Mazur & Polyzos, SSRN 5452994) on ≤18 months of data,
   contemporaneous-dominated.
5. **Evidence-claimed halving phase-bucket boundaries** — killed by
   n=3: every halving study (Lashkaripour FRL 2024; JRFM 18(5):242
   2025; PBFJ 2025) conditions on three events; the one robust
   regularity (diminishing amplitude) argues *against* boundary
   extrapolation. Buckets ship as labeled conventions only.
6. **MVRV threshold gates** — killed by our own standard: RIBAF (2026)
   MVRV-Z Sharpe 1.28 is an in-sample rule over exactly 3 cycles with
   no purge/null/PBO/DSR — the artifact scripts/overfit_check.py exists
   to reject.
7. **Influencer sentiment as a directional feature** — killed by Shen,
   Urquhart & Wang (Economics Letters 2019: volume/volatility only, not
   returns) plus failed robustness in follow-ups (FRL 2020; IREF 2022);
   Kraaijeveld & De Smedt (JIFMIM 2020) is window-limited and
   bot-contaminated by its own admission.
8. **Crypto-native stop-hunt "new detector"** — no crypto-specific
   peer-reviewed sweep study verified; TH-013 already encodes the
   strongest available evidence (Osler JF 2003 / JIMF 2005). Only the
   ladder-placement hygiene reuse is admissible.

Unverified-and-therefore-unclaimed this pass: authors of the PBFJ 2025
halving paper and the IREF 2023 expiry paper (papers verified, author
lists not); Hamrick et al. / Xu & Livshits pump-and-dump papers (not
searched — Dhawan & Putniņš carries the section alone); any published
version of Bhambhwani et al. beyond SSRN.

## Addendum (2026-07-24, operator-supplied): CoinPaprika as keyless vendor

Operator surfaced CoinPaprika's hosted MCP server (mcp.coinpaprika.com).
Adjudication: MCP is an AI-client protocol — the bot's runtime consumes
plain REST, so the relevant object is CoinPaprika's free keyless REST
API (api.coinpaprika.com: /v1/global for market cap + BTC dominance,
/v1/tickers for prices/volumes). Fits the keyless rule at hourly
context cadence. Role: REDUNDANT second source behind webdata_feed's
fear-greed/dominance so context degrades to `unknown` less often —
grades and adoptions above are unchanged. Does NOT unlock deferred
MVRV (no realized-cap data); DefiLlama remains the stablecoin-supply
source. Read-only context only; no execution surface.
