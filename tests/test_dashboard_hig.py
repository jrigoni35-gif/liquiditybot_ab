"""HIG conformance pins for the shipped Grafana boards.

These assert the OUTPUT properties the 2026-08-01 design pass established,
not the implementation that produces them. If _hig_pass is ever refactored,
moved, or replaced, these still hold - and if someone hand-edits a board and
regenerates without it, they go red.

Every number here was measured before it was asserted. That mattered: a first
audit claimed "65 panels missing units", which was wrong by roughly 10x. Most
unitless panels on these boards are integer counts, where a unit makes them
WORSE (Grafana's "short" renders 1000 as "1 K"), or ratios like the Kelly
multiplier, which have no unit by definition. The real defect set was seven
panels. Asserting the inflated number would have pinned a fiction.
"""
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BOARDS = ROOT / "docs" / "grafana"

# Panel types that render a number the operator reads as a magnitude.
NUMERIC = {"stat", "gauge", "bargauge", "timeseries", "barchart", "histogram"}
# The complete sanctioned color vocabulary: Apple's dark-mode system colors
# plus Grafana's theme-following "text". Anything else is drift.
#
# gray/purple are here because they ARE Apple system colors and were already
# correct on the boards - an earlier draft of this test omitted them and so
# flagged correct panels. The one genuine outlier the test did catch was a
# hand-picked #2596AB teal (5.37:1 on the dark canvas); it is now #40CBE0
# from the palette proper, at 9.65:1.
APPLE = {
    "#30D158",   # systemGreen   - nominal / profit
    "#FF453A",   # systemRed     - loss / unsafe
    "#FFD60A",   # systemYellow  - watch
    "#0A84FF",   # systemBlue    - neutral info
    "#FF9F0A",   # systemOrange  - warn
    "#5E5CE6",   # systemIndigo  - model domain
    "#BF5AF2",   # systemPurple  - categorical
    "#40CBE0",   # systemTeal    - categorical
    "#8E8E93",   # systemGray    - inactive / off
    "text",      # follows the Grafana theme
}


def _load(name):
    d = json.loads((BOARDS / name).read_text(encoding="utf-8"))
    return d.get("dashboard", d)


def _walk(panels, row=None):
    for p in panels or []:
        if p.get("type") == "row":
            yield from _walk(p.get("panels"), p.get("title"))
        else:
            yield row, p


def _all_panels():
    for path in sorted(BOARDS.glob("liquiditybot_*.json")):
        for row, p in _walk(_load(path.name).get("panels")):
            yield path.stem.replace("liquiditybot_", ""), row, p


BOARD_FILES = sorted(p.name for p in BOARDS.glob("liquiditybot_*.json"))


@pytest.mark.parametrize("name", BOARD_FILES)
def test_board_parses_and_has_panels(name):
    d = _load(name)
    assert d.get("panels"), f"{name} has no panels"
    assert d.get("uid"), f"{name} has no uid"


def test_no_dead_thresholds():
    """Threshold steps with no explicit color.mode may silently never paint.

    Grafana's default color mode varies by panel type, so a stat declaring
    green/yellow/red steps while leaving color.mode unset is relying on a
    default that is not guaranteed. Being explicit costs one key.
    """
    bad = []
    for board, _row, p in _all_panels():
        if p.get("type") not in ("stat", "gauge", "bargauge"):
            continue
        fc = (p.get("fieldConfig") or {}).get("defaults") or {}
        steps = (fc.get("thresholds") or {}).get("steps") or []
        if len(steps) > 1 and (fc.get("color") or {}).get("mode") is None:
            bad.append(f"{board}:{p.get('title')}")
    assert not bad, "threshold steps declared but color.mode unset: " + \
        ", ".join(bad)


def test_no_units_smuggled_into_titles():
    """A unit in the title cannot travel with the value.

    "Unlock ETA (days)" renders the number bare in tooltips, legends, CSV
    exports and alert notifications - every context that reads fieldConfig
    rather than the panel title. The unit belongs on the value.
    """
    pat = re.compile(r"\((?:days?|bps|usd|\$|ms|sec)\b[^)]*\)", re.I)
    bad = [f"{b}:{p.get('title')}" for b, _r, p in _all_panels()
           if p.get("type") in NUMERIC and pat.search(p.get("title") or "")]
    assert not bad, "unit belongs on the value, not the title: " + \
        ", ".join(bad)


def test_percentunit_shares_are_not_over_precise():
    """percentunit multiplies by 100, so fraction-era precision is too fine.

    A share stored as 0.250 and rendered with decimals=3 reads "25.000%".
    One decimal place is the honest resolution for a proportion here.
    """
    bad = []
    for board, _row, p in _all_panels():
        fc = (p.get("fieldConfig") or {}).get("defaults") or {}
        if fc.get("unit") == "percentunit" and (fc.get("decimals") or 0) > 2:
            bad.append(f"{board}:{p.get('title')}={fc.get('decimals')}")
    assert not bad, "percentunit over-precise: " + ", ".join(bad)


def test_percent_scale_matches_the_query():
    """`percent` vs `percentunit` is a 100x display error, silently.

    Grafana's "percent" treats the value as ALREADY a percentage; only
    "percentunit" multiplies a fraction by 100. So a panel carrying unit
    "percent" must either scale in its query (`*100`) or plot something
    genuinely already in percent units.

    A max at or below 1 proves the field is a fraction. That combination -
    unit "percent", no `*100`, max <= 1 - is how the execution board's
    calibration gauge printed a real 0.05 gap as "0.050%" while the SAME
    metric read "5.0%" on the command board. The needle sat correctly; only
    the number beside it lied, which is the harder version to notice.
    """
    bad = []
    for board, _row, p in _all_panels():
        fc = (p.get("fieldConfig") or {}).get("defaults") or {}
        if fc.get("unit") != "percent":
            continue
        mx = fc.get("max")
        if mx is None or mx > 1:
            continue
        exprs = " ".join(t.get("expr") or "" for t in p.get("targets") or [])
        if "*100" not in exprs.replace(" ", ""):
            bad.append(f"{board}:{p.get('title')} (max={mx})")
    assert not bad, ("unit=percent on an unscaled fraction - use "
                     "percentunit: " + ", ".join(bad))


def test_timeseries_legends_are_uniform():
    """One legend shape board-wide.

    The table legend carries exact last/min/max beside the trend, which is
    the point of plotting a trend you intend to act on. A list legend shows
    names only, so the operator reads a shape and then hunts for the number.
    """
    bad = []
    for board, _row, p in _all_panels():
        if p.get("type") != "timeseries":
            continue
        lg = (p.get("options") or {}).get("legend") or {}
        if lg.get("displayMode") != "table" or not lg.get("calcs"):
            bad.append(f"{board}:{p.get('title')}")
    assert not bad, "timeseries legend not a table with calcs: " + \
        ", ".join(bad)


def test_color_vocabulary_is_apple_system_colors():
    """No color outside the sanctioned palette reaches the shipped JSON.

    _apple_palette remaps Grafana's named colors; this pins that nothing
    slipped past it. A stray "#73BF69" beside "#30D158" is invisible in
    review and obvious on screen.
    """
    bad = set()
    for board, _row, p in _all_panels():
        fc = (p.get("fieldConfig") or {}).get("defaults") or {}
        for st in ((fc.get("thresholds") or {}).get("steps") or []):
            c = st.get("color")
            if isinstance(c, str) and c not in APPLE:
                bad.add(f"{board}:{p.get('title')}:{c}")
        for ov in (p.get("fieldConfig") or {}).get("overrides") or []:
            for prop in ov.get("properties") or []:
                v = prop.get("value")
                if isinstance(v, dict) and isinstance(v.get("fixedColor"),
                                                      str) \
                        and v["fixedColor"] not in APPLE:
                    bad.add(f"{board}:{p.get('title')}:{v['fixedColor']}")
    assert not bad, "color outside the Apple palette: " + ", ".join(
        sorted(bad))


def test_count_axes_anchor_at_zero():
    """An axis autoscaled to [270, 274] turns noise into a mountain range."""
    pat = re.compile(r"label|row|count|position|trade|token|admission"
                     r"|candidate", re.I)
    bad = []
    for board, _row, p in _all_panels():
        if p.get("type") != "timeseries":
            continue
        fc = (p.get("fieldConfig") or {}).get("defaults") or {}
        if pat.search(p.get("title") or "") and not fc.get("unit") \
                and fc.get("min") is None:
            bad.append(f"{board}:{p.get('title')}")
    assert not bad, "count axis not anchored at zero: " + ", ".join(bad)
