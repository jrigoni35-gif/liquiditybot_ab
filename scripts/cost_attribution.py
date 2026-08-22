"""scripts/cost_attribution.py - settle the fee question with measurement.

WHAT THIS SETTLES. Three cost claims were in play on 2026-08-02 and none of
them had a number attached:

  1. Are the configured fee constants (maker_fee_bps 25 / taker_fee_bps 40)
     stale relative to Kraken's schedule, or deliberately conservative?
  2. Is post_only honoured, or does the fee model ignore it?
  3. What is each discrepancy actually WORTH in P&L?

It answers all three from outputs/fills.csv, which records the real fill
price and the booked fee for every fill. Nothing here is asserted; every
line is computed.

ANSWERS AS OF 2026-08-02 (n=214, re-run to refresh - do not trust these
numbers if fills.csv has moved):

  2. post_only IS honoured. Booked rates are bimodal at exactly 25.0 bps
     (n=397, post_only=1) and 40.0 bps (n=286, post_only=0) - the config
     constants, applied correctly. An earlier claim that "~99% of fills book
     at taker rates" was WRONG: it compared against Kraken's 26 bps rather
     than against the bot's own 25 bps maker rate, so maker fills looked
     like taker fills. The flag works; the constants are what is high.
  1. SUPERSEDED 2026-08-22 - this line said "both constants exceed Kraken
     base tier (16/26)". It is BACKWARDS. 16/26 was a schedule this
     project struck on 2026-08-07; Kraken Tier 1 (this account, spot
     volume $0) is 40/80 bps, so the configured 25/40 is x0.542 of the
     venue - UNDERSTATED, the dangerous direction, which makes every
     counterfactual on this page optimistic. See the constants block.
  3. Section 3 computes it. SUPERSEDED: the old summary here said fees
     beat the gross gap "by an order of magnitude". That ratio divides
     by a quantity indistinguishable from zero - the equal-weighted mean
     gross sits inside 2x its day-clustered SE, its median is NEGATIVE,
     and dropping 5 of 434 trades flips it. Section 1b prints all of
     that now. Report cost ABSOLUTELY; never as a multiple of an edge
     whose interval contains zero.

TWO DISCIPLINES THIS TOOL ENFORCES.

DEDUPLICATION. Positions are keyed by their FILL PATTERN, not position_id.
One ETH position appeared under 16 distinct position_ids, and counting it 16
times produced a mean gross of -1.32% against a true -0.13% - an order of
magnitude, and 66% of all apparent losses. Those 64 rows are now quarantined
to outputs/fills.quarantine.csv, so the live file is clean and this dedupe
currently removes nothing.

IT STAYS ANYWAY. The duplicates correlated 1:1 with bot restarts, not with
market events: the same entry fill was written at 17:35, 21:35, 21:36 and
21:44 with identical price and size. That points at fills being re-logged on
position restore, and THAT BUG IS NOT FIXED - only its output was cleaned.
Until the restore path is read, duplicates can recur, and any analysis that
groups by position_id will silently inherit the error again. Note that
scripts/breakeven_test.py does NOT dedupe; it was the tool that reported
-1.32%, and it is only correct now because the bad rows were removed by
hand.

REPORT-ONLY. It never edits config.json. Over-stating cost is the SAFE
direction: a backtest that assumes fees higher than reality understates
profit, while one that assumes them lower manufactures it. If the constants
turn out to be deliberately conservative, lowering them makes every
historical result optimistic at once. The tool prints what the numbers say
and stops; changing them is an operator decision, and config.json:356
already carries an OM-080 reconciliation job that reads the ACTUAL Kraken
tier from the private TradeVolume endpoint. Check that before acting.

    python scripts/cost_attribution.py [--json]
"""
import argparse
import csv
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Legs that OPEN risk - a hedge opens a position exactly as an entry does.
# See scripts/breakeven_test.py's docstring; pinned by
# tests/test_opening_leg_pin.py.
_OPEN_PURPOSES = ("entry", "hedge")

# Kraken spot TIER 1 (the ENTRY tier - $0+ volume), verified 2026-08-21.
#
# CORRECTED 2026-08-22 (focused-fix cost-stack diagnosis). This file
# previously carried 16.0/26.0 with the note "lower tiers only reduce
# these, so using base is the conservative check". BOTH halves were
# wrong and the error ran in the FLATTERING direction:
#   * 16/26 is a schedule this project STRUCK on 2026-08-07. Kraken's
#     cross-platform tier change took effect 2026-07-09; Tier 1 is
#     40/80 bps. Secondary fee blogs still publish 0.25/0.40 as
#     "current", which is the live re-contamination vector that has now
#     put this same wrong number back into the codebase three times.
#   * The conservatism claim INVERTS at the true schedule. Tier 1 is the
#     MOST expensive row, not the cheapest: higher volume buys you DOWN
#     (T5 = 15/30). Benchmarking against 16/26 understated venue cost by
#     x0.65 when the account actually sits at x1.979 of configured.
# Understating cost makes every counterfactual optimistic, which is the
# dangerous direction - see this file's own closing note.
#
# NOT independently reconciled: OM-080 (execution/order_manager.py:767)
# has never fired on this box, so no venue measurement of the ACCOUNT's
# actual row exists. These constants settle the SCHEDULE, never the ROW.
KRAKEN_T1_MAKER_BPS = 40.0      # $0+        - this account (spot vol $0)
KRAKEN_T1_TAKER_BPS = 80.0
KRAKEN_T5_MAKER_BPS = 15.0      # deep-tier floor, for the headroom row
KRAKEN_T5_TAKER_BPS = 30.0


def _f(v):
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def med(xs):
    s = sorted(xs)
    n = len(s)
    if not n:
        return 0.0
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2.0


def load(path, tol=0.02):
    """Fully-closed positions, DEDUPLICATED BY FILL PATTERN.

    Returns (trades, skipped) where skipped is a Counter keyed by REASON.
    It used to return trades alone and drop the rest with a bare `continue`,
    which meant an exclusion of any size was indistinguishable from no
    exclusion at all - the same blindness that hid 159 hedge-opened round
    trips (40% of the book) from scripts/breakeven_test.py.
    """
    by_pid = defaultdict(list)
    with open(path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r.get("position_id"):
                by_pid[r["position_id"]].append(r)
    out, seen = [], set()
    skipped = Counter()
    # position_id is deliberately discarded: it is the field that carries
    # the 16x duplication, so keying on it is the bug this dedupe exists to
    # avoid. The fill pattern is the identity.
    for fills in by_pid.values():
        cash = fees = ez = xz = notional = 0.0
        t_close = None
        sig, ok = [], True
        maker_n = taker_n = 0
        for r in fills:
            sz, px = _f(r.get("fill_size")), _f(r.get("fill_price"))
            fee = _f(r.get("fees_delta_usd"))
            if not sz or not px or fee is None or sz <= 0 or px <= 0:
                ok = False
                break
            val = sz * px
            cash += val if r.get("side") == "sell" else -val
            fees += fee
            if r.get("purpose") in _OPEN_PURPOSES:
                ez += sz
                notional += val
            elif r.get("purpose") == "exit":
                xz += sz
            if str(r.get("post_only")) == "1":
                maker_n += 1
            else:
                taker_n += 1
            _rt = _f(r.get("ts"))
            if _rt is not None and (t_close is None or _rt > t_close):
                t_close = _rt
            sig.append((r.get("purpose"), r.get("side"),
                        round(sz, 6), round(px, 4)))
        if not ok:
            skipped["malformed_row"] += 1
            continue
        if ez <= 0 or notional <= 0:
            skipped["no_opening_leg"] += 1
            continue
        if xz <= 0:
            skipped["still_open"] += 1
            continue
        if abs(xz - ez) / ez > tol:
            skipped["size_mismatch"] += 1
            continue
        key = tuple(sig)
        if key in seen:
            skipped["duplicate_fill_pattern"] += 1
            continue
        seen.add(key)
        out.append({"notional": notional, "gross": cash, "fees": fees,
                    "t_close": t_close,
                    "gross_pct": 100.0 * cash / notional,
                    "fees_pct": 100.0 * fees / notional,
                    "maker_fills": maker_n, "taker_fills": taker_n,
                    "n_fills": len(fills)})
    return out, skipped


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fills", default=str(ROOT / "outputs" / "fills.csv"))
    ap.add_argument("--json", action="store_true")
    ns = ap.parse_args()
    p = Path(ns.fills)
    if not p.exists():
        print(f"no fills at {p}")
        return 1

    # --- 1. per-FILL effective rate, split by the post_only flag. This is
    # --- the direct test of whether post_only buys a maker fee at all.
    rows = list(csv.DictReader(open(p, newline="", encoding="utf-8")))
    by_flag = defaultdict(list)
    rate_hist = Counter()
    for r in rows:
        sz, px = _f(r.get("fill_size")), _f(r.get("fill_price"))
        fee = _f(r.get("fees_delta_usd"))
        if not sz or not px or fee is None or sz <= 0 or px <= 0:
            continue
        bps = 10000.0 * fee / (sz * px)
        by_flag[str(r.get("post_only"))].append(bps)
        rate_hist[round(bps, 1)] += 1

    trades, skipped = load(p)
    n = len(trades)
    if not n:
        print("no closed positions")
        return 1
    g = [t["gross_pct"] for t in trades]
    c = [t["fees_pct"] for t in trades]
    mean_g, med_g = sum(g) / n, med(g)
    mean_c = sum(c) / n

    # --- 2. what each fee schedule would cost, holding fills constant.
    # --- Round trip = entry leg + exit leg, so 2x the per-leg rate.
    schedules = {
        "configured (25/40)": None,          # measured, filled below
        "Kraken T1 maker/taker (40/80)": (KRAKEN_T1_MAKER_BPS
                                          + KRAKEN_T1_TAKER_BPS) / 100.0,
        "Kraken T1 maker/maker (40/40)": 2 * KRAKEN_T1_MAKER_BPS / 100.0,
        "Kraken T5 maker/maker (15/15)": 2 * KRAKEN_T5_MAKER_BPS / 100.0,
        "zero fees": 0.0,
    }
    schedules["configured (25/40)"] = mean_c

    # --- 3. decompose the mean into its two degrees of freedom. A mean is
    # --- a summary; win rate and payoff ratio are the things a strategy
    # --- change can actually move, and they say WHICH one is off.
    wins = [v for v in g if v > 0]
    losses = [v for v in g if v <= 0]
    p_win = len(wins) / n
    mean_w = sum(wins) / len(wins) if wins else 0.0
    mean_l = abs(sum(losses) / len(losses)) if losses else 0.0
    payoff = (mean_w / mean_l) if mean_l > 0 else float("inf")
    # Break-even payoff at the OBSERVED win rate, gross of fees.
    be_payoff = ((1 - p_win) / p_win) if p_win > 0 else float("inf")

    def be_winrate(cost):
        """Win rate needed to clear `cost`, holding win/loss SIZES fixed.

        p*W - (1-p)*L = cost  =>  p = (cost + L) / (W + L).
        Returns >1.0 when no win rate can clear the cost at this payoff
        ratio, which is the decisive case: it means the size asymmetry
        must change, not the hit rate.
        """
        d = mean_w + mean_l
        return float("inf") if d <= 0 else (cost + mean_l) / d

    res = {"n": n, "mean_gross_pct": mean_g, "median_gross_pct": med_g,
           "mean_fees_pct": mean_c,
           "gross_win_rate": p_win,
           "mean_win_pct": mean_w, "mean_loss_pct": -mean_l,
           "payoff_ratio": payoff, "breakeven_payoff": be_payoff,
           "breakeven_winrate_by_schedule": {k: be_winrate(v)
                                             for k, v in schedules.items()},
           "post_only_bps": {k: {"n": len(v), "median": med(v)}
                             for k, v in by_flag.items()},
           "net_by_schedule": {k: mean_g - v
                               for k, v in schedules.items()},
           "skipped": sum(skipped.values()),
           "skipped_by_reason": dict(skipped)}
    if ns.json:
        print(json.dumps(res, indent=1))
        return 0

    print("COST ATTRIBUTION - deduplicated by fill pattern")
    print("=" * 66)
    print("%d distinct closed positions" % n)
    n_skip = sum(skipped.values())
    if n_skip:
        # Named, not pooled. An unreported exclusion is an unauditable one.
        print("%d skipped (%.1f%% of round trips): %s"
              % (n_skip, 100.0 * n_skip / (n + n_skip),
                 ", ".join("%s=%d" % kv for kv in sorted(skipped.items()))))
    print()

    print("1. IS post_only BUYING A MAKER FEE?")
    for flag in sorted(by_flag):
        v = by_flag[flag]
        label = "post_only=1 (maker intended)" if flag == "1" \
            else "post_only=0 (taker)"
        print("   %-30s n=%-4d median %.1f bps" % (label, len(v), med(v)))
    m1, m0 = med(by_flag.get("1", [0])), med(by_flag.get("0", [0]))
    if abs(m1 - m0) < 1.0:
        print("   -> post_only makes NO difference to the booked fee.")
        print("      Either it is not honoured, or the fee model ignores it.")
    else:
        print("   -> post_only IS booking a different rate (%.1f vs %.1f)."
              % (m1, m0))
    print("   Kraken TIER 1 (this account, spot vol $0): maker %.0f / "
          "taker %.0f bps  -> configured 25/40 is x%.3f of venue"
          % (KRAKEN_T1_MAKER_BPS, KRAKEN_T1_TAKER_BPS,
             65.0 / (KRAKEN_T1_MAKER_BPS + KRAKEN_T1_TAKER_BPS)))
    print("   NOT venue-reconciled: OM-080 has never fired on this box,")
    print("   so the account's actual ROW is unverified (schedule only).")
    print("   observed rates: %s" % rate_hist.most_common(4))

    # --- 1b. DISPERSION. Added 2026-08-22 after this tool's own headline
    # --- ("mean gross +0.0733% (POSITIVE)") was taken for an edge and
    # --- built into a session-long thesis. The mean was equal-weighted,
    # --- its median sat NEGATIVE two sections away, and no interval was
    # --- printed anywhere. A point estimate with no dispersion beside it
    # --- invites over-reading; print the disagreement instead.
    tot_notional = sum(t["notional"] for t in trades)
    dw_gross = 100.0 * sum(t["gross"] for t in trades) / tot_notional
    dw_fees = 100.0 * sum(t["fees"] for t in trades) / tot_notional
    sd = (sum((x - mean_g) ** 2 for x in g) / (n - 1)) ** 0.5 if n > 1 else 0.0
    # day-cluster: trips held CONCURRENTLY share one market path, so an
    # iid SE over-counts independent observations (de Prado concurrency).
    days = defaultdict(list)
    for t in trades:
        days[int((t["t_close"] or 0) // 86400)].append(t["gross_pct"])
    gsum = [sum(v) for v in days.values()]
    gcnt = [len(v) for v in days.values()]
    G = len(days)
    if G > 1 and sum(gcnt):
        dmean = sum(gsum) / sum(gcnt)
        num = sum((gs - gc * dmean) ** 2 for gs, gc in zip(gsum, gcnt, strict=True))
        se_clu = (num ** 0.5) / sum(gcnt)
    else:
        se_clu = 0.0
    se_iid = sd / (n ** 0.5) if n else 0.0
    srt = sorted(trades, key=lambda t: t["gross_pct"], reverse=True)
    drop5 = [t["gross_pct"] for t in srt[5:]]
    mean_drop5 = sum(drop5) / len(drop5) if drop5 else 0.0

    print("")
    print("1b. DISPERSION - read this BEFORE the mean below")
    print("   mean gross (equal-weighted) %+.4f%%   median %+.4f%%"
          % (mean_g, med_g))
    print("   DOLLAR-WEIGHTED gross       %+.4f%%   ($%+.2f on $%.2f)"
          % (dw_gross, sum(t["gross"] for t in trades), tot_notional))
    print("   dollar-weighted fees        %+.4f%%" % dw_fees)
    print("   sd %.4f | SE iid %.4f t=%.3f | SE day-clustered %.4f t=%.3f (G=%d)"
          % (sd, se_iid, (mean_g / se_iid) if se_iid else 0.0,
             se_clu, (mean_g / se_clu) if se_clu else 0.0, G))
    print("   drop top 5 of %d trades -> mean %+.4f%%" % (n, mean_drop5))
    for lo, hi, lbl in ((0.0, 100.0, "  <$100"), (100.0, float("inf"), " >=$100")):
        b = [t for t in trades if lo <= t["notional"] < hi]
        if b:
            bn = sum(t["notional"] for t in b)
            print("   %s n=%-4d %5.1f%% of notional  mean %+.4f%%  dw %+.4f%%"
                  % (lbl, len(b), 100.0 * bn / tot_notional,
                     sum(t["gross_pct"] for t in b) / len(b),
                     100.0 * sum(t["gross"] for t in b) / bn))
    if se_clu and abs(mean_g) < 2.0 * se_clu:
        print("   ** the equal-weighted mean is INSIDE 2x its clustered SE:")
        print("   ** not distinguishable from zero. Do NOT quote a")
        print("   ** 'fees vs gross' RATIO - the denominator contains zero.")

    print("\n2. WHAT EACH SCHEDULE IS WORTH (mean gross %+.4f%%)" % mean_g)
    for k, v in schedules.items():
        print("   %-28s cost %.3f%%  ->  net %+.4f%%"
              % (k, v, mean_g - v))

    print("\n3. THE BREAK-EVEN QUESTION")
    print("   mean gross   %+.4f%%    median gross %+.4f%%"
          % (mean_g, med_g))
    print("   win rate %.1f%%   mean win %+.4f%%   mean loss %+.4f%%"
          % (100 * p_win, mean_w, -mean_l))
    print("   payoff ratio %.3f   (need %.3f to be gross-flat at this "
          "win rate)" % (payoff, be_payoff))

    # Which of the two knobs is off? Say it from the numbers, not from a
    # stored conclusion - an earlier version of this tool asserted "the
    # binding constraint is tail risk" and was wrong: that read was driven
    # by 16 duplicate rows of one fabricated trade, and once they were
    # quarantined the distribution came out near-symmetric.
    if payoff < be_payoff:
        print("\n   The win rate is FINE - %.1f%% of trades make money gross."
              % (100 * p_win))
        print("   The SIZES are wrong: losers average %.3f%% against winners"
              % mean_l)
        print("   at %.3f%%. That is an exit-geometry result, not a signal"
              % mean_w)
        print("   result, and not a tail: it is the average loser, not a")
        print("   rare one, that is oversized.")
    else:
        print("\n   Payoff ratio clears its break-even at this win rate; the")
        print("   mean is set by the hit rate, not by trade sizes.")

    print("\n   WIN RATE REQUIRED TO NET BREAK EVEN, holding sizes fixed:")
    impossible = []
    for k, v in schedules.items():
        need_p = be_winrate(v)
        if need_p > 1.0:
            impossible.append(k)
            print("   %-28s %6s  IMPOSSIBLE at payoff %.3f"
                  % (k, "-", payoff))
        else:
            print("   %-28s %5.1f%%  (observed %.1f%%)"
                  % (k, 100 * need_p, 100 * p_win))

    print()
    if impossible:
        print("   => No achievable win rate covers %d of %d fee schedules"
              % (len(impossible), len(schedules)))
        print("      while winners stay %.2fx the size of losers. Raising"
              % payoff)
        print("      the hit rate cannot fix this; only cutting the average")
        print("      loser or extending the average winner can. Fees are the")
        print("      larger term (%.3f%% against a %.3f%% gross gap) but"
              % (mean_c, abs(mean_g)))
        print("      cutting them to zero still leaves %+.4f%%." % mean_g)
    elif mean_g <= 0:
        print("   => Gross is negative, so no fee cut alone reaches profit,")
        print("      but the gap is reachable: %.1f%% win rate at zero fees"
              % (100 * be_winrate(0.0)))
        print("      against %.1f%% observed." % (100 * p_win))
    else:
        print("   => Mean gross is positive. Any round trip below %.3f%% is"
              % mean_g)
        print("      profitable in expectation; you are paying %.3f%%."
              % mean_c)
    print("\nREPORT-ONLY. Verify against the OM-080 reconciliation "
          "(config.json:356)")
    print("before changing any fee constant: under-stating cost makes every")
    print("backtest optimistic, which is the dangerous direction.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
