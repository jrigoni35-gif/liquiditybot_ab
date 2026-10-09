---
name: institutional-data-verdicts
description: "2026-08-08 adjudication of government/institutional data inputs — what to ingest, what is folklore; do not re-propose the skip list"
metadata: 
  node_type: memory
  type: project
  originSessionId: 63d8f842-8108-448c-b2d9-fa9a4c8a2da4
  modified: 2026-08-08T20:35:26.270Z
---

Three live-verified deep-research reports (2026-08-08, operator-requested) adjudicated institutional/government data for the bot. Full spec table: vault wiki `sources/session-20260808-institutional-data-adjudication.md`; queue items 45a–45f in `synthesis/owed-measurements.md`.

**Adopt (telemetry-first, 0 model DoF — the [[432-migration-hold]]-era feature ledger stays CLOSED):** CME basis + funding *extremes* as an asymmetric crash-risk dial (BIS WP 1087 — the #1 convergent pick; funding_rate is already a feature but the extreme-crowding *consumer* doesn't exist); BLS CPI/NFP into the existing FOMC calendar gate (BTC reacts within minutes, exactly our bar size); US spot ETF daily flows (Farside scrape needs a browser UA, publication is EVENING not 4pm ET — timestamp discipline or the backtest carries lookahead); OFR FSI daily; EDGAR 8-K watchlist (SEC 403s without name+email User-Agent); TFF COT crypto categories (weekly regime dial only).

**Do not re-propose:** COT as directional/entry signal (leveraged-fund shorts are basis-trade mechanics — category error); put/call ratios or IV skew as direction (folklore / sellable risk premium); COIN/MSTR options→crypto transmission (zero evidence — the three shipped opt_* features are schema-AB prune candidates, item 45f); aggregate stablecoin issuance (endogenous to demand, top-journal consensus); 13F/N-PORT/Form PF (lag); equity-leads-crypto-by-HOURS features (transmission is minutes; hourly leads in backtest are overfit); kimchi premium.

**Why:** the DoF arithmetic is binding — hundreds of labels fund ~2–5 *effective* context features total, and funding/basis/COT/DVOL correlate to ~1.5 effective. 64 features vs ~61 fresh-era labels.

**How to apply:** new sources land as ContextFeed dials (known=False grace discipline — the seam is agile and proven); consumers go behind quant gates at 0 model DoF; schema graduation only via schema-AB + era stamp after h432. Sequenced behind owed 41b/41c/42a/42e/37g/37b.
