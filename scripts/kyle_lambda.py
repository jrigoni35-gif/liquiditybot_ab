"""scripts/kyle_lambda.py - the bot's OWN price impact, as a COST term.

WHAT THIS IS. Kyle (1985) models an informed trader's price impact as linear
in signed order flow: dP = lambda * Q. Estimated on THIS bot's own fills,
lambda answers a cost question, not a signal question:

    how many basis points does the market move against us, per dollar we
    take, over and above the fee?

WHY IT IS FRAMED AS COST AND NOT AS ALPHA - THIS MATTERS FOR GOVERNANCE.
CLAUDE.md records a MODEL FREEZE (operator adjudication 2026-08-10): no new
families, features, or meta-labeling until the era-4 gate reads out. A Kyle
lambda FEATURE fed to the meta-model would be squarely inside that freeze and
would also rotate the feature schema. This is not that. It computes a COST
from fills that already exist, prints it, and touches nothing - the same
class as execution/markout.py and scripts/cost_attribution.py. No feature
column, no schema change, no decision path. SAFE class, non-cohort-resetting.

WHY IT IS WORTH MEASURING AT ALL. The binding constraint on this strategy is
not signal, it is cost: measured 2026-08-23, aggregate fee rate 38.68 bps
against a gross markout edge of 9-12 bps on the majors. Impact is the cost
term NOTHING here currently measures - fees are booked, slippage is recorded
per fill, but the systematic relationship between SIZE and adverse move is
not estimated anywhere. If lambda is material at working size it belongs in
the cost stack; if it is not, that is worth knowing with a number attached
rather than assumed.

TAKER FILLS ONLY, AND THE REASON IS NOT COSMETIC. Kyle impact is the cost of
CONSUMING liquidity. A post_only fill PROVIDES it - the trade happens because
someone else crossed, so "impact" of our own passive quote is a different
quantity with the opposite sign convention. Measured on this corpus
post_only fills are 448 of 1122 and their slip is structurally near zero.
Pooling them would drag lambda toward zero and manufacture a reassuring
answer. They are reported separately, never merged.

THE PRIOR, STATED BEFORE THE MEASUREMENT. Median fill notional here is ~$18
on liquid venues. Self-impact at that size should be indistinguishable from
zero. If this tool reports a large lambda, the FIRST hypothesis is that the
instrument is wrong - endogeneity below, or slip_bps capturing something that
is not impact - not that a $18 order moved Kraken.

WHAT WOULD MAKE THIS ESTIMATE WRONG, stated up front rather than in a
footnote:
  * ENDOGENEITY. We do not place sizes at random. If the sizer takes more
    when the book is thin or when it is confident, size correlates with
    conditions that independently move price, and the regression attributes
    that to impact. This is the dominant threat and it CANNOT be fixed by
    more data - only by randomised size, which would be a decision-path
    change and is not proposed here.
  * slip_bps is measured against `arrival_ref`. It therefore contains
    latency and spread as well as impact; lambda estimated this way is an
    UPPER BOUND on true impact.
  * Selection: cancelled or unfilled orders leave no row, so the fills that
    exist are the ones that got done - which skews toward favourable states.

Report-only. Reads outputs/fills.csv, prints, exits 0.

    python scripts/kyle_lambda.py [--fills PATH] [--min-n N] [--json]
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import math
import sys
from pathlib import Path

DEFAULT_FILLS = Path("outputs") / "fills.csv"
# Below this an OLS slope is noise wearing a decimal point. Not tuned: it is
# the smallest n at which a two-sided t on a single regressor is worth
# printing at all, and the report says so rather than hiding thin cells.
DEFAULT_MIN_N = 30


def _f(row: dict, key: str) -> float:
    try:
        return float(row.get(key) or "nan")
    except (TypeError, ValueError):
        return float("nan")


def _ols(xs: list[float], ys: list[float]) -> dict:
    """Slope, intercept, SE, t, R^2. Plain OLS - no library, no hidden
    weighting, so the arithmetic is auditable by reading it."""
    n = len(xs)
    if n < 3:
        return {"n": n, "insufficient": True}
    mx = sum(xs) / n
    my = sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx <= 0:
        return {"n": n, "insufficient": True, "why": "no variation in size"}
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=True))
    beta = sxy / sxx
    alpha = my - beta * mx
    resid = [y - (alpha + beta * x) for x, y in zip(xs, ys, strict=True)]
    sse = sum(r * r for r in resid)
    syy = sum((y - my) ** 2 for y in ys)
    dof = n - 2
    se = math.sqrt((sse / dof) / sxx) if dof > 0 and sse > 0 else float("nan")
    return {
        "n": n, "insufficient": False,
        "lambda_bps_per_1k": beta * 1000.0,
        "intercept_bps": alpha,
        "se_bps_per_1k": se * 1000.0 if math.isfinite(se) else float("nan"),
        "t": beta / se if math.isfinite(se) and se > 0 else float("nan"),
        "r2": 1.0 - sse / syy if syy > 0 else float("nan"),
        "median_notional": sorted(xs)[n // 2],
    }


def load(fills: Path) -> list[dict]:
    try:
        with fills.open(encoding="utf-8", errors="replace", newline="") as f:
            return list(csv.DictReader(f))
    except OSError:
        return []


def estimate(rows: list[dict], min_n: int) -> dict:
    by: dict[tuple[str, str], list[tuple[float, float]]] = {}
    skipped = 0
    for r in rows:
        slip = _f(r, "slip_bps")
        size = _f(r, "fill_size")
        px = _f(r, "fill_price")
        if not (math.isfinite(slip) and math.isfinite(size)
                and math.isfinite(px)) or size <= 0 or px <= 0:
            skipped += 1
            continue
        notional = size * px
        side = (r.get("side") or "").lower()
        if side not in ("buy", "sell"):
            skipped += 1
            continue
        # UNSIGNED size is the correct regressor HERE, and getting this
        # wrong is easy. core/fill_ledger.py:89-90 computes
        #     raw  = (fill_price - arrival) / arrival * 1e4
        #     slip = raw if side == "buy" else -raw
        # so slip_bps is ALREADY side-normalised: positive means adverse, in
        # the trade's own direction, for buys and sells alike. It is a COST,
        # not a raw price change. Signing the notional on top of that applies
        # the sign TWICE and splits the sample into two mirror halves - the
        # first cut of this file did exactly that and produced a significant
        # NEGATIVE lambda for ADA (t=-4.12), i.e. "bigger orders got better
        # prices", which is not a market fact but an artefact of the double
        # sign. Kyle's dP = lambda*Q is stated on RAW price change and SIGNED
        # flow; with an already-signed cost the matching regressor is |Q|.
        signed = abs(notional)
        maker = (r.get("post_only") or "0").strip() in ("1", "true", "True")
        key = (r.get("symbol") or "?", "maker" if maker else "taker")
        by.setdefault(key, []).append((signed, slip))

    out = []
    for (sym, kind), pairs in sorted(by.items()):
        xs = [p[0] for p in pairs]
        ys = [p[1] for p in pairs]
        res = _ols(xs, ys)
        res.update({"symbol": sym, "kind": kind,
                    "below_floor": len(pairs) < min_n})
        out.append(res)
    out.sort(key=lambda d: (d["kind"] != "taker", -d["n"]))
    return {"cells": out, "skipped_rows": skipped, "min_n": min_n,
            "read_at": dt.datetime.now().isoformat(timespec="seconds")}


def _render(res: dict, fee_bps: float) -> None:
    print("KYLE LAMBDA - the bot's OWN impact, measured as a COST")
    print("=" * 78)
    print("read at %s   |   rows skipped (unusable): %d"
          % (res["read_at"], res["skipped_rows"]))
    print("")
    print("lambda is bps of adverse move per $1,000 of SIGNED taker flow.")
    print("Estimated on OUR fills only - this is self-impact, not a market-")
    print("wide lambda, and it is an UPPER BOUND (slip_bps carries latency")
    print("and spread as well as impact).")
    print("")
    hdr = ("%-12s %-6s %6s %14s %12s %8s %7s"
           % ("SYMBOL", "KIND", "N", "LAMBDA/$1k", "SE", "t", "R2"))
    print(hdr)
    print("-" * 78)
    for c in res["cells"]:
        if c.get("insufficient"):
            print("%-12s %-6s %6d   (insufficient: %s)"
                  % (c["symbol"], c["kind"], c["n"],
                     c.get("why", "n<3")))
            continue
        flag = "  <- below --min-n, do not read" if c["below_floor"] else ""
        print("%-12s %-6s %6d %14.4f %12.4f %8.2f %7.3f%s"
              % (c["symbol"], c["kind"], c["n"], c["lambda_bps_per_1k"],
                 c["se_bps_per_1k"], c["t"], c["r2"], flag))
    print("-" * 78)
    print("")
    print("MATERIALITY vs THE FEE STACK (%.2f bps aggregate, measured)"
          % fee_bps)
    shown = False
    for c in res["cells"]:
        if (c.get("insufficient") or c["below_floor"]
                or c["kind"] != "taker"):
            continue
        med = c["median_notional"]
        cost = abs(c["lambda_bps_per_1k"]) * abs(med) / 1000.0
        print("  %-10s at its median $%8.2f -> impact %6.3f bps "
              "= %5.2f%% of the fee stack"
              % (c["symbol"], abs(med), cost, 100.0 * cost / fee_bps))
        shown = True
    if not shown:
        print("  no taker cell cleared the sample floor - nothing to price.")
    print("")
    print("READ THIS BEFORE BELIEVING A LARGE LAMBDA:")
    print("  ENDOGENEITY is the dominant threat. Sizes are NOT random, so")
    print("  any correlation between size and conditions that independently")
    print("  move price is attributed here to impact. More data does not fix")
    print("  it; only randomised size would, and that is a decision-path")
    print("  change this tool does not propose.")
    print("  Median fill notional here is small; self-impact SHOULD be near")
    print("  zero. A large number is evidence about the instrument first.")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fills", default=str(DEFAULT_FILLS))
    ap.add_argument("--min-n", type=int, default=DEFAULT_MIN_N)
    ap.add_argument("--fee-bps", type=float, default=38.68,
                    help="measured aggregate fee rate to price impact against")
    ap.add_argument("--json", action="store_true")
    ns = ap.parse_args()
    rows = load(Path(ns.fills))
    if not rows:
        print("no usable fills at %s - NOT a clean result, the check could "
              "not run" % ns.fills)
        return 2
    res = estimate(rows, ns.min_n)
    if ns.json:
        print(json.dumps(res, indent=1))
    else:
        _render(res, ns.fee_bps)
    return 0


if __name__ == "__main__":
    sys.exit(main())
