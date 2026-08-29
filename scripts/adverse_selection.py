"""scripts/adverse_selection.py — the GAME-THEORETIC adverse-selection meter.

SAFE class. Reads outputs/fills.csv (realized fills, book of record) and the
candle store (public OHLC, read-only), writes nothing to outputs/. No decision
path, feature, veto, sizing rule, fill sim or order lifecycle is touched or
imported.

THE QUESTION. The bot plays a negative-sum game: gross edge ~0, venue rake
~120 bps round-trip (established in docs/quant/2026-08-29_fee_anatomy.md and
2026-08-29_fee_dominance_diagnosis.md — cited, not re-derived). Those docs
found net = -(fees); they did NOT resolve whether the ~0 gross is a SYMMETRIC
null (neutral, edge-less) or a NEGATIVE alpha masked by maker spread-capture
(ADVERSELY SELECTED — the 'sucker' filled precisely when informed flow is
about to run past). This instrument decomposes that.

THE MEASURE — post-fill mark-out, reusing execution/markout.py's sign
convention verbatim:

    markout_bps = side_sign * (mark - fill_price) / fill_price * 1e4
    side_sign   = +1 for a BUY fill, -1 for a SELL fill

POSITIVE = the market moved in the trade's favour after the fill (favourable);
NEGATIVE = the market moved AGAINST the trade right after it filled (adverse
selection — 'picked off'). Mirrored for sells exactly as markout.py does it.

markout.py's own DECOMPOSITION note is load-bearing here: markout_bps folds in
SPREAD CAPTURE (fill vs mid, fixed at the instant of fill, carries NO forward
information) plus ALPHA (the mid-to-mid remainder — the half worth watching).
A maker who buys below the reference has positive spread-capture BY
CONSTRUCTION; reading raw markout as edge would credit that half-spread as
prediction. So this module reports THREE numbers per cohort:

    raw markout   = side_sign * (fwd_close  - fill_price ) / fill_price  * 1e4
    alpha         = side_sign * (fwd_close  - anchor_close) / anchor_close * 1e4
    spread_capture= side_sign * (anchor_close - fill_price ) / fill_price  * 1e4

ALPHA is the decisive adverse-selection signal (spread-neutral, mid-to-mid).
raw ~= spread_capture + alpha (an identity up to the differing denominators).

FORWARD PRICE. The markout mark is reconstructed from the candle store
(data/candle_journal.py, validated in docs/quant/2026-08-29_candle_store_
coverage.md). The finest stored grid is 1h, so sub-hour pickoff is NOT
observable here — these horizons (1h/4h/24h) measure adverse drift over the
bot's ~2h holding period, not HFT-scale pickoff. anchor_close is the close of
the bar CONTAINING the fill (value_as_of up to one interval AFTER the fill);
fwd_close is the close of the bar `horizon` later. See the module's __main__
report and the companion doc for the exact reconstruction caveats.

Lanes (per the coverage doc's recommendation — require SIGN AGREEMENT before
concluding): kraken/USD @ 4h is the execution venue at the traded quote and
covers the full fills window (PRIMARY); okx/USDT @ 1h is finer but carries a
~+9 bps USDT/USD quote confound (CROSS-CHECK).
"""
from __future__ import annotations

import csv
import math
import os
import statistics
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from data import candle_journal as cj              # noqa: E402
from data.candle_journal import Series             # noqa: E402

FILLS_PATH = Path("outputs") / "fills.csv"

# Lane definitions: (name, source, quote, interval_s, horizons_s).
# horizons must be positive multiples of interval_s (forward_return refuses
# otherwise — a 1h horizon on a 4h grid would silently resolve to the anchor).
LANES = {
    "kraken4h": ("kraken", "USD", 14400, [14400, 86400]),
    "okx1h": ("okx", "USDT", 3600, [3600, 14400, 86400]),
}

H_LABEL = {3600: "1h", 14400: "4h", 86400: "24h"}


# ---------------------------------------------------------------------------
# core mark-out math (pure, unit-testable, mutation-killable)
# ---------------------------------------------------------------------------
def side_sign(side: str) -> float:
    """+1 for a buy, -1 for a sell — execution/markout.py's convention."""
    return 1.0 if side == "buy" else -1.0


def raw_markout_bps(side: str, fill_price: float, fwd_close: float) -> float:
    """Bot's realized-including-spread mark-out. Positive = favourable."""
    return side_sign(side) * (fwd_close - fill_price) / fill_price * 1e4


def alpha_bps(side: str, anchor_close: float, fwd_close: float) -> float:
    """Spread-neutral mid-to-mid alpha (the adverse-selection signal).
    Equals candle_journal.forward_return(...) * 100, by construction."""
    return side_sign(side) * (fwd_close - anchor_close) / anchor_close * 1e4


def spread_capture_bps(side: str, fill_price: float,
                       anchor_close: float) -> float:
    """The half-spread captured at the instant of fill — no forward info."""
    return side_sign(side) * (anchor_close - fill_price) / fill_price * 1e4


# ---------------------------------------------------------------------------
# effective-n: concurrency uniqueness (Lopez de Prado avg-uniqueness form)
# ---------------------------------------------------------------------------
def effective_n(times: list[float], horizon_s: float) -> float:
    """Sum of per-fill uniqueness over a cohort, where uniqueness_i =
    1 / (number of fills whose [t_j, t_j+H] window overlaps [t_i, t_i+H],
    self included). Windows that share a forward bar produce near-identical
    mark-outs, so nominal n badly overstates independence; n_eff is the honest
    denominator for the SE. POOLED across assets (conservative — crypto
    co-moves, so cross-asset overlapping fills are NOT independent draws).
    An SE on nominal n is optimistic by sqrt(n / n_eff)."""
    n = len(times)
    if n == 0:
        return 0.0
    ts = sorted(times)
    neff = 0.0
    for ti in ts:
        c = 0
        for tj in ts:
            if tj < ti + horizon_s and ti < tj + horizon_s:
                c += 1
        neff += 1.0 / c
    return neff


def daycluster_bootstrap(times: list[float], vals: list[float],
                         B: int = 5000, seed: int = 7) -> dict:
    """Independent second route to the SE, resampling whole UTC DAYS with
    replacement (the day is the cluster, matching cost_attribution's G=35
    day-clustering). Robust to intra-day overlap without assuming a uniqueness
    model — a cross-check on the concurrency-deflated n_eff CI, not a
    replacement for it. Returns mean + 95% percentile CI + share of resamples
    below zero."""
    import random
    if not vals:
        return {"n": 0}
    rng = random.Random(seed)
    days: dict[int, list[float]] = {}
    for t, v in zip(times, vals, strict=True):
        days.setdefault(int(t // 86400), []).append(v)
    keys = list(days)
    G = len(keys)
    means = []
    for _ in range(B):
        pool = []
        for _ in range(G):
            pool.extend(days[rng.choice(keys)])
        if pool:
            means.append(statistics.fmean(pool))
    means.sort()
    lo = means[int(0.025 * len(means))]
    hi = means[int(0.975 * len(means))]
    return {"n": len(vals), "n_day_clusters": G,
            "mean": round(statistics.fmean(vals), 3),
            "ci95_boot": [round(lo, 2), round(hi, 2)],
            "share_boot_below_zero": round(
                sum(1 for m in means if m < 0) / len(means), 3)}


@dataclass
class Cohort:
    label: str
    vals: list[float] = field(default_factory=list)
    times: list[float] = field(default_factory=list)

    def add(self, v: float, t: float) -> None:
        self.vals.append(v)
        self.times.append(t)

    def stats(self, horizon_s: float) -> dict:
        n = len(self.vals)
        if n == 0:
            return {"n": 0, "n_eff": 0.0, "mean": None, "median": None,
                    "se_eff": None, "t_eff": None, "ci95": None,
                    "share_neg": None}
        mean = statistics.fmean(self.vals)
        med = statistics.median(self.vals)
        sd = statistics.pstdev(self.vals) if n > 1 else 0.0
        neff = effective_n(self.times, horizon_s)
        se = sd / math.sqrt(neff) if neff > 0 else None
        t = mean / se if se and se > 0 else None
        ci = (mean - 1.96 * se, mean + 1.96 * se) if se else None
        share_neg = sum(1 for v in self.vals if v < 0) / n
        return {"n": n, "n_eff": round(neff, 2), "mean": round(mean, 3),
                "median": round(med, 3),
                "se_eff": round(se, 3) if se is not None else None,
                "t_eff": round(t, 3) if t is not None else None,
                "ci95": [round(ci[0], 2), round(ci[1], 2)] if ci else None,
                "share_neg": round(share_neg, 3)}


# ---------------------------------------------------------------------------
# fills + view plumbing
# ---------------------------------------------------------------------------
def base_symbol(symbol: str) -> str:
    """'ETH/USD' -> 'ETH' (candle-store base symbol)."""
    return symbol.split("/")[0]


def load_fills(path: Path = FILLS_PATH) -> tuple[list[dict], dict]:
    """Return (rows, snapshot) — snapshot carries mtime + read time so every
    number downstream is as-of, never 'current' (USAGE.md rule c)."""
    read_at = time.time()
    mtime = os.path.getmtime(path)
    with open(path, encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    ts = [float(r["ts"]) for r in rows]
    snap = {
        "path": str(path),
        "mtime_s": mtime,
        "mtime_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(mtime)),
        "read_at_s": read_at,
        "read_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                     time.gmtime(read_at)),
        "n_rows": len(rows),
        "ts_min": min(ts), "ts_max": max(ts),
        "ts_min_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(min(ts))),
        "ts_max_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(max(ts))),
    }
    return rows, snap


class ViewCache:
    """load_view re-parses the whole store per call; cache one view per
    (symbol, interval, series)."""
    def __init__(self, source: str, quote: str, interval_s: int):
        self.series = Series(source, quote)
        self.interval_s = interval_s
        self._cache: dict[str, object] = {}

    def get(self, base: str):
        v = self._cache.get(base)
        if v is None:
            v = self._cache[base] = cj.load_view(
                base, self.interval_s, series=self.series)
        return v


def markouts_for_lane(rows: list[dict], lane: str) -> dict:
    """Compute per-fill mark-outs for one lane at all its horizons and roll up
    into cohorts (overall / by leg / entry maker-vs-taker). side-signed."""
    source, quote, iv, horizons = LANES[lane]
    vc = ViewCache(source, quote, iv)
    # cohorts keyed by (horizon, metric, cohort_label)
    coh: dict[tuple, Cohort] = {}
    # reason accounting: how many fills resolve vs are excluded, and why
    reasons: dict[int, dict] = {h: {} for h in horizons}

    def C(h: int, metric: str, label: str) -> Cohort:
        k = (h, metric, label)
        c = coh.get(k)
        if c is None:
            c = coh[k] = Cohort(label)
        return c

    for r in rows:
        base = base_symbol(r["symbol"])
        side = r["side"]
        fp = float(r["fill_price"])
        ts = float(r["ts"])
        t0 = int(ts // iv) * iv
        leg = r["purpose"]                       # entry / exit / hedge
        mk = "maker" if r["post_only"] == "1" else "taker"
        view = vc.get(base)
        anchor_close, r_a, _ = view.price_at(t0)
        for h in horizons:
            fwd_close, r_b, _ = view.price_at(t0 + h)
            # OK requires BOTH legs present and positive (forward_return's bar)
            ok = (r_a == "OK" and anchor_close and anchor_close > 0
                  and r_b == "OK" and fwd_close and fwd_close > 0)
            reason = "OK" if ok else (f"anchor_{r_a}" if r_a != "OK"
                                      else f"forward_{r_b}")
            reasons[h][reason] = reasons[h].get(reason, 0) + 1
            if not ok:
                continue
            a = alpha_bps(side, anchor_close, fwd_close)
            m = raw_markout_bps(side, fp, fwd_close)
            s = spread_capture_bps(side, fp, anchor_close)
            # overall (all legs)
            C(h, "alpha", "overall").add(a, ts)
            C(h, "markout", "overall").add(m, ts)
            C(h, "spread", "overall").add(s, ts)
            # by leg
            C(h, "alpha", f"leg:{leg}").add(a, ts)
            C(h, "markout", f"leg:{leg}").add(m, ts)
            C(h, "spread", f"leg:{leg}").add(s, ts)
            # entry leg split maker/taker + by side (the winner's-curse test)
            if leg == "entry":
                C(h, "alpha", f"entry:{mk}").add(a, ts)
                C(h, "markout", f"entry:{mk}").add(m, ts)
                C(h, "spread", f"entry:{mk}").add(s, ts)
                C(h, "alpha", f"entry:{mk}:{side}").add(a, ts)
    out: dict = {"lane": lane, "source": source, "quote": quote,
                 "interval_s": iv, "horizons_s": horizons,
                 "reasons": reasons, "cohorts": {}}
    for (h, metric, label), c in coh.items():
        out["cohorts"].setdefault(str(h), {}).setdefault(metric, {})[label] = \
            c.stats(h)
    return out


# ---------------------------------------------------------------------------
# item 3: toxicity conditioning (corpus-level, realized net per trip)
# ---------------------------------------------------------------------------
def _net_seg_stats(seg: list[dict], tox_key: str) -> dict:
    """Roll up one toxicity bucket's realized net (net_pnl_usd, BOOKED fees).
    GROSS per trip is deliberately NOT reported: live corpus rows store
    exit_price=0.0 ('absent' per ml/history.py), and ml.corpus.gross_ret_pct
    guards only entry<=0, so it returns a spurious -/+100% for every live row
    (verified 2026-08-29; the instrument-is-first-suspect trap). net_pnl_usd
    is the trustworthy realized figure, and since the venue rake is a nearly
    constant per-trip offset, a net gradient across toxicity buckets reflects
    the GROSS gradient — a valid adverse-selection test on its own."""
    nets = [t["net_usd"] for t in seg]
    neff = effective_n([t["ts"] for t in seg], 14400.0)   # 4h window
    return {"tox_range": [round(seg[0][tox_key], 4), round(seg[-1][tox_key], 4)],
            "n": len(seg), "n_eff": round(neff, 2),
            "mean_net_usd": round(statistics.fmean(nets), 4),
            "median_net_usd": round(statistics.median(nets), 4),
            "total_net_usd": round(sum(nets), 4),
            "win_rate": round(sum(1 for x in nets if x > 0) / len(nets), 3)}


def toxicity_gradient(quantiles: int = 4) -> dict:
    """Bucket CLOSED live trips by flow_tox quantile and report realized net.
    A player that loses MORE in high-toxicity (informed-flow) states is being
    selected against by informed players. Uses the canonical corpus accessor
    (ml.corpus). Realized net = net_pnl_usd (BOOKED fees). manip_suspect is a
    second, independent toxicity axis (adversarial-data suspicion)."""
    import ml.corpus as corp
    trips = []
    for r in corp.iter_rows():
        if r.get("source") != "live":
            continue
        tox = r.get("flow_tox", "").strip()
        net = r.get("net_pnl_usd", "").strip()
        if not tox or not net:
            continue
        try:
            tox_f = float(tox)
            net_f = float(net)
            ts = float(r.get("signal_ts") or r.get("ts") or "nan")
        except ValueError:
            continue
        if math.isnan(ts):
            continue
        manip = r.get("manip_suspect", "").strip()
        trips.append({"tox": tox_f, "net_usd": net_f, "ts": ts,
                      "manip": float(manip) if manip else 0.0})
    n = len(trips)
    out = {"n_trips": n, "quantiles": quantiles, "flow_tox_buckets": [],
           "manip_split": []}
    if n == 0:
        return out
    # flow_tox quantiles
    trips.sort(key=lambda d: d["tox"])
    per = n / quantiles
    for q in range(quantiles):
        lo = int(round(q * per))
        hi = int(round((q + 1) * per)) if q < quantiles - 1 else n
        seg = trips[lo:hi]
        if seg:
            b = _net_seg_stats(seg, "tox")
            b["q"] = q + 1
            out["flow_tox_buckets"].append(b)
    # manip_suspect split (== 0 vs > 0) — a distinct adversarial-flow axis
    for label, seg in (("manip==0", [t for t in trips if t["manip"] <= 0.0]),
                       ("manip>0", [t for t in trips if t["manip"] > 0.0])):
        if seg:
            seg = sorted(seg, key=lambda d: d["manip"])
            b = _net_seg_stats(seg, "manip")
            b["label"] = label
            out["manip_split"].append(b)
    return out


def entry_alpha_series(rows: list[dict], lane: str, horizon_s: int,
                       era: "str | None" = None) -> tuple[list[float],
                                                          list[float]]:
    """(times, alpha_bps) for ENTRY fills at one horizon, optionally filtered
    to one exec_era ('' selects pre-stamp era-4-and-earlier; None = all).
    Used for the double-derive bootstrap and the era-invariance check."""
    source, quote, iv, _ = LANES[lane]
    vc = ViewCache(source, quote, iv)
    ts_out, a_out = [], []
    for r in rows:
        if r["purpose"] != "entry":
            continue
        if era is not None and (r.get("exec_era") or "") != era:
            continue
        base = base_symbol(r["symbol"])
        ts = float(r["ts"])
        t0 = int(ts // iv) * iv
        view = vc.get(base)
        a_close, r_a, _ = view.price_at(t0)
        f_close, r_b, _ = view.price_at(t0 + horizon_s)
        if r_a == "OK" and a_close and a_close > 0 and r_b == "OK" \
                and f_close and f_close > 0:
            ts_out.append(ts)
            a_out.append(alpha_bps(r["side"], a_close, f_close))
    return ts_out, a_out


def typical_move_bps(rows: list[dict], lane: str, horizon_s: int) -> dict:
    """Median ABSOLUTE mid-to-mid alpha over ENTRY fills at one horizon — the
    game's natural per-trip price volatility over the holding window,
    measured cleanly from the candle store (the corpus gross is unusable, see
    _net_seg_stats). This is the denominator of the house-edge ratio."""
    source, quote, iv, _ = LANES[lane]
    vc = ViewCache(source, quote, iv)
    absmoves = []
    for r in rows:
        if r["purpose"] != "entry":
            continue
        base = base_symbol(r["symbol"])
        ts = float(r["ts"])
        t0 = int(ts // iv) * iv
        view = vc.get(base)
        a_close, r_a, _ = view.price_at(t0)
        f_close, r_b, _ = view.price_at(t0 + horizon_s)
        if r_a == "OK" and a_close and a_close > 0 and r_b == "OK" \
                and f_close and f_close > 0:
            absmoves.append(abs(alpha_bps(r["side"], a_close, f_close)))
    if not absmoves:
        return {"n": 0, "median_abs_alpha_bps": None}
    return {"n": len(absmoves),
            "median_abs_alpha_bps": round(statistics.median(absmoves), 2),
            "mean_abs_alpha_bps": round(statistics.fmean(absmoves), 2)}


# ---------------------------------------------------------------------------
# item 4: the rake as house edge
# ---------------------------------------------------------------------------
def house_edge_ratio(rows: list[dict], rake_bps: float = 120.8) -> dict:
    """rake / typical absolute per-trip move — how large the house's cut is
    relative to the game's natural volatility. rake_bps default = the
    venue-true median round-trip from docs/quant/2026-08-29_fee_anatomy.md
    (120.8 bps, cited not re-derived). 'Typical move' = median |alpha| over
    entry fills at the ~holding horizon (4h kraken primary, 1h okx
    cross-check) — the clean candle-store measure of the game's natural
    volatility over the holding window (the corpus gross is unusable)."""
    k4 = typical_move_bps(rows, "kraken4h", 14400)
    o1 = typical_move_bps(rows, "okx1h", 3600)
    o4 = typical_move_bps(rows, "okx1h", 14400)
    prim = k4["median_abs_alpha_bps"]
    return {"rake_bps": rake_bps,
            "typical_move_kraken4h_bps": prim,
            "typical_move_okx1h_bps": o1["median_abs_alpha_bps"],
            "typical_move_okx4h_bps": o4["median_abs_alpha_bps"],
            "house_edge_ratio_primary": (round(rake_bps / prim, 2)
                                         if prim else None),
            "house_edge_ratio_okx1h": (round(rake_bps / o1["median_abs_alpha_bps"], 2)
                                       if o1["median_abs_alpha_bps"] else None)}


# ---------------------------------------------------------------------------
# sign-convention self-test (the instrument-verification hook)
# ---------------------------------------------------------------------------
def self_test() -> list[str]:
    """PLANTED cases that PROVE the sign convention. A markout sign error
    inverts the entire conclusion (adverse<->favourable), so this must pass
    before any null is trusted. Returns a list of failure strings ([] = OK)."""
    fails = []
    # BUY fill at 100, market rises to 101 -> FAVOURABLE -> positive.
    if not raw_markout_bps("buy", 100.0, 101.0) > 0:
        fails.append("BUY + up-move must be POSITIVE (favourable)")
    # BUY fill at 100, market falls to 99 -> ADVERSE -> negative.
    if not raw_markout_bps("buy", 100.0, 99.0) < 0:
        fails.append("BUY + down-move must be NEGATIVE (adverse)")
    # SELL fill at 100, market falls to 99 -> FAVOURABLE for a short -> pos.
    if not raw_markout_bps("sell", 100.0, 99.0) > 0:
        fails.append("SELL + down-move must be POSITIVE (favourable short)")
    # SELL fill at 100, market rises to 101 -> ADVERSE for a short -> neg.
    if not raw_markout_bps("sell", 100.0, 101.0) < 0:
        fails.append("SELL + up-move must be NEGATIVE (adverse short)")
    # magnitude: buy 100 -> 101 is +100 bps exactly.
    mo = raw_markout_bps("buy", 100.0, 101.0)
    if abs(mo - 100.0) > 1e-9:
        fails.append(f"BUY 100->101 must be +100.0 bps, got {mo}")
    # alpha mirrors: buy, anchor 100, fwd 99 -> -100 bps adverse.
    if abs(alpha_bps("buy", 100.0, 99.0) + 100.0) > 1e-9:
        fails.append("alpha BUY 100->99 must be -100.0 bps")
    # spread capture: maker buy below reference is POSITIVE capture.
    if not spread_capture_bps("buy", 99.5, 100.0) > 0:
        fails.append("BUY below reference must be POSITIVE spread capture")
    return fails


def negative_arm() -> int:
    """NEGATIVE ARM (the control): plant a KNOWN defect — a sign-INVERTED
    markout — and confirm the sign-convention checks CATCH it. A self-test
    that stays green under an inverted instrument is vacuous (assurance C2:
    a null arm proves the instrument does not cry wolf, never that it can
    detect anything). Returns how many of the four directional planted cases
    the inverted instrument trips; must be all four."""
    def inv(side: str, fill: float, fwd: float) -> float:
        return -raw_markout_bps(side, fill, fwd)
    return sum((
        inv("buy", 100.0, 101.0) <= 0,    # planted POSITIVE, inversion trips it
        inv("buy", 100.0, 99.0) >= 0,     # planted NEGATIVE
        inv("sell", 100.0, 99.0) <= 0,    # planted POSITIVE (short)
        inv("sell", 100.0, 101.0) >= 0,   # planted NEGATIVE (short)
    ))


# ---------------------------------------------------------------------------
# report
# ---------------------------------------------------------------------------
def _fmt_cohort(name: str, s: dict) -> str:
    if s["n"] == 0:
        return f"    {name:<22} n=0"
    sig = ""
    if s["t_eff"] is not None:
        sig = "  SIG" if abs(s["t_eff"]) >= 1.96 else "  ns"
    return (f"    {name:<22} n={s['n']:>4} n_eff={s['n_eff']:>6} "
            f"mean={s['mean']:>8} bps  median={s['median']:>8}  "
            f"CI95={s['ci95']}  t={s['t_eff']}{sig}")


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--lane", choices=["kraken4h", "okx1h", "both"],
                    default="both")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args(argv)

    fails = self_test()
    neg = negative_arm()
    print("== SIGN-CONVENTION SELF-TEST ==")
    print("  PASS 7/7 planted cases" if not fails else "  FAIL:")
    for f in fails:
        print("   -", f)
    # NEGATIVE ARM / control: the inverted-sign instrument must be caught by
    # all 4 directional cases; a self-test that survives inversion is vacuous.
    print(f"  negative arm (control): inverted-sign instrument caught by "
          f"{neg}/4 planted cases")
    neg_ok = neg == 4
    if not neg_ok:
        print("   - CONTROL FAILED: self-test does not detect an inverted sign")
    if args.self_test:
        return 0 if (not fails and neg_ok) else 1
    if fails:
        print("ABORT: sign convention broken; no null is trustworthy.")
        return 1

    rows, snap = load_fills()
    print("\n== FILLS SNAPSHOT ==")
    print(f"  {snap['path']}  n={snap['n_rows']}")
    print(f"  mtime {snap['mtime_utc']}  read {snap['read_at_utc']}")
    print(f"  ts [{snap['ts_min_utc']}, {snap['ts_max_utc']}]  "
          f"([{snap['ts_min']}, {snap['ts_max']}])")

    lanes = ["kraken4h", "okx1h"] if args.lane == "both" else [args.lane]
    for lane in lanes:
        res = markouts_for_lane(rows, lane)
        print(f"\n== LANE {lane} ({res['source']}/{res['quote']} "
              f"@ {res['interval_s']}s) ==")
        for h in res["horizons_s"]:
            hl = H_LABEL.get(h, f"{h}s")
            rr = res["reasons"][h]
            ok = rr.get("OK", 0)
            print(f"\n  --- horizon {hl} (resolved {ok}/{sum(rr.values())}; "
                  f"reasons {dict(sorted(rr.items()))}) ---")
            ch = res["cohorts"][str(h)]
            print("  ALPHA (mid-to-mid, adverse-selection signal):")
            for name in ["overall", "leg:entry", "leg:exit", "leg:hedge",
                         "entry:maker", "entry:taker",
                         "entry:maker:buy", "entry:maker:sell",
                         "entry:taker:buy", "entry:taker:sell"]:
                if name in ch.get("alpha", {}):
                    print(_fmt_cohort(name, ch["alpha"][name]))
            print("  RAW MARKOUT (incl. spread capture):")
            for name in ["overall", "leg:entry", "entry:maker", "entry:taker"]:
                if name in ch.get("markout", {}):
                    print(_fmt_cohort(name, ch["markout"][name]))
            print("  SPREAD CAPTURE (no forward info):")
            for name in ["leg:entry", "entry:maker", "entry:taker"]:
                if name in ch.get("spread", {}):
                    print(_fmt_cohort(name, ch["spread"][name]))

    print("\n== DOUBLE-DERIVE + ERA CHECK: entry-leg ALPHA, kraken4h @ 4h ==")
    t_all, a_all = entry_alpha_series(rows, "kraken4h", 14400)
    boot = daycluster_bootstrap(t_all, a_all)
    print(f"  ALL eras: n={boot['n']} G_days={boot['n_day_clusters']} "
          f"mean={boot['mean']} bps  boot_CI95={boot['ci95_boot']}  "
          f"P(mean<0)={boot['share_boot_below_zero']}")
    for era_lbl, era_val in [("era4/pre-stamp (blank)", ""),
                             ("era7-e7d5ca1a", "7-e7d5ca1a")]:
        t_e, a_e = entry_alpha_series(rows, "kraken4h", 14400, era=era_val)
        if a_e:
            m = statistics.fmean(a_e)
            neff = effective_n(t_e, 14400.0)
            print(f"  {era_lbl:<24} n={len(a_e)} n_eff={neff:.1f} "
                  f"mean_alpha={m:.2f} bps")

    print("\n== ITEM 3: TOXICITY CONDITIONING (closed live trips, net_pnl_usd) ==")
    tox = toxicity_gradient()
    print(f"  n_trips={tox['n_trips']} (realized net = net_pnl_usd, booked fees)")
    print("  by flow_tox quantile:")
    for b in tox["flow_tox_buckets"]:
        print(f"    Q{b['q']} tox{b['tox_range']} n={b['n']} "
              f"n_eff={b['n_eff']} mean_net=${b['mean_net_usd']} "
              f"median_net=${b['median_net_usd']} total=${b['total_net_usd']} "
              f"win={b['win_rate']}")
    print("  by manip_suspect:")
    for b in tox["manip_split"]:
        print(f"    {b['label']:<9} n={b['n']} n_eff={b['n_eff']} "
              f"mean_net=${b['mean_net_usd']} median_net=${b['median_net_usd']} "
              f"total=${b['total_net_usd']} win={b['win_rate']}")

    print("\n== ITEM 4: RAKE AS HOUSE EDGE ==")
    he = house_edge_ratio(rows)
    print(f"  rake {he['rake_bps']} bps (venue-true RT, fee_anatomy)")
    print(f"  typical |move| kraken4h={he['typical_move_kraken4h_bps']} bps  "
          f"okx1h={he['typical_move_okx1h_bps']} bps  "
          f"okx4h={he['typical_move_okx4h_bps']} bps")
    print(f"  HOUSE EDGE = rake / typical move = "
          f"{he['house_edge_ratio_primary']}x (kraken4h primary), "
          f"{he['house_edge_ratio_okx1h']}x (okx1h)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
