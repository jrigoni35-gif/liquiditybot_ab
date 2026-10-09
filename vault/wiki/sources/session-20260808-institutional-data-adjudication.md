---
title: "Institutional/Government Data Adjudication (2026-08-08) — Six ADOPTs at 0 DoF, the SKIP Ledger, and the ContextFeed Agility Verdict"
category: source
summary: "Operator-requested adjudication by three deep-research agents with live-verified endpoints: six ADOPTs, all telemetry-first at 0 model DoF under the CLOSED 2026-07-24 DoF ledger — (1) CME basis + perp funding EXTREMES as a crash-risk/asymmetry dial (BIS WP 1087, Chi et al. JFM 2023; funding_rate is already a feature, the evidence-backed asymmetric veto consumer is not), with the key reinterpretation that CME leveraged-fund net shorts are basis-trade mechanics NOT bearishness; (2) BLS CPI/NFP into the existing FOMC event-gate machinery (minutes-scale response, NY Fed SR 1052 regime caveat); (3) US spot ETF daily flows — the ONE new institutional dataset with provisional next-day value (Lim SSRN 6592830), reversing the 07-24 availability rejection on its own stated revisit terms, with a publication-time lookahead hazard; (4) OFR FSI daily CSV (T+2, credit/funding sub-columns are the new info vs VIX); (5) EDGAR 8-K watchlist poller (403 without a name+email UA — our ContextFeed UA fails SEC policy today); (6) TFF COT crypto categories on Socrata gpe5-46if (Disaggregated has ZERO crypto rows — premise corrected; shutdown-class multi-week gaps must be tolerated). Thirteen SKIPs each with killing citation — including COIN/MSTR options→crypto transmission at ZERO evidence, making the three shipped opt_* features schema-AB PRUNE CANDIDATES. DoF arithmetic: hundreds of labels fund ~2-5 effective context features TOTAL; funding/basis/COT/DVOL ≈ 1.5 effective; at 64 features vs ~61 fresh-era labels the ledger stays closed. Agility verdict: ContextFeed IS the designed seam; gaps = config-lifted UA, wider-than-3x grace for weekly sources, and the deliberately GATED corpus-injection path (a feature, not a defect). Proposed queue family 45a-45f, sequenced BEHIND 41b/41c/42a/42e/37g/37b, nothing touching the feature schema before h432."
tags: [session, research, adjudication, data-sources, macro, institutional, government, dof-budget, contextfeed, evidence-grading, etf-flows, cot, funding, basis]
sources: 1
source_path: none — session work product (three deep-research agent reports in this session's task outputs; endpoint claims live-verified by the agents, not snapshotted to raw/)
source_date: 2026-08
authors: [operator, claude-session, three-deep-research-agents]
ingested: 2026-08-08
updated: 2026-08-08
---

# Institutional/Government Data Adjudication (2026-08-08)

## Provenance and boundary statement

Operator-requested research adjudication, filed same session per governance rule 12. Three
deep-research agents (institutional-data, government-data, and a cross-checking third) ran
independently; **every endpoint claim below was live-tested by the agents during the session**
(HTTP status codes, row counts, UA behavior first-hand), and the three reports converged on
the same #1. Full agent reports with all citations live in this session's task outputs; this
page distills the **durable** verdicts, endpoint specs, and gotchas.

**Paper/real boundary** ([[concepts/paper-real-boundary]]): everything here is
**research-side and venue-data-side** — literature grades plus live web-endpoint probes. No
sim-conditioned number is quoted. **Nothing on this page shipped as code**; the build
proposals are filed as owed item 45 (proposals, not facts), and the adjudicated *verdicts*
(ADOPT/SKIP grades, endpoint facts) are what this page asserts.

**Governing constraint, stated up front:** the standing **2026-07-24 DoF ledger
([[sources/compounder-context-evidence]], [[concepts/dof-budget]]) remains CLOSED — zero new
model features until the label corpus funds them.** Every ADOPT below enters at **0 model
DoF**: telemetry first, then at most a risk-gate consumer behind quant gates. This is the
central encoding principle ("slow context belongs in structural gates, not the 5m model
matrix") applied under a closed ledger.

---

## ADOPT — ranked, all telemetry-first at 0 model DoF

### 1. CME front-month basis + perp funding EXTREMES as a crash-risk/asymmetry dial
**The convergent #1 across all three agents.** Evidence: **BIS Working Paper 1087**
(Management Science 2026) — high carry predicts crashes and deleveraging episodes; **Chi et
al., Journal of Financial Markets 2023** — basis is the strongest cross-sectional predictor
in crypto. Mechanics:
- **Basis is computable free**: Yahoo `BTC=F` front-month (live-tested HTTP 200, **~15 min
  delay**) vs Kraken spot.
- **`funding_rate` is ALREADY a model feature** (via ccxt) — but the evidence-backed
  **consumer** does not exist: **extreme positive funding → truncate/veto longs,
  asymmetric** (down-only, per [[concepts/asymmetry-law]]). That consumer is a **risk-gate
  build, 0 DoF** — not a new feature.
- **KEY REINTERPRETATION (binding on future COT reads):** leveraged-fund **net shorts on CME
  are basis-trade mechanics, NOT bearishness**. The funds are short futures against long
  spot/ETF to harvest the carry. **Reading COT positioning directionally is a category
  error** — the directional information lives in the *live basis level itself*.

### 2. BLS CPI/NFP calendar into the existing FOMC event-gate machinery
Post-2020, BTC responds to CPI and FOMC surprises **within minutes**. The repo's calendar +
`in_event_window` machinery is **already wired and telemetry-only** — adding the BLS CPI/NFP
release calendar to it is the **highest value-per-effort item** on the list. Counterweight
carried with it: **NY Fed Staff Report 1052** — the macro sensitivity is **post-2020 and
regime-dependent**; a gate, never a signed direction ([[concepts/evidence-grading-ladder]]'s
existence/direction split, again).

### 3. US spot ETF daily flows — the ONE new institutional dataset with predictive value
**This reverses the 2026-07-24 availability rejection on exactly its stated revisit terms**
(a usable source plus a published study — see [[concepts/availability-failure-mode]]).
- Evidence: **Lim, SSRN 6592830** — $100M inflow ≈ **53bp same-day**, ~**21% of daily
  variance**, bidirectional Granger causality. **Grade: provisional/preprint** — an 18-month
  sample; treat as provisional next-day value, not established.
- Sources: **Farside scrape primary** (Cloudflare 403s non-browser UAs — needs a browser
  UA; **~666 rows of history verified** by the agents), **SoSoValue free API backup**
  (~20 calls/min).
- **CRITICAL lookahead hazard:** flows publish **evening/next-morning, NOT at 4pm ET**.
  Any backtest stamping flows at market close carries lookahead. Stamp at **publication
  time**; consume as **5-day z-scores/streaks, never single prints**.

### 4. OFR Financial Stress Index + FRED batch
**OFR FSI daily CSV** — live-verified, **T+2 lag**. The **credit and funding sub-columns are
the new information vs VIX**; the adjudicated condition is to **test incremental value over
the existing VIX-family dials before keeping it**. Alongside: **FRED batch** for
`NFCI` / `DFII10` / `BAMLH0A0HYM2` (**120 req/min**; use the **release-calendar endpoint**
to schedule pulls instead of polling blind).

### 5. EDGAR 8-K watchlist poller
`getcurrent` Atom feed + `efts` full-text search; **minutes-scale latency** on 8-K filings
for a watchlist (the MSTR/COIN class). Gotchas, **verified first-hand**: EDGAR returns
**403 WITHOUT a proper User-Agent** — SEC policy requires **name + email contact** —
and our ContextFeed `_UA` currently says **"contact: none", which fails that policy**;
**10 req/s ceiling**. Needs the config-lifted UA (gap (a) below) before any build.

### 6. TFF COT crypto categories — an upgrade of the existing legacy COT source
Same **Socrata API, dataset `gpe5-46if`** — live-verified to carry **current-week rows**.
**Premise corrected by the agents:** the *Disaggregated* COT report has **ZERO crypto rows**
— the crypto categories live in the **TFF (Traders in Financial Futures)** report. Operating
constraints: the **2025 government-shutdown precedent means multi-week publication gaps** —
the ingester must tolerate them (gap (b) below); and per ADOPT #1's reinterpretation, this is
a **weekly regime dial only, never directional**.

---

## SKIP — evidence-adjudicated; cite this section when any is re-proposed

Per [[concepts/evidence-grading-ladder]], every rejection carries its killing citation and
binds future sessions absent new evidence.

| Candidate | Killing reason |
|---|---|
| **COT as entry signal** | The information lives in the live basis (ADOPT #1); positioning is basis-trade mechanics, not direction. |
| **Put/call ratios as direction** | Folklore — no crypto evidence of directional value. |
| **IV-skew as direction** | It is a **sellable risk premium**, not a direction forecast. |
| **COIN/MSTR options → crypto transmission** | **ZERO evidence of any kind** — see the prune-candidate consequence below. |
| **Aggregate stablecoin issuance** | **Lyons & Viswanath-Natraj**: issuance is **endogenous to demand** — keep the existing `stable_wk_pct` dial at 0 DoF, **never graduate it** to the model matrix. |
| **13F holdings** | 45-day lag — cadence kill. |
| **N-PORT** | 60-day lag, third-month-only — cadence kill. |
| **Form PF** | Confidential — no public data exists. |
| **OFAC / EIA / BIS-IMF stats / ESMA** | No mechanism at the decision cadence. |
| **Equity-leads-crypto-by-HOURS features** | Documented transmission is **minutes**; any hourly lead found in a backtest is **overfit by construction**. |
| **Kimchi premium** | Retail-Korea gauge; level correlation with returns **−0.06**. |
| **Glassnode / CryptoQuant free tiers** | API access is **paid now** — [[concepts/availability-failure-mode]]. |
| **CME direct JSON** | **403 bot-walled even with a browser UA** — availability kill. |
| **Binance from the US** | **HTTP 451 geo-block** — availability kill. |

> **Consequence of the COIN/MSTR zero-evidence finding:** the repo's **three shipped model
> features `opt_pcr_z` / `opt_oi_pcr_z` / `opt_iv_skew` are now schema-AB PRUNE
> CANDIDATES** — the adjudication found no evidence of any kind for the transmission channel
> they encode, and one of them is already pinned at its −3.00 clip rail (owed 41(c)). Path:
> **INFO-arm schema-AB experiment first, no schema churn until the h432 verdict** (owed 45f).
> This is the evidence-based route [[concepts/coverage-floor]] demands — dormancy alone never
> justified a prune; a zero-evidence adjudication plus a measured A/B can.

---

## The DoF arithmetic (binding)

A corpus of **hundreds of labels funds ~2-5 effectively independent context features
TOTAL** (Peduzzi events-per-variable + DSR/PBO effective-trials accounting), and the
candidate quartet **funding / basis / COT / DVOL is mutually correlated ≈ 1.5 effective
features**. At **64 features vs ~61 fresh-era labels, the ledger stays CLOSED.** This is why
every ADOPT above is telemetry-first at 0 model DoF — see [[concepts/dof-budget]] for the
full arithmetic and its interaction with the ESS tension.

---

## The agility verdict — ContextFeed IS the designed seam

Ingestion-side agility: **YES.** [[entities/contextfeed]] already has the right shape for
all six ADOPTs — 5 keyless sources, per-source **3x-grace `known=False`** staleness states,
a wall-clock poll budget, injectable fetch (testable), config-lifted knobs, CX reason codes.
The government agent's headline recommendation — **"dials must go stale, not frozen"** — is
**ALREADY implemented** as the `known=False` discipline (independently converging with
[[concepts/zero-is-not-a-reading]]'s input-plane wing).

**Three gaps found:**
- **(a) UA header needs a config-lift** carrying real operator contact (name + email) — the
  current `_UA` "contact: none" fails SEC's policy and is impolite to NY Fed; blocks ADOPTs
  #3 and #5.
- **(b) Weekly-cadence sources need wider-than-3x grace** config — the COT shutdown
  precedent (multi-week gaps) would burn a 3x-grace weekly source to `known=False`
  permanently; grace must be per-source configurable.
- **(c) Corpus injection is deliberately GATED — a feature, not a defect.** The path is:
  telemetry → risk-gate consumer behind quant gates → schema graduation **only** via
  schema-AB + era stamp **when labels fund it**. The adjudication examined this as a
  potential agility gap and ruled it the opposite: it is [[concepts/shadow-first-adoption]]
  and the closed DoF ledger doing their jobs.

---

## Durable endpoint / gotcha specs

| Source | Endpoint / dataset | Access gotcha | Rate limit | Timing | Fragility |
|---|---|---|---|---|---|
| Yahoo `BTC=F` | front-month quote | none observed (live 200) | unpublished | **~15 min delay** | MODERATE — unofficial, churn-prone |
| Kraken spot | existing venue feed | — | existing | live | LOW (already the venue) |
| Farside (ETF flows) | daily-flow table scrape | **Cloudflare 403 for non-browser UA** — browser UA required; ~666 rows verified | scrape etiquette | publishes **evening/next-morning, NOT 4pm ET** — lookahead hazard | HIGH (scrape) |
| SoSoValue (ETF flows backup) | free API | — | **~20 calls/min** | same publication caveat | MODERATE |
| OFR FSI | daily CSV | none (live-verified) | — | **T+2** | LOW |
| FRED | `NFCI` / `DFII10` / `BAMLH0A0HYM2` batch | standard FRED access | **120 req/min** | use the **release-calendar endpoint** for scheduling | LOW |
| SEC EDGAR | `getcurrent` Atom + `efts` full-text | **403 without name+email User-Agent** (verified) | **10 req/s** | minutes-scale filing latency | LOW-MODERATE (policy-policed) |
| CFTC Socrata | dataset **`gpe5-46if`** (TFF) | none — live current-week rows verified; **Disaggregated has zero crypto rows** | Socrata defaults | weekly; **shutdown = multi-week gaps** | MODERATE (publication gaps) |
| CME direct JSON | — | **403 bot-walled even with browser UA** | — | — | UNUSABLE |
| Binance (from US) | — | **HTTP 451 geo-block** | — | — | UNUSABLE |
| Glassnode / CryptoQuant | free tiers | **API is paid now** | — | — | UNUSABLE (free) |

---

## What this supersedes

- **[[sources/compounder-context-evidence]] (2026-07-24):** ETF-flows availability rejection
  **REVERSED** (revisit trigger fired); COT adoption **reinterpreted** (basis-trade
  mechanics, TFF categories, weekly dial only); stablecoin aggregate-supply delta **demoted**
  (endogenous to demand — dial stays 0 DoF, never graduates); the "3-4 model-adjacent
  features" allowance moot under the closed ledger. Supersession callouts filed on that page.
- **[[concepts/availability-failure-mode]]:** first recorded reversal, plus three new kills
  (Glassnode/CryptoQuant, CME JSON, Binance-from-US) and the new **UA-conditional** middle
  class.

## Proposed queue — family 45a-45f (filed as owed item 45, NOT as work done)

45a basis+funding crash dial · 45b CPI/NFP calendar · 45c ETF-flow ContextFeed source ·
45d OFR FSI source · 45e EDGAR 8-K flag · 45f schema-AB options-features prune experiment.
All telemetry-first; **sequenced BEHIND the currently-owed queue
(41b / 41c / 42a / 42e / 37g / 37b); nothing touches the feature schema before the h432
verdict.** Full statements: [[synthesis/owed-measurements]] item 45.

## Related pages

[[concepts/dof-budget]] · [[concepts/evidence-grading-ladder]] ·
[[concepts/availability-failure-mode]] · [[concepts/asymmetry-law]] ·
[[concepts/shadow-first-adoption]] · [[entities/contextfeed]] ·
[[sources/compounder-context-evidence]] · [[synthesis/owed-measurements]]
