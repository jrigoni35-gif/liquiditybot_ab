"""Pins for scripts/era_readout.py - the era readout AS REGISTERED.

Every pin plants a synthetic ledger with a KNOWN answer and checks the
instrument gives it.

WHY THIS FILE IS LONGER THAN THE ONE IT REPLACES. A red-team pass on
2026-09-15 ran 35 mutants against the first version and 30 SURVIVED: the
suite could not see the day-block KEY (every fixture trip opened and closed
on the same UTC day), the CI WIDTH (planted edges at |z| ~ 44 pass a 90%,
99%, half- or double-width interval alike), the `-fee` clause of the n=100
CONTINUE rule (the only CONTINUE fixture had lo far above zero, so `lo > 0`
and `mean > fee_null` both survived), and the exact n=50/n=100 thresholds
(no fixture sat at 49/50/99/100). Those are the clauses the operator's
decision actually runs through. The pins below are organised by the clause
they defend, and each names the mutant it kills.

Nothing here touches outputs/ - every ledger lives in tmp_path.
"""
from __future__ import annotations

import csv
import statistics
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import era_readout as er  # noqa: E402

ERA = "12-test"
LETTER = "stamp-pure, all books (registration LETTER)"
HYPOTH = "stamp-pure, 5m book only (registration HYPOTHESIS)"  # = er.SELECTED_POP
ANYLEG = "any-leg (closes in era, incl. straddlers)"
LONGBK = "stamp-pure, long book only (NOT pooled - its own question)"

COLS = ["ts", "order_id", "position_id", "purpose", "symbol", "side", "ordertype",
        "post_only", "attempt", "fill_size", "fill_price", "arrival_ref", "slip_bps",
        "fees_delta_usd", "remaining", "reason", "exec_era", "book"]
DAY = 86400.0
T0 = 1_789_000_000.0            # 2026-09-10 00:26:40Z
FEE = 0.09                      # per leg, so $0.18 per round trip
TICKET = 60.0
P0 = 1000.0
SIZE = TICKET / P0              # 0.06 -> entry notional is exactly TICKET


def _leg(ts, pid, purpose, side, size, price, fee, era=ERA, book="", remaining=0.0):
    return {"ts": f"{ts:.3f}", "order_id": f"o{pid}{purpose}{ts:.0f}", "position_id": pid,
            "purpose": purpose, "symbol": "BTC/USD", "side": side, "ordertype": "limit",
            "post_only": "True", "attempt": "0", "fill_size": f"{size:.8f}",
            "fill_price": f"{price:.2f}", "arrival_ref": f"{price:.2f}", "slip_bps": "0",
            "fees_delta_usd": f"{fee:.6f}", "remaining": f"{remaining:.8f}", "reason": "",
            "exec_era": era, "book": book}


def _trip(rows, i, day, net_target, fee_each=FEE, era_entry=ERA, era_exit=ERA,
          book="", opened_by="entry", double_exit=False, hedge_leg=False,
          t_open=None, t_close=None, last_remaining=0.0):
    """One closed long trip whose net $ is exactly net_target."""
    pid = f"p{i:04d}"
    gross = net_target + 2 * fee_each
    p1 = P0 + gross / SIZE
    to = T0 + day * DAY + (i % 7) * 600 if t_open is None else t_open
    tc = to + 3600 * 6 if t_close is None else t_close
    rows.append(_leg(to, pid, opened_by, "buy", SIZE, P0, fee_each, era=era_entry, book=book))
    if hedge_leg:
        rows.append(_leg(to + 60, pid, "hedge", "sell", SIZE, P0, fee_each, era=era_entry))
    rows.append(_leg(tc, pid, "exit", "sell", SIZE, p1, fee_each, era=era_exit, book=book,
                     remaining=last_remaining))
    if double_exit:
        rows.append(_leg(tc + 3, pid, "exit", "sell", SIZE, p1, fee_each, era=era_exit, book=book))
    return pid


def _write(tmp_path, rows) -> Path:
    p = tmp_path / "fills.csv"
    with open(p, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=COLS)
        w.writeheader()
        w.writerows(rows)
    return p


def _noise(i):
    """Deterministic, zero-mean-ish jitter; no RNG in fixtures."""
    return ((i * 7919) % 13 - 6) * 0.05


def _from_days(tmp_path, per_day: dict[int, list[float]], **kw):
    """Exact control of the day blocks: {day_index: [net values]}."""
    rows, i = [], 0
    for day, vals in sorted(per_day.items()):
        for v in vals:
            _trip(rows, i, day=day, net_target=v, **kw)
            i += 1
    return _write(tmp_path, rows)


@pytest.fixture
def ledger(tmp_path):
    def build(n, net_mean, days=25, **kw):
        rows = []
        for i in range(n):
            _trip(rows, i, day=i % days, net_target=net_mean + _noise(i), **kw)
        return _write(tmp_path, rows)
    return build


def _reg(res):
    return res["populations"][LETTER]


# --------------------------------------------------------------------------
# The read-point rules
# --------------------------------------------------------------------------

def test_planted_edge_fires_the_lean_and_continues_at_n100(ledger):
    reg = _reg(er.run(ledger(110, net_mean=+0.80), ERA, -0.27, reps=800, seed=7))
    assert reg["n"] == 110
    assert reg["net"]["lo"] > 0
    assert reg["lean"].startswith("LEAN: ACT") and "POSITIVE" in reg["lean"]
    assert reg["verdict"].startswith("CONTINUE")


def test_planted_null_does_not_fire_the_lean(ledger):
    reg = _reg(er.run(ledger(110, net_mean=0.0), ERA, -0.27, reps=800, seed=7))
    assert reg["net"]["lo"] < 0 < reg["net"]["hi"]
    assert reg["lean"] == "LEAN: NO ACTION - CI includes zero"
    assert not reg["verdict"].startswith("CONTINUE")


def test_planted_loser_stops_on_no_gross_edge(ledger):
    reg = _reg(er.run(ledger(110, net_mean=-0.60), ERA, -0.27, reps=800, seed=7))
    assert reg["net"]["hi"] < 0 and "NEGATIVE" in reg["lean"]
    assert reg["verdict"].startswith("STOP - no gross edge")


def test_cost_bound_branch(ledger):
    reg = _reg(er.run(ledger(110, net_mean=-0.10), ERA, -0.27, reps=800, seed=7))
    assert reg["gross_pct"]["mean"] > 0 and reg["net"]["mean"] <= 0
    assert reg["verdict"].startswith("STOP - cost-bound")


@pytest.mark.parametrize("n,lean_reached,verdict_reached",
                         [(49, False, False), (50, True, False),
                          (99, True, False), (100, True, True)])
def test_thresholds_are_exact_at_49_50_99_100(ledger, n, lean_reached, verdict_reached):
    """Kills '<' vs '<=' at N_LEAN / N_VERDICT. The operator hits exactly 50."""
    reg = _reg(er.run(ledger(n, net_mean=+0.80), ERA, -0.27, reps=400, seed=7))
    assert reg["n"] == n
    assert reg["lean"].startswith("NOT REACHED") is not lean_reached
    assert reg["verdict"].startswith("NOT REACHED") is not verdict_reached


def test_continue_needs_the_CI_above_minus_fee_not_above_zero(tmp_path):
    """mean > 0, CI lo BELOW zero but ABOVE -fee -> CONTINUE.

    Kills `lo > 0` (the LEAN rule) substituted into the n=100 clause.
    """
    per_day = {d: [0.02 + s for s in (-0.10, 0.0, +0.10)] * 4 for d in range(10)}
    per_day[0] = [x + 0.12 for x in per_day[0]]
    per_day[1] = [x - 0.12 for x in per_day[1]]
    reg = _reg(er.run(_from_days(tmp_path, per_day), ERA, -0.27, reps=2000, seed=7))
    assert reg["n"] >= 100
    assert reg["net"]["mean"] > 0
    assert -0.27 < reg["net"]["lo"] < 0, reg["net"]
    assert reg["verdict"].startswith("CONTINUE")


def test_continue_needs_the_LO_above_minus_fee_not_the_MEAN(tmp_path):
    """mean > 0 but CI lo far BELOW -fee -> UNDETERMINED, not CONTINUE.

    Kills `mean > fee_null` substituted for `lo > fee_null`.
    """
    p = _from_days(tmp_path, {0: [+0.50] * 50, 1: [-0.46] * 50})
    reg = _reg(er.run(p, ERA, -0.27, reps=2000, seed=7))
    assert reg["n"] == 100 and reg["net"]["mean"] > 0
    assert reg["net"]["lo"] < -0.27
    assert reg["verdict"].startswith("UNDETERMINED")


def test_undetermined_says_so_when_the_net_CI_is_below_zero(tmp_path):
    """The registration's HOLE: gross mean <= 0, gross median > 0, net <= 0.

    The letter routes to extend-to-200 even with the net CI below zero; the
    page must say which clause actually applies.
    """
    # gross_pct = 100*(net + 2*FEE)/TICKET, so gross <= 0 iff net <= -0.18.
    # The hole needs the MEDIAN above -0.18 and the MEAN below it: many small
    # losers and a few large ones.
    per_day = {d: [v + (d % 5 - 2) * 0.02 for v in (-0.10, -0.10, -0.10, -1.00)]
               for d in range(26)}
    reg = _reg(er.run(_from_days(tmp_path, per_day), ERA, -0.27, reps=1500, seed=7))
    assert reg["n"] >= 100
    assert reg["gross_pct"]["mean"] <= 0 < reg["gross_median"]
    assert reg["net"]["mean"] <= 0 and reg["net"]["hi"] < 0
    assert reg["verdict"].startswith("UNDETERMINED")
    assert "excludes zero FROM BELOW" in reg["verdict"]


# --------------------------------------------------------------------------
# The interval: block key, width, protocol
# --------------------------------------------------------------------------

def test_day_block_is_the_utc_day_of_the_LAST_exit_not_the_open(tmp_path):
    """Kills close_day=_utc_day(t_open) and t=exits[0].

    On the live ledger 15 of 26 trips cross UTC midnight, and the t_open
    mutant moved the real CI while every old test stayed green.
    """
    rows = []
    d0_2300 = T0 - (T0 % DAY) + 23 * 3600          # 23:00 UTC, day 0
    pid = _trip(rows, 0, day=0, net_target=0.5,
                t_open=d0_2300, t_close=d0_2300 + 2 * 3600)   # 01:00 UTC, day 1
    rows.insert(1, _leg(d0_2300 + 1800, pid, "exit", "sell", SIZE / 2, P0, 0.0,
                        remaining=SIZE / 2))        # partial exit at 23:30, day 0
    # make the last exit carry the remaining half
    rows[-1] = _leg(d0_2300 + 2 * 3600, pid, "exit", "sell", SIZE / 2,
                    P0 + (0.5 + 2 * FEE) / SIZE, FEE * 2)
    for i in range(1, 6):
        _trip(rows, i, day=i, net_target=0.4)
    res = er.run(_write(tmp_path, rows), ERA, -0.27, reps=200, seed=7)
    t = next(x for x in res["trips"]["pure"] if x["pid"] == pid)
    day0, day1 = er._utc_day(d0_2300), er._utc_day(d0_2300 + 2 * 3600)
    assert day0 != day1
    assert t["close_day"] == day1, "block key must be the CLOSING day"
    assert t["t"] == pytest.approx(d0_2300 + 2 * 3600), "t must be the LAST exit"


def test_ci_half_width_matches_the_day_mean_standard_error(tmp_path):
    """A 95% interval has a KNOWN width. Kills 90%/99% bounds, half/double
    width, reps ignored, d-1 draws, a dropped block, nearest-percentile."""
    per_day = {d: [(_noise(d * 5 + k) + (d % 7 - 3) * 0.30) for k in range(5)]
               for d in range(40)}
    reg = _reg(er.run(_from_days(tmp_path, per_day), ERA, -0.27, reps=4000, seed=7))
    day_means = [statistics.mean(v) for v in per_day.values()]
    se = statistics.stdev(day_means) / len(day_means) ** 0.5
    half = (reg["net"]["hi"] - reg["net"]["lo"]) / 2
    assert 1.75 <= half / se <= 2.2, f"half-width/SE = {half / se:.2f}, expected ~1.96"


def test_day_block_interval_is_wider_than_an_iid_one_when_days_shock(tmp_path):
    """The DAY-BLOCK clause itself. With a per-day shock, clustering must
    widen the interval; an iid trip bootstrap would not see it."""
    import numpy as np
    per_day = {d: [(+1.0 if d % 2 == 0 else -1.0) + _noise(d * 10 + k) for k in range(10)]
               for d in range(6)}
    p = _from_days(tmp_path, per_day)
    reg = _reg(er.run(p, ERA, -0.27, reps=4000, seed=7))
    vals = np.array([t["net_usd"] for t in er.run(p, ERA, -0.27, reps=10, seed=7)["trips"]["pure"]])
    rng = np.random.default_rng(7)
    iid = np.array([vals[rng.integers(0, vals.size, vals.size)].mean() for _ in range(4000)])
    iid_half = float(np.percentile(iid, 97.5) - np.percentile(iid, 2.5)) / 2
    block_half = (reg["net"]["hi"] - reg["net"]["lo"]) / 2
    assert block_half > 2 * iid_half, (block_half, iid_half)


def test_ci_reproduces_the_stated_protocol_exactly(tmp_path):
    """Exact-reference pin: re-run the printed protocol and demand equality.
    Pins DRIFT (not the protocol's correctness - that is the live
    double-derivation's job)."""
    import numpy as np
    # UNEQUAL day sizes on purpose: with equal blocks, mean-of-concatenated and
    # mean-of-day-means are the same number, and a mutant swapping the
    # estimator survives (measured 2026-09-15).
    per_day = {d: [0.2 + _noise(d * 3 + k) for k in range(1 + d % 4)] for d in range(9)}
    res = er.run(_from_days(tmp_path, per_day), ERA, -0.27, reps=1000, seed=7)
    reg = _reg(res)
    days: dict[str, list[float]] = {}
    for t in res["trips"]["pure"]:
        days.setdefault(t["close_day"], []).append(t["net_usd"])
    keys = sorted(days)
    blocks = [np.asarray(days[k], dtype=float) for k in keys]
    rng = np.random.default_rng(7)
    means = np.empty(1000)
    for i in range(1000):
        idx = rng.integers(0, len(keys), size=len(keys))
        means[i] = float(np.concatenate([blocks[j] for j in idx]).mean())
    lo, hi = np.percentile(means, [2.5, 97.5])
    assert reg["net"]["lo"] == pytest.approx(float(lo), abs=1e-12)
    assert reg["net"]["hi"] == pytest.approx(float(hi), abs=1e-12)
    assert "PCG64" in reg["net"]["protocol"] and "linear" in reg["net"]["protocol"]


def test_seed_makes_the_ci_reproducible(ledger):
    p = ledger(60, net_mean=+0.2)
    a = _reg(er.run(p, ERA, -0.27, reps=500, seed=7))["net"]
    b = _reg(er.run(p, ERA, -0.27, reps=500, seed=7))["net"]
    c = _reg(er.run(p, ERA, -0.27, reps=500, seed=8))["net"]
    assert (a["lo"], a["hi"]) == (b["lo"], b["hi"])
    assert (a["lo"], a["hi"]) != (c["lo"], c["hi"])


def test_one_block_is_degenerate_and_says_so(tmp_path):
    reg = _reg(er.run(_from_days(tmp_path, {0: [0.3] * 8}), ERA, -0.27, reps=100, seed=7))
    assert reg["net"]["degenerate"] and reg["net"]["lo"] == reg["net"]["hi"]
    assert "DEGENERATE" in reg["net"]["protocol"]


def test_cluster_t_is_printed_and_is_not_the_rule(ledger):
    res = er.run(ledger(60, net_mean=-0.5), ERA, -0.27, reps=400, seed=7)
    reg = _reg(res)
    ct = reg["cluster_t_net"]
    assert ct["available"] and ct["lo"] < ct["hi"] and ct["df"] == ct["g"] - 1
    page = er.render(res)
    assert "calibration, NOT the rule" in page
    # the rule must read the registered interval, not the calibration one
    assert reg["lean"].startswith(("LEAN:", "NOT REACHED"))


# --------------------------------------------------------------------------
# Population: every trip lands in a row, an exclusion, or open/partial
# --------------------------------------------------------------------------

def test_doubled_exit_is_excluded_and_counted_not_silent(tmp_path):
    rows = []
    for i in range(6):
        _trip(rows, i, day=i, net_target=0.5)
    _trip(rows, 99, day=3, net_target=0.5, double_exit=True)
    res = er.run(_write(tmp_path, rows), ERA, -0.27, reps=200, seed=7)
    assert _reg(res)["n"] == 6
    ex = res["excluded"]
    assert len(ex) == 1 and ex[0]["pid"] == "p0099" and "2.00x" in ex[0]["reason"]
    assert "p0099" in er.render(res)


def test_hedge_leg_inside_an_entry_opened_trip_is_excluded(tmp_path):
    """Registration: 'hedge legs excluded'. Testing only the OPENING leg let a
    hedged trip stay in the population with its hedge folded into cash."""
    rows = []
    for i in range(5):
        _trip(rows, i, day=i, net_target=0.3)
    _trip(rows, 80, day=2, net_target=0.3, hedge_leg=True)
    res = er.run(_write(tmp_path, rows), ERA, -0.27, reps=200, seed=7)
    assert _reg(res)["n"] == 5
    assert any(e["pid"] == "p0080" and "hedge leg inside" in e["reason"]
               for e in res["excluded"])


def test_hedge_opened_trip_is_excluded_with_reason(tmp_path):
    rows = []
    for i in range(4):
        _trip(rows, i, day=i, net_target=0.3)
    _trip(rows, 70, day=1, net_target=0.3, opened_by="hedge")
    res = er.run(_write(tmp_path, rows), ERA, -0.27, reps=200, seed=7)
    assert _reg(res)["n"] == 4
    assert any(e["pid"] == "p0070" and "hedge" in e["reason"] for e in res["excluded"])


def test_trip_closing_outside_the_era_is_excluded_not_vanished(tmp_path):
    """Opened in the era, closed under a later stamp or unstamped: used to
    appear in NO row and NO exclusion list. At the next era cut every position
    open at the boundary takes this exact shape."""
    rows = []
    for i in range(4):
        _trip(rows, i, day=i, net_target=0.3)
    _trip(rows, 60, day=1, net_target=0.3, era_entry=ERA, era_exit="13-next")
    _trip(rows, 61, day=1, net_target=0.3, era_entry=ERA, era_exit="")
    res = er.run(_write(tmp_path, rows), ERA, -0.27, reps=200, seed=7)
    assert _reg(res)["n"] == 4
    reasons = {e["pid"]: e["reason"] for e in res["excluded"]}
    assert "closes outside" in reasons.get("p0060", "")
    assert "closes outside" in reasons.get("p0061", "")
    assert "p0060" in er.render(res) and "p0061" in er.render(res)


def test_open_and_partial_trips_are_counted_not_silently_dropped(tmp_path):
    rows = []
    for i in range(4):
        _trip(rows, i, day=i, net_target=0.3)
    _trip(rows, 40, day=1, net_target=0.3, last_remaining=0.5)      # partial
    rows.append(_leg(T0, "p0041", "entry", "buy", SIZE, P0, FEE))   # never closed
    res = er.run(_write(tmp_path, rows), ERA, -0.27, reps=200, seed=7)
    assert _reg(res)["n"] == 4
    kinds = {o["pid"]: o["reason"] for o in res["open_or_partial"]}
    assert "remaining" in kinds.get("p0040", "")
    assert "no exit leg" in kinds.get("p0041", "")
    page = er.render(res)
    assert "open / partially closed" in page and "p0040" in page and "p0041" in page


def test_straddler_counts_in_anyleg_but_not_in_pure(tmp_path):
    rows = []
    for i in range(5):
        _trip(rows, i, day=i, net_target=0.3)
    _trip(rows, 50, day=2, net_target=5.0, era_entry="11-old", era_exit=ERA)
    _trip(rows, 51, day=2, net_target=0.3, era_entry="", era_exit=ERA)
    res = er.run(_write(tmp_path, rows), ERA, -0.27, reps=200, seed=7)
    assert _reg(res)["n"] == 5
    assert res["populations"][ANYLEG]["n"] == 7
    assert sorted(t["membership"] for t in res["trips"]["anyleg_extra"]) == \
        ["straddler", "unstamped-legs"]


def test_book_membership_is_any_leg_because_exits_carry_no_book(tmp_path):
    """Ledger fact: only entry/add legs carry book='long'; exits carry ''."""
    rows = []
    for i in range(6):
        _trip(rows, i, day=i, net_target=0.3, book="long" if i < 2 else "")
    # (a) a long trip whose EXIT leg has a blank book, as the real ledger writes it
    pid = f"p{90:04d}"
    rows.append(_leg(T0 + DAY, pid, "entry", "buy", SIZE, P0, FEE, book="long"))
    rows.append(_leg(T0 + DAY + 3600, pid, "exit", "sell", SIZE, P0 + (0.3 + 2 * FEE) / SIZE,
                     FEE, book=""))
    # (b) a long trip whose FIRST leg is blank and whose ADD carries the tag.
    # This is the case that separates any-leg from first-leg; without it a
    # first-leg mutant survives (measured 2026-09-15).
    pid2 = f"p{91:04d}"
    rows.append(_leg(T0 + 2 * DAY, pid2, "entry", "buy", SIZE / 2, P0, FEE, book=""))
    rows.append(_leg(T0 + 2 * DAY + 60, pid2, "entry", "buy", SIZE / 2, P0, FEE, book="long"))
    rows.append(_leg(T0 + 2 * DAY + 3600, pid2, "exit", "sell", SIZE,
                     P0 + (0.3 + 2 * FEE) / SIZE, FEE, book=""))
    pops = er.run(_write(tmp_path, rows), ERA, -0.27, reps=200, seed=7)["populations"]
    assert pops[LETTER]["n"] == 8
    assert pops[LONGBK]["n"] == 4
    assert pops[HYPOTH]["n"] == 4


# --------------------------------------------------------------------------
# The page: what it must say out loud
# --------------------------------------------------------------------------

def test_no_row_is_labelled_REGISTERED(ledger):
    """The registration names no book. A row labelled REGISTERED would settle
    an open operator adjudication by default - and today the two rows differ
    in the sign of their medians."""
    res = er.run(ledger(12, net_mean=0.1), ERA, -0.27, reps=100, seed=7)
    assert not any("REGISTERED" in k for k in res["populations"])
    page = er.render(res)
    assert "registration names NO BOOK" in page
    assert "LETTER" in page and "HYPOTHESIS" in page
    # the selection is recorded on the page, with its disclosed cost
    assert "SELECTED (operator, 2026-09-15)" in page
    assert "FRIENDLIER median" in page and "hole" in page
    assert list(res["populations"])[0] == er.SELECTED_POP


def test_fee_null_defaults_to_the_eras_MEASURED_fee(ledger):
    """Operator adjudication 2026-09-15: H0 is what the account actually paid,
    recomputed every read - never a frozen literal."""
    res = er.run(ledger(12, net_mean=0.1), ERA, None, reps=100, seed=7)
    m = res["meta"]
    assert m["fee_null"] == pytest.approx(-2 * FEE, abs=1e-9)
    assert "MEASURED" in m["fee_null_source"]
    assert er.SELECTED_POP == HYPOTH


@pytest.mark.parametrize("spec,expect", [("cut11", -0.33), ("cut12", -0.27),
                                         (-0.5, -0.5), ("-0.41", -0.41)])
def test_fee_null_named_sources_and_literals(ledger, spec, expect):
    res = er.run(ledger(8, net_mean=0.1), ERA, spec, reps=50, seed=7)
    assert res["meta"]["fee_null"] == pytest.approx(expect)


def test_fee_null_rejects_an_unknown_name(ledger):
    with pytest.raises(ValueError, match="measured/cut11/cut12"):
        er.run(ledger(8, net_mean=0.1), ERA, "whatever", reps=50, seed=7)


def test_all_candidates_still_print(ledger):
    res = er.run(ledger(12, net_mean=0.1), ERA, "cut12", reps=100, seed=7)
    m = res["meta"]
    assert m["fee_null"] == -0.27 and "CLAUDE.md" in m["fee_null_source"]
    c = m["fee_null_candidates"]
    assert c["cut11_registered"] == -0.33 and c["cut12_adopted"] == -0.27
    assert c["era_measured_mean"] == pytest.approx(-2 * FEE, abs=1e-6)
    page = er.render(res)
    assert "cut-#11 registered -0.33" in page and "cut-#12 -0.27" in page
    assert "era measured" in page


def test_page_discloses_the_registrations_own_weaknesses(ledger):
    page = er.render(er.run(ledger(12, net_mean=0.1), ERA, -0.27, reps=100, seed=7))
    for phrase in ("under-covers", "CLOSING fill", "seed 7", "no alpha spending",
                   "HYPOTHESIS wording, not filters", "HOLE",
                   "powered to catch losing"):
        assert phrase in page, phrase


def test_effective_n_is_below_nominal_when_trips_overlap(tmp_path):
    rows = []
    for i in range(30):
        _trip(rows, i, day=0, net_target=0.2)
    reg = _reg(er.run(_write(tmp_path, rows), ERA, -0.27, reps=100, seed=7))
    eff = reg["effective"]
    assert eff["available"] and eff["effective_n"] < reg["n"] and eff["se_inflation"] > 1.0


def test_sd_uses_ddof_one(ledger):
    """pstdev understated the iid SE by sqrt(n/(n-1)) - flattering direction."""
    res = er.run(ledger(20, net_mean=0.3), ERA, -0.27, reps=100, seed=7)
    reg = _reg(res)
    nets = [t["net_usd"] for t in res["trips"]["pure"]]
    assert reg["sd"] == pytest.approx(statistics.stdev(nets), rel=1e-12)


def test_cli_runs_and_json_has_no_trip_dump(ledger, capsys):
    p = ledger(12, net_mean=0.1)
    assert er.main(["--fills", str(p), "--era", ERA, "--reps", "50", "--json"]) == 0
    out = capsys.readouterr().out
    assert '"populations"' in out and '"trips"' not in out
    assert '"era_source": "operator --era"' in out
