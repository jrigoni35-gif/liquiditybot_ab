"""scripts/target_book_replay.py - grade the SHADOW target book + idea lab on
real Kraken OHLC (SAFE: measurement only; places nothing).

    python scripts/target_book_replay.py                 # 4h bars, ~120 days
    python scripts/target_book_replay.py --interval 1440 # daily, ~2 years
    python scripts/target_book_replay.py --csv-dir DIR   # offline: DIR/<ASSET>.csv

Arms compared on the SAME bars and the SAME fill model (maker limit at the
decision close, filled only if the next bar trades THROUGH it, maker fee on
the fill; unfilled orders lapse):

  buy_hold      equal-weight basket bought once, never touched
  no_band       rebalance to target every bar (gamma -> inf: band ~ 0,
                aim 1) - what trading WITHOUT the band costs
  target_book   the configured book (band + aim, no tilt)
  idea lab      the market-reactive population, forward-graded, DSR-deflated
                over every idea ever born

Units: a STEP is one bar decided-and-settled; an IDEA is one family member
born into a paper book. Reconciliation: born = alive + retired.
Nothing here is a promotion; see docs/quant/2026-10-01_target_book_shadow_design.md.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.idea_lab import Bars, Idea, IdeaLab, ShadowBook, grade, step_book  # noqa: E402
from core.target_book import BookParams, PressureLimits  # noqa: E402

KRAKEN_PAIR = {"BTC": "XBTUSD", "ETH": "ETHUSD", "PAXG": "PAXGUSD",
               "LINK": "LINKUSD", "SOL": "SOLUSD", "XRP": "XRPUSD"}
OHLC_URL = "https://api.kraken.com/0/public/OHLC?pair={pair}&interval={iv}"


def default_out_dir() -> Path:
    return ROOT / "outputs" / "reports" / "target_book"


def fetch_kraken(asset: str, interval_min: int) -> list:
    """[(t_open_s, high, low, close)] from Kraken's PUBLIC endpoint (read-only
    market data; no credentials, no private endpoint)."""
    pair = KRAKEN_PAIR.get(asset, f"{asset}USD")
    url = OHLC_URL.format(pair=pair, iv=interval_min)
    req = urllib.request.Request(url, headers={"User-Agent": "liquiditybot-replay"})
    with urllib.request.urlopen(req, timeout=30) as r:  # nosec B310 - fixed https host
        d = json.loads(r.read().decode("utf-8"))
    if d.get("error"):
        raise RuntimeError(f"{asset}: {d['error']}")
    key = next(k for k in d["result"] if k != "last")
    rows = d["result"][key]
    # The last row is the still-forming bar: drop it (it is not a close).
    return [(int(x[0]), float(x[2]), float(x[3]), float(x[4])) for x in rows[:-1]]


def load_csv(path: Path) -> list:
    with path.open(encoding="utf-8", newline="") as f:
        return [(int(float(r["t_open_s"])), float(r["high"]), float(r["low"]),
                 float(r["close"])) for r in csv.DictReader(f)]


def save_csv(path: Path, rows: list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["t_open_s", "high", "low", "close"])
        w.writerows(rows)


def align(series: dict) -> Bars:
    common = sorted(set.intersection(*(set(r[0] for r in v) for v in series.values())))
    idx = {a: {r[0]: r for r in v} for a, v in series.items()}
    return Bars(t=common,
                high={a: [idx[a][t][1] for t in common] for a in series},
                low={a: [idx[a][t][2] for t in common] for a in series},
                close={a: [idx[a][t][3] for t in common] for a in series})


def params_from(cfg: dict) -> tuple:
    tb = cfg["target_book"]
    p = tb["pressure"]
    base = BookParams(gamma=float(tb["gamma"]), aim_rate=float(tb["aim_rate"]),
                      tilt_cap=float(tb["tilt_cap"]), weighting=tb["weighting"],
                      invest_frac=float(tb["invest_frac"]),
                      min_order_usd=float(tb["min_order_usd"]),
                      maker_fee_bps=float(cfg["pretrade"]["maker_fee_bps"]))
    lim = PressureLimits(**{k: float(v) for k, v in p.items() if not k.startswith("_")})
    lab_cfg = {**{k: v for k, v in tb.items() if k not in ("idea_lab", "pressure")},
               **tb["idea_lab"]}
    return base, lim, lab_cfg


def buy_hold(bars: Bars, cash: float, base: BookParams) -> dict:
    fee = base.maker_fee_bps / 1e4
    per = cash * base.invest_frac / len(bars.close)
    units = {a: per / c[0] / (1 + fee) for a, c in bars.close.items()}
    rest = cash - per * len(bars.close)
    eq = [rest + sum(u * bars.close[a][i] for a, u in units.items())
          for i in range(len(bars))]
    return {"cum_return": eq[-1] / cash - 1.0, "fees_usd": per * len(units) * fee / (1 + fee),
            "max_drawdown": _mdd(eq)}


def run_arm(bars: Bars, idea: Idea, cash: float, base: BookParams,
            cfg: dict, lim: PressureLimits, warm: int) -> dict:
    b = ShadowBook(idea, warm, cash, {}, cash)
    eq = [cash]
    for i in range(warm, len(bars) - 1):
        step_book(b, bars, i, base, cfg, lim)
        eq.append(b.equity({a: c[i + 1] for a, c in bars.close.items()}))
    g = grade(b, 1)
    g["max_drawdown"] = _mdd(eq)
    return g


def _mdd(eq: list) -> float:
    peak, worst = eq[0], 0.0
    for v in eq:
        peak = max(peak, v)
        worst = max(worst, 1.0 - v / peak if peak > 0 else 0.0)
    return worst


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--config", default=str(ROOT / "config.json"))
    ap.add_argument("--interval", type=int, default=None, help="bar minutes")
    ap.add_argument("--csv-dir", default=None)
    ap.add_argument("--cash", type=float, default=800.0)
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)

    cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))
    tb = cfg["target_book"]
    iv = int(args.interval or tb["bar_interval_min"])
    out_dir = Path(args.out) if args.out else default_out_dir()
    series = {}
    for a in tb["assets"]:
        if args.csv_dir:
            series[a] = load_csv(Path(args.csv_dir) / f"{a}.csv")
        else:
            series[a] = fetch_kraken(a, iv)
            save_csv(out_dir / f"ohlc_{iv}m" / f"{a}.csv", series[a])
            time.sleep(1.1)                       # public-endpoint courtesy
    bars = align(series)
    base, lim, lab_cfg = params_from(cfg)
    warm = int(lab_cfg["sigma_lookback_bars"])
    if len(bars) <= warm + 2:
        print(f"only {len(bars)} aligned bars; need > {warm + 2}")
        return 1
    try:
        from ml.overfit import deflated_sharpe as dsr_fn
    except Exception:  # noqa: BLE001 - report without DSR rather than die
        dsr_fn = None

    arms = {
        "buy_hold": buy_hold(Bars(bars.t[warm:], {a: v[warm:] for a, v in bars.high.items()},
                                  {a: v[warm:] for a, v in bars.low.items()},
                                  {a: v[warm:] for a, v in bars.close.items()}),
                             args.cash, base),
        "no_band": run_arm(bars, Idea(1e12, 1.0, base.weighting, "none"),
                           args.cash, base, lab_cfg, lim, warm),
        "target_book": run_arm(bars, Idea(base.gamma, base.aim_rate,
                                          base.weighting, "none"),
                               args.cash, base, lab_cfg, lim, warm),
    }
    lab = IdeaLab(lab_cfg, base, lim, args.cash)
    for i in range(warm, len(bars) - 1):
        lab.step(bars, i)
    rep = lab.report(dsr_fn)

    span_d = (bars.t[-1] - bars.t[warm]) / 86400
    print(f"target_book replay: {len(tb['assets'])} assets {tb['assets']}, "
          f"{iv}m bars, {len(bars) - 1 - warm} steps (~{span_d:.0f} days), "
          f"maker {base.maker_fee_bps:g} bps, start ${args.cash:,.0f}")
    print(f"{'arm':<13}{'return':>9}{'fees $':>9}{'traded $':>11}"
          f"{'fills/att':>11}{'max DD':>8}")
    for k, r in arms.items():
        fa = f"{r.get('fills', '-')}/{r.get('attempts', '-')}" if "fills" in r else "-"
        print(f"{k:<13}{r['cum_return']:>+9.2%}{r['fees_usd']:>9.2f}"
              f"{r.get('traded_usd', 0):>11,.0f}{fa:>11}{r['max_drawdown']:>8.1%}")
    print(f"\nidea lab: family {rep['family_size']}, born {rep['n_trials']} = "
          f"alive {rep['alive']} + retired {rep['retired']} "
          f"[{'OK' if rep['n_trials'] == rep['alive'] + rep['retired'] else 'MISMATCH'}]"
          f"  (DSR deflated over {rep['n_trials']} trials)")
    print(f"{'idea':<34}{'born':>6}{'steps':>7}{'return':>9}{'bench':>9}"
          f"{'fees $':>8}{'DSR':>7}  status")
    for r in sorted(rep["ideas"], key=lambda r: -(r["cum_return"] - r["cum_bench"])):
        dsr = f"{r['dsr']:.2f}" if r["dsr"] is not None else "-"
        print(f"{r['id']:<34}{r['born_i']:>6}{r['steps']:>7}"
              f"{r['cum_return']:>+9.2%}{r['cum_bench']:>+9.2%}"
              f"{r['fees_usd']:>8.2f}{dsr:>7}  {r['status']}")
    births = [e for e in rep["events"] if e[1] == "IL-000"]
    print("\nbirth triggers: " + ", ".join(sorted({e[3] for e in births})))
    print("NOTE: shadow measurement. EVIDENCE is not a promotion; promotion is "
          "an operator decision record and forks the cohort.")
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    path = out_dir / f"replay_{iv}m_{stamp}.json"
    path.write_text(json.dumps({"interval_min": iv, "assets": tb["assets"],
                                "steps": len(bars) - 1 - warm, "arms": arms,
                                "lab": rep}, indent=1, default=str),
                    encoding="utf-8")
    print(f"wrote {path.relative_to(ROOT) if path.is_relative_to(ROOT) else path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
