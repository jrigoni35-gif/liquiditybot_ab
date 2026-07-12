"""Anti-fixation (variety) rules.

With max_concurrent_positions raised to 5, nothing count-based stopped the
book from stacking every slot into one asset+direction: the inventory USD
caps (15%/25% of equity) are far above governor-clamped ticket sizes, so
five tiny ETH longs fit comfortably under them. Three mechanisms enforce
variety:

  1. InventoryManager.can_add vetoes a same-side add once the asset already
     holds max_same_side_positions_per_asset open positions (SZ-043).
     Hedges don't count; opposite direction is risk-reducing and allowed.
  2. LiquidityBot._entry_assets round-robins the per-cycle evaluation order
     so no asset gets permanent first claim on scarce slots.
  3. Exploration skips an asset holding >= max_asset_share of the labeled
     history, leaving learning slots for under-sampled assets.
"""
import types
from datetime import datetime, timezone

from core.codes import Code
from core.config_guard import validate
from core.state import PortfolioState, Position
from execution.inventory import InventoryManager
from main import LiquidityBot

NOW = datetime.now(timezone.utc)
# equity high enough that the USD soft/hard caps can never interfere:
# these tests isolate the COUNT rule
EQUITY = 1_000_000.0
MARKS = {"ETH/USD": 2000.0, "BTC/USD": 60000.0}


def _pos(pid, symbol, direction, is_hedge=False):
    return Position(pid, symbol, direction, 2000.0, 0.1, 0.1, NOW,
                    is_hedge=is_hedge)


def _state(*positions):
    st = PortfolioState(starting_capital=EQUITY)
    for p in positions:
        st.add_position(p)
    return st


def _inv(cap=2):
    return InventoryManager({"max_same_side_positions_per_asset": cap})


# ---- 1. per-asset same-side count cap ------------------------------------

def test_count_cap_blocks_third_same_side_add():
    st = _state(_pos("p1", "ETH/USD", "long"), _pos("p2", "ETH/USD", "long"))
    add = _inv(cap=2).can_add(st, "ETH", "long", 100.0, EQUITY, MARKS)
    assert not add.allowed
    assert add.code == Code.SZ_ASSET_CROWDED
    assert "variety" in add.reason


def test_count_cap_allows_below_cap_and_other_assets():
    st = _state(_pos("p1", "ETH/USD", "long"))
    inv = _inv(cap=2)
    assert inv.can_add(st, "ETH", "long", 100.0, EQUITY, MARKS).allowed
    st2 = _state(_pos("p1", "ETH/USD", "long"), _pos("p2", "ETH/USD", "long"))
    assert inv.can_add(st2, "BTC", "long", 100.0, EQUITY, MARKS).allowed


def test_count_cap_ignores_opposite_direction_and_hedges():
    # 2 ETH longs at cap: a short is risk-reducing and must stay allowed
    st = _state(_pos("p1", "ETH/USD", "long"), _pos("p2", "ETH/USD", "long"))
    inv = _inv(cap=2)
    assert inv.can_add(st, "ETH", "short", 100.0, EQUITY, MARKS).allowed
    # hedge positions are system-driven, not fixation - excluded from count
    st2 = _state(_pos("p1", "ETH/USD", "long"),
                 _pos("p2", "ETH/USD", "long", is_hedge=True))
    assert inv.can_add(st2, "ETH", "long", 100.0, EQUITY, MARKS).allowed


def test_usd_caps_still_enforced_below_count_cap():
    # count rule must not weaken the existing soft-cap veto: one large
    # position past the soft cap still blocks same-side adds
    st = _state(Position("p1", "ETH/USD", "long", 2000.0, 1.0, 1.0, NOW))
    inv = InventoryManager({"soft_cap_pct_of_equity": 15,
                            "hard_cap_pct_of_equity": 25,
                            "max_same_side_positions_per_asset": 2})
    add = inv.can_add(st, "ETH", "long", 1000.0, 10_000.0, MARKS)
    assert not add.allowed and add.code == ""     # generic inventory veto


# ---- 2. entry-order rotation ----------------------------------------------

def _rotation_bot(assets):
    b = LiquidityBot.__new__(LiquidityBot)
    b.view = {a: {"n": i} for i, a in enumerate(assets)}
    b.symbol_map = {a: f"{a}/USD" for a in assets}
    b._entry_rotation = 0
    return b


def test_entry_order_rotates_every_cycle():
    b = _rotation_bot(["ETH", "BTC", "SUI"])
    firsts = [b._entry_assets()[0][0] for _ in range(6)]
    assert firsts == ["ETH", "BTC", "SUI", "ETH", "BTC", "SUI"]


def test_entry_rotation_preserves_membership():
    b = _rotation_bot(["ETH", "BTC", "SUI"])
    order = b._entry_assets()
    assert sorted(a for a, _ in order) == ["BTC", "ETH", "SUI"]
    b.symbol_map = {"ETH": "ETH/USD"}         # non-tradeable assets filtered
    assert [a for a, _ in b._entry_assets()] == ["ETH"]


# ---- 3. exploration share cap ----------------------------------------------

def _explore_bot(counts, share=0.5, min_rows=10):
    b = LiquidityBot.__new__(LiquidityBot)
    b.dry_run = True
    b.explore_enabled = True
    b.explore_epsilon = 1.0                   # roll always fires
    b.explore_until_rows = 10_000
    b.explore_max_asset_share = share
    b.explore_share_min_rows = min_rows
    b._explore_rng = __import__("random").Random(1)
    setattr(b, "history", types.SimpleNamespace(
        row_count=lambda: sum(counts.values()),
        asset_counts=lambda: dict(counts)))
    return b


def test_exploration_skips_dominant_asset():
    b = _explore_bot({"ETH": 8, "BTC": 2})    # ETH at 80% share
    assert b._exploration_active(0.0, "ETH") is False
    assert b._exploration_active(0.0, "BTC") is True


def test_exploration_share_needs_min_rows():
    b = _explore_bot({"ETH": 5}, min_rows=10)  # 5 rows < floor: no check yet
    assert b._exploration_active(0.0, "ETH") is True


def test_exploration_share_check_off_without_asset_or_at_share_1():
    b = _explore_bot({"ETH": 100})
    assert b._exploration_active(0.0) is True             # legacy call shape
    b2 = _explore_bot({"ETH": 100}, share=1.0)
    assert b2._exploration_active(0.0, "ETH") is True     # 1.0 disables


def test_history_asset_counts_real_csv(tmp_path):
    import numpy as np
    from ml.features import FEATURE_NAMES
    from ml.history import HistoryStore
    hs = HistoryStore(str(tmp_path / "hist.csv"))
    feats = np.zeros(len(FEATURE_NAMES))
    for pid, asset in (("a1", "ETH"), ("a2", "ETH"), ("a3", "BTC")):
        hs.log_entry(pid, asset, "long", feats)
        hs.log_close(pid, 1.0)
    assert hs.asset_counts() == {"ETH": 2, "BTC": 1}
    assert HistoryStore(str(tmp_path / "missing.csv")).asset_counts() == {}


# ---- config_guard ------------------------------------------------------------

def test_guard_zero_same_side_cap_is_fatal():
    cfg = {"system": {"dry_run": True},
           "inventory": {"max_same_side_positions_per_asset": 0}}
    assert any("max_same_side_positions_per_asset" in m
               for sev, m in validate(cfg) if sev == "FATAL")


def test_guard_unreachable_book_warns():
    cfg = {"system": {"dry_run": True},
           "capital_management": {"max_concurrent_positions": 5},
           "inventory": {"max_same_side_positions_per_asset": 1},
           "exchanges": {"kraken": {"trading_pairs": ["ETH/USD", "BTC/USD"]}}}
    assert any("can never be reached" in m
               for sev, m in validate(cfg) if sev == "WARN")


def test_guard_exploration_share_out_of_range_is_fatal():
    for bad in (0.0, 1.5):
        cfg = {"system": {"dry_run": True},
               "ml": {"exploration": {"max_asset_share": bad}}}
        assert any("max_asset_share" in m
                   for sev, m in validate(cfg) if sev == "FATAL"), bad


def test_guard_shipped_variety_defaults_are_clean():
    cfg = {"system": {"dry_run": True},
           "capital_management": {"max_concurrent_positions": 5},
           "inventory": {"max_same_side_positions_per_asset": 2},
           "exchanges": {"kraken": {"trading_pairs":
                                    ["ETH/USD", "BTC/USD", "SUI/USD",
                                     "ARB/USD", "MINA/USD", "FLOW/USD"]}},
           "ml": {"exploration": {"max_asset_share": 0.5,
                                  "share_min_rows": 10}}}
    findings = validate(cfg)
    assert not any(("max_same_side" in m or "max_asset_share" in m
                    or "can never be reached" in m)
                   for _, m in findings)
