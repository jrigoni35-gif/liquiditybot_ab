"""Task #48 — per-position exploration marker (2026-07-17 OF-5 incident).

PT-050 probes deliberately bypass the profit-EV gate to buy labels, so the
DSR gate on the mixed live sample measured tuition, not the strategy. The
marker rides: entry decision -> order.meta['probe'] -> Position.is_probe
(snapshot-safe) -> history pending tuple -> 'probe' column on the live row
-> OF-5 grades the conviction-only sample even mid-exploration.

Bookkeeping only: probe rows keep FULL live training weight (a probe's
outcome is honest ground truth) — the column changes what OF-5 samples,
never what the model trains on.
"""
import sys
from pathlib import Path

import numpy as np

from core.persistence import position_from_dict, position_to_dict
from core.state import Position
from ml.features import FEATURE_NAMES
from ml.history import HistoryStore

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from overfit_check import split_dsr_samples  # noqa: E402


def _feats(seed=1):
    return np.random.default_rng(seed).normal(0, 1, len(FEATURE_NAMES))


# --- history: the column rides the pending tuple to the live row ------------
def test_probe_flag_reaches_the_live_row(tmp_path):
    hs = HistoryStore(str(tmp_path / "h.csv"))
    hs.log_entry("probe1", "ETH", "long", _feats(1), probe=True)
    hs.log_close("probe1", net_pnl_usd=-2.0)
    hs.log_entry("conv1", "BTC", "long", _feats(2), probe=False)
    hs.log_close("conv1", net_pnl_usd=3.0)
    import csv
    rows = {r["position_id"]: r
            for r in csv.DictReader(open(hs.path, encoding="utf-8"))}
    assert rows["probe1"]["probe"] == "1"
    assert rows["conv1"]["probe"] == "0"
    # training weight is untouched: both are full live rows
    assert rows["probe1"]["source"] == rows["conv1"]["source"] == "live"
    assert hs.source_counts() == {"live": 2}


def test_candidate_rows_carry_empty_probe(tmp_path):
    hs = HistoryStore(str(tmp_path / "h.csv"))
    hs._append_row("cand1", "ETH", "long", _feats(3), 1, 0.0, "candidate")
    import csv
    row = next(csv.DictReader(open(hs.path, encoding="utf-8")))
    assert row["probe"] == ""          # not applicable, never "conviction"


def test_legacy_pending_tuples_still_close(tmp_path):
    hs = HistoryStore(str(tmp_path / "h.csv"))
    # pre-upgrade 4-tuple (no probe slot) — e.g. restored old snapshot
    hs._pending["old4"] = ("ETH", "long", _feats(4), 1234.0)
    hs.log_close("old4", net_pnl_usd=1.0)
    import csv
    row = next(csv.DictReader(open(hs.path, encoding="utf-8")))
    assert row["probe"] == "0" and row["source"] == "live"


# --- position: flag survives serialization ----------------------------------
def test_is_probe_survives_snapshot_roundtrip():
    from datetime import datetime, timezone
    p = Position(position_id="p1", symbol="ETH/USD", direction="long",
                 entry_price=100.0, size=1.0, original_size=1.0,
                 opened_at=datetime.now(timezone.utc), is_probe=True)
    assert position_from_dict(position_to_dict(p)).is_probe is True
    # pre-upgrade snapshot dicts (no key) restore as conviction
    d = position_to_dict(p)
    del d["is_probe"]
    assert position_from_dict(d).is_probe is False


# --- engine wiring: source contract -----------------------------------------
def test_engine_threads_the_marker_end_to_end():
    src = (ROOT / "main.py").read_text(encoding="utf-8")
    assert '"position_id": pid,' in src          # ML-070 audit names the probe
    assert 'is_probe=bool(order.meta.get("probe", False)),' in src
    assert 'probe=pos.is_probe)' in src          # pending tuple gets it
    # direct entry + algo meta + v10 grid-ladder rungs: every path that
    # creates an entry order must thread the exploration marker, or probe
    # fills would masquerade as conviction trades in the OF-5 ledger
    assert src.count('"probe": explored') == 3
    assert '"probe": bool(meta_t.get("probe", False)),' in src  # algo route


# --- OF-5 sample selection ---------------------------------------------------
def test_dsr_conviction_sample_excludes_probes_and_unknowns():
    rows = [{"net_pnl_usd": "1.0", "probe": "0"},    # conviction
            {"net_pnl_usd": "-5.0", "probe": "1"},   # PT-050 probe
            {"net_pnl_usd": "2.0", "probe": ""},     # pre-marker unknown
            {"net_pnl_usd": "garbage", "probe": "0"},  # unparsable -> dropped
            {"net_pnl_usd": "3.0", "probe": "0"}]    # conviction
    conviction, mixed = split_dsr_samples(rows)
    assert conviction == [1.0, 3.0]
    assert mixed == [1.0, -5.0, 2.0, 3.0]
