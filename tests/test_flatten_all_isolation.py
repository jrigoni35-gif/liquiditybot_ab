"""tests/test_flatten_all_isolation.py — an operator emergency flatten must
not half-complete silently.

The flatten_all handler iterated open positions with a bare _submit_exit; if
one position raised, the loop aborted and every remaining position stayed open
while the operator saw only a generic ack. Now each position is isolated: one
that errors on submission is logged and counted, the REST are still flattened,
and the ack reports the truth (submitted vs failed).
"""
import types
from datetime import datetime, timezone

from core.state import PortfolioState, Position
from runner import BotRunner


def _runner_with_positions(pids):
    r = BotRunner.__new__(BotRunner)
    r.state = "RUNNING"
    st = PortfolioState(starting_capital=10_000.0)
    for pid in pids:
        st.add_position(Position(pid, "ETH/USD", "long", 2000.0, 1.0, 1.0,
                                 datetime.now(timezone.utc)))
    submitted = []

    def submit(pos, pct, reason):
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
