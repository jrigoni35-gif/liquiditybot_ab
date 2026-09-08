"""monitor/book.py — Kraken order-book structure for a pair (read-only).

The CEX half of the market-microstructure method: the vendored skill has no
order book (AMMs have none). This module supplies depth bands, wall
inventory, slippage curves, an exit estimate for a position, and wall
dynamics between two snapshots taken N seconds apart.

Pure functions take `bids` / `asks` as lists of (price, qty) floats, best
first. `snapshot()` fetches them from Kraken's public Depth endpoint.

CLI::

    python monitor/book.py --pair FLOWUSD
    python monitor/book.py --pair FLOWUSD --watch-seconds 75 --exit-units 74693.88 --avg 0.02937
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.request
from typing import Any

KRAKEN = "https://api.kraken.com/0/public"
TIMEOUT = 30
WALL_USD = 3000.0
Level = tuple[float, float]


def _get(endpoint: str, query: str) -> dict:
    url = f"{KRAKEN}/{endpoint}?{query}"
    if not url.startswith("https://api.kraken.com/"):  # pin scheme AND host
        raise ValueError(f"refusing non-Kraken URL: {url!r}")
    with urllib.request.urlopen(url, timeout=TIMEOUT) as fh:  # noqa: S310  # nosec B310
        payload = json.loads(fh.read().decode())
    if payload.get("error"):
        raise RuntimeError(f"kraken {endpoint}: {payload['error']}")
    return payload["result"]


def snapshot(pair: str, count: int = 500) -> tuple[list[Level], list[Level]]:
    res = _get("Depth", f"pair={pair}&count={count}")
    dp = next(v for k, v in res.items())
    bids = [(float(p), float(q)) for p, q, _ in dp["bids"]]
    asks = [(float(p), float(q)) for p, q, _ in dp["asks"]]
    return bids, asks


def mid_price(bids: list[Level], asks: list[Level]) -> float:
    return (bids[0][0] + asks[0][0]) / 2


def usd(levels: list[Level]) -> float:
    return sum(p * q for p, q in levels)


def depth_bands(
    bids: list[Level],
    asks: list[Level],
    edges: tuple[float, ...] = (0.5, 1, 2, 3, 5, 10, 25),
) -> list[dict[str, float]]:
    """Resting USD per distance band from mid, with (bid-ask)/(bid+ask) imbalance."""
    mid = mid_price(bids, asks)
    out = []
    lo = 0.0
    for hi in edges:
        b = usd([x for x in bids if lo < (1 - x[0] / mid) * 100 <= hi])
        a = usd([x for x in asks if lo < (x[0] / mid - 1) * 100 <= hi])
        out.append(
            {
                "lo_pct": lo,
                "hi_pct": hi,
                "bid_usd": b,
                "ask_usd": a,
                "imbalance": (b - a) / (b + a) if b + a else 0.0,
            }
        )
        lo = hi
    return out


def cumulative(bids: list[Level], asks: list[Level], pct: float) -> dict[str, float]:
    mid = mid_price(bids, asks)
    b = usd([x for x in bids if x[0] >= mid * (1 - pct / 100)])
    a = usd([x for x in asks if x[0] <= mid * (1 + pct / 100)])
    return {
        "pct": pct,
        "bid_usd": b,
        "ask_usd": a,
        "ratio": b / a if a else float("inf"),
    }


def walls(levels: list[Level], min_usd: float = WALL_USD) -> list[Level]:
    return [(p, q) for p, q in levels if p * q >= min_usd]


def slippage(levels: list[Level], amount_usd: float) -> dict[str, float] | None:
    """Average fill price, worst level, and units for a taker order of amount_usd.

    Pass asks for a buy, bids for a sell. None if the visible book cannot
    absorb the amount.
    """
    rem, units, worst = amount_usd, 0.0, None
    for p, q in levels:
        take = min(rem, p * q)
        units += take / p
        rem -= take
        worst = p
        if rem <= 1e-9:
            break
    if rem > 1e-9 or worst is None:
        return None
    return {
        "amount_usd": amount_usd,
        "avg": amount_usd / units,
        "worst": worst,
        "units": units,
    }


def exit_estimate(
    bids: list[Level], units: float, avg_cost: float, taker_fee: float = 0.0038
) -> dict[str, float] | None:
    """Proceeds and realised P&L for market-selling `units` into the bids."""
    rem, proceeds, worst = units, 0.0, None
    for p, q in bids:
        take = min(rem, q)
        proceeds += p * take
        rem -= take
        worst = p
        if rem <= 1e-9:
            break
    if rem > 1e-9 or worst is None:
        return None
    net = proceeds * (1 - taker_fee)
    return {
        "avg_fill": proceeds / units,
        "worst": worst,
        "proceeds": net,
        "cost": units * avg_cost,
        "pnl": net - units * avg_cost,
    }


def wall_dynamics(
    before: list[Level],
    after: list[Level],
    min_usd: float = WALL_USD,
    tol: float = 0.02,
) -> list[dict[str, Any]]:
    """Per-wall change between two snapshots: new / pulled / grew / shrank / held."""
    wa = dict(walls(before, min_usd))
    wb = dict(walls(after, min_usd))
    out = []
    for p in sorted(set(wa) | set(wb)):
        qa, qb = wa.get(p, 0.0), wb.get(p, 0.0)
        if not qa:
            tag = "new"
        elif not qb:
            tag = "pulled"
        elif abs(qb / qa - 1) <= tol:
            tag = "held"
        else:
            tag = "grew" if qb > qa else "shrank"
        out.append(
            {"price": p, "before": qa, "after": qb, "usd_after": p * qb, "change": tag}
        )
    return out


def report(
    bids: list[Level],
    asks: list[Level],
    *,
    prev: tuple[list[Level], list[Level]] | None = None,
    exit_units: float | None = None,
    avg_cost: float | None = None,
) -> dict[str, Any]:
    mid = mid_price(bids, asks)
    rep: dict[str, Any] = {
        "mid": mid,
        "best_bid": bids[0][0],
        "best_ask": asks[0][0],
        "levels": (len(bids), len(asks)),
        "bands": depth_bands(bids, asks),
        "cumulative": [cumulative(bids, asks, p) for p in (1, 2, 3, 5, 10)],
        "bid_walls": sorted(walls(bids), key=lambda x: -x[0] * x[1])[:6],
        "ask_walls": sorted(
            [w for w in walls(asks) if w[0] <= mid * 1.25], key=lambda x: -x[0] * x[1]
        )[:6],
        "far_ask_usd": usd([x for x in asks if x[0] > mid * 1.25]),
        "slippage": {
            amt: {"buy": slippage(asks, amt), "sell": slippage(bids, amt)}
            for amt in (1000, 5000, 10000, 25000, 50000)
        },
    }
    if prev is not None:
        rep["bid_dynamics"] = wall_dynamics(prev[0], bids)
        rep["ask_dynamics"] = wall_dynamics(prev[1], asks)
    if exit_units and avg_cost:
        rep["exit"] = exit_estimate(bids, exit_units, avg_cost)
    return rep


def print_report(rep: dict[str, Any]) -> None:
    mid = rep["mid"]
    print(
        f"=== BOOK  mid {mid:.5f}  bid {rep['best_bid']:.4f} / ask {rep['best_ask']:.4f}"
        f"  levels {rep['levels'][0]}/{rep['levels'][1]} ==="
    )
    print(f"{'band':>9s} {'bids $':>9s} {'asks $':>9s} {'imb':>6s}")
    for b in rep["bands"]:
        print(
            f"{b['lo_pct']:4.1f}-{b['hi_pct']:<4.0f}% {b['bid_usd']:9,.0f} {b['ask_usd']:9,.0f} {b['imbalance']:+6.2f}"
        )
    for c in rep["cumulative"]:
        print(
            f"within {c['pct']:2.0f}%: bid ${c['bid_usd']:8,.0f}  ask ${c['ask_usd']:8,.0f}  ratio {c['ratio']:.2f}"
        )
    print(
        "bid walls:",
        [
            f"{p:.4f} ${p * q:,.0f} ({(p / mid - 1) * 100:+.1f}%)"
            for p, q in rep["bid_walls"]
        ],
    )
    print(
        "ask walls:",
        [
            f"{p:.4f} ${p * q:,.0f} ({(p / mid - 1) * 100:+.1f}%)"
            for p, q in rep["ask_walls"]
        ],
    )
    print(f"asks parked >25% away: ${rep['far_ask_usd']:,.0f}")
    print("slippage (taker, pre-fee):")
    for amt, d in rep["slippage"].items():
        b, s = d["buy"], d["sell"]
        bs = (
            f"buy {(b['avg'] / mid - 1) * 100:+.2f}% (worst {b['worst']:.4f})"
            if b
            else "buy: book exhausted"
        )
        ss = (
            f"sell {(1 - s['avg'] / mid) * 100:+.2f}% (worst {s['worst']:.4f})"
            if s
            else "sell: book exhausted"
        )
        print(f"   ${amt:>6,}: {bs:36s} {ss}")
    for side in ("bid", "ask"):
        key = f"{side}_dynamics"
        if key in rep:
            moved = [d for d in rep[key] if d["change"] != "held"]
            print(
                f"{side} walls moved:",
                [
                    f"{d['price']:.4f} {d['change']} ${d['usd_after']:,.0f}"
                    for d in moved
                ]
                or "none",
            )
    if rep.get("exit"):
        e = rep["exit"]
        print(
            f"exit at market: avg {e['avg_fill']:.5f} worst {e['worst']:.4f} proceeds ${e['proceeds']:,.0f}"
            f" vs cost ${e['cost']:,.0f} -> {e['pnl']:+,.0f}"
        )


def main() -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    ap.add_argument("--pair", default="FLOWUSD")
    ap.add_argument(
        "--watch-seconds",
        type=float,
        default=0.0,
        help="second snapshot after N seconds for wall dynamics",
    )
    ap.add_argument("--exit-units", type=float, default=None)
    ap.add_argument(
        "--avg", type=float, default=None, help="average cost for the exit estimate"
    )
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    prev = None
    if a.watch_seconds > 0:
        prev = snapshot(a.pair)
        time.sleep(a.watch_seconds)
    bids, asks = snapshot(a.pair)
    rep = report(bids, asks, prev=prev, exit_units=a.exit_units, avg_cost=a.avg)
    if a.json:
        print(json.dumps(rep, default=str))
    else:
        print_report(rep)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
