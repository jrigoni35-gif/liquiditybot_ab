"""Red-first xfail PINS for two known FAIL-OPEN findings.

Both are COHORT-RESETTING to fix (they alter entry sizing / staleness
geometry) and therefore wait on operator adjudication under the era-5
moratorium - see docs/HANDOFF OPEN DOCKET (SWEEP-1 margin-health fails
open; the watchdog missing-book fail-open in the SWEEP family).

These tests assert the DESIRED live fail-closed behavior. They FAIL against
the code as shipped today, so they are marked strict xfail: the pin stays
green now and turns into a hard signal the day the fix lands (XPASS under
strict -> the fixer must delete the marker). They add NO behavior and pin
NO current contract - they only make the gap visible with its test waiting.
"""

import pytest

from core.watchdog import Watchdog
from risk.leverage import LeverageGovernor


@pytest.mark.xfail(
    strict=True,
    reason="FAIL-OPEN, adjudication-pending (docs/HANDOFF docket SWEEP-1): "
    "with use_margin=True a 0.0 margin_level_pct (a missing/failed live read) "
    "takes the `elif margin_level_pct > 0` no-constraint path in "
    "risk/leverage.py:allowed_leverage, so leverage passes UNCONSTRAINED "
    "instead of failing closed. The real fix must distinguish dry-run-unknown "
    "(the fetch never runs in dry_run, so margin is always 0.0 - a naive "
    "0.0->block would cap ALL dry-run leverage) from a live fetch that failed. "
    "Cohort-resetting (alters entry sizing); do not fix mid-era.")
def test_zero_margin_read_fails_closed_in_live():
    gov = LeverageGovernor({"use_margin": True, "region_max_leverage": 10.0,
                            "target_vol_annual_pct": 35.0})
    # low realized vol -> the vol-target ladder wants >1x; the margin read is
    # 0.0 (missing/failed). DESIRED live behavior: an unknown/failed margin
    # read must NOT permit leverage above 1x. Today the code returns ~7x
    # unconstrained, so this assertion fails -> the pin xfails.
    lev, _reasons = gov.allowed_leverage(sigma_annual_pct=5.0, regime_cap=10.0,
                                         margin_level_pct=0.0)
    assert lev <= 1.0


# FIXED at cut #10 (2026-09-06, era-7 boundary, operator-adjudicated as B1).
# This was a strict xfail from its creation until that boundary: the pin was a
# working detector of a fail-open the moratorium forbade fixing mid-era. The
# marker comes off in the SAME commit as the fix, exactly as the docket said
# it must - a strict xfail that starts passing reds the whole suite.
def test_never_delivered_book_reads_stale():
    wd = Watchdog({"stale_warn_sec": 30.0, "stale_critical_sec": 120.0})
    # BTC never delivered a book (empty book_ts). DESIRED: it is STALE, not
    # fresh. Today get("BTC", now) == now -> age 0 -> not stale, so this
    # assertion fails -> the pin xfails.
    st = wd.evaluate(now=1_000_000.0, book_ts={}, assets=["BTC"],
                     kraken_mids={"BTC": 100.0}, fair_values={"BTC": 100.0},
                     equity=1000.0, open_positions=1, dry_run=False)
    assert "BTC" in st.stale_assets
