# Full glass rebuild of the four banner dashboards — design

Date: 2026-07-22 · Status: approved by operator (chat, this date)
Decisions: depth **C — full rebuild** · curation **consolidate, drop
nothing** · approach **rebuild generator in place**.

## Context

The dedicated "Liquid Glass" board (`liquiditybot-glass`) and its mobile
companion were built on a misread of intent: the operator wanted the
Liquid Glass treatment applied to the four banner-linked boards they
already flip through (Command · Models·Inv·Exec · Problem/Solution ·
Screening), not a fifth board. The operator has deleted the mobile board
from Grafana. Five operator screenshots (7/22) also show live defects on
the four boards. This spec retires the accidental boards and re-authors
the four boards in the glass language.

## Invariants (unchanged)

- The four boards stay GENERATOR-OWNED by
  `scripts/build_trading_dashboard.py`; shipped JSON == generator output
  (`tests/test_trading_dashboard.py`). Never hand-edit the JSONs.
- Board uids, titles, nav banner links (`_NAV`), refresh/time ranges,
  non-scaling `prefix:$` dollar unit, and per-panel descriptions keep
  their current semantics.
- Every metric currently queried by a board stays on that board
  (consolidation into denser forms is allowed; deletion is not).
- `noValue` strings pinned by `tests/test_telemetry_restart_coupling.py`
  are preserved verbatim on the rebuilt panels.
- Full CLAUDE.md battery green before ship; JSONs written with
  `ensure_ascii=False`.

## 1 · Cleanup

- Delete `docs/grafana/liquiditybot_glass.json` and
  `docs/grafana/liquiditybot_glass_mobile.json`; remove both from
  `scripts/grafana_import.py` DASHBOARDS.
- Delete uids `liquiditybot-glass` and `liquiditybot-glass-mobile` from
  Grafana Cloud via API (mobile may already 404 — acceptable).
- Rewrite `docs/grafana/README_glass.md`: the glass suite IS the four
  boards; document the Business Text unlock (below).
- Remove any test references to the retired board files.

## 2 · Generator kit (rebuilt in place)

`scripts/build_trading_dashboard.py` keeps its file identity, layout
engine (`_place`/`_flush`/`row`), `_board`/`_links` assembly, and the
Apple palette. Panel helpers become the glass primitives (all proven
rendering on the operator's instance):

- **state_tile** — colorMode background, `textMode: "value"` (title
  names the tile; kills the raw-PromQL-inside-tile defect class).
- **bignum** — big stat, `textMode: "value"`, optional area sparkline.
- **gauge / timeseries** — glass defaults: smooth line, opacity
  gradient, fixed per-series colors from the validated categorical set
  (#5E5CE6 / #2596AB / #BF5AF2; neutral mid #6E6E73).
- **bargauge** — `displayMode: "basic"` + `displayName:
  "${__field.labels.asset}"` (no threshold ramp painted inside bars).
- **piechart donut** — 2-slice composition, entity-fixed teal/purple.
- **joined table** — targets `format: "table"` + `joinByField` on the
  entity label + `filterFieldsByName` include `^(<label>|Value.*)$` +
  `organize` rename. Replaces the `merge` transform everywhere
  (structural fix for split-row / colored-but-empty cells). Absent
  values render quiet (no base-threshold alarm color).
- **CSS injector** — hidden self-hiding text tile per board carrying the
  frosted-glass CSS; `transparent: true` on all panels.

## 3 · Board re-authoring (scope preserved)

- **Command**: VITALS state strip (bot/halted/entries/kraken/telemetry
  age/governor) → MONEY (equity chart, daily/open/weekly P&L, drawdown,
  pools row + pools-over-time) → LEARNING BRAIN (labels-by-source chart,
  Brier trio as ONE comparison chart, model/state tiles, corpus-quality
  tiles) → EDGE (net$/win-rate/trades ranked bars + scorecard joined
  table) → THALES (doc panel + scorecard + ranked bars) → POSITIONS &
  RISK (book joined table, streak/risk tiles, reason-code + gate-weight
  tables).
- **Models·Inv·Exec**: MODEL (model tiles, Brier trio, hit-rate bars,
  signal-quality joined table, gate weights) → INVENTORY (gauges,
  bignums, book table, uPnL bars) → EXECUTION QUALITY (maker/taker
  donut, slippage/reject tiles, mark-out heat table with 5s/30s/60s
  columns).
- **Problem/Solution**: intro text + PROBLEM→SOLUTION framing kept; each
  family (feed, model health, capital/drawdown, integrity/venue) =
  state tiles for states + ONE consolidated joined counter table (or
  ranked bar set) replacing the six-tile fault walls; budget gauges,
  breaker + firewall tables stay (as joined tables).
- **Screening**: skimmer (tiles + score bars + promoted table) →
  tradeability scorecard (joined) → regime & adverse selection
  (spread/vol bars + mark-out table).

## 4 · Defect fixes (from the 7/22 screenshots)

- Live/Candidate labels "No data" → single merged selector
  `liquiditybot_ml_labels{source="…",job="liquiditybot"}`.
- Model tile printing `{kind="blend"}` → `displayName:
  "${__field.labels.kind}"` (renders BLEND).
- Giant "prior" tile / prior-skew "No data" → value-only state tiles +
  honest `noValue` ("no batch yet").
- Mark-out queried by `horizon_sec` (the label `gc_pusher.py` emits).
- Honest empty states on event-sparse panels ("no fills yet", "flat — no
  open positions") retained/extended.

## 5 · Tests & battery

- Generator-match re-baselines by regeneration; metric-emission,
  no-overlap, supported-panel-type pins stay green (**piechart** added
  to the supported set).
- New regressions in the same commit: joined-table transform shape on
  every table panel · CSS injector present + self-hiding on all four
  boards · zero `value_and_name` state tiles across DASHBOARDS.
- Full battery: pytest · smoke · assurance · overfit · ruff · pyright ·
  bandit · compileall.

## 6 · Deploy

Regenerate → `scripts/grafana_import.py` re-imports the four boards +
API-deletes the two retired uids → commit → push branch
`claude/remote-control-e3h815` + fast-forward `main` (PC battery-gates
and self-deploys) → operator screenshot pass confirms rendering.

## Caveat — frosted blur

Grafana Cloud sanitizes the CSS injector until the signed **Business
Text** plugin is installed with the operator's Admin login
(Administration → Plugins; the Editor service-account token 403s on
plugin install). Until then the boards ship the native glass look
(transparent panels, Apple palette, black ground). The injector ships
dormant so the frosted skin activates on install with no re-import.

## Out of scope

- No mobile board (operator deleted it; not regenerated).
- No new metrics/exporter changes; no engine/risk-path changes.
- Business Text CSS wiring happens only after the operator installs the
  plugin (separate follow-up).
