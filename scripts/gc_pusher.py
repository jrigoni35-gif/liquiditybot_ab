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
docs/grafana/liquiditybot_command.json queries. (Do not set a unit here
without also renaming the dashboard's queried metrics in the same change.)
"""
import base64
import json
import math
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


def _num(x, default: float = 0.0) -> float:
    """Safe float: None / non-numeric / NaN -> default. status.json can carry a
    null upnl (bad_entry) or mark, which must not poison an aggregate sum."""
    try:
        v = float(x)
        return v if v == v else default          # NaN guard
    except (TypeError, ValueError):
        return default


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
    ml = s.get("ml") or {}          # bound once; §4 + ML blocks below read it
    # ---- live positions (§2): net per instrument (symbol,side) --------------
    # Aggregated per (symbol, side), NOT per ephemeral lot-id: putting the
    # per-position id in a label would churn Prometheus cardinality unbounded
    # (a Grafana footgun). This is the desk view — net exposure/uPnL/risk per
    # instrument. mark/upnl are already computed by the runner at venue
    # precision; hedges are excluded (they carry no tiers/stops of their own).
    # Also the risk-on banner: total unrealized, gross exposure, $-at-risk if
    # every stop filled. Instant queries on these show only OPEN positions
    # (a closed one stops updating and drops out of the lookback).
    agg: dict = {}
    for p in (s.get("positions") or []):
        if not isinstance(p, dict) or p.get("hedge"):
            continue
        sym, side = str(p.get("symbol") or "?"), str(p.get("direction") or "?")
        entry, mark = _num(p.get("entry")), _num(p.get("mark"))
        size, stop = abs(_num(p.get("size"))), _num(p.get("stop"))
        a = agg.setdefault((sym, side), {
            "notional": 0.0, "upnl": 0.0, "cost": 0.0, "risk": 0.0,
            "lots": 0, "tier": 0, "age": 0.0, "conv_w": 0.0, "stop_dist": None})
        notional = size * mark
        a["notional"] += notional
        a["upnl"] += _num(p.get("upnl_usd"))
        a["cost"] += size * entry
        a["lots"] += 1
        a["tier"] = max(a["tier"], int(_num(p.get("tiers_fired"))))
        a["age"] = max(a["age"], _num(p.get("age_h")))
        a["conv_w"] += _num(p.get("p_win")) * notional
        if stop > 0 and entry > 0:
            a["risk"] += abs(entry - stop) * size
            sd = abs(entry - stop) / entry * 100.0
            a["stop_dist"] = sd if a["stop_dist"] is None \
                else min(a["stop_dist"], sd)          # tightest (nearest) stop
    tot_upnl = tot_notional = tot_risk = 0.0
    for (sym, side), a in agg.items():
        lab = {"symbol": sym, "side": side}
        m.append(gauge("liquiditybot_position_notional_usd", a["notional"], lab, ts))
        m.append(gauge("liquiditybot_position_upnl_usd", a["upnl"], lab, ts))
        m.append(gauge("liquiditybot_position_lots", float(a["lots"]), lab, ts))
        m.append(gauge("liquiditybot_position_tiers_fired", float(a["tier"]), lab, ts))
        m.append(gauge("liquiditybot_position_age_hours", a["age"], lab, ts))
        if a["cost"] > 0:
            m.append(gauge("liquiditybot_position_upnl_pct",
                           a["upnl"] / a["cost"] * 100.0, lab, ts))
        # conviction divides by NOTIONAL, which is 0 when the mark is null
        # while cost>0 — that ZeroDivisionError aborted collect() and blacked
        # out the ENTIRE metric batch (audit DL-1 2026-07-17); guard its own
        # denominator, never a proxy's
        if a["notional"] > 0:
            m.append(gauge("liquiditybot_position_conviction",
                           a["conv_w"] / a["notional"], lab, ts))
        if a["risk"] > 0:
            m.append(gauge("liquiditybot_position_r_multiple",
                           a["upnl"] / a["risk"], lab, ts))
        if a["stop_dist"] is not None:
            m.append(gauge("liquiditybot_position_stop_dist_pct",
                           a["stop_dist"], lab, ts))
        tot_upnl += a["upnl"]
        tot_notional += a["notional"]
        tot_risk += a["risk"]
    m.append(gauge("liquiditybot_open_upnl_usd", tot_upnl, ts=ts))
    m.append(gauge("liquiditybot_gross_exposure_usd", tot_notional, ts=ts))
    m.append(gauge("liquiditybot_open_risk_usd", tot_risk, ts=ts))
    _eq = _num(s.get("equity"))
    if _eq > 0:
        m.append(gauge("liquiditybot_gross_exposure_pct",
                       tot_notional / _eq * 100.0, ts=ts))
    # ---- performance ledger (§1): win-rate / PF / expectancy / streak -------
    # Portfolio-wide + per asset. None-valued fields (expectancy_r with no
    # stops, payoff_ratio with no losses) are simply not numeric -> skipped.
    perf = s.get("performance") or {}
    for k in ("trades", "win_rate", "win_rate_lcb", "profit_factor",
              "expectancy_usd", "expectancy_r", "payoff_ratio", "sharpe",
              "sortino", "cur_loss_streak", "max_loss_streak", "net_usd",
              "gross_profit_usd", "gross_loss_usd", "avg_win_usd",
              "avg_loss_usd"):
        v = (perf.get("overall") or {}).get(k)
        if isinstance(v, (int, float)):
            m.append(gauge(f"liquiditybot_perf_{k}", v, ts=ts))
    for asset, st in (perf.get("by_asset") or {}).items():
        if not isinstance(st, dict):
            continue
        for k in ("trades", "win_rate", "profit_factor", "expectancy_usd",
                  "net_usd", "cur_loss_streak", "max_loss_streak"):
            v = st.get(k)
            if isinstance(v, (int, float)):
                m.append(gauge(f"liquiditybot_perf_asset_{k}", v,
                               {"asset": str(asset)}, ts))
    # ---- signal & edge (§4) --------------------------------------------------
    # confirmed + per-gate pass as 1/0 gauges: avg_over_time() in Grafana turns
    # them into confirmed-rate / gate pass-rate, so "which gate blocks most" is
    # answerable without a new counter. Bounded: assets x 8 gates.
    for asset, sig in (s.get("signals") or {}).items():
        if not isinstance(sig, dict):
            continue
        m.append(gauge("liquiditybot_signal_confirmed",
                       1.0 if sig.get("confirmed") else 0.0,
                       {"asset": asset}, ts))
        for gname, passed in (sig.get("gates") or {}).items():
            m.append(gauge("liquiditybot_signal_gate_passed",
                           1.0 if passed else 0.0,
                           {"asset": asset, "gate": str(gname)}, ts))
    gs = ml.get("gate_stats") or {}
    for gname, w in (gs.get("weights") or {}).items():
        if isinstance(w, (int, float)):
            m.append(gauge("liquiditybot_gate_weight", w,
                           {"gate": str(gname)}, ts))
    for k in ("labeled", "base_rate"):
        v = gs.get(k)
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            m.append(gauge(f"liquiditybot_gate_{k}", v, ts=ts))
    # per-asset regime context: numerics as plain gauges; the label strings ride
    # an info-style gauge (value 1, labels macro/vol/liq — the standard *_info
    # pattern; a superseded label-set goes stale and drops out of instant views)
    for asset, r in (s.get("regimes") or {}).items():
        if not isinstance(r, dict):
            continue
        for k in ("momentum", "vol_pct", "spread_bps", "basis_bps", "spoof"):
            v = r.get(k)
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                m.append(gauge(f"liquiditybot_regime_{k}", v,
                               {"asset": asset}, ts))
        m.append(gauge("liquiditybot_regime_info", 1.0,
                       {"asset": asset, "macro": str(r.get("macro", "?")),
                        "vol": str(r.get("vol", "?")),
                        "liq": str(r.get("liq", "?"))}, ts))
    # entry-decision reason codes in FULL (PT/SZ families): EV-gate rejects,
    # exploration bypasses (PT-050), sizing vetoes — the per-code trend view
    for code, cnt in ((s.get("code_stats") or {}).get("entry_codes")
                      or {}).items():
        if isinstance(cnt, (int, float)) and not isinstance(cnt, bool):
            m.append(gauge("liquiditybot_code_count_detail", cnt,
                           {"code": str(code)}, ts))
    for key in ("history_rows", "open_candidates", "pending_labels"):
        v = ml.get(key)
        if isinstance(v, (int, float)):
            m.append(gauge(f"liquiditybot_ml_{key}", v, ts=ts))
    for asset, v in (s.get("manip_suspect") or {}).items():
        m.append(gauge("liquiditybot_manip_suspect", v, {"asset": asset}, ts))
    for asset, sig in (s.get("signals") or {}).items():
        if isinstance(sig, dict):
            # concentration (0 diffuse .. 1 pinpointed): the per-asset
            # decision-quality signal - lets the desk compare a concentrated
            # conviction against a blended-average signal side by side
            for k in ("confidence", "urgency", "concentration"):
                if isinstance(sig.get(k), (int, float)):
                    m.append(gauge(f"liquiditybot_signal_{k}", sig[k],
                                   {"asset": asset}, ts))
    # THALES footprint detectors per asset: periodicity (grid/metronome/
    # clockwork), round-number stop-hunt proximity (stop_zone), bar-close
    # clustering (barclose), spoof-flicker EWMA per side (spoof_bid/ask,
    # TH-017), feed integrity (feed_dirty + lapse/hole counters). All bounded
    # [0,1] except the counters — the dashboard reads them as a manipulation
    # scorecard.
    for asset, th in ((s.get("thales") or {}).get("assets") or {}).items():
        for k in ("grid", "metronome", "clockwork", "stop_zone", "barclose",
                  "spoof_bid", "spoof_ask", "feed_dirty", "lapses",
                  "bar_holes", "lapse_warmup_sec"):
            if isinstance(th.get(k), (int, float)) and not isinstance(k, bool):
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
    # input feature-drift share (0..1): fraction of MARKET features past the PSI
    # threshold. Transient blips self-heal via auto-retrain; a value pinned high
    # WHILE monitor_level rises is the real signal (see the incidents alert rule).
    if isinstance(mon.get("drift_share"), (int, float)):
        m.append(gauge("liquiditybot_ml_drift_share", mon["drift_share"], ts=ts))
    # outcome-side model health — present ONLY when the judge window is full
    # (>= min_trades_to_judge closed trades on the DEPLOYED model). The rolling
    # Brier vs its base-rate baseline is the "are the predictions any good"
    # signal: brier - baseline_brier > 3*brier_margin is the governor's failing
    # (kill) line, which the outcome alert rule keys on. Absent = not yet
    # judgeable (too few outcomes) -> no metric -> alert stays OK, never a false
    # ping. This is INDEPENDENT of input drift: predictions can rot with stable
    # inputs, and inputs can drift while predictions still hold.
    for k in ("brier", "baseline_brier", "calibration_gap", "window_trades",
              # §5 model health: promised (avg_p) vs delivered (hit_rate,
              # Wilson LCB) + governor throttles + the deployed champion's bar
              "hit_rate", "hit_rate_lcb", "avg_p", "shrinkage", "kelly_mult",
              "stop_widen", "edge_ratio_bump", "champion_brier"):
        v = mon.get(k)
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            m.append(gauge(f"liquiditybot_ml_{k}", v, ts=ts))
    m.append(gauge("liquiditybot_ml_use_model",
                   1.0 if mon.get("use_model") else 0.0, ts=ts))
    m.append(gauge("liquiditybot_ml_retrain_flag",
                   1.0 if ml.get("retrain_flag") else 0.0, ts=ts))
    # labels by source: live = ground truth, candidate = triple-barrier proxy
    for src, cnt in (ml.get("labels_by_source") or {}).items():
        if isinstance(cnt, (int, float)) and not isinstance(cnt, bool):
            m.append(gauge("liquiditybot_ml_labels", cnt,
                           {"source": str(src)}, ts))
    # deployed model rung on the simplicity ladder (info-style label gauge)
    if ml.get("model_kind"):
        m.append(gauge("liquiditybot_ml_model_info", 1.0,
                       {"kind": str(ml["model_kind"])}, ts))
    # ML fault counters (fallbacks/inference faults/contract breaches/SMC
    # degrades/retrain failures) — rising = a subsystem quietly dying
    for k in ("model_fallbacks", "infer_faults", "contract_failed",
              "smc_faults", "retrain_failures"):
        v = ml.get(k)
        if isinstance(v, (int, float)):
            m.append(gauge(f"liquiditybot_ml_{k}", v, ts=ts))
    m.append(gauge("liquiditybot_audit_dropped_writes",
                   float(s.get("audit_dropped_writes") or 0), ts=ts))
    m.append(gauge("liquiditybot_audit_tail_truncations",
                   float(s.get("audit_tail_truncations") or 0), ts=ts))
    # central fault authority: op-state as a severity ladder (0 ARMED nominal,
    # 1 DEGRADED no-new-risk, 2 HALTED flatten-and-stop) + latched-fault count.
    _fault = s.get("fault") or {}
    _op = {"ARMED": 0.0, "DEGRADED": 1.0, "HALTED": 2.0}.get(
        str(_fault.get("state")), -1.0)
    m.append(gauge("liquiditybot_op_state", _op, ts=ts))
    m.append(gauge("liquiditybot_fault_count",
                   float(len(_fault.get("faults") or {})), ts=ts))
    # post-fill mark-out (bps) per asset+horizon — negative = adverse selection
    for asset, hs in (s.get("markout") or {}).get("by_asset", {}).items():
        for hz, rec in (hs or {}).items():
            v = (rec or {}).get("markout_bps")
            if isinstance(v, (int, float)):
                m.append(gauge("liquiditybot_markout_bps", v,
                               {"asset": asset, "horizon_sec": str(hz)}, ts))
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
    # + execution quality (§3): maker/taker split, rolling slippage, venue RTT.
    # None-valued fields (no fills yet) fail the numeric guard -> not emitted.
    om = s.get("order_manager") or {}
    for k in ("venue_rejects", "deadman_failures", "latency_ms",
              "maker_fills", "taker_fills", "maker_share",
              "maker_notional_usd", "taker_notional_usd",
              "avg_slip_bps", "worst_slip_bps"):
        v = om.get(k)
        if isinstance(v, (int, float)):
            m.append(gauge(f"liquiditybot_order_{k}", v, ts=ts))
    # ---- asset skimmer (§7): candidate rankings + promotions -----------------
    sk = s.get("skimmer") or {}
    for pair, rec in (sk.get("scores") or {}).items():
        v = (rec or {}).get("score")
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            m.append(gauge("liquiditybot_skimmer_score", v,
                           {"pair": str(pair)}, ts))
    if sk:
        m.append(gauge("liquiditybot_skimmer_promoted_count",
                       float(len(sk.get("promoted") or [])), ts=ts))
        m.append(gauge("liquiditybot_skimmer_candidates",
                       float(sk.get("candidates") or 0), ts=ts))
        for pair in (sk.get("promoted") or []):
            m.append(gauge("liquiditybot_skimmer_promoted_info", 1.0,
                           {"pair": str(pair)}, ts))
    # ---- per-asset circuit breaker -------------------------------------------
    cb = s.get("circuit_breaker") or {}
    if cb:
        m.append(gauge("liquiditybot_cb_tripped_count",
                       float(len(cb.get("tripped") or {})), ts=ts))
        for asset, hrs in (cb.get("tripped") or {}).items():
            if isinstance(hrs, (int, float)) and not isinstance(hrs, bool):
                m.append(gauge("liquiditybot_cb_paused_hours_left", hrs,
                               {"asset": str(asset)}, ts))
        for asset, streak in (cb.get("streaks") or {}).items():
            if isinstance(streak, (int, float)) and not isinstance(streak, bool):
                m.append(gauge("liquiditybot_cb_loss_streak", streak,
                               {"asset": str(asset)}, ts))
    # ---- risk-protocol posture (§6) ------------------------------------------
    rp = s.get("risk_protocols") or {}
    for k in ("daily_budget_used_frac", "weekly_budget_used_frac",
              "taper_mult", "heat_frac", "heat_cap_frac", "dd_throttle_mult"):
        v = rp.get(k)
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            m.append(gauge(f"liquiditybot_rp_{k}", v, ts=ts))
    # central reason-code frequency ledger, aggregated by prefix (SZ/PT/RP/FW/…)
    for prefix, cnt in ((s.get("code_stats") or {}).get("by_prefix") or {}).items():
        if isinstance(cnt, (int, float)):
            m.append(gauge("liquiditybot_code_count", cnt,
                           {"prefix": str(prefix)}, ts))
    # single choke point: a NaN/inf that slipped through any guard above (json
    # round-trips NaN happily) must not reach the wire — ONE non-finite gauge
    # invalidates the whole OTLP JSON batch and blacks out EVERY metric.
    return [x for x in m
            if math.isfinite(x["gauge"]["dataPoints"][0]["asDouble"])]


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
