# scripts/gate_shuffle_replay.py
"""Verdict-level shuffle null for the gate-ecology regime coupling (Lane G).

The Lane F gate-ecology section 3 reports desk absorb rates by volatility
regime (EN-000 tick absorbs joined to cross-asset max vol percentile). The
verdict that would matter at the boundary — "absorbs cluster in
high-vol regimes" — needs its own null, at the level of the statistic
that would carry the claim (OF-2 shuffle discipline, TH-012 doctrine:
shuffle-null mandatory, never optional).

STATISTIC: Δ = absorb_rate(HIGH) − absorb_rate(LOW) in percentage points,
where HIGH = ticks whose desk vol percentile lands elevated|extreme per
the config-derived regime thresholds, LOW = low|normal. Tick-level
arrival/absorb counts stay PAIRED (within-tick absorb heterogeneity is
preserved); only the regime labels are permuted — the null is "absorb
counts are exchangeable against market state".

NULL: B label permutations (recorded seed). p = (1 + #{|perm| >= |obs|})
/ (B + 1) — the standard +1 correction; a 95% interval on p itself is
printed (normal approx at B, stated as such) so a small-B reading carries
its own uncertainty (the 2026-09-12 PBO lesson: a B=20 estimate is a wide
interval, not a verdict).

UNIDENTIFIED, never imputed: if either bucket has zero arrivals the
statistic is undefined and the report says so. Advisory only: read-only,
prints + JSON, changes nothing.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.gate_ecology import (  # noqa: E402 - after sys.path bootstrap
    CUT12_FLOOR,
    _iso,
    _parse_since,
    check_corpus,
    derive_constants,
    en000_ticks,
    load_sigma,
    read_chain_filtered,
    regime_label,
    vol_percentile,
)

REFUSAL_NO_JOINED_TICKS = "SHUFFLE_NO_JOINED_TICKS"

HIGH_LABELS = frozenset({"elevated", "extreme"})
DEFAULT_REPS = 2000
DEFAULT_SEED = 20260921  # analysis choice, not a fitted value; recorded


def joined_ticks(ticks: list, sigma_by_asset: dict) -> tuple[list, int]:
    """Per-tick (arrivals, absorbed, desk_pct) — the section-3 join,
    factored so the shuffle permutes exactly what section 3 joined."""
    rows, gaps = [], 0
    for t in ticks:
        pcts = {a: vol_percentile(s, t["ts"])
                for a, s in sigma_by_asset.items() if s is not None}
        pcts = {a: p for a, p in pcts.items() if p is not None}
        if not pcts:
            gaps += 1
            continue
        rows.append({
            "arrivals": int(t["delta"].get("arrivals", 0)),
            "absorbed": int(sum(v for k, v in t["delta"].items()
                                if k != "arrivals")),
            "desk_pct": max(pcts.values()),
        })
    return rows, gaps


def delta_pp(rows: list, consts: dict) -> float | None:
    """absorb_rate(HIGH) − absorb_rate(LOW), percentage points.
    None when either bucket has zero arrivals (UNIDENTIFIED)."""
    agg = {"high": [0, 0], "low": [0, 0]}
    for r in rows:
        label = regime_label(r["desk_pct"], consts["vol_low_pct"],
                             consts["vol_elevated_pct"],
                             consts["vol_extreme_pct"])
        bucket = "high" if label in HIGH_LABELS else "low"
        agg[bucket][0] += r["absorbed"]
        agg[bucket][1] += r["arrivals"]
    (h_abs, h_arr), (l_abs, l_arr) = agg["high"], agg["low"]
    if not h_arr or not l_arr:
        return None
    return 100.0 * (h_abs / h_arr - l_abs / l_arr)


def shuffle_null(rows: list, consts: dict, reps: int,
                 seed: int) -> dict:
    """Permutation null over regime labels; tick counts stay paired."""
    obs = delta_pp(rows, consts)
    if obs is None:
        return {"refused": None, "identified": False,
                "detail": "one regime bucket has zero arrivals — "
                          "the statistic is UNIDENTIFIED, not imputed"}
    rng = np.random.default_rng(seed)
    pcts = np.array([r["desk_pct"] for r in rows])
    base = [{k: r[k] for k in ("arrivals", "absorbed")} for r in rows]
    hits = 0
    for _ in range(reps):
        perm = rng.permutation(pcts)
        shuffled = [dict(b, desk_pct=p)
                    for b, p in zip(base, perm, strict=True)]
        d = delta_pp(shuffled, consts)
        if d is not None and abs(d) >= abs(obs):
            hits += 1
    p = (hits + 1) / (reps + 1)
    se = math.sqrt(p * (1.0 - p) / (reps + 1))
    return {
        "refused": None, "identified": True,
        "observed_delta_pp": round(obs, 3),
        "reps": reps, "seed": seed, "hits": hits,
        "p_value": round(p, 5),
        "p_value_ci95_normal": [round(max(0.0, p - 1.96 * se), 5),
                                round(min(1.0, p + 1.96 * se), 5)],
        "null": "absorb counts exchangeable against market-state labels",
    }


def replay(*, audit_path, corpus_dir, config_path, since, reps, seed) -> dict:
    cfg = json.loads(Path(config_path).read_text(encoding="utf-8"))
    consts = derive_constants(cfg)
    symbols, refusal = check_corpus(corpus_dir)
    if refusal:
        return {"refused": refusal}
    records, refusal = read_chain_filtered(
        audit_path, since, frozenset({"EN-000"}))
    if refusal:
        return {"refused": refusal}
    ticks = en000_ticks(records)
    sigma_by_asset = {
        s.replace("USDT", ""): load_sigma(corpus_dir, s, since,
                                          consts["vol_window_min"])
        for s in symbols}
    rows, gaps = joined_ticks(ticks, sigma_by_asset)
    if not rows:
        return {"refused": REFUSAL_NO_JOINED_TICKS}
    result = shuffle_null(rows, consts, reps, seed)
    result.update({
        "since": _iso(since), "run_ts": time.time(),
        "joined_ticks": len(rows), "corpus_gap_ticks": gaps,
        "regime_thresholds": {"low": consts["vol_low_pct"],
                              "elevated": consts["vol_elevated_pct"],
                              "extreme": consts["vol_extreme_pct"]},
        "vol_window_min": consts["vol_window_min"],
    })
    return result


def main() -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--audit", default="outputs/audit.jsonl")
    ap.add_argument("--corpus", default="research/corpus/binance_vision")
    ap.add_argument("--config", default="config.json")
    ap.add_argument("--since", default=None,
                    help="epoch seconds or ISO 8601 (default: cut-#12 floor)")
    ap.add_argument("--reps", type=int, default=DEFAULT_REPS)
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED)
    ns = ap.parse_args()
    since = _parse_since(ns.since) if ns.since else CUT12_FLOOR
    out = replay(audit_path=ns.audit, corpus_dir=ns.corpus,
                 config_path=ns.config, since=since,
                 reps=ns.reps, seed=ns.seed)
    if out["refused"]:
        print(f"SHUFFLE-REPLAY REFUSED: {out['refused']}")
        return 2
    if not out["identified"]:
        print(f"SHUFFLE-REPLAY UNIDENTIFIED: {out['detail']}")
        print(json.dumps(out, indent=2, sort_keys=True, default=str))
        return 0
    print("GATE SHUFFLE-REPLAY (Lane G, advisory, verdict-level null)")
    print(f"window since {out['since']} | joined ticks "
          f"{out['joined_ticks']} (corpus gaps {out['corpus_gap_ticks']})")
    print(f"observed Δ(high−low absorb rate) = {out['observed_delta_pp']}pp")
    print(f"shuffle null: B={out['reps']} seed={out['seed']} "
          f"hits={out['hits']} → p={out['p_value']} "
          f"(95% CI on p {out['p_value_ci95_normal']}, normal approx)")
    print()
    print(json.dumps(out, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
