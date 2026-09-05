"""Does what we BOOK agree with what the venue CHARGES? Report-only.

THE RECURRENCE THIS CLOSES. The booked fee has been wrong three times in three
weeks, and each correction was itself a struck literal that set up the next
error:

    original   25/40 bps   understated vs the venue
    cut #8     40/80 bps   assumed a zero-volume account; ~2x over-stated
    cut #9     22/38 bps   from an account screenshot - and not a published
                           row at all (the venue's rows are 25/40, 20/35,
                           14/24, 12/22; 22/38 matches none of them)

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
    fetch_live_schedule, is_a_published_row)


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
        row = binding_row(args.volume_30d)
        if row is None:
            print(f"\n  binding tier      : UNKNOWN (bad volume "
                  f"{args.volume_30d!r})")
        else:
            m, t = row
            print(f"\n  binding tier at ${args.volume_30d:,.0f}/30d"
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
        live = fetch_live_schedule(args.pair)
        if live is None:
            print("\n  live venue        : UNREACHABLE")
            print("    Not a clean result. The reference table above is what "
                  "the venue published when last read; it cannot confirm "
                  "itself, so this run establishes nothing about drift "
                  "between the table and reality.")
        else:
            same = tuple(live) == tuple(KRAKEN_SPOT_SCHEDULE)
            print(f"\n  live venue        : {'AGREES' if same else 'DIFFERS'} "
                  f"with the reference table ({args.pair})")
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
