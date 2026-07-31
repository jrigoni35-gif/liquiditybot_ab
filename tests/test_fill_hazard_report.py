"""tests/test_fill_hazard_report.py — L1 maker-fill hazard time-consistency.

Synthetic-episode fixtures (constructed frame sequences with a KNOWN
per-poll hazard) prove the estimator recovers (i) a constant hazard —
the sim's assumption, bucket verdict NO — and (ii) a decreasing hazard
(Cont-Stoikov-Talreja 2010 / Huang-Lehalle-Rosenbaum 2015 queue-age
shape, bucket verdict YES), and that the report writer emits the L1
verdict line. No network, no dependence on real recordings; the
no-recordings path must skip gracefully with a clear message.
"""
import json

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
    run,
)

BASE_BID, BASE_ASK = 99.99, 100.01          # mid 100.0
DIP_BID, DIP_ASK = 99.39, 99.40             # sweeps through L_buy at 50bps


def _frame(ts, bid, ask):
    return {"ts": ts, "bid": bid, "ask": ask}


def _hazard_frames(h_of_t, life, n_windows, seed=7):
    """One placement frame + ``life`` observation frames per window (the
    extractor strides by life+1, so windows are fully disjoint). The ask
    dips through the 50bps buy level at poll age t with prob h_of_t(t) —
    exactly the discrete-hazard data-generating process."""
    rng = np.random.default_rng(seed)
    frames, ts = [], 0.0
    for _ in range(n_windows):
        frames.append(_frame(ts, BASE_BID, BASE_ASK))
        ts += 5.0
        for t in range(1, life + 1):
            hit = rng.random() < h_of_t(t)
            frames.append(_frame(ts, DIP_BID if hit else BASE_BID,
                                 DIP_ASK if hit else BASE_ASK))
            ts += 5.0
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
    h_c = constant_hazard_mle(eps)
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
    h_c = constant_hazard_mle(eps)
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
    v = hazard_verdict(fit, constant_hazard_mle(eps), 6)
    assert v["verdict"] == "DEFERRED"


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


def test_no_recordings_skips_gracefully(tmp_path):
    out = tmp_path / "report.md"
    rc = run(_cfg(), tmp_path / "nope", out)
    assert rc == 0 and out.exists()
    text = out.read_text(encoding="utf-8")
    assert "L1 verdict: INSUFFICIENT_EVIDENCE" in text
    assert "no recorded sessions" in text.lower()
