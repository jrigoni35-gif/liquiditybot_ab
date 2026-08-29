"""Pins for the candle store's WRITE path and schema (data/candle_journal.py).

A test here is accepted only with mutation-kill evidence recorded in the
commit message: break the implementation in the named way, watch the pin go
RED, restore. Green alone is not evidence.

Every test passes an explicit `root=tmp_path`. The store has NO module-level
outputs/ path by construction (see test_candle_store_safe_class.py), so the
production tree is unreachable from here whatever a test does.
"""
from __future__ import annotations

import csv
import inspect
import math
from pathlib import Path

import pytest

from core.sanitize import clean_candles
from data import candle_journal as cj

IV = 300
T0 = 1787800000 - (1787800000 % IV)     # a 5m-grid bar open, in SECONDS
SERIES = cj.Series("kraken", "USD")
NOW = 1787900000


def _bars(n=10, start=T0, step=IV):
    return [{"time": start + i * step, "open": 100.0 + i, "high": 101.0 + i,
             "low": 99.0 + i, "close": 100.5 + i, "volume": 3.5 + i}
            for i in range(n)]


def _ingest(root, bars=None, *, symbol="ETH", interval_s=IV,
            source="kraken", quote="USD", committed_upto=None,
            committed_by="venue_last", asked_from=T0, asked_to=None,
            status="OK", now_s=NOW):
    bars = _bars() if bars is None else bars
    times = [b["time"] for b in bars if isinstance(b.get("time"), int)]
    if committed_upto is None:
        committed_upto = max(times) if times else T0
    if asked_to is None:
        asked_to = committed_upto
    return cj.ingest(symbol, interval_s, source, quote, bars,
                     committed_upto_s=committed_upto,
                     committed_by=committed_by, asked_from_s=asked_from,
                     asked_to_s=asked_to, status=status, now_s=now_s,
                     root=root)


def _files(root: Path) -> dict[Path, bytes]:
    return {p: p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


# --- P21 lane validation / path traversal (SECURITY) ----------------------

@pytest.mark.parametrize("symbol", [
    "../../status", "a/b", "..", "eth", "ETH/USD", "A" * 17, "",
    "ETH-USD", "..\\..\\status", "ETH USD", "ETH.USD",
])
def test_lane_validation_rejects_path_traversal(tmp_path, symbol):
    """MUTATION THAT MUST KILL THIS: relax _SYMBOL_RE to `.+`.

    The symbol reaches the store from a caller and becomes a filename, so
    this is a security control, not tidiness."""
    with pytest.raises(cj.CandleLaneError):
        _ingest(tmp_path, symbol=symbol)
    assert list(tmp_path.rglob("*")) == []       # nothing created anywhere


def test_a_windows_reserved_stem_is_admissible_because_of_the_suffix(tmp_path):
    """"CON" passes the regex ON PURPOSE and this pin says so out loud: the
    parquet partition is named `{SYMBOL}_{interval_s}.parquet`, so the
    reserved DEVICE stem (CON/AUX/NUL/PRN/COM1) is never the whole stem and
    is therefore unreachable. If that naming ever changes, this pin is
    where the reasoning is recorded."""
    rep = _ingest(tmp_path, symbol="CON")
    assert rep.bars_accepted == 10
    view = cj.load_view("CON", IV, series=SERIES, root=tmp_path)
    assert len(view.bars(T0, T0 + 9 * IV)) == 10
    # every journal segment is named for a month, never for a symbol
    assert all(p.name.endswith(f".v{cj.SCHEMA_VERSION}.csv")
               for p in (tmp_path / "journal").glob("*"))


def test_lane_validation_rejects_unknown_source_quote_committed_by(tmp_path):
    for kwargs in ({"source": "coinbase"}, {"quote": "EUR"},
                   {"committed_by": "guess"}, {"status": "MAYBE"}):
        with pytest.raises(cj.CandleLaneError):
            _ingest(tmp_path, **kwargs)


# --- P4 interval validated BEFORE any grid arithmetic ---------------------

@pytest.mark.parametrize("interval_s", [0, 7, -300, 5, "5m", 300.0, True])
def test_interval_validated_before_grid_arithmetic(tmp_path, interval_s):
    """MUTATION THAT MUST KILL THIS: move the INTERVALS membership check
    AFTER the `t_open_s % interval_s` grid check. interval_s=0 then raises
    ZeroDivisionError instead of the clean CandleLaneError - and in a SQL
    layer the same hazard is worse, because `t % 0` is NULL and a NULL
    CHECK is not a violation, so the grid check silently disappears.

    The same shape already exists in this repo: core.sanitize.
    interval_str_to_sec returns 0.0 on anything unparsable, which makes
    drop_forming_candles a silent no-op."""
    with pytest.raises(cj.CandleLaneError):
        _ingest(tmp_path, interval_s=interval_s)


def test_interval_must_be_seconds_not_a_venue_string(tmp_path):
    """'5m' is minutes, '5M' is five MONTHS in core.sanitize's table. The
    store never accepts a venue interval string; conversion belongs to the
    ingester."""
    with pytest.raises(cj.CandleLaneError):
        _ingest(tmp_path, interval_s="5m")        # type: ignore[arg-type]


# --- P3 the ms/s sentinel, with its own counter ---------------------------

def test_millisecond_timestamp_refused_with_its_own_counter(tmp_path):
    """MUTATION THAT MUST KILL THIS: delete the
    `_TS_MIN_S < t_open < _TS_MAX_S` check.

    A ms value checked against a seconds clock sheds EVERY bar, so the
    observable signature of a ms/s regression is silent total emptiness -
    indistinguishable from a dead endpoint. The report must therefore
    distinguish '0 accepted' from '0 offered'."""
    rep = _ingest(tmp_path, [{"time": 1788000000000, "open": 1.0,
                              "high": 1.0, "low": 1.0, "close": 1.0,
                              "volume": 0.0}],
                  committed_upto=1788000000000, asked_from=None,
                  asked_to=None)
    assert rep.rejected_by_reason["UNIT_RANGE"] == 1
    assert rep.bars_accepted == 0
    assert rep.bars_offered == 1
    assert rep.bars_rejected == 1


@pytest.mark.parametrize("bad_t,reason", [
    (T0 + 0.5, "NON_INTEGRAL"),
    ("1787800000", "NON_INTEGRAL"),
    (None, "NON_INTEGRAL"),
    (True, "NON_INTEGRAL"),
    (1788000000000, "UNIT_RANGE"),
    (12345, "UNIT_RANGE"),
    (T0 + 7, "MISALIGNED"),
])
def test_each_timestamp_rejection_has_its_own_counter(tmp_path, bad_t, reason):
    rep = _ingest(tmp_path, [{"time": bad_t, "open": 1.0, "high": 1.0,
                              "low": 1.0, "close": 1.0, "volume": 0.0}],
                  committed_upto=T0 + 10 * IV, asked_from=None, asked_to=None)
    assert rep.rejected_by_reason == {reason: 1}


def test_float_seconds_within_a_nanosecond_are_accepted(tmp_path):
    """data/ccxt_feed.py emits FLOAT seconds (`ts/1000.0`) where every other
    feed emits int. An exactly-integral float is narrowed, not refused."""
    rep = _ingest(tmp_path, [{"time": float(T0), "open": 1.0, "high": 1.0,
                              "low": 1.0, "close": 1.0, "volume": 0.0}],
                  committed_upto=T0, asked_from=T0, asked_to=T0)
    assert rep.bars_accepted == 1


# --- P5 the committed boundary is INCLUSIVE -------------------------------

def test_committed_boundary_is_inclusive(tmp_path):
    """MUTATION THAT MUST KILL THIS: change the FORMING test from
    `t_open > committed_upto_s` to `t_open >= committed_upto_s`.

    Matches core.sanitize.drop_forming_candles and
    tests/test_candle_integrity.py: the bar AT committed_upto_s is
    committed. Do not re-derive this with a strict <."""
    at = {"time": T0, "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0,
          "volume": 0.0}
    past = {**at, "time": T0 + IV}
    rep = _ingest(tmp_path, [at, past], committed_upto=T0, asked_from=T0,
                  asked_to=T0 + IV)
    assert rep.bars_accepted == 1
    assert rep.rejected_by_reason == {"FORMING": 1}


def test_forming_bars_are_never_persisted(tmp_path):
    """A still-forming bar frozen into an append-only store permanently
    understates its intrabar range (missed barrier touches, crushed
    ATR/sigma) and the damage is unrecoverable."""
    bars = _bars(6)
    _ingest(tmp_path, bars, committed_upto=T0 + 3 * IV,
            asked_from=T0, asked_to=T0 + 5 * IV)
    view = cj.load_view("ETH", IV, series=SERIES, root=tmp_path)
    assert [b.t_open_s for b in view.bars(T0, T0 + 5 * IV)] == [
        T0 + i * IV for i in range(4)]


# --- P18 OHLC self-consistency, CORROBORATED against core.sanitize --------

_OHLC_VECTORS = [
    ("valid", 100.0, 101.0, 99.0, 100.5),
    ("flat", 100.0, 100.0, 100.0, 100.0),
    ("high_below_low", 100.0, 98.0, 99.0, 100.0),
    ("close_above_high", 100.0, 101.0, 99.0, 102.0),
    ("open_above_high", 105.0, 101.0, 99.0, 100.0),
    ("low_above_close", 100.0, 101.0, 100.5, 100.0),
    ("zero_close", 100.0, 101.0, 99.0, 0.0),
    ("negative_low", 100.0, 101.0, -1.0, 100.0),
    ("inf_high", 100.0, math.inf, 99.0, 100.0),
    ("nan_close", 100.0, 101.0, 99.0, math.nan),
    ("zero_everything", 0.0, 0.0, 0.0, 0.0),
]


@pytest.mark.parametrize("name,o,h,lo,cl", _OHLC_VECTORS)
def test_ohlc_predicate_agrees_with_sanitize(name, o, h, lo, cl):
    """CROSS-IMPLEMENTATION CORROBORATION, not a copied constant hoping to
    stay in sync. MUTATION THAT MUST KILL THIS: drop one conjunct from
    ohlc_is_consistent (e.g. `high < max(open, close)`) - the
    close_above_high / open_above_high vectors then disagree.

    core.sanitize is the source of truth; this predicate is restated in the
    store because a bot_cache bar arrives from outputs/state.json and never
    passed through sanitize at all."""
    ours = cj.ohlc_is_consistent(o, h, lo, cl)
    theirs = bool(clean_candles([{"time": T0, "open": o, "high": h,
                                  "low": lo, "close": cl, "volume": 1.0}]))
    assert ours == theirs, f"{name}: store={ours} sanitize={theirs}"


@pytest.mark.parametrize("name,o,h,lo,cl", _OHLC_VECTORS)
def test_bad_ohlc_is_rejected_at_ingest_never_repaired(tmp_path, name, o, h,
                                                       lo, cl):
    rep = _ingest(tmp_path, [{"time": T0, "open": o, "high": h, "low": lo,
                              "close": cl, "volume": 1.0}],
                  committed_upto=T0, asked_from=T0, asked_to=T0)
    expected_ok = cj.ohlc_is_consistent(o, h, lo, cl)
    assert rep.bars_accepted == (1 if expected_ok else 0)
    if not expected_ok:
        assert rep.rejected_by_reason == {"BAD_OHLC": 1}


# --- P14 UNKNOWN is never zero -------------------------------------------

def test_unknown_is_never_zero(tmp_path):
    """MUTATION THAT MUST KILL THIS: parse '' as `float(x or 0)` in
    _parse_optional_float.

    The bot_cache lane stores t/c/h/l only - no open, no volume - and both
    must round-trip as None. Asserted with `is None`, never a falsy check:
    0.0 is falsy and is exactly the value this rule forbids."""
    rep = cj.ingest("ETH", IV, "bot_cache", "USD",
                    [{"time": T0, "high": 101.0, "low": 99.0,
                      "close": 100.0}],
                    committed_upto_s=T0, committed_by="clock",
                    asked_from_s=T0, asked_to_s=T0, now_s=NOW, root=tmp_path)
    assert rep.bars_accepted == 1
    seg = next((tmp_path / "journal").glob("*.csv"))
    row = list(csv.DictReader(seg.open(encoding="utf-8", newline="")))[0]
    assert row["open"] == "" and row["volume"] == ""

    series = cj.Series("bot_cache", "USD")
    view = cj.load_view("ETH", IV, series=series, root=tmp_path)
    bar = view.bars(T0, T0)[0]
    assert bar.open is None
    assert bar.volume is None
    value, reason, stamp = view.price_at(T0, "open")
    assert value is None
    assert reason == "FIELD_UNKNOWN"
    assert stamp["t_open_s"] == T0
    # a PRESENT bar with an UNKNOWN field is not the same as an absent bar
    assert view.price_at(T0, "close")[1] == "OK"


def test_volume_zero_is_stored_as_zero_not_as_unknown(tmp_path):
    """A genuine zero-volume bar and an UNKNOWN one must stay
    distinguishable, which is the whole point of the '' encoding."""
    _ingest(tmp_path, [{"time": T0, "open": 1.0, "high": 1.0, "low": 1.0,
                        "close": 1.0, "volume": 0.0}],
            committed_upto=T0, asked_from=T0, asked_to=T0)
    view = cj.load_view("ETH", IV, series=SERIES, root=tmp_path)
    assert view.bars(T0, T0)[0].volume == 0.0


# --- P17 the price formatter IS part of the schema ------------------------

def test_price_formatter_is_pinned_to_the_corpus_formatter():
    """MUTATION THAT MUST KILL THIS: change _PRICE_FORMAT to '%.6g'.

    Byte-identical to ml/history.py's own entry_price formatter, so a
    stored close and a corpus entry_price compare AS STRINGS. Changing it
    makes every already-stored bar read as a CONFLICT."""
    vector = [1.0, 0.1, 1234.5678901234, 1e-9, 123456789012.0, 0.30000000004,
              99999.999999, 2.5e-8]
    assert [cj.render_price(x) for x in vector] == [f"{x:.10g}"
                                                    for x in vector]
    assert cj.render_price(None) == ""


def test_stored_close_is_byte_identical_to_the_corpus_rendering(tmp_path):
    price = 2543.210987654321
    _ingest(tmp_path, [{"time": T0, "open": price, "high": price,
                        "low": price, "close": price, "volume": 1.0}],
            committed_upto=T0, asked_from=T0, asked_to=T0)
    seg = next((tmp_path / "journal").glob("*.csv"))
    row = list(csv.DictReader(seg.open(encoding="utf-8", newline="")))[0]
    assert row["close"] == f"{price:.10g}"


# --- P6 idempotence: a re-run appends ZERO bytes --------------------------

def test_reingest_appends_zero_bytes(tmp_path):
    """MUTATION A THAT MUST KILL THIS: delete the `_window_index` lookup in
    step 4/5 so every offered bar is appended - N rows land again and the
    journal bytes differ.
    MUTATION B: include ingest_s in _VALUE_COLUMNS - every bar then reads
    as a CONFLICT at a different wall clock.

    Note the second ingest runs at a DIFFERENT now_s, which is the point:
    ingest_s is provenance and is excluded from the duplicate comparison."""
    rep1 = _ingest(tmp_path, now_s=NOW)
    assert rep1.bars_accepted == 10
    before = _files(tmp_path)
    assert before, "the first ingest must have written something"

    rep2 = _ingest(tmp_path, now_s=NOW + 3600)
    assert rep2.bars_accepted == 0
    assert rep2.bars_dup == 10
    assert rep2.bars_conflict == 0
    after = _files(tmp_path)
    assert set(after) == set(before), "a re-run created a file"
    assert after == before, "a re-run changed bytes"


def test_reingest_is_idempotent_for_the_content_digest(tmp_path):
    _ingest(tmp_path, now_s=NOW)
    d1 = cj.content_digest(tmp_path)
    _ingest(tmp_path, now_s=NOW + 86400)
    assert cj.content_digest(tmp_path) == d1


def test_a_later_run_that_extends_the_window_appends_only_the_new_bars(
        tmp_path):
    """Resumability: the second run overlaps the first by 5 bars and must
    append exactly the 5 new ones."""
    _ingest(tmp_path, _bars(10), committed_upto=T0 + 9 * IV, asked_from=T0,
            asked_to=T0 + 9 * IV)
    rep = _ingest(tmp_path, _bars(15), committed_upto=T0 + 14 * IV,
                  asked_from=T0, asked_to=T0 + 14 * IV, now_s=NOW + 60)
    assert (rep.bars_accepted, rep.bars_dup) == (5, 10)
    view = cj.load_view("ETH", IV, series=SERIES, root=tmp_path)
    assert len(view.bars(T0, T0 + 14 * IV)) == 15


# --- P7 a conflict is journalled and NEVER overwrites ---------------------

def test_conflict_journalled_never_overwrites(tmp_path):
    """MUTATION THAT MUST KILL THIS: switch resolution to last-wins (let a
    differing value replace the stored one).

    First-committed-wins, because last-wins lets a late forming-bar leak
    silently overwrite good history and the data is not re-acquirable -
    Kraken serves 720 committed bars and `since` does not page backward. A
    venue revision is a FACT ABOUT THE VENUE that analysis must see, so it
    is journalled rather than discarded."""
    base = {"time": T0, "open": 100.0, "high": 103.0, "low": 99.0,
            "close": 102.0, "volume": 1.0}
    _ingest(tmp_path, [base], committed_upto=T0, asked_from=T0, asked_to=T0)
    rep = _ingest(tmp_path, [{**base, "close": 101.5}], committed_upto=T0,
                  asked_from=T0, asked_to=T0, now_s=NOW + 60)
    assert rep.bars_conflict == 1
    assert rep.bars_accepted == 0

    seg = next((tmp_path / "journal").glob("*.csv"))
    rows = list(csv.DictReader(seg.open(encoding="utf-8", newline="")))
    assert [r["record_kind"] for r in rows] == ["BAR", "CONFLICT"]
    assert rows[1]["close"] == "101.5"          # the disagreement is kept

    view = cj.load_view("ETH", IV, series=SERIES, root=tmp_path)
    assert view.bars(T0, T0)[0].close == 102.0   # first-committed still wins
    assert view.coverage_of(T0) == "CONFLICTED"
    # a contradicted bar yields a value to a query but never to a statistic
    assert view.price_at(T0)[0] == 102.0
    assert view.forward_return(T0, IV)[1].startswith("anchor_CONFLICTED")


def test_identical_revalue_is_a_dup_not_a_conflict(tmp_path):
    base = {"time": T0, "open": 100.0, "high": 103.0, "low": 99.0,
            "close": 102.0, "volume": 1.0}
    _ingest(tmp_path, [base], committed_upto=T0, asked_from=T0, asked_to=T0)
    rep = _ingest(tmp_path, [base], committed_upto=T0, asked_from=T0,
                  asked_to=T0, now_s=NOW + 999)
    assert (rep.bars_dup, rep.bars_conflict) == (1, 0)


# --- schema shape ---------------------------------------------------------

def test_headers_are_the_schema(tmp_path):
    _ingest(tmp_path)
    jseg = next((tmp_path / "journal").glob("*.csv"))
    cseg = next((tmp_path / "coverage").glob("*.csv"))
    assert jseg.read_text(encoding="utf-8").splitlines()[0] == \
        ",".join(cj.BAR_COLUMNS)
    assert cseg.read_text(encoding="utf-8").splitlines()[0] == \
        ",".join(cj.COVERAGE_COLUMNS)
    assert jseg.name.endswith(f".v{cj.SCHEMA_VERSION}.csv")


def test_the_timestamp_column_names_its_unit():
    """The 100x pct-vs-fraction error that made 23,826 recorded outcomes
    inert, and the ms/s candle incident, were both bought by columns that
    did not name their unit. `t_open_s` does."""
    assert "t_open_s" in cj.BAR_COLUMNS
    assert "ts" not in cj.BAR_COLUMNS and "time" not in cj.BAR_COLUMNS
    assert cj.segment_name(1787900000) == "2026-08.v1.csv"


def test_out_of_window_bars_are_rejected_with_their_own_counter(tmp_path):
    rep = _ingest(tmp_path, _bars(10), committed_upto=T0 + 9 * IV,
                  asked_from=T0 + 3 * IV, asked_to=T0 + 6 * IV)
    assert rep.bars_accepted == 4
    assert rep.rejected_by_reason == {"OUT_OF_WINDOW": 6}


# --- P19 canonical order / compaction determinism -------------------------

def test_canonical_order_is_independent_of_arrival_order(tmp_path):
    """MUTATION THAT MUST KILL THIS: delete the final
    `out.sort(...)` in canonical_bar_rows.

    Without it the output is in ARRIVAL order, so the identical row set
    backfilled ETH-then-BTC and BTC-then-ETH compacts to different bytes
    and the store stops being reproducible. Byte identity is a property of
    an identical WRITE SEQUENCE; the CONTENT digest is the contract."""
    a = tmp_path / "a"
    b = tmp_path / "b"
    eth = _bars(5)
    btc = [{**x, "open": x["open"] + 1000.0, "high": x["high"] + 1000.0,
            "low": x["low"] + 1000.0, "close": x["close"] + 1000.0}
           for x in _bars(5)]
    for root, order in ((a, ("ETH", "BTC")), (b, ("BTC", "ETH"))):
        for sym in order:
            _ingest(root, eth if sym == "ETH" else btc, symbol=sym,
                    committed_upto=T0 + 4 * IV, asked_from=T0,
                    asked_to=T0 + 4 * IV)
    assert cj.canonical_digest(a) == cj.canonical_digest(b)
    rows = cj.canonical_bar_rows(a)
    assert [r["symbol"] for r in rows] == ["BTC"] * 5 + ["ETH"] * 5
    assert [int(r["t_open_s"]) for r in rows[:5]] == \
        [T0 + i * IV for i in range(5)]


def test_conflicts_are_excluded_from_value_selection(tmp_path):
    base = {"time": T0, "open": 100.0, "high": 103.0, "low": 99.0,
            "close": 102.0, "volume": 1.0}
    _ingest(tmp_path, [base], committed_upto=T0, asked_from=T0, asked_to=T0)
    _ingest(tmp_path, [{**base, "close": 101.5}], committed_upto=T0,
            asked_from=T0, asked_to=T0, now_s=NOW + 60)
    rows = cj.canonical_bar_rows(tmp_path)
    assert len(rows) == 1
    assert rows[0]["close"] == "102"


def test_rebuild_from_the_journal_alone_reproduces_the_index(tmp_path):
    """The parquet tree is DISPOSABLE: rm -r parquet/ && rebuild()."""
    pytest.importorskip("polars")
    import scripts.candle_store as cs
    _ingest(tmp_path)
    r1 = cs.compact(tmp_path, full=True)
    assert r1.partitions == 1 and r1.rows == 10
    d1 = r1.canonical_digest
    r2 = cs.rebuild(tmp_path)
    assert r2.canonical_digest == d1
    assert cs.compact(tmp_path, full=False).skipped is True
    rep = cs.verify(tmp_path, deep=True)
    assert rep.ok and rep.deep_matches is True
    assert rep.bar_rows == 10 and rep.conflicts == 0


# --- lock -----------------------------------------------------------------

def test_a_held_lock_refuses_rather_than_waiting_or_proceeding(tmp_path):
    lock = cj._IngestLock(tmp_path)
    assert lock.acquire() is True
    try:
        rep = _ingest(tmp_path)
        assert rep.status == "LOCKED"
        assert rep.bars_accepted == 0
        assert not (tmp_path / "journal").exists()
    finally:
        lock.release()
    assert _ingest(tmp_path).status == "OK"


def test_no_tolerance_parameter_exists_anywhere(tmp_path):
    """P11. MUTATION THAT MUST KILL THIS: add `tolerance_s=0` to
    forward_return.

    A tolerance >= the horizon makes every anchor match ITSELF and the cell
    reads 100% coverage - an artifact, measured on the corpus self-join. A
    caller wanting slack implements it, names it, and owns the error."""
    targets = [cj.forward_return, cj.forward_returns_batch, cj.price_at,
               cj.CandleView.forward_return, cj.CandleView.price_at,
               cj.CandleView.forward_returns_batch]
    for fn in targets:
        params = inspect.signature(fn).parameters
        assert not [p for p in params if p.startswith("tolerance")], fn
