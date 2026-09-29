"""scripts/shadow_policy_report.py - the walk-forward grade of the shadow
traded-value rule. The properties that make the grade honest: no look-ahead,
no guessed decision on a thin bin, and CS-1 reconciliation."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import shadow_policy_report as spr  # noqa: E402

DAY = 86400.0


def _history(n_hi=60, n_lo=60, t0=0.0):
    """Past candidates, resolved BEFORE t0: high-p pay +50, low-p lose -50."""
    shadow, label = [], {}
    for i in range(n_hi + n_lo):
        hi = i < n_hi
        cid = f"c{i}"
        shadow.append({"ts": t0 + i, "cid": cid, "p": 0.8 if hi else 0.2,
                       "fp": "f"})
        label[cid] = (50.0 if hi else -50.0, t0 + 1000 + i)   # resolves later
    return shadow, label


def test_decisions_follow_past_bins_and_reconcile():
    shadow, label = _history()
    t = 10 * DAY
    shadow += [{"ts": t, "cid": "new-hi", "p": 0.8, "fp": "f"},
               {"ts": t + 1, "cid": "new-lo", "p": 0.2, "fp": "f"}]
    label["new-hi"] = (10.0, t + 5000)
    label["new-lo"] = (-10.0, t + 5000)
    rows, counting = spr.grade(sorted(shadow, key=lambda s: s["ts"]), label,
                               {}, min_bin=20)
    by = {r["cid"]: r for r in rows}
    assert by["new-hi"]["enter"] is True and by["new-lo"]["enter"] is False
    assert counting["ok"] and counting["n"] == len(shadow)


def test_no_look_ahead_a_future_outcome_never_informs_a_past_decision():
    """The candidate's OWN outcome (and every later one) is a planted +1e6
    for low-p. If the grader peeked, the low-p bin would flip to enter."""
    shadow, label = _history()
    t = 10 * DAY
    shadow.append({"ts": t, "cid": "probe", "p": 0.2, "fp": "f"})
    label["probe"] = (1e6, t + 1)                    # resolves AFTER decision
    for j in range(40):                              # a flood of FUTURE lows
        cid = f"future{j}"
        shadow.append({"ts": t + 100 + j, "cid": cid, "p": 0.2, "fp": "f"})
        label[cid] = (1e6, t + 200 + j)
    rows, _ = spr.grade(sorted(shadow, key=lambda s: s["ts"]), label, {},
                        min_bin=20)
    assert next(r for r in rows if r["cid"] == "probe")["enter"] is False


def test_thin_bins_make_no_decision_and_unresolved_are_counted():
    shadow = [{"ts": float(i), "cid": f"c{i}", "p": 0.5, "fp": "f"}
              for i in range(10)]
    label = {f"c{i}": (5.0, 1000.0 + i) for i in range(8)}   # 2 unresolved
    rows, counting = spr.grade(shadow, label, {}, min_bin=20)
    assert rows == []
    assert counting["buckets"]["unresolved"] == 2
    assert counting["buckets"]["undecided"] == 8 and counting["ok"]


def test_promotion_stays_not_yet_below_the_registered_n():
    shadow, label = _history()
    t = 10 * DAY
    for j in range(30):
        cid = f"n{j}"
        shadow.append({"ts": t + j, "cid": cid, "p": 0.8, "fp": "f"})
        label[cid] = (40.0, t + 5000 + j * DAY)
    rows, counting = spr.grade(sorted(shadow, key=lambda s: s["ts"]), label,
                               {}, min_bin=20)
    s = spr.summarize(rows, counting, reps=200)
    assert s["promotion"].startswith("NOT YET")
    assert s["would_enter_label"]["n"] < spr.PROMOTE_MIN_N


def test_empty_inputs_render_without_error(tmp_path):
    shadow, label, traded = spr.load(tmp_path / "a.csv", tmp_path / "b.csv")
    rows, counting = spr.grade(shadow, label, traded)
    out = spr.render(spr.summarize(rows, counting, reps=50))
    assert "counting CS-1: n=0" in out and "NOT YET" in out
