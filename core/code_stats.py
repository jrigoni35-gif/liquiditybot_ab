"""
core/code_stats.py — process-global cumulative tally of reason-code emissions.

The registered reason codes (core/codes.py) flowed only as per-decision string
tags and audit lines; nothing counted how OFTEN each fired, so the FREQUENCY of
every reject / veto / fault / clamp (PT-*, SZ-*, RP-*, FW-*, OM-*, VN-*, ML-*,
…) was invisible — the operator could see the current disposition, never the
trend. This is the missing central ledger: tag() bumps a counter here on every
code emission, giving a cumulative {code: count} that runner surfaces in
status.json and gc_pusher exports to Grafana, so "how often are entries dying on
negative EV / budget exhaustion / a firewall fault" is finally answerable.

Telemetry-grade, not accounting-grade: a tiny lock guards the dict increment
(negligible next to per-cycle work) and the tally resets at process start like
every other counter, so dashboards read the per-restart increase/rate.
"""
import threading
from collections import Counter

_counts: "Counter[str]" = Counter()
_lock = threading.Lock()


def bump(code_value: str) -> None:
    """Increment the tally for one code. NEVER raises: telemetry must never
    wedge the decision path that emits the code."""
    try:
        with _lock:
            _counts[code_value] += 1
    except Exception:  # nosec B110 - telemetry must NEVER raise into the caller
        pass           # (a Counter bump can't realistically fail; stay safe)


def snapshot() -> dict:
    """Full {code: count} map (copy)."""
    with _lock:
        return dict(_counts)


def by_prefix() -> dict:
    """{prefix: total} aggregate, e.g. {'SZ': 412, 'PT': 88, 'FW': 3}."""
    agg: "Counter[str]" = Counter()
    with _lock:
        for k, v in _counts.items():
            agg[k.split("-", 1)[0]] += v
    return dict(agg)


def top(n: int = 20) -> dict:
    """The n most-frequent codes, highest first."""
    with _lock:
        return dict(sorted(_counts.items(), key=lambda kv: -kv[1])[:n])


def reset() -> None:
    """Test/QA hook: clear the tally."""
    with _lock:
        _counts.clear()
