"""monitor/tape.py — Kraken trade tape in the market-microstructure record shape.

Adapter + screens that let the vendored `market-microstructure` skill's
method run on a Kraken pair instead of a Solana DEX. Public endpoint only,
read-only, no keys.

Record shape (what the skill's functions consume)::

    {"timestamp": float, "side": "buy"|"sell", "volume_usd": float,
     "price": float, "size": float, "order_type": "market"|"limit",
     "wallet": str}

`side` is the TAKER side from Kraken's b/s flag. `wallet` does not exist on
a centralised exchange; it carries a pseudo-identity, the exact fill
quantity fingerprint ("q:<qty>"). Repeated exact fractional quantities are
one account's resting lot, and that is the only identity the public tape
gives. Every screen that uses it says so in its output name.

Screens (pure functions; each has a test in tests/test_monitor_tape.py):
pressure, size_skew, clip_repeats, both_sides_lots, same_second_cross,
hourly_buckets, acceleration, momentum_score (the skill's formula,
reproduced with attribution, fed with pseudo-identity inputs).

CLI::

    python monitor/tape.py --pair FLOWUSD --hours 24
    python monitor/tape.py --pair FLOWUSD --hours 6 --json
"""

from __future__ import annotations

import argparse
import collections
import datetime as dt
import json
import math
import statistics
import time
import urllib.request
from typing import Any

KRAKEN = "https://api.kraken.com/0/public"
TIMEOUT = 30
MAX_PAGES = 40
WHALE_USD = 1000.0  # a "whale" print on a $100k/day pair; see PROVENANCE


def _get(endpoint: str, query: str) -> dict:
    url = f"{KRAKEN}/{endpoint}?{query}"
    if not url.startswith("https://api.kraken.com/"):  # pin scheme AND host
        raise ValueError(f"refusing non-Kraken URL: {url!r}")
    with urllib.request.urlopen(url, timeout=TIMEOUT) as fh:  # noqa: S310  # nosec B310
        payload = json.loads(fh.read().decode())
    if payload.get("error"):
        raise RuntimeError(f"kraken {endpoint}: {payload['error']}")
    return payload["result"]


def fetch_trades(pair: str, hours: float, now: float | None = None) -> list[list]:
    """Raw Kraken trade rows [price, volume, time, b/s, m/l, misc, id] for the window."""
    now = time.time() if now is None else now
    since = int((now - hours * 3600) * 1e9)
    out: list[list] = []
    for _ in range(MAX_PAGES):
        res = _get("Trades", f"pair={pair}&since={since}")
        key = next(k for k in res if k != "last")
        batch = res[key]
        if not batch:
            break
        out.extend(batch)
        last = int(res["last"])
        if last == since or len(batch) < 1000:
            break
        since = last
    return [t for t in out if float(t[2]) >= now - hours * 3600]


def to_records(raw: list[list]) -> list[dict[str, Any]]:
    """Kraken rows -> skill records. `wallet` is the quantity fingerprint."""
    recs = []
    for t in raw:
        price, size, ts = float(t[0]), float(t[1]), float(t[2])
        recs.append(
            {
                "timestamp": ts,
                "side": "buy" if t[3] == "b" else "sell",
                "volume_usd": price * size,
                "price": price,
                "size": size,
                "order_type": "market" if t[4] == "m" else "limit",
                "wallet": f"q:{t[1]}",
            }
        )
    recs.sort(key=lambda r: r["timestamp"])
    return recs


# --------------------------------------------------------------------------
# Screens
# --------------------------------------------------------------------------


def pressure(recs: list[dict]) -> dict[str, float]:
    """Taker buy/sell USD, counts, net flow, market-order share."""
    buy = sum(r["volume_usd"] for r in recs if r["side"] == "buy")
    sell = sum(r["volume_usd"] for r in recs if r["side"] == "sell")
    n = len(recs)
    nb = sum(1 for r in recs if r["side"] == "buy")
    nm = sum(1 for r in recs if r["order_type"] == "market")
    tot = buy + sell
    return {
        "n": n,
        "buy_usd": buy,
        "sell_usd": sell,
        "net_usd": buy - sell,
        "buy_volume_pct": buy / tot if tot else 0.5,
        "trade_count_ratio": nb / n if n else 0.5,
        "market_share": nm / n if n else 0.0,
    }


def size_skew(recs: list[dict]) -> dict[str, float]:
    """Mean/median USD print and the skill's skew indicator (mean/median)."""
    sizes = [r["volume_usd"] for r in recs]
    if not sizes:
        return {"mean": 0.0, "median": 0.0, "skew": 0.0, "max": 0.0, "whale_pct": 0.0}
    med = statistics.median(sizes)
    tot = sum(sizes)
    return {
        "mean": statistics.mean(sizes),
        "median": med,
        "skew": statistics.mean(sizes) / med if med else 0.0,
        "max": max(sizes),
        "whale_pct": sum(s for s in sizes if s >= WHALE_USD) / tot if tot else 0.0,
    }


def clip_repeats(recs: list[dict], min_repeats: int = 3) -> list[tuple[str, int]]:
    """Exact quantity fingerprints seen >= min_repeats times, most common first."""
    c = collections.Counter(r["wallet"] for r in recs)
    return [(w, k) for w, k in c.most_common() if k >= min_repeats]


def both_sides_lots(recs: list[dict], min_usd: float = 100.0) -> list[dict]:
    """Fingerprints that printed as BOTH taker-buy and taker-sell.

    One resting lot size crossing in both directions is the CEX analogue of
    the skill's self-trade screen. Returns per-fingerprint side counts, the
    price set, and whether any fill on each side shares a price (at-cost
    round trip: volume with no P&L).
    """
    by: dict[str, list[dict]] = collections.defaultdict(list)
    for r in recs:
        if r["volume_usd"] >= min_usd:
            by[r["wallet"]].append(r)
    out = []
    for w, rs in by.items():
        buys = [r for r in rs if r["side"] == "buy"]
        sells = [r for r in rs if r["side"] == "sell"]
        if buys and sells:
            same_px = bool({r["price"] for r in buys} & {r["price"] for r in sells})
            out.append(
                {
                    "wallet": w,
                    "buys": len(buys),
                    "sells": len(sells),
                    "usd": sum(r["volume_usd"] for r in rs),
                    "same_price_round_trip": same_px,
                    "first": min(r["timestamp"] for r in rs),
                    "last": max(r["timestamp"] for r in rs),
                }
            )
    out.sort(key=lambda d: -d["usd"])
    return out


def same_second_cross(recs: list[dict], min_usd: float = 1000.0) -> list[dict]:
    """Seconds in which taker buys AND taker sells both printed.

    Both sides hitting inside one second at overlapping prices is two
    accounts trading through each other or one account crossing itself.
    Organic demand does not do that.
    """
    by: dict[int, list[dict]] = collections.defaultdict(list)
    for r in recs:
        by[int(r["timestamp"])].append(r)
    out = []
    for sec, rs in by.items():
        b = [r for r in rs if r["side"] == "buy"]
        s = [r for r in rs if r["side"] == "sell"]
        usd = sum(r["volume_usd"] for r in rs)
        if b and s and usd >= min_usd:
            out.append(
                {
                    "second": sec,
                    "prints": len(rs),
                    "usd": usd,
                    "buy_usd": sum(r["volume_usd"] for r in b),
                    "sell_usd": sum(r["volume_usd"] for r in s),
                    "prices": sorted({r["price"] for r in rs}),
                }
            )
    out.sort(key=lambda d: -d["usd"])
    return out


def hourly_buckets(recs: list[dict]) -> list[dict]:
    """Per-UTC-hour volume, net taker flow, market-order count, last price."""
    bk: dict[int, dict] = {}
    for r in recs:
        h = int(r["timestamp"] // 3600 * 3600)
        d = bk.setdefault(
            h,
            {"hour": h, "n": 0, "usd": 0.0, "net_usd": 0.0, "market": 0, "last": None},
        )
        d["n"] += 1
        d["usd"] += r["volume_usd"]
        d["net_usd"] += r["volume_usd"] if r["side"] == "buy" else -r["volume_usd"]
        d["market"] += r["order_type"] == "market"
        d["last"] = r["price"]
    return [bk[k] for k in sorted(bk)]


def acceleration(recs: list[dict]) -> float:
    """Second-half USD volume / first-half USD volume (skill definition)."""
    if len(recs) < 2:
        return 0.0
    mid = len(recs) // 2
    first = sum(r["volume_usd"] for r in recs[:mid])
    second = sum(r["volume_usd"] for r in recs[mid:])
    return second / first if first else 0.0


def momentum_score(
    buy_ratio: float,
    volume_accel: float,
    whale_buy_pct: float,
    unique_trader_trend: float,
) -> float:
    """Composite score, -100..+100. Formula reproduced from the vendored
    market-microstructure skill (agiprolabs, MIT). On a CEX the trader-trend
    input is the quantity-fingerprint count trend, not wallets."""
    buy_c = (buy_ratio - 0.5) * 80
    vol_c = min(max((volume_accel - 1.0) * 20, -20), 20)
    whale_c = (whale_buy_pct - 0.5) * 50
    trader_c = min(max(unique_trader_trend * 15, -15), 15)
    return max(-100.0, min(100.0, buy_c + vol_c + whale_c + trader_c))


def momentum_inputs(recs: list[dict]) -> dict[str, float]:
    """The four momentum_score inputs, computed the way the skill does."""
    p = pressure(recs)
    whale = [r for r in recs if r["volume_usd"] >= WHALE_USD]
    wt = sum(r["volume_usd"] for r in whale)
    wb = sum(r["volume_usd"] for r in whale if r["side"] == "buy")
    mid = len(recs) // 2
    u1 = len({r["wallet"] for r in recs[:mid]})
    u2 = len({r["wallet"] for r in recs[mid:]})
    return {
        "buy_ratio": p["buy_volume_pct"],
        "volume_accel": acceleration(recs),
        "whale_buy_pct": wb / wt if wt else 0.5,
        "unique_trader_trend": (u2 - u1) / u1 if u1 else 0.0,
    }


def interpret(score: float) -> str:
    if score >= 60:
        return "strong accumulation"
    if score >= 20:
        return "moderate buying"
    if score > -20:
        return "neutral"
    if score > -60:
        return "moderate selling"
    return "strong distribution"


# --------------------------------------------------------------------------
# Report
# --------------------------------------------------------------------------


def _ts(t: float) -> str:
    return dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime("%m-%d %H:%M:%S")


def report(recs: list[dict], pair: str, hours: float) -> dict[str, Any]:
    """Machine-readable summary; `print_report` renders it."""
    p = pressure(recs)
    mi = momentum_inputs(recs)
    score = momentum_score(**mi)
    return {
        "pair": pair,
        "hours": hours,
        "pressure": p,
        "size": size_skew(recs),
        "clip_repeats": clip_repeats(recs)[:10],
        "both_sides_lots": both_sides_lots(recs)[:10],
        "same_second_cross": same_second_cross(recs)[:10],
        "hourly": hourly_buckets(recs),
        "momentum_inputs": mi,
        "momentum_score": score,
        "momentum_label": interpret(score),
        "largest": sorted(recs, key=lambda r: -r["volume_usd"])[:8],
    }


def print_report(rep: dict[str, Any]) -> None:
    p = rep["pressure"]
    print(f"=== KRAKEN {rep['pair']} tape, last {rep['hours']:g}h ===")
    print(
        f"prints {p['n']}  taker buys ${p['buy_usd']:,.0f}  sells ${p['sell_usd']:,.0f}"
        f"  net ${p['net_usd']:+,.0f}  buy% {100 * p['buy_volume_pct']:.0f}"
        f"  market {100 * p['market_share']:.0f}%"
    )
    s = rep["size"]
    print(
        f"print size: median ${s['median']:,.0f} mean ${s['mean']:,.0f} skew {s['skew']:.1f}"
        f"  max ${s['max']:,.0f}  >=${WHALE_USD:,.0f} share {100 * s['whale_pct']:.0f}%"
    )
    print("repeated exact quantities:", [(w[2:], k) for w, k in rep["clip_repeats"]])
    if rep["both_sides_lots"]:
        print("fingerprints on BOTH taker sides (self-trade analogue):")
        for d in rep["both_sides_lots"]:
            flag = " AT-COST" if d["same_price_round_trip"] else ""
            print(
                f"   {d['wallet'][2:]:>16s}  b{d['buys']}/s{d['sells']}  ${d['usd']:,.0f}"
                f"  {_ts(d['first'])} -> {_ts(d['last'])}{flag}"
            )
    if rep["same_second_cross"]:
        print("buys AND sells inside one second:")
        for d in rep["same_second_cross"]:
            print(
                f"   {_ts(d['second'])}  {d['prints']} prints ${d['usd']:,.0f}"
                f"  (b ${d['buy_usd']:,.0f} / s ${d['sell_usd']:,.0f})  {d['prices']}"
            )
    print("largest prints:")
    for r in rep["largest"]:
        print(
            f"   {_ts(r['timestamp'])} {r['side']:4s} {r['order_type'][0]}"
            f" {r['size']:>12,.2f} @ {r['price']:.4f} = ${r['volume_usd']:,.0f}"
        )
    print("hour (UTC)      n     usd      net  mkt  last")
    for h in rep["hourly"]:
        print(
            f"{_ts(h['hour'])[:11]} {h['n']:4d} {h['usd']:8,.0f} {h['net_usd']:+8,.0f}"
            f" {h['market']:4d}  {h['last']:.4f}"
        )
    mi = rep["momentum_inputs"]
    print(
        f"momentum (skill formula, pseudo-identity inputs): buy_ratio {mi['buy_ratio']:.2f}"
        f" accel {mi['volume_accel']:.2f}x whale_buy {mi['whale_buy_pct']:.2f}"
        f" fp_trend {mi['unique_trader_trend']:+.2f} -> {rep['momentum_score']:+.0f}"
        f" ({rep['momentum_label']})"
    )


def main() -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    ap.add_argument("--pair", default="FLOWUSD")
    ap.add_argument("--hours", type=float, default=24.0)
    ap.add_argument("--json", action="store_true", help="emit the report as JSON")
    a = ap.parse_args()
    recs = to_records(fetch_trades(a.pair, a.hours))
    rep = report(recs, a.pair, a.hours)
    if a.json:
        print(
            json.dumps(
                rep,
                default=lambda o: None if isinstance(o, float) and math.isnan(o) else o,
            )
        )
    else:
        print_report(rep)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
