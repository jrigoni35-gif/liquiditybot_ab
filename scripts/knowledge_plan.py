"""scripts/knowledge_plan.py - which data teaches the bot the most next?
(SAFE: measurement only.)

    python scripts/knowledge_plan.py

THE MARKOV DECISION. Each registered hypothesis has a Gaussian belief about
its net edge mu = A - 2c (bps; A - 0 for a tilt), with sd from its CI.
Collecting one more independent block of forward data moves that belief - a
Markov transition of the knowledge state. The KNOWLEDGE GRADIENT (Frazier,
Powell & Dayanik 2008) is the optimal one-step policy for the value of that
observation. Here each hypothesis is its OWN act-or-not decision against the
null action (value 0): KG_i = s_i * f(-|mu_i| / s_i), f(z) = z Phi(z) +
phi(z), s_i = sd_i^2 / sqrt(sd_i^2 + obs_sd_i^2).

TIME TO A DECISION. If the true net edge equals today's estimate, an
optimal e-process grows at the KL rate mu^2 / (2 obs_sd^2) per block, so
reaching e = 20 (13 dB) takes about 2 ln(20) obs_sd^2 / mu^2 blocks.
"""
from __future__ import annotations

import glob
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

TWO_C = 45.0
E_TARGET = 20.0


def _phi(z: float) -> float:
    return math.exp(-z * z / 2) / math.sqrt(2 * math.pi)


def _Phi(z: float) -> float:
    return 0.5 * (1 + math.erf(z / math.sqrt(2)))


def knowledge_gradient(hyps: dict) -> dict:
    """Value of one more block of data for EACH hypothesis's own decision -
    act on it, or do nothing (value 0). Per-decision, not winner-take-all:
    the textbook KG compares to the best OTHER alternative, which let one
    wide-uncertainty hypothesis zero out every other's value (measured
    2026-10-02 - every KG but L5's read 0.00). The bot faces independent
    act-or-not decisions, so the comparison is the null action."""
    out = {}
    for k, h in hyps.items():
        s = h["sd"] ** 2 / math.sqrt(h["sd"] ** 2 + h["obs_sd"] ** 2)
        if s <= 0:
            out[k] = 0.0
            continue
        z = -abs(h["mu"]) / s
        out[k] = s * (z * _Phi(z) + _phi(z))
    return out


def blocks_to_decision(net_edge: float, obs_sd: float) -> float:
    if net_edge == 0:
        return math.inf
    return 2 * math.log(E_TARGET) * obs_sd ** 2 / net_edge ** 2


def block_weeks(node: dict) -> float:
    """Block length read from the series itself (review finding 9: a
    section-level map gave M1 four-week blocks it does not use)."""
    t = (node.get("series") or {}).get("t") or []
    if len(t) < 2:
        return 1.0
    d = min(b - a for a, b in zip(t[:-1], t[1:], strict=True))
    return max(d / 604800.0, 1e-9)


def main(argv=None) -> int:
    reg = json.loads((ROOT / "docs" / "quant" / "hypothesis_registry.json").read_text(encoding="utf-8"))
    rep = json.loads(Path(sorted(glob.glob(str(
        ROOT / "outputs" / "reports" / "alpha_decay" / "alpha_decay_*.json")))[-1]).read_text(encoding="utf-8"))
    hyps, meta = {}, {}
    for h in reg["hypotheses"]:
        node = rep.get(h["section"], {}).get(h["key"])
        if not isinstance(node, dict) or "A_ci_bps" not in node:
            continue
        lo, hi = node["A_ci_bps"]
        sd = (hi - lo) / 3.92
        nb = max(int(node.get("weeks", 1)), 1)
        target = 0.0 if h.get("use") == "tilt" else TWO_C
        hyps[h["id"]] = {"mu": node["A_bps"] - target, "sd": sd, "obs_sd": sd * math.sqrt(nb)}
        meta[h["id"]] = {"use": h.get("use", "trip"), "A": node["A_bps"],
                         "weeks_per_block": block_weeks(node)}
    kg = knowledge_gradient(hyps)
    print("knowledge plan - where the next forward data buys the most decision value")
    print(f"{'hypothesis':<28}{'use':<6}{'A bps':>8}{'net mu':>9}{'sd':>8}{'KG':>9}"
          f"{'weeks to a decision':>22}")
    for k in sorted(kg, key=lambda x: -kg[x]):
        h, m = hyps[k], meta[k]
        wk = blocks_to_decision(h["mu"], h["obs_sd"]) * m["weeks_per_block"]
        wk_s = "never (mu=0)" if math.isinf(wk) else (f"{wk:,.0f}" if wk < 1e6 else ">1e6")
        print(f"{k:<28}{m['use']:<6}{m['A']:>+8.1f}{h['mu']:>+9.1f}{h['sd']:>8.1f}"
              f"{kg[k]:>9.2f}{wk_s:>22}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
