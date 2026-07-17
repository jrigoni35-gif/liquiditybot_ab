"""scripts/build_trading_dashboard.py — generator for the professional trading
dashboard (docs/grafana/liquiditybot_trading.json).

THIS GENERATOR IS THE SOURCE OF TRUTH for that dashboard: edit sections here and
regenerate — never hand-edit the JSON (unlike the incidents dashboard, which is
hand-maintained). Same output file + stable uid 'liquiditybot-trading' means git
replaces and a Grafana re-import overwrites in place — no duplicates.

Sections: §1 Account & Performance · §2 Live Positions · §3 Execution Quality.
Every target must reference a metric scripts/gc_pusher.py actually emits;
tests/test_trading_dashboard.py enforces that (no dead panels).
"""
import json
from pathlib import Path

DS = {"type": "prometheus", "uid": "grafanacloud-prom"}
JOB = '{job="liquiditybot"}'
panels = []


def M(metric, suffix=""):
    """Complete PromQL for a single-series stat: max() collapses instance labels."""
    return f"max({metric}{JOB}){suffix}"


def _t(expr, ref="A", instant=True, legend=None, fmt=None):
    t = {"refId": ref, "datasource": DS, "expr": expr, "instant": instant}
    if legend is not None:
        t["legendFormat"] = legend
    if fmt:
        t["format"] = fmt
    return t


def row(pid, title, y):
    panels.append({"id": pid, "type": "row", "title": title, "collapsed": False,
                   "gridPos": {"h": 1, "w": 24, "x": 0, "y": y}, "panels": []})


def stat(pid, title, expr, x, y, w, h, unit="", decimals=2, desc="",
         steps=None, mode="value", mappings=None, text_mode="auto",
         legend=None):
    fld = {"unit": unit, "decimals": decimals,
           "thresholds": {"mode": "absolute",
                          "steps": steps or [{"color": "text", "value": None}]}}
    if mappings:
        fld["mappings"] = mappings
    panels.append({
        "id": pid, "type": "stat", "title": title, "description": desc,
        "datasource": DS, "gridPos": {"h": h, "w": w, "x": x, "y": y},
        "fieldConfig": {"defaults": fld, "overrides": []},
        "options": {"colorMode": mode, "graphMode": "area", "justifyMode": "auto",
                    "textMode": text_mode, "wideLayout": True,
                    "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False}},
        "targets": [_t(expr, legend=legend) if legend else _t(expr)]})


def gauge(pid, title, expr, x, y, w, h, mx=35.0, steps=None, desc=""):
    panels.append({
        "id": pid, "type": "gauge", "title": title, "description": desc,
        "datasource": DS, "gridPos": {"h": h, "w": w, "x": x, "y": y},
        "fieldConfig": {"defaults": {"unit": "percent", "min": 0, "max": mx, "decimals": 1,
            "thresholds": {"mode": "absolute", "steps": steps or [
                {"color": "green", "value": None}, {"color": "yellow", "value": mx * 0.7},
                {"color": "red", "value": mx * 0.9}]}}, "overrides": []},
        "options": {"showThresholdLabels": False, "showThresholdMarkers": True,
                    "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False}},
        "targets": [_t(expr)]})


def timeseries(pid, title, expr, x, y, w, h, unit="", desc="", legend="value"):
    panels.append({
        "id": pid, "type": "timeseries", "title": title, "description": desc,
        "datasource": DS, "gridPos": {"h": h, "w": w, "x": x, "y": y},
        "fieldConfig": {"defaults": {"unit": unit, "custom": {
            "drawStyle": "line", "lineInterpolation": "linear", "lineWidth": 2,
            "fillOpacity": 10, "gradientMode": "opacity", "showPoints": "never",
            "spanNulls": True, "axisPlacement": "auto",
            "scaleDistribution": {"type": "linear"}},
            "color": {"mode": "palette-classic"}}, "overrides": []},
        "options": {"legend": {"displayMode": "hidden", "placement": "bottom"},
                    "tooltip": {"mode": "single", "sort": "none"}},
        "targets": [_t(expr, instant=False, legend=legend)]})


def table(pid, title, x, y, w, h, cols, label_keys, desc=""):
    """cols: (metric, display_name, unit, decimals). Joined by label_keys."""
    refs = "ABCDEFGHIJKLMNOP"
    targets, rename, order, overrides = [], {}, {}, []
    for k in label_keys:
        order[k] = len(order)
    for i, (metric, name, unit, dec) in enumerate(cols):
        r = refs[i]
        targets.append(_t(f"{metric}{JOB}", ref=r, fmt="table"))
        rename[f"Value #{r}"] = name
        order[name] = len(order)
        overrides.append({"matcher": {"id": "byName", "options": name},
                          "properties": [{"id": "unit", "value": unit},
                                         {"id": "decimals", "value": dec}]})
    panels.append({
        "id": pid, "type": "table", "title": title, "description": desc,
        "datasource": DS, "gridPos": {"h": h, "w": w, "x": x, "y": y},
        "fieldConfig": {"defaults": {"custom": {"align": "auto", "filterable": True}},
                        "overrides": overrides},
        "options": {"showHeader": True, "cellHeight": "sm",
                    "sortBy": [{"displayName": label_keys[0], "desc": False}]},
        "targets": targets,
        "transformations": [
            {"id": "merge", "options": {}},
            {"id": "organize", "options": {
                "excludeByName": {"Time": True, "job": True, "instance": True,
                                  "__name__": True},
                "renameByName": rename, "indexByName": order}}]})


GRN = [{"color": "text", "value": None}]
PNL = [{"color": "red", "value": None}, {"color": "green", "value": 0}]

# ---------------- §1 · Account & Performance ----------------
row(1, "§1 · Account & Performance", 0)
stat(10, "Equity", M("liquiditybot_equity"), 0, 1, 5, 4, unit="currencyUSD",
     desc="Live account equity (cash + open uPnL).", steps=GRN)
stat(11, "P&L today", M("liquiditybot_daily_pnl"), 5, 1, 5, 4, unit="currencyUSD",
     steps=PNL, desc="Realized P&L since UTC midnight.")
stat(12, "Realized (total)", M("liquiditybot_realized_total"), 10, 1, 5, 4,
     unit="currencyUSD", steps=PNL, desc="Cumulative realized P&L since inception.")
stat(13, "Open uPnL", M("liquiditybot_open_upnl_usd"), 15, 1, 5, 4,
     unit="currencyUSD", steps=PNL, desc="Unrealized P&L across open positions.")
stat(14, "Drawdown", M("liquiditybot_drawdown_pct"), 20, 1, 4, 4, unit="percent",
     desc="Peak-to-now drawdown; 15% is the hard stop.",
     steps=[{"color": "green", "value": None}, {"color": "yellow", "value": 8},
            {"color": "red", "value": 12}])

timeseries(20, "Equity curve", M("liquiditybot_equity"), 0, 5, 16, 8,
           unit="currencyUSD", legend="equity", desc="Account equity over time.")
PF = [{"color": "red", "value": None}, {"color": "yellow", "value": 1.0},
      {"color": "green", "value": 1.5}]
stat(21, "Win rate", M("liquiditybot_perf_win_rate", "*100"), 16, 5, 4, 4,
     unit="percent", decimals=1, desc="Rolling win rate (closed trades).",
     steps=[{"color": "red", "value": None}, {"color": "yellow", "value": 45},
            {"color": "green", "value": 55}])
stat(22, "Win rate (LCB)", M("liquiditybot_perf_win_rate_lcb", "*100"), 20, 5, 4, 4,
     unit="percent", decimals=1,
     desc="Wilson lower bound — the honest floor, not a lucky streak.", steps=GRN)
stat(23, "Profit factor", M("liquiditybot_perf_profit_factor"), 16, 9, 4, 4,
     steps=PF, desc="Gross profit / gross loss. >1 is net-positive.")
stat(24, "Expectancy (R)", M("liquiditybot_perf_expectancy_r"), 20, 9, 4, 4,
     steps=PNL, desc="Average trade in R-multiples (realized ÷ stop-risk).")

stat(30, "Sharpe", M("liquiditybot_perf_sharpe"), 0, 13, 4, 4, steps=PNL,
     desc="Per-trade Sharpe (mean ÷ stdev of trade returns).")
stat(31, "Sortino", M("liquiditybot_perf_sortino"), 4, 13, 4, 4, steps=PNL,
     desc="Per-trade Sortino (downside deviation only).")
stat(32, "Expectancy ($)", M("liquiditybot_perf_expectancy_usd"), 8, 13, 4, 4,
     unit="currencyUSD", steps=PNL, desc="Average $ per closed trade.")
stat(33, "Payoff ratio", M("liquiditybot_perf_payoff_ratio"), 12, 13, 4, 4,
     steps=GRN, desc="Avg win ÷ avg loss.")
stat(34, "Avg win", M("liquiditybot_perf_avg_win_usd"), 16, 13, 4, 4,
     unit="currencyUSD", steps=[{"color": "green", "value": None}], desc="Mean winning trade.")
stat(35, "Avg loss", M("liquiditybot_perf_avg_loss_usd"), 20, 13, 4, 4,
     unit="currencyUSD", steps=[{"color": "red", "value": None}], desc="Mean losing trade.")

stat(40, "Trades (window)", M("liquiditybot_perf_trades"), 0, 17, 4, 4, decimals=0,
     steps=GRN, desc="Closed trades in the rolling window.")
stat(41, "Net P&L (window)", M("liquiditybot_perf_net_usd"), 4, 17, 4, 4,
     unit="currencyUSD", steps=PNL, desc="Net realized across the window.")
stat(42, "Gross profit", M("liquiditybot_perf_gross_profit_usd"), 8, 17, 4, 4,
     unit="currencyUSD", steps=[{"color": "green", "value": None}])
stat(43, "Gross loss", M("liquiditybot_perf_gross_loss_usd"), 12, 17, 4, 4,
     unit="currencyUSD", steps=[{"color": "red", "value": None}])
stat(44, "Loss streak (now)", M("liquiditybot_perf_cur_loss_streak"), 16, 17, 4, 4,
     decimals=0, mode="background",
     desc="Consecutive losing trades right now — the per-asset circuit-breaker input.",
     steps=[{"color": "green", "value": None}, {"color": "yellow", "value": 3},
            {"color": "red", "value": 5}])
stat(45, "Loss streak (max)", M("liquiditybot_perf_max_loss_streak"), 20, 17, 4, 4,
     decimals=0, steps=GRN, desc="Worst losing streak in the window.")

# ---------------- §2 · Live Positions ----------------
row(2, "§2 · Live Positions", 21)
stat(50, "Open positions", M("liquiditybot_positions_open"), 0, 22, 6, 4, decimals=0,
     steps=GRN, desc="Open position count (max 5 concurrent).")
gauge(51, "Gross exposure", M("liquiditybot_gross_exposure_pct"), 6, 22, 6, 4, mx=35.0,
      desc="Gross notional as % of equity vs the 35% portfolio-heat cap.")
stat(52, "Open risk (to stops)", M("liquiditybot_open_risk_usd"), 12, 22, 6, 4,
     unit="currencyUSD", steps=GRN, desc="Total $ lost if every open stop filled now.")
stat(53, "Open uPnL", M("liquiditybot_open_upnl_usd"), 18, 22, 6, 4,
     unit="currencyUSD", steps=PNL, desc="Unrealized P&L, all positions.")

table(54, "Open positions (net per instrument)", 0, 26, 24, 8,
      cols=[("liquiditybot_position_notional_usd", "Notional $", "currencyUSD", 2),
            ("liquiditybot_position_upnl_usd", "uPnL $", "currencyUSD", 2),
            ("liquiditybot_position_upnl_pct", "uPnL %", "percent", 2),
            ("liquiditybot_position_r_multiple", "R", "", 2),
            ("liquiditybot_position_stop_dist_pct", "Stop dist %", "percent", 2),
            ("liquiditybot_position_tiers_fired", "Tiers", "", 0),
            ("liquiditybot_position_lots", "Lots", "", 0),
            ("liquiditybot_position_conviction", "Conviction", "", 2),
            ("liquiditybot_position_age_hours", "Age (h)", "", 1)],
      label_keys=["symbol", "side"],
      desc="Live book, netted per instrument. Instant query — closed positions drop out.")

table(55, "Per-asset performance", 0, 34, 24, 8,
      cols=[("liquiditybot_perf_asset_trades", "Trades", "", 0),
            ("liquiditybot_perf_asset_win_rate", "Win rate", "percentunit", 2),
            ("liquiditybot_perf_asset_profit_factor", "Profit factor", "", 2),
            ("liquiditybot_perf_asset_expectancy_usd", "Expectancy $", "currencyUSD", 3),
            ("liquiditybot_perf_asset_net_usd", "Net $", "currencyUSD", 2),
            ("liquiditybot_perf_asset_cur_loss_streak", "Streak (now)", "", 0),
            ("liquiditybot_perf_asset_max_loss_streak", "Streak (max)", "", 0)],
      label_keys=["asset"],
      desc="Per-asset edge — the ranking basis for the coming per-asset circuit breaker.")

# ---------------- §3 · Execution Quality ----------------
row(3, "§3 · Execution Quality", 42)
# multi-series markout panel needs a visible legend (one series per
# asset+horizon), so it doesn't use the single-series helper.
panels.append({
    "id": 60, "type": "timeseries", "title": "Post-fill mark-out (bps)",
    "description": ("Mark move vs our fill, per asset and horizon. Negative = "
                    "adverse selection (we get filled right before price moves "
                    "against us — 'getting scalped'). Persistent negatives at "
                    "5s mean entries are being picked off."),
    "datasource": DS, "gridPos": {"h": 8, "w": 12, "x": 0, "y": 43},
    "fieldConfig": {"defaults": {"unit": "none", "decimals": 1, "custom": {
        "drawStyle": "line", "lineInterpolation": "linear", "lineWidth": 1,
        "fillOpacity": 8, "gradientMode": "opacity", "showPoints": "never",
        "spanNulls": True, "axisPlacement": "auto",
        "scaleDistribution": {"type": "linear"}},
        "color": {"mode": "palette-classic"}}, "overrides": []},
    "options": {"legend": {"displayMode": "table", "placement": "right",
                           "calcs": ["last", "mean"]},
                "tooltip": {"mode": "multi", "sort": "desc"}},
    "targets": [_t('liquiditybot_markout_bps' + JOB, instant=False,
                   legend="{{asset}} @{{horizon_sec}}s")]})
stat(61, "Maker fill share", M("liquiditybot_order_maker_share", "*100"),
     12, 43, 4, 4, unit="percent", decimals=0,
     desc="Share of fills that rested as maker (earned the spread) vs crossed "
          "as taker (paid it). Higher = cheaper execution.",
     steps=[{"color": "red", "value": None}, {"color": "yellow", "value": 40},
            {"color": "green", "value": 70}])
stat(62, "Avg slippage", M("liquiditybot_order_avg_slip_bps"), 16, 43, 4, 4,
     decimals=1, desc="Rolling mean signed slippage vs the price we asked "
     "(bps). Positive = adverse, negative = price improvement.",
     steps=[{"color": "green", "value": None}, {"color": "yellow", "value": 5},
            {"color": "red", "value": 15}])
stat(63, "Worst slippage", M("liquiditybot_order_worst_slip_bps"), 20, 43, 4, 4,
     decimals=1, desc="Worst single-fill slippage in the rolling window (bps).",
     steps=[{"color": "green", "value": None}, {"color": "yellow", "value": 10},
            {"color": "red", "value": 30}])
stat(64, "Venue RTT", M("liquiditybot_order_latency_ms"), 12, 47, 4, 4,
     unit="ms", decimals=0, desc="Order-path round-trip latency (EWMA).",
     steps=[{"color": "green", "value": None}, {"color": "yellow", "value": 800},
            {"color": "red", "value": 2000}])
stat(65, "Venue rejects", M("liquiditybot_order_venue_rejects"), 16, 47, 4, 4,
     decimals=0, desc="Orders the venue refused (OM-021). Rising = a submit "
     "path problem.", steps=[{"color": "green", "value": None},
                             {"color": "red", "value": 1}])
stat(66, "Dead-man failures", M("liquiditybot_order_deadman_failures"),
     20, 47, 4, 4, decimals=0,
     desc="Dead-man refresh failures (OM-050); >=3 escalates.",
     steps=[{"color": "green", "value": None}, {"color": "yellow", "value": 1},
            {"color": "red", "value": 3}])
stat(67, "Fees paid (total)", M("liquiditybot_fees_total"), 0, 51, 6, 4,
     unit="currencyUSD", steps=GRN, desc="Cumulative fees since inception.")
stat(68, "Maker notional", M("liquiditybot_order_maker_notional_usd"),
     6, 51, 6, 4, unit="currencyUSD", steps=GRN,
     desc="Notional filled passively (spread earned).")
stat(69, "Taker notional", M("liquiditybot_order_taker_notional_usd"),
     12, 51, 6, 4, unit="currencyUSD", steps=GRN,
     desc="Notional filled crossing (spread paid).")
stat(70, "Fees vs gross profit",
     f"100 * max(liquiditybot_fees_total{JOB}) / "
     f"clamp_min(max(liquiditybot_perf_gross_profit_usd{JOB}), 0.001)",
     18, 51, 6, 4, unit="percent", decimals=0,
     desc="Fees as % of gross profit — how much of the edge execution costs "
          "eat. Above 100% = trading for the venue, not for you.",
     steps=[{"color": "green", "value": None}, {"color": "yellow", "value": 50},
            {"color": "red", "value": 100}])

# ---------------- §4 · Signal & Edge ----------------
def ts_multi(pid, title, expr, x, y, w, h, legend, unit="", desc="",
             mn=None, mx=None, extra=None):
    """Multi-series timeseries with a visible right-hand legend table.
    `extra`: optional [(expr, legend), ...] additional targets."""
    fld = {"unit": unit, "decimals": 2, "custom": {
        "drawStyle": "line", "lineInterpolation": "linear", "lineWidth": 1,
        "fillOpacity": 6, "gradientMode": "opacity", "showPoints": "never",
        "spanNulls": True, "axisPlacement": "auto",
        "scaleDistribution": {"type": "linear"}},
        "color": {"mode": "palette-classic"}}
    if mn is not None:
        fld["min"] = mn
    if mx is not None:
        fld["max"] = mx
    panels.append({
        "id": pid, "type": "timeseries", "title": title, "description": desc,
        "datasource": DS, "gridPos": {"h": h, "w": w, "x": x, "y": y},
        "fieldConfig": {"defaults": fld, "overrides": []},
        "options": {"legend": {"displayMode": "table", "placement": "right",
                               "calcs": ["lastNotNull"]},
                    "tooltip": {"mode": "multi", "sort": "desc"}},
        "targets": [_t(expr, instant=False, legend=legend)] +
                   [_t(e, instant=False, legend=lg, ref=chr(66 + i))
                    for i, (e, lg) in enumerate(extra or [])]})


def bargauge(pid, title, expr, x, y, w, h, legend, unit="percent", mx=100,
             desc="", steps=None):
    panels.append({
        "id": pid, "type": "bargauge", "title": title, "description": desc,
        "datasource": DS, "gridPos": {"h": h, "w": w, "x": x, "y": y},
        "fieldConfig": {"defaults": {"unit": unit, "min": 0, "max": mx,
            "decimals": 1, "thresholds": {"mode": "absolute", "steps": steps or [
                {"color": "blue", "value": None}]}}, "overrides": []},
        "options": {"orientation": "horizontal", "displayMode": "gradient",
                    "showUnfilled": True, "valueMode": "color",
                    "reduceOptions": {"calcs": ["lastNotNull"], "fields": "",
                                      "values": False}},
        "targets": [_t(expr, instant=False, legend=legend)]})


row(4, "§4 · Signal & Edge", 55)
ts_multi(80, "Signal confidence (per asset)",
         f"max by (asset) (liquiditybot_signal_confidence{JOB})",
         0, 56, 12, 8, "{{asset}}", mn=0, mx=1,
         desc="Meta-model p(win) per asset — the continuous conviction line.")
ts_multi(81, "Signal urgency (per asset)",
         f"max by (asset) (liquiditybot_signal_urgency{JOB})",
         12, 56, 12, 8, "{{asset}}", mn=0, mx=1,
         desc="Gated trigger: EXACTLY 0 unless all confirmations align, then "
              "0.30-1.00 scaled by burst/freshness. Spiky-to-zero is the "
              "DESIGN — a smooth line here would mean overtrading.")
bargauge(82, "Gate pass-rate (24h)",
         f"100 * avg by (gate) (avg_over_time(liquiditybot_signal_gate_passed{JOB}[24h]))",
         0, 64, 8, 8, "{{gate}}",
         desc="Per-gate pass share across assets, last 24h. The LOWEST bar is "
              "the gate blocking most entries.",
         steps=[{"color": "red", "value": None}, {"color": "yellow", "value": 40},
                {"color": "green", "value": 70}])
bargauge(83, "Learned gate weights",
         f"max by (gate) (liquiditybot_gate_weight{JOB})",
         8, 64, 8, 8, "{{gate}}", unit="none", mx=1.3,
         desc="GateStats Wilson-LCB learned weight per gate (1.0 = neutral). "
              "Above 1 = predictive of wins, below = drag.",
         steps=[{"color": "red", "value": None}, {"color": "yellow", "value": 0.9},
                {"color": "green", "value": 1.0}])
bargauge(84, "Confirmed-rate (24h)",
         f"100 * avg by (asset) (avg_over_time(liquiditybot_signal_confirmed{JOB}[24h]))",
         16, 64, 8, 8, "{{asset}}",
         desc="Share of time each asset's signal was fully confirmed, last 24h.",
         steps=[{"color": "blue", "value": None}])
ts_multi(85, "Manipulation suspicion (per asset)",
         f"max by (asset) (liquiditybot_manip_suspect{JOB})",
         0, 72, 8, 8, "{{asset}}", mn=0, mx=1,
         desc="MAX of spoof / imbalance-whiplash / cross-venue divergence. "
              "Downsizes entries from 0.6, vetoes at 0.9 (SZ-045).")
ts_multi(86, "Entry decision codes (PT/SZ)",
         f"max by (code) (liquiditybot_code_count_detail{JOB})",
         8, 72, 8, 8, "{{code}}", unit="none",
         desc="Cumulative entry-decision reason codes: PT-041 edge/cost reject, "
              "PT-050 exploration bypass, SZ-045 manip veto, SZ-000 approved… "
              "Rising slope = that disposition is firing.")
panels.append({
    "id": 87, "type": "table", "title": "Regime (current)",
    "description": "Live regime read per asset: macro trend state, volatility "
                   "band, liquidity band. Instant — stale label-sets drop out.",
    "datasource": DS, "gridPos": {"h": 8, "w": 8, "x": 16, "y": 72},
    "fieldConfig": {"defaults": {"custom": {"align": "auto",
                                            "filterable": True}},
                    "overrides": []},
    "options": {"showHeader": True, "cellHeight": "sm",
                "sortBy": [{"displayName": "asset", "desc": False}]},
    "targets": [_t(f"liquiditybot_regime_info{JOB}", fmt="table")],
    "transformations": [
        {"id": "organize", "options": {
            "excludeByName": {"Time": True, "job": True, "instance": True,
                              "__name__": True, "Value": True},
            "renameByName": {}, "indexByName": {"asset": 0, "macro": 1,
                                                "vol": 2, "liq": 3}}}]})
ts_multi(88, "Momentum (per asset)",
         f"max by (asset) (liquiditybot_regime_momentum{JOB})",
         0, 80, 8, 8, "{{asset}}", unit="none",
         desc="Macro momentum score; sign gates counter-trend entries.")
ts_multi(89, "Volatility percentile (per asset)",
         f"max by (asset) (liquiditybot_regime_vol_pct{JOB})",
         8, 80, 8, 8, "{{asset}}", mn=0, mx=100,
         desc="Where current vol sits vs history — scales tier targets, "
              "trails and stops.")
ts_multi(90, "Spread (per asset, bps)",
         f"max by (asset) (liquiditybot_regime_spread_bps{JOB})",
         16, 80, 8, 8, "{{asset}}", unit="none",
         desc="Live spread cost per asset — the floor every edge must clear.")

# ---------------- §5 · Model Health & Learning ----------------
row(5, "§5 · Model Health & Learning", 88)
ts_multi(100, "Model Brier vs baseline",
         f"max(liquiditybot_ml_brier{JOB})", 0, 89, 12, 8, "model brier",
         desc="OUTCOME health: rolling Brier of the DEPLOYED model vs the "
              "base-rate baseline on the last judged trades (lower=better). "
              "Model ABOVE baseline = worse than a naive guess; the governor "
              "kills at baseline+0.03. Absent until >=15 trades judgeable.",
         extra=[(f"max(liquiditybot_ml_baseline_brier{JOB})",
                 "baseline (base-rate)"),
                (f"max(liquiditybot_ml_champion_brier{JOB})",
                 "champion (deploy bar)")])
ts_multi(101, "Promised vs delivered win-rate",
         f"max(liquiditybot_ml_avg_p{JOB})", 12, 89, 12, 8,
         "promised (avg p)", mn=0, mx=1,
         desc="Calibration in one picture: the model's average promised "
              "p(win) vs the realized hit rate and its Wilson lower bound on "
              "the same judged trades. Promised far above the LCB = the model "
              "is overselling its edge.",
         extra=[(f"max(liquiditybot_ml_hit_rate{JOB})", "delivered (hit rate)"),
                (f"max(liquiditybot_ml_hit_rate_lcb{JOB})",
                 "delivered floor (Wilson LCB)")])
stat(102, "Governor", M("liquiditybot_monitor_level"), 0, 97, 4, 4,
     decimals=0, mode="background",
     desc="ML governor kill-switch: OK / DEGRADED (shrunk sizing) / KILLED "
          "(prior only). Level 2 auto-requests a retrain.",
     steps=[{"color": "green", "value": None}, {"color": "yellow", "value": 1},
            {"color": "red", "value": 2}],
     mappings=[{"type": "value", "options": {
         "0": {"text": "OK", "index": 0},
         "1": {"text": "DEGRADED", "index": 1},
         "2": {"text": "KILLED", "index": 2}}}])
stat(103, "Model in use", M("liquiditybot_ml_use_model"), 4, 97, 4, 4,
     decimals=0, mode="background",
     desc="Whether inference uses the trained model (vs the cold-start prior).",
     steps=[{"color": "red", "value": None}, {"color": "green", "value": 1}],
     mappings=[{"type": "value", "options": {
         "0": {"text": "PRIOR", "index": 0},
         "1": {"text": "MODEL", "index": 1}}}])
stat(104, "Kelly multiplier", M("liquiditybot_ml_kelly_mult"), 8, 97, 4, 4,
     decimals=2, desc="Governor sizing throttle applied to Kelly (1.0 = full).",
     steps=[{"color": "red", "value": None}, {"color": "yellow", "value": 0.5},
            {"color": "green", "value": 0.99}])
stat(105, "Prob shrinkage", M("liquiditybot_ml_shrinkage"), 12, 97, 4, 4,
     decimals=2, desc="How hard p(win) is pulled toward 0.5 before sizing "
     "(higher = less trust in the model).",
     steps=[{"color": "green", "value": None}, {"color": "yellow", "value": 0.5},
            {"color": "red", "value": 0.7}])
stat(106, "Stop widen", M("liquiditybot_ml_stop_widen"), 16, 97, 4, 4,
     decimals=2, desc="Whipsaw governor: stops widened by this factor when "
     "stop-outs keep recovering past entry.",
     steps=[{"color": "green", "value": None}, {"color": "yellow", "value": 1.2}])
stat(107, "Calibration gap", M("liquiditybot_ml_calibration_gap"), 20, 97, 4, 4,
     decimals=3, desc="Mean |promised p - realized rate| across probability "
     "bins; the governor degrades past 0.15.",
     steps=[{"color": "green", "value": None}, {"color": "yellow", "value": 0.10},
            {"color": "red", "value": 0.15}])
ts_multi(108, "Feature drift share",
         f"max(liquiditybot_ml_drift_share{JOB})", 0, 101, 8, 8, "drift share",
         mn=0, mx=1,
         desc="Fraction of MARKET features past PSI 0.25 (clock features "
              "excluded). 0.30 = the retrain-vote line; transient blips "
              "self-heal via auto-retrain.")
ts_multi(109, "Learning velocity (labels/24h)",
         f"max(liquiditybot_ml_history_rows{JOB}) - "
         f"max(liquiditybot_ml_history_rows{JOB} offset 24h)",
         8, 101, 8, 8, "labels gained, 24h", unit="none",
         desc="Training rows added in the last 24h — the model's food supply. "
              "Zero for a sustained stretch = learning starved (check "
              "exploration + min-ticket flow).")
ts_multi(110, "Labels by source",
         f"max by (source) (liquiditybot_ml_labels{JOB})", 16, 101, 8, 8,
         "{{source}}", unit="none",
         desc="Cumulative labels: LIVE = real fills (ground truth), "
              "CANDIDATE = triple-barrier proxy labels. Live is scarce and "
              "precious; candidates keep the model fed between fills.")
stat(111, "Retrain requested", M("liquiditybot_ml_retrain_flag"), 0, 109, 4, 4,
     decimals=0, mode="background",
     desc="Retrain flag currently raised (drift/decay asked for a refit; "
          "auto-retrain services it next slow cycle).",
     steps=[{"color": "green", "value": None}, {"color": "yellow", "value": 1}],
     mappings=[{"type": "value", "options": {
         "0": {"text": "no", "index": 0},
         "1": {"text": "REQUESTED", "index": 1}}}])
stat(112, "Retrain failures", M("liquiditybot_ml_retrain_failures"),
     4, 109, 4, 4, decimals=0,
     desc="Auto-retrain attempts that threw. Rising = stale champion kept.",
     steps=[{"color": "green", "value": None}, {"color": "yellow", "value": 1},
            {"color": "red", "value": 5}])
stat(113, "Open candidates", M("liquiditybot_ml_open_candidates"), 8, 109, 4, 4,
     decimals=0, desc="Shadow entries awaiting a triple-barrier label.",
     steps=[{"color": "text", "value": None}])
stat(114, "Pending labels", M("liquiditybot_ml_pending_labels"), 12, 109, 4, 4,
     decimals=0, desc="Real positions open, feature rows awaiting their "
     "close label.", steps=[{"color": "text", "value": None}])
stat(115, "Deployed model",
     f"max by (kind) (liquiditybot_ml_model_info{JOB})", 16, 109, 8, 4,
     decimals=0, text_mode="name", legend="{{kind}}",
     desc="Current rung on the simplicity ladder (logreg -> gbt -> blend -> "
          "mlp). The walk-forward selector must EARN each step up.",
     steps=[{"color": "blue", "value": None}])

dash = {
    "uid": "liquiditybot-trading",
    "title": "liquiditybot — trading",
    "description": "Account performance and live positions for the liquiditybot "
                   "paper-trading engine. Complementary to 'control' and 'incidents'.",
    "tags": ["liquiditybot", "trading", "performance", "positions", "paper-trading"],
    "schemaVersion": 39, "editable": True, "timezone": "browser",
    "refresh": "30s", "time": {"from": "now-24h", "to": "now"},
    "templating": {"list": []}, "annotations": {"list": []},
    "panels": panels,
}
OUT = Path(__file__).resolve().parents[1] / "docs" / "grafana" / \
    "liquiditybot_trading.json"

if __name__ == "__main__":
    OUT.write_text(json.dumps(dash, indent=2, ensure_ascii=False),
                   encoding="utf-8")
    print(f"wrote {OUT} — {len(panels)} panels")
