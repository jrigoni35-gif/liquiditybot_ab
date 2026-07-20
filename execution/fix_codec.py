"""
execution/fix_codec.py — FIX 4.4 codec + session bookkeeping, rev 4

Transport groundwork for institutional connectivity (Kraken and prime
brokers offer FIX to onboarded institutional accounts). This module is
the PROTOCOL layer only: wire-exact message encoding/decoding with
BodyLength(9) and CheckSum(10) computed per spec, builders for the
session and order messages this bot would need, and monotonic sequence
tracking with gap detection.

It deliberately contains NO sockets and is wired to nothing: the live
order path stays on the hardened REST order_manager until a FIX session
is a conscious, credentialed decision (see docs/EXECUTION_CONNECTIVITY
.md for the onboarding contract). Shipping the codec now means the
transport swap later is an adapter, not a rewrite — and the codec is
fully unit-testable today.

Messages implemented: Logon(A), Heartbeat(0), TestRequest(1),
Logout(5), NewOrderSingle(D), OrderCancelRequest(F), ExecutionReport(8)
parse-side. Repeating groups are out of scope (not needed for these
types).

Hard-off stub, deliberately unreferenced by the engine: execution
eligibility is Kraken-only (CLAUDE.md invariant #3 - IBKR/DMA/prime/FIX
adapters exist as hard-off stubs). The builders are kept for protocol
fidelity should a venue ever be certified, NOT wired to any live path.
Do not flag them as dead code and do not wire them up.
"""

import time
from dataclasses import dataclass, field

SOH = "\x01"
BEGIN_STRING = "FIX.4.4"


class FixError(ValueError):
    pass


# ---------------------------------------------------------------------------
# wire codec
# ---------------------------------------------------------------------------
def encode(msg_type: str, fields: list, sender: str, target: str,
           seq_num: int, sending_time: float | None = None) -> str:
    """fields: [(tag:int, value)] in application order. Returns the full
    wire string with 8/9/35/49/56/34/52 header and trailer 10."""
    ts = time.strftime("%Y%m%d-%H:%M:%S",
                       time.gmtime(sending_time if sending_time is not None
                                   else time.time()))
    body_fields = [(35, msg_type), (49, sender), (56, target),
                   (34, int(seq_num)), (52, ts)] + list(fields)
    body = "".join(f"{t}={v}{SOH}" for t, v in body_fields)
    head = f"8={BEGIN_STRING}{SOH}9={len(body)}{SOH}"
    partial = head + body
    checksum = sum(partial.encode("ascii", "replace")) % 256
    return f"{partial}10={checksum:03d}{SOH}"


def decode(raw: str) -> dict:
    """Parse a wire message into {tag:int -> value:str}; verifies
    BodyLength(9) and CheckSum(10) or raises FixError. Duplicate tags
    keep the LAST occurrence (sufficient for non-group messages)."""
    if not raw or not raw.startswith(f"8={BEGIN_STRING}{SOH}"):
        raise FixError("FIX-001: missing/unsupported BeginString")
    try:
        nine = raw.index(f"{SOH}9=")
        body_start = raw.index(SOH, nine + 1) + 1
        declared = int(raw[nine + 3:body_start - 1])
    except (ValueError, IndexError):
        raise FixError("FIX-002: malformed BodyLength") from None
    ten = raw.rfind(f"{SOH}10=")
    if ten < 0 or not raw.endswith(SOH):
        raise FixError("FIX-003: missing CheckSum trailer")
    body = raw[body_start:ten + 1]
    if len(body) != declared:
        raise FixError(f"FIX-004: BodyLength {declared} != actual "
                       f"{len(body)}")
    declared_ck = raw[ten + 4:-1]
    actual_ck = sum(raw[:ten + 1].encode("ascii", "replace")) % 256
    if f"{actual_ck:03d}" != declared_ck:
        raise FixError(f"FIX-005: CheckSum {declared_ck} != computed "
                       f"{actual_ck:03d}")
    out = {}
    for pair in raw.split(SOH):
        if not pair:
            continue
        tag, _, val = pair.partition("=")
        try:
            out[int(tag)] = val
        except ValueError:
            raise FixError(f"FIX-006: non-numeric tag {tag!r}") from None
    return out


# ---------------------------------------------------------------------------
# message builders (application layer)
# ---------------------------------------------------------------------------
def logon(sender: str, target: str, seq: int, heartbeat_sec: int = 30,
          reset_seq: bool = False) -> str:
    f: list[tuple[int, object]] = [(98, 0), (108, int(heartbeat_sec))]
    if reset_seq:
        f.append((141, "Y"))
    return encode("A", f, sender, target, seq)


def heartbeat(sender: str, target: str, seq: int,
              test_req_id: str | None = None) -> str:
    f = [(112, test_req_id)] if test_req_id else []
    return encode("0", f, sender, target, seq)


def test_request(sender: str, target: str, seq: int, req_id: str) -> str:
    return encode("1", [(112, req_id)], sender, target, seq)


def logout(sender: str, target: str, seq: int, text: str = "") -> str:
    return encode("5", [(58, text)] if text else [], sender, target, seq)


_SIDES = {"buy": "1", "sell": "2"}
_ORDTYPES = {"market": "1", "limit": "2"}
_TIF = {"day": "0", "gtc": "1", "ioc": "3", "fok": "4"}


def new_order_single(sender: str, target: str, seq: int, cl_ord_id: str,
                     symbol: str, side: str, qty: float,
                     ordertype: str = "limit", price: float | None = None,
                     tif: str = "gtc") -> str:
    """Mirrors the order_manager contract: entries are LIMIT-only;
    building a market entry here raises, same invariant, same reason."""
    if side not in _SIDES:
        raise FixError(f"FIX-010: side {side!r}")
    if ordertype not in _ORDTYPES:
        raise FixError(f"FIX-011: ordertype {ordertype!r}")
    if ordertype == "limit" and (price is None or float(price) <= 0):
        raise FixError("FIX-012: limit order without a positive price")
    f = [(11, cl_ord_id), (55, symbol), (54, _SIDES[side]),
         (60, time.strftime("%Y%m%d-%H:%M:%S", time.gmtime())),
         (38, f"{float(qty):.10g}"), (40, _ORDTYPES[ordertype]),
         (59, _TIF.get(tif, "1"))]
    if ordertype == "limit":
        assert price is not None  # guaranteed by the FIX-012 guard above
        f.append((44, f"{float(price):.10g}"))
    return encode("D", f, sender, target, seq)


def order_cancel_request(sender: str, target: str, seq: int,
                         orig_cl_ord_id: str, cl_ord_id: str,
                         symbol: str, side: str) -> str:
    return encode("F", [(41, orig_cl_ord_id), (11, cl_ord_id),
                        (55, symbol), (54, _SIDES.get(side, "1"))],
                  sender, target, seq)


@dataclass
class ExecReport:
    order_id: str
    cl_ord_id: str
    exec_type: str        # 0=new 4=canceled 8=rejected F=trade ...
    ord_status: str
    symbol: str
    side: str
    last_qty: float
    last_px: float
    leaves_qty: float
    cum_qty: float


def parse_execution_report(fields: dict) -> ExecReport:
    if fields.get(35) != "8":
        raise FixError("FIX-020: not an ExecutionReport")
    side = {v: k for k, v in _SIDES.items()}.get(fields.get(54, ""), "?")

    def num(tag):
        try:
            return float(fields.get(tag, 0) or 0)
        except (TypeError, ValueError):
            return 0.0
    return ExecReport(order_id=fields.get(37, ""),
                      cl_ord_id=fields.get(11, ""),
                      exec_type=fields.get(150, ""),
                      ord_status=fields.get(39, ""),
                      symbol=fields.get(55, ""), side=side,
                      last_qty=num(32), last_px=num(31),
                      leaves_qty=num(151), cum_qty=num(14))


# ---------------------------------------------------------------------------
@dataclass
class FixSession:
    """Sequence bookkeeping with gap detection — the part of the FIX
    session layer that must be exactly right and is pure logic."""
    sender: str
    target: str
    out_seq: int = 1
    in_seq_expected: int = 1
    gaps: list = field(default_factory=list)

    def next_out(self) -> int:
        n = self.out_seq
        self.out_seq += 1
        return n

    def accept_in(self, seq: int) -> bool:
        """True if in-order; records a gap and returns False otherwise
        (caller would issue ResendRequest in a live session)."""
        if seq == self.in_seq_expected:
            self.in_seq_expected += 1
            return True
        if seq > self.in_seq_expected:
            self.gaps.append((self.in_seq_expected, seq - 1))
            self.in_seq_expected = seq
        return False