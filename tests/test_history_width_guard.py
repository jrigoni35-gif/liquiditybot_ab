"""Row-width invariant on the training CSV (found in the 2026-07-12 debug).

The schema check in HistoryStore guards the FILE header, not each row:
a candidate persisted before a FEATURE_NAMES bump and restored after it
carries a shorter feature vector, and labeling it wrote a short,
misaligned row under the wider header (4 such rows observed live after
the 36->43 SMC bump; every DictReader consumer saw source=None).

Two guards, both ML-013:
  * HistoryStore._append_row refuses any row whose width != header width
  * CandidateLabeler.restore drops candidates whose feature width != the
    current schema (unlabelable after a bump by construction)
"""
import logging

import numpy as np

from ml.features import FEATURE_NAMES, FEATURE_SCHEMA_VERSION
from ml.history import CandidateLabeler, HistoryStore

WANT = len(FEATURE_NAMES)
_LOGGER = "liquiditybot.ml.history"


def test_append_refuses_stale_width_row(tmp_path, caplog):
    hs = HistoryStore(str(tmp_path / "h.csv"))
    hs.log_entry("stale", "ETH", "long", np.zeros(WANT - 7))
    with caplog.at_level(logging.WARNING, logger=_LOGGER):
        hs.log_close("stale", 5.0)
    assert hs.row_count() == 0
    assert any("ML-013" in r.getMessage() for r in caplog.records)


def test_append_accepts_current_width_row(tmp_path):
    hs = HistoryStore(str(tmp_path / "h.csv"))
    hs.log_entry("ok", "ETH", "long", np.zeros(WANT))
    hs.log_close("ok", 5.0)
    assert hs.row_count() == 1


def test_restore_drops_pre_rotation_candidates(tmp_path, caplog):
    store = HistoryStore(str(tmp_path / "h.csv"))
    lab = CandidateLabeler(store, {"label_max_bars": 96})
    snapshot = {"bars": {}, "seq": 2, "last_reg": {},
                "schema_version": FEATURE_SCHEMA_VERSION,
                "cands": [
                    {"id": "cand-1", "asset": "ETH", "direction": "long",
                     "features": [0.0] * (WANT - 7), "sigma_bar": 0.01,
                     "bar_time": 1000, "spread_bps": 1.0, "gates": None},
                    {"id": "cand-2", "asset": "BTC", "direction": "long",
                     "features": [0.0] * WANT, "sigma_bar": 0.01,
                     "bar_time": 1000, "spread_bps": 1.0, "gates": None}]}
    with caplog.at_level(logging.WARNING, logger=_LOGGER):
        lab.restore(snapshot)
    # the correct-width candidate (cand-2, BTC) survives; the pre-rotation
    # one (cand-1) is dropped. Its id is re-minted onto the launch salt
    # (collision-proofing), so identify the survivor by asset, not old id.
    assert len(lab._cands) == 1 and lab._cands[0]["asset"] == "BTC"
    assert lab._cands[0]["id"].startswith(f"cand-{lab._id_salt}-")
    assert any("ML-013" in r.getMessage() and "dropped 1" in r.getMessage()
               for r in caplog.records)


def test_restore_drops_other_schema_versions_entirely(tmp_path, caplog):
    """Same width, different MEANING: a snapshot from another feature-
    schema version (or a versionless pre-v2 one) must drop every
    candidate - the width check cannot see a semantic change like the
    v2 side-relative re-encoding."""
    store = HistoryStore(str(tmp_path / "h.csv"))
    lab = CandidateLabeler(store, {"label_max_bars": 96})
    snapshot = {"bars": {}, "seq": 1, "last_reg": {},
                "cands": [{"id": "cand-1", "asset": "BTC",
                           "direction": "long",
                           "features": [0.0] * WANT, "sigma_bar": 0.01,
                           "bar_time": 1000, "spread_bps": 1.0,
                           "gates": None}]}          # no schema_version: v1
    with caplog.at_level(logging.WARNING, logger=_LOGGER):
        lab.restore(snapshot)
    assert lab._cands == []
    assert "different meaning" in caplog.text
