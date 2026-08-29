"""
scripts/candle_backfill.py — LANE B: venue backfill into the candle store.

SAFE class. Read-only public GETs plus appends into outputs/candles/. It
places no order, reads no credential-bearing endpoint, and is imported by
nothing in the decision path.

WHAT IT IS FOR. The store's PRIMARY lane is scripts/candle_collect.py,
which recovers the 5m path the labeler's ring buffer is discarding right
now at zero API cost and is byte-comparable to the corpus's entry_price.
THIS lane fills the PAST, which that one can never reach. Run the
collector first.

IT CONSTRUCTS ITS OWN FEED CLIENTS AND NEVER BORROWS THE ENGINE'S. main.py
builds ONE KrakenFeed and hands that SAME instance to OrderManager, whose
ThrottledRestClient holds a threading.Lock ACROSS its sleep - a backfill on
that object would serialize directly against live order placement. It also
reuses the SHIPPED feed classes rather than a new HTTP client, so every
call goes through the repo's own throttle, its 16 MB bounded-body decode,
and core.sanitize.

VENUE REACH. The figures below marked RUN were obtained by running this
script against the live venues on 2026-08-29 and reading the store back
(docs/quant/2026-08-29_candle_store_coverage.md holds the stamps); the
rest are structural properties of the endpoint. Re-derive, never recall.
  * Kraken serves 720 committed bars per interval and `since` DOES NOT
    page backward. RUN: 30.0 days at 1h, 119.8 days at 4h, 719 days at 1d.
    It is the execution venue and the depth-starved one. It cannot
    backfill 1h history older than its cap - which is why a corpus study
    that needs the execution venue's own quote must trade anchor precision
    for reach by dropping to 4h.
  * OKX /market/history-candles pages backward with the `after` cursor.
    RUN: 2879 hourly bars = 119.9 days at --total 2880, every asset in the
    live universe present. Deeper is a --total change, untested.
  * Binance.US honours startTime at the venue, but data/binanceus_feed.py
    sends only symbol/interval/limit, so through the SHIPPED client its
    reach is one page (<= 1000 bars). RUN: 999 bars = 41.6 days at 1h.
    Deepening it means extending that signature (extend-never-rename:
    optional start_ms defaulted to None) - a separate, reviewed change,
    not something to smuggle in here.
  * Binance.US has no MINA at all (RUN: HTTP 400, recorded EMPTY, coverage
    claims nothing), and ARB/PAXG/FLOW are USDT-only there.
    Filling a USD series from a USDT one is the era-confound shape, so the
    quote is part of the store key and this script refuses to pretend.

    AND THE ONE THAT IS NOT A REFUSAL: a DELISTED Binance.US USD pair
    still answers 200 with a well-formed body - the frozen final page.
    RUN: ARBUSD / PAXGUSD / FLOWUSD each returned 1000 bars dated
    2023-05-16 -> 2023-06-27 in response to a request for the most recent
    1000. Nothing in the response says so. The store contains it because
    coverage is derived from the RESPONSE's own timestamps, so those lanes
    answer BEYOND_RIGHT_EDGE at a 2026 anchor rather than a stale price -
    but `lanes` shows them populated. A LANE BEING POPULATED IS NOT A LANE
    BEING CURRENT: read t_min_s/t_max_s, never the row count.

BATCH ACCUMULATION IS A RULE, NOT AN OPTIMISATION. Every page of one
(symbol, interval, source, quote) run is accumulated and handed to
candle_journal.ingest() ONCE. Per-page ingest is quadratic, and
data/okx_feed.py pages backward in 100-row chunks.

RESUMABLE AND IDEMPOTENT by construction, not by bookkeeping: the store's
duplicate resolution compares the RENDERED value text and excludes
ingest_s, so re-running this script over an already-populated store
appends ZERO bytes. There is no cursor file to corrupt.

--dry-run PRINTS THE PLAN AND TOUCHES NEITHER THE NETWORK NOR THE STORE.
That is the run an operator wants before spending calls: it shows the lane
table, the venue endpoint each lane would use, the symbol mapping, and
what the store already covers.

Usage:
    python scripts/candle_backfill.py --dry-run
    python scripts/candle_backfill.py --venue okx --interval 3600 \\
        --symbols ETH,BTC --total 2880
    python scripts/candle_backfill.py --venue kraken --interval 86400 \\
        --root outputs/candles
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from data import candle_journal as cj          # noqa: E402

# Venue -> how that venue's committed boundary was established. Stored per
# row so an audit can segment on skew exposure: Kraken cuts on its own
# `last`, OKX on the per-row `confirm` flag, Binance.US has no venue flag
# and falls back to the local clock (zero skew tolerance, by design).
COMMITTED_BY = {"kraken": "venue_last", "okx": "venue_confirm",
                "binanceus": "clock"}

# Kraken denomination aliases. KrakenFeed.kraken_pair is a bare
# replace('/',''), and the XBT/XDG alias map is populated only as a side
# effect of get_pair_meta - it starts EMPTY in a fresh analysis process.
_KRAKEN_ASSET = {"BTC": "XBT", "DOGE": "XDG"}

_OKX_BAR = {60: "1m", 300: "5m", 900: "15m", 1800: "30m", 3600: "1H",
            14400: "4H", 86400: "1D"}
_BINANCE_INTERVAL = {60: "1m", 300: "5m", 900: "15m", 1800: "30m",
                     3600: "1h", 14400: "4h", 86400: "1d"}


def load_config(path: str | Path = "config.json") -> dict:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def venue_symbol(venue: str, asset: str, quote: str) -> str:
    """asset+quote -> the venue's own instrument name."""
    if venue == "kraken":
        return f"{_KRAKEN_ASSET.get(asset, asset)}{quote}"
    if venue == "okx":
        return f"{asset}-{quote}"
    if venue == "binanceus":
        return f"{asset}{quote}"
    raise ValueError(f"unknown venue {venue!r}")


def _strip_credentials(feed: Any) -> Any:
    """Make the public-only property STRUCTURAL, not a comment.

    Passing no credential keys is not the same as building a client that
    HAS none: KrakenFeed.__init__ resolves api_key/api_secret from the
    ENVIRONMENT (KRAKEN_API_KEY / KRAKEN_API_SECRET) irrespective of the
    config handed to it, and on the operator box those are set - so this
    analysis process would otherwise hold a live, signing-capable client
    exposing _private_post and the cancel/open-order calls. Nothing here
    calls them; the defect is that the SAFE classification would rest on
    prose, leaving a comment as the only guardrail against a future edit,
    an exception path that dumps the object, or a repr in a crash log.
    Blanking is done HERE rather than in the shipped feed class so no
    decision-path module changes. Pinned by test_candle_backfill_public_only.
    """
    for attr in ("api_key", "api_secret", "api_passphrase", "passphrase"):
        if getattr(feed, attr, None):
            setattr(feed, attr, "")
    return feed


def build_feed(venue: str, config: Mapping[str, Any]) -> Any:
    """A FRESH, CREDENTIAL-FREE client per run - never the engine's live
    instance. Only the throttle is carried over from config, and any
    credential the feed class resolved for itself is blanked before the
    object is returned (see _strip_credentials)."""
    ex = dict((config.get("exchanges") or {}).get(venue) or {})
    cfg = {"rate_limit_per_sec": ex.get("rate_limit_per_sec", 3)}
    if venue == "kraken":
        from data.kraken_feed import KrakenFeed
        return _strip_credentials(KrakenFeed(cfg))
    if venue == "okx":
        from data.okx_feed import OKXFeed
        return _strip_credentials(OKXFeed(cfg))
    if venue == "binanceus":
        from data.binanceus_feed import BinanceUSFeed
        return _strip_credentials(BinanceUSFeed(cfg))
    raise ValueError(f"unknown venue {venue!r}")


def fetch_lane(feed: Any, venue: str, asset: str, quote: str,
               interval_s: int, total: int) -> list[dict]:
    """One accumulated, sanitized, committed-only page set for one lane.

    Every row has already been through core.sanitize.clean_candles and the
    venue's forming-bar cut inside the shipped feed class - raw venue JSON
    never reaches the store, or the Infinity/NaN and ordering class comes
    back. Returns oldest-first bars with `time` in SECONDS."""
    sym = venue_symbol(venue, asset, quote)
    if venue == "kraken":
        return list(feed.get_candles(sym, interval=interval_s // 60))
    if venue == "okx":
        bar = _OKX_BAR[interval_s]
        # The paginating endpoint, accumulated across pages by the client
        # and ingested ONCE by the caller.
        return list(feed.get_history_candles(sym, bar=bar, total=total))
    if venue == "binanceus":
        return list(feed.get_candles(sym, interval=_BINANCE_INTERVAL[interval_s],
                                     limit=min(max(total, 1), 1000)))
    raise ValueError(f"unknown venue {venue!r}")


def backfill_lane(asset: str, interval_s: int, venue: str, quote: str, *,
                  fetch: Callable[[], list[dict]],
                  root: Path | str | None = None,
                  now_s: int | None = None) -> cj.IngestReport:
    """Fetch one lane and ingest it ONCE.

    A fetch that returns nothing is AMBIGUOUS at this layer: data/_http.py
    _get_json returns None on BOTH a transport failure and a hostile-body
    rejection, and every get_candles turns that None into []. So an empty
    result is recorded with status="EMPTY" and the store's empty-window
    sentinel, which claims NO coverage at all. A FAILED FETCH MUST NEVER
    WIDEN COVERAGE - the alternative reports a write that died as "we
    looked and the venue had nothing"."""
    now = int(time.time()) if now_s is None else int(now_s)
    committed_by = COMMITTED_BY[venue]
    try:
        raw = fetch()
    except Exception:                              # noqa: BLE001
        # The shipped feeds already swallow transport errors into []; this
        # catches anything else (a mapping miss, a venue schema change) and
        # records it as a FETCH_FAILED observation rather than crashing a
        # multi-lane run half way through.
        return cj.ingest(asset, interval_s, venue, quote, [],
                         committed_upto_s=now, committed_by=committed_by,
                         asked_from_s=None, asked_to_s=None,
                         status="FETCH_FAILED", now_s=now, root=root)
    times = [b.get("time") for b in raw
             if isinstance(b.get("time"), (int, float))]
    if not raw or not times:
        return cj.ingest(asset, interval_s, venue, quote, [],
                         committed_upto_s=now, committed_by=committed_by,
                         asked_from_s=None, asked_to_s=None, status="EMPTY",
                         now_s=now, root=root)
    # The shipped feeds have ALREADY cut the forming bar against venue
    # truth (Kraken `last`, OKX `confirm`) or the clock, so the newest row
    # they return IS the committed boundary. Deriving it from the response
    # rather than the wall clock is the same rule the collector's per-asset
    # right-edge clamp enforces, and for the same reason: a wall-clock
    # right edge claims coverage over bars that were never observed.
    committed_upto = int(max(float(t) for t in times))
    return cj.ingest(asset, interval_s, venue, quote, raw,
                     committed_upto_s=committed_upto,
                     committed_by=committed_by,
                     asked_from_s=None, asked_to_s=None, status="OK",
                     now_s=now, root=root)


def _plan_row(asset: str, interval_s: int, venue: str, quote: str,
              root: Path | str | None) -> dict[str, Any]:
    series = cj.Series(venue, quote)
    try:
        wins = cj.covered_windows(asset, interval_s, series=series, root=root)
    except cj.CandleStoreUnreadable as exc:
        return {"asset": asset, "interval_s": interval_s, "venue": venue,
                "quote": quote, "venue_symbol": venue_symbol(venue, asset, quote),
                "covered_windows": 0, "right_edge_s": None,
                "store": f"UNREADABLE: {exc}"}
    return {"asset": asset, "interval_s": interval_s, "venue": venue,
            "quote": quote, "venue_symbol": venue_symbol(venue, asset, quote),
            "covered_windows": len(wins),
            "right_edge_s": wins[-1][1] if wins else None,
            "store": "ok"}


def run(assets: Sequence[str], intervals: Sequence[int], venue: str,
        quote: str, *, total: int, root: Path | str | None,
        dry_run: bool, config_path: str | Path = "config.json",
        feed: Any = None) -> int:
    """Returns a process exit code. 0 = every lane produced an OK
    observation; 1 = at least one lane recorded FETCH_FAILED/EMPTY."""
    if dry_run:
        print(f"DRY RUN - no network call, no store write. venue={venue} "
              f"quote={quote} total={total} root={cj.store_root(root)}")
        print(f"{'asset':<8}{'interval_s':>11}  {'venue_symbol':<16}"
              f"{'covered_windows':>16}{'right_edge_s':>14}  store")
        for asset in assets:
            for interval_s in intervals:
                r = _plan_row(asset, interval_s, venue, quote, root)
                print(f"{r['asset']:<8}{r['interval_s']:>11}  "
                      f"{r['venue_symbol']:<16}{r['covered_windows']:>16}"
                      f"{str(r['right_edge_s']):>14}  {r['store']}")
        return 0

    if feed is None:
        feed = build_feed(venue, load_config(config_path))
    bad = 0
    print(f"{'asset':<8}{'interval_s':>11}{'offered':>9}{'accepted':>10}"
          f"{'dup':>7}{'conflict':>10}{'rejected':>10}  "
          f"{'win_from_s':>12}{'win_to_s':>12}  status  written  "
          f"rejected_by_reason")
    for asset in assets:
        for interval_s in intervals:
            rep = backfill_lane(
                asset, interval_s, venue, quote,
                fetch=lambda a=asset, i=interval_s: fetch_lane(
                    feed, venue, a, quote, i, total),
                root=root)
            # `written` counts as badly as a non-OK status. durable_append
            # never raises and returns False on OSError, so a lane whose
            # append died prints accepted=N for N bars that never reached
            # disk; and status=="LOCKED" writes nothing at all. Neither may
            # exit 0.
            if rep.status != "OK" or not rep.written:
                bad += 1
            print(f"{rep.symbol:<8}{rep.interval_s:>11}{rep.bars_offered:>9}"
                  f"{rep.bars_accepted:>10}{rep.bars_dup:>7}"
                  f"{rep.bars_conflict:>10}{rep.bars_rejected:>10}  "
                  f"{rep.win_from_s:>12}{rep.win_to_s:>12}  {rep.status}  "
                  f"{str(rep.written):<7}  {rep.rejected_by_reason or ''}")
    print(f"lanes with a non-OK or unwritten observation: {bad}")
    print("re-derive the store's own numbers with: "
          "python scripts/candle_store.py verify")
    return 1 if bad else 0


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__ or "",
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--venue", default="okx", choices=sorted(COMMITTED_BY))
    ap.add_argument("--quote", default="USD", choices=sorted(cj.QUOTES))
    ap.add_argument("--symbols", default="ETH,BTC",
                    help="comma-separated assets, e.g. ETH,BTC,SUI")
    ap.add_argument("--interval", type=int, action="append", dest="intervals",
                    help=f"seconds, one of {cj.INTERVALS}; repeatable")
    ap.add_argument("--total", type=int, default=2880,
                    help="bars to request per lane (OKX pages to reach it)")
    ap.add_argument("--root", default=None, help="store root")
    ap.add_argument("--config", default="config.json")
    ap.add_argument("--dry-run", action="store_true",
                    help="print the plan; no network call, no store write")
    args = ap.parse_args(argv)
    assets = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    intervals = args.intervals or [3600]
    for iv in intervals:
        if iv not in cj.INTERVALS:
            ap.error(f"--interval must be one of {cj.INTERVALS}, got {iv}")
    if args.venue == "kraken" and any(i not in (60, 300, 900, 1800, 3600,
                                                14400, 86400)
                                      for i in intervals):
        ap.error("kraken intervals are whole minutes")
    return run(assets, intervals, args.venue, args.quote, total=args.total,
               root=args.root, dry_run=args.dry_run,
               config_path=args.config)


if __name__ == "__main__":
    raise SystemExit(main())
