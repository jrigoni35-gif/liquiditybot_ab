"""Kraken's PUBLISHED fee schedule, and the tier that binds at a given volume.

WHY THIS EXISTS. The booked fee has been wrong FOUR times in four weeks, and
every time it was a struck literal that went stale:

    original   25/40 bps   the legacy API ladder's bottom row
    cut #8     40/80 bps   assumed a zero-volume account; ~2x over-stated
                           versus the account's real tier - but it IS Tier 1
                           of the venue's current ladder (see below)
    cut #9     22/38 bps   from the operator's app screenshot (2026-08-29:
                           "Tier 3, $17,482 30-day") - and it was RIGHT: 22/38
                           is Tier 3 of the current ladder
    cut #10    20/35 bps   "E1 fee correction", booked because the FIRST
                           version of THIS module said 22/38 "is not a
                           published row" and 20/35 binds at $17,482. Both
                           false. This module had read the LEGACY ladder from
                           /0/public/AssetPairs on 2026-09-05 - an array the
                           endpoint stopped serving by 2026-09-08 (it now
                           returns `fees: []`) - and its docstring called that
                           table the venue's schedule. 20/35 is Tier 4 and
                           needs $25,000 30-day volume or $50k assets on
                           platform. The instrument built to end this class
                           of error committed it. Fourth instance of
                           the-method recurrence #1.

Each correction was itself booked as a new literal, so each one set up the
next error. The defect is not any particular number: it is that a fee lives in
the source as a constant with no relationship to the venue that charges it.
This module removes that class. Nothing here BOOKS a fee - booking is fee
policy and cohort-resetting. This is the reference schedule and the arithmetic
for reading it, so that every other file can compare itself against the venue
instead of against a memory of the venue.

THE SCHEDULE BELOW IS A FALLBACK, NOT AN AUTHORITY. It is what the venue
published when it was last read, stamped. The authority is the venue's fee
page (SCHEDULE_PAGE) - the JSON endpoint SCHEDULE_SOURCE no longer carries
fee arrays - and `scripts/fee_drift_report.py` is what keeps the two honest:
it fetches live, diffs against this table AND against config, and says so out
loud. A test pins the table against the live page whenever a network is
available (skipped, never silently passed, when it is not).

Read 2026-09-08T20:15:29Z from https://www.kraken.com/features/fee-schedule
(raw page text, no summarizer in the loop; "Cross-platform Fee Tiers" table,
the one captioned "Spot Crypto"). Tiers 1-4 corroborated by the operator's
Kraken-app screenshot of 2026-08-29 14:58 (Tier 3 = 0.22/0.38 at $17,482.46;
next tier at $25,001) - two routes, two dates, same rows. The venue now
grants a tier by the BEST OF 30-day spot volume OR assets on platform (AoP),
so a tier cannot be resolved from volume alone if the account holds assets -
volume alone gives a LOWER BOUND on the discount.
Re-derive with:
    python scripts/fee_drift_report.py
"""
from __future__ import annotations

import html as _html
import logging
import re

log = logging.getLogger("liquiditybot.core.venue_fees")

# (30-day USD volume at or above which the row binds, maker bps, taker bps).
# Ascending by volume. Kraken's convention: the highest row whose threshold
# the account meets is the one that applies. Tier names are the page's own.
KRAKEN_SPOT_SCHEDULE: tuple = (
    (0.0, 40.0, 80.0),             # Tier 1
    (2_500.0, 30.0, 60.0),         # Tier 2
    (10_000.0, 22.0, 38.0),        # Tier 3
    (25_000.0, 20.0, 35.0),        # Tier 4
    (50_000.0, 15.0, 30.0),        # Tier 5
    (100_000.0, 12.0, 25.0),       # Tier 6
    (250_000.0, 10.0, 22.0),       # Tier 7
    (500_000.0, 8.0, 20.0),        # Tier 8
    (1_000_000.0, 6.0, 18.0),      # Tier 9
    (2_500_000.0, 4.0, 15.0),      # Tier 10
    (5_000_000.0, 2.0, 12.0),      # Tier 11
    (10_000_000.0, 0.0, 10.0),     # Tier 12
    (50_000_000.0, 0.0, 9.0),      # Pro 1
    (100_000_000.0, 0.0, 8.0),     # Pro 2
    (250_000_000.0, 0.0, 7.0),     # Pro 3
    (400_000_000.0, 0.0, 6.0),     # Pro 4
    (500_000_000.0, 0.0, 5.0),     # Pro 5
)
# Assets-on-platform (USD) that ALSO grant each row, index-aligned with the
# schedule; None where the page prints "N/A". The page: "your tier is based on
# the best of: your spot trading volume, your Assets on Platform (AoP)".
KRAKEN_SPOT_AOP_USD: tuple = (
    None, None, 20_000.0, 50_000.0, 100_000.0, 200_000.0, 400_000.0,
    600_000.0, 1_000_000.0, 2_500_000.0, 5_000_000.0, 10_000_000.0,
    20_000_000.0, 25_000_000.0, 50_000_000.0, 80_000_000.0, 100_000_000.0,
)
# The first cut of this table held only the first FOUR rows, because the probe
# that produced it printed `[:4]` and the truncation was copied without being
# noticed. The second cut held the LEGACY ladder (25/40, 20/35 at $10k, 14/24
# ...) because the JSON endpoint still served it on 2026-09-05 while the
# venue's page - and the operator's account - were already on the ladder
# above. A reference table cannot confirm itself; only the venue can, and
# only the source the venue actually keeps current.
SCHEDULE_READ_UTC = "2026-09-08T20:15:29Z"
SCHEDULE_SOURCE = "https://api.kraken.com/0/public/AssetPairs"
SCHEDULE_PAGE = "https://www.kraken.com/features/fee-schedule"
# The caption that follows the spot-crypto table on the page. The parser
# anchors on it because the page carries a SECOND ladder ("Spot Maker Rebate":
# 0.38/0.80 at $0, 0.20/0.38 at $10K ...) that also starts at $0+, and a
# stablecoin/FX table (0.20/0.20 ...). Taking "the first table" would be a
# coin flip between them.
_PAGE_CAPTION = "Spot Crypto Kraken uses a maker-taker"
_PAGE_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                               "liquiditybot-fee-drift/1.0"}
_ROW_RE = re.compile(
    r"(?:Tier|Pro)\s?\d+\s+\$([\d.,]+)\s?([KMB]?)\+\s+(N/A|[\d.]+\s?[kmbKMB]?)"
    r"\s+(-?\d+\.\d+)\s?%\s+(-?\d+\.\d+)\s?%")
_UNIT = {"": 1.0, "K": 1e3, "M": 1e6, "B": 1e9}


def _row_index(volume_30d_usd: "float | None") -> "int | None":
    if volume_30d_usd is None or isinstance(volume_30d_usd, bool):
        return None
    try:
        vol = float(volume_30d_usd)
    except (TypeError, ValueError):
        return None
    if vol < 0 or vol != vol:            # negative or NaN
        return None
    idx = None
    for i, (threshold, _m, _t) in enumerate(KRAKEN_SPOT_SCHEDULE):
        if vol >= threshold:
            idx = i
        else:
            break
    return idx


def _aop_index(aop_usd) -> "int | None":
    if aop_usd is None or isinstance(aop_usd, bool):
        return None
    try:
        aop = float(aop_usd)
    except (TypeError, ValueError):
        return None
    if aop < 0 or aop != aop:
        return None
    idx = None
    for i, thr in enumerate(KRAKEN_SPOT_AOP_USD):
        if thr is not None and aop >= thr:
            idx = i
    return idx


def binding_row(volume_30d_usd: "float | None",
                aop_usd: "float | None" = None) -> "tuple[float, float] | None":
    """(maker_bps, taker_bps) for the tier that binds at this 30-day volume,
    improved by assets on platform when that is known (the venue grants the
    better of the two).

    Returns None when the volume is unknown, negative or not a number - even
    if AoP is given. That is deliberate and is the whole point of the module:
    a tier CANNOT be resolved without a volume, and returning a plausible
    default here would recreate exactly the struck-literal failure this file
    exists to end. An unknown volume must propagate as unknown, never as the
    bottom row. With volume known and AoP unknown, the answer is a LOWER
    BOUND on the discount - say so wherever it is printed.
    """
    idx = _row_index(volume_30d_usd)
    if idx is None:
        return None
    a = _aop_index(aop_usd)
    if a is not None and a > idx:
        idx = a
    return (KRAKEN_SPOT_SCHEDULE[idx][1], KRAKEN_SPOT_SCHEDULE[idx][2])


def best_possible_row() -> "tuple[float, float]":
    """The cheapest fees the venue offers at ANY volume.

    This is the only honest "fees cannot be lower than this" bound, and it is
    what an understated-fee tripwire should compare against.
    """
    return (KRAKEN_SPOT_SCHEDULE[-1][1], KRAKEN_SPOT_SCHEDULE[-1][2])


def worst_row() -> "tuple[float, float]":
    """The zero-volume row - the most any spot account pays."""
    return (KRAKEN_SPOT_SCHEDULE[0][1], KRAKEN_SPOT_SCHEDULE[0][2])


def is_a_published_row(maker_bps: float, taker_bps: float) -> bool:
    """Is this pair EXACTLY a row the venue publishes?

    Booking a maker/taker pair that is not a row means the number came from
    somewhere other than the schedule - a screenshot, a memory, an average, or
    an older tier. The legacy ladder's 25/40 and 14/24 answer False here now;
    40/80 (Tier 1) and 22/38 (Tier 3) answer True. The first version of this
    function said the opposite of both, and cut #10 booked on its word.
    """
    return any(abs(maker_bps - m) < 1e-9 and abs(taker_bps - t) < 1e-9
               for _v, m, t in KRAKEN_SPOT_SCHEDULE)


def parse_fee_page(page_text: str):
    """The spot-crypto ladder from the venue's fee page as
    ((volume, maker_bps, taker_bps), ...) plus the aligned AoP tuple, or None.

    Pure; takes the raw HTML (or already-stripped text). Anchors on the caption
    that FOLLOWS the spot-crypto table and takes the last run of tier rows that
    starts at $0+ before it - so the maker-rebate and stablecoin tables, which
    also start at $0+, cannot be mistaken for it whatever order the page puts
    them in. None on anything it does not recognise: an unparseable page is
    UNKNOWN, never a guess.
    """
    if not page_text:
        return None
    txt = _html.unescape(re.sub(r"<[^>]+>", " ", page_text))
    txt = re.sub(r"\s+", " ", txt)
    cap = txt.find(_PAGE_CAPTION)
    if cap < 0:
        return None
    rows, aops = [], []
    for m in _ROW_RE.finditer(txt[:cap]):
        vol = float(m.group(1).replace(",", "")) * _UNIT[m.group(2).upper()]
        aop_s = m.group(3).replace(" ", "")
        if aop_s.upper() == "N/A":
            aop = None
        else:
            u = aop_s[-1].upper() if aop_s[-1].upper() in _UNIT else ""
            aop = float(aop_s[:-1] if u else aop_s) * _UNIT[u]
        maker = round(float(m.group(4)) * 100.0, 6)
        taker = round(float(m.group(5)) * 100.0, 6)
        if vol == 0.0:                       # a new table starts: reset
            rows, aops = [], []
        rows.append((vol, maker, taker))
        aops.append(aop)
    if len(rows) < 5 or rows[0][0] != 0.0:
        return None
    if any(rows[i][0] >= rows[i + 1][0] for i in range(len(rows) - 1)):
        return None                          # not ascending: not a ladder
    return tuple(rows), tuple(aops)


def fetch_page_schedule(timeout: float = 30.0):
    """The venue's CURRENT spot-crypto ladder from its fee page, in the same
    ((volume, maker_bps, taker_bps), ...) shape as the table above, or None on
    ANY failure (transport, blocked, unparseable). Read-only, no credentials.
    NOT called at boot. The page, not the JSON endpoint, is what the venue
    keeps current (measured 2026-09-08: AssetPairs `fees` is `[]`)."""
    import urllib.request
    if not SCHEDULE_PAGE.startswith("https://"):
        log.error("venue fee page is not https - refusing to fetch: %r",
                  SCHEDULE_PAGE)
        return None
    try:
        # The page answers 403 to Python's default User-Agent (measured
        # 2026-09-08) - a fetcher that swallowed that would skip its pin
        # forever and read as "no drift". The URL stays the module constant;
        # only the header changes, and the SSRF pin checks the Request's
        # first argument is that constant.
        with urllib.request.urlopen(  # nosec B310 - https enforced above
                urllib.request.Request(SCHEDULE_PAGE, headers=_PAGE_HEADERS),
                timeout=timeout) as fh:
            body = fh.read().decode("utf-8", errors="replace")
    except Exception:                     # noqa: BLE001 - report-only, fail closed
        log.debug("venue fee page unreachable", exc_info=True)
        return None
    parsed = parse_fee_page(body)
    return parsed[0] if parsed else None


def fetch_live_schedule(pair: str = "ETH/USD", timeout: float = 20.0):
    """The venue's per-pair fee arrays from the JSON endpoint, or None.

    Kept for the drift report's second route and the SSRF pin. As of
    2026-09-08 the endpoint returns `fees: []` / `fees_maker: []` for every
    spot pair, so this returns None - honestly UNKNOWN, never the legacy
    ladder it served until at least 2026-09-05. If it ever serves arrays
    again they are compared against the table like any other live read.
    Public endpoint, no credentials, read-only. NOT called at boot.
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
                # floating point makes 0.14*100 == 14.000000000000002.
                rows.append((float(v_t), round(float(pct_m) * 100.0, 6),
                             round(float(pct_t) * 100.0, 6)))
            return tuple(rows)
        return None
    except Exception:                     # noqa: BLE001 - report-only, fail closed
        log.debug("venue fee schedule unreachable", exc_info=True)
        return None
