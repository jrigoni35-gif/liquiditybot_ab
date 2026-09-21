# tests/test_gate_shuffle_replay.py
"""Synthetic-fixture tests for scripts/gate_shuffle_replay.py (Lane G)."""
import json as _json

import pytest

pd = pytest.importorskip("pandas")  # optional analysis stack — hygiene law

import numpy as np  # noqa: E402

from core.audit import configure_audit, get_audit  # noqa: E402
from core.codes import Code  # noqa: E402
from scripts.gate_ecology import REFUSAL_CORPUS_MISSING  # noqa: E402
from scripts.gate_shuffle_replay import (  # noqa: E402
    REFUSAL_NO_JOINED_TICKS,
    delta_pp,
    replay,
    shuffle_null,
)

CONSTS = {"vol_low_pct": 30.0, "vol_elevated_pct": 70.0,
          "vol_extreme_pct": 90.0}

# same minimal derivable-constants shape as tests/test_gate_ecology.py
CONFIG = {
    "pretrade": {"maker_fee_bps": 15.0, "taker_fee_bps": 30.0,
                 "min_edge_cost_ratio": 1.3},
    "ml": {"label_max_bars": 2},
    "vol_regime": {"fast_lookback_bars_5m": 2,
                   "low_pct": 30.0, "elevated_pct": 70.0,
                   "extreme_pct": 90.0},
}


def _rows(high_abs, high_arr, low_abs, low_arr):
    """One tick per unit row: high ticks at pct 80, low at pct 10."""
    rows = []
    for i in range(high_arr):
        rows.append({"arrivals": 1,
                     "absorbed": 1 if i < high_abs else 0,
                     "desk_pct": 80.0})
    for i in range(low_arr):
        rows.append({"arrivals": 1,
                     "absorbed": 1 if i < low_abs else 0,
                     "desk_pct": 10.0})
    return rows


def test_delta_pp_arithmetic():
    rows = _rows(high_abs=8, high_arr=10, low_abs=2, low_arr=10)
    assert delta_pp(rows, CONSTS) == pytest.approx(60.0)  # 80% - 20%


def test_delta_pp_unidentified_when_bucket_empty():
    rows = _rows(high_abs=0, high_arr=0, low_abs=5, low_arr=10)
    assert delta_pp(rows, CONSTS) is None
    out = shuffle_null(rows, CONSTS, reps=100, seed=1)
    assert out["identified"] is False
    assert "UNIDENTIFIED" in out["detail"]


def test_shuffle_null_deterministic_and_bounded():
    rows = _rows(high_abs=20, high_arr=40, low_abs=10, low_arr=40)
    a = shuffle_null(rows, CONSTS, reps=200, seed=7)
    b = shuffle_null(rows, CONSTS, reps=200, seed=7)
    assert a == b
    assert 0.0 < a["p_value"] <= 1.0
    lo, hi = a["p_value_ci95_normal"]
    assert 0.0 <= lo <= a["p_value"] <= hi <= 1.0


def test_shuffle_null_flags_planted_coupling():
    """Every high-regime arrival absorbed, no low-regime arrival absorbed:
    the null should essentially never reproduce the observed Δ."""
    rows = _rows(high_abs=40, high_arr=40, low_abs=0, low_arr=40)
    out = shuffle_null(rows, CONSTS, reps=200, seed=3)
    assert out["observed_delta_pp"] == 100.0
    assert out["p_value"] <= 0.05


def test_shuffle_null_clean_on_pure_null():
    """Absorb rate identical across regimes: observed Δ ≈ 0 sits mid-null."""
    rng = np.random.default_rng(11)
    rows = []
    for pct in (10.0, 80.0):
        for _ in range(60):
            rows.append({"arrivals": 1,
                         "absorbed": int(rng.random() < 0.5),
                         "desk_pct": pct})
    out = shuffle_null(rows, CONSTS, reps=300, seed=5)
    assert abs(out["observed_delta_pp"]) < 25.0
    assert out["p_value"] > 0.05


def test_replay_refuses_missing_corpus(tmp_path):
    configure_audit(tmp_path / "audit.jsonl")
    a = get_audit()
    a.log("entry_sweep", Code.EN_SWEEP_SUMMARY, "v1",
          {"arrivals": 4, "EN-030": 3}, counted=False)
    cfg = tmp_path / "config.json"
    cfg.write_text(_json.dumps(CONFIG))
    out = replay(audit_path=tmp_path / "audit.jsonl",
                 corpus_dir=tmp_path / "no_such_dir",
                 config_path=cfg, since=0.0, reps=10, seed=1)
    assert out["refused"] == REFUSAL_CORPUS_MISSING


def test_replay_refuses_when_nothing_joins(tmp_path):
    """Real chain, but the corpus ends before the tick timestamps: every
    tick is a corpus gap -> refused, never imputed."""
    configure_audit(tmp_path / "audit.jsonl")
    a = get_audit()
    a.log("entry_sweep", Code.EN_SWEEP_SUMMARY, "v1",
          {"arrivals": 4, "EN-030": 3}, counted=False)
    cdir = tmp_path / "corpus"
    cdir.mkdir()
    ot = [1_758_000_000_000 + i * 60_000 for i in range(50)]  # 2025, stale
    pd.DataFrame({"open_time": ot,
                  "close": [100.0] * 50}).to_parquet(
        cdir / "klines_1m_BTCUSDT.parquet")
    (cdir / "manifest.json").write_text(_json.dumps(
        {"symbols": ["BTCUSDT"], "missing_files": []}))
    cfg = tmp_path / "config.json"
    cfg.write_text(_json.dumps(CONFIG))
    out = replay(audit_path=tmp_path / "audit.jsonl", corpus_dir=cdir,
                 config_path=cfg, since=0.0, reps=10, seed=1)
    assert out["refused"] == REFUSAL_NO_JOINED_TICKS
