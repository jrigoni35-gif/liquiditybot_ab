"""
core/fault.py — central fault manager (Assurance Build)

Spacecraft-style fault protection adapted to a trading system: faults
LATCH (they do not clear because the symptom paused), each fault maps
to an explicit degraded-mode policy, and recovery is an operator
action, never a timeout.

Operational states (monotone-safe transitions only):
  INIT      constructing; nothing may trade
  ARMED     nominal; entries + exits allowed (subject to all gates)
  DEGRADED  >=1 non-critical fault latched: NEW RISK REFUSED,
            exits/hedge-unwinds run normally
  HALTED    critical fault or operator halt: flatten-and-stop posture

Policy queries (what modules actually ask):
  allow_new_risk()   -> ARMED only
  allow_exits()      -> always True (blocking risk reduction is never
                        the safe branch of any failure)

Latching a CRITICAL fault forces HALTED; any fault forces at least
DEGRADED. clear_fault() requires the operator to name the fault key —
"clear everything" is deliberately not an API. Every transition and
latch is written to the audit chain.

This module is pure bookkeeping: no network, no exceptions escape.
"""

import logging
import threading
from dataclasses import dataclass
from enum import Enum

from core.audit import get_audit
from core.codes import Code

log = logging.getLogger("liquiditybot.core.fault")


class OpState(str, Enum):
    INIT = "INIT"
    ARMED = "ARMED"
    DEGRADED = "DEGRADED"
    HALTED = "HALTED"


class Severity(str, Enum):
    WARNING = "WARNING"      # logged; no state change
    FAULT = "FAULT"          # latches; forces >= DEGRADED
    CRITICAL = "CRITICAL"    # latches; forces HALTED


@dataclass
class FaultRecord:
    key: str
    severity: Severity
    detail: str
    ts_wall: float = 0.0
    count: int = 1


class FaultManager:
    _MAX_FAULTS = 128        # bounded table; overflow is itself a fault

    def __init__(self, alerts=None):
        self._lock = threading.Lock()
        self._faults: dict = {}
        self.state = OpState.INIT
        self.alerts = alerts

    # ------------------------------------------------------------------
    def arm(self):
        """INIT -> ARMED once startup validation passed."""
        with self._lock:
            if self.state is OpState.INIT and not self._faults:
                self._set_state(OpState.ARMED, "startup validation passed")

    def latch(self, key: str, severity: Severity, detail: str):
        import time
        with self._lock:
            if len(self._faults) >= self._MAX_FAULTS and key not in self._faults:
                key, detail = "fault_table_overflow", \
                    f"fault table full; latest dropped fault: {key}"
                severity = Severity.CRITICAL
            rec = self._faults.get(key)
            if rec:
                rec.count += 1
                rec.detail = detail
                # a re-latch may ESCALATE severity, never soften it: the
                # record must reflect the worst level seen or clear_fault's
                # "no critical faults remain" check reads a stale WARNING and
                # downgrades HALTED while the critical condition persists
                order = {Severity.WARNING: 0, Severity.FAULT: 1,
                         Severity.CRITICAL: 2}
                if order[severity] > order[rec.severity]:
                    rec.severity = severity
            else:
                self._faults[key] = FaultRecord(key, severity, detail,
                                                ts_wall=time.time())
            log.critical("FAULT LATCHED [%s/%s] %s", key, severity.value,
                         detail)
            get_audit().log("fault", Code.FT_LATCHED, detail,
                            {"key": key, "severity": severity.value})
            if self.alerts is not None and severity is not Severity.WARNING:
                try:
                    self.alerts.fire(f"fault_{key}", detail, level="CRITICAL")
                except Exception:            # alerting must never cascade
                    log.error("alert sink failed while reporting a fault")
            if severity is Severity.CRITICAL:
                self._set_state(OpState.HALTED, f"critical fault: {key}")
            elif severity is Severity.FAULT and self.state is OpState.ARMED:
                self._set_state(OpState.DEGRADED, f"fault latched: {key}")

    def clear_fault(self, key: str, operator: str = "operator") -> bool:
        with self._lock:
            rec = self._faults.pop(key, None)
            if rec is None:
                return False
            get_audit().log("fault", Code.FT_CLEARED,
                            f"{key} cleared by {operator}",
                            {"was": rec.severity.value})
            log.warning("fault %s CLEARED by %s", key, operator)
            if not self._faults and self.state in (OpState.DEGRADED,
                                                   OpState.HALTED):
                self._set_state(OpState.ARMED, "all faults cleared")
            elif self._faults and self.state is OpState.HALTED and \
                    all(f.severity is not Severity.CRITICAL
                        for f in self._faults.values()):
                self._set_state(OpState.DEGRADED, "no critical faults remain")
            return True

    def _set_state(self, new: OpState, why: str):
        old, self.state = self.state, new
        log.warning("op-state %s -> %s (%s)", old.value, new.value, why)
        get_audit().log("fault", Code.FT_STATE_CHANGE, why,
                        {"from": old.value, "to": new.value})

    # ------------------------------------------------------------------
    def allow_new_risk(self) -> bool:
        return self.state is OpState.ARMED

    @staticmethod
    def allow_exits() -> bool:
        return True

    def status(self) -> dict:
        with self._lock:
            return {"state": self.state.value,
                    "faults": {k: {"severity": f.severity.value,
                                   "detail": f.detail, "count": f.count}
                               for k, f in self._faults.items()}}
