"""scripts/build_trading_dashboard.py — generator for the logistical dashboards.

THIS GENERATOR IS THE SOURCE OF TRUTH: edit here and regenerate; never
hand-edit the JSONs. tests/test_trading_dashboard.py enforces (1) generator ==
shipped JSON, (2) importable shape / no overlapping panels, (3) every metric a
panel queries is actually emitted by scripts/gc_pusher.py, (4) LOGISTICAL only
(stat/state/table/gauge — no time-series graphs).

Four focused boards, one theme each, same condensed format:

  liquiditybot_command.json          — daily driver: health, learning brain,
                                       positions, per-asset comparison, risk
  liquiditybot_execution.json        — decision models · inventory · execution
                                       (model health, positioning/heat, fills)
  liquiditybot_problem_solution.json — every failure mode as a PROBLEM whose
                                       panel shows the live detector and names
                                       the SOLUTION mechanism handling it
  liquiditybot_screening.json        — asset screening: skimmer ranks + a
                                       per-asset tradeability scorecard

Everything is a state/number/table you read at a glance, organized for
DECISIONS. Boards are authored by functions that share the helpers below; each
resets the layout cursor so panel ids and gridPos never collide across boards.
"""
import json
from pathlib import Path

DS = {"type": "prometheus", "uid": "grafanacloud-prom"}
JOB = '{job="liquiditybot"}'
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


# threshold palettes / mappings
GRN = [{"color": "text", "value": None}]
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
WR = [{"color": "red", "value": None}, {"color": "yellow", "value": 45},
      {"color": "green", "value": 55}]
SLIP = [{"color": "green", "value": None}, {"color": "yellow", "value": 3},
        {"color": "red", "value": 8}]

ON_OFF = {"1": ("YES", "green"), "0": ("NO", "red")}
UP_DOWN = {"1": ("RUNNING", "green"), "0": ("STOPPED", "red")}
WS = {"1": ("LIVE", "green"), "0": ("REST-fallback", "yellow")}
HALT = {"1": ("HALTED", "red"), "0": ("clear", "green")}
GOV = {"0": ("OK", "green"), "1": ("DEGRADED", "yellow"),
       "2": ("KILLED", "red")}
OPSTATE = {"0": ("ARMED", "green"), "1": ("DEGRADED", "yellow"),
           "2": ("HALTED", "red"), "-1": ("UNKNOWN", "red")}
RETRAIN = {"1": ("QUEUED", "yellow"), "0": ("idle", "green")}


# ========================= board 1 · command ===============================
def _author_command():
    row("§1 · Command & Health")
    state("Bot", M("liquiditybot_running"), 3, 4, UP_DOWN,
          desc="runner_state == RUNNING.")
    stat("Status age", M("liquiditybot_status_age_sec"), 3, 4, unit="s",
         decimals=0, mode="background",
         steps=[{"color": "green", "value": None},
                {"color": "yellow", "value": 120}, {"color": "red", "value": 300}],
         desc="Seconds since the last status write; climbs if the runner freezes.")
    stat("Cycle", M("liquiditybot_cycle"), 3, 4, decimals=0, steps=GRN,
         desc="Fast-cycle counter (advancing = alive).")
    stat("Equity", M("liquiditybot_equity"), 4, 4, unit="currencyUSD", steps=GRN,
         desc="Account equity (cash + open uPnL).")
    stat("Drawdown", M("liquiditybot_drawdown_pct"), 3, 4, unit="percent",
         mode="background", steps=DD, desc="Peak-to-now; 15% is the hard stop.")
    stat("Feed latency", M("liquiditybot_feed_latency_ms"), 4, 4, unit="ms",
         decimals=0, steps=LAT, desc="Kraken public-GET RTT EWMA.")
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
          desc="Governor lets the model size trades.")
    stat("Open risk", M("liquiditybot_open_risk_usd"), 3, 3, unit="currencyUSD",
         steps=GRN, desc="$ lost if every open stop filled now.")
    gauge("Gross exposure", M("liquiditybot_gross_exposure_pct"), 3, 3, mx=35.0,
          desc="Gross notional %/equity vs the 35% heat cap.")

    row("§2 · Learning brain")
    stat("Live labels", M('liquiditybot_ml_labels{source="live"}'), 4, 4,
         decimals=0, mode="background",
         steps=[{"color": "red", "value": None}, {"color": "yellow", "value": 30},
                {"color": "green", "value": 60}],
         desc="Ground-truth closed-trade labels — earns model complexity.")
    stat("Candidate labels", M('liquiditybot_ml_labels{source="candidate"}'),
         4, 4, decimals=0, steps=GRN, desc="Triple-barrier proxy labels.")
    stat("History rows", M("liquiditybot_ml_history_rows"), 3, 4, decimals=0,
         steps=GRN, desc="Total training rows.")
    stat("Model", "count(liquiditybot_ml_model_info" + JOB + ") by (kind)", 4, 4,
         desc="Deployed rung on the simplicity ladder.", text_mode="name",
         steps=GRN)
    stat("Retrain queued", M("liquiditybot_ml_retrain_flag"), 3, 4, decimals=0,
         mode="background", mappings=[{"type": "value", "options": {
             "1": {"text": "YES", "color": "yellow", "index": 0},
             "0": {"text": "no", "color": "green", "index": 1}}}], steps=GRN,
         desc="Monitor has requested a retrain.")
    stat("Drift share", M("liquiditybot_ml_drift_share"), 3, 4,
         unit="percentunit", steps=[{"color": "green", "value": None},
         {"color": "yellow", "value": 0.3}, {"color": "red", "value": 0.5}],
         desc="Fraction of market features past the PSI threshold.")
    stat("Brier", M("liquiditybot_ml_brier"), 4, 4, decimals=4, mode="background",
         steps=[{"color": "green", "value": None}, {"color": "yellow", "value": 0.24},
                {"color": "red", "value": 0.25}], desc="Rolling outcome Brier.")
    stat("Baseline Brier", M("liquiditybot_ml_baseline_brier"), 4, 4,
         decimals=4, steps=GRN, desc="Base-rate Brier; model must beat this.")
    stat("Calibration gap", M("liquiditybot_ml_calibration_gap"), 4, 4,
         decimals=3, mode="background", steps=CALIB, desc="ECE; Kelly reads "
         "probs literally so keep small.")
    stat("Champion Brier", M("liquiditybot_ml_champion_brier"), 4, 4,
         decimals=4, steps=GRN, desc="Deployed champion's OOF badge.")
    stat("Kelly mult", M("liquiditybot_ml_kelly_mult"), 4, 4, decimals=2,
         steps=GRN, desc="Governor size throttle.")
    stat("Shrinkage", M("liquiditybot_ml_shrinkage"), 4, 4, decimals=2,
         steps=GRN, desc="Probability shrink toward base rate.")
    stat("Win rate", M("liquiditybot_perf_win_rate", "*100"), 4, 4,
         unit="percent", decimals=1, mode="background", steps=WR,
         desc="Rolling closed-trade win rate.")
    stat("Win rate LCB", M("liquiditybot_perf_win_rate_lcb", "*100"), 4, 4,
         unit="percent", decimals=1, steps=GRN, desc="Wilson lower bound.")
    stat("Profit factor", M("liquiditybot_perf_profit_factor"), 4, 4,
         decimals=2, steps=[{"color": "red", "value": None},
         {"color": "yellow", "value": 1.0}, {"color": "green", "value": 1.5}],
         desc="Gross profit / gross loss.")
    stat("Expectancy R", M("liquiditybot_perf_expectancy_r"), 4, 4, decimals=2,
         steps=PNL, desc="Avg trade in R-multiples.")
    stat("Net (window)", M("liquiditybot_perf_net_usd"), 4, 4,
         unit="currencyUSD", steps=PNL, desc="Net realized over the window.")
    stat("Trades", M("liquiditybot_perf_trades"), 4, 4, decimals=0, steps=GRN,
         desc="Closed trades in the window.")

    row("§3 · Positions (net per instrument)")
    _positions_table()

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
          desc="One row per asset. Concentration ~1 = a pinpointed setup; ~0 = "
               "a diffuse average. Compare net/win rate against confidence & "
               "concentration to see where conviction is paying.")

    row("§5 · Risk & incidents")
    stat("Loss streak (now)", M("liquiditybot_perf_cur_loss_streak"), 4, 4,
         decimals=0, mode="background", steps=STREAK,
         desc="Consecutive losers now — circuit-breaker input.")
    stat("Max loss streak", M("liquiditybot_perf_max_loss_streak"), 4, 4,
         decimals=0, steps=GRN, desc="Worst streak in the window.")
    stat("Model fallbacks", M("liquiditybot_ml_model_fallbacks"), 4, 4,
         decimals=0, mode="background", steps=STREAK, desc="Inference fell to prior.")
    stat("Infer faults", M("liquiditybot_ml_infer_faults"), 4, 4, decimals=0,
         mode="background", steps=STREAK, desc="Model inference errors.")
    stat("Contract fails", M("liquiditybot_ml_contract_failed"), 4, 4,
         decimals=0, mode="background", steps=STREAK, desc="Input outside contract.")
    stat("Retrain failures", M("liquiditybot_ml_retrain_failures"), 4, 4,
         decimals=0, mode="background", steps=STREAK, desc="Auto-retrain crashed.")
    table("Entry-decision reason codes", 12, 8,
          cols=[("liquiditybot_code_count_detail", "Count", "short", 0)],
          label_keys=["code"], sort="Count",
          desc="Why entries were taken/vetoed — the most frequent code is what "
               "gates the book now.")
    table("Gate weights (learned)", 12, 8,
          cols=[("liquiditybot_gate_weight", "Weight", "short", 3)],
          label_keys=["gate"], sort="Weight",
          desc="Evidence-weighted contribution of each signal gate.")


def _positions_table():
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
          desc="One row per open instrument; watch R and stop distance for what "
               "to manage next.")


# ================= board 2 · models · inventory · execution ================
def _author_execution():
    row("§1 · Decision model")
    stat("Model", "count(liquiditybot_ml_model_info" + JOB + ") by (kind)", 4, 4,
         desc="Deployed rung on the simplicity ladder (evidence-gated).",
         text_mode="name", steps=GRN)
    state("Model in use", M("liquiditybot_ml_use_model"), 4, 4, ON_OFF,
          desc="Governor lets the model size trades vs the cold-start prior.")
    state("Governor", M("liquiditybot_monitor_level"), 4, 4, GOV,
          desc="0 OK / 1 degraded / 2 killed.")
    stat("Brier", M("liquiditybot_ml_brier"), 4, 4, decimals=4, mode="background",
         steps=[{"color": "green", "value": None}, {"color": "yellow", "value": 0.24},
                {"color": "red", "value": 0.25}], desc="Rolling outcome Brier.")
    stat("Baseline", M("liquiditybot_ml_baseline_brier"), 4, 4, decimals=4,
         steps=GRN, desc="Base-rate Brier the model must beat.")
    stat("Champion", M("liquiditybot_ml_champion_brier"), 4, 4, decimals=4,
         steps=GRN, desc="Deployed champion's OOF badge.")
    stat("Calibration gap", M("liquiditybot_ml_calibration_gap"), 4, 4,
         decimals=3, mode="background", steps=CALIB, desc="ECE; Kelly reads probs literally.")
    stat("Hit rate", M("liquiditybot_ml_hit_rate", "*100"), 4, 4, unit="percent",
         decimals=1, steps=GRN, desc="Delivered win rate on the judge window.")
    stat("Hit rate LCB", M("liquiditybot_ml_hit_rate_lcb", "*100"), 4, 4,
         unit="percent", decimals=1, steps=GRN, desc="Wilson floor of delivered.")
    stat("Promised p", M("liquiditybot_ml_avg_p", "*100"), 4, 4, unit="percent",
         decimals=1, steps=GRN, desc="Mean predicted p (promised vs delivered).")
    stat("Kelly mult", M("liquiditybot_ml_kelly_mult"), 4, 4, decimals=2,
         steps=GRN, desc="Size throttle.")
    stat("Shrinkage", M("liquiditybot_ml_shrinkage"), 4, 4, decimals=2,
         steps=GRN, desc="Shrink toward base rate.")
    stat("Stop widen", M("liquiditybot_ml_stop_widen"), 4, 4, decimals=2,
         steps=GRN, desc="Governor stop-distance multiplier.")
    stat("Edge bump", M("liquiditybot_ml_edge_ratio_bump"), 4, 4, decimals=2,
         steps=GRN, desc="Extra EV-gate margin the governor demands.")
    stat("Live labels", M('liquiditybot_ml_labels{source="live"}'), 4, 4,
         decimals=0, mode="background", steps=[{"color": "red", "value": None},
         {"color": "yellow", "value": 30}, {"color": "green", "value": 60}],
         desc="Ground truth that earns model complexity.")
    stat("Drift share", M("liquiditybot_ml_drift_share"), 4, 4,
         unit="percentunit", steps=[{"color": "green", "value": None},
         {"color": "yellow", "value": 0.3}, {"color": "red", "value": 0.5}],
         desc="Feature PSI drift fraction.")
    table("Per-asset signal quality", 12, 8,
          cols=[("liquiditybot_signal_confidence", "Confidence", "short", 2),
                ("liquiditybot_signal_urgency", "Urgency", "short", 2),
                ("liquiditybot_signal_concentration", "Concentration", "short", 2),
                ("liquiditybot_manip_suspect", "Manip", "short", 2)],
          label_keys=["asset"], sort="Concentration",
          desc="Signal decision quality per asset. Concentration ~1 = pinpointed.")
    table("Learned gate weights", 12, 8,
          cols=[("liquiditybot_gate_weight", "Weight", "short", 3)],
          label_keys=["gate"], sort="Weight",
          desc="Evidence-weighted contribution of each gate.")

    row("§2 · Inventory & positioning")
    stat("Open positions", M("liquiditybot_positions_open"), 4, 5, decimals=0,
         steps=GRN, desc="Open count (max 5 concurrent).")
    gauge("Gross exposure", M("liquiditybot_gross_exposure_pct"), 5, 5, mx=35.0,
          desc="Gross notional %/equity vs the 35% heat cap.")
    gauge("Portfolio heat", M("liquiditybot_rp_heat_frac", "*100"), 5, 5, mx=35.0,
          desc="CVaR portfolio heat vs cap.")
    stat("Open risk", M("liquiditybot_open_risk_usd"), 5, 5, unit="currencyUSD",
         steps=GRN, desc="$ at risk to stops.")
    stat("Open uPnL", M("liquiditybot_open_upnl_usd"), 5, 5, unit="currencyUSD",
         steps=PNL, desc="Unrealized across positions.")
    _positions_table()

    row("§3 · Execution quality")
    gauge("Maker share", M("liquiditybot_order_maker_share", "*100"), 5, 5,
          mx=100.0, desc="% of fills that were maker (limit) — higher = cheaper.")
    stat("Maker fills", M("liquiditybot_order_maker_fills"), 4, 5, decimals=0,
         steps=GRN, desc="Maker fills in the window.")
    stat("Taker fills", M("liquiditybot_order_taker_fills"), 4, 5, decimals=0,
         steps=GRN, desc="Taker fills (exit-ladder final rung).")
    stat("Avg slippage", M("liquiditybot_order_avg_slip_bps"), 4, 5, unit="short",
         decimals=1, mode="background", steps=SLIP,
         desc="Rolling avg slippage bps (negative = price improvement).")
    stat("Worst slippage", M("liquiditybot_order_worst_slip_bps"), 3, 5,
         unit="short", decimals=1, mode="background", steps=SLIP,
         desc="Worst single slippage in the window.")
    stat("Venue RTT", M("liquiditybot_order_latency_ms"), 4, 5, unit="ms",
         decimals=0, steps=LAT, desc="Private POST RTT (order path).")
    stat("Venue rejects", M("liquiditybot_order_venue_rejects"), 4, 4,
         decimals=0, mode="background", steps=STREAK, desc="OM-021 AddOrder rejects.")
    stat("Dead-man failures", M("liquiditybot_order_deadman_failures"), 4, 4,
         decimals=0, mode="background", steps=ZERO_BAD,
         desc="OM-050 CancelAllAfter refresh failures — resting orders unguarded.")
    stat("Maker notional", M("liquiditybot_order_maker_notional_usd"), 4, 4,
         unit="currencyUSD", decimals=0, steps=GRN, desc="Maker-filled notional.")
    stat("Taker notional", M("liquiditybot_order_taker_notional_usd"), 4, 4,
         unit="currencyUSD", decimals=0, steps=GRN, desc="Taker-filled notional.")
    table("Post-fill mark-out (adverse selection)", 8, 6,
          cols=[("liquiditybot_markout_bps", "Mark-out bps", "short", 2)],
          label_keys=["asset", "horizon_sec"], sort="Mark-out bps",
          desc="Price drift after our fill; persistently negative = we're being "
               "picked off (adverse selection).")


# ==================== board 3 · problem / solution =========================
def _author_problem():
    row("§A · Feed & data integrity")
    stat("PROBLEM: stale status", M("liquiditybot_status_age_sec"), 6, 5,
         unit="s", decimals=0, mode="background",
         steps=[{"color": "green", "value": None}, {"color": "yellow", "value": 120},
                {"color": "red", "value": 300}],
         desc="Detector: seconds since last status write. SOLUTION: runner "
              "wedge-guard escalates a persistently-failing cycle; supervisor "
              "revives a dead runner.")
    state("SOLUTION: Kraken WS", M("liquiditybot_ws_kraken_connected"), 6, 5, WS,
          desc="Push-book stream. When it drops, the SOLUTION is automatic: the "
               "engine falls back to the REST book — trading continues.")
    stat("PROBLEM: stale marks", M("liquiditybot_marks_age_sec"), 6, 5, unit="s",
         decimals=0, mode="background", steps=[{"color": "green", "value": None},
         {"color": "yellow", "value": 30}, {"color": "red", "value": 90}],
         desc="Detector: oldest live mark age. SOLUTION: mark-freshness gate "
              "holds non-escape risk actions on stale data; stops still run.")
    stat("SOLUTION: stale assets held", M("liquiditybot_watchdog_stale_assets"),
         6, 5, decimals=0, mode="background", steps=ZERO_BAD,
         desc="Watchdog count of assets quarantined for stale/divergent feeds "
              "— entries blocked on them until the feed heals.")
    stat("watchdog: entries blocked", M("liquiditybot_watchdog_entries_blocked"),
         6, 4, decimals=0, mode="background", steps=ZERO_BAD,
         desc="Feed watchdog is blocking new entries (a SOLUTION firing).")
    stat("watchdog: critical stale", M("liquiditybot_watchdog_critical_stale"),
         6, 4, decimals=0, mode="background", steps=ZERO_BAD,
         desc="Critical staleness latch.")
    stat("watchdog: divergent feeds", M("liquiditybot_watchdog_divergent"), 6, 4,
         decimals=0, mode="background", steps=ZERO_BAD,
         desc="Cross-venue book divergence count.")
    stat("watchdog: velocity trip", M("liquiditybot_watchdog_velocity_tripped"),
         6, 4, decimals=0, mode="background", steps=ZERO_BAD,
         desc="Tick-velocity quarantine (fat-finger guard).")

    row("§B · Model health")
    stat("PROBLEM: model Brier", M("liquiditybot_ml_brier"), 5, 5, decimals=4,
         mode="background", steps=[{"color": "green", "value": None},
         {"color": "yellow", "value": 0.24}, {"color": "red", "value": 0.25}],
         desc="Detector: rolling outcome Brier. SOLUTION: the ML governor "
              "kill-switch (below) disables the model and requests a retrain "
              "when Brier drifts past baseline.")
    stat("vs baseline", M("liquiditybot_ml_baseline_brier"), 4, 5, decimals=4,
         steps=GRN, desc="The bar Brier must stay under.")
    state("SOLUTION: governor", M("liquiditybot_monitor_level"), 5, 5, GOV,
          desc="0 OK / 1 shrink+throttle / 2 model killed to the prior.")
    state("SOLUTION: retrain", M("liquiditybot_ml_retrain_flag"), 4, 5, RETRAIN,
          desc="Auto-retrain queued to replace a degrading champion.")
    stat("calibration gap", M("liquiditybot_ml_calibration_gap"), 3, 5,
         decimals=3, mode="background", steps=CALIB, desc="Miscalibration; ECE.")
    stat("drift share", M("liquiditybot_ml_drift_share"), 3, 5,
         unit="percentunit", steps=[{"color": "green", "value": None},
         {"color": "yellow", "value": 0.3}, {"color": "red", "value": 0.5}],
         desc="PROBLEM: input drift. SOLUTION: retrain re-fits on fresh data.")
    stat("SOLUTION: kelly throttle", M("liquiditybot_ml_kelly_mult"), 4, 4,
         decimals=2, steps=GRN, desc="Governor shrinks size as confidence falls.")
    stat("model fallbacks", M("liquiditybot_ml_model_fallbacks"), 4, 4,
         decimals=0, mode="background", steps=STREAK,
         desc="Inference fell to the cold-start prior (fail-safe firing).")
    stat("infer faults", M("liquiditybot_ml_infer_faults"), 4, 4, decimals=0,
         mode="background", steps=STREAK, desc="Inference errors.")
    stat("contract fails", M("liquiditybot_ml_contract_failed"), 4, 4,
         decimals=0, mode="background", steps=STREAK, desc="Input outside contract.")
    stat("retrain failures", M("liquiditybot_ml_retrain_failures"), 4, 4,
         decimals=0, mode="background", steps=STREAK, desc="Auto-retrain crashed.")

    row("§C · Capital & drawdown")
    stat("PROBLEM: drawdown", M("liquiditybot_drawdown_pct"), 5, 5,
         unit="percent", mode="background", steps=DD,
         desc="Detector: peak-to-now. SOLUTION: drawdown throttle + the 15% "
              "hard-stop flatten.")
    stat("PROBLEM: loss streak", M("liquiditybot_perf_cur_loss_streak"), 5, 5,
         decimals=0, mode="background", steps=STREAK,
         desc="Detector: consecutive losers. SOLUTION: the per-asset circuit "
              "breaker pauses that asset.")
    stat("SOLUTION: breakers tripped", M("liquiditybot_cb_tripped_count"), 4, 5,
         decimals=0, mode="background", steps=ZERO_BAD,
         desc="Assets currently paused by the circuit breaker.")
    gauge("SOLUTION: heat vs cap", M("liquiditybot_rp_heat_frac", "*100"), 5, 5,
          mx=35.0, desc="Portfolio heat throttled under the CVaR cap.")
    stat("SOLUTION: taper mult", M("liquiditybot_rp_taper_mult"), 5, 5,
         decimals=2, steps=GRN,
         desc="Loss-budget taper shrinks size as the daily budget is consumed.")
    stat("daily budget used", M("liquiditybot_rp_daily_budget_used_frac", "*100"),
         6, 4, unit="percent", decimals=0, mode="background",
         steps=[{"color": "green", "value": None}, {"color": "yellow", "value": 60},
                {"color": "red", "value": 90}], desc="Daily loss budget consumed.")
    stat("weekly budget used", M("liquiditybot_rp_weekly_budget_used_frac", "*100"),
         6, 4, unit="percent", decimals=0, mode="background",
         steps=[{"color": "green", "value": None}, {"color": "yellow", "value": 60},
                {"color": "red", "value": 90}], desc="Weekly loss budget consumed.")
    stat("dd throttle mult", M("liquiditybot_rp_dd_throttle_mult"), 6, 4,
         decimals=2, steps=GRN, desc="Drawdown size throttle.")
    stat("SOLUTION: model kelly", M("liquiditybot_ml_kelly_mult"), 6, 4,
         decimals=2, steps=GRN, desc="Kelly size throttle (compounds with taper).")
    table("Circuit breaker — paused assets", 12, 7,
          cols=[("liquiditybot_cb_loss_streak", "Loss streak", "short", 0),
                ("liquiditybot_cb_paused_hours_left", "Hours left", "short", 1)],
          label_keys=["asset"], sort="Loss streak",
          desc="Per-asset breaker state; hours-left counts the cool-off.")

    row("§D · Manipulation, venue & integrity")
    state("PROBLEM/SOLUTION: op-state", M("liquiditybot_op_state"), 5, 5, OPSTATE,
          desc="Central fault authority: ARMED nominal / DEGRADED no-new-risk / "
               "HALTED flatten-and-stop.")
    stat("latched faults", M("liquiditybot_fault_count"), 4, 5, decimals=0,
         mode="background", steps=ZERO_BAD, desc="Active latched faults.")
    state("firewall fault", M("liquiditybot_firewall_fault"), 5, 5, HALT,
          desc="Risk-firewall latched fault (blocks new risk).")
    stat("PROBLEM: cycle wedge", M("liquiditybot_cycle_consecutive_failures"),
         5, 5, decimals=0, mode="background", steps=STREAK,
         desc="Detector: consecutive failing cycles. SOLUTION: runner wedge "
              "escalation.")
    stat("exit-eval failures", M("liquiditybot_exit_eval_failures"), 5, 5,
         decimals=0, mode="background", steps=ZERO_BAD,
         desc="A position wedging its own exit path.")
    stat("venue rejects", M("liquiditybot_order_venue_rejects"), 4, 4,
         decimals=0, mode="background", steps=STREAK, desc="OM-021 AddOrder rejects.")
    stat("dead-man failures", M("liquiditybot_order_deadman_failures"), 4, 4,
         decimals=0, mode="background", steps=ZERO_BAD,
         desc="OM-050 — resting orders would be unguarded.")
    stat("audit dropped writes", M("liquiditybot_audit_dropped_writes"), 4, 4,
         decimals=0, mode="background", steps=ZERO_BAD, desc="Audit-trail write drops.")
    stat("audit tail truncations", M("liquiditybot_audit_tail_truncations"), 4, 4,
         decimals=0, mode="background", steps=ZERO_BAD, desc="Audit tail truncations.")
    table("Firewall — clamps/rejects by code", 12, 7,
          cols=[("liquiditybot_firewall_count", "Count", "short", 0)],
          label_keys=["code"], sort="Count",
          desc="Which firewall rule (FW-*) is clamping/rejecting most.")
    table("Manipulation suspicion by asset", 12, 7,
          cols=[("liquiditybot_manip_suspect", "Manip", "short", 2),
                ("liquiditybot_regime_spoof", "Spoof", "short", 2)],
          label_keys=["asset"], sort="Manip",
          desc="PROBLEM: painted/spoofed books. SOLUTION: THALES shades size "
               "and down-weights those training rows.")


# ==================== board 4 · asset screening ============================
def _author_screening():
    row("§1 · Skimmer — candidate universe")
    stat("Candidates scanned", M("liquiditybot_skimmer_candidates"), 6, 4,
         decimals=0, steps=GRN, desc="Off-universe pairs the skimmer ranked.")
    stat("Promoted", M("liquiditybot_skimmer_promoted_count"), 6, 4, decimals=0,
         steps=GRN, desc="Pairs promoted into the tradeable set this cycle.")
    stat("Open positions", M("liquiditybot_positions_open"), 6, 4, decimals=0,
         steps=GRN, desc="Slots in use (max 5).")
    gauge("Gross exposure", M("liquiditybot_gross_exposure_pct"), 6, 4, mx=35.0,
          desc="Room left under the heat cap for a new name.")
    table("Skimmer ranking (higher = better book)", 12, 8,
          cols=[("liquiditybot_skimmer_score", "Score", "short", 3)],
          label_keys=["pair"], sort="Score",
          desc="Composite liquidity/spread/depth score per candidate pair.")
    table("Promoted pairs", 12, 8,
          cols=[("liquiditybot_skimmer_promoted_info", "Promoted", "short", 0)],
          label_keys=["pair"], sort="Promoted",
          desc="Pairs currently promoted into the tradeable universe.")

    row("§2 · Per-asset tradeability scorecard")
    table("Screen — book & regime vs signal & result", 24, 10,
          cols=[("liquiditybot_regime_spread_bps", "Spread bps", "short", 1),
                ("liquiditybot_regime_vol_pct", "Vol %", "percent", 1),
                ("liquiditybot_regime_spoof", "Spoof", "short", 2),
                ("liquiditybot_manip_suspect", "Manip", "short", 2),
                ("liquiditybot_signal_confidence", "Confidence", "short", 2),
                ("liquiditybot_signal_concentration", "Concentration", "short", 2),
                ("liquiditybot_signal_urgency", "Urgency", "short", 2),
                ("liquiditybot_perf_asset_win_rate", "Win rate", "percentunit", 2),
                ("liquiditybot_perf_asset_net_usd", "Net $", "currencyUSD", 2),
                ("liquiditybot_perf_asset_trades", "Trades", "short", 0)],
          label_keys=["asset"], sort="Net $",
          desc="Screen an asset in one row: a tight spread + low spoof/manip + "
               "high concentration + positive net is a tradeable edge; wide "
               "spread + high spoof + diffuse signal is a book to avoid.")

    row("§3 · Regime context & adverse selection")
    table("Live regime label", 12, 7,
          cols=[("liquiditybot_regime_momentum", "Momentum", "short", 2),
                ("liquiditybot_regime_vol_pct", "Vol %", "percent", 1),
                ("liquiditybot_regime_spread_bps", "Spread bps", "short", 1),
                ("liquiditybot_regime_basis_bps", "Basis bps", "short", 1)],
          label_keys=["asset"], sort="Vol %",
          desc="Per-asset regime numerics driving liquidity/vol classification.")
    table("Adverse selection (mark-out)", 12, 7,
          cols=[("liquiditybot_markout_bps", "Mark-out bps", "short", 2)],
          label_keys=["asset", "horizon_sec"], sort="Mark-out bps",
          desc="Post-fill drift; persistently negative on an asset = its book "
               "picks us off — screen it down.")


# ============================ assemble =====================================
_TAGS = ["liquiditybot", "trading", "paper-trading"]


def _board(uid, title, desc, author, extra_tag):
    panels.clear()
    _cur.update(x=0, y=0, row_h=0)
    _pid["n"] = 0
    author()
    return {"uid": uid, "title": title, "description": desc,
            "tags": _TAGS + [extra_tag], "schemaVersion": 39, "editable": True,
            "timezone": "browser", "refresh": "30s",
            "time": {"from": "now-24h", "to": "now"},
            "templating": {"list": []}, "annotations": {"list": []},
            "panels": list(panels)}


DASHBOARDS = {
    "liquiditybot_command.json": _board(
        "liquiditybot-trading", "liquiditybot — command",
        "Condensed logistical command board: health, learning brain, positions, "
        "per-asset comparison, risk.", _author_command, "command"),
    "liquiditybot_execution.json": _board(
        "liquiditybot-exec", "liquiditybot — models · inventory · execution",
        "Decision model health, inventory/positioning & heat, and execution "
        "fill quality (maker/taker, slippage, mark-out).", _author_execution,
        "execution"),
    "liquiditybot_problem_solution.json": _board(
        "liquiditybot-problem-solution", "liquiditybot — problem / solution",
        "Every failure mode as a PROBLEM whose panel shows the live detector "
        "and names the SOLUTION mechanism already handling it.",
        _author_problem, "diagnostics"),
    "liquiditybot_screening.json": _board(
        "liquiditybot-screening", "liquiditybot — asset screening",
        "Asset screening: skimmer candidate ranks + a per-asset tradeability "
        "scorecard (book, regime, signal quality, result).", _author_screening,
        "screening"),
}

OUT_DIR = Path(__file__).resolve().parents[1] / "docs" / "grafana"

if __name__ == "__main__":
    for fname, d in DASHBOARDS.items():
        out = OUT_DIR / fname
        out.write_text(json.dumps(d, indent=2, ensure_ascii=False),
                       encoding="utf-8")
        print(f"wrote {out} — {len(d['panels'])} panels ({d['title']})")
