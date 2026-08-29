"""
scripts/hedge_sim.py — HEDGE-SIM harness (SAFE class, measurement only).

Pre-registered in docs/quant/2026-08-28_hedge_sim_registration.md
(commit 67bdcdac). Reads outputs/fills.csv, outputs/audit.jsonl
(streamed), outputs/equity.csv (windowed). Writes ONLY a markdown
report to the caller-named docs/ path plus stdout. Never writes under
outputs/.

The registration is the law: the window, grid, fee model, effective-n
treatment and verdict rule below are transcribed from it, not tuned
here. The verdict rule maps outcomes to HEDGE_COSTS_MORE / HEDGE_PAYS /
UNDECIDABLE-AT-N; it names which decision became decidable — it never
decides.
"""

from __future__ import annotations

import argparse
import csv
import datetime as _dt
import json
import re
from dataclasses import dataclass
from pathlib import Path

# ---- registered constants (docs/quant/2026-08-28_hedge_sim_registration.md)
WINDOW_LO = 1786064980.459          # 2026-08-07T01:09:40.459Z inclusive
WINDOW_HI = 1786102531.553          # 2026-08-07T11:35:31.553Z inclusive
EQ_WINDOW_LO = 1786060800           # 2026-08-07T00:00:00Z inclusive
EQ_WINDOW_HI = 1786147200           # 2026-08-08T00:00:00Z inclusive
K_GRID = (0.0, 0.5, 1.0, 1.5, 2.0)
TRUTH_TAKER = 0.0080                # era-8 Kraken Tier-1 taker, 80 bps
TRUTH_MAKER = 0.0040                # era-8 maker, 40 bps
EPISODE_GAP_S = 1800.0
BOOTSTRAP_MIN_EPISODES = 5
REGISTRATION_SHA = "67bdcdac"
EXPECTED_TRIPS = 159


class PairingError(RuntimeError):
    """Round-trip pairing violated the registered 1:1/equal-size contract."""


@dataclass
class RoundTrip:
    position_id: str
    open_ts: float
    close_ts: float
    size: float
    open_px: float
    close_px: float
    open_side: str            # "sell" => short hedge
    open_fee: float           # booked, USD
    close_fee: float          # booked, USD
    open_post_only: bool
    close_post_only: bool

    @property
    def gross(self) -> float:
        d = 1.0 if self.open_side == "buy" else -1.0
        return d * (self.close_px - self.open_px) * self.size

    def fees(self, model: str) -> float:
        if model == "booked":
            return self.open_fee + self.close_fee
        if model == "era8_truth":
            def leg(px: float, post_only: bool) -> float:
                rate = TRUTH_MAKER if post_only else TRUTH_TAKER
                return px * self.size * rate
            return (leg(self.open_px, self.open_post_only)
                    + leg(self.close_px, self.close_post_only))
        raise ValueError(f"unknown fee model {model!r}")

    def net(self, model: str) -> float:
        return self.gross - self.fees(model)


def _f(row: dict, key: str) -> float:
    return float(row[key])


def load_round_trips(fills_path: Path,
                     lo: float = WINDOW_LO,
                     hi: float = WINDOW_HI) -> list[RoundTrip]:
    """Registered selectors: open = purpose=='hedge'; unwind =
    purpose=='exit' AND reason startswith 'hedge unwind'; ts in
    [lo, hi] inclusive; paired 1:1 on position_id with equal sizes.
    FAILS (PairingError) rather than degrading."""
    opens: dict[str, dict] = {}
    closes: dict[str, dict] = {}
    with fills_path.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            ts = _f(row, "ts")
            if not (lo <= ts <= hi):
                continue
            pid = row["position_id"]
            if row["purpose"] == "hedge":
                if pid in opens:
                    raise PairingError(f"duplicate hedge open for {pid}")
                opens[pid] = row
            elif (row["purpose"] == "exit"
                    and row["reason"].startswith("hedge unwind")):
                if pid in closes:
                    raise PairingError(f"duplicate hedge unwind for {pid}")
                closes[pid] = row
    if set(opens) != set(closes):
        raise PairingError(
            f"unpaired round-trips: {len(opens)} opens vs {len(closes)} "
            f"unwinds; diff={sorted(set(opens) ^ set(closes))[:5]}")
    trips = []
    for pid, o in sorted(opens.items(), key=lambda kv: _f(kv[1], "ts")):
        c = closes[pid]
        so, sc = _f(o, "fill_size"), _f(c, "fill_size")
        if abs(so - sc) > 1e-6 * max(so, sc, 1.0):
            raise PairingError(f"leg sizes differ for {pid}: {so} vs {sc}")
        trips.append(RoundTrip(
            position_id=pid, open_ts=_f(o, "ts"), close_ts=_f(c, "ts"),
            size=so, open_px=_f(o, "fill_price"), close_px=_f(c, "fill_price"),
            open_side=o["side"], open_fee=_f(o, "fees_delta_usd"),
            close_fee=_f(c, "fees_delta_usd"),
            open_post_only=o["post_only"] not in ("0", "", "0.0", "False"),
            close_post_only=c["post_only"] not in ("0", "", "0.0", "False")))
    return trips


def load_round_trips_supplement(fills_path: Path,
                                lo: float = WINDOW_LO,
                                hi: float = WINDOW_HI) -> list[RoundTrip]:
    """POST-HOC SUPPLEMENT selector (NOT the registered one; used only
    when the strict loader fails, and labeled as such in the report).
    Deviation, documented: a hedge position's close may be SPLIT across
    several exit legs with different reasons (measured 2026-08-28: 1 of
    159 trips closed 2766.3 via 'hard cap breach' + 3471.3 via 'hedge
    unwind'). Here the close = ALL exit legs of any position opened by a
    hedge fill, aggregated (size-weighted close price keeps gross
    exact); total sizes must still balance or PairingError."""
    opens: dict[str, dict] = {}
    exits: dict[str, list[dict]] = {}
    with fills_path.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            ts = _f(row, "ts")
            if not (lo <= ts <= hi):
                continue
            pid = row["position_id"]
            if row["purpose"] == "hedge":
                if pid in opens:
                    raise PairingError(f"duplicate hedge open for {pid}")
                opens[pid] = row
            elif row["purpose"] == "exit":
                exits.setdefault(pid, []).append(row)
    trips = []
    for pid, o in sorted(opens.items(), key=lambda kv: _f(kv[1], "ts")):
        legs = exits.get(pid)
        if not legs:
            raise PairingError(f"no exit legs for hedge {pid}")
        tot = sum(_f(x, "fill_size") for x in legs)
        so = _f(o, "fill_size")
        if abs(so - tot) > 1e-6 * max(so, tot, 1.0):
            raise PairingError(
                f"exit legs do not balance open for {pid}: {so} vs {tot}")
        vwap = sum(_f(x, "fill_size") * _f(x, "fill_price")
                   for x in legs) / tot
        trips.append(RoundTrip(
            position_id=pid, open_ts=_f(o, "ts"),
            close_ts=max(_f(x, "ts") for x in legs), size=so,
            open_px=_f(o, "fill_price"), close_px=vwap,
            open_side=o["side"], open_fee=_f(o, "fees_delta_usd"),
            close_fee=sum(_f(x, "fees_delta_usd") for x in legs),
            open_post_only=o["post_only"] not in ("0", "", "0.0", "False"),
            close_post_only=all(x["post_only"] not in ("0", "", "0.0",
                                                       "False")
                                for x in legs)))
    return trips


def booked_rate_stats(trips: list[RoundTrip]) -> dict:
    """Verify (not assume) the booked per-leg fee rate."""
    rates = []
    for t in trips:
        rates.append(t.open_fee / (t.size * t.open_px))
        rates.append(t.close_fee / (t.size * t.close_px))
    rates.sort()
    n = len(rates)
    return {"n_legs": n, "min": rates[0], "median": rates[n // 2],
            "max": rates[-1]}


def audit_pt061_nets(audit_path: Path) -> dict[str, float]:
    """Second route: PT-061 hedge-unwind closes, streamed."""
    out: dict[str, float] = {}
    with audit_path.open(encoding="utf-8") as f:
        for ln in f:
            if '"PT-061"' not in ln:
                continue
            d = json.loads(ln)
            data = d.get("data") or {}
            if str(data.get("close_reason", "")).startswith("hedge unwind"):
                out[str(data.get("position_id"))] = float(data["net_usd"])
    return out


_FW040_RE = re.compile(r"px=([0-9.eE+-]+) sz=([0-9.eE+-]+)")


def blocked_opens(audit_path: Path) -> dict:
    """Descriptive only (registered NOT verdict-bearing): FW-040 rejects
    of hedge orders; notional from px*sz in the msg."""
    n = 0
    notional = 0.0
    with audit_path.open(encoding="utf-8") as f:
        for ln in f:
            if '"FW-040"' not in ln or "hedge" not in ln:
                continue
            d = json.loads(ln)
            msg = d.get("msg", "")
            if "hedge" not in msg:
                continue
            m = _FW040_RE.search(msg)
            if not m:
                continue
            n += 1
            notional += float(m.group(1)) * float(m.group(2))
    return {"count": n, "notional_usd": notional,
            "truth_fee_cost_usd": notional * 2 * TRUTH_TAKER}


def last_hedge_open_ts(audit_path: Path) -> float:
    """Full-range scan (onset/last claims never from a tail sample)."""
    last = 0.0
    with audit_path.open(encoding="utf-8") as f:
        for ln in f:
            if '"purpose": "hedge"' not in ln:
                continue
            d = json.loads(ln)
            if (d.get("data") or {}).get("purpose") == "hedge":
                last = max(last, float(d["ts"]))
    return last


def episodes(trips: list[RoundTrip],
             gap_s: float = EPISODE_GAP_S) -> list[list[RoundTrip]]:
    eps: list[list[RoundTrip]] = []
    for t in sorted(trips, key=lambda t: t.open_ts):
        if eps and t.open_ts - eps[-1][-1].open_ts <= gap_s:
            eps[-1].append(t)
        else:
            eps.append([t])
    return eps


def grid(trips: list[RoundTrip]) -> dict:
    g = sum(t.gross for t in trips)
    cells = {}
    for model in ("booked", "era8_truth"):
        f_m = sum(t.fees(model) for t in trips)
        for k in K_GRID:
            cells[(k, model)] = {"net": k * (g - f_m), "fee_drag": k * f_m}
    base = cells[(1.0, "booked")]["net"]
    for c in cells.values():
        c["delta_vs_deployed"] = c["net"] - base
    return {"gross": g, "cells": cells}


def verdict(trips: list[RoundTrip]) -> dict:
    """Registered rule, verbatim: on N = net(1, era8_truth) and
    per-episode truth nets. <5 episodes -> all-sign rule, no bootstrap
    pretended."""
    n_total = sum(t.net("era8_truth") for t in trips)
    eps = episodes(trips)
    e_nets = [sum(t.net("era8_truth") for t in ep) for ep in eps]
    n_ep = len(eps)
    if n_ep >= BOOTSTRAP_MIN_EPISODES:
        import random
        rng = random.Random(20260828)
        sums = sorted(
            sum(e_nets[rng.randrange(n_ep)] for _ in range(n_ep))
            for _ in range(10_000))
        lo, hi = sums[249], sums[9749]
        if n_total < 0 and hi < 0:
            v = "HEDGE_COSTS_MORE"
        elif n_total > 0 and lo > 0:
            v = "HEDGE_PAYS"
        else:
            v = "UNDECIDABLE-AT-N"
        ci = (lo, hi)
    else:
        ci = None
        if n_total < 0 and all(e <= 0 for e in e_nets):
            v = "HEDGE_COSTS_MORE"
        elif n_total > 0 and all(e >= 0 for e in e_nets):
            v = "HEDGE_PAYS"
        else:
            v = "UNDECIDABLE-AT-N"
    return {"verdict": v, "net_truth": n_total, "n_nominal": len(trips),
            "n_episodes": n_ep, "episode_nets": e_nets, "ci95": ci}


def crosscheck(trips: list[RoundTrip], pt061: dict[str, float]) -> dict:
    """Double-derive: fills-leg booked net vs audit PT-061 net_usd."""
    missing = [t.position_id for t in trips if t.position_id not in pt061]
    per_trip_max = 0.0
    agg_fills = 0.0
    agg_audit = 0.0
    for t in trips:
        if t.position_id in pt061:
            agg_fills += t.net("booked")
            agg_audit += pt061[t.position_id]
            per_trip_max = max(per_trip_max,
                               abs(t.net("booked") - pt061[t.position_id]))
    return {"missing_in_audit": missing, "agg_fills": agg_fills,
            "agg_audit": agg_audit, "per_trip_max_abs_diff": per_trip_max,
            "ok": (not missing and per_trip_max <= 0.01
                   and abs(agg_fills - agg_audit) <= 1.0)}


def equity_window(equity_path: Path,
                  lo: float = EQ_WINDOW_LO,
                  hi: float = EQ_WINDOW_HI) -> list[tuple[float, float]]:
    pts = []
    first = last = None
    with equity_path.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            ts, eq = float(row["ts"]), float(row["equity"])
            if first is None:
                first = (ts, eq)
            last = (ts, eq)
            if lo <= ts <= hi:
                pts.append((ts, eq))
    pts.sort()
    equity_window.first_last = (first, last)  # type: ignore[attr-defined]
    return pts


def max_drawdown(path: list[float]) -> float:
    peak = float("-inf")
    dd = 0.0
    for v in path:
        peak = max(peak, v)
        dd = max(dd, peak - v)
    return dd


def drawdown_deltas(eq_pts: list[tuple[float, float]],
                    trips: list[RoundTrip]) -> dict:
    """eq_kM(t) = eq(t) - CumNet_booked(t) + k*CumNet_M(t), cum stepping
    at unwind timestamps. Registered metric 5."""
    steps = [(t.close_ts, t)
             for t in sorted(trips, key=lambda t: t.close_ts)]
    actual_dd = max_drawdown([e for _, e in eq_pts])
    out = {"actual_max_dd": actual_dd, "cells": {}}
    for model in ("booked", "era8_truth"):
        for k in K_GRID:
            path = []
            i = 0
            cum_b = cum_m = 0.0
            for ts, eq in eq_pts:
                while i < len(steps) and steps[i][0] <= ts:
                    cum_b += steps[i][1].net("booked")
                    cum_m += steps[i][1].net(model)
                    i += 1
                path.append(eq - cum_b + k * cum_m)
            out["cells"][(k, model)] = max_drawdown(path) - actual_dd
    return out


def _iso(ts: float) -> str:
    return _dt.datetime.fromtimestamp(
        ts, _dt.timezone.utc).isoformat().replace("+00:00", "Z")


def run(fills: Path, audit: Path, equity: Path, out: Path | None,
        registration_sha: str = REGISTRATION_SHA) -> str:
    read_stamp = _dt.datetime.now(_dt.timezone.utc).isoformat()
    strict_failure: str | None = None
    try:
        trips = load_round_trips(fills)
    except PairingError as e:
        strict_failure = str(e)
        trips = load_round_trips_supplement(fills)
    rates = booked_rate_stats(trips)
    g = grid(trips)
    v = verdict(trips)
    pt061 = audit_pt061_nets(audit)
    xc = crosscheck(trips, pt061)
    blocked = blocked_opens(audit)
    last_open = last_hedge_open_ts(audit)
    eq_pts = equity_window(equity)
    dd = drawdown_deltas(eq_pts, trips) if eq_pts else None
    first_last = getattr(equity_window, "first_last", (None, None))

    if not xc["ok"]:
        v = dict(v, verdict="UNDECIDABLE-AT-N",
                 note="cross-check failed (registered harness-failure arm)")

    L: list[str] = []
    a = L.append
    a("# HEDGE-SIM results — 2026-08-28")
    a("")
    a(f"Registration: docs/quant/2026-08-28_hedge_sim_registration.md "
      f"(commit {registration_sha}). Computed after the registration was "
      f"committed; nothing in it was amended.")
    a(f"Snapshot stamp (live files read at): {read_stamp}")
    a(f"Sources: fills={fills} audit={audit} equity={equity}")
    a("")
    if strict_failure:
        a("## REGISTERED VERDICT: **UNDECIDABLE-AT-N** (harness-failure arm)")
        a("")
        a(f"The registered strict selector FAILED as registered it must: "
          f"`{strict_failure}`. The registration's assumption that every "
          "unwind is a single exit leg with reason 'hedge unwind' was "
          "contradicted by the data (split close). The registration is NOT "
          "amended. Everything below is the POST-HOC SUPPLEMENT (documented "
          "deviation: close = ALL exit legs of hedge-opened positions, "
          "aggregated), applying the otherwise-identical registered "
          "computation.")
        a("")
        a(f"## SUPPLEMENTARY verdict (post-hoc selector): **{v['verdict']}**")
    else:
        a(f"## VERDICT (registered rule): **{v['verdict']}**")
    a("")
    a(f"- net_pnl(k=1, era8_truth) = {v['net_truth']:+.2f} USD  "
      f"[K: fills legs, truth fees]")
    a(f"- n_nominal = {v['n_nominal']} round-trips; n_episodes = "
      f"{v['n_episodes']} (gap > {EPISODE_GAP_S:.0f}s); per-episode truth "
      f"nets = {[round(e, 2) for e in v['episode_nets']]}")
    a(f"- 95% CI: {v['ci95'] if v['ci95'] else 'not computed (n_episodes < 5; registered all-sign rule used)'}")
    if "note" in v:
        a(f"- NOTE: {v['note']}")
    a("")
    a("Scope (registered, binding): this verdict covers ONLY the recorded "
      f"trigger window {_iso(WINDOW_LO)}–{_iso(WINDOW_HI)} inclusive and "
      "sizing aggression on triggers that actually fired. The post-"
      f"{_iso(last_open)} suppression period is UNRECONSTRUCTABLE-FROM-"
      "HISTORY (no persisted exposure/correlation paths).")
    a("")
    a("## Grid (net USD | delta vs deployed | fee drag)")
    a("")
    a("| k | fee model | net_pnl | delta_vs_deployed | fee_drag | max_dd_delta |")
    a("|---|-----------|---------|-------------------|----------|--------------|")
    for model in ("booked", "era8_truth"):
        for k in K_GRID:
            c = g["cells"][(k, model)]
            ddv = (f"{dd['cells'][(k, model)]:+.2f}" if dd else "n/a")
            a(f"| {k} | {model} | {c['net']:+.2f} | "
              f"{c['delta_vs_deployed']:+.2f} | {c['fee_drag']:.2f} | {ddv} |")
    a("")
    a(f"Gross (price legs only): {g['gross']:+.2f} USD. All metrics linear "
      "in k as registered; the grid is presentational.")
    a("")
    a("## Verification blocks")
    a("")
    a(f"- Booked per-leg fee rate ({rates['n_legs']} legs): min "
      f"{rates['min']*1e4:.2f} / median {rates['median']*1e4:.2f} / max "
      f"{rates['max']*1e4:.2f} bps  [K]")
    a(f"- Double-derive (fills booked net vs audit PT-061 net_usd): "
      f"fills {xc['agg_fills']:+.2f} vs audit {xc['agg_audit']:+.2f}; "
      f"per-trip max |diff| {xc['per_trip_max_abs_diff']:.4f}; missing in "
      f"audit: {len(xc['missing_in_audit'])}; ok={xc['ok']}")
    a(f"- Last hedge open fill in audit (FULL-range scan, needle "
      f"'\"purpose\": \"hedge\"'): {_iso(last_open)}  [K]")
    a("")
    a("## Blocked opens (descriptive, NOT verdict-bearing)")
    a("")
    a(f"- FW-040 hedge rejects: {blocked['count']}; total blocked notional "
      f"{blocked['notional_usd']:.2f} USD; fee-only round-trip cost at "
      f"era-8 truth {blocked['truth_fee_cost_usd']:.2f} USD. No PnL "
      "imputed (no unwind timing exists).")
    a("")
    a("## Equity context (descriptive, NOT verdict-bearing)")
    if first_last[0] and first_last[1]:
        (fts, feq), (lts, leq) = first_last
        a("")
        a(f"- equity.csv full span: {_iso(fts)} = {feq:.2f} → {_iso(lts)} = "
          f"{leq:.2f} (as-of {read_stamp}; capital sweeps/re-anchors, e.g. "
          "RP-042 2026-08-08, change the basis — span is NOT a PnL claim).")
        if dd:
            a(f"- Actual max drawdown in registered equity window "
              f"{_iso(EQ_WINDOW_LO)}–{_iso(EQ_WINDOW_HI)}: "
              f"{dd['actual_max_dd']:.2f} USD.")
    report = "\n".join(L) + "\n"
    if out is not None:
        out.write_text(report, encoding="utf-8")
    return report


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    root = Path(__file__).resolve().parent.parent
    ap.add_argument("--fills", type=Path, default=root / "outputs/fills.csv")
    ap.add_argument("--audit", type=Path, default=root / "outputs/audit.jsonl")
    ap.add_argument("--equity", type=Path, default=root / "outputs/equity.csv")
    ap.add_argument("--out", type=Path, default=None,
                    help="markdown report path under docs/ (default: stdout only)")
    ap.add_argument("--registration-sha", default=REGISTRATION_SHA)
    args = ap.parse_args()
    if args.out is not None and "outputs" in args.out.parts:
        raise SystemExit("refusing to write under outputs/ (SAFE contract)")
    print(run(args.fills, args.audit, args.equity, args.out,
              args.registration_sha))


if __name__ == "__main__":
    main()
