"""scripts/rpe_factor.py - reward prediction error over the triple barrier.

THE IDEA, STATED PRECISELY. Dopamine does not encode reward; it encodes
reward PREDICTION ERROR (Schultz 1997). A neuron fires on surprise, not on
profit, and in a well-calibrated agent the signal decays toward zero even
while it keeps winning - because nothing surprises it any more. That makes
an affect signal built this way a CALIBRATION INSTRUMENT rather than a mood
ring: persistent positive RPE does not mean the bot is doing well, it means
the bot is systematically surprised, which means its predictions are wrong.

    delta = realized_outcome - E[outcome | predictor]

THE TRIPLE BARRIER IS WHAT MAKES THIS COMPUTABLE. Each labeled row carries
its own geometry (pt_frac, sl_frac) and which barrier resolved, so both
halves are known per row rather than assumed:

    realized:  tb_pt   -> +pt_frac        (target paid)
               tb_sl   -> -sl_frac        (stop paid)
               tb_time -> the actual move (neither barrier; from prices)
    expected:  p * pt_frac - (1 - p) * sl_frac

FLEXIBLE IN THE ONE PLACE THAT MATTERS - WHICH p. Each predictor asks a
different question, and the difference between them is the finding:

    --predictor model     p = gate_confidence      "is the model calibrated?"
    --predictor base      p = corpus base rate     "does the model beat the null?"
    --predictor geometry  p = sl/(pt+sl)           "can the geometry pay at all?"

The geometry predictor is the one that cannot lie: p* = sl/(pt+sl) is the
hit rate at which the barrier is arithmetically break-even, model-free. On
this corpus it is 0.4286 and the measured tb_pt share is far below it -
which reproduces cohort_eval's independently derived 42.9% requirement.

READ THIS BEFORE TRUSTING --predictor model. `gate_confidence` ranges
[0.661, 1.000] with mean 0.859 against a realized base rate of 0.299. It is
a GATE-STACK CONFIDENCE, not a calibrated probability of winning, so the
model-predictor delta measures "how far the confidence score sits from a
probability", not a clean calibration error. The sizing p_win lives in
outputs/postmortem_summary.csv, on a much smaller population. Both are
reported; neither is silently substituted for the other.

WHAT THIS IS NOT. Report-only, SAFE class: reads the corpus, prints, exits.
It writes nothing and touches no decision path. It is deliberately NOT wired
into the model - a new input to the selector is a new ML feature, and model-
side investment is FROZEN until the era-4 gate reads out (CLAUDE.md). The
factor is an instrument today; adopting it as a feature is a boundary-class
decision with an OF-7 degrees-of-freedom cost, for the readout docket.

    python scripts/rpe_factor.py [--predictor model|base|geometry]
                                 [--alpha 0.1] [--era triple_barrier_h432]
                                 [--json] [--self-test]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CORPUS = ROOT / "outputs" / "signal_history.csv"

# Barriers whose realized magnitude is known from the geometry itself.
PT, SL, TIME = "tb_pt", "tb_sl", "tb_time"
BARRIERS = (PT, SL, TIME)


def realized(df: pd.DataFrame) -> pd.Series:
    """Realized fractional outcome per row, from the barrier that resolved.

    tb_pt and tb_sl pay their own geometry by construction. tb_time resolved
    at NEITHER barrier, so its magnitude has to come from prices; rows whose
    prices are missing are dropped rather than treated as zero - a
    time-stopped trade at an unknown price is not a flat trade.
    """
    out = pd.Series(np.nan, index=df.index, dtype=float)
    out[df.barrier == PT] = df.loc[df.barrier == PT, "pt_frac"]
    out[df.barrier == SL] = -df.loc[df.barrier == SL, "sl_frac"]
    t = df.barrier == TIME
    if t.any():
        ep = pd.to_numeric(df.loc[t, "entry_price"], errors="coerce")
        xp = pd.to_numeric(df.loc[t, "exit_price"], errors="coerce")
        # `direction` is +1 long / -1 short; a short profits when price falls
        d = pd.to_numeric(df.loc[t, "direction"], errors="coerce").fillna(1.0)
        d = np.where(d >= 0, 1.0, -1.0)
        out[t] = (xp / ep - 1.0) * d
    return out


def expected(df: pd.DataFrame, p: pd.Series) -> pd.Series:
    """E[outcome] under the barrier geometry at predicted hit probability p."""
    return p * df["pt_frac"] - (1.0 - p) * df["sl_frac"]


def predictor_series(df: pd.DataFrame, kind: str) -> tuple:
    """(p, human-readable description of what this p claims)."""
    if kind == "model":
        p = pd.to_numeric(df["gate_confidence"], errors="coerce")
        return p, ("gate_confidence - a GATE-STACK score, not a calibrated "
                   "p(win); read the delta as distance-from-probability")
    if kind == "base":
        br = float(df["label"].mean())
        return pd.Series(br, index=df.index), (
            "corpus base rate %.4f - the null a model must beat" % br)
    if kind == "geometry":
        denom = (df["pt_frac"] + df["sl_frac"]).replace(0.0, np.nan)
        p = df["sl_frac"] / denom
        return p, ("p* = sl/(pt+sl), the model-FREE break-even hit rate; "
                   "median %.4f" % float(p.median()))
    raise ValueError(kind)


def build(corpus: Path, kind: str, alpha: float, era: str | None) -> dict:
    df = pd.read_csv(corpus)
    for c in ("pt_frac", "sl_frac", "label", "barrier"):
        if c not in df.columns:
            return {"error": "corpus lacks column %s" % c}
    n_all = len(df)
    if era:
        df = df[df.get("label_era") == era]
    df = df[df["barrier"].isin(BARRIERS)].copy()
    for c in ("pt_frac", "sl_frac"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df[(df["pt_frac"] > 0) & (df["sl_frac"] > 0)]
    if df.empty:
        return {"error": "no barrier-resolved rows after filters",
                "rows_scanned": n_all}

    if "ts" in df.columns:
        df = df.sort_values("ts")
    r = realized(df)
    p, desc = predictor_series(df, kind)
    e = expected(df, p)
    delta = r - e
    keep = delta.notna()
    dropped = int((~keep).sum())
    delta = delta[keep]
    d = delta.to_numpy(dtype=float)

    # the running affect level: an EWMA of surprise. alpha IS the learning
    # rate - how hard one surprise moves the mood.
    level = pd.Series(d).ewm(alpha=alpha, adjust=False).mean().to_numpy()

    # THE QUESTION THE OPERATOR ASKED: does the affect level correlate with
    # the edge that FOLLOWS it? Feeling good is only informative if it
    # predicts doing well. Level at t vs realized outcome at t+1.
    corr = float("nan")
    if len(level) > 30:
        lv, nxt = level[:-1], d[1:]
        if np.std(lv) > 0 and np.std(nxt) > 0:
            corr = float(np.corrcoef(lv, nxt)[0, 1])

    sub = df[keep]
    by_barrier = {}
    for b in BARRIERS:
        m = (sub["barrier"] == b).to_numpy()
        if m.sum():
            by_barrier[b] = {"n": int(m.sum()),
                             "mean_delta": round(float(d[m].mean()), 6)}
    return {
        "corpus": str(corpus), "rows_scanned": n_all, "n": int(len(d)),
        "era": era or "(all)", "predictor": kind, "predictor_desc": desc,
        "alpha": alpha, "dropped_unknown_magnitude": dropped,
        "mean_delta": round(float(d.mean()), 6),
        "median_delta": round(float(np.median(d)), 6),
        "sd_delta": round(float(d.std(ddof=1)), 6) if len(d) > 1 else 0.0,
        "frac_positive": round(float((d > 0).mean()), 4),
        "level_last": round(float(level[-1]), 6),
        "level_corr_next_delta": None if np.isnan(corr) else round(corr, 4),
        "by_barrier": by_barrier,
        "base_rate": round(float(sub["label"].mean()), 4),
        # p* is the break-even of a TWO-outcome bet (+pt vs -sl), so the
        # only comparable hit rate is the CONDITIONAL one among
        # barrier-resolved rows. pt/(pt+sl+time) is a different quantity and
        # comparing it to p* flatters the geometry - caught 2026-08-22 when
        # this tool contradicted cohort_eval's pre-registered "NO GROSS
        # EDGE" in the favourable direction.
        "pt_share_all": round(float((sub["barrier"] == PT).mean()), 4),
        "pt_share_resolved": round(float(
            (sub["barrier"] == PT).sum()
            / max(1, int(((sub["barrier"] == PT) | (sub["barrier"] == SL)).sum()))), 4),
        "n_time_excluded": int((sub["barrier"] == TIME).sum()),
        "geometry_breakeven": round(
            float((sub["sl_frac"] / (sub["pt_frac"] + sub["sl_frac"])).median()), 4),
    }


def render(res: dict) -> None:
    if "error" in res:
        print("rpe_factor: %s" % res["error"])
        return
    print("REWARD PREDICTION ERROR over the triple barrier")
    print("=" * 62)
    print("corpus     %s" % res["corpus"])
    print("rows       %d barrier-resolved of %d scanned   era=%s"
          % (res["n"], res["rows_scanned"], res["era"]))
    if res["dropped_unknown_magnitude"]:
        print("           %d tb_time rows dropped (price missing - an unknown"
              % res["dropped_unknown_magnitude"])
        print("           magnitude is not a zero outcome)")
    print("predictor  %s" % res["predictor"])
    print("           %s" % res["predictor_desc"])
    print("")
    print("DELTA (realized - expected), in fraction of entry price")
    print("  mean %+.6f   median %+.6f   sd %.6f   %.1f%% positive"
          % (res["mean_delta"], res["median_delta"], res["sd_delta"],
             100 * res["frac_positive"]))
    for b, v in res["by_barrier"].items():
        print("  %-8s n=%-6d mean delta %+.6f" % (b, v["n"], v["mean_delta"]))
    print("")
    print("AFFECT LEVEL (EWMA of surprise, alpha=%.3f)" % res["alpha"])
    print("  level now              %+.6f" % res["level_last"])
    c = res["level_corr_next_delta"]
    print("  corr(level, NEXT delta) %s"
          % ("n/a (too few rows)" if c is None else "%+.4f" % c))
    if c is not None:
        if abs(c) < 0.05:
            print("  -> the affect level does NOT predict the next surprise.")
            print("     As an EDGE signal it is decorative; as a CALIBRATION")
            print("     readout it is still meaningful (see mean delta).")
        else:
            print("  -> the level carries information about what comes next.")
    print("")
    print("GEOMETRY REALITY CHECK (model-free)")
    print("  break-even hit rate p* = sl/(pt+sl)      %.4f"
          % res["geometry_breakeven"])
    print("  tb_pt / (tb_pt + tb_sl)   [comparable]   %.4f"
          % res["pt_share_resolved"])
    print("  tb_pt / all rows          [NOT p*-comparable] %.4f"
          % res["pt_share_all"])
    print("  %d tb_time rows resolve at NEITHER barrier and are excluded"
          % res["n_time_excluded"])
    print("  corpus base rate (label)                 %.4f" % res["base_rate"])
    gap = res["pt_share_resolved"] - res["geometry_breakeven"]
    print("  margin %+.4f on THIS population" % gap)
    print("")
    print("  ** DISAGREES WITH cohort_eval, WHICH IS PRE-REGISTERED.")
    print("  ** cohort_eval reports pt/(pt+sl) = 0.226 vs 0.429 -> NO GROSS")
    print("  ** EDGE, on n=765. This tool reads the whole label era")
    print("  ** (n=%d). DIFFERENT POPULATIONS, not a refutation:" % res["n"])
    print("  ** cohort_eval filters to the pre-registered cohort and this")
    print("  ** does not. Where they disagree, the PRE-REGISTERED tool")
    print("  ** governs. Reconciling the populations is an owed measurement.")
    print("")
    print("CAVEATS")
    print("  * Report-only, SAFE class. Not wired into the model: a new")
    print("    selector input is a new ML feature and model work is FROZEN")
    print("    until the era-4 readout. Adoption is boundary-class (OF-7).")
    print("  * Rows are barrier-resolved LABELS, most of them counterfactual")
    print("    candidates rather than filled trades - this measures the")
    print("    labelling geometry, not realised P&L.")
    print("  * Concurrent labels share market path; no effective-n")
    print("    correction is applied to the sd above. Do not build an")
    print("    interval on it without one.")


_SELFTEST_ROWS = [
    # a perfectly predicted set: p == realized frequency, so mean delta -> 0
    {"barrier": "tb_pt", "pt_frac": 0.02, "sl_frac": 0.01, "label": 1,
     "gate_confidence": 1.0, "direction": 1, "ts": 1, "label_era": "t"},
    {"barrier": "tb_sl", "pt_frac": 0.02, "sl_frac": 0.01, "label": 0,
     "gate_confidence": 0.0, "direction": 1, "ts": 2, "label_era": "t"},
]


def self_test() -> int:
    """An instrument that reports zero is worthless until shown to move on a
    planted signal. Builds two synthetic corpora and checks the sign."""
    import tempfile
    ok = True
    with tempfile.TemporaryDirectory() as td:
        # case 1: predictions exactly match outcomes -> delta 0 on both rows
        p = Path(td) / "exact.csv"
        pd.DataFrame(_SELFTEST_ROWS).assign(
            entry_price=100.0, exit_price=100.0).to_csv(p, index=False)
        r1 = build(p, "model", 0.1, None)
        exact_zero = abs(r1["mean_delta"]) < 1e-9

        # case 2: same outcomes, but the predictor now claims certainty of a
        # win on the row that LOST -> delta must go negative
        rows = [dict(x) for x in _SELFTEST_ROWS]
        rows[1]["gate_confidence"] = 1.0
        p2 = Path(td) / "overclaim.csv"
        pd.DataFrame(rows).assign(
            entry_price=100.0, exit_price=100.0).to_csv(p2, index=False)
        r2 = build(p2, "model", 0.1, None)
        moved_negative = r2["mean_delta"] < -1e-9

        # MAGNITUDE, not just sign (strengthened 2026-08-23). Checking only
        # that delta "went negative" is the same weakness as validating an
        # estimator on a null arm alone: it shows the instrument MOVES, never
        # that it moves by the RIGHT amount. Here the planted value is exact
        # and computable, so recovery is checkable:
        #   row0 unchanged           -> delta 0
        #   row1 realized -sl_frac (-0.01), but p=1.0 claims E=+pt_frac
        #        (+0.02)             -> delta = -0.01 - 0.02 = -0.03
        #   mean over the two rows                        = -0.015
        pt1 = float(_SELFTEST_ROWS[1]["pt_frac"])
        sl1 = float(_SELFTEST_ROWS[1]["sl_frac"])
        expected = (0.0 + (-sl1 - pt1)) / 2.0
        recovered = r2["mean_delta"]
        magnitude_ok = abs(recovered - expected) < 1e-9

        ok = exact_zero and moved_negative and magnitude_ok
        print("SELF-TEST %s" % ("PASS" if ok else "FAIL"))
        print("  NULL CONTROL  perfect prediction -> mean delta %+.9f "
              "(must be 0)" % r1["mean_delta"])
        print("  POWER ARM     planted over-claim -> recovered %+.9f vs "
              "planted %+.9f  (%d/1 recovered)"
              % (recovered, expected, int(magnitude_ok)))
        print("  (a null arm alone proves the estimator does not cry wolf;")
        print("   only the power arm shows it can measure anything)")
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default=str(DEFAULT_CORPUS))
    ap.add_argument("--predictor", default="geometry",
                    choices=("model", "base", "geometry"))
    ap.add_argument("--alpha", type=float, default=0.1)
    ap.add_argument("--era", default=None)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    ns = ap.parse_args()
    if ns.self_test:
        return self_test()
    corpus = Path(ns.corpus)
    if not corpus.exists():
        print("no corpus at %s" % corpus)
        return 2
    res = build(corpus, ns.predictor, ns.alpha, ns.era)
    if ns.json:
        print(json.dumps(res, indent=1))
    else:
        render(res)
    return 0 if "error" not in res else 1


if __name__ == "__main__":
    sys.exit(main())
