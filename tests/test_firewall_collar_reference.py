"""tests/test_firewall_collar_reference.py — the price collar must see a REAL
reference, never the order's own price.

OrderManager.submit passed `ref_price=ref_price or price` to the firewall. When
a caller had no mark (ref_price 0/None) that substituted the order's OWN limit
price as the reference, so the collar deviation was identically zero
(|price-price|=0) and BOTH the collar AND the firewall's fail-closed entry/hedge
refusal (FW-060, "no reference -> refuse new risk") were silently defeated: a
blind entry with no mark sailed through. The fix passes ref_price through
untouched, so an absent reference reaches the firewall as absent.
"""
from execution.order_manager import OrderManager
from execution.risk_firewall import RiskFirewall


def _om():
    fw = RiskFirewall({"entry_collar_bps": 100.0, "exit_collar_bps": 500.0,
                       "max_order_usd": 1_000_000.0})
    return OrderManager(feed=None, config={}, dry_run=True, firewall=fw)


def _submit(om, purpose, price, ref_price):
    return om.submit(asset="ETH", symbol="ETH/USD", pair="XETHZUSD",
                     side="buy" if purpose != "exit" else "sell",
                     price=price, size=0.01, purpose=purpose,
                     position_id="p1", ref_price=ref_price, equity=100_000.0,
                     book={"bids": [[price, 5.0]], "asks": [[price, 5.0]]})


def test_blind_entry_with_no_reference_is_refused():
    # THE fix: an entry with no mark (ref_price None) must be REFUSED, not
    # allowed through a self-referential zero-deviation collar.
    om = _om()
    assert _submit(om, "entry", price=2200.0, ref_price=None) is None
    assert _submit(om, "entry", price=2200.0, ref_price=0.0) is None


def test_entry_far_from_a_real_reference_is_collar_rejected():
    om = _om()
    # 1000 bps from a genuine mark, well past the 100 bps entry collar
    assert _submit(om, "entry", price=2200.0, ref_price=2000.0) is None


def test_entry_within_collar_of_a_real_reference_is_accepted():
    om = _om()
    order = _submit(om, "entry", price=2010.0, ref_price=2000.0)  # 50 bps
    assert order is not None and order.purpose == "entry"


def test_exit_with_no_reference_still_passes_uncollared():
    # exits are ALWAYS allowed: a missing mark drops collar screening, it never
    # blocks the escape (unlike an entry, which fails closed).
    om = _om()
    order = _submit(om, "exit", price=2200.0, ref_price=None)
    assert order is not None and order.purpose == "exit"
