"""The triple-barrier label cost must reflect the real round-trip (maker x2 =
0.5%), not the old 6bps default. At 6bps a near-breakeven trade labels "win";
at the realized cost it correctly labels "loss" - the difference is exactly the
trades that teach the model to overtrade. A config_guard coherence check stops
the value silently regressing below the maker round-trip.
"""
import numpy as np

from core.config_guard import validate
from ml.labeling import triple_barrier


def _near_breakeven_path():
    # a long that drifts to +0.3% then exits at the vertical barrier: a real
    # win at 6bps cost, a real LOSS after a 0.5% round-trip.
    closes = np.array([100.0, 100.1, 100.2, 100.3], float)
    highs = closes * 1.0005
    lows = closes * 0.9995
    return closes, highs, lows


def test_label_flips_when_cost_reflects_reality():
    closes, highs, lows = _near_breakeven_path()
    # wide barriers so neither pt nor sl is touched -> vertical (time) exit
    cheap = triple_barrier(closes, highs, lows, i=0, side=1, sigma_bar=0.05,
                           pt_mult=8, sl_mult=6, max_bars=3, cost_pct=0.06)
    real = triple_barrier(closes, highs, lows, i=0, side=1, sigma_bar=0.05,
                          pt_mult=8, sl_mult=6, max_bars=3, cost_pct=0.5)
    assert cheap.barrier == "time" and real.barrier == "time"
    assert cheap.label == 1      # +0.3% - 0.06% = +0.24% -> "win" (optimistic)
    assert real.label == 0       # +0.3% - 0.5%  = -0.20% -> honest loss


def test_candidate_labeler_uses_configured_cost():
    from ml.history import CandidateLabeler, HistoryStore
    import tempfile
    import os
    fd, path = tempfile.mkstemp(suffix=".csv")
    os.close(fd)
    lab = CandidateLabeler(HistoryStore(path),
                           {"label_round_trip_cost_pct": 0.7})
    assert lab.rt_cost_pct == 0.7
    lab2 = CandidateLabeler(HistoryStore(path), {})
    assert lab2.rt_cost_pct == 0.5      # coherent default (maker x2)


def _cfg(label_cost, maker=25.0):
    return {"system": {"dry_run": True},
            "pretrade": {"maker_fee_bps": maker, "taker_fee_bps": maker + 15},
            "order_manager": {"maker_fee_bps": maker, "taker_fee_bps": maker + 15},
            "ml": {"label_round_trip_cost_pct": label_cost}}


def test_guard_warns_when_label_cost_below_maker_round_trip():
    warns = [m for sev, m in validate(_cfg(0.06)) if sev == "WARN"]
    assert any("label_round_trip_cost_pct" in m for m in warns)


def test_guard_silent_when_label_cost_covers_round_trip():
    warns = [m for sev, m in validate(_cfg(0.5)) if sev == "WARN"]
    assert not any("label_round_trip_cost_pct" in m for m in warns)
