"""scripts/tape_to_candles.py - trades -> committed candles, offline.

Pins the three things that would silently produce plausible-but-wrong bars:
the forming window must never be written, an empty window must never be
invented, and OHLCV must come from the trades in THAT window and no other.
"""
from __future__ import annotations

import numpy as np

from scripts import tape_to_candles as T


def _tape(t0: float, n: int, dt: float, price0: float = 100.0):
    """n trades every dt seconds; price walks up by 0.01 per trade."""
    t = t0 + np.arange(n) * dt
    p = price0 + 0.01 * np.arange(n)
    v = np.full(n, 0.5)
    return t, p, v


def test_ohlcv_comes_from_the_trades_inside_each_window_only():
    t0 = 1_787_000_000.0                      # a multiple of 300? not required
    t, p, v = _tape(t0, 400, 5.0)             # 2000 s of tape, 5 s apart
    bars, upto = T.aggregate(t, p, v, 300)
    assert bars and upto is not None
    first = bars[0]
    w = first["time"]
    inside = (t >= w) & (t < w + 300)
    assert first["open"] == p[inside][0]
    assert first["close"] == p[inside][-1]
    assert first["high"] == p[inside].max() and first["low"] == p[inside].min()
    assert abs(first["volume"] - v[inside].sum()) < 1e-9
    assert all(b["time"] % 300 == 0 for b in bars)


def test_forming_window_is_never_written_and_boundary_is_the_last_full_window():
    t0 = 1_787_000_100.0
    t, p, v = _tape(t0, 400, 5.0)
    tmax = float(t[-1])
    bars, upto = T.aggregate(t, p, v, 300)
    forming = int(tmax // 300) * 300
    assert upto == forming - 300
    assert max(b["time"] for b in bars) <= upto
    assert all(b["time"] != forming for b in bars)


def test_empty_window_produces_no_bar_not_a_flat_one():
    # t0 MUST be a window boundary for the membership asserts below; the
    # first draft used a non-multiple of 300 and blamed the code.
    t0 = 1_786_999_800.0                      # = 5_956_666 * 300
    a = np.array([t0 + 10, t0 + 20])                 # window 0 has trades
    b = np.array([t0 + 910, t0 + 920, t0 + 1300])    # window 1 empty, 2 & 3 have
    t = np.concatenate([a, b])
    p = np.full(t.size, 50.0)
    v = np.ones(t.size)
    bars, upto = T.aggregate(t, p, v, 300, tape_max_s=t0 + 1500)
    times = [x["time"] for x in bars]
    assert t0 + 300 not in times                     # the empty window is ABSENT
    assert t0 in times and t0 + 900 in times and t0 + 1200 in times


def test_empty_tape_and_too_short_tape_return_nothing():
    assert T.aggregate(np.array([]), np.array([]), np.array([]), 300) == ([], None)
    t = np.array([1_787_000_000.0, 1_787_000_050.0])   # < one full window
    assert T.aggregate(t, np.array([1.0, 2.0]), np.array([1.0, 1.0]), 300) == ([], None)


def test_unsorted_tape_is_sorted_before_aggregation():
    t0 = 1_787_000_000.0
    t, p, v = _tape(t0, 200, 5.0)
    idx = np.random.default_rng(0).permutation(t.size)
    bars_a, _ = T.aggregate(t, p, v, 300)
    bars_b, _ = T.aggregate(t[idx], p[idx], v[idx], 300)
    assert bars_a == bars_b


def test_build_asset_commits_through_the_journal_in_a_temp_root(tmp_path, monkeypatch):
    """The write must go through cj.ingest with the documented provenance and
    a boundary that excludes the forming bar. A fake store supplies the tape."""
    import pandas as pd

    t0 = 1_787_000_000.0
    t, p, v = _tape(t0, 1000, 3.0)               # 3000 s -> 9 full 300 s windows

    class FakeStore:
        def load(self, pair):
            assert pair == "XBTUSD"
            return pd.DataFrame({"time_s": t, "price": p, "volume": v})

    captured = {}

    def fake_ingest(symbol, interval_s, source, quote, bars, **kw):
        captured.update(symbol=symbol, interval_s=interval_s, source=source,
                        quote=quote, bars=bars, **kw)

        class R:                       # the journal's report shape, incl. status
            status = "OK"
            bars_offered = len(bars)
            bars_accepted = len(bars)
            bars_dup = 0
            bars_conflict = 0
            bars_rejected = 0
        return R()

    monkeypatch.setattr(T.cj, "ingest", fake_ingest)
    out = T.build_asset("BTC", 300, root=tmp_path, store=FakeStore(), now_s=1)
    assert out["status"] == "OK" and out["bars"] == captured["bars"].__len__()
    assert captured["source"] == "kraken" and captured["committed_by"] == "clock"
    assert captured["quote"] == "USD" and captured["status"] == "OK"
    assert captured["committed_upto_s"] == int(float(t[-1]) // 300) * 300 - 300
    assert captured["asked_to_s"] == captured["committed_upto_s"]
    # note is a FROZEN vocabulary in the journal; the script sends "" and the
    # real-writer pin below proves the journal accepts exactly that.
    from data import candle_journal as _cj
    assert captured["note"] == "" and captured["note"] in _cj.NOTES


def test_real_journal_accepts_the_bars_and_reads_them_back(tmp_path):
    """NO FAKE WRITER HERE, on purpose. The first live run of this script was
    refused at lane validation because `note` is a frozen vocabulary, and the
    monkeypatched pins above could not see it - a test double that supplies
    what production refuses is the exact blind spot this repo has recorded
    (vault: stated-invariants-vs-audited-reality). This pin drives the REAL
    data.candle_journal.ingest against a temp root and reads the bars back
    through the REAL reader, so a vocabulary drift in source / committed_by /
    note / quote goes red here, not in production."""
    import pandas as pd
    from data import candle_journal as cj

    t0 = 1_786_999_800.0                            # window boundary
    t, p, v = _tape(t0, 1000, 3.0)                  # 3000 s -> 9 full 300 s bars

    class FakeStore:
        def load(self, pair):
            return pd.DataFrame({"time_s": t, "price": p, "volume": v})

    out = T.build_asset("ETH", 300, root=tmp_path, store=FakeStore(), now_s=1_790_000_000)
    assert out["status"] == "OK"
    assert out["bars_accepted"] == out["bars"] and out["bars_rejected"] == 0
    series = cj.Series(source=T.SOURCE, quote=T.QUOTE)
    got = cj.bars("ETH", 300, int(t0), out["committed_upto_s"], series=series, root=tmp_path)
    assert len(got) == out["bars"]
    assert got[0].t_open_s == int(t0)
    assert got[-1].t_open_s == out["committed_upto_s"]
    # the forming window is neither written nor claimed as covered
    forming = out["committed_upto_s"] + 300
    assert cj.bars("ETH", 300, forming, forming, series=series, root=tmp_path) == []


def test_a_locked_or_zero_accept_journal_report_is_a_failure_not_a_success(monkeypatch):
    """The first live run exited 0 having written NOTHING: main() held the
    journal lock, ingest() refused against our own pid with status LOCKED and
    bars_accepted=0, and the summary line reported 190,712 bars. A refusal
    or a zero-accept batch must surface as a failure with a non-zero exit."""
    import pandas as pd
    t0 = 1_786_999_800.0
    t, p, v = _tape(t0, 1000, 3.0)

    class FakeStore:
        def load(self, pair):
            return pd.DataFrame({"time_s": t, "price": p, "volume": v})

    class Locked:
        # accepted is deliberately NON-zero here so that ONLY the status
        # branch can catch this report: the first battery had both branches
        # masking each other and two mutants survived.
        status = "LOCKED"
        bars_offered = 9
        bars_accepted = 9
        bars_dup = 0
        bars_conflict = 0
        bars_rejected = 0

    monkeypatch.setattr(T.cj, "ingest", lambda *a, **k: Locked())
    out = T.build_asset("BTC", 300, store=FakeStore(), now_s=1)
    assert out["status"] == "LOCKED" and "failure" in out
    monkeypatch.setattr(T, "TickStore", lambda: FakeStore())
    assert T.main(["--interval", "300", "--assets", "BTC"]) != 0


def test_main_does_not_hold_the_journal_lock_around_ingest(monkeypatch):
    """ingest() takes its own non-re-entrant lock; if main() wraps it, every
    call refuses. Pin: main() never calls cj.ingest_lock."""
    import pandas as pd
    calls = []
    monkeypatch.setattr(T.cj, "ingest_lock", lambda *a, **k: calls.append("LOCK") or _Never())
    t0 = 1_786_999_800.0
    t, p, v = _tape(t0, 1000, 3.0)

    class FakeStore:
        def load(self, pair):
            return pd.DataFrame({"time_s": t, "price": p, "volume": v})

    class OK:
        status = "OK"
        bars_offered = 9
        bars_accepted = 9
        bars_dup = 0
        bars_conflict = 0
        bars_rejected = 0

    monkeypatch.setattr(T.cj, "ingest", lambda *a, **k: OK())
    monkeypatch.setattr(T, "TickStore", lambda: FakeStore())
    assert T.main(["--interval", "300", "--assets", "BTC"]) == 0
    assert calls == []


class _Never:
    def __enter__(self):
        raise AssertionError("main() must not take the journal lock")

    def __exit__(self, *a):
        return False


def test_an_ok_report_that_accepted_nothing_is_a_failure(monkeypatch):
    """Isolates the zero-accept branch: status OK, nothing accepted, nothing
    duplicate. Only the accepted==0 check can catch this."""
    import pandas as pd
    t0 = 1_786_999_800.0
    t, p, v = _tape(t0, 1000, 3.0)

    class FakeStore:
        def load(self, pair):
            return pd.DataFrame({"time_s": t, "price": p, "volume": v})

    class Silent:
        status = "OK"
        bars_offered = 9
        bars_accepted = 0
        bars_dup = 0
        bars_conflict = 0
        bars_rejected = 9

    monkeypatch.setattr(T.cj, "ingest", lambda *a, **k: Silent())
    out = T.build_asset("BTC", 300, store=FakeStore(), now_s=1)
    assert out["status"] == "OK" and "failure" in out
    monkeypatch.setattr(T, "TickStore", lambda: FakeStore())
    assert T.main(["--interval", "300", "--assets", "BTC"]) != 0


# --- exception isolation (adversarial review, 2026-09-02) -----------------
# The first version had none: a NaN in one asset's tape raised uncaught out
# of aggregate(), through build_asset(), through main()'s list comprehension,
# discarding the whole batch's summary - including bars already committed
# for assets processed before the crash. Reproduced by execution before the
# fix (see the review); these pin the fix, end to end.

def test_a_malformed_tape_row_is_isolated_to_its_own_asset(monkeypatch):
    """The exact reproduction: BTC good, ETH has a NaN time_s, ADA good.
    build_asset must report CRASHED for ETH alone and never raise."""
    import pandas as pd
    t0 = 1_786_999_800.0

    def tape_for(asset):
        t, p, v = _tape(t0, 500, 3.0)
        if asset == "ETH":
            t = t.copy()
            t[-1] = np.nan            # the exact defect that killed the batch
        return pd.DataFrame({"time_s": t, "price": p, "volume": v})

    class Store:
        def load(self, pair):
            asset = {"XBTUSD": "BTC", "ETHUSD": "ETH", "ADAUSD": "ADA"}[pair]
            return tape_for(asset)

    class OK:
        status = "OK"
        bars_offered = bars_accepted = 9
        bars_dup = bars_conflict = bars_rejected = 0

    monkeypatch.setattr(T.cj, "ingest", lambda *a, **k: OK())
    store = Store()
    out_btc = T.build_asset("BTC", 300, store=store, now_s=1)
    out_eth = T.build_asset("ETH", 300, store=store, now_s=1)   # must not raise
    out_ada = T.build_asset("ADA", 300, store=store, now_s=1)
    assert out_btc["status"] == "OK" and "failure" not in out_btc
    assert out_eth["status"] == "CRASHED" and "NaN" in out_eth["failure"]
    assert out_ada["status"] == "OK" and "failure" not in out_ada


def test_main_processes_every_asset_even_when_one_crashes(monkeypatch, capsys):
    """The end-to-end pin: main() must attempt ALL assets and report a
    non-zero exit, with the good ones' status still printed - not one
    swallowed traceback and silence for everything after the crash."""
    import pandas as pd
    t0 = 1_786_999_800.0

    def tape_for(asset):
        t, p, v = _tape(t0, 500, 3.0)
        if asset == "ETH":
            t = t.copy()
            t[-1] = np.nan
        return pd.DataFrame({"time_s": t, "price": p, "volume": v})

    class Store:
        def load(self, pair):
            asset = {"XBTUSD": "BTC", "ETHUSD": "ETH", "ADAUSD": "ADA"}[pair]
            return tape_for(asset)

    class OK:
        status = "OK"
        bars_offered = bars_accepted = 9
        bars_dup = bars_conflict = bars_rejected = 0

    monkeypatch.setattr(T.cj, "ingest", lambda *a, **k: OK())
    monkeypatch.setattr(T, "TickStore", lambda: Store())
    rc = T.main(["--interval", "300", "--assets", "BTC,ETH,ADA"])
    out = capsys.readouterr().out
    assert rc != 0
    assert " BTC " in out and "status OK" in out       # BTC's line was printed
    assert " ADA " in out                              # ADA was ATTEMPTED, not skipped
    assert "CRASHED" in out and "!!" in out


def test_an_exception_from_ingest_itself_is_isolated_not_just_from_aggregate(monkeypatch):
    """The second try/except: a crash INSIDE cj.ingest (not just inside
    aggregate) must also report CRASHED with the bars it had built, not
    propagate."""
    import pandas as pd
    t0 = 1_786_999_800.0
    t, p, v = _tape(t0, 1000, 3.0)

    class FakeStore:
        def load(self, pair):
            return pd.DataFrame({"time_s": t, "price": p, "volume": v})

    def boom(*a, **k):
        raise RuntimeError("journal disk full")

    monkeypatch.setattr(T.cj, "ingest", boom)
    out = T.build_asset("BTC", 300, store=FakeStore(), now_s=1)
    assert out["status"] == "CRASHED"
    assert "journal disk full" in out["failure"]
    assert out["bars"] > 0          # the aggregation succeeded; only the commit crashed


def test_main_catches_a_crash_even_if_build_asset_itself_somehow_raises(monkeypatch, capsys):
    """Belt-and-suspenders check: build_asset() is now guarded so it never
    raises in practice, which means the two tests above never exercise
    main()'s OWN try/except around the call. This one forces build_asset
    to raise directly, so that independent layer is actually verified
    rather than merely present."""
    calls = []

    def exploding_build_asset(asset, interval_s, **kw):
        calls.append(asset)
        if asset == "ETH":
            raise RuntimeError("simulated defect INSIDE build_asset's own guard")
        return {"asset": asset, "pair": asset + "USD", "interval_s": interval_s,
                "status": "OK", "bars": 3, "bars_accepted": 3, "bars_dup": 0}

    monkeypatch.setattr(T, "build_asset", exploding_build_asset)
    monkeypatch.setattr(T, "TickStore", lambda: object())
    rc = T.main(["--interval", "300", "--assets", "BTC,ETH,ADA"])
    out = capsys.readouterr().out
    assert calls == ["BTC", "ETH", "ADA"]        # every asset was ATTEMPTED
    assert rc != 0
    assert "status OK" in out and "CRASHED" in out
