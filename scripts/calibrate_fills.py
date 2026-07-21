"""scripts/calibrate_fills.py — calibrate the dry-run passive-fill model.

Feeds core.fill_calibration with REAL numbers and writes a report. Two inputs:

  * the per-fill ledger (outputs/fills.csv) — the sim's OWN maker/taker mix and
    realized slippage. Context only: calibrating the sim against its own fills
    would be circular, so this is reported, not inverted.
  * recorded book frames (outputs/recordings/) — the non-circular calibration
    TARGET: how often the MARKET actually crossed a hypothetical resting limit
    within its life, as a function of distance-from-mid. This drives the
    Wilson-interval inversion in core.fill_calibration.

Analysis-only: it writes outputs/fill_calibration.{md,json} and prints a
recommendation, and NEVER edits config. Dormant-safe: with no recordings it
reports the ledger context and defers the recommendation; exit is always 0
(this is a report, not a gate).

    python scripts/calibrate_fills.py
"""

import argparse
import csv
import json
import logging
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.codes import Code  # noqa: E402
from core.fill_calibration import (  # noqa: E402
    D_MAX_DEFAULT,
    buckets_agree,
    calibrate,
)
from core.replay_gate import discover_recordings  # noqa: E402
from main import load_config  # noqa: E402

log = logging.getLogger("calibrate_fills")

# distance-from-mid grid (bps) at which trade-through is measured; d_bar =
# dist / sigma_bps decides which land in the near-touch (identifiable) band
DEFAULT_DIST_GRID_BPS = [5.0, 10.0, 15.0, 20.0, 30.0, 45.0, 60.0]


def _f(x, default=0.0) -> float:
    try:
        v = float(x)
        return v if np.isfinite(v) else default
    except (TypeError, ValueError):
        return default


# --------------------------------------------------------- ledger (context)
def ledger_maker_fill_summary(rows: list) -> dict:
    """Observed maker/taker mix + slippage percentiles from the fill ledger."""
    maker, taker, slips, fees = 0, 0, [], []
    for r in rows:
        post_only = str(r.get("post_only", "")).strip() == "1"
        ordertype = str(r.get("ordertype", "")).strip().lower()
        is_maker = post_only and ordertype == "limit"
        if is_maker:
            maker += 1
            s = str(r.get("slip_bps", "")).strip()
            if s != "":
                slips.append(_f(s))
        else:
            taker += 1
        fees.append(_f(r.get("fees_delta_usd", 0.0)))
    slip_p50 = float(np.percentile(slips, 50)) if slips else None
    slip_p95 = float(np.percentile(slips, 95)) if slips else None
    return {"maker_fills": maker, "taker_fills": taker,
            "slip_p50_bps": slip_p50, "slip_p95_bps": slip_p95,
            "mean_fee_usd": float(np.mean(fees)) if fees else None,
            "n_rows": len(rows)}


# ------------------------------------------------ trade-through (the target)
def trade_through_counts(frames: list, life_polls: int, dist_bps_grid: list,
                         sigma_bps: float) -> list:
    """Per distance, count resting limits the market crossed within their life.

    A buy limit ``dist`` bps below mid is crossed if any future ask trades
    to/through it, a sell limit ``dist`` bps above if any future bid does.
    Placements are STRIDED by ``life`` so their look-ahead windows do not
    overlap: adjacent overlapping windows are heavily autocorrelated, which
    would inflate the Wilson trial count and over-power the recommendation.
    Returns one record per distance: {dist_bps, d_bar, k (crossed), n}.
    """
    sig = max(float(sigma_bps), 1.0)
    life = max(int(life_polls), 1)
    out = []
    # pre-extract clean mids/bids/asks once
    clean = []
    for fr in frames:
        bid, ask = _f(fr.get("bid")), _f(fr.get("ask"))
        if bid > 0 and ask > 0 and ask >= bid:
            clean.append((0.5 * (bid + ask), bid, ask))
        else:
            clean.append(None)
    for dist in dist_bps_grid:
        k = n = 0
        for i in range(0, len(clean) - 1, life):   # stride: non-overlapping windows
            here = clean[i]
            if here is None:
                continue
            mid = here[0]
            window = [c for c in clean[i + 1: i + 1 + life] if c is not None]
            if not window:
                continue
            l_buy = mid * (1.0 - dist / 1e4)
            l_sell = mid * (1.0 + dist / 1e4)
            min_ask = min(c[2] for c in window)
            max_bid = max(c[1] for c in window)
            n += 2                                  # a buy and a sell placement
            if min_ask <= l_buy:
                k += 1
            if max_bid >= l_sell:
                k += 1
        out.append({"dist_bps": float(dist), "d_bar": float(dist) / sig,
                    "k": k, "n": n})
    return out


def estimate_sigma_bps(frames: list) -> float:
    """Per-frame realized vol (bps) from mid log-returns; floored at 1."""
    mids = []
    for fr in frames:
        bid, ask = _f(fr.get("bid")), _f(fr.get("ask"))
        if bid > 0 and ask > 0:
            mids.append(0.5 * (bid + ask))
    if len(mids) < 3:
        return 30.0
    arr = np.asarray(mids, dtype=float)
    rets = np.diff(np.log(arr))
    rets = rets[np.isfinite(rets)]
    if rets.size < 2:
        return 30.0
    return max(float(np.std(rets)) * 1e4, 1.0)


def extract_frames(recording_path, venue: str = "kraken") -> dict:
    """{symbol: [ {ts,bid,ask} ...]} from a session's get_order_book frames,
    reading ALL rotation parts (base + .partNN) in stream order."""
    from data.recording import session_part_files
    by_symbol: dict = {}
    for fpath in (session_part_files(recording_path) or [Path(recording_path)]):
        try:
            with open(fpath, encoding="utf-8") as f:
                for line in f:
                    try:
                        rec = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if rec.get("feed") != venue or rec.get("method") != \
                            "get_order_book":
                        continue
                    res = rec.get("result") or {}
                    bids = res.get("bids") or []
                    asks = res.get("asks") or []
                    if not bids or not asks:
                        continue
                    sym = (rec.get("args") or ["?"])[0]
                    try:
                        bid = float(bids[0][0])
                        ask = float(asks[0][0])
                    except (TypeError, ValueError, IndexError):
                        continue
                    by_symbol.setdefault(sym, []).append(
                        {"ts": rec.get("t", 0.0), "bid": bid, "ask": ask})
        except OSError as e:
            log.warning("recording read failed %s: %s", fpath, e)
    return by_symbol


# ------------------------------------------------------------- orchestration
def calibrate_from_recordings(rec_dir, sf_base_current: float, n_bar: float, *,
                              dist_grid=None, venue="kraken",
                              life_polls: int = 5) -> list:
    """Aggregate trade-through across recordings, return per-distance verdicts."""
    dist_grid = dist_grid or DEFAULT_DIST_GRID_BPS
    agg: dict = {d: [0, 0, 0.0, 0] for d in dist_grid}   # dist -> [k,n,d_bar_sum,parts]
    for rec in discover_recordings(rec_dir):
        for _sym, frames in extract_frames(str(rec), venue).items():
            if len(frames) < 3:
                continue
            sigma = estimate_sigma_bps(frames)
            for row in trade_through_counts(frames, life_polls, dist_grid,
                                            sigma):
                a = agg[row["dist_bps"]]
                a[0] += row["k"]
                a[1] += row["n"]
                a[2] += row["d_bar"]
                a[3] += 1
    results = []
    for dist in dist_grid:
        k, n, dsum, parts = agg[dist]
        if parts == 0:
            continue
        d_bar = dsum / parts
        results.append(calibrate(k, n, d_bar, n_bar, sf_base_current))
    return results


def _headline(results: list):
    """Pick the recommendation: the armed near-touch bucket with the most data."""
    armed = [r for r in results if r.status in ("OK", "NO_CHANGE")
             and r.d_bar is not None and r.d_bar <= D_MAX_DEFAULT]
    if not armed:
        return None
    return max(armed, key=lambda r: r.n)


def render_report(ledger: dict, results: list, sf_base_current: float,
                  headline) -> tuple:
    """Return (markdown, json_obj)."""
    misspec = not buckets_agree(results)
    obj = {
        "sf_base_current": sf_base_current,
        "ledger": ledger,
        "model_misspecified": misspec,
        "buckets": [{"status": r.status, "sf_base_star": r.sf_base_star,
                     "band": list(r.band) if r.band else None, "n": r.n,
                     "k": r.k, "d_bar": r.d_bar, "reason": r.reason}
                    for r in results],
        "headline": None if headline is None else {
            "status": headline.status, "sf_base_star": headline.sf_base_star,
            "band": list(headline.band) if headline.band else None,
            "n": headline.n, "reason": headline.reason},
    }
    lines = ["# Dry-run fill-model calibration", ""]
    lines.append(f"- current `passive_base_prob` (sf_base): "
                 f"**{sf_base_current:.3f}**")
    lines.append(f"- ledger: {ledger.get('maker_fills', 0)} maker / "
                 f"{ledger.get('taker_fills', 0)} taker fills; "
                 f"slip p50/p95 = {ledger.get('slip_p50_bps')}/"
                 f"{ledger.get('slip_p95_bps')} bps")
    if not results:
        lines += ["", "_No recordings: trade-through calibration DEFERRED "
                  "(the recommendation needs recorded book frames). Turn on "
                  "`system.record_feeds` and accrue sessions._"]
    else:
        lines += ["", "| dist d_bar | n | k | status | sf_base* | band |",
                  "|---|---|---|---|---|---|"]
        for r in results:
            star = "-" if r.sf_base_star is None else f"{r.sf_base_star:.3f}"
            band = "-" if r.band is None else f"[{r.band[0]:.3f},{r.band[1]:.3f}]"
            db = "-" if r.d_bar is None else f"{r.d_bar:.2f}"
            lines.append(f"| {db} | {r.n} | {r.k} | {r.status} | {star} | "
                         f"{band} |")
        if misspec:
            lines += ["", f"> **{Code.XV_CALIB_MISSPECIFIED.value}**: "
                      "per-distance buckets disagree - the exp(-d_bar) form is "
                      "misspecified; treat any single number with suspicion."]
        if headline is None:
            lines += ["", f"**{Code.XV_CALIB_DEFERRED.value}**: no near-touch "
                      "bucket is adequately powered yet - no recommendation."]
        elif headline.status == "NO_CHANGE":
            lines += ["", f"**Recommendation: no change.** current "
                      f"{sf_base_current:.3f} sits inside the sampling band "
                      f"{obj['headline']['band']}."]
        else:
            lines += ["", f"**{Code.XV_CALIB_RECOMMEND.value}**: recommend "
                      f"`passive_base_prob` ~= "
                      f"**{headline.sf_base_star:.3f}** "
                      f"(band {obj['headline']['band']}, n={headline.n}). "
                      "Analysis only - review before changing config."]
    return "\n".join(lines) + "\n", obj


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.json")
    ap.add_argument("--recording-dir", default="outputs/recordings")
    ap.add_argument("--out-dir", default="outputs")
    args = ap.parse_args()
    logging.basicConfig(level=logging.WARNING,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    cfg = load_config(args.config)
    om = cfg.get("order_manager", {}) or {}
    sf = om.get("sim_fill", {}) or {}
    sf_base_current = _f(sf.get("passive_base_prob", 0.45), 0.45)
    poll_sec = _f(cfg.get("system", {}).get("cycle_interval_sec")
                  or om.get("poll_sec") or 5.0, 5.0)
    life_sec = _f(om.get("order_timeout_sec", 25.0), 25.0)
    n_bar = max(life_sec / max(poll_sec, 1e-6), 1.0)
    life_polls = max(int(round(n_bar)), 1)

    ledger_path = Path(cfg.get("system", {}).get("fills_ledger_path",
                                                 "outputs/fills.csv"))
    ledger_rows = []
    if ledger_path.exists():
        try:
            with open(ledger_path, encoding="utf-8") as fh:
                ledger_rows = list(csv.DictReader(fh))
        except OSError as e:
            log.warning("ledger read failed: %s", e)
    ledger = ledger_maker_fill_summary(ledger_rows)

    results = calibrate_from_recordings(args.recording_dir, sf_base_current,
                                        n_bar, life_polls=life_polls)
    headline = _headline(results)
    md, obj = render_report(ledger, results, sf_base_current, headline)

    out_dir = Path(args.out_dir)
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "fill_calibration.md").write_text(md, encoding="utf-8")
        (out_dir / "fill_calibration.json").write_text(
            json.dumps(obj, indent=2), encoding="utf-8")
    except OSError as e:
        log.warning("report write failed: %s", e)
    print(md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
