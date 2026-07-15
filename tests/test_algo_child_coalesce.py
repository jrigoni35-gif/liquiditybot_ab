"""tests/test_algo_child_coalesce.py — a sliced parent order is ONE position.

_submit_algo_child minted a fresh uuid per child slice, so every child of a
single parent filled into a SEPARATE Position: one logical order fragmented into
up to max_children positions, each carrying its own stop/tiers/high_water and
each consuming a max_concurrent_positions slot (a single algo parent could block
every other entry). All children now share one parent-derived position_id, so
_handle_fill coalesces their fills into one size-weighted position.
"""
from types import SimpleNamespace

import main as main_mod
from core.state import PortfolioState
from execution.algos import ChildSlice
from execution.order_manager import ManagedOrder


# --- the fix: children of one parent share one position_id ------------------
def _algo_shell():
    captured_ids = []

    def fake_submit(**kw):
        captured_ids.append(kw["position_id"])
        return SimpleNamespace(order_id="o", position_id=kw["position_id"])

    seqs = iter([1, 2, 3, 4])
    b = SimpleNamespace(
        _algo_meta={}, view={"ETH": {"candles": []}}, state=SimpleNamespace(),
        marks={"ETH/USD": 2000.0}, kraken_books={"ETH": {"bids": [[1999.0, 5]],
                                                         "asks": [[2001.0, 5]]}},
        fv=SimpleNamespace(state=lambda a: SimpleNamespace(kraken_mid=2000.0,
                                                           fair_value=2000.0)),
        vol=SimpleNamespace(state=lambda a: SimpleNamespace(sigma_bar_pct=0.3)),
        liq=SimpleNamespace(state=lambda a: SimpleNamespace(label="normal")),
        inventory=SimpleNamespace(inventory_ratio=lambda *a, **k: 0.0),
        quoter=SimpleNamespace(quote=lambda *a, **k: SimpleNamespace(bid=1999.0,
                                                                     ask=2001.0)),
        tactics=SimpleNamespace(plan_entry=lambda *a, **k: SimpleNamespace(
            price=2000.0, post_only=True, style="passive")),
        pretrade=SimpleNamespace(maker_fee_bps=1.0),
        kraken=SimpleNamespace(kraken_pair=lambda s: "XETHZUSD"),
        _equity=lambda: 10_000.0, _px=lambda s, p: f"{p:.2f}",
        orders=SimpleNamespace(submit=fake_submit),
        algo=SimpleNamespace(
            next_slice=lambda pid, now, vol: ChildSlice("par123", 1.0,
                                                        next(seqs), 4),
            note_child_order=lambda pid, posid: None,
            note_child_rejected=lambda *a, **k: None),
    )
    b._captured_ids = captured_ids
    return b


def _parent():
    return SimpleNamespace(parent_id="par123", asset="ETH", symbol="ETH/USD",
                           side="buy", direction="long", arrival_price=2000.0,
                           urgency=0.0)


def test_all_children_of_a_parent_share_one_position_id():
    b, parent = _algo_shell(), _parent()
    for _ in range(3):
        main_mod.LiquidityBot._submit_algo_child(b, parent, now=1000.0)
    assert len(b._captured_ids) == 3
    assert len(set(b._captured_ids)) == 1, "children must not fragment into " \
                                           "distinct positions"
    assert b._captured_ids[0] == "algo-par123"       # deterministic, restart-safe


# --- the outcome: shared id coalesces in _handle_fill -----------------------
def _fill_shell():
    b = main_mod.LiquidityBot.__new__(main_mod.LiquidityBot)
    b.state = PortfolioState(starting_capital=10_000.0)
    b._pos_realized = {}
    b._stop_price_for = lambda direction, entry, asset: 0.0
    b.postmortem = SimpleNamespace(note_fill=lambda *a, **k: None)
    b.history = SimpleNamespace(log_entry=lambda *a, **k: None)
    b.algo = SimpleNamespace(note_fill=lambda *a, **k: None)
    b._px = lambda s, p: f"{p:.2f}"
    return b


def _entry_fill(position_id, size, price, seq):
    o = ManagedOrder(order_id=f"o{seq}", txid=None, asset="ETH", pair="XETHZUSD",
                     symbol="ETH/USD", side="buy", price=price, size=size,
                     purpose="entry", position_id=position_id,
                     meta={"algo_parent": "par123", "algo_child_seq": seq})
    o.filled = size
    return SimpleNamespace(order=o, fill_size=size, fill_price=price, final=False)


def test_shared_position_id_coalesces_into_one_weighted_position():
    b = _fill_shell()
    b._handle_fill(_entry_fill("algo-par123", 1.0, 2000.0, 1), now=1000.0)
    b._handle_fill(_entry_fill("algo-par123", 3.0, 2100.0, 2), now=1001.0)
    assert b.state.open_position_count() == 1, "one coalesced position, not two"
    pos = b.state.get_position("algo-par123")
    assert pos.size == 4.0                                   # summed
    assert abs(pos.entry_price - (2000.0 + 3 * 2100.0) / 4.0) < 1e-9  # weighted
