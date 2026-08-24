"""Pins for label_ret_pct (schema 93->94) and the ghost-position check.

THE DEFECT THESE PREVENT RETURNING. _emit_label computed BarrierOutcome.ret
and then wrote a literal 0.0 into net_pnl_usd for every candidate row -
measured 2026-08-24: 5,923 of 5,945 active-era rows with the outcome
magnitude destroyed, on every barrier type. Consequence: no candidate label
could ever be re-adjudicated at a corrected cost (the boundary-#5 fee fix
faces a corpus that forgot its own outcomes), and the 218 tb_time "wins"
minted at the 0.5% label cost are retroactively unanswerable at the
venue-true ~1.2%.

The pins therefore assert PRESERVATION, and the UNKNOWN convention: "" (or a
short-row None after a bak merge) is UNKNOWN, never zero - a fabricated 0.0
is indistinguishable from a genuine zero-return outcome, which is the exact
ambiguity the column exists to end.
"""
from __future__ import annotations

import csv
import logging
from pathlib import Path

import numpy as np
import pytest

from ml.history import FEATURE_NAMES, HistoryStore

logging.disable(logging.WARNING)


def _store(tmp_path) -> tuple[HistoryStore, Path]:
    p = tmp_path / "outputs" / "signal_history.csv"
    p.parent.mkdir(parents=True, exist_ok=True)
    return HistoryStore(str(p)), p


def _read(p: Path):
    with p.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def test_schema_ends_with_label_ret_pct(tmp_path):
    """Append-at-END discipline: the column must be LAST so every consumer
    written against the old width still parses by position."""
    store, _ = _store(tmp_path)
    assert store._header[-1] == "label_ret_pct"


def test_candidate_ret_survives_the_write(tmp_path):
    store, p = _store(tmp_path)
    store._append_row("c1", "ETH", "long", np.zeros(len(FEATURE_NAMES)),
                      1, 0.0, "candidate", signal_ts=1.0, barrier="tb_time",
                      label_ret_pct=0.731)
    r = _read(p)[0]
    assert r["label_ret_pct"] == "0.731000"
    # and the dollars column keeps its honest 0.0 - it was never a lie
    assert r["net_pnl_usd"] == "0.00"


def test_emit_label_passes_ret_through_THE_REAL_CALLER(tmp_path):
    """Pins the defect AT ITS SITE. The first version of this suite tested
    _append_row directly with the kwarg and passed with the bug re-planted
    in _emit_label - the corpus could not reach the branch, the same shape
    as the audit-guard test that never entered the truncation path. This one
    goes through CandidateLabeler._emit_label itself."""
    from ml.history import CandidateLabeler
    from ml.labeling import BarrierOutcome
    store, p = _store(tmp_path)
    lab = CandidateLabeler(store, {})
    cand = {"id": "cx1", "asset": "ETH", "direction": "long",
            "features": np.zeros(len(FEATURE_NAMES)), "bar_time": 1.0,
            "disp": "", "gate_components": None, "avail": None}
    out = BarrierOutcome(1, -0.83, 12, "tb_time")
    lab._emit_label(cand, out)
    r = _read(p)[0]
    assert r["label_ret_pct"] == "-0.830000", (
        "BarrierOutcome.ret was discarded at write time - the 2026-08-24 "
        "defect is back")


def test_no_value_writes_UNKNOWN_never_zero(tmp_path):
    """The old defect was a fabricated 0.0. Absence must be blank."""
    store, p = _store(tmp_path)
    store._append_row("c2", "ETH", "long", np.zeros(len(FEATURE_NAMES)),
                      0, 0.0, "candidate", signal_ts=1.0, barrier="tb_sl")
    assert _read(p)[0]["label_ret_pct"] == ""


def test_nonfinite_ret_degrades_to_UNKNOWN(tmp_path):
    store, p = _store(tmp_path)
    for bad in (float("nan"), float("inf")):
        store._append_row("c3", "ETH", "long", np.zeros(len(FEATURE_NAMES)),
                          0, 0.0, "candidate", signal_ts=1.0,
                          barrier="tb_sl", label_ret_pct=bad)
    for r in _read(p):
        assert r["label_ret_pct"] == ""


def test_live_row_carries_percent_net_of_booked_fees(tmp_path):
    store, p = _store(tmp_path)
    store._pending["pos1"] = ("ETH", "long", np.zeros(len(FEATURE_NAMES)),
                              3.0, False, "")
    store.log_close("pos1", net_pnl_usd=1.25, barrier="tb_pt",
                    entry_usd=250.0)
    r = _read(p)[0]
    assert abs(float(r["label_ret_pct"]) - 0.5) < 1e-9   # 1.25/250*100


def test_live_row_without_entry_usd_is_UNKNOWN(tmp_path):
    """entry_usd=0.0 is the pre-upgrade default - a percent cannot be
    computed, and inventing one would poison the column."""
    store, p = _store(tmp_path)
    store._pending["pos2"] = ("ETH", "long", np.zeros(len(FEATURE_NAMES)),
                              3.0, False, "")
    store.log_close("pos2", net_pnl_usd=1.25, barrier="tb_pt")
    assert _read(p)[0]["label_ret_pct"] == ""


def test_rows_stay_width_aligned(tmp_path):
    store, p = _store(tmp_path)
    store._append_row("c4", "ETH", "long", np.zeros(len(FEATURE_NAMES)),
                      1, 0.0, "candidate", signal_ts=1.0, barrier="tb_pt",
                      label_ret_pct=2.0)
    with p.open(encoding="utf-8", newline="") as f:
        raw = list(csv.reader(f))
    assert len(raw[0]) == len(raw[1])


def test_old_schema_file_rotates_and_recovers_without_row_loss(tmp_path):
    """THE ROTATION HAZARD, exercised end to end: a 93-col production file
    under the new code must rotate write-path-only, and corpus_sync's
    recover_local_baks must merge every stranded row back. The July
    schema-loss incident and the August fills hole are both this event
    class going wrong."""
    import importlib.util
    root = tmp_path
    (root / "outputs").mkdir(exist_ok=True)
    p = root / "outputs" / "signal_history.csv"
    probe = HistoryStore(str(p))
    old_header = [c for c in probe._header if c != "label_ret_pct"]
    p.unlink(missing_ok=True)     # probe does not create the file eagerly
    feats = ["0.000000"] * len(FEATURE_NAMES)
    with p.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(old_header)
        for i in range(5):
            w.writerow([f"old{i}", "ETH", "long", *feats, "1", "0.00",
                        "candidate", "1", "1", "tb_pt", "", "", "", "5m",
                        "triple_barrier_h432", "0.02", "0.01",
                        *["0.0000"] * 7, "0", "0", "", "", "", ""])
    fresh = HistoryStore(str(p))
    fresh._append_row("new1", "ETH", "long", np.zeros(len(FEATURE_NAMES)),
                      1, 0.0, "candidate", signal_ts=9.0, barrier="tb_pt",
                      label_ret_pct=1.5)
    spec = importlib.util.spec_from_file_location(
        "cs", Path(__file__).resolve().parents[1] / "scripts" /
        "corpus_sync.py")
    cs = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(cs)
    res = cs.recover_local_baks(root)
    assert "recovered" in str(res)
    rows = _read(p)
    assert len(rows) == 6, f"row loss across the bump: {len(rows)}/6"
    old = [r for r in rows if r["position_id"].startswith("old")]
    new = [r for r in rows if r["position_id"] == "new1"]
    assert len(old) == 5 and len(new) == 1
    # merged short rows read as UNKNOWN (None/""), never a fabricated value
    assert all(r.get("label_ret_pct") in ("", None) for r in old)
    assert new[0]["label_ret_pct"] == "1.500000"


# --- the ghost-position check (ledger_continuity) -----------------------

def _lc():
    import importlib.util
    import sys
    src = Path(__file__).resolve().parents[1] / "scripts" / \
        "ledger_continuity.py"
    spec = importlib.util.spec_from_file_location("ledger_continuity", src)
    if spec is None or spec.loader is None:  # pragma: no cover
        pytest.skip("ledger_continuity not importable")
    m = importlib.util.module_from_spec(spec)
    sys.modules["ledger_continuity"] = m
    spec.loader.exec_module(m)
    return m


def _fill(pid, purpose, ts, oid):
    return {"ts": str(ts), "order_id": oid, "position_id": pid,
            "purpose": purpose, "symbol": "ETH/USD", "side": "buy",
            "ordertype": "limit", "post_only": "1", "attempt": "0",
            "fill_size": "1", "fill_price": "100", "arrival_ref": "",
            "slip_bps": "0", "fees_delta_usd": "0.04", "remaining": "0",
            "reason": "", "exec_era": ""}


def _write_fills(out: Path, rows):
    cols = list(rows[0].keys())
    with (out / "fills.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def _write_corpus(out: Path, pids):
    with (out / "signal_history.csv").open("w", newline="",
                                           encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["position_id", "label"])
        for p in pids:
            w.writerow([p, "1"])


def test_ghost_position_is_detected(tmp_path):
    """Closed >48h, entry+exit fills, no corpus row -> ghost. The measured
    instance is the stale-binary window (34 + 3 positions, 07-29..08-02)."""
    import time
    lc = _lc()
    out = tmp_path
    old = time.time() - 5 * 86400
    _write_fills(out, [_fill("ghost1", "entry", old, "o1"),
                       _fill("ghost1", "exit", old + 60, "o2"),
                       _fill("lab1", "entry", old, "o3"),
                       _fill("lab1", "exit", old + 60, "o4")])
    _write_corpus(out, ["lab1"])
    res = lc.scan(out)
    assert res["ghost_positions"] == 1
    assert res["ghost_sample"] == ["ghost1"]


def test_recent_close_is_inside_grace_not_a_ghost(tmp_path):
    import time
    lc = _lc()
    out = tmp_path
    now = time.time() - 3600
    _write_fills(out, [_fill("young", "entry", now, "o1"),
                       _fill("young", "exit", now + 60, "o2")])
    _write_corpus(out, [])
    assert lc.scan(out)["ghost_positions"] == 0


def test_open_position_is_not_a_ghost(tmp_path):
    """Entry without exit = still open; no label is EXPECTED yet."""
    import time
    lc = _lc()
    out = tmp_path
    old = time.time() - 5 * 86400
    _write_fills(out, [_fill("openpos", "entry", old, "o1")])
    _write_corpus(out, [])
    assert lc.scan(out)["ghost_positions"] == 0
