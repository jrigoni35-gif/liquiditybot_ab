---
title: Crypto skills scout for the assistant — 11 sources, judged and refuted (2026-09-08)
type: raw/research
status: COMPLETE — nothing installed; the refutations held
method: 13-agent workflow wf_942a9dea-809 (11 inventories → judge → refuter; 920k tokens, 327 tool uses) + 12 direct raw-SKILL.md / catalog / README fetches by the session
operator ask (verbatim): "Look up any good crypto skills that would help you"
---

# What was asked, and the bar

Which Claude Code SKILLS or MCP servers would help the ASSISTANT do better
work on this repo (not "help a human trade"). Five needs, scored 0–3:
N1 Kraken venue expertise · N2 measurement rigor for trade-level statistics
(look-ahead checklists, block bootstrap, cluster-robust, DSR, MinTRL/MinBTL,
PBO) · N3 market microstructure / market making · N4 DeFi/AMM mechanics ·
N5 read-only Kraken/crypto data tooling. Constraints: every ACTIVE skill's
description is loaded into every request (measured 2026-08-20: 336 skills =
~42k tokens/request; 8 = ~875), so install granularity matters; anything
that can PLACE ORDERS or MOVE FUNDS from the assistant's toolset is a hazard
(CLAUDE.md invariants 3–5), not a feature. `/plugin` is unavailable here;
install = copy a SKILL.md dir into `~/.claude/skills/`.

# Sources inventoried (scores N1..N5, [K] fetched)

| source | what | can_trade | N1 N2 N3 N4 N5 |
|---|---|---|---|
| **krakenfx/kraken-cli** — Rust CLI + stdio MCP + 59 SKILL.md dirs, MIT, v0.4.1; Windows = WSL or `cargo install --git` (cargo 1.97 is on this box) | official | YES (trade 11/11, funding 4/14 dangerous; `-s market` = 10 tools, 0 dangerous; README sample JSON is `-s all`) | 2 0 0 0 2 |
| **agiprolabs/claude-trading-skills** — 68 dirs, MIT, Solana-flavoured | pack | YES (dex-execution, jito-bundles, raptor-dex, copy-trading sign txs) | 0 2 2 2 1 |
| **ccxt/ccxt mcp/** (`ccxt-mcp`) + CCXT skills | official | LATENT (trading/funds tiers off by default, config-file enabled) | 1 0 0 0 3 |
| shakeebshaan/claude-code-quant-skills — 6 (backtest-review 7-audit checklist) | community | no | 0 2 0 0 0 |
| quant-research (claudskills.com) — 1 SKILL.md, best vocabulary table; "bundled scripts" 404 ×3; license/upstream unknown; $9/mo desktop path | community | no | 0 2 0 0 0 |
| crypto MCPs: Nayshins/mcp-server-ccxt, oilst/kraken-mcp (FastMCP, trades), Cryptohopper | community | YES (kraken-mcp) | 1 0 0 1 2 |
| solidity-audit ×3: farrellh1 (370-item Cyfrin checklist), Trail of Bits skills, Auditmos | community | no | 0 0 0 1 0 |
| anthropics/skills + financial-services-plugins + cookbook creating-financial-models (DCF) | official | no | 0 0 0 0 1 |
| tradermonty/claude-trading-skills — 74, equities | community | no | 0 1 0 0 1 |
| VictorVVedtion/trading-skills — persona pack ("68 legends") | community | no | 0 0 0 0 0 |
| Snyk "top 8" + dev.to "top 5" curated lists (JoelLewis/finance_skills statistics-fundamentals, etc.) | lists | mixed | 0 1 0 0 1 |

# Judge's top 12 → refuter's verdicts (every INSTALL knocked down; reasons re-read and upheld)

| pick | judge | refuter | why the refutation holds |
|---|---|---|---|
| prediction-market-live-ops (agiprolabs) | INSTALL-NOW (states D2's join rule verbatim) | DO-NOT-INSTALL | the lesson is already in [[concepts/the-method]] #12; the POSITIVE rule was the missing piece → written as consequence (e) today, zero toll |
| market-microstructure-traditional (agiprolabs) | INSTALL-SELECTIVELY (A-S, Kyle λ, Glosten-Milgrom, Roll; ~1,600 words; no queue/fill-hazard) | PARK | vault already holds `entities/avellaneda-stoikov` + 19 related pages and the repo ships execution/fill-hazard instruments |
| walk-forward-validation (agiprolabs) | INSTALL-SELECTIVELY (purge/embargo code, CPCV, DSR, PBO; no block bootstrap / n_eff / MinTRL) | PARK | duplicates `scripts/overfit_check.py`; "second implementation" is not an independent route |
| kraken-rate-limits (kraken-cli) | INSTALL-SELECTIVELY | DO-NOT-INSTALL | it summarizes two canonical pages that fetch as real content — see "Canonical URLs" |
| kraken-order-types (kraken-cli) | INSTALL-SELECTIVELY | DO-NOT-INSTALL; N1 ≤ 1 | ~9-row modifier table; ~65% CLI syntax noise on a box without the binary; no EOrder:/EAPI:, no WS-v2 |
| backtest-review (shakeebshaan) | INSTALL-SELECTIVELY | PARK | dominated by CLAUDE.md + the-method + overfit battery |
| ccxt-mcp | PARK | DO-NOT-INSTALL | the repo's own `.venv` ccxt 4.5.64 with no apiKey fetched a live Kraken book — zero-toll route already exists |
| kraken-cli MCP `-s market` | PARK | DO-NOT-INSTALL (hazard worse than judged: README default `-s all`; `KRAKEN_API_KEY` env precedence) | if ever revisited: WSL/cargo, `-s market` only, no key in env |
| quant-research (claudskills) | SKIP, harvest vocabulary | — | harvested below |
| lp-math + impermanent-loss (agiprolabs) | PARK until an AMM task exists | — | the only N4 candidate with math (x·y=k, CLMM 1.0001^tick, IL = 2√r/(1+r) − 1) |
| statistics-fundamentals (JoelLewis) | PARK | — | states "use block bootstrap for serially dependent series" in so many words; nothing beyond D3's fix |
| mcp-builder (anthropics/skills) | PARK, one build session | — | method only; the route to a repo-owned read-only recorder MCP if N5 ever needs one |

# Gaps no skill fills (the repo is ahead of the field here)
MinTRL/MinBTL — zero candidates. Effective-n deflation over concurrent
trips — zero (cohort_eval.py / gate_truth_report.py are ahead). Cluster-
robust inference — only a HAC aside. **No candidate has a MUTATION or
INJECTION step — every N2 candidate is a prose checklist, and D2 was caught
by an injection pin, not a checklist.** N3 queue position / maker fill
hazard / post-only fill probability under adverse selection — none. N1
Kraken error strings, WS-v2-vs-REST, book checksum — only docs.kraken.com.

# Harvested at zero toll
- **Canonical Kraken URLs (fetch, don't carry):**
  docs.kraken.com/api/docs/guides/spot-rest-ratelimits/ and
  /spot-ratelimits/ — verified tables: REST counter Starter/Intermediate/Pro
  15/20/20, decay 0.33/0.5/1.0 per s; per-pair trading engine 60/125/180,
  decay 1/2.34/3.75 per s; cancel < 5 s costs +8, amend < 5 s +3; batch ≤ 15
  orders; streaming consumes no REST points. `data/kraken_feed.py` uses a
  flat `rate_limit_per_sec` bucket (line 171) — the counter/decay model is
  NOT implemented; a latency question for later, not an era-8 change.
- **Vocabulary (quant-research):** look-ahead via truncation, target-leakage
  scan, stationary block bootstrap (Politis–Romano), PSR/DSR, PBO, CPCV,
  Romano–Wolf, time-shift placebo, cost monotonicity, sign-flip; guardrails
  "evidence citation is mandatory … file:line, hash, numeric value, or tool
  output" and "Kill > Promote" — this repo's law restated.
- **the-method #12 consequence (e)** added: join = last bar whose close ≤
  the decision instant; passive-fill replay EV = upper bound.
- **A stale fee schedule in the wild:** kraken-cli's `kraken-fee-optimization`
  quotes "starter tier 0.26% taker / 0.16% maker" — not a row on Kraken's
  fee page as fetched 2026-09-08 (see the fee-table section below). The
  skill's own advice, `kraken volume --pair BTCUSD -o json` (live, needs a
  query-permission key), is the FEE-3 cure; the hardcoded row is recurrence
  #1 of [[concepts/the-method]] shipping inside a vendor's skill.

# Fee-table finding (side effect of the scout)

The kraken-cli skill's "starter tier 0.26% taker / 0.16% maker" matched no
row anywhere in the repo, so the venue's page was fetched — first through the
summarizer (which reported two tables and a "Tier 1 0.38/0.80" that clashed
with the repo), then as RAW TEXT with no summarizer: **Tier 1 $0+ 0.40/0.80 ·
Tier 2 $2.5K+ 0.30/0.60 · Tier 3 $10K+ or $20k AoP 0.22/0.38 · Tier 4 $25K+
or $50k AoP 0.20/0.35 · … Pro 5 $500M+ 0.0/0.05**, tier granted by the best
of 30-day volume OR assets on platform (2026-09-08T20:15:29Z). The repo's
`core/venue_fees.py` carried the LEGACY ladder (25/40, 20/35 at $10k, 14/24
…) read from `/0/public/AssetPairs` on 09-05 — which by 09-08 returns
`fees: []`. Cut #10's E1 "fee correction" (22/38 → 20/35) had been booked on
that module's word; the operator's 08-29 app screenshot (Tier 3 = 22/38 at
$17,482) was right all along. Instrument corrected the same session
(schedule + AoP + page fetcher/parser, two-route drift report, pins
rewritten, mutation 7/7); the booking is cohort-resetting and docketed as
FEE-4. Full record: `docs/quant/2026-09-08_fee_ladder_correction.md`;
[[concepts/the-method]] #13. The vendor skill's 0.16/0.26 is neither ladder —
a struck schedule shipping inside a skill.
