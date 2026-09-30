"""Pins for scripts/pipeline_congruence_report.py (REPORT-ONLY)."""
from __future__ import annotations

import ast
import csv
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import pipeline_congruence_report as pc  # noqa: E402
from ml.labeling import triple_barrier  # noqa: E402


@pytest.mark.parametrize("seed", range(40))
def test_rederive_agrees_with_the_labeler_it_audits(seed):
    rng = np.random.default_rng(seed)
    n = 200
    c = 100 * np.cumprod(1 + rng.normal(0, 0.004, n))
    h = c * (1 + np.abs(rng.normal(0, 0.002, n)))
    lo = c * (1 - np.abs(rng.normal(0, 0.002, n)))
    t = np.arange(n, dtype=float) * 300
    side = 1 if seed % 2 else -1
    sigma = 0.002
    out = triple_barrier(c, h, lo, 5, side, sigma, 8.0, 6.0, 120,
                         cost_pct=0.45)
    bar, held = pc.rederive(t, c, h, lo, 5, side, 8.0 * sigma, 6.0 * sigma,
                            120)
    assert bar == f"tb_{out.barrier}"
    assert held == out.bars_held


@pytest.mark.parametrize("side", [1, -1])
def test_a_bar_touching_both_barriers_resolves_as_the_stop(side):
    # one wide bar spans BOTH barriers: the labeler is conservative (stop
    # first) and the audit must agree - random paths never exercise this
    t = np.arange(4, dtype=float) * 300
    c = np.full(4, 100.0)
    h = np.array([100.0, 103.0, 100.0, 100.0])
    lo = np.array([100.0, 97.0, 100.0, 100.0])
    out = triple_barrier(c, h, lo, 0, side, 0.002, 8.0, 6.0, 3,
                         cost_pct=0.45)
    bar, held = pc.rederive(t, c, h, lo, 0, side, 0.016, 0.012, 3)
    assert out.barrier == "sl" and bar == "tb_sl" and held == 1


def test_rederive_reports_gaps_and_incomplete_windows():
    t = np.array([0, 300, 900, 1200], float)          # a missing bar
    c = np.full(4, 100.0)
    assert pc.rederive(t, c, c, c, 0, 1, 0.1, 0.1, 3)[0] == "gap"
    t2 = np.arange(3, dtype=float) * 300
    c2 = np.full(3, 100.0)
    assert pc.rederive(t2, c2, c2, c2, 0, 1, 0.1, 0.1, 10)[0] is None


def _row(pid, ts):
    return {"source": "candidate", "position_id": pid,
            "signal_ts": str(ts)}


def test_funnel_reconciles_and_flags_reuse_and_duplicates():
    rows = [_row("cand-aaaaaaaa-10", 10), _row("cand-aaaaaaaa-11", 11),
            _row("cand-aaaaaaaa-11", 11),                # duplicate row
            _row("cand-bbbbbbbb-11", 12),                # seq reused by salt b
            _row("cand-bbbbbbbb-14", 14)]
    f = pc.funnel(rows, {"cand-bbbbbbbb-13"}, since=0)
    assert f["minted"] == 5 and f["written"] == 3
    assert f["pending_now"] == 1 and f["never_written"] == 1
    assert f["duplicate_row_ids"] == 1
    assert f["seq_reused_across_salts"] == 1
    assert f["counting"]["ok"]


def test_live_rows_match_the_fills_ledger(tmp_path):
    fills = tmp_path / "fills.csv"
    with open(fills, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["position_id", "purpose", "side", "fill_price",
                    "fill_size", "fees_delta_usd", "remaining"])
        w.writerow(["P", "entry", "buy", "100", "1", "0.1", "1"])
        w.writerow(["P", "exit", "sell", "102", "1", "0.1", "0"])
        w.writerow(["Q", "entry", "buy", "100", "1", "0.1", "1"])
        w.writerow(["Q", "exit", "sell", "101", "1", "0.1", "0"])
    rows = [{"source": "live", "position_id": "P", "signal_ts": "5",
             "net_pnl_usd": "1.80"},
            {"source": "live", "position_id": "Q", "signal_ts": "5",
             "net_pnl_usd": "5.00"},                    # disagrees
            {"source": "live", "position_id": "Z", "signal_ts": "5",
             "net_pnl_usd": "1.00"}]
    out = pc.live_vs_fills(rows, fills, since=0)
    assert out["counts"] == {"match": 1, "pnl_mismatch": 1, "no_fills": 1}
    assert out["counting"]["ok"]


def test_training_uses_the_engine_seam_never_the_bare_store():
    """The bare HistoryStore(path) defaults max_bars to 96 and selects the
    legacy era - this script's own first run fell into it (5,287 vs the
    engine's 24,573). Pinned on the CODE, not on text."""
    tree = ast.parse((ROOT / "scripts" / "pipeline_congruence_report.py")
                     .read_text(encoding="utf-8"))
    called = {n.func.id for n in ast.walk(tree)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    assert "store_for_config" in called
    assert "HistoryStore" not in called


def test_a_double_count_never_prints_ok(monkeypatch):
    class FakeStore:
        max_bars = 432
        last_load_stats = {"label_era": {"triple_barrier_h432": {"rows": 5},
                                         "legacy": {"rows": 10}}}

        def load_training_data(self, **kw):
            return (np.zeros((5, 2)), np.zeros(5), np.ones(5), np.zeros(5),
                    np.zeros(5))

    import ml.history as mh
    monkeypatch.setattr(mh, "store_for_config", lambda *a, **k: FakeStore())
    root = Path(__file__).resolve().parents[1]
    d = pc.training(root, n_disk=12)        # 5 + 10 > 12
    assert d["counting"]["ok"] is False
    assert "DOUBLE-COUNT" in d["counting"]["line"]
