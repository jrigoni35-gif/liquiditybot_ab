"""PATIENT-1 (2026-10-03, operator: inventory control to stop fees cutting
into profits). Time-based exits - the bracket vertical barrier (tb_time), the
PT-060 time-stop scratch, a non-urgent stale-inventory purge and the ML-073
label realization - are NOT risk-off: the position is expiring, not escaping.
Measured since cut #12, 108 of 113 exit legs paid the 30 bps taker rate.
A patient exit rests post-only at the touch on its FIRST attempt (15 bps
maker) and escalates into the unchanged marketable ladder if it expires; a
risk-off exit still pre-empts it (test_exit_preemption.py). Stops, trails,
floors and urgent derisk stay marketable-first.
"""
from datetime import datetime, timezone
from types import SimpleNamespace

import main as main_mod
from core.state import Position


def _run(direction, *, patient, attempts=0, flag=True,
         bids=((99.0, 5.0),), asks=((101.0, 5.0),), live=()):
    captured = {}

    def fake_submit(**kw):
        captured.update(kw)
        return SimpleNamespace(order_id="o1", position_id="p1", purpose="exit")

    fake = SimpleNamespace(
        _asset_of=lambda sym: "ETH",
        kraken=SimpleNamespace(kraken_pair=lambda sym: "XETHZUSD"),
        orders=SimpleNamespace(open_orders=lambda: list(live),
                               _ordermin=lambda pair: 0.0,
                               submit=fake_submit,
                               cancel_order=lambda o, reason="": captured.setdefault(
                                   "cancelled", []).append(o)),
        _exit_attempts=({"p1": attempts} if attempts else {}),
        max_slip_pct=0.5, esc_widen_mult=2.0, esc_max_slip_pct=3.0,
        esc_market_after=3,
        kraken_books={"ETH": {"bids": list(bids), "asks": list(asks)}},
        marks={"ETH/USD": 100.0},
        maker_first_profit_exits=True, maker_first_time_exits=flag,
        _mark_fresh=lambda sym, now: True,
        fv=SimpleNamespace(state=lambda a: SimpleNamespace(fair_value=100.0)),
        _equity=lambda: 1000.0,
        vol=SimpleNamespace(state=lambda a: SimpleNamespace(sigma_bar_pct=0.3)),
    )
    pos = Position(position_id="p1", symbol="ETH/USD", direction=direction,
                   entry_price=100.0, size=1.0, original_size=1.0,
                   opened_at=datetime.now(timezone.utc))
    main_mod.LiquidityBot._submit_exit(fake, pos, close_pct=100.0, reason="tb_time",
                                       now=1000.0, patient=patient)
    return captured


def test_patient_exit_rests_post_only_on_our_side_first():
    k = _run("long", patient=True)
    assert k["post_only"] is True and k["price"] == 101.0 and k["side"] == "sell"
    k = _run("short", patient=True)
    assert k["post_only"] is True and k["price"] == 99.0 and k["side"] == "buy"


def test_an_unfilled_patient_exit_escalates_into_the_marketable_ladder():
    k = _run("long", patient=True, attempts=1)
    assert k["post_only"] is False and k["price"] < 99.0


def test_non_patient_exit_is_unchanged_marketable():
    k = _run("long", patient=False)
    assert k["post_only"] is False and k["price"] < 99.0


def test_switch_off_and_missing_book_fall_back_to_marketable():
    assert _run("long", patient=True, flag=False)["post_only"] is False
    assert _run("long", patient=True, asks=())["post_only"] is False


def test_a_patient_exit_never_preempts_a_resting_maker_exit():
    resting = SimpleNamespace(purpose="exit", position_id="p1", post_only=True)
    k = _run("long", patient=True, live=[resting])
    assert "price" not in k and "cancelled" not in k      # deduped, nothing sent


def test_call_sites_mark_exactly_the_time_based_exits_patient():
    """Source pin: patient=True only at the time-based call sites."""
    import inspect
    src = inspect.getsource(main_mod.LiquidityBot)
    assert 'self._submit_exit(pos, 100.0, "tb_time", now=now, patient=True)' in src
    assert "patient=is_time_stop" in src
    assert "patient=not act.urgent" in src
    assert "self._submit_exit(pos, 100.0, reason, now=now, patient=True)" in src
    assert '"hard stop", now=now)' in src                 # stops untouched
