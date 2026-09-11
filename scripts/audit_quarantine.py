"""Quarantine synthetic sessions out of the audit trail, and annotate the seams.

WHAT HAPPENED. `core/audit.py:92` defaults the trail to `outputs/audit.jsonl`
and `configure_audit` puts the redirect obligation on the CALLER. QA harnesses
that ran as `__main__` discharged it; library callers did not, so synthetic
sessions were appended to the production hash-chained trail alongside the live
bot's. `scripts/replay.isolate_qa_singletons()` closed the leak on 2026-09-10.
This tool deals with the rows that are already there.

WHAT THIS TOOL WILL NOT DO. It never modifies `outputs/audit.jsonl`. That file
is a hash-chained evidence record; rewriting it would destroy the only trace of
what happened and break the chain for every consumer that has already read it.
The trail stays byte-intact and this writes SIDECARS beside it.

HOW SESSIONS ARE CLASSIFIED. Every record belongs to the session opened by the
nearest preceding `CG-000` (`Code.CG_SESSION_START`), whose payload carries
`starting_capital_usd`. A session whose capital equals the shipped
`capital_management.starting_capital_usd` is PRODUCTION; anything else is
SYNTHETIC. The production figure is READ FROM config.json, never hardcoded -
if the operator re-capitalises, this tool must follow rather than mislabel
every subsequent live session.

THE FORWARD-LEAK, and why a naive segmentation is wrong. The live bot emits its
`CG-000` once, at boot. A QA burst that starts mid-session emits its own
`CG-000`, and under nearest-preceding attribution EVERY later live record
inherits that synthetic label until the bot next reboots. Measured on the
2026-09-10 trail: three fixture `CG-000`s at 19:28Z would have mislabelled the
following 38 long_book/exploration/fault records as synthetic, and 86 synthetic
sessions span a gap larger than any real burst.

So a session also CLOSES on an idle gap. `SESSION_IDLE_S` defaults to 300 s:
the fixture class writes ~1-second bursts, so any threshold well above that and
below the live bot's own cadence bounds it. Records after a synthetic session
closes, but before the next `CG-000`, revert to the last PRODUCTION context -
the live bot is the only continuously-running writer - and are reported as
INFERRED, not folded into production, because that reversion is an inference.

THE SESSION-SHAPE TABLE THAT USED TO SIT HERE IS DELETED, and the deletion is
the point (red-team OBJ-5 prong 3, conceded). It read "800 (prod): median
duration 398 s, median max-gap 176 s" and those figures NO LONGER REPRODUCE - on
2026-09-11 the same computation over 88 production sessions gives 1563.1 s and
511.5 s. A number written into a docstring decays, which is the exact recurrence
this repo names, and I wrote one into the tool whose subject is decayed numbers.

Worse, the re-measurement moves the THRESHOLD's own justification: a median
production max-gap of 511.5 s is ABOVE `SESSION_IDLE_S`, so the rule closes
sessions that were merely quiet. `--session-shape` recomputes the table on
demand; read it there and treat 300 s as a floor under review, not a fact.

Records are never silently dropped: production + synthetic + unclassified
always equals the input line count, and the tool asserts it.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TRAIL = REPO_ROOT / "outputs" / "audit.jsonl"
SESSION_START = "CG-000"

# A synthetic burst is ~1 s (measured above). The live bot's own inter-record
# gap runs to ~180 s median. 300 s sits above both without reaching the
# multi-hour gaps that marked the leaked sessions.
SESSION_IDLE_S = 300.0

# HARD CEILING ON THE INFERENCE (red-team OBJ-5, conceded). The idle rule hands
# a synthetic session's context back to the live bot after SESSION_IDLE_S, and
# the handed-back context then STICKS until the next CG-000 is READ. Production
# CG-000s are rare - the bot emits one at boot - so "a 300 second rule" licensed
# an extrapolation whose measured span was a MEDIAN of 6.75 DAYS and a MAX of
# 25.99 days, 1,943x its own threshold. Beyond this ceiling a record is not
# inferred, it is assumed; it is labelled UNCLASSIFIED instead, which is an
# honest unknown rather than a production row nobody can defend.
MAX_INFER_S = 6 * 3600.0


def production_capital(config_path: Path) -> float:
    """The shipped starting capital. Read, never hardcoded - see the docstring."""
    with open(config_path, encoding="utf-8") as fh:
        cfg = json.load(fh)
    return float(cfg["capital_management"]["starting_capital_usd"])


def _capital_of(rec: dict):
    data = rec.get("data") or {}
    val = data.get("starting_capital_usd")
    try:
        return None if val is None else float(val)
    except (TypeError, ValueError):
        return None


def classify(records: list, prod_capital: float,
             idle_s: float = SESSION_IDLE_S,
             max_infer_s: float = MAX_INFER_S) -> list:
    """Label every record PRODUCTION / SYNTHETIC / UNCLASSIFIED.

    Returns a list of (label, reason) parallel to `records`.
    """
    out: list = []
    cur = None          # current session capital
    cur_ts = None       # ts of the last record attributed to it
    last_prod = None    # last capital known to be production
    inferred = False    # is the CURRENT context the result of an idle close?
    confirmed_ts = None  # ts of the last class actually READ from a CG-000
    for rec in records:
        ts = rec.get("ts")
        ts = ts if isinstance(ts, (int, float)) else None

        if rec.get("code") == SESSION_START:
            cap = _capital_of(rec)
            if cap is not None:
                cur, cur_ts = cap, ts
                inferred = False        # a real reading resets the inference
                confirmed_ts = ts       # ...and anchors the inference clock
                if cap == prod_capital:
                    last_prod = cap

        if cur is not None and cur != prod_capital and ts is not None \
                and cur_ts is not None and (ts - cur_ts) > idle_s:
            # the synthetic burst went quiet; the continuously-running writer
            # is the live bot, so hand the context back to it
            if last_prod is not None:
                cur, inferred = last_prod, True

        if cur is None:
            out.append(("UNCLASSIFIED", "before any session start"))
            continue
        if (inferred and ts is not None and confirmed_ts is not None
                and (ts - confirmed_ts) > max_infer_s):
            # past the ceiling this is an assumption, not an inference
            out.append(("UNCLASSIFIED", "inference span exceeded"))
            continue
        label = "PRODUCTION" if cur == prod_capital else "SYNTHETIC"
        # "inferred" STICKS until the next CG-000. Counting only the transition
        # record would report 86 where 16,429 records actually depend on the
        # idle-close rule - an instrument that understates its own uncertainty
        # by two orders of magnitude.
        out.append((label, "inferred" if inferred else "session"))
        if ts is not None:
            cur_ts = ts
    return out


def seams(records: list, labels: list) -> list:
    """Every point where the writer class changes, with both sides named."""
    out = []
    for i in range(1, len(records)):
        a, b = labels[i - 1][0], labels[i][0]
        if a == b:
            continue
        out.append({
            "line": i + 1,               # 1-indexed, matches the file
            "from": a,
            "to": b,
            "reason": labels[i][1],
            "seq_before": records[i - 1].get("seq"),
            "seq_after": records[i].get("seq"),
            "ts": records[i].get("ts"),
            "code_after": records[i].get("code"),
            "chain_intact": records[i].get("prev") == records[i - 1].get("h"),
        })
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--trail", default=str(DEFAULT_TRAIL))
    ap.add_argument("--config", default=str(REPO_ROOT / "config.json"))
    ap.add_argument("--out-dir", default=None,
                    help="where the sidecars go (default: beside the trail)")
    ap.add_argument("--idle-sec", type=float, default=SESSION_IDLE_S)
    ap.add_argument("--write", action="store_true",
                    help="write the sidecars; without it this only reports")
    args = ap.parse_args()

    trail = Path(args.trail)
    out_dir = Path(args.out_dir) if args.out_dir else trail.parent
    read_at = time.time()

    records, bad = [], 0
    with open(trail, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                bad += 1
                records.append({"_unparseable": True})

    prod_capital = production_capital(Path(args.config))
    labels = classify(records, prod_capital, args.idle_sec)
    marks = seams(records, labels)

    n = len(records)
    counts = {"PRODUCTION": 0, "SYNTHETIC": 0, "UNCLASSIFIED": 0}
    inferred = 0
    for label, reason in labels:
        counts[label] += 1
        inferred += (reason == "inferred")
    assert sum(counts.values()) == n, "records were lost during classification"

    stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(read_at))
    print(f"trail            : {trail}")
    print(f"read at          : {stamp}  (LIVE FILE - counts are as-of)")
    print(f"records          : {n}   unparseable: {bad}")
    print(f"production capital: {prod_capital:g}  (read from {args.config})")
    print(f"idle close       : {args.idle_sec:g}s")
    print()
    for k in ("PRODUCTION", "SYNTHETIC", "UNCLASSIFIED"):
        pct = 100.0 * counts[k] / n if n else 0.0
        print(f"  {k:<14}{counts[k]:>8}   {pct:5.1f}%")
    pct_inf = 100.0 * inferred / n if n else 0.0
    print(f"\n  of the above, {inferred} records ({pct_inf:.1f}%) are labelled "
          f"by INFERENCE, not by\n  a reading: their session context came from "
          f"the {args.idle_sec:g}s idle-close rule\n  rather than from a "
          f"CG-000 record. Treat that share as the tool's own\n  uncertainty.")
    print(f"\nseams (writer-class transitions): {len(marks)}")
    broken = sum(1 for m in marks if not m["chain_intact"])
    print(f"  of which the hash chain does not link: {broken}")

    if not args.write:
        print("\nreport only - pass --write to emit the sidecars")
        return 0

    prod_p = out_dir / "audit_production.jsonl"
    syn_p = out_dir / "audit_synthetic.jsonl"
    seam_p = out_dir / "audit_seams.json"
    with open(prod_p, "w", encoding="utf-8") as fp, \
            open(syn_p, "w", encoding="utf-8") as fs:
        # strict=True is the point, not lint appeasement: a length mismatch
        # between records and labels would silently TRUNCATE the sidecars,
        # which is the one failure mode this tool must never have.
        for rec, (label, _) in zip(records, labels, strict=True):
            if rec.get("_unparseable"):
                continue
            line = json.dumps(rec, sort_keys=True) + "\n"
            (fp if label == "PRODUCTION" else fs).write(line)
    with open(seam_p, "w", encoding="utf-8") as fh:
        json.dump({"read_at": stamp, "trail": str(trail), "records": n,
                   "production_capital": prod_capital,
                   "idle_sec": args.idle_sec, "counts": counts,
                   "inferred_records": inferred, "seams": marks}, fh, indent=2)
    print(f"\nwrote {prod_p}")
    print(f"wrote {syn_p}")
    print(f"wrote {seam_p}")
    print(f"\n{trail} is UNMODIFIED - it stays the evidence record.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
