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

import logging
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

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
