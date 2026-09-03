"""scripts/instrument_contract.py - the measurement plane gets a contract.

WHY THIS EXISTS, and why it is not a style linter.

CLAUDE.md states the asymmetry plainly: the decision path is the most-governed
code here, and the measurement plane that OBSERVES it is the least-governed,
because SAFE class exists so measurement can move fast. SAFE class is a
PERMISSION, not a contract - and on 2026-08-23 a single session found, in the
measurement plane alone: an audit trail that erased its own tamper evidence at
construction, a deploy gate running 1 of the 8 commands its own law names, a
freshly-shipped guard with 1-in-16 recall whose self-test could not fail,
outputs/ with a creator and a consumer and no reaper, a test that raced the
live bot, a markout that conflated captured spread with alpha, and a fee
constant that moves a pre-registered verdict across a band. Nothing in entry,
sizing, geometry or risk.

WILLPOWER IS NOT THE FIX. Every one of those was in code someone believed was
fine, and TWO of them were written that same day BY THE PERSON HUNTING THE
PATTERN, hours apart. Sustained attention was the control group and it failed.
So the clauses below are mechanical, and every one of them is EARNED from a
specific measured failure rather than invented.

WHAT IS CHECKED HERE (mechanically decidable, exact):

  C1 ROOTEDNESS      every gate CLAUDE.md's Definition of done NAMES must be
                     executed by the automated admission path. Earned by: the
                     DoD naming eight commands while battery_passes ran one,
                     proven by deleting the spoofy taker suppression - which
                     assurance_check FAILED and the battery passed 130/130.
                     The DoD list is PARSED from CLAUDE.md, never copied here,
                     so the law stays the single source.

  C2 SELF-TEST POWER an instrument shipping --self-test must exercise a
                     NEGATIVE arm and report a rate, not a bare PASS. Earned
                     twice in one day: vault_guard's original self-test
                     planted the literal strings its own regexes were written
                     against and certified a ~6% detector as healthy; and a
                     synthetic harness "validated" an algebraic identity on a
                     driftless walk, proving only that a market with no drift
                     has no drift. A null arm alone shows an instrument does
                     not cry wolf. It never shows it can detect anything -
                     "0 findings" and "the scan is broken" are the same
                     observation until separated.

  C3 ONE POPULATION  a stats record must not pair a count with an effective
                     count computed over a DIFFERENT population. Earned by
                     ml/history.py reporting ess_kish=6248.5 beside rows=5191
                     - a ratio of 1.204, impossible for a Kish ESS (bounded by
                     n via Cauchy-Schwarz) - because rows is corrected
                     post-era-exclusion and ess_kish is not. It cost a wrong
                     funnel and two wrong diagnoses before it was understood.

WHAT IS DELIBERATELY *NOT* CHECKED, and saying so is part of the contract.
Five further clauses were earned today and need judgment, so they belong in
review and are NOT pretended-at here: repair-before-classify ordering; a
retire step per artifact class; no live mutable state as a fixture; composite
numbers decomposed or labelled; a verdict-bearing constant naming its
provenance and as-of. A check that pretends to cover what it cannot is the
exact failure this file exists to stop.

BLOCKING SAFETY. C1 and C2 are pure functions of the incoming code, so they
can never refuse the commit that repairs them - safe to veto. C3 reads
status.json, which is LIVE MUTABLE STATE, so it runs ONLY when a --status path
is supplied and is otherwise skipped-and-said-so. Reading live state in a
blocking gate is itself one of the defects on the list above.

    python scripts/instrument_contract.py [--status PATH] [--json] [--strict]
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess  # nosec B404 - fixed argv, repo-local scripts only
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Commands the DoD names that this contract does NOT expect the automated
# battery to run, with the reason. pyright needs node/npx and is a developer
# gate; keeping it here (rather than silently omitting it) means the exemption
# is reviewable instead of invisible.
C1_EXEMPT = {"pyright": "needs node/npx; developer + PC-side gate"}


def _read(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


# --- C1: rootedness ----------------------------------------------------
def dod_commands() -> list[str]:
    """Parse the gate names out of CLAUDE.md's Definition of done.

    PARSED, never copied. A list duplicated into this file would drift from
    the law it claims to enforce - the same reason ledger_continuity imports
    the cohort boundary rather than restating it.
    """
    txt = _read(ROOT / "CLAUDE.md")
    m = re.search(r"##\s*Definition of done(.+?)(?=\n##\s|\Z)", txt, re.S)
    if not m:
        return []
    block = m.group(1)
    # A COMMAND STARTS WITH A VERB. The first cut extracted every
    # scripts/*.py it saw inside the block and reported three false
    # positives: quant_trials.py (an ARGUMENT to ruff, not a command) and
    # gate_truth_report/cohort_eval (backticked paths in PROSE about
    # degraded gates). A detector with a 4:1 false-positive rate gets
    # ignored, and being ignored is the same failure one level up - so only
    # the FIRST token of a chunk decides, and only if it is an invocation.
    VERBS = ("python", "python3", "ruff", "pyright", "bandit")
    names: list[str] = []
    for chunk in re.findall(r"`([^`]+)`", block):
        c = chunk.strip()
        toks = c.split()
        if not toks or toks[0] not in VERBS:
            continue                      # prose path or separator, not a run
        if toks[0].startswith("python"):
            mod = re.search(r"-m\s+([A-Za-z0-9_.]+)", c)
            first_script = re.search(r"scripts/([A-Za-z0-9_]+)\.py", c)
            if mod:
                names.append("compileall" if "compileall" in mod.group(1)
                             else mod.group(1).split(".")[-1])
            elif first_script:
                names.append(first_script.group(1))   # FIRST only
        else:
            names.append(toks[0])
    out: list[str] = []
    for n in names:
        if n not in out:
            out.append(n)
    return out


def battery_gates() -> set[str]:
    """What the automated admission path actually executes."""
    txt = _read(ROOT / "scripts" / "auto_update.py")
    got: set[str] = set()
    for block in re.findall(r"_(?:HARD|ADVISORY)_GATES\s*=\s*\((.+?)\n\)",
                            txt, re.S):
        # COMMENTED-OUT IS NOT EXECUTED. Without this strip the parser counted
        # a disabled gate as running: commenting out the smoke entry left the
        # text "scripts/smoke_test.py" inside the tuple and C1 still reported
        # "every named gate is executed". A detector that cannot see its own
        # target being switched off is theatre - caught by mutation, which is
        # the only reason it is not still in here.
        block = "\n".join(ln for ln in block.splitlines()
                          if not ln.lstrip().startswith("#"))
        for s in re.findall(r"scripts/([A-Za-z0-9_]+)\.py", block):
            got.add(s)
        for tok in ("ruff", "bandit", "compileall", "pyright"):
            if f'"{tok}"' in block or f"'{tok}'" in block:
                got.add(tok)
    if re.search(r'"-m",\s*"pytest"', txt) or "'-m', 'pytest'" in txt:
        got.add("pytest")
    # assurance_check runs under two labels; normalise both to the script name
    if "assurance-code" in txt or "assurance-corpus" in txt:
        got.add("assurance_check")
    return got


def check_rootedness() -> dict:
    named = dod_commands()
    run = battery_gates()
    missing = [n for n in named if n not in run and n not in C1_EXEMPT]
    exempt = [n for n in named if n in C1_EXEMPT]
    return {"clause": "C1 rootedness", "named": named, "executed": sorted(run),
            "exempt": exempt, "missing": missing, "ok": not missing}


# --- C2: self-test power ----------------------------------------------
_NEG_ARM = re.compile(
    r"false[_ ]positive|control|must not fire|wrongly[_ ]flagged"
    r"|not[_ ]flagged|negative arm", re.I)
_RATE = re.compile(r"\d+\s*/\s*\d+|\d+(?:\.\d+)?\s*%")

# A self-test that COULD NOT RUN is not a weak self-test. Collapsing the two
# is the same defect assurance_check names a few clauses away ("TOOL
# UNAVAILABLE IS NOT A FINDING about the incoming code ... how the replay gate
# bricked deploys 2026-07-21/22"), and it fired for real on 2026-09-03:
# scripts/rpe_factor.py carries a POWER ARM in its own source (it prints
# "POWER ARM ... recovered ... 1/1"), but imports pandas at MODULE scope, so on
# any box without the optional analysis stack it exits 1 before printing a
# line -- and was reported as "null-arm-only", a confident, specific and WRONG
# diagnosis of an instrument that is actually fine. "0 findings" and "the scan
# is broken" are the SAME OBSERVATION until separated (CLAUDE.md mindset #3).
#
# Only a THIRD-PARTY absence is excusable. A missing repo module is a real
# breakage and must still fail: that asymmetry is the whole point, and it is
# the same rule tests/test_import_integrity.py already applies.
_ABSENT_DEP = re.compile(
    r"ModuleNotFoundError: No module named ['\"]([\w.]+)['\"]")
_REPO_PKGS = ("core", "data", "execution", "ml", "risk", "regime",
              "strategies", "sentiment", "api", "scripts", "tests")


def instruments_with_self_test() -> list[Path]:
    out = []
    me = Path(__file__).name
    for p in sorted((ROOT / "scripts").glob("*.py")):
        if p.name == me:
            continue          # a detector must not detect itself by substring
        # REGISTERED, not merely mentioned: the first cut matched this file's
        # own docstring and ran it with an invalid flag (exit 2).
        if re.search(r"add_argument\(\s*[\"']--self-test", _read(p)):
            out.append(p)
    return out


def check_self_tests(timeout: int = 180) -> dict:
    rows = []
    for p in instruments_with_self_test():
        rec = {"file": p.name, "ran": False, "exit": None,
               "has_negative_arm": False, "reports_rate": False, "ok": False,
               "could_not_run": None}
        try:
            r = subprocess.run(  # nosec B603 - fixed argv, repo-local script
                [sys.executable, str(p), "--self-test"], cwd=str(ROOT),
                capture_output=True, text=True, timeout=timeout,
                encoding="utf-8", errors="replace")
        except Exception as e:  # noqa: BLE001
            rec["error"] = str(e)[:120]
            rows.append(rec)
            continue
        blob = (r.stdout or "") + (r.stderr or "")
        rec["ran"] = True
        rec["exit"] = r.returncode
        _m = _ABSENT_DEP.search(blob)
        if r.returncode != 0 and _m and _m.group(1).split(".")[0] \
                not in _REPO_PKGS:
            # UNVERIFIED, not weak - reported separately so the degraded form
            # can never be read as (or silence) a real finding.
            rec["could_not_run"] = _m.group(1)
            rows.append(rec)
            continue
        rec["has_negative_arm"] = bool(_NEG_ARM.search(blob))
        rec["reports_rate"] = bool(_RATE.search(blob))
        # A self-test that passes but exercises only a NULL arm proves the
        # instrument does not cry wolf, never that it can detect anything.
        rec["ok"] = (r.returncode == 0 and rec["has_negative_arm"]
                     and rec["reports_rate"])
        rows.append(rec)
    verified = [r for r in rows if not r.get("could_not_run")]
    return {"clause": "C2 self-test power", "instruments": rows,
            "unverified": [r["file"] for r in rows if r.get("could_not_run")],
            "ok": all(r["ok"] for r in verified) if verified else True}


# --- C3: one population ------------------------------------------------
# (count_key, effective_key): effective can never exceed the count when both
# describe the same rows. Kish ESS is bounded by n via Cauchy-Schwarz.
_PAIRS = (("rows", "ess_kish"), ("n", "effective_n"), ("n", "n_eff"),
          ("nominal_n", "effective_n"))


def _scan_populations(obj, path="") -> list[dict]:
    bad = []
    if isinstance(obj, dict):
        for ck, ek in _PAIRS:
            if ck in obj and ek in obj:
                try:
                    c, e = float(obj[ck]), float(obj[ek])
                except (TypeError, ValueError):
                    continue
                if c > 0 and e > c:
                    bad.append({"path": path or "<root>", "count_key": ck,
                                "count": c, "effective_key": ek,
                                "effective": e, "ratio": round(e / c, 4)})
        for k, v in obj.items():
            bad += _scan_populations(v, f"{path}.{k}" if path else k)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            bad += _scan_populations(v, f"{path}[{i}]")
    return bad


def check_one_population(status_path: Path | None) -> dict:
    if status_path is None:
        return {"clause": "C3 one population", "ok": True, "skipped": True,
                "why": ("no --status given. status.json is LIVE MUTABLE "
                        "state; reading it in a blocking gate is itself one "
                        "of the defects this contract exists to stop.")}
    try:
        data = json.loads(status_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        return {"clause": "C3 one population", "ok": False, "skipped": False,
                "why": f"unreadable status: {str(e)[:100]}",
                "violations": []}
    bad = _scan_populations(data)
    return {"clause": "C3 one population", "ok": not bad, "skipped": False,
            "read_at": status_path.stat().st_mtime, "violations": bad}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--status", default=None,
                    help="path to a status.json for C3 (live state: never "
                         "supplied by the blocking gate)")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--strict", action="store_true",
                    help="exit nonzero on any violation (default: C1/C2 only)")
    ns = ap.parse_args()

    c1 = check_rootedness()
    c2 = check_self_tests()
    c3 = check_one_population(Path(ns.status) if ns.status else None)
    res = {"c1": c1, "c2": c2, "c3": c3}
    if ns.json:
        print(json.dumps(res, indent=1, default=str))
    else:
        print("INSTRUMENT CONTRACT - the measurement plane, checked")
        print("=" * 70)
        print("C1 ROOTEDNESS  (DoD names it -> the battery must run it)")
        print("   named by CLAUDE.md : %s" % ", ".join(c1["named"]))
        print("   battery executes   : %s" % ", ".join(c1["executed"]))
        for e in c1["exempt"]:
            print("   exempt             : %s (%s)" % (e, C1_EXEMPT[e]))
        if c1["missing"]:
            print("   *** NAMED BUT NEVER RUN: %s" % ", ".join(c1["missing"]))
            print("   *** the law mandates a gate nothing executes.")
        else:
            print("   OK - every named gate is executed")
        print("")
        print("C2 SELF-TEST POWER  (a null arm alone proves nothing)")
        for r in c2["instruments"]:
            flag = "OK " if r["ok"] else "FAIL"
            print("   [%s] %-24s exit=%s negative_arm=%s rate=%s"
                  % (flag, r["file"], r["exit"], r["has_negative_arm"],
                     r["reports_rate"]))
            if not r["ok"] and r.get("error"):
                print("        error: %s" % r["error"])
        if not c2["instruments"]:
            print("   (no instrument ships --self-test)")
        print("")
        print("C3 ONE POPULATION  (count and effective-count, same rows)")
        if c3.get("skipped"):
            print("   SKIPPED: %s" % c3["why"])
        elif c3["ok"]:
            print("   OK - no impossible count/effective pair")
        else:
            for v in c3.get("violations", []):
                print("   *** %s: %s=%g but %s=%g (ratio %.3f > 1)"
                      % (v["path"], v["count_key"], v["count"],
                         v["effective_key"], v["effective"], v["ratio"]))
            if c3.get("why"):
                print("   *** %s" % c3["why"])
        print("")
        print("NOT CHECKED HERE (needs judgment, belongs in review):")
        print("  repair-before-classify ordering; a retire step per artifact")
        print("  class; no live mutable state as a fixture; composites")
        print("  decomposed or labelled; verdict-bearing constants naming")
        print("  provenance + as-of. A check that pretends to cover what it")
        print("  cannot is the failure this file exists to stop.")

    failed = (not c1["ok"]) or (not c2["ok"])
    if ns.strict and not c3.get("skipped") and not c3["ok"]:
        failed = True
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
