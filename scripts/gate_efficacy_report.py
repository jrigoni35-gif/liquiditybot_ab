"""scripts/gate_efficacy_report.py - does the gate stack actually select?

THE QUESTION NOBODY WAS ASKING. The bot labels EVERY gate-confirmed signal,
admitted or vetoed (that is what CandidateLabeler is for), so the corpus
already contains the counterfactual: what would have happened had each veto
not fired. Nothing consumed it. The gate stack has never been scored against
its own alternative.

First run, 2026-08-01, on 8,171 candidate rows:

    disposition                       n     win rate (net of cost)
    (blank)  = baseline            2061     26.5%  +/- 1.9
    entered  = ADMITTED BY GATE      43     18.6%  +/- 11.6
    SZ-030 net-Kelly f*<=0         1052      6.0%  +/- 1.4
    SZ-023 p 0.28 below bar 0.55    243     44.0%  +/- 6.2

Two findings, opposite signs. SZ-030 is doing real work - 6.0% against a
26.5% baseline is strong NEGATIVE selection, exactly what a good veto looks
like. SZ-023 in that configuration is ANTI-selective: it rejected candidates
that went on to win at 1.66x the base rate, on non-overlapping intervals.
The mechanism is visible in the disposition string itself - it vetoed on a
predicted p of 0.28 and the realized rate was 0.44, so the MODEL was
miscalibrated downward by 16 points and the gate faithfully executed the
miscalibration.

A gate is only as good as the calibration of what it gates on. This report
measures both, plus the concentration of what survives - because a gate that
improves its hit rate by collapsing onto one asset or one regime has not
learned, it has tunnel-visioned, and the two are indistinguishable from the
hit rate alone.

Report-only. Reads the corpus, writes markdown. Never touches a decision.

    python scripts/gate_efficacy_report.py [--history outputs/signal_history.csv]
                                           [--min-n 30] [--json]
"""
import argparse
import csv
import json
import math
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ml.corpus import (  # noqa: E402
    effective_n, wilson_interval as wilson, wilson_on_neff,
)
from ml.history import (  # noqa: E402
    label_era_of, LABEL_ERA_TRIPLE_BARRIER, LABEL_ERA_UNKNOWN,
)

# WHY THIS ONE. Three effective-n implementations exist in the repo and
# they answer different questions:
#   - `ml/history.py` ess_kish  - Kish ESS of a WEIGHT vector; it grades a
#     weighting scheme, and needs weights this route does not have.
#   - `scripts/cohort_eval.py` cohort_effective_n - continuous-time average
#     uniqueness over TRIP spans [t_open, t_close]; it needs realized
#     positions, and most rows here were never entered.
#   - `ml/corpus.py` effective_n - de Prado average uniqueness (AFML ch.4)
#     over CANDIDATE-ROW label windows [signal_ts, ts], per (asset, 5m
#     bar), the training loader's own algorithm computed within the
#     sample. RELOCATED there 2026-08-29 (verbatim) from
#     scripts/gate_truth_report.py so it has ONE stdlib-legal home;
#     gate_truth_report imports it from there too now.
# The rows this report scores ARE candidate rows with overlapping
# triple-barrier label windows, so this is the matching instrument - the
# same one the gate-truth route has quoted since 2026-07-29. Imported,
# never re-implemented: a second copy of an instrument is a second thing
# that can silently disagree. `wilson`/`wilson_on_neff` come from the same
# home so every interval on this page and the shared cut use one formula.

# Dispositions that mean "the gate let this through", not "a rule vetoed it".
ADMITTED = {"entered", "capped"}
# Blank disposition = registered but never reached a gate verdict; it is the
# closest thing to an unconditional sample and serves as the baseline.
#
# THE BASELINE IS A CLOSED COHORT. It cannot grow, and an unchanged baseline
# across two runs is the EXPECTED reading, not a stale cache. `_rows()`
# re-reads the live CSV on every invocation - there is no caching layer - but
# `ml/history.py`'s `register()` has stamped every candidate's default
# disposition as the literal "confirmed" since commit 8ceb5c3a
# (2026-07-20T16:12:14Z), so no row minted after that instant can ever land in
# the ""-bucket. The ERA-CONFOUND GUARD directly below says the same thing
# from the other side; it is repeated HERE, at the definition, because on
# 2026-09-08 a session re-ran this report over a corpus that had grown by
# thousands of rows, saw a byte-identical baseline, and spent its remaining
# turns treating a closed cohort as an instrument defect. The explanation was
# already in this file, eleven lines further down, and that was eleven lines
# too far. Re-derive rather than trusting any count written here:
#   python scripts/gate_efficacy_report.py --json
BASELINE = ""

# ERA-CONFOUND GUARD (2026-08-27, hardened 2026-08-27 fix-wave). The
# 2026-07-20 migration backfilled `disp=""` onto every pre-existing row
# without touching what LABEL DEFINITION produced it - BASELINE above is
# frozen at that instant (0 rows since, 84.1% `legacy` + 15.9%
# `exit_sim`, zero `triple_barrier*` - vault
# wiki/synthesis/open-contradictions-register.md, 2026-08-15 OPEN item).
# A code whose own rows are drawn entirely from an era the baseline
# never touches (SZ-021: 100% `triple_barrier_h432`, measured
# 2026-08-27) is not being compared to an alternative population - it is
# being compared to a different label definition from a different
# calendar month, and a disjoint-CI "significant" verdict there does not
# survive a same-window comparator (docs/HANDOFF.md REG-6 UPDATE,
# 2026-08-27 caveat: [0.439,0.580] vs a contemporaneous [0.369,0.514]
# overlaps).
#
# TWO FAILURE MODES the first cut of this guard (a MEMBERSHIP-SET check:
# "does this era appear ANYWHERE in the baseline, at any count") missed,
# both fixed by switching to a WEIGHTED (histogram-intersection) overlap
# below:
#   (i)  a single contaminating baseline row of a code's own era used to
#        read as FULL overlap (1.0) - membership doesn't care that the
#        baseline held that era ONCE in thousands of rows.
#   (ii) the 0.05 floor was a cliff on a fraction that could itself be
#        inflated the same way, so a sample that was 94.9% drawn from an
#        era the baseline never touches could still clear 0.05 (this
#        code's own SHARE of a scarce shared era) and print an unflagged
#        "significant" verdict on a mostly-incomparable sample.
# ERA_OVERLAP_FLOOR/_MAJORITY are POLICY floors, not fitted to any
# corpus: below FLOOR, no significance claim is rendered at all; between
# FLOOR and MAJORITY the baseline speaks to a MINORITY of this sample's
# own evidence (PARTIAL_OVERLAP - still no claim, but distinguished from
# fully confounded for a reader who wants to see how close it came); at
# or above MAJORITY the sample is COMPARABLE and ordinary significance
# discipline applies.
ERA_OVERLAP_FLOOR = 0.05
ERA_OVERLAP_MAJORITY = 0.5


def _row_era(r: dict) -> str:
    """Which label-definition era one row belongs to - same precedence
    `ml.history._row_label_era` and `migrate_history.py`'s migration
    both use (persisted `label_era` column first, `barrier`-derived
    fallback for a row written before the column existed): duplicated as
    this 2-line glue, not re-implemented, because the classification
    itself (`label_era_of`) is imported from ml.history so it cannot
    silently drift from the writer's own definition.

    A row with NO persisted `label_era` whose barrier falls back to the
    bare, un-suffixed `LABEL_ERA_TRIPLE_BARRIER` is AMBIGUOUS on this
    axis alone: `label_era_of` is a pure function of the barrier STRING
    ("tb_pt"/"tb_sl"/"tb_time") and cannot see which `label_max_bars`
    horizon produced it (this repo's per-row schema carries no horizon
    column - verified against the live corpus header, 2026-08-27), and
    the 2026-07-31 era-deadlock fix
    (`ml.history.triple_barrier_era`'s docstring) exists BECAUSE two
    different horizons once silently shared that one unqualified name.
    A fallback-derived bare "triple_barrier" is therefore routed to
    `LABEL_ERA_UNKNOWN` rather than trusted at face value. A row that
    DOES carry a persisted `label_era` (the normal case - every row in
    the live corpus has one as of 2026-08-27) is returned verbatim,
    horizon-qualified or not, and is unaffected by this rule."""
    persisted = (r.get("label_era") or "").strip()
    if persisted:
        return persisted
    derived = label_era_of(r.get("barrier") or "")
    return LABEL_ERA_UNKNOWN if derived == LABEL_ERA_TRIPLE_BARRIER else derived


def _era_mix(rows: list) -> Counter:
    return Counter(_row_era(r) for r in rows)


def _era_overlap_frac(mix: Counter, base_mix: Counter) -> float:
    """Weighted (histogram-intersection) overlap between a sample's own
    label_era mix and the baseline's: sum_e min(p_sample(e), p_base(e))
    over eras e, bounded [0, 1]. Weighting by each side's OWN proportion
    (not membership) is what fixes both failure modes in the comment
    above - a baseline era carried by one row in thousands contributes
    a near-zero p_base(e), so a code cannot buy full "overlap" just
    because the baseline happens to contain a single row of its era.

    `LABEL_ERA_UNKNOWN` rows are excluded from the numerator on BOTH
    sides (an unclassifiable row is not evidence of a SHARED label
    definition, so it earns no overlap credit) but stay in the sample's
    own denominator `n` below, so they correctly DILUTE the overlap
    fraction rather than silently vanishing from it.

    Weighting by raw row count, not by n_eff (effective/uniqueness-
    weighted count), was considered and deliberately not used: era
    membership is a population-DEFINITION question (which label rule
    produced this row), independent of how much INDEPENDENT evidence
    the row separately contributes once admitted - conflating the two
    corrections would make a large but low-uniqueness shared era read
    as thin overlap for the wrong reason."""
    n = sum(mix.values())
    nb = sum(base_mix.values())
    if not n or not nb:
        return 0.0
    return sum(min(c / n, base_mix.get(e, 0) / nb)
               for e, c in mix.items() if e != LABEL_ERA_UNKNOWN)


def _era_state(overlap: float, base_n: int) -> str:
    """CONFOUNDED_BASELINE below the floor, PARTIAL_OVERLAP between the
    floor and the majority line, COMPARABLE at or above it. Meaningful
    only when there IS a baseline; callers gate `base_n` separately
    (a code with a nonexistent baseline is not "comparable", it simply
    has nothing to be confounded against)."""
    if not base_n:
        return "COMPARABLE"
    if overlap < ERA_OVERLAP_FLOOR:
        return "CONFOUNDED_BASELINE"
    if overlap < ERA_OVERLAP_MAJORITY:
        return "PARTIAL_OVERLAP"
    return "COMPARABLE"


def _comparison(base_n: int, is_veto: bool, era_state: str,
                neff_ok_both: bool, lo, hi, base_lo, base_hi,
                *, admitted: bool = False) -> str:
    """Single significance-verdict vocabulary shared by every comparison
    site (per-disposition, by_code pooling, and the admitted-vs-baseline
    headline) so the three surfaces cannot silently diverge on what
    "significant" means. EXTEND this vocabulary, never repurpose an
    existing value - gc_pusher and the vault both key off these
    strings.

    `anti_selective`/`selective` are VETO-sample tokens: the sample is
    what the gate REJECTED, so winning MORE than baseline is harm and
    winning LESS is the veto earning its keep. The admitted-vs-baseline
    headline is the opposite kind of sample (rows the gate TOOK), so it
    passes `admitted=True` and the same two interval predicates emit
    `selects_winners` / `adverse_selection` instead - the direction
    words a taken sample actually means. Before 2026-08-28 (final-review
    F1) the headline lied `is_veto=True` to reach the confound states
    and exported the veto tokens inverted: admitted 0.90 vs baseline
    0.10, same era, read `anti_selective` - the harm word for brilliant
    selection. The confound / no-baseline / not-significant tokens are
    sample-direction-neutral and stay shared.

    `not_significant_nominal_n` is distinct from `not_significant`: the
    latter means both sides had a computable effective n AND their
    Wilson intervals still overlapped (an honest, effective-n-vetted
    null); the former means n_eff was NOT computable on at least one
    side, so whatever interval produced "no disjoint claim" here is the
    nominal-n fallback, not a vetted one - mirrors the per-disposition
    `anti_selective_nominal` distinction at the boolean level."""
    if not base_n:
        return "no_baseline"
    if not is_veto and not admitted:
        return "not_applicable"
    if era_state == "CONFOUNDED_BASELINE":
        return "CONFOUNDED_BASELINE"
    if era_state == "PARTIAL_OVERLAP":
        return "PARTIAL_OVERLAP"
    if not neff_ok_both:
        return "not_significant_nominal_n"
    if lo > base_hi:
        return "selects_winners" if admitted else "anti_selective"
    if hi < base_lo:
        return "adverse_selection" if admitted else "selective"
    return "not_significant"


# "SZ-023: p 0.28 below bar 0.55" -> (0.28, 0.55). The gate writes its own
# inputs into the disposition string, which makes calibration recoverable
# without any new instrumentation.
_P_BAR = re.compile(r"p\s+([0-9.]+)\s+below bar\s+([0-9.]+)")


# `wilson` (alias of ml.corpus.wilson_interval) and `wilson_on_neff` are
# imported at the top from the shared home — one Wilson formula for every
# interval on this page and the per-style cut below.


def _rows(path: Path) -> list:
    with open(path, newline="", encoding="utf-8") as f:
        return [r for r in csv.DictReader(f) if r.get("source") == "candidate"]


def _f(r, k):
    try:
        return float(r[k])
    except (TypeError, ValueError, KeyError):
        return None


def neff(rows: list) -> tuple:
    """(n_eff, mean_uniqueness, note) for a sample of candidate rows.

    Thin, honest wrapper around gate_truth_report.effective_n. `note` is
    None when the sample is fully dated, otherwise a string the report
    MUST print: a sample with no usable `ts` has no recoverable overlap
    structure, so n_eff comes back None and the route says so rather than
    quietly quoting the nominal-n interval as if it were the honest one
    (silence is the failure mode this repo keeps catching).
    """
    n = len(rows)
    if not n:
        return 0.0, 0.0, None
    dated = sum(1 for r in rows
                if (_f(r, "ts") or 0.0) > 0.0 or (_f(r, "signal_ts") or 0.0) > 0.0)
    if not dated:
        return (None, None,
                "no usable `ts`/`signal_ts` on any row - label-window "
                "overlap is unknown, so effective n is NOT computable "
                "here; the interval below is on NOMINAL n and is "
                "optimistic by an unmeasured factor")
    n_eff, mean_u = effective_n(rows)
    note = None
    if dated < n:
        note = (f"{n - dated} of {n} rows carry no timestamp; they enter "
                f"n_eff as single-bar (maximally independent) rows, so "
                f"n_eff here is an UPPER bound")
    return n_eff, mean_u, note


def _stat(rows: list) -> dict:
    """Win rate + BOTH intervals for one sample of labelled rows.

    `lo`/`hi` are the quoted interval and are computed on EFFECTIVE n
    (Wilson on k_eff = rate * n_eff successes out of n_eff trials - the
    point estimate is untouched, only its width). `lo_nom`/`hi_nom` are
    the old nominal-n interval, kept and printed beside it so a reader
    sees the shrinkage instead of being handed a silently-swapped number.
    When n_eff is not computable, `lo`/`hi` fall back to nominal AND
    `neff_note` says so; `neff_ok` is the flag every significance claim
    downstream is gated on.
    """
    ys = [_f(r, "label") for r in rows]
    ys = [y for y in ys if y is not None]
    n = len(ys)
    k = int(sum(ys))
    rate = (k / n) if n else 0.0
    lo_nom, hi_nom = wilson(k, n)
    n_eff, mean_u, note = neff(rows)
    if n_eff is None or n_eff <= 0.0:
        return {"n": n, "wins": k, "rate": rate, "n_eff": None,
                "mean_uniqueness": None, "neff_ok": False,
                "neff_note": note, "lo": lo_nom, "hi": hi_nom,
                "lo_nom": lo_nom, "hi_nom": hi_nom, "se_inflation": None}
    lo, hi = wilson_on_neff(rate, n_eff)
    return {"n": n, "wins": k, "rate": rate, "n_eff": n_eff,
            "mean_uniqueness": mean_u, "neff_ok": True, "neff_note": note,
            "lo": lo, "hi": hi, "lo_nom": lo_nom, "hi_nom": hi_nom,
            "se_inflation": math.sqrt(n / n_eff) if n_eff > 0 else None}


def efficacy(rows: list, min_n: int) -> dict:
    """Win rate per disposition, with the baseline and the admitted set
    called out. `separation` is the gate's actual selection power: admitted
    rate minus baseline rate. Positive means the gate finds winners.
    NEGATIVE MEANS IT IS SELECTING AGAINST ITSELF.

    Every interval and every disjointness claim below runs on EFFECTIVE n
    (de Prado average uniqueness over the rows' own label windows), not
    on the row count. On the 2026-08-22 corpus that is the difference
    between "the gate selects WINNERS, significant" and "intervals
    overlap": 2,061 baseline rows are ~112 independent observations
    (mean uniqueness 0.054) and 3,101 admitted rows are ~504.
    """
    by = defaultdict(list)
    for r in rows:
        if _f(r, "label") is not None:
            by[(r.get("disp") or "").strip()].append(r)

    base = _stat(by.get(BASELINE, []))
    base_era_mix = _era_mix(by.get(BASELINE, []))
    adm_rows = [r for d, v in by.items() if d in ADMITTED for r in v]
    adm = _stat(adm_rows)
    # C2 (2026-08-27 fix-wave): the "Does the gate select?" headline is
    # this file's most prominent claim and used to skip the era-confound
    # guard entirely - the exact defect species the guard exists to
    # catch, unfixed in the one place a reader looks first.
    adm_era_overlap = _era_overlap_frac(_era_mix(adm_rows), base_era_mix)
    adm_era_state = _era_state(adm_era_overlap, base["n"])
    out = {"baseline": base, "admitted": adm,
           "separation": adm["rate"] - base["rate"] if base["n"] else None,
           "admitted_era_overlap": adm_era_overlap,
           "admitted_comparison": _comparison(
               base["n"], False, adm_era_state,
               adm["neff_ok"] and base["neff_ok"], adm["lo"], adm["hi"],
               base["lo"], base["hi"], admitted=True),
           "dispositions": []}
    for d, v in sorted(by.items(), key=lambda kv: -len(kv[1])):
        if len(v) < min_n:
            continue
        s = _stat(v)
        # A veto is GOOD when what it rejected loses more than baseline.
        s["disposition"] = d or "(baseline)"
        s["vs_baseline"] = s["rate"] - base["rate"] if base["n"] else None
        is_veto = bool(d and d not in ADMITTED)
        s["era_overlap"] = _era_overlap_frac(_era_mix(v), base_era_mix)
        # CONFOUNDED_BASELINE / PARTIAL_OVERLAP: this sample's own rows
        # barely, partially, or never share a label_era with the
        # baseline sample, so no disjoint-CI claim about it means
        # anything - checked BEFORE anti_selective below, which either
        # state short-circuits.
        era_state = _era_state(s["era_overlap"], base["n"]) if is_veto else "COMPARABLE"
        s["confounded_baseline"] = bool(is_veto and era_state == "CONFOUNDED_BASELINE")
        s["partial_overlap"] = bool(is_veto and era_state == "PARTIAL_OVERLAP")
        comparable = era_state == "COMPARABLE"
        # ANTI-SELECTIVE is a significance claim (disjoint intervals), so
        # it is asserted only where BOTH samples have an effective n AND
        # an era-comparable baseline: a flag that survives on nominal n
        # alone, or on a disjoint/partial-era baseline, stops being
        # raised.
        s["anti_selective"] = bool(
            base["n"] and is_veto and comparable
            and s["neff_ok"] and base["neff_ok"] and s["lo"] > base["hi"])
        s["anti_selective_nominal"] = bool(
            base["n"] and is_veto and comparable
            and s["lo_nom"] > base["hi_nom"])
        # C7 (2026-08-27 fix-wave): per-disposition rows now carry the
        # SAME `comparison` vocabulary by_code has always emitted, so a
        # reader (or a doc) does not have to reconstruct the verdict
        # from confounded_baseline/era_overlap booleans by hand.
        s["comparison"] = _comparison(
            base["n"], is_veto, era_state, s["neff_ok"] and base["neff_ok"],
            s["lo"], s["hi"], base["lo"], base["hi"])
        out["dispositions"].append(s)

    # BY-CODE POOLING (2026-08-26, telemetry precision pass). The
    # disposition STRING fragments one gate into dozens of rows — SZ-023
    # alone parametrizes into "p 0.28 below bar 0.63", "p 0.51 below bar
    # 0.69", ... — which is the right granularity for calibration reading
    # but the wrong one for a dashboard asking "is this GATE earning its
    # keep". Dispositions PARTITION the labeled corpus (each row carries
    # exactly one), so pooling a code's variants is summing disjoint
    # samples: n, wins and effective-n all add, and the Wilson interval is
    # re-evaluated at the pooled effective n exactly as _stat does per
    # disposition. Rows whose disposition carries no SZ-*/PT-* token
    # (admitted / baseline / "capped") are not vetoes and stay out.
    code_re = re.compile(r"([A-Z]{2}-\d{3})")
    pooled = defaultdict(lambda: [0.0, 0.0, 0.0, 0])   # n, wins, n_eff, variants
    era_mix_by_code: "defaultdict[str, Counter]" = defaultdict(Counter)
    for d, v in by.items():
        mcode = code_re.search(d or "")
        if not mcode or d in ADMITTED:
            continue
        st = _stat(v)
        agg = pooled[mcode.group(1)]
        agg[0] += st["n"]
        agg[1] += st["wins"]
        agg[2] += st["n_eff"] if st["n_eff"] else 0.0
        agg[3] += 1
        era_mix_by_code[mcode.group(1)].update(_era_mix(v))
    out["by_code"] = []
    for code, (n, wins, n_eff, variants) in sorted(
            pooled.items(), key=lambda kv: -kv[1][0]):
        if n < min_n:
            continue
        rate = wins / n if n else 0.0
        if n_eff > 0:
            lo, hi = wilson_on_neff(rate, n_eff)
            neff_ok = True
        else:
            lo, hi = wilson(wins, n)
            neff_ok = False
        era_overlap = _era_overlap_frac(era_mix_by_code[code], base_era_mix)
        # CONFOUNDED_BASELINE / PARTIAL_OVERLAP (2026-08-27, hardened in
        # the fix-wave): this is the SZ-021 defect - a code whose rows
        # share little or no label_era with the frozen baseline is being
        # compared to a different label definition from a different
        # calendar window, not an alternative population.
        # `anti_selective`/`selective` are forced False for either
        # state, so the existing Grafana gauges
        # (`liquiditybot_veto_anti_selective`/`_selective`) read the
        # conservative "not proven" 0.0 with NO KEY RENAMED; `era_overlap`
        # and `comparison` EXTEND the payload for a reader who wants to
        # distinguish "not significant" (effective-n-vetted null),
        # "not_significant_nominal_n" (n_eff was not computable - see
        # `_comparison`'s docstring), and "unmeasurable against this
        # baseline" (fully or partially confounded). Rates/CIs are still
        # reported below, unsuppressed.
        era_state = _era_state(era_overlap, base["n"])
        comparable = era_state == "COMPARABLE"
        comparison = _comparison(base["n"], True, era_state,
                                 neff_ok and base["neff_ok"], lo, hi,
                                 base["lo"], base["hi"])
        out["by_code"].append({
            "code": code, "n": int(n), "wins": int(wins),
            "rate": rate, "n_eff": n_eff if n_eff > 0 else None,
            "neff_ok": neff_ok, "lo": lo, "hi": hi, "variants": variants,
            "vs_baseline": rate - base["rate"] if base["n"] else None,
            "era_overlap": era_overlap,
            "comparison": comparison,
            # same significance discipline as per-disposition, PLUS the
            # era-overlap guard: the flag is only raised where both
            # intervals run on effective n AND the baseline is COMPARABLE
            # (era_overlap at or above ERA_OVERLAP_MAJORITY)
            "anti_selective": bool(
                base["n"] and neff_ok and base["neff_ok"] and comparable
                and lo > base["hi"]),
            # a veto EARNS ITS KEEP when what it rejected wins
            # significantly LESS than baseline (disjoint below)
            "selective": bool(
                base["n"] and neff_ok and base["neff_ok"] and comparable
                and hi < base["lo"]),
        })
    return out


def calibration(rows: list, min_n: int) -> list:
    """Predicted p vs realized win rate, recovered from the disposition
    string. A gate cannot be better than the calibration of the quantity it
    thresholds on, so a miscalibrated p makes every bar downstream wrong in
    the same direction."""
    buckets = defaultdict(list)
    for r in rows:
        y = _f(r, "label")
        m = _P_BAR.search(r.get("disp") or "")
        if y is None or not m:
            continue
        buckets[round(float(m.group(1)), 2)].append(r)
    out = []
    for p_pred, v in sorted(buckets.items()):
        if len(v) < min_n:
            continue
        st = _stat(v)
        # MISCALIBRATED is a significance claim ("the predicted p lies
        # outside the realized interval"), so it is decided on the
        # effective-n interval; the nominal-n verdict is kept beside it
        # to show which calls survive the honest width and which do not.
        out.append({"p_predicted": p_pred, "n": st["n"],
                    "n_eff": st["n_eff"],
                    "mean_uniqueness": st["mean_uniqueness"],
                    "neff_ok": st["neff_ok"], "neff_note": st["neff_note"],
                    "p_realized": st["rate"], "lo": st["lo"],
                    "hi": st["hi"], "lo_nom": st["lo_nom"],
                    "hi_nom": st["hi_nom"],
                    "error": st["rate"] - p_pred,
                    "miscalibrated": (st["neff_ok"]
                                      and not (st["lo"] <= p_pred <= st["hi"])),
                    "miscalibrated_nominal": not (st["lo_nom"] <= p_pred
                                                  <= st["hi_nom"])})
    return out


def concentration(rows: list) -> dict:
    """TUNNEL-VISION DETECTOR. A gate can raise its hit rate two ways: by
    learning, or by collapsing onto one asset / one regime / one side. From
    the hit rate alone those are indistinguishable, and only one of them
    survives a regime change.

    Herfindahl-Hirschman index over the ADMITTED set, normalised to [0,1]:
    0 = perfectly spread over the available options, 1 = everything in one.
    Compared against the same index over ALL candidates, so the number
    answers "is the gate MORE concentrated than its own opportunity set"
    rather than "is the universe small"."""
    def hhi(counter: Counter) -> float:
        tot = sum(counter.values())
        if tot <= 0 or len(counter) <= 1:
            return 0.0
        raw = sum((c / tot) ** 2 for c in counter.values())
        k = len(counter)
        return max(0.0, (raw - 1.0 / k) / (1.0 - 1.0 / k))

    adm = [r for r in rows if (r.get("disp") or "").strip() in ADMITTED]
    out = {"admitted_n": len(adm)}
    for dim in ("asset", "direction"):
        a, allc = Counter(r.get(dim) for r in adm), Counter(r.get(dim) for r in rows)
        out[dim] = {"admitted_hhi": round(hhi(a), 4),
                    "corpus_hhi": round(hhi(allc), 4),
                    "excess": round(hhi(a) - hhi(allc), 4),
                    "distinct_admitted": len(a), "distinct_corpus": len(allc)}
    return out


# --- PER EXECUTION-STYLE CUT (2026-08-29) --------------------------------
# by_code above cuts the corpus by which VETO fired. This cuts it by
# execution STYLE - side, the five hard one-hot regimes, the five THALES
# channels, probe/conviction - and asks the same question every panel here
# asks: at HONEST (effective) n, is this stratum resolvably different from
# the book, or does its interval straddle the average while a nominal-n
# interval would read tight and optimistic by sqrt(n / n_eff)?
#
# ERA-CLEAN BY CONSTRUCTION. The cut runs inside the SINGLE most-populous
# label_era among labelled candidate rows and compares each style to the
# pooled win rate of that SAME era. One era in, one era out: no style is
# ever compared across disjoint label populations (the CONFOUNDED_BASELINE
# class guarded elsewhere on this page), so the only verdicts are
# effective-n verdicts - the whole point of the cut.
#
# The era baseline INCLUDES the style's own rows (the era pool), so the
# separation test is deliberately conservative: a style must out- or
# under-perform the very pool it belongs to. NO NOMINAL-n INTERVAL IS EVER
# RENDERED here. A style whose effective-n Wilson interval overlaps that
# baseline - n_eff too small to clear it - is reported UNESTIMABLE, never
# as a point rate that reads precise but is not.
_REGIME_COLS = ("regime_bull_quiet", "regime_bull_vol", "regime_range",
                "regime_bear", "regime_crisis")
_THALES_COLS = ("th_grid", "th_metronome", "th_clockwork", "th_stopzone",
                "th_barclose")


def _is_probe(r: dict) -> bool:
    return (r.get("probe") or "").strip() in ("1", "true", "True")


def _style_subsets(pop: list) -> list:
    """(style_name, kind, rows) for each execution-style axis over one
    era-clean population. Regimes are one-hot (active = value > 0.5);
    THALES channels are continuous shading scores (active = nonzero, any
    magnitude); `probe` is an ENTRY-time tag that candidate rows carry
    blank, so its cut is expected to be degenerate here and is REPORTED
    (UNESTIMABLE) rather than dropped, so the absence stays visible."""
    out = [("side=long", "side",
            [r for r in pop
             if (r.get("side") or "").strip().lower() == "long"]),
           ("side=short", "side",
            [r for r in pop
             if (r.get("side") or "").strip().lower() == "short"])]
    for c in _REGIME_COLS:
        out.append((c, "regime", [r for r in pop if (_f(r, c) or 0.0) > 0.5]))
    for c in _THALES_COLS:
        out.append((c, "thales",
                    [r for r in pop if (_f(r, c) or 0.0) != 0.0]))
    out.append(("probe", "probe", [r for r in pop if _is_probe(r)]))
    out.append(("conviction", "probe", [r for r in pop if not _is_probe(r)]))
    return out


def _style_verdict(st: dict, base: dict) -> str:
    """UNESTIMABLE unless the style's EFFECTIVE-n Wilson interval clears the
    era baseline's (disjoint above or below). n=0 or an incomputable n_eff
    is UNESTIMABLE by definition; an interval that overlaps the baseline
    means n_eff is too small to separate the style from the pack - reported
    as UNESTIMABLE, not as a falsely-precise rate."""
    if st["n"] == 0 or not st["neff_ok"] or not base["neff_ok"]:
        return "UNESTIMABLE"
    if st["lo"] > base["hi"]:
        return "above_baseline"
    if st["hi"] < base["lo"]:
        return "below_baseline"
    return "UNESTIMABLE"


def per_style(rows: list) -> dict:
    """Win rate + EFFECTIVE-n Wilson interval per execution style, inside
    one era-clean population (see the block comment above). Report-only;
    selects nothing, changes no threshold."""
    labelled = [r for r in rows if _f(r, "label") is not None]
    if not labelled:
        return {"available": False, "reason": "no labelled candidate rows"}
    era = Counter(_row_era(r) for r in labelled).most_common(1)[0][0]
    pop = [r for r in labelled if _row_era(r) == era]
    base = _stat(pop)
    styles = []
    for name, kind, sub in _style_subsets(pop):
        st = _stat(sub)
        verdict = _style_verdict(st, base)
        estimable = verdict in ("above_baseline", "below_baseline")
        styles.append({
            "style": name, "kind": kind, "n": st["n"],
            "n_eff": st["n_eff"], "mean_uniqueness": st["mean_uniqueness"],
            "se_inflation": st["se_inflation"],
            # NEVER a nominal-n number here: an unresolvable style carries
            # no rate/interval at all, only the diagnostics that say why.
            "rate": st["rate"] if estimable else None,
            "lo": st["lo"] if estimable else None,
            "hi": st["hi"] if estimable else None,
            "vs_baseline": (st["rate"] - base["rate"]) if estimable else None,
            "verdict": verdict,
        })
    return {"available": True, "era": era, "n": len(pop),
            "baseline": {"n": base["n"], "n_eff": base["n_eff"],
                         "mean_uniqueness": base["mean_uniqueness"],
                         "rate": base["rate"], "lo": base["lo"],
                         "hi": base["hi"], "neff_ok": base["neff_ok"]},
            "styles": styles}


def _neff_cell(st: dict) -> str:
    """`n_eff` for a table cell - never blank, never silently nominal."""
    return f"{st['n_eff']:.1f}" if st.get("neff_ok") else "n/a"


def render(eff: dict, cal: list, conc: dict,
           ps: "dict | None" = None) -> str:
    L = ["# Gate efficacy report", "",
         "Every interval below is a Wilson interval on EFFECTIVE n "
         "(de Prado average uniqueness over each row's own "
         "[signal_ts, ts] label window, per asset on a 5m concurrency "
         "grid - `ml.corpus.effective_n`, the standard "
         "this repo has applied since 2026-07-29). Overlapping label "
         "windows share one return path, so N concurrent rows are far "
         "fewer than N facts; the nominal-n interval is printed beside "
         "each one so the shrinkage is visible rather than assumed.", ""]
    b, a = eff["baseline"], eff["admitted"]
    L += ["## Does the gate select?", ""]
    for name, st in (("baseline (no verdict)", b),
                     ("admitted by the gate", a)):
        L.append(f"- {name}: **{st['rate']:.1%}** "
                 f"[{st['lo']:.1%}, {st['hi']:.1%}] "
                 f"n={st['n']} n_eff={_neff_cell(st)}"
                 + (f" (mean uniqueness {st['mean_uniqueness']:.4f}, SE "
                    f"inflation {st['se_inflation']:.1f}x)"
                    if st.get("neff_ok") else "")
                 + f"; nominal-n interval was [{st['lo_nom']:.1%}, "
                   f"{st['hi_nom']:.1%}]")
        if st.get("neff_note"):
            L.append(f"  - effective n caveat: {st['neff_note']}")
    if eff["separation"] is not None:
        s = eff["separation"]
        verdict = ("the gate selects WINNERS" if s > 0 else
                   "**the gate selects AGAINST itself**")
        L.append(f"- separation: **{s:+.1%}** - {verdict}")
        cmp = eff.get("admitted_comparison")
        # C2 (2026-08-27 fix-wave): the era-confound guard now covers
        # this headline too - checked BEFORE the neff-based significance
        # branches below, same precedence as the by_code/per-disposition
        # guard.
        if cmp == "CONFOUNDED_BASELINE":
            L.append("- **baseline CONFOUNDED** - the admitted set shares "
                     f"only {eff['admitted_era_overlap']:.0%} label_era "
                     "overlap with the baseline sample, so no "
                     "significance claim is made here")
        elif cmp == "PARTIAL_OVERLAP":
            L.append("- **baseline PARTIAL OVERLAP** - the admitted set "
                     f"shares only {eff['admitted_era_overlap']:.0%} "
                     "label_era overlap with the baseline sample "
                     "(majority of the admitted evidence is drawn from an "
                     "era the baseline can't speak to); no significance "
                     "claim is made here")
        else:
            # F1 (2026-08-28 final review): prose now branches on the
            # exported `admitted_comparison` token itself rather than
            # re-deriving the same interval predicates, so the JSON
            # field and this markdown cannot silently diverge.
            nom_disjoint = (a["n"] and b["n"]
                            and (a["lo_nom"] > b["hi_nom"]
                                 or a["hi_nom"] < b["lo_nom"]))
            if cmp == "not_significant_nominal_n":
                L.append("- **significance NOT assessed**: effective n is not "
                         "computable for at least one side, so no disjointness "
                         "claim is made here (a claim that would rest on "
                         "nominal n is not made at all)")
            elif cmp == "selects_winners":
                L.append("- separation is significant on effective n "
                         "(intervals disjoint)")
            elif cmp == "adverse_selection":
                L.append("- **adverse separation is SIGNIFICANT** on effective "
                         "n (intervals disjoint) - the admitted set is "
                         "reliably worse than taking no view at all")
            else:
                L.append("- not significant at this effective sample size; "
                         "intervals overlap"
                         + (" - NOTE: this comparison WOULD read 'significant "
                            "(intervals disjoint)' on nominal row counts. It "
                            "does not survive the label-overlap deflation, so "
                            "the claim is withdrawn."
                            if nom_disjoint else ""))
    L += ["", "## Per-rule", "",
          "| disposition | n | n_eff | win rate | 95% CI (n_eff) "
          "| 95% CI (nominal n) | vs baseline | |",
          "|---|---:|---:|---:|---|---|---:|---|"]
    for d in eff["dispositions"]:
        if d.get("confounded_baseline"):
            flag = (" (baseline CONFOUNDED - "
                    f"{d['era_overlap']:.0%} label_era overlap, no "
                    "significance claim made)")
        elif d.get("partial_overlap"):
            flag = (" (baseline PARTIAL - "
                    f"{d['era_overlap']:.0%} label_era overlap, majority "
                    "incomparable, no significance claim made)")
        elif d.get("anti_selective"):
            flag = " **ANTI-SELECTIVE**"
        elif d.get("anti_selective_nominal"):
            flag = " (anti-selective on nominal n ONLY - withdrawn)"
        else:
            flag = ""
        vs = f"{d['vs_baseline']:+.1%}" if d["vs_baseline"] is not None else "-"
        L.append(f"| `{d['disposition'][:52]}` | {d['n']} "
                 f"| {_neff_cell(d)} | {d['rate']:.1%} "
                 f"| [{d['lo']:.1%}, {d['hi']:.1%}] "
                 f"| [{d['lo_nom']:.1%}, {d['hi_nom']:.1%}] | {vs} |{flag} |")
    L += ["", "A veto is HEALTHY when its win rate sits well BELOW baseline -",
          "that means it is removing losers. A veto ABOVE baseline is",
          "rejecting winners, and the wider the gap the more it costs.", ""]
    if cal:
        L += ["## Calibration of the gated quantity", "",
              "| p predicted | n | n_eff | p realized | 95% CI (n_eff) "
              "| 95% CI (nominal n) | error | |",
              "|---:|---:|---:|---:|---|---|---:|---|"]
        for c in cal:
            f = " **MISCALIBRATED**" if c["miscalibrated"] else ""
            if not f and c.get("miscalibrated_nominal"):
                f = (" (miscalibrated on nominal n ONLY - withdrawn)"
                     if c.get("neff_ok") else
                     " (nominal-n call; effective n not computable)")
            L.append(f"| {c['p_predicted']:.2f} | {c['n']} | "
                     f"{_neff_cell(c)} | "
                     f"{c['p_realized']:.2f} | [{c['lo']:.2f}, {c['hi']:.2f}] "
                     f"| [{c['lo_nom']:.2f}, {c['hi_nom']:.2f}] "
                     f"| {c['error']:+.2f} |{f} |")
        L += ["", "A bar can only be as good as the calibration of what it",
              "thresholds. A p biased low makes every downstream bar reject",
              "in the same wrong direction.", ""]
    L += ["## Tunnel vision", "",
          f"admitted n={conc['admitted_n']}  "
          f"n_eff={_neff_cell(eff['admitted'])}", "",
          "HHI is a COMPOSITION statistic over the admitted set, not a "
          "rate estimated from independent draws, and no interval or "
          "significance claim is made on it here - so no effective-n "
          "correction applies to the numbers in this table. The admitted "
          "set's n_eff is printed above only so a reader knows how much "
          "independent evidence the same rows carry elsewhere.", "",
          "| dimension | admitted HHI | corpus HHI | excess | distinct |",
          "|---|---:|---:|---:|---:|"]
    for dim in ("asset", "direction"):
        d = conc[dim]
        L.append(f"| {dim} | {d['admitted_hhi']:.4f} | {d['corpus_hhi']:.4f} "
                 f"| {d['excess']:+.4f} | {d['distinct_admitted']}"
                 f"/{d['distinct_corpus']} |")
    L += ["", "Excess > 0 means the gate is MORE concentrated than the",
          "opportunity it was offered. A rising hit rate with rising excess",
          "is not learning - it is the gate narrowing onto a pocket that a",
          "regime change will remove.", ""]

    # ps is optional so existing 3-arg callers (tests, gc_pusher) keep their
    # exact output; the per-style section is emitted only when main supplies
    # it. Extend-with-default, never break the signature (CLAUDE.md inv. 7).
    if ps is None:
        return "\n".join(L)
    L += ["## Per execution style (effective-n)", ""]
    if not ps.get("available"):
        L += [f"_unavailable: {ps.get('reason', 'no data')}_", ""]
    else:
        pb = ps["baseline"]
        L += [f"Cut inside the single most-populous label_era "
              f"**{ps['era']}** (n={ps['n']}), era-clean so no style is "
              f"pooled across disjoint label populations. Baseline (that "
              f"era, all styles pooled, so the test is conservative): "
              f"**{pb['rate']:.1%}** [{pb['lo']:.1%}, {pb['hi']:.1%}] "
              f"n={pb['n']} n_eff={pb['n_eff']:.1f}. Every interval is on "
              f"EFFECTIVE n; a style whose n_eff cannot clear that baseline "
              f"interval is **UNESTIMABLE** - reported as such, never as a "
              f"nominal-n point rate.", "",
              "| style | kind | n | n_eff | SE infl | win rate | 95% CI "
              "(n_eff) | vs baseline | verdict |",
              "|---|---|---:|---:|---:|---|---|---:|---|"]
        for s in ps["styles"]:
            neff = f"{s['n_eff']:.1f}" if s.get("n_eff") else "n/a"
            infl = (f"{s['se_inflation']:.1f}x"
                    if s.get("se_inflation") else "-")
            if s["verdict"] in ("above_baseline", "below_baseline"):
                rate = f"{s['rate']:.1%}"
                ci = f"[{s['lo']:.1%}, {s['hi']:.1%}]"
                vs = f"{s['vs_baseline']:+.1%}"
            else:
                rate = ci = vs = "UNESTIMABLE"
            L.append(f"| `{s['style']}` | {s['kind']} | {s['n']} | {neff} "
                     f"| {infl} | {rate} | {ci} | {vs} | {s['verdict']} |")
        L += ["", "SE infl = sqrt(n / n_eff), the factor by which a "
              "nominal-n interval understates width. UNESTIMABLE is not a "
              "null result ABOUT the style - it is a statement about the "
              "SAMPLE: at this effective n the style cannot be separated "
              "from the era baseline, so no honest point rate is quoted "
              "(a nominal-n one would read tight and mislead).", ""]
    return "\n".join(L)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--history", default=str(ROOT / "outputs" /
                                             "signal_history.csv"))
    ap.add_argument("--min-n", type=int, default=30)
    ap.add_argument("--out", default=str(ROOT / "outputs" /
                                         "gate_efficacy.md"))
    ap.add_argument("--json", action="store_true")
    ns = ap.parse_args()

    p = Path(ns.history)
    if not p.exists():
        print(f"no history at {p}")
        return 1
    rows = _rows(p)
    if not rows:
        print("no candidate rows")
        return 1
    eff = efficacy(rows, ns.min_n)
    cal = calibration(rows, ns.min_n)
    conc = concentration(rows)
    ps = per_style(rows)
    if ns.json:
        print(json.dumps({"efficacy": eff, "calibration": cal,
                          "concentration": conc, "per_style": ps}, indent=1))
        return 0
    md = render(eff, cal, conc, ps)
    Path(ns.out).write_text(md, encoding="utf-8")
    print(md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
