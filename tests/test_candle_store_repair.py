"""Pins for the candle store's REPAIR and OPERATOR paths.

Everything here defends a boundary the append-only rules alone do not
cover: the one tool that rewrites an existing byte, the escape hatch out of
a wedged store, the published inventory that can go stale or be forged, the
credential blast radius of an analysis script, and the memory bound the
window index claims.

A test here is accepted only with mutation-kill evidence recorded in the
commit message. Every test passes an explicit root=tmp_path; nothing here
can reach the operator's live tree.
"""
from __future__ import annotations

import csv
import json
import tracemalloc
from pathlib import Path

import pytest

from data import candle_journal as cj

IV = 300
T0 = 1787800000 - (1787800000 % IV)
SERIES = cj.Series("kraken", "USD")
NOW = 1787900000


def _bars(n, start=T0, step=IV, base=100.0):
    return [{"time": start + i * step, "open": base, "high": base + 2.0,
             "low": base - 2.0, "close": base, "volume": 1.0}
            for i in range(n)]


def _ingest(root, bars, *, symbol="ETH", committed_upto=None, asked_from=T0,
            asked_to=None, now_s=NOW):
    times = [b["time"] for b in bars if isinstance(b.get("time"), int)]
    if committed_upto is None:
        committed_upto = max(times) if times else T0
    if asked_to is None:
        asked_to = committed_upto
    return cj.ingest(symbol, IV, "kraken", "USD", bars,
                     committed_upto_s=committed_upto,
                     committed_by="venue_last", asked_from_s=asked_from,
                     asked_to_s=asked_to, status="OK", now_s=now_s, root=root)


def _files(root: Path) -> dict[Path, bytes]:
    return {p: p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


def _seed_conflict(root):
    base = {"time": T0, "open": 100.0, "high": 102.0, "low": 98.0,
            "close": 100.0, "volume": 1.0}
    _ingest(root, [base], committed_upto=T0, asked_from=T0, asked_to=T0)
    rep = _ingest(root, [{**base, "close": 101.0}], committed_upto=T0,
                  asked_from=T0, asked_to=T0, now_s=NOW + 5)
    assert rep.bars_conflict == 1
    return base


# --- P31 the one path that rewrites a byte takes the writer's lock --------

def test_resolve_refuses_while_the_ingest_lock_is_held(tmp_path, capsys):
    """MUTATION THAT MUST KILL THIS: remove the cj.ingest_lock wrapper from
    resolve(), or make it proceed when the lock is held.

    scripts/candle_store_resolve.py calls itself "THE ONE PATH IN THIS BUILD
    THAT REWRITES AN EXISTING BYTE" and took no lock at all, so any append
    landing between its read and its os.replace was destroyed - silently,
    exit 0. The collector polls every 5 minutes BY DESIGN and its bars are
    not re-acquirable; the .preschema_ backup is taken before the concurrent
    append and so holds neither copy; and coverage/ is a different file that
    is never rewritten, so the destroyed slots came back as
    NO_BAR_IN_COVERED_WINDOW - the store asserting the venue had no data for
    bars it held thirty seconds earlier."""
    import scripts.candle_store_resolve as res
    _seed_conflict(tmp_path)
    before = _files(tmp_path)

    lock = cj._IngestLock(tmp_path)
    assert lock.acquire() is True
    try:
        rc = res.resolve(tmp_path, accept="latest", apply=True)
    finally:
        lock.release()
    assert rc == 1, "resolve proceeded while the lock was held"
    assert _files(tmp_path) == before, "resolve wrote under a held lock"
    assert "REFUSED" in capsys.readouterr().out
    # it never steals: the lock is still there for its owner
    assert cj.lock_path(tmp_path).exists() is False   # released by us above

    # ...and with the lock free it works
    assert res.resolve(tmp_path, accept="latest", apply=True) == 0
    view = cj.load_view("ETH", IV, series=SERIES, root=tmp_path)
    assert view.bars(T0, T0)[0].close == 101.0


def test_a_concurrent_append_survives_a_resolve(tmp_path):
    """THE RACE ITSELF, deterministically interleaved.

    The collector's ingest is fired from inside _rewrite's read->replace
    window (patched at shutil.copy2, exactly where the original defect was
    measured). With the lock in place that ingest must REFUSE rather than be
    silently overwritten - and the bars must still be absent-because-refused
    (NOT_COVERED / re-poll-able), never present-then-destroyed."""
    import scripts.candle_store_resolve as res
    _seed_conflict(tmp_path)
    fired = {}
    real_copy = res.shutil.copy2

    def racing_copy(src, dst):
        out = real_copy(src, dst)
        rep = _ingest(tmp_path, _bars(3, start=T0 + 10 * IV),
                      committed_upto=T0 + 12 * IV, asked_from=T0 + 10 * IV,
                      asked_to=T0 + 12 * IV, now_s=NOW + 9)
        fired["status"] = rep.status
        fired["accepted"] = rep.bars_accepted
        return out

    monkey = res.shutil.copy2
    res.shutil.copy2 = racing_copy
    try:
        assert res.resolve(tmp_path, accept="latest", apply=True) == 0
    finally:
        res.shutil.copy2 = monkey

    assert fired["status"] == "LOCKED", (
        "the concurrent writer was NOT held off - its bars were in the "
        "read->replace window and would have been destroyed")
    assert fired["accepted"] == 0
    view = cj.load_view("ETH", IV, series=SERIES, root=tmp_path)
    for k in (10, 11, 12):
        # refused, therefore never claimed - and therefore re-poll-able
        assert view.coverage_of(T0 + k * IV) != "NO_BAR_IN_COVERED_WINDOW"
    # and the refused poll lands cleanly afterwards
    again = _ingest(tmp_path, _bars(3, start=T0 + 10 * IV),
                    committed_upto=T0 + 12 * IV, asked_from=T0 + 10 * IV,
                    asked_to=T0 + 12 * IV, now_s=NOW + 99)
    assert again.bars_accepted == 3


def test_resolve_backup_and_tmp_names_are_pid_scoped(tmp_path):
    """Two rewrites in the same second clobbered the same backup, and the
    docstring's "PID-scoped tmp" claim was copied from the other file and
    was untrue here. A claim in a permanent file is a claim."""
    import scripts.candle_store_resolve as res
    src = (Path(res.__file__)).read_text(encoding="utf-8")
    assert "os.getpid()" in src
    _seed_conflict(tmp_path)
    res.resolve(tmp_path, accept="latest", apply=True)
    backups = list((tmp_path / "journal").glob("*.preschema_*"))
    assert len(backups) == 1
    assert str(backups[0]).count("_") >= 2, backups[0].name
    assert list((tmp_path / "journal").glob("*.tmp")) == []


# --- P32 the escape hatch out of a wedged store ---------------------------

def test_a_torn_record_wedges_the_whole_store_and_quarantine_frees_it(
        tmp_path):
    """MUTATION THAT MUST KILL THIS: have quarantine() skip the ingest lock,
    or delete the fragment instead of moving it to a sidecar.

    Segments are named for the month of INGEST, so every lane shares one
    file: ONE kill-torn record makes every symbol, interval, source and
    quote answer STORE_UNREADABLE, and ingest() then refuses everything -
    correct, and terminal, because durable_append's "the reader skips the
    junk line" recovery is deliberately unavailable here. Meanwhile the 5m
    lane and Kraken's 720-bar cap mean the wedge window is not
    re-acquirable, so "resolve by hand" is a race against data loss."""
    pytest.importorskip("polars")
    import scripts.candle_store as cs
    _ingest(tmp_path, _bars(6), committed_upto=T0 + 5 * IV, asked_from=T0,
            asked_to=T0 + 5 * IV)
    cj.ingest("BTC", 86400, "okx", "USDT",
              [{"time": T0 - (T0 % 86400) + i * 86400, "open": 200.0,
                "high": 202.0, "low": 198.0, "close": 200.0, "volume": 1.0}
               for i in range(5)],
              committed_upto_s=T0 - (T0 % 86400) + 4 * 86400,
              committed_by="venue_confirm", asked_from_s=None,
              asked_to_s=None, now_s=NOW + 1, root=tmp_path)
    healthy_rows = cs.verify(tmp_path).bar_rows
    assert healthy_rows == 11

    seg = next((tmp_path / "journal").glob("*.csv"))
    seg.write_bytes(seg.read_bytes()[:-14])          # a kill-torn tail

    # THE BLAST RADIUS: an untouched lane dies too
    other = cj.load_view("BTC", 86400, series=cj.Series("okx", "USDT"),
                         root=tmp_path)
    assert other.coverage_of(T0 - (T0 % 86400)) == "STORE_UNREADABLE"
    assert cs.verify(tmp_path).ok is False
    with pytest.raises(cj.CandleStoreUnreadable):
        _ingest(tmp_path, _bars(2, start=T0 + 20 * IV),
                committed_upto=T0 + 21 * IV, asked_from=T0 + 20 * IV,
                asked_to=T0 + 21 * IV, now_s=NOW + 60)

    # DRY RUN NAMES IT AND WRITES NOTHING
    before = _files(tmp_path)
    names_before = set(tmp_path.rglob("*"))
    dry = cs.quarantine(tmp_path)
    assert dry.ok and dry.applied is False
    assert dry.records_quarantined == 1
    assert _files(tmp_path) == before
    # a dry run creates NOTHING - not even the lock file (P8: reading
    # creates nothing, and a report is a read)
    assert set(tmp_path.rglob("*")) == names_before
    assert not cj.lock_path(tmp_path).exists()

    # APPLY moves the fragment to a sidecar and frees the store
    rep = cs.quarantine(tmp_path, apply=True)
    assert rep.ok and rep.applied and rep.records_quarantined == 1
    assert len(rep.sidecars) == 1
    sidecar = next((tmp_path / "quarantine").glob("*.quarantine_*.csv"))
    kept = list(csv.DictReader(sidecar.open(encoding="utf-8", newline="")))
    assert len(kept) == 1, "the fragment was deleted rather than preserved"
    assert kept[0]["source_segment"] == seg.name
    # the sidecar must NOT sit inside a ledger directory: a stray *.csv
    # there is a segment by definition and would re-wedge the store
    assert list((tmp_path / "journal").glob("*.quarantine*")) == []

    after = cs.verify(tmp_path)
    assert after.ok is True
    assert after.bar_rows == healthy_rows - 1, "exactly one record excised"
    resumed = _ingest(tmp_path, _bars(2, start=T0 + 20 * IV),
                      committed_upto=T0 + 21 * IV, asked_from=T0 + 20 * IV,
                      asked_to=T0 + 21 * IV, now_s=NOW + 120)
    assert resumed.status == "OK" and resumed.bars_accepted == 2


def test_quarantine_refuses_while_the_ingest_lock_is_held(tmp_path):
    import scripts.candle_store as cs
    _ingest(tmp_path, _bars(3), committed_upto=T0 + 2 * IV, asked_from=T0,
            asked_to=T0 + 2 * IV)
    seg = next((tmp_path / "journal").glob("*.csv"))
    seg.write_bytes(seg.read_bytes()[:-14])
    before = _files(tmp_path)
    lock = cj._IngestLock(tmp_path)
    assert lock.acquire() is True
    try:
        rep = cs.quarantine(tmp_path, apply=True)
    finally:
        lock.release()
    assert rep.ok is False and "lock" in rep.fault
    assert _files(tmp_path) == before


def test_quarantine_refuses_a_header_it_does_not_recognise(tmp_path):
    """It never guesses. A wrong header means we do not know what any of
    the columns mean, so the segment is left completely alone."""
    import scripts.candle_store as cs
    _ingest(tmp_path, _bars(3), committed_upto=T0 + 2 * IV, asked_from=T0,
            asked_to=T0 + 2 * IV)
    seg = next((tmp_path / "journal").glob("*.csv"))
    seg.write_bytes(b"not,a,schema\r\n1,2,3\r\n")
    before = _files(tmp_path)
    rep = cs.quarantine(tmp_path, apply=True)
    assert rep.ok is False and "header" in rep.fault
    assert _files(tmp_path) == before


def test_quarantine_also_frees_a_store_wedged_by_a_hand_written_row(tmp_path):
    """The read-path vocabulary check makes a traversal row wedge the store
    (correctly). Quarantine is the way out of that too."""
    import scripts.candle_store as cs
    _ingest(tmp_path, _bars(3), committed_upto=T0 + 2 * IV, asked_from=T0,
            asked_to=T0 + 2 * IV)
    seg = next((tmp_path / "journal").glob("*.csv"))
    with open(seg, "a", encoding="utf-8", newline="") as f:
        csv.writer(f).writerow([1, "BAR", r"..\..\ESCAPED", IV, "kraken",
                                "USD", T0 + 9 * IV, "100", "101", "99",
                                "100", "1", "venue_last", NOW])
    with pytest.raises(cj.CandleStoreUnreadable):
        list(cj._iter_bar_rows(tmp_path))
    rep = cs.quarantine(tmp_path, apply=True)
    assert rep.ok and rep.records_quarantined == 1
    assert len(list(cj._iter_bar_rows(tmp_path))) == 3
    assert any("ESCAPED" in d for d in rep.details)


def test_quarantine_on_a_healthy_store_is_a_no_op(tmp_path):
    import scripts.candle_store as cs
    _ingest(tmp_path, _bars(5), committed_upto=T0 + 4 * IV, asked_from=T0,
            asked_to=T0 + 4 * IV)
    before = _files(tmp_path)
    rep = cs.quarantine(tmp_path, apply=True)
    assert rep.ok and rep.records_quarantined == 0
    assert rep.records_kept >= 5
    assert _files(tmp_path) == before


# --- P33 the published inventory is BOUND to the bytes it describes -------

def test_lanes_does_not_serve_a_stale_manifest(tmp_path):
    """MUTATION THAT MUST KILL THIS: drop the `segment_shas` comparison from
    lanes(), or stop writing segment_shas in compact().

    Compact once, then collect or backfill - the DOCUMENTED order, since the
    collector runs continuously and compaction is manual - and lanes()
    served the old rows / t_min_s / t_max_s with no freshness marker, while
    verify() printed that stale lane count beside FRESH bar_rows. t_max_s is
    precisely the field scripts/candle_backfill.py's delisted-pair rule
    tells an operator to trust over the row count."""
    pytest.importorskip("polars")
    import scripts.candle_store as cs
    _ingest(tmp_path, _bars(3), committed_upto=T0 + 2 * IV, asked_from=T0,
            asked_to=T0 + 2 * IV)
    cs.compact(tmp_path, full=True)
    assert cj.lanes(root=tmp_path)[0]["rows"] == 3
    assert cj.lanes(root=tmp_path, prefer_manifest=True)[0]["rows"] == 3
    assert cs.verify(tmp_path).manifest_stale is False

    _ingest(tmp_path, _bars(60), committed_upto=T0 + 59 * IV, asked_from=T0,
            asked_to=T0 + 59 * IV, now_s=NOW + 60)
    rows = cj.lanes(root=tmp_path)
    assert rows[0]["rows"] == 60, "lanes() served a stale manifest"
    assert rows[0]["t_max_s"] == T0 + 59 * IV
    # even the OPT-IN fast path refuses a manifest the bytes have outrun
    assert cj.lanes(root=tmp_path, prefer_manifest=True)[0]["rows"] == 60
    rep = cs.verify(tmp_path)
    assert rep.manifest_stale is True
    assert rep.lanes == 1 and rep.bar_rows == 60

    cs.compact(tmp_path, full=True)
    assert cs.verify(tmp_path).manifest_stale is False


def test_a_forged_manifest_inventory_is_not_served(tmp_path):
    """MUTATION THAT MUST KILL THIS: default `prefer_manifest` back to True.

    MANIFEST.json is a plain file in the store root with nothing binding it
    to the journal, and its `lanes` array was served verbatim: a rewritten
    inventory claiming 74 lanes of 999,999 rows passed while `verify`
    reported ok:true, deep_matches:true - the digests are computed from the
    journal and stayed correct, so ONLY the inventory lied and nothing in
    the output distinguished the two. The sha binding catches divergence
    from the ledgers, but cannot vouch for an array replaced in place while
    the segments are untouched, so the journal derivation is the default and
    the fast path is opt-in."""
    pytest.importorskip("polars")
    import scripts.candle_store as cs
    _ingest(tmp_path, _bars(3), committed_upto=T0 + 2 * IV, asked_from=T0,
            asked_to=T0 + 2 * IV)
    cs.compact(tmp_path, full=True)
    mpath = cj.manifest_path(tmp_path)
    man = json.loads(mpath.read_text(encoding="utf-8"))
    # forged IN PLACE: segment_shas left intact, so only the array lies
    assert man["segment_shas"] == cj.segment_shas(tmp_path)
    man["lanes"] = [{"symbol": f"FAKE{i}", "interval_s": 3600,
                     "source": "kraken", "quote": "USD", "rows": 999999}
                    for i in range(74)]
    mpath.write_text(json.dumps(man), encoding="utf-8")

    rows = cj.lanes(root=tmp_path)
    assert [r["symbol"] for r in rows] == ["ETH"], rows
    assert rows[0]["rows"] == 3
    rep = cs.verify(tmp_path)
    assert rep.lanes == 1, "verify served a forged lane count"
    assert rep.manifest_stale is False       # the BYTES did not change
    # and the opt-in fast path is the only route to the forged array
    assert len(cj.lanes(root=tmp_path, prefer_manifest=True)) == 74


def test_lanes_still_uses_the_manifest_when_it_matches(tmp_path):
    """The fast path is kept, not deleted - it is opt-in and bound."""
    pytest.importorskip("polars")
    import scripts.candle_store as cs
    _ingest(tmp_path, _bars(3), committed_upto=T0 + 2 * IV, asked_from=T0,
            asked_to=T0 + 2 * IV)
    cs.compact(tmp_path, full=True)
    man = json.loads(cj.manifest_path(tmp_path).read_text(encoding="utf-8"))
    assert man["segment_shas"] == cj.segment_shas(tmp_path)
    marked = [{**r, "rows": r["rows"], "_from_manifest": True}
              for r in man["lanes"]]
    man["lanes"] = marked
    cj.manifest_path(tmp_path).write_text(json.dumps(man), encoding="utf-8")
    assert cj.lanes(root=tmp_path, prefer_manifest=True)[0].get(
        "_from_manifest") is True
    # ...and the DEFAULT never touches it
    assert cj.lanes(root=tmp_path)[0].get("_from_manifest") is None


# --- P26 the window index is bounded by the WINDOW, not the store ---------

def test_window_index_memory_is_bounded_by_the_window(tmp_path):
    """MUTATION THAT MUST KILL THIS: make _read_segment materialise its rows
    (`rows = list(csv.reader(f))`) again.

    _window_index's docstring claimed "Memory is O(window), not O(store)".
    MEASURED against the live 8.9 MB journal before the fix: a ONE-BAR
    window lookup peaked at 110.1 MB and 1.57 s - byte-identical to a full
    pass, which is the direct measurement that the window bound did nothing.
    The collector re-pays this every 300 s per asset over an append-only
    store that only grows, so the total work is quadratic in store size
    while the poll interval is fixed.

    The bound below is generous on purpose (a pin is not a benchmark); a
    materialising reader on this fixture exceeds it several times over."""
    rows = 40_000
    seg = tmp_path / "journal" / cj.segment_name(NOW)
    seg.parent.mkdir(parents=True, exist_ok=True)
    with open(seg, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(cj.BAR_COLUMNS)
        for i in range(rows):
            w.writerow([1, "BAR", "ETH", IV, "kraken", "USD",
                        T0 + i * IV, "100", "102", "98", "100", "1",
                        "venue_last", NOW])
    size = seg.stat().st_size
    assert size > 2_000_000, size

    tracemalloc.start()
    values, conflicts = cj._window_index(tmp_path, "ETH", IV, "kraken", "USD",
                                         T0, T0)
    peak = tracemalloc.get_traced_memory()[1]
    tracemalloc.stop()
    assert len(values) == 1 and conflicts == {}
    assert peak < size // 4, (
        f"a one-bar window peaked at {peak / 2**20:.1f} MB against a "
        f"{size / 2**20:.1f} MB segment - the reader is materialising")


def test_read_segment_is_a_generator_not_a_list(tmp_path):
    """The structural half of the same pin, so the bound above cannot be
    satisfied by a coincidence of fixture size."""
    import inspect
    assert inspect.isgeneratorfunction(cj._read_segment)


# --- P34 an analysis script holds no credential --------------------------

def test_candle_backfill_builds_a_credential_free_client(monkeypatch):
    """MUTATION THAT MUST KILL THIS: drop the _strip_credentials call from
    build_feed.

    build_feed's comment said "No credential keys are passed: every endpoint
    this script touches is public" - true of the dict it passes, false of
    the object it gets. KrakenFeed.__init__ resolves api_key/api_secret from
    the ENVIRONMENT irrespective of the config handed to it, and on the
    operator box those are set, so this analysis process held a live,
    signing-capable client exposing _private_post and the cancel/open-order
    calls. Nothing calls them; the defect is that the SAFE classification
    rested on prose, leaving a comment as the only guardrail against a
    future edit or a repr in a crash log. THIS TEST FAILED BEFORE THE FIX."""
    import scripts.candle_backfill as bf
    monkeypatch.setenv("KRAKEN_API_KEY", "AKIA-TEST-KEY-NOT-REAL")
    monkeypatch.setenv("KRAKEN_API_SECRET", "dGVzdHNlY3JldA==")
    feed = bf.build_feed("kraken", {})
    assert feed.api_key == ""
    assert feed.api_secret == ""
    # the config route is blanked too, not just the env one
    feed2 = bf.build_feed("kraken", {"exchanges": {"kraken": {
        "api_key": "literal-key", "api_secret": "dGVzdHNlY3JldA=="}}})
    assert feed2.api_key == "" and feed2.api_secret == ""


def test_the_env_route_is_real_so_the_pin_is_not_vacuous(monkeypatch):
    """SEPARATE "0 findings" FROM "the scan is broken": show that the
    unstripped constructor DOES pick the credential up, so the assertion
    above is testing something."""
    monkeypatch.setenv("KRAKEN_API_KEY", "AKIA-TEST-KEY-NOT-REAL")
    monkeypatch.setenv("KRAKEN_API_SECRET", "dGVzdHNlY3JldA==")
    from data.kraken_feed import KrakenFeed
    raw = KrakenFeed({"rate_limit_per_sec": 3})
    assert raw.api_key == "AKIA-TEST-KEY-NOT-REAL"
    assert raw.api_secret != ""


# --- the new ledger never collides with a runner-owned path ---------------

def test_the_reject_ledger_lives_inside_the_store_root(tmp_path):
    root = cj.store_root(tmp_path)
    p = cj.reject_dir(tmp_path)
    assert str(p).startswith(str(root))
    for owned in ("status.json", "audit.jsonl", "signal_history.csv",
                  "fills.csv", "state.json", "runner.lock"):
        assert p != root.parent / owned
    # and reading never creates it
    cj.load_view("ETH", IV, series=SERIES, root=tmp_path)
    assert not p.exists()
