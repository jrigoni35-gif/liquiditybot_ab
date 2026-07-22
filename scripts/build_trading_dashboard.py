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
(exact values beside every trend; no decoration that isn't data). A
consistent visual language across four focused boards:
  * ACCURACY FIRST: every money panel uses the non-scaling USD unit (see
    below) so the number displayed IS the number the bot holds — no "$5.00K"
    for $4,997.92; the equity curve carries a last/min/max legend table;
  * KPI tiles are stat panels with an AREA SPARKLINE (trend at a glance) and
    threshold color;
  * bounded ratios (exposure, heat, win rate, drawdown) are GAUGES;
  * per-entity comparisons are horizontal gradient BAR GAUGES (one bar per
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
         no_value=None):
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


def state(title, expr, w, h, mapping, desc=""):
    opts = {k: {"text": v[0], "color": v[1], "index": i}
            for i, (k, v) in enumerate(mapping.items())}
    stat(title, expr, w, h, desc=desc, mode="background", text_mode="value",
         graph="none", mappings=[{"type": "value", "options": opts}],
         steps=[{"color": "text", "value": None}])


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
               calcs=None, decimals=None, extra=None):
    """calcs (e.g. ["lastNotNull","min","max"]) upgrades the legend to a
    table with those reductions — exact numbers beside the trend, so the
    curve never has to be eyeballed off the axis (Tufte: show the data)."""
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
    panels.append({
        "id": _id(), "type": "timeseries", "title": title, "description": desc,
        "datasource": DS, "gridPos": {"h": h, "w": w, "x": x, "y": y},
        "fieldConfig": {"defaults": fld, "overrides": []},
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
             legend="{{asset}}", desc="", mn=None, mx=None, no_value=None):
    """Horizontal gradient bars, one per series (asset/pair) — a compact,
    professional ranked comparison."""
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
        "options": {"displayMode": "gradient", "orientation": "horizontal",
                    "showUnfilled": True, "valueMode": "color",
                    "reduceOptions": {"calcs": ["lastNotNull"], "fields": "",
                                      "values": False}},
        "targets": [_t(expr, instant=True, legend=legend)]})


def table(title, w, h, cols, label_keys, sort=None, desc=""):
    """cols: (metric_or_expr, name, unit, decimals[, thresholds]). A 5th
    threshold element renders that column as a gradient-colored heatmap cell."""
    x, y = _place(w, h)
    refs = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    targets, rename, order, overrides = [], {}, {}, []
    for k in label_keys:
        order[k] = len(order)
    for i, col in enumerate(cols):
        metric, name, unit, dec = col[0], col[1], col[2], col[3]
        thr = col[4] if len(col) > 4 else None
        r = refs[i]
        expr = metric if "(" in metric or "{" in metric else f"{metric}{JOB}"
        targets.append(_t(expr, ref=r, fmt="table"))
        rename[f"Value #{r}"] = name
        order[name] = len(order)
        props = [{"id": "unit", "value": unit},
                 {"id": "decimals", "value": dec}]
        if thr:
            props += [
                {"id": "thresholds",
                 "value": {"mode": "absolute", "steps": thr}},
                {"id": "color", "value": {"mode": "thresholds"}},
                {"id": "custom.cellOptions",
                 "value": {"type": "color-background", "mode": "gradient"}}]
        overrides.append({"matcher": {"id": "byName", "options": name},
                          "properties": props})
    panels.append({
        "id": _id(), "type": "table", "title": title, "description": desc,
        "datasource": DS, "gridPos": {"h": h, "w": w, "x": x, "y": y},
        "fieldConfig": {"defaults": {"custom": {
            "align": "auto", "filterable": True, "cellOptions": {"type": "auto"},
            "lineWidth": 1}}, "overrides": overrides},
        "options": {"showHeader": True, "cellHeight": "sm",
                    "footer": {"show": False},
                    "sortBy": [{"displayName": sort or label_keys[0],
                                "desc": bool(sort)}]},
        "targets": targets,
        "transformations": [
            {"id": "merge", "options": {}},
            {"id": "organize", "options": {
                "excludeByName": {"Time": True, "job": True, "instance": True,
                                  "__name__": True},
                "renameByName": rename, "indexByName": order}}]})


def text(title, md, w, h):
    """A markdown info panel — used to document THALES inline on the board."""
    x, y = _place(w, h)
    panels.append({
        "id": _id(), "type": "text", "title": title,
        "gridPos": {"h": h, "w": w, "x": x, "y": y}, "transparent": False,
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

ON_OFF = {"1": ("YES", "green"), "0": ("NO", "red")}
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
    row("💹 Performance")
    stat("Equity", M("liquiditybot_equity"), 5, 5, unit=USD,
         decimals=2, steps=GRN, desc="Account equity (cash + open uPnL).")
    stat("P&L today", M("liquiditybot_daily_pnl"), 4, 5, unit=USD,
         steps=PNL, desc="Realized P&L since UTC midnight.")
    stat("Open uPnL", M("liquiditybot_open_upnl_usd"), 4, 5, unit=USD,
         steps=PNL, desc="Unrealized across open positions.")
    gauge("Drawdown", M("liquiditybot_drawdown_pct"), 4, 5, mx=15.0, steps=DD,
          desc="Peak-to-now; 15% is the hard stop.")
    gauge("Win rate", M("liquiditybot_perf_win_rate", "*100"), 4, 5, mx=100.0,
          steps=WR100, desc="Rolling closed-trade win rate.")
    gauge("Gross exposure", M("liquiditybot_gross_exposure_pct"), 3, 5, mx=35.0,
          desc="Gross notional %/equity vs the 35% heat cap.")
    timeseries("Equity curve", M("liquiditybot_equity"), 16, 7,
               unit=USD, legend="equity", decimals=2,
               calcs=["lastNotNull", "min", "max"],
               desc="Account equity over time — exact dollars (no K-rounding); "
                    "the legend table shows last/min/max to the cent.")
    stat("Profit factor", M("liquiditybot_perf_profit_factor"), 4, 7,
         decimals=2, steps=PF, desc="Gross profit / gross loss.")
    stat("Expectancy R", M("liquiditybot_perf_expectancy_r"), 4, 7, decimals=2,
         steps=PNL, desc="Avg trade in R-multiples.")

    # Health strip sits directly under Performance: the operator's first glance
    # answers "is the bot alive & safe" before "how are the pools doing".
    row("🩺 Health")
    state("Bot", M("liquiditybot_running"), 3, 4, UP_DOWN, desc="runner RUNNING.")
    state("Governor", M("liquiditybot_monitor_level"), 3, 4, GOV,
          desc="0 OK / 1 degraded / 2 killed.")
    state("Entries", M("liquiditybot_entries_enabled"), 3, 4, ON_OFF,
          desc="New-risk entries enabled (exits always allowed).")
    state("Halted", M("liquiditybot_halted"), 3, 4, HALT, desc="Global halt.")
    state("Kraken WS", M("liquiditybot_ws_kraken_connected"), 3, 4, WS,
          desc="Push book vs REST fallback.")
    stat("Feed latency", M("liquiditybot_feed_latency_ms"), 3, 4, unit="ms",
         decimals=0, steps=LAT, desc="Kraken public-GET RTT EWMA.")
    stat("Status age", M("liquiditybot_status_age_sec"), 3, 4, unit="s",
         decimals=0, steps=[{"color": "green", "value": None},
         {"color": "yellow", "value": 120}, {"color": "red", "value": 300}],
         desc="Seconds since last status write.")
    stat("Cycle", M("liquiditybot_cycle"), 3, 4, decimals=0, steps=BLUE,
         desc="Fast-cycle counter (advancing = alive).")

    row("🏦 Profit pools & weekly rollover")
    stat("P&L this week", M("liquiditybot_weekly_pnl"), 5, 5, unit=USD,
         steps=PNL, desc="Realized P&L since the ISO-week open (Mon 00:00 "
                         "UTC). Resets at the weekly close-out (RP-070); a "
                         "losing week is refilled from Reserve before the "
                         "working baseline shrinks.")
    stat("Savings pool", M("liquiditybot_savings"), 5, 5, unit=USD,
         decimals=2, steps=GRN,
         desc="20% of every realized win, locked away - never traded, "
              "never refilled from, only ever grows.")
    stat("Reserve pool", M("liquiditybot_reserve"), 5, 5, unit=USD,
         decimals=2, steps=GRN,
         desc="10% of every realized win - the drawdown shock absorber. "
              "At each weekly close a losing week's realized loss refills "
              "trading cash from here (reserve only ever moves INTO cash).")
    stat("Reinvested (cash)", "liquiditybot_equity" + A +
         " - liquiditybot_savings" + A + " - liquiditybot_reserve" + A, 9, 5,
         unit=USD, decimals=2, steps=GRN,
         desc="Working trading capital: equity minus the two locked pools "
              "- the 70% share that compounds position sizing.")
    timeseries("Pools over time",
               M("liquiditybot_savings"), 16, 7, unit=USD,
               legend="savings", decimals=2,
               calcs=["lastNotNull", "max"],
               extra=[(M("liquiditybot_reserve"), "reserve"),
                      (M("liquiditybot_weekly_pnl"), "weekly P&L")],
               desc="Savings + reserve accrual and the week's running "
                    "realized P&L - the rollover ritual made visible.")

    row("🧠 Learning brain")
    timeseries("Learning rows by label (live vs candidate)",
               'max by (source) (liquiditybot_ml_labels' + JOB + ')', 24, 7,
               unit="short", legend="{{source}}",
               desc="Ground-truth LIVE (real closed-trade) labels vs CANDIDATE "
                    "(triple-barrier proxy) labels accruing over time — the "
                    "learning loop turning. LIVE climbing past 35 = ML-073 "
                    "realizing ground truth; a flat LIVE line = the loop is "
                    "starved. Total training rows = the sum of the two.")
    stat("Live labels", M('liquiditybot_ml_labels{source="live"}'), 4, 5,
         decimals=0, steps=[{"color": "red", "value": None},
         {"color": "yellow", "value": 30}, {"color": "green", "value": 60}],
         desc="Ground-truth closed-trade labels — earns model complexity.")
    stat("Candidate labels", M('liquiditybot_ml_labels{source="candidate"}'),
         4, 5, decimals=0, steps=BLUE, desc="Triple-barrier proxy labels.")
    stat("Model", "count(liquiditybot_ml_model_info" + JOB + ") by (kind)", 4, 5,
         desc="Deployed rung on the simplicity ladder.", text_mode="name",
         steps=BLUE, graph="none")
    state("Model in use", M("liquiditybot_ml_use_model"), 4, 5, ON_OFF,
          desc="Governor lets the model size trades.")
    state("Retrain", M("liquiditybot_ml_retrain_flag"), 4, 5, RETRAIN,
          desc="Auto-retrain queued.")
    stat("Kelly mult", M("liquiditybot_ml_kelly_mult"), 4, 5, decimals=2,
         steps=GRN, desc="Governor size throttle.")
    stat("Brier", M("liquiditybot_ml_brier"), 5, 5, decimals=4, steps=BRIER,
         desc="Rolling outcome Brier (lower better; must beat baseline).")
    stat("Baseline Brier", M("liquiditybot_ml_baseline_brier"), 4, 5,
         decimals=4, steps=GRN, desc="Base-rate bar the model must beat.")
    stat("Calibration gap", M("liquiditybot_ml_calibration_gap"), 4, 5,
         decimals=3, steps=CALIB, desc="ECE; Kelly reads probs literally.")
    stat("Champion Brier", M("liquiditybot_ml_champion_brier"), 4, 5,
         decimals=4, steps=GRN, desc="Deployed champion badge.")
    gauge("Drift share", M("liquiditybot_ml_drift_share", "*100"), 4, 5,
          mx=100.0, steps=[{"color": "green", "value": None},
          {"color": "yellow", "value": 30}, {"color": "red", "value": 50}],
          desc="Fraction of features past the PSI threshold.")
    stat("Win rate LCB", M("liquiditybot_perf_win_rate_lcb", "*100"), 3, 5,
         unit="percent", decimals=1, steps=GRN, desc="Wilson lower bound.")
    # AFML corpus-quality tiles (docs/learning/2026-07-19_weekend_labels.md):
    # is the corpus counting evidence honestly, not just accumulating rows
    stat("Clean live labels", M("liquiditybot_ml_live_clean"), 4, 5,
         decimals=0, steps=[{"color": "red", "value": None},
         {"color": "yellow", "value": 30}, {"color": "green", "value": 60}],
         desc="Live rows surviving the hygiene pass — the count the evidence "
              "gate actually admits model complexity on.")
    stat("Label uniqueness", M("liquiditybot_ml_mean_uniqueness"), 4, 5,
         decimals=3, steps=[{"color": "red", "value": None},
         {"color": "yellow", "value": 0.05}, {"color": "green", "value": 0.15}],
         desc="Mean average-uniqueness (AFML ch.4): 1 = every label an "
              "independent fact; near 0 = heavily overlapping horizons "
              "(weights redistribute so overlap can't double-count).")
    state("Batch prior skew", M("liquiditybot_ml_prior_skew"), 4, 5,
          {"0": ("OK", "green"), "1": ("SKEWED", "yellow")},
          desc="ML-074: trailing-window label prior vs corpus prior — SKEWED "
               "= a one-sided batch (e.g. all-zero quiet weekend) is moving "
               "calibration; detection only, weights untouched.")

    row("⚖️ Per-asset edge")
    bargauge("Net $ by asset", _pa("liquiditybot_perf_asset_net_usd"), 8, 8,
             unit=USD, decimals=2, steps=PNL,
             desc="Realized net per asset — where P&L actually comes from.")
    bargauge("Signal concentration", _pa("liquiditybot_signal_concentration"),
             8, 8, decimals=2, steps=HIGH_GOOD, mn=0, mx=1,
             desc="0 diffuse average .. 1 pinpointed setup.")
    bargauge("Confidence", _pa("liquiditybot_signal_confidence"), 8, 8,
             decimals=2, steps=HIGH_GOOD, mn=0, mx=1,
             desc="Model conviction per asset.")
    table("Asset scorecard", 24, 8,
          cols=[("liquiditybot_perf_asset_win_rate", "Win rate", "percentunit", 2, WRU),
                ("liquiditybot_perf_asset_net_usd", "Net $", USD, 2, PNL),
                ("liquiditybot_perf_asset_trades", "Trades", "short", 0),
                ("liquiditybot_perf_asset_cur_loss_streak", "Loss streak", "short", 0, STREAK),
                ("liquiditybot_signal_confidence", "Confidence", "short", 2, HIGH_GOOD),
                ("liquiditybot_signal_concentration", "Concentration", "short", 2, HIGH_GOOD),
                ("liquiditybot_signal_urgency", "Urgency", "short", 2),
                ("liquiditybot_manip_suspect", "Manip", "short", 2, LOW_GOOD),
                ("liquiditybot_regime_spread_bps", "Spread bps", "short", 1, SPREAD),
                ("liquiditybot_regime_vol_pct", "Vol %", "percent", 1)],
          label_keys=["asset"], sort="Net $",
          desc="One row per asset; color-coded so a green row (positive net, "
               "high concentration, low manip, tight spread) reads instantly.")

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
          desc="Per-asset footprint scores (0-1) + feed-integrity counters. "
               "THALES only ATTENUATES (shade size / down-weight the training "
               "row) — it never triggers a trade.")
    bargauge("Spoof-flicker pressure (bid)",
             _pa("liquiditybot_thales_spoof_bid"), 8, 6, decimals=2,
             steps=LOW_GOOD, mn=0, mx=1, legend="{{asset}}",
             desc="TH-017 spoof EWMA per asset — higher = a book being painted; "
             "THALES shades size there.")
    bargauge("Stop-hunt zone proximity", _pa("liquiditybot_thales_stop_zone"),
             8, 6, decimals=2, steps=LOW_GOOD, mn=0, mx=1, legend="{{asset}}",
             desc="Proximity to round-number stop clusters per asset.")
    bargauge("Manipulation suspicion", _pa("liquiditybot_manip_suspect"),
             8, 6, decimals=2, steps=LOW_GOOD, mn=0, mx=1, legend="{{asset}}",
             desc="Parameter-free max of the manipulation footprints per asset.")

    row("🛡️ Positions & risk")
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


def _positions_table():
    table("Open positions (net per instrument)", 12, 5,
          cols=[("liquiditybot_position_upnl_usd", "uPnL $", USD, 2, PNL),
                ("liquiditybot_position_upnl_pct", "uPnL %", "percent", 2, PNL),
                ("liquiditybot_position_r_multiple", "R", "short", 2, PNL),
                ("liquiditybot_position_notional_usd", "Notional $", USD, 0),
                ("liquiditybot_position_conviction", "p_win", "percentunit", 2, HIGH_GOOD),
                ("liquiditybot_position_stop_dist_pct", "Stop %", "percent", 2),
                ("liquiditybot_position_age_hours", "Age h", "short", 1)],
          label_keys=["symbol", "side"], sort="uPnL $",
          desc="Open instruments; green uPnL/R rows are working, red need "
               "managing.")


# ================= board 2 · models · inventory · execution ================
def _author_execution():
    row("🧠 Decision model")
    stat("Model", "count(liquiditybot_ml_model_info" + JOB + ") by (kind)", 4, 5,
         text_mode="name", steps=BLUE, graph="none",
         desc="Deployed rung (evidence-gated).")
    state("Model in use", M("liquiditybot_ml_use_model"), 3, 5, ON_OFF,
          desc="Model sizes trades vs the cold-start prior.")
    state("Governor", M("liquiditybot_monitor_level"), 3, 5, GOV,
          desc="0 OK / 1 degraded / 2 killed.")
    gauge("Calibration gap", M("liquiditybot_ml_calibration_gap"), 3, 5,
          mx=0.2, decimals=3, steps=CALIB, desc="ECE; keep small — Kelly reads "
          "probs literally.")
    gauge("Drift share", M("liquiditybot_ml_drift_share", "*100"), 3, 5,
          mx=100.0, steps=[{"color": "green", "value": None},
          {"color": "yellow", "value": 30}, {"color": "red", "value": 50}],
          desc="Feature PSI drift fraction.")
    stat("Kelly mult", M("liquiditybot_ml_kelly_mult"), 4, 5, decimals=2,
         steps=GRN, desc="Size throttle.")
    stat("Live labels", M('liquiditybot_ml_labels{source="live"}'), 4, 5,
         decimals=0, steps=[{"color": "red", "value": None},
         {"color": "yellow", "value": 30}, {"color": "green", "value": 60}],
         desc="Ground truth that earns model complexity.")
    stat("Brier", M("liquiditybot_ml_brier"), 6, 5, decimals=4, steps=BRIER,
         desc="Rolling outcome Brier (lower better; must beat baseline).")
    stat("Baseline", M("liquiditybot_ml_baseline_brier"), 6, 5, decimals=4,
         steps=GRN, desc="Bar Brier must beat.")
    stat("Champion Brier", M("liquiditybot_ml_champion_brier"), 4, 5,
         decimals=4, steps=GRN, desc="Deployed champion badge.")
    stat("Shrinkage", M("liquiditybot_ml_shrinkage"), 4, 5, decimals=2,
         steps=GRN, desc="Shrink toward base rate.")
    stat("Stop widen", M("liquiditybot_ml_stop_widen"), 4, 5, decimals=2,
         steps=GRN, desc="Governor stop-distance multiplier.")
    bargauge("Promised vs delivered (hit rate)",
             _pa("liquiditybot_ml_hit_rate", "*100"), 8, 5, unit="percent",
             decimals=1, steps=WR100, legend="hit rate",
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

    row("📦 Inventory & positioning")
    gauge("Gross exposure", M("liquiditybot_gross_exposure_pct"), 5, 5, mx=35.0,
          desc="Gross notional %/equity vs the 35% heat cap.")
    gauge("Portfolio heat", M("liquiditybot_rp_heat_frac", "*100"), 5, 5,
          mx=35.0, desc="CVaR portfolio heat vs cap.")
    stat("Open positions", M("liquiditybot_positions_open"), 3, 5, decimals=0,
         steps=BLUE, desc="Open count (max 5).")
    stat("Open risk", M("liquiditybot_open_risk_usd"), 3, 5, unit=USD,
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

    row("⚡ Execution quality")
    gauge("Maker share", M("liquiditybot_order_maker_share", "*100"), 5, 5,
          mx=100.0, steps=[{"color": "red", "value": None},
          {"color": "yellow", "value": 60}, {"color": "green", "value": 80}],
          no_value="no fills yet",
          desc="% fills that were maker (cheaper).")
    stat("Avg slippage", M("liquiditybot_order_avg_slip_bps"), 4, 5,
         unit="short", decimals=1, steps=SLIP, mode="background", graph="none",
         no_value="no fills yet",
         desc="Implementation shortfall vs the ARRIVAL mark, rolling avg bps (positive = paid worse than arrival; negative = improvement).")
    stat("Worst slippage", M("liquiditybot_order_worst_slip_bps"), 3, 5,
         unit="short", decimals=1, steps=SLIP, mode="background", graph="none",
         no_value="no fills yet",
         desc="Worst single implementation shortfall vs arrival in the window.")
    stat("Venue RTT", M("liquiditybot_order_latency_ms"), 4, 5, unit="ms",
         decimals=0, steps=LAT, desc="Private POST RTT (order path).")
    stat("Venue rejects", M("liquiditybot_order_venue_rejects"), 4, 5,
         decimals=0, steps=STREAK, graph="none", mode="background",
         desc="OM-021 AddOrder rejects.")
    stat("Dead-man failures", M("liquiditybot_order_deadman_failures"), 4, 5,
         decimals=0, steps=ZERO_BAD, graph="none", mode="background",
         desc="OM-050 refresh failures — resting orders unguarded.")
    stat("Maker fills", M("liquiditybot_order_maker_fills"), 3, 4, decimals=0,
         steps=GRN, desc="Maker fills in window.")
    stat("Taker fills", M("liquiditybot_order_taker_fills"), 3, 4, decimals=0,
         steps=GRN, desc="Taker fills (exit-ladder rung).")
    stat("Maker notional", M("liquiditybot_order_maker_notional_usd"), 4, 4,
         unit=USD, decimals=0, steps=GRN, desc="Maker-filled notional.")
    stat("Taker notional", M("liquiditybot_order_taker_notional_usd"), 4, 4,
         unit=USD, decimals=0, steps=GRN, desc="Taker-filled notional.")
    table("Post-fill mark-out (adverse selection)", 12, 6,
          cols=[("liquiditybot_markout_bps", "Mark-out bps", "short", 2, PNL)],
          label_keys=["asset", "horizon_sec"], sort="Mark-out bps",
          desc="Price drift after our fill; persistently negative = picked off.")
    bargauge("Slippage by fill quality — avg vs worst (bps)",
             M("liquiditybot_order_avg_slip_bps"), 12, 6, unit="short",
             decimals=1, steps=SLIP, legend="avg slip",
             no_value="no fills yet",
             desc="Implementation shortfall vs arrival, rolling avg bps (negative = price improvement).")


# ==================== board 3 · problem / solution =========================
def _author_problem():
    text("", "**Incident board — a calm board is all green.** Every tile is a "
             "PROBLEM paired with the SOLUTION that fires automatically; any "
             "non-zero / amber / red tile is a live incident worth a look. "
             "Refresh 30s · window 24h.", 24, 3)
    row("📡 Feed & data integrity")
    stat("Stale status", M("liquiditybot_status_age_sec"), 4, 5, unit="s",
         decimals=0, mode="background", graph="none",
         steps=[{"color": "green", "value": None}, {"color": "yellow", "value": 120},
                {"color": "red", "value": 300}],
         desc="PROBLEM: runner frozen. SOLUTION: wedge-guard escalates; "
              "supervisor revives a dead runner.")
    state("Kraken WS", M("liquiditybot_ws_kraken_connected"), 4, 5, WS,
          desc="SOLUTION: on drop the engine falls back to REST — trading continues.")
    stat("Stale marks", M("liquiditybot_marks_age_sec"), 4, 5, unit="s",
         decimals=0, mode="background", graph="none",
         steps=[{"color": "green", "value": None}, {"color": "yellow", "value": 30},
                {"color": "red", "value": 90}],
         desc="PROBLEM: old prices. SOLUTION: mark-freshness gate holds "
              "non-escape risk; stops still run.")
    stat("Stale assets held", M("liquiditybot_watchdog_stale_assets"), 4, 5,
         decimals=0, mode="background", graph="none", steps=ZERO_BAD,
         desc="Watchdog quarantined assets — entries blocked until feed heals.")
    stat("Entries blocked", M("liquiditybot_watchdog_entries_blocked"), 4, 5,
         decimals=0, mode="background", graph="none", steps=ZERO_BAD,
         desc="Feed watchdog blocking new entries (a solution firing).")
    stat("Divergent feeds", M("liquiditybot_watchdog_divergent"), 4, 5,
         decimals=0, mode="background", graph="none", steps=ZERO_BAD,
         desc="Cross-venue book divergence count.")

    row("🧠 Model health")
    stat("PROBLEM: model Brier", M("liquiditybot_ml_brier"), 4, 6, decimals=4,
         mode="background", graph="none", steps=BRIER,
         desc="Detector. SOLUTION: the governor kills the model + queues a "
              "retrain when Brier crosses baseline.")
    stat("vs baseline", M("liquiditybot_ml_baseline_brier"), 4, 6, decimals=4,
         steps=GRN, graph="none", desc="The bar Brier must stay under.")
    state("SOLUTION: governor", M("liquiditybot_monitor_level"), 4, 6, GOV,
          desc="0 OK / 1 shrink+throttle / 2 model killed to the prior.")
    state("SOLUTION: retrain", M("liquiditybot_ml_retrain_flag"), 4, 6, RETRAIN,
          desc="Auto-retrain queued to replace a degrading champion.")
    gauge("Drift share", M("liquiditybot_ml_drift_share", "*100"), 4, 6,
          mx=100.0, steps=[{"color": "green", "value": None},
          {"color": "yellow", "value": 30}, {"color": "red", "value": 50}],
          desc="PROBLEM: input drift. SOLUTION: retrain re-fits.")
    stat("Kelly throttle", M("liquiditybot_ml_kelly_mult"), 4, 6, decimals=2,
         steps=GRN, graph="none", desc="Size shrinks as confidence falls.")
    stat("Model fallbacks", M("liquiditybot_ml_model_fallbacks"), 4, 4,
         decimals=0, mode="background", graph="none", steps=STREAK,
         desc="Inference fell to the prior (fail-safe firing).")
    stat("Infer faults", M("liquiditybot_ml_infer_faults"), 4, 4, decimals=0,
         mode="background", graph="none", steps=STREAK, desc="Inference errors.")
    stat("Contract fails", M("liquiditybot_ml_contract_failed"), 4, 4,
         decimals=0, mode="background", graph="none", steps=STREAK,
         desc="Input outside contract.")
    stat("Retrain failures", M("liquiditybot_ml_retrain_failures"), 4, 4,
         decimals=0, mode="background", graph="none", steps=STREAK,
         desc="Auto-retrain crashed.")
    stat("Calibration gap", M("liquiditybot_ml_calibration_gap"), 4, 4,
         decimals=3, mode="background", graph="none", steps=CALIB,
         desc="Miscalibration; ECE.")
    stat("Dirty rows dropped", M("liquiditybot_ml_dropped_dirty"), 4, 4,
         decimals=0, mode="background", graph="none",
         steps=[{"color": "green", "value": None},
                {"color": "yellow", "value": 1}, {"color": "red", "value": 10}],
         desc="PROBLEM: legacy/imported non-finite rows. SOLUTION: the "
              "ML-015 load backstop drops them before they NaN a fit "
              "(0 = corpus clean by construction).")
    stat("Twin rows excluded", M("liquiditybot_ml_dropped_clash"), 4, 4,
         decimals=0, graph="none", steps=BLUE,
         desc="Synthetic candidate twins of REAL trades excluded so a taken "
              "signal is never double-counted (realized label kept). "
              "Nonzero is healthy — it tracks taken teach-trades.")

    row("💰 Capital & drawdown")
    gauge("PROBLEM: drawdown", M("liquiditybot_drawdown_pct"), 5, 6, mx=15.0,
          steps=DD, desc="SOLUTION: drawdown throttle + 15% hard-stop flatten.")
    stat("Loss streak", M("liquiditybot_perf_cur_loss_streak"), 4, 6,
         decimals=0, mode="background", graph="none", steps=STREAK,
         desc="PROBLEM: consecutive losers. SOLUTION: per-asset circuit breaker.")
    stat("Breakers tripped", M("liquiditybot_cb_tripped_count"), 3, 6,
         decimals=0, mode="background", graph="none", steps=ZERO_BAD,
         desc="Assets currently paused.")
    gauge("Heat vs cap", M("liquiditybot_rp_heat_frac", "*100"), 4, 6, mx=35.0,
          desc="SOLUTION: heat throttled under the CVaR cap.")
    stat("Taper mult", M("liquiditybot_rp_taper_mult"), 4, 6, decimals=2,
         steps=GRN, desc="SOLUTION: loss-budget taper shrinks size.")
    gauge("Daily budget used", M("liquiditybot_rp_daily_budget_used_frac", "*100"),
          6, 5, mx=100.0, steps=BUDGET, desc="Daily loss budget consumed.")
    gauge("Weekly budget used", M("liquiditybot_rp_weekly_budget_used_frac", "*100"),
          6, 5, mx=100.0, steps=BUDGET, desc="Weekly loss budget consumed.")
    table("Circuit breaker — paused assets", 12, 5,
          cols=[("liquiditybot_cb_loss_streak", "Loss streak", "short", 0, STREAK),
                ("liquiditybot_cb_paused_hours_left", "Hours left", "short", 1, BLUE)],
          label_keys=["asset"], sort="Loss streak",
          desc="Per-asset breaker state; hours-left counts the cool-off.")

    row("🕵️ Manipulation, venue & integrity")
    state("op-state", M("liquiditybot_op_state"), 4, 5, OPSTATE,
          desc="Central fault authority: ARMED / DEGRADED / HALTED.")
    stat("Latched faults", M("liquiditybot_fault_count"), 4, 5, decimals=0,
         mode="background", graph="none", steps=ZERO_BAD, desc="Active latched faults.")
    state("Firewall fault", M("liquiditybot_firewall_fault"), 4, 5, HALT,
          desc="Risk-firewall latched fault (blocks new risk).")
    stat("Cycle wedge", M("liquiditybot_cycle_consecutive_failures"), 4, 5,
         decimals=0, mode="background", graph="none", steps=STREAK,
         desc="PROBLEM: failing cycles. SOLUTION: runner wedge escalation.")
    stat("Exit-eval failures", M("liquiditybot_exit_eval_failures"), 4, 5,
         decimals=0, mode="background", graph="none", steps=ZERO_BAD,
         desc="A position wedging its own exit path.")
    stat("Venue rejects", M("liquiditybot_order_venue_rejects"), 4, 5,
         decimals=0, mode="background", graph="none", steps=STREAK,
         desc="OM-021 AddOrder rejects.")
    bargauge("Manipulation suspicion by asset",
             _pa("liquiditybot_manip_suspect"), 12, 6, decimals=2, steps=LOW_GOOD,
             mn=0, mx=1, desc="PROBLEM: painted/spoofed books. SOLUTION: THALES "
             "shades size + down-weights those training rows.")
    table("Firewall clamps/rejects by code", 12, 6,
          cols=[("liquiditybot_firewall_count", "Count", "short", 0, STREAK)],
          label_keys=["code"], sort="Count",
          desc="Which firewall rule (FW-*) is clamping most.")


# ==================== board 4 · asset screening ============================
def _author_screening():
    row("🔎 Skimmer — candidate universe")
    stat("Candidates scanned", M("liquiditybot_skimmer_candidates"), 5, 5,
         decimals=0, steps=BLUE, desc="Off-universe pairs ranked.")
    stat("Promoted", M("liquiditybot_skimmer_promoted_count"), 5, 5, decimals=0,
         steps=GRN, desc="Pairs promoted into the tradeable set.")
    stat("Open slots", M("liquiditybot_positions_open"), 4, 5, decimals=0,
         steps=BLUE, desc="Slots in use (max 5).")
    gauge("Exposure headroom", M("liquiditybot_gross_exposure_pct"), 5, 5,
          mx=35.0, desc="Room left under the heat cap for a new name.")
    stat("Model in use", M("liquiditybot_ml_use_model"), 5, 5, decimals=0,
         mappings=[{"type": "value", "options": {
             "1": {"text": "YES", "color": "green", "index": 0},
             "0": {"text": "prior", "color": "yellow", "index": 1}}}],
         mode="background", graph="none", desc="Is the model sizing yet.")
    bargauge("Skimmer score (higher = better book)",
             _pa("liquiditybot_skimmer_score"), 12, 8, decimals=3, steps=HIGH_GOOD,
             legend="{{pair}}", desc="Composite liquidity/spread/depth score "
             "per candidate pair.")
    table("Promoted pairs", 12, 8,
          cols=[("liquiditybot_skimmer_promoted_info", "Promoted", "short", 0, GRN)],
          label_keys=["pair"], sort="Promoted",
          desc="Pairs currently promoted into the tradeable universe.")

    row("📋 Tradeability scorecard")
    table("Screen — book & regime vs signal & result", 24, 9,
          cols=[("liquiditybot_regime_spread_bps", "Spread bps", "short", 1, SPREAD),
                ("liquiditybot_regime_vol_pct", "Vol %", "percent", 1),
                ("liquiditybot_regime_spoof", "Spoof", "short", 2, LOW_GOOD),
                ("liquiditybot_manip_suspect", "Manip", "short", 2, LOW_GOOD),
                ("liquiditybot_signal_confidence", "Confidence", "short", 2, HIGH_GOOD),
                ("liquiditybot_signal_concentration", "Concentration", "short", 2, HIGH_GOOD),
                ("liquiditybot_signal_urgency", "Urgency", "short", 2),
                ("liquiditybot_perf_asset_win_rate", "Win rate", "percentunit", 2, WRU),
                ("liquiditybot_perf_asset_net_usd", "Net $", USD, 2, PNL),
                ("liquiditybot_perf_asset_trades", "Trades", "short", 0)],
          label_keys=["asset"], sort="Net $",
          desc="Screen an asset in one row: tight spread + low spoof/manip + "
               "high concentration + positive net = a tradeable edge; the "
               "color coding makes a good book jump out.")

    row("🌡️ Regime context & adverse selection")
    bargauge("Spread by asset (bps, lower = tighter book)",
             _pa("liquiditybot_regime_spread_bps"), 8, 7, decimals=1, steps=SPREAD,
             desc="Cost of crossing; the screen's first filter.")
    bargauge("Volatility by asset (%)", _pa("liquiditybot_regime_vol_pct"), 8, 7,
             unit="percent", decimals=1, steps=BLUE,
             desc="Realized vol regime per asset.")
    table("Adverse selection (mark-out)", 8, 7,
          cols=[("liquiditybot_markout_bps", "Mark-out bps", "short", 2, PNL)],
          label_keys=["asset", "horizon_sec"], sort="Mark-out bps",
          desc="Post-fill drift; persistently negative = the book picks us "
               "off — screen it down.")


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


def _board(uid, title, desc, author, extra_tag):
    panels.clear()
    _cur.update(x=0, y=0, row_h=0)
    _pid["n"] = 0
    author()
    return {"uid": uid, "title": title, "description": desc,
            "tags": _TAGS + [extra_tag], "schemaVersion": 39, "editable": True,
            "timezone": "browser", "refresh": "30s", "style": "dark",
            "time": {"from": "now-24h", "to": "now"}, "links": _links(),
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
