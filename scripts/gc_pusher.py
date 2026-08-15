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
  GC_PERIOD_SEC    push interval seconds (default: 60 — Grafana Cloud
                   FREE tier meters active series at 1 datapoint/minute;
                   the boards refresh at 1m, so a faster push buys
                   nothing and doubles metered usage. 2026-07-29,
                   operator on the free plan.)

Grafana Cloud's OTLP translator appends a `_ratio` suffix ONLY to gauges
whose unit is "1"; gauge() below deliberately emits an EMPTY unit so the
stored name equals the exported name (no suffix). `liquiditybot_equity`
is therefore stored as `liquiditybot_equity` — the base name that
docs/grafana/liquiditybot_command.json queries. (Do not set a unit here
without also renaming the dashboard's queried metrics in the same change.)
"""
import base64
import json
import logging
import math
import os
import time
import urllib.request


log = logging.getLogger("gc_pusher")


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
        # default 60s: Grafana Cloud FREE meters series at 1 DPM and the
        # boards refresh at 1m — 30s pushes doubled metered usage for
        # zero visible freshness (2026-07-29 free-plan compatibility)
        "period": float(os.environ.get("GC_PERIOD_SEC", "60")),
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
    """Safe float: None / non-numeric / NaN / inf -> default. status.json can
    carry a null upnl (bad_entry) or mark, which must not poison an aggregate
    sum; a JSON Infinity must not reach int() at a call site either (that
    raised OverflowError and blacked out the whole metric batch)."""
    try:
        v = float(x)
        return v if math.isfinite(v) else default   # NaN/inf guard
    except (TypeError, ValueError):
        return default


STALE_AFTER_SEC = 120.0    # runner writes ~2s cadence; 120s = frozen/dead
                           # (mirrors the watchdog's stale_critical_sec)

# ---- label-era transition cardinality clamp (docs/quant/2026-07-26_
# era_exclusion.md) — bounded label sets, matching ml/history.py's own
# vocabularies (label_era_of's four known eras + "unknown", and the
# triple_barrier-mode / exit_sim-mode barrier strings). Cardinality is
# bounded or it does not ship: a malformed/garbage era or exit-reason
# string from a corrupted status.json must never mint a new Prometheus
# series — it clamps to "other" (or "none" for a blank reason) instead.
_ERA_KNOWN = frozenset({"legacy", "exit_sim", "exit_sim_time_stop",
                        "triple_barrier", "unknown"})
_REASON_KNOWN = frozenset({"pt", "sl", "time", "trail", "realized", "tier",
                          "floor", "time_stop", "tb_pt", "tb_sl", "tb_time"})


def _era_label(era) -> str:
    """Clamp to a bounded vocabulary - but the vocabulary must include
    the HORIZON-QUALIFIED triple_barrier eras.

    2026-08-15: `_ERA_KNOWN` was written before the 432-bar migration
    (7566ea88) started minting `triple_barrier_h<N>`, so the DEPLOYED
    era clamped to "other" and the operator's Prometheus series for the
    current era did not exist. The dashboard panel literally titled
    "New-era outcomes by barrier" was querying era="triple_barrier" -
    the RETIRED era - and would have found nothing even if it had asked
    for the right one. Two independent defects, either of which alone
    hides the current era.

    CARDINALITY. The first version of this widening claimed to stay
    bounded and did not - `suffix.isdigit()` alone admitted 50,000
    distinct series from 50,000 garbage values, plus three separate
    escapes found by adversarial review on 2026-08-15:
      * NON-ASCII digits - `str.isdigit()` is True for Arabic-Indic,
        Devanagari and superscript digits, so `triple_barrier_h<U+0664
        U+0663 U+0662>` minted a series
      * unbounded LENGTH - a 400-digit suffix produced a 416-char label
      * LEADING ZEROS - `_h00000432` and `_h432` are the same horizon
        and minted two different series
    This matters because the value is not ours: `label_era` is a column
    in signal_history.csv, and session_import.py MERGES that file from
    bundles on the shared durable branch. A tampered or corrupt bundle
    therefore reaches a Prometheus series name, which is the exact thing
    the original frozenset comment forbade.

    Bounded properly now: ASCII digits only, at most 4 of them, parsed
    to 1..4032 (two weeks of 5-minute bars - past any plausible label
    horizon). Worst case is 4032 series instead of unbounded, and the
    realistic case is the two or three horizons actually deployed.

    Leading zeros are handled by TWO different mechanisms, and saying
    only one of them would be the kind of half-true docstring this
    session spent its day deleting: `_h0432` NORMALISES through int() to
    `triple_barrier_h432` (so it cannot twin with `_h432`), while
    `_h00432` and longer exceed the 4-char bound and are REJECTED to
    "other". Both routes are safe; neither mints a duplicate series."""
    e = str(era or "").strip()
    if e in _ERA_KNOWN:
        return e
    base, sep, suffix = e.partition("_h")
    if (base == "triple_barrier" and sep and suffix.isascii()
            and suffix.isdigit() and len(suffix) <= 4):
        n = int(suffix)
        if 1 <= n <= 4032:
            return f"triple_barrier_h{n}"      # normalised, not echoed
    return "other"


def _reason_label(reason) -> str:
    r = str(reason or "").strip()
    if not r:
        return "none"
    return r if r in _REASON_KNOWN else "other"


# ---- ml_labels{source=} cardinality clamp (F1) — HistoryStore.
# source_counts() keys ride verbatim off the CSV column; bounded today
# only by the two literal write sites ("live"/"candidate"). A corrupted
# or hand-edited row must clamp to "other" here at the emission site,
# never mint a new Prometheus series (same clamp idiom as _era_label/
# _reason_label above; ml/history.py itself is left reporting truth).
_SOURCE_KNOWN = frozenset({"live", "candidate"})


def _source_label(source) -> str:
    s = str(source or "").strip()
    return s if s in _SOURCE_KNOWN else "other"


def _thales_reliability_metrics(th_state: dict, ts: float) -> list:
    """THALES V2 reliability ledger (2026-07-29 audit A-1/B-2): per-
    detector graded evidence (fired/vindicated) + the evidence weight
    (normalized Wilson-LCB lift over the base rate), plus the shared
    __base__ null itself (graded closes + base win rate). Structurally
    EMPTY before the shadow-grading unlock — these series ARE the
    promotion-to-advise evidence the operator watches accrue ("is THALES
    earning its keep"). Extracted from collect() (pyright complexity
    ceiling), same emission idioms."""
    out: list = []
    for det, r in (th_state.get("reliability") or {}).items():
        if not isinstance(r, dict):
            continue
        for k in ("fired", "vindicated", "weight"):
            v = r.get(k)
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                out.append(gauge(f"liquiditybot_thales_rel_{k}", v,
                                 {"detector": str(det)}, ts))
    base = th_state.get("reliability_base") or {}
    bf, bv = base.get("fired"), base.get("vindicated")
    if isinstance(bf, (int, float)) and not isinstance(bf, bool):
        out.append(gauge("liquiditybot_thales_base_graded", bf, ts=ts))
        if isinstance(bv, (int, float)) and not isinstance(bv, bool) \
                and bf > 0:
            out.append(gauge("liquiditybot_thales_base_win_rate",
                             bv / bf, ts=ts))
    return out


def _probe_budget_metrics(pb: dict, ts: float) -> list:
    """SPB-R probe-budget telemetry (status.ml.probe_budget, spec §8):
    bucket level vs capacity, refill/governor, trailing-24h admission
    counters, the headline labels/day + unlock ETA, per-asset scarcity
    weights/costs/eff_weight (the ONE combined-drag number), and
    per-regime live-label counts. Missing/empty section (a pre-SPB-R
    status.json) emits NOTHING - never a crash, never a fabricated 0.
    Extracted from collect() (pyright complexity ceiling), same emission
    idioms as _thales_reliability_metrics above. avg_cost_24h is None
    until the first admit - honest absence, not emitted."""
    out: list = []
    if not pb:
        return out
    for k in ("tokens", "capacity", "refill_per_day", "governor_factor",
              "tuition_24h_usd", "tuition_cap_usd", "admits_24h",
              "refunds_24h", "denied_exhausted_24h", "rolls_failed_24h",
              "avg_cost_24h", "labels_24h", "live_labels_per_day_7d",
              "tb_era_labels", "unlock_eta_days", "avg_concurrent_probes",
              "open_probes"):
        v = pb.get(k)
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            out.append(gauge(f"liquiditybot_probe_budget_{k}", v, ts=ts))
    mode = pb.get("mode")
    if mode:            # info-style label gauge (the *_info pattern)
        out.append(gauge("liquiditybot_probe_budget_mode_info", 1.0,
                         {"mode": str(mode)}, ts))
    for asset, rec in (pb.get("per_asset") or {}).items():
        if not isinstance(rec, dict):
            continue                # malformed asset entry: skip, never crash
        for k in ("n_live", "w_asset", "cost", "eff_weight"):
            v = rec.get(k)
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                out.append(gauge(f"liquiditybot_probe_asset_{k}", v,
                                 {"asset": str(asset)}, ts))
    for regime, n in (pb.get("per_regime_live") or {}).items():
        # cardinality bounded at the source (engine REGIME_LABELS)
        if isinstance(n, (int, float)) and not isinstance(n, bool):
            out.append(gauge("liquiditybot_probe_regime_live", n,
                             {"regime": str(regime)}, ts))
    return out


def collect(status_path: str) -> list:
    # W2-14 re-decision (2026-07-23, operator-delegated): a missing or
    # unreadable status file used to raise out of here and abort the push
    # entirely — total telemetry silence, indistinguishable in Grafana from
    # a dead pusher or a cut network. Runner-not-writing is the single most
    # alarming state this plane can report, so it pushes the DL-6
    # alarm-only shape plus an explicit status_missing flag instead. (The
    # git-plane push_pc_status "no_status" noop is intentionally unchanged:
    # that plane has nothing to publish and its envelope's pushed_at age is
    # its own staleness signal — see test_remote_control.py.)
    try:
        with open(status_path, encoding="utf-8") as fh:
            s = json.load(fh)
    except (OSError, ValueError):
        now = time.time()
        return [gauge("liquiditybot_status_missing", 1.0, ts=now),
                gauge("liquiditybot_running", 0.0, ts=now),
                gauge("liquiditybot_status_stale", 1.0, ts=now)]
    try:
        ts = float(s.get("written_at") or 0.0)
        m = []
        # stamped with NOW, not written_at: a frozen runner (or stale file)
        # shows up as a rising age even while runner_state still says RUNNING
        age = max(0.0, time.time() - ts)
        m.append(gauge("liquiditybot_status_age_sec", age, ts=time.time()))
        # DL-6: a frozen runner leaves a stale status file that still says
        # RUNNING with healthy equity/cycle numbers - pushing those painted a
        # live bot on every panel while only the age gauge told the truth.
        # Past the staleness threshold push the ALARM-ONLY batch: age,
        # running=0, and an explicit stale flag. No stale gauge ever masquerades
        # as current market/PnL state again.
        # status_missing=0 whenever the file was readable (stale or fresh) so
        # the alert rule can distinguish "runner frozen" from "file gone"
        m.append(gauge("liquiditybot_status_missing", 0.0, ts=time.time()))
        # liquiditybot_status_malformed mirrors status_missing exactly:
        # 0.0 here (file parsed AND the fresh-path body below completed) so
        # the series always exists; 1.0 only from the except Exception
        # fallback below (any wrong-shape field anywhere past this point).
        m.append(gauge("liquiditybot_status_malformed", 0.0, ts=time.time()))
        if age > STALE_AFTER_SEC:
            m.append(gauge("liquiditybot_running", 0.0, ts=time.time()))
            m.append(gauge("liquiditybot_status_stale", 1.0, ts=time.time()))
            return m
        m.append(gauge("liquiditybot_status_stale", 0.0, ts=time.time()))
        for key in ("equity", "daily_pnl", "weekly_pnl", "monthly_pnl", "savings",
                    "reserve", "drawdown_pct", "cycle",
                    "cycle_lifetime", "feed_latency_ms", "marks_age_sec",
                    # true iteration durations (latency audit 2026-08-07):
                    # an 88s stall is finally a plottable event, not a
                    # sleep-sizing intermediate thrown away every loop
                    "cycle_duration_sec", "cycle_duration_max_sec",
                    "fees_total", "realized_total", "equity_drift_pct",
                    # honest all-time P&L (2026-08-09): realized_total is
                    # net of the CLOSING fee leg only - opening-leg fees hit
                    # cash and no P&L line, hiding 49% of lifetime fees.
                    # net_pnl_all_time is the equity identity and is the
                    # number to trust on a board.
                    "net_pnl_all_time", "realized_net_all_in",
                    "entry_fees_total", "starting_capital",
                    # hardening guards (rising = a book position or the whole
                    # cycle is wedging its own escape path — see the incidents
                    # dashboard). Emitted as gauges; 0 in steady state.
                    "exit_eval_failures", "cycle_consecutive_failures"):
            v = s.get(key)
            if isinstance(v, (int, float)):
                m.append(gauge(f"liquiditybot_{key}", v, ts=ts))
        # profit-goal progress (measurement only): goal + running attainment %
        # per period, so a Grafana panel can show goal-vs-actual live. Absent
        # goals block (older status) -> no gauges, panel reads "no data".
        for per, g in (s.get("goals") or {}).items():
            if not isinstance(g, dict):
                continue
            m.append(gauge("liquiditybot_goal_target", _num(g.get("goal")),
                           {"period": str(per)}, ts))
            att = g.get("attainment_pct")
            if isinstance(att, (int, float)):
                m.append(gauge("liquiditybot_goal_attainment_pct", att,
                               {"period": str(per)}, ts))
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
        # probe vs conviction, labelled rather than pooled: a blended
        # expectancy describes neither population. "unknown" carries
        # pre-upgrade restored trades and drains as the window rolls.
        for kind, st in (perf.get("by_conviction") or {}).items():
            if not isinstance(st, dict):
                continue
            for k in ("trades", "win_rate", "profit_factor", "expectancy_usd",
                      "net_usd", "payoff_ratio"):
                v = st.get(k)
                if isinstance(v, (int, float)):
                    m.append(gauge(f"liquiditybot_perf_conviction_{k}", v,
                                   {"kind": str(kind)}, ts))
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
        # Realized-outcome loop (2026-08-02). gate_realized_base_rate beside
        # gate_base_rate is the reward-misspecification readout in two
        # numbers: barrier labels said 0.3991 while the money said 0.038,
        # and a gate ledger learning from the first can grow MORE confident
        # as it loses. Per-gate divergence (label weight minus realized
        # weight) names WHICH gate is coasting on barrier touches.
        for k in ("realized_closed", "realized_base_rate", "realized_active",
                  "realized_min_samples"):
            v = gs.get(k)
            if isinstance(v, bool):
                v = 1.0 if v else 0.0
            if isinstance(v, (int, float)):
                m.append(gauge(f"liquiditybot_gate_{k}", float(v), ts=ts))
        for gname, dv in (gs.get("divergence") or {}).items():
            if isinstance(dv, (int, float)) and not isinstance(dv, bool):
                m.append(gauge("liquiditybot_gate_divergence", float(dv),
                               {"gate": str(gname)}, ts))
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
        # TANGIBLE-VALUE GRADIENT (regime/haven.py): where capital sits on
        # the PAXG > BTC > ETH > alts ladder. The signed gradient is the
        # number to trend (positive = capital moving toward what is
        # tangible, i.e. fear); per-rung returns show WHICH rung is doing
        # the moving; the state rides the standard *_info label pattern.
        _hv = s.get("haven") or {}
        if isinstance(_hv, dict):
            _g = _hv.get("gradient")
            if isinstance(_g, (int, float)) and not isinstance(_g, bool):
                m.append(gauge("liquiditybot_haven_gradient", float(_g),
                               ts=ts))
            _rs = _hv.get("rungs_seen")
            if isinstance(_rs, (int, float)) and not isinstance(_rs, bool):
                m.append(gauge("liquiditybot_haven_rungs_seen", float(_rs),
                               ts=ts))
            for _rung, _ret in (_hv.get("returns") or {}).items():
                if isinstance(_ret, (int, float)) and not isinstance(_ret, bool):
                    m.append(gauge("liquiditybot_haven_rung_return",
                                   float(_ret), {"rung": str(_rung)}, ts))
            m.append(gauge("liquiditybot_haven_info", 1.0,
                           {"state": str(_hv.get("state", "unknown"))}, ts))
        # entry-decision reason codes in FULL (PT/SZ families): EV-gate rejects,
        # exploration bypasses (PT-050), sizing vetoes — the per-code trend view
        for code, cnt in ((s.get("code_stats") or {}).get("entry_codes")
                          or {}).items():
            if isinstance(cnt, (int, float)) and not isinstance(cnt, bool):
                m.append(gauge("liquiditybot_code_count_detail", cnt,
                               {"code": str(code)}, ts))
        # ---- conviction formula (#120, Compounder Phase A, risk/conviction.py) --
        # admission cadence + regime breakdown + denial-code tally for the
        # CONVICTION (non-probe) entry channel. Missing/empty section (older
        # status.json predating this feature, or a writer that emits {} rather
        # than omitting the key) degrades to NOTHING emitted here — never a
        # crash, never a partial metric set that reads as a healthy subsystem.
        cv = s.get("conviction") or {}
        if cv:
            ev, ad = cv.get("evaluated"), cv.get("admitted")
            if isinstance(ev, (int, float)) and not isinstance(ev, bool):
                m.append(gauge("liquiditybot_conviction_evaluated", ev, ts=ts))
            if isinstance(ad, (int, float)) and not isinstance(ad, bool):
                m.append(gauge("liquiditybot_conviction_admitted", ad, ts=ts))
            share, n = cv.get("share"), cv.get("n")
            if isinstance(share, (int, float)) and not isinstance(share, bool):
                m.append(gauge("liquiditybot_conviction_share", share, ts=ts))
            if isinstance(n, (int, float)) and not isinstance(n, bool):
                m.append(gauge("liquiditybot_conviction_n", n, ts=ts))
            for code, cnt in (cv.get("denials") or {}).items():
                if isinstance(cnt, (int, float)) and not isinstance(cnt, bool):
                    m.append(gauge("liquiditybot_conviction_denials", cnt,
                                   {"code": str(code)}, ts))
            for regime, rec in (cv.get("by_regime") or {}).items():
                if not isinstance(rec, dict):
                    continue        # malformed regime entry: skip, never crash
                r_share, r_n = rec.get("share"), rec.get("n")
                if isinstance(r_share, (int, float)) \
                        and not isinstance(r_share, bool):
                    m.append(gauge("liquiditybot_conviction_regime_share",
                                   r_share, {"regime": str(regime)}, ts))
                if isinstance(r_n, (int, float)) and not isinstance(r_n, bool):
                    m.append(gauge("liquiditybot_conviction_regime_n", r_n,
                                   {"regime": str(regime)}, ts))
            # ok=0 / low=1 / high=2; an unrecognized string degrades to -1
            # rather than silently reading as "ok" (state() maps -1 too)
            m.append(gauge("liquiditybot_conviction_alarm",
                           {"ok": 0.0, "low": 1.0, "high": 2.0}
                           .get(str(cv.get("alarm")), -1.0), ts=ts))
        # ---- context engine (Compounder Phase B, data/context_engine.py --------
        # ContextFeed.status()) — halving clock, macro-stress dial, flow dials,
        # event-window state, per-source ok/dark map. TELEMETRY ONLY (spec §3):
        # no gate/entry/exit/sizing path reads this in this phase; status, audit
        # and gc_pusher are the sole consumers. Missing/empty section (older
        # status.json predating this feature, or a writer that emits {} rather
        # than omitting the key) degrades to NOTHING emitted here — same silent
        # degrade as the conviction block above, never a crash.
        cx = s.get("context") or {}
        if cx:
            for key, suffix in (("stress", "stress"), ("cot_z", "cot_z"),
                                ("stable_wk_pct", "stable_wk_pct"),
                                ("days_since", "days_since_halving"),
                                ("days_to_next", "days_to_next_halving")):
                v = cx.get(key)
                # honest unknown: a None dial (source dark / no prior poll) is
                # simply not emitted this pass — never a fabricated 0 (source_ok
                # below is what makes "0" and "unknown" distinguishable)
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    m.append(gauge(f"liquiditybot_context_{suffix}", v, ts=ts))
            m.append(gauge("liquiditybot_context_event_window",
                           1.0 if cx.get("in_event_window") else 0.0, ts=ts))
            sources = cx.get("sources")
            if isinstance(sources, dict):
                for source, ok in sources.items():
                    m.append(gauge("liquiditybot_context_source_ok",
                                   1.0 if ok else 0.0,
                                   {"source": str(source)}, ts))
            # one-hot: the standard *_info label pattern (see liquiditybot_
            # regime_info / liquiditybot_ml_model_info above) — only the
            # CURRENT bucket is emitted; an empty phase (no poll has run yet)
            # is honestly absent, never a fake active bucket
            phase = cx.get("halving_phase")
            if phase:
                m.append(gauge("liquiditybot_context_phase", 1.0,
                               {"phase": str(phase)}, ts))
        # ---- long-horizon accumulation book (Task C6, Compounder Phase C, -----
        # runner.py BotRunner._long_book_status()) — evidence-ladder rung +
        # ceiling, combined-envelope exposure, add cadence, live-track profit
        # factor, paper/live closed counts, last add-cycle paused/context-
        # aligned disposition. Missing/empty section (a bot built before
        # long_ladder existed, or the status writer's own except-Exception {}
        # degrade) -> NOTHING emitted here, same silent degrade as conviction/
        # context above, never a crash.
        lb = s.get("long_book") or {}
        if lb:
            rung = lb.get("rung")
            if isinstance(rung, (int, float)) and not isinstance(rung, bool):
                m.append(gauge("liquiditybot_longbook_rung", rung, ts=ts))
            ceiling = lb.get("ceiling_frac")
            if isinstance(ceiling, (int, float)) and not isinstance(ceiling, bool):
                m.append(gauge("liquiditybot_longbook_ceiling_frac", ceiling,
                               ts=ts))
            exposure = lb.get("book_exposure_usd")
            if isinstance(exposure, (int, float)) \
                    and not isinstance(exposure, bool):
                m.append(gauge("liquiditybot_longbook_exposure_usd", exposure,
                               ts=ts))
            adds = lb.get("adds_placed")
            if isinstance(adds, (int, float)) and not isinstance(adds, bool):
                m.append(gauge("liquiditybot_longbook_adds_placed", adds, ts=ts))
            for key, track in (("closed_paper", "paper"), ("closed_live", "live")):
                v = lb.get(key)
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    m.append(gauge("liquiditybot_longbook_closed", v,
                                   {"track": track}, ts))
            pf = lb.get("pf_live")
            # honest unknown: pf_live is already JSON-safe at the source
            # (runner.py rounds a finite pf, or None for the raw `inf`/no-
            # evidence read) — None is never faked as 0
            if isinstance(pf, (int, float)) and not isinstance(pf, bool):
                m.append(gauge("liquiditybot_longbook_pf_live", pf, ts=ts))
            # paused: honest 0/1 off the free-form paused_reason detail string
            # (main._long_last_deny) — "" (last add attempt succeeded, or none
            # has run yet) is unconditionally 0; ANY non-empty detail (a
            # routine spacing wait, ceiling exhaustion, halt, an event window,
            # ...) is unconditionally 1. Emitted every pass — the field is
            # always a string on a real bot, never absent/None.
            m.append(gauge("liquiditybot_longbook_paused",
                           1.0 if lb.get("paused_reason") else 0.0, ts=ts))
            # context_aligned_last: True/False/None (risk/conviction.py's own
            # None=N/A convention) — None (no cycle has run yet, or the
            # context stress dial is dark/unknown) is honestly NOT emitted,
            # never a fabricated 0/1 (Global Constraint: context before
            # conviction, CX-030 on unknown).
            ctx_aligned = lb.get("context_aligned_last")
            if isinstance(ctx_aligned, bool):
                m.append(gauge("liquiditybot_longbook_context_aligned",
                               1.0 if ctx_aligned else 0.0, ts=ts))
        for key in ("history_rows", "open_candidates", "pending_labels"):
            v = ml.get(key)
            if isinstance(v, (int, float)):
                m.append(gauge(f"liquiditybot_ml_{key}", v, ts=ts))
        for asset, v in (s.get("manip_suspect") or {}).items():
            # DL-1: this was the ONLY per-asset loop with no isinstance-numeric
            # guard; one non-numeric value raised inside collect() and blacked
            # out the ENTIRE metric batch (including the alarm gauges) every
            # tick — matches the guard every sibling per-asset loop already has.
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                m.append(gauge("liquiditybot_manip_suspect", v,
                               {"asset": asset}, ts))
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
            if not isinstance(th, dict):
                continue                    # malformed asset entry: skip, never crash
            for k in ("grid", "metronome", "clockwork", "stop_zone", "barclose",
                      "spoof_bid", "spoof_ask", "feed_dirty", "lapses",
                      "bar_holes", "lapse_warmup_sec"):
                v = th.get(k)
                # exclude bool VALUES (bool is an int subclass) — the guard must
                # test the value, not the loop key (always a str, never bool)
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    m.append(gauge(f"liquiditybot_thales_{k}", v,
                                   {"asset": asset}, ts))
        m.extend(_thales_reliability_metrics(s.get("thales") or {}, ts))
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
                               {"source": _source_label(src)}, ts))
        # deployed model rung on the simplicity ladder (info-style label gauge).
        # When no champion is loaded the bot IS the prior - say so instead of
        # going silent: after the v7 schema bump the width guard correctly
        # refused the 58-wide champion and the model panel showed "No data"
        # for hours, which read as broken telemetry (lived 2026-07-20).
        kind = ml.get("model_kind") or ("prior" if not ml.get("trained") else "")
        if kind:
            m.append(gauge("liquiditybot_ml_model_info", 1.0,
                           {"kind": str(kind)}, ts))
        # ML fault counters (fallbacks/inference faults/contract breaches/SMC
        # degrades/retrain failures) — rising = a subsystem quietly dying
        for k in ("model_fallbacks", "infer_faults", "contract_failed",
                  "smc_faults", "retrain_failures"):
            v = ml.get(k)
            if isinstance(v, (int, float)):
                m.append(gauge(f"liquiditybot_ml_{k}", v, ts=ts))
        # AFML corpus-quality stats from the last training load: clean live
        # count (what the evidence gate actually sees), mean average-uniqueness
        # (label-overlap redundancy, AFML ch.4), ML-074 one-sided-batch flag
        ls = ml.get("load_stats") or {}
        for k in ("live_clean", "mean_uniqueness", "dropped_dirty",
                  "dropped_clash"):
            v = ls.get(k)
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                m.append(gauge(f"liquiditybot_ml_{k}", v, ts=ts))
        if "prior_skew" in ls:
            m.append(gauge("liquiditybot_ml_prior_skew",
                           1.0 if ls.get("prior_skew") else 0.0, ts=ts))
        # ---- label-era transition (era-gated training exclusion, docs/quant/
        # 2026-07-26_era_exclusion.md) — armed/active decision, dropped-row
        # count, per-era/per-exit-reason row counts and label rates (the
        # 0.0066->0.3991 repair this instrumentation exists to show), and the
        # ML-080 barrier-mix drift alarm. All read from ml.load_stats (ml/
        # history.py's last_load_stats, written verbatim by runner.py).
        # load_stats == {} (a just-restarted bot, no retrain yet — observed
        # live for hours) emits NOTHING here, same silent degrade as every
        # other ls-scoped gauge above: a fabricated 0 would read as
        # "exclusion off" when the truth is "not yet measured".
        if ls:
            excl = ls.get("era_exclusion") or {}
            if excl:      # sub-block itself present (a pre-era-task status.json
                           # has ls non-empty but no era_exclusion key at all)
                m.append(gauge("liquiditybot_era_excl_armed",
                               1.0 if excl.get("armed") else 0.0, ts=ts))
                m.append(gauge("liquiditybot_era_excl_active",
                               1.0 if excl.get("active") else 0.0, ts=ts))
                new_rows = excl.get("new_era_rows")
                if isinstance(new_rows, (int, float)) \
                        and not isinstance(new_rows, bool):
                    m.append(gauge("liquiditybot_era_excl_new_rows", new_rows,
                                   ts=ts))
                min_rows = excl.get("min_new_era_rows")
                if isinstance(min_rows, (int, float)) \
                        and not isinstance(min_rows, bool):
                    m.append(gauge("liquiditybot_era_excl_min_rows", min_rows,
                                   ts=ts))
                dropped = (excl.get("excluded") or {}).get("total")
                if isinstance(dropped, (int, float)) \
                        and not isinstance(dropped, bool):
                    m.append(gauge("liquiditybot_era_excl_dropped", dropped,
                                   ts=ts))
            for era, eb in (ls.get("label_era") or {}).items():
                if not isinstance(eb, dict):
                    continue        # malformed era entry: skip, never crash
                era_lab = _era_label(era)
                rows = eb.get("rows")
                if isinstance(rows, (int, float)) and not isinstance(rows, bool):
                    m.append(gauge("liquiditybot_era_rows", rows,
                                   {"era": era_lab}, ts))
                rate = eb.get("label_rate")
                if isinstance(rate, (int, float)) and not isinstance(rate, bool):
                    m.append(gauge("liquiditybot_era_label_rate", rate,
                                   {"era": era_lab}, ts))
                for reason, rb in (eb.get("by_reason") or {}).items():
                    if not isinstance(rb, dict):
                        continue    # malformed reason entry: skip, never crash
                    reason_lab = _reason_label(reason)
                    r_rows = rb.get("rows")
                    if isinstance(r_rows, (int, float)) \
                            and not isinstance(r_rows, bool):
                        m.append(gauge("liquiditybot_era_reason_rows", r_rows,
                                       {"era": era_lab, "reason": reason_lab},
                                       ts))
                    r_rate = rb.get("label_rate")
                    if isinstance(r_rate, (int, float)) \
                            and not isinstance(r_rate, bool):
                        m.append(gauge("liquiditybot_era_reason_label_rate",
                                       r_rate,
                                       {"era": era_lab, "reason": reason_lab},
                                       ts))
            # ML-080 barrier-mix drift: tvd is None (SILENT — too few recent
            # rows to trust the mix) whenever _era_mix_drift_check declines to
            # fire; honest-unknown, never a fabricated 0/"not exceeded" — the
            # alarm gauge only ships alongside a real tvd value.
            mix = ls.get("era_mix_drift")
            if isinstance(mix, dict):
                tvd = mix.get("tvd")
                if isinstance(tvd, (int, float)) and not isinstance(tvd, bool):
                    m.append(gauge("liquiditybot_era_mix_tvd", tvd, ts=ts))
                    m.append(gauge("liquiditybot_era_mix_alarm",
                                   1.0 if mix.get("fired") else 0.0, ts=ts))
        # ML-082 labeled-vs-realized bracket comparator (geometry-alignment
        # T6, spec D6, ml/history.py's bracket_divergence_summary()) — a
        # SIBLING of load_stats above (updated at close time, not only on a
        # retrain), so it is read off `ml` directly, never `ls`. DL-6 honest
        # absence: the block missing entirely (older status.json / pre-
        # first-bracket-close) AND the block present with n==0 (the shaped
        # "not yet measured" shape bracket_divergence_summary returns)
        # BOTH emit nothing — a fabricated 0% agreement/0 count would read
        # as "every bracket close disagreed" instead of "none measured
        # yet". No labels: single portfolio-wide window, not per-asset.
        bd = ml.get("bracket_divergence") or {}
        bd_n = bd.get("n")
        if isinstance(bd_n, (int, float)) and not isinstance(bd_n, bool) \
                and bd_n > 0:
            m.append(gauge("liquiditybot_bracket_divergence_n", bd_n, ts=ts))
            rate = bd.get("agree_rate")
            if isinstance(rate, (int, float)) and not isinstance(rate, bool):
                m.append(gauge("liquiditybot_bracket_divergence_rate", rate,
                               ts=ts))
        # SPB-R probe budget (status.ml.probe_budget, spec §8) - see the
        # extracted helper for the emission contract
        m.extend(_probe_budget_metrics(ml.get("probe_budget") or {}, ts))
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
                  "avg_slip_bps", "worst_slip_bps",
                  # 2026-07-29 wave-2/3 verify: the notional-weighted
                  # slip shipped in f877de0 never made this whitelist -
                  # the Cochran ratio-of-sums estimator was invisible in
                  # Grafana while the dust-skewed simple mean kept the
                  # panel
                  "slip_bps_notional_weighted"):
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
                  "taper_mult", "heat_frac", "heat_cap_frac",
                  "dd_throttle_mult", "drawdown_mtm_pct", "hard_stop_dd_pct"):
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
        kept = [x for x in m
                if math.isfinite(x["gauge"]["dataPoints"][0]["asDouble"])]
        # DL6-D: a NaN/inf gauge dropped by the finiteness filter above used to
        # vanish with no trace — a sudden NaN storm reads identically to "no
        # problem". Count what the filter dropped so it is visible instead of
        # silent; 0.0 in steady state, like every other always-on counter here.
        kept.append(gauge("liquiditybot_gauges_dropped_nonfinite",
                           float(len(m) - len(kept)), ts=ts))
        return kept
    except Exception:
        # Blanket backstop, not per-site hardening (~20 (s.get(X) or {}).
        # items() sites above): a status.json that PARSES but has the
        # wrong shape (top-level null/list, "goals" as a list,
        # "positions" as an int, written_at as a non-numeric string, ...)
        # used to raise OUT of collect() — main()'s push(cfg, collect(...))
        # is one expression, so push() never ran and ZERO gauges shipped,
        # not even the alarm batch. Degraded truth beats silence.
        log.exception("gc_pusher: malformed status.json shape at %s",
                      status_path)
        now = time.time()
        return [gauge("liquiditybot_status_malformed", 1.0, ts=now),
                gauge("liquiditybot_running", 0.0, ts=now),
                gauge("liquiditybot_status_stale", 1.0, ts=now),
                gauge("liquiditybot_status_missing", 0.0, ts=now)]


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


# Restart-coupling: the supervisor relaunches this sidecar only when it
# DIES (stale heartbeat log) - the auto-updater's restart signal reaches
# the runner alone, so a long-lived pusher kept exporting an old gauge
# set forever after every deploy (lived 2026-07-20: the profit-pools row
# showed "No data" all day; the runner carried the values, this process
# predated the gauges). Exit when our own source changes on disk and let
# the supervisor bring us back on the new code.
_BOOT_MTIME = os.path.getmtime(os.path.abspath(__file__))


def _source_changed() -> bool:
    """True once scripts/gc_pusher.py on disk differs from the running
    copy (mtime moved - a git fast-forward touched it). Read failures
    count as unchanged: staying alive is the fail-safe, and the
    auto-updater's rev-marker bounce is the backstop."""
    try:
        return os.path.getmtime(os.path.abspath(__file__)) != _BOOT_MTIME
    except OSError:
        return False


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
        if _source_changed():
            print(f"{time.strftime('%H:%M:%S')} source changed on disk "
                  f"(deploy) - exiting; supervisor relaunches on new code",
                  flush=True)
            return
        time.sleep(cfg["period"])


if __name__ == "__main__":
    main()
