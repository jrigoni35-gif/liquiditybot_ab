"""data/recording.py — feed-recording retention + reconciliation sidecar.

The record/replay harness (data/replay.py) records live feed frames so the
production engine can be re-driven through the exact market it saw. Two things
were missing to make that a STANDING capability rather than a manual one:

  * retention — recordings piled up unbounded (one file per boot, no cap, no
    cleanup). SinkRotator caps a single session file and rolls to .partNN;
    prune_recordings keeps the newest N sessions and drops the too-old.
  * reconciliation ground truth — a recording carried no link to the live
    session's realized P&L, so replay output could not be checked against what
    the live bot actually did. The flat-start sidecar stamps start/end P&L so
    the replay-vs-live gate (scripts/replay_gate.py) can tie them out.

Everything here is capture/operational only — no trading behavior reads it, and
every path fails soft: losing a recording or a sidecar must never break the
running bot.
"""

import json
import logging
import threading
from pathlib import Path

log = logging.getLogger("liquiditybot.data.recording")

# operational (disk/retention) literals — not decision-path knobs
DEFAULT_MAX_FILE_MB = 128
DEFAULT_RETAIN_DAYS = 45
DEFAULT_RETAIN_FILES = 60


class SinkRotator:
    """Size-triggered file roller shared by all feed recorders in one boot.

    Part 0 is the un-suffixed base file (backward-compatible with existing
    single-file recordings); once it exceeds ``max_bytes`` the rotator advances
    to ``<session>.partNN.jsonl``. All recorders in a boot share ONE rotator so
    they write to the same active part and stay in one ordered stream.
    """

    def __init__(self, base_path, max_bytes: int):
        self._base = Path(base_path)
        self._max = int(max_bytes)
        self._part = 0
        self._lock = threading.Lock()   # feeds may be read off-thread someday
        self._base.parent.mkdir(parents=True, exist_ok=True)

    def _part_path(self, part: int) -> Path:
        if part <= 0:
            return self._base
        stem = self._base.name[: -len(".jsonl")] if \
            self._base.name.endswith(".jsonl") else self._base.stem
        return self._base.with_name(f"{stem}.part{part:03d}.jsonl")

    def current(self) -> Path:
        with self._lock:
            p = self._part_path(self._part)
            try:
                if self._max > 0 and p.exists() and \
                        p.stat().st_size >= self._max:
                    self._part += 1
                    p = self._part_path(self._part)
            except OSError:
                pass
            return p


def session_sink(rec_dir, now_ts: float) -> Path:
    """Return this boot's base recording path, ensuring the directory."""
    d = Path(rec_dir)
    d.mkdir(parents=True, exist_ok=True)
    return d / f"session_{int(now_ts)}.jsonl"


# --- session grouping: a rolled session is base + .partNN, ONE logical unit ---
def session_id(path) -> str:
    """The 'session_<ts>' id a recording file (base or .partNN) belongs to."""
    stem = Path(path).name.split(".part")[0]
    if stem.endswith(".jsonl"):
        stem = stem[: -len(".jsonl")]
    return stem


def session_part_files(path) -> list[Path]:
    """Every existing file for a session in STREAM order: base first, then
    .part01, .part02 ... Accepts the base path or any part path."""
    p = Path(path)
    sid = session_id(p)
    d = p.parent
    ordered: list[Path] = []
    base = d / f"{sid}.jsonl"
    if base.exists():
        ordered.append(base)

    def _part_num(p: Path) -> int:
        try:                                    # numeric, so part100 > part011
            return int(p.name.split(".part")[1].split(".")[0])
        except (IndexError, ValueError):
            return 0
    try:
        ordered.extend(sorted(d.glob(f"{sid}.part*.jsonl"), key=_part_num))
    except OSError:
        pass
    return ordered


def discover_sessions(rec_dir) -> list[Path]:
    """One base path per recorded session (excludes .partNN fragments), newest
    first by the session's most-recent part mtime. This is the unit every
    consumer (replay, reconcile, calibrate, prune) must treat as ONE recording;
    globbing session_*.jsonl directly would double-count rolled parts."""
    d = Path(rec_dir)
    if not d.exists():
        return []
    try:
        bases = [f for f in d.glob("session_*.jsonl") if ".part" not in f.name]
    except OSError:
        return []

    def _mtime(base: Path) -> float:
        try:
            return max((p.stat().st_mtime for p in session_part_files(base)),
                       default=0.0)
        except OSError:
            return 0.0
    bases.sort(key=_mtime, reverse=True)
    return bases


def sidecar_path(sink) -> Path:
    """The single ``.meta.json`` for a session, shared across its parts."""
    base = Path(sink)
    stem = base.name.split(".part")[0]
    if stem.endswith(".jsonl"):
        stem = stem[: -len(".jsonl")]
    return base.with_name(f"{stem}.meta.json")


def read_sidecar(sink) -> dict | None:
    p = sidecar_path(sink)
    try:
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        log.warning("sidecar read failed %s: %s", p, e)
    return None


def update_sidecar(sink, key: str, snapshot: dict) -> None:
    """Merge ``snapshot`` under ``key`` (e.g. 'start'/'end') into the sidecar."""
    meta = read_sidecar(sink) or {}
    meta[key] = snapshot
    p = sidecar_path(sink)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(meta, indent=2, default=str), encoding="utf-8")
    except OSError as e:
        log.warning("sidecar write failed %s: %s", p, e)


def pnl_snapshot(realized_pnl: float, equity: float, open_positions: int,
                 now_ts: float) -> dict:
    """One flat-start/-end P&L snapshot for the reconciliation gate."""
    return {"ts": round(float(now_ts), 3),
            "realized_pnl": round(float(realized_pnl), 6),
            "equity": round(float(equity), 6),
            "open_positions": int(open_positions)}


def prune_recordings(rec_dir, retain_days: float, retain_files: int,
                     now_ts: float) -> list[Path]:
    """Delete whole SESSIONS beyond retention; return the deleted base files.

    A session (base + all its .partNN parts + shared sidecar) is dropped if it
    is older than ``retain_days`` (when > 0) OR falls outside the newest
    ``retain_files`` sessions (when > 0). Rotation parts count as ONE session,
    never as separate recordings, so pruning can never orphan a surviving part
    or delete a shared sidecar out from under one. Orphaned sidecars (whole
    session already gone) are swept.
    """
    d = Path(rec_dir)
    if not d.exists():
        return []
    bases = discover_sessions(rec_dir)          # newest first, parts grouped
    cutoff = now_ts - float(retain_days) * 86400.0
    deleted: list[Path] = []
    for i, base in enumerate(bases):
        parts = session_part_files(base)
        try:
            mtime = max((p.stat().st_mtime for p in parts), default=0.0)
        except OSError:
            mtime = 0.0
        too_old = retain_days > 0 and mtime < cutoff
        beyond = retain_files > 0 and i >= retain_files   # newest-first index
        if too_old or beyond:
            for p in parts:
                _unlink(p)
            _unlink(sidecar_path(base))
            deleted.append(base)
    # sweep orphaned sidecars (whole session already gone)
    try:
        for meta in d.glob("session_*.meta.json"):
            base = meta.with_name(meta.name[: -len(".meta.json")] + ".jsonl")
            if not base.exists():
                _unlink(meta)
    except OSError:
        pass
    return deleted


def _unlink(p: Path) -> None:
    try:
        p.unlink(missing_ok=True)
    except OSError as e:
        log.warning("prune unlink failed %s: %s", p, e)
