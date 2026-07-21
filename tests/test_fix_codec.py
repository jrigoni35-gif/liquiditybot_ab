"""FIX 4.4 codec (execution/fix_codec.py).

This module is a HARD-OFF, deliberately-unwired protocol stub — CLAUDE.md
invariant #3 keeps Kraken the sole execution venue, and the FIX adapter is
one of the disabled connectivity stubs. It ships now purely so a future
certified venue is an adapter swap rather than a rewrite, and its own
docstring promises it is "fully unit-testable today". It was at 0% coverage
because nothing imports it. This suite makes good on the promise: wire-exact
encode/decode round-trips, every FixError path, the session/order builders,
and the sequence-gap bookkeeping. No sockets, nothing wired to the engine —
testing the codec does NOT wire it up.
"""
import pytest

from execution import fix_codec as fx

SOH = fx.SOH


def _frame(body: str) -> str:
    """Assemble a checksum- and BodyLength-correct wire message around an
    arbitrary body, so a test can craft a message that passes framing checks
    and then trips a LATER validation (e.g. a non-numeric tag)."""
    head = f"8={fx.BEGIN_STRING}{SOH}9={len(body)}{SOH}"
    partial = head + body
    ck = sum(partial.encode("ascii", "replace")) % 256
    return f"{partial}10={ck:03d}{SOH}"


# ----------------------------------------------------------- wire codec
def test_encode_decode_round_trips_with_valid_framing():
    wire = fx.encode("D", [(11, "abc"), (55, "ETHUSD")],
                     "SENDER", "TARGET", 42, sending_time=0.0)
    assert wire.startswith(f"8={fx.BEGIN_STRING}{SOH}9=")
    assert wire.endswith(SOH)
    got = fx.decode(wire)                    # verifies BodyLength + CheckSum
    assert got[35] == "D" and got[49] == "SENDER" and got[56] == "TARGET"
    assert got[34] == "42" and got[11] == "abc" and got[55] == "ETHUSD"


def test_decode_rejects_missing_beginstring():          # FIX-001
    with pytest.raises(fx.FixError):
        fx.decode(f"35=D{SOH}10=000{SOH}")


def test_decode_rejects_malformed_bodylength():         # FIX-002
    with pytest.raises(fx.FixError):
        fx.decode(f"8={fx.BEGIN_STRING}{SOH}9=xx{SOH}35=0{SOH}10=000{SOH}")


def test_decode_rejects_missing_checksum_trailer():     # FIX-003
    with pytest.raises(fx.FixError):
        fx.decode(f"8={fx.BEGIN_STRING}{SOH}9=5{SOH}35=0{SOH}")


def test_decode_rejects_bodylength_mismatch():          # FIX-004
    with pytest.raises(fx.FixError):
        fx.decode(f"8={fx.BEGIN_STRING}{SOH}9=999{SOH}35=0{SOH}10=000{SOH}")


def test_decode_rejects_bad_checksum():                 # FIX-005
    wire = fx.encode("5", [(58, "ABC")], "S", "T", 1, sending_time=0.0)
    tampered = wire.replace("ABC", "ABD", 1)            # same length, new bytes
    with pytest.raises(fx.FixError):
        fx.decode(tampered)


def test_decode_rejects_non_numeric_tag():              # FIX-006
    # frame passes BeginString/BodyLength/CheckSum, then the tag loop trips
    with pytest.raises(fx.FixError):
        fx.decode(_frame(f"35=0{SOH}abc=1{SOH}"))


# ------------------------------------------------------ message builders
def test_session_message_builders():
    assert fx.decode(fx.logon("S", "T", 1))[35] == "A"
    assert fx.decode(fx.logon("S", "T", 1, reset_seq=True))[141] == "Y"
    assert fx.decode(fx.heartbeat("S", "T", 1))[35] == "0"
    assert fx.decode(fx.heartbeat("S", "T", 1, test_req_id="q"))[112] == "q"
    assert fx.decode(fx.test_request("S", "T", 1, "q"))[112] == "q"
    assert fx.decode(fx.logout("S", "T", 1, text="bye"))[58] == "bye"
    assert 58 not in fx.decode(fx.logout("S", "T", 1))


def test_new_order_single_limit_and_market():
    lim = fx.decode(fx.new_order_single("S", "T", 1, "c1", "ETHUSD", "buy",
                                        0.5, ordertype="limit", price=2000.0))
    assert lim[40] == "2" and lim[44] == "2000" and lim[54] == "1"
    # market is permitted (exit escalation ladder's final rung, invariant #5)
    mkt = fx.decode(fx.new_order_single("S", "T", 1, "c1", "ETHUSD", "sell",
                                        0.5, ordertype="market"))
    assert mkt[40] == "1" and 44 not in mkt and mkt[54] == "2"


def test_new_order_single_guards():
    with pytest.raises(fx.FixError):
        fx.new_order_single("S", "T", 1, "c", "ETHUSD", "hodl", 1.0)   # side
    with pytest.raises(fx.FixError):
        fx.new_order_single("S", "T", 1, "c", "ETHUSD", "buy", 1.0,
                            ordertype="iceberg")                        # type
    with pytest.raises(fx.FixError):
        fx.new_order_single("S", "T", 1, "c", "ETHUSD", "buy", 1.0,
                            ordertype="limit", price=0)                 # price


def test_order_cancel_request():
    d = fx.decode(fx.order_cancel_request("S", "T", 1, "orig", "new",
                                          "ETHUSD", "sell"))
    assert d[35] == "F" and d[41] == "orig" and d[11] == "new" and d[54] == "2"


# ---------------------------------------------------- execution report
def test_parse_execution_report():
    r = fx.parse_execution_report(
        {35: "8", 37: "OID", 11: "COID", 150: "F", 39: "1", 55: "ETHUSD",
         54: "1", 32: "0.5", 31: "2000.0", 151: "0.5", 14: "0.5"})
    assert r.order_id == "OID" and r.cl_ord_id == "COID"
    assert r.exec_type == "F" and r.ord_status == "1" and r.side == "buy"
    assert r.last_qty == 0.5 and r.last_px == 2000.0 and r.cum_qty == 0.5


def test_parse_execution_report_rejects_non_report():
    with pytest.raises(fx.FixError):
        fx.parse_execution_report({35: "D"})


def test_parse_execution_report_coerces_bad_numbers_and_unknown_side():
    r = fx.parse_execution_report({35: "8", 31: "not-a-number", 54: "9"})
    assert r.last_px == 0.0 and r.side == "?"


# ------------------------------------------------------ session bookkeeping
def test_out_sequence_is_monotonic():
    s = fx.FixSession("S", "T")
    assert s.next_out() == 1 and s.next_out() == 2 and s.out_seq == 3


def test_accepts_in_order_messages():
    s = fx.FixSession("S", "T")
    assert s.accept_in(1) is True and s.accept_in(2) is True
    assert s.in_seq_expected == 3 and s.gaps == []


def test_records_gap_on_skipped_sequence():
    s = fx.FixSession("S", "T")
    assert s.accept_in(1) is True
    assert s.accept_in(5) is False           # skipped 2,3,4
    assert s.gaps == [(2, 4)] and s.in_seq_expected == 5


def test_ignores_stale_or_duplicate_sequence():
    s = fx.FixSession("S", "T")
    s.accept_in(1)
    s.accept_in(2)
    assert s.accept_in(1) is False           # old/dup: no advance, no gap
    assert s.in_seq_expected == 3 and s.gaps == []
