# Fix-wave brief — veto-efficacy telemetry chain (adjudicated findings vs a94b5751)

Feature scope: scripts/gate_efficacy_report.py (core) + consumers scripts/gc_pusher.py, scripts/build_trading_dashboard.py (+ built artifact docs/grafana/liquiditybot_problem_solution.json), scripts/learning_panel.py (verified unaffected — confirm during trace), tests/test_veto_quality.py, tests/test_boards_stripped.py, docs/HANDOFF.md.
All findings below came from three independent review lenses with file:line evidence and (mostly) runtime verification. They are still CLAIMS — re-verify each cheaply during your TRACE/DIAGNOSE phases before fixing (instrument-first).

## CRITICAL (fix in this order: deps → types → logic → tests → integration)

C1 (F1+F9) — `_era_overlap_frac` is one-directional membership-set overlap: a single contaminating baseline row of a code's era reads overlap 1.0 (guard silenced); and the 0.05 floor is a cliff — a 94.9%-disjoint sample escapes with full unflagged significance. The repo's own right abstraction: `_reason_mix_tvd` (ml/history.py:461-480, symmetric, weight-aware). REQUIRED OUTCOME: both failure modes die — (i) single-row contamination cannot unfire the guard, (ii) majority-incomparable evidence cannot print an unflagged verdict. Candidate designs (you pick, justify in the report): (a) weighted overlap = Σ_e min(p_code(e), p_base(e)) with a majority floor + explicit PARTIAL_OVERLAP intermediate state; (b) era-matched subsample comparison (significance computed only on shared-era rows; CONFOUNDED when shared-era n too small). Injection tests for BOTH failure modes in the same commit.

C2 (F4) — the headline "Does the gate select?" admitted-vs-baseline separation verdict (render() ~:461-475, efficacy() :238-240) never touches the confound guard — the exact defect species the patch fixed, unfixed in the file's most prominent claim. Apply the same guard to adm-vs-base; test it.

C3 (F8+F12) — `_row_era` fallback (:93-102) calls un-horizon-aware `label_era_of`, the documented era-mixing defect class (see ml/history.py:395-398 docstring, migrate_history.py:125-132 incident). And LABEL_ERA_UNKNOWN counts as shared overlap (:109-117) though it means "unclassifiable", not "same label definition". Fix: fallback rows that would land plain "triple_barrier" without horizon knowledge go to UNKNOWN (or horizon-qualify if the row carries it); UNKNOWN is excluded from shared-overlap credit on BOTH sides (counts toward incomparable weight). Tests for both.

C4 (F2+F10) — `comparison` conflates "effective-n vetted null" with "n_eff uncomputable, nominal-n guess" (:300-305 vs :319-329). Extend (never rename): distinct comparison value (e.g. not_significant_nominal_n) or explicit disclosure; mirror per-disposition's `anti_selective_nominal` distinction. Test.

C5 (F5, = minor #6) — gc_pusher.py `_run_veto_quality` (:1271-1317) drops era_overlap/comparison/confounded_baseline: glass cannot distinguish CONFOUNDED from not-significant — the two states the patch exists to separate. Add gauge(s) (e.g. liquiditybot_veto_confounded per code, and/or era_overlap value) — EXTEND metric set, never rename existing keys. Update tests/test_boards_stripped.py pins accordingly.

C6 (F6+F7) — build_trading_dashboard.py:1798-1809 "Anti-selective gates" panel desc still asserts SZ-021 "measurable harm ... 0.51 against a 0.27 baseline" — now false (that read is confounded); baked into checked-in docs/grafana/liquiditybot_problem_solution.json:3868-3869. Fix desc (dated, both sides: 08-26 read + 08-27 confound caveat), REBUILD the JSON artifact via its build script, and add a pin so a desc-level staleness of this panel can't ship silently again (e.g. pin a substring of the corrected desc).

C7 (F3, TWO-LENS PROMOTED) — docs/HANDOFF.md:153-154 overclaims: per-rule markdown does NOT carry `comparison: "CONFOUNDED_BASELINE"` (only by_code JSON does; per-disposition dicts use confounded_baseline bool + era_overlap float; render() emits prose). Fix BOTH sides: unify the code so per-disposition rows also emit the `comparison` field (extend), AND correct the HANDOFF sentence to name exactly where each surface shows the verdict.

## IMPORTANT
I1 (F11) — no test pins cross-variant era pooling (`era_mix_by_code[...].update(...)` :293): `.update`→`=` regression passes green today. Add the one-code-two-variants-different-eras test.
I2 (minor #2) — boundary numbering drift: HANDOFF OPEN DOCKET calls FEE-1+FEE-2 "Boundary #6" (08-22 sections) while WHY-1 and the ca55e2ba commit + scripts/fee_reprice.py docstring say "boundary #5" (and the docstring bundles ALGO-5 into #5 while WHY-1 lists it separately). Reconcile to ONE numbering in docs + docstring; if genuinely ambiguous which is canonical, flag AMBIGUOUS in your report and change only the internally-contradictory doc lines, not adjudication semantics.
I3 (minor #1) — 8a9cc087's commit message overclaims its verification (claims 13 new pins, actual 12; falsely lists tests/test_migrate_history.py among updated pins — zero diff there; likely confusion with test_history_migration.py). History is pushed — do NOT amend. Add a one-line correction where permanent claims get corrected (a dated line in docs/HANDOFF.md RECENTLY SETTLED or a docs note near the labels change), so the false tally can't be cited as settled.
I4 (minor #4) — document (comment) that the era-overlap weighting choice considered n_eff-weighting; one line at the definition.
I5 (minor #5) — pin `_row_era` precedence against ml.history's `_row_label_era` (drift in the latter's precedence order is currently uncaught). Cheap structural test (import both, feed rows exercising persisted-vs-fallback precedence, assert equal) — subsumes into C3's tests if you unify the helper instead (preferred if clean: import/reuse rather than duplicate).

## OUT OF SCOPE (do not touch)
- Minor #3 (boundary5_stage.py regression test) — different feature, stays on backlog for final review triage.
- Minor #8 (test_fee_reconciliation order-dependent flake) — pre-existing, separate root cause.
- Anything cohort-resetting: no engine/decision-path file, nothing that changes which orders are placed or how they fill. Everything above is measurement/report/docs plane — keep it that way.
- learning_panel.py (verified structurally unaffected — confirm, don't modify).

## Constraints (binding)
- Interpreter ./.venv/Scripts/python.exe. No writes to outputs/ production files (tmp_path tests fine; dashboard build writes docs/grafana/ — allowed).
- Grafana metric families and JSON report keys: EXTEND, never rename (boards + checkin.py consume them; grep consumers before changing any key).
- Mutation-verify the load-bearing fixes: break each guard once, watch its new pin go red, restore.
- Ruff green on touched files; pyright: scripts/tests outside gate but keep clean; run the covering suites (test_veto_quality, test_boards_stripped, test_gc_pusher_owed_metrics) + any suite covering build_trading_dashboard.
- ONE commit (or two if code vs docs separation is cleaner), local, current branch, no push. Terse message claiming only what you ran. End commit msg: Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
- Report: append full fix log (per-phase, per-fix, with commands + exact test counts + mutation evidence) to this file's directory as fixwave-report.md. Return ONLY: STATUS, commit SHA(s), one-line test summary, concerns.
