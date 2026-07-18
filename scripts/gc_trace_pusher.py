"""
scripts/gc_trace_pusher.py — order-lifecycle spans to Grafana Cloud Traces.

Feeds the Traces drilldown (RED: Rate / Errors / Duration of order flow).
Tails outputs/audit.jsonl and converts every ORDER TERMINAL record
(OM-000 clean terminal / OM-040 timeout) into ONE OTLP span:

  span      = the order's whole life, created_ts -> terminal ts
  status    = ERROR when the order died unfilled (rejected/expired/
              cancelled at fill_ratio 0) — the venue never gave us the
              trade we asked for; partial or full fills are OK
  attributes: pair, side, purpose, terminal state, fill_ratio,
              fees_usd, reprices

Same contract as the other pushers: stdlib-only, read-only on the bot's
files, fail-safe (a push failure never advances the offset — retries,
never drops), restart-safe byte-offset state, rotation resets. The
traces endpoint accepts the SAME access-policy token as metrics/logs
(probed live 2026-07-18: HTTP 200 on /otlp/v1/traces).

ENV: GC_OTLP_URL (metrics endpoint; traces endpoint derived) or
GC_OTLP_TRACES_URL explicit; GC_INSTANCE_ID; GC_TOKEN_FILE;
GC_TRACE_STATE (default outputs/.gc_trace_offset);
GC_TRACE_PERIOD_SEC (default 60).
"""
import base64
import hashlib
import json
import os
import time
import urllib.request

_BATCH = 100
_TERMINAL_ERROR = {"rejected", "expired", "cancelled"}


def _cfg() -> dict:
    url = os.environ.get("GC_OTLP_TRACES_URL", "")
    if not url:
        base = os.environ.get("GC_OTLP_URL", "")
        if base.endswith("/v1/metrics"):
            url = base[: -len("/v1/metrics")] + "/v1/traces"
    instance = os.environ.get("GC_INSTANCE_ID", "")
    token_file = os.environ.get("GC_TOKEN_FILE", "")
    if not (url.startswith("https://") and instance and token_file):
        raise SystemExit(
            "gc_trace_pusher: set GC_OTLP_URL (or GC_OTLP_TRACES_URL), "
            "GC_INSTANCE_ID and GC_TOKEN_FILE — see the module docstring")
    with open(token_file, encoding="utf-8") as fh:
        token = fh.read().strip()
    return {
        "url": url,
        "auth": base64.b64encode(f"{instance}:{token}".encode()).decode(),
        "audit": os.environ.get("LB_AUDIT", "outputs/audit.jsonl"),
        "state": os.environ.get("GC_TRACE_STATE",
                                "outputs/.gc_trace_offset"),
        "period": float(os.environ.get("GC_TRACE_PERIOD_SEC", "60")),
    }


def _load_state(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return {"inode": None, "offset": 0}


def _save_state(path: str, inode, offset: int) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump({"inode": inode, "offset": offset}, fh)
    os.replace(tmp, path)


def _attr(key, value):
    if isinstance(value, bool):
        return {"key": key, "value": {"boolValue": value}}
    if isinstance(value, (int, float)):
        return {"key": key, "value": {"doubleValue": float(value)}}
    return {"key": key, "value": {"stringValue": str(value)}}


def span_of(line: str):
    """One audit line -> one OTLP span dict, or None (not an order
    terminal / missing lifecycle fields / malformed). PURE."""
    try:
        r = json.loads(line)
    except json.JSONDecodeError:
        return None
    if r.get("code") not in ("OM-000", "OM-040") or r.get("src") != \
            "order_manager":
        return None
    d = r.get("data") or {}
    try:
        end_ts = float(r["ts"])
        start_ts = float(d["created_ts"])
        oid = str(d["order_id"])
    except (KeyError, TypeError, ValueError):
        return None                      # pre-upgrade record: no lifecycle
    if not (0 < start_ts <= end_ts):
        return None
    terminal = str(d.get("terminal", "?"))
    fill_ratio = float(d.get("fill_ratio", 0.0) or 0.0)
    failed = terminal in _TERMINAL_ERROR and fill_ratio <= 0.0
    digest = hashlib.sha256(oid.encode()).hexdigest()
    return {
        "traceId": digest[:32],
        "spanId": digest[32:48],
        "name": f"order.{d.get('purpose', '?')}",
        "kind": 3,                       # CLIENT: we call the venue
        "startTimeUnixNano": str(int(start_ts * 1e9)),
        "endTimeUnixNano": str(int(end_ts * 1e9)),
        "status": {"code": 2 if failed else 1},
        "attributes": [
            _attr("pair", d.get("pair", "?")),
            _attr("side", d.get("side", "?")),
            _attr("purpose", d.get("purpose", "?")),
            _attr("terminal", terminal),
            _attr("fill_ratio", fill_ratio),
            _attr("fees_usd", float(d.get("fees_usd", 0.0) or 0.0)),
            _attr("reprices", float(d.get("reprices", 0) or 0)),
        ],
    }


def _push(cfg: dict, spans: list) -> None:
    body = {"resourceSpans": [{
        "resource": {"attributes": [
            {"key": "service.name",
             "value": {"stringValue": "liquiditybot"}}]},
        "scopeSpans": [{"scope": {"name": "order_manager"},
                        "spans": spans}]}]}
    req = urllib.request.Request(
        cfg["url"], data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json",
                 "Authorization": f"Basic {cfg['auth']}"})
    # scheme validated to https in _cfg()
    with urllib.request.urlopen(req, timeout=30) as r:  # nosec B310
        r.read()


def tick(cfg: dict) -> int:
    """Ship every new order-terminal span since the saved offset."""
    st = _load_state(cfg["state"])
    try:
        stat = os.stat(cfg["audit"])
    except FileNotFoundError:
        return 0
    inode = getattr(stat, "st_ino", None)
    offset = st["offset"]
    if st["inode"] != inode or stat.st_size < offset:
        offset = 0                        # rotation/truncation: start over
    if stat.st_size == offset:
        return 0
    sent = 0
    with open(cfg["audit"], "r", encoding="utf-8", errors="replace") as fh:
        fh.seek(offset)
        while True:
            batch, consumed = [], 0
            while len(batch) < _BATCH:
                pos = fh.tell()
                line = fh.readline()
                if not line or not line.endswith("\n"):
                    fh.seek(pos)          # partial write: retry next tick
                    break
                sp = span_of(line)
                if sp is not None:
                    batch.append(sp)
                consumed = fh.tell()
            if consumed > offset and not batch:
                # progress with no spans (non-order records): advance
                offset = consumed
                _save_state(cfg["state"], inode, offset)
                continue
            if not batch:
                break
            _push(cfg, batch)             # raises on failure -> no advance
            offset = consumed
            _save_state(cfg["state"], inode, offset)
            sent += len(batch)
    return sent


def main() -> None:
    cfg = _cfg()
    while True:
        try:
            n = tick(cfg)
            # heartbeat EVERY tick: the supervisor judges liveness by log
            # mtime, and order terminals are rare — a silent quiet period
            # would read as dead and spawn a duplicate pusher
            print(f"{time.strftime('%H:%M:%S')} tick "
                  f"({n} span(s) shipped)", flush=True)
        except Exception as e:
            print(f"{time.strftime('%H:%M:%S')} ship failed: {e}",
                  flush=True)
        time.sleep(cfg["period"])


if __name__ == "__main__":
    main()
