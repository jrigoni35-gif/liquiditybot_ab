---
title: Hardening Catalog
category: source
summary: Scenario-to-defense catalog by failure plane, naming what fails, which layer catches it, the exact code location, and what the operator sees
tags: [hardening, failure-modes, thresholds, operations]
sources: 1
updated: 2026-08-01
---

# Hardening Catalog

**Raw source:** `raw/architecture/HARDENING.md`

The operational failure-mode catalog and the **source of truth for concrete thresholds**. Organized by
[[concepts/failure-plane-taxonomy]].

## Config-time
`config_guard` refuses live start with fees below Kraken's public floor (**25/40 bps**); cross-checks
that the `pretrade` and `order_manager` fee sections agree (FATAL); enforces **ladder ordering** — the
daily-loss limit must trip before the hard-stop drawdown ("brake before parachute"); tier-trigger
monotonicity; warns on untradeable tickets. Clock skew self-tested against the venue at startup.

## Data plane
Watchdog stale-data trip (30s warn / 120s critical). **Venue divergence trip** when the Kraken mid
dislocates **>150 bps** from the OKX/Binance.US composite — blocks new entries until re-agreement.
**Tick quarantine** — a >8% single-cycle jump holds stop evaluation one cycle; the next tick confirms
or discards.

## Order plane
Per-pair precision from `AssetPairs` with a static offline fallback (BTC to 2 decimals would be 100%
rejected). Firewall price collar: entries **reject at 100 bps**, exits **clamp at 500 bps, never
blocked**. Rate limit **30/min entries, 2x budget for exits**. Dupe suppression on a 3s window over
(pair, side, purpose, price, size). Notional caps **$25k absolute, 30% equity**.

## Runtime
**Dead-man switch** — venue-side `CancelAllOrdersAfter(60s)` refreshed every fast cycle at half
timeout. Snapshots SHA-256 checksummed and fsynced with a `.bak` generation and fallback on verify
failure. Dry-run/live snapshot mixing guard.

## Market plane
**PnL-velocity breaker** — -6% in 15 min latches for 30 min and blocks new entries **independent of
absolute drawdown** (a flash crash rips through a level trigger). **Exit-escalation ladder** — each
unfilled attempt widens the slippage cap x2 up to 3%; the **fourth attempt goes MARKET**.

## Account plane
Hourly `TradeBalance` cross-check; drift >2% alerts and blocks new entries. **"The ledger is never
silently 'corrected' — hidden adjustments are how small errors become unexplainable ones."**

## Hard rules
`ordertype="market"` refused unless `purpose="exit"`. Exits never blocked by the collar, only clamped.
Withdrawals blocked by a deny list checked **pre-network**. Live orders require the typed `ARM LIVE`
phrase; `live_armed` is **not persisted**.

## Explicitly left to the operator
API-key hygiene (trade + query only, no withdrawal); host security (**anyone with write access to the
control directory sends commands**); dependency drift; manually updating fee config when the venue
volume tier moves.

## Related
[[entities/config-guard]] · [[entities/kraken]] · [[concepts/failure-plane-taxonomy]]
