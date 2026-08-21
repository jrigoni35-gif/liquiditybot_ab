"""
core/sanitize.py

Hardened parsing boundary for ALL untrusted external data. Every feed
that pulls from a website or exchange (news RSS, CoinGecko, Fear&Greed,
Reddit, and the exchange REST responses) routes its parsing through
here so a hostile, compromised, or merely broken remote endpoint cannot:

  * inject NaN / Infinity - Python's json accepts them by default, and
    a single NaN poisons every downstream comparison while Infinity
    blows out position sizing. safe_float rejects both.
  * blow up memory - responses are size-capped before parsing.
  * mount an XML entity-expansion ("billion laughs") DoS - RSS is
    parsed with defusedxml, which disables entity expansion and
    external entity resolution.
  * push absurd values into the model/risk math - numeric fields are
    clamped to sane domains at the boundary, not trusted downstream.

Nothing here trusts the remote to be honest. This is defense in depth
on top of using read-only feeds and a withdrawal-disabled exchange key.
"""

import json
import logging
import math
import time
from typing import Optional

log = logging.getLogger("liquiditybot.sanitize")

# Reject any response body larger than this before parsing (bytes).
MAX_RESPONSE_BYTES = 5_000_000


def safe_float(value, default: float = 0.0,
            lo: Optional[float] = None, hi: Optional[float] = None) -> float:
    """Coerce to a FINITE float, optionally clamped. NaN/Inf/garbage -> default.
    This is the single choke point that keeps poisoned numbers out of the
    feature vector and the risk engine."""
    try:
        f = float(value)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(f):            # NaN, +Inf, -Inf all rejected
        return default
    if lo is not None and f < lo:
        return lo
    if hi is not None and f > hi:
        return hi
    return f


def is_finite(x) -> bool:
    """True iff x is a real, finite number (not bool-excluding — callers that
    build math on it already treat bool as int). The single home for the
    `isinstance(x,(int,float)) and math.isfinite(x)` predicate copied across
    the execution/risk modules."""
    return isinstance(x, (int, float)) and math.isfinite(x)


def is_finite_pos(x) -> bool:
    """True iff x is a finite, strictly-positive number. Single home for the
    `_fin_pos`/`_finite_pos` predicate copied across execution modules."""
    return isinstance(x, (int, float)) and math.isfinite(x) and x > 0


def loads_bounded(text: str | None, max_bytes: int = MAX_RESPONSE_BYTES):
    """json.loads that (a) rejects oversized payloads and (b) refuses the
    non-standard NaN/Infinity/-Infinity tokens stdlib json otherwise
    accepts. Returns None on any problem rather than raising."""
    if text is None:
        return None
    if isinstance(text, str) and len(text) > max_bytes:
        log.warning(f"response {len(text)} bytes exceeds cap {max_bytes} - rejected")
        return None

    def _no_constants(tok):
        raise ValueError(f"non-finite JSON constant '{tok}' rejected")

    # W2 (adversarial review 2026-08-21): stdlib json REJECTS a leading
    # UTF-8 BOM ("Unexpected UTF-8 BOM") where simplejson accepted it. A
    # CDN/proxy/captive-portal rewrite is the realistic source, and the
    # rejection is permanent and per-poll, so a venue would silently drop
    # out of the composite feed forever. Strip it; a BOM carries no JSON
    # meaning. NOTE: parse_constant catches only the bare NaN/Infinity
    # TOKENS - IEEE overflow (1e400 -> inf) still parses to a non-finite
    # float here and always did (verified identical pre-change), so
    # downstream is_finite/safe_float guards remain load-bearing. This
    # boundary is not sufficient on its own.
    try:
        return json.loads(text.lstrip("﻿"), parse_constant=_no_constants)
    except (ValueError, TypeError) as e:
        log.warning(f"rejected malformed/hostile JSON: {e}")
        return None


def safe_rss_root(xml_text: str, max_bytes: int = MAX_RESPONSE_BYTES):
    """Parse RSS/Atom with defusedxml (entity expansion + external entity
    resolution disabled). Returns the root Element or None. Falls back to
    stdlib with a warning only if defusedxml isn't installed."""
    if xml_text is None:
        return None
    if isinstance(xml_text, str) and len(xml_text) > max_bytes:
        log.warning(f"XML {len(xml_text)} bytes exceeds cap {max_bytes} - rejected")
        return None
    try:
        import defusedxml.ElementTree as det_et
        try:
            return det_et.fromstring(xml_text)
        except Exception as e:          # ParseError, EntitiesForbidden, etc.
            log.warning(f"rejected malformed/hostile XML: {e}")
            return None
    except ImportError:
        # defusedxml is a hard requirement (see requirements.txt); this
        # fallback only executes in a broken install and is annotated for
        # the static scanner accordingly.
        log.error("defusedxml MISSING - RSS parsing is NOT hardened; "
                "install it: pip install defusedxml")
        import xml.etree.ElementTree as ET  # nosec B405 - guarded fallback only
        try:
            return ET.fromstring(xml_text)  # nosec B314 - unreachable when defusedxml present
        except ET.ParseError:
            return None


def cap_text(text: Optional[str], max_bytes: int = MAX_RESPONSE_BYTES) -> Optional[str]:
    """Truncate an oversized text body defensively (used by fetch wrappers)."""
    if text is None:
        return None
    if len(text) > max_bytes:
        log.warning(f"truncating {len(text)}-byte response to {max_bytes}")
        return text[:max_bytes]
    return text


def clean_book(book: dict, max_levels: int = 100) -> Optional[dict]:
    """Sanitize an order book from any venue: every price/size must be a
    finite positive number, levels are capped, and a book that ends up
    empty on a side is rejected (None). A poisoned book (NaN/negative/Inf
    price) must never reach fair value, the quoter, or stop logic."""
    if not isinstance(book, dict):
        return None
    out = {}
    for side in ("bids", "asks"):
        levels = book.get(side) or []
        clean = []
        for lvl in levels[:max_levels]:
            try:
                px = float(lvl[0])
                sz = float(lvl[1])
            except (TypeError, ValueError, IndexError):
                continue
            if math.isfinite(px) and math.isfinite(sz) and px > 0 and sz > 0:
                clean.append([px, sz])
        out[side] = clean
    if not out["bids"] or not out["asks"]:
        return None
    # A venue (or an adversary) can return levels in ANY order; downstream
    # trusts [0] to be the touch (best bid / best ask) for mid, imbalance,
    # fair value and STOP logic. Sort explicitly so an unsorted book can't
    # feed a wrong touch into the stop engine. Bids high->low, asks low->high.
    out["bids"].sort(key=lambda lvl: lvl[0], reverse=True)
    out["asks"].sort(key=lambda lvl: lvl[0])
    # sanity: best bid must be below best ask (reject crossed/garbage books)
    if out["bids"][0][0] >= out["asks"][0][0]:
        log.warning("rejected crossed/garbage order book (bid >= ask)")
        return None
    return out


def clean_candles(candles: list, max_n: int = 2000) -> list:
    """Sanitize OHLCV candles: drop any row with a non-finite or
    non-positive OHLC. Volume is coerced to finite non-negative."""
    if not isinstance(candles, list):
        return []
    out = []
    for c in candles[-max_n:]:
        try:
            o = safe_float(c["open"], 0.0)
            h = safe_float(c["high"], 0.0)
            lo = safe_float(c["low"], 0.0)
            cl = safe_float(c["close"], 0.0)
        except (TypeError, KeyError):
            continue
        if min(o, h, lo, cl) <= 0:
            continue
        # OHLC must be self-consistent: high is the ceiling, low the floor.
        # A row with high < low, or a body poking outside [low, high], is
        # physically impossible - a corrupt/adversarial candle that would
        # poison volatility (sigma_bar), ATR, swing points and every
        # candle-derived feature. Drop it rather than trust it.
        if h < lo or h < max(o, cl) or lo > min(o, cl):
            continue
        out.append({"time": c.get("time", 0), "open": o, "high": h,
                    "low": lo, "close": cl,
                    "volume": safe_float(c.get("volume"), 0.0, lo=0.0)})
    return out


_INTERVAL_UNIT_SEC = {"m": 60, "h": 3600, "H": 3600, "d": 86400,
                      "D": 86400, "w": 604800, "W": 604800, "M": 2592000}


def interval_str_to_sec(interval: str) -> float:
    """Venue bar-size string -> seconds. Case is load-bearing across both
    conventions in use (Binance '1m' minute vs '1M' month; OKX '1m'/'1H'/
    '1D'/'1M'): lowercase m is minutes, uppercase M is months."""
    try:
        return float(interval[:-1]) * _INTERVAL_UNIT_SEC[interval[-1]]
    except (KeyError, ValueError, IndexError, TypeError):
        return 0.0


def drop_forming_candles(candles: list, interval_sec: float,
                         now: Optional[float] = None,
                         committed_upto: Optional[float] = None) -> list:
    """Keep committed bars only: drop any bar whose window is still open
    (time + interval > now). Venues serve the currently-forming candle as
    the last row and its high/low/close keep mutating; an append-only
    downstream cache freezes the first sight, understating every intrabar
    range (missed triple-barrier touches, crushed ATR/sigma). Also sheds
    future-timestamped bars from clock skew or a venue glitch. A zero or
    unknown interval passes the list through untouched - better the old
    behavior than silently dropping everything.

    committed_upto: when the venue hands back its OWN authoritative
    committed-boundary timestamp (Kraken OHLC's `last` field - "id to be
    used as since when polling for new, committed OHLC data"), bars are
    cut against THAT instead of the local clock (W2-22). The local-clock
    heuristic has zero skew tolerance: a locally-fast clock can push
    `now - interval_sec` past a bar's open ts in the final skew-seconds of
    that bar's still-open window, admitting a forming bar the venue has not
    committed yet. committed_upto is exact - no skew is possible - so bars
    with time <= committed_upto are kept, all others dropped."""
    if not isinstance(candles, list) or not candles or interval_sec <= 0:
        return candles if isinstance(candles, list) else []
    if committed_upto is not None:
        return [c for c in candles if safe_float(c.get("time"), 0.0) <= committed_upto]
    cutoff = (time.time() if now is None else now) - interval_sec
    return [c for c in candles if safe_float(c.get("time"), 0.0) <= cutoff]
