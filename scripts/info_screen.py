"""scripts/info_screen.py - does NEW information (the signed trade tape) carry
direction? REPORT-ONLY: reads outputs/signal_history.csv + outputs/ticks/,
writes nothing, decides nothing.

WHY (operator 2026-10-01, "Yes" to the new-information screen). Every
measurement says the bot's current features carry no tradeable direction
(Markov/Brownian walk-forward 2026-09-29/30: best within-day AUC ~0.54, about
delta 0.5 = 40% of break-even). The lever is new information. The 09-01
edge-hunter mirror already tried the tape and found (a) the stored L2
imbalance is not reconstructable from it and (b) trade INTENSITY predicts
resolution, not direction (direction AUC 0.510, 0/7 pairs). It never tested
SIGNED aggressor flow, large-trade flow, market-order flow or BTC-leads-alts,
and it graded with a POOLED AUC - which the 2026-09-30 power run showed is
blind under the day-level drift. This screen tests the untested signals with
the metric that has power.

PRE-REGISTERED 2026-10-01, before the first run:
  rows     candidate rows (source != live), label_era triple_barrier_h432,
           assets whose tape covers the row; DIRECTION target only: resolved
           rows (tb_pt / tb_sl), market-absolute "up barrier hit first"
           (09-01 rule: resolution and direction are separate channels).
  cutoff   a signal uses trades with time < signal_ts + 300 s (the entry
           bar's close = the entry price); the label path starts at the next
           bar, so nothing a signal sees is inside its own label.
  signals  SIGNALS below, 7, market-absolute (+ = buy pressure).
           Large trades = notional >= the asset's 95th percentile over the
           FIRST 7 days of its tape (before every scored row: no look-ahead).
  metric   PRIMARY within-day AUC (mean of per-UTC-day AUCs, days with both
           classes); day-block bootstrap CI (BOOT reps); within-day
           permutation null (NULL_REPS), two-sided |AUC-0.5|. Bonferroni over
           the 7 signals. Pooled AUC printed beside it (day-level confound).
  power    implied delta from the 2026-09-30 power curve (basis-state
           structure, real day level: AUC 0.517 @ 0.3, 0.549 @ 0.6, 0.625 @
           1.2) - a ROUGH [I] translation, break-even is delta ~1.2.
  counting CS-1 over every candidate row read.

CORRECTION 2026-10-01, found by this tool's own first run (read before the
numbers). The within-day AUC is BIASED for any score derived from the same
price path the labels come from: rows inside one day share one path, so row
B's "past" is row A's "future", and comparing rows against each other
manufactures contrarian ranking under a pure random walk (simulated:
within-(day,asset) AUC 0.39 for the 1h return with zero predictability). The
within-day permutation null shuffles scores and destroys that structure, so
it is too narrow for such scores. Signed flow correlates +0.23 with the 30 min
return, so it inherits part of the bias. Measured, in order:
  - flow_30m, decision-time cutoff (bar OPEN): 0.460 [0.435, 0.481]; halves
    0.459 / 0.461 - stable
  - flow residualised on past 5m/30m/1h returns: 0.485 [0.459, 0.506] - the
    flow lead is mostly the return in disguise
  - past 1h / 30m return vs a SIGN-FLIP null (real returns, random signs:
    real volatility kept, direction destroyed), same close-only procedure:
    real 0.2945 / 0.3332 vs null 0.360 [0.324, 0.398] / 0.392 - p 0.016:
    real short-horizon reversal beyond the artifact, ~0.06-0.07 AUC excess,
    in features the bot ALREADY has (ret_*_dir).
  - Independent confirmation of direction AND economics: Kitron &
    Wengrowicz arXiv:2608.21888 - real crypto 15 min reversal, gross ~1.3 bp
    vs a 5 bp cost: sub-cost; this bot's round trip is ~45 bps.
For path-derived scores, grade against a sign-flip null, never the
within-day permutation null.

Usage: python scripts/info_screen.py [--root DIR] [--null-reps N]
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.cohort import reconcile  # noqa: E402

ERA = "triple_barrier_h432"
BAR_S = 300.0
BOOT = 1000
NULL_REPS = 500
SEED = 11
PAIR = {"BTC": "XBTUSD", "ETH": "ETHUSD", "LINK": "LINKUSD", "PAXG": "PAXGUSD",
        "ADA": "ADAUSD", "SOL": "SOLUSD", "XRP": "XRPUSD", "DOGE": "XDGUSD",
        "DOT": "DOTUSD", "ARB": "ARBUSD", "SUI": "SUIUSD", "MINA": "MINAUSD",
        "FLOW": "FLOWUSD", "AVAX": "AVAXUSD", "LTC": "LTCUSD"}
SIGNALS = ("flow_5m", "flow_30m", "flow_2h", "mkt_flow_30m", "large_flow_2h",
           "lead_flow_30m", "flow_accel")
POWER = ((0.5, 0.0), (0.517, 0.3), (0.549, 0.6), (0.625, 1.2), (0.703, 2.0))


class Tape:
    """Prefix sums of signed notional for one pair, O(log n) window queries."""

    def __init__(self, pair_dir: Path):
        import pandas as pd
        files = sorted(Path(pair_dir).glob("*.parquet"))
        if not files:
            raise FileNotFoundError(pair_dir)
        df = pd.concat([pd.read_parquet(f, columns=["time_s", "price", "volume",
                                                    "side", "otype"])
                        for f in files], ignore_index=True)
        df = df.sort_values("time_s", kind="stable")
        self.t = df["time_s"].to_numpy(float)
        notl = (df["price"] * df["volume"]).to_numpy(float)
        sgn = np.where(df["side"].to_numpy() == "b", 1.0, -1.0)
        mkt = df["otype"].to_numpy() == "m"
        first = self.t[0] + 7 * 86400
        ref = notl[self.t < first]
        self.large_thr = float(np.quantile(ref, 0.95)) if len(ref) else np.inf
        big = notl >= self.large_thr
        z = np.zeros(1)
        self.c_signed = np.concatenate([z, np.cumsum(sgn * notl)])
        self.c_abs = np.concatenate([z, np.cumsum(notl)])
        self.c_mkt_s = np.concatenate([z, np.cumsum(sgn * notl * mkt)])
        self.c_mkt_a = np.concatenate([z, np.cumsum(notl * mkt)])
        self.c_big_s = np.concatenate([z, np.cumsum(sgn * notl * big)])
        self.c_big_a = np.concatenate([z, np.cumsum(notl * big)])
        self.t0, self.t1 = float(self.t[0]), float(self.t[-1])

    def covers(self, start: float, end: float) -> bool:
        return self.t0 <= start and end <= self.t1

    def _imb(self, cs, ca, start, end):
        i, j = np.searchsorted(self.t, [start, end], side="left")
        a = ca[j] - ca[i]
        return float((cs[j] - cs[i]) / a) if a > 0 else 0.0

    def flow(self, start, end):
        return self._imb(self.c_signed, self.c_abs, start, end)

    def mkt_flow(self, start, end):
        return self._imb(self.c_mkt_s, self.c_mkt_a, start, end)

    def large_flow(self, start, end):
        return self._imb(self.c_big_s, self.c_big_a, start, end)


def signals_at(tape: Tape, lead: Tape | None, cut: float) -> dict | None:
    if not tape.covers(cut - 7200, cut):
        return None
    out = {"flow_5m": tape.flow(cut - 300, cut),
           "flow_30m": tape.flow(cut - 1800, cut),
           "flow_2h": tape.flow(cut - 7200, cut),
           "mkt_flow_30m": tape.mkt_flow(cut - 1800, cut),
           "large_flow_2h": tape.large_flow(cut - 7200, cut)}
    out["flow_accel"] = out["flow_30m"] - out["flow_2h"]
    out["lead_flow_30m"] = (lead.flow(cut - 1800, cut)
                            if lead is not None and lead.covers(cut - 1800, cut)
                            else np.nan)
    return out


def auc(score, y) -> float:
    pos = y == 1
    n1, n0 = int(pos.sum()), int((~pos).sum())
    if n1 == 0 or n0 == 0:
        return float("nan")
    order = np.argsort(score, kind="mergesort")
    ranks = np.empty(len(score))
    s = score[order]
    i = 0
    while i < len(s):
        j = i
        while j + 1 < len(s) and s[j + 1] == s[i]:
            j += 1
        ranks[order[i:j + 1]] = (i + j) / 2.0 + 1.0
        i = j + 1
    return float((ranks[pos].sum() - n1 * (n1 + 1) / 2.0) / (n1 * n0))


def within_day_auc(x, y, day) -> tuple:
    per = []
    for d in np.unique(day):
        m = day == d
        a = auc(x[m], y[m])
        if a == a:
            per.append(a)
    return (float(np.mean(per)) if per else float("nan")), np.asarray(per)


def implied_delta(a: float) -> float:
    """Signed, rough: |AUC-0.5| mapped on the power curve, sign kept."""
    d = abs(a - 0.5) + 0.5
    xs, ys = zip(*POWER, strict=True)
    return float(np.sign(a - 0.5) * np.interp(d, xs, ys))


def load_rows(path: Path):
    drops = {"not_candidate_h432": 0, "time_out_resolution_only": 0,
             "unparseable": 0}
    rows, n = [], 0
    with open(path, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            n += 1
            if r.get("source") == "live" or r.get("label_era") != ERA:
                drops["not_candidate_h432"] += 1
                continue
            bar = r.get("barrier") or ""
            if bar == "tb_time":
                drops["time_out_resolution_only"] += 1
                continue
            try:
                st, side = float(r["signal_ts"]), float(r["direction"])
            except (KeyError, TypeError, ValueError):
                drops["unparseable"] += 1
                continue
            if bar not in ("tb_pt", "tb_sl") or side not in (1.0, -1.0):
                drops["unparseable"] += 1
                continue
            up = (bar == "tb_pt") == (side > 0)
            rows.append((r.get("asset") or "", st, 1 if up else 0))
    return rows, drops, n


def run(root: Path, null_reps: int = NULL_REPS) -> dict:
    out_dir = root / "outputs"
    rows, drops, n_read = load_rows(out_dir / "signal_history.csv")
    rng = np.random.default_rng(SEED)
    tapes: dict = {}
    for a in sorted({r[0] for r in rows}):
        p = PAIR.get(a)
        if p:
            try:
                tapes[a] = Tape(out_dir / "ticks" / "kraken" / p)
            except FileNotFoundError:
                pass
    feats = {k: [] for k in SIGNALS}
    ys, days, assets = [], [], []
    no_tape = 0
    for a, st, up in rows:
        tp = tapes.get(a)
        lead = tapes.get("ETH" if a == "BTC" else "BTC")
        s = signals_at(tp, lead, st + BAR_S) if tp is not None else None
        if s is None:
            no_tape += 1
            continue
        for k in SIGNALS:
            feats[k].append(s[k])
        ys.append(up)
        days.append(int(st // 86400))
        assets.append(a)
    y, day = np.asarray(ys), np.asarray(days)
    res = {"rows_scored": int(len(y)), "days": int(len(np.unique(day))),
           "base_up": float(y.mean()) if len(y) else float("nan"),
           "assets": {a: int(sum(1 for x in assets if x == a))
                      for a in sorted(set(assets))},
           "large_thr_usd": {a: round(t.large_thr, 2) for a, t in tapes.items()},
           "signals": {}}
    for k in SIGNALS:
        x = np.asarray(feats[k], float)
        ok = np.isfinite(x)
        xk, yk, dk = x[ok], y[ok], day[ok]
        wd, per = within_day_auc(xk, yk, dk)
        boots = []
        uniq = np.unique(dk)
        by_day = {d: np.where(dk == d)[0] for d in uniq}
        for _ in range(BOOT):
            pick = rng.choice(uniq, len(uniq))
            vals = [within_day_auc(xk[by_day[d]], yk[by_day[d]],
                                   np.zeros(len(by_day[d])))[0] for d in pick]
            vals = [v for v in vals if v == v]
            if vals:
                boots.append(float(np.mean(vals)))
        lo, hi = (np.percentile(boots, [2.5, 97.5]) if boots
                  else (float("nan"), float("nan")))
        null = []
        for _ in range(null_reps):
            xs = xk.copy()
            for ix in by_day.values():
                xs[ix] = rng.permutation(xs[ix])
            null.append(abs(within_day_auc(xs, yk, dk)[0] - 0.5))
        p = ((1 + sum(n >= abs(wd - 0.5) for n in null)) / (1 + len(null))
             if null else float("nan"))
        res["signals"][k] = {
            "n": int(ok.sum()), "within_day_auc": wd, "ci": (float(lo), float(hi)),
            "null_p": p, "pooled_auc": auc(xk, yk),
            "implied_delta": implied_delta(wd)}
    res["bonferroni"] = 0.05 / len(SIGNALS)
    res["p_floor"] = 1.0 / (null_reps + 1)
    res["counting"] = reconcile(n_read, {
        **drops, "no_tape_cover": no_tape, "scored": int(len(y))})
    return res


def render(r: dict) -> str:
    L = [f"info_screen - signed trade tape vs DIRECTION (resolved rows, "
         f"market-absolute up-first), era {ERA}",
         r["counting"]["line"],
         f"rows {r['rows_scored']} over {r['days']} days, base up-first "
         f"{r['base_up']:.3f}, assets {r['assets']}",
         f"Bonferroni {r['bonferroni']:.4f}; p floor {r['p_floor']:.4f}; "
         f"break-even delta ~1.2", "",
         "signal          n      within-day AUC [95% CI]       null_p   "
         "pooled AUC  implied delta"]
    for k, s in r["signals"].items():
        flag = " *" if s["null_p"] <= r["bonferroni"] else ""
        L.append(f"{k:14s} {s['n']:6d}   {s['within_day_auc']:.4f} "
                 f"[{s['ci'][0]:.4f}, {s['ci'][1]:.4f}]   {s['null_p']:.4f}{flag}"
                 f"   {s['pooled_auc']:.4f}     {s['implied_delta']:+.2f}")
    L.append("* = clears Bonferroni. implied delta is a ROUGH translation "
             "(basis-state power curve), not a measurement of this signal.")
    L.append("BIASED FOR PATH-DERIVED SCORES: rows in one day share one price "
             "path, so within-day AUC reads contrarian under a pure random "
             "walk and the permutation null is too narrow. Flow correlates "
             "with past returns; residualised on them it reads ~0.485 "
             "(CI spans 0.5). Grade against a sign-flip null - see the "
             "module docstring CORRECTION.")
    return "\n".join(L)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--root", type=Path, default=ROOT)
    ap.add_argument("--null-reps", type=int, default=NULL_REPS)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    t = time.time()
    r = run(a.root, a.null_reps)
    print(f"read {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(t))}")
    print(json.dumps(r, indent=1, default=float) if a.json else render(r))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
