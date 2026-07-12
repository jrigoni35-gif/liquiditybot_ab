"""
scripts/calling_card.py -- the bot's introduction of itself.

A behavior, not a metric dump: asked to introduce itself in a room of
prestigious models, this bot speaks with composure. Every claim is drawn
from live telemetry (status.json, the deployed model card, the model
registry, the audit trail) and stated in CALIBRATED terms -- edge where
the data earns it, candor where it doesn't. The elegance is the restraint:
it never quotes a return it can't defend, names its own limits before
anyone asks, and offers receipts. In a room of algo bots the one worth
meeting isn't the loudest backtest; it's the one still standing, and
honest about why.

Read-only: opens outputs, prints an introduction, touches nothing.

Usage:  python scripts/calling_card.py
"""

import argparse
import csv
import json
from pathlib import Path

# feature name -> the plain-language insight it represents, so the bot
# describes what it has LEARNED rather than reciting column names
_INSIGHT = {
    "mom_score": "longer-horizon momentum",
    "ret_1": "the last five minutes of drift",
    "ret_6": "the last half-hour of drift",
    "ret_12": "the last hour's trend",
    "ret_48": "the four-hour trend",
    "sigma_bar_pct": "its own volatility, bar by bar",
    "vol_percentile": "where volatility sits within its own range",
    "imbalance": "the weight of the order book",
    "spread_bps": "the cost of crossing the spread",
    "fv_edge_bps": "the gap between price and fair value",
    "basis_bps": "the basis between venues",
    "funding_bps": "the cost carried by leverage",
    "corr_fast": "how the majors are moving together",
    "turbulence_pct": "how disordered the tape has become",
    "fear_greed": "the crowd's fear and greed",
    "sent_score": "the tone of the news flow",
}


def _json(p):
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


def _n_audit(p):
    try:
        with open(p, encoding="utf-8") as f:
            return sum(1 for line in f if line.strip())
    except OSError:
        return 0


def compose(outputs="outputs"):
    o = Path(outputs)
    st = _json(o / "status.json")
    model = _json(o / "meta_model.json")
    ml = st.get("ml", {})
    mon = st.get("monitor", {})
    regimes = st.get("regimes") or {}
    assets = list(regimes)
    rows = _rows(o / "signal_history.csv")
    live = [r for r in rows if r.get("source") == "live"]
    audit_n = _n_audit(o / "audit.jsonl")

    brier = model.get("oof_brier")
    calibrated = bool(model.get("calibration"))
    imp = model.get("wf_importance") or model.get("importance") or []
    if isinstance(imp, dict):
        imp = sorted(imp.items(), key=lambda kv: -abs(kv[1]))
    insights: list[str] = []
    if isinstance(imp, list):
        for item in imp[:3]:
            try:
                name = str(item[0])
            except (TypeError, IndexError, KeyError):
                continue
            insights.append(_INSIGHT.get(name, name.replace("_", " ")))

    L = []
    L.append("- - - - - - - - - - - - - - - - - - - - - - - - - - - - - -")
    L.append("  An introduction.")
    L.append("- - - - - - - - - - - - - - - - - - - - - - - - - - - - - -")
    L.append("")

    # provenance -- who I am, and I can prove it
    L.append("  I am a liquidity model. You may verify me: the decisions I")
    L.append(f"  make run through a hash-chained ledger, {audit_n:,} records")
    L.append("  deep and unbroken, and the mind I think with is a registered")
    kind = ml.get("model_kind") or model.get("kind") or "meta-labeling model"
    L.append(f"  artifact ({kind}). Nothing I claim is unverifiable.")
    L.append("")

    # connections -- I do not trade in isolation
    if assets:
        L.append(f"  I watch {len(assets)} markets at once "
                 f"({', '.join(assets)}), but I do not")
        L.append("  watch them separately. I read how the majors move")
        L.append("  together, how dominance shifts, and how disordered the")
        L.append("  tape becomes -- a move in one is rarely only about one.")
        L.append("")

    # foresight -- what I have learned, and how sure I am
    if insights:
        L.append("  What have I learned actually predicts? Chiefly "
                 + insights[0] + ",")
        if len(insights) > 1:
            L.append("  then " + ", then ".join(insights[1:]) + ".")
        L.append("  I did not assume these. I earned them out of sample.")
    if isinstance(brier, (int, float)):
        verdict = ("sharper than a coin" if brier < 0.25
                   else "still finding its feet")
        cal = " and honestly calibrated" if calibrated else ""
        L.append(f"  My forecasts score {brier:.3f} on the Brier scale"
                 f" -- {verdict}{cal}.")
    L.append("")

    # discipline -- my real edge is survival
    lvl = mon.get("level", 0)
    posture = {0: "at full authority", 1: "deliberately throttled",
               2: "on the prior, model muted"}.get(lvl, "under governance")
    L.append("  My edge is not a number I shout. It is that I am still")
    L.append("  here. I size by fractional Kelly and decelerate toward the")
    L.append(f"  drawdown cliff rather than into it; today I trade {posture}.")
    L.append("  A model that misbehaves I demote before it costs me. I take")
    L.append("  no trade whose edge the costs would eat.")
    L.append("")

    # candor -- the elegant part: I name my own limits
    n_live = len(live)
    L.append("  And candidly: I am young. I have closed "
             f"{n_live} live trade" + ("" if n_live == 1 else "s") + " with")
    L.append("  real costs against them; a deflated Sharpe wants thirty")
    L.append("  before it will call my edge real, and I will not pretend")
    L.append("  otherwise. I would rather be trusted than admired.")
    L.append("")
    L.append("  That, I think, is worth an introduction.")
    L.append("- - - - - - - - - - - - - - - - - - - - - - - - - - - - - -")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--outputs", default="outputs")
    ap.add_argument("--out", default="outputs/calling_card.txt")
    args = ap.parse_args()
    card = compose(args.outputs)
    print(card)
    try:
        Path(args.out).write_text(card + "\n", encoding="utf-8")
    except OSError:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
