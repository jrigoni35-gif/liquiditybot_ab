# liquiditybot v2 — institutional hardening

Scenario-to-defense catalog. Each row: what fails, which layer catches
it, where in the code, and what the operator sees.

## Config-time (before any capital is at risk)

| Scenario | Defense | Where | Behavior |
|---|---|---|---|
| Fees understated vs Kraken's real tier — pre-trade gate approves net-losing trades | Config guard: refuses live start below public floor (25/40 bps) unless `pretrade.allow_sub_floor_fees=true` | `core/config_guard.py` | FATAL live, WARN dry-run, alert dispatched |
| `pretrade` and `order_manager` fee sections drift apart — edge gate and PnL ledger disagree | Config guard: cross-section equality check | `core/config_guard.py` | FATAL |
| `starting_capital_usd:0` silently pretends it's live | Config guard: enforces >0 live; dry-run uses $10k paper only | `core/config_guard.py`, `main.LiquidityBot.__init__` | FATAL live |
| Daily-loss limit above hard-stop drawdown — brake trips AFTER parachute | Ladder ordering check | `core/config_guard.py` | FATAL |
| Tier triggers non-increasing or close-pcts absurd | Monotonicity check | `core/config_guard.py` | FATAL / WARN |
| $100 capital × 10% cap = $10 < $25 min ticket — untradeable by construction | Untradeable-ticket warning | `core/config_guard.py` | WARN — you must raise `max_position_size_pct` or add capital |
| Clock skew corrupts nonces and staleness math | Startup self-test vs Kraken `Time` endpoint | `runner.BotRunner.run` | Alert if \|skew\| > 2s |

## Data-plane failure (venue is lying or silent)

| Scenario | Defense | Where |
|---|---|---|
| Kraken stops answering — marks freeze, stops evaluate a dead price | Watchdog stale-data trip (30s warn / 120s critical) | `core/watchdog.Watchdog.evaluate` |
| Kraken mid dislocates >150bps from OKX/Binance.US composite | Venue divergence trip — blocks new entries until they re-agree | `core/watchdog.Watchdog.evaluate` |
| Single anomalous print (fat-finger, feed glitch) fires every stop on the book | Tick quarantine: >8% single-cycle jump holds stop evaluation one cycle, next tick confirms or discards | `core/watchdog.Watchdog.filter_mark` + `main.fast_cycle` |
| Poisoned book / non-finite numbers reaching execution | `clean_book`, `clean_candles`, `safe_float`, `loads_bounded` | `core/sanitize.py` (existing; unchanged) |

## Order-plane failure (something wants to send a bad order)

| Scenario | Defense | Where |
|---|---|---|
| BTC price formatted to 2 decimals — Kraken only accepts 1 → 100% AddOrder rejection | Per-pair precision from `AssetPairs`, static fallback offline | `data/kraken_feed.get_pair_meta`, `execution/order_manager._fmt_price` |
| Order below venue `ordermin` — burns API quota on guaranteed rejects | Pre-flight `ordermin` check | `execution/order_manager.submit` |
| Bug or compromise sends order 500bps off reference | Firewall price collar: entries reject at 100bps, exits clamp at 500bps (never blocked) | `execution/risk_firewall.RiskFirewall.check` |
| Runaway loop or repricing bug machine-guns the exchange | Firewall rate limit: 30/min entries, 2× budget for exits | `execution/risk_firewall.RiskFirewall.check` |
| Duplicate order (double-click / retry storm) | Firewall dupe suppression: 3s window on (pair, side, purpose, price, size) | `execution/risk_firewall.RiskFirewall.check` |
| Notional blows through absolute or equity-relative cap | Firewall notional caps: $25k absolute, 30% equity | `execution/risk_firewall.RiskFirewall.check` |
| Market order accidentally used for an entry | Hard invariant: `ordertype="market"` refused unless `purpose="exit"` | `execution/order_manager.submit` |

## Runtime / process failure (the bot itself dies or misbehaves)

| Scenario | Defense | Where |
|---|---|---|
| Process crash leaves resting limits unmanaged on Kraken | Dead-man switch: Kraken `CancelAllOrdersAfter(60s)`, refreshed every fast cycle at half timeout | `data/kraken_feed.cancel_all_orders_after`, `execution/order_manager.refresh_deadman` |
| Clean shutdown with resting orders / open positions | Runner: `CancelAll` + disarm dead-man + alert if positions left unmanaged | `runner.BotRunner.run` (finally block) |
| Snapshot torn by power loss or bit rot — silent corrupt restore | SHA-256 checksum + `fsync`, `.json.bak` generation, verify on restore, fall back to backup | `core/persistence.StateStore.snapshot/restore/_verify` |
| Snapshot from dry-run loaded into live (or vice versa) | Existing dry-run/live mixing guard | `core/persistence.StateStore.restore` (unchanged) |

## Market-plane failure (the market itself is the tail event)

| Scenario | Defense | Where |
|---|---|---|
| Flash crash — drawdown limit is a level trigger; market rips through faster than any daily brake | Watchdog PnL-velocity breaker: -6% in 15 min latches for 30 min, blocks new entries independent of absolute drawdown | `core/watchdog.Watchdog.evaluate` |
| Book gaps — normal 50bps exit rests forever while the position bleeds | Exit-escalation ladder: each unfilled attempt widens slippage cap ×2 (up to 3%), fourth attempt goes MARKET | `main._submit_exit` |
| Hard-stop drawdown breached (existing) | Flatten all + halt new risk | `main.fast_cycle` (unchanged) |
| Crisis / spoofy liquidity regime (existing) | Blocks new risk; detection defensive only | `regime/*` (unchanged) |

## Account-plane failure (someone or something moved money without the bot)

| Scenario | Defense | Where |
|---|---|---|
| Manual trade, missed fill, wire in/out — internal equity ledger drifts from venue truth | Hourly `TradeBalance` cross-check: drift >2% alerts and blocks new entries. The ledger is never silently "corrected" — hidden adjustments are how small errors become unexplainable ones | `main._check_equity_truth` |
| Withdrawal attempted from bot code | Hard deny list, pre-network | `data/kraken_feed.FORBIDDEN_PRIVATE_ENDPOINTS` (existing) |
| Live orders before operator ready | ARM LIVE phrase gate + `live_armed` not persisted (existing) | `runner.handle_command`, `main._live_order_allowed` (unchanged) |

## Operator-visibility failure (something breaks and nobody knows)

| Scenario | Defense | Where |
|---|---|---|
| Any critical event (halts, watchdog trips, equity drift, dead-man failure, config fatal, clock skew, shutdown-with-positions) | Alert sink: rate-limited webhook (Slack/Discord/Mattermost-compatible), threaded so it never blocks; disabled by default, always logs regardless | `core/alerts.AlertSink` |

Set `alerts.enabled=true` and `alerts.webhook_url` to receive them out of band.

## What's still on the operator

- API-key hygiene (trade + query only, no withdrawal — defense in depth behind the deny list).
- Host security (anyone with write on `outputs/control/` sends commands).
- Dependency drift (`pip-audit -r requirements.txt` periodically).
- Fee tier changes (update `pretrade.maker_fee_bps` / `taker_fee_bps` when your Kraken volume tier moves).
