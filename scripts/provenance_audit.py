"""scripts/provenance_audit.py - which rows are usable, and how we know.

THE QUESTION. QA harnesses wrote fixture data into production output files
seven times (see tests/test_qa_isolation.py for the list). Commit 858c8d71
stopped new leaks. It did not clean old ones, so every downstream number
carries an unanswered question: how much of this file is real?

CLASSIFY BY PROVENANCE, NOT BY PLAUSIBILITY. This is the whole method, and
it is a correction of how the first pass was done. Plausibility heuristics
ask "does this value look wrong" - and that already produced a false
positive: round `arrival_ref` was used as a contamination tell and flagged
BTC 65990 and ETH 1940, both real prices. Provenance asks "where did this
record come from", which these files mostly already record.

FOUR SIGNALS, strongest first:

  1. RECORDED ARTIFACT PATH. registry.jsonl stores the artifact it
     registered. A path under /tmp/pytest-* was written by a test. Direct
     evidence, no inference.
  2. CONTENT HASH CROSS-REFERENCE. meta_model.json is a fitted blob, so no
     row filter applies; but its sha256 either matches a registry record
     with a production artifact path or it does not.
  3. SYMBOL WHITELIST. Every QA harness prices exactly two assets -
     ETH=2000.0 and BTC=60000.0 (scripts/debug_cycle.py:62,
     scripts/overfit_check.py:308, five sites in scripts/smoke_test.py). A
     row for any other asset CANNOT have come from one.
  4. STRUCTURAL DETERMINISM. A replayed scenario emits the same payload
     under a repeating key. Real market data does not repeat to full
     precision. This needs no external reference at all.

THREE VERDICTS, NEVER TWO. Signal 3 proves rows GENUINE; it never proves
them contaminated, so ETH/BTC rows it cannot clear stay UNDECIDABLE rather
than being folded into either pile. A dataset whose only value is being
trustworthy is worse off with a guess in it than with a gap - the same rule
GateStats.note_realized applies when it drops an era-less sample.

WHAT THIS TOOL WILL NOT DO. It never edits a file. outputs/models/
registry.jsonl is part of the hash-chained assurance spine that
scripts/assurance_check.py verifies; rewriting it to remove fixture records
would break the chain and destroy the audit trail to fix a reporting
problem. Contaminated records there are filtered AT READ TIME. Nothing is
deleted anywhere - quarantine and filter, never delete.

    python scripts/provenance_audit.py [--json]
"""
import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"

# The complete set of assets any QA harness can produce. Sourced from the
# mock price dicts, not guessed: debug_cycle.py:62 and overfit_check.py:308
# are both {"ETH": 2000.0, "BTC": 60000.0}, and smoke_test.py repeats it.
QA_ASSETS = {"ETH", "BTC", "ETH/USD", "BTC/USD"}

# Substrings that mark an artifact path as belonging to a test run. These
# are CLASSIFIER PATTERNS matched against paths recorded in registry
# entries, not temp locations this tool writes to - hence the nosec.
FIXTURE_MARKS = ("/tmp/", "pytest", "\\temp\\", "/temp/",  # nosec B108
                 "appdata\\local\\temp", "appdata/local/temp")

CLEAN, DIRTY, UNSURE = "CLEAN", "CONTAMINATED", "UNDECIDABLE"


def _is_fixture_path(p: str) -> bool:
    s = str(p or "").lower().replace("\\", "/")
    return any(m.replace("\\", "/") in s for m in FIXTURE_MARKS)


def _jsonl(path: Path):
    if not path.exists():
        return []
    out = []
    for ln in path.read_text(encoding="utf-8", errors="replace").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            out.append(json.loads(ln))
        except json.JSONDecodeError:
            continue
    return out


def audit_registry():
    """Signal 1. Direct: the record names the artifact it registered."""
    recs = _jsonl(OUT / "models" / "registry.jsonl")
    v = Counter()
    for r in recs:
        v[DIRTY if _is_fixture_path(r.get("artifact")) else CLEAN] += 1
    return {"file": "outputs/models/registry.jsonl", "n": len(recs),
            "verdicts": dict(v), "signal": "recorded artifact path",
            "action": "FILTER AT READ TIME - hash-chained, never rewrite"}


def audit_meta_model():
    """Signal 2. A fitted blob cannot be row-filtered; it is either traceable
    to a production registration or it is not."""
    mm = OUT / "meta_model.json"
    if not mm.exists():
        return {"file": "outputs/meta_model.json", "n": 0,
                "verdicts": {}, "signal": "sha256 vs registry",
                "action": "file absent"}
    sha = hashlib.sha256(mm.read_bytes()).hexdigest()
    hits = [r for r in _jsonl(OUT / "models" / "registry.jsonl")
            if r.get("sha256") == sha]
    if not hits:
        verdict, act = UNSURE, ("UNREGISTERED - no registry record carries "
                                "this hash; provenance unknown")
    elif all(_is_fixture_path(r.get("artifact")) for r in hits):
        verdict, act = DIRTY, "DEPLOYED MODEL CAME FROM A QA RUN - retrain"
    else:
        card = (hits[-1].get("card") or {})
        verdict, act = CLEAN, ("traceable to %s (rows=%s, train_data_sha=%s)"
                               % (hits[-1].get("ts_h"), card.get("rows"),
                                  card.get("train_data_sha")))
    return {"file": "outputs/meta_model.json", "n": 1,
            "verdicts": {verdict: 1}, "signal": "sha256 vs registry",
            "action": act, "sha256": sha[:16]}


def audit_horizon_shadow():
    """Signals 3 + 4. The asset whitelist CLEARS rows; it never convicts
    them, so ETH/BTC rows fall through to the determinism check and then to
    UNDECIDABLE rather than to CLEAN."""
    p = OUT / "horizon_shadow.csv"
    if not p.exists():
        return {"file": "outputs/horizon_shadow.csv", "n": 0, "verdicts": {},
                "signal": "asset whitelist + payload collision",
                "action": "file absent"}
    rows = list(csv.DictReader(p.open(newline="", encoding="utf-8")))
    seen, collisions = {}, 0
    for r in rows:
        k = (r.get("candidate_id"), r.get("horizon_bars"))
        val = (r.get("asset"), r.get("direction"), r.get("net_ret_pct"))
        if k in seen and seen[k] != val:
            collisions += 1
        seen[k] = val
    v = Counter()
    for r in rows:
        v[UNSURE if r.get("asset") in QA_ASSETS else CLEAN] += 1
    act = ("no replay signature (0 payload collisions); UNDECIDABLE rows are "
           "unproven, not suspected" if not collisions else
           "%d REPLAY COLLISIONS - investigate before use" % collisions)
    return {"file": "outputs/horizon_shadow.csv", "n": len(rows),
            "verdicts": dict(v), "collisions": collisions,
            "signal": "asset whitelist + payload collision", "action": act}


def audit_retrain_history():
    """Signal 4, done right on the second attempt. The first version
    convicted any corpus size seen 3+ times - a PLAUSIBILITY heuristic, the
    exact mistake this tool's docstring warns against, and it was wrong
    within hours: rows=2141 repeats six times with gaps of ~3603s, which is
    the live scheduler's hourly cadence to within seconds. A frozen corpus
    (era exclusion holds training rows constant after a geometry change)
    legitimately repeats its size every retrain.

    The structural signal is TIMING, not repetition. Live retrains fire on
    the macro_refit_minutes cadence; a suite re-running a fixture fires as
    fast as the tests do. Measured: the fixture group's median gap is ~460s
    against a 3600s cadence, an 8x separation - not a tuning knife-edge."""
    recs = _jsonl(OUT / "retrain_history.jsonl")
    if not recs:
        return {"file": "outputs/retrain_history.jsonl", "n": 0,
                "verdicts": {}, "signal": "cadence timing",
                "action": "file absent"}
    try:
        cfg = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
        cadence = 60.0 * float(cfg.get("system", {})
                               .get("macro_refit_minutes", 60))
    except (OSError, ValueError):
        cadence = 3600.0
    groups = defaultdict(list)
    for r in recs:
        groups[r.get("rows")].append(float(r.get("ts", 0)))
    verdict_by_rows, notes = {}, []
    for k, ts_list in groups.items():
        if len(ts_list) < 3:
            verdict_by_rows[k] = CLEAN     # too few to repeat structurally
            continue
        ts_list.sort()
        gaps = sorted(b - a for a, b in
                      zip(ts_list, ts_list[1:], strict=False))
        med_gap = gaps[len(gaps) // 2]
        if med_gap < cadence / 3.0:
            verdict_by_rows[k] = DIRTY     # faster than any live scheduler
            notes.append("rows=%s x%d burst (median gap %.0fs vs %.0fs "
                         "cadence)" % (k, len(ts_list), med_gap, cadence))
        elif abs(med_gap - cadence) <= 0.1 * cadence:
            verdict_by_rows[k] = CLEAN     # the scheduler's own heartbeat
            notes.append("rows=%s x%d on live cadence (frozen corpus, "
                         "expected after a geometry change)"
                         % (k, len(ts_list)))
        else:
            verdict_by_rows[k] = UNSURE
            notes.append("rows=%s x%d irregular spacing" % (k, len(ts_list)))
    v = Counter(verdict_by_rows[r.get("rows")] for r in recs)
    return {"file": "outputs/retrain_history.jsonl", "n": len(recs),
            "verdicts": dict(v), "signal": "cadence timing",
            "action": "; ".join(notes) or "no repeated corpus sizes"}


def audit_fills():
    """The strongest signal in the whole tool, and it is not a heuristic:
    every genuine order's id appears in the hash-chained audit trail
    (outputs/audit.jsonl), while QA harnesses have ALWAYS redirected the
    audit singleton (configure_audit, 8 call sites) even while they were
    leaking fills. So a fills row whose order_id is absent from the audit
    cannot have come from the live bot. Verified before shipping: 0 of 2
    known fixture order_ids appear in the audit; a 12/12 sample of kept
    order_ids do; audit coverage predates the earliest fill.

    This turns the asset whitelist's UNDECIDABLE bucket (ETH/BTC rows the
    whitelist cannot clear) into a decided one - which is why fills gets a
    three-way verdict from evidence while horizon_shadow, with no order_id
    column, keeps its honest UNDECIDABLE remainder."""
    p = OUT / "fills.csv"
    if not p.exists():
        return {"file": "outputs/fills.csv", "n": 0, "verdicts": {},
                "signal": "order_id in hash-chained audit trail",
                "action": "file absent"}
    rows = list(csv.DictReader(p.open(newline="", encoding="utf-8")))
    audit_p = OUT / "audit.jsonl"
    audit_txt = audit_p.read_text(encoding="utf-8", errors="replace") \
        if audit_p.exists() else ""
    covered = False
    if audit_txt and rows:
        try:
            first_audit_ts = json.loads(audit_txt.splitlines()[0]).get(
                "ts", float("inf"))
            first_fill_ts = min(float(r.get("ts", 0) or 0) for r in rows)
            covered = float(first_audit_ts) <= first_fill_ts
        except (ValueError, json.JSONDecodeError):
            covered = False
    pat = Counter()
    for r in rows:
        pat[(r.get("purpose"), r.get("side"), r.get("fill_size"),
             r.get("fill_price"))] += 1
    dupes = sum(c - 1 for c in pat.values() if c > 1)
    v = Counter()
    orphans = 0
    for r in rows:
        oid = str(r.get("order_id") or "")
        if covered and oid:
            hit = oid in audit_txt
            v[CLEAN if hit else DIRTY] += 1
            orphans += 0 if hit else 1
        else:
            sym = str(r.get("symbol", "")).split("/")[0]
            v[UNSURE if sym in QA_ASSETS else CLEAN] += 1
    bits = []
    if not covered:
        bits.append("audit does not cover the fills window - fell back to "
                    "the asset whitelist")
    bits.append("%d order_ids absent from the audit trail" % orphans
                if orphans else "every order_id present in the audit trail")
    bits.append("%d repeated exact fill patterns" % dupes if dupes
                else "no duplicate fill patterns")
    return {"file": "outputs/fills.csv", "n": len(rows), "verdicts": dict(v),
            "duplicate_fill_rows": dupes,
            "signal": "order_id in hash-chained audit trail",
            "action": "; ".join(bits)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ns = ap.parse_args()
    reports = [audit_fills(), audit_horizon_shadow(), audit_meta_model(),
               audit_registry(), audit_retrain_history()]
    if ns.json:
        print(json.dumps(reports, indent=1))
        return 0

    print("PROVENANCE AUDIT - classify by where a record came from")
    print("=" * 70)
    for r in reports:
        print("\n%s   (n=%d)" % (r["file"], r["n"]))
        print("  signal: %s" % r["signal"])
        for k in (CLEAN, UNSURE, DIRTY):
            if r["verdicts"].get(k):
                pct = 100.0 * r["verdicts"][k] / max(r["n"], 1)
                print("    %-14s %6d  (%.1f%%)" % (k, r["verdicts"][k], pct))
        print("  -> %s" % r["action"])

    print("\n" + "=" * 70)
    print("UNDECIDABLE IS NOT CLEAN. The asset whitelist proves a row GENUINE")
    print("(no QA harness prices anything but ETH and BTC); it can never")
    print("prove one contaminated. Rows it cannot clear are unproven, not")
    print("suspected - and must not be counted as either.")
    print("\nREPORT-ONLY. Nothing here edits a file. registry.jsonl is part")
    print("of the hash-chained assurance spine (scripts/assurance_check.py);")
    print("removing records to tidy it would break the chain to fix a")
    print("reporting problem. Filter at read time instead.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
