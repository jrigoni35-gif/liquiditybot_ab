"""
ui/dashboard.py — liquiditybot operator console (Streamlit)

Reads outputs/status.json, equity.csv, events.jsonl, audit.jsonl, and
postmortem files. Sends commands by dropping JSON into
outputs/control/ — the runner consumes them between cycles. Never
imports the engine; never touches an exchange. If the runner dies,
this shows a stale banner; if this dies, the bot doesn't notice.

Safety surfaced in the UI:
  * Mode badge always visible: DRY RUN / LIVE (DISARMED) / LIVE (ARMED).
  * Arming live requires config dry_run=false AND typing the exact ARM
    phrase. Disarm is one click; arming never is.
  * Simulation controls only render in dry run.
  * Withdrawals impossible by construction (endpoint deny list).
"""

import csv
import json
import sys
import time
from datetime import datetime
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.runtime import ARM_PHRASE, ControlChannel, read_json, tail_events  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"
STATUS = OUT / "status.json"
EQUITY = OUT / "equity.csv"
PM_SUMMARY = OUT / "postmortem_summary.csv"
AUDIT = OUT / "audit.jsonl"

st.set_page_config(page_title="liquiditybot", page_icon="💧", layout="wide",
                   initial_sidebar_state="expanded")
control = ControlChannel(str(OUT / "control"))


# ---- helpers ---------------------------------------------------------------


def load_status():
    return read_json(STATUS)


def stale_seconds(s: dict) -> float:
    if not s:
        return 1e9
    return time.time() - float(s.get("written_at", 0))


def fmt_usd(x, sig=2) -> str:
    try:
        return f"${float(x):,.{sig}f}"
    except (TypeError, ValueError):
        return "—"


def fmt_pct(x, sig=2, signed=False) -> str:
    try:
        v = float(x)
        return f"{v:+.{sig}f}%" if signed else f"{v:.{sig}f}%"
    except (TypeError, ValueError):
        return "—"


def mode_style(mode: str) -> tuple:
    if mode == "DRY_RUN":
        return ("DRY RUN", "#3b82f6",
                "Simulated fills only. No real orders reach any venue.")
    if mode == "LIVE_DISARMED":
        return ("LIVE — DISARMED", "#f59e0b",
                "Connected to real venue. Entries BLOCKED until armed. "
                "Exits and hedge-unwinds still run.")
    if mode == "LIVE_ARMED":
        return ("LIVE — ARMED", "#ef4444",
                "Real orders are being placed. Withdrawals are impossible "
                "at the code level.")
    return (mode or "UNKNOWN", "#6b7280", "")


def runner_style(state: str | None) -> tuple:
    return {"RUNNING": ("▶ RUNNING", "#10b981"),
            "PAUSED": ("⏸ PAUSED", "#f59e0b"),
            "STOPPED": ("■ STOPPED", "#6b7280")}.get(
                state or "", (state or "?", "#6b7280"))


def read_csv_dicts(path: Path) -> list:
    """Best-effort CSV -> list[dict]; [] on any problem (UI never raises)."""
    if not path.exists():
        return []
    try:
        with open(path, encoding="utf-8") as f:
            return list(csv.DictReader(f))
    except OSError:
        return []


# ---- sidebar ---------------------------------------------------------------


@st.fragment(run_every=2)
def sidebar_live_strip():
    """Auto-refreshing status strip + loop/entry controls. Lives in a
    fragment so the staleness indicator and button enable/disable state
    track the runner without requiring a click."""
    s = load_status() or {}
    stale = stale_seconds(s)
    if stale > 10:
        st.error(f"runner stale ({min(stale, 9999):.0f}s) — is it running?")
    else:
        st.success(f"runner OK ({stale:.1f}s ago)")
    r_label, r_color = runner_style(s.get("runner_state"))
    st.markdown(
        f"<span style='color:{r_color};font-weight:700'>{r_label}</span>"
        f"&nbsp;&nbsp;cycle {s.get('cycle', 0)}",
        unsafe_allow_html=True)

    st.markdown("### Loop")
    c1, c2 = st.columns(2)
    if c1.button("▶ Start", width="stretch"):
        control.send("start")
        st.toast("start sent")
    if c2.button("⏸ Pause", width="stretch"):
        control.send("pause")
        st.toast("pause sent")
    c3, c4 = st.columns(2)
    if c3.button("⏭ Step", width="stretch"):
        control.send("step")
        st.toast("step sent")
    if c4.button("💾 Snapshot", width="stretch"):
        control.send("snapshot")
        st.toast("snapshot sent")

    st.markdown("### Entries")
    entries_on = bool(s.get("entries_enabled", True))
    e1, e2 = st.columns(2)
    if e1.button("Entries ON", width="stretch", disabled=entries_on):
        control.send("entries_on")
    if e2.button("Entries OFF", width="stretch", disabled=not entries_on):
        control.send("entries_off")
    st.caption(
        f"currently **{'ENABLED' if entries_on else 'DISABLED'}** "
        "(exits and hedge-unwinds are never blocked)")


def sidebar_static(s: dict):
    """Confirm-gated and typed-input controls stay OUTSIDE the auto-
    refreshing fragment so reruns can't interrupt typing the ARM phrase
    or a pending flatten confirmation."""
    st.sidebar.markdown("### Flatten")
    if st.sidebar.button("🧹 Flatten ALL positions", width="stretch",
                         type="secondary"):
        st.session_state["confirm_flatten"] = True
    if st.session_state.get("confirm_flatten"):
        st.sidebar.warning("Confirm: closes every open position at market.")
        cf1, cf2 = st.sidebar.columns(2)
        if cf1.button("Yes, flatten", width="stretch"):
            control.send("flatten_all")
            st.session_state["confirm_flatten"] = False
            st.toast("flatten sent")
        if cf2.button("Cancel", width="stretch"):
            st.session_state["confirm_flatten"] = False

    mode = s.get("mode", "DRY_RUN")
    if mode != "DRY_RUN":
        st.sidebar.markdown("### Live trading gate")
        if st.sidebar.button("🛟 FORCE DRY-RUN", width="stretch",
                             help="One-way. Seals live order paths now; "
                                  "venue dead-man cancels resting orders. "
                                  "Returning to live requires config "
                                  "dry_run=false + restart + ARM phrase."):
            control.send("force_dry")
            st.toast("force_dry sent — live paths sealed")
        if mode == "LIVE_ARMED":
            if st.sidebar.button("🔒 DISARM now", type="primary",
                                 width="stretch"):
                control.send("disarm_live")
                st.toast("disarm sent")
        else:
            phrase = st.sidebar.text_input(
                f"Type the ARM phrase exactly: **{ARM_PHRASE}**", value="",
                key="arm_phrase")
            if st.sidebar.button("Arm live trading",
                                 disabled=(phrase != ARM_PHRASE),
                                 width="stretch"):
                control.send("arm_live", {"confirm": phrase})
                st.toast("arm sent")

    if mode == "DRY_RUN":
        st.sidebar.caption("🛟 DRY RUN — this interface cannot place real "
                           "orders. Going live requires config "
                           "dry_run=false, a restart, and the typed ARM "
                           "phrase. Withdrawals are impossible in any mode.")
        st.sidebar.markdown("### Simulate (dry run only)")
        assets = list((s.get("regimes") or {}).keys()) or ["ETH", "BTC"]
        sim_asset = st.sidebar.selectbox("Asset", assets, key="sim_asset")
        shock_pct = st.sidebar.slider("Price shock %", -30.0, 30.0, -8.0,
                                      step=0.5)
        cycles = st.sidebar.number_input("Over how many cycles", 1, 24, 3,
                                         key="sim_cycles")
        if st.sidebar.button("Fire shock", width="stretch"):
            control.send("sim_price_shock",
                         {"asset": sim_asset, "pct": shock_pct,
                          "cycles": int(cycles)})
        if st.sidebar.button("Fear-spike (6 cycles)", width="stretch"):
            control.send("sim_force_fear", {"cycles": 6})
        regime = st.sidebar.selectbox(
            "Force regime", ["crisis", "bear", "range", "bull_quiet",
                             "bull_vol"], key="sim_regime")
        r1, r2 = st.sidebar.columns(2)
        if r1.button("Force regime", width="stretch"):
            control.send("sim_force_regime",
                         {"asset": sim_asset, "label": regime, "cycles": 12})
        if r2.button("Clear sim", width="stretch"):
            control.send("sim_clear")


# ---- header ----------------------------------------------------------------


def header(s: dict):
    mode = s.get("mode", "UNKNOWN")
    label, color, tip = mode_style(mode)
    r_label, r_color = runner_style(s.get("runner_state"))
    halted = bool(s.get("halted", False))
    dd = float(s.get("drawdown_pct", 0.0))
    n_pos = len(s.get("positions") or [])
    n_ord = len(s.get("open_orders") or [])
    updated = time.strftime("%H:%M:%S",
                            time.localtime(float(s.get("written_at", 0))))

    left, mid, right = st.columns([2, 3, 3])
    with left:
        st.markdown(
            f"<div style='background:{color};color:white;padding:12px 16px;"
            f"border-radius:8px;font-weight:700;font-size:16px;"
            f"line-height:1.1'>{label}"
            f"<div style='font-weight:400;font-size:11px;opacity:0.9;"
            f"margin-top:4px'>{tip}</div></div>",
            unsafe_allow_html=True)
        st.markdown(
            f"<div style='margin-top:6px;font-size:13px'>"
            f"<span style='color:{r_color};font-weight:700'>{r_label}</span>"
            f" · {n_pos} position{'s' if n_pos != 1 else ''}"
            f" · {n_ord} order{'s' if n_ord != 1 else ''}"
            f" · updated {updated}</div>",
            unsafe_allow_html=True)
    with mid:
        c1, c2, c3 = st.columns(3)
        c1.metric("Equity", fmt_usd(s.get("equity")),
                  f"realized {fmt_usd(s.get('realized_total'))}")
        c2.metric("Daily PnL", fmt_usd(s.get("daily_pnl")))
        c3.metric("Drawdown", fmt_pct(dd),
                  delta_color=("inverse" if dd > 0 else "off"))
    with right:
        c1, c2, c3 = st.columns(3)
        c1.metric("Cycle", s.get("cycle", 0))
        c2.metric("Latency", f"{float(s.get('latency_ms', 0)):.0f} ms")
        c3.metric("Fees", fmt_usd(s.get("fees_total")))

    if halted:
        st.error("⚠ HALTED — hard-stop drawdown breached. Manual reset "
                 "required.")


# ---- panels ----------------------------------------------------------------


def trade_stats_panel():
    """Closed-trade scoreboard from the postmortem summary."""
    rows = read_csv_dicts(PM_SUMMARY)
    if not rows:
        return
    rets, wins, stops = [], 0, 0
    for r in rows:
        try:
            v = float(r.get("realized_pct") or 0.0)
        except (TypeError, ValueError):
            continue
        rets.append(v)
        wins += v > 0
        stops += (r.get("cause") or "").startswith("stop")
    if not rets:
        return
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Closed trades", len(rets))
    c2.metric("Win rate", f"{wins / len(rets):.0%}")
    c3.metric("Avg realized", fmt_pct(sum(rets) / len(rets), signed=True))
    c4.metric("Stop-outs", stops)


def positions_panel(s: dict):
    positions = s.get("positions") or []
    st.subheader(f"Open positions ({len(positions)})")
    if not positions:
        st.info("No open positions.")
        return
    rows, total_upnl = [], 0.0
    for p in positions:
        entry = float(p.get("entry_price") or 0)
        mark = float(p.get("mark") or entry)
        size = float(p.get("size") or 0)
        sgn = -1.0 if p.get("direction") == "short" else 1.0
        upnl_usd = sgn * (mark - entry) * size
        upnl_pct = sgn * ((mark - entry) / entry * 100.0) if entry else 0.0
        total_upnl += upnl_usd
        rows.append({
            "symbol": p.get("symbol"),
            "dir": p.get("direction"),
            "size": size,
            "entry": entry,
            "mark": mark,
            "uPnL $": round(upnl_usd, 2),
            "uPnL %": round(upnl_pct, 2),
            "stop": p.get("stop_price"),
            "tier": p.get("tier_closed", 0),
            "hedge": p.get("is_hedge", False),
            "p_win": p.get("p_win"),
        })
    st.dataframe(rows, width="stretch", hide_index=True)
    st.caption(f"Total unrealized: **{fmt_usd(total_upnl)}**")


def orders_panel(s: dict):
    orders = s.get("open_orders") or []
    st.subheader(f"Working orders ({len(orders)})")
    if not orders:
        st.caption("No resting or in-flight orders.")
        return
    st.dataframe([{
        "pair": o.get("pair"),
        "side": o.get("side"),
        "size": o.get("size"),
        "price": o.get("price"),
        "purpose": o.get("purpose"),
        "status": o.get("status"),
        "fills": f"{o.get('filled', 0)}/{o.get('size', 0)}",
    } for o in orders], width="stretch", hide_index=True)


def equity_chart():
    if not EQUITY.exists():
        st.caption("No equity history yet.")
        return
    try:
        with open(EQUITY, encoding="utf-8") as f:
            rows = list(csv.reader(f))
        if len(rows) < 2:
            st.caption("Warming up (need >=2 samples).")
            return
        head, data = rows[0], rows[1:]
        idx = head.index("equity") if "equity" in head else 1
        ts_idx = head.index("ts") if "ts" in head else 0
        eq = [{"time": datetime.fromtimestamp(float(r[ts_idx])),
               "equity": float(r[idx])}
              for r in data[-720:] if len(r) > max(idx, ts_idx)]
    except (OSError, ValueError, IndexError, OverflowError):
        st.warning("equity.csv unreadable")
        return
    if not eq:
        return
    st.line_chart(eq, x="time", y="equity", height=240)


def monitor_panel(s: dict):
    mon = s.get("monitor") or {}
    ml = s.get("ml") or {}
    lvl = int(mon.get("level", 0))
    lvl_label = {0: "🟢 HEALTHY", 1: "🟡 DEGRADED",
                 2: "🔴 KILL SWITCH ACTIVE"}.get(lvl, "?")
    st.markdown(f"**Governor:** {lvl_label}")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Shrinkage", f"{mon.get('shrinkage', 0):.2f}")
    c2.metric("Kelly mult", f"{mon.get('kelly_mult', 1.0):.2f}")
    c3.metric("Use model", "yes" if mon.get("use_model") else "NO")
    c4.metric("Trained", "yes" if ml.get("trained") else "cold-start prior")

    if mon.get("window_trades"):
        c1, c2, c3 = st.columns(3)
        c1.metric("Rolling Brier", f"{mon.get('brier', 0):.3f}",
                  f"baseline {mon.get('baseline_brier', 0):.3f}")
        c2.metric("Hit rate", f"{mon.get('hit_rate', 0):.2f}",
                  f"promised {mon.get('avg_p', 0):.2f}")
        c3.metric("Calibration gap",
                  f"{mon.get('calibration_gap', 0):.3f}")

    # learning pipeline: is training data actually flowing? A starved model
    # (0 rows accruing) is the difference between "learning" and "idling".
    st.markdown("**Learning pipeline**")
    l1, l2, l3, l4 = st.columns(4)
    l1.metric("Training rows", f"{ml.get('history_rows', 0)}")
    l2.metric("Awaiting close label", f"{ml.get('pending_labels', 0)}")
    l3.metric("Open candidates", f"{ml.get('open_candidates', 0)}",
              help="Gate-confirmed signals (taken AND vetoed) waiting for "
                   "their triple-barrier outcome — the unbiased dataset "
                   "the model retrains on.")
    l4.metric("Model", ml.get("model_kind") or "—")

    drift_share = float(mon.get("drift_share", 0.0))
    if drift_share > 0:
        st.progress(min(drift_share, 1.0),
                    text=f"Input drift: {drift_share:.0%} of features "
                         f"shifted "
                         f"{', '.join(mon.get('drifting_features', [])[:5])}")
    if ml.get("retrain_flag"):
        st.warning("Retrain requested — run scripts/train_meta.py or "
                   "wait for auto-retrain on next slow cycle.")


def regimes_panel(s: dict):
    regs = s.get("regimes") or {}
    if not regs:
        st.caption("No regime data yet.")
        return
    st.dataframe([{
        "asset": k,
        "regime": v.get("regime"),
        "vol σ/day": f"{v.get('sigma_daily_pct', 0):.2f}%",
        "liquidity": v.get("liquidity"),
        "spread bps": v.get("spread_bps"),
        "FV basis bps": v.get("basis_bps"),
    } for k, v in regs.items()], width="stretch", hide_index=True)


def signal_engine_panel(s: dict):
    """rev-3 evidence-fusion state per asset: what the engine saw on the
    latest evaluation, confirmed or not."""
    sigs = s.get("signals") or {}
    if not sigs:
        return
    st.markdown("**Signal engine (evidence fusion)**")
    rows = []
    for asset, d in sorted(sigs.items()):
        gates = d.get("gates") or {}
        passed = sum(1 for x in gates.values() if x)
        failed = [k.replace("if_", "").replace("v3_", "")
                  for k, x in gates.items() if not x]
        rows.append({
            "asset": asset,
            "state": ("✅ " + (d.get("direction") or "?").upper())
                     if d.get("confirmed") else "—",
            "confidence": f"{d.get('confidence', 0):.2f}",
            "urgency": f"{d.get('urgency', 0):.2f}",
            "gates": f"{passed}/{len(gates)}" if gates else "n/a",
            "blocking": ", ".join(failed[:3]) if failed else "",
        })
    st.dataframe(rows, width="stretch", hide_index=True)


def signals_panel(s: dict):
    sent = s.get("sentiment") or {}
    web = s.get("webdata") or {}
    risk = s.get("moomoo") or {}
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("**Sentiment (free feeds)**")
        if sent.get("available"):
            score = float(sent.get("score", 0))
            st.metric("Blended score", f"{score:+.2f}",
                      "fear" if sent.get("fear")
                      else "euphoria" if sent.get("euphoria")
                      else "neutral")
        else:
            st.caption("Feed unavailable.")
    with c2:
        st.markdown("**Crypto web data**")
        if web.get("available"):
            st.metric("Fear & Greed", f"{web.get('fear_greed', 0):.0f}")
            st.metric("BTC dominance", f"{web.get('btc_dominance', 0):.1f}%",
                      f"{web.get('dominance_delta', 0):+.2f}%")
        else:
            st.caption("Feed unavailable.")
    with c3:
        st.markdown("**Risk equities (moomoo)**")
        if risk.get("available"):
            z = float(risk.get("risk_z", 0))
            st.metric("Basket z", f"{z:+.2f}",
                      f"{risk.get('basket_ret_pct', 0):+.2f}% return")
        else:
            st.caption("Feed unavailable.")


def audit_panel():
    if not AUDIT.exists():
        st.caption("No audit records yet.")
        return
    code_filter = st.text_input(
        "Filter by reason-code prefix (e.g. FW-, OM-, SZ-)", value="",
        key="audit_filter").strip().upper()
    try:
        with open(AUDIT, encoding="utf-8") as f:
            lines = f.readlines()[-400:]
    except OSError:
        st.warning("audit.jsonl unreadable")
        return
    rows = []
    for ln in reversed(lines):
        try:
            r = json.loads(ln)
        except ValueError:
            continue
        code = str(r.get("code", ""))
        if code_filter and not code.upper().startswith(code_filter):
            continue
        rows.append({
            "seq": r.get("seq"),
            "ts": time.strftime("%H:%M:%S",
                                time.localtime(r.get("ts", 0))),
            "src": r.get("src"),
            "code": code,
            "msg": r.get("msg", "")[:100],
        })
        if len(rows) >= 30:
            break
    if not rows:
        st.caption("No matching audit records.")
        return
    st.dataframe(rows, width="stretch", hide_index=True)


def postmortem_panel():
    rows = read_csv_dicts(PM_SUMMARY)
    if not rows:
        st.caption("No postmortem summary yet (need >=1 closed trade).")
        return
    show = rows[-20:][::-1]
    st.dataframe(show, width="stretch", hide_index=True)
    st.caption(f"Most recent {len(show)} of {len(rows)} closed trades. "
               f"Full reports in outputs/postmortems/.")


def events_panel():
    f1, f2 = st.columns([1, 3])
    with f1:
        min_level = st.selectbox("Min level", ["INFO", "WARNING", "ERROR"],
                                 index=0, key="ev_level")
    with f2:
        needle = st.text_input("Search", value="", key="ev_search",
                               placeholder="substring in source/message")
    events = tail_events(str(OUT / "events.jsonl"), min_level=min_level)
    if not events:
        st.caption("No events yet.")
        return
    n_warn = sum(1 for e in events
                 if e.get("level") in ("WARNING", "ERROR", "CRITICAL"))
    if n_warn:
        st.caption(f"⚠ {n_warn} warning/error events in the last "
                   f"{len(events)} records")
    rows = []
    needle_l = needle.strip().lower()
    for e in reversed(events):
        src = e.get("name", "").replace("liquiditybot.", "")
        msg = e.get("msg", "")
        if needle_l and needle_l not in src.lower() \
                and needle_l not in msg.lower():
            continue
        rows.append({
            "time": time.strftime("%H:%M:%S",
                                  time.localtime(e.get("ts", 0))),
            "level": e.get("level"),
            "source": src,
            "message": msg[:120],
        })
        if len(rows) >= 40:
            break
    if not rows:
        st.caption("No matching events.")
        return
    st.dataframe(rows, width="stretch", hide_index=True)


# ---- layout ----------------------------------------------------------------


@st.fragment(run_every=2)
def live_view():
    s = load_status()
    if not s:
        st.warning("Waiting for outputs/status.json — start the runner: "
                   "`python runner.py` (or start.bat / start.sh).")
        return
    header(s)
    st.divider()

    tabs = st.tabs(["📊 Overview", "📈 Model & Governor",
                    "🌐 Signals & Regime", "🧾 Audit & Events",
                    "🔬 Postmortems"])
    with tabs[0]:
        trade_stats_panel()
        c1, c2 = st.columns([3, 2])
        with c1:
            equity_chart()
            positions_panel(s)
            orders_panel(s)
        with c2:
            signals_panel(s)
            signal_engine_panel(s)
    with tabs[1]:
        monitor_panel(s)
    with tabs[2]:
        regimes_panel(s)
        st.divider()
        signals_panel(s)
        signal_engine_panel(s)
    with tabs[3]:
        st.markdown("**Audit chain (last records — hash-chained, "
                    "tamper-evident)**")
        audit_panel()
        st.divider()
        st.markdown("**Events**")
        events_panel()
    with tabs[4]:
        postmortem_panel()


def main():
    s = load_status() or {}
    with st.sidebar:
        st.title("Controls")
        sidebar_live_strip()
    sidebar_static(s)
    live_view()


main()
