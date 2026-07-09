"""
core/audit.py — tamper-evident audit trail (Assurance Build)

Append-only JSONL record of every consequential decision: order
verdicts, firewall actions, model deployments, fault latches, config
fingerprints. Each record carries the SHA-256 of the previous record
(hash chaining), so any after-the-fact edit, deletion, or reordering
of the file breaks the chain at exactly the point of tampering —
the property regulators mean by "immutable audit trail" implemented
at the file level.

Record shape (one JSON object per line):
  {"seq": n, "ts": wall, "src": "firewall", "code": "FW-040",
   "msg": "...", "data": {...}, "prev": "<hex16>", "h": "<hex16>"}

Design rules:
  * Never raises into the caller: an audit-write failure logs an
    ERROR and increments a dropped-record counter, but a broken disk
    must not take the trading loop down with it. The counter is
    exposed so "the audit trail has holes" is itself visible.
  * Writes are line-buffered appends with flush; the chain hash makes
    partial-line corruption from a crash detectable on verify().
  * verify() replays the chain and reports the first broken link.

Module-level singleton via get_audit(); modules call
  get_audit().log("firewall", Code.FW_040, "notional reject", {...})
"""

import hashlib
import json
import logging
import threading
import time
from pathlib import Path

log = logging.getLogger("liquiditybot.core.audit")

_GENESIS = "0" * 16


def _h(payload: str) -> str:
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


class AuditTrail:
    def __init__(self, path: str = "outputs/audit.jsonl"):
        self.path = Path(path)
        self._lock = threading.Lock()
        self._seq = 0
        self._prev = _GENESIS
        self._synced = False     # tail re-adopted at first write, see log()
        self.dropped = 0
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._adopt_tail()
        except (OSError, ValueError):
            log.error("audit trail unreadable at startup - chain restarts "
                      "from genesis (verify() will show the seam)")

    def _adopt_tail(self):
        """Resume the chain from the last record on disk. seq never
        regresses: a process that read the tail early must not reuse
        sequence numbers another writer appended in the meantime."""
        if not self.path.exists():
            return
        last = None
        with open(self.path, "rb") as f:
            for raw in f:
                raw = raw.strip()
                if raw:
                    last = raw
        if last:
            rec = json.loads(last)
            self._seq = max(self._seq, int(rec.get("seq", 0)))
            self._prev = str(rec.get("h", _GENESIS))

    # ------------------------------------------------------------------
    def log(self, src: str, code, msg: str, data: dict | None = None) -> int:
        """Append one chained record. Returns its seq (0 on failure)."""
        with self._lock:
            if not self._synced:
                # a long gap between construction and first write (runner
                # boot) once let another writer advance the file in between;
                # this instance then reused its stale seq/prev and broke the
                # chain (SD-007). Re-adopt the tail at the last moment.
                try:
                    self._adopt_tail()
                except (OSError, ValueError):
                    pass                     # keep in-memory chain state
                self._synced = True
            self._seq += 1
            rec = {"seq": self._seq, "ts": round(time.time(), 3),
                   "src": str(src),
                   "code": getattr(code, "value", str(code)),
                   "msg": str(msg)[:2000],
                   "data": data or {},
                   "prev": self._prev}
            body = json.dumps(rec, sort_keys=True, default=str)
            rec["h"] = _h(body)
            try:
                with open(self.path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(rec, sort_keys=True, default=str)
                            + "\n")
                    f.flush()
                self._prev = rec["h"]
                return self._seq
            except OSError:
                self.dropped += 1
                self._seq -= 1
                log.error("AUDIT WRITE FAILED (dropped=%d) - trail has a "
                          "hole; investigate disk", self.dropped)
                return 0

    # ------------------------------------------------------------------
    def verify(self) -> dict:
        """Replay the chain; report integrity. Bounded by file size."""
        ok, n, prev = True, 0, _GENESIS
        first_break = None
        try:
            with open(self.path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                        h = rec.pop("h", None)
                        body = json.dumps(rec, sort_keys=True, default=str)
                        if rec.get("prev") != prev or _h(body) != h:
                            raise ValueError("chain break")
                        prev = h
                        n += 1
                    except (ValueError, KeyError):
                        ok = False
                        if first_break is None:
                            first_break = n + 1
                        break
        except OSError:
            return {"ok": False, "records": 0, "error": "unreadable"}
        return {"ok": ok, "records": n, "first_break": first_break,
                "dropped_writes": self.dropped}


_AUDIT = None


def get_audit() -> AuditTrail:
    global _AUDIT
    if _AUDIT is None:
        _AUDIT = AuditTrail()
    return _AUDIT


def configure_audit(path) -> AuditTrail:
    """Point the process-wide singleton at `path`. QA harnesses (smoke,
    assurance, trials) MUST call this before constructing any engine
    component: their synthetic order/fault/self-test records once landed
    in the production trail, burying real dispositions and colliding
    with the live runner's chain (SD-007)."""
    global _AUDIT
    _AUDIT = AuditTrail(path)
    return _AUDIT
