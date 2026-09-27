"""Tests for decisioning-coupling fixes R1-R3 (2026-09-19).

R1: VolState.sigma_bar_pct_measured centralizes the placeholder guard on
    the producer (main._measured_sigma now delegates to it).
R2: Position.tier_trigger_snapshots freezes tiers 2-4 effective triggers at
    the moment the preceding tier fires; the freeze survives a persistence
    round-trip and a post-fire vol spike cannot retroactively move them.
R3: OrderManager.check_fee_reconciliation persists a mismatch as a
    PROPOSAL file (outputs/fee_recon/latest_proposal.json), never applied.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from core.persistence import position_from_dict, position_to_dict
from core.state import Position
from execution import order_manager as om_mod
from execution.order_manager import OrderManager
from regime.vol_regime import VolState
from risk.profit_tiers import ProfitTierEngine


def _pos(tier_closed: int = 0) -> Position:
    return Position(
        position_id="p1", symbol="BTC", direction="long",
        entry_price=100.0, size=1.0, original_size=1.0,
        opened_at=datetime(2026, 9, 19, tzinfo=timezone.utc),
        tier_closed=tier_closed)


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


# --- R2 -----------------------------------------------------------------

def _engine(vol_scaled: bool = True) -> ProfitTierEngine:
    return ProfitTierEngine({
        "vol_scaled": vol_scaled,
        "tier_1": {"trigger_pct_gain": 1.0, "trigger_vol_mult": 1.0,
                   "close_pct_of_position": 25.0},
        "tier_2": {"trigger_pct_gain": 2.0, "trigger_vol_mult": 2.0,
                   "close_pct_of_position": 25.0},
        "tier_3": {"trigger_pct_gain": 3.0, "close_pct_of_position": 25.0},
        "tier_4": {"trigger_pct_gain": 4.0, "close_pct_of_position": 25.0},
    })


def test_r2_snapshot_written_at_tier_fire():
    eng = _engine()
    pos = _pos()
    # sigma 0.5%/bar -> tier-1 trigger = 1.0 * 0.5 = 0.5%
    act = eng.evaluate(pos, 100.5, sigma_bar_pct=0.5)
    assert act.should_close_partial and act.is_profit_take
    # the firing regime's MEASURED sigma is frozen for tier 2 (its trigger
    # is then 2.0 * 0.5 = 1.0% under the CURRENT engine scale)
    assert pos.tier_trigger_snapshots.get("1") == pytest.approx(0.5)


def test_r2_snapshot_survives_vol_spike():
    eng = _engine()
    pos = _pos()
    eng.evaluate(pos, 100.5, sigma_bar_pct=0.5)       # tier 1 fires
    pos.tier_closed = 1
    # vol triples: live recompute would put tier 2 at 4.0%; the freeze
    # must hold it at the snapshotted 1.0% so gain 1.0% still fires it.
    act = eng.evaluate(pos, 101.0, sigma_bar_pct=1.5)
    assert act.should_close_partial and act.is_profit_take
    assert act.tier_fired == 2


def test_r2_no_snapshot_means_live_recompute():
    eng = _engine()
    pos = _pos()
    # below tier-1 trigger: nothing fires, nothing freezes
    act = eng.evaluate(pos, 100.2, sigma_bar_pct=0.5)
    assert not act.should_close_partial
    assert pos.tier_trigger_snapshots == {}


def test_r2_persistence_roundtrip():
    pos = _pos()
    pos.tier_trigger_snapshots = {"1": 1.0, "2": 2.5}
    back = position_from_dict(position_to_dict(pos))
    assert back.tier_trigger_snapshots == {"1": 1.0, "2": 2.5}


def test_r2_legacy_snapshot_dict_defaults_empty():
    d = position_to_dict(_pos())
    d.pop("tier_trigger_snapshots")                    # pre-R2 snapshot
    assert position_from_dict(d).tier_trigger_snapshots == {}


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


# --- R3 proposal completeness (review 2026-09-26) ----------------------

def test_r3_applied_proposal_passes_config_guard(tmp_path, monkeypatch):
    """The dangerous direction (venue tier ABOVE config, same shape as the
    one real OM-080 row): applying the proposal verbatim must yield a
    config that boots - four of six fee keys FATALs on the label cost."""
    import copy
    from core import config_guard
    cfg = json.loads((Path(__file__).resolve().parents[1]
                      / "config.json").read_text(encoding="utf-8"))
    monkeypatch.chdir(tmp_path)
    om = _om(_Feed(40.0, 80.0), maker=15.0, taker=30.0)
    om.check_fee_reconciliation(now=1000.0)
    prop = json.loads(_proposal_path().read_text())
    new = copy.deepcopy(cfg)
    for key, val in prop["proposed_config_values"].items():
        sec, leaf = key.split(".")
        new[sec][leaf] = val
    assert [f for f in config_guard.validate(new) if f[0] == "FATAL"] == []


def test_r3_resolved_mismatch_clears_stale_proposal(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    feed = _Feed(25.0, 50.0)
    om = _om(feed)
    om.check_fee_reconciliation(now=1000.0)
    assert _proposal_path().exists()
    feed._m, feed._t = 40.0, 80.0                     # operator re-booked
    om.check_fee_reconciliation(now=1000.0 + 2 * 3600.0)
    assert not _proposal_path().exists()


# --- R2 coupling pins (review 2026-09-26) ------------------------------

def _scaled_engine(key: float) -> ProfitTierEngine:
    """main._tier_engine's scaling rule: trigger_pct_gain AND
    trigger_vol_mult both x key (macro tier_scale, inventory bleed 0.75)."""
    import json as _json
    base = _json.loads(_json.dumps({
        "vol_scaled": True,
        "tier_1": {"trigger_pct_gain": 1.0, "trigger_vol_mult": 1.0,
                   "close_pct_of_position": 25.0},
        "tier_2": {"trigger_pct_gain": 2.0, "trigger_vol_mult": 2.0,
                   "close_pct_of_position": 25.0},
        "tier_3": {"trigger_pct_gain": 3.0, "close_pct_of_position": 25.0},
        "tier_4": {"trigger_pct_gain": 4.0, "close_pct_of_position": 25.0}}))
    for i in range(1, 5):
        t = base[f"tier_{i}"]
        t["trigger_pct_gain"] = float(t["trigger_pct_gain"]) * key
        if "trigger_vol_mult" in t:
            t["trigger_vol_mult"] = float(t["trigger_vol_mult"]) * key
    return ProfitTierEngine(base)


def test_r2_engine_scale_still_applies_after_freeze():
    # sigma CONSTANT, inventory crosses the soft cap after tier 1 ->
    # main scales the engine x0.75; tier 2 must follow the live scale.
    pos = _pos()
    assert _scaled_engine(1.0).evaluate(pos, 100.5,
                                        sigma_bar_pct=0.5).tier_fired == 1
    pos.tier_closed = 1
    act = _scaled_engine(0.75).evaluate(pos, 100.8, sigma_bar_pct=0.5)
    assert act.should_close_partial and act.tier_fired == 2


def test_r2_unmeasured_sigma_is_never_frozen():
    eng = _engine()
    pos = _pos()
    assert eng.evaluate(pos, 101.0, sigma_bar_pct=None).tier_fired == 1
    assert pos.tier_trigger_snapshots == {}
    pos.tier_closed = 1
    act = eng.evaluate(pos, 101.2, sigma_bar_pct=0.3)   # live tier 2 = 1.0
    assert act.should_close_partial and act.tier_fired == 2


def test_r2_refire_while_resting_keeps_first_snapshot():
    eng = _engine()
    pos = _pos()
    eng.evaluate(pos, 100.5, sigma_bar_pct=0.5)
    eng.evaluate(pos, 102.0, sigma_bar_pct=1.5)        # take still resting
    assert pos.tier_trigger_snapshots == {"1": 0.5}


@pytest.mark.parametrize("bad", [{"1": None}, {"1": "x"}, ["1", 2.0],
                                 "garbage", 5, {"1": float("nan")},
                                 {"1": float("inf")}, {"1": -3.0}])
def test_r2_malformed_snapshot_restores_without_raising(bad):
    d = position_to_dict(_pos())
    d["tier_trigger_snapshots"] = bad
    assert position_from_dict(d).tier_trigger_snapshots == {}


def test_r2_negative_snapshot_never_fires_a_loss_as_profit_take():
    pos = _pos(tier_closed=1)
    pos.tier_trigger_snapshots = {"1": -3.0}           # corrupt in memory
    act = _engine().evaluate(pos, 99.0, sigma_bar_pct=0.5)
    assert not act.is_profit_take


