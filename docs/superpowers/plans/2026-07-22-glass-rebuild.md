# Liquid Glass Rebuild of the Four Banner Boards — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Retire the accidental dedicated Glass + mobile dashboards and re-author the four generator-owned banner boards (Command · Models·Inv·Exec · Problem/Solution · Screening) in the Liquid Glass language, fixing all 7/22 screenshot defects structurally.

**Architecture:** All board JSON is produced by `scripts/build_trading_dashboard.py` (single source of truth; `tests/test_trading_dashboard.py` enforces generator == shipped JSON). The rebuild happens inside that file: its panel helpers become glass primitives (value-only state tiles, basic-mode bar gauges, donut, `joinByField` tables, hidden CSS injector, transparency), then the four `_author_*` functions are re-authored one board per task. Every task ends with regenerated JSONs and a green dashboard suite.

**Tech Stack:** Python 3.11 (stdlib only in the generator), Grafana Cloud schema v39 dashboards, Prometheus/PromQL, pytest.

## Global Constraints

- The four boards stay GENERATOR-OWNED: never hand-edit `docs/grafana/liquiditybot_{command,execution,problem_solution,screening}.json`; regenerate with `python scripts/build_trading_dashboard.py` after every generator change.
- Every metric currently queried by a board stays on that board (consolidation into denser panels allowed; deletion is not). `tests/test_trading_dashboard.py::test_every_query_hits_an_emitted_metric` guards querying only emitted metrics.
- Preserve verbatim (pinned by `tests/test_telemetry_restart_coupling.py::test_sparse_panels_declare_honest_empty_states`, all on the execution board): `"noValue": "no fills yet"` at least 3×, and `"noValue": "flat — no open positions"` exactly on the open-positions bargauge.
- Board uids unchanged: `liquiditybot-trading`, `liquiditybot-exec`, `liquiditybot-problem-solution`, `liquiditybot-screening`. Nav banner `_NAV`/`_links()` unchanged. Non-scaling dollar unit `USD = "prefix:$"` on every money panel.
- JSONs written with `ensure_ascii=False` (em-dashes stay literal).
- Position metrics are labeled `{symbol, side}`; per-asset metrics `{asset}`; skimmer `{pair}`; mark-out `{asset, horizon_sec}` (values "5"/"30"/"60"). `liquiditybot_position_upnl_pct`, `_conviction`, `_r_multiple`, `_stop_dist_pct` are CONDITIONALLY emitted — table joins must be outer joins and absent cells must not paint alarm colors.
- Commit after every task; run `python -m pytest tests/test_trading_dashboard.py tests/test_telemetry_restart_coupling.py tests/test_glass_suite.py -q` (the dashboard suite) inside every task; the FULL CLAUDE.md battery runs in Task 7 before deploy.
- `GRAFANA_SA_TOKEN` comes from `~/.liquiditybot/grafana-sa-token` via env only — never argv, never committed.

---

### Task 1: Retire the accidental Glass + mobile boards

**Files:**
- Delete: `docs/grafana/liquiditybot_glass.json`, `docs/grafana/liquiditybot_glass_mobile.json`
- Modify: `scripts/grafana_import.py:24-38` (DASHBOARDS list)
- Rewrite: `docs/grafana/README_glass.md`
- Create: `tests/test_glass_suite.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `tests/test_glass_suite.py` with `ROOT` (repo-root `Path`) and `test_retired_glass_boards_stay_retired()`; later tasks append tests to this file.

- [ ] **Step 1: Write the failing test**

Create `tests/test_glass_suite.py`:

```python
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
    four = {"liquiditybot_command.json", "liquiditybot_execution.json",
            "liquiditybot_problem_solution.json",
            "liquiditybot_screening.json"}
    assert set(gi.DASHBOARDS) == four
    assert set(gen.DASHBOARDS) == four
    for name in ("liquiditybot_glass.json", "liquiditybot_glass_mobile.json"):
        assert not (ROOT / "docs" / "grafana" / name).exists(), \
            f"{name} was retired on 2026-07-22 — do not resurrect"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_glass_suite.py -q`
Expected: FAIL — `set(gi.DASHBOARDS)` still contains the two glass entries and both files exist.

- [ ] **Step 3: Delete the boards and importer entries**

```bash
git rm docs/grafana/liquiditybot_glass.json docs/grafana/liquiditybot_glass_mobile.json
```

In `scripts/grafana_import.py` replace the whole DASHBOARDS list (lines 24-38) with:

```python
DASHBOARDS = [
    # the four banner-linked Liquid Glass boards — generator-owned by
    # scripts/build_trading_dashboard.py (the command board keeps uid
    # liquiditybot-trading, replacing the old monolith). The dedicated
    # glass + mobile boards were retired 2026-07-22; the glass treatment
    # lives in the four boards themselves (docs/grafana/README_glass.md).
    "liquiditybot_command.json",
    "liquiditybot_execution.json",
    "liquiditybot_problem_solution.json",
    "liquiditybot_screening.json",
]
```

- [ ] **Step 4: Rewrite the README**

Replace the full contents of `docs/grafana/README_glass.md` with:

```markdown
# Liquid Glass — the four banner boards

The Liquid Glass suite IS the four banner-linked boards (Command ·
Models·Inv·Exec · Problem/Solution · Screening). They are generated by
`scripts/build_trading_dashboard.py` (never hand-edit the JSONs) and
imported with `scripts/grafana_import.py`. The dedicated glass + mobile
boards were retired 2026-07-22.

Native look (works on any Grafana Cloud instance): transparent panels
over the dark ground, Apple system palette (semantic color only), value-
only state tiles, basic-mode bar gauges, joined tables, donut
composition.

## Frosted-blur upgrade (optional, needs Admin once)

Grafana Cloud sanitizes `<style>` in native text panels, so each board
ships a hidden 1x1 CSS-injector tile that stays dormant. To activate the
full frosted-glass skin:

1. Log in to Grafana as **Admin** → Administration → Plugins.
2. Search **"Business Text"** (marcusolsson-dynamictext-panel), Install.
   (The Editor service-account token gets HTTP 403 on plugin install —
   this step needs the human Admin login.)
3. Tell the bot session: it will move the injector CSS into a Business
   Text panel (afterRender) and re-import. No other changes needed.

The CSS itself lives in the generator (`GLASS_CSS`), so it is versioned
with everything else.
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_glass_suite.py tests/test_trading_dashboard.py -q`
Expected: PASS (the four-board generator tests never referenced the glass files).

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "chore(grafana): retire the dedicated glass + mobile boards

The glass suite is the four banner boards (2026-07-22 spec); pin the
retirement in tests so the accidental boards cannot resurrect."
```

---

### Task 2: Glass kit + structural fixes in the generator

**Files:**
- Modify: `scripts/build_trading_dashboard.py` (module docstring lines 1-37; helpers `stat` 103-131, `state` 134-139, `timeseries` 162-189, `bargauge` 192-214, `table` 217-263, `text` 266-274; `_board` 874-884)
- Modify: `tests/test_trading_dashboard.py:149-157` (allowed panel types) and its module docstring point 4
- Modify: `tests/test_glass_suite.py` (append regressions)
- Regenerate: the four `docs/grafana/liquiditybot_*.json`

**Interfaces:**
- Consumes: Task 1's `tests/test_glass_suite.py`.
- Produces (used verbatim by Tasks 3-6):
  - `stat(title, expr, w, h, unit="", decimals=2, desc="", steps=None, mode="value", mappings=None, text_mode="auto", graph="area", no_value=None, display_name=None)` — unchanged signature.
  - `state(title, expr, w, h, mapping, desc="", no_value=None)` — gains `no_value`.
  - `gauge(title, expr, w, h, mx=35.0, unit="percent", decimals=1, steps=None, desc="", no_value=None)` — unchanged.
  - `timeseries(title, expr, w, h, unit="", legend="value", desc="", fill=18, calcs=None, decimals=None, extra=None, colors=None)` — gains `colors` (dict series-name → hex, rendered as byName fixed-color overrides).
  - `bargauge(title, expr, w, h, unit="", decimals=2, steps=None, legend="{{asset}}", desc="", mn=None, mx=None, no_value=None, extra=None)` — displayMode becomes `"basic"`; gains `extra` (list of `(expr, legend)` extra targets for multi-metric ranked bars).
  - `donut(title, slices, w, h, colors, desc="", no_value=None)` — NEW; `slices` = list of `(expr, legend)`, `colors` = dict legend → hex.
  - `table(title, w, h, cols, label_keys, sort=None, desc="", drop=())` — `cols` items are `(metric_or_expr, name, unit, decimals[, thresholds[, cell]])` where `cell` is `"bg"` (default, color-background gradient) or `"text"` (color-text — REQUIRED for signed/PNL columns so absent cells never paint alarm red); transformations become joinByField-outer on `label_keys[0]` + filterFieldsByName + organize; `drop` lists post-join duplicate columns to exclude (e.g. `"side 2"`).
  - Module constants: `GREEN "#30D158"`, `RED_HEX "#FF453A"`, `ORANGE_HEX "#FF9F0A"`, `INDIGO "#5E5CE6"`, `GRAY_HEX "#8E8E93"`, `CAT_TEAL "#2596AB"`, `CAT_PURPLE "#BF5AF2"`, `GLASS_CSS`, `INJ_ID = 990`.
  - `_board()` appends a hidden self-hiding CSS-injector text panel (id 990) and sets `"transparent": True` on every non-row panel.

- [ ] **Step 1: Append the failing regression tests**

Append to `tests/test_glass_suite.py`:

```python
def _boards():
    return list(gen.DASHBOARDS.values())


def test_all_panels_transparent():
    for d in _boards():
        for p in d["panels"]:
            if p["type"] != "row":
                assert p.get("transparent") is True, \
                    f'{d["uid"]}: panel {p["id"]} not transparent'


def test_injector_present_and_self_hiding():
    for d in _boards():
        inj = [p for p in d["panels"] if p["type"] == "text"
               and p.get("options", {}).get("mode") == "html"]
        assert len(inj) == 1, f'{d["uid"]}: exactly one CSS injector'
        assert inj[0]["id"] == 990
        css = inj[0]["options"]["content"]
        assert "panel-990" in css          # hides its own tile
        assert "backdrop-filter" in css    # the frosted skin


def test_state_tiles_never_print_query_text():
    # textMode value_and_name on a background stat renders the raw PromQL
    # inside the tile (7/22 screenshots) — banned suite-wide
    for d in _boards():
        for p in d["panels"]:
            if p["type"] == "stat":
                assert p["options"]["textMode"] != "value_and_name", \
                    f'{d["uid"]}: panel {p["id"]} ({p["title"]})'


def test_tables_use_outer_join_recipe():
    # merge silently drops rows when frames disagree on label columns and
    # paints absent cells with base threshold colors; every table joins
    for d in _boards():
        for p in d["panels"]:
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
        for p in d["panels"]:
            for t in p.get("targets", []):
                assert "}{" not in t["expr"].replace(" ", ""), \
                    f'{d["uid"]}: {p["title"]}: {t["expr"]}'


def test_markout_queried_by_horizon_sec():
    # the exporter labels mark-out {asset, horizon_sec} — a bare
    # `horizon=` selector matches nothing and shows "No data"
    for d in _boards():
        for p in d["panels"]:
            for t in p.get("targets", []):
                if "liquiditybot_markout_bps" in t["expr"] and "{" in t["expr"]:
                    assert "horizon=" not in t["expr"], \
                        f'{d["uid"]}: {p["title"]} uses wrong label'


def test_bargauges_basic_mode():
    # gradient mode paints the threshold ramp INSIDE every bar (reads as
    # data that isn't there); basic mode colors the bar by its value
    for d in _boards():
        for p in d["panels"]:
            if p["type"] == "bargauge":
                assert p["options"]["displayMode"] == "basic", \
                    f'{d["uid"]}: {p["title"]}'
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_glass_suite.py -q`
Expected: FAIL — `test_all_panels_transparent`, `test_injector_present_and_self_hiding`, `test_tables_use_outer_join_recipe`, `test_no_double_selector_promql` (command board's Live/Candidate labels), `test_bargauges_basic_mode`. (`test_state_tiles_never_print_query_text` and `test_markout_queried_by_horizon_sec` already pass — they are ratchets.)

- [ ] **Step 3: Add module constants + GLASS_CSS**

In `scripts/build_trading_dashboard.py`, directly under `USD = "prefix:$"` (line 48), insert:

```python
# ---- Apple Liquid Glass constants ------------------------------------------
# Semantic palette (mapped over named colors by _apple_palette) plus the
# dataviz-validated categorical series set for multi-line charts.
GREEN = "#30D158"
RED_HEX = "#FF453A"
ORANGE_HEX = "#FF9F0A"
INDIGO = "#5E5CE6"
GRAY_HEX = "#8E8E93"
CAT_TEAL = "#2596AB"
CAT_PURPLE = "#BF5AF2"

INJ_ID = 990          # fixed id on every board so the CSS can self-hide

# Hidden frosted-glass skin. Grafana Cloud sanitizes native <style> until
# the signed Business Text plugin is installed (Admin-only) — the tile
# ships dormant; see docs/grafana/README_glass.md.
GLASS_CSS = """<style id="lb-glass">
.main-view, .scrollbar-view { background: #000 !important; }
html, body, .main-view, [class*="dashboard"] {
  font-family: -apple-system, "SF Pro Text", "SF Pro Display", "Inter",
               system-ui, sans-serif !important;
  -webkit-font-smoothing: antialiased;
}
[data-testid="data-testid panel content"] {
  background: linear-gradient(180deg, rgba(40,40,44,.60) 0%,
              rgba(28,28,30,.50) 100%) !important;
  backdrop-filter: blur(22px) saturate(180%);
  -webkit-backdrop-filter: blur(22px) saturate(180%);
  border: .5px solid rgba(255,255,255,.12) !important;
  border-radius: 20px !important;
  box-shadow: inset 0 1px 0 0 rgba(255,255,255,.14),
              inset 0 -1px 1px 0 rgba(0,0,0,.30),
              0 1px 1px rgba(0,0,0,.35), 0 12px 32px rgba(0,0,0,.55) !important;
}
.react-grid-item { background: transparent !important; }
[data-testid^="data-testid Panel header"] { background: transparent !important;
  border: 0 !important; }
[data-testid="data-testid header-container"] {
  font-weight: 600; letter-spacing: .4px; font-size: 11px;
  text-transform: uppercase; color: rgba(235,235,245,.6) !important; }
[data-testid^="data-testid dashboard-row-title-"] {
  text-transform: uppercase; letter-spacing: 1.4px; font-size: 12px;
  font-weight: 700; color: rgba(235,235,245,.55) !important; }
[data-viz-panel-key="panel-990"] { display: none !important; }
</style>
<span id="lb-glass-marker"></span>"""
```

- [ ] **Step 4: Patch `state`, `timeseries`, `bargauge`; add `donut`**

Replace `state()` (lines 134-139) with:

```python
def state(title, expr, w, h, mapping, desc="", no_value=None):
    opts = {k: {"text": v[0], "color": v[1], "index": i}
            for i, (k, v) in enumerate(mapping.items())}
    stat(title, expr, w, h, desc=desc, mode="background", text_mode="value",
         graph="none", mappings=[{"type": "value", "options": opts}],
         steps=[{"color": "text", "value": None}], no_value=no_value)
```

Replace `timeseries()` (lines 162-189) with (adds `colors`; body otherwise identical):

```python
def timeseries(title, expr, w, h, unit="", legend="value", desc="", fill=18,
               calcs=None, decimals=None, extra=None, colors=None):
    """calcs upgrades the legend to a table of reductions (exact numbers
    beside the trend). colors: {series_name: hex} pins each line to a
    fixed validated color instead of palette-classic rotation."""
    x, y = _place(w, h)
    fld = {"unit": unit, "custom": {
        "drawStyle": "line", "lineInterpolation": "smooth", "lineWidth": 2,
        "fillOpacity": fill, "gradientMode": "opacity",
        "showPoints": "never", "spanNulls": True, "pointSize": 5,
        "axisPlacement": "auto",
        "scaleDistribution": {"type": "linear"}},
        "color": {"mode": "palette-classic"}}
    if decimals is not None:
        fld["decimals"] = decimals
    overrides = []
    for name, col in (colors or {}).items():
        overrides.append({"matcher": {"id": "byName", "options": name},
                          "properties": [{"id": "color", "value": {
                              "mode": "fixed", "fixedColor": col}}]})
    panels.append({
        "id": _id(), "type": "timeseries", "title": title, "description": desc,
        "datasource": DS, "gridPos": {"h": h, "w": w, "x": x, "y": y},
        "fieldConfig": {"defaults": fld, "overrides": overrides},
        # showLegend MUST be present: the bare {displayMode:"hidden"} shape
        # blanks the whole timeseries plugin on current Grafana Cloud.
        "options": {"legend": {"showLegend": True,
                               "displayMode": "table" if calcs else "list",
                               "placement": "bottom", "calcs": calcs or []},
                    "tooltip": {"mode": "multi", "sort": "desc"}},
        "targets": [_t(expr, instant=False, legend=legend)] + [
            _t(e, ref=chr(ord("B") + i), instant=False, legend=lg)
            for i, (e, lg) in enumerate(extra or [])]})
```

Replace `bargauge()` (lines 192-214) with (basic mode + `extra` targets):

```python
def bargauge(title, expr, w, h, unit="", decimals=2, steps=None,
             legend="{{asset}}", desc="", mn=None, mx=None, no_value=None,
             extra=None):
    """Horizontal bars, one per series — basic mode colors each bar by its
    value (gradient mode paints the whole threshold ramp inside every bar,
    which reads as data that isn't there). extra: [(expr, legend)] extra
    targets, for ranked comparisons across scalar metrics."""
    x, y = _place(w, h)
    fld = {"unit": unit, "decimals": decimals, "color": {"mode": "thresholds"},
           "thresholds": {"mode": "absolute",
                          "steps": steps or [{"color": "blue", "value": None}]}}
    if no_value:
        fld["noValue"] = no_value
    if mn is not None:
        fld["min"] = mn
    if mx is not None:
        fld["max"] = mx
    panels.append({
        "id": _id(), "type": "bargauge", "title": title, "description": desc,
        "datasource": DS, "gridPos": {"h": h, "w": w, "x": x, "y": y},
        "fieldConfig": {"defaults": fld, "overrides": []},
        "options": {"displayMode": "basic", "orientation": "horizontal",
                    "showUnfilled": True, "valueMode": "color",
                    "namePlacement": "left", "sizing": "auto",
                    "reduceOptions": {"calcs": ["lastNotNull"], "fields": "",
                                      "values": False}},
        "targets": [_t(expr, instant=True, legend=legend)] + [
            _t(e, ref=chr(ord("B") + i), instant=True, legend=lg)
            for i, (e, lg) in enumerate(extra or [])]})
```

Insert `donut()` directly after `bargauge()`:

```python
def donut(title, slices, w, h, colors, desc="", no_value=None):
    """2-4 slice composition donut. slices: [(expr, legend)]; colors:
    {legend: hex} — color follows the ENTITY, fixed, never positional."""
    x, y = _place(w, h)
    overrides = [{"matcher": {"id": "byName", "options": name},
                  "properties": [{"id": "color", "value": {
                      "mode": "fixed", "fixedColor": col}}]}
                 for name, col in colors.items()]
    fld = {"unit": "percentunit", "decimals": 1, "mappings": [],
           "color": {"mode": "palette-classic"}}
    if no_value:
        fld["noValue"] = no_value
    panels.append({
        "id": _id(), "type": "piechart", "title": title, "description": desc,
        "datasource": DS, "gridPos": {"h": h, "w": w, "x": x, "y": y},
        "fieldConfig": {"defaults": fld, "overrides": overrides},
        "options": {"pieType": "donut",
                    "displayLabels": ["name", "percent"],
                    "legend": {"displayMode": "list", "placement": "bottom",
                               "showLegend": True},
                    "reduceOptions": {"calcs": ["lastNotNull"], "fields": "",
                                      "values": False},
                    "tooltip": {"mode": "single"}},
        "targets": [_t(e, ref=chr(ord("A") + i), instant=True, legend=lg)
                    for i, (e, lg) in enumerate(slices)]})
```

- [ ] **Step 5: Replace `table()` with the outer-join recipe**

Replace `table()` (lines 217-263) with:

```python
def table(title, w, h, cols, label_keys, sort=None, desc="", drop=()):
    """cols: (metric_or_expr, name, unit, decimals[, thresholds[, cell]]).
    cell "bg" (default) = color-background gradient heatmap cell; "text" =
    color-text — REQUIRED for signed/PNL columns, because an outer join
    leaves legitimately-absent cells null and a null background paints the
    BASE threshold color (alarm red on PNL scales — the 7/22 defect).
    Frames join outer on label_keys[0]; other label columns ride along
    from the join; drop lists post-join duplicate columns to exclude."""
    x, y = _place(w, h)
    refs = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    targets, rename, order, overrides = [], {}, {}, []
    for k in label_keys:
        order[k] = len(order)
    for i, col in enumerate(cols):
        metric, name, unit, dec = col[0], col[1], col[2], col[3]
        thr = col[4] if len(col) > 4 else None
        cell = col[5] if len(col) > 5 else "bg"
        r = refs[i]
        expr = metric if "(" in metric or "{" in metric else f"{metric}{JOB}"
        targets.append(_t(expr, ref=r, fmt="table"))
        rename[f"Value #{r}"] = name
        order[name] = len(order)
        props = [{"id": "unit", "value": unit},
                 {"id": "decimals", "value": dec}]
        if thr:
            cell_opts = {"type": "color-background", "mode": "gradient"} \
                if cell == "bg" else {"type": "color-text"}
            props += [
                {"id": "thresholds",
                 "value": {"mode": "absolute", "steps": thr}},
                {"id": "color", "value": {"mode": "thresholds"}},
                {"id": "custom.cellOptions", "value": cell_opts}]
        overrides.append({"matcher": {"id": "byName", "options": name},
                          "properties": props})
    include = "^(" + "|".join(label_keys) + r"|Value.*)$"
    panels.append({
        "id": _id(), "type": "table", "title": title, "description": desc,
        "datasource": DS, "gridPos": {"h": h, "w": w, "x": x, "y": y},
        "fieldConfig": {"defaults": {"noValue": "·", "custom": {
            "align": "auto", "filterable": True, "cellOptions": {"type": "auto"},
            "lineWidth": 1}}, "overrides": overrides},
        "options": {"showHeader": True, "cellHeight": "sm",
                    "footer": {"show": False},
                    "sortBy": [{"displayName": sort or label_keys[0],
                                "desc": bool(sort)}]},
        "targets": targets,
        "transformations": [
            {"id": "joinByField",
             "options": {"byField": label_keys[0], "mode": "outer"}},
            {"id": "filterFieldsByName",
             "options": {"include": {"pattern": include}}},
            {"id": "organize", "options": {
                "excludeByName": {d: True for d in drop},
                "renameByName": rename, "indexByName": order}}]})
```

- [ ] **Step 6: Injector + transparency in `_board`; docstring**

Replace `_board()` (lines 874-884) with:

```python
def _injector():
    return {"id": INJ_ID, "type": "text", "title": "", "datasource": None,
            "gridPos": {"h": 1, "w": 1, "x": 0, "y": _cur["y"] + 1},
            "transparent": True,
            "options": {"mode": "html", "content": GLASS_CSS,
                        "code": {"language": "html",
                                 "showLineNumbers": False,
                                 "showMiniMap": False}},
            "pluginVersion": "11.1.0"}


def _board(uid, title, desc, author, extra_tag):
    panels.clear()
    _cur.update(x=0, y=0, row_h=0)
    _pid["n"] = 0
    author()
    _flush()
    panels.append(_injector())
    for p in panels:
        if p["type"] != "row":
            p["transparent"] = True
    return {"uid": uid, "title": title, "description": desc,
            "tags": _TAGS + [extra_tag], "schemaVersion": 39, "editable": True,
            "timezone": "browser", "refresh": "30s", "style": "dark",
            "time": {"from": "now-24h", "to": "now"}, "links": _links(),
            "templating": {"list": []}, "annotations": {"list": []},
            "panels": list(panels)}
```

In `text()` (line 271) change `"transparent": False` to `"transparent": True` (the `_board` pass would overwrite it anyway; keep the literal consistent).

Update the module docstring's DESIGN paragraph (lines 8-31): replace the sentence beginning "A consistent visual language across four focused boards:" with "One Liquid Glass visual language across four focused boards (transparent panels, Apple system palette, value-only state tiles, basic-mode bar gauges, outer-joined tables, a dormant frosted-skin CSS injector — see docs/grafana/README_glass.md):" — keep the bullet list.

- [ ] **Step 7: Fix the two call sites the new `table()` breaks, minimally**

(The full re-authoring happens in Tasks 3-6; this keeps every board valid NOW.)

In `_positions_table()` (line 551) change the call to add the duplicate-side drops:

```python
def _positions_table():
    table("Open positions (net per instrument)", 12, 5,
          cols=[("liquiditybot_position_upnl_usd", "uPnL $", USD, 2, PNL, "text"),
                ("liquiditybot_position_upnl_pct", "uPnL %", "percent", 2, PNL, "text"),
                ("liquiditybot_position_r_multiple", "R", "short", 2, PNL, "text"),
                ("liquiditybot_position_notional_usd", "Notional $", USD, 0),
                ("liquiditybot_position_conviction", "p_win", "percentunit", 2, HIGH_GOOD),
                ("liquiditybot_position_stop_dist_pct", "Stop %", "percent", 2),
                ("liquiditybot_position_age_hours", "Age h", "short", 1)],
          label_keys=["symbol", "side"], sort="uPnL $",
          drop=tuple(f"side {i}" for i in range(2, 8)),
          desc="Open instruments; green uPnL/R rows are working, red need "
               "managing.")
```

In `_author_command()` fix the two invalid double-selector exprs (lines 432-437):

```python
    stat("Live labels",
         'max(liquiditybot_ml_labels{source="live",job="liquiditybot"})',
         4, 5, decimals=0, steps=[{"color": "red", "value": None},
         {"color": "yellow", "value": 30}, {"color": "green", "value": 60}],
         desc="Ground-truth closed-trade labels — earns model complexity.")
    stat("Candidate labels",
         'max(liquiditybot_ml_labels{source="candidate",job="liquiditybot"})',
         4, 5, decimals=0, steps=BLUE, desc="Triple-barrier proxy labels.")
```

In `_author_execution()` and `_author_screening()`, change the mark-out tables from the two-key form to the horizon-pivot form (join on asset, one column per horizon — same metric, correct label):

```python
    table("Post-fill mark-out (adverse selection)", 12, 6,
          cols=[('liquiditybot_markout_bps{job="liquiditybot",horizon_sec="5"}',
                 "5s bps", "short", 2, PNL, "text"),
                ('liquiditybot_markout_bps{job="liquiditybot",horizon_sec="30"}',
                 "30s bps", "short", 2, PNL, "text"),
                ('liquiditybot_markout_bps{job="liquiditybot",horizon_sec="60"}',
                 "60s bps", "short", 2, PNL, "text")],
          label_keys=["asset"], sort="5s bps",
          desc="Price drift after our fill at 5/30/60s; persistently "
               "negative = picked off.")
```

(in `_author_screening()` the same cols/label_keys/sort with its original title
"Adverse selection (mark-out)", width 8, height 7, and its original desc.)

Add `"text"` cell mode to every PNL/signed column in the remaining `table()` calls (Asset scorecard "Win rate"/"Net $", tradeability "Win rate"/"Net $"): change their 5-tuples to 6-tuples ending in `"text"`.

- [ ] **Step 8: Allow piechart in the panel-type test**

In `tests/test_trading_dashboard.py:152` change:

```python
    allowed = {"row", "stat", "table", "gauge", "timeseries", "bargauge",
               "text", "piechart"}
```

and update docstring point 4 (line 12-13) to: `4. only supported panel types (stat/state/table/gauge/bargauge/timeseries/piechart/text) — the deprecated "graph" plugin is never allowed.`

- [ ] **Step 9: Regenerate and run the suite**

Run: `python scripts/build_trading_dashboard.py && python -m pytest tests/test_glass_suite.py tests/test_trading_dashboard.py tests/test_telemetry_restart_coupling.py -q`
Expected: PASS (all glass-suite regressions now green; generator matches shipped).

- [ ] **Step 10: Commit**

```bash
git add -A && git commit -m "feat(grafana): glass kit — transparent panels, CSS injector, joined tables, basic bars

Structural fixes shared by all four boards: outer joinByField tables
(conditional per-position metrics no longer split rows or paint absent
cells alarm-red), basic-mode bar gauges, merged label selectors, markout
pivoted on horizon_sec, donut primitive, per-board dormant frosted-skin
injector."
```

---

### Task 3: Re-author the Command board

**Files:**
- Modify: `scripts/build_trading_dashboard.py` — replace `_author_command()` (lines 350-548) entirely; `_positions_table()` stays as Task 2 left it.
- Regenerate: the four JSONs.

**Interfaces:**
- Consumes: every Task 2 helper signature (see Task 2 Produces).
- Produces: nothing new for later tasks.

- [ ] **Step 1: Replace `_author_command()`**

```python
def _author_command():
    row("🫀 VITALS — alive & armed")
    state("Bot", M("liquiditybot_running"), 4, 4, UP_DOWN,
          desc="runner RUNNING.")
    state("Halted", M("liquiditybot_halted"), 4, 4, HALT, desc="Global halt.")
    state("Entries", M("liquiditybot_entries_enabled"), 4, 4, ON_OFF,
          desc="New-risk entries enabled (exits always allowed).")
    state("Kraken WS", M("liquiditybot_ws_kraken_connected"), 4, 4, WS,
          desc="Push book vs REST fallback.")
    stat("Telemetry age", M("liquiditybot_status_age_sec"), 4, 4, unit="s",
         decimals=0, mode="background", graph="none",
         steps=[{"color": "green", "value": None},
                {"color": "yellow", "value": 120},
                {"color": "red", "value": 300}],
         desc="Seconds since last status write.")
    state("Governor", M("liquiditybot_monitor_level"), 4, 4, GOV,
          desc="0 OK / 1 degraded / 2 killed.")
    stat("Feed latency", M("liquiditybot_feed_latency_ms"), 12, 3, unit="ms",
         decimals=0, steps=LAT, desc="Kraken public-GET RTT EWMA.")
    stat("Cycle", M("liquiditybot_cycle"), 12, 3, decimals=0, steps=BLUE,
         desc="Fast-cycle counter (advancing = alive).")

    row("💹 MONEY — equity & P&L")
    timeseries("Equity curve", M("liquiditybot_equity"), 12, 8,
               unit=USD, legend="equity", decimals=2,
               calcs=["lastNotNull", "min", "max"], colors={"equity": GREEN},
               desc="Account equity over time — exact dollars (no "
                    "K-rounding); the legend table shows last/min/max to "
                    "the cent.")
    stat("P&L today", M("liquiditybot_daily_pnl"), 6, 8, unit=USD,
         steps=PNL, desc="Realized P&L since UTC midnight.")
    stat("Open uPnL", M("liquiditybot_open_upnl_usd"), 6, 8, unit=USD,
         steps=PNL, desc="Unrealized across open positions.")
    stat("Equity", M("liquiditybot_equity"), 5, 5, unit=USD,
         decimals=2, steps=GRN, desc="Account equity (cash + open uPnL).")
    gauge("Drawdown", M("liquiditybot_drawdown_pct"), 5, 5, mx=15.0, steps=DD,
          desc="Peak-to-now; 15% is the hard stop.")
    gauge("Win rate", M("liquiditybot_perf_win_rate", "*100"), 5, 5, mx=100.0,
          steps=WR100, desc="Rolling closed-trade win rate.")
    stat("Profit factor", M("liquiditybot_perf_profit_factor"), 5, 5,
         decimals=2, steps=PF, desc="Gross profit / gross loss.")
    stat("Expectancy R", M("liquiditybot_perf_expectancy_r"), 4, 5, decimals=2,
         steps=PNL, desc="Avg trade in R-multiples.")

    row("🏦 PROFIT POOLS — weekly rollover")
    stat("P&L this week", M("liquiditybot_weekly_pnl"), 6, 5, unit=USD,
         steps=PNL, desc="Realized P&L since the ISO-week open (Mon 00:00 "
                         "UTC). Resets at the weekly close-out (RP-070); a "
                         "losing week is refilled from Reserve before the "
                         "working baseline shrinks.")
    stat("Savings pool", M("liquiditybot_savings"), 6, 5, unit=USD,
         decimals=2, steps=GRN,
         desc="20% of every realized win, locked away - never traded, "
              "never refilled from, only ever grows.")
    stat("Reserve pool", M("liquiditybot_reserve"), 6, 5, unit=USD,
         decimals=2, steps=GRN,
         desc="10% of every realized win - the drawdown shock absorber. "
              "At each weekly close a losing week's realized loss refills "
              "trading cash from here (reserve only ever moves INTO cash).")
    stat("Reinvested (cash)", "liquiditybot_equity" + A +
         " - liquiditybot_savings" + A + " - liquiditybot_reserve" + A, 6, 5,
         unit=USD, decimals=2, steps=GRN,
         desc="Working trading capital: equity minus the two locked pools "
              "- the 70% share that compounds position sizing.")
    timeseries("Pools over time",
               M("liquiditybot_savings"), 24, 7, unit=USD,
               legend="savings", decimals=2,
               calcs=["lastNotNull", "max"],
               extra=[(M("liquiditybot_reserve"), "reserve"),
                      (M("liquiditybot_weekly_pnl"), "weekly P&L")],
               colors={"savings": GREEN, "reserve": CAT_TEAL,
                       "weekly P&L": GRAY_HEX},
               desc="Savings + reserve accrual and the week's running "
                    "realized P&L - the rollover ritual made visible.")

    row("🧠 LEARNING BRAIN")
    timeseries("Learning rows by label (live vs candidate)",
               'max by (source) (liquiditybot_ml_labels' + JOB + ')', 12, 7,
               unit="short", legend="{{source}}",
               colors={"live": GREEN, "candidate": GRAY_HEX},
               desc="Ground-truth LIVE (real closed-trade) labels vs "
                    "CANDIDATE (triple-barrier proxy) labels accruing over "
                    "time — the learning loop turning. LIVE climbing past "
                    "35 = ML-073 realizing ground truth; a flat LIVE line "
                    "= the loop is starved.")
    timeseries("Brier — live vs champion vs baseline (lower = better)",
               M("liquiditybot_ml_brier"), 12, 7, legend="live",
               decimals=4, calcs=["lastNotNull"],
               extra=[(M("liquiditybot_ml_champion_brier"), "champion"),
                      (M("liquiditybot_ml_baseline_brier"), "baseline")],
               colors={"live": INDIGO, "champion": CAT_TEAL,
                       "baseline": CAT_PURPLE},
               desc="Rolling outcome Brier: live vs deployed champion vs "
                    "the base-rate baseline the model must undercut.")
    stat("Live labels",
         'max(liquiditybot_ml_labels{source="live",job="liquiditybot"})',
         4, 4, decimals=0, steps=[{"color": "red", "value": None},
         {"color": "yellow", "value": 30}, {"color": "green", "value": 60}],
         desc="Ground-truth closed-trade labels — earns model complexity.")
    stat("Candidate labels",
         'max(liquiditybot_ml_labels{source="candidate",job="liquiditybot"})',
         4, 4, decimals=0, steps=BLUE, desc="Triple-barrier proxy labels.")
    stat("Model", "count(liquiditybot_ml_model_info" + JOB + ") by (kind)",
         4, 4, desc="Deployed rung on the simplicity ladder.",
         text_mode="name", display_name="${__field.labels.kind}",
         steps=BLUE, graph="none")
    state("Model in use", M("liquiditybot_ml_use_model"), 4, 4, ON_OFF,
          desc="Governor lets the model size trades; NO is a stand-down, "
               "not a fault.")
    state("Retrain", M("liquiditybot_ml_retrain_flag"), 4, 4, RETRAIN,
          desc="Auto-retrain queued.")
    stat("Kelly mult", M("liquiditybot_ml_kelly_mult"), 4, 4, decimals=2,
         steps=GRN, desc="Governor size throttle.")
    stat("Calibration gap", M("liquiditybot_ml_calibration_gap"), 4, 4,
         decimals=3, steps=CALIB, desc="ECE; Kelly reads probs literally.")
    gauge("Drift share", M("liquiditybot_ml_drift_share", "*100"), 4, 4,
          mx=100.0, steps=[{"color": "green", "value": None},
          {"color": "yellow", "value": 30}, {"color": "red", "value": 50}],
          desc="Fraction of features past the PSI threshold.")
    stat("Win rate LCB", M("liquiditybot_perf_win_rate_lcb", "*100"), 4, 4,
         unit="percent", decimals=1, steps=GRN, desc="Wilson lower bound.")
    stat("Clean live labels", M("liquiditybot_ml_live_clean"), 4, 4,
         decimals=0, steps=[{"color": "red", "value": None},
         {"color": "yellow", "value": 30}, {"color": "green", "value": 60}],
         desc="Live rows surviving the hygiene pass — the count the "
              "evidence gate actually admits model complexity on.")
    stat("Label uniqueness", M("liquiditybot_ml_mean_uniqueness"), 4, 4,
         decimals=3, steps=[{"color": "red", "value": None},
         {"color": "yellow", "value": 0.05}, {"color": "green", "value": 0.15}],
         desc="Mean average-uniqueness (AFML ch.4): 1 = every label an "
              "independent fact; near 0 = heavily overlapping horizons "
              "(weights redistribute so overlap can't double-count).")
    state("Batch prior skew", M("liquiditybot_ml_prior_skew"), 4, 4,
          {"0": ("OK", "green"), "1": ("SKEWED", "yellow")},
          no_value="no batch yet",
          desc="ML-074: trailing-window label prior vs corpus prior — "
               "SKEWED = a one-sided batch (e.g. all-zero quiet weekend) "
               "is moving calibration; detection only, weights untouched.")

    row("⚖️ EDGE — per-asset performance")
    bargauge("Net $ by asset", _pa("liquiditybot_perf_asset_net_usd"), 8, 8,
             unit=USD, decimals=2, steps=PNL, mn=-12, mx=12,
             desc="Realized net per asset — where P&L actually comes from.")
    bargauge("Signal concentration", _pa("liquiditybot_signal_concentration"),
             8, 8, decimals=2, steps=HIGH_GOOD, mn=0, mx=1,
             desc="0 diffuse average .. 1 pinpointed setup.")
    bargauge("Confidence", _pa("liquiditybot_signal_confidence"), 8, 8,
             decimals=2, steps=HIGH_GOOD, mn=0, mx=1,
             desc="Model conviction per asset.")
    table("Asset scorecard", 24, 8,
          cols=[("liquiditybot_perf_asset_win_rate", "Win rate", "percentunit", 2, WRU, "text"),
                ("liquiditybot_perf_asset_net_usd", "Net $", USD, 2, PNL, "text"),
                ("liquiditybot_perf_asset_trades", "Trades", "short", 0),
                ("liquiditybot_perf_asset_cur_loss_streak", "Loss streak", "short", 0, STREAK),
                ("liquiditybot_signal_confidence", "Confidence", "short", 2, HIGH_GOOD),
                ("liquiditybot_signal_concentration", "Concentration", "short", 2, HIGH_GOOD),
                ("liquiditybot_signal_urgency", "Urgency", "short", 2),
                ("liquiditybot_manip_suspect", "Manip", "short", 2, LOW_GOOD),
                ("liquiditybot_regime_spread_bps", "Spread bps", "short", 1, SPREAD),
                ("liquiditybot_regime_vol_pct", "Vol %", "percent", 1)],
          label_keys=["asset"], sort="Net $",
          desc="One row per asset; color-coded so a green row (positive "
               "net, high concentration, low manip, tight spread) reads "
               "instantly. Absent cells (·) mean the asset hasn't traded "
               "yet — not a fault.")

    row("🏛️ THALES — footprint & manipulation defense")
    text("What THALES is", _THALES_MD, 8, 9)
    table("THALES detector scorecard (higher = more suspicious)", 16, 9,
          cols=[("liquiditybot_thales_grid", "Grid", "short", 2, LOW_GOOD),
                ("liquiditybot_thales_metronome", "Metronome", "short", 2, LOW_GOOD),
                ("liquiditybot_thales_clockwork", "Clockwork", "short", 2, LOW_GOOD),
                ("liquiditybot_thales_stop_zone", "Stop-zone", "short", 2, LOW_GOOD),
                ("liquiditybot_thales_barclose", "Bar-close", "short", 2, LOW_GOOD),
                ("liquiditybot_thales_spoof_bid", "Spoof bid", "short", 2, LOW_GOOD),
                ("liquiditybot_thales_spoof_ask", "Spoof ask", "short", 2, LOW_GOOD),
                ("liquiditybot_thales_feed_dirty", "Feed dirty", "short", 2, LOW_GOOD),
                ("liquiditybot_thales_lapses", "Lapses", "short", 0, STREAK),
                ("liquiditybot_thales_bar_holes", "Bar holes", "short", 0, STREAK)],
          label_keys=["asset"], sort="Spoof bid",
          desc="Per-asset footprint scores (0-1) + feed-integrity "
               "counters. THALES only ATTENUATES (shade size / down-weight "
               "the training row) — it never triggers a trade.")
    bargauge("Spoof-flicker pressure (bid)",
             _pa("liquiditybot_thales_spoof_bid"), 8, 6, decimals=2,
             steps=LOW_GOOD, mn=0, mx=1, legend="{{asset}}",
             desc="TH-017 spoof EWMA per asset — higher = a book being "
                  "painted; THALES shades size there.")
    bargauge("Stop-hunt zone proximity", _pa("liquiditybot_thales_stop_zone"),
             8, 6, decimals=2, steps=LOW_GOOD, mn=0, mx=1, legend="{{asset}}",
             desc="Proximity to round-number stop clusters per asset.")
    bargauge("Manipulation suspicion", _pa("liquiditybot_manip_suspect"),
             8, 6, decimals=2, steps=LOW_GOOD, mn=0, mx=1, legend="{{asset}}",
             desc="Parameter-free max of the manipulation footprints per "
                  "asset.")

    row("🛡️ POSITIONS & RISK")
    _positions_table()
    stat("Loss streak (now)", M("liquiditybot_perf_cur_loss_streak"), 4, 5,
         decimals=0, steps=STREAK, graph="none", mode="background",
         desc="Consecutive losers now — circuit-breaker input.")
    stat("Open risk", M("liquiditybot_open_risk_usd"), 4, 5, unit=USD,
         steps=GRN, desc="$ lost if every open stop filled now.")
    stat("Trades (window)", M("liquiditybot_perf_trades"), 4, 5, decimals=0,
         steps=BLUE, desc="Closed trades in the window.")
    table("Entry-decision reason codes", 6, 5,
          cols=[("liquiditybot_code_count_detail", "Count", "short", 0, BLUE)],
          label_keys=["code"], sort="Count", desc="Why entries fired/vetoed.")
    table("Learned gate weights", 6, 5,
          cols=[("liquiditybot_gate_weight", "Weight", "short", 3, HIGH_GOOD)],
          label_keys=["gate"], sort="Weight", desc="Evidence weight per gate.")
    gauge("Gross exposure", M("liquiditybot_gross_exposure_pct"), 6, 5,
          mx=35.0, desc="Gross notional %/equity vs the 35% heat cap.")
    stat("Positions open", M("liquiditybot_positions_open"), 6, 5, decimals=0,
         steps=BLUE, graph="none", desc="Open count (max 5).")
```

- [ ] **Step 2: Regenerate and run the suite**

Run: `python scripts/build_trading_dashboard.py && python -m pytest tests/test_glass_suite.py tests/test_trading_dashboard.py tests/test_telemetry_restart_coupling.py -q`
Expected: PASS. If `test_importable_shape_and_layout_per_board` reports overlapping panels, fix widths/heights in the author until green — the layout engine wraps rows automatically; overlaps mean two calls in one visual line disagree on height.

- [ ] **Step 3: Commit**

```bash
git add -A && git commit -m "feat(grafana): re-author Command board in the glass language

VITALS state strip, money row with full-width pools chart, learning
brain with the Brier trio as one comparison chart, merged label
selectors, model-kind display name, honest prior-skew empty state."
```

---

### Task 4: Re-author the Models·Inv·Exec board

**Files:**
- Modify: `scripts/build_trading_dashboard.py` — replace `_author_execution()` entirely.
- Regenerate: the four JSONs.

**Interfaces:**
- Consumes: Task 2 helpers, `_positions_table()`.
- Produces: nothing new. MUST keep ≥3 `no_value="no fills yet"` and exactly the string `"flat — no open positions"` on the uPnL bargauge (pinned).

- [ ] **Step 1: Replace `_author_execution()`**

```python
def _author_execution():
    row("🧠 DECISION MODEL")
    stat("Model", "count(liquiditybot_ml_model_info" + JOB + ") by (kind)",
         4, 5, text_mode="name", steps=BLUE, graph="none",
         display_name="${__field.labels.kind}",
         desc="Deployed rung (evidence-gated).")
    state("Model in use", M("liquiditybot_ml_use_model"), 4, 5, ON_OFF,
          desc="Model sizes trades vs the cold-start prior; NO is a "
          "stand-down, not a fault.")
    state("Governor", M("liquiditybot_monitor_level"), 4, 5, GOV,
          desc="0 OK / 1 degraded / 2 killed.")
    gauge("Calibration gap", M("liquiditybot_ml_calibration_gap"), 4, 5,
          mx=0.2, decimals=3, steps=CALIB, desc="ECE; keep small — Kelly "
          "reads probs literally.")
    gauge("Drift share", M("liquiditybot_ml_drift_share", "*100"), 4, 5,
          mx=100.0, steps=[{"color": "green", "value": None},
          {"color": "yellow", "value": 30}, {"color": "red", "value": 50}],
          desc="Feature PSI drift fraction.")
    stat("Kelly mult", M("liquiditybot_ml_kelly_mult"), 4, 5, decimals=2,
         steps=GRN, desc="Size throttle.")
    timeseries("Brier — live vs champion vs baseline (lower = better)",
               M("liquiditybot_ml_brier"), 12, 6, legend="live",
               decimals=4, calcs=["lastNotNull"],
               extra=[(M("liquiditybot_ml_champion_brier"), "champion"),
                      (M("liquiditybot_ml_baseline_brier"), "baseline")],
               colors={"live": INDIGO, "champion": CAT_TEAL,
                       "baseline": CAT_PURPLE},
               desc="Rolling outcome Brier: live vs deployed champion vs "
               "the base-rate baseline. Lower is better.")
    stat("Live labels",
         'max(liquiditybot_ml_labels{source="live",job="liquiditybot"})',
         4, 6, decimals=0, steps=[{"color": "red", "value": None},
         {"color": "yellow", "value": 30}, {"color": "green", "value": 60}],
         desc="Ground truth that earns model complexity.")
    stat("Shrinkage", M("liquiditybot_ml_shrinkage"), 4, 6, decimals=2,
         steps=GRN, desc="Shrink toward base rate.")
    stat("Stop widen", M("liquiditybot_ml_stop_widen"), 4, 6, decimals=2,
         steps=GRN, desc="Governor stop-distance multiplier.")
    bargauge("Promised vs delivered (hit rate)",
             _pa("liquiditybot_ml_hit_rate", "*100"), 8, 5, unit="percent",
             decimals=1, steps=WR100, legend="{{asset}}",
             desc="Delivered win rate on the judge window.")
    table("Per-asset signal quality", 8, 5,
          cols=[("liquiditybot_signal_confidence", "Confidence", "short", 2, HIGH_GOOD),
                ("liquiditybot_signal_concentration", "Concentration", "short", 2, HIGH_GOOD),
                ("liquiditybot_signal_urgency", "Urgency", "short", 2),
                ("liquiditybot_manip_suspect", "Manip", "short", 2, LOW_GOOD)],
          label_keys=["asset"], sort="Concentration",
          desc="Signal decision quality per asset.")
    table("Learned gate weights", 8, 5,
          cols=[("liquiditybot_gate_weight", "Weight", "short", 3, HIGH_GOOD)],
          label_keys=["gate"], sort="Weight", desc="Evidence weight per gate.")

    row("📦 INVENTORY & POSITIONING")
    gauge("Gross exposure", M("liquiditybot_gross_exposure_pct"), 4, 5,
          mx=35.0, desc="Gross notional %/equity vs the 35% heat cap.")
    gauge("Portfolio heat", M("liquiditybot_rp_heat_frac", "*100"), 4, 5,
          mx=35.0, desc="CVaR portfolio heat vs cap.")
    stat("Open positions", M("liquiditybot_positions_open"), 4, 5, decimals=0,
         steps=BLUE, desc="Open count (max 5).")
    stat("Open risk", M("liquiditybot_open_risk_usd"), 4, 5, unit=USD,
         steps=GRN, desc="$ at risk to stops.")
    stat("Open uPnL", M("liquiditybot_open_upnl_usd"), 4, 5, unit=USD,
         steps=PNL, desc="Unrealized across positions.")
    stat("Gross exposure $", M("liquiditybot_gross_exposure_usd"), 4, 5,
         unit=USD, decimals=0, steps=GRN, desc="Gross notional $.")
    _positions_table()
    bargauge("uPnL by instrument", _pa("liquiditybot_position_upnl_usd"), 12, 5,
             unit=USD, decimals=2, steps=PNL, legend="{{symbol}} {{side}}",
             no_value="flat — no open positions",
             desc="Unrealized P&L ranked across open instruments.")

    row("⚡ EXECUTION QUALITY")
    donut("Maker / taker mix", [
          (M("liquiditybot_order_maker_share"), "maker"),
          ("1 - " + M("liquiditybot_order_maker_share"), "taker")],
          6, 6, colors={"maker": CAT_TEAL, "taker": CAT_PURPLE},
          no_value="no fills yet",
          desc="Fill composition — maker is the cheap side; the exit "
               "ladder's final rung is the only taker path.")
    bargauge("Slippage vs arrival (bps)",
             M("liquiditybot_order_avg_slip_bps"), 6, 6, unit="short",
             decimals=1, steps=SLIP, legend="avg",
             extra=[(M("liquiditybot_order_worst_slip_bps"), "worst")],
             no_value="no fills yet",
             desc="Implementation shortfall vs the ARRIVAL mark (positive "
                  "= paid worse than arrival; negative = improvement).")
    bargauge("Fills — maker vs taker",
             M("liquiditybot_order_maker_fills"), 6, 6, decimals=0,
             steps=GRN, legend="maker fills",
             extra=[(M("liquiditybot_order_taker_fills"), "taker fills")],
             no_value="no fills yet",
             desc="Fill counts in the window; taker fills are exit-ladder "
                  "rungs.")
    bargauge("Notional — maker vs taker ($)",
             M("liquiditybot_order_maker_notional_usd"), 6, 6, unit=USD,
             decimals=0, steps=GRN, legend="maker $",
             extra=[(M("liquiditybot_order_taker_notional_usd"), "taker $")],
             no_value="no fills yet",
             desc="Filled notional split by liquidity side.")
    stat("Venue RTT", M("liquiditybot_order_latency_ms"), 6, 4, unit="ms",
         decimals=0, steps=LAT, desc="Private POST RTT (order path).")
    stat("Venue rejects", M("liquiditybot_order_venue_rejects"), 6, 4,
         decimals=0, steps=STREAK, graph="none", mode="background",
         desc="OM-021 AddOrder rejects.")
    stat("Dead-man failures", M("liquiditybot_order_deadman_failures"), 6, 4,
         decimals=0, steps=ZERO_BAD, graph="none", mode="background",
         desc="OM-050 refresh failures — resting orders unguarded.")
    gauge("Maker share", M("liquiditybot_order_maker_share", "*100"), 6, 4,
          mx=100.0, steps=[{"color": "red", "value": None},
          {"color": "yellow", "value": 60}, {"color": "green", "value": 80}],
          no_value="no fills yet",
          desc="% fills that were maker (cheaper).")
    table("Post-fill mark-out (adverse selection)", 24, 6,
          cols=[('liquiditybot_markout_bps{job="liquiditybot",horizon_sec="5"}',
                 "5s bps", "short", 2, PNL, "text"),
                ('liquiditybot_markout_bps{job="liquiditybot",horizon_sec="30"}',
                 "30s bps", "short", 2, PNL, "text"),
                ('liquiditybot_markout_bps{job="liquiditybot",horizon_sec="60"}',
                 "60s bps", "short", 2, PNL, "text")],
          label_keys=["asset"], sort="5s bps",
          desc="Price drift after our fill at 5/30/60s per asset; "
               "persistently negative = picked off. Absent cells (·) = no "
               "fills measured at that horizon yet.")
```

- [ ] **Step 2: Regenerate and run the suite (including the noValue pins)**

Run: `python scripts/build_trading_dashboard.py && python -m pytest tests/test_glass_suite.py tests/test_trading_dashboard.py tests/test_telemetry_restart_coupling.py -q`
Expected: PASS — `test_sparse_panels_declare_honest_empty_states` counts 5× `"no fills yet"` (donut, 3 bargauges, maker-share gauge ≥ pinned 3) and the exact uPnL string.

- [ ] **Step 3: Commit**

```bash
git add -A && git commit -m "feat(grafana): re-author Models-Inv-Exec board in the glass language

Maker/taker donut, avg-vs-worst slippage bars, fills/notional split
bars, full-width mark-out pivot on horizon_sec, honest empty states
preserved."
```

---

### Task 5: Re-author the Problem/Solution board

**Files:**
- Modify: `scripts/build_trading_dashboard.py` — replace `_author_problem()` entirely.
- Regenerate: the four JSONs.

**Interfaces:**
- Consumes: Task 2 helpers.
- Produces: nothing new. Consolidation rule: STATES stay tiles; scalar COUNTER walls become one multi-target ranked bargauge per family; every metric keeps its PROBLEM/SOLUTION description.

- [ ] **Step 1: Replace `_author_problem()`**

```python
def _author_problem():
    text("", "**Incident board — a calm board is all green.** Every tile is "
             "a PROBLEM paired with the SOLUTION that fires automatically; "
             "any non-zero / amber / red panel is a live incident worth a "
             "look. Counter families are ranked bars — the tallest bar is "
             "the incident. Refresh 30s · window 24h.", 24, 3)
    row("📡 FEED & DATA INTEGRITY")
    stat("Stale status", M("liquiditybot_status_age_sec"), 4, 5, unit="s",
         decimals=0, mode="background", graph="none",
         steps=[{"color": "green", "value": None},
                {"color": "yellow", "value": 120},
                {"color": "red", "value": 300}],
         desc="PROBLEM: runner frozen. SOLUTION: wedge-guard escalates; "
              "supervisor revives a dead runner.")
    state("Kraken WS", M("liquiditybot_ws_kraken_connected"), 4, 5, WS,
          desc="SOLUTION: on drop the engine falls back to REST — trading "
               "continues.")
    stat("Stale marks", M("liquiditybot_marks_age_sec"), 4, 5, unit="s",
         decimals=0, mode="background", graph="none",
         steps=[{"color": "green", "value": None},
                {"color": "yellow", "value": 30},
                {"color": "red", "value": 90}],
         desc="PROBLEM: old prices. SOLUTION: mark-freshness gate holds "
              "non-escape risk; stops still run.")
    bargauge("Watchdog — blocked / stale / divergent",
             M("liquiditybot_watchdog_entries_blocked"), 12, 5, decimals=0,
             steps=ZERO_BAD, legend="entries blocked",
             extra=[(M("liquiditybot_watchdog_stale_assets"), "stale assets held"),
                    (M("liquiditybot_watchdog_divergent"), "divergent feeds")],
             desc="PROBLEM: rotten feed. SOLUTION: the watchdog quarantines "
                  "stale assets and blocks new entries until the feed "
                  "heals; exits always run. Any bar above zero is a "
                  "solution actively firing.")

    row("🧠 MODEL HEALTH")
    stat("PROBLEM: model Brier", M("liquiditybot_ml_brier"), 4, 5, decimals=4,
         mode="background", graph="none", steps=BRIER,
         desc="Detector. SOLUTION: the governor kills the model + queues a "
              "retrain when Brier crosses baseline.")
    stat("vs baseline", M("liquiditybot_ml_baseline_brier"), 4, 5, decimals=4,
         steps=GRN, graph="none", desc="The bar Brier must stay under.")
    state("SOLUTION: governor", M("liquiditybot_monitor_level"), 4, 5, GOV,
          desc="0 OK / 1 shrink+throttle / 2 model killed to the prior.")
    state("SOLUTION: retrain", M("liquiditybot_ml_retrain_flag"), 4, 5,
          RETRAIN, desc="Auto-retrain queued to replace a degrading "
          "champion.")
    gauge("Drift share", M("liquiditybot_ml_drift_share", "*100"), 4, 5,
          mx=100.0, steps=[{"color": "green", "value": None},
          {"color": "yellow", "value": 30}, {"color": "red", "value": 50}],
          desc="PROBLEM: input drift. SOLUTION: retrain re-fits.")
    stat("Calibration gap", M("liquiditybot_ml_calibration_gap"), 4, 5,
         decimals=3, mode="background", graph="none", steps=CALIB,
         desc="Miscalibration; ECE.")
    bargauge("Fail-safe counters (any bar = a guard firing)",
             M("liquiditybot_ml_model_fallbacks"), 12, 6, decimals=0,
             steps=STREAK, legend="model fallbacks",
             extra=[(M("liquiditybot_ml_infer_faults"), "infer faults"),
                    (M("liquiditybot_ml_contract_failed"), "contract fails"),
                    (M("liquiditybot_ml_retrain_failures"), "retrain failures"),
                    (M("liquiditybot_ml_dropped_dirty"), "dirty rows dropped")],
             desc="PROBLEM: inference/training faults. SOLUTION: every "
                  "fault path falls back to the prior (fail-safe), dirty "
                  "rows are dropped before they NaN a fit (ML-015).")
    stat("Kelly throttle", M("liquiditybot_ml_kelly_mult"), 6, 6, decimals=2,
         steps=GRN, graph="none", desc="SOLUTION: size shrinks as "
         "confidence falls.")
    stat("Twin rows excluded", M("liquiditybot_ml_dropped_clash"), 6, 6,
         decimals=0, graph="none", steps=BLUE,
         desc="Synthetic candidate twins of REAL trades excluded so a "
              "taken signal is never double-counted (realized label kept). "
              "Nonzero is healthy — it tracks taken teach-trades.")

    row("💰 CAPITAL & DRAWDOWN")
    gauge("PROBLEM: drawdown", M("liquiditybot_drawdown_pct"), 5, 6, mx=15.0,
          steps=DD, desc="SOLUTION: drawdown throttle + 15% hard-stop "
          "flatten.")
    stat("Loss streak", M("liquiditybot_perf_cur_loss_streak"), 4, 6,
         decimals=0, mode="background", graph="none", steps=STREAK,
         desc="PROBLEM: consecutive losers. SOLUTION: per-asset circuit "
              "breaker.")
    stat("Breakers tripped", M("liquiditybot_cb_tripped_count"), 3, 6,
         decimals=0, mode="background", graph="none", steps=ZERO_BAD,
         desc="Assets currently paused.")
    gauge("Heat vs cap", M("liquiditybot_rp_heat_frac", "*100"), 4, 6,
          mx=35.0, desc="SOLUTION: heat throttled under the CVaR cap.")
    stat("Taper mult", M("liquiditybot_rp_taper_mult"), 4, 6, decimals=2,
         steps=GRN, desc="SOLUTION: loss-budget taper shrinks size.")
    gauge("Daily budget used",
          M("liquiditybot_rp_daily_budget_used_frac", "*100"), 4, 6,
          mx=100.0, steps=BUDGET, desc="Daily loss budget consumed.")
    gauge("Weekly budget used",
          M("liquiditybot_rp_weekly_budget_used_frac", "*100"), 12, 5,
          mx=100.0, steps=BUDGET, desc="Weekly loss budget consumed.")
    table("Circuit breaker — paused assets", 12, 5,
          cols=[("liquiditybot_cb_loss_streak", "Loss streak", "short", 0, STREAK),
                ("liquiditybot_cb_paused_hours_left", "Hours left", "short", 1, BLUE)],
          label_keys=["asset"], sort="Loss streak",
          desc="Per-asset breaker state; hours-left counts the cool-off.")

    row("🕵️ MANIPULATION, VENUE & INTEGRITY")
    state("op-state", M("liquiditybot_op_state"), 4, 5, OPSTATE,
          desc="Central fault authority: ARMED / DEGRADED / HALTED.")
    state("Firewall fault", M("liquiditybot_firewall_fault"), 4, 5, HALT,
          desc="Risk-firewall latched fault (blocks new risk).")
    bargauge("Integrity counters (any bar = an incident)",
             M("liquiditybot_fault_count"), 16, 5, decimals=0,
             steps=ZERO_BAD, legend="latched faults",
             extra=[(M("liquiditybot_cycle_consecutive_failures"), "cycle wedge"),
                    (M("liquiditybot_exit_eval_failures"), "exit-eval failures"),
                    (M("liquiditybot_order_venue_rejects"), "venue rejects")],
             desc="PROBLEM: wedged cycles / unguarded exits / venue "
                  "rejects. SOLUTION: runner wedge escalation, exit-path "
                  "isolation, OM-021 reject handling.")
    bargauge("Manipulation suspicion by asset",
             _pa("liquiditybot_manip_suspect"), 12, 6, decimals=2,
             steps=LOW_GOOD, mn=0, mx=1,
             desc="PROBLEM: painted/spoofed books. SOLUTION: THALES shades "
                  "size + down-weights those training rows.")
    table("Firewall clamps/rejects by code", 12, 6,
          cols=[("liquiditybot_firewall_count", "Count", "short", 0, STREAK)],
          label_keys=["code"], sort="Count",
          desc="Which firewall rule (FW-*) is clamping most.")
```

- [ ] **Step 2: Regenerate and run the suite**

Run: `python scripts/build_trading_dashboard.py && python -m pytest tests/test_glass_suite.py tests/test_trading_dashboard.py tests/test_telemetry_restart_coupling.py -q`
Expected: PASS. Metric check: every metric from the old board still appears (`watchdog_entries_blocked/stale_assets/divergent`, `ml_model_fallbacks/infer_faults/contract_failed/retrain_failures/dropped_dirty/dropped_clash`, `fault_count/cycle_consecutive_failures/exit_eval_failures/order_venue_rejects` — now inside the family bargauges).

- [ ] **Step 3: Commit**

```bash
git add -A && git commit -m "feat(grafana): re-author Problem/Solution board in the glass language

States stay tiles; the six-tile counter walls become one ranked
fail-safe bargauge per family (feed, model, integrity) — same metrics,
the tallest bar IS the incident."
```

---

### Task 6: Re-author the Screening board

**Files:**
- Modify: `scripts/build_trading_dashboard.py` — replace `_author_screening()` entirely.
- Regenerate: the four JSONs.

**Interfaces:**
- Consumes: Task 2 helpers.
- Produces: nothing new.

- [ ] **Step 1: Replace `_author_screening()`**

```python
def _author_screening():
    row("🔎 SKIMMER — candidate universe")
    stat("Candidates scanned", M("liquiditybot_skimmer_candidates"), 5, 5,
         decimals=0, steps=BLUE, desc="Off-universe pairs ranked.")
    stat("Promoted", M("liquiditybot_skimmer_promoted_count"), 5, 5,
         decimals=0, steps=GRN, desc="Pairs promoted into the tradeable "
         "set.")
    stat("Open slots", M("liquiditybot_positions_open"), 4, 5, decimals=0,
         steps=BLUE, desc="Slots in use (max 5).")
    gauge("Exposure headroom", M("liquiditybot_gross_exposure_pct"), 5, 5,
          mx=35.0, desc="Room left under the heat cap for a new name.")
    state("Model sizing", M("liquiditybot_ml_use_model"), 5, 5,
          {"1": ("MODEL", "green"), "0": ("PRIOR", "yellow")},
          desc="Whether promotions are sized by the model or the "
               "cold-start prior (PRIOR is a stand-down, not a fault).")
    bargauge("Skimmer score (higher = better book)",
             _pa("liquiditybot_skimmer_score"), 12, 8, decimals=3,
             steps=HIGH_GOOD, mn=0, mx=1, legend="{{pair}}",
             desc="Composite liquidity/spread/depth score per candidate "
                  "pair.")
    table("Promoted pairs", 12, 8,
          cols=[("liquiditybot_skimmer_promoted_info", "Promoted", "short", 0, GRN)],
          label_keys=["pair"], sort="Promoted",
          desc="Pairs currently promoted into the tradeable universe.")

    row("📋 TRADEABILITY SCORECARD")
    table("Screen — book & regime vs signal & result", 24, 9,
          cols=[("liquiditybot_regime_spread_bps", "Spread bps", "short", 1, SPREAD),
                ("liquiditybot_regime_vol_pct", "Vol %", "percent", 1),
                ("liquiditybot_regime_spoof", "Spoof", "short", 2, LOW_GOOD),
                ("liquiditybot_manip_suspect", "Manip", "short", 2, LOW_GOOD),
                ("liquiditybot_signal_confidence", "Confidence", "short", 2, HIGH_GOOD),
                ("liquiditybot_signal_concentration", "Concentration", "short", 2, HIGH_GOOD),
                ("liquiditybot_signal_urgency", "Urgency", "short", 2),
                ("liquiditybot_perf_asset_win_rate", "Win rate", "percentunit", 2, WRU, "text"),
                ("liquiditybot_perf_asset_net_usd", "Net $", USD, 2, PNL, "text"),
                ("liquiditybot_perf_asset_trades", "Trades", "short", 0)],
          label_keys=["asset"], sort="Net $",
          desc="Screen an asset in one row: tight spread + low spoof/manip "
               "+ high concentration + positive net = a tradeable edge. "
               "Absent cells (·) mean the asset hasn't traded yet — not a "
               "fault.")

    row("🌡️ REGIME CONTEXT & ADVERSE SELECTION")
    bargauge("Spread by asset (bps, lower = tighter book)",
             _pa("liquiditybot_regime_spread_bps"), 8, 7, decimals=1,
             steps=SPREAD, desc="Cost of crossing; the screen's first "
             "filter.")
    bargauge("Volatility by asset (%)", _pa("liquiditybot_regime_vol_pct"),
             8, 7, unit="percent", decimals=1, steps=BLUE,
             desc="Realized vol regime per asset.")
    table("Adverse selection (mark-out)", 8, 7,
          cols=[('liquiditybot_markout_bps{job="liquiditybot",horizon_sec="5"}',
                 "5s bps", "short", 2, PNL, "text"),
                ('liquiditybot_markout_bps{job="liquiditybot",horizon_sec="30"}',
                 "30s bps", "short", 2, PNL, "text"),
                ('liquiditybot_markout_bps{job="liquiditybot",horizon_sec="60"}',
                 "60s bps", "short", 2, PNL, "text")],
          label_keys=["asset"], sort="5s bps",
          desc="Post-fill drift; persistently negative = the book picks us "
               "off — screen it down.")
```

- [ ] **Step 2: Regenerate and run the suite**

Run: `python scripts/build_trading_dashboard.py && python -m pytest tests/test_glass_suite.py tests/test_trading_dashboard.py tests/test_telemetry_restart_coupling.py -q`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add -A && git commit -m "feat(grafana): re-author Screening board in the glass language

Model-sizing tile reads MODEL/PRIOR instead of the giant lowercase
'prior'; tradeability + mark-out tables on the outer-join recipe."
```

---

### Task 7: Full battery, import, retire uids, deploy

**Files:**
- No source changes expected (fix-forward if the battery finds any).

**Interfaces:**
- Consumes: everything above.
- Produces: the deployed suite.

- [ ] **Step 1: Run the full CLAUDE.md battery**

```bash
python -m pytest tests/ -q
python scripts/smoke_test.py
python scripts/assurance_check.py
python scripts/overfit_check.py
ruff check core data execution ml risk regime strategies sentiment api main.py runner.py tests scripts/quant_trials.py scripts/overfit_check.py
pyright core data execution ml risk regime strategies sentiment api main.py runner.py
bandit -c pyproject.toml -r . -x ./.venv,./tests
python -m compileall -q . -x '.venv'
```

Expected: all green (overfit's pre-existing data-thinness baseline counts as its known-green state). Fix anything red before proceeding.

- [ ] **Step 2: Import the four boards and delete the retired uids**

```bash
GRAFANA_SA_TOKEN=$(cat ~/.liquiditybot/grafana-sa-token) .venv/bin/python scripts/grafana_import.py
for uid in liquiditybot-glass liquiditybot-glass-mobile; do
  curl -sS -X DELETE -H "Authorization: Bearer $(cat ~/.liquiditybot/grafana-sa-token)" \
    "https://goldsavanna1216.grafana.net/api/dashboards/uid/$uid"; echo
done
```

Expected: four `OK` import lines; the DELETEs return `{"title":...,"message":"Dashboard ... deleted"}` or a 404 body for the already-deleted mobile board (both acceptable).

- [ ] **Step 3: Push branch and fast-forward main (the PC's deploy channel)**

```bash
git push -u origin claude/remote-control-e3h815
git push origin HEAD:main
```

(Retry each up to 4 times with 2s/4s/8s/16s backoff only on network failure.)
Expected: both accepted; the PC's auto-updater battery-gates the commit and self-deploys.

- [ ] **Step 4: Confirm and hand back**

Verify the deploy landed: `git fetch origin paper-telemetry && git show origin/paper-telemetry:control/pc_status.json` (within ~15 min shows the new rev). Then ask the operator for one screenshot pass of the four boards.
