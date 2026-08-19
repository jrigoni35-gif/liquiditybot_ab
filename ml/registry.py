"""
ml/registry.py — model registry & lineage (Assurance Build)

The SR 11-7 / OCC 2011-12 model-inventory requirement, implemented at
the file level. Every model artifact that can influence sizing gets:

  IDENTITY    model_id = first 12 hex of the artifact's SHA-256. The
              file IS its identity; a byte changed is a different model.
  MODEL CARD  who/what/when/how-well: kind, seed(s), training rows and
              class balance, sample-weight config, walk-forward OOF
              Brier/AUC, calibration method, feature schema version,
              top permutation importances, and the SHA-256 of the
              training data snapshot it learned from.
  LEDGER      outputs/models/registry.jsonl — append-only lifecycle
              events (registered / deployed / retired / rejected), one
              JSON object per line. The ledger is never rewritten.
  INTEGRITY   verify(path) recomputes the hash before any live load.
              A tampered or bit-rotted artifact fails closed: the
              service falls back to the prior and the failure is loud.

Answers the question every model-risk review starts with: "exactly
which model was making decisions at 3:47am on Tuesday, what data was
it trained on, and what did you know about it when you deployed it?"
"""

import hashlib
import json
import logging
import os
import time
from pathlib import Path

log = logging.getLogger("liquiditybot.ml.registry")


def sha256_file(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_array(arr) -> str:
    import numpy as np
    a = np.ascontiguousarray(np.asarray(arr, dtype=float))
    return hashlib.sha256(a.tobytes()).hexdigest()[:16]


def _canonical(path) -> str:
    """Windows is the runtime; an artifact path arrives with either
    separator style (str(Path) yields backslashes on Windows, forward
    slashes elsewhere). Canonicalize to forward slashes so register() and
    verify() agree — and so the FILE READ resolves — regardless of the
    caller's separator, matching the posix-keyed ledger. Backslash is a
    path separator on the target OS and never appears in this project's
    artifact filenames, so this is loss-free here."""
    return str(path).replace("\\", "/")


GENESIS = "0" * 16


def _record_hash(rec: dict) -> str:
    """Hash over the record's CONTENT plus its prev link, matching
    core/audit.py's construction: json with sorted keys so the digest is
    reproducible, truncated to 16 hex chars for a readable ledger."""
    body = {k: v for k, v in rec.items() if k != "h"}
    payload = json.dumps(body, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


class ModelRegistry:
    """Append-only, HASH-CHAINED model lineage ledger.

    The chain (added 2026-08-05) is what lets this file's guarantee match
    the language used about it. Before, "append-only ledger" described
    intent only: rows carried no prev-hash and no sequence, so verify()
    scanned for the last matching row and compared ONE unauthenticated
    sha256 string. Deleting, truncating or reordering the ledger was
    undetectable; editing the last registered row's hash (or appending a
    newer one) legitimized any swapped artifact with full "verified"
    provenance; and simply deleting registry.jsonl downgraded every load
    to ok=None ("unknown provenance"), which the loader accepts - so the
    ML-011 tamper gate degraded to a log line for anyone with the same
    write access the artifact itself needs.

    That mattered beyond this file: the corpus's decisive provenance
    argument is membership in the hash-chained audit trail, and the shared
    adjective was one step from carrying that guarantee here, where it did
    not hold. Now it does: each row links to its predecessor, verify_chain
    walks the links, and a tampered or truncated ledger is detectable
    rather than authoritative.
    """

    def __init__(self, directory: str = "outputs/models"):
        self.dir = Path(directory)
        self.ledger = self.dir / "registry.jsonl"
        try:
            self.dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            log.error("registry directory unavailable — lineage records "
                      "will be dropped (models still function)")

    # ------------------------------------------------------------------
    def _tail_link(self) -> tuple[int, str]:
        """(seq, hash) of the last COMPLETE row, or (0, GENESIS).

        Read fresh on every append rather than cached: the CLI retrain and
        the runner's auto-retrain both write this ledger from separate
        processes, and a cached tail would fork the chain exactly the way
        the audit trail's own side-car note documents (a duplicate seq that
        broke verification from that record on).
        """
        seq, prev = 0, GENESIS
        try:
            with open(self.ledger, encoding="utf-8") as f:
                for line in f:
                    if not line.endswith("\n"):
                        break               # torn final row: ignore it
                    try:
                        rec = json.loads(line)
                    except ValueError:
                        continue
                    h = rec.get("h")
                    if not h:
                        continue            # pre-chain row: no link to adopt
                    seq = int(rec.get("seq", seq) or seq)
                    prev = str(h)
        except OSError:
            return (0, GENESIS)
        return (seq, prev)

    def _append(self, rec: dict):
        seq, prev = self._tail_link()
        rec = {"seq": seq + 1, "ts": round(time.time(), 3),
               "ts_h": time.strftime("%Y-%m-%d %H:%M:%S"), **rec,
               "prev": prev}
        rec["h"] = _record_hash(rec)
        # HEAL A TORN TAIL before appending (same class as the fills-ledger
        # fix): a kill mid-write leaves a fragment with no newline, and
        # appending straight onto it FUSES two records into one unparseable
        # line - which would take the surviving row down with the fragment
        # and break the chain walk at that point. Terminating the fragment
        # isolates it as one bad line the walk reports honestly.
        torn = False
        try:
            if self.ledger.exists() and self.ledger.stat().st_size > 0:
                with open(self.ledger, "rb") as rf:
                    rf.seek(-1, os.SEEK_END)
                    torn = rf.read(1) != b"\n"
        except OSError:
            torn = False
        try:
            with open(self.ledger, "a", encoding="utf-8") as f:
                if torn:
                    f.write("\n")
                f.write(json.dumps(rec, default=str) + "\n")
                f.flush()
                os.fsync(f.fileno())
        except OSError:
            log.error("registry ledger write failed: %s", rec.get("event"))

    def verify_chain(self) -> dict:
        """Walk the links. Returns {ok, rows, chained, reason}.

        Rows written before the chain existed carry no `h` and are counted
        but not linked - they are reported as `unchained` rather than
        silently treated as verified, because a pre-chain row cannot make
        a claim it was never able to make. A chained row whose recomputed
        hash differs (content edited) or whose prev does not match its
        predecessor (a row deleted, reordered, or inserted) fails.
        """
        rows = chained = unchained = 0
        prev = GENESIS
        try:
            with open(self.ledger, encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    rows += 1
                    try:
                        rec = json.loads(line)
                    except ValueError:
                        return {"ok": False, "rows": rows, "chained": chained,
                                "reason": f"row {rows}: unparseable"}
                    h = rec.get("h")
                    if not h:
                        # A pre-chain row (no h) is legitimate ONLY as a
                        # contiguous prefix, before chaining ever started:
                        # once any row carries h, every later row must too.
                        # An unchained row AFTER chained>0 is an appended
                        # forgery (runtime-injection-verified 2026-08-20: a
                        # well-formed no-h `registered` row pointing at a
                        # swapped artifact previously passed as ok=True and
                        # the ML-011 gate then trusted it). Fail closed.
                        if chained > 0:
                            return {"ok": False, "rows": rows,
                                    "chained": chained,
                                    "reason": f"row {rows}: unchained row "
                                              f"after the chain began - "
                                              f"appended without a hash link"}
                        unchained += 1
                        continue
                    if _record_hash(rec) != h:
                        return {"ok": False, "rows": rows, "chained": chained,
                                "reason": f"row {rows}: content edited "
                                          f"(hash mismatch)"}
                    if str(rec.get("prev", "")) != prev and chained > 0:
                        return {"ok": False, "rows": rows, "chained": chained,
                                "reason": f"row {rows}: broken link - a row "
                                          f"was deleted, reordered or "
                                          f"inserted"}
                    prev = str(h)
                    chained += 1
        except OSError:
            return {"ok": None, "rows": 0, "chained": 0,
                    "reason": "ledger unreadable"}
        return {"ok": True, "rows": rows, "chained": chained,
                "unchained": unchained, "reason": "chain intact"}

    def register(self, artifact_path: str, card: dict) -> str:
        """Hash the artifact, archive an immutable copy, append the card.
        Returns model_id ('' on failure — registration failure never
        blocks trading; it blocks silence about trading)."""
        artifact_path = _canonical(artifact_path)
        try:
            digest = sha256_file(artifact_path)
        except OSError:
            log.error("registry: cannot hash %s", artifact_path)
            return ""
        model_id = digest[:12]
        archived = self.dir / f"model_{model_id}.json"
        try:
            if not archived.exists():
                archived.write_bytes(Path(artifact_path).read_bytes())
        except OSError:
            log.warning("registry: archive copy failed for %s", model_id)
        self._append({"event": "registered", "model_id": model_id,
                      "sha256": digest,
                      "artifact": Path(artifact_path).as_posix(),
                      "card": card or {}})
        log.info("ML-060: model %s registered (%s, oof_brier=%s, rows=%s)",
                 model_id, (card or {}).get("kind"),
                 (card or {}).get("oof_brier"), (card or {}).get("rows"))
        return model_id

    def note(self, event: str, model_id: str, detail: dict | None = None):
        """deployed | retired | rejected | integrity_fail ..."""
        self._append({"event": event, "model_id": model_id,
                      "detail": detail or {}})

    # ------------------------------------------------------------------
    def verify(self, artifact_path: str, expected_sha256: str | None = None) -> dict:
        """Integrity check before a live load. If expected hash is not
        supplied, checks the artifact against the last 'registered'
        ledger entry for that path. Unregistered artifacts verify as
        ok=None (unknown provenance — loudly logged, not blocked, so a
        hand-trained model still loads; it just has no pedigree)."""
        artifact_path = _canonical(artifact_path)
        try:
            actual = sha256_file(artifact_path)
        except OSError:
            return {"ok": False, "reason": "artifact unreadable"}
        expected = expected_sha256
        if expected is None:
            # A pedigree is only as good as the ledger it comes from: if the
            # chain is broken, the "expected" hash is an unauthenticated
            # string an attacker (or a bad merge) could have written, so
            # trusting it would launder the tamper it is meant to catch.
            chain = self.verify_chain()
            if chain.get("ok") is False:
                log.critical("ML-011: registry ledger chain BROKEN (%s) - "
                             "refusing to treat its pedigree as evidence",
                             chain.get("reason"))
                return {"ok": False, "reason": "ledger chain broken",
                        "chain": chain, "model_id": actual[:12],
                        "sha256": actual}
            expected = self._last_registered_hash(str(artifact_path))
        if expected is None:
            log.warning("ML-060: %s has no registry pedigree — loading "
                        "with unknown provenance", artifact_path)
            return {"ok": None, "model_id": actual[:12], "sha256": actual}
        ok = actual == expected
        if not ok:
            self.note("integrity_fail", actual[:12],
                      {"expected": expected, "actual": actual,
                       "artifact": str(artifact_path)})
            log.critical("ML-011: artifact %s FAILED integrity check — "
                         "expected %s got %s", artifact_path,
                         expected[:12], actual[:12])
        return {"ok": ok, "model_id": actual[:12], "sha256": actual}

    def _last_registered_hash(self, artifact_path: str):
        # separator-normalized comparison: Windows str(Path()) yields
        # backslashes while the ledger stores posix paths - a raw string
        # match silently reported "no pedigree" for every registered model
        want = Path(artifact_path).as_posix()
        try:
            with open(self.ledger, encoding="utf-8") as f:
                last = None
                for line in f:
                    try:
                        rec = json.loads(line)
                    except ValueError:
                        continue
                    if rec.get("event") == "registered" and \
                            Path(rec.get("artifact", "")).as_posix() == want:
                        last = rec.get("sha256")
                return last
        except OSError:
            return None

    def history(self, limit: int = 20) -> list:
        try:
            with open(self.ledger, encoding="utf-8") as f:
                lines = f.readlines()[-limit:]
            return [json.loads(x) for x in lines if x.strip()]
        except (OSError, ValueError):
            return []


_REGISTRY = None


def get_registry() -> ModelRegistry:
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = ModelRegistry()
    return _REGISTRY


def configure_registry(directory) -> ModelRegistry:
    """Point the process-wide singleton at `directory`. QA harnesses
    (smoke, assurance, overfit, replay, pytest) MUST call this before
    constructing engines: replayed bots' lifecycle records were growing
    the production outputs/models/registry.jsonl ledger."""
    global _REGISTRY
    _REGISTRY = ModelRegistry(str(directory))
    return _REGISTRY
