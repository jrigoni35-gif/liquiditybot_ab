"""core/replay_gate.py — replay-vs-live standing gate (pure logic).

Turns the record/replay harness into a truth-teller the DoD battery can lean
on. Two checks per recording:

  * DETERMINISM (hard): replaying one recording twice must yield identical
    P&L/fills. This is the harness's core promise — every counterfactual sweep
    (queue-aware re-baseline, gate analysis) trusts it. A change in engine
    behavior on recorded frames turns it red.
  * RECONCILIATION (conditional): when the recording carries a flat-start
    sidecar (data/recording.py), replay's realized P&L must match the live
    session's realized-P&L delta within tolerance. It HARD-FAILS only on a
    self-contained recording (every input the engine used was recorded);
    otherwise it WARNs, because unrecorded sentiment/webdata/moomoo feeds
    legitimately move live P&L away from replay.

SKIP-safe: no recordings => dormant PASS-equivalent (SKIP), so a fresh clone or
cloud snapshot never reddens the battery. The replay function is injected, so
this module is unit-testable without the engine.

Scope honesty: this validates that the backtester faithfully reproduces the
live ENGINE (fidelity). It does NOT validate that the strategy has EDGE — that
needs real out-of-sample data across regimes (see the Bucket-C work plan).
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from data.recording import read_sidecar

log = logging.getLogger("liquiditybot.core.replay_gate")

# summary keys that must be bit-identical across two replays of one recording
_DETERMINISM_KEYS = ("realized_pnl", "final_equity", "entries_filled",
                     "exit_orders", "fees", "labeled_rows")

DEFAULT_REL_TOL = 0.005     # 0.5% of the live P&L delta
DEFAULT_ABS_TOL = 0.01      # or 1 cent, whichever is larger
DEFAULT_MAX_RECORDINGS = 3  # newest N replayed per gate run (cost bound)


@dataclass(frozen=True)
class ReconResult:
    status: str                     # OK | WARN | FAIL | SKIP
    live_delta: float | None
    replay_pnl: float | None
    tol: float | None
    reason: str


@dataclass(frozen=True)
class GateResult:
    status: str                     # PASS | FAIL | SKIP
    recordings: int
    reason: str
    details: list = field(default_factory=list)


def discover_recordings(rec_dir) -> list[Path]:
    """Session recordings under ``rec_dir``, newest first (by mtime)."""
    d = Path(rec_dir)
    if not d.exists():
        return []
    try:
        files = list(d.glob("session_*.jsonl"))
    except OSError:
        return []
    files.sort(key=lambda p: p.stat().st_mtime if p.exists() else 0.0,
               reverse=True)
    return files


def determinism_ok(a: dict, b: dict,
                   keys: tuple = _DETERMINISM_KEYS) -> tuple[bool, str]:
    """True iff two replay summaries agree on every compared key present."""
    diffs = []
    for k in keys:
        if k in a and k in b and a[k] != b[k]:
            diffs.append(f"{k}: {a[k]!r} != {b[k]!r}")
    return (not diffs, "; ".join(diffs))


def reconcile(replay_summary: dict, sidecar: dict | None, *,
              rel_tol: float = DEFAULT_REL_TOL,
              abs_tol: float = DEFAULT_ABS_TOL) -> ReconResult:
    """Tie replay P&L to the live session's flat-start P&L delta."""
    if not sidecar or "start" not in sidecar or "end" not in sidecar:
        return ReconResult("SKIP", None, None, None,
                           "no flat-start sidecar to reconcile against")
    start, end = sidecar["start"], sidecar["end"]
    try:
        if int(start.get("open_positions", 1)) != 0:
            return ReconResult("SKIP", None, None, None,
                               "non-flat start (open_positions>0); "
                               "replay-from-flat cannot tie out")
        live_delta = float(end["realized_pnl"]) - float(start["realized_pnl"])
        replay_pnl = float(replay_summary.get("realized_pnl", 0.0))
    except (TypeError, ValueError, KeyError) as e:
        return ReconResult("SKIP", None, None, None, f"bad sidecar/summary: {e}")
    tol = max(abs_tol, rel_tol * abs(live_delta))
    diff = abs(replay_pnl - live_delta)
    self_contained = bool(start.get("self_contained", False))
    if diff <= tol:
        return ReconResult("OK", live_delta, replay_pnl, tol,
                           f"replay {replay_pnl:.4f} ~= live {live_delta:.4f} "
                           f"(diff {diff:.4f} <= tol {tol:.4f})")
    if self_contained:
        return ReconResult("FAIL", live_delta, replay_pnl, tol,
                           f"replay {replay_pnl:.4f} != live {live_delta:.4f} "
                           f"(diff {diff:.4f} > tol {tol:.4f}) on a "
                           f"self-contained recording")
    return ReconResult("WARN", live_delta, replay_pnl, tol,
                       f"replay {replay_pnl:.4f} != live {live_delta:.4f} "
                       f"(diff {diff:.4f} > tol {tol:.4f}) but recording is "
                       f"not self-contained (unrecorded feeds)")


def run_gate(rec_dir, replay_fn: Callable[[str], dict], *,
             rel_tol: float = DEFAULT_REL_TOL, abs_tol: float = DEFAULT_ABS_TOL,
             max_recordings: int = DEFAULT_MAX_RECORDINGS) -> GateResult:
    """Replay the newest recordings twice each; check determinism + reconcile.

    ``replay_fn(path) -> summary`` is injected (scripts/replay_gate.py binds the
    production run_replay). Returns SKIP when no recordings exist.
    """
    recs = discover_recordings(rec_dir)[:max_recordings]
    if not recs:
        return GateResult("SKIP", 0, "no recordings present - gate dormant")
    details: list = []
    failed = False
    for rec in recs:
        path = str(rec)
        try:
            s1 = replay_fn(path)
            s2 = replay_fn(path)
        except Exception as e:                       # a replay crash is a fail
            details.append({"recording": rec.name, "determinism": "ERROR",
                            "reconcile": "SKIP", "detail": f"replay raised: {e}"})
            failed = True
            continue
        det_ok, det_msg = determinism_ok(s1, s2)
        recon = reconcile(s1, read_sidecar(rec), rel_tol=rel_tol,
                          abs_tol=abs_tol)
        det_label = "OK" if det_ok else "FAIL"
        if not det_ok or recon.status == "FAIL":
            failed = True
        details.append({"recording": rec.name,
                        "determinism": det_label,
                        "determinism_detail": det_msg,
                        "reconcile": recon.status,
                        "reconcile_detail": recon.reason})
    status = "FAIL" if failed else "PASS"
    reason = (f"{len(recs)} recording(s): "
              + ("determinism/reconciliation FAILED" if failed
                 else "determinism + reconciliation clean"))
    return GateResult(status, len(recs), reason, details)
