"""
scripts/reason_chain_report.py — the bot's REASONING as a Markov chain over
registered reason codes (SAFE class, report-only).

WHAT THIS IS. Invariant 6 requires a registered reason code on every
disposition, and `core/codes.py` is the registry. That makes the bot's
reasoning a DISCRETE STATE SPACE that is already fully instrumented and
hash-chained: the audit trail records which code fired, in order, with `seq`.

(The registry SIZE is deliberately NOT written here. This docstring said "201
registered codes" while `registered_codes()` returned 206 twelve lines later -
red-team OBJ-9, conceded. A count in a docstring decays the day someone adds a
code, which is the exact recurrence CLAUDE.md names; the report emits
`len(registered_codes())` at runtime, so read it there.)

Every other learning instrument here reads OUTCOMES —
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

**THE MARKOV ASSUMPTION IS TESTED BY DESTROYING TIME ORDER.** A transition
matrix can
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
import random
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


def load_transitions(audit_path: Path, prefix: str | None = None,
                     scope: str = "production") -> dict[str, Any]:
    """Per-asset code sequences in `seq` order -> first-order transitions.

    SCOPE, added 2026-09-11 after red-team OBJ-6 (BLOCKING, conceded). This read
    the WHOLE of outputs/audit.jsonl while the same branch ships
    scripts/audit_quarantine.py, whose classifier shows 34.5% of that trail is
    QA-fixture output from replay/overfit harnesses. The effect is not cosmetic:
    SZ-047 publishes at 25.36% of pooled records against 4.04% production-only -
    a 6.3x overstatement on the code the report ranks near the top. Building the
    contamination classifier and then not using it here was the defect.

      scope="production" (DEFAULT) - records classified PRODUCTION only
      scope="all"                  - the pooled trail, as before
      scope="synthetic"            - the fixture rows, for comparison

    The three-way split is ALWAYS reported in `corpus_split`, whichever scope is
    read, so a reader can see what was excluded rather than trusting that the
    question was asked. Note the split's own caveat: audit_quarantine labels
    18.8% of records by an idle-close INFERENCE rather than a CG-000 reading,
    and that share is reported as `inferred` rather than folded silently into
    production.
    """
    seqs: dict[str, list] = defaultdict(list)
    seen = Counter()
    unregistered = Counter()
    reg = registered_codes()
    rows = 0

    try:
        fh = open(audit_path, "r", encoding="utf-8", errors="replace")
    except OSError as exc:
        return {"error": f"audit unreadable: {exc}"}

    # Classify the WHOLE file first: the classifier is sequential (a session's
    # class is set by the nearest preceding CG-000 and closed by an idle gap),
    # so it cannot be applied to a filtered stream.
    split = Counter()
    labels: list = []
    all_recs: list = []
    try:
        from scripts.audit_quarantine import (classify,
                                              production_capital)
        with open(audit_path, "r", encoding="utf-8", errors="replace") as cfh:
            for line in cfh:
                line = line.strip()
                if not line:
                    continue
                try:
                    all_recs.append(json.loads(line))
                except ValueError:
                    all_recs.append({"_unparseable": True})
        cap = production_capital(REPO_ROOT / "config.json")
        labels = [lab for lab, _why in classify(all_recs, cap)]
        reasons = [why for _lab, why in classify(all_recs, cap)]
        for lab, why in zip(labels, reasons, strict=False):
            split[lab if why != "inferred" else f"{lab}_inferred"] += 1
    except Exception:                       # noqa: BLE001 - classifier optional
        log.warning("corpus classification unavailable - reading the POOLED "
                    "trail; figures may include QA fixture output")
        labels = []

    keep = set()
    scope_effective = scope
    if labels:
        want = {"production": {"PRODUCTION"}, "synthetic": {"SYNTHETIC"},
                "all": {"PRODUCTION", "SYNTHETIC", "UNCLASSIFIED"}}.get(
                    scope, {"PRODUCTION"})
        keep = {i for i, lab in enumerate(labels) if lab in want}
        if not keep and scope != "all":
            # A corpus the classifier cannot place - no CG-000 anywhere, e.g. a
            # freshly rotated trail - would otherwise yield an EMPTY report that
            # reads exactly like a quiet system. "No transitions" and "no
            # readable corpus" are the same observation until separated, which
            # is the rule this file already pins elsewhere. Fall back to the
            # pooled read and SAY SO rather than reporting nothing.
            log.warning("no %s records after classification (%d records "
                        "classified) - falling back to the POOLED trail; "
                        "figures may include QA fixture output",
                        scope, len(labels))
            keep = set(range(len(labels)))
            scope_effective = "all (fallback: nothing classified as %s)" % scope

    with fh:
        for line_no, line in enumerate(fh):
            if labels and line_no not in keep:
                continue
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
    for _asset, pairs in seqs.items():
        pairs.sort(key=lambda t: t[0])
        for (_, a), (_, b) in zip(pairs, pairs[1:], strict=False):
            trans[a][b] += 1
            exits[a] += 1
            if a == b:
                self_loops[a] += 1

    return {
        "rows": rows,
        "scope": scope_effective,
        "corpus_split": dict(split),
        "codes_seen": seen,
        "unregistered": unregistered,
        "transitions": trans,
        "exits": exits,
        # ORDERED per-group code sequences, kept rather than discarded so the
        # order-destroying control below can actually be run. Without these the
        # information test has no way to ask "would this verdict survive if I
        # shuffled time?", which is the only question that separates temporal
        # structure from group composition.
        "sequences": {g: [c for _, c in sorted(pairs, key=lambda x: x[0])]
                      for g, pairs in seqs.items()},
        "self_loops": self_loops,
        "groups": len(seqs),
        "audit_path": str(audit_path),
        "audit_mtime_utc": (
            time.strftime("%Y-%m-%dT%H:%M:%SZ",
                          time.gmtime(audit_path.stat().st_mtime))
            if audit_path.exists() else None),
    }


def _chi2_total(trans: dict, exits: Counter) -> tuple:
    """Summed chi-square of every testable row against the POOLED successor
    distribution, plus the number of rows tested. Extracted so the identical
    statistic can be computed on permuted data."""
    pooled: Counter = Counter()
    for _a, succ in trans.items():
        pooled.update(succ)
    total = sum(pooled.values())
    if total == 0:
        return (0.0, 0)
    stat_sum, tested = 0.0, 0
    for a, succ in trans.items():
        n = exits.get(a, 0)
        if n < MIN_EXITS_FOR_RATES:
            continue
        tested += 1
        for b, p_tot in pooled.items():
            exp = n * (p_tot / total)
            if exp < 5.0:
                continue
            stat_sum += (succ.get(b, 0) - exp) ** 2 / exp
    return (stat_sum, tested)


def _transitions_from(sequences: dict) -> tuple:
    trans: dict = defaultdict(Counter)
    exits: Counter = Counter()
    for seq in sequences.values():
        for a, b in zip(seq, seq[1:], strict=False):
            trans[a][b] += 1
            exits[a] += 1
    return (dict(trans), exits)


def permutation_order_test(sequences: dict, n_perm: int = 200,
                           seed: int = 20260911) -> dict[str, Any]:
    """Does the chain's structure survive DESTROYING time order?

    THE DEFECT THIS REPLACES (found by adversarial review 2026-09-11, and it
    had shipped). The analytic test below compares each code's successors to a
    GLOBALLY pooled distribution while transitions are built PER GROUP. A code
    concentrated in one asset's stream therefore produces a large chi-square
    from GROUP COMPOSITION alone, with no temporal structure whatsoever.
    Measured on the live trail: within-group permutation - which destroys order
    and preserves every marginal - returned 32/32 codes informative and the
    IDENTICAL affirmative verdict. A safeguard advertised as "the Markov
    assumption is TESTED, not assumed" could not tell the real trail from
    shuffled noise.

    The control is now the test. Permute within each group, recompute the same
    summed statistic, and report where the observed value falls in that null.
    An observed statistic inside the permutation null means the matrix below is
    group composition wearing a matrix's clothes - the permuted data would have
    produced it too.

    Deterministic seed: a report that prints a different verdict on each run is
    not a measurement.
    """
    # nosec B311 - a permutation NULL for a statistical test, not a
    # security primitive. The seed is fixed deliberately: a report that
    # prints a different verdict on each run is not a measurement.
    rng = random.Random(seed)  # nosec B311
    obs_trans, obs_exits = _transitions_from(sequences)
    observed, tested = _chi2_total(obs_trans, obs_exits)
    if tested == 0:
        return {"applicable": False, "reason": "no row had enough exits"}

    null = []
    for _ in range(n_perm):
        shuffled = {}
        for g, seq in sequences.items():
            s = list(seq)
            rng.shuffle(s)
            shuffled[g] = s
        pt, pe = _transitions_from(shuffled)
        null.append(_chi2_total(pt, pe)[0])

    n_ge = sum(1 for v in null if v >= observed)
    p_emp = (n_ge + 1) / (n_perm + 1)          # add-one, never reports p=0
    null_sorted = sorted(null)
    q95 = null_sorted[int(0.95 * (len(null_sorted) - 1))] if null_sorted else 0.0
    carries = p_emp < 0.05
    return {
        "applicable": True,
        "observed_chi2": round(observed, 1),
        "null_median": round(null_sorted[len(null_sorted) // 2], 1),
        "null_q95": round(q95, 1),
        "n_perm": n_perm,
        "p_empirical": round(p_emp, 4),
        "rows_tested": tested,
        "carries_order_information": carries,
        "verdict": (
            "ORDER CARRIES INFORMATION: the observed structure exceeds what "
            "within-group shuffling produces"
            if carries else
            "NO ORDER INFORMATION: shuffling time reproduces this structure, so "
            "the matrix below is GROUP COMPOSITION, not a Markov chain. Do not "
            "read the transition table as temporal structure."),
        "note": ("within-group permutation null, order destroyed and every "
                 "marginal preserved; add-one empirical p so p=0 is never "
                 "claimed"),
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
    for _a, succ in trans.items():
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


def steady_state(trans: dict, exits: Counter, iters: int = 0, *,
                 tol: float = 1e-12, max_iters: int = 200_000) -> dict:
    """Long-run share of reasoning time per code, iterated TO A CRITERION.

    THE DEFECT THIS REPLACES (red-team panel OBJ-2, 2026-09-11, conceded).
    This ran a FIXED 500 power iterations and published the 500th iterate as
    "long-run" share. Measured on the live trail, the transition matrix has
    |lambda_2| = 0.996195, so reaching 1e-12 needs 7,249 iterations - the loop
    stopped roughly 6,750 short and the convergence break could never fire. The
    published per-code figures were a non-converged snapshot presented as a
    limit.

    It now iterates until the L1 change falls under `tol`, and returns {} -
    an EXPLICIT UNKNOWN - if `max_iters` is exhausted. Empty is never silently
    replaced by a uniform prior, which would read as "the bot spends equal time
    in every reason", a claim about the world made from a failure of the solver.
    That contract is copied deliberately from `regime_chain_report._steady_state`,
    which had it right first.

    `iters` is kept as a DEPRECATED positional for callers that passed it; a
    non-zero value is treated as a floor on max_iters, never as a stopping rule.

    The old docstring justified avoiding an eigensolver on the grounds that one
    "would hand back a complex vector for a reducible chain with no warning".
    That was false, and falsified by this repo's own code: the sibling above
    takes np.real, checks |lambda - 1| > 1e-6, and returns None on a defective
    matrix. The real reason to iterate here is that this matrix is sparse and
    grows with the code registry; it is not that the alternative is unsafe.
    """
    states = sorted(set(list(trans.keys()) + [b for s in trans.values() for b in s]))
    if not states:
        return {}
    idx = {s: i for i, s in enumerate(states)}
    n = len(states)
    v = [1.0 / n] * n
    cap = max(int(max_iters), int(iters) if iters else 0)
    converged = False
    for _step in range(cap):
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
        if max(abs(nv[i] - v[i]) for i in range(n)) < tol:
            v = nv
            converged = True
            break
        v = nv
    if not converged:
        # EXPLICIT UNKNOWN. Publishing the last iterate here is what shipped
        # before and it is what the panel caught: a non-converged snapshot read
        # as a limit. An empty result is rendered as "not available"; it is
        # never backfilled with a uniform prior.
        log.warning("steady_state did not converge in %d iterations (tol %g) - "
                    "returning EMPTY rather than publishing a non-limit",
                    cap, tol)
        return {}
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
        # The ORDER control. markov_test alone cannot separate temporal
        # structure from group composition - measured 2026-09-11, it
        # returned the identical affirmative on a within-group permuted
        # corpus. This one destroys order and is the verdict that counts.
        "order_test": permutation_order_test(loaded.get("sequences") or {}),
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
