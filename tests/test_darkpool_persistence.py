"""Dark-pool mirror window persistence (v10, 2026-09-21).

Same hazard class as test_moomoo_persistence.py (41c): the DarkPoolFeed's
z-windows and freeze gate live in memory only, and at the bot's restart
cadence an empty rebuild would fabricate dp_surge_z/dp_vol_z back toward
neutral for weeks of publication-lagged data. to_dict/from_dict ride the
same StateStore sections as moomoo_state ("darkpool_state"), restored
BEFORE the first poll so the freeze fingerprint classifies a still-frozen
mirror without re-seeding the windows.
"""
import pytest

duckdb = pytest.importorskip("duckdb")

from data.darkpool_feed import DarkPoolFeed  # noqa: E402

_COLS = """symbol VARCHAR, period_start DATE, period_end DATE,
           published_date DATE, ingested_at DATE, data_age_days INTEGER,
           venue_mpid VARCHAR, volume_shares BIGINT, is_complete BOOLEAN"""


def _mk_con(rows) -> "duckdb.DuckDBPyConnection":
    con = duckdb.connect(":memory:")
    con.execute(f"CREATE TABLE ats_venue_weekly ({_COLS})")
    if rows:
        con.executemany(
            "INSERT INTO ats_venue_weekly VALUES (?,?,?,?,?,?,?,?,?)", rows)
    return con


def _rows(period_start: str, mult: float = 1.0) -> list:
    base = [("MSPL", 10_000_000), ("UBSA", 8_000_000), ("WCHX", 5_000_000)]
    return [
        ("MSTR", period_start, "2026-04-24", "2026-05-02", "2026-05-02",
         30, mp, int(v * mult), True)
        for mp, v in base
    ] + [
        ("COIN", period_start, "2026-04-24", "2026-05-02", "2026-05-02",
         30, mp, int(v * mult * 0.4), True)
        for mp, v in base
    ]


def _feed(con) -> DarkPoolFeed:
    return DarkPoolFeed({"enabled": True, "poll_minutes": 0,
                         "min_prior_periods": 2,
                         "tickers": [{"symbol": "MSTR", "weight": 1.0},
                                     {"symbol": "COIN", "weight": 1.0}]},
                        con=con)


def test_windows_and_freeze_state_roundtrip():
    con = _mk_con(_rows("2026-04-13") + _rows("2026-04-20"))
    f1 = _feed(con)
    s = f1._poll(1000.0)
    assert s.available and s.periods == 2 and s.dp_surge_z == 0.0
    d = f1.to_dict()
    f2 = _feed(_mk_con([]))
    f2.from_dict(d)
    assert list(f2._surge_hist) == list(f1._surge_hist)
    assert list(f2._vol_hist) == list(f1._vol_hist)
    assert f2._last_per == f1._last_per
    assert f2.to_dict() == d               # stable fixed point


def test_identical_week_does_not_reenter_z_windows():
    """DF-010 analog: weekly rows repeat between publications, so a
    full-repeat poll must not append to the z windows."""
    con = _mk_con(_rows("2026-04-13") + _rows("2026-04-20"))
    f = _feed(con)
    f._poll(1000.0)
    n = len(f._surge_hist)
    s = f._poll(2000.0)                    # identical data -> frozen
    assert s.dp_frozen is True
    assert len(f._surge_hist) == n, "no z-window append on a repeat poll"


def test_new_publication_appends_normally():
    con = _mk_con(_rows("2026-04-13") + _rows("2026-04-20"))
    f = _feed(con)
    f._poll(1000.0)
    con.executemany(                       # next weekly publication lands
        "INSERT INTO ats_venue_weekly VALUES (?,?,?,?,?,?,?,?,?)",
        _rows("2026-04-27", mult=2.0))
    s = f._poll(2000.0)
    assert s.dp_frozen is False
    assert len(f._surge_hist) == 2
    # z stays 0.0 by design until >=8 observations; the fresh publication
    # shows up in the raw surge ratio and the concentration mean instead
    assert s.per_ticker["MSTR"]["surge_ratio"] == 2.0
    assert s.dp_hhi != 0.0


def test_malformed_section_leaves_clean_boot_state():
    f = _feed(_mk_con([]))
    f.from_dict({"surge_hist": ["nan-value"], "last_per": 7})
    assert list(f._surge_hist) == [] and f._last_per == {}
    assert f._frozen is False
    f.from_dict("garbage")                 # type: ignore[arg-type]
    assert list(f._surge_hist) == []


def test_statestore_carries_darkpool_section(tmp_path):
    """Through the REAL snapshot()/restore(): the section must survive,
    and a bot WITHOUT a darkpool attr (runner-state double convention)
    must still snapshot an empty section."""
    from types import SimpleNamespace

    from core.persistence import StateStore

    f1 = _feed(_mk_con(_rows("2026-04-13") + _rows("2026-04-20")))
    f1._poll(1000.0)

    import tests.test_gate_components as tgc
    hs = tgc._mk_store(tmp_path / "src")
    bot = tgc._persist_stub_bot(hs)
    bot.darkpool = f1
    store = StateStore(str(tmp_path / "state.json"))
    assert store.snapshot(bot)

    f2 = _feed(_mk_con([]))
    hs2 = tgc._mk_store(tmp_path / "dst")
    revived = tgc._persist_stub_bot(hs2)
    revived.darkpool = f2
    assert store.restore(revived)
    assert list(f2._surge_hist) == list(f1._surge_hist)
    assert f2._last_per == f1._last_per

    # bot without any darkpool attr: section writes {} via the getattr guard
    bot2 = tgc._persist_stub_bot(tgc._mk_store(tmp_path / "src2"))
    bot2.darkpool = SimpleNamespace(close=lambda: None)
    assert store.snapshot(bot2)


def test_degraded_mirror_reports_unavailable():
    """Empty table -> poll raises -> snapshot degrades to the unavailable
    contract (flags cleared, ts NOT advanced, neutrals already 0.0)."""
    f = _feed(_mk_con([]))
    s = f.maybe_poll(1000.0)
    assert s.available is False
    assert s.dp_frozen is False and s.is_complete is False
