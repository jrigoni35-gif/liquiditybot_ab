"""scripts/mm_viability_report.py - can this bot earn the spread as a maker?
(SAFE: measurement only; places nothing; reads public, read-only prices.)

    python scripts/mm_viability_report.py

THE QUESTION (docs/quant/2026-10-02_feature_program.md, item 5). Liquidity
provision is the institutional edge that needs no forecast: a maker earns
half the quoted spread per fill and loses whatever informed flow does to the
price right after the fill (adverse selection). Per maker fill:

    net_bps = half_spread_bps + alpha_bps(h) - maker_fee_bps

half_spread  the spread the bot itself observed on Kraken for that asset
             (signal_history.csv `spread_bps`, median per asset) / 2
alpha(h)     scripts/adverse_selection.py's spread-neutral mid-to-mid
             mark-out (its sign convention, reused, not re-derived), here
             at 5-minute resolution on independent Binance 5m bars - the
             sub-hour pick-off that tool says it cannot observe (1h grid)
maker_fee    config pretrade.maker_fee_bps (the booked tier, 15)

REGISTERED (2026-10-02, before the first run): fills = every post_only
ORDER in the bot's fills.csv (partials aggregated - corrected after code
review; the first run counted partial legs) (paper fills from the dry-run simulator: they fill
when the market trades THROUGH the resting price, which is the event
adverse selection is about - stated as a limit, not hidden); anchor = close
of the 5m bar CONTAINING the fill; horizons 5, 15, 60, 240 min; day-cluster
bootstrap (adverse_selection.daycluster_bootstrap, 5,000 reps, seed 7).
Viable for an asset iff the 95% CI of net_bps at 60 min is entirely > 0
with >= 30 fills. Unit: one MAKER FILL (leg).
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.adverse_selection import alpha_bps, daycluster_bootstrap  # noqa: E402
from scripts.alpha_decay_report import (BOT_MONTHS, binance_klines,  # noqa: E402
                                        entry_index, to_seconds)

HORIZONS_MIN = (5, 15, 60, 240)
DECISION_H = 60
MIN_FILLS = 30


def load_maker_fills(path: Path) -> list:
    """One record per maker ORDER (CS-1 unit): partial fills of the same
    order_id are aggregated - size-weighted price, first fill time. Counting
    partials as separate fills inflated n and weighted orders by their
    partial count (review finding 10)."""
    orders: dict = {}
    with path.open(encoding="utf-8", newline="") as f:
        for i, r in enumerate(csv.DictReader(f)):
            if str(r.get("post_only", "")).strip() not in ("1", "1.0", "True"):
                continue
            try:
                ts, px = float(r["ts"]), float(r["fill_price"])
                qty = float(r.get("fill_size") or 1.0)
            except (KeyError, ValueError):
                continue
            key = r.get("order_id") or f"row{i}"
            o = orders.setdefault(key, {"ts": ts, "asset": r["symbol"].split("/")[0],
                                        "side": r["side"], "purpose": r["purpose"],
                                        "q": 0.0, "pq": 0.0})
            o["ts"] = min(o["ts"], ts)
            o["q"] += qty
            o["pq"] += px * qty
    out = [{"ts": o["ts"], "asset": o["asset"], "side": o["side"], "purpose": o["purpose"],
            "price": o["pq"] / o["q"] if o["q"] > 0 else 0.0} for o in orders.values()]
    if out:
        ts_s, _ = to_seconds(np.array([x["ts"] for x in out]))
        for x, t in zip(out, ts_s, strict=True):
            x["ts"] = float(t)
    return out


def median_half_spread(path: Path) -> dict:
    import pandas as pd
    d = pd.read_csv(path, usecols=["asset", "spread_bps"], low_memory=False)
    d = d[d["spread_bps"] > 0]
    return {a: float(g["spread_bps"].median()) / 2 for a, g in d.groupby("asset")}


def markouts(fills: list, cache: Path, counts: dict | None = None) -> dict:
    """{asset: [(ts, {h: alpha_bps})]} on Binance 5m closes. `counts`, if
    given, receives the CS-1 buckets every order lands in."""
    c = counts if counts is not None else {}
    for k in ("marked", "asset_not_on_binance", "outside_price_data", "no_full_horizon"):
        c.setdefault(k, 0)
    out = {}
    for a in sorted({f["asset"] for f in fills}):
        mine = [x for x in fills if x["asset"] == a]
        d = binance_klines(f"{a}USDT", "5m", BOT_MONTHS, cache)
        if len(d["close"]) < 1000:
            c["asset_not_on_binance"] += len(mine)
            continue
        cl = d["close"]
        rows = []
        for f in mine:
            j = int(entry_index(d["t"], np.array([f["ts"]]))[0])
            if j < 0 or f["ts"] - d["t"][j] > 300:
                c["outside_price_data"] += 1
                continue
            al = {}
            for h in HORIZONS_MIN:
                k = j + h // 5
                if k < len(cl):
                    al[h] = alpha_bps(f["side"], cl[j], cl[k])
            if len(al) == len(HORIZONS_MIN):
                rows.append((f["ts"], al))
                c["marked"] += 1
            else:
                c["no_full_horizon"] += 1
        out[a] = rows
    return out


def assess(fills_path: Path, sh_path: Path, maker_fee_bps: float,
           cache: Path) -> dict:
    from core.cohort import reconcile
    fills = load_maker_fills(fills_path)
    hs = median_half_spread(sh_path)
    counts: dict = {}
    mk = markouts(fills, cache, counts)
    res = {"maker_fee_bps": maker_fee_bps, "unit": "maker order (partials aggregated)",
           "fills_post_only": len(fills), "fills_marked": counts["marked"],
           "reconcile": reconcile(len(fills), counts)["line"], "assets": {}}
    pooled_t, pooled = [], {h: [] for h in HORIZONS_MIN}
    for a, rows in mk.items():
        if not rows:
            continue
        half = hs.get(a)
        t = [r[0] for r in rows]
        row = {"fills": len(rows), "half_spread_bps": half, "alpha": {}}
        for h in HORIZONS_MIN:
            v = [r[1][h] for r in rows]
            row["alpha"][h] = daycluster_bootstrap(t, v)
            pooled[h] += v
        if half is not None:
            net = [half + r[1][DECISION_H] - maker_fee_bps for r in rows]
            row["net_60m"] = daycluster_bootstrap(t, net)
            ci = row["net_60m"].get("ci95_boot", [0, 0])
            row["viable"] = bool(len(rows) >= MIN_FILLS and ci[0] > 0)
            row["break_even_half_spread_bps"] = maker_fee_bps - float(np.mean(
                [r[1][DECISION_H] for r in rows]))
        res["assets"][a] = row
        pooled_t += t
    res["pooled_alpha"] = {h: daycluster_bootstrap(pooled_t, pooled[h]) for h in HORIZONS_MIN}
    return res


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--fills", default=str(ROOT / "outputs" / "imported_sessions" / "pc-live" / "fills.csv"))
    ap.add_argument("--signals", default=str(ROOT / "outputs" / "signal_history.csv"))
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)
    cfg = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    fee = float(cfg["pretrade"]["maker_fee_bps"])
    out_dir = Path(args.out) if args.out else ROOT / "outputs" / "reports" / "mm_viability"
    res = assess(Path(args.fills), Path(args.signals), fee,
                 ROOT / "outputs" / "reports" / "alpha_decay" / "cache")
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"mm_viability_{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}.json"
    path.write_text(json.dumps(res, indent=1, default=str), encoding="utf-8")
    print(f"unit: {res['unit']}; {res['reconcile']}; maker fee {fee:g} bps")
    print("pooled alpha after a maker fill (bps, day-cluster CI):")
    for h, s in res["pooled_alpha"].items():
        print(f"  {h:>4} min  mean {s.get('mean', float('nan')):+7.2f}  CI {s.get('ci95_boot')}")
    print(f"{'asset':<6}{'fills':>6}{'half-spread':>12}{'alpha60':>9}{'net60 mean':>11}"
          f"{'net60 CI':>20}{'break-even half-spread':>24}  viable")
    for a, r in sorted(res["assets"].items(), key=lambda kv: -kv[1]["fills"]):
        n = r.get("net_60m", {})
        hs = r["half_spread_bps"]
        print(f"{a:<6}{r['fills']:>6}{(hs if hs is not None else float('nan')):>12.1f}"
              f"{r['alpha'][DECISION_H].get('mean', float('nan')):>+9.2f}"
              f"{n.get('mean', float('nan')):>+11.2f}{str(n.get('ci95_boot')):>20}"
              f"{r.get('break_even_half_spread_bps', float('nan')):>24.1f}  {r.get('viable')}")
    print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
