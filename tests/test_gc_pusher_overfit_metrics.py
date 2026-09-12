"""The overfit battery must be VISIBLE on a board, and never stale-green.

WHY THIS EXISTS (2026-09-12). `scripts/gc_pusher.py` exported nothing about
the overfit battery - measured, `grep -c overfit_` returned 0 - so no board
and no alert could see a pre-registered gate go red. That is not academic:
that day OF-3 (`pbo`) went red and sat unnoticed behind OF-5's
operator-adjudicated red, because `overfit_check` exits 1 on ANY failing rung
and the record had an explanation ready for `rc=1`.

Two properties are pinned here, and they pull in opposite directions:

  1. A RED RUNG IS INDIVIDUALLY VISIBLE. `rung` is a label, so a second
     failure cannot hide inside the first one's exit code.

  2. A STALE REPORT NEVER PAINTS GATE STATE. The report is written only when
     a human runs the battery, so pushing its contents unconditionally would
     render a days-old verdict in healthy colour forever - the Brier-incident
     mechanism the dashboard HIG warns about. The collector borrows
     `collect()`'s DL-6 shape: past the staleness line, push the alarm-only
     batch and return.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

import scripts.gc_pusher as gp                              # noqa: E402
from scripts.gc_pusher import parse_overfit_report          # noqa: E402

REPORT = """# Overfit audit - 2026-09-12 06:19 UTC

Dataset: live history (18008 rows)

- **PASS** shuffle: destroyed labels learn nothing OOF - mean_auc=0.504
- **FAIL** pbo: DEPLOYED selection not dominated by luck - pbo=0.63
- **PASS** purge: never manufactures out-of-sample edge - leak_closed=-0.006
- **PASS** dof: not starved - rows/feature=281.4
- **FAIL** dsr: P(true SR > sr0) on conviction-only sample - dsr=0.006
- **INFO** gap[logistic] — INFORMATIONAL (OVER the 0.12 band): gap=+0.217
- **INFO** null-floor[gbt] — OOF Brier 0.2576 vs base 0.2441: LOSES
- **INFO** dsr READ THIS WITH THE VERDICT — SIGN READING: PSR=0.111

3 passed, 2 failed (123s)
"""


def _by_name(metrics):
    out = {}
    for m in metrics:
        dp = m["gauge"]["dataPoints"][0]
        attrs = {a["key"]: a["value"]["stringValue"]
                 for a in dp.get("attributes", [])}
        key = (m["name"], attrs.get("rung")) if attrs else m["name"]
        out[key] = dp["asDouble"]
    return out


# ---------------------------------------------------------------------------
# the parse
# ---------------------------------------------------------------------------

def test_every_graded_rung_is_parsed_with_its_verdict():
    p = parse_overfit_report(REPORT)
    assert p["rungs"] == {"shuffle": True, "pbo": False, "purge": True,
                          "dof": True, "dsr": False}
    assert (p["passed"], p["failed"], p["armed"]) == (3, 2, 5)


def test_INFO_lines_are_not_gate_state():
    """INFO lines can never move PASS_N/FAIL_N or the exit code. Counting one
    as a rung would inflate the armed count, which CLAUDE.md calls the number
    to read."""
    assert "dsr READ THIS WITH THE VERDICT" not in parse_overfit_report(
        REPORT)["rungs"]
    assert parse_overfit_report(REPORT)["armed"] == 5


def test_a_second_red_does_not_hide_behind_the_first():
    """THE WHOLE POINT. Two rungs are red; both must be individually
    addressable, because the exit code cannot tell them apart."""
    rungs = parse_overfit_report(REPORT)["rungs"]
    assert rungs["dsr"] is False and rungs["pbo"] is False
    assert sum(1 for v in rungs.values() if not v) == 2


def test_an_empty_report_yields_no_rungs_rather_than_a_green():
    assert parse_overfit_report("")["rungs"] == {}
    assert parse_overfit_report("")["armed"] == 0


# ---------------------------------------------------------------------------
# the staleness contract (DL-6 shape)
# ---------------------------------------------------------------------------

def _write(tmp_path, text, age_sec):
    p = tmp_path / "overfit_report.md"
    p.write_text(text, encoding="utf-8")
    import os
    t = time.time() - age_sec
    os.utime(p, (t, t))
    return p


def test_a_fresh_report_publishes_every_rung(tmp_path, monkeypatch):
    monkeypatch.setattr(gp, "OVERFIT_REPORT_PATH",
                        _write(tmp_path, REPORT, 60.0))
    m = _by_name(gp._overfit_gate_metrics(time.time()))
    assert m["liquiditybot_overfit_stale"] == 0.0
    assert m[("liquiditybot_overfit_rung_passed", "pbo")] == 0.0
    assert m[("liquiditybot_overfit_rung_passed", "dsr")] == 0.0
    assert m[("liquiditybot_overfit_rung_passed", "purge")] == 1.0
    assert m["liquiditybot_overfit_failed"] == 2.0
    assert m["liquiditybot_overfit_armed"] == 5.0


def test_a_STALE_report_publishes_NO_rung_values(tmp_path, monkeypatch):
    """The load-bearing one. A range-queried stat renders a dead producer's
    last value in healthy colour for up to a month; a battery report can be
    days old and still be the newest truth. Past the line the collector must
    push the alarm-only batch and RETURN."""
    monkeypatch.setattr(gp, "OVERFIT_REPORT_PATH",
                        _write(tmp_path, REPORT,
                               gp.OVERFIT_STALE_AFTER_SEC + 60.0))
    metrics = gp._overfit_gate_metrics(time.time())
    m = _by_name(metrics)
    assert m["liquiditybot_overfit_stale"] == 1.0
    assert m["liquiditybot_overfit_report_age_sec"] > \
        gp.OVERFIT_STALE_AFTER_SEC
    assert not any(x["name"] == "liquiditybot_overfit_rung_passed"
                   for x in metrics), (
        "a stale report published per-rung gate state; those values would "
        "render in healthy colour on a board long after they stopped being "
        "true")
    for dead in ("liquiditybot_overfit_passed", "liquiditybot_overfit_failed",
                 "liquiditybot_overfit_armed"):
        assert dead not in m, f"{dead} survived the staleness cut"


def test_a_MISSING_report_is_reported_as_absent_not_as_green(tmp_path,
                                                             monkeypatch):
    """A missing SERIES reads as 'no panel', which on a board is
    indistinguishable from 'all green'. The absence must be explicit."""
    monkeypatch.setattr(gp, "OVERFIT_REPORT_PATH", tmp_path / "nope.md")
    m = _by_name(gp._overfit_gate_metrics(time.time()))
    assert m["liquiditybot_overfit_report_missing"] == 1.0
    assert m["liquiditybot_overfit_stale"] == 1.0
    assert ("liquiditybot_overfit_rung_passed", "dsr") not in m


def test_the_staleness_line_is_not_silently_enormous():
    assert 3600.0 <= gp.OVERFIT_STALE_AFTER_SEC <= 7 * 24 * 3600.0, (
        "a staleness line beyond a week would let an arbitrarily old verdict "
        "paint the board, which is the failure this collector exists to "
        "prevent")


def test_the_collector_is_registered_in_collect_aux():
    """An unregistered collector is a file nobody runs."""
    import inspect
    assert "_overfit_gate_metrics" in inspect.getsource(gp.collect_aux), (
        "the overfit collector is no longer wired into collect_aux, so no "
        "overfit series reaches Grafana at all")


def test_a_collector_failure_cannot_cost_the_status_batch(monkeypatch):
    """collect_aux backstops each helper; a defect here must never take the
    equity/PnL batch down with it."""
    def boom(_ts):
        raise RuntimeError("planted")
    monkeypatch.setattr(gp, "_overfit_gate_metrics", boom)
    gp.collect_aux(time.time())      # must not raise
