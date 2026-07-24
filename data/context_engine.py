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
import json
import logging
import math
import time
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Optional

from core.codes import Code, tag
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


# ---- ContextFeed (Task B3) --------------------------------------------------
#
# Telemetry-only stateful poller: mirrors `data/webdata_feed.py`'s shape
# (injectable `fetch`, cadence early-return, per-source availability with
# a 3x-grace window — see webdata_feed.py:132-133) generalized from
# webdata's ONE combined availability flag to FIVE independent network
# sources (dff, t10y2y, vix, cot, stablecoins) feeding two dial groups,
# plus two purely-local components that need no grace at all: the
# halving clock (pure date math, always known) and the shipped event
# calendar (known iff the file parses THIS poll — a local file read
# either succeeds or it doesn't; there is no "flaky endpoint" to smooth
# over with a freshness window).
#
# Audit-vs-logging choice (see the class docstring below for the full
# reasoning): no module under data/ imports core.audit's get_audit() —
# verified against every data/*.py file, most directly webdata_feed.py,
# which never audits. Transitions here are logged through the standard
# `logging` module using the registered-code `tag()` formatter
# (core.codes.tag — a pure "CODE: detail" formatter + code_stats bump,
# no audit-chain dependency), never a new get_audit() call from the data
# layer.

try:
    import requests
except ImportError:                     # pragma: no cover
    requests = None

_UA = {"User-Agent": "liquiditybot/2.0 (research; contact: none)"}

# Network sources whose freshness gets the 3x-grace treatment. "calendar"
# and "halving" are LOCAL (no network, no grace — see module note above)
# and are tracked separately.
_NET_SOURCES: tuple[str, ...] = ("dff", "t10y2y", "vix", "cot", "stablecoins")

_DEFAULT_HISTORY_PATH = "outputs/context_history.jsonl"


def _default_fetch(url: str, timeout: float = 10.0) -> Optional[str]:
    """Mirrors `data/webdata_feed.py`'s `_default_fetch` exactly: same
    guard, same UA, same timeout, same "let it raise, the caller's
    per-source try/except turns it into a dark reading" contract (NOT a
    swallow-to-None here — the per-source try/except in `ContextFeed.
    _poll_source` is what stops one source's failure from ever reaching
    a caller, exactly like `WebDataFeed.maybe_poll`'s per-block
    try/except around each sub-fetch)."""
    if requests is None:
        return None
    resp = requests.get(url, headers=_UA, timeout=timeout)
    resp.raise_for_status()
    return resp.text


@dataclass
class ContextState:
    """One context poll's snapshot. Telemetry only this phase (spec §3):
    nothing in this codebase's entry/exit/sizing/gate path reads a
    ContextState yet. Every Optional field is None when its source (or
    source GROUP) is unknown — a STATE, never a guess, and never a stale
    value silently re-presented as fresh once its grace window lapses."""
    halving_phase: str = ""
    days_since: int = 0
    days_to_next: int = 0
    stress: Optional[float] = None
    stress_known: bool = False
    cot_z: Optional[float] = None
    stable_wk_pct: Optional[float] = None
    flow_known: bool = False
    in_event_window: bool = False
    next_event: str = ""
    calendar_known: bool = False
    ts: float = 0.0


class ContextFeed:
    """Compounder Phase B context engine (spec §3, evidence doc
    2026-07-24 both passes): a slow-cadence (default 6h, floored at 1h)
    poll producing a `ContextState`. TELEMETRY ONLY — no decision path in
    this codebase reads it until a later phase wires the long book.

    Audit note (read this before adding a get_audit() call here): NO
    module under `data/` imports `core.audit.get_audit()` — checked
    against `data/webdata_feed.py` and every other `data/*.py` module;
    the audit trail is wired one layer up, from execution/ml/main.py/
    core.fault. Rather than invent a new audit-layer dependency for the
    data layer just for this one feed, source/state transitions are
    logged through the standard `logging` module using the SAME
    registered-code `tag()` formatter the rest of the codebase uses
    (`core.codes.tag` — a pure "CODE: detail" formatter + code_stats
    tally bump, no audit-chain dependency) and are additionally
    surfaced structurally via `status()`. A later engine/runner wiring
    task is free to route these through `get_audit()` from main.py if a
    call site there wants them in the hash-chained trail too; this data-
    layer module does not create that path itself.

    Config-key translation note: B2's `stress_dial`/`flow_dials` read
    `dff_delta_center`/`dff_delta_scale`/`cot_delta_scale` (see their
    docstrings); the B3 config block (shipped verbatim, brief §context)
    uses the shorter `dff_center`/`dff_scale`/`cot_scale` spelling. Both
    default to the SAME numeric value today, so the mismatch is
    invisible until an operator tunes one of those three knobs and
    nothing happens. `__init__` translates the shipped names onto the
    dial functions' actual parameter names so the configured value is
    the one that actually reaches the math (see task-B3-report.md)."""

    def __init__(self, config: dict,
                fetch: Callable[[str], Optional[str]] | None = None,
                history_path: str | Path | None = None,
                calendar_path: str | Path | None = None):
        cfg = config or {}
        self.enabled = bool(cfg.get("enabled", True))
        poll_hours = float(cfg.get("poll_hours", 6.0))
        if poll_hours < 1.0:            # defense in depth; config_guard
            poll_hours = 1.0            # FATALs a configured value below 1
        self.poll_sec = poll_hours * 3600.0
        self.fetch = fetch or _default_fetch

        self._next_halving_iso = str(cfg.get("next_halving_date",
                                             "2028-04-17"))
        self._buckets = cfg.get("phase_bucket_days") or {
            "accumulation": 180, "expansion": 540, "euphoria": 900,
            "contraction": 1460}
        self._event_cfg = cfg.get("event_window", {}) or {}
        self._urls = cfg.get("urls", {}) or {}

        stress_raw = cfg.get("stress", {}) or {}
        self._stress_cfg = dict(stress_raw)
        if "dff_center" in stress_raw:
            self._stress_cfg.setdefault("dff_delta_center",
                                        stress_raw["dff_center"])
        if "dff_scale" in stress_raw:
            self._stress_cfg.setdefault("dff_delta_scale",
                                        stress_raw["dff_scale"])

        flow_raw = cfg.get("flow", {}) or {}
        # `flow.stable_scale_pct` is currently UNCONSUMED by flow_dials
        # (stable_wk_pct is raw percent) - reserved, do not tune expecting
        # effect.
        self._flow_cfg = dict(flow_raw)
        if "cot_scale" in flow_raw:
            self._flow_cfg.setdefault("cot_delta_scale", flow_raw["cot_scale"])

        self._calendar_path = Path(calendar_path) if calendar_path else (
            Path(__file__).resolve().parent / "context_calendar.json")
        self._history_path = Path(history_path or _DEFAULT_HISTORY_PATH)

        self._last_poll = 0.0
        self._last_success: dict[str, float] = {s: 0.0 for s in _NET_SOURCES}
        self._known: dict[str, bool] = {s: False for s in _NET_SOURCES}
        self._known["calendar"] = False
        self._known["halving"] = True   # local, deterministic, never dark

        self._prev_known: Optional[dict[str, bool]] = None
        self._prev_phase: Optional[str] = None
        self._prev_in_window: Optional[bool] = None
        self._first_poll_done = False

        self._prev_cot_net: Optional[float] = None
        self._prev_stable_total: Optional[float] = None

        self._state = ContextState()

        self._warm_start()

    # ---- warm start: seed flow-delta prev-values from the PIT file ------

    def _warm_start(self) -> None:
        """Read-only: seeds `_prev_cot_net`/`_prev_stable_total` from the
        LAST line of the PIT file so a process restart does not blank
        the weekly deltas back to a "first poll, no prior" state. Any
        missing file, I/O error, or malformed last line leaves both at
        None (behaves exactly like a genuine first poll) — never raises,
        never writes."""
        try:
            if not self._history_path.exists():
                return
            text = self._history_path.read_text(encoding="utf-8")
        except OSError as e:
            log.warning(f"context PIT warm-start unreadable: {e}")
            return
        lines = [ln for ln in text.splitlines() if ln.strip()]
        if not lines:
            return
        parsed = loads_bounded(lines[-1])
        if not isinstance(parsed, dict):
            return
        raw = parsed.get("raw")
        if not isinstance(raw, dict):
            return
        cot_net = raw.get("cot_net")
        stable_total = raw.get("stable_total")
        if isinstance(cot_net, (int, float)) and math.isfinite(cot_net):
            self._prev_cot_net = float(cot_net)
        if isinstance(stable_total, (int, float)) and \
                math.isfinite(stable_total):
            self._prev_stable_total = float(stable_total)

    # ---- per-source fetch + parse + 3x-grace availability ----------------

    def _poll_source(self, name: str, url: Optional[str], parser,
                     now: float) -> Optional[float]:
        """Returns THIS poll's genuinely-fresh parsed value, or None — a
        momentary miss inside the grace window is honestly reported as
        "no fresh reading this cycle" (never a carried-forward stale
        value dressed up as current; see the class docstring). The grace
        window smooths only the `_known` ok/dark CLASSIFICATION (used for
        status + CX-010/CX-020 transition alerting), exactly the shape
        `webdata_feed.py:132-133` uses: `now - last_success < 3 *
        poll_sec`, generalized to run once per source instead of once for
        the whole feed."""
        value = None
        if url:
            try:
                value = parser(self.fetch(url))
            except Exception as e:
                log.warning(f"context source '{name}' fetch failed: {e}")
                value = None
        if value is not None:
            self._last_success[name] = now
            self._known[name] = True
        else:
            self._known[name] = (
                now - self._last_success[name] < 3 * self.poll_sec)
        return value

    # ---- event window / next event ---------------------------------------

    @staticmethod
    def _nearest_cme_expiry(now_ts: float) -> float:
        """Nearest CME BTC futures expiry to `now_ts` (this month's or
        next month's last-Friday reference, whichever is closer) — purely
        local/deterministic, needs no calendar file."""
        d = _to_utc_date(now_ts)
        candidates = []
        for delta in (0, 1):
            y, m = d.year, d.month + delta
            if m > 12:
                y += 1
                m -= 12
            candidates.append(cme_expiry_utc(y, m))
        return min(candidates, key=lambda t: abs(t - now_ts))

    @staticmethod
    def _fomc_candidate_ts(fomc_dates) -> list:
        """FOMC statements release ~2pm ET; rather than track DST, use a
        fixed 18:00 UTC reference for every date (mirrors
        `cme_expiry_utc`'s fixed-midpoint rationale — the event window's
        half-width in config absorbs the +/-1h DST error). Malformed date
        strings are skipped, never raised."""
        out = []
        for d in fomc_dates or []:
            if not isinstance(d, str):
                continue
            try:
                y, m, dd = (int(x) for x in d.split("-"))
                out.append(datetime(y, m, dd, 18, 0,
                                    tzinfo=timezone.utc).timestamp())
            except (ValueError, TypeError):
                continue
        return out

    def _event_state(self, now: float,
                     calendar_data: Optional[dict]) -> tuple[bool, str]:
        ew = self._event_cfg
        fomc_pre = float(ew.get("fomc_pre_h", 24.0))
        fomc_post = float(ew.get("fomc_post_h", 6.0))
        expiry_pre = float(ew.get("expiry_pre_h", 8.0))
        expiry_post = float(ew.get("expiry_post_h", 2.0))

        candidates = [("cme_expiry", self._nearest_cme_expiry(now),
                      expiry_pre, expiry_post)]
        if isinstance(calendar_data, dict):
            fomc_ts_list = self._fomc_candidate_ts(calendar_data.get("fomc"))
            if fomc_ts_list:
                nearest_fomc = min(fomc_ts_list, key=lambda t: abs(t - now))
                candidates.append(("fomc", nearest_fomc, fomc_pre, fomc_post))

        in_window = False
        nearest_label = "none"
        nearest_dist = None
        for label, event_ts, pre_h, post_h in candidates:
            if in_event_window(now, event_ts, pre_h, post_h):
                in_window = True
            dist = abs(event_ts - now)
            if nearest_dist is None or dist < nearest_dist:
                nearest_dist = dist
                nearest_label = f"{label}:{_to_utc_date(event_ts).isoformat()}"
        return in_window, nearest_label

    # ---- PIT (point-in-time) append --------------------------------------

    def _append_pit(self, now: float, state: ContextState,
                    dff: Optional[float], t10y2y: Optional[float],
                    vix: Optional[float], cot_net: Optional[float],
                    stable_total: Optional[float]) -> None:
        """Append one JSON line — the as-observed snapshot for any future
        label join or replay to read (pass-2 §2.1, PIT discipline: never
        re-fetch). IO errors are swallowed with a log line; telemetry
        must never wedge the poll itself."""
        payload = {
            "ts": now,
            "state": asdict(state),
            "raw": {"dff": dff, "t10y2y": t10y2y, "vix": vix,
                    "cot_net": cot_net, "stable_total": stable_total},
        }
        try:
            self._history_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._history_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(payload) + "\n")
        except OSError as e:
            log.warning(f"context PIT append failed (telemetry only): {e}")

    # ---- transition-only audit logging -----------------------------------

    def _emit_transitions(self, state: ContextState) -> None:
        """CX-* transition logging — steady state is silent. Per-source
        ok->dark logs CX_SOURCE_DARK; dark->ok recovery AND any halving-
        phase/event-window flip log CX_STATE_CHANGE. The very first poll
        never emits a transition here (bootstrap: there is no PRIOR state
        to differ from) — it gets CX_POLL_OK instead, from `maybe_poll`."""
        if self._prev_known is not None:
            for name in (*_NET_SOURCES, "calendar"):
                prev = self._prev_known.get(name, False)
                cur = self._known[name]
                if prev and not cur:
                    log.warning(tag(Code.CX_SOURCE_DARK, f"{name} dark"))
                elif not prev and cur:
                    log.info(tag(Code.CX_STATE_CHANGE, f"{name} recovered"))
        if self._prev_phase is not None and \
                state.halving_phase != self._prev_phase:
            log.info(tag(Code.CX_STATE_CHANGE,
                        f"halving_phase {self._prev_phase} -> "
                        f"{state.halving_phase}"))
        if self._prev_in_window is not None and \
                state.in_event_window != self._prev_in_window:
            log.info(tag(Code.CX_STATE_CHANGE,
                        f"in_event_window {self._prev_in_window} -> "
                        f"{state.in_event_window}"))
        self._prev_known = dict(self._known)
        self._prev_phase = state.halving_phase
        self._prev_in_window = state.in_event_window

    # ---- poll --------------------------------------------------------------

    def maybe_poll(self, now: float | None = None) -> ContextState:
        now = now if now is not None else time.time()
        if not self.enabled or now - self._last_poll < self.poll_sec:
            return self._state
        self._last_poll = now

        # local: halving clock (always known, pure date math)
        days_since, days_to_next = halving_clock(now, self._next_halving_iso)
        phase = phase_bucket(days_since, self._buckets)

        # local: shipped event calendar (known iff it parses THIS poll)
        calendar_data = load_calendar(self._calendar_path)
        calendar_known = calendar_data is not None
        self._known["calendar"] = calendar_known

        # network: five keyless sources, each with its own 3x-grace known
        dff = self._poll_source("dff", self._urls.get("fred_dff"),
                                parse_fred_csv, now)
        t10y2y = self._poll_source("t10y2y", self._urls.get("fred_t10y2y"),
                                    parse_fred_csv, now)
        vix = self._poll_source("vix", self._urls.get("fred_vix"),
                                parse_fred_csv, now)
        cot_net = self._poll_source("cot", self._urls.get("cot_finfut"),
                                    parse_cot_btc_lev_net, now)
        stable_total = self._poll_source(
            "stablecoins", self._urls.get("stablecoins"),
            parse_stablecoin_total, now)

        stress = stress_dial(dff, t10y2y, vix, self._stress_cfg)
        cot_z, stable_wk_pct = flow_dials(
            cot_net, self._prev_cot_net, stable_total,
            self._prev_stable_total, self._flow_cfg)
        in_window, next_event = self._event_state(now, calendar_data)

        state = ContextState(
            halving_phase=phase, days_since=days_since,
            days_to_next=days_to_next, stress=stress,
            stress_known=stress is not None, cot_z=cot_z,
            stable_wk_pct=stable_wk_pct,
            flow_known=cot_z is not None and stable_wk_pct is not None,
            in_event_window=in_window, next_event=next_event,
            calendar_known=calendar_known, ts=now)

        self._emit_transitions(state)
        self._state = state

        # prev-values for the NEXT poll's delta persist across a miss —
        # a failed fetch must not blank the anchor, only skip this cycle
        if cot_net is not None:
            self._prev_cot_net = cot_net
        if stable_total is not None:
            self._prev_stable_total = stable_total

        self._append_pit(now, state, dff, t10y2y, vix, cot_net, stable_total)

        if not self._first_poll_done:
            self._first_poll_done = True
            log.info(tag(Code.CX_POLL_OK, "first context poll completed"))

        return state

    # ---- status ------------------------------------------------------------

    def status(self) -> dict:
        """JSON-safe telemetry snapshot: the latest ContextState fields
        flattened, the per-source ok/dark map, and last_poll_age_sec
        (None before the first poll has ever run)."""
        s = self._state
        age = round(time.time() - self._last_poll, 1) if self._last_poll \
            else None
        return {
            "enabled": self.enabled,
            "halving_phase": s.halving_phase,
            "days_since": s.days_since,
            "days_to_next": s.days_to_next,
            "stress": s.stress,
            "stress_known": s.stress_known,
            "cot_z": s.cot_z,
            "stable_wk_pct": s.stable_wk_pct,
            "flow_known": s.flow_known,
            "in_event_window": s.in_event_window,
            "next_event": s.next_event,
            "calendar_known": s.calendar_known,
            "sources": dict(self._known),
            "last_poll_age_sec": age,
        }
