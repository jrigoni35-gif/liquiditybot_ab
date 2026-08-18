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
import os
import threading
import time
from pathlib import Path

from core import code_stats
from core.codes import Code

log = logging.getLogger("liquiditybot.core.audit")

_GENESIS = "0" * 16

# Registry MEMBERSHIP, not shape (2026-08-17): only code values actually
# registered in core/codes.py reach the frequency tally from log(). The
# earlier shape-only regex ("XX-NNN") let any canonical-LOOKING string —
# audit.log("qa_probe", "ZZ-999", ...) — mint a fake ZZ prefix in
# code_stats.by_prefix() on the exported ledger (injection-verified).
# The trail itself stays permissive: it records what happened, whatever
# the code string; only the frequency ledger is registry-strict.
_REGISTERED_CODES = frozenset(c.value for c in Code)


def _h(payload: str) -> str:
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


class AuditTrail:
    def __init__(self, path: str = "outputs/audit.jsonl", fsync: bool = True):
        self.path = Path(path)
        # fsync per write is right for the LIVE trail of record; QA harnesses
        # that redirect the audit (configure_audit) run the engine over 200x1200
        # replay/trial cycles where a per-disposition disk-flush dominates
        # wall-clock and buys nothing (tempdir, thrown away) — they pass False.
        self._fsync = bool(fsync)
        self._lock = threading.Lock()
        self._seq = 0
        self._prev = _GENESIS
        self._synced = False     # tail re-adopted at first write, see log()
        self.dropped = 0
        self.tail_truncations = 0    # torn final lines recovered (unclean stops)
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._adopt_tail()
        except (OSError, ValueError):
            log.error("audit trail unreadable at startup - chain restarts "
                      "from genesis (verify() will show the seam)")

    def _adopt_tail(self):
        """Resume the chain from the last COMPLETE record on disk. seq never
        regresses: a process that read the tail early must not reuse sequence
        numbers another writer appended in the meantime.

        A crash mid-append leaves a TORN (unparseable) final line. The old code
        did json.loads on it, raised, was swallowed, and the chain restarted
        from genesis (seq=1, prev=GENESIS) — colliding seqs AND a permanent
        mid-file break once the next record appended. Instead we TRUNCATE the
        torn final line (an incomplete write was never a committed record) so
        the next append chains cleanly onto the last good record. Only an
        UNPARSEABLE final line is truncated; a complete-but-altered record is
        tamper evidence and is left for verify() to surface."""
        if not self.path.exists():
            return
        while True:
            last_off, last = None, None
            with open(self.path, "rb") as f:
                off = 0
                for raw in f:
                    if raw.strip():
                        last_off, last = off, raw.strip()
                    off += len(raw)
            if last is None:
                return                       # empty file: stay at genesis
            try:
                rec = json.loads(last)
                seq = int(rec.get("seq", 0))    # TypeError on a null/dict seq
            except (ValueError, TypeError):
                # torn OR malformed final line (bad bytes, or a non-int seq our
                # writer never produces): drop it and re-examine the new tail.
                # int() is INSIDE the guard so a malformed record can't raise
                # out of log()'s first-write re-adopt (its "never raises"
                # contract) — it was previously outside and could TypeError.
                with open(self.path, "r+b") as f:
                    f.truncate(last_off)
                self.tail_truncations += 1
                log.warning("audit: truncated a torn/malformed final line at "
                            "byte %d so the chain resumes cleanly", last_off)
                continue
            self._seq = max(self._seq, seq)
            self._prev = str(rec.get("h", _GENESIS))
            # repair a missing trailing newline: if a crash dropped only the
            # final '\n' but kept the record bytes, the next append would
            # concatenate onto it into one line that a LATER _adopt_tail reads
            # as unparseable and truncates — silently destroying BOTH records.
            try:
                with open(self.path, "rb") as f:
                    f.seek(-1, 2)
                    if f.read(1) != b"\n":
                        with open(self.path, "ab") as af:
                            af.write(b"\n")
            except OSError:
                pass
            return

    # ------------------------------------------------------------------
    def log(self, src: str, code, msg: str, data: dict | None = None, *,
            counted: bool = False) -> int:
        """Append one chained record. Returns its seq (0 on failure).

        FREQUENCY LANE (2026-08-17): every audited REGISTERED code (a value
        of core/codes.py's Code enum — _REGISTERED_CODES above; shape alone
        is not enough) also bumps core/code_stats.py, so audit-only
        emissions (ML-*, OM-000/040, FT-*, RP-070/071/072/042, RT-010,
        CG-000, ...) finally reach the central {code: count} ledger that
        status.json/by_prefix and the exported liquiditybot_code_count
        read — before this, only tag() bumped, and those prefixes could
        never appear on the glass. Non-member code strings (freeform,
        src-like, or canonical-shaped-but-unregistered) are still written
        to the trail but never bump. One EMISSION counts ONCE, guarded two
        ways against the call sites that already bumped via tag():
          * the tag idiom — ``log(src, code, tag(code, detail))`` — is
            detected by the msg carrying the "CODE: " prefix tag() renders,
            and is not re-counted;
          * ``counted=True`` is for call sites whose SAME emission already
            tag()'d the code into a DIFFERENT string (risk_firewall's
            reject/clamp paths build reasons/notes with tag() and audit a
            separate summary msg).
        The bump never raises (code_stats contract) and happens whether or
        not the disk write below succeeds — the tally counts emissions;
        `dropped` counts write holes."""
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
            code_val = getattr(code, "value", None)
            if not isinstance(code_val, str):
                code_val = str(code)
            if (not counted and code_val in _REGISTERED_CODES
                    and not str(msg).startswith(code_val + ":")):
                code_stats.bump(code_val)
            self._seq += 1
            rec = {"seq": self._seq, "ts": round(time.time(), 3),
                   "src": str(src),
                   "code": code_val,
                   "msg": str(msg)[:2000],
                   "data": data or {},
                   "prev": self._prev}
            try:
                # serialization is INSIDE the try: a caller can hand us a data
                # payload that json.dumps chokes on (sort_keys=True over non-
                # comparable keys -> TypeError). That must drop the record, not
                # raise back into the disposition call site (order transition,
                # firewall reject) and abort the very action being audited.
                body = json.dumps(rec, sort_keys=True, default=str)
                rec["h"] = _h(body)
                line = json.dumps(rec, sort_keys=True, default=str)
                with open(self.path, "a", encoding="utf-8") as f:
                    f.write(line + "\n")
                    f.flush()
                    # fsync so a record that returned a seq is durable across a
                    # power loss - flush alone leaves it in the OS page cache.
                    # This is the regulated trail of record; the audit write
                    # rate (per disposition, not per tick) makes the cost fine.
                    if self._fsync:
                        os.fsync(f.fileno())
                self._prev = rec["h"]
                return self._seq
            except (OSError, TypeError, ValueError):
                self.dropped += 1
                self._seq -= 1
                # Re-arm the tail adoption (2026-08-06). An OSError can fire
                # PART-WAY THROUGH f.write, leaving orphan bytes with no
                # newline; _synced was already True, so no later log() ever
                # re-adopted and the next append WELDED onto that fragment.
                # Once further records followed, verify_chain saw a break
                # with tail_after_break > 0 -> torn=False -> tamper=True,
                # PERMANENTLY: crash damage presenting as tampering on the
                # regulated trail of record. _adopt_tail already truncates a
                # torn/malformed final line, so re-arming it heals the
                # fragment on the next write instead of fusing onto it.
                self._synced = False
                log.error("AUDIT WRITE FAILED (dropped=%d) - trail has a hole; "
                          "investigate disk or payload", self.dropped)
                return 0

    # ------------------------------------------------------------------
    def verify(self) -> dict:
        """Replay the chain; report integrity. Bounded by file size.

        Three anomaly classes (see verify_chain for the full rationale):
          * TORN TAIL (torn_tail=True): incomplete final line from a crash
            mid-append; chain intact through `records`. Benign.
          * WRITER SEAM (seams>0, tamper=False): a hash-valid record whose
            prev forks back to an earlier record — two writers overlapped.
            Nothing committed was altered. Benign, permanently in the file.
          * TAMPER (tamper=True): an edited record (own-hash mismatch) or a
            deleted one (dangling prev). The alarm class.
        ok=True only for a single clean chain (no anomaly of any kind); a
        caller that only cares about TAMPER consults the tamper bit, not
        ok. Delegates to verify_chain() — a read-only pass that NEVER
        mutates the file (construction's _adopt_tail is what heals a torn
        tail; verify itself must not, so external callers can inspect a
        bundle's trail without truncating it)."""
        r = verify_chain(self.path)
        r["dropped_writes"] = self.dropped
        return r


def verify_chain(path) -> dict:
    """Read-only chain replay of a JSONL audit file. NEVER mutates the file
    (unlike constructing an AuditTrail, whose _adopt_tail heals a torn tail) —
    so session_import and operators can inspect a bundle's trail without
    truncating it.

    Three anomaly classes, because they mean very different things:
      * TORN TAIL (benign): unparseable FINAL line, nothing valid after — a
        crash mid-append.
      * WRITER SEAM (benign): a record whose OWN hash is valid but whose
        prev resolves to an EARLIER verified record (or GENESIS — the
        designed unreadable-at-startup refork). Two writers forked the
        chain (dual-runner window, SD-007); nothing committed was altered.
        The chain is adopted through the seam (later records chained onto
        it physically) and verification continues.
      * TAMPER (loud): an edited record (own-hash mismatch) or a deleted
        one (successor's prev resolves NOWHERE). This is the alarm class.

    Classification is sound against the naive-tamper modes the unkeyed
    chain can catch: editing a record breaks its own sha256 before any
    prev logic runs, and deleting one removes its hash from the file so
    the successor's prev dangles — neither can be laundered as a seam. A
    deliberate adversary with file-write access could always recompute
    the whole unkeyed tail; the chain never defended against that, and
    the seam class does not change it."""
    n, prev = 0, _GENESIS
    first_break = None
    first_break_torn = False          # True iff the breaking line was UNPARSEABLE
    tail_after_break = 0
    seams = 0
    seen: dict = {}                   # h -> ordinal of every verified record
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                # strip trailing whitespace AND NUL padding: some filesystems
                # leave a run of \x00 after a torn append into a freshly-
                # extended block, and NUL is not whitespace (a NUL-only line
                # must read as blank, not as "content after the break").
                line = line.strip().strip("\x00").strip()
                if not line:
                    continue
                if first_break is not None:
                    tail_after_break += 1     # real content past the break
                    continue
                try:
                    rec = json.loads(line)
                except ValueError:
                    # incomplete/corrupt BYTES = a crashed append (torn tail
                    # candidate — only if nothing valid follows it)
                    first_break, first_break_torn = n + 1, True
                    continue
                try:
                    h = rec.pop("h", None)
                    body = json.dumps(rec, sort_keys=True, default=str)
                    if _h(body) != h:
                        # the record's own bytes changed: tamper, before any
                        # prev logic can classify it as a seam
                        raise ValueError("record hash mismatch")
                    rp = rec.get("prev")
                    if rp != prev:
                        if rp in seen or rp == _GENESIS:
                            seams += 1        # hash-valid fork: benign seam
                        else:
                            # prev resolves nowhere: a committed record was
                            # removed from under its successor
                            raise ValueError("dangling prev")
                    prev = h
                    seen[h] = n + 1
                    n += 1
                except (ValueError, KeyError, AttributeError, TypeError):
                    # a COMPLETE record that fails the hash check or whose
                    # prev dangles is TAMPER (or genuine corruption of a
                    # committed record), NOT a benign crash or seam.
                    first_break, first_break_torn = n + 1, False
    except OSError:
        return {"ok": False, "records": 0, "error": "unreadable",
                "first_break": None, "torn_tail": False,
                "seams": 0, "tamper": True}
    torn = (first_break is not None and tail_after_break == 0
            and first_break_torn)
    return {"ok": first_break is None and seams == 0, "records": n,
            "first_break": first_break,
            # torn_tail ONLY when the breaking line was an UNPARSEABLE final line
            # with nothing valid after it (a crashed append). A complete-but-
            # altered final record is tamper, not a torn tail.
            "torn_tail": torn,
            "seams": seams,
            # the alarm bit: a break that is neither a torn tail nor a seam
            "tamper": first_break is not None and not torn}


_AUDIT = None


def get_audit() -> AuditTrail:
    global _AUDIT
    if _AUDIT is None:
        _AUDIT = AuditTrail()
    return _AUDIT


def configure_audit(path, fsync: bool = False) -> AuditTrail:
    """Point the process-wide singleton at `path`. QA harnesses (smoke,
    assurance, trials) MUST call this before constructing any engine
    component: their synthetic order/fault/self-test records once landed
    in the production trail, burying real dispositions and colliding
    with the live runner's chain (SD-007). fsync defaults OFF here: a
    redirected trail is a throwaway tempdir, and per-write fsync over the
    200x1200 replay/trial cycles is pure wall-clock tax with no durability
    value. The live singleton (get_audit) keeps fsync ON."""
    global _AUDIT
    _AUDIT = AuditTrail(path, fsync=fsync)
    return _AUDIT
