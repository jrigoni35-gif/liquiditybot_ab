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
run every time, and it's also exactly what a human/CI runner invokes. A
few tests below (the ones that need to run main() TWICE in one process to
diff its own behavior against itself, or that call regime_diagnostic /
regime_corpus_stats directly) import scripts.overfit_check instead and
explicitly reset PASS_N/FAIL_N/REPORT themselves — see
`_run_overfit_main`'s docstring.

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

import numpy as np
import pytest

_ROOT = Path(__file__).resolve().parents[1]


# timing: subprocess runs of the full audit under a HARD 120s wall timeout
# - the same load-marginal class as test_pbo_variants' CLI tests (a
# saturated -n 8 battery starves the child past the deadline). The
# in-process _run_overfit_main tests below have no wall deadline and stay
# in the parallel pass.
@pytest.mark.timing
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


@pytest.mark.timing
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
    # #103 T3 review Important #3: the stratum-AUC-vs-pooled statistical
    # caveat must land WHERE THE OPERATOR READS THEM — in the emitted
    # report — not only in a code comment. (This run is --force-synthetic,
    # i.e. on_synthetic=True, so regime_corpus_stats never runs and the
    # separate n=/oof_n= counting-pass caveat is correctly absent here; see
    # test_regime_diagnostic_emits_corpus_caveat_on_live_path below for
    # that one, which only applies on the non-synthetic path.)
    assert "concatenated-OOF" in text and "MEAN-OF-FOLDS" in text


def test_regime_diagnostic_emits_corpus_caveat_on_live_path(tmp_path):
    """#103 T3 review Important #3, second caveat: n= (regime_corpus_stats'
    raw signal_history.csv count) vs oof_n= (the deduped/purged X actually
    OOF-scored) are two different counting passes, and that must be visible
    in the report too — but only reachable on the non-synthetic path (real
    live history clearing load_dataset's min_rows), which needs hundreds of
    real feature rows to exercise through full main(). Calls
    regime_diagnostic directly (on_synthetic=False) with a small valid
    corpus fixture instead."""
    from ml.features import FEATURE_NAMES
    import scripts.overfit_check as oc

    n = 40
    rng = np.random.default_rng(3)
    X = np.zeros((n, len(FEATURE_NAMES)))
    X[:, FEATURE_NAMES.index("regime_range")] = 1.0  # every row -> 'range'
    y = (rng.random(n) < 0.5).astype(float)
    gaps = {"gbt": {"oof_idx": np.arange(n), "oof_pred": rng.random(n),
                    "oof_auc": 0.55, "oof_brier": 0.24}}

    header = (["label"] + [f"regime_{s}" for s in oc.REGIME_STRATA] +
              ["source"])
    lines = [",".join(header)]
    for i in range(n):
        row = ["1" if y[i] else "0"]
        row += ["1" if s == "range" else "0" for s in oc.REGIME_STRATA]
        row.append("live")
        lines.append(",".join(row))
    csv_path = tmp_path / "signal_history.csv"
    csv_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    oc.REPORT.clear()
    oc.regime_diagnostic(gaps, X, y, False, str(csv_path))
    detail_texts = " ".join(detail for _, _, detail in oc.REPORT)
    assert "raw signal_history.csv count" in detail_texts
    assert "regime[range]" in [name for _, name, _ in oc.REPORT]


def _run_overfit_main(monkeypatch, cwd: Path, report_path: Path,
                      patches: dict | None = None) -> int:
    """Run scripts/overfit_check.py's main() IN-PROCESS (not via subprocess)
    against the CURRENT tree, resetting the module-level PASS_N/FAIL_N/
    REPORT accumulators first (main() itself never resets them between
    calls — see the module docstring above on why every OTHER test in this
    file uses a fresh subprocess instead) and swapping in any of
    `patches` (name -> replacement callable) as module attributes for the
    duration of the call via monkeypatch (auto-restored at test teardown).

    Used only by tests that need to run the CURRENT revision of main()
    twice in one process and diff its own behavior against itself — no git
    history involved, so the comparison can never go stale."""
    import scripts.overfit_check as oc
    monkeypatch.setattr(oc, "PASS_N", 0)
    monkeypatch.setattr(oc, "FAIL_N", 0)
    monkeypatch.setattr(oc, "REPORT", [])
    for attr, fn in (patches or {}).items():
        monkeypatch.setattr(oc, attr, fn)
    monkeypatch.chdir(cwd)
    monkeypatch.setattr(
        sys, "argv",
        ["overfit_check.py", "--quick", "--force-synthetic",
         "--report-path", str(report_path)])
    return oc.main()


def test_regime_diagnostic_does_not_change_verdicts_or_exit_code(
        tmp_path, monkeypatch):
    """THE CRITICAL invariant (#103 T3 hard constraint): appending the
    regime-stratified section must not move a single existing OF-1..OF-7
    verdict or the exit code.

    Revision-independent by design. The prior version of this test diffed
    against `git show HEAD:scripts/overfit_check.py` as the "before"
    baseline — but the moment this task's own commit becomes HEAD, that
    "before" snapshot already contains the diagnostic, so before_text ==
    after_text and the test's own anti-tautology guard
    (`"regime[" not in before_text`) fails permanently (confirmed: this is
    the #103 T3 review's Critical finding, reproduced RED against the
    committed tree before this rewrite — see task-t3-report.md's Fix pass).

    Fix: run the CURRENT tree's main() TWICE in this process on the same
    deterministic synthetic corpus — once with the diagnostic active, once
    with regime_diagnostic (and regime_corpus_stats, the function it calls)
    monkeypatched to a no-op — and assert the PASS/FAIL line set and exit
    code are IDENTICAL. This never goes stale and needs no git history."""
    report_active = tmp_path / "active.md"
    report_neutered = tmp_path / "neutered.md"

    rc_active = _run_overfit_main(monkeypatch, tmp_path, report_active)
    rc_neutered = _run_overfit_main(
        monkeypatch, tmp_path, report_neutered,
        patches={"regime_diagnostic": lambda *a, **k: None,
                "regime_corpus_stats": lambda *a, **k: {}})

    assert rc_active == 0, rc_active
    assert rc_neutered == rc_active, (
        f"exit code moved: neutered={rc_neutered} active={rc_active}")
    active_text = report_active.read_text(encoding="utf-8")
    neutered_text = report_neutered.read_text(encoding="utf-8")
    assert _pass_fail_lines(active_text) == _pass_fail_lines(neutered_text)
    # anti-tautology guard: proves the neutering actually took effect, i.e.
    # this isn't a vacuous same-run-twice comparison
    assert "regime[" in active_text
    assert "regime[" not in neutered_text


def test_regime_corpus_stats_survives_non_utf8_file(tmp_path):
    """#103 T3 review Important #2, the demonstrated repro: a non-UTF8 byte
    in signal_history.csv raises UnicodeDecodeError (a ValueError subclass)
    out of csv.DictReader mid-iteration. Pre-fix, regime_corpus_stats caught
    only OSError, so this propagated straight out of the function. Confirms
    the broadened (OSError, ValueError) catch returns {} instead of
    raising."""
    import scripts.overfit_check as oc
    bad = tmp_path / "signal_history.csv"
    bad.write_bytes(
        b"position_id,label,regime_bull_quiet,regime_bull_vol,regime_range,"
        b"regime_bear,regime_crisis,source\n"
        b"p1,1,\xff\xfe1,0,0,0,0,live\n")
    assert oc.regime_corpus_stats(str(bad)) == {}


def test_regime_diagnostic_exception_is_isolated_report_only(
        tmp_path, monkeypatch):
    """#103 T3 review Important #2: REPORT-ONLY must hold in the failure
    path too. Pre-fix, a raising regime_diagnostic call (e.g. the
    UnicodeDecodeError demonstrated in
    test_regime_corpus_stats_survives_non_utf8_file above, or — #103 T3
    review Minor — a renamed FEATURE_NAMES regime column raising out of
    regime_diagnostic's own FEATURE_NAMES.index(...) call) propagated out
    of main() uncaught, suppressing the whole report write and changing the
    exit code. This proves the call-site try/except added in main() absorbs
    ANY exception from the diagnostic section — the specific cause doesn't
    matter, which is also why no separate fix was needed for the Minor
    finding beyond this isolation."""
    report_ok = tmp_path / "ok.md"
    report_raises = tmp_path / "raises.md"

    rc_ok = _run_overfit_main(monkeypatch, tmp_path, report_ok)

    def _boom(*_a, **_k):
        raise ValueError("simulated: renamed FEATURE_NAMES regime column")

    rc_raises = _run_overfit_main(monkeypatch, tmp_path, report_raises,
                                  patches={"regime_diagnostic": _boom})

    assert rc_raises == rc_ok, (
        f"exit code moved: raises={rc_raises} ok={rc_ok}")
    ok_text = report_ok.read_text(encoding="utf-8")
    raises_text = report_raises.read_text(encoding="utf-8")
    assert _pass_fail_lines(ok_text) == _pass_fail_lines(raises_text), (
        "battery verdicts moved when the diagnostic raised")
    assert raises_text  # report still written
    assert ("regime diagnostic skipped: ValueError: simulated" in
            raises_text)
    assert "regime[" not in raises_text


@pytest.mark.timing
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
