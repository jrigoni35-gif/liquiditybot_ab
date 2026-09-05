"""Kraken's PUBLISHED fee schedule, and the tier that binds at a given volume.

WHY THIS EXISTS. The booked fee has been wrong three times in three weeks, and
every time it was a struck literal that went stale:

    original   25/40 bps   understated vs the venue
    cut #8     40/80 bps   assumed a zero-volume account; ~2x over-stated
    cut #9     22/38 bps   from an account screenshot - and NOT A ROW in the
                           venue's published schedule at all

Each correction was itself booked as a new literal, so each one set up the
next error. The defect is not any particular number: it is that a fee lives in
the source as a constant with no relationship to the venue that charges it.
This module removes that class. Nothing here BOOKS a fee - booking is fee
policy and cohort-resetting. This is the reference schedule and the arithmetic
for reading it, so that every other file can compare itself against the venue
instead of against a memory of the venue.

THE SCHEDULE BELOW IS A FALLBACK, NOT AN AUTHORITY. It is what the venue
published when it was last read, stamped. The authority is the live endpoint,
and `scripts/fee_drift_report.py` is what keeps the two honest: it fetches
live, diffs against this table AND against config, and says so out loud. A
test pins the table against the live endpoint whenever a network is available
(skipped, never silently passed, when it is not).

Read 2026-09-05T14:33:42Z from https://api.kraken.com/0/public/AssetPairs,
verified IDENTICAL across FLOW/USD, ETH/USD, XBT/USD, SOL/USD and LINK/USD -
so it is an account-wide spot schedule, not a per-pair one.
Re-derive with:
    python scripts/fee_drift_report.py
"""
from __future__ import annotations

import logging

log = logging.getLogger("liquiditybot.core.venue_fees")

# (30-day USD volume at or above which the row binds, maker bps, taker bps).
# Ascending by volume. Kraken's convention: the highest row whose volume
# threshold the account meets is the one that applies.
KRAKEN_SPOT_SCHEDULE: tuple = (
    (0.0, 25.0, 40.0),
    (10_000.0, 20.0, 35.0),
    (50_000.0, 14.0, 24.0),
    (100_000.0, 12.0, 22.0),
    (250_000.0, 10.0, 20.0),
    (500_000.0, 8.0, 18.0),
    (1_000_000.0, 6.0, 16.0),
    (2_500_000.0, 4.0, 14.0),
    (5_000_000.0, 2.0, 12.0),
    (10_000_000.0, 0.0, 10.0),
    (100_000_000.0, 0.0, 8.0),
    (500_000_000.0, 0.0, 5.0),
)
# The first cut of this table held only the first FOUR rows, because the probe
# that produced it printed `[:4]` and the truncation was copied without being
# noticed. scripts/fee_drift_report.py caught it on its first run against the
# live endpoint - which is the entire argument for having a drift detector
# rather than a carefully-written constant. A reference table cannot confirm
# itself; only the venue can.
SCHEDULE_READ_UTC = "2026-09-05T14:47Z"
SCHEDULE_SOURCE = "https://api.kraken.com/0/public/AssetPairs"


def binding_row(volume_30d_usd: "float | None") -> "tuple[float, float] | None":
    """(maker_bps, taker_bps) for the tier that binds at this 30-day volume.

    Returns None when the volume is unknown, negative or not a number. That is
    deliberate and is the whole point of the module: a tier CANNOT be resolved
    without a volume, and returning a plausible default here would recreate
    exactly the struck-literal failure this file exists to end. An unknown
    volume must propagate as unknown, never as the bottom row.
    """
    if volume_30d_usd is None or isinstance(volume_30d_usd, bool):
        return None
    try:
        vol = float(volume_30d_usd)
    except (TypeError, ValueError):
        return None
    if vol < 0 or vol != vol:            # negative or NaN
        return None
    row = None
    for threshold, maker, taker in KRAKEN_SPOT_SCHEDULE:
        if vol >= threshold:
            row = (maker, taker)
        else:
            break
    return row


def best_possible_row() -> "tuple[float, float]":
    """The cheapest fees the venue offers at ANY volume.

    This is the only honest "fees cannot be lower than this" bound, and it is
    what an understated-fee tripwire should compare against. core/config_guard
    previously used a struck 40/80 for that purpose - a figure that is not a
    row in the schedule and is 1.6x the venue's own WORST (zero-volume) row, so
    it flagged legitimate configurations as understated and had to be switched
    off with allow_sub_floor_fees to ship a correct value.
    """
    return (KRAKEN_SPOT_SCHEDULE[-1][1], KRAKEN_SPOT_SCHEDULE[-1][2])


def worst_row() -> "tuple[float, float]":
    """The zero-volume row - the most any spot account pays."""
    return (KRAKEN_SPOT_SCHEDULE[0][1], KRAKEN_SPOT_SCHEDULE[0][2])


def is_a_published_row(maker_bps: float, taker_bps: float) -> bool:
    """Is this pair EXACTLY a row the venue publishes?

    Booking a maker/taker pair that is not a row means the number came from
    somewhere other than the schedule - a screenshot, a memory, an average, or
    an older tier. Every one of the three historical fee errors would have
    answered False here, including cut #9's 22/38, which sits between the
    20/35 and 25/40 rows and matches neither.
    """
    return any(abs(maker_bps - m) < 1e-9 and abs(taker_bps - t) < 1e-9
               for _v, m, t in KRAKEN_SPOT_SCHEDULE)


def fetch_live_schedule(pair: str = "ETH/USD", timeout: float = 20.0):
    """The venue's CURRENT schedule for one pair, or None on ANY failure.

    Public endpoint, no credentials, read-only. Returns the same
    ((volume, maker_bps, taker_bps), ...) shape as the table above so the two
    are directly comparable. None - never a fabricated schedule - on transport
    failure, a non-JSON body, or a shape this does not recognise: an
    unreachable venue must read as UNKNOWN, exactly like an unknown volume.

    NOT called at boot. config_guard must never block startup on a network
    round trip; it reads the static table. This exists for the drift report
    and for the test that pins the table against reality.
    """
    import json
    import urllib.request
    # SCHEME CHECK BEFORE OPEN (bandit B310). urlopen honours file:// and
    # ftp://, so an endpoint that ever became attacker-influenceable could
    # read local files. SCHEDULE_SOURCE is a module constant today and a test
    # pins that it stays one - this is the defence in depth for the day
    # someone makes it configurable, which is exactly the edit that turns a
    # fee reader into an SSRF. Refuse rather than fall back: an unreadable
    # schedule is UNKNOWN, never a guess.
    if not SCHEDULE_SOURCE.startswith("https://"):
        log.error("venue fee source is not https - refusing to fetch: %r",
                  SCHEDULE_SOURCE)
        return None
    try:
        with urllib.request.urlopen(  # nosec B310 - https enforced above
                SCHEDULE_SOURCE, timeout=timeout) as fh:
            body = json.loads(fh.read().decode("utf-8", errors="replace"))
        result = body.get("result") or {}
        for meta in result.values():
            if meta.get("wsname") != pair:
                continue
            taker = meta.get("fees") or []
            maker = meta.get("fees_maker") or []
            if not taker or not maker or len(taker) != len(maker):
                return None
            rows = []
            # strict=True: the length equality is checked above, but a silent
            # zip truncation here would drop tiers off the end of the schedule
            # and read as agreement - the same shape as the [:4] truncation
            # that produced the first, wrong version of the reference table.
            for (v_t, pct_t), (v_m, pct_m) in zip(taker, maker, strict=True):
                if float(v_t) != float(v_m):
                    return None          # schedules not aligned; refuse to guess
                # ROUND. The venue publishes percent; bps is *100, and binary
                # floating point makes 0.14*100 == 14.000000000000002. An
                # exact tuple comparison against the reference table then
                # reports DRIFT on two rows that are identical, which would
                # train a reader to ignore this report - the way every alarm
                # dies. 6 dp is far finer than any real schedule step.
                rows.append((float(v_t), round(float(pct_m) * 100.0, 6),
                             round(float(pct_t) * 100.0, 6)))
            return tuple(rows)
        return None
    except Exception:                     # noqa: BLE001 - report-only, fail closed
        log.debug("venue fee schedule unreachable", exc_info=True)
        return None
