"""scripts/pbo_row_sensitivity.py - is OF-3's reading stable in the corpus SIZE?

WHY THIS EXISTS. On 2026-09-12 `docs/quant/2026-09-12_pbo_null_calibration.md`
and `docs/HANDOFF.md` were both amended to say OF-3 (pbo) is UNSTABLE rather
than red, on the strength of a band measured by a session-scratch harness that
was then lost with the session. A red-team panel had charged exactly that
failure one day earlier (the four harnesses behind the same document's earlier
sections are also gone, and the document cannot be re-run). Publishing a second
claim by the same route would have repeated the finding instead of closing it.
So the harness is committed and the published numbers name THIS file.

The battery itself cannot answer the question: `scripts/overfit_check.py` calls
`model_space_pbo` once, at full T, and reports a POINT. A point cannot show that
the point moves.

METHOD.

  DETERMINISM CONTROL FIRST. The same array is scored twice. If the two disagree
  the estimator carries RNG and every spread below is that RNG, not corpus
  sensitivity - the run says so and stops claiming a band. This ordering is the
  whole method: "0 findings" and "the scan is broken" are the same observation
  until separated.

  TRUNCATION SWEEP. pbo is then recomputed on the first T-k rows for each k,
  through the same shipped entry point the battery uses, with the same
  arguments the battery passes (evidence gate via n_live, de Prado sample
  weights, the deployed simplicity-ladder selection rule, the adaptive rung
  included iff config enables it). Only the row count changes.

WHAT IT MEASURES, AND WHAT IT DOES NOT. The sweep is a REPRODUCIBILITY probe in
the metrology sense - one deliberate perturbation that must not change a verdict
if the verdict is about the strategy rather than about the sample. It is NOT a
%GRR: there is no repeatability component to pool (the estimator is
deterministic), and a ratio to the distance-to-threshold is not a variance
decomposition. Report the band and the distance to the gate; do not dress it as
an MSA number.

NOTHING IS WRITTEN. Read-only, no side effects, no file output - it prints.
Numbers move with the corpus, which the runner appends to every cycle, so the
row count is stamped on every line and NO figure from this tool belongs in a
permanent file without its T.

Usage:
    python scripts/pbo_row_sensitivity.py
    python scripts/pbo_row_sensitivity.py --drops 0,1,2,3,5,10,20
    python scripts/pbo_row_sensitivity.py --gate 0.5
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
if str(REPO / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO / "scripts"))


def parse_drops(spec: str) -> list[int]:
    """Parse a comma-separated drop list into sorted unique non-negative ints.

    Pure and unit-tested: the sweep's axis is the one thing a caller controls,
    so a silently-mangled axis would move every published number.
    """
    out: set[int] = set()
    for part in str(spec).split(","):
        part = part.strip()
        if not part:
            continue
        v = int(part)
        if v < 0:
            raise ValueError(f"drop counts must be >= 0, got {v}")
        out.add(v)
    if not out:
        raise ValueError("no drop counts parsed")
    return sorted(out)


def band(values: list[float]) -> float:
    """max - min over the sweep. 0.0 for a single reading."""
    vals = [float(v) for v in values]
    return (max(vals) - min(vals)) if len(vals) > 1 else 0.0


def straddles(values: list[float], gate: float) -> bool:
    """True when the sweep lands on BOTH sides of the gate.

    This is the finding-or-not predicate: a band that stays one side of the
    threshold is imprecision that costs nothing, while a band that crosses it
    means the verdict is a property of the row count.
    """
    vals = [float(v) for v in values]
    return any(v > gate for v in vals) and any(v <= gate for v in vals)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--drops", default="0,1,2,3,5,10",
                    help="comma-separated rows to drop from the END")
    ap.add_argument("--gate", type=float, default=0.5,
                    help="the pbo threshold OF-3 grades against")
    args = ap.parse_args(argv)
    drops = parse_drops(args.drops)

    import ml.overfit as mo
    from overfit_check import load_dataset

    X, y, w, sig, res, source, n_live = load_dataset()
    cfg = json.loads((REPO / "config.json").read_text(encoding="utf-8"))
    _ml = cfg.get("ml") or {}
    _ag = _ml.get("adaptive_gbt") or {}
    include_adaptive = bool(_ag.get("enabled", False))
    total = len(y)

    def run(k: int):
        n = total - k
        if n < 50:
            return None
        r = mo.model_space_pbo(
            X[:n], y[:n], n_splits=5, n_blocks=8,
            sig=(sig[:n] if sig is not None else None),
            res=(res[:n] if res is not None else None),
            sample_weight=(w[:n] if w is not None else None),
            n_live=n_live, include_adaptive=include_adaptive,
            adaptive_cfg=(_ag if include_adaptive else None),
            select_cfg=(_ml.get("model_selection") or None))
        return n, r.get("pbo"), r.get("n_configs"), r.get("median_lambda")

    print(f"corpus: {source}   T={total}   n_live={n_live}   "
          f"adaptive_rung={'in' if include_adaptive else 'out'}")

    a, b = run(0), run(0)
    if a is None or b is None:
        print("corpus too small to sweep")
        return 0
    deterministic = a[1] == b[1]
    print(f"\nDETERMINISM CONTROL  same array twice -> {a[1]:.6f} vs {b[1]:.6f}"
          f"   identical={deterministic}")
    if not deterministic:
        print("  ESTIMATOR CARRIES RNG. The spread below is that RNG, not corpus\n"
              "  sensitivity - no band is claimed and nothing here may be quoted\n"
              "  as a stability result.")

    print(f"\n  {'rows':>7}  {'pbo':>8}  {'ncfg':>5}  {'median_lambda':>14}  verdict")
    print("  " + "-" * 52)
    readings: list[float] = []
    for k in drops:
        got = run(k)
        if got is None:
            continue
        n, pbo, ncfg, med = got
        readings.append(float(pbo))
        print(f"  {n:>7}  {pbo:>8.4f}  {ncfg:>5}  {med:>+14.4f}  "
              f"{'RED' if pbo > args.gate else 'green'}")

    if not readings:
        print("\n  no readings")
        return 0

    bw = band(readings)
    n_red = sum(1 for v in readings if v > args.gate)
    print("  " + "-" * 52)
    print(f"  band over the sweep = {bw:.4f}     gate = {args.gate}")
    print(f"  {n_red}/{len(readings)} readings RED, "
          f"{len(readings) - n_red}/{len(readings)} green")
    if deterministic and straddles(readings, args.gate):
        print("\n  THE SWEEP STRADDLES THE GATE. OF-3's verdict on this corpus is a\n"
              "  property of the ROW COUNT, not of the strategy. Neither the red nor\n"
              "  the green is evidence; read the band, never a point.")
    elif deterministic:
        print("\n  The sweep stays one side of the gate: imprecise but not\n"
              "  verdict-changing at this corpus size.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
