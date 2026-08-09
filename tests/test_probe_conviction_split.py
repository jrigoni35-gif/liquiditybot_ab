"""Probe and conviction tickets are separate populations (A3), plus the
drawdown gauge that was computed and discarded (D2).

WHY THIS MATTERS. A probe is a deliberately small exploratory ticket; a
conviction trade is the real thesis. Pooling them produces an expectancy that
describes NEITHER - probes pull the mean toward zero while conviction trades
carry the variance - and the blended figure is precisely the one an operator
reads as "how is the strategy doing". Same defect family as the hedge
exclusion in tests/test_opening_leg_pin.py: a population silently folded into
a number that then gets read as if it were homogeneous.

The "unknown" bucket is deliberate. A trade restored from a snapshot written
before this field existed has no provenance, and counting it as conviction
would inflate one side with rows nobody classified. It is reported as its own
bucket and drains as the rolling window turns over.
"""
from __future__ import annotations

import pytest

from core.performance import PerformanceTracker


def _t(cfg=None):
    return PerformanceTracker(cfg or {"perf_window_trades": 50})


def test_probe_and_conviction_are_not_pooled():
    p = _t()
    # 3 probes, small and losing; 2 conviction trades, large and winning.
    for i in range(3):
        p.record_close("ADA", -1.0, 20.0, now=float(i), is_probe=True)
    for i in range(2):
        p.record_close("ADA", +40.0, 400.0, now=float(10 + i), is_probe=False)

    snap = p.snapshot()
    conv = snap["by_conviction"]

    assert conv["probe"]["trades"] == 3
    assert conv["conviction"]["trades"] == 2
    assert conv["unknown"]["trades"] == 0

    # The pooled figure describes neither population - that is the point.
    assert snap["overall"]["expectancy_usd"] == pytest.approx(
        (3 * -1.0 + 2 * 40.0) / 5)
    assert conv["probe"]["expectancy_usd"] == pytest.approx(-1.0)
    assert conv["conviction"]["expectancy_usd"] == pytest.approx(40.0)
    assert conv["probe"]["win_rate"] == 0.0
    assert conv["conviction"]["win_rate"] == 1.0

    # overall must be unchanged by the split - this EXTENDS, never redefines
    assert snap["overall"]["trades"] == 5
    assert snap["overall"]["net_usd"] == pytest.approx(3 * -1.0 + 2 * 40.0)


def test_unknown_provenance_is_not_counted_as_conviction():
    """Absent != conviction. The silent-misattribution guard."""
    p = _t()
    p.record_close("ETH", -5.0, 100.0, now=1.0)          # is_probe omitted
    snap = p.snapshot()
    conv = snap["by_conviction"]
    assert conv["unknown"]["trades"] == 1
    assert conv["conviction"]["trades"] == 0
    assert conv["probe"]["trades"] == 0


def test_restore_of_a_pre_upgrade_snapshot_lands_in_unknown():
    """A snapshot written before the probe field existed has no such key."""
    old = {"trades": [
        {"asset": "BTC", "usd": -2.0, "ret_pct": -1.0, "r": None,
         "win": False, "ts": 1.0},                        # NOTE: no "probe"
    ]}
    p = _t()
    p.restore(old)
    conv = p.snapshot()["by_conviction"]
    assert conv["unknown"]["trades"] == 1
    assert conv["conviction"]["trades"] == 0
    assert p.snapshot()["overall"]["trades"] == 1


def test_probe_flag_survives_a_persistence_round_trip():
    p = _t()
    p.record_close("SOL", 1.0, 10.0, now=1.0, is_probe=True)
    p.record_close("SOL", 2.0, 10.0, now=2.0, is_probe=False)
    q = _t()
    q.restore(p.to_dict())
    conv = q.snapshot()["by_conviction"]
    assert conv["probe"]["trades"] == 1
    assert conv["conviction"]["trades"] == 1
    assert conv["unknown"]["trades"] == 0


def test_main_passes_is_probe_to_the_ledger():
    """AST pin: main.py's perf.record_close call must carry is_probe.

    Parsed, not grepped - main.py's surrounding comments mention is_probe,
    and a substring check would pass on the prose while the call itself
    stayed blind.
    """
    import ast
    from pathlib import Path

    src = (Path(__file__).resolve().parents[1] / "main.py").read_text(
        encoding="utf-8")
    calls = []
    for node in ast.walk(ast.parse(src)):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        if isinstance(fn, ast.Attribute) and fn.attr == "record_close":
            # only the performance ledger's call; the breaker's is separate
            obj = fn.value
            if isinstance(obj, ast.Attribute) and obj.attr == "perf":
                calls.append(node)
    assert calls, "no self.perf.record_close(...) call found in main.py"
    for c in calls:
        kw = {k.arg for k in c.keywords}
        assert "is_probe" in kw, (
            f"main.py:{c.lineno} calls perf.record_close without is_probe - "
            f"probe and conviction trades would pool into one expectancy")


def test_drawdown_is_exported_not_just_its_throttle():
    """D2: _rp_status computed drawdown_mtm_pct and discarded it.

    A dd_throttle_mult of 1.0 is identical whether drawdown is genuinely
    zero or hard_stop_dd_pct is misconfigured to a value that can never
    bind - the raw reading distinguishes them.
    """
    import ast
    from pathlib import Path

    src = (Path(__file__).resolve().parents[1] / "runner.py").read_text(
        encoding="utf-8")
    tree = ast.parse(src)
    fn = next((n for n in ast.walk(tree)
               if isinstance(n, ast.FunctionDef) and n.name == "_rp_status"),
              None)
    assert fn is not None, "_rp_status not found in runner.py"
    keys = {k.value for n in ast.walk(fn) if isinstance(n, ast.Dict)
            for k in n.keys
            if isinstance(k, ast.Constant) and isinstance(k.value, str)}
    for want in ("drawdown_mtm_pct", "hard_stop_dd_pct"):
        assert want in keys, f"_rp_status does not export {want}"


def test_gc_pusher_exports_the_new_risk_keys():
    """gc_pusher skips keys absent from its list, so the board would stay
    blank even once the runner emits them."""
    from pathlib import Path

    src = (Path(__file__).resolve().parents[1] / "scripts"
           / "gc_pusher.py").read_text(encoding="utf-8")
    for want in ("drawdown_mtm_pct", "hard_stop_dd_pct",
                 "liquiditybot_perf_conviction_"):
        assert want in src, f"gc_pusher.py never emits {want}"
