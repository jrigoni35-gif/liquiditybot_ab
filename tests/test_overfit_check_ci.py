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
    report = tmp_path / "overfit_report.md"
    proc = subprocess.run(
        [sys.executable, str(_ROOT / "scripts" / "overfit_check.py"),
         "--quick", "--force-synthetic", "--report-path", str(report)],
        cwd=str(_ROOT), capture_output=True, text=True, timeout=120)

    assert proc.returncode == 0, (
        "overfit audit regression (exit "
        f"{proc.returncode}):\n{proc.stdout}\n{proc.stderr}")
    assert report.exists()
    assert "FAIL" not in report.read_text(encoding="utf-8")
