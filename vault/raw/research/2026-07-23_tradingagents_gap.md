# Adoption Ledger — TradingAgents v0.3.1 vs liquiditybot

*Synthesis over four subsystem audits (orchestration, data, risk/decision, eval/ops), reconciled against CLAUDE.md invariants 1-7, the 2026-07-23 whole-code audit (W1/W2), and the shipped profitability program + #103. Nothing already shipped is re-proposed.*

## 1. Verdict (operator plain-language)

TradingAgents is an **LLM research scaffold**: a LangGraph graph (`trading_graph.py:65-150`) that runs a pipeline of language-model calls — analysts, a bull/bear debate, a three-persona risk debate, a portfolio-manager verdict — and emits a five-word rating plus prose, with a Reflexion-style markdown memory (`agents/utils/memory.py`) fed back as few-shot context. Its own README (`README.md:292`) disclaims it as "not a strategy with a fixed, replicable return." **liquiditybot is a deterministic, cost-aware execution engine.** Every mechanism in TA that produces a *number* (cost, slippage, EV, Kelly fraction, drawdown throttle, leverage headroom), liquiditybot already computes deterministically, replayably, and overfit-audited; TA produces none of them — it produces text. liquiditybot is strictly ahead on: risk math, execution-cost modeling, evaluation rigor (OF-1..7 + G1-G5 vs *zero* backtest statistics in TA), look-ahead safety, and auditability. TA is ahead on **exactly one thing worth having**: a human-legible, per-decision "what did I decide and how did it turn out" narrative loop — and only offline, never in the engine. The entire adoptable surface is reporting and dev-process; the entire live-decision surface is either something we do better or the LLM-in-engine architecture CLAUDE.md forbids.

## 2. ADOPT (offline / advisory / dev-process only) — ranked by net value

**A1 — Per-decision outcome ledger + lessons digest (one script family).** *Highest value.*
- **What**: a read-only `scripts/lessons_digest.py` (plus a per-decision `scripts/decision_ledger.py` view) that joins already-audited dispositions to their realized outcome and aggregates per asset/regime.
- **Why**: TA's `memory.py:70-95` `get_past_context` exists to brief the *next decision-maker*; its inline outcome-tag schema `[date|ticker|rating|raw%|alpha%|Nd]` + `REFLECTION:` (`memory.py:160-216`, atomic tmp+`os.replace`) is a genuinely clean legibility pattern. liquiditybot has all the *inputs* — hash-chained audit (`core/audit.py:46-172`), postmortem taxonomy + CSV (`ml/postmortem.py`, `outputs/postmortem_summary.csv`), goals ledger RP-071 (`core/goals.py:22-79`), monitor cause tallies (`ml/monitor.py:377-393`), replay/recording (`data/recording.py`, `data/replay.py`) — but **no single human-readable line-per-decision-with-eventual-outcome view stitched across them.** Grafana glass (shipped #103) shows metric panels, not this ledger.
- **Shape under our law**: new `scripts/`, reads existing JSONL/CSV only, registers **zero** engine state and **zero** new `Code`; never imported by `cycle_once` or any live path; same trust tier as `assurance_check.py`/`overfit_check.py` output. Content is *deterministic templated strings* from the existing enumerable cause taxonomy (`postmortem._attribute:301-327`), not prose. No OF-7 DoF cost (no new feature). Digest per asset/regime: last-N postmortems, dominant cause, current governor level (L0/L1/L2), current goal attainment.

**A2 — StockTwits read-only sentiment feed.** *Medium value, cheap.*
- **What**: `sentiment/stocktwits_feed.py` mirroring the `sentiment/scanner.py:21-25` pattern (injectable `fetch`, degrade-to-empty).
- **Why**: it is the one TA source we genuinely lack — crowd-labeled Bullish/Bearish tags (`stocktwits.py:76-85`), free/keyless like everything in `sentiment/`; TA's symbol fix (`symbol_utils.py:83-101` `crypto_base`) resolves `BTC-USD`→`.X`. Our other crowd sources already outrun TA's 403-degraded Reddit RSS (`scanner.py:98-119` HN Algolia + curated crypto RSS).
- **Shape**: advisory-only, feeds `per_source` into `NarrativeFilter.evaluate` the way `sentiment/fear_filter.py:85-121` already consumes `score`/`fear_spike`. Never touches sizing/direction. No DoF cost if it stays a filter input, not an ML feature. Low priority — three sources already blend.

**A3 — Router-exhaustiveness test idiom.** *Dev-process, cheap.*
- **What**: adopt TA's `tests/test_risk_router_path_map.py:1-82` idiom — assert a dispatch table's *entire return range* ⊆ the handled path map, parametrized over drift/relabeled inputs.
- **Why**: our `data/ws_feed.py:484-538` router is already this defensive (`tests/test_ws_feed.py:103,308`), but the idiom is a cheap standing guard for any *future* dispatch table (e.g. if `execution/routing.py` or a venue-adapter dispatch grows branches — cf. invariant #3).
- **Shape**: test-only, no engine change.

**A4 — Curated FRED macro as structural-stress input (2-3 series only).** *Medium value, real DoF risk — guard hard.*
- **What**: `data/macro_feed.py` mirroring `data/webdata_feed.py` exactly (injectable `fetch`, `poll_minutes≈360`, degrade-to-last-snapshot, `available` flag), exposing **fed funds, 10y-2y spread, VIX** as a `MacroSnapshot`.
- **Why**: our regime layer (`regime/` HMM/TSMOM) is price/microstructure-only — no rates, no yield curve; crypto has documented macro-liquidity sensitivity pure HMM sees only *after* the fact. TA's `fred.py:37-72` proves the plumbing.
- **Shape / overfit**: consume as a **slow structural-stress confirmation** the way `moomoo_feed.py`'s `risk_z` feeds `StructuralInputs.risk_asset_z` (`fear_filter.py:36-43`) — never a signal generator, gate, or sizer input. **OF-7 cost is real**: `overfit_check.py:532-558` gates `rows_per_feature≥10`; the full 18-series `MACRO_SERIES` is rejected outright (monthly CPI is stale ~8,928 cycles → `dead_feature_frac` flag, `overfit_check.py:547-558`). Even the 3 chosen series, *if* used as ML features rather than a structural gate, must clear OF-7 DoF and OF-4 plateau, and be config-lifted with `config_guard` bounds (no fitted literals). Default to structural-input-only; ML-feature use is a separate, gated decision.

## 3. ADAPT (concept transfers, implementation does not)

- **Reflexion memory → deterministic digest.** TA reinjects free-text lessons into the *next LLM prompt* (`portfolio_manager.py:35-40`). We already do the *structurally superior* version numerically — `postmortem.MITIGATIONS:61-97` maps each enumerable cause to a config knob, bounded/decaying into `monitor._apply_cause_adjustments`. Adapt only the **"brief the next decision-maker"** framing → the A1 human digest, never prompt-reinjection, never engine-consumed.
- **LLM post-hoc narration (`reflection.py:31-57`, RISK-report `narrate_ledger` idea) → templated narration.** Keep the *human-readable* commentary; drop the LLM. Generate A1's lines from deterministic string templates over registered reason codes. **Any** LLM-derived multiplier/rating/adjustment touching sizing/gates/exits is REJECT, not ADAPT (invariants 1-7).
- **Inline outcome-tag schema (`memory.py` `[…|raw%|alpha%|Nd]`) → ledger line format.** Adopt the *shape* (one resolved line per decision) for A1; our fields are `reason_code | realized_pnl | exit_reason | holding_bars`, joined from audit + replay, cost-inclusive (unlike TA's cost-blind `raw-bench`).
- **Checkpoint run-signature (`_run_signature`, `trading_graph.py:348-360`) → we already have the analog.** Snapshot generations + per-section restore isolation (W1-3/W1-4, fixed) solve our crash-recovery. Standing pattern, not new work — see §6.

## 4. REJECT (one line each)

- **LangGraph StateGraph / graph engine** (`trading_graph.py:65-150`) — LLM-in-engine; nothing to schedule (invariant: no LLM in `cycle_once`).
- **Bull/bear debate** (`conditional_logic.py:52-61`, string-concat transcripts) — bare counter, no stopping rule, temperature-dependent → un-testable, un-replayable.
- **Three-persona risk debate** (`risk_mgmt/*_debator.py:39`) — zero numeric output (grep: no kelly/cvar/var/leverage); talk-to-quota, not risk math.
- **PM verdict / 5-tier over/underweight rating** (`schemas.py:44-51,197-202`) — ordinal < continuous `p_win`; feeding Kelly needs an invented bucket→prob literal = overfit violation.
- **Soft structured-output schemas** (`structured.py:49-79` silent free-text fallback) — we enforce via types + pyright@0; TA's own `signal_processing.py:1-31` de-LLM'd its parser, validating *our* stance.
- **SqliteSaver checkpointer** (`checkpointer.py:28-38`) — solves multi-turn generative resume; our engine is single-shot/deterministic.
- **yfinance CSV cache** (`stockstats_utils.py:141-181`) — memoizes one date-ranged vendor call; we live-poll every cycle.
- **`route_to_vendor` fallback chain** (`interface.py:168-262`) — wrong shape; our read-only feeds combine concurrently (`strategies/liquidity_model.py`), fail-closed per-venue (`okx_feed.py:43-57`).
- **Look-ahead cutoff-filter pattern** (`alpha_vantage_fundamentals.py:6-27`) — patch for a bug class our venue-truth boundary flags (`sanitize.drop_forming_candles:200-226`) + FIFO replay + purged CV don't have.
- **Polymarket** (`polymarket.py:68-139`) — thin crypto coverage (its own docstring), no 5-min-cycle mapping; advisory-text-only at best.
- **Full 18-series FRED as ML features** — DoF burn / dead-feature (see A4).
- **LLM retry budget** (`llm_max_retries`) — no LLM in engine; our `ws_feed._backoff_delay:143-161` is the equivalent, already present.
- **"Alpha benchmark"** (`_fetch_returns:251-294`) — single-trade `raw-bench`, cost-blind, n=1; not an evaluation methodology.

## 5. ALREADY AHEAD (do not envy)

- **Deterministic step-able engine** (`main.py:cycle_once`) vs stochastic LLM graph.
- **Risk math**: CVaR/gap/budget/heat with fail-closed vetoes (`risk/protocols.py:133-333`, same code Monte-Carlo'd by `quant_trials.py`) + cost-adjusted fractional Kelly, drawdown throttle, vol scalar, Avellaneda-Stoikov skew, leverage governor (`position_sizer.py:279-378`, `leverage.py`) vs a prose sentence.
- **Decision-time cost modeling**: maker/taker fee, book-walk slippage, sqrt-impact, Glosten-Milgrom adverse-selection, mandatory exit-leg re-pricing, fill-prob-weighted EV (`execution/pretrade.py:105-327`) vs **nothing** in TA.
- **Evaluation rigor**: OF-1..7 + PBO-on-deployed-rule + DSR (`overfit_check.py:479-558`) + G1-G5 (`quant_trials.py`) + replay-gate fidelity vs zero backtest statistics.
- **Postmortem → bounded numeric mitigation** (`postmortem.py`, `monitor._apply_cause_adjustments`) vs free-prose "hope the LLM reads the paragraph."
- **Look-ahead safety**: venue committed-boundary flags (`kraken_feed:313-323`/`okx_feed:113-121`) + label-span-purged walk-forward (`ml/overfit.py`, `ml/history.py:573-574`) vs manual wall-clock date clips.
- **Auditability**: hash-chained JSONL + registered reason codes (`core/codes.py`, invariant #6) vs soft schema.
- **Crypto-native context**: Fear&Greed + BTC-dominance (`data/webdata_feed.py:55-140`) vs none.
- **Restore isolation** already fixed per-section (W1-3/W1-4, `tests/test_restore_isolation.py`); **config_guard FATALs** on incoherent combos vs TA's silent config no-ops (#764/#788).

## 6. Self-check teachings — concrete re-verify items (their bug classes → ours)

Cheap, read-only checks; none are code changes on their own:

1. **JSON-string-treated-as-parsed look-ahead** (TA #1115: `isinstance(dict)` guard no-op'd a JSON *string* payload). **Check**: grep `data/` for any `if isinstance(x, dict)` guard that gates a filter/cutoff on a field that could arrive as a serialized string before parse. Verify none skips silently.
2. **Config read-into-local-then-never-forwarded** (TA #764 `max_recur_limit`; #788 sub-dict leak between runs). **Check**: W2-7 already aligned ~8 `.get()` defaults to `config.json`; residual sweep of `config.json` keys vs read-sites for any declared-but-unconsumed knob outside `config_guard`'s exhaustiveness.
3. **Resume identity not keyed on all state-shape** (TA #1089). **Standing pattern**: any *future* multi-subsystem restore/dispatch must use W1-3/W1-4 per-section isolation + a shape signature; confirm on next persistence change.
4. **Dispatch path-map not covering full return range** (TA #1088). **Adopt A3** for future dispatch tables (`execution/routing.py`, venue-adapter dispatch); `ws_feed.handle` already conforms.
5. **Undated-record kept-live-but-dropped-in-window** (TA #992/1007). **Check**: our intentional keep-forming-daily-bar (`kraken_feed:325-330`, `okx_feed:123-128`) is safe *only* because it's live-only + FIFO-replayed literally. **Re-verify** the moment this path is ever repurposed for a replay-at-arbitrary-date backtester (it would then reproduce TA's exact bug). Keep the rationale documented at the call site.