"""
scripts/overfit_check.py — whole-codebase overfit audit, rev 4

Runs every overfitting instrument the system has against every layer
that can overfit, entirely offline, and emits a PASS/FAIL report:

  [OF-1] TRAIN/OOF GAP        ml/overfit.train_test_gap on the live
                              labeled history (or the planted-signal
                              synthetic benchmark when the LOADED corpus
                              is under len(FEATURE_NAMES)*10 rows, clearly
                              labeled as machinery validation). That
                              predicate counts LOADED rows - candidate +
                              live, after every filter - not live rows;
                              the flat "60" this line used to claim was
                              deleted 2026-07-11 (7486ab29) and the stale
                              wording caused a real misdiagnosis on
                              2026-08-08, so it is spelled out here.
  [OF-2] SHUFFLED-LABEL NULL  leakage detector: destroyed labels must
                              yield chance OOF AUC through the purged
                              walk-forward. Catches purge bugs, feature
                              peeking, index misalignment.
  [OF-3] MODEL-SPACE PBO      CSCV probability-of-backtest-overfitting
                              across the model/hyperparameter space the
                              selector actually chooses from.
  [OF-4] STRATEGY PLATEAU     parameter-sensitivity via deterministic
                              record/replay: sweep post-signal knobs
                              (min_p_win, chandelier_k, edge ratio) and
                              measure whether performance sits on a
                              plateau (robust) or a spike (curve-fit).
  [OF-5] DEFLATED SHARPE      gate on live results: with < 30 labeled
                              live trades it reports DEFERRED, which is
                              the honest answer. While dry-run active
                              learning is on (ml.exploration.enabled) the
                              live sample is EV-mixed by design, so DSR
                              is reported INFORMATIONAL, not gated; it
                              arms when exploration is disabled.

EXPLORATION-PHASE GATING (operator adjudication 2026-08-09). OF-1 and
OF-7's dead-feature check follow the OF-5 rule above for the same
reason: while ml.exploration.enabled is true the corpus is dominated by
EV-mixed probe/candidate rows bought to acquire labels, so both grade
the acquisition phase rather than anything a trade depends on. NO
THRESHOLD MOVED - 0.12 and 0.55 are unchanged and the numbers are always
printed; only what they BLOCK is scoped, because this battery stage
gates CODE deploys and model trust is enforced independently by
ml.model_selection's evidence floors and the live ML governor. Both
gates are fail-CLOSED (an unreadable config gates fully), stay HARD on
the synthetic benchmark where they validate the instrument, and re-arm
by themselves when exploration is switched off.

Usage:
  python scripts/overfit_check.py [--quick] [--recording PATH]
Exit code 0 = all applicable checks pass, 1 = any failure.
"""

import argparse
import datetime as _dt
import json
import logging
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np                                            # noqa: E402

from ml.history import load_for_config, store_for_config       # noqa: E402
from ml.models import GradientBoostedStumps                    # noqa: E402
from ml.overfit import (LC_MIN_OOF, LC_TREND_MARGIN_AUC,       # noqa: E402
                        REGIME_DEGRADE_MARGIN_AUC, REGIME_MIN_N,
                        REGIME_STRATA, deflated_sharpe,
                        feature_dof_report, learning_curve,
                        learning_curve_trend, model_space_pbo,
                        purge_leakage_probe, regime_stratified_oof,
                        regime_stratum_labels, shuffled_label_check,
                        train_test_gap)

log = logging.getLogger("liquiditybot.scripts.overfit")
PASS_N, FAIL_N = 0, 0
REPORT: list = []

# The gate families observed to ARM on this box's live corpus, keyed by the
# token before the ':' in each check() name. A RATCHET, read at the bottom of
# main(): a family here that stops arming exits 3 (see the block there for
# why monotone-arming rather than "all seven must arm"). Measured 2026-09-10
# on the live-history corpus, two runs an hour apart:
#   shuffle  OF-2 shuffle-null
#   pbo      OF-3 PBO on the deployed simplicity ladder
#   purge    OF-6 purged/embargoed CV
#   dof      OF-7 "not starved" (>=10 rows per feature); the OTHER dof line,
#            the dead-feature fraction, is info() under exploration and never
#            enters REPORT as PASS/FAIL, so this key stays unambiguous
# NOT here, and deliberately: OF-1 (informational under exploration), OF-4
# (plateau inert on a zero-entry recording), OF-5 (DSR deferred below its
# conviction floor and documented unpassable at N=7). Add a family when it
# starts arming - the script prints NEWLY ARMED to prompt exactly that. Never
# remove one to get green; that is the widening CLAUDE.md forbids.
EXPECTED_ARMED = {"shuffle", "pbo", "purge", "dof", "dsr"}


def check(name: str, ok: bool, detail: str = ""):
    global PASS_N, FAIL_N
    mark = "ok  " if ok else "FAIL"
    line = f"  {mark}  {name}" + (f"  {detail}" if detail else "")
    print(line)
    REPORT.append(("PASS" if ok else "FAIL", name, detail))
    if ok:
        PASS_N += 1
    else:
        FAIL_N += 1


def info(name: str, detail: str = ""):
    print(f"  --    {name}" + (f"  {detail}" if detail else ""))
    REPORT.append(("INFO", name, detail))


def armed_families(report) -> set:
    """The gate families that actually FIRED, keyed by the token before ':'.

    INFO lines are excluded by construction: a gate that could not fire is
    not an armed gate, which is the whole distinction this file's summary
    prints and the exit code did not carry.
    """
    return {str(name).split(":")[0].strip()
            for kind, name, _ in report if kind in ("PASS", "FAIL")}


def arming_exit_code(report, expected, fail_n: int, emit=print, *,
                     on_synthetic: bool = False,
                     forced_synthetic: bool = False,
                     corpus_absent: bool = False) -> int:
    """0 green, 1 a gate FAILED, 3 arming REGRESSED, 4 SILENT synthetic.

    Pure (given `emit`) so the policy is unit-testable rather than only
    observable by running a 2-minute battery.

    Precedence, and why:
      1  a real FAILURE outranks everything - something measured and said no.
      4  a SILENT synthetic substitution outranks an arming regression,
         because it invalidates every rung above it at once: the battery
         measured the planted-signal benchmark, so "which gates armed" is a
         fact about the fixture, not about the strategy. `--force-synthetic`
         is DELIBERATE (CI runs it on purpose) and stays green; the
         under-the-row-floor fallback is the one nobody chose.
      3  arming regressed - a family that fired before did not this run.

    CORPUS ABSENT IS NOT A SILENT SUBSTITUTION (red-team OBJ-13, conceded).
    `test_windows.bat:57` vetoes on ANY non-zero, so returning 4 on a tree with
    no corpus AT ALL printed "OVERFIT GATES FAILED - do not arm" for every
    worktree-resident agent, with zero defect in the code - a permanently red
    gate, which this same docstring elsewhere calls a brick rather than a gate.
    The hazard 4 exists for is a corpus that EXISTS and was silently swapped
    out because it fell under the row floor: something was there, and nobody
    chose to ignore it. An absent corpus is an ENVIRONMENT, reported loudly and
    exiting 0 - the battery still validated the machinery, and there was nothing
    to be silent about.

    The synthetic case was found by an adversarial audit re-testing the
    EXPECTED_ARMED ratchet added minutes earlier and showing it did NOT
    cover this: forcing the corpus under the row floor with no CLI flag
    still exited 0. Worse, the synthetic fixture ARMS ALL SEVEN rungs while
    the live corpus arms four - so the ratchet is not merely blind here, it
    is SATISFIED by the substitution. A roster check alone would have made
    the silent case look better than the real one.
    """
    armed = armed_families(report)
    newly_armed = sorted(armed - set(expected))
    went_dark = sorted(set(expected) - armed)
    if newly_armed:
        emit(f"  ^^ NEWLY ARMED: {newly_armed} - add to EXPECTED_ARMED so "
             f"the ratchet holds the new floor")
    if fail_n:
        return 1
    if on_synthetic:
        if not forced_synthetic and corpus_absent:
            emit("  ^^ NO CORPUS on this tree - the battery validated the "
                 "MACHINERY, not the market. Not a defect and not a silent "
                 "substitution: there was nothing to substitute. Exit 0.")
            return 1 if fail_n else 0
        if not forced_synthetic:
            emit("  ^^ SILENT SYNTHETIC SUBSTITUTION: the corpus fell under "
                 "the row floor and the battery scored the planted-signal "
                 "benchmark without anyone asking for it. Every rung above "
                 "measured the FIXTURE. This is not a green about the "
                 "strategy. Re-read the corpus line; do NOT lower the floor "
                 "to make it go away.")
            return 4
        # DELIBERATE synthetic run: the ROSTER CHECK DOES NOT APPLY. Which
        # families arm against a planted-signal fixture is a property of the
        # fixture, not of the corpus - tests/test_audit_ml_offline.py stubs
        # `pbo` outright for speed, and reading that stub as an arming
        # regression would make the ratchet fire on its own test harness.
        # (It did, first run: 'ARMING REGRESSED: [pbo]', exit 3 against a
        # test asserting 0. The suite caught it; the fix is here, not there.)
        return 0
    if went_dark:
        emit(f"  ^^ ARMING REGRESSED: {went_dark} armed before and did not "
             f"this run. A gate that stopped firing is not a pass; read WHY "
             f"above (corpus, exploration flag, evidence gate) before "
             f"treating this battery as green.")
        return 3
    return 0


def gate_is_informational(explore_on: bool, on_synthetic: bool) -> bool:
    """THE exploration-phase gating predicate for OF-1 and OF-7's
    dead-feature check (operator adjudication 2026-08-09; see the module
    header). One function so the two gates can never drift apart, and a
    pure one so the policy is unit-testable instead of only observable
    through a 40s CLI run.

    True = report the number, do not block. It never changes a THRESHOLD;
    it decides whether a threshold's verdict gates the CODE battery.

    Two properties are deliberate and load-bearing:
      * fail-CLOSED - a caller that could not read the config passes
        explore_on=False and gets the full gate, matching OF-5/DSR;
      * the SYNTHETIC benchmark always gates, because there these checks
        validate the INSTRUMENT (planted signal, known answer) rather
        than the corpus, and an instrument must never grade itself
        leniently."""
    return bool(explore_on) and not bool(on_synthetic)


# ---------------------------------------------------------------------------
def split_dsr_samples(live_rows: list) -> tuple[list, list]:
    """OF-5 sample selection (pure, unit-tested). Returns (conviction, mixed)
    PnL lists from live-source rows. Conviction = probe column explicitly
    "0" — a PT-050 probe ("1") bypassed the profit-EV gate to buy its label,
    and a pre-marker row ("") is unknown provenance; neither may vouch for
    the deployed strategy's Sharpe. Mixed = every live row (the legacy
    sample, still reported for context)."""
    conviction, mixed = [], []
    for row in live_rows:
        try:
            pnl = float(row.get("net_pnl_usd"))
        except (TypeError, ValueError):
            continue
        mixed.append(pnl)
        if str(row.get("probe", "")).strip() == "0":
            conviction.append(pnl)
    return conviction, mixed


def dsr_sample_span(live_rows: list) -> dict:
    """Calendar span of the CONVICTION rows, so OF-5 stops hiding its corpus.

    WHY THIS EXISTS (2026-09-11). OF-5 grades whatever `probe == "0"` rows
    exist, with NO time bound and NO era bound, and prints only a count. The
    count reads as "30 recent conviction trips". Measured that day it was 30
    trips spanning 53 days, of which 28 closed BEFORE cut #10 - so the graded
    Sharpe was overwhelmingly a statistic about configurations that had been
    superseded twice, presented as a verdict on the deployed one.

    CLAUDE.md's era law is explicit that trips are "all citable AS their era,
    none poolable across a cut", and reading-discipline rule (c): a series
    that crosses a corpus reset is not one series. OF-5 crosses several.

    IT CANNOT BE ERA-SCOPED HERE, and that is a settled finding, not work
    anyone still owes. `signal_history.csv` carries NO `exec_era` column -
    the stamp lives in `core/fill_ledger.py` (outputs/fills.csv), a different
    file keyed by position_id, and `core/session_digest.py` already says so
    in as many words. Era-scoping would have required either that join or a
    schema addition; it was considered and REFUSED - see the adjudication
    directly below, which is the operative instruction.

    ==> ADJUDICATED 2026-09-11. THE OPERATOR'S DECISION, VERBATIM: "Keep
    pooling." OF-5's sample definition is SETTLED and STAYS POOLED. This is
    not a pending item, not a known defect, and not a TODO. Do NOT era-scope
    this gate, do NOT add the fill-ledger join to narrow it, and do NOT read
    the pooling as a bug someone forgot to fix - it was put to the operator
    with the measurement in hand and this is the answer that came back.

    The decision is deliberate and its cost was named before it was taken:
    era-scoped, OF-5 would DEFER, because the deployed era's WHOLLY-INSIDE
    conviction count sits far under this gate's own 30 floor; pooled, it
    GRADES and it FAILS. The operator chose the graded red over the honest
    silence. What this function exists to do is make that red READABLE - so
    the FAIL is never mistaken for a verdict on the deployed configuration,
    which contributes a small minority of the sample.

    NO COUNT IS WRITTEN HERE, and the omission is the point. An earlier draft
    of this docstring asserted "era-9 held 2 conviction trips" as standing
    fact. An adversarial pass refuted it against the repo's own instrument:
    joined to `outputs/fills.csv` by position_id, those 2 trips carry legs
    stamped across THREE eras, which `cohort_eval` classifies MIXED, so the
    count WHOLLY INSIDE the deployed era was ZERO - and a further 19 of 30
    are unattributable (blank stamps or absent from the ledger). The sibling
    docstring in `ml/overfit.py` refuses to write a corpus figure for exactly
    this reason; this one had broken that discipline in the same change.
    Re-derive from `report_dsr_sentinel` below, which prints it per run.
    Record: vault `sources/session-20260911-of5-dsr-reading`.

    Pure and unit-tested; report-only, grades nothing."""
    ts, rejected = [], 0
    for row in live_rows:
        if str(row.get("probe", "")).strip() != "0":
            continue
        t = _usable_epoch(row.get("ts"))
        if t is None:
            rejected += 1
            continue
        # The validity check lives in `_usable_epoch` above, shared with the
        # deployed-era sentinel. It is NOT a try/except around float():
        # float() accepts "nan", "inf" and a millisecond stamp, each of which
        # then reaches datetime.fromtimestamp() in dsr_disclosure and raises
        # ValueError / OverflowError / OSError from a call site inside a
        # DEFINITION-OF-DONE gate. NOT HYPOTHETICAL: `ml/history.py:180` reads
        # this same file with `float(row.get("ts") or "nan")`.
        ts.append(t)
    if not ts:
        return {"available": False, "n": 0, "rejected": rejected}
    ts.sort()
    return {"available": True, "n": len(ts), "first": ts[0], "last": ts[-1],
            "days": (ts[-1] - ts[0]) / 86400.0, "rejected": rejected}


# ---------------------------------------------------------------------------
# OF-5 DEPLOYED-ERA REGRESSION SENTINEL
#
# WHY THIS EXISTS, and it is the operator's own requirement (2026-09-11):
# "Put something in place to make sure if it is regressive then it's not
# silenced."
#
# THE HAZARD. OF-5 pools execution eras BY OPERATOR DECISION ("Keep pooling").
# Its FAIL is therefore expected and documented - 28 of the 30 conviction
# trips at the adjudication predated cut #10. But a documented red is a red
# nobody looks at, and the next reader has a ready-made dismissal for ANY
# OF-5 failure: "that's the known legacy drag." If the DEPLOYED strategy
# starts genuinely losing, that signal arrives inside a gate already agreed
# to be red, and it is invisible. Documenting a failure is how a real
# regression gets waved through.
#
# THE ANSWER is not to change OF-5 - the operator settled its sample. It is a
# SECOND, SEPARATELY NAMED predicate over the CURRENT era only, which is
# silent while the deployed config is fine and goes FAIL on its own line when
# it is not. The pooled gate answers "has a Sharpe been demonstrated"; this
# answers "is what we are running now LOSING MONEY", which is a different
# question and the one a red must never be able to hide.
#
# IT DOES NOT ERA-SCOPE OF-5 AND MUST NEVER BE MADE TO. The graded pooled
# verdict is untouched; this adds a line, it does not narrow a sample.
#
# FAMILY TOKEN. It reports as `dsr: ...` so `armed_families()` reads it as the
# already-expected "dsr" family. Deliberate: this rung arms CONDITIONALLY (it
# defers below OF5_SENTINEL_MIN_N), so a distinct family name would either
# spam "NEWLY ARMED" every run or, added to EXPECTED_ARMED, fire "ARMING
# REGRESSED" (exit 3) on every run where the era is still young.
OF5_SENTINEL_MIN_N = 10

# ONE-SIDED 95%. The predicate is `ok = ub95 >= 0` - a single-tailed question
# ("has the deployed era DEMONSTRATED a loss?"), so a two-tailed 1.96 runs it
# at alpha=0.025 and halves the advertised sensitivity IN THE NOT-FIRING
# DIRECTION (red-team OBJ-12, conceded). For an anti-silencing alarm that is
# the dangerous way to be wrong. 1.645 is also the repo's shipped convention
# for exactly this shape: `ml/monitor.py:79 wilson_ucb(..., z=1.645)`,
# docstring "One-sided 95% Wilson UPPER bound". The alpha is now stated on the
# printed line rather than implied by a field name.
SENTINEL_Z = 1.645


def _usable_epoch(value):
    """A parsed, RANGE-CHECKED unix epoch, or None. Shared, deliberately.

    `float()` accepts "nan", "inf" and a millisecond stamp, so a try/except
    around it is not a validity check - the lesson `dsr_sample_span` was fixed
    for, which the sentinel then repeated with worse consequences (a single ms
    stamp built a ~54,000-year span and halved every other trip's uniqueness).
    Both callers use this one function so the two cannot drift apart again.

    Upper bound 4e9 is ~2096 and is a SCHEMA check, not a date opinion: a
    seconds epoch cannot plausibly exceed it, while a millisecond stamp
    (~1.79e12 today) blows straight past."""
    try:
        t = float(value)
    except (TypeError, ValueError):
        return None
    if t != t or t in (float("inf"), float("-inf")):       # NaN / +-inf
        return None
    return t if 0.0 < t < 4e9 else None


def _exec_era_now() -> str:
    """The CURRENT execution era, read from the module that stamps it.

    Read, never hardcoded - the era rolls at every cut, and a date or sha
    frozen into this file would leave the sentinel silently watching a
    SUPERSEDED era while the live one regressed unobserved. That is the exact
    decay shape this repo has a register of. `core/fill_ledger.EXEC_ERA` is
    the writer of the stamps being matched, so it is the only honest source.
    Empty string on failure -> the sentinel reports INDETERMINATE rather than
    silently measuring nothing."""
    try:
        from core.fill_ledger import EXEC_ERA
        return str(EXEC_ERA or "")
    except Exception:                                      # noqa: BLE001
        return ""


def dsr_deployed_segment(live_rows: list, fills_path, exec_era: str) -> dict:
    """The conviction trips WHOLLY INSIDE the current execution era.

    "Wholly inside" is `scripts/cohort_eval.py`'s standard, reused rather than
    reinvented: a trip counts only when every exec_era stamp on its fills is
    the current era. Straddlers - opened in one era, closed in another - are
    counted in NEITHER, because pooling across a fee correction is what the
    moratorium forbids and a straddler is half of each.

    The join is signal_history.position_id -> fills.csv.position_id, because
    signal_history carries no exec_era of its own (see dsr_sample_span).

    Degrades HONESTLY: a missing/unreadable ledger returns available=False
    with a reason, never a silent empty segment that would read as "no
    regression". Report-only; grades nothing by itself."""
    import csv as _csv
    if not exec_era:
        return {"available": False,
                "reason": "current exec_era unreadable (core.fill_ledger)"}
    rows = [r for r in live_rows if str(r.get("probe", "")).strip() == "0"]
    try:
        with open(fills_path, encoding="utf-8") as fh:
            fills = list(_csv.DictReader(fh))
    except (OSError, ValueError) as exc:
        return {"available": False,
                "reason": f"fill ledger unreadable ({exc.__class__.__name__})"}
    if not fills or "exec_era" not in (fills[0].keys() if fills else {}):
        return {"available": False,
                "reason": "fill ledger carries no exec_era column"}

    # PURITY IS OVER ALL LEGS, NOT OVER STAMPED LEGS. `cohort_eval.py:557`
    # refutes the weaker form verbatim and in advance: building `eras` from
    # stamped legs only makes `len(eras) == 1` mean "every leg that CARRIED a
    # stamp agreed", which silently overstates the accruing count the moment a
    # stale-binary or pre-stamp leg lands in the current era. The first cut of
    # this function used exactly that weaker form while its docstring claimed
    # to reuse cohort_eval's standard (red-team OBJ-10, conceded). A trip with
    # ANY unstamped leg is now IMPURE and excluded.
    stamps, opened, unstamped = {}, {}, set()
    for f in fills:
        pid = f.get("position_id") or ""
        if not pid:
            # "" is a legal dict key on both sides of this join, so a blank
            # position_id would merge every unattributed fill into one
            # pseudo-trip and then match blank-pid history rows against it
            # (red-team OBJ-13: injection returned n=4 total=-26.00 where the
            # correct answer was n=1 +1.00). `ml/history.py:1786` already
            # guards this exact join on this exact file; the gate was the
            # outlier. core/fill_ledger.py writes `order.position_id or ""`,
            # so the blank is reachable from the shipped writer.
            continue
        era = (f.get("exec_era") or "").strip()
        if era:
            stamps.setdefault(pid, set()).add(era)
        else:
            unstamped.add(pid)
        t = _usable_epoch(f.get("ts"))
        if t is not None:
            opened[pid] = min(opened.get(pid, t), t)

    # ONE POPULATION. The first cut appended to `pnl` BEFORE the span checks
    # and `continue`d afterwards, so a trip could enter the mean while leaving
    # `spans` - n and n_eff were then computed over DIFFERENT sets. Measured
    # (red-team OBJ-8, conceded): one close-ts written in milliseconds creates
    # a ~54,000-year span that overlaps every other trip, halving their
    # uniqueness. n stayed 16, n_eff fell 16.000 -> 8.500, SE inflated x1.372
    # and ub95 moved -0.2151 -> -0.0173 on an UNCHANGED book. Any book whose
    # true ub95 lies in [-0.198, 0) was silenced by a single malformed row -
    # a silencing defect inside the instrument built to prevent silencing.
    # A trip now enters only if its PnL, its open and its close are ALL
    # usable, and every exclusion is counted and disclosed.
    pnl, spans = [], []
    dropped = {"blank_pid": 0, "impure_era": 0, "bad_pnl": 0, "no_open": 0,
               "bad_close": 0}
    dropped_pnl = 0.0
    for r in rows:
        pid = r.get("position_id") or ""
        if not pid:
            dropped["blank_pid"] += 1
            continue
        try:
            value = float(r.get("net_pnl_usd"))
        except (TypeError, ValueError):
            value = None
        if pid in unstamped:
            # UNATTRIBUTABLE, not "belongs to another era". A trip carrying an
            # unstamped leg cannot be placed in ANY era, so if ledger stamping
            # degrades, a losing book quietly stops being measurable by this
            # guard. Its PnL is accumulated so the disclosure can say what
            # left the statistic - counting the trips but not the money would
            # understate the channel.
            dropped["impure_era"] += 1
            dropped_pnl += value or 0.0
            continue
        if stamps.get(pid) != {exec_era}:
            continue        # simply a different era - not an exclusion
        if value is None:
            dropped["bad_pnl"] += 1
            continue
        t_open = opened.get(pid)
        t_close = _usable_epoch(r.get("ts"))
        if t_open is None:
            dropped["no_open"] += 1
            dropped_pnl += value
            continue
        if t_close is None or t_close <= t_open:
            dropped["bad_close"] += 1
            dropped_pnl += value
            continue
        pnl.append(value)
        spans.append({"t_open": t_open, "t": t_close})

    n = len(pnl)
    excluded = sum(dropped.values())
    if n == 0:
        # dropped_pnl BELONGS HERE. Omitting it made the DEFERRED line print
        # "$+0.00 of PnL is not in this statistic" while 19 unattributable
        # conviction trips worth -$18.91 sat outside it - the disclosure
        # built to expose a silencing channel was itself silent, because
        # `seg.get("dropped_pnl", 0.0)` fell back to the default. Caught by
        # running it against the live ledger rather than reading it.
        return {"available": True, "n": 0, "era": exec_era,
                "dropped": dropped, "excluded": excluded,
                "dropped_pnl": dropped_pnl}
    mean = sum(pnl) / n
    var = sum((x - mean) ** 2 for x in pnl) / (n - 1) if n > 1 else 0.0
    sd = var ** 0.5
    # EFFECTIVE n, per CLAUDE.md: an SE on nominal n is optimistic by
    # sqrt(n/n_eff), and a too-narrow CI makes this alarm fire EARLY - the
    # wrong direction for a sentinel whose credibility is the whole point.
    # `spans` and `pnl` are now the SAME trips, so this deflation describes
    # the sample it is applied to.
    n_eff = float(n)
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        from scripts.cohort_eval import cohort_effective_n
        en = cohort_effective_n(spans)
        n_eff = float(en["effective_n"]) if en.get("available") else float(n)
    except Exception:                                      # noqa: BLE001
        n_eff = float(n)                                   # nominal fallback
    n_eff = max(min(n_eff, float(n)), 1.0)
    se = sd / (n_eff ** 0.5) if n_eff > 0 else float("inf")
    return {"available": True, "n": n, "era": exec_era, "mean": mean,
            "sd": sd, "n_eff": n_eff, "se": se,
            "z": SENTINEL_Z, "alpha": 0.05,
            "ub95": mean + SENTINEL_Z * se, "total": sum(pnl),
            "dropped": dropped, "excluded": excluded,
            "dropped_pnl": dropped_pnl}


def dsr_sentinel_verdict(seg: dict, min_n: int = OF5_SENTINEL_MIN_N) -> tuple:
    """(armed, ok, detail) for the deployed-era sentinel. Pure.

    ARMS only with >= min_n trips wholly inside the current era. FAILS only
    when the ONE-SIDED 95% upper bound (z=1.645, alpha=0.05) on mean net PnL
    per trip is BELOW ZERO - i.e. the deployed configuration has DEMONSTRATED
    a loss, not merely failed to demonstrate a profit. That asymmetry is
    deliberate: OF-5 already reports the failure-to-demonstrate side, and an
    alarm that fires on ordinary statistical silence would be cried wolf until
    it was ignored, which is the silencing this exists to prevent.

    IT NEVER EXCULPATES (red-team OBJ-11, conceded). The first cut's passing
    branch asserted the pooled red was "legacy drag, not a regression" - an
    affirmative all-clear from a test with single-digit power at its own
    arming floor. At n=10 the detectable loss is roughly 4x the registered H0
    bleed of -$0.27/trip, so "did not fire" there is almost uninformative. The
    passing branch now PRINTS ITS OWN MDE and says only that no loss was
    demonstrated AT THAT SENSITIVITY. A guard that says "all clear" at 6-10%
    power is a silencing device wearing a green badge."""
    if not seg.get("available"):
        return (False, None,
                f"INDETERMINATE - {seg.get('reason', 'no ledger')}; the "
                f"deployed era cannot be segmented, so a regression in it "
                f"would be INVISIBLE. Fix the ledger read before trusting "
                f"any OF-5 reading.")
    drop = seg.get("dropped") or {}
    excl = seg.get("excluded") or 0
    drop_note = ""
    if excl:
        shown = ", ".join(f"{k}={v}" for k, v in drop.items() if v)
        drop_note = (f" [{excl} conviction trip(s) EXCLUDED ({shown}); "
                     f"${seg.get('dropped_pnl', 0.0):+.2f} of PnL is not in "
                     f"this statistic - an exclusion that removes losers is "
                     f"itself a silencing channel, so read this count]")
    n = seg.get("n", 0)
    if n < min_n:
        return (False, None,
                f"DEFERRED - {n} conviction trips wholly inside era "
                f"{seg.get('era')} < {min_n}. The deployed configuration is "
                f"not yet separately measurable; OF-5's pooled verdict says "
                f"NOTHING about it either way.{drop_note}")
    ok = seg["ub95"] >= 0.0
    # MDE: the per-trip mean this sample could actually resolve. Solving
    # mean + z*se < 0 gives mean < -z*sd/sqrt(n_eff). Printed in BOTH
    # branches - a green is only as big as its power.
    mde = -SENTINEL_Z * seg["sd"] / (seg["n_eff"] ** 0.5) \
        if seg["n_eff"] > 0 else float("-inf")
    detail = (f"era={seg['era']} n={n} n_eff={seg['n_eff']:.1f} "
              f"mean=${seg['mean']:+.3f}/trip total=${seg['total']:+.2f} "
              f"ub95=${seg['ub95']:+.3f} (one-sided 95%, z={SENTINEL_Z}) "
              f"MDE=${mde:+.3f}/trip")
    if ok:
        return (True, True,
                f"{detail} - NO LOSS DEMONSTRATED AT THIS SENSITIVITY. That "
                f"is NOT an all-clear, and it says NOTHING about why OF-5's "
                f"pooled gate is red: this test can only resolve a mean "
                f"worse than ${mde:+.3f}/trip, against a registered H0 bleed "
                f"of about -$0.27/trip. Read it as 'not yet decidable', and "
                f"read the MDE before quoting this line.{drop_note}")
    return (True, False,
            f"{detail} - REGRESSION: the one-sided 95% upper bound on the "
            f"DEPLOYED era's mean net PnL is BELOW ZERO. This is NOT the "
            f"documented legacy-pooling red. The configuration running right "
            f"now has demonstrated a loss on its own trips. Do not dismiss "
            f"this as the known OF-5 failure; it is a different "
            f"predicate.{drop_note}")


def report_dsr_sentinel(live_rows: list, fills_path, exec_era: str) -> tuple:
    """Emit the sentinel through check()/info(). Returns (armed, ok).

    The branching lives HERE rather than in main(): main sits against ruff's
    C901 ceiling (40) and a disclosure must not spend the complexity budget
    CLAUDE.md keeps at zero for the shipped scope."""
    seg = dsr_deployed_segment(live_rows, fills_path, exec_era)
    armed, ok, detail = dsr_sentinel_verdict(seg)
    name = "dsr: deployed-era regression sentinel"
    if not armed:
        info(name, detail)
    else:
        check(name, bool(ok), detail)
    return (armed, ok)


def dsr_disclosure(d: dict, live_rows: list) -> str:
    """The two things OF-5's verdict line does not say, as ONE string.

    Built as a single unconditional message on purpose: the branchy version
    of this pushed `main` past ruff's C901 ratchet (41 > 40), and a gate
    disclosure is not worth spending the complexity budget that CLAUDE.md
    keeps at zero for the shipped scope. Pure; grades nothing."""
    psr = d.get("psr_zero")
    sign = ("psr_zero unavailable (track too short)" if psr is None else
            f"PSR(SR*=0)={psr:.3f} -> P(true SR < 0)={1 - psr:.3f}")
    span = dsr_sample_span(live_rows)
    # BELT AND BRACES. dsr_sample_span now range-checks every ts, so nothing
    # here should raise - but this call site sits in a definition-of-done gate
    # with no enclosing try, and a DISCLOSURE must never be the thing that
    # takes the battery down. If the formatting fails the gate still grades;
    # it just says it could not describe its corpus.
    try:
        fmt = "%Y-%m-%d"
        corpus = (
            f"{span['n']} conviction trips spanning "
            f"{_dt.datetime.fromtimestamp(span['first'], _dt.UTC):{fmt}}.."
            f"{_dt.datetime.fromtimestamp(span['last'], _dt.UTC):{fmt}} "
            f"({span['days']:.1f} days)") if span.get("available") else (
            "corpus span UNKNOWN (no row carries a usable ts)")
    except (KeyError, ValueError, OverflowError, OSError) as exc:
        corpus = (f"corpus span UNREADABLE ({exc.__class__.__name__}) - the "
                  f"ts column has changed shape; the gate still graded")
    dropped = span.get("rejected") or 0
    if dropped:
        corpus += (f" [{dropped} conviction row(s) had an unusable ts and are "
                   f"EXCLUDED from this span - a non-finite or out-of-range "
                   f"value, which usually means a unit change or a partial "
                   f"write, and which the GRADED sample still counts]")
    return (
        f"SIGN READING: {sign}. This, NOT the graded dsr, is the 'is the "
        f"edge positive' number - dsr is P(true SR > sr0) where sr0 is the "
        f"expected max under the null across N trials. A red dsr beside a "
        f"PSR near 0.5 means UNDERPOWERED, not harmful. || CORPUS: {corpus}. "
        f"NOT era-scoped: signal_history.csv has no exec_era column (the "
        f"stamp lives in core/fill_ledger.py, keyed by position_id), so this "
        f"sample pools every execution era it covers - different fee "
        f"bookings AND different barrier geometries. CLAUDE.md: trips are "
        f"'citable AS their era, none poolable across a cut'. Read the "
        f"verdict against THIS span, not against the deployed config.")


def synthetic_benchmark(n: int | None = None, seed: int = 11):
    """Planted-signal dataset with the live feature width: linear +
    regime-conditional structure + noise, known learnable ceiling. Used
    to validate the MACHINERY when live history is thin — results are
    about the pipeline, not the market, and the report says so.

    n scales with the feature-vector width (~35 rows/feature, matching
    the ratio this benchmark was originally calibrated at: 1200 rows /
    36 features). GradientBoostedStumps' colsample_bytree draws a FIXED
    FRACTION of columns as split candidates each round, so a wider
    feature vector at a fixed row count gives it more candidates per
    split and less effective regularization on this one fixed seed -
    a dimensionality artifact of adding features (all-zero padding in
    this synthetic set), not a live-model overfitting signal. Keeping
    the row count in step with feature count is a "re-baseline
    consciously" fix: the OF-1 pass bar (gap_auc <= 0.12) stays put."""
    from ml.features import FEATURE_NAMES
    rng = np.random.default_rng(seed)
    d = len(FEATURE_NAMES)
    if n is None:
        n = d * 40
    X = np.zeros((n, d))
    live = rng.normal(size=(n, 6))
    X[:, 0] = np.clip(live[:, 0], -6, 6)          # ret_1
    X[:, 1] = np.clip(live[:, 1], -6, 6)          # ret_6
    X[:, 6] = np.clip(live[:, 2] * 0.5, -2, 2)    # imbalance
    X[:, 11] = np.clip(live[:, 3], -5, 5)         # volume_z
    X[:, 15] = (live[:, 4] > 0).astype(float)     # regime_bull_quiet
    X[:, FEATURE_NAMES.index("direction")] = np.where(live[:, 5] > 0, 1, -1)
    X[:, FEATURE_NAMES.index("gate_confidence")] = 1.0
    logit = (0.5 * X[:, 0] + 0.9 * X[:, 6] * X[:, 15] +
             0.4 * X[:, 11] * (X[:, 15] - 0.5) - 0.1)
    y = (rng.random(n) < 1.0 / (1.0 + np.exp(-logit))).astype(float)
    return X, y


def dof_effective_n(sig, res, n_features: int, label: str = "") -> dict:
    """OF-7's rows-per-feature at EFFECTIVE n, printed beside the nominal one.

    WHY THIS EXISTS (2026-09-15). OF-7 gates on NOMINAL rows: rows/feature =
    n / d against a floor of 10. CLAUDE.md's own measurement standard says
    any statistic over overlapping label windows must report EFFECTIVE n,
    and OF-7's rows are maximally overlapping - one per 5m bar, each label
    spanning up to ml.label_max_bars. So the one gate built to catch an
    under-determined model reads a row count the model does not have, and
    reads it green. That is the degraded-gate shape this repo's own
    definition-of-done section warns about: a green is only as big as its
    corpus.

    IT REPORTS. IT NEVER RE-GATES. Moving OF-7's floor, or swapping the
    quantity the floor is applied to, is a silent re-registration of a
    pre-registered gate - the exact move the overfit-discipline section
    forbids ("DO NOT 'fix' any of these by lowering a floor"; raising the
    bar on a different quantity is that same move wearing a hat). The
    check() beside this call is untouched and its numbers stay byte-
    identical. This is an info() line and it cannot move PASS_N/FAIL_N or
    the exit code.

    ONE BOUND, NOT THE ANSWER. The route is ASSET-BLIND: the same
    cohort_effective_n this file already uses for the OF-5 sentinel, fed
    each row's [signal_ts, resolution_ts] span. It counts two rows on
    DIFFERENT assets that merely overlap in time as concurrent, and two
    different assets' label paths are not one path - so this is a LOWER
    bound on n_eff and therefore a PESSIMISTIC rows/feature. The per-asset
    route is the upper bound and cannot be computed at this seam: the
    training tuple (X, y, w, sig, res) carries no asset column, and
    widening load_training_data's arity to add one is a stable-interface
    change (invariant 7), not a report tweak. The record already holds
    competing derivations spanning roughly an order of magnitude, so this
    prints its route and its DIRECTION and claims nothing more.
    """
    out: dict = {"n": 0, "n_features": int(n_features), "available": False,
                 "route": "asset-blind (lower bound on n_eff)",
                 "label": label}
    # THE SYNTHETIC PATH HANDS BACK None, NOT EMPTY ARRAYS. load_dataset
    # returns (Xs, ys, None, None, None, ...) on the synthetic benchmark -
    # its own docstring says so in as many words - and the first version of
    # this function took len(sig) OUTSIDE the try, so len(None) raised a
    # TypeError that CRASHED THE WHOLE BATTERY to a non-zero exit. Eight
    # suite tests caught it; the live-corpus run this was developed against
    # never could, because on that path sig and res are real arrays. A
    # report-only line taking down the gate it reports on is the worst
    # possible failure for SAFE-class code, and the guard is deliberately
    # the FIRST statement that touches either argument.
    if sig is None or res is None:
        out["reason"] = ("no label times (sig/res are None) - the SYNTHETIC "
                         "benchmark carries no signal_history correspondence, "
                         "so there is no concurrency to measure here; this is "
                         "the expected reading on that corpus, not a defect")
        return out
    n = int(len(sig))
    out["n"] = n
    if n == 0 or n_features <= 0:
        out["reason"] = f"no usable rows (n={n}, d={n_features})"
        return out
    if len(res) != n:
        # Distinct from the empty case ON PURPOSE. Folding the two together
        # printed "no usable rows (n=2, d=3)" for a length MISMATCH - a
        # message that names neither the mismatch nor the other length, and
        # so sends the reader looking for an empty corpus that is not the
        # problem. Falling through instead would raise inside the zip and
        # be swallowed by the except below as a bare ValueError repr, which
        # is the same silence with a worse string.
        out["reason"] = (f"signal/resolution arrays disagree: "
                         f"len(sig)={n}, len(res)={len(res)}")
        return out
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        # ml.corpus.effective_n, NOT scripts.cohort_eval.cohort_effective_n.
        # The first draft used cohort_effective_n because this file already
        # imports it for the OF-5 sentinel, and it WEDGED THE BATTERY: that
        # function is written for a cohort of ~50 TRIPS and is O(n^3) - an
        # outer loop over spans, a middle loop over ~2n sorted endpoints,
        # and an inner full rescan of every span inside both. Measured on
        # this corpus (19,203 usable spans) that is ~1.4e13 operations; the
        # run was killed after 16 minutes having printed nothing. The
        # canonical route here is the bar-grid one - per-(asset, 5m-bar)
        # concurrency, de Prado AFML ch.4, the same helper gate_truth_report
        # has used since 2026-07-29 - and it is O(total bar-visits): 3.4e6
        # on the same corpus, seven orders of magnitude less. Reusing a
        # neighbour's helper is not free; its complexity is part of its
        # interface.
        from ml.corpus import effective_n as _corpus_effective_n
        rows = [{"signal_ts": float(a), "ts": float(b)}
                for a, b in zip(sig, res, strict=True)]
        # Degenerate rows are KEPT in the concurrency count - a zero-length label
        # still occupies its bar and still crowds its neighbours - but if
        # NONE of them has a real span the corpus carries no duration at all
        # and the reading is meaningless rather than merely small.
        usable = sum(1 for r in rows if r["ts"] > r["signal_ts"])
        if not usable:
            out["reason"] = ("no row has resolution_ts > signal_ts - every "
                             "label span is degenerate, so concurrency is "
                             "undefined")
            return out
        n_eff_raw, _mean_u = _corpus_effective_n(rows)
    except Exception as exc:                               # noqa: BLE001
        out["reason"] = f"{type(exc).__name__}: {exc}"
        return out
    # Clamp to [1, n]: n_eff can never exceed the nominal count, and a
    # zero would make the SE-inflation ratio divide by zero.
    n_eff = max(min(float(n_eff_raw), float(n)), 1.0)
    out.update({"available": True,
                "n_eff": round(n_eff, 1),
                "spans_used": usable,
                "mean_uniqueness": round(n_eff / n, 4),
                "rows_per_feature_nominal": round(n / n_features, 2),
                "rows_per_feature_effective": round(n_eff / n_features, 2),
                "se_inflation": round((n / n_eff) ** 0.5, 2)})
    return out


def load_dataset(min_rows: int | None = None, force_synthetic: bool = False,
                 history_path: "str | None" = None,
                 ml_cfg: "dict | None" = None):
    """min_rows gates when the ML-layer checks (OF-1/2/3/6/7) switch from
    the deterministic synthetic benchmark to real production history. It
    defaults to 10 rows/feature (matching feature_dof_report's own
    rows_per_feature_floor, OF-7) rather than a flat 60 — at 60 rows over
    36 features that's 1.7 rows/feature, so the purged walk-forward and
    shuffle-null checks were switching onto real data before there was
    remotely enough of it to be well-posed (observed live: 87 rows / 36
    features = 2.4 rows/feature failed OF-2 with a degenerate mean_auc=0.0
    and OF-7 with rows_per_feature=2.4, neither a real overfitting signal,
    just data starvation surfaced too early).

    `history_path` (T3.2 review MINOR fix): defaults to
    "outputs/signal_history.csv" (unchanged) when the caller doesn't
    resolve one from config.json's ml.history_path — but main() DOES
    resolve one and passes it, so the corpus this function reads and the
    corpus --epoch-ab's build_epoch_ab_mask scans are always the SAME
    file. Previously this bare HistoryStore() always used the hardcoded
    default while --epoch-ab separately read ml.history_path — harmless
    only because the two happened to agree; an operator repointing
    ml.history_path would have silently desynced them (build_epoch_ab_mask
    scanning the wrong file, every lookup missing, the arm fail-opening
    into a silent no-op instead of erroring).

    `ml_cfg` (2026-08-01 audit H12) is the SAME resolved ml block main()
    already reads once for hist_path/adaptive/select_cfg, extended to the
    loader itself — the corpus era (ml.label_max_bars) and the sample
    weights (ml.sample_weights) must come from the same config read as the
    corpus path or the battery audits a different corpus than it reports.
    Left None it falls back to the historical cwd-relative config.json
    read, so a direct/standalone caller is unchanged.

    Returns (X, y, w, sig, res, source, n_live). `res` (per-row label
    RESOLUTION time) is additive — return_label_times=True changes nothing
    about how X/y/w/sig are computed (ml/history.py's load_training_data
    only branches on it for return SHAPE), so this is not a behavior
    change to OF-1/2/6/7, which never read res. It exists for OF-3's
    opt-in --epoch-ab experiment arm (T3.6a), which needs it to build a
    row mask aligned to X (ml.overfit.build_epoch_ab_mask). On the
    SYNTHETIC benchmark there is no signal_history.csv correspondence, so
    res is None."""
    from ml.features import FEATURE_NAMES
    if min_rows is None:
        min_rows = len(FEATURE_NAMES) * 10
    # same weighting the deployed trainer uses (uniqueness / barrier / skew),
    # so every OF instrument measures the process that actually ships.
    # `ml_cfg` is main()'s ONE resolved config block (see its comment on why
    # hist_path is resolved once); the cwd-relative read below is the
    # standalone/legacy fallback for a direct caller that supplies neither.
    if ml_cfg is None:
        try:
            with open("config.json", encoding="utf-8") as fh:
                ml_cfg = json.load(fh).get("ml", {}) or {}
        except (OSError, ValueError):
            ml_cfg = {}
    # era-gated training exclusion (docs/quant/2026-07-26_era_exclusion.md):
    # OF-3's PBO must measure the SAME corpus the production retrain path
    # (main.py) trains on - the cross-consumer prerequisite that sank the
    # epoch filter (docs/quant/pbo_admission_policy.md) applies here with
    # a sharper edge, since this filter auto-activates on the data alone.
    # store_for_config also threads ml.label_max_bars as max_bars: the bare
    # HistoryStore() default (96) resolved current_era to the legacy
    # "triple_barrier" while main.py:714 resolves "triple_barrier_h24", so
    # the era filter kept production's exact COMPLEMENT and every OF verdict
    # was measured on a corpus the bot never trains on (2026-08-01 audit H12).
    store = store_for_config(ml_cfg, history_path)
    X, y, w, sig, res = load_for_config(store, ml_cfg,
                                        return_label_times=True)
    if not force_synthetic and len(X) >= min_rows and 5 <= y.sum() <= len(y) - 5:
        # live rows: hand the signal-time array down so the OF folds purge
        # by TIME, exactly like the deployed selector (evaluate_and_select).
        # n_live = the load's own clean-pass count, so OF-3's evidence gate
        # mirrors the deployed ladder at the real live-row count.
        n_live = int((store.last_load_stats or {}).get(
            "live_clean", store.source_counts().get("live", 0)))
        return X, y, w, sig, res, f"live history ({len(X)} rows)", n_live
    Xs, ys = synthetic_benchmark()
    # NOT "live rows": len(X) is the LOADED row count (candidate + live,
    # post-filter). Mislabelling it cost a session's diagnosis on
    # 2026-08-08 - the number was read as a live-row count it can never be
    # (the corpus held 305 live rows while this string printed 467).
    reason = ("forced" if force_synthetic
              else f"loaded rows={len(X)} < {min_rows}")
    # synthetic benchmark is uniformly spaced -> row-count purge is exact.
    # n_live = len(Xs): the benchmark validates the FULL selection machinery,
    # so it must not be evidence-gated down to logistic-only.
    return Xs, ys, None, None, None, (
        f"SYNTHETIC benchmark ({reason}) — validating "
        f"machinery, not market"), len(Xs)


# ---------------------------------------------------------------------------
def strategy_plateau(recording: str, quick: bool) -> None:
    """Sweep post-signal parameters over one deterministic recording;
    a robust configuration sits on a plateau, a curve-fit one on a
    spike. Peakiness = |best - mean(neighbors)| / (|best| + eps) on the
    per-axis PnL profile."""
    from scripts.replay import run_replay, set_dotted
    from main import load_config

    base = load_config(str(Path(__file__).resolve().parents[1] /
                           "config.json"))
    base["capital_management"]["starting_capital_usd"] = 10_000
    base["position_sizer"] = dict(base.get("position_sizer", {}),
                                  entry_cooldown_min=0, min_p_win=0.50)
    base["ml"]["cold_start_prior_p"] = 0.62
    base["ml"]["model_path"] = "outputs/_no_model.json"
    base["pretrade"]["min_edge_cost_ratio"] = 0.1

    axes = {
        "position_sizer.min_p_win": [0.50, 0.55, 0.60],
        "profit_taking.chandelier_k": [2.0, 3.0, 4.0],
        "pretrade.min_edge_cost_ratio": [0.1, 0.6, 1.2],
    }
    if quick:
        axes = {"position_sizer.min_p_win": [0.50, 0.55, 0.60]}

    for dotted, values in axes.items():
        pnls, entries = [], []
        for v in values:
            cfg = json.loads(json.dumps(base))
            set_dotted(cfg, dotted, str(v))
            r = run_replay(cfg, recording, quiet=True)
            pnls.append(r["realized_pnl"])
            entries.append(r["entries_filled"])
        spread = max(pnls) - min(pnls)
        if spread < 1e-9:
            info(f"plateau[{dotted}]",
                 f"flat surface (pnl {pnls}, entries {entries}) — "
                 f"parameter inert on this recording")
            continue
        k = int(np.argmax(pnls))
        neigh = [pnls[j] for j in (k - 1, k + 1) if 0 <= j < len(pnls)]
        peak = abs(pnls[k] - float(np.mean(neigh))) / (abs(pnls[k]) + 1e-9)
        check(f"plateau[{dotted}]: best not a knife-edge", peak <= 0.60,
              f"pnl={pnls} peakiness={peak:.2f}")
        # tightening a gate must not mint entries out of thin air
        if dotted in ("position_sizer.min_p_win",
                      "pretrade.min_edge_cost_ratio"):
            check(f"monotone[{dotted}]: stricter gate ⇒ ≤ entries",
                  all(entries[i] >= entries[i + 1]
                      for i in range(len(entries) - 1)),
                  f"entries={entries}")


def make_offline_recording(tmpdir: Path) -> str:
    """Deterministic mock-fed session with forced ETH long signals —
    the same generator smoke [22] proves byte-identical on replay."""
    import shutil
    from data.replay import FeedRecorder
    from main import LiquidityBot, load_config
    from strategies.signal_gates import SignalResult
    from scripts.replay import isolate_qa_singletons
    from scripts.smoke_test import (MockOKX, MockBinanceUS, MockKraken,
                                    qa_redirect_paths)

    # This function CONSTRUCTS a LiquidityBot, so it carries the audit/registry
    # redirect obligation that main() discharges at :825 - and as a LIBRARY
    # entrypoint it did not. pytest is covered by tests/conftest.py:81's
    # autouse fixture; the exposed caller is an ad-hoc script importing this
    # function directly. See scripts/replay.isolate_qa_singletons for the
    # measured contamination.
    isolate_qa_singletons()

    shutil.rmtree(tmpdir, ignore_errors=True)
    tmpdir.mkdir(parents=True)
    sink = str(tmpdir / "session.jsonl")
    cfg = load_config(str(Path(__file__).resolve().parents[1] /
                          "config.json"))
    qa_redirect_paths(cfg, "overfit_rec")   # no writes into production outputs/
    cfg["capital_management"]["starting_capital_usd"] = 10_000
    cfg["system"]["dry_run"] = True
    cfg["sentiment"]["enabled"] = False
    cfg["webdata"]["enabled"] = False
    cfg["moomoo"]["enabled"] = False
    cfg["system"]["state_path"] = str(tmpdir / "state.json")
    cfg["ml"]["model_path"] = str(tmpdir / "none.json")
    cfg["ml"]["history_path"] = str(tmpdir / "hist.csv")
    cfg["position_sizer"] = dict(cfg.get("position_sizer", {}),
                                 entry_cooldown_min=0, min_p_win=0.50)
    cfg["ml"]["cold_start_prior_p"] = 0.62
    cfg["pretrade"]["min_edge_cost_ratio"] = 0.1

    prices = {"ETH": 2000.0, "BTC": 60000.0}
    okx, bnc, krk = MockOKX(prices), MockBinanceUS(prices), \
        MockKraken(prices)
    bot = LiquidityBot(cfg, okx=FeedRecorder(okx, "okx", sink),
                       binanceus=FeedRecorder(bnc, "binanceus", sink),
                       kraken=FeedRecorder(krk, "kraken", sink),
                       resume=False)
    bot.gates.evaluate_asset = lambda base_asset, view: SignalResult(  # type: ignore[assignment]
        symbol=f"{base_asset}/USD", direction="long" if base_asset == "ETH" else None,
        confidence=1.0 if base_asset == "ETH" else 0.0, size=0.0,
        all_confirmed=(base_asset == "ETH"), gates_passed={})
    rng = np.random.default_rng(77)
    t = time.time()
    for _k in range(60):
        for a in prices:
            prices[a] *= float(1 + rng.normal(0, 0.0012) +
                               (0.0008 if a == "ETH" else 0.0))
        bot.cycle_once(t)
        t += bot.poll_sec
    return sink


# ---------------------------------------------------------------------------
def regime_corpus_stats(path) -> dict:
    """Raw-corpus per-stratum stats (candidate/live split, base rate): an
    INDEPENDENT pass over the full signal_history.csv — unlike the OOF
    slice below (which only covers the OOF-tested subset of the deduped/
    purged X), this counts every candidate + live row, answering "how much
    do we even have per regime". Same argmax-of-one-hots stratification as
    the OOF side (regime_stratum_labels), just applied to the raw file
    directly. Missing/unreadable file (OSError) or one that is present but
    unparseable as UTF-8 CSV (ValueError — e.g. a non-UTF8 byte, which
    surfaces as UnicodeDecodeError, a ValueError subclass), or a schema
    without the regime/label columns (e.g. a minimal live-only CI fixture)
    -> {} — reported and skipped, never a crash from this function; same
    (OSError, ValueError) convention as OF-5's own raw CSV scan. The CALLER
    (regime_diagnostic, via main()) additionally wraps the whole diagnostic
    section in its own broad except, so an exception type this function
    doesn't anticipate still can't take down the battery."""
    import csv
    cols = [f"regime_{s}" for s in REGIME_STRATA]
    one_hot, source, label = [], [], []
    try:
        with open(path, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                try:
                    oh = [float(row[c]) for c in cols]
                    lab = float(row["label"])
                except (KeyError, ValueError):
                    continue
                one_hot.append(oh)
                source.append(row.get("source") or "unknown")
                label.append(lab)
    except (OSError, ValueError):
        return {}
    if not one_hot:
        return {}
    strata = regime_stratum_labels(np.array(one_hot))
    source_a = np.array(source, dtype=object)
    label_a = np.array(label, float)
    out = {}
    for s in (*REGIME_STRATA, "unknown"):
        mask = strata == s
        n = int(mask.sum())
        if n == 0:
            continue
        out[s] = {
            "n": n,
            "n_candidate": int((mask & (source_a == "candidate")).sum()),
            "n_live": int((mask & (source_a == "live")).sum()),
            "base_rate": float(label_a[mask].mean()),
        }
    return out


def learning_curve_diagnostic(X: np.ndarray, y: np.ndarray, w, sig, res,
                              on_synthetic: bool) -> None:
    """Standing plateau-vs-climb instrument (operator-approved 2026-07-29;
    Brownlee/MLM's empirical sample-size method), REPORT-ONLY: every line
    goes through info(), never check() — whatever the trend says, it can
    not move PASS_N/FAIL_N or the exit code. Skill vs corpus size on
    expanding chronological prefixes, scored with the same time-purged
    walk-forward the deployed selector uses (ml.overfit.learning_curve).
    gbt only — the ladder's workhorse family; one family bounds runtime.

    The verdict answers ONE question as new-era rows accrue: is the model
    data-starved (CLIMBING — more rows still buy skill) or representation-
    limited (FLAT — more rows alone buy nothing; improve features/labels
    instead)? 2026-07-29 baseline on 1,020 era rows: FLAT at ~0.50 AUC."""
    if on_synthetic:
        info("learning curve", "SYNTHETIC benchmark dataset — corpus-size "
             "trend has no market meaning; skipped")
        return
    if sig is None:
        info("learning curve", "no signal-time array — chronological "
             "prefixes undefined; skipped")
        return
    pts = learning_curve(X, y, w, sig, res,
                         lambda: GradientBoostedStumps(seed=7))
    info("learning curve caveat",
         "each point refits gbt on a chronological PREFIX of the corpus "
         "(time-purged OOF, deployed protocol) — points are the same "
         "statistic across sizes, but none is OF-1's own pooled number")
    for p in pts:
        if p["scored"]:
            info(f"lc[n={p['n']}]",
                 f"oof_n={p['n_oof']} auc={p['auc']:.3f} "
                 f"brier={p['brier']:.4f}")
        else:
            info(f"lc[n={p['n']}]",
                 f"oof_n={p['n_oof']} < {LC_MIN_OOF} — not scored")
    t = learning_curve_trend(pts)
    if t["trend"] == "insufficient":
        info("learning curve trend",
             f"insufficient ({t['n_scored']} scored point(s) < 3) — no "
             f"trend claim")
    elif t["trend"] == "climbing":
        info("learning curve trend",
             f"CLIMBING (delta_auc={t['delta_auc']:+.3f} > "
             f"+{LC_TREND_MARGIN_AUC:.2f}) — data-starved: more rows are "
             f"still buying skill; corpus growth is the highest-leverage "
             f"learning input right now")
    elif t["trend"] == "declining":
        info("learning curve trend FLAG",
             f"DECLINING (delta_auc={t['delta_auc']:+.3f} < "
             f"-{LC_TREND_MARGIN_AUC:.2f}) — later rows are HURTING "
             f"skill: regime/era drift inside the training window "
             f"(check ML-080 mix drift and era_exclusion)")
    else:
        info("learning curve trend",
             f"FLAT (|delta_auc={t['delta_auc']:+.3f}| <= "
             f"{LC_TREND_MARGIN_AUC:.2f}) — representation-limited: more "
             f"rows alone are not buying skill; feature/label quality is "
             f"the binding constraint, not corpus size")


# optional-feed features and their documented neutrals (ml/features.py):
# each imputes its neutral when the feed is dark, and the imputed constant
# is also a legitimate measured value — so at-neutral share is the honest
# LIVENESS meter (Rubin/Little missing-data doctrine: this is the
# report-only precursor to a missingness-indicator column, which costs a
# schema bump and is only earned when measured liveness makes the column
# worth the width — 2026-07-29 defect-category audit).
EXTRAS_NEUTRALS = (("equity_risk_z", 0.0), ("opt_pcr_z", 0.0),
                   ("opt_oi_pcr_z", 0.0), ("dominance_delta", 0.0),
                   ("sent_fear", 0.0), ("fear_greed", 0.5))


def extras_liveness_diagnostic(X: np.ndarray, on_synthetic: bool) -> None:
    """REPORT-ONLY (info() only, never check()): share of corpus rows
    where each optional-feed feature sits exactly at its neutral. ~100%
    = the feed has been dark for the whole corpus (dead column, wasted
    capacity); a falling share = the feed came alive mid-corpus, the
    exact transition where an indicator column starts earning its keep
    (training on a mostly-imputed column with no indicator attenuates
    the true coefficient — Kaufman/Rubin class)."""
    if on_synthetic:
        info("extras liveness", "SYNTHETIC benchmark dataset — feed "
             "liveness has no meaning; skipped")
        return
    from ml.features import FEATURE_NAMES
    for name, neutral in EXTRAS_NEUTRALS:
        if name not in FEATURE_NAMES:
            continue
        col = X[:, FEATURE_NAMES.index(name)]
        share = float((np.abs(col - neutral) < 1e-9).mean())
        note = ""
        if share > 0.95:
            note = " — feed effectively dark corpus-wide (dead column)"
        elif share < 0.5:
            note = (" — feed live for most of the corpus; consider the "
                    "missingness-indicator column (schema bump) if this "
                    "family earns model importance")
        info(f"extras[{name}]",
             f"at-neutral share {share:.1%} (n={len(col)}){note}")


def regime_diagnostic(gaps: dict, X: np.ndarray, y: np.ndarray,
                      on_synthetic: bool, csv_path) -> None:
    """#103 T3 — regime-stratified OOF diagnostic, REPORT-ONLY: every line
    below goes through info(), NEVER check(), so nothing here can move
    PASS_N/FAIL_N or the exit code, whatever the numbers say. Reuses the
    OOF predictions train_test_gap(..., return_oof=True) already produced
    for OF-1's gbt candidate above — no separate fit, same folds, same
    numbers OF-1's pooled gap[gbt] line reports.

    This function itself does not blanket-catch every exception (e.g. a
    renamed FEATURE_NAMES regime column still raises out of the
    FEATURE_NAMES.index(...) call below) — main()'s call site wraps this
    whole call in a broad except so a failure here degrades to a single
    "regime diagnostic skipped" info line rather than crashing the battery.

    Stratum = argmax of the five regime one-hot FEATURE_NAMES columns per
    row (rows with all-zero one-hots -> "unknown"); a stratum's OOF AUC/
    Brier are computed ONLY when its OOF-scored row count clears
    REGIME_MIN_N — thin strata report insufficient evidence, never a noisy
    point estimate. Flags (text only, never gating): a stratum whose OOF
    AUC sits more than REGIME_DEGRADE_MARGIN_AUC below the pooled OOF AUC
    ("materially degrades vs pooled"), and a stratum with fewer than
    REGIME_MIN_N live-sourced rows ("insufficient live coverage" — the
    operator-facing rationale #103 T4's regime-coverage probe term reads
    off of)."""
    from ml.features import FEATURE_NAMES
    g = gaps.get("gbt", {})
    oof_idx, oof_pred = g.get("oof_idx"), g.get("oof_pred")
    if oof_idx is None or not len(oof_idx):
        info("regime diagnostic", "no OOF folds available (OF-1 gbt gap "
                                  "reported 0 folds) — skipped")
        return
    regime_cols = [FEATURE_NAMES.index(f"regime_{s}") for s in REGIME_STRATA]
    one_hot_oof = X[np.asarray(oof_idx, int)][:, regime_cols]
    pooled_auc, pooled_brier = g.get("oof_auc"), g.get("oof_brier")
    oof_stats = regime_stratified_oof(y, oof_idx, oof_pred, one_hot_oof,
                                      pooled_auc=pooled_auc,
                                      pooled_brier=pooled_brier,
                                      min_n=REGIME_MIN_N)
    info("regime diagnostic caveat",
         "stratum auc/brier below are concatenated-OOF over all scored "
         "rows, while the pooled figures they're compared against are "
         "MEAN-OF-FOLDS (OF-1's own convention) — the delta is indicative, "
         "not a rebasing of the same statistic")
    if on_synthetic:
        info("regime diagnostic", "SYNTHETIC benchmark dataset — "
             "candidate/live split & base rate n/a (no signal_history.csv "
             "correspondence); OOF numbers below validate the machinery on "
             "the planted-signal benchmark, not a market read")
        corpus: dict = {}
    else:
        corpus = regime_corpus_stats(csv_path)
        info("regime diagnostic caveat",
             "n= below is a raw signal_history.csv count (candidate+live); "
             "oof_n= is the deduped/purged X actually OOF-scored — two "
             "different counting passes over related but non-identical data")

    for s in (*REGIME_STRATA, "unknown"):
        c = corpus.get(s)
        oof = oof_stats[s]
        if c is None and not on_synthetic:
            info(f"regime[{s}]", "n=0 — absent from corpus")
            continue
        if c is not None:
            info(f"regime[{s}]",
                 f"n={c['n']} (candidate={c['n_candidate']} "
                 f"live={c['n_live']}) base_rate={c['base_rate']:.3f}")
            if c["n_live"] < REGIME_MIN_N:
                info(f"regime[{s}] FLAG",
                     f"insufficient live coverage ({c['n_live']} live < "
                     f"{REGIME_MIN_N}) — operator rationale for #103 T4's "
                     f"regime-coverage probe term")
        if oof["scored"]:
            d_auc = oof["auc"] - (pooled_auc or 0.0)
            d_brier = oof["brier"] - (pooled_brier or 0.0)
            info(f"regime[{s}] oof",
                 f"oof_n={oof['n_oof']} auc={oof['auc']:.3f} "
                 f"(pooled {pooled_auc or 0:.3f}, delta_auc={d_auc:+.3f}) "
                 f"brier={oof['brier']:.4f} (pooled {pooled_brier or 0:.4f}, "
                 f"delta_brier={d_brier:+.4f})")
            if oof["degrade"]:
                info(f"regime[{s}] FLAG",
                     f"OOF materially degrades vs pooled (delta_auc="
                     f"{d_auc:+.3f}, worse than the "
                     f"-{REGIME_DEGRADE_MARGIN_AUC:.2f} margin OF-1 uses "
                     f"for its own train/OOF gap)")
        elif oof["n_oof"] > 0 or c is not None:
            info(f"regime[{s}] oof",
                 f"oof_n={oof['n_oof']} < {REGIME_MIN_N} — insufficient "
                 f"OOF evidence, not scored")


def resolve_dsr_trials(configured: int, ledger_path) -> tuple:
    """TRIALS-1 ratchet (spec 2026-08-27 [SEV-2]): the measured trial
    ledger can only DEEPEN the DSR deflation, never relax it below the
    configured floor. Absent/invalid ledger ≡ legacy behavior, loudly.
    Returns (n_trials_eff, source_line) — main() prints the line so
    every OF-5 green names the world it ran in."""
    from pathlib import Path as _P

    from scripts.trial_ledger import measured_trials, read_ledger
    p = _P(ledger_path)
    if not p.exists():
        return configured, (f"OF-5 trials: assumed N={configured} "
                            f"(no ledger at {p}; var=1/n null fallback)")
    try:
        m = measured_trials(read_ledger(p))
    except (OSError, ValueError) as e:
        return configured, (f"OF-5 trials: ledger INVALID or unreadable "
                            f"({e}); assumed N={configured}, "
                            f"var=1/n null fallback")
    measured = int(m["n_trials"])
    if measured > configured:
        return measured, (f"OF-5 trials: measured N={measured} from ledger "
                          f"({m['by_source']}); var=1/n null fallback (v0.1)")
    return configured, (f"OF-5 trials: measured N={measured} < configured; "
                        f"ratchet holds configured {configured}")


def dsr_gate_reachable(n_trials: int, gate: float = 0.90,
                       n_returns: int = 30) -> tuple:
    """Is OF-5's `dsr >= gate` ATTAINABLE AT ALL at this trial count?

    IT WAS NOT, AND THE CAUSE IS NOW FIXED AT SOURCE (2026-09-11). The
    unidentified nuisance parameter `var_trial_sr` - the dispersion of SR
    ACROSS trials, which no ledger records - used to fall back to
    `max(sr_observed**2, 0.01)`. That set sqrt(V) = |SR|, making the rejection
    threshold PROPORTIONAL to the statistic under test:

        sr0 = k(N) * |SR|,   k(N) crossing 1.0 between N=3 and N=4

    so for every N >= 4, sr0 >= |SR| for ANY sample, z <= 0, DSR < 0.5 < gate.
    An exhaustive sweep of 518,616 (SR, n, skew, kurtosis) combinations found 0
    passing and a maximum attainable DSR of 0.4262 (2026-08-31). Worse, it was
    INVERTED - a larger observed SR produced a SMALLER DSR.

    `ml.overfit.deflated_sharpe` now falls back to the SAMPLING VARIANCE of a
    Sharpe estimate under H0, Var(SR_hat) -> 1/n, so sr0 = k(N)/sqrt(n) no
    longer depends on the statistic. The gate is reachable, monotone in SR, and
    the 0.90 bar is UNCHANGED - it became meetable by evidence, not lowered.

    Returns (reachable, k, sr0). `k` is the pure trial-count multiplier,
    obtained by passing var_trial_sr=1.0 so sqrt(V)=1 - the old code inferred
    it by passing SR=1.0, a trick that only worked because of the very fallback
    being replaced, and that would now silently return sr0 mislabelled as k.
    """
    import math

    from ml.overfit import deflated_sharpe
    N = max(int(n_trials), 1)
    n = max(int(n_returns), 3)
    k = deflated_sharpe(1.0, 1000, n_trials=N,
                        var_trial_sr=1.0)["sr0_threshold"]
    sr0 = deflated_sharpe(0.0, n, n_trials=N)["sr0_threshold"]
    # With sr0 independent of SR, some attainable SR clears it: reachable.
    # Guard the pathological case anyway rather than asserting it.
    probe = deflated_sharpe(sr0 + 10.0 / math.sqrt(n), n, n_trials=N)["dsr"]
    return (probe is not None and probe >= gate), k, sr0


def dsr_verdict(name: str, dsr: float, detail: str, reachable: bool,
                k: float, n_trials: int) -> str:
    """Grade OF-5 — or ABSTAIN when its acceptance region is empty.

    THE BOMB THIS DEFUSES (found 2026-09-10, two conviction trades from
    detonating). OF-5 arms at 30 conviction-marked trades; the corpus stood
    at 28. Once armed it calls check(dsr >= 0.90) — and dsr_gate_reachable()
    proves that for every n_trials >= 4 the threshold sr0 = k*|SR| with
    k >= 1, so dsr < 0.5 < 0.90 for EVERY possible sample. The gate would
    have armed and then failed forever, turning CLAUDE.md's definition of
    done permanently red on a predicate no code change to the STRATEGY could
    ever satisfy.

    WHY ABSTAIN IS THE SOUND ANSWER, AND WHY THIS IS NOT LOWERING A FLOOR.
    A predicate that returns FAIL for every input in its domain carries
    exactly as much information as one that returns PASS for every input:
    none. It is the vacuous test this repo already refuses, wearing the
    opposite sign. The n=30 conviction floor is UNCHANGED. The dsr >= 0.90
    threshold is UNCHANGED. The statistic is still computed and still
    printed. The only thing that changes is that an UNSATISFIABLE gate stops
    rendering a verdict it cannot support — which is what CLAUDE.md means by
    treating what a gate was meant to prove as UNPROVEN rather than proven
    either way.

    THE CAUSE IS NOW FIXED, SO THIS GRADES AGAIN (2026-09-11, operator
    decision: "replace the threshold"). The abstention was the right answer to
    an unsatisfiable predicate, but it left a PRE-REGISTERED rung out of the
    exit code, which is a different and worse problem - red-team OBJ-15. The
    repair went to the root: `ml.overfit.deflated_sharpe`'s unidentified
    var_trial_sr no longer falls back to max(SR**2, 0.01) - which made sr0
    proportional to the statistic under test, and was INVERTED besides (at
    n=30, N=7 it scored SR 0.20 -> DSR 0.340 but SR 0.75 -> 0.084) - but to
    the sampling variance of a Sharpe estimate under H0, Var(SR_hat) -> 1/n.

    sr0 = k(N)/sqrt(n) is now independent of the statistic, reachability
    recomputes to True, and this branch grades normally with the 0.90 bar and
    the n=30 floor BOTH UNCHANGED. At n=30, N=7 the gate now needs a per-trip
    Sharpe near 0.5-0.75 to pass: demanding, attainable, and monotone in the
    right direction.

    SELF-HEALING BY CONSTRUCTION, and it healed. Reachability is recomputed
    every run from dsr_gate_reachable(), never from a date or a remembered
    constant, so this re-armed itself the moment the fallback changed - no
    edit in this function. The abstention path stays as the guard it was: if a
    future change makes the acceptance region empty again, OF-5 says so rather
    than failing forever. A measured per-trial SR dispersion still beats the
    null substitute; pass var_trial_sr explicitly when a trial ledger records
    one.

    Returns "graded" or "abstained" so callers and tests can assert which.
    """
    if reachable:
        check(name, (dsr or 0.0) >= 0.90, detail)
        return "graded"
    info(f"{name} [ABSTAINED - gate unsatisfiable]",
         f"{detail} | NOT GRADED: at n_trials={n_trials} the threshold is "
         f"sr0={k:.3f}x|SR|, so dsr>=0.90 is attainable for NO sample and a "
         f"FAIL here would carry no information. Floors and thresholds are "
         f"UNCHANGED. Repair: record per-trial SR so var_trial_sr is MEASURED "
         f"rather than the SR^2 fallback; this arms itself when that lands.")
    return "abstained"


# ---------------------------------------------------------------------------
def main() -> int:
    # OF-4 replays construct full bots that audit their dispositions and
    # record model lifecycle events; keep synthetic records out of the
    # production trail and registry ledger
    from core.audit import configure_audit
    from ml.registry import configure_registry
    configure_audit(Path(tempfile.gettempdir()) / "liqbot_overfit_audit.jsonl")
    configure_registry(Path(tempfile.gettempdir()) / "liqbot_overfit_models")
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--recording", default="",
                    help="existing session.jsonl to sweep; default: "
                         "generate a deterministic offline one")
    ap.add_argument("--force-synthetic", action="store_true",
                    help="always use the deterministic synthetic benchmark "
                         "for the ML layer, even if live history clears "
                         "min_rows — for a CI-bound run that must not "
                         "depend on ambient production telemetry state")
    ap.add_argument("--report-path", default="outputs/overfit_report.md",
                    help="where to write the markdown report — override "
                         "for a CI-bound run so it doesn't clobber a human "
                         "operator's last real audit")
    ap.add_argument("--schema-ab", default="", metavar="PRUNEFILE",
                    help="opt-in, report-only OF-3 experiment arm (T3.2): "
                         "adds a gbt_d3_lr05_schema_ab config trained "
                         "without the columns in PRUNEFILE's always_dead "
                         "list (a scripts/feature_stability.py dated "
                         "snapshot) - regime one-hots stay exempt. Never "
                         "gates; adds INFO lines only. A malformed "
                         "PRUNEFILE fails loudly (non-zero exit).")
    ap.add_argument("--epoch-ab", action="store_true",
                    help="opt-in, report-only OF-3 experiment arm (T3.6a): "
                         "adds a gbt_d3_lr05_epoch_ab config trained on "
                         "live rows + candidate rows resolved at/after "
                         "ml.epoch.candidate_cutoff_ts only. No-op on the "
                         "SYNTHETIC benchmark (no signal_history.csv "
                         "correspondence). Never gates; adds INFO lines "
                         "only.")
    args = ap.parse_args()
    logging.basicConfig(level=logging.WARNING)
    t0 = time.time()
    print("liquiditybot overfit audit\n" + "=" * 42)

    # ---- ML layer -----------------------------------------------------
    # T3.2 review MINOR fix: load config ONCE, here, before load_dataset() —
    # hist_path (the corpus load_dataset()'s HistoryStore reads) and the
    # --epoch-ab block's hist_path used to be derived independently (this
    # config read happened AFTER load_dataset(), which called the bare
    # HistoryStore() default instead). They agreed only because config.json
    # happens to match the hardcoded default today; an operator repointing
    # ml.history_path would silently desync them — build_epoch_ab_mask would
    # scan the WRONG file, every lookup would miss, and the fail-open default
    # would quietly turn the arm into a no-op instead of erroring. Deriving
    # both from this ONE resolved `hist_path` makes that divergence
    # structurally impossible.
    inc_adaptive, adaptive_cfg, select_cfg = False, None, None
    _ml_cfg: dict = {}
    try:
        from main import load_config
        _ml_cfg = load_config(str(Path(__file__).resolve().parents[1]
                              / "config.json")).get("ml", {}) or {}
        _ag = _ml_cfg.get("adaptive_gbt", {}) or {}
        inc_adaptive = bool(_ag.get("enabled", False))
        adaptive_cfg = _ag if inc_adaptive else None
        select_cfg = _ml_cfg.get("model_selection", {}) or None
        # Active-learning phase flag, derived ONCE here and reused by
        # OF-1, OF-7 and OF-5 below. It used to be re-derived inside the
        # DSR block from a second config read; two derivations of one
        # predicate is the drift hazard this repo keeps paying for, so
        # there is now exactly one.
        _explore_on = bool((_ml_cfg.get("exploration") or {})
                           .get("enabled", False))
    except Exception:                                    # noqa: BLE001
        inc_adaptive, adaptive_cfg, select_cfg, _ml_cfg = (
            False, None, None, {})                        # fail safe
        _explore_on = False              # unreadable config: FULL gate
    hist_path = _ml_cfg.get("history_path", "outputs/signal_history.csv")

    X, y, w, sig, res, source, n_live = load_dataset(
        force_synthetic=args.force_synthetic, history_path=hist_path,
        ml_cfg=_ml_cfg)
    on_synthetic = source.startswith("SYNTHETIC")
    print(f"[OF-1] train/OOF gap  ({source})")
    # return_oof=True: purely additive (see train_test_gap docstring) - it
    # only adds 'oof_idx'/'oof_pred' keys the gap[...] checks below never
    # read, so OF-1's verdicts are unaffected. Consumed by the regime-
    # stratified diagnostic at the end of main() so it reuses gbt's OOF
    # predictions instead of retraining separately.
    # res=res: the DEPLOYED selector purges on measured label RESOLUTION
    # time (main.py:5734 -> evaluate_and_select(res=res)), a branch that
    # ignores label_span entirely — which is why OF-1's label_span literal
    # drifting from ml.label_max_bars is NOT fixed by wiring the config
    # knob in (span-24 UNDER-purges every fold vs the deployed sizes; see
    # train_test_gap's docstring for the measured fold widths). Threading
    # res is what makes OF-1 measure the process that actually ships.
    gaps = train_test_gap(X, y, sample_weight=w,
                          n_splits=3 if args.quick else 5, sig=sig,
                          return_oof=True, res=res)
    # OF-1 GATING POLICY (operator adjudication 2026-08-09, following the
    # OF-5/DSR precedent above it in this file's own header).
    #
    # The THRESHOLD IS UNCHANGED (0.12) and the numbers are always printed.
    # What is scoped is what the number BLOCKS. While dry-run active
    # learning is on, the corpus is dominated by EV-mixed probe/candidate
    # rows acquired to BUY labels (PT-050) - the identical reason DSR is
    # informational during exploration - so a train/OOF gap measured on it
    # grades the acquisition phase, not the generalization of a model any
    # trade actually depends on. Model TRUST is enforced elsewhere and is
    # untouched by this: the selection ladder's evidence floors
    # (ml.model_selection.min_live_rows) refuse the higher-capacity
    # families outright at this row count, and the ML governor grades the
    # deployed model on REALIZED outcomes and kills it (use_model=False)
    # when it is confidently wrong. This battery stage gates CODE deploys;
    # holding a code-safety fix hostage to a data-starved corpus conflates
    # model readiness with code correctness.
    #
    # Fail-CLOSED and self-terminating, exactly like DSR: an unreadable
    # config leaves _explore_on False (full gate), the SYNTHETIC benchmark
    # always keeps the hard gate because there OF-1 validates the
    # instrument rather than the corpus, and the gate re-arms by itself
    # the moment ml.exploration.enabled goes false - no stamp to clear, no
    # operator memory required.
    _of1_soft = gate_is_informational(_explore_on, on_synthetic)
    for name, g in gaps.items():
        if not g.get("folds"):
            info(f"gap[{name}]", "no viable folds")
            continue
        detail = (f"train_auc={g['train_auc']:.3f} "
                  f"oof_auc={g['oof_auc']:.3f} gap={g['gap_auc']:+.3f}")
        if _of1_soft:
            verdict = "WITHIN" if g["gap_auc"] <= 0.12 else "OVER"
            info(f"gap[{name}]",
                 f"INFORMATIONAL ({verdict} the 0.12 memorization band) - "
                 f"{detail}; exploration is ON so the corpus is EV-mixed "
                 f"by design (PT-050) - model trust stays enforced by the "
                 f"selection evidence floors + the live governor; this "
                 f"gate arms when ml.exploration.enabled is false")
        else:
            check(f"gap[{name}]: OOF gap within memorization band",
                  g["gap_auc"] <= 0.12, detail)

    # ---- OF-1b: NULL-MODEL FLOOR (2026-07-31 era-deadlock debate, item
    # G). A model that scores WORSE than a constant predicting the corpus
    # base rate has negative skill - it is not merely weak, it is
    # anti-informative, and sizing on its p(win) is worse than sizing on
    # the base rate. Both debate arms measured exactly this and NOTHING in
    # the battery said so: deployed logistic Brier 0.2736 vs 0.1936 for
    # the constant; the gbt an unlock would buy, 0.2355 vs 0.1959. The
    # base rate is the honest floor every rung must clear before "which
    # family wins" is even a meaningful question.
    # REPORT-ONLY by design: it must not gate the battery on the very
    # condition the operator is trying to fix (a gate here would block
    # every deploy while the model is cold), but it must be impossible to
    # miss in the report.
    for name, g in gaps.items():
        oof_idx, oof_pred = g.get("oof_idx"), g.get("oof_pred")
        if oof_idx is None or oof_pred is None or not len(oof_idx):
            continue
        y_oof = np.asarray(y)[np.asarray(oof_idx)]
        p_hat = np.asarray(oof_pred, float)
        base = float(y_oof.mean())
        brier_model = float(np.mean((p_hat - y_oof) ** 2))
        brier_null = float(np.mean((base - y_oof) ** 2))
        beats = brier_model < brier_null
        info(f"null-floor[{name}]",
             f"OOF Brier {brier_model:.4f} vs base-rate constant "
             f"{brier_null:.4f} (base={base:.3f}, n={len(y_oof)}) — "
             + ("BEATS the null" if beats else
                "LOSES TO THE NULL: negative skill, sizing on this "
                "model's p(win) is worse than sizing on the base rate"))

    print("[OF-2] shuffled-label leakage null")
    sh = shuffled_label_check(X, y, repeats=2 if args.quick else 3, sig=sig)
    check("shuffle: destroyed labels learn nothing OOF", sh.get("ok", False),
          f"mean_auc={sh.get('mean_auc', 0):.3f} z={sh.get('z', 99):.1f} "
          f"(limit {sh.get('z_limit')})")

    print("[OF-3] model-space PBO (CSCV)")
    # OF-3 must measure the DEPLOYED selection space. When the opt-in
    # adaptive_gbt rung is enabled in config it is live in walkforward's
    # ladder, so it enters the PBO space too; otherwise the space is the
    # historical default. Config unreadable -> default space (fail safe).
    # (inc_adaptive/adaptive_cfg/select_cfg/_ml_cfg/hist_path were resolved
    # once, above, before load_dataset() — see that comment for why.)
    # n_live (from load_dataset) drives the SAME evidence gate the deployed
    # ladder uses, so the measured PBO space is byte-for-byte the space the
    # bot actually selects from at the current ground-truth count.
    if inc_adaptive:
        info("pbo space", "ml.adaptive_gbt.enabled=true — the adaptive "
                          "rung is IN the measured selection space")

    # ---- T3.2/T3.6a: opt-in, report-only PBO experiment arms -------------
    # Both default to no-op (schema_ab_cols/epoch_ab_mask stay None), which
    # is exactly model_space_pbo's byte-identity baseline — neither flag
    # given ⇒ zero footprint on the measured space or the report below.
    schema_ab_cols = None
    if args.schema_ab:
        from ml.features import FEATURE_NAMES as _FN
        from ml.overfit import load_schema_ab_cols
        # deliberately UNCAUGHT: a malformed --schema-ab prunefile (missing
        # always_dead, or one naming a feature outside FEATURE_NAMES) must
        # fail loudly — a clear error message and a non-zero exit — never
        # silently run the rest of the audit on a wrong/empty prune set.
        schema_ab_cols = load_schema_ab_cols(args.schema_ab, _FN)
        info("schema-ab", f"{args.schema_ab}: pruned "
             f"{len(_FN) - len(schema_ab_cols)}/{len(_FN)} column(s) for "
             f"the gbt_d3_lr05_schema_ab arm (regime one-hots exempt)")

    epoch_ab_mask = None
    if args.epoch_ab:
        if source.startswith("SYNTHETIC"):
            info("epoch-ab", "skipped — SYNTHETIC benchmark has no "
                             "signal_history.csv source/ts correspondence")
        else:
            cutoff_ts = (_ml_cfg.get("epoch", {}) or {}).get(
                "candidate_cutoff_ts")
            if cutoff_ts is None:
                info("epoch-ab", "skipped — ml.epoch.candidate_cutoff_ts "
                                 "not configured")
            else:
                from ml.overfit import build_epoch_ab_mask
                # SAME hist_path load_dataset() built its HistoryStore from
                # (resolved once, above) — never re-derived, so this can
                # never scan a different file than X/y/sig/res came from.
                epoch_ab_mask = build_epoch_ab_mask(hist_path, sig, res,
                                                    float(cutoff_ts))
                info("epoch-ab",
                     f"cutoff_ts={float(cutoff_ts):.0f} - "
                     f"{int(epoch_ab_mask.sum())}/{len(epoch_ab_mask)} rows "
                     f"kept for the gbt_d3_lr05_epoch_ab arm's training "
                     f"({int((~epoch_ab_mask).sum())} pre-cutoff candidate "
                     f"row(s) excluded from TRAINING only — scoring still "
                     f"uses the full shared OOF rows)")

    # sample_weight=w / res=res: OF-3 certifies the DEPLOYED selection rule,
    # so its per-arm fits must use the deployed trainer's de Prado weights
    # (ml/walkforward.py:302-303) and its folds the deployed purge basis.
    # Fitting uniformly perturbed per-family Brier by 0.0012-0.0121 against
    # a BRIER_MARGIN of 0.002 on the live corpus — a conscious CSCV
    # re-baseline per docs/quant/pbo_admission_policy.md rule 2, NOT a
    # widened gate. Weight the FIT, not the metric: M stays unweighted
    # because deployed selection ranks on unweighted Brier.
    pb = model_space_pbo(X, y, n_splits=3 if args.quick else 5,
                         n_blocks=6 if args.quick else 8, sig=sig,
                         include_adaptive=inc_adaptive,
                         adaptive_cfg=adaptive_cfg,
                         n_live=n_live, select_cfg=select_cfg,
                         schema_ab_cols=schema_ab_cols,
                         epoch_ab_mask=epoch_ab_mask,
                         sample_weight=w, res=res)
    if pb.get("pbo") is None:
        info("pbo", pb.get("reason", "n/a") +
             (f" (space={pb.get('configs')})" if pb.get("configs") else ""))
    else:
        check("pbo: DEPLOYED selection (simplicity ladder) not "
              "dominated by luck", pb["pbo"] <= 0.5,
              f"pbo={pb['pbo']:.2f} over {pb['n_configs']} configs / "
              f"{pb['n_combos']} splits (mean winner: {pb.get('is_winner')})")
        info("pbo argmax stress",
             f"raw argmax selection pbo={pb.get('pbo_argmax', float('nan')):.2f}"
             " — the worst-case rule the ladder exists to avoid; gate is on"
             " the rule the bot actually runs")
        if pb.get("edge_purged_frac") is not None:
            # visibility for the Debate-1 item E purge: an inert purge
            # (frac ~ 0 on an overlapping corpus) or a degenerate one
            # (combos dropped) must be readable in the report
            info("pbo edge purge",
                 f"label-window purge active: edge_purged_frac="
                 f"{pb['edge_purged_frac']:.3f}, combos_dropped="
                 f"{pb.get('combos_dropped_purged', 0)}")
        if pb["pbo"] > 0.2:
            info("pbo note", "0.2 < pbo <= 0.5: selection has luck in it — "
                             "expected at this sample size; keep the "
                             "simplicity-ladder margin")
    # T3.2/T3.6a: experiment-arm results are always INFO, never check() —
    # they report on a caller-widened measurement space, they never gate.
    for arm_name, exp in (pb.get("experiments") or {}).items():
        pbo_txt = f"{exp['pbo']:.2f}" if exp.get("pbo") is not None else "n/a"
        info(f"pbo experiment[{arm_name}]",
             f"base={exp['base']} pbo={pbo_txt} "
             f"ladder_winner={exp['ladder_winner']} "
             f"mean_winner={exp['mean_winner']}")
    for note in pb.get("experiment_notes") or []:
        info("pbo experiment note", note)
    for note in pb.get("degraded_folds") or []:
        info("pbo experiment degraded fold", note)

    print("[OF-6] purge-leakage probe")
    lk = purge_leakage_probe()
    check("purge: never manufactures out-of-sample edge",
          lk["purge_does_not_inflate"],
          f"unpurged={lk['unpurged_oof_auc']:.3f} "
          f"purged={lk['purged_oof_auc']:.3f} leak_closed={lk['leak_closed']:+.3f}")
    info("purge note", "expanding-window design keeps boundary leak ~0 by "
                       "construction; shuffle-null [OF-2] is the leak gate")

    print("[OF-7] feature degrees-of-freedom")
    from ml.features import FEATURE_NAMES
    # sample_weight=w: the dead-feature read must be taken off the model the
    # deployed trainer fits (weighted), not an unweighted stand-in - same
    # "measure the process that ships" contract as OF-3 above.
    dof = feature_dof_report(X, y, FEATURE_NAMES,
                             label_span=32 if args.quick else 96, sig=sig,
                             sample_weight=w)
    check("dof: not starved (>=10 rows per feature)", not dof["starved"],
          f"rows/feature={dof['rows_per_feature']:.1f} "
          f"({dof['n_rows']} rows / {dof['n_features']} features)")
    # The gate above is NOMINAL and stays that way (see dof_effective_n's
    # docstring for why re-gating would be a silent re-registration). This
    # line says how big that green actually is.
    _dn = dof_effective_n(sig, res, dof["n_features"],
                          label="synthetic" if on_synthetic else "live")
    if _dn.get("available"):
        _synth = (" — SYNTHETIC corpus: this qualifies the machinery, not "
                  "the market" if on_synthetic else "")
        info("dof EFFECTIVE n (report-only; the gate above reads NOMINAL)",
             f"rows/feature nominal={_dn['rows_per_feature_nominal']:.2f} vs "
             f"effective={_dn['rows_per_feature_effective']:.2f} "
             f"(n={_dn['n']} -> n_eff={_dn['n_eff']}, mean uniqueness "
             f"{_dn['mean_uniqueness']:.3f}); an SE on nominal n is "
             f"optimistic by x{_dn['se_inflation']:.2f}. Route: "
             f"{_dn['route']} — the floor of 10 is NOT applied to it and "
             f"nothing here moves PASS/FAIL." + _synth)
    else:
        info("dof EFFECTIVE n",
             f"UNAVAILABLE ({_dn.get('reason', 'unknown')}) — OF-7's "
             f"rows/feature above is NOMINAL and unqualified")
    # SCAN COVERAGE (2026-08-31): dead_feature_frac is only evidence about
    # features the fitted GBT actually consulted. Measured on the live
    # corpus: early stopping left the fit consulting 15/64 features across
    # a full seed sweep, and 41 of 48 "always dead" entries were features
    # NO fit ever split on - a blind model, not dead features. info(), not
    # check(): coverage qualifies the reading, it is not itself a gate.
    if not dof.get("scan_informative", True):
        info("dof COVERAGE",
             f"dead-feature scan UNINFORMATIVE: the fitted GBT consulted "
             f"only {dof.get('features_consulted', 0)}/{dof['n_features']} "
             f"features ({dof.get('dead_but_never_consulted', 0)} of the "
             f"{len(dof['dead_features'])} 'dead' were never split on at "
             f"all). Read dead_feature_frac as the model's blindness, not "
             f"the features' deadness; the clustered-MDA report "
             f"(scripts/interpret_report.py) is the honest ranking.")
    else:
        info("dof coverage",
             f"fitted GBT consulted {dof.get('features_consulted', 0)}/"
             f"{dof['n_features']} features - dead read taken on a model "
             f"that actually looked")
    # dead-feature semantics depend on the dataset: the synthetic
    # benchmark plants signal in ~6 of 36 features BY CONSTRUCTION, so a
    # high dead fraction there is expected and says nothing about
    # production. It's a hard check only on real live history; on the
    # synthetic set it's reported for machinery validation. The models
    # already regularize against dead weight (GBT colsample + L2 + gain
    # importance, logistic L2), and OF-2 confirms none is exploited.
    dead_detail = (f"dead_frac={dof['dead_feature_frac']:.2f} "
                   f"({len(dof['dead_features'])} near-zero-importance "
                   f"features)")
    if on_synthetic:
        info("dof: dead-feature fraction (synthetic — informational)",
             dead_detail + " — expected: benchmark plants signal in ~6/36")
    elif gate_is_informational(_explore_on, on_synthetic):
        # Same adjudication as OF-1 above, same threshold (0.55), same
        # self-terminating condition, via the SAME predicate so the two
        # gates cannot drift into disagreeing about the phase. A dead-feature fraction on a corpus
        # this size is the DoF budget restating itself (2026-08-08:
        # hundreds of labels fund ~2-5 effectively independent features
        # against 64 present), which is a FEATURE-COUNT decision - the
        # schema-AB prune experiment - not a code-deploy verdict.
        info("dof: dead-feature fraction (exploration — informational)",
             dead_detail + " — arms when ml.exploration.enabled is false; "
             "reduce the schema (prune experiment) or grow the corpus")
    else:
        check("dof: dead-feature fraction under 55% (live data)",
              dof["dead_feature_frac"] < 0.55, dead_detail)
    if dof["dead_features"]:
        info("dof note", f"low/zero-importance: {dof['dead_features'][:6]}"
                         + (" ..." if len(dof["dead_features"]) > 6 else ""))

    # ---- strategy layer -------------------------------------------------
    print("[OF-4] strategy parameter plateau (deterministic replay)")
    try:
        rec = args.recording or make_offline_recording(
            # QA intermediate (~1MB replay session): temp dir, not the
            # production telemetry directory
            Path(tempfile.gettempdir()) / "liqbot_overfit_rec")
        strategy_plateau(rec, args.quick)
    except Exception as e:
        check("plateau: replay harness ran", False, f"{e!r}")

    # ---- live-results layer ---------------------------------------------
    print("[OF-5] deflated Sharpe (live trades)")
    # SAME hist_path the ML layer above loaded from (resolved once at the
    # top of main()). This live-results layer was left on the bare
    # HistoryStore() default — the exact desync the ML layer already fixed
    # for load_dataset. Dormant while config matches the default, but after
    # a corpus rotation/repoint OF-5 emits a confident PASS/FAIL DSR verdict
    # on the WRONG sample and the report header never prints the path it
    # read. hist_path stays relative when config says so, preserving the
    # cwd-relative resolution tests/test_overfit_check_ci.py:39-44 depends
    # on (it pins OF-5's DEFERRED branch by running from an empty cwd).
    store = store_for_config(_ml_cfg, hist_path)
    live_rows = []
    try:
        import csv
        with open(store.path, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if row.get("source") == "live" and row.get("net_pnl_usd"):
                    live_rows.append({"net_pnl_usd": row["net_pnl_usd"],
                                      "probe": row.get("probe", ""),
                                      # ts: dsr_sample_span (corpus width).
                                      # position_id: the fill-ledger join the
                                      # deployed-era sentinel needs. Neither
                                      # reaches the graded sample - OF-5 stays
                                      # pooled per the 2026-09-11 decision.
                                      "ts": row.get("ts", ""),
                                      "position_id": row.get("position_id",
                                                             "")})
    except (OSError, ValueError):
        pass
    conviction, mixed = split_dsr_samples(live_rows)
    try:
        _cfg_p = Path(__file__).resolve().parents[1] / "config.json"
        _ml_cfg = (json.loads(_cfg_p.read_text(encoding="utf-8"))
                   .get("ml") or {})
        # _explore_on is NOT re-derived here: it is resolved once at the
        # top of main() (fail-closed) and shared by OF-1/OF-5/OF-7, so the
        # three gates can never disagree about which phase they are in.
        # Debate-1 item A: the DSR trials count is a decision-path knob
        # (Harvey-Liu multiple-testing deflation) — config-lifted with the
        # identical default; config_guard bounds it and WARNs below the
        # shipped baseline.
        _dsr_trials = int((_ml_cfg.get("overfit") or {})
                          .get("dsr_n_trials", 7))
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        _dsr_trials = 7

    _dsr_trials, _dsr_src = resolve_dsr_trials(
        _dsr_trials, Path(__file__).resolve().parents[1] /
        "outputs" / "trial_ledger.csv")
    info(_dsr_src)
    _reach, _k, _ = dsr_gate_reachable(_dsr_trials)
    if not _reach:
        info("dsr REACHABILITY",
             f"UNPASSABLE at N={_dsr_trials}: the var_trial_sr=SR^2 fallback "
             f"makes sr0 = {_k:.3f}x|SR|, so the rejection threshold scales "
             f"with the statistic and dsr>=0.90 is attainable for NO sample "
             f"(exhaustive sweep 2026-08-31: 0/518616 combinations pass at "
             f"N=7, max dsr 0.4262). This gate cannot produce a green — read "
             f"any OF-5 line below as INERT, not as evidence. Repair needs a "
             f"var_trial_sr MEASURED from per-trial SR (trial_ledger v0.1 "
             f"records none), never a threshold move.")

    def _dsr_of(r):
        # UNIT NOTE (2026-07-29 audit): r is per-trade USD PnL, so this is
        # a NOTIONAL-WEIGHTED Sharpe — identical to return-based Sharpe
        # only while per-trade notional is ~constant (true today: probes
        # and conviction tickets are floor-dominated ~$10-40). The history
        # schema carries no entry_usd, so a true per-trade-return DSR
        # needs a schema addition first; revisit when sizing starts
        # varying materially (Kelly off the floor).
        # ddof=1 (Bessel): population moments inflated SR by sqrt(n/(n-1))
        # (+1.7% at n=30) in the ANTI-conservative direction on the hard
        # DSR gate (2026-07-29 defect-category audit; CGL 1983 / Higham).
        sd = float(r.std(ddof=1)) + 1e-12
        sr = float(r.mean()) / sd
        d = deflated_sharpe(sr, len(r),
                            skew=float(((r - r.mean()) ** 3).mean() / sd ** 3),
                            kurtosis=float(((r - r.mean()) ** 4).mean()
                                           / sd ** 4),
                            n_trials=_dsr_trials)
        return d, sr

    # PT-050 probes deliberately bypass the profit-EV gate to buy labels, so
    # DSR on the mixed sample measures tuition, not the deployed strategy.
    # Since 2026-07-20 every position carries is_probe -> the 'probe' column,
    # so the gate can grade the CONVICTION-ONLY sample even while exploration
    # is running. Pre-marker rows ('' = unknown) never count as conviction.
    if len(conviction) >= 30:
        r = np.array(conviction)
        d, sr = _dsr_of(r)
        # THE LABEL USED TO READ "P(true SR > 0)" AND THAT WAS FALSE
        # (2026-09-11). dsr is P(true SR > sr0_threshold), and sr0 is the
        # expected max Sharpe under the null across N trials - strictly
        # positive. The sign question is psr_zero, printed below, and it is
        # NOT what this gate grades. Conflating them let "dsr=0.006" read as
        # "0.6% chance of positive edge" when it meant "0.6% chance of
        # beating the best of 7 tries".
        dsr_verdict("dsr: P(true SR > sr0) on conviction-only sample",
                    d.get("dsr") or 0.0,
                    f"dsr={d.get('dsr'):.3f} sr={sr:.2f} n={len(r)} "
                    f"sr0={d.get('sr0_threshold'):.3f} "
                    f"(probes excluded: {len(mixed) - len(conviction)})",
                    _reach, _k, _dsr_trials)
        info("dsr READ THIS WITH THE VERDICT",
             dsr_disclosure(d, live_rows))
    elif _explore_on:
        note = ""
        if len(mixed) >= 30:
            d, sr = _dsr_of(np.array(mixed))
            note = f" mixed-sample dsr={d.get('dsr'):.3f} sr={sr:.2f};"
        info("dsr", f"DEFERRED — {len(conviction)} conviction-marked live "
                    f"trades < 30 (mixed n={len(mixed)});{note} probes are "
                    f"EV-mixed by design (PT-050); gate arms as conviction "
                    f"labels accrue")
    elif len(mixed) < 30:
        info("dsr", f"DEFERRED — {len(mixed)} live labeled trades < 30; "
                    f"rerun after live history accrues")
    else:
        # exploration off and conviction sample still thin: pre-marker
        # corpora ('' rows) would defer forever, so grade the full live
        # sample (no probes are entering anymore)
        r = np.array(mixed)
        d, sr = _dsr_of(r)
        dsr_verdict("dsr: P(true SR > sr0) after trials correction",
                    d.get("dsr") or 0.0,
                    f"dsr={d.get('dsr'):.3f} sr={sr:.2f} n={len(r)} "
                    f"sr0={d.get('sr0_threshold'):.3f} "
                    f"(conviction-marked subset still {len(conviction)} < 30)",
                    _reach, _k, _dsr_trials)

    # THE ANTI-SILENCING RUNG, hoisted OUT of the four-way branch above
    # (red-team OBJ-2, conceded). It was originally called only inside the
    # `len(conviction) >= 30` arm, so in the file's own designed
    # post-exploration steady state - exploration off, conviction < 30,
    # mixed >= 30 - the pooled verdict still armed the "dsr" family while the
    # sentinel emitted NOTHING, and `went_dark` stayed empty so the arming
    # ratchet saw nothing either. The guard was silent in exactly the branch
    # the system is heading for. It depends on the fill ledger and the current
    # era, NOT on the pooled sample, so it belongs outside every arm.
    report_dsr_sentinel(
        live_rows,
        Path(__file__).resolve().parents[1] / "outputs" / "fills.csv",
        _exec_era_now())

    # ---- regime-stratified OOF diagnostic (#103 T3, report-only) ---------
    print("[diagnostic] regime-stratified OOF (report-only, no gate)")
    # Exception-isolated like OF-4's replay harness above: this section is
    # REPORT-ONLY (info() only, never check()) precisely so a raising
    # diagnostic (a corrupt/non-UTF8 signal_history.csv past what
    # regime_corpus_stats' own catch anticipates, a renamed FEATURE_NAMES
    # regime column, anything) degrades to a single skip line instead of
    # taking the whole battery's report and exit code down with it.
    try:
        regime_diagnostic(gaps, X, y, source.startswith("SYNTHETIC"),
                          store.path)
    except Exception as e:                                    # noqa: BLE001
        info(f"regime diagnostic skipped: {type(e).__name__}: {e}")

    # same isolation contract as the regime diagnostic above: report-only,
    # so any failure degrades to one skip line, never the battery
    try:
        learning_curve_diagnostic(X, y, w, sig, res,
                                  source.startswith("SYNTHETIC"))
    except Exception as e:                                    # noqa: BLE001
        info(f"learning curve diagnostic skipped: {type(e).__name__}: {e}")

    try:
        extras_liveness_diagnostic(X, source.startswith("SYNTHETIC"))
    except Exception as e:                                    # noqa: BLE001
        info(f"extras liveness diagnostic skipped: {type(e).__name__}: {e}")

    # ---- report ----------------------------------------------------------
    out = Path(args.report_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(f"# Overfit audit — {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())}\n\n"
                f"Dataset: {source}\n\n")
        for status, name, detail in REPORT:
            f.write(f"- **{status}** {name}" +
                    (f" — {detail}" if detail else "") + "\n")
        f.write(f"\n{PASS_N} passed, {FAIL_N} failed "
                f"({time.time() - t0:.0f}s)\n")
        f.write(f"\nCorpus: {source}\n")
        if on_synthetic:
            f.write("\n> **This green validates the OVERFIT MACHINERY, not "
                    "the market.** It is not evidence that the deployed "
                    "strategy is un-overfit.\n")
    print("=" * 42)
    # INERT COUNT ON THE SUMMARY LINE, same argument as the corpus line
    # below: "passed 3, failed 0" is what a reader takes away, and it
    # reads identically whether seven gates fired and three passed or
    # three fired and four could not fire at all (OF-1 informational
    # under exploration, OF-3 evidence-gated to one family, OF-4 inert on
    # a zero-entry recording, OF-5 deferred/unreachable). A gate that
    # COULD NOT FIRE reported the same way as one that fired and passed
    # is the laundering this line stops. Measured 2026-08-31: passed 3,
    # failed 0, informational 30+ — three of seven gates armed.
    _info_n = sum(1 for kind, _, _ in REPORT if kind == "INFO")
    print(f"passed {PASS_N}, failed {FAIL_N}, informational lines {_info_n}  "
          f"(report: {out}, {time.time() - t0:.0f}s)")
    print(f"  ^^ {PASS_N} ARMED checks passed. Informational lines are NOT "
          f"passes and include gates that COULD NOT FIRE - read the '--' "
          f"lines to see which, and why, before reading this as a green")
    # THE CORPUS BELONGS ON THE SUMMARY LINE, not only in the OF-1 header ~30
    # lines up. "passed N, failed 0" is what a reader takes away, and
    # CLAUDE.md's definition-of-done lists this script as a GATE — so a
    # synthetic-benchmark green was being read as evidence about the STRATEGY
    # when the tool is (honestly) reporting evidence about the INSTRUMENT.
    # Nothing about what runs or what passes changes; the distinction just
    # survives the scroll. Measured 2026-08-15: era exclusion left 346 loaded
    # rows against the len(FEATURE_NAMES)*10 = 640 floor, so every overfit
    # green this session was machinery-validation.
    print(f"corpus: {source}")
    if on_synthetic:
        print("  ^^ validates the OVERFIT MACHINERY, not the market - NOT "
              "evidence the deployed strategy is un-overfit")

    # DARK != PASS, IN THE RETURN TYPE (2026-09-10).
    #
    # Everything above already SAYS which gates could not fire. None of it
    # reached the exit code: `return 0 if FAIL_N == 0` is blind to how many
    # gates armed, so a battery that measured four of seven rungs and a
    # battery that measured all seven both hand back 0. CLAUDE.md's
    # definition-of-done consumes this script by exit code, and a machine
    # (or a tired reader) reads 0 as "done".
    #
    # WHY A SET AND NOT A COUNT, and why a ratchet and not a target:
    #   * a count goes stale immediately - measured this session, two runs
    #     ~1h apart reported 3 then 4 armed.
    #
    #     THE CAUSE WAS MIS-ATTRIBUTED (red-team OBJ-14, conceded). The
    #     original text blamed `dof: not starved` arming as the corpus grew
    #     past its rows/feature floor. It cannot have been: `check("dof: not
    #     starved...")` runs UNCONDITIONALLY at the OF-7 site, so it always
    #     emits PASS or FAIL and is therefore ALWAYS armed - it has no dark
    #     state to come out of. The 3->4 OBSERVATION stands; the mechanism
    #     named for it does not, and the original runs are gone so it is not
    #     now re-derivable. Recorded as un-derived rather than replaced with a
    #     second guess.
    #
    #     THE FRAGILITY THAT IS derivable, and matters more: `pbo` IS
    #     evidence-gated on live rows. Measured 2026-09-11, n_live = 63
    #     against a min_live_rows floor of 60 - a THREE-ROW margin. An era
    #     reset or a label-era migration that drops four rows takes `pbo`
    #     dark, this ratchet returns 3, and test_windows.bat vetoes on a
    #     corpus movement rather than a code defect. That is a gate whose
    #     release condition depends on something the change under test does
    #     not control, and it is the shape CLAUDE.md warns about in four
    #     separate incidents. Watch it; do not silently drop `pbo` from the
    #     set to clear a red - that is the widening this file forbids.
    #   * demanding all seven arm would exit non-zero today and stay there
    #     until the corpus and the conviction-trade count grow, which is a
    #     brick, not a gate. OF-5 is documented UNPASSABLE at N=7.
    # So the invariant is MONOTONE ARMING: a gate that arms today must not
    # stop arming tomorrow. That is a regression and gets its own code.
    # This lowers no floor - it strictly ADDS a failure the exit code could
    # not previously express (CLAUDE.md: "DO NOT fix any of these by
    # lowering a floor").
    return arming_exit_code(REPORT, EXPECTED_ARMED, FAIL_N,
                            on_synthetic=on_synthetic,
                            forced_synthetic=bool(args.force_synthetic),
                            corpus_absent=not Path(hist_path).exists())


if __name__ == "__main__":
    raise SystemExit(main())
