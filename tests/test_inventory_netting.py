"""NET-1 (2026-10-03, operator: "the bot has to have control and conscious of
the inventory to improve upon the fees"). Every trip here is a SEPARATE
position with its own brackets, so an entry opposite an open same-asset
position does not reduce anything: it opens a second trade that pays a round
trip of fees for exposure that cancels. Measured since cut #12: 36 of 112
entries (32%) opened against an open opposite position and paid $9.07 of
$27.81 trip fees (docs/quant/2026-10-03_inventory_netting_patient_exits.md).
"""
from datetime import datetime, timezone

from core.codes import Code
from core.state import PortfolioState, Position
from execution.inventory import InventoryManager

NOW = datetime.now(timezone.utc)
EQUITY = 1_000_000.0
MARKS = {"ETH/USD": 2000.0, "BTC/USD": 60000.0}


def _pos(pid, symbol, direction, is_hedge=False):
    return Position(pid, symbol, direction, 2000.0, 0.1, 0.1, NOW, is_hedge=is_hedge)


def _state(*positions):
    st = PortfolioState(starting_capital=EQUITY)
    for p in positions:
        st.add_position(p)
    return st


def _inv(refuse=True):
    return InventoryManager({"max_same_side_positions_per_asset": 2,
                             "refuse_opposite_side": refuse})


def test_opposite_entry_on_an_asset_with_open_inventory_is_refused():
    st = _state(_pos("p1", "ETH/USD", "short"))
    add = _inv().can_add(st, "ETH", "long", 100.0, EQUITY, MARKS)
    assert not add.allowed and add.allowed_usd == 0.0
    assert add.code == Code.SZ_OPPOSES_INVENTORY


def test_same_side_and_other_assets_are_untouched():
    st = _state(_pos("p1", "ETH/USD", "short"))
    assert _inv().can_add(st, "ETH", "short", 100.0, EQUITY, MARKS).allowed
    assert _inv().can_add(st, "BTC", "long", 100.0, EQUITY, MARKS).allowed


def test_a_hedge_is_not_inventory_to_net_against():
    st = _state(_pos("h1", "ETH/USD", "short", is_hedge=True))
    assert _inv().can_add(st, "ETH", "long", 100.0, EQUITY, MARKS).allowed


def test_switch_off_restores_the_old_behaviour():
    st = _state(_pos("p1", "ETH/USD", "short"))
    assert _inv(refuse=False).can_add(st, "ETH", "long", 100.0, EQUITY, MARKS).allowed


def test_code_default_is_off_so_other_constructors_are_unchanged():
    st = _state(_pos("p1", "ETH/USD", "short"))
    inv = InventoryManager({"max_same_side_positions_per_asset": 2})
    assert inv.can_add(st, "ETH", "long", 100.0, EQUITY, MARKS).allowed


def test_shipped_config_turns_it_on():
    import json
    from pathlib import Path
    cfg = json.loads((Path(__file__).resolve().parents[1] / "config.json")
                     .read_text(encoding="utf-8"))
    assert cfg["inventory"]["refuse_opposite_side"] is True
