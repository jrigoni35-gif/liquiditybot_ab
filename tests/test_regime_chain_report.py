"""Pins for scripts/regime_chain_report.py (SAFE class, report-only).

The load-bearing property is NEGATIVE: the report must refuse to name a
CURRENT regime when the daily lane it read is stale. Measured 2026-09-09, all
four traded assets sat on an 86400s lane whose last bar was 2026-08-28 (13.0 d
old, exactly 720 bars = Kraken's OHLC page limit, i.e. a one-shot backfill
nothing appends to). A daily job over that corpus would otherwise print a
confident present-tense regime forever. `test_stale_lane_withholds...` is the
pin that makes that impossible; it is written so that deleting the staleness
branch turns it red.
"""

from __future__ import annotations

import time
from pathlib import Path

import numpy as np
import pytest

from data import candle_journal as cj
from scripts import regime_chain_report as rcr

REPO_ROOT = Path(__file__).resolve().parents[1]


def _bar(symbol: str, t_open_s: int, high: float, low: float, close: float):
    return cj.Bar(
        symbol=symbol, interval_s=86_400, source="kraken", quote="USD",
        t_open_s=t_open_s, open=None, high=high, low=low, close=close,
        volume=None, committed_by="test", ingest_s=t_open_s, conflicted=False,
    )


def _synthetic_bars(n: int, last_age_days: float, symbol: str = "TEST"):
    """A two-regime price path: alternating calm/violent blocks.

    Deterministic (fixed seed) so the HMM fit is reproducible.
    """
    rng = np.random.default_rng(11)
    now = time.time()
    t_last = int(now - last_age_days * 86_400)
    bars = []
    price = 100.0
    for i in range(n):
        calm = (i // 40) % 2 == 0
        sd = 0.004 if calm else 0.030
        ret = float(rng.normal(0.0, sd))
        price = max(price * (1.0 + ret), 1e-3)
        span = abs(ret) + sd
        high = price * (1.0 + span)
        low = price * max(1.0 - span, 1e-6)
        t_open = t_last - (n - 1 - i) * 86_400
        bars.append(_bar(symbol, t_open, high, low, price))
    return bars


# --------------------------------------------------------------------------
# steady state: a distribution, or an explicit UNKNOWN — never a silent prior
# --------------------------------------------------------------------------

def test_steady_state_matches_the_analytic_answer():
    A = np.array([[0.9, 0.1], [0.2, 0.8]])
    ss = rcr._steady_state(A)
    assert ss is not None
    # pi = pi A  =>  pi = [2/3, 1/3]
    assert ss == pytest.approx([2.0 / 3.0, 1.0 / 3.0], abs=1e-9)
    assert ss.sum() == pytest.approx(1.0, abs=1e-12)


def test_steady_state_returns_unknown_rather_than_a_uniform_prior():
    """A defective chain must yield None, not 'equal time in every regime'."""
    bad = np.array([[np.nan, np.nan], [np.nan, np.nan]])
    assert rcr._steady_state(bad) is None


def test_steady_state_of_a_sticky_chain_is_not_uniform():
    A = np.array([[0.99, 0.01], [0.50, 0.50]])
    ss = rcr._steady_state(A)
    assert ss is not None
    assert ss[0] > 0.90, "a highly persistent state must dominate the long run"


# --------------------------------------------------------------------------
# the report must label the chain the ENGINE acts on
# --------------------------------------------------------------------------

def test_semantic_order_reproduces_the_engine_relabelling():
    """Lowest mean return -> 'bear', highest -> 'bull', middle -> 'range'.

    macro_regime.update() does exactly this; if the two ever diverge the
    report names a different chain than the one the bot acts on.
    """
    class _Stub:
        def state_return_means(self):
            return np.array([0.05, -0.07, 0.001])   # idx1 lowest, idx0 highest

    sem = rcr._semantic_order(_Stub(), 3)
    assert sem[1] == "bear"
    assert sem[0] == "bull"
    assert sem[2] == "range"


# --------------------------------------------------------------------------
# universe resolution reads the SHIPPED key
# --------------------------------------------------------------------------

def test_universe_reads_kraken_trading_pairs_and_splits_the_base():
    cfg = {"exchanges": {"kraken": {"trading_pairs":
                                    ["PAXG/USD", "ETH/USD", "BTC/USD", "ETH/USD"]}}}
    assert rcr._universe(cfg) == ["PAXG", "ETH", "BTC"]


def test_universe_is_empty_rather_than_guessing_when_config_is_silent():
    assert rcr._universe({}) == []


# --------------------------------------------------------------------------
# THE PIN: a stale lane may not produce a current-regime claim
# --------------------------------------------------------------------------

def _fit_with_age(monkeypatch, age_days: float):
    bars = _synthetic_bars(400, age_days)
    monkeypatch.setattr(rcr, "_fetch_daily",
                        lambda *a, **k: (bars, 0, "ok"))
    return rcr.analyse_asset("TEST", {}, source="kraken", quote="USD")


def test_fresh_lane_does_make_a_current_regime_claim(monkeypatch):
    """The control. Without this, the stale test could pass on a report that
    never makes a current-regime claim at all."""
    row = _fit_with_age(monkeypatch, age_days=0.5)
    assert row["fitted"] is True
    assert row["stale"] is False
    assert row["current_state"] in ("bull", "bear", "range")
    assert row["current_state_prob"] is not None


def test_stale_lane_withholds_the_current_regime_claim(monkeypatch):
    row = _fit_with_age(monkeypatch, age_days=rcr.STALE_AFTER_DAYS + 10.0)
    assert row["fitted"] is True, "a stale lane still fits; only the claim changes"
    assert row["stale"] is True
    assert row["current_state"] is None
    assert row["current_state_prob"] is None
    assert row["current_expected_dwell_days"] is None
    # the descriptive half survives — the window is still describable
    assert row["as_of_state"] in ("bull", "bear", "range")
    assert row["transition_matrix"] is not None
    assert row["data_age_days"] > rcr.STALE_AFTER_DAYS


def test_age_is_measured_from_the_bar_close_not_its_open(monkeypatch):
    """A Bar covers [t_open, t_open + interval); its close is the reading.

    Chosen to DISCRIMINATE: a bar whose OPEN is 3.5 d old closed only 2.5 d
    ago, so it is fresh against a 3.0 d threshold. Measured from the open it
    would read stale. A healthy daily lane always carries an open between 1
    and 2 days old, so measuring from the open left roughly one day of slack
    before a false STALE.
    """
    assert rcr.STALE_AFTER_DAYS == 3.0, "this test's arithmetic assumes 3.0"
    row = _fit_with_age(monkeypatch, age_days=3.5)   # open 3.5d, close 2.5d
    assert row["fitted"] is True
    assert row["stale"] is False, "measured from the close, 2.5d is fresh"
    assert row["data_age_days"] == pytest.approx(2.5, abs=0.05)
    assert row["current_state"] is not None


def test_stale_row_renders_without_a_present_tense_claim(monkeypatch):
    row = _fit_with_age(monkeypatch, age_days=rcr.STALE_AFTER_DAYS + 10.0)
    rep = {
        "report": "regime_chain", "read_at_utc": "2026-01-01T00:00:00Z",
        "lane": "kraken/USD", "assets_requested": 1, "assets_fitted": 1,
        "assets_stale": 1, "stale_after_days": rcr.STALE_AFTER_DAYS,
        "staleness_warning": "1/1 stale", "decode": "posterior-marginal argmax",
        "caveat": "x", "assets": [row],
    }
    text = rcr.render(rep)
    assert "NO CURRENT-STATE CLAIM" in text
    assert "    now: " not in text, "a stale row must not print a 'now:' line"
    assert "HMM vote:" not in text, "a stale row must not print a live vote"
    # and the render must never imply this is the regime the bot trades on
    assert "NOT the bot's regime" in text


# --------------------------------------------------------------------------
# transition rows are a probability distribution
# --------------------------------------------------------------------------

def test_transition_rows_sum_to_one(monkeypatch):
    row = _fit_with_age(monkeypatch, age_days=0.5)
    for r in row["transition_matrix"]:
        assert sum(r) == pytest.approx(1.0, abs=1e-4)


def test_conflicted_bars_are_excluded_not_consumed(monkeypatch):
    """A venue-contradicted bar is not one a statistic may quietly consume.

    This drives the REAL `_fetch_daily`, patching the store call beneath it.
    An earlier version of this test patched `_fetch_daily` itself and
    re-implemented the drop inside the fake — so it asserted that the fake
    filtered, which it did by construction, and would have passed with the
    real filter deleted. An adversarial review caught that, mutation-confirmed.
    """
    good = _synthetic_bars(400, 0.5)
    bad = cj.Bar(symbol="TEST", interval_s=86_400, source="kraken",
                 quote="USD", t_open_s=good[-1].t_open_s + 86_400, open=None,
                 high=1e9, low=1e-9, close=1e9, volume=None,
                 committed_by="test", ingest_s=0, conflicted=True)

    monkeypatch.setattr(cj, "bars", lambda *a, **k: good + [bad])
    usable, dropped, status = rcr._fetch_daily("TEST", "kraken", "USD")

    assert status == "ok"
    assert dropped == 1, "the real filter must drop the contradicted bar"
    assert len(usable) == len(good)
    assert all(not b.conflicted for b in usable)
    assert bad not in usable, "the 1e9 close must not reach any statistic"


def test_the_conflicted_filter_is_not_vacuous(monkeypatch):
    """Control: with NO conflicted bar the same path drops nothing.

    Without this, the assertion above could be satisfied by a `_fetch_daily`
    that drops the last bar unconditionally.
    """
    good = _synthetic_bars(400, 0.5)
    monkeypatch.setattr(cj, "bars", lambda *a, **k: list(good))
    usable, dropped, status = rcr._fetch_daily("TEST", "kraken", "USD")
    assert status == "ok"
    assert dropped == 0
    assert len(usable) == len(good)


# --------------------------------------------------------------------------
# SAFE class: this report may not be imported by decision code
# --------------------------------------------------------------------------

def _decision_imports(name: str) -> list[str]:
    """Every decision-tree file that IMPORTS `name`, by AST.

    Deliberately AST and not a substring grep. The fence is a DEPENDENCY
    fence: decision code must not import analysis code. A docstring that
    NAMES this report — regime/macro_regime.py points at it, so a reader who
    finds the transition matrix knows where it is surfaced — creates no
    dependency and must not trip the guard. A substring scan cannot tell
    those apart and would push the next author to delete a useful
    cross-reference to get the suite green, which is the wrong direction.
    An import cannot hide in a comment, so this is also the stricter check.
    """
    import ast

    trees = ("core", "execution", "risk", "regime", "strategies", "sentiment",
             "api", "ml", "data")
    files = [p for t in trees for p in (REPO_ROOT / t).rglob("*.py")]
    files += [REPO_ROOT / "main.py", REPO_ROOT / "runner.py"]
    hits: list[str] = []
    for p in files:
        if not p.is_file() or "__pycache__" in p.parts:
            continue
        try:
            tree = ast.parse(p.read_text(encoding="utf-8"))
        except (OSError, SyntaxError):  # pragma: no cover
            continue
        for node in ast.walk(tree):
            mods: list[str] = []
            if isinstance(node, ast.Import):
                mods = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                base = node.module or ""
                mods = [base] + [f"{base}.{a.name}" for a in node.names]
            if any(name in m.split(".") for m in mods if m):
                hits.append(p.relative_to(REPO_ROOT).as_posix())
                break
    return hits


# --------------------------------------------------------------------------
# pins for the 2026-09-09 adversarial-review fixes
# --------------------------------------------------------------------------

def test_min_bars_reads_the_key_the_engine_reads(monkeypatch):
    """The engine gates on `regime.min_daily_bars` (default 120).

    This file read `min_bars` — a key that exists nowhere in config.json — so
    `.get()` returned 0 and the floor collapsed to ABSOLUTE_MIN_BARS=60, and
    the report would publish a chain for an asset the engine refuses to fit.
    """
    bars = _synthetic_bars(100, 0.5)          # 100: over 60, under 120
    monkeypatch.setattr(rcr, "_fetch_daily", lambda *a, **k: (bars, 0, "ok"))
    row = rcr.analyse_asset("TEST", {"regime": {"min_daily_bars": 120}},
                            source="kraken", quote="USD")
    assert row["fitted"] is False
    assert "insufficient" in row["status"]
    # and the DEFAULT must be 120, not 0 — an absent key may not lower the bar
    row2 = rcr.analyse_asset("TEST", {}, source="kraken", quote="USD")
    assert row2["fitted"] is False, "absent config must not collapse the floor"


def test_a_gap_is_not_differenced_across(monkeypatch):
    """A missing slot must not book a multi-day move as one daily return."""
    a = _synthetic_bars(200, 40.0, symbol="TEST")      # older block
    b = _synthetic_bars(200, 0.5, symbol="TEST")       # newer block, far later
    monkeypatch.setattr(rcr, "_fetch_daily", lambda *a_, **k: (a + b, 0, "ok"))
    row = rcr.analyse_asset("TEST", {}, source="kraken", quote="USD")
    assert row["gaps_detected"] >= 1
    # only the longest clean run may be used, never the spliced union
    assert row["bars_after_contiguity"] <= 200
    if row.get("fitted"):
        assert row["bars_used"] == row["bars_after_contiguity"]


def test_contiguous_run_picks_the_longest_block():
    bars = _synthetic_bars(10, 0.5)
    gapped = bars[:3] + bars[6:]          # hole between index 2 and 6
    kept, gaps, span = rcr._longest_contiguous_run(gapped)
    assert gaps == 1
    assert len(kept) == 4                 # the later block is longer
    assert all(kept[i + 1].t_open_s - kept[i].t_open_s == 86_400
               for i in range(len(kept) - 1))


def test_a_stuck_feed_is_refused_not_described(monkeypatch):
    """Constant price: rets all-zero, log(pvol+EPS) a finite constant, and
    GaussianHMM.fit still returns True with a finite A. Publishing dwell
    times for that chain describes the artefact, not the market."""
    now = time.time()
    flat = [_bar("TEST", int(now - (200 - i) * 86_400), 100.0, 100.0, 100.0)
            for i in range(200)]
    monkeypatch.setattr(rcr, "_fetch_daily", lambda *a, **k: (flat, 0, "ok"))
    row = rcr.analyse_asset("TEST", {}, source="kraken", quote="USD")
    assert row["fitted"] is False
    assert "degenerate" in row["status"]


def test_transition_rows_keep_their_mass_at_four_states(monkeypatch):
    """With n_states>=4 several states share the label 'range'; keying a dict
    on the label without summing silently discarded all but one."""
    bars = _synthetic_bars(400, 0.5)
    monkeypatch.setattr(rcr, "_fetch_daily", lambda *a, **k: (bars, 0, "ok"))
    row = rcr.analyse_asset("TEST", {"regime": {"hmm_states": 4}},
                            source="kraken", quote="USD")
    if not row.get("fitted"):
        pytest.skip(f"4-state fit did not converge: {row.get('status')}")
    for ps in row["per_state"]:
        assert sum(ps["transitions_to"].values()) == pytest.approx(1.0, abs=1e-4)


def test_by_label_sums_duplicates_rather_than_overwriting():
    got = rcr._by_label(["bear", "range", "range", "bull"],
                        [0.1, 0.2, 0.3, 0.4])
    assert got["range"] == pytest.approx(0.5)
    assert sum(got.values()) == pytest.approx(1.0)


def test_main_reports_failure_when_nothing_was_measured(monkeypatch, tmp_path,
                                                        capsys):
    """Exit code is the only thing Task Scheduler reads. 0/N fitted is not
    success — it is the silent-degradation shape this repo keeps paying for.

    LIQUIDITYBOT_OUTPUTS is redirected because `main()` persists on every run
    and conftest fails any test that writes into the production outputs/ tree.
    """
    monkeypatch.setenv("LIQUIDITYBOT_OUTPUTS", str(tmp_path / "outputs"))
    monkeypatch.setattr(rcr, "_universe", lambda cfg: [])
    rc = rcr.main([])
    capsys.readouterr()
    assert rc == 1


def test_main_reports_failure_when_no_asset_fits(monkeypatch, tmp_path, capsys):
    """The other silent-degradation door: a universe resolves, but the store
    gives nothing back. That is still not success."""
    monkeypatch.setenv("LIQUIDITYBOT_OUTPUTS", str(tmp_path / "outputs"))
    monkeypatch.setattr(rcr, "_universe", lambda cfg: ["TEST"])
    monkeypatch.setattr(rcr, "_fetch_daily",
                        lambda *a, **k: ([], 0, "no-bars-in-lane"))
    rc = rcr.main([])
    capsys.readouterr()
    assert rc == 1


def test_main_succeeds_on_a_healthy_fit(monkeypatch, tmp_path, capsys):
    """Control for the two above: without this, `return 1` on every path
    would pass them both."""
    monkeypatch.setenv("LIQUIDITYBOT_OUTPUTS", str(tmp_path / "outputs"))
    monkeypatch.setattr(rcr, "_universe", lambda cfg: ["TEST"])
    bars = _synthetic_bars(400, 0.5)
    monkeypatch.setattr(rcr, "_fetch_daily", lambda *a, **k: (bars, 0, "ok"))
    rc = rcr.main([])
    capsys.readouterr()
    assert rc == 0
    assert (tmp_path / "outputs" / "regime_chain_report.json").exists()


def test_main_refuses_an_out_path_outside_outputs(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(rcr, "_universe", lambda cfg: ["TEST"])
    bars = _synthetic_bars(400, 0.5)
    monkeypatch.setattr(rcr, "_fetch_daily", lambda *a, **k: (bars, 0, "ok"))
    monkeypatch.setenv("LIQUIDITYBOT_OUTPUTS", str(tmp_path / "outputs"))
    escape = tmp_path / "config"          # outside the outputs dir
    rc = rcr.main(["--out", str(escape)])
    capsys.readouterr()
    assert rc == 2, "an --out escaping the outputs dir must be refused"
    assert not (tmp_path / "config.json").exists(), "it must not have written"


def test_report_is_absent_from_decision_code():
    """Same fence data/candle_journal.py carries: analysis reads the decision
    tree, never the other way round."""
    hits = _decision_imports("regime_chain_report")
    assert not hits, f"report imported by decision code: {hits}"


def test_the_fence_would_actually_catch_an_import():
    """The guard is worthless if it cannot fire. `numpy` IS imported across
    the decision tree, so a non-empty result here proves the AST walk really
    reaches those files and really matches an import."""
    assert _decision_imports("numpy"), (
        "the import scan found nothing even for numpy — it is not reaching "
        "the decision tree, so the fence above is vacuous")
