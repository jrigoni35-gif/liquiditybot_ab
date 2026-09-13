"""scripts/agent_brief.py - the canonical briefing block for delegated work.

WHY THIS EXISTS. Four multi-agent workflows were authored in one session
(2026-09-12), each with a hand-typed CONTEXT block restating the bot's state.
Three problems followed, all of them accuracy problems:

  1. THE NUMBERS WERE STALE THE MOMENT THEY WERE TYPED. One brief carried
     "~18,020 rows / mean_uniqueness 0.0868"; the live loader read 18,052 /
     0.0867 within the hour. The runner appends every cycle, so ANY corpus
     figure written into prose is wrong by the time an agent reads it.
  2. THE BLOCKS DRIFTED FROM EACH OTHER. Same facts, four hand-copies, no
     single source, no way to tell which was current.
  3. A HAND-COPIED FENCE UNDER-PUBLISHED THE LAW. docs/HANDOFF.md listed SIX
     cohort-resetting axes where CLAUDE.md lists TEN, omitting the universe,
     the hedger, the probe ticket and the heat cap - and asserted "the TERMS
     below are unchanged" while saying it. A session reading the copy could
     have restarted era-9 believing it was SAFE. Corrected 2026-09-12
     (c0807f7f); this tool exists so the copy cannot drift again.

THE DESIGN RULE, which is this repo's own: A NUMBER WRITTEN INTO A FILE DECAYS
INTO A FALSE CLAIM. So nothing volatile is stored here. Every measured value is
RE-DERIVED at call time from its authority, and every live-file read is
SNAPSHOT-STAMPED so the consumer knows the value is as-of, never "current".
The only static text is POLICY (the measurement contract, the constraints),
which is a rule rather than a measurement.

THE MORATORIUM AXES ARE PARSED FROM CLAUDE.md, never restated. CLAUDE.md is the
LAW and the only authority on that list. If the parse fails this tool says so
LOUDLY and emits [UNKNOWN] rather than a plausible-looking list - degrading
closed, because a silently-short fence is the exact defect above.

Usage:
    python scripts/agent_brief.py                 # markdown, for a prompt
    python scripts/agent_brief.py --json          # machine-readable
    python scripts/agent_brief.py --no-contract   # facts only, omit policy

Read-only. Writes nothing. Runs in well under a second so an agent can call it.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

UNKNOWN = "[UNKNOWN]"


def _stamp(path: Path) -> str:
    """UTC mtime of a live file, so every value it feeds is explicitly as-of."""
    try:
        return datetime.fromtimestamp(
            path.stat().st_mtime, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except OSError:
        return UNKNOWN


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _dig(obj, *keys, default=None):
    for k in keys:
        if not isinstance(obj, dict):
            return default
        obj = obj.get(k)
    return default if obj is None else obj


def moratorium_axes() -> tuple[list[str], str]:
    """The cohort-resetting axes, PARSED FROM CLAUDE.md - never restated here.

    Returns (axes, source_note). An empty list means the parse failed, and the
    caller must surface that rather than substituting a remembered list: a
    fence that is short by four axes is how an era gets restarted by accident.
    """
    law = REPO / "CLAUDE.md"
    try:
        txt = law.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return [], "CLAUDE.md unreadable"
    m = re.search(
        r"COHORT-RESETTING.*?restarts accrual\)\s*:(.*?)(?:\*\*|\Z)",
        txt, re.DOTALL)
    if not m:
        return [], "parse failed - CLAUDE.md wording changed"
    body = re.sub(r"\s+", " ", m.group(1))
    body = re.sub(r"\([^)]*\)", "", body)          # drop parentheticals
    body = body.replace("changes to", "")
    parts = re.split(r",| or ", body)
    axes = [p.strip(" .—-") for p in parts]
    axes = [a for a in axes if a and len(a) > 2]
    return axes, "parsed from CLAUDE.md"


def collect() -> dict:
    """Every fact, re-derived. No value in this function is a literal."""
    out: dict = {"generated_utc": _now(), "repo": str(REPO)}

    # --- the execution era: the code is the authority -----------------------
    try:
        from core.fill_ledger import EXEC_ERA
        out["exec_era"] = str(EXEC_ERA)
    except Exception:
        out["exec_era"] = UNKNOWN
    # the ordinal lives only in a comment beside the stamp; degrade closed
    out["era_ordinal"] = UNKNOWN
    if out["exec_era"] != UNKNOWN:
        try:
            src = (REPO / "core" / "fill_ledger.py").read_text(
                encoding="utf-8", errors="replace")
            m = re.search(r"^#\s*" + re.escape(out["exec_era"])
                          + r"\b[^\n]*?\(era-(\d{1,2})\)", src, re.MULTILINE)
            if m:
                out["era_ordinal"] = f"era-{m.group(1)}"
        except OSError:
            pass

    # --- config: fee row, label geometry inputs -----------------------------
    cfg = _json(REPO / "config.json") or {}
    out["config_stamp"] = _stamp(REPO / "config.json")
    out["maker_fee_bps"] = _dig(cfg, "pretrade", "maker_fee_bps", default=UNKNOWN)
    out["taker_fee_bps"] = _dig(cfg, "pretrade", "taker_fee_bps", default=UNKNOWN)
    for key in ("label_round_trip_cost_pct", "label_pt_vol_mult",
                "label_sl_vol_mult", "label_pt_cost_mult", "label_max_bars"):
        out[key] = _dig(cfg, "ml", key, default=UNKNOWN)

    # derived, not stored: the barrier geometry the label is using right now
    out["label_pt_bps"] = out["label_sl_bps"] = UNKNOWN
    try:
        from ml.labeling import barrier_geometry
        pt, sl = barrier_geometry(
            0.0, float(out["label_round_trip_cost_pct"]),
            float(out["label_pt_vol_mult"]), float(out["label_sl_vol_mult"]),
            float(out["label_pt_cost_mult"]))
        out["label_pt_bps"] = round(pt * 1e4, 2)
        out["label_sl_bps"] = round(sl * 1e4, 2)
        out["meef_dpt_dcost"] = float(out["label_pt_cost_mult"])
    except Exception:
        out["meef_dpt_dcost"] = UNKNOWN

    # --- live runtime state: ALWAYS stamped ---------------------------------
    st_path = REPO / "outputs" / "status.json"
    st = _json(st_path) or {}
    out["status_stamp"] = _stamp(st_path)
    out["mode"] = st.get("mode", UNKNOWN)
    out["runner_state"] = st.get("runner_state", UNKNOWN)
    ls = _dig(st, "ml", "load_stats", default={}) or {}
    out["corpus_rows"] = ls.get("rows", UNKNOWN)
    out["mean_uniqueness"] = ls.get("mean_uniqueness", UNKNOWN)
    out["ess_kish"] = ls.get("ess_kish", UNKNOWN)
    # n_eff has THREE competing derivations in the record; publish the routes,
    # never one number, and say they disagree.
    out["n_eff_routes"] = {}
    if isinstance(out["corpus_rows"], (int, float)) and \
            isinstance(out["mean_uniqueness"], (int, float)):
        out["n_eff_routes"]["rows_x_uniqueness"] = round(
            out["corpus_rows"] * out["mean_uniqueness"], 1)
    if isinstance(out["ess_kish"], (int, float)):
        out["n_eff_routes"]["ess_kish_published"] = out["ess_kish"]
    out["n_eff_note"] = ("routes DISAGREE; a third derivation (~896, pooled-u "
                         "restricted to returned rows) is in the record. Pick a "
                         "route explicitly and say which.")
    for k in ("edge_ratio_bump", "stop_widen", "kelly_mult"):
        out[k] = _dig(st, "monitor", k, default=UNKNOWN)
    out["ws_kraken"] = _dig(st, "ws_kraken", default={})
    out["moomoo_available"] = _dig(st, "moomoo", "available", default=UNKNOWN)

    # --- safety posture -----------------------------------------------------
    sentinel = REPO / "outputs" / "force_dry.on"
    out["force_dry_sentinel_present"] = sentinel.exists()
    out["dry_run_config"] = _dig(cfg, "system", "dry_run", default=UNKNOWN)

    # --- the law ------------------------------------------------------------
    axes, note = moratorium_axes()
    out["cohort_resetting_axes"] = axes or UNKNOWN
    out["cohort_resetting_source"] = note
    out["cohort_resetting_count"] = len(axes) if axes else UNKNOWN

    # --- last battery result, if one is on disk (stamped, may be stale) -----
    rep = REPO / "outputs" / "overfit_report.md"
    out["overfit_report_stamp"] = _stamp(rep) if rep.exists() else UNKNOWN
    out["overfit_summary"] = UNKNOWN
    if rep.exists():
        try:
            for line in rep.read_text(encoding="utf-8",
                                      errors="replace").splitlines():
                if "passed" in line and "failed" in line:
                    out["overfit_summary"] = line.strip()
        except OSError:
            pass
    return out


CONTRACT = """\
# DELEGATED-MEASUREMENT CONTRACT (enforced; measured cause - under-determined
# specs produced 5 of 9 wrong numbers, because agents fill gaps silently
# rather than halting)
  a. BOUNDARIES ARE EXACT. No approximations. State inclusive epoch/line/row
     bounds once, verbatim, in every prompt sharing the window.
  b. NAME THE NEEDLE. Exact grep string per source. Unknown needle -> locate it
     and report the string you used.
  c. SNAPSHOT-STAMP LIVE FILES. status.json / *.lock / logs mutate: report the
     read time; values are AS-OF, never "current".
  d. ONSET CLAIMS NEED FULL-RANGE SCANS. "First/earliest/began" never from a
     sampled tail.
  e. DOUBLE-DERIVE LOAD-BEARING COUNTS. Two routes; report both if they differ.
  f. PROVENANCE PER CLAIM. file + filter + value. Tag [K] read / [I] inferred /
     [UNKNOWN]. Never estimate silently.
  g. RE-DERIVE, DO NOT RECALL - including numbers in this brief and in your own
     earlier summaries.

# STANDING CONSTRAINTS
- Read-only unless the task says otherwise. Do not restart or kill the runner
  or supervisor. Do not run the full DoD matrix or heavy model fits.
- "THE INSTRUMENT IS THE FIRST SUSPECT." The measurement plane is the
  least-governed code here and its failures are SILENT. A green is only as big
  as its corpus. "0 findings" and "the scan is broken" are the SAME observation
  until separated - say which you established.
- EVERY finding and EVERY proposal carries its moratorium class:
  SAFE | COHORT-RESETTING | OPERATOR-DOCKET | NEEDS-LIVE-DATA.
"""

AUTHORING_NOTE = """\
# AUTHORING A WORKFLOW SCRIPT THAT PARSES (bought by a real parse failure)
- Workflow scripts are PLAIN JS. A backtick inside a template literal ends it:
  prose containing `if book:` or `git diff` breaks the parse with a confusing
  column number. Build long prompt blocks as ARRAY-OF-STRINGS + .join('\\n')
  and avoid backticks in prose entirely.
- Heredocs mangle backslash escapes through this repo's shell hook. Write
  regex-heavy patch scripts to a FILE (Write tool) and run the file.
- Cache the fan-out prefix: run ONE agent first, then fan out, so the shared
  CONTEXT block is a cache hit rather than N concurrent cache writes.
"""


def render(facts: dict, contract: bool = True, authoring: bool = False) -> str:
    L = []
    A = L.append
    A("# LIQUIDITYBOT - BRIEFING BLOCK")
    A(f"generated {facts['generated_utc']} by scripts/agent_brief.py")
    A("EVERY VALUE BELOW WAS RE-DERIVED AT GENERATION TIME. Live-file values are")
    A("AS-OF their stamp and MUST be re-derived, never quoted from this block.")
    A("")
    A("## Execution era and the law")
    A(f"- exec_era: {facts['exec_era']}  ordinal: {facts['era_ordinal']}"
      "   (authority: core/fill_ledger.EXEC_ERA)")
    A(f"- cohort-resetting axes ({facts['cohort_resetting_count']}), "
      f"{facts['cohort_resetting_source']}:")
    axes = facts["cohort_resetting_axes"]
    if isinstance(axes, list):
        for a in axes:
            A(f"    * {a}")
    else:
        A("    !! COULD NOT PARSE THE FENCE FROM CLAUDE.md. Do NOT substitute a")
        A("       remembered list - read CLAUDE.md yourself before classifying")
        A("       anything. A short fence is how an era gets restarted.")
    A("- SAFE = measurement/report tools, dashboards, tests, wiki, telemetry,")
    A("  and bug fixes that do not change which orders are placed or how they fill.")
    A("")
    A("## Safety posture")
    A(f"- mode: {facts['mode']}   runner_state: {facts['runner_state']}"
      f"   (status.json as-of {facts['status_stamp']})")
    A(f"- system.dry_run in config: {facts['dry_run_config']}")
    A(f"- outputs/force_dry.on present: {facts['force_dry_sentinel_present']}")
    A("- the road to live has FOUR steps: delete the sentinel (or boot --fresh)")
    A("  -> config dry_run:false -> restart -> typed ARM LIVE. The sentinel step")
    A("  fails SAFE and SILENTLY; a three-step version will not reach live.")
    A("")
    A("## Booked cost and the label geometry it determines")
    A(f"- maker/taker bps: {facts['maker_fee_bps']}/{facts['taker_fee_bps']}"
      f"   (config as-of {facts['config_stamp']})")
    A(f"- label_round_trip_cost_pct: {facts['label_round_trip_cost_pct']}")
    A(f"- pt/sl/cost mults: {facts['label_pt_vol_mult']}/"
      f"{facts['label_sl_vol_mult']}/{facts['label_pt_cost_mult']}"
      f"   label_max_bars: {facts['label_max_bars']}")
    A(f"- label geometry AT THE COST FLOOR: PT {facts['label_pt_bps']} bps / "
      f"SL {facts['label_sl_bps']} bps  (re-derived via ml.labeling.barrier_geometry)")
    A(f"- MEEF dPT/dcost = {facts['meef_dpt_dcost']} exactly at the floor: a 1 bp")
    A("  fee-booking error moves the label target by that many bps. Fee-booking")
    A("  tolerance must be that much tighter than label tolerance.")
    A("")
    A("## Corpus (VOLATILE - the runner appends every cycle)")
    A(f"- rows: {facts['corpus_rows']}   mean_uniqueness: {facts['mean_uniqueness']}"
      f"   (as-of {facts['status_stamp']})")
    A(f"- n_eff routes: {json.dumps(facts['n_eff_routes'])}")
    A(f"  NOTE: {facts['n_eff_note']}")
    A("")
    A("## Live controller knobs (must sit at neutral during era accrual)")
    A(f"- edge_ratio_bump: {facts['edge_ratio_bump']} (neutral 0.0)"
      f"   stop_widen: {facts['stop_widen']} (neutral 1.0)"
      f"   kelly_mult: {facts['kelly_mult']} (neutral 1.0)")
    A("  These move the ENTRY BAR and STOP GEOMETRY autonomously on cause-share")
    A("  triggers; both axes are cohort-resetting. If any is off-neutral, say so.")
    A("")
    A("## Data plane")
    A(f"- kraken ws: {json.dumps(facts['ws_kraken'])}")
    A(f"- moomoo available: {facts['moomoo_available']}")
    A("")
    A("## Last overfit battery on disk (may be stale - check the stamp)")
    A(f"- stamp: {facts['overfit_report_stamp']}")
    A(f"- summary line: {facts['overfit_summary']}")
    A("- READ THE ARMED COUNT, never the exit code: four of seven rungs can fail")
    A("  to ARM, and 'passed 3, failed 0' reads identically whether seven fired")
    A("  or three did. The corpus prints on the summary line - read it every run.")
    if contract:
        A("")
        A(CONTRACT.rstrip())
    if authoring:
        A("")
        A(AUTHORING_NOTE.rstrip())
    return "\n".join(L)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--json", action="store_true", help="machine-readable facts")
    ap.add_argument("--no-contract", action="store_true",
                    help="omit the measurement contract and constraints")
    ap.add_argument("--authoring", action="store_true",
                    help="append the workflow-authoring notes")
    args = ap.parse_args(argv)
    facts = collect()
    if args.json:
        print(json.dumps(facts, indent=2, default=str))
    else:
        print(render(facts, contract=not args.no_contract,
                     authoring=args.authoring))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
