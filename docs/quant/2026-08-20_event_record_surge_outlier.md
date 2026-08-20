# EVENT RECORD — 2026-08-20 majors surge: OUTLIER (operator-adjudicated)

*Operator directive 2026-08-20: label the surge as an outlier; determine
whether the system can attribute WHY it happened — from its own inputs,
not from this one instance.*

## The event

BTC +10.5%/24h (peak ~+11% in ~3h), ETH +17.5-18.4%/24h (peak ~+20%),
volume 3-4x, alt basket +10%. Window: ~2026-08-20 03:00-09:00Z (the 6h
deltas had collapsed to +3%/+0.7% by 12:20Z - the spike crested before
noon). Bot behavior during: flat book, zero entries (crisis-regime +
elevated-vol gates), 1,132 probe/candidate decisions logged.

## External attribution (verified press, 2026-08-20)

1. **Macro liquidity**: U.S. Treasury doubled its single long-end bond
   buyback limit to $4B.
2. **Policy**: White House meeting with crypto/prediction-market
   executives (08-19); push for the CLARITY Act.
3. **Mechanical amplifier**: ~$1.44B forced short liquidations.
4. **Flows**: ~$487M two-day spot-ETF inflows.

## Can the bot attribute it? (the capability audit)

| Sensor | Caught? | What it read |
|---|---|---|
| haven / regime engine | MAGNITUDE only | ETH +18.3 / BTC +11.3, crisis, vol 89th pct — the WHAT, flawlessly; never the WHY |
| moomoo equity basket | CONCURRENT | +8.18% (COIN/MSTR/QQQ), opt_pcr_z 1.19 — confirmed risk-on in the correlated market, no lead |
| webdata fear&greed / dominance | LAGGING | 62 (greed), small dominance delta |
| context feed (calendar/stress/flows) | **MISSED** | in_event_window=false — its calendar knows SCHEDULED events (CME, FOMC); a surprise Treasury buyback change and a White House meeting are not in any series it polls |
| sentiment (news/figures/crowd) | **MISSED — the damning one** | score 0.002, news 0.004, crowd 0.0 flat. A news-RSS sentiment layer whose JOB is "president meets crypto executives" read ZERO through the most newsworthy crypto policy day of the quarter |
| funding/liquidation structure | **BLIND** | no liquidation/OI feed; funding single-sourced and dead-listed — the $1.44B cascade was invisible |

**Verdict: the bot measures outliers perfectly and cannot explain them.**
Of four real drivers, its sensors caught zero causally, one concurrently
(equity proxies), two lagging, and the news layer - the designed
attribution channel - was silent (its crowd source was already flagged
flat on 2026-08-18).

## Corpus handling (the LEGAL form of "label it as an outlier")

- The window's rows ALREADY self-label structurally: macro=crisis,
  vol_pct 76-89, elevated turbulence ride every row - models and
  reports can condition on them. This note makes the event citable.
- **NO mid-era exclusion, reweighting, or label surgery** - that is
  retuning on one instance (the operator's own directive: "not all from
  this one instance") and a model-side change under the freeze.
- Era-4 readout instruction: stratify surge-window-resolved labels
  (resolution tail through ~2026-08-21 21:00Z, one barrier horizon) by
  the crisis stamp before reading any rate; the 08-19 base-rate note
  (0.24->0.42) compounds with this event.

## Docket additions (evidence-attached, adjudication at readout)

1. **Sentiment-feed health + coverage** - promoted from "crowd source
   flat" to a concrete missed-event finding; A2 (StockTwits) and news
   source verification carry this event as their test case.
2. **Event/attribution inputs** - unscheduled-policy and
   liquidation/OI awareness are the two structurally blind axes; any
   post-readout intake must price OF-7 DoF and stay advisory-only.
