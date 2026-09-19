"""Tests for decisioning-coupling fixes R1+R3 (2026-09-19).

R1: VolState.sigma_bar_pct_measured centralizes the placeholder guard on
    the producer (main._measured_sigma now delegates to it).
R3: OrderManager.check_fee_reconciliation persists a mismatch as a
    PROPOSAL file (outputs/fee_recon/latest_proposal.json), never applied.

R2 (Position.tier_trigger_snapshots) is intentionally NOT in this branch:
it changes when tiers 2-4 fire under post-fire vol spikes, which is
arguably exit geometry under the era-9 accrual moratorium. It ships on
fix/decisioning-coupling-r123 after operator adjudication.
"""

import json
from pathlib import Path

from execution import order_manager as om_mod
from execution.order_manager import OrderManager
from regime.vol_regime import VolState


# --- R1 -----------------------------------------------------------------

def test_r1_unmeasured_sigma_is_none():
    st = VolState(asset="BTC")
    assert st.measured is False
    assert st.sigma_bar_pct_measured is None
    # the raw placeholder remains available for non-decision consumers
    assert st.sigma_bar_pct == 0.05


def test_r1_measured_sigma_returns_value():
    st = VolState(asset="BTC", sigma_bar_pct=0.31, measured=True)
    assert st.sigma_bar_pct_measured == 0.31


# --- R3 -----------------------------------------------------------------

class _Feed:
    def __init__(self, actual_maker: float, actual_taker: float):
        self._m, self._t = actual_maker, actual_taker

    def has_private_credentials(self):
        return True

    def get_trade_fee_schedule(self, pairs):
        return {"pairs": {p: {"maker_bps": self._m, "taker_bps": self._t}
                          for p in pairs},
                "volume_30d": 12345.0, "volume_currency": "USD"}


def _om(feed, maker=40.0, taker=80.0):
    return OrderManager(feed, {
        "maker_fee_bps": maker, "taker_fee_bps": taker,
        "fee_recon": {"enabled": True, "tolerance_bps": 1.0,
                      "interval_hours": 1.0}},
        dry_run=True, pair_meta={"XXBTZUSD": {"price_decimals": 2}})


def _proposal_path() -> Path:
    # read via the module attr, not a hardcoded relative path: the conftest
    # _sidecar_logs_to_tmp redirect points it at this test's tmp dir during
    # the battery, so the literal outputs/fee_recon/... shape only exists
    # in production.
    return Path(om_mod._FEE_PROPOSAL_REL_PATH)


def test_r3_mismatch_writes_proposal(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    om = _om(_Feed(25.0, 50.0))          # venue cheaper, but far past 1bp tol
    om.check_fee_reconciliation(now=1000.0)
    prop = json.loads(_proposal_path().read_text())
    assert prop["applied"] is False
    assert prop["recon"]["mismatched_pairs"] == ["XXBTZUSD"]
    # fail-conservative: both configured sources proposed together at the
    # venue actuals; never applied to the live config
    assert prop["proposed_config_values"]["order_manager.maker_fee_bps"] == 25.0
    assert prop["proposed_config_values"]["pretrade.taker_fee_bps"] == 50.0
    assert om.maker_fee_bps == 40.0 and om.taker_fee_bps == 80.0


def test_r3_no_mismatch_no_proposal(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    om = _om(_Feed(40.0, 80.0))          # venue matches config exactly
    om.check_fee_reconciliation(now=1000.0)
    assert not _proposal_path().exists()
