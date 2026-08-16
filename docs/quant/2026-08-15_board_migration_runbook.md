# Board migration c4272391 — compatibility + rollback runbook

**Migration:** strip every Grafana visualization panel from all four boards, then rebuild
one (the liquidity board). **Shipped and deployed 2026-08-15 21:24:57.**

Written AFTER the deploy, which is the wrong order and is itself the first finding: by the
migration gate's own criterion ("not approved until a rollback runbook exists for every
phase") the change was **unapproved at the moment it went out**. Everything below is the
gap being closed, and every command in it was RUN, not drafted.

---

## Phase 1 — board strip + liquidity rebuild  (STATE: DEPLOYED)

| | |
|---|---|
| commit | `c4272391`, parent `ed69da60` |
| deployed | 2026-08-15 21:24:57, battery-verified by the PC's own gate |
| imported to Grafana | 2026-08-15 21:26:27 (`grafana_import.py`, fingerprint-driven) |
| result | command 19 panels · exec/problem/screening 1 each (glass injector, y=0) |

### Compatibility analysis

| item | verdict | evidence |
|---|---|---|
| Exporter metrics | **UNAFFECTED** | `scripts/gc_pusher.py` is not in the diff (`git diff --name-only ed69da60..c4272391`). No metric renamed, added or removed. |
| Alert rules | **UNAFFECTED** | `liquiditybot_brier_alert.yaml` / `liquiditybot_drift_alert.yaml` fire on `liquiditybot_ml_brier`, `_ml_baseline_brier`, `_ml_drift_share`, `_monitor_level`. Grepped for `panelId` / `dashboardUId` — **zero hits**. Alerts reference metrics, never panels. |
| Engine code | **UNAFFECTED** | The only engine-scope references to `docs/grafana` are COMMENTS: `ml/monitor.py:783`, `scripts/gc_pusher.py:29`. Nothing reads the JSON at runtime. |
| Board URLs / bookmarks | **PRESERVED** | uids unchanged (`liquiditybot-trading`, `-exec`, `-problem-solution`, `-screening`). Nav links intact — 4 links on every board. |
| Panel deep links | **BREAKING, ACCEPTED** | Any saved URL of the form `?viewPanel=<id>` into a deleted panel is dead. Unavoidable when deleting 188 panels; accepted by the operator instruction that ordered the strip. |
| Test suite | **BREAKING, ACCEPTED** | 22 test functions pinning deleted content were removed (deleted, not skipped; git history retains them). Replaced by `tests/test_boards_stripped.py`. |

### COVERAGE GAP — found here, CLOSED 2026-08-16

The two alert rules fire on `liquiditybot_ml_brier`, `_ml_baseline_brier`,
`_ml_drift_share` and `_monitor_level`. After the strip, **none of those four was on any
board**, so an alert could only be discovered by being paged.

Measuring it turned up something worse than the gap. Against Prometheus, 2026-08-16:

| metric | last data | last value |
|---|---|---|
| `liquiditybot_ml_brier` | 2026-08-06 21:42 (234 h earlier) | 0.1133 |
| `liquiditybot_ml_baseline_brier` | 2026-08-06 21:42 | 0.0586 |

Gap **0.0547** against the rule's **0.03** line — the alert condition was BREACHED at the
last observation. The series then went absent and `noDataState: OK` returned the rule to
green. The rule is correctly configured (an event-gated metric's absence genuinely is not
its job) but the effect is a gate that has read healthy for ten days on an EMPTY CORPUS,
having last seen a breach. Same shape as a vacuous test: green because nothing was
measured, not because nothing is wrong.

**CLOSED** by rebuilding `liquiditybot_execution.json` to carry exactly those four metrics
plus `ml_champion_brier`, with the hero panel rendering the rule's OWN arithmetic
(`ml_brier - ml_baseline_brier`, red at 0.03) so panel and rule cannot disagree. Their
empty state now reads "window filling (<15 model-scored closes)" — visibly not the same
thing as green. Pinned by
`tests/test_boards_stripped.py::test_execution_board_still_mirrors_the_alert_rules`, which
parses the alert YAML's own `expr:` lines and fails if a rule fires on a metric no panel
shows. Mutation-verified in both directions.

### Rollback — PATH A (git), VERIFIED END TO END

Run in a throwaway worktree first; never in the live checkout.

```bash
git worktree add --detach <TMP> c4272391
cd <TMP>
git revert --no-edit c4272391
.venv/Scripts/python.exe scripts/build_trading_dashboard.py
```

Verification performed 2026-08-15, not asserted:

* All four regenerated boards are **byte-identical** to the pre-strip originals
  (`git show ed69da60:docs/grafana/<file>` == regenerated file → YES on all four).
* Panel totals restored exactly: command 64, execution 74, problem/solution 37,
  screening 40. (The generator prints TOP-LEVEL panels — 48/37/37/24 — because panels
  nested inside collapsed rows are not counted there. Comparing the printed number
  against a total is how a healthy rollback reads as broken; compare like with like.)
* Reverted tree passes its own tests: **81 passed**, ruff clean.
* Full deploy-gate battery on the reverted tree, run under the EXACT gate command
  (`LB_ALLOW_OUTPUT_WRITES=1 pytest tests/ -q -x --no-header`), 2026-08-16:
  **3719 passed, 1 skipped, 617.04s, exit 0** — the same 3719 the tree carried BEFORE the
  strip, so the rollback restores the test corpus as well as the boards. A rollback that
  cannot pass the gate cannot deploy; this one can.

To deploy the rollback: commit the revert and push to ALL THREE refs — the feature branch,
`main`, and `claude/remote-control-e3h815`. `auto_update._deploy_branch()` follows the
CHECKED-OUT branch, so a push to `main` alone deploys nothing.

### Rollback — PATH B (Grafana only), VERIFIED AVAILABLE

Restores the boards without touching git. Use when the panels are the problem and the code
is not.

Grafana retains version history — confirmed by API, not assumed:

```
v43  2026-08-16T02:25:20  import via scripts/grafana_import.py   <- stripped + liquidity
v42  2026-08-16T00:40:02  import via scripts/grafana_import.py   <- pre-strip, 64 panels
```

Restore `liquiditybot-trading` to **v42** (and the deep boards to v22 / v24 / v18).

**PATH B IS TEMPORARY.** `pc_supervisor` re-imports whenever the JSON fingerprint changes,
so a Grafana-side restore is overwritten the next time the boards are regenerated. It buys
time; it is not a fix. Only Path A is durable.

### Rollback triggers

Roll back if any of these is observed:
* a deep board renders a "panel plugin not found" tile (would mean the Business Text plugin
  was removed — it is currently installed, **6.3.0**, verified via
  `/public/plugins/marcusolsson-dynamictext-panel/plugin.json` → 307 to the CDN);
* the liquidity board shows `⚠ no series — exporter/pusher, not the bot` on tiles while the
  bot is demonstrably running;
* any board fails to load.

---

## Phase 2 — DuckDB analysis layer  (STATE: PROPOSED, NOT APPROVED, NOT STARTED)

Grafana answers the operational question (is it alive, where does it stand). It structurally
cannot answer the edge question: Prometheus holds 30-second gauge SNAPSHOTS of
`status.json`, so it cannot join a fill to its label to its postmortem, and has no
censoring-aware statistics.

Scale, measured — this is why the answer is an embedded engine and not a warehouse:

| table | rows |
|---|---|
| `outputs/audit.jsonl` | 45,143 |
| `outputs/equity.csv` | 194,025 |
| `outputs/signal_history.csv` | 10,688 |
| `outputs/fills.csv` | 1,069 |
| `outputs/postmortem_summary.csv` | 280 |

Analytical corpus ≈ 25 MB. (`outputs/` totals 5.6 GB, but 5.3 GB of that is
`outputs/recordings` — replay fixtures, not analysis input.)

### Compatibility — the one hard constraint

`duckdb` is in `tests/test_dependency_hygiene.py:37 FORBIDDEN`. That guard applies to
ENGINE_DIRS only, and `test_scripts_are_deliberately_out_of_scope` pins `scripts/` and
`tests/` as deliberately out of scope. **So DuckDB is already sanctioned in `scripts/`
and forbidden in the engine — no guard change is required, and none should be made.**
If a change to that guard ever appears in the same diff as a DuckDB import, that is the
signal the boundary is being eroded.

### Rollback

Delete the script and `pip uninstall duckdb`. Nothing in the engine imports it, so the
blast radius is one file. The pre-existing stdlib tools (`scripts/cohort_eval.py` et al.)
are untouched by this phase and remain the fallback — **do not delete them when the DuckDB
version lands**; run both and compare before retiring either.

### Gate for Phase 2 — not yet met

1. A DuckDB result must be reconciled against the existing stdlib implementation on the
   same data before it is trusted for any decision (they must agree, or the disagreement
   is the finding).
2. Nothing in `scripts/` may import `duckdb` at module scope in a file the deploy battery
   imports, or a missing dependency turns into a red battery and refuses every update.
3. A rollback runbook for the specific script, written BEFORE it ships — not after, as
   happened in Phase 1.
