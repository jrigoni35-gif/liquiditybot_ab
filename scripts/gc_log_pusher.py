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


def _drain_rotated(cfg: dict, st: dict) -> int:
    """Ship the unshipped tail of the ROTATED predecessor (<events>.1).

    JsonlLogHandler renames events.jsonl -> events.jsonl.1 at the size cap;
    every line appended between this pusher's previous tick and the rotation
    sits in that renamed file, and resetting offset=0 on the new file alone
    dropped those lines from Loki forever - a silent hole at every rotation
    ('all CRITICAL overnight' could miss records that exist on disk). Same
    at-least-once contract as tick(): state advances (still under the OLD
    inode) only after a successful push, so an outage mid-drain re-ships on
    recovery rather than drops. Conservative by provenance: drains only
    when the saved inode is known and does not contradict the .1 file's."""
    prev = cfg["events"] + ".1"
    if st["inode"] is None:
        return 0                  # no provenance for the offset: never guess
    try:
        pstat = os.stat(prev)
    except OSError:
        return 0
    pino = getattr(pstat, "st_ino", None)
    if pino is not None and pino != st["inode"]:
        return 0                  # .1 is not the file the offset belongs to
    if pstat.st_size <= st["offset"]:
        return 0
    sent = 0
    with open(prev, "r", encoding="utf-8", errors="replace") as fh:
        fh.seek(st["offset"])
        while True:
            batch, consumed = [], 0
            while len(batch) < _BATCH:
                pos = fh.tell()
                line = fh.readline()
                if not line or not line.endswith("\n"):
                    fh.seek(pos)
                    break
                rec = _record(line)
                if rec is not None:
                    batch.append(rec)
                consumed = fh.tell()
            if consumed > st["offset"] and not batch:
                st["offset"] = consumed
                _save_state(cfg["state"], st["inode"], consumed)
                continue
            if not batch:
                break
            _push(cfg, batch)             # raises on failure -> no advance
            st["offset"] = consumed
            _save_state(cfg["state"], st["inode"], consumed)
            sent += len(batch)
    return sent


def tick(cfg: dict) -> int:
    """Ship everything new since the saved offset. Returns records sent."""
    st = _load_state(cfg["state"])
    try:
        stat = os.stat(cfg["events"])
    except FileNotFoundError:
        return 0
    inode = getattr(stat, "st_ino", None)
    offset = st["offset"]
    sent = 0
    if st["inode"] != inode or stat.st_size < offset:
        # rotation/truncation: ship the renamed predecessor's tail FIRST
        # (29g), then start over at 0 on the new file
        sent += _drain_rotated(cfg, st)
        offset = 0
    if stat.st_size == offset:
        return sent
    with open(cfg["events"], "r", encoding="utf-8", errors="replace") as fh:
        # provenance from the OPENED handle, not the earlier stat: the
        # drain above can take seconds of network time, and a rotation
        # inside that window would persist this read's offsets under the
        # PREVIOUS generation's inode - the next tick's drain would then
        # seek the .1 file at a foreign offset and silently skip its head.
        _fst = os.fstat(fh.fileno())
        inode = getattr(_fst, "st_ino", None)
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
            if consumed > offset and not batch:
                # progress with no records (junk/malformed lines only):
                # advance past them so they are not re-parsed every tick
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


# Restart-coupling guard (same as gc_pusher): the supervisor relaunches
# this sidecar only when it dies, so deploys never reached a long-lived
# process. Exit when our source changes on disk; supervisor brings us back.
_BOOT_MTIME = os.path.getmtime(os.path.abspath(__file__))


def _source_changed() -> bool:
    try:
        return os.path.getmtime(os.path.abspath(__file__)) != _BOOT_MTIME
    except OSError:
        return False       # staying alive is the fail-safe


# pc_supervisor judges this process alive by the mtime of its stdout log
# (STALE_SEC=120 there). Printing only when events ship made a QUIET pusher
# indistinguishable from a dead one: on 2026-08-02 22:05 the runner was down
# for a deploy bounce, no events flowed, the log went stale, and the
# supervisor spawned a second pusher next to a healthy first - both then
# shipped every log line twice for ~22h. The two sibling pushers never had
# the bug because they print every tick. Heartbeat cadence: comfortably
# inside the supervisor's 120s staleness window without matching the
# siblings' full every-tick volume.
_HEARTBEAT_SEC = 55.0


def main() -> None:
    cfg = _cfg()
    last_out = time.time()
    while True:
        try:
            n = tick(cfg)
            if n:
                print(f"{time.strftime('%H:%M:%S')} shipped {n} events",
                      flush=True)
                last_out = time.time()
            elif time.time() - last_out >= _HEARTBEAT_SEC:
                print(f"{time.strftime('%H:%M:%S')} alive, nothing to ship",
                      flush=True)
                last_out = time.time()
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
