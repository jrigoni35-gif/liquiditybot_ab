"""monitor/flow_transfers.py — FLOW transfer scan on Flow mainnet (Cadence side).

The on-chain half of the market-microstructure method for FLOW: the wallet
search. Reads FungibleToken Deposited/Withdrawn events from the public Flow
REST access node, keeps FlowToken vault movements at or above a size floor,
pairs each transaction's withdrawal with its deposit, and ranks hub
accounts by unique counterparties. Exchange wallets have no public labels
on Flow; they are identified by SHAPE (many counterparties, sweep
addresses that empty into one cold store, dozens of signing keys). The
report says "exchange-pattern", never an exchange name.

Pure functions (tested): decode_payload, pair_transfers, hub_stats,
daily_flows. `scan()` does the network reads.

CLI::

    python monitor/flow_transfers.py --hours 24 --min-flow 1000
    python monitor/flow_transfers.py --hours 168 --min-flow 5000 --json
"""

from __future__ import annotations

import argparse
import base64
import collections
import concurrent.futures as cf
import json
import time
import urllib.request
from typing import Any

REST = "https://rest-mainnet.onflow.org/v1"
TIMEOUT = 60
FLOW_VAULT = "A.1654653399040a61.FlowToken.Vault"
EVENT_TYPES = ("Deposited", "Withdrawn")
CHUNK = 250  # access-node cap on blocks per event query
BLOCKS_PER_HOUR = 3600  # ~1 sealed block/s on mainnet
WORKERS = 8


def _get(path: str) -> Any:
    url = f"{REST}/{path}"
    if not url.startswith("https://rest-mainnet.onflow.org/"):  # pin scheme AND host
        raise ValueError(f"refusing non-Flow URL: {url!r}")
    for attempt in range(4):
        try:
            with urllib.request.urlopen(url, timeout=TIMEOUT) as fh:  # noqa: S310  # nosec B310
                return json.loads(fh.read().decode())
        except Exception:  # noqa: BLE001 - retry transient access-node errors
            if attempt == 3:
                raise
            time.sleep(1.5 * (attempt + 1))
    return None


def decode_payload(payload_b64: str) -> dict[str, Any]:
    """JSON-CDC event payload (base64) -> {field: value}; Optionals unwrapped."""
    j = json.loads(base64.b64decode(payload_b64))
    out: dict[str, Any] = {}
    for f in j["value"]["fields"]:
        v = f["value"]
        if v.get("type") == "Optional":
            v = v.get("value")
        out[f["name"]] = None if v is None else v.get("value")
    return out


def sealed_height() -> int:
    return int(_get("blocks?height=sealed")[0]["header"]["height"])


def _chunk(start: int, end: int, min_flow: float) -> list[dict[str, Any]]:
    rows = []
    for typ in EVENT_TYPES:
        ev = _get(
            f"events?type=A.f233dcee88fe0abe.FungibleToken.{typ}"
            f"&start_height={start}&end_height={end}"
        )
        for blk in ev or []:
            for x in blk.get("events", []):
                d = decode_payload(x["payload"])
                if d.get("type") != FLOW_VAULT:
                    continue
                amt = float(d["amount"])
                if amt < min_flow:
                    continue
                rows.append(
                    {
                        "height": int(blk["block_height"]),
                        "ts": blk["block_timestamp"],
                        "tx": x["transaction_id"],
                        "kind": typ,
                        "amt": amt,
                        "addr": d.get("to") or d.get("from"),
                        "bal": float(d["balanceAfter"]),
                    }
                )
    return rows


def scan(
    hours: float, min_flow: float, head: int | None = None
) -> list[dict[str, Any]]:
    """Raw event rows for the last `hours` (network)."""
    head = sealed_height() if head is None else head
    start = head - int(hours * BLOCKS_PER_HOUR)
    starts = list(range(start, head + 1, CHUNK))
    rows: list[dict[str, Any]] = []
    with cf.ThreadPoolExecutor(WORKERS) as ex:
        for out in ex.map(
            lambda s: _chunk(s, min(s + CHUNK - 1, head), min_flow), starts
        ):
            rows.extend(out)
    return rows


def pair_transfers(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Match each tx's Withdrawn rows to Deposited rows of equal amount."""
    bytx: dict[str, dict[str, list]] = collections.defaultdict(
        lambda: {"w": [], "d": []}
    )
    for r in rows:
        bytx[r["tx"]]["w" if r["kind"] == "Withdrawn" else "d"].append(r)
    xf = []
    for tx, v in bytx.items():
        ws = sorted(v["w"], key=lambda r: -r["amt"])
        ds = sorted(v["d"], key=lambda r: -r["amt"])
        for w, d in zip(ws, ds, strict=False):
            if abs(w["amt"] - d["amt"]) < 1e-6:
                xf.append(
                    {
                        "ts": w["ts"],
                        "tx": tx,
                        "from": w["addr"],
                        "to": d["addr"],
                        "amt": w["amt"],
                        "from_bal": w["bal"],
                        "to_bal": d["bal"],
                    }
                )
    xf.sort(key=lambda x: x["ts"])
    return xf


def hub_stats(xf: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Per-address in/out FLOW, counts, unique counterparties, last balance."""
    st: dict[str, dict[str, Any]] = collections.defaultdict(
        lambda: {"in": 0.0, "out": 0.0, "nin": 0, "nout": 0, "cps": set(), "bal": 0.0}
    )
    for x in xf:
        f, t = x["from"], x["to"]
        if f:
            s = st[f]
            s["out"] += x["amt"]
            s["nout"] += 1
            s["cps"].add(t)
            s["bal"] = x["from_bal"]
        if t:
            s = st[t]
            s["in"] += x["amt"]
            s["nin"] += 1
            s["cps"].add(f)
            s["bal"] = x["to_bal"]
    out = [
        {
            "addr": a,
            "in": s["in"],
            "out": s["out"],
            "net": s["in"] - s["out"],
            "nin": s["nin"],
            "nout": s["nout"],
            "counterparties": len(s["cps"]),
            "balance": s["bal"],
        }
        for a, s in st.items()
    ]
    out.sort(key=lambda d: (-d["counterparties"], -d["balance"]))
    return out


def daily_flows(
    xf: list[dict[str, Any]], hubs: list[str]
) -> dict[str, dict[str, float]]:
    """Per-UTC-day net FLOW into each hub address (in minus out)."""
    day: dict[str, dict[str, float]] = collections.defaultdict(
        lambda: collections.defaultdict(float)
    )
    for x in xf:
        d = x["ts"][:10]
        day[d]["total"] += x["amt"]
        for h in hubs:
            if x["to"] == h:
                day[d][h] += x["amt"]
            if x["from"] == h:
                day[d][h] -= x["amt"]
    return {k: dict(v) for k, v in sorted(day.items())}


def report(rows: list[dict[str, Any]], hours: float, min_flow: float) -> dict[str, Any]:
    xf = pair_transfers(rows)
    hubs = hub_stats(xf)
    top = [h["addr"] for h in hubs[:6]]
    return {
        "hours": hours,
        "min_flow": min_flow,
        "rows": len(rows),
        "transfers": len(xf),
        "total_flow": sum(x["amt"] for x in xf),
        "hubs": hubs[:12],
        "largest": sorted(xf, key=lambda x: -x["amt"])[:15],
        "daily": daily_flows(xf, top),
    }


def print_report(rep: dict[str, Any]) -> None:
    print(
        f"=== FLOW transfers >= {rep['min_flow']:,.0f} FLOW/leg, last {rep['hours']:g}h ==="
    )
    print(
        f"rows {rep['rows']}  matched transfers {rep['transfers']}  total {rep['total_flow']:,.0f} FLOW"
    )
    print(
        f"{'hub (exchange-pattern if many cps)':36s} {'cps':>4s} {'in':>12s} {'out':>12s} {'net':>12s} {'balance':>14s}"
    )
    for h in rep["hubs"]:
        print(
            f"{h['addr']:36s} {h['counterparties']:4d} {h['in']:12,.0f} {h['out']:12,.0f} {h['net']:+12,.0f} {h['balance']:14,.0f}"
        )
    print("largest transfers:")
    for x in rep["largest"]:
        print(
            f"   {x['ts'][:16]} {x['from']} -> {x['to']} {x['amt']:12,.0f}  to_bal {x['to_bal']:12,.0f}"
        )
    print("daily net into top hubs (FLOW):")
    for d, v in rep["daily"].items():
        print(
            f"   {d} total {v.get('total', 0):12,.0f}  "
            + "  ".join(f"{k[:8]} {v.get(k, 0):+10,.0f}" for k in v if k != "total")
        )


def main() -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    ap.add_argument("--hours", type=float, default=24.0)
    ap.add_argument("--min-flow", type=float, default=1000.0)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    rows = scan(a.hours, a.min_flow)
    rep = report(rows, a.hours, a.min_flow)
    print(json.dumps(rep) if a.json else "", end="")
    if not a.json:
        print_report(rep)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
