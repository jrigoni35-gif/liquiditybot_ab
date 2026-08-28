# 04 — FINSABER: Can LLM Trading Agents Outperform Long-Run?

**Citation:** Weixian Waylon Li, Hyeonjun Kim, Mihai Cucuringu, Tiejun
Ma, "Can LLM-based Financial Investing Strategies Outperform the Market
in Long Run?", KDD 2026 Datasets & Benchmarks Track (Oral);
arXiv:2505.07078 (v1 2025-05-11, v6 2026-06-26); code
https://github.com/waylonli/FINSABER. Status: FOUND.

## Core claims

- Reported LLM trading-agent outperformance (FinMem, FinAgent, FinCon)
  is an evaluation artifact: cherry-picked symbols (TSLA/NFLX/AMZN/
  MSFT), short windows (Oct 2022–Apr 2023), survivorship/data-snooping
  bias. Under 20-year, 100+ symbol bias-controlled backtests the
  advantage "deteriorates significantly".
- Buy-and-hold and cheap baselines (ARIMA, rules) frequently beat LLM
  agents risk-adjusted across all four unbiased selection setups.
- Regime asymmetry: LLM strategies over-conservative in bulls,
  over-aggressive in bears (FinMem bull Sharpe −0.19 / bear −0.97 vs
  B&H 0.61 / −0.28).
- Fragile to backbone choice: GPT-4 vs 4o vs 4o-mini "drastically"
  changes results — the strategy is partly an artifact of the model
  snapshot.
- Scaling framework complexity buys no alpha; authors argue for trend
  detection, regime-aware risk controls, and API costs inside the
  performance metric.

## Method

Rolling-window backtests 2004–2024, 7,000+ US equities incl. delisted
S&P 500 constituents (survivorship control), 15.7M news records +
SEC filings; symbol selection via pre-registered unbiased rules
(Random-5, Momentum, Volatility effect, FinCon's own selector); inputs
temporally aligned (look-ahead control); 20-year span as data-snooping
control. Costs: $0.0049/share, $0.99/order min (Moomoo schedule),
risk-free 3%; no slippage model. Regime analysis via bull/bear/sideways
Sharpe stratification.

## Key numbers

- Composite 2004–2024 Random-5 (91 symbols): B&H Sharpe 0.315 / AR
  6.694% / MDD −35.130%; ARIMA 0.255 / 6.928% / −21.691%; FinMem
  −0.253 / −0.094% / −24.243%; FinAgent 0.094 / 4.477% / −28.059%.
- Momentum (84 symbols): ARIMA 0.542 / 13.257% beats FinAgent 0.104
  (AR 13.950%, MDD −20.675%) and FinMem 0.025 / 3.649%; B&H 0.384 /
  9.916%.
- Volatility-effect (63): B&H 0.703 / 7.898% / −14.146%; FinAgent
  0.241 / 4.954%; FinMem −0.228 / 4.061%.
- FinCon-selector (80): B&H 0.389; ARIMA 0.532 / 10.662%.
- Single-stock 2004–2024: FinMem beats B&H only on TSLA (0.641/42.153%
  vs 0.630/37.767%); loses NFLX (0.293 vs 0.622), AMZN (0.188 vs
  0.551), MSFT (0.203 vs 0.461); FinAgent NFLX −0.511.
- Regime Sharpe: FinMem bull −0.19 / bear −0.97; FinAgent 0.12 /
  −0.38; B&H 0.61 / −0.28.

## Limitations

- Authors: traditional baselines NOT re-tuned per window (LLM loss
  margin understated); look-ahead not fully eliminated — LLM training
  corpora overlap 2004–2024 test periods, biasing IN FAVOR of agents,
  which still lose; public data only.
- Extractor: equity daily-bar timing; does not transfer directly to
  intraday crypto liquidity provision (different cost structure, no
  delisting analog, no funding/inventory dynamics). No slippage —
  LLM churn cost understated too. Regime bull/bear Sharpes are
  verbatim narrative text in Section 7 and may be cited as exact
  *(corrected 2026-08-27: page previously understated the source with
  "Regime numbers from a heatmap figure, limited precision")*. No
  purged CV / DSR / PBO — bias control
  is span+breadth+temporal alignment, weaker than our battery on the
  selection-rule axis.

## GAP ANALYSIS

### ALREADY AHEAD

- **Selection-rule axis**: FINSABER has no PBO/DSR/purged CV; our
  battery runs OF-3 CSCV PBO on the deployed rule
  (overfit_check.py:22,800), OF-2 shuffle-null (:794-796), OF-5 DSR
  (:690,722). Cite FINSABER as breadth/span precedent, never
  selection-rule precedent.
- **Effective-n**: FINSABER reports symbol counts (91/84/63/80), not
  overlap-corrected n; `cohort_eval.py:484-531` cohort_effective_n
  already exceeds their standard (POWER-2: n=33 → n_eff=9.92 is the
  live example of why it matters).
- **Cost realism**: their $0.0049/share + $0.99 min with no slippage is
  weaker than the pretrade EV gate's measured round-trip stack
  (core/config_guard.py:600-611, core/codes.py:524) and the POWER-2
  cost-tolerance bar (43/118 bps vs 67.04 booked). Re-cost any
  FINSABER number under our stack before comparing.
- **Pre-registration**: era-4 cohort is pre-registered n=50 with a
  signed three-verdict decision table; FINSABER pre-registers symbol
  selection only.
- **No-LLM-in-the-loop, confirmed**: LLMs here are build-time agents
  only; the decision path is PositionSizer/RiskProtocolStack/
  ProfitTierEngine (CLAUDE.md architecture). FINSABER is the external
  citation for why that rejection stays: LLM timing agents lose to
  B&H and ARIMA over 20 years even before API costs.

### ADOPTABLE

- **Regime-asymmetry diagnostic** (SAFE): replicate
  conservative-in-bull / aggressive-in-bear stratification on our own
  cohort — stratify era-4 trips by regime label (status schema
  `regimes` key; `regime/` module) in a measurement script beside
  `cohort_eval.py`. Measurement only; any resulting sizing/geometry
  change is cohort-resetting and waits for the boundary #6 docket.
  Validation: effective-n reported per stratum, double-derived counts.
- **Backbone-fragility support for agent tiering** (doctrinal): the
  GPT-4/4o/4o-mini result and the API-costs-in-the-metric argument
  directly support USAGE.md rules h–k and the frozen model-side
  stance — complexity scaling bought no alpha in the only 20-year
  controlled test. Vault citation; no code.

### NOT APPLICABLE

- Absolute Sharpe/AR/MDD numbers — equity daily bars under Moomoo
  commissions; not comparable to crypto LP economics without
  re-costing.
- FinMem/FinAgent/FinCon architectures — LLM-in-loop, rejected by
  standing architecture.
- Their news/SEC data plane — no equities here; sentiment gaps are
  already docketed separately (ATTR-1/ATTR-2).

## Standards-compliance table — FINSABER bias controls vs this repo

| FINSABER requirement | our equivalent | status |
|---|---|---|
| Survivorship control (delisted constituents in universe) | No delisting analog in crypto pairs; universe is a fixed 12-asset Kraken set chosen by the operator, not survivorship-filtered from a historical index | **N/A by construction** — but note asset selection predates era-4 and was never bias-audited as a selection |
| Long-span data-snooping control (20 years) | Era-4 window is weeks, n=50 pre-registered trips; span is bought with pre-registration + n_eff instead of calendar length | **PARTIALLY** — pre-registration is the stronger tool per decision, but we cannot claim span; POWER-2 says gross edge is *precisely undetermined* at n_eff 9.92 |
| Unbiased symbol selection (pre-registered rules, no cherry-pick) | Cohort membership is every closed honest-fill trip in the window — no post-hoc symbol filtering; WHY-1's alt-tail vs BTC/ETH split is reported, not selected on | **MET** |
| Temporal alignment / look-ahead control | Deterministic `cycle_once(now)` under injected feeds; walk-forward deployment (`ml/walkforward.py`); OF-6 purge in the battery | **MET** (and stricter: purging, which FINSABER lacks) |
| Multiple-comparison / selection-rule discipline | OF-3 PBO on the DEPLOYED ladder rule, OF-5 DSR, OF-4 plateau — FINSABER itself has none of these | **MET, exceeds source** |
| Realistic transaction costs | Full measured cost stack in the EV gate; POWER-2 cost tolerance 43/118 bps vs 67.04 booked | **PARTIALLY** — stack exists and gates, but FEE-1/FEE-3 (HANDOFF docket) show configured fees ≈ half true Kraken T1 and OM-080 reconciliation has never fired; venue truth unverified until the TradeVolume check |
| API/agent costs inside the performance metric | Agent spend is tiered by operator law (USAGE.md h–m) but NOT logged into any performance ledger | **MISSING** — the 02-paper's adoptable agent-spend ledger is the fix; honest miss |
| Regime-stratified reporting | Regime labels exist (status `regimes`, regime/ module, REG-7/REG-8 docket) but era-4 trip outcomes are not yet stratified by regime | **MISSING** — the adoptable diagnostic above; SAFE to build now |
| Effective-n / overlap correction | cohort_eval.py + gate_truth_report.py report n_eff; FINSABER does not | **MET, exceeds source** |
| Backbone/model-snapshot sensitivity | Deployed model is version-pinned and walk-forward selected; retrain loop continues by design; no cross-backbone sensitivity sweep exists (and is frozen anyway) | **PARTIALLY** — pinning yes, sensitivity analysis no; frozen until readout |
