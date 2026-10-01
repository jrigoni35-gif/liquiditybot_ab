"""Per-asset venue leverage caps (2026-10-01).

Operator: "correlate all assets with the leverage options appropriate for my
location" - Alabama, Kraken US retail margin. Kraken's US table (read
2026-10-01): 20x BTC; 10x ADA AVAX DOGE ETH LINK LTC SOL SUI XRP; 5x DOT
PAXG; ARB MINA FLOW not marginable for US clients.
"""
from __future__ import annotations

import ast
import copy
import json
from pathlib import Path

import pytest

from core.config_guard import validate
from risk.leverage import LeverageGovernor

ROOT = Path(__file__).resolve().parents[1]
CFG = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
KRAKEN_US = {"BTC": 20, "ETH": 10, "LINK": 10, "ADA": 10, "SOL": 10,
             "XRP": 10, "DOGE": 10, "SUI": 10, "AVAX": 10, "LTC": 10,
             "PAXG": 5, "DOT": 5}
NOT_MARGINABLE_US = ("ARB", "MINA", "FLOW")


def _gov(**over):
    lev = dict(CFG["leverage"])
    # the governor floors vol at 5%, so the shipped 35% target tops out at
    # 7x - raise it so the CAPS (not the vol target) are what bind here
    lev["target_vol_annual_pct"] = 1000
    lev.update(over)
    return LeverageGovernor(lev)


def _lev(gov, asset, sigma=1.0, regime=50.0):
    return gov.allowed_leverage(sigma, regime, 0.0, asset=asset)[0]


def test_shipped_table_matches_the_venue_for_every_traded_asset():
    caps = {k: v for k, v in CFG["leverage"]["asset_max_leverage"].items()
            if not k.startswith("_")}
    assert caps == KRAKEN_US
    for a in NOT_MARGINABLE_US:
        assert a not in caps                     # spot only via the default
    assert CFG["leverage"]["unlisted_asset_max_leverage"] == 1.0


@pytest.mark.parametrize("asset,expect", [("PAXG", 5.0), ("DOT", 5.0),
                                          ("ETH", 10.0), ("BTC", 10.0),
                                          ("ARB", 1.0), ("MINA", 1.0),
                                          ("FLOW", 1.0), ("paxg", 5.0)])
def test_entry_leverage_is_clamped_to_the_assets_venue_cap(asset, expect):
    # BTC: venue 20x, region ceiling 10x still binds
    assert _lev(_gov(), asset) == pytest.approx(expect)


def test_no_asset_named_is_exactly_the_legacy_behaviour():
    assert _lev(_gov(), None) == pytest.approx(
        float(CFG["leverage"]["region_max_leverage"]))


def test_no_table_configured_is_exactly_the_legacy_behaviour():
    lev = {k: v for k, v in CFG["leverage"].items()
           if k not in ("asset_max_leverage", "unlisted_asset_max_leverage")}
    lev["target_vol_annual_pct"] = 1000
    assert _lev(LeverageGovernor(lev), "PAXG") == pytest.approx(10.0)


def test_the_shipped_vol_target_still_binds_below_every_cap():
    # with the real 35% target the vol floor yields 7x - below BTC/ETH caps,
    # above PAXG's 5x: the asset cap is live for PAXG/DOT even today
    g = LeverageGovernor(CFG["leverage"])
    assert g.allowed_leverage(1.0, 50.0, 0.0, asset="ETH")[0] == \
        pytest.approx(7.0)
    assert g.allowed_leverage(1.0, 50.0, 0.0, asset="PAXG")[0] == \
        pytest.approx(5.0)


def test_margin_off_still_caps_every_asset_at_spot():
    g = _gov(use_margin=False)
    for a in ("BTC", "PAXG", "ARB"):
        assert _lev(g, a) <= 1.0


def test_the_reason_names_the_asset_cap():
    _, reasons = _gov().allowed_leverage(1.0, 50.0, 0.0, asset="PAXG")
    assert any("asset cap 5x (PAXG" in r for r in reasons)


def test_decide_threads_the_asset_into_headroom():
    class _S:
        def open_positions(self):
            return []
    d = _gov().decide(_S(), {}, 1000.0, 1.0, 50.0, 0.0, asset="PAXG")
    assert d.allowed_leverage == pytest.approx(5.0)
    assert d.headroom_usd == pytest.approx(5000.0)


def test_engine_passes_the_asset_to_the_governor():
    tree = ast.parse((ROOT / "main.py").read_text(encoding="utf-8"))
    calls = [c for c in ast.walk(tree) if isinstance(c, ast.Call)
             and ast.unparse(c.func) == "self.lev_gov.decide"]
    assert len(calls) == 1
    kw = {k.arg: ast.unparse(k.value) for k in calls[0].keywords}
    assert kw.get("asset") == "asset"


# ---------------- config guard ----------------
def _findings(mutate):
    c = copy.deepcopy(CFG)
    mutate(c)
    return validate(c)


def _msgs(found, sev):
    return [m for s, m in found if s == sev]


def test_shipped_config_raises_no_asset_leverage_fatal():
    assert not [m for m in _msgs(validate(CFG), "FATAL")
                if "asset_max_leverage" in m]


@pytest.mark.parametrize("bad", [0, -1, 500, "10", True])
def test_a_malformed_cap_is_fatal(bad):
    def m(c):
        c["leverage"]["asset_max_leverage"]["PAXG"] = bad
    assert any("asset_max_leverage.PAXG" in x
               for x in _msgs(_findings(m), "FATAL"))


def test_unlisted_cap_above_region_is_fatal():
    def m(c):
        c["leverage"]["unlisted_asset_max_leverage"] = 50
    assert any("unlisted_asset_max_leverage" in x
               for x in _msgs(_findings(m), "FATAL"))


def test_live_margin_without_the_table_is_fatal_dry_run_is_not():
    def live(c):
        c["system"]["dry_run"] = False
        del c["leverage"]["asset_max_leverage"]
    def dry(c):
        del c["leverage"]["asset_max_leverage"]
    assert any("per-asset caps" in x for x in _msgs(_findings(live), "FATAL"))
    assert not any("per-asset caps" in x
                   for x in _msgs(_findings(dry), "FATAL"))
