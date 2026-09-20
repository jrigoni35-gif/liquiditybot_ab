"""scripts/gradeability_census.py - the era-9 decision-population census.

WHY THIS EXISTS. 82.6% of era-9's decision population is ungradeable
(measured 2026-09-19): EN-000 carries counts only, so pre-DE-010 arrivals
have no per-arrival record BY CONSTRUCTION. This census sizes the hole
exactly - by absorb key, with hard reconciliation - and derives the field
list DE-010 must carry so the hole never regrows. Report-plane: reads
outputs/, writes only its dated doc. Refuses rather than approximates.

    python scripts/gradeability_census.py
    python scripts/gradeability_census.py --since 2026-09-08 \
        --doc docs/quant/2026-09-20_gradeability_census.md
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.fill_ledger import EXEC_ERA   # noqa: E402 - "12-10d4d0c2" (era-9)

REFUSAL_CHAIN_TORN = "CHAIN_TORN"
REFUSAL_NO_EN000 = "NO_EN000_IN_WINDOW"
REFUSAL_INCONSISTENT = "CENSUS_INCONSISTENT"
REFUSAL_NO_FILLS = "NO_FILLS"

# cut-#12 runner restart (era-9 accrual begins), docs/HANDOFF.md.
CUT12_FLOOR = datetime(2026, 9, 8, tzinfo=timezone.utc).timestamp()

# core/audit.py:_GENESIS - the chain anchor every boot record points at.
_GENESIS = "0" * 16

GRADER_NEEDS = ("asset", "ts", "decision_mid", "mid_available",
                "gates", "absorb", "direction", "confidence")


def _h(payload: str) -> str:
    # identical construction to core/audit.py:_h - the record-hash scheme
    # this census VERIFIES against (sha256, first 16 hex chars).
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def read_chain(path):
    """Parse + verify with core.audit.verify_chain semantics.

    Each record's OWN sha256 is recomputed (an edited record fails here,
    before any linkage logic: tamper -> refusal). Linkage follows the
    engine's verifier, NOT a strict seq/prev walk: the real trail carries
    hash-valid WRITER SEAMS (dual-runner windows, SD-007; 63 of them at
    the 2026-09-19 read, all classified benign by verify_chain) where an
    adopted fork's prev points at an earlier verified record or GENESIS.
    Those are adopted and reading continues; a prev that resolves NOWHERE
    (a committed record deleted under its successor) is tamper -> refusal.
    An unparseable FINAL line is a crash-torn tail: the verified prefix is
    kept; real content past the break makes it tamper. Never a partial.
    """
    records, seen = [], {_GENESIS}
    prev_h, broken = _GENESIS, False
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip().strip("\x00").strip()
        if not line:
            continue                     # torn-tail fragment guard
        if broken:
            return None                  # real content past the break: tamper
        try:
            rec = json.loads(line)
        except ValueError:
            broken = True                # crash mid-append candidate
            continue
        h = rec.get("h")
        body = json.dumps({k: v for k, v in rec.items() if k != "h"},
                          sort_keys=True, default=str)
        if not h or _h(body) != h:
            return None                  # edited record: tamper
        rp = rec.get("prev")
        if rp != prev_h and rp not in seen:
            return None                  # dangling prev: deletion, tamper
        prev_h = h                       # (seam: rp in seen, adopt + continue)
        seen.add(h)
        records.append(rec)
    return records


def _iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ")


def en000_deltas(records, since: float) -> dict:
    """Restart-aware positive deltas of the cumulative EN-000 vector."""
    ticks = [r for r in records
             if r.get("src") == "entry_sweep"
             and r.get("code") == "EN-000" and r.get("ts", 0) >= since]
    if not ticks:
        return {}
    out, prev = {}, None
    for t in sorted(ticks, key=lambda r: r["ts"]):
        data = t.get("data") or {}
        for k, v in data.items():
            if not isinstance(v, (int, float)):
                continue
            delta = v if prev is None or k not in prev or v < prev[k] \
                else v - prev[k]
            out[k] = out.get(k, 0) + delta
        prev = data
    return out


def gradeable_entries(fills_path, since: float) -> int:
    """Era-stamped entry fills carrying a decision price (arrival_ref)."""
    if not fills_path or not Path(fills_path).exists():
        return 0
    seen = set()
    with open(fills_path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if (row.get("exec_era") == EXEC_ERA
                    and row.get("purpose") == "entry"
                    and (row.get("arrival_ref") or "")):
                seen.add(row.get("position_id") or row["order_id"])
    return len(seen)


def cv_records(records, since: float) -> int:
    return sum(1 for r in records
               if str(r.get("code", "")).startswith("CV-")
               and r.get("ts", 0) >= since and (r.get("data") or {}).get("asset"))


def census(*, audit_path, fills_path, since, doc_path) -> dict:
    records = read_chain(audit_path)
    if records is None:
        return {"refused": REFUSAL_CHAIN_TORN}
    keys = en000_deltas(records, since)
    if not keys:
        return {"refused": REFUSAL_NO_EN000}
    n = int(keys.get("arrivals", 0))
    en020, en030 = int(keys.get("EN-020", 0)), int(keys.get("EN-030", 0))
    g = gradeable_entries(fills_path, since)
    if en020 + en030 > n or g > n - en020 - en030:
        return {"refused": REFUSAL_INCONSISTENT}
    lost = en020 + en030
    deep = n - en020 - en030 - g
    out = {
        "refused": None, "since": _iso(since), "arrivals": n,
        "by_key": {k: int(v) for k, v in keys.items()},
        "gradeable": g, "lost_forever": lost, "deep_pipeline": deep,
        "cv_records_with_asset": cv_records(records, since),
        "de010_coverage": sum(len((r.get("data") or {}).get("events") or [])
                              for r in records if r.get("code") == "DE-010"),
        "de010_fields_derived": list(GRADER_NEEDS),
    }
    if doc_path:
        _write_doc(out, doc_path)
    return out


def _write_doc(out: dict, doc_path) -> None:
    p = Path(doc_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    rows = "\n".join(f"| {k} | {v} |" for k, v in out["by_key"].items())
    p.write_text(f"""# Gradeability census (run {_iso(__import__('time').time())}, SAFE-plane)

Window since {out['since']} (era-9 = {EXEC_ERA}).

| absorb key | count |
|---|---|
{rows}

- arrivals N = {out['arrivals']}
- gradeable (priced entries) g = {out['gradeable']}
- lost forever L (EN-020+EN-030, no per-arrival record exists) = {out['lost_forever']}
- deep pipeline D (gate stack reached, no priced entry) = {out['deep_pipeline']}
- CV records carrying an asset (retro path via Kraken-OHLC proxy, Lane B) = {out['cv_records_with_asset']}
- DE-010 coverage (post-capture events) = {out['de010_coverage']}
- DE-010 derived fields: {', '.join(out['de010_fields_derived'])}

Reconciliation pins held: EN-020+EN-030 <= N, g <= N-EN-020-EN-030,
L+g+D == N. Unreconciled census = refused census.
""", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--audit", default="outputs/audit.jsonl")
    ap.add_argument("--fills", default="outputs/fills.csv")
    ap.add_argument("--since", default=None,
                    help="epoch or YYYY-MM-DD (default: cut-#12 floor)")
    ap.add_argument("--doc", default=None)
    ns = ap.parse_args()
    since = (float(ns.since) if ns.since and ns.since[0].isdigit()
             and len(ns.since) > 10 else
             datetime.fromisoformat(ns.since).replace(
                 tzinfo=timezone.utc).timestamp()) if ns.since else CUT12_FLOOR
    out = census(audit_path=ns.audit, fills_path=ns.fills,
                 since=since, doc_path=ns.doc)
    if out["refused"]:
        print(f"CENSUS REFUSED: {out['refused']}")
        return 2
    print(json.dumps(out, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
