"""Does what we BOOK agree with what the venue CHARGES? Report-only.

THE RECURRENCE THIS CLOSES - AND COMMITTED ONCE ITSELF. The booked fee has
been wrong four times in four weeks, and each correction was itself a struck
literal that set up the next error:

    original   25/40 bps   the legacy API ladder's bottom row
    cut #8     40/80 bps   assumed a zero-volume account (~2x the real tier;
                           it IS Tier 1 of the current ladder)
    cut #9     22/38 bps   from the operator's app screenshot - and RIGHT:
                           Tier 3 of the current ladder
    cut #10    20/35 bps   booked on THIS script's 2026-09-06 verdict that
                           22/38 "is not a published row" and 20/35 binds at
                           $17,482 - both false: the reference table had been
                           read from a JSON endpoint still serving the LEGACY
                           ladder (it serves none by 2026-09-08). 20/35 is
                           Tier 4 (>= $25,000 30-day OR >= $50k assets on
                           platform). See core/venue_fees.py.

The live authority is now the venue's fee PAGE (fetch_page_schedule); the
JSON endpoint is a second route that must agree or be reported as DIFFERS.

Nobody was careless. The defect is structural: a fee lived in the source as a
constant with no relationship to the venue that charges it, so nothing could
notice when the two diverged. This script is the thing that notices.

It CHANGES NOTHING. Fee booking is cohort-resetting and belongs to an operator
adjudication; this only says out loud whether config, the local reference
table and the live venue agree, and exits non-zero when they do not - so it
can be run from a scheduled task and be believed.

    python scripts/fee_drift_report.py            # live venue check
    python scripts/fee_drift_report.py --offline  # config vs local table only

EXIT: 0 agreement (or offline-and-consistent) · 1 drift found · 2 could not
establish (venue unreachable). 1 and 2 are DIFFERENT: "the fees disagree" and
"the scan did not run" are the same observation until separated, and this
script refuses to conflate them.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.venue_fees import (  # noqa: E402
    KRAKEN_SPOT_SCHEDULE, SCHEDULE_READ_UTC, binding_row,
    fetch_live_schedule, fetch_page_schedule, is_a_published_row)


def _cfg() -> dict:
    with open(ROOT / "config.json", encoding="utf-8") as fh:
        return json.load(fh)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true",
                    help="skip the live venue read")
    ap.add_argument("--volume-30d", type=float, default=None,
                    help="30-day USD volume; without it the binding tier "
                         "CANNOT be resolved and is reported UNKNOWN")
    ap.add_argument("--aop-usd", type=float, default=None,
                    help="assets on platform (USD); the venue grants the "
                         "better of the volume tier and the AoP tier. "
                         "Optional: without it the volume tier is a LOWER "
                         "BOUND on the discount")
    ap.add_argument("--pair", default="ETH/USD")
    args = ap.parse_args()

    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    cfg = _cfg()
    pt = cfg.get("pretrade") or {}
    booked_m = float(pt.get("maker_fee_bps", float("nan")))
    booked_t = float(pt.get("taker_fee_bps", float("nan")))

    print("=" * 68)
    print(f"FEE DRIFT REPORT — read {now}")
    print("=" * 68)
    print(f"\n  config books      : maker {booked_m:g} / taker {booked_t:g} bps"
          f"   (round trip {booked_m + booked_t:g} bps)")

    drift = []

    # ---- 1. is the booked pair even a row the venue publishes? -----------
    published = is_a_published_row(booked_m, booked_t)
    print(f"  is a published row: {'YES' if published else 'NO'}")
    if not published:
        drift.append(
            f"config books {booked_m:g}/{booked_t:g}, which is NOT a row in "
            f"the venue's schedule. A number that matches no tier came from "
            f"somewhere other than the schedule — a screenshot, an average, "
            f"or an older tier. Every historical fee error would fail here.")

    # ---- 2. local reference table ----------------------------------------
    print(f"\n  reference schedule (read {SCHEDULE_READ_UTC}):")
    for vol, m, t in KRAKEN_SPOT_SCHEDULE:
        print(f"    >= ${vol:>10,.0f}   maker {m:>5g}   taker {t:>5g} bps")

    # ---- 3. which tier actually binds? -----------------------------------
    if args.volume_30d is None:
        print("\n  binding tier      : UNKNOWN — no --volume-30d given.")
        print("    A tier cannot be resolved without a 30-day volume, and "
              "guessing one is how this went wrong before. The account's "
              "volume is a PRIVATE TradeVolume read (FEE-3 on the docket); "
              "until that is armed, pass the figure explicitly to compare.")
    else:
        row = binding_row(args.volume_30d, aop_usd=args.aop_usd)
        if row is None:
            print(f"\n  binding tier      : UNKNOWN (bad volume "
                  f"{args.volume_30d!r})")
        else:
            m, t = row
            aop = (f" + AoP ${args.aop_usd:,.0f}" if args.aop_usd is not None
                   else " (AoP unknown: a LOWER BOUND on the discount)")
            print(f"\n  binding tier at ${args.volume_30d:,.0f}/30d{aop}"
                  f"   : maker {m:g} / taker {t:g} bps"
                  f"   (round trip {m + t:g} bps)")
            if abs(m - booked_m) > 1e-9 or abs(t - booked_t) > 1e-9:
                delta = (booked_m + booked_t) - (m + t)
                direction = "OVER" if delta > 0 else "UNDER"
                drift.append(
                    f"config books {booked_m:g}/{booked_t:g} but the binding "
                    f"tier is {m:g}/{t:g} — {direction}-stating the round "
                    f"trip by {abs(delta):g} bps "
                    f"({abs(delta) / (m + t) * 100:.1f}%).")

    # ---- 4. the live venue -----------------------------------------------
    if args.offline:
        print("\n  live venue        : SKIPPED (--offline)")
        live = None
    else:
        # Two routes. The PAGE is what the venue keeps current (the authority);
        # the JSON endpoint served the LEGACY ladder until at least 2026-09-05
        # and no arrays by 2026-09-08. Either agreeing with the table is
        # evidence; the two disagreeing with EACH OTHER is drift too.
        live = fetch_page_schedule()
        src = "fee page"
        api = fetch_live_schedule(args.pair)
        if api is not None:
            print(f"\n  JSON endpoint     : serves fee arrays again for {args.pair} "
                  f"({'AGREES' if tuple(api) == tuple(KRAKEN_SPOT_SCHEDULE) else 'DIFFERS'} "
                  f"with the reference table)")
            if tuple(api) != tuple(KRAKEN_SPOT_SCHEDULE):
                drift.append("the JSON endpoint's fee arrays differ from the "
                             "page-derived reference table - resolve which "
                             "source the venue keeps current before booking.")
        else:
            print("\n  JSON endpoint     : no fee arrays (as measured 2026-09-08) "
                  "- not an authority; the page is")
        if live is None:
            print(f"\n  live venue        : UNREACHABLE ({src})")
            print("    Not a clean result. The reference table above is what "
                  "the venue published when last read; it cannot confirm "
                  "itself, so this run establishes nothing about drift "
                  "between the table and reality.")
        else:
            same = tuple(live) == tuple(KRAKEN_SPOT_SCHEDULE)
            print(f"\n  live venue        : {'AGREES' if same else 'DIFFERS'} "
                  f"with the reference table ({src})")
            if not same:
                print("    live rows:")
                for vol, m, t in live:
                    print(f"      >= ${vol:>10,.0f}   maker {m:>5g}   "
                          f"taker {t:>5g} bps")
                drift.append(
                    "the venue's published schedule has MOVED since the "
                    "reference table was read. Update core/venue_fees."
                    "KRAKEN_SPOT_SCHEDULE and re-stamp SCHEDULE_READ_UTC.")

    # ---- verdict ----------------------------------------------------------
    print("\n" + "=" * 68)
    if drift:
        print("DRIFT FOUND")
        for d in drift:
            print(f"  * {d}")
        print("\n  Fee booking is COHORT-RESETTING. This report changes "
              "nothing; correcting the booked value is an operator "
              "adjudication and mints an execution-era boundary.")
        return 1
    if live is None and not args.offline:
        print("COULD NOT ESTABLISH — the venue was unreachable.")
        return 2
    print("NO DRIFT — config, the reference table and the venue agree.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
