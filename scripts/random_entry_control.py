"""scripts/random_entry_control.py - is there ANY entry-timing signal?

THE QUESTION, pre-registered before the answer was known. 87% of this bot's
trades reached a positive favourable excursion, which was once read as
evidence the entries find moves. Research flagged the trap: over hours on
5-minute bars nearly EVERY entry - including a random one - touches some
positive MFE by diffusion. The statistic is uninformative without a
control, and the control had never been run. This is it.

METHOD.

  PRICES  Real Kraken 5-minute OHLC reconstructed from the feed recordings
          (outputs/recordings/session_*.jsonl): every kraken.get_candles
          response carries a 720-bar window; the union across sessions plus
          lookback yields a continuous per-asset series, with runner
          downtime backfilled by later calls' history.
  REAL    Every fully-closed position in the (audit-verified) fills.csv:
          entry time, direction, and DURATION from first entry fill to last
          exit fill.
  CONTROL For each real trade, K random entry times on the SAME asset with
          the SAME duration and direction, drawn uniformly over the covered
          span (seeded - deterministic across runs).
  MFE     For longs, best high vs entry over the window; for shorts, best
          low. BOTH arms enter at the containing bar's close, so the
          comparison isolates TIMING - the actual fill price adds execution
          edge, which is a different question and reported separately.

THE ONE NUMBER: each real trade's percentile within its own control
distribution. Mean percentile ~0.5 means the entries time the market no
better than a random-number generator at the same horizons - and then no
entry-model improvement is the binding lever, which is what the payoff-
asymmetry finding already implies from the other direction. Materially
above 0.5 means timing signal exists and is being lost downstream.

    python scripts/random_entry_control.py [--json] [--per-trade 200]

Report-only. Reads recordings and fills.csv, writes nothing.
"""
import argparse
import csv
import json
import math
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
BAR_SEC = 300.0          # kraken.get_candles bar spacing (5-minute bars)
COVERAGE_MIN = 0.8       # window must have >= this fraction of its bars


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (p, max(0.0, c - h), min(1.0, c + h))


def harvest_candles(rec_dir: Path, keep_every: int = 12) -> dict:
    """Per-asset {bar_time: (high, low, close)} union across all sessions.

    Adjacent get_candles responses overlap by ~719 of 720 bars, so parsing
    every one re-reads the same window hundreds of times; every 12th call
    per asset still overlaps the previous kept window by >95%."""
    out = defaultdict(dict)
    seen = defaultdict(int)
    files = sorted(p for p in rec_dir.glob("session_*.jsonl"))
    for p in files:
        with open(p, encoding="utf-8") as f:
            for ln in f:
                if '"get_candles"' not in ln:
                    continue
                try:
                    r = json.loads(ln)
                except json.JSONDecodeError:
                    continue
                if r.get("method") != "get_candles":
                    continue
                args = r.get("args") or []
                asset = str(args[0])[:-3] if args and \
                    str(args[0]).endswith("USD") else None
                if not asset:
                    continue
                seen[asset] += 1
                if (seen[asset] - 1) % keep_every:
                    continue
                res = r.get("result")
                if not isinstance(res, list):
                    continue
                book = out[asset]
                for bar in res:
                    try:
                        book[int(bar["time"])] = (float(bar["high"]),
                                                  float(bar["low"]),
                                                  float(bar["close"]))
                    except (KeyError, TypeError, ValueError):
                        continue
    return {a: b for a, b in out.items() if len(b) >= 100}


def load_trades(fills_path: Path) -> list:
    """Fully-closed positions: (asset, direction, t0, duration)."""
    by_pid = defaultdict(list)
    with open(fills_path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r.get("position_id"):
                by_pid[r["position_id"]].append(r)
    trades = []
    for fills in by_pid.values():
        ent = [r for r in fills if r.get("purpose") == "entry"]
        ext = [r for r in fills if r.get("purpose") == "exit"]
        if not ent or not ext:
            continue
        try:
            ez = sum(float(r["fill_size"]) for r in ent)
            xz = sum(float(r["fill_size"]) for r in ext)
            if ez <= 0 or abs(xz - ez) / ez > 0.02:
                continue
            t0 = min(float(r["ts"]) for r in ent)
            t1 = max(float(r["ts"]) for r in ext)
            px = sum(float(r["fill_size"]) * float(r["fill_price"])
                     for r in ent) / ez
        except (KeyError, TypeError, ValueError, ZeroDivisionError):
            continue
        if t1 <= t0:
            continue
        trades.append({
            "asset": str(fills[0].get("symbol", "")).split("/")[0],
            "long": ent[0].get("side") == "buy",
            "t0": t0, "dur": max(t1 - t0, BAR_SEC), "fill_px": px})
    return trades


def window_mfe(book_keys, book, t0: float, dur: float, long: bool):
    """(mfe_pct, mae_pct, entry_close) over (t0, t0+dur], or None when the
    series does not cover the window densely enough for the answer to mean
    anything - a sparse window silently understates MFE."""
    i0 = np.searchsorted(book_keys, t0, side="right") - 1
    if i0 < 0:
        return None
    entry_bar = book_keys[i0]
    if t0 - entry_bar > 2 * BAR_SEC:
        return None                      # entry falls in a data gap
    i1 = np.searchsorted(book_keys, t0 + dur, side="right")
    win = book_keys[i0 + 1:i1]
    if len(win) < max(1, COVERAGE_MIN * dur / BAR_SEC):
        return None
    entry = book[entry_bar][2]
    his = np.array([book[t][0] for t in win])
    los = np.array([book[t][1] for t in win])
    if long:
        mfe = float(his.max() / entry - 1.0)
        mae = float(los.min() / entry - 1.0)
    else:
        mfe = float(1.0 - los.min() / entry)
        mae = float(1.0 - his.max() / entry)
    return (100.0 * mfe, 100.0 * mae, entry)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--recordings", default=str(ROOT / "outputs" /
                                                "recordings"))
    ap.add_argument("--fills", default=str(ROOT / "outputs" / "fills.csv"))
    ap.add_argument("--per-trade", type=int, default=200,
                    help="random control entries per real trade")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--json", action="store_true")
    ns = ap.parse_args()

    books = harvest_candles(Path(ns.recordings))
    if not books:
        print("no candle data recoverable from recordings")
        return 1
    keys = {a: np.array(sorted(b)) for a, b in books.items()}
    trades = load_trades(Path(ns.fills))
    rng = np.random.default_rng(ns.seed)

    pct, real_mfe, ctrl_mfe, real_mae = [], [], [], []
    skipped_cover = skipped_asset = 0
    for t in trades:
        a = t["asset"]
        if a not in books:
            skipped_asset += 1
            continue
        k, b = keys[a], books[a]
        real = window_mfe(k, b, t["t0"], t["dur"], t["long"])
        if real is None:
            skipped_cover += 1
            continue
        lo, hi = float(k[0]), float(k[-1]) - t["dur"] - BAR_SEC
        if hi <= lo:
            skipped_cover += 1
            continue
        ctl = []
        tries = 0
        while len(ctl) < ns.per_trade and tries < ns.per_trade * 4:
            tries += 1
            r = window_mfe(k, b, float(rng.uniform(lo, hi)), t["dur"],
                           t["long"])
            if r is not None:
                ctl.append(r[0])
        if len(ctl) < ns.per_trade // 2:
            skipped_cover += 1
            continue
        ctl_arr = np.array(ctl)
        pct.append(float((ctl_arr < real[0]).mean()
                         + 0.5 * (ctl_arr == real[0]).mean()))
        real_mfe.append(real[0])
        real_mae.append(real[1])
        ctrl_mfe.append(float(np.median(ctl_arr)))

    n = len(pct)
    if n == 0:
        print("no real trade fell inside the recorded price coverage")
        return 1
    pct_a = np.array(pct)
    beats = int((pct_a > 0.5).sum())
    p, plo, phi = wilson(beats, n)
    res = {
        "n_trades_scored": n,
        "skipped_no_asset_series": skipped_asset,
        "skipped_coverage": skipped_cover,
        "mean_percentile": float(pct_a.mean()),
        "se_percentile": float(pct_a.std(ddof=1) / math.sqrt(n))
        if n > 1 else 0.0,
        "p_beats_control_median": p,
        "p_beats_ci": [plo, phi],
        "median_real_mfe_pct": float(np.median(real_mfe)),
        "median_control_mfe_pct": float(np.median(ctrl_mfe)),
        "median_real_mae_pct": float(np.median(real_mae)),
        "assets_covered": sorted(books),
        "per_trade_controls": ns.per_trade, "seed": ns.seed,
    }
    if ns.json:
        print(json.dumps(res, indent=1))
        return 0

    lo95 = res["mean_percentile"] - 1.96 * res["se_percentile"]
    hi95 = res["mean_percentile"] + 1.96 * res["se_percentile"]
    print("RANDOM-ENTRY CONTROL - entry timing vs matched random entries")
    print("=" * 68)
    print("%d real trades scored (%d skipped: outside recorded coverage, "
          "%d: no series)" % (n, skipped_cover, skipped_asset))
    print("assets: %s" % ", ".join(res["assets_covered"]))
    print("\n  mean MFE percentile vs own control  %.3f  [%.3f, %.3f] 95%%"
          % (res["mean_percentile"], lo95, hi95))
    print("  P(real beats control median)        %.3f  [%.3f, %.3f]"
          % (p, plo, phi))
    print("  median MFE   real %+8.3f%%   control %+.3f%%"
          % (res["median_real_mfe_pct"], res["median_control_mfe_pct"]))
    print("  median MAE   real %+8.3f%%" % res["median_real_mae_pct"])

    print("\n" + "=" * 68)
    if lo95 <= 0.5 <= hi95:
        print("NO TIMING SIGNAL DETECTABLE. The entries' favourable")
        print("excursions are statistically indistinguishable from random")
        print("entries at the same horizons - the 87%-positive-MFE figure")
        print("was diffusion, as the null predicted. Entry-model work is")
        print("not the lever; this closes the question from the other")
        print("side of the payoff-asymmetry finding.")
    elif res["mean_percentile"] > 0.5:
        print("TIMING SIGNAL PRESENT: real entries sit at the %.0fth"
              % (100 * res["mean_percentile"]))
        print("percentile of their own controls. The entries DO find")
        print("better-than-random moments, and the losses happen after")
        print("entry - exit geometry and cost are where the edge leaks.")
    else:
        print("ENTRIES ARE WORSE THAN RANDOM (mean percentile %.3f)."
              % res["mean_percentile"])
        print("The gates are selecting into adverse moments - anti-signal.")
        print("Inverting nothing; measure which gate drives it first.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
