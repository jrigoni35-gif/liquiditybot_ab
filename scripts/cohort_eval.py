"""scripts/cohort_eval.py — pre-registered cohort evaluation of the 432-bar
migration, with era segmentation and an exit-asymmetry decomposition.

WHY THIS EXISTS. On 2026-08-02 the operator asked why the bot was profitable.
It was not: net -$50.44 over 20 days, and -$12.42 of that in the last 48
hours. What HAD changed was live_clean going 0 -> 24, the learning loop
restarting after the migration. Learning-loop-repaired and
strategy-profitable are different claims, and conflating them is how a losing
system keeps getting funded.

This tool exists so the next reading is settled by a rule written BEFORE the
data arrives rather than by whatever the number happens to be that morning.

THREE THINGS IT DOES, all of which the boards cannot:

1. PRE-REGISTRATION. The stopping rule is a constant in this file, committed
   to git, timestamped. MIN_COHORT_N is 50 closed trades under the new
   geometry. 48 hours at a 36-hour horizon is barely one horizon-length: a
   win rate off six trades has a Wilson interval so wide it is consistent
   with both ruin and riches, so reading it is worse than not looking.
   The tool REFUSES to render a verdict below the threshold.

2. ERA SEGMENTATION. Never one blended win rate. Nearly all of the 200-trade
   performance window is old-geometry, so a blended figure moves for purely
   COMPOSITIONAL reasons - it can show "recovery" purely because old losers
   aged out of the window, with no change in behaviour whatsoever. Cohorts
   are split at the migration commit (7566ea88, 2026-08-01 20:27:08 -0500).

3. EXIT ASYMMETRY. Win rate 5.5% together with payoff ratio 0.409 should not
   co-occur: a low win rate is normal when winners are LARGE. Small winners
   AND few of them means either winners are cut early or costs dominate. The
   decomposition below separates those two, because they have opposite fixes
   - one is an exit-policy bug, the other says the geometry cannot pay at
   this horizon no matter how good the selector is.

   The discriminator is MFE (max favourable excursion) against realized:
     capture   = realized / MFE   how much of the available move was taken
     cost drag = MAE  - realized  loss NOT explained by price moving against
   A trade with MFE +0.307%, MAE -0.075% and realized -0.410% never moved
   0.41% against you in the first place. That is not an exit problem.

    python scripts/cohort_eval.py [--json] [--csv PATH]

Report-only. Reads outputs/postmortem_summary.csv (432-cohort sections) and
outputs/fills.csv (era-4 section), touches no decision path.

KNOWN CENSORING, measured 2026-08-10 and left in place deliberately: the
432-cohort sections read postmortem_summary.csv, and ml/postmortem.py records
only trades that UNDERPERFORMED entry-time EV (shortfall > max(0.10*|EV|,
0.25%)). Coverage of entry-opened closes is 85.1% pre-432 / 93.1% post-432,
which biases the win rate LOW by a measured -1.5pp / -5.4pp. The bias runs
the same direction in both cohorts, so the comparison stands; the absolute
win rates read a few points worse than truth. The original registration is
not rewritten mid-flight - the era-4 gate below reads the COMPLETE population
instead, which is the fix applied where it can still be applied honestly:
before the data exists.
"""
import argparse
import collections
import csv
import json
import math
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Legs that OPEN risk - a hedge opens a position exactly as an entry does
# (main.py debits the entry fee for every non-exit leg). Reconstruction must
# treat both as opening legs or hedge-opened trips read as still-open and
# vanish - the defect that inverted breakeven_test's verdict. Pinned by
# tests/test_opening_leg_pin.py.
_OPEN_PURPOSES = ("entry", "hedge")

# --- PRE-REGISTERED, 2026-08-02. Changing these after seeing the data is
# --- exactly the thing pre-registration exists to prevent; if they must
# --- change, say so in the commit message and say why.
MIGRATION_TS = 1785634028      # 7566ea88, 432-bar migration
MIN_COHORT_N = 50              # closed trades before ANY verdict
STOP_IF_NET_PCT_BELOW = -1.0   # cohort mean net % per trade -> stand down
CONTINUE_IF_NET_PCT_ABOVE = 0.0
_PREREG = "2026-08-02"

# --- PRE-REGISTERED, 2026-08-10, at era-4 n=1 - the only honest moment to
# --- register a stopping rule for a cohort: before the data exists. Same
# --- discipline as above: changing these after the cohort accrues is the
# --- thing pre-registration exists to prevent.
#
# ERA 4 = execution-era boundary #4 (commit aeeaae36): the fill simulator
# stopped double-counting the market crossing, so era-4 fills are the first
# whose per-order fill rate matches what the recorded market actually
# granted. Every earlier era was measured under a ~1.88x near-touch fill
# inflation; era-4 numbers are therefore the first citable ones.
#
# POPULATION: entry-opened closed round trips reconstructed from fills.csv -
# the COMPLETE population, not the postmortem (underperformer-censored) set.
# Hedge-opened trips are reconstructed (a hedge is an opening leg) but are
# NOT the strategy's trades: a hedge is insurance and loses by design, the
# same split main.py:1671 applies to the performance ledger.
#
# READOUT RULE, registered before the data (adjudicated with the operator
# 2026-08-10, CAIO review): the tool never decides - it names which decision
# has become decidable.
#   gross mean <= 0 AND gross median <= 0  -> "NO GROSS EDGE": the
#       stop-strategy question goes to the operator. No execution, cost or
#       model change is on the table, because none of them create
#       expectancy (scripts/breakeven_test.py's corrected verdict).
#   gross > 0, net <= 0                    -> "COST-BOUND": an edge exists
#       and fees eat it; the fee levers held behind h432 become the live
#       discussion.
#   net > 0                                -> "CONTINUE".
B4_TS = datetime(2026, 8, 10, 11, 3, 35,
                 tzinfo=timezone.utc).timestamp()   # aeeaae36, UTC instant
# CAPITAL EPOCH AMENDMENT (2026-08-10T23:05:27Z, operator-adjudicated
# stressor): the paper account reset 5000 -> 800 with the $100/month RP-072
# ladder. The verdict population starts at the RESET instant, not merely at
# boundary #4 - the 3 closes accrued between them were $5000-regime trades
# whose sizing floors ($15 min ticket = 0.3% of equity then, 1.9% now)
# differ enough to shift the gross%% distribution. Amended at accrual n=3,
# BEFORE any new-regime data existed: the book was flat and entries were
# OFF across the instant, so the boundary has zero in-flight ambiguity.
# The registration's rules (n=50, three readouts) are UNCHANGED.
CAPITAL_EPOCH_TS = datetime(2026, 8, 10, 23, 5, 27,
                            tzinfo=timezone.utc).timestamp()
ERA4_MIN_N = 50                # entry-opened closes before ANY verdict
_PREREG_ERA4 = "2026-08-10"
_PREREG_CAPITAL = "2026-08-10T23:05:27Z"


def wilson(k: int, n: int, z: float = 1.96):
    """Wilson score interval — the honest interval for a proportion at small n.

    The normal approximation puts the bound outside [0,1] and understates
    width exactly where it matters most (few trades), which is the regime
    this whole tool is about.
    """
    if n == 0:
        return (0.0, 0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (p, max(0.0, c - h), min(1.0, c + h))


def _f(row, key):
    try:
        return float(row[key])
    except (TypeError, ValueError, KeyError):
        return None


def summarize(rows, label):
    net = [r for r in (_f(x, "realized_pct") for x in rows) if r is not None]
    n = len(net)
    if n == 0:
        return {"cohort": label, "n": 0}
    wins = sum(1 for v in net if v > 0)
    w_p, w_lo, w_hi = wilson(wins, n)
    gp = sum(v for v in net if v > 0)
    gl = -sum(v for v in net if v < 0)
    avg_w = (gp / wins) if wins else 0.0
    avg_l = (gl / (n - wins)) if n - wins else 0.0

    # Exit asymmetry. capture is only meaningful where a favourable move
    # existed at all, so trades with MFE <= 0 are excluded rather than
    # counted as 0% capture - there was nothing to capture.
    caps, drags = [], []
    for x in rows:
        rp, mfe, mae = (_f(x, "realized_pct"), _f(x, "mfe_pct"),
                        _f(x, "mae_pct"))
        if rp is None:
            continue
        if mfe is not None and mfe > 0.01:
            caps.append(rp / mfe)
        if mae is not None:
            drags.append(mae - rp)      # >0 means worse than price alone
    return {
        "cohort": label, "n": n,
        "win_rate": w_p, "win_lo": w_lo, "win_hi": w_hi,
        "mean_net_pct": sum(net) / n,
        "median_net_pct": sorted(net)[n // 2],
        "payoff": (avg_w / avg_l) if avg_l else float("inf"),
        "profit_factor": (gp / gl) if gl else float("inf"),
        "capture_n": len(caps),
        "capture_median": sorted(caps)[len(caps) // 2] if caps else None,
        "cost_drag_median": (sorted(drags)[len(drags) // 2]
                             if drags else None),
        "mfe_positive_share": (len([1 for x in rows
                                    if (_f(x, "mfe_pct") or 0) > 0.01]) / n),
    }


def _summ(trips: list) -> dict:
    n = len(trips)
    if not n:
        return {"available": False, "n": 0}
    g = sorted(t["gross_pct"] for t in trips)
    nt = sorted(t["net_pct"] for t in trips)
    return {"available": True, "n": n,
            "gross_mean_pct": sum(g) / n, "gross_median_pct": g[n // 2],
            "net_mean_pct": sum(nt) / n, "net_median_pct": nt[n // 2],
            "gross_win_rate": sum(1 for v in g if v > 0) / n}


def lifetime_gross(fills_path) -> dict:
    """Fee-free gross over the WHOLE closed-trip history, on BOTH populations.

    WHY BOTH, and why this section does not assert a verdict. COST_BOUND says
    "a gross edge exists and fees eat it", and whether the wider history agrees
    depends entirely on ONE population choice that is easy to make silently:

      entry-opened only  — what the era-4 cohort measures (`opened_by` must be
                           "entry"; a hedge is insurance, not the thesis)
      + hedge-opened     — the whole book as actually traded

    Measured 2026-08-15: entry-only gross mean **+0.0173%** / median
    **+0.0533%** over 256 trips; hedge-inclusive is NEGATIVE, and the corpus
    already records the flip (discarding 159 hedge round trips moves median
    gross -0.0303% -> +0.0505%, `synthesis/the-money-path-thesis`). A session
    that quotes one of these as "the" fee-free number can refute or confirm
    COST_BOUND at will, which is exactly how the shipped breakeven tool once
    printed the opposite of its own method's answer.

    So this prints both, labelled, and draws no conclusion. The readout rule is
    untouched; the registration is the law. What is added is the fact that the
    verdict's SIGN is population-sensitive — the operator should see that before
    acting on any branch, not after. Report-only.
    """
    return {"entry_only": _summ(era4_trips(fills_path, since=0.0)),
            "with_hedges": _summ(era4_trips(fills_path, since=0.0,
                                            include_hedges=True))}


def era4_trips(fills_path, since: float | None = None,
               include_hedges: bool = False):
    """Entry-opened closed round trips from fills.csv closing at/after B4_TS.

    Returns a list of {"t", "gross_pct", "net_pct"} - the complete era-4
    strategy population. Same reconstruction discipline as breakeven_test:
    signed cash flow is gross, fees subtracted separately, fully-closed only
    (2% size tolerance), duplicate fill patterns dropped.
    """
    try:
        rows = list(csv.DictReader(open(fills_path, newline="",
                                        encoding="utf-8")))
    except OSError:
        return []
    by_pid = collections.defaultdict(list)
    for r in rows:
        if r.get("position_id"):
            by_pid[r["position_id"]].append(r)
    out, seen = [], set()
    for legs in by_pid.values():
        legs.sort(key=lambda r: _f(r, "ts") or 0.0)
        cash = fees = esz = xsz = enot = 0.0
        tclose = None
        topen = None
        opened_by = None
        # ERA PROVENANCE (report-only, added 2026-08-14). THREE-way, because
        # the ledger's own rule ("blank exec_era = pre-stamp, decide by ts")
        # returns the WRONG answer for rows a STALE BINARY wrote: their ts
        # says era-7 while their fill physics is era-2. csv.DictReader fills a
        # MISSING trailing field with None, and exec_era is the LAST column
        # (core/fill_ledger.COLS, index 16 of 17), so "absent" and "blank" are
        # distinguishable exactly where the distinction matters:
        #   None -> the writer's COLS predates the stamp  -> STALE BINARY
        #   ""   -> stamp-aware writer, pre-stamp row     -> decide by ts
        #   else -> stamped
        # This CLASSIFIES ONLY. The pre-registered selection below is
        # untouched: changing which trips count after the cohort accrues is
        # the exact thing pre-registration exists to prevent.
        eras, stale_legs, prestamp_legs = set(), 0, 0
        sig, ok = [], True
        for r in legs:
            sz, px = _f(r, "fill_size"), _f(r, "fill_price")
            fee = _f(r, "fees_delta_usd")
            if sz is None or px is None or fee is None or sz <= 0 or px <= 0:
                ok = False
                break
            _era = r.get("exec_era")
            if _era is None:
                stale_legs += 1
            elif not str(_era).strip():
                prestamp_legs += 1
            else:
                eras.add(str(_era).strip())
            cash += (sz * px) if r.get("side") == "sell" else -(sz * px)
            fees += fee
            if r.get("purpose") in _OPEN_PURPOSES:
                esz += sz
                enot += sz * px
                if opened_by is None:
                    opened_by = r.get("purpose")
                    topen = _f(r, "ts")
            elif r.get("purpose") == "exit":
                xsz += sz
                tclose = _f(r, "ts")
            sig.append((r.get("purpose"), r.get("side"),
                        round(sz, 6), round(px, 4)))
        if not ok or esz <= 0 or xsz <= 0 or enot <= 0 or tclose is None:
            continue
        if abs(xsz - esz) / esz > 0.02:
            continue
        key = tuple(sig)
        if key in seen:
            continue
        seen.add(key)
        # hedges are insurance, not the thesis — the pre-registered population
        # is entry-opened ONLY. include_hedges=True is used solely by
        # lifetime_gross() to show how much the fee-free sign depends on this
        # one choice; it never touches the verdict population (default False).
        if opened_by != "entry" and not include_hedges:
            continue
        # the verdict population: honest fills (post-#4) AND one capital
        # regime (post-reset) - the epoch cut is the later of the two.
        # `since` defaults to EXACTLY that cut, so the pre-registered
        # population is byte-identical; only lifetime_gross() passes 0.0, to
        # reconstruct the same trips WITHOUT the cut as a falsifier population.
        _cut = max(B4_TS, CAPITAL_EPOCH_TS) if since is None else since
        if tclose < _cut:
            continue
        out.append({"t": tclose, "t_open": topen, "pid": legs[0].get(
                        "position_id", ""),
                    "gross_pct": 100.0 * cash / enot,
                    "net_pct": 100.0 * (cash - fees) / enot,
                    "eras": sorted(eras), "stale_legs": stale_legs,
                    "prestamp_legs": prestamp_legs})
    return out


def era4_section(trips):
    """The pre-registered era-4 readout. Never decides; names what became
    decidable."""
    n = len(trips)
    res = {"pre_registered": _PREREG_ERA4, "b4_ts": B4_TS,
           "min_n": ERA4_MIN_N, "n": n,
           "progress": f"{n}/{ERA4_MIN_N}",
           "verdict_available": n >= ERA4_MIN_N}
    if n:
        g = sorted(t["gross_pct"] for t in trips)
        nt = sorted(t["net_pct"] for t in trips)
        mean_g = sum(g) / n
        # SE of the mean, printed WITH the mean (challenge hardening #2,
        # added at n=2, pre-data). At n=50 with per-trade sd ~0.5% the SE is
        # ~0.07%, so only |edges| beyond ~0.14% are resolvable - an order of
        # magnitude above every gross edge this strategy has exhibited. The
        # readout rule is unchanged: it is a pre-committed decision TRIGGER,
        # not a significance claim, and the interval exists so nobody reads
        # a triggered readout as a measured effect size.
        var_g = sum((v - mean_g) ** 2 for v in g) / n
        se_g = math.sqrt(var_g / n) if n > 1 else float("nan")
        res.update({
            "gross_mean_pct": mean_g, "gross_median_pct": g[n // 2],
            "gross_se_pct": se_g,
            "net_mean_pct": sum(nt) / n, "net_median_pct": nt[n // 2],
            "gross_win_rate": sum(1 for v in g if v > 0) / n,
            "net_win_rate": sum(1 for v in nt if v > 0) / n,
        })
    if not res["verdict_available"]:
        res["readout"] = "ACCRUING"
    elif res["gross_mean_pct"] <= 0 and res["gross_median_pct"] <= 0:
        res["readout"] = "NO_GROSS_EDGE"
    elif res["net_mean_pct"] <= 0:
        res["readout"] = "COST_BOUND"
    else:
        res["readout"] = "CONTINUE"
    return res


# --- CONTAMINATION / HOMOGENEITY (report-only, added 2026-08-14) ----------
# WHY: the registration says the accruing cohort is "uniformly post-geometry
# by construction". There are two ways that can silently stop being true, and
# before this section no tool could see either.
#   FILL-ERA  — fills.csv carries rows written by a binary whose COLS predate
#               exec_era (the live tree sat at 21769fb8, 2026-08-07, until the
#               08-12 fast-forward; boundaries #3/#4 and cut #7 are all NON-
#               ancestors of it). Those fills were granted by a simulator with
#               both the TTL-hazard bug and the ~1.88x near-touch double-count
#               live — inside the accruing verdict window.
#   MODEL-ERA — the champion can swap mid-cohort (it did: 2026-08-14T15:14:13Z,
#               a 10,217-row adaptive_gbt replaced by a 211-row logistic via
#               the ML-083 era-orphan unlock). fills.csv has NO model_id column
#               and adding one would be a fill-path change the moratorium
#               forbids, so a timestamp join against the retrain ledger is the
#               only honest route.
# Both are REPORTED and nothing else. Whether a mixed cohort resets accrual is
# an operator adjudication; this exists so the question cannot go unnoticed.
RETRAIN_HISTORY = "outputs/retrain_history.jsonl"
SIGNAL_HISTORY = "outputs/signal_history.csv"
CURRENT_LABEL_ERA = "triple_barrier_h432"


def deploy_epochs(path) -> list:
    """(ts, family, rows, oof_brier) per DEPLOYED retrain, ascending.

    A missing or unreadable ledger returns [] and the model-era section
    degrades to UNKNOWN rather than raising: a report tool must never become
    the reason the verdict gate cannot be read at all."""
    out = []
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue
                if not rec.get("deployed"):
                    continue
                try:
                    ts = float(rec.get("ts"))
                except (TypeError, ValueError):
                    continue
                out.append((ts, str(rec.get("selected") or "?"),
                            rec.get("rows"), rec.get("oof_brier")))
    except OSError:
        return []
    out.sort(key=lambda x: x[0])
    return out


def _champion_at(epochs: list, t):
    """Family in force at instant t; None before the first recorded deploy."""
    if t is None:
        return None
    fam = None
    for ts, family, _rows, _brier in epochs:
        if ts <= t:
            fam = family
        else:
            break
    return fam


def homogeneity(trips: list, epochs: list, cohort_start: float = 0.0) -> dict:
    """Classify the accruing cohort. Report-only; selects nothing.

    `cohort_start` trims the REPORTED deploy list to the accrual window. The
    full epoch history is still consulted to resolve which champion was in
    force when a trip opened — that champion may have deployed long before
    the window began, so filtering the input would misattribute it."""
    stale = [t for t in trips if t.get("stale_legs")]
    prestamp = [t for t in trips if t.get("prestamp_legs")]
    eras = sorted({e for t in trips for e in (t.get("eras") or [])})
    fill_mixed = bool(stale) or len(eras) > 1

    champs, straddle = set(), 0
    for t in trips:
        fam = _champion_at(epochs, t.get("t_open"))
        if fam:
            champs.add(fam)
        # a deploy landing strictly INSIDE a trip means the model that opened
        # it is not the model that was live when it closed
        topen, tclose = t.get("t_open"), t.get("t")
        # NB: never bind `_f` here — it is the module-level float parser
        if topen is not None and tclose is not None and any(
                topen < ts < tclose for ts, _fam, _r, _b in epochs):
            straddle += 1
    model_known = bool(epochs)
    model_mixed = model_known and (len(champs) > 1 or straddle > 0)

    if not model_known:
        verdict = "MIXED(fill)" if fill_mixed else "UNKNOWN(no model ledger)"
    elif fill_mixed and model_mixed:
        verdict = "MIXED(both)"
    elif fill_mixed:
        verdict = "MIXED(fill)"
    elif model_mixed:
        verdict = "MIXED(model)"
    else:
        verdict = "CLEAN"
    return {"verdict": verdict, "n": len(trips),
            "stale_trips": len(stale), "prestamp_trips": len(prestamp),
            "fill_eras": eras, "fill_mixed": fill_mixed,
            "model_known": model_known, "champions": sorted(champs),
            "straddling_trips": straddle, "model_mixed": model_mixed,
            "deploys": [(ts, fam) for ts, fam, _r, _b in epochs
                        if ts >= cohort_start]}


def cohort_effective_n(trips: list) -> dict:
    """Average-uniqueness effective sample size on the cohort's OWN trips.

    WHY THE GATE NEEDS THIS. The era-4 readout prints a resolution note built
    on the SE of the mean: "at n=50 with per-trade sd ~0.5% the SE is ~0.07%,
    so only |edges| beyond ~0.14% are resolvable". That arithmetic assumes 50
    INDEPENDENT observations. Trips held concurrently are not independent —
    they share the same market path over their overlap, which is de Prado's
    concurrency problem (AFML ch.4). The corpus already applies uniqueness
    weighting to TRAINING (`ml/history.py` uniqueness_enabled,
    `ml/event_sampler.py`) and the operator dashboard already plots label
    uniqueness at ~15.3%. The VERDICT GATE has never had it, so its stated
    resolution floor is optimistic by exactly the factor computed here.

    Method, on trip spans [t_open, t_close], no library needed: a trip's
    average uniqueness is the time-weighted mean of 1/c(t) over its own span,
    where c(t) is how many trips are open at t. effective_n is their sum, and
    SE scales as 1/sqrt(effective_n) rather than 1/sqrt(n) — so the resolvable
    edge inflates by sqrt(n / effective_n).

    Report-only. Changes no threshold and no selection; it says how much the
    cohort KNOWS, not which trips are in it."""
    spans = [(t["t_open"], t["t"]) for t in trips
             if t.get("t_open") is not None and t.get("t") is not None
             and t["t"] > t["t_open"]]
    n = len(spans)
    if not n:
        return {"available": False, "n": 0}
    # event-driven: concurrency only changes at a span endpoint, so the
    # segments between sorted endpoints have constant c(t)
    pts = sorted({p for s in spans for p in s})
    uniq = []
    for a, b in spans:
        acc, span = 0.0, b - a
        # strict=False is REQUIRED here, not stylistic. pts[1:] is one shorter
        # than pts by construction, so strict=True would raise ValueError on
        # EVERY call - and this is the uniqueness/effective-n path, so the
        # crash would land in the era-4 gate rather than in a report margin.
        # The short-tail truncation IS the adjacent-pair semantics wanted.
        for lo, hi in zip(pts, pts[1:], strict=False):
            seg = min(hi, b) - max(lo, a)
            if seg <= 0:
                continue
            c = sum(1 for x, y in spans if x < hi and y > lo)
            acc += seg / max(1, c)
        uniq.append(acc / span if span > 0 else 1.0)
    eff = sum(uniq)
    return {"available": True, "n": n, "effective_n": eff,
            "mean_uniqueness": eff / n,
            "se_inflation": (n / eff) ** 0.5 if eff > 0 else float("inf")}


def cohort_composition(trips: list, signal_history_path) -> dict:
    """WHAT the accruing cohort is made of, joined by position_id.

    A THIRD homogeneity axis, and measured 2026-08-15 the most damaging of the
    three. The fill-era and model-era sections above ask whether the trips were
    executed comparably. This asks whether they were SELECTED comparably — and
    they were not: 12 of 13 are `probe` admissions.

    Why that breaks the reading rather than merely biasing it: a probe sets
    `p_win = max(p_win, explore_p_win)` (main.py, exploration path) with
    `ml.exploration.p_win` = 0.7 against a derived entry bar near 0.567, so 0.7
    clears the bar BY CONSTRUCTION and the model's own probability is never the
    admitting quantity. A cohort of probes measures the exploration constant,
    not the selector the verdict is about.

    Report-only. Joins, counts, and prints; it selects nothing and the
    pre-registered population is untouched."""
    res = {"n": len(trips), "joined": 0, "available": False,
           "probe": {}, "label_era": {}, "source": {}}
    if not trips:
        return res
    want = {str(t.get("pid") or "") for t in trips} - {""}
    if not want:
        return res
    try:
        with open(signal_history_path, newline="", encoding="utf-8") as fh:
            rows = [r for r in csv.DictReader(fh)
                    if str(r.get("position_id", "")) in want]
    except OSError:
        return res
    if not rows:
        return res
    res["available"] = True
    res["joined"] = len({str(r.get("position_id")) for r in rows})
    for key in ("probe", "label_era", "source"):
        res[key] = dict(collections.Counter(
            str(r.get(key, "")).strip() or "<blank>" for r in rows
        ).most_common())
    n_probe = sum(v for k, v in res["probe"].items() if k == "1")
    res["probe_share"] = n_probe / max(1, sum(res["probe"].values()))
    res["label_eras_present"] = len([k for k in res["label_era"]
                                     if k and k != "<blank>"])
    return res


def geometry_breakeven(path, era: str = CURRENT_LABEL_ERA) -> dict:
    """Can the CURRENT label geometry pay at its own realized hit rate?

    A triple barrier with take-profit pt and stop sl breaks even GROSS (before
    any cost) only when the target is hit at least sl/(pt+sl) of the time.
    That threshold is arithmetic, not a fit, and it is the cheapest possible
    check on whether an exit geometry can pay AT ALL — model-independent. It
    is reported, never enforced: pt/sl are frozen under the moratorium and
    changing them is the pre-named ALGO-5 adjudication.

    Time-stopped paths resolve at NEITHER barrier and are excluded from the
    ratio; their count is always printed so the exclusion is never silent."""
    try:
        with open(path, newline="", encoding="utf-8") as fh:
            rows = [r for r in csv.DictReader(fh)
                    if str(r.get("label_era", "")).strip() == era]
    except OSError:
        return {"era": era, "n": 0, "available": False}
    bars = collections.Counter(str(r.get("barrier", "")) for r in rows)
    n_pt, n_sl = bars.get("tb_pt", 0), bars.get("tb_sl", 0)
    res = {"era": era, "n": len(rows), "available": False,
           "n_pt": n_pt, "n_sl": n_sl, "n_time": bars.get("tb_time", 0)}
    pts = sorted(v for v in (_f(r, "pt_frac") for r in rows) if v)
    sls = sorted(v for v in (_f(r, "sl_frac") for r in rows) if v)
    if not (pts and sls and (n_pt + n_sl)):
        return res
    mpt, msl = pts[len(pts) // 2], sls[len(sls) // 2]
    actual = n_pt / (n_pt + n_sl)
    need = msl / (mpt + msl)
    res.update({"available": True, "median_pt": mpt, "median_sl": msl,
                "payoff": (mpt / msl) if msl else float("inf"),
                "actual_hit": actual, "breakeven_hit": need,
                "margin": actual - need,
                "expectancy_pct": 100.0 * (n_pt * mpt - n_sl * msl)
                / (n_pt + n_sl)})
    return res


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default=str(ROOT / "outputs" /
                                         "postmortem_summary.csv"))
    ap.add_argument("--fills", default=str(ROOT / "outputs" / "fills.csv"))
    ap.add_argument("--retrain-history", default=str(ROOT / RETRAIN_HISTORY),
                    help="retrain ledger for the model-era join (report-only)")
    ap.add_argument("--signal-history", default=str(ROOT / SIGNAL_HISTORY),
                    help="label corpus for the geometry breakeven check")
    ap.add_argument("--json", action="store_true")
    ns = ap.parse_args()

    p = Path(ns.csv)
    if not p.exists():
        print(f"no postmortem data at {p}")
        return 1
    rows = list(csv.DictReader(open(p, newline="", encoding="utf-8")))
    old = [r for r in rows if (_f(r, "ts") or 0) < MIGRATION_TS]
    new = [r for r in rows if (_f(r, "ts") or 0) >= MIGRATION_TS]

    _trips = era4_trips(ns.fills)
    _epochs = deploy_epochs(ns.retrain_history)
    res = {"pre_registered": _PREREG, "min_cohort_n": MIN_COHORT_N,
           "migration_ts": MIGRATION_TS,
           "cohorts": [summarize(old, "pre-432 (old geometry)"),
                       summarize(new, "post-432 (36h horizon)")],
           "era4": era4_section(_trips),
           "homogeneity": homogeneity(_trips, _epochs,
                                      max(B4_TS, CAPITAL_EPOCH_TS)),
           "geometry": geometry_breakeven(ns.signal_history),
           "composition": cohort_composition(_trips, ns.signal_history),
           "lifetime": lifetime_gross(ns.fills),
           "effective_n": cohort_effective_n(_trips)}
    nn = res["cohorts"][1]["n"]
    res["verdict_available"] = nn >= MIN_COHORT_N
    res["progress"] = f"{nn}/{MIN_COHORT_N}"

    if ns.json:
        print(json.dumps(res, indent=1, default=str))
        return 0

    print("COHORT EVALUATION — pre-registered %s" % _PREREG)
    print("=" * 68)
    for c in res["cohorts"]:
        if not c["n"]:
            print("\n%s: no closed trades" % c["cohort"])
            continue
        print("\n%s  (n=%d)" % (c["cohort"], c["n"]))
        print("  win rate        %.1f%%   Wilson 95%% [%.1f%%, %.1f%%]"
              % (c["win_rate"] * 100, c["win_lo"] * 100, c["win_hi"] * 100))
        print("  mean net/trade  %+.3f%%   median %+.3f%%"
              % (c["mean_net_pct"], c["median_net_pct"]))
        print("  payoff ratio    %.3f    profit factor %.3f"
              % (c["payoff"], c["profit_factor"]))
        if c["capture_median"] is not None:
            print("  MFE capture     %.3f  (median realized/MFE over %d "
                  "trades that HAD a favourable move)"
                  % (c["capture_median"], c["capture_n"]))
        if c["cost_drag_median"] is not None:
            print("  cost drag       %+.3f%%  (median MAE-realized; >0 means "
                  "the loss exceeds the worst the price ever went)"
                  % c["cost_drag_median"])
        print("  had upside      %.0f%% of trades reached MFE > 0.01%%"
              % (c["mfe_positive_share"] * 100))

    print("\n  CAVEAT (measured 2026-08-10): these cohorts read the")
    print("  postmortem ledger, which records only trades that")
    print("  underperformed entry-time EV - coverage 85.1%/93.1% of")
    print("  entry-opened closes, biasing win rates LOW by -1.5pp/-5.4pp.")
    print("  Same direction both cohorts: the comparison stands, the")
    print("  absolute win rates read a few points worse than truth.")

    print("\n" + "=" * 68)
    print("VERDICT GATE: %s toward the pre-registered %d closed trades"
          % (res["progress"], MIN_COHORT_N))
    if not res["verdict_available"]:
        print("\nNo verdict. The post-migration cohort is too small, and a")
        print("win rate at this n has a Wilson interval consistent with both")
        print("ruin and riches — reading it is worse than not looking.")
        print("Keep accruing. Do not retune on this number.")
    else:
        m = res["cohorts"][1]["mean_net_pct"]
        if m < STOP_IF_NET_PCT_BELOW:
            print("\nSTAND DOWN: cohort mean %+.3f%% is below the "
                  "pre-registered %.1f%%." % (m, STOP_IF_NET_PCT_BELOW))
        elif m > CONTINUE_IF_NET_PCT_ABOVE:
            print("\nCONTINUE: cohort mean %+.3f%% clears the bar." % m)
        else:
            print("\nINCONCLUSIVE: cohort mean %+.3f%% sits between the "
                  "pre-registered thresholds. Keep accruing." % m)

    e4 = res["era4"]
    print("\n" + "=" * 68)
    print("ERA-4 GATE - pre-registered %s at n=1, the honest-fill cohort"
          % _PREREG_ERA4)
    print("(execution-era boundary #4, aeeaae36: first fills granted at the")
    print(" rate the recorded market actually crossed - all earlier eras")
    print(" carried a ~1.88x near-touch inflation. Complete population from")
    print(" fills.csv, entry-opened only; no postmortem censoring.)")
    print("\n  accrual: %s entry-opened closes toward the verdict gate"
          % e4["progress"])
    print("  COHORT HOMOGENEITY: %s" % res["homogeneity"]["verdict"])
    if e4["n"]:
        print("  gross  mean %+.4f%%  (SE %.4f%%)  median %+.4f%%  win %.1f%%"
              % (e4["gross_mean_pct"], e4.get("gross_se_pct", float("nan")),
                 e4["gross_median_pct"], e4["gross_win_rate"] * 100))
        print("  resolution note: the gate is a pre-committed TRIGGER, not a")
        print("  measurement - a readout does not claim the effect size is")
        print("  resolved beyond ~2x the SE above.")
        _en = res.get("effective_n") or {}
        if _en.get("available"):
            print("  EFFECTIVE n: %.1f of %d nominal (mean uniqueness %.3f)."
                  % (_en["effective_n"], _en["n"], _en["mean_uniqueness"]))
            print("  Trips held CONCURRENTLY share the same market path over")
            print("  their overlap, so the SE above - which assumes n")
            print("  independent observations - is optimistic by x%.2f."
                  % _en["se_inflation"])
            print("  Read the resolvable-edge floor as ~%.4f%%, not the"
                  % (2 * e4.get("gross_se_pct", float("nan"))
                     * _en["se_inflation"]))
            print("  nominal figure. (de Prado concurrency; the corpus already")
            print("  weights TRAINING this way - the gate never did.)")
        print("  net    mean %+.4f%%  median %+.4f%%  win %.1f%%"
              % (e4["net_mean_pct"], e4["net_median_pct"],
                 e4["net_win_rate"] * 100))
    if e4["readout"] == "ACCRUING":
        print("\n  No verdict below n=%d. Do not read these numbers as a"
              % ERA4_MIN_N)
        print("  trend; do not retune on them.")
    elif e4["readout"] == "NO_GROSS_EDGE":
        print("\n  NO GROSS EDGE at n>=%d on honest fills: the stop-strategy"
              % ERA4_MIN_N)
        print("  question goes to the operator. No execution, cost or model")
        print("  change is on the table - none of them create expectancy.")
    elif e4["readout"] == "COST_BOUND":
        print("\n  COST-BOUND: a gross edge exists on honest fills and fees")
        print("  eat it. The fee levers held behind h432 become the live")
        print("  discussion.")
        print("\n  BEFORE ACTING ON THAT LINE: the sign is POPULATION-SENSITIVE")
        print("  (see the FEE-FREE GROSS section below). COST_BOUND asserts a")
        print("  gross edge EXISTS; whether the wider history agrees flips with")
        print("  one choice - whether hedge-opened round trips are counted.")
        print("  Read both rows there before touching a fee lever.")
    else:
        print("\n  CONTINUE: net-positive on honest fills at n>=%d."
              % ERA4_MIN_N)

    hg = res["homogeneity"]
    print("\n" + "=" * 68)
    print("COHORT HOMOGENEITY - %s" % hg["verdict"])
    print("(Report-only. The pre-registered selection rule is UNCHANGED: this")
    print(" section classifies what accrued, it never filters it. Whether a")
    print(" mixed cohort resets accrual is an OPERATOR adjudication.)")
    print("\n  FILL-ERA")
    print("    trips with a STALE-BINARY leg (exec_era field ABSENT): %d/%d"
          % (hg["stale_trips"], hg["n"]))
    print("    trips with a pre-stamp blank leg:                      %d/%d"
          % (hg["prestamp_trips"], hg["n"]))
    print("    distinct stamped eras present: %s"
          % (", ".join(hg["fill_eras"]) or "none"))
    if hg["stale_trips"]:
        print("    -> a leg was written by a binary whose COLS predate the")
        print("       exec_era stamp: its ts reads era-7 while its fill")
        print("       physics is pre-boundary-#4 (TTL hazard + ~1.88x")
        print("       near-touch). The ledger's blank-means-decide-by-ts rule")
        print("       returns the WRONG era for exactly these rows.")
    print("\n  MODEL-ERA")
    if not hg["model_known"]:
        print("    UNKNOWN - no retrain ledger readable at the given path.")
    else:
        print("    champions that opened trips in this cohort: %s"
              % (", ".join(hg["champions"]) or "none resolved"))
        print("    trips straddling a mid-flight deploy:       %d"
              % hg["straddling_trips"])
        for _ts, _fam in hg["deploys"]:
            print("      deploy %s  ->  %s"
                  % (datetime.fromtimestamp(_ts, timezone.utc)
                     .strftime("%Y-%m-%dT%H:%M:%SZ"), _fam))

    cp = res["composition"]
    print("\n  SELECTION-ERA (what the cohort is MADE OF)")
    if not cp.get("available"):
        print("    UNAVAILABLE - no signal_history join at the given path.")
    else:
        print("    joined %d/%d trips by position_id" % (cp["joined"], cp["n"]))
        print("    probe:     %s" % cp["probe"])
        print("    label_era: %s" % cp["label_era"])
        print("    source:    %s" % cp["source"])
        if cp.get("probe_share", 0) > 0.5:
            print("    -> %.0f%% of this cohort are PROBE admissions. A probe sets"
                  % (100 * cp["probe_share"]))
            print("       p_win = max(p_win, ml.exploration.p_win = 0.7) against a")
            print("       derived bar near 0.567, so it clears BY CONSTRUCTION and")
            print("       the model's own p is never the admitting quantity. This")
            print("       cohort measures the EXPLORATION CONSTANT, not the selector")
            print("       the verdict is about.")
        if cp.get("label_eras_present", 0) > 1:
            print("    -> %d distinct label eras in one cohort - the label axis is"
                  % cp["label_eras_present"])
            print("       mixed as well as the fill and model axes.")

    lt = res.get("lifetime") or {}
    print("\n" + "=" * 68)
    print("FEE-FREE GROSS over the whole closed-trip history - BOTH populations")
    print("(the verdict's sign depends on this choice; neither row is 'the'")
    print(" number, and quoting one alone can confirm or refute COST_BOUND at")
    print(" will - which is how the shipped breakeven tool once printed the")
    print(" opposite of its own method's answer)")
    for _key, _lbl in (("entry_only", "entry-opened ONLY (what the cohort "
                                      "measures)"),
                       ("with_hedges", "+ hedge-opened (the whole book as "
                                       "traded)")):
        _s = lt.get(_key) or {}
        if not _s.get("available"):
            print("  %-46s unavailable" % _lbl)
            continue
        print("  %s" % _lbl)
        print("    n=%-5d gross mean %+.4f%%  median %+.4f%%  win %.1f%%"
              % (_s["n"], _s["gross_mean_pct"], _s["gross_median_pct"],
                 100 * _s["gross_win_rate"]))
    _e, _h = lt.get("entry_only") or {}, lt.get("with_hedges") or {}
    if _e.get("available") and _h.get("available") and \
            (_e["gross_median_pct"] > 0) != (_h["gross_median_pct"] > 0):
        print("  -> THE TWO ROWS DISAGREE IN SIGN. The fee-free question has no")
        print("     single answer on this book; it has one answer per")
        print("     population, and the cohort's own definition picks the")
        print("     entry-only row. Say which one you mean, every time.")

    g = res["geometry"]
    print("\n" + "=" * 68)
    print("LABEL-GEOMETRY BREAKEVEN - %s" % g["era"])
    if not g.get("available"):
        print("  unavailable (n=%d rows for this era; needs pt/sl plus at"
              % g.get("n", 0))
        print("  least one barrier-resolved path)")
    else:
        print("  n=%d rows   barriers: tb_pt=%d  tb_sl=%d  tb_time=%d"
              % (g["n"], g["n_pt"], g["n_sl"], g["n_time"]))
        print("  median pt %.4f%%   median sl %.4f%%   payoff %.3f"
              % (100 * g["median_pt"], 100 * g["median_sl"], g["payoff"]))
        print("  target-hit rate  ACTUAL %.3f  BREAKEVEN %.3f  margin %+.3f"
              % (g["actual_hit"], g["breakeven_hit"], g["margin"]))
        print("  gross expectancy %+.4f%% per barrier-resolved path (pre-cost)"
              % g["expectancy_pct"])
        print("  NOTE: %d time-stopped paths resolve at NEITHER barrier and"
              % g["n_time"])
        print("  are excluded from the ratio above - never silently.")
        if g["margin"] < 0:
            print("\n  NO GROSS EDGE IN THE GEOMETRY ITSELF: the target must be")
            print("  hit %.1f%% of the time to break even before costs, and is"
                  % (100 * g["breakeven_hit"]))
            print("  hit %.1f%%. That is arithmetic, not a fit, and it is"
                  % (100 * g["actual_hit"]))
            print("  model-INDEPENDENT - no selector rescues a geometry that")
            print("  cannot pay. Changing pt/sl is the pre-named ALGO-5")
            print("  adjudication and is FROZEN: report, do not retune.")

    c = res["cohorts"][0]
    if c["n"] and c.get("cost_drag_median") is not None \
            and c["cost_drag_median"] > 0:
        print("\nEXIT ASYMMETRY READ (old cohort): median loss exceeds the")
        print("worst adverse excursion by %+.3f%%. The price never moved that"
              % c["cost_drag_median"])
        print("far against these trades — so this is COST, not a stop being")
        print("hit too tight and not winners being cut early. An exit-policy")
        print("change cannot fix it; only a horizon long enough to earn more")
        print("than the round trip costs can.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
