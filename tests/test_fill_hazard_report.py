"""tests/test_fill_hazard_report.py — L1 maker-fill hazard time-consistency.

Synthetic-episode fixtures (constructed frame sequences with a KNOWN
per-poll hazard) prove the estimator recovers (i) a constant hazard —
the sim's assumption, bucket verdict NO — and (ii) a decreasing hazard
(Cont-Stoikov-Talreja 2010 / Huang-Lehalle-Rosenbaum 2015 queue-age
shape, bucket verdict YES), and that the report writer emits the L1
verdict line. No network, no dependence on real recordings; the
no-recordings path must skip gracefully with a clear message. Burst-gap
fixtures (frames far denser than polling_interval_sec) prove the
frame-gap guard excludes such tapes from hazard-age fitting and that
the report discloses the gap distribution + exclusion count.
"""
import json
from pathlib import Path
import math

import numpy as np

from scripts.fill_hazard_report import (
    REL_MISSTATE_MAX,
    Episode,
    chi2_sf,
    constant_hazard_mle,
    episodes_from_frames,
    fit_discrete_hazard,
    hazard_verdict,
    ks_distance,
    lr_test,
    median_frame_gap,
    run,
)

BASE_BID, BASE_ASK = 99.99, 100.01          # mid 100.0
DIP_BID, DIP_ASK = 99.39, 99.40             # sweeps through L_buy at 50bps


def _frame(ts, bid, ask):
    return {"ts": ts, "bid": bid, "ask": ask}


def _hazard_frames(h_of_t, life, n_windows, seed=7, gap_sec=5.0):
    """One placement frame + ``life`` observation frames per window (the
    extractor strides by life+1, so windows are fully disjoint). The ask
    dips through the 50bps buy level at poll age t with prob h_of_t(t) —
    exactly the discrete-hazard data-generating process. ``gap_sec``
    spaces the frame timestamps (5.0 matches the poll interval; a small
    value fakes a burst re-read tape for the frame-gap guard)."""
    rng = np.random.default_rng(seed)
    frames, ts = [], 0.0
    for _ in range(n_windows):
        frames.append(_frame(ts, BASE_BID, BASE_ASK))
        ts += gap_sec
        for t in range(1, life + 1):
            hit = rng.random() < h_of_t(t)
            frames.append(_frame(ts, DIP_BID if hit else BASE_BID,
                                 DIP_ASK if hit else BASE_ASK))
            ts += gap_sec
    return frames


# ------------------------------------------------------ episode extraction
def test_episode_extraction_first_hit_censoring_and_truncation():
    life = 4
    frames = [_frame(0, BASE_BID, BASE_ASK),      # placement (window 1)
              _frame(5, BASE_BID, BASE_ASK),      # t=1 no hit
              _frame(10, BASE_BID, BASE_ASK),     # t=2 no hit
              _frame(15, DIP_BID, DIP_ASK),       # t=3 HIT (buy side)
              _frame(20, BASE_BID, BASE_ASK),     # t=4 after first hit
              _frame(25, BASE_BID, BASE_ASK),     # placement (window 2)
              _frame(30, BASE_BID, BASE_ASK),     # t=1 no hit
              _frame(35, BASE_BID, BASE_ASK)]     # t=2 no hit, tape ends
    eps = episodes_from_frames(frames, life_polls=life, dist_bps=50.0,
                               sides=("buy",))
    assert eps == [Episode(3, True), Episode(2, False)]
    # the sell side of the same tape is never touched: censored full-life
    eps_sell = episodes_from_frames(frames, life_polls=life, dist_bps=50.0,
                                    sides=("sell",))
    assert eps_sell == [Episode(4, False), Episode(2, False)]


def test_bad_frame_censors_the_episode():
    frames = [_frame(0, BASE_BID, BASE_ASK),
              _frame(5, BASE_BID, BASE_ASK),
              _frame(10, 0.0, 0.0),               # broken frame
              _frame(15, DIP_BID, DIP_ASK)]       # never reached
    eps = episodes_from_frames(frames, life_polls=4, dist_bps=50.0,
                               sides=("buy",))
    assert eps == [Episode(1, False)]


def test_empty_frames_yield_no_episodes():
    assert episodes_from_frames([], life_polls=4, dist_bps=50.0) == []


# ------------------------------------------------- estimator: known hazards
def test_recovers_constant_hazard_and_says_no():
    p, life, n_win = 0.30, 6, 2000
    frames = _hazard_frames(lambda t: p, life, n_win, seed=7)
    eps = episodes_from_frames(frames, life_polls=life, dist_bps=50.0,
                               sides=("buy",))
    assert len(eps) == n_win
    fit = fit_discrete_hazard(eps, life)
    h_c = constant_hazard_mle(fit)
    assert abs(h_c - p) < 0.02
    # per-bin 95% Wilson CIs cover the true hazard, and point estimates
    # land close. Estimator verified UNBIASED over a 50-seed sweep (mean
    # h_c 0.2989, per-bin means ~0.30, miss counts matching nominal 95%
    # coverage); at this pinned seed every bin covers — allow one miss so
    # a legitimate future refactor of the rng stream can't flake.
    misses = sum(1 for t in range(life) if fit.n[t] >= 50
                 and not (fit.h_lo[t] <= p <= fit.h_hi[t]))
    assert misses <= 1
    for t in range(life):
        if fit.n[t] >= 50:
            assert abs(fit.h[t] - p) < 0.05
    v = hazard_verdict(fit, h_c, life)
    assert v["verdict"] == "NO"
    assert v["rel_misstate"] < REL_MISSTATE_MAX
    lr, dof, pval = lr_test(fit, h_c)
    assert dof == life - 1
    assert pval is not None and pval > 0.01    # no spurious rejection


def test_recovers_decreasing_hazard_and_says_yes():
    life, n_win = 6, 2000
    frames = _hazard_frames(lambda t: 0.5 * (0.55 ** (t - 1)), life, n_win,
                            seed=13)
    eps = episodes_from_frames(frames, life_polls=life, dist_bps=50.0,
                               sides=("buy",))
    fit = fit_discrete_hazard(eps, life)
    h_c = constant_hazard_mle(fit)
    # early hazard above late hazard with clear CI separation
    assert fit.h_lo[0] > fit.h_hi[2]
    lr, dof, pval = lr_test(fit, h_c)
    assert dof == life - 1 and lr > 0.0
    assert pval is not None and pval < 1e-6
    assert ks_distance(fit, h_c) > 0.05
    v = hazard_verdict(fit, h_c, life)
    assert v["verdict"] == "YES"
    assert v["rel_misstate"] > REL_MISSTATE_MAX


def test_underpowered_sample_defers():
    eps = [Episode(1, True)] * 5 + [Episode(1, False)] * 5
    fit = fit_discrete_hazard(eps, 6)
    v = hazard_verdict(fit, constant_hazard_mle(fit), 6)
    assert v["verdict"] == "DEFERRED"


def test_greenwood_se_and_ks_exact_small_table():
    """Exact-value pin on a tiny hand-computed life table.

    Episodes (1,hit), (2,hit), (2,cens), (2,cens):
      n1=4 d1=1 h1=1/4; n2=3 d2=1 h2=1/3; S1=3/4, S2=1/2.
      Greenwood: se1 = S1*sqrt(1/(4*3)); se2 = S2*sqrt(1/12 + 1/(3*2)) = 1/4.
      h_const = events/exposure = 2/7.
      KS = max(|1/4 - 2/7|, |1/2 - (1-(5/7)^2)|) = max(1/28, 1/98) = 1/28.
    """
    eps = [Episode(1, True), Episode(2, True),
           Episode(2, False), Episode(2, False)]
    fit = fit_discrete_hazard(eps, 2)
    assert fit.n == (4, 3) and fit.d == (1, 1)
    assert abs(fit.h[0] - 0.25) < 1e-12
    assert abs(fit.h[1] - 1.0 / 3.0) < 1e-12
    assert abs(fit.surv[0] - 0.75) < 1e-12
    assert abs(fit.surv[1] - 0.5) < 1e-12
    assert abs(fit.surv_se[0] - 0.75 * math.sqrt(1.0 / 12.0)) < 1e-12
    assert abs(fit.surv_se[1] - 0.25) < 1e-12
    h_c = constant_hazard_mle(fit)
    assert abs(h_c - 2.0 / 7.0) < 1e-12
    assert abs(ks_distance(fit, h_c) - 1.0 / 28.0) < 1e-12


def test_constant_hazard_mle_agrees_with_clamped_exposure():
    """h_const is fit.events/fit.exposure, so a duration beyond t_max can
    never make the comparator disagree with the clamped life table."""
    eps = [Episode(10, True), Episode(2, True), Episode(3, False)]
    fit = fit_discrete_hazard(eps, 3)          # duration 10 clamps to 3
    assert constant_hazard_mle(fit) == fit.events / fit.exposure


def test_greenwood_se_positive_and_survival_monotone():
    frames = _hazard_frames(lambda t: 0.3, 6, 500, seed=5)
    eps = episodes_from_frames(frames, life_polls=6, dist_bps=50.0,
                               sides=("buy",))
    fit = fit_discrete_hazard(eps, 6)
    assert all(s2 <= s1 + 1e-12 for s1, s2 in zip(fit.surv, fit.surv[1:]))
    assert all(se > 0.0 for se, n in zip(fit.surv_se, fit.n) if n > 0)


def test_chi2_sf_reference_points():
    assert chi2_sf(0.0, 5) == 1.0
    assert abs(chi2_sf(3.841, 1) - 0.05) < 2e-3
    assert abs(chi2_sf(11.070, 5) - 0.05) < 2e-3
    assert chi2_sf(100.0, 5) < 1e-15


# ----------------------------------------------------------- report writer
def _write_session(rec_dir, name, frames, symbol="ETHUSD"):
    rec_dir.mkdir(parents=True, exist_ok=True)
    with open(rec_dir / name, "w", encoding="utf-8") as f:
        for fr in frames:
            f.write(json.dumps({
                "t": fr["ts"], "feed": "kraken", "method": "get_order_book",
                "args": [symbol], "kwargs": {},
                "result": {"bids": [[fr["bid"], 1.0]],
                           "asks": [[fr["ask"], 1.0]]}}) + "\n")


def _cfg(life_sec=30, poll_sec=5):
    return {"system": {"polling_interval_sec": poll_sec},
            "order_manager": {"order_timeout_sec": life_sec,
                              "sim_fill": {"passive_base_prob": 0.45,
                                           "sigma_ref_bps": 30.0,
                                           "queue_aware": True}}}


def test_report_written_with_verdict_line(tmp_path):
    rec = tmp_path / "recordings"
    frames = _hazard_frames(lambda t: 0.5 * (0.55 ** (t - 1)), 6, 400,
                            seed=3)
    _write_session(rec, "session_100.jsonl", frames)
    out = tmp_path / "report.md"
    rc = run(_cfg(), rec, out)
    assert rc == 0 and out.exists()
    text = out.read_text(encoding="utf-8")
    assert "L1 verdict:" in text
    assert "book-frame synthesis" in text.lower()
    # survival CI band column (+-1.96*se beside the Greenwood se)
    assert "S(t) 95% CI" in text
    # gap disclosure present even when every tape is included
    assert "Frame-gap vs poll-interval" in text
    assert "0 tape(s) whose median gap deviates" in text


def test_no_recordings_skips_gracefully(tmp_path):
    out = tmp_path / "report.md"
    rc = run(_cfg(), tmp_path / "nope", out)
    assert rc == 0 and out.exists()
    text = out.read_text(encoding="utf-8")
    assert "L1 verdict: INSUFFICIENT_EVIDENCE" in text
    assert "no recorded sessions" in text.lower()


# ------------------------------------------- frame-gap guard (poll-age validity)
def test_median_frame_gap():
    frames = [_frame(t, BASE_BID, BASE_ASK)
              for t in (0.0, 5.0, 10.0, 10.012)]
    assert median_frame_gap(frames) == 5.0     # gaps 5, 5, 0.012
    assert median_frame_gap([_frame(0.0, BASE_BID, BASE_ASK)]) is None
    # missing/constant ts -> no positive gaps -> unmeasurable
    assert median_frame_gap([{"bid": BASE_BID, "ask": BASE_ASK}] * 3) is None


def test_burst_gap_tape_excluded_and_disclosed(tmp_path):
    """A burst re-read tape (median gap ~0.05 s vs 5 s polls) contributes
    ZERO episodes to hazard-age fitting, and the report discloses the gap
    distribution and the exclusion count."""
    good = _hazard_frames(lambda t: 0.5 * (0.55 ** (t - 1)), 6, 400, seed=3)
    burst = _hazard_frames(lambda t: 0.4, 6, 400, seed=11, gap_sec=0.05)
    rec_a = tmp_path / "rec_a"
    _write_session(rec_a, "session_100.jsonl", good)
    rec_b = tmp_path / "rec_b"
    _write_session(rec_b, "session_100.jsonl", good)
    _write_session(rec_b, "session_200.jsonl", burst)
    out_a, out_b = tmp_path / "a.md", tmp_path / "b.md"
    assert run(_cfg(), rec_a, out_a) == 0
    assert run(_cfg(), rec_b, out_b) == 0
    text_a = out_a.read_text(encoding="utf-8")
    text_b = out_b.read_text(encoding="utf-8")

    def tables(txt):
        return [ln for ln in txt.splitlines() if ln.startswith("|")]

    # identical fitted tables: the burst tape was excluded, not fitted
    assert tables(text_a) == tables(text_b)
    assert "1 tape(s) whose median gap deviates" in text_b
    assert "EXCLUDED from hazard-age fitting (1 tape(s) fitted)" in text_b


def test_all_burst_tapes_yield_insufficient_evidence(tmp_path):
    """When EVERY tape trips the frame-gap guard nothing may be fitted:
    the verdict stays INSUFFICIENT_EVIDENCE with the guard called out."""
    rec = tmp_path / "recordings"
    burst = _hazard_frames(lambda t: 0.4, 6, 400, seed=11, gap_sec=0.05)
    _write_session(rec, "session_100.jsonl", burst)
    out = tmp_path / "report.md"
    assert run(_cfg(), rec, out) == 0
    text = out.read_text(encoding="utf-8")
    assert "L1 verdict: INSUFFICIENT_EVIDENCE" in text
    assert "frame-gap guard" in text
    assert "1 of 1 tape(s)" in text
    assert "Frame-gap vs poll-interval" in text


def test_sigma_fallback_footnoted(tmp_path):
    """A fitted tape too thin for estimate_sigma_bps (2 frames) rides the
    30 bps fallback; the report footnotes how many tapes did."""
    rec = tmp_path / "recordings"
    frames = _hazard_frames(lambda t: 0.5 * (0.55 ** (t - 1)), 6, 400,
                            seed=3)
    _write_session(rec, "session_100.jsonl", frames)
    tiny = [_frame(0.0, BASE_BID, BASE_ASK), _frame(5.0, BASE_BID, BASE_ASK)]
    _write_session(rec, "session_200.jsonl", tiny, symbol="XBTUSD")
    out = tmp_path / "report.md"
    assert run(_cfg(), rec, out) == 0
    text = out.read_text(encoding="utf-8")
    assert "estimate_sigma_bps" in text
    assert "1 of 2 fitted tape(s)" in text


# --------------------------------------------------------------------------
# THE TWO CAVEATS — red-team OBJ-4, conceded
#
# A commit message read "both hazard reports still verdict NO ... so the fill
# simulator's SHAPE is sound". NO means this test could not show a misstatement
# above threshold; it is a failure to reject, not evidence of absence, and
# treating it as a clean bill of health affirms the null. The same message cited
# two reports as mutual corroboration - they read a ROLLING WINDOW over one
# recording store and shared 7 of their 9 days.
#
# Both caveats now ship IN the report, because the misreading happens where the
# number is read, not where it is computed.
# --------------------------------------------------------------------------

def test_the_report_says_NO_is_not_a_clean_bill_of_health():
    import scripts.fill_hazard_report as fh
    src = Path(fh.__file__).read_text(encoding="utf-8")
    assert "NO IS NOT" in src, (
        "the report no longer warns that a NO verdict is a failure to reject "
        "rather than evidence the simulator is sound")
    assert "affirms the null" in src


def test_the_report_says_consecutive_runs_are_not_independent():
    import scripts.fill_hazard_report as fh
    src = Path(fh.__file__).read_text(encoding="utf-8")
    assert "NOT INDEPENDENT" in src
    assert "ROLLING WINDOW" in src, (
        "the report no longer warns that consecutive runs share corpus, so two "
        "agreeing reports will be cited as corroboration again")
