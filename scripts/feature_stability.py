"""
scripts/feature_stability.py — T3.1 dead-list stability screen (offline,
REPORT-ONLY: reads the real training corpus + config, writes dated
outputs/feature_reports/stability_<UTCstamp>.{json,md}; never touches
config, model artifacts, or shipped ml/ code — it CALLS
ml.overfit.feature_dof_report, nothing in ml/ is modified).

Spec: docs/superpowers/specs/2026-07-25-learning-acceleration-design.md
§4 T3.1 — "dead-feature membership across >=3 report dates x folds x
seeds, training-side only; all five regime one-hots exempt (dead by
coverage, not uselessness)."

Why this exists: ml/overfit.py's feature_dof_report (OF-7) already
computes a per-feature "dead" flag (near-zero OOS permutation
importance), but scripts/overfit_check.py calls it with exactly ONE
seed/n_splits combo, and NEITHER outputs/overfit_report.md nor
outputs/interpret_report.json carries any dated retention — both
overwrite in place on every run. A single seed/fold-cut is not a stable
membership set: a live side-by-side re-run of the identical function
against a corpus ~30 rows larger (same code, same seed=7) flipped
dead_feature_frac 0.52 -> 0.597 (32 -> 37 of 62 features), with largely
different membership, purely because fold boundaries shift with N.

This script sweeps MULTIPLE (seed x n_splits) combos per run, snapshots
the result under a wall-clock filename (append-only — a run never
overwrites a prior dated snapshot), and accrues a cross-DATE persistence
view once >=2 prior snapshots exist in --out-dir, so a feature only
becomes a genuine prune CANDIDATE after surviving unanimous dead status
across every combo of the CURRENT run AND every PRIOR dated snapshot's
always_dead set. The five regime one-hots are hard-excluded from every
aggregate dead set regardless of their measured status: the corpus is
almost entirely regime[range]/regime[bear] today, so three of the five
one-hot columns are structurally constant-zero and mechanically read as
"dead" no matter how informative the regime concept is — dead by
coverage, not uselessness, per the spec line above.

Usage: python scripts/feature_stability.py [--seeds 7,11,13]
    [--n-splits-list 4,5,6] [--out-dir outputs/feature_reports]
    [--min-rows N] [--label-span 96] [--config config.json]
"""
import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ml.features import FEATURE_NAMES, REGIME_ONE_HOT_FEATURES  # noqa: E402
from ml.history import HistoryStore                              # noqa: E402
from ml.overfit import feature_dof_report                         # noqa: E402


# ---------------------------------------------------------------------------
# pure computation (no wall-clock, no file I/O — fully deterministic given
# identical X, y, feature_names, seeds, n_splits_list, sig)
# ---------------------------------------------------------------------------
def compute_snapshot(X, y, feature_names, seeds, n_splits_list, *, sig=None,
                     label_span: int = 96, corpus_rows: "int | None" = None,
                     n_live: "int | None" = None) -> dict:
    """Runs feature_dof_report once per (seed x n_splits) combo on the SAME
    corpus and aggregates dead-feature membership. always_dead/ever_dead/
    flip_features/stability_ratio are computed with the five regime
    one-hots REMOVED first (see module docstring / spec T3.1 exemption) —
    the exemption is unconditional (hard-coded), not "only if they
    happened to test dead this run". Each combo's raw `dead` list (as
    feature_dof_report actually returned it, unfiltered) is still kept
    verbatim for traceability.

    Identical inputs -> identical output: no randomness here beyond what
    feature_dof_report itself seeds deterministically, and no timestamp is
    read anywhere in this function — callers stamp the snapshot
    filename/metadata themselves so the MEASURED content stays fully
    reproducible."""
    feature_names = list(feature_names)
    # docs/superpowers/specs/2026-07-25-learning-acceleration-design.md:90-92
    # "all five regime one-hots exempt (dead by coverage, not
    # uselessness)" — hard exclusion, independent of this run's readings.
    regime_exempt = set(REGIME_ONE_HOT_FEATURES) & set(feature_names)

    combos = []
    for seed in seeds:
        for n_splits in n_splits_list:
            dof = feature_dof_report(X, y, feature_names,
                                     label_span=label_span,
                                     n_splits=n_splits, seed=seed, sig=sig)
            combos.append({"seed": int(seed), "n_splits": int(n_splits),
                           "dead": sorted(dof["dead_features"])})

    dead_sets = [set(c["dead"]) - regime_exempt for c in combos]
    if dead_sets:
        always_dead = set.intersection(*dead_sets)
        ever_dead = set.union(*dead_sets)
    else:
        always_dead, ever_dead = set(), set()
    flip_features = ever_dead - always_dead
    # |always|/|ever|; a union of zero dead features means no combo ever
    # disagreed about anything (vacuously perfectly stable) -> 1.0, never
    # a ZeroDivisionError.
    stability_ratio = (len(always_dead) / len(ever_dead)) if ever_dead else 1.0

    return {
        "corpus_rows": int(corpus_rows) if corpus_rows is not None else int(len(X)),
        "n_live": int(n_live) if n_live is not None else 0,
        "seeds": [int(s) for s in seeds],
        "n_splits_list": [int(s) for s in n_splits_list],
        "combos": combos,
        "always_dead": sorted(always_dead),
        "ever_dead": sorted(ever_dead),
        "flip_features": sorted(flip_features),
        "stability_ratio": round(stability_ratio, 4),
        "regime_one_hots_excluded": sorted(regime_exempt),
    }


def load_prior_snapshots(out_dir: Path) -> list:
    """Every stability_*.json already on disk in --out-dir, oldest first
    (the UTC-stamped filename sorts chronologically). A snapshot that
    fails to parse is skipped with a warning rather than crashing the
    whole run — corrupt/partial history must not block a new dated
    reading."""
    snaps = []
    for p in sorted(Path(out_dir).glob("stability_*.json")):
        try:
            snaps.append(json.loads(p.read_text(encoding="utf-8")))
        except (OSError, ValueError) as e:
            print(f"warning: skipping unreadable prior snapshot {p}: {e!r}")
    return snaps


def compute_persistence(prior: list, current: dict) -> dict:
    """Cross-DATE section: across every accrued snapshot (all priors plus
    this run), what fraction call each feature always_dead. This is the
    spec's '>=3 report dates' screen accruing run by run — callers only
    attach this once >=2 priors exist (>=3 dates total with the current
    run)."""
    all_snaps = prior + [current]
    total = len(all_snaps)
    counts: dict = {}
    for s in all_snaps:
        for f in s.get("always_dead", []):
            counts[f] = counts.get(f, 0) + 1
    return {
        "dates_considered": total,
        "always_dead_persistence": {f: round(c / total, 4)
                                    for f, c in sorted(counts.items())},
    }


def compute_candidate_prune_list(prior: list, current: dict) -> list:
    """Brief's rule: features in always_dead across every combo of THIS
    run AND present in every prior snapshot's always_dead (if priors
    exist). With no priors yet, the candidate list is just this run's
    always_dead — the bar tightens as more dated snapshots accrue, which
    is exactly how the spec's '>=3 report dates' screen is meant to
    build up evidence run by run rather than all at once."""
    current_set = set(current.get("always_dead", []))
    if not prior:
        return sorted(current_set)
    prior_sets = [set(s.get("always_dead", [])) for s in prior]
    inter_prior = set.intersection(*prior_sets)
    return sorted(current_set & inter_prior)


def render_markdown(snap: dict) -> str:
    md = ["# Feature-stability screen (T3.1)", "",
          f"generated: **{snap.get('generated_utc', '?')}** UTC · corpus "
          f"{snap['corpus_rows']} rows ({snap['n_live']} live) · "
          f"{len(snap['seeds'])} seeds x {len(snap['n_splits_list'])} "
          f"n_splits = {len(snap['combos'])} combos", ""]

    md += ["## Per-combo dead-feature counts", "",
           "| seed | n_splits | dead features |", "|---|---|---|"]
    for c in snap["combos"]:
        md.append(f"| {c['seed']} | {c['n_splits']} | {len(c['dead'])} |")

    excluded = ", ".join(snap["regime_one_hots_excluded"]) or "none present"
    md += ["", "regime one-hots hard-excluded from always_dead/ever_dead "
           f"(dead by coverage, not uselessness — spec T3.1): {excluded}", ""]

    always = ", ".join(snap["always_dead"]) or "(none)"
    ever = ", ".join(snap["ever_dead"]) or "(none)"
    flip = ", ".join(snap["flip_features"]) or "(none)"
    md += [f"**always_dead** ({len(snap['always_dead'])}): {always}", "",
           f"**ever_dead** ({len(snap['ever_dead'])}): {ever}", "",
           f"**flip_features** ({len(snap['flip_features'])}): {flip}", "",
           f"**stability_ratio**: {snap['stability_ratio']:.4f} "
           f"(|always_dead| / |ever_dead|)", ""]

    if "persistence" in snap:
        p = snap["persistence"]
        md += [f"## Cross-date persistence ({p['dates_considered']} dates)",
               "", "| feature | always-dead fraction |", "|---|---|"]
        for f, r in p["always_dead_persistence"].items():
            md.append(f"| {f} | {r:.3f} |")
        md.append("")

    cpl = snap.get("candidate_prune_list", [])
    md += [f"## Candidate prune list ({len(cpl)})", "",
           (", ".join(cpl) or "(none — no feature qualifies yet)"), ""]
    return "\n".join(md) + "\n"


# ---------------------------------------------------------------------------
# wall-clock + file I/O — isolated here so compute_snapshot stays pure/pinned
# ---------------------------------------------------------------------------
def _utc_stamp() -> str:
    return time.strftime("%Y%m%d-%H%M%S", time.gmtime())


def _unique_stem(out_dir: Path, stamp: str) -> str:
    """Snapshot files are append-only history: this run's stamp must never
    collide with (and therefore never overwrite) a snapshot already on
    disk. If two runs land in the same UTC second, suffix -1, -2, ...
    until BOTH the .json and .md targets for that stem are free."""
    stem = f"stability_{stamp}"
    n = 0
    while (out_dir / f"{stem}.json").exists() or (out_dir / f"{stem}.md").exists():
        n += 1
        stem = f"stability_{stamp}-{n}"
    return stem


def run_snapshot(X, y, feature_names, seeds, n_splits_list, out_dir: Path, *,
                 sig=None, label_span: int = 96,
                 corpus_rows: "int | None" = None,
                 n_live: "int | None" = None) -> tuple:
    """Orchestrates one full dated snapshot: compute -> merge prior
    history -> write dated JSON + md twin (never overwriting an existing
    snapshot). Returns (json_path, md_path, snap)."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    prior = load_prior_snapshots(out_dir)

    snap = compute_snapshot(X, y, feature_names, seeds, n_splits_list,
                            sig=sig, label_span=label_span,
                            corpus_rows=corpus_rows, n_live=n_live)
    snap["prior_snapshot_count"] = len(prior)
    if len(prior) >= 2:
        snap["persistence"] = compute_persistence(prior, snap)
    snap["candidate_prune_list"] = compute_candidate_prune_list(prior, snap)

    stamp = _utc_stamp()
    snap["generated_utc"] = stamp
    stem = _unique_stem(out_dir, stamp)
    json_path = out_dir / f"{stem}.json"
    md_path = out_dir / f"{stem}.md"
    json_path.write_text(json.dumps(snap, indent=1), encoding="utf-8")
    md_path.write_text(render_markdown(snap), encoding="utf-8")
    return json_path, md_path, snap


def load_corpus(config_path: str, min_rows: int, *,
                store_factory=HistoryStore) -> tuple:
    """Loads the REAL training corpus only — training-side only per spec,
    and this screen measures the live ML-shipped feature set, so there is
    no synthetic fallback (contrast scripts/overfit_check.py's
    load_dataset, whose synthetic benchmark validates OF-1..OF-3
    machinery when live rows are thin — a different job than this
    screen's). Mirrors that function's real-corpus branch: same
    ml.sample_weights config plumbing, same last_load_stats/source_counts
    n_live derivation, same return_sig=True (time-based purge).

    Returns (X, y, sig, corpus_rows, n_live); X is None when corpus_rows
    is below the --min-rows floor — the caller must not run a stability
    screen on starved data."""
    try:
        with open(config_path, encoding="utf-8") as fh:
            cfg = json.load(fh)
    except (OSError, ValueError):
        cfg = {}
    ml_cfg = cfg.get("ml", {}) or {}
    weights_cfg = ml_cfg.get("sample_weights", {}) or {}
    store = store_factory(ml_cfg.get("history_path",
                                     "outputs/signal_history.csv"))
    X, y, _w, sig = store.load_training_data(return_sig=True,
                                              weights_cfg=weights_cfg)
    corpus_rows = len(X)
    if corpus_rows < min_rows:
        return None, None, None, corpus_rows, 0
    n_live = int((store.last_load_stats or {}).get(
        "live_clean", store.source_counts().get("live", 0)))
    return X, y, sig, corpus_rows, n_live


def _parse_int_list(s: str) -> list:
    return [int(tok) for tok in s.split(",") if tok.strip()]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="T3.1 dead-list stability screen — dated snapshots")
    ap.add_argument("--config", default=str(ROOT / "config.json"))
    ap.add_argument("--seeds", default="7,11,13",
                    help="comma-separated model seeds (>=3 recommended)")
    ap.add_argument("--n-splits-list", default="4,5,6",
                    help="comma-separated walk-forward fold counts")
    ap.add_argument("--out-dir",
                    default=str(ROOT / "outputs" / "feature_reports"))
    ap.add_argument("--min-rows", type=int, default=None,
                    help="row floor below which the corpus is too thin to "
                         "screen (default: 10 rows/feature, matching "
                         "feature_dof_report's own starvation floor)")
    ap.add_argument("--label-span", type=int, default=96)
    args = ap.parse_args(argv)

    seeds = _parse_int_list(args.seeds)
    n_splits_list = _parse_int_list(args.n_splits_list)
    min_rows = (args.min_rows if args.min_rows is not None
               else len(FEATURE_NAMES) * 10)

    X, y, sig, corpus_rows, n_live = load_corpus(args.config, min_rows)
    if X is None:
        print(f"corpus too thin for a stability screen: {corpus_rows} rows "
              f"< floor {min_rows} — refusing to snapshot starved data "
              f"(no synthetic fallback for this training-side-only screen)")
        return 1

    json_path, md_path, snap = run_snapshot(
        X, y, FEATURE_NAMES, seeds, n_splits_list, Path(args.out_dir),
        sig=sig, label_span=args.label_span, corpus_rows=corpus_rows,
        n_live=n_live)
    print(render_markdown(snap))
    print(f"written: {json_path} / {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
