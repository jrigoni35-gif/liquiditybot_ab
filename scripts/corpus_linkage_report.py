"""
scripts/corpus_linkage_report.py — T2.4 Fellegi-Sunter EM corpus linkage
report (offline, REPORT-ONLY: reads signal_history.csv, writes
outputs/corpus_linkage_report.{md,json}, never touches config or state).

Task 3 already threads exact lineage (candidate_id) between a live close
and the candidate row it descends from. That JOIN only fires for rows
the pipeline itself can prove correlated; every OTHER live row still has
a population of candidate "twins" nearby in time, on the same
(asset, side), that got no chance at a match — no lineage recorded, or
the vector match's 6-decimal tolerance missed a candidate whose features
drifted (funding_dist is a clock function, recomputed fresh every
cycle). This script builds that residual pair space and probabilistically
links it with `ml.linkage.FellegiSunterEM`, EXPANDING the T2.2b
sim-to-live agreement sample beyond the exact-lineage set — reported
side by side with it, never merged into it.

Pair space: for every live row, every candidate row sharing its
(asset, side) within `window_h` hours of its signal_ts is a candidate
pair, MINUS any pair that is already an exact-lineage pair (Task 3) —
those are excluded from the EM fit and reported as their own population.
`book == "long"` rows (risk/long_book.py's own closes - a different
trading process, no p(win)/edge signal) are excluded from BOTH sides
before pairing, mirroring ml/history.py's load-time exclusion: a
long-book row must never be linked against a 5m twin it has nothing to
do with. Each surviving pair is reduced to a 2-variable fuzzy pattern (both
`FellegiSunterEM.k_exact == 0`: asset/side agreement is already enforced
by the pairing itself, so an "exact" variable that is always 1 would add
nothing):
  fuzzy 1 — signal-time proximity  (|delta signal_ts| in minutes)
  fuzzy 2 — feature proximity      (mean |delta feature| over
                                     ml.features.FEATURE_NAMES)
A pair whose PATTERN's fitted posterior P(match|pattern) clears
`ml.linkage.posterior_threshold` counts as "linked". Label agreement
(does the live row's realized label match the candidate row's
triple-barrier label) is then computed over the linked population and,
side by side, over the exact-lineage population, each with a Wilson
interval (`ml.history.wilson_interval`).

Report-only, same as T2.2's telemetry: this NEVER reweights training
data or gates any decision on its own. The Phase-4 density-ratio item is
the only consumer, and it applies its own gates.

Usage: python scripts/corpus_linkage_report.py [--config config.json]
                                                [--history PATH]
                                                [--out-dir outputs]
"""
import argparse
import csv
import json
import logging
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.codes import Code                                  # noqa: E402
from ml.features import FEATURE_NAMES                        # noqa: E402
from ml.history import wilson_interval                       # noqa: E402
from ml.linkage import FellegiSunterEM, discretize_fuzzy      # noqa: E402

log = logging.getLogger("liquiditybot.ml.linkage")

DEFAULTS = {
    "window_h": 24.0,           # +/- pairing window around a live signal_ts
    "ts_near_min": 10.0,        # fuzzy1 (ts proximity): "most similar" band
    "ts_far_min": 60.0,         # fuzzy1: beyond this, "least similar"
    "feat_near": 0.05,          # fuzzy2 (mean |delta feature|): "most similar"
    "feat_far": 0.25,           # fuzzy2: beyond this, "least similar"
    "posterior_threshold": 0.9,
    "seed": 7,
}


def _read_rows(path) -> list:
    p = Path(path)
    if not p.exists():
        return []
    with open(p, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _to_float(row: dict, key: str, default: float = 0.0) -> float:
    try:
        return float(row.get(key) or default)
    except (TypeError, ValueError):
        return default


def _feat_vec(row: dict) -> np.ndarray:
    return np.array([_to_float(row, n) for n in FEATURE_NAMES], dtype=float)


def _agreement(pairs: list) -> dict:
    """`pairs` is a list of (live_label, cand_label). Wilson95 over the
    fraction that agree; n=0 -> agreement/wilson95 both None (nothing to
    report, distinct from a measured 0%)."""
    n = len(pairs)
    if n == 0:
        return {"n": 0, "k": 0, "agreement": None, "wilson95": None}
    k = sum(1 for lv, cv in pairs if lv == cv)
    lo, hi = wilson_interval(k, n)
    return {"n": n, "k": k, "agreement": round(k / n, 4),
            "wilson95": [round(lo, 4), round(hi, 4)]}


def build_report(history_path, cfg: dict) -> tuple:
    """Pure core: (markdown, json-dict). Reads `history_path` itself (a
    raw csv.DictReader scan, header-resolved — never assumes column
    position) so it works unchanged against a HistoryStore-written file
    or a hand-built test fixture sharing its header."""
    c = {**DEFAULTS, **(cfg or {})}
    threshold = float(c["posterior_threshold"])
    seed = int(c["seed"])
    window_sec = float(c["window_h"]) * 3600.0

    rows = _read_rows(history_path)
    # book=="long" rows are the long-horizon accumulation book's own
    # closes (risk/long_book.py) - a completely different trading
    # process (patient, ladder-gated accumulation, no p(win)/edge
    # signal) from the 5m scalping flow this linkage is built for.
    # Excluded from BOTH sides here, before any pairing, mirroring
    # ml/history.py's load-time exclusion (book contamination guard):
    # a long-book live/candidate row must never be linked against a 5m
    # twin it has nothing to do with. (row.get("book") or "5m") mirrors
    # every other book-tag read site's default (pre-C1 rows / any
    # writer that never heard of `book`).
    rows = [r for r in rows if (r.get("book") or "5m") != "long"]
    live = [r for r in rows if (r.get("source") or "") == "live"]
    cands = [r for r in rows if (r.get("source") or "") == "candidate"]

    exact_pairs: list = []              # (live_label, cand_label)
    fuzzy_rows: list = []               # (ts_min, feat_diff, live_label, cand_label)
    for lrow in live:
        try:
            l_label = float(lrow.get("label"))
        except (TypeError, ValueError):
            continue
        l_asset = lrow.get("asset") or ""
        l_side = lrow.get("side") or ""
        l_ts = _to_float(lrow, "signal_ts", _to_float(lrow, "ts", 0.0))
        l_cid = (lrow.get("candidate_id") or "").strip()
        l_feat = _feat_vec(lrow)
        for crow in cands:
            if (crow.get("asset") or "") != l_asset:
                continue
            if (crow.get("side") or "") != l_side:
                continue
            try:
                c_label = float(crow.get("label"))
            except (TypeError, ValueError):
                continue
            c_ts = _to_float(crow, "signal_ts", _to_float(crow, "ts", 0.0))
            dt = abs(l_ts - c_ts)
            if dt > window_sec:
                continue
            c_pid = (crow.get("position_id") or "").strip()
            if l_cid and c_pid and l_cid == c_pid:
                exact_pairs.append((l_label, c_label))
                continue         # Task 3's exact-lineage pair - excluded from EM
            feat_diff = float(np.mean(np.abs(l_feat - _feat_vec(crow))))
            fuzzy_rows.append((dt / 60.0, feat_diff, l_label, c_label))

    n_exact = len(exact_pairs)
    n_fuzzy = len(fuzzy_rows)
    agreement_exact = _agreement(exact_pairs)

    lam = None
    converged = None
    patterns_list: list = []
    pattern_counts: list = []
    pattern_posterior: list = []
    n_linked = 0
    agreement_linked = _agreement([])

    if n_fuzzy:
        ts_min = np.array([r[0] for r in fuzzy_rows])
        feat_diff = np.array([r[1] for r in fuzzy_rows])
        f1 = discretize_fuzzy(ts_min, near=c["ts_near_min"], far=c["ts_far_min"])
        f2 = discretize_fuzzy(feat_diff, near=c["feat_near"], far=c["feat_far"])

        shape = FellegiSunterEM(2, 0, np.zeros(9))
        patterns = shape.patterns
        pattern_index = {tuple(p): i for i, p in enumerate(patterns.tolist())}
        counts = np.zeros(len(patterns))
        pair_pattern_idx = []
        for a, b in zip(f1.tolist(), f2.tolist(), strict=True):
            idx = pattern_index[(int(a), int(b))]
            counts[idx] += 1
            pair_pattern_idx.append(idx)

        est = FellegiSunterEM(2, 0, counts, seed=seed).fit()
        post = est.match_posterior
        lam = round(float(est.lam), 6)
        converged = bool(est.converged)
        patterns_list = patterns.tolist()
        pattern_counts = [int(x) for x in counts.tolist()]
        pattern_posterior = [round(float(x), 6) for x in post.tolist()]

        linked_by_pattern = post >= threshold
        linked_pairs = [(fuzzy_rows[i][2], fuzzy_rows[i][3])
                        for i, idx in enumerate(pair_pattern_idx)
                        if linked_by_pattern[idx]]
        n_linked = len(linked_pairs)
        agreement_linked = _agreement(linked_pairs)

    rep = {
        "history_path": str(history_path),
        "n_live_rows": len(live),
        "n_candidate_rows": len(cands),
        "n_exact_pairs": n_exact,
        "n_fuzzy_pairs": n_fuzzy,
        "n_linked_pairs": n_linked,
        "threshold": threshold,
        "seed": seed,
        "lambda": lam,
        "converged": converged,
        "patterns": patterns_list,
        "pattern_counts": pattern_counts,
        "pattern_posterior": pattern_posterior,
        "agreement_linked": agreement_linked,
        "agreement_exact": agreement_exact,
    }

    md_lines = ["# Corpus linkage report (T2.4 Fellegi-Sunter EM)", "",
               f"history: `{history_path}`", "",
               f"- live rows: **{len(live)}** · candidate rows: "
               f"**{len(cands)}**",
               f"- exact-lineage pairs (Task 3 `candidate_id` join): "
               f"**{n_exact}**",
               f"- fuzzy candidate-pair pool (excludes exact-lineage): "
               f"**{n_fuzzy}**",
               f"- probabilistically-linked pairs (posterior >= "
               f"{threshold}): **{n_linked}**", ""]
    if not n_fuzzy:
        md_lines += ["No fuzzy candidate pairs in the corpus (asset/side/"
                    "time-window filters left nothing to link) — EM was "
                    "not fit.", ""]
    else:
        md_lines += [f"lambda (unconditional match probability): "
                    f"**{lam:.4f}**",
                    f"EM: {'converged' if converged else 'hit max_iter'}",
                    "",
                    "## Posterior per pattern (fuzzy1 = ts proximity, "
                    "fuzzy2 = feature proximity; 2 = most similar)", "",
                    "| pattern | count | P(match\\|pattern) | linked |",
                    "|---|---|---|---|"]
        for pat, cnt, p in zip(patterns_list, pattern_counts,
                               pattern_posterior, strict=True):
            md_lines.append(f"| {tuple(pat)} | {cnt} | {p:.4f} | "
                            f"{'yes' if p >= threshold else 'no'} |")
        md_lines.append("")
    md_lines += ["## Label agreement (live label == candidate label)", ""]
    if agreement_linked["n"]:
        md_lines.append(
            f"- linked pairs: {agreement_linked['k']}/{agreement_linked['n']}"
            f" agree ({agreement_linked['agreement']:.1%}), Wilson95 "
            f"[{agreement_linked['wilson95'][0]:.2f}, "
            f"{agreement_linked['wilson95'][1]:.2f}]")
    else:
        md_lines.append("- linked pairs: none")
    if agreement_exact["n"]:
        md_lines.append(
            f"- exact-lineage pairs: {agreement_exact['k']}/"
            f"{agreement_exact['n']} agree "
            f"({agreement_exact['agreement']:.1%}), Wilson95 "
            f"[{agreement_exact['wilson95'][0]:.2f}, "
            f"{agreement_exact['wilson95'][1]:.2f}]")
    else:
        md_lines.append("- exact-lineage pairs: none")
    md_lines += ["",
                "Report-only: this expands the T2.2b sim-to-live agreement "
                "sample over gate-passing signals only — it feeds NO "
                "weights on its own; the Phase-4 density-ratio item "
                "consumes it under its own gates.", ""]
    md = "\n".join(md_lines) + "\n"

    log.info("%s: %d exact-lineage + %d linked pair(s) of %d fuzzy "
             "candidate(s), lambda=%s - report-only, no weight authority",
             Code.ML_LINKAGE_REPORT.value, n_exact, n_linked, n_fuzzy,
             f"{lam:.4f}" if lam is not None else "n/a")
    return md, rep


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=str(ROOT / "config.json"))
    ap.add_argument("--history", default=None)
    ap.add_argument("--out-dir", default=str(ROOT / "outputs"))
    args = ap.parse_args(argv)
    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    ml_cfg = config.get("ml", {}) or {}
    lk_cfg = ml_cfg.get("linkage", {}) or {}
    history_path = args.history or ml_cfg.get(
        "history_path", "outputs/signal_history.csv")

    md, rep = build_report(history_path, lk_cfg)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_md = out_dir / "corpus_linkage_report.md"
    out_js = out_dir / "corpus_linkage_report.json"
    out_md.write_text(md, encoding="utf-8")
    out_js.write_text(json.dumps(rep, indent=1), encoding="utf-8")
    print(md)
    print(f"written: {out_md} / {out_js}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
