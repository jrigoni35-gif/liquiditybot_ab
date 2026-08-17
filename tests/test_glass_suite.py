"""tests/test_glass_suite.py — the Liquid Glass suite contract.

The glass suite IS the four banner boards (2026-07-22 spec). The dedicated
glass + mobile boards were retired; these pins keep them retired and keep
the glass primitives (value-only state tiles, joinByField tables, CSS
injector, transparency) from regressing.
"""
from pathlib import Path

import scripts.build_trading_dashboard as gen
import scripts.grafana_import as gi

ROOT = Path(__file__).resolve().parents[1]


def test_retired_glass_boards_stay_retired():
    # 2026-08-17 three-link rebuild: LEARNING replaced the injector-only
    # screening board. The family stays at exactly four; screening joins
    # the retired set below so an import run deletes it from the instance.
    boards = {"liquiditybot_command.json", "liquiditybot_execution.json",
              "liquiditybot_problem_solution.json",
              "liquiditybot_learning.json"}
    assert set(gi.DASHBOARDS) == boards
    assert set(gen.DASHBOARDS) == boards
    for name in ("liquiditybot_glass.json", "liquiditybot_glass_mobile.json",
                 "liquiditybot_screening.json"):
        assert not (ROOT / "docs" / "grafana" / name).exists(), \
            f"{name} was retired (glass/mobile 2026-07-22, screening " \
            "2026-08-17) — do not resurrect"
    assert "liquiditybot-screening" in gi.RETIRED_UIDS, \
        "the screening uid must be deleted from the instance on import"


def _boards():
    return list(gen.DASHBOARDS.values())


def _panels(d):
    """Every panel including members nested inside collapsed rows —
    collapsed rows carry their panels in the row object's own list, and
    every glass pin must keep applying to them (2026-07-25)."""
    out = []
    for p in d["panels"]:
        out.append(p)
        out.extend(p.get("panels") or [])
    return out


def test_all_panels_transparent():
    for d in _boards():
        for p in _panels(d):
            if p["type"] != "row":
                assert p.get("transparent") is True, \
                    f'{d["uid"]}: panel {p["id"]} not transparent'


def test_injector_present_and_self_hiding():
    # 2026-07-23: injector promoted from the dormant native text tile to a
    # Business Text panel — Grafana Cloud sanitizes <style> in native text,
    # so the CSS is injected into document.head by the plugin's afterRender
    # hook instead (plugin installed by the operator; README_glass.md).
    # id 990 is the CSS injector; the Pulse board carries a SECOND Business
    # Text panel (its whole-screen content tile), so select the injector by
    # its fixed id rather than by plugin type.
    for d in _boards():
        inj = [p for p in d["panels"]
               if p["type"] == "marcusolsson-dynamictext-panel"
               and p["id"] == 990]
        assert len(inj) == 1, f'{d["uid"]}: exactly one CSS injector'
        opts = inj[0]["options"]
        assert "afterRender" in opts.get("editors", []), \
            "afterRender editor must be enabled for the hook to run"
        js = opts["afterRender"]
        assert "lb-glass" in js            # idempotence guard + style id
        assert "panel-990" in js           # hides its own tile
        assert "backdrop-filter" in js     # the frosted skin
        # no native text injector left behind (would be sanitized anyway)
        assert not [p for p in d["panels"] if p["type"] == "text"
                    and p.get("options", {}).get("mode") == "html"]


def test_state_tiles_never_print_query_text():
    # textMode value_and_name on a background stat renders the raw PromQL
    # inside the tile (7/22 screenshots) — banned suite-wide
    for d in _boards():
        for p in _panels(d):
            if p["type"] == "stat":
                assert p["options"]["textMode"] != "value_and_name", \
                    f'{d["uid"]}: panel {p["id"]} ({p["title"]})'


def test_tables_use_outer_join_recipe():
    # merge silently drops rows when frames disagree on label columns and
    # paints absent cells with base threshold colors; every table joins
    for d in _boards():
        for p in _panels(d):
            if p["type"] != "table":
                continue
            tr = p["transformations"]
            assert tr[0]["id"] == "joinByField", \
                f'{d["uid"]}: table {p["title"]} not joined'
            assert tr[0]["options"]["mode"] == "outer"
            assert tr[1]["id"] == "filterFieldsByName"
            for t in p["targets"]:
                assert t.get("format") == "table"


def test_no_double_selector_promql():
    # M('metric{source="live"}') built {..}{job=..} — invalid PromQL that
    # renders as a silent "No data" (7/22 Live/Candidate labels defect)
    for d in _boards():
        for p in _panels(d):
            for t in p.get("targets", []):
                assert "}{" not in t["expr"].replace(" ", ""), \
                    f'{d["uid"]}: {p["title"]}: {t["expr"]}'


def test_markout_queried_by_horizon_sec():
    # the exporter labels mark-out {asset, horizon_sec} — a bare
    # `horizon=` selector matches nothing and shows "No data"
    for d in _boards():
        for p in _panels(d):
            for t in p.get("targets", []):
                if "liquiditybot_markout_bps" in t["expr"] and "{" in t["expr"]:
                    assert "horizon=" not in t["expr"], \
                        f'{d["uid"]}: {p["title"]} uses wrong label'


def test_bargauges_basic_mode():
    # gradient mode paints the threshold ramp INSIDE every bar (reads as
    # data that isn't there); basic mode colors the bar by its value
    for d in _boards():
        for p in _panels(d):
            if p["type"] == "bargauge":
                assert p["options"]["displayMode"] == "basic", \
                    f'{d["uid"]}: {p["title"]}'


def test_signed_table_columns_use_color_text():
    # an outer join leaves legitimately-absent cells null, and a null
    # color-background cell paints the BASE threshold color - alarm red
    # on PNL scales (the 7/22 defect). Signed columns must color TEXT.
    for d in _boards():
        for p in _panels(d):
            if p["type"] != "table":
                continue
            for o in p["fieldConfig"]["overrides"]:
                props = {pr["id"]: pr["value"] for pr in o["properties"]}
                thr = props.get("thresholds") or {}
                steps = thr.get("steps") or []
                if not steps or steps[0].get("color") != "#FF453A":
                    continue
                cell = props.get("custom.cellOptions") or {}
                assert cell.get("type") == "color-text", (
                    f'{d["uid"]}: table {p["title"]!r} column '
                    f'{o["matcher"]["options"]!r} has a red-based scale '
                    "but paints cell backgrounds")


def test_uids_and_nav_links_pinned():
    uids = {d["uid"] for d in _boards()}
    assert uids == {"liquiditybot-trading", "liquiditybot-exec",
                    "liquiditybot-problem-solution",
                    "liquiditybot-learning"}
    for d in _boards():
        nav = {ln["url"] for ln in d["links"]}
        assert nav == {f"/d/{u}" for u in uids}, d["uid"]
