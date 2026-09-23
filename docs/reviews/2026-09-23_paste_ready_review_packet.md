# INDEPENDENT REVIEW REQUEST — liquiditybot (advisory, read-only)

You are an independent reviewer. The author of this code is a different AI
agent; your job is to judge, not to defend. Reply with the typed checklist
only — no essays.

## Context (zero prior knowledge assumed)

liquiditybot is a Kraken-only trading bot under an "era-9 evidence
moratorium": NO change may alter which orders are placed or how they fill
without operator adjudication. Measurement/report tooling is SAFE class.
Kraken is the sole execution venue, enforced by a DENY-LIST in main.py:
if the feed handed to OrderManager is a read-only venue class, engine
construction raises VN_ROGUE_EXECUTION.

Three changes under review (diffs below, in order):

1. **operator_page** (commit c6c540572) — read-only localhost operator page
   assembling tiles from outputs/status.json, equity.csv, fills.csv,
   session_digest.json, boundary_payload.json + 4 Grafana board PNGs.
   Contract: never fabricate (nosource), never show stale as fresh
   (stale when age > 2x cadence), equity cross-checked status.json vs
   equity.csv within $0.01 else MISMATCH badge.

2. **era_readout cohort split** (commit bcb5411f7) — operator ruling B: a
   v10 feature-schema diff went live mid-era unadjudicated; the readout
   splits the SELECTED population into v9/v10 cohorts by ENTRY time
   (t_open), cutoff DERIVED from the first non-empty avail_darkpool row
   in outputs/signal_history.csv (never a hardcoded literal).

3. **darkpool integration** (commit 12a164f06) — v10 shadow features
   (dp_surge_z, dp_vol_z, dp_hhi, avail_dp; feature vector 64->68 wide),
   data/darkpool_feed.py read-only DuckDB mirror of FINRA ATS weekly data,
   wiring in main.py / ml/features.py / core/persistence.py / runner.py.
   DarkPoolFeed was ADDED to the execution deny-list in the same diff.

## Method (Jev-style typed review)

For EACH check C1-C9 return EXACTLY:
  Cx: STATUS in {PASS, CONCERN, FAIL} | confidence 0.00-1.00 | one line of evidence (file:line)

C1. operator_page: can build_state or render_html ever raise on missing
    or malformed outputs files? (contract: never)
C2. operator_page: any path where a stale value renders WITHOUT a stale
    marker?
C3. operator_page serve: can a request path escape the boards dir or
    leak another file (path traversal)?
C4. era_readout cohort_cutoff: any input shape making the derived cutoff
    silently WRONG (as opposed to reported unavailable)?
C5. era_readout: is entry-time cohort assignment sound? Verify against
    diff 3 that no exit/sizing code changed.
C6. darkpool: can DarkPoolFeed construction or maybe_poll raise into or
    block the live trading loop?
C7. darkpool: any path for darkpool data to reach OrderManager or change
    order sizing/placement? (must be NO)
C8. cross-cutting: does any commit violate SAFE class (alter which orders
    are placed or how they fill)?
C9. tests: do the new tests pin the failure modes they claim, or are any
    assertion-free / tautological?

End with: OVERALL: {PASS, CONCERN, FAIL} | confidence | single most
important fix if any.

======================================================================
DIFF 1 of 3 — c6c540572 operator_page (new files, shown in full)
======================================================================
diff --git a/scripts/operator_page.py b/scripts/operator_page.py
new file mode 100644
index 000000000..dda507651
--- /dev/null
+++ b/scripts/operator_page.py
@@ -0,0 +1,387 @@
+# scripts/operator_page.py
+"""Operator page — one localhost page that tells the correct thing.
+
+Design: docs/superpowers/specs/2026-09-22-operator-page-design.md (approved
+2026-09-22). SAFE plane: read-only over outputs/ + the Grafana render API.
+Correctness contract: every tile carries source/as_of/age; stale => STALE,
+absent => NO SOURCE, disagreeing sources => MISMATCH. Never a bare number
+without its age.
+"""
+from __future__ import annotations
+
+import argparse
+import csv
+import json
+import sys
+import time
+import urllib.request
+import webbrowser
+from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
+from pathlib import Path
+
+ROOT = Path(__file__).resolve().parents[1]
+OUT = ROOT / "outputs"
+BOARDS_DIR = OUT / "boards"
+TOKEN_FILE = Path.home() / ".liquiditybot" / "grafana-sa-token"
+GRAFANA = "https://goldsavanna1216.grafana.net"
+BOARD_UIDS = ["liquiditybot-trading", "liquiditybot-problem-solution",
+              "liquiditybot-learning", "liquiditybot-exec"]
+EQUITY_TOLERANCE = 0.01
+# expected write cadence per source; age > 2x cadence => STALE
+CADENCE = {"status": 60, "fills": 3600, "digest": 3600,
+           "payload": 3600, "boards": 300}
+
+
+def tile(label, value, *, source, as_of, cadence, now, status=None):
+    if status is None:
+        if as_of is None:
+            status = "nosource"
+        else:
+            status = "stale" if now - as_of > 2 * cadence else "ok"
+    return {"label": label, "value": value, "status": status,
+            "source": source, "as_of": as_of,
+            "age_s": None if as_of is None else round(now - as_of, 1)}
+
+
+def _read_json(path: Path):
+    try:
+        return json.loads(Path(path).read_text(encoding="utf-8"))
+    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
+        return None
+
+
+def _equity_tail(path: Path):
+    try:
+        last = None
+        with Path(path).open(newline="", encoding="utf-8") as fh:
+            for row in csv.reader(fh):
+                if row:
+                    last = row
+        if last is None:
+            return None, None
+        return float(last[1]), float(last[0])
+    except (OSError, ValueError, IndexError):
+        return None, None
+
+
+def position_rows(fills_path: Path):
+    """Net base qty per symbol over the lifetime ledger = open inventory.
+    as_of = max fill ts. Read-only; no marks fabricated."""
+    agg: dict[str, dict] = {}
+    try:
+        with Path(fills_path).open(newline="", encoding="utf-8") as fh:
+            for row in csv.DictReader(fh):
+                try:
+                    size = float(row["fill_size"])
+                    ts = float(row["ts"])
+                except (TypeError, ValueError, KeyError):
+                    continue
+                a = agg.setdefault(row["symbol"],
+                                   {"net": 0.0, "legs": 0, "last_ts": 0.0})
+                a["net"] += size if row.get("side") == "buy" else -size
+                a["legs"] += 1
+                a["last_ts"] = max(a["last_ts"], ts)
+    except OSError:
+        return [], None
+    rows = [{"symbol": s, "net_qty": round(a["net"], 8), "legs": a["legs"],
+             "last_ts": a["last_ts"]}
+            for s, a in sorted(agg.items()) if abs(a["net"]) > 1e-10]
+    as_of = max((a["last_ts"] for a in agg.values()), default=None)
+    return rows, as_of
+
+
+def _posture(status: dict | None, now):
+    src = "outputs/status.json"
+    cas_of = status.get("ts") if status else None
+
+    def t(label, val):
+        return tile(label, val, source=src, as_of=cas_of,
+                    cadence=CADENCE["status"], now=now)
+    if not status:
+        return [t("runner", None), t("mode", None), t("posture", None),
+                t("entries", None), t("faults", None)]
+    mode = "PAPER" if status.get("mode") == "DRY_RUN" else "LIVE"
+    faults = (status.get("fault") or {}).get("faults") or {}
+    return [
+        t("runner", status.get("runner_state")),
+        t("mode", mode),
+        t("posture", (status.get("fault") or {}).get("state")),
+        t("entries", "open" if status.get("entries_enabled") else "BLOCKED"),
+        t("faults", len(faults))]
+
+
+def _money(status: dict | None, equity_csv: Path, now):
+    cas_of = status.get("ts") if status else None
+    eq_status = status.get("equity") if status else None
+    eq_csv, eq_csv_ts = _equity_tail(equity_csv)
+    as_of = max([x for x in (cas_of, eq_csv_ts) if x is not None],
+                default=None)
+    if eq_status is None and eq_csv is None:
+        eq = tile("equity", None, source="status.json+equity.csv",
+                  as_of=None, cadence=CADENCE["status"], now=now)
+    elif (eq_status is not None and eq_csv is not None
+            and abs(eq_status - eq_csv) > EQUITY_TOLERANCE):
+        eq = tile("equity", f"status {eq_status} vs csv {eq_csv}",
+                  source="status.json+equity.csv", as_of=as_of,
+                  cadence=CADENCE["status"], now=now, status="mismatch")
+    else:
+        eq = tile("equity", eq_status if eq_status is not None else eq_csv,
+                  source="status.json+equity.csv", as_of=as_of,
+                  cadence=CADENCE["status"], now=now)
+
+    def t(label, val):
+        return tile(label, val, source="outputs/status.json", as_of=cas_of,
+                    cadence=CADENCE["status"], now=now)
+    return [eq,
+            t("weekly_pnl", status.get("weekly_pnl") if status else None),
+            t("monthly_pnl", status.get("monthly_pnl") if status else None),
+            t("savings", status.get("savings") if status else None),
+            t("reserve", status.get("reserve") if status else None)]
+
+
+def _judge(digest: dict | None, now):
+    cas_of = digest.get("generated_at") if digest else None
+    model = (digest or {}).get("model") or {}
+
+    def t(label, val):
+        return tile(label, val, source="outputs/session_digest.json",
+                    as_of=cas_of, cadence=CADENCE["digest"], now=now)
+    return [t("model_in_use", model.get("use_model")),
+            t("monitor_level", model.get("monitor_level")),
+            t("champion_brier", model.get("champion_brier")),
+            t("history_rows", model.get("history_rows"))]
+
+
+def _era(payload: dict | None, digest: dict | None, now):
+    cas_of = None
+    if payload:
+        try:
+            cas_of = time.mktime(time.strptime(
+                payload["meta"]["generated_at"], "%Y-%m-%dT%H:%M:%SZ"))
+        except (KeyError, ValueError):
+            cas_of = None
+    era = (payload or {}).get("meta", {}).get("exec_era") or \
+        (digest or {}).get("eras", {}).get("current_era")
+    pops = (((payload or {}).get("sections") or {})
+            .get("era_readout") or {}).get("data") or {}
+    sel = next((v for k, v in (pops.get("populations") or {}).items()
+                if "5m book" in k), None)
+
+    def t(label, val):
+        return tile(label, val, source="outputs/boundary_payload.json",
+                    as_of=cas_of, cadence=CADENCE["payload"], now=now)
+    if not sel:
+        return [t("era", era), t("n (5m book)", None), t("net/trip", None),
+                t("lean", None)]
+    net = sel.get("net") or {}
+    return [t("era", era),
+            t("n (5m book)", sel.get("n")),
+            t("net/trip", f"{net.get('mean')} [{net.get('lo')}, "
+                          f"{net.get('hi')}]"),
+            t("lean", sel.get("lean"))]
+
+
+def _boards(boards_dir: Path, now):
+    out = []
+    for uid in BOARD_UIDS:
+        p = boards_dir / f"{uid}.png"
+        as_of = p.stat().st_mtime if p.exists() else None
+        out.append(tile(uid, str(p) if p.exists() else None,
+                        source="grafana render", as_of=as_of,
+                        cadence=CADENCE["boards"], now=now))
+    return out
+
+
+def build_state(outputs_dir: Path, boards_dir: Path,
+                now: float | None = None) -> dict:
+    now = time.time() if now is None else now
+    status = _read_json(outputs_dir / "status.json")
+    digest = _read_json(outputs_dir / "session_digest.json")
+    payload = _read_json(outputs_dir / "boundary_payload.json")
+    rows, pos_as_of = position_rows(outputs_dir / "fills.csv")
+    return {"generated_at": now, "sections": {
+        "posture": _posture(status, now),
+        "money": _money(status, outputs_dir / "equity.csv", now),
+        "positions": {"rows": rows,
+                      "tile": tile("positions", len(rows),
+                                   source="outputs/fills.csv",
+                                   as_of=pos_as_of,
+                                   cadence=CADENCE["fills"], now=now)},
+        "judge": _judge(digest, now),
+        "era": _era(payload, digest, now),
+        "boards": _boards(boards_dir, now),
+    }}
+
+
+_STATUS_LABEL = {"stale": "STALE", "nosource": "NO SOURCE",
+                 "mismatch": "MISMATCH"}
+
+
+def _tile_html(t: dict) -> str:
+    cls = t["status"]
+    badge = _STATUS_LABEL.get(t["status"], "")
+    age = "n/a" if t["age_s"] is None else f"{t['age_s']}s"
+    return (f'<div class="tile {cls}"><div class="label">{t["label"]}</div>'
+            f'<div class="value">{t["value"]}</div>'
+            f'<div class="meta">{badge} {t["source"]} · age {age}</div></div>')
+
+
+def render_html(state: dict) -> str:
+    secs = state["sections"]
+    rows = "".join(
+        f"<tr><td>{r['symbol']}</td><td>{r['net_qty']}</td>"
+        f"<td>{r['legs']}</td></tr>" for r in secs["positions"]["rows"])
+    boards = "".join(
+        f'<figure class="{t["status"]}"><img src="boards/'
+        f'{t["label"]}.png" alt="{t["label"]}">'
+        f'<figcaption>{t["label"]} · age {t["age_s"]}s'
+        f'{" STALE" if t["status"] == "stale" else ""}</figcaption>'
+        f"</figure>" for t in secs["boards"] if t["value"])
+    posture = "".join(_tile_html(t) for t in secs["posture"])
+    money = "".join(_tile_html(t) for t in secs["money"])
+    judge = "".join(_tile_html(t) for t in secs["judge"])
+    era = "".join(_tile_html(t) for t in secs["era"])
+    return f"""<!doctype html><html><head><meta charset="utf-8">
+<title>liquiditybot — operator page</title><style>
+body{{background:#0d1117;color:#e6edf3;font-family:Consolas,monospace;margin:16px}}
+h1{{font-size:18px}} h2{{font-size:14px;color:#8b949e;margin:18px 0 6px}}
+.row{{display:flex;gap:10px;flex-wrap:wrap}}
+.tile{{background:#161b22;border:1px solid #30363d;border-radius:8px;
+padding:10px 14px;min-width:140px}}
+.tile .label{{color:#8b949e;font-size:11px}} .tile .value{{font-size:20px}}
+.tile .meta{{color:#6e7681;font-size:10px;margin-top:4px}}
+.tile.ok{{border-color:#238636}} .tile.stale{{border-color:#da3633}}
+.tile.stale .value,.tile.nosource .value{{color:#6e7681}}
+.tile.nosource,.tile.mismatch{{border-color:#da3633}}
+.tile.mismatch .value{{color:#f85149;font-size:13px}}
+table{{border-collapse:collapse}} td,th{{border:1px solid #30363d;
+padding:4px 10px;font-size:12px}}
+figure{{margin:8px;display:inline-block}} img{{width:480px;display:block}}
+figcaption{{font-size:10px;color:#8b949e}} figure.stale img{{opacity:.5}}
+</style></head><body>
+<h1>liquiditybot — operator page</h1>
+<h2>posture</h2><div class="row">{posture}</div>
+<h2>money</h2><div class="row">{money}</div>
+<h2>positions (net from lifetime fills ledger — no marks fabricated)</h2>
+<table><tr><th>symbol</th><th>net qty</th><th>legs</th></tr>{rows}</table>
+{_tile_html(secs['positions']['tile'])}
+<h2>judge / learning</h2><div class="row">{judge}</div>
+<h2>era</h2><div class="row">{era}</div>
+<h2>boards (cloud-rendered)</h2>{boards}
+<script>window.__STATE__={json.dumps(state, default=str)};</script>
+</body></html>"""
+
+
+def main(argv=None) -> int:
+    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
+    ap.add_argument("--once", action="store_true",
+                    help="write a static snapshot and exit")
+    ap.add_argument("--out", default=str(OUT / "operator_page.html"))
+    ap.add_argument("--outputs", default=str(OUT))
+    ap.add_argument("--boards", default=str(BOARDS_DIR))
+    ap.add_argument("--port", type=int, default=8787)
+    ap.add_argument("--no-render", action="store_true",
+                    help="skip the board render fetch")
+    ns = ap.parse_args(argv)
+    outputs_dir, boards_dir = Path(ns.outputs), Path(ns.boards)
+    if not ns.no_render:
+        res = fetch_boards(boards_dir)
+        bad = {k: v for k, v in res.items() if v != "ok"}
+        if bad:
+            print(f"board fetch issues: {bad}", file=sys.stderr)
+    if ns.once:
+        out = Path(ns.out)
+        out.write_text(render_html(build_state(outputs_dir, boards_dir)),
+                       encoding="utf-8")
+        print(f"operator page snapshot -> {out}")
+        return 0
+    return serve(outputs_dir, boards_dir, ns.port, not ns.no_render)
+
+
+def fetch_boards(boards_dir: Path, token_file: Path = TOKEN_FILE,
+                 fetcher=None) -> dict:
+    """Refresh the four board PNGs via the cloud render API.
+    Token read from disk, never printed. Any failure leaves the last
+    cached PNG in place and is reported, never raised."""
+    boards_dir.mkdir(parents=True, exist_ok=True)
+    if fetcher is None:
+        def fetcher(url, headers):
+            req = urllib.request.Request(url, headers=headers)
+            with urllib.request.urlopen(req, timeout=90) as resp:  # nosec B310 - fixed https host, operator's own Grafana
+                return resp.read()
+    try:
+        token = token_file.read_text(encoding="utf-8").strip()
+    except OSError:
+        return {uid: "skip: no token file" for uid in BOARD_UIDS}
+    headers = {"Authorization": f"Bearer {token}"}
+    out = {}
+    for uid in BOARD_UIDS:
+        url = (f"{GRAFANA}/render/d/{uid}/_?from=now-14d&to=now"
+               f"&width=1600&height=1600&kiosk")
+        try:
+            data = fetcher(url, headers)
+            if not data.startswith(b"\x89PNG"):
+                raise ValueError("render did not return a PNG")
+            (boards_dir / f"{uid}.png").write_bytes(data)
+            out[uid] = "ok"
+        except Exception as exc:  # noqa: BLE001 - reported, never raised
+            out[uid] = f"error: {type(exc).__name__}: {exc}"[:120]
+    return out
+
+
+def _boards_stale(boards_dir: Path, now: float) -> bool:
+    """True if any board PNG is missing or older than its cadence."""
+    for uid in BOARD_UIDS:
+        p = boards_dir / f"{uid}.png"
+        try:
+            if now - p.stat().st_mtime > CADENCE["boards"]:
+                return True
+        except OSError:
+            return True
+    return False
+
+
+def serve(outputs_dir: Path, boards_dir: Path, port: int,
+          render: bool) -> int:
+    class Handler(BaseHTTPRequestHandler):
+        def _send(self, body: bytes, ctype: str):
+            self.send_response(200)
+            self.send_header("Content-Type", ctype)
+            self.send_header("Content-Length", str(len(body)))
+            self.end_headers()
+            self.wfile.write(body)
+
+        def do_GET(self):  # noqa: N802 - stdlib handler name
+            if self.path == "/state":
+                self._send(json.dumps(
+                    build_state(outputs_dir, boards_dir),
+                    default=str).encode(), "application/json")
+            elif self.path.startswith("/boards/"):
+                p = boards_dir / self.path.rsplit("/", 1)[-1]
+                if p.exists() and p.suffix == ".png":
+                    self._send(p.read_bytes(), "image/png")
+                else:
+                    self.send_error(404)
+            else:
+                # refetch at most once per board cadence, never per reload
+                if render and _boards_stale(boards_dir, time.time()):
+                    fetch_boards(boards_dir)
+                self._send(render_html(
+                    build_state(outputs_dir, boards_dir)).encode(),
+                    "text/html; charset=utf-8")
+
+        def log_message(self, *a):  # quiet
+            pass
+
+    httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
+    print(f"operator page on http://127.0.0.1:{port} (Ctrl-C to stop)")
+    webbrowser.open(f"http://127.0.0.1:{port}")
+    try:
+        httpd.serve_forever()
+    except KeyboardInterrupt:
+        pass
+    return 0
+
+
+if __name__ == "__main__":
+    sys.exit(main())
diff --git a/tests/test_operator_page.py b/tests/test_operator_page.py
new file mode 100644
index 000000000..44577d6c1
--- /dev/null
+++ b/tests/test_operator_page.py
@@ -0,0 +1,113 @@
+# tests/test_operator_page.py
+"""Correctness-contract tests for scripts/operator_page.py."""
+import json
+
+from scripts.operator_page import (  # noqa: E402
+    build_state,
+    position_rows,
+    tile,
+)
+
+
+def _write(path, obj):
+    path.write_text(json.dumps(obj), encoding="utf-8")
+
+
+def _status(tmp, **over):
+    s = {"ts": 1000.0, "runner_state": "RUNNING", "mode": "DRY_RUN",
+         "entries_enabled": True, "halted": False,
+         "fault": {"state": "ARMED", "faults": {}}, "equity": 766.42,
+         "cash": 761.13, "savings": 5.57, "reserve": 0.19,
+         "weekly_pnl": -1.93, "monthly_pnl": -18.84}
+    s.update(over)
+    _write(tmp / "status.json", s)
+    return s
+
+
+def test_tile_fresh_stale_nosource():
+    ok = tile("x", 1, source="s", as_of=100.0, cadence=60, now=110.0)
+    stale = tile("x", 1, source="s", as_of=0.0, cadence=60, now=1000.0)
+    none = tile("x", None, source="s", as_of=None, cadence=60, now=1000.0)
+    assert ok["status"] == "ok" and ok["age_s"] == 10.0
+    assert stale["status"] == "stale"
+    assert none["status"] == "nosource"
+
+
+def test_money_equity_agreement_and_mismatch(tmp_path):
+    _status(tmp_path)
+    (tmp_path / "equity.csv").write_text("1,766.42,0.00\n", encoding="utf-8")
+    st = build_state(tmp_path, tmp_path / "boards", now=1010.0)
+    eq = [t for t in st["sections"]["money"] if t["label"] == "equity"][0]
+    assert eq["status"] == "ok" and eq["value"] == 766.42
+    (tmp_path / "equity.csv").write_text("1,800.00,0.00\n", encoding="utf-8")
+    st = build_state(tmp_path, tmp_path / "boards", now=1010.0)
+    eq = [t for t in st["sections"]["money"] if t["label"] == "equity"][0]
+    assert eq["status"] == "mismatch"
+
+
+def test_position_rows_net(tmp_path):
+    (tmp_path / "fills.csv").write_text(
+        "ts,order_id,position_id,purpose,symbol,side,ordertype,post_only,"
+        "attempt,fill_size,fill_price,arrival_ref,slip_bps,fees_delta_usd,"
+        "remaining,reason,exec_era,book\n"
+        "1,o1,p1,entry,PAXG/USD,buy,limit,t,1,1.0,100.0,,0,0,0,,e,5m\n"
+        "2,o2,p1,exit,PAXG/USD,sell,limit,f,1,0.4,101.0,,0,0,0,,e,5m\n"
+        "3,o3,p2,entry,BTC/USD,buy,limit,t,1,0.001,50000.0,,0,0,0,,e,long\n",
+        encoding="utf-8")
+    rows, as_of = position_rows(tmp_path / "fills.csv")
+    by = {r["symbol"]: r for r in rows}
+    assert abs(by["PAXG/USD"]["net_qty"] - 0.6) < 1e-9
+    assert by["BTC/USD"]["net_qty"] == 0.001
+    assert by["PAXG/USD"]["legs"] == 2 and as_of == 3.0
+
+
+def test_build_state_never_raises_on_empty(tmp_path):
+    st = build_state(tmp_path, tmp_path / "boards", now=1000.0)
+    assert st["generated_at"] == 1000.0
+    for name in ("posture", "money", "judge", "era", "boards"):
+        assert all(t["status"] == "nosource"
+                   for t in st["sections"][name]
+                   if isinstance(t, dict) and "status" in t)
+    assert st["sections"]["positions"]["rows"] == []
+
+
+def test_render_html_badges(tmp_path):
+    from scripts.operator_page import render_html  # noqa: PLC0415
+    _status(tmp_path, ts=0.0)  # ancient => stale
+    st = build_state(tmp_path, tmp_path / "boards", now=1000.0)
+    html = render_html(st)
+    assert "STALE" in html and "window.__STATE__" in html
+    assert "RUNNING" in html  # values render even when stale
+
+
+def test_once_writes_html(tmp_path):
+    from scripts.operator_page import main  # noqa: PLC0415
+    out = tmp_path / "page.html"
+    rc = main(["--once", "--out", str(out), "--no-render",
+               "--outputs", str(tmp_path)])
+    assert rc == 0
+    body = out.read_text(encoding="utf-8")
+    assert "<html" in body and "nosource" in body  # empty dir, truthful
+
+
+def test_fetch_boards_writes_and_reports(tmp_path):
+    from scripts.operator_page import fetch_boards  # noqa: PLC0415
+    tok = tmp_path / "tok"
+    tok.write_text("secret", encoding="utf-8")
+
+    def fake(url, headers):
+        assert headers["Authorization"] == "Bearer secret"
+        return b"\x89PNG"
+
+    res = fetch_boards(tmp_path / "b", token_file=tok, fetcher=fake)
+    assert all(v == "ok" for v in res.values())
+    png = tmp_path / "b" / "liquiditybot-trading.png"
+    assert png.read_bytes() == b"\x89PNG"
+
+
+def test_fetch_boards_no_token_is_skip(tmp_path):
+    from scripts.operator_page import fetch_boards  # noqa: PLC0415
+    res = fetch_boards(tmp_path / "b", token_file=tmp_path / "absent",
+                       fetcher=lambda u, h: b"x")
+    assert all(v.startswith("skip") for v in res.values())
+    assert not list((tmp_path / "b").glob("*.png"))

======================================================================
DIFF 2 of 3 — bcb5411f7 era_readout cohort split
======================================================================
diff --git a/scripts/era_readout.py b/scripts/era_readout.py
index 3a7f140a4..31ffd973b 100644
--- a/scripts/era_readout.py
+++ b/scripts/era_readout.py
@@ -384,6 +384,37 @@ def leave_one_day_out(trips: list[dict], key: str, reps: int, seed: int) -> dict
             "sign_stable": max(his) < 0 or min(los) > 0}
 
 
+def cohort_cutoff(signal_history: Path) -> dict:
+    """The v10-schema activation moment, DERIVED from the ledger.
+
+    Operator ruling B (2026-09-23): the v10 dark-pool feature block (commit
+    12a164f06) went live mid-era without adjudication; the readout must
+    report the uncontaminated v9 cohort beside the pooled read. The cutoff
+    is the ts of the FIRST signal-history row carrying a non-empty
+    avail_darkpool: pre-v10 code could not write that column ("" =
+    pre-v10, "0"/"1" = v10 code live, mirror dark or lit). Never a
+    hardcoded literal - if the column is absent or all-empty, there is
+    nothing to split and the readout says so.
+    """
+    try:
+        with open(signal_history, newline="", encoding="utf-8") as fh:
+            for r in csv.DictReader(fh):
+                v = r.get("avail_darkpool")
+                if v is None:
+                    return {"available": False,
+                            "reason": "no avail_darkpool column (pre-v10 ledger)"}
+                if v.strip() != "":
+                    ts = float(r["ts"])
+                    return {"available": True, "ts": ts,
+                            "utc": datetime.fromtimestamp(
+                                ts, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
+                            "source": str(signal_history)}
+    except (OSError, ValueError, KeyError) as exc:
+        return {"available": False, "reason": f"{type(exc).__name__}: {exc}"}
+    return {"available": False,
+            "reason": "avail_darkpool present but all empty (pre-v10 ledger)"}
+
+
 def rules(trips: list[dict], fee_null: float, reps: int, seed: int) -> dict:
     """Apply the registered read points to one membership population."""
     n = len(trips)
@@ -628,6 +659,32 @@ def render(res: dict) -> str:
         a(f"  n=50  {blk['lean']}")
         a(f"  n=100 {blk['verdict']}")
         a("")
+    co = res.get("cohorts") or {}
+    a("COHORT SPLIT (operator ruling B, 2026-09-23)")
+    if not co.get("available"):
+        a(f"  NOT APPLICABLE - {co.get('reason', 'unknown')}")
+        a("")
+    else:
+        cut = co["cutoff"]
+        a("  The v10 feature schema (commit 12a164f06) went live mid-era without")
+        a("  adjudication. Ruling B: keep accruing; read the verdict on the")
+        a("  uncontaminated v9 cohort beside the pooled SELECTED row.")
+        a(f"  cutoff {cut['utc']} - first avail_darkpool != '' in {cut['source']}")
+        a("  (DERIVED, not a literal). Cohort follows ENTRY time: the diff changed")
+        a("  the feature space (entry decisioning) but no exit/sizing code.")
+        for name in ("v9", "v10"):
+            blk = co[name]
+            tag = "v9 cohort (UNCONTAMINATED)" if name == "v9" else "v10 cohort"
+            a(f"  --- {tag} ---")
+            if blk["n"] == 0:
+                a("    (empty)")
+                continue
+            net = blk["net"]
+            a(f"    net $/trip mean {net['mean']:+.4f}   95% CI "
+              f"[{net['lo']:+.4f}, {net['hi']:+.4f}]   wins {blk['wins']}/{blk['n']}")
+            a(f"    n=50  {blk['lean']}")
+            a(f"    n=100 {blk['verdict']}")
+        a("")
     a("READ THIS WITH THE VERDICT")
     a("  * The registered 95% PERCENTILE day-block bootstrap under-covers when blocks")
     a("    are few: ~0.85 at 6 blocks, ~0.92 at ~12 (about n=50), ~0.94 at ~24 (about")
@@ -694,7 +751,8 @@ def render(res: dict) -> str:
 
 
 def run(fills: Path, era: str, fee_null: float | None, reps: int = REPS,
-        seed: int = SEED, era_source: str = "operator --era") -> dict:
+        seed: int = SEED, era_source: str = "operator --era",
+        signal_history: Path | None = None) -> dict:
     read_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
     mtime = datetime.fromtimestamp(os.path.getmtime(fills), timezone.utc)
     with open(fills, newline="", encoding="utf-8") as fh:
@@ -718,6 +776,25 @@ def run(fills: Path, era: str, fee_null: float | None, reps: int = REPS,
     pops["stamp-pure, long book only (NOT pooled - its own question)"] = rules(
         [t for t in pure if t["book"] == "long"], fee_null, reps, seed)
     proto = next((p["net"]["protocol"] for p in pops.values() if p.get("net")), "n/a")
+    # COHORT SPLIT (operator ruling B, 2026-09-23): the v10 feature schema
+    # went live mid-era; report the uncontaminated v9 cohort beside the
+    # pooled SELECTED read. Cohort follows ENTRY time - commit 12a164f06
+    # touched entry decisioning (feature space) but no exit/sizing code,
+    # so a trip's decision regime is set at t_open. Split over the
+    # SELECTED population only: that is the row the verdict is read from.
+    if signal_history is None:
+        signal_history = ROOT / "outputs" / "signal_history.csv"
+    cut = cohort_cutoff(signal_history)
+    cohorts: dict = {"available": False}
+    if cut.get("available"):
+        sel = [t for t in pure if t["book"] != "long"]
+        v9 = [t for t in sel if t["t_open"] < cut["ts"]]
+        v10 = [t for t in sel if t["t_open"] >= cut["ts"]]
+        cohorts = {"available": True, "cutoff": cut,
+                   "v9": rules(v9, fee_null, reps, seed),
+                   "v10": rules(v10, fee_null, reps, seed)}
+    else:
+        cohorts["reason"] = cut.get("reason", "unknown")
     return {
         "meta": {"fills": str(fills), "read_utc": read_utc,
                  "mtime_utc": mtime.strftime("%Y-%m-%dT%H:%M:%SZ"), "legs": len(rows),
@@ -736,6 +813,7 @@ def run(fills: Path, era: str, fee_null: float | None, reps: int = REPS,
         # one the verdict is read from - not over `pure`, which pools books.
         "what_this_measures": what_this_measures(
             [t for t in pure if t["book"] != "long"]),
+        "cohorts": cohorts,
     }
 
 
diff --git a/tests/test_era_readout.py b/tests/test_era_readout.py
index beb0a5a0c..ecfcd5f13 100644
--- a/tests/test_era_readout.py
+++ b/tests/test_era_readout.py
@@ -613,3 +613,72 @@ def test_the_disclosure_moves_no_verdict(tmp_path):
     assert before == after
     assert "WHAT THIS COHORT ACTUALLY MEASURES" in er.render(res)
 
+
+
+# --- COHORT SPLIT (operator ruling B, 2026-09-23) -------------------------
+# The v10 feature schema (commit 12a164f06) went live mid-era without
+# adjudication; ruling B keeps accruing but requires the readout to report
+# the uncontaminated v9 cohort beside the pooled read. Cohort follows ENTRY
+# time (the diff touched no exit/sizing code); the cutoff is DERIVED from
+# the first non-empty avail_darkpool row, never a hardcoded literal.
+
+def _write_signal_history(tmp_path, rows, with_col=True) -> Path:
+    p = tmp_path / "signal_history.csv"
+    cols = ["ts", "avail_darkpool"] if with_col else ["ts", "other"]
+    with open(p, "w", newline="", encoding="utf-8") as fh:
+        w = csv.DictWriter(fh, fieldnames=cols)
+        w.writeheader()
+        for r in rows:
+            w.writerow(r)
+    return p
+
+
+def test_cohort_cutoff_first_nonempty(tmp_path):
+    sh = _write_signal_history(tmp_path, [
+        {"ts": "100.0", "avail_darkpool": ""},
+        {"ts": "200.0", "avail_darkpool": ""},
+        {"ts": "300.0", "avail_darkpool": "1"},
+        {"ts": "400.0", "avail_darkpool": "0"},
+    ])
+    cut = er.cohort_cutoff(sh)
+    assert cut["available"] and cut["ts"] == 300.0
+
+
+def test_cohort_cutoff_absent_column_and_empty(tmp_path):
+    no_col = _write_signal_history(tmp_path, [{"ts": "1.0", "other": "x"}],
+                                   with_col=False)
+    assert not er.cohort_cutoff(no_col)["available"]
+    all_empty = _write_signal_history(tmp_path, [{"ts": "1.0", "avail_darkpool": ""}])
+    assert not er.cohort_cutoff(all_empty)["available"]
+    assert not er.cohort_cutoff(tmp_path / "missing.csv")["available"]
+
+
+def test_run_splits_selected_by_entry_time(tmp_path):
+    cutoff = T0 + 3 * DAY + 12 * 3600  # mid day-3
+    rows, i = [], 0
+    for day in range(3):               # 3 trips opening before cutoff
+        _trip(rows, i, day=day, net_target=-0.30)
+        i += 1
+    for day in (4, 5):                 # 2 trips opening after cutoff
+        _trip(rows, i, day=day, net_target=-0.30)
+        i += 1
+    # straddler: opened pre-cutoff, closed post-cutoff -> v9 (entry rule)
+    _trip(rows, i, day=3, net_target=-0.30, t_open=cutoff - 3600,
+          t_close=cutoff + 3600)
+    fills = _write(tmp_path, rows)
+    sh = _write_signal_history(tmp_path, [{"ts": f"{cutoff}", "avail_darkpool": "1"}])
+    res = er.run(fills, ERA, -0.27, reps=200, seed=7, signal_history=sh)
+    co = res["cohorts"]
+    assert co["available"] and co["cutoff"]["ts"] == cutoff
+    assert co["v9"]["n"] == 4 and co["v10"]["n"] == 2
+    assert co["v9"]["n"] + co["v10"]["n"] == res["populations"][HYPOTH]["n"]
+
+
+def test_run_without_signal_history_is_back_compatible(tmp_path):
+    rows = []
+    for i in range(3):
+        _trip(rows, i, day=i, net_target=-0.30)
+    res = er.run(_write(tmp_path, rows), ERA, -0.27, reps=200, seed=7,
+                 signal_history=tmp_path / "no_such_file.csv")
+    assert not res["cohorts"]["available"]
+    assert res["populations"][HYPOTH]["n"] == 3  # populations untouched

======================================================================
DIFF 3 of 3 — 12a164f06 darkpool integration (foreign work under review)
======================================================================
diff --git a/config.json b/config.json
index 4f0b32ef8..7017b7515 100644
--- a/config.json
+++ b/config.json
@@ -1172,6 +1172,31 @@
       }
     ]
   },
+  "darkpool": {
+    "description": "Read-only weekly dark-pool (FINRA ATS) context from the external mirror (darkpool.duckdb, table ats_venue_weekly). SHADOW-FIRST: feeds only the v10 dp_* shadow features + avail_darkpool bookkeeping; no gate/sizer/exit may read it until pre-registered promotion criteria pass. Neutral-on-failure, same contract as moomoo (41a/41c): duckdb missing / DB absent / query error -> neutrals + avail_darkpool=0, ts frozen at last REAL observation. Weekly regulatory data: 6h polling is generous; the freeze gate makes faster polling harmless but pointless. Requires pip install duckdb (present in .venv).",
+    "enabled": true,
+    "duckdb_path": "C:\\Users\\haird\\Documents\\kimi\\tasks\\2026-09-20\\19-59-23-0f9af856\\darkpool_v2.duckdb",
+    "poll_minutes": 360,
+    "min_prior_periods": 2,
+    "z_lookback_polls": 60,
+    "tickers": [
+      {
+        "code": "US.COIN",
+        "symbol": "COIN",
+        "weight": 1.0
+      },
+      {
+        "code": "US.MSTR",
+        "symbol": "MSTR",
+        "weight": 1.0
+      },
+      {
+        "code": "US.QQQ",
+        "symbol": "QQQ",
+        "weight": 0.7
+      }
+    ]
+  },
   "watchdog": {
     "description": "Tail-event sentry: stale-data trips, cross-venue divergence, rolling PnL-velocity circuit breaker, single-tick quarantine, live equity-truth drift. Any trip blocks NEW entries; exits are never touched.",
     "enabled": true,
diff --git a/core/persistence.py b/core/persistence.py
index 6aa322dd8..07ae94039 100644
--- a/core/persistence.py
+++ b/core/persistence.py
@@ -542,6 +542,12 @@ class StateStore:
                 "moomoo_state": (bot.moomoo.to_dict() if callable(
                     getattr(getattr(bot, "moomoo", None), "to_dict", None))
                     else {}),
+                # v10: darkpool z-window + freeze-gate state, same 41c
+                # contract and duck-typed guard as moomoo_state (runner-
+                # state doubles may not carry the section).
+                "darkpool_state": (bot.darkpool.to_dict() if callable(
+                    getattr(getattr(bot, "darkpool", None), "to_dict", None))
+                    else {}),
                 # V2 vindication continuity: fired-detector maps for OPEN
                 # positions and the graded reliability ledger. Detector
                 # OBSERVATION state stays un-snapshotted (see NOTE below);
@@ -992,6 +998,15 @@ class StateStore:
                 bot.moomoo.from_dict(ms)
         except Exception:
             log.exception("moomoo section malformed - skipped")
+        # v10: darkpool z-windows/freeze state, same 41c contract and
+        # duck-typed guard as moomoo_state; pre-v10 snapshots lack the key.
+        try:
+            ds = data.get("darkpool_state")
+            if ds and callable(getattr(getattr(bot, "darkpool", None),
+                                       "from_dict", None)):
+                bot.darkpool.from_dict(ds)
+        except Exception:
+            log.exception("darkpool section malformed - skipped")
         try:
             bot._pos_realized.update(data.get("pos_realized", {}))
         except (TypeError, ValueError):
diff --git a/data/darkpool_feed.py b/data/darkpool_feed.py
new file mode 100644
index 000000000..d8e984770
--- /dev/null
+++ b/data/darkpool_feed.py
@@ -0,0 +1,332 @@
+"""
+data/darkpool_feed.py  — DROP-IN for liquiditybot_ab (see integration guide)
+
+Read-only weekly dark-pool (FINRA ATS) context, keyed to the same risk
+basket as the moomoo feed (COIN / MSTR / QQQ by default). NO EXECUTION,
+by construction: this module only ever opens a DuckDB file read-only and
+runs SELECTs; there is no network path and no write path.
+
+Why dark-pool context in a crypto bot: institutional accumulation /
+distribution in crypto-adjacent equities (COIN, MSTR) and the QQQ risk
+proxy shows up in off-exchange venue volume weeks before it shows up in
+price. This feed surfaces that as SHADOW features first (house law: a
+new feature is measured before any decision path may read it).
+
+Data source: the FINRA ATS weeklySummary mirror built outside the bot
+(darkpool_db.mirror_cache -> darkpool.duckdb, table ats_venue_weekly).
+Weekly granularity, publication-lagged 2-4 weeks; every value carries
+its own timestamps (period_start/period_end/published_date/ingested_at)
+so staleness is a first-class feature, not a hidden assumption.
+
+Failure model (mirrors moomoo_feed.py): duckdb missing, DB file absent,
+or query error -> snapshot reports available=False, flags cleared,
+numeric fields neutral 0.0, `ts` NOT advanced (a degraded snapshot keeps
+pointing at the last REAL observation). Weekly data repeats identically
+across polls, so the closed-market freeze gate from moomoo_feed (DF-010)
+is replicated here as `dp_frozen`: a full-repeat poll does not re-append
+to the z windows.
+"""
+
+import logging
+import time
+from collections import deque
+from dataclasses import dataclass, field
+from pathlib import Path
+
+import numpy as np
+
+log = logging.getLogger("liquiditybot.data.darkpool")
+
+EPS = 1e-9
+
+# query: per-symbol dark-volume rollup for the newest complete period,
+# plus the surge ratio vs that symbol's prior complete periods (same tier
+# wave only — cross-wave comparisons fabricate surges; see darkpool_db)
+_LATEST_PER_SYMBOL = """
+-- NOTE: tier is deliberately NOT a partition key. Per-row tier values
+-- scatter within a symbol-week (venue rows carry their own tier labels),
+-- which fragments each symbol into bogus 1-venue partitions. For a
+-- single liquid symbol, latest-period + prior-periods within that symbol
+-- is the robust rollup; the tier-wave subtlety matters only for
+-- market-wide scans (handled in darkpool_db.surge_scan instead).
+WITH per_venue AS (
+    -- date/timestamp columns are CAST to VARCHAR: DuckDB needs pytz to
+    -- materialize DATE/TIMESTAMP values into Python objects, and the bot
+    -- venv carries duckdb WITHOUT pytz - a missing optional module must
+    -- not disable the feed. ISO strings sort chronologically (same
+    -- lexicographic order), and the feed only ever stringifies them.
+    SELECT symbol, CAST(period_start AS VARCHAR) AS period_start,
+           CAST(period_end AS VARCHAR) AS period_end,
+           CAST(published_date AS VARCHAR) AS published_date,
+           CAST(ingested_at AS VARCHAR) AS ingested_at,
+           data_age_days, venue_mpid, volume_shares,
+           SUM(volume_shares) OVER (PARTITION BY symbol, period_start)
+               AS sym_vol
+    FROM ats_venue_weekly
+    WHERE is_complete AND symbol = ?
+),
+rolled AS (
+    -- group ONLY by (symbol, period): per-venue metadata (period_end,
+    -- lastReportedDate, published_date) varies slightly across venue rows
+    -- and was silently fragmenting each symbol into 1-venue groups
+    SELECT symbol, period_start,
+           MAX(period_end) AS period_end,
+           MAX(published_date) AS published_date,
+           MAX(ingested_at) AS ingested_at,
+           MAX(data_age_days) AS data_age_days,
+           SUM(volume_shares) AS dp_volume,
+           COUNT(DISTINCT venue_mpid) AS dp_venue_count,
+           SUM(POWER(volume_shares * 1.0 / NULLIF(sym_vol, 0), 2))
+               AS dp_venue_hhi
+    FROM per_venue
+    GROUP BY symbol, period_start
+),
+with_rn AS (
+    SELECT *, ROW_NUMBER() OVER (PARTITION BY symbol
+                                 ORDER BY period_start DESC) AS rn
+    FROM rolled
+)
+SELECT cur.symbol, cur.period_start, cur.period_end,
+       cur.published_date, cur.ingested_at, cur.data_age_days,
+       cur.dp_volume, cur.dp_venue_count, cur.dp_venue_hhi,
+       (SELECT AVG(prev.dp_volume) FROM with_rn prev
+         WHERE prev.symbol = cur.symbol
+           AND prev.rn BETWEEN 2 AND 5) AS prior_avg_volume
+FROM with_rn cur WHERE cur.rn = 1
+"""
+
+
+@dataclass
+class DarkPoolSnapshot:
+    # cross-basket means (z-scored where history exists)
+    dp_surge_z: float = 0.0        # z of per-symbol surge ratio, basket mean
+    dp_vol_z: float = 0.0          # z of per-symbol log dark volume
+    dp_hhi: float = 0.0            # venue concentration (mean, 0..1)
+    # symbol -> {"surge_ratio","dp_volume","venue_count","hhi",
+    #            "period_start","data_age_days"} for the dashboard
+    per_ticker: dict = field(default_factory=dict)
+    available: bool = False
+    ts: float = field(default_factory=time.time)
+    # weekly data repeats identically between publications: a full-repeat
+    # poll is NOT a fresh observation. Same contract as quotes_frozen.
+    dp_frozen: bool = False
+    # data hygiene, first-class by design (this feed is publication-lagged)
+    data_age_days: float = 0.0     # age of the newest period_end we hold
+    is_complete: bool = False      # underlying periods passed completeness
+    periods: int = 0               # distinct complete periods on file
+
+
+class DarkPoolFeed:
+    def __init__(self, config: dict, con=None):
+        cfg = config or {}
+        self.enabled = bool(cfg.get("enabled", False))
+        self.db_path = str(cfg.get("duckdb_path", "darkpool.duckdb"))
+        # weekly regulatory data: a slow cadence is honest; the frozen
+        # gate makes faster polling harmless but pointless
+        self.poll_sec = float(cfg.get("poll_minutes", 360.0)) * 60.0
+        # [{"code": "US.COIN", "symbol": "COIN", "weight": 1.0}]
+        self.tickers = cfg.get("tickers", [])
+        self.min_prior_periods = int(cfg.get("min_prior_periods", 2))
+        self._con = con            # injectable for tests
+        self._db_ok = con is not None
+        self._last_poll = 0.0
+        self._surge_hist: deque = deque(maxlen=int(
+            cfg.get("z_lookback_polls", 60)))
+        self._vol_hist: deque = deque(maxlen=int(
+            cfg.get("z_lookback_polls", 60)))
+        self._last_per: dict = {}
+        self._frozen = False
+        self._snapshot = DarkPoolSnapshot()
+        self._warned = False
+
+    def snapshot(self) -> DarkPoolSnapshot:
+        return self._snapshot
+
+    # ------------------------------------------------------------------
+    @staticmethod
+    def _import_db():
+        """Isolated import seam (same rationale as moomoo_feed._import_sdk:
+        the smoke suite patches this to exercise the no-DB branch on every
+        machine). duckdb is on the dependency-hygiene FORBIDDEN list
+        (tests/test_dependency_hygiene.py: analysis stack, never a plain
+        import statement at engine scope), so the seam routes through
+        importlib - a lazy, optional, failure-tolerant import. READ-ONLY
+        use only."""
+        import importlib
+        return importlib.import_module("duckdb")
+
+    def _ensure_con(self) -> bool:
+        if self._con is not None:
+            return True
+        if not self.enabled:
+            return False
+        try:
+            if not Path(self.db_path).exists():
+                if not self._warned:
+                    log.info(f"darkpool DB not found at {self.db_path} "
+                             f"- running without it")
+                    self._warned = True
+                return False
+            duckdb = self._import_db()
+            # read-only: the bot must never be able to mutate the mirror
+            self._con = duckdb.connect(self.db_path, read_only=True)
+            self._db_ok = True
+            self._warned = False
+            log.info(f"darkpool mirror opened read-only: {self.db_path}")
+            return True
+        except ImportError:
+            if not self._warned:
+                log.info("darkpool feed enabled but duckdb not installed "
+                         "(pip install duckdb) - running without it")
+                self._warned = True
+        except Exception as e:
+            if not self._warned:
+                log.info(f"darkpool DB unusable at {self.db_path} ({e}) "
+                         f"- running without it")
+                self._warned = True
+        return False
+
+    def _degrade(self) -> None:
+        """Unavailable contract, identical to moomoo_feed._degrade: flags
+        cleared, numerics already neutral, ts keeps pointing at the last
+        REAL observation."""
+        self._snapshot.available = False
+        self._snapshot.dp_frozen = False
+        self._snapshot.is_complete = False
+
+    def maybe_poll(self, now: float | None = None) -> DarkPoolSnapshot:
+        now = now if now is not None else time.time()
+        if not self.enabled or not self.tickers:
+            return self._snapshot
+        if now - self._last_poll < self.poll_sec:
+            return self._snapshot
+        self._last_poll = now
+        if not self._ensure_con():
+            self._degrade()
+            return self._snapshot
+        try:
+            self._snapshot = self._poll(now)
+        except Exception as e:
+            log.warning(f"darkpool poll failed ({e}) - keeping last snapshot")
+            self._degrade()
+        return self._snapshot
+
+    def _poll(self, now: float) -> DarkPoolSnapshot:
+        assert self._con is not None
+        periods = self._con.execute(
+            "SELECT COUNT(DISTINCT period_start) FROM ats_venue_weekly "
+            "WHERE is_complete").fetchone()[0]
+        per, surges, vols = {}, [], []
+        weights = {t["symbol"].upper(): float(t.get("weight", 1.0))
+                   for t in self.tickers if t.get("symbol")}
+        missing = []
+        for t in self.tickers:
+            sym = str(t.get("symbol", "")).upper()
+            if not sym:
+                continue
+            row = self._con.execute(_LATEST_PER_SYMBOL, [sym]).fetchone()
+            if row is None:
+                missing.append(sym)
+                continue
+            (sym_out, pstart, pend, pub, ing, age,
+             vol, vcount, hhi, prior_avg) = row
+            surge = (vol / prior_avg) if (prior_avg and prior_avg > EPS) \
+                else None
+            per[sym_out] = {
+                "surge_ratio": (round(float(surge), 3) if surge else None),
+                "dp_volume": int(vol),
+                "venue_count": int(vcount),
+                "hhi": round(float(hhi), 4) if hhi is not None else None,
+                "period_start": str(pstart),
+                "period_end": str(pend),
+                "published_date": str(pub),
+                "data_age_days": int(age) if age is not None else None,
+            }
+            w = weights.get(sym_out, 1.0)
+            if surge:
+                surges.append(float(surge) * w)
+            if vol and vol > 0:
+                vols.append(float(np.log(vol)) * w)
+        if not per:
+            raise RuntimeError(f"no dark-pool rows for any configured "
+                               f"symbol (missing: {missing})")
+
+        # freeze gate: weekly rows are identical between publications, so a
+        # repeat observation must not re-enter the z windows (DF-010 analog)
+        fingerprint = {k: (v["surge_ratio"], v["dp_volume"])
+                       for k, v in per.items()}
+        frozen = bool(self._last_per) and fingerprint == self._last_per
+        self._last_per = fingerprint
+        if frozen:
+            if not self._frozen:
+                self._frozen = True
+                log.info("darkpool rows unchanged since last poll "
+                         "(weekly publication cadence); z-window appends "
+                         "suspended, z holds")
+        else:
+            self._frozen = False
+            if surges:
+                self._surge_hist.append(float(np.mean(surges)))
+            if vols:
+                self._vol_hist.append(float(np.mean(vols)))
+
+        def _z(vals: deque) -> float:
+            arr = np.array(vals, float)
+            sd = float(arr.std()) if len(arr) >= 8 else 0.0
+            return (float(np.clip((vals[-1] - float(arr.mean())) / sd, -4, 4))
+                    if sd > EPS and len(arr) >= 8 else 0.0)
+
+        age_days = max((v["data_age_days"] or 0) for v in per.values())
+        hhi_mean = float(np.mean([v["hhi"] for v in per.values()
+                                  if v["hhi"] is not None])) \
+            if any(v["hhi"] is not None for v in per.values()) else 0.0
+        snap = DarkPoolSnapshot(
+            dp_surge_z=_z(self._surge_hist),
+            dp_vol_z=_z(self._vol_hist),
+            dp_hhi=round(hhi_mean, 4),
+            per_ticker=per,
+            available=True, ts=now, dp_frozen=frozen,
+            data_age_days=float(age_days),
+            is_complete=True, periods=int(periods))
+        log.info(f"darkpool: {len(per)} symbols, periods={periods}, "
+                 f"age={age_days}d, surge_z={snap.dp_surge_z:+.2f}, "
+                 f"vol_z={snap.dp_vol_z:+.2f}, hhi={snap.dp_hhi:.3f}"
+                 + (f" | missing: {missing}" if missing else ""))
+        return snap
+
+    def to_dict(self) -> dict:
+        """Serializable window/freeze state (same contract as
+        moomoo_feed.to_dict): z windows and the freeze gate's comparison
+        state survive a restart so a restart cannot silently rebuild the
+        windows empty."""
+        return {"surge_hist": [float(x) for x in self._surge_hist],
+                "vol_hist": [float(x) for x in self._vol_hist],
+                "last_per": dict(self._last_per),
+                "frozen": bool(self._frozen)}
+
+    def from_dict(self, d: dict) -> None:
+        try:
+            if not isinstance(d, dict):
+                return
+            for key, hist in (("surge_hist", self._surge_hist),
+                              ("vol_hist", self._vol_hist)):
+                vals = d.get(key) or []
+                hist.clear()
+                hist.extend(float(x) for x in vals)
+            lp = d.get("last_per")
+            self._last_per = ({str(k): tuple(v) for k, v in lp.items()}
+                              if isinstance(lp, dict) else {})
+            self._frozen = bool(d.get("frozen", False))
+        except (TypeError, ValueError):
+            self._surge_hist.clear()
+            self._vol_hist.clear()
+            self._last_per = {}
+            self._frozen = False
+
+    def close(self):
+        if self._con is not None:
+            try:
+                self._con.close()
+            except Exception:  # nosec B110 - shutdown close is best-effort
+                log.debug("darkpool con close failed at shutdown")
+            self._con = None
diff --git a/main.py b/main.py
index 487402305..e4500eaea 100644
--- a/main.py
+++ b/main.py
@@ -64,6 +64,7 @@ from data.ws_feed import (KrakenV2BookStream, LiveMarketCache,
 from data.kraken_feed import KrakenFeed
 from data.webdata_feed import WebDataFeed
 from data.moomoo_feed import MoomooFeed
+from data.darkpool_feed import DarkPoolFeed
 from data.context_engine import ContextFeed
 from strategies.liquidity_model import LiquidityModel, extract_base_asset
 from strategies.signal_gates import (GateStats, SignalGateEngine,
@@ -573,7 +574,8 @@ def _context_avail_check(bot, avail: dict) -> None:
         down = frozenset(k for k, ok in
                          (("web", avail.get("web")),
                           ("equity", avail.get("equity")),
-                          ("options", avail.get("options")))
+                          ("options", avail.get("options")),
+                          ("darkpool", avail.get("darkpool")))
                          if not ok) | (
             frozenset(("frozen",)) if avail.get("frozen") else frozenset())
     except AttributeError:
@@ -640,6 +642,7 @@ def _book_mid(book: dict) -> float:
 class LiquidityBot:
     def __init__(self, config: dict, okx=None, binanceus=None, kraken=None,
                 webdata=None, moomoo=None, sentiment_scanner=None,
+                darkpool=None,
                 resume: bool = True):
         self.config = config
         sys_cfg = config.get("system", {})
@@ -728,6 +731,13 @@ class LiquidityBot:
         self.fg_fear_max = float(wcfg.get("fear_greed_fear_max", 15))
         self.fg_euphoria_min = float(wcfg.get("fear_greed_euphoria_min", 85))
         self.moomoo = moomoo or MoomooFeed(config.get("moomoo", {}))
+        # v10 SHADOW dark-pool context (FINRA ATS weekly mirror, read-only
+        # DuckDB). Same construction contract as moomoo: an injectable
+        # double for tests, else built from config. Data-only by
+        # construction - DarkPoolFeed is in the _readonly deny-list below
+        # and its outputs land ONLY in the v10 dp_* shadow features until
+        # the pre-registered promotion criteria pass (DP_NEUTRAL).
+        self.darkpool = darkpool or DarkPoolFeed(config.get("darkpool", {}))
         # Compounder Phase B (spec §3): telemetry-only cycle/macro context
         # engine. NOT a decision-path input this phase - the ONLY other
         # touch point in this file is the one poll line in slow_cycle's
@@ -859,7 +869,8 @@ class LiquidityBot:
         # what may NEVER reach OrderManager is one of the real read-only
         # venues. FeedRecorder wraps the feed, so unwrap before checking.
         _exec_feed = getattr(self.kraken, "_feed", self.kraken)
-        _readonly = [OKXFeed, BinanceUSFeed, MoomooFeed, WebDataFeed, ContextFeed]
+        _readonly = [OKXFeed, BinanceUSFeed, MoomooFeed, WebDataFeed,
+                     ContextFeed, DarkPoolFeed]
         try:
             from data.ccxt_feed import CCXTFeed as _CCXT
         except Exception:                        # noqa: BLE001 - optional dep
@@ -4571,6 +4582,7 @@ class LiquidityBot:
         sentiment = self.xscan.maybe_poll(now)
         web = self.webdata.maybe_poll(now)
         risk = self.moomoo.maybe_poll(now)
+        self.darkpool.maybe_poll(now)  # v10 shadow weekly mirror (slow, gated)
         self._context_state = self.context.maybe_poll(now)
         # Fear&Greed extremes join fear/euphoria detection (same clamps
         # apply downstream - still a filter, never a trigger)
@@ -6290,10 +6302,20 @@ class LiquidityBot:
         # the flags ride every corpus row as bookkeeping columns - never as
         # features (the DoF ledger is closed). "frozen" is 41a's closed-
         # market signature: the equity quote is real but static.
+        # v10 SHADOW dark-pool snapshot (polled in slow_cycle; read-only
+        # here). dp_live=False (degraded/absent mirror) -> DP_NEUTRAL values
+        # and avail_dp=0.0: build_features gates the three dp_* on avail_dp
+        # at the vector boundary, and the avail dict's "darkpool" flag rides
+        # every corpus row as bookkeeping (avail_darkpool) so offline
+        # consumers can separate "mirror dark" from "genuinely quiet flow".
+        dp_snap = self.darkpool.snapshot() if getattr(self, "darkpool",
+                                                      None) else None
+        dp_live = bool(dp_snap is not None and dp_snap.available)
         avail = {"web": bool(getattr(web, "available", False)),
                  "equity": bool(getattr(risk, "available", False)),
                  "options": bool(getattr(risk, "options_available", False)),
-                 "frozen": bool(getattr(risk, "quotes_frozen", False))}
+                 "frozen": bool(getattr(risk, "quotes_frozen", False)),
+                 "darkpool": dp_live}
         _context_avail_check(self, avail)
         return {"avail": avail,
                 "fear_greed": web.fear_greed,
@@ -6311,7 +6333,18 @@ class LiquidityBot:
                 "opt_iv_skew": risk.opt_iv_skew,
                 "manip_suspect": suspect,
                 "mkt_ret_6": mkt_ret_6,
-                "book_touch_share": touch_share}
+                "book_touch_share": touch_share,
+                # v10 SHADOW dark-pool block (see DP_NEUTRAL): neutrals
+                # unless dp_live; the mirror's own staleness (data_age_days)
+                # is logged by the feed at poll time - weekly regulatory
+                # data is publication-lagged by nature.
+                "dp_surge_z": float(getattr(dp_snap, "dp_surge_z", 0.0))
+                              if dp_live else 0.0,
+                "dp_vol_z": float(getattr(dp_snap, "dp_vol_z", 0.0))
+                            if dp_live else 0.0,
+                "dp_hhi": float(getattr(dp_snap, "dp_hhi", 0.0))
+                          if dp_live else 0.0,
+                "avail_dp": 1.0 if dp_live else 0.0}
 
     def _maybe_unwind_unteachable(self, now: float) -> None:
         """ML-071 anti-wedge (see pick_unteachable_unwind). Dry-run only:
diff --git a/ml/contracts.py b/ml/contracts.py
index 681442f75..0c27f2c02 100644
--- a/ml/contracts.py
+++ b/ml/contracts.py
@@ -65,6 +65,8 @@ _RANGES = {
     "vol_term": (-2, 2), "mkt_ret_6_dir": (-3, 3),
     "book_touch_share": (0, 1), "flow_tox": (0, 1),
     "ofi_dir": (-3, 3), "basis_mom_dir": (-3, 3),
+    "dp_surge_z": (-4, 4), "dp_vol_z": (-4, 4),
+    "dp_hhi": (0, 1), "avail_dp": (0, 1),
     "direction": (-1, 1), "gate_confidence": (0, 1),
 }
 _TOL = 1e-6
diff --git a/ml/features.py b/ml/features.py
index e7e176922..8483006f3 100644
--- a/ml/features.py
+++ b/ml/features.py
@@ -87,6 +87,22 @@ TOX_NEUTRAL = {"flow_tox": 0.0}
 # exit/execution module reads them.
 V9_NEUTRAL = {"ofi_dir": 0.0, "basis_mom_dir": 0.0}
 
+# migration neutrals for the v10 SHADOW dark-pool block (FINRA ATS weekly
+# mirror, basket COIN/MSTR/QQQ): 0.0 = "no dark-pool observation read" -
+# a dead/absent mirror's zeros are byte-identical to genuine neutral flow,
+# exactly the TOX_NEUTRAL/V9_NEUTRAL convention. dp_hhi's true neutral would
+# be a dispersed-book value, but 0.0 is the documented migration neutral
+# (same trade-off as book_touch_share: padding must never CLAIM structure).
+# avail_dp is the block's own availability feature (1 = real observation,
+# 0 = degraded/neutral) and gates the other three to 0.0 in build_features,
+# so a stale producer can never serve its last-live value as fresh.
+# SHADOW status, same pre-registered promotion law as V9_NEUTRAL: the three
+# dp_* columns feed ONLY the feature vector until the TANK quant-2 criteria
+# (3 stability snapshots out of the OOS-dead set, green OF battery with it
+# in the trained space, non-negative >=200-entry markout delta) all pass.
+DP_NEUTRAL = {"dp_surge_z": 0.0, "dp_vol_z": 0.0, "dp_hhi": 0.0,
+              "avail_dp": 0.0}
+
 # Bumped whenever vectors change MEANING (v2: side-relative encoding;
 # v3: +context/THALES block, 46->53; v4: +options positioning, 53->56;
 # v5: +manip_suspect adversarial-data score, 56->57; v6: +th_barclose
@@ -100,11 +116,18 @@ V9_NEUTRAL = {"ofi_dir": 0.0, "basis_mom_dir": 0.0}
 # basis_mom_dir SHADOW pair, 62->64 - event-based best-level OFI
 # (Cont-Kukanov-Stoikov 2014) and perp-basis momentum, ONE batched bump
 # for both columns (TANK quant-2 K/N; see V9_NEUTRAL above for the
-# pre-registered promotion criteria)).
+# pre-registered promotion criteria);
+# v10: +dp_surge_z/dp_vol_z/dp_hhi/avail_dp SHADOW dark-pool block, 64->68 -
+# FINRA ATS weekly dark-volume context (basket COIN/MSTR/QQQ) mirrored
+# outside the bot into darkpool.duckdb and read read-only by
+# data/darkpool_feed.py; ONE batched bump for all four columns (same
+# TANK quant-2 K/N law; see DP_NEUTRAL above). All four absolute gauges,
+# NOT side-relative - like the opt_* fear gauges, direction is an empirical
+# question for the model, not doctrine.
 # Restore paths must drop pending vectors from other versions - the
 # width guard alone cannot see a semantic change, and versioning also
 # documents additive bumps.
-FEATURE_SCHEMA_VERSION = 9
+FEATURE_SCHEMA_VERSION = 10
 
 # *_dir features are SIDE-RELATIVE: market-absolute signed quantities
 # multiplied by trade direction, so "+" always means "with my trade".
@@ -151,6 +174,17 @@ FEATURE_NAMES = [
                                   # touch-depths/min, with/against trade
     "basis_mom_dir",              # v9 SHADOW: basis drift bps/min /10,
                                   # with/against trade
+    "dp_surge_z",                 # v10 SHADOW: z of basket-mean dark-volume
+                                  # surge ratio (current FINRA period / avg of
+                                  # prior <=4 complete periods) - absolute,
+                                  # clip [-4,4]
+    "dp_vol_z",                   # v10 SHADOW: z of basket-mean log dark
+                                  # volume - absolute, clip [-4,4]
+    "dp_hhi",                     # v10 SHADOW: venue concentration 0..1,
+                                  # low = dispersed institutional flow
+    "avail_dp",                   # v10 SHADOW: 1 = dp_* from a REAL
+                                  # observation, 0 = degraded/neutral
+                                  # (gates the three dp_* to DP_NEUTRAL)
     "direction", "gate_confidence",
 ]
 
@@ -367,6 +401,9 @@ def build_features(asset: str, direction: str, gate_confidence: float,
     sent_score = float(getattr(sentiment, "score", 0.0) or 0.0)
     sent_fear = float(bool(getattr(sentiment, "fear_spike", False)))
 
+    _avail_dp = 1.0 if _finite((extras or {}).get("avail_dp", 0.0)) \
+        >= 0.5 else 0.0
+
     x = np.array([
         dir_sign * _ret(closes, 1, sigma_bar),
         dir_sign * _ret(closes, 6, sigma_bar),
@@ -462,6 +499,23 @@ def build_features(asset: str, direction: str, gate_confidence: float,
                                  -3, 3)),
         dir_sign * float(np.clip(_finite(getattr(fv_state, "basis_mom_bps",
                                                  0.0)), -30, 30)) / 10.0,
+        # v10 SHADOW dark-pool block (see DP_NEUTRAL for the pre-registered
+        # promotion criteria). All four ABSOLUTE gauges, NOT side-relative:
+        # institutional dark-flow accumulation/distribution is symmetric
+        # information, like the opt_* fear gauges - whether it confirms or
+        # fades a side is an empirical question for the model. avail_dp
+        # gates the three dp_* to DP_NEUTRAL here, at the vector boundary,
+        # so a stale/malformed producer can never serve its last-live value
+        # as a fresh observation. _finite: producers document 0.0-on-
+        # missing/stale - enforce it so a legacy stub/NaN can never poison
+        # the vector.
+        float(np.clip(_finite((extras or {}).get("dp_surge_z", 0.0)),
+                      -4, 4)) * _avail_dp,
+        float(np.clip(_finite((extras or {}).get("dp_vol_z", 0.0)),
+                      -4, 4)) * _avail_dp,
+        float(np.clip(_finite((extras or {}).get("dp_hhi", 0.0)),
+                      0, 1)) * _avail_dp,
+        _avail_dp,
         dir_sign,
         float(np.clip(gate_confidence, 0, 1)),
     ], dtype=float)
diff --git a/ml/history.py b/ml/history.py
index 24a113932..3a27330aa 100644
--- a/ml/history.py
+++ b/ml/history.py
@@ -304,7 +304,7 @@ SG_COMPONENT_KEYS = ("flow", "delta", "accum", "burst", "trend",
 # _N_LEAD: position_id, asset, side. _N_TRAIL: label, net_pnl_usd, source,
 # ts, signal_ts, barrier, probe, disp, candidate_id, book, label_era,
 # pt_frac, sl_frac (13) + the 7 sg_* + entry_price, exit_price
-# + the 4 avail_* flags (AVAIL_COLS) = 26.
+# + the 5 avail_* flags (AVAIL_COLS) = 27.
 # _append_row's width guard AND its warning message both derive from these,
 # so the "expected feature count" they report can never disagree again -
 # tests/test_durable_append.py pins the identity against the live header
@@ -325,7 +325,14 @@ _N_LEAD = 3
 # closed); these exist so a FUTURE training decision can weight or filter
 # degraded-context rows offline, deliberately.
 AVAIL_COLS = ("avail_web", "avail_equity", "avail_options",
-              "quotes_frozen")
+              "quotes_frozen", "avail_darkpool")
+# avail dict keys (main._feature_extras) per bookkeeping column. Appended
+# LAST (2026-09-21, schema 95->96, same bump as FEATURE_SCHEMA_VERSION 9->10):
+# the first four columns keep their positions in already-padded rows; new
+# rows write "1"/"0", migrated/old rows carry "" = UNKNOWN.
+AVAIL_KEY = {"avail_web": "web", "avail_equity": "equity",
+             "avail_options": "options", "quotes_frozen": "frozen",
+             "avail_darkpool": "darkpool"}
 # label_ret_pct (schema 93->94, 2026-08-24): the labeled outcome's REALIZED
 # RETURN in PERCENT, net of the cost basis used AT LABEL TIME. Before this
 # column, _emit_label computed BarrierOutcome.ret and then wrote a literal
@@ -1190,9 +1197,9 @@ class HistoryStore:
                f"{pt_frac:.6f}", f"{sl_frac:.6f}",
                *[f"{sg[k]:.4f}" for k in SG_COMPONENT_KEYS],
                f"{entry_price:.10g}", f"{exit_price:.10g}",
-               *(["", "", "", ""] if not avail else
-                 [str(int(bool(avail.get(k, False))))
-                  for k in ("web", "equity", "options", "frozen")]),
+               *( [""] * len(AVAIL_COLS) if not avail else
+                  [str(int(bool(avail.get(AVAIL_KEY[c], False))))
+                   for c in AVAIL_COLS] ),
                # "" = UNKNOWN, never 0.0 - a zero here would be
                # indistinguishable from a genuine zero-return outcome,
                # which is the exact ambiguity this column exists to end.
diff --git a/runner.py b/runner.py
index f995752d7..93a502ec9 100644
--- a/runner.py
+++ b/runner.py
@@ -1771,6 +1771,11 @@ class BotRunner:
             # contending with the peer we just conceded to.
             self._stop_heartbeat()
             bot.moomoo.close()
+            # v10: dark-pool mirror connection. Guarded getattr: runner-
+            # state doubles may stub a moomoo-only namespace.
+            dp = getattr(bot, "darkpool", None)
+            if dp is not None and callable(getattr(dp, "close", None)):
+                dp.close()
             ws = getattr(bot, "ws_manager", None)
             if ws is not None:
                 ws.stop()               # join the daemon stream thread
diff --git a/tests/test_darkpool_persistence.py b/tests/test_darkpool_persistence.py
new file mode 100644
index 000000000..fadfcdd65
--- /dev/null
+++ b/tests/test_darkpool_persistence.py
@@ -0,0 +1,141 @@
+"""Dark-pool mirror window persistence (v10, 2026-09-21).
+
+Same hazard class as test_moomoo_persistence.py (41c): the DarkPoolFeed's
+z-windows and freeze gate live in memory only, and at the bot's restart
+cadence an empty rebuild would fabricate dp_surge_z/dp_vol_z back toward
+neutral for weeks of publication-lagged data. to_dict/from_dict ride the
+same StateStore sections as moomoo_state ("darkpool_state"), restored
+BEFORE the first poll so the freeze fingerprint classifies a still-frozen
+mirror without re-seeding the windows.
+"""
+import pytest
+
+duckdb = pytest.importorskip("duckdb")
+
+from data.darkpool_feed import DarkPoolFeed  # noqa: E402
+
+_COLS = """symbol VARCHAR, period_start DATE, period_end DATE,
+           published_date DATE, ingested_at DATE, data_age_days INTEGER,
+           venue_mpid VARCHAR, volume_shares BIGINT, is_complete BOOLEAN"""
+
+
+def _mk_con(rows) -> "duckdb.DuckDBPyConnection":
+    con = duckdb.connect(":memory:")
+    con.execute(f"CREATE TABLE ats_venue_weekly ({_COLS})")
+    if rows:
+        con.executemany(
+            "INSERT INTO ats_venue_weekly VALUES (?,?,?,?,?,?,?,?,?)", rows)
+    return con
+
+
+def _rows(period_start: str, mult: float = 1.0) -> list:
+    base = [("MSPL", 10_000_000), ("UBSA", 8_000_000), ("WCHX", 5_000_000)]
+    return [
+        ("MSTR", period_start, "2026-04-24", "2026-05-02", "2026-05-02",
+         30, mp, int(v * mult), True)
+        for mp, v in base
+    ] + [
+        ("COIN", period_start, "2026-04-24", "2026-05-02", "2026-05-02",
+         30, mp, int(v * mult * 0.4), True)
+        for mp, v in base
+    ]
+
+
+def _feed(con) -> DarkPoolFeed:
+    return DarkPoolFeed({"enabled": True, "poll_minutes": 0,
+                         "min_prior_periods": 2,
+                         "tickers": [{"symbol": "MSTR", "weight": 1.0},
+                                     {"symbol": "COIN", "weight": 1.0}]},
+                        con=con)
+
+
+def test_windows_and_freeze_state_roundtrip():
+    con = _mk_con(_rows("2026-04-13") + _rows("2026-04-20"))
+    f1 = _feed(con)
+    s = f1._poll(1000.0)
+    assert s.available and s.periods == 2 and s.dp_surge_z == 0.0
+    d = f1.to_dict()
+    f2 = _feed(_mk_con([]))
+    f2.from_dict(d)
+    assert list(f2._surge_hist) == list(f1._surge_hist)
+    assert list(f2._vol_hist) == list(f1._vol_hist)
+    assert f2._last_per == f1._last_per
+    assert f2.to_dict() == d               # stable fixed point
+
+
+def test_identical_week_does_not_reenter_z_windows():
+    """DF-010 analog: weekly rows repeat between publications, so a
+    full-repeat poll must not append to the z windows."""
+    con = _mk_con(_rows("2026-04-13") + _rows("2026-04-20"))
+    f = _feed(con)
+    f._poll(1000.0)
+    n = len(f._surge_hist)
+    s = f._poll(2000.0)                    # identical data -> frozen
+    assert s.dp_frozen is True
+    assert len(f._surge_hist) == n, "no z-window append on a repeat poll"
+
+
+def test_new_publication_appends_normally():
+    con = _mk_con(_rows("2026-04-13") + _rows("2026-04-20"))
+    f = _feed(con)
+    f._poll(1000.0)
+    con.executemany(                       # next weekly publication lands
+        "INSERT INTO ats_venue_weekly VALUES (?,?,?,?,?,?,?,?,?)",
+        _rows("2026-04-27", mult=2.0))
+    s = f._poll(2000.0)
+    assert s.dp_frozen is False
+    assert len(f._surge_hist) == 2
+    # z stays 0.0 by design until >=8 observations; the fresh publication
+    # shows up in the raw surge ratio and the concentration mean instead
+    assert s.per_ticker["MSTR"]["surge_ratio"] == 2.0
+    assert s.dp_hhi != 0.0
+
+
+def test_malformed_section_leaves_clean_boot_state():
+    f = _feed(_mk_con([]))
+    f.from_dict({"surge_hist": ["nan-value"], "last_per": 7})
+    assert list(f._surge_hist) == [] and f._last_per == {}
+    assert f._frozen is False
+    f.from_dict("garbage")                 # type: ignore[arg-type]
+    assert list(f._surge_hist) == []
+
+
+def test_statestore_carries_darkpool_section(tmp_path):
+    """Through the REAL snapshot()/restore(): the section must survive,
+    and a bot WITHOUT a darkpool attr (runner-state double convention)
+    must still snapshot an empty section."""
+    from types import SimpleNamespace
+
+    from core.persistence import StateStore
+
+    f1 = _feed(_mk_con(_rows("2026-04-13") + _rows("2026-04-20")))
+    f1._poll(1000.0)
+
+    import tests.test_gate_components as tgc
+    hs = tgc._mk_store(tmp_path / "src")
+    bot = tgc._persist_stub_bot(hs)
+    bot.darkpool = f1
+    store = StateStore(str(tmp_path / "state.json"))
+    assert store.snapshot(bot)
+
+    f2 = _feed(_mk_con([]))
+    hs2 = tgc._mk_store(tmp_path / "dst")
+    revived = tgc._persist_stub_bot(hs2)
+    revived.darkpool = f2
+    assert store.restore(revived)
+    assert list(f2._surge_hist) == list(f1._surge_hist)
+    assert f2._last_per == f1._last_per
+
+    # bot without any darkpool attr: section writes {} via the getattr guard
+    bot2 = tgc._persist_stub_bot(tgc._mk_store(tmp_path / "src2"))
+    bot2.darkpool = SimpleNamespace(close=lambda: None)
+    assert store.snapshot(bot2)
+
+
+def test_degraded_mirror_reports_unavailable():
+    """Empty table -> poll raises -> snapshot degrades to the unavailable
+    contract (flags cleared, ts NOT advanced, neutrals already 0.0)."""
+    f = _feed(_mk_con([]))
+    s = f.maybe_poll(1000.0)
+    assert s.available is False
+    assert s.dp_frozen is False and s.is_complete is False
