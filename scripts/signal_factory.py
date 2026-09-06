"""scripts/signal_factory.py — generate many candidate signals, kill almost all.

WHY THIS EXISTS. The repo evaluates signals one batch at a time, by hand. That
is how you get "5 of 64 features read DIRECTIONAL" and cannot say whether five
is a finding or what chance produces — and it is how a search spread across ten
sessions quietly accumulates a multiple-comparisons debt nobody is counting.

This is the other half of the method the rest of this codebase already applies
everywhere else: a PRE-REGISTERED grid, scored through the EXISTING instrument,
against the MEASURED chance rate, with the batch's multiplicity controlled, and
every trial written to a durable ledger so the count survives the session that
made it.

WHAT IT REUSES, DELIBERATELY (prior-art pass 2026-09-05):
  scripts/label_decomposition_report.decompose      the three-AUC split
  ...                     .null_calibration         the REALISED chance rate
  ...                     .load_production_corpus    era-clean corpus + metadata
  scripts/geometry_search.py already does pre-registered grid + Bonferroni for
  EXIT geometry; this is the entry-SIGNAL sibling, not a replacement.
Nothing here re-implements an AUC, a bootstrap or a day block.

THE SPLIT IS THE POINT. A feature scored against a triple-barrier label mixes
RESOLUTION (did the path touch a barrier — volatility loads this and it carries
NO edge) with DIRECTION (which barrier — the only channel that is an edge). A
raw-label AUC is a blend of the two, and reporting one alone is the exact
misread this repo has made twice. Survivors are judged on DIRECTION only.

THE GRID IS PRE-REGISTERED AND ITS SIZE IS KNOWN BEFORE THE DATA IS TOUCHED.
That is what separates a search from a fishing expedition: the denominator of
the multiple-comparisons correction cannot be chosen after seeing the results.

SURVIVING THE STATISTICS IS NOT THE BAR — PAYING FOR ITSELF IS. Every survivor
is then run through `cost_screen` against a break-even band derived from the
shipped barrier geometry (`ml.labeling.barrier_geometry`, the same pure
function the labeler and the live exit engine call). Measured 2026-09-05, and
the reason this screen exists: the v1 grid's best survivor REPLICATED across a
time-ordered split and still could not clear its own rake. A tool that printed
the AUC and stopped would have promoted it.

LEDGER SCHEMA IS FROZEN AT v1 ON PURPOSE. The cost screen is reported, never
appended: the ledger already holds >1,400 rows, and widening a CSV header in
place tears the file for every reader of the old rows. If the screen ever needs
persisting it gets its OWN file with its own schema — see the history
schema-loss incident for what the other choice costs.

Report-only. Reads the corpus and writes its ledger; touches no config, no
engine state, no order path. SAFE under the era-6 moratorium.

    python scripts/signal_factory.py --dry-run     # print the grid, score nothing
    python scripts/signal_factory.py --reps 200
    python scripts/signal_factory.py --self-test
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from itertools import combinations
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.label_decomposition_report import (  # noqa: E402
    DEFAULT_REPS, DEFAULT_SEED, FLAG_DIR, ci_excludes_half, decompose,
    load_production_corpus, null_calibration)

LEDGER_PATH = ROOT / "outputs" / "signal_trials.csv"
SCHEMA_VERSION = 1
LEDGER_COLUMNS = ("schema_version", "run_utc", "grid_id", "signal_id",
                  "family", "n", "n_resolved", "ndays", "direction_auc",
                  "dir_lo", "dir_hi", "flag", "corpus_sha", "era")

# ---------------------------------------------------------------- the grid
# PRE-REGISTERED. Changing any of this changes the multiple-comparisons
# denominator, so it is a deliberate act with a new GRID_ID, never a tweak.
GRID_ID = "v1-2026-09-05"

# Families, each a pure row-wise transform of the stored features. Row-wise on
# purpose: the corpus is one row per signal EVENT, not a per-asset time series,
# so a lag or a rolling window would need a per-asset regrouping that this
# version does not do (see WHAT THIS CANNOT SEE at the bottom).
FAMILY_SIGN = "sign"          # direction only, magnitude discarded
FAMILY_ABS = "abs"            # magnitude only, direction discarded
FAMILY_PROD = "prod"          # pairwise interaction
FAMILIES = (FAMILY_SIGN, FAMILY_ABS, FAMILY_PROD)

# Interactions are the genuinely unexplored space: every stored feature has
# already been scored ALONE and none is directional, while the deployed model
# is linear in them. Pairs are drawn from the features that are actually
# LEARNABLE - a feature whose decile edges are tied can never carry drift and
# is near-constant, so pairing it multiplies noise by noise.
MIN_DISTINCT_FOR_PAIRING = 20


def _finite(x: np.ndarray) -> np.ndarray:
    return np.asarray(x, float).reshape(-1)


def learnable_features(X: np.ndarray, names: list) -> list:
    """Feature names with enough distinct values to be worth pairing.

    Not a fitted knob: it separates a continuous score from a flag. A column
    with two distinct values across 15k rows is a flag whatever its name, and
    the product of two flags is a rarer flag, not a richer signal.
    """
    out = []
    for j, nm in enumerate(names):
        col = X[:, j]
        col = col[np.isfinite(col)]
        if col.size and np.unique(col).size >= MIN_DISTINCT_FOR_PAIRING:
            out.append(nm)
    return out


def build_grid(X: np.ndarray, names: list) -> dict:
    """The pre-registered candidate set. Pure: no scoring, no I/O.

    Returns {signal_id: (family, ndarray)}. Size is knowable before any
    result is seen, which is the property the correction below depends on.
    """
    idx = {nm: j for j, nm in enumerate(names)}
    pairable = learnable_features(X, names)
    cand: dict = {}
    for nm in names:
        col = _finite(X[:, idx[nm]])
        cand[f"sign({nm})"] = (FAMILY_SIGN, np.sign(col))
        cand[f"abs({nm})"] = (FAMILY_ABS, np.abs(col))
    for a, b in combinations(sorted(pairable), 2):
        cand[f"{a}*{b}"] = (FAMILY_PROD,
                            _finite(X[:, idx[a]]) * _finite(X[:, idx[b]]))
    return cand


# ------------------------------------------------- multiplicity accounting
def benjamini_hochberg(pvals: list, q: float = 0.05) -> list:
    """Indices surviving BH-FDR at level q. Empty list is a valid answer."""
    m = len(pvals)
    if not m:
        return []
    order = sorted(range(m), key=lambda i: pvals[i])
    keep_upto = -1
    for rank, i in enumerate(order, start=1):
        if pvals[i] <= q * rank / m:
            keep_upto = rank
    return [order[r] for r in range(keep_upto)] if keep_upto > 0 else []


def ci_to_p(lo: float, hi: float) -> float:
    """Two-sided p for H0: AUC = 0.5, from a bootstrap percentile CI.

    Normal approximation on the CI half-width - the CI is the primary object
    here and the p-value exists only to feed BH. Deliberately crude and
    labelled as such: a bootstrap CI already carries the day-block structure,
    and inventing a sharper p from it would be false precision.
    """
    if lo is None or hi is None:
        return 1.0
    centre = 0.5 * (lo + hi)
    se = max((hi - lo) / (2 * 1.96), 1e-12)
    z = abs(centre - 0.5) / se
    return math.erfc(z / math.sqrt(2.0))


# ------------------------------------------------------------- the cost bar
# An AUC is not money. A candidate that replicates out of sample and still
# cannot cover its own rake is not a signal you can trade, and the ONLY way to
# know which it is is to convert it into the units the rake is denominated in.
# Measured 2026-09-05: the best survivor of the v1 grid replicated across a
# time-ordered split and STILL died here, so this screen is not decoration.
VERDICT_CLEARS = "CLEARS_COST"
VERDICT_CANNOT = "CANNOT_PAY"
VERDICT_UNDET = "UNDETERMINED"
RESOLVED_PT, RESOLVED_SL = "tb_pt", "tb_sl"
MIN_RULE_ROWS = 100          # below this the win rate is not worth a verdict


def break_even_band(ml_cfg: dict) -> tuple:
    """P(take-profit) a rule must beat to pay, as a BAND — never a point.

    Barriers here are VOLATILITY-SCALED and cost-floored, so there is no single
    break-even win rate. A win pays pt, a loss pays sl, every round trip pays
    cost, so the break-even is

        w_be(sigma) = (sl(sigma) + cost) / (pt(sigma) + sl(sigma))

    which DECREASES in sigma — the wider the barriers, the less the fixed cost
    matters. Hence a band, evaluated at the two extremes:
      hi = w_be at the cost floor   (sigma_bar -> 0, the most hostile case)
      lo = w_be as sigma -> infinity (cost negligible: sl_mult/(pt+sl)_mult)

    A rule whose CI lies wholly below `lo` cannot pay at ANY volatility. One
    wholly above `hi` pays at every volatility. Anything between is undetermined
    and must NOT be reported as an edge.

    A PROPERTY WORTH KNOWING, and it is not intuitive (measured 2026-09-05, and
    it broke the first version of this function's test): the hostile end is
    INVARIANT TO THE FEE LEVEL. At the floor the barriers are *defined* as a
    multiple of cost, so cost cancels out of the ratio —

        w_be(floor) = (sl_mult*pt_cost_mult + pt_mult)
                      / ((pt_mult + sl_mult) * pt_cost_mult)

    which at the shipped 8/6/4.0 is 32/56 = 0.5714 whether fees are 5bps or
    500. Raising fees does NOT raise the win rate required at the floor; it
    pushes MORE ROWS ONTO the floor, moving the corpus toward the hostile end
    of the band. So a fee rise shows up as a change in the MIX, never in this
    number — do not read a stable `hi` as evidence that fees do not matter.

    Geometry comes from ml.labeling.barrier_geometry — the same pure function
    the candidate labeler and the live bracket-exit engine both call — so this
    band cannot drift away from the bet actually being labelled and traded.
    Nothing here is a literal.
    """
    from ml.labeling import barrier_geometry
    cost_pct = float(ml_cfg.get("label_round_trip_cost_pct", 0.0) or 0.0)
    pt_m = float(ml_cfg.get("label_pt_vol_mult", 0.0) or 0.0)
    sl_m = float(ml_cfg.get("label_sl_vol_mult", 0.0) or 0.0)
    ptc = float(ml_cfg.get("label_pt_cost_mult", 0.0) or 0.0)
    cost = cost_pct / 100.0
    # generous end: barriers so wide the fixed cost is negligible
    pt_b, sl_b = barrier_geometry(1e6, cost_pct, pt_m, sl_m, ptc)
    lo = ((sl_b + cost) / (pt_b + sl_b)) if (pt_b + sl_b) > 0 else float("nan")
    # hostile end: sigma_bar 0 lets the cost floor set the geometry. With no
    # cost floor (zero cost, or pt_cost_mult=0) that degenerates to 0/0 — and
    # correctly so: with nothing to recover, break-even IS the barrier ratio at
    # every sigma and the band collapses to a point. Returning NaN there would
    # hand every verdict an unorderable bound.
    pt_f, sl_f = barrier_geometry(0.0, cost_pct, pt_m, sl_m, ptc)
    hi = ((sl_f + cost) / (pt_f + sl_f)) if (pt_f + sl_f) > 0 else lo
    return (lo, hi) if lo <= hi else (hi, lo)


def rule_win_rate(x: np.ndarray, barrier: np.ndarray, sig: np.ndarray,
                  flip: bool, reps: int = DEFAULT_REPS,
                  seed: int = DEFAULT_SEED) -> dict:
    """Realised P(tb_pt) among the RESOLVED rows a sign rule selects.

    DIRECTION channel only (resolved rows), for the reason the module docstring
    gives: scoring on all rows re-mixes RESOLUTION back in.

    The interval is a DAY-BLOCK bootstrap drawn from the same helpers
    decompose() uses — rows inside one day are not independent draws, and an
    iid interval here would manufacture the significance this screen exists to
    withhold.

    AND IT CARRIES decompose()'s BLOCK FLOOR, for the same reason decompose()
    does. A percentile bootstrap over a handful of blocks does not merely get
    noisy, it COLLAPSES: every draw repeats the same few days, the resampled
    mean barely moves, and the interval comes back NARROW. Measured while
    writing this function's own tests — 3 blocks returned width 0.0170 against
    0.0347 at 60 blocks, i.e. the thinnest evidence produced the most confident
    interval. Without this floor a rule that fires on three days could be
    reported CLEARS_COST on a manufactured CI, which is the exact false
    promotion this whole module exists to prevent. `ndays` is reported either
    way so the refusal is visible rather than silent.
    """
    from scripts.label_decomposition_report import (
        MIN_CI_DAYS, day_index, draw_day_weights)
    x = _finite(x)
    b = np.asarray(barrier).astype(str)
    resolved = np.isin(b, (RESOLVED_PT, RESOLVED_SL))
    fires = (x < 0) if flip else (x > 0)
    m = resolved & np.isfinite(x) & fires
    n = int(m.sum())
    out = {"n": n, "flip": bool(flip), "p_pt": None, "ci": None, "ndays": 0}
    if n < MIN_RULE_ROWS:
        return out
    won = (b[m] == RESOLVED_PT).astype(float)
    row_day, ndays = day_index(np.asarray(sig, float)[m])
    out["ndays"] = int(ndays)
    out["p_pt"] = round(float(won.mean()), 4)
    if ndays < MIN_CI_DAYS:
        out["few_blocks"] = True
        return out                      # a point estimate, but NO interval
    W = draw_day_weights(row_day, ndays, reps, seed)
    tot = W.sum(axis=1)
    good = tot > 0
    if not good.any():
        return out
    means = (W[good] * won).sum(axis=1) / tot[good]
    out["ci"] = [round(float(v), 4) for v in np.percentile(means, [2.5, 97.5])]
    return out


def cost_screen(signal_id: str, x: np.ndarray, direction_auc, barrier,
                sig, band: tuple, reps: int = DEFAULT_REPS,
                seed: int = DEFAULT_SEED) -> dict:
    """One candidate, converted from an AUC into a verdict about money.

    The traded rule is the sign rule the measured DIRECTION AUC implies: below
    0.5 the feature is ANTI-predictive with the trade's own sign, so the rule
    is the FLIP. That choice is made by the already-scored AUC, not by trying
    both sides and keeping the better one — picking the better side would be an
    extra, uncounted comparison per candidate.
    """
    lo, hi = band
    flip = (direction_auc is not None) and (float(direction_auc) < 0.5)
    r = rule_win_rate(x, barrier, sig, flip=flip, reps=reps, seed=seed)
    ci = r.get("ci")
    if ci is None:
        verdict = VERDICT_UNDET
    elif ci[0] > hi:
        verdict = VERDICT_CLEARS
    elif ci[1] < lo:
        verdict = VERDICT_CANNOT
    else:
        verdict = VERDICT_UNDET
    return {"signal": signal_id, "direction_auc": direction_auc,
            "rule": "x<0" if flip else "x>0", "p_pt": r["p_pt"], "ci": ci,
            "n": r["n"], "ndays": r["ndays"],
            "break_even": [round(lo, 4), round(hi, 4)], "verdict": verdict}


# ------------------------------------------------------------ the ledger
def append_trials(rows: list, path: Path = LEDGER_PATH) -> None:
    """Durable append so the multiplicity count survives the session.

    Routed through core.runtime.durable_append for the same reason
    scripts/trial_ledger.py is: a kill mid-append must not weld two records
    into one and lose BOTH. This ledger only ever DEEPENS the correction -
    a trial that happened cannot be un-counted by forgetting it.
    """
    from core.runtime import durable_append
    header = ",".join(LEDGER_COLUMNS)
    for r in rows:
        def render(fh, _r=r):
            csv.writer(fh, lineterminator="").writerow(
                [_r.get(c, "") for c in LEDGER_COLUMNS])
        durable_append(path, render, header=header, newline="\n")


def cumulative_trials(path: Path = LEDGER_PATH) -> int:
    """How many candidate signals have EVER been scored on this corpus.

    This is the honest denominator. A search spread over ten sessions is one
    search; counting only today's batch is how a chance winner is promoted.
    """
    try:
        with open(path, newline="", encoding="utf-8") as fh:
            return sum(1 for _ in csv.DictReader(fh))
    except OSError:
        return 0


# ------------------------------------------------------------------ run
def run(reps: int, seed: int, q: float, dry_run: bool) -> dict:
    import hashlib
    import os
    os.chdir(ROOT)                     # load_production_corpus reads relatively
    corpus = load_production_corpus()
    X, y = corpus["X"], corpus["y"]
    barrier, sig = corpus["barrier"], corpus["sig"]
    names = list(corpus["feature_names"])

    grid = build_grid(np.asarray(X, float), names)
    out: dict = {
        "grid_id": GRID_ID, "n_candidates": len(grid), "reps": reps, "seed": seed,
        "q": q, "n_rows": int(np.asarray(y).size), "era": corpus.get("current_era"),
        "families": {f: sum(1 for v in grid.values() if v[0] == f) for f in FAMILIES},
        "cumulative_trials_before": cumulative_trials(),
    }
    if dry_run:
        out["dry_run"] = True
        return out

    feats = {k: v[1] for k, v in grid.items()}
    rows = decompose(feats, y, barrier, sig, reps=reps, seed=seed)

    # The MEASURED chance rate at THIS batch size, on THESE rows and day
    # blocks - not the nominal 5%, which the instrument's own docstring says
    # to quote for neither the synthetic nor the real corpus.
    null = null_calibration(y, barrier, sig, n_features=min(len(grid), 200),
                            reps=reps, seed=seed)
    dir_rate = (null.get("direction") or {}).get("rate")
    out["null"] = {"direction_exclusion_rate": dir_rate,
                   "expected_directional_by_chance":
                       round(dir_rate * len(grid), 1) if dir_rate else None}

    pvals, idx_map = [], []
    for i, r in enumerate(rows):
        ci = r.get("direction_ci")
        pvals.append(ci_to_p(*(ci if ci else (None, None))))
        idx_map.append(i)
    survivors_i = benjamini_hochberg(pvals, q=q)
    out["bh_survivors"] = len(survivors_i)
    out["raw_direction_flags"] = sum(1 for r in rows if r.get("flag") == FLAG_DIR)

    surv = []
    for i in sorted(survivors_i, key=lambda k: pvals[k]):
        r = rows[i]
        ci = r.get("direction_ci") or (None, None)
        surv.append({"signal": r["feature"], "family": grid[r["feature"]][0],
                     "direction_auc": r.get("direction_auc"),
                     "ci": list(ci), "p": round(pvals[i], 6),
                     "flag": r.get("flag"), "n": r.get("n"),
                     "ndays": r.get("ndays")})
    out["survivors"] = surv

    # THE COST BAR. Surviving multiplicity control earns a candidate the right
    # to be measured in money, nothing more. Screening here rather than leaving
    # it to the reader is deliberate: the v1 grid's best survivor replicated
    # out of sample and still could not clear its own rake, and a tool that
    # prints AUCs without that verdict invites exactly the promotion this whole
    # file exists to prevent.
    with open(ROOT / "config.json", encoding="utf-8") as fh:
        ml_cfg = json.load(fh).get("ml", {})
    band = break_even_band(ml_cfg)
    out["break_even_band"] = [round(band[0], 4), round(band[1], 4)]
    screen = [cost_screen(s["signal"], grid[s["signal"]][1],
                          s["direction_auc"], barrier, sig, band,
                          reps=reps, seed=seed) for s in surv]
    out["cost_screen"] = screen
    out["clears_cost"] = sum(1 for s in screen if s["verdict"] == VERDICT_CLEARS)
    out["cannot_pay"] = sum(1 for s in screen if s["verdict"] == VERDICT_CANNOT)
    out["undetermined"] = sum(1 for s in screen if s["verdict"] == VERDICT_UNDET)

    csha = hashlib.sha256(np.asarray(y, float).tobytes()).hexdigest()[:12]
    import datetime as _dt
    stamp = _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")
    append_trials([{
        "schema_version": SCHEMA_VERSION, "run_utc": stamp, "grid_id": GRID_ID,
        "signal_id": r["feature"], "family": grid[r["feature"]][0],
        "n": r.get("n"), "n_resolved": r.get("n_resolved"), "ndays": r.get("ndays"),
        "direction_auc": r.get("direction_auc"),
        "dir_lo": (r.get("direction_ci") or ["", ""])[0],
        "dir_hi": (r.get("direction_ci") or ["", ""])[1],
        "flag": r.get("flag"), "corpus_sha": csha, "era": corpus.get("current_era"),
    } for r in rows])
    out["cumulative_trials_after"] = cumulative_trials()
    return out


def self_test() -> int:
    """Positive and negative arms on synthetic data. A factory that cannot be
    shown to FIND a planted signal, and to REJECT pure noise, is decoration."""
    rng = np.random.default_rng(7)
    n = 4000
    y = (rng.random(n) < 0.5).astype(float)
    barrier = np.where(rng.random(n) < 0.75,
                       np.where(y > 0.5, "tb_pt", "tb_sl"), "tb_time")
    sig = np.sort(rng.integers(1_780_000_000, 1_782_600_000, size=n).astype(float))
    fails = []

    planted = (y - 0.5) * 2.0 + rng.normal(0, 0.6, n)      # a real edge
    noise = {f"n{i}": rng.normal(size=n) for i in range(12)}
    rows = decompose({"planted": planted, **noise}, y, barrier, sig, reps=120, seed=1)
    by = {r["feature"]: r for r in rows}
    if not ci_excludes_half(by["planted"].get("direction_ci")):
        fails.append("POSITIVE ARM: a planted directional signal was NOT detected")
    noisy_hits = sum(1 for k in noise if ci_excludes_half(by[k].get("direction_ci")))
    # THE TOLERANCE IS DELIBERATELY LOOSE AND THE PRINTED RATE IS THE POINT.
    # Measured here: 4/12 = 33% of pure-noise controls exclude 0.5, against a
    # NOMINAL 5%. That gap is not a defect in the bootstrap - it is the reason
    # this module scores survivors against `null_calibration`'s MEASURED chance
    # rate instead of the nominal one, and the reason a raw flag count is
    # meaningless on its own (the live grid threw 217 raw flags where noise
    # alone predicts 145). A tight bound here would be a false claim about an
    # instrument whose real null rate is this high; surfacing the number is
    # worth more than pretending it is 5%.
    if noisy_hits > 4:
        fails.append(f"NEGATIVE ARM: {noisy_hits}/12 pure-noise features excluded 0.5")

    if benjamini_hochberg([0.9, 0.8, 0.7]):
        fails.append("BH accepted a batch with no small p-values")
    if len(benjamini_hochberg([1e-9] * 5)) != 5:
        fails.append("BH rejected a batch that is all strongly significant")
    if benjamini_hochberg([]) != []:
        fails.append("BH did not handle an empty batch")

    # COST-BAR ARMS. A screen that cannot be shown to PASS a payer and REFUSE
    # a loser is decoration, exactly as above.
    band = break_even_band({"label_round_trip_cost_pct": 0.6,
                            "label_pt_vol_mult": 8, "label_sl_vol_mult": 6,
                            "label_pt_cost_mult": 4.0})
    if not (0.0 < band[0] < band[1] < 1.0):
        fails.append(f"break-even band is not an ordered probability: {band}")
    # a rule that wins far above the band must CLEAR; far below must be REFUSED
    nb = np.where(rng.random(n) < 0.5, RESOLVED_PT, RESOLVED_SL)
    # AUC >= 0.5 -> no flip -> the rule is x>0. Make x>0 land on tb_pt.
    winner = np.where(nb == RESOLVED_PT, 1.0, -1.0)
    v_win = cost_screen("winner", winner, 0.99, nb, sig, band)["verdict"]
    if v_win != VERDICT_CLEARS:
        fails.append("COST ARM: a rule that always takes profit did not CLEAR")
    # AUC < 0.5 -> FLIP -> the rule is x<0. Make x<0 land on tb_sl, so the
    # rule genuinely selects losers. (Negating `winner` instead would put x<0
    # on tb_pt and the flip would correctly find the WINNING side - a fixture
    # that tests nothing. Caught by this arm on 2026-09-05.)
    loser = np.where(nb == RESOLVED_SL, -1.0, 1.0)
    v_lose = cost_screen("loser", loser, 0.01, nb, sig, band)["verdict"]
    if v_lose != VERDICT_CANNOT:
        fails.append("COST ARM: a rule that always stops out was not REFUSED")

    for f in fails:
        print("FAIL:", f)
    # REPORT THE MEASURED RATE, not a bare PASS. A self-test that only says
    # "ok" proves the instrument does not cry wolf; it never shows the
    # instrument can DETECT anything, and it hides how often the null arm
    # fires. scripts/instrument_contract.check_self_tests enforces this on
    # every --self-test in the repo, and it caught this file on 2026-09-05.
    rate = noisy_hits / len(noise) if noise else 0.0
    print("  positive arm : planted directional signal "
          f"{'DETECTED' if ci_excludes_half(by['planted'].get('direction_ci')) else 'MISSED'}"
          f" (direction AUC {by['planted'].get('direction_auc')})")
    print(f"  negative arm : {noisy_hits}/{len(noise)} pure-noise controls "
          f"wrongly flagged = {100.0 * rate:.1f}% false-positive rate")
    print(f"  cost arms    : winner -> {v_win}, loser -> {v_lose}"
          f"  (break-even band {tuple(round(v, 4) for v in band)})")
    print(f"self-test: {'PASS' if not fails else 'FAIL'} ({len(fails)} failure(s))")
    return 1 if fails else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--reps", type=int, default=DEFAULT_REPS)
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED)
    ap.add_argument("--q", type=float, default=0.05, help="BH-FDR level")
    ap.add_argument("--dry-run", action="store_true",
                    help="print the pre-registered grid and its size; score nothing")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        return self_test()

    res = run(a.reps, a.seed, a.q, a.dry_run)
    if a.json:
        print(json.dumps(res, indent=2, default=str))
        return 0

    print("=" * 70)
    print(f"SIGNAL FACTORY — grid {res['grid_id']}")
    print("=" * 70)
    print(f"  candidates      : {res['n_candidates']}  {res['families']}")
    print(f"  corpus rows     : {res['n_rows']}   era: {res['era']}")
    print(f"  trials before   : {res['cumulative_trials_before']}")
    if res.get("dry_run"):
        print("\n  DRY RUN — nothing scored, nothing written.")
        return 0
    nl = res["null"]
    print(f"  measured chance : {nl['direction_exclusion_rate']} exclusion rate"
          f"  -> {nl['expected_directional_by_chance']} DIRECTIONAL flags"
          f" expected from noise alone at this batch size")
    print(f"  raw DIR flags   : {res['raw_direction_flags']}")
    print(f"  BH-FDR q={res['q']}  survivors: {res['bh_survivors']}")
    print(f"  trials after    : {res['cumulative_trials_after']}"
          f"   <- the honest multiple-comparisons denominator, cumulative")
    print()
    if not res["survivors"]:
        print("  NO SURVIVORS. That is a result, not a failure: this grid")
        print("  contains no signal distinguishable from noise on this corpus.")
        return 0

    print("  SURVIVORS (DIRECTION channel only):")
    for s in res["survivors"][:25]:
        print(f"    {s['signal'][:44]:46s} AUC {s['direction_auc']}"
              f"  CI {s['ci']}  p={s['p']}")
    band = res["break_even_band"]
    print()
    print("=" * 70)
    print(f"  THE COST BAR — break-even P(take-profit) band {band[0]} .. {band[1]}")
    print("=" * 70)
    print("    derived from the shipped barrier geometry via "
          "ml.labeling.barrier_geometry;")
    print(f"    {band[0]} applies when barriers dwarf cost, {band[1]} at the "
          f"cost floor.")
    print("    A rule must beat the band to pay. Below it, no volatility "
          "saves it.")
    print()
    for s in res["cost_screen"][:25]:
        print(f"    {s['signal'][:40]:42s} rule {s['rule']:5s} "
              f"P(pt)={s['p_pt']} CI {s['ci']}  n={s['n']} d={s['ndays']}")
        print(f"    {'':42s} -> {s['verdict']}")
    print()
    print(f"  CLEARS_COST {res['clears_cost']}   CANNOT_PAY {res['cannot_pay']}"
          f"   UNDETERMINED {res['undetermined']}")
    print()
    print("  A survivor is a CANDIDATE, not a finding. Surviving multiplicity")
    print("  control earns it the right to be measured in money, nothing more.")
    print("  Before it may be believed it still needs an out-of-sample repeat")
    print("  and a plausible mechanism — neither of which this tool measures.")
    if not res["clears_cost"]:
        print()
        print("  NOTHING CLEARED THE COST BAR. Report that as the result.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
