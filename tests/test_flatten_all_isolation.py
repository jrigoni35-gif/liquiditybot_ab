"""tests/test_flatten_all_isolation.py — an operator emergency flatten must
not half-complete silently.

The flatten_all handler iterated open positions with a bare _submit_exit; if
one position raised, the loop aborted and every remaining position stayed open
while the operator saw only a generic ack. Now each position is isolated: one
that errors on submission is logged and counted, the REST are still flattened,
and the ack reports the truth (submitted vs failed).

W2-6 (2026-07-23): a pause -> flatten_all left exits unmanaged. handle_command
ran every loop tick even while PAUSED, but orders.poll (fills/timeouts) + the
live dead-man refresh only ran inside cycle_once/fast_cycle - so a flatten
order rested unmanaged (a real fill in that window silently lost) until the
venue's blunt ~60s dead-man cancelled it, with the ack claiming "submitted"
regardless. Also, _submit_exit here was the one exit call site outside the
injected-now discipline every other caller already follows.
"""
import types
from datetime import datetime, timezone

from core.state import PortfolioState, Position
from execution.order_manager import ManagedOrder, OrderManager
from runner import BotRunner


def _runner_with_positions(pids):
    r = BotRunner.__new__(BotRunner)
    r.state = "RUNNING"
    st = PortfolioState(starting_capital=10_000.0)
    for pid in pids:
        st.add_position(Position(pid, "ETH/USD", "long", 2000.0, 1.0, 1.0,
                                 datetime.now(timezone.utc)))
    submitted = []

    def submit(pos, pct, reason, now=None):
        if pos.position_id == "bad":
            raise RuntimeError("simulated corrupt-position blow-up")
        submitted.append(pos.position_id)
    r.bot = types.SimpleNamespace(state=st, _submit_exit=submit)
    r._submitted = submitted
    return r


def test_flatten_all_flattens_the_rest_when_one_position_raises():
    r = _runner_with_positions(["p1", "bad", "p2"])
    r.handle_command({"cmd": "flatten_all"})          # must not raise
    assert sorted(r._submitted) == ["p1", "p2"], \
        "a raising position must not abort the emergency flatten of the rest"


def test_flatten_all_clean_path_submits_every_position():
    r = _runner_with_positions(["p1", "p2", "p3"])
    r.handle_command({"cmd": "flatten_all"})
    assert sorted(r._submitted) == ["p1", "p2", "p3"]


# ---------------------------------------------------------------------------
# W2-6a: flatten_all passes the loop's injected `now` into _submit_exit
# ---------------------------------------------------------------------------
def test_flatten_all_passes_injected_now_to_submit_exit():
    r = _runner_with_positions(["p1"])
    captured = {}
    r.bot._submit_exit = lambda pos, pct, reason, now=None: captured.update(
        {pos.position_id: now})
    r.handle_command({"cmd": "flatten_all"}, now=555_555.0)
    assert captured == {"p1": 555_555.0}


def test_flatten_all_without_now_falls_back_to_none():
    """handle_command keeps working for every existing caller that never
    passed now (smoke_test.py, other tests) - default stays None, and
    _submit_exit itself falls back to wall clock exactly as before."""
    r = _runner_with_positions(["p1"])
    captured = {}
    r.bot._submit_exit = lambda pos, pct, reason, now=None: captured.update(
        {pos.position_id: now})
    r.handle_command({"cmd": "flatten_all"})
    assert captured == {"p1": None}


def test_flatten_all_ack_notes_paused_management_only_when_paused(caplog):
    r = _runner_with_positions(["p1"])
    r.state = "PAUSED"
    with caplog.at_level("WARNING"):
        r.handle_command({"cmd": "flatten_all"})
    ack = [rec.message for rec in caplog.records if "control: flatten_all"
          in rec.message]
    assert ack and "exits will be managed while paused" in ack[0]


def test_flatten_all_ack_omits_paused_note_when_running(caplog):
    r = _runner_with_positions(["p1"])
    assert r.state == "RUNNING"
    with caplog.at_level("WARNING"):
        r.handle_command({"cmd": "flatten_all"})
    ack = [rec.message for rec in caplog.records if "control: flatten_all"
          in rec.message]
    assert ack and "exits will be managed while paused" not in ack[0]


# ---------------------------------------------------------------------------
# W2-6b: order-maintenance slice runs each tick while PAUSED
# ---------------------------------------------------------------------------
def _live_om_with_one_exit(created_ts=0.0, order_timeout_sec=25.0):
    calls = []

    def _post(endpoint, data=None):
        calls.append(endpoint)
        return {}

    feed = types.SimpleNamespace(
        _private_post=_post,
        cancel_all_orders_after=lambda sec: (calls.append("deadman") or True))
    om = OrderManager(feed=feed, config={"deadman_timeout_sec": 60,
                                         "order_timeout_sec": order_timeout_sec},
                      dry_run=False)
    o = ManagedOrder(order_id="o1", txid="TX1", asset="ETH", pair="ETHUSD",
                     symbol="ETH/USD", side="sell", price=100.0, size=1.0,
                     purpose="exit", position_id="p1", created_ts=created_ts)
    om._orders[o.order_id] = o
    return om, o, calls


def _paused_runner(om):
    handled = []
    bot = types.SimpleNamespace(
        orders=om, kraken_books={}, symbol_map={"ETH": "ETH/USD"},
        vol=types.SimpleNamespace(
            state=lambda a: types.SimpleNamespace(sigma_bar_pct=0.05)),
        _handle_fill=lambda ev, now: handled.append(ev))
    r = BotRunner.__new__(BotRunner)
    r.state = "PAUSED"
    r.bot = bot
    return r, handled


def test_paused_maintenance_polls_and_refreshes_deadman_with_exit_open():
    # order_timeout_sec well beyond `now` so the order stays open; the
    # dead-man refresh cadence gate (deadman_sec/2 = 30s) clears at now=30
    om, o, calls = _live_om_with_one_exit(order_timeout_sec=1000.0)
    r, handled = _paused_runner(om)
    r._run_paused_order_maintenance(now=30.0)
    assert "deadman" in calls, "the live dead-man refresh must still run"
    assert o.status in ("pending", "partial")   # not yet timed out


def test_paused_maintenance_progresses_a_timed_out_exit_to_terminal():
    om, o, calls = _live_om_with_one_exit(created_ts=0.0, order_timeout_sec=25.0)
    r, handled = _paused_runner(om)
    r._run_paused_order_maintenance(now=30.0)  # > order_timeout_sec (25s)
    assert "CancelOrder" in calls
    # zero-filled timeout resolves to "expired" (fill_ratio==0), same
    # disposition rule as the always-on live timeout path
    assert o.status == "expired"
    assert o not in om.open_orders()


def test_paused_maintenance_applies_fills_through_handle_fill():
    om, o, _ = _live_om_with_one_exit()
    r, handled = _paused_runner(om)

    def fake_query(ep, data=None):
        if ep == "QueryOrders":
            return {"TX1": {"vol_exec": "1.0", "price": "100.0",
                            "status": "closed"}}
        return {}
    om._timed_private = fake_query
    r._run_paused_order_maintenance(now=5.0)
    assert len(handled) >= 1, "a fill landing while paused must reach _handle_fill"
    assert o.status == "filled"


def test_paused_maintenance_noop_when_no_exit_orders_open():
    """The common case: paused with nothing resting costs nothing extra -
    no QueryOrders/CancelOrder/deadman calls at all."""
    om, o, calls = _live_om_with_one_exit()
    o.purpose = "entry"          # no EXIT-purpose order open
    r, handled = _paused_runner(om)
    r._run_paused_order_maintenance(now=5.0)
    assert calls == []


def test_paused_maintenance_noop_when_no_orders_attribute():
    r = BotRunner.__new__(BotRunner)
    r.state = "PAUSED"
    r.bot = types.SimpleNamespace()          # no .orders at all
    r._run_paused_order_maintenance(now=5.0)  # must not raise


def test_paused_maintenance_is_isolated_never_raises():
    om, o, _ = _live_om_with_one_exit()

    def exploding(*a, **k):
        raise RuntimeError("venue down")
    om.poll = exploding
    r, handled = _paused_runner(om)
    r._run_paused_order_maintenance(now=5.0)  # must not raise


def test_run_loop_calls_paused_maintenance_while_paused():
    """Structural pin (mirrors the EX-3 pattern in test_exit_safety_batch.py
    for a control-flow property impractical to drive through the full,
    real-I/O `run()` loop): the PAUSED branch of the loop must invoke the
    order-maintenance slice every tick, not only handle_command."""
    from pathlib import Path
    src = (Path(__file__).resolve().parents[1] / "runner.py").read_text(
        encoding="utf-8")
    i = src.index("# paused: not failing, but not proof of recovery either")
    block = src[i:i + 900]
    assert "self._run_paused_order_maintenance(now)" in block
