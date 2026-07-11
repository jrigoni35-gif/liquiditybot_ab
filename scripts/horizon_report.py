"""
scripts/horizon_report.py

Reads the multi-horizon SHADOW evidence (outputs/horizon_shadow.csv,
written by ml.history.CandidateLabeler when ml.multi_horizon.enabled) and
answers the question that justifies adding a holding-horizon feature at
all: does some asset pair actually pay over a LONGER hold than another,
or is the short horizon always best?

For each asset x horizon it reports sample count, win rate, and mean net
return per trade, then flags each asset's best horizon by mean net
return. This is decision support, not a decision: it PROMOTES nothing.
A horizon feature moves into the live model only after this shows a
stable, material per-asset edge - never on a single window.

Usage:
    python scripts/horizon_report.py
    python scripts/horizon_report.py --shadow outputs/horizon_shadow.csv \
        --min-samples 20
"""

import argparse
import csv
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def load(path: Path):
    """(asset, horizon_bars) -> list of (label, net_ret_pct)."""
    agg = defaultdict(list)
    if not path.exists():
        return agg
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            try:
                key = (row["asset"], int(row["horizon_bars"]))
                agg[key].append((int(row["label"]),
                                 float(row["net_ret_pct"])))
            except (KeyError, ValueError):
                continue
    return agg


def build_report(path: Path, min_samples: int) -> str:
    agg = load(path)
    lines = ["Multi-horizon shadow report",
             "=" * 42,
             f"source: {path}"]
    if not agg:
        lines.append("")
        lines.append("no shadow evidence yet - ml.multi_horizon must be "
                     "enabled and candidates must have labeled. Let the run "
                     "accrue, then re-check.")
        return "\n".join(lines)

    assets = sorted({a for a, _ in agg})
    horizons = sorted({h for _, h in agg})
    lines.append(f"assets: {', '.join(assets)} | horizons(bars): "
                 f"{', '.join(map(str, horizons))}")
    lines.append("")
    lines.append(f"{'asset':<8}{'horizon':>8}{'n':>7}{'win%':>8}"
                 f"{'mean_net%':>11}")
    best = {}
    for a in assets:
        for h in horizons:
            rows = agg.get((a, h), [])
            if not rows:
                continue
            n = len(rows)
            win = 100.0 * sum(lb for lb, _ in rows) / n
            mean_ret = sum(r for _, r in rows) / n
            flag = "  (thin)" if n < min_samples else ""
            lines.append(f"{a:<8}{h:>8}{n:>7}{win:>7.1f}%{mean_ret:>10.3f}%"
                         f"{flag}")
            if n >= min_samples:
                if a not in best or mean_ret > best[a][1]:
                    best[a] = (h, mean_ret)
        lines.append("")

    lines.append("best horizon per asset (by mean net return, "
                 f">= {min_samples} samples):")
    if not best:
        lines.append("  none has enough samples yet - keep accruing shadow "
                     "evidence before trusting any horizon ranking.")
    else:
        for a in assets:
            if a in best:
                h, r = best[a]
                lines.append(f"  {a}: {h} bars (mean net {r:+.3f}% / trade)")
        lines.append("  NOTE: a best-horizon ranking is necessary but not "
                     "sufficient to promote. Confirm it is STABLE across "
                     "windows and material vs. the shortest horizon before "
                     "wiring horizon into the live model.")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--shadow", default="outputs/horizon_shadow.csv")
    ap.add_argument("--min-samples", type=int, default=20)
    ap.add_argument("--out", default="outputs/horizon_report.txt")
    args = ap.parse_args()
    report = build_report(Path(args.shadow), args.min_samples)
    print(report)
    try:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(report + "\n", encoding="utf-8")
        print(f"\nwritten: {args.out}")
    except OSError:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
