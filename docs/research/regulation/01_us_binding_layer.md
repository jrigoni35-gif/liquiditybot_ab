# US binding regulatory layer (read 2026-10-01)

Produced by a delegated research agent under a citation contract (fetch every
source, grade it, never cite from memory, mark interpretation). Grades:
[PRIMARY] statute/regulation/regulator release; [VENUE] Kraken's own pages;
[SECONDARY] law firm/news; [UNVERIFIED] not opened. **VERIFIED-BY-SESSION** =
re-read by the orchestrating session itself on 2026-10-01. Interpretations are
marked [I]. Not legal or tax advice.

## Rules

| # | rule | authority / citation | grade | applies? | what it means for this bot |
|---|---|---|---|---|---|
| 1 | Retail commodity transactions, "actual delivery" within 28 days | CEA 2(c)(2)(D); CFTC interpretive guidance, Fed. Reg. 2020-11827 (2020-06-24) | PRIMARY | conditional | Leveraged retail crypto is lawful only with actual delivery in 28 days OR through a registered entity. Kraken's 2026 product uses the registered-entity route (#4). [I] |
| 2 | Eligible Contract Participant threshold, individuals | 7 U.S.C. 1a(18)(A)(xi): >$10M discretionary, or >$5M to manage risk | PRIMARY | conditional | The operator is almost certainly not an ECP; irrelevant to the 2026 retail product. [I] |
| 3 | CFTC v. Kraken 2021 | CFTC press release 8433-21 (2021-09-28): $1.25M penalty for margined retail crypto via an unregistered FCM | PRIMARY | context | The 2021 product - the closest analogue of this bot's `use_margin` intent - was illegal as then structured. |
| 4 | Kraken US retail spot margin | Kraken support "Getting started with US margin"; Kraken blog 2026-05-06 | VENUE, **VERIFIED-BY-SESSION** (support page) | yes | NinjaTrader Clearing, LLC d/b/a Kraken Derivatives US, CFTC-registered FCM, NFA ID 0309379. Per-asset caps BTC 20x / ETH 10x / LINK 10x / **PAXG 5x**. Margin call at 80% of required margin, liquidation possible at 40%. Eligibility questionnaire. **Config gap: flat 10x > PAXG 5x.** |
| 5 | State exclusions | Kraken support "geographic restrictions" (read by session 2026-10-01): no service to residents of Maine and New York; margin available to eligible US retail clients, no US state excluded | VENUE, **VERIFIED-BY-SESSION** | **cleared** | Operator resides in **Alabama** (2026-10-01) - served, margin-eligible subject to the questionnaire. The secondary claim that WA is excluded is not on Kraken's page. |
| 6 | SEC/CFTC joint classification | SEC Rel. 33-11412 / 34-105020 (2026-03-17), via Sullivan & Cromwell summary; PDF not opened | PRIMARY via SECONDARY | yes | BTC, ETH named digital commodities; LINK reported on the list (not confirmed against primary text); PAXG classification undetermined. |
| 7 | CFTC anti-fraud / anti-manipulation | CEA 6(c)(1); 17 CFR 180.1 (Fed. Reg. 2011-17549) | PRIMARY | yes | Reaches any commodity in interstate commerce - spot crypto fraud/manipulation by an individual (wash trading, layering). Existing conduct controls cover it; 180.1 is the right citation for spot. [I] |
| 8 | Spoofing | CEA 4c(a)(5)(C), 7 U.S.C. 6c(a)(5)(C) | PRIMARY | no, textually | Applies "on or subject to the rules of a registered entity" (DCMs, SEFs), not spot cash trading. Spot layering is reached via 180.1 instead. [I] |
| 9 | Kraken ToS - automation | Kraken Global Terms §9 | VENUE | yes, favourable | Prohibits bots/scripts on site content but carves out API trading - this bot's path. [I] |
| 10 | Kraken trading rules - abuse / STP | Kraken Exchange Trading Rules | VENUE | yes | Prohibits wash trading, layering, spoofing; mandatory self-trade prevention is a backstop, not a substitute (the bot's own LB-022 cancel-first logic stays required). |
| 11 | Kraken API rate limits | Kraken API docs | VENUE | yes | Decay counters shared across REST/WS/FIX; ~4 trades/day is far from limits. |
| 12 | Margin liquidation mechanics | Kraken support (same page as #4) | VENUE, **VERIFIED-BY-SESSION** | yes | Venue-side liquidation is outside the bot's exit ladder (invariant 5 governs the bot's own exits only). Design gap if margin is ever used. |
| 13 | IRS 1099-DA broker reporting | IRS final regulations (digital asset broker reporting) | PRIMARY | yes | Gross proceeds from 2025-01-01; basis for assets acquired from 2026-01-01. CPA needed for lot reconciliation. |
| 14 | Wash sale | IRC 1091; IRS Notice 2014-21 (via secondary) | SECONDARY | does not apply today | Crypto is property; 1091 covers stock/securities. Legislative target - build nothing that assumes it stays. |
| 15 | NY BitLicense | 23 NYCRR Part 200 | PRIMARY / SECONDARY | conditional | Kraken has excluded NY since 2015 (secondary). |

## Global one-liners (no nexus for a US operator; for completeness)

- **EU** MiCA (Reg. 2023/1114) governs licensed CASPs; MiFID II RTS 6 algo rules bind investment firms, not an individual trading own account. [I]
- **UK** FCA bans crypto-derivative sales to retail clients.
- **Japan** reported 2x retail crypto margin cap [SECONDARY].
- **Singapore** MAS: sources conflict (retail leverage ban vs 2:1 on unrelated CFDs) - unresolved.
- **Hong Kong** SFC: leveraged virtual-asset derivatives restricted to professional investors.

## Not verified (carry forward, do not treat as settled)

NFA BASIC registration of NinjaTrader Clearing; any CFTC release specific to
Kraken's 2026 retail margin product; the SEC/CFTC 2026 release PDF (and LINK's
place on its list); Kraken's authoritative excluded-state list; IRS Notice
2014-21 text; the Singapore rule.
