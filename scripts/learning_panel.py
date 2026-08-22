"""scripts/learning_panel.py — concurrent multi-route learning panel.

SAFE class (measurement/report tool, CLAUDE.md era-4 moratorium): the repo
already has ~14 report-only "learning lens" scripts (lessons_digest,
cohort_eval, gate_truth_report, ...), each answering one question, each run
by hand, one at a time. This orchestrator runs the selected subset
CONCURRENTLY as subprocesses and writes one consolidated panel. It imports
nothing from the engine, touches no config/state/model registry, and emits
no core/codes.py disposition — it only shells out to scripts that already
exist and reports what they printed. A route crashing, timing out, or
exiting nonzero is itself the finding this tool exists to surface, so no
route's failure may take down the panel or another route (fail-safe
throughout, same discipline as scripts/auto_update.py).

    python scripts/learning_panel.py                  # run every route
    python scripts/learning_panel.py --list            # print route names
    python scripts/learning_panel.py --only cohort_eval,gate_truth
    python scripts/learning_panel.py --json             # also print JSON
"""
import argparse
import json
import os
import subprocess  # nosec B404 - fixed argv, no shell
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
OUT = ROOT / "outputs"

# Rebindable for tests (LOG_PATH pattern, scripts/auto_update.py): production
# reads these defaults; tests/conftest.py's outputs-write guard fails any
# test that leaves them pointed at the real outputs/ tree, so tests
# monkeypatch both to tmp_path.
PANEL_MD = OUT / "learning_panel.md"
PANEL_JSON = OUT / "learning_panel.json"

CAVEAT = (
    "A green is only as big as its corpus — each route's own output "
    "states what it actually measured; a route that degraded honestly "
    "answers a different question."
)


@dataclass(frozen=True)
class Route:
    name: str
    script: str
    timeout_sec: float


# Every entry here is an existing report-only lens (each documents
# SAFE/report-only in its own module docstring). No-arg invocation is each
# tool's documented default — this orchestrator adds no flags.
ROUTES: tuple[Route, ...] = (
    Route("lessons_digest", "lessons_digest.py", 300),
    Route("asset_learning", "asset_learning_report.py", 300),
    Route("learning_curve", "learning_curve.py", 900),
    Route("cohort_eval", "cohort_eval.py", 300),
    Route("gate_truth", "gate_truth_report.py", 600),
    Route("gate_efficacy", "gate_efficacy_report.py", 600),
    Route("cost_attribution", "cost_attribution.py", 300),
    Route("cost_truth", "cost_truth_report.py", 300),
    Route("corpus_linkage", "corpus_linkage_report.py", 900),
    Route("feature_stability", "feature_stability.py", 900),
    Route("horizon", "horizon_report.py", 300),
    Route("fill_hazard", "fill_hazard_report.py", 300),
    Route("defensive_cadence", "defensive_cadence_report.py", 300),
    Route("interpret", "interpret_report.py", 900),
    Route("ground_truth", "ground_truth_metrics.py", 900),
    Route("walkforward_lab", "walkforward_lab.py", 300),
)

# Windows: a windowless parent spawning children otherwise pops a console
# window per subprocess (scripts/auto_update.py _NOWIN); 0 is the POSIX no-op.
_NOWIN = 0x08000000 if os.name == "nt" else 0


def _head_tail(stdout: str, stderr: str, ok: bool) -> tuple[list[str], list[str]]:
    """First 3 non-empty stdout lines, last 15 stdout lines; stderr's tail is
    appended to `tail` only on a non-OK result (a green route's stderr is
    noise, a failing one's is often the whole story)."""
    lines = [ln for ln in stdout.splitlines() if ln.strip()]
    head = lines[:3]
    tail = stdout.splitlines()[-15:]
    if not ok and stderr.strip():
        tail = tail + ["--- stderr (tail) ---"] + stderr.splitlines()[-15:]
    return head, tail


def _run_route(route: Route) -> dict:
    """Run one route to completion; NEVER raises — a route's own crash is a
    reportable outcome (ERROR), not a reason to abort the panel."""
    argv = [sys.executable, str(SCRIPTS_DIR / route.script)]
    started = time.time()
    try:
        p = subprocess.run(  # nosec B603
            argv, capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=route.timeout_sec, cwd=str(ROOT),
            creationflags=_NOWIN, check=False)
        duration = time.time() - started
        ok = p.returncode == 0
        head, tail = _head_tail(p.stdout or "", p.stderr or "", ok)
        return {
            "name": route.name, "status": "OK" if ok else "FAILED",
            "rc": p.returncode, "duration_sec": duration,
            "head": head, "tail": tail,
        }
    except subprocess.TimeoutExpired as e:
        duration = time.time() - started
        head, tail = _head_tail(e.stdout or "" if isinstance(e.stdout, str) else "",
                                e.stderr or "" if isinstance(e.stderr, str) else "",
                                False)
        return {
            "name": route.name, "status": "TIMEOUT", "rc": None,
            "duration_sec": duration, "head": head,
            "tail": tail or [f"timed out after {route.timeout_sec}s"],
        }
    except Exception as e:                       # noqa: BLE001 - fail-safe
        duration = time.time() - started
        return {
            "name": route.name, "status": "ERROR", "rc": None,
            "duration_sec": duration, "head": [],
            "tail": [f"{type(e).__name__}: {e}"],
        }


def _git_head() -> str:
    try:
        p = subprocess.run(  # nosec B603 B607
            ["git", "rev-parse", "--short", "HEAD"], cwd=str(ROOT),
            capture_output=True, text=True, timeout=15, creationflags=_NOWIN,
            check=False)
        return p.stdout.strip() if p.returncode == 0 else ""
    except Exception:                             # noqa: BLE001 - best-effort
        return ""


def run_panel(only: list[str] | None = None) -> dict:
    """Run the selected routes (default: all) concurrently, one subprocess
    each. Bounded worker pool: cpu_count-1 leaves a core free for whatever
    else is running on the box (the PC also runs a live paper bot), floored
    at 2 so a single-core box still gets concurrency, capped at the route
    count so idle workers are never spun up."""
    selected = ROUTES if only is None else [r for r in ROUTES if r.name in only]
    started = time.time()
    workers = min(len(selected), max(2, (os.cpu_count() or 4) - 1))
    with ThreadPoolExecutor(max_workers=max(workers, 1)) as ex:
        routes = list(ex.map(_run_route, selected))
    counts = {"ok": 0, "failed": 0, "timeout": 0, "error": 0}
    for r in routes:
        counts[r["status"].lower()] += 1
    return {
        "generated_at": started,
        "git_head": _git_head(),
        "duration_sec": time.time() - started,
        "routes": routes,
        "counts": counts,
    }


def _render_md(result: dict) -> str:
    c = result["counts"]
    header = (
        f"# Learning panel — {c['ok']} OK, {c['failed']} FAILED, "
        f"{c['timeout']} TIMEOUT, {c['error']} ERROR "
        f"(total {result['duration_sec']:.1f}s, head {result['git_head'] or '?'})"
    )
    lines = [header, "", CAVEAT, ""]
    for r in result["routes"]:
        lines.append(f"## {r['name']} — {r['status']} "
                     f"({r['duration_sec']:.1f}s, rc={r['rc']})")
        lines.append("```")
        lines.extend(r["tail"] or ["(no output)"])
        lines.append("```")
        lines.append("")
    return "\n".join(lines)


def write_panel(result: dict) -> None:
    """Write both panel files. JSON is atomic tmp-write + os.replace (the
    2026-07-31 LOG_PATH lesson: a reader mid-read must never see a partial
    file); the MD is human-facing and rewritten in place."""
    PANEL_MD.parent.mkdir(parents=True, exist_ok=True)
    PANEL_MD.write_text(_render_md(result), encoding="utf-8")
    PANEL_JSON.parent.mkdir(parents=True, exist_ok=True)
    tmp = PANEL_JSON.with_suffix(f".{os.getpid()}.tmp")
    tmp.write_text(json.dumps(result, indent=2), encoding="utf-8")
    os.replace(tmp, PANEL_JSON)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--list", action="store_true",
                        help="print route names and exit")
    parser.add_argument("--only", default=None,
                        help="comma-separated subset of route names")
    parser.add_argument("--json", action="store_true",
                        help="also print the panel JSON to stdout")
    args = parser.parse_args(argv)

    if args.list:
        for route in ROUTES:
            print(route.name)
        return 0

    only = None
    if args.only:
        only = [n.strip() for n in args.only.split(",") if n.strip()]
        known = {r.name for r in ROUTES}
        unknown = [n for n in only if n not in known]
        if unknown:
            print(f"learning_panel: unknown route(s): {', '.join(unknown)}",
                 file=sys.stderr)
            return 2

    result = run_panel(only=only)
    try:
        write_panel(result)
    except OSError as e:
        print(f"learning_panel: could not write panel files: {e}",
             file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        c = result["counts"]
        print(f"learning_panel: {c['ok']} OK, {c['failed']} FAILED, "
             f"{c['timeout']} TIMEOUT, {c['error']} ERROR -> {PANEL_MD}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
