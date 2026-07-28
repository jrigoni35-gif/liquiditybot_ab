"""Gate-truth report: grade the informed-flow gate's component evidence
against realized triple-barrier outcomes (gate-truth instrumentation,
spec docs/superpowers/specs/2026-07-28-gate-truth-instrumentation.md).

Report-only — reads outputs/signal_history.csv, mutates nothing.
Sample: rows with label_era == "triple_barrier" AND any |sg_*| > 0
(instrumented). Direction alignment derived here: aligned_i = s_i × the
row's `direction` feature (±1) — rows store RAW signed scores.

SG_MIN_ROWS (=100): below this the verdict is XV-042 (thin) — the same
documented-floor approach as cost_truth_report's both-legs floor, never
a config knob (this is a measurement standard, not a tunable).

Weight source: config `informed_flow.weights` — NOT `strategies.weights`
(main.py:544 constructs InformedFlowEngine(config.get("informed_flow",
{})), and core/config_guard.py validates every informed_flow.* knob
under that same prefix; `strategies` only carries `engine`/`_rollback`).
"""
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.codes import Code                                # noqa: E402
from ml.history import SG_COMPONENT_KEYS                   # noqa: E402

SG_MIN_ROWS = 100
_WEIGHT_KEYS = ("flow", "delta", "accum", "burst", "trend")
_DEFAULT_W = {"flow": 1.0, "delta": 0.6, "accum": 0.9, "burst": 0.8,
              "trend": 0.7}


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
    """Spearman rho of two equal-length lists (ranks, no ties expected
    for 5 distinct weights; midrank if any)."""
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


def classify_alignment(weights, aucs, n):
    """(code_value, human_line) for the weight-vs-data verdict."""
    if n < SG_MIN_ROWS:
        return (Code.XV_GATE_TRUTH_THIN.value,
                f"{Code.XV_GATE_TRUTH_THIN.value}: only {n} instrumented "
                f"era rows (< {SG_MIN_ROWS}) - no verdict yet, keep "
                f"accruing")
    keys = [k for k in _WEIGHT_KEYS if k in weights and k in aucs]
    rho = _spearman([weights[k] for k in keys], [aucs[k] for k in keys])
    if rho >= 0.0:
        return (Code.XV_GATE_TRUTH_ALIGNED.value,
                f"{Code.XV_GATE_TRUTH_ALIGNED.value}: weight order "
                f"rank-agrees with realized AUCs (spearman {rho:+.2f}, "
                f"n={n})")
    return (Code.XV_GATE_TRUTH_MISALIGNED.value,
            f"{Code.XV_GATE_TRUTH_MISALIGNED.value}: weight order "
            f"CONTRADICTS realized discrimination (spearman {rho:+.2f}, "
            f"n={n}) - re-weight decision needs the full gate battery, "
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

    rows = list(csv.DictReader(open(history_path, encoding="utf-8")))
    era = [r for r in rows if (r.get("label_era") or "") == "triple_barrier"]
    inst = [r for r in era if any(abs(_f(r.get(f"sg_{k}"))) > 0.0
                                  for k in SG_COMPONENT_KEYS)]
    out = ["GATE TRUTH REPORT", "=" * 60,
           f"corpus rows: {len(rows)}  era rows: {len(era)}  "
           f"instrumented era rows: {len(inst)}", ""]

    y = [1.0 if r.get("label") == "1" else 0.0 for r in inst]
    aucs = {}
    out.append("[1] per-component realized discrimination "
               "(aligned = s_i x direction)")
    for k in _WEIGHT_KEYS:
        a = [_f(r.get(f"sg_{k}")) * _f(r.get("direction"), 1.0)
             for r in inst]
        auc = _rank_auc(a, y) if inst else float("nan")
        aucs[k] = auc
        n_pos = sum(1 for v in a if v > 0)
        out.append(f"  {k:6s} w={weights[k]:.2f}  AUC={auc:.3f}  "
                   f"aligned_n={n_pos}/{len(a)}")
    out.append("")

    out.append("[2] evidence strength + concentration")
    for k in ("evidence", "conc"):
        a = [_f(r.get(f"sg_{k}")) for r in inst]
        # evidence is signed long/short: align it too; conc is unsigned
        if k == "evidence":
            a = [v * _f(r.get("direction"), 1.0)
                 for v, r in zip(a, inst, strict=True)]
        out.append(f"  {k:8s} AUC={_rank_auc(a, y) if inst else float('nan'):.3f}")
    out.append("")

    code, line = classify_alignment(weights, aucs, len(inst))
    out += ["[3] verdict", f"  {line}", ""]
    return "\n".join(out)


def main():
    print(build_report())
    return 0


if __name__ == "__main__":
    sys.exit(main())
