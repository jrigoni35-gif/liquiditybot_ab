"""scripts/trip_explain.py - why did each closed trip make or lose what it did?

SAFE class: reads outputs/fills.csv, outputs/signal_history.csv (live rows),
outputs/trade_paths.csv and the candle store; writes ONE derived artifact,
outputs/trip_explanations.jsonl (schema TE-1, regenerated whole each run,
atomic replace). Nothing in the decision path imports it.

OPERATOR (2026-09-30): "Whether the position ends in a negative PnL or a
positive PnL, all features should couple in ways where said PnL and evidence
of why it resulted in that PnL should be apparent." / "react with a better
sample format that the bot can read in outputs".

THE IDENTITY (exact, per trip, USD; checked: identity_residual_usd):
    net = market + asset_specific + timing + slippage + fees
  fees            -sum(fees_delta_usd) over the trip's legs
  slippage        fill vs the leg's own arrival_ref (the mid when the order
                  was sent): sells (fill-ref)*size + buys (ref-fill)*size
  price           gross at arrival refs = market + asset_specific + timing
  market          side * beta * r_basket * entry_notional. r_basket = equal-
                  weight return of BTC/ETH/LINK EXCLUDING the traded asset
                  (scripts/beta_alpha_decomposition.py convention: PAXG out,
                  an asset never regressed on itself). beta = OLS of the
                  asset's 5m returns on the basket's over up to 7 days
                  BEFORE entry (never after: no look-ahead), >= 1 day of
                  aligned bars or the split is refused.
  asset_specific  side * (r_asset - beta * r_basket) * entry_notional
  timing          price - side * r_asset * notional: the fills vs the 5m
                  anchors (intra-bar timing, multi-leg averaging). Printed,
                  never hidden; a large one says the tape did not explain it.
  timing_split  (NOT part of the sum) entry = side*(anchor0 - ref0)*size:
                  what entering at the order's arrival mid instead of the last
                  closed 5m close cost; exit = timing - entry (exact
                  remainder: stop/target fills vs their anchors).
                  READ exit timing BY EXIT REASON, never pooled: the anchor
                  lags the fill by up to a bar, and a stop fires exactly
                  when price moves against the trade inside that bar, so
                  its exit timing is NEGATIVE BY CONSTRUCTION (targets
                  positive). Measured 2026-09-30: median entry 0.0 bps (no
                  chasing); exit tb_sl -32.7 (n=47), tb_pt +27.8 (n=9) -
                  anchor-lag selection, not a cost. The execution cost of an
                  exit is `slippage` (fill vs the leg's arrival mid).
  Returns to multi-leg exits are exit-notional-weighted over each leg's own
  time. A price is the CLOSE of the last bar closed by that instant (never
  the bar containing it - its close prints after the fill). Each asset's
  return uses ONE lane for both anchors: bot_cache (the bot's own ring,
  byte-faithful to its prices) first, else kraken.
  No tape -> market/asset_specific/timing are null and the price component
  is reported whole as price_unattributed; the identity still closes.

EVIDENCE (what the bot saw at entry; the live signal_history row):
  every *_dir feature is side-relative (ml/features.py dir_sign: > 0 = with
  the trade). Counted with / against, top 3 each by magnitude. p_win from
  trade_paths and gate_confidence verbatim. LANE = signal_history `probe`
  (1 probe / 0 conviction / blank unknown): a probe's p_win is the
  exploration constant, NOT a model estimate - read p_win only with lane.
  COUPLING = did the evidence majority point the way the price then moved.
  This is a description of one trip, NOT a test of a feature - a feature's
  worth is measured across trips (scripts/label_decomposition_report.py).

VERDICT (deterministic, pinned):
  net > 0             WIN_<driver>  driver = largest POSITIVE price part
  net <= 0, price > 0 COST_EATEN    the price paid; fees+slippage took more
  net <= 0, price <= 0 LOSS_<driver> driver = most NEGATIVE price part
  drivers: MARKET, ASSET, TIMING, PRICE (unattributed, no tape).
  Loss path tag from trade_paths: AHEAD_THEN_REVERSED when the trip's best
  excursion (mfe) exceeded its own round-trip cost, else NEVER_AHEAD.

CS-1: unit = position (trip). Every position_id in fills.csv lands in one
bucket (explained / open / hedge_book / exit_without_entry), reconciled.
Cohort = the ENTRY leg's decision_fp through core.cohort.cohort_of.

Usage: python scripts/trip_explain.py [--root DIR] [--no-write] [--last N]
"""
from __future__ import annotations

import argparse
import collections
import csv
import json
import os
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.cohort import cohort_of, reconcile  # noqa: E402

SCHEMA = "TE-1"
BASKET = ("BTC", "ETH", "LINK")
LANES = ("bot_cache", "kraken")          # preference order, never mixed
BAR_S = 300
BETA_WINDOW_S = 7 * 86400
BETA_MIN_BARS = 288                      # one day of aligned 5m returns
TOP_K = 3


def _f(x, d=0.0):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return d
    return v if np.isfinite(v) else d


# ---------------------------------------------------------------- loading
def load_positions(fills: Path) -> tuple[dict, dict]:
    """position_id -> legs (hedge legs excluded), plus CS-1 buckets."""
    legs = collections.defaultdict(list)
    hedge = set()
    with open(fills, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            pid = r["position_id"]
            if r.get("purpose") == "hedge":
                hedge.add(pid)
                continue
            legs[pid].append({
                "ts": _f(r["ts"]), "purpose": r["purpose"],
                "side": r["side"].lower()[:1], "size": abs(_f(r["fill_size"])),
                "price": _f(r["fill_price"]), "ref": _f(r.get("arrival_ref")),
                "fees": _f(r["fees_delta_usd"]), "remaining": _f(r["remaining"]),
                "reason": r.get("reason") or "", "symbol": r["symbol"],
                "fp": r.get("decision_fp") or ""})
    closed, buckets = {}, collections.Counter()
    for pid in set(legs) | hedge:
        lg = sorted(legs.get(pid, []), key=lambda x: x["ts"])
        ent = [x for x in lg if x["purpose"] == "entry"]
        ext = [x for x in lg if x["purpose"] == "exit"]
        if not ent:
            buckets["hedge_book" if pid in hedge else "exit_without_entry"] += 1
        elif not ext or ext[-1]["remaining"] > 1e-9:
            buckets["open"] += 1
        else:
            closed[pid] = lg
            buckets["explained"] += 1
    return closed, dict(buckets)


def load_evidence(history: Path) -> dict:
    """position_id -> the live row's side-relative features + gate_confidence."""
    out = {}
    if not history.exists():
        return out
    with open(history, newline="", encoding="utf-8") as fh:
        rd = csv.DictReader(fh)
        dirs = [c for c in (rd.fieldnames or []) if c.endswith("_dir")]
        for r in rd:
            if r.get("source") != "live" or not r.get("position_id"):
                continue
            out[r["position_id"]] = {
                "features": {c: _f(r.get(c)) for c in dirs},
                "gate_confidence": _f(r.get("gate_confidence"), None),
                "lane": {"1": "probe", "0": "conviction"}.get(
                    (r.get("probe") or "").strip())}
    return out


def load_paths(paths: Path) -> dict:
    out = {}
    if not paths.exists():
        return out
    with open(paths, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            out[r["position_id"]] = {
                "p_win": _f(r.get("p_win"), None),
                "mfe_pct": _f(r.get("mfe_pct"), None),
                "mae_pct": _f(r.get("mae_pct"), None),
                "stopped_out": r.get("stopped_out"), "cause": r.get("cause")}
    return out


class Tape:
    """close-of-last-closed-bar prices per (asset, lane), 5m."""

    def __init__(self, root: Path, assets):
        from data import candle_journal as cj
        self.series = {}
        for a in assets:
            for lane in LANES:
                v = cj.load_view(a, BAR_S, series=cj.Series(lane, "USD"),
                                 root=root)
                bars = [] if v.unreadable else v.bars(0, 2 ** 31)
                bars = [b for b in bars if not b.conflicted and b.close]
                if bars:
                    t = np.array([b.t_open_s for b in bars], float)
                    c = np.array([b.close for b in bars], float)
                    self.series[(a, lane)] = (t, c)

    def price(self, asset: str, lane: str, ts: float):
        s = self.series.get((asset, lane))
        if s is None:
            return None
        t, c = s
        i = int(np.searchsorted(t, ts - BAR_S, side="right")) - 1
        if i < 0 or ts - (t[i] + BAR_S) > 3 * BAR_S:   # gap = no anchor
            return None
        return float(c[i])

    def ret(self, asset: str, t0: float, times, weights):
        """Weighted return from t0 to each exit time, ONE lane for all
        anchors; (r, lane) or (None, None)."""
        for lane in LANES:
            p0 = self.price(asset, lane, t0)
            ps = [self.price(asset, lane, t) for t in times]
            if p0 and all(ps):
                return float(sum(w * (p / p0 - 1.0)
                                 for w, p in zip(weights, ps, strict=True))), lane
        return None, None

    def beta(self, asset: str, basket, t0: float):
        """OLS slope of asset 5m returns on the basket's, BEFORE t0."""
        best = None
        for lane in LANES:
            rs = {}
            for a in (asset, *basket):
                s = self.series.get((a, lane))
                if s is None:
                    break
                t, c = s
                m = (t >= t0 - BETA_WINDOW_S) & (t + BAR_S <= t0)
                rs[a] = dict(zip(t[m][1:], np.diff(c[m]) / c[m][:-1],
                                 strict=True))
            else:
                common = set(rs[asset])
                for a in basket:
                    common &= set(rs[a])
                if len(common) < BETA_MIN_BARS:
                    continue
                k = sorted(common)
                y = np.array([rs[asset][x] for x in k])
                x = np.mean([[rs[a][x] for x in k] for a in basket], axis=0)
                vx = float(np.var(x))
                if vx > 0:
                    best = (float(np.cov(x, y, bias=True)[0, 1] / vx), lane,
                            len(k))
                    break
        return best


# ---------------------------------------------------------------- core
def decompose(legs: list, asset: str, tape) -> dict:
    """The exact USD identity for one closed trip (see module docstring)."""
    ent = [x for x in legs if x["purpose"] == "entry"]
    ext = [x for x in legs if x["purpose"] == "exit"]
    side = 1 if ent[0]["side"] == "b" else -1
    notional = sum(x["size"] * x["price"] for x in ent)
    gross = sum((1 if x["side"] == "s" else -1) * x["size"] * x["price"]
                for x in legs)
    fees = -sum(x["fees"] for x in legs)
    slip = 0.0
    no_ref = 0
    for x in legs:
        ref = x["ref"] if x["ref"] > 0 else x["price"]
        no_ref += x["ref"] <= 0
        slip += (x["price"] - ref if x["side"] == "s" else ref - x["price"]) \
            * x["size"]
    price = gross - slip
    net = gross + fees
    comp = {"market": None, "asset_specific": None, "timing": None,
            "price_unattributed": None, "slippage": slip, "fees": fees}
    split = {"entry": None, "exit": None}
    cov = {"asset_lane": None, "basket_lane": None, "beta": None,
           "beta_bars": None, "legs_without_ref": no_ref, "reason": ""}
    t0 = ent[0]["ts"]
    ex_notl = [x["size"] * x["price"] for x in ext]
    w = [n / sum(ex_notl) for n in ex_notl] if sum(ex_notl) > 0 else []
    times = [x["ts"] for x in ext]
    basket = [a for a in BASKET if a != asset]
    r_a, lane_a = tape.ret(asset, t0, times, w) if tape and w else (None, None)
    rb = [tape.ret(a, t0, times, w) for a in basket] if tape and w else []
    bt = tape.beta(asset, basket, t0) if tape and r_a is not None else None
    if r_a is None:
        cov["reason"] = "no_asset_tape"
    elif not rb or any(r is None for r, _ in rb):
        cov["reason"] = "no_basket_tape"
    elif bt is None:
        cov["reason"] = "beta_window_short"
    if cov["reason"]:
        comp["price_unattributed"] = price
    else:
        r_b = float(np.mean([r for r, _ in rb]))
        beta, _lane_b, nb = bt
        comp["market"] = side * beta * r_b * notional
        comp["asset_specific"] = side * (r_a - beta * r_b) * notional
        comp["timing"] = price - side * r_a * notional
        p0 = tape.price(asset, lane_a, t0)
        size0 = sum(x["size"] for x in ent)
        ref0 = sum(x["size"] * (x["ref"] if x["ref"] > 0 else x["price"])
                   for x in ent) / size0 if size0 > 0 else 0.0
        if p0 and size0 > 0:
            split["entry"] = side * (p0 - ref0) * size0
            split["exit"] = comp["timing"] - split["entry"]
        cov.update(asset_lane=lane_a, basket_lane=rb[0][1], beta=beta,
                   beta_bars=nb)
    parts = [v for v in comp.values() if v is not None]
    return {"side": side, "notional": notional, "net": net, "gross": gross,
            "price": price, "components": comp, "coverage": cov,
            "timing_split": split,
            "identity_residual": net - sum(parts)}


DRIVER = {"market": "MARKET", "asset_specific": "ASSET", "timing": "TIMING",
          "price_unattributed": "PRICE"}


def verdict(dec: dict, path: dict | None) -> tuple[str, str]:
    comp = dec["components"]
    parts = {k: comp[k] for k in DRIVER if comp[k] is not None}
    if dec["net"] > 0:
        k = max(parts, key=lambda k: parts[k])
        return f"WIN_{DRIVER[k]}", ""
    if dec["price"] > 0:
        return "COST_EATEN", ""
    k = min(parts, key=lambda k: parts[k])
    tag = ""
    if path and path.get("mfe_pct") is not None and dec["notional"] > 0:
        cost_pct = -(comp["fees"] + comp["slippage"]) / dec["notional"] * 100
        tag = ("AHEAD_THEN_REVERSED" if path["mfe_pct"] > cost_pct
               else "NEVER_AHEAD")
    return f"LOSS_{DRIVER[k]}", tag


def evidence_block(ev: dict | None, price_usd: float) -> dict | None:
    if not ev:
        return None
    f = {k: v for k, v in ev["features"].items() if v != 0.0}
    w = sorted(((k, v) for k, v in f.items() if v > 0), key=lambda t: -t[1])
    a = sorted(((k, v) for k, v in f.items() if v < 0), key=lambda t: t[1])
    maj = "with" if len(w) > len(a) else "against" if len(a) > len(w) \
        else "split"
    moved = "with" if price_usd > 0 else "against"
    return {"n_with": len(w), "n_against": len(a), "majority": maj,
            "with_top": [[k, round(v, 4)] for k, v in w[:TOP_K]],
            "against_top": [[k, round(v, 4)] for k, v in a[:TOP_K]],
            "gate_confidence": ev["gate_confidence"],
            "lane": ev.get("lane"),
            "price_moved": moved,
            "majority_matched": None if maj == "split" else maj == moved}


def _usd(x):
    return None if x is None else round(float(x), 4)


def why(v: str, tag: str, dec: dict, asset: str) -> str:
    c = dec["components"]
    s = "long" if dec["side"] > 0 else "short"
    bits = [f"{v} {dec['net']:+.2f} USD on a {s} {asset}"]
    if c["market"] is not None:
        bits.append(f"market {c['market']:+.2f} (beta "
                    f"{dec['coverage']['beta']:.2f}), asset-specific "
                    f"{c['asset_specific']:+.2f}, timing {c['timing']:+.2f}")
    else:
        bits.append(f"price {c['price_unattributed']:+.2f} (no tape: "
                    f"{dec['coverage']['reason']})")
    bits.append(f"fees {c['fees']:+.2f}, slippage {c['slippage']:+.2f}")
    if tag:
        bits.append(tag.lower().replace("_", " "))
    return "; ".join(bits)


def explain(pid: str, legs: list, tape, evidence: dict, paths: dict) -> dict:
    ent = [x for x in legs if x["purpose"] == "entry"]
    ext = [x for x in legs if x["purpose"] == "exit"]
    asset = ent[0]["symbol"].split("/")[0]
    dec = decompose(legs, asset, tape)
    path = paths.get(pid)
    v, tag = verdict(dec, path)
    n = dec["notional"]
    return {
        "schema": SCHEMA, "position_id": pid, "asset": asset,
        "side": "long" if dec["side"] > 0 else "short",
        "cohort": cohort_of(ent[0]["fp"]),
        "entry_ts": ent[0]["ts"], "exit_ts": ext[-1]["ts"],
        "held_h": round((ext[-1]["ts"] - ent[0]["ts"]) / 3600, 3),
        "entry_notional_usd": _usd(n), "net_usd": _usd(dec["net"]),
        "components_usd": {k: _usd(x) for k, x in dec["components"].items()},
        "components_bps": {k: None if x is None or n <= 0 else
                           round(x / n * 1e4, 2)
                           for k, x in dec["components"].items()},
        "identity_residual_usd": _usd(dec["identity_residual"]),
        "timing_split_usd": {k: _usd(x) for k, x in
                             dec["timing_split"].items()},
        "coverage": dec["coverage"],
        "exit": {"reason": ext[-1]["reason"], "legs": len(ext),
                 "reasons": sorted({x["reason"] for x in ext})},
        "path": path,
        "evidence": evidence_block(evidence.get(pid), dec["price"]),
        "verdict": v, "path_tag": tag or None,
        "why": why(v, tag, dec, asset)}


# ---------------------------------------------------------------- shell
def write_jsonl(path: Path, recs: list) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        for r in recs:
            fh.write(json.dumps(r, sort_keys=True) + "\n")
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


def summarize(recs: list, buckets: dict, n_positions: int) -> str:
    L = [reconcile(n_positions, buckets)["line"]]
    by = collections.defaultdict(list)
    for r in recs:
        by[r["cohort"]].append(r)
    for coh, rs in sorted(by.items(), key=lambda kv: -len(kv[1])):
        tot = collections.Counter()
        for r in rs:
            for k, x in r["components_usd"].items():
                if x is not None:
                    tot[k] += x
        net = sum(r["net_usd"] for r in rs)
        L.append(f"\ncohort {coh}: {len(rs)} trips, net {net:+.2f} USD = "
                 + " + ".join(f"{k} {v:+.2f}" for k, v in tot.items()))
        vc = collections.Counter(r["verdict"] for r in rs)
        L.append("  verdicts: " + ", ".join(f"{k} {v}"
                                             for k, v in vc.most_common()))
        cp = collections.Counter(
            (r["evidence"]["majority"], r["evidence"]["price_moved"])
            for r in rs if r["evidence"])
        if cp:
            L.append("  evidence majority x price moved: " + ", ".join(
                f"{m}/{p} {c}" for (m, p), c in sorted(cp.items())))
        tagged = collections.Counter(r["path_tag"] for r in rs
                                     if r["path_tag"])
        if tagged:
            L.append("  losses by path: " + ", ".join(
                f"{k} {v}" for k, v in tagged.items()))
    worst = max((abs(r["identity_residual_usd"]) for r in recs), default=0)
    L.append(f"\nidentity: max |residual| {worst:.6f} USD over "
             f"{len(recs)} trips (must be ~0)")
    return "\n".join(L)


def run(root: Path, write: bool = True, last: int = 10) -> int:
    out = root / "outputs"
    closed, buckets = load_positions(out / "fills.csv")
    n_positions = sum(buckets.values())
    assets = set(BASKET) | {lg[0]["symbol"].split("/")[0]
                            for lg in closed.values()}
    tape = Tape(out / "candles", sorted(assets))
    ev, paths = load_evidence(out / "signal_history.csv"), \
        load_paths(out / "trade_paths.csv")
    recs = sorted((explain(pid, lg, tape, ev, paths)
                   for pid, lg in closed.items()),
                  key=lambda r: r["exit_ts"])
    print(f"trip_explain {SCHEMA} read {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}")
    print(summarize(recs, buckets, n_positions))
    for r in recs[-last:]:
        print(f"  {r['position_id'][:10]} {r['why']}")
    if write:
        write_jsonl(out / "trip_explanations.jsonl", recs)
        print(f"wrote {len(recs)} records -> {out / 'trip_explanations.jsonl'}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--root", type=Path, default=ROOT)
    ap.add_argument("--no-write", action="store_true")
    ap.add_argument("--last", type=int, default=10)
    a = ap.parse_args(argv)
    return run(a.root, write=not a.no_write, last=a.last)


if __name__ == "__main__":
    raise SystemExit(main())
