"""scripts/glass_console.py — the liquid-glass operator console, box-rendered.

WHAT THIS IS. A presentation layer for the shared state files (the same
atomic snapshots Grafana's pushers read: outputs/status.json, fills.csv,
equity.csv) rendered as ONE self-contained HTML file the operator opens in
any browser. Grafana stays the PAGER and the forensic/history layer (its
alerting, retention and phone access are the load-bearing parts); this
console is where the design language lives unconstrained — the liquid-glass
treatment executed natively instead of injected through a third-party
panel's afterRender hook (the mechanism behind the 2026-08-30 black-screen
and glitching incidents).

Out-of-process by construction (CLAUDE.md architecture law): reads shared
state, writes outputs/console.html, never touches the engine, the runner,
or an order. SAFE class. No network, no server, no external assets — the
page works offline over file:// and auto-reloads via <meta refresh>; fresh
DATA appears when this script re-renders the file.

    python scripts/glass_console.py              # render once, print path
    python scripts/glass_console.py --open       # render once + open browser
    python scripts/glass_console.py --loop 30    # re-render every 30s
                                                 # (foreground; Ctrl-C exits —
                                                 # documented in README
                                                 # "Scripting inputs")

Honesty rules baked in: every page carries its RENDERED instant and the
status.json snapshot ts (values are as-of, never "current"); absent inputs
degrade to labeled placeholders, never invented numbers; all strings from
state files are HTML-escaped before they touch the page.
"""
from __future__ import annotations

import argparse
import csv
import html
import json
import sys
import time
import webbrowser
from pathlib import Path
from string import Template

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "console.html"
STATUS = ROOT / "outputs" / "status.json"
FILLS = ROOT / "outputs" / "fills.csv"
EQUITY = ROOT / "outputs" / "equity.csv"

# The CURRENT execution era — feed shows only rows a binary carrying the
# current constant wrote. Import kept soft so the console renders even on a
# tree where core is mid-edit; the constant is the single source of truth.
try:
    from core.fill_ledger import EXEC_ERA
except Exception:                                            # pragma: no cover
    EXEC_ERA = "9-16ec821e"

# Apple dark-variant system palette — the same map the Grafana generator
# applies (_APPLE in build_trading_dashboard.py). One visual language.
C = {"green": "#30D158", "red": "#FF453A", "orange": "#FF9F0A",
     "yellow": "#FFD60A", "blue": "#0A84FF", "indigo": "#5E5CE6",
     "cyan": "#40CBE0"}

EQUITY_TAIL_BYTES = 96 * 1024        # ~last few hours at 1 row/min
FILLS_FEED_MAX = 14
REGIME_ORDER = ["BTC", "ETH", "SOL", "XRP", "LINK", "DOGE", "DOT", "ARB",
                "SUI", "MINA", "FLOW", "PAXG"]


def esc(v) -> str:
    return html.escape(str(v), quote=True)


def _num(v, default=None):
    try:
        f = float(v)
        return f if f == f and abs(f) != float("inf") else default
    except (TypeError, ValueError):
        return default


def load_status() -> dict:
    try:
        return json.loads(STATUS.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def load_equity_tail() -> list[tuple[float, float]]:
    """(ts, equity) points from the file tail — never the whole MB-scale
    file. Seeks back EQUITY_TAIL_BYTES and drops the first (torn) line."""
    try:
        size = EQUITY.stat().st_size
        with open(EQUITY, "rb") as f:
            if size > EQUITY_TAIL_BYTES:
                f.seek(size - EQUITY_TAIL_BYTES)
            raw = f.read().decode("utf-8", errors="replace")
        lines = raw.splitlines()[1:]
        pts = []
        for ln in lines:
            parts = ln.split(",")
            if len(parts) < 2:
                continue
            ts, eq = _num(parts[0]), _num(parts[1])
            if ts and eq:
                pts.append((ts, eq))
        return pts
    except OSError:
        return []


def load_era_fills() -> list[dict]:
    try:
        with open(FILLS, newline="", encoding="utf-8") as f:
            return [r for r in csv.DictReader(f)
                    if r.get("exec_era") == EXEC_ERA]
    except OSError:
        return []


def fmt_usd(v, signed=False) -> str:
    n = _num(v)
    if n is None:
        return "—"
    sign = "+" if (signed and n > 0) else ""
    return f"{sign}{n:,.2f}"


def pnl_cls(v) -> str:
    n = _num(v)
    if n is None:
        return "dim"
    return "up" if n > 0 else ("down" if n < 0 else "dim")


def _macro_color(macro: str) -> str:
    return {"bull_quiet": C["green"], "bull_volatile": C["yellow"],
            "bear": C["red"], "crisis": C["red"], "range": C["blue"],
            "drift_down": C["orange"]}.get(macro, "rgba(235,235,245,.35)")


def build(now: float | None = None) -> str:
    now = now or time.time()
    s = load_status()
    eq_pts = load_equity_tail()
    fills = load_era_fills()

    status_ts = _num(s.get("ts")) or _num(s.get("timestamp"))
    age = (now - status_ts) if status_ts else None
    stale = age is None or age > 180
    equity = _num(s.get("equity"))

    # ---- hero -------------------------------------------------------------
    live_dot = C["orange"] if stale else (
        C["green"] if s.get("runner_state") == "RUNNING" else C["red"])
    state_line = esc(f"{s.get('runner_state', 'UNKNOWN')} · "
                     f"{s.get('mode', '?')}")
    age_line = ("status age %ds" % age) if age is not None else "status MISSING"

    # ---- positions --------------------------------------------------------
    pos_rows = []
    for p in (s.get("positions") or []):
        upnl = _num(p.get("upnl_usd"))
        pos_rows.append(
            "<tr><td class='sym'>{sym}</td><td class='side {sc}'>{side}</td>"
            "<td class='num'>{entry}</td><td class='num'>{mark}</td>"
            "<td class='num {pc}'>{upnl}</td>"
            "<td class='num {pc}'>{upct}%</td><td class='num dim'>{age}h</td>"
            "</tr>".format(
                sym=esc(p.get("symbol", "?")),
                sc="up" if p.get("direction") == "long" else "down",
                side=esc(p.get("direction", "?")),
                entry=esc(fmt_usd(p.get("entry"))),
                mark=esc(fmt_usd(p.get("mark"))),
                pc=pnl_cls(upnl), upnl=esc(fmt_usd(upnl, signed=True)),
                upct=esc(fmt_usd(p.get("upnl_pct"), signed=True)),
                age=esc(f"{_num(p.get('age_h'), 0):.0f}")))
    pos_html = ("<table><thead><tr><th>asset</th><th>side</th><th>entry</th>"
                "<th>mark</th><th>upnl $</th><th>upnl %</th><th>age</th>"
                "</tr></thead><tbody>" + "".join(pos_rows) +
                "</tbody></table>") if pos_rows else \
        "<div class='empty'>book flat — no open positions</div>"

    # ---- era feed ---------------------------------------------------------
    feed_rows = []
    for r in fills[-FILLS_FEED_MAX:][::-1]:
        ts = _num(r.get("ts"))
        feed_rows.append(
            "<div class='fill'><span class='mono dim'>{t}</span>"
            "<span class='sym'>{sym}</span>"
            "<span class='side {sc}'>{side}</span>"
            "<span class='dim'>{purpose}</span>"
            "<span class='num'>{size} @ {px}</span>"
            "<span class='num dim'>fee {fee}</span></div>".format(
                t=time.strftime("%H:%MZ", time.gmtime(ts)) if ts else "—",
                sym=esc(r.get("symbol", "?")),
                sc="up" if r.get("side") == "buy" else "down",
                side=esc(r.get("side", "?")), purpose=esc(r.get("purpose", "")),
                size=esc(r.get("fill_size", "?")),
                px=esc(r.get("fill_price", "?")),
                fee=esc(fmt_usd(r.get("fees_delta_usd")))))
    feed_html = "".join(feed_rows) or \
        "<div class='empty'>no fills stamped %s yet</div>" % esc(EXEC_ERA)

    # ---- regimes ----------------------------------------------------------
    regimes = s.get("regimes") or {}
    reg_cells = []
    for a in REGIME_ORDER + sorted(set(regimes) - set(REGIME_ORDER)):
        r = regimes.get(a)
        if not isinstance(r, dict):
            continue
        macro = str(r.get("macro", "?"))
        spoof = _num(r.get("spoof"), 0) or 0
        reg_cells.append(
            "<div class='chip'><span class='dot' style='background:{c}'>"
            "</span><b>{a}</b><span class='dim'>{m}</span>"
            "<span class='dim'>{sp}</span></div>".format(
                c=_macro_color(macro), a=esc(a), m=esc(macro),
                sp=("spoof %.0f%%" % (spoof * 100)) if spoof >= .5 else ""))
    reg_html = "".join(reg_cells) or "<div class='empty'>no regime data</div>"

    # ---- learning / monitor ----------------------------------------------
    mon = s.get("monitor") or {}
    ml = s.get("ml") or {}
    brier, base = _num(mon.get("brier")), _num(mon.get("baseline_brier"))
    edge = (base - brier) if (brier is not None and base is not None) else None
    tiles = [
        ("model brier", f"{brier:.4f}" if brier is not None else "—",
         "vs naive %+.4f" % edge if edge is not None else "unjudgeable",
         "up" if (edge or 0) > 0 else "dim"),
        ("drift share", "%.0f%%" % (100 * _num(mon.get("drift_share"), 0)),
         "governor level %s" % esc(mon.get("level", "—")),
         "down" if _num(mon.get("drift_share"), 0) > .3 else "dim"),
        ("corpus rows", f"{_num(ml.get('history_rows'), 0):,.0f}",
         "%s pending labels" % esc(ml.get("pending_labels", "—")), "dim"),
        ("kelly mult", esc(mon.get("kelly_mult", "—")),
         "shrinkage %.2f" % _num(mon.get("shrinkage"), 0), "dim"),
    ]
    tile_html = "".join(
        "<div class='tile'><label>{l}</label><b class='{c}'>{v}</b>"
        "<span class='dim'>{s}</span></div>".format(l=esc(t[0]), v=esc(t[1]),
                                                    s=esc(t[2]), c=t[3])
        for t in tiles)

    # ---- data for the canvas chart ---------------------------------------
    chart = json.dumps([[round(t), round(v, 2)] for t, v in eq_pts])

    page = Template(_TEMPLATE).substitute(
        GREEN=C["green"], RED=C["red"], ORANGE=C["orange"], BLUE=C["blue"],
        INDIGO=C["indigo"], CYAN=C["cyan"],
        LIVE_DOT=live_dot, STATE=state_line, AGE=esc(age_line),
        RENDERED=time.strftime("%Y-%m-%d %H:%M:%SZ", time.gmtime(now)),
        EQUITY=esc(fmt_usd(equity)),
        DAY=esc(fmt_usd(s.get("daily_pnl"), signed=True)),
        DAY_CLS=pnl_cls(s.get("daily_pnl")),
        WEEK=esc(fmt_usd(s.get("weekly_pnl"), signed=True)),
        WEEK_CLS=pnl_cls(s.get("weekly_pnl")),
        DD=esc("%.2f%%" % _num(s.get("drawdown_pct"), 0)),
        FEES=esc(fmt_usd(s.get("fees_total"))),
        ERA=esc(EXEC_ERA), NFILLS=len(fills),
        POSITIONS=pos_html, FEED=feed_html, REGIMES=reg_html,
        TILES=tile_html, CHART=chart)
    return page


def render(path: Path = OUT) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(build(), encoding="utf-8")
    return path


_TEMPLATE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="60">
<title>liquiditybot glass console</title>
<style>
:root { --glass-hi: rgba(40,40,44,.60); --glass-lo: rgba(28,28,30,.50);
  --ink: rgba(245,245,247,.92); --ink-2: rgba(235,235,245,.60);
  --ink-3: rgba(235,235,245,.35); --line: rgba(255,255,255,.12); }
* { box-sizing: border-box; margin: 0; }
html { -webkit-text-size-adjust: 100%; }
body { background: #000; color: var(--ink); min-height: 100vh; padding: 22px;
  font-family: -apple-system, "SF Pro Text", "SF Pro Display", Inter,
    system-ui, sans-serif; -webkit-font-smoothing: antialiased;
  font-variant-numeric: tabular-nums; }
body::before { content: ""; position: fixed; inset: 0; z-index: -1;
  background:
    radial-gradient(900px 480px at 12% -8%, rgba(94,92,230,.16), transparent 62%),
    radial-gradient(760px 420px at 88% 4%, rgba(10,132,255,.10), transparent 60%),
    radial-gradient(640px 520px at 55% 108%, rgba(64,203,224,.06), transparent 58%); }
.wrap { max-width: 1220px; margin: 0 auto; display: grid; gap: 14px; }
.card { background: linear-gradient(180deg, var(--glass-hi), var(--glass-lo));
  backdrop-filter: blur(22px) saturate(180%);
  -webkit-backdrop-filter: blur(22px) saturate(180%);
  border: .5px solid var(--line); border-radius: 20px; padding: 18px 20px;
  box-shadow: inset 0 1px 0 0 rgba(255,255,255,.14),
    inset 0 -1px 1px 0 rgba(0,0,0,.30), 0 1px 1px rgba(0,0,0,.35),
    0 12px 32px rgba(0,0,0,.55);
  opacity: 0; transform: translateY(10px);
  animation: rise .5s cubic-bezier(.2,.7,.3,1) forwards; }
@media (prefers-reduced-motion: reduce) {
  .card { animation: none; opacity: 1; transform: none; } }
.wrap > :nth-child(2) { animation-delay: .05s } .wrap > :nth-child(3) { animation-delay: .10s }
.wrap > :nth-child(4) { animation-delay: .15s } .wrap > :nth-child(5) { animation-delay: .20s }
@keyframes rise { to { opacity: 1; transform: none } }
header { display: flex; align-items: baseline; gap: 14px; flex-wrap: wrap; }
header h1 { font-size: 15px; font-weight: 700; letter-spacing: 2.2px;
  text-transform: uppercase; }
.era { font: 600 11px/1 ui-monospace, SFMono-Regular, Menlo, monospace;
  letter-spacing: .4px; color: $CYAN; border: .5px solid rgba(64,203,224,.35);
  border-radius: 99px; padding: 5px 10px; }
.dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; }
.meta { margin-left: auto; color: var(--ink-3); font-size: 11px;
  letter-spacing: .4px; text-transform: uppercase; }
.hero { display: grid; grid-template-columns: minmax(230px,1fr) 3fr;
  gap: 24px; align-items: center; }
.hero .big { font-size: 52px; font-weight: 700; letter-spacing: -1.5px; }
.hero .big small { font-size: 18px; color: var(--ink-2); font-weight: 600; }
.kpis { display: flex; gap: 22px; flex-wrap: wrap; margin-top: 10px; }
.kpis div { display: grid; gap: 3px; }
label { font-size: 11px; font-weight: 600; letter-spacing: .4px;
  text-transform: uppercase; color: var(--ink-2); }
.kpis b { font-size: 17px; font-weight: 650; }
canvas { width: 100%; height: 160px; display: block; }
.cols { display: grid; grid-template-columns: 3fr 2fr; gap: 14px; }
@media (max-width: 900px) { .cols, .hero { grid-template-columns: 1fr } }
h2 { font-size: 12px; font-weight: 700; letter-spacing: 1.4px;
  text-transform: uppercase; color: rgba(235,235,245,.55); margin: 0 0 12px; }
table { width: 100%; border-collapse: collapse; font-size: 13px; }
th { text-align: left; font-size: 10.5px; font-weight: 600; letter-spacing: .4px;
  text-transform: uppercase; color: var(--ink-3); padding: 0 8px 8px 0; }
td { padding: 7px 8px 7px 0; border-top: .5px solid rgba(255,255,255,.07); }
.num { text-align: left; } .sym { font-weight: 650; }
.up { color: $GREEN } .down { color: $RED } .dim { color: var(--ink-2) }
.side { text-transform: uppercase; font-size: 11px; font-weight: 700;
  letter-spacing: .5px; }
.fill { display: flex; gap: 12px; align-items: baseline; font-size: 12.5px;
  padding: 6.5px 0; border-top: .5px solid rgba(255,255,255,.07);
  flex-wrap: wrap; }
.fill:first-child { border-top: 0 }
.mono { font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 11px; }
.chips { display: flex; flex-wrap: wrap; gap: 8px; }
.chip { display: flex; gap: 7px; align-items: center; font-size: 12px;
  border: .5px solid rgba(255,255,255,.09); border-radius: 99px;
  padding: 6px 12px; }
.tiles { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px,1fr));
  gap: 14px; }
.tile { display: grid; gap: 4px; }
.tile b { font-size: 22px; font-weight: 650; letter-spacing: -.3px; }
.tile span, .chip .dim { font-size: 11px; }
.empty { color: var(--ink-3); font-size: 13px; padding: 8px 0; }
footer { color: var(--ink-3); font-size: 11px; letter-spacing: .4px;
  text-align: center; padding: 4px 0 12px; }
</style></head><body><div class="wrap">
<header class="card" style="border-radius:16px;padding:14px 20px">
  <span class="dot" style="background:$LIVE_DOT;box-shadow:0 0 10px $LIVE_DOT"></span>
  <h1>liquiditybot</h1>
  <span class="era">$ERA · $NFILLS fills</span>
  <span class="dim" style="font-size:12px">$STATE</span>
  <span class="meta">$AGE · rendered $RENDERED</span>
</header>
<section class="card hero">
  <div><label>equity (paper)</label>
    <div class="big">$$$EQUITY</div>
    <div class="kpis">
      <div><label>today</label><b class="$DAY_CLS">$DAY</b></div>
      <div><label>week</label><b class="$WEEK_CLS">$WEEK</b></div>
      <div><label>drawdown</label><b class="dim">$DD</b></div>
      <div><label>fees paid</label><b class="dim">$$$FEES</b></div>
    </div></div>
  <div><label>equity — session tail</label><canvas id="eq"></canvas></div>
</section>
<div class="cols">
  <section class="card"><h2>Open book</h2>$POSITIONS
    <h2 style="margin-top:18px">Era feed</h2>$FEED</section>
  <section class="card"><h2>Model &amp; governor</h2>
    <div class="tiles">$TILES</div>
    <h2 style="margin-top:20px">Regimes</h2>
    <div class="chips">$REGIMES</div></section>
</div>
<footer>values as-of the stamps above · dry-run paper telemetry ·
  pager &amp; history live in Grafana — this console is the glass</footer>
</div>
<script>
(function(){
  var pts = $CHART; if (!pts.length) return;
  var cv = document.getElementById('eq'), dpr = window.devicePixelRatio||1;
  var W = cv.clientWidth, H = cv.clientHeight||160;
  cv.width = W*dpr; cv.height = H*dpr;
  var g = cv.getContext('2d'); g.scale(dpr,dpr);
  var vs = pts.map(function(p){return p[1]});
  var lo = Math.min.apply(0,vs), hi = Math.max.apply(0,vs);
  if (hi-lo < 0.5) { var m=(hi+lo)/2; lo=m-0.25; hi=m+0.25; }
  var x = function(i){return 4+(W-8)*i/(pts.length-1)};
  var y = function(v){return 8+(H-24)*(1-(v-lo)/(hi-lo))};
  g.strokeStyle='rgba(255,255,255,.06)'; g.lineWidth=1;
  [0.25,0.5,0.75].forEach(function(f){ g.beginPath();
    g.moveTo(4,8+(H-24)*f); g.lineTo(W-4,8+(H-24)*f); g.stroke(); });
  var up = vs[vs.length-1] >= vs[0];
  var col = up ? '$GREEN' : '$RED';
  var grad = g.createLinearGradient(0,0,0,H);
  grad.addColorStop(0, up?'rgba(48,209,88,.28)':'rgba(255,69,58,.28)');
  grad.addColorStop(1,'rgba(0,0,0,0)');
  g.beginPath(); g.moveTo(x(0),y(vs[0]));
  vs.forEach(function(v,i){ g.lineTo(x(i),y(v)) });
  g.lineTo(x(vs.length-1),H); g.lineTo(x(0),H); g.closePath();
  g.fillStyle=grad; g.fill();
  g.beginPath(); g.moveTo(x(0),y(vs[0]));
  vs.forEach(function(v,i){ g.lineTo(x(i),y(v)) });
  g.strokeStyle=col; g.lineWidth=1.6; g.stroke();
  var lx=x(vs.length-1), ly=y(vs[vs.length-1]);
  g.beginPath(); g.arc(lx,ly,3.2,0,7); g.fillStyle=col; g.fill();
  g.font='600 10px -apple-system,Inter,sans-serif';
  g.fillStyle='rgba(235,235,245,.6)';
  g.fillText(hi.toFixed(2), 6, 16); g.fillText(lo.toFixed(2), 6, H-10);
})();
</script></body></html>
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--open", action="store_true", help="open in browser")
    ap.add_argument("--loop", type=int, metavar="SEC",
                    help="re-render every SEC seconds until Ctrl-C")
    ns = ap.parse_args()
    path = render()
    print(f"rendered {path}")
    if ns.open:
        webbrowser.open(path.as_uri())
    if ns.loop:
        try:
            while True:                      # operator foreground loop —
                time.sleep(max(5, ns.loop))  # Ctrl-C is the documented exit
                render()
        except KeyboardInterrupt:
            print("stopped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
