"""scripts/shadow_gate_weights.py — SANDBOX PROTOTYPE, sidecar only.

Reads veto counterfactual grades (gate_efficacy_report.py's `by_code`
table, from a JSON export at outputs/gate_efficacy.json IF ONE EXISTS -
see the ABSENT note below) and the CURRENT live GateStats learned weights
(outputs/status.json's `gate_stats.weights`), and computes the
HYPOTHETICAL weight a grade-informed update would assign to each veto
code - using the EXACT shading formula the real learner already uses
(strategies.signal_gates.GateStats._shade), so this is not a second,
drift-prone reimplementation of that math. Appends one row per code per
run to outputs/shadow_gate_weights.jsonl via durable_append (torn-tail-
safe, one record per call).

NEVER APPLIED, NEVER WIRED IN. This script is invoked by nothing in the
runner/engine loop, imported by no decision-path module, and writes
NOTHING the live system reads. THALES's shadow-first law: a new signal
proves itself in a sidecar ledger before a promotion decision - always a
separate, explicit, human act - lets it influence anything real. See
tests/test_shadow_gate_weights.py::test_shadow_output_referenced_nowhere_
decision_path for the structural guard.

THE NAMESPACE CAVEAT (read this before trusting `current_weight`). Veto
codes (SZ-*, PT-*, the `by_code` key) and GateStats-tracked gates (the
informed-flow COMPONENT names - flow/delta/accum/burst/trend/evidence/
conc) are DIFFERENT KEY SPACES today: nothing in this codebase maps a
veto reason onto a confirmation-gate component, and this script invents
no such mapping. So `current_weight` is almost always null and
`gatestats_tracked` almost always false - that is not a bug in this
script, it is an honest report that GateStats does not track vetoes at
all yet. `hypothetical_weight` answers a narrower, still-useful question:
"if a code's own counterfactual grade were fed through GateStats's own
shading formula against the SAME baseline gate_efficacy_report used, what
weight would come out" - a preview of the math, not a claim about what
GateStats is currently doing.

DEGRADE HONESTLY (absent-is-not-zero - scripts/trial_ledger.py's own
convention, sibling branch commit d1184dad, `harvest()`'s ABSENT-source
reporting). A checkout with no outputs/gate_efficacy.json prints ABSENT
and exits 0 - this is the ORDINARY state of a fresh checkout:
gate_efficacy_report.py --json is not wired into any scheduled export
today (gc_pusher.py runs it as a subprocess and reads stdout directly,
never writes a file - grep the repo), so the file's existence is an
OPERATOR action, not a corpus-size signal. Likewise a missing status.json
degrades `current_weight` to null for every row rather than pretending
0.0/1.0 is a measured cold-start value.

CONSUMER TODO (out of scope here - scripts/gate_efficacy_report.py is
concurrently edited elsewhere per this change's task brief): once the
sibling stratification tag (see ml/history.py's CONTROL_ARM_FRACTION
constant and its docstring) has accrued enough contemporaneous rows,
gate_efficacy_report.py's own `baseline` should grow a second, era-
current arm sourced from that tag's minority-arm rows instead of (or
beside) the frozen blank-disposition cohort - see this change's report
for the concrete 5-line sketch. (Deliberately not named literally here -
this module's own test suite greps the tree to prove no decision-path
file reads that column; this comment is prose about a FUTURE consumer,
not a read, but names it indirectly to keep that guard meaningful.)
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.runtime import durable_append, read_json  # noqa: E402
from strategies.signal_gates import GateStats  # noqa: E402

# Module-level output/input path DEFAULTS. Registered in
# tests/conftest.py's _REDIRECTED_PATH_ATTRS (SHADOW_WEIGHTS_PATH only -
# the other three are READ paths, never opened write-mode by this script,
# so the production-write guard has nothing to catch there).
GATE_EFFICACY_PATH = "outputs/gate_efficacy.json"
STATUS_PATH = "outputs/status.json"
CONFIG_PATH = "config.json"
SHADOW_WEIGHTS_PATH = "outputs/shadow_gate_weights.jsonl"

# Fallback GateStats tuning when config.json is absent or carries no
# signal_gates.learned_weights block - byte-identical to that block's own
# shipped defaults (config.json, 2026-08 baseline), so an absent config
# does not silently invent a DIFFERENT hypothesis than the live learner
# would use under its own defaults.
DEFAULT_MIN_SAMPLES = 40
DEFAULT_STRENGTH = 2.0


def load_by_code(path: str) -> tuple[list, "dict | None", bool]:
    """(by_code rows, baseline dict, present). present=False - the file
    does not exist, or does not parse as the expected shape - is ABSENT,
    never silently treated as zero vetoes."""
    p = Path(path)
    if not p.exists():
        return [], None, False
    data = read_json(p)
    if not isinstance(data, dict):
        return [], None, False
    eff = data.get("efficacy")
    if not isinstance(eff, dict):
        return [], None, False
    by_code = eff.get("by_code")
    baseline = eff.get("baseline")
    return (by_code if isinstance(by_code, list) else [],
            baseline if isinstance(baseline, dict) else None, True)


def load_gate_stats_weights(path: str) -> tuple[dict, bool]:
    """(weights dict keyed by GateStats gate name, present). Never raises;
    a missing/malformed status.json degrades to ({}, False) - EVERY row's
    current_weight then reads null, not a fabricated 1.0."""
    p = Path(path)
    if not p.exists():
        return {}, False
    data = read_json(p)
    if not isinstance(data, dict):
        return {}, False
    gs = data.get("gate_stats")
    weights = gs.get("weights") if isinstance(gs, dict) else None
    return (weights if isinstance(weights, dict) else {}), True


def load_gate_stats_cfg(path: str) -> dict:
    """{'min_samples', 'strength'} - real config.json values when present
    and shaped as expected, else the documented defaults above. Always
    returns a usable dict; never raises."""
    p = Path(path)
    data = read_json(p) if p.exists() else None
    lw = {}
    if isinstance(data, dict):
        sg = data.get("signal_gates")
        if isinstance(sg, dict):
            cand = sg.get("learned_weights")
            if isinstance(cand, dict):
                lw = cand
    return {"min_samples": int(lw.get("min_samples", DEFAULT_MIN_SAMPLES)),
            "strength": float(lw.get("strength", DEFAULT_STRENGTH))}


def hypothetical_weight(gs: GateStats, n: int, wins: int, base_n: int,
                        base_wins: int) -> float:
    """The weight GateStats's OWN shading formula would assign if this
    code's (n, wins) were fed to it as a tracked gate's label ledger,
    against the SAME baseline gate_efficacy_report scored. Calls the real
    `_shade` (private, same-repo reuse) rather than re-deriving the
    Wilson-LCB-vs-base-rate math a second time - the two must never be
    allowed to drift apart, and importing the real function is the only
    way to guarantee that."""
    return gs._shade(n, wins, base_n, base_wins, gs.min_samples)


def build_rows(by_code: list, baseline: "dict | None", weights: dict,
              cfg: dict, as_of: float) -> list[dict]:
    gs = GateStats({"min_samples": cfg["min_samples"],
                    "strength": cfg["strength"]})
    base_n = int(baseline.get("n", 0) or 0) if baseline else 0
    base_wins = int(baseline.get("wins", 0) or 0) if baseline else 0
    rows = []
    for entry in by_code:
        if not isinstance(entry, dict):
            continue
        code = entry.get("code")
        if not code:
            continue
        try:
            n = int(entry.get("n", 0) or 0)
            wins = int(entry.get("wins", 0) or 0)
        except (TypeError, ValueError):
            continue
        hyp = hypothetical_weight(gs, n, wins, base_n, base_wins)
        tracked = code in weights
        rows.append({
            # --- the four fields the task spec names -------------------
            "as_of": as_of,
            "code": code,
            "current_weight": weights.get(code) if tracked else None,
            "hypothetical_weight": round(float(hyp), 4),
            "grade_basis": entry.get("comparison") or "unknown",
            "n_eff": entry.get("n_eff"),
            # --- EXTEND-only transparency fields (no consumer may treat
            # these as required - they exist so a reader does not have to
            # re-derive what this row's hypothesis was computed against) --
            "n": n, "wins": wins,
            "vs_baseline": entry.get("vs_baseline"),
            "gatestats_tracked": tracked,
            "min_samples": cfg["min_samples"], "strength": cfg["strength"],
            "baseline_n": base_n, "baseline_wins": base_wins,
        })
    return rows


def _append_jsonl_row(path: str, row: dict) -> bool:
    return durable_append(path, lambda f: f.write(json.dumps(row) + "\n"),
                          newline="\n")


def run(gate_efficacy_path: str = GATE_EFFICACY_PATH,
       status_path: str = STATUS_PATH, config_path: str = CONFIG_PATH,
       out_path: str = SHADOW_WEIGHTS_PATH,
       as_of: "float | None" = None) -> dict:
    """Core logic, separate from CLI parsing so tests call it directly
    with tmp_path fixtures instead of shelling out. Never raises - every
    failure mode here is a report-only degrade, matching this script's own
    shadow-first, never-applied nature."""
    by_code, baseline, present = load_by_code(gate_efficacy_path)
    if not present:
        print(f"gate_efficacy source ABSENT (not zero vetoes) at "
             f"{gate_efficacy_path} - nothing written")
        return {"status": "absent", "rows_written": 0}
    if not by_code:
        print(f"gate_efficacy present but by_code is empty at "
             f"{gate_efficacy_path} (corpus below the report's --min-n, "
             f"or nothing labeled yet) - nothing written")
        return {"status": "empty", "rows_written": 0}

    weights, status_present = load_gate_stats_weights(status_path)
    if not status_present:
        print(f"status.json ABSENT (not zero) at {status_path} - "
             f"current_weight will read null for every code")

    cfg = load_gate_stats_cfg(config_path)
    ts = as_of if as_of is not None else round(time.time(), 1)
    rows = build_rows(by_code, baseline, weights, cfg, ts)

    ok = True
    for row in rows:
        ok = _append_jsonl_row(out_path, row) and ok

    print(f"shadow_gate_weights: wrote {len(rows)} row(s) -> {out_path} "
         f"(status.json {'present' if status_present else 'ABSENT'}, "
         f"min_samples={cfg['min_samples']} strength={cfg['strength']})")
    return {"status": "written" if ok else "partial", "rows_written": len(rows)}


def main(argv: "list[str] | None" = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--gate-efficacy", default=GATE_EFFICACY_PATH,
                    help="JSON export of gate_efficacy_report.py --json "
                         "(NOT auto-generated - operator/cron action)")
    ap.add_argument("--status", default=STATUS_PATH)
    ap.add_argument("--config", default=CONFIG_PATH)
    ap.add_argument("--out", default=SHADOW_WEIGHTS_PATH)
    ns = ap.parse_args(argv)
    run(ns.gate_efficacy, ns.status, ns.config, ns.out)
    return 0     # never a failure exit - ABSENT/empty are honest reports


if __name__ == "__main__":
    raise SystemExit(main())
