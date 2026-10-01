"""Pins for scripts/info_screen.py and scripts/conviction_value_report.py
(both REPORT-ONLY, 2026-10-01)."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import conviction_value_report as cv  # noqa: E402
import info_screen as S  # noqa: E402


def _tape(tmp_path, trades):
    # optional analysis stack: skip, never break collection
    # (tests/test_dependency_hygiene.py simulates its absence)
    pd = pytest.importorskip("pandas")
    pytest.importorskip("pyarrow")
    d = tmp_path / "XBTUSD"
    d.mkdir(parents=True)
    pd.DataFrame(trades, columns=["time_s", "price", "volume", "side",
                                  "otype"]).to_parquet(d / "2026-09.parquet")
    return S.Tape(d)


def test_flow_is_signed_notional_imbalance_inside_the_window(tmp_path):
    tp = _tape(tmp_path, [(100.0, 10.0, 3.0, "b", "m"),     # +30
                          (200.0, 10.0, 1.0, "s", "l"),     # -10
                          (900.0, 10.0, 5.0, "s", "m")])    # outside [0, 300)
    assert tp.flow(0.0, 300.0) == pytest.approx((30 - 10) / 40)
    assert tp.mkt_flow(0.0, 300.0) == pytest.approx(1.0)   # only the market buy


def test_signals_never_see_a_trade_at_or_after_the_cutoff(tmp_path):
    rows = [(float(t), 10.0, 1.0, "s", "l") for t in range(0, 7300, 10)]
    rows.append((7300.0, 10.0, 1000.0, "b", "m"))            # AT the cutoff
    tp = _tape(tmp_path, rows + [(9000.0, 10.0, 1.0, "s", "l")])
    s = S.signals_at(tp, None, 7300.0)
    assert s["flow_5m"] == pytest.approx(-1.0)               # the big buy unseen


def test_large_trade_threshold_comes_from_the_first_week_only(tmp_path):
    day = 86400.0
    early = [(i * 60.0, 10.0, 1.0, "b", "l") for i in range(100)]
    late = [(8 * day + i, 10.0, 1e6, "b", "l") for i in range(100)]
    tp = _tape(tmp_path, early + late)
    assert tp.large_thr == pytest.approx(10.0)               # not the 1e7 later


def test_within_day_auc_averages_per_day():
    x = np.array([1.0, 2.0, 3.0, 4.0, 1.0, 2.0, 3.0, 4.0])
    y = np.array([0, 0, 1, 1, 1, 1, 0, 0])
    d = np.array([1, 1, 1, 1, 2, 2, 2, 2])
    wd, per = S.within_day_auc(x, y, d)
    assert per.tolist() == [1.0, 0.0] and wd == pytest.approx(0.5)
    assert S.auc(x, y) == pytest.approx(0.5)


def test_implied_delta_is_signed_and_monotone():
    assert S.implied_delta(0.5) == 0.0
    assert S.implied_delta(0.625) == pytest.approx(1.2)
    assert S.implied_delta(0.375) == pytest.approx(-1.2)


def test_render_carries_the_path_overlap_warning():
    r = {"counting": {"line": "counting CS-1: ok"}, "rows_scored": 1,
         "days": 1, "base_up": 0.5, "assets": {}, "bonferroni": 0.007,
         "p_floor": 0.05,
         "signals": {"flow_5m": {"n": 1, "within_day_auc": 0.5,
                                 "ci": (0.5, 0.5), "null_p": 1.0,
                                 "pooled_auc": 0.5, "implied_delta": 0.0}}}
    assert "BIASED FOR PATH-DERIVED SCORES" in S.render(r)


def test_conviction_bins_partition_rows_by_rank():
    rng = np.random.default_rng(0)
    p = rng.random(1000)
    y = (rng.random(1000) < p).astype(float)
    day = np.repeat(np.arange(10), 100)
    b = cv.bins(p, y, day, 5, rng)
    assert sum(x["n"] for x in b) == 1000
    assert [x["p_lo"] for x in b] == sorted(x["p_lo"] for x in b)
    assert b[-1]["win"] > b[0]["win"]                       # skill shows


def test_conviction_report_isolates_the_audit_trail():
    src = (ROOT / "scripts" / "conviction_value_report.py").read_text(
        encoding="utf-8")
    run_src = src[src.index("def run("):src.index("def render(")]
    assert run_src.index("configure_audit(") < run_src.index("load(root)")
