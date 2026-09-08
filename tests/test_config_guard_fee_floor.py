"""The sub-floor fee FATAL must sit at VENUE TRUTH — measured, not asserted.

CORRECTED TWICE, AND THE SECOND CORRECTION IS THE POINT OF THIS FILE.

2026-09-05: this suite had pinned the floor at 40/80 and asserted 25/40 must
FATAL. It was rewritten against a ladder read from /0/public/AssetPairs
(25/40, 20/35 at $10k, 14/24 ...) and asserted "40/80 is not a row. Neither is
22/38."

2026-09-08: BOTH of those assertions were false about the account's venue.
The JSON endpoint had served Kraken's LEGACY ladder (it now serves no fee
arrays at all); the venue's fee page — and the operator's 2026-08-29 app
screenshot — carry the current "Cross-platform Fee Tiers": Tier 1 40/80 at
$0, Tier 2 30/60 at $2.5K, Tier 3 22/38 at $10K, Tier 4 20/35 at $25K, ...
0/5 at $500M; a tier is granted by the best of 30-day volume OR assets on
platform. So the 09-05 pins defended a stale ladder exactly the way the
08-29 pins had defended an invented row, and cut #10's E1 "fee correction"
(22/38 → 20/35) was booked on this suite's word. A belief about an external
system written into a constant and pinned by a test defends the error, not
the property — twice now, in the same file.

WHAT THE FLOOR MEANS, restated so it cannot drift again: no spot account pays
LESS than the zero-volume row unless it has earned a discount, which is
exactly what `pretrade.allow_sub_floor_fees` declares. That is the property.
The NUMBER is derived from core/venue_fees, which is diffed against the live
PAGE — the source the venue keeps current — by scripts/fee_drift_report.py.

These pins assert the floor AGAINST THE SCHEDULE, never against a literal
repeated here — except where a literal is the defect being pinned OUT.
"""
import pytest

from core.config_guard import (KRAKEN_SPOT_FLOOR_MAKER_BPS,
                               KRAKEN_SPOT_FLOOR_TAKER_BPS, validate)
from core.venue_fees import (KRAKEN_SPOT_AOP_USD, KRAKEN_SPOT_SCHEDULE,
                             binding_row, fetch_live_schedule,
                             fetch_page_schedule, is_a_published_row,
                             parse_fee_page, worst_row)

_FLOOR_M, _FLOOR_T = worst_row()


def _fatal_msgs(cfg):
    out = []
    for f in validate(cfg):
        sev = f[0] if isinstance(f, (tuple, list)) else getattr(f, "severity", "")
        msg = f[1] if isinstance(f, (tuple, list)) else str(f)
        if str(sev).upper() == "FATAL":
            out.append(str(msg))
    return out


def _has_floor_fatal(cfg):
    return any("floor" in m.lower() or "below kraken" in m.lower()
               for m in _fatal_msgs(cfg))


def _cfg(maker, taker, *, dry_run=False, allow_low=False):
    return {
        "system": {"dry_run": dry_run},
        "pretrade": {"maker_fee_bps": maker, "taker_fee_bps": taker,
                     "allow_sub_floor_fees": allow_low},
        "order_manager": {"maker_fee_bps": maker, "taker_fee_bps": taker},
    }


# --------------------------------------------------------- the floor itself
def test_floor_is_the_venue_zero_volume_row():
    """The constant must BE the schedule's worst row, not a literal."""
    assert (KRAKEN_SPOT_FLOOR_MAKER_BPS,
            KRAKEN_SPOT_FLOOR_TAKER_BPS) == worst_row()
    assert (KRAKEN_SPOT_FLOOR_MAKER_BPS,
            KRAKEN_SPOT_FLOOR_TAKER_BPS) == (KRAKEN_SPOT_SCHEDULE[0][1],
                                             KRAKEN_SPOT_SCHEDULE[0][2])


def test_the_rows_the_venue_publishes_and_the_ladders_that_must_stay_dead():
    """THE REGRESSION PIN, inverted from its 09-05 form. 40/80 IS Tier 1 and
    22/38 IS Tier 3 of the venue's current ladder (page 2026-09-08, app
    screenshot 2026-08-29). The LEGACY API ladder (25/40, 20/35-at-$10k,
    14/24) and the struck 16/26 must never again read as venue tiers."""
    assert is_a_published_row(KRAKEN_SPOT_FLOOR_MAKER_BPS,
                              KRAKEN_SPOT_FLOOR_TAKER_BPS)
    assert is_a_published_row(40.0, 80.0), "Tier 1 is 40/80"
    assert is_a_published_row(22.0, 38.0), "Tier 3 is 22/38 (cut #9 was right)"
    assert is_a_published_row(20.0, 35.0), "Tier 4 is 20/35"
    assert not is_a_published_row(25.0, 40.0), "legacy API ladder bottom row"
    assert not is_a_published_row(14.0, 24.0), "legacy API ladder $50k row"
    assert not is_a_published_row(16.0, 26.0), "the struck 2026-08-07 schedule"


def test_the_schedule_is_a_ladder_with_aligned_aop():
    vols = [r[0] for r in KRAKEN_SPOT_SCHEDULE]
    assert vols == sorted(vols) and vols[0] == 0.0 and len(set(vols)) == len(vols)
    assert len(KRAKEN_SPOT_AOP_USD) == len(KRAKEN_SPOT_SCHEDULE)
    assert KRAKEN_SPOT_AOP_USD[:2] == (None, None) and KRAKEN_SPOT_AOP_USD[2] == 20_000.0
    for (_v, m, t) in KRAKEN_SPOT_SCHEDULE:
        assert t >= m and t > 0


# ------------------------------------------------------------- the behaviour
def test_the_zero_volume_row_passes_exactly_at_the_floor():
    assert not _has_floor_fatal(_cfg(_FLOOR_M, _FLOOR_T))


@pytest.mark.parametrize("maker,taker", [(0.0, 0.0), (5.0, 10.0),
                                         (12.0, 25.0), (20.0, 35.0),
                                         (22.0, 38.0), (25.0, 40.0),
                                         (39.9, 79.9)])
def test_genuinely_sub_floor_fees_fatal_in_live(maker, taker):
    """Everything strictly below the zero-volume row trips the guard unless
    a discount is declared - including real discount tiers, which is correct:
    claiming one without declaring it is what the flag is for."""
    assert maker < _FLOOR_M or taker < _FLOOR_T, "fixture is not sub-floor"
    assert _has_floor_fatal(_cfg(maker, taker))


def test_fees_above_the_floor_do_not_fatal():
    """ANTI-RUBBER-STAMP: the guard must be able to stay silent."""
    assert not _has_floor_fatal(_cfg(45.0, 90.0))
    assert not _has_floor_fatal(_cfg(100.0, 200.0))


def test_deleted_fee_keys_fall_back_and_are_judged_on_the_fallback():
    cfg = {"system": {"dry_run": False}, "pretrade": {}, "order_manager": {}}
    assert _fatal_msgs(cfg), "a config with no fee keys at all produced no FATAL"


def test_allow_sub_floor_escape_still_works():
    """A genuine tier discount can opt out. The shipped config (20/35, Tier 4)
    and cut #9's 22/38 (Tier 3) both rely on it."""
    assert not _has_floor_fatal(_cfg(20.0, 35.0, allow_low=True))
    assert not _has_floor_fatal(_cfg(22.0, 38.0, allow_low=True))


# ---------------------------------------------------- the anti-rot mechanism
def test_reference_schedule_still_matches_the_live_fee_page():
    """The table cannot confirm itself. When a network is available, diff it
    against the venue's PAGE; SKIP - never silently pass - when it is not."""
    live = fetch_page_schedule()
    if live is None:
        pytest.skip("fee page unreachable/unparseable - this pin establishes nothing here")
    assert tuple(live) == tuple(KRAKEN_SPOT_SCHEDULE), (
        "Kraken's published schedule has MOVED. Update "
        "core/venue_fees.KRAKEN_SPOT_SCHEDULE (+ AoP) and re-stamp "
        "SCHEDULE_READ_UTC; then re-check the booked fee against it.")


def test_the_json_endpoint_is_not_believed_over_the_page():
    """AssetPairs served the LEGACY ladder until at least 2026-09-05 and no
    arrays at all by 2026-09-08. If it ever serves arrays again they must
    match the page-derived table, or the drift report must say DIFFERS -
    they must never silently become the reference again."""
    live = fetch_live_schedule("ETH/USD")
    if live is None:
        pytest.skip("AssetPairs publishes no fee arrays (measured 2026-09-08) or is unreachable")
    assert tuple(live) == tuple(KRAKEN_SPOT_SCHEDULE), (
        "the JSON endpoint disagrees with the page-derived table - resolve "
        "which source the venue keeps current before booking anything")


def test_page_parser_takes_the_spot_crypto_table_not_its_neighbours():
    """PLANTED PAGE. Three ladders that all start at $0+: stablecoin first,
    then spot crypto (captioned), then the maker-rebate table. The parser must
    return exactly the captioned one, in either table order."""
    spot = ("Tier 1 $0+ N/A 0.40 % 0.80 % Tier 2 $2.5K+ N/A 0.30 % 0.60 % "
            "Tier 3 $10K+ 20k 0.22 % 0.38 % Tier 4 $25K+ 50k 0.20 % 0.35 % "
            "Tier 5 $50K+ 100k 0.15 % 0.30 % Tier 12 $10M+ 10m 0.0 % 0.10 % "
            "Pro 5 $500M+ 100m 0.0 % 0.05 % ")
    rebate = ("Tier 1 $0+ N/A 0.38 % 0.80 % Tier 2 $2.5K+ N/A 0.28 % 0.60 % "
              "Tier 3 $10K+ 20k 0.20 % 0.38 % Tier 4 $25K+ 50k 0.18 % 0.35 % "
              "Tier 5 $50K+ 100k 0.13 % 0.30 % ")
    stable = "30-Day Volume (USD) Maker Taker $0 + 0.20% 0.20% $50,000 + 0.16% 0.16% "
    caption = "Spot Crypto Kraken uses a maker-taker fee tier system "
    page = "<html><body>" + stable + spot + caption + "Spot Maker Rebate " + rebate + "</body></html>"
    rows, aop = parse_fee_page(page)
    assert rows[:4] == ((0.0, 40.0, 80.0), (2_500.0, 30.0, 60.0),
                        (10_000.0, 22.0, 38.0), (25_000.0, 20.0, 35.0))
    assert rows[-1] == (500_000_000.0, 0.0, 5.0) and len(rows) == 7
    assert aop[:4] == (None, None, 20_000.0, 50_000.0) and aop[-1] == 100_000_000.0
    # rebate table FIRST, spot table second: still the captioned one
    page2 = "<p>" + rebate + "</p>" + spot + caption + stable
    rows2, _ = parse_fee_page(page2)
    assert rows2 == rows
    assert parse_fee_page(rebate + "no caption here") is None
    assert parse_fee_page("") is None


def test_binding_row_needs_a_volume_and_refuses_to_guess():
    """A tier cannot be resolved without a 30-day volume - not even with AoP,
    because AoP alone only bounds the discount from below."""
    assert binding_row(None) is None
    assert binding_row(-1) is None
    assert binding_row(None, aop_usd=50_000) is None
    assert binding_row(0) == (40.0, 80.0)
    assert binding_row(2_499) == (40.0, 80.0)
    assert binding_row(2_500) == (30.0, 60.0)
    assert binding_row(9_999) == (30.0, 60.0)
    assert binding_row(10_000) == (22.0, 38.0)      # boundary is inclusive
    assert binding_row(17_482) == (22.0, 38.0)      # the 2026-08-29 account
    assert binding_row(24_999) == (22.0, 38.0)
    assert binding_row(25_000) == (20.0, 35.0)      # what cut #10 booked


def test_assets_on_platform_improve_the_row_but_never_worsen_it():
    assert binding_row(17_482, aop_usd=50_000) == (20.0, 35.0)
    assert binding_row(0, aop_usd=20_000) == (22.0, 38.0)
    assert binding_row(0, aop_usd=19_999) == (40.0, 80.0)
    assert binding_row(30_000, aop_usd=1_000) == (20.0, 35.0)   # volume wins
    assert binding_row(30_000, aop_usd=None) == (20.0, 35.0)
    assert binding_row(30_000, aop_usd="junk") == (20.0, 35.0)


def test_the_not_a_row_warning_names_the_current_ladder_not_a_literal():
    """config_guard's WARN used to print '(rows: 25/40, 20/35, 14/24, 12/22,
    ...)' as a string literal - the legacy ladder, outliving the table it
    described. It must now be derived from the schedule."""
    cfg = _cfg(23.0, 39.0, allow_low=True)          # not a row on any ladder
    warns = [str(f[1]) for f in validate(cfg) if str(f[0]).upper() == "WARN"
             and "published Kraken tier" in str(f[1])]
    assert warns, "the not-a-row WARN did not fire on 23/39"
    assert "40/80, 30/60, 22/38, 20/35" in warns[0], warns[0]
    assert "25/40" not in warns[0] and "14/24" not in warns[0]


def test_drift_report_takes_aop_and_reproduces_the_operators_reading():
    """The venue grants the better of the volume tier and the AoP tier. The
    report must (a) let AoP lift the row and (b) reproduce the operator's
    2026-09-08 app reading: Tier 5 = 15/30 on $69,652.65 with AoP $822.24,
    and say the booked 20/35 OVER-states."""
    import subprocess
    import sys
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    def run(*args):
        r = subprocess.run([sys.executable, str(root / "scripts" / "fee_drift_report.py"),
                            "--offline", *args], capture_output=True, text=True,
                           cwd=str(root), timeout=120)
        return r.stdout
    out = run("--volume-30d", "0", "--aop-usd", "20000")
    assert "maker 22 / taker 38" in out, out            # AoP lifts $0 volume to Tier 3
    out = run("--volume-30d", "69652.65", "--aop-usd", "822.24")
    assert "maker 15 / taker 30" in out and "AoP $822" in out, out
    out_lb = run("--volume-30d", "69652.65")
    assert "LOWER BOUND" in out_lb, out_lb


# ------------------------------- the escape hatch had no floor of its own
def test_allow_sub_floor_is_not_a_licence_for_ZERO_fees():
    assert _has_floor_fatal(_cfg(0.0, 0.0, allow_low=True)), \
        "zero fees validated clean under the discount flag"
    assert _has_floor_fatal(_cfg(1.0, 1.0, allow_low=True))
    assert _has_floor_fatal(_cfg(0.0, 4.9, allow_low=True)), \
        "a taker below the venue's cheapest published tier is not a discount"


def test_a_genuine_top_tier_discount_still_passes():
    best_m, best_t = __import__("core.venue_fees", fromlist=["x"]).best_possible_row()
    assert not _has_floor_fatal(_cfg(best_m, best_t, allow_low=True)), \
        f"the venue's own best tier {best_m}/{best_t} was rejected as sub-floor"
    assert not _has_floor_fatal(_cfg(20.0, 35.0, allow_low=True)), \
        "the SHIPPED config must keep validating - this change is SAFE only " \
        "because it does not move the live posture"


def test_absent_fee_keys_are_a_FATAL_not_a_silent_default():
    import copy
    import json as _json
    from pathlib import Path as _P
    root = _P(__file__).resolve().parents[1]
    cfg = copy.deepcopy(_json.loads(
        (root / "config.json").read_text(encoding="utf-8")))
    baseline = [m for m in _fatal_msgs(cfg) if "fee" in m.lower()]
    assert not baseline, (
        f"the SHIPPED config already has a fee FATAL - this fixture cannot "
        f"isolate the absent-key case: {baseline}")
    for section in ("pretrade", "order_manager"):
        for key in ("maker_fee_bps", "taker_fee_bps"):
            cfg[section].pop(key, None)
    fee_fatals = [m for m in _fatal_msgs(cfg) if "fee" in m.lower()]
    assert fee_fatals, (
        "the fee keys were removed from BOTH pretrade and order_manager and "
        "no fee FATAL fired - four consumers then substitute four different "
        "fallback schedules, silently")
