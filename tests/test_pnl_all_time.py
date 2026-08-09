"""Honest all-time P&L (operator-reported 2026-08-09: "net pnl all time
doesn't match up with equity").

THE DEFECT. Fees split into two populations that were reported nothing
alike. Closing-leg fees are netted inside realized_pnl_total by
record_realized_pnl. OPENING-leg fees (entry AND hedge) are debited
straight to cash by record_entry_fee (main.py's fill handler calls it for
every non-exit leg) and were netted into NO P&L figure at all - not the
lifetime total, not daily/weekly/monthly. On the live book that was
$185.94 of $382.59 lifetime fees, i.e. 49% of all costs invisible: the
bot reported -$208.31 against a true all-time change of -$383.26.

THE FIX. entry_fees_total makes the invisible population countable, and
two derived figures close the identity so it can be audited from
status.json alone:
    net_pnl_all_time    = equity - starting_capital      (incl. unrealized)
    realized_net_all_in = realized_pnl_total - entry_fees_total

net_pnl_all_time is deliberately defined as the EQUITY IDENTITY rather
than as a sum of counters: equity cannot drift from the money, whereas a
counter can be forgotten - which is precisely how this bug happened. A
future cash path that bypasses a counter shows up here automatically.
"""
from datetime import datetime, timezone

from core.persistence import SNAPSHOT_VERSION
from core.state import PortfolioState, Position


def _pos(direction, entry, size, symbol="ETH/USD"):
    return Position(position_id="p", symbol=symbol, direction=direction,
                    entry_price=entry, size=size, original_size=size,
                    opened_at=datetime.now(timezone.utc))


def _stub_bot(hist_dir):
    """Reuses tests/test_gate_components.py's established persistence stub
    (itself the test_probe_throttle precedent) so these tests exercise the
    ACTUAL StateStore save/restore code rather than a hand-mirrored dict -
    the same reason the gate-components suite caught a silently dropped
    tuple slot earlier today."""
    from ml.history import HistoryStore

    import tests.test_gate_components as tgc
    hist_dir.mkdir(parents=True, exist_ok=True)
    b = tgc._persist_stub_bot(HistoryStore(str(hist_dir / "hist.csv")))
    b.state = PortfolioState(starting_capital=5000.0)
    return b


# ------------------------------------------------------- the missing half
def test_opening_fees_are_counted_not_swallowed():
    p = PortfolioState(starting_capital=1000.0)
    p.record_fees(3.0)
    p.record_entry_fee(3.0)
    assert p.entry_fees_total == 3.0
    assert p.cash_balance == 997.0
    # the pre-fix symptom: realized P&L is untouched by an opening fee, so
    # a report built only from it cannot see the cost at all
    assert p.realized_pnl_total == 0.0


def test_realized_net_all_in_includes_both_fee_legs():
    p = PortfolioState(starting_capital=1000.0)
    p.record_entry_fee(2.0)                 # opening leg: cash only
    p.record_realized_pnl(10.0)             # already net of the closing leg
    assert p.realized_pnl_total == 10.0     # the number that used to be shown
    assert p.realized_net_all_in() == 8.0   # the honest one


def test_net_pnl_all_time_equals_the_equity_identity():
    """The headline: with an open position, an opening fee and a realized
    close, the reported all-time figure must equal equity - start EXACTLY,
    and must NOT equal realized_pnl_total."""
    p = PortfolioState(starting_capital=1000.0)
    p.record_entry_fee(2.0)
    p.record_realized_pnl(10.0)
    p.add_position(_pos("long", 100.0, 1.0))
    marks = {"ETH/USD": 105.0}              # +5 unrealized

    assert p.net_pnl_all_time(marks) == p.total_equity(marks) - 1000.0
    assert round(p.net_pnl_all_time(marks), 6) == 13.0    # -2 +10 +5
    assert p.realized_pnl_total == 10.0, (
        "the old figure must remain available and unchanged - this is an "
        "addition, not a redefinition")


def test_all_time_figure_survives_the_pool_skim():
    """Skimming profit into savings/reserve moves cash between pools and
    must not change all-time P&L by a cent (equity spans all three)."""
    p = PortfolioState(starting_capital=1000.0)
    p.record_realized_pnl(100.0)
    before = p.net_pnl_all_time()
    p.cash_balance -= 30.0                  # the skim, as capital_manager does
    p.savings_balance += 20.0
    p.reserve_balance += 10.0
    assert round(p.net_pnl_all_time(), 6) == round(before, 6) == 100.0


def test_losses_are_negative_everywhere():
    p = PortfolioState(starting_capital=1000.0)
    p.record_entry_fee(5.0)
    p.record_realized_pnl(-20.0)
    assert p.net_pnl_all_time() == -25.0
    assert p.realized_net_all_in() == -25.0


# --------------------------------------------------------- the backfill
def test_backfill_recovers_history_from_the_cash_identity(tmp_path):
    """entry_fees_total was added AFTER this bot had been trading, so a
    pre-upgrade snapshot carries no value for it. Defaulting to 0.0 would
    leave the honest figures permanently wrong by the whole historical
    population, so persistence derives it from the cash identity - the
    only four paths that move cash are record_realized_pnl (+),
    record_entry_fee (-) and the pool skim/refill pair, whose net cash
    removal is exactly the two pool balances.

    Driven through the REAL StateStore.restore, not a hand-mirrored dict."""
    import json

    from core.persistence import StateStore

    # a snapshot in the pre-fix shape: no entry_fees_total key at all
    snap = {
        "version": SNAPSHOT_VERSION, "saved_at": 0.0, "dry_run": True,
        "portfolio": {
            "starting_capital": 5000.0,
            "cash_balance": 4604.02,
            "savings_balance": 1.47,
            "reserve_balance": 0.26,
            "realized_pnl_total": -208.31,
            "daily_realized_pnl": 0.0,
            "fees_paid_total": 382.59,
            "positions": [],
        },
    }
    path = tmp_path / "state.json"
    path.write_text(json.dumps(snap), encoding="utf-8")

    bot = _stub_bot(tmp_path / "h1")
    store = StateStore(str(path))
    assert store.restore(bot)

    # 5000 - 208.31 - 4604.02 - 1.47 - 0.26 = 185.94, the live figure
    assert round(bot.state.entry_fees_total, 2) == 185.94
    # and the identity now closes: equity - start is the TRUE all-time loss,
    # ~1.84x the -208.31 the bot used to report
    assert round(bot.state.net_pnl_all_time(), 2) == -394.25


def test_persisted_value_wins_over_the_backfill(tmp_path):
    """Once written, the stored number is authoritative - the backfill is a
    one-time migration, not a recurring recomputation that could silently
    paper over a future accounting divergence."""
    import json

    from core.persistence import StateStore

    snap = {
        "version": SNAPSHOT_VERSION, "saved_at": 0.0, "dry_run": True,
        "portfolio": {
            "starting_capital": 5000.0, "cash_balance": 4604.02,
            "savings_balance": 1.47, "reserve_balance": 0.26,
            "realized_pnl_total": -208.31, "daily_realized_pnl": 0.0,
            "fees_paid_total": 382.59, "entry_fees_total": 42.0,
            "positions": [],
        },
    }
    path = tmp_path / "state.json"
    path.write_text(json.dumps(snap), encoding="utf-8")
    bot = _stub_bot(tmp_path / "h2")
    assert StateStore(str(path)).restore(bot)
    assert bot.state.entry_fees_total == 42.0


def test_roundtrip_keeps_the_counter(tmp_path):
    from core.persistence import StateStore

    bot = _stub_bot(tmp_path / "h3")
    bot.state.record_entry_fee(7.5)
    store = StateStore(str(tmp_path / "s.json"))
    assert store.snapshot(bot)

    revived = _stub_bot(tmp_path / "h4")
    assert store.restore(revived)
    assert revived.state.entry_fees_total == 7.5
