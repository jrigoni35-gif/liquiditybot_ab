# liquiditybot v2

Regime-aware liquidity trading system. OKX + Binance.US as public read-only data
sources, Kraken as the only execution venue. v1's 5-gate signal engine,
4-tier profit taking and capital management remain; v2 adds macro regime
detection (HMM + momentum), Avellaneda-Stoikov limit-order execution,
inventory/leverage governance, meta-labeled ML sizing, spoof-aware
liquidity regimes, β-weighted hedging, and a free multi-source sentiment layer
(Google News per tracked CEO/figure, crypto news RSS, Reddit) plus
Fear&Greed/CoinGecko context and optional moomoo equities — all feeding a
narrative filter that cannot trigger trades. Full design: `docs/ARCHITECTURE_V2.md`.

## Architecture: engine / runner

Two separate processes, connected only through files in `outputs/`
(all writes atomic). Out-of-process consumers can never block or crash
the trading loop.

```text
main.py         engine     loop-free; exposes cycle_once()
runner.py       runner     the ONLY loop; consumes control commands,
                           writes status.json + equity.csv each cycle
```

Observability is **Grafana Cloud** (a telemetry sidecar reads the files
and pushes metrics + logs); control is the **git remote-control plane**
(`outputs/control/` command files). The legacy Streamlit operator
dashboard has been retired.

## Quickstart — two commands

Windows:

```bat
install.bat     REM one-time: venv + all dependencies + verify
start.bat       REM run the bot (own window)
```

macOS / Linux:

```bash
./install.sh    # one-time: venv + all dependencies + verify
./start.sh      # run the bot (background)
```

`stop.bat` / `./stop.sh` stops the bot cleanly (snapshot, dead-man
cancel of resting orders, loop exit between cycles). Everything starts
in DRY RUN — paper trading; no real orders can be placed until you set
`dry_run:false` in config.json, restart, AND type the ARM phrase
(`ARM LIVE`) at the PC console.

## Run (manual, equivalent)

```bash
pip install -r requirements.txt       # bot dependencies
python scripts/smoke_test.py          # 220 checks, no network

python runner.py                      # the bot
```

`python main.py` still works (delegates to the runner). Flags:
`--config path`, `--fresh` (wipe saved state), `--paused` (start paused,
control it from the git remote-control plane).

## Control commands

Sent by the git remote-control plane, or by hand — drop JSON into `outputs/control/`:

```bash
python -c "from core.runtime import ControlChannel; ControlChannel().send('pause')"
```

start · pause · stop · step (run exactly one cycle) · snapshot ·
entries_on/entries_off (new-risk kill switch; exits always run) ·
flatten_all · arm_live {confirm:"ARM LIVE"} · disarm_live ·
force_dry (one-way LIVE→DRY: seals bot AND order-manager flags, disarms;
there is no command in the other direction — live again means config
`dry_run:false` + restart + typed ARM phrase) ·
sim_price_shock {asset,pct,cycles} · sim_force_fear {cycles} ·
sim_force_regime {asset,label,cycles} · sim_clear (sim_* dry-run only).

### Remote control (one-bot)

The always-on PC is THE bot; any other machine with repo access is a
console. Commands travel over the `paper-telemetry` branch — no open
ports on the PC (`scripts/remote_control.py`; supervisor polls every
`LB_REMOTE_CMD_POLL_SEC`, default 120s, and publishes the full
status.json back as `control/pc_status.json` every `LB_STATUS_PUSH_SEC`,
default 600s):

```bash
python scripts/remote_control.py --send pause          # from any console
python scripts/remote_control.py --send force_dry
```

Remote whitelist: pause · start · stop · entries_on · entries_off ·
force_dry · flatten_all · snapshot · disarm_live. `arm_live` is excluded
by construction (import-time guard + tests): going live remains config +
restart + the typed ARM phrase at the PC console, never remote. Commands
expire after 30 min and apply exactly once; dispositions log RC-010/011.
Kill switches on the PC: `LB_NO_REMOTE_CMD=1`, `LB_NO_STATUS_PUSH=1`.

## Live-money safety model

Layered, each independent:

1. `system.dry_run: true` (default) — everything simulated.
2. In live config, ALL new orders are blocked until the operator arms
   at the PC console by typing exactly `ARM LIVE`. Disarm is one
   command. Exits are never blocked either way.
3. Withdrawals are impossible at the code level: Withdraw/WalletTransfer
   and every related endpoint is on a hard deny list in the Kraken
   client, before any network call. Use an API key without withdrawal
   rights anyway (defense in depth).
4. A dry-run snapshot never loads into a live session, and vice versa.

## Outputs (standardized)

| file | what |
| --- | --- |
| outputs/status.json | full UI state, rewritten every cycle (atomic) |
| outputs/equity.csv | equity curve, one row / 15s |
| outputs/events.jsonl | every log record, structured `{ts,level,logger,msg}` |
| outputs/state.json | pause/resume snapshot (every 30s + every fill + shutdown) |
| outputs/signal_history.csv | labeled training rows (`live` + `candidate`) |
| outputs/postmortems/*.md, postmortem_summary.csv | EV-miss reports |
| outputs/retrain_requested.flag | monitor's retrain request |

## Scripting inputs — effective deep learning

Everything the learning stack consumes, and the knobs that matter:

* **Data volume** — rows accrue from every closed trade (`source=live`)
  and every gate-confirmed candidate, taken or vetoed, labeled by
  triple-barrier (`source=candidate`). More dry-run hours = more rows.
  `ml.max_open_candidates` caps in-flight candidates.
* **`python scripts/train_meta.py [--config path] [--bootstrap]`** —
  trains logistic + MLP under purged walk-forward, fits isotonic
  calibration on out-of-fold predictions, saves to `ml.model_path`.
  Needs ≥60 rows minimum; ≥`ml.min_train_rows` (150) before live rows
  replace bootstrap. `--bootstrap` forces EMA-cross pseudo-labels from
  OKX candles (weak prior; requires network).
* **Labels** — `ml.label_max_bars` is the triple-barrier vertical, counted
  in 5m bars, so the horizon is always `label_max_bars × 5m`. Read the
  number out of `config.json`, never out of docs: `config_guard` FATALs
  any value at or above `profit_taking.time_stop.max_bars_no_progress`
  (a vertical past the no-progress scratch is unreachable — the
  2026-07-31 era deadlock), so a stale figure copied from a README
  refuses to start. `label_pt_vol_mult`/`label_sl_vol_mult` are the
  up/down barriers, in vol units.
* **Auto-retrain** — fires when the monitor hits level 2 (or the flag
  exists) AND ≥`ml.monitor.retrain_min_new_rows` (40) new rows accrued,
  cooldown `retrain_cooldown_hours` (12). Challenger deploys only if
  OOF Brier beats champion by `challenger_brier_margin`.
* **Runtime behavior** — `ml.cold_start_prior_p`,
  `probability_shrinkage`, and the monitor's bounded overrides
  (shrinkage_max, kelly_mult_min, edge_ratio_bump_max, stop_widen_max).
* **Sample weighting** — training rows decay with age
  (`ml.sample_weights.half_life_days`, 30d) and candidate rows are
  down-weighted vs real fills (`candidate_weight` 0.4). The model
  tracks the current market, not ancient history.
* **Ensemble** — the MLP candidate is `ml.ensemble_seeds` (3) nets on
  different seeds, probability-averaged: pure variance reduction at
  small sample sizes. Still must beat the logistic baseline to deploy.
* **Feature importance** — every training run measures permutation
  importance on a true out-of-sample fold (which features, when
  shuffled, actually cost AUC) — printed and stored in the model JSON.
* **Input drift (leading indicator)** — recent live feature
  distributions are compared to the training deciles via PSI. When
  >30% of features shift past PSI 0.25, a retrain fires *before*
  outcome metrics can degrade (outcomes lag by the label horizon).
* **`python scripts/glass_console.py [--open] [--loop SEC]`** — renders
  the liquid-glass operator console (`outputs/console.html`) from the
  shared state files; presentation layer only, SAFE class (Grafana
  remains the pager/history). `--loop` re-renders every SEC seconds in
  the foreground; **Ctrl-C is the documented exit**. The page
  self-reloads each minute; fresh data appears when a render runs.

## Replay backtesting & parameter sweeps

Bar-based backtesters can't validate this bot - the edge lives in
order-book microstructure candles don't contain. Instead: record real
sessions, replay them through the unmodified engine.

```bash
# 1. record: set "system.record_feeds": true, run the bot for hours
# 2. replay the exact session through the real engine:
python scripts/replay.py --recording outputs/recordings/session_X.jsonl
# 3. with overrides:
python scripts/replay.py --recording ... --set position_sizer.min_p_win=0.60
# 4. sensitivity sweep (every combo = one full deterministic replay):
python scripts/sweep.py --recording outputs/recordings/session_X.jsonl \
  --grid "position_sizer.min_p_win=0.52,0.55,0.60" \
  --grid "risk.stop_vol_mult=3,4,5"
```

Two replays of one recording are byte-identical (seeded fills,
loop-free engine). Use sweeps for sensitivity - does the edge survive a
knob moving? - not for crowning one lucky combo; that's curve-fitting.
Sentiment/webdata/moomoo are neutral during replay (their live values
aren't in the frames).

* **`python scripts/smoke_test.py`** — full offline verification; run
  after any config or code change.

## Security

Audited with bandit + pip-audit + manual threat-model review:
**0 static-analysis issues, 0 known dependency CVEs; suites: 5524 pytest + 220 smoke + 47 assurance checks.**
The primary attack surface is untrusted inbound *data*. All external feed
data — exchange books/candles and web/RSS/JSON — is sanitized at the
boundary: non-finite numbers (NaN/Inf) rejected, poisoned/crossed order
books dropped, RSS parsed with defusedxml (entity-bomb-proof), responses
size-capped. Withdrawals are blocked at the code level (endpoint deny
list, pre-network). Full report: `docs/SECURITY_AUDIT.md`. Re-run:
`bandit -c pyproject.toml -r . -x ./.venv,./tests`.

Two surfaces are **not** pure-data and are worth knowing before you widen
anything:

* **`api_server.rest` / `api_server.grpc` both ship `enabled: false`.**
  When enabled they bind 127.0.0.1 only, never expose `arm_live`, and
  `/control` requires `Content-Type: application/json` plus a same-origin
  Origin/Referer/Sec-Fetch-Site — loopback binding alone is *not* a
  defence against a browser, since every page the operator opens can
  reach 127.0.0.1. Set `auth_token` (mirrored by gRPC's `x-auth-token`
  metadata) before enabling either.
* **Imported session bundles are untrusted input.** `scripts/corpus_sync.py`
  runs `session_import --apply` unattended against the telemetry branch,
  so the manifest's `label` and `files` keys are allow-listed to bare
  basenames before they are ever used as paths; a bundle that fails that
  check is refused with exit 4 (never partially applied).

## Setup

### Quick install

```bash
python -m venv .venv
# Windows:  .venv\Scripts\activate      Linux/macOS:  source .venv/bin/activate
pip install -r requirements.txt
python scripts/smoke_test.py        # 220 checks, no network needed
```

### What gets installed, and why

**Required — the engine will not start without these** (all in `requirements.txt`):

* **Python 3.11+** — the codebase uses modern typing (`X | None`) and stdlib features. Tested on 3.14.
* **requests** (`>=2.31.0`) — HTTP client for public market data and REST calls.
* **numpy** (`>=1.26`) — every quant path: signals, position sizing, the ML models, and the HMM macro-regime detector.
* **defusedxml** (`>=0.7`) — hardened XML/RSS parsing for untrusted sentiment feeds (blocks entity-expansion attacks).

**Optional feature dependencies — the bot degrades gracefully (one warning, keeps running) if any are absent:**

* **ccxt** — multi-exchange crypto data feeds (`data/ccxt_feed.py`). Install with `pip install ccxt`. Absent → that feed disables itself.
* **moomoo-api** — read-only equities/macro context via a local moomoo OpenD gateway (`data/moomoo_feed.py`). Install with `pip install moomoo-api`.
* **grpcio** + **grpcio-tools** — optional gRPC control surface (`api/grpc_server.py`). The REST surface works without them. Install with `pip install grpcio grpcio-tools`, then generate the stubs (see below).
* **torch** — only if you later slot in PyTorch sequence models; the default models are pure-numpy and need nothing extra.

**Development / testing:**

* **pytest** — runs the suite in `tests/`. Install with `pip install pytest`, then `pytest -q`.

One-liner for all optional extras:

```bash
pip install ccxt moomoo-api grpcio grpcio-tools pytest
```

### gRPC stubs (only if you use the gRPC surface)

The generated protobuf modules are not checked in. Generate them after installing `grpcio-tools`:

```bash
python -m grpc_tools.protoc -I api --python_out=api --grpc_python_out=api api/liquiditybot.proto
```

`api/grpc_server.py` imports these lazily and logs a single warning if they're missing, so this step is entirely optional.

### Windows note

If Python aborts at startup with `Fatal Python error: preconfig_init_utf8_mode: invalid PYTHONUTF8`, the `PYTHONUTF8` environment variable is set to something other than `0` or `1`. Set `PYTHONUTF8=1` (or clear it). The provided `.vscode/settings.json` already sets it correctly for the integrated terminal.

Edit `config.json`:

* `exchanges.kraken.api_key/api_secret` — trade + query permissions only
  (no withdrawal). OKX/Binance.US stay keyless. `config.json` is
  git-tracked; the feed resolves credentials env-first
  (`api_key_env`, else `KRAKEN_API_KEY`/`KRAKEN_API_SECRET`, else the
  literal), but the live-start config guard reads the config dict only —
  see README_WINDOWS.md "Live trading" for that asymmetry.
* `pretrade.maker_fee_bps / taker_fee_bps` — set to your actual Kraken tier.
* `capital_management.starting_capital_usd`.

Run:

```bash
python main.py                      # dry_run: true by default
python main.py --fresh              # ignore saved state, start clean
```

## Pause / resume

Ctrl+C pauses: a final snapshot of positions, resting orders, balances,
and pending training labels is written to `outputs/state.json` (also
saved every 30s and after every fill). `python main.py` resumes from it
automatically. Live-mode resume reconciles restored resting orders
through Kraken QueryOrders - fills that happened while the bot was down
are applied as normal fill events - and cross-checks local positions
against account balances, warning on mismatch. A paper snapshot will
never load into a live session (and vice versa).

A snapshot saved before the probe throttle's admissions tracking shipped
restores to an empty exploration-probe window by design (up to
`probe_share_window` unthrottled probes before the share cap re-binds).
Newer snapshots round-trip the window faithfully instead, so if probe
admissions look frozen, the drought floor (SZ-048) is the sanctioned way
out - not a restart.

## Going live — in order

1. Run `dry_run: true` for at least a few weeks. The dry-run path uses the
   identical order state machine against real books with simulated fills.
2. Watch `outputs/signal_history.csv` accumulate labeled trades; retrain
   with `python scripts/train_meta.py` once past `ml.min_train_rows`.
3. Flip `dry_run: false` with small capital. Leave `leverage.use_margin`
   at `false` (hard 1x) until the spot behavior has earned trust.
4. Sentiment/web context is ON by default and needs no keys: tracked
   figures via Google News RSS (edit `sentiment.figures`), crypto news
   RSS, Reddit, CoinGecko, and the Fear & Greed index. Optional moomoo
   equities context: install `moomoo-api`, run the OpenD gateway, set
   `moomoo.enabled: true`. Everything degrades to neutral if a source
   dies — the loop never depends on them.

## Safety properties

* Entries are post-only limits priced by the AS quoter; exits are
  slippage-capped marketable limits that bypass the edge gate (risk
  reduction is never blocked).
* Hard stops are vol- and regime-scaled and enforced every 5s cycle.
* Inventory: soft cap blocks same-side adds, hard cap forces reduction,
  stale losers with the regime against them are purged.
* Crisis regime (vol/turbulence spike) blocks all new entries immediately.
* Spoofy liquidity regime blocks new risk; detection is defensive only.
* Fear narratives without structural confirmation are ignored by design.
* v1 hard-stop drawdown halt still rules everything: breach flattens the
  book and stops new risk.

## Institutional hardening (added)

Layered defenses against the "expect the unexpected" class of failure.
Each row is a real-world failure mode caught somewhere in the stack;
full catalog in `docs/HARDENING.md`.

* **Config guard** — refuses live start on sub-floor fees, mismatched
  fee sections, unset live capital, misordered risk ladder, non-
  monotonic tiers. Warns on untradeable-by-construction sizing (e.g.
  $100 capital × 10% cap = $10 < $25 min ticket).
* **Watchdog** — stale-data trip (30s warn / 120s critical + alert),
  cross-venue divergence trip (>150bps between Kraken and OKX/BinanceUS
  composite), PnL-velocity circuit breaker (-6% in 15min latches new
  entries off for 30min), single-tick quarantine (>8% jump holds stops
  one cycle for confirmation).
* **Risk firewall** — independent last-line checks on EVERY submitted
  order: price collar (100bps entries reject / 500bps exits clamp),
  notional caps ($25k absolute, 30% equity), per-minute rate limit,
  duplicate suppression. In the spirit of SEC 15c3-5.
* **Dead-man's switch** — Kraken `CancelAllOrdersAfter(60s)` refreshed
  every fast cycle. Process death → resting orders die with it. Clean
  shutdown cancels every venue order and disarms the timer.
* **Exit-escalation ladder** — an unfilled exit doubles its slippage
  cap on each retry (up to 3%); after three failed attempts it goes
  MARKET. In a gapping book, being out at a bad price beats being
  trapped at a good one.
* **Venue precision** — per-pair `AssetPairs` metadata: BTC/USD orders
  format to 1 decimal (previous hardcoded 2 → guaranteed venue reject).
  Below-`ordermin` orders skipped pre-flight. Market orders refused for
  entries as a hard invariant.
* **Snapshot integrity** — SHA-256 checksum + `fsync` + `.json.bak`
  generation. Corrupt primary falls back to backup automatically.
* **Equity truth sync (live)** — hourly `TradeBalance` cross-check.
  Drift >2% between internal ledger and venue alerts and blocks new
  entries. The ledger is never silently corrected.
* **Alert sink** — rate-limited webhook (Slack/Discord/Mattermost
  compatible) for critical events. Disabled by default; set
  `alerts.enabled=true` and `alerts.webhook_url` to receive them.

Fees ship as **25 bps maker / 40 bps taker** (Kraken spot public floor).
If your real tier is lower, set both `pretrade.*` and
`order_manager.*` fee fields consistently and set
`pretrade.allow_sub_floor_fees=true`. Starting capital ships as **$100**
so config_guard's untradeable-sizing warning fires immediately in
dry-run — raise it before there's any point going live.

No profitability is guaranteed or implied. Crypto trading with leverage
can lose more than the capital committed.
