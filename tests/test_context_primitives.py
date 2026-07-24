"""tests/test_context_primitives.py — Compounder Phase B context engine:
pure module-level primitives (no ContextFeed class yet — that is a later
task). Covers the CX-* code family and every deterministic helper in
data/context_engine.py: halving clock, phase bucketing, z-clipping, CME
expiry, event windows, and calendar-file loading (happy/missing/garbage).

Date-arithmetic anchors verified with `.venv/bin/python` before pinning:
2026-07-24 vs the last halving (2024-04-20) is 825 days; vs the
next-halving estimate (2028-04-17) is 633 days. These match the brief's
worked example exactly."""
import json
from datetime import datetime, timezone
from pathlib import Path

from core.codes import Code
from data.context_engine import (
    HALVING_DATES,
    cme_expiry_utc,
    clip_z,
    halving_clock,
    in_event_window,
    load_calendar,
    phase_bucket,
)

_BUCKETS = {"accumulation": 180, "expansion": 540, "euphoria": 900,
            "contraction": 1460}


def _ts(iso: str, hour: int = 0, minute: int = 0, second: int = 0) -> float:
    y, m, d = (int(x) for x in iso.split("-"))
    return datetime(y, m, d, hour, minute, second,
                    tzinfo=timezone.utc).timestamp()


# ---- CX codes registered and stable -----------------------------------

def test_cx_codes_registered_and_stable():
    assert Code.CX_POLL_OK.value == "CX-000"
    assert Code.CX_SOURCE_DARK.value == "CX-010"
    assert Code.CX_STATE_CHANGE.value == "CX-020"


# ---- HALVING_DATES ------------------------------------------------------

def test_halving_dates_tuple():
    assert HALVING_DATES == ("2012-11-28", "2016-07-09", "2020-05-11",
                              "2024-04-20")


# ---- halving_clock -------------------------------------------------------

def test_halving_clock_known_anchor():
    # verified with .venv/bin/python: (2026-07-24 - 2024-04-20) = 825 days;
    # (2028-04-17 - 2026-07-24) = 633 days. Matches the brief's example.
    now_ts = _ts("2026-07-24")
    days_since, days_to_next = halving_clock(now_ts, "2028-04-17")
    assert days_since == 825
    assert days_to_next == 633


def test_halving_clock_is_pure_utc_date_math_not_raw_seconds():
    # a timestamp late in the UTC day must not push days_since up by one -
    # the contract is calendar-date subtraction, not a raw /86400 division.
    now_ts = _ts("2026-07-24", hour=23, minute=59, second=59)
    days_since, days_to_next = halving_clock(now_ts, "2028-04-17")
    assert days_since == 825
    assert days_to_next == 633


def test_halving_clock_at_last_halving_is_zero():
    now_ts = _ts("2024-04-20")
    days_since, _ = halving_clock(now_ts, "2028-04-17")
    assert days_since == 0


# ---- phase_bucket ---------------------------------------------------------

def test_phase_bucket_boundaries():
    assert phase_bucket(0, _BUCKETS) == "accumulation"
    assert phase_bucket(179, _BUCKETS) == "accumulation"
    assert phase_bucket(180, _BUCKETS) == "expansion"          # at the bound
    assert phase_bucket(539, _BUCKETS) == "expansion"
    assert phase_bucket(540, _BUCKETS) == "euphoria"
    assert phase_bucket(899, _BUCKETS) == "euphoria"
    assert phase_bucket(900, _BUCKETS) == "contraction"
    assert phase_bucket(2000, _BUCKETS) == "contraction"       # clamp, no wrap


# ---- clip_z ----------------------------------------------------------------

def test_clip_z_basic_math():
    assert clip_z(55.0, 50.0, 10.0, 3.0) == 0.5


def test_clip_z_clips_high_and_low():
    assert clip_z(100.0, 50.0, 10.0, 3.0) == 3.0
    assert clip_z(20.0, 50.0, 10.0, 3.0) == -3.0


def test_clip_z_scale_zero_or_negative_is_safe():
    assert clip_z(100.0, 50.0, 0.0, 3.0) == 0.0
    assert clip_z(100.0, 50.0, -5.0, 3.0) == 0.0


# ---- cme_expiry_utc ----------------------------------------------------------

def test_cme_expiry_utc_known_month():
    ts = cme_expiry_utc(2026, 7)
    dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    assert (dt.year, dt.month, dt.day) == (2026, 7, 31)
    assert dt.weekday() == 4               # Friday
    assert (dt.hour, dt.minute) == (15, 30)


# ---- in_event_window ----------------------------------------------------

def test_in_event_window_edges():
    event_ts = 1_000_000.0
    pre_h, post_h = 2.0, 1.0
    # exactly at the event
    assert in_event_window(event_ts, event_ts, pre_h, post_h) is True
    # at the pre-window boundary (inclusive)
    assert in_event_window(event_ts - 2 * 3600, event_ts, pre_h, post_h) is True
    # just outside the pre-window
    assert in_event_window(event_ts - 2 * 3600 - 1, event_ts, pre_h, post_h) is False
    # at the post-window boundary (inclusive)
    assert in_event_window(event_ts + 1 * 3600, event_ts, pre_h, post_h) is True
    # just outside the post-window
    assert in_event_window(event_ts + 1 * 3600 + 1, event_ts, pre_h, post_h) is False


# ---- load_calendar ------------------------------------------------------

def test_load_calendar_happy(tmp_path: Path):
    p = tmp_path / "cal.json"
    p.write_text(json.dumps({"fomc": ["2026-01-28"]}), encoding="utf-8")
    data = load_calendar(p)
    assert data == {"fomc": ["2026-01-28"]}


def test_load_calendar_missing_file_returns_none(tmp_path: Path):
    assert load_calendar(tmp_path / "does_not_exist.json") is None


def test_load_calendar_garbage_returns_none_no_raise(tmp_path: Path):
    p = tmp_path / "garbage.json"
    p.write_text("{not valid json at all", encoding="utf-8")
    assert load_calendar(p) is None


def test_load_calendar_shipped_file_is_valid():
    root = Path(__file__).resolve().parents[1]
    data = load_calendar(root / "data" / "context_calendar.json")
    assert data is not None
    assert "fomc" in data
    assert len(data["fomc"]) == 8
    assert data["fomc"][0] == "2026-01-28"
