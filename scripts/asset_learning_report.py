"""
scripts/asset_learning_report.py

Per-asset learning-progress view for a multi-pair paper run. When several
pairs (especially newly-added small caps) learn at once, the aggregate
session_digest hides whether EACH pair is actually progressing or silently
stuck. This reconciles the output files into one per-asset table:

  * live regime/liquidity  (outputs/status.json)  - why a pair may be gated
  * open candidates        (outputs/state.json)   - signals in flight
  * labeled rows           (signal_history.csv)   - training data accrued
  * horizon-shadow rows    (horizon_shadow.csv)   - long-vs-short evidence

and a conservative per-asset status: learning / gated-illiquid / quiet.
Read-only: opens outputs, writes a report, never touches live state or the
engine.

Usage:  python scripts/asset_learning_report.py
"""
import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path


def _load_json(p):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _rows(p):
    try:
        with open(p, newline="", encoding="utf-8") as f:
            return list(csv.DictReader(f))
    except (OSError, ValueError):
        return []


def _candidate_counts(state):
    """Open candidates per asset, robust to the nested candidates dict."""
    c = state.get("candidates", {})
    cands = []
    if isinstance(c, dict):
        for v in c.values():
            if isinstance(v, list) and v and isinstance(v[0], dict) \
                    and "asset" in v[0]:
                cands = v
                break
    return Counter(x.get("asset") for x in cands)


def build_report(outputs="outputs"):
    o = Path(outputs)
    status = _load_json(o / "status.json")
    state = _load_json(o / "state.json")
    regimes = status.get("regimes") or {}
    open_c = _candidate_counts(state)
    hist = _rows(o / "signal_history.csv")
    shadow = _rows(o / "horizon_shadow.csv")

    labeled = defaultdict(Counter)          # asset -> source -> n
    wins = defaultdict(int)
    for r in hist:
        a = r.get("asset")
        labeled[a][r.get("source") or "?"] += 1
        try:
            wins[a] += int(float(r.get("label", 0)))
        except (TypeError, ValueError):
            pass

    sh = defaultdict(lambda: defaultdict(list))   # asset -> horizon -> [ret]
    for r in shadow:
        try:
            sh[r.get("asset")][int(r.get("horizon_bars", 0))].append(
                float(r.get("net_ret_pct", 0)))
        except (TypeError, ValueError):
            pass

    assets = list(regimes) or sorted(set(open_c) | set(labeled) | set(sh))
    lines = ["per-asset learning progress", "=" * 60]
    for a in assets:
        rg = regimes.get(a, {})
        oc = open_c.get(a, 0)
        lab = labeled.get(a, Counter())
        nlab = sum(lab.values())
        liq = rg.get("liq", "?")
        spread = rg.get("spread_bps")
        spoof = rg.get("spoof")
        if nlab or oc:
            st = "learning"
        elif liq == "spoofy" or (isinstance(spread, (int, float))
                                 and spread >= 15):
            st = "gated: illiquid/spoofy (correct caution)"
        else:
            st = "quiet: no confirmed signal yet"
        lines.append(
            f"\n[{a}] {st}"
            f"\n  regime={rg.get('macro','?')} liq={liq} "
            f"spread={spread}bps spoof={spoof} vol_pct={rg.get('vol_pct')}"
            f"\n  open candidates: {oc} | labeled rows: {nlab} "
            f"({dict(lab)}) wins={wins.get(a, 0)}")
        if a in sh:
            parts = []
            for h in sorted(sh[a]):
                rets = sh[a][h]
                win = sum(1 for x in rets if x > 0) / len(rets)
                mean = sum(rets) / len(rets)
                # net_ret_pct is ALREADY in percent units (HorizonShadowStore
                # writes triple_barrier ret_pct); format as a plain number
                # with a literal % - a .2% format would multiply by 100 and
                # report -1.1% as a nonsensical -112%.
                parts.append(f"h{h}: n={len(rets)} win={win:.0%} "
                             f"mean_ret={mean:+.2f}%")
            lines.append("  horizon evidence: " + " | ".join(parts))
        else:
            lines.append("  horizon evidence: none yet (writes when a "
                         "candidate completes its full horizon)")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--outputs", default="outputs")
    ap.add_argument("--out", default="outputs/asset_learning_report.txt")
    args = ap.parse_args()
    rep = build_report(args.outputs)
    print(rep)
    try:
        Path(args.out).write_text(rep + "\n", encoding="utf-8")
        print(f"\nwritten: {args.out}")
    except OSError:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
