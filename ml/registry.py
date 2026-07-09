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


class ModelRegistry:
    def __init__(self, directory: str = "outputs/models"):
        self.dir = Path(directory)
        self.ledger = self.dir / "registry.jsonl"
        try:
            self.dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            log.error("registry directory unavailable — lineage records "
                      "will be dropped (models still function)")

    # ------------------------------------------------------------------
    def _append(self, rec: dict):
        rec = {"ts": round(time.time(), 3),
               "ts_h": time.strftime("%Y-%m-%d %H:%M:%S"), **rec}
        try:
            with open(self.ledger, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec, default=str) + "\n")
        except OSError:
            log.error("registry ledger write failed: %s", rec.get("event"))

    def register(self, artifact_path: str, card: dict) -> str:
        """Hash the artifact, archive an immutable copy, append the card.
        Returns model_id ('' on failure — registration failure never
        blocks trading; it blocks silence about trading)."""
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
        try:
            actual = sha256_file(artifact_path)
        except OSError:
            return {"ok": False, "reason": "artifact unreadable"}
        expected = expected_sha256
        if expected is None:
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
