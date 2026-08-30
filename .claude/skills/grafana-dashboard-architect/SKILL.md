---
name: grafana-dashboard-architect
description: Architect and modify the liquiditybot Grafana boards safely — generator-owned JSON, the zero-script-panel law (liquid glass removed 2026-08-30 after three paid-for incidents), exact-inventory test pins, supervisor auto-import pipeline, cloud/API verification, and the black-screen triage drill.
---

# Grafana Dashboard Architect

Operating manual for the liquiditybot observability boards. Every rule here
was bought by a dated incident; commit hashes cite the receipts. Read
`docs/grafana/HIG.md` before shaping any panel, and `docs/HANDOFF.md` for
what is currently open (ALERT-DRIFT lives there).

## Iron rules

1. **Boards are GENERATOR-OWNED.** `scripts/build_trading_dashboard.py`
   emits every `docs/grafana/*.json`. NEVER hand-edit the emitted JSON —
   the shipped-JSON == generator invariant is load-bearing (palette,
   HIG pass, and tags are applied at generation). Change the generator,
   re-run it, diff the output.
2. **ZERO script-executing panels, ever** (one-way pin since the
   2026-08-30 glass removal). No `marcusolsson-dynamictext-panel`, no
   `afterRender`/`helpers` hook, no html-mode text tile, no CSS injection
   of any kind. Test-enforced both ends (shipped JSON + generator module).
   The boards are pure declarative JSON; anything needing browser script
   belongs in the console, not Grafana.
3. **Every metric a panel queries must exist in `scripts/gc_pusher.py`'s
   `collect()`** — the pusher is the sole source of series names. A tile
   whose label says X but queries Y is the exact lie the inventory pins
   exist to prevent (the pins carry (id, title, type, sorted metrics)
   quadruples for this reason — see their docstring for the two measured
   failures that forced it).
4. **A board must say WHY it is empty** (honest-absence contract,
   `452bad12`). A stripped/retired board keeps a signpost text panel
   naming where its content went. Shipping a bare glass skin reads as an
   outage — measured: operator report "alert inputs is black screen"
   (2026-08-30, fixed `51b261af`).
5. **Never write volatile numbers into board descriptions or this
   skill.** Panel counts, thresholds, versions: re-derive from the
   generator run output and the cloud API.

## The pipeline (edit → verify → ship → confirm)

```
edit scripts/build_trading_dashboard.py
python scripts/build_trading_dashboard.py          # emits docs/grafana/*.json
git diff --stat docs/grafana/                      # expect ONLY intended lines;
                                                   # unintended churn = CRLF noise
                                                   # (checkout those files) or a leak
python -m pytest tests/test_glass_suite.py tests/test_boards_stripped.py -q
# move inventory pins CONSCIOUSLY in the same commit if panels changed
git commit + push (SAFE class — measurement plane, never cohort-resetting)
```

Shipping is automatic: `pc_supervisor` hashes the `grafana_import.DASHBOARDS`
manifest content each tick and, when it changes and a token is present
(`GRAFANA_SA_TOKEN` env or `~/.liquiditybot/grafana-sa-token`), runs
`scripts/grafana_import.py` — stable uids overwrite in place, never
duplicate. It triggers on DISK content, not git state, so the import can
land before your commit. Confirm in `outputs/grafana_import.log`, then
verify the CLOUD, not the repo:

```python
GET https://goldsavanna1216.grafana.net/api/dashboards/uid/<uid>
  Authorization: Bearer <token from ~/.liquiditybot/grafana-sa-token>
# check dashboard.version bumped and grep the JSON for your change
```

One legacy note: any browser tab open since BEFORE the 2026-08-30 glass
removal still carries the old injected style until one hard refresh;
after that, board changes need only a normal reload.

## The glass skin — REMOVED 2026-08-30 ("delete the liquid glass 100%")

The frosted skin only ever existed in Grafana as CSS smuggled through a
third-party panel's `afterRender` hook, and in ONE day that mechanism
produced three operator-visible incidents, each with its own failed fix:

- **Unscoped selectors**: `.main-view { background:#000 }` leaked across
  the SPA — blackened Alerting → History ("alert history screen is
  black"; `b8a673ce`).
- **`:has(#lb-glass-marker)` scoping** (`b8a673ce`): keyed the page theme
  to a React-managed span's MOUNT STATE — whole-page skin flicker per
  re-render, plus a `body:has()` recalc storm ("glitching"; reverted
  `42560be0` same day).
- The route-keyed `style.disabled` toggle (`42560be0`) worked — and the
  operator then ordered the entire mechanism deleted anyway, correctly:
  a pager surface should not depend on browser-executed injection at all.

After the removal: boards render native Grafana dark; the generator holds
a tombstone comment where `GLASS_RULES`/`_injector()` lived; the removal
is pinned one-way (`test_glass_removal_is_total`,
`test_no_panel_executes_javascript`). **The design language lives in
`scripts/glass_console.py`** (`outputs/console.html`) — the same palette
and idioms rendered natively, where they can never leak into Grafana. The
unused Business Text plugin may be uninstalled from the cloud instance
(Admin step, optional).

## Test pins & contracts (move pins in the SAME commit, never widen)

- `tests/test_boards_stripped.py` — exact per-board panel inventories as
  (id, title, type, sorted-metrics) frozensets; the single-JS-panel rule;
  afterRender must carry `GLASS_RULES` verbatim (compares against
  `gen.GLASS_RULES`, so generator edits auto-track); alert-rule metrics
  must appear on a board (`_alert_rule_facts` degrades CLOSED); the
  execution board is valid in exactly two pinned forms (full mirror or
  stripped-with-signpost).
- `tests/test_glass_suite.py` — injector idempotence guard + style id.
- Mirror duty: every metric the pager fires on lives on Problems →
  "What the pager watches" (`test_problem_board_mirrors_both_pager_conditions`).
- Learning board: INSTANT-tile idiom — a range-queried stat renders a dead
  producer's last value in healthy color for up to a month (the Brier
  incident mechanism); stat tiles there stay instant queries.

## Alert plane

Rules-as-YAML live in `docs/grafana/liquiditybot_*_alert.yaml`
(dead-man `noDataState: Alerting`; brier/drift `noDataState: OK` —
deliberate, read their comments). Provisioning is NOT automatic — as of
2026-08-30 the cloud held only {dead-man, an unversioned
"manipulation suspicion high"} while brier/drift YAMLs were never applied
(ALERT-DRIFT, HANDOFF watch list). Read cloud truth via:
`/api/prometheus/grafana/api/v1/rules` (current rules + state) and
`/api/v1/rules/history?from=&to=` (state transitions).

## Black-screen / glitch triage drill (instrument first)

A dark or broken board is a MEASUREMENT-PLANE fault until proven
otherwise; the market/bot is usually fine. Check in this order — each
step killed a real theory on 2026-08-30:

1. **Is the pipe up?** `outputs/gc_pusher.log` push cadence + HTTP codes;
   `outputs/status.json` mtime. (Was healthy during both black reports.)
2. **Is it the board's own JSON?** Read the emitted file — a stripped
   board with only the injector renders pure black BY CONSTRUCTION.
3. **Is it injected style?** Since the 2026-08-30 removal there IS no
   injection — so this symptom (dark on NON-board pages, cleared by one
   hard refresh) now means someone resurrected a script panel: the
   one-way pins should already be red. Also: any tab open since before the
   removal keeps the old style until one hard refresh.
4. **Is it data absence?** Query the cloud series directly
   (`/api/ds/query`, `count_over_time(<metric>[5m])`) — VENUE TRUTH for
   gaps. Ad-hoc log-timestamp parsing has dateless-midnight traps and
   produced a refuted 12.9h-gap claim (PAGER-1, dissolved by exactly this
   query).
5. **Plugin/browser** last: does another board render the glass skin in
   the same session?

## Cross-links

- Vault: `wiki/concepts/the-method.md` (instrument-first, this file's
  spine), `docs/quant/` for dated postmortems.
- claude.ai/design iteration path (parked 2026-08-30): authoring a mini
  "liquiditybot glass" React component set from `GLASS_RULES`/`_APPLE`
  and syncing via /design-sync needs a one-time `/design-login` from an
  interactive Claude Code session first.
