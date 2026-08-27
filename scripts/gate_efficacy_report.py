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

from scripts.gate_truth_report import effective_n  # noqa: E402

# WHY THIS ONE. Three effective-n implementations exist in the repo and
# they answer different questions:
#   - `ml/history.py` ess_kish  - Kish ESS of a WEIGHT vector; it grades a
#     weighting scheme, and needs weights this route does not have.
#   - `scripts/cohort_eval.py` cohort_effective_n - continuous-time average
#     uniqueness over TRIP spans [t_open, t_close]; it needs realized
#     positions, and most rows here were never entered.
#   - `scripts/gate_truth_report.py` effective_n - de Prado average
#     uniqueness (AFML ch.4) over CANDIDATE-ROW label windows
#     [signal_ts, ts], per (asset, 5m bar), the training loader's own
#     algorithm computed within the sample.
# The rows this report scores ARE candidate rows with overlapping
# triple-barrier label windows, so the third one is the matching
# instrument - and it is the same one the gate-truth route has quoted
# since 2026-07-29. Imported, never re-implemented: a second copy of an
# instrument is a second thing that can silently disagree.

# Dispositions that mean "the gate let this through", not "a rule vetoed it".
ADMITTED = {"entered", "capped"}
# Blank disposition = registered but never reached a gate verdict; it is the
# closest thing to an unconditional sample and serves as the baseline.
BASELINE = ""

# "SZ-023: p 0.28 below bar 0.55" -> (0.28, 0.55). The gate writes its own
# inputs into the disposition string, which makes calibration recoverable
# without any new instrumentation.
_P_BAR = re.compile(r"p\s+([0-9.]+)\s+below bar\s+([0-9.]+)")


def wilson(k: float, n: float, z: float = 1.96) -> tuple:
    """Wilson score interval - correct near 0 and 1, where the normal
    approximation produces bounds outside [0,1] and a veto rule sitting at a
    6% hit rate is exactly that regime.

    `k`/`n` are floats, not ints, because the honest sample size here is
    EFFECTIVE n: the interval is evaluated at k_eff = rate * n_eff out of
    n_eff trials, which keeps the point estimate exactly where the data
    put it and widens only the interval. Integer counts still work
    unchanged."""
    if n <= 0:
        return (0.0, 0.0)
    p = k / n
    d = 1.0 + z * z / n
    c = p + z * z / (2 * n)
    m = z * math.sqrt(max(p * (1 - p) / n + z * z / (4 * n * n), 0.0))
    return ((c - m) / d, (c + m) / d)


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
    lo, hi = wilson(rate * n_eff, n_eff)
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
    adm = _stat([r for d, v in by.items() if d in ADMITTED for r in v])
    out = {"baseline": base, "admitted": adm,
           "separation": adm["rate"] - base["rate"] if base["n"] else None,
           "dispositions": []}
    for d, v in sorted(by.items(), key=lambda kv: -len(kv[1])):
        if len(v) < min_n:
            continue
        s = _stat(v)
        # A veto is GOOD when what it rejected loses more than baseline.
        s["disposition"] = d or "(baseline)"
        s["vs_baseline"] = s["rate"] - base["rate"] if base["n"] else None
        # ANTI-SELECTIVE is a significance claim (disjoint intervals), so
        # it is asserted only where BOTH samples have an effective n: a
        # flag that survives on nominal n alone stops being raised.
        s["anti_selective"] = bool(
            base["n"] and d and d not in ADMITTED
            and s["neff_ok"] and base["neff_ok"] and s["lo"] > base["hi"])
        s["anti_selective_nominal"] = bool(
            base["n"] and d and d not in ADMITTED
            and s["lo_nom"] > base["hi_nom"])
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
    out["by_code"] = []
    for code, (n, wins, n_eff, variants) in sorted(
            pooled.items(), key=lambda kv: -kv[1][0]):
        if n < min_n:
            continue
        rate = wins / n if n else 0.0
        if n_eff > 0:
            lo, hi = wilson(rate * n_eff, n_eff)
            neff_ok = True
        else:
            lo, hi = wilson(wins, n)
            neff_ok = False
        out["by_code"].append({
            "code": code, "n": int(n), "wins": int(wins),
            "rate": rate, "n_eff": n_eff if n_eff > 0 else None,
            "neff_ok": neff_ok, "lo": lo, "hi": hi, "variants": variants,
            "vs_baseline": rate - base["rate"] if base["n"] else None,
            # same significance discipline as per-disposition: the flag is
            # only raised where both intervals run on effective n
            "anti_selective": bool(
                base["n"] and neff_ok and base["neff_ok"]
                and lo > base["hi"]),
            # a veto EARNS ITS KEEP when what it rejected wins
            # significantly LESS than baseline (disjoint below)
            "selective": bool(
                base["n"] and neff_ok and base["neff_ok"]
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


def _neff_cell(st: dict) -> str:
    """`n_eff` for a table cell - never blank, never silently nominal."""
    return f"{st['n_eff']:.1f}" if st.get("neff_ok") else "n/a"


def render(eff: dict, cal: list, conc: dict) -> str:
    L = ["# Gate efficacy report", "",
         "Every interval below is a Wilson interval on EFFECTIVE n "
         "(de Prado average uniqueness over each row's own "
         "[signal_ts, ts] label window, per asset on a 5m concurrency "
         "grid - `scripts/gate_truth_report.effective_n`, the standard "
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
        nom_disjoint = (a["n"] and b["n"]
                        and (a["lo_nom"] > b["hi_nom"]
                             or a["hi_nom"] < b["lo_nom"]))
        if not (a["neff_ok"] and b["neff_ok"]):
            L.append("- **significance NOT assessed**: effective n is not "
                     "computable for at least one side, so no disjointness "
                     "claim is made here (a claim that would rest on "
                     "nominal n is not made at all)")
        elif a["lo"] > b["hi"]:
            L.append("- separation is significant on effective n "
                     "(intervals disjoint)")
        elif a["hi"] < b["lo"]:
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
        flag = " **ANTI-SELECTIVE**" if d.get("anti_selective") else ""
        if not flag and d.get("anti_selective_nominal"):
            flag = " (anti-selective on nominal n ONLY - withdrawn)"
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
    if ns.json:
        print(json.dumps({"efficacy": eff, "calibration": cal,
                          "concentration": conc}, indent=1))
        return 0
    md = render(eff, cal, conc)
    Path(ns.out).write_text(md, encoding="utf-8")
    print(md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
