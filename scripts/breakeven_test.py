"""scripts/breakeven_test.py - is there ANY edge before costs?

THE ONE QUESTION THIS ANSWERS. Every remedy discussed for this bot - longer
horizons, maker-only execution, entry banding, gate filtering, meta-labeling,
sample weighting - operates on COST or on SELECTION. Every one of them is
irrelevant if the strategy has negative expectancy with the fees set to zero.
So that is the first thing to measure, and it had not been.

WHY NOT THE EARLIER ESTIMATE. A previous pass approximated gross P&L as
`net + assumed_flat_cost` and concluded gross was about -0.34%/trade. That
is first-order but it ADDS BACK A NUMBER RATHER THAN REMOVING A MEASURED
ONE, and it cannot separate fees from slippage. This reconstructs P&L from
outputs/fills.csv - real fill prices and real per-fill fees_delta_usd - so
the fee term is removed, not estimated.

METHOD. Fills carry purpose (entry/hedge/exit) and side (buy/sell). Summing
signed cash flows works for BOTH directions without a direction column: a long
buys then sells, a short sells then buys, and in each case

    gross_usd = (proceeds from every sell) - (cost of every buy)

is the correct P&L. Fees are then subtracted separately, which is what makes
the fee term removable. Positions are included only when the exited size
matches the entered size within tolerance - a partially-closed position has
an unrealized leg and its "P&L" would be an artifact of where the data ends.

HEDGE IS AN OPENING LEG, CORRECTED 2026-08-09. This tool tested
`purpose == "entry"` for the opening side, so any position opened by a HEDGE
leg had entry_sz == 0 and was dropped as "partial or malformed" - 159 of 400
round trips, 66% of all fees ever paid, silently absent from the one number
that decides whether this bot should keep running. main.py debits the entry
fee for every non-exit leg, so a hedge opens risk exactly as an entry does.
The skip counter is now broken out by reason precisely because a single
pooled "skipped" total is what let a 40%-of-the-book exclusion look routine.

DEDUPLICATION, ADDED 2026-08-02 AFTER THIS TOOL GOT IT WRONG. An earlier
run of this script reported mean gross -1.32%/trade and that number was
wrong by 27x. One fabricated ETH position had been written to fills.csv
under 16 distinct position_ids, and keying on position_id counted it 16
times - it alone was 66% of all apparent losses. Positions are now keyed by
their FILL PATTERN instead. The duplicates correlated 1:1 with bot restarts
rather than market events, which points at fills being re-logged on position
restore; THAT BUG IS NOT FIXED, only its output was quarantined, so the
dedupe is a live defence and not history.

WHAT A RESULT MEANS. Read the mean and the median together - a mean alone
cannot tell a broadly losing strategy from a slightly asymmetric one, and
mistaking the second for the first is what the -1.32% error did.
  gross > 0, net < 0   Cost is the binding constraint. Maker fees, banding
                       and holding period are the levers, and they can work.
  gross <= 0, median   Not "no edge". Trades win more often than they lose;
  positive             the average loser is simply bigger than the average
                       winner. That is exit geometry, and it is fixable
                       without touching the signal. Run
                       scripts/cost_attribution.py, which decomposes this
                       into win rate vs payoff ratio and computes the win
                       rate needed to break even at each fee schedule.
  gross <= 0, median   Broadly negative. No execution or selection change
  negative             fixes it, because none of them create expectancy
                       that is not there. The question stops being "how do
                       we keep more of the edge" and becomes "is there a
                       signal at all" - which a random-entry control at the
                       same horizon answers, not another model.

    python scripts/breakeven_test.py [--json]

Report-only. Reads outputs/fills.csv, touches no decision path.
"""
import argparse
import csv
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Legs that OPEN risk. A hedge is an opening leg: main.py fires the entry-fee
# path for every non-exit leg, and a hedge's cash flow enters gross P&L the
# same way an entry's does. Testing only for "entry" dropped every
# hedge-opened round trip - see the docstring.
_OPEN_PURPOSES = ("entry", "hedge")


def _f(v):
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def median(xs):
    s = sorted(xs)
    n = len(s)
    if not n:
        return 0.0
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2.0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fills", default=str(ROOT / "outputs" / "fills.csv"))
    ap.add_argument("--tol", type=float, default=0.02,
                    help="max |entry-exit| size mismatch, as a fraction")
    ap.add_argument("--json", action="store_true")
    ns = ap.parse_args()

    p = Path(ns.fills)
    if not p.exists():
        print(f"no fills at {p}")
        return 1
    by_pos = defaultdict(list)
    with open(p, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r.get("position_id"):
                by_pos[r["position_id"]].append(r)

    # Skips are counted BY REASON. A pooled total cannot distinguish "a few
    # partials at the edge of the file" from "40% of the book is structurally
    # invisible", and the second is what was actually happening.
    trades, skipped, deduped = [], Counter(), 0
    seen = set()
    for pid, fills in by_pos.items():
        cash = 0.0          # + on sells, - on buys
        fees = 0.0
        entry_sz = exit_sz = 0.0
        entry_notional = 0.0
        ok = True
        sig = []
        for r in fills:
            sz, px = _f(r.get("fill_size")), _f(r.get("fill_price"))
            # A missing fee is NOT a zero fee. Coercing it to 0.0 silently
            # understates cost, which is the direction that manufactures
            # profit; drop the position instead. No row currently trips
            # this - it is a guard against a future writer, and it matches
            # what cost_attribution.py already does.
            fee = _f(r.get("fees_delta_usd"))
            if sz is None or px is None or fee is None or sz <= 0 or px <= 0:
                ok = False
                break
            cash += (sz * px) if r.get("side") == "sell" else -(sz * px)
            fees += fee
            if r.get("purpose") in _OPEN_PURPOSES:
                entry_sz += sz
                entry_notional += sz * px
            elif r.get("purpose") == "exit":
                exit_sz += sz
            sig.append((r.get("purpose"), r.get("side"),
                        round(sz, 6), round(px, 4)))
        if not ok:
            skipped["malformed_row"] += 1
            continue
        if entry_sz <= 0 or entry_notional <= 0:
            skipped["no_opening_leg"] += 1
            continue
        if exit_sz <= 0:
            skipped["still_open"] += 1
            continue
        # Fully-closed only: an open leg's "P&L" is an artifact of the
        # dataset's end date, not a result.
        if abs(exit_sz - entry_sz) / entry_sz > ns.tol:
            skipped["size_mismatch"] += 1
            continue
        # position_id is deliberately NOT the identity: it is the field
        # that carried a 16x duplication of one position and produced a
        # 27x error in this tool's headline number. The fill pattern is.
        key = tuple(sig)
        if key in seen:
            deduped += 1
            continue
        seen.add(key)
        gross = cash                 # fees NOT yet applied
        net = gross - fees
        trades.append({
            "pid": pid, "notional": entry_notional,
            "gross_usd": gross, "fees_usd": fees, "net_usd": net,
            "gross_pct": 100.0 * gross / entry_notional,
            "fees_pct": 100.0 * fees / entry_notional,
            "net_pct": 100.0 * net / entry_notional,
        })

    n = len(trades)
    if not n:
        print("no fully-closed positions reconstructable")
        return 1
    g = [t["gross_pct"] for t in trades]
    c = [t["fees_pct"] for t in trades]
    net = [t["net_pct"] for t in trades]
    gw = sum(1 for v in g if v > 0)
    nw = sum(1 for v in net if v > 0)
    res = {
        "n": n, "skipped": sum(skipped.values()),
        "skipped_by_reason": dict(skipped), "deduped": deduped,
        "mean_gross_pct": sum(g) / n, "median_gross_pct": median(g),
        "mean_fees_pct": sum(c) / n, "median_fees_pct": median(c),
        "mean_net_pct": sum(net) / n, "median_net_pct": median(net),
        "gross_win_rate": gw / n, "net_win_rate": nw / n,
        "total_gross_usd": sum(t["gross_usd"] for t in trades),
        "total_fees_usd": sum(t["fees_usd"] for t in trades),
        "total_net_usd": sum(t["net_usd"] for t in trades),
    }
    if ns.json:
        print(json.dumps(res, indent=1))
        return 0

    print("BREAK-EVEN TEST - reconstructed from actual fills")
    print("=" * 64)
    n_skip = sum(skipped.values())
    print("%d fully-closed positions (%d skipped)" % (n, n_skip))
    if n_skip:
        # Named, not pooled: an exclusion nobody can see is an exclusion
        # nobody audits.
        print("  skipped by reason: %s"
              % ", ".join("%s=%d" % kv for kv in sorted(skipped.items())))
        print("  (%.1f%% of reconstructable round trips were excluded)"
              % (100.0 * n_skip / (n + n_skip)))
    if deduped:
        print("%d DUPLICATE fill patterns dropped - the same position was"
              % deduped)
        print("logged under more than one position_id. Duplicates track bot")
        print("restarts, not trades; see the docstring. Investigate before")
        print("trusting any per-position statistic from this dataset.")
    print()
    print("                         mean        median")
    print("  GROSS (fees zeroed) %+8.4f%%   %+8.4f%%" %
          (res["mean_gross_pct"], res["median_gross_pct"]))
    print("  fees                %+8.4f%%   %+8.4f%%" %
          (res["mean_fees_pct"], res["median_fees_pct"]))
    print("  NET                 %+8.4f%%   %+8.4f%%" %
          (res["mean_net_pct"], res["median_net_pct"]))
    print("\n  win rate  GROSS %.1f%%    NET %.1f%%"
          % (100 * res["gross_win_rate"], 100 * res["net_win_rate"]))
    print("\n  totals    gross $%+.2f   fees $%.2f   net $%+.2f"
          % (res["total_gross_usd"], res["total_fees_usd"],
             res["total_net_usd"]))

    print("\n" + "=" * 64)
    if res["mean_gross_pct"] > 0:
        print("GROSS EXPECTANCY IS POSITIVE (%+.4f%%/trade)."
              % res["mean_gross_pct"])
        print("Cost IS the binding constraint. Fees average %.4f%% and eat"
              % res["mean_fees_pct"])
        print("the edge. Maker-only execution, entry banding and holding")
        print("period are the levers, and they can work.")
    elif res["median_gross_pct"] > 0:
        # The mean is negative but the typical trade wins. Calling this
        # "no edge" is the error that produced the -1.32% headline: it
        # reads an asymmetry between win and loss SIZES as an absence of
        # signal. They are different problems with different fixes.
        print("GROSS MEAN IS NEGATIVE (%+.4f%%) BUT THE MEDIAN IS POSITIVE"
              % res["mean_gross_pct"])
        print("(%+.4f%%), and %.1f%% of trades win gross."
              % (res["median_gross_pct"], 100 * res["gross_win_rate"]))
        print("\nThis is NOT 'no edge'. Trades win more often than they lose;")
        print("the average loser is simply larger than the average winner.")
        print("That is exit geometry - stop distance, target distance, time")
        print("stop - and it is fixable without touching the signal.")
        print("\nRun scripts/cost_attribution.py next. It splits this into")
        print("win rate vs payoff ratio and computes the win rate needed to")
        print("break even at each fee schedule, which says whether the hit")
        print("rate or the trade sizes are the thing to move.")
    else:
        print("GROSS EXPECTANCY IS NEGATIVE (%+.4f%%/trade), median %+.4f%%."
              % (res["mean_gross_pct"], res["median_gross_pct"]))
        print("With every fee set to ZERO this strategy still loses, and the")
        print("typical trade loses too - so this is not a size asymmetry.")
        print("Cost is NOT the binding constraint - it is an aggravator. No")
        print("execution change, holding period, gate, filter or model")
        print("creates expectancy that is not in the entries to begin with.")
        print("\nNext question is no longer 'how do we keep more of the edge'")
        print("but 'is there an edge at all' - answered by a random-entry")
        print("control at the same horizon, not by another model.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
