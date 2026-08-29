"""Pins for the candle store's READ path: the coverage algebra and the
UNKNOWN split (data/candle_journal.py, scripts/candle_collect.py).

THE FIVE-WAY SPLIT IS THE POINT. NOT_COVERED (we never looked),
NO_BAR_IN_COVERED_WINDOW (we looked, the venue had nothing),
BEYOND_RIGHT_EDGE (right-censored), BEFORE_LEFT_EDGE (backfillable past)
and STORE_UNREADABLE (an instrument fault) are five different epistemic
states. Collapsing any pair biases every horizon-stratified number in one
direction, and the bias concentrates in the thin-alt cohort whose sampling
is 5-10x sparser than ETH's.

Mutation-kill evidence for each load-bearing pin is named in its docstring
and recorded in the commit message.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from data import candle_journal as cj

IV = 300
T0 = 1787800000 - (1787800000 % IV)
SERIES = cj.Series("kraken", "USD")
NOW = 1787900000


def _bars(n, start=T0, step=IV, base=100.0):
    return [{"time": start + i * step, "open": base, "high": base + 1.0,
             "low": base - 1.0, "close": base + 0.5, "volume": 1.0}
            for i in range(n)]


def _ingest(root, bars, *, symbol="ETH", interval_s=IV, source="kraken",
            quote="USD", committed_upto, asked_from, asked_to,
            committed_by="venue_last", status="OK", now_s=NOW):
    return cj.ingest(symbol, interval_s, source, quote, bars,
                     committed_upto_s=committed_upto,
                     committed_by=committed_by, asked_from_s=asked_from,
                     asked_to_s=asked_to, status=status, now_s=now_s,
                     root=root)


def _files(root: Path) -> dict[Path, bytes]:
    return {p: p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


# --- P1 the crash-order pin: bars FIRST, coverage SECOND ------------------

def _only_first_append(monkeypatch):
    """Let the FIRST durable_append of an ingest land and drop the second -
    a kill in the window between the two writes."""
    calls = {"n": 0}
    real = cj.durable_append

    def fake(path, render, **kw):
        calls["n"] += 1
        if calls["n"] == 1:
            return real(path, render, **kw)
        return True                    # the process died before this one

    monkeypatch.setattr(cj, "durable_append", fake)
    return calls


def test_bars_before_coverage_crash_order(tmp_path, monkeypatch):
    """THE PIN THAT MATTERS MOST.

    MUTATION THAT MUST KILL THIS: swap the two durable_append calls in
    _ingest_locked so the coverage row is written first. The pin then flips
    from NOT_COVERED to NO_BAR_IN_COVERED_WINDOW.

    Those two answers are not equally wrong. Bars-first means a crash
    leaves bars on disk with no coverage: they read NOT_COVERED, are
    invisible until re-covered, and the next successful run heals it -
    UNDER-claiming, benign. Coverage-first means the store claims a window
    over bars that were never written, so a real hole reports as "we looked
    and the venue had nothing". That is a confident lie with no external
    symptom, and no downstream check can catch it."""
    _only_first_append(monkeypatch)
    rep = _ingest(tmp_path, _bars(5), committed_upto=T0 + 4 * IV,
                  asked_from=T0, asked_to=T0 + 4 * IV)
    assert rep.bars_accepted == 5

    view = cj.load_view("ETH", IV, series=SERIES, root=tmp_path)
    reason = view.coverage_of(T0)
    assert reason == "NOT_COVERED", (
        f"a kill between the two writes reported {reason!r}. "
        f"NO_BAR_IN_COVERED_WINDOW here would mean the store claims it "
        f"looked and the venue had nothing, when in truth the write died - "
        f"the writes are in the wrong order.")
    assert view.price_at(T0) == (None, "NOT_COVERED", view.price_at(T0)[2])

    # the journal landed; the coverage ledger did not
    assert (tmp_path / "journal").is_dir()
    assert not (tmp_path / "coverage").exists()
    # ...and it self-heals on the next complete run (the process restarted,
    # so the simulated kill is no longer in force)
    monkeypatch.undo()
    _ingest(tmp_path, _bars(5), committed_upto=T0 + 4 * IV, asked_from=T0,
            asked_to=T0 + 4 * IV, now_s=NOW + 60)
    healed = cj.load_view("ETH", IV, series=SERIES, root=tmp_path)
    assert healed.coverage_of(T0) == "OK"


# --- P2 a failed fetch must NEVER widen coverage --------------------------

@pytest.mark.parametrize("status", ["FETCH_FAILED", "EMPTY"])
def test_failed_fetch_never_widens_coverage(tmp_path, status):
    """MUTATION THAT MUST KILL THIS: remove the empty-window sentinel so a
    status != "OK" row writes win_to_s = asked_to_s. Every slot in the
    asked window then reads NO_BAR_IN_COVERED_WINDOW - "the venue had
    nothing" - when in truth the fetch never returned.

    data/_http.py:_get_json returns None on BOTH a transport failure and a
    hostile-body rejection, and every get_candles turns that None into [].
    An empty list is therefore ambiguous and must never be recorded as
    'no data existed'."""
    a, b = T0, T0 + 20 * IV
    rep = _ingest(tmp_path, [], committed_upto=b, asked_from=a, asked_to=b,
                  status=status)
    assert rep.win_to_s < rep.win_from_s          # the sentinel
    view = cj.load_view("ETH", IV, series=SERIES, root=tmp_path)
    for t in range(a, b + 1, IV):
        assert view.coverage_of(t) == "NOT_COVERED", t
    assert cj.covered_windows("ETH", IV, series=SERIES, root=tmp_path) == []


def test_a_successful_empty_window_IS_a_real_hole(tmp_path):
    """The complement of the pin above: when the venue genuinely answered
    and had nothing, the window IS covered and the slots are holes."""
    a, b = T0, T0 + 4 * IV
    _ingest(tmp_path, [], committed_upto=b, asked_from=a, asked_to=b,
            status="OK")
    view = cj.load_view("ETH", IV, series=SERIES, root=tmp_path)
    for t in range(a, b + 1, IV):
        assert view.coverage_of(t) == "NO_BAR_IN_COVERED_WINDOW", t


# --- the coverage algebra -------------------------------------------------

def test_bar_adjacent_windows_fuse_but_a_one_bar_hole_does_not(tmp_path):
    _ingest(tmp_path, _bars(3), committed_upto=T0 + 2 * IV, asked_from=T0,
            asked_to=T0 + 2 * IV)
    # adjacent: starts exactly one bar after the previous window's end
    _ingest(tmp_path, _bars(3, start=T0 + 3 * IV),
            committed_upto=T0 + 5 * IV, asked_from=T0 + 3 * IV,
            asked_to=T0 + 5 * IV, now_s=NOW + 1)
    # disjoint: a genuine gap of several bars
    _ingest(tmp_path, _bars(3, start=T0 + 10 * IV),
            committed_upto=T0 + 12 * IV, asked_from=T0 + 10 * IV,
            asked_to=T0 + 12 * IV, now_s=NOW + 2)
    wins = cj.covered_windows("ETH", IV, series=SERIES, root=tmp_path)
    assert wins == [(T0, T0 + 5 * IV), (T0 + 10 * IV, T0 + 12 * IV)]


def test_coverage_reports_its_own_denominator(tmp_path):
    """expected_bars and present_bars travel TOGETHER so no horizon number
    can be quoted without its denominator - "a green is only as big as its
    corpus", transposed to this instrument."""
    bars = [b for b in _bars(10) if b["time"] != T0 + 4 * IV]
    _ingest(tmp_path, bars, committed_upto=T0 + 9 * IV, asked_from=T0,
            asked_to=T0 + 9 * IV)
    out = cj.coverage("ETH", IV, T0, T0 + 19 * IV, series=SERIES,
                      root=tmp_path)
    assert out["expected_bars"] == 20
    assert out["covered_bars"] == 10
    assert out["present_bars"] == 9
    assert out["missing_in_covered"] == 1
    assert out["uncovered_bars"] == 10
    assert out["holes_in_covered"] == [(T0 + 4 * IV, T0 + 4 * IV)]
    assert out["uncovered_windows"] == [(T0 + 10 * IV, T0 + 19 * IV)]
    assert out["left_edge_s"] == T0 and out["right_edge_s"] == T0 + 9 * IV
    assert out["committed_by_mix"] == {"venue_last": 9}
    assert out["read_at_s"] > 0            # snapshot stamp: values are as-of
    assert out["store_schema_version"] == cj.SCHEMA_VERSION


def test_bars_yields_nothing_for_a_gap_never_a_placeholder(tmp_path):
    """A NaN bar in a numpy path is the zero-fill sin wearing a different
    hat. MUTATION THAT MUST KILL THIS: emit a placeholder Bar for a missing
    slot."""
    bars = [b for b in _bars(5) if b["time"] != T0 + 2 * IV]
    _ingest(tmp_path, bars, committed_upto=T0 + 4 * IV, asked_from=T0,
            asked_to=T0 + 4 * IV)
    got = cj.bars("ETH", IV, T0, T0 + 4 * IV, series=SERIES, root=tmp_path)
    assert [b.t_open_s for b in got] == [T0, T0 + IV, T0 + 3 * IV,
                                         T0 + 4 * IV]
    assert all(b.close is not None for b in got)


def test_price_at_floors_and_never_reaches_for_a_neighbour(tmp_path):
    _ingest(tmp_path, _bars(3), committed_upto=T0 + 2 * IV, asked_from=T0,
            asked_to=T0 + 2 * IV)
    view = cj.load_view("ETH", IV, series=SERIES, root=tmp_path)
    value, reason, stamp = view.price_at(T0 + 299)
    assert reason == "OK" and value == 100.5
    assert stamp["t_open_s"] == T0 and stamp["offset_s"] == 299
    assert stamp["source"] == "kraken" and stamp["quote"] == "USD"
    # one second past the last stored bar's window is NOT forward-filled
    assert view.price_at(T0 + 3 * IV)[0] is None


def test_forward_return_matches_the_corpus_formula(tmp_path):
    _ingest(tmp_path, [
        {"time": T0, "open": 100.0, "high": 100.0, "low": 100.0,
         "close": 100.0, "volume": 1.0},
        {"time": T0 + IV, "open": 110.0, "high": 110.0, "low": 110.0,
         "close": 110.0, "volume": 1.0},
    ], committed_upto=T0 + IV, asked_from=T0, asked_to=T0 + IV)
    view = cj.load_view("ETH", IV, series=SERIES, root=tmp_path)
    assert view.forward_return(T0, IV) == (10.0, "OK")
    assert view.forward_return(T0, IV, side="short") == (-10.0, "OK")
    assert view.forward_returns_batch([T0, T0 + IV], IV) == [
        (10.0, "OK"), (None, "forward_BEYOND_RIGHT_EDGE")]
    assert cj.forward_returns_batch([("ETH", T0)], IV, interval_s=IV,
                                    series=SERIES, root=tmp_path) == [
        (10.0, "OK")]


def test_reason_prefixing_separates_no_anchor_from_no_future(tmp_path):
    """MUTATION THAT MUST KILL THIS: return a flat reason instead of
    anchor_/forward_.

    Right-censoring is missing-not-at-random on the TRAILING edge; a hole
    is missing-not-at-random on the THIN ALTS. A study that cannot tell
    them apart pools two different biases."""
    bars = [b for b in _bars(10) if b["time"] != T0 + 5 * IV]
    _ingest(tmp_path, bars, committed_upto=T0 + 9 * IV, asked_from=T0,
            asked_to=T0 + 9 * IV)
    view = cj.load_view("ETH", IV, series=SERIES, root=tmp_path)
    assert view.forward_return(T0 + 5 * IV, IV)[1] == \
        "anchor_NO_BAR_IN_COVERED_WINDOW"
    assert view.forward_return(T0 + 4 * IV, IV)[1] == \
        "forward_NO_BAR_IN_COVERED_WINDOW"
    assert view.forward_return(T0 + 9 * IV, IV)[1] == \
        "forward_BEYOND_RIGHT_EDGE"
    assert view.forward_return(T0 + 3, IV) == (None, "MISALIGNED_T0")


# --- P15 an instrument fault is NEVER a data gap --------------------------

@pytest.mark.parametrize("damage", ["torn_row", "garbage_header",
                                    "future_schema"])
def test_store_unreadable_is_not_a_data_gap(tmp_path, damage):
    """MUTATION THAT MUST KILL THIS: catch CandleStoreUnreadable in
    CandleView._load and report NOT_COVERED.

    "0 findings" and "the scan is broken" are the same observation until
    separated. A damaged store must say so; reporting it as a data hole is
    the confident-instrument failure this repo keeps re-buying."""
    _ingest(tmp_path, _bars(5), committed_upto=T0 + 4 * IV, asked_from=T0,
            asked_to=T0 + 4 * IV)
    seg = next((tmp_path / "journal").glob("*.csv"))
    if damage == "torn_row":
        raw = seg.read_bytes()
        seg.write_bytes(raw[:-14])          # truncate mid-record
    elif damage == "garbage_header":
        seg.write_bytes(b"not,a,schema\r\n1,2,3\r\n")
    else:
        seg.rename(seg.with_name(f"2026-08.v{cj.SCHEMA_VERSION + 1}.csv"))

    view = cj.load_view("ETH", IV, series=SERIES, root=tmp_path)
    assert view.unreadable
    assert view.coverage_of(T0) == "STORE_UNREADABLE"
    assert view.price_at(T0)[1] == "STORE_UNREADABLE"
    assert view.forward_return(T0, IV)[1] == "anchor_STORE_UNREADABLE"
    assert view.coverage_of(T0) != "NOT_COVERED"


def test_a_damaged_store_refuses_further_ingest(tmp_path):
    """Refuse rather than start a second, divergent history beside bytes
    the reader cannot parse."""
    _ingest(tmp_path, _bars(5), committed_upto=T0 + 4 * IV, asked_from=T0,
            asked_to=T0 + 4 * IV)
    seg = next((tmp_path / "journal").glob("*.csv"))
    seg.write_bytes(b"not,a,schema\r\n")
    with pytest.raises(cj.CandleStoreUnreadable):
        _ingest(tmp_path, _bars(5, start=T0 + 10 * IV),
                committed_upto=T0 + 14 * IV, asked_from=T0 + 10 * IV,
                asked_to=T0 + 14 * IV, now_s=NOW + 60)


# --- P12 the reason vocabulary: exhaustive AND reachable ------------------

def _write_raw_bar(root: Path, *, close: str, symbol="ETH") -> None:
    """Hand-build a segment. The only way to put a value in the store that
    ingest() would refuse - which is how the NONPOSITIVE_ANCHOR guard is
    reachable at all (see its docstring)."""
    jseg = root / "journal" / cj.segment_name(NOW)
    cseg = root / "coverage" / cj.segment_name(NOW)
    jseg.parent.mkdir(parents=True, exist_ok=True)
    cseg.parent.mkdir(parents=True, exist_ok=True)
    with open(jseg, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(cj.BAR_COLUMNS)
        w.writerow([1, "BAR", symbol, IV, "kraken", "USD", T0, "", close,
                    close, close, "", "clock", NOW])
    with open(cseg, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(cj.COVERAGE_COLUMNS)
        w.writerow([1, symbol, IV, "kraken", "USD", T0, T0 + IV, T0 + IV,
                    "clock", 1, 1, 0, 0, 0, "OK", "", NOW])


def _reachable_reasons(tmp_path) -> set[str]:
    """One constructed case per REASONS member. If a member cannot be
    reached, it does not belong in the vocabulary."""
    seen: set[str] = set()

    def note(reason: str) -> None:
        seen.add(reason.replace("anchor_", "").replace("forward_", ""))

    # OK / NO_BAR_IN_COVERED_WINDOW / NOT_COVERED / edges
    a = tmp_path / "a"
    bars = [b for b in _bars(5) if b["time"] != T0 + 2 * IV]
    _ingest(a, bars, committed_upto=T0 + 4 * IV, asked_from=T0,
            asked_to=T0 + 4 * IV)
    _ingest(a, _bars(3, start=T0 + 20 * IV), committed_upto=T0 + 22 * IV,
            asked_from=T0 + 20 * IV, asked_to=T0 + 22 * IV, now_s=NOW + 1)
    va = cj.load_view("ETH", IV, series=SERIES, root=a)
    note(va.coverage_of(T0))                       # OK
    note(va.coverage_of(T0 + 2 * IV))              # NO_BAR_IN_COVERED_WINDOW
    note(va.coverage_of(T0 + 10 * IV))             # NOT_COVERED
    note(va.coverage_of(T0 - 10 * IV))             # BEFORE_LEFT_EDGE
    note(va.coverage_of(T0 + 99 * IV))             # BEYOND_RIGHT_EDGE
    note(va.forward_return(T0 + 3, IV)[1])         # MISALIGNED_T0
    # QUOTE_MISMATCH / SYMBOL_UNKNOWN / INTERVAL_UNKNOWN
    note(cj.load_view("ETH", IV, series=cj.Series("kraken", "USDT"),
                      root=a).coverage_of(T0))
    note(cj.load_view("XYZ", IV, series=SERIES, root=a).coverage_of(T0))
    note(cj.load_view("ETH", 3600, series=SERIES, root=a).coverage_of(T0))
    # FIELD_UNKNOWN (the bot_cache lane has no open, no volume)
    b = tmp_path / "b"
    cj.ingest("ETH", IV, "bot_cache", "USD",
              [{"time": T0, "high": 101.0, "low": 99.0, "close": 100.0}],
              committed_upto_s=T0, committed_by="clock", asked_from_s=T0,
              asked_to_s=T0, now_s=NOW, root=b)
    note(cj.load_view("ETH", IV, series=cj.Series("bot_cache", "USD"),
                      root=b).price_at(T0, "open")[1])
    # CONFLICTED
    c = tmp_path / "c"
    base = {"time": T0, "open": 100.0, "high": 103.0, "low": 99.0,
            "close": 102.0, "volume": 1.0}
    _ingest(c, [base], committed_upto=T0, asked_from=T0, asked_to=T0)
    _ingest(c, [{**base, "close": 101.5}], committed_upto=T0, asked_from=T0,
            asked_to=T0, now_s=NOW + 60)
    note(cj.load_view("ETH", IV, series=SERIES, root=c).coverage_of(T0))
    # NONPOSITIVE_ANCHOR
    d = tmp_path / "d"
    _write_raw_bar(d, close="0")
    note(cj.load_view("ETH", IV, series=SERIES, root=d).forward_return(
        T0, IV)[1])
    # STORE_UNREADABLE
    e = tmp_path / "e"
    _write_raw_bar(e, close="100")
    next((e / "journal").glob("*.csv")).write_bytes(b"garbage\r\n")
    note(cj.load_view("ETH", IV, series=SERIES, root=e).coverage_of(T0))
    return seen


def test_reason_vocabulary_exhaustive_and_reachable(tmp_path):
    """BOTH DIRECTIONS.

    MUTATION A THAT MUST KILL THIS: emit a bare string (e.g. "MISSING")
    from one branch of coverage_of - the subset assertion fails.
    MUTATION B: add an unreachable member to REASONS - the equality
    assertion fails.

    Same discipline as core/codes.py (closed set, never a bare string),
    adopted locally rather than by registering a family there, because an
    entry in core/codes.py would create an import-graph edge from every
    decision module toward this store's vocabulary."""
    seen = _reachable_reasons(tmp_path)
    assert seen <= cj.REASONS, f"reasons emitted outside the vocabulary: " \
                               f"{sorted(seen - cj.REASONS)}"
    assert seen == set(cj.REASONS), \
        f"unreachable members: {sorted(set(cj.REASONS) - seen)}"


def test_nonpositive_anchor_is_none_not_infinity(tmp_path):
    """The corpus encodes UNKNOWN entry_price as the literal 0 on thousands
    of rows. A reader that divides by it produces a silent +-inf; this
    store returns an honest UNKNOWN instead."""
    _write_raw_bar(tmp_path, close="0")
    value, reason = cj.load_view("ETH", IV, series=SERIES,
                                 root=tmp_path).forward_return(T0, IV)
    assert value is None
    assert reason == "anchor_NONPOSITIVE_ANCHOR"


# --- P8 the read path creates and mutates NOTHING -------------------------

def test_read_path_creates_and_mutates_nothing(tmp_path):
    """MUTATION THAT MUST KILL THIS: call mkdir/ensure/compact from any
    read path (e.g. `store_root(root).mkdir(parents=True, exist_ok=True)`
    at the top of CandleView._load).

    This is the 2026-07-11 incident class removed rather than guarded: a
    schema bump plus init-time rotation destroyed live rows. Constructing a
    view, reading coverage, or running any query must leave every byte
    alone - and a MISSING root must stay missing."""
    _ingest(tmp_path, _bars(5), committed_upto=T0 + 4 * IV, asked_from=T0,
            asked_to=T0 + 4 * IV)
    before = _files(tmp_path)
    names_before = {p for p in tmp_path.rglob("*")}

    view = cj.load_view("ETH", IV, series=SERIES, root=tmp_path)
    view.coverage(T0, T0 + 20 * IV)
    view.price_at(T0)
    view.forward_return(T0, IV)
    view.bars(T0, T0 + 4 * IV)
    cj.coverage("ETH", IV, T0, T0 + IV, series=SERIES, root=tmp_path)
    cj.price_at("ETH", T0, interval_s=IV, series=SERIES, root=tmp_path)
    cj.forward_return("ETH", T0, IV, interval_s=IV, series=SERIES,
                      root=tmp_path)
    cj.bars("ETH", IV, T0, T0 + IV, series=SERIES, root=tmp_path)
    cj.covered_windows("ETH", IV, series=SERIES, root=tmp_path)
    cj.lanes(root=tmp_path)
    cj.content_digest(tmp_path)
    cj.canonical_digest(tmp_path)

    assert _files(tmp_path) == before
    assert {p for p in tmp_path.rglob("*")} == names_before
    assert list(tmp_path.rglob("*.bak*")) == []

    missing = tmp_path / "does_not_exist"
    v = cj.load_view("ETH", IV, series=SERIES, root=missing)
    assert v.coverage_of(T0) == "SYMBOL_UNKNOWN"
    assert cj.lanes(root=missing) == []
    assert not missing.exists(), "a read created the store root"


# --- the collector: P13 per-asset right edge, P16 unreadable poll ---------

def _state(tmp_path, edges: dict[str, int], n=5) -> Path:
    payload = {"candidates": {"bars": {
        asset: {"t": [edge - (n - 1 - i) * IV for i in range(n)],
                "c": [100.0 + i for i in range(n)],
                "h": [101.0 + i for i in range(n)],
                "l": [99.0 + i for i in range(n)]}
        for asset, edge in edges.items()}}}
    p = tmp_path / "state.json"
    p.write_text(json.dumps(payload), encoding="utf-8")
    return p


def test_per_asset_right_edge_clamp(tmp_path):
    """MUTATION THAT MUST KILL THIS: derive committed_upto_s from the wall
    clock (or from the ring's global max) instead of THAT ASSET'S OWN
    newest cached bar.

    MEASURED LIVE on this box [K, read_at_s=1788020156.44, state.json
    mtime=1788020127.93, size=3,248,129 B]: the per-asset right edges
    spanned 586,200 s = 6.785 DAYS - AVAX at 1787433600 while LINK/MINA/
    PAXG were at 1788019800. A wall-clock right edge would claim coverage
    over ~1,950 five-minute bars per stale asset that were never observed,
    and every one of them would then read as a REAL HOLE."""
    import scripts.candle_collect as cc
    fresh_edge = T0 + 100 * IV
    stale_edge = fresh_edge - 6 * 86400 - 1200          # ~6.01 days behind
    state = _state(tmp_path, {"ETH": fresh_edge, "AVAX": stale_edge})
    root = tmp_path / "candles"
    summary = cc.collect_once(state, root, now_s=NOW)
    assert summary["poll_unreadable"] == 0
    assert summary["assets"] == 2

    lane = cj.Series("bot_cache", "USD")
    stale = cj.load_view("AVAX", IV, series=lane, root=root)
    assert stale.right_edge_s == stale_edge
    # the trailing region the stale asset never observed
    for t in (stale_edge + IV, stale_edge + 500 * IV, fresh_edge):
        assert stale.coverage_of(t) == "BEYOND_RIGHT_EDGE", t
        assert stale.coverage_of(t) != "NO_BAR_IN_COVERED_WINDOW"
    fresh = cj.load_view("ETH", IV, series=lane, root=root)
    assert fresh.right_edge_s == fresh_edge
    assert fresh.coverage_of(fresh_edge) == "OK"


def test_collector_stores_open_and_volume_as_unknown(tmp_path):
    import scripts.candle_collect as cc
    state = _state(tmp_path, {"ETH": T0 + 4 * IV})
    root = tmp_path / "candles"
    cc.collect_once(state, root, now_s=NOW)
    bar = cj.load_view("ETH", IV, series=cj.Series("bot_cache", "USD"),
                       root=root).bars(T0, T0 + 4 * IV)[0]
    assert bar.open is None and bar.volume is None
    assert bar.close is not None


def test_collector_is_idempotent(tmp_path):
    import scripts.candle_collect as cc
    state = _state(tmp_path, {"ETH": T0 + 4 * IV, "BTC": T0 + 4 * IV})
    root = tmp_path / "candles"
    cc.collect_once(state, root, now_s=NOW)
    before = _files(root)
    cc.collect_once(state, root, now_s=NOW + 7200)
    assert _files(root) == before


def test_unreadable_state_json_writes_no_coverage_row(tmp_path, monkeypatch):
    """MUTATION THAT MUST KILL THIS: write a coverage row (or an EMPTY
    observation) on the read_json -> None path.

    A coverage row for a failed poll fabricates a PERMANENT phantom hole
    into an append-only store: the slots would read "we looked and the bot
    cache had nothing" forever, when in truth the poll never happened."""
    import scripts.candle_collect as cc
    state = _state(tmp_path, {"ETH": T0 + 4 * IV})
    root = tmp_path / "candles"
    cc.collect_once(state, root, now_s=NOW)
    before = _files(root)

    monkeypatch.setattr(cc, "read_json", lambda _p: None)
    summary = cc.collect_once(state, root, now_s=NOW + 300)
    assert summary["poll_unreadable"] == 1
    assert summary["assets"] == 0
    assert _files(root) == before

    # ...and on a fresh store the unreadable poll creates nothing at all
    empty = tmp_path / "empty"
    assert cc.collect_once(state, empty, now_s=NOW)["poll_unreadable"] == 1
    assert not empty.exists()


def test_collector_only_reads_state_json(tmp_path):
    import scripts.candle_collect as cc
    state = _state(tmp_path, {"ETH": T0 + 4 * IV})
    raw = state.read_bytes()
    cc.collect_once(state, tmp_path / "candles", now_s=NOW)
    assert state.read_bytes() == raw
    assert list(tmp_path.glob("state.json.*")) == []
