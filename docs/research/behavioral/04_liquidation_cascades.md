# Lens 04 — margin shorts, liquidation cascades, and who harvests them

We hold no margin and never will (Kraken-spot-only, CLAUDE.md invariant 3);
everything here models OTHER participants. See README for legend and bars.

---

## liq-asym-1 — long-side liquidation asymmetry on BitMEX [B] [FLAGSHIP — AMENDED]

**Amended claim (verdict text, use this):** On BitMEX inverse (coin-margined)
BTC perpetuals, Jan 29 2020 - Feb 3 2021 (372 days, sample includes the Mar
12 2020 crash), daily forced liquidations averaged 3.51% of open interest on
the long side vs 1.89% on the short side (1.86x), with liquidated-position
leverage INFERRED at ~60x average from liquidation-price distance under an
open-at-daily-open assumption. Long-side dominance is an unconditional
average driven by retail long bias PLUS the inverse-payoff convexity (absent
in today's dominant linear USDT-margined perps, which also cap leverage
lower); cascade side is direction-conditional — down-moves liquidate longs,
up-moves liquidate shorts (max short-liquidation day was a +10% rally).
Direction independently corroborated (WWW '21 BitMEX case study) but the
ratio is unstable across instruments and eras. Grade B, single venue,
pre-2021 regime; treat 1.86x as era-bound, not a constant.

**Verdict: AMENDED — core numbers CONFIRMED verbatim from the primary source;
four defects.** (1) The original "non-crash regimes" scoping is NOT in the
paper and is contradicted by its own extremes: max long liquidation ($843M)
on the Mar 12 2020 crash, max SHORT liquidation ($132M) on a +10% rally day
(Jun 1 2020). (2) 60x is INFERRED (paper eq. 4.2/4.4), not observed —
"liquidated accounts traded at" overstated provenance. (3) Inverse
coin-margined payoff contributed part of the asymmetry; today's volume is
predominantly linear USDT-margined (<=20x-125x caps), so the mechanical
component of 1.86x does not transfer. (4) Direction corroborated but
magnitude "somewhat unstable" (WWW '21, doi:10.1145/3442381.3450059).

**Citations:** Cheng, Deng, Wang & Yu 2021, Applied Economics 53(47),
doi:10.1080/00036846.2021.1922597; arXiv:2102.04591; "Towards Understanding
Cryptocurrency Derivatives: A Case Study of BitMEX", WWW '21,
doi:10.1145/3442381.3450059.

**Mechanism:** Retail long bias (+ payoff structure, era-dependent) means
adverse down-moves hit longs harder; the liquidation engine emits
price-insensitive market sells that gift liquidity to resting bids — the
forced-flow counterparty class who-loses-to-us says we monetize via
resting-limit-only entries (OM-011).

**Testable:** Not with current data — ATTR-2 (confirmed by grep: zero
OI/liquidation ingest in liquiditybot_ab). Cheapest add: OKX read-only
public liquidation-orders + open-interest endpoints in data/okx_feed.py
beside get_funding_rate (okx_feed.py:168-201); SAFE class, does not reset
the era cohort. See 06 OWED DATA.

---

## stop-cluster-1 — round-number stop clusters and price cascades [A clustering / B mechanism] [FLAGSHIP — AMENDED]

**Amended claim (verdict text, use this):** Stop-loss and take-profit orders
cluster around round numbers (pooled: almost 10% of 9,655 orders / >$55B
face value at rates ending in 00 vs ~1% uniform; RBS complete order book,
Aug 1 1999 - Apr 11 2000), with a placement asymmetry that is the tradable
structure: take-profits cluster ON round numbers, stop-losses just BEYOND
them (sells below, buys above). Price moves are unusually rapid through
inferred stop clusters and the stop-loss response is larger and
longer-lasting than the take-profit response — but the cascade tests ran on
non-overlapping 1996-1998 FX quote data with cluster locations assumed
stationary, significance holds at hourly not daily horizons, and the author
disclaims causal proof. Grade A for round-number clustering and price
effects (independently replicated across markets including crypto prices:
Urquhart 2017; FRL 2022); grade B for the stop-loss forced-flow mechanism
itself (one bank's labeled orders, one author). It is the best-documented,
not the only, price-side-detectable forced/constrained-flow predictability
(cf. magnet effect of price limits, Cho et al. 2003, replicated in Korea,
failed in Spain).

**Verdict: AMENDED — core facts CONFIRMED from NY Fed SR150 full text; five
amendments.** (1) The ~10%-at-00 figure is POOLED stops + take-profits;
stops cluster just BEYOND round numbers, TPs ON them — this placement
asymmetry changes the sign structure of any Kraken event study
(breach-acceleration past the level vs bounce at it). (2) Cascade tests used
minute quotes on dollar-mark/yen/pound Jan 1996 - Apr 1998 — NON-overlapping
with the 1999-2000 order sample; stationarity assumed; "statistical analysis
cannot prove that the connection is causal" (Osler's own words). (3) Horizon:
significant for HOURS, not days. (4) "Replicated" holds for round-number
CLUSTERING (incl. crypto: Urquhart 2017 Economics Letters; "Evidence for
round number effects in cryptocurrencies prices", FRL 2022,
doi:10.1016/j.frl.2022.102811; "Psychological barriers in the cryptocurrency
market" 2019) but NOT for the labeled stop-loss ORDER mechanism (one bank's
book, one author: Osler 2003 JF + 2005 JIMF share the dataset). (5) "The
only" price-side forced-flow predictability overstated — magnet effect of
price limits (Cho, Russell, Tiao & Tsay 2003, J. Empirical Finance,
doi:10.1016/S0927-5398(02)00024-5; replicated Korea, failed Spain) is a
second one.

**Citations:** Osler 2003, Journal of Finance 58(5); Osler 2005, JIMF
24(2):219-241, doi:10.1016/j.jimonfin.2004.12.002; NY Fed Staff Report 150
(newyorkfed.org/medialibrary/media/research/staff_reports/sr150.pdf); plus
replication cites above.

**Mechanism:** Stops generate positive-feedback trading: cluster breach ->
forced market orders -> price discontinuity -> next cluster; whoever rests
limits just past the cluster receives forced flow at a discount. Already the
cited basis of the who-loses-to-us forced-flow arm and THALES TH-013
stop-herding (the only detector that has ever fired: 100% of advice events,
vault entities/thales-engine.md).

**Testable:** Yes, on our corpus now — event-study Kraken spot 1m candles at
round-number levels with the AMENDED sign structure; OF-2 shuffle null;
effective-n per gate_truth_report. Any resulting entry-placement change is
COHORT-RESETTING and needs operator adjudication. See 06 spec T9.

---

## cascade-ews-1 — no event-invariant cascade early warning [C]

**Claim:** Across seven Binance BTC perp cascades 2022-2025 (1-min price,
5-min leverage/flow, ~2-month windows each; Oct-2025 event: $19B liquidated,
1.6M accounts, OI -24.6% intraday), NO event-invariant early-warning variable
exists; the only cross-event regularity is taker order-flow variance
COMPRESSION before onset (6/7 events, median Kendall-tau -0.13 to -0.44,
placebo-tested at 300 ordinary onsets, Fisher-combined p~5e-6); price lag-1
autocorrelation flagged only 5/7 and was absent in both tariff-shock events.

**Citations:** Garcia Seuma 2026, arXiv:2607.27070 (preprint, not yet
peer-reviewed).

**Mechanism:** Pre-cascade quieting of aggressive-flow variance = crowd
positioning frozen at high leverage; exogenously-triggered cascades carry no
endogenous precursor — a cascade "predictor" structurally misses the biggest
events. This is a shade-down/stand-aside signal, not an entry signal.

**Testable:** Partial — we compute event-based OFI (ml/features.py:100-101,
Cont-Kukanov-Stoikov) on Kraken/Binance.US spot books: replicate rolling
variance of taker-proxy flow, test compression vs subsequent realized range
on recorded feed history. Full replication needs perp taker buy/sell + OI
(ATTR-2). Consume as a THALES-style shadow detector first, never a sizing
input without shadow evidence. See 06 spec T10.

---

## stophunt-folklore-1 — crypto "stop hunting" lore is unmeasured [D]

**Claim:** Crypto-specific stop hunting / liquidity sweeps /
liquidation-heatmap targeting has NO peer-reviewed measurement — the
quantified evidence base for deliberate stop-triggering is FX order-book work
(Osler) plus regulator spoofing cases; heatmap lore (Coinglass-style) is
unvalidated vendor inference from assumed leverage distributions.

**Citations:** Osler 2005, JIMF 24(2) (the measured FX baseline the folklore
extrapolates from); Kamps & Kleinberg 2018, Crime Science 7:18,
doi:10.1186/s40163-018-0093-5 (nearest peer-reviewed crypto manipulation
measurement; covers pumps, NOT stop-hunts).

**Mechanism:** Heatmap vendors infer liquidation prices from OI deltas +
assumed leverage tiers; traders narrate sweeps post hoc; survivorship of
confirming anecdotes. Distinguishing "price seeks liquidity" (mechanical,
Osler-consistent) from "actor hunts stops" (intent) is an
observational-equivalence problem TH-017 already failed at (honest maker vs
layerer both 0.949) — expect the same identifiability wall.

**Testable:** Mechanical (non-intent) version only: do Kraken spot wicks
disproportionately terminate just beyond prior swing extremes then revert,
vs shuffle null (OF-2 style)? Intent attribution NOT testable with any feed
we can add. Detection-only per compliance fence. See 06 spec T11.

---

## carry-decay-1 — crypto carry harvests retail long bias, and has decayed [B]

**Claim:** Crypto carry (short perp / long spot harvesting retail long bias
via funding) reached >40% annualized at peaks, driven by trend-chasing
small-investor leverage demand against limited arbitrage capital, and has
DECAYED hard: full-sample 2020-2025 Sharpe 6.45 falls to 4.06 from 2024 and
turns NEGATIVE in 2025 — and it is structurally unavailable to us regardless
(no perp leg; invariant 3).

**Citations:** Schmeling, Schrimpf & Todorov, "Crypto Carry", Management
Science 2026 (Articles in Advance, 0(0)), doi:10.1287/mnsc.2024.05069
*(citation corrected 2026-08-27: page previously dated it 2025; the MS
record shows 2026/forthcoming)*; BIS WP 1087, April 2023
(bis.org/publ/work1087.pdf — confirmed, carries the >40% p.a. carry and the
trend-chasing-retail-vs-limited-arbitrage mechanism verbatim);
"Cryptocurrency as an Investable Asset Class: Coming of Age" 2025,
arXiv:2510.14435 (decay numbers; preprint, grade C on its own).

**Mechanism:** Retail longs pay funding to whoever shorts the perp; carry
desks harvest it and carry crashes when the long crowd deleverages — the
SAME loser pool who-loses-to-us names, harvested by better-capitalized
specialists, replenished not educated. For us the funding level is a free
positioning gauge, not a revenue line.

**Testable:** Conditioning use, yes: we already ingest OKX funding
(okx_feed.py:168-201) and feed funding_dir (ml/features.py:384); regress
recorded funding extremes vs forward Kraken spot returns at our holding
horizons, LS-1-style importance verification before promotion. See 06 spec
T12.

---

## funding-cond-1 — funding is a positioning gauge, not an entry signal [C]

**Claim:** Funding rate has essentially NO predictive power for subsequent
BTC price change per Presto Research (zero predictive R² of funding-rate
changes for future price); Fulgur Ventures 2024 alone reports a SLIGHT
negative correlation with subsequent returns (mean-reversion direction,
small effect, not individually fetched this pass; no peer-reviewed effect
size at trade horizons) — while funding LEVELS are strongly predictable one
step ahead (DAR beats no-change on Binance/Bybit BTC, Inan 2025); extreme
readings flag crowded one-sided leverage that unwinds violently.
*(Attribution split 2026-08-27: page previously pooled the slight-negative
finding under "industry backtests" with Presto cited first — Presto's
actual result is a null, and a null instrument must not be quoted as a weak
positive; the slight-negative leg belongs to Fulgur alone.)*

**Citations:** Presto Research, "Can Funding Rate Predict Price Change?",
Aug 2024, prestolabs.io (finding: zero predictive R²); Fulgur Ventures 2024,
"Bitcoin funding rates and price predictability" (sole source of the
slight-negative correlation); Inan 2025, "Predictability of Funding Rates",
SSRN 5576424 (Binance BTC focus).

**Mechanism:** Extreme funding = crowded leveraged side paying to hold; the
crowd is the future forced flow (feeds liq-asym-1). Already treated
defensively: gate_4 blocks entries when |funding| exceeds cap, fail-open only
when the spot venue pays no funding (signal_gates.py:163-179); funding_dir in
the model vector (ml/features.py:384). Missing: the OI interaction — funding
extremes matter conditional on OI buildup, and we have no OI (ATTR-2).

**Testable:** Yes — recorded funding_rate history vs forward spot returns at
1h-24h horizons, effective-n corrected. gate_4 threshold changes are
gate-widening territory: any retune must clear the overfit battery +
quant-trial G3/G5 and is likely COHORT-RESETTING. See 06 spec T12.

---

## funding-structure-1 — funding markets are two-tiered (CEX vs DEX); OKX representative of the CEX tier over a short window [B]

**Claim:** Across 35.7M one-minute observations, 749 symbols, 26 exchanges —
over an EIGHT-DAY panel (span omitted by this page until 2026-08-27) — the
paper's two tiers are CENTRALIZED vs DECENTRALIZED exchanges, with all
information flow CEX->DEX. *(Softened 2026-08-27: page previously claimed
"major-exchange funding dynamics lead and Granger-cause smaller venues'
rates — a single deep-venue funding feed is a defensible proxy for
market-wide positioning state"; that deep-vs-shallow reading is a reframing
of the paper's CEX-vs-DEX result. Supported form: OKX is representative of
the CEX tier over a short validation window; T13's own cross-venue check —
not this cite — carries the representativeness claim.)*

**Citations:** Petar Zhivkov, "The Two-Tiered Structure of Cryptocurrency
Funding Rate Markets", Mathematics (MDPI) 14(2):346, Jan 2026,
doi:10.3390/math14020346 (identifiers and 35.7M/749/26 confirmed
2026-08-27).

**Mechanism:** Arbitrageurs propagate the funding-relevant basis from
centralized venues to decentralized ones with lag; information originates
where leverage concentrates. Partially de-risks our single-source design:
OKX-only funding ingest (okx_feed.py:168-201) sits in the leading CEX tier,
but cross-CEX representativeness rests on T13, not this paper — and
single-venue outage blanks the signal, which gate_4's fail-open converts to
"no funding constraint" (a quiet degrade worth a telemetry counter).

**Testable:** Yes — cross-implementation check: correlate OKX funding
against a second read-only venue's funding via the existing ccxt layer
(data/ccxt_feed.py) for a bounded sample; instrument verification per
the-method before trusting funding-conditioned results. See 06 spec T13.

---

## postcascade-rev-1 — post-cascade reversion at our horizons is UNMEASURED [D]

**Claim:** The narrative that liquidation flash-crashes (10-30% in minutes)
"reverse quickly once forced selling exhausts" has no peer-reviewed
magnitude/half-life estimate net of costs — the one rigorous cascade paper
explicitly does not address recovery — so whether the post-cascade spot
bounce clears our 43-118 bps round-trip bar is an owed measurement, not a
fact.

**Citations:** Bitsgap, "Liquidation Cascades Explained" (narrative,
industry); Garcia Seuma 2026, arXiv:2607.27070 (recovery explicitly not
addressed); "Anatomy of the Oct 10-11 2025 Crypto Liquidation Cascade",
ResearchGate preprint 396645981 (amplification channels, no tradable
reversion estimate).

**Mechanism:** If real: forced sellers exhaust -> overshoot vs fundamental
holders' reservation prices -> patient spot bids capture the rebound — the
exact accumulate-and-hold shape we want, and the only cascade-linked edge our
venue can actually execute (resting limits into the flush, exits via
ProfitTierEngine). If the bounce nets under ~43 bps after 40/80 bps fees, it
is a detection curiosity, not P&L (WHY-1 cost-bound lesson).

**Testable:** Yes, NOW, as a SAFE-class measurement script: extreme
down-range bars in recorded Kraken spot candles (z-scored range + volume),
event-study forward returns 15m/1h/4h/24h, shuffle null (OF-2 pattern),
effective-n on overlapping windows, report vs the 43/118 bps bars. Better
trigger fidelity needs the liquidation feed (ATTR-2). Acting on it =
COHORT-RESETTING, operator-adjudicated. See 06 spec T14.
