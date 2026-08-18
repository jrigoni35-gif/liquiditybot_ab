# Plan: multi-route learning panel (SAFE class — measurement only)

## Context

Operator request (2026-08-18): "make the bot simultaneously understand
things faster in the same manner it is now … taking more routes to
learning more effectively," explicitly inside the repo's parameters and
safety nets.

What the law permits today: CLAUDE.md freezes model-side investment (no
new families, features, meta-labeling) until the era-4 gate readout, and
the era-4 moratorium forbids any change to which orders are placed or how
they fill. docs/research/2026-07-23_tradingagents_gap.md already
adjudicated multi-agent LLM debate architectures: LLM-in-engine is
REJECT; the adoptable surface is offline measurement/reporting.

The repo therefore already HAS many "routes to learning" — ~14 report-only
lenses (lessons_digest, cohort_eval, gate_truth_report, cost_attribution,
interpret_report, …), each answering one question, each run by hand, one
at a time. The gap is orchestration: no single command runs every lens
simultaneously and produces one consolidated learning panel. That is what
ships here. Measurement only: zero engine imports, zero decision-path
effects, zero new model surface.

## Global constraints (binding, verbatim from repo law)

- SAFE class only: "measurement/report tools, dashboards, tests, wiki,
  telemetry export" — this tool must not alter which orders are placed or
  how they fill, and must not touch config, state, or the model registry.
- No new `core/codes.py` codes: this tool emits no dispositions into the
  decision path; it is an offline report like assurance_check.
- No bare `print` restriction applies to engine/runner/library code —
  scripts' human output is fine (CLAUDE.md).
- Windows is the target runtime: `pathlib` paths, explicit `encoding=`,
  and the no-console-popup pattern (`creationflags=0x08000000` on nt,
  `0` on POSIX — see `scripts/auto_update.py` `_NOWIN`).
- Subprocess calls are fixed argv, never shell; mark `# nosec B603` in the
  style of `scripts/auto_update.py`.
- Output paths must be REBINDABLE module attributes (the LOG_PATH lesson,
  2026-07-31): tests monkeypatch them; tests must never write production
  `outputs/` (tests/conftest.py enforces).
- New behavior gets a test in the same commit. Every module imports in
  isolation.
- Fail-safe throughout: one route's failure (crash, timeout, missing
  input data) must never kill the panel or another route.

## Task 1 — `scripts/learning_panel.py` + `tests/test_learning_panel.py`

New script, stdlib-only imports (argparse, concurrent.futures, dataclasses
or plain dicts, json, os, subprocess, sys, time, pathlib). No repo-module
imports (keeps import-integrity trivial and avoids engine side effects).

### Route registry

Module-level tuple `ROUTES` of entries with fields:
`name`, `script` (path relative to `scripts/`), `timeout_sec`.

| name | script | timeout_sec |
|---|---|---|
| lessons_digest | lessons_digest.py | 300 |
| asset_learning | asset_learning_report.py | 300 |
| learning_curve | learning_curve.py | 900 |
| cohort_eval | cohort_eval.py | 300 |
| gate_truth | gate_truth_report.py | 600 |
| gate_efficacy | gate_efficacy_report.py | 600 |
| cost_attribution | cost_attribution.py | 300 |
| cost_truth | cost_truth_report.py | 300 |
| corpus_linkage | corpus_linkage_report.py | 900 |
| feature_stability | feature_stability.py | 900 |
| horizon | horizon_report.py | 300 |
| fill_hazard | fill_hazard_report.py | 300 |
| defensive_cadence | defensive_cadence_report.py | 300 |
| interpret | interpret_report.py | 900 |

All 14 are documented report-only in their own docstrings. Argv is built
as `[sys.executable, str(SCRIPTS_DIR / entry.script)]` — no extra flags
(each tool's no-arg invocation is its documented default).

### Orchestrator

- `run_panel(only: list[str] | None = None) -> dict`: runs the selected
  routes concurrently via `ThreadPoolExecutor(max_workers=min(n_routes,
  max(2, (os.cpu_count() or 4) - 1)))`, each in its own subprocess with
  `capture_output=True, text=True, encoding="utf-8", errors="replace"`,
  per-route timeout, `creationflags=_NOWIN`, cwd=repo root.
- Per-route result: `{name, status, rc, duration_sec, head, tail}` where
  `status` ∈ `OK` (rc==0) / `FAILED` (rc!=0) / `TIMEOUT`
  (TimeoutExpired) / `ERROR` (any other exception, message captured);
  `head` = first 3 non-empty stdout lines, `tail` = last 15 stdout lines
  (stderr tail appended on non-OK). Never raises out of a route.
- Panel result dict: `{generated_at (time.time()), git_head (best-effort
  `git rev-parse --short HEAD`, "" on failure), routes: [...],
  counts: {ok, failed, timeout, error}}`.

### Output

Rebindable module attrs `PANEL_MD = OUT / "learning_panel.md"`,
`PANEL_JSON = OUT / "learning_panel.json"` with `OUT = ROOT / "outputs"`.
`write_panel(result)` writes both, `encoding="utf-8"`, atomic tmp +
`os.replace` for the JSON. The MD leads with:

1. a header line: route counts by status + total duration;
2. the standing epistemic caveat, verbatim: "A green is only as big as
   its corpus — each route's own output states what it actually measured;
   a route that degraded honestly answers a different question.";
3. one section per route: status, duration, and the tail excerpt in a
   fenced block.

### CLI

`--list` (print route names, exit 0), `--only a,b,c` (subset; unknown
name = exit 2 with message), `--json` (print the JSON to stdout as well).
Exit code: 0 when the panel files were written (even with failed routes —
the panel REPORTS failure, it does not fail on it), 1 only when the panel
itself could not be written.

### Tests (same commit)

- Registry: names unique; every `script` file exists under `scripts/`;
  timeouts positive.
- Isolation: monkeypatch `subprocess.run` so route A returns rc 0 with
  stdout, route B returns rc 1, route C raises `TimeoutExpired`, route D
  raises OSError → panel completes, four statuses OK/FAILED/TIMEOUT/ERROR,
  both files written to a tmp-rebased `PANEL_MD`/`PANEL_JSON`.
- `--only` with an unknown route name exits 2.
- JSON output parses; MD contains every selected route name and the
  caveat sentence.
- No production writes: all tests rebind `PANEL_MD`/`PANEL_JSON` (and any
  log path) to tmp_path.

### Definition of done for the task

`python -m pytest tests/test_learning_panel.py -q` green, plus targeted:
`ruff check scripts/learning_panel.py tests/test_learning_panel.py`,
`python -m compileall -q scripts/learning_panel.py`, and a live smoke:
`python scripts/learning_panel.py --only cohort_eval` writes both panel
files (route may be OK or FAILED depending on local data — both are
acceptable; the panel must be written either way).

## Task 2 — `docs/learning/2026-08-18_multi_route_learning.md` (controller-authored)

Records the adjudication mapping of the operator request: what shipped
(the panel), what is barred and why (LLM-in-engine REJECT per the
2026-07-23 adoption ledger; model freeze per the 2026-08-10 adjudication;
cohort-resetting classes per the era-4 moratorium), and the post-readout
pathway (ALGO-5 is the pre-named next adjudication). Doc only, no code.

## Out of scope (explicitly NOT in this plan)

Bull/Bear LLM debate agents, DRL execution, RAG grounding, patch-based
Transformers, any new ML feature/family/meta-label, any change to entry
decisioning, sizing, stop/exit geometry, fill simulation, fee booking, or
order lifecycle. These are frozen/rejected under current law; the design
doc names the door they would re-enter through (operator adjudication at
the era-4 gate readout).
