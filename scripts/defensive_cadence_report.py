"""ALGO-3: the defensive-cadence report (Grand Synthesis Tier 1, adjudicated
2026-08-11 — REPORT ONLY, zero engine writes).

THE QUESTION IT ANSWERS: does the bot's trading cadence adapt DEFENSIVELY to
hostile tape — and do outcomes justify the cadence it keeps? Hostility here
is measured three ways the corpus already carries (vol_percentile,
turbulence_pct, funding_dist), plus the Osler stop-zone score th_stopzone,
which the bull-readiness directive singles out: promising-looking books with
heavy clustered stops are exactly where cadence should FALL.

MEASUREMENT DISCIPLINE (comparability-boundaries law):
- Everything below is DRY-RUN paper data. Nothing here is venue truth.
- Label-axis stats filter to label_era == triple_barrier_h432 (the current
  cohort); live closes (exit_sim) are reported separately, never pooled.
- Money-axis stats cut at the capital epoch 2026-08-10T23:05:27Z; stop
  geometry stats cut at cut #7 2026-08-11T01:33:50Z. Sections state their
  cut. Small n is printed, never hidden behind a percentage.

Writes outputs/defensive_cadence.md (the established report-file pattern:
gate_efficacy.md, fill_calibration.md) and a stdout summary. It never
touches engine state, config, or any ledger.
"""
from __future__ import annotations

import csv
import math
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SIG = ROOT / "outputs" / "signal_history.csv"
PATHS = ROOT / "outputs" / "trade_paths.csv"
FILLS = ROOT / "outputs" / "fills.csv"
OUT = ROOT / "outputs" / "defensive_cadence.md"

CAPITAL_EPOCH_TS = 1786403127.0          # 2026-08-10T23:05:27Z
CUT7_TS = 1786412030.0                   # 2026-08-11T01:33:50Z exactly (e7d5ca1a).
# owed-78 CLOSED 2026-08-19: the prior constant 1786411630.0 was 400s EARLY
# (01:27:10Z) while its comment certified 01:33:50Z - every geometry-side
# split this report cut there included up to 400s of pre-epoch rows, and
# item 69's split was measured through it. Re-derived three times
# (catch-up filing x2, tonight's datetime check); vault owed-measurements
# item 78 records the history.
H432 = "triple_barrier_h432"


def _f(x, default=float("nan")):
    try:
        v = float(x)
        return v if math.isfinite(v) else default
    except (TypeError, ValueError):
        return default


def _read(path):
    if not path.exists():
        return []
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _tercile_edges(vals):
    s = sorted(vals)
    if len(s) < 3:
        return None
    return s[len(s) // 3], s[2 * len(s) // 3]


def _tercile(v, edges):
    if edges is None or not math.isfinite(v):
        return "n/a"
    lo, hi = edges
    return "low" if v <= lo else ("high" if v > hi else "mid")


def _bucket_table(rows, col, title, lines):
    """Candidate cadence + outcome mix, bucketed by terciles of `col`."""
    vals = [_f(r.get(col)) for r in rows]
    edges = _tercile_edges([v for v in vals if math.isfinite(v)])
    buckets = defaultdict(list)
    for r, v in zip(rows, vals, strict=True):
        buckets[_tercile(v, edges)].append(r)
    lines.append(f"\n### {title} (terciles of `{col}`, h432 candidates)\n")
    lines.append("| bucket | n | labeled | win rate | tb_sl | tb_pt | tb_time |")
    lines.append("|---|---|---|---|---|---|---|")
    for b in ("low", "mid", "high", "n/a"):
        rs = buckets.get(b, [])
        if not rs:
            continue
        labeled = [r for r in rs if r.get("label") in ("0", "1")]
        wins = sum(1 for r in labeled if r["label"] == "1")
        bar = Counter(r.get("barrier", "") for r in labeled)
        nl = len(labeled)
        wr = f"{wins / nl:.1%}" if nl else "—"

        def share(k, _bar=bar, _nl=nl):
            return f"{_bar.get(k, 0) / _nl:.0%}" if _nl else "—"
        lines.append(f"| {b} | {len(rs)} | {nl} | {wr} (n={nl}) | "
                     f"{share('tb_sl')} | {share('tb_pt')} | {share('tb_time')} |")


def main() -> int:
    # Windows console defaults to cp1252; the md file is utf-8 either way
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    now = time.time()
    sig = _read(SIG)
    paths = _read(PATHS)
    fills = _read(FILLS)
    lines = ["# Defensive-cadence report (ALGO-3)\n",
             f"Generated {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(now))} — "
             "DRY-RUN paper data throughout; nothing here is venue truth.\n",
             "Cuts applied: label stats = `triple_barrier_h432` only; money cut = "
             "capital epoch 2026-08-10T23:05:27Z; stop-geometry cut = cut #7 "
             "2026-08-11T01:33:50Z. Sections state which side they read.\n"]

    # ---------------------------------------------------------------- cadence
    cand = [r for r in sig if r.get("source") == "candidate"
            and r.get("label_era") == H432]
    live = [r for r in sig if r.get("source") == "live"]
    lines.append("## 1. Cadence: how selective is the book being?\n")
    lines.append(f"- h432 candidate rows: **{len(cand)}** · live close rows: "
                 f"**{len(live)}** (separate era `exit_sim`, never pooled)")
    post_cand = [r for r in cand if _f(r.get("ts")) >= CAPITAL_EPOCH_TS]
    lines.append(f"- candidates minted since the capital epoch: **{len(post_cand)}**")
    day = 86400.0
    recent = [r for r in cand if _f(r.get("ts")) >= now - 7 * day]
    by_day = Counter(int((_f(r.get("ts")) - (now - 7 * day)) // day) for r in recent)
    if recent:
        lines.append("- candidate cadence, last 7 days (per day): "
                     + ", ".join(str(by_day.get(d, 0)) for d in range(7)))

    # ------------------------------------------------- hostility bucket tables
    lines.append("\n## 2. Outcomes by hostility bucket (label axis, h432)\n")
    lines.append("If cadence is defensively adapted, the HIGH buckets should "
                 "show fewer candidates taken and no worse a barrier mix; a "
                 "rising tb_sl share in high-hostility buckets is the shakeout "
                 "signature the bull-readiness directive names.")
    _bucket_table(cand, "vol_percentile", "Volatility", lines)
    _bucket_table(cand, "turbulence_pct", "Turbulence", lines)
    _bucket_table(cand, "funding_dist", "Funding distance", lines)
    _bucket_table(cand, "th_stopzone", "Stop-cluster proximity (Osler zone)", lines)

    # ------------------------------------------------- momentum conditioning
    lines.append("\n## 2b. Momentum alignment (owed 69 — LEAD, not fact)\n")
    lines.append("The 2026-08-11 audit's verifier found candidates entered "
                 "WITH 12-bar momentum winning LESS at h432, symmetrically "
                 "in both direction cohorts. ret_12_dir is SIDE-RELATIVE "
                 "(positive = momentum with the trade, ml/features.py:342) "
                 "— do not read it market-absolute. The lifetime table "
                 "pools across every boundary cut; the post-epoch table is "
                 "the clean cohort and stays a lead until its n is real.")
    def _mom_table(rows, tag):
        lines.append(f"\n### {tag}\n")
        lines.append("| direction | momentum | n | win rate |")
        lines.append("|---|---|---|---|")
        for want_dir, dlabel in ((1.0, "long"), (-1.0, "short")):
            drs = [r for r in rows if _f(r.get("direction")) == want_dir
                   and r.get("label") in ("0", "1")]
            for lo, hi, mlabel in ((0.5, float("inf"), "with (>+0.5)"),
                                   (-0.5, 0.5, "flat"),
                                   (float("-inf"), -0.5, "against (<-0.5)")):
                sub = [r for r in drs
                       if lo <= _f(r.get("ret_12_dir")) < hi]
                n = len(sub)
                wr = (f"{sum(1 for r in sub if r['label'] == '1') / n:.1%}"
                      if n else "—")
                lines.append(f"| {dlabel} | {mlabel} | {n} | {wr} |")
    _mom_table(cand, "Lifetime h432 candidates (POOLED across all cuts — "
                     "context only)")
    _mom_table(post_cand, "Since capital epoch (clean cohort — the owed-69 "
                          "measurement of record as it accrues)")

    # ------------------------------------------------------ live-close section
    lines.append("\n## 3. Live closes (exit_sim era — separate ledger)\n")
    if live:
        pnl = [_f(r.get("net_pnl_usd"), 0.0) for r in live]
        post = [r for r in live if _f(r.get("ts")) >= CAPITAL_EPOCH_TS]
        lines.append(f"- lifetime live closes in corpus: {len(live)}, net "
                     f"${sum(pnl):.2f} (pooled across ALL boundary cuts — "
                     "context only, never a verdict)")
        lines.append(f"- since capital epoch: **{len(post)}** closes "
                     f"(gate accrual counts a subset; see cohort_eval)")
    else:
        lines.append("- none recorded")

    # ------------------------------------------------------ trade-path section
    lines.append("\n## 4. Uncensored trade paths (post-cut-#7 geometry)\n")
    real_paths = [r for r in paths if _f(r.get("ts")) >= CUT7_TS]
    if real_paths:
        by_reg = defaultdict(list)
        for r in real_paths:
            by_reg[r.get("regime_entry", "?")].append(r)
        lines.append("| regime_entry | n | med MAE% | med MFE% | stopped | causes |")
        lines.append("|---|---|---|---|---|---|")
        for reg, rs in sorted(by_reg.items()):
            maes = sorted(_f(r.get("mae_pct")) for r in rs)
            mfes = sorted(_f(r.get("mfe_pct")) for r in rs)
            stopped = sum(1 for r in rs if r.get("stopped_out") == "1")
            causes = Counter(r.get("cause", "") for r in rs)
            top = ", ".join(f"{c}×{n}" for c, n in causes.most_common(3))
            lines.append(f"| {reg} | {len(rs)} | {maes[len(maes)//2]:.2f} | "
                         f"{mfes[len(mfes)//2]:.2f} | {stopped} | {top} |")
    else:
        lines.append("- **0 paths since cut #7** — the ledger accrues from "
                     "2026-08-11T01:33:50Z; the ALGO-5 amendment is pre-named "
                     "at ~30 uncensored paths (owed 67). Nothing to report is "
                     "the correct state, not a defect.")

    # -------------------------------------------------------- fills since epoch
    lines.append("\n## 5. Post-epoch executions (money axis)\n")
    post_fills = [r for r in fills if _f(r.get("ts")) >= CAPITAL_EPOCH_TS]
    if post_fills:
        by_asset = Counter(r.get("asset") or r.get("symbol", "?") for r in post_fills)
        lines.append(f"- fills since capital epoch: **{len(post_fills)}** — "
                     + ", ".join(f"{a}×{n}" for a, n in by_asset.most_common()))
        eras = Counter(r.get("exec_era", "") for r in post_fills)
        lines.append(f"- exec_era stamps: {dict(eras)}")
    else:
        lines.append("- no fills since the capital epoch yet ($800 book, "
                     "honest-fill starvation is the expected rate)")

    body = "\n".join(lines) + "\n"
    OUT.write_text(body, encoding="utf-8")
    print(body)
    print(f"[defensive_cadence] wrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
