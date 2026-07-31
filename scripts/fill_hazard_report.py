"""scripts/fill_hazard_report.py — L1 maker-fill hazard time-consistency.

TANK quant-2 / Debate-1 item L1 (REPORT-ONLY, never gates, no engine
change). The dry-run sim fills a resting maker order with a CONSTANT
per-poll probability p = passive_base_prob * exp(-dist/sigma)
(execution/order_manager.py `_poll_dry`) — a geometric / memoryless
time-to-fill. The queue-reactive literature (Cont-Stoikov-Talreja 2010;
Huang-Lehalle-Rosenbaum 2015) predicts a DECREASING hazard with queue
age instead. If the constant-hazard shape misstates cumulative fill
probability at the order-timeout horizon by more than
``REL_MISSTATE_MAX`` relative, the L2 label-geometry change (+ 200x1200
re-baseline) stays justified; otherwise L2 should be closed.

Method (book-frame synthesis mode): recordings carry NO order events and
NO trade prints (the kraken feed records get_order_book snapshots only),
so resting-maker episodes are SYNTHESIZED: a hypothetical maker order is
placed at each strided book frame at ``dist`` bps from mid, and its
time-to-first-fill-opportunity is the first later poll whose opposite
best quote reaches at-or-through the resting price (the same
trade-through proxy scripts/calibrate_fills.py uses for level
calibration). Episodes are censored at tape end / order life. Per poll
age t the discrete hazard h(t) = d_t / n_t is fitted with per-bin Wilson
CIs and a Greenwood-style survival CI, and compared against the
best-fit CONSTANT hazard via a likelihood-ratio test and the KS distance
between the two cumulative fill curves. The verdict uses the BEST-FIT
constant (not the configured level) so it isolates the SHAPE question —
the level is calibrate_fills.py's job; the configured sim probability is
reported alongside for context.

Report-only and standalone: reads config.json for the sim knobs
(order_manager.sim_fill.*, order_manager.order_timeout_sec,
system.polling_interval_sec — never hardcoded), writes a markdown
report, exits 0 always, needs no operator input. With no recordings it
writes an INSUFFICIENT_EVIDENCE report and still exits 0.

    .venv/bin/python scripts/fill_hazard_report.py
"""

import argparse
import logging
import math
import sys
import time
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.codes import Code  # noqa: E402
from core.fill_calibration import D_MAX_DEFAULT, wilson_interval  # noqa: E402
from core.replay_gate import discover_recordings  # noqa: E402
from scripts.calibrate_fills import (  # noqa: E402
    DEFAULT_DIST_GRID_BPS,
    estimate_sigma_bps,
    extract_frames,
)

log = logging.getLogger("fill_hazard_report")

# L1 program threshold (Debate-1): relative misstatement of cumulative
# fill probability at the order-timeout horizon above which the
# constant-hazard sim is declared shape-inconsistent (YES -> L2 stays).
REL_MISSTATE_MAX = 0.10
ALPHA = 0.05                # LR-test significance required to assert YES
MIN_EPISODES = 80           # power floor (mirrors fill_calibration N_MIN)
E_MIN = 10                  # minimum observed hits (stable-proportion floor)
MIN_AT_RISK = 20            # a poll bin with fewer at-risk is unresolved
MIN_RESOLVED_BINS = 2       # a SHAPE needs >= 2 resolved bins
DEFAULT_OUT = Path("docs/quant/2026-07-31_fill_hazard_l1.md")


@dataclass(frozen=True)
class Episode:
    """One synthesized resting-maker episode.

    ``duration`` = polls at risk (>= 1); ``event`` True means the level
    was hit (opposite best quote at-or-through the resting price) at poll
    ``duration``, False means censored after ``duration`` polls.
    """
    duration: int
    event: bool


@dataclass(frozen=True)
class HazardFit:
    """Discrete life-table fit: index 0 corresponds to poll age t=1."""
    t_max: int
    n: tuple[int, ...]          # at-risk per poll age
    d: tuple[int, ...]          # first-hits per poll age
    h: tuple[float, ...]        # raw hazard d/n (MLE)
    h_lo: tuple[float, ...]     # per-bin Wilson 95% lower
    h_hi: tuple[float, ...]     # per-bin Wilson 95% upper
    surv: tuple[float, ...]     # Kaplan-Meier survival S(t)
    surv_se: tuple[float, ...]  # Greenwood standard error of S(t)
    episodes: int
    events: int
    exposure: int               # total at-risk poll count


def _clean(fr: dict) -> tuple[float, float, float] | None:
    """(mid, bid, ask) for a sane frame, else None."""
    try:
        bid, ask = float(fr.get("bid", 0.0)), float(fr.get("ask", 0.0))
    except (TypeError, ValueError):
        return None
    if not (math.isfinite(bid) and math.isfinite(ask)):
        return None
    if bid <= 0.0 or ask <= 0.0 or ask < bid:
        return None
    return (0.5 * (bid + ask), bid, ask)


def episodes_from_frames(frames: list, life_polls: int, dist_bps: float,
                         sides: tuple = ("buy", "sell")) -> list[Episode]:
    """Synthesize resting-maker episodes from book frames.

    A placement at frame i rests a buy limit at mid*(1 - dist) and/or a
    sell limit at mid*(1 + dist); observation polls are the next
    ``life_polls`` frames. A buy episode is hit at age t when the ask at
    frame i+t trades at-or-through the level; sell symmetrically on the
    bid. First hit ends the episode; a broken frame or tape end censors
    it at the last valid poll. Placements stride by life_polls + 1 so
    windows are fully DISJOINT (no shared boundary frame): overlapping
    windows are autocorrelated and would overstate the at-risk counts,
    and a window's last dip must not contaminate the next placement mid.
    """
    life = max(int(life_polls), 1)
    dist = max(float(dist_bps), 0.0)
    cleaned = [_clean(fr) for fr in frames]
    out: list[Episode] = []
    for i in range(0, len(cleaned) - 1, life + 1):
        here = cleaned[i]
        if here is None:
            continue
        mid = here[0]
        levels = []
        if "buy" in sides:
            levels.append(("buy", mid * (1.0 - dist / 1e4)))
        if "sell" in sides:
            levels.append(("sell", mid * (1.0 + dist / 1e4)))
        for side, level in levels:
            duration, event = 0, False
            for t in range(1, life + 1):
                j = i + t
                if j >= len(cleaned) or cleaned[j] is None:
                    break                      # censored at last valid poll
                _, bid, ask = cleaned[j]
                duration = t
                if (side == "buy" and ask <= level) or \
                        (side == "sell" and bid >= level):
                    event = True
                    break
            if duration >= 1:
                out.append(Episode(duration, event))
    return out


def fit_discrete_hazard(episodes: list[Episode], t_max: int) -> HazardFit:
    """Life-table (Kaplan-Meier) fit of the discrete per-poll hazard.

    h(t) = d_t / n_t with n_t = episodes still at risk at poll age t
    (neither hit nor censored before t). Survival S(t) = prod(1 - h(u)),
    Greenwood variance Var[S(t)] = S(t)^2 * sum d_u / (n_u (n_u - d_u)).
    Per-bin Wilson 95% CIs quantify each hazard estimate's uncertainty.
    """
    T = max(int(t_max), 1)
    n = [0] * T
    d = [0] * T
    for ep in episodes:
        dur = min(max(int(ep.duration), 1), T)
        for t in range(dur):
            n[t] += 1
        if ep.event and ep.duration <= T:
            d[dur - 1] += 1
    h, h_lo, h_hi, surv, surv_se = [], [], [], [], []
    s, gw = 1.0, 0.0
    for t in range(T):
        ht = (d[t] / n[t]) if n[t] > 0 else 0.0
        _, lo, hi = wilson_interval(d[t], n[t]) if n[t] > 0 else (0.0, 0.0, 0.0)
        h.append(ht)
        h_lo.append(lo)
        h_hi.append(hi)
        s *= (1.0 - ht)
        if n[t] > 0 and n[t] > d[t]:
            gw += d[t] / (n[t] * (n[t] - d[t]))
        surv.append(s)
        surv_se.append(s * math.sqrt(gw) if gw > 0.0 else 0.0)
    return HazardFit(t_max=T, n=tuple(n), d=tuple(d), h=tuple(h),
                     h_lo=tuple(h_lo), h_hi=tuple(h_hi), surv=tuple(surv),
                     surv_se=tuple(surv_se), episodes=len(episodes),
                     events=sum(d), exposure=sum(n))


def constant_hazard_mle(episodes: list[Episode]) -> float:
    """MLE of a constant per-poll hazard: total hits / total exposure."""
    events = sum(1 for ep in episodes if ep.event)
    exposure = sum(max(int(ep.duration), 1) for ep in episodes)
    return (events / exposure) if exposure > 0 else 0.0


def _bin_ll(d: int, n: int, h: float) -> float:
    """Binomial log-likelihood of one life-table bin, boundary-safe."""
    ll = 0.0
    if d > 0:
        ll += d * math.log(max(h, 1e-300))
    if n - d > 0:
        ll += (n - d) * math.log(max(1.0 - h, 1e-300))
    return ll


def lr_test(fit: HazardFit, h_const: float) -> tuple:
    """LR of the fitted per-poll hazard vs the constant-hazard model.

    Returns (lr_stat, dof, p_value). dof = populated bins - 1; p is None
    when the shape is not testable (fewer than two populated bins).
    """
    bins = sum(1 for nt in fit.n if nt > 0)
    ll_fit = sum(_bin_ll(dt, nt, ht)
                 for dt, nt, ht in zip(fit.d, fit.n, fit.h, strict=True)
                 if nt > 0)
    ll_c = sum(_bin_ll(dt, nt, h_const)
               for dt, nt in zip(fit.d, fit.n, strict=True) if nt > 0)
    lr = max(2.0 * (ll_fit - ll_c), 0.0)
    dof = bins - 1
    if dof < 1:
        return (lr, dof, None)
    return (lr, dof, chi2_sf(lr, dof))


def cumulative_fill_const(h: float, t: int) -> float:
    """Constant-hazard cumulative fill probability by poll t."""
    h = min(max(float(h), 0.0), 1.0)
    return 1.0 - (1.0 - h) ** max(int(t), 0)


def ks_distance(fit: HazardFit, h_const: float) -> float:
    """Max distance between fitted and constant cumulative fill curves."""
    worst = 0.0
    for t in range(1, fit.t_max + 1):
        f_fit = 1.0 - fit.surv[t - 1]
        worst = max(worst, abs(f_fit - cumulative_fill_const(h_const, t)))
    return worst


# ------------------------------------------------------- chi2 (no scipy)
def _gser(a: float, x: float) -> float:
    """Regularized lower incomplete gamma P(a,x) by series (x < a+1)."""
    ap, total, delta = a, 1.0 / a, 1.0 / a
    for _ in range(500):
        ap += 1.0
        delta *= x / ap
        total += delta
        if abs(delta) < abs(total) * 1e-12:
            break
    return total * math.exp(-x + a * math.log(x) - math.lgamma(a))


def _gcf(a: float, x: float) -> float:
    """Regularized upper incomplete gamma Q(a,x) by continued fraction."""
    tiny = 1e-300
    b, c, dd = x + 1.0 - a, 1e30, 1.0 / max(x + 1.0 - a, tiny)
    frac = dd
    for i in range(1, 500):
        an = -i * (i - a)
        b += 2.0
        dd = an * dd + b
        dd = 1.0 / (dd if abs(dd) > tiny else tiny)
        c = b + an / (c if abs(c) > tiny else tiny)
        delta = dd * c
        frac *= delta
        if abs(delta - 1.0) < 1e-12:
            break
    return frac * math.exp(-x + a * math.log(x) - math.lgamma(a))


def chi2_sf(x: float, k: int) -> float:
    """Chi-square survival function P(X >= x) with k dof (scipy-free)."""
    x, a = float(x), max(float(k), 1e-12) / 2.0
    if x <= 0.0:
        return 1.0
    xx = x / 2.0
    q = _gcf(a, xx) if xx >= a + 1.0 else 1.0 - _gser(a, xx)
    return min(max(q, 0.0), 1.0)


# --------------------------------------------------------------- verdict
def hazard_verdict(fit: HazardFit, h_const: float, horizon: int, *,
                   rel_max: float = REL_MISSTATE_MAX,
                   min_episodes: int = MIN_EPISODES, e_min: int = E_MIN,
                   min_at_risk: int = MIN_AT_RISK,
                   min_bins: int = MIN_RESOLVED_BINS,
                   alpha: float = ALPHA) -> dict:
    """One bucket's L1 verdict: YES / NO / DEFERRED.

    YES needs BOTH the relative cumulative-fill misstatement at the
    timeout horizon above ``rel_max`` AND an LR rejection at ``alpha`` —
    a big point estimate on noise never asserts YES. NO needs adequate
    power (episodes, hits, and >= ``min_bins`` resolved poll bins: a
    single-bin tape cannot certify a SHAPE). Everything else DEFERRED.
    """
    T = min(max(int(horizon), 1), fit.t_max)
    f_fit = 1.0 - fit.surv[T - 1] if fit.surv else 0.0
    f_const = cumulative_fill_const(h_const, T)
    lr, dof, p = lr_test(fit, h_const)
    resolved = sum(1 for nt in fit.n if nt >= min_at_risk)
    rel = abs(f_const - f_fit) / f_fit if f_fit > 0.0 else None
    powered = (fit.episodes >= min_episodes and fit.events >= e_min
               and resolved >= min_bins and rel is not None)
    if not powered:
        verdict, reason = "DEFERRED", (
            f"underpowered: episodes={fit.episodes} (<{min_episodes}?) "
            f"events={fit.events} (<{e_min}?) resolved_bins={resolved} "
            f"(<{min_bins}?)")
    elif rel is not None and rel > rel_max and p is not None and p < alpha:
        verdict = "YES"
        reason = (f"constant hazard misstates F({T}) by {rel:.1%} "
                  f"(> {rel_max:.0%}) with LR p={p:.2e}")
    elif rel is not None and rel <= rel_max:
        verdict = "NO"
        reason = (f"constant hazard within {rel_max:.0%} at F({T}): "
                  f"rel={rel:.1%}, LR p={'n/a' if p is None else f'{p:.3f}'}")
    else:
        verdict = "DEFERRED"
        reason = (f"misstatement {rel:.1%} above threshold but not "
                  f"statistically resolved "
                  f"(LR p={'n/a' if p is None else f'{p:.3f}'} >= {alpha})")
    return {"verdict": verdict, "reason": reason, "horizon": T,
            "f_fit": f_fit, "f_const": f_const, "rel_misstate": rel,
            "ks": ks_distance(fit, h_const), "lr": lr, "dof": dof, "p": p,
            "h_const": h_const, "episodes": fit.episodes,
            "events": fit.events, "resolved_bins": resolved}


# ---------------------------------------------------------- orchestration
def collect_bucket_episodes(rec_dir, life_polls: int, dist_grid: list,
                            venue: str = "kraken") -> tuple:
    """Aggregate episodes per distance bucket across every recording.

    Returns (buckets, stats): buckets = {dist_bps: {"episodes": [...],
    "d_bar_sum": float, "parts": int}}; stats covers sessions/frames/span
    for the evidence-limits block. Each (session, symbol) tape gets its
    own sigma (scripts/calibrate_fills.estimate_sigma_bps) so d_bar
    reflects that tape's own vol; the bucket d_bar is the per-part mean.
    """
    buckets: dict = {d: {"episodes": [], "d_bar_sum": 0.0, "parts": 0}
                     for d in dist_grid}
    stats = {"sessions": 0, "tapes": 0, "frames": 0,
             "t_min": None, "t_max": None, "max_duration": 0}
    for rec in discover_recordings(rec_dir):
        by_symbol = extract_frames(str(rec), venue)
        if not by_symbol:
            continue
        stats["sessions"] += 1
        for _sym, frames in by_symbol.items():
            if len(frames) < 2:
                continue
            stats["tapes"] += 1
            stats["frames"] += len(frames)
            tss = [f.get("ts", 0.0) for f in frames]
            lo, hi = min(tss), max(tss)
            stats["t_min"] = lo if stats["t_min"] is None \
                else min(stats["t_min"], lo)
            stats["t_max"] = hi if stats["t_max"] is None \
                else max(stats["t_max"], hi)
            sigma = estimate_sigma_bps(frames)
            for dist in dist_grid:
                eps = episodes_from_frames(frames, life_polls, dist)
                if not eps:
                    continue
                b = buckets[dist]
                b["episodes"].extend(eps)
                b["d_bar_sum"] += float(dist) / max(sigma, 1.0)
                b["parts"] += 1
                stats["max_duration"] = max(
                    stats["max_duration"], max(ep.duration for ep in eps))
    return buckets, stats


def _overall(rows: list) -> tuple:
    """Overall verdict from per-bucket rows (near-touch buckets only).

    Any powered near-touch YES -> YES; at least one powered near-touch
    and all powered say NO -> NO; otherwise INSUFFICIENT_EVIDENCE.
    """
    near = [r for r in rows if r["near_touch"]]
    powered = [r for r in near if r["verdict"]["verdict"] in ("YES", "NO")]
    if any(r["verdict"]["verdict"] == "YES" for r in powered):
        return "YES", Code.XV_HAZARD_MISSTATED.value
    if powered:
        return "NO", Code.XV_HAZARD_SHAPE_OK.value
    return "INSUFFICIENT_EVIDENCE", Code.XV_HAZARD_INSUFFICIENT.value


def _fmt(x, spec=".3f", none="-") -> str:
    if x is None:
        return none
    try:
        return format(float(x), spec)
    except (TypeError, ValueError):
        return none


def render_report(cfg_view: dict, rows: list, stats: dict,
                  overall: str, code: str) -> str:
    """Markdown report. ``rows`` = per-bucket dicts (fit + verdict)."""
    T = cfg_view["life_polls"]
    lines = [
        "# L1 — maker-fill hazard time-consistency "
        "(Debate-1, report-only)", "",
        f"- generated: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}"
        f" by `scripts/fill_hazard_report.py`",
        "- mode: **book-frame synthesis** — recordings contain order-book"
        " snapshots only (no order events, no trade prints), so"
        " resting-maker episodes are synthesized by replaying book frames"
        " against a hypothetical resting level; a fill opportunity ="
        " opposite best quote at-or-through the level.",
        f"- recordings: {stats['sessions']} session(s), {stats['tapes']}"
        f" symbol-tape(s), {stats['frames']} book frames"
        + (f", span {time.strftime('%Y-%m-%d', time.gmtime(stats['t_min']))}"
           f" .. {time.strftime('%Y-%m-%d', time.gmtime(stats['t_max']))}"
           if stats["t_min"] is not None else ""),
        f"- sim under test: `passive_base_prob="
        f"{cfg_view['passive_base_prob']}` x exp(-dist/sigma), constant"
        f" per poll; `order_timeout_sec={cfg_view['order_timeout_sec']}`,"
        f" `polling_interval_sec={cfg_view['polling_interval_sec']}` ->"
        f" horizon T={T} polls; `queue_aware="
        f"{cfg_view['queue_aware']}`.",
        f"- verdict rule: YES iff rel misstatement of F(T) >"
        f" {REL_MISSTATE_MAX:.0%} AND LR p < {ALPHA}; the constant"
        " comparator is the BEST-FIT constant hazard (shape test — the"
        " LEVEL belongs to scripts/calibrate_fills.py).", ""]
    if not rows:
        lines += ["## Verdict", "",
                  f"**L1 verdict: {overall}** (`{code}`)", "",
                  "No recorded sessions with usable book frames were found"
                  " — the constant-vs-decreasing hazard question cannot be"
                  " adjudicated. Accrue recordings (system.record_feeds)"
                  " with enough polls per session to cover the order"
                  f" timeout horizon (T={T} polls) and re-run.", ""]
        lines += _limits_block(stats, T)
        return "\n".join(lines) + "\n"

    lines += ["## Constant vs fitted, per distance bucket", "",
              "| dist bps | d_bar | near-touch | episodes | events |"
              " h_const (MLE) | p_sim (config) | F_fit(T) | F_const(T) |"
              " rel misstate | KS | LR | dof | p | verdict |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"
              "---|"]
    for r in rows:
        v = r["verdict"]
        lines.append(
            f"| {r['dist_bps']:g} | {_fmt(r['d_bar'], '.2f')} |"
            f" {'y' if r['near_touch'] else 'n'} | {v['episodes']} |"
            f" {v['events']} | {_fmt(v['h_const'])} |"
            f" {_fmt(r['p_sim'])} | {_fmt(v['f_fit'])} |"
            f" {_fmt(v['f_const'])} |"
            f" {_fmt(v['rel_misstate'], '.1%')} | {_fmt(v['ks'])} |"
            f" {_fmt(v['lr'], '.2f')} | {v['dof']} |"
            f" {_fmt(v['p'], '.3g')} | {v['verdict']} |")
    lines += ["",
              "`p_sim (config)` = passive_base_prob * exp(-d_bar): the"
              " configured LEVEL, shown for context only — the verdict"
              " compares shapes, not levels."]

    primary = max((r for r in rows if r["near_touch"]),
                  key=lambda r: r["verdict"]["events"], default=None)
    if primary is not None:
        fit: HazardFit = primary["fit"]
        lines += ["", f"## Fitted hazard h(t) — primary bucket"
                  f" ({primary['dist_bps']:g} bps, most events among"
                  " near-touch)", "",
                  "| poll t | at-risk n_t | hits d_t | h(t) |"
                  " Wilson 95% | S(t) | Greenwood se |",
                  "|---|---|---|---|---|---|---|"]
        for t in range(fit.t_max):
            lines.append(
                f"| {t + 1} | {fit.n[t]} | {fit.d[t]} |"
                f" {_fmt(fit.h[t])} | [{_fmt(fit.h_lo[t])},"
                f" {_fmt(fit.h_hi[t])}] | {_fmt(fit.surv[t])} |"
                f" {_fmt(fit.surv_se[t], '.4f')} |")

    lines += ["", "## Verdict", "",
              f"**L1 verdict: {overall}** (`{code}`)", ""]
    if overall == "YES":
        lines += ["The constant-hazard sim misstates cumulative fill"
                  f" probability at the T={T} poll timeout horizon by more"
                  f" than {REL_MISSTATE_MAX:.0%} relative on these"
                  " recordings. **L2 (label-geometry change + 200x1200"
                  " re-baseline) stays justified.**"]
    elif overall == "NO":
        lines += ["On these recordings the constant-hazard shape stays"
                  f" within {REL_MISSTATE_MAX:.0%} relative of the fitted"
                  f" cumulative fill probability at the T={T} poll"
                  " horizon. **Recommend closing L2** (no label-geometry"
                  " change; re-open only if richer recordings contradict"
                  " this)."]
    else:
        lines += ["The recordings cannot resolve the constant-vs-"
                  "decreasing hazard question (see evidence limits)."
                  " **L2 stays unadjudicated** — do not spend the"
                  " 200x1200 re-baseline on this evidence; accrue longer"
                  " recordings first."]
    lines += [""]
    lines += _limits_block(stats, T)
    return "\n".join(lines) + "\n"


def _limits_block(stats: dict, T: int) -> list:
    span_h = 0.0
    if stats["t_min"] is not None and stats["t_max"] is not None:
        span_h = (stats["t_max"] - stats["t_min"]) / 3600.0
    lines = [
        "## Evidence limits (read before acting)", "",
        f"- {stats['sessions']} session(s) / {stats['tapes']} tape(s) /"
        f" {stats['frames']} book frames, wall-clock span ~{span_h:.1f} h"
        " — but hazard resolution is bounded by CONSECUTIVE polls per"
        " tape, not wall-clock span.",
    ]
    if stats["tapes"] > 0:
        lines.append(
            f"- ~{stats['frames'] / stats['tapes']:.1f} book polls per"
            f" tape; longest observed episode ="
            f" {stats['max_duration']} poll(s) vs horizon T={T} — poll"
            " ages beyond that are structurally UNOBSERVABLE in these"
            " recordings regardless of session count.")
    return lines + [
        "- Episodes are SYNTHESIZED from book snapshots (no recorded"
        " order events or trade prints): a best-quote touch is a fill"
        " OPPORTUNITY, not a guaranteed fill — queue position is not"
        " observable, so this measures the market-side arrival hazard"
        " the sim's constant-p term models.",
        "- With `queue_aware` on, the sim's EFFECTIVE hazard is 0 until"
        " the modeled queue clears, then constant — the constant-hazard"
        " assumption under test is the post-queue-clear phase.",
        "- Buy and sell placements are pooled per bucket; per-bucket"
        " fits avoid cross-DISTANCE pooling, but residual heterogeneity"
        " (symbol/session/side) biases a pooled hazard toward DECREASING"
        " (frailty artifact) — a YES that leans on a single bucket or a"
        " thin tape should be re-confirmed on richer recordings.",
        f"- Poll bins with fewer than {MIN_AT_RISK} at-risk episodes are"
        " unresolved; a verdict needs >= "
        f"{MIN_RESOLVED_BINS} resolved bins, {MIN_EPISODES} episodes and"
        f" {E_MIN} hits per bucket (horizon T={T} polls).",
    ]


def run(cfg: dict, rec_dir, out_path, dist_grid: list | None = None) -> int:
    """Build episodes, fit hazards, write the report. Always returns 0."""
    dist_grid = dist_grid or DEFAULT_DIST_GRID_BPS
    om = cfg.get("order_manager", {}) or {}
    sf = om.get("sim_fill", {}) or {}
    sys_cfg = cfg.get("system", {}) or {}
    poll_sec = float(sys_cfg.get("polling_interval_sec") or 5.0)
    life_sec = float(om.get("order_timeout_sec", 25.0))
    life_polls = max(int(round(life_sec / max(poll_sec, 1e-6))), 1)
    cfg_view = {
        "passive_base_prob": float(sf.get("passive_base_prob", 0.45)),
        "sigma_ref_bps": float(sf.get("sigma_ref_bps", 30.0)),
        "queue_aware": bool(sf.get("queue_aware", False)),
        "order_timeout_sec": life_sec,
        "polling_interval_sec": poll_sec,
        "life_polls": life_polls,
    }

    buckets, stats = collect_bucket_episodes(rec_dir, life_polls, dist_grid)
    rows = []
    for dist in dist_grid:
        b = buckets[dist]
        if not b["episodes"]:
            continue
        d_bar = b["d_bar_sum"] / b["parts"] if b["parts"] > 0 else None
        fit = fit_discrete_hazard(b["episodes"], life_polls)
        h_c = constant_hazard_mle(b["episodes"])
        p_sim = None
        if d_bar is not None:
            p_sim = cfg_view["passive_base_prob"] * math.exp(
                -min(d_bar, 20.0))
        rows.append({"dist_bps": float(dist), "d_bar": d_bar,
                     "near_touch": d_bar is not None
                     and d_bar <= D_MAX_DEFAULT,
                     "p_sim": p_sim, "fit": fit,
                     "verdict": hazard_verdict(fit, h_c, life_polls)})

    overall, code = _overall(rows)
    md = render_report(cfg_view, rows, stats, overall, code)
    out = Path(out_path)
    try:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(md, encoding="utf-8")
    except OSError as e:
        log.warning("report write failed %s: %s", out, e)
    print(md)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(
        description="L1 maker-fill hazard time-consistency report "
                    "(report-only; exit 0 always)")
    ap.add_argument("--config", default="config.json")
    ap.add_argument("--recording-dir", default=None,
                    help="default: system.recording_dir from config")
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    args = ap.parse_args()
    logging.basicConfig(level=logging.WARNING,
                        format="%(asctime)s %(levelname)s %(name)s: "
                               "%(message)s")
    from main import load_config
    cfg = load_config(args.config)
    rec_dir = args.recording_dir or cfg.get("system", {}).get(
        "recording_dir", "outputs/recordings")
    return run(cfg, rec_dir, Path(args.out))


if __name__ == "__main__":
    raise SystemExit(main())
