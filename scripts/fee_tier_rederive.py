#!/usr/bin/env python
"""fee_tier_rederive.py -- SAFE re-derivation helper for the 2026-08-29 fee-tier
correction adjudication (docs/quant/2026-08-29_fee_tier_correction_adjudication.md).

Re-derives every fee-dependent DECISION number under the live config's assumed
Kraken Tier-1 (40/80 bps, round-trip 1.20%) versus the operator-verified real
account tier, Kraken Tier-3 (22/38 bps, round-trip 0.60%; app screenshot
2026-08-29 14:58, $17,482.46 30d spot volume).

READ-ONLY. Touches no config, no outputs/, no state. Reads config.json for the
tier/stop geometry, then reconstructs the PositionSizer's own b_net / derived
p-bar via the SHIPPED formula (risk/position_sizer.py) at each fee schedule --
so the headline "entry bar 0.8335 -> ?" is the sizer's number, not a paraphrase.

Two independent routes for the entry bar:
  R1  construct the real PositionSizer with each pretrade fee block (asks the
      shipped object what bar it would set).
  R2  recompute payoff_ratio_from_config + 1/(1+b_net) by hand from config.
They must agree.

Usage:  ./.venv/Scripts/python.exe scripts/fee_tier_rederive.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from risk.position_sizer import PositionSizer, payoff_ratio_from_config  # noqa: E402

# --- fee schedules -----------------------------------------------------------
TIER1 = ("Kraken Tier-1 (config, cut #8)", 40.0, 80.0)   # rt 1.20%
TIER3 = ("Kraken Tier-3 (real account)", 22.0, 38.0)     # rt 0.60%


def load_cfg() -> dict:
    return json.loads((ROOT / "config.json").read_text(encoding="utf-8"))


def derive(cfg: dict, maker: float, taker: float) -> dict:
    """Return the sizer's b, b_net, derived p-bar for a given fee schedule.

    R1: build the real PositionSizer with an overridden pretrade fee block.
    R2: recompute by hand from the same config geometry.
    """
    profit_cfg = cfg["profit_taking"]
    risk_cfg = cfg["risk"]
    ps_cfg = cfg["position_sizer"]
    pretrade = dict(cfg["pretrade"])
    pretrade["maker_fee_bps"] = maker
    pretrade["taker_fee_bps"] = taker

    # R1 -- shipped object
    sizer = PositionSizer(ps_cfg, profit_cfg, risk_cfg, pretrade_cfg=pretrade)
    bar_r1 = sizer.p_bar_base

    # R2 -- hand recompute
    rt = (maker + taker) / 100.0
    reach = min(max(float(ps_cfg.get("tier_reach_decay", 0.65)), 0.05), 1.0)
    b_net_r2 = payoff_ratio_from_config(profit_cfg, risk_cfg,
                                        rt_cost_pct=rt, reach_decay=reach)
    edge = float(ps_cfg.get("p_bar_edge_margin", 0.0))
    floor = float(ps_cfg.get("min_p_win", 0.55))
    bar_r2 = max(1.0 / (1.0 + b_net_r2) + edge, floor)

    return {
        "maker": maker, "taker": taker, "rt_pct": rt,
        "b": sizer.b, "b_net": sizer.b_net,
        "bar_r1": bar_r1, "bar_r2": bar_r2,
        "agree": abs(bar_r1 - bar_r2) < 1e-9,
    }


def give_back_buffer(cfg: dict, est_fee_bps: float) -> dict:
    """Reproduce config_guard's give-back arm-vs-breakeven buffer check.

    be_buf_bps = be_buffer_bps + 2*est_fee_bps ; WARN if arm_gain*100 <= be_buf.
    """
    pt = cfg["profit_taking"]
    be_buffer = float(pt.get("be_buffer_bps", 6.0))
    arm = float(pt["give_back"]["arm_gain_pct"])
    be_buf = be_buffer + 2.0 * est_fee_bps
    return {"est_fee_bps": est_fee_bps, "be_buf_bps": be_buf,
            "arm_bps": arm * 100.0, "warn": arm * 100.0 <= be_buf}


def main() -> int:
    cfg = load_cfg()
    print("=" * 68)
    print("FEE-TIER RE-DERIVATION  (SAFE, read-only)")
    print("live config pretrade fees: %s/%s bps"
          % (cfg["pretrade"]["maker_fee_bps"], cfg["pretrade"]["taker_fee_bps"]))
    print("=" * 68)

    for name, mk, tk in (TIER1, TIER3):
        d = derive(cfg, mk, tk)
        print("\n%s  [%s/%s bps, rt %.2f%%]" % (name, mk, tk, d["rt_pct"]))
        print("  b (gross)   = %.4f" % d["b"])
        print("  b_net       = %.4f" % d["b_net"])
        print("  entry bar   = %.4f   (R1 sizer=%.4f R2 hand=%.4f agree=%s)"
              % (d["bar_r1"], d["bar_r1"], d["bar_r2"], d["agree"]))
        # label round-trip cost + barrier target
        rt_label = d["rt_pct"] / 2.0  # label cost tracks one-way? No: see doc.
        pt_mult = float(cfg["ml"].get("label_pt_cost_mult", 4.0))
        # label_round_trip_cost_pct is a standalone config knob; report the
        # coherent value (== rt) and its 4x barrier target.
        coherent_label = d["rt_pct"]
        print("  coherent label rt cost = %.2f%%  -> barrier target (%.1fx) = %.2f%%"
              % (coherent_label, pt_mult, pt_mult * coherent_label))

    print("\n" + "-" * 68)
    print("GIVE-BACK buffer (config_guard arm-vs-breakeven WARN):")
    for label, fee in (("Tier-1 est_fee_bps=80", 80.0),
                       ("Tier-3 est_fee_bps=38", 38.0)):
        g = give_back_buffer(cfg, fee)
        print("  %s: buffer=%.0fbps arm=%.0fbps WARN=%s"
              % (label, g["be_buf_bps"], g["arm_bps"], g["warn"]))

    print("\nLive config carries label_round_trip_cost_pct=%s, exploration.p_win=%s"
          % (cfg["ml"].get("label_round_trip_cost_pct"),
             cfg["ml"].get("exploration", {}).get("p_win")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
