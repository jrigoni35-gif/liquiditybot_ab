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


# ==========================================================================
# C5 - the `dsr` family token is shared, and last-write-wins silenced the
# anti-silencing sentinel IN BOTH DIRECTIONS (2026-09-13)
#
# Two rungs legitimately report under `dsr`: the pooled OF-5 verdict
# (overfit_check.py:1772) and the deployed-era regression sentinel (:629).
# The sharing is DELIBERATE and documented at overfit_check.py:347-351 - a
# distinct name would spam "NEWLY ARMED" or fire "ARMING REGRESSED" (exit 3)
# while the era is young - so the defect is in this consumer, not there.
#
# Injected before fixing: a sentinel PASS drove rung_passed{rung="dsr"}
# 0 -> 1.0 while the report still read FAIL, and overfit_failed 1 -> 0; a
# sentinel FAIL was byte-identical to the pooled red, so a genuine
# deployed-era regression was equally invisible.
# ==========================================================================

_POOLED_FAIL = "- **FAIL** dsr: P(true SR > sr0) on conviction-only sample - x"
_POOLED_PASS = "- **PASS** dsr: P(true SR > sr0) on conviction-only sample - x"
_SENT_PASS = "- **PASS** dsr: deployed-era regression sentinel - ub95 >= 0"
_SENT_FAIL = "- **FAIL** dsr: deployed-era regression sentinel - ub95 < 0"
_OTHER = "- **PASS** pbo: DEPLOYED selection not dominated by luck - x"


class TestDsrFamilyTokenCollision:
    def test_a_sentinel_PASS_cannot_green_a_pooled_RED(self):
        """The exact silencing that was measured."""
        r = parse_overfit_report(_POOLED_FAIL + "\n" + _SENT_PASS)
        assert r["rungs"]["dsr"] is False, \
            "a sentinel PASS overwrote the pooled FAIL - the red is silenced"
        assert r["failed"] == 1 and r["passed"] == 0

    def test_the_silencing_is_order_independent(self):
        """Emission order is an implementation detail of main(); the merge
        must not depend on it."""
        r = parse_overfit_report(_SENT_PASS + "\n" + _POOLED_FAIL)
        assert r["rungs"]["dsr"] is False

    def test_a_sentinel_FAIL_beside_a_pooled_PASS_is_also_caught(self):
        """The OTHER direction, which is the one that matters when the pooled
        red eventually clears: a deployed-era regression must not be hidden by
        a green pooled verdict."""
        r = parse_overfit_report(_POOLED_PASS + "\n" + _SENT_FAIL)
        assert r["rungs"]["dsr"] is False
        assert r["failed"] == 1

    def test_both_green_stays_green(self):
        """NEGATIVE ARM: the merge must not manufacture a red."""
        r = parse_overfit_report(_POOLED_PASS + "\n" + _SENT_PASS)
        assert r["rungs"]["dsr"] is True
        assert r["passed"] == 1 and r["failed"] == 0

    def test_collisions_are_counted_and_observable(self):
        """A silent merge is how the next token collision hides. Zero when
        tokens are distinct, non-zero when they are not - both arms."""
        assert parse_overfit_report(
            _POOLED_FAIL + "\n" + _OTHER)["rung_collisions"] == 0
        assert parse_overfit_report(
            _POOLED_FAIL + "\n" + _SENT_PASS)["rung_collisions"] == 1

    def test_the_armed_count_follows_the_family_convention(self):
        """armed counts FAMILIES, matching overfit_check.armed_families, which
        deliberately treats both rungs as the `dsr` family. Two dsr lines plus
        one pbo line is TWO families, not three."""
        r = parse_overfit_report(
            _POOLED_FAIL + "\n" + _SENT_PASS + "\n" + _OTHER)
        assert r["armed"] == 2


import re  # noqa: E402  (C6 parity pin)


# ==========================================================================
# C6 - the rung regex dropped every BRACKETED family (2026-09-13)
#
# The battery emits bracketed family tokens at overfit_check.py:855
# (plateau[...]), :860 (monotone[...]) and :1443 (gap[...]). The character
# class `[A-Za-z0-9_\-]+` matched none of them, so a bracketed rung -
# INCLUDING A FAILING ONE - contributed nothing to passed/failed/armed, and
# no dashboard tile compensated because overfit_failed derives from this same
# parse. CLAUDE.md calls the armed count "the number to read"; it was
# under-countable by construction.
#
# LATENT, NOT LIVE - measured, not assumed. This parser landed 2026-09-12
# (5dc0b861); the only bracketed reports on disk are archived, stamped
# 2026-07-08..07-18. No published number was ever wrong.
#
# The pin below is PARITY WITH THE AUTHORITY, not a regex restatement: the
# docstring says this uses "the SAME convention armed_families uses", so the
# test asserts that sentence. A regex pin would drift from the thing it is
# supposed to track - which is how the defect got here.
# ==========================================================================

def _armed_families_reference(lines):
    """scripts/overfit_check.armed_families, applied to report LINES.

    Imported rather than reimplemented where possible; falls back to the
    documented one-liner so the pin still runs if the battery module cannot
    be imported in this environment.
    """
    try:
        import importlib.util
        import sys as _sys
        from pathlib import Path as _Path
        root = _Path(__file__).resolve().parent.parent
        spec = importlib.util.spec_from_file_location(
            "_of_check", root / "scripts" / "overfit_check.py")
        if spec and spec.loader:
            mod = importlib.util.module_from_spec(spec)
            _sys.modules["_of_check"] = mod
            spec.loader.exec_module(mod)
            report = []
            for ln in lines:
                m = re.match(r"^- \*\*(PASS|FAIL)\*\* (.*)$", ln)
                if m:
                    report.append((m.group(1), m.group(2), ""))
            return mod.armed_families(report)
    except Exception:
        pass
    out = set()
    for ln in lines:
        m = re.match(r"^- \*\*(PASS|FAIL)\*\* (.*)$", ln)
        if m:
            out.add(m.group(2).split(":")[0].strip())
    return out


_BRACKETED = [
    "- **PASS** gap[logistic]: OOF gap within memorization band - gap=+0.025",
    "- **PASS** gap[gbt]: OOF gap within memorization band - gap=+0.074",
    "- **FAIL** plateau[gbt_d2_lr10]: best not a knife-edge - peak=0.71",
    "- **PASS** monotone[gbt]: stricter gate => fewer entries",
]
_PLAIN = [
    "- **PASS** pbo: DEPLOYED selection not dominated by luck - pbo=0.19",
    "- **FAIL** dsr: P(true SR > sr0) on conviction-only sample - dsr=0.006",
]


class TestBracketedRungFamilies:
    def test_a_bracketed_family_is_parsed_at_all(self):
        r = parse_overfit_report("\n".join(_BRACKETED))
        assert r["armed"] == 4, f"bracketed rungs dropped: {r['rungs']}"
        assert "gap[gbt]" in r["rungs"]
        assert "plateau[gbt_d2_lr10]" in r["rungs"]

    def test_a_FAILING_bracketed_rung_reaches_the_failed_count(self):
        """The consequence that matters: a red that cannot be counted is a red
        that cannot page anyone."""
        with_it = parse_overfit_report("\n".join(_PLAIN + _BRACKETED))
        without = parse_overfit_report("\n".join(
            _PLAIN + [x for x in _BRACKETED if "plateau" not in x]))
        assert with_it["failed"] == without["failed"] + 1, (
            "a FAILING bracketed rung is invisible in the failed count")

    def test_families_are_NOT_collapsed_to_their_stem(self):
        """armed_families keeps gap[gbt] whole (split on ':' only), so three
        gap variants are THREE families. Collapsing them would under-count
        arming in the other direction."""
        r = parse_overfit_report("\n".join(_BRACKETED))
        assert "gap" not in r["rungs"]
        assert {"gap[logistic]", "gap[gbt]"} <= set(r["rungs"])

    def test_parity_with_armed_families_on_bracketed_input(self):
        """THE LOAD-BEARING PIN. The docstring claims this parse uses the same
        convention as overfit_check.armed_families. Assert the claim, so the
        two cannot drift - drifting is exactly how C6 happened."""
        lines = _PLAIN + _BRACKETED
        assert set(parse_overfit_report("\n".join(lines))["rungs"]) == \
            _armed_families_reference(lines)

    def test_parity_holds_on_the_report_actually_on_disk(self):
        """Non-vacuity against real data rather than only fixtures."""
        from pathlib import Path as _P
        rep = _P(__file__).resolve().parent.parent / "outputs" / "overfit_report.md"
        if not rep.exists():
            import pytest as _pt
            _pt.skip("no overfit_report.md on disk")
        text = rep.read_text(encoding="utf-8", errors="replace")
        lines = [ln for ln in text.splitlines() if ln.startswith("- **")]
        assert set(parse_overfit_report(text)["rungs"]) == \
            _armed_families_reference(lines)

    def test_plain_families_are_unchanged(self):
        """NEGATIVE ARM: the widened class must not alter existing behaviour."""
        r = parse_overfit_report("\n".join(_PLAIN))
        assert set(r["rungs"]) == {"pbo", "dsr"}
        assert (r["passed"], r["failed"], r["armed"]) == (1, 1, 2)

    def test_an_INFO_line_is_still_not_a_rung(self):
        """INFO lines can never move the exit code and must stay unparsed -
        the widened class must not start swallowing them."""
        r = parse_overfit_report(
            "- **INFO** gap[gbt]: no viable folds\n" + _PLAIN[0])
        assert set(r["rungs"]) == {"pbo"}
