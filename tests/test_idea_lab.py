"""core/idea_lab.py - finite family, forward-only grading, birth/retire law."""
import copy
import json
import math
import random
from pathlib import Path

import pytest

from core.codes import Code
from core.idea_lab import (Bars, Idea, IdeaLab, MarketReading, ShadowBook,
                           decide, family, premise_matches, read_market,
                           step_book)
from core.target_book import BookParams, PressureLimits

ROOT = Path(__file__).resolve().parents[1]


def _cfg():
    tb = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))["target_book"]
    return {**{k: v for k, v in tb.items() if k not in ("idea_lab", "pressure")},
            **tb["idea_lab"]}


def _bars(n=260, seed=3, assets=("A", "B", "C", "D")):
    rng = random.Random(seed)
    close = {a: [100.0] for a in assets}
    for _ in range(n - 1):
        for a in assets:
            close[a].append(close[a][-1] * math.exp(rng.gauss(0, 0.02)))
    high = {a: [c * 1.01 for c in v] for a, v in close.items()}
    low = {a: [c * 0.99 for c in v] for a, v in close.items()}
    return Bars(list(range(n)), high, low, close)


def _lab(cfg=None):
    return IdeaLab(cfg or _cfg(), BookParams(maker_fee_bps=15.0),
                   PressureLimits(), 800.0)


def test_family_is_the_declared_grid():
    cfg = _cfg()
    fam = family(cfg)
    want = (len(cfg["gamma_grid"]) * len(cfg["aim_grid"])
            * len(cfg["weightings"]) * len(cfg["tilt_sources"]))
    assert len(fam) == want == len({i.id for i in fam})


def _run(bars, upto):
    lab = _lab()
    for i in range(42, upto):
        lab.step(bars, i)
    return lab


def _state(lab):
    return {k: (round(b.cash, 9), {a: round(u, 12) for a, u in b.units.items()},
                [round(r, 12) for r in b.rets], b.attempts, b.fills)
            for k, b in lab.books.items()}, list(lab.born), list(lab.events)


def test_no_look_ahead_future_bars_cannot_change_the_past():
    """Mutation pin: rewrite every bar after k+1; steps 42..k-1 must be
    bit-identical (step k-1 reads at most bar k)."""
    bars, k = _bars(), 200
    a = _state(_run(bars, k))
    fut = copy.deepcopy(bars)
    for sym in fut.close:
        for j in range(k + 1, len(fut)):
            fut.close[sym][j] *= 3.0
            fut.high[sym][j] *= 3.0
            fut.low[sym][j] *= 0.2
    assert _state(_run(fut, k)) == a


def _cut(bars, n):
    return Bars(bars.t[:n], {a: v[:n] for a, v in bars.high.items()},
                {a: v[:n] for a, v in bars.low.items()},
                {a: v[:n] for a, v in bars.close.items()})


def _poison(bars, i):
    """Every bar after i replaced by wild values (x/÷ 50 alternating)."""
    out = copy.deepcopy(bars)
    for a in out.close:
        for j in range(i + 1, len(out)):
            f = 50.0 if j % 2 else 0.02
            out.close[a][j] *= f
            out.high[a][j] *= f * 2
            out.low[a][j] *= f / 2
    return out


def _sig(p):
    return ([(o.asset, o.side, round(o.notional_usd, 9)) for o in p.orders],
            {a: round(v, 12) for a, v in p.bands.items()},
            {a: round(v, 12) for a, v in p.aims.items()}, p.pressure,
            dict(p.holds))


def test_decision_at_i_reads_nothing_after_i():
    """Mutation pin for the DECISION (settlement legitimately reads i+1, so
    the future-rewrite pin above cannot see a one-bar peek): decide() on bars
    truncated at i, and on bars whose future is poisoned, must equal decide()
    on the true series - orders, bands, aims, pressure and holds - at every
    step. Truncation catches an index past i; poisoning catches a slice past
    i (slices do not raise)."""
    bars, cfg, base = _bars(), _cfg(), BookParams(maker_fee_bps=15.0)
    for idea in (Idea(3.0, 0.5, "equal", "xs_reversal"),
                 Idea(1.5, 1.0, "inverse_vol", "xs_momentum")):
        full = ShadowBook(idea, 42, 800.0, {}, 800.0)
        for i in range(42, len(bars) - 1):
            snap = copy.deepcopy(full.__dict__)
            want = _sig(decide(full, bars, i, base, cfg, PressureLimits())[0])
            for variant in (_cut(bars, i + 1), _poison(bars, i)):
                twin = ShadowBook(idea, 42, 800.0, {}, 800.0)
                twin.__dict__.update(copy.deepcopy(snap))
                got = _sig(decide(twin, variant, i, base, cfg, PressureLimits())[0])
                assert got == want, f"decision at {i} read past i"
            full.__dict__.update(snap)
            step_book(full, bars, i, base, cfg, PressureLimits())


def test_step_refuses_without_next_bar():
    bars = _bars(50)
    with pytest.raises(IndexError):
        _lab().step(bars, len(bars) - 1)


def test_births_are_reactive_unique_and_reconcile():
    bars = _bars()
    lab = _run(bars, len(bars) - 1)
    rep = lab.report()
    born = [e for e in lab.events if e[1] == Code.IL_BORN.value]
    assert len(born) == rep["n_trials"] == len(set(lab.born))
    assert rep["n_trials"] == rep["alive"] + rep["retired"]
    assert rep["n_trials"] <= rep["family_size"]
    assert born[0][3] == "baseline"
    assert all(e[3] != "" for e in born)


def test_retire_rule_and_baseline_is_never_retired():
    cfg = {**_cfg(), "retire_after_steps": 5, "min_evidence_steps": 5}
    lab = _lab(cfg)
    bars = _bars()
    for i in range(42, len(bars) - 1):
        lab.step(bars, i)
    assert lab.books[lab.baseline_id].alive
    for e in lab.events:
        if e[1] == Code.IL_RETIRED.value:
            b = lab.books[e[2]]
            assert not b.alive and len(b.rets) >= 5


def test_report_never_promotes():
    bars = _bars()
    lab = _run(bars, len(bars) - 1)

    def always(sr, n, n_trials=1):
        return {"dsr": 0.999}
    rep = lab.report(always)
    for r in rep["ideas"]:
        assert r["status"] in ("accruing", "retired", "evidence (NOT a promotion)")
        if r["status"].startswith("evidence"):
            assert r["steps"] >= lab.cfg["min_evidence_steps"]
            assert r["code"] == Code.IL_EVIDENCE.value


def test_premise_matching():
    grid = [0.25, 0.5, 1.0]
    rev = MarketReading("reverting", False, -0.3, 1.0, 40)
    trd = MarketReading("trending", False, 0.3, 1.0, 40)
    neu = MarketReading("neutral", True, 0.0, 3.0, 40)
    assert premise_matches(Idea(3, 0.5, "equal", "xs_reversal"), rev, grid)
    assert not premise_matches(Idea(3, 0.5, "equal", "xs_momentum"), rev, grid)
    assert premise_matches(Idea(3, 0.5, "equal", "xs_momentum"), trd, grid)
    assert not premise_matches(Idea(3, 0.5, "equal", "xs_reversal"), trd, grid)
    assert premise_matches(Idea(3, 0.5, "equal", "none"), neu, grid)
    assert not premise_matches(Idea(3, 1.0, "equal", "none"), neu, grid)


def test_read_market_sees_reversion_and_trend():
    n = 60
    up = [100.0]
    dn = [100.0]
    for k in range(1, n):                # alternating relative moves
        s = 0.02 if k % 2 else -0.02
        up.append(up[-1] * (1 + s))
        dn.append(dn[-1] * (1 - s))
    rev = Bars(list(range(n)), {"A": up, "B": dn}, {"A": up, "B": dn},
               {"A": up, "B": dn})
    assert read_market(rev, n - 1, 42, 6, 2.0).state == "reverting"
    rng = random.Random(1)
    a, b = [100.0], [100.0]
    lead = 1.0
    for k in range(1, n):                # persistent relative regimes
        if k % 10 == 0:
            lead = -lead
        e = rng.gauss(0, 0.002)
        a.append(a[-1] * (1 + 0.01 * lead + e))
        b.append(b[-1] * (1 - 0.01 * lead + e))
    trd = Bars(list(range(n)), {"A": a, "B": b}, {"A": a, "B": b},
               {"A": a, "B": b})
    assert read_market(trd, n - 1, 42, 6, 2.0).state == "trending"


def test_state_classifier_false_positive_rate_on_noise():
    """Measured 2026-10-01: the naive 1/sqrt(n) cut fired on 14.2% of pure
    GBM windows (design 4.6%). The self-normalised statistic must hold the
    design rate on independent, heteroskedastic, correlated noise."""
    import numpy as np
    from scripts.target_book_validation import gbm_bars
    rng = np.random.default_rng(11)
    vol = np.array([0.02, 0.04, 0.08, 0.005])        # PAXG-like to LINK-like
    corr = np.full((4, 4), 0.6) + 0.4 * np.eye(4)
    corr[3, :3] = corr[:3, 3] = 0.05
    cov = corr * np.outer(vol, vol)
    names = ["A", "B", "C", "D"]
    n = 1500
    fired = sum(read_market(gbm_bars(np.zeros(4), cov, 44, names, rng), 43, 42,
                            6, 1e9).state != "neutral" for _ in range(n))
    assert 0.02 <= fired / n <= 0.075, fired / n
