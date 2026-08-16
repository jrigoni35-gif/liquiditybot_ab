"""scripts/build_trading_dashboard.py — generator for the trading dashboards.

THIS GENERATOR IS THE SOURCE OF TRUTH: edit here and regenerate; never
hand-edit the JSONs. tests/test_trading_dashboard.py enforces (1) generator ==
shipped JSON, (2) importable shape / no overlapping panels, (3) every metric a
panel queries is emitted by scripts/gc_pusher.py, (4) only supported panel
types.

STRIPPED 2026-08-15. Every visualization panel was deleted from all four
boards before the newly-configured bot produced real data, so that nothing on
screen could be a number carried over from the retired geometry. ONE board was
then rebuilt small — see the stub block at "board 1 · command". The Liquid
Glass FRAMEWORK is untouched: GLASS_RULES + _injector() (the frosted skin),
_apple_palette()/_hig_all(), and every panel factory below
(row/stat/state/gauge/timeseries/bargauge/donut/table/text) with its threshold
palettes. A board is rebuilt by writing constructor calls into its _author_
stub; nothing else has to be restored first. See docs/grafana/README_glass.md.

DESIGN — the rules the rebuilt board follows, and that a future one should:
  * ACCURACY FIRST. Two rules, and they do NOT have the same force — the
    difference is stated because claiming otherwise is how a false assurance
    gets written into a permanent file:
      ENFORCED. tests/test_trading_dashboard.py::
      test_every_query_hits_an_emitted_metric rejects any panel querying a
      metric scripts/gc_pusher.py never emits. Never add a panel from memory
      of another board — three plausible names (liquiditybot_open_positions,
      _win_rate, _cash) do NOT exist.
      CONVENTION ONLY, nothing tests it (verified 2026-08-15 by mutation:
      changing USD to "currencyUSD" and regenerating left the suite fully
      green). Every money panel must use the non-scaling USD unit so the
      number displayed IS the number the bot holds — Grafana's currencyUSD
      SI-abbreviates at >=$1k and renders $4,997.92 as "$5.00K". Held by
      review, not by the battery; if you add a money panel, check it.
  * one purpose per board, most-important top-left, no orphan queries;
  * a THREE-TIER type scale only (hero/normal/compact, see _SIZES) so the
    hierarchy is authored rather than an accident of Grafana's auto-fit;
  * KPI tiles are stat panels with an area sparkline and threshold color;
  * bounded ratios (exposure, drawdown) are GAUGES;
  * dense detail lives in color-coded TABLES, which render "·" for absent
    cells — absence is often the truth and must not read as "No data";
  * live STATE readouts are colored tiles;
  * telemetry age belongs on the front page: if it climbs, every other number
    on the board is a fossil.

Boards:
  liquiditybot_command.json          — LIQUIDITY BOARD, the at-a-glance read
  liquiditybot_execution.json        — models · inventory · execution (EMPTY)
  liquiditybot_problem_solution.json — problem / solution diagnostics (EMPTY)
  liquiditybot_screening.json        — asset screening (EMPTY)
"""
import json
import re
from pathlib import Path

DS = {"type": "prometheus", "uid": "grafanacloud-prom"}

# Longest gap a timeseries line may be drawn ACROSS, in milliseconds.
# gc_pusher exports every 30s (GC_PERIOD_SEC), so 5 min is 10x cadence:
# generous enough that a routine restart or a deploy's test-gate pause
# stays one continuous line, decisive enough that real downtime reads as
# a hole. `spanNulls: True` (the old value) connects ANY gap, which is
# how the 2026-07-26 outage rendered: the bot was dark 03:05->14:55 UTC
# and the equity + Brier panels drew smooth glides straight through the
# dead air — an 11.8h hole that looked like a gentle trend, on the same
# board where Feed latency (a `stat` sparkline, which never spanned)
# showed the break honestly. A monitoring board that turns "the bot was
# down" into "a mild decline" is worse than no board.
SPAN_NULLS_MS = 300_000

# Plain-language decode for every reason code that renders on a panel
# ("decode them", 2026-07-25). Keys are the literal code strings from
# core/codes.py; tests/test_trading_dashboard.py enforces FULL coverage of
# the SZ / CV / PT families against core.codes.Code, so adding a code
# without a label breaks the build instead of shipping a raw code to the
# operator. Labels keep the code as prefix — the audit trail speaks codes.
CODE_LABELS = {
    "SZ-000": "SZ-000 · entry approved",
    "SZ-010": "SZ-010 · invalid inputs",
    "SZ-020": "SZ-020 · cooldown active",
    "SZ-021": "SZ-021 · regime blocked",
    "SZ-022": "SZ-022 · direction blocked",
    "SZ-023": "SZ-023 · win-prob below bar",
    "SZ-030": "SZ-030 · no edge after costs",
    "SZ-031": "SZ-031 · size multiplier zero",
    "SZ-040": "SZ-040 · inventory cap",
    "SZ-041": "SZ-041 · leverage cap",
    "SZ-042": "SZ-042 · below min ticket",
    "SZ-043": "SZ-043 · asset crowded",
    "SZ-044": "SZ-044 · exploration floor sized",
    "SZ-045": "SZ-045 · manipulation suspected",
    "SZ-046": "SZ-046 · circuit breaker paused",
    "SZ-047": "SZ-047 · probe throttled",
    "SZ-048": "SZ-048 · drought floor probe",
    "SZ-049": "SZ-049 · probe budget exhausted",
    "SZ-050": "SZ-050 · drawdown throttle",
    "SZ-051": "SZ-051 · probe priced (admitted)",
    "SZ-052": "SZ-052 · probe cost refunded",
    "SZ-053": "SZ-053 · probe tuition governor",
    "SZ-060": "SZ-060 · inventory aggression scaled",
    "SZ-061": "SZ-061 · inventory skew scaled",
    "CV-000": "CV-000 · conviction admitted",
    "CV-010": "CV-010 · agreement below floor",
    "CV-020": "CV-020 · edge below cost multiple",
    "CV-030": "CV-030 · regime evidence thin",
    "CV-040": "CV-040 · context misaligned",
    "CV-050": "CV-050 · admit share too high",
    "CV-051": "CV-051 · admit share too low",
    "PT-000": "PT-000 · pretrade approved",
    "PT-010": "PT-010 · invalid inputs",
    "PT-020": "PT-020 · stale data",
    "PT-021": "PT-021 · spread too wide",
    "PT-022": "PT-022 · spoofy regime",
    "PT-023": "PT-023 · book too shallow",
    "PT-030": "PT-030 · participation clamped",
    "PT-031": "PT-031 · below min order",
    "PT-040": "PT-040 · EV negative after fill odds",
    "PT-041": "PT-041 · edge/cost below minimum",
    "PT-050": "PT-050 · exploration bypassed EV bar",
    "PT-060": "PT-060 · time-stop scratch",
    "PT-061": "PT-061 · close reason (verbatim)",
}


def _code_value_mappings():
    return [{"type": "value",
             "options": {c: {"text": t, "index": i}
                         for i, (c, t) in enumerate(sorted(CODE_LABELS.items()))}}]
JOB = '{job="liquiditybot"}'
# NON-SCALING dollars. Grafana's built-in currencyUSD SI-abbreviates at
# >=$1k, so a $4,997.92 equity renders as "$5.00K" on stats and axes —
# literally not the actual amount (user-reported). The custom prefix unit
# renders the raw value with the panel's decimals, no K/M scaling, so every
# money panel shows true dollars.
USD = "prefix:$"

# ---- Apple Liquid Glass constants ------------------------------------------
# Semantic palette (mapped over named colors by _apple_palette) plus the
# dataviz-validated categorical series set for multi-line charts.
GREEN = "#30D158"
RED_HEX = "#FF453A"
ORANGE_HEX = "#FF9F0A"
INDIGO = "#5E5CE6"
GRAY_HEX = "#8E8E93"
# 2026-08-01: was #2596AB, a hand-picked teal that predated the Apple pass
# and was the ONLY color on any board outside the system palette. On the
# Grafana dark canvas (#111217) it measures 5.37:1; the palette's own teal
# measures 9.65:1 — same hue family, nearly double the contrast, and one
# fewer vocabulary item. (Apple system colors: gray #8E8E93 and purple
# #BF5AF2 below were already correct and are unchanged.)
CAT_TEAL = "#40CBE0"
CAT_PURPLE = "#BF5AF2"

INJ_ID = 990          # fixed id on every board so the CSS can self-hide

# Frosted-glass skin, ACTIVE since 2026-07-23: the operator installed the
# signed Business Text plugin (Admin-only step), so the injector tile is a
# marcusolsson-dynamictext-panel whose afterRender hook appends these rules
# to document.head — the route Grafana Cloud's <style> sanitizer (which kept
# the old native-text tile dormant) does not touch. README_glass.md.
GLASS_RULES = """\
html { -webkit-text-size-adjust: 100%; text-size-adjust: 100%; }
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
"""

panels: list = []

_cur = {"x": 0, "y": 0, "row_h": 0}
_pid = {"n": 0}


def _id() -> int:
    _pid["n"] += 1
    return _pid["n"]


def _flush() -> None:
    if _cur["x"] > 0:
        _cur["y"] += _cur["row_h"]
        _cur["x"] = 0
        _cur["row_h"] = 0


def _place(w: int, h: int):
    if _cur["x"] + w > 24:
        _cur["y"] += _cur["row_h"]
        _cur["x"] = 0
        _cur["row_h"] = 0
    x, y = _cur["x"], _cur["y"]
    _cur["x"] += w
    _cur["row_h"] = max(_cur["row_h"], h)
    return x, y


def M(metric, suffix=""):
    return f"max({metric}{JOB}){suffix}"


def _t(expr, ref="A", instant=True, legend=None, fmt=None):
    t = {"refId": ref, "datasource": DS, "expr": expr,
         "instant": instant, "range": not instant}
    if legend is not None:
        t["legendFormat"] = legend
    if fmt:
        t["format"] = fmt
    return t


def row(title, collapsed=False):
    """Section header. collapsed=True ships the row closed: Grafana runs NO
    queries for panels inside a collapsed row, so deep-dive sections cost
    nothing until the operator expands them (2026-07-25 slow-dashboard fix).
    _board() nests the section's member panels into the row object — the
    shape Grafana itself exports for a collapsed row."""
    _flush()
    panels.append({"id": _id(), "type": "row", "title": title,
                   "collapsed": collapsed,
                   "gridPos": {"h": 1, "w": 24, "x": 0, "y": _cur["y"]},
                   "panels": []})
    _cur["y"] += 1
    _cur["x"] = 0
    _cur["row_h"] = 0


# Type scale (2026-08-02). Every stat tile shipped with titleSize/valueSize
# unset, so Grafana auto-fit each number to its box: a 4-wide tile and a
# 12-wide tile rendered at whatever size happened to fit, and NOTHING on the
# board read as more important than anything else. Auto-fit is a layout
# result, not a hierarchy — the same defect as setting every heading in a
# document to the same weight and hoping the reader infers structure.
#
# Three tiers, and only three, so the hierarchy stays legible:
#   hero    the answer to a question you opened the board to ask
#   normal  supporting numbers you read after the hero
#   compact dense state/count tiles read as a group, not individually
# Values are points; Grafana still shrinks to fit, so these are ceilings
# rather than fixed sizes and a long value degrades gracefully.
_SIZES = {"hero": (16, 56), "normal": (14, 34), "compact": (12, 24)}


def stat(title, expr, w, h, unit="", decimals=2, desc="", steps=None,
         mode="value", mappings=None, text_mode="auto", graph="area",
         no_value=None, display_name=None, size="normal"):
    """KPI tile. graph='area' draws a sparkline behind the number (the default,
    for the professional look); graph='none' for pure state/count tiles.
    no_value: honest empty-state text for event-sparse series (fills,
    positions) whose ABSENCE is truthful - 'No data' reads as broken
    telemetry, the text says what absence means.
    size: 'hero' | 'normal' | 'compact' — the type tier (see _SIZES)."""
    x, y = _place(w, h)
    _ts, _vs = _SIZES.get(size, _SIZES["normal"])
    fld = {"unit": unit, "decimals": decimals,
           "thresholds": {"mode": "absolute",
                          "steps": steps or [{"color": "text", "value": None}]},
           "color": {"mode": "thresholds"}}
    if no_value:
        fld["noValue"] = no_value
    if display_name:
        fld["displayName"] = display_name
    if mappings:
        fld["mappings"] = mappings
    panels.append({
        "id": _id(), "type": "stat", "title": title, "description": desc,
        "datasource": DS, "gridPos": {"h": h, "w": w, "x": x, "y": y},
        "fieldConfig": {"defaults": fld, "overrides": []},
        "options": {"colorMode": mode, "graphMode": graph,
                    "justifyMode": "auto", "textMode": text_mode,
                    "wideLayout": True,
                    "text": {"titleSize": _ts, "valueSize": _vs},
                    "reduceOptions": {"calcs": ["lastNotNull"], "fields": "",
                                      "values": False}},
        "targets": [_t(expr, instant=(graph == "none"), legend="")]})


def state(title, expr, w, h, mapping, desc="", no_value=None):
    opts = {k: {"text": v[0], "color": v[1], "index": i}
            for i, (k, v) in enumerate(mapping.items())}
    stat(title, expr, w, h, desc=desc, mode="background", text_mode="value",
         graph="none", mappings=[{"type": "value", "options": opts}],
         steps=[{"color": "text", "value": None}], no_value=no_value)


def gauge(title, expr, w, h, mx=35.0, mn=0, unit="percent", decimals=1,
          steps=None, desc="", no_value=None):
    x, y = _place(w, h)
    fld = {"unit": unit, "min": mn, "max": mx,
           "decimals": decimals, "thresholds": {"mode": "absolute",
               "steps": steps or [{"color": "green", "value": None},
               {"color": "yellow", "value": mx * 0.7},
               {"color": "red", "value": mx * 0.9}]}}
    if no_value:
        fld["noValue"] = no_value
    panels.append({
        "id": _id(), "type": "gauge", "title": title, "description": desc,
        "datasource": DS, "gridPos": {"h": h, "w": w, "x": x, "y": y},
        "fieldConfig": {"defaults": fld, "overrides": []},
        "options": {"showThresholdLabels": False, "showThresholdMarkers": True,
                    "reduceOptions": {"calcs": ["lastNotNull"], "fields": "",
                                      "values": False}},
        "targets": [_t(expr)]})


def timeseries(title, expr, w, h, unit="", legend="value", desc="", fill=18,
               calcs=None, decimals=None, extra=None, colors=None,
               no_value=None):
    """calcs upgrades the legend to a table of reductions (exact numbers
    beside the trend). colors: {series_name: hex} pins each line to a
    fixed validated color instead of palette-classic rotation."""
    x, y = _place(w, h)
    fld = {"unit": unit, "custom": {
        "drawStyle": "line", "lineInterpolation": "smooth", "lineWidth": 2,
        "fillOpacity": fill, "gradientMode": "opacity",
        # showPoints "auto" (not "never"): with a BOUNDED spanNulls a series
        # can be left as isolated samples around an outage, and "never" would
        # render those as nothing at all — a blank panel reads as "no problem"
        # instead of "no data". "auto" only draws points when density is low,
        # so at the 30s push cadence normal traces look unchanged.
        "showPoints": "auto", "spanNulls": SPAN_NULLS_MS, "pointSize": 5,
        "axisPlacement": "auto",
        "scaleDistribution": {"type": "linear"}},
        "color": {"mode": "palette-classic"}}
    if decimals is not None:
        fld["decimals"] = decimals
    if no_value:
        fld["noValue"] = no_value
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


def bargauge(title, expr, w, h, unit="", decimals=2, steps=None,
             legend="{{asset}}", desc="", mn=None, mx=None, no_value=None,
             extra=None, decode_family=None):
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
        "fieldConfig": {"defaults": fld, "overrides": [
            {"matcher": {"id": "byName", "options": c},
             "properties": [{"id": "displayName", "value": t}]}
            for c, t in sorted(CODE_LABELS.items())
            if decode_family and c.startswith(decode_family)]},
        "options": {"displayMode": "basic", "orientation": "horizontal",
                    "showUnfilled": True, "valueMode": "color",
                    "namePlacement": "left", "sizing": "auto",
                    "reduceOptions": {"calcs": ["lastNotNull"], "fields": "",
                                      "values": False}},
        "targets": [_t(expr, instant=True, legend=legend)] + [
            _t(e, ref=chr(ord("B") + i), instant=True, legend=lg)
            for i, (e, lg) in enumerate(extra or [])]})


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
    if "code" in label_keys:
        overrides.append({"matcher": {"id": "byName", "options": "code"},
                          "properties": [{"id": "mappings",
                                          "value": _code_value_mappings()}]})
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


def text(title, md, w, h):
    """A markdown info panel — used to document THALES inline on the board."""
    x, y = _place(w, h)
    panels.append({
        "id": _id(), "type": "text", "title": title,
        "gridPos": {"h": h, "w": w, "x": x, "y": y}, "transparent": True,
        "options": {"mode": "markdown", "content": md,
                    "code": {"language": "plaintext", "showLineNumbers": False,
                             "showMiniMap": False}}})


# ---- threshold palettes ----------------------------------------------------
GRN = [{"color": "text", "value": None}]
BLUE = [{"color": "blue", "value": None}]
PNL = [{"color": "red", "value": None}, {"color": "green", "value": 0}]
DD = [{"color": "green", "value": None}, {"color": "yellow", "value": 8},
      {"color": "red", "value": 12}]
LAT = [{"color": "green", "value": None}, {"color": "yellow", "value": 250},
       {"color": "red", "value": 500}]
CALIB = [{"color": "green", "value": None}, {"color": "yellow", "value": 0.10},
         {"color": "red", "value": 0.15}]
STREAK = [{"color": "green", "value": None}, {"color": "yellow", "value": 3},
          {"color": "red", "value": 5}]
ZERO_BAD = [{"color": "green", "value": None}, {"color": "red", "value": 1}]
BRIER = [{"color": "green", "value": None}, {"color": "yellow", "value": 0.24},
         {"color": "red", "value": 0.25}]
WR100 = [{"color": "red", "value": None}, {"color": "yellow", "value": 45},
         {"color": "green", "value": 55}]
WRU = [{"color": "red", "value": None}, {"color": "yellow", "value": 0.45},
       {"color": "green", "value": 0.55}]
PF = [{"color": "red", "value": None}, {"color": "yellow", "value": 1.0},
      {"color": "green", "value": 1.5}]
# Bracket-geometry economics: measured payoff 0.56 vs ~0.75 needed to break
# even at the observed win rate + fee stack (2026-08-02 payoff decomposition,
# wiki: cost-is-the-binding-constraint). Green only at the break-even line.
PAYOFF = [{"color": "red", "value": None}, {"color": "yellow", "value": 0.60},
          {"color": "green", "value": 0.75}]
SLIP = [{"color": "green", "value": None}, {"color": "yellow", "value": 3},
        {"color": "red", "value": 8}]
HIGH_GOOD = [{"color": "red", "value": None}, {"color": "yellow", "value": 0.4},
             {"color": "green", "value": 0.7}]   # 0..1, higher better
LOW_GOOD = [{"color": "green", "value": None}, {"color": "yellow", "value": 0.4},
            {"color": "red", "value": 0.7}]       # 0..1, lower better
SPREAD = [{"color": "green", "value": None}, {"color": "yellow", "value": 3},
          {"color": "red", "value": 8}]
DRIFT = [{"color": "green", "value": None}, {"color": "yellow", "value": 0.3},
         {"color": "red", "value": 0.5}]
BUDGET = [{"color": "green", "value": None}, {"color": "yellow", "value": 60},
          {"color": "red", "value": 90}]
# SPB-R probe budget (spec §8): labels/day vs the 3/day floor pace and the
# ~12/day expected rate; unlock ETA lower-better; governor factor 1.0
# nominal (floor 0.25); per-regime live labels vs the 60 coverage floor.
PROBE_LABELS = [{"color": "red", "value": None},
                {"color": "yellow", "value": 3},
                {"color": "green", "value": 8}]
PROBE_ETA = [{"color": "green", "value": None},
             {"color": "yellow", "value": 10},
             {"color": "red", "value": 30}]
PROBE_GOV = [{"color": "red", "value": None},
             {"color": "yellow", "value": 0.26},
             {"color": "green", "value": 1}]
PROBE_REGIME = [{"color": "red", "value": None},
                {"color": "yellow", "value": 30},
                {"color": "green", "value": 60}]

ON_OFF = {"1": ("YES", "green"), "0": ("NO", "#8E8E93")}
UP_DOWN = {"1": ("RUNNING", "green"), "0": ("STOPPED", "red")}
WS = {"1": ("LIVE", "green"), "0": ("REST", "yellow")}
HALT = {"1": ("HALTED", "red"), "0": ("clear", "green")}
GOV = {"0": ("OK", "green"), "1": ("DEGRADED", "yellow"), "2": ("KILLED", "red")}
# era_mix_alarm is `1.0 if mix.get("fired")`, so 1 is the BAD state — the
# training corpus has drifted away from the live label era. It was pushed on
# every tick and rendered on no board, so the alarm could fire indefinitely
# with nothing on screen saying so. (It is firing as of 2026-08-02.)
ERA_MIX = {"1": ("DRIFTED", "red"), "0": ("aligned", "green")}
OPSTATE = {"0": ("ARMED", "green"), "1": ("DEGRADED", "yellow"),
           "2": ("HALTED", "red"), "-1": ("UNKNOWN", "red")}
RETRAIN = {"1": ("QUEUED", "yellow"), "0": ("idle", "green")}
# neutral-when-ok: "ok" is the expected steady state and must not compete
# visually with a real departure, so it reads in the neutral gray text color
# (GRAY_HEX) rather than an affirmative green; only low/high (a sustained
# admit share outside the cadence governor's band) earn warning color.
CV_ALARM = {"0": ("ok", GRAY_HEX), "1": ("low", "yellow"),
            "2": ("high", "red")}
# neutral-when-clear: same rationale as CV_ALARM above — "clear" is the
# expected steady state (gates cadence-pause only, per spec §3.4, never
# direction) and reads neutral gray; only the in-window state earns a
# highlight color, and it's yellow (a pause), never red (nothing is
# unsafe about an event window).
CONTEXT_EVENT = {"0": ("clear", GRAY_HEX), "1": ("in-window", "yellow")}
# an achievement ladder, not a severity (task C6): rung 0 (paper-only) is
# the expected, neutral steady state (risk/long_book.py's own docstring —
# "the book trades whenever the system runs") and never reads as a
# warning, so it gets the same neutral gray as CV_ALARM/CONTEXT_EVENT's
# "ok"/"clear" states above; r1/r2 read blue (live risk progressively
# earned); r3 (every gate cleared, the full live ceiling) is the one
# "target reached" state and is the only rung that earns green.
LB_RUNG = {"0": ("paper-only", GRAY_HEX), "1": ("r1", "blue"),
           "2": ("r2", "blue"), "3": ("r3", "green")}
# neutral-when-ok, same rationale as CV_ALARM/CONTEXT_EVENT: an empty
# paused_reason (last add attempt succeeded, or none has run yet) is the
# expected steady state; a non-empty detail (a routine spacing wait,
# ceiling exhaustion, an event window, a halt, ...) is routine cadence
# gating, never a fault — yellow, never red.
LB_PAUSED = {"0": ("ok", GRAY_HEX), "1": ("paused", "yellow")}

# THALES inline documentation (rendered in a markdown text panel)
_THALES_MD = (
    "**THALES** is the bot's footprint & manipulation-defense layer — "
    "evidence-weighted detectors that shade sizing when a book looks "
    "*engineered* rather than organic. Every score is **0–1** (higher = more "
    "suspicious) and **reliability-weighted**: a detector only bites once it "
    "has proven itself on realized outcomes (Wilson-LCB), so it can't cry "
    "wolf.\n\n"
    "- **grid / metronome / clockwork** — periodicity footprints: grid-bot "
    "ladders, fixed-interval refills, time-of-day algo seasonality.\n"
    "- **stop-zone** — proximity to round-number stop clusters (stop-hunt "
    "zones).\n"
    "- **bar-close** — order-flow clustering at bar closes.\n"
    "- **spoof bid / ask** — flicker: large levels that appear then vanish "
    "without the mid ever crossing (**TH-017**).\n"
    "- **feed dirty / lapses / bar holes** — feed integrity; a dirty feed is "
    "quarantined, never traded.\n\n"
    "THALES **never triggers a trade** — it only *attenuates*: shade the size, "
    "or down-weight that row in learning (a painted book teaches the "
    "painter's lesson, not the market's).")

# per-asset series (label asset) via instant vector, one bar/line each
A = "{" + 'job="liquiditybot"' + "}"


def _pa(metric, suffix=""):
    return f"{metric}{A}{suffix}"


# The LEARNING BRAIN header. Written as a DECISION LADDER rather than a
# legend (2026-08-02): a legend tells you what a tile means, which you can
# already get from its tooltip. What was missing was what to DO — which of
# fourteen numbers is the binding constraint right now, and what the next
# action is. The rule is deliberately mechanical: read top-down, stop at the
# first red stage, fix only that. A model-quality problem is unfixable while
# the supply stage above it is starved, and every hour spent tuning the model
# while live_clean sits at 0 is an hour spent on a downstream symptom.
_BRAIN_GUIDE = (
    "**Read top-down. Stop at the first stage that is red — that is your "
    "binding constraint. Everything below it is a symptom, not a cause.**\n\n"
    "| # | Stage | Red when | What it means | Do this |\n"
    "|---|---|---|---|---|\n"
    "| 1 | **SUPPLY** | `Clean live labels` flat or < 30 | The loop is "
    "starved. No amount of model work matters — there is nothing to learn "
    "from. | Check `Live labels` beside it: if live is climbing and clean "
    "is not, hygiene is eating the rows, so read `Label uniqueness`. If "
    "both are flat, the bot is not closing trades. |\n"
    "| 2 | **CORPUS** | `Era exclusion` ACTIVE with `New-era rows` < 150, "
    "or uniqueness < 0.05 | You have rows but they do not count. Overlapping "
    "horizons mean N labels carry far less than N labels of evidence "
    "(AFML ch. 4 — sample weights redistribute so overlap cannot "
    "double-count). | Wait for new-era rows to reach 150, or shorten the "
    "label horizon. A corpus of 274 rows at uniqueness 0.05 is an effective "
    "sample near 14. |\n"
    "| 3 | **QUALITY** | `Brier` at or above baseline, or "
    "`Calibration gap` widening | The model is not beating the base rate, "
    "or its probabilities are not the thing they claim to be. Kelly reads "
    "probabilities literally, so a calibration error is a *sizing* error. | "
    "Compare against `champion` on the Brier chart. If live is worse than "
    "baseline, the honest move is to stand the model down, not retune it. |\n"
    "| 4 | **GOVERNOR** | `Model in use` NO while 1–3 are green | The model "
    "earned its place and is still muted. | This is usually correct — a "
    "stand-down, not a fault. Check the governor level on VITALS before "
    "overriding anything. |\n\n"
    "**When all four are green and it still loses money**, the constraint "
    "is not learning — it is geometry. A selector cannot harvest an edge "
    "smaller than costs: check cost per round trip against horizon sigma "
    "(`scripts/horizon_bootstrap.py`) and the gate's realized separation "
    "(`scripts/gate_efficacy_report.py`). At a 2-hour horizon this bot paid "
    "0.82 sigma per round trip and no selector could win; the fix was the "
    "horizon, not the model.\n\n"
    "*Sample-size discipline throughout: prefer `Win rate LCB` (Wilson "
    "lower bound) to the point estimate, and treat any conclusion drawn "
    "from fewer than ~30 clean live labels as a hypothesis rather than a "
    "finding.*")


# ========================= board 1 · command ===============================
# ---------------------------------------------------------------------------
# BOARD CONTENT - stripped 2026-08-15, then ONE board rebuilt.
#
# Stripped on operator instruction BEFORE the new configuration produced its
# first real data: no board may show a number carried over from the retired
# geometry, and an empty pane is honest where a stale one is not. 188
# visualization panels and 23 row headers were deleted.
#
# CURRENT STATE, and it is deliberately asymmetric:
#   _author_command    the LIQUIDITY BOARD - a small at-a-glance read (below)
#   _author_execution  EMPTY
#   _author_problem    EMPTY
#   _author_screening  EMPTY
# The three deep boards stay empty until the new configuration has produced
# enough data to justify a panel. Emptiness here is a decision, not a defect.
#
# SANITIZER CONTRACT - recorded here because the only two places it was ever
# written down (the _bt_options() docstring and the pulse banner comment) were
# deleted in the strip, and losing it would make the glass skin unmaintainable:
# Grafana Cloud STRIPS <style> out of rendered panel HTML. CSS reaches the page
# by exactly two routes - (a) the Business Text plugin's dedicated `styles`
# option, which the plugin injects itself, outside the sanitizer's reach, or
# (b) an `afterRender` hook appending a <style> node to document.head, which is
# the route _injector() takes. A <style> tag placed back into a panel's
# `content` silently vanishes on the instance and the board renders unskinned.
#
# What survives is the FRAMEWORK, not the content:
#   * GLASS_RULES + _injector()      the Liquid Glass frosted skin
#                                    (docs/grafana/README_glass.md)
#   * _apple_palette() + _hig_all()  Apple system palette and the HIG pass
#                                    (docs/grafana/HIG.md)
#   * the panel FACTORIES - row/stat/state/gauge/timeseries/bargauge/donut/
#     table/text - and every threshold palette, untouched.
#
# Each board therefore renders as: shell (title, tags, nav links, time range)
# plus exactly ONE glass injector panel. Panel count per board is 1.
#
# TO REBUILD a board, append factory calls inside the matching _author_ below;
# nothing else has to be restored first. The deleted content is recoverable in
# full from git history (parent commit of this change).
# ---------------------------------------------------------------------------


def _author_command():
    """THE LIQUIDITY BOARD - the at-a-glance read, before any deep dive.

    Deliberately small. The deep boards stay EMPTY until the new
    configuration has produced enough data to justify a panel; this one
    answers only "where does the account stand right now".

    ACCURACY RULE for anything added here: every expression below queries a
    metric that scripts/gc_pusher.py was VERIFIED to emit, by running
    gc_pusher.collect() against the live outputs/status.json and reading the
    value back (2026-08-15). Three plausible-looking names were REJECTED by
    that check - liquiditybot_open_positions, _win_rate and _cash do not
    exist; the real ones are _positions_open, and win rate / cash are not
    exported at all. A panel whose metric was never emitted renders "No
    data", which is indistinguishable from a broken exporter. Do not add a
    panel here from memory of another board - re-run the check.
    """
    # Staleness scale for a 30s push cadence (GC_PERIOD_SEC): two missed
    # pushes is noise, a minute is worth noticing, five minutes means the
    # pusher is down and every other number on this board is a fossil.
    age_steps = [{"color": "green", "value": None},
                 {"color": "yellow", "value": 60},
                 {"color": "red", "value": 300}]

    # ---- hero line: the five numbers the board exists to answer ----------
    stat("Equity", M("liquiditybot_equity"), 6, 6, unit=USD, decimals=2,
         size="hero", steps=GRN,
         desc="Account equity, marked to market. PAPER account - the bot "
              "runs dry_run and places no real order.")
    # NOTE: no explicit no_value= anywhere on this board. The generator
    # already assigns empty-state text from _ALWAYS_ON / _NO_VALUE_BY_FAMILY
    # (:1137-1190), and that registry restates the ACTUAL guard in
    # scripts/gc_pusher.py per metric family. A hand-written string here
    # OVERRIDES it - which is how "Open positions" first shipped saying
    # "flat" when its series was missing. positions_open is always-on, so its
    # absence is a broken exporter, and "flat" would have read as a truthful
    # empty book. Let the registry answer; it knows the guards and I do not.
    stat("Today", M("liquiditybot_daily_pnl"), 5, 6, unit=USD, decimals=2,
         steps=PNL, desc="P&L since midnight, realized plus unrealized.")
    stat("This week", M("liquiditybot_weekly_pnl"), 5, 6, unit=USD,
         decimals=2, steps=PNL)
    stat("All time", M("liquiditybot_net_pnl_all_time"), 4, 6, unit=USD,
         decimals=2, steps=PNL)
    stat("Drawdown", M("liquiditybot_drawdown_pct"), 4, 6, unit="percent",
         decimals=2, steps=DD, desc="Peak-to-trough, percent of peak equity.")

    # ---- the one chart: equity is the only trend worth a glance ----------
    timeseries("Equity", M("liquiditybot_equity"), 24, 7, unit=USD,
               legend="equity", decimals=2, colors={"equity": GREEN},
               desc="Equity over the dashboard time range. Gaps wider than "
                    "5 min are drawn as gaps, not bridged - a flat line "
                    "across an outage would be a fiction.")

    # ---- book and telemetry health, read as a group ----------------------
    stat("Open positions", M("liquiditybot_positions_open"), 4, 5,
         unit="short", decimals=0, graph="none", size="compact", steps=BLUE,
         desc="Count of open positions. A zero here is a flat book; a MISSING "
              "series is a broken exporter, and the generator labels it so.")
    gauge("Gross exposure", M("liquiditybot_gross_exposure_pct"), 5, 5,
          mx=100.0, unit="percent", decimals=1, steps=BUDGET,
          desc="Notional at risk as a percent of equity.")
    stat("Fees paid", M("liquiditybot_fees_total"), 4, 5, unit=USD,
         decimals=2, graph="none", size="compact", steps=GRN,
         desc="Cumulative simulated fees. At this account size fees are the "
              "binding constraint, so they belong on the front page.")
    state("Entries", M("liquiditybot_entries_enabled"), 4, 5, ON_OFF,
          desc="Whether the bot may OPEN new positions. Exits are always "
               "allowed regardless of this.")
    state("Halt", M("liquiditybot_halted"), 3, 5, HALT,
          desc="Circuit breaker. 'clear' is the healthy state.")
    stat("Data age", M("liquiditybot_status_age_sec"), 4, 5, unit="s",
         decimals=0, graph="none", size="compact", steps=age_steps,
         desc="Seconds since the RUNNER last wrote outputs/status.json "
              "(gc_pusher.py: now - status['written_at']) - the age of the "
              "bot's own write, NOT of the push. If this climbs, every other "
              "number on this board is a fossil - read it FIRST.")

    # ---- liveness: WHOSE silence is it? ---------------------------------
    # These four exist because of a measured failure mode, not for symmetry.
    # When the runner freezes, gc_pusher.collect() drops from 792 series to
    # FIVE - running / status_age_sec / status_malformed / status_missing /
    # status_stale. Every money tile above then renders its LAST value
    # forever (stat panels reduce lastNotNull over the window), so a frozen
    # bot reads as a calm, profitable book. The pre-strip board carried
    # `running` and `status_stale`; deleting them removed the only controls
    # that made that state visible, and these tiles put them back. They are
    # also the ONLY way to tell the two silences apart:
    #   runner frozen  -> Runner STOPPED / Telemetry STALE, age climbing
    #   pusher dead    -> every tile including these goes to its noValue text
    state("Runner", M("liquiditybot_running"), 6, 5, UP_DOWN,
          desc="Is the bot's own loop alive. STOPPED here means every money "
               "tile above is a fossil, however healthy it looks.")
    state("Telemetry", M("liquiditybot_status_stale"), 6, 5,
          {"1": ("STALE", "red"), "0": ("fresh", "green")},
          desc="Whether the status write has aged past the exporter's "
               "staleness threshold. STALE = do not trust the numbers.")
    state("Kraken feed", M("liquiditybot_ws_kraken_connected"), 6, 5, WS,
          desc="Kraken websocket. REST means degraded marks, not an outage.")
    state("Op state", M("liquiditybot_op_state"), 6, 5, OPSTATE,
          desc="Overall operating state. Distinct from the Halt tile: that "
               "is the circuit breaker alone, this is the whole posture.")

    # ---- the only detail worth showing before going deeper ---------------
    row("Positions")
    table("Open positions", 24, 9,
          cols=[("liquiditybot_position_notional_usd", "notional", USD, 2,
                 None, "text"),
                ("liquiditybot_position_upnl_usd", "uP&L $", USD, 2, PNL,
                 "text"),
                ("liquiditybot_position_upnl_pct", "uP&L %", "percent", 2,
                 PNL, "text"),
                ("liquiditybot_position_r_multiple", "R", "short", 2, PNL,
                 "text"),
                # "text", NOT the default "bg": HIGH_GOOD is a red-BASED
                # scale, and an outer join leaves a legitimately-absent cell
                # null, which paints the BASE threshold colour - a null
                # conviction would render as alarm red. That is the 2026-07-22
                # defect; tests/test_glass_suite.py pins it and caught this.
                ("liquiditybot_position_conviction", "conviction", "short", 2,
                 HIGH_GOOD, "text"),
                ("liquiditybot_position_age_hours", "age", "h", 1, None),
                ("liquiditybot_position_stop_dist_pct", "stop dist",
                 "percent", 2, None)],
          label_keys=["symbol", "side"], sort="uP&L $",
          desc="One row per open position, joined on symbol. An empty table "
               "is AMBIGUOUS and must not be read as a flat book: the same "
               "emptiness appears when the runner freezes, because every "
               "liquiditybot_position_* series stops being emitted while the "
               "positions are still genuinely open (measured 2026-08-15 - 5 "
               "open, 0 series). Read the Runner and Telemetry tiles before "
               "concluding anything from an empty table.")


def _author_execution():
    """Intentionally empty - board content stripped, see note above."""
    return


def _author_problem():
    """Intentionally empty - board content stripped, see note above."""
    return


def _author_screening():
    """Intentionally empty - board content stripped, see note above."""
    return


_TAGS = ["liquiditybot", "trading", "paper-trading"]
_NAV = [("⌘ Command", "liquiditybot-trading"),
        ("⚙ Models·Inv·Exec", "liquiditybot-exec"),
        ("🩹 Problem/Solution", "liquiditybot-problem-solution"),
        ("🔎 Screening", "liquiditybot-screening")]


def _links():
    return [{"title": t, "type": "link", "url": f"/d/{u}", "icon": "dashboard",
             "tooltip": "", "targetBlank": False, "asDropdown": False,
             "includeVars": False, "keepTime": True, "tags": []}
            for t, u in _NAV]


def _injector():
    # json.dumps embeds the rules as a JS string literal — no escaping
    # hazards, and the guard keeps re-renders / cross-board SPA navigation
    # from stacking duplicate <style> nodes.
    marker = '<span id="lb-glass-marker"></span>'
    js = ("if (!document.getElementById('lb-glass')) { "
          "var s = document.createElement('style'); s.id = 'lb-glass'; "
          f"s.textContent = {json.dumps(GLASS_RULES)}; "
          "document.head.appendChild(s); }")
    return {"id": INJ_ID, "type": "marcusolsson-dynamictext-panel",
            "title": "", "datasource": None,
            "gridPos": {"h": 1, "w": 1, "x": 0, "y": _cur["y"] + 1},
            "transparent": True,
            "options": {"renderMode": "data", "content": marker,
                        "defaultContent": marker,
                        "editors": ["afterRender"], "afterRender": js,
                        "helpers": "", "styles": "", "wrap": False,
                        "externalStyles": [], "contentPartials": []},
            "pluginVersion": "6.3.0"}


def _nest_collapsed(flat):
    """Move each collapsed row's member panels INTO the row object — the
    exact shape Grafana exports for a collapsed row. Grafana runs no
    queries for nested panels until the row is expanded, so collapsed
    sections cost nothing at load (2026-07-25 slow-dashboard fix).
    gridPos values are kept verbatim: Grafana re-lays nested panels out
    from these same coordinates on expand."""
    out = []
    receiving = None
    for p in flat:
        if p["type"] == "row":
            receiving = p if p["collapsed"] else None
            out.append(p)
        elif receiving is not None:
            receiving["panels"].append(p)
        else:
            out.append(p)
    return out


def _board(uid, title, desc, author, extra_tag, time_from="now-24h"):
    panels.clear()
    _cur.update(x=0, y=0, row_h=0)
    _pid["n"] = 0
    author()
    _flush()
    top = _nest_collapsed(panels)
    # the CSS injector must stay top-level: a panel nested in a collapsed
    # row never renders, and the frosted-glass skin would vanish until the
    # operator happened to expand that row
    top.append(_injector())
    # _injector() places itself one row BELOW the last content panel, which is
    # correct while a board has content. On a stripped (content-free) board it
    # is the ONLY panel, and y=1 would leave a dead empty row above it and
    # break the "first panel starts at the top" invariant that
    # test_importable_shape_and_layout_per_board pins. Re-seat it at the
    # origin in exactly that case; a board WITH content is untouched.
    if len(top) == 1:
        top[0]["gridPos"]["y"] = 0
    for p in top:
        if p["type"] != "row":
            p["transparent"] = True
        for member in p.get("panels") or []:
            member["transparent"] = True
    # refresh 1m: gc_pusher exports every 30s; 1m still surfaces every push
    # within one refresh at half the query/render churn (2026-07-25 fix)
    return {"uid": uid, "title": title, "description": desc,
            "tags": _TAGS + [extra_tag], "schemaVersion": 39, "editable": True,
            "timezone": "browser", "refresh": "1m", "style": "dark",
            "time": {"from": time_from, "to": "now"}, "links": _links(),
            "templating": {"list": []}, "annotations": {"list": []},
            "panels": top}


# ---- Apple system palette (Liquid Glass design language) --------------------
# The whole suite shares one visual language with the Glass boards: Grafana's
# named colors / stock hexes are remapped onto the Apple dark-variant system
# palette at GENERATION time, so the shipped JSON == generator invariant holds
# and the semantics (green nominal/profit, red loss/unsafe, orange watch,
# blue neutral-info, indigo model domain) stay exactly as authored.
_APPLE = {
    "green": "#30D158", "dark-green": "#30D158", "semi-dark-green": "#30D158",
    "light-green": "#30D158", "super-light-green": "#30D158",
    "#73BF69": "#30D158", "#56A64B": "#30D158", "#37872D": "#30D158",
    "red": "#FF453A", "dark-red": "#FF453A", "semi-dark-red": "#FF453A",
    "light-red": "#FF453A", "#F2495C": "#FF453A", "#E02F44": "#FF453A",
    "orange": "#FF9F0A", "dark-orange": "#FF9F0A",
    "semi-dark-orange": "#FF9F0A", "light-orange": "#FF9F0A",
    "#FF9830": "#FF9F0A", "#FA6400": "#FF9F0A",
    "yellow": "#FFD60A", "dark-yellow": "#FFD60A",
    "semi-dark-yellow": "#FFD60A", "light-yellow": "#FFD60A",
    "#FADE2A": "#FFD60A", "#EAB839": "#FFD60A", "#F2CC0C": "#FFD60A",
    "blue": "#0A84FF", "dark-blue": "#0A84FF", "semi-dark-blue": "#0A84FF",
    "light-blue": "#40CBE0", "super-light-blue": "#40CBE0",
    "#5794F2": "#0A84FF", "#3274D9": "#0A84FF", "#1F60C4": "#0A84FF",
    "purple": "#5E5CE6", "dark-purple": "#5E5CE6",
    "semi-dark-purple": "#5E5CE6", "light-purple": "#5E5CE6",
    "#B877D9": "#5E5CE6", "#8F3BB8": "#5E5CE6",
}


def _apple_palette(obj):
    """Recursively remap every color-bearing field onto the Apple palette."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in ("color", "fixedColor", "lineColor", "fillColor") \
                    and isinstance(v, str):
                obj[k] = _APPLE.get(v, v)
            else:
                _apple_palette(v)
    elif isinstance(obj, list):
        for x in obj:
            _apple_palette(x)
    return obj


# --- HIG conformance pass (2026-08-01) ------------------------------------
# A second recursive post-pass, in the same spirit as _apple_palette: state
# the rule once, apply it everywhere, instead of remembering it at 179 call
# sites. Every rule was MEASURED before it was written, and the measuring
# mattered — a first audit claimed "65 panels missing units", which was wrong
# by roughly 10x. Most unitless panels here are integer counts, where a unit
# makes them WORSE (Grafana's "short" renders 1000 as "1 K"), or ratios like
# the Kelly multiplier, which have no unit by definition. The full count, and
# what was deliberately NOT changed, is in docs/grafana/HIG.md. Results are
# pinned by tests/test_dashboard_hig.py.

# Titles whose value is genuinely a PROPORTION and so belongs in percentunit.
# Scores are deliberately excluded: a manipulation-suspicion of 0.42 is not
# "42%" of anything, and percentunit would assert a part-of-whole that does
# not exist. Only true shares appear here.
_PERCENTUNIT = {
    "Label uniqueness", "Calibration gap", "Admit share by regime",
    "Era mix drift (TVD)", "Per-asset eff weight (taper × scarcity)",
}
# Units that were smuggled into the TITLE, where they cannot travel with the
# value into a tooltip, a legend, or an alert notification.
_TITLE_UNIT = {
    "Unlock ETA (days)": ("Unlock ETA", "suffix:d"),
    "Spread by asset (bps, lower = tighter book)":
        ("Spread by asset", "suffix: bps"),
    # unit was "short", which renders nothing — the real unit lived in the
    # title, so the number reached tooltips and alerts dimensionless.
    "Slippage vs arrival (bps)": ("Slippage vs arrival", "suffix: bps"),
}
# Counts whose y-axis must anchor at zero. An axis that autoscales to
# [270, 274] turns four units of noise into a mountain range.
_ZERO_ANCHOR = re.compile(
    r"label|row|count|position|trade|token|admission|candidate", re.I)


# --- honest-absence presentation contract (2026-08-15) --------------------
# A panel that renders Grafana's stock "No data" says nothing about WHY.
# Two entirely different facts render identically: (a) the bot has not yet
# done the thing the series counts (zero fills, no retrain, judge window
# short) and (b) the telemetry that should always be there is gone. The
# first is an honest absence and the board must SAY SO; the second is a
# defect and the board must say THAT. This block is the rule, applied once
# in _hig_pass to every panel on every board (same doctrine as
# _apple_palette / the HIG pass: state it once, never at 185 call sites).

# Metrics scripts/gc_pusher.collect() emits from a status.json containing
# ONLY {written_at, runner_state} — i.e. whose emission depends on no
# status content whatsoever. If one of these has no series, the bot's
# trading state is not the explanation: the pusher, the status file, or
# the query is. Pinned against the exporter by
# tests/test_dashboard_no_value.py::test_always_on_set_matches_the_exporter,
# which recomputes this set by RUNNING collect() on a minimal status.
_ALWAYS_ON = frozenset({
    "liquiditybot_audit_dropped_writes", "liquiditybot_audit_tail_truncations",
    "liquiditybot_entries_enabled", "liquiditybot_fault_count",
    "liquiditybot_firewall_fault", "liquiditybot_gauges_dropped_nonfinite",
    "liquiditybot_gross_exposure_usd", "liquiditybot_halted",
    "liquiditybot_haven_info", "liquiditybot_ml_model_info",
    "liquiditybot_ml_retrain_flag", "liquiditybot_ml_use_model",
    "liquiditybot_moomoo_available", "liquiditybot_moomoo_options_available",
    "liquiditybot_op_state", "liquiditybot_open_risk_usd",
    "liquiditybot_open_upnl_usd", "liquiditybot_positions_open",
    "liquiditybot_running", "liquiditybot_status_age_sec",
    "liquiditybot_status_malformed", "liquiditybot_status_missing",
    "liquiditybot_status_stale", "liquiditybot_watchdog_critical_stale",
    "liquiditybot_watchdog_divergent", "liquiditybot_watchdog_entries_blocked",
    "liquiditybot_watchdog_stale_assets",
    "liquiditybot_watchdog_velocity_tripped",
    "liquiditybot_ws_kraken_connected",
})

# The one string that means "this is broken", never "this has not happened".
_NV_DEFECT = "⚠ no series — exporter/pusher, not the bot"

_NV_NOT_WRITTEN = "not in this cycle's status write"
_NV_NO_RETRAIN = "awaiting first retrain (no corpus load)"
_NV_JUDGE = "window filling (<15 model-scored closes)"

# metric-name PREFIX -> (tier, operator-readable precondition).
# tier "event"   the series cannot exist until the named event happens
# tier "section" the series cannot exist until the runner writes that block
# Every string restates the ACTUAL guard in scripts/gc_pusher.py; the
# file:line of each guard is in the comment beside it.
_NO_VALUE_BY_FAMILY = {
    # ---- event-gated ----------------------------------------------------
    # order_manager.py:730-731  "maker_share": ... if fills else None
    "liquiditybot_order_maker_share": ("event", "awaiting first fill"),
    # order_manager.py:734-741 read the SLIP LEDGER, appended at :707-710
    # only for a fill with a finite arrival ref AND notional >= 1% of the
    # order — a dust fill books fees and no slip.
    "liquiditybot_order_avg_slip_bps": ("event", "awaiting first non-dust fill"),
    "liquiditybot_order_worst_slip_bps": ("event", "awaiting first non-dust fill"),
    "liquiditybot_order_slip_bps_notional_weighted":
        ("event", "awaiting first non-dust fill"),
    # gc_pusher.py:874-879  per asset+horizon markout sample
    "liquiditybot_markout_bps": ("event", "awaiting first post-fill markout"),
    # gc_pusher.py:721-728 <- ml/monitor.py:773 `if w is not None` <- :225-226
    # `if len(recs) < self.min_trades: return None`, min_trades default 15
    "liquiditybot_ml_brier": ("event", _NV_JUDGE),
    "liquiditybot_ml_baseline_brier": ("event", _NV_JUDGE),
    "liquiditybot_ml_calibration_gap": ("event", _NV_JUDGE),
    "liquiditybot_ml_hit_rate": ("event", _NV_JUDGE),
    "liquiditybot_ml_avg_p": ("event", _NV_JUDGE),
    "liquiditybot_ml_window_trades": ("event", _NV_JUDGE),
    # gc_pusher.py:757-765  ls = ml["load_stats"], written only by a
    # completed HistoryStore.load_training_data (main.py:6245 auto-retrain)
    "liquiditybot_ml_live_clean": ("event", _NV_NO_RETRAIN),
    "liquiditybot_ml_mean_uniqueness": ("event", _NV_NO_RETRAIN),
    "liquiditybot_ml_dropped_dirty": ("event", _NV_NO_RETRAIN),
    "liquiditybot_ml_dropped_clash": ("event", _NV_NO_RETRAIN),
    "liquiditybot_ml_prior_skew": ("event", _NV_NO_RETRAIN),
    # gc_pusher.py:776  `if ls:` gates the WHOLE era block — same root cause
    "liquiditybot_era_": ("event", _NV_NO_RETRAIN),
    # gc_pusher.py:851-852  `bd_n > 0`
    "liquiditybot_bracket_divergence_":
        ("event", "awaiting first bracket close"),
    # gc_pusher.py:533-536 / :537-547  zero-iteration over empty dicts
    "liquiditybot_conviction_denials": ("event", "no conviction denial yet"),
    "liquiditybot_conviction_regime_":
        ("event", "awaiting first regime-bucketed eval"),
    # gc_pusher.py:227-229  avg_cost_24h is None until the first admit
    "liquiditybot_probe_budget_avg_cost_24h":
        ("event", "awaiting first probe admit"),
    # gc_pusher.py:939-942  loop over cb["tripped"], empty when nothing paused
    "liquiditybot_cb_paused_hours_left":
        ("event", "no asset circuit-breaker tripped"),
    # gc_pusher.py:898-901  loop over firewall["counters"]
    "liquiditybot_firewall_count": ("event", "no firewall trip recorded"),
    # gc_pusher.py:510-514 / :956-959  per-code tallies
    "liquiditybot_code_count": ("event", "this reason code has not fired"),
    # gc_pusher.py:423-431 / :411-419 / :402-410  performance ledger slices
    "liquiditybot_perf_conviction_":
        ("event", "awaiting first close in this bucket"),
    "liquiditybot_perf_asset_": ("event", "awaiting first close on this asset"),
    "liquiditybot_perf_": ("event", "awaiting first closed trade"),
    # gc_pusher.py:343-388  aggregated from status.positions (non-hedge)
    "liquiditybot_position_": ("event", "flat — no open positions"),
    # gc_pusher.py:189-204  graded-evidence ledger, structurally empty
    # before the shadow-grading unlock
    "liquiditybot_thales_rel_": ("event", "no graded THALES evidence yet"),
    "liquiditybot_thales_base_": ("event", "no graded THALES evidence yet"),
    # gc_pusher.py:734-737  labels_by_source
    "liquiditybot_ml_labels": ("event", "no labelled rows yet"),
    # ---- section-gated --------------------------------------------------
    "liquiditybot_goal_": ("section", "no profit goal configured"),
    "liquiditybot_context_": ("section", "no context poll yet"),
    "liquiditybot_longbook_": ("section", "long book disabled/not built"),
    "liquiditybot_probe_": ("section", "no probe-budget telemetry yet"),
    "liquiditybot_thales_": ("section", "no THALES read for this asset"),
    "liquiditybot_regime_": ("section", "no regime data yet"),
    "liquiditybot_signal_": ("section", "no signal read this cycle"),
    "liquiditybot_gate_": ("section", "gate ledger empty — no labelled rows"),
    "liquiditybot_skimmer_": ("section", "skimmer has scored no candidate"),
    "liquiditybot_haven_": ("section", "no haven ladder read yet"),
    "liquiditybot_cb_": ("section", "circuit-breaker ledger not written"),
    "liquiditybot_conviction_": ("section", "conviction ledger not written"),
    "liquiditybot_manip_suspect": ("section", "no manipulation read this cycle"),
    "liquiditybot_rp_": ("section", "risk-protocol stack not reporting"),
    "liquiditybot_ml_": ("section", _NV_NOT_WRITTEN),
    "liquiditybot_monitor_": ("section", _NV_NOT_WRITTEN),
    "liquiditybot_order_": ("section", _NV_NOT_WRITTEN),
    # ---- bare top-level scalars: gc_pusher.py:294-315 numeric whitelist --
    "liquiditybot_equity": ("section", _NV_NOT_WRITTEN),
    "liquiditybot_daily_pnl": ("section", _NV_NOT_WRITTEN),
    "liquiditybot_weekly_pnl": ("section", _NV_NOT_WRITTEN),
    "liquiditybot_savings": ("section", _NV_NOT_WRITTEN),
    "liquiditybot_reserve": ("section", _NV_NOT_WRITTEN),
    "liquiditybot_drawdown_pct": ("section", _NV_NOT_WRITTEN),
    "liquiditybot_cycle": ("section", _NV_NOT_WRITTEN),
    "liquiditybot_feed_latency_ms": ("section", _NV_NOT_WRITTEN),
    "liquiditybot_marks_age_sec": ("section", _NV_NOT_WRITTEN),
    "liquiditybot_fees_total": ("section", _NV_NOT_WRITTEN),
    "liquiditybot_realized_": ("section", _NV_NOT_WRITTEN),
    "liquiditybot_net_pnl_all_time": ("section", _NV_NOT_WRITTEN),
    "liquiditybot_entry_fees_total": ("section", _NV_NOT_WRITTEN),
    "liquiditybot_starting_capital": ("section", _NV_NOT_WRITTEN),
    "liquiditybot_exit_eval_failures": ("section", _NV_NOT_WRITTEN),
    "liquiditybot_gross_exposure_pct": ("section", _NV_NOT_WRITTEN),
}
_NV_TIER_RANK = {"event": 0, "section": 1}
# Panel types whose fieldConfig.defaults.noValue replaces the panel-level
# "No data" message. `table` is EXCLUDED on purpose: there noValue fills
# every empty CELL, and a sentence per cell is unreadable — the table's
# "·" stays, and its absence story rides its description.
_NV_TYPES = ("stat", "gauge", "bargauge", "timeseries", "piechart")
_MET_RE = re.compile(r"liquiditybot_[a-z0-9_]+")


def _nv_family(metric):
    """Longest-prefix match into _NO_VALUE_BY_FAMILY. None for an
    always-on metric. Raises for anything undeclared — a panel whose
    metric family has no stated precondition must not ship, because the
    board would render its absence with no explanation at all."""
    if metric in _ALWAYS_ON:
        return None
    best = ""
    for k in _NO_VALUE_BY_FAMILY:
        if metric.startswith(k) and len(k) > len(best):
            best = k
    if not best:
        raise KeyError(
            f"{metric}: no entry in _NO_VALUE_BY_FAMILY. Declare the "
            f"precondition (the guard in scripts/gc_pusher.py) before "
            f"shipping a panel that queries it.")
    return best


def _panel_no_value(panel):
    """The honest empty-state string for one panel, or None if the panel
    is not a noValue-bearing type or carries no query."""
    if panel.get("type") not in _NV_TYPES:
        return None
    mets = set()
    for t in panel.get("targets") or []:
        mets |= set(_MET_RE.findall(t.get("expr") or ""))
    if not mets:
        return None
    if any(m in _ALWAYS_ON for m in mets):
        return _NV_DEFECT
    ranked = []
    for m in sorted(mets):
        key = _nv_family(m)
        tier, msg = _NO_VALUE_BY_FAMILY[key]
        ranked.append((_NV_TIER_RANK[tier], -len(key), m, msg))
    ranked.sort()
    return ranked[0][3]


def _nv_all_preconditions(panel):
    """Every distinct precondition on the panel, for the description."""
    mets = set()
    for t in panel.get("targets") or []:
        mets |= set(_MET_RE.findall(t.get("expr") or ""))
    out = []
    for m in sorted(mets):
        key = _nv_family(m)
        if key is None:
            msg = _NV_DEFECT
        else:
            msg = _NO_VALUE_BY_FAMILY[key][1]
        if msg not in out:
            out.append(msg)
    return out


def _hig_pass(panel):
    """Apply the measured HIG fixes to one leaf panel, in place."""
    fc = panel.setdefault("fieldConfig", {}).setdefault("defaults", {})
    title = panel.get("title") or ""
    ptype = panel.get("type")

    # Honest-absence contract: every data panel says what its own emptiness
    # MEANS. setdefault, so a hand-authored no_value= at the call site always
    # wins over the family default.
    _nv = _panel_no_value(panel)
    if _nv:
        fc.setdefault("noValue", _nv)
        if ptype == "timeseries":
            # timeseries noValue support is not verified against this
            # Grafana Cloud instance, and a multi-series panel has more
            # than one precondition anyway — the description always renders
            # and always carries the full list.
            _pc = _nv_all_preconditions(panel)
            _d = panel.get("description") or ""
            _tail = "Empty means: " + "; ".join(_pc) + "."
            if _tail not in _d:
                panel["description"] = (_d + " " if _d else "") + _tail

    # Thresholds declared but no explicit color mode: Grafana's default
    # varies by panel type, so those steps may silently never paint.
    steps = (fc.get("thresholds") or {}).get("steps") or []
    if len(steps) > 1 and (fc.get("color") or {}).get("mode") is None \
            and ptype in ("stat", "gauge", "bargauge"):
        fc["color"] = {"mode": "thresholds"}

    if title in _TITLE_UNIT:
        new, unit = _TITLE_UNIT[title]
        was = title[len(new):].strip(" (),")
        panel["title"] = new
        fc["unit"] = unit
        d = panel.get("description") or ""
        if was and was not in d:
            panel["description"] = (d + " " if d else "") + f"({was})"
    elif title in _PERCENTUNIT and not fc.get("unit"):
        fc["unit"] = "percentunit"
        # percentunit multiplies by 100, so precision carried over from the
        # fraction is one decimal place too far: 0.250 would read "25.000%".
        if (fc.get("decimals") or 0) > 1:
            fc["decimals"] = 1

    if ptype == "timeseries":
        # Match the QUERY as well as the title. "Era exclusion — progress
        # toward re-arming" plots era_excl_new_rows against min_rows, both
        # plain counts, but carries no count word in its title and so slipped
        # through a title-only rule. That panel is the one where it matters
        # most: at 140 rows against a 150 threshold an autoscaled axis
        # renders [140, 150] and makes 93%-of-the-way-there look like a
        # chasm. The metric name is the honest signal, not the label.
        exprs = " ".join(t.get("expr") or ""
                         for t in panel.get("targets") or [])
        if (_ZERO_ANCHOR.search(title) or _ZERO_ANCHOR.search(exprs)) \
                and not fc.get("unit") and fc.get("min") is None:
            fc["min"] = 0
            fc.setdefault("custom", {})["axisSoftMin"] = 0
        # One legend shape board-wide. The table legend carries exact
        # last/min/max beside the trend, which is the whole point of
        # plotting a trend you intend to act on.
        lg = panel.setdefault("options", {}).setdefault("legend", {})
        if lg.get("displayMode") != "table":
            lg["displayMode"] = "table"
            lg["placement"] = "bottom"
            lg["showLegend"] = True
            if not lg.get("calcs"):
                lg["calcs"] = ["lastNotNull", "min", "max"]
    return panel


def _hig_all(d):
    for p in d.get("panels") or []:
        _hig_pass(p)
        for sub in p.get("panels") or []:
            _hig_pass(sub)
    return d


DASHBOARDS = {
    "liquiditybot_command.json": _board(
        "liquiditybot-trading", "liquiditybot — trading desk",
        "Exchange-style daily driver: equity & P&L vs the rent goal, spot "
        "positions & risk, performance & bracket-geometry economics, profit "
        "pools, per-asset edge.", _author_command, "command"),
    "liquiditybot_execution.json": _board(
        "liquiditybot-exec", "liquiditybot — models · learning · execution",
        "Decision-model health, the learning brain & trajectory, admission "
        "detail, probe budget, and execution fill quality (maker/taker, "
        "slippage, mark-out).", _author_execution, "execution"),
    "liquiditybot_problem_solution.json": _board(
        "liquiditybot-problem-solution", "liquiditybot — problem / solution",
        "Every failure mode as a PROBLEM whose panel shows the live detector "
        "and names the SOLUTION mechanism handling it — including the audit "
        "chain's and telemetry's own health.", _author_problem,
        "diagnostics"),
    "liquiditybot_screening.json": _board(
        "liquiditybot-screening", "liquiditybot — screening & market",
        "Asset screening & market context: skimmer ranks, per-asset "
        "tradeability scorecard, regime, macro cycle context, THALES "
        "manipulation defense.", _author_screening, "screening"),
}
for _d in DASHBOARDS.values():
    _apple_palette(_d)
    _hig_all(_d)
    _tags = set(_d.get("tags") or [])
    _tags.add("liquid-glass")
    _d["tags"] = sorted(_tags)

OUT_DIR = Path(__file__).resolve().parents[1] / "docs" / "grafana"

if __name__ == "__main__":
    for fname, d in DASHBOARDS.items():
        out = OUT_DIR / fname
        out.write_text(json.dumps(d, indent=2, ensure_ascii=False),
                       encoding="utf-8")
        print(f"wrote {out} — {len(d['panels'])} panels ({d['title']})")
