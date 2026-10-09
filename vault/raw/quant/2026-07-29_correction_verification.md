# Adversarial verification of the 2026-07-29 correction waves

Operator ask: "go over all the earlier corrections with systematic-
debugging as well." Three independent fresh-eyed verifiers, one per wave
group, each instructed to REFUTE (full tables in the session scratchpad;
verdicts and dispositions preserved here).

## Verdicts

| Wave | Scope | Verdict |
|---|---|---|
| 1 (`1cda426`) | CVaR bar clock, payoff compounding, exp_alpha, vol_regime gate, label mirrors, bootstrap neutrals, calibrate_fills | 8/9 CONFIRMED-GOOD, 1 SUSPECT (below) |
| 2+3 (`24c8aa7`, `f877de0`) | Parkinson RMS, DSR quantiles+ddof, ZMA subsample, slip tuples/dust guard, liveness instrument | 5/5 CONFIRMED-GOOD, 2 observations (below) |
| 4+5 (`faa792b`, `ce12da4`) | PT-060 seniority, log hygiene, ML-083, THALES A-1/A-2/A-3/B-2/B-1b, floor withhold | 5/6 CONFIRMED-GOOD, 1 SUSPECT (below) |

Highlights of what was independently re-derived: payoff math to 1e-12
(b_net 0.44877 / breakeven 0.69024); CVaR anchor-return exactness under
a 47s poll stall; Parkinson Jensen removal on planted GBM (0.919→0.963,
residual = disclosed discrete-monitoring bias); `_norm_ppf` ≤5e-7 vs
known quantiles; spoof cadence invariance incl. burst-poll bound; probe
floor-withhold dies as an explicit SZ-042 veto with OM-013 backstop.

## Findings fixed same-day (commit follows this doc)

1. **ML-083 was fail-closed but likely INEFFECTIVE** (wave-4/5 SUSPECT):
   `should_deploy`'s no-champion disjunct frees the coin bar only when
   the badge is ≥ 0.25; the live era-orphaned badge is 0.1237 (measured
   on the dead 0.169-base population), so challengers on the new
   0.30-base corpus (naive base-rate Brier ~0.21) still lost to a ghost.
   Fix: `should_deploy(..., ignore_champion=True)` from the ML-083
   branch — badge set aside entirely (ML-076 ghost-badge doctrine; a
   cross-base-rate Brier is exactly what the like-for-like gate refuses
   to compare), true cold-start standard applied (< 0.25 +
   deploy_min_oof). Pinned in tests/test_champion_compare.py.
2. **`slip_bps_notional_weighted` never reached Grafana** (wave-2/3):
   missing from gc_pusher's order_manager whitelist — the Cochran
   ratio estimator was invisible while the dust-skewed simple mean kept
   the panel. Exported + added to the Execution board slippage panel.
3. **`cvar.bar_sec` had zero config_guard coverage** (wave-1): FATAL
   outside [60, 1800]s, WARN ≠ 300 (baseline divergence). Pinned in
   tests/test_protocols.py.
4. Comment-truth fixes: exp_alpha "shipped b>1" (post-payoff-fix b≈0.92,
   the exact form is now the conservative one); order_manager
   zero-notional dust wording; suppress_pt060 one-cycle give-back-mask
   corner documented at the seam.

## Accepted / consciously deferred

- **CVaR post-restart warmup ~10h** (wave-1 SUSPECT): the bar-return
  window is not persisted, so RP-040 runs loose for min_obs=120 bars
  after a restart. This was the conscious ship-time adjudication ("10h
  honest warmup"); making it shorter requires persisting the return
  deque (snapshot schema migration) — queued as a follow-up, not rushed.
- **≤25s give-back mask during the resting-maker PT-060 deferral**
  (wave-4/5 note): bounded to one maker rest, hard stop stays live —
  documented at the seam, accepted.
- PT-060-before-give-back ordering: verified same-price marketable
  closes either way — no better-price loss exists.

## Grafana Cloud FREE-tier compatibility audit (operator downgraded)

- Panels: 100% core types (stat/timeseries/gauge/bargauge/table/text/
  piechart/row) + 6 Business Text panels (`marcusolsson-dynamictext-
  panel`) — a free, signed community plugin already installed on the
  instance; nothing enterprise/Pro-only anywhere in the four boards.
- Datasources: Prometheus only. No Loki panels, no enterprise sources.
- Time ranges: all boards now-24h — far inside the 14-day free metric
  retention.
- Active series: structural count ≈ 600–800 (≈25 per-asset names × 12
  assets + ~90 globals + skimmer/markout/thales/code tallies) — under
  10% of the 10k free-tier series allowance, including the new
  reliability series.
- Push cadence: GC_PERIOD_SEC default 30s meant 2 datapoints/minute —
  double the free tier's 1-DPM metering for zero benefit (boards refresh
  at 1m). Default now 60s; the PC can override via env if ever needed.
- Import path unchanged: `GRAFANA_SA_TOKEN=glsa_... python
  scripts/grafana_import.py` (service-account token, Editor role — free
  tier supports service accounts).
