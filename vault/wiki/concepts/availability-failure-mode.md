---
title: Availability Failure Mode
category: concept
summary: Good evidence plus no keyless machine-readable source equals rejected, regardless of how strong the evidence is — and as of 2026-08-08 the rule has fired in both directions, with the first recorded reversal (ETF flows, on exactly its stated revisit terms), three new kills (Glassnode/CryptoQuant paid tiers, CME's bot-wall, Binance's 451), and a new UA-conditional middle class
tags: [data, constraints, method]
sources: 2
updated: 2026-08-08
---

# Availability Failure Mode

## Definition
A candidate input is **rejected on availability alone** when no keyless, machine-readable, stable
source exists — even when the underlying evidence grades MODERATE or better.

## Instances
- **ETF flow data** — real measured effect sizes and a decent literature, killed because the only
  sources are a screen-scrape or a keyed issuer API.
- **Token unlock calendars** — mechanism plausible, but the calendar's API tier is ambiguous, so it is
  deferred under "the same availability failure mode."
- **A national central-bank statistics API** — rejected outright because it is **keyed**.
- **A market-data vendor** — rejected for a short history, a tight rate limit, **and a
  non-commercial license clause that is itself a compliance failure mode** for a for-profit system.

## Why the rule is absolute
An input that needs a key, a scrape, or a license exception introduces an operational dependency and a
silent failure mode into a system whose feeds are all designed to **degrade independently to neutral**.
The evidence quality does not change that.

## The revisit trigger
Rejections here are explicitly reversible: "revisit on a keyless source plus a published study."
Unlike an evidence-based reject, an availability reject can be undone by the world changing rather than
by new research.

## The trigger FIRED — the first recorded reversal (ETF flows, 2026-08-08)
The founding instance of this page was reversed on exactly its stated terms
([[sources/session-20260808-institutional-data-adjudication]]): a **published study arrived**
(Lim, SSRN 6592830 — $100M inflow ≈ 53bp same-day, ~21% of daily variance; preprint-grade)
**and usable sources exist** (Farside scrape with a browser UA, ~666 rows of history
verified; SoSoValue free API backup at ~20 calls/min). ETF daily flows are now **ADOPT #3**,
telemetry-first at 0 DoF — with a **publication-time lookahead hazard** (flows publish
evening/next-morning, not 4pm ET) carried as part of the adoption. The reversal is evidence
the rule works: the rejection was parked, not litigated, and un-parked the day the world
changed.

## New instances (2026-08-08 sweep, each live-verified)
- **Glassnode / CryptoQuant** — free API tiers **no longer exist** (paid now); killed.
- **CME direct JSON** — **403 bot-walled even with a browser UA**; killed (the basis is
  computed from Yahoo `BTC=F` vs Kraken spot instead).
- **Binance from the US** — **HTTP 451 geo-block**; killed.

## The UA-conditional middle class (new, 2026-08-08)
Some sources are keyless but **UA-policed**: SEC EDGAR returns 403 without a
**name + email User-Agent** (SEC policy, verified first-hand); Farside's Cloudflare 403s
non-browser UAs. These are **availability-CONDITIONAL, not availability-failed** — the cure
is a config-lifted UA carrying real operator contact ([[entities/contextfeed]] gap (a)),
not a key, a scrape workaround, or a license exception. The class sits between ADOPT and
REJECT: adoptable the moment the UA lift ships, and not before.

## Related
[[concepts/evidence-grading-ladder]] · [[concepts/dof-budget]] ·
[[sources/compounder-context-evidence]] ·
[[sources/session-20260808-institutional-data-adjudication]] · [[entities/contextfeed]]
