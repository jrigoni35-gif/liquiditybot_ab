# scripts/operator_page.py
"""Operator page — one localhost page that tells the correct thing.

Design: docs/superpowers/specs/2026-09-22-operator-page-design.md (approved
2026-09-22). SAFE plane: read-only over outputs/ + the Grafana render API.
Correctness contract: every tile carries source/as_of/age; stale => STALE,
absent => NO SOURCE, disagreeing sources => MISMATCH. Never a bare number
without its age.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"
BOARDS_DIR = OUT / "boards"
TOKEN_FILE = Path.home() / ".liquiditybot" / "grafana-sa-token"
GRAFANA = "https://goldsavanna1216.grafana.net"
BOARD_UIDS = ["liquiditybot-trading", "liquiditybot-problem-solution",
              "liquiditybot-learning", "liquiditybot-exec"]
EQUITY_TOLERANCE = 0.01
# expected write cadence per source; age > 2x cadence => STALE
CADENCE = {"status": 60, "fills": 3600, "digest": 3600,
           "payload": 3600, "boards": 300}


def tile(label, value, *, source, as_of, cadence, now, status=None):
    if status is None:
        if as_of is None:
            status = "nosource"
        else:
            status = "stale" if now - as_of > 2 * cadence else "ok"
    return {"label": label, "value": value, "status": status,
            "source": source, "as_of": as_of,
            "age_s": None if as_of is None else round(now - as_of, 1)}


def _read_json(path: Path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return None


def _equity_tail(path: Path):
    try:
        last = None
        with Path(path).open(newline="", encoding="utf-8") as fh:
            for row in csv.reader(fh):
                if row:
                    last = row
        if last is None:
            return None, None
        return float(last[1]), float(last[0])
    except (OSError, ValueError, IndexError):
        return None, None


def position_rows(fills_path: Path):
    """Net base qty per symbol over the lifetime ledger = open inventory.
    as_of = max fill ts. Read-only; no marks fabricated."""
    agg: dict[str, dict] = {}
    try:
        with Path(fills_path).open(newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                try:
                    size = float(row["fill_size"])
                    ts = float(row["ts"])
                except (TypeError, ValueError, KeyError):
                    continue
                a = agg.setdefault(row["symbol"],
                                   {"net": 0.0, "legs": 0, "last_ts": 0.0})
                a["net"] += size if row.get("side") == "buy" else -size
                a["legs"] += 1
                a["last_ts"] = max(a["last_ts"], ts)
    except OSError:
        return [], None
    rows = [{"symbol": s, "net_qty": round(a["net"], 8), "legs": a["legs"],
             "last_ts": a["last_ts"]}
            for s, a in sorted(agg.items()) if abs(a["net"]) > 1e-10]
    as_of = max((a["last_ts"] for a in agg.values()), default=None)
    return rows, as_of


def _posture(status: dict | None, now):
    src = "outputs/status.json"
    cas_of = status.get("ts") if status else None

    def t(label, val):
        return tile(label, val, source=src, as_of=cas_of,
                    cadence=CADENCE["status"], now=now)
    if not status:
        return [t("runner", None), t("mode", None), t("posture", None),
                t("entries", None), t("faults", None)]
    mode = "PAPER" if status.get("mode") == "DRY_RUN" else "LIVE"
    faults = (status.get("fault") or {}).get("faults") or {}
    return [
        t("runner", status.get("runner_state")),
        t("mode", mode),
        t("posture", (status.get("fault") or {}).get("state")),
        t("entries", "open" if status.get("entries_enabled") else "BLOCKED"),
        t("faults", len(faults))]


def _money(status: dict | None, equity_csv: Path, now):
    cas_of = status.get("ts") if status else None
    eq_status = status.get("equity") if status else None
    eq_csv, eq_csv_ts = _equity_tail(equity_csv)
    as_of = max([x for x in (cas_of, eq_csv_ts) if x is not None],
                default=None)
    if eq_status is None and eq_csv is None:
        eq = tile("equity", None, source="status.json+equity.csv",
                  as_of=None, cadence=CADENCE["status"], now=now)
    elif (eq_status is not None and eq_csv is not None
            and abs(eq_status - eq_csv) > EQUITY_TOLERANCE):
        eq = tile("equity", f"status {eq_status} vs csv {eq_csv}",
                  source="status.json+equity.csv", as_of=as_of,
                  cadence=CADENCE["status"], now=now, status="mismatch")
    else:
        eq = tile("equity", eq_status if eq_status is not None else eq_csv,
                  source="status.json+equity.csv", as_of=as_of,
                  cadence=CADENCE["status"], now=now)

    def t(label, val):
        return tile(label, val, source="outputs/status.json", as_of=cas_of,
                    cadence=CADENCE["status"], now=now)
    return [eq,
            t("weekly_pnl", status.get("weekly_pnl") if status else None),
            t("monthly_pnl", status.get("monthly_pnl") if status else None),
            t("savings", status.get("savings") if status else None),
            t("reserve", status.get("reserve") if status else None)]


def _judge(digest: dict | None, now):
    cas_of = digest.get("generated_at") if digest else None
    model = (digest or {}).get("model") or {}

    def t(label, val):
        return tile(label, val, source="outputs/session_digest.json",
                    as_of=cas_of, cadence=CADENCE["digest"], now=now)
    return [t("model_in_use", model.get("use_model")),
            t("monitor_level", model.get("monitor_level")),
            t("champion_brier", model.get("champion_brier")),
            t("history_rows", model.get("history_rows"))]


def _era(payload: dict | None, digest: dict | None, now):
    cas_of = None
    if payload:
        try:
            cas_of = time.mktime(time.strptime(
                payload["meta"]["generated_at"], "%Y-%m-%dT%H:%M:%SZ"))
        except (KeyError, ValueError):
            cas_of = None
    era = (payload or {}).get("meta", {}).get("exec_era") or \
        (digest or {}).get("eras", {}).get("current_era")
    pops = (((payload or {}).get("sections") or {})
            .get("era_readout") or {}).get("data") or {}
    sel = next((v for k, v in (pops.get("populations") or {}).items()
                if "5m book" in k), None)

    def t(label, val):
        return tile(label, val, source="outputs/boundary_payload.json",
                    as_of=cas_of, cadence=CADENCE["payload"], now=now)
    if not sel:
        return [t("era", era), t("n (5m book)", None), t("net/trip", None),
                t("lean", None)]
    net = sel.get("net") or {}
    return [t("era", era),
            t("n (5m book)", sel.get("n")),
            t("net/trip", f"{net.get('mean')} [{net.get('lo')}, "
                          f"{net.get('hi')}]"),
            t("lean", sel.get("lean"))]


def _boards(boards_dir: Path, now):
    out = []
    for uid in BOARD_UIDS:
        p = boards_dir / f"{uid}.png"
        as_of = p.stat().st_mtime if p.exists() else None
        out.append(tile(uid, str(p) if p.exists() else None,
                        source="grafana render", as_of=as_of,
                        cadence=CADENCE["boards"], now=now))
    return out


def build_state(outputs_dir: Path, boards_dir: Path,
                now: float | None = None) -> dict:
    now = time.time() if now is None else now
    status = _read_json(outputs_dir / "status.json")
    digest = _read_json(outputs_dir / "session_digest.json")
    payload = _read_json(outputs_dir / "boundary_payload.json")
    rows, pos_as_of = position_rows(outputs_dir / "fills.csv")
    return {"generated_at": now, "sections": {
        "posture": _posture(status, now),
        "money": _money(status, outputs_dir / "equity.csv", now),
        "positions": {"rows": rows,
                      "tile": tile("positions", len(rows),
                                   source="outputs/fills.csv",
                                   as_of=pos_as_of,
                                   cadence=CADENCE["fills"], now=now)},
        "judge": _judge(digest, now),
        "era": _era(payload, digest, now),
        "boards": _boards(boards_dir, now),
    }}


_STATUS_LABEL = {"stale": "STALE", "nosource": "NO SOURCE",
                 "mismatch": "MISMATCH"}


def _tile_html(t: dict) -> str:
    cls = t["status"]
    badge = _STATUS_LABEL.get(t["status"], "")
    age = "n/a" if t["age_s"] is None else f"{t['age_s']}s"
    return (f'<div class="tile {cls}"><div class="label">{t["label"]}</div>'
            f'<div class="value">{t["value"]}</div>'
            f'<div class="meta">{badge} {t["source"]} · age {age}</div></div>')


def render_html(state: dict) -> str:
    secs = state["sections"]
    rows = "".join(
        f"<tr><td>{r['symbol']}</td><td>{r['net_qty']}</td>"
        f"<td>{r['legs']}</td></tr>" for r in secs["positions"]["rows"])
    boards = "".join(
        f'<figure class="{t["status"]}"><img src="boards/'
        f'{t["label"]}.png" alt="{t["label"]}">'
        f'<figcaption>{t["label"]} · age {t["age_s"]}s'
        f'{" STALE" if t["status"] == "stale" else ""}</figcaption>'
        f"</figure>" for t in secs["boards"] if t["value"])
    posture = "".join(_tile_html(t) for t in secs["posture"])
    money = "".join(_tile_html(t) for t in secs["money"])
    judge = "".join(_tile_html(t) for t in secs["judge"])
    era = "".join(_tile_html(t) for t in secs["era"])
    return f"""<!doctype html><html><head><meta charset="utf-8">
<title>liquiditybot — operator page</title><style>
body{{background:#0d1117;color:#e6edf3;font-family:Consolas,monospace;margin:16px}}
h1{{font-size:18px}} h2{{font-size:14px;color:#8b949e;margin:18px 0 6px}}
.row{{display:flex;gap:10px;flex-wrap:wrap}}
.tile{{background:#161b22;border:1px solid #30363d;border-radius:8px;
padding:10px 14px;min-width:140px}}
.tile .label{{color:#8b949e;font-size:11px}} .tile .value{{font-size:20px}}
.tile .meta{{color:#6e7681;font-size:10px;margin-top:4px}}
.tile.ok{{border-color:#238636}} .tile.stale{{border-color:#da3633}}
.tile.stale .value,.tile.nosource .value{{color:#6e7681}}
.tile.nosource,.tile.mismatch{{border-color:#da3633}}
.tile.mismatch .value{{color:#f85149;font-size:13px}}
table{{border-collapse:collapse}} td,th{{border:1px solid #30363d;
padding:4px 10px;font-size:12px}}
figure{{margin:8px;display:inline-block}} img{{width:480px;display:block}}
figcaption{{font-size:10px;color:#8b949e}} figure.stale img{{opacity:.5}}
</style></head><body>
<h1>liquiditybot — operator page</h1>
<h2>posture</h2><div class="row">{posture}</div>
<h2>money</h2><div class="row">{money}</div>
<h2>positions (net from lifetime fills ledger — no marks fabricated)</h2>
<table><tr><th>symbol</th><th>net qty</th><th>legs</th></tr>{rows}</table>
{_tile_html(secs['positions']['tile'])}
<h2>judge / learning</h2><div class="row">{judge}</div>
<h2>era</h2><div class="row">{era}</div>
<h2>boards (cloud-rendered)</h2>{boards}
<script>window.__STATE__={json.dumps(state, default=str)};</script>
</body></html>"""


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--once", action="store_true",
                    help="write a static snapshot and exit")
    ap.add_argument("--out", default=str(OUT / "operator_page.html"))
    ap.add_argument("--outputs", default=str(OUT))
    ap.add_argument("--boards", default=str(BOARDS_DIR))
    ap.add_argument("--port", type=int, default=8787)
    ap.add_argument("--no-render", action="store_true",
                    help="skip the board render fetch")
    ns = ap.parse_args(argv)
    outputs_dir, boards_dir = Path(ns.outputs), Path(ns.boards)
    if not ns.no_render:
        res = fetch_boards(boards_dir)
        bad = {k: v for k, v in res.items() if v != "ok"}
        if bad:
            print(f"board fetch issues: {bad}", file=sys.stderr)
    if ns.once:
        out = Path(ns.out)
        out.write_text(render_html(build_state(outputs_dir, boards_dir)),
                       encoding="utf-8")
        print(f"operator page snapshot -> {out}")
        return 0
    return serve(outputs_dir, boards_dir, ns.port, not ns.no_render)


def fetch_boards(boards_dir: Path, token_file: Path = TOKEN_FILE,
                 fetcher=None) -> dict:
    """Refresh the four board PNGs via the cloud render API.
    Token read from disk, never printed. Any failure leaves the last
    cached PNG in place and is reported, never raised."""
    boards_dir.mkdir(parents=True, exist_ok=True)
    if fetcher is None:
        def fetcher(url, headers):
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=90) as resp:  # nosec B310 - fixed https host, operator's own Grafana
                return resp.read()
    try:
        token = token_file.read_text(encoding="utf-8").strip()
    except OSError:
        return {uid: "skip: no token file" for uid in BOARD_UIDS}
    headers = {"Authorization": f"Bearer {token}"}
    out = {}
    for uid in BOARD_UIDS:
        url = (f"{GRAFANA}/render/d/{uid}/_?from=now-14d&to=now"
               f"&width=1600&height=1600&kiosk")
        try:
            data = fetcher(url, headers)
            if not data.startswith(b"\x89PNG"):
                raise ValueError("render did not return a PNG")
            (boards_dir / f"{uid}.png").write_bytes(data)
            out[uid] = "ok"
        except Exception as exc:  # noqa: BLE001 - reported, never raised
            out[uid] = f"error: {type(exc).__name__}: {exc}"[:120]
    return out


def _boards_stale(boards_dir: Path, now: float) -> bool:
    """True if any board PNG is missing or older than its cadence."""
    for uid in BOARD_UIDS:
        p = boards_dir / f"{uid}.png"
        try:
            if now - p.stat().st_mtime > CADENCE["boards"]:
                return True
        except OSError:
            return True
    return False


def serve(outputs_dir: Path, boards_dir: Path, port: int,
          render: bool) -> int:
    class Handler(BaseHTTPRequestHandler):
        def _send(self, body: bytes, ctype: str):
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):  # noqa: N802 - stdlib handler name
            if self.path == "/state":
                self._send(json.dumps(
                    build_state(outputs_dir, boards_dir),
                    default=str).encode(), "application/json")
            elif self.path.startswith("/boards/"):
                p = boards_dir / self.path.rsplit("/", 1)[-1]
                if p.exists() and p.suffix == ".png":
                    self._send(p.read_bytes(), "image/png")
                else:
                    self.send_error(404)
            else:
                # refetch at most once per board cadence, never per reload
                if render and _boards_stale(boards_dir, time.time()):
                    fetch_boards(boards_dir)
                self._send(render_html(
                    build_state(outputs_dir, boards_dir)).encode(),
                    "text/html; charset=utf-8")

        def log_message(self, *a):  # quiet
            pass

    httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"operator page on http://127.0.0.1:{port} (Ctrl-C to stop)")
    webbrowser.open(f"http://127.0.0.1:{port}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
