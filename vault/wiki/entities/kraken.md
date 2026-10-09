---
title: Kraken
category: entity
summary: The sole execution venue, holder of the only credentials, and the trust anchor for venue-integrity judgements
tags: [venue, external]
sources: 6
updated: 2026-08-01
---

# Kraken

The **sole execution venue**. Holds the only credentials in the system.

## Invariant status
Enforced structurally: an execution-eligibility check requires the venue name to match, and the rule
must not be relaxed or subclassed around. Adapters for other venues exist only as hard-off stubs.

## Safety mechanisms tied to it
- **Withdrawal endpoints are deny-listed and checked before any network call.**
- A venue-side **dead-man switch** auto-cancels if the bot stops refreshing it.
- Per-pair precision fetched from venue metadata with a static offline fallback.
- Clock skew self-tested against the venue's time endpoint at startup.
- Hourly balance cross-check; drift beyond tolerance blocks new entries.

## Its epistemic role
As the **regulated execution venue it is the trust anchor**, while read-only feeds from other venues are
"the objects of suspicion" in venue-integrity weighting. Candle volume is re-grounded on it "so the
model never learns from fabricated external volume."

## Cost relevance
Its public fee floor is enforced by the config guard, and **its volume tiers are the direct lever on
[[concepts/cost-to-volatility-ratio]]** — halving the fee buys the same cost/sigma improvement as a 6x
longer horizon.

## PAXG joins the universe (2026-08-05, commit `717b2e39`)
Gold enters as the top rung of the tangible-value ladder
([[synthesis/tangible-value-doctrine]]). Venue facts as verified at commit time:

- **Tradeable, not decorative** — Kraken quotes **PAXG/USD at a 2.86bps spread with 20 levels a
  side**.
- **AssetPairs-verified fallback meta** (`data/kraken_feed.py`): `PAXGUSD` **price_decimals 2,
  lot_decimals 8, ordermin 0.001**, **costmin $0.50**.
- **ordermin 0.001 oz ≈ $4.25 at a $4,250 spot — the smallest ticket in the universe by dollar
  value.** This is the fact that makes gold *reachable by the sizer at this account size* rather
  than a listing it can never fill; the offline fallback exists precisely so a metadata fetch
  failure cannot silently make it unreachable.
- **Realized 5m volatility 0.075%** — the lowest in the universe, and the top of the measured
  ordering PAXG < BTC < ETH ~ SUI < ARB.
- **Spot only.** The bot holds **no margin on this venue or any other**, and no board or metric
  was created that would imply otherwise.

Capacity consequence: the guard's REST-fallback envelope FATALs at 13 pairs, so PAXG cost one
discretionary skimmer slot (`max_extra` 6 → 5) — [[entities/config-guard]].
