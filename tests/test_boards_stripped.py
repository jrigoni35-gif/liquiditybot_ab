"""tests/test_boards_stripped.py — pins the STRIPPED board contract.

2026-08-15: every visualisation panel was deleted from the Grafana boards
before the reconfigured bot produced data, so no board could display a number
carried over from the retired geometry. The tests that pinned that deleted
content were deleted with it (git history holds them verbatim). That left a
hole: nothing pinned the *stripped* state itself, so a board could silently
regrow panels — or the glass injector could quietly vanish — and the battery
would stay green. "A green is only as big as its corpus." This module is that
corpus.

What it pins, and why each item is a FRAMEWORK invariant rather than deleted
content:

  * the three deep boards (execution / problem-solution / screening) hold
    EXACTLY ONE panel, the id-990 glass CSS injector, seated at gridPos y=0.
    This names no metric, query or tile — only the count and the skin.
  * the injector exists on EVERY board, is transparent, is 1x1, is the
    bottom-most panel, and carries the WHOLE of gen.GLASS_RULES inside its
    afterRender JS (asserted against the module constant, not a copy, so a
    rewritten stylesheet cannot pass by accident).
  * the board shell survives the strip: unique non-empty uid, schemaVersion
    39, non-empty title, and nav links whose targets are exactly the four
    board uids.
  * shipped JSON == what the generator produces right now (the repo's
    long-standing source-of-truth invariant; same idiom as
    tests/test_trading_dashboard.py::test_generator_matches_shipped_json).
  * the panel FACTORIES still build a board — proved by actually running
    _board() over a throwaway author, not by asserting callable(). A rebuild
    has to be possible on the day the boards come back.

DIVERGENCE, deliberate and flagged: the COMMAND board is no longer empty. It
is the LIQUIDITY BOARD — the at-a-glance read (hero money line, equity chart,
health + liveness group, positions table; ids 1..18 plus the injector), every
panel authored against a metric verified emitted by scripts/gc_pusher.py. So
the "exactly one panel" pin applies to the three deep boards; the command
board instead gets a regrowth pin that accepts EITHER the fully-stripped form
OR exactly the pinned inventory, and nothing else. Adding, removing, renaming,
retyping or REPOINTING a tile is a deliberate act and must edit
_COMMAND_HERO_PANELS below in the same commit — that edit is the review
record. Accepting the stripped form too is not laxity: it means re-stripping
the board cannot brick the deploy gate.

Every board file is read with encoding="utf-8" — the Windows cp1252 default
CRASHES on the ⌘/⚙/🔎 nav-link glyphs.
"""
import json
import re
from pathlib import Path

import pytest

import scripts.build_trading_dashboard as gen

ROOT = Path(__file__).resolve().parents[1]

COMMAND = "liquiditybot_command.json"
DEEP_BOARDS = ("liquiditybot_execution.json",
               "liquiditybot_problem_solution.json",
               "liquiditybot_screening.json")
ALL_BOARDS = (COMMAND,) + DEEP_BOARDS

INJ_TYPE = "marcusolsson-dynamictext-panel"

# The command board's authored inventory, as
# (id, title, type, sorted metrics) QUADRUPLES.
#
# Two failures of this pin, in order, both found by MUTATION rather than by
# reading it - the reason the metric tuple is in here at all:
#   1. It was an id SET. _id() assigns sequentially, so ANY 14 panels
#      satisfied `ids == range(1,15)`. A review repointed the "Equity" hero
#      at liquiditybot_savings and swapped a tile wholesale; GREEN both times.
#   2. Widened to (id, title, type) - the review's own recommendation - and
#      re-tested: STILL GREEN with "Equity" plotting liquiditybot_savings,
#      because repointing a query changes none of those three fields.
# A tile labelled "Equity" quietly plotting a different series is the exact
# plausible-looking lie this board must not be able to tell, so WHAT EACH
# PANEL QUERIES is pinned, not merely how many panels there are.
_COMMAND_HERO_PANELS = frozenset({
    (1, "Equity", "stat", ("liquiditybot_equity",)),
    (2, "Today", "stat", ("liquiditybot_daily_pnl",)),
    (3, "This week", "stat", ("liquiditybot_weekly_pnl",)),
    (4, "All time", "stat", ("liquiditybot_net_pnl_all_time",)),
    (5, "Drawdown", "stat", ("liquiditybot_drawdown_pct",)),
    (6, "Equity", "timeseries", ("liquiditybot_equity",)),
    (7, "Open positions", "stat", ("liquiditybot_positions_open",)),
    (8, "Gross exposure", "gauge", ("liquiditybot_gross_exposure_pct",)),
    (9, "Fees paid", "stat", ("liquiditybot_fees_total",)),
    (10, "Entries", "stat", ("liquiditybot_entries_enabled",)),
    (11, "Halt", "stat", ("liquiditybot_halted",)),
    (12, "Data age", "stat", ("liquiditybot_status_age_sec",)),
    # liveness group - restored after review; see the generator's comment on
    # why a frozen runner otherwise reads as a calm, profitable book
    (13, "Runner", "stat", ("liquiditybot_running",)),
    (14, "Telemetry", "stat", ("liquiditybot_status_stale",)),
    (15, "Kraken feed", "stat", ("liquiditybot_ws_kraken_connected",)),
    (16, "Op state", "stat", ("liquiditybot_op_state",)),
    (17, "Positions", "row", ()),
    (18, "Open positions", "table",
     ("liquiditybot_position_age_hours", "liquiditybot_position_conviction",
      "liquiditybot_position_notional_usd", "liquiditybot_position_r_multiple",
      "liquiditybot_position_stop_dist_pct", "liquiditybot_position_upnl_pct",
      "liquiditybot_position_upnl_usd")),
    (gen.INJ_ID, "", INJ_TYPE, ()),
})
_COMMAND_STRIPPED_PANELS = frozenset({(gen.INJ_ID, "", INJ_TYPE, ())})

_MET_RE = re.compile(r"liquiditybot_[a-z0-9_]+")


def _identity(p: dict) -> tuple:
    """(id, title, type, sorted metrics) — what the panel IS and what it
    ACTUALLY QUERIES. Titles lie; queries do not."""
    mets = sorted({m for t in (p.get("targets") or [])
                   for m in _MET_RE.findall(t.get("expr", ""))})
    return (p["id"], p.get("title", ""), p["type"], tuple(mets))

# Panels that execute JavaScript in the operator's browser. The glass
# injector is the only sanctioned one; a second such panel is how a board
# would grow script execution without anyone noticing.
_JS_PANEL_TYPES = (INJ_TYPE,)


def _shipped(fname: str) -> dict:
    return json.loads((ROOT / "docs" / "grafana" / fname)
                      .read_text(encoding="utf-8"))


def _all_panels(d: dict) -> list:
    """Every panel including members nested inside collapsed rows (Grafana
    moves a collapsed row's panels INTO the row object's own `panels`)."""
    out = []
    for p in d["panels"]:
        out.append(p)
        out.extend(p.get("panels") or [])
    return out


def _injector_of(d: dict) -> dict:
    inj = [p for p in _all_panels(d) if p.get("id") == gen.INJ_ID]
    assert len(inj) == 1, f"expected exactly one id-{gen.INJ_ID} panel"
    return inj[0]


# --------------------------------------------------------------------------
# the shipped == generator invariant (source of truth is the generator)
# --------------------------------------------------------------------------
def test_generator_matches_shipped_json():
    for fname, d in gen.DASHBOARDS.items():
        assert d == _shipped(fname), \
            f"{fname} differs from the generator — regenerate with " \
            "`python scripts/build_trading_dashboard.py` (never hand-edit)"


def test_expected_boards_present():
    assert set(gen.DASHBOARDS) == set(ALL_BOARDS)


# --------------------------------------------------------------------------
# the stripped state itself
# --------------------------------------------------------------------------
@pytest.mark.parametrize("fname", DEEP_BOARDS)
def test_deep_board_holds_only_the_glass_injector(fname):
    """The deep boards were emptied on purpose. One panel, and it is the
    skin — not a tile, not a row, not a text note."""
    d = _shipped(fname)
    panels = d["panels"]
    assert len(panels) == 1, (
        f"{fname}: expected EXACTLY 1 panel (the glass injector), found "
        f"{len(panels)}: {[(p.get('id'), p.get('type')) for p in panels]}. "
        "The deep boards stay empty until the reconfigured bot has produced "
        "data worth a panel.")
    only = panels[0]
    assert not only.get("panels"), f"{fname}: injector must not nest panels"
    assert only["id"] == gen.INJ_ID, f"{fname}: panel id {only['id']}"
    assert only["type"] == INJ_TYPE, f"{fname}: panel type {only['type']}"
    assert only["gridPos"]["y"] == 0, (
        f"{fname}: the only panel must sit at the top (y=0), found "
        f"{only['gridPos']}; a non-zero y leaves a dead band above it")


def test_command_board_has_not_silently_regrown():
    """Change-detector on the ONE board that kept content. Accepts the
    stripped form too, so re-stripping the board does not brick the deploy
    gate; anything else means panels appeared or disappeared without this
    pin being updated."""
    got = frozenset(_identity(p) for p in _all_panels(_shipped(COMMAND)))
    assert got in (_COMMAND_HERO_PANELS, _COMMAND_STRIPPED_PANELS), (
        f"{COMMAND} inventory does not match either pinned form.\n"
        f"  unexpected: {sorted(got - _COMMAND_HERO_PANELS)}\n"
        f"  missing:    {sorted(_COMMAND_HERO_PANELS - got)}\n"
        "If you deliberately added, removed, renamed or retyped a panel, "
        "update _COMMAND_HERO_PANELS in this file in the SAME commit — that "
        "edit is the review record.")


@pytest.mark.parametrize("fname", ALL_BOARDS)
def test_only_the_glass_injector_executes_javascript(fname):
    """The Business Text plugin runs arbitrary JS in the operator's browser
    via its afterRender hook. Exactly one panel per board may do that, and it
    must be the injector at the pinned id — otherwise a board could grow a
    second script-executing tile while every other pin stayed green."""
    js = [p for p in _all_panels(_shipped(fname))
          if p.get("type") in _JS_PANEL_TYPES]
    assert len(js) == 1, (
        f"{fname}: expected exactly ONE JavaScript-executing panel, found "
        f"{len(js)}: {[(p.get('id'), p.get('title')) for p in js]}")
    assert js[0]["id"] == gen.INJ_ID, (
        f"{fname}: the JS panel is id {js[0]['id']}, not the sanctioned "
        f"injector id {gen.INJ_ID}")


def test_liquidity_board_surfaces_telemetry_age():
    """Whatever else the at-a-glance board shows, it must show how OLD the
    data is.

    Every other number on this board is a snapshot republished by
    scripts/gc_pusher.py. If the pusher stops, the tiles do not blank - they
    keep displaying the last value they saw, indefinitely and confidently.
    A stale equity figure is indistinguishable from a live one, so the age
    reading is what makes the rest of the board falsifiable.

    This replaces the board-wide test_every_board_surfaces_telemetry_age,
    which was retired with the panels it swept: the three deep boards are
    intentionally empty and cannot carry the tile. Narrowed to the board that
    still has content, NOT weakened - the assertion is the same one.
    """
    d = _shipped(COMMAND)
    if frozenset(_identity(p) for p in _all_panels(d)) ==             _COMMAND_STRIPPED_PANELS:
        pytest.skip("command board is in the fully-stripped form")
    exprs = " ".join(t.get("expr", "")
                     for p in _all_panels(d)
                     for t in (p.get("targets") or []))
    assert "liquiditybot_status_age_sec" in exprs, (
        f"{COMMAND} has content but no panel queries "
        "liquiditybot_status_age_sec. Without it a dead exporter looks "
        "exactly like a quiet market: every tile keeps showing its last "
        "value and nothing on screen says the data stopped moving.")


# --------------------------------------------------------------------------
# the glass framework survives on every board
# --------------------------------------------------------------------------
@pytest.mark.parametrize("fname", ALL_BOARDS)
def test_every_board_carries_a_transparent_glass_injector(fname):
    d = _shipped(fname)
    inj = _injector_of(d)
    assert inj["type"] == INJ_TYPE, f"{fname}: {inj['type']}"
    assert inj["transparent"] is True, f"{fname}: injector must be transparent"
    assert inj["gridPos"]["w"] == 1 and inj["gridPos"]["h"] == 1, \
        f"{fname}: injector must stay 1x1, found {inj['gridPos']}"
    # it must be TOP-LEVEL: a panel nested in a collapsed row never renders,
    # and the skin would vanish until someone expanded that row
    assert any(p["id"] == gen.INJ_ID for p in d["panels"]), \
        f"{fname}: injector nested inside a row — it would never render"
    # and bottom-most, so it never pushes content down a grid row
    ys = [p["gridPos"]["y"] for p in d["panels"]]
    assert inj["gridPos"]["y"] == max(ys), \
        f"{fname}: injector at y={inj['gridPos']['y']}, max y={max(ys)}"
    assert min(ys) == 0, f"{fname}: no panel at y=0 — dead band at the top"


@pytest.mark.parametrize("fname", ALL_BOARDS)
def test_injector_embeds_the_whole_glass_stylesheet(fname):
    after = _injector_of(_shipped(fname))["options"]["afterRender"]
    assert gen.GLASS_RULES.strip(), "GLASS_RULES is empty — the skin is gone"
    # distinctive fragments, asserted BOTH ends: present in the module
    # constant AND in the shipped JS. A fragment that drifts out of
    # GLASS_RULES fails here rather than silently weakening the check.
    for frag in ("-webkit-text-size-adjust: 100%", "backdrop-filter",
                 f"panel-{gen.INJ_ID}"):
        assert frag in gen.GLASS_RULES, f"stale fragment {frag!r}"
        assert frag in after, f"{fname}: {frag!r} missing from afterRender"
    # the whole stylesheet, embedded as a JS string literal by _injector()
    assert json.dumps(gen.GLASS_RULES) in after, (
        f"{fname}: afterRender does not carry GLASS_RULES verbatim — the "
        "shipped skin has drifted from the generator constant")
    assert "document.getElementById('lb-glass')" in after, \
        f"{fname}: the duplicate-<style> guard is gone"


# --------------------------------------------------------------------------
# the board shell
# --------------------------------------------------------------------------
def test_board_shell_survives_the_strip():
    uids, link_targets = set(), set()
    for fname in ALL_BOARDS:
        d = _shipped(fname)
        assert "dashboard" not in d, f"{fname}: wrapped export, not importable"
        assert d["schemaVersion"] == 39, f"{fname}: {d['schemaVersion']}"
        assert d["uid"], f"{fname}: empty uid"
        assert d["uid"] not in uids, f"{fname}: uid {d['uid']} not unique"
        uids.add(d["uid"])
        assert d["title"].strip(), f"{fname}: empty title"
        assert d["tags"], f"{fname}: no tags — board is unfindable"
        links = d["links"]
        assert links, f"{fname}: nav links gone — the boards are unreachable"
        link_targets |= {ln["url"] for ln in links}
    assert link_targets == {f"/d/{u}" for u in uids}, (
        "nav links and board uids disagree — a link points at a board that "
        f"does not exist, or a board is unreachable: {sorted(link_targets)} "
        f"vs {sorted(uids)}")


# --------------------------------------------------------------------------
# a rebuild has to remain possible
# --------------------------------------------------------------------------
def test_panel_factories_still_build_a_board():
    """Not `callable()` — that proves nothing. Actually run the factories
    through _board() and check a real multi-panel board comes out, so the
    day the boards are rebuilt the framework is known to work."""
    for name in ("row", "stat", "state", "gauge", "timeseries", "bargauge",
                 "donut", "table", "text"):
        assert callable(getattr(gen, name, None)), f"factory {name} is gone"

    def _author():
        # gen.USD ("prefix:$"), never Grafana's built-in "currencyUSD": that
        # unit SI-abbreviates at >=$1k and renders $4,997.92 as "$5.00K", so
        # the number shown is not the number the bot holds. Nothing in the
        # battery enforces this, which is exactly why the worked example a
        # rebuilder copies from must not demonstrate the wrong one.
        gen.stat("Equity", gen.M("liquiditybot_equity"), 6, 6, unit=gen.USD)
        gen.gauge("Exposure", gen.M("liquiditybot_gross_exposure_pct"), 6, 6)
        gen.timeseries("Equity", gen.M("liquiditybot_equity"), 12, 7)
        gen.row("Positions")
        gen.table("Open", 24, 9,
                  cols=[("liquiditybot_position_upnl_usd", "uP&L", gen.USD,
                         2, None, "text")],
                  label_keys=["symbol"])

    saved = (list(gen.panels), dict(gen._cur), dict(gen._pid))
    try:
        built = gen._board("throwaway-uid", "throwaway", "probe", _author,
                           "probe")
    finally:  # _board leaves the module buffers dirty; put them back
        gen.panels.clear()
        gen.panels.extend(saved[0])
        gen._cur.clear()
        gen._cur.update(saved[1])
        gen._pid.clear()
        gen._pid.update(saved[2])

    built_panels = built["panels"]
    assert len(built_panels) > 1, "factories produced no content panels"
    types = {p["type"] for p in built_panels} | {
        m["type"] for p in built_panels for m in (p.get("panels") or [])}
    assert {"stat", "gauge", "timeseries", "table", INJ_TYPE} <= types, \
        f"rebuilt board is missing panel types: {sorted(types)}"
    assert built["schemaVersion"] == 39
    assert any(p["id"] == gen.INJ_ID for p in built_panels), \
        "a rebuilt board would ship without the glass injector"
