"""
scripts/kraken_trades_backfill.py — Kraken public trade tape -> outputs/ticks/.

SAFE class. Read-only public GETs (``/0/public/Trades``) appended into a
parquet tick store. Places no order, reads no credential-bearing endpoint,
imported by nothing in the decision path. It builds its OWN credential-free
client through scripts/candle_backfill.build_feed - never the engine's.

WHY IT EXISTS. The loadable signal corpus spans ~50 days; the False
Strategy Theorem wants years (vault concepts/false-strategy-theorem-and-
minbtl). The 2026-09-01 deep-research pass left "does /Trades reach back to
listing" UNVERIFIED and assumed trade direction had to be tick-rule
inferred. A one-call experiment settled both (scratch trades_reach.py,
2026-09-01T23:04Z, XBTUSD): ``since=0`` returns trade id 1 dated
2013-10-06, and EVERY row carries the aggressor side (``b``/``s``) and
order type (``m`` market / ``l`` limit). Signed flow is native and free.
Re-derive, never recall: ``--probe`` re-runs that experiment.

ENDPOINT CONTRACT (docs.kraken.com/api/docs/rest-api/get-recent-trades,
read 2026-09-01): up to 1000 trades per call; ``since`` is a NANOSECOND
timestamp; the response's ``last`` is the cursor for the next page. Rows
are ``[price, volume, time_s, side, otype, misc, trade_id]``.

THE CURSOR IS AN INT, ALWAYS. ``last`` is 19 digits; through a float it
loses the low bits and the same page is served forever (freqtrade #12961
is that bug in the wild). Everything here parses it with int(), stores it
as int, and the stall guard below stops the run if it ever fails to
advance - an exit condition owned by this script, per CLAUDE.md.

STORE. ``<root>/kraken/<PAIR>/<YYYY-MM>.parquet`` keyed on ``trade_id``,
plus ``<root>/kraken/<PAIR>/cursor.json`` ({"last_ns", "last_id",
"updated_utc"}). Re-running is IDEMPOTENT: months are re-read, de-duplicated
on trade_id and re-written, so an overlap appends nothing twice. Delete the
cursor file to force a re-walk from ``--since``.

COST (measured 2026-09-01T23:05Z by trade-id arithmetic, scratch
trades_volume.py): the 2026-07-13..now window over the 14 pairs the bot
has ever filled = 8.56M trades = ~8.6k calls; lifetime ids sum to ~349M
= ~350k calls. RATE: a 28-call probe at 0.3 s spacing passed, but a
SUSTAINED 3 calls/s run hit ``EGeneral:Too many requests`` after 66
calls (~40 s; RUN 2026-09-01T23:09Z) - the venue tolerates a burst, not
that rate. Default is 1 call/s: ~2.4 h for the window, ~4 days for the
lifetime tape, resumable across runs. Illiquid pairs (ARB, MINA) can go
minutes between prints; a short page is the normal end-of-tape signal,
not an error.

Usage:
    python scripts/kraken_trades_backfill.py --probe
    python scripts/kraken_trades_backfill.py --pairs BTC,ETH --since 2026-07-13
    python scripts/kraken_trades_backfill.py --pairs ADA --since 2024-01-01 \\
        --max-calls 2000            # budgeted, resumes next run
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import sys
import time
from pathlib import Path
from typing import Any, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd  # noqa: E402

from scripts.candle_backfill import _KRAKEN_ASSET, build_feed, load_config  # noqa: E402

log = logging.getLogger("kraken_trades_backfill")

DEFAULT_ROOT = Path("outputs") / "ticks"
PAGE = 1000                      # venue maximum per call
COLUMNS = ("trade_id", "time_s", "price", "volume", "side", "otype", "misc")
# consecutive failed/empty calls before the run gives up (transient venue
# trouble backs off geometrically up to _MAX_BACKOFF_S first)
_MAX_FAILURES = 8
_MAX_BACKOFF_S = 60.0


def kraken_pair(asset: str, quote: str = "USD") -> str:
    return f"{_KRAKEN_ASSET.get(asset.upper(), asset.upper())}{quote}"


def to_ns(when: str | float | int | dt.datetime) -> int:
    """ISO date/datetime (UTC), epoch seconds, or datetime -> int ns."""
    if isinstance(when, dt.datetime):
        if when.tzinfo is None:
            when = when.replace(tzinfo=dt.timezone.utc)
        return int(when.timestamp() * 1_000_000_000)
    if isinstance(when, (int, float)):
        return int(float(when) * 1_000_000_000)
    s = str(when).strip()
    if s.replace(".", "", 1).isdigit():
        return int(float(s) * 1_000_000_000)
    d = dt.datetime.fromisoformat(s)
    return to_ns(d)


def parse_page(result: dict, pair: str) -> tuple[list[dict], int | None]:
    """(rows, last_ns). The venue keys the rows under ITS pair name
    (XXBTZUSD for XBTUSD), so take the one key that is not 'last'."""
    keys = [k for k in result if k != "last"]
    if not keys:
        return [], None
    raw = result[keys[0]] or []
    rows: list[dict] = []
    for r in raw:
        try:
            rows.append({
                "trade_id": int(r[6]),
                "time_s": float(r[2]),
                "price": float(r[0]),
                "volume": float(r[1]),
                "side": str(r[3]),
                "otype": str(r[4]),
                "misc": str(r[5]) if len(r) > 5 else "",
            })
        except (IndexError, TypeError, ValueError):
            continue
    last = result.get("last")
    try:
        last_ns = int(str(last)) if last is not None else None
    except ValueError:
        last_ns = None
    return rows, last_ns


class TickStore:
    """Month-partitioned parquet per pair, de-duplicated on trade_id."""

    def __init__(self, root: Path | str = DEFAULT_ROOT):
        self.root = Path(root)

    def pair_dir(self, pair: str) -> Path:
        return self.root / "kraken" / pair

    def cursor_path(self, pair: str) -> Path:
        return self.pair_dir(pair) / "cursor.json"

    def read_cursor(self, pair: str) -> dict | None:
        p = self.cursor_path(pair)
        if not p.exists():
            return None
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
            return {"last_ns": int(d["last_ns"]), "last_id": int(d.get("last_id", 0))}
        except (OSError, ValueError, KeyError, TypeError):
            return None

    def write_cursor(self, pair: str, last_ns: int, last_id: int) -> None:
        self.pair_dir(pair).mkdir(parents=True, exist_ok=True)
        tmp = self.cursor_path(pair).with_suffix(".json.tmp")
        tmp.write_text(json.dumps({
            "last_ns": int(last_ns), "last_id": int(last_id),
            "updated_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        }), encoding="utf-8")
        tmp.replace(self.cursor_path(pair))

    def append(self, pair: str, rows: list[dict]) -> int:
        """Merge rows into their month files. Returns rows NEW to the store."""
        if not rows:
            return 0
        df = pd.DataFrame(rows, columns=list(COLUMNS))
        df["month"] = pd.to_datetime(df["time_s"], unit="s", utc=True).dt.strftime("%Y-%m")
        added = 0
        self.pair_dir(pair).mkdir(parents=True, exist_ok=True)
        for month, part in df.groupby("month"):
            path = self.pair_dir(pair) / f"{month}.parquet"
            part = part.drop(columns="month")
            before = 0
            if path.exists():
                old = pd.read_parquet(path)
                before = len(old)
                part = pd.concat([old, part], ignore_index=True)
            part = (part.drop_duplicates("trade_id", keep="last")
                        .sort_values("trade_id").reset_index(drop=True))
            tmp = path.with_suffix(".parquet.tmp")
            part.to_parquet(tmp, index=False)
            tmp.replace(path)
            added += len(part) - before
        return added

    def load(self, pair: str, start_s: float | None = None,
             end_s: float | None = None) -> pd.DataFrame:
        files = sorted(self.pair_dir(pair).glob("*.parquet"))
        if not files:
            return pd.DataFrame(columns=list(COLUMNS))
        df = pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)
        if start_s is not None:
            df = df[df["time_s"] >= float(start_s)]
        if end_s is not None:
            df = df[df["time_s"] < float(end_s)]
        return df.sort_values("trade_id").reset_index(drop=True)

    def coverage(self, pair: str) -> dict:
        df = self.load(pair)
        if df.empty:
            return {"pair": pair, "rows": 0}
        return {"pair": pair, "rows": int(len(df)),
                "id_min": int(df["trade_id"].min()), "id_max": int(df["trade_id"].max()),
                "t_min_utc": dt.datetime.fromtimestamp(float(df["time_s"].min()), dt.timezone.utc).isoformat(timespec="seconds"),
                "t_max_utc": dt.datetime.fromtimestamp(float(df["time_s"].max()), dt.timezone.utc).isoformat(timespec="seconds")}


def backfill_pair(feed: Any, store: TickStore, pair: str, since_ns: int, *,
                  until_ns: int | None = None, max_calls: int = 10_000,
                  flush_pages: int = 25, sleep: Any = time.sleep) -> dict:
    """Walk the tape forward from the cursor (or since_ns) page by page.

    Exit conditions, all owned here: a short page (end of tape), the cursor
    reaching until_ns, the call budget, a cursor that fails to advance
    (stall guard), or _MAX_FAILURES consecutive failed calls."""
    cur = store.read_cursor(pair)
    cursor_ns = max(cur["last_ns"], since_ns) if cur else since_ns
    last_id = cur["last_id"] if cur else 0
    calls = fetched = added = failures = 0
    buf: list[dict] = []
    reason = "budget"

    def flush() -> None:
        nonlocal added, buf
        if buf:
            added += store.append(pair, buf)
            buf = []
        store.write_cursor(pair, cursor_ns, last_id)

    while calls < max_calls:
        result = feed._public_get("Trades", {"pair": pair, "since": str(cursor_ns), "count": PAGE})
        calls += 1
        if result is None:
            failures += 1
            if failures >= _MAX_FAILURES:
                reason = "failures"
                break
            sleep(min(_MAX_BACKOFF_S, 2.0 ** failures))
            continue
        failures = 0
        rows, last_ns = parse_page(result, pair)
        if not rows:
            # nothing newer than the cursor: caught up (illiquid pairs
            # sit here for minutes between prints)
            reason = "end_of_tape"
            break
        fresh = [r for r in rows if r["trade_id"] > last_id]
        if last_ns is None or last_ns <= cursor_ns:
            # rows came back but the cursor did not move: the exact shape
            # of the float-truncated-cursor bug. Keep what arrived, stop.
            reason = "stalled"
            buf.extend(fresh)
            break
        buf.extend(fresh)
        fetched += len(fresh)
        if fresh:
            last_id = fresh[-1]["trade_id"]
        cursor_ns = last_ns
        if calls % flush_pages == 0:
            flush()
        if len(rows) < PAGE:
            reason = "end_of_tape"
            break
        if until_ns is not None and cursor_ns >= until_ns:
            reason = "until"
            break
    flush()
    return {"pair": pair, "calls": calls, "fetched": fetched, "added": added,
            "cursor_ns": cursor_ns, "last_id": last_id, "stop": reason}


def probe(feed: Any, pair: str = "XBTUSD") -> list[dict]:
    """Re-run the reach experiment: one call per `since`, report what came
    back. This is the measurement the docstring cites - re-derive it."""
    out = []
    for label, since_ns in (("epoch", 0), ("2020-01-01", to_ns("2020-01-01")),
                            ("corpus_start_2026-07-13", to_ns("2026-07-13"))):
        result = feed._public_get("Trades", {"pair": pair, "since": str(since_ns), "count": PAGE})
        rows, last_ns = parse_page(result or {}, pair)
        rec = {"since": label, "n": len(rows), "last_ns": last_ns}
        if rows:
            rec.update({"first_id": rows[0]["trade_id"],
                        "first_utc": dt.datetime.fromtimestamp(rows[0]["time_s"], dt.timezone.utc).isoformat(timespec="seconds"),
                        "sides": sorted({r["side"] for r in rows}),
                        "otypes": sorted({r["otype"] for r in rows})})
        out.append(rec)
    return out


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__ or "",
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pairs", default="BTC,ETH", help="comma list of assets (BTC,ETH,ADA...)")
    ap.add_argument("--quote", default="USD")
    ap.add_argument("--since", default="2026-07-13", help="ISO date/datetime UTC or epoch seconds")
    ap.add_argument("--until", default=None, help="stop once the cursor passes this (ISO/epoch)")
    ap.add_argument("--max-calls", type=int, default=10_000, help="per pair, per run")
    ap.add_argument("--rate", type=float, default=1.0,
                    help="calls per second; 3/s sustained trips the venue limit (measured, see docstring)")
    ap.add_argument("--root", default=str(DEFAULT_ROOT))
    ap.add_argument("--config", default="config.json")
    ap.add_argument("--probe", action="store_true", help="run the reach experiment on XBTUSD and exit")
    ap.add_argument("--coverage", action="store_true", help="print store coverage per pair and exit (no network)")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")

    store = TickStore(args.root)
    pairs = [kraken_pair(a.strip(), args.quote) for a in args.pairs.split(",") if a.strip()]
    if args.coverage:
        for p in pairs:
            print(json.dumps(store.coverage(p)))
        return 0

    cfg = load_config(args.config)
    cfg.setdefault("exchanges", {}).setdefault("kraken", {})["rate_limit_per_sec"] = args.rate
    feed = build_feed("kraken", cfg)
    if args.probe:
        print(f"[K] probe read {dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')}")
        for rec in probe(feed):
            print(json.dumps(rec))
        return 0

    since_ns = to_ns(args.since)
    until_ns = to_ns(args.until) if args.until else None
    rc = 0
    for p in pairs:
        t0 = time.monotonic()
        res = backfill_pair(feed, store, p, since_ns, until_ns=until_ns, max_calls=args.max_calls)
        res["seconds"] = round(time.monotonic() - t0, 1)
        res["coverage"] = store.coverage(p)
        print(json.dumps(res))
        if res["stop"] in ("failures", "stalled"):
            rc = 1
    return rc


if __name__ == "__main__":
    sys.exit(main())
