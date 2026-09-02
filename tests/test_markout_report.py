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
                 "ticks", "tick_store", "caveats"}


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
    assert rep["tick_store"]["enabled"] is False
    assert set(rep["tick_store"]) == TICK_STORE_KEYS
    json.dumps(rep)                                  # serialisable as-is
    assert "n= " in mr.render(rep) or "n=   0" in mr.render(rep)
    # the CLI path, same shape, no candle dir at all
    out = subprocess.run([sys.executable, str(mr.ROOT / "scripts" / "markout_report.py"),
                          "--json", "--root", str(root)],
                         capture_output=True, text=True, check=True, cwd=str(mr.ROOT))
    parsed = json.loads(out.stdout)
    assert set(parsed) == EXPECTED_KEYS
    assert parsed["ticks"]["enabled"] is False
    assert parsed["tick_store"]["enabled"] is False


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


# --- (g) tick-store mode: LOCAL tape, offline ----------------------------------

TICK_STORE_KEYS = {"enabled", "root", "read_at", "horizons_s", "pre_s", "placebo_shifts_s",
                   "pairs", "fills_considered", "scored", "skipped_by_pair", "skip_reasons",
                   "groups", "placebo", "matched", "density", "caveats"}
TS0 = float(T0 + 50 * 3600 + 600)           # a fill 10 min into an hour
STORE_H = mr.STORE_HORIZONS_S


def write_tape(root: Path, sym: str, points, start_id: int = 1) -> None:
    """points = [(time_s, price)] -> <root>/outputs/ticks/kraken/<PAIR>/..parquet
    through the SAME TickStore.append the backfill uses."""
    import scripts.kraken_trades_backfill as kb
    store = kb.TickStore(root / "outputs" / "ticks")
    rows = [{"trade_id": start_id + i, "time_s": float(t), "price": float(p), "volume": 1.0,
             "side": "b", "otype": "l", "misc": ""} for i, (t, p) in enumerate(points)]
    store.append(kb.kraken_pair(sym), rows)


def flat_tape(t0: float, price: float, span_s: float = 5000.0, step_s: float = 5.0,
              before_s: float = 4000.0):
    """A print every step_s from t0-before_s through t0+span_s at `price`."""
    return [(t, price) for t in np.arange(t0 - before_s, t0 + span_s + step_s, step_s)]


def stepped(points, at: float, factor: float):
    """Multiply every print with time > at by factor (a step strictly AFTER
    at) and add a stepped print at at+0.25s so the 1s horizon sees it."""
    base = [p for t, p in points if t <= at][-1]
    out = [(t, p * factor if t > at else p) for t, p in points]
    return sorted(out + [(at + 0.25, base * factor)])


def _store_all(rep) -> dict:
    return rep["tick_store"]["groups"][0]


def test_tick_store_sign_is_with_us_for_buy_and_sell(root: Path):
    # buy at TS0: prints step UP 20bps 0.5s after the fill; sell at TS0+2h:
    # prints step DOWN 20bps 0.5s after. Both must read +20 at EVERY horizon.
    t_sell = TS0 + 7200.0
    pts = stepped(flat_tape(TS0, 100.0, span_s=7200.0 + 5000.0), TS0 + 0.5, 1.002)
    pts = stepped(pts, t_sell + 0.5, 0.998)
    write_tape(root, "ETH", pts)
    write_fills(root / "outputs/fills.csv", [
        fill_row(TS0, "ETH/USD", "buy", 100.0, 100.0),
        fill_row(t_sell, "ETH/USD", "sell", 100.2, 100.2),
    ])
    rep = mr.build_report(root=root, tick_store=True)
    ts_ = rep["tick_store"]
    assert ts_["enabled"] is True and ts_["scored"] == 2
    assert ts_["skipped_by_pair"] == {} and ts_["skip_reasons"] == {}
    _, entries = mr.load_fills(root / "outputs/fills.csv")
    tape, _meta = mr.load_tape(root / "outputs" / "ticks", ["ETH"])
    rows, _, _ = mr.score_tick_store(entries, tape)
    assert [r["side"] for r in rows] == ["buy", "sell"]
    for r in rows:
        for h in STORE_H:
            assert r[f"{h}s"] == pytest.approx(20.0, abs=1e-6), (r["side"], h, r[f"{h}s"])
        # the fill equals the pre-fill print -> limit distance 0 for both sides
        assert r["pre1s"] == pytest.approx(0.0, abs=1e-9)
    g = _store_all(rep)
    assert g["tag"] == "ALL entries" and g["n"] == 2 and g["hrs"] == 2
    assert g["stats"]["60s"]["mean"] == pytest.approx(20.0, abs=1e-6)
    assert g["stats"]["900s"]["mean"] == pytest.approx(20.0, abs=1e-6)


def test_tick_store_pre1s_is_signed_limit_distance():
    # buy filled 10bps BELOW the last pre-fill print -> pre1s = -10 (same
    # convention as arr2fill: negative = filled better than the reference)
    t = np.array([TS0 - 3000.0, TS0 - 1.5, TS0 + 0.4, TS0 + 1000.0])
    p = np.array([100.0, 100.0, 100.0, 100.0])
    entries = [{"ts": f"{TS0:.3f}", "symbol": "ETH/USD", "side": "buy", "purpose": "entry",
                "fill_size": "1", "fill_price": "99.9", "post_only": "1", "exec_era": ""}]
    rows, _, _ = mr.score_tick_store(entries, {"ETH": (t, p)})
    assert rows[0]["pre1s"] == pytest.approx(-10.0, abs=1e-6)
    # the print at TS0+0.4 (after fill_ts-1s) must NOT be the reference:
    # move it and pre1s does not change
    p2 = np.array([100.0, 100.0, 150.0, 100.0])
    rows2, _, _ = mr.score_tick_store(entries, {"ETH": (t, p2)})
    assert rows2[0]["pre1s"] == pytest.approx(-10.0, abs=1e-6)


def test_tape_lookup_is_last_trade_at_or_before_each_horizon():
    t = np.array([TS0 - 10.0, TS0 + 0.5, TS0 + 5.0, TS0 + 45.0, TS0 + 200.0,
                  TS0 + 600.0, TS0 + 950.0])
    p = np.array([100.0, 101.0, 102.0, 103.0, 104.0, 105.0, 106.0])
    assert mr.tape_price_at_or_before(t, p, TS0 + 1) == 101.0
    assert mr.tape_price_at_or_before(t, p, TS0 + 10) == 102.0
    assert mr.tape_price_at_or_before(t, p, TS0 + 60) == 103.0
    assert mr.tape_price_at_or_before(t, p, TS0 + 300) == 104.0
    assert mr.tape_price_at_or_before(t, p, TS0 + 900) == 105.0
    assert mr.tape_price_at_or_before(t, p, TS0 + 5.0) == 102.0        # exactly AT counts
    assert mr.tape_price_at_or_before(t, p, TS0 - 20.0) is None        # nothing before
    # end to end: a buy at 100 reads +100/+200/+300/+400/+500 bps; the
    # first-trade-AFTER defect would read +200/+300/+400/+500/+600
    entries = [{"ts": f"{TS0:.3f}", "symbol": "ETH/USD", "side": "buy", "purpose": "entry",
                "fill_size": "1", "fill_price": "100.0", "post_only": "1", "exec_era": ""}]
    rows, by_sym, reasons = mr.score_tick_store(entries, {"ETH": (t, p)})
    assert len(rows) == 1 and by_sym == {}
    assert set(reasons) == {"placebo-3600_uncovered", "placebo+3600_uncovered"}
    assert [round(rows[0][f"{h}s"]) for h in STORE_H] == [100, 200, 300, 400, 500]


def test_tick_store_skips_and_counts_uncovered_fills_by_pair(root: Path):
    write_tape(root, "ETH", flat_tape(TS0, 100.0))                       # full cover
    write_tape(root, "BTC", flat_tape(TS0, 50000.0, span_s=500.0))       # ends before +900
    write_tape(root, "SOL", flat_tape(TS0, 50.0, before_s=0.5))          # starts after fill-1s
    write_fills(root / "outputs/fills.csv", [
        fill_row(TS0, "ETH/USD", "buy", 100.0, 100.0),
        fill_row(TS0, "BTC/USD", "buy", 50000.0, 50000.0),
        fill_row(TS0, "BTC/USD", "sell", 50000.0, 50000.0),
        fill_row(TS0, "SOL/USD", "buy", 50.0, 50.0),
        fill_row(TS0, "FLOW/USD", "buy", 1.0, 1.0),                      # no tape at all
        fill_row(TS0, "ETH/USD", "buy", "", 100.0),                      # no fill_price
        fill_row(TS0, "ETH/USD", "buy", 100.0, 100.0, size="0"),         # not an entry fill
    ])
    rep = mr.build_report(root=root, tick_store=True)
    ts_ = rep["tick_store"]
    assert ts_["fills_considered"] == 6
    assert ts_["scored"] == 1
    assert ts_["skipped_by_pair"] == {"BTC": 2, "SOL": 1, "FLOW": 1, "ETH": 1}
    assert ts_["skip_reasons"] == {"tape_ends_before_horizon": 2, "tape_starts_after_fill": 1,
                                   "no_tape": 1, "no_fill_price": 1}
    assert ts_["scored"] + sum(ts_["skipped_by_pair"].values()) == ts_["fills_considered"]
    assert ts_["pairs"]["FLOW"] == {"pair": "FLOWUSD", "rows": 0, "t_min": None, "t_max": None}
    assert ts_["pairs"]["BTC"]["pair"] == "XBTUSD" and ts_["pairs"]["BTC"]["rows"] > 0
    assert ts_["pairs"]["ETH"]["t_max"] == pytest.approx(TS0 + 5000.0)
    # the single scored row is the ETH fill, and the BTC fill was NOT scored
    # from its last (stale) print
    assert [g["tag"] for g in ts_["groups"] if g["tag"] in ("BTC", "ETH")] == ["ETH"]


def test_tape_covers_reasons():
    t = np.array([TS0 - 100.0, TS0 + 950.0])
    assert mr.tape_covers(t, TS0) is None
    assert mr.tape_covers(t, TS0 + 51.0) == "tape_ends_before_horizon"     # +51+900 > +950
    assert mr.tape_covers(t, TS0 + 50.0) is None                            # exactly reaches
    assert mr.tape_covers(t, TS0 - 99.5) == "tape_starts_after_fill"       # needs ts-1 >= t[0]
    assert mr.tape_covers(t, TS0 - 99.0) is None
    assert mr.tape_covers(np.empty(0), TS0) == "no_tape"


def test_tick_store_placebo_shift_and_no_lookahead_reference(root: Path):
    # real window: step +20bps at TS0+0.5. The +3600 placebo window holds a
    # SECOND step (+20bps at TS0+3600.5): with reference = last print at or
    # before the shifted ts it reads +20; a look-ahead reference (first
    # print AFTER the shifted ts, already stepped) would read 0. The -3600
    # window is flat and must read 0.
    pts = flat_tape(TS0, 100.0, span_s=6000.0, before_s=5000.0)
    pts = stepped(pts, TS0 + 0.5, 1.002)
    pts = stepped(pts, TS0 + 3600.5, 1.002)
    write_tape(root, "ETH", pts)
    # two fills 0.1s apart (group_stats needs >= 2 values), both pre-step
    write_fills(root / "outputs/fills.csv", [fill_row(TS0, "ETH/USD", "buy", 100.0, 100.0),
                                             fill_row(TS0 + 0.1, "ETH/USD", "buy", 100.0, 100.0)])
    rep = mr.build_report(root=root, tick_store=True)
    ts_ = rep["tick_store"]
    assert ts_["scored"] == 2 and ts_["skip_reasons"] == {}
    _, entries = mr.load_fills(root / "outputs/fills.csv")
    tape, _ = mr.load_tape(root / "outputs" / "ticks", ["ETH"])
    for r in mr.score_tick_store(entries, tape)[0]:
        for h in STORE_H:
            assert r[f"{h}s"] == pytest.approx(20.0, abs=1e-6)
            assert r[f"pl-3600_{h}s"] == pytest.approx(0.0, abs=1e-9), h
            assert r[f"pl+3600_{h}s"] == pytest.approx(20.0, abs=1e-6), h
    by_shift = {g["shift_s"]: g for g in ts_["placebo"]}
    assert set(by_shift) == {-3600, 3600}
    assert by_shift[-3600]["stats"]["60s"]["mean"] == pytest.approx(0.0, abs=1e-9)
    assert by_shift[3600]["stats"]["60s"]["mean"] == pytest.approx(20.0, abs=1e-6)
    # the placebo hour set is the SHIFTED one
    assert by_shift[3600]["n"] == 2 and by_shift[3600]["hrs"] == 1
    assert by_shift[-3600]["n"] == 2 and by_shift[-3600]["hrs"] == 1


def test_tick_store_placebo_is_skipped_where_the_shifted_window_is_uncovered():
    # tape covers the real window and -3600 but ends before +3600+900
    t = np.array([TS0 - 3700.0, TS0 - 1.5, TS0 + 950.0, TS0 + 3600.0 + 100.0])
    p = np.array([100.0, 100.0, 100.0, 100.0])
    entries = [{"ts": f"{TS0:.3f}", "symbol": "ETH/USD", "side": "buy", "purpose": "entry",
                "fill_size": "1", "fill_price": "100.0", "post_only": "1", "exec_era": ""}]
    rows, _, reasons = mr.score_tick_store(entries, {"ETH": (t, p)})
    assert len(rows) == 1
    assert "pl-3600_60s" in rows[0] and "pl+3600_60s" not in rows[0]
    assert reasons == {"placebo+3600_uncovered": 1}
    sec = mr.build_tick_store_sections(rows)
    assert {g["shift_s"]: g["n"] for g in sec["placebo"]} == {-3600: 1, 3600: 0}


def test_tick_store_eras_and_maker_taker_are_never_pooled(root: Path):
    # era A (maker): +20bps after every fill; era B (taker): -20bps. ALL pools
    # to 0; each era line, and each era x maker/taker line, keeps its own sign.
    ta = [TS0, TS0 + 2 * 3600.0]
    tb = [TS0 + 4 * 3600.0, TS0 + 6 * 3600.0]
    pts = flat_tape(TS0, 100.0, span_s=8 * 3600.0)
    price = 100.0
    out = []
    steps = sorted([(t + 0.5, 1.002) for t in ta] + [(t + 0.5, 0.998) for t in tb])
    for t, _ in pts:
        while steps and t > steps[0][0]:
            price *= steps.pop(0)[1]
        out.append((t, price))
    write_tape(root, "ETH", out)
    def px_at(t):                      # last print at/before t (the fill price we book)
        return [p for tt, p in out if tt <= t][-1]

    write_fills(root / "outputs/fills.csv",
                [fill_row(t, "ETH/USD", "buy", px_at(t), px_at(t), era="7-e7d5ca1a") for t in ta]
                + [fill_row(t, "ETH/USD", "buy", px_at(t), px_at(t), post_only="0",
                            era="9-16ec821e") for t in tb])
    rep = mr.build_report(root=root, tick_store=True)
    by_tag = {g["tag"]: g for g in rep["tick_store"]["groups"]}
    assert rep["tick_store"]["scored"] == 4
    assert by_tag["ALL entries"]["n"] == 4
    assert by_tag["ALL entries"]["stats"]["60s"]["mean"] == pytest.approx(0.0, abs=1e-6)
    assert by_tag["era 7-e7d5ca1a"]["n"] == 2
    assert by_tag["era 7-e7d5ca1a"]["stats"]["60s"]["mean"] == pytest.approx(20.0, abs=1e-6)
    assert by_tag["era 9-16ec821e"]["n"] == 2
    assert by_tag["era 9-16ec821e"]["stats"]["60s"]["mean"] == pytest.approx(-20.0, abs=1e-6)
    assert by_tag["maker (post_only)"]["stats"]["900s"]["mean"] == pytest.approx(20.0, abs=1e-6)
    assert by_tag["taker"]["stats"]["900s"]["mean"] == pytest.approx(-20.0, abs=1e-6)
    assert by_tag["era 7-e7d5ca1a maker"]["n"] == 2 and by_tag["era 7-e7d5ca1a taker"]["n"] == 0
    assert by_tag["era 9-16ec821e taker"]["n"] == 2 and by_tag["era 9-16ec821e maker"]["n"] == 0
    # nothing labelled pre-era exists here: no pooled '(pre-era)' line may appear
    assert "era (pre-era)" not in by_tag


def test_tick_store_se_deflates_to_distinct_fill_hours(root: Path):
    # three fills in ONE hour (different minutes) + one in the next hour ->
    # hrs == 2, never 4; SE = std/sqrt(2)
    write_tape(root, "ETH", flat_tape(TS0, 100.0, span_s=8000.0))
    pts_v = [(TS0, 100.0), (TS0 + 300.0, 100.1), (TS0 + 1200.0, 99.9), (TS0 + 3600.0, 100.05)]
    write_fills(root / "outputs/fills.csv",
                [fill_row(t, "ETH/USD", "buy", p, p) for t, p in pts_v])
    rep = mr.build_report(root=root, tick_store=True)
    g = _store_all(rep)
    assert g["n"] == 4 and g["hrs"] == 2
    vals = np.array([(100.0 - p) / p * 1e4 for _, p in pts_v])
    assert g["stats"]["60s"]["mean"] == pytest.approx(vals.mean(), abs=1e-6)
    assert g["stats"]["60s"]["se"] == pytest.approx(vals.std(ddof=1) / np.sqrt(2), abs=1e-9)


def test_tick_store_json_section_and_cli(root: Path):
    write_tape(root, "ETH", flat_tape(TS0, 100.0))
    write_fills(root / "outputs/fills.csv", [fill_row(TS0, "ETH/USD", "buy", 100.0, 100.0)])
    rep = mr.build_report(root=root, tick_store=True)
    ts_ = rep["tick_store"]
    assert set(ts_) == TICK_STORE_KEYS
    assert ts_["enabled"] is True and ts_["root"] == str(root / "outputs" / "ticks")
    assert ts_["horizons_s"] == [1, 10, 60, 300, 900] and ts_["pre_s"] == 1
    assert ts_["placebo_shifts_s"] == [-3600, 3600]
    assert [g["tag"] for g in ts_["groups"]] == [
        "ALL entries", "era (pre-era)", "maker (post_only)", "taker",
        "era (pre-era) maker", "era (pre-era) taker", "buy", "sell", "ETH"]
    assert set(ts_["groups"][0]["stats"]) == {"1s", "10s", "60s", "300s", "900s", "pre1s"}
    assert [g["shift_s"] for g in ts_["placebo"]] == [-3600, 3600]
    assert ts_["matched"]["shift_s"] == 0 and ts_["matched"]["n"] == 1
    assert set(ts_["density"]["stale_by_horizon"]) == {"1s", "10s", "60s", "300s", "900s"}
    assert ts_["read_at"].endswith("+00:00")
    json.dumps(rep)
    text = mr.render(rep)
    assert "=== TICK-STORE" in text and "tape ETH   ETHUSD" in text
    assert "skipped by pair {}" in text
    # CLI: bare --tick-store resolves to <root>/outputs/ticks; an explicit
    # ROOT with no tape scores nothing and counts every fill
    out = subprocess.run([sys.executable, str(mr.ROOT / "scripts" / "markout_report.py"),
                          "--json", "--root", str(root), "--tick-store"],
                         capture_output=True, text=True, check=True, cwd=str(mr.ROOT))
    parsed = json.loads(out.stdout)
    assert parsed["tick_store"]["enabled"] is True and parsed["tick_store"]["scored"] == 1
    out = subprocess.run([sys.executable, str(mr.ROOT / "scripts" / "markout_report.py"),
                          "--json", "--root", str(root), "--tick-store", str(root / "nowhere")],
                         capture_output=True, text=True, check=True, cwd=str(mr.ROOT))
    parsed = json.loads(out.stdout)
    assert parsed["tick_store"]["root"] == str(root / "nowhere")
    assert parsed["tick_store"]["scored"] == 0
    assert parsed["tick_store"]["skip_reasons"] == {"no_tape": 1}
    assert parsed["tick_store"]["skipped_by_pair"] == {"ETH": 1}


def test_tick_store_symbol_cannot_name_a_path(root: Path):
    (root / "escape").mkdir()
    write_tape(root, "ETH", flat_tape(TS0, 100.0))
    write_fills(root / "outputs/fills.csv", [
        fill_row(TS0, "../escape/USD", "buy", 1.0, 1.0),           # asset '..' -> UNKNOWN
        fill_row(TS0, r"..\..\ETH/USD", "buy", 100.0, 100.0),      # separators stripped -> ETH
    ])
    rep = mr.build_report(root=root, tick_store=True)
    ts_ = rep["tick_store"]
    assert set(ts_["pairs"]) == {"UNKNOWN", "ETH"}
    assert ts_["pairs"]["UNKNOWN"] == {"pair": "UNKNOWNUSD", "rows": 0, "t_min": None, "t_max": None}
    assert ts_["skipped_by_pair"] == {"UNKNOWN": 1}
    assert ts_["scored"] == 1
    assert not list((root / "escape").iterdir())


# --- (h) reference estimand, print density, tape ORDER ---------------------------

def test_matched_reference_is_a_tape_print_not_the_fill_price(root: Path):
    """THE ESTIMAND PIN. The group lines are referenced to fill_price (off
    tape, inside the spread); the placebos to a tape print. A maker buy
    filled 10bps under a DEAD-FLAT tape therefore reads +10bps forever on
    the group line and EXACTLY 0.0 on the matched (shift-0) line, which is
    the placebos' own construction. A matched line that reused fill_price
    (or a placebo built off the fill) would read +10 here and the
    'placebo is flat' reading would be circular."""
    write_tape(root, "ETH", flat_tape(TS0, 100.0, span_s=6000.0, before_s=5000.0))
    write_fills(root / "outputs/fills.csv", [fill_row(TS0, "ETH/USD", "buy", 99.9, 99.9),
                                             fill_row(TS0 + 0.1, "ETH/USD", "buy", 99.9, 99.9)])
    rep = mr.build_report(root=root, tick_store=True)
    ts_ = rep["tick_store"]
    assert ts_["scored"] == 2
    fill_ref = ts_["groups"][0]["stats"]
    matched = ts_["matched"]
    assert matched["shift_s"] == 0 and matched["n"] == 2
    for h in STORE_H:
        assert fill_ref[f"{h}s"]["mean"] == pytest.approx(10.01, abs=0.01), h
        assert matched["stats"][f"{h}s"]["mean"] == pytest.approx(0.0, abs=1e-9), h
    # the whole fill-referenced number IS the limit distance, and pre1s says so
    assert fill_ref["pre1s"]["mean"] == pytest.approx(-10.0, abs=1e-6)
    for g in ts_["placebo"]:
        for h in STORE_H:
            assert g["stats"][f"{h}s"]["mean"] == pytest.approx(0.0, abs=1e-9)
    text = mr.render(rep)
    assert "MATCHED" in text and "TAPE-REFERENCED" in text
    assert any("DIFFERENT ESTIMANDS" in c for c in ts_["caveats"])


def test_stale_horizons_are_counted_when_the_window_has_no_prints():
    """tape_covers is ENDPOINT-only. A fill in a 400 s tape dead zone is
    'covered' yet its 1/10/60/300 s prices are all the SAME pre-fill print,
    so those horizons are -pre1s by construction, not forward moves. The
    density block must name them; a report that only prints means cannot
    tell this apart from a market that did not move."""
    pre = [(t, 100.0) for t in np.arange(TS0 - 1000.0, TS0 + 0.1, 5.0)]
    post = [(t, 101.0) for t in np.arange(TS0 + 400.0, TS0 + 950.1, 5.0)]
    t = np.array([x for x, _ in pre + post], float)
    p = np.array([y for _, y in pre + post], float)
    entries = [{"ts": f"{TS0:.3f}", "symbol": "ETH/USD", "side": "buy", "purpose": "entry",
                "fill_size": "1", "fill_price": "99.9", "post_only": "1", "exec_era": ""}]
    rows, _, _ = mr.score_tick_store(entries, {"ETH": (t, p)})
    r = rows[0]
    assert [r["stale_1s"], r["stale_10s"], r["stale_60s"], r["stale_300s"]] == [True] * 4
    assert r["stale_900s"] is False
    assert r["n_prints"] == 101                      # (TS0, TS0+900]: 400..900 step 5
    assert r["max_gap_s"] == pytest.approx(400.0, abs=1e-9)
    # the mechanism: a stale horizon is the pre-fill print, so it mirrors pre1s
    assert r["1s"] == pytest.approx(-r["pre1s"], rel=2e-3)
    assert r["900s"] > 0 and r["900s"] != pytest.approx(r["300s"])
    d = mr.density_summary(rows)
    assert d["stale_by_horizon"] == {"1s": 1, "10s": 1, "60s": 1, "300s": 1, "900s": 0}
    assert d["no_print_in_window"] == 0
    assert d["max_gap_s"]["median"] == pytest.approx(400.0, abs=1e-9)
    assert d["window_s"] == 900
    # a fill whose whole window is silent: every horizon stale, gap == window
    t2 = np.array([TS0 - 10.0, TS0 + 901.0], float)
    rows2, _, _ = mr.score_tick_store(entries, {"ETH": (t2, np.array([100.0, 100.0]))})
    d2 = mr.density_summary(rows2)
    assert d2["no_print_in_window"] == 1 and rows2[0]["max_gap_s"] == 900.0
    assert d2["stale_by_horizon"] == {f"{h}s": 1 for h in STORE_H}


def test_load_tape_sorts_by_TIME_not_trade_id(root: Path):
    """TickStore.load sorts by trade_id; every searchsorted downstream needs
    TIME order. Plant a tape whose trade_id order is NOT time order (the
    backfill pages out of order / a re-request) and require both: the loaded
    times come back non-decreasing, and the fill still scores its planted
    +20bps. Without load_tape's re-sort the endpoint check reads the last
    INSERTED print and the fill is silently skipped."""
    pts = flat_tape(TS0, 100.0, span_s=5000.0, before_s=5000.0)
    pts = stepped(pts, TS0 + 0.5, 1.002)
    shuffled = pts[len(pts) // 2:] + pts[:len(pts) // 2]      # trade_id != time order
    write_tape(root, "ETH", shuffled)
    tape, meta = mr.load_tape(root / "outputs" / "ticks", ["ETH"])
    t, _p = tape["ETH"]
    assert np.all(np.diff(t) >= 0), "load_tape returned a tape out of time order"
    assert meta["ETH"]["t_min"] == pytest.approx(min(x for x, _ in pts))
    assert meta["ETH"]["t_max"] == pytest.approx(max(x for x, _ in pts))
    write_fills(root / "outputs/fills.csv", [fill_row(TS0, "ETH/USD", "buy", 100.0, 100.0)])
    rep = mr.build_report(root=root, tick_store=True)
    ts_ = rep["tick_store"]
    assert ts_["scored"] == 1 and ts_["skip_reasons"] == {}
    _, entries = mr.load_fills(root / "outputs/fills.csv")
    r = mr.score_tick_store(entries, tape)[0][0]
    for h in STORE_H:
        assert r[f"{h}s"] == pytest.approx(20.0, abs=1e-6), h
