# Session log — 2026-07-13 phone session (10:33 → 23:30 UTC)

## TL;DR

Started with "restart the bot clean." Ended with: the bot learning on a
53-feature schema in an open-ended supervised run, learning data
surviving any container death, one code line on `main` (14 commits),
phone access to both a read-only status page and the full dashboard,
and a Windows runbook for home parity. Cost of the day: **−$1.11 paper**
($1.55 fees — learning tuition). Gained: **22 training rows** and an
infrastructure that compounds them forever.

## What runs right now (cloud container)

| Thing | State |
|---|---|
| Bot | DRY_RUN, RUNNING, ~$798.8, lifetime cycle counter persisting |
| Supervision | sentinel loop (keepalive 10min + deep audit hourly), armed by `outputs/keepalive.on` |
| Claude | hourly tick at :52 (health, page refresh, bundle push), incident monitor, silent unless anomalous |
| Phone: status page | https://claude.ai/code/artifact/d1314828-31f6-485b-91b8-8f0552ed34c5 (read-only, hourly refresh) |
| Phone: full dashboard | https://liquiditybot-cloud.tail7a5ca4.ts.net (Tailscale, tailnet-only, ~150–270ms) |
| Learning stream | `paper-telemetry` branch, bundle refreshed hourly, checksummed + audit-chained |

**Stopping things**: delete `outputs/keepalive.on` → revival stops.
Tell Claude "stop the ticks" → hourly cron stops. `./stop.sh` → bot stops.

## Shipped to `main` (all battery-green: ~447 tests, smoke 205, assurance 47, overfit 7)

**Trust & safety**
- `c1eaa23` force_dry restored to VALID_COMMANDS — the LIVE→DRY safety button was silently dead
- `dd33d31` keepalive portable relaunch (was Windows-only; proven with a live crash drill)
- `d10c15c` ML-071 anti-wedge: full book + zero teachable positions → unwind oldest (learning-phase, dry-run only)
- `03416fc` pyright back to baseline (10 type regressions fixed)

**Continuity (the "phone sessions are forgotten" fix)**
- `d085dfc` session bundles: `session_export.py` / `session_import.py` — checksummed, audit-verified, schema-gated, idempotent
- `aa049ac` SessionStart hook auto-restores learning before any work + `meta_model.json` travels copy-if-absent
- `5e54be5` Windows home runbook in `docs/PHONE_SESSIONS.md`

**Learning quality**
- `a680c8b` **candle integrity — the big bug**: all 3 venues fed the still-forming candle into an append-only cache (frozen mid-bar highs/lows → biased triple-barrier labels, crushed vol inputs). Fixed at feed boundary; committed bars only; daily regime path deliberately unchanged
- `1e5e618` candlestick formations as features: engulfing / hammer / marubozu (schema 43→46)
- `b907ce7` **side-relative encoding (v2)**: 14 signed features × direction — the label's frame; the linear ladder baseline can use them day one; migration *derived* (not padded) all rows
- `2ebac2b` **context + THALES block (v3, 53 features)**: regime_age, funding_dist (8h clock), venue_disloc_dir, and the 4 THALES detector scores as model-weighed features (influence-ladder rung 3, operator-approved)
- `9a51307` THALES counterfactual exposure join in `thales_report.py` (promotion evidence: exposed-vs-unexposed trade outcomes)
- `1002a26` persistent lifetime cycle counter (per-process `cycle` still resets by design — that's the restart tell)

## Learning state

- **22 rows** (10 live fills, 16W/6L; 12 candidate triple-barrier), all on v3 schema, all in the telemetry bundle
- Candidates incubate 8h (96 × 5m bars); post-restart queue refilling — next label wave overnight
- **Gates ahead**: 60 rows → first champion/challenger retrain (deploys only if OOF Brier beats champion); 240 rows → exploration graduates
- **THALES promotion**: TH-013 stop-herding cleared the 30-fire bar (65+); counterfactual still data-starved (needs ≥10 exposed AND ≥10 unexposed rows) — report shows it converging each run
- Purge/embargo, triple-barrier everywhere, timestamp discipline: audited clean

## Doctrines established today

1. All code → `main` via fast-forward; no branch sprawl (2 stale fully-merged branches remain, deletable from PC: `chore/remove-tracked-bytecode`, `claude/bot-startup-deduplication-02e1e8`)
2. Features are model-weighed, never gates (SMC contract extended to formations + THALES)
3. Same-width schema changes bump `FEATURE_SCHEMA_VERSION`; restore paths drop cross-version vectors (dataset purity over row count)
4. Battery re-baselines by density/pinning, never by widening bars
5. Live ledger (`state.json`) never travels between machines; only learning does
6. Sim overrides = short-lived operator tools; organic regimes preferred for learning

## Known issues / footnotes

- `test_artifact_pipeline.py::test_registry_pedigree_survives_path_separator_mismatch` — pre-existing, Windows-only semantics, fails on Linux (untouched)
- moomoo needs the OpenD gateway → home-only; `equity_risk_z` stays neutral in cloud
- 1 pyright error remains: the optional moomoo import (resolves where SDK installed)
- Worker restarts can kill container processes + Claude's schedulers; the hourly tick knows how to rebuild everything (tested twice today, zero data loss)
- Tailscale node in the container is ephemeral; delete `liquiditybot-cloud` from the admin console when it goes dark for good

## Next milestones

1. Home setup (15-min runbook, bottom of `docs/PHONE_SESSIONS.md`)
2. Watch rows climb: 60 = first trained model, then calibrated p(win) → Kelly
3. THALES counterfactual goes green → your one-line promote decision
4. Later feature batches (book slope, vol term ratio, uniqueness weights) — gated by permutation-importance pruning at first retrain
