"""
scripts/gc_log_pusher.py — ship events.jsonl to Grafana Cloud Loki.

Sidecar, not engine code: tails the bot's structured event log
(outputs/events.jsonl — {ts, level, logger, msg} per line, written by
JsonlLogHandler) and pushes OTLP log records to the same Grafana Cloud
OTLP gateway the metrics pusher uses, same credentials, zero new
secrets. Loki then answers questions metrics can't: "every ML-071 this
week", "all CRITICAL overnight", "every rejection on MINA".

Fail-safe and restart-safe: the byte offset into events.jsonl is
persisted only AFTER a successful push, so a failed tick re-ships
rather than drops; a rotated/truncated file resets the offset. Any
error logs one line and retries next tick. The bot never knows this
exists.

Configuration is environment-only, no secrets in the repo or argv:

  GC_OTLP_URL       OTLP gateway metrics endpoint (the logs endpoint is
                    derived by replacing /v1/metrics with /v1/logs), or
  GC_OTLP_LOGS_URL  explicit logs endpoint (overrides derivation)
  GC_INSTANCE_ID    numeric Grafana Cloud instance for Basic auth
  GC_TOKEN_FILE     path to a chmod-600 file with the write token
  LB_EVENTS         event log path (default: outputs/events.jsonl)
  GC_LOG_STATE      offset-state path (default: outputs/.gc_log_offset)
  GC_LOG_PERIOD_SEC poll interval seconds (default: 10)
"""
import base64
import json
import os
import time
import urllib.request

_SEV = {"DEBUG": 5, "INFO": 9, "WARNING": 13, "ERROR": 17, "CRITICAL": 21}
_BATCH = 500          # records per push request
_MAX_MSG = 4096       # truncate pathological lines, keep Loki happy


def _cfg() -> dict:
    url = os.environ.get("GC_OTLP_LOGS_URL", "")
    if not url:
        base = os.environ.get("GC_OTLP_URL", "")
        if base.endswith("/v1/metrics"):
            url = base[: -len("/v1/metrics")] + "/v1/logs"
    instance = os.environ.get("GC_INSTANCE_ID", "")
    token_file = os.environ.get("GC_TOKEN_FILE", "")
    if not (url.startswith("https://") and instance and token_file):
        raise SystemExit(
            "gc_log_pusher: set GC_OTLP_URL (or GC_OTLP_LOGS_URL), "
            "GC_INSTANCE_ID and GC_TOKEN_FILE — see the module docstring")
    with open(token_file, encoding="utf-8") as fh:
        token = fh.read().strip()
    return {
        "url": url,
        "auth": base64.b64encode(f"{instance}:{token}".encode()).decode(),
        "events": os.environ.get("LB_EVENTS", "outputs/events.jsonl"),
        "state": os.environ.get("GC_LOG_STATE", "outputs/.gc_log_offset"),
        "period": float(os.environ.get("GC_LOG_PERIOD_SEC", "10")),
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


def _record(line: str):
    """One JSONL event -> one OTLP logRecord (None for junk lines)."""
    try:
        e = json.loads(line)
        ts = float(e["ts"])
        level = str(e.get("level", "INFO")).upper()
        msg = str(e.get("msg", ""))[:_MAX_MSG]
        logger = str(e.get("logger", ""))
    except Exception:
        return None
    return {
        "timeUnixNano": str(int(ts * 1e9)),
        "severityText": level,
        "severityNumber": _SEV.get(level, 9),
        "body": {"stringValue": msg},
        "attributes": [
            {"key": "logger", "value": {"stringValue": logger}},
        ],
    }


def _push(cfg: dict, records: list) -> None:
    body = {"resourceLogs": [{
        "resource": {"attributes": [
            {"key": "service.name",
             "value": {"stringValue": "liquiditybot"}}]},
        "scopeLogs": [{"logRecords": records}]}]}
    req = urllib.request.Request(
        cfg["url"], data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json",
                 "Authorization": f"Basic {cfg['auth']}"})
    # scheme validated to https in _cfg()
    with urllib.request.urlopen(req, timeout=30) as r:  # nosec B310
        r.read()


def tick(cfg: dict) -> int:
    """Ship everything new since the saved offset. Returns records sent."""
    st = _load_state(cfg["state"])
    try:
        stat = os.stat(cfg["events"])
    except FileNotFoundError:
        return 0
    inode = getattr(stat, "st_ino", None)
    offset = st["offset"]
    if st["inode"] != inode or stat.st_size < offset:
        offset = 0                        # rotation/truncation: start over
    if stat.st_size == offset:
        return 0
    sent = 0
    with open(cfg["events"], "r", encoding="utf-8", errors="replace") as fh:
        fh.seek(offset)
        while True:
            batch, consumed = [], 0
            while len(batch) < _BATCH:
                pos = fh.tell()
                line = fh.readline()
                if not line or not line.endswith("\n"):
                    fh.seek(pos)          # partial write: retry next tick
                    break
                rec = _record(line)
                if rec is not None:
                    batch.append(rec)
                consumed = fh.tell()
            if not batch:
                break
            _push(cfg, batch)             # raises on failure -> no advance
            offset = consumed
            _save_state(cfg["state"], inode, offset)
            sent += len(batch)
    return sent


# Restart-coupling guard (same as gc_pusher): the supervisor relaunches
# this sidecar only when it dies, so deploys never reached a long-lived
# process. Exit when our source changes on disk; supervisor brings us back.
_BOOT_MTIME = os.path.getmtime(os.path.abspath(__file__))


def _source_changed() -> bool:
    try:
        return os.path.getmtime(os.path.abspath(__file__)) != _BOOT_MTIME
    except OSError:
        return False       # staying alive is the fail-safe


def main() -> None:
    cfg = _cfg()
    while True:
        try:
            n = tick(cfg)
            if n:
                print(f"{time.strftime('%H:%M:%S')} shipped {n} events",
                      flush=True)
        except Exception as e:
            print(f"{time.strftime('%H:%M:%S')} ship failed: {e}",
                  flush=True)
        if _source_changed():
            print(f"{time.strftime('%H:%M:%S')} source changed on disk "
                  f"(deploy) - exiting; supervisor relaunches on new code",
                  flush=True)
            return
        time.sleep(cfg["period"])


if __name__ == "__main__":
    main()
