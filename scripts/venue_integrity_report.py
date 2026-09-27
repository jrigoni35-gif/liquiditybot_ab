"""scripts/venue_integrity_report.py - VENUE INTEGRITY report (conduct
standard section 3, VG-1..VG-10). SAFE class: read-only measurement.

Reads fills.csv, the audit trail (main chain only, via
core.audit.read_main_chain) and venue JSON the operator exports. It writes
NOTHING (stdout only; `--json` for machine output), places no order, and
imports nothing from the decision path. `--fetch` (orphans / venue-status /
custody only) calls read-only Kraken query endpoints - OpenOrders,
TradeBalance, AssetPairs, SystemStatus - through KrakenFeed, whose
withdrawal deny-list is untouched; it is never run by the engine.

    python scripts/venue_integrity_report.py fees --volume-30d 60000
    python scripts/venue_integrity_report.py fill-accept
    python scripts/venue_integrity_report.py fill-gap
    python scripts/venue_integrity_report.py errors --log outputs/bot.log
    python scripts/venue_integrity_report.py post-only --closed closed.json
    python scripts/venue_integrity_report.py orphans --open open.json
    python scripts/venue_integrity_report.py reconcile --closed c.json --trades t.json
    python scripts/venue_integrity_report.py self-cross
    python scripts/venue_integrity_report.py venue-status --asset-pairs ap.json --system-status ss.json
    python scripts/venue_integrity_report.py custody --target-usd 1000 --trade-balance tb.json

Every sub-report carries registered VI-* codes (core/codes.py). VI-001 means
the input held no live rows: an ABSENT verdict, never a clean one.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core import venue_integrity as vi  # noqa: E402
from core.audit import read_main_chain  # noqa: E402

DEFAULT_FILLS = ROOT / "outputs" / "fills.csv"
DEFAULT_AUDIT = ROOT / "outputs" / "audit.jsonl"


def _fills(path: Path) -> list:
    if not path.is_file():
        return []
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _audit(path: Path) -> list:
    recs, main = read_main_chain(path)
    return [recs[i] for i in sorted(main) if recs[i] is not None]


def _json(path) -> object:
    if not path:
        return None
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _config_pairs() -> list:
    try:
        with open(ROOT / "config.json", encoding="utf-8") as fh:
            cfg = json.load(fh)
        return list(cfg["exchanges"]["kraken"]["trading_pairs"])
    except (OSError, ValueError, KeyError, TypeError):
        return []


def _feed():
    """Read-only KrakenFeed (credentials from env as the engine resolves
    them). Only query endpoints are called by this script."""
    from data.kraken_feed import KrakenFeed
    return KrakenFeed({"rate_limit_per_sec": 1})


def run(args) -> dict:
    cmd = args.cmd
    if cmd in ("fees", "fill-accept", "fill-gap", "orphans", "reconcile",
               "self-cross"):
        records = _audit(Path(args.audit))
        posture = vi.Posture(records)
    else:
        records, posture = [], vi.Posture([])
    fills = _fills(Path(args.fills)) if hasattr(args, "fills") else []
    if cmd == "fees":
        rep = (vi.trades_fee_check(_json(args.trades), args.volume_30d,
                                   args.aop_usd, args.tol_bps)
               if args.trades else
               vi.fee_check(fills, posture, args.volume_30d, args.aop_usd,
                            args.tol_bps))
    elif cmd == "fill-accept":
        booked = posture.latest_booked_fees()
        maker = args.maker if args.maker is not None else (booked or (None, None))[0]
        taker = args.taker if args.taker is not None else (booked or (None, None))[1]
        if maker is None or taker is None:
            return {"check": "VG-2 fill acceptance", "verdict": "UNKNOWN",
                    "reason": "no booked fee row: pass --maker/--taker",
                    "codes": ["VI-001"]}
        marks = _json(args.markout_json) if args.markout_json else None
        postures = ("live", "dry") if args.include_dry else ("live",)
        rep = vi.fill_acceptance(fills, posture, float(maker), float(taker),
                                 marks if isinstance(marks, list) else None,
                                 include_postures=postures)
    elif cmd == "fill-gap":
        rep = vi.sim_live_gap(records, posture, args.purpose)
    elif cmd == "errors":
        lines: list = []
        for p in args.log:
            with open(p, encoding="utf-8", errors="replace") as fh:
                lines.extend(fh)
        rep = vi.classify_log_lines(lines)
    elif cmd == "post-only":
        rep = vi.post_only_cancels(_json(args.closed))
    elif cmd == "orphans":
        opened = _feed().get_open_orders() if args.fetch else _json(args.open)
        known = {r.get("order_id", "") for r in fills} | {
            t["order_id"] for t in vi.terminals(records)}
        term = {t["order_id"] for t in vi.terminals(records)}
        rep = vi.orphan_diff(opened, {k for k in known if k}, term)
    elif cmd == "reconcile":
        rep = vi.reconcile(fills, posture, _json(args.closed), _json(args.trades))
    elif cmd == "self-cross":
        rep = vi.self_cross_scan(fills, posture, args.window_sec, args.px_tol_bps)
        rep["coexistence"] = vi.coexistence_scan(records, fills)
    elif cmd == "venue-status":
        if args.fetch:
            f = _feed()
            ap, ss = f._public_get("AssetPairs"), f._public_get("SystemStatus")
        else:
            ap, ss = _json(args.asset_pairs), _json(args.system_status)
        rep = vi.venue_status(ap, ss, args.pairs or _config_pairs())
    elif cmd == "custody":
        if args.fetch:
            usd = vi.trade_balance_usd(_feed()._private_post(
                "TradeBalance", {"asset": "ZUSD"}))
        elif args.trade_balance:
            usd = vi.trade_balance_usd(_json(args.trade_balance))
        else:
            usd = args.equity_usd
        rep = vi.custody(usd, args.target_usd)
    else:                                          # pragma: no cover
        raise SystemExit(f"unknown command {cmd}")
    if cmd in ("fees", "fill-accept", "fill-gap", "reconcile", "self-cross"):
        rep["posture_sessions"] = posture.sessions
        rep["inputs"] = {"fills": str(getattr(args, "fills", "")),
                         "fill_rows": len(fills),
                         "audit": str(args.audit),
                         "audit_main_chain_records": len(records)}
    return rep


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--json", action="store_true", help="machine output")
    js = argparse.ArgumentParser(add_help=False)
    js.add_argument("--json", action="store_true", default=argparse.SUPPRESS,
                    help="machine output")
    sub = ap.add_subparsers(dest="cmd", required=True)
    _add = sub.add_parser
    sub.add_parser = lambda *a, **k: _add(*a, parents=[js], **k)  # type: ignore[method-assign]

    def common(p, fills=True, audit=True):
        if fills:
            p.add_argument("--fills", default=str(DEFAULT_FILLS))
        if audit:
            p.add_argument("--audit", default=str(DEFAULT_AUDIT))
        return p

    p = common(sub.add_parser("fees", help="VG-1 per-fill fee vs published tier"))
    p.add_argument("--volume-30d", type=float, default=None)
    p.add_argument("--aop-usd", type=float, default=None)
    p.add_argument("--tol-bps", type=float, default=1.0)
    p.add_argument("--trades", default=None, help="TradesHistory JSON export")
    p = common(sub.add_parser("fill-accept", help="VG-2 registered thresholds"))
    p.add_argument("--maker", type=float, default=None)
    p.add_argument("--taker", type=float, default=None)
    p.add_argument("--markout-json", default=None,
                   help="JSON list of per-fill 30s alpha mark-outs (bps)")
    p.add_argument("--include-dry", action="store_true",
                   help="also grade simulator fills (labelled; never a live verdict)")
    p = common(sub.add_parser("fill-gap", help="VG-3 sim vs live fill rate"),
               fills=False)
    p.add_argument("--purpose", default="entry")
    p = sub.add_parser("errors", help="VG-4 classify venue errors in logs")
    p.add_argument("--log", nargs="+", required=True)
    p = sub.add_parser("post-only", help="VG-5 post-only cancels (ClosedOrders)")
    p.add_argument("--closed", required=True)
    p = common(sub.add_parser("orphans", help="VG-6 venue open orders vs bot"))
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--open", help="OpenOrders JSON export")
    g.add_argument("--fetch", action="store_true")
    p = common(sub.add_parser("reconcile", help="VG-7 fills vs venue"))
    p.add_argument("--closed", required=True)
    p.add_argument("--trades", required=True)
    p = common(sub.add_parser("self-cross", help="VG-8 self-match scan"))
    p.add_argument("--window-sec", type=float, default=1.0)
    p.add_argument("--px-tol-bps", type=float, default=1.0)
    p = sub.add_parser("venue-status", help="VG-9 pair + system status")
    p.add_argument("--asset-pairs", default=None)
    p.add_argument("--system-status", default=None)
    p.add_argument("--fetch", action="store_true")
    p.add_argument("--pairs", nargs="*", default=None)
    p = sub.add_parser("custody", help="VG-10 on-venue USD vs target")
    p.add_argument("--target-usd", type=float, required=True)
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--trade-balance", help="TradeBalance JSON export")
    g.add_argument("--equity-usd", type=float)
    g.add_argument("--fetch", action="store_true")
    return ap


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    rep = run(args)
    if args.json:
        print(json.dumps(rep, indent=2, default=str))
    else:
        print(f"{rep.get('check')}: verdict={rep.get('verdict')} "
              f"codes={','.join(rep.get('codes', []))}")
        for k, v in rep.items():
            if k in ("check", "verdict", "codes"):
                continue
            s = json.dumps(v, default=str)
            print(f"  {k}: {s if len(s) < 400 else s[:400] + ' ...'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
