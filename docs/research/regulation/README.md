# Regulation knowledge base — US operator (2026-10-01)

Operator request (2026-09-29): "Give the bot the knowledge of security
regulations stock exchanges of the world, also 2026 published literature about
margin trading with algorithms." Jurisdiction: **United States** (memory
`operator-jurisdiction`; a UK answer was a mis-click). Not legal or tax advice.

| file | what |
|---|---|
| `01_us_binding_layer.md` | the rules that bind THIS bot (US retail individual, own account, Kraken spot, `use_margin: true` at 10x configured, dry-run) + a one-line global map |
| `02_literature_2025_2026.md` | graded 2025-2026 literature on leveraged/algorithmic crypto trading |

Prior art kept, not redone: vault `sources/compliance-market-conduct` (conduct
classes using CME rules as the model) and `docs/law/conduct_standard.md`.

## Pre-live blockers found (none matters while dry-run; each must clear before ARM LIVE)

1. **State of residence — UNKNOWN, and a precondition for the whole bot.**
   Kraken is reported (secondary sources, June 2026) to exclude NY, WA and ME
   from the platform entirely, not just margin. If the operator lives in one,
   the sole execution venue is unavailable. Verify against Kraken's current
   terms. [SECONDARY]
2. **`leverage.region_max_leverage: 10` exceeds Kraken's PAXG cap.** Kraken's
   US margin page, read by this session 2026-10-01: BTC up to 20x, ETH 10x,
   LINK 10x, **PAXG 5x**. A flat scalar cannot represent per-asset venue caps.
   [VENUE, VERIFIED-BY-SESSION]. Changing the config forks the decision cohort -
   an operator decision, deliberately not made during the 2-week hold.
3. **Venue-forced liquidation sits outside the bot's exit ladder.** Margin
   call at 80% of required margin, possible liquidation at 40% [VENUE,
   VERIFIED-BY-SESSION]. Invariant 5 governs the bot's own exits; Kraken's
   liquidation engine is a third actor. Needs monitoring/alerting before any
   margin use - a design gap, not a config one.
4. **Margin eligibility.** Since 2026-05-06 (Kraken blog [VENUE]) US retail
   spot margin is offered through NinjaTrader Clearing, LLC d/b/a Kraken
   Derivatives US, a CFTC-registered FCM, NFA ID 0309379 [VENUE,
   VERIFIED-BY-SESSION]. It requires an eligibility questionnaire. The NFA
   registration itself was NOT checked against NFA BASIC - do that first.
5. **Tax.** 1099-DA broker reporting covers 2025+ proceeds; ~4 trades/day is
   ~1,460 lots/year to reconcile. Wash-sale (IRC 1091) does not currently reach
   crypto (property, Notice 2014-21) - a live legislative target. CPA needed.

## What the literature says about using margin here

With no established edge (every measurement to 2026-10-01), leverage adds only
variance drag: g = L·mu − L²·sigma²/2 (Heimer & Simsek 2019, JFE, an identity).
Realized leverage has been 0.004-0.12x per position and 0.344x aggregate
(`docs/quant/2026-09-02_leverage_liquidation_distance.md`) - the 10x cap is
configured but has never bound. Keep it unexercised until an edge clears the
overfit battery.
