"""
scripts/gc_pusher.py — push bot telemetry to Grafana Cloud (OTLP/HTTP).

Sidecar, not engine code: reads outputs/status.json (the same atomic
snapshot the dashboard reads) every PERIOD seconds and posts gauges to
the Grafana Cloud OTLP gateway. The bot never knows this exists; any
failure logs one line and retries next tick. Works everywhere the repo
does — cloud container, Windows PC — so phone monitoring survives any
single machine dying.

Configuration is environment-only, no secrets in the repo or argv:

  GC_OTLP_URL      OTLP metrics endpoint, e.g.
                   https://otlp-gateway-prod-us-east-3.grafana.net/otlp/v1/metrics
  GC_INSTANCE_ID   numeric Grafana Cloud instance / username for Basic auth
  GC_TOKEN_FILE    path to a file containing the OTLP write token
                   (chmod 600; NEVER commit the file)
  LB_STATUS        status.json path (default: outputs/status.json)
  GC_PERIOD_SEC    push interval seconds (default: 30)

Grafana Cloud's OTLP translator appends a `_ratio` suffix ONLY to gauges
whose unit is "1"; gauge() below deliberately emits an EMPTY unit so the
stored name equals the exported name (no suffix). `liquiditybot_equity`
is therefore stored as `liquiditybot_equity` — the base name that
docs/grafana/liquiditybot_dashboard.json queries. (Do not set a unit here
without also renaming the dashboard's queried metrics in the same change.)
"""
import base64
import json
import os
import time
import urllib.request


def _cfg() -> dict:
    url = os.environ.get("GC_OTLP_URL", "")
    instance = os.environ.get("GC_INSTANCE_ID", "")
    token_file = os.environ.get("GC_TOKEN_FILE", "")
    if not (url.startswith("https://") and instance and token_file):
        raise SystemExit(
            "gc_pusher: set GC_OTLP_URL (https), GC_INSTANCE_ID and "
            "GC_TOKEN_FILE — see the module docstring")
    with open(token_file, encoding="utf-8") as fh:
        token = fh.read().strip()
    return {
        "url": url,
        "auth": base64.b64encode(f"{instance}:{token}".encode()).decode(),
        "status": os.environ.get("LB_STATUS", "outputs/status.json"),
        "period": float(os.environ.get("GC_PERIOD_SEC", "30")),
    }


def gauge(name: str, value: float, attrs: dict | None = None,
          ts: float | None = None) -> dict:
    dp: dict = {"asDouble": float(value),
                "timeUnixNano": str(int((ts or time.time()) * 1e9))}
    if attrs:
        dp["attributes"] = [{"key": k, "value": {"stringValue": str(v)}}
                            for k, v in attrs.items()]
    # unit stays EMPTY: Grafana Cloud's OTLP translator appends "_ratio"
    # to unit-"1" gauges, which mislabels raw counts (cycles, rows) as
    # ratios; with no unit the stored name matches the exported name
    return {"name": name, "unit": "", "gauge": {"dataPoints": [dp]}}


def collect(status_path: str) -> list:
    with open(status_path, encoding="utf-8") as fh:
        s = json.load(fh)
    ts = float(s.get("written_at") or time.time())
    m = []
    # stamped with NOW, not written_at: a frozen runner (or stale file)
    # shows up as a rising age even while runner_state still says RUNNING
    m.append(gauge("liquiditybot_status_age_sec",
                   max(0.0, time.time() - ts), ts=time.time()))
    for key in ("equity", "daily_pnl", "drawdown_pct", "cycle",
                "cycle_lifetime", "feed_latency_ms", "marks_age_sec",
                "fees_total", "realized_total", "equity_drift_pct",
                # hardening guards (rising = a book position or the whole
                # cycle is wedging its own escape path — see the incidents
                # dashboard). Emitted as gauges; 0 in steady state.
                "exit_eval_failures", "cycle_consecutive_failures"):
        v = s.get(key)
        if isinstance(v, (int, float)):
            m.append(gauge(f"liquiditybot_{key}", v, ts=ts))
    m.append(gauge("liquiditybot_positions_open",
                   len(s.get("positions") or []), ts=ts))
    m.append(gauge("liquiditybot_running",
                   1.0 if s.get("runner_state") == "RUNNING" else 0.0, ts=ts))
    ml = s.get("ml") or {}
    for key in ("history_rows", "open_candidates", "pending_labels"):
        v = ml.get(key)
        if isinstance(v, (int, float)):
            m.append(gauge(f"liquiditybot_ml_{key}", v, ts=ts))
    for asset, v in (s.get("manip_suspect") or {}).items():
        m.append(gauge("liquiditybot_manip_suspect", v, {"asset": asset}, ts))
    for asset, sig in (s.get("signals") or {}).items():
        if isinstance(sig, dict):
            for k in ("confidence", "urgency"):
                if isinstance(sig.get(k), (int, float)):
                    m.append(gauge(f"liquiditybot_signal_{k}", sig[k],
                                   {"asset": asset}, ts))
    for asset, th in ((s.get("thales") or {}).get("assets") or {}).items():
        for k in ("grid", "metronome", "clockwork", "stop_zone",
                  "lapses", "bar_holes", "lapse_warmup_sec"):
            if isinstance(th.get(k), (int, float)):
                m.append(gauge(f"liquiditybot_thales_{k}", th[k],
                               {"asset": asset}, ts))
    mm = s.get("moomoo") or {}
    for k in ("risk_z", "opt_pcr_z", "opt_oi_pcr_z", "opt_iv_skew"):
        v = mm.get(k)
        if isinstance(v, (int, float)):
            m.append(gauge(f"liquiditybot_moomoo_{k}", v, ts=ts))
    # Kraken v2 ws feed health: connected (1/0) and live cached books. A
    # dropping feed shows up as connected->0 / books falling while the bot
    # silently keeps trading on the REST fallback.
    kws = s.get("ws_kraken") or {}
    m.append(gauge("liquiditybot_ws_kraken_connected",
                   1.0 if kws.get("connected") else 0.0, ts=ts))
    for k in ("books", "reconnects"):
        v = kws.get(k)
        if isinstance(v, (int, float)):
            m.append(gauge(f"liquiditybot_ws_kraken_{k}", v, ts=ts))
    # ---- fault & health signals (the incidents dashboard) --------------
    # These were tracked internally but never exported; a degrading subsystem
    # showed up only in a log line nobody was watching.
    m.append(gauge("liquiditybot_halted",
                   1.0 if s.get("halted") else 0.0, ts=ts))
    m.append(gauge("liquiditybot_entries_enabled",
                   1.0 if s.get("entries_enabled") else 0.0, ts=ts))
    # ML governor kill-switch level: 0 ok / 1 degraded / 2 model killed
    mon = s.get("monitor") or {}
    if isinstance(mon.get("level"), (int, float)):
        m.append(gauge("liquiditybot_monitor_level", mon["level"], ts=ts))
    # ML fault counters (fallbacks/inference faults/contract breaches/SMC
    # degrades/retrain failures) — rising = a subsystem quietly dying
    for k in ("model_fallbacks", "infer_faults", "contract_failed",
              "smc_faults", "retrain_failures"):
        v = ml.get(k)
        if isinstance(v, (int, float)):
            m.append(gauge(f"liquiditybot_ml_{k}", v, ts=ts))
    m.append(gauge("liquiditybot_audit_dropped_writes",
                   float(s.get("audit_dropped_writes") or 0), ts=ts))
    # moomoo up/down (options + basket feed) — was dark
    m.append(gauge("liquiditybot_moomoo_options_available",
                   1.0 if mm.get("options_available") else 0.0, ts=ts))
    m.append(gauge("liquiditybot_moomoo_available",
                   1.0 if mm.get("available") else 0.0, ts=ts))
    # watchdog trips — each blocks new entries
    wd = s.get("watchdog") or {}
    for k in ("entries_blocked", "critical_stale", "velocity_tripped"):
        m.append(gauge(f"liquiditybot_watchdog_{k}",
                       1.0 if wd.get(k) else 0.0, ts=ts))
    m.append(gauge("liquiditybot_watchdog_divergent",
                   float(len(wd.get("divergent") or [])), ts=ts))
    m.append(gauge("liquiditybot_watchdog_stale_assets",
                   float(len(wd.get("stale_assets") or [])), ts=ts))
    # risk firewall: latched fault (1/0) + per-code reject/clamp tallies
    fw = s.get("firewall") or {}
    m.append(gauge("liquiditybot_firewall_fault",
                   1.0 if fw.get("fault") else 0.0, ts=ts))
    for code, cnt in (fw.get("counters") or {}).items():
        if isinstance(cnt, (int, float)):
            m.append(gauge("liquiditybot_firewall_count", cnt,
                           {"code": str(code)}, ts))
    # order manager: venue rejects (OM-021) + dead-man refresh failures (OM-050)
    om = s.get("order_manager") or {}
    for k in ("venue_rejects", "deadman_failures"):
        v = om.get(k)
        if isinstance(v, (int, float)):
            m.append(gauge(f"liquiditybot_order_{k}", v, ts=ts))
    # central reason-code frequency ledger, aggregated by prefix (SZ/PT/RP/FW/…)
    for prefix, cnt in ((s.get("code_stats") or {}).get("by_prefix") or {}).items():
        if isinstance(cnt, (int, float)):
            m.append(gauge("liquiditybot_code_count", cnt,
                           {"prefix": str(prefix)}, ts))
    return m


def push(cfg: dict, metrics: list) -> int:
    # ONE resource attribute only: service.name -> job="liquiditybot". Adding
    # service.instance.id here would split the EXISTING series (historical
    # samples have no instance label) into two - every panel then draws two
    # identical lines for the whole retention window. Single-instance is
    # enforced operationally (the single-runner lock + the self-heal keeping
    # exactly one pusher), so a per-instance label buys nothing and only
    # duplicates the dashboard. If a true multi-instance setup ever lands,
    # add the label AND ship dashboard queries that select/aggregate it in
    # the same change - never one without the other.
    body = {"resourceMetrics": [{
        "resource": {"attributes": [
            {"key": "service.name",
             "value": {"stringValue": "liquiditybot"}}]},
        "scopeMetrics": [{"metrics": metrics}]}]}
    req = urllib.request.Request(
        cfg["url"], data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json",
                 "Authorization": f"Basic {cfg['auth']}"})
    # scheme is validated to https in _cfg(); file:// can't reach here
    with urllib.request.urlopen(req, timeout=30) as r:  # nosec B310
        return r.status


def main() -> None:
    cfg = _cfg()
    while True:
        try:
            code = push(cfg, collect(cfg["status"]))
            print(f"{time.strftime('%H:%M:%S')} pushed HTTP {code}",
                  flush=True)
        except Exception as e:
            print(f"{time.strftime('%H:%M:%S')} push failed: {e}",
                  flush=True)
        time.sleep(cfg["period"])


if __name__ == "__main__":
    main()
