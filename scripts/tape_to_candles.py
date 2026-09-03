"""Build sub-hour candles from the LOCAL Kraken trade tape and commit them
through the candle journal (read-only on the tape, journal-write only).

WHY (operator, 2026-09-02): the candle store held 3600 / 14400 / 86400 s
only, and the stop-hunt measurement needs sub-hour timing. Kraken's OHLC
endpoint serves 720 committed bars per interval and `since` does not page
backward (scripts/candle_backfill.py), so 15 m over 51 days is NOT
re-acquirable from the venue. The trade tape IS local for all 15 assets
(scripts/kraken_trades_backfill.py), and a bar is a deterministic
aggregation of trades, so any interval in data.candle_journal.INTERVALS can
be built exactly, offline, with no rate limit. 300 s is the bot's own bar
unit (ml.label_max_bars counts 5 m bars); 900 s is the operator's floor.

WHAT A BAR IS HERE. For each interval window [k*I, (k+1)*I): open = first
trade price, high/low = max/min, close = last, volume = sum of base volume.
A window with NO trades writes NO bar - the journal then answers
NO_BAR_IN_COVERED_WINDOW for it, which is the truth (a thin book printed
nothing), never a synthetic flat bar.

COMMIT BOUNDARY. committed_upto_s is the open of the last window that lies
ENTIRELY inside the tape (the tape's max trade time floored to the interval,
minus one interval). The forming window is never written and never claimed.

PROVENANCE. source='kraken' because the trades are Kraken's own prints;
committed_by='clock' because the boundary is derived from the tape's last
timestamp, not a venue confirm flag (the journal's vocabulary is a frozen
set; extending it is a data/ change and out of scope). The journal's
FIRST-COMMITTED-WINS rule means a later venue backfill of the same
(symbol, interval, kraken) lane will land as CONFLICT records rather than
replacing these - a documented consequence, and the reason `--force` does
not exist: there is nothing to force.

SAFE / measurement plane: writes only the candle journal under
outputs/candles through data.candle_journal.ingest(), which takes the
single-writer lock ITSELF per call (an O_EXCL per-pid lock, not re-entrant
- this script must NOT wrap it; the first live run did, and every call
refused against our own pid while the summary line read as success).
Touches no ledger. Any journal refusal, zero-accept batch, or per-asset
exception (a malformed tape row, a missing pair directory, anything else)
exits non-zero and is reported with status CRASHED - never silently, and
never at the cost of hiding what OTHER assets in the same run did
(adversarial review, 2026-09-02: an uncaught exception on one asset used
to abort the whole batch with no summary at all, discarding the visibility
of bars already committed for assets processed before the crash).

    python scripts/tape_to_candles.py --interval 300 --assets all
    python scripts/tape_to_candles.py --interval 900 --assets ETH,BTC,FLOW
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from data import candle_journal as cj                       # noqa: E402
from scripts.kraken_trades_backfill import (TickStore,      # noqa: E402
                                            kraken_pair)

ALL_ASSETS = ("BTC", "ETH", "ADA", "SOL", "XRP", "DOGE", "LINK", "DOT",
              "ARB", "SUI", "MINA", "FLOW", "AVAX", "LTC", "PAXG")
SOURCE = "kraken"
QUOTE = "USD"
COMMITTED_BY = "clock"


def aggregate(time_s: np.ndarray, price: np.ndarray, volume: np.ndarray,
              interval_s: int, *, tape_max_s: float | None = None
              ) -> tuple[list[dict[str, Any]], int | None]:
    """Pure. Trades -> committed bars + the committed_upto_s boundary.

    Windows are [k*I, (k+1)*I) on the raw epoch grid. Only windows lying
    entirely at or before the boundary are emitted; a window with no trades
    is simply absent. Returns ([], None) on an empty tape.
    """
    t = np.asarray(time_s, float)
    if t.size == 0:
        return [], None
    order = np.argsort(t, kind="stable")
    t, p, v = t[order], np.asarray(price, float)[order], np.asarray(volume, float)[order]
    tmax = float(t[-1]) if tape_max_s is None else float(tape_max_s)
    # last window that ENDS at or before the tape's last print: its open is
    # floor(tmax/I)*I - I  (the window containing tmax is still forming)
    committed_upto = int(tmax // interval_s) * interval_s - interval_s
    if committed_upto < int(t[0] // interval_s) * interval_s:
        return [], None
    win = (t // interval_s).astype("int64") * interval_s
    keep = win <= committed_upto
    win, p, v = win[keep], p[keep], v[keep]
    if win.size == 0:
        return [], None
    # boundaries of each window's run in the sorted array
    starts = np.flatnonzero(np.r_[True, win[1:] != win[:-1]])
    ends = np.r_[starts[1:], win.size]
    bars: list[dict[str, Any]] = []
    for s, e in zip(starts, ends, strict=True):
        seg_p = p[s:e]
        bars.append({"time": int(win[s]),
                     "open": float(seg_p[0]), "high": float(seg_p.max()),
                     "low": float(seg_p.min()), "close": float(seg_p[-1]),
                     "volume": float(v[s:e].sum())})
    return bars, int(committed_upto)


def build_asset(asset: str, interval_s: int, *, root: Path | str | None = None,
                store: TickStore | None = None, now_s: int | None = None) -> dict[str, Any]:
    """Aggregate one asset's tape and commit it. Returns a summary dict;
    never raises - on an empty tape, on a malformed tape, or on any other
    exception from the store/aggregate/ingest calls (records it instead).

    WHY (adversarial review, 2026-09-02, of this file's own first version).
    The prior version had no defense here: a single corrupted row (e.g. a
    NaN time_s from a truncated tape write) raised ValueError out of
    aggregate(), uncaught, and propagated through main()'s list
    comprehension - killing the ENTIRE multi-asset batch. Reproduced by
    execution, not argued: a NaN in the second of three assets left the
    first asset's bars ALREADY COMMITTED to the journal while the third
    asset was never attempted and main()'s reporting loop never ran at
    all - a raw traceback, no summary, no way to tell what succeeded. That
    is the exact failure this script's whole design exists to prevent (see
    "THE JOURNAL'S OWN STATUS IS THE VERDICT" below) via a path that
    bypassed the verdict machinery entirely. Every exception here is now
    caught PER ASSET and reported with the same "failure" key a journal
    refusal uses, so a bad row on one asset cannot hide the state of any
    other asset."""
    try:
        store = store or TickStore()
        pair = kraken_pair(asset)
        tape = store.load(pair)
        if tape is None or not len(tape):
            return {"asset": asset, "pair": pair, "interval_s": interval_s,
                    "status": "NO_TAPE", "bars": 0}
        bars, upto = aggregate(tape["time_s"].to_numpy(float),
                               tape["price"].to_numpy(float),
                               tape["volume"].to_numpy(float), interval_s)
    except Exception as exc:                                # noqa: BLE001
        # pair may be unset if kraken_pair() itself raised; fall back to
        # the raw asset name so the failure line is never missing a column
        pair = locals().get("pair", asset)
        return {"asset": asset, "pair": pair, "interval_s": interval_s,
                "status": "CRASHED", "bars": 0,
                "failure": f"{type(exc).__name__}: {exc}"}
    if not bars or upto is None:
        return {"asset": asset, "pair": pair, "interval_s": interval_s,
                "status": "EMPTY", "bars": 0}
    try:
        # note="" on purpose: the journal's `note` is a FROZEN vocabulary
        # (data.candle_journal.NOTES), not free text - the first run of
        # this script was refused at lane validation for passing a
        # provenance sentence here. Provenance lives in this module's
        # docstring and in committed_by='clock'. The pin that guards this
        # calls the REAL ingest against a temp root; a fake writer would
        # have accepted it.
        rep = cj.ingest(asset, interval_s, SOURCE, QUOTE, bars,
                        committed_upto_s=upto, committed_by=COMMITTED_BY,
                        asked_from_s=bars[0]["time"], asked_to_s=upto,
                        status="OK", now_s=now_s, note="", root=root)
    except Exception as exc:                                # noqa: BLE001
        # The journal's own write order is "evidence then claim, never
        # reversed" (data.candle_journal.ingest docstring): a crash here
        # can leave bars written with coverage not yet claimed, which is
        # self-healing (a later run re-derives and re-claims it) - never
        # the reverse. Safe to catch and report per-asset for the same
        # reason a journal LOCKED refusal is safe to catch below.
        return {"asset": asset, "pair": pair, "interval_s": interval_s,
                "status": "CRASHED", "bars": len(bars),
                "failure": f"ingest raised {type(exc).__name__}: {exc}"}
    # THE JOURNAL'S OWN STATUS IS THE VERDICT, never this script's. The
    # first live run printed "190,712 bars ... in 1.8s" while every row
    # read accepted 0: ingest() had refused (status LOCKED) because main()
    # was holding the single-writer lock that ingest() takes ITSELF. Exit
    # code 0 and a confident summary over zero writes - the verification
    # standard's item 3 failing on its author. A refusal or a batch with
    # nothing accepted is now a failure that names itself.
    j_status = str(getattr(rep, "status", "UNKNOWN"))
    accepted = int(getattr(rep, "bars_accepted", 0) or 0)
    dup = int(getattr(rep, "bars_dup", 0) or 0)
    out = {"asset": asset, "pair": pair, "interval_s": interval_s,
           "status": j_status, "bars": len(bars), "committed_upto_s": upto,
           "first_bar_s": bars[0]["time"], "tape_rows": int(len(tape))}
    for k in ("bars_offered", "bars_accepted", "bars_dup", "bars_conflict",
              "bars_rejected"):
        if hasattr(rep, k):
            out[k] = getattr(rep, k)
    if j_status != "OK":
        out["failure"] = f"journal refused: status={j_status}"
    elif accepted == 0 and dup == 0:
        out["failure"] = "journal accepted 0 of a non-empty batch and none were duplicates"
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--interval", type=int, default=300,
                    help=f"seconds; one of {cj.INTERVALS}")
    ap.add_argument("--assets", default="all",
                    help="comma list or 'all' (%s)" % ",".join(ALL_ASSETS))
    ap.add_argument("--root", default=None, help="journal root (tests)")
    args = ap.parse_args(argv)
    if args.interval not in cj.INTERVALS:
        ap.error(f"--interval must be one of {cj.INTERVALS}")
    assets = ALL_ASSETS if args.assets == "all" else tuple(
        a.strip().upper() for a in args.assets.split(",") if a.strip())
    t0 = time.time()
    # NO outer lock here: data.candle_journal.ingest() acquires the
    # single-writer lock ITSELF per call, and it is an O_EXCL per-pid lock
    # that is not re-entrant. Holding it around ingest() makes every call
    # refuse against our own pid (measured 2026-09-02: 15 refusals, 0 bars).
    store = TickStore()
    # PRINT AS WE GO, PER ASSET, AND CATCH HERE TOO (belt and suspenders).
    # build_asset() now catches everything it can raise, but a caller
    # crashing before this line was reproduced once already (adversarial
    # review, 2026-09-02): a NaN in one asset's tape killed the whole
    # batch, silently discarding bars already committed for prior assets
    # because the summary loop never ran. Printing incrementally means a
    # defect THIS defense-in-depth catch does not anticipate still leaves
    # every already-processed asset's line on the operator's screen,
    # rather than none of them.
    results: list[dict[str, Any]] = []
    failed = 0
    for a in assets:
        try:
            r = build_asset(a, args.interval, root=args.root, store=store)
        except Exception as exc:                            # noqa: BLE001
            r = {"asset": a, "pair": "?", "interval_s": args.interval,
                 "status": "CRASHED", "bars": 0,
                 "failure": f"build_asset raised {type(exc).__name__}: {exc}"}
        results.append(r)
        line = (f"  {r['asset']:5} {r['pair']:8} {r['interval_s']:>5}s  "
                f"bars {r['bars']:>7,}  accepted {r.get('bars_accepted', '-'):>7}  "
                f"dup {r.get('bars_dup', '-'):>5}  status {r['status']}")
        if r.get("failure"):
            failed += 1
            line += f"  !! {r['failure']}"
        print(line)
    total_acc = sum(int(r.get("bars_accepted", 0) or 0) for r in results)
    total_dup = sum(int(r.get("bars_dup", 0) or 0) for r in results)
    print(f"[K] offered {sum(r['bars'] for r in results):,} bars over {len(results)} "
          f"assets; ACCEPTED {total_acc:,}, duplicate {total_dup:,}; "
          f"{time.time() - t0:.1f}s; source={SOURCE} committed_by={COMMITTED_BY}")
    if failed:
        print(f"[!] {failed} asset(s) FAILED - see the !! lines; exit non-zero")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
