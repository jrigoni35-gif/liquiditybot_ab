"""
scripts/order_chain_report.py — the order lifecycle as an ABSORBING MARKOV
CHAIN, estimated from the audit ledger (SAFE class, report-only).

WHY THIS EXISTS. Three numbers that govern maker execution are CONSTANTS in
config.json, not estimates:

    pretrade.maker_fill_p0            0.45   P(fill) at the touch, feeds the EV gate
    order_manager.sim_fill.passive_base_prob  0.048  per-poll hazard, constant by construction
    order_manager.order_timeout_sec   25     the horizon those two are read at

The first is a prior nobody has re-derived. The second is measured
(`scripts/calibrate_fills.py`, XV-021) but its own config doc concedes the
FORM is misspecified — "the exp(-d_bar) form is misspecified ... the FORM
deserves replacement eventually, not just the constant". The third is a chosen
horizon. `execution/order_manager.py` `_LEGAL` already describes the process
exactly: `pending -> {partial, filled, cancelled, expired}`, with
{filled, cancelled, expired} absorbing. That is an absorbing Markov chain, and
absorbing-chain theory answers all three questions in closed form from the
transition matrix — no simulation, no fitted curve:

    P = [[Q, R], [0, I]]        Q = transient->transient, R = transient->absorbing
    N = (I - Q)^-1              fundamental matrix; N[i][j] = expected visits
    t = N * 1                   EXPECTED POLLS TO ABSORPTION
    B = N * R                   ABSORPTION PROBABILITIES  (P(fill) vs P(expire))

WHAT IS ALREADY DONE, so this does not duplicate it. `scripts/fill_hazard_
report.py` (L1) tests the same constant-hazard assumption, but it SYNTHESIZES
episodes from order-book snapshots because "recordings carry NO order events",
and its own limits section reports only 9 tapes usable for age-fitting with the
longest observed episode equal to the horizon itself. This report uses the
opposite source: 1,700+ REAL order terminals with exact absorption times, read
from the hash-chained audit trail. Same question, independent route. Where the
two disagree, that disagreement is the finding.

**CIRCULARITY — READ THIS BEFORE QUOTING ANY NUMBER BELOW.** `system.dry_run`
is true and has been for this entire corpus, so every terminal counted here was
produced by the bot's OWN fill simulator, not by Kraken. This report therefore
measures **what the simulator realizes**, never what the venue does. That is
still worth measuring — it is the only way to check whether the sim delivers the
hazard it is configured with, and whether the pretrade EV gate's `maker_fill_p0`
matches what the pipeline behind it actually produces — but reading it as a
market measurement is the exact circular error this repo has already paid for
once (POWER-2: two routes anchored on the same configured constant "proves
booking==config, not venue truth"). Every headline below is prefixed SIM.

CLASSIFICATION — SAFE AS SHIPPED. Report-only: it reads
`outputs/audit.jsonl` and `config.json` and writes only under outputs/. It
places no order, changes no size, moves no stop, books no fee, touches no fill.
Wiring any number it prints into `pretrade`, the sizer, or the fill simulator is
COHORT-RESETTING under the era-9 moratorium and forbidden without operator
adjudication — this script exists to make that adjudication possible, not to
pre-empt it.

USAGE
    python scripts/order_chain_report.py
    python scripts/order_chain_report.py --json
    python scripts/order_chain_report.py --purpose entry
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

log = logging.getLogger("liquiditybot.scripts.order_chain")

TERMINAL_CODES = ("OM-000", "OM-040")     # clean terminal, timeout-cancel

# A lifetime outside this band is a corrupt `created_ts`, not a long order.
# Measured 2026-09-09: 72 of 1,786 terminals carry a created_ts that yields a
# negative or ~56-year lifetime (an epoch-zero / unset field), and one bucket's
# median was 886s against a 25s configured timeout. They are EXCLUDED and
# COUNTED — never silently clipped into the sane range, which would move mass
# onto the horizon and bias the hazard's tail upward.
LIFE_MIN_S = 0.0
LIFE_MAX_S = 3600.0

FULL_FILL = 0.999          # fill_ratio at/above this is a complete fill


def _load_config() -> dict:
    try:
        with open(REPO_ROOT / "config.json", "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def _wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval. Never the normal approximation: at the per-poll
    hazards involved (~1%) the normal interval crosses zero and reads as
    'possibly never fills', which is an artefact of the approximation."""
    if n <= 0:
        return (0.0, 0.0)
    p = k / n
    d = 1.0 + z * z / n
    c = p + z * z / (2 * n)
    m = z * math.sqrt(max(p * (1 - p) / n + z * z / (4 * n * n), 0.0))
    return (max(0.0, (c - m) / d), min(1.0, (c + m) / d))


def load_terminals(purpose: str | None = None,
                   audit_path: Path | None = None) -> dict[str, Any]:
    """Read every order terminal the audit trail carries.

    Returns the episodes plus an explicit accounting of what was dropped and
    why — a sample this report silently narrowed would be a worse instrument
    than no report.
    """
    path = audit_path or (REPO_ROOT / "outputs" / "audit.jsonl")
    episodes: list[dict[str, Any]] = []
    seen = 0
    no_schema = 0
    bad_life = 0
    wrong_purpose = 0

    try:
        fh = open(path, "r", encoding="utf-8", errors="replace")
    except OSError as exc:
        return {"error": f"audit unreadable: {exc}", "episodes": []}

    with fh:
        for line in fh:
            if "OM-0" not in line:
                continue
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            if rec.get("code") not in TERMINAL_CODES:
                continue
            seen += 1
            d = rec.get("data") or {}
            if "terminal" not in d or "fill_ratio" not in d or "created_ts" not in d:
                no_schema += 1
                continue
            if purpose and d.get("purpose") != purpose:
                wrong_purpose += 1
                continue
            ts = rec.get("ts")
            c0 = d.get("created_ts")
            if not (isinstance(ts, (int, float)) and isinstance(c0, (int, float))):
                bad_life += 1
                continue
            life = float(ts) - float(c0)
            if not (LIFE_MIN_S <= life <= LIFE_MAX_S):
                bad_life += 1
                continue
            fr = float(d.get("fill_ratio") or 0.0)
            episodes.append({
                "life_s": life,
                "fill_ratio": fr,
                "terminal": str(d.get("terminal")),
                "purpose": d.get("purpose"),
                "pair": d.get("pair"),
                "filled": fr >= FULL_FILL,
                "any_fill": fr > 0.0,
                "ts": float(ts),
            })

    return {
        "episodes": episodes,
        "records_seen": seen,
        "dropped_old_schema": no_schema,
        "dropped_bad_lifetime": bad_life,
        "dropped_other_purpose": wrong_purpose,
        "audit_path": str(path),
        "audit_mtime_utc": (
            time.strftime("%Y-%m-%dT%H:%M:%SZ",
                          time.gmtime(path.stat().st_mtime))
            if path.exists() else None),
    }


def discrete_hazard(episodes: list[dict], poll_s: float, horizon_polls: int
                    ) -> list[dict[str, Any]]:
    """Per-poll fill hazard h(t) = P(fill in poll t | still resting at t).

    This is the chain's transient->absorbing rate, estimated non-parametrically
    per poll rather than assumed constant. `at_risk` shrinks by BOTH arms —
    orders that filled and orders that expired — because an expired order is
    genuinely no longer at risk of filling, not a censored observation to be
    carried forward.
    """
    rows = []
    for t in range(1, horizon_polls + 1):
        lo = (t - 1) * poll_s
        hi = t * poll_s
        at_risk = sum(1 for e in episodes if e["life_s"] >= lo - 1e-9)
        fills = sum(1 for e in episodes
                    if e["any_fill"] and lo - 1e-9 <= e["life_s"] < hi + 1e-9)
        exits = sum(1 for e in episodes
                    if (not e["any_fill"]) and lo - 1e-9 <= e["life_s"] < hi + 1e-9)
        h = (fills / at_risk) if at_risk else 0.0
        lo_ci, hi_ci = _wilson(fills, at_risk)
        rows.append({
            "poll": t,
            "window_s": [round(lo, 1), round(hi, 1)],
            "at_risk": at_risk,
            "fills": fills,
            "expiries": exits,
            "hazard": round(h, 6),
            "hazard_ci95": [round(lo_ci, 6), round(hi_ci, 6)],
        })
    return rows


def absorbing_chain(haz_rows: list[dict]) -> dict[str, Any]:
    """Absorbing-chain summary from the estimated per-poll hazards.

    Builds the (H x H) transient block Q for the time-INHOMOGENEOUS chain —
    state = "resting, having survived t polls" — because that is what the data
    supports; collapsing it to one state would ASSUME the very homogeneity the
    homogeneity test below is there to check. Then applies the standard
    identities N = (I - Q)^-1, t = N*1, B = N*R.
    """
    H = len(haz_rows)
    if H == 0:
        return {"error": "no hazard rows"}

    # transient states s_1..s_H ; s_t -> s_{t+1} with prob (1 - h_t - e_t)
    # THREE absorbing columns. An earlier cut had two and folded any residual
    # survival at the horizon into EXPIRED — that misfiled 200 orders that
    # actually filled AFTER the horizon and understated P(fill) by ~12 points
    # against the raw outcome count. Survival past the horizon is CENSORED:
    # the chain did not observe its resolution, which is a different statement
    # from "it expired" and must not be silently converted into one.
    Q = np.zeros((H, H))
    R = np.zeros((H, 3))          # columns: FILLED, EXPIRED, CENSORED
    for i, row in enumerate(haz_rows):
        n = row["at_risk"]
        if n <= 0:
            continue
        h = row["fills"] / n
        e = row["expiries"] / n
        surv = max(0.0, 1.0 - h - e)
        R[i, 0] = h
        R[i, 1] = e
        if i + 1 < H:
            Q[i, i + 1] = surv
        else:
            R[i, 2] = surv        # censored, NOT expired

    try:
        N = np.linalg.inv(np.eye(H) - Q)
    except np.linalg.LinAlgError:
        return {"error": "fundamental matrix is singular"}

    expected_polls = float((N @ np.ones(H))[0])
    B = N @ R
    p_fill = float(B[0, 0])
    p_expire = float(B[0, 1])
    p_cens = float(B[0, 2])

    return {
        "expected_polls_to_absorption": round(expected_polls, 4),
        "p_absorb_filled": round(p_fill, 6),
        "p_absorb_expired": round(p_expire, 6),
        "p_still_resting_at_horizon": round(p_cens, 6),
        "mass_check": round(p_fill + p_expire + p_cens, 6),
        "transient_states": H,
        "note": ("p_absorb_filled is P(fill WITHIN the horizon). Orders still "
                 "resting at the horizon are CENSORED, not expired — compare "
                 "against the raw outcome counts, which are unconditional."),
    }


def homogeneity_test(haz_rows: list[dict]) -> dict[str, Any]:
    """Likelihood-ratio test: is the per-poll hazard CONSTANT?

    The simulator assumes it is (`passive_base_prob` is applied per poll with
    no age term), and the queue-reactive literature the repo already cites
    (Cont-Stoikov-Talreja 2010; Huang-Lehalle-Rosenbaum 2015) predicts a
    DECREASING hazard with queue age. This is the same question
    scripts/fill_hazard_report.py asks of synthesized book episodes, asked
    instead of real order terminals.
    """
    k = [r["fills"] for r in haz_rows]
    n = [r["at_risk"] for r in haz_rows]
    tot_k, tot_n = sum(k), sum(n)
    if tot_n == 0 or tot_k == 0:
        return {"applicable": False, "reason": "no events"}
    p0 = tot_k / tot_n

    def ll(ks, ns, ps):
        out = 0.0
        for ki, ni, pi in zip(ks, ns, ps, strict=True):
            if ni <= 0:
                continue
            pi = min(max(pi, 1e-12), 1 - 1e-12)
            out += ki * math.log(pi) + (ni - ki) * math.log(1 - pi)
        return out

    ll_const = ll(k, n, [p0] * len(k))
    ll_free = ll(k, n, [(ki / ni if ni else p0) for ki, ni in zip(k, n, strict=True)])
    stat = 2.0 * (ll_free - ll_const)
    dof = max(1, sum(1 for ni in n if ni > 0) - 1)
    # survival function of chi2 without scipy: Wilson-Hilferty approximation
    x = stat / dof
    z = (x ** (1.0 / 3.0) - (1 - 2.0 / (9 * dof))) / math.sqrt(2.0 / (9 * dof))
    p = 0.5 * math.erfc(z / math.sqrt(2.0))
    return {
        "applicable": True,
        "pooled_hazard": round(p0, 6),
        "lr_stat": round(stat, 4),
        "dof": dof,
        "p_value": round(p, 6),
        "constant_hazard_rejected": bool(p < 0.05),
        "note": ("p < 0.05 means the per-poll hazard is NOT constant, which is "
                 "what the simulator assumes. Chi-square tail via "
                 "Wilson-Hilferty (no scipy dependency); exact near the "
                 "decision boundary to ~1e-3."),
    }


def build_report(purpose: str | None = None) -> dict[str, Any]:
    cfg = _load_config()
    om = cfg.get("order_manager", {}) if isinstance(cfg.get("order_manager"), dict) else {}
    pt = cfg.get("pretrade", {}) if isinstance(cfg.get("pretrade"), dict) else {}
    sf = om.get("sim_fill", {}) if isinstance(om.get("sim_fill"), dict) else {}

    timeout_s = float(om.get("order_timeout_sec", 25.0))
    poll_s = float(cfg.get("system", {}).get("polling_interval_sec", 5.0)
                   if isinstance(cfg.get("system"), dict) else 5.0)
    # +1 poll. The timeout ELAPSES at order_timeout_sec but the cancel is only
    # OBSERVED on the following poll, so a horizon of exactly timeout/poll cuts
    # the chain at the instant the mass resolves: measured 2026-09-09, entry
    # life median 25.19s and p90 27.21s against a 25s timeout, which left 71.1%
    # of entries "still resting at the horizon" — censored, describing nothing.
    # One extra poll turns that censored mass into the observed expiries it
    # actually is. This is a property of the polling loop, not a fitted knob:
    # re-derive it as ceil(timeout/poll) + 1 if either constant moves.
    horizon = max(1, int(math.ceil(timeout_s / poll_s)) + 1)

    loaded = load_terminals(purpose=purpose)
    eps = loaded.get("episodes", [])
    read_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    base: dict[str, Any] = {
        "report": "order_chain",
        "classification": "SAFE — report-only; measures the DRY-RUN simulator, not the venue",
        "read_at_utc": read_at,
        "audit_path": loaded.get("audit_path"),
        "audit_mtime_utc": loaded.get("audit_mtime_utc"),
        "purpose_filter": purpose or "(all)",
        "records_seen": loaded.get("records_seen", 0),
        "episodes_used": len(eps),
        "dropped_old_schema": loaded.get("dropped_old_schema", 0),
        "dropped_bad_lifetime": loaded.get("dropped_bad_lifetime", 0),
        "dropped_other_purpose": loaded.get("dropped_other_purpose", 0),
        "poll_interval_s": poll_s,
        "order_timeout_s": timeout_s,
        "horizon_polls": horizon,
        "circularity_warning": (
            "system.dry_run is true for this entire corpus: every terminal here "
            "was produced by the bot's own fill simulator. These are SIM "
            "quantities. They test whether the simulator realizes what it is "
            "configured with — they are NOT a measurement of Kraken."),
    }
    if loaded.get("error"):
        base["status"] = loaded["error"]
        return base
    if not eps:
        base["status"] = "no usable episodes"
        return base

    maker_p0 = float(pt.get("maker_fill_p0", float("nan")))
    base_prob = float(sf.get("passive_base_prob", float("nan")))

    def _section(group: list[dict]) -> dict[str, Any]:
        n = len(group)
        oc = {
            "full_fill": sum(1 for e in group if e["filled"]),
            "partial_fill": sum(1 for e in group
                                if e["any_fill"] and not e["filled"]),
            "no_fill": sum(1 for e in group if not e["any_fill"]),
        }
        lo, hi = _wilson(oc["full_fill"] + oc["partial_fill"], n)
        lives = sorted(e["life_s"] for e in group)
        haz = discrete_hazard(group, poll_s, horizon)
        return {
            "n": n,
            "outcomes": oc,
            "p_any_fill": round((oc["full_fill"] + oc["partial_fill"]) / n, 6),
            "p_any_fill_ci95": [round(lo, 6), round(hi, 6)],
            "life_median_s": round(lives[n // 2], 3),
            "life_p90_s": round(lives[min(n - 1, int(0.9 * n))], 3),
            "beyond_horizon": sum(1 for e in group
                                  if e["life_s"] > horizon * poll_s),
            "beyond_horizon_that_filled": sum(
                1 for e in group
                if e["life_s"] > horizon * poll_s and e["any_fill"]),
            "hazard_by_poll": haz,
            "absorbing_chain": absorbing_chain(haz),
            "homogeneity": homogeneity_test(haz),
        }

    # SEGMENTED BY PURPOSE, ALWAYS. Measured 2026-09-09 these are three
    # different processes, not one: entry 42.9% fill / median life 25.2s (the
    # modal entry reaches the timeout), exit 95.4% / 5.5s (the exit ladder ends
    # in a market order), hedge 100% / 5.5s. A pooled rate of 67.5% describes
    # none of them and would have read as a large overshoot against
    # maker_fill_p0=0.45, when the population that constant actually governs —
    # entries, limit-only by invariant 5 — sits at 42.9%. Pooling three
    # populations under one denominator is the error this repo keeps re-buying.
    by_purpose = {}
    for p in ("entry", "exit", "hedge"):
        g = [e for e in eps if e["purpose"] == p]
        if g:
            by_purpose[p] = _section(g)

    base.update({
        "status": "ok",
        "by_purpose": by_purpose,
        "pooled_do_not_quote": {
            "n": len(eps),
            "p_any_fill": round(
                sum(1 for e in eps if e["any_fill"]) / len(eps), 6),
            "why": ("Retained only so a reader who computes it anyway sees it "
                    "labelled. Entry/exit/hedge have materially different fill "
                    "processes; the pooled number is a mixing artefact whose "
                    "value moves with the entry:exit ratio, not with execution "
                    "quality."),
        },
        "configured_constants": {
            "pretrade.maker_fill_p0": maker_p0,
            "order_manager.sim_fill.passive_base_prob": base_prob,
            "order_manager.order_timeout_sec": timeout_s,
        },
        "comparison": {
            "governs": "entry",
            "entry_sim_realized_p_any_fill": (
                by_purpose.get("entry", {}).get("p_any_fill")),
            "pretrade_assumes_at_touch": maker_p0,
            "note": ("maker_fill_p0 is the EV gate's P(fill) at ZERO distance; "
                     "the realized entry rate pools every distance and side, so "
                     "this is not like-for-like. It is reported because both "
                     "are models of the same physical event and nothing "
                     "currently reconciles them."),
        },
    })
    return base


def render(rep: dict[str, Any]) -> str:
    L: list[str] = []
    a = L.append
    a("=" * 74)
    a("ORDER LIFECYCLE AS AN ABSORBING MARKOV CHAIN")
    a("=" * 74)
    a(f"read_at : {rep['read_at_utc']}   audit mtime: {rep.get('audit_mtime_utc')}")
    a(f"purpose : {rep['purpose_filter']}")
    a("")
    a("!! " + rep["circularity_warning"])
    a("")
    if rep.get("status") != "ok":
        a(f"NO CHAIN ESTIMATED — {rep.get('status')}")
        return "\n".join(L)

    a(f"episodes used : {rep['episodes_used']}  "
      f"(seen {rep['records_seen']}; dropped "
      f"{rep['dropped_old_schema']} pre-schema, "
      f"{rep['dropped_bad_lifetime']} corrupt-lifetime, "
      f"{rep['dropped_other_purpose']} other-purpose)")
    a(f"horizon       : {rep['horizon_polls']} polls x "
      f"{rep['poll_interval_s']:.0f}s = {rep['order_timeout_s']:.0f}s "
      f"(order_timeout_sec)")
    a("")
    a("SEGMENTED BY PURPOSE — these are three different processes and the")
    a("pooled rate describes none of them.")
    a("")

    for name, s in rep["by_purpose"].items():
        o = s["outcomes"]
        ci = s["p_any_fill_ci95"]
        a("-" * 74)
        a(f"{name.upper()}   n={s['n']}   "
          f"SIM P(any fill) = {s['p_any_fill'] * 100:.1f}%  "
          f"95% CI [{ci[0] * 100:.1f}%, {ci[1] * 100:.1f}%]")
        a(f"  outcomes: full {o['full_fill']}  partial {o['partial_fill']}  "
          f"none {o['no_fill']}   life median {s['life_median_s']:.1f}s "
          f"p90 {s['life_p90_s']:.1f}s")
        if s["beyond_horizon"]:
            a(f"  {s['beyond_horizon']} order(s) outlived the horizon "
              f"({s['beyond_horizon_that_filled']} of them filled) — CENSORED "
              f"in the chain below, not counted as expiries")
        a("")
        a("  poll   at_risk   fills   expiries   h(t)      95% CI")
        for r in s["hazard_by_poll"]:
            c = r["hazard_ci95"]
            a(f"   {r['poll']:<5} {r['at_risk']:<9} {r['fills']:<7} "
              f"{r['expiries']:<10} {r['hazard']:.4f}    "
              f"[{c[0]:.4f}, {c[1]:.4f}]")
        ch = s["absorbing_chain"]
        a("")
        if "error" in ch:
            a(f"  chain: {ch['error']}")
        else:
            a("  N = (I-Q)^-1,  t = N*1,  B = N*R")
            a(f"    expected polls to absorption : "
              f"{ch['expected_polls_to_absorption']:.3f} "
              f"({ch['expected_polls_to_absorption'] * rep['poll_interval_s']:.1f}s)")
            a(f"    P(fill within horizon)       : {ch['p_absorb_filled'] * 100:.1f}%")
            a(f"    P(expire within horizon)     : {ch['p_absorb_expired'] * 100:.1f}%")
            a(f"    P(still resting at horizon)  : "
              f"{ch['p_still_resting_at_horizon'] * 100:.1f}%")
            a(f"    mass check (must be 1.000)   : {ch['mass_check']:.3f}")
        h = s["homogeneity"]
        if h.get("applicable"):
            verdict = ("REJECTED — the hazard is NOT constant"
                       if h["constant_hazard_rejected"]
                       else "not rejected — constant is compatible here")
            a("")
            a(f"  constant hazard? pooled h = {h['pooled_hazard']:.4f}  "
              f"LR = {h['lr_stat']:.1f}  dof = {h['dof']}  p = {h['p_value']:.3g}")
            a(f"    -> {verdict}")
        a("")

    a("-" * 74)
    c = rep["configured_constants"]
    cmp_ = rep["comparison"]
    a("configured constants this bears on")
    a(f"  pretrade.maker_fill_p0                   {c['pretrade.maker_fill_p0']}"
      f"   <- governs ENTRY")
    a(f"  order_manager.sim_fill.passive_base_prob {c['order_manager.sim_fill.passive_base_prob']}")
    a(f"  order_manager.order_timeout_sec          {c['order_manager.order_timeout_sec']}")
    ep = cmp_.get("entry_sim_realized_p_any_fill")
    if ep is not None:
        a("")
        a(f"  ENTRY realized {ep * 100:.1f}%  vs  maker_fill_p0 "
          f"{c['pretrade.maker_fill_p0'] * 100:.0f}% at the touch.")
        a("  NOT like-for-like: the constant is at ZERO distance, the realized")
        a("  rate pools every distance and side. Reported because both model the")
        a("  same physical event and nothing currently reconciles them.")
    a("")
    a(f"POOLED (do not quote): {rep['pooled_do_not_quote']['p_any_fill'] * 100:.1f}% "
      f"over n={rep['pooled_do_not_quote']['n']} — a mixing artefact.")
    return "\n".join(L)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Order lifecycle as an absorbing Markov chain (SAFE, report-only)")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--purpose", default=None,
                    choices=["entry", "exit", "hedge"],
                    help="restrict to one order purpose")
    ap.add_argument("--out", default=None, help="output STEM inside outputs/")
    args = ap.parse_args(argv)

    rep = build_report(purpose=args.purpose)
    print(json.dumps(rep, indent=2) if args.json else render(rep))

    try:
        out_dir = Path(os.environ.get("LIQUIDITYBOT_OUTPUTS",
                                      str(REPO_ROOT / "outputs"))).resolve()
        out_dir.mkdir(parents=True, exist_ok=True)
        stem = (Path(args.out).resolve() if args.out
                else out_dir / "order_chain_report")
        if out_dir not in stem.parents:
            log.error("refusing --out outside %s: %s", out_dir, stem)
            return 2
        with open(f"{stem}.json", "w", encoding="utf-8") as fh:
            json.dump(rep, fh, indent=2)
        with open(f"{stem}.txt", "w", encoding="utf-8", newline="\n") as fh:
            fh.write(render(rep) + "\n")
    except OSError as exc:
        log.warning("order chain report not persisted: %s", exc)
        return 1

    if rep.get("status") != "ok":
        log.error("no chain estimated: %s", rep.get("status"))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
