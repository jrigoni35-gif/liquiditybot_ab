# FLOW/USD position — independent sweep (2026-09-04)

Second pass over the operator's Kraken FLOW/USD margin position, run
against **primary sources only** after the prior session's handoff was
explicitly flagged "don't trust at face value". Scope: measurement.
No order path touched — **SAFE** under the era-6 moratorium.

Instrument: `monitor/pass2.py` (live Kraken public endpoints).
Position figures: the operator's account screen, not repo state.
Per the standing correction, **no liquiditybot number is cited here.**

## Position as read

90,334.862054 FLOW @ $0.02793 avg, 3x. Used margin $840.88, equity
$778.99 quoted @ $0.02723, carry $3.78/day. Margin state 92.6%.

Notional $2,523.05; /3 = $841.02 vs the reported $840.88 — a $0.14
rounding gap. Internally consistent.

Minor: the brief's "P&L ~-$52" corresponds to px $0.02735, while the
equity is quoted at $0.02723 (P&L -$63.23). Two different timestamps.
At the live mid $0.02750 the position is **-$38.84**.

## Handoff claims, checked

| Claim | Verdict | Source |
|---|---|---|
| Tick $0.0001 = 36 bps, the spread floor | **confirmed** — 36.4 bps at $0.0275 mid; book is 2 ticks / 72.7 bps wide | `AssetPairs.tick_size` |
| Maker 0.20 / taker 0.35, NOT the repo's 22/38 | **confirmed, and stronger** — "22/38" is not a row in Kraken's FLOWUSD schedule at all (rows: 0.25/0.40 → 0.20/0.35 → 0.14/0.24 → 0.12/0.22). At $17,482/30d the $10k row binds. | `AssetPairs.fees{,_maker}` |
| Fitted −119%/yr drift is a dead regime; use driftless | **confirmed** — full-sample −152.5%/yr, 365d −266.9%/yr, but 90d **+22.7%/yr**. Driftless is if anything generous to the bear side. | 721 Kraken daily bars |
| "90d −10%/yr, 30d +18%/yr" | **wrong in sign** — point-to-point is 90d **+22.7%/yr**, 30d **+63.3%/yr** (close $0.02760 now vs $0.02610 / $0.02620). Conclusion survives; the numbers do not. | same |
| Fat tails regime-contaminated (kurt 6.66 old vs −0.26 recent) | **confirmed** — 365d ex-kurt **+6.69**, 30d **−0.45**. Current regime is near-Gaussian *and* lower-vol: 90d **3.31%/d** vs full-sample **4.85%/d**. | same |
| Biconomy ~69% of reported spot, wash; genuine ~$320k/day | **confirmed** — Biconomy FLOW/USDC **71.8%** ($1,274,642), `trust_score: no_data`. High-trust venues sum to **$359,983/day**. Kraken FLOW/USD is **3.9%** of the real tape. | CoinPaprika `getCoinMarkets` |
| Binance FLOWUSDT max lev 10x, MMR 5% | **BLOCKED, still unverified** — `fapi.binance.com` and `api.binance.com` return **HTTP 451** (geo-restricted) from this box; the `data-api.binance.vision` spot mirror answers but carries no leverage/MMR data; the trading-rules page renders its table client-side and fetches as "No Data". Not confirmed, not refuted. | attempted 2026-09-04 |
| No on-chain forced sellers $0.0240–$0.0290; ankrFLOW/More Markets paused | **CONFIRMED on-chain** — **9/9** More Markets reserves read `PAUSED`; ankrFLOW `paused()` = true. See below. | Flow EVM RPC |

One row is BLOCKED, not clean. Recording the distinction because
"0 findings" and "the scan never ran" are the same observation until
separated. The Binance claim is carried forward as **unknown** — it is
not load-bearing for the Kraken position, but it must not be quoted as
verified until an endpoint answers.

## Finding 0 — the chain contradicts the press, and the chain wins

Secondary coverage of the 2026-08-31 ankrFLOW exploit states that **"no
operational pause was announced"**. Read directly on Flow EVM
(`monitor/chain_check.py`), on a pool whose `ADDRESSES_PROVIDER()`
matches the published deployment:

    WFLOW  ankrFLOWEVM  USDC.e  cbBTC  USDF  stgUSDC  WETH  WBTC  PYUSD0
    -> 9/9 reserves PAUSED ;  ankrFLOW token paused() = true

Announced and enforced are different claims and only the second binds.
The mechanism is what matters: in Aave V3 the reserve PAUSED flag
(config bit 60) gates `liquidationCall` alongside supply/borrow/repay/
withdraw. **No forced seller can execute at ANY price while the pause
holds** — so the "no forced sellers between $0.0240 and $0.0290" claim
is structural, not a statement about where liquidation prices sit. It
also means the claim's failure mode is a single state change, not a
price move: re-run the check before relying on it.

Separately, the press's **$9.3M** exploit figure is corroborated as
wrong by a headline in the same result set reading "**drains $410K**",
consistent with the reconstructed ~$412k face value.

## Finding 1 — the margin call is a slope, not a level

The barrier everyone has been quoting as "$0.0261, 4.6% below spot" is a
**day-zero snapshot of a barrier moving toward the position.** Used margin
is pinned at open while rollover is debited from equity every 4h, so:

    call(t) = $0.0260534 + $0.0000418/day · t        (0.42 tick/day)

    day  0   $0.02605   -5.26% vs mid
    day 14   $0.02664   -3.13%
    day 31   $0.02735   -0.54%   <- through the live bid ($0.02740)
    day 60   $0.02856   +3.87%   <- above spot

Cushion above the call is **$106.29**. At $3.78/day that is a
**28.1-day runway at a perfectly flat price.** The position has a hard
expiry independent of price.

The operator's own $3.78/day is what proves it, and it implies
**0.0250%/4h**, not the 0.02%/4h a generic Kraken assumption gives
($3.03/day). The account figure is the primary source and is used as
given; the rate discrepancy is flagged, not resolved.

## Finding 2 — the bid wall stepped down and thinned

Against the published artifact (2026-09-03), read live:

| | artifact | live |
|---|---|---|
| bid wall | $0.0274, $54,776 | **$0.0269, $36,662** (+$6,790 @ .0268) |
| depth spot→call | $80,861 | **$49,535** |

The wall did not hold — it **repriced 1.8% lower and shrank ~33%** inside
24h, and near-book depth is down ~38%. 51 resting bids against 500 asks.

$49,535 to walk price to the call is 3.6 days of Kraken volume, which
reads protective and **is not**: Kraken is 3.9% of genuine spot. The book
is arbitraged to wherever the other 96% goes; the wall is one mobile
order that has already moved once on tape. Do not read it as a floor.

## Finding 3 — barrier probabilities, corrected

Driftless, 90d vol 3.31%/d, 31d to Oct 5, **continuous monitoring**
(Kraken evaluates margin against last trade, not daily closes — a
daily-step sim understates touches by ~5pp: 78.4% → 83.2%).

    HOLD ALL   P(margin call)            83.2%     median day 3.8
               P(touch 0.0300)           59.0%   ... before the call  34.6%
               P(touch 0.0330)           28.2%   ... before the call  17.6%
               P(touch 0.0400)            3.2%   ... before the call   2.6%
    SELL HALF  P(margin call)             2.4%

    running-max: p50 0.03073  p75 0.03344  p90 0.03655  p99 0.04340

Robustness: 30d vol → 84%; t(4) tails → 82%; full-sample vol → 87%;
365d block bootstrap → 94%. The call is the base case in every variant.

## The open decision

Sell 45,167 units, then rest 18,067 @ 0.0300 / 18,067 @ 0.0330 /
9,033 @ 0.0400.

**The arithmetic checks.** Selling half at the bid realises -$28.27
(incl. $4.33 taker), halves used margin to $420.44 and carry to
$1.89/day, and moves the call **$0.02605 → $0.01736** — matching the
handoff's $0.0174. Runway 28 days → **236 days**.

**Expected value does not move.** All variants sit near **-$80** over the
horizon: that is sunk unrealised (-$38.84) + carry + exit fees, and no
resizing changes it under driftless. Anyone claiming a reshaping of this
position *makes* money is selling something.

| | P(call) | E[P&L] | p50 | p90 |
|---|---|---|---|---|
| hold all | 83.1% | -$78.88 | -$177.64 | +$266.78 |
| hold all + ladder | 83.1% | -$82.19 | -$177.62 | +$212.74 |
| sell half + ladder | 3.7% | -$80.33 | -$54.10 | +$125.59 |

What changes is **shape**, and two things about it are decision-relevant:

1. **Holding all is a tight stop you hit 83% of the time.** The call at
   80% is not liquidation (that is 40%), but treating it as the exit makes
   the hold a stop-loss at -$178 that fires on a median day 3.8. The
   median outcome of holding is being stopped out, not being right.
2. **Selling half nearly doubles the chance the ladder ever fires.** With
   the full position, P(touch 0.0300 *before* the call) is 34.6%. Clear
   the call out of the way and it is 59.0%. The strongest argument for the
   plan is mechanical, not statistical: it is what lets the plan execute.

**Two amendments.**

- **The $0.0400 rung is dead.** 3.2% touch probability — 9,033 units that
  will almost certainly be unsold on Oct 5. The running max is p50
  $0.03073 / p90 $0.03655; the ladder should sit where the mass is.
  Moving that rung to ~$0.0360 (11.9%) roughly quadruples its fill odds.
- **Adding $785.65 of collateral achieves the identical call price
  ($0.01736) while selling nothing** — same downside protection, full
  upside retained. It does *not* fix the clock: carry stays $3.78/day, so
  runway is 236 days either way. This is the variant to prefer if the
  upside case is believed; selling half is the variant to prefer if the
  cash is wanted out.

## Reproduce

    python monitor/pass2.py          # live venue truth + the carry clock
    python -m pytest tests/test_monitor_pass2.py -q
