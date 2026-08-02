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


def _row_members(board, title_substr):
    """Panels belonging to a row, for BOTH row shapes Grafana emits.

    A COLLAPSED row carries its members nested under "panels". An EXPANDED
    row is only a header - its members are top-level siblings that follow it
    until the next row. Reading just the nested list therefore returns [] for
    every expanded row, which makes a membership assertion pass vacuously.
    That is exactly how an earlier draft of this file reported green on a row
    it had never actually inspected.
    """
    tops = _load(board).get("panels") or []
    for i, p in enumerate(tops):
        if p.get("type") != "row" or title_substr not in (p.get("title") or ""):
            continue
        if p.get("panels"):
            return list(p["panels"])
        out = []
        for q in tops[i + 1:]:
            if q.get("type") == "row":
                break
            out.append(q)
        return out
    raise AssertionError(f"no row matching {title_substr!r} in {board}")


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


def test_outcome_statistics_are_on_the_command_board():
    """The bottom line must be a number, not an inference from a curve.

    Added 2026-08-02 after an audit of what the bot EMITS versus what any
    board SHOWS: 29 metrics were pushed to Grafana on every tick and
    displayed nowhere. Among them were cumulative net P&L, monthly goal
    attainment, the worst-ever loss streak, and payoff ratio - so "is it
    losing money" could only be answered by reading the shape of the equity
    curve, and "am I on track" not at all.

    These four are pinned by name because they are the ones the operator
    opens the board to read. A refactor that quietly drops one puts the
    board back in the state where the answer had to be inferred.
    """
    want = {
        "liquiditybot_perf_net_usd": "cumulative bottom line",
        "liquiditybot_goal_attainment_pct": "progress toward the goal",
        "liquiditybot_perf_payoff_ratio": "the other half of win rate",
        "liquiditybot_perf_max_loss_streak": "what to judge the current "
                                             "streak against",
    }
    d = _load("liquiditybot_command.json")
    exprs = " ".join(
        t.get("expr") or ""
        for _r, p in _walk(d.get("panels"))
        for t in p.get("targets") or [])
    missing = {m: why for m, why in want.items() if m not in exprs}
    assert not missing, f"command board lost an outcome statistic: {missing}"


def test_learning_brain_reads_as_a_funnel():
    """The section's value is its ORDER, so the order is pinned.

    Redesigned 2026-08-02 from fourteen identically-sized tiles in arbitrary
    sequence. The worst symptom: "Live labels" sat eight tiles from "Clean
    live labels" — the same funnel stage, one the filtered version of the
    other — so the attrition between them, the most diagnostic number in the
    section, had to be computed by eye across half a screen.

    Reading order now encodes the diagnosis: supply, corpus, quality,
    governor. A reader stops at the first red stage, because a model-quality
    problem is not fixable while the supply above it is starved. Scrambling
    the order silently removes that, and nothing else in the suite notices.
    """
    members = _row_members("liquiditybot_command.json", "LEARNING BRAIN")
    titles = [p.get("title") or "" for p in members]
    pos = {t: i for i, t in enumerate(titles)}
    for a, b in (("Live labels", "Clean live labels"),
                 ("Clean live labels", "Label uniqueness"),
                 ("Label uniqueness", "Calibration gap"),
                 ("Calibration gap", "Model in use")):
        assert a in pos and b in pos, f"missing {a!r} or {b!r}"
        assert pos[a] < pos[b], f"funnel order broken: {a!r} after {b!r}"
    # Live/Clean must be adjacent — the attrition is the reading.
    assert pos["Clean live labels"] - pos["Live labels"] == 1, \
        "Live labels and Clean live labels must sit side by side"
    # Every band exactly 24 wide: a short band is the ragged edge the
    # redesign removed (14 tiles at w=4 wrapped 6/6/2).
    bands = {}
    for p in members:
        gp = p.get("gridPos") or {}
        bands.setdefault(gp.get("y"), []).append(gp.get("w") or 0)
    bad = {y: sum(w) for y, w in bands.items() if sum(w) != 24}
    assert not bad, f"LEARNING BRAIN bands not 24 wide: {bad}"


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


def test_learning_trajectory_row_exists():
    """The structural fix: trend panels for the trajectory questions.

    Before 2026-08-01 the four boards carried 8 timeseries against 167 state
    panels. State tiles answer "is it healthy" well, and that is most of
    what these boards do. But "is it learning" is a trajectory question and
    a tile shows a number, never a direction - live_clean sat pinned at 0
    for thirteen days and the board could not distinguish that from a value
    that had merely touched 0 on the current scrape.
    """
    members = _row_members("liquiditybot_command.json",
                           "LEARNING TRAJECTORY")
    trends = [p for p in members if p.get("type") == "timeseries"]
    assert len(trends) >= 4, \
        f"trajectory row should carry >= 4 charts, has {len(trends)}"
    # The real invariant is that NO state tile sits in the trend row - a
    # single stat among the charts re-introduces exactly the ambiguity the
    # row exists to remove. The row does trail the board's 1x1 hidden
    # _injector() utility panel, which is neither a tile nor a chart, so
    # "everything here is a timeseries" would be the wrong assertion.
    tiles = [p.get("title") for p in members
             if p.get("type") in ("stat", "gauge", "bargauge")]
    assert not tiles, f"state tiles in the trend row: {tiles}"


def test_trajectory_metrics_exist_in_exporter():
    """A panel querying a metric the bot never emits is worse than no panel.

    An absent metric renders an empty chart, which reads as "zero" rather
    than "absent" - precisely the confusion this row was added to remove.
    """
    members = _row_members("liquiditybot_command.json",
                           "LEARNING TRAJECTORY")
    metrics = set()
    for p in members:
        for t in p.get("targets") or []:
            metrics.update(re.findall(r"liquiditybot_[a-z0-9_]+",
                                      t.get("expr") or ""))
    src = "\n".join(
        f.read_text(encoding="utf-8", errors="ignore")
        for f in ROOT.rglob("*.py")
        if ".venv" not in str(f) and "outputs" not in str(f))
    missing = sorted(m for m in metrics if m not in src)
    assert not missing, f"trajectory row queries unexported metrics: {missing}"


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
