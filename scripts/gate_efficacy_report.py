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
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Dispositions that mean "the gate let this through", not "a rule vetoed it".
ADMITTED = {"entered", "capped"}
# Blank disposition = registered but never reached a gate verdict; it is the
# closest thing to an unconditional sample and serves as the baseline.
BASELINE = ""

# "SZ-023: p 0.28 below bar 0.55" -> (0.28, 0.55). The gate writes its own
# inputs into the disposition string, which makes calibration recoverable
# without any new instrumentation.
_P_BAR = re.compile(r"p\s+([0-9.]+)\s+below bar\s+([0-9.]+)")


def wilson(k: int, n: int, z: float = 1.96) -> tuple:
    """Wilson score interval - correct near 0 and 1, where the normal
    approximation produces bounds outside [0,1] and a veto rule sitting at a
    6% hit rate is exactly that regime."""
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


def efficacy(rows: list, min_n: int) -> dict:
    """Win rate per disposition, with the baseline and the admitted set
    called out. `separation` is the gate's actual selection power: admitted
    rate minus baseline rate. Positive means the gate finds winners.
    NEGATIVE MEANS IT IS SELECTING AGAINST ITSELF."""
    by = defaultdict(list)
    for r in rows:
        y = _f(r, "label")
        if y is not None:
            by[(r.get("disp") or "").strip()].append(y)

    def stat(vals):
        n = len(vals)
        k = int(sum(vals))
        lo, hi = wilson(k, n)
        return {"n": n, "wins": k, "rate": (k / n) if n else 0.0,
                "lo": lo, "hi": hi}

    base = stat(by.get(BASELINE, []))
    adm = stat([y for d, v in by.items() if d in ADMITTED for y in v])
    out = {"baseline": base, "admitted": adm,
           "separation": adm["rate"] - base["rate"] if base["n"] else None,
           "dispositions": []}
    for d, v in sorted(by.items(), key=lambda kv: -len(kv[1])):
        if len(v) < min_n:
            continue
        s = stat(v)
        # A veto is GOOD when what it rejected loses more than baseline.
        s["disposition"] = d or "(baseline)"
        s["vs_baseline"] = s["rate"] - base["rate"] if base["n"] else None
        s["anti_selective"] = bool(
            base["n"] and d and d not in ADMITTED and s["lo"] > base["hi"])
        out["dispositions"].append(s)
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
        buckets[round(float(m.group(1)), 2)].append(y)
    out = []
    for p_pred, v in sorted(buckets.items()):
        if len(v) < min_n:
            continue
        k = int(sum(v))
        lo, hi = wilson(k, len(v))
        out.append({"p_predicted": p_pred, "n": len(v),
                    "p_realized": k / len(v), "lo": lo, "hi": hi,
                    "error": (k / len(v)) - p_pred,
                    "miscalibrated": not (lo <= p_pred <= hi)})
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


def render(eff: dict, cal: list, conc: dict) -> str:
    L = ["# Gate efficacy report", ""]
    b, a = eff["baseline"], eff["admitted"]
    L += ["## Does the gate select?", "",
          f"- baseline (no verdict): **{b['rate']:.1%}** "
          f"[{b['lo']:.1%}, {b['hi']:.1%}] n={b['n']}",
          f"- admitted by the gate: **{a['rate']:.1%}** "
          f"[{a['lo']:.1%}, {a['hi']:.1%}] n={a['n']}"]
    if eff["separation"] is not None:
        s = eff["separation"]
        verdict = ("the gate selects WINNERS" if s > 0 else
                   "**the gate selects AGAINST itself**")
        L.append(f"- separation: **{s:+.1%}** - {verdict}")
        if a["n"] and b["n"] and a["lo"] > b["hi"]:
            L.append("- separation is significant (intervals disjoint)")
        elif a["n"] and b["n"] and a["hi"] < b["lo"]:
            L.append("- **adverse separation is SIGNIFICANT** (intervals "
                     "disjoint) - the admitted set is reliably worse than "
                     "taking no view at all")
        else:
            L.append("- not significant at this sample size; intervals overlap")
    L += ["", "## Per-rule", "",
          "| disposition | n | win rate | 95% CI | vs baseline | |",
          "|---|---:|---:|---|---:|---|"]
    for d in eff["dispositions"]:
        flag = " **ANTI-SELECTIVE**" if d.get("anti_selective") else ""
        vs = f"{d['vs_baseline']:+.1%}" if d["vs_baseline"] is not None else "-"
        L.append(f"| `{d['disposition'][:52]}` | {d['n']} | {d['rate']:.1%} "
                 f"| [{d['lo']:.1%}, {d['hi']:.1%}] | {vs} |{flag} |")
    L += ["", "A veto is HEALTHY when its win rate sits well BELOW baseline -",
          "that means it is removing losers. A veto ABOVE baseline is",
          "rejecting winners, and the wider the gap the more it costs.", ""]
    if cal:
        L += ["## Calibration of the gated quantity", "",
              "| p predicted | n | p realized | 95% CI | error | |",
              "|---:|---:|---:|---|---:|---|"]
        for c in cal:
            f = " **MISCALIBRATED**" if c["miscalibrated"] else ""
            L.append(f"| {c['p_predicted']:.2f} | {c['n']} | "
                     f"{c['p_realized']:.2f} | [{c['lo']:.2f}, {c['hi']:.2f}] "
                     f"| {c['error']:+.2f} |{f} |")
        L += ["", "A bar can only be as good as the calibration of what it",
              "thresholds. A p biased low makes every downstream bar reject",
              "in the same wrong direction.", ""]
    L += ["## Tunnel vision", "",
          f"admitted n={conc['admitted_n']}", "",
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
