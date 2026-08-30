"""tests/test_glass_suite.py — the board-suite contract (glass RETIRED).

HISTORICAL NAME. The Liquid Glass skin was deleted 100% on 2026-08-30
operator directive (three same-day display incidents from its CSS-injection
mechanism — 51b261af / b8a673ce / 42560be0; the design language now renders
natively in scripts/glass_console.py). What this file keeps: the four-board
family pins, and every SUBSTANCE contract that survived the skin — accuracy
idioms (joinByField tables, no query-text tiles, valid PromQL), plus the
retirement pins for the boards that stay retired.
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


def test_boards_are_native_and_script_free():
    # 2026-08-30 glass removal: no injector, no dynamictext plugin, no
    # afterRender hook, no forced transparency, and no html-mode text tile
    # (Grafana sanitizes those anyway — an html tile is always a mistake).
    # This is the suite-side twin of test_boards_stripped's one-way pin.
    for d in _boards():
        for p in _panels(d):
            assert p["type"] != "marcusolsson-dynamictext-panel", \
                f'{d["uid"]}: panel {p["id"]} resurrects the glass injector'
            opts = p.get("options") or {}
            assert not opts.get("afterRender"), \
                f'{d["uid"]}: panel {p["id"]} executes browser script'
            assert not (p["type"] == "text"
                        and opts.get("mode") == "html"), \
                f'{d["uid"]}: html-mode text tile (sanitized to nothing)'


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
