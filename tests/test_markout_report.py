"""Planted-defect pins for scripts/markout_report.py.

Every test here plants a KNOWN geometry and asserts the number the report
must produce from it, so a broken sign, denominator, SE deflation, skip
accounting or tick lookup goes red rather than merely different. Mutation
evidence for each is recorded in the promoting commit.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from scripts import markout_report as mr

HEADER = ("ts,order_id,position_id,purpose,symbol,side,ordertype,post_only,attempt,"
          "fill_size,fill_price,arrival_ref,slip_bps,fees_delta_usd,remaining,reason,exec_era")
T0 = 1_780_000_000 - (1_780_000_000 % 3600)     # an aligned hour boundary
N_BARS = 200


def _bar_ts(k: int) -> float:
    """A fill 10s before bar k opens -> bar k is 'the first bar opening at
    or after the fill' by the report's definition."""
    return T0 + k * 3600 - 10.0


def write_candles(candle_dir: Path, sym: str, closes, source: str = "kraken",
                  t0: int = T0) -> None:
    candle_dir.mkdir(parents=True, exist_ok=True)
    rows = [{"schema_version": "1", "record_kind": "BAR", "symbol": sym,
             "interval_s": "3600", "source": source, "quote": "USD",
             "t_open_s": str(t0 + k * 3600), "open": str(c), "high": str(c),
             "low": str(c), "close": str(c), "volume": "1",
             "committed_by": "venue_last", "ingest_s": "0"}
            for k, c in enumerate(closes)]
    path = candle_dir / f"{sym}_3600.parquet"
    if path.exists():                       # second lane for the same symbol
        rows = pd.read_parquet(path).to_dict("records") + rows
    pd.DataFrame(rows).astype(str).to_parquet(path, index=False)


def fill_row(ts: float, symbol: str, side: str, fill_price: float, arrival_ref,
             post_only: str = "1", size: str = "0.01", era: str = "",
             slip: str = "0.0") -> str:
    return (f"{ts:.3f},oid,pid,entry,{symbol},{side},limit,{post_only},0,{size},"
            f"{fill_price},{arrival_ref},{slip},0.0,0.0,,{era}")


def write_fills(path: Path, rows) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join([HEADER, *rows]) + "\n", encoding="utf-8")


@pytest.fixture
def root(tmp_path: Path) -> Path:
    (tmp_path / "outputs" / "candles" / "parquet").mkdir(parents=True)
    return tmp_path


def _step_series(steps: dict[int, float], base: float = 100.0):
    """closes flat at base, multiplied by (1+step) from each step bar on."""
    c = np.full(N_BARS, base, dtype=float)
    for k, pct in sorted(steps.items()):
        c[k:] *= (1.0 + pct)
    return [f"{v:.6f}" for v in c]


# --- (a) sign convention + placebo ------------------------------------------

def test_planted_20bps_move_after_every_entry_and_flat_placebo(root: Path):
    # buy at bar 50 -> price steps UP 20bps; sell at bar 120 -> steps DOWN 20bps
    closes = _step_series({50: +0.002, 120: -0.002})
    write_candles(root / "outputs/candles/parquet", "ETH", closes)
    ref_buy, ref_sell = 100.0, float(closes[100])
    write_fills(root / "outputs/fills.csv", [
        fill_row(_bar_ts(50), "ETH/USD", "buy", ref_buy, ref_buy),
        fill_row(_bar_ts(120), "ETH/USD", "sell", ref_sell, ref_sell),
    ])
    rep = mr.build_report(root=root)
    assert rep["scored"] == 2 and rep["skipped"] == {"no_ref": 0, "no_bar": 0}
    _, entries = mr.load_fills(root / "outputs/fills.csv")
    rows, _ = mr.score_fills(entries, mr.load_lanes(root / "outputs/candles/parquet"))
    for r in rows:
        for h in mr.HORIZONS:
            assert r[h] == pytest.approx(20.0, abs=1e-6), (r["side"], h, r[h])
            assert r["fill_" + h] == pytest.approx(20.0, abs=1e-6)
        # placebo: the shifted windows never straddle the step at 1h/4h
        for sh in mr.PLACEBO_SHIFTS:
            for h in ("1h", "4h"):
                assert r[f"pl{sh:+d}_{h}"] == pytest.approx(0.0, abs=1e-9), (r["side"], sh, h)
    all_line = rep["arrival_markout"][0]
    assert all_line["tag"] == "ALL entries" and all_line["n"] == 2
    assert all_line["stats"]["1h"]["mean"] == pytest.approx(20.0, abs=1e-6)
    for g in rep["placebo"]:
        assert g["n"] == 2
        assert g["stats"]["1h"]["mean"] == pytest.approx(0.0, abs=1e-9)
    # the placebo's SE deflation uses the SHIFTED hour set
    assert all(g["hrs"] == 2 for g in rep["placebo"])


def test_placebo_reference_is_close_of_bar_before_shifted_index(root: Path):
    # step at bar 56 = fill bar 50 shifted +6. The +6 placebo's reference
    # must be close[55] (pre-step) so its 1h reads +20; a look-ahead
    # reference close[56] would read 0. The REAL 1h/4h windows (bars 50,
    # 50..53) sit before the step and must read 0.
    closes = _step_series({56: +0.002})
    write_candles(root / "outputs/candles/parquet", "ETH", closes)
    write_fills(root / "outputs/fills.csv",
                [fill_row(_bar_ts(50), "ETH/USD", "buy", 100.0, 100.0)])
    _, entries = mr.load_fills(root / "outputs/fills.csv")
    rows, _ = mr.score_fills(entries, mr.load_lanes(root / "outputs/candles/parquet"))
    r = rows[0]
    assert r["1h"] == pytest.approx(0.0, abs=1e-9)
    assert r["4h"] == pytest.approx(0.0, abs=1e-9)
    assert r["24h"] == pytest.approx(20.0, abs=1e-6)
    assert r["pl+6_1h"] == pytest.approx(20.0, abs=1e-6)
    assert r["pl+6_4h"] == pytest.approx(20.0, abs=1e-6)
    assert r["pl-6_1h"] == pytest.approx(0.0, abs=1e-9)


# --- (b) arrival->fill denominator + sign --------------------------------------

def test_arrival_ref_10bps_above_fill_on_buy_is_minus_10_exactly(root: Path):
    write_candles(root / "outputs/candles/parquet", "BTC", _step_series({}))
    # ref 100, fill 99.9: the buy filled 10bps BELOW arrival -> +10 for us
    # in price terms, but arr2fill is signed (fill - ref)/ref -> -10.
    write_fills(root / "outputs/fills.csv",
                [fill_row(_bar_ts(40), "BTC/USD", "buy", 99.9, 100.0)])
    _, entries = mr.load_fills(root / "outputs/fills.csv")
    rows, skipped = mr.score_fills(entries, mr.load_lanes(root / "outputs/candles/parquet"))
    assert len(rows) == 1 and skipped["no_bar"] == 0
    assert rows[0]["arr2fill"] == pytest.approx(-10.0, abs=1e-6)
    # and the fill-referenced horizon differs from the arrival one by that
    # distance (the decomposition identity, up to the denominator)
    assert rows[0]["1h"] == pytest.approx(0.0, abs=1e-6)
    assert rows[0]["fill_1h"] == pytest.approx((100.0 - 99.9) / 99.9 * 1e4, abs=1e-6)


# --- (c) skip accounting + lane preference -------------------------------------

def test_uncovered_fills_are_counted_not_dropped(root: Path):
    cd = root / "outputs/candles/parquet"
    write_candles(cd, "ETH", _step_series({}))
    # a lane that is too short to cover anything, plus a full second lane
    write_candles(cd, "SOL", ["50.0"] * 20, source="kraken")
    write_candles(cd, "SOL", ["50.0"] * N_BARS, source="binanceus")
    write_fills(root / "outputs/fills.csv", [
        fill_row(_bar_ts(40), "ETH/USD", "buy", 100.0, 100.0),                 # scored
        fill_row(_bar_ts(N_BARS - 5), "ETH/USD", "buy", 100.0, 100.0),         # inside last 30 bars
        fill_row(_bar_ts(40), "ETH/USD", "buy", 100.0, ""),                    # no arrival_ref
        fill_row(_bar_ts(40), "XRP/USD", "buy", 1.0, 1.0),                     # no lane at all
        fill_row(_bar_ts(40), "SOL/USD", "sell", 50.0, 50.0),                  # falls through to binanceus
        fill_row(_bar_ts(40), "ETH/USD", "buy", 100.0, 100.0, size="0"),       # not an entry fill
    ])
    rep = mr.build_report(root=root)
    assert rep["entries_with_size"] == 5
    assert rep["scored"] == 2
    assert rep["skipped"] == {"no_ref": 1, "no_bar": 2}
    assert rep["scored"] + sum(rep["skipped"].values()) == rep["entries_with_size"]
    assert rep["skipped_no_bar_near_right_edge"] == 1
    assert rep["lanes_used"] == {"kraken": 1, "binanceus": 1, "okx": 0}


# --- (d) SE denominator = distinct hours ----------------------------------------

def test_se_deflates_to_distinct_hours_not_rows():
    same_hour = [{"hour": 7, "v": 10.0}, {"hour": 7, "v": 30.0}]
    diff_hour = [{"hour": 7, "v": 10.0}, {"hour": 8, "v": 30.0}]
    g1 = mr.group_stats(same_hour, ["v"])
    g2 = mr.group_stats(diff_hour, ["v"])
    sd = np.std([10.0, 30.0], ddof=1)
    assert g1["n"] == 2 and g1["hrs"] == 1
    assert g2["n"] == 2 and g2["hrs"] == 2
    assert g1["stats"]["v"]["se"] == pytest.approx(sd / np.sqrt(1))
    assert g2["stats"]["v"]["se"] == pytest.approx(sd / np.sqrt(2))
    assert g1["stats"]["v"]["se"] / g2["stats"]["v"]["se"] == pytest.approx(np.sqrt(2))


def test_two_fills_in_one_hour_report_hrs_1_end_to_end(root: Path):
    write_candles(root / "outputs/candles/parquet", "ETH", _step_series({}))
    write_fills(root / "outputs/fills.csv", [
        fill_row(_bar_ts(40), "ETH/USD", "buy", 100.0, 100.0),
        fill_row(_bar_ts(40) + 5.0, "ETH/USD", "buy", 100.0, 100.0),
    ])
    rep = mr.build_report(root=root)
    assert rep["arrival_markout"][0]["n"] == 2
    assert rep["arrival_markout"][0]["hrs"] == 1


# --- (e) --json shape on an empty file -----------------------------------------

EXPECTED_KEYS = {"read_at", "fills_path", "candle_dir", "rows_total", "entries_with_size",
                 "scored", "skipped", "skipped_no_bar_near_right_edge", "lanes_used",
                 "lanes_loaded", "horizons", "placebo_shifts", "min_bars_ahead", "too_few",
                 "arrival_markout", "per_symbol", "placebo", "decomposition", "slip",
                 "ticks", "caveats"}


def test_json_shape_is_stable_on_empty_fills(root: Path):
    write_fills(root / "outputs/fills.csv", [])
    rep = mr.build_report(root=root)
    assert set(rep) == EXPECTED_KEYS
    assert rep["rows_total"] == 0 and rep["scored"] == 0
    assert rep["skipped"] == {"no_ref": 0, "no_bar": 0}
    assert [g["tag"] for g in rep["arrival_markout"]] == [
        "ALL entries", "maker (post_only)", "taker", "buy", "sell"]
    assert [g["shift"] for g in rep["placebo"]] == list(mr.PLACEBO_SHIFTS)
    assert [g["tag"] for g in rep["decomposition"]] == ["ALL", "maker", "taker"]
    assert rep["per_symbol"] == []
    assert rep["slip"] == {"mean": None, "p50": None, "p95": None,
                           "maker_mean": None, "taker_mean": None}
    assert rep["ticks"]["enabled"] is False
    assert set(rep["ticks"]["horizons"]) == {f"{h}s" for h in mr.TICK_HORIZONS_S}
    json.dumps(rep)                                  # serialisable as-is
    assert "n= " in mr.render(rep) or "n=   0" in mr.render(rep)
    # the CLI path, same shape, no candle dir at all
    out = subprocess.run([sys.executable, str(mr.ROOT / "scripts" / "markout_report.py"),
                          "--json", "--root", str(root)],
                         capture_output=True, text=True, check=True, cwd=str(mr.ROOT))
    parsed = json.loads(out.stdout)
    assert set(parsed) == EXPECTED_KEYS
    assert parsed["ticks"]["enabled"] is False


# --- (f) tick-mode horizon lookup, no network ----------------------------------

def test_tick_horizon_uses_last_trade_at_or_before_each_horizon():
    ts = 1_780_000_000.0
    trades = [(ts - 30.0, 100.0), (ts + 0.5, 101.0), (ts + 5.0, 102.0),
              (ts + 45.0, 103.0), (ts + 200.0, 104.0)]
    got = mr.tick_horizon_prices(trades, ts, (1, 10, 60, 300), page_last_s=ts + 250.0)
    assert got == {1: 101.0, 10: 102.0, 60: 103.0, 300: None}   # 300s beyond the page
    got = mr.tick_horizon_prices(trades, ts, (1, 10, 60, 300), page_last_s=None)
    assert got[300] == 104.0
    # a trade EXACTLY at the horizon counts ("at or before")
    got = mr.tick_horizon_prices([(ts + 10.0, 55.0)], ts, (10,), page_last_s=ts + 10.0)
    assert got == {10: 55.0}
    # nothing precedes the horizon -> None, never the next trade
    got = mr.tick_horizon_prices([(ts + 2.0, 99.0)], ts, (1,), page_last_s=ts + 50.0)
    assert got == {1: None}


def test_parse_trades_reads_kraken_shape():
    raw = {"XXBTZUSD": [["30243.4", "0.3", 1688669597.8, "b", "m", "", 1],
                        ["30250.0", "0.1", 1688669590.2, "s", "l", "", 2],
                        ["bad"]],
           "last": "1688671969993150842"}
    trades, last_s = mr.parse_trades(raw)
    assert trades == [(1688669590.2, 30250.0), (1688669597.8, 30243.4)]
    assert last_s == pytest.approx(1688671969.993150842)
    assert mr.parse_trades(None) == ([], None)


def test_score_ticks_uses_fake_fetch_cache_and_sleep_floor(tmp_path: Path):
    ts = 1_780_000_000.0
    calls: list[dict] = []
    sleeps: list[float] = []

    def fetch(endpoint: str, params: dict):
        calls.append({"endpoint": endpoint, **params})
        # +20bps at every horizon relative to a fill at 100
        return {"XXBTZUSD": [[f"{100.2:.5f}", "1", ts - 59.0, "b", "l", "", 1],
                             [f"{100.2:.5f}", "1", ts + 0.2, "b", "l", "", 2]],
                "last": str(int((ts + 400) * 1e9))}

    scored = [{"ts": ts, "sym": "BTC", "side": "buy", "fill": 100.0, "hour": int(ts // 3600)},
              {"ts": ts + 30, "sym": "BTC", "side": "sell", "fill": 100.0,
               "hour": int(ts // 3600)}]
    cache = tmp_path / "cache"
    tk = mr.score_ticks(scored, fetch, cache, max_fills=100, sleep=sleeps.append)
    assert tk["network_calls"] == 2 and tk["cache_hits"] == 0
    assert calls[0]["endpoint"] == "Trades" and calls[0]["pair"] == "XBTUSD"
    assert calls[0]["since"] == str(int((ts - mr.TICK_PRE_WINDOW_S) * 1e9))
    assert len(sleeps) == 1 and 1.0 < sleeps[0] <= mr.TICK_SLEEP_S      # floor between calls
    assert tk["since_unit_checked"] == 2 and tk["since_unit_confirmed"] == 2
    assert tk["horizons"]["1s"]["n"] == 2
    assert tk["horizons"]["1s"]["mean"] == pytest.approx(0.0)   # buy +20, sell -20
    assert tk["horizons"]["300s"]["n"] == 2
    assert sorted(p.name for p in cache.iterdir()) == [f"BTC_{ts:.3f}.json",
                                                       f"BTC_{ts + 30:.3f}.json"]
    # second run: served from cache, no network, no sleep
    tk2 = mr.score_ticks(scored, fetch, cache, max_fills=100, sleep=sleeps.append)
    assert tk2["network_calls"] == 0 and tk2["cache_hits"] == 2 and len(calls) == 2
    assert len(sleeps) == 1
    assert tk2["horizons"]["1s"]["n"] == 2
    # the cap is honoured
    tk3 = mr.score_ticks(scored, fetch, cache, max_fills=1, sleep=sleeps.append)
    assert tk3["fills_attempted"] == 1


def test_tick_cache_filename_cannot_escape_cache_dir(tmp_path: Path):
    cache = tmp_path / "cache"
    (tmp_path / "escape").mkdir()
    fetch_calls = []

    def fetch(endpoint, params):
        fetch_calls.append(params)
        return {"X": [], "last": "0"}

    mr.fetch_trades_cached(fetch, "../escape/evil/USD", 1.0, cache, sleep=lambda s: None)
    mr.fetch_trades_cached(fetch, "..\\escape\\x/USD", 2.0, cache, sleep=lambda s: None)
    written = sorted(p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*.json"))
    assert written == ["cache/UNKNOWN_1.000.json", "cache/escapex_2.000.json"]
    assert not list((tmp_path / "escape").iterdir())


def test_kraken_pair_aliases():
    assert mr.kraken_pair_for("BTC/USD") == "XBTUSD"
    assert mr.kraken_pair_for("DOGE/USD") == "XDGUSD"
    assert mr.kraken_pair_for("ETH/USD") == "ETHUSD"
