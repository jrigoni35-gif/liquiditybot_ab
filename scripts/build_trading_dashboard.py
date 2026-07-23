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
from pathlib import Path

DS = {"type": "prometheus", "uid": "grafanacloud-prom"}
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
CAT_TEAL = "#2596AB"
CAT_PURPLE = "#BF5AF2"

INJ_ID = 990          # fixed id on every board so the CSS can self-hide

# Frosted-glass skin, ACTIVE since 2026-07-23: the operator installed the
# signed Business Text plugin (Admin-only step), so the injector tile is a
# marcusolsson-dynamictext-panel whose afterRender hook appends these rules
# to document.head — the route Grafana Cloud's <style> sanitizer (which kept
# the old native-text tile dormant) does not touch. README_glass.md.
GLASS_RULES = """\
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


def row(title):
    _flush()
    panels.append({"id": _id(), "type": "row", "title": title,
                   "collapsed": False,
                   "gridPos": {"h": 1, "w": 24, "x": 0, "y": _cur["y"]},
                   "panels": []})
    _cur["y"] += 1
    _cur["x"] = 0
    _cur["row_h"] = 0


def stat(title, expr, w, h, unit="", decimals=2, desc="", steps=None,
         mode="value", mappings=None, text_mode="auto", graph="area",
         no_value=None, display_name=None):
    """KPI tile. graph='area' draws a sparkline behind the number (the default,
    for the professional look); graph='none' for pure state/count tiles.
    no_value: honest empty-state text for event-sparse series (fills,
    positions) whose ABSENCE is truthful - 'No data' reads as broken
    telemetry, the text says what absence means."""
    x, y = _place(w, h)
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
                    "reduceOptions": {"calcs": ["lastNotNull"], "fields": "",
                                      "values": False}},
        "targets": [_t(expr, instant=(graph == "none"), legend="")]})


def state(title, expr, w, h, mapping, desc="", no_value=None):
    opts = {k: {"text": v[0], "color": v[1], "index": i}
            for i, (k, v) in enumerate(mapping.items())}
    stat(title, expr, w, h, desc=desc, mode="background", text_mode="value",
         graph="none", mappings=[{"type": "value", "options": opts}],
         steps=[{"color": "text", "value": None}], no_value=no_value)


def gauge(title, expr, w, h, mx=35.0, unit="percent", decimals=1, steps=None,
          desc="", no_value=None):
    x, y = _place(w, h)
    fld = {"unit": unit, "min": 0, "max": mx,
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

ON_OFF = {"1": ("YES", "green"), "0": ("NO", "#8E8E93")}
UP_DOWN = {"1": ("RUNNING", "green"), "0": ("STOPPED", "red")}
WS = {"1": ("LIVE", "green"), "0": ("REST", "yellow")}
HALT = {"1": ("HALTED", "red"), "0": ("clear", "green")}
GOV = {"0": ("OK", "green"), "1": ("DEGRADED", "yellow"), "2": ("KILLED", "red")}
OPSTATE = {"0": ("ARMED", "green"), "1": ("DEGRADED", "yellow"),
           "2": ("HALTED", "red"), "-1": ("UNKNOWN", "red")}
RETRAIN = {"1": ("QUEUED", "yellow"), "0": ("idle", "green")}

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


# ========================= board 1 · command ===============================
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
         decimals=3, steps=CALIB, no_value="not scoring — model shadowed",
         desc="ECE; Kelly reads probs literally.")
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
          cols=[("liquiditybot_gate_weight", "Weight", "short", 3, HIGH_GOOD, "text")],
          label_keys=["gate"], sort="Weight", desc="Evidence weight per gate.")
    gauge("Gross exposure", M("liquiditybot_gross_exposure_pct"), 6, 5,
          mx=35.0, desc="Gross notional %/equity vs the 35% heat cap.")
    stat("Positions open", M("liquiditybot_positions_open"), 6, 5, decimals=0,
         steps=BLUE, graph="none", desc="Open count (max 5).")


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
          mx=0.2, decimals=3, steps=CALIB,
          no_value="not scoring — model shadowed",
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

    row("🧠 MODEL HEALTH")
    stat("PROBLEM: model Brier", M("liquiditybot_ml_brier"), 4, 5, decimals=4,
         mode="background", graph="none", steps=BRIER,
         no_value="not scoring — model shadowed",
         desc="Detector. SOLUTION: the governor kills the model + queues a "
              "retrain when Brier crosses baseline.")
    stat("vs baseline", M("liquiditybot_ml_baseline_brier"), 4, 5, decimals=4,
         steps=GRN, graph="none",
         no_value="not scoring — model shadowed",
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
         no_value="not scoring — model shadowed",
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


# ==================== board 4 · asset screening ============================
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
_PULSE_CONTENT = """\
<style>
.pulse-wrap{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,\
system-ui,sans-serif;color:#F5F5F7;max-width:26rem;margin:0 auto;\
box-sizing:border-box;min-height:100%;display:flex;flex-direction:column;\
justify-content:center;\
padding:2.6rem 1.25rem 1.4rem;text-align:center;-webkit-font-smoothing:antialiased;}
.pulse-state{display:flex;align-items:center;justify-content:center;\
flex-wrap:wrap;gap:.5em;font-size:11px;font-weight:600;text-transform:uppercase;\
letter-spacing:.14em;color:#86868B;font-variant-numeric:tabular-nums;\
margin-bottom:2.1rem;}
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
.pulse-spark{margin:1.7rem 0 1.9rem;line-height:0;}
.pulse-spark svg{display:block;width:100%;height:42px;overflow:visible;}
.pulse-nohist{line-height:1.4;font-size:11px;color:#6E6E73;text-transform:uppercase;\
letter-spacing:.08em;padding:.9rem 0;}
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
.pulse-foot{margin-top:1.9rem;font-size:11px;color:#6E6E73;\
text-transform:uppercase;letter-spacing:.1em;}
</style>
<div class="pulse-wrap">
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
{{#if data.[15].[0].Value}}{{toFixed data.[15].[0].Value 0}},\
{{#with (split (toFixed data.[16].[0].Value 0) "") as |d|}}\
{{lookup d 1}}{{lookup d 2}}{{lookup d 3}}{{/with}}\
{{else}}{{lookup (split (toFixed data.[3].[0].Value 2) ".") 0}}{{/if}}\
<span class="pulse-cents">.{{lookup (split (toFixed data.[3].[0].Value 2) ".") 1}}\
</span>{{else}}--{{/if}}</div>
<div class="pulse-pnl">{{#with data.[4].[0]}}\
{{#if (eq (toFixed Value 2) "0.00")}}<span class="flat">$0.00 today</span>\
{{else}}{{#if (eq (toFixed Value 2) "-0.00")}}<span class="flat">$0.00 today</span>\
{{else}}{{#if (startsWith (toFixed Value 2) "-")}}\
<span class="loss">-${{#if data.[17].[0].Value}}{{toFixed data.[17].[0].Value 0}},\
{{#with (split (toFixed data.[18].[0].Value 0) "") as |d|}}\
{{lookup d 1}}{{lookup d 2}}{{lookup d 3}}{{/with}}\
{{else}}{{lookup (split (lookup (split (toFixed Value 2) "-") 1) ".") 0}}{{/if}}\
.{{lookup (split (toFixed Value 2) ".") 1}} today</span>\
{{else}}<span class="gain">+${{#if data.[17].[0].Value}}{{toFixed data.[17].[0].Value 0}},\
{{#with (split (toFixed data.[18].[0].Value 0) "") as |d|}}\
{{lookup d 1}}{{lookup d 2}}{{lookup d 3}}{{/with}}\
{{else}}{{lookup (split (toFixed Value 2) ".") 0}}{{/if}}\
.{{lookup (split (toFixed Value 2) ".") 1}} today</span>{{/if}}{{/if}}{{/if}}\
{{else}}<span class="flat">-- today</span>{{/with}}\
{{#with data.[5].[0]}}<span class="wk">\
{{#if (eq (toFixed Value 2) "0.00")}}$0.00 this week\
{{else}}{{#if (eq (toFixed Value 2) "-0.00")}}$0.00 this week\
{{else}}{{#if (startsWith (toFixed Value 2) "-")}}-${{#if data.[19].[0].Value}}\
{{toFixed data.[19].[0].Value 0}},{{#with (split (toFixed data.[20].[0].Value 0) "") as |d|}}\
{{lookup d 1}}{{lookup d 2}}{{lookup d 3}}{{/with}}\
{{else}}{{lookup (split (lookup (split (toFixed Value 2) "-") 1) ".") 0}}{{/if}}\
.{{lookup (split (toFixed Value 2) ".") 1}} this week\
{{else}}+${{#if data.[19].[0].Value}}{{toFixed data.[19].[0].Value 0}},\
{{#with (split (toFixed data.[20].[0].Value 0) "") as |d|}}\
{{lookup d 1}}{{lookup d 2}}{{lookup d 3}}{{/with}}\
{{else}}{{lookup (split (toFixed Value 2) ".") 0}}{{/if}}\
.{{lookup (split (toFixed Value 2) ".") 1}} this week{{/if}}{{/if}}{{/if}}\
</span>{{else}}<span class="wk">-- this week</span>{{/with}}</div>
<div class="pulse-spark">{{#if data.[12].[0]}}\
<svg viewBox="0 {{data.[13].[0].Value}} 575 {{data.[14].[0].Value}}" \
preserveAspectRatio="none"><polyline fill="none" stroke="#86868B" \
stroke-width="1.4" stroke-linejoin="round" stroke-linecap="round" \
vector-effect="non-scaling-stroke" points="\
{{#each data.[12]}}{{@index}},{{Value}} {{/each}}"/>\
{{#each data.[12]}}{{#if @last}}<line x1="{{@index}}" y1="{{Value}}" \
x2="{{@index}}" y2="{{Value}}" stroke="#F5F5F7" stroke-width="4.5" \
stroke-linecap="round" vector-effect="non-scaling-stroke"/>{{/if}}{{/each}}\
</svg>{{else}}<div class="pulse-nohist">no equity history yet</div>{{/if}}</div>
<div class="pulse-rows">
<div class="pulse-row"><span class="lab">Time-stop scratches\
<span class="exp">Trades the max-hold clock closed flat &mdash; patience, \
not conviction</span></span>\
<span class="val">{{#with data.[6].[0]}}{{toFixed Value 0}}{{else}}--{{/with}}\
</span></div>
<div class="pulse-row"><span class="lab">Probes held back\
<span class="exp">Entries the sizer judged too small to be worth the risk\
</span></span>\
<span class="val">{{#with data.[7].[0]}}{{toFixed Value 0}}{{else}}--{{/with}}\
</span></div>
<div class="pulse-row"><span class="lab">Learning corpus\
<span class="exp">Labelled trades feeding the model</span></span>\
<span class="val">{{#with data.[8].[0]}}{{toFixed Value 0}}{{else}}--{{/with}}\
<span class="sub">{{#with data.[9].[0]}}{{toFixed Value 0}} live\
{{else}}-- live{{/with}}</span></span></div>
<div class="pulse-row"><span class="lab">Model\
<span class="exp">Whether the model is sizing trades or standing aside\
</span></span>\
<span class="val">{{#if data.[10].[0]}}\
{{#if (eq data.[10].[0].Value 2)}}watching\
{{else}}{{#if data.[11].[0].Value}}driving{{else}}standing by{{/if}}{{/if}}\
{{else}}--{{/if}}</span></div>
</div>
<div class="pulse-foot">Live &middot; refreshes with the bot's telemetry</div>
</div>"""

_PULSE_DEFAULT = ('<div class="pulse-wrap"><div class="pulse-foot">'
                  'waiting for telemetry&hellip;</div></div>')


def _author_pulse():
    """The single full-width Business Text tile — no row header, the tile IS
    the screen (the shared nav already names it). refId order below == the
    `data.[i]` frame index the template reads."""
    x, y = _place(24, 28)
    inst = [
        ("A", 'max(liquiditybot_running{job="liquiditybot"})'),
        ("B", 'max(liquiditybot_status_age_sec{job="liquiditybot"})'),
        ("C", 'max(liquiditybot_status_stale{job="liquiditybot"})'),
        ("D", 'max(liquiditybot_equity{job="liquiditybot"})'),
        ("E", 'max(liquiditybot_daily_pnl{job="liquiditybot"})'),
        ("F", 'max(liquiditybot_weekly_pnl{job="liquiditybot"})'),
        ("G", 'max(liquiditybot_code_count_detail'
              '{job="liquiditybot",code="PT-060"})'),
        ("H", 'max(liquiditybot_code_count_detail'
              '{job="liquiditybot",code="SZ-047"})'),
        ("I", 'sum(liquiditybot_ml_labels{job="liquiditybot"})'),
        ("J", 'max(liquiditybot_ml_labels{job="liquiditybot",source="live"})'),
        ("K", 'max(liquiditybot_monitor_level{job="liquiditybot"})'),
        ("L", 'max(liquiditybot_ml_use_model{job="liquiditybot"})'),
    ]
    targets = [_t(e, ref=r, instant=True) for r, e in inst]
    # M: 48h equity sparkline series (NEGATED so up = higher equity). maxData
    # Points 576 => ~5m step over the board's default now-48h range, and x =
    # {{@index}} 0..575 fills the fixed 575-wide viewBox.
    # NOTE (design M4, left by design): on a cold start (<48h history) the
    # polyline occupies only the left fraction of the 575-wide box. Both
    # reviewer-suggested fixes are infeasible under the plugin's constraints:
    # per-point x-scaling needs a math helper (none ships), and pinning the
    # viewBox width to the point count needs an array-length helper (none) or
    # a PromQL point-count — but the range step is Grafana-adaptive (the
    # keepTime nav can carry a non-48h range here), so any fixed-window count
    # (count_over_time / subquery) would MIS-scale the axis at steady state,
    # i.e. worse than the honest cosmetic compression. Kept as-is.
    tM = _t('0 - max(liquiditybot_equity{job="liquiditybot"})', ref="M",
            instant=False)
    tM["maxDataPoints"] = 576
    targets.append(tM)
    # N/O: viewBox y-origin (-max) and height (max-min, clamped>0) — the pure-
    # PromQL bounds the sparkline normalizes against (no template math).
    targets.append(_t(
        '0 - max_over_time(liquiditybot_equity{job="liquiditybot"}[48h])',
        ref="N", instant=True))
    targets.append(_t(
        'clamp_min(max_over_time(liquiditybot_equity{job="liquiditybot"}[48h])'
        ' - min_over_time(liquiditybot_equity{job="liquiditybot"}[48h]), '
        '0.01)', ref="O", instant=True))
    # P/Q: thousands-separator for the equity hero (design C1). The plugin
    # ships no math helpers, so grouping is arithmetic in PromQL: P = whole
    # thousands (its Handlebars truthiness gates the comma; 0 => no group), and
    # Q = 1000 + (integer % 1000) so `toFixed`->`split ""` yields the ZERO-
    # PADDED low three digits at char positions 1..3 (covers up to 6 figures).
    targets.append(_t(
        'floor(max(liquiditybot_equity{job="liquiditybot"}) / 1000)',
        ref="P", instant=True))
    targets.append(_t(
        '1000 + (floor(max(liquiditybot_equity{job="liquiditybot"})) % 1000)',
        ref="Q", instant=True))
    # R/S (daily) + T/U (weekly): the SAME thousands-grouping companions for
    # the P&L strings (design C1 — grouping applies everywhere money renders,
    # not just the hero). abs() strips the sign (rendered in-template via
    # startsWith), so R/T = whole thousands (truthiness gates the comma) and
    # S/U = 1000 + (|pnl| % 1000) => the zero-padded low three digits.
    targets.append(_t(
        'floor(abs(max(liquiditybot_daily_pnl{job="liquiditybot"})) / 1000)',
        ref="R", instant=True))
    targets.append(_t(
        '1000 + (floor(abs(max(liquiditybot_daily_pnl{job="liquiditybot"}))) '
        '% 1000)', ref="S", instant=True))
    targets.append(_t(
        'floor(abs(max(liquiditybot_weekly_pnl{job="liquiditybot"})) / 1000)',
        ref="T", instant=True))
    targets.append(_t(
        '1000 + (floor(abs(max(liquiditybot_weekly_pnl{job="liquiditybot"}))) '
        '% 1000)', ref="U", instant=True))
    panels.append({
        "id": _id(), "type": "marcusolsson-dynamictext-panel",
        "title": "", "description": "Live single-screen truth.",
        "datasource": DS, "gridPos": {"h": 28, "w": 24, "x": x, "y": y},
        "fieldConfig": {"defaults": {}, "overrides": []},
        "options": {"renderMode": "data", "content": _PULSE_CONTENT,
                    "defaultContent": _PULSE_DEFAULT, "editors": [],
                    "helpers": "", "afterRender": "", "styles": "",
                    "wrap": False, "externalStyles": [], "contentPartials": []},
        "targets": targets, "pluginVersion": "6.3.0"})


# ============================ assemble =====================================
_TAGS = ["liquiditybot", "trading", "paper-trading"]
_NAV = [("⌘ Command", "liquiditybot-trading"),
        ("⚙ Models·Inv·Exec", "liquiditybot-exec"),
        ("🩹 Problem/Solution", "liquiditybot-problem-solution"),
        ("🔎 Screening", "liquiditybot-screening"),
        ("🧭 Pulse", "liquiditybot-pulse")]


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


def _board(uid, title, desc, author, extra_tag, time_from="now-24h"):
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
            "time": {"from": time_from, "to": "now"}, "links": _links(),
            "templating": {"list": []}, "annotations": {"list": []},
            "panels": list(panels)}


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


DASHBOARDS = {
    "liquiditybot_command.json": _board(
        "liquiditybot-trading", "liquiditybot — command",
        "Daily driver: performance, health, learning brain, per-asset edge, "
        "positions & risk.", _author_command, "command"),
    "liquiditybot_execution.json": _board(
        "liquiditybot-exec", "liquiditybot — models · inventory · execution",
        "Decision-model health, inventory/positioning & heat, and execution "
        "fill quality (maker/taker, slippage, mark-out).", _author_execution,
        "execution"),
    "liquiditybot_problem_solution.json": _board(
        "liquiditybot-problem-solution", "liquiditybot — problem / solution",
        "Every failure mode as a PROBLEM whose panel shows the live detector "
        "and names the SOLUTION mechanism handling it.", _author_problem,
        "diagnostics"),
    "liquiditybot_screening.json": _board(
        "liquiditybot-screening", "liquiditybot — asset screening",
        "Asset screening: skimmer ranks + a per-asset tradeability scorecard "
        "(book, regime, signal quality, result).", _author_screening,
        "screening"),
    "liquiditybot_pulse.json": _board(
        "liquiditybot-pulse", "Pulse",
        "One screen, one truth: live equity, P&L, a 48h sparkline and the "
        "few numbers that say whether the bot is healthy — a single Business "
        "Text panel.", _author_pulse, "pulse", time_from="now-48h"),
}
for _d in DASHBOARDS.values():
    _apple_palette(_d)
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
