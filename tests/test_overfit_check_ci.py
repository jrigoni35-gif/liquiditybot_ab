"""tests/test_overfit_check_ci.py - bind the FULL overfit audit to CI.

scripts/overfit_check.py (OF-1..OF-7) previously had no standing CI gate
at all: tests/test_overfit.py only unit-tests the individual ml/overfit.py
probes for discrimination (pass-clean/fail-dirty), which validates the
INSTRUMENTS but never runs the actual audit CLAUDE.md's own Definition of
Done requires green. This makes running it a standing pytest obligation,
mirroring how tests/test_quant_trials.py binds the G1-G5 quant gates.

Invoked via subprocess (not imported) because scripts/overfit_check.py's
main() carries module-level PASS_N/FAIL_N/REPORT globals that are never
reset between calls - a fresh process is the simplest way to get a clean
run every time, and it's also exactly what a human/CI runner invokes.

--force-synthetic pins the ML-layer dataset to the deterministic planted-
signal benchmark regardless of how much live history has accrued in
outputs/signal_history.csv by the time this runs - without it, this test
would silently flip from validating machinery (today, 17 live trades) to
depending on ambient production telemetry state once live rows clear 60,
making CI flaky and dependent on whatever the paper bot happened to do.
--report-path keeps the run from clobbering a human operator's last real
outputs/overfit_report.md.
"""
import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]


def test_full_overfit_audit_passes_on_synthetic_benchmark(tmp_path):
    # cwd=tmp_path (NOT the repo): OF-5 reads outputs/signal_history.csv
    # relative to cwd, so running from the repo made this test depend on
    # ambient production telemetry — it went red live 2026-07-17 the moment
    # the paper bot's live sample crossed 30 rows. An empty cwd pins OF-5
    # to its DEFERRED branch; the exploration-phase branch is pinned by the
    # dedicated test below.
    report = tmp_path / "overfit_report.md"
    proc = subprocess.run(
        [sys.executable, str(_ROOT / "scripts" / "overfit_check.py"),
         "--quick", "--force-synthetic", "--report-path", str(report)],
        cwd=str(tmp_path), capture_output=True, text=True, timeout=120)

    assert proc.returncode == 0, (
        "overfit audit regression (exit "
        f"{proc.returncode}):\n{proc.stdout}\n{proc.stderr}")
    assert report.exists()
    assert "FAIL" not in report.read_text(encoding="utf-8")


def _pass_fail_lines(report_text: str) -> list:
    """(status, name) pairs from '- **STATUS** name — detail' report lines,
    STATUS in {PASS, FAIL} only — INFO/diagnostic lines (which can never
    move PASS_N/FAIL_N/exit code) are deliberately excluded, so this is
    exactly the set of assertions that decide the battery's verdict."""
    out = []
    for line in report_text.splitlines():
        for status in ("PASS", "FAIL"):
            prefix = f"- **{status}** "
            if line.startswith(prefix):
                name = line[len(prefix):].split(" — ")[0].strip()
                out.append((status, name))
    return out


def test_regime_diagnostic_section_present_report_only(tmp_path):
    """#103 T3: the regime-stratified section must show up in the report
    and must never use PASS/FAIL formatting — every line is INFO, so it can
    never move PASS_N/FAIL_N/the exit code."""
    report = tmp_path / "overfit_report.md"
    proc = subprocess.run(
        [sys.executable, str(_ROOT / "scripts" / "overfit_check.py"),
         "--quick", "--force-synthetic", "--report-path", str(report)],
        cwd=str(tmp_path), capture_output=True, text=True, timeout=120)
    assert proc.returncode == 0, f"{proc.stdout}\n{proc.stderr}"
    text = report.read_text(encoding="utf-8")
    assert "regime[" in text, "regime-stratified diagnostic section missing"
    # every regime[...] line is INFO — never a PASS/FAIL gate line
    for line in text.splitlines():
        if "regime[" in line:
            assert line.startswith("- **INFO**"), line


def test_regime_diagnostic_does_not_change_verdicts_or_exit_code(tmp_path):
    """THE CRITICAL invariant (#103 T3 hard constraint): appending the
    regime-stratified section must not move a single existing OF-1..OF-7
    verdict or the exit code. Baseline = the actual pre-task HEAD revision
    of scripts/overfit_check.py (git show), run byte-for-byte the same way
    on the same deterministic synthetic corpus as the current tree."""
    baseline_src = subprocess.run(
        ["git", "show", "HEAD:scripts/overfit_check.py"],
        cwd=str(_ROOT), capture_output=True, text=True, check=True).stdout
    baseline_script = _ROOT / "scripts" / "_t3_baseline_snapshot.py"
    baseline_script.write_text(baseline_src, encoding="utf-8")
    try:
        report_before = tmp_path / "before.md"
        report_after = tmp_path / "after.md"
        before = subprocess.run(
            [sys.executable, str(baseline_script), "--quick",
             "--force-synthetic", "--report-path", str(report_before)],
            cwd=str(tmp_path), capture_output=True, text=True, timeout=120)
        after = subprocess.run(
            [sys.executable, str(_ROOT / "scripts" / "overfit_check.py"),
             "--quick", "--force-synthetic", "--report-path",
             str(report_after)],
            cwd=str(tmp_path), capture_output=True, text=True, timeout=120)
    finally:
        baseline_script.unlink(missing_ok=True)

    assert before.returncode == 0, f"{before.stdout}\n{before.stderr}"
    assert after.returncode == before.returncode, (
        f"exit code moved: before={before.returncode} "
        f"after={after.returncode}\n{after.stdout}\n{after.stderr}")
    before_text = report_before.read_text(encoding="utf-8")
    after_text = report_after.read_text(encoding="utf-8")
    assert _pass_fail_lines(before_text) == _pass_fail_lines(after_text)
    # and the diagnostic really is present in "after" (else the comparison
    # above would be vacuous — same script running twice)
    assert "regime[" in after_text
    assert "regime[" not in before_text


def test_dsr_is_informational_not_gating_during_exploration(tmp_path):
    # The live 2026-07-17 regression, distilled: 40 losing live-labeled
    # trades (an active-learning sample, EV-mixed by design) must NOT fail
    # the battery while the shipped config has ml.exploration.enabled=true.
    # The number is still reported so the trend stays visible.
    out = tmp_path / "outputs"
    out.mkdir()
    rows = ["position_id,net_pnl_usd,source"] + [
        f"p{i},-0.25,live" for i in range(40)]
    (out / "signal_history.csv").write_text("\n".join(rows) + "\n",
                                            encoding="utf-8")
    report = tmp_path / "overfit_report.md"
    proc = subprocess.run(
        [sys.executable, str(_ROOT / "scripts" / "overfit_check.py"),
         "--quick", "--force-synthetic", "--report-path", str(report)],
        cwd=str(tmp_path), capture_output=True, text=True, timeout=120)

    assert proc.returncode == 0, (
        f"a pure-exploration losing sample must not gate the battery:\n"
        f"{proc.stdout}\n{proc.stderr}")
    # since the probe marker (task #48) the gate defers on the conviction
    # sample instead of going informational on the mixed one — same intent:
    # an EV-mixed exploration sample must never gate the battery
    assert "conviction-marked live trades" in proc.stdout
    assert "FAIL" not in report.read_text(encoding="utf-8")
