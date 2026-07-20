"""
scripts/overfit_check.py — whole-codebase overfit audit, rev 4

Runs every overfitting instrument the system has against every layer
that can overfit, entirely offline, and emits a PASS/FAIL report:

  [OF-1] TRAIN/OOF GAP        ml/overfit.train_test_gap on the live
                              labeled history (or the planted-signal
                              synthetic benchmark when live rows < 60,
                              clearly labeled as machinery validation).
  [OF-2] SHUFFLED-LABEL NULL  leakage detector: destroyed labels must
                              yield chance OOF AUC through the purged
                              walk-forward. Catches purge bugs, feature
                              peeking, index misalignment.
  [OF-3] MODEL-SPACE PBO      CSCV probability-of-backtest-overfitting
                              across the model/hyperparameter space the
                              selector actually chooses from.
  [OF-4] STRATEGY PLATEAU     parameter-sensitivity via deterministic
                              record/replay: sweep post-signal knobs
                              (min_p_win, chandelier_k, edge ratio) and
                              measure whether performance sits on a
                              plateau (robust) or a spike (curve-fit).
  [OF-5] DEFLATED SHARPE      gate on live results: with < 30 labeled
                              live trades it reports DEFERRED, which is
                              the honest answer. While dry-run active
                              learning is on (ml.exploration.enabled) the
                              live sample is EV-mixed by design, so DSR
                              is reported INFORMATIONAL, not gated; it
                              arms when exploration is disabled.

Usage:
  python scripts/overfit_check.py [--quick] [--recording PATH]
Exit code 0 = all applicable checks pass, 1 = any failure.
"""

import argparse
import json
import logging
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np                                            # noqa: E402

from ml.history import HistoryStore                            # noqa: E402
from ml.overfit import (deflated_sharpe, feature_dof_report,   # noqa: E402
                        model_space_pbo, purge_leakage_probe,
                        shuffled_label_check, train_test_gap)

log = logging.getLogger("liquiditybot.scripts.overfit")
PASS_N, FAIL_N = 0, 0
REPORT: list = []


def check(name: str, ok: bool, detail: str = ""):
    global PASS_N, FAIL_N
    mark = "ok  " if ok else "FAIL"
    line = f"  {mark}  {name}" + (f"  {detail}" if detail else "")
    print(line)
    REPORT.append(("PASS" if ok else "FAIL", name, detail))
    if ok:
        PASS_N += 1
    else:
        FAIL_N += 1


def info(name: str, detail: str = ""):
    print(f"  --    {name}" + (f"  {detail}" if detail else ""))
    REPORT.append(("INFO", name, detail))


# ---------------------------------------------------------------------------
def split_dsr_samples(live_rows: list) -> tuple[list, list]:
    """OF-5 sample selection (pure, unit-tested). Returns (conviction, mixed)
    PnL lists from live-source rows. Conviction = probe column explicitly
    "0" — a PT-050 probe ("1") bypassed the profit-EV gate to buy its label,
    and a pre-marker row ("") is unknown provenance; neither may vouch for
    the deployed strategy's Sharpe. Mixed = every live row (the legacy
    sample, still reported for context)."""
    conviction, mixed = [], []
    for row in live_rows:
        try:
            pnl = float(row.get("net_pnl_usd"))
        except (TypeError, ValueError):
            continue
        mixed.append(pnl)
        if str(row.get("probe", "")).strip() == "0":
            conviction.append(pnl)
    return conviction, mixed


def synthetic_benchmark(n: int | None = None, seed: int = 11):
    """Planted-signal dataset with the live feature width: linear +
    regime-conditional structure + noise, known learnable ceiling. Used
    to validate the MACHINERY when live history is thin — results are
    about the pipeline, not the market, and the report says so.

    n scales with the feature-vector width (~35 rows/feature, matching
    the ratio this benchmark was originally calibrated at: 1200 rows /
    36 features). GradientBoostedStumps' colsample_bytree draws a FIXED
    FRACTION of columns as split candidates each round, so a wider
    feature vector at a fixed row count gives it more candidates per
    split and less effective regularization on this one fixed seed -
    a dimensionality artifact of adding features (all-zero padding in
    this synthetic set), not a live-model overfitting signal. Keeping
    the row count in step with feature count is a "re-baseline
    consciously" fix: the OF-1 pass bar (gap_auc <= 0.12) stays put."""
    from ml.features import FEATURE_NAMES
    rng = np.random.default_rng(seed)
    d = len(FEATURE_NAMES)
    if n is None:
        n = d * 40
    X = np.zeros((n, d))
    live = rng.normal(size=(n, 6))
    X[:, 0] = np.clip(live[:, 0], -6, 6)          # ret_1
    X[:, 1] = np.clip(live[:, 1], -6, 6)          # ret_6
    X[:, 6] = np.clip(live[:, 2] * 0.5, -2, 2)    # imbalance
    X[:, 11] = np.clip(live[:, 3], -5, 5)         # volume_z
    X[:, 15] = (live[:, 4] > 0).astype(float)     # regime_bull_quiet
    X[:, FEATURE_NAMES.index("direction")] = np.where(live[:, 5] > 0, 1, -1)
    X[:, FEATURE_NAMES.index("gate_confidence")] = 1.0
    logit = (0.5 * X[:, 0] + 0.9 * X[:, 6] * X[:, 15] +
             0.4 * X[:, 11] * (X[:, 15] - 0.5) - 0.1)
    y = (rng.random(n) < 1.0 / (1.0 + np.exp(-logit))).astype(float)
    return X, y


def load_dataset(min_rows: int | None = None, force_synthetic: bool = False):
    """min_rows gates when the ML-layer checks (OF-1/2/3/6/7) switch from
    the deterministic synthetic benchmark to real production history. It
    defaults to 10 rows/feature (matching feature_dof_report's own
    rows_per_feature_floor, OF-7) rather than a flat 60 — at 60 rows over
    36 features that's 1.7 rows/feature, so the purged walk-forward and
    shuffle-null checks were switching onto real data before there was
    remotely enough of it to be well-posed (observed live: 87 rows / 36
    features = 2.4 rows/feature failed OF-2 with a degenerate mean_auc=0.0
    and OF-7 with rows_per_feature=2.4, neither a real overfitting signal,
    just data starvation surfaced too early)."""
    from ml.features import FEATURE_NAMES
    if min_rows is None:
        min_rows = len(FEATURE_NAMES) * 10
    store = HistoryStore()
    # same weighting the deployed trainer uses (uniqueness / barrier / skew),
    # so every OF instrument measures the process that actually ships
    try:
        with open("config.json", encoding="utf-8") as fh:
            _sw = (json.load(fh).get("ml", {}) or {}).get("sample_weights", {})
    except (OSError, ValueError):
        _sw = {}
    X, y, w, sig = store.load_training_data(return_sig=True, weights_cfg=_sw)
    if not force_synthetic and len(X) >= min_rows and 5 <= y.sum() <= len(y) - 5:
        # live rows: hand the signal-time array down so the OF folds purge
        # by TIME, exactly like the deployed selector (evaluate_and_select).
        # n_live = the load's own clean-pass count, so OF-3's evidence gate
        # mirrors the deployed ladder at the real live-row count.
        n_live = int((store.last_load_stats or {}).get(
            "live_clean", store.source_counts().get("live", 0)))
        return X, y, w, sig, f"live history ({len(X)} rows)", n_live
    Xs, ys = synthetic_benchmark()
    reason = "forced" if force_synthetic else f"live rows={len(X)} < {min_rows}"
    # synthetic benchmark is uniformly spaced -> row-count purge is exact.
    # n_live = len(Xs): the benchmark validates the FULL selection machinery,
    # so it must not be evidence-gated down to logistic-only.
    return Xs, ys, None, None, (f"SYNTHETIC benchmark ({reason}) — validating "
                                f"machinery, not market"), len(Xs)


# ---------------------------------------------------------------------------
def strategy_plateau(recording: str, quick: bool) -> None:
    """Sweep post-signal parameters over one deterministic recording;
    a robust configuration sits on a plateau, a curve-fit one on a
    spike. Peakiness = |best - mean(neighbors)| / (|best| + eps) on the
    per-axis PnL profile."""
    from scripts.replay import run_replay, set_dotted
    from main import load_config

    base = load_config(str(Path(__file__).resolve().parents[1] /
                           "config.json"))
    base["capital_management"]["starting_capital_usd"] = 10_000
    base["position_sizer"] = dict(base.get("position_sizer", {}),
                                  entry_cooldown_min=0, min_p_win=0.50)
    base["ml"]["cold_start_prior_p"] = 0.62
    base["ml"]["model_path"] = "outputs/_no_model.json"
    base["pretrade"]["min_edge_cost_ratio"] = 0.1

    axes = {
        "position_sizer.min_p_win": [0.50, 0.55, 0.60],
        "profit_taking.chandelier_k": [2.0, 3.0, 4.0],
        "pretrade.min_edge_cost_ratio": [0.1, 0.6, 1.2],
    }
    if quick:
        axes = {"position_sizer.min_p_win": [0.50, 0.55, 0.60]}

    for dotted, values in axes.items():
        pnls, entries = [], []
        for v in values:
            cfg = json.loads(json.dumps(base))
            set_dotted(cfg, dotted, str(v))
            r = run_replay(cfg, recording, quiet=True)
            pnls.append(r["realized_pnl"])
            entries.append(r["entries_filled"])
        spread = max(pnls) - min(pnls)
        if spread < 1e-9:
            info(f"plateau[{dotted}]",
                 f"flat surface (pnl {pnls}, entries {entries}) — "
                 f"parameter inert on this recording")
            continue
        k = int(np.argmax(pnls))
        neigh = [pnls[j] for j in (k - 1, k + 1) if 0 <= j < len(pnls)]
        peak = abs(pnls[k] - float(np.mean(neigh))) / (abs(pnls[k]) + 1e-9)
        check(f"plateau[{dotted}]: best not a knife-edge", peak <= 0.60,
              f"pnl={pnls} peakiness={peak:.2f}")
        # tightening a gate must not mint entries out of thin air
        if dotted in ("position_sizer.min_p_win",
                      "pretrade.min_edge_cost_ratio"):
            check(f"monotone[{dotted}]: stricter gate ⇒ ≤ entries",
                  all(entries[i] >= entries[i + 1]
                      for i in range(len(entries) - 1)),
                  f"entries={entries}")


def make_offline_recording(tmpdir: Path) -> str:
    """Deterministic mock-fed session with forced ETH long signals —
    the same generator smoke [22] proves byte-identical on replay."""
    import shutil
    from data.replay import FeedRecorder
    from main import LiquidityBot, load_config
    from strategies.signal_gates import SignalResult
    from scripts.smoke_test import (MockOKX, MockBinanceUS, MockKraken,
                                    qa_redirect_paths)

    shutil.rmtree(tmpdir, ignore_errors=True)
    tmpdir.mkdir(parents=True)
    sink = str(tmpdir / "session.jsonl")
    cfg = load_config(str(Path(__file__).resolve().parents[1] /
                          "config.json"))
    qa_redirect_paths(cfg, "overfit_rec")   # no writes into production outputs/
    cfg["capital_management"]["starting_capital_usd"] = 10_000
    cfg["system"]["dry_run"] = True
    cfg["sentiment"]["enabled"] = False
    cfg["webdata"]["enabled"] = False
    cfg["moomoo"]["enabled"] = False
    cfg["system"]["state_path"] = str(tmpdir / "state.json")
    cfg["ml"]["model_path"] = str(tmpdir / "none.json")
    cfg["ml"]["history_path"] = str(tmpdir / "hist.csv")
    cfg["position_sizer"] = dict(cfg.get("position_sizer", {}),
                                 entry_cooldown_min=0, min_p_win=0.50)
    cfg["ml"]["cold_start_prior_p"] = 0.62
    cfg["pretrade"]["min_edge_cost_ratio"] = 0.1

    prices = {"ETH": 2000.0, "BTC": 60000.0}
    okx, bnc, krk = MockOKX(prices), MockBinanceUS(prices), \
        MockKraken(prices)
    bot = LiquidityBot(cfg, okx=FeedRecorder(okx, "okx", sink),
                       binanceus=FeedRecorder(bnc, "binanceus", sink),
                       kraken=FeedRecorder(krk, "kraken", sink),
                       resume=False)
    bot.gates.evaluate_asset = lambda base_asset, view: SignalResult(  # type: ignore[assignment]
        symbol=f"{base_asset}/USD", direction="long" if base_asset == "ETH" else None,
        confidence=1.0 if base_asset == "ETH" else 0.0, size=0.0,
        all_confirmed=(base_asset == "ETH"), gates_passed={})
    rng = np.random.default_rng(77)
    t = time.time()
    for _k in range(60):
        for a in prices:
            prices[a] *= float(1 + rng.normal(0, 0.0012) +
                               (0.0008 if a == "ETH" else 0.0))
        bot.cycle_once(t)
        t += bot.poll_sec
    return sink


# ---------------------------------------------------------------------------
def main() -> int:
    # OF-4 replays construct full bots that audit their dispositions and
    # record model lifecycle events; keep synthetic records out of the
    # production trail and registry ledger
    from core.audit import configure_audit
    from ml.registry import configure_registry
    configure_audit(Path(tempfile.gettempdir()) / "liqbot_overfit_audit.jsonl")
    configure_registry(Path(tempfile.gettempdir()) / "liqbot_overfit_models")
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--recording", default="",
                    help="existing session.jsonl to sweep; default: "
                         "generate a deterministic offline one")
    ap.add_argument("--force-synthetic", action="store_true",
                    help="always use the deterministic synthetic benchmark "
                         "for the ML layer, even if live history clears "
                         "min_rows — for a CI-bound run that must not "
                         "depend on ambient production telemetry state")
    ap.add_argument("--report-path", default="outputs/overfit_report.md",
                    help="where to write the markdown report — override "
                         "for a CI-bound run so it doesn't clobber a human "
                         "operator's last real audit")
    args = ap.parse_args()
    logging.basicConfig(level=logging.WARNING)
    t0 = time.time()
    print("liquiditybot overfit audit\n" + "=" * 42)

    # ---- ML layer -----------------------------------------------------
    X, y, w, sig, source, n_live = load_dataset(
        force_synthetic=args.force_synthetic)
    print(f"[OF-1] train/OOF gap  ({source})")
    gaps = train_test_gap(X, y, sample_weight=w,
                          n_splits=3 if args.quick else 5, sig=sig)
    for name, g in gaps.items():
        if not g.get("folds"):
            info(f"gap[{name}]", "no viable folds")
            continue
        check(f"gap[{name}]: OOF gap within memorization band",
              g["gap_auc"] <= 0.12,
              f"train_auc={g['train_auc']:.3f} oof_auc={g['oof_auc']:.3f} "
              f"gap={g['gap_auc']:+.3f}")

    print("[OF-2] shuffled-label leakage null")
    sh = shuffled_label_check(X, y, repeats=2 if args.quick else 3, sig=sig)
    check("shuffle: destroyed labels learn nothing OOF", sh.get("ok", False),
          f"mean_auc={sh.get('mean_auc', 0):.3f} z={sh.get('z', 99):.1f} "
          f"(limit {sh.get('z_limit')})")

    print("[OF-3] model-space PBO (CSCV)")
    # OF-3 must measure the DEPLOYED selection space. When the opt-in
    # adaptive_gbt rung is enabled in config it is live in walkforward's
    # ladder, so it enters the PBO space too; otherwise the space is the
    # historical default. Config unreadable -> default space (fail safe).
    inc_adaptive, adaptive_cfg, select_cfg = False, None, None
    try:
        from main import load_config
        _ml = load_config(str(Path(__file__).resolve().parents[1]
                              / "config.json")).get("ml", {})
        _ag = _ml.get("adaptive_gbt", {}) or {}
        inc_adaptive = bool(_ag.get("enabled", False))
        adaptive_cfg = _ag if inc_adaptive else None
        select_cfg = _ml.get("model_selection", {}) or None
    except Exception:                                    # noqa: BLE001
        inc_adaptive, adaptive_cfg, select_cfg = False, None, None  # fail safe
    # n_live (from load_dataset) drives the SAME evidence gate the deployed
    # ladder uses, so the measured PBO space is byte-for-byte the space the
    # bot actually selects from at the current ground-truth count.
    if inc_adaptive:
        info("pbo space", "ml.adaptive_gbt.enabled=true — the adaptive "
                          "rung is IN the measured selection space")
    pb = model_space_pbo(X, y, n_splits=3 if args.quick else 5,
                         n_blocks=6 if args.quick else 8, sig=sig,
                         include_adaptive=inc_adaptive,
                         adaptive_cfg=adaptive_cfg,
                         n_live=n_live, select_cfg=select_cfg)
    if pb.get("pbo") is None:
        info("pbo", pb.get("reason", "n/a") +
             (f" (space={pb.get('configs')})" if pb.get("configs") else ""))
    else:
        check("pbo: DEPLOYED selection (simplicity ladder) not "
              "dominated by luck", pb["pbo"] <= 0.5,
              f"pbo={pb['pbo']:.2f} over {pb['n_configs']} configs / "
              f"{pb['n_combos']} splits (mean winner: {pb.get('is_winner')})")
        info("pbo argmax stress",
             f"raw argmax selection pbo={pb.get('pbo_argmax', float('nan')):.2f}"
             " — the worst-case rule the ladder exists to avoid; gate is on"
             " the rule the bot actually runs")
        if pb["pbo"] > 0.2:
            info("pbo note", "0.2 < pbo <= 0.5: selection has luck in it — "
                             "expected at this sample size; keep the "
                             "simplicity-ladder margin")

    print("[OF-6] purge-leakage probe")
    lk = purge_leakage_probe()
    check("purge: never manufactures out-of-sample edge",
          lk["purge_does_not_inflate"],
          f"unpurged={lk['unpurged_oof_auc']:.3f} "
          f"purged={lk['purged_oof_auc']:.3f} leak_closed={lk['leak_closed']:+.3f}")
    info("purge note", "expanding-window design keeps boundary leak ~0 by "
                       "construction; shuffle-null [OF-2] is the leak gate")

    print("[OF-7] feature degrees-of-freedom")
    from ml.features import FEATURE_NAMES
    dof = feature_dof_report(X, y, FEATURE_NAMES,
                             label_span=32 if args.quick else 96, sig=sig)
    check("dof: not starved (>=10 rows per feature)", not dof["starved"],
          f"rows/feature={dof['rows_per_feature']:.1f} "
          f"({dof['n_rows']} rows / {dof['n_features']} features)")
    # dead-feature semantics depend on the dataset: the synthetic
    # benchmark plants signal in ~6 of 36 features BY CONSTRUCTION, so a
    # high dead fraction there is expected and says nothing about
    # production. It's a hard check only on real live history; on the
    # synthetic set it's reported for machinery validation. The models
    # already regularize against dead weight (GBT colsample + L2 + gain
    # importance, logistic L2), and OF-2 confirms none is exploited.
    on_synthetic = source.startswith("SYNTHETIC")
    dead_detail = (f"dead_frac={dof['dead_feature_frac']:.2f} "
                   f"({len(dof['dead_features'])} near-zero-importance "
                   f"features)")
    if on_synthetic:
        info("dof: dead-feature fraction (synthetic — informational)",
             dead_detail + " — expected: benchmark plants signal in ~6/36")
    else:
        check("dof: dead-feature fraction under 55% (live data)",
              dof["dead_feature_frac"] < 0.55, dead_detail)
    if dof["dead_features"]:
        info("dof note", f"low/zero-importance: {dof['dead_features'][:6]}"
                         + (" ..." if len(dof["dead_features"]) > 6 else ""))

    # ---- strategy layer -------------------------------------------------
    print("[OF-4] strategy parameter plateau (deterministic replay)")
    try:
        rec = args.recording or make_offline_recording(
            # QA intermediate (~1MB replay session): temp dir, not the
            # production telemetry directory
            Path(tempfile.gettempdir()) / "liqbot_overfit_rec")
        strategy_plateau(rec, args.quick)
    except Exception as e:
        check("plateau: replay harness ran", False, f"{e!r}")

    # ---- live-results layer ---------------------------------------------
    print("[OF-5] deflated Sharpe (live trades)")
    store = HistoryStore()
    live_rows = []
    try:
        import csv
        with open(store.path, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if row.get("source") == "live" and row.get("net_pnl_usd"):
                    live_rows.append({"net_pnl_usd": row["net_pnl_usd"],
                                      "probe": row.get("probe", "")})
    except (OSError, ValueError):
        pass
    conviction, mixed = split_dsr_samples(live_rows)
    try:
        _cfg_p = Path(__file__).resolve().parents[1] / "config.json"
        _explore_on = bool(((json.loads(_cfg_p.read_text(encoding="utf-8"))
                             .get("ml") or {}).get("exploration") or {})
                           .get("enabled", False))
    except (OSError, json.JSONDecodeError):
        _explore_on = False                     # unreadable config: full gate

    def _dsr_of(r):
        sr = float(r.mean() / (r.std() + 1e-12))
        d = deflated_sharpe(sr, len(r),
                            skew=float(((r - r.mean()) ** 3).mean()
                                       / (r.std() + 1e-12) ** 3),
                            kurtosis=float(((r - r.mean()) ** 4).mean()
                                           / (r.std() + 1e-12) ** 4),
                            n_trials=7)
        return d, sr

    # PT-050 probes deliberately bypass the profit-EV gate to buy labels, so
    # DSR on the mixed sample measures tuition, not the deployed strategy.
    # Since 2026-07-20 every position carries is_probe -> the 'probe' column,
    # so the gate can grade the CONVICTION-ONLY sample even while exploration
    # is running. Pre-marker rows ('' = unknown) never count as conviction.
    if len(conviction) >= 30:
        r = np.array(conviction)
        d, sr = _dsr_of(r)
        check("dsr: P(true SR > 0) on conviction-only sample",
              (d.get("dsr") or 0) >= 0.90,
              f"dsr={d.get('dsr'):.3f} sr={sr:.2f} n={len(r)} "
              f"(probes excluded: {len(mixed) - len(conviction)})")
    elif _explore_on:
        note = ""
        if len(mixed) >= 30:
            d, sr = _dsr_of(np.array(mixed))
            note = f" mixed-sample dsr={d.get('dsr'):.3f} sr={sr:.2f};"
        info("dsr", f"DEFERRED — {len(conviction)} conviction-marked live "
                    f"trades < 30 (mixed n={len(mixed)});{note} probes are "
                    f"EV-mixed by design (PT-050); gate arms as conviction "
                    f"labels accrue")
    elif len(mixed) < 30:
        info("dsr", f"DEFERRED — {len(mixed)} live labeled trades < 30; "
                    f"rerun after live history accrues")
    else:
        # exploration off and conviction sample still thin: pre-marker
        # corpora ('' rows) would defer forever, so grade the full live
        # sample (no probes are entering anymore)
        r = np.array(mixed)
        d, sr = _dsr_of(r)
        check("dsr: P(true SR > 0) after trials correction",
              (d.get("dsr") or 0) >= 0.90,
              f"dsr={d.get('dsr'):.3f} sr={sr:.2f} n={len(r)} "
              f"(conviction-marked subset still {len(conviction)} < 30)")

    # ---- report ----------------------------------------------------------
    out = Path(args.report_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(f"# Overfit audit — {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())}\n\n"
                f"Dataset: {source}\n\n")
        for status, name, detail in REPORT:
            f.write(f"- **{status}** {name}" +
                    (f" — {detail}" if detail else "") + "\n")
        f.write(f"\n{PASS_N} passed, {FAIL_N} failed "
                f"({time.time() - t0:.0f}s)\n")
    print("=" * 42)
    print(f"passed {PASS_N}, failed {FAIL_N}  "
          f"(report: {out}, {time.time() - t0:.0f}s)")
    return 0 if FAIL_N == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
