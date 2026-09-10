"""
scripts/reason_chain_report.py — the bot's REASONING as a Markov chain over
registered reason codes (SAFE class, report-only).

WHAT THIS IS. Invariant 6 requires a registered reason code on every
disposition, and `core/codes.py` is the registry. That makes the bot's
reasoning a DISCRETE STATE SPACE that is already fully instrumented and
hash-chained: 201 registered codes, and the audit trail records which fired,
in order, with `seq`. Every other learning instrument here reads OUTCOMES —
did the trade win, did the order fill, what regime were we in. This one reads
WHY: given the engine just emitted this reason, which reason comes next?

WHY IT IS WORTH A CHAIN RATHER THAN A HISTOGRAM. A histogram of reason codes
says where the bot spends its reasoning. It cannot say which reasons LEAD to
which — whether a veto is terminal or a way-station, whether the engine loops
on one reason, or which paths precede the dispositions you care about. Those
are transition questions, and a first-order chain is the smallest model that
answers them. The feature corpus is 64 continuous columns of which the overfit
battery reports the large majority near-zero importance; the reason space is
small, discrete, complete, and already audited.

**THE MARKOV ASSUMPTION IS TESTED, NOT ASSUMED.** A transition matrix can
always be estimated; that it MEANS anything requires P(next | current) to
differ from P(next). This report computes that comparison per code (a
chi-square against the unconditional successor distribution) and prints an
INDEPENDENT verdict. If the chain carries no information, the report says so
in as many words rather than printing a confident matrix — the failure mode
this repo keeps re-buying is a confident instrument that is wrong with nothing
flagging it.

WHAT IT CANNOT SEE, up front:
  * `system.dry_run` has been true for this whole corpus. These are the
    reasons a PAPER bot gave. They describe the decision pipeline honestly,
    but no claim here is about Kraken.
  * A reason code is a PROJECTION of the engine's state, not the state. Two
    different situations that emit the same code are the same state to this
    chain. First-order means the chain also forgets everything before the
    previous code. Both are stated so a reader deflates accordingly.
  * The audit records no decision/candidate id, so a "path" is reconstructed
    per ASSET in `seq` order. Interleaving between assets is removed by that
    grouping; interleaving between subsystems for the SAME asset is not.
  * Codes fire at very different rates (exploration dominates). Transition
    probabilities out of a rare code rest on few observations; every one is
    reported with its n and a Wilson interval.

CLASSIFICATION — SAFE AS SHIPPED. Report-only: reads outputs/audit.jsonl and
core/codes.py, writes only under outputs/. It places no order, changes no
size, moves no stop, books no fee and touches no fill. Wiring any number here
into decisioning is COHORT-RESETTING under the era-9 moratorium.

USAGE
    python scripts/reason_chain_report.py
    python scripts/reason_chain_report.py --json
    python scripts/reason_chain_report.py --prefix SZ      # one code family
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import os
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

log = logging.getLogger("liquiditybot.scripts.reason_chain")

# Below this many observed exits, a row's successor distribution is not a
# reading. Reported as UNDER-OBSERVED rather than dropped: a code that fires
# rarely is itself a fact, and silently omitting it would misrepresent the
# state space as smaller than it is.
MIN_EXITS_FOR_RATES = 30

GROUPLESS = "(no-asset)"


def _wilson(k: int, n: int, z: float = 1.96) -> tuple:
    if n <= 0:
        return (0.0, 0.0)
    p = k / n
    d = 1.0 + z * z / n
    c = p + z * z / (2 * n)
    m = z * math.sqrt(max(p * (1 - p) / n + z * z / (4 * n * n), 0.0))
    return (max(0.0, (c - m) / d), min(1.0, (c + m) / d))


def registered_codes() -> set:
    """Every code the registry declares. core/codes.py is the ONLY authority
    on which codes exist (CLAUDE.md invariant 6), so an unregistered code in
    the audit is a finding, not a parsing quirk."""
    try:
        from core import codes as _codes
    except ImportError:
        return set()
    out = set()
    for holder in (getattr(_codes, "Code", None), _codes):
        for k, v in vars(holder).items() if holder else ():
            if isinstance(v, str) and "-" in v and k.isupper():
                head = v.split("-")[0]
                if head.isalpha() and head.isupper():
                    out.add(v)
    return out


def load_transitions(audit_path: Path, prefix: str | None = None
                     ) -> dict[str, Any]:
    """Per-asset code sequences in `seq` order -> first-order transitions."""
    seqs: dict[str, list] = defaultdict(list)
    seen = Counter()
    unregistered = Counter()
    reg = registered_codes()
    rows = 0

    try:
        fh = open(audit_path, "r", encoding="utf-8", errors="replace")
    except OSError as exc:
        return {"error": f"audit unreadable: {exc}"}

    with fh:
        for line in fh:
            if '"code"' not in line:
                continue
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            code = rec.get("code")
            if not isinstance(code, str) or "-" not in code:
                continue
            if prefix and not code.startswith(prefix):
                continue
            rows += 1
            seen[code] += 1
            if reg and code not in reg:
                unregistered[code] += 1
            d = rec.get("data") or {}
            asset = (d.get("asset") if isinstance(d, dict) else None) or GROUPLESS
            s = rec.get("seq")
            seqs[str(asset)].append((s if isinstance(s, int) else 0, code))

    trans: dict = defaultdict(Counter)
    self_loops = Counter()
    exits = Counter()
    for asset, pairs in seqs.items():
        pairs.sort(key=lambda t: t[0])
        for (_, a), (_, b) in zip(pairs, pairs[1:]):
            trans[a][b] += 1
            exits[a] += 1
            if a == b:
                self_loops[a] += 1

    return {
        "rows": rows,
        "codes_seen": seen,
        "unregistered": unregistered,
        "transitions": trans,
        "exits": exits,
        "self_loops": self_loops,
        "groups": len(seqs),
        "audit_path": str(audit_path),
        "audit_mtime_utc": (
            time.strftime("%Y-%m-%dT%H:%M:%SZ",
                          time.gmtime(audit_path.stat().st_mtime))
            if audit_path.exists() else None),
    }


def markov_information_test(trans: dict, exits: Counter) -> dict[str, Any]:
    """Does knowing the CURRENT code tell you anything about the next one?

    Null: successors are drawn from the pooled (unconditional) successor
    distribution regardless of the current code. Per code with enough exits,
    a chi-square of observed successors against that pooled expectation.
    A chain whose rows all match the pooled distribution is a histogram
    wearing a matrix's clothes, and this is what says so.
    """
    pooled = Counter()
    for a, succ in trans.items():
        pooled.update(succ)
    total = sum(pooled.values())
    if total == 0:
        return {"applicable": False, "reason": "no transitions"}

    informative, tested = [], 0
    for a, succ in trans.items():
        n = exits.get(a, 0)
        if n < MIN_EXITS_FOR_RATES:
            continue
        tested += 1
        stat, dof = 0.0, 0
        for b, p_tot in pooled.items():
            exp = n * (p_tot / total)
            if exp < 5.0:          # chi-square validity floor
                continue
            obs = succ.get(b, 0)
            stat += (obs - exp) ** 2 / exp
            dof += 1
        dof = max(1, dof - 1)
        # chi-square tail, Wilson-Hilferty (no scipy dependency)
        x = stat / dof
        z = ((x ** (1.0 / 3.0) - (1 - 2.0 / (9 * dof)))
             / math.sqrt(2.0 / (9 * dof)))
        p = 0.5 * math.erfc(z / math.sqrt(2.0))
        if p < 0.05:
            informative.append((a, n, round(stat, 1), dof, p))
    informative.sort(key=lambda t: -t[2])
    return {
        "applicable": True,
        "codes_tested": tested,
        "codes_informative": len(informative),
        "top": [{"code": a, "n": n, "chi2": s, "dof": d, "p": p}
                for a, n, s, d, p in informative[:12]],
        "verdict": (
            "the current code CARRIES information about the next"
            if informative else
            "NO code's successors differ from the pooled distribution - the "
            "chain is a histogram, and the transition matrix below should not "
            "be read as structure"),
        "note": ("chi-square vs the POOLED successor distribution, per code "
                 f"with >= {MIN_EXITS_FOR_RATES} exits; cells with expected "
                 "< 5 are skipped for validity. Wilson-Hilferty tail."),
    }


def steady_state(trans: dict, exits: Counter, iters: int = 500) -> dict:
    """Long-run share of reasoning time per code, by power iteration.

    Power iteration rather than an eigensolver: the matrix is sparse, large
    and not guaranteed irreducible, and an eigensolver would hand back a
    complex vector for a reducible chain with no warning.
    """
    states = sorted(set(list(trans.keys()) + [b for s in trans.values() for b in s]))
    if not states:
        return {}
    idx = {s: i for i, s in enumerate(states)}
    n = len(states)
    v = [1.0 / n] * n
    for _ in range(iters):
        nv = [0.0] * n
        for a, succ in trans.items():
            tot = exits.get(a, 0)
            if tot <= 0:
                continue
            share = v[idx[a]]
            for b, c in succ.items():
                nv[idx[b]] += share * (c / tot)
        s = sum(nv)
        if s <= 0:
            break
        nv = [x / s for x in nv]
        if max(abs(nv[i] - v[i]) for i in range(n)) < 1e-12:
            v = nv
            break
        v = nv
    return {states[i]: v[i] for i in range(n)}


def build_report(prefix: str | None = None,
                 audit_path: Path | None = None) -> dict[str, Any]:
    path = audit_path or (REPO_ROOT / "outputs" / "audit.jsonl")
    loaded = load_transitions(path, prefix)
    read_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    base: dict[str, Any] = {
        "report": "reason_chain",
        "classification": "SAFE - report-only; the reasons a DRY-RUN bot gave",
        "read_at_utc": read_at,
        "prefix_filter": prefix or "(all)",
        "caveat": ("A reason code is a PROJECTION of engine state, not the "
                   "state; first-order forgets everything before the previous "
                   "code; dry_run has been true for this whole corpus."),
    }
    if loaded.get("error"):
        base["status"] = loaded["error"]
        return base
    base.update({
        "audit_path": loaded["audit_path"],
        "audit_mtime_utc": loaded["audit_mtime_utc"],
        "coded_records": loaded["rows"],
        "distinct_codes": len(loaded["codes_seen"]),
        "registered_codes": len(registered_codes()),
        "groups": loaded["groups"],
    })
    if not loaded["rows"]:
        base["status"] = "no coded records"
        return base

    trans, exits = loaded["transitions"], loaded["exits"]
    ss = steady_state(trans, exits)
    rows = []
    for code, n in loaded["codes_seen"].most_common():
        ex = exits.get(code, 0)
        succ = trans.get(code, Counter())
        top = []
        for b, c in succ.most_common(4):
            lo, hi = _wilson(c, ex)
            top.append({"to": b, "n": c, "p": round(c / ex, 4) if ex else None,
                        "ci95": [round(lo, 4), round(hi, 4)]})
        loops = loaded["self_loops"].get(code, 0)
        rows.append({
            "code": code,
            "fired": n,
            "exits_observed": ex,
            "under_observed": ex < MIN_EXITS_FOR_RATES,
            "self_loop_p": round(loops / ex, 4) if ex else None,
            "terminal": ex == 0,
            "steady_state": round(ss.get(code, 0.0), 6),
            "top_successors": top,
        })
    base.update({
        "status": "ok",
        "markov_test": markov_information_test(trans, exits),
        "codes": rows,
        "unregistered_codes": dict(loaded["unregistered"]),
    })
    return base


def render(rep: dict[str, Any]) -> str:
    L: list = []
    a = L.append
    a("=" * 76)
    a("REASON-CODE MARKOV CHAIN - what the bot says, and what it says next")
    a("=" * 76)
    a(f"read_at : {rep['read_at_utc']}   audit mtime: {rep.get('audit_mtime_utc')}")
    a(f"filter  : {rep['prefix_filter']}")
    a("")
    a(f"!! {rep['caveat']}")
    a("")
    if rep.get("status") != "ok":
        a(f"NO CHAIN - {rep.get('status')}")
        return "\n".join(L)

    a(f"coded records {rep['coded_records']}   distinct codes fired "
      f"{rep['distinct_codes']} of {rep['registered_codes']} registered   "
      f"asset groups {rep['groups']}")
    if rep.get("unregistered_codes"):
        a(f"  !! UNREGISTERED codes in the audit: {rep['unregistered_codes']} "
          f"- core/codes.py is the only authority on which codes exist")
    a("")

    mt = rep["markov_test"]
    if mt.get("applicable"):
        a("DOES THE CURRENT REASON PREDICT THE NEXT ONE?")
        a(f"  {mt['codes_informative']} of {mt['codes_tested']} tested codes "
          f"have successors differing from the pooled distribution (p<0.05)")
        a(f"  -> {mt['verdict']}")
        for t in mt["top"][:6]:
            a(f"     {t['code']:<10} n={t['n']:<6} chi2={t['chi2']:<9} "
              f"dof={t['dof']:<4} p={t['p']:.3g}")
        a("")

    a("PER CODE  (fired / P(self-loop) / long-run share / most likely next)")
    for r in rep["codes"][:20]:
        flag = "  UNDER-OBSERVED" if r["under_observed"] else ""
        term = "  TERMINAL" if r["terminal"] else ""
        sl = "n/a" if r["self_loop_p"] is None else f"{r['self_loop_p']*100:5.1f}%"
        a(f"  {r['code']:<10} fired {r['fired']:>6}  self-loop {sl}  "
          f"long-run {r['steady_state']*100:5.1f}%{term}{flag}")
        for s in r["top_successors"][:3]:
            ci = s["ci95"]
            a(f"      -> {s['to']:<10} {s['p']*100:5.1f}%  "
              f"[{ci[0]*100:.1f}%, {ci[1]*100:.1f}%]  n={s['n']}")
    return "\n".join(L)


def main(argv: list | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Reason codes as a Markov chain (SAFE, report-only)")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--prefix", default=None,
                    help="restrict to one code family, e.g. SZ")
    ap.add_argument("--out", default=None, help="output STEM inside outputs/")
    args = ap.parse_args(argv)

    rep = build_report(prefix=args.prefix)
    print(json.dumps(rep, indent=2, default=str) if args.json else render(rep))

    try:
        out_dir = Path(os.environ.get("LIQUIDITYBOT_OUTPUTS",
                                      str(REPO_ROOT / "outputs"))).resolve()
        out_dir.mkdir(parents=True, exist_ok=True)
        stem = (Path(args.out).resolve() if args.out
                else out_dir / "reason_chain_report")
        if out_dir not in stem.parents:
            log.error("refusing --out outside %s: %s", out_dir, stem)
            return 2
        with open(f"{stem}.json", "w", encoding="utf-8") as fh:
            json.dump(rep, fh, indent=2, default=str)
        with open(f"{stem}.txt", "w", encoding="utf-8", newline="\n") as fh:
            fh.write(render(rep) + "\n")
    except OSError as exc:
        log.warning("reason chain report not persisted: %s", exc)
        return 1

    if rep.get("status") != "ok":
        log.error("no chain estimated: %s", rep.get("status"))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
