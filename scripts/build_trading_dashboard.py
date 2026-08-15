"""scripts/build_trading_dashboard.py — generator for the trading dashboards.

THIS GENERATOR IS THE SOURCE OF TRUTH: edit here and regenerate; never
hand-edit the JSONs. tests/test_trading_dashboard.py enforces (1) generator ==
shipped JSON, (2) importable shape / no overlapping panels, (3) every metric a
panel queries is emitted by scripts/gc_pusher.py, (4) only supported panel
types.

DESIGN — professional and readable, information-dense but not a wall of raw
numbers. Grounded in referenced practice: Grafana's dashboard best practices
(one purpose per board, most-important top-left, no orphan queries), the
RED/USE methods for the ops rows (rate/errors/duration; utilization/
saturation/errors), and Tufte's data-ink principle for the analytics panels
(exact values beside every trend; no decoration that isn't data). One Liquid
Glass visual language across four focused boards (transparent panels, Apple
system palette, value-only state tiles, basic-mode bar gauges, outer-joined
tables, a Business Text frosted-skin CSS injector — see
docs/grafana/README_glass.md):
  * ACCURACY FIRST: every money panel uses the non-scaling USD unit (see
    below) so the number displayed IS the number the bot holds — no "$5.00K"
    for $4,997.92; the equity curve carries a last/min/max legend table;
  * KPI tiles are stat panels with an AREA SPARKLINE (trend at a glance) and
    threshold color;
  * bounded ratios (exposure, heat, win rate, drawdown) are GAUGES;
  * per-entity comparisons are horizontal basic-mode BAR GAUGES (one bar per
    asset/pair) — the eye ranks them instantly;
  * a couple of real TIME-SERIES carry the trends that matter (equity, Brier);
  * dense detail lives in COLOR-CODED tables (heatmap cells);
  * live STATE readouts (RUNNING/HALTED, ARMED/KILLED) are colored tiles;
  * the Learning row surfaces CORPUS QUALITY (clean live count, AFML mean
    uniqueness, ML-074 prior-skew) — the bot's evidence accounting, live.
Every board links to the others (top nav) and uses emoji section headers for
fast scanning.

Boards:
  liquiditybot_command.json          — daily driver
  liquiditybot_execution.json        — models · inventory · execution
  liquiditybot_problem_solution.json — problem / solution diagnostics
  liquiditybot_screening.json        — asset screening
  liquiditybot_pulse.json            — one full-width Business Text hero
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
def _author_command():
    _pulse_hero()          # the board opens on the one-glance pulse screen
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
    # 3x8 at h=4, not 2x12 at h=3 (2026-08-02): the h=3 band was the only
    # 3-high row on the board and sat directly under a 4-high one, which is
    # the raggedness you notice without being able to name. Matching the
    # height above also makes room for the era-mix alarm, which belongs with
    # the other alarms rather than buried in the learning section.
    stat("Feed latency", M("liquiditybot_feed_latency_ms"), 8, 4, unit="ms",
         decimals=0, steps=LAT, size="compact",
         desc="Kraken public-GET RTT EWMA.")
    stat("Cycle", M("liquiditybot_cycle"), 8, 4, decimals=0, steps=BLUE,
         size="compact", desc="Fast-cycle counter (advancing = alive).")
    state("Era mix", M("liquiditybot_era_mix_alarm"), 8, 4, ERA_MIX,
          desc="Training corpus vs live label era. DRIFTED means the rows "
               "the model learns from no longer match the geometry it "
               "trades under — see Era mix drift (TVD) on the execution "
               "board for the magnitude.")

    row("💹 MONEY — equity & P&L")
    timeseries("Equity curve", M("liquiditybot_equity"), 12, 8,
               unit=USD, legend="equity", decimals=2,
               calcs=["lastNotNull", "min", "max"], colors={"equity": GREEN},
               desc="Account equity over time — exact dollars (no "
                    "K-rounding); the legend table shows last/min/max to "
                    "the cent.")
    stat("P&L today", M("liquiditybot_daily_pnl"), 6, 8, unit=USD,
         steps=PNL, size="hero", desc="Realized P&L since UTC midnight.")
    stat("Open uPnL", M("liquiditybot_open_upnl_usd"), 6, 8, unit=USD,
         steps=PNL, size="hero", desc="Unrealized across open positions.")

    # Band 2 — OUTCOME (2026-08-02). This row carried equity, drawdown and
    # win rate but never the cumulative bottom line: perf_net_usd was pushed
    # to Grafana on every tick and shown on NO board, so "is it losing
    # money" could only be answered by reading a curve's shape. Net $ and
    # goal attainment are the two numbers the operator opens this board for,
    # so they lead, at hero size, before any mechanism.
    # Three-series P&L taxonomy (institutional review condition, 2026-08-07):
    # this tile used to be titled "Net P&L (all time)" while reading
    # perf_net_usd — a rolling 200-close hedge-excluded ring, NOT all time.
    # The two series legitimately disagree (ring −56.91 vs ledger −208.22
    # at review time); the label was the lie. Each series now carries its
    # true name, and the fee ledger — the ONLY counter where an open leg's
    # entry fee is visible before its close (record_entry_fee debits cash
    # at fill; no P&L counter sees it until the trade closes) — gets a
    # tile of its own instead of being invisible on every board.
    stat("Net P&L (all time)", M("liquiditybot_net_pnl_all_time"), 6, 5,
         unit=USD, steps=PNL, size="hero",
         desc="equity − starting capital: the ONE figure that cannot drift "
              "from the money, because it is measured rather than "
              "accumulated. Repointed 2026-08-09 from realized_total, which "
              "is net of the CLOSING fee leg only and so hid 49% of "
              "lifetime fees (−208.31 shown against a true −383.48). "
              "Includes unrealized. Paper while system.dry_run is true.")
    stat("Realized (closing-leg basis)", M("liquiditybot_realized_total"),
         6, 5, unit=USD, steps=PNL,
         desc="The old hero tile, kept and correctly named. Monotonic "
              "realized P&L across every close, hedges included — but a "
              "trade's OPENING fee never enters it, so it reads better than "
              "the truth. Compare with 'Realized (all-in)'.")
    stat("Realized (all-in)", M("liquiditybot_realized_net_all_in"), 6, 5,
         unit=USD, steps=PNL,
         desc="realized_total − entry_fees_total: realized P&L net of BOTH "
              "fee legs. Excludes unrealized, so it is the harshest honest "
              "read of closed business.")
    stat("Net P&L (last 200 closes)", M("liquiditybot_perf_net_usd"), 6, 5,
         unit=USD, steps=PNL,
         desc="Rolling ring of the last 200 non-hedge closes — recent "
              "form, not the lifetime ledger. Diverges from all-time by "
              "construction: it forgets old trades and excludes hedges.")
    stat("Fees paid (all time)", M("liquiditybot_fees_total"), 6, 5,
         unit=USD, decimals=2, steps=GRN,
         desc="Every venue fee ever booked, BOTH legs at fill time "
              "(state.fees_paid_total). The one counter where an open "
              "position's entry fee is visible before the close — cash "
              "each entry spends that no P&L tile can see yet. Simulated "
              "at configured bps while paper.")
    stat("Goal attainment", 'max(liquiditybot_goal_attainment_pct'
         '{period="month",job="liquiditybot"})', 6, 5, unit="percent",
         decimals=1, steps=WR100, size="hero",
         desc="Progress toward the monthly goal (liquiditybot_goal_target). "
              "Emitted since the goals ledger shipped and never displayed, "
              "so the target existed with no way to see distance from it.")
    stat("Equity", M("liquiditybot_equity"), 12, 5, unit=USD,
         decimals=2, steps=GRN, desc="Account equity (cash + open uPnL).")
    gauge("Drawdown (MTM, governs the hard stop)",
          M("liquiditybot_rp_drawdown_mtm_pct"), 6, 5, mx=15.0, steps=DD,
          desc="Peak-to-now on MARK-TO-MARKET equity — the basis the "
               "catastrophe hard stop and the sizer throttle actually use. "
               "This panel previously plotted liquiditybot_drawdown_pct, "
               "which measures from STARTING CAPITAL on cash+savings only "
               "and ignores unrealized loss: the description said "
               "'peak-to-now' while the metric said something else, so a "
               "book underwater on marks could read calm here while the "
               "throttle was already biting.")
    gauge("Drawdown (realized, from start)", M("liquiditybot_drawdown_pct"),
          6, 5, mx=15.0, steps=DD,
          desc="From starting capital, cash + savings only — blind to "
               "unrealized loss and to any high-water above start. Kept "
               "because it is what the daily/weekly budget ledger reasons "
               "about; it is NOT the hard-stop basis.")

    # Band 3 — TRADE QUALITY. Win rate alone is not a quality measure: a 30%
    # win rate with a 3.0 payoff ratio is profitable and a 60% win rate with
    # a 0.4 payoff ratio is not, so the two belong side by side and were not.
    gauge("Win rate", M("liquiditybot_perf_win_rate", "*100"), 5, 5, mx=100.0,
          steps=WR100, desc="Rolling closed-trade win rate.")
    stat("Payoff ratio", M("liquiditybot_perf_payoff_ratio"), 5, 5,
         decimals=2, steps=PAYOFF,
         desc="Average win / average loss. The other half of win rate — "
              "below 1.0 every winner is smaller than every loser, so the "
              "win rate has to clear 1/(1+payoff) just to break even.")
    stat("Profit factor", M("liquiditybot_perf_profit_factor"), 5, 5,
         decimals=2, steps=PF, desc="Gross profit / gross loss.")
    # Probe vs conviction, side by side rather than blended. A probe is a
    # deliberately small exploratory ticket and a conviction trade is the
    # real thesis; one pooled expectancy describes neither, because the
    # probes drag the mean toward zero while the conviction trades carry the
    # variance. kind="unknown" holds trades restored from a snapshot written
    # before the split existed and drains as the rolling window turns over.
    stat("Expectancy · conviction",
         'liquiditybot_perf_conviction_expectancy_usd'
         '{kind="conviction",job="liquiditybot"}', 5, 5, unit=USD,
         decimals=4, steps=PNL,
         desc="Average $ per REAL-thesis close. The number that answers "
              "'is the strategy working', with exploratory probes taken "
              "out of it.")
    stat("Expectancy · probe",
         'liquiditybot_perf_conviction_expectancy_usd'
         '{kind="probe",job="liquiditybot"}', 5, 5, unit=USD,
         # BLUE, not PNL (design-token audit 2026-08-10): a probe's
         # expectancy is EXPECTED slightly negative - it buys information.
         # PNL steps would paint this tile red in normal operation, and a
         # tile that is red when nothing is wrong trains alarm fatigue.
         # Neutral-info semantics; the money verdict lives in the
         # conviction tile beside it.
         decimals=4, steps=BLUE,
         desc="Average $ per exploratory probe close. Expected to be "
              "small and slightly negative — probes buy information, not "
              "P&L. Judge it against the information, not against zero.")
    stat("Probe / conviction mix",
         'liquiditybot_perf_conviction_trades{kind="probe",job="liquiditybot"}'
         ' / clamp_min(sum(liquiditybot_perf_conviction_trades'
         '{job="liquiditybot"}), 1)', 4, 5, unit="percentunit",
         decimals=1, steps=BLUE, graph="none",
         desc="Share of closes that were probes. If this drifts high the "
              "headline expectancy is mostly measuring exploration cost.")
    stat("Expectancy R", M("liquiditybot_perf_expectancy_r"), 5, 5,
         decimals=2, steps=PNL, desc="Avg trade in R-multiples.")
    stat("Worst streak", M("liquiditybot_perf_max_loss_streak"), 4, 5,
         decimals=0, steps=STREAK, graph="none", size="compact",
         desc="Longest run of consecutive losers ever recorded. The board "
              "showed the CURRENT streak but not the worst, so there was "
              "nothing to judge the current one against.")

    row("🏦 PROFIT POOLS — weekly rollover", collapsed=True)
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

    _risk_row()
    _edge_row()
    _longbook_row()


def _learning_brain():
    """The learning section, ordered as the FUNNEL it actually is.

    REDESIGNED 2026-08-02. It was fourteen identical 4-wide tiles in no
    particular order followed by two charts. Three things made it unreadable:

      1. No order. "Live labels" sat eight tiles away from "Clean live
         labels" — the same funnel stage, one the filtered version of the
         other — so the attrition between them, which is the single most
         diagnostic number in the section, had to be computed by eye across
         half a screen.
      2. No hierarchy. Fourteen tiles at identical size say every number
         matters equally. They do not: clean live labels gates retraining,
         batch prior skew is a footnote.
      3. Ragged bands. Fourteen tiles at w=4 wrap 6/6/2, so the section
         ended on a third-empty row.

    Now it reads top to bottom as the four questions the loop answers in
    sequence — does data arrive, is the corpus clean, is the model any good,
    is it allowed to trade — with every band exactly 24 wide. The order IS
    the explanation, which is why the header panel can stay short.
    """
    row("🧠 LEARNING BRAIN", collapsed=True)
    text("How to read this — and what to do about it", _BRAIN_GUIDE, 24, 9)

    # --- 1. SUPPLY: does training data arrive at all? -----------------
    # Read left to right as a funnel: candidate proxies, of which some are
    # real closed trades, of which some survive hygiene. Clean live is the
    # count the evidence gate admits complexity on, so it is the hero.
    stat("Candidate labels",
         'max(liquiditybot_ml_labels{source="candidate",job="liquiditybot"})',
         6, 5, decimals=0, steps=BLUE, size="compact",
         desc="1/4 SUPPLY · Triple-barrier proxy labels — the widest part "
              "of the funnel.")
    stat("Live labels",
         'max(liquiditybot_ml_labels{source="live",job="liquiditybot"})',
         6, 5, decimals=0, steps=[{"color": "red", "value": None},
         {"color": "yellow", "value": 30}, {"color": "green", "value": 60}],
         desc="2/4 SUPPLY · Ground-truth closed-trade labels — earns model "
              "complexity.")
    stat("Clean live labels", M("liquiditybot_ml_live_clean"), 6, 5,
         decimals=0, size="hero",
         steps=[{"color": "red", "value": None},
                {"color": "yellow", "value": 30},
                {"color": "green", "value": 60}],
         desc="3/4 SUPPLY · Live rows surviving the hygiene pass — the "
              "count the evidence gate actually admits model complexity "
              "on. Sits beside Live labels so the attrition between them "
              "is one glance, not arithmetic across the section.")
    stat("New-era rows", M("liquiditybot_era_excl_new_rows"), 6, 5,
         decimals=0, steps=[{"color": "text", "value": None},
         {"color": "green", "value": 150}],
         desc="4/4 SUPPLY · Corpus rows tagged the NEW label era "
              "(triple_barrier). Arms the era exclusion at 150 "
              "(min_new_era_rows) — the floor past which old-era rows stop "
              "training the model.")

    # --- 2. CORPUS HEALTH: is the data it trains on trustworthy? ------
    stat("Label uniqueness", M("liquiditybot_ml_mean_uniqueness"), 6, 5,
         decimals=3, steps=[{"color": "red", "value": None},
         {"color": "yellow", "value": 0.05}, {"color": "green", "value": 0.15}],
         desc="CORPUS · Mean average-uniqueness (AFML ch.4): 1 = every "
              "label an independent fact; near 0 = heavily overlapping "
              "horizons (weights redistribute so overlap can't "
              "double-count). A big label count with low uniqueness is a "
              "small sample wearing a big number.")
    state("Era exclusion", M("liquiditybot_era_excl_active"), 6, 5,
          {"0": ("INERT", "blue"), "1": ("ACTIVE", "green")},
          desc="CORPUS · ACTIVE = old-era rows (legacy/exit_sim/"
               "exit_sim_time_stop), INCLUDING live, are excluded from "
               "training — see liquiditybot_era_excl_dropped for the row "
               "count.")
    state("Batch prior skew", M("liquiditybot_ml_prior_skew"), 6, 5,
          {"0": ("OK", "green"), "1": ("SKEWED", "yellow")},
          no_value="no batch yet",
          desc="CORPUS · ML-074: trailing-window label prior vs corpus "
               "prior — SKEWED = a one-sided batch (e.g. all-zero quiet "
               "weekend) is moving calibration; detection only, weights "
               "untouched.")
    gauge("Drift share", M("liquiditybot_ml_drift_share", "*100"), 6, 5,
          mx=100.0, steps=[{"color": "green", "value": None},
          {"color": "yellow", "value": 30}, {"color": "red", "value": 50}],
          desc="CORPUS · Fraction of features past the PSI threshold — the "
               "world moving out from under the training set.")

    # --- 3. MODEL QUALITY: is what it learned any good? ---------------
    stat("Model", "count(liquiditybot_ml_model_info" + JOB + ") by (kind)",
         8, 5, desc="QUALITY · Deployed rung on the simplicity ladder — "
                    "complexity is earned by clean live labels, not chosen.",
         text_mode="name", display_name="${__field.labels.kind}",
         steps=BLUE, graph="none")
    stat("Calibration gap", M("liquiditybot_ml_calibration_gap"), 8, 5,
         # 2026-07-29 anomaly-audit #4: the old no_value text claimed the
         # ML-075 shadow state, but the metric is simply absent until the
         # ECE window holds >= min_trades_to_judge (15) model-scored
         # closes of the last 30 (ml/monitor.py) - a filling window is
         # not a stand-down, and "Model in use: YES" beside it was read
         # as a contradiction.
         unit="percentunit", decimals=1, steps=CALIB,
         no_value="window filling (<15 model-scored closes)",
         desc="QUALITY · ECE — how far stated probabilities sit from "
              "realized rates. Kelly reads probs literally, so this is a "
              "sizing error, not a scoring nicety.")
    stat("Win rate LCB", M("liquiditybot_perf_win_rate_lcb", "*100"), 8, 5,
         unit="percent", decimals=1, steps=GRN,
         desc="QUALITY · Wilson lower bound on the win rate — what the "
              "evidence supports rather than what the point estimate "
              "flatters. A high win rate on few trades lands here honestly.")

    # --- 4. GOVERNOR: is the model allowed to size trades? ------------
    state("Model in use", M("liquiditybot_ml_use_model"), 8, 5, ON_OFF,
          desc="GOVERNOR · Governor lets the model size trades; NO is a "
               "stand-down, not a fault.")
    stat("Kelly mult", M("liquiditybot_ml_kelly_mult"), 8, 5, decimals=2,
         steps=GRN, desc="GOVERNOR · Size throttle applied to the Kelly "
                         "fraction — 1.0 is full trust, 0 is muted.")
    state("Retrain", M("liquiditybot_ml_retrain_flag"), 8, 5, RETRAIN,
          desc="GOVERNOR · Auto-retrain queued.")

    # --- trends, last: the tiles say where it stands, these say where
    # --- it is heading. Same order as the funnel above.
    timeseries("Learning rows by label (live vs candidate)",
               'max by (source) (liquiditybot_ml_labels' + JOB + ')', 12, 7,
               unit="short", legend="{{source}}",
               calcs=["lastNotNull", "min", "max"],
               colors={"live": GREEN, "candidate": GRAY_HEX},
               desc="Ground-truth LIVE (real closed-trade) labels vs "
                    "CANDIDATE (triple-barrier proxy) labels accruing over "
                    "time — the learning loop turning. LIVE climbing past "
                    "35 = ML-073 realizing ground truth; a flat LIVE line "
                    "= the loop is starved.")
    timeseries("Brier — live vs champion vs baseline (lower = better)",
               M("liquiditybot_ml_brier"), 12, 7, legend="live",
               decimals=4, calcs=["lastNotNull", "min", "max"],
               extra=[(M("liquiditybot_ml_champion_brier"), "champion"),
                      (M("liquiditybot_ml_baseline_brier"), "baseline")],
               colors={"live": INDIGO, "champion": CAT_TEAL,
                       "baseline": CAT_PURPLE},
               desc="Rolling outcome Brier: live vs deployed champion vs "
                    "the base-rate baseline the model must undercut. Above "
                    "the baseline means the model is worse than guessing "
                    "the base rate.")
    timeseries("Label rate by era",
               'max by (era) (liquiditybot_era_label_rate' + JOB + ')',
               24, 6, unit="percentunit", legend="{{era}}", decimals=2,
               calcs=["lastNotNull", "min", "max"],
               desc="Per-era label rate on the surviving corpus — the "
                    "instrument that shows the 0.0066 (exit_sim_time_stop) "
                    "-> 0.3991 (triple_barrier) repair as the new era "
                    "takes over.")


def _edge_row():
    row("⚖️ EDGE — per-asset performance", collapsed=True)
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
                ("liquiditybot_signal_confidence", "Confidence", "short", 2, HIGH_GOOD, "text"),
                ("liquiditybot_signal_concentration", "Concentration", "short", 2, HIGH_GOOD, "text"),
                ("liquiditybot_signal_urgency", "Urgency", "short", 2),
                ("liquiditybot_manip_suspect", "Manip", "short", 2, LOW_GOOD),
                ("liquiditybot_regime_spread_bps", "Spread bps", "short", 1, SPREAD),
                ("liquiditybot_regime_vol_pct", "Vol %", "percent", 1)],
          label_keys=["asset"], sort="Net $",
          desc="One row per asset; color-coded so a green row (positive "
               "net, high concentration, low manip, tight spread) reads "
               "instantly. Absent cells (·) mean the asset hasn't traded "
               "yet — not a fault.")


def _context_row():
    row("🌐 CONTEXT — cycle & macro state", collapsed=True)
    stat("Halving phase", "count(liquiditybot_context_phase" + JOB +
         ") by (phase)", 6, 5, text_mode="name", steps=BLUE, graph="none",
         display_name="${__field.labels.phase}",
         no_value="no context poll yet",
         desc="Days-since-halving bucket — a labeled CONVENTION over n=3 "
              "completed halving cycles (evidence doc "
              "2026-07-24_compounder_context_evidence.md), not a "
              "statistical finding. Telemetry only this phase.")
    stat("Days since halving", M("liquiditybot_context_days_since_halving"),
         6, 5, decimals=0, steps=BLUE, no_value="no context poll yet",
         desc="Pure UTC calendar-date math from the last chain-history "
              "halving date.")
    stat("Days to next halving", M("liquiditybot_context_days_to_next_halving"),
         6, 5, decimals=0, steps=BLUE, no_value="no context poll yet",
         desc="To the configured next_halving_date — a block-clock "
              "ESTIMATE, not a fact.")
    gauge("Macro stress", M("liquiditybot_context_stress"), 6, 5, mn=-2,
          mx=2, unit="short", decimals=2,
          no_value="unknown this cycle — check Sources ok / next poll",
          desc="Mean of three clip_z terms (funding-rate delta, "
               "yield-curve inversion, VIX); absent (not zero) when any "
               "of the three sources is dark — see Sources ok below.")
    stat("COT z (crowding)", M("liquiditybot_context_cot_z"), 8, 5,
         decimals=2, steps=BLUE, no_value="unknown — no prior COT read yet",
         desc="Leveraged-funds net-position weekly delta, clip-z'd. A "
              "crowding/fragility dial for JOINT reading with basis_bps "
              "(pass-2 §1.3c) — never a signed directional input alone.")
    stat("Stablecoin Δ (wk %)", M("liquiditybot_context_stable_wk_pct"), 8, 5,
         unit="percent", decimals=2, steps=BLUE,
         no_value="unknown — no prior stablecoin read yet",
         desc="Week-over-week %change in total circulating stablecoin "
              "USD (DefiLlama) — an independent flow dial from COT.")
    state("Event window", M("liquiditybot_context_event_window"), 8, 5,
          CONTEXT_EVENT,
          desc="CME BTC futures expiry / FOMC cadence-pause window "
               "(spec §3.4) — gates cadence only, never direction.")
    bargauge("Sources ok", _pa("liquiditybot_context_source_ok"), 24, 5,
             decimals=0, steps=HIGH_GOOD, mn=0, mx=1, legend="{{source}}",
             no_value="no context poll yet",
             desc="Per-source freshness (3x-poll-cadence grace, mirroring "
                  "webdata_feed.py): a dark source degrades its dial to "
                  "unknown — a STATE, never a stale value read as fresh.")


def _longbook_row():
    row("🌱 LONG BOOK — evidence ladder", collapsed=True)
    state("Rung", M("liquiditybot_longbook_rung"), 6, 5, LB_RUNG,
          no_value="long book disabled/not built",
          desc="Evidence ladder (spec §5): rung 0 is paper-only; r1-r3 "
               "unlock progressively wider LIVE ceilings on realized, "
               "book-tagged closes. A drawdown breach drops one rung "
               "instantly; re-earning it back is gradual (redemption).")
    gauge("Ceiling", M("liquiditybot_longbook_ceiling_frac", "*100"), 6, 5,
          no_value="long book disabled/not built",
          desc="Equity-fraction ceiling for the CURRENT track (paper "
               "floors at r1 regardless of earned rung; live is 0 at "
               "rung 0) — bounded by the shared combined-envelope 35% "
               "portfolio heat cap; the long book never gets its own "
               "risk stack.")
    stat("Book exposure", M("liquiditybot_longbook_exposure_usd"), 6, 5,
         unit=USD, decimals=2, steps=GRN,
         no_value="long book disabled/not built",
         desc="Open long-book position notional + resting entry-order "
              "notional, book-wide across every configured asset.")
    stat("Adds placed", M("liquiditybot_longbook_adds_placed"), 6, 5,
         decimals=0, steps=BLUE, no_value="long book disabled/not built",
         desc="Post_only maker bids placed since boot — averaging adds "
              "into the book's one growing position per asset (never a "
              "second same-book position, never a short).")
    state("Paused", M("liquiditybot_longbook_paused"), 6, 5, LB_PAUSED,
          no_value="long book disabled/not built",
          desc="Last add-cycle disposition: any deny (spacing wait, "
               "ceiling exhaustion, context gate, event window, halt) "
               "reads paused. New-risk cadence only — exits are always "
               "allowed regardless of this state.")
    stat("PF (live)", M("liquiditybot_longbook_pf_live"), 6, 5, decimals=2,
         steps=PF, no_value="no live closes yet",
         desc="Running live-track profit factor — the same evidence r2/r3 "
              "gate on (pf_floor).")
    bargauge("Closed (paper vs live)", _pa("liquiditybot_longbook_closed"),
             12, 5, decimals=0, steps=BLUE, legend="{{track}}",
             no_value="no closes yet",
             desc="Realized book-tagged closes per evidence track — the "
                  "ladder's raw input (r1 gates on paper evidence; r2/r3 "
                  "gate on live evidence + live profit factor).")


def _thales_row():
    row("🏛️ THALES — footprint & manipulation defense", collapsed=True)
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
                  "painted; THALES shades size there. Wall-time "
                  "normalized 2026-07-29: the score no longer depends on "
                  "poll cadence, only on the spoofer's actual flip rate.")
    bargauge("Stop-hunt zone proximity", _pa("liquiditybot_thales_stop_zone"),
             8, 6, decimals=2, steps=LOW_GOOD, mn=0, mx=1, legend="{{asset}}",
             desc="Proximity to round-number stop clusters per asset. "
                  "2026-07-29 recalibration: the geometric base rate "
                  "(tolerance band / magnet spacing) is now subtracted, "
                  "so a random mark reads ~0 — before this the gauge sat "
                  "at 0.4-0.5 everywhere the price grid was fine (43% of "
                  "history >0.5 with zero PnL discrimination). A high "
                  "reading now means the mark is genuinely AT a magnet.")
    bargauge("Manipulation suspicion", _pa("liquiditybot_manip_suspect"),
             8, 6, decimals=2, steps=LOW_GOOD, mn=0, mx=1, legend="{{asset}}",
             desc="Parameter-free max of the manipulation footprints per "
                  "asset.")
    table("Detector reliability — lift over base rate (earning its keep)",
          12, 7,
          cols=[("liquiditybot_thales_rel_fired", "Graded", "short", 0,
                 BLUE),
                ("liquiditybot_thales_rel_vindicated", "Vindicated",
                 "short", 0, BLUE),
                ("liquiditybot_thales_rel_weight", "Weight", "short", 2,
                 GRN)],
          label_keys=["detector"], sort="Graded",
          desc="THALES V2 vindication ledger (2026-07-29 unlock): every "
               "closed model-lane trade grades the detectors that advised "
               "on its entry — in SHADOW mode too, so this is the "
               "promotion-to-advise evidence accruing live. Weight = the "
               "detector's Wilson-LCB win/loss lift over the base rate "
               "below (0 = no proven edge over just knowing the base "
               "rate; the shade gain scales by it in advise mode). Empty "
               "table = ledger still accruing its first min_fired=20 "
               "grades per detector.")
    stat("Graded closes", M("liquiditybot_thales_base_graded"), 6, 7,
         decimals=0, steps=BLUE, no_value="accruing — 0 graded closes",
         desc="Closed trades graded into the THALES reliability ledger "
              "(the __base__ null's sample size). Started counting "
              "2026-07-29 — was structurally stuck at 0 before (grading "
              "was advise-gated while promotion required shadow "
              "evidence).")
    stat("Base win rate", M("liquiditybot_thales_base_win_rate", "*100"),
         6, 7, unit="percent", decimals=1, steps=BLUE,
         no_value="accruing — needs graded closes",
         desc="Win rate across ALL graded closes — the null each "
              "detector must BEAT to earn shade weight ('up' advice vs "
              "this, 'down' advice vs its complement). The 2026-07-29 "
              "correction replaced the old 0.5 coin-flip null that muted "
              "honest detectors on a ~16%-win stream.")


def _risk_row():
    row("🛡️ POSITIONS & RISK")
    _positions_table()
    bargauge("uPnL by instrument", _pa("liquiditybot_position_upnl_usd"), 12, 5,
             unit=USD, decimals=2, steps=PNL, legend="{{symbol}} {{side}}",
             no_value="flat — no open positions",
             desc="Unrealized P&L ranked across open instruments.")
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
          cols=[("liquiditybot_gate_weight", "Weight", "short", 3, HIGH_GOOD, "text")],
          label_keys=["gate"], sort="Weight", desc="Evidence weight per gate.")
    gauge("Gross exposure", M("liquiditybot_gross_exposure_pct"), 6, 5,
          mx=35.0, desc="Gross notional %/equity vs the 35% heat cap.")
    stat("Positions open", M("liquiditybot_positions_open"), 6, 5, decimals=0,
         steps=BLUE, graph="none", desc="Open count (max 5).")


def _learning_trajectory():
    """Trend row: the questions a stat tile structurally cannot answer.

    WHY THIS ROW EXISTS (2026-08-01). Before it, 8 of 175 panels were
    timeseries — roughly 21 state tiles per trend panel. State tiles answer
    "is it healthy" very well, and that is most of what these boards are for.
    But "is it learning" and "is it losing money" are TRAJECTORY questions,
    and a tile shows a number, never a direction.

    That gap had a real cost: live_clean sat pinned at 0 for thirteen days
    and the board could not distinguish it from a value that had merely
    touched 0 on the current scrape, because a tile has no memory. Each
    panel here plots the pair of series whose DIVERGENCE is the signal, so
    the reading needs no mental arithmetic across two tiles.

    Every metric below is verified present in the exporter. A panel querying
    a metric the bot never emits is worse than no panel: it renders an empty
    chart that reads as "zero" rather than "absent".
    """
    row("📈 LEARNING TRAJECTORY — direction, not position")
    timeseries(
        "Label supply — is training data arriving?",
        M("liquiditybot_ml_live_clean"), 12, 8, legend="live_clean",
        decimals=0, calcs=["lastNotNull", "min", "max"],
        extra=[('max(liquiditybot_ml_labels'
                '{source="live",job="liquiditybot"})', "live"),
               ('max(liquiditybot_ml_labels'
                '{source="candidate",job="liquiditybot"})', "candidate")],
        colors={"live_clean": "#30D158", "live": "#0A84FF",
                "candidate": "#FFD60A"},
        desc="The three label pools over time. live_clean gates retraining; "
             "it was pinned at 0 for thirteen days and no tile could show "
             "that. FLAT is the alarm here, not the all-clear.")
    timeseries(
        "Era exclusion — progress toward re-arming",
        M("liquiditybot_era_excl_new_rows"), 12, 8, legend="new-era rows",
        decimals=0, calcs=["lastNotNull", "min", "max"],
        extra=[(M("liquiditybot_era_excl_min_rows"), "threshold")],
        colors={"new-era rows": "#30D158", "threshold": "#FF453A"},
        desc="New-era rows against the min_rows threshold that arms "
             "era-gated training. Both are plotted so the GAP is the visible "
             "quantity — distance to the threshold is what you actually want "
             "to read, and two separate tiles make you subtract by hand.")
    timeseries(
        "Calibration quality — is the model honest?",
        M("liquiditybot_ml_calibration_gap"), 12, 8, unit="percentunit",
        legend="calibration gap", decimals=1,
        calcs=["lastNotNull", "min", "max"],
        extra=[(M("liquiditybot_ml_mean_uniqueness"), "label uniqueness")],
        colors={"calibration gap": "#FF453A",
                "label uniqueness": "#0A84FF"},
        desc="A gap that WIDENS while labels accumulate means the model is "
             "learning the wrong thing — the one failure mode that looks "
             "identical to healthy progress on a state tile.")
    timeseries(
        "Admission funnel — is the gate passing anything?",
        M("liquiditybot_conviction_evaluated"), 12, 8, legend="evaluated",
        decimals=0, calcs=["lastNotNull", "min", "max"],
        extra=[(M("liquiditybot_conviction_admitted"), "admitted")],
        colors={"evaluated": "#0A84FF", "admitted": "#30D158"},
        desc="A gate whose admitted line rides at zero while evaluated "
             "climbs is selecting against itself — which is what "
             "scripts/gate_efficacy_report.py measured at -12.2% "
             "separation. The divergence is the signal; neither line alone "
             "shows it.")


def _positions_table():
    table("Open positions (net per instrument)", 12, 5,
          cols=[("liquiditybot_position_upnl_usd", "uPnL $", USD, 2, PNL, "text"),
                ("liquiditybot_position_upnl_pct", "uPnL %", "percent", 2, PNL, "text"),
                ("liquiditybot_position_r_multiple", "R", "short", 2, PNL, "text"),
                ("liquiditybot_position_notional_usd", "Notional $", USD, 0),
                ("liquiditybot_position_conviction", "p_win", "percentunit", 2, HIGH_GOOD, "text"),
                ("liquiditybot_position_stop_dist_pct", "Stop %", "percent", 2),
                ("liquiditybot_position_age_hours", "Age h", "short", 1)],
          label_keys=["symbol", "side"], sort="uPnL $",
          drop=tuple(f"side {i}" for i in range(2, 8)),
          desc="Open instruments; green uPnL/R rows are working, red need "
               "managing.")


# ================= board 2 · models · inventory · execution ================
def _author_execution():
    row("🧠 DECISION MODEL")
    # Telemetry age FIRST on every board (2026-07-26): this board carries the
    # Brier timeseries but had NO staleness cue at all, so during the 11.8h
    # outage every tile here showed a confident pre-crash number with nothing
    # to say the bot was dead. Value tiles reduce with lastNotNull, which
    # keeps painting the last push forever; the age tile is what makes that
    # honest. Same thresholds as the Command board's copy.
    stat("Telemetry age", M("liquiditybot_status_age_sec"), 4, 5, unit="s",
         decimals=0, mode="background", graph="none",
         steps=[{"color": "green", "value": None},
                {"color": "yellow", "value": 120},
                {"color": "red", "value": 300}],
         desc="Seconds since the runner last wrote status.json. Red = the "
              "numbers on this board are stale, not calm.")
    stat("Model", "count(liquiditybot_ml_model_info" + JOB + ") by (kind)",
         4, 5, text_mode="name", steps=BLUE, graph="none",
         display_name="${__field.labels.kind}",
         desc="Deployed rung (evidence-gated).")
    state("Model in use", M("liquiditybot_ml_use_model"), 4, 5, ON_OFF,
          desc="Model sizes trades vs the cold-start prior; NO is a "
          "stand-down, not a fault.")
    state("Governor", M("liquiditybot_monitor_level"), 4, 5, GOV,
          desc="0 OK / 1 degraded / 2 killed.")
    # unit=percentunit, NOT the gauge() default of percent (2026-08-01).
    # calibration_gap is Expected Calibration Error, |predicted p - realized
    # rate|, so it is a FRACTION in [0,1] — which is why mx is 0.2 and not
    # 20. Grafana's "percent" treats the value as ALREADY a percentage, so a
    # real gap of 0.05 printed as "0.050%" instead of "5.0%": the needle sat
    # in the right place while the number beside it read 100x too small, and
    # the same metric rendered "5.0%" on the command board. percentunit does
    # the x100 for display and leaves the 0.2 scale correct.
    gauge("Calibration gap", M("liquiditybot_ml_calibration_gap"), 4, 5,
          mx=0.2, unit="percentunit", decimals=1, steps=CALIB,
          no_value="window filling (<15 model-scored closes)",
          desc="ECE; keep small — Kelly reads probs literally.")
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
          cols=[("liquiditybot_signal_confidence", "Confidence", "short", 2, HIGH_GOOD, "text"),
                ("liquiditybot_signal_concentration", "Concentration", "short", 2, HIGH_GOOD, "text"),
                ("liquiditybot_signal_urgency", "Urgency", "short", 2),
                ("liquiditybot_manip_suspect", "Manip", "short", 2, LOW_GOOD)],
          label_keys=["asset"], sort="Concentration",
          desc="Signal decision quality per asset.")
    table("Learned gate weights", 8, 5,
          cols=[("liquiditybot_gate_weight", "Weight", "short", 3, HIGH_GOOD, "text")],
          label_keys=["gate"], sort="Weight", desc="Evidence weight per gate.")
    bargauge("New-era outcomes by barrier",
             'liquiditybot_era_reason_label_rate'
             '{era=~"triple_barrier(_h[0-9]+)?",'
             'job="liquiditybot"}*100', 16, 6, unit="percent", decimals=1,
             steps=BLUE, legend="{{reason}}",
             desc="Label rate per exit reason on NEW-era (triple_barrier) "
                  "rows. Healthy signature: tb_pt high (profit-taking "
                  "barrier), tb_sl ~0 (stop-loss barrier — expected, not "
                  "a fault), tb_time mixed (no-move rows).")
    stat("Era mix drift (TVD)", M("liquiditybot_era_mix_tvd"), 8, 6,
         decimals=3, steps=DRIFT,
         desc="ML-080: recent-window exit-reason mix vs the trailing "
              "corpus mix (total-variation distance). Yellow at 0.30 "
              "(era_mix_drift_tvd_threshold) — detection only, never "
              "gates training or reweights a row.")
    stat("Bracket divergence",
         M("liquiditybot_bracket_divergence_rate", "*100"), 8, 6,
         unit="percent", decimals=1,
         steps=[{"color": "red", "value": None},
                {"color": "yellow", "value": 60},
                {"color": "green", "value": 80}],
         no_value="no bracket closes yet",
         desc="ML-082: rolling agreement rate between each bracket "
              "close's REALIZED net return and the LABELED counter-"
              "factual its own stamped pt_frac/sl_frac implies (tb_pt/"
              "tb_sl → the fixed barrier distance net of cost, tb_time → "
              "realized itself, so it always agrees). Report-only PROOF "
              "instrument — never gates an entry/exit/size decision; "
              "feeds the D4 cost model as evidence, not the reverse.")

    _learning_brain()
    _learning_trajectory()

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
             extra=[(M("liquiditybot_order_slip_bps_notional_weighted"),
                     "weighted"),
                    (M("liquiditybot_order_worst_slip_bps"), "worst")],
             no_value="no fills yet",
             desc="Implementation shortfall vs the ARRIVAL mark (positive "
                  "= paid worse than arrival; negative = improvement). "
                  "'weighted' is notional-weighted (Cochran ratio "
                  "estimator, 2026-07-29): the cost of the average "
                  "DOLLAR, immune to dust-fill skew — trust it over the "
                  "simple avg when they disagree.")
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

    row("🎯 CONVICTION — admission detail", collapsed=True)
    stat("Evaluated", M("liquiditybot_conviction_evaluated"), 4, 5,
         decimals=0, steps=BLUE, no_value="no conviction data yet",
         desc="Total conviction-channel evaluations since boot.")
    stat("Admitted", M("liquiditybot_conviction_admitted"), 4, 5,
         decimals=0, steps=GRN, no_value="no conviction data yet",
         desc="Total conviction admits since boot.")
    stat("Admit share", M("liquiditybot_conviction_share"), 4, 5,
         unit="percentunit", decimals=1, steps=BLUE,
         no_value="no conviction data yet",
         desc="Rolling admit share over the cadence window.")
    state("Alarm", M("liquiditybot_conviction_alarm"), 4, 5, CV_ALARM,
          no_value="no conviction data yet",
          desc="Cadence governor: sustained admit share outside "
               "[share_lo, share_hi].")
    bargauge("Regime window size (n)",
             _pa("liquiditybot_conviction_regime_n"), 8, 5, decimals=0,
             steps=BLUE, legend="{{regime}}", no_value="no regime data yet",
             desc="Rolling-window sample count per regime — alarms only "
                  "fire once a regime clears share_min_n.")
    bargauge("Admit share by regime",
             _pa("liquiditybot_conviction_regime_share"), 12, 6,
             decimals=2, steps=HIGH_GOOD, mn=0, mx=1, legend="{{regime}}",
             no_value="no regime data yet",
             desc="Per-regime admit share — a regime pinned always-on "
                  "or always-off is the T4 coverage / EV-multiple floor "
                  "misfiring for that regime specifically.")
    bargauge("Denials by code", _pa("liquiditybot_conviction_denials"),
             12, 6, decimals=0, steps=BLUE, legend="{{code}}",
             no_value="no denials yet", decode_family="CV",
             desc="CV-* disposition tally — which term denies most "
                  "(agreement / EV-multiple / regime-known / context).")
    table("Denials by code (detail)", 16, 5,
          cols=[("liquiditybot_conviction_denials", "Count", "short", 0, BLUE)],
          label_keys=["code"], sort="Count",
          desc="CV-* disposition tally in full detail.")

    row("🎫 PROBE BUDGET — scarcity-priced exploration (SPB-R)",
        collapsed=True)
    stat("Mode", "count(liquiditybot_probe_budget_mode_info" + JOB +
         ") by (mode)", 4, 5, text_mode="name", steps=BLUE, graph="none",
         display_name="${__field.labels.mode}",
         no_value="no probe-budget telemetry yet",
         desc="share_cap = legacy SZ-047 rolling share cap (byte-"
              "identical, the escape hatch); budget = SPB-R scarcity-"
              "priced token bucket. The flip is a conscious operator "
              "config change + restart.")
    stat("Tokens now", M("liquiditybot_probe_budget_tokens"), 4, 5,
         decimals=2, steps=BLUE, no_value="no probe-budget telemetry yet",
         desc="Token bucket level; negative = bounded placement debt "
              "(floor −C by construction, refill climbs it out).")
    stat("Labels/day (24h)", M("liquiditybot_probe_budget_labels_24h"),
         4, 5, decimals=0, steps=PROBE_LABELS,
         no_value="no probe closes yet",
         desc="Probe closes realized in the trailing 24h — the "
              "program's headline number. Book ceiling is 15/day "
              "(5 slots × 24h / 8h label horizon); expected ≈ 11-12 at "
              "defaults in budget mode.")
    stat("Unlock ETA (days)", M("liquiditybot_probe_budget_unlock_eta_days"),
         4, 5, decimals=1, steps=PROBE_ETA, no_value="no labels yet",
         desc="max(0, 60 − tb-era labels) / labels-per-day: days to the "
              "60-label tb-era evidence milestone at the current rate.")
    stat("Governor factor", M("liquiditybot_probe_budget_governor_factor"),
         4, 5, decimals=2, steps=PROBE_GOV,
         no_value="no probe-budget telemetry yet",
         desc="Tuition-governor refill scale: 1.0 nominal; < 1 = "
              "trailing-24h clipped probe losses crossed the cap "
              "(SZ-053); floored at 0.25 and self-redeeming as the "
              "window rolls — probation, never a life sentence.")
    gauge("Tuition vs cap (24h)",
          M("liquiditybot_probe_budget_tuition_24h_usd", " / ") +
          M("liquiditybot_probe_budget_tuition_cap_usd", " * 100"), 4, 5,
          mx=100.0, steps=BUDGET,
          no_value="no probe-budget telemetry yet",
          desc="Trailing-24h clipped probe tuition as % of the daily cap "
               "(10 bps of equity). Per-close clip = cap/3, so one "
               "outlier can never engage the governor alone.")
    timeseries("Token bucket vs capacity",
               M("liquiditybot_probe_budget_tokens"), 12, 6,
               legend="tokens", decimals=2, calcs=["lastNotNull"],
               extra=[(M("liquiditybot_probe_budget_capacity"),
                       "capacity")],
               colors={"tokens": INDIGO, "capacity": GRAY_HEX},
               desc="Bucket level vs capacity C (= one book-fill, 5 "
                    "tokens at defaults). Time below zero is bounded "
                    "placement DEBT (worst −C ≈ 8h of refill); pinned at "
                    "C = arrivals are cheaper than supply — headroom.")
    timeseries("Avg admission cost (24h)",
               M("liquiditybot_probe_budget_avg_cost_24h"), 12, 6,
               legend="avg cost", decimals=2, calcs=["lastNotNull"],
               colors={"avg cost": CAT_TEAL},
               desc="Mean scarcity price of admitted probes. Drift "
                    "toward 1.0 = buying scarce labels (good); toward "
                    "the clamp = only redundant arms arriving.")
    bargauge("Admissions (24h)",
             M("liquiditybot_probe_budget_admits_24h"), 8, 6, decimals=0,
             steps=BLUE, legend="admits",
             extra=[(M("liquiditybot_probe_budget_refunds_24h"),
                     "refunds (unfilled)"),
                    (M("liquiditybot_probe_budget_denied_exhausted_24h"),
                     "denied (exhausted)"),
                    (M("liquiditybot_probe_budget_rolls_failed_24h"),
                     "rolls failed")],
             no_value="no probe-budget telemetry yet",
             desc="Budget-mode admission flow: admits vs the ~12/day "
                  "target, SZ-052 refunds (unfilled entries hand their "
                  "cost back), exhausted-bucket denials (SZ-049 "
                  "brackets), and failed affordability rolls (non-"
                  "dispositions — counters, not audit spam).")
    bargauge("Per-asset eff weight (taper × scarcity)",
             _pa("liquiditybot_probe_asset_eff_weight"), 8, 6, decimals=3,
             steps=HIGH_GOOD, mn=0, mx=1, legend="{{asset}}",
             no_value="no probe-budget telemetry yet",
             desc="The ONE combined per-asset drag number (stats-judge "
                  "note): label-share taper pass-prob × scarcity weight "
                  "S(a,r), normalized — never two invisible "
                  "multiplications. Both factors floored, so no arm can "
                  "reach zero.")
    bargauge("Per-regime live labels",
             _pa("liquiditybot_probe_regime_live"), 8, 6, decimals=0,
             steps=PROBE_REGIME, legend="{{regime}}",
             no_value="no live labels yet",
             desc="LIVE labels per regime vs the 60-per-regime coverage "
                  "floor (corpus_target 300 / 5 regimes) — under-floor "
                  "regimes hold the decay AND price cheap (same "
                  "direction, no fight).")


# ==================== board 3 · problem / solution =========================
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

    row("🔗 AUDIT & TELEMETRY INTEGRITY")
    stat("PROBLEM: audit writes dropped",
         M("liquiditybot_audit_dropped_writes"), 4, 5, decimals=0,
         mode="background", graph="none", steps=ZERO_BAD,
         desc="Hash-chain append failures since boot. SOLUTION: any bar "
              "here means the book of record missed a write — check disk "
              "and the audit path before trusting the trail's negatives.")
    stat("PROBLEM: audit tail truncations",
         M("liquiditybot_audit_tail_truncations"), 4, 5, decimals=0,
         mode="background", graph="none", steps=ZERO_BAD,
         desc="Torn final records adopted and truncated at boot — each "
              "one is a crash mid-append the chain healed itself around.")
    stat("PROBLEM: gauges dropped (non-finite)",
         M("liquiditybot_gauges_dropped_nonfinite"), 4, 5, decimals=0,
         mode="background", graph="none", steps=ZERO_BAD,
         desc="Telemetry values refused for NaN/inf — a poisoned "
              "upstream feed shows here before it shows anywhere else.")
    timeseries("Gate divergence — reward-misspecification watch",
               'max by (gate) (liquiditybot_gate_divergence' + JOB + ')',
               12, 5, legend="{{gate}}",
               desc="Learned gate-weight recommendations diverging from "
                    "realized outcome grades. Flat near zero is healthy; "
                    "a sustained trend means the gate is learning the "
                    "wrong lesson. Report-only watch instrument.")

    row("🧠 MODEL HEALTH")
    stat("PROBLEM: model Brier", M("liquiditybot_ml_brier"), 4, 5, decimals=4,
         mode="background", graph="none", steps=BRIER,
         no_value="window filling (<15 model-scored closes)",
         desc="Detector. SOLUTION: the governor kills the model + queues a "
              "retrain when Brier crosses baseline.")
    stat("vs baseline", M("liquiditybot_ml_baseline_brier"), 4, 5, decimals=4,
         steps=GRN, graph="none",
         no_value="window filling (<15 model-scored closes)",
         desc="The bar Brier must stay under.")
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
         no_value="window filling (<15 model-scored closes)",
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
    gauge("PROBLEM: drawdown", M("liquiditybot_rp_drawdown_mtm_pct"), 5, 6,
          mx=15.0, steps=DD,
          desc="SOLUTION: drawdown throttle + 15% hard-stop flatten. Plots "
               "the MARK-TO-MARKET drawdown, which is the basis both of "
               "those controls key off — it previously plotted the "
               "realized-only figure, so the panel and the control it "
               "describes were reading different numbers.")
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


# ==================== board 4 · asset screening ============================
def _author_screening():
    row("🔎 SKIMMER — candidate universe")
    # see _author_execution: every board carries the staleness cue, because
    # every value tile here reduces with lastNotNull and will happily show a
    # pre-outage number as though it were live (2026-07-26)
    stat("Telemetry age", M("liquiditybot_status_age_sec"), 4, 5, unit="s",
         decimals=0, mode="background", graph="none",
         steps=[{"color": "green", "value": None},
                {"color": "yellow", "value": 120},
                {"color": "red", "value": 300}],
         desc="Seconds since the runner last wrote status.json. Red = the "
              "numbers on this board are stale, not calm.")
    stat("Candidates scanned", M("liquiditybot_skimmer_candidates"), 4, 5,
         decimals=0, steps=BLUE, desc="Off-universe pairs ranked.")
    stat("Promoted", M("liquiditybot_skimmer_promoted_count"), 4, 5,
         decimals=0, steps=GRN, desc="Pairs promoted into the tradeable "
         "set.")
    stat("Positions open", M("liquiditybot_positions_open"), 4, 5, decimals=0,
         steps=BLUE, desc="Open positions occupying slots (max 5).")
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
                ("liquiditybot_signal_confidence", "Confidence", "short", 2, HIGH_GOOD, "text"),
                ("liquiditybot_signal_concentration", "Concentration", "short", 2, HIGH_GOOD, "text"),
                ("liquiditybot_signal_urgency", "Urgency", "short", 2),
                ("liquiditybot_perf_asset_win_rate", "Win rate", "percentunit", 2, WRU, "text"),
                ("liquiditybot_perf_asset_net_usd", "Net $", USD, 2, PNL, "text"),
                ("liquiditybot_perf_asset_trades", "Trades", "short", 0)],
          label_keys=["asset"], sort="Net $",
          desc="Screen an asset in one row: tight spread + low spoof/manip "
               "+ high concentration + positive net = a tradeable edge. "
               "Absent cells (·) mean the asset hasn't traded yet — not a "
               "fault.")

    row("🥇 TANGIBLE-VALUE LADDER — gold › BTC › ETH › alts")
    state("Haven state", 'count(liquiditybot_haven_info' + JOB + ') by (state)',
          6, 5, {}, desc="Where capital sits on the tangibility ladder. "
                         "FLIGHT_TO_QUALITY = money moving DOWN the ladder "
                         "toward what is real (fear); RISK_ON = reaching up "
                         "for beta (froth); UNKNOWN = too few rungs to say. "
                         "Report-only — it sizes nothing.")
    stat("Gradient", M("liquiditybot_haven_gradient"), 6, 5, decimals=2,
         steps=BLUE, no_value="fewer than two adjacent rungs",
         desc="Mean spread between ADJACENT rungs, % over 24h. POSITIVE = "
              "the more tangible rung is outperforming (fear travelling "
              "down the ladder); negative = the reach for beta. Adjacent-"
              "only so one blown-out microcap cannot write a headline "
              "about gold.")
    stat("Rungs read", M("liquiditybot_haven_rungs_seen"), 6, 5, decimals=0,
         steps=BLUE, graph="none",
         desc="How many of the four rungs had usable bars this scrape "
              "(PAXG/BTC/ETH/ALT). Fewer than two adjacent = UNKNOWN, a "
              "state rather than a guessed zero.")
    bargauge("Return by rung (24h %)",
             'liquiditybot_haven_rung_return' + JOB, 6, 5, unit="percent",
             decimals=2, steps=PNL, legend="{{rung}}",
             no_value="no rung data yet",
             desc="The ladder itself: gold (a bar in a vault) › BTC (a "
                  "network with a security budget) › ETH (a platform "
                  "contingent on usage) › alts (venture bets). The ALT "
                  "rung is AVERAGED so one coin ripping is not a regime.")
    timeseries("Gradient over time — is fear travelling down the ladder?",
               M("liquiditybot_haven_gradient"), 24, 6, legend="gradient",
               desc="The trend is the read: a gradient climbing through "
                    "zero is capital rotating toward tangibility ahead of "
                    "a drawdown; falling through zero is risk appetite "
                    "returning. Sustained direction matters, not the "
                    "current print.")

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
    _context_row()
    _thales_row()


# ==================== board 5 · pulse ======================================
# ONE full-width Business Text panel: the whole board is a single live
# "one screen, one truth" readout (marcusolsson-dynamictext-panel). Data is
# read via renderMode "data" — `data.[i]` is query i's frame (refId order
# A..Q below), `.[0].Value` the single instant value; the range frame is
# iterated for the sparkline. Every value carries a "--" empty-state.
#
# Sparkline strategy = PURE HANDLEBARS + inline SVG (NO helpers / NO
# afterRender): the sanitizer keeps SVG primitives, so this renders even if
# panel JS were ever locked down on the Cloud tenant (Brief 1 §5 "reliable"
# path). The plugin ships no math helpers, so ALL arithmetic is pushed into
# PromQL: x = {{@index}} against a fixed 575-wide viewBox; y = the NEGATED
# equity value (so higher equity sits higher), mapped by a viewBox whose
# y-origin (-max) and height (max-min, clamped) come from sibling
# min/max_over_time instant queries — zero per-point math in the template.
# Grafana Cloud SANITIZES <style> blocks out of rendered panel HTML (the same
# sanitizer that keeps the glass injector dormant as a native text panel), so
# the pulse CSS must ship via Business Text's dedicated `styles` option — the
# plugin injects it as scoped CSS itself, outside the sanitizer's reach. The
# content template below is therefore HTML-only; putting a <style> tag back
# into content will silently strip on the instance (pinned in tests).
_PULSE_CSS = """\
.pulse-wrap{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,\
system-ui,sans-serif;color:#F5F5F7;max-width:26rem;margin:0 auto;\
box-sizing:border-box;min-height:100%;display:flex;flex-direction:column;\
justify-content:center;\
padding:1.8rem 1.25rem 1.2rem;text-align:center;-webkit-font-smoothing:antialiased;}
.pulse-state{display:flex;align-items:center;justify-content:center;\
flex-wrap:wrap;gap:.5em;font-size:11px;font-weight:600;text-transform:uppercase;\
letter-spacing:.14em;color:#86868B;font-variant-numeric:tabular-nums;\
margin-bottom:1.6rem;}
.pulse-state .sep{opacity:.45;}
.pulse-state.stale{color:#FF9F0A;}
.pulse-dot{width:7px;height:7px;border-radius:50%;background:#30D158;\
box-shadow:0 0 0 4px rgba(48,209,88,.16);}
.pulse-state.stale .pulse-dot{background:#FF9F0A;\
box-shadow:0 0 0 4px rgba(255,159,10,.16);}
.pulse-state.idle .pulse-dot{background:#8E8E93;\
box-shadow:0 0 0 4px rgba(142,142,147,.16);}
.pulse-hero{font-size:clamp(3.4rem,17vw,5.4rem);font-weight:600;\
letter-spacing:-.03em;line-height:1;font-variant-numeric:tabular-nums;}
.pulse-cur{color:#86868B;font-weight:500;font-size:.4em;vertical-align:.42em;\
margin-right:.05em;}
.pulse-cents{color:#86868B;font-weight:500;font-size:.42em;}
.pulse-pnl{margin-top:1.05rem;font-size:1.05rem;font-variant-numeric:tabular-nums;\
letter-spacing:-.01em;}
.pulse-pnl .gain{color:#30D158;}
.pulse-pnl .loss{color:#FF453A;}
.pulse-pnl .flat{color:#86868B;}
.pulse-pnl .wk{color:#86868B;margin-left:.7em;}
.pulse-top{padding-bottom:.4rem;}
.pulse-bot{padding-top:.4rem;}
@media (min-width:900px){.pulse-wrap{max-width:32rem;}}
.pulse-rows{border-top:1px solid rgba(242,242,244,.13);text-align:left;}
.pulse-row{display:flex;align-items:baseline;justify-content:space-between;\
gap:1rem;padding:.9rem .15rem;border-bottom:1px solid rgba(242,242,244,.13);}
.pulse-row:last-child{border-bottom:0;}
.pulse-row .lab{font-size:15px;font-weight:500;color:#F5F5F7;}
.pulse-row .exp{display:block;font-size:15px;font-weight:400;color:#86868B;\
margin-top:.18rem;}
.pulse-row .val{font-size:17px;font-variant-numeric:tabular-nums;color:#F5F5F7;\
white-space:nowrap;text-align:right;}
.pulse-row .val .sub{display:block;font-size:11px;font-weight:500;color:#86868B;\
text-transform:uppercase;letter-spacing:.06em;margin-top:.1rem;}
.pulse-foot{margin-top:1.4rem;font-size:11px;color:#6E6E73;\
text-transform:uppercase;letter-spacing:.1em;}"""

_PULSE_TOP = """\
<div class="pulse-wrap pulse-top">
<div class="pulse-state{{#if data.[2].[0].Value}} stale\
{{else}}{{#unless data.[0].[0].Value}} idle{{/unless}}{{/if}}">\
<span class="pulse-dot"></span>\
{{#if data.[2].[0].Value}}<span>Stale</span>\
{{#with data.[1].[0]}}<span class="sep">&middot;</span>\
<span>{{toFixed Value 0}}s ago</span>{{/with}}\
{{else}}<span>{{#if data.[0].[0].Value}}Running{{else}}Idle{{/if}}</span>\
<span class="sep">&middot;</span><span>Paper</span>\
<span class="sep">&middot;</span>\
{{#with data.[1].[0]}}<span>{{toFixed Value 0}}s ago</span>\
{{else}}<span>-- ago</span>{{/with}}{{/if}}</div>
<div class="pulse-hero">{{#if data.[3].[0]}}<span class="pulse-cur">$</span>\
{{#if data.[6].[0].Value}}{{toFixed data.[6].[0].Value 0}},\
{{#with (split (toFixed data.[7].[0].Value 0) "") as |d|}}\
{{lookup d 1}}{{lookup d 2}}{{lookup d 3}}{{/with}}\
{{else}}{{lookup (split (toFixed data.[3].[0].Value 2) ".") 0}}{{/if}}\
<span class="pulse-cents">.{{lookup (split (toFixed data.[3].[0].Value 2) ".") 1}}\
</span>{{else}}--{{/if}}</div>
<div class="pulse-pnl">{{#with data.[4].[0]}}\
{{#if (eq (toFixed Value 2) "0.00")}}<span class="flat">$0.00 today</span>\
{{else}}{{#if (eq (toFixed Value 2) "-0.00")}}<span class="flat">$0.00 today</span>\
{{else}}{{#if (startsWith (toFixed Value 2) "-")}}\
<span class="loss">-${{#if data.[8].[0].Value}}{{toFixed data.[8].[0].Value 0}},\
{{#with (split (toFixed data.[9].[0].Value 0) "") as |d|}}\
{{lookup d 1}}{{lookup d 2}}{{lookup d 3}}{{/with}}\
{{else}}{{lookup (split (lookup (split (toFixed Value 2) "-") 1) ".") 0}}{{/if}}\
.{{lookup (split (toFixed Value 2) ".") 1}} today</span>\
{{else}}<span class="gain">+${{#if data.[8].[0].Value}}{{toFixed data.[8].[0].Value 0}},\
{{#with (split (toFixed data.[9].[0].Value 0) "") as |d|}}\
{{lookup d 1}}{{lookup d 2}}{{lookup d 3}}{{/with}}\
{{else}}{{lookup (split (toFixed Value 2) ".") 0}}{{/if}}\
.{{lookup (split (toFixed Value 2) ".") 1}} today</span>{{/if}}{{/if}}{{/if}}\
{{else}}<span class="flat">-- today</span>{{/with}}\
{{#with data.[5].[0]}}<span class="wk">\
{{#if (eq (toFixed Value 2) "0.00")}}$0.00 this week\
{{else}}{{#if (eq (toFixed Value 2) "-0.00")}}$0.00 this week\
{{else}}{{#if (startsWith (toFixed Value 2) "-")}}-${{#if data.[10].[0].Value}}\
{{toFixed data.[10].[0].Value 0}},{{#with (split (toFixed data.[11].[0].Value 0) "") as |d|}}\
{{lookup d 1}}{{lookup d 2}}{{lookup d 3}}{{/with}}\
{{else}}{{lookup (split (lookup (split (toFixed Value 2) "-") 1) ".") 0}}{{/if}}\
.{{lookup (split (toFixed Value 2) ".") 1}} this week\
{{else}}+${{#if data.[10].[0].Value}}{{toFixed data.[10].[0].Value 0}},\
{{#with (split (toFixed data.[11].[0].Value 0) "") as |d|}}\
{{lookup d 1}}{{lookup d 2}}{{lookup d 3}}{{/with}}\
{{else}}{{lookup (split (toFixed Value 2) ".") 0}}{{/if}}\
.{{lookup (split (toFixed Value 2) ".") 1}} this week{{/if}}{{/if}}{{/if}}\
</span>{{else}}<span class="wk">-- this week</span>{{/with}}</div>
</div>"""

_PULSE_ROWS = """\
<div class="pulse-wrap pulse-bot">
<div class="pulse-rows">
<div class="pulse-row"><span class="lab">Time-stop scratches\
<span class="exp">Trades the max-hold clock closed flat &mdash; patience, \
not conviction (covers bracket probes since 2026-07-29; counts \
scratches, not log lines)</span></span>\
<span class="val">{{#with data.[0].[0]}}{{toFixed Value 0}}{{else}}--{{/with}}\
</span></div>
<div class="pulse-row"><span class="lab">Probes held back\
<span class="exp">Entries the sizer judged too small to be worth the risk\
</span></span>\
<span class="val">{{#with data.[1].[0]}}{{toFixed Value 0}}{{else}}--{{/with}}\
</span></div>
<div class="pulse-row"><span class="lab">Learning corpus\
<span class="exp">Labelled trades feeding the model</span></span>\
<span class="val">{{#with data.[2].[0]}}{{toFixed Value 0}}{{else}}--{{/with}}\
<span class="sub">{{#with data.[3].[0]}}{{toFixed Value 0}} live\
{{else}}-- live{{/with}}</span></span></div>
<div class="pulse-row"><span class="lab">Model\
<span class="exp">Whether the model is sizing trades or standing aside\
</span></span>\
<span class="val">{{#if data.[4].[0]}}\
{{#if (eq data.[4].[0].Value 2)}}watching\
{{else}}{{#if data.[5].[0].Value}}driving{{else}}standing by{{/if}}{{/if}}\
{{else}}--{{/if}}</span></div>
</div>
<div class="pulse-foot">Live &middot; refreshes with the bot's telemetry</div>
</div>"""

_PULSE_DEFAULT = ('<div class="pulse-wrap"><div class="pulse-foot">'
                  'waiting for telemetry&hellip;</div></div>')


def _bt_options(content):
    """Business Text options with the SANITIZER CONTRACT applied: CSS rides
    in `styles` (plugin-injected, sanitizer-proof), never in content."""
    return {"renderMode": "data", "content": content,
            "defaultContent": _PULSE_DEFAULT, "editors": ["styles"],
            "helpers": "", "afterRender": "", "styles": _PULSE_CSS,
            "wrap": False, "externalStyles": [], "contentPartials": []}


def _pulse_hero():
    """The Command board's opening screen, THREE stacked transparent panels
    reading as one composition (operator decision 2026-07-23: 'integrate it
    with my 4 boards, not a new one' — the family stays at four, the
    standalone liquiditybot-pulse uid is retired in grafana_import.py):
      1. Business Text hero — state line, grouped equity numeral, P&L.
      2. NATIVE full-bleed equity strip (stat/area sparkline): Grafana draws
         it itself, so it can never be sanitized away (the inline-SVG
         sparkline WAS — same sanitizer that eats <style>), it self-scales
         to the dashboard range (no viewBox math), and it anchors the
         composition's full width on desktop.
      3. Business Text rows — the four hairline truth rows + footer.
    Phone view: Command's viewPanel+kiosk URL still shows panel 1; the strip
    and rows stack beneath on the board itself."""
    # -- 1. hero -------------------------------------------------------------
    x, y = _place(24, 8)
    inst = [
        ("A", 'max(liquiditybot_running{job="liquiditybot"})'),
        ("B", 'max(liquiditybot_status_age_sec{job="liquiditybot"})'),
        ("C", 'max(liquiditybot_status_stale{job="liquiditybot"})'),
        ("D", 'max(liquiditybot_equity{job="liquiditybot"})'),
        ("E", 'max(liquiditybot_daily_pnl{job="liquiditybot"})'),
        ("F", 'max(liquiditybot_weekly_pnl{job="liquiditybot"})'),
        # P/Q + R/S + T/U: thousands-grouping companions (design C1). The
        # plugin ships no math helpers, so grouping is arithmetic in PromQL:
        # thousands = floor(|v|/1000) (Handlebars truthiness gates the
        # comma; 0 => no group) and remainder = 1000 + (floor(|v|) % 1000)
        # so toFixed->split "" yields the ZERO-PADDED low three digits at
        # char positions 1..3 (covers up to 6 figures).
        ("P", 'floor(max(liquiditybot_equity{job="liquiditybot"}) / 1000)'),
        ("Q", '1000 + (floor(max(liquiditybot_equity{job="liquiditybot"}))'
              ' % 1000)'),
        ("R", 'floor(abs(max(liquiditybot_daily_pnl{job="liquiditybot"}))'
              ' / 1000)'),
        ("S", '1000 + (floor(abs(max(liquiditybot_daily_pnl'
              '{job="liquiditybot"}))) % 1000)'),
        ("T", 'floor(abs(max(liquiditybot_weekly_pnl{job="liquiditybot"}))'
              ' / 1000)'),
        ("U", '1000 + (floor(abs(max(liquiditybot_weekly_pnl'
              '{job="liquiditybot"}))) % 1000)'),
    ]
    panels.append({
        "id": _id(), "type": "marcusolsson-dynamictext-panel",
        "title": "", "description": "Live single-screen truth (hero).",
        "datasource": DS, "gridPos": {"h": 8, "w": 24, "x": x, "y": y},
        "fieldConfig": {"defaults": {}, "overrides": []},
        "options": _bt_options(_PULSE_TOP),
        "targets": [_t(e, ref=r, instant=True) for r, e in inst],
        "pluginVersion": "6.3.0"})
    # -- 2. native equity strip ----------------------------------------------
    x, y = _place(24, 4)
    panels.append({
        "id": _id(), "type": "stat", "title": "",
        "description": "Equity over the dashboard range — native sparkline "
                       "(stat/area): sanitizer-proof and self-scaling.",
        "datasource": DS, "gridPos": {"h": 4, "w": 24, "x": x, "y": y},
        "transparent": True,
        "fieldConfig": {"defaults": {
            "color": {"mode": "fixed", "fixedColor": "#86868B"},
            "unit": "currencyUSD", "decimals": 2,
            "noValue": "no equity history yet"}, "overrides": []},
        "options": {"graphMode": "area", "textMode": "none",
                    "colorMode": "none", "justifyMode": "auto",
                    "orientation": "horizontal", "wideLayout": True,
                    "reduceOptions": {"calcs": ["lastNotNull"],
                                      "fields": "", "values": False},
                    "showPercentChange": False},
        "targets": [_t('max(liquiditybot_equity{job="liquiditybot"})',
                       ref="M", instant=False)],
        "pluginVersion": "11.1.0"})
    # -- 3. rows ---------------------------------------------------------------
    x, y = _place(24, 10)
    rows_t = [
        ("G", 'max(liquiditybot_code_count_detail'
              '{job="liquiditybot",code="PT-060"})'),
        ("H", 'max(liquiditybot_code_count_detail'
              '{job="liquiditybot",code="SZ-047"})'),
        ("I", 'sum(liquiditybot_ml_labels{job="liquiditybot"})'),
        ("J", 'max(liquiditybot_ml_labels{job="liquiditybot",source="live"})'),
        ("K", 'max(liquiditybot_monitor_level{job="liquiditybot"})'),
        ("L", 'max(liquiditybot_ml_use_model{job="liquiditybot"})'),
    ]
    panels.append({
        "id": _id(), "type": "marcusolsson-dynamictext-panel",
        "title": "", "description": "Live single-screen truth (rows).",
        "datasource": DS, "gridPos": {"h": 10, "w": 24, "x": x, "y": y},
        "fieldConfig": {"defaults": {}, "overrides": []},
        "options": _bt_options(_PULSE_ROWS),
        "targets": [_t(e, ref=r, instant=True) for r, e in rows_t],
        "pluginVersion": "6.3.0"})


# ============================ assemble =====================================
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
