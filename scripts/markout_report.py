"""
scripts/markout_report.py — post-fill MARKOUT / adverse-selection report.

SAFE class (era-6 moratorium): read-only measurement over outputs/fills.csv
and the candle store. It places no order, alters no config, imports nothing
from the decision path, and writes into outputs/ ONLY in --ticks mode, and
then only the raw-response cache under outputs/markout_ticks_cache/.

WHAT IT MEASURES. For every ENTRY fill with fill_size > 0:

    markout_h = side_sign * (P[t0 + h] - ref) / ref * 1e4        (bps)
    side_sign = +1 buy, -1 sell.  POSITIVE = the market moved WITH us after
    we entered; NEGATIVE = we were adversely selected.

Two references are reported side by side:
  * arrival_ref  — the venue price at DECISION time, so this is the SIGNAL's
                   short-horizon timing (the fill simulator is not in it);
  * fill_price   — the price we actually booked, so this is the fill's
                   TOXICITY: what happened after we were done.
and the DECOMPOSITION table splits the arrival_ref number into
    arr->fill      = side_sign * (fill - ref) / ref * 1e4   (limit distance:
                     a maker resting below arrival collects this by
                     construction; it carries no forward information)
    fill->horizon  = the toxicity term above.
Read execution/markout.py's "DECOMPOSITION" note before calling either an
edge: spread capture is not prediction, and fill-time selection is not
removed by subtracting it.

CANDLE MODE (default, offline). P[t0 + h] is the CLOSE of the (h-1)-th bar
after the first 1h bar OPENING at or after the fill ts, read from
outputs/candles/parquet/<SYM>_3600.parquet (every column is stored as a
string — cast on load). Lane preference kraken > binanceus > okx (USDT
quote, ~0 basis for majors); the first lane in that order whose series
contains the fill AND >= 30 bars beyond it is used, so a fill is skipped —
COUNTED, never silently dropped — only when no lane covers its window
(`no_bar`) or it carries no arrival_ref (`no_ref`). Recent fills inside the
store's last 30 bars are `no_bar` by construction and become scorable as
the store extends. Bars are indexed by POSITION inside a lane, so a gap in
a lane's bar series makes "h bars ahead" longer than h hours for the fills
whose window straddles the gap — the store's coverage report, not this
script, is where that is measured.

PLACEBO (always printed). The same fills and sides with the bar index
shifted by -24/-6/+6/+24 bars, reference = close of the bar BEFORE the
shifted index (so the placebo has no look-ahead and inherits whatever
drift and side-mix bias the real measurement has). It is the control that
separates adverse selection from "we buy in a falling market": a real
markout that the placebo reproduces is drift, not selection. Note that the
-6 shift's 24h window overlaps the real fill window by construction.

STANDARD ERRORS are deflated to DISTINCT FILL-HOURS, not row count (a
burst of five fills in one hour is one draw of the market), and the
printed caveat says what that still does not fix: cross-asset fills in the
same hour remain correlated, so every SE here is OPTIMISTIC.

TICK MODE (--ticks, NETWORK, off by default). For each scored entry fill,
pulls Kraken public trades (`_public_get("Trades", ...)` on a
credential-free client built the way scripts/candle_backfill.py builds
one) and computes markout from fill_price at +1s/+10s/+60s/+300s using the
LAST trade price at or before each horizon. `since` is sent as a
NANOSECOND string: docs.kraken.com describes it only as "Return trade data
since given timestamp", shows a 10-digit (seconds) example value, and
returns the page cursor `last` as a 19-digit (nanoseconds) string; the
venue accepts both scales by magnitude [I — verified from the docs page
2026-09-01, not from repo usage: nothing in data/kraken_feed.py calls
Trades]. Rather than trust that, the run CONFIRMS THE UNIT FROM THE
RUNTIME: the first trade of every fresh page must fall within one hour of
the requested since, and the summary prints how many pages passed that
check. A hard sleep of >= 1.1 s separates network calls (Kraken public
rate limit; the shipped client's own throttle sits under it), --max-fills
(default 100) bounds a default run to ~2 min, and every raw response is
cached at outputs/markout_ticks_cache/<symbol>_<ts>.json so re-runs are
free. One page (<= 1000 trades) per fill: a horizon the page does not
reach is counted `page_exhausted`, never filled from a later trade.

Usage:
    python scripts/markout_report.py                # candle report
    python scripts/markout_report.py --json         # same, as one dict
    python scripts/markout_report.py --ticks --max-fills 50
"""

from __future__ import annotations

import argparse
import csv
import datetime as _dt
import glob
import json
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable, Optional, Sequence

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

HORIZONS: dict[str, int] = {"1h": 1, "4h": 4, "24h": 24}
LANE_PREF: tuple[str, ...] = ("kraken", "binanceus", "okx")
PLACEBO_SHIFTS: tuple[int, ...] = (-24, -6, 6, 24)
MIN_BARS_AHEAD = 30       # a lane covers a fill only with this many bars past it
TOO_FEW = 10              # groups below this print "(too few)" instead of stats
CANDLE_INTERVAL_S = 3600

TICK_HORIZONS_S: tuple[int, ...] = (1, 10, 60, 300)
TICK_SLEEP_S = 1.1        # hard floor between network calls, on top of the throttle
TICK_PRE_WINDOW_S = 60    # request trades from this far before the fill
TICK_PAGE_COUNT = 1000    # Kraken Trades max per page
TICK_UNIT_TOLERANCE_S = 3600.0
TICK_CACHE_SUBDIR = "markout_ticks_cache"
DEFAULT_MAX_FILLS = 100

# Kraken denomination aliases for the Trades pair name (same table as
# scripts/candle_backfill.py; KrakenFeed.kraken_pair is a bare replace).
_KRAKEN_ASSET = {"BTC": "XBT", "DOGE": "XDG"}

Row = dict[str, Any]


# --- loading ---------------------------------------------------------------

def _num(s: Optional[str]) -> float:
    """float(s) with '', None, unparsable and non-finite all -> 0.0."""
    try:
        v = float(s or 0.0)
    except ValueError:
        return 0.0
    return v if np.isfinite(v) else 0.0


def load_fills(path: Path) -> tuple[list[Row], list[Row]]:
    """(all rows, entry rows with fill_size > 0). Missing file -> ([], [])."""
    if not path.exists():
        return [], []
    with open(path, encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    entries = [r for r in rows
               if r.get("purpose") == "entry" and _num(r.get("fill_size")) > 0]
    return rows, entries


def load_lanes(candle_dir: Path) -> dict[tuple[str, str], tuple[np.ndarray, np.ndarray]]:
    """{(symbol, source): (t_open_s sorted, close aligned)} from every
    <SYM>_3600.parquet. Columns are strings in the store — cast here."""
    import pandas as pd  # local: keeps `--help` and the tests' pure paths cheap
    lanes: dict[tuple[str, str], tuple[np.ndarray, np.ndarray]] = {}
    for fp in sorted(glob.glob(str(candle_dir / f"*_{CANDLE_INTERVAL_S}.parquet"))):
        df = pd.read_parquet(fp)
        if df.empty:
            continue
        sym = str(df["symbol"].iloc[0])
        for src, g in df.groupby("source"):
            t = g["t_open_s"].astype(float).to_numpy()
            c = g["close"].astype(float).to_numpy()
            o = np.argsort(t, kind="stable")
            lanes[(sym, str(src))] = (t[o], c[o])
    return lanes


def close_at(lanes, sym: str, ts: float):
    """(t, c, i, source) for the first lane in LANE_PREF whose series has the
    bar opening at or after ts (index i, i >= 1) plus MIN_BARS_AHEAD bars
    beyond it; None when no lane covers the window."""
    for src in LANE_PREF:
        got = lanes.get((sym, src))
        if got is None:
            continue
        t, c = got
        i = int(np.searchsorted(t, ts, side="left"))
        if 0 < i < len(t) - MIN_BARS_AHEAD:
            return t, c, i, src
    return None


# --- scoring ---------------------------------------------------------------

def side_sign(side: str) -> float:
    return 1.0 if side == "buy" else -1.0


def score_fills(entries: Sequence[Row], lanes) -> tuple[list[Row], dict[str, int]]:
    """One scored row per coverable entry fill; every uncoverable fill is
    counted in the returned skip dict under its reason."""
    rows: list[Row] = []
    skipped: dict[str, int] = {"no_ref": 0, "no_bar": 0}
    for f in entries:
        ts = float(f["ts"])
        sym = str(f["symbol"]).split("/")[0]
        ref = _num(f.get("arrival_ref"))
        if ref <= 0:
            skipped["no_ref"] += 1
            continue
        got = close_at(lanes, sym, ts)
        if got is None:
            skipped["no_bar"] += 1
            continue
        t, c, i, src = got
        sgn = side_sign(str(f.get("side")))
        fp = _num(f.get("fill_price")) or ref
        r: Row = {
            "ts": ts, "sym": sym, "side": f.get("side"), "src": src,
            "maker": f.get("post_only") == "1",
            "era": f.get("exec_era") or "",
            "slip": _num(f.get("slip_bps")),
            "hour": int(ts // CANDLE_INTERVAL_S),
            "ref": ref, "fill": fp,
        }
        for name, h in HORIZONS.items():
            px = c[i + h - 1]
            r[name] = sgn * (px - ref) / ref * 1e4
            r["fill_" + name] = sgn * (px - fp) / fp * 1e4
        r["arr2fill"] = sgn * (fp - ref) / ref * 1e4
        for sh in PLACEBO_SHIFTS:
            j = i + sh
            if 0 < j < len(t) - MIN_BARS_AHEAD:
                pref_ = c[j - 1]
                for name, h in HORIZONS.items():
                    r[f"pl{sh:+d}_{name}"] = sgn * (c[j + h - 1] - pref_) / pref_ * 1e4
        rows.append(r)
    return rows, skipped


def group_stats(sub: Sequence[Row], keys: Sequence[str], hour_shift: int = 0) -> Row:
    """n, distinct fill-hours, and per-key mean/median/se/t with the SE
    deflated to DISTINCT HOURS (std ddof=1 / sqrt(hours)), never to n."""
    n = len(sub)
    hours = len({int(r["hour"]) + hour_shift for r in sub})
    stats: dict[str, Optional[Row]] = {}
    for k in keys:
        vals = np.array([float(r[k]) for r in sub if k in r], dtype=float)
        if vals.size < 2 or hours < 1:
            stats[k] = None
            continue
        se = float(vals.std(ddof=1) / np.sqrt(hours))
        mean = float(vals.mean())
        stats[k] = {"mean": mean, "median": float(np.median(vals)), "se": se,
                    "t": (mean / se) if se > 0 else None}
    return {"n": n, "hrs": hours, "stats": stats}


def _era_label(era: str) -> str:
    return era or "(pre-era)"


def _mean_or_none(vals: Sequence[float]) -> Optional[float]:
    return float(np.mean(vals)) if len(vals) else None


def build_candle_sections(rows: Sequence[Row]) -> Row:
    hk = list(HORIZONS)
    fk = ["fill_" + k for k in hk]

    def grp(tag: str, sub: Sequence[Row]) -> Row:
        g = group_stats(sub, hk)
        g.update({"tag": tag, "too_few": len(sub) < TOO_FEW})
        return g

    eras = sorted({r["era"] for r in rows})
    arrival = [grp("ALL entries", rows)]
    arrival += [grp(f"era {_era_label(e)}", [r for r in rows if r["era"] == e]) for e in eras]
    arrival += [grp("maker (post_only)", [r for r in rows if r["maker"]]),
                grp("taker", [r for r in rows if not r["maker"]]),
                grp("buy", [r for r in rows if r["side"] == "buy"]),
                grp("sell", [r for r in rows if r["side"] == "sell"])]
    symbols = sorted({r["sym"] for r in rows})
    per_symbol = [grp(s, [r for r in rows if r["sym"] == s]) for s in symbols]

    placebo = []
    for sh in PLACEBO_SHIFTS:
        keys = [f"pl{sh:+d}_{k}" for k in hk]
        sub = [r for r in rows if keys[0] in r]
        g = group_stats(sub, keys, hour_shift=sh)
        g["stats"] = {k: g["stats"][f"pl{sh:+d}_{k}"] for k in hk}
        g["shift"] = sh
        placebo.append(g)

    def dec(tag: str, sub: Sequence[Row]) -> Row:
        g = group_stats(sub, fk)
        g["stats"] = {k: g["stats"]["fill_" + k] for k in hk}
        g.update({"tag": tag, "too_few": len(sub) < TOO_FEW,
                  "arr2fill_mean": _mean_or_none([r["arr2fill"] for r in sub])})
        return g

    decomposition = [dec("ALL", rows),
                     dec("maker", [r for r in rows if r["maker"]]),
                     dec("taker", [r for r in rows if not r["maker"]])]
    decomposition += [dec(f"era {_era_label(e)}", [r for r in rows if r["era"] == e]) for e in eras]
    decomposition += [dec(s, [r for r in rows if r["sym"] == s]) for s in symbols]

    sl = [r["slip"] for r in rows]
    slip = {"mean": _mean_or_none(sl),
            "p50": float(np.median(sl)) if sl else None,
            "p95": float(np.quantile(sl, 0.95)) if sl else None,
            "maker_mean": _mean_or_none([r["slip"] for r in rows if r["maker"]]),
            "taker_mean": _mean_or_none([r["slip"] for r in rows if not r["maker"]])}
    return {"arrival_markout": arrival, "per_symbol": per_symbol,
            "placebo": placebo, "decomposition": decomposition, "slip": slip}


# --- tick mode -------------------------------------------------------------

def kraken_pair_for(symbol: str) -> str:
    """'BTC/USD' -> 'XBTUSD' (Kraken altname the public endpoints accept)."""
    asset, _, quote = symbol.partition("/")
    return f"{_KRAKEN_ASSET.get(asset, asset)}{quote or 'USD'}"


def parse_trades(result: Optional[dict]) -> tuple[list[tuple[float, float]], Optional[float]]:
    """Kraken Trades result -> ([(time_s, price)], last_s). Trade rows are
    [price, volume, time, side, ordertype, misc, id]; `last` is the ns
    cursor. Malformed rows are dropped, not raised."""
    if not isinstance(result, dict):
        return [], None
    trades: list[tuple[float, float]] = []
    for key, val in result.items():
        if key == "last" or not isinstance(val, list):
            continue
        for row in val:
            try:
                trades.append((float(row[2]), float(row[0])))
            except (TypeError, ValueError, IndexError):
                continue
    trades.sort()
    last_s: Optional[float] = None
    try:
        if result.get("last") is not None:
            last_s = int(str(result["last"])) / 1e9
    except (TypeError, ValueError):
        last_s = None
    if last_s is None and trades:
        last_s = trades[-1][0]
    return trades, last_s


def tick_horizon_prices(trades: Sequence[tuple[float, float]], fill_ts: float,
                        horizons_s: Sequence[int] = TICK_HORIZONS_S,
                        page_last_s: Optional[float] = None) -> dict[int, Optional[float]]:
    """Last trade price AT OR BEFORE fill_ts + h for each horizon. None when
    no trade precedes the horizon, or when the page does not reach it
    (page_last_s < fill_ts + h) — a later trade is never substituted."""
    ts_sorted = sorted(trades)
    times = np.array([t for t, _ in ts_sorted], dtype=float)
    out: dict[int, Optional[float]] = {}
    for h in horizons_s:
        target = fill_ts + h
        if page_last_s is not None and page_last_s < target:
            out[h] = None
            continue
        k = int(np.searchsorted(times, target, side="right"))
        out[h] = ts_sorted[k - 1][1] if k > 0 else None
    return out


def _build_public_feed(root: Path):
    """Credential-free KrakenFeed the way candle_backfill builds one
    (_strip_credentials blanks any env-resolved key STRUCTURALLY)."""
    from scripts.candle_backfill import build_feed, load_config
    return build_feed("kraken", load_config(root / "config.json"))


def fetch_trades_cached(fetch: Callable[[str, dict], Optional[dict]], symbol: str,
                        fill_ts: float, cache_dir: Path,
                        sleep: Callable[[float], None] = time.sleep,
                        state: Optional[dict] = None) -> tuple[Optional[dict], bool]:
    """(raw result, from_cache). Enforces TICK_SLEEP_S between NETWORK
    calls via state['last_call'] (monotonic); cache hits never sleep."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    # the asset comes from a CSV column: keep the filename inside cache_dir
    # whatever a corrupt row carries (no separators, no '..')
    asset = "".join(ch for ch in symbol.split("/")[0] if ch.isalnum()) or "UNKNOWN"
    path = cache_dir / f"{asset}_{fill_ts:.3f}.json"
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8")).get("result"), True
        except (OSError, ValueError):
            pass
    since_s = fill_ts - TICK_PRE_WINDOW_S
    st = state if state is not None else {}
    last = st.get("last_call")
    if last is not None:
        wait = TICK_SLEEP_S - (time.monotonic() - last)
        if wait > 0:
            sleep(wait)
    st["last_call"] = time.monotonic()
    result = fetch("Trades", {"pair": kraken_pair_for(symbol),
                              "since": str(int(since_s * 1e9)),
                              "count": TICK_PAGE_COUNT})
    if result is not None:
        path.write_text(json.dumps({"symbol": symbol, "fill_ts": fill_ts,
                                    "since_s": since_s, "result": result}),
                        encoding="utf-8")
    return result, False


def score_ticks(scored: Sequence[Row], fetch: Callable[[str, dict], Optional[dict]],
                cache_dir: Path, max_fills: int,
                sleep: Callable[[float], None] = time.sleep) -> Row:
    """Fill-price markout at TICK_HORIZONS_S for the first max_fills scored
    entries. Every fill and horizon not scored is counted under a reason."""
    skipped: dict[str, int] = defaultdict(int)
    per_h: dict[int, list[Row]] = {h: [] for h in TICK_HORIZONS_S}
    unit_ok = unit_checked = cache_hits = calls = 0
    state: dict = {}
    for r in list(scored)[:max(int(max_fills), 0)]:
        symbol = f"{r['sym']}/USD"
        result, cached = fetch_trades_cached(fetch, symbol, float(r["ts"]), cache_dir,
                                             sleep=sleep, state=state)
        cache_hits += int(cached)
        calls += int(not cached)
        if result is None:
            skipped["fetch_failed"] += 1
            continue
        trades, last_s = parse_trades(result)
        if not trades:
            skipped["empty_page"] += 1
            continue
        if not cached:
            unit_checked += 1
            unit_ok += int(abs(trades[0][0] - (float(r["ts"]) - TICK_PRE_WINDOW_S))
                           <= TICK_UNIT_TOLERANCE_S)
        prices = tick_horizon_prices(trades, float(r["ts"]), TICK_HORIZONS_S, last_s)
        sgn = side_sign(str(r["side"]))
        fp = float(r["fill"])
        for h, px in prices.items():
            if px is None:
                target = float(r["ts"]) + h
                skipped[f"{h}s_page_exhausted" if (last_s is not None and last_s < target)
                        else f"{h}s_no_trade"] += 1
                continue
            per_h[h].append({"hour": r["hour"], "v": sgn * (px - fp) / fp * 1e4})
    horizons: dict[str, Row] = {}
    for h, sub in per_h.items():
        g = group_stats(sub, ["v"])
        horizons[f"{h}s"] = {"n": g["n"], "hrs": g["hrs"], **(g["stats"]["v"] or
                             {"mean": None, "median": None, "se": None, "t": None})}
    return {"enabled": True, "max_fills": int(max_fills), "fills_attempted": min(len(scored), max(int(max_fills), 0)),
            "network_calls": calls, "cache_hits": cache_hits,
            "since_unit_checked": unit_checked, "since_unit_confirmed": unit_ok,
            "skipped": dict(skipped), "horizons": horizons}


def empty_ticks_section(max_fills: int = DEFAULT_MAX_FILLS) -> Row:
    return {"enabled": False, "max_fills": int(max_fills), "fills_attempted": 0,
            "network_calls": 0, "cache_hits": 0, "since_unit_checked": 0,
            "since_unit_confirmed": 0, "skipped": {},
            "horizons": {f"{h}s": {"n": 0, "hrs": 0, "mean": None, "median": None,
                                   "se": None, "t": None} for h in TICK_HORIZONS_S}}


# --- report ----------------------------------------------------------------

CAVEATS = [
    "SE deflated to distinct fill-hours, NOT to independent trades; "
    "cross-asset same-hour fills are still correlated -> SE optimistic.",
    "ALL/maker/taker/buy/sell/symbol lines POOL across exec eras (and across "
    "the cut-#9 fee correction); cite per-era lines for any era claim.",
    "arr->fill is limit distance (spread capture, fixed at fill, no forward "
    "information); fill->h is the toxicity term. Neither is an edge on its own.",
    "Bars are position-indexed within a lane: a gap in a lane's series "
    "stretches 'h bars ahead' past h hours for fills straddling it.",
]


def build_report(root: Path = ROOT, fills_path: Optional[Path] = None,
                 candle_dir: Optional[Path] = None, ticks: bool = False,
                 max_fills: int = DEFAULT_MAX_FILLS,
                 fetch: Optional[Callable[[str, dict], Optional[dict]]] = None,
                 sleep: Callable[[float], None] = time.sleep) -> Row:
    fills_path = fills_path or (root / "outputs" / "fills.csv")
    candle_dir = candle_dir or (root / "outputs" / "candles" / "parquet")
    read_at = _dt.datetime.now().isoformat(timespec="seconds")
    all_rows, entries = load_fills(fills_path)
    lanes = load_lanes(candle_dir) if candle_dir.exists() else {}
    scored, skipped = score_fills(entries, lanes)
    lanes_used = {s: sum(1 for r in scored if r["src"] == s) for s in LANE_PREF}
    # how many no_bar fills sit inside MIN_BARS_AHEAD bars of the store's
    # right edge (not yet coverable) vs. genuinely unlaned
    right_edge = max((float(t[-1]) for t, _ in lanes.values()), default=None)
    near_edge = 0
    if right_edge is not None:
        threshold = right_edge - MIN_BARS_AHEAD * CANDLE_INTERVAL_S
        near_edge = sum(1 for f in entries if _num(f.get("arrival_ref")) > 0
                        and close_at(lanes, str(f["symbol"]).split("/")[0], float(f["ts"])) is None
                        and float(f["ts"]) >= threshold)
    report: Row = {
        "read_at": read_at, "fills_path": str(fills_path), "candle_dir": str(candle_dir),
        "rows_total": len(all_rows), "entries_with_size": len(entries),
        "scored": len(scored), "skipped": skipped,
        "skipped_no_bar_near_right_edge": near_edge,
        "lanes_used": lanes_used, "lanes_loaded": len(lanes),
        "horizons": list(HORIZONS), "placebo_shifts": list(PLACEBO_SHIFTS),
        "min_bars_ahead": MIN_BARS_AHEAD, "too_few": TOO_FEW,
    }
    report.update(build_candle_sections(scored))
    if ticks:
        fetch_fn = fetch or _build_public_feed(root)._public_get
        report["ticks"] = score_ticks(scored, fetch_fn, root / "outputs" / TICK_CACHE_SUBDIR,
                                      max_fills, sleep=sleep)
    else:
        report["ticks"] = empty_ticks_section(max_fills)
    report["caveats"] = list(CAVEATS)
    return report


def _fmt_stats(g: Row, label: str = "") -> str:
    out = ""
    for k in HORIZONS:
        s = g["stats"].get(k)
        if s is None:
            out += f"| {label}{k} {'n/a':>8s} "
            continue
        t = f"{s['t']:+4.1f}" if s["t"] is not None else " n/a"
        out += f"| {label}{k} {s['mean']:+7.1f}bps med {s['median']:+6.1f} ({t}se) "
    return out


def render(rep: Row) -> str:
    L: list[str] = []
    L.append(f"[K] fills.csv rows {rep['rows_total']} read={rep['read_at']}  ({rep['fills_path']})")
    L.append(f"[K] entry fills with size>0: {rep['entries_with_size']}")
    L.append(f"[K] scored {rep['scored']}  skipped {rep['skipped']}  "
             f"(no_bar within {rep['min_bars_ahead']} bars of store right edge: "
             f"{rep['skipped_no_bar_near_right_edge']})  lanes used {rep['lanes_used']}")
    L.append("")
    L.append("=== signed markout from arrival_ref (bps; +=with us) ===")

    def line(g: Row) -> str:
        if g.get("too_few"):
            return f"  {g['tag']:34s} n={g['n']:4d}  (too few)"
        return f"  {g['tag']:34s} n={g['n']:4d} hrs={g['hrs']:4d} " + _fmt_stats(g)

    L += [line(g) for g in rep["arrival_markout"]]
    L.append("")
    L += [line(g) for g in rep["per_symbol"]]
    L.append("")
    L.append("=== PLACEBO: same fills/sides, bar index shifted (drift + side-mix control) ===")
    for g in rep["placebo"]:
        L.append(f"  shift {g['shift']:+3d}h                        n={g['n']:4d} hrs={g['hrs']:4d} "
                 + _fmt_stats(g))
    L.append("")
    L.append("=== DECOMPOSITION: arrival->fill (limit distance) vs fill->horizon (toxicity) ===")
    for g in rep["decomposition"]:
        if g.get("too_few"):
            L.append(f"  {g['tag']:16s} n={g['n']:4d}  (too few)")
            continue
        a = g["arr2fill_mean"]
        a_s = f"{a:+6.1f}" if a is not None else "   n/a"
        L.append(f"  {g['tag']:16s} n={g['n']:4d} hrs={g['hrs']:4d} arr->fill {a_s}bps "
                 + _fmt_stats(g, "fill->"))
    L.append("")
    sl = rep["slip"]

    def f2(v: Optional[float]) -> str:
        return f"{v:+.2f}" if v is not None else "n/a"

    L.append(f"[K] slip_bps entries: mean {f2(sl['mean'])} p50 {f2(sl['p50'])} p95 {f2(sl['p95'])}"
             f"  maker mean {f2(sl['maker_mean'])}  taker mean {f2(sl['taker_mean'])}")
    tk = rep["ticks"]
    if tk["enabled"]:
        L.append("")
        L.append("=== TICKS: markout from fill_price, Kraken public trades (bps; +=with us) ===")
        L.append(f"[K] fills attempted {tk['fills_attempted']} (cap {tk['max_fills']})  "
                 f"network calls {tk['network_calls']}  cache hits {tk['cache_hits']}  "
                 f"since-unit confirmed {tk['since_unit_confirmed']}/{tk['since_unit_checked']} fresh pages  "
                 f"skipped {tk['skipped']}")
        for h, s in tk["horizons"].items():
            if s["mean"] is None:
                L.append(f"  +{h:5s} n={s['n']:4d}  (n/a)")
                continue
            t = f"{s['t']:+4.1f}" if s["t"] is not None else " n/a"
            L.append(f"  +{h:5s} n={s['n']:4d} hrs={s['hrs']:4d} | {s['mean']:+7.1f}bps "
                     f"med {s['median']:+6.1f} ({t}se)")
    for c in rep["caveats"]:
        L.append(f"[D] {c}")
    return "\n".join(L)


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[1])
    ap.add_argument("--root", type=Path, default=ROOT, help="repo root (outputs/ lives under it)")
    ap.add_argument("--fills", type=Path, default=None, help="override outputs/fills.csv")
    ap.add_argument("--candles", type=Path, default=None,
                    help="override outputs/candles/parquet")
    ap.add_argument("--json", action="store_true", help="emit the full result dict as JSON")
    ap.add_argument("--ticks", action="store_true",
                    help="ALSO pull Kraken public trades (network) for sub-5-minute markout")
    ap.add_argument("--max-fills", type=int, default=DEFAULT_MAX_FILLS,
                    help="cap on fills scored in --ticks mode")
    a = ap.parse_args(argv)
    rep = build_report(root=a.root, fills_path=a.fills, candle_dir=a.candles,
                       ticks=a.ticks, max_fills=a.max_fills)
    if a.json:
        print(json.dumps(rep, indent=1, default=str))
    else:
        print(render(rep))
    return 0


if __name__ == "__main__":
    sys.exit(main())
