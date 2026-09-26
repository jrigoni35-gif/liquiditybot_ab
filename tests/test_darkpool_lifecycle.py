"""DarkPoolFeed connection lifecycle + staleness honesty (2026-09-26 review).

Measured defects these pin:
  * a lifetime read-only DuckDB handle blocks the external mirror writer
    (Windows) - the mirror could never refresh while the bot ran;
  * a connection invalidated after an error was retried forever, never
    reopened, even with the file healthy;
  * `data_age_days` came from a column stamped at INGEST (151 d on every
    poll 09-21..09-26) - staleness never grew with wall time;
  * a degraded snapshot kept the last live numerics under available=False.
"""
import calendar
import subprocess
import sys
import time

import pytest

duckdb = pytest.importorskip("duckdb")

from data.darkpool_feed import DarkPoolFeed  # noqa: E402

_COLS = """symbol VARCHAR, period_start DATE, period_end DATE,
           published_date DATE, ingested_at DATE, data_age_days INTEGER,
           venue_mpid VARCHAR, volume_shares BIGINT, is_complete BOOLEAN"""


def _mk_db(path):
    con = duckdb.connect(str(path))
    con.execute(f"CREATE TABLE ats_venue_weekly ({_COLS})")
    rows = []
    for ps, pe in (("2026-04-13", "2026-04-17"), ("2026-04-20", "2026-04-24")):
        for mp, v in (("MSPL", 10_000_000), ("UBSA", 8_000_000)):
            rows.append(("MSTR", ps, pe, "2026-05-02", "2026-05-02", 30, mp,
                         v, True))
    con.executemany(
        "INSERT INTO ats_venue_weekly VALUES (?,?,?,?,?,?,?,?,?)", rows)
    con.close()


def _feed(path):
    return DarkPoolFeed({"enabled": True, "poll_minutes": 0,
                         "duckdb_path": str(path),
                         "tickers": [{"symbol": "MSTR", "weight": 1.0}]})


def test_poll_releases_handle_so_external_writer_can_refresh(tmp_path):
    db = tmp_path / "dp.duckdb"
    _mk_db(db)
    f = _feed(db)
    assert f.maybe_poll(1e9).available
    rc = subprocess.run(
        [sys.executable, "-c",
         "import duckdb,sys; c=duckdb.connect(sys.argv[1]); "
         "c.execute('select 1'); c.close()", str(db)],
        capture_output=True, text=True, timeout=60)
    assert rc.returncode == 0, rc.stderr[-300:]


def test_failed_poll_reconnects_next_time(tmp_path):
    db = tmp_path / "dp.duckdb"
    _mk_db(db)
    f = _feed(db)
    assert f.maybe_poll(1e9).available
    assert f._ensure_con()
    f._con.close()                  # handle invalidated behind the feed
    assert not f.maybe_poll(1e9 + 10).available
    assert f.maybe_poll(1e9 + 20).available, "must reopen, not retry a dead handle"


def test_degraded_snapshot_carries_neutral_numerics(tmp_path):
    db = tmp_path / "dp.duckdb"
    _mk_db(db)
    f = _feed(db)
    s = f.maybe_poll(1e9)
    assert s.available and s.dp_hhi > 0
    f.db_path = str(tmp_path / "gone.duckdb")
    s = f.maybe_poll(1e9 + 10)
    assert not s.available
    assert (s.dp_surge_z, s.dp_vol_z, s.dp_hhi) == (0.0, 0.0, 0.0)


def test_data_age_grows_with_the_poll_clock(tmp_path):
    db = tmp_path / "dp.duckdb"
    _mk_db(db)
    f = _feed(db)
    end = calendar.timegm(time.strptime("2026-04-24", "%Y-%m-%d"))
    a1 = f.maybe_poll(end + 10 * 86400).data_age_days
    a2 = f.maybe_poll(end + 40 * 86400).data_age_days
    assert (a1, a2) == (10.0, 40.0)
