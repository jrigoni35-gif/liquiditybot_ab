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
    # 300 -> 900 on 2026-09-06: the daily 05:30 run TIMED OUT at 300s (panel
    # LastResult=1), while a same-day foreground run measured 159s wall on the
    # current recording corpus. The route scans outputs/recordings/, which
    # grows with the runner, and shares the box with the 05:30 cadence. 900s
    # is ~5.7x the measured run - a WALL against a hang, not a standard; it
    # is an offline daily report and a longer wall costs nothing. Re-measure
    # (time python scripts/fill_hazard_report.py) before moving it again.
    Route("fill_hazard", "fill_hazard_report.py", 900),
    Route("defensive_cadence", "defensive_cadence_report.py", 300),
    Route("interpret", "interpret_report.py", 900),
    Route("ground_truth", "ground_truth_metrics.py", 900),
    Route("walkforward_lab", "walkforward_lab.py", 300),
    # Surfaces the macro-regime HMM's transition matrix, dwell times and
    # steady state - quantities regime/macro_regime.py fits daily and then
    # discards. 300s is ~31x a measured 9.6s wall (4 assets x 720 daily bars,
    # 3 EM restarts each, 2026-09-09); it scales with the traded universe, not
    # with the recording corpus, so it does not grow the way fill_hazard did.
    # Re-measure (time python scripts/regime_chain_report.py) before moving it.
    Route("regime_chain", "regime_chain_report.py", 300),
    # The order lifecycle as an absorbing Markov chain, read off the audit
    # trail: per-poll fill hazard, expected polls to absorption, and P(fill)
    # vs P(expire) for the three purposes separately. 300s against a measured
    # 0.27s wall (1,712 terminals over an 85k-line audit.jsonl, warm cache,
    # 2026-09-09) — a WALL against a hang, not a standard. It scans the whole
    # audit trail, which the runner grows without bound, so re-measure
    # (time python scripts/order_chain_report.py) before moving it.
    Route("order_chain", "order_chain_report.py", 300),
)

# Windows: a windowless parent spawning children otherwise pops a console
# window per subprocess (scripts/auto_update.py _NOWIN); 0 is the POSIX no-op.
_NOWIN = 0x08000000 if os.name == "nt" else 0


TAIL_LINES = 15
# Per-route cap on the retained full text (see _package_result). 256 KB is
# ~30x the largest real route, so nothing is lost in practice; it exists so a
# runaway or looping route cannot grow a synced artifact without bound.
FULL_TEXT_CAP = 256 * 1024


def _bounded(text: str, cap: int = FULL_TEXT_CAP) -> str:
    """Keep the TAIL within `cap` bytes and say so. The tail, not the head:
    verdict lines are emitted last, and dropping them is what made this field
    necessary in the first place."""
    if text is None:
        return ""
    if len(text) <= cap:
        return text
    dropped = len(text) - cap
    return (f"[... {dropped} characters truncated at the {cap}-byte "
            f"per-route cap; head dropped, tail kept ...]\n") + text[-cap:]


def _head_tail(stdout: str, stderr: str, ok: bool) -> tuple[list[str], list[str]]:
    """First 3 non-empty stdout lines, last TAIL_LINES stdout lines; stderr's
    tail is appended to `tail` only on a non-OK result (a green route's stderr
    is noise, a failing one's is often the whole story).

    The tail is MARKED when it drops lines. Truncation is fine - silent
    truncation is not: 14 of 16 routes saturate this window, and an unmarked
    15-line block is indistinguishable from complete output, which is how
    cohort_eval's verdict + homogeneity section went missing from every panel
    without anyone noticing (measured 2026-09-04). The full text is preserved
    in the result dict's `stdout_full` for the JSON.
    """
    all_lines = stdout.splitlines()
    lines = [ln for ln in all_lines if ln.strip()]
    head = lines[:3]
    tail = all_lines[-TAIL_LINES:]
    omitted = len(all_lines) - len(tail)
    if omitted > 0:
        tail = [f"... ({omitted} earlier lines truncated; "
                f"full text in the JSON's stdout_full)"] + tail
    if not ok and stderr.strip():
        err = stderr.splitlines()
        err_tail = err[-TAIL_LINES:]
        err_omitted = len(err) - len(err_tail)
        tail = tail + ["--- stderr (tail) ---"]
        if err_omitted > 0:
            tail = tail + [f"... ({err_omitted} earlier stderr lines truncated)"]
        tail = tail + err_tail
    return head, tail


def panel_exit_code(counts: dict) -> int:
    """0 only when every route produced a measurement.

    The old `main()` ended in an unconditional `return 0`, so a run in which
    every route failed exited green and the LiquidityBot-LearningPanel-Daily
    scheduled task recorded LastTaskResult=0 with a TIMEOUT inside it. "The
    process exited" is not "a measurement was made", and an operator reading
    Task Scheduler could not tell those apart.
    """
    bad = (int(counts.get("failed", 0)) + int(counts.get("timeout", 0))
           + int(counts.get("error", 0)))
    return 1 if bad else 0


def _package_result(route: "Route", stdout: str, stderr: str, rc,
                    duration: float, status: str) -> dict:
    """One shape for all three exit paths, so `stdout_full` can never be
    present on some and missing on others."""
    head, tail = _head_tail(stdout, stderr, status == "OK")
    return {
        "name": route.name, "status": status, "rc": rc,
        "duration_sec": duration, "head": head, "tail": tail,
        # The record: the .md is a summary, this is what a later reader
        # reconstructs a verdict from. BOUNDED, because learning_panel.json is
        # bundled and synced off-box - unbounded route output would grow this
        # file without limit and widen what leaves the machine. The cap is far
        # above any real route (the largest, cohort_eval, is single-digit KB),
        # so it preserves the whole reason this field exists while making the
        # worst case finite. Truncation is MARKED, never silent - that is the
        # defect this same commit fixes one field up.
        "stdout_full": _bounded(stdout),
        "stderr_full": _bounded(stderr),
    }


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
        return _package_result(route, p.stdout or "", p.stderr or "",
                               p.returncode, duration,
                               "OK" if ok else "FAILED")
    except subprocess.TimeoutExpired as e:
        duration = time.time() - started
        out = e.stdout if isinstance(e.stdout, str) else ""
        err = e.stderr if isinstance(e.stderr, str) else ""
        res = _package_result(route, out or "", err or "", None, duration,
                              "TIMEOUT")
        if not res["tail"]:
            res["tail"] = [f"timed out after {route.timeout_sec}s"]
        return res
    except Exception as e:                       # noqa: BLE001 - fail-safe
        duration = time.time() - started
        res = _package_result(route, "", "", None, duration, "ERROR")
        res["tail"] = [f"{type(e).__name__}: {e}"]
        return res


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
    # A green exit must mean every route produced a measurement. See
    # panel_exit_code: the unconditional `return 0` this replaces is why the
    # daily scheduled task logged LastTaskResult=0 over a TIMEOUT.
    return panel_exit_code(result["counts"])


if __name__ == "__main__":
    raise SystemExit(main())
