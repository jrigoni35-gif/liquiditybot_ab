"""Pins for scripts/shadow_gate_weights.py (sandbox prototype,
2026-08-27) - the shadow, never-applied gate-weight learner.

Three properties protected, same priority order as the module's own
docstring: (1) NEVER writes anywhere the live system reads - a structural
grep guard, not just an absence of call sites today; (2) degrades
HONESTLY (absent-is-not-zero) rather than fabricating a grade or a
weight when its inputs are missing; (3) the hypothetical math is a
faithful reuse of GateStats's own shading formula, verified against an
INDEPENDENT, from-scratch reference implementation of the same Wilson-
LCB-vs-base-rate math (double-derive - USAGE.md rule e/g) rather than
trusted merely because it imports the "real" function.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

from scripts import shadow_gate_weights as sgw

REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _efficacy_payload(by_code, baseline=None):
    return {"efficacy": {"baseline": baseline or {"n": 0, "wins": 0},
                         "by_code": by_code},
            "calibration": [], "concentration": {}}


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in
            path.read_text(encoding="utf-8").splitlines() if line.strip()]


# --- independent reference implementation (double-derive) ------------------
# Deliberately NOT imported from strategies.signal_gates - a hand-written
# second route over the SAME published formula (Wilson lower confidence
# bound on a win rate, shaded against a base rate, bounded [0.7, 1.3]).
# If this and the shipped GateStats._shade ever disagree, one of the two
# implementations has a bug - that is exactly what this pin exists to
# catch, which importing the function under test could never do.
def _ref_wilson_lcb(wins: int, n: int, z: float = 1.96) -> float:
    if n <= 0:
        return 0.0
    p = wins / n
    z2 = z * z
    denom = 1.0 + z2 / n
    center = p + z2 / (2 * n)
    rad = z * math.sqrt(p * (1 - p) / n + z2 / (4 * n * n))
    return max((center - rad) / denom, 0.0)


def _ref_shade(n, wins, tot_n, tot_wins, floor, strength) -> float:
    if n < floor or tot_n < floor:
        return 1.0
    base = tot_wins / max(tot_n, 1)
    lcb = _ref_wilson_lcb(wins, n)
    return min(max(1.0 + (lcb - base) * strength, 0.7), 1.3)


def test_hypothetical_weight_matches_independent_reference():
    from strategies.signal_gates import GateStats
    gs = GateStats({"min_samples": 40, "strength": 2.0})
    cases = [(60, 20, 500, 260), (40, 5, 500, 260), (10, 2, 500, 260),
            (200, 150, 500, 100)]
    for n, wins, base_n, base_wins in cases:
        shipped = sgw.hypothetical_weight(gs, n, wins, base_n, base_wins)
        ref = _ref_shade(n, wins, base_n, base_wins, 40, 2.0)
        assert abs(shipped - ref) < 1e-9, (n, wins, shipped, ref)


# --- ABSENT degrade ----------------------------------------------------

def test_absent_gate_efficacy_prints_absent_exits_zero_writes_nothing(
        tmp_path, capsys):
    out = tmp_path / "outputs" / "shadow_gate_weights.jsonl"
    result = sgw.run(gate_efficacy_path=str(tmp_path / "nope.json"),
                     status_path=str(tmp_path / "status.json"),
                     config_path=str(tmp_path / "config.json"),
                     out_path=str(out))
    assert result == {"status": "absent", "rows_written": 0}
    assert not out.exists()
    assert "ABSENT" in capsys.readouterr().out


def test_empty_by_code_exits_zero_writes_nothing(tmp_path, capsys):
    ge = tmp_path / "gate_efficacy.json"
    _write_json(ge, _efficacy_payload([]))
    out = tmp_path / "shadow_gate_weights.jsonl"
    result = sgw.run(gate_efficacy_path=str(ge),
                     status_path=str(tmp_path / "status.json"),
                     config_path=str(tmp_path / "config.json"),
                     out_path=str(out))
    assert result == {"status": "empty", "rows_written": 0}
    assert not out.exists()


def test_absent_status_json_current_weight_null_and_untracked(
        tmp_path, capsys):
    ge = tmp_path / "gate_efficacy.json"
    _write_json(ge, _efficacy_payload(
        [{"code": "SZ-021", "n": 80, "wins": 20, "n_eff": 40.0,
          "comparison": "not_significant", "vs_baseline": -0.05}],
        baseline={"n": 500, "wins": 260}))
    out = tmp_path / "shadow_gate_weights.jsonl"
    result = sgw.run(gate_efficacy_path=str(ge),
                     status_path=str(tmp_path / "no_status.json"),
                     config_path=str(tmp_path / "no_config.json"),
                     out_path=str(out))
    assert result["rows_written"] == 1
    rows = _read_jsonl(out)
    assert rows[0]["current_weight"] is None
    assert rows[0]["gatestats_tracked"] is False
    assert "ABSENT" in capsys.readouterr().out


def test_status_present_but_code_not_gatestats_tracked(tmp_path):
    """The namespace caveat, exercised: a REAL status.json with REAL
    GateStats weights, keyed by gate-component names, never happens to
    contain a veto CODE string - current_weight must read null, not
    silently pick up an unrelated gate's weight."""
    ge = tmp_path / "gate_efficacy.json"
    _write_json(ge, _efficacy_payload(
        [{"code": "SZ-021", "n": 80, "wins": 20, "n_eff": 40.0,
          "comparison": "not_significant"}],
        baseline={"n": 500, "wins": 260}))
    status = tmp_path / "status.json"
    _write_json(status, {"gate_stats": {"weights": {
        "flow": 1.05, "delta": 0.92, "accum": 1.0}}})
    out = tmp_path / "shadow_gate_weights.jsonl"
    sgw.run(gate_efficacy_path=str(ge), status_path=str(status),
           config_path=str(tmp_path / "no_config.json"), out_path=str(out))
    row = _read_jsonl(out)[0]
    assert row["current_weight"] is None
    assert row["gatestats_tracked"] is False


def test_status_present_and_code_happens_to_be_tracked(tmp_path):
    """The other side of the same guard: IF a status.json ever does carry
    a literal match (contrived here), current_weight must read the REAL
    tracked value, not null."""
    ge = tmp_path / "gate_efficacy.json"
    _write_json(ge, _efficacy_payload(
        [{"code": "SZ-021", "n": 80, "wins": 20, "n_eff": 40.0,
          "comparison": "selective"}],
        baseline={"n": 500, "wins": 260}))
    status = tmp_path / "status.json"
    _write_json(status, {"gate_stats": {"weights": {"SZ-021": 0.813}}})
    out = tmp_path / "shadow_gate_weights.jsonl"
    sgw.run(gate_efficacy_path=str(ge), status_path=str(status),
           config_path=str(tmp_path / "no_config.json"), out_path=str(out))
    row = _read_jsonl(out)[0]
    assert row["current_weight"] == 0.813
    assert row["gatestats_tracked"] is True


def test_config_absent_uses_documented_defaults(tmp_path):
    ge = tmp_path / "gate_efficacy.json"
    _write_json(ge, _efficacy_payload(
        [{"code": "SZ-023", "n": 60, "wins": 10, "n_eff": None,
          "comparison": "anti_selective"}],
        baseline={"n": 500, "wins": 260}))
    out = tmp_path / "shadow_gate_weights.jsonl"
    sgw.run(gate_efficacy_path=str(ge),
           status_path=str(tmp_path / "no_status.json"),
           config_path=str(tmp_path / "no_config.json"), out_path=str(out))
    row = _read_jsonl(out)[0]
    assert row["min_samples"] == sgw.DEFAULT_MIN_SAMPLES
    assert row["strength"] == sgw.DEFAULT_STRENGTH


def test_config_present_overrides_defaults(tmp_path):
    ge = tmp_path / "gate_efficacy.json"
    _write_json(ge, _efficacy_payload(
        [{"code": "SZ-023", "n": 60, "wins": 10, "n_eff": None,
          "comparison": "anti_selective"}],
        baseline={"n": 500, "wins": 260}))
    cfg = tmp_path / "config.json"
    _write_json(cfg, {"signal_gates": {"learned_weights": {
        "min_samples": 15, "strength": 3.5}}})
    out = tmp_path / "shadow_gate_weights.jsonl"
    sgw.run(gate_efficacy_path=str(ge),
           status_path=str(tmp_path / "no_status.json"),
           config_path=str(cfg), out_path=str(out))
    row = _read_jsonl(out)[0]
    assert row["min_samples"] == 15
    assert row["strength"] == 3.5


def test_grade_basis_carries_the_comparison_flag(tmp_path):
    """The most important honesty field: if gate_efficacy_report itself
    flagged CONFOUNDED_BASELINE for a code, that must survive verbatim
    into grade_basis - the whole reason this prototype exists is that a
    CONFOUNDED_BASELINE hypothesis is not trustworthy, and a reader must
    be able to see that without re-deriving it."""
    ge = tmp_path / "gate_efficacy.json"
    _write_json(ge, _efficacy_payload(
        [{"code": "SZ-021", "n": 400, "wins": 50, "n_eff": 12.0,
          "comparison": "CONFOUNDED_BASELINE"}],
        baseline={"n": 500, "wins": 260}))
    out = tmp_path / "shadow_gate_weights.jsonl"
    sgw.run(gate_efficacy_path=str(ge),
           status_path=str(tmp_path / "no_status.json"),
           config_path=str(tmp_path / "no_config.json"), out_path=str(out))
    assert _read_jsonl(out)[0]["grade_basis"] == "CONFOUNDED_BASELINE"


def test_multiple_codes_write_one_row_each(tmp_path):
    ge = tmp_path / "gate_efficacy.json"
    _write_json(ge, _efficacy_payload(
        [{"code": "SZ-021", "n": 80, "wins": 20, "n_eff": 40.0,
          "comparison": "not_significant"},
         {"code": "SZ-023", "n": 60, "wins": 5, "n_eff": None,
          "comparison": "anti_selective"},
         {"code": "PT-050", "n": 45, "wins": 30, "n_eff": 22.0,
          "comparison": "selective"}],
        baseline={"n": 500, "wins": 260}))
    out = tmp_path / "shadow_gate_weights.jsonl"
    result = sgw.run(gate_efficacy_path=str(ge),
                     status_path=str(tmp_path / "no_status.json"),
                     config_path=str(tmp_path / "no_config.json"),
                     out_path=str(out))
    assert result["rows_written"] == 3
    codes = {r["code"] for r in _read_jsonl(out)}
    assert codes == {"SZ-021", "SZ-023", "PT-050"}


def test_as_of_is_stamped_and_snapshot_style(tmp_path):
    """USAGE.md measurement contract: a live-file read must be snapshot-
    stamped, never treated as 'current'. as_of is that stamp - injected
    explicitly here rather than depending on wall-clock time.time()."""
    ge = tmp_path / "gate_efficacy.json"
    _write_json(ge, _efficacy_payload(
        [{"code": "SZ-021", "n": 80, "wins": 20, "n_eff": 40.0,
          "comparison": "not_significant"}],
        baseline={"n": 500, "wins": 260}))
    out = tmp_path / "shadow_gate_weights.jsonl"
    sgw.run(gate_efficacy_path=str(ge),
           status_path=str(tmp_path / "no_status.json"),
           config_path=str(tmp_path / "no_config.json"), out_path=str(out),
           as_of=1_700_000_000.5)
    assert _read_jsonl(out)[0]["as_of"] == 1_700_000_000.5


def test_appends_across_runs_never_truncates(tmp_path):
    ge = tmp_path / "gate_efficacy.json"
    _write_json(ge, _efficacy_payload(
        [{"code": "SZ-021", "n": 80, "wins": 20, "n_eff": 40.0,
          "comparison": "not_significant"}],
        baseline={"n": 500, "wins": 260}))
    out = tmp_path / "shadow_gate_weights.jsonl"
    for _ in range(3):
        sgw.run(gate_efficacy_path=str(ge),
               status_path=str(tmp_path / "no_status.json"),
               config_path=str(tmp_path / "no_config.json"),
               out_path=str(out))
    assert len(_read_jsonl(out)) == 3


def test_never_writes_anywhere_but_the_declared_out_path(tmp_path):
    """Structural sweep of the fresh tmp_path tree after a real run: the
    ONLY new file created anywhere under it must be the declared --out
    file (plus its parent dirs) - nothing lands beside status.json,
    gate_efficacy.json, or config.json."""
    ge = tmp_path / "inputs" / "gate_efficacy.json"
    _write_json(ge, _efficacy_payload(
        [{"code": "SZ-021", "n": 80, "wins": 20, "n_eff": 40.0,
          "comparison": "not_significant"}],
        baseline={"n": 500, "wins": 260}))
    status = tmp_path / "inputs" / "status.json"
    _write_json(status, {"gate_stats": {"weights": {"flow": 1.0}}})
    before = {p for p in tmp_path.rglob("*") if p.is_file()}
    out = tmp_path / "outputs" / "shadow_gate_weights.jsonl"
    sgw.run(gate_efficacy_path=str(ge), status_path=str(status),
           config_path=str(tmp_path / "no_config.json"), out_path=str(out))
    after = {p for p in tmp_path.rglob("*") if p.is_file()}
    assert after - before == {out}


def test_cli_entrypoint_writes_via_explicit_args(tmp_path):
    ge = tmp_path / "gate_efficacy.json"
    _write_json(ge, _efficacy_payload(
        [{"code": "SZ-021", "n": 80, "wins": 20, "n_eff": 40.0,
          "comparison": "not_significant"}],
        baseline={"n": 500, "wins": 260}))
    out = tmp_path / "shadow_gate_weights.jsonl"
    rc = sgw.main(["--gate-efficacy", str(ge),
                  "--status", str(tmp_path / "no_status.json"),
                  "--config", str(tmp_path / "no_config.json"),
                  "--out", str(out)])
    assert rc == 0
    assert len(_read_jsonl(out)) == 1


def test_default_output_path_is_redirected_by_conftest(tmp_path):
    """ASK THE RUNTIME, safely: call main() with NO --out (the module
    default SHADOW_WEIGHTS_PATH) and confirm the row lands under
    tmp_path, never under this worktree's real outputs/ tree - proof the
    conftest registration this change adds actually takes effect for a
    brand-new module, not just a claim in a comment."""
    ge = tmp_path / "gate_efficacy.json"
    _write_json(ge, _efficacy_payload(
        [{"code": "SZ-021", "n": 80, "wins": 20, "n_eff": 40.0,
          "comparison": "not_significant"}],
        baseline={"n": 500, "wins": 260}))
    rc = sgw.main(["--gate-efficacy", str(ge),
                  "--status", str(tmp_path / "no_status.json"),
                  "--config", str(tmp_path / "no_config.json")])
    assert rc == 0
    resolved = Path(sgw.SHADOW_WEIGHTS_PATH)
    assert str(resolved).startswith(str(tmp_path)), (
        f"SHADOW_WEIGHTS_PATH was not redirected to tmp_path: {resolved} "
        f"- the conftest registration for this module is not taking "
        f"effect (see tests/conftest.py _REDIRECTED_PATH_ATTRS)")
    assert resolved.exists()
    assert not (REPO_ROOT / "outputs" / "shadow_gate_weights.jsonl").exists()


# --- structural guard: never read by decision code --------------------

def test_shadow_output_referenced_nowhere_decision_path():
    """HARD CONSTRAINT: this script writes NOTHING the live system reads.
    Grep guard, not just an absence of call sites today - 'shadow_gate_
    weights' (module name) and its output filename must appear only in
    this script and the test tree."""
    allow = {REPO_ROOT / "scripts" / "shadow_gate_weights.py"}
    needles = ("shadow_gate_weights",)
    hits = []
    for path in REPO_ROOT.rglob("*.py"):
        parts = path.parts
        # See test_control_arm_tag.py for the measured rationale: a git
        # worktree under .claude/worktrees/ holds byte-copies of this repo's
        # files at different absolute paths, missing the canonical-path
        # `allow` set and reading as a violation on an unmodified tree.
        # `.claude` is agent tooling, never decision code.
        if (
            ".venv" in parts
            or "__pycache__" in parts
            or "tests" in parts
            or ".claude" in parts
        ):
            continue
        if path.resolve() in allow:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if any(needle in text for needle in needles):
            hits.append(str(path.relative_to(REPO_ROOT)))
    assert hits == [], f"shadow_gate_weights referenced outside itself: {hits}"
