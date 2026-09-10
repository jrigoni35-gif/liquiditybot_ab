"""
scripts/regime_chain_report.py — surface the Markov chain the regime engine
already fits and then discards (SAFE class, report-only).

WHAT THIS IS. `regime/macro_regime.py` fits a Hamilton (1989) Markov
regime-switching model — a diagonal-covariance Gaussian HMM, scaled
Baum-Welch EM — on every macro update. The E-step accumulates `xi_sum` and
the M-step writes `GaussianHMM.A`, the K x K TRANSITION MATRIX. That matrix
is the Markov chain. Nothing reads it: `MacroRegimeState` carries
`state_probs` (the posterior over states at the LAST bar) and a label, so the
chain's persistence structure — how long a regime lasts, how likely it is to
end, where the asset lives in the long run — is computed daily and thrown
away. Those three quantities are otherwise eyeballed off a chart. This report
reads them off the fitted chain instead.

CLASSIFICATION — SAFE AS SHIPPED.
Report-only. It places no order, changes no size, moves no stop, books no fee
and touches no fill. It IMPORTS the decision module `regime.macro_regime` in
the read direction only, to reuse the deployed estimator — importing it the
other way (this script into a decision path) or wiring any number below into
sizing, entry decisioning or geometry is COHORT-RESETTING under the era-9
moratorium and forbidden without operator adjudication.

It deliberately introduces NO new model family, feature or meta-label: it
constructs the SAME feature matrix `update()` builds and fits the SAME
`GaussianHMM` class with the SAME configured `n_states`, so what it reports is
the deployed chain, not a second opinion about it. That is what keeps it
outside the 2026-08-10 model-investment freeze.

WHAT IT CANNOT SEE, stated up front.
  * It re-fits OFFLINE from the candle store; the live engine fits from
    whatever `main.py` last handed `update()`. Same estimator and same feature
    construction, but not necessarily the same bars — the report states the
    exact inclusive window and bar count it used, per asset.
  * Baum-Welch is a local optimum. `GaussianHMM` takes the best of
    `restarts` seeded fits (default 3, seed 7). The fit is deterministic for a
    fixed corpus and seed; it is NOT stable against an arbitrary corpus change.
  * `A` is estimated, not known. With a few hundred daily bars the diagonal is
    far better determined than the off-diagonal. Dwell times are reported with
    the bar count that produced them so a reader can deflate them; no CI is
    computed and none is implied.
  * Bars the venue has CONTRADICTED (`Bar.conflicted`) are excluded and
    counted separately — a contradicted bar is not one a statistic may quietly
    consume (data/candle_journal.py).

USAGE
    python scripts/regime_chain_report.py            # human-readable
    python scripts/regime_chain_report.py --json     # machine-readable
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import os
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from data import candle_journal as cj                      # noqa: E402
from regime.macro_regime import (EPS, GaussianHMM,          # noqa: E402
                                 parkinson_vol)

log = logging.getLogger("liquiditybot.scripts.regime_chain")

DAILY_S = 86_400

# The report's own default lane. Kraken is the sole execution venue
# (CLAUDE.md invariant 3), so kraken/USD is the lane the bot's own regimes
# are formed on. Never defaulted inside the store itself, so it is named here.
DEFAULT_SOURCE = "kraken"
DEFAULT_QUOTE = "USD"

# Horizons the "will this regime still hold" line is reported at, in days.
DWELL_HORIZONS_D = (1, 5, 21)

# Minimum usable bars. GaussianHMM.fit itself refuses < 8*K; the macro engine
# additionally gates on config regime.min_bars. Below that a fit is not a
# reading, and this report says UNKNOWN rather than printing a number.
ABSOLUTE_MIN_BARS = 60

# A daily lane that is not being APPENDED is a frozen snapshot, and a frozen
# snapshot will happily answer "what regime are we in NOW" forever.
#
# Measured 2026-09-09T22:58Z, kraken/USD, all four traded assets: the 86400s
# lane's last bar is 2026-08-28 (13.0 d old) and holds EXACTLY 720 bars; the
# 3600s lane's last bar is 2026-08-29 and also holds EXACTLY 720; the 300s
# lane was current to within 2.1 d. 720 is Kraken's OHLC page limit, so the
# daily and hourly lanes are one-shot backfills that nothing appends to,
# while the 5m lane is live. Re-derive before trusting this comment:
#   python -c "import time;from data import candle_journal as cj;
#   s=cj.Series(source='kraken',quote='USD');n=int(time.time());
#   b=cj.bars('ETH',86400,0,n,series=s);print(len(b),max(x.t_open_s for x in b))"
#
# Consequence for THIS report: the fitted chain is still a valid description
# of its window, so the transition matrix, dwell times and steady state stay
# readable. The one claim that becomes false is the CURRENT-state line, which
# names a regime "now" from the last bar in the corpus. Past this threshold
# that line is withheld rather than qualified — a stale current-regime claim
# is exactly the confident-instrument failure this repo keeps re-buying.
STALE_AFTER_DAYS = 3.0


def _load_config() -> dict:
    """Read config.json if present. Absent keys fall back to the same
    defaults regime/macro_regime.py uses, so the report tracks the engine."""
    path = REPO_ROOT / "config.json"
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def _universe(cfg: dict) -> list[str]:
    """Base assets to report on, in config order, de-duplicated.

    The traded universe is `exchanges.kraken.trading_pairs` (Kraken is the
    sole execution venue, CLAUDE.md invariant 3). Pairs are stored as
    "ETH/USD"; the candle store keys on the BASE symbol, so the base is split
    off here. Fallback keys are kept because a caller may pass a config shape
    from an older era, but the shipped key is the first one checked.
    """
    def _bases(pairs: Any) -> list[str]:
        out: list[str] = []
        seen: set[str] = set()
        if not isinstance(pairs, list):
            return out
        for p in pairs:
            s = str(p).upper().strip()
            if not s:
                continue
            base = s.split("/", 1)[0].strip()
            if base and base not in seen:
                seen.add(base)
                out.append(base)
        return out

    ex = cfg.get("exchanges")
    if isinstance(ex, dict):
        kr = ex.get("kraken")
        if isinstance(kr, dict):
            found = _bases(kr.get("trading_pairs"))
            if found:
                return found
    for key in ("assets", "universe", "symbols"):
        found = _bases(cfg.get(key))
        if found:
            return found
    trading = cfg.get("trading")
    if isinstance(trading, dict):
        found = _bases(trading.get("assets"))
        if found:
            return found
    return []


def _steady_state(A: np.ndarray) -> np.ndarray | None:
    """Left eigenvector of A for eigenvalue 1, normalised to a distribution.

    Returns None when the chain has no usable stationary distribution (a
    numerically defective A). None is an EXPLICIT UNKNOWN and is rendered as
    such; it is never silently replaced by a uniform prior, which would read
    as 'this asset spends equal time in every regime' — a claim about the
    world made from a failure of the solver.
    """
    try:
        vals, vecs = np.linalg.eig(A.T)
    except np.linalg.LinAlgError:
        return None
    idx = int(np.argmin(np.abs(vals - 1.0)))
    if abs(vals[idx] - 1.0) > 1e-6:
        return None
    v = np.real(vecs[:, idx])
    # An eigenvector is defined up to sign; orient it positive before testing.
    if v.sum() < 0:
        v = -v
    if np.any(v < -1e-9):
        return None
    v = np.clip(v, 0.0, None)
    total = float(v.sum())
    if not math.isfinite(total) or total <= EPS:
        return None
    return v / total


def _semantic_order(hmm: GaussianHMM, n_states: int) -> dict[int, str]:
    """Reproduce macro_regime.update()'s relabelling EXACTLY.

    update() sorts states by mean return (low -> high), names the lowest
    'bear' and the highest 'bull', and leaves everything between as 'range'.
    Any divergence here would mean this report labels a different chain than
    the one the engine acts on, so it is copied, not re-derived.
    """
    order = np.argsort(hmm.state_return_means())
    sem: dict[int, str] = {int(order[0]): "bear", int(order[-1]): "bull"}
    for k in range(n_states):
        sem.setdefault(k, "range")
    return sem


def _fetch_daily(symbol: str, source: str, quote: str,
                 root: Path | str | None = None) -> tuple[list, int, str]:
    """Return (usable_bars, n_conflicted_dropped, status).

    Reads the whole stored history: an onset/persistence statistic must not be
    computed from a sampled tail.
    """
    series = cj.Series(source=source, quote=quote)
    t1 = int(time.time())
    t0 = 0  # full-range: the store bounds itself
    try:
        raw = cj.bars(symbol, DAILY_S, t0, t1, series=series, root=root)
    except cj.CandleStoreUnreadable as exc:
        return [], 0, f"store-unreadable: {exc}"
    except (cj.CandleLaneError, ValueError, KeyError, OSError) as exc:
        return [], 0, f"unavailable: {type(exc).__name__}: {exc}"
    if not raw:
        return [], 0, "no-bars-in-lane"
    usable = [b for b in raw if not getattr(b, "conflicted", False)]
    dropped = len(raw) - len(usable)
    usable.sort(key=lambda b: b.t_open_s)
    return usable, dropped, "ok"


def _by_label(labels: list[str], values: list[float]) -> dict[str, float]:
    """Aggregate per-state values onto their semantic labels by SUM.

    Several states can share a label (everything between the extremes is
    "range"), so keying a dict on the label without summing silently discards
    every duplicate but one.
    """
    out: dict[str, float] = {lab: 0.0 for lab in dict.fromkeys(labels)}
    # strict: one value per state, always — a length mismatch here would mean
    # the caller paired a relabelling with the wrong transition row.
    for lab, v in zip(labels, values, strict=True):
        out[lab] += float(v)
    return {k: round(v, 6) for k, v in out.items()}


def _longest_contiguous_run(bars: list) -> tuple[list, int, list[str] | None]:
    """Longest run of consecutive daily slots, the gap count, and its window.

    `data/candle_journal.bars()` yields no Bar at all for a slot the store
    never received, and `_fetch_daily` drops venue-contradicted bars on top of
    that — so a returned list is not necessarily contiguous. Differencing
    across a hole books a multi-day move as a single daily return, which
    inflates that state's variance and, because the diagonal of A is estimated
    from exactly those transitions, distorts the dwell time this report
    exists to publish. Taking the longest clean run keeps the returns
    honest-by-construction and makes "days" and "bars" the same unit again.
    """
    if not bars:
        return [], 0, None
    runs: list[list] = [[bars[0]]]
    gaps = 0
    # strict=False is deliberate: this is an offset pairwise walk, so the two
    # sequences differ in length by exactly one by construction.
    for prev, cur in zip(bars, bars[1:], strict=False):
        if cur.t_open_s - prev.t_open_s == DAILY_S:
            runs[-1].append(cur)
        else:
            gaps += 1
            runs.append([cur])
    best = max(runs, key=len)
    span = [time.strftime("%Y-%m-%d", time.gmtime(best[0].t_open_s)),
            time.strftime("%Y-%m-%d", time.gmtime(best[-1].t_open_s))]
    return best, gaps, span


def analyse_asset(symbol: str, cfg: dict, *, source: str, quote: str,
                  root: Path | str | None = None) -> dict[str, Any]:
    """Fit the deployed chain for one asset and read its structure off."""
    reg = cfg.get("regime", {}) if isinstance(cfg.get("regime"), dict) else {}
    n_states = int(reg.get("hmm_states", 3))
    # The engine's key is `min_daily_bars` (regime/macro_regime.py:288,
    # default 120) — NOT `min_bars`. An adversarial review on 2026-09-09
    # caught this file reading `min_bars`, a key that exists nowhere in
    # config.json, so `.get()` returned 0 and the floor silently collapsed to
    # ABSOLUTE_MIN_BARS=60. The report would then fit and publish a chain for
    # an asset the deployed engine refuses to fit at all. Read the same key
    # the engine reads, with the same default.
    min_bars = max(int(reg.get("min_daily_bars", 120)),
                   ABSOLUTE_MIN_BARS, 8 * n_states)

    out: dict[str, Any] = {
        "asset": symbol, "lane": f"{source}/{quote}", "n_states": n_states,
        "fitted": False, "status": "unknown",
    }

    bars, dropped, status = _fetch_daily(symbol, source, quote, root)
    out["bars_conflicted_dropped"] = dropped
    if status != "ok":
        out["status"] = status
        return out

    # CONTIGUITY. `bars()` returns NO Bar for a slot the store never got, and
    # this function additionally DROPS venue-contradicted bars — so the list
    # can contain gaps. np.diff over a gap silently books a multi-day move as
    # one daily return and feeds it to the HMM as if it were one. Keep only
    # the longest run of consecutive daily slots; report what that cost.
    bars, gaps, kept_span = _longest_contiguous_run(bars)
    out["gaps_detected"] = gaps
    out["bars_after_contiguity"] = len(bars)
    if kept_span is not None:
        out["contiguous_window_utc"] = kept_span

    if len(bars) < min_bars:
        out["status"] = (f"insufficient-contiguous-bars: {len(bars)} < "
                         f"{min_bars} (gaps={gaps})")
        out["bars_used"] = len(bars)
        return out

    closes = np.array([b.close for b in bars], dtype=float)
    highs = np.array([b.high for b in bars], dtype=float)
    lows = np.array([b.low for b in bars], dtype=float)
    if not (np.all(np.isfinite(closes)) and np.all(np.isfinite(highs))
            and np.all(np.isfinite(lows))):
        out["status"] = "non-finite-ohlc"
        return out
    if np.any(closes <= 0.0) or np.any(highs <= 0.0) or np.any(lows <= 0.0):
        out["status"] = "non-positive-price"
        return out
    if np.any(highs < lows):
        out["status"] = "inverted-high-low"
        return out

    # Feature construction copied from MacroRegimeEngine.update() so the
    # chain reported is the chain deployed.
    rets = np.diff(np.log(np.maximum(closes, EPS)))
    pvol = parkinson_vol(highs, lows)[1:]

    # DEGENERACY. A stuck feed writing one price forever still fits: `rets`
    # is all-zero, `log(pvol + EPS)` is a finite constant (log 1e-9), and
    # GaussianHMM.fit returns True with a finite A. The report would then
    # publish dwell times and a steady state for a chain fitted to nothing.
    # "Zero is not a reading" — refuse, rather than describe the artefact.
    if float(np.std(rets)) <= EPS or float(np.std(pvol)) <= EPS:
        out["status"] = "degenerate-corpus: zero variance in returns or range"
        out["bars_used"] = len(bars)
        return out

    X = np.column_stack([rets, np.log(pvol + EPS)])

    hmm = GaussianHMM(n_states=n_states)
    if not hmm.fit(X):
        out["status"] = "fit-refused"
        out["bars_used"] = len(bars)
        return out

    assert hmm.A is not None
    A = np.asarray(hmm.A, dtype=float)
    sem = _semantic_order(hmm, n_states)
    labels = [sem[k] for k in range(n_states)]

    gamma = hmm.posteriors(X)
    path = np.argmax(gamma, axis=1)          # posterior-marginal decode, as deployed
    realized = {lab: 0.0 for lab in dict.fromkeys(labels)}
    for k in range(n_states):
        realized[labels[k]] += float((path == k).mean())

    steady = _steady_state(A)
    steady_by_label: dict[str, float] | None = None
    if steady is not None:
        steady_by_label = {lab: 0.0 for lab in dict.fromkeys(labels)}
        for k in range(n_states):
            steady_by_label[labels[k]] += float(steady[k])

    per_state = []
    for k in range(n_states):
        p_stay = float(np.clip(A[k, k], 0.0, 1.0))
        # Expected dwell of a geometric holding time, in BARS. It is
        # reported in days only because `_longest_contiguous_run` has already
        # guaranteed every bar is one consecutive 86400s slot — without that
        # guarantee "bars" and "days" diverge exactly when the corpus is
        # gappiest, i.e. when the number matters most. p_stay is clipped to
        # 1e-6..1-1e-6 by the M-step, so the divisor cannot be 0.
        dwell = (1.0 / (1.0 - p_stay)) if (1.0 - p_stay) > EPS else float("inf")
        per_state.append({
            "state": k,
            "label": labels[k],
            "p_stay_1d": round(p_stay, 6),
            "expected_dwell_days": (round(dwell, 2)
                                    if math.isfinite(dwell) else None),
            "p_leave_within": {
                f"{h}d": round(1.0 - p_stay ** h, 6) for h in DWELL_HORIZONS_D
            },
            "mean_daily_return": round(float(hmm.state_return_means()[k]), 6),
            # SUM over states sharing a semantic label, never overwrite. With
            # n_states >= 4 the relabelling names only the argmin/argmax
            # ("bear"/"bull") and calls every middle state "range", so a dict
            # comprehension keyed on the label silently kept ONE of them and
            # dropped the rest — the row then no longer summed to 1 and the
            # discarded mass was invisible. Summing is the only reading that
            # preserves "probability of moving to a state with this label".
            "transitions_to": _by_label(labels, [float(A[k, j])
                                                 for j in range(n_states)]),
        })

    cur = gamma[-1]
    cur_state = int(np.argmax(cur))
    last_t = int(bars[-1].t_open_s)
    # Age from the bar's CLOSE, not its open. A Bar covers
    # [t_open_s, t_open_s + interval_s) and its close is the price as of the
    # END of that window, so the open is a full interval older than the
    # reading actually is. Measuring from the open made a perfectly healthy
    # daily lane read 1-2 days stale against a 3-day threshold, leaving about
    # one day of slack before a false STALE — the threshold would have been
    # doing something other than what it says.
    last_close_s = last_t + DAILY_S
    age_days = max(0.0, (time.time() - last_close_s) / 86_400.0)
    stale = age_days > STALE_AFTER_DAYS
    out.update({
        "fitted": True,
        "status": "ok",
        "bars_used": len(bars),
        "last_bar_utc": time.strftime("%Y-%m-%d", time.gmtime(last_t)),
        "data_age_days": round(age_days, 2),
        "stale": stale,
        "window_utc_inclusive": [
            time.strftime("%Y-%m-%d", time.gmtime(bars[0].t_open_s)),
            time.strftime("%Y-%m-%d", time.gmtime(last_t)),
        ],
        "loglik": round(float(hmm.loglik_), 3),
        "labels": labels,
        "transition_matrix": [[round(float(A[i, j]), 6)
                               for j in range(n_states)]
                              for i in range(n_states)],
        "per_state": per_state,
        "steady_state": (None if steady_by_label is None
                         else {k: round(v, 6) for k, v in steady_by_label.items()}),
        "realized_occupancy": {k: round(v, 6) for k, v in realized.items()},
        # A current-regime claim is only as current as its last bar. Past the
        # staleness threshold these are None, not a qualified number: a reader
        # skimming JSON takes a present value at face value.
        "current_state": None if stale else labels[cur_state],
        "current_state_prob": None if stale else round(float(cur[cur_state]), 6),
        "current_expected_dwell_days": (
            None if stale else per_state[cur_state]["expected_dwell_days"]),
        "as_of_state": labels[cur_state],
        "as_of_state_prob": round(float(cur[cur_state]), 6),
    })
    return out


def build_report(*, source: str = DEFAULT_SOURCE, quote: str = DEFAULT_QUOTE,
                 root: Path | str | None = None,
                 assets: list[str] | None = None) -> dict[str, Any]:
    cfg = _load_config()
    universe = assets if assets else _universe(cfg)
    read_at = time.time()
    rows = [analyse_asset(a, cfg, source=source, quote=quote, root=root)
            for a in universe]
    fitted = [r for r in rows if r.get("fitted")]
    stale = [r for r in fitted if r.get("stale")]
    return {
        "report": "regime_chain",
        "classification": "SAFE — report-only; reads the deployed HMM, wires nothing",
        "read_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(read_at)),
        "lane": f"{source}/{quote}",
        "assets_requested": len(universe),
        "assets_fitted": len(fitted),
        "assets_stale": len(stale),
        "stale_after_days": STALE_AFTER_DAYS,
        "staleness_warning": (
            None if not stale else
            f"{len(stale)}/{len(fitted)} fitted asset(s) sit on a daily lane older "
            f"than {STALE_AFTER_DAYS}d; no current-regime claim is made for them. "
            "The fitted chain still describes its own window."),
        "decode": "posterior-marginal argmax (as deployed) — NOT Viterbi",
        "caveat": ("A is estimated, not known: the diagonal is far better "
                   "determined than the off-diagonal at these bar counts. No CI "
                   "is computed and none is implied — read bars_used."),
        "assets": rows,
    }


def _fmt_pct(x: float | None) -> str:
    return "  n/a" if x is None else f"{100.0 * x:5.1f}%"


def render(rep: dict[str, Any]) -> str:
    lines: list[str] = []
    add = lines.append
    add("=" * 72)
    add("REGIME MARKOV CHAIN — the transition matrix the engine fits and discards")
    add("=" * 72)
    add(f"read_at   : {rep['read_at_utc']}   lane: {rep['lane']}")
    add(f"fitted    : {rep['assets_fitted']}/{rep['assets_requested']} assets")
    add(f"decode    : {rep['decode']}")
    if rep.get("staleness_warning"):
        add("")
        add(f"!! {rep['staleness_warning']}")
    add("")

    if rep["assets_fitted"] == 0:
        add("NO ASSET FITTED. This is a statement about the corpus or the lane,")
        add("not about the market. Per-asset status:")
        for r in rep["assets"]:
            add(f"  {r['asset']:<8} {r.get('status')}")
        add("")
        add(rep["caveat"])
        return "\n".join(lines)

    for r in rep["assets"]:
        if not r.get("fitted"):
            add(f"{r['asset']:<8} UNREAD — {r.get('status')}")
            continue
        w = r["window_utc_inclusive"]
        add(f"{r['asset']}  [{w[0]} .. {w[1]} inclusive, {r['bars_used']} daily bars]")
        if r.get("bars_conflicted_dropped"):
            add(f"    {r['bars_conflicted_dropped']} venue-contradicted bar(s) excluded")
        if r.get("stale"):
            add(f"    NO CURRENT-STATE CLAIM — daily lane is "
                f"{r['data_age_days']:.1f}d stale (last bar {r['last_bar_utc']}). "
                f"As of that bar the HMM vote was {r['as_of_state']} "
                f"(p={r['as_of_state_prob']:.3f}).")
        else:
            add(f"    HMM vote: {r['current_state']} "
                f"(p={r['current_state_prob']:.3f}); this state's expected "
                f"dwell is {r['current_expected_dwell_days']} bars")
        add("    NOT the bot's regime: the engine layers a TSMOM ensemble and "
            "hysteresis on this vote (macro_regime.py `_ensemble_label` then "
            "N confirmations) — read `st.label` for what the playbook uses.")
        add("")
        add("    transition matrix P(row -> col), per day")
        hdr = "".join(f"{lab:>9}" for lab in r["labels"])
        add(f"      {'from/to':<10}{hdr}")
        for i, row in enumerate(r["transition_matrix"]):
            cells = "".join(f"{v * 100:8.1f}%" for v in row)
            add(f"      {r['labels'][i]:<10}{cells}")
        add("")
        add("    persistence")
        for ps in r["per_state"]:
            dw = ("never leaves" if ps["expected_dwell_days"] is None
                  else f"{ps['expected_dwell_days']:>6.2f}d")
            leave = "  ".join(f"{h}:{_fmt_pct(v)}"
                              for h, v in ps["p_leave_within"].items())
            add(f"      {ps['label']:<8} dwell {dw}   P(leave within) {leave}")
        add("")
        ss = r["steady_state"]
        add("    long-run vs realized occupancy")
        if ss is None:
            add("      steady state UNKNOWN (chain has no usable stationary "
                "distribution)")
        else:
            for lab in dict.fromkeys(r["labels"]):
                add(f"      {lab:<8} chain-implied {_fmt_pct(ss.get(lab))}"
                    f"   realized {_fmt_pct(r['realized_occupancy'].get(lab))}")
            add("      (a wide gap is a statement about the FIT, not the market —"
                " verify the instrument first)")
        add("")
    add(rep["caveat"])
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Report the fitted macro-regime Markov chain (SAFE, report-only)")
    ap.add_argument("--json", action="store_true", help="emit JSON")
    ap.add_argument("--source", default=DEFAULT_SOURCE)
    ap.add_argument("--quote", default=DEFAULT_QUOTE)
    ap.add_argument("--asset", action="append", default=None,
                    help="restrict to this asset (repeatable)")
    ap.add_argument("--out", default=None,
                    help=("output STEM (not a path with an extension): '.json' "
                          "and '.txt' are appended. Must resolve inside the "
                          "outputs directory."))
    args = ap.parse_args(argv)

    rep = build_report(source=args.source, quote=args.quote,
                       assets=[a.upper() for a in args.asset] if args.asset else None)

    text = json.dumps(rep, indent=2) if args.json else render(rep)
    print(text)

    # Persist alongside the other daily lenses. Never a module-level path.
    try:
        out_dir = Path(os.environ.get("LIQUIDITYBOT_OUTPUTS",
                                      str(REPO_ROOT / "outputs"))).resolve()
        out_dir.mkdir(parents=True, exist_ok=True)
        stem = Path(args.out).resolve() if args.out else (out_dir /
                                                          "regime_chain_report")
        # CONTAINMENT. `--out` is a stem that gets ".json"/".txt" appended and
        # is opened for write with no existence check, so an unconstrained
        # value silently clobbers whatever it names — `--out ../config` would
        # have written config.json. Refuse anything resolving outside the
        # outputs directory rather than trusting the caller.
        if out_dir not in stem.parents:
            log.error("refusing --out outside %s: %s", out_dir, stem)
            return 2
        stem.parent.mkdir(parents=True, exist_ok=True)
        with open(f"{stem}.json", "w", encoding="utf-8") as fh:
            json.dump(rep, fh, indent=2)
        with open(f"{stem}.txt", "w", encoding="utf-8", newline="\n") as fh:
            fh.write(render(rep) + "\n")
    except OSError as exc:
        log.warning("regime chain report not persisted: %s", exc)
        return 1

    # EXIT CODE IS THE ONLY THING THE SCHEDULER READS. Returning 0 whatever
    # happened means an empty store, a wrong lane name, or a universe that
    # resolved to nothing all report SUCCESS to learning_panel and to Task
    # Scheduler — the silent-degradation shape this repo keeps paying for.
    if rep["assets_requested"] == 0:
        log.error("no assets resolved from config; nothing was measured")
        return 1
    if rep["assets_fitted"] == 0:
        log.error("0/%d assets fitted; the report describes the corpus, "
                  "not the market", rep["assets_requested"])
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
