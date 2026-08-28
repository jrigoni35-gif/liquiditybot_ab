# Lens 02 — exchange/company profitability mechanics

Who structurally profits from retail crypto trading and through what
plumbing. See README for legend and bars.

---

## gov-fee-1 — spot fee capture is the largest measured structural transfer [C] [FLAGSHIP — STANDS]

**Claim:** Coinbase booked $3.43B in consumer (retail) transaction revenue in
FY2024 vs $1.33B in FY2023, out of $3.99B total transaction revenue —
consumer take rates run 100-250 bps while institutional runs single-digit
bps, so retail pays the overwhelming share per dollar traded.

**Verdict: STANDS** (referee row recorded with placeholder reason — the
verdict stands as filed; no amendment was issued).

**Citations:** Coinbase Global Inc., Form 10-K FY2024, SEC EDGAR, filed Feb
2025 (sec.gov/Archives/edgar/data/1679788/000167978825000022/coin-20241231.htm).
*Footnote (re-referee 2026-08-27, verdict STANDS):* the FY2023 comparator
($1.33B consumer) is Coinbase's *restated* figure per the Q1-2024
reclassification of Base/payment revenue out of Consumer into Other, as shown
in the FY2024 10-K — not the $1.429B originally reported in the FY2023 10-K;
a diff against the original filing is a false discrepancy.

**Mechanism:** Exchange prices convenience: retail defaults to
simple-buy/taker flows at 40-250 bps while institutional/MM tiers approach
zero; a regressive volume tax whose incidence falls on the smallest, most
frequent traders. Exchange profits from retail regardless of retail P&L
direction.

**Testable:** Directly demonstrated on OUR corpus: era-4 readout
(docs/HANDOFF.md WHY-1, n=54) gross +$8.23 vs true fees $13.59 -> net
-$5.36; cost_attribution.py + fill ledger measure exactly this transfer at
the 40/80 bps Kraken tier. The 43-118 bps bar exists because of this claim.
See 06 spec T2.

---

## gov-fee-2 — maker/taker tiering shapes retail into the taker role [B]

**Claim:** Volume-tiered schedules (Kraken 25/40 bps base tier falling toward
~0/10 bps at $10M+ 30-day volume) make the marginal fee for professional
makers near zero while retail pays full taker rate; fee-breakdown theory
shows the maker/taker split is non-neutral when tick sizes bind — a designed
cross-subsidy from small takers to large makers.

**Citations:** Colliard & Foucault, RFS 25(11), 2012, doi:10.1093/rfs/hhs089;
Malinova & Park, Journal of Finance 70(2), 2015, doi:10.1111/jofi.12230;
Kraken fee schedule (kraken.com/features/fee-schedule).

**Mechanism:** Exchange + tiered MMs profit via the taker-fee wedge; MMs
additionally earn the spread against retail marketable orders. Retail cannot
reach maker tiers (volume floors); the schedule converts impatience into fee
revenue. Our OM-011 limit-entry-only invariant is the deployed countermeasure.

**Testable:** Yes — fill-ledger maker/taker flags: realized maker fraction
and fee tier vs counterfactual taker cost at 80 bps in cost_attribution.py
output. See 06 spec T2.

---

## gov-liq-1 — liquidation engines as revenue plumbing [C]

**Claim:** Liquidation fees are skimmed from remaining margin into
exchange-controlled insurance funds — BitMEX's fund grew roughly 62% in 2019
alone (20.77k -> ~33.47-33.49k XBT per contemporaneous reports; page
previously claimed "62.8% (20,700 -> 33,700)" — amended 2026-08-27 to
source-exact figures), stands near $280M (Blockhead's figure alone,
unverified elsewhere); Binance's support FAQ "Introduction to Futures
Insurance Funds" states funds above a required minimum "may be deployed by
Binance for other purposes as it considers appropriate in its sole
discretion" *(quote re-attributed 2026-08-27: previously credited to the
Blog Part 2 post)*.

**Citations:** BitMEX "Insurance Fund Changes / Trader Protection"; Binance
Blog "Liquidation & Insurance Funds" Part 2; Binance support FAQ
"Introduction to Futures Insurance Funds" (source of the sole-discretion
quote); Blockhead "Liquidation Alchemy Part 2", Dec 2025.

**Mechanism:** Venue profits from the leveraged loser twice: taker fees on
the forced close plus the liquidation-fee residual swept into a
venue-controlled fund. Persistent fund growth is CONSISTENT WITH the engine
over-collecting relative to socialized losses, but is not direct evidence of
it — 2019 growth also reflects that year's volatility regime and the venue's
parameter choices *(softened 2026-08-27; page previously called growth
"direct evidence" of over-collection)*.

**Testable:** Not with current data (ATTR-2). BitMEX publishes daily fund
balances — ingestable as read-only context without touching decisioning. See
06 OWED DATA.

---

## gov-liq-2 — cascades are the largest episodic forced transfer [C] [FLAGSHIP]

**Claim:** 2025 totaled >$150B in liquidations (CoinGlass; daily average
$400-500M); the 2025-10-10 event alone printed $19B in 24h reported — with
credible analysis putting the true figure at $30-40B because exchange APIs
throttle liquidation reporting — the largest single-day forced flush in
sector history.

**Citations:** CoinGlass 2025 annual liquidation report via Bitcoinist;
Blockscope Research, "The Crypto Apocalypse of October 10", Oct 2025;
insights4vc, "Inside the $19B Flash Crash", 2025.

**Mechanism:** Leveraged retail longs are the standing fuel; the transfer
flows to liquidation engines (fees), insurance funds, and patient/short
counterparties absorbing forced flow at cascade prices — the exact
forced-flow cohort who-loses-to-us names as our monetizable counterparty, and
the bridge-hypothesis endpoint (bot-amplified narrative -> retail leverage ->
cascade).

**Testable:** Not with current data — ATTR-2 (docs/HANDOFF.md): no
liquidation/OI feed exists in the bot; CoinGlass-class OI + liquidation
ingestion is the named missing feed. Sizing caveat: even anticipating a
cascade, our harvest must clear 43-118 bps round-trip on Kraken spot. See 06
OWED DATA + T14.

---

## gov-fund-1 — perp funding is a structural long-bias tax [B mechanics / C magnitude]

**Claim:** The funding mechanism makes longs pay shorts proportional to the
perp-spot gap (peer-reviewed no-arbitrage treatment); empirically Binance BTC
funding averaged roughly 14% annualized over six years against ~3% T-bills —
an ~11%/yr wedge extracted from the retail-dominated long side, harvested by
cash-and-carry desks and market makers.

**Citations:** He, Manela, Ross, von Wachter, "Fundamentals of Perpetual
Futures", 2024 Utah Winter Finance Conference / SSRN 4301150,
arXiv:2212.06888; Elm Wealth, "Perpetual Futures: Mechanics, History and
Purpose" (14% vs 3% figure).

**Mechanism:** Retail expresses leveraged directional optimism; funding
transfers a continuous premium to the delta-neutral short. A tax on impatient
conviction flowing to patient capital by construction.

**Testable:** Not directly (no funding P&L for us — spot only). Funding
rates are freely available; a persistent-positive-funding regime flag would
proxy crowded retail longs upstream of cascades. Partially covered by
existing OKX funding ingest — see lens 04 funding claims and 06 spec T12.

---

## gov-pfof-1 — crypto PFOF analogue: retail flow purchased wholesale [C]

**Claim:** Robinhood routes crypto orders to market makers and receives
"transaction rebates" set as a fixed percentage of notional order value (per
its 10-K) — the internalizing MM prices retail flow profitably enough to pay
for it, the classic sign retail flow is uninformed and systematically
monetizable.

**Citations:** Robinhood Markets Inc., Form 10-K FY2024, SEC EDGAR;
Robinhood crypto order routing disclosure; SEC DERA working paper, "How Does
Payment for Order Flow Influence Markets?", 2025.

**Mechanism:** Broker sells segmented retail flow; MM pays because segregated
retail flow carries near-zero adverse selection and wide effective spread.
Retail pays via spread markup, not a visible fee line. Confirms
who-loses-to-us: uninformed flow is priced and purchased wholesale.

**Testable:** Not with current data. Indirect corollary on OUR feeds:
internalized retail flow never reaches lit books, so Binance.US/Kraken depth
UNDERSTATES true retail imbalance — a scope caveat for imbalance features in
regime/liquidity_regime.py, not a tradeable claim.

---

## gov-mm-1 — exchange-affiliated MM conflict, at its adjudicated extreme [C]

**Claim:** SDNY trial testimony (Gary Wang) and the CFTC complaint establish
Alameda held a $65B line of credit, permission for negative balances, and a
coded exemption from FTX's auto-liquidation engine — privileges no retail
counterparty had, funded by $8B of customer deposits withdrawn by bankruptcy.

**Citations:** CFTC v. Bankman-Fried/FTX/Alameda, complaint 2022-12-13; SEC
Litigation Release LR-25616; US v. Bankman-Fried, SDNY testimony of Gary
Wang, Oct 2023 (Malay Mail/Reuters). Court records — grade C (adjudicated
fact, not peer-reviewed study).

**Mechanism:** When the venue owns the MM, retail trades against a
counterparty exempt from the rules that force retail out: the house cannot be
liquidated but the customer can, and the house sees the flow.

**Testable:** Partial — venue-favoritism footprints (an MM that never gets
liquidated / reprices with impunity) are what THALES TH-011 (metronome MM)
and TH-017 shadow-detect on Kraken/OKX/Binance.US books. Caveat: TH-017's
documented identifiability failure (honest maker and layerer both 0.949,
vault entities/thales-engine.md).

---

## gov-wash-1 — fake volume is core plumbing [B]

**Claim:** Wash trading averages over 70% of reported volume on unregulated
exchanges (n=29 exchanges; regulated exchanges show statistically normal
trade-size and first-significant-digit distributions, unregulated do not),
improving venue rankings and directly moving prices.

**Citations:** Cong, Li, Tang, Yang, "Crypto Wash Trading", Management
Science 69(11):6427-6454, 2023, doi:10.1287/mnsc.2021.02709; NBER WP w30783.

**Mechanism:** Exchange manufactures the appearance of liquidity: inflated
volume buys ranking placement, attracts listing-fee-paying issuers and real
retail flow, which then pays real fees and trades against
worse-than-advertised books. Retail pays through slippage on liquidity that
does not exist.

**Testable:** Yes, on OUR corpus: apply the paper's instruments (Benford
first-digit, trade-size clustering/roundness, power-law tail exponent) to
read-only OKX and Binance.US trade prints vs Kraken as the regulated
baseline. Pure measurement, SAFE class. See 06 spec T3.

---

## gov-list-1 — listing economics tax issuers and late retail simultaneously [C]

**Claim:** Tier-1 listing fees run $500K-$2.5M (industry-disclosed ranges);
a working-paper event study (page previously called it "peer-reviewed" —
amended 2026-08-27) of 327 listings across 22 exchanges finds +5.7% abnormal
return on listing day (+9.2% over -3/+3 window); industry tracking finds 98%
of Binance-listed tokens subsequently trade below the post-listing pump (not
verified in the 2026-08-27 pass).

**Citations:** Lennart Ante, "Market Reaction to Exchange Listings of
Cryptocurrencies", 2019, SSRN 3450301 / Blockchain Research Lab working
paper (327 listings/180 tokens/22 exchanges; also ResearchGate 335690724) —
327/180/22, +5.7% day-0, +9.2% [-3,+3] confirmed verbatim 2026-08-27;
Coin360 listing-fee overview; CryptoNinjas/Storible via BitPinas (98% dump
figure, unverified). Composite grade C: abnormal-return core downgraded
B -> C-pending-publication-check 2026-08-27 (journal publication not
confirmed; it is an SSRN/BRL working paper), fee and dump figures
industry-sourced.

**Mechanism:** Exchange collects the fee from the issuer; issuer recoups via
the listing pump; exit liquidity is attention-recruited retail buying the
announcement — the emotional-flow cohort who-loses-to-us classifies as
monetizable.

**Testable:** In principle on OUR corpus: event study on Kraken listing
announcements vs stored candles for newly-listed pairs (SUI/ARB/MINA/FLOW
added with Kraken candle history). Tag: a 5.7% day-0 move could clear the
43-118 bps bar, but our entry is resting-limit-only — chasing a listing pump
is taker behavior the invariants forbid. See 06 spec T4.

---

## gov-retail-1 — the retail loss base is measured, not inferred [C]

**Claim:** Across 95 countries 2015-2022, an estimated 73-81% of crypto-app
retail users lost money on their bitcoin purchases (median investor down ~48%
of invested funds), with blockchain data showing the largest holders selling
into the retail inflows that rising prices recruit.

**Citations:** Auer, Cornelli, Doerr, Frost, Gambacorta, BIS WP 1049, Nov
2022 (bis.org/publ/work1049.pdf); SSRN 4357559.

**Mechanism:** Price rises recruit new retail (feedback trading,
disproportionately young/male); whales distribute into recruited demand. The
empirical backbone of the vault's "replenished, not educated" durability
claim — the loser pool refills each cycle at scale, which is why the
counterparty taxonomy is stable enough to build gates on.

**Testable:** Not with current data (no adoption/app-download feed; out of
scope). Cited as the population-level base rate funding every other channel
in this lens; extends vault concepts/who-loses-to-us.
