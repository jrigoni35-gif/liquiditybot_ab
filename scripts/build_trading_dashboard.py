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

Boards (2026-08-17 rebuild — the operator's THREE screen-snip links plus the
pin-required alert mirror; the empty screening board was folded away and its
uid retired on import):
  liquiditybot_command.json          — COMMAND: what is the bot doing
  liquiditybot_learning.json         — LEARNING: is it getting smarter (30d)
  liquiditybot_problem_solution.json — PROBLEMS: what needs attention
  liquiditybot_execution.json        — alert-input mirror (kept verbatim)
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

# ---- config-derived board constants (2026-08-17) ---------------------------
# Values that must TRACK config are read from it at generation time, never
# hardcoded. Two lessons drive this:
#   * the era donut shipped querying era="triple_barrier" — the RETIRED
#     un-suffixed era (see gc_pusher._era_label's own incident docstring:
#     the 432-bar migration mints triple_barrier_h<N>) — so the panel would
#     have found nothing even on a healthy bot. The era label is derived
#     from ml.label_max_bars with the SAME formula as
#     ml.history.triple_barrier_era (legacy 96 stays un-suffixed);
#     tests/test_boards_stripped.py pins the board's label against the real
#     function, so formula drift reds the build instead of dark panels.
#   * the judge-window floor ("<15") was hardcoded into empty-state text; a
#     config change would turn the text into a lie. It reads
#     ml.monitor.min_trades_to_judge instead.
_CFG = json.loads((Path(__file__).resolve().parents[1] / "config.json")
                  .read_text(encoding="utf-8"))
_TB_MAX_BARS = int(_CFG["ml"]["label_max_bars"])
TB_ERA = ("triple_barrier" if _TB_MAX_BARS == 96
          else f"triple_barrier_h{_TB_MAX_BARS}")
JUDGE_MIN = int((_CFG["ml"].get("monitor") or {})
                .get("min_trades_to_judge", 15))
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
# EVERY rule is scoped with :has(#lb-glass-marker) (2026-08-30). The injected
# <style id="lb-glass"> node lives in document.head for the LIFE OF THE TAB -
# Grafana is a SPA, so navigating from a bot board to any other page (Alerting
# -> History was the measured casualty: operator report "alert history screen
# is black") used to carry `.main-view { background:#000 }` along and blacken
# pages this skin was never written for. :has() keys the rules to the marker
# span's PRESENCE IN THE DOM instead: on a bot board (all four embed the
# hidden injector tile) the skin applies; navigate away and the marker leaves
# the DOM, so every rule stops matching that same instant - no removal JS, no
# polling, nothing to leak. Failure direction on a pre-:has() browser is the
# safe one: rules never match, boards render plain dark theme, nothing goes
# black. Solo-panel view (viewPanel=N) omits the marker tile, so it renders
# unskinned - accepted; the dashboard view is the product.
GLASS_RULES = """\
html:has(#lb-glass-marker) { -webkit-text-size-adjust: 100%;
  text-size-adjust: 100%; }
body:has(#lb-glass-marker) .main-view,
body:has(#lb-glass-marker) .scrollbar-view { background: #000 !important; }
html:has(#lb-glass-marker), body:has(#lb-glass-marker),
body:has(#lb-glass-marker) .main-view,
body:has(#lb-glass-marker) [class*="dashboard"] {
  font-family: -apple-system, "SF Pro Text", "SF Pro Display", "Inter",
               system-ui, sans-serif !important;
  -webkit-font-smoothing: antialiased;
}
body:has(#lb-glass-marker) [data-testid="data-testid panel content"] {
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
body:has(#lb-glass-marker) .react-grid-item {
  background: transparent !important; }
body:has(#lb-glass-marker) [data-testid^="data-testid Panel header"] {
  background: transparent !important; border: 0 !important; }
body:has(#lb-glass-marker) [data-testid="data-testid header-container"] {
  font-weight: 600; letter-spacing: .4px; font-size: 11px;
  text-transform: uppercase; color: rgba(235,235,245,.6) !important; }
body:has(#lb-glass-marker) [data-testid^="data-testid dashboard-row-title-"] {
  text-transform: uppercase; letter-spacing: 1.4px; font-size: 12px;
  font-weight: 700; color: rgba(235,235,245,.55) !important; }
body:has(#lb-glass-marker) [data-viz-panel-key="panel-990"] {
  display: none !important; }
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


def donut(title, slices, w, h, colors, desc="", no_value=None,
          unit="percentunit", decimals=1):
    """2-4 slice composition donut. slices: [(expr, legend)]; colors:
    {legend: hex} — color follows the ENTITY, fixed, never positional
    ({} for label-driven slices, which rotate palette-classic). unit rides
    the VALUE (tooltips/legend); the slice labels always show percent."""
    x, y = _place(w, h)
    overrides = [{"matcher": {"id": "byName", "options": name},
                  "properties": [{"id": "color", "value": {
                      "mode": "fixed", "fixedColor": col}}]}
                 for name, col in colors.items()]
    fld = {"unit": unit, "decimals": decimals, "mappings": [],
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
# Base "text", not green (2026-08-17): Grafana paints a stat's noValue
# string with the BASE threshold step's color, so a green base rendered
# ABSENCE as an all-clear — a dead exporter's empty fault tile glowed the
# same green as a checked-and-passed one. Neutral base = value 0 reads
# neutral (the board's neutral-when-ok doctrine, see CV_ALARM), a real
# count reads red, and absence reads as neither verdict. Renderer claim
# verified by precedent (state() tiles already pair base-text with
# mappings); the one-tile live injection is the deploy-time check.
ZERO_BAD = [{"color": "text", "value": None}, {"color": "red", "value": 1}]
# Signed-gap tiles (Brier gap) need base-text for absence AND real colors
# for every reachable value, which a two-step scale cannot do — so the
# base covers only an UNREACHABLE band via a -100 sentinel (Brier gaps
# live in [-1, 1]) and the reachable range gets its true colors above it.
GAP_GOOD_POS = [{"color": "text", "value": None},      # only noValue lands here
                {"color": "red", "value": -100},
                {"color": "green", "value": 0}]
GAP_BAD_POS = [{"color": "text", "value": None},       # only noValue lands here
               {"color": "green", "value": -100},
               {"color": "red", "value": 0.03}]
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
# 2026-08-17 rebuild palettes -----------------------------------------------
# Staleness scale for the 30s push cadence, shared by the LEARNING and
# PROBLEMS "Data age" tiles (the command board keeps its identical local
# copy untouched): two missed pushes is noise, a minute is worth noticing,
# five minutes means every other number on the board is a fossil.
AGE_STEPS = [{"color": "green", "value": None},
             {"color": "yellow", "value": 60},
             {"color": "red", "value": 300}]
# loss-budget FRACTIONS (0..1 percentunit): yellow at 60% spent, red at 90%
FRAC_BUDGET = [{"color": "green", "value": None},
               {"color": "yellow", "value": 0.6},
               {"color": "red", "value": 0.9}]
# size multipliers where 1.0 is nominal and LOWER means throttled
MULT_LOW_BAD = [{"color": "red", "value": None},
                {"color": "yellow", "value": 0.5},
                {"color": "green", "value": 0.99}]
MARKS_AGE = [{"color": "green", "value": None},
             {"color": "yellow", "value": 30},
             {"color": "red", "value": 120}]
RECONNECTS = [{"color": "green", "value": None},
              {"color": "yellow", "value": 3},
              {"color": "red", "value": 10}]
# base text, not green: on a dry-run bot the recompute never runs and the
# exported 0.0 is an initializer, not a verdict (main.py gates the
# equity-truth check on `not dry_run`) — a green 0.00 would render the
# check that never ran as the check that passed. Since 2026-08-17 the
# Books tile ALSO filters itself away in paper mode (`and dry_run == 0`),
# so the base color now covers live-mode zeros, which read neutral by
# the neutral-when-ok doctrine — the base stays "text" either way.
EQ_DRIFT = [{"color": "text", "value": None},
            {"color": "yellow", "value": 0.5},
            {"color": "red", "value": 2.0}]
HEAT = [{"color": "green", "value": None},
        {"color": "yellow", "value": 0.25},
        {"color": "red", "value": 0.35}]
# OM-040 timeout-cancel share of clean terminals (0..1 percentunit). Base
# "text" per the absence doctrine (a low share is the expected steady state
# and reads neutral, never an affirmative green); the 48h audit that
# motivated the panel measured 68% — squarely in the red band, which is the
# scale's calibration point, not a tunable.
OM_TIMEOUT_SHARE = [{"color": "text", "value": None},
                    {"color": "yellow", "value": 0.4},
                    {"color": "red", "value": 0.6}]
# ERA-8 fix-wave (2026-08-28): the confound-visibility mutation's own
# thresholds. MUST equal scripts/gate_efficacy_report.py's
# ERA_OVERLAP_FLOOR/ERA_OVERLAP_MAJORITY (that file's own docstring at
# :104: "POLICY floors, not fitted to any data") — not imported directly
# (the TB_ERA/JUDGE_MIN precedent keeps this generator's own dependency
# surface light), cross-checked instead by
# tests/test_boards_stripped.py::test_confound_thresholds_track_the_reports_policy_constants.
# LOWER overlap is WORSE (less comparable), so red anchors the bottom:
# <0.05 CONFOUNDED_BASELINE, <0.5 PARTIAL_OVERLAP, >=0.5 COMPARABLE.
ERA_OVERLAP_FLOOR = 0.05
ERA_OVERLAP_MAJORITY = 0.5
ERA_OVERLAP_STEPS = [{"color": "red", "value": None},
                     {"color": "yellow", "value": ERA_OVERLAP_FLOOR},
                     {"color": "green", "value": ERA_OVERLAP_MAJORITY}]

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
# CURRENT STATE (2026-08-17 three-link rebuild):
#   _author_command    COMMAND - the at-a-glance read + activity & budget
#   _author_learning   LEARNING - the 30-day "is it getting smarter" read
#   _author_problem    PROBLEMS - what needs attention (empty-looking = good)
#   _author_execution  the alert-input mirror (pin-required, kept verbatim)
# The screening board was folded away (nothing to fold - it held only the
# injector); scripts/grafana_import.py retires its uid on the next import.
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

    ACCURACY RULE for anything added here: every expression below queries a
    metric that scripts/gc_pusher.py was VERIFIED to emit, by running
    gc_pusher.collect() against the live outputs/status.json and reading the
    value back. A panel whose metric was never emitted renders "No data",
    which is indistinguishable from a broken exporter. Do not add a panel
    here from memory of another board - re-run the check.

    STREAM 7c REBUILD (2026-08-28, `scratchpad/sdd/grafana-audit.md`): fewer,
    better panels — every FIX/MERGE/REMOVE verdict applied. Six panels
    retired (Telemetry state folded into Data age's own numeric threshold;
    Exposure-by-asset pie removed as a redundant view of the positions
    table one row up; Daily/Weekly loss budget and Size taper removed as
    duplicates of the PROBLEMS board's canonical risk-brakes home; Fills so
    far folded into Fill mix's own two-slice legend) — 25 data panels down
    to 19, per the audit's proposed information hierarchy (this board stays
    the ALIVE/SAFE-posture read; PROBLEMS owns the risk-brake deep dive).
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
    # already assigns empty-state text from _ALWAYS_ON / _NO_VALUE_BY_FAMILY,
    # and that registry restates the ACTUAL guard in scripts/gc_pusher.py
    # per metric family. A hand-written string here OVERRIDES it - which is
    # how "Open positions" first shipped saying "flat" when its series was
    # missing. Let the registry answer; it knows the guards and I do not.
    stat("Today", M("liquiditybot_daily_pnl"), 5, 6, unit=USD, decimals=2,
         steps=PNL, desc="P&L since midnight, realized plus unrealized.")
    stat("This week", M("liquiditybot_weekly_pnl"), 5, 6, unit=USD,
         decimals=2, steps=PNL,
         desc="P&L over the trading week. A capital sweep (savings/reserve "
              "skim) can read as a false weekly loss here - the RP-041 "
              "family; see the budget_reanchor_week control verb if a drop "
              "coincides with a sweep rather than a losing run.")
    # RETITLED 2026-08-28 (audit top-5 #2): the metric is equity minus
    # STARTING capital, and starting_capital is RE-ANCHORED at every
    # capital-epoch reset (savings/reserve sweeps mint a new epoch) - so
    # "All time" claimed a lifetime figure while showing a since-epoch one,
    # the exact digest false-alarm shape. Metric name unchanged (extend,
    # never rename); only the title and desc now say what it actually is.
    stat("Since capital epoch", M("liquiditybot_net_pnl_all_time"), 4, 6,
         unit=USD, decimals=2, steps=PNL,
         desc="Equity minus starting_capital, where starting_capital is "
              "RE-ANCHORED at each capital-epoch reset (a savings/reserve "
              "sweep mints a new epoch) - this is since-the-last-epoch "
              "P&L, not a lifetime total, despite the metric's own name "
              "(liquiditybot_net_pnl_all_time, kept for compatibility).")
    # FIXED 2026-08-28 (audit top-5 #1, FIX(verify) resolved by reading
    # core/state.py directly): the desc used to claim "peak-to-trough,
    # percent of peak equity", which is what drawdown_mtm_pct computes
    # (core/state.py:343-353). THIS metric is state.drawdown_pct()
    # (core/state.py:327-332): starting_capital minus cash+savings, as a
    # percent of starting_capital - not a peak, not mark-to-market, and
    # blind to unrealized loss. The two are genuinely different numbers.
    stat("Drawdown", M("liquiditybot_drawdown_pct"), 4, 6, unit="percent",
         decimals=2, steps=DD,
         desc="Percent below STARTING (capital-epoch) equity, cash+savings "
              "basis only - blind to unrealized P&L. NOT peak-to-trough and "
              "NOT mark-to-market. The drawdown the catastrophe hard stop "
              "actually watches is the MTM peak-to-trough figure on the "
              "Problems board ('Drawdown vs the hard stop').")

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
              "series means the status write carried no positions key, or "
              "the exporter is down.")
    gauge("Gross exposure", M("liquiditybot_gross_exposure_pct"), 5, 5,
          mx=100.0, unit="percent", decimals=1, steps=BUDGET,
          desc="Notional at risk as a percent of equity.")
    # FIXED 2026-08-28 (audit top-5 #3): FEE-1 (config fees ~half the
    # venue's real bottom tier, 25/40 vs Kraken T1 40/80) is RESOLVED, not
    # merely caveated - cut #8 (exec_era 8-ca55e2ba, 2026-08-28T03:14:13Z)
    # moved both the pricing and booking sides to venue-true 40/80 bps.
    # Fees booked BEFORE that cut in this cumulative total still carry the
    # old understated schedule; cost_truth_report remains the independent
    # cross-check for anyone auditing pre-cut history.
    stat("Fees paid", M("liquiditybot_fees_total"), 4, 5, unit=USD,
         decimals=2, graph="none", size="compact", steps=GRN,
         desc="Cumulative simulated fees. At this account size fees are the "
              "binding constraint, so they belong on the front page. "
              "Venue-true since cut #8 (era 8-ca55e2ba, 2026-08-28): "
              "Kraken Tier-1 40/80 bps on both pricing and booking - the "
              "FEE-1 understatement is shipped, not merely a caveat.")
    state("Entries", M("liquiditybot_entries_enabled"), 4, 5, ON_OFF,
          desc="Whether the bot may OPEN new positions. Exits are always "
               "allowed regardless of this.")
    state("Halt", M("liquiditybot_halted"), 3, 5, HALT,
          desc="Circuit breaker. 'clear' is the healthy state.")
    # FIXED 2026-08-28 (audit top-5, MERGE 14->12): the separate
    # "Telemetry" state tile (STALE/fresh) restated exactly what this
    # numeric age already says with thresholds - one fact, two tiles. The
    # exporter's OWN staleness flag (liquiditybot_status_stale) fires at
    # STALE_AFTER_SEC=120s (scripts/gc_pusher.py), tighter than this
    # tile's 300s red line, so status_stale=1 is already visible here
    # before this tile turns red.
    stat("Data age", M("liquiditybot_status_age_sec"), 4, 5, unit="s",
         decimals=0, graph="none", size="compact", steps=age_steps,
         desc="Seconds since the RUNNER last wrote outputs/status.json "
              "(gc_pusher.py: now - status['written_at']) - the age of the "
              "bot's own write, NOT of the push. If this climbs, every other "
              "number on this board is a fossil - read it FIRST. Subsumes "
              "the separate Telemetry STALE/fresh tile (merged 2026-08-28): "
              "the exporter itself marks the whole batch STALE past 120s, "
              "tighter than this tile's own 300s red line.")

    # ---- liveness: WHOSE silence is it? ---------------------------------
    # These exist because of a measured failure mode, not for symmetry.
    # When the runner freezes, gc_pusher.collect() drops from hundreds of
    # series to FIVE - running / status_age_sec / status_malformed /
    # status_missing / status_stale. Every money tile above then renders
    # its LAST value forever (stat panels reduce lastNotNull over the
    # window), so a frozen bot reads as a calm, profitable book. Retiled
    # 5/5/5/4 -> 6/6/6/6 (2026-08-28) after the Telemetry tile's removal
    # left this line four tiles instead of five, still evenly filling 24
    # columns.
    state("Runner", M("liquiditybot_running"), 6, 5, UP_DOWN,
          desc="Is the bot's own loop alive. STOPPED here means every money "
               "tile above is a fossil, however healthy it looks.")
    state("Kraken feed", M("liquiditybot_ws_kraken_connected"), 6, 5, WS,
          desc="Kraken websocket. REST means degraded marks, not an outage.")
    state("Op state", M("liquiditybot_op_state"), 6, 5, OPSTATE,
          desc="Overall operating state. Distinct from the Halt tile: that "
               "is the circuit breaker alone, this is the whole posture.")
    # posture tile: the mode the bot ITSELF reports (liquiditybot_dry_run,
    # born presence-guarded — an absent mode key emits NO series, so this
    # tile can never render LIVE from silence; the registry's "state
    # unknown" text answers instead). PAPER is the expected steady state
    # and reads calm blue; LIVE is EXTRAORDINARY on this bot (dry_run
    # defaults true; the only road to live is config + restart + typed ARM
    # LIVE) and earns the red accent — not "unsafe", "look up from the
    # coffee". -1 is the exporter's sentinel for a mode string it does not
    # recognize.
    state("Paper / Live", M("liquiditybot_dry_run"), 6, 5,
          {"1": ("PAPER", "blue"), "0": ("LIVE", "red"),
           "-1": ("unknown", GRAY_HEX)},
          desc="Which mode the bot itself reports. PAPER: dry-run, no real "
               "order leaves the bot. LIVE: real money - deliberate red "
               "accent so it can never be missed. 'unknown' means the "
               "runner wrote a mode this board does not recognize.")

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
               "open, 0 series). Read the Runner and Data age tiles before "
               "concluding anything from an empty table. ERA-8: this book "
               "is EXPECTED quiet (derived entry bar 0.8335, conviction "
               "entries effectively stopped at true costs) - an empty table "
               "now is the strategy's honest position, not a fault; read "
               "Runner/Data age to tell that apart from a frozen bot.")

    # ---- activity & budget: what the bot is DOING with the book ----------
    # STREAM 7c (2026-08-28): Exposure-by-asset removed (the positions
    # table one row up already shows notional per symbol - a pie of the
    # same handful of slices answered nothing new). Daily/weekly loss
    # budget gauges and Size taper removed - they duplicated the Problems
    # board's canonical "Risk brakes" row byte-for-byte; live there once.
    # Fills so far folded into Fill mix's own legend (both slices sum to
    # the same total the removed stat showed).
    row("Activity & budget")
    donut("Fill mix",
          [(M("liquiditybot_order_maker_fills"), "maker (earned the spread)"),
           (M("liquiditybot_order_taker_fills"), "taker (paid the spread)")],
          12, 7, colors={"maker (earned the spread)": GREEN,
                        "taker (paid the spread)": ORANGE_HEX},
          unit="", decimals=0,
          desc="Of all fills since restart, how many were patient maker "
               "orders vs paying the spread to cross. Mostly-maker is the "
               "cheap, healthy shape at this account size. Total fills = "
               "the two slice values summed (the separate 'Fills so far' "
               "tile was folded in here 2026-08-28); read them off the "
               "legend or hover tooltip.")
    stat("Profit pools", f'{M("liquiditybot_savings")} + '
         f'{M("liquiditybot_reserve")}', 12, 7, unit=USD, decimals=2,
         graph="none", steps=GRN,
         desc="Money skimmed out of the trading float into the savings and "
              "reserve pools. It counts in equity but is no longer at risk.")


_EXEC_SIGNPOST_MD = """\
### This board was retired 2026-08-27 (STREAM 7c, `034e6aa6`)

Every metric the alert rules fire on — `liquiditybot_ml_brier`,
`liquiditybot_ml_baseline_brier`, `liquiditybot_ml_drift_share`,
`liquiditybot_monitor_level` — lives on
[**🚨 Problems → "What the pager watches"**](/d/liquiditybot-problem-solution),
as the same arithmetic the rules run. It is kept in ONE place so the pager's
inputs cannot drift between two copies
(`test_problem_board_mirrors_both_pager_conditions` pins the mirror).

This page stays only as a nav anchor; nothing here queries data, so there is
no outage to read into an empty render. Alert rules themselves:
`docs/grafana/liquiditybot_*_alert.yaml` (Brier gap · drift-stuck ·
telemetry dead-man).
"""


def _author_execution():
    """RETIRED to its stripped form, STREAM 7c (2026-08-28 audit).

    The audit's measurement (`scripts/gate_efficacy_report.py --json` +
    `test_problem_board_mirrors_both_pager_conditions`): every metric the
    two alert rules fire on (liquiditybot_ml_brier / _ml_baseline_brier /
    _ml_drift_share / _monitor_level) is ALREADY on the PROBLEMS board's
    "What the pager watches" row, as the SAME arithmetic the rules run —
    proven independently, not asserted. This board's six data panels were
    a byte-for-byte second copy of that row. Fewer, better panels: the
    board file and uid are KEPT (nav link, `test_expected_boards_present`,
    `_EXEC_STRIPPED_PANELS`), only the content is gone — exactly the
    2026-08-15 strip's own precedent, applied to a board that turned out
    to duplicate rather than originate its content. To rebuild, write
    factory calls back into this stub; nothing else has to be restored
    first.

    SIGNPOST ADDED 2026-08-30: the strip shipped WITHOUT the honest
    empty-state text the board description promised, so the rendered page
    was the glass skin alone — pure black, and the operator read it as a
    fault (the exact misread 452bad12's honest-absence contract exists to
    prevent: "a board must say WHY it is empty"). One core `text` panel now
    says why the board is empty and where the inputs live. It queries
    nothing, so the stripped-form contract (zero DATA panels) is intact —
    the pin moves to include it in the same commit.
    """
    text("Where the alert inputs live", _EXEC_SIGNPOST_MD, 14, 9)


def _author_learning():
    """THE LEARNING BOARD - is the bot getting smarter, on a 30-day clock.

    Long-term read: ships with a 30-day default range, every trend panel
    judged across weeks, not scrapes. Layout follows the LEARNING BRAIN
    decision ladder (supply -> corpus -> quality -> governor). Every
    metric verified against gc_pusher.collect() (the ACCURACY RULE in
    _author_command applies here verbatim).

    STREAM 7c REBUILD (2026-08-28, `scratchpad/sdd/grafana-audit.md`):
    nine duplicate/near-duplicate panels retired — 45 data panels down to
    36. Calibration gap folded onto Hit-rate-vs-claimed as a third line;
    Where-labels-come-from folded onto Corpus growth as an extra series;
    the raw/loaded gauges (15/16) and the era-mix-alarm state (28) merged
    into their stat-tile twins' descriptions, keeping every caveat that
    made the merged-away panel worth having; Labels-in-24h, Tuition-cap,
    Refunds-in-24h, and Base-win-rate-the-gates-see removed as
    context/duplicate reads folded into a surviving neighbor's desc.

    THE INSTANT-TILE IDIOM (board-wide on THIS board): every stat tile
    here is graph="none", i.e. an INSTANT query. A range-queried stat
    reduces lastNotNull over the DASHBOARD WINDOW, and this board's window
    is 30 days - a dead producer would render its final value, in its
    healthy color, for a month before the noValue text could fire. That
    is the same fossil mechanism the command board's liveness group
    narrates, stretched 30x - and the exact Brier-incident shape
    (ab8ee2b4: last real reading a breach, then ten silent green days).
    An instant query falls off within Prometheus' ~5m lookback, so
    absence becomes visible at the same speed the Data age tile turns
    yellow. Sparklines are given up on tiles ONLY: every trend worth
    seeing has a dedicated timeseries panel, whose bounded spanNulls
    already draws outages as holes.
    """
    # ---- hero: the verdict tiles ----------------------------------------
    gap_good = (f'max(liquiditybot_ml_baseline_brier{JOB}) '
                f'- max(liquiditybot_ml_brier{JOB})')
    stat("Model edge over naive guess", gap_good, 6, 6, decimals=4,
         size="hero", steps=GAP_GOOD_POS, graph="none",
         desc="Positive = the model predicts trade outcomes better than "
              "always guessing the long-run average. (Baseline Brier minus "
              "model Brier; higher is better; the pager fires at -0.03.)")
    # RETITLED 2026-08-20 (operator: "old labels are still on grafana, and
    # im assuming in my bots head"): this tile said "Training rows" while
    # plotting the RAW all-era archive - the era fence keeps most of those
    # OUT of training. A title claiming training-rows on the archive count
    # is the documentation-drift class: a tile lying about itself. The
    # archive stays panelled - it is the falsifier population - but under
    # its true name. MERGED 2026-08-28 (audit id=2<-15): the raw-training-
    # rows GAUGE plotted the SAME metric a second time; its 640-floor
    # caveat prose (the overfit battery's real-data reference line) is
    # folded in below rather than lost.
    stat("Corpus rows (all eras, archive)",
         M("liquiditybot_ml_history_rows"), 4, 6,
         decimals=0, steps=BLUE, graph="none",
         desc="Every row ever recorded across ALL geometry/fill eras - the "
              "archive, NOT what the model learns from. The era fence "
              "excludes old-era rows from training; 'Rows teaching the "
              "model' beside this is the number in the bot's head. The "
              "overfit battery's real-data floor for LOADED rows is 640 - "
              "read the battery's own summary line for which corpus it "
              "ran on, never this count.")
    # MERGED 2026-08-28 (audit id=3<-16): same story as above, for the
    # loaded-rows gauge.
    stat("Rows teaching the model", M("liquiditybot_ml_loaded_rows"), 4, 6,
         decimals=0, steps=BLUE, graph="none",
         desc="Rows that SURVIVED loading filters (era fence, hygiene, "
              "clash drops) at the last retrain - the labels actually in "
              "the bot's head right now. Read beside 'Corpus rows (all "
              "eras, archive)': the gap is what hygiene and the era fence "
              "ate. 640 is the overfit battery's real-data floor for this "
              "count as a REFERENCE scale, not a success line - the "
              "battery's own summary line is the authority, never this "
              "tile.")
    stat("Clean live labels", M("liquiditybot_ml_live_clean"), 4, 6,
         decimals=0, graph="none",
         steps=[{"color": "red", "value": None},
                {"color": "yellow", "value": 30},
                {"color": "green", "value": 150}],
         desc="Live-outcome rows that survived hygiene checks - the highest-"
              "value food the model gets. Under 30, the loop is starved and "
              "every quality number below is a hypothesis, not a finding. "
              "As of the last retrain's corpus load.")
    state("Model in use", M("liquiditybot_ml_use_model"), 3, 6,
          {"1": ("YES", "green"), "0": ("benched", GRAY_HEX)},
          desc="Whether the governor lets the model influence sizing. "
               "'benched' beside green quality tiles is usually a deliberate "
               "stand-down, not a fault.")
    state("Learning health", M("liquiditybot_monitor_level"), 4, 6, GOV,
          desc="The ML governor's own verdict on the model. OK / DEGRADED / "
               "KILLED.")
    stat("Data age", M("liquiditybot_status_age_sec"), 3, 6, unit="s",
         decimals=0, graph="none", size="compact", steps=AGE_STEPS,
         desc="Seconds since the bot last wrote its status. If this climbs, "
              "every other number on this board is a fossil - read it "
              "first.")

    # ---- quality: the trends that mean "smarter" -------------------------
    row("Is it getting smarter?")
    timeseries("Prediction error - model vs naive vs champion",
               M("liquiditybot_ml_brier"), 24, 8, legend="model", decimals=3,
               extra=[(M("liquiditybot_ml_baseline_brier"), "naive guess"),
                      (M("liquiditybot_ml_champion_brier"), "champion")],
               colors={"model": INDIGO, "naive guess": GRAY_HEX,
                       "champion": CAT_TEAL},
               desc="Brier score: how wrong the win-probability estimates "
                    "are (lower is better; 0.25 is a coin flip). The model "
                    "line staying UNDER the naive line, week after week, is "
                    "what 'getting smarter' looks like.")
    # the disambiguator: separates "window filling" from "judge dead" —
    # absent/zero here with old Brier numbers means the judge stopped
    # scoring, not that the model went quiet
    stat("Trades the judge has scored",
         M("liquiditybot_ml_window_trades"), 6, 8, decimals=0, graph="none",
         steps=[{"color": "text", "value": None},
                {"color": "green", "value": JUDGE_MIN}],
         desc=f"How many recent closes the model judge has scored - the "
              f"Brier tiles wake at {JUDGE_MIN}. Zero or absent here while "
              f"Brier numbers sit unchanged means the judge is dead, not "
              f"the model healthy.")
    # MERGED 2026-08-28 (audit id=13->11): "Calibration gap" was a second
    # timeseries restating the visible distance between this panel's
    # actual/claimed lines. Rides in as a fourth line instead.
    timeseries("Hit rate vs claimed probability",
               M("liquiditybot_ml_hit_rate"), 6, 8, unit="percentunit",
               legend="actual win rate", decimals=1,
               extra=[(M("liquiditybot_ml_avg_p"), "claimed probability"),
                      (M("liquiditybot_ml_hit_rate_lcb"),
                       "conservative floor"),
                      (M("liquiditybot_ml_calibration_gap"),
                       "calibration gap")],
               colors={"actual win rate": GREEN,
                       "claimed probability": INDIGO,
                       "conservative floor": GRAY_HEX,
                       "calibration gap": ORANGE_HEX},
               desc="If the model claims 65% and wins 45%, its sizing is "
                    "built on a lie. Honest = the claimed line hugging the "
                    "actual line; on small samples trust the conservative "
                    "floor. 'calibration gap' is the distance between "
                    "claimed and reality plotted directly - small is "
                    "honest, widening turns into sizing errors because "
                    "position size reads these probabilities literally.")
    timeseries("Feature drift share", M("liquiditybot_ml_drift_share"), 6, 8,
               unit="percentunit", legend="drift share", decimals=1,
               desc="Share of the model's inputs that look different from "
                    "what it trained on. High AND stuck means the market "
                    "moved and the model has not.")

    # ---- supply: is there anything to learn from? ------------------------
    row("Is the pipeline filling?")
    gauge("New-era rows toward re-arm", M("liquiditybot_era_excl_new_rows"),
          8, 6, mn=0, mx=150, unit="", decimals=0,
          steps=[{"color": "blue", "value": None},
                 {"color": "green", "value": 150}],
          desc="Rows collected under the CURRENT trading geometry. Old-era "
               "rows sit out of training until this reaches the re-arm line "
               "(liquiditybot_era_excl_min_rows, default 150).")
    # MERGED 2026-08-28 (audit id=19->18): "Labels in the last 24h" was the
    # same floor read over a shorter, noisier window.
    stat("Labels per day",
         M("liquiditybot_probe_budget_live_labels_per_day_7d"), 8, 6,
         decimals=1, steps=PROBE_LABELS, graph="none",
         desc="7-day average of live labels earned per day. Under 3 a day "
              "the corpus fills slower than the floor pace. A closer, "
              "noisier 24h reading lives at liquiditybot_probe_budget_"
              "labels_24h if today's pace specifically matters.")
    stat("Label uniqueness", M("liquiditybot_ml_mean_uniqueness"), 8, 6,
         decimals=1, steps=HIGH_GOOD, graph="none",
         desc="How independent the labels are - overlapping trades share "
              "evidence, so 100 rows at 0.05 uniqueness carry about 5 rows "
              "of real information. As of the last retrain's corpus load.")
    # MERGED 2026-08-28 (audit id=22->21): "Where labels come from" plotted
    # the SAME corpus-fill question from a second angle (origin instead of
    # cleanliness) - rides in as a third target instead of a second panel.
    timeseries("Corpus growth", M("liquiditybot_ml_history_rows"), 12, 8,
               legend="all rows", decimals=0,
               extra=[(M("liquiditybot_ml_live_clean"), "clean live rows"),
                      (_pa("liquiditybot_ml_labels"), "{{source}}")],
               colors={"all rows": CAT_TEAL, "clean live rows": GREEN},
               desc="The corpus filling over the month. Both flat: the bot "
                    "is not closing trades. All-rows climbing while "
                    "clean-live stays flat: hygiene is eating the rows. "
                    "The by-source lines split labelled rows by origin - "
                    "live closes (gold standard) vs simulated candidates "
                    "(fill in while live experience accumulates).")
    # 2026-08-20: the era split, previously exported but never panelled -
    # the one chart that answers "are old labels in the bot's head" at a
    # glance (current-era line vs the retired-era lines the fence excludes).
    timeseries("Labels by era (fence view)", _pa("liquiditybot_era_rows"),
               12, 8, legend="{{era}}", decimals=0,
               desc="Loaded-corpus rows split by label era, as of the last "
                    "retrain. Only the CURRENT era teaches the model; every "
                    "other line is archive the era fence keeps out of "
                    "training. Old eras flat + current era climbing = the "
                    "fence working as designed.")

    # ---- what the labels themselves say ----------------------------------
    row("What the labels say")
    # TB_ERA, never a literal: the un-suffixed "triple_barrier" is the
    # RETIRED 96-bar era (see the config-derived constants block at the
    # top of this file); a hardcoded era here is a dark panel on a healthy
    # bot, and a hardcoded h432 re-poisons on the next horizon migration.
    _tb = (f'liquiditybot_era_reason_rows{{job="liquiditybot",'
           f'era="{TB_ERA}",reason="%s"}}')
    donut("How this era's trades ended",
          [(f"max({_tb % 'tb_pt'})", "hit profit target"),
           (f"max({_tb % 'tb_sl'})", "hit the stop"),
           (f"max({_tb % 'tb_time'})", "timed out")],
          8, 8, colors={"hit profit target": GREEN,
                        "hit the stop": RED_HEX,
                        "timed out": GRAY_HEX},
          unit="", decimals=0,
          desc=f"Outcome mix of current-era ({TB_ERA}) labelled trades, as "
               "of the last retrain's corpus load. A healthy edge needs "
               "enough profit-target exits to pay for all the stops.")
    stat("Label rate this era",
         f'max(liquiditybot_era_label_rate{{job="liquiditybot",'
         f'era="{TB_ERA}"}})', 4, 8, unit="percentunit", decimals=1,
         steps=HIGH_GOOD, graph="none",
         desc="Share of current-era rows that earned a definite win/loss "
              "verdict (the rest timed out unresolved or are still open). "
              "As of the last retrain's corpus load.")
    # MERGED 2026-08-28 (audit id=28->27): "Corpus matches live?" state
    # tile thresholded the SAME tvd value this stat already shows raw -
    # the 0.3/0.5 thresholds below already say DRIFTED in color.
    stat("Corpus drift distance", M("liquiditybot_era_mix_tvd"), 4, 8,
         decimals=2, steps=DRIFT, graph="none",
         desc="How different the whole training corpus looks from recent "
              "live trading (0 = identical, 1 = nothing in common) - "
              "yellow at 0.3, red at 0.5 (DRIFTED, liquiditybot_era_mix_"
              "alarm's own line): the model is learning mostly from a "
              "market that no longer exists, treat its opinions with "
              "suspicion until the mix re-aligns. As of the last retrain's "
              "corpus load.")
    stat("Rows excluded from training", M("liquiditybot_era_excl_dropped"),
         4, 8, decimals=0, steps=BLUE, graph="none",
         desc="Old-geometry rows the era fence keeps OUT of training so "
              "stale lessons cannot leak into the current model. As of the "
              "last retrain's corpus load.")

    # ---- lineage: which model is driving ---------------------------------
    row("Which model is driving")
    timeseries("Deployed model over time", _pa("liquiditybot_ml_model_info"),
               12, 7, legend="{{kind}}", decimals=0,
               desc="Which model family is deployed (its line sits at 1 "
                    "while active). A step from one line to another is a "
                    "redeploy; the full lineage ledger with Brier evidence "
                    "lives in outputs/registry.jsonl.")
    state("Retrain queued", M("liquiditybot_ml_retrain_flag"), 4, 7, RETRAIN,
          desc="QUEUED means the trainer will rebuild the model on its next "
               "pass - routine housekeeping, not an alarm.")
    stat("Retrain failures", M("liquiditybot_ml_retrain_failures"), 4, 7,
         decimals=0, graph="none", steps=ZERO_BAD,
         desc="Times the retrain loop crashed. Anything above zero deserves "
              "a look at the runner log.")
    stat("Model fallbacks", M("liquiditybot_ml_model_fallbacks"), 4, 7,
         decimals=0, graph="none", steps=ZERO_BAD,
         desc="Times inference fell back to the safe default instead of "
              "the deployed model.")
    # lifecycle + orphan: the panels fed by gc_pusher's LEDGER-derived aux
    # batch rather than status.json — their families are declared above
    # and the board coverage gates include collect_aux() on fixture
    # ledgers (the aux section header's contract).
    bargauge("Model lifecycle events", _pa("liquiditybot_ml_lineage_events"),
             16, 6, legend="{{event}}", decimals=0, steps=BLUE, mn=0,
             desc="Lifetime counts from the model registry ledger: models "
                  "registered (a retrain produced a candidate), deployed "
                  "(it took the wheel), rejected (the deploy gate refused "
                  "it). 'other' bundles every rarer event so nothing is "
                  "invisible. Counts cover the ledger's whole history, not "
                  "the dashboard window.")
    # NOT percentunit, deliberately, against the panel brief: orphan_ratio
    # is trained_rows / n_rows (ml/retrain_log.py:57-59) — a scale-free
    # MULTIPLE that measured 48.4x in the 2026-08-14 incident, not a 0..1
    # share, and this file's own HIG doctrine forbids percentunit on a
    # value that is not a part-of-whole (48.4 would render "4840%").
    # Thresholds cite the code: ML-083 fires on watermark > corpus
    # (main.py:6596, strict >1) and ~3.2x is the scale the unlock was
    # designed for (ml/retrain_log.py docstring). Base "text": absence
    # must read as absence, and sub-1x is the routine growing-corpus
    # state, no verdict color earned.
    stat("Is the model orphaned?", M("liquiditybot_ml_orphan_ratio"), 8, 6,
         unit="suffix:x", decimals=2, graph="none",
         steps=[{"color": "text", "value": None},
                {"color": "yellow", "value": 1},
                {"color": "red", "value": 3.2}],
         desc="The deployed model's training watermark against the corpus "
              "that exists today, from the retrain ledger's last record. "
              "Below 1.00x is routine (the corpus grew since the model "
              "trained). Above 1x the model learned from rows an era reset "
              "has since removed - the ML-083 cold-start unlock territory. "
              "The 2026-08-14 incident ran at 48x when ~3.2x was the "
              "designed-for scale.")

    # ---- the verdict clock -----------------------------------------------
    # COUNT ONLY, by law: gc_pusher._run_cohort_eval never parses the
    # gross/net means (accrual moratorium — the accruing gate numbers are
    # not a trend), so a count and its floor are the only things that CAN
    # render here; keep it that way. The target comes from the metric
    # (liquiditybot_cohort_min_n), never a hardcoded literal.
    row("The verdict clock")
    bargauge("Era-4 verdict progress", M("liquiditybot_cohort_closes"),
             24, 5, legend="closed trades counted", decimals=0, steps=BLUE,
             mn=0,
             extra=[(M("liquiditybot_cohort_min_n"),
                     "pre-registered target")],
             desc="Closed trades counted toward the pre-registered verdict, "
                  "against the target the readout needs - the target is "
                  "read from the bot, never hardcoded. The gate DECIDES "
                  "nothing until the target is reached, and the accruing "
                  "win/loss numbers are deliberately on no board: reading "
                  "them early is how a verdict gets tuned instead of "
                  "measured. Count refreshes about every 30 minutes.")

    # ---- the price of tuition (collapsed: read on demand) ----------------
    row("The cost of learning", collapsed=True)
    gauge("Probe tokens in the tank", M("liquiditybot_probe_budget_tokens"),
          6, 6, mn=0, mx=5, unit="", decimals=1,
          steps=[{"color": "red", "value": None},
                 {"color": "yellow", "value": 1},
                 {"color": "green", "value": 2.5}],
          desc="Small exploratory trades are paid for in tokens; an empty "
               "tank means no new probes until it refills (capacity: "
               "liquiditybot_probe_budget_capacity).")
    # MERGED 2026-08-28 (audit id=42->41): "Tuition cap" was a static ceiling
    # this spend is judged against, not its own reading.
    stat("Tuition spent in 24h",
         M("liquiditybot_probe_budget_tuition_24h_usd"), 5, 6, unit=USD,
         decimals=2, steps=GRN, graph="none",
         desc="What the probes cost in the last day - the price paid for "
              "the labels they earned. Judged against the daily cap "
              "(liquiditybot_probe_budget_tuition_cap_usd) - the most the "
              "bot may spend on learning per day.")
    stat("Unlock ETA", M("liquiditybot_probe_budget_unlock_eta_days"), 4, 6,
         unit="suffix:d", decimals=1, steps=PROBE_ETA, graph="none",
         desc="Projected days until enough current-era labels exist to "
              "unlock the next model step, at the current pace.")
    stat("Probes open now", M("liquiditybot_probe_budget_open_probes"), 5, 6,
         decimals=0, graph="none", steps=BLUE,
         desc="Exploratory positions currently on the book.")
    stat("Denied - budget empty",
         M("liquiditybot_probe_budget_denied_exhausted_24h"), 8, 5,
         decimals=0, graph="none",
         steps=[{"color": "text", "value": None},
                {"color": "yellow", "value": 20},
                {"color": "red", "value": 100}],
         desc="Probe attempts turned away in the last day because the token "
              "tank was empty. High means the bot wants to learn faster "
              "than the budget allows.")
    stat("Probe governor", M("liquiditybot_probe_budget_governor_factor"),
         8, 5, decimals=2, steps=PROBE_GOV, graph="none",
         desc="Throttle on probe spending (1.00 full speed, 0.25 floor). It "
              "backs off when tuition outruns the labels earned.")

    # ---- learned gate weights (collapsed: read on demand) ----------------
    row("Gate learning", collapsed=True)
    bargauge("Learned gate weights", _pa("liquiditybot_gate_weight"), 12, 8,
             legend="{{gate}}", decimals=2, steps=BLUE, mn=0, mx=1,
             desc="How much say each entry gate has earned from labelled "
                  "outcomes. A gate near zero is being ignored.")
    # MERGED 2026-08-28 (audit id=52->50): "Base win rate the gates see"
    # is context, not its own verdict.
    bargauge("Is any gate lying?", _pa("liquiditybot_gate_divergence"),
             12, 8, legend="{{gate}}", decimals=2, steps=DRIFT, mn=0,
             desc="Gap between what a gate predicts and what actually "
                  "happens (divergence from the base rate,"
                  " liquiditybot_gate_base_rate — the long-run average "
                  "win rate the gates are judged against). High means "
                  "that gate's opinion is misleading right now.")
    stat("Labeled rows feeding the gates", M("liquiditybot_gate_labeled"),
         12, 5, decimals=0, steps=BLUE, graph="none",
         desc="Sample size behind the two panels above - small numbers "
              "mean noisy weights.")


def _author_problem():
    """THE PROBLEMS BOARD - what needs attention. Looking empty is GOOD.

    Reading order is the reading order of an incident: posture hero (is
    anything on fire), the two pager conditions AS THE SAME ARITHMETIC THE
    RULES RUN (the execution board's lesson: a rule whose inputs are on no
    board is discovered by being paged), then fault tallies, staleness,
    the risk brakes, and the audit trail's own health. Every metric
    verified against gc_pusher.collect(); the ACCURACY RULE in
    _author_command applies verbatim.

    STREAM 7c REBUILD (2026-08-28, `scratchpad/sdd/grafana-audit.md`):
    48 data panels down to 43 (the audit's own header claimed "47 data" —
    recounted directly against the shipped pin list and corrected here;
    the instrument-suspicion doctrine applies to audits too). Telemetry
    folded into Data age; Model-inference/Feature-contract faults merged
    into one two-series tile; the stale/diverging/critical watchdog trio
    merged into one tile; Firewall-trips-by-code now FILTERS to actual
    trip codes instead of plotting the always-present lifecycle counters
    under a "by code" title; the cumulative "Why entries die" timeseries
    is retired in favor of its own per-hour companion (a slope read off a
    cumulative line was the thing the per-hour panel existed to remove);
    the veto-quality roster now charts the codes that actually fire
    (SZ-021/SZ-030/SZ-049 in, never-fired PT-040/PT-041 out); and
    "Confounded verdicts" is MUTATED into the confound-visibility bargauge
    the audit named as the one permitted new element.
    """
    # ---- hero: is anything on fire? --------------------------------------
    state("Overall posture", M("liquiditybot_op_state"), 5, 6, OPSTATE,
          desc="The whole bot's operating state in one word. ARMED is "
               "normal; anything else is why the bot is holding back.")
    state("Halted?", M("liquiditybot_halted"), 4, 6, HALT,
          desc="The master circuit breaker. 'clear' is healthy; HALTED "
               "blocks all NEW risk while exits keep running.")
    state("New trades blocked?", M("liquiditybot_watchdog_entries_blocked"),
          4, 6, {"1": ("BLOCKED", "red"), "0": ("open", "green")},
          desc="The data watchdog's entry gate. BLOCKED means the feeds are "
               "too stale or divergent to trust with new money.")
    stat("Active faults", M("liquiditybot_fault_count"), 4, 6, decimals=0,
         graph="none", steps=ZERO_BAD,
         desc="Latched fault conditions right now. Zero is the only good "
              "number; each fault names its reason code in the audit "
              "trail.")
    state("Risk firewall", M("liquiditybot_firewall_fault"), 4, 6,
          {"1": ("TRIPPED", "red"), "0": ("quiet", "green")},
          desc="Last line of defense before an order leaves the bot. "
               "TRIPPED means it latched a violation and refuses new risk.")
    stat("Data age", M("liquiditybot_status_age_sec"), 3, 6, unit="s",
         decimals=0, graph="none", size="compact", steps=AGE_STEPS,
         desc="Seconds since the bot last wrote its status. Past 5 minutes "
              "every tile on this board describes the past - read it "
              "first. Subsumes the separate Telemetry STALE/fresh tile "
              "(merged 2026-08-28): the exporter itself marks the whole "
              "batch STALE past 120s (STALE_AFTER_SEC), tighter than this "
              "tile's own 300s red line.")

    # ---- the pager's own arithmetic --------------------------------------
    row("What the pager watches")
    gap = (f'max(liquiditybot_ml_brier{JOB}) '
           f'- max(liquiditybot_ml_baseline_brier{JOB})')
    stat("Model worse than naive by", gap, 6, 6, decimals=4,
         steps=GAP_BAD_POS, graph="none",
         desc="Mirrors the REPO's copy of the Brier rule "
              "(liquiditybot_brier_alert.yaml: above 0.03 for 15 minutes "
              "pages). Red here means the page is coming. Two things this "
              "tile cannot see: the live instance's rule can drift from "
              "the repo copy, and when the series is ABSENT the alert "
              "holds green (noDataState: OK) while this tile shows its "
              "empty-state text instead.")
    stat("Trades the judge has scored",
         M("liquiditybot_ml_window_trades"), 6, 6, decimals=0, graph="none",
         steps=[{"color": "text", "value": None},
                {"color": "green", "value": JUDGE_MIN}],
         desc=f"The Brier tiles and pager wake at {JUDGE_MIN} model-scored "
              f"closes. Zero or absent here is why the tile beside this "
              f"one is empty - and if it stays absent while trades close, "
              f"the judge is dead, which the pager cannot see.")
    _drift_expr = (f'(max(liquiditybot_ml_drift_share{JOB}) > bool 0.3) * '
                   f'(max(liquiditybot_monitor_level{JOB}) > bool 0)')
    state("Drift stuck while degraded", _drift_expr, 6, 6,
          {"1": ("FIRING", "red"), "0": ("quiet", GRAY_HEX)},
          desc="Mirrors the REPO's copy of the drift rule "
               "(liquiditybot_drift_alert.yaml): feature drift above 30% "
               "WHILE the governor is degraded, held 30 minutes, pages. "
               "The live instance's rule can drift from the repo copy.")
    state("Model governor", M("liquiditybot_monitor_level"), 6, 6, GOV,
          desc="OK / DEGRADED / KILLED - the governor both pagers read. "
               "The learning board explains why it moved.")

    # ---- faults & rejections ---------------------------------------------
    row("Faults & rejections")
    # FIXED 2026-08-28 (audit top-5 #4): liquiditybot_firewall_count also
    # carries FOUR always-present lifecycle counters (screened/accepted/
    # accepted_modified/rejected, execution/risk_firewall.py:131-132) on
    # the SAME metric name — the unfiltered query plotted those, not trip
    # codes, under a "by code" title, and made the honest-empty noValue
    # text ("no firewall trip recorded") unreachable. code=~"FW-.*"
    # restores the actual trip-code view and lets that noValue text fire
    # again when nothing has tripped.
    timeseries("Firewall trips by code",
               'liquiditybot_firewall_count{job="liquiditybot",'
               'code=~"FW-.*"}',
               12, 8, legend="{{code}}", decimals=0,
               desc="Cumulative trips per firewall CODE only (lifecycle "
                    "counters screened/accepted/accepted_modified/rejected "
                    "excluded by the code=~\"FW-.*\" filter) - FW-070/080/"
                    "081 are the data-staleness family. A step up is one "
                    "new trip; codes are decoded in core/codes.py.")
    timeseries("Decisions by family", _pa("liquiditybot_code_count"), 12, 8,
               legend="{{prefix}}", decimals=0,
               desc="Reason-code volume per family (SZ sizing, PT pretrade, "
                    "CV conviction, ...). One family suddenly dominating is "
                    "a behavior change worth explaining.")
    # NOTE on all six counters below: they are in-memory and reset on
    # restart, so a crash-LOOP reads 0 here by construction — each desc
    # names the tell ("Cycles since restart" resetting).
    stat("Venue rejects", M("liquiditybot_order_venue_rejects"), 4, 4,
         decimals=0, graph="none", size="compact", steps=ZERO_BAD,
         desc="Orders Kraken refused. Zero is normal; a burst usually means "
              "rate limits or malformed sizes. Resets on restart - a "
              "crash-loop reads 0; cross-check 'Cycles since restart'.")
    stat("Dead-man failures", M("liquiditybot_order_deadman_failures"), 4, 4,
         decimals=0, graph="none", size="compact", steps=ZERO_BAD,
         desc="Failed refreshes of the dead-man cancel timer that flattens "
              "orders if the bot goes silent. Resets on restart - a "
              "crash-loop reads 0; cross-check 'Cycles since restart'.")
    stat("Exit-check failures", M("liquiditybot_exit_eval_failures"), 4, 4,
         decimals=0, graph="none", size="compact", steps=ZERO_BAD,
         desc="Cycles where evaluating an exit crashed. Exits are the one "
              "thing that must never fail - any number here is urgent. "
              "Resets on restart; cross-check 'Cycles since restart'.")
    stat("Cycle failures in a row",
         M("liquiditybot_cycle_consecutive_failures"), 4, 4, decimals=0,
         graph="none", size="compact", steps=ZERO_BAD,
         desc="Consecutive whole-cycle crashes. The loop retries, but a "
              "climb here means it is wedged on something. Resets on "
              "restart - a crash-loop reads 0; cross-check 'Cycles since "
              "restart'.")
    # MERGED 2026-08-28 (audit id=19+20): both answer "is inference
    # rejecting the world" - one tile, two bars, instead of two tiles.
    bargauge("Model & feature faults", M("liquiditybot_ml_infer_faults"),
             8, 4, legend="inference faults", decimals=0, steps=ZERO_BAD,
             mn=0,
             extra=[(M("liquiditybot_ml_contract_failed"),
                     "feature-contract failures")],
             desc="Inference faults: times the model failed to score a "
                  "candidate and the safe default was used instead. "
                  "Feature-contract failures: rows that violated the "
                  "model's input contract and were refused - rising means "
                  "the feed and the model disagree about the world's "
                  "shape. Both reset on restart - a crash-loop reads 0; "
                  "cross-check 'Cycles since restart'.")

    # ---- staleness & feeds -----------------------------------------------
    row("Staleness & feeds")
    stat("Feed latency", M("liquiditybot_feed_latency_ms"), 4, 5, unit="ms",
         decimals=0, steps=LAT,
         desc="Round-trip time fetching market data. Slow feeds mean stale "
              "decisions.")
    stat("Price marks age", M("liquiditybot_marks_age_sec"), 4, 5, unit="s",
         decimals=0, steps=MARKS_AGE,
         desc="Age of the prices used to value open positions. Old marks "
              "mean the P&L numbers are guesses.")
    state("Kraken feed", M("liquiditybot_ws_kraken_connected"), 4, 5, WS,
          desc="The live price stream. REST means degraded (polling) "
               "marks, not an outage.")
    stat("Feed reconnects", M("liquiditybot_ws_kraken_reconnects"), 4, 5,
         decimals=0, graph="none", steps=RECONNECTS,
         desc="Times the websocket dropped and re-dialed since restart. A "
              "climb means an unstable link.")
    # MERGED 2026-08-28 (audit id=26+27+28, "the watchdog trio"): one
    # bargauge answers "which feed problem" at a glance instead of three
    # tiles read separately.
    bargauge("Feed watchdog", M("liquiditybot_watchdog_stale_assets"), 12, 5,
             legend="stale assets", decimals=0, steps=ZERO_BAD, mn=0,
             extra=[(M("liquiditybot_watchdog_divergent"),
                     "diverging feeds"),
                    (M("liquiditybot_watchdog_critical_stale"),
                     "critical data stale (1=STALE)")],
             desc="Stale assets: market data aged past the watchdog's "
                  "limit, entries blocked until it freshens. Diverging "
                  "feeds: two data sources disagree about the price, the "
                  "bot refuses to trade what it cannot price. Critical "
                  "data stale: any CRITICAL feed aged out (1=STALE), "
                  "blocking all new entries at once. All zero is the "
                  "healthy state.")
    # gated on the mode the bot itself reports (2026-08-17): the equity
    # recompute runs in LIVE mode only (main.py gates it on `not
    # dry_run`), so in paper mode the exported 0.00 is an initializer,
    # never a verdict. `and (dry_run == 0)` filters the drift value away
    # unless the bot says LIVE — the comparison deliberately carries NO
    # `bool` modifier: the drift mirror above needs a 0/1 and keeps
    # `> bool`, this tile needs ABSENCE, and a bare `==` returns empty
    # on a non-match. Paper mode, unknown mode (-1) and an absent mode
    # key all land on the no_value text instead of a soothing 0.00.
    stat("Books cross-check (live mode)",
         f'{M("liquiditybot_equity_drift_pct")} and '
         f'({M("liquiditybot_dry_run")} == 0)',
         6, 5, unit="percent", decimals=2, steps=EQ_DRIFT, graph="none",
         no_value="accounting cross-check runs in live mode only",
         desc="Drift between reported equity and an independent recompute. "
              "The recompute runs in LIVE mode only, so in paper trading "
              "this tile is EMPTY by construction - the expression filters "
              "on the bot's own mode report, and absence here is the "
              "paper-mode truth, not a fault. In live mode, near zero "
              "means the accounting is telling the truth.")
    # MERGED 2026-08-28 (audit: command 14->12 precedent applied here too):
    # the separate Telemetry STALE/fresh tile folded into "Data age"'s own
    # desc above - one fact, one tile.
    state("Runner", M("liquiditybot_running"), 6, 5, UP_DOWN,
          desc="Is the bot's own loop alive. STOPPED means everything "
               "else shown is the last known state, not the current one.")

    # ---- the risk brakes -------------------------------------------------
    row("Risk brakes")
    gauge("Daily loss budget used",
          M("liquiditybot_rp_daily_budget_used_frac"), 6, 7, mn=0, mx=1,
          unit="percentunit", decimals=0, steps=FRAC_BUDGET,
          desc="How much of today's allowed loss is spent. At 100% new "
               "trades stop until the day rolls over - the lockout state "
               "this board exists to explain.")
    gauge("Weekly loss budget used",
          M("liquiditybot_rp_weekly_budget_used_frac"), 6, 7, mn=0, mx=1,
          unit="percentunit", decimals=0, steps=FRAC_BUDGET,
          desc="Same as the daily budget, over the trading week. NOTE: a "
               "capital sweep can inflate this falsely - see the "
               "budget_reanchor_week control verb.")
    timeseries("Drawdown vs the hard stop",
               M("liquiditybot_rp_drawdown_mtm_pct"), 12, 7, unit="percent",
               legend="drawdown (mark-to-market)", decimals=1,
               extra=[(M("liquiditybot_rp_hard_stop_dd_pct"),
                       "hard-stop line")],
               colors={"drawdown (mark-to-market)": ORANGE_HEX,
                       "hard-stop line": RED_HEX},
               desc="The drawdown the catastrophe stop actually watches, "
                    "against the line where it fires and flattens "
                    "everything.")
    stat("Size taper", M("liquiditybot_rp_taper_mult"), 6, 5, decimals=2,
         graph="none", steps=MULT_LOW_BAD,
         desc="Multiplier on every new position's size. 1.00 full size; "
              "lower means the risk stack is shrinking trades.")
    stat("Drawdown throttle", M("liquiditybot_rp_dd_throttle_mult"), 6, 5,
         decimals=2, graph="none", steps=MULT_LOW_BAD,
         desc="Extra size cut applied while climbing out of a drawdown. "
              "1.00 means no throttle.")
    stat("Portfolio heat", M("liquiditybot_rp_heat_frac"), 6, 5,
         unit="percentunit", decimals=1, steps=HEAT,
         desc="Total risk on the book if every stop filled, as a share of "
              "equity. The stack caps this near 35%.")
    stat("Assets circuit-broken", M("liquiditybot_cb_tripped_count"), 6, 5,
         decimals=0, graph="none", steps=ZERO_BAD,
         desc="Assets benched for repeated losses. They sit out until "
              "their cooldown ends.")
    bargauge("Circuit-breaker cooldown left",
             _pa("liquiditybot_cb_paused_hours_left"), 12, 6, unit="h",
             decimals=1, steps=[{"color": "orange", "value": None}],
             desc="Hours each benched asset still has to sit out. Empty "
                  "with the tile at zero means nothing is benched - the "
                  "good state.")
    bargauge("Loss streak by asset",
             _pa("liquiditybot_perf_asset_cur_loss_streak"), 12, 6,
             decimals=0, steps=STREAK,
             desc="Consecutive losses per asset right now. Streaks are what "
                  "trip the circuit breaker.")

    # ---- the audit trail's own health ------------------------------------
    row("Audit & self-health")
    stat("Audit writes dropped", M("liquiditybot_audit_dropped_writes"),
         6, 5, decimals=0, graph="none", steps=ZERO_BAD,
         desc="Audit-trail records that could not be written. The hash "
              "chain must never lose a link - any number here is urgent.")
    stat("Audit tail truncations", M("liquiditybot_audit_tail_truncations"),
         6, 5, decimals=0, graph="none", steps=ZERO_BAD,
         desc="Times a partial line was cut from the audit tail on "
              "recovery. Expected zero outside crash recovery.")
    stat("Bad values dropped by exporter",
         M("liquiditybot_gauges_dropped_nonfinite"), 6, 5, decimals=0,
         graph="none", steps=ZERO_BAD,
         desc="NaN/Infinity values the telemetry exporter refused to "
              "push. Rising means something upstream is emitting garbage.")
    stat("Cycles since restart", M("liquiditybot_cycle"), 6, 5, decimals=0,
         graph="none", steps=BLUE,
         desc="Decision cycles since the runner last started - a restart "
              "shows as this resetting to zero (lifetime total: "
              "liquiditybot_cycle_lifetime).")

    # ---- the entry/order funnel: why nothing is happening ----------------
    # Appended 2026-08-17 (code-emission funnel audit) AFTER the existing
    # rows so ids 1-46 stay stable — the command board's append-only
    # precedent. Two measured gaps drove it: liquiditybot_code_count_detail
    # was exported and consumed by ZERO panels (the recurring
    # "why-no-entries-for-38h?" question had its answer on the wire and
    # nothing on the glass), and 68% of terminal orders in a 48h window
    # were OM-040 timeout-cancels with no panel saying so.
    row("Why entries die")
    # REMOVED 2026-08-28 (audit: id=48 MERGE->50, operator instruction
    # "keep per-hour, drop cumulative"): the cumulative timeseries required
    # reading a SLOPE to find which check is firing hardest right now; the
    # per-hour companion below answers that directly, no slope-reading
    # required, and is now the sole "why entries die" chart.
    stat("Timeout-cancel share",
         f'{M("liquiditybot_order_timeout_cancels")} / '
         f'({M("liquiditybot_order_terminal_orders")} > 0)',
         8, 8, unit="percentunit", decimals=0, steps=OM_TIMEOUT_SHARE,
         no_value="no terminal orders since restart - or exporter down",
         desc="Of the orders that finished cleanly since restart, the share "
              "that died as OM-040 timeout-cancels - the resting maker "
              "order sat out its whole lifetime without filling - instead "
              "of filling (OM-000). A 48h audit measured 68% AS OF "
              "2026-08-17 - RE-DERIVE before citing, do not treat as "
              "current: query the same two counters over a fresh window. "
              "REPORT-ONLY: the levers this number informs - the "
              "resting-order lifetime (order_manager.order_timeout_sec) "
              "and how far from the touch entries rest "
              "(grid_ladder.spacing_vol_mult / min_spacing_bps) - are "
              "execution geometry, FENCED by the accrual moratorium: "
              "moving them mints a new execution era and needs operator "
              "adjudication. This panel measures; it must never be used "
              "to tune them mid-cohort.")

    # ---- precision companions (2026-08-26, "make this more precisely
    # measured"). The cumulative panel above answers WHICH check fires;
    # these answer the two questions it structurally cannot: how hard is
    # each gate firing NOW (a slope read off a cumulative line is an eye
    # exercise), and - from the labeled counterfactual corpus - was the
    # gate RIGHT. cf_rate is the win rate of what the gate REJECTED, so
    # below-baseline = the veto selected real losers = earning its keep;
    # above-baseline = anti-selective, the SZ-023 defect class of
    # 2026-08-01. The flags carry gate_efficacy_report's own significance
    # discipline (disjoint Wilson intervals on EFFECTIVE n), pooled
    # per code across parametrized disposition variants.
    # FIXED 2026-08-28 (audit top-5 #5 + operator instruction): the
    # roster now charts the codes that ACTUALLY fire. The audit's
    # full-corpus league table (18,588 signal_history rows, double-
    # derived against a 23.5MB audit-trail window): SZ-023 ~4.8k,
    # SZ-022 ~3.0k, SZ-021 2,032 (#3), SZ-030 1,052 (#4) - none of them
    # PT-040/PT-041, which read ZERO in both routes. This panel is now
    # the SOLE "why entries die" chart (the cumulative twin retired
    # above): per-hour vetoes need no slope-reading to see which check
    # is killing entries right now, and a restart dents one sample, not
    # the view.
    _cdr = ('max(delta(liquiditybot_code_count_detail'
            '{{job="liquiditybot",code="{c}"}}[1h]))')
    timeseries("Why entries die (per hour)",
               _cdr.format(c="SZ-023"), 8, 8, decimals=0,
               legend=CODE_LABELS["SZ-023"],
               extra=[(_cdr.format(c=c), CODE_LABELS[c])
                      for c in ("SZ-022", "SZ-021", "SZ-030", "SZ-049")],
               colors={CODE_LABELS["SZ-023"]: INDIGO,
                       CODE_LABELS["SZ-022"]: CAT_TEAL,
                       CODE_LABELS["SZ-021"]: ORANGE_HEX,
                       CODE_LABELS["SZ-030"]: CAT_PURPLE,
                       CODE_LABELS["SZ-049"]: GRAY_HEX},
               desc="Vetoes in the trailing hour for the five checks that "
                    "actually fire (roster fixed 2026-08-28 - SZ-021/"
                    "SZ-030/SZ-049 added, the never-fired PT-040/PT-041 "
                    "dropped). The line on top is the check killing "
                    "entries right now, no slope-reading required, and a "
                    "restart dents one sample, not the view. ERA-8 "
                    "REALITY: the book is EXPECTED quiet (derived entry "
                    "bar 0.8335 since cut #8's fee-truth cut, era "
                    "8-ca55e2ba) - flat or low lines here are the "
                    "strategy's honest position at true costs, not a "
                    "fault; cross-check Data age/Runner before reading a "
                    "quiet board as broken telemetry.")
    bargauge("Were the vetoes right?", _pa("liquiditybot_veto_cf_rate"),
             8, 8, legend="{{code}}", decimals=2, mn=0, mx=1,
             unit="percentunit", steps=BLUE,
             desc="Counterfactual win rate of what each gate REJECTED "
                  "(every veto is labeled; this is the corpus answering "
                  "back), pooled per code with effective-n intervals. "
                  "Read against the candidate baseline "
                  "(liquiditybot_veto_baseline_rate): BELOW baseline = "
                  "the veto selects real losers and earns its keep; AT "
                  "baseline = the gate is not selecting on outcome at "
                  "all; ABOVE = anti-selective - it rejects candidates "
                  "that win MORE than average. FIXED 2026-08-28: a bar "
                  "here is only trustworthy for a code reading COMPARABLE "
                  "on 'Verdict comparability' below (era_overlap >= 0.5) "
                  "- as of 2026-08-27 every code read CONFOUNDED_BASELINE "
                  "or PARTIAL_OVERLAP there, so no code's bar is "
                  "currently a proven example of either earning its keep "
                  "or misfiring; read both panels together before citing "
                  "one.")
    stat("Anti-selective gates",
         'sum(liquiditybot_veto_anti_selective)', 8, 4, decimals=0,
         graph="none",
         # FIXED 2026-08-28 (audit top-5 #6, id=52): base was "green",
         # so the vacuous-green zero (every code CONFOUNDED/PARTIAL,
         # gate_efficacy_report.py's own bar) painted an all-clear its
         # own desc retracted below. Neutral "text": this tile now reads
         # neither verdict on absence/zero, only a real positive count
         # reads red.
         steps=[{"color": "text", "value": None},
                {"color": "red", "value": 1}],
         no_value="veto-quality collector not published yet",
         desc="How many veto codes are rejecting candidates that go on "
              "to win SIGNIFICANTLY more than baseline (disjoint Wilson "
              "intervals on effective n, era-COMPARABLE codes only - "
              "gate_efficacy_report's own bar). Anything above zero "
              "names a gate doing measurable harm; as of 2026-08-26 that "
              "read SZ-021 (crisis), whose vetoed candidates won at 0.51 "
              "against a 0.27 baseline. SUPERSEDED 2026-08-27: that "
              "comparison is CONFOUNDED_BASELINE (zero label_era overlap "
              "with the frozen baseline - docs/HANDOFF.md REG-6 CAVEAT), "
              "so this tile now reads zero for SZ-021 by construction, "
              "not because the question was resolved. The live per-code "
              "lens is 'Verdict comparability (label-era overlap vs "
              "baseline)' below - read that bargauge before trusting a "
              "zero here as a clean verdict rather than an unmeasured "
              "one.")
    stat("Candidate baseline win rate",
         M("liquiditybot_veto_baseline_rate"), 8, 4,
         unit="percentunit", decimals=1, steps=BLUE, graph="none",
         no_value="veto-quality collector not published yet",
         desc="The un-gated candidate win rate the bars above are judged "
              "against (Wilson band on effective n rides the exporter as "
              "veto_baseline_lo/hi).")
    # MUTATED 2026-08-28 (the audit's one permitted new element, applied
    # as a mutation of this existing panel rather than a new one): a bare
    # count of confounded codes said HOW MANY without saying WHICH or how
    # FAR from readable. Per-code bargauge over the report's own
    # era-overlap fraction, thresholded at the report's own policy floors
    # (never tuned to this data), plus the admitted-vs-baseline headline
    # riding in as one more bar - an EXTEND-ONLY exporter addition
    # (liquiditybot_admitted_era_overlap, gc_pusher.py, nothing renamed)
    # so the admitted comparison reaches glass without a second panel.
    bargauge("Verdict comparability (label-era overlap vs baseline)",
             _pa("liquiditybot_veto_era_overlap"), 24, 8,
             legend="{{code}}", decimals=2, mn=0, mx=1,
             unit="percentunit", steps=ERA_OVERLAP_STEPS,
             decode_family="SZ",
             extra=[(M("liquiditybot_admitted_era_overlap"),
                     "admitted (headline)")],
             desc="Per-code label-era overlap of what each veto rejected "
                  "against the frozen baseline, plus the admitted-vs-"
                  "baseline headline as one more bar. Thresholds are "
                  "gate_efficacy_report.py's OWN policy floors "
                  "(ERA_OVERLAP_FLOOR/ERA_OVERLAP_MAJORITY, :111-112), "
                  "not fitted to this data: red <0.05 = "
                  "CONFOUNDED_BASELINE (this code's label_era mix shares "
                  "almost none of the baseline's - no anti-selective/"
                  "selective claim is measurable), yellow <0.5 = "
                  "PARTIAL_OVERLAP (a minority of the baseline is drawn "
                  "from this code's era - read with caution), green "
                  ">=0.5 = COMPARABLE (the comparison is trustworthy). As "
                  "of 2026-08-27 every code read red or yellow - "
                  "'Anti-selective gates' and 'Were the vetoes right?' "
                  "above are reading an unmeasured population, not a "
                  "clean one, until a bar here crosses green.")


_TAGS = ["liquiditybot", "trading", "paper-trading"]
_NAV = [("⌘ Command", "liquiditybot-trading"),
        ("🧠 Learning", "liquiditybot-learning"),
        ("🚨 Problems", "liquiditybot-problem-solution"),
        ("⚙ Alert inputs", "liquiditybot-exec")]


def _links():
    return [{"title": t, "type": "link", "url": f"/d/{u}", "icon": "dashboard",
             "tooltip": "", "targetBlank": False, "asDropdown": False,
             "includeVars": False, "keepTime": True, "tags": []}
            for t, u in _NAV]


def _injector():
    # json.dumps embeds the rules as a JS string literal — no escaping
    # hazards, and the guard keeps re-renders / cross-board SPA navigation
    # from stacking duplicate <style> nodes. The node itself outlives the
    # board (SPA head is tab-lifetime); that is SAFE ONLY because every
    # GLASS_RULES selector is :has(#lb-glass-marker)-scoped — a style that
    # persists but matches nothing off-board. Add an unscoped rule and the
    # 2026-08-30 "alert history screen is black" leak comes straight back.
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
    # SHRUNK 2026-08-17 (29 -> 17): the exporter's presence guards now make
    # halted / entries_enabled / op_state / fault_count / firewall_fault /
    # watchdog_* / audit_* conditional on their key or block existing in the
    # status write, so an old-schema or partial write can no longer export
    # fabricated healthy zeros. Those families moved to
    # _NO_VALUE_BY_FAMILY below with "not in this status write" texts.
    # SHRUNK AGAIN 2026-08-17 (17 -> 11, owed-metrics batch 2): the same
    # guard sweep reached the remaining coerced bools — ml_use_model /
    # ml_retrain_flag / ws_kraken_connected / moomoo_available /
    # moomoo_options_available / positions_open now emit only when their
    # key exists in the status write.
    "liquiditybot_gauges_dropped_nonfinite",
    "liquiditybot_gross_exposure_usd",
    "liquiditybot_haven_info", "liquiditybot_ml_model_info",
    "liquiditybot_open_risk_usd",
    "liquiditybot_open_upnl_usd",
    "liquiditybot_running", "liquiditybot_status_age_sec",
    "liquiditybot_status_malformed", "liquiditybot_status_missing",
    "liquiditybot_status_stale",
})

# The one string that means "this is broken", never "this has not happened".
_NV_DEFECT = "⚠ no series — exporter/pusher, not the bot"

_NV_NOT_WRITTEN = "not in this cycle's status write"
_NV_NO_RETRAIN = "awaiting first retrain (no corpus load)"
# both-cause phrasing (2026-08-17): the window filling is only ONE reason
# this family can be absent — a dead judge or exporter renders identically,
# and text asserting the benign cause alone would soothe over the outage.
# The floor is config-derived (ml.monitor.min_trades_to_judge), never a
# literal: a config change must not turn this text into a lie.
_NV_JUDGE = f"window filling (<{JUDGE_MIN} scored closes) or judge down"

# metric-name PREFIX -> (tier, operator-readable precondition).
# tier "event"   the series cannot exist until the named event happens
# tier "section" the series cannot exist until the runner writes that block
# Every string restates the ACTUAL guard in scripts/gc_pusher.py; the
# file:line of each guard is in the comment beside it.
_NO_VALUE_BY_FAMILY = {
    # gc_pusher.py _veto_quality_metrics: cached subprocess over
    # gate_efficacy_report --json every 30 min; drops (never re-serves) on
    # any failure, and the baseline band is all-or-nothing with the codes
    "liquiditybot_veto_": ("event",
                           "veto-quality collector not published yet"),
    # ERA-8 fix-wave (2026-08-28): the admitted-vs-baseline headline rides
    # the SAME _run_veto_quality cache and fails closed the same way —
    # distinct family from liquiditybot_veto_ only because the metric
    # name itself doesn't share that prefix.
    "liquiditybot_admitted_": ("event",
                               "veto-quality collector not published yet"),
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
    # gc_pusher.py:929-934  per asset+horizon markout sample
    "liquiditybot_markout_bps": ("event", "awaiting first post-fill markout"),
    # gc_pusher.py:755-763 <- ml/monitor.py:773 `if w is not None` <- :225-226
    # `if len(recs) < self.min_trades: return None`, min_trades default 15
    "liquiditybot_ml_brier": ("event", _NV_JUDGE),
    "liquiditybot_ml_baseline_brier": ("event", _NV_JUDGE),
    "liquiditybot_ml_calibration_gap": ("event", _NV_JUDGE),
    "liquiditybot_ml_hit_rate": ("event", _NV_JUDGE),
    "liquiditybot_ml_avg_p": ("event", _NV_JUDGE),
    "liquiditybot_ml_window_trades": ("event", _NV_JUDGE),
    # gc_pusher.py:796-802  ls = ml["load_stats"], written only by a
    # completed HistoryStore.load_training_data (main.py:6245 auto-retrain)
    "liquiditybot_ml_live_clean": ("event", _NV_NO_RETRAIN),
    "liquiditybot_ml_mean_uniqueness": ("event", _NV_NO_RETRAIN),
    "liquiditybot_ml_dropped_dirty": ("event", _NV_NO_RETRAIN),
    "liquiditybot_ml_dropped_clash": ("event", _NV_NO_RETRAIN),
    "liquiditybot_ml_prior_skew": ("event", _NV_NO_RETRAIN),
    # load_stats.era_mix_drift: absent when no retrain has run OR when the
    # mix check itself declined to fire — both-cause text, not one benign
    # cause (2026-08-17 honesty sweep)
    "liquiditybot_era_mix_": ("event",
                              "no retrain or mix check yet - or feed down"),
    # gc_pusher.py:824  `if ls:` gates the WHOLE era block — same root cause
    "liquiditybot_era_": ("event", _NV_NO_RETRAIN),
    # gc_pusher.py:899-900  `bd_n > 0`
    "liquiditybot_bracket_divergence_":
        ("event", "awaiting first bracket close"),
    # gc_pusher.py:551-554 / :555-565  zero-iteration over empty dicts
    "liquiditybot_conviction_denials": ("event", "no conviction denial yet"),
    "liquiditybot_conviction_regime_":
        ("event", "awaiting first regime-bucketed eval"),
    # gc_pusher.py:230-232  avg_cost_24h is None until the first admit
    "liquiditybot_probe_budget_avg_cost_24h":
        ("event", "awaiting first probe admit"),
    # gc_pusher.py:1004-1007  loop over cb["tripped"], empty when nothing paused
    "liquiditybot_cb_paused_hours_left":
        ("event", "no asset circuit-breaker tripped"),
    # gc_pusher.py:963-966  loop over firewall["counters"]
    "liquiditybot_firewall_count": ("event", "no firewall trip recorded"),
    # gc_pusher.py ws_kraken block — the whole family (connected included
    # since guard batch 2) is gated on its key existing in the block
    "liquiditybot_ws_": ("section", "kraken websocket block not written"),
    # ---- presence-guarded fault/health family (2026-08-17) --------------
    # These left _ALWAYS_ON when the exporter gained presence guards: an
    # absent key/block now emits NO series instead of a fabricated healthy
    # zero, and these texts say what that absence means.
    "liquiditybot_halted": ("section", _NV_NOT_WRITTEN),
    "liquiditybot_entries_enabled": ("section", _NV_NOT_WRITTEN),
    "liquiditybot_op_state": ("section", _NV_NOT_WRITTEN),
    "liquiditybot_fault_count": ("section", _NV_NOT_WRITTEN),
    "liquiditybot_firewall_fault": ("section", _NV_NOT_WRITTEN),
    # ---- presence-guarded batch 2 (2026-08-17, owed-metrics batch) ------
    # The remaining coerced bools left _ALWAYS_ON the same way: absent
    # key -> no series, never a fabricated flat book / dead feed / model
    # off. positions_open's absence therefore now means EITHER the key
    # was not written OR the exporter is down — the panel desc says so.
    "liquiditybot_positions_open": ("section", _NV_NOT_WRITTEN),
    "liquiditybot_moomoo_": ("section", "moomoo block not in this status write"),
    # liquiditybot_dry_run (guard batch 2, born guarded): absent mode key
    # emits NO series — the tile must NEVER render live from silence, so
    # the text asserts ignorance, not a state.
    "liquiditybot_dry_run": ("section", "mode not in this status write - state unknown"),
    # liquiditybot_ml_loaded_rows rides the load_stats gate like
    # ml_live_clean, but its VALUE is a snapshot of the last corpus load,
    # so the absence text names both honest causes.
    "liquiditybot_ml_loaded_rows":
        ("event", "as of the last retrain's corpus load, or exporter down"),
    # ---- ledger-derived aux batch (gc_pusher.collect_aux, 2026-08-17) ---
    # These ride NO status.json: the guards live in the aux collectors,
    # which emit nothing for an absent/empty/unreadable ledger or a failed
    # cohort_eval run. The longer keys beat the generic liquiditybot_ml_
    # entry by longest-prefix — its "status write" text would be a lie for
    # a ledger series. Paneling one of these REQUIRES the board coverage
    # gates to include collect_aux() on fixture-rebound paths (see the aux
    # section header in scripts/gc_pusher.py and _aux_emitted in
    # tests/test_trading_dashboard.py).
    # gc_pusher.py:_orphan_ratio_metrics — last COMPLETE ledger record
    # only; a record without a ratio emits nothing rather than walking
    # deeper for a stale value
    "liquiditybot_ml_orphan_ratio":
        ("event", "no retrain-ledger ratio yet - or pusher down"),
    # gc_pusher.py:_lineage_metrics — zero parseable registry rows emit
    # nothing (an unreadable ledger must not read as an empty one)
    "liquiditybot_ml_lineage_events":
        ("event", "model registry ledger empty - or pusher down"),
    # gc_pusher.py:_cohort_metrics — a failed refresh DROPS the cache: a
    # count that cannot be re-derived is never re-served
    "liquiditybot_cohort_":
        ("section", "cohort_eval.py gave no count - or pusher down"),
    "liquiditybot_watchdog_": ("section",
                               "watchdog block not in this status write"),
    "liquiditybot_audit_": ("section",
                            "audit counters not in this status write"),
    # gc_pusher.py:528-532 / :1021-1024  per-code tallies
    "liquiditybot_code_count": ("event", "this reason code has not fired"),
    # gc_pusher.py:441-449 / :429-437 / :420-428  performance ledger slices
    "liquiditybot_perf_conviction_":
        ("event", "awaiting first close in this bucket"),
    "liquiditybot_perf_asset_": ("event", "awaiting first close on this asset"),
    "liquiditybot_perf_": ("event", "awaiting first closed trade"),
    # gc_pusher.py:360-409  aggregated from status.positions (non-hedge).
    # Both-cause: a frozen runner stops these series while positions are
    # still genuinely open (measured 2026-08-15, 5 open / 0 series)
    "liquiditybot_position_": ("event",
                               "flat, no open positions - or see Data age"),
    # gc_pusher.py:192-208  graded-evidence ledger, structurally empty
    # before the shadow-grading unlock
    "liquiditybot_thales_rel_": ("event", "no graded THALES evidence yet"),
    "liquiditybot_thales_base_": ("event", "no graded THALES evidence yet"),
    # gc_pusher.py:773-776  labels_by_source
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
    # ---- bare top-level scalars: gc_pusher.py:297-318 numeric whitelist --
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
        "COMMAND — what is the bot doing right now: equity & P&L, the open "
        "book, liveness, exposure by asset, fill mix, and the loss-budget "
        "posture.", _author_command, "command"),
    "liquiditybot_learning.json": _board(
        "liquiditybot-learning", "liquiditybot — learning",
        "LEARNING — is the bot getting smarter, on a 30-day clock: model vs "
        "naive-guess error, label supply & corpus health, outcome mix, "
        "model lineage, and what the learning costs.", _author_learning,
        "learning", time_from="now-30d"),
    "liquiditybot_problem_solution.json": _board(
        "liquiditybot-problem-solution", "liquiditybot — problems",
        "PROBLEMS — what needs attention: posture, the pager conditions as "
        "live numbers, faults & rejections, staleness, the risk brakes, and "
        "the audit trail's own health. Looking empty is good.",
        _author_problem, "diagnostics"),
    "liquiditybot_execution.json": _board(
        "liquiditybot-exec", "liquiditybot — alert inputs",
        "RETIRED signpost (STREAM 7c, 2026-08-28): the alert-input metrics "
        "moved to the Problems board's 'What the pager watches' row. This "
        "page only says where they went — it queries nothing.",
        _author_execution, "execution"),
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
