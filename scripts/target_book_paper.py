"""scripts/target_book_paper.py - the target book run FORWARD on live Kraken
bars, as a paper instance (SAFE: shadow; places nothing; no OrderManager, no
credentials, no private endpoint).

    python scripts/target_book_paper.py --once        # supervisor: hourly
    python scripts/target_book_paper.py --once --csv-dir DIR   # offline

Operator direction 2026-10-02: "Set everything up to gain data for the bot's
purposes and configure it like it's not anything different than a real
instance yet we are running dry." The real instance's terms are used as-is:
the bot's paper capital (config capital_management.starting_capital_usd), the booked maker fee
(pretrade.maker_fee_bps), Kraken prices (the execution venue's PUBLIC OHLC),
the target_book config, 4h bars, maker limit at the decision close filled
only if the next bar trades THROUGH it.

REGISTERED 2026-10-02, before any forward bar existed. Changing anything
below after looking is a new registration and must say so.

  PAPER_FROM  2026-10-03T00:00Z. The first decision is the close of the
              first bar opening at or after it; bars before it are warm-up
              only (sigma, tilt, floor look-backs) and are never graded.
  Arms        buy_hold            equal-weight basket bought at PAPER_FROM
              target_book         the configured book (band + aim)
              target_book_vol40   the same + vol targeting at 40%/yr, the
                                  one lever with supported evidence
                                  (docs/quant/2026-10-02_feature_program.md)
              idea lab            the market-reactive population, never
                                  promoted (core/idea_lab.py)
  Read points n = 180 steps (30 days) the lean, n = 540 steps (90 days) the
              verdict, per arm against buy_hold, paired block bootstrap
              (scripts/target_book_validation.py). Readouts never decide.

STATE. Kraken's public endpoint returns the last 720 bars, so bars are kept
in an append-merge store (outputs/target_book/paper/ohlc_240m/<ASSET>.csv)
and every run REPLAYS DETERMINISTICALLY from PAPER_FROM over the stored
bars. There is no mutable book state to corrupt: a restart, a crash or a
skipped hour changes nothing, and a closed bar's result never moves
(pinned by tests/test_target_book_paper.py). A run that cannot reach
Kraken re-reports the stored bars and says so. Gaps (the box was off
longer than Kraken's 720-bar memory) are COUNTED and printed, never filled.

Unit: a STEP is one 4h bar decided at its close and settled on the next.
"""
from __future__ import annotations

import argparse
import calendar
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402

from core import view_blend as vb  # noqa: E402
from core.idea_lab import Bars, Idea, IdeaLab, ShadowBook, grade, step_book  # noqa: E402
from scripts.target_book_replay import (_mdd, align, fetch_kraken,  # noqa: E402
                                        load_csv, params_from, save_csv)

PAPER_FROM = "2026-10-03T00:00:00Z"
VOL_ARM_TARGET = 0.40
INTERVAL_MIN = 240
READ_POINTS = {"lean": 180, "verdict": 540}
# a distinct basename: session_export flattens paths, and "status.json" is
# the runner's own file, which may never leave the box
STATUS_NAME = "target_book_paper.json"

# ---- VIEW-BLEND ARMS (core/view_blend.py) - REGISTERED 2026-10-03, before
# BL_FROM. bl_gated: each view's confidence is earned from the forward
# evidence log, using at each bar ONLY evidence recorded before that bar's
# close (a later promotion never rewrites the past). bl_ungated_c25: every
# view at confidence 0.25 - a diagnostic of what the views WOULD do; its own
# read never promotes anything. bl_window_vol40: the vol-40 basket from the
# same start, the comparator (bl_gated must equal it while nothing is
# promoted). Views: P5 cross-sectional 7 d momentum (relative), L2 28 d
# time-series momentum (absolute, per asset). IC prior 0.02 is the low end
# of the institutional 0.02-0.05 range; evidence moves CONFIDENCE, never IC.
BL_FROM = "2026-10-04T00:00:00Z"
BL_IC_PRIOR = 0.02
BL_UNGATED_C = 0.25
COV_LOOKBACK = 180          # bars (30 d) for the covariance
XS_LOOKBACK = 42            # bars = 168 h, as registered for P5
TS_LOOKBACK = 168           # bars = 672 h, as registered for L2
VIEW_HYPOTHESES = {"xs_mom": "P5_xs_mom_168", "tsmom": "L2_tsmom_672"}
EVIDENCE_LOG = ROOT / "outputs" / "reports" / "forward" / "evidence_log.jsonl"


def bl_from_ts() -> int:
    return calendar.timegm(time.strptime(BL_FROM, "%Y-%m-%dT%H:%M:%SZ"))


def evidence_confidence(evidence: list):
    """confidence(view_key, t): the view's hypothesis status as last
    recorded at or before t, mapped by view_blend.confidence_from_status."""
    by_id: dict = {}
    for e in sorted(evidence or [], key=lambda x: x.get("ts", 0.0)):
        by_id.setdefault(e.get("id"), []).append(e)

    def conf(key: str, t: float) -> float:
        rows = [e for e in by_id.get(VIEW_HYPOTHESES.get(key), []) if e["ts"] <= t]
        if not rows:
            return 0.0
        last = rows[-1]
        return vb.confidence_from_status(last.get("status", ""),
                                         float(last.get("db_exist_forward") or 0.0))
    return conf


def make_reshape(conf):
    """Basket weights -> view-blended weights at bar i, from bars[: i + 1]."""
    def reshape(w: dict, bars: Bars, i: int) -> dict:
        assets = sorted(w)
        if i < max(COV_LOOKBACK, TS_LOOKBACK) or len(assets) < 2:
            return w
        px = np.array([[bars.close[a][k] for a in assets]
                       for k in range(i - COV_LOOKBACK, i + 1)])
        sigma = vb.shrunk_cov(np.diff(np.log(px), axis=0))
        sd = np.sqrt(np.diag(sigma))
        t_close = float(bars.t[i] + INTERVAL_MIN * 60)
        views = []
        r = np.array([bars.close[a][i] / bars.close[a][i - XS_LOOKBACK] - 1.0
                      for a in assets])
        if r.std(ddof=1) > 0:
            z = (r - r.mean()) / r.std(ddof=1)
            p = z / (np.abs(z).sum() / 2.0)            # long leg sums to 1
            sig_p = float(np.sqrt(p @ sigma @ p))
            views.append(vb.View("xs_mom", dict(zip(assets, p, strict=True)),
                                 vb.grinold_q(BL_IC_PRIOR, sig_p, 1.0),
                                 conf("xs_mom", t_close), VIEW_HYPOTHESES["xs_mom"]))
        for k, a in enumerate(assets):
            s = float(np.sign(bars.close[a][i] / bars.close[a][i - TS_LOOKBACK] - 1.0))
            if s:
                views.append(vb.View(f"tsmom_{a}", {a: 1.0},
                                     vb.grinold_q(BL_IC_PRIOR, float(sd[k]), s),
                                     conf("tsmom", t_close), VIEW_HYPOTHESES["tsmom"]))
        return vb.blend(assets, w, sigma, views, invest_frac=sum(w.values()))
    return reshape


def paper_from_ts() -> int:
    return calendar.timegm(time.strptime(PAPER_FROM, "%Y-%m-%dT%H:%M:%SZ"))


def default_dir() -> Path:
    return ROOT / "outputs" / "target_book" / "paper"


def merge_store(store: Path, asset: str, fresh: list) -> list:
    """Union of stored and fresh bars by open time. A CLOSED bar keeps its
    stored value: Kraken does not revise closed bars, and keeping the first
    copy is what makes past steps immutable."""
    f = store / f"{asset}.csv"
    old = load_csv(f) if f.exists() else []
    have = {r[0] for r in old}
    rows = sorted(old + [r for r in fresh if r[0] not in have])
    save_csv(f, rows)
    return rows


def count_gaps(t: list, step_s: int) -> int:
    return sum(max(0, (b - a) // step_s - 1) for a, b in zip(t[:-1], t[1:], strict=True))


def run(bars: Bars, cfg: dict, evidence: list | None = None) -> dict:
    """Replay every arm from PAPER_FROM over `bars`. Pure: same bars, same
    result. Returns the status document."""
    base, lim, lab_cfg = params_from(cfg)
    lab_cfg["bar_interval_min"] = INTERVAL_MIN
    cash = float(cfg["capital_management"]["starting_capital_usd"])
    start = paper_from_ts()
    # decision index: the first bar opening at/after PAPER_FROM
    i0 = next((k for k, t in enumerate(bars.t) if t >= start), len(bars))
    steps = max(0, len(bars) - 1 - i0)
    doc = {"registered": {"paper_from": PAPER_FROM, "interval_min": INTERVAL_MIN,
                          "cash_usd": cash, "maker_fee_bps": base.maker_fee_bps,
                          "assets": sorted(bars.close), "vol_arm_target": VOL_ARM_TARGET,
                          "read_points_steps": READ_POINTS},
           "unit": "step = one 4h bar decided at its close, settled on the next",
           "steps": steps, "warmup_bars": i0,
           "gap_bars": count_gaps(bars.t, INTERVAL_MIN * 60),
           "first_decision_open_utc": _iso(bars.t[i0]) if i0 < len(bars) else None,
           "last_settled_open_utc": _iso(bars.t[-1]) if steps else None,
           "arms": {}, "curve": []}
    if steps == 0:
        doc["note"] = "waiting for the first bar after PAPER_FROM to close"
        return doc
    vol_base = type(base)(**{**base.__dict__, "vol_target_ann": VOL_ARM_TARGET})
    arms = {"target_book": (Idea(base.gamma, base.aim_rate, base.weighting, "none"), base),
            "target_book_vol40": (Idea(base.gamma, base.aim_rate, base.weighting, "none"),
                                  vol_base)}
    curves: dict = {}
    for name, (idea, params) in arms.items():
        b = ShadowBook(idea, i0, cash, {}, cash)
        eq = [cash]
        for i in range(i0, len(bars) - 1):
            step_book(b, bars, i, params, lab_cfg, lim)
            eq.append(b.equity({a: c[i + 1] for a, c in bars.close.items()}))
        g = grade(b, 1)
        g.update(equity_usd=eq[-1], max_drawdown=_mdd(eq), units=dict(b.units),
                 cash_usd=b.cash)
        doc["arms"][name] = g
        curves[name] = eq
    # view-blend arms: their own registered start, padded before it
    ib = next((k for k, t in enumerate(bars.t) if t >= bl_from_ts()), len(bars))
    bl_arms = {"bl_window_vol40": None,
               "bl_gated": make_reshape(evidence_confidence(evidence or [])),
               "bl_ungated_c25": make_reshape(lambda key, t: BL_UNGATED_C)}
    for name, reshape in bl_arms.items():
        idea = Idea(base.gamma, base.aim_rate, base.weighting, "none")
        b = ShadowBook(idea, ib, cash, {}, cash)
        eq = [None] * max(0, ib - i0) + [cash]
        for i in range(ib, len(bars) - 1):
            step_book(b, bars, i, vol_base, lab_cfg, lim, reshape)
            eq.append(b.equity({a: c[i + 1] for a, c in bars.close.items()}))
        live = [x for x in eq if x is not None]
        g = grade(b, 1)
        g.update(equity_usd=live[-1], max_drawdown=_mdd(live), units=dict(b.units),
                 cash_usd=b.cash, start_utc=BL_FROM)
        doc["arms"][name] = g
        curves[name] = eq
    # buy_hold: the same purchase the book's benchmark twin makes, with fee
    fee = base.maker_fee_bps / 1e4
    per = cash * base.invest_frac / len(bars.close)
    u = {a: per / c[i0] / (1 + fee) for a, c in bars.close.items()}
    rest = cash - per * len(u)
    bh = [rest + sum(q * bars.close[a][i] for a, q in u.items())
          for i in range(i0, len(bars))]
    doc["arms"]["buy_hold"] = {"equity_usd": bh[-1], "cum_return": bh[-1] / cash - 1.0,
                               "max_drawdown": _mdd(bh), "fees_usd": per * len(u) * fee / (1 + fee)}
    curves["buy_hold"] = bh
    lab = IdeaLab(lab_cfg, base, lim, cash)
    for i in range(i0, len(bars) - 1):
        lab.step(bars, i)
    try:
        from ml.overfit import deflated_sharpe as dsr_fn
    except Exception:  # noqa: BLE001 - report without DSR rather than die
        dsr_fn = None
    rep = lab.report(dsr_fn)
    doc["lab"] = {k: rep[k] for k in ("family_size", "n_trials", "alive", "retired")}
    doc["lab"]["reconcile"] = (f"born {rep['n_trials']} = alive {rep['alive']} + "
                               f"retired {rep['retired']} "
                               f"[{'OK' if rep['n_trials'] == rep['alive'] + rep['retired'] else 'MISMATCH'}]")
    doc["lab"]["ideas"] = rep["ideas"]
    doc["read_point"] = next((k for k, n in sorted(READ_POINTS.items(), key=lambda kv: -kv[1])
                              if steps >= n), None)
    doc["curve"] = [{"open_utc": _iso(bars.t[i0 + k]),
                     **{n: (None if c[k] is None else round(c[k], 4))
                        for n, c in curves.items()}}
                    for k in range(steps + 1)]
    return doc


def _iso(t: int) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--once", action="store_true", help="one fetch+replay (the only mode)")
    ap.add_argument("--config", default=str(ROOT / "config.json"))
    ap.add_argument("--csv-dir", default=None, help="offline bars: DIR/<ASSET>.csv")
    ap.add_argument("--out", default=None)
    ap.add_argument("--evidence", default=None, help="forward evidence log (jsonl)")
    args = ap.parse_args(argv)
    cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))
    out = Path(args.out) if args.out else default_dir()
    store = out / f"ohlc_{INTERVAL_MIN}m"
    store.mkdir(parents=True, exist_ok=True)
    series, fetch_errors = {}, []
    for a in cfg["target_book"]["assets"]:
        try:
            fresh = (load_csv(Path(args.csv_dir) / f"{a}.csv") if args.csv_dir
                     else fetch_kraken(a, INTERVAL_MIN))
        except Exception as e:  # noqa: BLE001 - keep the stored bars, say so
            fresh = []
            fetch_errors.append(f"{a}: {type(e).__name__}: {e}")
        series[a] = merge_store(store, a, fresh)
        if not args.csv_dir:
            time.sleep(1.1)                       # public-endpoint courtesy
    if any(not v for v in series.values()):
        print(f"target_book_paper: no stored bars for some assets; errors {fetch_errors}")
        return 1
    evidence = []
    ev_path = Path(args.evidence) if args.evidence else EVIDENCE_LOG
    if ev_path.exists():
        for line in ev_path.read_text(encoding="utf-8").splitlines():
            try:
                evidence.append(json.loads(line))
            except ValueError:
                continue                    # a torn line is skipped, never fatal
    doc = run(align(series), cfg, evidence)
    doc["written_at_utc"] = _iso(int(time.time()))
    doc["fetch_errors"] = fetch_errors
    (out / STATUS_NAME).write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    line = {k: doc[k] for k in ("written_at_utc", "steps", "gap_bars", "fetch_errors")}
    line["equity"] = {k: round(v["equity_usd"], 2) for k, v in doc["arms"].items()}
    with (out / "runs.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(line) + "\n")
    print(f"target_book_paper: {doc['steps']} steps since {PAPER_FROM}, "
          f"gaps {doc['gap_bars']}, equity {line['equity']}"
          + (f", fetch errors {fetch_errors}" if fetch_errors else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
