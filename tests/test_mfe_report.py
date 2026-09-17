"""Pins for scripts/mfe_report.py - the peak a closed trade never recorded.

WHY THIS FILE MATTERS MORE THAN MOST. This instrument exists to settle a
question a firing audit deliberately left open: whether the give-back overlay
CENSORS winners or whether the market simply never offered the labelled win.
Those two produce identical rows in the fill ledger, so the answer rests
entirely on a reconstruction - and a reconstruction that is wrong in the
flattering direction would manufacture a finding out of arithmetic.

The dangerous failure here is SIGN. A short scored with the highest high
instead of the lowest low reads as a huge censored winner every single time.
That is pinned first.
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

mfe = pytest.importorskip("scripts.mfe_report")
np = pytest.importorskip("numpy")

FILL_COLS = ["ts", "order_id", "position_id", "purpose", "symbol", "side",
             "ordertype", "post_only", "attempt", "fill_size", "fill_price",
             "arrival_ref", "slip_bps", "fees_delta_usd", "remaining",
             "reason", "exec_era", "book"]


def _candles(bars):
    """(t_open_s, high, low) exactly as load_candles returns them."""
    ts = np.array([b[0] for b in bars], dtype="int64")
    hi = np.array([b[1] for b in bars], dtype="float64")
    lo = np.array([b[2] for b in bars], dtype="float64")
    return ts, hi, lo


def _trip(long=True, entry=100.0, exit_px=101.0, t0=1000, t1=1900, qty=1.0):
    return {"pid": "p1", "symbol": "ETH/USD", "long": long,
            "t_open": float(t0), "t_close": float(t1),
            "entry_px": entry, "exit_px": exit_px, "qty": qty,
            "notional": qty * entry, "fees": 0.0,
            "reason": "tier trail", "era": "E1"}


# ------------------------------------------------------------------ the sign
def test_a_long_uses_the_HIGH_and_a_short_uses_the_LOW():
    """THE PIN THAT MATTERS MOST. Favourable is side-dependent. Scoring a
    short off the highest high inverts it, and an inverted short reads as a
    large censored winner on every single trade - the exact shape of the
    finding this instrument was built to test. Both arms, one fixture."""
    bars = _candles([(900, 100.0, 100.0), (1200, 112.0, 96.0),
                     (1500, 105.0, 88.0), (1800, 101.0, 99.0)])
    lng = mfe.excursion(_trip(long=True), bars)
    sht = mfe.excursion(_trip(long=False), bars)
    assert lng["covered"] and sht["covered"]
    # long: best is the 112 high -> +12%
    assert lng["mfe_pct"] == pytest.approx(12.0)
    # short: best is the 88 low -> +12% in the short's favour
    assert sht["mfe_pct"] == pytest.approx(12.0)
    # and they are NOT the same computation - swap the price path and they part
    one_sided = _candles([(900, 100.0, 100.0), (1200, 130.0, 99.5),
                          (1800, 100.0, 99.5)])
    lng2 = mfe.excursion(_trip(long=True), one_sided)
    sht2 = mfe.excursion(_trip(long=False), one_sided)
    assert lng2["mfe_pct"] == pytest.approx(30.0)
    assert sht2["mfe_pct"] == pytest.approx(0.5)


def test_realized_is_also_side_dependent():
    """A short that exits BELOW entry made money. Scoring realized with the
    long formula would report every profitable short as a loss and invert the
    whole by-reason table."""
    bars = _candles([(900, 100.0, 99.0), (1800, 100.0, 99.0)])
    r = mfe.excursion(_trip(long=False, entry=100.0, exit_px=98.0), bars)
    assert r["realized_pct"] == pytest.approx(2.0)


# -------------------------------------------------------------- the coverage
def test_a_trip_outside_candle_coverage_is_UNCOVERED_not_zero():
    """DEGRADE CLOSED. A trip whose window runs past the store's last bar has
    an UNKNOWN peak, not a peak of zero. Scoring it as zero would say 'the
    market never offered the win' about a trade nobody measured - the exact
    conclusion this report is built to test, handed out for free."""
    bars = _candles([(900, 101.0, 99.0), (1200, 101.0, 99.0)])
    r = mfe.excursion(_trip(t0=1000, t1=5000), bars)
    assert r["covered"] is False
    assert "coverage ends" in r["reason"]
    assert "mfe_pct" not in r


def test_a_window_starting_after_coverage_is_uncovered():
    bars = _candles([(100, 101.0, 99.0), (400, 101.0, 99.0)])
    r = mfe.excursion(_trip(t0=9000, t1=9600), bars)
    assert r["covered"] is False


def test_no_candles_at_all_is_uncovered_with_a_reason():
    r = mfe.excursion(_trip(), None)
    assert r["covered"] is False
    assert "no candles" in r["reason"]


def test_the_bar_containing_the_exit_is_included():
    """The exit happened INSIDE its bar, so that bar's extreme was reachable
    before the exit fired. Excluding it would drop the peak of every trade
    that ran to its own close."""
    bars = _candles([(900, 100.5, 99.5), (1800, 120.0, 99.5)])
    r = mfe.excursion(_trip(t0=1000, t1=1900), bars)
    assert r["covered"] and r["mfe_pct"] == pytest.approx(20.0)


# ------------------------------------------------------------- the dollar math
def _scored(rows_targets, bars, monkeypatch, reason="tier trail"):
    monkeypatch.setattr(mfe, "load_candles", lambda s, d, interval=300: bars)
    trips = []
    targets = {}
    for i, (long, entry, exit_px, pt_frac, notional_qty) in enumerate(rows_targets):
        t = _trip(long=long, entry=entry, exit_px=exit_px, qty=notional_qty)
        t["pid"] = f"p{i}"
        t["reason"] = reason
        trips.append(t)
        targets[f"p{i}"] = {"pt_frac": pt_frac, "sl_frac": 0.0,
                            "label_era": "e", "barrier": "", "probe": ""}
    return mfe.score(trips, targets, Path("."))


def test_shortfall_is_clamped_at_zero_when_the_exit_BEAT_the_target(monkeypatch):
    """MEASURED DEFECT, first version. A trade exiting ABOVE its labelled
    target produced a NEGATIVE shortfall that summed into the total and made
    the overlay's cost read as -$0.73 - a number with no meaning that a reader
    takes for a profit. Exiting better than the target is not forgone."""
    bars = _candles([(900, 100.0, 100.0), (1200, 106.0, 99.0),
                     (1800, 105.0, 104.0)])
    # entry 100, exit 105 (=+5%), target 2% -> reached, and BEAT it
    res = _scored([(True, 100.0, 105.0, 0.02, 1.0)], bars, monkeypatch)
    r = res["scored"][0]
    assert r["reached_pt"] is True
    assert r["shortfall_usd"] == 0.0
    assert r["beat_target"] is True


def test_shortfall_is_real_when_the_target_was_available_and_missed(monkeypatch):
    """The other arm. Peak reached 6%, target was 2%, we took 1% -> the
    labelled win WAS on the table and we banked less."""
    bars = _candles([(900, 100.0, 100.0), (1200, 106.0, 99.0),
                     (1800, 101.0, 100.5)])
    res = _scored([(True, 100.0, 101.0, 0.02, 1.0)], bars, monkeypatch)
    r = res["scored"][0]
    assert r["reached_pt"] is True
    assert r["beat_target"] is False
    # (2% - 1%) of a $100 notional
    assert r["shortfall_usd"] == pytest.approx(1.0)


def test_a_trade_that_never_reached_the_target_owes_nothing(monkeypatch):
    """THE FINDING THIS INSTRUMENT EXISTS TO ALLOW. If the market never
    offered the labelled win, the overlay censored nothing and the shortfall
    is zero - not a small number, ZERO. A report that could not return this
    could only ever confirm the censoring theory."""
    bars = _candles([(900, 100.0, 100.0), (1200, 100.8, 99.0),
                     (1800, 100.4, 100.0)])
    res = _scored([(True, 100.0, 100.4, 0.02, 1.0)], bars, monkeypatch)
    r = res["scored"][0]
    assert r["reached_pt"] is False
    assert r["shortfall_usd"] == 0.0
    assert r["giveback_usd"] > 0.0, "peak-to-exit is still reported"


def test_giveback_is_peak_to_exit_and_priced_on_notional(monkeypatch):
    bars = _candles([(900, 100.0, 100.0), (1200, 103.0, 99.0),
                     (1800, 101.0, 100.0)])
    res = _scored([(True, 100.0, 101.0, 0.50, 2.0)], bars, monkeypatch)
    r = res["scored"][0]
    assert r["gave_back_pct"] == pytest.approx(2.0)       # 3% peak - 1% got
    assert r["giveback_usd"] == pytest.approx(4.0)        # 2% of $200


# ------------------------------------------------------------------ the joins
def test_a_trip_with_no_labelled_target_is_UNSCORED_not_assumed(monkeypatch):
    monkeypatch.setattr(mfe, "load_candles", lambda s, d, interval=300: None)
    t = _trip()
    res = mfe.score([t], {}, Path("."))
    assert res["unscored"] == 1
    assert res["scored"] == []


def test_the_symbol_maps_from_the_pair_to_the_base(tmp_path):
    """The ledger says 'ETH/USD', the store keys on 'ETH'. Getting this wrong
    returns None for EVERY symbol, scores every trip UNCOVERED, and the report
    then says nothing was measurable - silently, in the flattering direction.

    Pinned on the PATH, not on the None: an earlier version asserted only
    that a bad symbol returns None, which is equally true of a correct mapping
    and a completely broken one."""
    assert mfe.candle_path("ETH/USD", tmp_path).name == "ETH_300.parquet"
    assert mfe.candle_path("eth/usd", tmp_path).name == "ETH_300.parquet"
    assert mfe.candle_path("PAXG/USD", tmp_path, 900).name == "PAXG_900.parquet"
    assert mfe.candle_path("BTC", tmp_path).name == "BTC_300.parquet"
    # and an unreadable file is still None rather than a crash
    (tmp_path / "ETH_300.parquet").write_bytes(b"")
    assert mfe.load_candles("ETH/USD", tmp_path) is None


def test_trips_are_reconstructed_from_both_sides(tmp_path):
    p = tmp_path / "fills.csv"
    with p.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FILL_COLS)
        w.writeheader()
        base = {c: "" for c in FILL_COLS}
        for ts, side, size, px, reason in (
                (1000, "buy", "1.0", "100.0", ""),
                (1900, "sell", "1.0", "101.0", "tier trail")):
            r = dict(base)
            r.update({"ts": str(ts), "position_id": "p1", "symbol": "ETH/USD",
                      "side": side, "fill_size": size, "fill_price": px,
                      "reason": reason, "exec_era": "E1"})
            w.writerow(r)
    trips = mfe.load_trips(p)
    assert len(trips) == 1
    t = trips[0]
    assert t["long"] is True and t["entry_px"] == 100.0 and t["exit_px"] == 101.0
    assert t["reason"] == "tier trail"
    assert t["notional"] == pytest.approx(100.0)


def test_a_one_sided_position_is_not_a_trip(tmp_path):
    p = tmp_path / "fills.csv"
    with p.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FILL_COLS)
        w.writeheader()
        r = {c: "" for c in FILL_COLS}
        r.update({"ts": "1000", "position_id": "p1", "symbol": "ETH/USD",
                  "side": "buy", "fill_size": "1.0", "fill_price": "100.0"})
        w.writerow(r)
    assert mfe.load_trips(p) == []


# --------------------------------------------------------------- the contract
def test_the_report_writes_nothing_anywhere(tmp_path, monkeypatch):
    """REPORT-ONLY is what makes this SAFE under the era-12 moratorium.
    Pinned with an audit hook, not by inspection."""
    writes: list[str] = []

    def _audit(event, args):
        if event == "open" and len(args) > 1:
            mode = args[1]
            if isinstance(mode, str) and any(c in mode for c in "wxa+"):
                writes.append(str(args[0]))
        elif event in ("os.rename", "os.replace", "os.remove", "os.unlink",
                       "os.mkdir"):
            writes.append(str(args[0]))

    monkeypatch.setenv("LB_OUTPUTS", str(tmp_path))
    sys.addaudithook(_audit)
    mfe.collect()
    assert not writes, f"the report-only instrument wrote: {writes[:5]}"
    assert not list(tmp_path.iterdir())


def test_render_says_COVERAGE_not_FINDING_when_nothing_scored(tmp_path,
                                                              monkeypatch):
    """An empty result must NOT read as 'the market never offered the win'.
    That is the conclusion under test, and handing it out for free on a
    coverage failure is the worst thing this file could do."""
    monkeypatch.setenv("LB_OUTPUTS", str(tmp_path))
    text = mfe.render(mfe.collect())
    assert "NOTHING SCORED" in text
    assert "COVERAGE result, not a" in text


def test_the_upper_bound_caveat_always_prints(tmp_path, monkeypatch):
    """A 5 m bar's high may have lived for a second between two polls, so
    'the market offered it' is never 'the bot could have taken it'. If that
    caveat ever stops printing, every number here gets over-read."""
    monkeypatch.setenv("LB_OUTPUTS", str(tmp_path))
    text = mfe.render(mfe.collect())
    assert "NOTHING SCORED" in text        # coverage path still carries it
    full = mfe.render({"read_at": "X", "stamps": {}, "era_filter": "(all)",
                       "trips_closed": 1, "unscored_no_label": 0,
                       "uncovered_no_candles": 0, "coverage_ends": "X",
                       "summary": mfe.summarize([]), "rows": []})
    assert "NOTHING SCORED" in full
