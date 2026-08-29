"""
data/candle_journal.py — the append-only candle store (SAFE class).

WHAT THIS IS. A price-path store: given (symbol, t0, horizon) it returns a
forward return or an EXPLICIT UNKNOWN with a reason. It exists because the
only price path on disk today is `entry_price` sampled irregularly into
outputs/signal_history.csv, and reconstructing forward returns by
self-joining that column is lossy in a way that is NOT random - the misses
concentrate in the thin alts whose sampling median is 5-10x sparser than
ETH's. A horizon statistic built on that join measures the SAMPLER.

CLASSIFICATION — SAFE AS SHIPPED, AND STRUCTURALLY HELD THERE.
This module is a DATA STORE READ BY ANALYSIS ONLY. It is imported by no
decision module: not main.py, not runner.py, not ml/features.py, and by
nothing under core/, execution/, risk/, regime/, strategies/, sentiment/
or api/. It places no order, changes no size, moves no stop, books no fee
and touches no fill. Wiring it into any of those is COHORT-RESETTING under
the era-5 moratorium (exec_era 8-ca55e2ba) and forbidden without operator
adjudication. That boundary is enforced by a repo-wide grep guard
(tests/test_candle_store_safe_class.py), not by this paragraph.

NO MODULE-LEVEL outputs/ PATH EXISTS HERE, DELIBERATELY. Ten leak-class
instances (a module constant under outputs/ that no test redirects) have
been found in this repo. `store_root()` is a FUNCTION and every public
call takes `root=`; tests pass tmp_path and there is no attribute for a
future maintainer to forget to register. If one is ever added it MUST join
tests/conftest.py:_REDIRECTED_PATH_ATTRS under the distinctive name
CANDLE_STORE_ROOT in the same commit, together with the redirect-proof pin
the sandbox sidecar's own suite already models (call main() with no --out,
then assert the module constant resolves under tmp_path AND that the real
outputs/ file does not exist). Pin P10 makes adding one without
registering it a CI red.

NOTE FOR ANY FUTURE EDITOR OF THIS DOCSTRING: several repo guards are
plain greps over non-test source for a module name they own. Naming such
a file here - even in prose, even in a citation - turns their green red.
Describe the pattern; do not spell the guarded name.

WHY CSV AND NOT SQLITE. The conftest audit hook that catches a stray write
into the operator's live outputs/ tree fires on the `open` audit event. It
is a live backstop for a CSV store; a measured sqlite3 write of 8,192
bytes produced ZERO audit events, so a sqlite store would ship past the
repo's own structural leak-class guard invisibly.

TIME AND UNIT LAW (this repo has already bought the ms/s incident twice).
  * Every timestamp in this store is `t_open_s`: UNIX SECONDS, UTC, and
    the bar's OPEN. The unit is in the column name and pinned by test.
  * A bar covers the HALF-OPEN interval [t_open_s, t_open_s + interval_s).
    `close` is therefore the price as of t_open_s + interval_s. That one
    sentence is the difference between a correct horizon study and a
    one-bar-shifted one.
  * `interval_s` is an INTEGER number of seconds from INTERVALS. It is
    never a venue interval string: core.sanitize.interval_str_to_sec is
    case-load-bearing ('m' minutes, 'M' months) and returns 0.0 on
    anything unparsable. That conversion belongs to the INGESTER.
  * A 13-digit millisecond value is refused LOUDLY, with its own counter
    (UNIT_RANGE). Without that counter the failure signature of a ms/s
    regression is silent total emptiness, indistinguishable from a dead
    endpoint.

UNKNOWN IS NEVER ZERO, NEVER INTERPOLATED, NEVER NEAREST. A gap yields no
Bar at all - not a placeholder, not NaN (a NaN bar in a numpy path is the
zero-fill sin wearing a different hat). An unknown field is '' on disk and
None in memory. There is NO tolerance parameter on any forward-return call
and there never will be (pin P11): a tolerance >= the horizon makes every
anchor match ITSELF and the cell reads 100% coverage, which is an artifact,
not data.

THE FIVE-WAY SPLIT IS THE WHOLE POINT AND IS NEVER COLLAPSED.
`NOT_COVERED` (we never looked - curable by fetching),
`NO_BAR_IN_COVERED_WINDOW` (we looked, the venue had nothing - a real
hole), `BEYOND_RIGHT_EDGE` (right-censored: the future has not happened
yet), `BEFORE_LEFT_EDGE` (backfillable past), and `STORE_UNREADABLE` (an
INSTRUMENT FAULT, never a data gap) are five different epistemic states.
Pooling censoring with holes biases every horizon-stratified number in one
direction and concentrates the bias in the thin-alt cohort.

NO ROTATION, NO INIT-TIME ANYTHING. A schema bump starts a NEW segment
({YYYY-MM}.v2.csv); the v1 segment is never opened for write again. No
byte this module wrote is ever renamed, truncated or rewritten by any code
path here. That is strictly stronger than "write-path-only rotation" and
removes the 2026-07-11 incident class (a schema bump plus init-time
rotation destroyed live rows) rather than guarding against it. Reading -
constructing a view, taking coverage, running any query - creates NOTHING:
not a directory, not a manifest, not an empty segment. Pin P8.

Re-deriving volatile facts (row counts, byte sizes, lane inventories):
    python scripts/candle_store.py verify --root <root>
No count is written into this docstring; a number in a permanent file
decays into a false claim.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import logging
import math
import os
import re
import socket
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from core.runtime import durable_append, read_json

log = logging.getLogger("liquiditybot.data.candle_journal")

# --------------------------------------------------------------------------
# schema
# --------------------------------------------------------------------------

SCHEMA_VERSION = 1

# THE HEADER IS THE SCHEMA. Extend at the END only - never rename, never
# reorder, never repurpose. A bump starts a new {YYYY-MM}.v{N}.csv segment;
# older segments keep their own header and are read under it.
BAR_COLUMNS: tuple[str, ...] = (
    "schema_version", "record_kind", "symbol", "interval_s", "source",
    "quote", "t_open_s", "open", "high", "low", "close", "volume",
    "committed_by", "ingest_s",
)

COVERAGE_COLUMNS: tuple[str, ...] = (
    "schema_version", "symbol", "interval_s", "source", "quote",
    "win_from_s", "win_to_s", "committed_upto_s", "committed_by",
    "bars_offered", "bars_accepted", "bars_dup", "bars_conflict",
    "bars_rejected", "status", "note", "observed_at_s",
)

# Per-generation column tuples, so a segment is always read under ITS OWN
# header rather than the current one.
_BAR_COLUMNS_BY_VERSION: dict[int, tuple[str, ...]] = {1: BAR_COLUMNS}
_COVERAGE_COLUMNS_BY_VERSION: dict[int, tuple[str, ...]] = {1: COVERAGE_COLUMNS}

RECORD_KINDS = frozenset({"BAR", "CONFLICT"})
INTERVALS: tuple[int, ...] = (60, 300, 900, 1800, 3600, 14400, 86400)
SOURCES = frozenset({"bot_cache", "kraken", "okx", "binanceus"})
QUOTES = frozenset({"USD", "USDT", "USDC"})
COMMITTED_BY = frozenset({"venue_last", "venue_confirm", "clock"})
STATUSES = frozenset({"OK", "FETCH_FAILED", "EMPTY"})
NOTES = frozenset({
    "", "window_inferred_from_response", "truncated_by_venue_cap",
    "schema_narrower_than_current",
})

# A symbol becomes a parquet filename and a journal cell. This regex is a
# SECURITY control, not tidiness: it is what makes ingest(symbol="../../
# status") raise instead of escaping the store root. The `_{interval_s}`
# filename suffix additionally puts a Windows reserved device stem
# (CON/AUX/NUL/PRN/COM1) out of reach.
_SYMBOL_RE = re.compile(r"^[A-Z0-9]{1,16}$")

# THE PRICE FORMATTER IS PART OF THE SCHEMA. Byte-identical to the corpus's
# own entry_price formatter (ml/history.py renders prices with %.10g), so a
# stored close and a corpus entry_price compare AS STRINGS with no
# re-derivation - which is the comparability this store exists to provide.
# Changing it makes every already-stored bar read as a CONFLICT. Pinned by
# test_price_formatter_is_pinned_to_the_corpus_formatter (P17).
_PRICE_FORMAT = "%.10g"

# Fields compared to decide duplicate-vs-conflict. ingest_s is PROVENANCE
# and is excluded from the comparison, from every join and from every
# ordering that affects a value - that exclusion is exactly what makes a
# re-run at a different wall clock append ZERO bytes.
_VALUE_COLUMNS: tuple[str, ...] = (
    "open", "high", "low", "close", "volume", "committed_by")

# Advisory single-writer lock. 120s is the heartbeat staleness an operator
# should read as "the writer died", NOT a licence for this module to steal
# the lock: a gate whose release condition is the thing it blocks has
# already caused four separate incidents in this repo (CLAUDE.md). Stale
# locks are cleared ONLY by `scripts/candle_store.py unlock --force`.
LOCK_STALE_S = 120


class CandleLaneError(ValueError):
    """A caller bug: an invalid symbol/interval/source/quote/status.

    Raised, not counted. A bad LANE is not a data UNKNOWN - there is no
    honest row to write for it, and silently dropping the batch would make
    a typo'd source look exactly like a venue outage."""


class CandleStoreUnreadable(RuntimeError):
    """The store's own bytes are damaged or newer than this code.

    An INSTRUMENT FAULT. Public queries convert it to the STORE_UNREADABLE
    reason and NEVER to NOT_COVERED: "0 findings" and "the scan is broken"
    are the same observation until separated."""


# --------------------------------------------------------------------------
# reasons
# --------------------------------------------------------------------------

# CLOSED, APPEND-ONLY, never renumbered, never re-meaned. Deliberately NOT
# registered in core/codes.py: hard invariant 6 governs DISPOSITIONS on the
# hash-chained audit trail and this store writes nothing to that trail,
# while core/codes.py is imported by every decision module - a family there
# would create an import-graph edge from governed code toward this store's
# vocabulary and blur exactly the SAFE boundary the grep guard enforces.
# The DISCIPLINE is adopted locally in full: closed set, never a bare
# string, pinned exhaustive AND reachable in both directions (P12).
REASONS = frozenset({
    "OK",
    "NOT_COVERED",               # we never looked. curable by fetching.
    "NO_BAR_IN_COVERED_WINDOW",  # we looked, the venue had nothing.
    "BEFORE_LEFT_EDGE",          # earlier than every window; backfillable.
    "BEYOND_RIGHT_EDGE",         # right-censored: the future has not happened.
    "FIELD_UNKNOWN",             # bar PRESENT, requested field is ''.
    "MISALIGNED_T0",
    "NONPOSITIVE_ANCHOR",
    "CONFLICTED",
    "QUOTE_MISMATCH",
    "SYMBOL_UNKNOWN",
    "INTERVAL_UNKNOWN",
    "STORE_UNREADABLE",          # INSTRUMENT FAULT. never a data UNKNOWN.
})

REJECT_REASONS = frozenset({
    "NON_INTEGRAL", "UNIT_RANGE", "MISALIGNED", "FORMING", "OUT_OF_WINDOW",
    "BAD_OHLC",
})

FIELDS = ("open", "high", "low", "close", "volume")

# THE ms/s SENTINEL. A 10-digit second value sits inside this band; a
# 13-digit millisecond value is > 4e9 and is refused with its own counter.
_TS_MIN_S = 10 ** 9
_TS_MAX_S = 4 * 10 ** 9


# --------------------------------------------------------------------------
# paths (functions, never module constants - see the leak-class note above)
# --------------------------------------------------------------------------

def store_root(root: Path | str | None = None) -> Path:
    """The store root. Explicit argument > LB_CANDLE_ROOT > outputs/candles.

    A FUNCTION on purpose: a module-level Path("outputs")/"candles" would
    be leak-class instance #11 unless registered in
    tests/conftest.py:_REDIRECTED_PATH_ATTRS. This has nothing to register
    and nothing to forget."""
    if root is not None:
        return Path(root)
    env = os.environ.get("LB_CANDLE_ROOT")
    if env:
        return Path(env)
    return Path("outputs") / "candles"


def journal_dir(root: Path | str | None = None) -> Path:
    return store_root(root) / "journal"


def coverage_dir(root: Path | str | None = None) -> Path:
    return store_root(root) / "coverage"


def parquet_dir(root: Path | str | None = None) -> Path:
    return store_root(root) / "parquet"


def manifest_path(root: Path | str | None = None) -> Path:
    return store_root(root) / "MANIFEST.json"


def compaction_state_path(root: Path | str | None = None) -> Path:
    return store_root(root) / ".compaction" / "state.json"


def lock_path(root: Path | str | None = None) -> Path:
    return store_root(root) / ".ingest.lock"


def bar_header(version: int = SCHEMA_VERSION) -> str:
    return ",".join(_BAR_COLUMNS_BY_VERSION[version]) + "\r\n"


def coverage_header(version: int = SCHEMA_VERSION) -> str:
    return ",".join(_COVERAGE_COLUMNS_BY_VERSION[version]) + "\r\n"


def segment_name(ingest_s: int, version: int = SCHEMA_VERSION) -> str:
    """{YYYY-MM}.v{N}.csv, the UTC month of INGEST time.

    Plain name sort is chronological by construction and v1 always precedes
    v2 within a month. Note the consequence, which the reader honours: a
    bar's segment is chosen by when it was INGESTED, not by its own
    t_open_s, so a duplicate lookup may never restrict itself to the
    segments whose names overlap the queried window."""
    stamp = datetime.fromtimestamp(int(ingest_s), tz=timezone.utc)
    return f"{stamp.year:04d}-{stamp.month:02d}.v{version}.csv"


# --------------------------------------------------------------------------
# rendering / parsing
# --------------------------------------------------------------------------

def render_price(value: float | None) -> str:
    """%.10g, or '' for UNKNOWN. Never 0, never NaN, never a placeholder."""
    if value is None:
        return ""
    return _PRICE_FORMAT % (value,)


def _parse_optional_float(text: str) -> float | None:
    if text == "":
        return None
    try:
        return float(text)
    except (TypeError, ValueError):
        raise CandleStoreUnreadable(f"unparsable numeric cell: {text!r}") from None


def _parse_int(text: str) -> int:
    try:
        return int(text)
    except (TypeError, ValueError):
        raise CandleStoreUnreadable(f"unparsable integer cell: {text!r}") from None


def _coerce_number(value: Any) -> float | None:
    """Strict numeric coercion for INGEST. Returns None when the value is
    absent/UNKNOWN; raises ValueError when it is present but not a finite
    number. Deliberately NOT core.sanitize.safe_float: that COERCES poison
    to 0.0, and a fabricated 0 is indistinguishable from a measured one."""
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        raise ValueError("bool is not a price")
    try:
        out = float(value)
    except (TypeError, ValueError):
        raise ValueError("not a number") from None
    if not math.isfinite(out):
        raise ValueError("not finite")
    return out


def _coerce_t_open(value: Any) -> int:
    """Bar-open timestamp -> int seconds, raising for the NON_INTEGRAL class.

    data/ccxt_feed.py is the one repo feed that emits FLOAT seconds
    (`ts/1000.0`); a float within 1e-9 of an integer is accepted and
    narrowed, anything else is a rejection with its own counter."""
    if isinstance(value, bool):
        raise ValueError("bool is not a timestamp")
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if math.isfinite(value) and abs(value - round(value)) <= 1e-9:
            return int(round(value))
        raise ValueError("non-integral float timestamp")
    raise ValueError("non-numeric timestamp")


def ohlc_is_consistent(open_: float | None, high: float, low: float,
                       close: float) -> bool:
    """The bar-validity predicate, IDENTICAL to core/sanitize.py's
    clean_candles: every value finite and strictly positive, and
    `high >= low`, `high >= max(open, close)`, `low <= min(open, close)`.
    A flat bar (h == l == o == c) is legal.

    core.sanitize is the SOURCE OF TRUTH for this rule. It is restated here
    because a bot_cache bar arrives from outputs/state.json and never
    passed through sanitize at all - and it is CORROBORATED against
    sanitize by a shared vector table (pin P18) rather than trusted to stay
    in sync. When `open` is UNKNOWN the close stands in for it, which is
    the only reading under which the sanitize predicate is well-defined for
    a three-field bar."""
    ref_open = close if open_ is None else open_
    values = (ref_open, high, low, close)
    if any((not math.isfinite(v)) or v <= 0 for v in values):
        return False
    return not (high < low or high < max(ref_open, close)
                or low > min(ref_open, close))


# --------------------------------------------------------------------------
# public value types
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Series:
    """The (source, quote) lane. REQUIRED on every query, NEVER defaulted.

    There is no "the price of ETH" in this store - there is kraken/USD and
    there is binanceus/USDT. Binance.US has no MINA at all and ARB/PAXG/
    FLOW are USDT-only there, so a default would silently reintroduce the
    quote confound: two disjoint populations pooled under one name, which
    is the exact shape of the era confound the repo already refuses."""
    source: str
    quote: str


@dataclass(frozen=True)
class Bar:
    """One committed bar covering [t_open_s, t_open_s + interval_s).

    `close` is the price as of t_open_s + interval_s. `open` and `volume`
    are None (UNKNOWN) on the bot_cache lane, which stores only t/c/h/l -
    they are never 0.0 and never invented."""
    symbol: str
    interval_s: int
    source: str
    quote: str
    t_open_s: int
    open: float | None
    high: float
    low: float
    close: float
    volume: float | None
    committed_by: str
    ingest_s: int


@dataclass(frozen=True)
class IngestReport:
    """Extend at the end only - a consumer may already read these keys."""
    symbol: str
    interval_s: int
    source: str
    quote: str
    status: str
    bars_offered: int
    bars_accepted: int
    bars_dup: int
    bars_conflict: int
    bars_rejected: int
    rejected_by_reason: dict[str, int] = field(default_factory=dict)
    win_from_s: int = 0
    win_to_s: int = -1
    written: bool = False
    note: str = ""

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


# --------------------------------------------------------------------------
# the advisory single-writer lock
# --------------------------------------------------------------------------

class _IngestLock:
    """O_EXCL create (atomic on NTFS), holding {pid, host, heartbeat_s}.

    Never waits forever and never proceeds anyway: a caller that cannot
    take it gets status="LOCKED" back. Never steals a stale lock either -
    see LOCK_STALE_S."""

    def __init__(self, root: Path | str | None = None) -> None:
        self.path = lock_path(root)
        self.held = False
        self.holder: dict[str, Any] | None = None

    def acquire(self) -> bool:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps({
            "pid": os.getpid(),
            "host": socket.gethostname(),
            "heartbeat_s": int(time.time()),
        }).encode("utf-8")
        try:
            with open(self.path, "xb") as f:
                f.write(payload)
                f.flush()
                os.fsync(f.fileno())
        except FileExistsError:
            self.holder = read_json(self.path) or {}
            return False
        except OSError:
            log.exception("candle store: cannot create ingest lock %s",
                          self.path)
            return False
        self.held = True
        return True

    def release(self) -> None:
        if not self.held:
            return
        try:
            self.path.unlink(missing_ok=True)
        except OSError:
            log.exception("candle store: cannot release ingest lock %s",
                          self.path)
        self.held = False

    def __enter__(self) -> "_IngestLock":
        self.acquire()
        return self

    def __exit__(self, *exc: object) -> None:
        self.release()


def lock_age_s(root: Path | str | None = None,
               now_s: float | None = None) -> float | None:
    """Seconds since the held lock's heartbeat, or None when unlocked.

    An operator reads this to decide whether the writer died; this module
    never acts on it."""
    rec = read_json(lock_path(root))
    if not isinstance(rec, dict):
        return None
    beat = rec.get("heartbeat_s")
    if not isinstance(beat, (int, float)):
        return None
    return (time.time() if now_s is None else now_s) - float(beat)


# --------------------------------------------------------------------------
# segment reading (never creates anything)
# --------------------------------------------------------------------------

_SEGMENT_RE = re.compile(r"^(\d{4})-(\d{2})\.v(\d+)\.csv$")


def _segments(directory: Path) -> list[tuple[Path, int]]:
    """(path, schema_version) for every segment, in name order.

    Name order is chronological by construction and v1 precedes v2 within a
    month. A file in the directory that is not a segment is an instrument
    fault, not a data gap."""
    if not directory.is_dir():
        return []
    out: list[tuple[Path, int]] = []
    for p in sorted(directory.glob("*.csv")):
        m = _SEGMENT_RE.match(p.name)
        if m is None:
            raise CandleStoreUnreadable(f"unrecognised segment name: {p.name}")
        version = int(m.group(3))
        if version > SCHEMA_VERSION:
            raise CandleStoreUnreadable(
                f"{p.name} is schema v{version}; this code reads up to "
                f"v{SCHEMA_VERSION}. Upgrade the reader - do NOT downgrade "
                f"the file.")
        out.append((p, version))
    return out


def _read_segment(path: Path, version: int,
                  columns_by_version: Mapping[int, tuple[str, ...]],
                  ) -> list[dict[str, str]]:
    """Rows of ONE segment, read under ITS OWN header.

    Refuses rather than guesses. A garbage header, an unknown column, or a
    row whose field count differs from the header (which is what a
    kill-torn record isolated by durable_append looks like) raises
    CandleStoreUnreadable. That is deliberate: a damaged store must be
    loud, because the alternative - skipping the row - reports an
    instrument fault as a data hole, which is the one failure this store
    exists to make impossible. `scripts/candle_store.py verify` names the
    segment and line; resolution is by hand."""
    expected = columns_by_version.get(version)
    if expected is None:
        raise CandleStoreUnreadable(f"no column set for schema v{version}")
    try:
        with open(path, encoding="utf-8", newline="") as f:
            rows = list(csv.reader(f))
    except OSError as exc:
        raise CandleStoreUnreadable(f"cannot read {path.name}: {exc}") from exc
    except UnicodeDecodeError as exc:
        raise CandleStoreUnreadable(f"{path.name} is not UTF-8") from exc
    rows = [r for r in rows if r != []]
    if not rows:
        return []
    header = tuple(rows[0])
    if header != expected:
        raise CandleStoreUnreadable(
            f"{path.name} header is not the v{version} schema: {header!r}")
    out: list[dict[str, str]] = []
    for lineno, raw in enumerate(rows[1:], start=2):
        if len(raw) != len(expected):
            raise CandleStoreUnreadable(
                f"{path.name}:{lineno} has {len(raw)} fields, expected "
                f"{len(expected)} (a torn or hand-edited record)")
        out.append(dict(zip(expected, raw, strict=True)))
    return out


def _iter_bar_rows(root: Path | str | None) -> Iterable[dict[str, str]]:
    for path, version in _segments(journal_dir(root)):
        yield from _read_segment(path, version, _BAR_COLUMNS_BY_VERSION)


def _iter_coverage_rows(root: Path | str | None) -> Iterable[dict[str, str]]:
    for path, version in _segments(coverage_dir(root)):
        yield from _read_segment(path, version, _COVERAGE_COLUMNS_BY_VERSION)


# --------------------------------------------------------------------------
# the parsed lane (one pass; CandleView holds it)
# --------------------------------------------------------------------------

def merge_windows(windows: Sequence[tuple[int, int]],
                  interval_s: int) -> list[tuple[int, int]]:
    """Merged disjoint inclusive bar-open windows.

    SENTINEL ROWS (win_to < win_from) ARE DROPPED BEFORE MERGING - that is
    what stops a failed fetch from widening coverage. Two windows fuse iff
    `a2 <= b1 + interval_s`, i.e. bar-ADJACENT windows join but a genuine
    one-bar hole does not."""
    real = sorted((a, b) for a, b in windows if b >= a)
    out: list[tuple[int, int]] = []
    for a, b in real:
        if out and a <= out[-1][1] + interval_s:
            if b > out[-1][1]:
                out[-1] = (out[-1][0], b)
        else:
            out.append((a, b))
    return out


def _covered(windows: Sequence[tuple[int, int]], t: int) -> bool:
    lo, hi = 0, len(windows) - 1
    while lo <= hi:
        mid = (lo + hi) // 2
        a, b = windows[mid]
        if t < a:
            hi = mid - 1
        elif t > b:
            lo = mid + 1
        else:
            return True
    return False


class CandleView:
    """ONE parse of a (symbol, interval_s, source, quote) lane.

    THE CALL A HORIZON SWEEP ACTUALLY USES. The module-level convenience
    functions below re-parse the whole store on every call; at thousands of
    anchors x several horizons that is the difference between sub-second
    and minutes. Build one view and carry it.

    A view is a SNAPSHOT. `read_at_s` stamps when it was taken; values are
    as-of, never "current". Constructing one creates nothing on disk."""

    def __init__(self, symbol: str, interval_s: int, series: Series,
                 root: Path | str | None = None) -> None:
        self.symbol = symbol
        self.interval_s = interval_s
        self.series = series
        self.read_at_s = time.time()
        self.unreadable: str = ""
        self._bars: dict[int, Bar] = {}
        self._conflicts: set[int] = set()
        self._windows: list[tuple[int, int]] = []
        self._committed_by_mix: dict[str, int] = {}
        self.symbol_known = False
        self.interval_known = False
        self.lane_known = False
        self.left_edge_s: int | None = None
        self.right_edge_s: int | None = None
        try:
            self._load(root)
        except CandleStoreUnreadable as exc:
            self.unreadable = str(exc)

    # -- loading ----------------------------------------------------------
    def _load(self, root: Path | str | None) -> None:
        sym, iv = self.symbol, self.interval_s
        src, qte = self.series.source, self.series.quote
        conflicted: set[int] = set()
        for row in _iter_bar_rows(root):
            if row["symbol"] != sym:
                continue
            self.symbol_known = True
            if _parse_int(row["interval_s"]) != iv:
                continue
            self.interval_known = True
            if row["source"] != src or row["quote"] != qte:
                continue
            self.lane_known = True
            kind = row["record_kind"]
            t_open = _parse_int(row["t_open_s"])
            if kind == "CONFLICT":
                conflicted.add(t_open)
                continue
            if kind != "BAR":
                raise CandleStoreUnreadable(f"unknown record_kind {kind!r}")
            if t_open in self._bars:
                # FIRST-COMMITTED WINS. A later BAR row for a key that
                # already holds one can only exist in a hand-edited or
                # concurrently-written journal; the first is authoritative.
                continue
            high = _parse_optional_float(row["high"])
            low = _parse_optional_float(row["low"])
            close = _parse_optional_float(row["close"])
            if high is None or low is None or close is None:
                raise CandleStoreUnreadable(
                    f"BAR row at t_open_s={t_open} has an UNKNOWN required "
                    f"field (high/low/close)")
            cb = row["committed_by"]
            self._committed_by_mix[cb] = self._committed_by_mix.get(cb, 0) + 1
            self._bars[t_open] = Bar(
                symbol=sym, interval_s=iv, source=src, quote=qte,
                t_open_s=t_open,
                open=_parse_optional_float(row["open"]),
                high=high, low=low, close=close,
                volume=_parse_optional_float(row["volume"]),
                committed_by=cb, ingest_s=_parse_int(row["ingest_s"]),
            )
        self._conflicts = conflicted

        raw_windows: list[tuple[int, int]] = []
        for row in _iter_coverage_rows(root):
            if row["symbol"] != sym:
                continue
            self.symbol_known = True
            if _parse_int(row["interval_s"]) != iv:
                continue
            self.interval_known = True
            if row["source"] != src or row["quote"] != qte:
                continue
            self.lane_known = True
            raw_windows.append((_parse_int(row["win_from_s"]),
                                _parse_int(row["win_to_s"])))
        self._windows = merge_windows(raw_windows, iv)
        if self._windows:
            self.left_edge_s = self._windows[0][0]
            self.right_edge_s = self._windows[-1][1]

    # -- lane identity ----------------------------------------------------
    def _lane_reason(self) -> str:
        if self.unreadable:
            return "STORE_UNREADABLE"
        if not self.symbol_known:
            return "SYMBOL_UNKNOWN"
        if not self.interval_known:
            return "INTERVAL_UNKNOWN"
        if not self.lane_known:
            # The (source, quote) series is absent for a symbol/interval the
            # store DOES hold. Named QUOTE_MISMATCH because the quote is the
            # confound this refusal exists to prevent; it covers a missing
            # source identically.
            return "QUOTE_MISMATCH"
        return ""

    # -- queries ----------------------------------------------------------
    def coverage_of(self, t_open_s: int) -> str:
        """The reason a bar-open slot carries, WITHOUT reading its value."""
        lane = self._lane_reason()
        if lane:
            return lane
        if t_open_s in self._conflicts:
            return "CONFLICTED"
        if not self._covered_at(t_open_s):
            if self.left_edge_s is not None and t_open_s < self.left_edge_s:
                return "BEFORE_LEFT_EDGE"
            if self.right_edge_s is not None and t_open_s > self.right_edge_s:
                return "BEYOND_RIGHT_EDGE"
            return "NOT_COVERED"
        if t_open_s not in self._bars:
            return "NO_BAR_IN_COVERED_WINDOW"
        return "OK"

    def _covered_at(self, t_open_s: int) -> bool:
        return _covered(self._windows, t_open_s)

    def bars(self, t0_s: int, t1_s: int) -> list[Bar]:
        """Bars with INCLUSIVE bar-open bounds, ascending.

        YIELDS NOTHING FOR A GAP - never a placeholder, never NaN. This call
        ALONE cannot tell you whether an absence is a hole or a
        never-looked window: pair it with coverage()."""
        if self.unreadable:
            return []
        return [self._bars[t] for t in sorted(self._bars)
                if t0_s <= t <= t1_s]

    def price_at(self, ts_s: int, field_name: str = "close",
                 ) -> tuple[float | None, str, dict[str, Any]]:
        """Resolve by FLOOR onto the bar grid. No nearest-neighbour, no
        forward-fill, no tolerance.

        The third element stamps {t_open_s, source, quote, committed_by,
        offset_s} so a caller can CORRECT for up to one interval of error
        rather than silently absorb it. `offset_s` is ts_s - t_open_s.

        A PRESENT bar whose requested field is UNKNOWN returns
        (None, "FIELD_UNKNOWN", stamp) - never 0.0, and never conflated
        with an absent bar."""
        if field_name not in FIELDS:
            raise CandleLaneError(
                f"field must be one of {FIELDS}, got {field_name!r}")
        t_open = ts_s - (ts_s % self.interval_s)
        stamp: dict[str, Any] = {
            "t_open_s": t_open, "source": self.series.source,
            "quote": self.series.quote, "committed_by": "",
            "offset_s": ts_s - t_open,
        }
        reason = self.coverage_of(t_open)
        if reason != "OK" and reason != "CONFLICTED":
            return None, reason, stamp
        bar = self._bars.get(t_open)
        if bar is None:
            # A conflicted key with no surviving BAR record: the store saw
            # only disagreement. Report the conflict, never a value.
            return None, "CONFLICTED", stamp
        stamp["committed_by"] = bar.committed_by
        value = getattr(bar, field_name)
        if value is None:
            return None, "FIELD_UNKNOWN", stamp
        return float(value), reason, stamp

    def forward_return(self, t0_s: int, horizon_s: int,
                       side: str = "long") -> tuple[float | None, str]:
        """Percent forward return from the bar AT t0_s to the bar at
        t0_s + horizon_s, or (None, reason).

        Computed EXACTLY as ml.corpus.gross_ret_pct does it:
        `(exit - entry) / entry * 100.0`, negated for side == "short",
        None when entry <= 0.

        EXACT-BAR ONLY. `t0_s % interval_s != 0` returns
        (None, "MISALIGNED_T0") and is NEVER re-anchored - a study that
        wants slack implements it, names it, and owns the error.

        REASON PREFIXING. "OK" only when BOTH endpoints resolve; otherwise
        the failing endpoint's reason prefixed `anchor_` or `forward_`, so
        "no anchor" and "no future" never pool. That distinction is
        load-bearing: right-censoring is missing-not-at-random on the
        TRAILING edge, a hole is missing-not-at-random on the THIN ALTS.

        A CONFLICTED endpoint yields no number. The value exists and
        price_at() will show it, but a bar the venue has contradicted is
        not one a statistic may quietly consume."""
        if side not in ("long", "short"):
            raise CandleLaneError(f"side must be long|short, got {side!r}")
        if self.interval_s <= 0 or t0_s % self.interval_s != 0:
            return None, "MISALIGNED_T0"
        entry, r_a, _ = self.price_at(t0_s)
        if r_a != "OK" or entry is None:
            return None, f"anchor_{r_a}"
        if entry <= 0.0:
            # Structurally unreachable through this module's write path
            # (BAD_OHLC refuses a non-positive close). The guard stands
            # because outputs/signal_history.csv proves an UNKNOWN-as-zero
            # encoding can reach a reader, and dividing by it would produce
            # a silent +-inf instead of an honest UNKNOWN.
            return None, "anchor_NONPOSITIVE_ANCHOR"
        exit_, r_b, _ = self.price_at(t0_s + horizon_s)
        if r_b != "OK" or exit_ is None:
            return None, f"forward_{r_b}"
        raw = (exit_ - entry) / entry * 100.0
        return (-raw if side == "short" else raw), "OK"

    def forward_returns_batch(self, anchors: Sequence[int], horizon_s: int,
                              side: str = "long",
                              ) -> list[tuple[float | None, str]]:
        """N anchors against ONE parsed view, same reason vocabulary."""
        return [self.forward_return(t, horizon_s, side) for t in anchors]

    def coverage(self, t0_s: int, t1_s: int) -> dict[str, Any]:
        """THE MANDATORY COMPANION TO EVERY STATISTIC.

        `expected_bars` and `present_bars` travel TOGETHER so no horizon
        number can be quoted without its denominator, and
        `holes_in_covered` is the source of a study's exclusion accounting
        rather than a silently dropped row. `read_at_s` is the snapshot
        stamp: values are as-of."""
        iv = self.interval_s
        first = t0_s + ((-t0_s) % iv)
        last = t1_s - (t1_s % iv)
        slots = list(range(first, last + 1, iv)) if last >= first else []
        covered = [t for t in slots if self._covered_at(t)]
        present = [t for t in covered if t in self._bars]
        holes = [t for t in covered if t not in self._bars]
        uncovered = [t for t in slots if not self._covered_at(t)]
        return {
            "symbol": self.symbol,
            "interval_s": iv,
            "source": self.series.source,
            "quote": self.series.quote,
            "t0_s": t0_s,
            "t1_s": t1_s,
            "expected_bars": len(slots),
            "covered_bars": len(covered),
            "present_bars": len(present),
            "missing_in_covered": len(holes),
            "uncovered_bars": len(uncovered),
            "covered_windows": list(self._windows),
            "holes_in_covered": _runs(holes, iv),
            "uncovered_windows": _runs(uncovered, iv),
            "left_edge_s": self.left_edge_s,
            "right_edge_s": self.right_edge_s,
            "committed_by_mix": dict(self._committed_by_mix),
            "conflicts": len(self._conflicts),
            "read_at_s": self.read_at_s,
            "store_schema_version": SCHEMA_VERSION,
            "unreadable": self.unreadable,
        }


def _runs(slots: Sequence[int], interval_s: int) -> list[tuple[int, int]]:
    """Consecutive bar-open slots collapsed into inclusive [from, to] runs."""
    out: list[tuple[int, int]] = []
    for t in slots:
        if out and t == out[-1][1] + interval_s:
            out[-1] = (out[-1][0], t)
        else:
            out.append((t, t))
    return out


# --------------------------------------------------------------------------
# module-level convenience API (each re-parses the store - see load_view)
# --------------------------------------------------------------------------

def load_view(symbol: str, interval_s: int, *, series: Series,
              root: Path | str | None = None) -> CandleView:
    """One parse of one lane. Use this for anything that queries in a loop."""
    return CandleView(symbol, interval_s, series, root=root)


def bars(symbol: str, interval_s: int, t0_s: int, t1_s: int, *,
         series: Series, root: Path | str | None = None) -> list[Bar]:
    """Bars in [t0_s, t1_s] inclusive by bar-open, ascending.

    CALLING THIS IN A LOOP RE-PARSES THE STORE; use load_view(). Yields
    nothing for a gap - pair with coverage() to tell a hole from a
    never-looked window."""
    return load_view(symbol, interval_s, series=series, root=root).bars(
        t0_s, t1_s)


def price_at(symbol: str, ts_s: int, *, interval_s: int, series: Series,
             field: str = "close", root: Path | str | None = None,
             ) -> tuple[float | None, str, dict[str, Any]]:
    """Floor-resolved price with a provenance stamp.

    CALLING THIS IN A LOOP RE-PARSES THE STORE; use load_view()."""
    return load_view(symbol, interval_s, series=series, root=root).price_at(
        ts_s, field)


def forward_return(symbol: str, t0_s: int, horizon_s: int, *,
                   interval_s: int, series: Series, side: str = "long",
                   root: Path | str | None = None,
                   ) -> tuple[float | None, str]:
    """THE CONSUMER'S PRIMARY CALL. See CandleView.forward_return.

    CALLING THIS IN A LOOP RE-PARSES THE STORE; use load_view()."""
    return load_view(symbol, interval_s, series=series,
                     root=root).forward_return(t0_s, horizon_s, side)


def forward_returns_batch(anchors: Sequence[tuple[str, int]], horizon_s: int,
                          *, interval_s: int, series: Series,
                          side: str = "long",
                          root: Path | str | None = None,
                          ) -> list[tuple[float | None, str]]:
    """(symbol, t0_s) anchors -> returns, one parsed view PER SYMBOL."""
    views: dict[str, CandleView] = {}
    out: list[tuple[float | None, str]] = []
    for symbol, t0_s in anchors:
        view = views.get(symbol)
        if view is None:
            view = views[symbol] = load_view(symbol, interval_s,
                                             series=series, root=root)
        out.append(view.forward_return(t0_s, horizon_s, side))
    return out


def coverage(symbol: str, interval_s: int, t0_s: int, t1_s: int, *,
             series: Series, root: Path | str | None = None,
             ) -> dict[str, Any]:
    """THE EXPENSIVE CALL - one parse. Call once per study and carry it."""
    return load_view(symbol, interval_s, series=series, root=root).coverage(
        t0_s, t1_s)


def covered_windows(symbol: str, interval_s: int, *, series: Series,
                    root: Path | str | None = None) -> list[tuple[int, int]]:
    """The merged disjoint coverage windows for one lane. Pure stdlib;
    answers with polars absent."""
    return list(load_view(symbol, interval_s, series=series,
                          root=root)._windows)


def lanes(symbol: str | None = None, root: Path | str | None = None,
          ) -> list[dict[str, Any]]:
    """What the store actually HOLDS - the prior-art / what-do-I-have call.

    Reads MANIFEST.json when a compaction has published one, and otherwise
    derives the same shape from the journal. Makes the USD/USDT and
    kraken/bot_cache splits visible rather than implicit."""
    manifest = read_json(manifest_path(root))
    rows: list[dict[str, Any]]
    if isinstance(manifest, dict) and isinstance(manifest.get("lanes"), list):
        rows = [r for r in manifest["lanes"] if isinstance(r, dict)]
    else:
        acc: dict[tuple[str, int, str, str], dict[str, Any]] = {}
        for row in _iter_bar_rows(root):
            if row["record_kind"] != "BAR":
                key_c = (row["symbol"], _parse_int(row["interval_s"]),
                         row["source"], row["quote"])
                if key_c in acc:
                    acc[key_c]["conflicts"] += 1
                continue
            key = (row["symbol"], _parse_int(row["interval_s"]),
                   row["source"], row["quote"])
            t = _parse_int(row["t_open_s"])
            entry = acc.get(key)
            if entry is None:
                entry = acc[key] = {
                    "symbol": key[0], "interval_s": key[1], "source": key[2],
                    "quote": key[3], "rows": 0, "t_min_s": t, "t_max_s": t,
                    "committed_by_mix": {}, "conflicts": 0,
                }
            entry["rows"] += 1
            entry["t_min_s"] = min(entry["t_min_s"], t)
            entry["t_max_s"] = max(entry["t_max_s"], t)
            mix = entry["committed_by_mix"]
            cb = row["committed_by"]
            mix[cb] = mix.get(cb, 0) + 1
        rows = list(acc.values())
    if symbol is not None:
        rows = [r for r in rows if r.get("symbol") == symbol]
    return sorted(rows, key=lambda r: (str(r.get("symbol")),
                                       int(r.get("interval_s", 0)),
                                       str(r.get("source")),
                                       str(r.get("quote"))))


def content_digest(root: Path | str | None = None) -> str:
    """sha256 over the canonical sorted row tuples: bars, then coverage.

    THE REPRODUCIBILITY CONTRACT, and it is ORDER-INDEPENDENT on purpose.
    A file sha256 is DIAGNOSTIC ONLY and is never the contract: CSV byte
    order is arrival-dependent (backfilling A-then-B differs from
    B-then-A in bytes for the identical row set) and parquet bytes are
    toolchain-dependent (the same rows under zstd L3, zstd L9 and snappy
    produce three different shas). NEVER claim cross-toolchain or
    cross-order byte identity.

    The claim that IS true, and is pinned: re-running the same ingest over
    the same store appends ZERO bytes."""
    h = hashlib.sha256()
    bar_rows = sorted(
        tuple(r[c] for c in BAR_COLUMNS if c != "ingest_s")
        for r in _iter_bar_rows(root))
    for row in bar_rows:
        h.update(("\x1f".join(row) + "\x1e").encode("utf-8"))
    h.update(b"\x1d")
    cov_rows = sorted(
        tuple(r[c] for c in COVERAGE_COLUMNS if c != "observed_at_s")
        for r in _iter_coverage_rows(root))
    for row in cov_rows:
        h.update(("\x1f".join(row) + "\x1e").encode("utf-8"))
    return h.hexdigest()


def canonical_bar_rows(root: Path | str | None = None,
                       ) -> list[dict[str, Any]]:
    """Every stored BAR, deduplicated and in THE CANONICAL ORDER.

    This is the compaction contract, and it lives here rather than in the
    polars lane so exactly one implementation owns the semantics:

     1. Segments are read in NAME order (chronological by construction, and
        v1 precedes v2 within a month), and each row gets `_ord`, its
        global ordinal computed from the journal BYTES. Dedup is therefore
        a pure function of file content, independent of any library's
        internal ordering.
     2. record_kind == "CONFLICT" rows are dropped from value selection and
        counted separately - a venue's disagreement is preserved on disk
        and visible to a query, but it never becomes the value.
     3. FIRST-COMMITTED WINS: the lowest `_ord` row for each
        (symbol, interval_s, source, quote, t_open_s) survives.
     4. The survivors are sorted by
        (symbol, interval_s, t_open_s, source, quote). THIS STEP IS
        LOAD-BEARING, not cosmetic: without it the output order is arrival
        order, so the identical row set backfilled A-then-B and B-then-A
        produces different bytes and the store stops being reproducible.
        Pin P19 removes this sort and watches the digest diverge.

    The projection onto the current schema is PURE `row.get(col, "")`. A
    value already present passes through UNCHANGED and is NEVER recomputed
    from other columns - the repo bought that rule the hard way when one
    non-idempotent migration column re-tagged thousands of corpus rows over
    two passes and promoted a model family on a data bug."""
    ordered: list[tuple[int, dict[str, Any]]] = []
    ordinal = 0
    for path, version in _segments(journal_dir(root)):
        for row in _read_segment(path, version, _BAR_COLUMNS_BY_VERSION):
            ordered.append((ordinal, row))
            ordinal += 1
    best: dict[tuple[str, int, str, str, int], tuple[int, dict[str, Any]]] = {}
    for ordinal, row in ordered:
        if row.get("record_kind") != "BAR":
            continue
        key = (row["symbol"], _parse_int(row["interval_s"]), row["source"],
               row["quote"], _parse_int(row["t_open_s"]))
        if key not in best:
            best[key] = (ordinal, row)
    out = [{col: row.get(col, "") for col in BAR_COLUMNS}
           for _, row in best.values()]
    out.sort(key=lambda r: (str(r["symbol"]), int(r["interval_s"]),
                            int(r["t_open_s"]), str(r["source"]),
                            str(r["quote"])))
    return out


def canonical_digest(root: Path | str | None = None) -> str:
    """sha256 over canonical_bar_rows IN WRITTEN ORDER, ingest_s excluded.

    ORDER-SENSITIVE on purpose - it is the check that the canonical sort
    actually ran, which is what makes two stores holding the identical rows
    compact to identical content. The parquet FILE sha is diagnostic only:
    the same rows under zstd L3, zstd L9 and snappy produce three different
    file shas, so byte identity is a property of an identical toolchain,
    never of identical content."""
    h = hashlib.sha256()
    for row in canonical_bar_rows(root):
        h.update(("\x1f".join(str(row[c]) for c in BAR_COLUMNS
                              if c != "ingest_s") + "\x1e").encode("utf-8"))
    return h.hexdigest()


# --------------------------------------------------------------------------
# the write path
# --------------------------------------------------------------------------

def _validate_lane(symbol: str, interval_s: Any, source: str, quote: str,
                   committed_by: str, status: str) -> int:
    """STEP 1. Runs BEFORE any grid arithmetic, on purpose (pin P4).

    An unvalidated interval_s of 0 reaching a modulo is a ZeroDivisionError
    here and - in a SQL layer - a SILENTLY DISABLED grid check, which is
    the same shape as core.sanitize.interval_str_to_sec returning 0.0 and
    thereby making drop_forming_candles a no-op."""
    if not isinstance(symbol, str) or _SYMBOL_RE.match(symbol) is None:
        raise CandleLaneError(
            f"symbol must match {_SYMBOL_RE.pattern} (uppercase alnum, "
            f"<=16 chars): {symbol!r}. This is a security control - the "
            f"symbol becomes a filename.")
    if isinstance(interval_s, bool) or not isinstance(interval_s, int):
        raise CandleLaneError(
            f"interval_s must be an int number of SECONDS from {INTERVALS}, "
            f"never a venue interval string: {interval_s!r}")
    if interval_s not in INTERVALS:
        raise CandleLaneError(
            f"interval_s must be one of {INTERVALS}: {interval_s!r}")
    if source not in SOURCES:
        raise CandleLaneError(f"source must be one of {sorted(SOURCES)}: "
                              f"{source!r}")
    if quote not in QUOTES:
        raise CandleLaneError(f"quote must be one of {sorted(QUOTES)}: "
                              f"{quote!r}")
    if committed_by not in COMMITTED_BY:
        raise CandleLaneError(
            f"committed_by must be one of {sorted(COMMITTED_BY)}: "
            f"{committed_by!r}")
    if status not in STATUSES:
        raise CandleLaneError(f"status must be one of {sorted(STATUSES)}: "
                              f"{status!r}")
    return interval_s


def _window_index(root: Path | str | None, symbol: str, interval_s: int,
                  source: str, quote: str, t_lo: int, t_hi: int,
                  ) -> tuple[dict[int, tuple[str, ...]], set[int]]:
    """Existing values for JUST the ingested window: t_open_s -> value tuple.

    Memory is O(window), not O(store). The I/O is NOT restricted to the
    segments whose names overlap the window and must never be: a segment is
    named for the month of INGEST, so a July bar backfilled in August lives
    in the August segment. Restricting by name would miss the duplicate and
    append it again, which is how a re-run stops being a no-op."""
    values: dict[int, tuple[str, ...]] = {}
    conflicts: set[int] = set()
    for row in _iter_bar_rows(root):
        if (row["symbol"] != symbol or row["source"] != source
                or row["quote"] != quote):
            continue
        if _parse_int(row["interval_s"]) != interval_s:
            continue
        t = _parse_int(row["t_open_s"])
        if t < t_lo or t > t_hi:
            continue
        if row["record_kind"] == "CONFLICT":
            conflicts.add(t)
            continue
        values.setdefault(t, tuple(row[c] for c in _VALUE_COLUMNS))
    return values, conflicts


def _existing_windows(root: Path | str | None, symbol: str, interval_s: int,
                      source: str, quote: str) -> list[tuple[int, int]]:
    """The lane's already-merged coverage windows, for the write path's
    "does this observation add anything?" test."""
    raw: list[tuple[int, int]] = []
    for row in _iter_coverage_rows(root):
        if (row["symbol"] != symbol or row["source"] != source
                or row["quote"] != quote):
            continue
        if _parse_int(row["interval_s"]) != interval_s:
            continue
        raw.append((_parse_int(row["win_from_s"]),
                    _parse_int(row["win_to_s"])))
    return merge_windows(raw, interval_s)


def _align_up(t: int, interval_s: int) -> int:
    return t + ((-t) % interval_s)


def _align_down(t: int, interval_s: int) -> int:
    return t - (t % interval_s)


def ingest(symbol: str, interval_s: int, source: str, quote: str,
           bars: Sequence[Mapping[str, Any]], *,
           committed_upto_s: int, committed_by: str,
           asked_from_s: int | None, asked_to_s: int | None,
           status: str = "OK", now_s: int | None = None,
           note: str = "",
           root: Path | str | None = None) -> IngestReport:
    """THE ONLY WRITE ENTRY POINT.

    The store never talks to a venue: the caller owns fetching, the ms->s
    conversion, and deriving `committed_upto_s`. `bars` are mappings with
    a `time` (or `t_open_s`) in UNIX SECONDS plus high/low/close, and
    optional open/volume (absent or None means UNKNOWN, which is stored as
    '' and NEVER as 0).

    ORDER OF OPERATIONS IS LOAD-BEARING AND FIXED:
      1. LANE VALIDATION (raises CandleLaneError) - before any modulo.
      2. status != "OK" writes ONE coverage row bearing the EMPTY-WINDOW
         SENTINEL (win_to_s = win_from_s - interval_s, which the union
         algebra skips) and returns. A FAILED FETCH MUST NEVER WIDEN
         COVERAGE - this is the highest-consequence rule in the module, and
         it exists because data/_http.py:_get_json returns None on BOTH
         transport failure and hostile-body rejection while every
         get_candles turns that None into [].
      3. PER-BAR VALIDATION of the whole batch before any write. Each
         rejection gets its own counter.
      4/5. Window index, then per-key resolution: absent -> BAR appended;
         present and EQUAL (rendered text, ingest_s excluded) -> NOTHING
         written, bars_dup++; present and DIFFERENT -> a CONFLICT record is
         appended and THE QUERYABLE VALUE STAYS THE FIRST ONE.
         FIRST-COMMITTED WINS, never last-wins: last-wins lets a late
         forming-bar leak silently overwrite good history, the data is not
         re-acquirable (Kraken serves 720 committed bars and `since` does
         not page backward), and a venue revision is a FACT ABOUT THE
         VENUE that analysis must be able to see.
      6. THE TWO WRITES, BARS FIRST THEN COVERAGE, NEVER REVERSED. A crash
         between them leaves bars on disk that read NOT_COVERED -
         UNDER-claiming, benign, self-healing. The reverse order would
         claim coverage over bars that were never written, so a real hole
         reports as NO_BAR_IN_COVERED_WINDOW - "we looked and the venue had
         nothing" when the write simply died. A confident lie with no
         external symptom. Pin P1 mutates the order and watches the reason
         flip.

    BATCH ACCUMULATION RULE: a backfill MUST accumulate every page for one
    (symbol, interval_s, source, quote) run and call this ONCE. Per-page
    ingest is quadratic - data/okx_feed.py pages backward in 100-row chunks
    and nothing in the type system stops a maintainer from calling this per
    page. Do not.

    IDEMPOTENCE IS LITERAL, NOT APPROXIMATE. A coverage row is appended
    only when the observation CHANGES the store (new or conflicting bars,
    or a window not already covered), so re-running the same successful
    ingest appends ZERO BYTES to both files. status != "OK" rows are never
    suppressed - a failed fetch is a real event and the ledger is the
    fetch-health series.

    Returns an IngestReport. `written=False` means an append failed:
    core.runtime.durable_append returns False and never raises, and that is
    propagated rather than turned into an exception (CLAUDE.md invariant 5
    - losing a log row must never unwind the action it records).

    Raises CandleLaneError for an invalid lane (a caller bug, not a data
    UNKNOWN) and CandleStoreUnreadable when the journal's own bytes are
    damaged - the store refuses to append into a store it cannot read,
    rather than silently starting a second, divergent history."""
    interval_s = _validate_lane(symbol, interval_s, source, quote,
                                committed_by, status)
    if note not in NOTES:
        raise CandleLaneError(f"note must be one of {sorted(NOTES)}: {note!r}")
    now = int(time.time()) if now_s is None else int(now_s)
    committed_upto_s = int(committed_upto_s)

    lock = _IngestLock(root)
    if not lock.acquire():
        holder = lock.holder or {}
        log.warning("candle store: ingest lock held by pid=%s host=%s - "
                    "refusing to proceed", holder.get("pid"),
                    holder.get("host"))
        return IngestReport(symbol, interval_s, source, quote, "LOCKED",
                            len(bars), 0, 0, 0, 0, {}, 0, -1, False,
                            "")
    try:
        return _ingest_locked(symbol, interval_s, source, quote, bars,
                              committed_upto_s, committed_by, asked_from_s,
                              asked_to_s, status, now, note, root)
    finally:
        lock.release()


def _coverage_row(symbol: str, interval_s: int, source: str, quote: str,
                  win_from_s: int, win_to_s: int, committed_upto_s: int,
                  committed_by: str, offered: int, accepted: int, dup: int,
                  conflict: int, rejected: int, status: str, note: str,
                  now: int) -> list[Any]:
    return [SCHEMA_VERSION, symbol, interval_s, source, quote, win_from_s,
            win_to_s, committed_upto_s, committed_by, offered, accepted,
            dup, conflict, rejected, status, note, now]


def _ingest_locked(symbol: str, interval_s: int, source: str, quote: str,
                   bars: Sequence[Mapping[str, Any]], committed_upto_s: int,
                   committed_by: str, asked_from_s: int | None,
                   asked_to_s: int | None, status: str, now: int, note: str,
                   root: Path | str | None) -> IngestReport:
    cov_path = coverage_dir(root) / segment_name(now)
    offered = len(bars)

    # --- STEP 2: a failed / empty fetch claims NOTHING --------------------
    if status != "OK":
        anchor = _align_up(asked_from_s if asked_from_s is not None
                           else committed_upto_s, interval_s)
        row = _coverage_row(symbol, interval_s, source, quote, anchor,
                            anchor - interval_s, committed_upto_s,
                            committed_by, offered, 0, 0, 0, 0, status,
                            note, now)
        ok = durable_append(cov_path, lambda f: csv.writer(f).writerow(row),
                            header=coverage_header())
        return IngestReport(symbol, interval_s, source, quote, status,
                            offered, 0, 0, 0, 0, {}, anchor,
                            anchor - interval_s, ok, note)

    # --- STEP 3: validate the WHOLE batch before any write ----------------
    rejected_by_reason: dict[str, int] = {}

    def _reject(reason: str) -> None:
        rejected_by_reason[reason] = rejected_by_reason.get(reason, 0) + 1

    valid: list[tuple[int, tuple[str, ...]]] = []
    for raw in bars:
        source_t = raw.get("t_open_s", raw.get("time"))
        try:
            t_open = _coerce_t_open(source_t)
        except ValueError:
            _reject("NON_INTEGRAL")
            continue
        if not (_TS_MIN_S < t_open < _TS_MAX_S):
            # THE ms/s SENTINEL, with its own counter. A 13-digit
            # millisecond value lands here loudly instead of shedding every
            # bar as "future-dated" and reading as a dead endpoint.
            _reject("UNIT_RANGE")
            continue
        if t_open <= 0 or t_open % interval_s != 0:
            _reject("MISALIGNED")
            continue
        if t_open > committed_upto_s:
            # INCLUSIVE-COMMITTED: the bar AT committed_upto_s is ACCEPTED,
            # matching core.sanitize.drop_forming_candles and
            # tests/test_candle_integrity.py. Do not re-derive with `<`.
            _reject("FORMING")
            continue
        if asked_from_s is not None and asked_to_s is not None and not (
                asked_from_s <= t_open <= asked_to_s):
            _reject("OUT_OF_WINDOW")
            continue
        try:
            o = _coerce_number(raw.get("open"))
            h = _coerce_number(raw.get("high"))
            lo = _coerce_number(raw.get("low"))
            cl = _coerce_number(raw.get("close"))
            v = _coerce_number(raw.get("volume"))
        except ValueError:
            _reject("BAD_OHLC")
            continue
        if h is None or lo is None or cl is None:
            _reject("BAD_OHLC")
            continue
        if v is not None and v < 0:
            _reject("BAD_OHLC")
            continue
        if not ohlc_is_consistent(o, h, lo, cl):
            _reject("BAD_OHLC")
            continue
        valid.append((t_open, (render_price(o), render_price(h),
                               render_price(lo), render_price(cl),
                               render_price(v), committed_by)))

    rejected = sum(rejected_by_reason.values())

    # --- STEP 4/5: window index, then resolve per key ---------------------
    if valid:
        t_lo = min(t for t, _ in valid)
        t_hi = max(t for t, _ in valid)
        try:
            existing, _existing_conflicts = _window_index(
                root, symbol, interval_s, source, quote, t_lo, t_hi)
        except CandleStoreUnreadable:
            log.exception("candle store: journal unreadable - refusing to "
                          "ingest into a damaged store")
            raise
    else:
        existing = {}

    bar_rows: list[list[Any]] = []
    accepted = dup = conflict = 0
    seen: set[int] = set()
    for t_open, value in sorted(valid):
        if t_open in seen:
            # Two rows for the same key inside one batch: the first wins,
            # consistently with first-committed-wins across batches.
            dup += 1
            continue
        seen.add(t_open)
        prior = existing.get(t_open)
        if prior is None:
            accepted += 1
            bar_rows.append([SCHEMA_VERSION, "BAR", symbol, interval_s,
                             source, quote, t_open, *value[:5], value[5],
                             now])
        elif prior == value:
            dup += 1
        else:
            conflict += 1
            log.warning("candle store: venue revision for %s %ss %s/%s at "
                        "t_open_s=%d - journalled as CONFLICT; the "
                        "queryable value stays the first one",
                        symbol, interval_s, source, quote, t_open)
            bar_rows.append([SCHEMA_VERSION, "CONFLICT", symbol, interval_s,
                             source, quote, t_open, *value[:5], value[5],
                             now])

    # --- window derivation (law, not taste) -------------------------------
    win_to = _align_down(min(asked_to_s, committed_upto_s)
                         if asked_to_s is not None else committed_upto_s,
                         interval_s)
    out_note = note
    if asked_from_s is not None:
        win_from = _align_up(asked_from_s, interval_s)
    elif seen:
        # UNBOUNDED request (Kraken OHLC never states how far back it
        # looked): claim only from the oldest bar it actually returned.
        win_from = min(seen)
        out_note = out_note or "window_inferred_from_response"
    else:
        # Nothing to claim at all -> the empty-window sentinel.
        win_from = win_to + interval_s
        out_note = out_note or "window_inferred_from_response"
    if win_to < win_from:
        win_to = win_from - interval_s        # sentinel: claims nothing

    # A ledger row is appended only when the observation CHANGES the store:
    # new or conflicting bars, or a window not already covered. A re-run
    # that discovers nothing therefore appends ZERO bytes ANYWHERE, which
    # is what makes "run it twice -> identical store" literally true rather
    # than approximately true, and what stops a polling collector from
    # growing the ledger by one redundant row per idle poll. The caller
    # still gets the full IngestReport for its own logging.
    # status != "OK" rows are NEVER suppressed above: a failed fetch is a
    # real event and the ledger is the fetch-health series.
    adds_bars = bool(accepted or conflict)
    prior_windows = _existing_windows(root, symbol, interval_s, source, quote)
    already_covered = win_to >= win_from and all(
        _covered(prior_windows, t)
        for t in range(win_from, win_to + 1, interval_s))

    # --- STEP 6: bars FIRST, coverage SECOND. NEVER REVERSED --------------
    written = True
    if bar_rows:
        buf = io.StringIO(newline="")
        writer = csv.writer(buf)
        for row in bar_rows:
            writer.writerow(row)
        body = buf.getvalue()
        written = durable_append(journal_dir(root) / segment_name(now),
                                 lambda f: f.write(body),
                                 header=bar_header())
    if adds_bars or not already_covered:
        cov = _coverage_row(symbol, interval_s, source, quote, win_from,
                            win_to, committed_upto_s, committed_by, offered,
                            accepted, dup, conflict, rejected, status,
                            out_note, now)
        written = durable_append(cov_path,
                                 lambda f: csv.writer(f).writerow(cov),
                                 header=coverage_header()) and written

    return IngestReport(symbol, interval_s, source, quote, "OK", offered,
                        accepted, dup, conflict, rejected,
                        dict(rejected_by_reason), win_from, win_to, written,
                        out_note)
