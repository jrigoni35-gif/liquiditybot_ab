"""
data/context_engine.py — Compounder Phase B: cycle/macro context primitives.

Telemetry-only (spec §3, `docs/superpowers/specs/2026-07-24-compounder-
framework-design.md`): this phase's engine is read-only and reports
structural context to status/audit/gc_pusher exactly as Phase A's
conviction formula did before any gate consumed it. NO entry, exit,
sizing, or gate path in this codebase reads context state yet; `ml/
features.py` is untouched (ZERO new 5m model features per the evidence
doc's §0 conclusion). Wiring a consumer is a later task's job, not this
module's.

Honest unknown: every context source can go dark. A dark source degrades
its component to `known=False` — a STATE, never a guess, and never a
stale value re-presented as fresh. The grace window is 3x the source's
poll cadence, mirroring `data/webdata_feed.py:132-133`'s
`now - last_success < 3 * poll_sec` freshness rule. Absent sources never
fabricate values; this module ships only pure, deterministic helpers —
no network I/O, no stateful feed class (that is `ContextFeed`, built in
a later Phase B task).

Phase-bucket conventions: the halving-phase buckets below are labeled
CONVENTIONS, not statistical findings — n=3 completed halving cycles in
recorded history affords no claim of significance (evidence doc,
`docs/research/2026-07-24_compounder_context_evidence.md`, "Adopt at 0
model DoF: halving phase clock as structural gate (buckets are labeled
CONVENTIONS, not findings; down-only influence)"). Direction is never
signed from calendar or cycle inputs.
"""

import csv
import io
import logging
import math
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from core.sanitize import loads_bounded

log = logging.getLogger("liquiditybot.data.context_engine")

# Chain history (public, verifiable block-height constants) — see the
# task brief / evidence doc for sourcing. The next halving is NOT in this
# tuple: it is an ESTIMATE (block-clock projection), shipped separately as
# a config value (`context.next_halving_date`), refreshed as the epoch
# approaches.
HALVING_DATES: tuple[str, ...] = (
    "2012-11-28",
    "2016-07-09",
    "2020-05-11",
    "2024-04-20",
)


def _to_utc_date(ts: float) -> date:
    return datetime.fromtimestamp(ts, tz=timezone.utc).date()


def halving_clock(now_ts: float, next_halving_iso: str) -> tuple[int, int]:
    """(days_since_last, days_to_next) — pure UTC-date math (calendar-date
    subtraction, never a raw seconds/86400 division, so the time-of-day
    component of `now_ts` cannot shift the day count). `days_since` is
    measured from the most recent date in HALVING_DATES on or before
    `now_ts`'s UTC date; `days_to_next` is measured to the config-supplied
    `next_halving_iso` estimate (a block-clock projection, not a fact)."""
    now_date = _to_utc_date(now_ts)
    last_date = date.fromisoformat(HALVING_DATES[0])
    for iso in HALVING_DATES:
        d = date.fromisoformat(iso)
        if d <= now_date:
            last_date = d
        else:
            break
    days_since = (now_date - last_date).days
    next_date = date.fromisoformat(next_halving_iso)
    days_to_next = (next_date - now_date).days
    return days_since, days_to_next


def phase_bucket(days_since: int, buckets: dict) -> str:
    """Map days-since-halving to a named CONVENTION bucket. `buckets` is an
    ordered {name: upper_bound_days} mapping (e.g. {"accumulation": 180,
    "expansion": 540, "euphoria": 900, "contraction": 1460}); a name's
    bucket is `days_since < upper_bound`, checked in insertion order, so
    boundaries are exclusive on the upper side (180 lands in the NEXT
    bucket). `days_since` at or beyond the last bound CLAMPS to the last
    bucket's name rather than wrapping — a late cycle stays late until the
    next halving resets days_since to 0; order/monotonicity of `buckets`
    is guard-checked at the config layer (B3), not here."""
    last_name = ""
    for name, upper_bound in buckets.items():
        last_name = name
        if days_since < upper_bound:
            return name
    return last_name


def clip_z(value: float, center: float, scale: float, clip: float) -> float:
    """Center/scale a value into a symmetric z-like clip:
    `max(-clip, min(clip, (value-center)/scale))`. A non-positive `scale`
    is a degraded-config state, not a divide-by-zero crash: returns 0.0."""
    if scale <= 0:
        return 0.0
    z = (value - center) / scale
    return max(-clip, min(clip, z))


def cme_expiry_utc(year: int, month: int) -> float:
    """Epoch timestamp of the CME BRR/expiry reference: the last Friday of
    `month` at a fixed 15:30 UTC midpoint.

    _doc: the real reference (London 4pm BRR fix) is 16:00 UTC in winter
    and 15:00 UTC in summer (British Summer Time); rather than track DST
    transitions here, this uses a fixed 15:30 UTC midpoint and leans on
    the event-window half-width in config to absorb the +/-30min DST
    error — precision to the hour is irrelevant for a cadence-pause
    window, never a directional input."""
    last_day = _last_day_of_month(year, month)
    d = date(year, month, last_day)
    offset = (d.weekday() - 4) % 7   # Friday == weekday() 4
    d = d - timedelta(days=offset)
    dt = datetime(d.year, d.month, d.day, 15, 30, tzinfo=timezone.utc)
    return dt.timestamp()


def _last_day_of_month(year: int, month: int) -> int:
    if month == 12:
        next_month_first = date(year + 1, 1, 1)
    else:
        next_month_first = date(year, month + 1, 1)
    return (next_month_first - timedelta(days=1)).day


def in_event_window(now_ts: float, event_ts: float, pre_h: float,
                    post_h: float) -> bool:
    """True iff `now_ts` falls inside [event_ts - pre_h hours, event_ts +
    post_h hours], inclusive on both ends. Gates cadence (pause) only —
    never direction — per spec §3.4."""
    lo = event_ts - pre_h * 3600.0
    hi = event_ts + post_h * 3600.0
    return lo <= now_ts <= hi


def load_calendar(path: Path) -> dict | None:
    """Parse the shipped event calendar (`data/context_calendar.json`).
    Returns None on any missing/unreadable/invalid file — no raise — so a
    corrupt or absent calendar degrades the calendar component to
    `known=False` (unknown) rather than crashing the poll cycle."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as e:
        log.warning(f"context calendar unreadable at {path}: {e}")
        return None
    parsed = loads_bounded(text)
    if not isinstance(parsed, dict):
        return None
    return parsed


# ---- source parsers (Task B2) --------------------------------------------
#
# Free/keyless, no network I/O here (that is `ContextFeed`, a later task).
# Every parser returns None on empty/garbage/malformed input rather than
# raising — a dark or hostile source degrades its component to
# `known=False`, never a crash and never a fabricated value.


def parse_fred_csv(text: Optional[str]) -> Optional[float]:
    """Last non-missing numeric observation from a single-series FRED
    export (`fredgraph.csv?id=X`): two columns, one header row, "." marks
    a missing observation and is skipped. The real fetched fixtures'
    header reads `observation_date,<ID>` rather than the interface doc's
    generic `DATE,<ID>` — this parser does not depend on the header's
    literal spelling, only on treating row 0 as a header to be skipped
    (a non-numeric row 0 is skipped naturally by the same float() guard
    that skips any other malformed line, so no special-casing is needed).
    None on empty/garbage/header-only/all-missing content — never raises.
    """
    if not text:
        return None
    lines = text.splitlines()
    if len(lines) < 2:
        return None
    for line in reversed(lines[1:]):
        parts = line.strip().split(",")
        if len(parts) != 2:
            continue
        raw = parts[1].strip()
        if raw in ("", "."):
            continue
        try:
            value = float(raw)
        except ValueError:
            continue
        if not math.isfinite(value):
            continue
        return value
    return None


def parse_stablecoin_total(json_text: Optional[str]) -> Optional[float]:
    """Total circulating USD across all stablecoins from DefiLlama's `GET
    https://stablecoins.llama.fi/stablecoins?includePrices=false`: sum of
    `peggedAssets[].circulating.peggedUSD`, tolerant of entries missing
    the key (skipped, never zero-filled so one bad entry cannot silently
    understate the total). None on any parse failure — bad JSON, wrong
    shape, missing/empty `peggedAssets`, or zero contributing entries —
    never raises. An empty result is treated the same as a parse failure
    (honest unknown, not a fabricated zero)."""
    parsed = loads_bounded(json_text)
    if not isinstance(parsed, dict):
        return None
    assets = parsed.get("peggedAssets")
    if not isinstance(assets, list):
        return None
    total = 0.0
    found_any = False
    for asset in assets:
        if not isinstance(asset, dict):
            continue
        circulating = asset.get("circulating")
        if not isinstance(circulating, dict):
            continue
        raw = circulating.get("peggedUSD")
        if raw is None:
            continue
        try:
            value = float(raw)
        except (TypeError, ValueError):
            continue
        if not math.isfinite(value):
            continue
        total += value
        found_any = True
    if not found_any:
        return None
    return total


# Column positions in the CFTC "Traders in Financial Futures - Futures
# Only" report (dea/newcot `FinFutWk.txt`, HEADERLESS short format),
# 0-indexed. Verified against the real fetched fixture by cross-
# referencing the column-identical, header-carrying annual equivalent
# report (`fut_fin_txt_YYYY.zip` -> `FinFutYY.txt`, same 87-field layout)
# and aligning field-by-field across several distinct market rows; see
# tests/fixtures/context/README.md for the full verification transcript.
# Never derived from the documentation alone.
_COT_COL_MARKET_NAME = 0
_COT_COL_LEV_LONG = 14   # Lev_Money_Positions_Long_All
_COT_COL_LEV_SHORT = 15  # Lev_Money_Positions_Short_All
_COT_EXPECTED_FIELDS = 87   # verified field count of the dea FinFutWk.txt
                            # layout (cross-checked against the header'd
                            # annual FinFutYY.txt, Task B2); any other row
                            # shape = schema drift -> fail safe to None,
                            # never a silently-wrong read


def parse_cot_btc_lev_net(text: Optional[str]) -> Optional[float]:
    """Leveraged-funds net position (Lev_Money_Positions_Long_All minus
    _Short_All) for the standard CME BTC futures contract, from the CFTC
    Traders-in-Financial-Futures futures-only CSV. Exactly ONE COT series
    (pass-2 §1.3c) — a crowding/fragility dial for joint reading with
    `basis_bps`, never a signed directional input on its own.

    Columns are located BY DOCUMENTED POSITION (see `_COT_COL_*` above)
    because the real `FinFutWk.txt` fetch is headerless; header-name
    lookup is used instead whenever a source ships one (not applicable
    here). Returns the FIRST row whose market name contains both
    "BITCOIN" and "CHICAGO MERCANTILE" (the standard-size contract, ahead
    of the MICRO/NANO variants that also match both substrings) — 'first'
    matters, so row order is preserved, never sorted or deduplicated.
    None when no such row exists, the file is malformed (bad CSV, too few
    columns, non-numeric long/short fields), or `text` is empty — never
    raises."""
    if not text:
        return None
    try:
        rows = list(csv.reader(io.StringIO(text)))
    except csv.Error:
        return None
    for row in rows:
        if len(row) != _COT_EXPECTED_FIELDS:
            continue
        name = row[_COT_COL_MARKET_NAME].upper()
        if "BITCOIN" in name and "CHICAGO MERCANTILE" in name:
            try:
                long_ = float(row[_COT_COL_LEV_LONG].strip())
                short_ = float(row[_COT_COL_LEV_SHORT].strip())
            except ValueError:
                return None
            if not (math.isfinite(long_) and math.isfinite(short_)):
                return None
            return long_ - short_
    return None


# ---- dial math (Task B2) --------------------------------------------------
#
# All numeric anchors are CONVENTIONS supplied via `cfg` (a plain dict);
# the documented defaults below are used only when `cfg` omits a key, so
# wiring `config.json`'s `context` block in a later task is behavior-
# preserving by construction (identical defaults, never a bare literal in
# the decision path). Any missing/unknown input propagates to None -
# never a partial dial computed from incomplete data.


def stress_dial(dff_delta_90d: Optional[float], t10y2y: Optional[float],
                vix: Optional[float], cfg: dict) -> Optional[float]:
    """Mean of three `clip_z` terms - funding-rate delta, yield-curve
    inversion, and volatility - into a single unitless macro-stress dial.
    `cfg` keys (CONVENTION defaults in parens, used when the key is
    absent): `dff_delta_center` (0.0) / `dff_delta_scale` (0.5);
    `t10y2y_center` (0.0) / `t10y2y_scale` (0.5) - t10y2y is SIGN-FLIPPED
    before centering, so an inverted/negative curve reads as POSITIVE
    stress, not negative; `vix_center` (20.0) / `vix_scale` (10.0);
    `clip` (2.0), shared by all three terms. ANY of the three inputs
    being None propagates to an overall None - a partial read is never
    presented as a full one."""
    if dff_delta_90d is None or t10y2y is None or vix is None:
        return None
    clip = cfg.get("clip", 2.0)
    dff_term = clip_z(dff_delta_90d, cfg.get("dff_delta_center", 0.0),
                    cfg.get("dff_delta_scale", 0.5), clip)
    curve_term = clip_z(-t10y2y, cfg.get("t10y2y_center", 0.0),
                        cfg.get("t10y2y_scale", 0.5), clip)
    vix_term = clip_z(vix, cfg.get("vix_center", 20.0),
                    cfg.get("vix_scale", 10.0), clip)
    return (dff_term + curve_term + vix_term) / 3.0


def flow_dials(cot_net_now: Optional[float], cot_net_prev: Optional[float],
            stable_now: Optional[float], stable_prev: Optional[float],
            cfg: dict) -> tuple[Optional[float], Optional[float]]:
    """(cot_delta_z, stable_wk_pct) - two INDEPENDENT crowding/flow dials;
    each degrades to None on its OWN missing input without dragging the
    other one down (a first-poll `prev=None` for one source never blanks
    the other source's dial).

    `cot_delta_z` = `clip_z(cot_net_now - cot_net_prev, 0.0, cfg
    "cot_delta_scale" (default 5000.0), cfg "clip" (default 2.0))`; None
    if either COT input is missing (first poll has no `prev` yet).

    `stable_wk_pct` = `100 * (stable_now - stable_prev) / stable_prev`;
    None if either stablecoin input is missing OR `stable_prev <= 0` (a
    non-positive base makes a percent change meaningless, not merely a
    divide-by-zero to guard)."""
    if cot_net_now is None or cot_net_prev is None:
        cot_delta_z = None
    else:
        clip = cfg.get("clip", 2.0)
        cot_delta_z = clip_z(cot_net_now - cot_net_prev, 0.0,
                            cfg.get("cot_delta_scale", 5000.0), clip)
    if stable_now is None or stable_prev is None or stable_prev <= 0:
        stable_wk_pct = None
    else:
        stable_wk_pct = 100.0 * (stable_now - stable_prev) / stable_prev
    return cot_delta_z, stable_wk_pct
