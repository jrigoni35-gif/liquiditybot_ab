"""Gate-truth report: grade the informed-flow gate's component evidence
against realized triple-barrier outcomes (gate-truth instrumentation,
spec docs/superpowers/specs/2026-07-28-gate-truth-instrumentation.md).

Report-only — reads outputs/signal_history.csv, mutates nothing.
Sample: rows whose label_era == the CONFIGURED triple-barrier era
(ml.label_max_bars via triple_barrier_era) AND any |sg_*| > 0
(instrumented). Direction alignment derived here: aligned_i = s_i × the
row's `direction` feature (±1) — rows store RAW signed scores.

SG_MIN_ROWS (=100): below this the verdict is XV-042 (thin) — the same
documented-floor approach as cost_truth_report's both-legs floor, never
a config knob (this is a measurement standard, not a tunable). The floor
is applied to EFFECTIVE n (uniqueness-weighted independent observations,
operator-approved 2026-07-29), not the raw row count: overlapping
same-asset label windows share one return path (de Prado average
uniqueness, AFML ch.4 — the loader's exact algorithm computed within
this report's sample), so 100 fully-concurrent rows are ~one
independent fact and prove nothing. At the 2026-07-29 corpus's mean
uniqueness (~0.16), 100 raw rows ≈ 16 independent observations — the
detectable per-component effect at that size (~0.17 AUC) exceeds every
deviation the weights could plausibly carry, which is exactly why the
honest unit matters.

Weight source: config `informed_flow.weights` — NOT `strategies.weights`
(main.py:544 constructs InformedFlowEngine(config.get("informed_flow",
{})), and core/config_guard.py validates every informed_flow.* knob
under that same prefix; `strategies` only carries `engine`/`_rollback`).
"""
import csv
import itertools
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.codes import Code                                # noqa: E402
from ml.history import (SG_COMPONENT_KEYS,                 # noqa: E402
                        triple_barrier_era)
# effective_n RELOCATED to ml.corpus (2026-08-29), the stdlib-legal
# canonical home; re-exported here (module attribute) so existing callers
# and tests that `from scripts.gate_truth_report import effective_n`
# keep working, and there is now exactly ONE copy of the algorithm.
from ml.corpus import effective_n                          # noqa: E402,F401

SG_MIN_ROWS = 100
_WEIGHT_KEYS = ("flow", "delta", "accum", "burst", "trend")
_DEFAULT_W = {"flow": 1.0, "delta": 0.6, "accum": 0.9, "burst": 0.8,
              "trend": 0.7}
# gate_confidence calibration buckets (spec D5, section [4]). Report
# constant, not a config knob (T7 precedent, D7 non-goals). Half-open
# [lo, hi) except the top bucket, which is widened to 1.01 to include an
# exact confidence of 1.0 despite float noise in the persisted %.6f value.
_CONF_BUCKETS = ((0.0, 0.5), (0.5, 0.8), (0.8, 0.999), (0.999, 1.01))


def _f(v, d=0.0):
    try:
        x = float(v)
        return x if x == x and abs(x) != float("inf") else d
    except (TypeError, ValueError):
        return d


def _rank_auc(x, y):
    """Mann-Whitney rank AUC of score x for binary y (ties: midrank)."""
    pairs = sorted(zip(x, y, strict=True), key=lambda t: t[0])
    ranks, i = {}, 0
    while i < len(pairs):
        j = i
        while j < len(pairs) and pairs[j][0] == pairs[i][0]:
            j += 1
        mid = (i + j + 1) / 2.0
        for k in range(i, j):
            ranks[k] = mid
        i = j
    n1 = sum(1 for _, yy in pairs if yy)
    n0 = len(pairs) - n1
    if not n1 or not n0:
        return float("nan")
    rsum = sum(ranks[k] for k, (_, yy) in enumerate(pairs) if yy)
    return (rsum - n1 * (n1 + 1) / 2.0) / (n1 * n0)


def _spearman(a, b):
    """Spearman rho of two equal-length lists. ranks() below assigns
    SEQUENTIAL ranks (1..n by sort position), not midranks — a tied input
    would rank sort-order-dependent rather than averaged. Fine for this
    call site: 5 distinct configured weights, essentially never tied."""
    def ranks(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v)
        for pos, i in enumerate(order):
            r[i] = pos + 1.0
        return r
    ra, rb = ranks(a), ranks(b)
    n = len(a)
    ma = sum(ra) / n
    mb = sum(rb) / n
    num = sum((x - ma) * (y - mb) for x, y in zip(ra, rb, strict=True))
    da = sum((x - ma) ** 2 for x in ra) ** 0.5
    db = sum((y - mb) ** 2 for y in rb) ** 0.5
    return num / (da * db) if da and db else 0.0


def auc_se_on_neff(n_eff, pos_rate):
    """H0 standard error of a rank AUC, evaluated on EFFECTIVE n.

    sqrt((n1 + n0 + 1) / (12 * n1 * n0)) — the Bamber/Hanley-McNeil
    null-hypothesis SE. Deliberately fed EFFECTIVE counts: overlapping
    label windows share one return path, so an SE computed on nominal n
    is optimistic by sqrt(n / n_eff) (the same deflation SG_MIN_ROWS has
    been judged against since 2026-07-29). Returns nan for a degenerate
    one-class split, which callers must treat as "no margin available",
    never as zero margin."""
    n1 = float(n_eff) * float(pos_rate)
    n0 = float(n_eff) - n1
    if not (n1 > 0.0 and n0 > 0.0):
        return float("nan")
    return math.sqrt((n1 + n0 + 1.0) / (12.0 * n1 * n0))


def rho_identified_set(weights, aucs, margin, keys):
    """IDENTIFIED SET of the XV-040 spearman rho (Manski partial
    identification), given each AUC is known only to +/- `margin`.

    rho depends on the AUCs ONLY through their RANK ORDER, so the set of
    rho values consistent with the data is finite and can be enumerated
    EXHAUSTIVELY rather than sampled: <= 5! = 120 orderings. An ascending
    ordering sigma is feasible iff every pair it commits to can actually
    be realized inside the boxes — auc_i - auc_j <= 2*margin whenever
    sigma places v_i <= v_j (pairwise is sufficient here: independent
    intervals admit a realizing assignment whenever every pair does).

    Returns (rho_lo, rho_hi, n_feasible). When the set straddles zero the
    ALIGNED-vs-MISALIGNED distinction is NOT IDENTIFIED: the point rho is
    a coin flip dressed as a verdict, and the caller must decline."""
    lo, hi, n_feas = 1.0, -1.0, 0
    wv = [weights[k] for k in keys]
    for sigma in itertools.permutations(range(len(keys))):
        feasible = True
        for a in range(len(sigma)):
            for b in range(a + 1, len(sigma)):
                i, j = sigma[a], sigma[b]           # commits v_i <= v_j
                if aucs[keys[i]] - aucs[keys[j]] > 2.0 * margin:
                    feasible = False
                    break
            if not feasible:
                break
        if not feasible:
            continue
        n_feas += 1
        # rank surrogate: any values in this order give the same rho
        surrogate = [0.0] * len(keys)
        for pos, i in enumerate(sigma):
            surrogate[i] = float(pos)
        r = _spearman(wv, surrogate)
        lo, hi = min(lo, r), max(hi, r)
    if n_feas == 0:                                  # unreachable in theory
        return float("nan"), float("nan"), 0
    return lo, hi, n_feas


def classify_alignment(weights, aucs, n, n_eff=None, auc_margin=None):
    """(code_value, human_line) for the weight-vs-data verdict.

    `n_eff` (uniqueness-weighted independent-observation count) is the
    number the SG_MIN_ROWS floor is judged against when provided — the
    unit the AUC statistics actually run on; None preserves the legacy
    raw-n gate byte-identically (existing callers/tests).

    `auc_margin` (half-width of each AUC's 95% interval on EFFECTIVE n)
    turns the verdict from a point into a partial-identification test:
    the rho is computed from five ESTIMATED AUCs, so when the identified
    set of rho straddles zero, ALIGNED and MISALIGNED are both consistent
    with the data and NEITHER may be asserted. Measured 2026-08-31 on the
    live corpus: n=10718 / n_eff=611.3, AUC spread 0.026 against a 95%
    margin of +/-0.046 — 120 of 120 orderings feasible, identified set
    [-1.000, +1.000]. XV-040 ALIGNED was being printed on a rho whose
    sign the evidence does not determine. None preserves the legacy
    point-verdict byte-identically."""
    gate_n = n if n_eff is None else n_eff
    if gate_n < SG_MIN_ROWS:
        unit = (f"only {n} instrumented era rows" if n_eff is None else
                f"only {n_eff:.1f} effective independent observations "
                f"(raw {n} rows deflated by label overlap)")
        return (Code.XV_GATE_TRUTH_THIN.value,
                f"{Code.XV_GATE_TRUTH_THIN.value}: {unit} "
                f"(< {SG_MIN_ROWS}) - no verdict yet, keep accruing")
    keys = [k for k in _WEIGHT_KEYS if k in weights and k in aucs]
    if any(math.isnan(aucs[k]) for k in keys):
        # Degenerate one-class sample (e.g. all winners/all losers) makes
        # _rank_auc return NaN for that component. Unguarded, NaN
        # propagates into the spearman rho and `rho >= 0.0` is False for
        # NaN in Python — silently falling through to a false XV-041
        # MISALIGNED. Catch it here instead: no verdict is possible yet.
        nan_keys = ", ".join(k for k in keys if math.isnan(aucs[k]))
        return (Code.XV_GATE_TRUTH_THIN.value,
                f"{Code.XV_GATE_TRUTH_THIN.value}: degenerate one-class "
                f"AUC (NaN) for component(s) [{nan_keys}] - no verdict "
                f"yet, keep accruing")
    rho = _spearman([weights[k] for k in keys], [aucs[k] for k in keys])
    counts = f"n={n}" if n_eff is None else f"n={n}, n_eff={n_eff:.0f}"
    # PARTIAL IDENTIFICATION: the five AUCs are estimates, and rho reads
    # only their rank order, so sampling error at effective n can reorder
    # them outright. If both signs of rho survive, decline the verdict —
    # XV-042 already carries "no verdict yet" for the other non-row-count
    # condition in this function (the degenerate-NaN branch above).
    if auc_margin is not None and auc_margin == auc_margin:
        r_lo, r_hi, n_feas = rho_identified_set(weights, aucs,
                                                float(auc_margin), keys)
        if r_lo == r_lo and r_lo < 0.0 <= r_hi:
            return (Code.XV_GATE_TRUTH_THIN.value,
                    f"{Code.XV_GATE_TRUTH_THIN.value}: weight-vs-AUC rank "
                    f"agreement NOT IDENTIFIED — point spearman {rho:+.2f}, "
                    f"but the identified set of rho is [{r_lo:+.2f}, "
                    f"{r_hi:+.2f}] ({n_feas}/120 orderings feasible at the "
                    f"+/-{auc_margin:.3f} AUC margin on effective n, "
                    f"{counts}) - ALIGNED and MISALIGNED are both "
                    f"consistent with this evidence, so neither is claimed")
    if rho >= 0.0:
        return (Code.XV_GATE_TRUTH_ALIGNED.value,
                f"{Code.XV_GATE_TRUTH_ALIGNED.value}: weight order "
                f"rank-agrees with realized AUCs (spearman {rho:+.2f}, "
                f"{counts})")
    return (Code.XV_GATE_TRUTH_MISALIGNED.value,
            f"{Code.XV_GATE_TRUTH_MISALIGNED.value}: weight order "
            f"CONTRADICTS realized discrimination (spearman {rho:+.2f}, "
            f"{counts}) - re-weight decision needs the full gate battery, "
            f"never a blind tune")


def build_report(history_path="outputs/signal_history.csv",
                 config_path="config.json"):
    try:
        cfg = json.load(open(config_path, encoding="utf-8"))
    except OSError:
        cfg = {}
    # informed_flow.weights, not strategies.weights (main.py:544, config_guard.py)
    wcfg = ((cfg.get("informed_flow") or {}).get("weights") or {})
    weights = {k: _f(wcfg.get(k, _DEFAULT_W[k]), _DEFAULT_W[k])
               for k in _WEIGHT_KEYS}

    rows = list(csv.DictReader(open(history_path, newline="",
                                    encoding="utf-8")))
    # LABEL ERA: derived from config, NEVER hardcoded. This line read
    # `== "triple_barrier"` - the RETIRED unqualified (96-bar) era -
    # while the deployed era is horizon-qualified. Measured 2026-08-15
    # with ml.label_max_bars=432: the literal selected 5,328 retired
    # rows (4,228 instrumented) and ZERO deployed rows, so every figure
    # below described a label geometry the bot had stopped using - and
    # said nothing about it, because the era was never printed. A
    # hardcoded era name is a silent time bomb at every horizon
    # migration; triple_barrier_era() is the one definition of "which
    # era is current", already used by ml/history.py's own loader.
    _max_bars = int((cfg.get("ml") or {}).get("label_max_bars", 96))
    _label_era = triple_barrier_era(_max_bars)
    era = [r for r in rows if (r.get("label_era") or "") == _label_era]
    inst = [r for r in era if any(abs(_f(r.get(f"sg_{k}"))) > 0.0
                                  for k in SG_COMPONENT_KEYS)]
    n_eff, mean_u = effective_n(inst)
    out = ["GATE TRUTH REPORT", "=" * 60,
           "[1] instrumentation coverage",
           # name the POPULATION on the report's own face: a reader who
           # cannot see which era was measured cannot tell a thin real
           # answer from a fat wrong one (the defect this line fixes).
           f"  label era: {_label_era}  "
           f"(ml.label_max_bars={_max_bars})",
           f"  corpus rows: {len(rows)}  era rows: {len(era)}  "
           f"instrumented era rows: {len(inst)}",
           f"  effective n (uniqueness-weighted): {n_eff:.1f}  "
           f"mean uniqueness: {mean_u:.3f}  "
           f"(independent observations - the unit the floor and every "
           f"AUC below actually run on)", ""]

    y = [1.0 if r.get("label") == "1" else 0.0 for r in inst]
    # AUC INTERVAL, on the SAME effective n the floor is judged against.
    # Section [1] has always printed n_eff and called it "the unit every
    # AUC below actually runs on" — until 2026-08-31 no AUC below carried
    # an interval, so a reader saw five points and read a RANKING that
    # the sampling error does not support.
    _win = (sum(y) / len(y)) if y else float("nan")
    _auc_se = auc_se_on_neff(n_eff, _win) if y else float("nan")
    _margin = 1.96 * _auc_se if _auc_se == _auc_se else float("nan")
    aucs = {}
    out.append("[2] per-component realized discrimination "
               "(aligned = s_i x direction)")
    if _margin == _margin:
        out.append(f"  AUC 95% margin +/-{_margin:.4f} on effective n="
                   f"{n_eff:.1f} (nominal n={len(inst)} would read "
                   f"+/-{1.96 * auc_se_on_neff(len(inst), _win):.4f} — "
                   f"optimistic by x{math.sqrt(len(inst) / n_eff):.2f})")
    for k in _WEIGHT_KEYS:
        a = [_f(r.get(f"sg_{k}")) * _f(r.get("direction"), 1.0)
             for r in inst]
        auc = _rank_auc(a, y) if inst else float("nan")
        aucs[k] = auc
        n_pos = sum(1 for v in a if v > 0)
        _ci = ""
        if _margin == _margin and auc == auc:
            _sig = "" if abs(auc - 0.5) > _margin else "  [spans 0.5]"
            _ci = f"  95% CI [{auc - _margin:.3f}, {auc + _margin:.3f}]{_sig}"
        out.append(f"  {k:6s} w={weights[k]:.2f}  AUC={auc:.3f}{_ci}  "
                   f"aligned_n={n_pos}/{len(a)}")
        # win-rate SPLIT: aligned (s_i x direction > 0) vs opposed (< 0).
        # Rows with s_i x direction == 0 count toward neither side.
        aligned_y = [yy for v, yy in zip(a, y, strict=True) if v > 0]
        opposed_y = [yy for v, yy in zip(a, y, strict=True) if v < 0]
        aligned_wr = (f"{sum(aligned_y) / len(aligned_y):.3f}"
                      if aligned_y else "-")
        opposed_wr = (f"{sum(opposed_y) / len(opposed_y):.3f}"
                      if opposed_y else "-")
        out.append(f"         win_rate aligned={aligned_wr} "
                   f"(n={len(aligned_y)})  opposed={opposed_wr} "
                   f"(n={len(opposed_y)})")
    out.append("")

    out.append("[3] evidence strength + concentration")
    for k in ("evidence", "conc"):
        a = [_f(r.get(f"sg_{k}")) for r in inst]
        # evidence is signed long/short: align it too; conc is unsigned
        if k == "evidence":
            a = [v * _f(r.get("direction"), 1.0)
                 for v, r in zip(a, inst, strict=True)]
        out.append(f"  {k:8s} AUC={_rank_auc(a, y) if inst else float('nan'):.3f}")
    out.append("")

    # [4] gate_confidence calibration buckets — the spec's motivating
    # measurement (docs/superpowers/specs/2026-07-28-gate-truth-
    # instrumentation.md, D5): the 2026-07-28 audit found win rate falling
    # as confidence rose (0.359 -> 0.321 -> 0.297, AUC 0.469) - the gate is
    # ANTI-calibrated. This section re-measures that over the SAME
    # instrumented-era sample the sections above use.
    out.append("[4] gate_confidence calibration")
    gc = [_f(r.get("gate_confidence")) for r in inst]
    for lo, hi in _CONF_BUCKETS:
        bucket_y = [yy for v, yy in zip(gc, y, strict=True) if lo <= v < hi]
        if not bucket_y:
            continue
        wr = sum(bucket_y) / len(bucket_y)
        out.append(f"  [{lo:.3f},{hi:.3f})  n={len(bucket_y)}  "
                   f"win_rate={wr:.3f}")
    conf_auc = _rank_auc(gc, y) if inst else float("nan")
    out.append(f"  gate_confidence AUC={conf_auc:.3f}  "
               f"(vs label; <0.5 = anti-calibrated)")
    out.append("")

    code, line = classify_alignment(weights, aucs, len(inst), n_eff=n_eff,
                                    auc_margin=_margin)
    out += ["[5] verdict", f"  {line}", ""]
    return "\n".join(out)


def main():
    print(build_report())
    return 0


if __name__ == "__main__":
    sys.exit(main())
