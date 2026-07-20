"""#51 batch: exit-safety cluster (EX-3/4/5/6 from the 2026-07-17 audit).

Invariant #5 — disarm, faults, and kill switches block NEW RISK, never
escapes. Each fix here removes a path where an escape could be deferred,
vetoed, or priced un-fillable:

  EX-3  one dark symbol stalled the WHOLE catastrophe flatten + halt latch
  EX-4  firewall notional clamp could dust an exit below venue ordermin
  EX-5  the firewall dupe window vetoed intentional exit-ladder retries
  EX-6  the exit collar could anchor to entry price (a price that no
        longer exists) and clamp the escape un-fillable
"""
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import main as main_mod
from core.state import Position
from execution.order_manager import OrderManager
from execution.risk_firewall import RiskFirewall

ROOT = Path(__file__).resolve().parents[1]


# --- EX-5: firewall dupe window never vetoes an exit ------------------------
def _fw():
    return RiskFirewall({"max_order_usd": 1e9, "max_order_pct_equity": 100.0,
                         "dupe_window_sec": 5.0})


def test_identical_exit_retry_is_never_dupe_vetoed():
    fw = _fw()
    kw = dict(pair="XETHZUSD", side="sell", purpose="exit",
              price=100.0, size=1.0, ref_price=100.0, equity=10_000.0)
    assert fw.check(**kw).allowed
    v2 = fw.check(**kw)                    # frozen book: identical retry
    assert v2.allowed, "an escape retry must never be dupe-vetoed"
    assert any("never dupe-vetoed" in r for r in v2.reasons)


def test_identical_entry_is_still_dupe_rejected():
    fw = _fw()
    kw = dict(pair="XETHZUSD", side="buy", purpose="entry",
              price=100.0, size=1.0, ref_price=100.0, equity=10_000.0)
    assert fw.check(**kw).allowed
    v2 = fw.check(**kw)
    assert not v2.allowed, "entry dupe protection unchanged"


# --- EX-4: clamped exits floor at the venue minimum -------------------------
def _om_with_min(omin):
    om = OrderManager(feed=None, config={}, dry_run=True,
                      firewall=_fw())
    om._ordermin = lambda pair: omin
    return om


def test_notional_clamped_exit_floors_at_ordermin():
    # near-wiped account: equity $4 -> exit cap $8 (2x) -> clamp 1.0 ->
    # 0.08 units, below the 0.1 venue minimum. Must floor to 0.1, not None.
    om = _om_with_min(0.1)
    o = om.submit(asset="ETH", symbol="ETH/USD", pair="XETHZUSD",
                  side="sell", price=100.0, size=1.0, purpose="exit",
                  position_id="p1", post_only=False, ref_price=100.0,
                  equity=4.0)
    assert o is not None, "the escape must stay executable"
    assert o.size == 0.1, "floored to the minimum executable escape"


def test_exit_requested_below_ordermin_still_skips():
    # the caller asked for dust in the first place (no firewall shrink):
    # unchanged behavior - the caller's dust-flat path owns this case
    om = _om_with_min(0.1)
    o = om.submit(asset="ETH", symbol="ETH/USD", pair="XETHZUSD",
                  side="sell", price=100.0, size=0.05, purpose="exit",
                  position_id="p1", post_only=False, ref_price=100.0,
                  equity=10_000.0)
    assert o is None


def test_entry_clamp_semantics_unchanged():
    om = _om_with_min(0.1)
    o = om.submit(asset="ETH", symbol="ETH/USD", pair="XETHZUSD",
                  side="buy", price=100.0, size=0.05, purpose="entry",
                  post_only=True, ref_price=100.0, equity=10_000.0)
    assert o is None, "below-min entries still skip - only escapes floor"


# --- EX-6: exit collar reference chain --------------------------------------
def _ref_captured(marks, mark_fresh, bids, asks, fair_value):
    captured = {}

    def fake_submit(**kw):
        captured.update(kw)
        return SimpleNamespace(order_id="o", position_id="p1", purpose="exit")

    fake = SimpleNamespace(
        _asset_of=lambda sym: "ETH",
        kraken=SimpleNamespace(kraken_pair=lambda sym: "XETHZUSD"),
        orders=SimpleNamespace(open_orders=lambda: [],
                               _ordermin=lambda pair: 0.0,
                               submit=fake_submit),
        _exit_attempts={}, max_slip_pct=0.5, esc_widen_mult=2.0,
        esc_max_slip_pct=3.0, esc_market_after=3,
        kraken_books={"ETH": {"bids": bids, "asks": asks}},
        marks=marks, maker_first_profit_exits=False,
        _mark_fresh=mark_fresh,
        fv=SimpleNamespace(state=lambda a: SimpleNamespace(
            fair_value=fair_value)),
        _equity=lambda: 1000.0,
        vol=SimpleNamespace(state=lambda a: SimpleNamespace(sigma_bar_pct=0.3)),
    )
    pos = Position(position_id="p1", symbol="ETH/USD", direction="long",
                   entry_price=140.0, size=1.0, original_size=1.0,
                   opened_at=datetime.now(timezone.utc))
    main_mod.LiquidityBot._submit_exit(fake, pos, 100.0, "hard stop",
                                       now=1000.0)
    return captured.get("ref_price")


def test_collar_ref_prefers_the_fresh_mark():
    ref = _ref_captured({"ETH/USD": 99.0}, lambda s, n: True,
                        [[98.0, 5.0]], [[100.0, 5.0]], 97.0)
    assert ref == 99.0


def test_collar_ref_falls_to_book_mid_when_mark_stale():
    ref = _ref_captured({"ETH/USD": 99.0}, lambda s, n: False,
                        [[98.0, 5.0]], [[100.0, 5.0]], 97.0)
    assert ref == (98.0 + 100.0) / 2


def test_collar_ref_never_anchors_to_entry_price():
    # crash scenario: mark stale, book gone, fair value dead -> ref must be
    # None (exits pass the firewall UNCOLLARED by design), never the 140.0
    # entry price that would clamp the escape 40% above the market
    ref = _ref_captured({}, lambda s, n: False, [], [], 0.0)
    assert ref is None


# --- EX-3: catastrophe flatten survives a dark symbol -----------------------
def test_hard_stop_block_retries_while_latched_and_gates_per_position():
    src = (ROOT / "main.py").read_text(encoding="utf-8")
    # the flatten block re-enters while halted, not only on a fresh trigger
    assert "or self._halted):" in src
    # per-position trusted-mark gate INSIDE the flatten loop
    i = src.index("or self._halted):")
    block = src[i:i + 1800]
    assert 'self._submit_exit(pos, 100.0, "hard stop", now=now)' in block
    assert "self._mark_fresh(pos.symbol, now)" in block
    # all-confirmed still returns; partially-dark falls through so the
    # protective-stop loop keeps managing the deferred positions
    assert "if marks_confirmed:\n                return" in block
