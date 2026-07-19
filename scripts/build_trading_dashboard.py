"""scripts/build_trading_dashboard.py — generator for the ONE condensed
logistical command dashboard (docs/grafana/liquiditybot_command.json).

THIS GENERATOR IS THE SOURCE OF TRUTH: edit here and regenerate; never
hand-edit the JSON. tests/test_trading_dashboard.py enforces (1) generator ==
shipped JSON, (2) importable shape / no overlapping panels, (3) every metric
a panel queries is actually emitted by scripts/gc_pusher.py.

DESIGN — a LOGISTICAL framework, not a wall of graphs. Everything is a
state/number/table you read at a glance, organized for DECISIONS:

  §1 Command & Health   at-a-glance state readouts (UP/DOWN, ARMED, KILLED)
                        + the load-bearing numbers (equity, drawdown, latency)
  §2 Learning brain     ground-truth vs proxy labels, model health, calibration
  §3 Positions          net-per-instrument table (uPnL, R, stop distance, age)
  §4 Per-asset compare  ONE row per asset — win rate, net, signal quality,
                        concentration, regime — the side-by-side that answers
                        "where is the edge accumulating, what do I capitalize on"
  §5 Risk & incidents   exposure, governor throttles, entry-reason codes, faults

Single board, uid 'liquiditybot-trading' — re-import REPLACES the old desk
board in place. The four graph-heavy partitions and the old monolith are
retired (deleted from docs/grafana/).
"""
import json
from pathlib import Path

DS = {"type": "prometheus", "uid": "grafanacloud-prom"}
JOB = '{job="liquiditybot"}'
panels = []

# ---- auto-layout cursor: no hand-computed gridPos, so no overlaps ----------
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
    if _cur["x"] + w > 24:                    # wrap to next line
        _cur["y"] += _cur["row_h"]
        _cur["x"] = 0
        _cur["row_h"] = 0
    x, y = _cur["x"], _cur["y"]
    _cur["x"] += w
    _cur["row_h"] = max(_cur["row_h"], h)
    return x, y


# ---- query + panel helpers -------------------------------------------------
def M(metric, suffix=""):
    """Single-series stat PromQL: max() collapses instance labels."""
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
         mode="value", mappings=None, text_mode="auto"):
    x, y = _place(w, h)
    fld = {"unit": unit, "decimals": decimals,
           "thresholds": {"mode": "absolute",
                          "steps": steps or [{"color": "text", "value": None}]}}
    if mappings:
        fld["mappings"] = mappings
    panels.append({
        "id": _id(), "type": "stat", "title": title, "description": desc,
        "datasource": DS, "gridPos": {"h": h, "w": w, "x": x, "y": y},
        "fieldConfig": {"defaults": fld, "overrides": []},
        "options": {"colorMode": mode, "graphMode": "none",
                    "justifyMode": "auto", "textMode": text_mode,
                    "wideLayout": True,
                    "reduceOptions": {"calcs": ["lastNotNull"], "fields": "",
                                      "values": False}},
        "targets": [_t(expr)]})


def state(title, expr, w, h, mapping, desc=""):
    """A state readout: value -> colored text (UP/DOWN, ARMED, KILLED).
    mapping: {value_str: (text, color)}. Background-colored for a glance."""
    opts = {k: {"text": v[0], "color": v[1], "index": i}
            for i, (k, v) in enumerate(mapping.items())}
    stat(title, expr, w, h, desc=desc, mode="background", text_mode="value",
         mappings=[{"type": "value", "options": opts}],
         steps=[{"color": "text", "value": None}])


def gauge(title, expr, w, h, mx=35.0, desc=""):
    x, y = _place(w, h)
    panels.append({
        "id": _id(), "type": "gauge", "title": title, "description": desc,
        "datasource": DS, "gridPos": {"h": h, "w": w, "x": x, "y": y},
        "fieldConfig": {"defaults": {"unit": "percent", "min": 0, "max": mx,
            "decimals": 1, "thresholds": {"mode": "absolute", "steps": [
                {"color": "green", "value": None},
                {"color": "yellow", "value": mx * 0.7},
                {"color": "red", "value": mx * 0.9}]}}, "overrides": []},
        "options": {"showThresholdLabels": False, "showThresholdMarkers": True,
                    "reduceOptions": {"calcs": ["lastNotNull"], "fields": "",
                                      "values": False}},
        "targets": [_t(expr)]})


def table(title, w, h, cols, label_keys, sort=None, desc=""):
    """Comparison table. cols: (metric_or_expr, name, unit, decimals). Each
    target is an instant vector; frames MERGE on their shared label(s) in
    label_keys, giving one row per entity (per symbol/side, or per asset)."""
    x, y = _place(w, h)
    refs = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    targets, rename, order, overrides = [], {}, {}, []
    for k in label_keys:
        order[k] = len(order)
    for i, (metric, name, unit, dec) in enumerate(cols):
        r = refs[i]
        expr = metric if "(" in metric or "{" in metric else f"{metric}{JOB}"
        targets.append(_t(expr, ref=r, fmt="table"))
        rename[f"Value #{r}"] = name
        order[name] = len(order)
        overrides.append({"matcher": {"id": "byName", "options": name},
                          "properties": [{"id": "unit", "value": unit},
                                         {"id": "decimals", "value": dec}]})
    panels.append({
        "id": _id(), "type": "table", "title": title, "description": desc,
        "datasource": DS, "gridPos": {"h": h, "w": w, "x": x, "y": y},
        "fieldConfig": {"defaults": {"custom": {"align": "auto",
                                                "filterable": True}},
                        "overrides": overrides},
        "options": {"showHeader": True, "cellHeight": "sm",
                    "sortBy": [{"displayName": sort or label_keys[0],
                                "desc": bool(sort)}]},
        "targets": targets,
        "transformations": [
            {"id": "merge", "options": {}},
            {"id": "organize", "options": {
                "excludeByName": {"Time": True, "job": True, "instance": True,
                                  "__name__": True},
                "renameByName": rename, "indexByName": order}}]})


# threshold palettes
GRN = [{"color": "text", "value": None}]
PNL = [{"color": "red", "value": None}, {"color": "green", "value": 0}]
DD = [{"color": "green", "value": None}, {"color": "yellow", "value": 8},
      {"color": "red", "value": 12}]
LAT = [{"color": "green", "value": None}, {"color": "yellow", "value": 250},
       {"color": "red", "value": 500}]
AGE = [{"color": "green", "value": None}, {"color": "yellow", "value": 30},
       {"color": "red", "value": 90}]
CALIB = [{"color": "green", "value": None}, {"color": "yellow", "value": 0.10},
         {"color": "red", "value": 0.15}]
STREAK = [{"color": "green", "value": None}, {"color": "yellow", "value": 3},
          {"color": "red", "value": 5}]
WR = [{"color": "red", "value": None}, {"color": "yellow", "value": 45},
      {"color": "green", "value": 55}]

ON_OFF = {"1": ("YES", "green"), "0": ("NO", "red")}
UP_DOWN = {"1": ("RUNNING", "green"), "0": ("STOPPED", "red")}
WS = {"1": ("LIVE", "green"), "0": ("REST-fallback", "yellow")}
HALT = {"1": ("HALTED", "red"), "0": ("clear", "green")}
GOV = {"0": ("OK", "green"), "1": ("DEGRADED", "yellow"),
       "2": ("KILLED", "red")}


# ============================ §1 · Command & Health ========================
row("§1 · Command & Health")
state("Bot", M("liquiditybot_running"), 3, 4, UP_DOWN,
      desc="runner_state == RUNNING.")
stat("Status age", M("liquiditybot_status_age_sec"), 3, 4, unit="s",
     decimals=0, mode="background", steps=[{"color": "green", "value": None},
     {"color": "yellow", "value": 120}, {"color": "red", "value": 300}],
     desc="Seconds since the last status write; climbs if the runner freezes.")
stat("Cycle", M("liquiditybot_cycle"), 3, 4, decimals=0, steps=GRN,
     desc="Fast-cycle counter since last restart (advancing = alive).")
stat("Equity", M("liquiditybot_equity"), 4, 4, unit="currencyUSD", steps=GRN,
     desc="Account equity (cash + open uPnL).")
stat("Drawdown", M("liquiditybot_drawdown_pct"), 3, 4, unit="percent",
     mode="background", steps=DD, desc="Peak-to-now; 15% is the hard stop.")
stat("Feed latency", M("liquiditybot_feed_latency_ms"), 4, 4, unit="ms",
     decimals=0, steps=LAT, desc="Kraken public-GET RTT EWMA (physical RTT).")
stat("Open uPnL", M("liquiditybot_open_upnl_usd"), 4, 4, unit="currencyUSD",
     steps=PNL, desc="Unrealized P&L across open positions.")

state("Governor", M("liquiditybot_monitor_level"), 4, 3, GOV,
      desc="ML kill-switch: 0 OK / 1 degraded / 2 model killed.")
state("Entries", M("liquiditybot_entries_enabled"), 3, 3, ON_OFF,
      desc="New-risk entries enabled (exits always allowed).")
state("Halted", M("liquiditybot_halted"), 3, 3, HALT, desc="Global halt flag.")
state("Kraken WS", M("liquiditybot_ws_kraken_connected"), 4, 3, WS,
      desc="v2 book stream live vs REST fallback.")
state("Model in use", M("liquiditybot_ml_use_model"), 4, 3, ON_OFF,
      desc="Governor lets the model size trades (vs cold-start prior).")
stat("Open risk", M("liquiditybot_open_risk_usd"), 3, 3, unit="currencyUSD",
     steps=GRN, desc="$ lost if every open stop filled now.")
gauge("Gross exposure", M("liquiditybot_gross_exposure_pct"), 3, 3, mx=35.0,
      desc="Gross notional %/equity vs the 35% heat cap.")

# ============================ §2 · Learning brain ==========================
row("§2 · Learning brain")
stat("Live labels", M('liquiditybot_ml_labels{source="live"}'), 4, 4,
     decimals=0, mode="background",
     steps=[{"color": "red", "value": None}, {"color": "yellow", "value": 30},
            {"color": "green", "value": 60}],
     desc="Ground-truth closed-trade labels — the ONLY thing that earns model "
          "complexity (evidence gate). This is the number to grow.")
stat("Candidate labels", M('liquiditybot_ml_labels{source="candidate"}'), 4, 4,
     decimals=0, steps=GRN,
     desc="Triple-barrier proxy labels (down-weighted, don't earn complexity).")
stat("History rows", M("liquiditybot_ml_history_rows"), 3, 4, decimals=0,
     steps=GRN, desc="Total training rows (live + candidate).")
stat("Model", "count(liquiditybot_ml_model_info" + JOB + ") by (kind)", 4, 4,
     desc="Deployed rung on the simplicity ladder.", text_mode="name",
     steps=GRN)
stat("Retrain queued", M("liquiditybot_ml_retrain_flag"), 3, 4, decimals=0,
     mode="background", mappings=[{"type": "value", "options": {
         "1": {"text": "YES", "color": "yellow", "index": 0},
         "0": {"text": "no", "color": "green", "index": 1}}}],
     steps=GRN, desc="Monitor has requested a retrain.")
stat("Drift share", M("liquiditybot_ml_drift_share"), 3, 4, unit="percentunit",
     steps=[{"color": "green", "value": None}, {"color": "yellow", "value": 0.3},
            {"color": "red", "value": 0.5}],
     desc="Fraction of market features past the PSI threshold.")

stat("Brier", M("liquiditybot_ml_brier"), 4, 4, decimals=4, mode="background",
     steps=[{"color": "green", "value": None}, {"color": "yellow", "value": 0.24},
            {"color": "red", "value": 0.25}],
     desc="Rolling outcome Brier on the deployed model (lower better).")
stat("Baseline Brier", M("liquiditybot_ml_baseline_brier"), 4, 4, decimals=4,
     steps=GRN, desc="Base-rate Brier; model must beat this.")
stat("Calibration gap", M("liquiditybot_ml_calibration_gap"), 4, 4, decimals=3,
     mode="background", steps=CALIB,
     desc="|predicted - realized| ECE. Kelly consumes probs literally, so this "
          "must stay small.")
stat("Champion Brier", M("liquiditybot_ml_champion_brier"), 4, 4, decimals=4,
     steps=GRN, desc="Deployed champion's OOF Brier badge.")
stat("Kelly mult", M("liquiditybot_ml_kelly_mult"), 4, 4, decimals=2, steps=GRN,
     desc="Governor size throttle (1.0 = full).")
stat("Shrinkage", M("liquiditybot_ml_shrinkage"), 4, 4, decimals=2, steps=GRN,
     desc="Probability shrink toward base rate.")

stat("Win rate", M("liquiditybot_perf_win_rate", "*100"), 4, 4, unit="percent",
     decimals=1, mode="background", steps=WR, desc="Rolling closed-trade win rate.")
stat("Win rate LCB", M("liquiditybot_perf_win_rate_lcb", "*100"), 4, 4,
     unit="percent", decimals=1, steps=GRN,
     desc="Wilson lower bound — the honest floor.")
stat("Profit factor", M("liquiditybot_perf_profit_factor"), 4, 4, decimals=2,
     steps=[{"color": "red", "value": None}, {"color": "yellow", "value": 1.0},
            {"color": "green", "value": 1.5}], desc="Gross profit / gross loss.")
stat("Expectancy R", M("liquiditybot_perf_expectancy_r"), 4, 4, decimals=2,
     steps=PNL, desc="Avg trade in R-multiples.")
stat("Net (window)", M("liquiditybot_perf_net_usd"), 4, 4, unit="currencyUSD",
     steps=PNL, desc="Net realized over the rolling window.")
stat("Trades", M("liquiditybot_perf_trades"), 4, 4, decimals=0, steps=GRN,
     desc="Closed trades in the window.")

# ============================ §3 · Positions ===============================
row("§3 · Positions (net per instrument)")
table("Open positions", 24, 8,
      cols=[("liquiditybot_position_upnl_usd", "uPnL $", "currencyUSD", 2),
            ("liquiditybot_position_upnl_pct", "uPnL %", "percent", 2),
            ("liquiditybot_position_r_multiple", "R", "short", 2),
            ("liquiditybot_position_notional_usd", "Notional $", "currencyUSD", 0),
            ("liquiditybot_position_conviction", "p_win", "percentunit", 2),
            ("liquiditybot_position_stop_dist_pct", "Stop dist %", "percent", 2),
            ("liquiditybot_position_tiers_fired", "Tiers", "short", 0),
            ("liquiditybot_position_age_hours", "Age h", "short", 1)],
      label_keys=["symbol", "side"], sort="uPnL $",
      desc="One row per open instrument. Sorted by uPnL; watch R and stop "
           "distance for what to manage next.")

# ============================ §4 · Per-asset comparison ====================
row("§4 · Per-asset comparison — where is the edge?")
table("Asset scorecard", 24, 9,
      cols=[("liquiditybot_perf_asset_win_rate", "Win rate", "percentunit", 2),
            ("liquiditybot_perf_asset_net_usd", "Net $", "currencyUSD", 2),
            ("liquiditybot_perf_asset_trades", "Trades", "short", 0),
            ("liquiditybot_perf_asset_cur_loss_streak", "Loss streak", "short", 0),
            ("liquiditybot_signal_confidence", "Confidence", "short", 2),
            ("liquiditybot_signal_urgency", "Urgency", "short", 2),
            ("liquiditybot_signal_concentration", "Concentration", "short", 2),
            ("liquiditybot_manip_suspect", "Manip", "short", 2),
            ("liquiditybot_regime_spread_bps", "Spread bps", "short", 1),
            ("liquiditybot_regime_vol_pct", "Vol %", "percent", 1)],
      label_keys=["asset"], sort="Net $",
      desc="Side-by-side, one row per asset. Concentration near 1 = a "
           "pinpointed setup (few strong factors); near 0 = a diffuse average. "
           "Compare win rate/net against confidence & concentration to see "
           "where conviction is actually paying — the input to session/asset "
           "weighting decisions.")

# ============================ §5 · Risk & incidents ========================
row("§5 · Risk & incidents")
stat("Loss streak (now)", M("liquiditybot_perf_cur_loss_streak"), 4, 4,
     decimals=0, mode="background", steps=STREAK,
     desc="Consecutive losers now — the circuit-breaker input.")
stat("Max loss streak", M("liquiditybot_perf_max_loss_streak"), 4, 4,
     decimals=0, steps=GRN, desc="Worst streak in the window.")
stat("Model fallbacks", M("liquiditybot_ml_model_fallbacks"), 4, 4, decimals=0,
     mode="background", steps=STREAK, desc="Inference fell back to the prior.")
stat("Infer faults", M("liquiditybot_ml_infer_faults"), 4, 4, decimals=0,
     mode="background", steps=STREAK, desc="Model inference errors.")
stat("Contract fails", M("liquiditybot_ml_contract_failed"), 4, 4, decimals=0,
     mode="background", steps=STREAK, desc="Inference input outside contract.")
stat("Retrain failures", M("liquiditybot_ml_retrain_failures"), 4, 4,
     decimals=0, mode="background", steps=STREAK, desc="Auto-retrain crashed.")

table("Entry-decision reason codes", 12, 8,
      cols=[("liquiditybot_code_count_detail", "Count", "short", 0)],
      label_keys=["code"], sort="Count",
      desc="Why entries were taken/vetoed (SZ/PT/QT families) — the most "
           "frequent code is what's gating the book right now.")
table("Gate weights (learned)", 12, 8,
      cols=[("liquiditybot_gate_weight", "Weight", "short", 3)],
      label_keys=["gate"], sort="Weight",
      desc="Evidence-weighted contribution of each signal gate.")


# ============================ assemble =====================================
def _dash():
    return {"uid": "liquiditybot-trading",
            "title": "liquiditybot — command",
            "description": "Condensed logistical command board: health, "
                           "learning brain, positions, per-asset comparison, "
                           "risk. Replaces the old multi-dashboard set.",
            "tags": ["liquiditybot", "trading", "paper-trading", "command"],
            "schemaVersion": 39, "editable": True, "timezone": "browser",
            "refresh": "30s", "time": {"from": "now-24h", "to": "now"},
            "templating": {"list": []}, "annotations": {"list": []},
            "panels": panels}


DASHBOARDS = {"liquiditybot_command.json": _dash()}
OUT_DIR = Path(__file__).resolve().parents[1] / "docs" / "grafana"

if __name__ == "__main__":
    for fname, d in DASHBOARDS.items():
        out = OUT_DIR / fname
        out.write_text(json.dumps(d, indent=2, ensure_ascii=False),
                       encoding="utf-8")
        print(f"wrote {out} — {len(d['panels'])} panels ({d['title']})")
