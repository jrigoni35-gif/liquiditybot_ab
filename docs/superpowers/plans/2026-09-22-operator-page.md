# Operator Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **This session's override:** operator directive — build in-session, no subagents. Execute inline, task by task, TDD per step.

**Goal:** One localhost page (`scripts/operator_page.py`, port 8787) that shows the desk's posture/money/positions/judge/era state with a STALE / NO SOURCE / MISMATCH correctness contract, plus a strip of the four cloud-rendered Grafana board PNGs.

**Architecture:** stdlib-only read-only assembly (`build_state`) over `outputs/status.json`, `outputs/state.json`, `outputs/fills.csv`, `outputs/equity.csv`, `outputs/session_digest.json`, `outputs/boundary_payload.json`, `outputs/boards/*.png`; self-contained dark HTML with embedded state; `http.server` serve mode + `--once` snapshot mode; board refresh via Grafana Cloud render API (SA token read from disk, never printed).

**Tech Stack:** Python stdlib (`http.server`, `urllib.request`, `json`, `csv`), pytest.

**Spec:** `docs/superpowers/specs/2026-09-22-operator-page-design.md` (approved 2026-09-22).

## Global Constraints

- SAFE plane: read-only over `outputs/`; writes only to `outputs/boards/` (render cache) and the `--once` snapshot path. No engine imports. EXEC_ERA untouched.
- Every tile carries `label, value, status, source, as_of, age_s`; status ∈ `ok | stale | nosource | mismatch`.
- Equity agreement tolerance **$0.01** between `status.json` and `equity.csv` tail.
- Staleness rule: `now − as_of > 2 × cadence` → `stale`.
- Server binds `127.0.0.1` only. No network in tests (render fetch injected).
- Venv python: `.venv/Scripts/python.exe` (fall back `../.venv/Scripts/python.exe`).
- ruff scope: new files; bandit: new script; compileall both.

## Verified source shapes (measured 2026-09-22, do not re-guess)

- `status.json`: `ts, runner_state, mode("DRY_RUN"), entries_enabled, halted, fault{state,faults}, equity, cash, savings, reserve, weekly_pnl, monthly_pnl`
- `state.json`: `saved_at`, `dry_run`; NO open-positions table (`open_orders` is a list, currently empty) → positions derive from fills.csv.
- `fills.csv` header: `ts,order_id,position_id,purpose,symbol,side,ordertype,post_only,attempt,fill_size,fill_price,arrival_ref,slip_bps,fees_delta_usd,remaining,reason,exec_era,book`
- `equity.csv` rows: `ts,equity,<unused>` (e.g. `1790124402,768.46,0.00`)
- `session_digest.json`: `generated_at`, `model{monitor_level,use_model,champion_brier,history_rows,cold}`, `eras.current_era`
- `boundary_payload.json`: `meta{generated_at(iso),exec_era}`, `sections.era_readout.data.populations` — dict keyed by population name; SELECTED row key contains `"5m book"`; row fields: `n, net{mean,lo,hi}, lean, verdict, wins`
- Boards: `outputs/boards/<uid>.png`; render endpoint `GET {grafana}/render/d/{uid}/_?from=now-14d&to=now&width=1600&height=1600&kiosk` with header `Authorization: Bearer <token>`; uids `liquiditybot-trading, liquiditybot-problem-solution, liquiditybot-learning, liquiditybot-exec`.

---

### Task 1: State assembly + tile semantics

**Files:**
- Create: `scripts/operator_page.py`
- Test: `tests/test_operator_page.py`

**Interfaces:**
- Produces (consumed by Tasks 2–3):
  - `tile(label, value, *, source, as_of, cadence, now, status=None) -> dict`
  - `build_state(outputs_dir: Path, boards_dir: Path, now: float | None = None) -> dict` — returns `{"generated_at": float, "sections": {"posture": [tile...], "money": [tile...], "positions": {"rows": [...], "tile": tile}, "judge": [tile...], "era": [tile...], "boards": [tile...]}}`; never raises on missing/garbage inputs.
  - `position_rows(fills_path: Path) -> tuple[list[dict], float | None]` — rows `{symbol, net_qty, legs, last_ts}`.

- [ ] **Step 1: failing tests** — create `tests/test_operator_page.py`:

```python
# tests/test_operator_page.py
"""Correctness-contract tests for scripts/operator_page.py."""
import json

from scripts.operator_page import (  # noqa: E402
    build_state,
    position_rows,
    tile,
)


def _write(path, obj):
    path.write_text(json.dumps(obj), encoding="utf-8")


def _status(tmp, **over):
    s = {"ts": 1000.0, "runner_state": "RUNNING", "mode": "DRY_RUN",
         "entries_enabled": True, "halted": False,
         "fault": {"state": "ARMED", "faults": {}}, "equity": 766.42,
         "cash": 761.13, "savings": 5.57, "reserve": 0.19,
         "weekly_pnl": -1.93, "monthly_pnl": -18.84}
    s.update(over)
    _write(tmp / "status.json", s)
    return s


def test_tile_fresh_stale_nosource():
    ok = tile("x", 1, source="s", as_of=100.0, cadence=60, now=110.0)
    stale = tile("x", 1, source="s", as_of=0.0, cadence=60, now=1000.0)
    none = tile("x", None, source="s", as_of=None, cadence=60, now=1000.0)
    assert ok["status"] == "ok" and ok["age_s"] == 10.0
    assert stale["status"] == "stale"
    assert none["status"] == "nosource"


def test_money_equity_agreement_and_mismatch(tmp_path):
    _status(tmp_path)
    (tmp_path / "equity.csv").write_text("1,766.42,0.00\n", encoding="utf-8")
    st = build_state(tmp_path, tmp_path / "boards", now=1010.0)
    eq = [t for t in st["sections"]["money"] if t["label"] == "equity"][0]
    assert eq["status"] == "ok" and eq["value"] == 766.42
    (tmp_path / "equity.csv").write_text("1,800.00,0.00\n", encoding="utf-8")
    st = build_state(tmp_path, tmp_path / "boards", now=1010.0)
    eq = [t for t in st["sections"]["money"] if t["label"] == "equity"][0]
    assert eq["status"] == "mismatch"


def test_position_rows_net(tmp_path):
    (tmp_path / "fills.csv").write_text(
        "ts,order_id,position_id,purpose,symbol,side,ordertype,post_only,"
        "attempt,fill_size,fill_price,arrival_ref,slip_bps,fees_delta_usd,"
        "remaining,reason,exec_era,book\n"
        "1,o1,p1,entry,PAXG/USD,buy,limit,t,1,1.0,100.0,,0,0,0,,e,5m\n"
        "2,o2,p1,exit,PAXG/USD,sell,limit,f,1,0.4,101.0,,0,0,0,,e,5m\n"
        "3,o3,p2,entry,BTC/USD,buy,limit,t,1,0.001,50000.0,,0,0,0,,e,long\n",
        encoding="utf-8")
    rows, as_of = position_rows(tmp_path / "fills.csv")
    by = {r["symbol"]: r for r in rows}
    assert abs(by["PAXG/USD"]["net_qty"] - 0.6) < 1e-9
    assert by["BTC/USD"]["net_qty"] == 0.001
    assert by["PAXG/USD"]["legs"] == 2 and as_of == 3.0


def test_build_state_never_raises_on_empty(tmp_path):
    st = build_state(tmp_path, tmp_path / "boards", now=1000.0)
    assert st["generated_at"] == 1000.0
    for name in ("posture", "money", "judge", "era", "boards"):
        assert all(t["status"] == "nosource"
                   for t in st["sections"][name] if isinstance(t, dict)
                   and "status" in t)
    assert st["sections"]["positions"]["rows"] == []
```

- [ ] **Step 2: run, expect ImportError** — `.venv/Scripts/python.exe -m pytest tests/test_operator_page.py -q -p no:cacheprovider` → collection error (module absent).

- [ ] **Step 3: implementation** — create `scripts/operator_page.py`:

```python
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
           "payload": 86400, "boards": 300}


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
    src, cas_of = "outputs/status.json", None
    if status:
        cas_of = status.get("ts")
    t = lambda label, val: tile(  # noqa: E731 - local shorthand, scoped
        label, val, source=src, as_of=cas_of,
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
    elif eq_status is not None and eq_csv is not None \
            and abs(eq_status - eq_csv) > EQUITY_TOLERANCE:
        eq = tile("equity", f"status {eq_status} vs csv {eq_csv}",
                  source="status.json+equity.csv", as_of=as_of,
                  cadence=CADENCE["status"], now=now, status="mismatch")
    else:
        eq = tile("equity", eq_status if eq_status is not None else eq_csv,
                  source="status.json+equity.csv", as_of=as_of,
                  cadence=CADENCE["status"], now=now)
    t = lambda label, val: tile(  # noqa: E731
        label, val, source="outputs/status.json", as_of=cas_of,
        cadence=CADENCE["status"], now=now)
    return [eq, t("weekly_pnl", status.get("weekly_pnl") if status else None),
            t("monthly_pnl", status.get("monthly_pnl") if status else None),
            t("savings", status.get("savings") if status else None),
            t("reserve", status.get("reserve") if status else None)]


def _judge(digest: dict | None, now):
    cas_of = digest.get("generated_at") if digest else None
    model = (digest or {}).get("model") or {}
    t = lambda label, val: tile(  # noqa: E731
        label, val, source="outputs/session_digest.json", as_of=cas_of,
        cadence=CADENCE["digest"], now=now)
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
    t = lambda label, val: tile(  # noqa: E731
        label, val, source="outputs/boundary_payload.json", as_of=cas_of,
        cadence=CADENCE["payload"], now=now)
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
```

- [ ] **Step 4: run, expect 4 PASS** — same pytest command.

- [ ] **Step 5: commit** — `git add scripts/operator_page.py tests/test_operator_page.py && git commit -m "feat(ops): operator page state assembly + correctness contract (SAFE)"`

---

### Task 2: HTML rendering + `--once`

**Files:**
- Modify: `scripts/operator_page.py` (append)
- Test: `tests/test_operator_page.py` (append)

**Interfaces:**
- Consumes: `build_state(...)` from Task 1.
- Produces (consumed by Task 3): `render_html(state: dict) -> str` — self-contained dark HTML, state JSON embedded as `window.__STATE__`, tiles rendered server-side; JS refreshes via `fetch('/state')` only when served (snapshot keeps baked values silently on failure).

- [ ] **Step 1: failing tests** — append:

```python
def test_render_html_badges(tmp_path):
    _status(tmp_path, ts=0.0)  # ancient => stale
    st = build_state(tmp_path, tmp_path / "boards", now=1000.0)
    html = render_html(st)
    assert "STALE" in html and "window.__STATE__" in html
    assert "RUNNING" in html  # values render even when stale


def test_once_writes_html(tmp_path):
    out = tmp_path / "page.html"
    rc = main(["--once", "--out", str(out), "--no-render",
               "--outputs", str(tmp_path)])
    assert rc == 0
    body = out.read_text(encoding="utf-8")
    assert "<html" in body and "NO SOURCE" in body  # empty dir truthfully red
```

- [ ] **Step 2: run, expect NameError/ImportError.**

- [ ] **Step 3: implementation** — append to `scripts/operator_page.py`:

```python
_STATUS_CLASS = {"ok": "ok", "stale": "stale",
                 "nosource": "nosource", "mismatch": "mismatch"}
_STATUS_LABEL = {"stale": "STALE", "nosource": "NO SOURCE",
                 "mismatch": "MISMATCH"}


def _tile_html(t: dict) -> str:
    cls = _STATUS_CLASS[t["status"]]
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
        f'<figure class="{t["status"]}"><img src="/boards/'
        f'{t["label"]}.png" alt="{t["label"]}">'
        f'<figcaption>{t["label"]} · age {t["age_s"]}s'
        f'{" STALE" if t["status"] == "stale" else ""}</figcaption>'
        f"</figure>" for t in secs["boards"] if t["value"])
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
<h1>liquiditybot — operator page <span id="age"></span></h1>
<h2>posture</h2><div class="row">{''.join(_tile_html(t) for t in secs['posture'])}</div>
<h2>money</h2><div class="row">{''.join(_tile_html(t) for t in secs['money'])}</div>
<h2>positions (net from lifetime fills ledger — no marks fabricated)</h2>
<table><tr><th>symbol</th><th>net qty</th><th>legs</th></tr>{rows}</table>
{_tile_html(secs['positions']['tile'])}
<h2>judge / learning</h2><div class="row">{''.join(_tile_html(t) for t in secs['judge'])}</div>
<h2>era</h2><div class="row">{''.join(_tile_html(t) for t in secs['era'])}</div>
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
        fetch_boards(boards_dir)
    if ns.once:
        out = Path(ns.out)
        out.write_text(render_html(build_state(outputs_dir, boards_dir)),
                       encoding="utf-8")
        print(f"operator page snapshot -> {out}")
        return 0
    return serve(outputs_dir, boards_dir, ns.port, not ns.no_render)
```

- [ ] **Step 4: run both test files' tests, expect PASS.**

- [ ] **Step 5: commit** — `feat(ops): operator page HTML + --once snapshot (SAFE)`

---

### Task 3: serve mode + board strip fetch + live verification

**Files:**
- Modify: `scripts/operator_page.py` (append `fetch_boards`, `serve`)
- Test: `tests/test_operator_page.py` (append fetch tests with injected fetcher)

**Interfaces:**
- Produces: `fetch_boards(boards_dir: Path, token_file: Path = TOKEN_FILE, fetcher=None) -> dict` (`{uid: "ok" | "error: ..."}`; fetcher injectable, signature `fetcher(url: str, headers: dict) -> bytes`); `serve(outputs_dir, boards_dir, port, render: bool) -> int`.

- [ ] **Step 1: failing tests** — append:

```python
def test_fetch_boards_injected(tmp_path):
    calls = []
    def fake(url, headers):
        calls.append(url)
        assert "Authorization" in headers
        return b"PNG"
    res = fetch_boards(tmp_path, token_file=tmp_path / "tok",
                       fetcher=fake)
    (tmp_path / "tok").write_text("x")  # not needed; token read inside
    assert len(calls) == 0 or True  # placeholder-free: see below


def test_fetch_boards_writes_and_reports(tmp_path):
    tok = tmp_path / "tok"
    tok.write_text("secret", encoding="utf-8")
    def fake(url, headers):
        assert headers["Authorization"] == "Bearer secret"
        return b"\x89PNG"
    res = fetch_boards(tmp_path, token_file=tok, fetcher=fake)
    assert all(v == "ok" for v in res.values())
    assert (tmp_path / "liquiditybot-trading.png").read_bytes() == b"\x89PNG"


def test_fetch_boards_no_token_is_skip(tmp_path):
    res = fetch_boards(tmp_path, token_file=tmp_path / "absent",
                       fetcher=lambda u, h: b"x")
    assert all(v.startswith("skip") for v in res.values())
    assert not list(tmp_path.glob("*.png"))
```

(Delete `test_fetch_boards_injected` — superseded by the two precise tests; it exists only as a drafting step marker. Do not ship it.)

- [ ] **Step 2: run, expect ImportError on fetch_boards.**

- [ ] **Step 3: implementation** — append:

```python
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
                if render:
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
```

- [ ] **Step 4: run full test file, expect all PASS.**

- [ ] **Step 5: live verification** —
  - `.venv/Scripts/python.exe scripts/operator_page.py --once --no-render` → snapshot written; open the HTML and confirm tiles + red badges render.
  - `.venv/Scripts/python.exe scripts/operator_page.py --once` → boards refreshed (4 PNG mtimes update), snapshot written.
  - Serve smoke: launch detached, `curl http://127.0.0.1:8787/state` returns JSON, `curl /` returns HTML; then kill.

- [ ] **Step 6: scoped gates** — pytest `tests/test_operator_page.py tests/test_code_registry.py tests/test_dependency_hygiene.py -q -p no:cacheprovider`; `ruff check scripts/operator_page.py tests/test_operator_page.py`; `bandit -c pyproject.toml scripts/operator_page.py`; compileall.

- [ ] **Step 7: commit** — `feat(ops): operator page serve mode + board strip (SAFE)` — add ONLY the two files; foreign in-flight diff untouched.

## Self-review notes

- Spec coverage: serve (T3), --once (T2), all six sections (T1–T3), correctness contract (T1), staleness/mismatch/nosource tests (T1–T2), no-network tests (T3 injected fetcher), live verify (T3 step 5).
- Era payload `generated_at` is ISO via `time.strptime` — parses the documented format; on drift the tile goes nosource (correct by contract).
- `--once` with `--no-render` still embeds cached board mtimes — age badges stay truthful.
