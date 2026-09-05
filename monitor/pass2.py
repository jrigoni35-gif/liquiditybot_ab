"""monitor/pass2.py — carry-corrected FLOW/USD margin monitor (Kraken).

Standalone. Reads LIVE Kraken public endpoints and the operator's own
account figures; cites no liquiditybot state. Nothing here places,
cancels or simulates an order — SAFE class under the era-6 moratorium.

Why "pass2": pass 1 quoted the margin call as a STATIC price. It is not.
Rollover is debited from margin equity every 4h, so with used margin
fixed at open, the call price *rises* at carry/units per day. On the
position this file defaults to that is +$0.0000418/day, which walks a
call quoted at $0.02605 up to $0.02735 in 31 days — through spot. Any
"N% below spot" number for a leveraged carry position is a day-zero
snapshot of a barrier that is moving toward you, and quoting it without
the slope is the error this module exists to prevent.

Primary sources only:
  - price/spread/volume  : Kraken /0/public/Ticker
  - full bid book        : Kraken /0/public/Depth
  - fees, tick, call/stop: Kraken /0/public/AssetPairs  (never a repo note)
  - carry, equity, units : the operator's account screen (--carry etc.)

Usage:
    python monitor/pass2.py
    python monitor/pass2.py --units 90334.862054 --avg 0.02793 \
        --used-margin 840.88 --equity 778.99 --equity-px 0.02723 --carry 3.78
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import urllib.request
from dataclasses import dataclass

KRAKEN = "https://api.kraken.com/0/public"
PAIR = "FLOWUSD"
TIMEOUT = 30


def _get(endpoint: str, query: str) -> dict:
    url = f"{KRAKEN}/{endpoint}?{query}"
    if not url.startswith("https://api.kraken.com/"):  # pin the scheme AND the host
        raise ValueError(f"refusing non-Kraken URL: {url!r}")
    with urllib.request.urlopen(url, timeout=TIMEOUT) as fh:  # noqa: S310  # nosec B310
        payload = json.loads(fh.read().decode())
    if payload.get("error"):
        raise RuntimeError(f"kraken {endpoint}: {payload['error']}")
    return payload["result"]


@dataclass(frozen=True)
class Position:
    """Operator account figures. Defaults are the 2026-09-04 account screen."""

    units: float = 90334.862054
    avg: float = 0.02793
    used_margin: float = 840.88
    equity: float = 778.99
    equity_px: float = 0.02723
    carry_per_day: float = 3.78
    as_of: str = "2026-09-04"

    @property
    def cash_balance(self) -> float:
        """Margin equity = cash + unrealised P&L; invert at the quoted price."""
        return self.equity - self.units * (self.equity_px - self.avg)

    def threshold_px(self, level: float, day: float = 0.0) -> float:
        """Price at which equity hits `level` x used margin, `day` days out.

        Carry is debited from equity while used margin stays pinned at open,
        so the barrier translates upward by carry/units per day.
        """
        need = level * self.used_margin
        return (
            self.avg
            + (need - self.cash_balance) / self.units
            + self.carry_per_day * day / self.units
        )

    def equity_at(self, px: float | None = None, days: float = 0.0) -> float:
        """Margin equity repriced to `px`, `days` of carry after the snapshot.

        The snapshot's own equity is a fact about the moment it was read.
        Quoting it against a later price is how a monitor reports a cured
        or worsened position as if it were current — reprice, always.
        """
        if px is None:
            px = self.equity_px
        return self.cash_balance + self.units * (px - self.avg) - self.carry_per_day * days

    def runway_days(
        self, level: float = 0.80, px: float | None = None, days: float = 0.0
    ) -> float:
        """Days to breach `level` at a flat price — carry alone, from (px, days)."""
        cushion = self.equity_at(px, days) - level * self.used_margin
        return cushion / self.carry_per_day if self.carry_per_day > 0 else math.inf

    def days_since_snapshot(self, today: dt.date | None = None) -> float:
        """Calendar days since the account figures were read."""
        if today is None:
            today = dt.datetime.now(dt.timezone.utc).date()
        return float((today - dt.date.fromisoformat(self.as_of)).days)


def fee_tier(pair_info: dict, volume_30d: float) -> tuple[float, float]:
    """(maker, taker) percent for `volume_30d`, straight off AssetPairs."""

    def pick(rows: list[list[float]]) -> float:
        hit = rows[0][1]
        for floor, fee in rows:
            if volume_30d >= floor:
                hit = fee
        return hit

    return pick(pair_info["fees_maker"]), pick(pair_info["fees"])


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--units", type=float, default=Position.units)
    ap.add_argument("--avg", type=float, default=Position.avg)
    ap.add_argument("--used-margin", type=float, default=Position.used_margin)
    ap.add_argument("--equity", type=float, default=Position.equity)
    ap.add_argument("--equity-px", type=float, default=Position.equity_px)
    ap.add_argument("--carry", type=float, default=Position.carry_per_day)
    ap.add_argument("--as-of", default=Position.as_of,
                    help="date the account figures were read (ISO)")
    ap.add_argument("--days-elapsed", type=float, default=None,
                    help="override carry ageing since --as-of")
    ap.add_argument("--volume-30d", type=float, default=17482.0)
    ap.add_argument("--horizon", type=int, default=31)
    args = ap.parse_args()

    pos = Position(
        units=args.units,
        avg=args.avg,
        used_margin=args.used_margin,
        equity=args.equity,
        equity_px=args.equity_px,
        carry_per_day=args.carry,
        as_of=args.as_of,
    )
    aged = (
        args.days_elapsed if args.days_elapsed is not None
        else pos.days_since_snapshot()
    )

    tick = _get("Ticker", f"pair={PAIR}")[PAIR]
    info = _get("AssetPairs", f"pair={PAIR}")[PAIR]
    depth = _get("Depth", f"pair={PAIR}&count=500")[PAIR]

    bid, ask = float(tick["b"][0]), float(tick["a"][0])
    mid = (bid + ask) / 2
    vol24 = float(tick["v"][1]) * float(tick["p"][1])
    tick_sz = float(info["tick_size"])
    call_lvl = float(info["margin_call"]) / 100
    stop_lvl = float(info["margin_stop"]) / 100
    maker, taker = fee_tier(info, args.volume_30d)

    print(f"=== KRAKEN {PAIR} — venue truth ===")
    print(f"  bid {bid:.5f}  ask {ask:.5f}  mid {mid:.5f}")
    print(
        f"  spread {(ask - bid) / mid * 1e4:6.1f} bps"
        f"  = {round((ask - bid) / tick_sz)} tick(s)"
        f"   [1 tick = {tick_sz / mid * 1e4:.1f} bps — this is the spread floor]"
    )
    print(f"  24h volume ${vol24:,.0f} on {int(tick['t'][1])} trades")
    print(f"  fees at ${args.volume_30d:,.0f}/30d: maker {maker}% / taker {taker}%")
    print(f"  margin_call {call_lvl:.0%}  margin_stop {stop_lvl:.0%}"
          f"  max leverage {max(info['leverage_buy'])}x")

    print("\n=== POSITION ===")
    print(f"  {pos.units:,.3f} u @ {pos.avg:.5f}   notional ${pos.units * pos.avg:,.2f}")
    print(f"  used margin ${pos.used_margin:,.2f}")
    print(f"  SNAPSHOT {pos.as_of}: equity ${pos.equity:,.2f} @ {pos.equity_px:.5f}"
          f"  state {pos.equity / pos.used_margin:.1%}   <- as read, NOT current")
    eq_now = pos.equity_at(mid, aged)
    print(f"  LIVE (repriced to mid, +{aged:g}d carry): equity ${eq_now:,.2f}"
          f"  state {eq_now / pos.used_margin:.1%}")
    print(f"  unrealised P&L at mid: ${pos.units * (mid - pos.avg):+,.2f}")
    if aged > 3:
        print(f"  !! account figures are {aged:g} days old — re-read the account screen;"
              f"\n     everything below ages them by carry only, not by deposits,"
              f" fills or fee debits")

    cushion = eq_now - call_lvl * pos.used_margin
    runway = pos.runway_days(call_lvl, mid, aged)
    slope = pos.carry_per_day / pos.units
    print("\n=== THE CARRY CLOCK  (the number pass 1 missed) ===")
    print(f"  cushion above call ${cushion:,.2f} (live)   carry ${pos.carry_per_day:.2f}/day")
    print(f"  *** RUNWAY AT A PERFECTLY FLAT PRICE: {runway:.1f} DAYS ***")
    print(f"  call price rises ${slope:.7f}/day ({slope / tick_sz:.2f} tick/day)")
    print(f"  implied rollover {pos.carry_per_day / 6 / (pos.units * pos.avg) * 100:.4f}%/4h")
    print(f"\n  {'day':>5} {'call':>10} {'vs mid':>9} {'liquidation':>13}")
    for day in (0, 7, 14, 21, args.horizon, 60):
        cp = pos.threshold_px(call_lvl, aged + day)
        lp = pos.threshold_px(stop_lvl, aged + day)
        print(f"  {day:5d} {cp:10.5f} {(cp / mid - 1) * 100:+8.2f}% {lp:13.5f}")

    bids = [(float(p), float(v)) for p, v, _ in depth["bids"]]
    call_now = pos.threshold_px(call_lvl, aged)
    to_call = sum(p * v for p, v in bids if p >= call_now)
    wall_px, wall_usd = max(((p, p * v) for p, v in bids), key=lambda t: t[1])
    print("\n=== BID BOOK ===")
    print(f"  {len(bids)} resting bids   {len(depth['asks'])} asks")
    print(f"  largest bid: {wall_px:.5f}  ${wall_usd:,.2f}"
          f"   ({(wall_px / mid - 1) * 100:+.2f}% from mid)")
    print(f"  USD of bids between mid and the call ({call_now:.5f}): ${to_call:,.2f}"
          f"  = {to_call / vol24:.1f} days of Kraken volume")
    print("  NOTE: Kraken is a price-taker (~4% of genuine spot). This depth is"
          " not a floor —\n        it is arbitraged to wherever the other ~96% goes,"
          " and the wall is mobile.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
