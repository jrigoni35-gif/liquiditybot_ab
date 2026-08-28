# Lens 03 — why retail loses beyond the risk-management cliché

Behavioral-finance mechanisms, graded, mapped to liquiditybot prior art. See
README for legend and bars.

---

## retail-adverse-selection-1 — order aggressiveness as the loss channel [A Taiwan / B-D transfer] [FLAGSHIP — AMENDED]

**Original claim:** Virtually all aggregate individual-investor trading
losses trace to AGGRESSIVE (marketable) orders — a 3.8 pp annual portfolio
penalty equal to 2.2% of Taiwan's GDP — while retail PASSIVE limit orders are
profitable at short horizons; the loss channel is order type, not stock
picking.

**Verdict: AMENDED.** Core Taiwan numbers verified verbatim (Barber, Lee, Liu
& Odean, RFS 22(2):609-632, 2009, doi:10.1093/rfs/hhn046): 3.8 pp penalty,
losses = 2.2% of GDP / 2.8% of personal income, institutions +1.5 pp. Three
defects:

1. **CONFLATION.** The paper's own decomposition splits the headline loss:
   gross trading losses 27% (NT$249B), commissions 32% (NT$302B), transaction
   taxes 34% (NT$319B), market-timing 7% (NT$65B). "Virtually all traced to
   aggressive orders" applies to the PRICE-loss component only — ~66% of the
   headline is fees/taxes NO counterparty (including a maker bot) can
   harvest. **The harvestable adverse-selection pool is ~27% of the headline.**
2. **OMISSION.** Passive orders are "profitable at short horizons and suffer
   modest losses at longer horizons"; losses/gains asymptote at ~6 months.
3. **SCOPE.** Taiwan 1995-1999, order-driven, no designated MMs, 0.1425%
   capped commissions, 0.3% transaction tax. The order-type law does NOT
   generalize: Kelley & Tetlock (JF 68(3):1229-1265, 2013, doi:10.1111/jofi.12028,
   US 2003-2007) find retail AGGRESSIVE orders positively predict returns up
   to 20 days; Boehmer, Jones, Zhang & Zhang (JF 76(5):2249-2305, 2021,
   doi:10.1111/jofi.13033, US 2010-2015) find marketable retail imbalance
   predicts +~10 bps next week (predictability roughly halved, gone in
   large-caps 2016-2021 per Ardia, Aymard & Cenesizoglu, "Revisiting
   Boehmer et al. (2021)", arXiv:2403.17095 — weakened, not sign-flipped;
   attribution corrected 2026-08-27: page previously credited "Barardehi
   et al.", who authored related retail-order-imbalance work (SSRN 3966059)
   but not this paper). Linnainmaa (JF 65(4):1473-1506, 2010,
   doi:10.1111/j.1540-6261.2010.01576.x, Finland): retail LIMIT orders suffer
   mechanical adverse selection — passive is not automatically the winning
   side; monitoring/repricing is load-bearing (the bot reprices; a stale
   resting order is the picked-off side).

**Amended grade:** A for the Taiwan-specific numbers; B/D for any transfer of
the order-type law to 2026 crypto spot. Model the harvestable share as ~27%
of any BLLO-style headline, against the 43-118 bps bar.

**Mechanism:** Retail crosses the spread on impulse/attention timing; the
resting maker sells the fill at a price already adverse. OM-011
limit-entry-only puts us structurally on the receiving side — but at Kraken
true 40/80 bps the HFT maker-rebate economics do not exist for us, so the
harvest must clear 43-118 bps.

**Testable:** Yes — era-4 fill-ledger decomposition (core/fill_ledger.py):
trips by whether our resting order was hit during an attention/volatility
spike vs quiet tape; short-horizon post-fill drift. n=54 closed is thin but
sign is checkable now. This is the owed measurement the verdict names. See
06 spec T1.

---

## retail-base-rate-2 — full-population day-trader loss base rates [A]

**Claim:** 97% of Brazilian equity-futures day traders who persisted >300
days lost money (all entrants 2013-2015; only 0.4% earned more than a bank
teller); <1% of the Taiwan day-trader population (1992-2006) predictably
earned positive abnormal returns net of fees.

**Citations:** Chague, De-Losso & Giovannetti, "Day Trading for a Living?",
SSRN 3423101, 2020; Barber, Lee, Liu & Odean, J. Financial Markets 18:1-24,
2014, doi:10.1016/j.finmar.2013.05.006.

**Mechanism:** Two independent full-population (not survivor-sampled)
datasets converge: the retail short-horizon pool is net-negative after fees
at 97-99% incidence. The 1-3% who win (top-500 Taiwan: +37.9 bps/day after
fees) win FROM the rest — we compete with that skilled 1% for the same flow,
not with the 97%.

**Testable:** Base rate not testable on our corpus (no counterparty
accounts); its implication — resting flow hit by systematically-losing
takers — is T1. Per-counterparty attribution: never available to us.

---

## retail-crypto-lossrate-3 — crypto loss incidence via entry timing [B]

**Claim:** Across 95 countries Aug 2015-Dec 2022, a majority of crypto
trading-app users in nearly all economies lost money on bitcoin; BIS
back-of-envelope puts it at roughly three-quarters of users, because app
downloads (retail entry) concentrate after price run-ups.

**Citations:** Auer, Cornelli, Doerr, Frost & Gambacorta, BIS WP 1049, 2022
(rev. 2023); published IMF Economic Review 2025, doi:10.1057/s41308-025-00275-0;
BIS Bulletin 69, 2023. The 75% figure is the authors' own back-of-envelope —
hence B not A.

**Mechanism:** Entry timing is the loss mechanism: adoption is price-chasing
(downloads spike after rallies), so the median cost basis sits near local
highs. Crypto instantiation of the attention channel at the extensive margin
— the peer-reviewed base under "replenished, not educated"
(who-loses-to-us.md).

**Testable:** Proxy on our feeds: correlate Kraken/Binance.US volume and
candidate-flow density with trailing return sign — price-chasing flow makes
taker volume a lagging function of returns. Feasible on existing OHLC + book
snapshots in outputs/. See 06 spec T5.

---

## retail-learning-failure-4 — losing does not shrink the pool's volume [B] [FLAGSHIP — AMENDED]

**Original claim:** 74% of Taiwan day-trading volume is generated by traders
with a HISTORY of losses, 97% of continuing day traders are expected to lose
going forward, traders with up to 10-year negative track records keep
trading; attrition (80% quit within 2 years) removes accounts but volume is
continuously re-supplied.

**Verdict: AMENDED — direction survives every refutation attempt; the
amendment is number provenance.** The 74%/97% do NOT appear in the cited 2017
working paper (which prints 72% of volume from unprofitable traders, "nearly
3/4ths", ~80% of volume in late-sample years, ">75% of all day traders quit
within two years", "<3% predictably profitable / 9.81% of volume"). Both
numbers ARE verbatim in the published version, which is the correct citation:
**Barber, Lee, Liu, Odean & Zhang, "Learning, Fast or Slow", Review of Asset
Pricing Studies 10(1):61-93, 2020**: "74% of day trading volume is generated
by traders with a history of losses; and 97% of day traders are likely to
lose money in future day trading" (3.7B TSE transactions, 1992-2006). State
attrition as "more than 75% quit within two years" (the 80% figure is the
late-sample loss-history VOLUME share; secondary summaries conflate them).
Additional confirmations: 10-year-negative persistence; previously
unprofitable experienced traders re-trade within 12 months at nearly the
profitable traders' 96.4% rate. Failed refutations: (a) Seru, Shumway &
Stoffman (RFS 23(2):705-739, 2010, doi:10.1093/rfs/hhp060) — learning is
dominantly by attrition, supporting "accounts leave, volume re-supplied"
(soften "unteachable" to "barely-improving"); (b) regime staleness —
Chague et al. (Brazil 2013-2015, modern low-fee electronic market): 97% of
1,551 individuals persisting >300 days lost net of fees, only 1.1% above
minimum wage, no learning through experience — independent derivation
landing on the same 97% (working paper: corroboration at C/B-, claim stays
B). Taiwan day trading was a stable ~20% of total volume 1995-2006.
**Unestablished: stationarity of the re-supply in 2026 crypto (grade D) —
exactly the claim's own THALES/era-boundary stability test, still owed.**

**Mechanism:** Biased self-attribution (Gervais & Odean, RFS 14(1):1-27,
2001, doi:10.1093/rfs/14.1.1) blocks the Bayesian update that would end the
trading; counterparty supply is a renewable resource. Load-bearing assumption
behind any patient-capital strategy: the edge does not educate itself away.
Peer-reviewed base of who-loses-to-us "replenished, not educated" — cited,
not re-derived.

**Testable:** Partial — stationarity proxy: adverse-selection markers on our
fills (T1 decomposition) and THALES lazy-bot footprint rates stable across
era boundaries rather than decaying. Account-level learning curves: never
available. See 06 spec T19.

---

## retail-lottery-skew-5 — lottery preference priced, sign disputed [B]

**Claim:** The high-minus-low MAX-decile spread in cryptocurrencies is +3.03%
raw / +1.99% risk-adjusted PER WEEK (positive premium, contra the negative
equity MAX premium of Bali-Cakici-Whitelaw), while intraday evidence finds
the equity-style overvaluation sign (1-sd MAX increase -> -0.043% subsequent
return).

**Citations:** Ozdamar, Akdeniz & Sensoy, "Lottery-like preferences and the
MAX effect in the cryptocurrency market", Financial Innovation 7:67, 2021,
doi:10.1186/s40854-021-00291-9 *(attribution corrected 2026-08-27: page
previously credited Grobys & Junttila, who wrote a different 2021 paper,
"Speculation and lottery-like demand in cryptocurrency markets", JIFMIM;
the +3.03% raw / +1.99% risk-adjusted weekly HML-MAX numbers are verbatim
correct for Ozdamar et al.)*; "Intraday lottery demands in cryptocurrency
market", ScienceDirect 2025 (S1086737625000172).

**Mechanism:** Retail pays up for right-tail payoffs; whoever is short the
spike-chasing flow collects the skew premium. The SIGN DISPUTE between weekly
and intraday studies means the harvest window is frequency-dependent and
unsettled — no sizing on this without our own measurement. Cost tag: the
intraday effect is 4.3 bps/sd — far below the 43-118 bps bar, NOT
monetizable; the weekly effect would clear it if real, but is
momentum-confounded.

**Testable:** Yes — computable on existing multi-asset Kraken candle history
(SUI/ARB/MINA/FLOW + majors): rank universe by trailing-month MAX, check
next-week return spread. Single-digit cross-section = low power; report
effective n per gate_truth_report standard. See 06 spec T6.

---

## retail-leverage-drain-6 — leverage damage quadratic, edge linear [A]

**Claim:** Geometric growth at leverage L is g(L) = L*mu - L^2*sigma^2/2, so
at BTC-like daily sigma=4%, 10x leverage costs 0.5*(0.40)^2 = 8.0%/day in
volatility drag against 10x of any edge; the one clean natural experiment
(2010 CFTC retail-FX cap to 50:1) reduced high-leverage traders' losses by
40% and volume by 23% without harming liquidity.

**Citations:** Heimer & Simsek, JFE 132(3):1-21, 2019,
doi:10.1016/j.jfineco.2018.10.017; volatility-drag identity g = mu -
sigma^2/2 standard (Booth & Fama, "Diversification Returns and Asset
Contributions", FAJ 48(3):26-32, 1992 — cite verified 2026-08-27 but loose:
the paper is about diversification return and uses rather than states the
identity per se; the identity itself is textbook-standard).

**Mechanism:** Leveraged retail converts variance into wealth transfer twice:
(a) L^2 drag compounds against them; (b) forced liquidation converts
drawdowns into guaranteed market-order sales at the worst tick — the
forced-flow supply who-loses-to-us taxonomizes and patient resting capital
receives. We hold no margin (spot-only); strictly a model of OTHER
participants whose liquidation points cluster predictably.

**Testable:** The arithmetic is an identity. The cascade-timing implication
is NOT testable with current data — ATTR-2: no liquidation/OI feed; OKX OI
ingestion is the owed instrument. See 06 OWED DATA.

---

## retail-attention-buying-7 — attention buying with partial reversal [B]

**Claim:** Coins with abnormal Google search volume show higher subsequent
returns, volatility, and volume (price-pressure hypothesis — verified from
the abstract 2026-08-27). The reversal-share leg is DEMOTED to an owed
full-text check (2026-08-27): the page previously asserted "PARTIAL (not
full) reversal — late attention-recruited buyers systematically overpay, but
less of the move round-trips than the equity Barber-Odean lineage predicts"
as the paper's finding, but only attention -> higher subsequent
returns/volatility/volume was verifiable from the accessible abstract
(publisher page 403). The reversal leg is load-bearing for the
fading-attention-indiscriminately-is-negative-EV gate-shape argument and may
not carry weight until the full text is checked.

**Citations:** Hoang & Vo, "Google search and cross-section of cryptocurrency
returns and trading activities", J. Behavioral and Experimental Finance,
Vol 44, Dec 2024, doi:10.1016/j.jbef.2024.100991 *(DOI corrected 2026-08-27:
page previously cited 10.1016/j.jbef.2024.100966, which is a different JBEF
article on green bonds, Vol 43)*; Barber & Odean, RFS 21(2):785-818, 2008,
doi:10.1093/rfs/hhm079 (lineage); Stella, Ferrara & De Domenico, PNAS
115(49):12435-12440, 2018, doi:10.1073/pnas.1803470115 (bots as
attention-channel amplifiers — bridge hypothesis, upstream of the buying).

**Mechanism:** Attention is the recruitment channel: bots (23.6% of posts,
PNAS) can inflate it cheaply; retail buys what it sees; IF the reversal leg
survives the owed full-text check, partial reversal transfers the
overpayment to whoever was resting on the offer. Honest caveat:
some attention moves are informed — fading attention indiscriminately is
negative-EV; the vault admission rule (priced adverse selection + THALES,
never confidence) is the correct gate shape.

**Testable:** Not with current data — ATTR-1: sentiment feed read 0.002-flat
through the 2026-08-20 policy melt-up; the attention instrument is the
missing feed. Owed: search-volume or social-velocity feed validated against
known attention events before any gate consumes it. See 06 OWED DATA.

---

## retail-geometric-vs-psych-8 — disposition signatures are geometric [C]

**Claim:** A fully mechanical system with near take-profit and far stop
reproduced the retail profile (58.3% win rate, 0.670 payoff ratio, 2.20x
disposition effect) with zero emotion machinery — disposition-shaped losses
survive even for emotionless bots; psychological remedies mis-target the
cause.

**Citations:** vault wiki/concepts/behavioral-isomorphism.md (isomorphism
proof 2026-08-09, sources/session-20260809-turing-test-hedge-verdict) —
internal controlled measurement, hence C; Ben-David & Hirshleifer, RFS
25(8):2485-2532, 2012, doi:10.1093/rfs/hhs077 (independent peer-reviewed
support: selling patterns fit belief-driven speculation, not preference for
realizing gains per se).

**Mechanism:** Winners resolve to the closer boundary sooner; losers must
travel further — arithmetic alone manufactures
sell-winners-early/hold-losers-long. For us: detected loser cohorts include
lazy-configured bots (THALES TH-010/011/012 targets) whose geometry, not
psychology, makes them exploitable — detectable without inferring mind.
Symmetry warning: our own exit inversion (ratchet winners, protocol-stop
losers) is why WHY-1 shows exit geometry held while fees, not exits, bound
the era-4 verdict.

**Testable:** Yes — already run once (2026-08-09 hedge verdict); re-runnable
via the replay-A/B harness on the current era-4 recording to confirm the
mechanical disposition ratio is stable under cut-#7 geometry. See 06 spec T7.

---

## retail-crypto-disposition-9 — disposition effect is regime-contingent [B]

**Claim:** Bitcoin on-chain flows show the classic disposition effect
intensifying from the 2017 boom-bust onward, while exchange-level evidence
finds a REVERSE disposition effect in bullish periods (hold winners too long)
and the classic effect in bearish periods.

**Citations:** Schatzmann et al., "Exploring investor behavior in Bitcoin: a
study of the disposition effect", Digital Finance, 2023,
doi:10.1007/s42521-023-00086-w; Haryanto, Subroto & Ulpah, J. Industrial and
Business Economics 47:115-132, 2020, doi:10.1007/s40812-019-00130-0.

**Mechanism:** Regime-flipped disposition moves the harvestable object: in
bear regimes held losers accumulate as stale inventory that eventually
capitulates (forced-flow supply at magnets — who-loses-to-us
disposition-effect-holders cohort); in bull regimes over-held winners produce
the late give-back our ratchet exists to avoid. Cost tag: capitulation-point
harvesting is cascade-adjacent and needs ATTR-2 to time — a detection
target, not a trade, until then.

**Testable:** Partial — regime-conditioned analysis of price-magnet touch
behavior computable from existing book snapshots + candles; on-chain version
not with current data (no on-chain feed). See 06 spec T8.
