# Log — vault

> Append-only timeline. Every LLM operation leaves an entry here.
>
> Format: `## [YYYY-MM-DD] <op> | <title>` followed by an optional detail line.
> Valid ops: `ingest`, `query`, `lint`, `create`, `update`, `delete`, `note`.
>
> Grep the last 10 entries: `grep "^## \[" log.md | tail -10`

## [2026-08-01] note | Vault initialized
Topic: **liquiditybot — quant trading research, model validation, and engineering decisions**. Layers created: `raw/`, `wiki/{entities,concepts,sources,comparisons,synthesis}`.
Schema loader: `CLAUDE.md` + `AGENTS.md` + `.cursorrules`.


## [2026-08-01] ingest | Bulk ingest — 35 liquiditybot documents
Ingested the full `docs/` knowledge corpus from the liquiditybot repo: 20 quant validation memos,
4 research/literature passes, 10 architecture and assurance docs, 1 whole-code audit.
Built 123 pages: 35 sources, 54 concepts, 17 entities, 9 comparisons, 8 synthesis.
Key threads reconstructed: the learning-pipeline arc (label quality -> era exclusion -> deploy
deadlock -> clock inversion -> horizon re-alignment -> cost/sigma), the governance doctrine
(never widen a gate, measured-before-eligible, ship inert, shadow-first), and the manipulation-defense
convergence (microstructure and criminology independently reaching the same posture).
Flagged 7 UNRESOLVED contradictions — most consequentially the effective-sample-size vs DoF-ledger
gap and three simultaneous round-trip cost numbers (0.50% / 0.65% / 0.86%).
Recorded 25 owed measurements. Lint clean: 0 orphans, 0 broken links, 1 connected component,
419 links.

## [2026-08-01] note | Schema extended with project conventions
Added domain rules to `CLAUDE.md` / `AGENTS.md`: qualify every measurement by corpus size and date,
preserve exact numbers, record retractions as first-class content, distinguish shipped from working,
and route contradictions and owed measurements to their registers.

## [2026-08-02] ingest | Session digest 2026-08-02 — QA root cause, corrected P&L, forward plan

Created sources/session-20260802-digest + concepts/{default-path-fallback-writes, payoff-asymmetry, abstention-filters-ruled-out}. Corrected synthesis/the-money-path-thesis (payoff asymmetry 0.560 vs 0.740 needed supersedes cost/sigma as binding term), extended synthesis/learning-pipeline-arc to 08-02, updated sources/test-suite-outputs-contamination (root cause fixed 858c8d71), sources/cost-to-volatility-horizon-mismatch, concepts/{iron-law-of-debugging, cost-to-volatility-ratio}, comparisons/horizon-96-vs-24-bars (432-bar hold), entities/liquiditybot. Registers: contradictions +2b/+14/+15, owed measurements +random-entry MFE control, money-path partially closed, contamination cleanup items.

## [2026-08-02] update | Addendum to session-20260802-digest — residual quarantine, attribution correction, provenance signal

Residual contamination quarantined (18 fixture positions/72 rows incl. one pre-fix battery block, commit 483f6727) — fills.csv now 637/637 audit-crossref CLEAN; attribution corrected to battery smoke runs (not bot restarts or debug_cycle alone); new decisive provenance signal: order_id membership in hash-chained audit.jsonl; lesson filed under iron-law-of-debugging: repetition is not evidence, timing structure is (rows=2141x6 @3603s = live hourly cadence CLEAN vs rows=60x7 @548s median = suite burst CONTAMINATED — first heuristic convicted the wrong group). Owed measurements: fills cleanup CLOSED, retrain_history 158/165 clean (08-02 snapshot), registry 97/129 fixtures filter-at-read-time, horizon_shadow 58.8% proven clean rest undecidable, calibrate_fills re-run still owed. Post-quarantine P&L materially unchanged: n=217, mean gross -0.0501%, median +0.0469%, win 57.1%, payoff 0.561 vs 0.750 needed — payoff-asymmetry thesis stands. Touched: sources/{session-20260802-digest, test-suite-outputs-contamination, cost-to-volatility-horizon-mismatch}, concepts/{payoff-asymmetry, default-path-fallback-writes, iron-law-of-debugging, cost-to-volatility-ratio, abstention-filters-ruled-out}, synthesis/{owed-measurements, open-contradictions-register, the-money-path-thesis, learning-pipeline-arc}, entities/liquiditybot, index.

## [2026-08-02] ingest | Second addendum 2026-08-02 late session - two decisive nulls, cost wedge, MDPI + Lund sources

Random-entry MFE control RUN and NULL (random_entry_control.py, commit 8062f46a: 51 real trades vs 200 seeded matched controls each on recorded 5-min Kraken OHLC; mean MFE percentile 0.516 [0.439,0.594]; the 87%-positive-MFE figure was diffusion; owed-measurements item 0 CLOSED, caveat n=51 rules out large edge only). Pre-registered 48-combo geometry search (geometry_search.py, Bonferroni z=3.26, 222 real entries, config fees): NO GEOMETRY SURVIVES - best h=432 tp=1% sl=2% mean -0.400% LB -1.124%; exit design minimizes bleed, cannot create edge - payoff-asymmetry lever claim bounded. Cost wedge quantified: 25.1% of winning PT touches fail the cost stack and label 0; first-touch P(PT)=0.418 pooled ~= 0.429 null (sl/(pt+sl)=6/14) vs label rate ~0.31 - contradiction register #16 RESOLVED + citation hazards added (87% MFE, exit-geometry-as-edge, BTC cells multiple-testing, 42.9% touch-vs-label). Per-asset ladder: only BTC h=48 (0.482) and h=96 (0.479) above null; LTC ~0.10, FLOW ~0.33 below. XV-021: passive_base_prob 0.048 measured vs 0.450 configured (sim fills 9x too often) - new owed item 13b, docketed post-cohort. Cohort 11/50, post-432 0% wins Wilson [0,25.9%] unreadable, hold continues. label_transfer_filter repaired (NO ANALOGUE, closest pair 4.5x off 18x target; Kish-on-uniform bug fixed to weight-sum) - era exclusion stands. Injection policy filed as governance-doctrine rule 11 (corpus gets nothing synthetic/relabeled). NVIDIA distillation blueprint adjudicated irrelevant. New sources: sources/mdpi-label-driven-mhs, sources/lund-meta-labeling (+ SSRN failed-fetch marker noted). Repo: f0120393/858c8d71/483f6727/8062f46a local-only, deploys stall until push. Touched: sources/session-20260802-digest, synthesis/{owed-measurements, open-contradictions-register, the-money-path-thesis, learning-pipeline-arc, governance-doctrine}, concepts/{payoff-asymmetry, cost-to-volatility-ratio, era-exclusion, average-uniqueness-and-ess, abstention-filters-ruled-out}, comparisons/horizon-96-vs-24-bars, entities/liquiditybot, CLAUDE.md/AGENTS.md standing question rewritten, index regenerated (129 pages).

## [2026-08-02] update | Final micro-addendum 2026-08-02 - geometry_search committed, wiki-is-truth directive, cost-wedge correction provenance

geometry_search.py committed 663434ae BATTERY GREEN - second addendum's pending-battery note RESOLVED; full day commit list f0120393/858c8d71/483f6727/8062f46a/663434ae, all local-only until operator pushes (deploys stall). GOVERNANCE: operator directive filed verbatim as governance-doctrine rule 12 - 'the corpus's Wiki is the truth; everything determined correct gets injected into the wiki'; operationalized: confirmed (measured, battery-green, committed) findings filed same-session; hypotheses enter only as owed measurements, never as facts; wiki is NOT the training corpus (rule 11 unchanged - nothing synthetic/relabeled enters signal_history); mirrored into CLAUDE.md/AGENTS.md domain rule 8. Cost-wedge provenance: geometry_search section 2 conflated label-space with touch-space, corrected BEFORE commit; 663434ae commit message records the wrong-quantity mistake as a citation hazard - filed with contradiction #16 (the hazard bit the tool that quantified it). Touched: sources/session-20260802-digest (final micro-addendum section + repo state + summary), synthesis/{governance-doctrine rule 12, open-contradictions-register #16 + hazard list, the-money-path-thesis, learning-pipeline-arc}, concepts/{payoff-asymmetry, cost-to-volatility-ratio}, comparisons/horizon-96-vs-24-bars, entities/liquiditybot, CLAUDE.md/AGENTS.md rule 8, index regenerated.

## [2026-08-02] update | Third addendum 2026-08-02 - honest fills shipped (8e5455e8), risk-posture doctrine page, deletion refused

HONEST FILLS: order_manager.sim_fill.passive_base_prob 0.45 -> 0.048 shipped 8e5455e8, battery green (pytest 3289/1, smoke 219, assurance 49) - the XV-021 measured market trade-through rate (22,854 resting-limit trials, Wilson [0.046,0.050]); sim no longer fills resting orders 9x too often. Consequences filed: paper entry rate will drop sharply (that IS the honest rate, starving is truthful); commit ts is an execution-regime boundary INSIDE the 432 cohort (first 11 closes under flattered fills - n=50 verdict read across it); XV-022 form caveat carried (0.048 = conservative end of [0.048,0.082], exp form owed replacement - new owed item 13c; 13b CLOSED shipped-ahead-of-trigger). 4 QA harnesses pinned passive_base_prob=1.0 alongside queue_aware=False (had declared deterministic fill while riding the shipped constant - same absence-of-a-key class, filed in default-path-fallback-writes; realism coverage stays in test_sim_fill_queue). NOT changed deliberately: fees stay 25/40 vs Kraken 16/26 (overstating cost is the safe direction - cost-truth). NEW PAGE synthesis/risk-posture-doctrine: operator directive verbatim intent - trade as if rent money is on the line at all times AND rent gets paid through profitable trades; survival side mechanized (daily 5% brake below 15% parachute per config_guard ordering, weekly budget, heat veto, give-back ratchet, loss-streak cooldown); deployment side - idle capital fails the rent test, monthly_profit_goal_usd=350 IS the rent number, gates learn from realized P&L since 07d38a51/162c595c; calculated risk = EV-positive by measurement, never a loosened floor. Session Q&A: quarantined records audit-crossref 0/136 - none recoverable, none wrongly convicted; deletion of learning data refused by design (governance rule 8 reaffirmed under challenge). Repo: 7 commits today incl 8e5455e8, all local-only until push. Touched: sources/session-20260802-digest (third addendum + supersedes + summary), NEW synthesis/risk-posture-doctrine, synthesis/{owed-measurements 13b/13c/1b/23b, governance-doctrine rule 8 + sibling link, the-money-path-thesis, learning-pipeline-arc}, concepts/{default-path-fallback-writes, cost-truth}, comparisons/horizon-96-vs-24-bars (regime-boundary callout), entities/{liquiditybot, config-guard}, CLAUDE.md/AGENTS.md standing question item 4 (fill-regime boundary), index regenerated (130 pages).

## [2026-08-03] ingest | Bug sweep 2026-08-03 - duplicate log pusher fixed, -50bps benign, gate-stats watch armed, first honest-fills day (d67fd6a5 pushed)

CONFIRMED+FIXED gc_log_pusher duplicate-spawn: pc_supervisor judges liveness by stdout-log mtime (STALE_SEC=120), pusher printed only when shipping; 08-02 22:05 runner bounce -> healthy idle pusher read stale -> second pair spawned -> every log line shipped to Grafana Cloud TWICE ~22h; fix = 55s quiet heartbeat (stdlib-only preserved), self-cleaned live via _source_changed (4 processes -> 1); sibling immunity was accidental (they print every tick) - failure mode named as NEW concepts/liveness-by-output-cadence, NEW entities/observability-sidecars. CLASSIFIED BENIGN: slip exactly -50.0bps = long_book add_offset_pct=0.5 resting bids 0.5% below mark by design (_entry_doc records 1.5->0.5 collar history), order_ids audit-verified - NOT fixture despite exact ref-multiple shape; citation hazard filed in iron-law-of-debugging (arithmetic shape is not provenance; the audit chain adjudicates). WATCH ARMED not adjudicable: ml.gate_stats.realized_closed=0 after first post-restart closes - nearly all old-runner entries (no gates attached) + one ambiguous ADA probe-path case; discriminator = next few closes of organic post-restart entries (tripwire 1 of owed item 1b). EXPECTED: single ERROR = ML-032 retrain request, 37% feature drift, day after fill-regime change. FIRST HONEST-FILLS DAY: ~8 positions/day vs ~16 (half, not zero), exits flowing (2 stale-loser purges incl 100h ETH, tb_time verticals firing), cohort 14/50 post-432 0 wins Wilson [0,21.5%] verdict still refused, equity 4930.79, era_mix alarm stood down (unexplained), fills 655 rows zero fixture signatures. DEPLOY CHAIN LIVE: head=remote=d67fd6a5, 08-02 stall resolved (tripwire 3 satisfied). Touched: NEW sources/session-20260803-bug-sweep, NEW concepts/liveness-by-output-cadence, NEW entities/observability-sidecars, entities/{long-book, liquiditybot}, concepts/iron-law-of-debugging, sources/test-suite-outputs-contamination, synthesis/{owed-measurements 1b+tripwires, risk-posture-doctrine}, comparisons/horizon-96-vs-24-bars, index regenerated.

## [2026-08-04] ingest | Deploy-gate worktree incident 2026-08-04 - location-variant test fixed (242568fb), other-session integration verified, corpus 87-to-89

INCIDENT root-caused+FIXED: auto_update battery worktree at outputs/_update_wt_<pid> (audit C-F11) x HIG test substring path filter ('outputs' not in str(f)) = gate saw empty repo, test_trajectory_metrics_exist_in_exporter red exactly where deploys are decided, green in every dev checkout; rejected external commits 4d56d0e0 (price anchors) + c66fa836 (dependency hygiene) twice deterministically; surfaced only now because gate battery never runs for local-ahead commits (first outside-pushed commits since HIG tests landed). Fix = path-COMPONENT exclusion relative to ROOT, verified two-sided in simulated outputs-nested worktree (old filter reproduces exact red, fixed 15/15 green). Defect class named (3rd instance this week): substring where identity required - position_id, round-number, paths. OTHER SESSION VERIFIED: price anchors sound (test_dependency_hygiene clean, explicit dir enumeration = location-invariant by construction); corpus-migration claim NOT yet true on production box (87 cols) until idempotent migrator ran post-battery: 9358 rows, 87->89 cols, entry_price/exit_price at tail, zero features padded; battery gap closed GREEN on merged tree (3292/1, smoke 219, assurance 49, ruff, compileall). DEPLOY: main 242568fb local==origin, runner bounced via ControlChannel (watcher pending), gate reads current next cycle ending 15-min reject loop. DESIGN QA filed to reason-code-registry: codes = discipline half (exact lineage, O(1) filter, drift audit; exit_reason/label separation made 25.1% wedge findable); confidence half = continuous companions + provenance spine; 136 fixture fills carried VALID codes - enumeration validates form not origin. HOUSEKEEPING: review worktrees removed; realized_closed tripwire still armed. Touched: NEW sources/session-20260804-deploy-gate, NEW concepts/location-invariant-tests, NEW entities/auto-update, entities/{liquiditybot, historystore, reason-code-registry}, synthesis/{owed-measurements 1b, open-contradictions-register 2b}, index regenerated (136 pages).

## [2026-08-04] ingest | Deploy-gate worktree incident 2026-08-04 - location-variant test root-caused and fixed (242568fb pushed+deployed), other-session claims adjudicated, price anchors live

DEPLOY GATE BRICKED+UNBRICKED: gate rejected first externally-pushed commits (4d56d0e0 price-anchor, c66fa836 dependency-hygiene) twice deterministically on test_trajectory_metrics_exist_in_exporter; mechanism = auto_update battery worktree at outputs/_update_wt_<pid> (INSIDE outputs/, audit C-F11) x HIG test substring path filter ('outputs' not in str(f)) -> in the gate worktree every path contains 'outputs', scan empty, every metric missing -> green in every dev checkout, red exactly where deploys are decided; invisible until now because this box always commits locally (local-ahead skips battery) - 08-04 delivered the first external pushes since the HIG tests landed. Fix = path-COMPONENT exclusion relative to ROOT, verified TWO-SIDED in a simulated outputs-nested worktree (old filter reproduces exact red; fixed 15/15 green same location). THIRD INSTANCE of substring-where-identity class (position_id grouping #2b, round-number, now paths) - iron-law corollary extended; NEW concepts/location-invariant-tests + NEW entities/auto-update. OTHER SESSION ADJUDICATED: HELD - price-anchor code sound, dependency-hygiene test location-invariant by construction (explicit dir enumeration), migrator idempotent+correct (ran live: 9,358 rows 87->89 cols, entry_price/exit_price at tail). DID NOT HOLD - 'session-start hook already migrated your real corpus' untrue on the PC (still 87-wide; migrated only when run here); its full battery ran pre-rebase only - the gate rejection WAS the disclosed risk materializing; gap closed: full 3292/1 battery GREEN on TRUE merged tree (smoke 219, assurance 49). PRICE ANCHORS LIVE: every new labeled row carries entry/exit price from 242568fb; 9,358 legacy rows padded 0=absent-forever (bookkeeping, never a feature - non-stationarity). DEPLOY CONFIRMED: local==remote==242568fb, dirty stamp transient (uncommitted-fix window), runner relaunched pid 9212, equity 4,931.69, honest-fills regime continues. NEW CITATION HAZARD filed (register + iron-law): a test green everywhere except the gate worktree is invisible until the first EXTERNAL push - single-writer repos never exercise their own gate. Design QA filed to reason-code-registry: enumeration validates form not origin (136 fixture fills carried VALID codes). Touched: sources/session-20260804-deploy-gate, NEW concepts/location-invariant-tests, NEW entities/auto-update, concepts/iron-law-of-debugging, entities/{liquiditybot, historystore, reason-code-registry}, synthesis/open-contradictions-register (hazard list), index regenerated (136 pages).

## [2026-08-04] update | Micro-update 2026-08-04 late - tripwire #1 RESOLVED (realized loop works), price anchors proven live, cohort 15/50

TRIPWIRE #1 RESOLVED - WORKING: ml.gate_stats.realized_closed moved 0->1; an organically-entered post-restart position closed and note_realized credited it, proving the realized-outcome loop (07d38a51/162c595c) wired end-to-end in production: gates -> order.meta -> position -> close -> era-keyed ledger; realized_active correctly False (1/25 toward activation). The 08-03 watch item ('not yet adjudicable') is now adjudicated: the loop works; the earlier zero was old-runner entries carrying no gates, exactly as hypothesized - verdict-withholding vindicated. PRICE ANCHORS PROVEN LIVE: 27 new corpus rows carry real entry_price/exit_price (newest 0.8442->0.8636); corpus 9,385 rows and growing anchored - the 242568fb deploy claim now backed by data on disk. STATUS: cohort 15/50; deploy chain current at 242568fb; equity 4,932.05; honest-fills cadence continues (~5 fill rows since morning). Touched: sources/session-20260804-deploy-gate (new section 6 + summary), sources/session-20260803-bug-sweep (finding 3 adjudicated), synthesis/owed-measurements (item 1b tripwire 1 RESOLVED, cohort 15/50), synthesis/risk-posture-doctrine (Side 2 gates-learn claim proven in production), entities/liquiditybot, entities/historystore, comparisons/horizon-96-vs-24-bars (cohort 14->15), index regenerated.

## [2026-08-04] ingest | Mythos-router integration 2026-08-04 - dormant receipts identified, 36/36 security false positives adjudicated, MCP integrated under write policy (b824a854 pushed)

DISCOVERY: dormant .mythos/ = receipt store of github.com/thewaltero/mythos-router v1.23.0 - two verified SWD runs 2026-07-12 (asset_learning_report.py create+fix, before/after sha256, git context, provider claude-code/claude-fable-5); Documents/mythos-workspace = its abandoned memory scaffold (MEMORY.md zero entries); marketing caveat filed: 'leaked Anthropic reasoning protocol' tagline is hype - real mechanics are Strict Write Discipline (path validation, snapshots, hash verify, rollback, receipts). SECURITY ADJUDICATION: skill-security-auditor raw FAIL (28 CRITICAL/8 HIGH) - ALL 36 false positives: 20 CRITICAL = SQLite exec() on FIXED SQL literals (BEGIN/COMMIT/PRAGMA, not code execution); rest = shell-free arg-array execFileSync, git.ts exemplary (branch regex, path normalization rejecting ../ and absolute); 8 HIGH incl TWO OF ITS OWN SECURITY TESTS flagged (path-traversal assertion, CI guard forbidding npm lifecycle hooks); independent sweeps clean (no install hooks, 2 reputable deps, 0 npm vulns, egress only opt-in provider APIs, surplusintelligence.ai = optional key-gated 4th provider not telemetry, no phone-home); iron-law extended: pattern-matching without adjudication convicts the innocent - now proven for security scanners; scanner FAIL = lead sheet, never a verdict. INTEGRATED: installed globally v1.23.0, project MCP in .mcp.json beside coinpaprika, tooling-only boundary (runtime never consumes MCP); write policy .mythos/policy.json (gitignored, this box): BLOCK outputs/**+config.json+.git (never-delete-learning-data as MACHINE policy - governance rule 8), CONFIRM engine trees+scripts; verified: mythos runs lists both July receipts PASS; role = receipts for AGENT file actions complementing hash-chained audit.jsonl (ENGINE actions), replaces nothing. NOT INTEGRATED deliberately: mythos memory system REJECT (vault sole brain per rule 12, third store would fragment truth); NVIDIA distillation blueprint REJECT clone-only (news-classification distillation, no GPU infra, addresses neither geometry nor corpus, YAGNI). STATUS: battery 3292/1 green, tree clean, head=remote=b824a854. Touched: NEW sources/session-20260804-mythos-router, NEW entities/mythos-router, concepts/{iron-law-of-debugging, adoption-ledger}, entities/{liquiditybot, tradingagents}, synthesis/governance-doctrine (rules 8+12), index regenerated (138 pages).

## [2026-08-05] update | Daily micro-update 2026-08-05 - first post-432 win (17/50), realized ledger 3/25, drift watch 37-to-40

FIRST WIN in the post-432 cohort: 17/50 closed, win rate 5.9% Wilson [1.0%, 27.0%] (was 0/15) - still unreadable, verdict still refused, correctly; hold continues; trail 0/11 [0,25.9%] -> 0/14 [0,21.5%] -> 0/15 -> 1/17 [1.0%,27.0%], lower bound just lifted off zero. REALIZED LEDGER ACCRUING: realized_closed 3 (was 1), realized_base_rate 0.3333, 3/25 toward activation - the 08-04-proven loop keeps crediting organically. CORPUS: 9,422 rows, 64 price-anchored (was 27). FILLS: 668 rows, +8/day - honest-fills cadence steady at the measured rate. STATUS: equity 4,931.73 flat; deploy chain current at b824a854; runner pid 9212 healthy. WATCH ITEM NOT DEFECT: ML-032 feature drift grew 37% -> 40% - governor keeps requesting retrain, champion bar keeps refusing worse challengers (both mechanisms working as designed, in tension); expected post-regime-change, resolves as post-change rows accumulate, but the deployed model is increasingly mismatched to the current fill regime - filed as ML-032 drift watch section on entities/ml-governor. Touched: comparisons/horizon-96-vs-24-bars (cohort 17/50 + trail + fills cadence), synthesis/owed-measurements (item 1b first win, tripwire 1 accrual note, tripwire 2), entities/liquiditybot (in-flight para + new Status 2026-08-05 block), entities/historystore (corpus 9,422 / 64 anchored), entities/ml-governor (NEW drift-watch section), synthesis/risk-posture-doctrine (Side 2 accrual), index regenerated (138 pages).

## [2026-08-05] ingest | Telemetry-stack audit 2026-08-05 - taxonomy strong, dark metrics, probe-admission dominance, log skew (report-only; held 21:08Z, approved and filed same day)

MEASURED (telemetry_audit.py, scratchpad, 21:05 UTC vs gc_pusher.py / docs/grafana/*.json / last-8k events.jsonl / core/codes.py / last-2k audit.jsonl; re-run at filing time reproduced all findings within tail drift): (1) TAXONOMY STRONG - 182 registered reason codes / 22 families, closed vocabulary at write, 36 distinct active in last 2k audit records, scored 95. (2) DARK METRICS - ~2 dozen emitted-but-on-no-board incl audit_dropped_writes + audit_tail_truncations (the hash chain's OWN health counters, no visual alarm), gauges_dropped_nonfinite, gate_divergence (07d38a51 reward-misspecification watch, never displayed), era trio, bracket_divergence_n, longbook_context_aligned; empty-panel hazard = absent metric indistinguishable from zero. (3) AUDIT-STREAM DOMINANCE - SZ-047 574 + SZ-051 260 + SZ-049 110 = ~47% of last 2k records are exploration-admission machinery (SD-004 corroborates: SZ-047 = 86% of 25,988 non-routine full-trail); corroborates unshipped per-gate conversion instrument as loudest untracked funnel stage. (4) LOG SKEW - 99.8% INFO, regime 3,536 + strategies 2,304 = 73% of Loki volume; diet owed. (5) NEW CITATION HAZARD (register + iron-law): static metric scans over f-string emitters produce phantom ghosts - the 92 displayed-but-not-emitted and 16 non-snake_case findings were ALL dynamic-name artifacts; repo's own source-matching test (ghosts=0) is the authority. Scorecard ~80/100 (taxonomy 95, provenance 90, metrics 75, logs 70, funnel 70). REPORT-ONLY - nothing changed; priorities filed as owed items 26 (board audit-health pair + gauges_dropped_nonfinite to VITALS, gate_divergence, era trio to LEARNING BRAIN - via board generator only), 27 (per-gate conversion instrument), 28 (log-volume diet). FILING PROVENANCE: measured 08-05 21:05 UTC, same-session filing declined by operator 21:08 UTC, approved and filed later same day. Touched: NEW sources/telemetry-stack-audit, entities/{observability-sidecars (+gc_pusher/gc_trace_pusher cast, audited-state section), reason-code-registry (measured size + dominance), liquiditybot (status note)}, concepts/iron-law-of-debugging (phantom-ghosts corollary), synthesis/{owed-measurements 26-28, open-contradictions-register hazard list}, index regenerated (139 pages).

## [2026-08-05] ingest | Debug-sweep deep-dive 2026-08-05 - 8 ranked findings, 8th QA-redirect instance, report-only (second held item, approved and filed same day)

READ-ONLY python-expert sweep (task a3858b19f9de22ae8, ~21:35 UTC) of liquiditybot_ab at head b824a854 (= deployed head); 26 files; REPORT-ONLY - no fixes applied, operator NOT yet asked which fixes to apply; all 8 filed as owed item 29 fix docket. HIGH 29a (confirmed): replay.py:64-82 hand-rolled QA redirect (+ sweep.py / replay_gate.py which call no redirect) omits system.fills_ledger_path (-> production fills.csv via main.py:1663 default, the exact 27x mechanism), ml.multi_horizon.shadow_path (-> horizon_shadow.csv, the 23,826-row 432 evidence base - still-open candidate writer for its undecidable rows), ml.model_path (replay-trained champion could deploy), ml/retrain_log - the 8TH INSTANCE of default-path-fallback-writes, first one caught BEFORE corrupting a result; invisible to CI (test_qa_isolation checks only configure_audit/configure_registry string presence for these entrypoints - boundary callout added to the class page fix-pattern claim). HIGH 29b (confirmed): train_meta.py:73/142 unguarded stale read-modify-write of live state.json beside a live runner (model file got CAS W2-2, state.json got none; exposure = unclean death before next 30s snapshot; closed positions resurrect, executed fills vanish). MEDIUM 29c (probable): week/month close not crash-atomic (state.py:251-252) - restart in <=30s window replays close, DOUBLE reserve refill after a losing week. MEDIUM 29d (probable): 432x200 candidate-pool saturation (history.py:2075-2081/2211-2218) - decided candidates hold slots full horizon for shadows, retention 2h->36h (18x) vs fixed 200, pop() evicts NEWEST, ceiling ~5.5 candidates/h, quiet-hour bias inversion - unpriced label-THROUGHPUT throttle distinct from the documented 18x live-label slowdown; per hold: report only, no retune (filed on horizon-96-vs-24-bars). MEDIUM 29e (possible): SingleInstanceLock stale-reclaim TOCTOU (runtime.py:266-271) - both racers can acquire ~15s, audit.jsonl.forked_* shape. LOW 29f (possible): FW_INVALID_PRICE exit reject + 'rejected orders never escalate' (main.py:2163-2164) = MARKET rung unreachable under total feed poisoning - invariant #5 corner, added to stated-invariants-vs-audited-reality. LOW 29g (confirmed): events.jsonl rotation drops unshipped tail from Loki forever (gc_log_pusher.py:120-123 resets offset=0 on new inode, .1 never drained). LOW 29h (confirmed): fills.csv torn-row on crash mid-append (fill_ledger.py:51-64, no fsync, no _adopt_tail analogue). NEAR-MISSES verified OK: gc_trace_pusher torn-tail re-ship impossible (offset never passes unterminated line), pc_supervisor log-handle non-leak (CPython scope close), sibling pushers measured immune to duplicate-spawn class (60s+30s < 120s window). EXPLICIT NEGATIVES: HTML/web (ui/ empty, REST/gRPC off-by-default loopback JSON-only, sound CSRF), numeric/timezone (tz-aware UTC, UTC-keyed rollovers, decimal side-aware rounding), sim-fill (no oversell, no fee double-book) - all clean. Iron-law extension: the law run prospectively - mechanism named at file:line then STOP, near-miss adjudication applied to the sweep's own output. FILING PROVENANCE: second of two held 2026-08-05 items approved by operator (first = telemetry-stack-audit); deliverable recovered verbatim from session transcript. Touched: NEW sources/session-20260805-debug-sweep, concepts/{default-path-fallback-writes (8th instance + fix-pattern boundary), iron-law-of-debugging}, sources/test-suite-outputs-contamination (second sequel), comparisons/{horizon-96-vs-24-bars (saturation callout), stated-invariants-vs-audited-reality (new exit-block corner)}, synthesis/owed-measurements (item 29a-h), entities/{liquiditybot, historystore, observability-sidecars}, index regenerated (140 pages), lint clean (0 orphans / 0 broken links).

## [2026-08-05] update | Fix docket resolved 2026-08-05 - owed item 29 closed: 7 of 8 fixed (e7ebbf60 + b409a24b), 29d deferred per 432 hold

OWED ITEM 29 DISCHARGED SAME DAY - all decisions made and shipped in two battery-green commits, head=remote=b409a24b. COMMIT e7ebbf60 (the two HIGHs): 29a FIXED as the CLASS fix - replay.py/sweep.py/replay_gate.py route through canonical qa_redirect_paths via new prepare_replay_config (one list, never two; hand-rolled replay list gone); sweep.py gained configure_audit/configure_registry isolation it NEVER had (sweeps had been appending replayed dispositions to the PRODUCTION audit trail and model registry); pinned by new replay-family tests in test_qa_isolation.py (real config through real replay preparation, all five known-leak keys + retrain rebind); docstring now EIGHT instances - 8th instance of default-path-fallback-writes CLOSED, the FIRST caught before corrupting a result; also closes the still-open candidate writer on horizon_shadow.csv going forward (past-rows assessment stands). 29b FIXED - train_meta.py _deploy_challenger re-reads freshest state.json at persist time, mutates ONLY the monitor section; ACCURACY CORRECTION filed on the sweep source page: the sweep's 'minutes of training' window was wrong - load_raw happens post-training, real window was the SECONDS of rescore+gate+save; still a real clobber vs the runner's 30s cadence, now one read-write pair. COMMIT b409a24b (five remaining fixables): 29c FIXED - fast_cycle close-out factored verbatim into _close_periods, snapshots the moment a week/month boundary fires (close + rollover land together; double-reserve-refill window gone); 29e FIXED - SingleInstanceLock stale-reclaim re-reads immediately before unlink, backs off on ANY change; 29f FIXED - rejected exits count an escalation attempt + non-finite exit price falls back mark->ref->entry so FW_INVALID_PRICE unreachable for exits - INVARIANT #5 RESTORED in the poisoned-feed corner (stated-invariants row now two found-and-fixed mechanisms); 29g FIXED - gc_log_pusher drains rotated events.jsonl.1 tail before offset reset, inode-provenance-checked, same at-least-once contract; 29h FIXED - append_fill heals torn tails + fsyncs each row. 29d DEFERRED deliberately - candidate-pool saturation is a property of the in-flight 432 migration, standing order hold-do-not-retune; stays a report-only watch item on horizon-96-vs-24-bars, decision re-opens post-cohort. TESTS: 8 new, all written red-first; battery 3310/1, smoke 219, assurance 49, ruff + compileall clean. Iron-law note: the separation held (name mechanism -> stop -> decide -> fix as distinct steps) and the fix pass corrected the sweep's own 29b claim - even a named mechanism gets re-measured when the fix touches it. Touched: synthesis/owed-measurements (item 29 per-sub-item dispositions + items 22/23 notes), concepts/default-path-fallback-writes (8th instance CLOSED SAME DAY + boundary-closed callout), sources/test-suite-outputs-contamination (second sequel fixed, incl 29h), comparisons/stated-invariants-vs-audited-reality (invariant #5 corner fixed), sources/session-20260805-debug-sweep (status RESOLVED, 29b accuracy note, new fix-disposition section), concepts/iron-law-of-debugging (separation completed + self-correction), index regenerated.

## [2026-08-05] ingest | Evening session 2026-08-05 - boards redesign, adversarial round-1 review, debug round 2 (5 HIGH fixed), PAXG + tangible-value gradient (717b2e39)

FOUR BATTERY-GREEN COMMITS, head = remote = 717b2e39; final battery pytest 3332 passed / 1 skipped, smoke 219, assurance 49, ruff + compileall clean (per-commit trail 3310/1 -> 3312/1 -> 3320/1 -> 3332/1). (1) bc198aa5 BOARDS REDESIGN, operator-ordered ("trash the old boards except the Apple glass and neat look... professional stock trading exchanges as reference... spot and margin positions... still see depth of geometry, asset screening, problems/solutions... learning brain... neat and professional") and authorized against the 08-01 HIG pass's standing deferral ("Panel removal: not done, on purpose - needs operator judgement"). command -> "trading desk" (exchange-style: money / positions & risk / geometry economics; the payoff-ratio tile now carries the 0.75 BREAK-EVEN THRESHOLD instead of borrowing the profit-factor scale, so the villain number colors red first); execution -> "models . learning . execution" (gains LEARNING BRAIN + TRAJECTORY + conviction admission - relocated not dropped, CV decode contract repointed; loses the duplicate INVENTORY & POSITIONING row); screening -> "screening & market" (gains CONTEXT + THALES); problem_solution gains the AUDIT & TELEMETRY INTEGRITY row = the telemetry audit's dark metrics FINALLY BOARDED (audit_dropped_writes, audit_tail_truncations, gauges_dropped_nonfinite as PROBLEM tiles + gate_divergence as a trend panel) - CLOSES owed item 26 (a)+(b) and boards the 07d38a51 KNOWN-GAP instrument for the first time; era trio (c) still open. Glass skin / Apple palette / HIG passes / panel primitives / SPAN_NULLS_MS / CODE_LABELS / UIDs all preserved; generator only, JSON never hand-edited. Fixture-gap-in-reverse recorded: the synthetic status fixture PREDATED gate_divergence so test_every_query_hits_an_emitted_metric read it as never-emitted and declined to protect it (phantom-ghost hazard inverted - a stale fixture erases a metric that exists). (2) 46cdc19a THREE RESIDUAL EDGES from an ADVERSARIAL review of the same day's own fixes. VERDICT ON ROUND 1: ALL SEVEN FIXES HOLD. Residue, each narrower than the bug it neighbors: (a) fills.csv could still be born HEADERLESS - the 29h heal covered torn rows but NOT the create-to-first-flush window; a 0-byte file + path.exists()==True skipped the header, DictReader then adopts the first FILL as the header and every consumer (breakeven_test, cost_attribution, calibrate_fills, provenance_audit, random_entry_control, geometry_search) misparses the WHOLE ledger with no error raised - same book of record as the 27x error; new_file now counts size 0 as new. (b) gc_log_pusher saved new-generation offsets under the OLD inode: tick() stat'd once, _drain_rotated (29g) spends seconds of network time before the main file opens, so a rotation in that window made the NEXT tick's drain seek .1 at a foreign offset and skip its head - a smaller instance of the hole 29g closed, INVISIBLE to 29g's own provenance check; provenance now from os.fstat on the opened handle. (c) the brand-new gate_divergence panel collapsed per-gate series under a bare max() while gc_pusher emits per gate with a {gate} label - it HID exactly the trend its own description tells the operator to watch; now max by (gate) with a {{gate}} legend, pinned. Lesson filed: a fix's NEIGHBORHOOD is where the next bug lives. (3) f3253f0d THE FIVE HIGH FINDINGS of debug round 2 - 27 findings across 5 parallel area agents (data, risk, ml, runner/deploy, order_manager) + A (adversarial) + H (board restructure); each fix red-first. R2-1 remote_control._runner_alive treated a FRESH status as alive but the clean-shutdown path writes runner_state=STOPPED with a fresh written_at, so for ~2min after every deploy bounce a remote flatten_all/stop was ledgered "applied" (at-most-once, never retried) then purged by the next boot as predating _PROC_START - an ACKED EMERGENCY COMMAND THAT NEVER RAN, the C-F3 class; H6 only covered commands sent DURING a boot, not in the dead gap before one; terminal state now means DOWN regardless of freshness. R2-2 take_deferred() had ZERO production callers despite its docstring naming main._submit_exit - live, a 100% close after a fully-filled preempted maker take SELLS THE POSITION TWICE (flips short) then the deferred fill drives pos.size into the zero-clamp with units unaccounted; now drains+applies through the same _handle_fill path, early-return if already flat. R2-3 failed CancelOrder ORPHANED LIVE GTC VENUE ORDERS (feed._private_post returns None rather than raising; both cancel paths discarded it, local state went terminal, order rested at Kraken forever) - and the healthy bot's own ~30s deadman refresh PREVENTS the venue backstop from firing; fixed with new registered code OM-090 + cancel_unconfirmed counter + hash-chained audit record on both paths, terminal transition retained (a blocked escape is worse), dry-run exempt. R2-4 the CLI deploy gate fit the isotonic calibrator on the very OOF vector it scored (IN-SAMPLE) while the champion is rescored strictly OOS - main.py fixed this in H13 (measured optimism +0.0032..+0.0066 = 25-150% of the 0.005 margin, ALWAYS pro-challenger) but the CLI lane never got it, so a manual retrain could deploy a strictly worse model AND stamp the optimistic number as the next champion badge; now scores through cross_fitted_calibrated_oof. R2-5 deploy/verify seam - save_model publishes the artifact then appends the ledger row a beat later; a reload in that gap rejects a GOOD model as tampered (ML-011), drops to cold-start prior, and never retries because _loaded_mtime is stamped before the verify; rejection now un-stamps the mtime (race heals, real tamper re-rejects loudly). (4) 717b2e39 PAXG + THE TANGIBLE-VALUE GRADIENT (operator: "open the bot up to paxg and treat gold as a tangible investment. make it understand the psycological aspects between the value of gold>bitcoin>Eth>alt coins"). New regime/haven.py encodes PAXG (a bar in a vault, value independent of adoption) > BTC (digital gold: fixed supply + deepest security budget but a claim on a NETWORK - the tangible anchor OF crypto, a risk asset TO everything else) > ETH (productive infrastructure, contingent on usage) > ALTS (venture bets). MECHANISM NOT MOOD: fear travels DOWN and greed UP the ladder, in order, because under stress the question stops being "what could this become" and becomes "what is this, actually" - so ADJACENT-rung spreads read regime better than any single return (adjacent-only so one blown-out microcap cannot dominate a reading about gold; rungs averaged so one alt ripping is a coin story). MEASURED AT COMMIT TIME on live Kraken bars: realized 5m vol ranks EXACTLY down the ladder - PAXG 0.075% < BTC 0.093% < ETH 0.120% ~ SUI 0.116% < ARB 0.160% - the tangibility ordering IS the volatility ordering, the thesis's own falsifiable prediction, and it HELD. First live gradient read flight_to_quality +2.00 (PAXG +4.7% / BTC +0.8% / ETH +2.1% / ALT -1.3% over 24h) - but BTC-ETH came out NEGATIVE in the same reading: the ladder is a TENDENCY not a law, which is why the instrument reports per-rung detail instead of a verdict (filed as a citation hazard). REPORT-ONLY by construction: no imports of execution/risk/main, pinned by a PARSED-AST test not a prose scan - a text search would match the docstring promising the restraint it checks (the 08-04 discriminator rule used prospectively). DEFAULT_BAND_PCT=1.0 is a stated convention, not a fitted constant. Wired: status.json haven block (guarded), gc_pusher exports gradient/rungs_seen/per-rung returns/state label, screening board gains the TANGIBLE-VALUE LADDER row with a trend panel; the synthetic fixture carries the block AT BIRTH this time. TWO REAL CONSEQUENCES the battery caught: (a) gold costs one DISCRETIONARY skimmer slot - config_guard FATALs at 13 pairs because the WS-down REST book poll at 3 req/s sustains a 12-pair envelope, so max_extra 6->5 (raising it again requires raising the envelope first); (b) PAXG needed AssetPairs-verified fallback meta (PAXGUSD price_decimals 2, lot_decimals 8, ordermin 0.001oz ~ $4.25 at $4,250 spot, costmin $0.50 - the SMALLEST TICKET IN THE UNIVERSE by dollar value, so gold is genuinely reachable by the sizer at this account size, not a listing; Kraken quotes PAXG/USD at 2.86bps with 20 levels a side). NO feature-vector change (432-bar cohort frozen mid-migration - the hold held against a new input, and the refusal is recorded as costing something real). SPOT ONLY - no margin anywhere, and no margin panel invented to imply otherwise despite the brief naming "spot and margin". ALSO FILED: round-2's NOT-fixed findings as owed item 30a-30j with file:line and mechanism (registry has no real hash chain; monitor Wilson guard algebraically dead + in-window-oracle baseline; per-leg profit-pool skim on entry-fee-inclusive net; OKX >2000-bar truncation; WS publish-before-checksum; 45s force-kill vs measured 88.1/55.5/50.2s stalls - likely origin of audit_tail_truncations; skimmer hysteresis voided every restart at a 15min deploy cadence; session_import within-bundle dupes; remote_control transient git-show permanent reject; runner boot-hang holds the lock forever), plus round-2 near-misses verified OK and CLEAN AREAS (ml/labeling.py, ml/walkforward.py, data/_http.py, data/recording.py - no reportable bugs, evidence not silence). Touched: NEW sources/session-20260805-evening, NEW synthesis/tangible-value-doctrine, synthesis/{owed-measurements (item 26 (a)+(b) CLOSED, item 29 residual edges, NEW item 30a-30j), open-contradictions-register (4 new citation hazards)}, sources/{telemetry-stack-audit (discharge section), session-20260805-debug-sweep (adversarial re-review section)}, concepts/{default-path-fallback-writes (headerless-ledger neighbor), iron-law-of-debugging (adversarial-on-own-work + AST-over-prose + inverted fixture hazard), payoff-asymmetry (0.75 threshold reached the screen)}, comparisons/{stated-invariants-vs-audited-reality (3 new rows), horizon-96-vs-24-bars (the hold held against a new input)}, entities/{liquiditybot, observability-sidecars, reason-code-registry (OM-090, 182->183), config-guard (the 13-pair envelope), kraken (PAXG venue facts), ml-governor (R2-4/R2-5 + the two open governance gaps)}, index regenerated (142 pages).

## [2026-08-05] create | synthesis/tangible-value-doctrine - ground truth for the gold > BTC > ETH > alts ladder

NEW DOCTRINE PAGE, ground truth for the corpus on the haven gradient (regime/haven.py, commit 717b2e39). Sections: (1) THE LADDER - PAXG (allocated bar in a vault, value independent of adoption, the only universe member whose drawdowns are not the others') > BTC (digital gold, fixed supply + deepest security budget, but a claim on a NETWORK - tangible anchor OF crypto, risk asset TO everything else) > ETH (productive infrastructure, contingent on usage) > ALTS (venture bets, the pump-and-dump surface the long book already refuses); everything unclassified defaults to ALT as the honest default. (2) THE PSYCHOLOGY AS MECHANISM - fear travels DOWN and greed UP, in order, because under stress the question stops being "what could this become" and becomes "what is this, actually"; therefore the MEASUREMENT follows the mechanism: adjacent-rung spreads (BTC up 2% is ambiguous; BTC up 2% while alts are down 4% is a flight to quality already in progress), adjacent-only so one microcap cannot dominate a reading about gold, rung-averaged so one alt ripping is a coin story; gradient signed positive = capital moving toward tangibility; state unknown when evidence is insufficient (a state, never a guessed number); DEFAULT_BAND_PCT 1.0 a stated convention, not a fitted constant. (3) THE FALSIFIABLE PREDICTION AND ITS FIRST MEASUREMENT - if tangibility is real and ordered, realized vol must rank down the same ladder; measured on live Kraken bars at commit time PAXG 0.075% < BTC 0.093% < ETH 0.120% ~ SUI 0.116% < ARB 0.160%, IT HELD; first live gradient read flight_to_quality +2.00 (PAXG +4.7 / BTC +0.8 / ETH +2.1 / ALT -1.3 over 24h) WITH BTC-ETH NEGATIVE in the same reading - the ladder is a TENDENCY NOT A LAW, recorded on the first reading in the doctrine itself because that is the qualifier that gets lost once a number reaches a board, and the reason the instrument reports per-rung detail instead of a verdict. (4) THE RESTRAINT AND ITS ENFORCEMENT - report-only, pinned by a PARSED-AST test rather than a prose scan because a text search for "import execution" would match the docstring promising the very restraint being checked (a guard green forever and worth nothing, same shape as the substring path filter and the phantom-ghost scan); no feature-vector change (432 cohort frozen); no gold-specific bracket geometry (sigma-scaled geometry tightens on its own - PAXG needing a special case would have been the tell that the abstraction was wrong); spot only, and no margin panel invented despite the brief naming margin. (5) WHAT IT COSTS AND BUYS - one discretionary skimmer slot (max_extra 6->5, guard FATALs at 13 pairs on the 3 req/s WS-down REST envelope, a measured capacity limit not a preference); genuinely reachable (ordermin 0.001oz ~ $4.25, costmin $0.50, smallest ticket in the universe by dollar value); buys ONE INSTRUMENT AND ONE SURVIVING PREDICTION, NOT EDGE - the binding defect remains payoff asymmetry 0.561 vs 0.750 needed at n=217, a regime read can only raise p or select when to trade, and gold's honest contribution is near-zero crypto beta (diversification), not alpha. (6) WHAT WOULD EARN IT DECISION WIRING, named in advance so it cannot be moved later - a track record against realized outcomes (the exports and the ladder trend panel start accruing it today); not before the 432 cohort verdict; veto rights before alpha rights under the asymmetry law and the certificate hierarchy; graded with a killing citation if rejected; and the honest possibility of a null. Until then the ladder is a lens the operator can watch and nothing else. (7) PROVENANCE DISCIPLINE - guarded status block + fixture carrying it at birth (the gate_divergence fixture gap, closed pre-emptively); read-only means read-only (any future QA/replay path must walk the ONE redirect - the eight-time-recurring class); a stated restraint is a design intent until something measures it, and the AST test is what makes this page's report-only claim a measured property. Cross-linked: payoff-asymmetry + the-money-path-thesis (the corrected cost-is-binding position), horizon-96-vs-24-bars (the 432 hold), iron-law-of-debugging, default-path-fallback-writes, owed-measurements, observability-sidecars, reason-code-registry, stated-invariants-vs-audited-reality, liquiditybot, kraken, config-guard, shadow-first-adoption, asymmetry-law, certificate-hierarchy, evidence-grading-ladder, honest-null-result, risk-posture-doctrine, and both 2026-08-05 source pages (telemetry-stack-audit, session-20260805-debug-sweep) plus session-20260805-evening.


## [2026-08-05] update | Owed item 30 CLOSED 2026-08-05 - all ten sub-items fixed in 4799bfc7, each with a red-first test; an eleventh bug found by accident

Battery 3376 passed / 1 skipped, smoke 219, assurance 49, ruff + compileall clean; head = remote = 4799bfc7. MONEY (30c): the profit-pool skim ran once per exit LEG on net (gross minus that leg's exit fee, NOT minus the slice's pro-rata entry fees), so it skimmed an overstated base AND fired on winning legs of losing trades - a +$16 tier take on a trade netting -$80 still moved ~$4.80 into locked savings/reserve, never clawed back; with tiered exits the normal shape, trading cash bled monotonically into locked pools as a function of gross winning legs. Fixed by separating the fused concerns: cash settles per leg (skim=False; entry fees already left cash at fill time), the three-way split runs ONCE per closed trade on the fully-net total via new CapitalManager.skim_trade() in _finalize_position; equity-conservation + no-double-booking pins. EVIDENCE (30b): the Wilson credibility guard was ALGEBRAICALLY DEAD (lcb <= observed always, so the clause was implied by the raw-gap condition and could never veto - and grew MORE permissive as n fell); baseline_brier was an in-window oracle scoring the window's own realized mean (an all-loss 15-close window handed the baseline a clairvoyant 0.05). Fixed with wilson_ucb() and _prior_base_rate() (rows predating the window only, neutral 0.5 at cold start - a weaker baseline, slower to convict). RETRACTION FILED: the item's own '15-loss streak is a ~4-9% event' premise was WRONG - against a promised 0.30 it is 0.70^15 ~ 0.5%, so convicting is correct; the test was rewritten to pin the real mechanism (an honest ~0.18 promise survives an unlucky streak; the same shortfall is harder to indict at small n), and test_monitor_deescalate_deadband needed a _seeded() helper because its fixture had been leaning on the oracle baseline. PROVENANCE (30a): ml/registry.py is now genuinely hash-chained (prev + seq + content hash, matching core/audit.py's construction), verify_chain() walks the links, and a broken chain FAILS the load gate instead of authorizing it - the registry.jsonl citation hazard is RESOLVED in both the contradictions register and stated-invariants. ELEVENTH BUG, found by a test for a DIFFERENT property: the registry ledger had the same torn-append fusion defect as the fills ledger (crash mid-append leaves a fragment, next write welds onto it, taking a good record down with the bad one) - THIRD instance of the class, now concepts/torn-append-fusion. Also: OKX deep history no longer truncated to 2000 bars (train_meta asked ~10 days of 5m bars and got ~7, no log line); ws_feed publishes the Kraken book only after checksum verification (the resubscribe backoff had been serving a phantom 1-5-level book stamped fresh every frame); auto_update force-kill grace 45s -> 150s against runner stalls MEASURED at 88.1/55.5/50.2s - the likely origin of audit_tail_truncations; skimmer replace-hysteresis restored across restarts (scores persisted but never read back, so a 0.55 candidate evicted a 0.90 incumbent every 15-min deploy); runner boot-hang lock-forever bounded by lock_boot_max_stall_sec (2x the running stall bound); session_import within-bundle duplicate merges; remote_control transient git-show failures left unledgered and retried within the command's own 30-min expiry. Touched: synthesis/owed-measurements (item 30 struck, per-sub-item dispositions), concepts/torn-append-fusion (NEW), concepts/default-path-fallback-writes, concepts/wrong-null-calibration, concepts/payoff-asymmetry, comparisons/stated-invariants-vs-audited-reality, synthesis/open-contradictions-register, entities/ml-governor, entities/observability-sidecars, entities/auto-update, entities/liquiditybot, sources/session-20260805-evening (new section 5), index regenerated.

## [2026-08-05] create | concepts/torn-append-fusion - a crash mid-append leaves a fragment and the next append welds onto it, taking a good record down with the bad one

Third instance of the class in this repo (fills.csv 29h in b409a24b; the fills create-to-first-flush window in 46cdc19a; ml/registry.py's provenance ledger in 4799bfc7), so it earns its own page. Standing rule recorded for every append-only JSONL/CSV writer here: check whether the last byte is a newline, terminate the torn tail so the fragment isolates as one skippable junk record, fsync each record, and treat size 0 as new rather than trusting path.exists(). The second lesson is how it was found - writing tests/test_registry_chain.py for a COMPLETELY DIFFERENT property (that the new hash chain detects edited/deleted/reordered/rewritten rows) forced the torn-row state to be constructed as test INPUT, and that is what revealed the writer could produce it; five parallel area agents had read ml/ in round 2 and not seen it. Page also records where the class has NOT been swept - events.jsonl, retrain history, context_history.jsonl and horizon_shadow.csv are unchecked against the rule; core/audit.py already truncates a torn final line at boot, arrived at independently. Cause-vs-consequence noted: 29b/29h shrank the consequences of an unclean kill weeks before item 30f removed the cause (auto_update's 45s force-kill grace against measured 88.1/55.5/50.2s runner stalls).

## [2026-08-06] ingest | Geometry filing-system deep dive 2026-08-06 (ee0ac4ad) - one durable append, four honest reports

Commit ee0ac4ad, head=remote, battery 3398 passed/1 skipped (22 new tests, each RED first), smoke 219, assurance 49, ruff+compileall clean. THE NULL: the geometry write path is SOUND - rotation loses nothing (13 .bak generations recovered, 0 rows missing), pending-vector round-trips through state.json, width invariant 3+64+22=89 exact, and the live pt_frac/sl_frac threaded into log_close IS the traded geometry with NO recompute anywhere; a suspected 10.9 percent ground-truth hole resolved to 34 quarantined QA fills + 3 FEATURE_SCHEMA_VERSION drops matched BY POSITION ID (exactly the 3 positions open at the v8->v9 bump) - nothing was bleeding. DURABILITY: torn-append fusion consolidated from a per-file pattern into ONE primitive core/runtime.durable_append (append-mode sibling of atomic_write_json), adopted by 8 writers - signal_history.csv via BOTH independent appenders, horizon_shadow.csv, retrain_history.jsonl, context_history.jsonl, equity.csv, postmortem_summary.csv, weekly/monthly period ledgers (the last had NO error handling at all); all ten files clean on disk (9692 corpus rows, 145576 equity, 29013 audit, 25039 events, 44 rotated generations, zero fusions) - preventive not remedial; the size-0 header hole recurred independently in horizon_shadow.csv one day after the fills.csv instance. FOUR HONESTY DEFECTS: (1) mark_disposition capped disp at 40 chars against a 113-char SZ-023 - 2614 SZ-023 rows lost bracket geometry, 1052 SZ-030 lost net breakeven/b_net, ZERO of 9692 rows retained a bracket payload, and gate_efficacy_report regex-scrapes that field; cap now 200, main.py stops pre-truncating; (2) bracket_divergence_summary published a TAUTOLOGY - tb_time's counterfactual IS its realized value so delta is 0 by construction, 33 of 35 lifetime records (94.3 percent) were tb_time, so the Grafana gauge read 1.0000 and was 94 percent arithmetically incapable of anything else; now computed over the PRICED subset (tb_pt/tb_sl) with n_priced beside n and None until one exists; (3) AuditTrail.log dropped a record on OSError without re-arming _adopt_tail, so a part-way write left orphan bytes, the next append welded on, and verify_chain classified it torn=False->tamper=True - reporting the regulated trail of record as PERMANENTLY TAMPERED for crash damage; (4) _ensure_schema rotated the corpus without invalidating the derived LIVE counters, stamping the new file's (mtime_ns,size) key onto stale counts so the cache REFUSED to re-scan - reproduced as a 6x asset overcount, and these feed position SIZING (n_a in SPB-R scarcity pricing) and the regime-coverage admission hold, not telemetry. Plus: the width guard and its warning message were two independent literals (correct 22, stale 20) reporting a phantom 69-column schema against a true 64; and log_close's 'if entry is None: return' was the ONLY unlogged exit in the write path, now ML-084 (183->184 codes). NEW: sources/session-20260806-geometry-filing, concepts/tautological-instrument. UPDATED: concepts/torn-append-fusion (class SWEPT - the page's own named honest close discharged; residual: enforced by adoption not by a gate), entities/historystore (filing-layer audit, corpus 9692 rows), entities/reason-code-registry (ML-084, 184 codes), comparisons/stated-invariants-vs-audited-reality (3 new rows + the unstated-invariant thesis), synthesis/open-contradictions-register (4 new citation hazards), synthesis/owed-measurements (item 31 CLOSED, items 32-33 opened), synthesis/learning-pipeline-arc (lesson 7: the data was clean and the instruments were not). Index regenerated (145 pages).

## [2026-08-06] ingest | Append gate 2026-08-06 (0e30ca09) - the third corpus writer, and the torn-append invariant converted from adoption to enforcement

COMMIT 0e30ca09 (parent ee0ac4ad, head). 2 files, +167/-5. Battery 3406 passed / 1 skipped (8 new), smoke 219, assurance 49, ruff + compileall clean; gate re-run at filing time = 8 passed in 1.09s. WHY IT EXISTS: filing ee0ac4ad into this wiki forced the sentence 'the invariant is enforced by adoption, not by a test' onto concepts/torn-append-fusion - that residual was the whole spec for this commit, and it is discharged the SAME DAY in the form it was named in. THE MISSED WRITER: scripts/session_import.py:366 is a THIRD independent appender to outputs/signal_history.csv (alongside HistoryStore._append_row and corpus_sync's recovery merge) - bare open(...,'a') with no torn-tail probe and no fsync, PLUS a header under 'if dest_hist.exists()' so a ZERO-LENGTH corpus stays headerless and csv.DictReader adopts the first TRAINING ROW as column names (the size-0 variant, THIRD occurrence in this repo). Worst-placed of the three: corpus_sync --apply runs it HOURLY and UNATTENDED, so a kill mid-import fuses two labelled outcomes with nobody watching. Three concurrent unhealed writers on one file is the seam that produced SD-007 on the audit chain. Fixed: one durable_append per import batch, primitive owns the header. THE GATE: tests/test_append_invariant.py walks the AST of every shipped module (core data execution ml risk regime strategies sentiment api scripts + main.py runner.py - VERIFIED to be exactly the repo's ten non-test packages and two top-level modules) and fails on any open(..., literal mode containing 'a') outside a 13-entry reasoned allowlist in three groups (the primitive + three predating heals incl core/audit.py whose _adopt_tail also truncates and re-adopts seq/prev; seven human-readable text logs; two operator-invoked/hot-path exemptions). AST not regex because prose false-positives. PROVEN TO BITE: bare append injected into ml/interpret.py failed the gate with file+line, injection reverted. Three companion tests: stale exemptions must leave (a stale exemption silently covers a FUTURE append), every entry must name a real file, and five data writers must POSITIVELY contain durable_append so deleting the call is caught too. core/events.jsonl JsonlEventHandler.emit stays a bare append DELIBERATELY (durable_append reports via log.exception; calling it inside a logging handler would re-enter that handler) - now a reasoned allowlist entry rather than an unexplained hole in the sweep. THE HEADLINE FINDING: the gate's FIRST RUN found the writer that a careful by-inspection sweep, run one day earlier with the defect shape fully in mind, had walked past. A sweep is a search (coverage = attention); a gate is an inventory (coverage = a written scan scope). NEW RESIDUAL, recorded not measured: (a) the allowlist is per-FILE not per-call-site, so scripts/corpus_sync.py - exempt for its :57 text log while being the corpus's SECOND data appender at :160, and the one data writer ABSENT from the positive durable_append list - could have that call replaced by a bare append with the battery still green; (b) SCANNED_DIRS is a hardcoded tuple, correct today, so a new top-level package is unscanned until someone adds it; (c) tests/ deliberately excluded (a test that fabricates a torn tail must append), which is exactly where default-path-fallback-writes lives - the two classes meet at the boundary the gate declines to cross. TOUCHED: NEW sources/session-20260806-append-gate; NEW concepts/adoption-is-not-enforcement (type specimen: 3 rounds of per-file fixes -> a primitive -> a gate; the design rules incl make-the-exemption-list-the-product, keep-the-allowlist-from-rotting, assert-positively-too, AST-not-regex, prove-the-gate-bites; and the honest recursion that a gate is itself adopted, so enforcement buys a FINITE LISTED GREPPABLE residue rather than a closed class); concepts/torn-append-fusion (residual DISCHARGED, ninth writer added, arc extended to a 5th round - a bug in the METHOD OF LOOKING - sources 4->5); synthesis/owed-measurements (item 31 residual CLOSED, three narrower holes replace it, sources 27->28); comparisons/stated-invariants-vs-audited-reality (new row - every other row is an invariant stated and never measured, this one was stated, believed, deliberately swept the day before, and still false; sources 6->7); entities/historystore (THREE appenders not two, with a cadence table, plus corpus_sync named as the corpus's one durability blind spot in the new gate; sources 11->12); concepts/default-path-fallback-writes (the twin got a gate, this class did not - tests/ exclusion lands on its home ground; sources 5->6); index regenerated 145->147 pages.

## [2026-08-06] ingest | Hedge open/unwind thrash 2026-08-06 (5c111962) - 147 round trips because two code paths tested two different pairs

COMMIT 5c111962 (parent 0e30ca09, head). 3 files, +203/-14: execution/hedging.py, tests/test_hedge_thrash.py (new, 146 lines), tests/test_append_invariant.py (an unrelated tightening that rides along). EVERY NUMBER BELOW RE-DERIVED AT FILING TIME FROM outputs/fills.csv AND outputs/equity.csv, not copied from the commit message; the two agree to the cent. THE INCIDENT: 2026-08-06 20:09:40.459 to 20:34:19.303, 24.65 minutes, 294 ADA/USD fills = exactly 147 hedge opens + 147 unwinds, ZERO other fills in the window (the entire 25 minutes of trading was the loop), $72,433.15 of notional churned on a $4,933 book = 14.7x equity, $289.73 of fees at a median 40.00 bps PER FILL (80 bps per round trip, $1.97 each), equity 4,934.22 -> 4,632.30, and fees = 95.60% of the $303.07 drop. Median cycle spacing 5.0s (the fast cycle), median slip 2.03 bps, post_only=0 on all 294 (marketable by design per the F6 Rule 534 self-cross guard, so both legs pay taker), hedge notional decaying 365.20 -> 126.63 as beta and equity fell. Net delta sat at +1,086 the whole time against a cap drifting 932 -> 927 only because the loop was burning the equity the cap is a fraction of. PAPER, STATED HONESTLY: system.dry_run=True and outputs/force_dry.on is present - the commit's 'LIVE INCIDENT' means the live running process, not a harness and not real money; the 294 orders and the mechanism are real, the dollars are simulated at the deliberately overstated 40 bps taker constant (Kraken published 26 -> the same churn is $188.33). THE ASYMMETRY: open gated on corr(exposed, hedge_asset) = corr(ETH,ADA) >= 0.55; unwind tested corr(hedge_asset, others[0]) = corr(ADA,ARB) = 0.00, where others[0] is 'the alphabetically-first asset that is not the hedge asset' - an unrelated pair. Both assets were alphabetical accidents of the same kind: hedge_asset = others[0] picks the alphabetically-first NON-EXPOSED asset (ADA), the old unwind's others[0] picks the alphabetically-first NON-HEDGE asset (ARB). The hedge was chosen by one alphabetical tiebreak and killed by a different one. SECOND MECHANISM UNDERNEATH: regime/correlation.py:40-41 returns 0.0 for any pair it has never seen and _EwmaCov.corr returns 0.0 whenever either variance <= EPS, so 'no data' reads as 0.00, which is below every correlation floor - the 147 unwind reasons ('correlation 0.00 below floor') were literally true and completely misleading. The same file defends the SAME hazard one path over: beta() also returns 0.0 for an unknown pair and the OPEN applies beta_floor; the UNWIND consumed corr raw. THE FIX: a shared HedgeEngine._exposure_by_asset() that both paths call, so 'which asset are we exposed to' has ONE definition; the unwind now tests corr(dominant, this hedge's asset) - the exact quantity the open gated on - with dominant is None or dominant == a giving corr=1.0 so the 'signal delta normalized' arm owns the empty-book case. The property is AGREEMENT, not correctness: a cold engine now makes both paths refuse, so the hedger either opens and keeps or never opens. SECOND THRASH OF THIS SHAPE IN THIS ONE FUNCTION: evaluate()'s signal_net comment documents the first (the unwind read TOTAL net delta, so a correctly-sized hedge unwound itself the moment it worked). In the parent revision that comment ENDED AT LINE 78 and the second disagreement sat at LINE 90 - twelve lines below the warning about its own shape. Thrash #1 was fixed by correcting arguments; that closed the instance and left the class open, which is why #2's fix is an extracted definition. ADVERSARIAL VERIFICATION RUN AT FILING (scratch tree, live checkout untouched): the 5 new tests run against the PARENT's hedging.py give 3 FAILED / 2 PASSED, and 5/5 against the fixed module. The two that pass on the buggy code are the anti-rubber-stamp guard (expected) and - the finding - test_open_and_unwind_agree_across_repeated_evaluations, the one whose docstring says 'the actual money bug'. It is VACUOUS: evaluate() is a pure function of a state the test never mutates and whose actions it never applies, so its seen set holds one element for ANY implementation; it tests determinism, not oscillation. The repo stated the exact discipline ONE COMMIT EARLIER (the append gate was proven to bite by injecting a bare append) and did not apply it here. The commit IS protected - by its three real red-first tests, not by the one named after the bug. RESIDUALS (owed item 34, none measured): (a) NO GATE for the class - the shared helper is a convention and test_exposure_helper_excludes_hedges_and_is_shared asserts sharing in its NAME ONLY, so re-inlining a third definition is caught by nothing (adoption-is-not-enforcement, reopened one day after it was written; honest asymmetry noted: 'no quantity is computed twice' has no mechanical predicate the way open(...,'a') does); (b) the vacuous test, closing together with (a) via a fixed-point rewrite or an AST call-site assertion; (c) NO CHURN BREAKER ANYWHERE - _run_hedge_pass runs every ~5s, orders.has_open() blocks only CONCURRENT duplicates not SEQUENTIAL re-opens, and risk/circuit_breaker.py (4 consecutive full-trade losses -> veto new entries) is fed inside 'if not pos.is_hedge:' at main.py:1588, so 147 consecutive losing round trips on one symbol were INVISIBLE to the mechanism whose stated purpose is pulling a misbehaving symbol off the sheet - the exclusion is right for attribution and leaves a hole for churn; (d) the hedge asset is STILL chosen alphabetically - the fix makes both paths agree about an arbitrary choice, it does not make the choice good. DELIBERATELY NOT OWED: the surviving net vs signal_net asymmetry between open and unwind is documented hysteresis installed by thrash #1's fix - unifying it would reinstate that bug. ALSO CARRIED IN THE COMMIT: the positive durable_append assertion list gained scripts/corpus_sync.py, core/runtime.py and main.py, which HALF-CLOSES owed item 31 residual (a) the day after it was written (the named exposure is covered; the per-file-vs-per-call-site granularity that created it is unchanged). DRIFT: the shipped unwind comment and the test docstring record a MID-INCIDENT snapshot - '121 times / 246 fills / ~$143 / 21 minutes' - so the source understates its own incident by roughly half; the incident kept running while the fix was written. TOUCHED: NEW sources/session-20260806-hedge-thrash; NEW concepts/two-paths-one-quantity (the root cause class, with the corpus's other instances: the cost stack's three simultaneous round-trip numbers 0.50/0.65/0.86%, the schema width's two independent literals 22 vs 20, the disposition cap's two truncation sites, the assurance check counts); NEW concepts/zero-is-not-a-reading (the missing-data sentinel inside the domain of the comparison, five instances incl the book-walk cost returning 0.0 instead of the veto sentinel and the size-0 header branch, plus the one correct handling - agree_rate: None with n_priced beside it). UPDATED: concepts/adoption-is-not-enforcement (the next commit reopened the gap for a different class), concepts/iron-law-of-debugging (the law satisfied FOR FREE by fills.csv's reason column recording both sides of the disagreement verbatim - the payoff on the recorder the law demanded in its first instance - then betrayed by the vacuous test), comparisons/stated-invariants-vs-audited-reality (a THIRD kind of row: stated correctly at the top of the file that then measured something else, and the docstring names BTC/ETH, a pairing the live seven-asset universe does not privilege), synthesis/documentation-drift-register (2 rows + a new kind of drift: shipped source comments already stale at commit time), synthesis/owed-measurements (item 34 opened, item 31(a) half-closed), synthesis/the-money-path-thesis (the cost stack with the signal set to zero: no entry decision, no geometry, no win rate, no model - just turnover, and the forward reading that maker-only execution is not only a bps saving but a RATE LIMIT), concepts/cost-truth (in paper the FEE component of a round trip is the configured constant by construction - only slippage and spread carry information). Index regenerated 147 -> 150 pages.

## [2026-08-07] ingest | Hedge churn #2 + the churn guards (cf454d5e cloud-authored, af544d4c, HANDOFF 42f6cc61/9b1eb6a5/21769fb8) - cold correlation must never buy new risk

INCIDENT #2, ~12h after #1's fix and with it HOLDING: 01:09:45-01:34:19Z, 147 laps of the same ADA hedge at ~10s cadence, every close 'correlation 0.00 below floor', sum -$318.27 (fills.csv re-verified at filing: 290 fills in-window, 296 incl. shoulders = 148 opens+148 exits, 147 corr-0.00 laps, fees $296.93 = open-leg 149.83 + exit-leg 147.10, notional $74,232, all post_only=0); NOT two-paths - the READING oscillated: cold post-restart EWMA flaps |rho|~1 (2 samples: open passes) <-> 0.0 (variance<=EPS: unwind fires); proof cold-start not market: isolated warm unwinds 02:01/02:24/02:34/02:44Z at corr 0.34/0.46/0.55, slow-lap tail to 11:35:31Z (last hedge fill in ledger). Owed 34(c) 'no churn breaker anywhere' FIRED before it closed. CROSS-SESSION ARC: HANDOFF doc to VS Code session (42f6cc61) -> operator deadlock directive appended (9b1eb6a5, 'I don't want to deadlock anything' - the naive cold->hold-state spec was itself the week's 4th release-depends-on-the-blocked-thing gate) -> fix reassigned mid-flight to CLOUD session (cf454d5e) -> stand-down notice (21769fb8, 'two writers never meet on the hedger - this incident's own disease'). THE FIX, guards on OPEN side only, unwinds NEVER gated: CorrState.samples+pair_samples ('gate on this count, never on the rho value's plausibility'; empty dict = legacy warm-assumed 1e9, byte-identical for old callers); open needs pair_samples>=corr_min_samples 12; per-asset rehedge_cooldown_sec 600; FW-070 latch (registry 184->185) at 3 unwinds/900s, AUTO-release on window+warm (time and evidence, never the gated action); hedger clocks ride the snapshot (persistence hasattr-guarded own-try section, live state.json verified carrying it); config_guard bounds + coherence FATAL cooldown<window CAUGHT ITS OWN AUTHOR'S first config (900>=900) on first battery run; 8 red-first tests incl. both acceptance cases (cold flap zero opens; warm 02:01Z low-corr unwind STILL FIRES); pyright ratchet back to 0. af544d4c closed owed 34(b): the vacuous test now drives evaluate-APPLY-evaluate, proven RED against the parent blob loaded as a scratch module (git show 0e30ca09:... - the git-stash red-check was a no-op once the fix was committed): pre-fix 13 opens/12 unwinds alternating, post-fix 1/0. DEPLOY verified from auto_update.log: incoming-code battery on merged tree 3423 passed/1 skipped in 536.90s, replay gate XV-000 clean, live 19:04:16Z; zero hedge fills since (and zero fills of any kind since 12:35Z through the 23:02Z status - honestly noted the tape was already quiet pre-deploy, so quiet-since is consistent-with, not proof-of). CORRECTIONS vs the session's own claims: estimator sample counts NOT persisted (HANDOFF rule 3 second sentence unshipped - samples nowhere in persistence.py; every boot re-colds, safe direction, owed 35a); FW-070 telemetry-dark (no gauge/panel, one log.warning; task #148 class alarm owned by cloud session; owed 35b); hedging.py:75 comment says FW-060 for the FW-070 latch (drift row). TOUCHED: NEW sources/session-20260807-hedge-churn-guards; NEW concepts/deadlock-discipline (the 5 operator rules; 4 self-blocking-gate instances in one week; FW-070 as first mechanism built to the rules); sources/session-20260806-hedge-thrash (sequel section 9, residual dispositions); concepts/zero-is-not-a-reading (2nd live firing + class fix; under-evidenced |rho|~1 joins the 0.0 sentinel; sources 4->5); concepts/two-paths-one-quantity (boundary of the class: agreement held, reading flapped; sources 4->5); concepts/adoption-is-not-enforcement (rule 5 discharged late + parent-blob red-check technique; sources 3->4); concepts/protective-senior-overlay (invariant under incident pressure; sources 2->3); synthesis/owed-measurements (34b/34c CLOSED with fired-first note, NEW item 35); entities/reason-code-registry (FW-070, 184->185, stale registry-chain callout resolved); entities/liquiditybot; synthesis/documentation-drift-register (FW-060 comment row + HANDOFF 'exactly per' inexactness row).

## [2026-08-07] ingest | P&L reconciliation (institutional-review ground phase) - four numbers, three series, one invisible fee channel; the perf ring is churn-clean

CONFIRMED ground findings filed (reports 1-2 of task wfgp8n380; read-only, file:line-cited; key numbers re-verified against 23:02Z status at filing). THE HEADLINE: the desk's 'NET P&L (ALL TIME)' -56.91 is NOT realized_total - it is liquiditybot_perf_net_usd, a ROLLING LAST-200 NON-HEDGE window (deque maxlen 200 full+truncating, oldest 07-22; hedge exclusion main.py:1588), and its panel description 'Cumulative realized P&L across every closed trade' is FALSE ON TWO AXES while the true monotonic realized_pnl_total (-208.22, deepened from -186.78 mid-incident-#1) is UNEXPORTED - 3.7x the tile. THE INVISIBLE CHANNEL: entry/hedge OPEN-leg fees go record_entry_fee -> cash_balance only (state.py:172-178, NO P&L counter anywhere); exit legs go record_realized_profit -> realized/daily/weekly/monthly. Churn in these terms: ~-$297 ALL fees (gross ~0), exit-leg ~-$147 visible in the realized family, open-leg ~-$150 visible ONLY in equity+fees_total; 08-07 whole day: 321 fills (159 hedge+162 exit), open-leg 157.84 = the equity-cliff(-318)-vs-daily(-164.38) gap, NOT a bucketing artifact (daily reset 00:00:30Z verified; churn wholly in the 08-07 bucket; 08-06 closed +0.56). Weekly -173.23 = daily + Mon-Thu -8.85, no W32 rollover; skim equity-neutral, losses skim nothing. Identities exact: equity 4615.33 = cash+savings+reserve+uPnL; status==state==equity.csv; balance-sheet arithmetic recorded WITHOUT interpretation (equity -384.82 from start vs fees_total 382.28 - interpretation belongs to the pending panel). PERF RING CHURN-CLEAN: perf.record_close sole call site inside 'if not pos.is_hedge:'; ZERO of 200 ring entries in the churn window (wr with/without window identical 8.00%); board reproduces digit-for-digit from persisted ring (8.00%/0.676/0.0588/-0.3490/57); pre-incident baseline WORSE (198 trades: 7.07%, PF 0.026, net -58.90) and both post-incident trades were WINS; the 57-streak dates 07-22->07-23, two weeks pre-incident. WIN RATE 8.0%/WORST STREAK 57 = the ORGANIC picture - never attribute it to the incidents (citation hazard filed). PARTIAL not adjudicated: ring is 66.5% one 07-22/23 cluster of unadjudicated provenance (QA-harness era) - owed 36c, label never delete. DELIBERATELY NOT FILED: ground report 3 (panel-truth stale/honest-zero/dead-wiring classification) and the four institutional lens reviews - pending the judge panel. TOUCHED: NEW sources/session-20260807-pnl-reconciliation; synthesis/open-contradictions-register (2 new citation hazards: named-series translation for every P&L figure; organic-not-incident win rate; sources 24->25); synthesis/owed-measurements (NEW item 36a/b/c); entities/liquiditybot (status block, equity 4615.18).

## [2026-08-07] note | In flight, unfiled by design: 5-master-judge adversarial panel + pytest-xdist parallel-battery experiment

Two work products exist and are deliberately NOT filed as facts yet, per governance rule 12's hypotheses-are-not-facts clause: (1) a 5-master-judge adversarial panel over the institutional review's findings and four lens reports (citadel/janestreet/virtu/twosigma - written, unadjudicated; nothing from them cited as fact in today's filings); (2) a pytest-xdist parallel-battery experiment (12-thread 5600X, -n 8). Outcomes get their own filing this session or a follow-up. Marker so the next session knows these are owed, not lost.

## [2026-08-07] ingest | Institutional Review Verdict — 5 judges, 6 areas, unanimous APPROVED_WITH_CONDITIONS

Filed sources/session-20260807-institutional-review (task wq55239mp: ground F1-F6 + 4 lenses + judges round1/finals/tally). Key adjudications: churn gross -13.37 not 0.00 (149 paired laps, ~95.7% fees); TWO churn mechanisms (12 residual warm-corr laps 01:56Z-11:35Z outlived the pair fix until cf454d5e); 25/40 fee constant matches NO Kraken row — correction SEQUENCED post-h432 (label-geometry coupling, ml/labeling.py:45-52); cf454d5e circulated record false on four verified counts; conviction 0/0 honest for a seam 1,100+ ML-070 explorations bypass; DRY_RUN fill-at-limit RNG = phantom quoter edge (markout sim-conditioned); UNADJUDICATED: era realized ledger 6/11 vs recent-30 story (contradiction #17). Plus filing-session ledger verification: the two filed 147-lap hedge incidents are ONE event double-filed local-vs-UTC (contradiction #19; all 159 lifetime hedge fills are 08-07 UTC; D3 committed 01:53Z after the event, deployed 02:08Z). Touched: pnl-reconciliation + hedge-thrash + hedge-churn-guards (supersession banners), two-paths-one-quantity, zero-is-not-a-reading, cost-truth (fee falsification), money-path-thesis, liquiditybot, contradictions register (#17/#18/#19 + 6 citation hazards), owed item 37 (panel conditions), documentation-drift register (4 new rows).

## [2026-08-07] create | The Paper/Real Boundary (nothing here executes) — operator directive filed as governance rule 13

Operator directive 2026-08-07, verbatim intent: 'make sure the Wiki knows it is not executing bids/positions itself but it is a big relation and datapoint that needs to be apparent in all of the corpus's mindset considering that is the point.' Filed as first-class cross-cutting concept concepts/paper-real-boundary: every fill/fee/queue/markout/RTT/dollar is SIMULATED (dry_run, fill-at-limit RNG, config-constant fees); the paper-vs-real boundary is THE central relation — the corpus rehearses real-money discipline on simulated execution; every filed conclusion states its side of the boundary; sim-conditioned numbers are never venue truth. Wired corpus-wide: governance-doctrine rule 13, risk-posture-doctrine frame section, liquiditybot identity block, money-path-thesis addendum, cost-truth, both hedge incident pages, vault CLAUDE.md/AGENTS.md domain rule 9 + standing-question hook.

## [2026-08-07] note | pytest-xdist adopted after evidence gate

Parallel battery -n 8 on the 5600X: 3423 passed / 1 skipped in 413s vs 623s serial control, identical results. Second confirming run pending before any serial default changes. (Recorded on sources/session-20260807-institutional-review; sim/venue boundary n/a — repo-side tooling measurement.)

## [2026-08-07] ingest | Capacity sweep round 1 (00bd0e52+101f7436) - two DoD gates were lying about themselves; xdist institutionalized; battery renices below the bot

COMMITS 00bd0e52 + 101f7436 (capacity-sweep round 1, throughput/hygiene half; coverage half unstarted). All repo-side - no sim or venue number in this filing. HEADLINE, gate integrity: TWO Definition-of-Done gates were lying about themselves. (1) Full-scope ruff RED on the live tree - cf454d5e's hedger snapshot section grew core/persistence.py restore() to C901 42>40 and nobody ran full-scope ruff after the pull; fixed by extracting _restore_subsystem_sections per the file's own convention. (2) The battery's pyright type-ratchet stage printed SKIPPED for weeks because the tool was never installed on the box, while CLAUDE.md claimed a zero-error ratchet - every local battery-green in that window asserted a type gate that did not run (the ratchet's zero was real only in cloud environments, e.g. cf454d5e's record); test_windows.bat now HARD-FAILS on a missing tool; pyright 1.1.411 in-venv, 0 errors on shipped scope, measured. A GATE THAT CAN QUIETLY NOT EXIST IS A GATE THAT LIES - same family as adoption-is-not-enforcement and the vacuous-test episode; the class filed as NEW concepts/false-green with three variants (skipped stage; vacuous test; false-green invocation - a Git Bash 'cmd /c test_windows.bat' run printed a banner and exited 0 without running any stage, so OUTPUT MUST BE READ, EXIT CODES ARE NOT EVIDENCE) plus the adjacent unrun-gate case. MATRIX HARDENING measured on the 5600X, full hardened matrix ALL GREEN end-to-end: pytest-xdist -n 8 INSTITUTIONALIZED (623s -> ~400s, two clean runs - closes the 08-07 'in flight, unfiled by design' marker; the one flake was a load-starved 5s harness timeout hardened to 30s in 00bd0e52, the test was innocent); battery priority -> BelowNormal because the LIVE runner runs BelowNormal and a Normal-priority battery OUTCOMPETED THE TRADING LOOP on all 12 threads during every verify cycle (PROFIT-PROTECTION, not speedup - renice the tests, never the bot); compileall -j 0 (9.32s -> 1.71s cold). DEFERRED as NEW owed item 38, none measured: (a) Defender exclusion A/B (needs admin; AV exclusion over repo/venv is a supply-chain exposure - measure first, price the tradeoff at decision time), (b) runner.log rotation at the supervisor spawn boundary (153.8MB, live append handle held so in-place rotation is unsafe), (c) pytest-cov coverage baseline (coverage of shipped scope NEVER measured - the sweep's whole second half), (d) venv pruning of the retired streamlit/pandas UI stack (~150-250MB, zero importers verified). TOUCHED: NEW sources/session-20260807-capacity-sweep; NEW concepts/false-green; concepts/adoption-is-not-enforcement (new section: the recursion's sharpest instance - the gate that quietly did not exist; sources 4->5); sources/session-20260807-hedge-churn-guards (6.6 addendum: the circulated record's 'ruff, pyright 0' line did not hold on the pulled tree - a battery record certifies its environment, not the deploy box; sources 1->2); synthesis/documentation-drift-register (2 rows: the CLAUDE.md ratchet claim, the cf454d5e battery record vs the local tree; sources 14->15); synthesis/owed-measurements (NEW item 38a-d; sources 32->33); index regenerated 155->157 pages.

## [2026-08-07] ingest | Evening ops session 2026-08-07 (48a63610) - rotation verified live, the auto_update local-commit blind spot, the REST _deny RST class, the fee-ledger topology, the venv shim pairs

NEW sources/session-20260807-evening-ops (five confirmed findings, all evidence re-verified on the box at filing time). (1) Child-log rotation shipped at the spawn boundary AND verified live 15 minutes after commit: supervisor log 19:49:32 'rotated runner.log (64MB cap)', the ~154MB archive on disk as runner.log.1, fresh runner.log growing - owed item 38(b) CLOSED by measurement. (2) auto_update local-commit blind spot: decide() 'current'/'ahead' paths never touch the runner, only externally-pushed commits reach _signal_restart, while pushers bounce on ANY rev change - committed is not deployed; 48a63610 deployed only because its one file was pc_supervisor.py (the single self-restarting file); its own commit message ('the normal auto_update bounce') filed as a drift-register row, entity page corrected ('the code is already live' is FALSE). (3) The recurring test_audit_security flake root-caused: _deny closes with the POST body unread (deliberate anti-smuggling, ab76cdfb) -> TCP RST can destroy the in-flight refusal response under -n 8 load; survived the 30s-timeout fix which rules timeout out; fix decision owed as NEW item 39 (bounded drain-then-close vs harness RST tolerance + red-first pin). (4) fees_total write topology verified at file:line: one counter, exactly two writers (entry legs main.py:1935 paired with the record_entry_fee cash-only debit, exit legs main.py:1980 netted into realized) - fees_total is the ONLY complete fee ledger; money-path fee identity (-384.67 vs 382.28) confirmed well-founded; addendum on the P&L reconciliation page. (5) venv shim process pairs verified live: 10 OS processes = 5 logical (shim -> base interpreter, identical command lines); supervisor Popen tracks the shim while runner.lock names the base (pid 23020); pusher bounce kills both halves only by accident of command-line propagation; rotation's held-handle contract is a pair property. Touched: sources/session-20260807-evening-ops (new), entities/auto-update, entities/observability-sidecars, synthesis/owed-measurements (38(b) closed, 39 opened), synthesis/documentation-drift-register (new row), sources/session-20260807-pnl-reconciliation (addendum), synthesis/the-money-path-thesis (foundation note), index. Paper/real boundary: findings 1-3 and 5 repo/box-side; finding 4 topology repo-side with sim-side dollars. Battery at commit: 3427 passed / 1 failed (the finding-3 class) / 1 skipped in 400.57s -n 8.

## [2026-08-07] ingest | Fleet night sweep 2026-08-07 - fill-sim TTL skew (CRITICAL), the losing-even-with-gifts reframe, frozen inputs, dead latency gates, first coverage baseline

EVERY headline claim re-verified against the box before filing; three transcript claims REFUTED and filed as refutations, not findings. (1) FILL-SIM TTL SKEW, the #1 P&L-integrity item (owed 40): sf_base=0.048 calibrated at n_bar=5 (25s life, outputs/fill_calibration.json - identity re-derived exactly: 0.048*exp(-0.544)=0.028/poll, 1-(1-0.028)^5=0.131=f_hat) but drawn PER POLL for the order's whole life (order_manager.py _poll_dry), while long-book bids live 6h (config order_ttl_hours=6.0, main.py:5371) = ~4,320 polls -> compounded fill prob ~1.0; PLUS _sim_maker_cross (order_manager.py:1085, called :1220) deterministically fills FULL remaining, no depth/queue constraint, on the SAME trade-through predicate calibrate_fills.py measured (:81-91) - double-count; ledger signature verified with one correction: 22/41 post-08-03 entries at exactly -50.0bps (= add_offset_pct) + 2 at -58.7 (fleet's '24/41 exact' conflated these), all post_only, BTC 13 / ETH 9; markout +3.58bps@5s pooled (ETH +14.8 / BTC +11.2) fleet-measured-not-re-derived, mechanism now named for the panel's 'sim physics' verdict. Fix mints a THIRD execution-era boundary when it lands. (2) THE REFRAME, verified exactly against status.json performance.by_asset: every asset negative expectancy except AVAX (n=3) - BTC 0/17 exp -0.8312, ETH 3/26 exp -0.6393, PF 0.0-0.119 - the sim-gifted assets are the WORST books: no paper edge is being manufactured; sim optimism is one-way, so every paper number is an UPPER BOUND on a book that already loses (money-path addendum). (3) INPUT-FEED SKEW (owed 41): moomoo appends frozen closed-market quotes unconditionally (moomoo_feed.py:218-272; live log: identical +3.60% basket for hours, z collapsed to +0.00; ~62h weekend ahead); sentiment volume gate STRUCTURALLY DEAD (per-source caps saturate at items=200 every observed poll -> vol_z=0 -> fear/euphoria spikes can never fire, scanner.py:275-292); opt_iv_skew pinned at -3.00 clip bound (live log); feed failure byte-identical to CONTEXT_NEUTRAL padding on the ML path (main.py:5703-5718 reads no .available; ml/features.py:50-57); _warm_start (data/context_engine.py:566) the one correct restart pattern, ~1 of 6 windows. (4) LATENCY (owed 42): pre-trade staleness veto arithmetically dead - book_ts=now vs the same frozen now (main.py:2420 vs :4403), always ~0ms against pretrade's 4000ms ceiling (pretrade.py:96,236); marks_age_sec live 0.0 with .get(s,now) making a MISSING mark read fresh; cycle_lifetime is a counter, no cycle-duration telemetry exists; POSITIVE: main fill path look-ahead-free (single orders.poll site main.py:2459, verified count=1). (5) REST _deny RST already owed 39, nothing new. (6) 20-transcript sweep (~200 bugs) adjudicated: REGISTERED (owed 43) CRLF bundle port unconfirmed (.gitattributes has no binary pin), registry ok=None accepted-not-blocked (ml/registry.py:84,244), min_corr no hysteresis (hedging.py:44,208,294), GBT l2=3.0 hand-tuned against the overfit battery (models.py:501,508-513 - OF-1 not independent evidence for GBT); REFUTED on current tree: 'no hash chain' (chain exists since 4799bfc7), 'mtf_align daily_candles never passed' (passed at main.py:4222+5338, populated :5885), 'skim per-leg bleed' (closed 30c); ML-070 bypass already owed 37e. (7) COVERAGE BASELINE closes owed 38(c): 17,789 stmts, 88% re-verified from the box's .coverage; least-covered: grpc_server 26, kraken_feed 49, binanceus_feed 59, scanner 59, algos 60; the instrumented run's 3 fails = overfit_check subprocess 120s timeouts under ~1.7x overhead, green in clean battery. (8) FINANCIAL VERDICT: strategy not making money on realized sim-side evidence, fee-dominated; fee constants stay HELD behind h432 (37a). Pages: NEW sources/session-20260807-fleet-findings; updated owed-measurements (38c closed; 40-43 added), money-path-thesis (08-07 night addendum), paper-real-boundary (fills row rewritten with the two-path mechanism; rule 4 sharpened), long-book (second reading: benign provenance, skewed evidence), zero-is-not-a-reading (input-plane wing: absence/staleness/saturation/clipping), tautological-instrument (clock-shaped specimens), open-contradictions-register (#20 RESOLVED both-true-different-layers); index regenerated (159 pages).

## [2026-08-07] ingest | Closing batch 2026-08-07 night (48a63610 -> 1e7f882c -> 486a6891 -> 915b362f) - Defender verdict adopted, latency truth tier 1 live-verified, the pandas the grep could not see

NEW sources/session-20260807-closing-batch (all six items re-verified against the box: git show, Defender event log 5007, runner.log + pc_supervisor.log, status.json, site-packages, config.json). CLOSED: owed 36(a) via 486a6891 boards v37 (with correction - realized_total was exported all along, the gap was display); 38(a) Defender A/B measured 401.30s vs 375.39s = +6.9% caveated, posture ADOPTED, event log proved the years-old broad exclusion made every historical battery baseline effectively unscanned; 38(d) venv prune executed with its premise part-refuted (pandas is a moomoo runtime KEEP - hard sys.exit at import, never declared to pip; six removals stand); 39 via 1e7f882c bounded-drain (RST flake class dead; successor load-marginal flake test_feed_concurrency registered); 43(a) CRLF pin existed since 4a42d2c2 2026-07-18 at telemetry_backup.py:246 - wrong layer searched; July transcript item 70 resolved (adaptive_gbt.enabled true). UPDATED: owed 42 (tier 1: 42b/42c closed, 42d instrumented FW-080, 42a open; new 42(e) restart-warmup race - 3.5min cold warmup vs stale=120s); concepts/tautological-instrument (marks_age specimen repaired + live-proven: 16.7s climbing while stopped, cycle max 45.56 caught the warmup stall); concepts/liveness-by-output-cadence (second firing - displaced a warming runner); concepts/false-green (4th specimen: the blind verification - grep + silent pip check vs vendor SDK runtime graph); concepts/conscious-re-baseline (environment-posture extension); entities/reason-code-registry (FW-080, 185->186); pnl-reconciliation + fleet-findings addenda. Next-session queue unchanged: fill-sim TTL (owed 40) on top.

## [2026-08-08] ingest | Morning batch 2026-08-08 (3cfe0710 + 050421a7) - execution-era boundary #3 minted (fill-sim TTL normalization, owed 40 CLOSED), false-green specimen #5 CRITICAL (the battery's pytest gate never fired)

NEW sources/session-20260808-morning-batch (operator-dictated batch; every item re-verified against the box: git show both commits, _passive_poll_prob read in full, config.json:370, pytest --collect-only on both new test files, test_windows.bat, runner.log, pc_supervisor.log, status.json, runner.lock, pushers_code_rev.txt; head = remote = 050421a7 verified). (1) OWED 40 CLOSED via 3cfe0710: _passive_poll_prob TTL-normalizes the passive hazard - p = 1-(1-sf_base*exp(-d/sigma))**min(cal_life/ttl, 1.0) - per-ORDER fill prob TTL-invariant at the calibrated F(25s); ttl==cal_life bit-identical (5m book + G1-G5, no re-baseline); exponent clamped at 1.0; sf_base=1.0 deterministic test-mode bypass; sim_fill.calibration_life_sec=25.0 with era doc; double-count (b) disposed by design (_sim_maker_cross = genuine trade-through, hazard = conservative floor); EXECUTION-ERA BOUNDARY #3 minted (after QA quarantine + XV-021 ts~1785717000) - label cohorts cut at 2026-08-08; XV-023 opened as owed 40b (per-TTL recalibration, interacts 13c/23b). TWO FILING CORRECTIONS against the box: test_fill_ttl_normalization.py collects 7 tests not the claimed 8 (3438+11=3449 confirms), and the resume snapshot was 2.1 min old not 6s (runner.log's own line). (2) FALSE-GREEN SPECIMEN #5, CRITICAL, via 050421a7: `start /b /wait "" cmd || (...)` satisfies || with start's LAUNCH success - the battery's pytest arm could NEVER fire; window 101f7436 (08-07, the 'repair two lying gates' commit itself) -> 050421a7; found LIVE when a red pytest (the pbo flake) sailed to ALL GREEN - first false arm the matrix ever produced; every earlier failed battery was caught by LATER stages (a lying gate survives while it is never the last line of defense - new design rule 6: prove the failure arm two-sided live + fence the treacherous form); fixed with `if errorlevel 1`, proven two-sided live; tests/test_battery_gate.py (4) pins cmd semantics both ways AND bans the construct; gotcha filed: inline cmd /c "start /b /wait" DEADLOCKS under captured pipes (3x 60s TimeoutExpired) - must run from a real .bat. (3) pbo flake reconfirmed load-marginal (test_schema_ab_flag... fails -n 8 at 33s inner 'passed 7, failed 1', passes solo 60.33s) - registered as second member of the owed-39-successor family. (4) Runner bounced onto 050421a7: graceful stop 11:08:17, resumed 11:10:22, 2 positions restored, RUNNING DRY_RUN, marks_age_sec/cycle_duration_sec reading real values, no import deaths - every long-book order from this boot priced by the honest simulator. (5) Battery through the HONEST gate 3449/0/1 in 349.51s, smoke 219, ALL GATES PASS; both commits pushed. Boundary: item 1 sim-side (instrument change), 2-3 repo-side, 4 box-side ops with sim-side dollars. TOUCHED: NEW sources/session-20260808-morning-batch; synthesis/owed-measurements (40 closed, 40b/XV-023 opened, 39-family second member, item 1b second cut; sources 36->37); concepts/false-green (specimen #5 + survival mechanism + gotcha + design rule 6; 4->5); entities/long-book (third reading: gift dead; 4->5); concepts/paper-real-boundary (fills row repaired-state, rule 4 third boundary; 4->5); synthesis/the-money-path-thesis (08-08 addendum: embargo narrows to pre-boundary rows, upper-bound reframe stands; 13->14); sources/session-20260807-fleet-findings (closure banner on section 1; 1->2); vault CLAUDE.md + AGENTS.md standing question 4 rewritten (three execution-era boundaries). Index regenerated 160->161 pages. Queue: input-feed docket (41) next, then 42a + 42e, ret_pct/bars_held (37g), cf454d5e repairs (37b); fee constants HELD behind h432 (37a).

## [2026-08-08] ingest | The weekly-budget lockout and the audited re-anchor (f07d60f8) - bug-attributable consumption gets its own verb; RP-042; the honest gate's rotating flakes; 41a tests parked

NEW sources/session-20260808-budget-reanchor (operator-dictated docket; every claim re-verified against the box: git show f07d60f8, protocols/runner/runtime/codes/rest_server at cited lines, pytest --collect-only, runner.log:24540, audit.jsonl:37995 seq 37983, status.json, equity.csv Monday-open, config.json:233-234, the parked file's existence). (1) INCIDENT: the ADA hedge-churn class's ~$303 of simulated W32 fees (panel-canonical 301.31 + residual laps) drove weekly_budget_used_frac to 1.0906 (1.0921 pre-reanchor; arithmetic closes against the box: anchor $4,940.59 from equity.csv x 6% budget = $296.4, drop $323.6 -> 1.0916) with taper_mult 0.0 - ALL entries blocked, unclearable by restart (equity-anchored persisted state), natural release only at the W33 rollover. The lockout is 100% bug-attributable (without the bug frac ~0.07 vs taper_start 0.5). FILING CORRECTION: 'week net POSITIVE without the bug' is a hair too strong AND crosses two series - equity axis ~-$21, weekly_pnl axis ~-$23 (only exit-leg ~$150 lives in weekly_pnl per the three-series taxonomy); essentially FLAT, not positive; the decision survives. (2) MECHANISM f07d60f8 (pushed, 13:09 local): ControlChannel verb budget_reanchor_week -> RiskProtocolStack.reanchor_week(equity) (protocols.py:238-255) - anchor ONLY (weekly_pnl/pools/day-budget/learning untouched, ISO rollover preserved, degenerate equity refused); reason REQUIRED (refused without); audited RP-042 with equity+reason (codes.py:221, registry 186->187 verified by scan); registered in BOTH vocabulary halves (runtime.py:48 + runner.py:74 - the silent-drop drift class, pinned); deliberately ABSENT from rest_server ALLOWED_CONTROL (arm_live posture, pinned). tests/test_budget_reanchor.py: 8 red-first (docket claimed 9; collection says 8 - same correction class as the morning batch's 8->7). (3) EXECUTED LIVE 13:13:10 local: re-anchored at $4,617.00; ack in runner.log carries the FULL reason; audit seq 37983 hash-chained (h 9acb9c6b / prev a8270138); command id 1786212788.674852-e82d3b session-reported (control file consumed; audit ts 1786212790.778 corroborates within ~2s); weekly_used 1.0921->0.0001 (box at filing 0.0004 at equity $4,616.90 - the new anchor working), taper 0.0->1.0, weekly_pnl -173.36 UNCHANGED = the no-ledger-touch proof. (4) HONEST-GATE AFTERMATH: the ship cycle's batteries went red-clean-red on ROTATING load-marginal timing tests (pbo schema-AB, 18/18 solo beside a running battery; throttle burst, 4/4 solo 7.7s) - the family is now the batteries' binding constraint; shipped with disclosure per the 48a63610 precedent, no blanket retries; NEW owed item 44 (battery split: parallel -m 'not timing' + gated SERIAL -m timing, both arms held to false-green design rules). (5) DOCKET 41a: freeze-gate tests WRITTEN and PARKED as test_feed_freeze_gate.py.parked in the session scratchpad (session-scoped - copy out before cleanup); must return to tests/ when the moomoo gate implementation resumes next; noted on the owed item so it is not lost. Boundary: dollars sim-side, mechanism repo-side, execution box-side ops; the lockout itself was real. TOUCHED: NEW sources/session-20260808-budget-reanchor; synthesis/owed-measurements (item 44 NEW, 39-family third member + escalation, 41a parked note; sources 37->38); entities/reason-code-registry (RP-042 newest, 186->187; sources 11->12); concepts/false-green (aftermath section: what an honest gate costs; sources 5->6); sources/session-20260807-hedge-churn-guards (5bis: the churn's last bill - a churn's cost has a tail in every stateful layer that consumed it; sources 2->3); sources/session-20260807-pnl-reconciliation (addendum: the taxonomy's first operational test - proof AND correction; sources 1->2); entities/liquiditybot (08-08 status block; sources 22->23). Index regenerated 161->162 pages.

## [2026-08-08] ingest | Battery split + moomoo frozen-quote gate (be341867 + 01d59908) - owed 44 CLOSED, docket 41a SHIPPED, DF- family born, the 14:10 pushers-only bounce watched confirm the local-commit blind spot

NEW sources/session-20260808-battery-split-freeze-gate (both commits re-verified against the box: git show both, pyproject.toml marker block, test_windows.bat:39-45, moomoo_feed.py at cited lines, codes.py scan = 189, grep quotes_frozen over runner/main/gc_pusher = absent, collected test names, auto_update.log, runner.log, pc_supervisor.log, runner.lock; head = remote = 01d59908). (1) OWED 44 CLOSED via be341867, exactly as specced: the load-marginal timing family = 17 tests / 7 files tagged by MECHANISM (hard 120s subprocess wall timeouts on overfit_check CLI children = the TimeoutExpired class - test_pbo_variants CLI x3 + test_overfit_check_ci x3; burst/thread-gap compression from a worker descheduled between throttle release and stamp - test_concurrency_throttle; upper-bounded elapsed asserts - test_feed_concurrency, test_audit_data x3, test_throttle_threadsafe, test_pc_supervisor_lock; starvable heartbeat thread - pc_supervisor live-peer refusal); lower-bounded elapsed tests deliberately STAY parallel (load only grows them); timing marker registered STRICT in pyproject.toml (a typo is a collection ERROR, never a silent rejoin); the bat runs parallel -n 8 -m "not timing" + SERIAL -m timing, each behind its own honest `if errorlevel 1` gate, BelowNormal; split pinned by test_battery_gate.py now 5 (exactly two passes, parallel excludes timing, timing serial, honest form both, construct ban). FIRST SPLIT BATTERY FULLY GREEN ZERO-FLAKE: parallel 3445 passed / 1 skipped in 3:28 + serial 17/17 in 3:07; arithmetic exact (3459 collected at split commit + 4 freeze-gate tests = 3463 = 3445+1+17). Scheduling changed, the gate did not - no retry, no widening. (2) DOCKET 41a SHIPPED via 01d59908: full-basket per-ticker-return equality vs the previous poll = the closed-market signature (one name moving is not a freeze); frozen polls do NOT append, so z HOLDS its last honest value - the +0.39->0.00 repetition-decay defect is dead; available stays True + additive snapshot field quotes_frozen; DF-010/DF-011 latched transition codes = the DF- (data feed) family born, registry 187->189 verified by scan; options gate on raw (pcr, oi_pcr) equality, append-skip only; red-first test_feed_freeze_gate.py 4/4 red on the pre-fix tree (AttributeError: quotes_frozen) -> 4/4 green, test_moomoo_failfast 5/5 intact; the 08-08 morning PARKED file RETURNED to tests/ and is committed in the fix - parked-file notes cleared on budget-reanchor section 6 and owed 41a; 41c persistence stays deliberately sequenced AFTER the gate; status.json moomoo block does NOT yet carry quotes_frozen (rides with 41b - until then DF-010/DF-011 are the only operator-visible freeze evidence). (3) DEPLOY - one docket claim corrected AND adjudicated by measurement at filing: the 14:10 auto_update cycle was WATCHED land (14:10:03 already up to date / 14:10:04 pushers bounced for rev 01d59908, runner pid 22740 untouched) = third measured confirmation of the local-commit blind spot; the runner's actual deploy path today is ControlChannel stop -> supervisor relaunch (13:09:24 -> 13:11:57 for f07d60f8 - which also explains how the 13:13:10 RP-042 ack ran on a verb committed 13:09); the freeze gate is committed-not-running at filing; runner bounce before US close = session intent, confirmation owed on the 41a closure note. Boundary: both findings repo-side (harness plane / feed adapter); the moomoo quotes are real venue-data-side inputs; no sim dollar quoted in this filing. TOUCHED: NEW sources/session-20260808-battery-split-freeze-gate; synthesis/owed-measurements (44 closed same-day, 41a closed + parked note struck, deploy adjudication; sources 38->39); sources/session-20260808-budget-reanchor (sections 5+6 resolution banners; 1->2); sources/session-20260807-fleet-findings (section 3 moomoo closure banner; 2->3); entities/reason-code-registry (DF-010/DF-011 newest section, DF- family added to the families line, 187->189; 12->13); concepts/zero-is-not-a-reading (input-plane wing's first shipped repair - repetition is not a reading either; staleness spelling closed, absence/saturation/clipping remain; 6->7); concepts/false-green (aftermath sequel: item 44 shipped by scheduling, not tolerance; 6->7); entities/overfit-check (its CLI tests as the timing family's largest bloc; 7->8); entities/auto-update (third measured blind-spot confirmation, watched in real time; 6->7). Index regenerated 162->163 pages.

## [2026-08-08] ingest | Institutional/government data adjudication 2026-08-08 - six ADOPTs at 0 DoF, the SKIP ledger, ETF-flows availability reversal, ContextFeed agility verdict, owed family 45a-45f

NEW sources/session-20260808-institutional-data-adjudication (operator-requested; three deep-research agents, endpoints live-verified by the agents; research-side/venue-data-side, no sim number quoted, nothing shipped). SIX ADOPTs, all telemetry-first at 0 model DoF under the CLOSED 2026-07-24 ledger: (1) CME basis + perp funding EXTREMES crash-risk dial - convergent #1 across all three agents (BIS WP 1087 Mgmt Sci 2026 high carry predicts crashes; Chi et al. JFM 2023 basis strongest cross-sectional predictor); basis free via Yahoo BTC=F (live 200, ~15min delay) vs Kraken spot; funding_rate ALREADY a feature but the asymmetric extreme-funding veto consumer does not exist = risk-gate build 0 DoF; KEY REINTERPRETATION binding on future COT reads - CME leveraged-fund net shorts are basis-trade mechanics NOT bearishness, reading COT directionally is a category error; (2) BLS CPI/NFP into the existing FOMC event-gate machinery (minutes-scale response post-2020; NY Fed SR 1052 regime caveat; highest value-per-effort); (3) US spot ETF daily flows - REVERSES the 07-24 availability rejection on exactly its stated revisit terms (Lim SSRN 6592830: $100M ~ 53bp same-day, ~21% of variance, preprint-grade; Farside browser-UA scrape ~666 rows verified + SoSoValue ~20/min backup; CRITICAL lookahead hazard - flows publish evening/next-morning NOT 4pm ET, consume as 5-day z/streaks); (4) OFR FSI daily CSV T+2 (credit/funding sub-columns the new info vs VIX, incremental-value test conditional) + FRED batch NFCI/DFII10/BAMLH0A0HYM2 120/min; (5) EDGAR 8-K watchlist poller (getcurrent Atom + efts, minutes latency, 403 without name+email UA verified first-hand, 10 req/s; our ContextFeed _UA says contact:none which FAILS SEC policy); (6) TFF COT crypto categories on Socrata gpe5-46if (live current-week rows; Disaggregated has ZERO crypto rows - premise corrected; 2025 shutdown precedent = multi-week gaps the ingester must tolerate; weekly regime dial only). THIRTEEN SKIPs each with killing citation, incl. COIN/MSTR options-crypto transmission at ZERO evidence -> the three shipped opt_pcr_z/opt_oi_pcr_z/opt_iv_skew features are now schema-AB PRUNE CANDIDATES (INFO-arm first, no schema churn until h432); aggregate stablecoin issuance (Lyons & Viswanath-Natraj endogenous - stable_wk_pct dial stays 0 DoF, never graduates); 13F/N-PORT/Form PF lags; equity-leads-by-HOURS (documented transmission is minutes, any hourly lead is overfit); kimchi premium (-0.06); Glassnode/CryptoQuant paid now; CME JSON 403 bot-walled; Binance 451. DoF ARITHMETIC: hundreds of labels fund ~2-5 effective context features TOTAL (Peduzzi EPV + DSR/PBO effective trials); funding/basis/COT/DVOL ~ 1.5 effective; 64 features vs ~61 fresh-era labels = ledger CLOSED. AGILITY VERDICT: ContextFeed IS the designed seam (5 keyless sources, 3x-grace known=False, poll budget, injectable fetch, CX codes; the gov agent's dials-go-stale-not-frozen recommendation is ALREADY the known=False discipline); gaps: (a) UA config-lift with operator contact, (b) per-source wider-than-3x grace for shutdown-class weekly gaps, (c) corpus injection deliberately GATED - a feature not a defect. QUEUE: NEW owed item 45 (45a-45f, all telemetry-first) sequenced BEHIND 41b/41c/42a/42e/37g/37b, nothing touches the feature schema before the h432 verdict. TOUCHED: NEW sources/session-20260808-institutional-data-adjudication (with durable endpoint/gotcha spec table: UAs, rate limits, publication timings, Socrata IDs, fragility grades); NEW entities/contextfeed; concepts/dof-budget (effective-DoF section, ledger CLOSED; 3->4); concepts/availability-failure-mode (first recorded reversal + 3 new kills + UA-conditional middle class; 1->2); sources/compounder-context-evidence (2026-08-08 supersessions block: ETF reversed, COT reinterpreted, stablecoin demoted, 3-4-features allowance moot; 1->2); concepts/evidence-grading-ladder (durability rule's first live test; 2->3); synthesis/owed-measurements (item 45 NEW; 39->40). Index regenerated 163->165 pages.

## [2026-08-08] ingest | Evening queue execution (2026-08-08) - owed 41b (64724480) and 41c (e22df720) SHIPPED and CLOSED

New source sources/session-20260808-evening-availability-persistence. 41b: context-feed availability recorded on every corpus row at ZERO model DoF (ledger stays closed) - _feature_extras {web,equity,options,frozen} truth dict rides gate_components' proven plumbing (candidate dict, all three order-meta stashes incl. ladder rungs via threaded feat_avail, pending 9-tuple) into 4 trailing bookkeeping columns avail_web/avail_equity/avail_options/quotes_frozen; '' = UNKNOWN strictly distinct from '0' = measured down; DF-020/DF-021 latched episode codes (registry 189->191); runner status moomoo block now carries quotes_frozen (41a visibility deferral discharged). Battery earned its keep: first red run exposed core/persistence.py's FIXED-SHAPE pending-tuple rebuild (would silently drop the 9th slot every restart - the class that ate gate_components pre-T4), fixed + pinned; migrate_history.py pads the 4 columns blank; three red batteries ALL legitimate downstream schema pins, zero timing-family flakes across four batteries (owed-44 split holding); header change rotates production file on deploy, recover_local_baks merges via marker. 41c: moomoo z-windows + freeze state persist via MoomooFeed.to_dict/from_dict + StateStore moomoo_state (method-guarded, fail-soft; poll timestamps deliberately NOT persisted - restored _last_per classifies the immediate re-poll); closes fleet-measured ~3.5h/day empty-window rebuild hole (median 0.5h restart cadence); 41a x 41c composition pinned by test (still-frozen market reads frozen on first post-restart poll, never re-seeded); 5 tests test_moomoo_persistence.py. Runner bounce onto e22df720 sent ~17:4x local, supervisor relaunch pending - carries 41a+41b+41c through the ~62h weekend window. Register: 41b/41c CLOSED, 41d/41e re-lettered and open (sentiment vol_z saturation, opt_iv_skew clip rail); queue continues 42a/42e -> 37g -> 37b -> 45a-45f. Touched: owed-measurements, battery-split-freeze-gate, fleet-findings, reason-code-registry, dof-budget, zero-is-not-a-reading, historystore, overfit-check, index. Boundary: both commits repo-side; avail flags record venue-data-side feed truth; no sim dollars quoted.

## [2026-08-09] ingest | Corpus corruption incident + fixes (3c0debd7), the 42a audit, and an IN-PLACE CORRECTION of the false root cause filed 08-08

NEW sources/session-20260809-corpus-corruption (every headline claim re-verified against the box at filing: git log/show 3c0debd7 + 36fcfd6e, the migrator's new idempotence comment read in full at scripts/migrate_history.py:110-140, scripts/session_import.py:244, scripts/overfit_check.py:1-15 + :180-182/:207/:228, config.json:340/773/887-888/1059, core/config_guard.py:2844-2878, git log 7486ab29, the @pytest.mark.timing inventory across 8 files; head = 3c0debd7). (1) THE INCIDENT, CRITICAL and SELF-INFLICTED: migrate_history.py:125 recomputed label_era unconditionally as label_era_of(barrier) - the ONLY non-idempotent trailing column in migrate_rows, violating an idempotence rule documented in the pt_frac comment IMMEDIATELY BELOW it, with the other 19 trailing columns as correct worked examples. label_era_of() has no horizon knowledge (unqualified "triple_barrier" for any tb_*) while the writer ml/history.py _row_era -> triple_barrier_era(label_max_bars) persists "triple_barrier_h432". TRIGGER: the session's OWN 41b commit 64724480 (+4 cols) -> _ensure_schema rotation 20:01:30 -> corpus_sync recover_local_baks merged the .bak back THROUGH migrate_rows 20:01:46 (16 seconds). BLAST RADIUS verified twice independently (position_id join AND re-running migrate_rows on the real bak): 2,729 rows, h24->pooled 2,077 + h432->pooled 652, ZERO rows lost, one bucket pooling THREE incompatible label definitions. CONSEQUENCE CHAIN, each link measured: current-era 690->42 < min_new_era_rows=150 -> era filter DISARMED -> training load 690->9,746 -> live_clean 5->299 -> min_live_rows cleared for gbt(60)/blend(60)/mlp(150)/adaptive_gbt(250) ALL FOUR IN ONE STEP (adaptive_gbt's 250 floor had never cleared in any document in this corpus) -> gbt champion DEPLOYED 20:10:44 on a DATA BUG, nine minutes fourteen seconds after the merge; the same disarm flipped overfit_check synthetic->live and reddened the battery. FIXED in 3c0debd7 (pass persisted era through, derive only when absent; also session_import.py:244 which runs HOURLY UNATTENDED) with 3 red-first tests in test_migrate_history.py - persisted-era preserved, MIGRATION IS A FIXED POINT (the class gate), legacy row still derives. CORPUS REPAIRED: 2,729 cells from .bak_1785879005.recovered + .bak_1786237290.recovered, position_id join, most-qualified-wins, 0 conflicts, 0 rows added/removed/reordered, no other cell touched, concurrent-append-safe (the live runner was appending), prerepair backup signal_history.csv.prerepair_1786253662 retained; verified after - era armed=True/active=True, load 9,746->690, live_clean 299->6. Re-corruption risk CLOSED (pc_supervisor _spawn:657 spawns corpus_sync as a fresh process - no stale in-memory code hazard). (2) IN-PLACE CORRECTION of sources/session-20260808-night-staleness-overfit: its 60-row synthetic->live root cause is FALSE IN BOTH HALVES - the predicate is len(X) >= len(FEATURE_NAMES)*10 = 640 and len(X) is LOADED rows not live rows; the flat 60 was DELETED 2026-07-11 by 7486ab29; the corpus holds 305 live rows total and is append-only so the battery's printed "live rows=467" was arithmetically IMPOSSIBLE; 33 rows appended (all candidate) between the 17:06 and 23:30 batteries while loaded went 467->9,739 = the DISARM. Struck not deleted (the retraction record is preserved), banner added, §1's known-limits and ship-disclosure also corrected, Related rewired. The two stale strings that made it plausible are fixed at source (docstring :9, report string :216). (3) THE HONEST GATE VERDICT on the REPAIRED corpus, NO THRESHOLD MOVED: 3 pass / 4 fail - OF-1 +0.422/+0.414/+0.503 WORSE than the pooled corpus's +0.19..+0.27 (the correct direction: the pool was flattered by ~9,000 other-era rows), OF-7 dead_frac 0.95 (61 of 64 features), OF-7 rows/feature 10.8 PASSES BARELY, shuffle+purge PASS; the audit's own learning curve reads CLIMBING (delta_auc=+0.112, "data-starved") = the DoF CLOSED-ledger adjudication restated by an independent instrument that was not told the answer. Deploy gate (auto_update.battery_passes) BLOCKED; 3 policy options registered NOT decided. (4) NEW OWED 47, THE WEDGED CHAMPION: train_meta correctly re-gated to ['logistic'] (live=6, total=692) but the champion gate REJECTED the swap - challenger 0.2714 (clean 692 rows) vs champion 0.1537 (CORRUPTED pooled 9,708 rows); incommensurable evaluation sets, the bug-promoted gbt is WEDGED, no clean challenger can dislodge it; the gate was deliberately NOT overridden (re-baselining is a conscious operator act); the ML governor still grades on realized outcomes as the safety net. (5) 42a AUDIT: CRITICAL-latent VETO BAND FIXED - kraken_max_book_age_sec 5.0 > pretrade.max_data_staleness_ms 4000ms meant 4-5s books were SERVED then VETOED while PREEMPTING a fresh REST read (main.py falls back to REST only when the ws returns None), ~0.6-3% of entry evaluations, MINA 3.2% FLOW 2.9% PAXG/LINK 1.9% BTC 0.6%, skewing WHICH ASSETS can accumulate fill labels; masked only by a full 5/5 book, would have armed on the first close; fixed 5.0->3.5 PLUS a config_guard FATAL on the RELATION itself (verified two-sided); config_guard:2835-2848 prose and tests/test_audit_fixes.py's test NAME both still asserted the falsified premise - both rewritten. THREE KNOWN LIMITS filed honestly (the genuine gain is the WS path only): REST sign inversion (staleness_ms <= 0 for any book fetched this cycle; a 50s hang reads -50000ms), the pre-42a code was NOT tautological on the FAILURE path (it grew ~5s/cycle - precisely the path the commit message led with), DL-10 cannot benefit (capped at 3.5s vs stale_critical_sec=120). (6) OWED-44 GAP CLOSED: tests/test_import_integrity.py was never tagged @pytest.mark.timing, went red on TimeoutExpired, and is the most SELF-saturating test in the suite (8 threads x ~100 fresh interpreter spawns, hard 120s wall, inside the -n 8 pass beside the live BelowNormal runner; solo 4.3s) - now serial, timing family 17->18 across 8 files; --strict-markers catches a typo but cannot see an absence. (7) PROCESS LESSON: 36fcfd6e's commit message asserted "the identical red reproduces on the parent commit" - ASSERTED, NEVER RUN; running it would have made the +9,272-row jump unmissable that same evening. Disclosure precedent tightened: a stage turning red FOR THE FIRST TIME is a blocking investigation, not a disclosable footnote (design rule 7), and any orthogonality / reproduces-on-parent claim must ship with the command that produced it (design rule 8). BATTERY: pytest 3466+1 parallel / 18 serial timing, smoke 219, assurance, ruff, pyright 0 errors, bandit, compileall, quant G1-G5 ALL GREEN; overfit honestly RED. Committed and pushed 3c0debd7; runner bounce sent, relaunch onto 3c0debd7 UNCONFIRMED at filing (committed != running). BOUNDARY: the incident is repo-side (a migrator defect) and box-side (the repair against the live corpus file); NO sim dollar is quoted; the corrupted and repaired rows are training-corpus rows whose live entries are sim-execution-conditioned by construction; the veto-band exposure percentages are venue-data-side facts about real Kraken feeds. TOUCHED: NEW sources/session-20260809-corpus-corruption; NEW concepts/migration-idempotence (the class this incident mints - a migrator that is not a fixed point is a data-destruction loop; record integrity vs MEANING integrity, with the table of five defenses that all held); sources/session-20260808-night-staleness-overfit CORRECTED IN PLACE (banner + §1 limits + §1 disclosure + §2 retraction + register moves + Related; 1->2); concepts/label-era (the "derived purely from the barrier string" premise CORRECTED - persisted-era-wins is now the binding rule; plus the three-instance horizon-qualification table; 5->6); entities/historystore (the FOURTH writer class - MIGRATORS; the defenses-that-all-held table; the repair; 13->14); concepts/era-exclusion (the failure mode of arming on a count of the very column it protects; nothing-is-ever-deleted paid out for a reason it was not written for; 6->7); concepts/evidence-floors (the RELEASE direction, and the rule that four floors clearing in one step is an alarm not evidence; 4->5); concepts/ghost-badge (2nd instance and a worse category - a badge from a population that never legitimately existed; 1->2); concepts/deploy-deadlock (the mirror polarity - a champion wedged IN rather than challengers locked out; 2->3); concepts/two-paths-one-quantity (the WRITE-SIDE instance = a third severity rung above create/destroy; 5->6); concepts/adoption-is-not-enforcement (the extreme case of proximity - the rule twelve lines below the violation, with 19 correct worked examples around it; 5->6); concepts/false-green (the MIRROR specimen: a RED explained away by a claim never run; design rules 7+8; 7->8); concepts/tautological-instrument (the veto specimen repaired AND the claim corrected - success-path-only tautology, WS-only gain, and the capped-quantity variant of the class; 3->4); concepts/dof-budget (the ledger restated AS A MEASUREMENT; the gaps got worse after cleaning; 5->6); entities/overfit-check (the 640 predicate stated correctly, the wrong-noun drift, the first honest live grading; 9->10); entities/pretrade-gate (PT-020's resurrection + the VETO BAND + the producer/consumer ceiling rule; 6->7); entities/config-guard (new check class: CROSS-SECTION FRESHNESS RELATIONS; and the day its own prose asserted a falsified premise; 8->9); entities/auto-update (the gate is BLOCKED by an honest red, and why a blocked gate is a poor alarm; 7->8); entities/liquiditybot (08-08/09 status block; 23->24); synthesis/owed-measurements (item 46 CORRECTED and written for the FIRST time - the 08-08 filing referenced it but never created the entry; NEW 47 wedged champion; NEW 48 incident residue incl. the citation embargo and the owed monotonic-era-count detector; 42(a) REOPENED as three sub-limits plus the veto band; 44 addendum; 41->42); synthesis/open-contradictions-register (the citation embargo on the corruption window, the "no 60" killing citation, and the UNRESOLVED incommensurable-champion-comparison entry; 27->28); synthesis/documentation-drift-register (the 2026-08-09 class: stale strings that ship INSIDE a running instrument and a passing test, believed because they run; 4 rows; 16->17); synthesis/learning-pipeline-arc (new chapter + lesson 8: a pipeline built to decide automatically from corpus statistics makes a confident wrong DECISION from a corrupted corpus faster than a human notices - nine minutes here; 14->15). Index regenerated 166->169 pages.

## [2026-08-09] ingest | Gate Policy + the Self-Healing Champion (2026-08-09, 8e9d7e6f) — both open adjudications CLOSED

DECISION 1 (item 47) CLOSED, RESOLVED WITHOUT INTERVENTION - the headline: the deliberately-NOT-overridden deploy gate was unwedged by the codebase's OWN already-adjudicated ML-083 doctrine. Audit-confirmed (outputs/audit.jsonl): ML-016 02:56:04.391 (admitted ['logistic'], live 6, total 701) -> ML-083 02:56:04.480 (trained_rows 9708 > corpus_rows 701, challenger_brier 0.24728, n_oof 464) -> ML-040 02:56:04.483 (DEPLOY, ignore_champion=true). main.py:6330 era-orphan branch: the champion watermark (corrupted pooled population) EXCEEDED the repaired matrix, so like-for-like is empty BY CONSTRUCTION and the badge is unfalsifiable; per ML-076/ML-083 the badge was set aside and logistic faced the true COLD-START bar (0.24728 < 0.25). ARITHMETIC PROVING THE BRANCH (ml/monitor.py:667-668, evaluated on the recorded inputs, not inferred): normal branch 0.24728 < 0.1537-0.005 FALSE and champion_brier>=0.25 FALSE -> would have REJECTED. Verified live: meta_model.json kind=logistic rows=701 oof_brier=0.24728; status.json model_kind=logistic, era armed/active True, load 701, live_clean 6. THE BUG-PROMOTED GBT IS NO LONGER TRADING. The corpus repair was the necessary AND sufficient intervention; forcing the gate would have masked that capability - filed as a POSITIVE instance on concepts/false-green (new design rule 9: a gate's refusal to compare is the gate working). DECISION 2 (item 46) CLOSED - option (a) shipped 8e9d7e6f: OF-1/OF-7 dead-feature check informational ONLY while ml.exploration.enabled (OF-5/DSR precedent), FAIL-CLOSED, HARD on synthetic always, SELF-TERMINATING; pure predicate gate_is_informational(explore_on, on_synthetic) at overfit_check.py:101 so the two gates cannot drift; 8 tests. NO THRESHOLD MOVED (0.12/0.55 pinned by test_thresholds_are_untouched); numbers still print every run (pinned); model TRUST untouched. BONUS: _explore_on was derived TWICE, one bypassing main.load_config - fixed; exposed a bare-substring test assertion that failed on a report proving the fix. Battery ALL GREEN 3473+1 parallel / 19 serial / smoke 219 / assurance 49 / overfit 3-0 - first fully-green since the incident AND first ever grading the LIVE corpus. NEW ITEM 49: CLI/runner ML-083 asymmetry (train_meta.py:122 lacks the era-orphan branch; CLI REJECTED 0.2714 at 00:52, runner DEPLOYED 0.2473 at 02:56; ML-032 tells the operator to run the CLI). PATTERN: three instances of one-predicate-two-derivations in one night (label_era / _explore_on / the champion badge) folded into concepts/two-paths-one-quantity as the report-decide-PERSIST ladder, with migration-idempotence restated as its persist-rung special case; the new policy predicate is the class's first PROSPECTIVE application. Runner live on 3c0debd7 - 8e9d7e6f is battery/QA-only, NO BOUNCE NEEDED (stated explicitly on entities/auto-update). Pages: NEW sources/session-20260809-gate-policy-and-self-heal; owed-measurements (46 CLOSED, 47 CLOSED, 49 NEW); ghost-badge; deploy-deadlock; two-paths-one-quantity; migration-idempotence; false-green; never-widen-a-gate (SCOPING is not WIDENING boundary); overfit-battery; entities/overfit-check; entities/ml-governor; entities/auto-update; entities/reason-code-registry; dof-budget; learning-pipeline-arc (lesson 9); open-contradictions-register; documentation-drift-register; sources/session-20260809-corpus-corruption; index

## [2026-08-09] ingest | THE UNBIASED ECONOMIC READ — gross edge is ~zero, 100% of the loss is costs, and the house vocabulary was absorbing the result

OPERATOR DIRECTIVE (verbatim): "make sure you're taking an unbiased opinion... Not making those unbiased opinions (true data) conform to my bot" / "this blocks the corpus from understanding real truth." Filed as governance RULE 14 + NEW concepts/unfalsifiable-explanation.

(1) THE HEADLINE NOBODY HAD COMPUTED, every term re-derived at filing from the live outputs/state.json (saved_at 1786291418) rather than quoted: starting_capital 5000.00, cash 4604.02, realized_pnl_total -208.31 (net of CLOSING fees only), fees_paid_total 382.59, savings 1.4710, reserve 0.2642. entry_fees_total is NOT a key on this snapshot and was recovered EXACTLY from the cash identity = 185.9377, closing legs = 196.6549. Therefore GROSS trading P&L before ANY fees = -11.66 over ~250 closed positions / 438 entry fills = ~-$0.05/trade, indistinguishable from zero; NET realized all-in = -394.25 = -7.89% of starting capital; fees/|gross| = 32.8x; 100% OF THE LOSS IS COSTS. (net_pnl_all_time by the equity identity reads -383.26 = -394.25 + 10.99 unrealized; both filed, denominators declared.) THIS IS NOT "the corpus is data-starved" - it is stronger and unwelcome: there is NO measured gross edge to be starved OF. CORROBORATED by three instruments sharing no mechanism: OOF AUC 0.43-0.48 across logistic/gbt/mlp (at or BELOW chance), champion Brier 0.24728 vs 0.25 for a coin (beats nothing by 0.003), postmortem MFE median 0.18% / p90 0.55% vs a ~0.65% round-trip cost (the median trade never moved far enough IN ITS FAVOUR, at its single best moment, to cover its own costs). DIRECTIONAL CAVEAT STATED BECAUSE IT CUTS AGAINST THE BOT: the fill simulator is documented-optimistic (full quoted offset, no queue, no depth, pooled maker markout +3.58bps@5s where real passive fills mark out NEGATIVE via adverse selection), so real-execution gross would be WORSE than -11.66 - the defensible statement is GROSS EDGE <= 0.

(2) THE FRAMING CORRECTION, the part the operator flagged. The repo's vocabulary (cold-start / data-starved / exploration buys labels / tuition / the learning curve is CLIMBING / DoF budget / era exclusion) is individually defensible term-by-term and composes into an account with NO FAILURE STATE: a losing week is tuition, a failing gate is a corpus that needs to grow, a coin-flip model is a curve that has not plateaued. THE WIKI'S OWN MAINTAINER DEMONSTRATED THE FAILURE MODE TWICE THIS SESSION, both already corrected in place and cited as evidence not re-litigated: (a) attributing the overfit-stage red to "the cold-start corpus failing honestly, exactly as the 2026-08-08 DoF adjudication predicts" when the actual cause was corpus corruption from a migrator bug - the vocabulary made a DATA-INTEGRITY INCIDENT look like an EXPECTED MILESTONE, and it reached the wiki before it was caught; (b) 36fcfd6e's "the identical red reproduces on the parent commit" - asserted, never run, carrying the entire deploy argument. THE RULE: an explanation that cannot be wrong is not an explanation; before accepting any house-vocabulary account of a bad number, state what observation would FALSIFY it. Two terms tested immediately: "data-starved" predicts gross edge > 0 merely hard to select on -> measured gross -11.66 (~0) -> FALSIFIED AS A COMPLETE ACCOUNT; "exploration is tuition" predicts the labels are teaching something -> OOF AUC < 0.5 after 305 live labels -> NOT YET. Neither term banned; both now carry their falsifier.

(3) NEW OWED 50, HIGH - THE CORPUS CANNOT SEE ITS OWN COSTS. Verified against the live 93-column header: signal_history.csv carries net_pnl_usd (col 69) and NO gross column and NO per-row fee column. Consequences: no row distinguishes "the signal was wrong" from "the signal was right and costs ate it"; gross-edge-by-subpopulation (asset/regime/horizon/signal strength) - the single most decision-relevant open question - is UNASKABLE from this file; ml/postmortem.py cannot decompose either, which is why its terminal fallback (postmortem.py:334 "underperformance" = "closed below expectation without a single dominant cause") absorbs 202 of 264 postmortems = 76% OF TRADES DIE UNDIAGNOSED (the other buckets are sound, the inputs to reach them are missing); and the binary win/loss label CONFLATES THE TWO CASES AT THE POINT WHERE THE MODEL LEARNS, so the learner is structurally incapable of learning the distinction no matter how many rows accrue - corpus growth CANNOT fix it. PROPOSED FIX, own change own battery, explicitly NOT bundled: add gross_pnl_usd + fees_usd as TRAILING columns via the established extend-with-defaults ritual (header + migrate_history pad + downstream pins), backfilled offline from outputs/fills.csv (per-fill fees_delta_usd keyed by position_id); the 3c0debd7 idempotence fix makes the resulting rotation safe - the exact path that corrupted the corpus is now fixed and tested. 0 model DoF (bookkeeping, never features). SEQUENCING DEPENDENCY: the backfill sources from a ledger that is 1.6% short (see 5).

(4) NEW OWED 51 - THE FREE POPULATION HAS NEVER BEEN SEARCHED. 9,570 CANDIDATE rows are counterfactual and cost ZERO fees vs 305 live rows that cost ~382.59. Standing rule established: any plan proposing "trade more to learn more" must FIRST state why the free 31x-larger sample cannot answer the same question. Not a free lunch - candidate rows never face fill hazard, queue position or adverse selection, so a positive read there is necessary and NOT sufficient.

(5) RE-MEASURED, STILL OPEN, NOW CONSEQUENTIAL - contradictions item 18: fills.csv fees_delta_usd sums 376.35 across 1,019 rows vs fees_paid_total 382.59 = gap 6.24 (1.6%). Both sides grew ~0.31 since the 08-07 snapshot (382.28/376.04) so THE GAP IS STABLE NOT DRIFTING. Every offline cost analysis built on fills.csv reads OPTIMISTIC by that much - and owed 50's backfill sources from exactly this file, so filing a 1.6%-short fee column would bake the gap into the learner's view of its own costs. CLOSE OR DECLARE BEFORE THE BACKFILL.

(6) NEW CONTRADICTION 21 - "the corpus is data-starved" vs "there is no measured gross edge". Both readings stand (the learning curve genuinely climbs; the gross mean is genuinely ~0); what is contradictory is the INFERENCE drawn from the first. Filed UNRESOLVED rather than closed because the disambiguating measurement - is there gross edge in ANY subpopulation - is blocked on owed 50. Self-flagged: authored by the agent that authored the framing it contradicts.

(7) ADJUDICATION INPUT, NOT A DECISION TAKEN: the ONE live lead is GEOMETRY, not a model - shadow win rate rises MONOTONICALLY 22.3% -> 30.4% -> 35.4% at 108 -> 216 -> 432 bars, i.e. exits are early relative to the cost being paid (the same finding as the MFE median seen on the time axis instead of the price axis). Three cautions filed against over-reading it: a rising win rate is not a rising expectancy (p is not the binding term, and 35.4% is far below the ~99% the derived bar demands); the 48-combo geometry search already found NO surviving bracket with h=432 as the least-bad cell of a grid with no positive cell; shadow and paper. And config_guard has been saying the verdict out loud at every startup, computed from TIERS/STOP/FEES ALONE with no model or corpus - core/config_guard.py:3104-3107, derived entry bar 0.990 > 0.90, "the payoff geometry (tiers/stop/fees) is so cost-heavy that no plausible model clears it; fix the geometry, the bar is only reporting it". A REQUIRED WIN PROBABILITY OF ~99% IS NOT A MODELLING PROBLEM. That makes config_guard the CHEAPEST AVAILABLE FALSIFIER for any account locating the problem in the model or the data. (It is a warn, not a FATAL - recorded, because the project's sharpest economic finding rides a warning-level line.)

(8) THE REPORTING HALF - FILED AS AUTHORED, BATTERY IN FLIGHT, NOT COMMITTED. Verified at filing: git status shows core/state.py, core/persistence.py, runner.py, scripts/gc_pusher.py MODIFIED and tests/test_pnl_all_time.py UNTRACKED; HEAD is 8e9d7e6f; the live state.json does NOT carry the entry_fees_total key. Per governance rule 12 ("confirmed" = measured, battery-green, COMMITTED) this is work in flight, not a shipped fact - and the (1) decomposition does not depend on it. Filed this way deliberately: stating it as shipped would be the exact conformity error this session exists to correct. OPERATOR SYMPTOM "net pnl all time doesn't match up with equity" VERIFIED EXACTLY - equity = cash 4604.02 + savings 1.47 + reserve 0.26 + unrealized 10.99 = 4616.74, and cash = 5000 - 208.31 - 185.94 - 1.73 (pools) = 4604.02. NO MONEY WAS MISSING; THE STATEMENT WAS WRONG. CAUSE: core/state.py record_entry_fee debits opening-leg fees (entry AND hedge - main.py:2019-2020 fires for every non-exit leg) straight to cash while record_realized_pnl nets only the CLOSING leg, so 185.94 of 382.59 lifetime fees (49%) appeared in NO P&L figure at all - the same invisible-fee-channel class the 08-07 reconciliation found, now measured on the whole book. CHANGE: PortfolioState.entry_fees_total accumulator + net_pnl_all_time() DEFINED AS THE EQUITY IDENTITY not a sum of counters (so a future counter omission cannot hide - the bug existed because a P&L number was a sum of the counters someone remembered) + realized_net_all_in(); persisted with an EXACT one-time backfill from the cash identity for pre-upgrade snapshots (verified live: recovers 185.94); four new status keys + gc_pusher metrics; 8 red-first tests in tests/test_pnl_all_time.py incl. the backfill through the REAL StateStore and a pool-skim invariance check. Also corrected: total_equity's docstring omitted the reserve term it has always added. Dashboard regeneration deliberately HELD pending the in-flight panel audit so one regeneration covers all findings.

BOUNDARY (governance rule 13): every dollar is SIM-SIDE - fees are config constants (themselves falsified: 25/40 matches no Kraken row), fills are RNG-at-limit, no queue, no depth. The DECOMPOSITION is an exact identity over the bot's own ledger and is therefore true of the simulated book; the DOLLAR MAGNITUDES are not venue truth. The simulator's optimism is one-directional, so the inequality (real gross WORSE) is the transferable part. The 93-column header, the 1,019-row fills sum, the config_guard source lines, the postmortem fallback and the git status are all repo-side/box-side facts.

TOUCHED: NEW sources/session-20260809-unbiased-economics; NEW concepts/unfalsifiable-explanation (the rule, with the two self-demonstrations recorded as its evidence and its relation to false-green / honest-null-result / iron-law-of-debugging / tautological-instrument); synthesis/the-money-path-thesis (the decomposition the thesis had asserted qualitatively for a week and never computed; payoff-asymmetry RELOCATED not refuted; cost work now provably insufficient; 14->15); synthesis/governance-doctrine (RULE 14, the first rule aimed at the corpus's own reasoning rather than its code; and the failure-mode section sharpened - a fluent vocabulary can make an unasked question feel answered; 18->19); synthesis/owed-measurements (NEW 50 HIGH, NEW 51; 43->44); synthesis/open-contradictions-register (NEW 21; item 18 re-measured and tied to owed 50's backfill; 29->30); synthesis/learning-pipeline-arc (LESSON 10 - a working pipeline is not evidence of a working strategy, and the arc was quietly conflating them; the economics were computable by one arithmetic identity the whole time; "what is still open" rewritten - the economics are now the open question, not the plumbing); concepts/dof-budget (the falsifier "data-starved" now carries; ledger readings and its two exits UNCHANGED, what is withdrawn is the licence to offer corpus growth as the reason the book loses money; 7->8); concepts/priced-bleed (the falsifier it always lacked - a priced bleed must also be a MEASURED bleed; tuition is no longer a terminal justification; the free-population comparison as the default first move; 1->2); concepts/payoff-asymmetry (RELOCATED - 0.561-vs-0.750 describes the SHAPE of the gross distribution, the new measurement describes its MEAN at ~0, the mean is upstream; both 08-02 nulls now explained rather than merely observed; this page's own claim now carries its falsifier; 1->2); concepts/cost-truth (book-level cost truth 32.8x - the gate has always compared cost against CONFIGURATION and never against the edge the cost is paid to capture; 6->7); concepts/false-green (the narrative twin section - same question applied to narratives instead of gates); entities/config-guard (the verdict it has been saying out loud, and why it is the cheapest available falsifier; 9->10); entities/historystore (THE CORPUS CANNOT SEE ITS OWN COSTS - third instance of complete/durable/well-formed-and-missing-the-decisive-column; 14->15); entities/liquiditybot (the economic bottom line + the three misreadings it does not license; 24->25); comparisons/horizon-96-vs-24-bars (now the project's ONE live lead, and it is GEOMETRY not a model; the monotone ladder with its three cautions; 5->6); index regenerated.

## [2026-08-09] ingest | TWO ADVERSARIAL AUDITS (47 agents) + TWO SHIPPED FIXES — the sizer was reading an empty book, the go/no-go tool prints the OPPOSITE of its own method, and every measured distortion flatters (11 for 11)

Every headline claim re-verified against the live tree before filing; two numbers CORRECTED IN PLACE by the filing agent and two by the audits themselves. SHIPPED + DEPLOYED (runner relaunched 11:46:10, RUNNING cycle 5; battery ALL GREEN both commits — pytest 3490/19 skipped, smoke 219, assurance 49, overfit 3/0, ruff, pyright 0, bandit, compileall, quant G1-G5). (1) 1fee174e THE SIZER WAS READING AN EMPTY BOOK — risk/position_sizer.py read getattr(state,'positions',{}).values() at THREE sites; PortfolioState has NO 'positions' attribute (book is _positions, exposed as open_positions()), so the getattr DEFAULT was taken UNCONDITIONALLY for the life of the module (verified directly: a PortfolioState holding a real position returns {}). Three risk controls inert, ALL failing PERMISSIVE: portfolio-heat veto (max_portfolio_heat_frac 0.35, RP_HEAT_FULL) unreachable; signed-inventory reservation skew SZ-061 never applied; inventory-aggression pinned at light_boost 1.10 — a permanent 10% size-UP — where it should taper toward heavy_cut 0.65. Measured on the live book with REAL position ages: gross heat 0.1176 (read 0.0000), signed +0.1052 (read 0.0000), multiplier 0.9488 vs pinned 1.1000 => tickets 13.7% LARGER than designed, precisely when risk was already on. CORRECTION OF THE FILING AGENT'S OWN FIRST NUMBER: initially printed -40.9% because the reconstruction stamped every position as opened NOW, maxing the clustering term u_short; with real ages it is -13.7%. Post-deploy live: status heat_frac 0.1177, structurally 0.0 forever before. WHY IT SURVIVED ~3,400 TESTS — the load-bearing lesson: THE TEST DOUBLES INVENTED THE ATTRIBUTE PRODUCTION LACKS. tests/test_protocols.py::test_open_heat_reads_position_size_not_units is the sharpest instance — its docstring says it exists to catch 'an earlier draft [that] read a nonexistent units attribute, which zeroed heat for every real Position and made the RP-050/051 heat gates unreachable in production' — and it MISSED the identical bug one level up because its own class _State: positions = {...} supplied the missing attribute itself; it guarded a nonexistent field on Position while depending on a nonexistent attribute on state. Three doubles fixed to mirror open_positions(). NEW RULE, filed as concepts/test-double-fidelity and adopted as governance RULE 15: A TEST DOUBLE MAY ONLY IMPLEMENT API THE PRODUCTION OBJECT ACTUALLY HAS. Fix centralises one _open_book() accessor + logs once when a state cannot report its book (a dead reader and a genuinely flat book previously produced the identical benign 0.0 — zero-is-not-a-reading, on the SIZING path). 9 tests incl. an AST pin that PARSES rather than greps, because a substring check matched the module's own prose describing the bug and failed on first run (third instance of the AST-over-grep discriminator). (2) a6334162 HONEST ALL-TIME P&L (operator: 'net pnl all time doesn't match up with equity') — no money missing; the STATEMENT was wrong. record_realized_pnl nets the CLOSING leg only; record_entry_fee debits the OPENING leg (entry AND hedge) straight to cash and touches no P&L counter, so 185.94 of 382.59 lifetime fees (49%) appeared in NO readable number. Added entry_fees_total + net_pnl_all_time (defined as the EQUITY IDENTITY, not a sum of counters, so a forgotten counter cannot hide again) + realized_net_all_in + 4 status keys + gc_pusher gauges + an EXACT one-time backfill. Verified live post-bounce: entry_fees_total 185.94, realized_net_all_in -394.25, net_pnl_all_time -382.40 (= equity 4617.60 - 5000). 8 tests. AUDIT A (Grafana panel/metric chain, 22 agents): 11 defects across 15 panels, 8 decision-grade. D1 hero tile 'Net P&L (all time)' plotted realized_total -208.31 vs a true -382.34 while its description claimed 'the true bottom line, never resets, hedges included' — all three clauses false of the series it plots, the strongest false claim on any board; the number is FIXED by a6334162, the board repoint is now UNBLOCKED post-bounce (gc_pusher skips absent keys, so a panel may only be repointed at a series the RUNNING process emits). D2 STILL OPEN, decision-grade: BOTH drawdown gauges (command id 23, problem/solution id 23) plot drawdown_pct = (start - cash - savings)/start, a start-to-now cash-only figure, while the 15% hard-stop flatten AND the throttle both read drawdown_mtm_pct (peak-to-now MTM); reproduced on live code, a book -20% on marks fires hard_stop_triggered ('20.00% >= 15%') while the gauge reads 0.0 FULL GREEN, and the inverse is already pinned at tests/test_audit_config_risk.py:281-288 where a WINNING account pegs the same gauge at 15.0 red; runner.py:984 computes drawdown_mtm_pct and DISCARDS it as a local, and no board references the MTM series at all. D3 = the sizer bug: the 'Heat vs cap' panel reading 0.0% forever was the SYMPTOM that led to a live risk bug — a gauge that has never moved is a finding, not a quiet subsystem. AUDIT B (self-flattery hunt, 25 agents) — the bigger one. A1 VERIFIED INDEPENDENTLY: scripts/breakeven_test.py:126 counts only purpose=='entry' as the opening leg, so all 159 COMPLETE hedge round trips are discarded under '165 skipped: partial or malformed' (none are malformed; they close to within 0.0% of opening size). Reimplementing the tool's own accumulation both ways on outputs/fills.csv: shipped 235 closed / 165 skipped, gross -3.03, fees 59.23, net -62.27, MEDIAN GROSS +0.0505%; corrected (entry|hedge) 394 closed / 6 skipped, gross -13.01, fees 374.96, net -387.96, MEDIAN GROSS -0.0303%. THE SIGN FLIPS, which flips the branch the tool PRINTS — from ':214-230 This is NOT no edge ... that is exit geometry ... fixable without touching the signal' to ':231-241 GROSS EXPECTANCY IS NEGATIVE ... no execution change, holding period, gate, filter or model creates expectancy that is not in the entries.' THE GO/NO-GO TOOL HAS BEEN PRINTING THE OPPOSITE OF ITS OWN METHOD'S ANSWER. Fix ~10 lines + break the skip counter out BY REASON. FILING AGENT'S OWN NEAR-MISS, filed as process evidence: the first verification added fees back into cash, which is already the pure notional flow, producing a 'gross' that was really net and showing NO flip — on that basis the operator would have been told the audit was wrong; caught by re-deriving the terms. Same error class as the 'reproduces on parent commit' claim earlier this session. A4 LIVE RISK, STILL OPEN: main.py:1671 'if not pos.is_hedge:' gates BOTH perf.record_close AND breaker.record_close, so the entire -325.70 hedge book is invisible to expectancy/win_rate/profit_factor/Sharpe AND to the consecutive-loss circuit breaker — which is why 159 consecutive losing hedge round trips over 10.4h never tripped it: they were never recorded as losses. status.json implies 200 trades x -0.2838 = -56.76 against a true closed book of -387.96. ADJUDICATION NEEDED AND DELIBERATELY NOT TAKEN: the perf ledger clearly SHOULD see hedges; whether the BREAKER should is a genuine design question (a hedge is risk-reducing insurance that often loses BY DESIGN, so counting hedge losses could trip the breaker during correct operation, and the 159-loss run was a churn bug FW-070 since fixed) — changing what a circuit breaker counts changes WHEN IT FIRES, and that belongs to the operator; note the status quo is itself the PERMISSIVE choice. A3: performance.overall pools 91% EV-gate-bypassed probes with conviction trades, count-weighted; inside the exact 200-close window (197/200 joined) probe n=182 expectancy -0.1636, conviction n=17 expectancy -1.5840, reported pooled -0.2838 = a 5.6x understatement of the conviction figure; pos.is_probe is IN SCOPE 22 lines earlier at main.py:1650 and simply not passed; sharpe -1.067 / sortino -0.751 / max_loss_streak 57 are all computed on the mixed sample and describe NEITHER population. THE CODEBASE ALREADY HOLDS THE OPPOSITE DOCTRINE — overfit_check.py:1031-1034 refuses to grade DSR on the mixed sample for exactly this reason; the correction lives in the ML-validation lane and never travelled to the P&L-reporting lane. CORRECTION the audit made to itself: notional weighting does NOT support the argument (return-on-notional -0.692% probe vs -0.479% conviction, the opposite ordering); the SPLIT is the repair, not a re-weighting. A2: scripts/cost_attribution.py:126 is a bare continue with NO skip counter — same hedge blindness; the reader sees n=1019 in one paragraph and a cost from n=235 in the next with no signal. CORRECTED DOWNWARD from the initial hunt: the printed 0.668%/trade is CORRECT for the 235 directional trades, honest blended is 0.7766% (1.16x, NOT 6.4x); severity MEDIUM — the defect is that a cost-attribution tool is structurally blind to its own largest cost event. FILL SIM: 22.30% per-order fill against an 11.66% calibration target at the touch — resting maker orders get TWO independent chances to fill per modelled event, so roughly half the near-touch paper entry population describes fills the recorded market never granted; bounded 1.19x at 20bps to 1.91x at the touch, weighted high because 57% of post-only fills rest within 5bps; propagation into the 305 live corpus rows and the 432-bar cohort verdict is directionally supported but UNVERIFIED and may NOT be cited against the h432 hold. CORRECTED DOWNWARD by the audit's own verify pass: 'hedging is 84% of the loss' is true of the LIFETIME ledger but is one already-fixed incident on one day, not a standing per-entry cost; go-forward unpriced hedge cost is ~7% of fees — do not size a fix off the 84%. THE SYNTHESIS: gross trading P&L before any fees is ~ZERO by TWO INDEPENDENT METHODS — -11.66 by the state identity and -13.01 by the full-book fills reconstruction (394 round trips) — agreeing to within 1.35 on a book that paid 382.59 in fees, and the second arrived as a BY-PRODUCT of fixing A1 rather than as an attempt to reproduce the first. Corroborated by OOF AUC 0.43-0.48, champion Brier 0.24728 vs 0.25 coin, postmortem MFE median 0.18% against a ~0.65% round trip. AND THE META-FINDING, which is why both audits were worth running: EVERY distortion found in both audits runs the SAME DIRECTION, flattering; ZERO instances of the bot understating itself (11 for 11). A measurement error is a coin flip; eleven landing on the same face is a process fact — filed as concepts/self-flattery-gradient with a testable prediction (every future correction to a reported performance number moves it DOWN until the gradient is addressed at its source). Fill-sim inflation means REAL gross would be WORSE: the honest statement is gross edge <= 0. OWED — severity-ordered docket 52-57 (+58 = the pre-existing 6.24 fills-ledger gap, listed only for queue completeness): 52 A4 perf/breaker hedge blindness (perf fix clear, breaker semantics needs operator adjudication, deliberately unsplit); 53 A1 breakeven_test opening-leg fix (~10 lines, changes the go/no-go answer); 54 A3 probe/conviction split (pass is_probe at main.py:1672, emit overall/conviction/probe blocks, streaks within-population); 55 D2 drawdown MTM export + board repoint + retitle; 56 A2 cost_attribution skip counter by reason; 57 fill-sim double-chance. Board regeneration is ONE pass covering D1 repoint + D2 + all panel findings — the JSON is NEVER hand-edited. Still owed from earlier, restated for queue completeness: item 49 (train_meta ML-083 asymmetry), 42e, 37g/37b, 45a-45f, 41d/41e, status.json empty-key PowerShell break. TOUCHED: NEW sources/session-20260809-adversarial-audits; NEW concepts/{test-double-fidelity, self-flattery-gradient, uncounted-exclusion, pooled-populations}; synthesis/{owed-measurements (docket 52-58), open-contradictions-register (NEW entries 22/23/24), documentation-drift-register (2 rows: the D1 panel description, and the test docstring that named the exact class its own fixture was hiding), governance-doctrine (RULE 15), the-money-path-thesis (second independent gross method + the go/no-go retraction), learning-pipeline-arc (LESSON 11)}; concepts/{false-green (sixth way + design rule 10), zero-is-not-a-reading (sizing-path instance, first fix to install the DISCRIMINATOR rather than a better default), two-paths-one-quantity (fifth instance 'drawdown' on the DECIDE rung, plus the class's INVERSION — one predicate serving two decisions must be SPLIT), adversarial-verification (four corrections incl. the near-miss, and the rule: verify your own refutation hardest), cost-truth (both cost instruments blind to the largest cost event), payoff-asymmetry (median gross -0.0303%), never-widen-a-gate (the mirror boundary — no silent TIGHTENING either), unfalsifiable-explanation (instrument-side twin), iron-law-of-debugging (AST-over-grep three-for-three)}; comparisons/stated-invariants-vs-audited-reality (3 new rows, the widest gap in the table and the first covered by PASSING tests); entities/{observability-sidecars (panel audit + the committed-vs-running repoint rule), liquiditybot (both fixes + the bottom line)}. Index regenerated (177 pages); lint clean — 0 orphans, 0 broken wikilinks, 0 missing frontmatter, 0 duplicate titles.

## [2026-08-09] ingest | TURING TEST + the hedge verdict (0 of 159) + the breaker counterfactual — SHIPPED 415af0f9 and f11b7e32

Machine identified INSTANTLY on mechanics (modal ticket exactly $18.00 x51, after-win/after-loss size ratio 1.000, 0.0% round-number landing, 8-decimal sizes incl 31 dust legs to 1.17e-09 ETH, 100% limit 1019/1019, 59 trips held exactly 5.000s, chi2 137.8 with ZERO empty hours) yet ECONOMICALLY INDISTINGUISHABLE from an unprofitable retail human (58.3% win rate on 0.670 payoff, disposition effect 2.20x = losers 2.00h vs winners 0.91h) — resolved as concepts/behavioral-isomorphism: the bias is GEOMETRIC, not psychological. Algo verdict: gross edge -0.0019%, t=-0.332, fees 368x |edge| (percent space; NOT in conflict with the 32.8x dollar-space figure), 0.91h median winner vs 0.71% round-trip cost, 60.6% taker fills. HEDGE POPULATION: 0 of 159 round trips profitable NET of fees (gross win 15.1%, net 0.0%), net -325.70 on 39,460 notional = 4.5x the entry book's 8,821; entry-opened 235 trips won 57.4% on a +0.0505% median and still totalled -3.03 gross. CHURN RE-MEASURED (same ledger event as OCR entry 19 — NO third incident page opened): 2026-08-07 01:09-01:34Z, 147 ADA hedge round trips, all 2-leg, 59 at exactly 5.000s, 36,210 notional, gross -12.77, fees 289.73 = 77.3% of ALL lifetime fees (denominator 374.96; at 382.59 it reads 75.7%), no recurrence in 56.5h. OWED 52 COUNTERFACTUAL MEASURED, DECISION STILL OPERATOR-OWNED: replaying the shipped CircuitBreaker over the real close sequence, counting hedges costs +1 trip in 19.5 days (42->43) and would have stopped the churn after 4 laps instead of 147; breaker has fired 48 times across 12 assets. SHIPPED 415af0f9 (hedge-is-an-opening-leg across FIVE scripts, not one): breakeven_test 235->394 trips, 165->6 skipped, median gross +0.0505%->-0.0305%, PRESCRIPTION INVERTED — owed 53 and 56 CLOSED, OCR entry 22 RESOLVED, by-reason skip counter survives as 53-residual. SHIPPED f11b7e32: probe/conviction split SHIPPED AND INERT (unknown 200 / probe 0 / conviction 0) so owed 54 stays OPEN; drawdown_mtm_pct 7.6706 vs realized-only 7.89 exported, throttle 0.3416, hero tile repointed to net_pnl_all_time — owed 55 PARTIAL, board regeneration still owed. NEW OWED 59 (status-schema/fixture drift: a6334162 shipped 4 keys without updating _SYNTH_STATUS; the gate fired CORRECTLY — a positive false-green counterweight) and NEW OWED 60 (agent-raised: 31 dust legs to 1.17e-09 ETH filled in sim that no venue would accept). THREE SELF-CAUGHT AGENT ERRORS FILED: tail's exit code cited as the battery's (false-green 7th way), then excused with a PRE-CHANGE green run (new concept: retroactive-excuse); a breaker replay that never called is_tripped() and reported a false 'no difference'; and a '7.04x revenge sizing' artifact from pooling entry ($18.00) and hedge ($265.44) tickets that differ 14.7x by construction — filed as the second specimen on pooled-populations, notable because pooling FABRICATED a finding present in neither sub-population. Created sources/session-20260809-turing-test-hedge-verdict, comparisons/bot-vs-discretionary-vs-algo-trader, concepts/behavioral-isomorphism, concepts/retroactive-excuse. Updated owed-measurements (52/53/54/55/56 + 59/60), open-contradictions-register (6, 19, 22, citation hazards), the-money-path-thesis, pooled-populations, false-green, test-double-fidelity, cost-to-volatility-ratio, liquiditybot, both hedge churn sources.

## [2026-08-10] ingest | Owed 57 CLOSED as EXECUTION-ERA BOUNDARY #4 (aeeaae36) - the fill sim counted ONE market crossing TWICE; the 08-08 "conservative floor" disposition RETRACTED; and an over-generous simulator was MASKING four tests that passed on luck

OWED 57 CLOSED / EXECUTION-ERA BOUNDARY #4 (aeeaae36, stamp 2026-08-10 06:03:35 -0500 = 2026-08-10T11:03:35Z, pushed, origin/main==aeeaae36, runner bounced 06:06:01 local; 8 files +309/-12). ZONE-STAMP CORRECTION: config.json:376 _passive_hazard_with_book_doc AND core/config_guard.py both date the boundary 2026-08-09 while git author+committer say 2026-08-10 - filed as a drift row; measured blast radius of the wrong date is 4 ledger rows (0 post_only, 2 entries) misclassified by a naive 2026-08-09T00:00Z cut. MECHANISM, confirmed THREE independent ways (own derivation, the calibration source, and the vault's OWN 2026-08-07 log entry which had already named it): calibrate_fills.py measures f = how often the MARKET crossed a hypothetical resting limit within its life from recorded book frames; core.fill_calibration.invert_base_prob solves passive_base_prob so the HAZARD ALONE reproduces f over n_bar polls (p_poll=1-(1-f)^(1/n_bar); sf_base=p_poll*exp(d_bar)); _poll_dry then ALSO called _sim_maker_cross which fills FULL remaining deterministically whenever the book crosses - the very event f counts; and DECISIVELY the hazard only ever ran INSIDE `if book:` so it modelled nothing a snapshot could show - purely additive, never a floor. 1-(1-f)^2 = 2f-f^2 = 21.96% vs the 11.66% target against a ledger-measured 22.30% - agreement to 0.34pp, two computations with no shared mechanism. 1.88x at the touch (NOT the 1.91x first bounded), approaching 2x as f FALLS i.e. worst exactly where the book rests. BLAST RADIUS measured BEFORE any change and re-reproduced at filing: 402 post_only fills, 57.2% within 5bps (230/402 - independently reproduces the 57% already on record, third computation), 154/401 positions = 38.4% opened by a near-touch post_only leg, 20.4% within 1bps. FIX: observed book is ground truth (order_manager.py:275, :1308); passive_hazard_with_book=true restores the pre-boundary simulator EXACTLY (a time machine, not a knob) so pre-#4 cohorts stay reproducible; config.json:375 ships false; config_guard WARNs carrying the MAGNITUDE - deliberately NOT FATAL because a FATAL would make the old cohort unreproducible hence UNAUDITABLE (new doctrine on entities/config-guard: FATAL for INCOHERENT, WARN for COHERENT-BUT-SUPERSEDED). Expected consequence stated in config: paper fill rate roughly HALVES near the touch - the third fill correction whose visible effect is fewer trades, each written down in advance. tests/test_fill_double_count.py 7 tests, count VERIFIED by reading the file (contrast the 08-08 filing: claimed 8, collected 7). Battery pytest 3518+19, smoke 219, assurance 49, overfit 3/0, quant G1-G5. THE CORPUS IS ENTIRELY PRE-BOUNDARY: last fills.csv row 2026-08-10T06:50:23.746Z, ZERO fills at/after the commit - a clean cut, no mixed population, and no post-#4 sample to compare against. RETRACTION, first-class (domain rule 3): the 2026-08-08 disposition of owed 40's sub-item (b) - '_sim_maker_cross = genuine trade-through, hazard = conservative floor, disposed by design' - is WRONG and RETRACTED. The hazard was purely additive, not a floor. Item 40's closure stands for (a) the TTL normalization ALONE. sources/session-20260807-fleet-findings VINDICATED (its 'the calibrated trade-through frequency is spent twice' was correct and was talked away the next morning, costing two days with a 1.88x bias live). Filed as open-contradictions entry 25 RESOLVED-and-kept, and as a NEW SURFACE on concepts/self-flattery-gradient: the gradient reached the ADJUDICATION, not just the measurement - closing an item requires no evidence, only a sentence. Rule extracted: a disposition that closes a docket item deserves the same adversarial pass as the finding that opened it, and MORE when written beside a fix the author is pleased with. NEW OWED 61: MP-7 QUEUE GATING IS NOW INERT - queue_ok is computed at :1302-1304 and consumed ONLY at :1308, so queue_aware:true now protects nothing and _sim_maker_cross fills full remaining with no depth constraint. Pinned by test_queue_gate_is_inert_on_the_default_path so it stays VISIBLE. Deliberately NOT fixed in the same commit: physically right but a second uncalibrated change to a learning system's fill model, and compounding both would make any later corpus change impossible to attribute. Dormant-vs-inert specimen with a twist: inertness CREATED BY A FIX, not by a bug. NEW OWED 57b: recalibrate passive_base_prob under the single-path simulator (the 're-run calibrate_fills.py' half of 57's closure condition, which did NOT happen) - folds into 40b/XV-023; ONE campaign closes 13c/23b/40b/57b, and it would mint a FIFTH boundary so it waits for the cohort. NO new reason code minted - which surfaced that XV-023 ITSELF is unregistered (core/codes.py stops at XV-022; XV-023 lives only in a docstring and is cited by config.json, fill_calibration.py and this vault). Second drift row; filed on entities/reason-code-registry. NEW CONCEPT concepts/generosity-masks-fragility (arguably the more valuable half): FOUR FULL-ENGINE TESTS WERE PASSING ON LUCK. The old hazard granted a fill on essentially any book, hiding that tests/test_bracket_exits.py full-engine cases depended on a random walk dipping through a resting bid; one 4-file combination FAILED once then PASSED three times with only COMMENTS changed between runs. Fixed with a driftless 90-cycle walk, verified stable 3x. A negative drift also fills them but trips FW-050's 100bps collar - passing for a reason unrelated to the subject, rejected as a tautological green. THE CLASS: an over-generous simulator MASKS test fragility, so making a model honest SURFACES flakiness that was always there - the flake wave is debt DISCLOSED, not created. Mirror of false-green: there a gate could not FIRE, here a test could not FAIL. PIN DECAY, second occurrence on concepts/default-path-fallback-writes: the two smoke fixtures pinned to the deterministic fill model on 2026-07-21 had their pin SILENTLY stop working because passive_base_prob became irrelevant once a book is present; extended to the new flag (smoke_test.py:571, :822) following that documented precedent. Generalized rule, third statement: absence of a key is not absence of a write -> absence of a pinned value is not absence of a dependency -> PRESENCE of a pinned value is not presence of a guarantee. Pin the PROPERTY, not the constant (only 1 of 4 fixtures took the durable option - test_exec_quality_stats moved to a crossed book). The persistence fixture failed with IndexError on open_positions()[0] rather than an assertion - it crashed rather than reporting 'no position', unable to distinguish a broken subject from a setup that never happened. FOUR SELF-CAUGHT AGENT ERRORS filed to concepts/adversarial-verification: (1) first measurement tested for two draws WITHIN one poll where they are mutually exclusive and found nothing - the register was right and the test was aimed at the wrong level, nearly closing 57 as unreproducible; (2) that same script printed sf_base 0.45 having silently fallen through to defaults when live is 0.048 - a measurement harness riding a default, the same class one plane up; (3) the 2.22x seen at dist_bps=0 was the harness degenerating, true figure 1.88x - an error in the UNFLATTERING direction, still an error; (4) patched a test by LINE NUMBER (1134 was the probe test), reverted and redid by test name. Errors 1 and 3 point OPPOSITE ways, which is what an unbiased error process looks like. TOUCHED: NEW sources/session-20260810-fill-double-count; NEW concepts/generosity-masks-fragility; synthesis/owed-measurements (57 CLOSED + 57b + NEW 61 + 40(b) RETRACTED + docket table + summary; 46->47); concepts/paper-real-boundary (fills row rewritten to ONE path, rule 4 -> FOUR boundaries, the whole-corpus-is-pre-boundary property, and the 'honest fills claimed 3x wrong 2x' warning; 5->6); vault CLAUDE.md + AGENTS.md standing question 4 rewritten (four boundaries, blocks re-verified identical); concepts/two-paths-one-quantity (SIXTH instance + the new CALIBRATE rung above persist - the two paths did not disagree, they COMPOSED, so 'do they agree?' returns yes and is useless; 8->9); concepts/default-path-fallback-writes (pin decay; 6->7); concepts/self-flattery-gradient (adjudication surface); entities/config-guard (WARN-not-FATAL doctrine; 10->11); entities/long-book (FOURTH reading - worst-affected population by construction, four readings in eight days; 5->6); entities/reason-code-registry (XV-023 unregistered; 14->15); comparisons/horizon-96-vs-24-bars (THREE boundaries inside the cohort, four fill regimes, trend confounded with fill regime by construction; 6->7); synthesis/the-money-path-thesis (08-10 addendum: thesis unchanged BECAUSE every number was measured with the thumb on the scale; 16->17); synthesis/open-contradictions-register (NEW entry 25 RESOLVED; 31->32); synthesis/documentation-drift-register (2 rows: the boundary date, and XV-023; 19->20); sources/session-20260807-fleet-findings (VINDICATED banner on section 1); sources/session-20260808-morning-batch ((b) disposition struck + retraction); sources/session-20260809-adversarial-audits (section 4.5 closure banner + the 1.91x->1.88x correction). Index regenerated to 183 pages (the previously-stated 177 predates the 08-09 turing-test session, which added four pages without restating the count: 181 -> 183 here). Lint clean: 0 orphans, 0 broken wikilinks, 0 stale, 0 missing frontmatter, 0 duplicate titles.

## [2026-08-10] ingest | The $800 stressor regime + capital epoch (2fee7f64 + d6112bca..a7dab725) - model FREEZE behind the pre-registered era-4 gate, RP-072 goal ladder, the ledger defends itself (exec_era + OM-085), owed 62 SHIPPED / 63-64 registered

Seven pushed commits, batteries ALL GREEN, re-verified against the box (codes.py 193 codes incl OM-085/RP-072, XV-023 STILL absent; config 800/25/100/4000/250). (1) d6112bca CAIO adjudication ('apply them'): model-side investment FROZEN, only unfreeze trigger = the era-4 gate readout - NO_GROSS_EDGE (stop-strategy question to operator) / COST_BOUND (h432 fee levers) / CONTINUE - at n>=50 on entry-opened closed round trips reconstructed from fills.csv, hedges excluded, registered at n=1 before the data had a vote; accrual cross-check +0.9619% exact. (2) 6fe6d98d exec_era provenance column '4-aeeaae36' (old rows deliberately BLANK - never manufacture provenance) + OM-085 restart-replay guard on (order_id,size,price,remaining) - owed 62 registered AND shipped same day. (3) 43015031 SE+resolution note in the gate readout (SE ~0.07% at n=50, resolvable |edge| ~0.14% = 10x anything exhibited - a TRIGGER, not an effect measure); REST matrix 33 tests (negative Content-Length hang REFUTED empirically, then pinned); ERA-4 ACCRUAL MORATORIUM as binding law in repo CLAUDE.md -> governance RULE 17; challenge hardening #1 closed HONEST NEGATIVE (recordings at 5.00s median cadence sit inside the same fast poll - intra-poll bias structurally unmeasurable; ws book capture = owed 63). (4) 38751d5b THE $800 STRESSOR, operator-adjudicated ('full clean sweep... $100 a month... see what we have right and what is completely wrong' + 'scale the profits to the most it can stress every month'): capital 5000->800, goals 25/wk 100/mo, RP-072 ladder x1.5 graded-then-escalated never-de-escalates AST-pinned RP-071-before-RP-072; %-knobs invariant, USD knobs x0.16, venue floors UNSCALED ($15 = 1.9% of equity, the bite IS the stressor); _MONEY_ZERO was missing monthly_realized_pnl (survived EVERY prior reset) and entry_fees_total (would have carried $185.94 - persistence backfill only fires when key ABSENT); perf-window swept (pooled-populations on live boards otherwise); HONESTY LINE filed with it: nothing makes a no-gross-edge book EARN $100/mo - expected outcome is the truth faster and louder. (5) Challenge ordering audit: ratchet consumes ONE derivation of month-met (two sites drift silently); _drive_flatten exits positions ONLY - a restored $5000-sized 6h bid could fill 156%-of-equity past the $4000 cap -> deploy gate hardened to positions==0 AND open_orders==0 (open_orders was 0 - theoretical this time); month-rollover->ratchet crash window = owed 64 (benign: RP-071-without-RP-072 detectable, under-escalates, documented not fixed). (6) a7dab725 CAPITAL EPOCH 2026-08-10T23:05:27Z (epoch 1786403127), verified equity 800.00 exact all-zeros; gate cut = max(B4_TS, CAPITAL_EPOCH_TS); amended at n=3 BEFORE any new-regime data, book flat + entries OFF across the instant; 3 $5000-regime closes excluded (honest fills, wrong regime); accrual 3/50 -> 0/50. (7) Also: probe tile -> BLUE neutral-info (3a5fdab2, alarm fatigue; generator IS the design system, WCAG AA measured); heartbeat test asserted one lucky thread schedule - the halted-runner schedule it read as failure is the SAFER outcome (c60f9772, generosity-masks-fragility specimen #2); orphan .pyc of retired Streamlit console removed; 2fee7f64 resolves the drift register's boundary-stamp row (XV-023 row STANDS). Touched: NEW sources/session-20260810-stressor-epoch, NEW synthesis/comparability-boundaries (the one authoritative cut table), NEW synthesis/evidence-closed-register; synthesis/{owed-measurements (docket 52-64: 62 CLOSED-same-day, 63/64 NEW, 61 fenced by moratorium), governance-doctrine (RULES 16+17), risk-posture-doctrine ($800 regime + ladder rent number), the-money-path-thesis (verdict-instrument chapter), documentation-drift-register (2fee7f64 resolution)}; concepts/{paper-real-boundary (capital axis + table pointer), two-paths-one-quantity (prospective #2), generosity-masks-fragility (scheduler specimen)}; comparisons/horizon-96-vs-24-bars (capital epoch = 4th in-cohort cut); entities/{liquiditybot (current-regime section), reason-code-registry (191->193, XV-023 stands)}; vault CLAUDE.md + AGENTS.md (standing question 0 + boundary (v) + register checks in ingest checklist); index regenerated (186 pages)

## [2026-08-10] lint | CAIO retention survey of the vault itself - does it retain what the project cannot afford to lose?

Seven probes, verdict per probe, gaps FIXED in the same pass. (a) Model freeze + only unfreeze trigger: WAS A GAP (the freeze/gate lived only in tonight's commits) -> now on sources/session-20260810-stressor-epoch SS1, money-path-thesis (verdict-instrument chapter), governance rule 17, liquiditybot entity, and CLAUDE.md/AGENTS.md standing question 0 - findable from the index in one hop, unambiguous. (b) Comparability boundaries: WAS A GAP (four fill boundaries in prose across 4+ pages, no capital epoch, no single table) -> NEW synthesis/comparability-boundaries with exact stamps (QA quarantine, XV-021 8e5455e8 ts~1785717000, 3cfe0710, aeeaae36 2026-08-10T11:03:35Z, label axis 7566ea88 verified against the repo, capital epoch 23:05:27Z) + the exec_era blank=decide-by-ts rule + who-reads-which-cut; pointed from CLAUDE.md/AGENTS.md, paper-real-boundary, horizon comparison. (c) Evidence-closed skip lists: PARTIAL GAP (rejections existed with killing citations but scattered across abstention-filters, governance rule 11, institutional SKIP table, availability-failure) -> NEW synthesis/evidence-closed-register (one index: meta-labeling, synthetic-data SMOTE/GAN/jitter/relabel, exit-geometry rescue, timing-signal claims, corpus-growth-as-complete-account, COT-as-signal, put/call, IV-skew, opt_* transmission, stablecoin issuance, 13F/N-PORT/PF, hourly-lead features, availability kills) + the reopening rule (stated revisit terms only; ETF flows the sole recorded reversal); wired into the ingest checklist so it is read BEFORE proposing. (d) $800/100 adjudication trail: FILED - operator verbatim, rescale rules, honesty line, and the WHY (stressor = truth faster and louder) on the source page SS6; reconstruction needs no re-litigation. (e) Owed register 52-64: NOW COMPLETE, severity-ordered, measurement-vs-decision status explicit per item (52b operator-owned decision, 61 fenced-open, 62 closed-same-day, 63 registered instrument, 64 documented-benign). (f) Governance as RULES: disposition-adversarial-pass promoted from contradiction-25 prose to RULE 16; moratorium+freeze to RULE 17; wiki-as-truth (12) and never-delete (8, machine-enforced) already rules - PASS. (g) Contradiction register: CURRENT - 22 and 25 resolved-and-kept, 23 (drawdown word) and 21/24 still honestly open, no new contradictions minted by tonight's changeset; drift register's stamp row resolved by 2fee7f64 with the XV-023 row explicitly left standing. Residual risks noted: XV-023 still unregistered in codes.py; owed 55 board regeneration still owed; lint 0 broken wikilinks, 186 pages

## [2026-08-10] ingest | The Grand Synthesis standing directive (2026-08-11) + the complete trade-path ledger

Operator standing directive filed VERBATIM (sources/directive-20260811-grand-synthesis): all-issues synthesis, past/present/future analysis, bot-specific algorithms from the bot's own uncensored data, sequenced INTO the moratorium/freeze/era-4 gate (never over them); fires on 3 inputs (academic sweep, engineering-precedents sweep, battery 14) = owed 66. Phase D mechanized as concepts/closed-loop-self-measurement. Trade-path ledger recorded (PATHS_COLS, trade_paths.csv, winners included, 15/266 -> verified 15/269; working tree, battery 14 in flight) closing the winners-censoring instance of uncounted-exclusion. FOUND AT FILING: paths_path fallback let a QA fixture row (2000,p1,ETH = test_telemetry_fixes F1) into production trade_paths.csv - default-path-fallback-writes NINTH instance, owed 65. Geometry epoch RESERVED as cut #7 (comparability-boundaries), pending operator timing adjudication. Touched: directive page (new), closed-loop-self-measurement (new), owed-measurements (65+66), default-path-fallback-writes, uncounted-exclusion, governance-doctrine, comparability-boundaries, the-money-path-thesis, index

## [2026-08-10] ingest | Grand Synthesis delivered - owed 66 SATISFIED, owed 65 CLOSED (2602371b), algorithm package filed

Trigger satisfied: academic sweep filed (sources/sweep-20260811-academic-stops - Kaminski-Lo regime-conditional stops THE load-bearing result; Han-Zhou-Zhu tight stops contradict widen-in-high-vol; Osler JIMF 2005 the peer-reviewed kernel under stop-hunt folklore; Goulding-Harvey-Mazzoleni four-state slow/fast disagreement THE turn-detection answer; widen-in-high-vol CONTESTED lean AGAINST; MAE-boundary/ICT/ATR-multiplier/funding-flip/cross-regime-purge FOLKLORE; triple-barrier regime shift = the gap only ALGO-2 can close locally; 100-seed AFML replication matches project internals). Engineering sweep filed (sources/sweep-20260811-engineering-precedents - nobody documents symmetric-R brackets; time-decay+time-limit+ratchet-invariant convergence with the minimal_roi trap; mark-price triggering the only deployed anti-wick mechanism; state reconciliation = the hard part, ALREADY AHEAD via OM-085; NFI no-hard-SL cost = deep drawdowns; brookmiles artifact confirms generosity-masks-fragility; own-hedge-cadence unclaimed territory, falsifier-only). Package filed (synthesis/grand-synthesis-algorithm-package): Tier 1 SAFE ALGO-1..4 (ALGO-4 shipped 2602371b), Tier 2 geometry-epoch ALGO-5..7 PENDING operator cut-#7 timing adjudication, five NOT-ADOPTED. Owed 65 closed same commit: row QUARANTINED (trade_paths.csv.quarantine_qa_1786), five harnesses to tmp_path, caught TWICE (vault verification + battery 14 RED via conftest tripwire - its FIRST confirmed catch). Battery 15 ALL GREEN BATCH_EXIT=0 verified directly. Filed per rule 16: session first read battery 14 off the TASK wrapper exit instead of BATCH_EXIT - owed-44 lying-gate class, SECOND occurrence that night, self-caught. Touched: owed-measurements (65/66), governance-doctrine, the-money-path-thesis, comparability-boundaries, evidence-closed-register (NOT-ADOPTED section), directive-20260811-grand-synthesis, default-path-fallback-writes (9th instance CLOSED), false-green (7th-way recurrence + tripwire counterweight), closed-loop-self-measurement, evidence-grading-ladder (2nd application), osler, retail-bot-frameworks. Open: geometry-epoch adjudication (operator), owed 52 (parked).

## [2026-08-10] ingest | Cut #7 MINTED - the geometry epoch (e7d5ca1a, 2026-08-11T01:33:50Z): Osler semantic flip, ALGO-6 pins, the CDO-review split

NEW sources/session-20260811-cut7-geometry-epoch (every claim verified on the box: git log/show e7d5ca1a + 76030603 + ee7a94a2, risk/stop_placement.py read in full, tests/test_algo6_time_limit_pins.py, tests/test_fill_ledger_provenance.py diff, config.json risk block diff; head = ee7a94a2). (1) THE ADJUDICATION: the operator's cut-#7 timing decision landed as a CDO-REVIEW SPLIT, not a monolithic yes - evidence-sufficient Tier-2 elements shipped at the free cohort reset (zero closes since the capital epoch), replay-parameterized stop widths + time-decay ladder DEFERRED to a pre-named ALGO-5 amendment at ~30 uncensored paths = the next boundary-minting adjudication (NEW owed 67). Two CDO sharpenings filed on grand-synthesis-algorithm-package: 'one package, one adjudication, one boundary' SUPERSEDED by the split; 'cheapest at low accrual' resolved to FREE at zero accrual - max(B4_TS, CAPITAL_EPOCH_TS) and 'after cut #7' select identical populations by construction. (2) ALGO-7, THE SEMANTIC FLIP: the existing main.py Osler nudge held OPPOSITE semantics (tighten-above - any sweep TO a round level ejected the position, the exact bull-readiness shakeout), was nearly dormant (bracket sl leg raw), and read a PHANTOM config block (risk_management does not exist; the knob was never read, masked by the coinciding 5.0 default - drift register's first PHANTOM KNOB row, resolved same commit). Fixed as risk/stop_placement.py: widen-beyond, both stop sites, only-ever-widens, direction-only (half-step lattice kept); the four Osler tests flipped sign as the record. (3) ALGO-6 shipped as PINS NOT DUPLICATES - tb_time full P&L-blind close + PT-060 (MFE 0.16% vs MAE -1.44%, recovered 0/17) already existed; 4 pins including EXACTLY ONE tb_time submit site. (4) BATTERY 16 went RED on the package's own first pin: a <=4 threshold from a head-truncated grep (main.py legitimately says tb_time six times) - filed with owed-44's wrapper-exit error as the EVIDENCE-TRUNCATION class, both polarities (14 hid a red, 16 manufactured one); final battery ALL GREEN. (5) exec_era bump 4-aeeaae36 -> 7-e7d5ca1a landed ONE COMMIT LATE (76030603) - gap verified fill-free, provenance pin now locks exact constant + format. Touched: comparability-boundaries (already carried the minted row), grand-synthesis-algorithm-package, osler, false-green, documentation-drift-register, owed-measurements (66 updated, 67 registered), the-money-path-thesis, governance-doctrine, CLAUDE.md/AGENTS.md standing question, index.

## [2026-08-10] ingest | The since-6am operator audit (wf_54d5cbd8-caf, 7 agents, 2026-08-11) — backwards-derivative claim REFUTED (NO-INVERSION-FOUND, 0/3), the anti-momentum surprise, MIXED asset-selection verdict, ledger COHERENT under $800

HEADLINE: the operator's backwards-derivative claim VERIFIED FALSE at high confidence — three adversarial refuters (recompute / consumption / data lenses) instructed to FIND the inversion, 0/3 succeeded. What the operator saw decomposes into three non-bugs: the *_dir features are SIDE-RELATIVE (ml/features.py:109-115, dir_sign at :342 — short rows print sign-flipped derivatives by construction), ±6 values are vol-normalized returns not [-1,1] flags, and there is NO candidate leaderboard to sort backwards (round-robin _entry_assets, main.py:3911-3921). New concept page concepts/side-relative-features carries the reading hazard; the adjudication is binding — no re-litigation from raw-row reads. THE REFUTER THAT FAILED AND STILL PAID: the data lens surfaced a symmetric ANTI-momentum pattern at h432 (longs ret_12_dir>0.5 wr 21.8% n=2620 vs 22.6% below -0.5; shorts 17.5% n=1849 vs 21.4% — momentum-agreeing trades win LESS in BOTH cohorts; symmetry rules out a sign bug) — filed as a LEAD with both caveats (pre-cut-boundary, pooled) and registered as owed 69 (re-measure post-epoch, disaggregated). ASSET-SELECTION VERDICT MIXED: per-asset regimes/features/vol-scaled stops/breakers/caps under a GLOBAL meta-model + gate thresholds; bracket cost floor flattens majors to identical 1.50/2.00 sl/pt while FLOW/ARB/MINA differentiate; ETH/BTC fill concentration is gate-confirmation frequency (gate_confidence flat 0.81-0.90), not preference — filed to entities/liquiditybot as the standing selection description. venue_disloc_dir is ANTI-oriented vs basis_dir (kraken-rich vs kraken-cheap positive) — documented intended, model-input-only, the closest real thing to a backwards derivative. ALL 14 COMMITS since 2026-08-10T11:00Z verified claim-vs-diff clean. LEDGER AUDIT COHERENT with the $800 stressor; anomalies adjudicated: 138s equity reset lag BENIGN; orphan-close postmortem undercount (long-book flatten ETH d5513dd5 / BTC e35c0a59, no thesis at close) FIXED with degraded orphan_close path rows in ml/postmortem.py (uncounted-exclusion, the no-filter-predicate kind); PAXG live row tb_time/h432 BY DESIGN (label_era_of is a pure function of the barrier string); long-book live rows missing post-migration schema columns OPEN = owed 68; and the fee note ("padded 25/40 vs Kraken 16/26, intentional stress") flagged as inheriting the STALE 16/26 schedule — contradiction callout on concepts/cost-truth (standing panel finding: Tier 1 is 40/80; the falsified premise still propagates from config.json:325). FIXES SHIPPED IN RESPONSE: ml/postmortem.py degraded orphan_close rows; config_guard checks for the stop_round knobs (first declaration-consumer JOIN check — the phantom-knob class now FATALs at boot instead of silently defaulting); three doc-drift fixes (stop_placement phantom-block docstring, Osler test docstring, _goals_doc rewritten for $800). Touched: sources/session-20260811-operator-audit (new), concepts/side-relative-features (new), concepts/uncounted-exclusion, concepts/adversarial-verification, concepts/cost-truth, entities/config-guard, entities/osler, entities/long-book, entities/liquiditybot, synthesis/documentation-drift-register, synthesis/owed-measurements (docket 52-69), index, log.

## [2026-08-10] ingest | The apply-batch (66744ed1) - owed 68 CLOSED, owed 69 INSTRUMENTED, orientation pins, stale-fee note at the source, NOT-applied register

NEW sources/session-20260811-apply-batch (commit 66744ed1, battery 19 GREEN, 3602 tests, deployed, runner verified back). (1) OWED 68 CLOSED - diagnosis sharpened at the fix: the long-book entry path computed _feature_extras and DISCARDED it, so meta never carried avail and every long-book live row shipped blank avail_*/quotes_frozen; meta[avail] now threads from the SAME extras dict the features were built from (main.py long-book entry, feature-build-instant semantics), pinned in tests/test_long_book_integration.py. Rule-16 pass on the closing disposition: the audit's two blank ETH/BTC rows were ALSO explained by entry-time tuple shape (registered before avail existed) - both true, the writer defect real and current. History not rewritten; pre-fix long-book rows stay blank and never-pooled on the record axis. (2) OWED 69 INSTRUMENTED, STILL OPEN - defensive_cadence_report.py section 2b: momentum-alignment win rates with the side-relative caveat PRINTED on the report's face and lifetime-POOLED vs since-capital-epoch tables printed separately. First run (h432-only, pooled, context only): anti-momentum gradient MONOTONE both directions - longs with/flat/against 30.9/35.3/41.8 (n=194/184/158), shorts 25.9/37.1/47.4 (n=197/159/78) - STEEPER than the audit verifier's all-era numbers; post-epoch clean cohort (n=36) leans OPPOSITE (longs-with 81.8 pct, n=11) - stays a LEAD until clean accrual is real. (3) Orientation pins in tests/test_ofi_feature.py: basis_bps Kraken-cheap-positive, venue_disloc_bps Kraken-rich-positive, pinned BY SUBTRACTION ORDER; harmonizing either sign = feature-meaning change under MODEL FREEZE requiring adjudicated retrain. (4) Stale-fee note lands IN config.json market_maker: min_half_spread_bps=26 descends from the STRUCK 16/26 schedule (NEW surface on the falsified-schedule map - the quote floor); retuning is quote-pricing = cohort-resetting, HELD with the fee constants behind the h432 gate - the drift register's recurrence row closed AT THE SOURCE. (5) NOT-applied register (deliberate): _dir column renames (corpus schema churn under freeze), venue_disloc sign flip (frozen feature meaning), majors' cost-floor un-flattening (stop geometry - ALGO-5 amendment scope, owed 67). Docket after the batch: 68 closed; still open 52, 54, 55, 59, 60, 61, 63, 64, 67, 69. Touched: sources/session-20260811-apply-batch (new), synthesis/owed-measurements (68/69/67), entities/long-book, concepts/side-relative-features, concepts/cost-truth, synthesis/documentation-drift-register, sources/session-20260811-operator-audit (follow-ups), index, log.

## [2026-08-14] ingest | Cohort instruments — exec_era ABSENT vs blank qualifies the boundary table, ML-083's unlock has no floor (fired at 48x), the h432 geometry cannot pay, and the DoD battery had been dying at collection

NEW sources/session-20260814-cohort-instruments (measurement-only session; commits 61c3b5c1 instruments + 258d2eeb designs; battery green: pytest 3656 passed/1 skipped, smoke 219/0, assurance 48/0, overfit 7/0, ruff clean, pyright shipped scope 0 errors, bandit 0, compileall 0). Filed same-session per governance rule 12. Nothing minted: no entry decisioning, sizing, stop/exit geometry, fill sim, fee booking or order lifecycle touched.

(1) THE BOUNDARY TABLE'S DECIDE-BY-TS RULE IS QUALIFIED, NOT OVERTURNED. comparability-boundaries said "pre-schema rows are deliberately blank = decide by ts... a feature of the schema, not a gap in it". Measured: fills.csv field-width histogram {17: 1059, 16: 6} (double-derived; a first pass by naive comma-splitting wrongly said 170 and was discarded). exec_era is column index 16, the LAST of 17, so a writer whose COLS predates the stamp emits a 16-field row where the field is ABSENT, not blank - and deciding those by ts reads era-7 while their fill physics is pre-boundary-#4. git reflog puts the live tree at 21769fb8 (2026-08-07) from 08-11 19:50 until the 08-12 20:21 fast-forward; boundaries #3, #4 and cut #7 are all NON-ancestors, so the TTL-hazard bug and the ~1.88x near-touch double-count were both live for those fills. Three-way rule now implemented (scripts/cohort_eval.py) and pinned (tests/test_cohort_homogeneity.py). COHORT IMPACT: 4 of 13 accruing era-4 trips carry a stale-binary leg; 6 of 13 straddle a mid-flight champion deploy; two distinct champions opened trips. Contradiction callout filed on comparability-boundaries. No cut minted or moved - this reports contamination against the EXISTING cuts, and whether a mixed cohort resets accrual is operator-owned, deliberately not taken.

(2) DEPLOY-DEADLOCK GAINS A THIRD POLARITY - the release mechanism over-releases. ML-083's era-orphan unlock (main.py:6387) sets the champion badge aside and applies the cold-start bar Brier<0.25 whenever trained_rows > len(X). Its own comment records the case it was built for on 2026-07-29: 4,823 vs 1,516, a 3.2x ratio. It fired 2026-08-14T15:14:13Z at 10,217 vs 211 - 48x - promoting a logistic trained on 2.0% of the incumbent's data whose own family_brier was 0.33105, WORSE than the 0.25 a constant p=0.5 predictor scores. Only upstream floor is len(X)<60. The gate then DEFENDED the regression: post-deploy trained_rows became 211, the unlock stopped firing, and the next challenger - with a BETTER oof_brier 0.17959 - was rejected by the like-for-like branch for having no shared row set. Rule extracted: a gate's refusal to compare is the gate working, but the escape hatch that resolves an unfalsifiable badge must itself be BOUNDED - unbounded, "an unfalsifiable badge may not gate forever" degrades into "a sufficiently stale badge may be ignored entirely", so the staler the badge the weaker the bar. Retraction filed on the same page's session source: this session's FIRST reading blamed champion_bar "loosening" 0.15985->0.21936 with the challenger clearing by 0.00049 - WRONG; champion_bar is monitor.champion_brier recorded for observability only (main.py:6467), never a threshold, and the 0.00049 was coincidence.

(3) THE h432 GEOMETRY CANNOT PAY - and owed 67's trigger has NOT fired. Breakeven for a triple barrier is sl/(pt+sl). On all h432 rows (n=259 at 23:38Z, n=262 thirty minutes later - live file, as-of): median pt 2.064%, median sl 1.548%, payoff 1.333, so breakeven needs a 42.9% target-hit rate and the realized rate is 22.4% (41 tb_pt vs 141 tb_sl) = -0.734% per barrier-resolved path GROSS, before any cost. Arithmetic, not a fit, model-INDEPENDENT. Caveats on the instrument's face: 77 tb_time paths resolve at neither barrier and are excluded, and 119 of 123 recent rows are candidate, so this is COUNTERFACTUAL geometry expectancy and NOT the era-4 verdict. SESSION ERROR FILED AND CORRECTED: this was first reported as firing owed 67's ~30-uncensored-path trigger "6x over" at 182. Retracted - owed 67's measure is the ALGO-4 ledger outputs/trade_paths.csv, which holds 10 rows against ~30. The 182 are barrier resolutions, a different population. Two measures whose names both reduce to "paths" are not interchangeable; owed 67 updated with the corrected counter plus the geometry numbers as CONTEXT for the eventual adjudication, not a condition of it.

(4) FALSE-GREEN'S EIGHTH WAY, and the sharpest - there was no green, there was NOTHING. A globally-installed SuperClaude pytest plugin APPLIES four marks at collection (unit/integration/hallucination/performance) while registering only its own different set; under this repo's deliberate --strict-markers that raises INTERNALERROR mid-collection: "no tests ran in 4.28s". Any session on this box running the DoD matrix was verifying nothing. Fixed by DECLARING the four marks in pyproject.toml - not by -p no:superclaude (a fix that survives only by being remembered is a debt wearing a friendly face) and not by loosening strict mode (whose own comment records the gate hole it holds shut). Verified both ways: 3656 passed/1 skipped with the plugin disabled and the IDENTICAL 3656/1 with it enabled, so declaring changed nothing about what runs.

SUPPORTING - labels/day, exact 24h window [1786664298, 1786750698], snapshot 2026-08-14T23:38:18Z: 123 labels, 119 candidate / 4 live, all resolved, backlog 0; 12-day mean 124.5/day of which 3.0 live/day (2.4%); 3 of the 4 live rows are probe=1, so the gate itself produced exactly ONE entry in 24h (BTC, label=0, -$0.42) and 24h net -$0.15 double-derives pipeline_audit.md by an independent route. label_era base rates span 40x (exit_sim_time_stop 0.0065 n=459 to legacy 0.2611 n=1781); current triple_barrier_h432 is 0.2239 at n=259 = 2.5% of the 10,559-row corpus, which is why the retrain matrix was 211 - era exclusion working CORRECTLY against very little honest data.

ALSO SHIPPED: DL-2 headless git hardening (all 6 git call sites across auto_update/corpus_sync/remote_control/telemetry_backup now make git FAIL rather than ASK - GIT_TERMINAL_PROMPT=0, empty askpass, GCM_INTERACTIVE=never, credential.interactive=false via GIT_CONFIG_COUNT/KEY_0/VALUE_0 so argv is untouched; telemetry_backup's two calls were UNBOUNDED and are now bounded at 300s) and the ML-060 lineage gap (registry held 134 registered and ZERO deployed events; both cutover sites now record it).

THE CAUSAL CHAIN, filed as the reason these are ONE docket item: the h432 cut shrank the honest corpus -> era exclusion correctly refused to pool -> orphan ratio 48x -> ML-083 fired -> a negative-skill model landed inside the accruing verdict window -> 6 of 13 trips straddle a deploy. Adjudicating ALGO-5 without the ML-083 floor re-runs the chain at the next geometry cut.

Touched: sources/session-20260814-cohort-instruments (new), synthesis/comparability-boundaries (contradiction callout, three-way rule), concepts/deploy-deadlock (third polarity), synthesis/owed-measurements (67 corrected counter + geometry context + ML-083 coupling), index, log.

## [2026-08-14] update | Cohort-instruments ingest EXTENDED — contradiction register, owed 73/74 registered, probe-livelock's terminal state, era-exclusion's measured cost, pooled-populations' split no longer inert

Extends the ingest above (same session, same commits 61c3b5c1 / 258d2eeb). The first pass touched 6 files and left the ingest checklist incompletely served — specifically DOMAIN RULE 6 ("contradictions go in open-contradictions-register, not silently into a page") was violated: the exec_era callout was filed on comparability-boundaries alone. Corrected here, plus four concept/synthesis pages the findings genuinely move.

(1) OPEN-CONTRADICTIONS-REGISTER, two entries. FIRST, the standing incommensurable-champion-scores entry (class OPEN since 2026-08-09) FIRED AGAIN IN THE OTHER DIRECTION: that entry worried about the SILENT case ("a corrupt population that happened to be SMALLER would compare successfully and pass unremarked"); what happened on 08-14 is the loud case with no ceiling — ML-083's row-count proxy fired CORRECTLY at 48x and, having fired, applied the bare cold-start bar. So the proxy is not the weak link; the unlock it triggers has no floor. Generalization recorded: an unfalsifiable claim is not made falsifiable by refusing to evaluate it — refusing merely moves the unfalsifiability from the comparison into the BYPASS. Partial progress toward that entry's stated closing condition: 61c3b5c1's deployed lifecycle row now carries rows/family/oof_brier (registry previously held 134 registered and ZERO deployed); corpus revision and era set are still absent. SECOND, a new entry for exec_era ABSENT vs BLANK, class OPEN — not because the read is still wrong (cohort_eval is three-way and pinned) but because whether a cohort containing 4 stale-binary trips and 6 deploy-straddling trips may still serve the pre-registered n=50 verdict is an operator adjudication that has not been taken. Both entries share a shape worth naming: provenance the system genuinely HAD was not carried to the place that needed it.

(2) OWED 73 REGISTERED — the ML-083 unlock floor. Built for a 3.2x orphan ratio, fired at 48x, promoted a logistic whose family_brier 0.33105 is worse than a constant p=0.5 predictor; only upstream guard is len(X)<60. The regression is STICKY: post-deploy trained_rows fell to 211, the unlock stopped firing, and a BETTER challenger (oof 0.17959) was then rejected by the like-for-like branch — correct fail-closed logic defending a worse incumbent. What would close it: an operator-adjudicated bound (orphan-ratio ceiling / absolute minimum matrix / required shadow period) PLUS a rollback path, since ModelRegistry.note() supports "retired" and nothing calls it. NOT startable — entry decisioning, rule 17. NOT independent of item 67.

(3) OWED 74 REGISTERED — the cohort-contamination adjudication. Measurement DONE and printing every run; the RULING does not exist. 4 of 13 trips carry a stale-binary leg, 6 of 13 straddle a mid-flight deploy, two distinct champions opened trips, a fifth trip joins on close. Three named options (stands-as-registered / exclude-contaminated / reset), tool deliberately chooses none, selection rule byte-identical and pinned. Timing note: this COMPOUNDS at ~3-4 closes/day.

(4) PROBE-LIVELOCK gains its terminal state. The fix worked and the result is the loop's END STATE rather than its escape: over the exact 24h window, live rows are 4 of 123 and THREE OF THE FOUR ARE probe=1 — the gate itself produced exactly ONE entry in 24h (BTC, label=0, -$0.42) against three probes (+0.02/+0.13/+0.12), net -$0.15 double-deriving pipeline_audit.md by an independent route. 12-day mean 124.5 labels/day of which 3.0 live/day (2.4%). The drought floor is no longer a floor under a temporary hole — it is supplying essentially the entire live-label stream and therefore essentially the entire era-4 accrual. Two consequences stated, neither a proposal: the verdict is accruing on a population the strategy's own gate did not select, and the accrual RATE is set by the probe allowance rather than the gate.

(5) ERA-EXCLUSION gains what correct exclusion COSTS. label_era across all 10,559 rows: triple_barrier 5328 (50.5%), exit_sim 2732 (25.9%), legacy 1781 (16.9%), exit_sim_time_stop 459 (4.3%, base rate 0.0065 = 3 positives in 459), current triple_barrier_h432 259 = 2.5% (0.2239). Base rates span 40x, which is the AFFIRMATIVE case for the filter — refusing to exclude would be indefensible. But keeping only the current era leaves a 211-row matrix where the champion learned on 10,217, and that 48x gap IS the ML-083 firing condition. Generalization filed: the filter's correctness and the promotion defect are the same event seen twice — a filter that correctly refuses to POOL must be paired with a promotion gate that correctly refuses to PROMOTE on what little remains.

(6) POOLED-POPULATIONS — the probe/conviction split is NO LONGER INERT, a direct status change to that page's standing "live reads unknown 200 / probe 0 / conviction 0, because every live row predates the flag". Live rows now carry it: probe=1 x3, probe=0 x1 in the 24h window. Owed 54 moves shipped-and-inert -> POPULATING, NOT closed (at n=4 the original specimen still cannot be reproduced from the live split). Consequence recorded: the live half of the corpus is now 75% probe, a lane deliberately exempt from the EV gate, so the pooled live population is mostly the population that page says must never be pooled. Second axis: label_era base rates span 40x corpus-wide, and the deploy gate already enforces no-comparing-across-base-rates BETWEEN champion and challenger while not enforcing it WITHIN the training matrix. Third, filed explicitly as a LEAD and not a finding: source=live base rate 0.750 (3/4) vs source=candidate 0.227 (27/119) — at n=4 the Wilson interval is nearly the unit interval and this is evidence of NOTHING; recorded only because the model trains on a pool that is 96.7% candidate and is applied to live decisions.

All 8 touched pages had their `updated:` frontmatter bumped to 2026-08-14. Touched in this extension: synthesis/open-contradictions-register, synthesis/owed-measurements (73 + 74 registered), concepts/probe-livelock, concepts/era-exclusion, concepts/pooled-populations, log.

## [2026-08-14] update | Cohort-instruments ingest COMPLETED — the two narrative-carrier pages served, lesson 13, the geometry arithmetic on the thesis, and the floors/promotion split

Third and final pass of the same ingest (commits 61c3b5c1 / 258d2eeb, now PUSHED: origin/claude/remote-control-e3h815 4609a1a9..258d2eeb, main and the feature branch converged to the same head). Closes the ingest checklist item the first two passes left unserved — "check whether it changes the-money-path-thesis or learning-pipeline-arc, those two carry the live narrative" — plus the two concept pages whose standing text the findings falsify.

(1) LEARNING-PIPELINE-ARC gains LESSON 13. Lesson 9 recorded the arc's best moment: the pipeline re-derived an honest champion BY ITSELF once the data was true. The same machinery ran unattended on 08-14 and produced the inverse by the same property - autonomy. Chain, every link individually correct: h432 cut leaves 259 current-era rows (2.5% of 10,559) -> era exclusion correctly refuses to pool eras whose base rates span 40x -> 211-row matrix vs a champion trained on 10,217 = 48x orphan ratio -> ML-083's unlock has no floor, badge set aside, bare cold-start bar -> a logistic with family_brier 0.33105 (worse than constant p=0.5) deploys INSIDE the accruing era-4 window -> the gate then DEFENDS it, rejecting a better 0.17959 challenger for having no shared row set. LESSON 13: a self-improving loop is only as safe as its worst permitted promotion. Lesson 9's healing and this regression are THE SAME CAPABILITY; what distinguished the good case was that the DATA had been repaired first. Autonomy is a multiplier on corpus quality, in whichever sign the corpus has. Also corrected on this page: its standing "item 54 shipped but INERT (unknown 200 / probe 0 / conviction 0)" is superseded - the split is POPULATING (probe=1 x3, probe=0 x1) though it closes nothing at n=4.

(2) THE-MONEY-PATH-THESIS gains the geometry's own arithmetic, upstream of every model question. The thesis was already decomposed to gross edge ~0 against 32.8x fees; the same fact is now measurable straight off the label geometry with NO MODEL IN IT: breakeven target-hit rate = sl/(pt+sl). On h432 (n=259 at 23:38Z, n=262 thirty min later - live file, as-of): median pt 2.064%, median sl 1.548%, payoff 1.333 -> breakeven 0.429 vs realized 0.225 -> -0.734% per barrier-resolved path GROSS, pre-cost. Model-INDEPENDENT, which is why it belongs on the thesis rather than the ML lane and why it sits upstream of the freeze question. Sharpens rather than disturbs the two 08-02 nulls: exit design minimizes bleed and does not create edge - here the bleed is arithmetic in the geometry itself. Caveats printed per domain rule 1: 77 tb_time paths resolve at NEITHER barrier and are excluded, and 119 of 123 recent rows are candidate, so this is COUNTERFACTUAL, sim-side, and NOT the era-4 verdict; it is context for the ALGO-5 adjudication, not its trigger (that trigger is the ALGO-4 ledger at 10 of ~30). Filed alongside: what moved on the verdict instrument is not a number - the era-4 population is no longer known-homogeneous (4/13 stale-binary legs, 6/13 straddling a deploy, owed 74), so the gate remains sole arbiter but WHAT IT WILL ARBITRATE OVER is now an open operator question that compounds at ~3-4 closes/day.

(3) EVIDENCE-FLOORS gains the mirror of its 2026-08-09 entry. That one was floors CLEARING on a false counter (live_clean 5->299, four families admitted in one step). This is floors WORKING PERFECTLY AND BEING BYPASSED: live collapsed 314->5, admitted families went 5->1 with gbt/blend/mlp/adaptive_gbt all GATED (ML_LADDER_GATED logged with the admitted/gated/live payload), matrix 181->211->237 - and the sole survivor deployed anyway, around the floors via ML-083. LESSON: evidence floors gate SELECTION, not PROMOTION. A floor that admits exactly one under-evidenced family has not approved that family; it has reported that the corpus can support at most one, and nothing downstream read it that way. The page already treats four floors CLEARING at once as an alarm; four floors GATING at once deserves the same status and currently raises none.

(4) LABEL-ERA gains the two-axes warning. The corpus now carries TWO era stamps on DIFFERENT axes - label_era (signal_history.csv, label definition, triple_barrier_h432) and exec_era (fills.csv, fill-simulator regime, 7-e7d5ca1a) - and they move independently; a row can be current on one and retired on the other. This session conflated a related pair once already (barrier resolutions vs trade paths), so the warning is filed explicitly. Per-axis facts: LABEL axis, current era is 259 of 10,559 = 2.5%, base rates span 40x; FILL axis, exec_era has a failure mode this page's own doctrine predicts - the page records that live rows "depend ENTIRELY on the persisted column", and six fills.csv rows have exec_era ABSENT rather than blank. GENERALIZATION: "decide by timestamp when the stamp is missing" is safe only when a missing stamp means the writer was OLD-BUT-HONEST; it is unsafe when a missing stamp means the writer DID NOT KNOW THE COLUMN EXISTED - indistinguishable from the value, distinguishable from the ROW SHAPE. Same family as this page's 08-09 correction: a derived era is a guess wearing a column's name.

Touched in this pass: synthesis/the-money-path-thesis, synthesis/learning-pipeline-arc, concepts/evidence-floors, concepts/label-era, log. All four `updated:` bumped. Ingest total across the three passes: 15 pages. Lint green.

## [2026-08-15] ingest | The docket answered — 16 of 16, ~88% conceded, and seven objections amended BY the verification that upheld them

Recovery + closure of the red-team docket against `f756676e`. The
originating session (`4b5e9197`) was compacted mid-answer and ended; the
charge survived only inside a temp workflow artifact subject to cleanup,
and the panel system itself (`.claude/workflows/red-team-panel.js`) was
never committed. Both now in-repo:
`docs/quant/2026-08-15_red_team_docket_f756676e.md` (the charge),
`docs/quant/2026-08-15_docket_dispositions.md` (the answer),
`docs/quant/2026-08-15_program_history_and_priorities.md` (the arc).
Commits `bb7c193b`, `426c2e80`, `e3d93305`, `e2d12fca`.

(1) THE ONE DEFECT WITH LIVE CONSEQUENCES, now fixed.
`gate_truth_report.py:194` filtered `label_era == "triple_barrier"` — the
RETIRED unqualified 96-bar era — while `ml.label_max_bars` has been 432
since `7566ea88`. Measured: it read **5,328 retired rows (4,228
instrumented)** and **zero** of 359 deployed `h432` rows, then printed a
confident **XV-040 ALIGNED**. It was not failing visibly; it was
answering about a label geometry the bot stopped using. Fixed to derive
the era from config via `triple_barrier_era()` and to PRINT the era on
the report's face. Verdict corrected to **XV-042, effective n 56.1 < 100,
no verdict yet**. Generalization for `concepts/false-green`: this is the
false-green's sibling — not a green that measured nothing, but a
**confident verdict that measured the wrong population**, and the
distinguishing property is identical: the instrument never named its
corpus.

(2) THE TESTS PINNED THE DEFECT. All 8 fixtures hardcoded
`label_era: "triple_barrier"` while passing the real `config.json` (432),
so they passed only because the REPORT hardcoded the same literal. Two
hardcoded copies agreeing is not a test. Now config-derived. The new
regression pin was PROVEN non-vacuous by mutation (revert → RED). Its
first draft was itself tautological — `assert retired not in text` can
never fail because `"triple_barrier_h432"` CONTAINS `"triple_barrier"` —
committed by the author while fixing that exact defect class. Filed to
`concepts/adversarial-verification`: the tautological-pin trap is not a
lapse of care; it is the DEFAULT outcome of asserting about a name
instead of a behaviour.

(3) SEVEN OBJECTIONS AMENDED BY VERIFICATION. ~88% conceded would read as
capitulation without this: OBJ-15's arithmetic was wrong (7 of 14, not
13 — it missed `:955`) and its OF-4 rider contradicted CLAUDE.md's own
text; OBJ-10's remedy was REFUSED (the banned `in ...upper()` spelling
fails OPEN on false positives — proven over an EXHAUSTIVE scan of all
1,114,112 codepoints, zero counterexamples); OBJ-3 cited a file where its
evidence appears 0 times; OBJ-13(a)'s severity class was refuted by four
measured pyright runs; OBJ-7 carried a +1 offset (a 16:13Z artifact
arbitrates); OBJ-4's stated mechanism was refuted — the loader returns an
IDENTICAL count across a 46-day clock span on a byte-identical file, so
the drift is file growth, not wall-clock label resolution.

(4) OWED — NEW, STRUCTURAL (OBJ-8). Era exclusion is the TRANSMISSION,
not the trigger. Counterfactual matrix on a frozen corpus: the same
filter over a mature era loads **5,287 rows REAL**, so exclusion alone
can never drive a >640-row corpus under the floor. The trigger is the era
RESET. And `ml.era_exclusion.min_new_era_rows = 150` sits BELOW the
overfit floor of **640**, which GUARANTEES a window
`150 ≤ new_era_rows < 640` where the filter is armed and the battery is
simultaneously under its floor. **We are inside that window now
(353/640)**, and it recurs at EVERY horizon migration. The arming cliff
is located to the row: −10,165 loaded in a single append at
2026-08-14T00:15:08Z. NOT started — 150 and 640 are measurement
standards, and CLAUDE.md forbids moving one so a gate reads "real".
OPERATOR adjudication.

(5) OWED — `forced_off` IS UN-FENCED. `core/config_guard.py:911-914`
type-checks it as a bool and nothing more, while `forced_on` carries a
semantic FATAL at `:925-934`. Flipping it moves the battery 353 → 10,522
and SYNTHETIC → REAL over a corpus mixing five label eras whose base
rates span 40× — the exact widening the new CLAUDE.md paragraph forbids
by floors, reachable through a config flag instead of through a floor.

(6) THE RECORD ITSELF HAS TWO DEFECTS, found while harvesting all 13
compaction summaries: one summary is a **byte-identical duplicate** of
another (same timestamp, same 18,873 chars, different line), and header
timestamps are **NON-MONOTONIC** — one stamped ~18h earlier than a
summary 2,268 lines before it. Transcript position does not imply
chronology. Anyone reconstructing history from these must sort by
content, not by offset.

Vault governance note recorded against this entry: the 08-15 source page
(`sources/session-20260815-scans-and-corrections`) was filed and indexed
but never LOGGED — this entry closes that gap. Separately, `wiki/index.md`
is stale: header claims 195 pages, actual count is 209, and four content
pages are unindexed including — with some irony —
`concepts/no-orphan-claims`, the governance rule page itself.

## [2026-08-15] update | The tautological CHECK — fourth specimen class, and the method that actually detects it

Extends `concepts/tautological-instrument` (sources 4→5, updated 2026-08-15).
Operator's framing, filed verbatim as the rule: *"static inference about
what a system does is nearly always vacuous; ask the running system."*

The page's first three specimen groups are instruments inside the running
bot (the bracket-divergence gauge 94% incapable of reading anything else;
the staleness veto aging a timestamp with the same frozen `now` that
stamped it; the `marks_age_sec` twin). The fourth class is the
**verification tooling the author writes to check their own work** — and
it ranks above the others because a vacuous check is what lets the rest
ship.

FOUR vacuous checks in one session, THREE written while fixing this class:

(1) The docket's two BLOCKING objections were both this. `OBJ-2` — a pin
whose message asserted "exactly ONE place may derive `on_synthetic`" while
counting the ASSIGNMENT SPELLING (=1) against five real derivations
(`overfit_check.py:704, 833, 1075, 1084, 1089`). `OBJ-14` — the same pin
survives the exact mutation it forbids.

(2) The guard written against tautological pins was itself tautological.
`tests/test_pin_quality.py` draft 1 required the era literal on the same
line, so it did NOT fire on `assert retired not in text` — the precise
spelling the author had corrected minutes earlier. Found by INJECTION,
invisible to reading.

(3) Its draft 2 then cried wolf on `tests/test_cohort_homogeneity.py:208`,
where `label_era` holds a collection and membership is legitimate — the
other route to vacuity, since a guard that fails on correct code gets
deleted.

(4) The Grafana coverage analysis returned a confident **"0 dead of 181"**
TWICE. First by matching every metric against a bare `liquiditybot_`
prefix harvested from `gc_pusher.py:289` (`f"liquiditybot_{key}"`), making
the predicate always-true; then by expanding 18 f-string prefixes × ~425
string literals into 7,650 synthetic names. Only `collect()` against the
live `status.json` gave a real answer: **27 of 181 queried metrics (14%)
are not produced**, 23 of them on the execution board.

THE METHOD, now tabled on the page. This page already asked the right
question — *"what would this instrument have to see in order to read
differently?"* — and this session supplies how to ANSWER it: not by
reading. Mutation (reverting the era fix turned the new pin RED),
injection, exhaustive enumeration (all 1,114,112 codepoints for OBJ-10),
controlled experiment (4 pyright runs proved CLI paths override config
`include`, where the docs would have said the opposite), and replay across
a swept parameter (identical loader count over a 46-day clock span,
refuting OBJ-4's stated mechanism). Common shape: **make the thing produce
an output it could not produce if the claim were false.**

COROLLARY for delegated work, owed into `USAGE.md`'s measurement contract:
an agent returning a clean result from a static scan has reported NOTHING
until the scan is shown to fail on a planted defect. "0 findings" and "the
scan is broken" are the same observation until separated.

SEPARATE FINDING from the same analysis, filed here and owed to a board
rebuild: the Grafana boards are not badly designed, they are badly FED.
The 27 dead references reduce to TWO root causes — `ml.load_stats == {}`
and `orders == {}` in the live status — and `gc_pusher` is CORRECT to emit
nothing there (its own comment: a fabricated 0 would read as "exclusion
off" when the truth is "not yet measured"). But no panel says "not yet
measured", so honest absence renders as broken. That is `concepts/false-green`
inverted: a panel that cannot distinguish MEASURED ZERO from NEVER MEASURED.
Structural note recorded alongside: 39 of 58 command-board panels are stat
tiles against only 2 timeseries, so the boards answer "what is the value"
and almost never "is it getting better or worse".

Touched: `concepts/tautological-instrument` (frontmatter bumped), log.

## [2026-08-16] correction | The 10 bps Kraken tier never existed — an uncited parenthetical became vault knowledge

RULE-2b VIOLATION BY THIS ASSISTANT, corrected same session, both sides
flagged. `docs/quant/2026-08-01_cost_to_volatility_horizon_mismatch.md`
contained *"At 10bps/side instead of 25 (**a Kraken volume tier**)"* — the
parenthetical asserted a fee tier **with no citation**. It was then filed
into `concepts/cost-to-volatility-ratio` as settled knowledge and cited
from there into a boardroom brief five days later.

**The vault already held the answer.** [[sources/session-20260807-institutional-review]]
§C, triple-confirmed by three independent fetches on 2026-08-07: Tier 1
($0+) **40/80**, Tier 2 ($2.5k+) 30/60, Tier 3 ($10k+) 22/38, **Tier 5
($50k+) ~15/30 is the DEEPEST row.** No 10 bps row exists at any volume.
[[concepts/cost-truth]] has carried this correctly since 08-07.
Recall-before-derive would have caught it in one grep; the vault was not
consulted before deriving.

**The correction runs the WRONG WAY, which is why it matters.** An $800
book is Tier 1, so `config.json`'s 25/40 UNDERSTATES fees and every
cost/sigma figure derived from it is optimistic:

  premise                          round trip   cost/sigma   breakeven hit
  25 bps maker/maker (as written)     0.50%        0.82          0.567
  Tier 1 maker/maker (40 bps)         0.80%        1.31          0.650
  Tier 1 @ observed 60.6% taker       1.285%       2.11          0.784
  zero fees                           0.00%        0.00          0.4286

The "cut fees to reach a 5.4-hour hold" lever does not exist. Corrected on
all three surfaces the same session: the vault page (callout), the source
doc (callout), and the brief (pillar RETRACTED).

SECOND RETRACTION, same brief, same class. Its other case-FOR pillar cited
`delta_auc = +0.033` "data-starved — more rows are still buying skill".
**That figure exists in no artifact on this machine** (grep of `outputs/`
and `docs/` returns nothing). The only real-data reading — cloud-mirror,
2026-07-31, 2,141 rows — carries the OPPOSITE SIGN: *"learning curve trend
FLAG — DECLINING (delta_auc=-0.034) — later rows are HURTING skill"*. Both
of today's reports skip the metric entirely: *"SYNTHETIC benchmark dataset
— corpus-size trend has no market meaning"*, on 347 rows against a 640
floor.

**Both retracted pillars pointed the same way — toward continuing.** A
brief written to adjudicate the false-green class contained two false
greens, both flattering, both the author's. Filed to
[[concepts/tautological-instrument]]'s fourth specimen class as the
strongest instance yet: the failure survives being *known about* and
*written about* in the same document.

GENERALIZATION worth more than either fact: **an unsourced parenthetical is
the cheapest way to manufacture vault knowledge.** "(a Kraken volume
tier)", six words, no citation, survived filing, indexing, and five days of
reuse. Rule 2b exists for exactly this and was not applied. The defence is
not care — it is the grep before the claim.

Touched: `concepts/cost-to-volatility-ratio` (correction callout),
repo `docs/quant/2026-08-01_...` + `2026-08-16_boardroom_brief_money_path`
(both retractions), log.

## [2026-08-16] correction | The anti-predictive finding is REFUTED — wrong null, and the artifact was larger than the effect

The adversarial seat of the boardroom panel was pointed at the brief that
convened it. It killed the brief's only fresh measurement — which was this
session author's own, reported repeatedly, and filed into the vault.

THE CLAIM: "entry selection is anti-predictive", P(hit target first) 0.258
vs a driftless gambler's-ruin expectation of 0.4286, **z = −3.24**,
measured at both horizons (h24 −4.31, h432 −4.14).

THE REFUTATION: `b/(a+b)` is the first-passage probability for an
**unbounded-time** walk. These labels are **censored at a vertical
barrier**, and the profit target sits FARTHER out (a/b = 1.333) so it
takes longer to reach — censoring therefore removes PT-bound paths
**preferentially**. Conditioning on resolution is not neutral; it
manufactures exactly the sign reported.

VERIFIED INDEPENDENTLY by this author before accepting it — exact lattice
DP, no RNG, which converges to 0.4396 ≈ 0.4286 at ~0% censoring and so
validates itself:

  censoring    correct driftless P(PT|resolved)
     ~0%              0.4396   <- converges to gambler's ruin
    48.6%             0.3758
    86.4%             0.2351

The h24 sample was **87.8% censored**. Against the correct null of ~0.235
its observed **0.258 is ABOVE chance** — weakly PRO-predictive. Applying
the correct null AND this project's own effective-n standard (uniqueness
0.245 by de Prado concurrency):

              brief's null    correct null at n_eff
  h24            −7.05            +0.58  (SIGN FLIPS)
  h432           −4.21            −1.47
  pooled         −3.24            −0.63   (p = 0.53)

**Nothing significant remains.** The honest position is that the labeled
bet is INDISTINGUISHABLE FROM CHANCE, not worse than it.

WHAT THIS DOES TO THE MONEY-PATH CASE. Four of the five "case AGAINST"
items fell in the same audit: the 32.8x fee ratio is 98.6% pre-correction
(only 14 of 415 trips ran on today's simulator, where gross is POSITIVE)
and divides by a statistical zero (gross −11.89 ± 19.4, z = −1.20, so the
ratio's CI is [12.2x, +∞)); the geometry deficit is stale by 47% (realized
0.291, not 0.225) and its implicit 0.000% null is also wrong for a
censored sample; and the "three INDEPENDENT refutations" share a data path
that commit `415af0f9` fixed in five scripts at once — four days after the
date they are cited under.

SURVIVING, and now the load-bearing evidence: **the verdict instrument
cannot resolve its own question** (sd 2.7341% vs an assumed 0.5%, n_eff
4.287 of 14, floor 1.40% against a +0.64% observation — robust across the
sd's full CI) **[⚠️ SUPERSEDED 2026-08-16 — these are an as-of read, not the
state. Re-derived by RUNNING cohort_eval at 2026-08-16T21:01:13Z: n = 16 of
50, n_eff = 5.249648119206663, mean uniqueness 0.328103, SE inflation
1.7458016289694764, sd 2.559127919795581%, observed gross mean
+0.6576563162731225%. The CONCLUSION strengthens rather than moves — the
floor at n=50 is 1.2636647844398836% at 2·SE (1.92x the observation) and
1.7701322903683439% at 80% power (2.69x), and the two conventions differ by
40.08% with neither named in the decision table.
See sources/session-20260816-catchup-08-12-to-08-16 §1-2 and owed 82.]**,
and **cost/sigma**, which is worse than stated: an $800
book is Tier 1 (40/80) giving 1.31, or 2.11 at the observed 60.6% taker
share, with measured population round trip 75.58 bps against 65
configured.

THE GENERALIZATION, filed to [[concepts/tautological-instrument]]: this is
the fourth specimen class again, in its purest form. **The conditioning
produced the statistic.** P(PT|resolved) could not have come out any other
way once the sample was censored asymmetrically — it is definitional, not
empirical, exactly like the bracket-divergence gauge that was 94%
arithmetically incapable of reading anything else. The author computed it,
reported it four times, and filed it, without once asking what the null
should be for a CENSORED sample. Static reasoning about a statistic is as
vacuous as static reasoning about code; the lattice DP settled in seconds
what argument had not.

METHOD NOTE worth keeping: the refuter attacked its OWN method too —
fitting sigma to observed censoring could in principle absorb a real
drift, so it checked, and found P(PT|resolved) is 9.9x more
drift-sensitive than the censoring rate, making the calibration a valid
nuisance-parameter fit rather than a circular one.

Touched: `sources/cost-to-volatility-horizon-mismatch` (retraction
callout), repo `docs/quant/2026-08-01_...` (section retracted) and
`2026-08-16_boardroom_brief_money_path` (4 of 5 AGAINST items corrected),
log.

## [2026-08-16] ingest | THE SESSION THAT DID NOT KNOW WHAT DAY IT WAS (VS Code 3b307393, 2026-08-11..16) - rule 19 (a session is not a citation) + rule 20 (an unstated protocol is an absent protocol), the remote_control.log that lied for a day, Docker deleted, the isolated backup

Operator directive: "everything - even the fact sessions can get mixed up - needs to be apparent to the wiki." Filed repo/host/tooling-side only; NO execution-era boundary minted (no entry decisioning, sizing, stop/exit geometry, fill sim, fee booking or order-lifecycle change), era-4 accrual untouched and unread.

(1) SESSION IDENTITY IS NOT STABLE - governance RULE 19, new page concepts/session-identity-is-not-stable. One VS Code Claude session persisted FOUR calendar days across several host-process restarts with its in-context "now" frozen at 2026-08-12 while disk reached 2026-08-16. RE-DERIVED at filing: 8cb56a82 (2026-08-12T18:24:10-05:00) .. c4272391 (2026-08-15T21:02:27-05:00) = 33 commits (32 non-merge + 1 merge), 24 by first-parent - the session's own "25" reproduces NEITHER, and the discrepancy is left standing because it is the thesis firing on its own source. Five measured failure modes: a frozen clock that planned around a tomorrow four days past; background monitors dead with the host (exit 4) while the session still awaited their notifications; MCP servers detaching mid-conversation (MCP_DOCKER, coinpaprika, TodoWrite); a user interrupt that killed four investigator subagents leaving a run with NO completion record - primary artifact wf_dd79a1a4-724/journal.jsonl re-derived as 12 lines, 8 started, 4 result, with a4ec4bab902f7c612 / a4ac7be5a385f31f2 / abd313aafc976fda4 / ad8f71d837e8b562f lacking any result line (the session had recorded "4 started, 0 result" - wrong shape, right substance; sibling wf_ff7688fb-22b is 7 started / 6 result); and stale out-of-order notifications. CONSEQUENCE: "a session found X" is not a citation - every filed claim carries a session identity AND a wall-clock date, and an in-session conclusion is RECALL until re-derived against disk (rule 18 obligation (b), now with a carrier-level mechanism rather than a caution about model memory). Standing WAKE PROTOCOL, snapshot-stamped at filing 2026-08-16T20:25:17Z: main @ c4272391, status.json DRY_RUN/RUNNING age 1.5 s, runner.lock 47 B mtime 15:25 local, 10 pythonw - and every pre-gap background task presumed dead.

(2) remote_control.log FORENSICS - the log lied, the ledger did not. Eight remote pause/snapshot ids (1785619944, 1785619947, 1785620492, 1785620496, 1785622353, 1785622357, 1785622365, 1785622368) appeared as RC-010 forwarded on 2026-08-01 and were absent from the exactly-once ledger. VERDICT: never real - pytest fixtures from tests/test_remote_control.py leaking into the operator's production log, because the pre-fix _log() ignored its root parameter while _save_consumed(root,...) and ControlChannel honored the tests' tmp_path. RE-DERIVED at filing: 16 log lines for the 8 ids, spanning 2026-08-01 16:32:24-17:12:48 local; outputs/remote_consumed.json holds 5 entries and has not been written since 2026-07-25 19:49 local. The fix 64b6fd52 is stamped 2026-07-31T20:48:07Z but this A/B tree ran its audit session on an older checkout - reflog "checkout: moving from main to fix/audit-20260801" 2026-08-01 15:45:05 -0500, "merge origin/main" (landing the fix) 17:20:10 -0500 - so contamination outlived the fix by 24.74 h to the first contaminated line and 25.53 h to the merge (the session said "~21 h": CORRECTED, finding unchanged and slightly stronger). FOUR independent confirmations that no real command existed: (a) fixture fingerprint - queued and RC-010 forwarded in the SAME SECOND, impossible for a 120 s poll, against the genuine command's 470.86 s (~7.85 min) lag, plus a deterministic "stale (1861s old > 1800s)" = MAX_AGE_SEC 1800 (scripts/remote_control.py:69, message at :198) against tests/test_remote_control.py:147's time.time() + MAX_AGE_SEC + 60; (b) git - exactly FIVE control/queue/* files have ever been committed across all refs (newest 1785026512-ccea155405.json in 6bf7009d, 2026-07-26T00:41:53Z) and NO Aug-1 blob exists in any tree, the in-session git fsck --unreachable sweep agreeing; (c) reflog - no force-push or rewrite near the window; (d) the hash-chained audit.jsonl shows no pause ack and continuous trading. LAST REAL COMMAND recovered from 6bf7009d: id 1785026512-ccea155405, cmd snapshot, issued_at 1785026512.5869443, issued_by "vm" - socket.gethostname() of the phone/web Claude cloud sandbox (this PC is DESKTOP-OS02KQS), applied 2026-07-25 19:49:42 local. RULES: (i) remote_control.log entries before 2026-08-01 17:20 local are UNTRUSTWORTHY in this tree - trust the ledger + pc_status envelope + paper-telemetry branch history, which agree one-for-one; (ii) DATE THE CHECKOUT, NOT THE FIX COMMIT - a defect is fixed where the fix is checked out, and a multi-worktree repo has as many "is it fixed?" answers as it has checkouts; (iii) this is QA-writes-production in the LOG plane, not the data plane. Benign artifact recorded: same-second "fetch_failed: cannot lock ref" pairs are two git children racing on refs/remotes/origin/paper-telemetry.

(3) DOCKER DELETED 2026-08-11 by operator order, audited clean FIRST: no Hummingbot (archived 07-09), only Docker Desktop's built-in kind sandbox - an nginx deployment "my-app" with zero requests since the Aug-7 restart and the Grafana k6 load-test operator with no TestRuns, ClusterIP only, apiserver 127.0.0.1:55743, no external exposure - burning ~38% of one core and ~900 MB RAM for ZERO bot value (the bot runs natively as 10 pythonw; observability is Grafana CLOUD, the local grafana/k6 image is a load tester). Removed: MSI uninstall, docker-desktop WSL distro unregistered, E:\DockerWSL, the AppData\Local\Docker junction, Roaming\Docker*, docker-secrets-engine, ~\.docker, ProgramData\Docker, Program Files\Docker, HKCU autostart, the Desktop "Docker (clean start).bat". PRESERVED: D:\Archive\hummingbot-docker-2026-07-09\docker_data.vhdx (only surviving copy) and the Ubuntu WSL distro - both re-verified present 2026-08-16, along with Docker's absence and 10 pythonw alive. CORRECTION to the session's own consequence claim: coinpaprika did NOT die with Docker - it is registered directly in the repo's .mcp.json as a hosted SSE endpoint (operator-approved 2026-07-24) and still works; what is true is that MCP_DOCKER's tools are gone while its registration SURVIVES in the global ~/.claude.json as a dangling entry. The tooling-only boundary is unchanged (the runtime never consumes MCP) and the bot never used either; the AF_UNIX broken-socket workaround is moot.

(4) ISOLATED BACKUP at Documents\liquiditybot_isolated_2026-08-11, copy-not-move while runners were live: full tree incl. .git (all branches + stash) and 3.8 GB outputs/ - robocopy 2593/2593 files, 0 FAILED, ended 2026-08-11 20:01:56 local; a git bundle of ALL refs re-verified at filing as "records a complete history" (20,830,320 B, incl. refs/stash and a worktree HEAD); a copy of the Claude project dir (memory + every session transcript); README.txt with restore steps. NEW OWED 77: the copy's liquiditybot_ab subdirectory carries an mtime of 2026-08-16 11:36, five days after the copy - dir mtime alone proves nothing, but an isolation copy that is not provably frozen is not a restore point; closes on a hash manifest against the robocopy inventory.

(5) DELEGATION DISCIPLINE (operator directive 2026-08-16) - governance RULE 20. Every delegated agent that may EDIT anything runs the focused-fix 5-phase protocol (SCOPE -> TRACE -> DIAGNOSE -> FIX -> VERIFY), IRON LAW "no fixes without completing scope/trace/diagnose first", escalate at 3+ cascading fixes - embedded BY PATH (C:\Users\haird\.claude\skills\focused-fix\SKILL.md) because SUBAGENTS DO NOT INHERIT THE PARENT'S SKILLS: an unstated protocol is an absent protocol, the same failure shape as the delegated-measurement contract (measured cause: under-determined specs produced 5 of 9 wrong numbers in one session; agents fill gaps silently rather than halting). OPERATOR CARVE-OUT: OPTIMIZATIONS are exempt from the phase gate but NOT from rigor - read the module first, measure rather than infer, no silent behavior changes, no cheating the code to move a number, DoD matrix still runs; named precedent = parallelizing the book fetches measured ZERO gain and was reverted, the rate limit was the wall.

Touched: NEW concepts/session-identity-is-not-stable, NEW sources/session-20260811-16-vscode-3b307393, synthesis/governance-doctrine (RULES 19 + 20), concepts/no-orphan-claims (the measured mechanism behind obligation (b) + three self-corrections), concepts/location-not-magnitude (the protocol does not travel; the optimization carve-out), concepts/false-green (the NINTH way - silence from a watcher that died with its host; design rule 12: a channel is evidence only if the sender is proven alive at read time), concepts/scoped-data-unscoped-record (the class recurred in its own type-specimen module, 24.74 h after the fix; the fixture fingerprint; date-the-checkout), concepts/default-path-fallback-writes (the mirror class's recurrence applies here too - every "closed" claim is closed PER WORKTREE), sources/test-suite-outputs-contamination (third sequel; the b459a90 suspect-range instruction amended to 2026-08-01 17:20 local for this tree), synthesis/documentation-drift-register (two 2026-08-16 rows: a RECORD that is false rather than stale, and a registration whose subject was deleted), synthesis/owed-measurements (NEW item 77; docket header 52-72 -> 52-77), entities/liquiditybot (NEW host-infrastructure section), index (211 pages), log.

## [2026-08-16] amendment | RULE 20's optimization carve-out is TEMPORARY, not standing law - the Iron Law of Repair gets a durable home

Operator: the carve-out filed hours earlier as standing rule text is "just temporary". A temporary suspension filed as standing law is EXACTLY the stale-page failure rule 18's currency clause exists to prevent - everything in this vault reads as settled. AMENDED SAME SESSION, BOTH SIDES.

NEW `concepts/iron-law-of-repair` - rule 20's substance, with the source of truth referenced BY PATH (`C:\Users\haird\.claude\skills\focused-fix\SKILL.md`, 318 lines verified by `wc -l` 2026-08-16) and deliberately NOT pasted, so the page cannot drift from the skill. THE IRON LAW verbatim at SKILL.md:36-44: "NO FIXES WITHOUT COMPLETING SCOPE -> TRACE -> DIAGNOSE FIRST" / "If you haven't finished Phase 3, you cannot propose fixes. Period." FIVE PHASES: SCOPE (feature manifest, every file, entry points) -> TRACE (inbound AND outbound deps, env vars + config) -> DIAGNOSE (code/runtime/tests/logs/config, HIGH/MED/LOW risk labels, root cause CONFIRMED not assumed) -> FIX (dependencies -> types -> logic -> tests -> integration, ONE issue at a time; "if a fix breaks something else, STOP and re-evaluate", :206) -> VERIFY (feature tests + consumer tests + full suite). ESCALATION at :211-221: 3+ fixes creating NEW issues is an ARCHITECTURE problem, "Do NOT attempt fix #4 without this discussion" - and the escalation is TO THE OPERATOR, because a session three fixes deep is the least neutral reader of whether a fourth is warranted. DELEGATION COROLLARY: subagents do not inherit the parent's loaded skills, so every fix-capable prompt carries the law BY PATH; read-only investigator agents are Phases 1-3 by construction and owe the diagnosis report, never a fix.

THE CARVE-OUT, now stamped TEMPORARY / ACTIVE 2026-08-16 in the frontmatter, in the FIRST line of its section, and in a callout at the TOP of the page - a future reader cannot reach the exemption without reading its expiry. It EXPIRES rather than accrues; the DEFAULT state is the full Iron Law; a later session may NOT cite it as settled practice and must re-confirm with the operator if it is load-bearing. WHAT IS EXEMPT IS CEREMONY, NEVER RIGOR: (a) READ THE MODULE FIRST - no guessed APIs, no assumed signatures, no invented attributes, cross-linked to `concepts/false-green`'s sixth way where ~3,400 tests went green over a fabricated object because the doubles supplied an attribute PortfolioState lacks; (b) MEASURE, DO NOT INFER - an optimization's claim IS its before/after number, precedent = parallelizing the Kraken book fetches measured ZERO gain and was reverted, the rate limit was the wall, so cut call COUNT not concurrency; (c) no silent behavior changes, no cheating the code to move a number, DoD matrix still runs. SHAPE, cross-linked to `concepts/never-widen-a-gate`: "speed is licensed, assumption is not" is the same shape as "a gate may be DISCONNECTED but never WIDENED" - both permit a STRUCTURAL relaxation while forbidding the EPISTEMIC one, and in both the danger is identical, that the relaxation is the part that gets remembered while the condition is the part that gets dropped.

Touched: NEW `concepts/iron-law-of-repair`, `synthesis/governance-doctrine` (RULE 20 amended + frontmatter), `concepts/location-not-magnitude` (carve-out callout + Related), `concepts/session-identity-is-not-stable` (Related - a suspension inherited as settled is a stale claim with the citation formatting intact), index, log.

## [2026-08-16] ingest | THE CATCH-UP OVER THE GAP (08-12..08-16) - the gate fires BELOW ITS OWN NOISE, four retractions land on canonical pages, and four of the catch-up's own claims fail re-derivation

Source: an 8-agent read-only catch-up over `8cb56a82..c4272391`, re-verified page-side at filing. NO execution-era boundary minted (no entry decisioning, sizing, stop/exit geometry, fill sim, fee booking or order-lifecycle change). ALL live reads snapshot-stamped: `cohort_eval` RUN at 2026-08-16T21:01:13Z, `era4_trips` at ~21:03Z, head `c4272391` on `main`.

(1) VERDICT STATE SUPERSEDED, re-derived by RUNNING the tool. era-4 n = 16 of 50 (NOT 14), verdict_available false, ERA4_MIN_N 50, effective n 5.249648119206663, mean uniqueness 0.32810300745041643, SE inflation 1.7458016289694764 (re-derived as 1/sqrt(u) = ...767), cohort cut max(B4_TS, CAPITAL_EPOCH_TS) = 1786403127.0 = 2026-08-10T23:05:27Z (called live), gross mean +0.6576563162731225%. PER-TRADE SD DOUBLE-DERIVED: the tool's gross_se_pct 0.6397819799488953 is a NOMINAL-n SE, so sd = gross_se_pct * sqrt(16) = 2.559127919795581%; the effective-n SE is 1.1169324227800985 - the shipped instrument's default is the OPTIMISTIC one, by exactly the 1.7458 factor CLAUDE.md warns about. The two new closes are exactly the ones the decision table's own section 2.5 pre-named (9716db79 at 2026-08-16T01:48:49.774Z, gross +0.566368 net -0.085896; 3cc0e558 at 2026-08-16T15:28:55.563Z, gross +1.006418 net +0.210444) - THE DOC IS 2 CLOSES STALE, NOT WRONG. Composition at n=16: probe 14 / conviction 2 = 87.5%, label_era exit_sim 8 / triple_barrier_h432 8, stale-binary leg 4/16, prestamp 0, exec_era 7-e7d5ca1a 15/16 (one trip carries an EMPTY era set on both legs), 9/16 straddle a mid-flight champion deploy across five deploys, homogeneity MIXED(both). LEGACY 2026-08-02 GATE re-derives at 42/50 (NOT 40/50) and READS OUT FIRST, 26 closes ahead of era-4 - two pre-registrations are accruing against the same tape and the FIRST to read out is not the one anyone is watching; which one governs is an OPERATOR call and it arrives sooner than the calendar suggests. SELF-CORRECTION recorded: my own first read said 16/16 stamped, because homogeneity.fill_eras is a DISTINCT-SET field, not a count - a field's shape is part of its meaning, the same class as the "4 started / 0 result" shape error rule 19 records.

(2) THE HEADLINE, DECISION-GRADE, and filed NOWHERE (0 vault hits for "17298877", "decision table", "UNSIGNED"). `docs/quant/2026-08-16_era4_readout_decision_table.md`, 527 lines, line 3 verbatim: "**Status: UNSIGNED. Awaiting operator signature (section 4).**" Its section 3 Row 3 at :336 already says the CONTINUE trigger "is a **trigger, not a measurement**", and that sentence had never reached a vault page. ARITHMETIC COMPUTED TWICE, reproduces to the digit: n_eff@50 = 50*u = 16.405150372520822, SE = sd/sqrt(n_eff) = 0.6318323922199418%, floor at 2*SE = 1.2636647844398836% = 1.9214668105081922x the observed gross mean, floor at 80% power two-sided 5% (multiplier z_.975 + z_.80 = 2.801585218112968) = 1.7701322903683439% = 2.6915765067072113x. THE GATE FIRES ON A QUANTITY 1.92x BELOW ITS OWN NOISE - and that is the CHARITABLE reading, because 2*SE is a 2-sigma DETECTION threshold, not a power-calibrated MDE. THE CONVENTION IS NAMED NOWHERE: a case-insensitive grep for "2*SE", "power", "MDE" and "80%" over all 527 lines returns ZERO. Its section 2.2 projects 1.3974% (at uniqueness 0.306) and 1.7292% (at saturated-book uniqueness 0.200) - BOTH are 2*SE numbers under two different uniqueness assumptions, NEITHER is a power calculation - and section 4's signature line commits the operator to them without saying which convention they are. The two conventions differ by 40.079%. This is NOT an argument to move n=50 (`concepts/never-widen-a-gate`); the finding is that a signature is being requested on a number whose meaning the document does not state. Owed 82. Also: section 5 names TEN voiders (items 1-10, :437-500) by enumeration - an earlier summarizing agent's "five" is REFUTED; item 9 (the stale binary) and item 7 (max_concurrent_positions) are carried into the vault as standing rules.

(3) FOUR RETRACTED CLAIMS WERE STILL LIVE ON CANONICAL PAGES - the vault's own currency rule was being violated by the vault. Each correction had been MADE, in a log entry, a repo doc, or one concept page, and NONE had reached the synthesis pages that actually get read. (a) THE 10 BPS KRAKEN TIER DOES NOT EXIST - true schedule Tier 1 ($0+) 40/80, Tier 2 30/60, Tier 3 22/38, Tier 5 ~15/30 the DEEPEST row; an $800 book is TIER 1, so config's 25/40 UNDERSTATES fees and the correction runs the WRONG WAY (25bps maker/maker 0.50% round trip, cost/sigma 0.82, breakeven 0.567 | Tier 1 maker/maker 0.80%, 1.31, 0.650 | Tier 1 at the observed 60.6% taker share 1.285%, 2.11, 0.784). Fixed on `synthesis/the-money-path-thesis` AND - FOUND BY THIS FILING, MISSED BY THE ORIGINAL CORRECTION PASS - on `sources/cost-to-volatility-horizon-mismatch`:53-56, which still carried the claim verbatim. (b) THE 32.8x FEE/EDGE MULTIPLE IS STALE AND STATISTICALLY VOID - 98.6% of its 415 trips predate the current simulator (218 pre-passive-fix, 177 under the live double-count; only 14 ran on today's simulator, where gross is POSITIVE +$0.82), which is a pooling across execution-era boundary #4 that `synthesis/comparability-boundaries` forbids; and it divides by a statistical zero (gross -11.89 +/- 19.4, z = -1.20, so the ratio's CI is [12.2x, +inf)). 368x inherits the same denominator. Fixed at 3 sites plus the frontmatter on the thesis, and at index.md:22. (c) "THREE INDEPENDENT REFUTATIONS" SHARED ONE DATA PATH - `git show --stat 415af0f9` (2026-08-09T21:06:48Z) shows FIVE scripts in one commit, including breakeven_test.py, geometry_search.py and random_entry_control.py, FOUR DAYS AFTER the 2026-08-05 date they are cited under, and in breakeven_test the defect INVERTED the printed verdict (median gross -0.0303% -> +0.0505%); all three must be RE-RUN post-415af0f9 before being cited again. (d) THE ANTI-PREDICTIVE FINDING IS REFUTED - wrong null: b/(a+b) is the first-passage probability for an UNBOUNDED-TIME walk, these labels are CENSORED at a vertical barrier with a/b = 1.333, so censoring removes PT-bound paths PREFERENTIALLY and the conditioning MANUFACTURES the sign; correct driftless null by exact lattice DP is 0.3758 at 48.6% censoring and 0.2351 at 86.4%; the h24 sample was 87.8% censored, so the observation is ABOVE chance; with the correct null plus effective n, h24 -7.05 -> +0.58 (SIGN FLIPS), h432 -4.21 -> -1.47, pooled -3.24 -> -0.63, p = 0.53. Fixed at `synthesis/owed-measurements` item 2, which had no callout at all. CORRECTED HEADLINE, and it is the load-bearing sentence of the whole filing: GROSS EDGE IS INDISTINGUISHABLE FROM ZERO IN BOTH DIRECTIONS - which is NOT "there is no edge". Every retraction moved the corpus from a confident negative to an honest inability to resolve.

(4) ONE NEW DEFECT, CONFIRMED AND DOUBLE-DERIVED. `scripts/defensive_cadence_report.py`:39 reads CUT7_TS = 1786411630.0 with the comment "2026-08-11T01:33:50Z (deploy less 800ms is fine at row granularity)". 1786411630.0 IS 2026-08-11T01:27:10Z; the correct value for 01:33:50Z is 1786412030.0; the error is 400.0 SECONDS = 6m40s EARLY, and the comment understates the gap 500-fold. It is not the commit instant either (e7d5ca1a is stamped 01:33:28Z = 1786412008.0). Added pre-gap by d3779c8e and UNTOUCHED by all 33 gap commits. Line 38, CAPITAL_EPOCH_TS = 1786403127.0 = 2026-08-10T23:05:27Z, is CORRECT - one line, not a pattern. Consequence: every geometry-side statistic that report cuts at CUT7_TS is cut 6m40s early, INCLUDING owed 69's anti-momentum split. Owed 78. NEW CLASS for the drift register: A COMMENT THAT EXPLAINS A DISCREPANCY IS DOING MORE WORK THAN A COMMENT THAT DESCRIBES THE CODE - "deploy less 800ms is fine at row granularity" is a VERIFICATION CLAIM, asserting that somebody checked; nobody had, and a reviewer who spotted the mismatch would have been talked out of the finding BY THE COMMENT ITSELF. Second, benign (owed 79): cohort_eval.py's capital-epoch amendment states "the 3 closes accrued between them were $5000-regime trades" where SIX re-derive; a benign reading is available and probably right (the same comment says "amended at accrual n=3"), there is NO effect on n=16, and it is registered only because it sits inside a PRE-REGISTRATION whose entire authority is that it can be checked afterwards.

(5) THE BOARD REBUILD CLOSES THE LOOP OPENED AT log.md:446-455 ("the boards are not badly designed, they are badly FED", filed as owed to a board rebuild). 192 viz panels + 23 row headers -> 21 viz + 1 row across all four `docs/grafana/*.json`. The surviving board is `docs/grafana/liquiditybot_command.json`, uid liquiditybot-trading, title "liquiditybot - trading desk", 19 top-level panels = 1 row + 18 viz, of which 17 are data panels (14 stat, 1 timeseries, 1 gauge, 1 table) plus a dynamic-text header. DEPLOYED, verified two ways, the first BY ASKING THE RUNTIME: `pc_supervisor._dash_fingerprint()` CALLED LIVE equals `outputs/.dash_import_stamp` byte-for-byte (602440f4...c6512; stamp mtime 2026-08-16T02:25:22Z), and `outputs/grafana_import.log`:106 reads "OK liquiditybot_command.json -> /d/liquiditybot-trading/... (v43)". NEAR-MISS RECORDED: a first attempt recomputed the stamp with a NAIVE concat-sha256 over the sorted JSONs and MISMATCHED - the real function hashes p.name THEN p.read_bytes() per file; calling the shipped function settled in one command what a re-implementation had gotten wrong. No in-repo UI was reintroduced: `ui/` does not exist, and a grep of the gap diff for added streamlit / flask / http.server / app.run lines returns 0. The diagnosis behind it: 27 of 192 panels rendered nothing and NONE of it was a code defect (ml.load_stats == {} and orders == {} in the live status, after fills went to zero following passive_base_prob 0.45 -> 0.048 at 8e5455e8). DURABLE OUTPUT = NEW `concepts/honest-absence-contract`: three mechanically-decidable panel states (a live value | an honest absence naming its own precondition, each string restating the ACTUAL guard with that guard's file:line | THE ONE reserved defect string), and an undeclared metric family raises KeyError AT BUILD TIME - PROVEN BY INJECTION (undeclared family raises with the declare-the-precondition message; declared control returns), so "the guard passed" and "the guard is broken" are separated observations. Registry read by RUNNING the module: 64 declared families (31 event-gated, 33 section-gated), 29 always-on metrics pinned by a test that RUNS collect() rather than asserting a list, longest precondition 40 chars.

(6) WHAT FAILED RE-DERIVATION - THE CATCH-UP'S OWN CLAIMS, corrected rather than dropped, per rule 16. (i) "config_guard.py:911-914 type-checks forced_off and nothing more; the door is un-fenced" - REFUTED, ALREADY FIXED: 7f48f6ea (2026-08-15T22:35:06Z, INSIDE THE GAP, ancestor of c4272391) added BOTH fences - a WARN on the 150 < 640 window whose text forbids moving either number, and parity semantics on forced_off at :994, as a WARN NOT A FATAL because true is a legitimate rollback mode and "a FATAL would make the pre-exclusion view unreachable, which is the one thing a rollback lever may never be"; current lines are :971-1010. THE CATCH-UP EXISTED TO COVER A GAP AND REPORTED AS BROKEN A THING THAT A COMMIT INSIDE THAT GAP HAD ALREADY FIXED - a finding is as stale as the tree it was measured on, and "still broken" needs re-derivation exactly as much as "now fixed" does. (ii) "build_trading_dashboard.py:1398 still queries the RETIRED era" - REFUTED: the file is 1,361 lines, so there is no line 1398, and a grep for triple_barrier / label_era over it returns 0. (iii) "the lattice DP converges to 0.4396 at ~0% censoring" - REFUTED, and the vault was already right: it converges to 0.4286, which is exactly what makes it self-validating, since b/(a+b) = 1.548/3.612 = 0.42857 - confirmed independently by the live tool (geometry.breakeven_hit = 0.4285674702133555). A DP converging to 0.4396 would have FAILED its own validation. (iv) "25 commits 8cb56a82..c4272391" - REFUTED: 33 all / 24 first-parent, reproducing NEITHER. This is the identical error, on the identical range, that `concepts/session-identity-is-not-stable` was created to record five days ago, now on a THIRD independent session. (v) "64 families -> 33 preconditions" and "<=60 chars" - CORRECTED: all 64 carry a precondition, 33 is the section-tier count, and NO 60-char rule exists in the code (40 is the measured maximum). (vi) "15 of 16 stamped 7-e7d5ca1a" - CONFIRMED by per-trip census.

(7) TWO GOVERNANCE ITEMS WITH NO CODE IN THEM. THE RED-TEAM PANEL IS NOT MANDATED (owed 80): `.claude/workflows/red-team-panel.js` is 261 lines with five mandated-position lenses and a measured record (first run 26 agents / 35 objections / 4 withdrawn / 16 surviving, against a commit its own author had already declared clean; five gap commits trace to it), and a case-insensitive grep for "red team" / "red-team" / "red_team" returns ZERO in CLAUDE.md, README.md, .claude/settings.json and .claude/hooks/. Its own README says the quiet part: "The workflow cannot make you answer it - that part is discipline." A mechanism whose activation depends on the good intentions of the party it is meant to check is `concepts/adoption-is-not-enforcement` in its purest form; binding it is a LAW change in CLAUDE.md, not a tooling change, and therefore the OPERATOR's. THE TWO-VAULTS DECISION WAS INVISIBLE FROM CANONICAL - now NEW `concepts/two-vaults-open-decision`; the merge-or-retire decision lived ONLY inside the retired tree's own _RETIRED_READ_THIS_FIRST.md, and canonical returned 0 hits for "vaults", "RETIRED_READ_THIS_FIRST" and "merge-or-retire", so a reader following this vault's own rule (read canonical first) was GUARANTEED to miss it. Inventory RE-DERIVED 2026-08-16 by os.walk: canonical 249 .md (211 under wiki/), retired tree 117 (116 basenames), 89 absent from canonical - the note's 244/115/88 was correct WHEN WRITTEN, which is exactly why the new page names its command instead of freezing a number.

(8) HOUSEKEEPING THAT MATTERS BECAUSE IT LOOKS LIKE AN OPEN QUEUE. `docs/quant/2026-08-15_docket_dispositions.md` carries FOUR mutually contradictory counts, all verified verbatim: :13 "Status: 12 of 16 dispositioned. OBJ-4/7/8 and OBJ-13(a) pending" (reads as an OPEN QUEUE); :169-172 "Docket CLOSED - 16 of 16 ... 14 CONCEDE, 2 split concede/refute, 0 fully dismissed, ~88%" (matches the commit message, and is the only current one); :189-191 "Reading so far: 11 conceded, 1 split concede/contest, 0 fully refuted" (an earlier draft left in place); and a token grep giving 17 CONCEDE / 1 CONTEST (a third arithmetic). DO NOT READ LINE 13 AS AN OPEN QUEUE - a stale header on a closed docket manufactures work that does not exist, the mirror of a stale page manufacturing confidence that does not exist. UNRECONCILED (owed 83): for the SAME cohort_eval read at 2026-08-15T22:06:48Z, the boardroom brief says -0.4981% and the decision table says -0.4975%, BOTH tagged [MEASURED]; it CANNOT be settled by re-running, because the cohort has moved (net mean now reads -0.030137595811143666% at 21:01:13Z). The durable fix is to the TAG - [MEASURED] must mean "emitted by the tool in THIS run", with a separate tag for "quoted from another document". A provenance tag that survives a copy is not a provenance tag.

(9) A FAILED REFUTATION, recorded because the rule says verify your own refutation hardest. The adversary opened EXPECTING the geometry epoch to be wrong: git log -1 e7d5ca1a gives 2026-08-11T01:33:28Z while CLAUDE.md:84, the decision table:42 and core/fill_ledger.py:42 all carry 01:33:50Z - a 22 s gap. fill_ledger.py:42 RESOLVES it: 01:33:50Z is the DEPLOY instant, not the commit instant. NOT A DEFECT. And it cannot move the cohort, proven on live data rather than argued - era4_trips(since=) returns n = 16 at EVERY candidate boundary: none, 1786412008.0 (commit 01:33:28Z), 1786412030.0 (deploy 01:33:50Z), and 1786411630.0 (the miscoded CUT7_TS, 01:27:10Z). CLAUDE.md's re-fencing assertion HOLDS ON LIVE DATA, and the fourth row is the useful one - it shows the section (4) defect, real as it is, does not touch the era-4 population, which is why it is owed-registered rather than urgent.

Touched: NEW `sources/session-20260816-catchup-08-12-to-08-16`, NEW `concepts/honest-absence-contract`, NEW `concepts/two-vaults-open-decision`, `synthesis/the-money-path-thesis` (four retraction callouts + a new 2026-08-16 verdict-state section + frontmatter), `synthesis/owed-measurements` (item 2 REFUTED; NEW items 78-83; docket header 52-77 -> 52-83 + frontmatter), `synthesis/comparability-boundaries` (the binary-sha rule + the max_concurrent_positions epoch note), `synthesis/documentation-drift-register` (the 2026-08-16 catch-up additions: the CUT7_TS comment that certifies its own error, the era-vocabulary row RESOLVED-and-verified-at-head, and one row REFUTED at head), `concepts/false-green` (the SIBLING CLASS filed at last - a confident verdict about a population that no longer exists; design rule 13; the generalization the 08-15 log promised this page and never delivered), `concepts/never-widen-a-gate` (a THIRD road into the forbidden move - through a config flag, not a floor - with the un-fenced half CORRECTED against head), `concepts/overfit-battery` (still SYNTHETIC at 347 rows; the floor double-derived as 64 AST-counted FEATURE_NAMES x 10 = 640; the companion hole and its fix), `sources/cost-to-volatility-horizon-mismatch` (the 10bps retraction the original pass missed), `sources/session-20260815-scans-and-corrections` (era-4 row SUPERSEDED), log.md:567-573 (the n=14 / n_eff 4.287 reading SUPERSEDED in place), index (215 pages; Concept 80 -> 83, Source 76 -> 77), log.

## [2026-08-16] correction | THE AGENTS WERE NOT DEAD, THEY WERE LATE - and the vault nearly recorded a cause it never observed

THIRD LAYER OF ONE SESSION. The catch-up ingest (log entry above) launched two
background verification agents, observed NO NOTIFICATION and 0-BYTE OUTPUT FILES,
concluded they had died with the host, said so in the filing, and re-derived
everything itself. BOTH AGENTS WERE ALIVE. They returned ~6 MINUTES AFTER the
ingest concluded they were dead - agent A (18 static repo items, 62 tool uses
against live files/git/AST) and agent B (31 tool uses, cohort_eval.py in the repo
.venv, 2026-08-16T20:43:15Z-20:48:54Z).

THE META-FINDING, AND IT IS THE IMPORTANT ONE. The recovery was RIGHT and the
stated CAUSE was WRONG. Presuming death and re-deriving independently is exactly
what concepts/false-green design rule 12 prescribes; what the rule does NOT
authorize is writing the presumption into the record as a measured cause. "No
notification" and "the work is dead" are THE SAME OBSERVATION until separated -
the identical discriminator this vault was built on ("0 findings" vs "the scan is
broken"), in a THIRD polarity: NO OUTPUT vs NO OUTPUT YET. Three things make it
worth a section rather than a footnote: (1) the action was right and only the
record was wrong; (2) the error was INVISIBLE IN THE OUTPUT - independent
re-derivation reached the same numbers the late agents did, so nothing downstream
broke and the false attribution would have been permanent; (3) a cheap
discriminator existed and was skipped - the workflow journal, which failure mode 4
already names as the completion record (a started line with no result line is
"still running"; a nonzero exit status is "dead"). Filed as failure mode 6 on
concepts/session-identity-is-not-stable, beside mode 2 which it MIRRORS: mode 2 is
treating silence as nothing-to-report when the watcher is dead; mode 6 is treating
silence as proof-of-death when the watcher is merely slow. DESIGN RULE 14 on
concepts/false-green: a presumption granted for ACTION may never be filed as a
FINDING - write "unreturned after N minutes" (the observation), never "died" (the
cause), unless a journal result line, an exit status or a PID established it.

TWO OF THE CORRECTIONS THEMSELVES FAILED RE-DERIVATION, filed as further
corrections rather than substituted, because at the third layer the error rate IS
the finding. (a) "The docket page fabricated two quotes" - REFUTED BOTH TIMES. The
":189-191" citation is a RANGE and resolves exactly (:189 "## Reading so far",
:191-192 "11 conceded ..., 1 split concede/contest, 0 fully refuted"); reading a
range citation as a single-line citation manufactured the discrepancy. And "17
CONCEDE / 1 CONTEST" was never asserted as a quoted string - the table labels that
row "token grep", and text.count() returns 17 and 1 EXACTLY. Grepping for the
literal "17 CONCEDE" tests a claim nobody made. (b) "The board page claims 22
panels" - NO REFERENT: the page says 19, and 19 re-derives; the only 22 in the
document is the 22-SECOND commit-vs-deploy gap. THE LESSON: a refuter must first
establish WHAT FORM THE CLAIM TAKES - quoted sentence, line range, or derived
count. Three of four charges failed on FORM, not on FACT. concepts/location-not-
magnitude holds again: the pointers all verified, the adjudication did not.

WHAT THE CORRECTIONS GOT RIGHT, RE-DERIVED AND APPLIED. (i) THE -0.4981/-0.4975
PAIR WAS MIS-FRAMED (owed 83 amended, narrower): both figures are
geometry_breakeven.expectancy_pct - gross, model-independent triple-barrier
arithmetic - NOT era-4 net_mean_pct as the filing implied (brief :50-52, decision
table :191-195). MECHANISM ESTABLISHED BY ASKING THE RUNTIME: geometry_breakeven()
reads outputs/signal_history.csv (cohort_eval.py:390 SIGNAL_HISTORY, passed at
:648), NOT fills.csv - a LIVE file, 8,395,113 bytes, mtime 2026-08-16T21:16:29Z,
observed to GROW BETWEEN TWO OF THIS PASS'S OWN READS 34 SECONDS APART. Three
reads: 371 rows/-0.4975% (08-15 doc) -> 435/-0.504757740585774% (agent B) ->
446/-0.5385178137651823% (this pass, 21:15:55Z). So the metric is a SNAPSHOT OF A
CORPUS THAT GROWS WHILE YOU READ IT, and two documents can carry one copied stamp
and different values with NEITHER being a transcription error - a candidate
mechanism [I], not a closure. Era-4's ACTUAL net_mean_pct is -0.030137595811143666%
[K], with NO prior published comparison point [UNKNOWN]; first-14-by-close-time
gives -0.04333925281724908%, matching neither figure under any slice. Residue
recorded honestly: why the two documents differ FROM EACH OTHER is still
unexplained. New standing rule: never quote expectancy_pct without its read stamp
and row count. (ii) CONFIG_GUARD LINE NUMBERS - the original :911-914/:925-934 are
wrong (900-940 is min_new_era_rows + the OBJ-8 corpus-floor commentary, no mention
of the flags), AND the filing's own correction :971-1010 was short at both ends.
Correct: :971-974 forced_off type, :975-978 forced_on type, :979-983 BOTH-TRUE
FATAL (missed by ALL THREE prior reads), :985-993 the asymmetry comment, :994-1011
forced_off WARN, :1012-1027 forced_on conditional FATAL. Shape-level point holds.
Three successive reads of one 57-line block produced three different ranges, none
complete - location-not-magnitude applies to RANGES too: two endpoints, both must
be read. (iii) BOARD PANELS RE-DERIVED BY JSON WALK and CONFIRMED: 19 top-level =
18 non-row + 1 row, ZERO nested; census stat 14 / timeseries 1 / gauge 1 / table 1
/ marcusolsson-dynamictext 1 / row 1; all-boards 21 viz + 1 row; uid
liquiditybot-trading; title em-dash U+2014 verified via .encode('utf-8'). ONE
PROVENANCE DOWNGRADE: "17 are data panels" is [K] -> [I] - the JSON does not label
panels data vs presentational, so 17 survives only under the (probably right)
reading that the dynamictext panel is a header. (iv) "four mutually contradictory
counts" -> THREE STATED TALLIES plus one grep artifact; a word frequency is not a
claim the document makes and cannot contradict the other three.

THE ERA-4 BLOCK IS NOW DOUBLE-SOURCED BIT-FOR-BIT (tool + independent
csv.DictReader reconstruction + import cohort_eval, all three identical): n=16/50
verdict_available false at both levels, effective_n 5.249648119206663,
mean_uniqueness 0.32810300745041643, se_inflation 1.7458016289694764, cut
1786403127.0 = 2026-08-10T23:05:27Z recomputed not copied, gross mean
+0.6576563162731225%, net mean -0.030137595811143666%, per-trade sd
2.559127919795581%, probe 14 / conviction 2 = 87.5%, label_era exit_sim 8 /
triple_barrier_h432 8, stale-binary trips 4 of 16, legacy gate 42/50 (was 40/50 at
the doc's 08-15T22:07:30Z stamp - 2 have since accrued), newest closes
2026-08-16T01:48:49.774Z and 15:28:55.563Z, floors n_eff@50 16.405150372520822 / SE
0.6318323922199418 / 2*SE 1.2636647844398836 (1.9214668105081922x the mean) /
80%-power 1.770394363000277 (2.6919750015219774x). PRECISION ADDED: the 16th trip
(d6fcc6df) carries NO exec_era stamp at all (eras=[], stale_legs=2), it is not a
DIFFERENT stamp - fill_eras is a ONE-element set. Say "15 stamped, 1 unstamped".
Owed 79 CONFIRMED AT SIX by two independent agents with identical ids/timestamps
(three of them simultaneous at 23:04:53.311Z, likely why the comment says 3). Owed
78 re-confirmed: CUT7_TS 1786411630.0 = 01:27:10Z, correct 1786412030.0, error
400.0s exactly.

AND THE INVARIANCE TEST IS WEAKER THAN IT LOOKED (self-correction to the same
filing's section 9). era4_trips(since=) returns 16 at every candidate - true, and
re-derived - but the EARLIEST cohort trip does not close until
2026-08-12T03:14:40.142Z, so the 400-second disputed window contains ZERO CLOSES.
An invariance over an empty set is arithmetic, not evidence. State the actual,
stronger fact: NO TRIP EXISTS IN THE DISPUTED INTERVAL.

TWO NEW ITEMS. OWED 82(b) - cohort_eval's gross_se_pct uses a POPULATION
(n-denominator) sd, a SECOND optimism independent of the nominal-vs-effective-n one
already on item 82. Pinned without reading further code: 0.6397819799488953 x
sqrt(16) = 2.5591279197955812 = pstdev EXACTLY, while stdev = 2.6430559504487245.
The floor is understated by 3.2795558988644613% in the FLATTERING direction, so
item 82 gets STRONGER not weaker (2*SE ratio 1.9215x -> 1.9845x; 80%-power 2.6920x
-> 2.7783x). DO NOT PATCH THE ESTIMATOR MID-ACCRUAL - the registration is a
measurement standard, and changing it between registration and readout is
never-widen-a-gate in the tightening direction. NAME IT IN THE READOUT, beside item
82's unnamed detection convention: both are one defect class, a signature line
committing an operator to numbers whose statistical definition the document never
states. STANDING BLIND SPOT (filed to synthesis/comparability-boundaries) -
outputs/fills.csv is GITIGNORED via .gitignore:9 "outputs/" (a DIRECTORY rule, so
every cohort artifact is covered) and git log returns EMPTY, so every boundary on
that page is applied to a file whose past states are UNRECOVERABLE: composition
drift can only be RE-DERIVED, never forensically diffed, and two disagreeing
readings cannot be adjudicated by history. This is why the decision table's section
5 item 10 (quarantine, never delete) is load-bearing rather than ceremonial - THE
QUARANTINE RULE IS THE VERSION HISTORY. As-of read 2026-08-16T21:15:55Z: 170,155
bytes, 1,069 data rows, mtime 15:28:57.671817Z = 2.1s after the last close,
consistent with pure append - but append-consistent mtimes are EVIDENCE OF, not
PROOF OF, an append-only history, and with no git history no stronger check exists.

RE-CONFIRMED AT HEAD, and the strongest single item is now double-sourced: the
decision table is 527 lines, :3 UNSIGNED verbatim, section 4 commits the operator at
:418-420 to a "1.3974% to 1.7292%" floor, section 5 has exactly TEN items
(:437-500) with 5.1 at :502 - and case-insensitive grep for "2*SE", "2 * SE",
"power", "MDE", "80%" returns ZERO HITS ON ALL FIVE. The convention is genuinely
unnamed. Also: red-team panel NOT mandated (zero hits in CLAUDE.md /
.claude/settings.json / .claude/hooks/ / README.md); bb7c193b verified at code
level (gate_truth_report.py:197 is now a COMMENT, :207 live dynamic
triple_barrier_era(_max_bars); main.py:3690-3705 same class); ml/features.py
len(FEATURE_NAMES)=64 at :116 by AST -> floor 640, report header "loaded rows=347 <
640", delta_auc=-0.034 DECLINING verbatim; 415af0f9 = 2026-08-09T16:06:48-05:00, 6
files +322/-23 including breakeven_test.py, geometry_search.py,
random_entry_control.py, tests/test_opening_leg_pin.py; fill_ledger.py:41-46
confirms 01:33:50Z is the DEPLOY instant (22s after the commit) - not a defect;
.dash_import_stamp is 64 bytes of sha256-shaped hex, NOT a timestamp, and
grafana_import.log's tail shows the three RETIRED boards "already gone", completing
the strip story. NO IN-REPO UI, WITH THE HITS RECORDED RATHER THAN CLAIMED AS ZERO:
ui/ does not exist and grep streamlit|flask|http.server|app.run over *.py (excl
.venv/.claude) returns EXACTLY 2 HITS, BOTH in api/rest_server.py (:7 a comment,
:50 a stdlib http.server import) - a stdlib REST server, not a UI process, recorded
explicitly so a future scan reads them as known rather than as a regression.

WHAT THIS PASS COULD NOT SEE. Owed 83's residue is unclosed (mechanism is [I], and
closing it needs an archived 2026-08-15 --json output nobody has located). No
forensic history for fills.csv - permanent. Append-only is inferred, not proven. And
one route recorded so it is not rediscovered as an anomaly: a deliberately naive
independent reconstruction (position-id grouping + close-time filter only) yields 19
trips past the cut, not 16 - NOT a contradiction, it omits the three filters
era4_trips applies (entry-opened only, fully-closed at 2% size tolerance, duplicate
fill-pattern drop); the conforming double-derive returns 16.

Touched: `concepts/session-identity-is-not-stable` (failure mode 6 + frontmatter +
wake protocol now says write "unreturned", not "dead"), `concepts/false-green` (the
ninth way's OWN INVERSE + design rule 14 + frontmatter),
`sources/session-20260816-catchup-08-12-to-08-16` (four inline callouts at C1-C4,
the invariance-is-trivial self-correction, NEW section 10 with the double-sourced
table / the SE finding / the gitignore blind spot / re-confirmations / what could
not be seen, + frontmatter), `synthesis/owed-measurements` (NEW 82(b); 83 AMENDED
and narrowed; frontmatter), `synthesis/comparability-boundaries` (NEW standing
blind spot + frontmatter), index, log.

## [2026-08-16] ingest | THE FEE WEDGE BINDS AT EVERY TIER — the loss was never entry selection, and both carried numbers dissolve on contact

A 5-agent evening pass (1 finder, 3 hostile refuters, 1 measurement; session
55a25968) on "where do the losses concentrate." Answer: nowhere in entry
selection, because there is nothing to concentrate. The pre-epoch closed book
(−$391.43, close-ts < 2026-08-10T23:05:27Z) = the fixed ADA churn incident
(−$325.70, 159 trips, 96.9% fees) + a 0.6694%/round-trip fee wedge on a
zero-gross entry book (242 trips, gross −0.0187%/trip, z_eff −0.273 —
stable under nominal/AFML/Kish; the sign-test crack at nominal n closes at
eff-n and is 13× under the wedge regardless). Verified by THREE routes
including the runtime's own PT-061 audit book: 216/216 covered trips within
$0.01, hedge book exact to 4dp. The finder's "~100 comparisons" was 9 — the
refuter ran all 87 buckets and the only exceedances are outcome tautologies
(stop_hit z=−27.4, the planted-defect proof the scan can fire); pre-trade max
+2.92 at n=3. THE DECIDER: Kraken Tier-1 confirmed 40/80 by fresh fetch; the
wedge binds at EVERY spot-ladder row (booked 5.7× the +0.1182% gross UCB,
true Tier-1 10.7×, maker-only at $1M+ = 1.02× parity). COST_BOUND decided in
feasibility terms; the era-4 gate stays sole arbiter. Provenance closed on
two carried claims: "z=−4.14 at h432" was the label-space anti-predictive
stat, RETRACTED same-day it was filed (ea259ca5, wrong null); "0.8%
time-outs" is unfindable garble (real: 209/476 = 43.9%). Same session, the
label-capacity fix landed in worktree d10c1a91 (UNPUSHED): 200→1200 with a
Little's-law config_guard FATAL, after the fix agent refuted the session's
own prior arithmetic (residence = structural 36h under multi_horizon
retention, not 14.54h; sizing basis = the exact 659-registration peak 36h
window; the 200-cap era refused ≥84% of registrations, upper bound). Owed
84–88 registered: zombie slot squatting (32/187 slots, DOT 156h stale),
restore() cap-shrink gap, DOT/SOL staleness, RP-070 weekly reconciliation,
and the fee-booking adjudication (decision-grade, cohort-resetting,
operator-owned).

Touched: `raw/quant/2026-08-16_fee_wedge_feasibility.md` (NEW, primary),
`sources/session-20260816-fee-wedge-feasibility` (NEW),
`synthesis/owed-measurements` (NEW 84–88), index (new source line +
owed-measurements entry extension + header 215→216), log.

## [2026-08-17] ingest | THE FLEET NIGHT — five fixes, a dead stack revived twice-protected, a signed readout, and the stop that never ran

Continuation of the 08-16 fee-wedge session (same session 55a25968). Seven
agents total. (1) INCIDENT: the whole stack was found DEAD 48 min — the
at-logon supervisor (pid 15160) exited code 1 at 17:37 local and Task
Scheduler's JOB OBJECT killed runner+pushers with it; forensics split the
cause honestly (death #1 that morning = operator OS shutdown [K, event 1074];
death #2 = external kill vs a read_json UnicodeDecodeError hole [I] — both
audit channels were off). Revived DETACHED 18:27. KeepAlive-10m was found
EXPIRED since 07-14 (One-Time trigger, repetition window ended;
my earlier /ENABLE had re-armed a corpse) — BOTH tasks re-registered with
indefinite repetition, first fires verified; Task Scheduler Operational log
now enabled (operator UAC). Supervisor hardened: guarded tick+refresh, exit
forensics (logged FATAL = internal, silence = external), loud in-job
fallback. (2) FIXES MERGED (union at post-e1f94dc1, battery pending): ML-085
zombie eviction (three gates: clock/age/data-impossibility, censored not
labeled, epoch floor for toy clocks), ML-086 restore truncation, FW-081
label-bars staleness alert, reconcile_weekly.py (owed 87 RESOLVED — RP-070
was EXACT, the confound was wrong), and the OFF-UNIVERSE MARK STARVATION fix:
marks are never persisted and dicts boot empty, so the rotated-out SOL trip's
stop compare had NEVER RUN, exit_attempts {} — and any single orphan position
disabled the equity-peak ratchet and catastrophe hard-stop trigger BOOK-WIDE
(marks_confirmed early-return). Operator adjudicated it broken-exit-path
BUG-FIX class; trip c031d650 flagged and accepted in the contamination rows.
(3) GOVERNANCE: the era-4 readout decision table got its §4.1 convention
rider (owed 82/82(b) CLOSED) and was SIGNED — operator per-blank Q&A recorded
2026-08-17T01:00Z: BOTH gates, NO_GROSS_EDGE→1D, COST_BOUND→2D (verbatim
intent "the most disciplined aggressive profit"), CONTINUE→3A, larger n=100
binding, 80%-power MDE convention, all contamination accepted. §5.3
exception note inscribed so the mark repair cannot read as a silent boundary.
(4) #148 CLOSED: 24h hedge-unwind watch CLEAN (0 events, scan proven
sighted). Owed docket motion this night: 84/85/86/87 CLOSED or RESOLVED,
82/82(b) CLOSED, 88 adjudicated-scheduled. Deploy-time watch: first live
poll after next restart should emit one ML-085 line (32 zombies clearing).

Touched: `synthesis/owed-measurements` (84/85 fixed, 86 closed, 87 resolved
+ wrong-confound callout, 88 adjudication), index (owed line extension,
source-line RP-070 correction), `raw/quant/2026-08-16_fee_wedge_feasibility`
(RP-070 callout), `sources/session-20260816-fee-wedge-feasibility` (RP-070
note), log. Repo side: signed decision table, 5 worktree merges, #148
closure in the churn HANDOFF doc.

## [2026-08-17] ingest | THE THREE-LINK BOARDS - built, torn apart by three lenses, rebuilt honest

Operator ordered a from-scratch board set (COMMAND / LEARNING / PROBLEMS,
glass style, layman titles, snip-first layout) plus a mandatory hostile
refinement pass. Builder shipped 50167857 (27/45/46 panels + the pinned
8-panel exec mirror, screening RETIRED with uid deletion, 3782 tests green,
mutation-verified pins) - and the refinement fleet then found the Brier
mechanism REBUILT INTO IT TWICE plus a permanent vacuous green: (1) HIGH -
LEARNING's event-gated stat tiles were range-queried over the 30d window, so
a dead producer renders healthy for up to a month before honest-absence can
fire; (2) HIGH - the "this era" panels queried era="triple_barrier", the
RETIRED era, the exact defect gc_pusher's own docstring narrates (the
builder's "every metric verified" was a NAME check; the poison was the label
VALUE); (3) HIGH - "Do the books add up?" rendered the dry-run initializer
0.0 as verified accounting (main.py runs the recompute only if not dry_run -
the check that never ran was indistinguishable from the check that passed);
plus absent-boolean coercion in the pusher (healthy-0 on missing keys),
green-tinted noValue base colors, RAW-vs-LOADED rows on the 640 gauge,
import-loop stamp hostage + no backoff, names-only alert-mirror pins that
degrade OPEN. Hindrance lens: CLEAN all five channels, measured (0.58ms/tick
fingerprint, pusher diff 0 bytes, runner revival evaluated before the dash
check, +4 test tax, all queries to grafanacloud-prom). All 12 findings
closed at 5c261d3d (instant-idiom + config-derived era + neutral absence
colors + presence-guarded bool family + backoff ladder + degrade-closed
threshold mirrors + judge disambiguator panel), 3799 tests green, two
honest deviations recorded. DEPLOYED to main; pc_supervisor auto-imports.
OWED METRICS registered by the build (exact sources named in the agent
reports): liquiditybot_dry_run (status mode), liquiditybot_ml_loaded_rows
(post-filter len(X)), liquiditybot_cohort_closes, per-asset bars-age,
ml_orphan_ratio, lineage events; follow-up: the remaining coerced bool
family (ml_use_model, ws_kraken_connected, moomoo_*, positions_open).
NOTE: the running pushers/supervisor carry pre-fix code until their next
natural restart; the spawned grafana_import child runs the NEW script.

Touched: log (this entry), index owed-line NOT extended (metrics ride in
the agent reports + this entry; formal owed numbering at next docket pass).

## [2026-08-17] update | Guided window opens: owed-metrics batch SHIPPED sidecar-only, dead-man found firing into a void

Window contract signed by the professional reviewer (SIGN-WITH-AMENDMENTS;
supervisor manual swap REJECTED - reproduced the 08-16 job-object kill; the
designed self-swap already existed, pinned). Baseline 12:24Z: era-4 n
double-derived 19 (cohort_eval, authoritative) vs 22 (independent regroup,
discipline gap), runner engine-current. DEAD-MAN DISCOVERY: rule
lb-telemetry-stale has existed since 07-14 and FIRED SIX TIMES during the
08-16 teardown - every firing swallowed by a receiver named "empty" (zero
integrations). Detection never broke; delivery was void. Routing fix blocked
by permission classifier in both contexts; operator holds the 30-second
phone path + ready script. Metrics batch 360b9cc9 DEPLOYED (main): 
ml_loaded_rows (= len(w) post-filter, prior-art verified - zero engine
change), dry_run (mode vocabulary verified DRY_RUN/LIVE_ARMED/LIVE_DISARMED),
orphan_ratio (tail-read, torn-fragment safe), cohort_closes/min_n
(subprocess --json, 30-min attempt-gated cache, means never leave the
parser - pinned), lineage_events (bounded vocab + other-clamp), guard sweep
2 (_ALWAYS_ON 17->11). Per-asset bars-age correctly deferred (engine class).
Watches 13:04Z: FW-081 0, ML-085 3 events, labels ~136/day (NOT yet a
capacity-fix read - 36h maturation lag; re-measure T+36h this evening).

## [2026-08-17] measurement | T+36h capacity read: pool 470 vs old cap 200 - mechanism CONFIRMED, throughput maturing

@19:33:19Z local files: candidate pool 470 pending of 1200 (median age
6.93h) - 270 of those would have been REFUSED under the 200 cap; labels
159/day (24h) / 174/day (12h) vs 136/day interim - direction right,
magnitude awaits the pool's 36h maturation (full read T+72h);
ml_loaded_rows 551 -> 580 toward the 640 honest-corpus floor (~2 days at
pace); era-4 n 19 (no closes today); ML-085 quiet since 06:10 (23+2+1
censored total, tail drained, no recurrence). VERDICT: capacity fix
CONFIRMED at mechanism level, throughput lift PENDING maturation.
ALSO: GitHub credential expired ~18:00Z (the 08-16 class again) - sidecar
hardening HELD (fail-fast, no prompt storm), deploy pipeline frozen until
operator re-auths, bot unaffected, zero fault-family audit hits.

## [2026-08-17] ingest | WINDOW CLOSE - the 12h guided window's ledger

Full arc d10c1a91 -> fb98e9cb, nine battery-green pushes. Late-window:
analytics-taxonomy audit scored the code funnel 62/100 and found the TWO
FREQUENCY LANES that never met - tag() bumps code_stats but never audits,
AuditTrail.log() audits but never bumped, so the exported code_count
reported ML/OM emission as zero forever - FIXED fb98e9cb (bump bridged
under the audit lock, tag-idiom double-count skipped by prefix match, 4
split-string firewall sites pass counted=True, mutation-verified);
plus "Why entries die" panel (first consumer of code_count_detail ever),
timeout-cancel share on glass (measured 68% of terminals - reads red),
registry hygiene (prefix map had WD-that-never-existed and was missing
VN/RT/DF AND RP), registry gate widened 2 files -> 96 (found exactly one
unregistered family: SD-*, allowlisted where its docstring declares it
report-only). Audit residue owed: 43/196 codes reach the durable trail
(entry vetoes live in restart-volatile counters, ~8.6 restarts/day);
events.jsonl lane durability unmeasured. CREDENTIAL: expired ~18:00Z,
healed ~21:46Z - deploy pipeline frozen ~4h, sidecar hardening held.
Handoff brief: session scratchpad handoff_20260817.md; staged for the
operator's /code-review ultra. Dead-man routing (owed 90) remains the
operator's two clicks - the pager is dead until then.

## 2026-08-19 — config solidity check (VS Code session, PC)

Operator asked for config.json verification. Ran, not recalled: strict
parse (121,299 B, utf-8, no BOM, LF-only), duplicate-key scan clean at
all levels, config_guard 0 FATAL / 4 WARN (era-row floor, burst-hours vs
36h horizon, queue-aware caution, give-back arm inside BE buffer - all
standing advisory tier; three are readout-docket tunables), phantom
top-level sweep clean (`assurance` = doc block by design), guard enforced
at main.py:56, load path explicit utf-8. Filed:
sources/session-20260819-config-solidity. Repo HEAD d25489aa; era-4
accrual 21/50 per pc_status.

## 2026-08-19 (later) — deploy-box security sweep + Hermes adjudication

Machine audit (perimeter: repo, env, git creds, ~/.claude, ~/.liquiditybot,
listeners, Defender — NOT full-disk): 0 real secret leaks (6 scanner HIGHs
= resolver-code false positives, names-only logging by design); git creds
via GCM, no plaintext; token files ACL user/SYSTEM/Admins; listeners =
tailscaled + VS Code + svchost only, ZERO bot/python ports (no-listener
law holds); Defender RT on, sigs current. Windows test truth: the 4
Linux-fenced tests PASS on the PC (28 passed/1 skipped, run 2026-08-19).
Fixed: stale 35MB worktree removed (branch safe on origin). Hermes plugin
(cloned, quarantined): adoption ledger filed in repo
(docs/research/2026-08-19_hermes_gap.md) - 4/5 capabilities already ahead
here, skills-hub REJECT on the deploy box. Engine "lighter/reactive"
edits REFUSED: moratorium @ accrual 21/50 + measured I/O-wall truth
(perf-latency-work, 2026-07-12).

## 2026-08-19 (sweep) - owed-78 CLOSED + era4 telemetry n-fix + diode M2

CUT7_TS corrected 1786411630.0 -> 1786412030.0 in
defensive_cadence_report (400s early, third re-derivation agrees; item
69 re-measure still owed and now unblocked on a correct cut). pc_status
era4 now publishes signed_continue_n=100 beside target 50 (signed table
1D/3A bound - the 50-only reading understated the wait 2x). Diode M2
quote-truncation flag shipped, injection-verified. The 4 Linux-fenced
tests confirmed PASSING on the PC. Windows full battery = the deploy
gate as always. Commit: see repo log 2026-08-19.

## 2026-08-19 (late) - era-4 signature contested, reviewed, RE-RATIFIED

Operator: "no i didnt" [sign the decision table] - two days after the
recorded 08-17T01:00Z signing. Adversarial provenance review ran against
the primary artifact (transcript 55a25968, 3.4MB): the per-blank Q&A is
REAL (scope Both gates, 1D/2D/3A, n=100, accept-all contamination,
80pc-MDE; COST_BOUND answer was operator free text verbatim, agent-mapped
to 2D). Finding promoted CRITICAL: 6/7 blanks were one-click recommended
defaults authored by the asking agent - a signature the signer could not
remember at the moment pre-commitment exists for. Operator shown the
evidence, offered amend/void (lawful at 21/50), chose RE-AFFIRM AS
RECORDED. Doc carries the re-ratification block; telemetry
signed_continue_n=100 stands. STANDING RULE minted: signature-grade
adjudications take TYPED answers, never default clicks - measurement law
now authenticated no weaker than ARM LIVE. (Also settles the mirror-piece
verification: commit rate was ~8/day not 14-18; first readout ~9-10 days
out at 2.8-3.3 closes/day, not a month.)

## 2026-08-20 - ground-truth metrics battery + step-away verification

Metrics catalog triaged w/ live-verified citations (PR-AUC headline at
0.21 prevalence per Saito&Rehmsmeier; MAE improper per Gneiting&Raftery;
RMSE=sqrt(Brier) rejected; B-A referee-lattice-only). New
scripts/ground_truth_metrics.py (numpy-only, analytic test pins, reuses
overfit_check loader + train_test_gap OOF - no new convention). FIRST
FOLD-ROBUST POSITIVE DISCRIMINATION on the era-fenced corpus (1,107 rows,
read 2026-08-20 ~02:00Z): PR-AUC lift over null POSITIVE at n_splits
3/5/8, range [+0.021, +0.039]; ROC-AUC ~0.52 (why PR headlines). Thin -
NOT retune evidence (moratorium; sensitivity sweep, no argmax). Deployed
bar 0.625 operating point: precision 0.260 vs base 0.240.
STEP-AWAY VERIFICATION: retrain loop firing (3 auto in 5h, challengers
honestly rejected 0.183-0.192 vs champion 0.169), labels flowing, keepalive
armed (10m), checkin 4h armed, LiquidityBot task = logon trigger (blank
NextRun CORRECT, not the 08-16 corpse), disk 71.8GB free, Grafana
dead-man receiver now grafana-default-email -> operator inbox (void-
receiver incident CLOSED; email DELIVERY itself unverified end-to-end).

## 2026-08-20 - full-codebase sweep (25 agents) + symmetry audit filed

TWO adversarial workflows landed. (1) Learning-symmetry: AHEAD 16/28
ladder mechanisms (whole AFML stack + honesty machinery no tier carries);
only 2 reachable gaps that matter (MDA feature-importance audit, Bayesian
sizing); 3 paths killed by refuters w/ receipts (h864 no shadow pairs,
FOMC 8-event calendar, capital=honesty-not-edge); survivor = 2D conviction
kill-test (cheapest decisive measurement). Filed
docs/quant/2026-08-20_learning_symmetry_{synthesis.md,result.json}. (2)
Codebase sweep: 22 raw -> 13 confirmed. 5 SAFE_NOW FIXED (445f6c89):
registry verify_chain unchained-after-chain tamper (runtime-injection-
verified, the ML-011 gate trusted a forged row), test stub filled,
session_import symlink guards, _http DL-7 header-absent-bypass closed,
diode README drift. 5 BOUNDARY docketed for readout adjudication -
sharpest: inventory.py derisk can force-close a HEDGE with zero
coordination -> cf454d5 ADA churn (-$318) via unguarded path; leverage.py
margin veto FAILS OPEN on TradeBalance failure (0.0 = both failed and
healthy), disables 150/200pc block a full hour, inert only via dry_run.
docs/quant/2026-08-20_codebase_sweep_docket.md. Board pin regenerated
(stale since era-fence edit). Full DoD matrix GREEN on PC (4 cmd.exe
tests pass here). Learning-panel daily task armed 05:30.

## [2026-08-21] ingest | THE SHAPE IS NOT THE INTENT — the manip gate audited from both ends, and the live-readiness verdict comes back NOT READY

Pages: sources/session-20260821-manip-gate-and-live-readiness (new) ·
concepts/observational-equivalence (new) · synthesis/live-readiness-verdict
(new) · comparisons/thales-engine-vs-manip-suspect (CORRECTED) ·
entities/thales-engine (updated) · synthesis/owed-measurements (94-96) ·
index. Raw: raw/quant/2026-08-21_manip_gate_and_live_readiness.md.
HEAD dae58cf6; deployed head dae58cf6 (auto_update `current` — the
HANDOFF "BLOCKED" entry is stale). Corpus snapshot md5
a6b83a65e0a037bdc4ad740ae49f1a77, 14,170 rows, .. 2026-08-21T22:42:22Z;
live state read 2026-08-21T23:53:07Z.

LIVE-READINESS: **NOT READY, remain in DRY_RUN**, five blockers each
sufficient alone. (1) The gate has not read out — 33/50, double-derived
by pc_status.era4 AND cohort_eval. (2) It cannot resolve what it will be
asked: effective n 9.9 of 33, resolvable floor ~1.7033% vs observed gross
+1.1820% — owed-82's shape at a NEW n and the OPPOSITE sign, which makes
it a property of the design, not the sample. (3) The cohort is 85% probe
admissions (28/33, p_win forced to 0.7 vs a ~0.567 bar → clears by
construction) and MIXED(both) on fill/model/label axes (18/33 straddle a
deploy). (4) SWEEP-0/SWEEP-1 are inert ONLY because dry_run is true —
margin veto FAILS OPEN, derisk force-closes a HEDGE uncoordinated;
flipping the flag arms both the same day. (5) The manip gate is not
evidence.

AUDIT A (SZ-045 efficacy): UNRESOLVED IN BOTH DIRECTIONS. Disposition
instrument +11.71pp z=+2.41 p=0.016; feature instrument +2.80pp z=+0.61
p=0.542; Jaccard 0.462; 25.6% of stamped rows record a sub-threshold
feature. Stamp fixed → score explains nothing (z +0.46 / −0.11). PLACEBO
KILLS IT: SZ-021 +33.51pp beats SZ-045 +15.48pp. Within-asset h432 MINA
dWR −0.7pp (n=87 vs 114); FLOW +34.3pp on a control arm of n_eff 3.0.
Dose-response monotone in triple_barrier, FLAT in h432. Route-B stdlib
double-derive agrees with the pandas route on every load-bearing figure.
DO NOT RETUNE — and retuning is cohort-resetting regardless.

AUDIT B (paired injection into the SHIPPED LiquidityRegimeEngine):
honest maker repricing in a +15bps/30s melt-up scores spoof 0.949 / 79
events / label spoofy — IDENTICAL to true layering at matched 30s
cadence. veto_at is 0.90. Directional (melt-up trips the offer 0.949 /
bid 0.003; crash mirrors). Trip conditions enumerated: any trend
≥1bps/30s, size ≥8× median (exactly spoof_size_mult), +25bps distance
but not +2..+10 or +100 (level leaves track_levels=15 — blind spot, not
immunity). EVASION: repost ≥120s → 0.000. New concept filed; the
capability is established, the production RATE is owed (96).

AUDIT C (adversarial pass on eeff0f7a → dae58cf6, 7 agents, zero
criticals surviving): W1 the poison-boundary hardening deleted that
boundary's only venue-identifying alarm and booked false
retries_recovered/latency for discarded payloads; W2 a BOM regression
would drop a venue from the composite feed permanently; W3 an
unregistered code minted into a HASH-CHAINED record that verify_chain
still calls ok=True; W4 the "constant-time comparison" pin was satisfied
by the string appearing in a COMMENT — mutation-verified that
`return str(a)==str(b)` passes the entire pin with the suite green.
Process defect recorded: an auth primitive (_token_ok) reached a live
bot inside a commit titled "NaN/Infinity JSON rejection at the HTTP
boundary" because the diff was read filtered to the four expected files.
Matrix 3881/0, smoke 219/0, assurance 49/0, all SAFE class.

CORRECTED: comparisons/thales-engine-vs-manip-suspect said "the veto has
never fired in anger" — 454 SZ-045 rows say otherwise; callout filed on
the page and the correction noted on entities/thales-engine, which also
now carries the caution that TH-017 spoof_flicker is described in the
same words as the failing detector and should read as UNFALSIFIED, not
validated, until run against its own benign twin.

## [2026-08-21] ingest | THE METHOD GETS A PAGE, AND RULE 21 MAKES "SETTLED" SOMETHING A PAGE HAS TO EARN

**Operator directive, two governance-level asks in one session.** Both landed.

**(1) THE METHOD is now first-class wiki truth** — `concepts/the-method`. The investigation
protocol every finding in this vault rests on existed only as scattered practice: clauses in the
operator's `USAGE.md`, invariants in the repo's `CLAUDE.md`, a dozen concept pages each holding one
piece, and the rest in one person's head. **That is an orphan claim about the corpus itself — the
reason to believe these findings had no page.** Nine stages, and *the order is load-bearing*, because
most of the failures behind them were failures of SEQUENCE rather than of rigor (the 1.12M-token
fan-out was rigorous; it was rigorous in the wrong order): **0** recall before derive, carrying its
own trap — recall must never become reuse of a cached conclusion as evidence · **1** no orphan claims
(consult → reference back → *"no citation available" is a TASK, not a disposition*) · **2**
pre-register before looking (the readout names which decision became decidable; it never decides —
and the floors are measurement standards, not tunables) · **3** classify **SAFE vs BOUNDARY** before
the fix is written, because the class decides *who may authorize it*, and a correct diagnosis of a
real defect does not license the change · **4** diagnose before fix (SCOPE→TRACE→DIAGNOSE→FIX→VERIFY,
escalate at 3+) · **5** **ASK THE RUNNING SYSTEM** — MUTATION > INJECTION > ASK THE RUNTIME >
EXHAUSTIVE ENUMERATION > CONTROLLED EXPERIMENT > SWEPT REPLAY, with the discriminator that gives the
stage teeth: ***"0 findings" and "the scan is broken" are THE SAME OBSERVATION until separated*** ·
**6** the delegated-measurement contract (a) exact boundaries (b) named needles (c) snapshot stamps
(d) full-range scans for onset claims (e) double-derivation (f) provenance tags (g) re-derive don't
recall — with **ship the POINTER, never the NUMBER** · **7** effective n over nominal n · **8**
adversarial refutation **defaulting to REFUTED**, where a disposition gets the same pass as the
finding it closes and *you verify your own refutation hardest of all* · **9** file it, with a declared
status. It closes on what it does NOT do: it is superb at preventing bad changes and poor at forcing
the right question, and **it cannot make a claim true — only findable, dated, and attributable to a
named step.**

**(2) RULE 21 — a claim page declares its status, or it is read as SETTLED** —
`concepts/claim-status-discipline`, `synthesis/governance-doctrine` §RULE 21, schema domain rule 12 in
`CLAUDE.md` / `AGENTS.md` / `.cursorrules`. **A wiki has no neutral register: filing something IS the
claim that it is settled.** An in-flight finding written without a marker does not read as
"preliminary" — it reads as **true**. It is not incomplete; it is **misinformation, believed because
it is written down.** Three states: **SETTLED** (measured, the measurement ran, *and its refuters ran
and failed* — never stamped in bulk), **PROVISIONAL** (actionable as a LEAD, never citable as
evidence, nothing downstream may depend on it; must carry a visible callout, a `## What would settle
this` section, and its **PENDING REFUTERS** named at default disposition REFUTED, plus an owed entry),
**SUPERSEDED** (overturned, never deleted, must route forward by wikilink). PROVISIONAL and SUPERSEDED
must be visible **in the body** — Obsidian does not render frontmatter, and *a marker the reader
cannot see is adopted, not enforced*.

**ENFORCED, NOT ADOPTED.** `~/.claude/skills/llm-wiki/scripts/lint_claim_status.py` (new) fails the
vault on an invalid status value, a PROVISIONAL page missing its callout / settle-condition /
refuters, or a SUPERSEDED page with no supersedor. **Mutation-verified: 6/6 checks fired on their
planted defect, clean control, clean restore** — per stage 5, it was not shipped on the strength of
reading correct. Its own limit ships on its face: **a page that is wrong-but-declared-SETTLED passes
it and always will**, and the in-flight-language scan is an ADVISORY heuristic (16 raised across 209
baseline pages, most of them innocent "mid-flight deploy" uses).

**THE TYPE SPECIMEN IS THIS SESSION'S OWN EARLIER FILING.** `synthesis/live-readiness-verdict` was
filed hours earlier the same day as a final-reading five-blocker VERDICT — the vault's single answer
to "can this go live yet" — while a cost-stack investigation reframing its central economics was still
running. **Nothing on that page was false.** It simply could not say *"an open investigation may move
this"* — and it was produced by a session following every other rule correctly. That page is now
**PROVISIONAL**: its NOT-READY **direction** and all five blockers stand untouched; its **framing** is
what moved.

**The in-flight investigation is filed PROVISIONAL, with its refuters pending** —
`sources/session-20260821-cost-stack-in-flight`. Reported over **434 closed positions**: mean **gross
+0.0733% (POSITIVE)** against a configured 25/40bps stack costing **0.717%**, net **−0.6440%** — fees
≈**10x** the gross edge. Arithmetically coherent ([K]: `+0.0733 − 0.7173 = −0.6440` exactly) but
**single-route, no effective n, no snapshot stamp, no stated population cut** (434 ≫ era-4's 33, so
certainly pooled) and **no refuter run**. Five refuters named, R1 pooling artifact first and **R3
carrying an exact historical mechanism**: `breakeven_test.py` once flipped its own median gross
−0.0303% → **+0.0505%** by discarding 159 hedge round trips — *the same sign as this reframe*.

**THREE THINGS WERE VERIFIED THIS SESSION AND ARE NOT PROVISIONAL** (owed 98):
`scripts/cost_attribution.py:76-77` still hard-codes `KRAKEN_MAKER_BPS = 16.0` / `KRAKEN_TAKER_BPS =
26.0` — **the schedule this corpus STRUCK on 2026-08-07** (true Tier-1 is **40/80**) — and builds two
counterfactual comparison rows from it at `:201-204` (0.52% / 0.32% round trip, both below the true
1.20%), so those figures are computed against **a fee schedule that does not exist**, in the
**flattering** direction. **Third recorded recurrence** of that propagation. Worse, `:74-75` asserts
*"lower tiers only reduce these, so using base is the conservative check"* — a safety property that is
**INVERTED** at 40/80, a false claim shipped inside a running instrument and believed because it runs.
And the direction matters: at the true schedule the wedge is **≈16x, not ≈10x** — **the pending fee
correction makes the finding WORSE, not softer.**

**Two residuals registered rather than explained** (owed 99): the **0.7173%** implied fee cost exceeds
even a 60%-taker two-leg model of the configured stack (0.68%) by **≈3.7bps**; and a **60% taker share
sits ABOVE the 50% structural ceiling** of a limit-only-entry bot (repo invariant 5) against **41.87%**
measured by the same tool on 2026-08-02 — a **+18pp execution-mix drift** if real, with fill-axis
consequences.

**Retroactive scope, and its deliberate limit.** Rule 21 applied to all six pages of the earlier
2026-08-21 filing plus this filing's three new pages: **7 SETTLED, 2 PROVISIONAL, 203 UNDECLARED** of
212 claim pages, **0 lint errors** — double-derived (linter JSON vs `grep -rl '^status: ' wiki/`,
both giving 9 declared). `lint_wiki.py` also re-run: **0 broken wikilinks, 0 orphans**, the vault's
standing clean-graph property preserved (one placeholder `[[...]]` in a draft broke it; caught and fixed). The 203 were **deliberately not bulk-stamped** (owed **100**) —
bulk-stamping SETTLED without re-establishing that refuters ran would be a 203-page orphan claim filed
in the name of the rule against orphan claims.

**The filing's own adversarial pass, recorded per rule 16.** Three limits of the new enforcement, filed
on `concepts/claim-status-discipline` rather than left implicit: **checks 3 and 4 are satisfiable
without doing the work** (they match a heading and a phrase, so they enforce that the author was ASKED,
not that the author answered); **the enforcer itself is unenforced** — `lint_claim_status.py` lives in
`~/.claude/skills/llm-wiki/scripts/`, outside both trees, unversioned, in a directory that has been
bulk-reinstalled before, and **nothing runs it automatically**, so it can be overwritten and the rule
will revert to hoped-for SILENTLY while every schema file still cites it by path — *adoption-is-not-
enforcement recurring one level up, on the enforcer*; and its attack surface is genuinely minimal
(read-only, no network, no eval, echoes no page content, `errors="replace"` on read). **UNDECLARED is an honest third reading:** *no session
has asserted a status here.* Each page declares at the moment it is next touched.

Pages: **+3** (`concepts/the-method`, `concepts/claim-status-discipline`,
`sources/session-20260821-cost-stack-in-flight`) · **amended** `synthesis/live-readiness-verdict`
(PROVISIONAL + reframe callout + settle-condition + pending refuters),
`synthesis/governance-doctrine` (RULE 21 + the-method companion note),
`synthesis/owed-measurements` (items **97-100**),
`sources/session-20260821-manip-gate-and-live-readiness`,
`comparisons/thales-engine-vs-manip-suspect`, `concepts/observational-equivalence`,
`entities/thales-engine` (statuses), `index.md`, and the schema files
`CLAUDE.md` / `AGENTS.md` / `.cursorrules` (domain rule 12).
Tooling: **+1** `~/.claude/skills/llm-wiki/scripts/lint_claim_status.py` (mutation-verified 6/6).

## [2026-08-26] ingest | The why-losing deep dive at readout — era-4 COST_BOUND at n=54, tuition not alpha decay

**The era-4 gate crossed its pre-registered n=50 and read COST_BOUND** — the readout the model
freeze has waited on since 2026-08-10. Source: `docs/quant/2026-08-26_why_losing_deep_dive.md`
(commits `e4577515` / `cb0a2461` / `5d5c4e40`), snapshotted to
`raw/quant/2026-08-26_why_losing_deep_dive.md`, filed as
`sources/session-20260826-why-losing-deep-dive` (**SETTLED** — its refuters ran the same day and
drew blood: bootstrap B=20k, ×1.58 concurrency deflation; claim 5 ticket-size fee-floor
**REFUTED**, claim 3 alt-tail demoted to **POST-HOC**, the exits paragraph amended twice).

**The answer to "why is it still losing money":** gross **+$8.23** on the 54-close cohort, net
**+$1.36 booked / −$5.36 at the true ×1.979 fee anchor**. Conviction n=5 nets **+1.463%/trip at
TRUE fees** (directional only — owed 102); probe n=49 (91% of the cohort) nets **−1.052%** —
probe gross (+0.283%/trip) sits structurally below the round trip it pays. **Tuition, not alpha
decay**; the market is allowed to be boring, the apparatus was mispriced. The verdict machinery
is vindicated: COST_BOUND is the instrument doing its job, and the old postmortem gate
independently printed STAND DOWN (−1.007% vs −1.0%).

**Double-derived by this filing** (second route, `cohort_eval.py --json` read
2026-08-26T23:55:14Z): n=54, readout COST_BOUND, probe 49/5, effective n 21.52 (uniqueness
0.3986, SE ×1.584), homogeneity MIXED(both) — all of the dive's cohort facts reproduce.

**What it settled:** owed **97 CLOSED by route substitution** (the cost-stack question answered
on the decision-grade cohort; the 434-pool figures are moot as evidence);
`sources/session-20260821-cost-stack-in-flight` narrowed (PROVISIONAL only for the 434 figures;
B1/B2 + mix residuals stand as owed 98/99); `synthesis/live-readiness-verdict` blocker (1)
factually resolved, **verdict UNCHANGED: NOT READY** (blockers 3/4/5 untouched — the cohort is
91% probes and MIXED(both), exactly what blocker 3 predicted the readout would describe);
`synthesis/the-money-path-thesis` gets its firing-instrument callout (the 08-16 "indistinguishable
from zero in both directions" headline moves on the era-4 cohort).

**What it opened:** owed **101** (pre-register the majors/alts split BEFORE the next era — the
+1.69% CI[+0.20,+3.36] d=0.70 grouping was chosen after seeing the data, deflated p≈0.08, do not
act), **102** (conviction power: ~16 trades for 80%, have 5), **103** (the 08-22..08-25 repo
docket — POWER-1/2, FEE-1/2/3, CONC-1, TRIALS-1, the boundary-#5 staging memo, four 08-22
turbulence/walkforward docs — is UNFILED in this vault; the 08-26 page cites them by repo path).

**Boundary #5 (fee truth) is STAGED and INERT** (`ca55e2ba`, `scripts/boundary5_stage.py
--apply`; p_win 0.85, derived bar 0.8335); its adjudicated batching condition — AT READOUT — is
now met. Recorded on `synthesis/comparability-boundaries` as staged-not-minted. **Nothing was
applied; every remedy is cohort-resetting and the operator owns the cut.** All sim-side; fee
truth conditional on FEE-3 (the venue tier row has never been verified — OM-080 n_records=0).

Pages: **+1** (`sources/session-20260826-why-losing-deep-dive`) · **amended**
`sources/session-20260821-cost-stack-in-flight`, `synthesis/live-readiness-verdict`,
`synthesis/the-money-path-thesis`, `synthesis/owed-measurements` (97 closed; 101-103),
`synthesis/comparability-boundaries` (boundary-#5 staged note), `index.md` (header note + entry
+ 5 entry UPD tags). Raw: **+1** snapshot.

## [2026-08-27] ingest | SDD 3-day verification, the era-confound instrument defect, the confounded-everything consequence

Session `cdb03d59` (liquiditybot_ab, branch `claude/claude-rc-f3heik`); filed 2026-08-27T23:09Z.
**All session commits (`a94b5751`, `62ab10c0`) LOCAL AND UNPUSHED at filing — push = operator.**

**SDD verification (T1-T4):** T1 `8a9cc087` code clean, **commit message overclaims** (13 pins
claimed, 12 re-derived; names `test_migrate_history.py` which has zero diff). T2 `ca55e2ba`
boundary-#5 stager VERIFIED_CLEAN + inert (minors: #5/#6 numbering drift — reconciled to #5;
no persisted stager regression test). T3 `5e785c16` **DEFECT: the era confound** — SZ-021's
"ANTI-SELECTIVE at significance" was graded against the frozen 2026-07-20 baseline
(84.1% legacy / 0% triple_barrier*) with **zero label-era overlap**; a contemporaneous
same-window comparator (n=1,772, 0.440 [0.369, 0.514]) overlaps SZ-021's interval — direction
UNRESOLVED, not refuted. T4 branch `hds2hd` clean in itself; its fresh worktrees exposed two
pre-existing main defects (#9 VETO_SCRIPT unbound in fixture; #10 `_VAULT_GUARD_STAMP` = 10th
leak-class instance, real production-outputs write).

**The fix chain and its consequence:** `a94b5751` (CONFOUNDED_BASELINE refusal, 5% floor;
injection- and mutation-verified) → 12-finding code review → fix-wave `62ab10c0` (WEIGHTED
histogram-intersection overlap + 50% majority line + headline guard + fallback rows → UNKNOWN
+ gc_pusher/dashboard/doc corrections). **Under the hardened guard EVERY by_code row and the
admitted-vs-baseline headline read CONFOUNDED_BASELINE or PARTIAL_OVERLAP** — SZ-030's
"selective, earns its keep" included (membership 0.685 was the artifact; weighted 0.1587; the
baseline's own composition caps everything near 0.159). The frozen baseline cannot vouch for
ANY of today's corpus. Structural remedy = live baseline (**owed 104**); the control-arm
sandbox (`sandbox_control_arm`, branch `sandbox/control-arm-shadow-weights`) prototypes the
root cure (era-matched stratification tag + never-applied shadow weight learner), NOT merged
without operator adjudication.

**Host-state discovery:** same suite, same day — 4060/0/9 live repo vs 2f/4085p/9s/1e fresh
worktree (same 3 reds on bare main): live-repo greens OVERSTATE; filed as
`concepts/host-state-dependent-green`; remedy = fresh-worktree suite leg (**owed 105**).

**Research folders:** five written and reviewed, **UNCOMMITTED at filing** —
`docs/research/{behavioral, llm_economics, llm_linting, llm_test_suites, token_efficiency}`
(35 files; behavioral = docket material, its 9 feature candidates pre-registered only and
FORBIDDEN until boundary adjudication). Queued at filing: T5 synthesis, post-fix-wave fixer
(#9/#10/minors), research-folder commit, final whole-branch review, HANDOFF update.

Pages: **+2** (`sources/session-20260827-sdd-verification-and-era-confound`,
`concepts/host-state-dependent-green`) · **amended** `synthesis/open-contradictions-register`
(second same-day addition, SZ-030 clause superseded), `synthesis/owed-measurements` (104-105),
`concepts/label-era`, `concepts/false-green`, `concepts/who-loses-to-us`,
`concepts/behavioral-isomorphism`, `entities/thales-engine`, `index.md` (header note, 2 entries,
2 UPD tags). Raw: **+14** files at `raw/audits/2026-08-27_sdd_verification/`.

## [2026-08-27] create | synthesis/progression-bar
Operator-directed: infinite poor→Prestige maturity bar; era = prestige cycle, code-as-measured = 0% basis, mapped-set-verified = 100%, operator adjudication = prestige gate. Index bumped Synthesis 14→15. Links verified by basename (comparability-boundaries, owed-measurements, session-20260827 source page).

## [2026-08-28] update | RE-STAMP — session cdb03d59's landing (the 23:09Z filing's queue executed and pushed)

The 08-27 filing predated the session's landing; this pass brings every page it touched to
currency. Verified before writing (rule 4): commit ancestry by `git merge-base --is-ancestor`,
the T5 doc on disk, the overfit report's corpus line, `0084c16d`'s diff, the behavioral README
grade table.

**What landed post-filing:** (1) the full chain **PUSHED to origin/main** — `a94b5751` ·
`62ab10c0` · `0257fd59` (defects #9/#10 + stager pins) · `cd84c2aa` (config-audit SAFE batch) ·
`f17e28b5` (five research folders, **citation-verified**: 19 defects + 19 overreach corrected,
0 hallucinated sources; **sent-ret-1 regraded "B in-sample; D at our horizon", sent-ret-2 to
C** — the operator's re-stamp brief said "sent-ret-1/2 gutted to D at our horizon"; the
committed README grade table holds sent-ret-2 at C, with D-at-our-horizon on the DERIVED
sentiment-feature row — recorded per the record, not the brief; gov-liq-1 amended,
gov-fee-1 re-refereed STANDS at C) · `52315a57` (**T5 synthesis** —
`docs/quant/2026-08-28_session_synthesis_T5.md`) · `0084c16d` (**F1**: admitted headline speaks
`selects_winners`/`adverse_selection` — the inverted veto-token leak killed; vocabulary
enumerations predating it are incomplete) · `22d789ce` (HANDOFF landing). (2) Final
whole-branch review passed; **full DoD GREEN with corpus lines read** — overfit on the REAL
live-history corpus (**8220 rows**, no synthetic substitution), OF-4 plateau inert, OF-5 DSR
deferred (26 conviction < 30). (3) **SAC/diode finding:** the C++ diode's 8 skips are PERMANENT
on this box under Smart App Control (signed-compiler route exhausted) — diode verification
moves to the owed-105 fresh-worktree CI leg or an operator SAC decision.

**Owed-item currency:** 104 still OPEN — control-arm sandbox BUILT (`11eafb97`+`f0f3c370`, 5%
stratification tag, schema 94→95, shadow learner) but base `a94b5751` ⇒ **REBASE + FULL RETEST
required before merge**, adjudication = operator. 105 — the #9/#10 fix leg CLOSED (`0257fd59`),
the standing fresh-worktree CI leg OPEN (now also the diode's only verification home); flake #8
triple-checked unreproducible under serial scope, deliberately left.

Pages amended: `sources/session-20260827-sdd-verification-and-era-confound` (top RE-STAMP
callout + 4 inline UPDs incl. the §2 Fix-3/F1 addendum with the vocabulary-currency note),
`synthesis/open-contradictions-register` (third addition to the gate-efficacy entry — F1 +
pushed-chain currency), `synthesis/owed-measurements` (104/105 UPD blocks),
`synthesis/progression-bar` (post-filing movement list + AS-OF re-stamp),
`concepts/host-state-dependent-green`, `concepts/who-loses-to-us`,
`concepts/behavioral-isomorphism`, `entities/thales-engine` (uncommitted-folder caveats
retired), `index.md` (header re-stamp note + 5 entry UPDs). Raw snapshot untouched
(dated-correct as filed). 0 pages added.

## [2026-08-28] update | concepts/the-method
Measured-recurrences register (6 CLAUDE.md incidents verbatim + 7th era-confound) moved here per operator-approved law compression; CLAUDE.md now points at this page.

## [2026-08-28] update | CUT #8 PRESTIGE FILING — the fee-truth epoch executed (boundary #5, exec_era 8-ca55e2ba)
Boundary #5 EXECUTED under operator adjudication ("both: full bundle", 2026-08-27) — **cut #8
minted at the deploy instant 2026-08-28T03:14:13Z** (config applied 02:34:42Z; stop 03:11:58Z →
STOPPED 03:12:13Z → runner PID 9108 up 03:14:13Z, RUNNING 03:14:51Z). `exec_era` =
**`8-ca55e2ba`** — naming judgment recorded in the constant: a commit cannot contain its own
hash, so the anchor is `ca55e2ba`, the package-defining commit. Commits **`4e502478`** (sandbox
merge in + stager `--apply` fee-truth 40/80 bps + era mint SAME-COMMIT — cut #7's late-bump
debt not repeated; 7 pins re-baselined / 2 structural, none widened) + **`9f0264c6`** (deploy
stamp), both verified on `origin/main`. Constants proven **in-binary** (startup log
`fees=40/80bps`, bar `0.833` derived from 0.6902→0.8335); **SZ-023 ×42/162 cycles** = the book
quieting exactly as adjudicated; **`dry_run` TRUE untouched**. Era-4 CLOSED at COST_BOUND n=54;
era-5 accrual from zero; gate machinery deliberately untouched.

Filed: (1) `synthesis/comparability-boundaries` **table row 8** (the executor's OWED row
discharged; STAGED paragraph superseded to EXECUTED; era-4/era-5 accrual note; sources 13).
(2) `synthesis/progression-bar` **PRESTIGE #1** per its own update contract — the era-4 AS-OF
block archived into the boundary record (source page §6), page reset to the era-8-ca55e2ba
baseline: new 0% = this code as measured at the boundary; new map = remaining docket incl.
QT-1/CTRL-2/GB-1/ALGO-5/asset-discipline/CONC-1 + adoption rankings + owed register.
(3) `synthesis/owed-measurements` EXTENDED TO 52-106: **104 → MERGED-LIVE** (control-arm tag
`7b19181d` schema 94→95 + shadow learner `d64ad030` in the bundle; rebase+retest clause
discharged; **first live tagged row NOT yet observed** — label queue quiet, rotation rehearsed
on a real copy with 18,657 rows preserved — owed poll, then CTRL-2 + accrued minority-arm rows,
usable n=30 in 0.85–1.6d); **106 = QT-1** (quant_trials `TIER_CFG["est_fee_bps"]` 40 vs
deployed 80; measured 200×1200 seed 7, config-independent: as-is G1–G5 byte-identical,
mirrored **FAILS G5 0.574 vs 0.606** + G1 margin 4.84% vs cap 4.91% — the #103 T6 shape;
conscious re-baseline adjudication owed; until then G1–G5 greens are NOT deployed-geometry
evidence). (4) source page `session-20260827-sdd-verification-and-era-confound` gained the
**§6 cut-#8 addendum** (the boundary record, carrying the archived progression block);
`index.md` banner + 4 entry UPDs. 0 pages added.

## [2026-08-29] ingest | The fee-tier ground truth, a DOUBLE-OVERTURN, and the stream's n_eff ceiling

Filed 2026-08-30 as a **backfill** — the 08-29 session's page landed but its log entry
never did; recorded as a backfill rather than dated forward, because a log that
silently re-dates is not a timeline.

**The fee ground truth (the-method #1 recurrence, at full scale).** Operator's Kraken
app screenshot (2026-08-29 14:58): the account is **Tier 3 = maker 0.22% / taker 0.38%
(22/38 bps)** on **$17,482** 30-day spot volume. The live config booked **40/80**
(assumed Tier-1) — a **~2x over-statement**, fired on the cut-#8 fee-truth epoch
itself. The unheeded warnings were already on record: `fee_anatomy`'s BOOKED median was
~65bps (approximately real 60, not config 120), and **OM-080 n=0** meant 40/80 was
never verified against the account. Cross-check that stings: the pre-cut **25/40 was
CLOSER to real 22/38 than cut #8's 40/80** — cut #8 moved the config AWAY from truth
while asserting it as venue-true.

**The double-overturn — both of Claude's confident claims were wrong.** (1) Original:
"gross ~ 0, so net = -rake, confidently negative." (2) `/adversarial-reviewer` overturn:
"REFUTED — WF-5 breakeven is 118bps, so at real ~60bps net is POSITIVE; COST_BOUND was
a 2bps artifact." (3) Walkforward re-run correcting (2): the 118bps tolerance was a
**stale n=33 melt-up snapshot**, reproduced at n=33 exactly and decaying monotonically
to **+41.3bps by completed n=61**. Real ~60bps EXCEEDS the true tolerance -> net point
estimate **-18.68bps/trip** (double-derived, agree). Pre-registered readout class is
**COST_BOUND at BOTH 120 and 60bps**. The fee error inflated the shortfall MAGNITUDE
(-79 -> -19bps), not its sign CLASS. Honest sign: **UNDETERMINED-leaning-NEGATIVE**
(CI spans zero, n_eff 25.83, P(net<=0) approximately 0.73). **The adversarial reviewer
that overturned the original made the SAME class of error it was invoked to catch** —
a confident claim built on a single snapshot number is a hypothesis about the
instrument.

**What survives:** correcting the fee buys an *honest* readout, not a winning strategy.
Median trip **+72.6bps DOES clear 60bps** — the shortfall is fat-tail losers, making
this an **ALGO-5 tail-control** problem, the OPPOSITE lever from the fee fix.

**Stream n_eff ceiling** (corpus 19,343 rows, snapshot 2026-08-29T20:00:30Z): data is
**genuinely clean, DQS 95/100** (0 out-of-bounds; regime one-hot sums to exactly 1.0 on
all rows, refuting the same session's earlier "0.000000 = active" mis-probe; `''` is
honest UNKNOWN and UNKNOWN rates FALL over the stream = no feed degradation) **but the
streaming verdict is RED**: every stratum's n_eff collapses 1-2 orders below nominal
(h432 8,988 -> n_eff **33**; a nominal Wilson is optimistic by **12-16x** while looking
right). No non-directional execution style produced an n_eff-supported positive slope;
the dominant recoverable structure is **market beta (direction), not execution style**.

Pages: **+1** (`sources/session-20260829-fee-tier-and-stream-audit`) · `index.md`
banner. Primary artifacts, all on `origin/main`:
`docs/quant/2026-08-29_fee_tier_correction_adjudication.md` + `scripts/fee_tier_rederive.py`
(`16ec821e`), `docs/quant/2026-08-29_stream_data_quality_audit.md` (`965cdce9`),
`docs/quant/2026-08-29_game_theory_adverse_selection.md` (`c1882728`).

## [2026-08-30] update | CUT #9 PRESTIGE FILING — the TIER-3 FEE CORRECTION (boundary #6, exec_era 9-16ec821e)

Boundary #6 EXECUTED under operator ARM scoped **"fee correction only"** — **cut #9
minted at the deploy instant 2026-08-30T15:32:36Z** (control-plane `stop` 15:30:24Z,
cid `1788103824.226997-67a8f6`; runner ack 15:30:25Z; pc_supervisor relaunch and new
worker **PID 7692** at 15:32:36Z; first RUNNING line 15:32:37Z). `exec_era` =
**`9-16ec821e`** — anchor `16ec821e` is the *fee_tier_correction adjudication commit
that DEFINES the cut* (a commit cannot name its own hash; same resolution as cut #8).
Commit **`59bdcf87`** carried the `scripts/fee_correction_stage.py --apply` config
write AND the era bump **in the same commit** — cut #7's late-bump debt still not
repeated. **NOTE the updater could never have restarted it:** a locally-born deploy
reads "local is AHEAD — runner untouched", so restart is operator-side by construction
for on-box cuts.

**Cut #8's fee premise was WRONG and is SUPERSEDED.** Cut #8 booked venue-true Kraken
**Tier-1 40/80** as "conservative", ASSUMING a zero-volume account; the operator's
Kraken app proved **Tier 3 = 22/38 bps** on $17,482 30-day volume, so cut #8
over-stated fees **~2x** (the-method #1 recurrence). **Era-5 never reached its n=50
readout** — those rows stay citable AS era-5 (accrued at the over-stated 40/80) and
pool with nothing across the correction. Applied: fees 40/80 -> **22/38** on pricing
AND booking, PT break-even `est_fee_bps` 80 -> **38**, label round-trip cost 1.2% ->
**0.6%**, `allow_sub_floor_fees` -> true (22/38 sits below the 40/80
`KRAKEN_SPOT_FLOOR` tripwire, which **STAYS** as the understated-fee guard; the account
genuinely holds the Tier-3 discount, which is what the flag is for); exploration
`p_win` LEFT at 0.85. Constants proven **in-binary** by the new process's own startup
log (`fees=22/38bps ... net of 0.60% rt cost ... p(win) bar=0.677 (derived)`);
`dry_run` **TRUE untouched**. Full DoD green (4422 pytest / 220 smoke / 51 assurance /
3 overfit on a **live 9468-row** corpus, not the synthetic fallback / ruff / bandit 0 /
pyright 0-0 / compileall); **5 suite re-baselines, each runtime-verified, none
widened** — the sub-floor tripwire re-baseline PROVES the mechanism still fires
(flag-off arm) and pins the opt-out.

**Consequence, chosen knowingly:** the derived entry bar FALLS **0.8335 -> 0.6772**
(b_net 0.1998 -> 0.4766) — **conviction RESUMES** and cut #8's probe-dominated book is
**UNWOUND** (it was an artifact of the ~2x-too-high fee); the give-back ratchet now
arms inside an **82bps** break-even buffer (2*38+6, below the pre-cut-8 86), still
docketed with ALGO-5. **The correction buys an HONEST readout, not a winning
strategy** — net stays undetermined-leaning-negative at real fees: the median trip
clears the rake, the **fat tail loses**, an **ALGO-5 problem EXCLUDED from this cut**
(its net-CI spans zero on fills alone; needs the candle re-sim).

Filed: (1) `synthesis/comparability-boundaries` **table row 9** — already on the page at
this filing, verified current, NOT re-filed. (2) `synthesis/progression-bar` **PRESTIGE
#2** per its own update contract — and with a **NEW SHAPE recorded**: the
era-`8-ca55e2ba` cycle's final block is archived **ON that page** because cut #8 never
got its own boundary doc, and **a prestige cycle can be ended by its own BASELINE being
falsified, not only by its map being completed** (cut #8 lasted **2.0 days** and
accrued nothing). (3) `synthesis/owed-measurements` **EXTENDED TO 52-111** — item
**106/QT-1 RIDER**: the harness-vs-deployed `est_fee_bps` drift NARROWED **40bps ->
2bps** (harness 40 vs deployed 38) **by accident of the correction, not by
adjudication**, and the item STAYS OPEN because the G5 0.574-vs-0.606 failure was
measured against the **80bps** mirror and has **NOT** been re-run at 38, so the gate
effect is **[UNKNOWN]**, not "small". (4) Riders on `synthesis/the-money-path-thesis`
(FEE-3 came back and falsified its anchor in the OTHER direction; COST_BOUND STANDS as
an era-4 reading; the named lever moves to ALGO-5) and `synthesis/live-readiness-verdict`
(**VERDICT UNCHANGED: NOT READY**; the "approximately 16x at true Tier-1 40/80" multiple
SUPERSEDED, nearer approximately 9x at 22/38; blocker (3) moved **SIDEWAYS, not green**;
blocker (4) GAINED a member). (5) `sources/session-20260829-fee-tier-and-stream-audit`
discharge callout + `status: SETTLED`. `index.md` banner + counts. **0 pages added by
this half of the filing.**

**Era-6 accrual begins at ZERO from 15:32:36Z**, on the same pre-registered machinery —
`scripts/cohort_eval.py` was **not touched** by the cut; the gate, its bands and its
selection rule are exactly as registered. Decision record:
`docs/quant/2026-08-29_fee_tier_correction_adjudication.md`.

## [2026-08-30] ingest | THE AUDIT WAVE — a 47-day silent pager, an era-6 count nobody computes, a tamper gate that ATTESTS forgeries, and the public-record atlas

Same day as the cut, measurement plane only (**SAFE class**, one exception docketed
BECAUSE it is cohort-resetting). Primary artifacts: `docs/HANDOFF.md` (WATCH LIST /
OPERATOR DECISIONS OWED / OWED-VERIFY / DELIVERY-1), commit **`8f27a326`**,
`docs/grafana/*.yaml`, `ml/registry.py`, `ml/meta_model.py`, `scripts/cohort_eval.py`.

**(1) THE PAGER WAS SILENT FOR 47 DAYS.** Both pre-existing Grafana rules
(`lb-telemetry-stale`, `lb-manip-high`) carried **`notification_settings: null` since
creation 2026-07-14**, and the root notification policy's receiver is `"empty"` — **zero
integrations**. **Any firing between 2026-07-14 and 2026-08-30 paged nobody.** The repo
had **already found it**: its own `liquiditybot_deadman_alert.yaml` dated it 2026-08-17
as "MANUAL-APPLY" and it was never applied — a correct diagnosis that aged into
decoration. Fixed `8f27a326` (documented read-modify-write PUT, GET-verified; drift
closed both ways — `lb-drift-stuck` + `lb-brier-degraded` PROVISIONED live, `lb-manip-high`
exported back to a new YAML). **Delivery then PROVEN end-to-end by an ORGANIC firing —
nothing artificial sent:** `lb-drift-stuck` `startsAt` **2026-08-30T23:04:30Z**, mailer
`lastNotifyAttempt` **23:05:05.164Z**, `duration` **341ms**, `error=None`, read from a
**zero-cost GET of the dispatch record** — which **corrects the lane's own method claim**
that "only a real send closes that" (true at 22:44Z when nothing had fired; false the
moment any rule did). **RESIDUAL, unclosed:** `error=None` proves the mailer ACCEPTED
the handoff — **not** inbox-vs-spam, and not that the mailbox is monitored (owed 109).
**STILL-ARMED TRAP, an OPERATOR DECISION OWED:** the root route **still** points at
receiver `empty`; the 4 current rules deliver ONLY because each carries its own per-rule
override, so **any rule created without one routes to the void exactly as the outage
did**. Contact point is `provenance: "api"` -> UI-locked.

**(2) THE INSTRUMENT LESSON -> `concepts/the-method` measured recurrence #8.** The false
"the fix is only cosmetic" suspicion came from reading `/api/v1/provisioning/policies`,
which **HIDES Grafana's autogenerated routes** (the full AM config carries a
simplified-routing autogen subtree, `__grafana_autogenerated__ = true` ->
`__grafana_receiver__ = grafana-default-email`). **The instrument's VIEW, not the config,
produced the wrong conclusion.** REFUTED by four independent routes, decisively by
Stage 5 — the runtime's own testimony, live alert instances already carrying the matcher
labels at evaluation time. **A partial view and a broken config are observationally
identical from inside the partial view.** *The recurrence is filed on the SUSPICION; the
outage underneath it was real.*

**(3) ERA-6 COUNT = 4** closed entry-opened trips (**upper bound 7** under any-leg /
close-time membership; those 3 ENTERED under cut #8 at the superseded 40/80 and only
EXITED under cut #9). Frozen snapshot md5 `f972dd36f569369a9dfb78cc06727578`, mtime
21:10:20Z, **read 22:47Z**; supersedes an 11-row fill-leg proxy (**11 legs = 7 pids = 4
wholly-era-6 trips**). Two independent routes agreed **exactly** — the gate's own
`era4_trips()` **unmodified**, segmented on its report-only `eras` field, plus a
from-predicates re-implementation — and a hand-written join agreed on the same
`position_id` set. **Agreement is NOT the evidence that matters**; the evidence is a
**10-case injection battery incl. 2 positive controls** proving the counter MOVES, so
**"4" is a measurement, not a dead scan**. Boundary clean: 0 era-9 legs before
15:32:36Z, 0 era-8 legs after. **DECAY NOTE (23:10Z, re-confirmed 23:17:45Z):** the
snapshot has already moved — md5 `ef92ef6cd3295b69dff0fcefd39b60fb`, **1,189 rows**,
**12** era-9 legs across **8** pids — while **the trip count stayed 4** (the new leg is
an unclosed ENTRY). **RE-DERIVE, NEVER CITE. COUNT ONLY** — no gross/net/win-rate on an
accruing era. **Instrument gap (owed 107):** `cohort_eval` prints **no era-scoped
counter**; its `accrual: 72/50` headline at **printed line 39 of 144** is the
pre-registered **era-4** population POOLING cuts `7-e7d5ca1a` / `8-ca55e2ba` /
`9-16ec821e` (enumerated at line 73), and **must NOT be "fixed" by filtering a
pre-registered gate**. **Correction recorded AGAINST THE FINDING'S OWN INTEREST:**
`COHORT HOMOGENEITY: MIXED(both)` prints at line **40 — ONE line below the headline**,
so the "a reader never sees the disclosure" argument is **materially WEAKER than first
written**; what survives is the narrower complaint (no era label, no proportions, and
no tool computes era-6 accrual at all). Membership rule = **OPERATOR DECISION OWED**
(owed 110): 4 under stamp-purity AND entry-time — **SET-EQUAL, not merely count-equal**
— vs 7 under any-leg AND close-time.

**(4) MLSEC-1 — NEW, DOCKETED, NOT FIXED (cohort-resetting).** An adversarial re-verify
**RE-ROOTED** a shallower first diagnosis and made the finding WORSE: `ml/registry.py`
`_record_hash` (`:64`, used `:143`/`:209`) is an **UNKEYED public sha256**, so anyone who
can write the ledger can write a **valid chain over forged content**. Measured
forged-chained-row case: append ONE well-formed `registered` row whose `sha256` is the
SWAPPED artifact and whose `prev` is the last row's `h` -> `verify_chain()` returns
`{'ok': True, 'rows': 3, 'chained': 3, 'reason': 'chain intact'}` **and** `verify()`
returns `ok=True` — the swapped artifact is **not merely un-rejected, it is POSITIVELY
ATTESTED**. Therefore **"reject on `ok is not True`" DOES NOT CLOSE THIS** (that covers
only the `ok=None` path); **a keyed MAC or an out-of-tree signer is the class of fix**.
Two weaker symptoms on top: `ml/meta_model.py:83` rejects only on `ok is False` while
`registry.py:284-287`/`:221-222` return `ok=None` for absent pedigree or unreadable
ledger — injection-confirmed with controls (ledger intact -> `ok=False`, ML-011 fires,
`p_win` falls to the prior **0.5600**; ledger deleted -> `ok=None`, the swapped artifact
**LOADS**, `p_win` = **0.9500**, the hard-clip ceiling) — and an **EMPTY ledger passes
`verify_chain()` vacuously**. **THREAT MODEL, stated so it is neither over- nor
under-fixed:** [HIGH] rests on a **PARTIAL-WRITE** attacker; **against an attacker who
already owns the repo NO gate here helps**, since ledger and artifact share a directory
and the verifier is editable. **Fifth** instance of *a gate's release condition must
never depend on the thing it blocks* — same shape as (1)'s alerting default. Live state
healthy as of **2026-08-30T22:52:02Z** (chain ok, 177 rows, artifact `1ee3ae68c0df`
verifies ok=True) — a snapshot, not a standing property.

**(5) THE PUBLIC-RECORD DATA ATLAS — new knowledge, no prior vault page, ADOPTED FOR
NOTHING.** **UK Companies House full accounts are FREE and carry a real P&L**: Jane
Street Financial `06211806` FY2025 rev **USD 71,495k** / profit **49,153k**; Citadel
Securities (Europe) `05462867` FY2024 **USD 310,766k**; HRT Europe `06796079` FY2024
**GBP 84,309,989**; XTX Markets `09415174` FY2025 **GBP 62,041k with ZERO staff**; Tower
Research Capital Europe `06005750` FY2024 PBT **MINUS 467,377** (a filed, audited LOSS at
a named HFT house). **CAVEAT THAT MUST SURVIVE:** Optiver UK `11478632` and Jump Trading
International `05976015` "revenue" is **INTERNAL RECHARGE** ("charged to group
undertakings" / "back-office support services to affiliates", transfer pricing) — so
**ranking these seven on revenue is MEANINGLESS and was REFUSED**, not footnoted. Access:
**SEC hosts require an SEC-format declared `User-Agent` ("Name email"); a generic UA
returns 403.** **TWO REFUTED CLAIMS recorded so they are not repeated:** (i) FINRA
`weeklySummary` was believed to be "the only free FIRM-ATTRIBUTED sizing lane" — a
**5,000-row pull measured `firmCRDNumber` EMPTY on every row**; the dataset carries **no
firm identity**; (ii) **SEC Rule 606 net payments are wholesaler COSTS** (money the
market-maker PAYS to acquire retail flow), **not revenue** — any join reading them as MM
revenue is **INVERTED**. **CapitolTrades / STOCK Act REJECTED** and added to
`synthesis/evidence-closed-register` on four independent kills: cadence (already closed
twice by this register's own 13F 45-day row and its minutes-not-hours equity-leads row;
this feed is **30-45+ DAYS**), identification (**RANGE-BUCKETED** amounts, bottom bucket
$1,001-$15,000 = **15x span**; blind trusts excluded; self-reported, no verification),
legal (**Ethics in Government Act** bars use "for any commercial purpose other than by
news media", civil penalty up to **$10,000**; whether systematic trading is such a
purpose is **[UNKNOWN]** and needs counsel, not an agent), and literature (Belmont,
Sacerdote, Sehgal & Van Hoek 2022, *J. Public Economics* **207:104602**, Jan 2012-Dec
2020: **no evidence of superior performance**; even 95th/99th percentile returns
consistent with random stock picking). **STATISTICS** (computed this session; script is
**session-scoped scratchpad**, `disclosure_stats.py`, registered as owed 111 with the
closed forms recorded inline): midpoint imputation on the bottom bucket **overstates the
conditional mean 175%-326%** (Pareto alpha 1.0-2.0), **202%** for lognormal sigma=1,
**43.2%** equal-weighted across all 7 buckets; **assumption-free bounds do NOT shrink
with n** — 1,000 bucket-1 disclosures bound the total in **[$1,001,000, $15,000,000]**,
ratio **15x regardless of n**; **POWER** — detecting a **26bps** 6-month abnormal return
needs **52,248-145,135 INDEPENDENT** trades at 6-month sigma 21%-35%, clustering
inflating SE a further **1.40x-2.43x**, so Belmont's null is **absence of evidence for
small effects but credibly EXCLUDES large ones**; **MULTIPLICITY** — at **535**
candidates Bonferroni demands **|z| > 3.91** and **E[max z] under pure noise is 2.93**,
so a naive t>1.96 claim about an ex-post-selected member **does not even clear the
expected maximum of noise**; **DSR analogue** N=535 over T=24 gives **E[max Sharpe | ZERO
SKILL] = 0.63** — *the same correction `scripts/overfit_check.py` applies, and the reason
TRIALS-1 is docketed*. **DISCLOSED-TRADE BEHAVIOR:** House PTR **n=611 records / 85
documents / 58 filers** (filing window 2026-07-01..08-27) vs SEC Form 4 **n=68 rows / 25
filings / 22 persons**. **HEADLINE: the cross-population correlation is NOT COMPUTABLE**
— after time-aligning both to the same MARKET period the shared-ticker intersection is
**EMPTY, n=0 pairs**; the single raw MMM overlap is an **artifact of pairing on the
FILING window instead of the TRANSACTION window** (a comparability-boundary error
committed on someone else's data). Detecting r=0.3 would need **>=85** time-aligned
shared tickers. Also: **66.2% of Form 4 rows are COMPENSATION MECHANICS** (M/A/C/F/D/L/J),
only **33.8%** open-market; natural-person purchase dollars are **$239,605.15 = 0.81%**
of a headline **$29.65M**, the rest fund subscriptions. **UNIT TRAP:** P:S = **0.353 by
rows, 5.99 by shares, 9.875 by dollars** — three units, **OPPOSITE directions**; **a
buy/sell ratio without a stated unit is not a number.**

Pages: **+2** (`sources/session-20260830-audit-wave-and-external-data-atlas`,
`synthesis/public-record-data-atlas`) · **amended** `concepts/the-method` (recurrence #8),
`synthesis/evidence-closed-register` (CapitolTrades row + revisit terms),
`synthesis/owed-measurements` (107-111), `index.md` (banner, Synthesis 15->16, Source
81->82, 2 catalog entries). **Raw: NONE** — no `raw/` snapshot was taken this session;
the atlas's external sources are public records cited by company number / endpoint /
paper, and the era-6 and MLSEC evidence lives in the repo artifacts named above. Say so
rather than imply a snapshot exists.

## [2026-08-30] ingest | THE POINT-VS-SET AUDIT — the fee tier is a 2-element set, the record said n=0 and it was n=1, and the shipped ticket is minimax-optimal at no rung

Partial-identification (Manski) audit of every point estimate feeding a decision
or verdict; two lanes plus an independent verification lane that reproduced every
load-bearing number, most to the cent; **document-only** (era-6 moratorium
respected, runner PID 7692 untouched, `dry_run` TRUE throughout; nothing under
`core/ execution/ ml/ risk/ config.json outputs/` written). Lane runs
2026-08-31T00:38-00:46Z UTC, verification 01:08-01:15Z, minimax-regret
02:23:13Z.

**(1) THE FEE TIER IS NOT POINT-IDENTIFIED, AND THE DECISION RECORD MISREAD THE
EVIDENCE AS EMPTY.** `docs/quant/2026-08-29_fee_tier_correction_adjudication.md:84-90`
asserts, tagged [K], "OM-080 has fired n=0 ... no live credentials, TradeVolume
never called." **Both clauses FALSE, and false AT AUTHORSHIP**: OM-080 fired
exactly once — `outputs/audit.jsonl` seq 69754, 2026-08-29T15:47:07.123Z, XBTUSD
**40/80 bps**, hash-chained, **4h40m58s BEFORE** the adjudication commit
`16ec821e` (20:28:05Z). Double-derived (full-range 70,409-line grep n=1;
`scripts/cost_truth_report.py` `n_records=1`, live verdict **XV-033 DANGEROUS:
configured UNDER measured** vs the shipped 22/38); no test fixture emits XBTUSD
40/80; the emit path (`execution/order_manager.py:807-829` →
`data/kraken_feed.py:406-429`) needs a signed non-error response, so credentials
existed on the box that day. The doc's surviving cross-check is CIRCULAR (booked
median 65.4bps against a then-configured 65bps round-trip measures booking==config
— HANDOFF POWER-2's own correction, unapplied). **Both sides, held:** Kraken may
return schedule-top `fee` for an untraded pair, so a Tier-3 account could
faithfully read 40/80 — the set `{40/80 [K, one venue reading], 22/38 [I,
operator screenshot]}` is UNRESOLVED, and `data/kraken_feed.py:415-428` discards
the exact fields (`minfee`/`maxfee`/`nextfee`/`nextvolume`/`tiervolume`, 30-day
`volume`) that would collapse it. Consequence: the derived entry bar
(`risk/position_sizer.py:189-195`) is a set **[0.6772, 0.8335]** (T3/T2/T1:
0.6772/0.7554/0.8335, all four digits reproduced through the real
`PositionSizer`) — reported everywhere as the point 0.6772, while era-6 accrues
at 22/38.

**(2) THE MODEL PATH IS CLOSED AT EVERY ELEMENT OF THE SET, INVISIBLY.** Deployed
champion `1ee3ae68c0df` over all 21,047 corpus rows: raw range [0.0196, 0.9832],
isotonic-calibrated **[0.3992, 0.6446]**, live post-shrink ceiling (L1) 0.5687 —
**0/21,047 rows clear the bar at any tier**. Mutation-verified: identity
calibrator → **1,956 rows clear (9.3%)** — the scan is live, the zero is real,
and **the ISOTONIC, not the raw model, closes the path** (recurrence of
`_label_max_bars_migration_doc`'s "structurally unreachable" shape). Every live
entry is a synthetic-p probe (exploration 0.85 / aggressive 0.72) — the era-6
readout is reading the probe lane. And the closing veto persists NOWHERE:
`main.py:4152-4160` logs non-exploration sizer vetoes at DEBUG, log level is
INFO, 0 DEBUG lines in `events.jsonl` (83-minute tail — no onset claim), **0**
SZ-023/SZ-030 in the full 70,409-line audit.

**(3) THE TICKET LADDER + MINIMAX REGRET.** Exploration ticket (p=0.85, equity
$795.51), real sizer, shipped point **$81.97**; identified set **$0.00–$153.14
joint** over fee-tier x calibration error, **$50.44–$113.51** at shipped tier
with the smaller (OOF) error. The two measured calibration errors disagree
2.48x (OOF 0.06647 vs live 0.1648) with the dangerous sign (avg_p 0.470 vs
hit_rate 0.375); the live window's n_eff is **2.46** (Wilson [0.066, 0.837]) —
the L1 governor state is a verdict on ~2.5 independent observations. Minimax-
regret tickets by rung: realized-data-only **$0.00**; assumption-free union
**$26.30**; live-ECE **$105.02**; OOF-ECE at shipped tier **$153.14** — the
shipped $81.97 is the MMR action at **NO rung** (worst-case regret 0.0814
log-growth/trip under the realized-data rung). Overstatement held against the
finding's own interest: the joint endpoints transport ECE onto a CONFIG CONSTANT
(0.85) and p+e=1.0 exceeds the emittable ceiling — prefer rungs 1 and 3; the
verification lane's fuller list of overstatements arrived TRUNCATED and is
recorded as such, not reconstructed.

**(4) UNCERTAINTY COMPUTED, THEN DISCARDED** (ranked by distance to a decision):
`ml/monitor.py:259/291/340` `lcb` → log string only; `:797` `hit_rate_lcb` →
Grafana only; the whole interval quantized to `kelly_mult ∈ {1.0,0.7,0.40}`
applied AFTER the veto and AFTER `f_star` (can shrink the ticket, can never move
admission); ensemble member spread averaged away at source (latent — champion is
logistic). Credit kept current: `wilson_ucb` → `hit_deficit`
(`ml/monitor.py:271-272`) IS a consumed interval, the one shipped example.

**PRIOR ART CONFIRMED, NOT REBUILT:** effective-n (`ml/corpus.py:200-259`,
`gate_truth_report`, `cohort_eval`), PBO-on-deployed + DSR deflation
(`overfit_check.py`), the CONFOUNDED_BASELINE/PARTIAL_OVERLAP refusal
(`gate_efficacy_report.py:184-243`), POWER-1's fee-world split, LS-2 —
**CONFIRMED and PRICED** ($50-114 at its own assumptions), with a scope
extension docketed (admission, not only sizing; b_net uncertainty dominates
p_win uncertainty in the joint set). SAFE fixes applied: **NONE** — all four
SAFE remedies docketed rather than shipped (each touches engine/data files the
audit boundary excluded, and none ran the DoD matrix).

Pages: **+1** (`concepts/partial-identification`) · **amended**
`sources/session-20260829-fee-tier-and-stream-audit` (§1 correction callout,
both sides — the Tier-3 ground truth NOT overturned, the COUNT and the [K] tag
overturned) · `index.md` (banner, Concept 87→88, 1 catalog entry) · repo-side:
`docs/HANDOFF.md` FEE-3 row corrected ("never fired" → n=1) + PI-1..PI-4
docketed. **Raw: NONE** — evidence lives in the repo artifacts named above
(audit.jsonl seq 69754, status.json as-of stamps, scratchpad scripts recorded by
closed form); volatile numbers are stamped as-of and must be RE-DERIVED, never
cited forward.

## [2026-08-31] update | OPERATOR TESTIMONY OVERTURNS THE "VENUE 40/80" READING
The seq-69754 OM-080 row is planted fixture data, not a venue reading:
operator states no Kraken keys have EVER been on this bot, and
`_private_post` cannot produce a signed non-error response without a valid
HMAC (re-read 2026-08-31, no stub path). The row rides a 62-second
unredirected fork (parent seq 69742, AUDIT-SEAM-0829); 38 duplicated seqs
file-wide, none flagged. Filed: the-method recurrence #9 (QA data read as
production truth); counter-correction on sources/session-20260829-fee-tier-
and-stream-audit; repo HANDOFF FEE-3 re-corrected (tier evidence =
screenshot only; a read-only key is an OPERATOR SECURITY DECISION, zero-key
manual tier checks are a legitimate alternative). Detector owed:
duplicate-seq/fork check in core/session_digest.py.

## [2026-08-31] note | Second-route verification of the 2026-08-31 vault-reachability fix (external session)

An external session (operator: a session-bridge agent, not on this machine's roster) wired TWO-VAULTS callouts into CLAUDE.md/AGENTS.md/.cursorrules and declared concepts/two-vaults-open-decision SETTLED. Verified by liquiditybot-ab-f2: all three callouts present on disk; totals 285/232/117/97 confirmed by independent Get-ChildItem route; absent-basename count NOT reproduced (claimed 84, second route gives 78-82 across five definitions) - contradiction callout added to the page per rule 10. Its cited sources/session-20260831-vault-reachability-fix page does not exist; owed by whichever session next touches it.

## [2026-09-01] session | Edge-hunter mirror — six-part operator objective measured; Kraken tape reach discovered; tape-proxy null on the book feature

Filed sources/session-20260901-edge-hunter-mirror (12 findings, each with its
artifact), concepts/false-strategy-theorem-and-minbtl CORRECTED a second time
(denominator = production-loaded 23.73 d = 0.065 yr; the 0.137-yr figure was
the raw file span; commit 1d751e22's subject carries the wrong one), and two
raw research files: 2026-09-01_deep_research_data_scarcity_historical_backfill
(#2, 106 agents, angles 4-5 UNRUN) and
2026-09-01_deep_research_measurement_consequences (#3, PARTIAL: 86/108 agents,
synthesis failed on the account session limit, angles 4-5 UNRUN, resume
pointer inside). Structural discovery: /0/public/Trades since=0 returns trade
id 1 (2013-10-06) with native aggressor side - research #2 had left this
UNVERIFIED and assumed tick-rule; one call refuted both (the-method rule 2).
Shipped scripts/kraken_trades_backfill.py; 12/14 pairs backfilled 2026-07-13
to now at the measured ~1/s sustained limit. Deciding measurement, replicated on
six pairs: the stored L2 imbalance_dir is NOT reconstructable from the tape
(Spearman ~0 at 60s, <= 0.19 at 1h) and scores AUC <= 0.50 vs label on all
six anyway. THE SESSION'S ONE POSITIVE RESULT WAS REFUTED THE SAME SESSION
and is filed as the-method recurrence #10: tape trade-count intensity scored
AUC 0.52-0.58 vs the raw label on six pairs (4/6 CI-significant), then
decomposed into RESOLUTION 0.616 (does the path touch a barrier at all vs
time out) and DIRECTION-given-resolution 0.510 with 0/7 pairs significant.
Volatility drives resolution; no direction. Second instance of the shape that
killed the T2 magnitude lead (2f8550de), so the-method now carries the rule:
no feature is a signal against a triple-barrier label until its AUC is split
into resolution and direction. I had written the lead into three documents
before running the split - the register entry is filed on that, not only on
the number. Instrument findings:
ofi_dir structurally zero for 13/15 assets (external books ETH/BTC only);
the archetype-battery flake is a live-writer race on audit.jsonl. Repo
HANDOFF EDGE-HUNTER MIRROR block items 1-9 hold the same facts with
re-derivation commands. Owed: ETH/BTC tape replication, research #3 resume,
operator report docs/quant/2026-09-01_edge_hunter_mirror_report.md.

## [2026-09-02] concept | concepts/resolution-vs-direction-decomposition (new) + CLAUDE.md reading-discipline (f)

The barrier-geometry tautology promoted from a register entry to its own
concept page: P(label=1|x) = P(resolved|x) * P(tb_pt|resolved,x); volatility
loads the first factor and it is not an edge. Two measured instances (T2
magnitude 2026-08-30, tape activity 2026-09-01) = a class. Rule: three
numbers on the same rows (raw / RESOLUTION / DIRECTION) with day-block CIs
before "signal" is used. Repo CLAUDE.md reading discipline gained clause (f)
pointing here. Enforcing instrument scripts/label_decomposition_report.py in
flight under workflow wf_21c3a8ff-c7b together with: tick-horizon markout
from the local tape, tape features vs a continuous target, the battery
live-writer race fix, and a tape cross-route for the manipulation detector
(detection only). Research #3 resumed as wf_c5fac112-377 for angles 4-5.

## [2026-09-02] session | Instrument built, all 64 features decomposed, three nulls, one self-inflicted ledger incident

Workflow wf_33d04172-ab9 (13 agents, 0 errors, 1.5M tok - an optimized re-run of
a killed 27-agent design, reusing its partial disk work). Results, all nulls:
(1) scripts/label_decomposition_report.py shipped and run - DIRECTIONAL 5 of 64
against 5.3 expected by chance; RESOLUTION is where everything loads
(sigma_bar_pct 0.750, spread_bps 0.662). No stored feature is credibly
directional. concepts/resolution-vs-direction-decomposition updated from rule to
measured result. (2) Tick-horizon markout: the apparent +3.7 bps seconds-horizon
gain is the BID/ASK BOUNCE - corr with the reflected limit distance +0.995 at 1s;
net of the mirror it is negative at every horizon. Third instance of
apparent-positive-is-artifact. (3) Tape features vs the continuous outcome:
nothing survives - the real run flags 7/72 cells, its own placebo 9/72.
(4) The tape CANNOT adjudicate SZ-045: a successful spoof leaves no print, and
98.8% of refusals are on pairs with no or negligible tape.
INCIDENT: a delegated agent wrote two MUTATION-ROW-T4 lines into the PRODUCTION
hash-chained audit trail (verify_chain tamper=true) because the prompt's own
mutation instruction told it to, contradicting the same prompt's NEVER clause.
Repaired by excision with quarantine + byte backup; tamper=false, 76,438 records
verified, 0 seq lost. Filed as the-method recurrence #11 (the authorship, not the
agent, was the defect). New docket tickets MANIP-2 (744 SZ-045 dispositions vs
1,028 manip_suspect>=0.90, overlap only 544, min score among refused 0.2126 - the
disposition does not reconcile with the score it compares, which may be what the
standing Jaccard 0.462 disagreement is actually measuring) and MANIP-3 (SZ-045 is
absent from the audit trail, join rate 0/744).

## [2026-09-02] correction | The chance baseline was wrong everywhere: realized 12.5%, not nominal 5%

Discharging the tape memo's owed re-run produced a correction that reaches
back through several pages. Scoring 84 features (64 stored + 20 tape, full
coverage, 12,422 rows, 25 day blocks) flags 6 DIRECTIONAL. Every prior
statement compared such counts against the NOMINAL ~5% rate ("~3 of 64 by
chance"). The instrument's own null calibration - 200 pure N(0,1) features
against the real targets, rows and day blocks - measures the realized
DIRECTION exclusion rate at 12.5%, i.e. 10.5 expected flags at 84 features.
Day-block percentile CIs at 25 blocks are anti-conservative. So the observed
count is BELOW noise, and the earlier framing ("5 flagged vs 5.3 expected")
was accidentally right in verdict and wrong in arithmetic. concepts/
resolution-vs-direction-decomposition corrected on both points; the realized
rate is a property of the block count and must be re-measured, never recalled.
Also settled the same run: NO tape feature is directional - the free Kraken
tape back to 2013 adds no directional information about this label - and the
tape memo's one surviving cell (absimb_60, 0.5308 on partial coverage) reads
0.505 [0.486,0.525] on full coverage.

## [2026-09-02] research | LLM-written instrument reliability (deep research #3 resumed) -> a verification standard

wf_c5fac112-377 resumed, 106 agents, 0 errors. READ THE STATS LINE: 120 claims
extracted, only 25 VERIFIED - budget-limited at the verify stage, so "did not
survive" usually means "never voted on", and where it means refuted it is
overwhelmingly scope-mismatch, not the paper being wrong. Filed
raw/research/2026-09-02_deep_research_llm_instrument_reliability.md.
SURVIVED: execution success is not correctness (BLADE, GPT-4o 96% runnable vs
best expert agreement F1 44.8; DS-1000 best-at-publication 43.3% of 1000);
the measuring instrument is itself a defect source (EvalPlus found 18/164 of
HumanEval's OWN reference solutions defective, only via differential testing
against a second re-implementation - the exact structure that caught our two
unpinned defects); under-testing REVERSES rankings; temp-0 is not reproducible
on default serving stacks (1000 samples -> 80 unique completions), so
re-prompting is not a reproduction check; contradictory-instruction compliance
spans 98.2%-20.5% across 37 models (adjacent to the-method #11, though ours was
same-channel specific-vs-general which nothing measures).
DID NOT SURVIVE, and this bounds what we may claim: no primary base rate for the
SILENT numeric classes we actually hit; rendering DS-1000's 56.7% or BLADE's
55.2% as a "silent error rate" is a category error the sources do not license;
no measurement of false-positive bias in LLM analysis; none of adversarial
cross-check vs self-verification.
PRODUCT: repo docs/INSTRUMENT_VERIFICATION_STANDARD.md - eight checks, each
tagged [K] primary-sourced or [I] our-incidents-only, referenced BY PATH in
delegated prompts (a subagent inherits no context).
STILL UNRUN after two attempts: angle 5 entirely (SR 11-7 / OCC 2011-12 text,
JPMorgan CIO 2012 VaR mechanism, Reinhart-Rogoff, Simmons/Nelson/Simonsohn) -
sources fetched, no claim cleared verification; and 4(a)-(e), so the operator's
pasted LLM-inconsistency claims remain UNVERIFIED, not refuted.

## [2026-09-02] repair | The null-readout plane now carries its own power - and the answer SPLITS

/focused-fix on the instruments that emit null verdicts. Harvey & Liu's 86.9%
Type II rate had started functioning as a general excuse for our nulls.
Measuring rather than assuming settled it in OPPOSITE directions for two
instruments, which is why measuring mattered.

champion_skill_report WAS the unfalsifiable case: verdict was `skill <= 0 ->
"NO SKILL"`, a bare sign test with no interval anywhere in the file. Now
reports a day-block bootstrap CI and the |skill| the window resolves. Live:
fresh window n=5,751, skill -0.003562, CI [-0.02371,+0.00166] on 9 day blocks,
resolves only |skill| > 0.01462 - the estimate is 4.1x SMALLER than the
smallest effect the window can see. Nothing about skill was ever established.
The +0.0536 in-sample figure in that module's own docstring also spans zero.

Second defect found while fixing it: the skill score is negatively biased by
~1/n (the oracle refits per window while the predictor is fixed). Measured
-0.005178 at n=200 down to -0.000049 at n=20,000. At the champion's n that is
-0.000174, 20x too small to explain the observed -0.0036.

label_decomposition_report is NOT underpowered, refuting the hypothesis I was
carrying. New --power-calibration mirrors --null-calibration by planting a
DIRECTION effect of known size against the real targets/rows/day blocks:
0.02sd -> 50%, 0.05sd -> 100%. MDE 0.05 SD. So "no directional signal above
0.05 SD" among the 64 features is a REAL falsifiable finding, not a Type II
artifact - do NOT cite Harvey & Liu to excuse it. Caveat: the plant is a clean
location shift with iid noise, so 0.05 SD is a LOWER bound on the true MDE.

cohort_eval's NO_GROSS_EDGE paragraph now states its resolvable floor inline,
and refuses to state a null at all when effective-n is unavailable.

9 planted defects, all red, all restores hash-verified. TWO mutants survived
the first pass and earned pins: dropping the timestamps at the call site (the
report silently reverts to an optimistic row resample) and halving the floor
from 2 SE to 1 SE. Both silent-degradation shapes no existing test saw.
My own process failures, recorded: the first mutation harness left a planted
defect in the tree because its restore was not in a finally, and shell escape
mangling corrupted cohort_eval.py twice before I restored from git.

## [2026-09-02] closure | Five open items closed; the manip ticket found a CORPUS-WIDE defect

Workflow wf_9d67f1cf-a2c, 12 agents, 0 errors.

THE BIG ONE: MANIP-2's root cause is not a manip-gate bug. ml/history.py:2460
mark_disposition stamps the NEWEST OPEN candidate for (asset,direction) with
LAST-WINS semantics - no candidate-id match, no recency bound - while the veto
reads a per-CYCLE scalar. Registration gap p50 923s against a ~5s cycle, so
~10^2 veto evaluations can overwrite disp against one frozen feature snapshot.
mark_disposition has NO code filter, so EVERY disposition in signal_history.csv
carries it: capped 5607, SZ-021 2664, SZ-022 2546, SZ-030 1052, entered 383.
Any study conditioning on disp inherits it, incl. gate_efficacy_report.

CONSEQUENCE FOR THIS VAULT: sources/session-20260821-manip-gate-and-live-
readiness's Jaccard 0.462 was measuring THE SEAM, not the detector. Today's
recomputation gives 0.442 with 27.1% of stamped rows below threshold (was
25.6%) - stable, not shrinking. The PLACEBO finding on that page SURVIVES and
is now mechanically explained: a last-wins stamp is a recency channel, which
is exactly why a placebo stamp outscored the real one. What must be retracted
is the framing of those rows as "refused by a threshold they sit below".
Counter-callout owed on that page.

MANIP-3 confirmed: the entry-path SZ-045 refusal has no audit emitter at all
(join 0/752). A verifier corrected the memo: outputs/events.jsonl DOES carry
241 timestamped SZ-045 lines with the live score, so "unobservable" was false -
the hash chain lacks it, the event log does not.

ML-080 is an UNINFORMATIVE ALARM: its baseline still holds 20.7% retired label
vocabulary from the 2026-07-26 schema change, a permanent TVD floor of 0.2072 =
69% of the 0.30 threshold; 72.4% of post-schema 24h windows already exceed it.
Today sits at the 53rd percentile once dead vocabulary is removed. Over-fires
on renames, under-fires on re-parameterisation (the h432 horizon change moved
tb_time 62.2% -> 16.7% invisibly).

gate_truth_report's "~0.17 AUC" was WRONG, not just stale - 0.405x the correct
value. Computed live: +/-0.0622 AUC at 80% power on effective n=685.4.

DESK-PRACTICE RESEARCH (twice-failed, now closed) CORRECTS US: the 86.9%
Harvey & Liu Type-II figure does NOT transfer to a single pre-registered test -
it is the power of a joint cross-sectional test over ~3,000 funds. Both repo
citations struck at source. NO PRIMARY SOURCE exists for the desk kill-rate
base rate; verdict definitive, stop searching. Meta-labeling is method-only.
The triple-penance rule's IID-Normal assumption is refuted by its own authors'
data in 21 of 26 indices.

TWO-VAULTS: the 84-vs-78-82 disagreement was a DEFINITION dispute, resolved -
all five definitions reproduced independently. 1 safe-to-retire, 83 need a
human read. Nothing has written to the retired vault since retirement.

MY OWN ERROR, recorded: I nearly reported an 'entered'-stamp loss from 383
stamps vs 541 fills. Those 541 fills are 329 positions (partial fills), so
stamps EXCEED positions. Verification-standard item 5 - read the denominator
from the code that computes it - failing on its own author.

## [2026-09-02] decision + design | Target change REJECTED on measurement; manip gate is an illiquidity detector; labeling gets a resource-model design and its first verification node

TARGET CHANGE: REJECTED, decided by measurement not judgement (operator asked
for a learning-basis decision). Same 6,071 rows / 11 day blocks: planted-effect
POWER reaches 80% at 0.05 SD for BOTH the continuous and the 1-bit target - the
switch buys no resolution; and all 64 features scored against label_ret_pct
give 5 CI exclusions vs 6.3 expected by chance (measured null 10.0%), below
chance exactly as the 1-bit target reads. Zero information gain against a
certain cohort reset. The lesson outranks the decision: the question was
answerable offline in two scripts at zero cohort cost because label_ret_pct
was already on the rows. Before any cohort-resetting proposal, ask whether its
central claim is testable on data in hand. Repo: docs/quant/
2026-09-02_flow_vs_eth_and_target_decision.md; the adjudication brief carries a
SUPERSEDED banner (its own stated trigger was run and came back negative).

FLOW vs ETH: the chain-architecture comparison does not reach the code (Kraken
spot, one account-level fee tier). The LISTING comparison found something:
ETH 985.6 trades/h vs FLOW 15.0 (66x); FLOW median manip_suspect 0.927 against
a veto at 0.90; FLOW SZ-045 refusals 470/1,065 (44.1%) vs ETH 1/3,919; FLOW 0
fills ever, alone among 14 assets. THE MANIPULATION GATE IS BEHAVING AS AN
ILLIQUIDITY DETECTOR - a thin book scores like a manipulated one, the
observational-equivalence shape again. Counter-callout owed on
concepts/observational-equivalence and the SZ-045 source page. Do not lower the
threshold; listing FLOW is an operator call.

LABELING DESIGN (repo docs/quant/2026-09-02_labeling_resource_model_design.md):
the operator's Flow/Ethereum brief maps onto this week's measured defects as
PRESCRIPTIONS - the disposition is a mapping write (mark_disposition addresses
(asset,direction) and ignores the UUID every candidate already carries) where
it should be a resource (UUID-bound, write-once, tombstoned on eviction); three
clocks written as one row; no verification role; one ledger with two
vocabularies and no test/production type boundary; label resolution as a
scheduled event. Changes to the writer are BOUNDARY (training corpus) and go to
the ALGO-5/GB-1 bundle. The verification role SHIPPED as SAFE.

VERIFICATION NODE (repo scripts/disposition_integrity_report.py, 6 pins,
direction mutant red): joins every SZ-045 stamp to the sizer's own veto log
line in runner.log. CORRECTION OF RECORD: a verifier had claimed events.jsonl
carries 241 such lines - it carries ZERO; runner.log carries 415 sizer-path
lines (FLOW 224, MINA 190, ARB 1) from 2026-08-25. First per-event measurement
of the MANIP-2 seam: 771 stamps, 630 before the log (unauditable), 141
covered; at a 24h window 103 matched, lag registration->verdict p90 18.7 h,
stored-vs-live score disagrees 80/103, SEAM (stored < veto <= live) 25/103 =
24.3%. Cadence arithmetic had said ~27%. Two independent routes agree; MANIP-2
is confirmed at the row level. Coverage is strict by design so "unmatched" is
unambiguous - documented and pinned.

## [2026-09-02] capability | Sub-hour candles built from the local tape (5 m and 15 m, all 15 assets)

Operator: "find a way below 1h; 15 min acceptable". The venue cannot
re-serve 51 days at 15 m (720-bar cap, no backward paging); the local trade
tape can be aggregated into any journal interval exactly and offline.
scripts/tape_to_candles.py (10 pins, 7 mutants red) built 190,712 bars at
300 s and 69,883 at 900 s, every one accepted by data.candle_journal.ingest,
0 duplicates, 0 conflicts; published to the disposable parquet index (30 new
lanes); cross-checked FLOW/300 journal 5,218 = parquet 5,218. Provenance
committed_by=clock, source=kraken; empty windows write no bar (a thin book's
truth). Two self-inflicted failures recorded: (a) first live run exited 0
having written NOTHING - main() wrapped ingest() in the journal's own
non-re-entrant per-pid lock, 15 refusals against our own pid, and the summary
line reported success over zero writes (standard item 3 on its author); now
fails non-zero on LOCKED / zero-accept, pinned with branch-isolating tests
after both mutants survived by masking each other; (b) a rebuild gated on
`pytest | tail && ...` tested tail's exit code - 4th laundered RC, recorded in
memory session-harness-discipline. Verified the production write by the
journal's own reader, not by the wrapper's exit code.

## [2026-09-02] measurement | Sustainability: all three operator premises REFUTED at power; the threat is the known one

wf_f66a5b27-2c7 (12 agents, 0 errors). Every table FLOW/ETH/BTC; "BTC is
reliable" tested, not assumed. (1) SPREADS: the pooled bear-wider gap (-1.0 bps)
is asset-mix composition - reproduced by a regime-blind within-asset time-shift
placebo; within-asset median gap 0.147 bps; spread is 1-5% of a 44-76 bps fee
round trip; ETH/BTC tick-pinned; the gate already refuses wide spreads. (2) STOP
HUNTS at the hourly lane: reversal-through-entry equals the random-entry
placebo at every horizon 5 min - 24 h (30 min -0.8 pp [-3.4,+1.7]); MDE +4 pp
pooled, BTC 10 pp; rising volume does NOT raise reversal; volatility raises
reversal and tb_pt together (RESOLUTION not DIRECTION). Cut-#7 UNDETERMINED (2
blocks) and VACUOUS on candidates - the nudge applies to live stops only. 5 m
re-run in flight (wf_f4033e09-41f) for sweep depth/duration - the one thing an
hour cannot see. (3) VOLUME GROWTH: return effect +0.19% [-0.05,+0.36]
(opposite sign, null); stop beyond resolution -0.027 [-0.065,+0.017]; every
volume feature NULL through the shipped instrument. (4) LEVERAGE: account-level
max 0.344x (per-position 0.119x); 0/324 stop-liquidation violations; crossover
5.88x; margin branches never fired; Kraken's real liquidation formula is NOT in
the repo - every headroom uses the bot's own 150% floor. (5) VALUE ACROSS
ENVIRONMENTS: net of 0.6% cost POOL -0.71% [-1.03,-0.39], FLOW -1.53, ETH
-1.10, BTC -0.82 [-1.05,-0.56] (MDE 0.35, tightest); no cell positive above its
floor; shorts lose LESS than longs (0.28 pp, p=0.000) - a loss-size difference.
"BTC reliable": earned as the tightest CI, and that CI is reliably negative.
ARM package: docs/quant/2026-09-02_sustainability_arm_package.md - do not arm
spread/volume/anti-hunt changes; ARM two SAFE prerequisites (encode Kraken's
liquidation formula; audit-code the margin branches); FLOW listing is the
operator's. Verifier corrections carried into the memos (10): BTC stop-hunt MDE
4 -> 10 pp; crossover 6.67 -> 5.88x; sl_frac provenance 97.9% -> 42.6%; pooled
volume quintiles were an asset selector; the pooled spread gap was composition.

## [2026-09-02] closure | 5-minute stop-hunt confirms null twice; self-review finds and fixes a real CRITICAL; full diagnostic scan filed

5-minute re-run (wf_f4033e09-41f) does not move the verdict: pooled reversal
30 min 1.3% vs placebo 2.5% (floor 5 pp), 2h 12.5% vs 12.4% (floor 15 pp). The
NEW measurement the hour could not make - sweep depth/duration beyond the
stop - is ALSO placebo (48 vs 50 bps at 30 min, 83 vs 92 at 2h). Rising volume
into the stop still does not raise reversal; stop-share of resolved rows
FALLS with growth (0.600->0.493). Verifier ran an independently-designed
second placebo and flipped the sign of "BTC has the highest reversal" -
struck - but nothing clears its floor under either design. Row B (anti-hunt/
ALGO-5) of the sustainability ARM package closed at two independent
resolutions, no measured motive.

Running /adversarial-reviewer on the last commit (tape_to_candles.py, shipped
hours earlier) found a real CRITICAL: an uncaught exception on ANY single
asset killed the ENTIRE multi-asset batch. Reproduced by execution (a planted
NaN): the first asset's bars were already committed while the third was never
attempted and the summary loop never ran - a bare traceback, no report of
what succeeded. The exact failure shape the-method exists to catch, in code
shipped the same session that wrote the instrument verification standard.
Fixed with per-asset exception isolation at both the aggregate and ingest
stages plus an independent outer catch in main(); 14 pins (was 10), 4 new
mutants all red, restore hash-verified.

Full diagnostic scan filed (docs/quant/2026-09-02_full_diagnostic_scan.md) -
a synthesis connecting every defect/finding into one prioritized list, plus
three new targeted checks. The reason-code registry is healthy: my own quick
regex flagged 50 "orphan" codes, a false positive (SHA-256 matched the
pattern; the SD-family and stub-adapter codes are a deliberately separate,
already test-pinned allowlist) - the instrument was correctly the suspect,
this time on me. The disposition write-semantics fix (the MANIP-2 root cause)
is very likely training-inert (disp is written purely descriptively, read
back by nothing in the training path) but recommended for scoped adjudication
rather than a unilateral fix since it lives in ml/history.py. Aggressive
exploration - the direct, legitimate reading of "aggression in learning" - is
a real, already-shipped, enabled feature: 23,897 normal vs 333 aggressive
exploration entries (1.4%) since 2026-07-19; its outcome comparison is named
owed, not measured (no position id on the audit lines). Headline: nearly
every rapid-impact opportunity is an integrity fix, not edge-generation,
because every edge-generation channel tested this session came back null at
real power.

## 2026-09-05 — the tautological TRUST ANCHOR (fifth specimen class)

Operator surfaced a verification defect in a third-party gate: the escape hatch
says "re-confirm against canonical_source", and `canonical_source` is a field of
the same record an attacker submits. Researched to primary sources and filed as
the FIFTH specimen class on [[concepts/tautological-instrument]] rather than a
new page — it is the fourth class (the tautological CHECK) relocated from the
measurement domain to the trust domain, and it is the security-domain statement
of CLAUDE.md's law that a gate's release condition must never depend on the
thing it blocks. Four prior repo incidents share the shape; this is a fifth, in
someone else's code.

Catalogued as CAPEC-693 (StarJacking). Type specimen CVE-2024-23832 (Mastodon,
CVSS 9.4): `FetchRemoteResource` passed the fetched object's `id` instead of the
queried URL — a one-variable substitution with an identical log line. The class
is blessed by RFC 7515 §4.1.2 (`jku`: TLS mandated, anchor unconstrained) and
the seam sits in RFC 8725 §3.8 itself (MUST on the tautological half, `may` on
"the issuer is trusted").

ADOPTED RULE: `self_consistent` and `externally_corroborated` are two fields,
never one boolean — the DKIM/DMARC resolution, where the repair is a NARROWER
CONCLUSION rather than a stronger check. Detection is only partly mechanical and
the page says so; the tractable move is constraining the egress surface, shipped
as `tests/test_no_attacker_directed_fetch.py` (mutation-verified). Repo status
CLEAN and established, not assumed: parsers extract only title/pubDate, no href
extraction anywhere, every fetch URL from a constant or config.

Full citations, CVE register and instrument caveats:
[[raw/2026-09-05_self_referential_verification_research]]

### Addendum same day — the formal statement, and a corrected headline

The remedy/detection lane returned the exact framing: this is **principal
collapse** in the ABLP calculus, not circular reasoning and not vacuity. It
also asked to be checked on its own load-bearing step, having derived it in one
pass. It was checked, and it was wrong: the report gave `S ^ C = S`; two
independent routes (order-theoretic and semantic) both give **`S ^ C = C`**.
The conclusion survives and sharpens - the joint principal collapses to the
nominated source, whose utterances the speaks-for axiom attributes to the
submitter, so the corroboration is the submitter's own word laundered through a
channel it chose.

Recorded on the concept page WITH the correction, because an agent that flags
its own headline as un-double-derived is doing the thing the page is about.

Two further results worth carrying: **vacuity detection would pass this gate**
(substituting canonical_source does change the verdict - the check fails to
fail only against an adversary holding both halves), so the formal-methods
frame has the right method (mutation, Beer et al. 1997) and the wrong
predicate. And the detection verdict: the undecidable half is whether the
anchor lies inside the submitter's trust domain, which is a fact about the
world, not a program property - so the move is to make the state unrepresentable
(one anchor-fetch chokepoint taking an enum, never a URL) rather than to detect
it. Architecture beats analysis.

---

## 2026-09-05 — the signal factory read out, and the champion has no measurable skill

Ran the pre-registered entry-signal factory (`scripts/signal_factory.py`,
`GRID_ID v1-2026-09-05`, 1,454 candidates over 52 learnable features, still
UNCOMMITTED and un-pinned). 217 raw DIRECTIONAL flags against a **measured**
chance rate of 0.10 (145.4 expected from noise); 54 survived BH-FDR at q=0.05.
**That is not 54 discoveries** — `fv_edge_bps` appears in ~15 of the top 25 and
`basis_dir` in ~7, and both survive ALONE. An interaction grid re-flagging its
own marginals is the classic artifact.

Time-ordered out-of-sample split (early 15 days / late 13, both above
`MIN_CI_DAYS`=5 so the instrument's own guard does not void the intervals):
**two of four candidates repeat** — `fv_edge_bps` 0.4634 -> 0.4806 and
`basis_dir` 0.4496 -> 0.4718, both below 0.5 with day-block CIs excluding it.
`manip_suspect` and `liq_pocket_pull` FLIP sign across the halves: corpus
artifacts. Signed with-my-trade, "below 0.5" means **anti**-predictive.

**The candidate then died on the cost bar, which is the criterion that
matters.** Barriers are volatility-scaled 8σ:6σ with a cost floor, so
break-even P(pt) is a BAND — `6/14`=0.4286 when barriers dwarf cost, up to
`(1.8+0.6)/4.2`=**0.5714** at the floor. On the held-out half, resolved rows
only (n=6,126, 12 blocks), the flipped rule reaches P(pt) **0.4851**
CI [0.4277, **0.5373**] for `fv_edge_bps`. **The upper bound sits below the
cost-floor break-even.** Real, replicated, and too small to pay.

Also: `basis_dir` is already weight **rank 3 of 64** (w=−0.220) — the model
knows it. `fv_edge_bps` is rank **59** (w=−0.0033), effectively ignored, and
adding it cannot rescue a model that has no skill to begin with:

**Re-derived the champion's skill and corrected a baseline** (callout filed on
[[synthesis/the-money-path-thesis]]). The page's "Brier 0.24728 vs **0.25** for
a coin" scores an unbalanced label against a FAIR COIN; the honest constant is
`p(1-p)` = **0.247458** at base rate 0.4496. Current corpus, deployed
selection: model **0.248069**, skill score **−0.0025**, day-block CI
**[−0.0029, +0.0043]** — **indistinguishable from the constant**, not worse
than it. Corroborated by stored permutation importance (max OOS AUC drop
+0.0079, 0 of 10 above 0.01).

**The instrument was the first suspect and the first suspect was mine.** The
opening read of "2.72% worse than the base rate" divided `oof_brier` (the
purged walk-forward OOF **subset**) by a constant built from `class_balance`
(the **full** training matrix) — two populations, one ratio, and the error ran
in the direction that made the finding look bigger. [[concepts/the-method]]
reading-discipline (a), caught by re-deriving both numbers on one vector.

---

## 2026-09-06 — cut #10 minted: six verified defects, E1's fee correction, and two things NOT bundled

Operator approved spending one boundary. What went in: **B1** never-delivered
books read FRESH (a strict xfail since creation, un-marked in the same commit),
**B2** `est_fee_bps` absent-default 0.0 → 6 bps floor, **B3** NaN equity →
multiplier 1.0 with no reason (the "fails CLOSED" veto failed open on the one
input it couldn't do arithmetic on: `max(nan,0)` keeps the NaN), **B4** the
execution feed was an unchecked injectable — a submit on a non-Kraken feed
PLACED; now a deny-list assertion, **B5** fill-ledger dedup disarmed on an
unloadable cache (now direct scan → refuse + OM-086), **B6** capacity constant
18.3 → **43.7** (two derivations agree to the tenth on the check's own
36h-window statistic), cap 1200 → 1800. Plus **E1**: cut #9's 22/38 is NOT a
published Kraken row; binding at $17,482 is **20/35**. Derived entry bar
**0.6772 → 0.6642**. `exec_era` → `10-<record sha>`.

**What was NOT bundled, and the mistake behind it.** I recommended bundling
ALGO-5 + GB-1 "to spend one reset instead of two" — and had not read the
docket. ALGO-5 was **adjudicated "do not arm" on 09-02** at two independent
resolutions. GB-1 is **refuted at HEAD**: `_give_back_candidate` has carried
`arm = max(arm, cost/(1−frac))` since 07-30, so the effective arm is 1.27% at
76 bps (verified live: both open positions carry est_cost_bps). The
"two resets" argument collapsed — there is no second reset queued. The
operator was steered toward the wrong option on a stale premise; retracted
before code. [[concepts/the-method]] rule: a summary row is a pointer; the
signed document (`2026-09-02_sustainability_arm_package.md` row B) was read
directly before retracting.

**E1's real result** (corrected schema — the first parse returned $0.00 from
wrong column names, a broken scan): **92% of fees ($361/$393) on exit and
hedge legs at taker rates**; entry-only instruments saw 8%. **60% taker** on
a passive-execution thesis. In paper `fees_delta_usd` == configured bps to
the digit — a restatement, exactly as the Simons pass warned. The fee lever
is NOT retired; the next cost question is execution.

**B6 lens correction.** An hourly BIN reads peak 75 / median 17 and made 18.3
look like "the median mislabelled as a peak". Wrong lens: the check is
Little's law over the HORIZON, so the horizon-window sustained rate is the
statistic, and on it 18.3 was simply stale (2.4×). A sliding window that
floored its span at 1 s produced 21,600/h — discarded as broken.


---

## 2026-09-07 — closeout: per-era gross is a table, E2 refutes the expected null, E3 is starved

**Per-era gross** (fills.csv, closed trips, single-era only, hedges out):
era-7 +$0.17/trip CI [+0.03, +0.34] — the only era clearing zero, on an
optimistic trip-bootstrap; **era-9 −$0.06, CI [−0.22, +0.11], n=29 — spans
zero.** The +$0.0255 I quoted on 09-05 belongs to no era. The "open sign"
was open because it was asked as one number.

**E2** (51-day 5m parquet tape, every bar a hypothetical entry, no Gaussian):
the oracle-MFE median clears the 55 bps fee line within a day on every core
pair — ETH at 8 h with 152 independent windows. The Simons pass predicted it
never would. So the instruments CAN pay the rake; MAE is symmetric with MFE
(random-walk shape), so without a selector the median trade still loses.
The sharp reading: at the shipped 36 h horizon the majors' median MFE
(132–178 bps) sits BELOW the 240 bps take-profit barrier — only the top
~25–30% of paths can reach TP by construction, which IS the 30–35% shadow
win rate, now derived from the tape. That is geometry, ALGO-5 territory,
adjudicated *do not arm*. Filed, not acted on.

**E3** re-run: null holds (MFE percentile 0.526 ± 0.046) — at **n=48**,
because the harness reads recordings and retention (the S3 defect) had
evicted 452 of 500 trade spans. The parquet tape covers all of them; the
re-run is owed, not done — this pass was measurements only.

**Two instrument corrections of my own**: a closeout pin asserted the new
`momentum_bear_max` partitions the lattice like the literal −0.34 — it does
not, because −1/3 ≤ −0.34 is False; the literal had EXCLUDED the level and
the runtime's repair had included it. The failing pin is what surfaced that.
And the bridge-branch merge was gated on bandit and reverted by its own gate
(B404/B603) — kept, not forced.

---

## 2026-09-07 — the last 47 findings verified; seven more SAFE fixes; the backlog is now evidence, not reading

25 agents verified the remaining unverified findings by execution (37 hunt,
10 candle): **36 CONFIRMED+SAFE, 9 BOUNDARY, ~14 REFUTED, 4 already fixed,
16 cannot-determine**. Every open finding in this repo now carries either
an executed reproduction or an executed refutation. Filed verbatim at
`docs/quant/2026-09-07_verified_findings_register_47.md`.

**Fixed (SAFE, batch 3):** the ARM LIVE gate had no pytest pin at all —
neutering it reddened 0 of 2,027 tests; the fill ledger's width guard was
one-directional (ragged rows on any unknown header column) and the LIVE
17-column ledger has been silently dropping `book` on every fill since
09-05 — now counted and warned, migration (runner-stopped) still owed; the
deploy gate's bandit scanned 82 files while the law scans 195; a red HARD
gate whose last line said "cannot find" was waved through (h41's residual);
the supervisor's self-handoff inherited its own log handle and overwrote
its exit-forensics line every time; a cost-attribution ratio still divided
a struck 65 bps by the current schedule; eleven report timestamps were
naive local time (read 00:13Z, stamped 19:13).

**Docketed, not touched:** the SMC candle features — five of ten are
binary, null, saturated, or volatility proxies (`fvg_liq_confluence` ≈ null
at ±400 ulp, `fvg_pull` polarity dead, missingness ≡ neutral 7/7, FVG count
≈ volatility) — model-side and FROZEN; three BOUNDARY runtime findings
(spread floor binds silently, `purpose` string is the sole exemption key,
NaN marks pass `filter_mark` and silence the hard stop); and the SAFE items
that touch execution modules (h13's four fee-fallback vintages).

**One correction of my own instrument:** my new HARD-gate absence check
demanded a quote in `No module named 'x'`; an older fixture writes it
unquoted. The pin was right; the regex was mine.


---

## 2026-09-07 — cut #11 LIVE: the bot is told to commit

The operator asked the right question ("what am I doing wrong") and got the
honest answer: perfecting the measurement of zero. Then: "make it do things
that would make it have to either end with a positive or negative PnL."

A five-lead design pass recommended the arithmetic-optimal answer for a
coin-flip model — trade LESS, so fees bite less (best case +5¢/day, hedger
on). Right math, wrong objective; recorded and overridden. Cut #11 removes
the three zero-makers that are not the model: the **hedger** (cancels the
bet by construction; 40% of all fees), the **alt universe** (the measured
loss channel), and the **$18 probe ticket** (`size_scale` was already at
its clamp; the floor was the only lever → $60). Everything else untouched.
Under H0 the daily paper loss GROWS (~$0.94 → ~$1.30) — the price of a
readable sign, accepted by the operator in plain language.

Registered before data: n=50 lean, n=100 verdict, day-block CIs; powered to
catch losing, not to certify small winning; STOP never reverts to the
hedged 12-asset book. Take-profit width is the pre-named next lever
(240 bps sits above the majors' 36 h median oracle move; deferred because
`label_era_of` encodes the horizon only and a width change would mix two
geometries under one era).

Live at 14:58:47Z, pid 7808, `11-6e584923`. Built on a branch, shown to the
operator in plain language, merged on "Go".


---

## 2026-09-07 — the wash-trading paper, and a fee premise I repeated

Operator: "It might explain my fees." It does, twice over.

**What the bot did that a wash trader does:** hedge legs were **38.6% of
all-time traded volume** — the bot buying and selling against itself, paying
the fee both ways for zero net exposure. On an AMM that is the manipulator's
mechanic (colluding addresses, near-simultaneous buy/sell, holdings nearly
constant — the paper's detection rule); here it was accidental, unrewarded,
and 40% of all fees. Cut #11 turned it off.

**What I repeated:** cut #10 booked 20/35 on a **$17,482** 30-day volume read
from the operator's Kraken app on 08-29 — a rolling window — and the
paper/real boundary says the sim's fills count toward no tier at all. The
sim's own trailing-30d notional is $5,185. No API credentials resolve on this
box, so OM-080 cannot bind the row. If the real account's volume has rolled
off, the true row is 25/40 and the booking understates cost. Fifth instance
of [[concepts/the-method]] recurrence #1 — a fee reading asserted from a
dated screenshot — and this time the reader was me. Filed on HANDOFF as a
FEE-TIER PREMISE CAVEAT; FEE-3 (live TradeVolume) is the cure.

## 2026-09-07 — beta/alpha attribution: the instrument was wrong eight ways, and the answer is "the market, with nothing to hedge"

Operator asked whether the bot can learn what it is hedging against. Built
`scripts/beta_alpha_decomposition.py` (Jensen's alpha per closed trip against
a crypto basket), and it was refuted before a number was filed — eight silent
defects, the cleanest [[concepts/the-method]] instance this month: alpha as
the mean residual (≡ 0); a 5m store that ended 09-02 while fills ran to 09-07,
so the 22 losing recent trips were dropped without a word; an anchor on the
bar CONTAINING the fill (a price printed after it) with a pin named
`no_look_ahead` that asserted exactly that; a percentile CI ~2× too narrow at
few days; gold in the crypto factor; one day carrying 47% of the fit; a dead
bootstrap; and my own "clear" rule that every negative interval passed. All
fixed, 12 pins, mutation 8/8 red; the store refreshed by
backfill → tape_to_candles → compact.

Corrected readout, 329/329 trips: beta 0.894 [0.64, 1.15], alpha −5.1 bps
[−20, +11], p 0.49 — zero on every route and both baskets. The only clear
alphas are NEGATIVE: era-9 −54 bps/trip [−83, −22] (8/8 days) and ARB −88 on
two routes of three. LINK's +43 was the look-ahead. Second route: the 159
hedges as practised netted −82.5 bps at a 0.1-minute median hold, 147 of 159
under a minute. Read: the bets were the market, there was nothing
coin-specific to hedge around, and the losses that are clear are selection/
exit losses a hedge would have kept. Corroborates cut #11; points at the
TP-width lever. Filed: `docs/quant/2026-09-07_beta_alpha_attribution.md`,
session page §7, raw JSON + refutation verdict. Owed: re-run at era-8
n=50/100.

## 2026-09-07 — the theory named: Treynor–Black alpha isolation

Operator read the attribution (beta ≈ 1, alpha ≈ 0) as "market-neutralised around nothing — hedge systematic risk only once there is measurable idiosyncratic alpha to isolate" and asked what the theory is. Filed [[concepts/treynor-black-alpha-isolation]]: Sharpe/Jensen decomposition → Treynor & Black (1973) optimal active weight ∝ α/σ²_ε and the appraisal ratio → Grinold–Kahn information ratio and Fundamental Law → portable alpha / market-neutral in practice. Plugged in: trip sd 132 bps = market 82 ⊕ residual 104; appraisal ratio −0.05 pooled, BTC −0.17, era-9 −0.59 — the theory's instruction is no active position and no hedge, which cut #11 already applies. Vault was silent on the concept before this page.

## 2026-09-07 — operator-flagged reference: Flow "Forte" (filed on directive)

Operator pasted https://developers.flow.com/blockchain-development-tutorials/forte and, mid-assessment, said verbatim "Stop and include this no matter what." Assessment stopped; the reference is filed as given at `raw/research/2026-09-07_flow_forte_pointer.md` (Flow Actions with IncrementFi pool-liquidity and flashloan connectors, native Scheduled Transactions, Fix128/UFix128 math; both pages fetched 2026-09-07). It sits next to [[concepts/treynor-black-alpha-isolation]] §6 route 3 (structural edge) because that is the conversation it arrived in. Kraken remains the sole venue (invariant 3); any use is an operator adjudication.

## 2026-09-07 — Flow reference, link 3: linktr.ee/flowonchain (filed on the standing directive)

Operator pasted Flow's Linktree; appended to `raw/research/2026-09-07_flow_forte_pointer.md` verbatim: "The Home of Consumer DeFi" (1.1M MAU, ~1B transactions claimed), six links — Flow.com, Earn with Peak Money, Liquidity on Flow (liquidity.flow.com), Flow Bridge, Swap (swap.flow.com), Dune dashboard. Destinations not fetched. Not assessed; venue law unchanged.

## 2026-09-07 — Flow links accessed on instruction ("Access it")

Six Linktree destinations fetched (static HTML): liquidity.flow.com, swap.flow.com, bridge.flow.com are JS shells (titles only); peak.money 403; flow.com rendered (products: Bridge via Stargate/LayerZero/LiFi, Swap, Wallet, Actions, VRF, Scheduled Transactions, Credit Market; Uniswap partnership; stablecoins ATH $74.6M June 2026); Dune dashboard rendered (TVL $12.68M, stablecoin cap $72.5M, MAU Aug 2026 312,496 wallets, 90-day avg daily active 42,332, weekly tx 998,756). Recorded a two-source discrepancy: Linktree "1.1M monthly active users" vs Dune 312,496 monthly active wallets. All appended to `raw/research/2026-09-07_flow_forte_pointer.md`. Not assessed.

Addendum (same entry): the two developer pages behind the shells were fetched and appended — Flow Actions primitives (Source/Sink/Swapper/PriceOracle/Flasher; connectors for IncrementFi swap + flashloan, Band oracle; atomic single-transaction composition; no caller-type restriction stated) and Scheduled Transactions (`FlowTransactionScheduler.TransactionHandler`, High/Medium/Low priority, fee in FLOW by effort/priority/data size, absolute timestamp "at, or after" — no execution window, limits or failure semantics on the page). The DEX behind swap.flow.com per the docs is IncrementFi.

## 2026-09-08 — era-8 day-1 watch: the heat cap binds the accrual rate

Status 11:21Z: RUNNING, DRY_RUN, equity $789.69, 5 open positions. Era-8 (`11-6e584923`) since the 09-07 15:40Z restart: 2 entries ($67 BTC 09-07 15:50Z, $60 ETH 09-08 05:30Z), 0 closed era-8 trips (the two era-8-stamped exits closed era-7 positions). Since 09-08 02h every sizing pass is vetoed — 34 of 34 — on **RP-050 portfolio heat 0.37–0.39 vs `risk.heat.max_portfolio_heat_frac` 0.35** (heat = corr-weighted open notional / equity; open notional ≈ $305: ETH e602d04f $47 built from three $15–16 adds across eras 9→10 since 08-31, BTC 99ec3b2c $32 (two adds, eras 9→10), PAXG short $99 (era-10), BTC $67 + ETH $60 (era-8)). Arithmetic: cap $276 of notional at $790 equity; $178 is held by pre-era positions; headroom for one more $60 ticket at most until something closes. Consequence: the ~4 fills/day the cut-#11 registration assumed was an $18-ticket rate; at $60 the heat cap binds at ~4 concurrent positions × 36–40 h holds ≈ 2–3 entries/day ceiling, and 0/day while the stale positions sit. n=50 reads 4–7 weeks, not 2. Not a bug; a design interaction not modelled at cut #11. Under the moratorium the heat cap is risk-stack (cohort-resetting) — NOT touched; recorded on HANDOFF ERA-8 for the operator. Also: retrain loop healthy (auto-retrain 09:59Z on 16,688 rows, challenger rejected); fill-hazard L1 regenerated 09-08 by the scheduled task, verdict NO again.

Addendum 2026-09-08: operator decision on the heat-cap binding, verbatim "I'll just wait it out" — option (a). Heat cap stays 0.35, pre-era positions run off on their own exits, era-8 read points stand (expect n=50 in 4–7 weeks). Recorded on HANDOFF ERA-8 WATCH; reopen only on a zero-entry week.

## 2026-09-08 — crypto skills scout: nothing installed, and the refuter was right

Operator: "Look up any good crypto skills that would help you." 11 sources, 13-agent workflow (judge + refuter) plus 12 direct raw fetches. Every INSTALL verdict was refuted on re-read: kraken-cli (official, 59 skills, MIT) has a real read-only `-s market` MCP but its README default is `-s all` (trade + funding) and its skills summarize canonical docs that fetch fine; agiprolabs' microstructure/walk-forward skills duplicate the vault's Avellaneda–Stoikov page and overfit_check.py; ccxt read-only is already in the .venv at zero toll; the best quant vocabulary skill 404s on its own scripts. Gaps NO skill fills: MinTRL/MinBTL, effective-n deflation, cluster-robust inference, and any mutation/injection step — the repo is ahead of the field. Harvested: canonical Kraken rate-limit URLs (counter/decay tables; our feed uses a flat bucket), the quant vocabulary, and the-method #12 consequence (e) (the positive join rule). Side effect: the Kraken fee page fetched today puts 20/35 at the **$25K+** row and 22/38 at $10K+ — cut #10's "20/35 at ≥$10K" premise and my "25/40 below $10K" caveat are both misreadings; second route via public AssetPairs fee arrays in progress. Filed `raw/research/2026-09-08_crypto_skills_scout.md`.

## 2026-09-08 — the fee ladder was the legacy one: cut #10's E1 booked a tier the account does not hold

Found by accident during the skills scout (a vendor skill's 0.16/0.26 matched nothing). Kraken's fee page, read as raw text with no summarizer (20:15:29Z), and the operator's 08-29 app screenshot both carry the current cross-platform ladder — T1 40/80, T2 30/60 at $2.5K, **T3 22/38 at $10K or $20k assets-on-platform**, **T4 20/35 at $25K or $50k AoP**, … 0/5 — while `core/venue_fees.py` (09-05) had read the LEGACY ladder (25/40, 20/35 at $10k, 14/24 …) from `/0/public/AssetPairs`, which by today returns no fee arrays at all. On that module's word cut #10's E1 moved the booking 22/38 → 20/35: from the account's real Tier 3 (cut #9, from the app, was RIGHT) to a Tier 4 the $17,482 volume did not reach. My own 09-07 caveat invented a "25/40 below $10k" row. Corrected drift report: booked 20/35 UNDER-states the round trip by 5 bps at $17,482 (35 bps if volume decayed to Tier 2). Instrument fixed (ladder + AoP, page fetcher with caption-anchored parser, two-route drift report, derived guard WARN and fallback, 5 false comments dated and corrected; 187 pins green, mutation 7/7; guard sweep identical). Nothing booked changed — re-booking is cohort-resetting, docketed FEE-4 (needs the operator's tier, 30-day volume AND AoP). Filed `docs/quant/2026-09-08_fee_ladder_correction.md`; [[concepts/the-method]] #13 (recurrence #1 committed by the module built to end it: prefer the surface the venue keeps current; two sources disagreeing IS the finding; a table pinned against its own source is circular; a booking correction is a boundary in both directions).

Addendum 2026-09-08 (evening): the operator supplied the live reading — Kraken app 17:51 device time: **Tier 5, 30-day spot volume $69,652.65, AoP $822.24** (screenshot filed `raw/quant/2026-09-08_kraken_fee_tier_screenshot.png`, transcription `raw/quant/2026-09-08_kraken_fee_tier_reading.md`). `binding_row` → 15/30; the app's next-tier distances (30,348.35 volume / 199,178.76 AoP) reproduce from the table to the cent — third route on the ladder, AoP column confirmed. So the booked 20/35 now OVER-states the round trip by 10 bps (22.2%), $0.06 per $60 ticket: the era-8 readout is conservative, not optimistic as this morning's record assumed from the 08-29 volume. The tier is rolling on the operator's real trading (×4 since 08-29) — book from a fresh reading at the boundary, never chase mid-era. FEE-4's inputs are supplied; the re-booking remains the operator's boundary call (era-8 has ~1 day of accrual, so a boundary now resets almost nothing).

## 2026-09-08 — cut #12 staged: FEE-4, the row the account holds (era-9)

Operator: "Re-book now ... Yes do a reset." Decision record committed alone as `10d4d0c2` (= the era stamp); `scripts/cut12_stage.py --apply` moved six keys and nothing else — pretrade/order_manager 20/35 → 15/30, est_fee_bps 35 → 30, label round-trip cost 0.55 → 0.45; derived entry bar 0.6642 → 0.6381; guard 0 FATAL. Stage refuses unless `core.venue_fees.binding_row` at the operator's reading (Tier 5, $69,652.65, AoP $822.24) equals the staged row. Pins 7, mutation 4/4 red; era-8 closes with 2 entries / 0 closed trips. Rule added: the tier rolls with the operator's real trading — book from a fresh reading at the boundary, re-read at every readout, never chase mid-era. In parallel, operator-approved: a signal-quality battery (8 theories + quality-focus experiment, `wf_b11a8349-ceb`, approved to go beyond read-only) and a config.json debug pass (`wf_74b30a86-ba5`) whose evidence-backed amendments may ride this same boundary before merge. DoD running on branch cut12; live only after merge + runner restart verified from the boot line.

Addendum 2026-09-08 (cut #12 review): the adversarial review of the diff returned BLOCK with three criticals, all real — (C1) a `p_bar` fixture baselined to the old bar went silent at 0.6381 (re-baselined 0.183 → 0.209); (C2) era-8 counts in four permanent files were RECALLED from the 11:21Z watch, not re-derived — the ledger at staging (23:29Z, two routes) holds 4 entries and 1 closed trip, and the closing count belongs to `cohort_eval` at the restart, so no count is written into law now; (C3) 'geometry untouched' was false the way cuts #9/#10 were silently false: `barrier_geometry` floors σ at the cost, so label PT 220 → 180 bps, SL 165 → 135, BE/trail floor 76 → 66, same label_era — now said in CLAUDE.md, HANDOFF, the stamp comment and a record erratum. Warnings fixed: `main()` refusal paths pinned (second apply, wrong TO row, wrong reading, incoherent cascade); config_guard FATAL for a label cost below the booked round trip; the orphan signal-quality-gate sentence moved from law to the docket. Lesson filed to [[concepts/the-method]] rule (g): a number written at staging that was true at the morning read is a recalled number.

Addendum 2026-09-08 (23:38Z, correction of the morning watch): the config.json debug pass surfaced the LONG BOOK (`long_book.enabled`, BTC/ETH accumulation, 12% thesis stops, no time stop) holding 2 of 5 slots — the 'pre-era positions'. A full-day scan across the rotated log (`events.jsonl` rotates at 5 MB; the live file held 55 minutes) shows the 83 daily heat vetoes are the long book's hourly `LB-010` add attempts; the 5 m book placed 3 entries on 09-08 and had 12 vetoes of its own (cooldown/crowded). So 'every sizing pass vetoed, n=50 in 4–7 weeks' was two instrument errors of mine (a needle matching two populations; a tail read as a full scan) — corrected on HANDOFF, CLAUDE.md, the cut #12 record erratum, and filed as the-method stage-6 rule (b′). Era-9 accrues at ~3/day → n=50 in ~2–3 weeks. The long book is an operator docket item (keep inside era-9 accounting, or disable at a boundary).

Addendum 2026-09-08 (23:49Z): **era-9 went live at 23:47:45Z by accident of load, not by the procedure.** `pc_supervisor` logged "runner stale/absent -> relaunching" at 23:41Z — the old runner's `status.json` heartbeat exceeded STALE_SEC 120 s under the cut's DoD battery plus two workflows' agents running pytest — and the relaunch booted from the working tree (branch cut12, config applied): boot line `fees=15/30bps`, lock taken by pid 6664; a second spawn backed off on "peer runner healthy"; the old runner (7808, 20/35) exited on the forfeited lock by 23:49Z. Era-8 closed FINAL: 4 entries, 1 closed trip. The committed tree will differ from the booted one only in docs/tests/guard list; a deliberate restart on the merged commit follows the DoD. Lesson to memory `era-cut-procedure` #7: a DoD can restart the runner for you — run it at below-normal priority and never beside agent fan-outs, or stage→DoD→merge→apply→restart in that order.

## 2026-09-09 — the signal-quality battery returned: a measured null on skill, and one leak every task inherited

Operator: "do a run of number theories ... see what happens when quality of signals are focused on" (approved beyond read-only). `wf_b11a8349-ceb`: 8 theories on 17,057 triple_barrier_h432 rows (26–31 day-blocks), judge, 3 refuters, 2.4M tokens. Verdict that survives refutation: **no deployed feature carries direction skill that survives multiplicity** (0/63 BH; the two survivors, fv_edge_bps and basis_dir, are anti-predictive); **the champion out of sample equals its base rate** (Brier skill +0.002 [−0.026, +0.017]; AUC 0.553 [0.48, 0.62]) — though the refuters correctly cut the STRENGTH: at 15 day-blocks the test can only detect AUC ≥ 0.60, so 'equals' means 'below the resolution'; **focusing on signal quality does not move net from zero** — 27 pre-registered walk-forward rules, baseline −42 bps/trip at 15/30 [−73, −13], 0 BH survivors, DSR 0.41, the one positive cell (+15 bps, p 0.75, n_eff 4.5) underperforms a plain long-only control; on the real ledger every confidence subset is negative and the highest-confidence forced probes are the worst (−108 bps). The fee row 15/30 shifts every number +10 bps and changes no verdict. What looks like model skill is trade SIDE (longs 0.545 vs shorts 0.286 hit the profit barrier) — beta, as the 09-07 attribution said. Both refuters converge on the study's most useful finding, which no task named: **a corpus-wide stale-entry anchor** — the labeler enters at close[k] of the last COMMITTED bar (`ml/history.py:2658`) while the decision and every live-book feature are taken ~150–160 s later inside bar k+1 (audit phase uniform, n=25,055), so the 'bar-(k+1) reversal' features are reading a move the label's entry price predates. That is a labeling/timing defect to size and, if material, a model-side boundary. Also: the five regime one-hots are an exact dummy trap into a logistic with intercept (VIF ∞); era h432 pools 4–5 cost-floor geometries; `sent_dir` is contrarian at 36 h with uncorrected intervals excluding zero — a candidate for ONE pre-registered test. Record and phase-2 (size the anchor leak; the sent_dir test; the dummy-trap check) to follow.

Addendum 2026-09-09 (00:2xZ): the cut-#12 DoD at Idle priority (runner heartbeat never above 10 s) read 4863 passed / 1 failed on pytest (the failure is being named by a re-run — the guard module was hoisted mid-suite for a pyright complexity error) and **bandit red with six High-confidence findings, all in gitignored agent scratch under `outputs/reports/`** (try/except/continue, a subprocess import) — the same wrong-corpus shape as the purity walkers earlier tonight. The law's bandit exclusion becomes `./.venv,./tests,./outputs` (CLAUDE.md, dated note), mirrored in `scripts/auto_update.py`'s deploy gate, `.vscode/tasks.json` and `docs/ASSURANCE.md`, with the batch-3 pin extended to assert the mirror. Everything else green: smoke 220/0, assurance 51/0, overfit 3 ARMED on 17,065 live rows, ruff, compileall, pyright 0.

## 2026-09-10 — operator-flagged reference: GitHits (filed, not adjudicated)

Operator pasted, verbatim: `GitHits / Community / Trending / Version-aware index of open-source dependencies for Claude`. No URL. Filed under the 2026-09-07 directive — a pasted reference is captured BEFORE any relevance assessment. Raw: `raw/2026-09-10_githits_operator_reference.md` (the paste plus the verbatim WebSearch return, 8 links). Source page: `sources/githits-evaluation-2026-09-10` (**PROVISIONAL**). What it claims: a version-aware index of public open-source code, package internals, dependency graphs, vulnerabilities and changelogs, exposed to agents as an **MCP server over stdio**, with a CLI and a Claude Code plugin. **Every capability claim carries [UNVERIFIED]** — nothing fetched, probed or installed by this session; the claims are vendor copy relayed by a search engine. Governing precedent named on the page: `sources/pyth-evaluation-2026-08-30`, where a vendor's "keyless" surface READ as usable and was REFUTED by runtime probe (metadata only; every real price 401/404), and the refuted claim was the page author's own from earlier the same session. The page argues the first question is NOT capability but the **trust boundary**: an stdio MCP server attached to this repo's sessions receives the agent's queries, and those queries carry context about a private trading codebase — `CLAUDE.md` invariant 4 and the endpoint deny-list govern what the BOT may reach and say nothing about what a SESSION's tooling may transmit, a gap no existing guard closes. Restraint precedent: the 2026-09-08 crypto-skill scout judged 11 sources and installed NOTHING. Two places it could legitimately help if it ever survives a probe, recorded so the option is not lost: **HYG-1** (measured 2026-09-10 — NO gate tool is version-pinned in any tracked file while the law requires pyright shipped-scope at zero, so an unpinned tool can move a gate with no diff) and dependency CVE/changelog review, which `bandit` does not cover (it scans our code, not our dependencies). **No adjudication, no install, no recommendation.** Next step if wanted, in this order: probe the free surface, then answer in writing what the stdio server receives.


## [2026-09-11] ingest | OF-5 armed and failed - the gate label was false, and the sample is 93% pre-cut-#10
Page: `sources/session-20260911-of5-dsr-reading`. Callout added to `concepts/overfit-battery` (its OF-5 DEFERRED line is superseded - the gate now grades). DSR returns P(true SR > sr0), not P(true SR > 0); sign reading PSR(SR*=0)=0.111. Gate MDE at n=30 is SR=0.506 (a real +0.24 book fails 92.5% of the time); CI spans zero on every route; n_eff=16.47 measured for the first time on this sample. signal_history.csv has NO exec_era column, so OF-5 pools eras by construction - 28 of 30 conviction trips predate cut #10, only 2 are era-9. Era-9 counts reconciled (10 wholly-inside / 19 any-leg / 2 conviction). Repo fix SAFE-class: label at 4 sites, psr_zero key, sign+corpus disclosure beside the verdict, 12 tests, 4/4 mutants caught. No floor or threshold moved; era-scoping OF-5 left as an OPERATOR decision.


## [2026-09-11] update | OPERATOR DECISION on OF-5: "Keep pooling" - and the red is now GUARDED
Supersedes the same-day ingest entry's closing line ("era-scoping OF-5 left as an OPERATOR decision"), which is now STALE. The operator ruled verbatim "Keep pooling": OF-5's sample definition is SETTLED, it stays pooled across execution eras, and its FAIL stays red. Follow-up instruction, verbatim: "Put something in place to make sure if it is regressive then it's not silenced." Answered with (a) a separately-named deployed-era regression sentinel in scripts/overfit_check.py - fires only on a DEMONSTRATED loss (95% upper bound on mean net PnL below zero), SE on effective n, era read live from core.fill_ledger.EXEC_ERA, DEFERS below 10 trips and reports INDETERMINATE rather than clean when blind; currently DEFERRED at n=0 because the 2 era-9 conviction trips are STRADDLERS and nothing is wholly inside - and (b) tests/test_of5_not_silenced.py, 11 anti-silencing pins, 11/11 mutation-caught. TWO of those pins were VACUOUS on the first pass (the 0.90 bar pin was satisfied by its own docstring - the-method's 'test pin satisfied by a comment' recurrence; the n_eff clamp pin could not reach its own defence) and a third apparent survivor was the MUTATION HARNESS replacing prose. Adversarial pass amended two consequence claims before they were filed: 'permanently red' is FALSE (the gate is escapable by evidence - sr0=k(N)/sqrt(n), legacy drag dilutes at 1/n) and the blast radius excludes the deploy updater (auto_update.py:488 lists overfit as ADVISORY, never vetoes). OPEN, not acted on: test_windows.bat now vetoes on a condition no change under test controls.

## [2026-09-13] ingest | the guards that failed open, the gauge that could not be read
Page: `sources/session-20260913-guard-failopen-and-gauge`. Callout added to `concepts/overfit-battery` (every pbo figure in its table is now a point estimate with an unquoted band).

**Three guard defects, one shape — a comparison silently answering False on a value nobody checked.** (a) A non-finite config value passed every range bound and approved a live entry with `cost=nan`; measured on a real PreTradeGate, baseline approved=False/54.300 vs impact_eta=NaN approved=TRUE/nan. Same shape as RP-052 (cut #10 B3) one subsystem over, and reachable by the repo's own tooling because `json.dumps` EMITS bare `NaN`. (b) The four HARD VETOES failed open on a non-finite THRESHOLD — and that is the live exposure, because `ml.exploration.enabled=True` means PT-041/PT-040 are bypassed by design in the lane era-9 entries use, leaving those vetoes as the last line: `max_data_staleness_ms=NaN` APPROVES a 1,000,000 ms stale book. (c) `float()` raises OverflowError on a 400-digit int, so `validate()` RAISED instead of reporting and every other finding was lost with it — regressing the property `1d7e9e5f` shipped by name. Each was closed as a CLASS, not as instances, because the 2026-09-11 `miss_cost_bps` fix had already enumerated four of five keys and left the fifth.

**(c) was found only by adversarially reviewing (a) and (b)** — and two of that review's three findings were MISATTRIBUTED on first pass: the crash blamed on the new sweep was in pre-existing code, and a "veto reordering" WARNING was moot because the gate cannot be constructed at all with the malformed input.

**OF-3 is discontinuous in the corpus size**, deterministically: 0.1857 at 18,018 rows, **0.9000 at 18,017**, 0.6286 at 18,010 — band 0.714 over ten rows, three of six readings each side of the gate; and re-measured that evening at T=18,043 the band was 0.186 with 0 of 6 RED, so the BAND itself decays with T. Quote neither the point nor the band; `scripts/pbo_row_sensitivity.py` is committed because the previous study's four harnesses died in a temp directory.

**The horizon lever is dead on its own evidence.** `horizon_shadow.csv` had doubled to 52,402 rows against the 23,826 config.json cites as the migration evidence, and nobody had re-read it: 45 of 45 asset×horizon cells negative, best-horizon split 5/6/4 over 15 assets against a 33% null. H=216's aggregate advantage is a pooling artifact. The n_eff route agrees independently (a 4× cut buys 1.47×, and is cohort-resetting).

**The shadow-labelling lane is not SAFE by construction** — four measured leak channels, of which GateStats is live and shading entries right now (`weighted_confidence` on the entry path, eight of nine weights off 1.0). The order path IS closed by an immutable symbol_map, so isolation reduces to never touching `trading_pairs`; but admitting one watch row into TRAINING is cohort-resetting on the day it happens. OPERATOR DECISION, not taken.

**Measurement-plane, silent until looked at:** the Grafana tile built to stop a second red hiding behind the first was itself hiding one (bare `max()` drops the `{{rung}}` label — the only defect whose wrong output an operator was looking at); `docs/HANDOFF.md` named a cohort closed three cuts earlier AND published six fence axes where CLAUDE.md publishes ten, omitting cut #11's own levers; and the era-currency scan could not see its own defect class because all four of its markers were lifted verbatim from the single sentence that motivated the file.

**Two false positives in this session's own harnesses, recorded because the harness is an instrument:** a mutation reported CAUGHT that was really pytest exit 5 (no tests collected), and a blast-radius scan missed 9 panels nested in collapsed rows. Every later mutation carries an exit-5 pre-check.

Tooling: `scripts/agent_brief.py` added after four hand-typed briefing blocks drifted — one carried corpus figures that were stale within the hour. It re-derives at call time, parses the ten-axis fence from CLAUDE.md rather than restating it (degrading CLOSED), and publishes n_eff as competing routes with a note that they disagree.

## [2026-09-13] ingest | the resume storm, the hook that could not see its own file, and a red that was mine

Page: `sources/session-20260913-resume-storm-and-hook`. Raw:
`raw/2026-09-13_resume_storm_hook_and_template_phase1.md`. Repo record:
`docs/quant/2026-09-13_resume_storm_and_hook_root_cause.md` sections 1-7.
`main` = `c189c462` at filing; bot pid 14112, the original 09-12 boot, never
restarted by any of this.

**A ~40-session resume storm moved HEAD inside the DEPLOY checkout.** At
19:53:17 a resumed session checked out a branch 148 commits behind, reverting
the working-tree config to cut #8's 40/80 fees; `pc_supervisor` hot-reloaded
onto that two-week-old code twenty-three seconds later and pushed stale
Grafana boards. The runner never restarted, so nothing reached the decision
path — **luck, not a guard**: the supervisor relaunches from the working tree
on a stale heartbeat, and a concurrent pytest battery is already known to
starve that heartbeat. The structural hazard is that the dev checkout and the
deploy checkout are the same directory. Also: **resumed transcripts are
re-stamped at resume time**, so "the latest message" must be ranked by session
activity, never by transcript timestamp.

**Every plugin hook had been failing on its own file, and two of my
explanations were wrong before the measurement settled it.** Real mechanism:
`AppData\Roaming\Claude` is the packaged app's MSIX write-virtualization
**overlay, visible only to descendants of `claude.exe`**, and the `python3`
app-execution alias launches the interpreter as a child WITHOUT it. A
correction to the shim's own comments: it does **not** fall through to `py -3`
— its version probe SUCCEEDS through the alias, so the failure is filesystem
view, not interpreter selection.

**The host fix was correct and INERT, and restarting was not the answer.** The
app's process tree predates the registry write by **63 min 45 s**, and Windows
cannot mutate a running process's environment. Activated with no restart and
no config edit by dropping `python3.exe` into a directory the hook shell's
PATH **already named** (Launcher, position 22, ahead of WindowsApps at 24),
because **bash resolves PATH at exec time**. The `~/bin` variant also worked
and was rejected: it would have put a user-writable directory ahead of
`system32` for every Git Bash process on the box. Mutation pair on the real
hook command: rc 2 with the ENOENT, rc 0 with metrics. **Read `skip_reason`,
not the rc** — 3 is the credential gate after a full load-parse-dispatch, **-2
is a stdin JSON decode failure**, and both print `rc 0, skipped: true`. The
planned SDK install was **refuted**: the installer returns `NOOP_VENV`, the
venv was already built.

**Two pytest failures reported as inherited reds on `main` were disproved and
are mine.** `gc_pusher` hardcodes its repo root and does not honour
`LB_OUTPUTS`; the fresh worktree had an empty `outputs/`; and the battery ran
pytest BEFORE the gate that generates the file those contract tests read.
Green in all three arms once the artifact existed. The inverse of
`concepts/host-state-dependent-green` — a host-state-dependent RED. The
battery's exit-code column was blank throughout because a PowerShell parameter
named `$args` shadowed the automatic variable; **the implausible runtime, not
the rc, is what exposed it.**

**Template-refactor phase 1 is filed as CANDIDATES, not findings.** 93 files,
84 blocks, 128 SAFE and 32 BOUNDARY items — with **zero refuter verdicts
delivered**, no scripts census, strategies+regime truncated at 4 of 13, and
main.py/runner.py/api/sentiment never inventoried. The one claim re-derived
four ways and CONFIRMED: **the long book prices fees at the venue's
zero-volume row** — `main.py:910` builds its tier engine from
`long_book.profit_taking`, which has no `est_fee_bps`, so the code defaults to
80 bps against the booked 30. Break-even ratchet 166 bps against 66, both
arming after tier 1; realized P&L understated 50 bps of closed notional per
partial close. **Fail-conservative in direction** and tier 1 triggers at +8%,
so it may never bind — whether it ever engaged is OWED. `config_guard`'s own
comment that "production never reaches ANY default" is **false for this path**;
its five dotted paths are all top-level. Not changed: cohort-resetting, now on
the HANDOFF docket.

`concepts/the-method` gains **measured recurrences 17 and 18** — the
instrument answering truthfully about a scope nobody asked about (five
instances in one session, including a `$'\r'` census that counted every line of
a pure-LF file, and a Bash call that ERRORED after already writing its target),
and the registry fix that could never reach a running process.

## [2026-09-13] correction | the hook fix reviewed itself and lost: a copied python.exe cannot find its own DLL

Amends the entry immediately above and `sources/session-20260913-resume-storm-and-hook` (new §7).
Filed against the finding's own interest, same session, per the currency rule.

**The activation artifact was wrong and is replaced.** §3 dropped a byte copy
of `python.exe`, named `python3.exe`, at the winning PATH position. **A copy of
`python.exe` outside its install directory cannot find `python314.dll` beside
itself.** It started only because `...\Programs\Python\Python314` happened to
sit on PATH; strip those entries and it dies at **exit -1073741515 =
`0xC0000135 STATUS_DLL_NOT_FOUND`** — carrying no message at all, strictly
worse than the readable `[Errno 2]` it replaced. Measured both ways. The
original fix had put the copy BESIDE `python.exe` for exactly this reason, and
relocating it to win the PATH race traded that property away without
re-checking. The write-up compounded it by calling the Python314 PATH entry
"redundant-but-harmless", which invites the cleanup that breaks it. **Ships now
as a two-line `/bin/sh` script naming the interpreter by ABSOLUTE PATH**,
verified rc 0 with `Python314` stripped from PATH entirely. Bonus: an
extensionless script is found by shells searching PATH for exact names (the
hooks' bash) and not by `cmd.exe`/PowerShell, so the redirect reaches one
consumer instead of every process. §3's MECHANISM is untouched and stands.

**Second erratum, in a commit message.** `c189c462` claimed *"the four suites
that read docs/ ... pass, 107 tests"*. There are **32** such files and **675**
tests; the four came from a `grep ... | head` read as a complete list. The
corrected run is green — 675 passed, 7 skipped, 1 xfailed, rc 0 — so nothing
shipped broken, but the claim was narrower than its evidence in the one place
that outlives the code. **Sixth instance of recurrence 17 in a single
session.** A companion instrument note: that run first returned **rc 1 with no
failing test**, from a pytest temp-dir teardown (`WinError 5` unlinking
`pytest-current`); `--basetemp` separates harness from result.

**And the thing nobody was looking for.** The plugin's own log has **no live
hook invocation before 20:31:48**, and that first entry is a manual probe.
`origin/main` took **18 commits on 2026-09-13** and **16 landed before the
fix** — including one self-labelled CRITICAL and four guard/validator changes.
The hook's state file now baselines at `c189c462`, so the backlog is never
reviewed retroactively. **The outage's real cost is that gap, not the
notification noise.** A manual pass over `4d58ad61..3f891c19` is OWED, not done.

`concepts/the-method` recurrence 18 gains clause **(c)**: a fix verified only
in the environment that motivated it is verified against one arm. Vary the
thing you did not change.

## [2026-09-13] correction | red-team panel: the hook fix restored DETECTION, not REVIEW

Amends the two entries above and `sources/session-20260913-resume-storm-and-hook` (new §8).
Five mandated-position panelists, 37 objections, 2 withdrawn, **18 surviving, 14 conceded outright + 3 in part**.
Docket and dispositions: `docs/quant/2026-09-13_resume_storm_and_hook_root_cause.md` §9.

**The headline inverts the previous entry.** It said 16 commits went
unreviewed. **No security review has ever completed on this box.**
`HAS_API_CREDENTIALS` is false (`hooks/llm.py:124-126`); all three review entry
points bail; the plugin log shows the author's OWN post-fix commits as
`detected git commit` → `LLM review disabled or no API credentials` (21:40,
21:44, 22:06); `.git/sg-reviewed-shas` is absent; `rev-list --count origin/main`
= **940**. The author had measured that gate — `skip_reason 3` IS it — named it
correctly, and then reported the hook as WORKING. **Both true, conjunction
false. Split INVOCATION restored from REVIEW ran.** What got fixed is the
notification storm.

**Two more inversions.** The shim DOES resolve in PowerShell (`Get-Command
python3 -All` lists it first) and left `$LASTEXITCODE` at the prior command's
value — a false-green generator and a regression, since PowerShell's `python3`
worked via the alias before; mitigated by a `python3.cmd` and re-measured.
And the long-book row's BOTH consequences were wrong: `TierAction.realized_pnl`
has 2 attribute reads repo-wide, both tests, so "reports realized P&L
understated" is RETRACTED; and "fail-conservative, never tightens" is INVERTED
by enumeration — 224 of 960 states install a different stop, 6 of 8 one-tick
paths give a different EXIT, and the shipped 80 bps leaves the position
UNPROTECTED through a band the booked 30 would have closed at break-even. The
same false sentence is in SHIPPED CODE at `risk/profit_tiers.py:240-242` and
half of it at `core/config_guard.py:881-882`.

**Instrument limit neither side named:** `outputs/gc_pusher.log` has no date
field and spans multiple days, so nothing in it can be attributed to a date by
that route alone. `concepts/the-method` recurrence 18 gains clause **(d)**.

## [2026-09-15] ingest | two SAFE fixes shipped, and SEVEN defects found in the session's own new code

Operator authorised items 1 and 2 of the survey's ranked list ("Do this"). Both landed:
`06b9ca1c` (watch-lane pending-pool persistence) and `56fdcd96` (OF-7 reports EFFECTIVE n).
Full record: [[sources/session-20260915-master-survey-and-double-exit]] §11–§16.

**The headline measurement.** OF-7 — the one battery rung built to catch an under-determined
model — gates on rows/feature against a floor of 10 and computes it on NOMINAL rows, over
labels that overlap by construction. Read twice on a growing live corpus: **19,203 rows →
nominal 300.05 / effective 0.98 / n_eff 62.5 / SE ×17.53**, and **19,204 → 300.06 / 0.97 /
62.4 / ×17.55**. As-of readings, not constants; the invariant is that the gate's number and the
honest one are **two orders of magnitude apart**, in the direction that makes a green
meaningless. The n_eff independently reproduces the ~63 pooled figure a different route reached
the same day. **The gate itself was NOT re-pointed** — a pin asserts the verdict does not move,
because re-aiming a pre-registered gate after seeing the data is the widening CLAUDE.md forbids.

**Seven defects, all in code written this session, none found by reading the diff:**

1. A pin asserting a **production** path was ABSENT — would have gone red the day it shipped and
   then blamed the test for the bot working.
2. An unread module constant holding a production path — bait for the 12th QA-writes-production
   instance, since conftest redirects only REGISTERED names. Deleted before shipping.
3. A **decorative** atomicity pin — "no `.tmp` left" + "parses", both satisfied by a plain
   `open(p,"w")`; deleting the whole atomic-write block passed all 29 tests.
4. A **mutation harness that never ran** and reported 4/4 — [[concepts/false-green]] design
   rule 15.
5. A **cubic-complexity helper** reused because it was already imported: ~1.4e13 ops on the
   19k-row corpus, wedged the battery 16 minutes. Canonical bar-grid route: 3.4e6 ops, 0.76 s.
6. A fixture **wrong about bar quantisation** (the 300 s grid makes 100 s-spaced labels
   concurrent) — the helper was right, the fixture was wrong.
7. A **report-only line that CRASHED THE GATE IT REPORTS ON**: `load_dataset`'s synthetic path
   returns `sig=res=None`, `len(None)` raised outside the try, 8 suite tests red.

Rules bought: [[concepts/false-green]] **design rule 15** (a sweep must assert an unmutated
CONTROL green before reporting any mutant) and **design rule 16** (a sweep that plants a
production-path mutant PERFORMS that write — the tripwire is a detector, not a janitor).

**And a false claim was removed from SHIPPED CODE before it shipped.** `_load_state`'s docstring
asserted "the lane had written 12 rows in total", carried in from a workflow summary and never
re-derived. Refuted the same night by two routes (live snapshot `rows_labeled` **217** at
00:34Z, `outputs/watch_history.csv` **224** — which disagree with each other by 9 and with 12 by
two orders of magnitude). The docstring now carries the MECHANISM argument, which needs no
count, and tells the next reader not to re-cite 12.

**Gate on the committed tree:** pytest 5475 passed / 9 skipped / 1 xfailed (rc 0); smoke 220/0;
assurance 51/0; ruff clean; pyright shipped 0; bandit 0; compileall clean. `overfit_check` exits
**1** on OF-5 DSR — armed and failing since [2026-09-11] under the operator's "Keep pooling"
ruling, shown not-mine two ways. Live bot untouched: DRY_RUN, ARMED, no faults, `force_dry.on`
present. **7 commits ahead of origin, push HELD.**

## [2026-09-16] ingest | the bot is SAFE and is not running the experiment the law describes

Operator: "do the work to fix all of it and look at how the bot has been firing to make sure it's
been doing what it is supposed to do or what our theory is to become." Two 16/17-agent fan-outs,
every lane adversarially verified. Five commits: `3a354e43` `c0ef265d` `2f09e369` `e0b790c0`
`2ae7b3df`. Full record: [[sources/session-20260915-master-survey-and-double-exit]] §17.

**THE CLEAN BILL, established in both directions.** ZERO of the seven hard invariants breached.
1,340/1,340 legs ever written are LIMIT orders; hedger off; universe exactly the four configured
pairs; `dry_run` true with its sentinel on all 482 session starts; 0 `VN-*` in 89,254 audit
records. **Six claimed breaches were adjudicated and all six FELL.** The machine obeys its
configuration exactly. What is wrong is the LAW describing a machine that changed underneath it.

**THE CRUX, and it is arithmetic over the shipped config — no sample size, no sampling error.**
The label's profit target is **1.80%**, its stop **1.35%**. The give-back overlay arms at
**0.75%** and locks **0.60 of peak**, so banking a 1.80% win *through the trail* needs a peak of
**3.00%** — while the bracket's profit leg fires the instant price touches 1.80%. **The trail can
NEVER pay a labelled-PT-sized win while the bracket is armed.** Ledger: 12 era-12 trips exited
"tier trail" at mean **+$0.1439** (12/12 wins), 12 closed at "tb_sl" at mean **−$1.5263** (0/12) —
**10.6:1**, needing a 91.4% win rate against 43.8% observed. And **47.4%** of era-12 live closes
are filed `barrier='realized'`/`label_era='exit_sim'` and dropped by the training filter.

**THE MODEL IS DECORATIVE.** Every era-12 5m entry is an exploration probe at a substituted
`p_win` of 0.85 with both profit gates bypassed, and the model's own calibrated number **cannot
reach 0.85** at the shipped shrinkage (it would need p > 1.0). No retrain changes which trades are
taken. The cohort is a seeded control arm.

**NOT ESTABLISHED, and it cuts against the alarming reading:** at n=20 resolved live trips the
live-vs-candidate gap is NOT statistically separated (Wilson [2.8%, 30.1%]). "The overlay censored
a winner" and "the market never offered one" remain the same observation. Settled: the structural
truncation and the training-corpus loss. Unsettled: the dollar cost.

**SHIPPED.** `scripts/discard_ledger.py` — the missing aggregator (34.8% of rows discarded, 75
live labels surviving, 77.9% of stamped trips refused, 86.7% of the corpus under a retired cost).
OF-7 now prints the effective-n **PAIR** (0.98 asset-blind vs 25.63 per-asset, **x26.1**), which
CORRECTS a single figure shipped the day before. The readout discloses all three findings beside
its own verdict. CLAUDE.md now **prices a mint** with a 14-day floor. A false auditability claim
left `execution/pretrade.py`.

**FOUR DEFECTS IN MY OWN NEW CODE, all found by running it.** Two planes of the discard ledger
reproduced numbers a verification pass had refuted the SAME DAY (a lifetime-denominator error and
a tolerance-dependent staleness share) — I wrote the caveat against both into the docstring and
violated it in the same file. Two mutation harnesses lied: `[] or [...]` is a NO-OP because `[]`
is falsy ([[concepts/the-method]]'s "a green mutation is a claim about the MUTANT first"), and a
backslash-n inside a heredoc collapsed to a literal — **three times in one session**, each already
written down in memory. Harnesses now assert the mutant changed the bytes before trusting it.

**PLANE 3 OVERTURNED BOTH EARLIER ROUTES.** `barrier_geometry` floors `pt_frac` at exactly
0.018000 and **ZERO rows sit there** — the minimum is 0.0180030 with 1,433 rows in a band 1e-4
wide, because 5m crypto sigma sits right AT cost/2 as CLAUDE.md says. Floor-bound vs sigma-bound
is therefore NOT separable from `pt_frac`; two defensible tolerances gave 34.8% and 82.9%. The
ledger now partitions by DATE, which needs no tolerance and proves itself disjoint.

**Gate:** pytest 5497 passed / 9 skipped / 1 xfailed; smoke 220/0; assurance 51/0; ruff clean;
pyright shipped 0; bandit 0; compileall clean. `overfit_check` exits **1 on TWO rungs** — OF-5 DSR
(settled 09-11) and now OF-3 PBO, which moved **0.41 → 0.80 while the corpus grew 2%**; PBO is
seeded and deterministic, so that is ~400 rows moving a registered gate by nearly double. Neither
is fixable by widening a gate. Live bot untouched: DRY_RUN, ARMED, no faults, sentinel present,
net −$27.87 on $772.13. **12 commits ahead of origin, push HELD.**

## [2026-09-18] update | law audit D1-D6 applied; D5 mint-price derivation registered as owed measurement
`liquiditybot_ab/docs/quant/2026-09-17_law_audit.md` §7 rewritten to mark D1-D4 and D6 as applied in commit `4c25d22e`; D5 re-labelled as open and routed to `synthesis/owed-measurements` item 121 (MINT-PRICE-1). No engine/config/outputs files touched. Pages touched: `docs/quant/2026-09-17_law_audit.md`, `synthesis/owed-measurements.md`, `log.md`.

## [2026-09-18] update | comparability-boundaries gains cuts #10-#12; the-method recurrence count corrected
Rows 10 (10-a5acfe2d, E1 legacy-ladder re-book), 11 (11-6e584923, COMMIT configuration), 12 (12-10d4d0c2, FEE-4 15/30 Tier 5, live 2026-09-08T23:47:45Z) appended to synthesis/comparability-boundaries from HANDOFF ERA-9 + the 2026-09-08 cut-12 adjudication doc (both re-verified against config.json and ml/labeling.barrier_geometry in the 2026-09-17 law audit: PT 180/SL 135, derived bar 0.6381, BE floor 66bps all reproduce). Numbers on the new rows are AS-OF-HANDOFF. concepts/the-method frontmatter corrected: register summary said THIRTEEN, the body has TWENTY-TWO (added #14-22 one-line shapes, 2026-09-13..15). Pages touched: synthesis/comparability-boundaries, concepts/the-method, log.md. Filed by a Kimi Code session (operator-present, auto-approved).

## [2026-09-26] ingest | Kimi review + remote plane + SAFE batch
New source page sources/session-20260926-kimi-review-and-remote-plane; raw artifacts raw/audits/2026-09-26_kimi_review/ (36 files: reviewer diffs, pin tests, probes). Findings are [K] with mutation/injection evidence; held items (F1, R3, R2, C5, cohort redefinition) await operator ruling.

## [2026-09-28] update | cut #13 live — decision-fingerprint cohorts
sources/session-20260926-kimi-review-and-remote-plane gains the cut-13 section: live 2026-09-28T03:33:40Z, decision_fp 0f773bf5fc67, ledger migrated with backup, first fills stamped. Exit replay filed under raw/audits/2026-09-26_kimi_review/exit_replay/ (no exit geometry clears p*).

## [2026-09-28] update | C5 live + probe lane resolved
C5 (auto-retrain heavy half off the engine thread; stops never wait on training) shipped fca6e745c, live 2026-09-28T14:15:57Z, decision_fp 75e19fa38ffb (forked from 0f773bf5fc67: config gains ml.auto_retrain_async, code changed; NOT pooled - removing the 21-28 s stop-loop pause changes exit timing). Probe lane resolved: keep exploring (exits ruled out by the replay; entry-signal work waits on the 08-10 model freeze). Scratch reviewer worktree removed.

## [2026-09-29] update | counting standard CS-1 + adversarial-review fixes live
Adversarial review of "nothing to fix" found the cut-13 fingerprint migration incomplete (5 readers pooled forks into era-9). Fixed + root-caused by CS-1 (repo docs/law/counting_standard.md): one vocabulary, attribution only via core/cohort.py (entry leg; main-chain boot timeline), reconcile() lines (live 100/201/603 OK), conformance pin. W1 atomic load stats; W2 deploy half measured ~0.2 s; W4 darkpool mirror promoted into outputs/darkpool (sha256 cb0b57ac..., byte-identical) + out-of-repo refusal + QA redirect (QA runs had read the live mirror); W3 closed (Grafana stall = prod-us-east-3 incident, before/after probes). main 52c3ced72, live 2026-09-29T13:56:24Z, decision_fp 281334f23604.

## [2026-09-29] update | model freeze LIFTED (operator ruling)
Operator: "Lift the model freeze" - supersedes the 2026-08-10 adjudication. Law updated at every site (repo commit 6fb3ee585, docs only, no cohort fork). Guardrails kept: overfit_discipline.md gates, cohort forking for feature/schema changes, CS-1, no retuning on a cohort's own accruing gate numbers. Entry-signal work is now the open lever (exit geometry was ruled out by the 2026-09-27 replay).

## [2026-09-29] update | model program 1-3 live
Model freeze lifted; plan revised before building (exit_policy labels = the 2026-07-26-rejected mode, not re-run). 1a bracket geometry = label geometry via ml.labeling.label_cost_pct (measured gap labels 181/136 vs trades 200/151 bps). 1b+3 shadow traded-value rule: ml/shadow_policy.py + scripts/shadow_policy_report.py (walk-forward, no look-ahead, CS-1), promotion via docs/law/shadow_policy_promotion.md; first live shadow row 18:34Z (PAXG long p=0.490). 2 feature screen (label-span 432): 58-66/68 features dead OOS per combo, 5 dead on all 43 dates - the lever is new information. main 40658e15d, live 2026-09-29T18:32:06Z, decision_fp 6709bb74df3e. Record: repo docs/quant/2026-09-29_model_program_decision_record.md.

## [2026-09-29] ingest | Markov-modulated Brownian edge, walk-forward (SAFE, research only)
Operator: directional edges vs their formulas; a Markov chain forming the best solutions; Brownian theory; walk-forward; porcelain hands. Built ml/markov_edge.py + scripts/markov_edge_report.py + tests (37, mutation 7/7 vs green control). Registered run (snapshot 2026-09-29T20:10:58Z, 200 null reps): no spec beats psi=0 out of sample; day-level trend dominates; basis weak within-day rank only; chain dilutes. Nothing wired, no cohort fork. Source: sources/session-20260929-markov-brownian-edge; raw: raw/2026-09-29_markov_brownian_edge_walkforward.md; repo docs/quant/2026-09-29_markov_brownian_edge_report.md.

## [2026-09-30] update | Markov edge report CORRECTED - test-side censoring
Rows land only when labels resolve, so test days younger than day_end + 36 h were censored (run 1 scored 09-28/09-29). Fixed with a maturity rule, re-run on the same snapshot: conclusions stand; chained dislocation ranks backwards OOS. Callout on sources/session-20260929-markov-brownian-edge (both sides); raw/2026-09-30_markov_brownian_edge_walkforward_corrected.md. Forward-registered operator spec (regime x vol) first matures 2026-10-02T12:00Z.

## [2026-09-30] ingest | TE-1 trip explanations + candle tape recovery + Markov power
Operator: PnL and its why must be apparent per trip, bot-readable. Built scripts/trip_explain.py -> outputs/trip_explanations.jsonl (TE-1). Found the 5m collector never scheduled; recovered 32,400 bars. Power run showed the Markov report's gain metric blind under day-level drift. Source: sources/session-20260930-trip-explanations-te1; repo docs/quant/2026-09-30_trip_explanations_te1.md.

## [2026-09-30] ingest | pipeline congruence + one-writer corpus fix (cohort fork)
Operator: is the corpus congruent with the rows it attained; configure it to run smoothly and not duplicate. Values exact on every re-derivation; duplicates traced to losing runners; one-writer rule + exact dedup + CS-1 counters shipped on the branch (fork 6709bb74df3e -> 6709bb58cd7c). Drift share shown to be an autocorrelation artifact by an in-sample null (raw/2026-09-30_drift_share_in_sample_null.md). Source: sources/session-20260930-pipeline-congruence.

## [2026-09-30] update | drift calibrated + candle collector scheduled + 5m hole closed
Operator 'Execute 1 and 2'. (1) Calibrated drift monitor shipped (fork 6709bbc2778d): per-feature in-sample consecutive-window null; legacy flags 13.3 vs 13.1 features with/without a regime change, calibrated 1.8 vs 6.0. (2) Collector rides pc_supervisor every 6 h (S4U task refused without elevation); trade-tape backfill + tape_to_candles closed 09-07..09-23. TE-1 re-run: all 97 era-9 trips split. Callout on sources/session-20260930-trip-explanations-te1. Record: repo docs/quant/2026-09-30_drift_calibration_decision_record.md.

## [2026-10-01] ingest | new information + path-overlap bias + conviction evidence + US regulation
Operator 'Yes' (screen + regulation during the hold) and 'derive new information for conviction labels'. All SAFE, no fork. Within-day AUC bias found and corrected (callout on session-20260929-markov-brownian-edge). shadow_policy_report join bug fixed. Regulation corpus in repo docs/research/regulation/. Source: sources/session-20261001-new-information-and-conviction.

## [2026-10-03] measure | owed 69 closed NULL — anti-momentum pattern
Operator 'continue with the 37% phenomena'. Re-measured on a 2026-10-03T23:35:20Z snapshot (n=25,840, read-only). Gap against−with +1.6% [−3.0, +6.2]; scramble/plant validation passed; CS-1 reconcile OK. Callout on synthesis/owed-measurements item 69. Source: sources/session-20261003-owed69-remeasure. Raw: raw/2026-10-03_owed69_momentum_alignment_remeasure.md.

## [2026-10-05] measure | model vs August champion — paired OOS, no detectable improvement
Operator: 'Is the model better now than before? August'. Paired loss differential on 4,948 rows after 2026-09-23 (13 days), snapshot 2026-10-05T17:57:31Z, read-only. August-minus-today Brier +0.0053 [-0.0050, +0.0164]; neither beats the base rate. Literature verified: Campbell & Thompson 2008, Diebold & Mariano 1995, Politis & Romano 1994. Source: sources/session-20261005-model-vs-august. Raw: raw/2026-10-05_model_vs_august_paired_oos.md.

## [2026-10-05] measure | power of the August-vs-today test + learning curve
Operator: 'future test those 60 days in our own simulation'. Simulated the measurement, not the market: 80% power needs ~106 days at the observed gap (57% at 60d) - corrects the same-day ~60d estimate. Learning curve flat (10.5k->26.3k rows). Addendum on sources/session-20261005-model-vs-august.
