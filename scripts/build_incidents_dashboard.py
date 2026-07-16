"""
scripts/build_incidents_dashboard.py — generate docs/grafana/liquiditybot_incidents.json.

The incidents/faults dashboard, COMPLEMENTARY to liquiditybot_dashboard.json
(the control view): zero equity/learning overlap, faults only. Every panel
reads a metric gc_pusher.py exports (the fault-observability surface), so it is
data-backed, not "No data". Distinct identity so it never collides with the
control dashboard: uid=liquiditybot-incidents, precise tags. Regenerate with
`python scripts/build_incidents_dashboard.py`; the emitted JSON is what you
import into Grafana (Dashboards -> New -> Import -> upload JSON).
"""
import json
from pathlib import Path

PROM = {"type": "prometheus", "uid": "grafanacloud-prom"}
LOKI = {"type": "loki", "uid": "grafanacloud-logs"}
JOB = 'job="liquiditybot"'

_id = [0]


def _next_id() -> int:
    _id[0] += 1
    return _id[0]


def _thresholds(steps):
    return {"mode": "absolute",
            "steps": [{"color": c, "value": v} for v, c in steps]}


def _mappings(pairs):
    return [{"type": "value",
             "options": {str(k): {"text": t, "color": c, "index": i}}}
            for i, (k, t, c) in enumerate(pairs)]


def stat(title, expr, *, unit="", decimals=0, steps=(("null", "green"),),
         mappings=None, desc="", w=4, h=4, x=0, y=0, color_bg=False):
    d = {"unit": unit, "decimals": decimals, "thresholds": _thresholds(steps)}
    if mappings:
        d["mappings"] = mappings
    return {
        "id": _next_id(), "type": "stat", "title": title, "description": desc,
        "datasource": PROM, "gridPos": {"h": h, "w": w, "x": x, "y": y},
        "fieldConfig": {"defaults": d, "overrides": []},
        "options": {"colorMode": "background" if color_bg else "value",
                    "graphMode": "area", "justifyMode": "auto",
                    "textMode": "auto", "wideLayout": True,
                    "reduceOptions": {"calcs": ["lastNotNull"], "fields": "",
                                      "values": False}},
        "targets": [{"refId": "A", "datasource": PROM, "expr": expr,
                     "instant": True}],
    }


def timeseries(title, series, *, unit="", desc="", w=12, h=8, x=0, y=0,
               fill=10, stack=False):
    targets = [{"refId": chr(65 + i), "datasource": PROM, "expr": e,
                "legendFormat": lf} for i, (e, lf) in enumerate(series)]
    custom = {"drawStyle": "line", "lineInterpolation": "linear",
              "lineWidth": 1, "fillOpacity": fill, "gradientMode": "opacity",
              "showPoints": "never", "pointSize": 5, "spanNulls": True,
              "axisPlacement": "auto", "scaleDistribution": {"type": "linear"}}
    if stack:
        custom["stacking"] = {"mode": "normal", "group": "A"}
    return {
        "id": _next_id(), "type": "timeseries", "title": title,
        "description": desc, "datasource": PROM,
        "gridPos": {"h": h, "w": w, "x": x, "y": y},
        "fieldConfig": {"defaults": {"unit": unit, "custom": custom,
                                     "color": {"mode": "palette-classic"}},
                        "overrides": []},
        "options": {"legend": {"displayMode": "table", "placement": "right",
                               "calcs": ["last", "max"]},
                    "tooltip": {"mode": "multi", "sort": "desc"}},
        "targets": targets,
    }


def table(title, expr, legend, *, desc="", w=12, h=8, x=0, y=0):
    return {
        "id": _next_id(), "type": "table", "title": title, "description": desc,
        "datasource": PROM, "gridPos": {"h": h, "w": w, "x": x, "y": y},
        "fieldConfig": {"defaults": {"custom": {"align": "auto",
                                                "filterable": True}},
                        "overrides": []},
        "options": {"showHeader": True,
                    "sortBy": [{"displayName": "Value", "desc": True}]},
        "targets": [{"refId": "A", "datasource": PROM, "expr": expr,
                     "legendFormat": legend, "instant": True, "format": "table"}],
    }


def logs(title, expr, *, w=24, h=10, x=0, y=0):
    return {
        "id": _next_id(), "type": "logs", "title": title, "datasource": LOKI,
        "gridPos": {"h": h, "w": w, "x": x, "y": y},
        "options": {"showTime": True, "wrapLogMessage": True,
                    "dedupStrategy": "none", "enableLogDetails": True,
                    "sortOrder": "Descending"},
        "targets": [{"refId": "A", "datasource": LOKI, "expr": expr,
                     "queryType": "range"}],
    }


def row(title, y):
    return {"id": _next_id(), "type": "row", "title": title, "collapsed": False,
            "gridPos": {"h": 1, "w": 24, "x": 0, "y": y}, "panels": []}


def M(name, fn="max"):
    return f'{fn}(liquiditybot_{name}{{{JOB}}})'


OK_BAD = _mappings([(0, "OK", "green"), (1, "FAULT", "red")])
UP_DOWN = _mappings([(1, "UP", "green"), (0, "DOWN", "red")])
ON_OFF = _mappings([(1, "ENABLED", "green"), (0, "BLOCKED", "red")])
YES_NO = _mappings([(0, "no", "green"), (1, "YES", "red")])


def build():
    panels = []
    y = 0

    # ---- Row 1: health at a glance -----------------------------------
    panels.append(row("Health at a glance", y))
    y += 1
    panels += [
        stat("Runner", M("running"), steps=(("null", "red"), (1, "green")),
             mappings=UP_DOWN, color_bg=True, desc="1 = loop RUNNING", x=0, y=y),
        stat("Kill-switch level", M("monitor_level"),
             steps=(("null", "green"), (1, "yellow"), (2, "red")), color_bg=True,
             desc="ML governor: 0 ok / 1 degraded / 2 model killed", x=4, y=y),
        stat("Entries", M("entries_enabled"),
             steps=(("null", "red"), (1, "green")), mappings=ON_OFF,
             color_bg=True, desc="new-risk gate", x=8, y=y),
        stat("Halted", M("halted"), steps=(("null", "green"), (1, "red")),
             mappings=YES_NO, color_bg=True, desc="capital hard-stop", x=12, y=y),
        stat("Firewall fault", M("firewall_fault"),
             steps=(("null", "green"), (1, "red")), mappings=OK_BAD,
             color_bg=True, desc="15c3-5 screen latched a fault", x=16, y=y),
        stat("Status age", M("status_age_sec"), unit="s",
             steps=(("null", "green"), (90, "yellow"), (180, "red")),
             desc="freshness of status.json; climbs if the runner freezes",
             x=20, y=y),
    ]
    y += 4

    # ---- Row 2: feeds & connectivity ---------------------------------
    panels.append(row("Feeds & connectivity", y))
    y += 1
    panels += [
        stat("Kraken WS", M("ws_kraken_connected"),
             steps=(("null", "red"), (1, "green")), mappings=UP_DOWN,
             color_bg=True, desc="live book stream (REST fallback if down)",
             x=0, y=y),
        stat("WS reconnects", M("ws_kraken_reconnects"),
             steps=(("null", "green"), (5, "yellow"), (25, "red")),
             desc="cumulative; a rising count = flapping feed", x=4, y=y),
        stat("moomoo", M("moomoo_available"),
             steps=(("null", "red"), (1, "green")), mappings=UP_DOWN,
             color_bg=True, x=8, y=y),
        stat("moomoo options", M("moomoo_options_available"),
             steps=(("null", "red"), (1, "green")), mappings=UP_DOWN,
             color_bg=True, x=12, y=y),
        stat("Marks age", M("marks_age_sec"), unit="s",
             steps=(("null", "green"), (10, "yellow"), (30, "red")),
             desc="oldest live mark; climbs the instant a price stops updating",
             x=16, y=y),
        stat("Feed latency", M("feed_latency_ms"), unit="ms",
             steps=(("null", "green"), (1500, "yellow"), (4000, "red")),
             x=20, y=y),
    ]
    y += 4

    # ---- Row 3: ML faults --------------------------------------------
    panels.append(row("ML faults (cumulative — rising = a subsystem dying)", y))
    y += 1
    panels += [
        timeseries("ML fault counters", [
            (M("ml_model_fallbacks"), "model fallbacks (ML-020)"),
            (M("ml_infer_faults"), "inference faults"),
            (M("ml_contract_failed"), "contract violations (ML-010)"),
            (M("ml_smc_faults"), "SMC compute faults"),
            (M("ml_retrain_failures"), "retrain failures"),
        ], desc="each rise = the model or a feature block degraded to prior/"
                "neutral. Flat is healthy.", x=0, y=y),
        stat("Retrain failures", M("ml_retrain_failures"),
             steps=(("null", "green"), (1, "yellow"), (5, "red")),
             desc="auto-retrain threw; a rising number = stale champion kept "
                  "forever", w=6, x=12, y=y),
        stat("Model fallbacks", M("ml_model_fallbacks"),
             steps=(("null", "green"), (1, "yellow"), (50, "red")),
             desc="inferences served the prior instead of the model", w=6,
             x=18, y=y),
    ]
    y += 8

    # ---- Row 4: execution & risk rejects -----------------------------
    panels.append(row("Execution & risk rejects", y))
    y += 1
    panels += [
        timeseries("Firewall rejects/clamps by code", [
            (f'liquiditybot_firewall_count{{{JOB}}}', "{{code}}"),
        ], desc="per-code FW tallies: rate-limit, dupe, notional/collar reject "
                "or clamp, fault-reject", x=0, y=y),
        timeseries("Order-manager rejects", [
            (M("order_venue_rejects"), "venue rejects (OM-021)"),
            (M("order_deadman_failures"), "dead-man failures (OM-050)"),
        ], desc="venue refused an order / dead-man refresh failing (precedes "
                "Kraken auto-cancelling all resting orders)", w=6, x=12, y=y),
        stat("Dead-man failures", M("order_deadman_failures"),
             steps=(("null", "green"), (1, "yellow"), (3, "red")),
             desc=">=3 escalates; the switch that cancels resting orders is "
                  "failing to refresh", w=6, x=18, y=y),
    ]
    y += 8

    # ---- Row 5: reason-code frequency --------------------------------
    panels.append(row("Reason-code frequency (why decisions go the way they do)",
                      y))
    y += 1
    panels += [
        timeseries("Code emissions by family", [
            (f'liquiditybot_code_count{{{JOB}}}', "{{prefix}}"),
        ], desc="cumulative count of every reason code by prefix — SZ sizer, PT "
                "pre-trade, RP risk-protocol, FW firewall, OM orders, ML, VN, "
                "TH. A jump in RP = budget/heat exhaustion stopping entries.",
           x=0, y=y),
        table("Code totals", f'liquiditybot_code_count{{{JOB}}}', "{{prefix}}",
              desc="current cumulative totals per code family", x=12, y=y),
    ]
    y += 8

    # ---- Row 6: risk, watchdog & integrity ---------------------------
    panels.append(row("Risk, watchdog & integrity", y))
    y += 1
    panels += [
        timeseries("Drawdown & equity drift", [
            (M("drawdown_pct"), "drawdown %"),
            (M("equity_drift_pct"), "equity drift %"),
        ], unit="percent", desc="drift = book vs recomputed equity mismatch "
                                "(reconciliation health)", w=8, x=0, y=y),
        timeseries("Watchdog trips", [
            (M("watchdog_entries_blocked"), "entries blocked"),
            (M("watchdog_critical_stale"), "critical stale"),
            (M("watchdog_velocity_tripped"), "flash-crash velocity"),
            (M("watchdog_divergent"), "divergent assets"),
            (M("watchdog_stale_assets"), "stale assets"),
        ], desc="infrastructure sentry: each trip blocks new entries", w=8,
           x=8, y=y),
        stat("Audit dropped writes", M("audit_dropped_writes"),
             steps=(("null", "green"), (1, "red")),
             desc="hash-chained audit records lost to disk errors (chain holes)",
             w=8, h=4, x=16, y=y),
        stat("WS books cached", M("ws_kraken_books"),
             steps=(("null", "red"), (1, "green")),
             desc="live cached order books (should equal traded-pair count)",
             w=8, h=4, x=16, y=y + 4),
    ]
    y += 8

    # ---- Row 7: live error log ---------------------------------------
    panels.append(row("Live error log", y))
    y += 1
    panels.append(logs(
        "Warnings, errors & reason codes",
        '{service_name="liquiditybot"} | severity_text=~"WARNING|ERROR|CRITICAL"',
        x=0, y=y))

    # UNWRAPPED dashboard model (top-level), NOT {"dashboard": {...}}: Grafana's
    # UI import ("Import via dashboard JSON model" / file upload) reads
    # schemaVersion at the TOP level and rejects the API-style wrapper with
    # "Invalid or unknown dashboard schema". The wrapper is only for the HTTP
    # API (POST /api/dashboards/db), which we don't use.
    return {
        "uid": "liquiditybot-incidents",
        "title": "liquiditybot — incidents",
        "description": "Faults, rejects and self-heal signals for the "
                       "liquiditybot paper-trading engine. Complementary to "
                       "'liquiditybot — control'.",
        "tags": ["liquiditybot", "faults", "self-heal", "paper-trading"],
        "schemaVersion": 39, "version": 1, "editable": True,
        "timezone": "browser", "refresh": "30s",
        "time": {"from": "now-6h", "to": "now"},
        "templating": {"list": []},
        "annotations": {"list": []},
        "panels": panels,
    }


if __name__ == "__main__":
    # NOTE: the shipped docs/grafana/liquiditybot_incidents.json has since been
    # hand-extended (Operating-state row, exit-eval / cycle-failure / audit
    # torn-tail panels). This generator is the STARTING POINT, not the live
    # source of truth — re-running it drops those additions. Writes to a
    # .generated sibling so it can't silently clobber the maintained file;
    # diff/merge intentionally.
    out = Path(__file__).resolve().parents[1] / "docs" / "grafana" / \
        "liquiditybot_incidents.generated.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(build(), indent=2), encoding="utf-8")
    print(f"wrote {out} (compare against the maintained liquiditybot_"
          f"incidents.json before replacing it)")
