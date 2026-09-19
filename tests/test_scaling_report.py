"""Tests for scripts/scaling_report.py — the SAFE scaling-benefit instrument.

REPORT-ONLY. It computes what a cost-aware scaling system WOULD change;
it never sizes, places, or gates anything. The registered era-9 statistic
lives in scripts/era_readout.py — this tool reads the same fills for
distributional parameters but is NOT the registration and says so on its
own output.
"""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
import scaling_report as sr  # noqa: E402


# --- 1. cost floor -------------------------------------------------------

def test_cost_floor_grows_with_friction_not_ticket():
    # break-even edge (bps) for a round trip at fee+adverse friction
    assert sr.cost_floor_bps(60.0, 45.5, 15.0) == 60.5
    # friction is ticket-independent in bps, so the floor is too — the
    # lever is that gross edge must be MEASURED per setup; the floor
    # only sets the kill line
    assert sr.cost_floor_bps(250.0, 45.5, 15.0) == 60.5
    # a maker-rebate tier (near-zero fees) drops the kill line to the
    # adverse component alone
    assert sr.cost_floor_bps(60.0, 2.0, 15.0) == 17.0


def test_net_after_cost_sign():
    # gross 3 bps median vs 60.5 bps floor -> negative, ~20:1 short
    assert sr.net_after_cost_bps(3.0, 60.5) < 0
    assert abs(sr.net_after_cost_bps(3.0, 60.5) - (-57.5)) < 1e-9


# --- 2. tier roll economics ----------------------------------------------

def test_tier_roll_table_orders_by_cost():
    ladder = [(0.0, 40.0, 80.0), (2500.0, 30.0, 60.0),
              (10000.0, 22.0, 38.0), (25000.0, 20.0, 35.0),
              (69652.0, 15.0, 30.0)]
    rows = sr.tier_roll_table(ladder, volume_30d=70000.0)
    costs = [r["round_trip_bps"] for r in rows]
    assert costs == sorted(costs)                 # non-increasing cost
    binding = sr.binding_tier(ladder, volume_30d=70000.0)
    assert binding["maker_bps"] == 15.0           # best volume row


# --- 3. edge-conditional size --------------------------------------------

def test_kelly_size_is_zero_without_edge():
    assert sr.kelly_size(edge_usd=0.0, var_usd=0.87 ** 2,
                         bankroll=800.0) == 0.0
    assert sr.kelly_size(edge_usd=-0.1, var_usd=0.87 ** 2,
                         bankroll=800.0) == 0.0


def test_kelly_size_quarter_kelly_math():
    # f* = edge/var (bankroll fraction); quarter-Kelly, $800 bankroll:
    # 0.25 * (0.40/0.7569) * 800 = 105.71
    got = sr.kelly_size(edge_usd=0.40, var_usd=0.87 ** 2, bankroll=800.0)
    assert abs(got - 105.694) < 0.001


def test_kelly_size_respects_cap():
    got = sr.kelly_size(edge_usd=4.0, var_usd=0.5, bankroll=800.0,
                        cap_usd=100.0)
    assert got == 100.0


# --- 4. era-9 distributional parameters ----------------------------------

def test_trip_params_from_synthetic_fills(tmp_path):
    import csv as csvmod
    f = tmp_path / "fills.csv"
    cols = ["ts", "position_id", "purpose", "symbol", "side",
            "fill_size", "fill_price", "fees_delta_usd", "exec_era"]
    rows = []
    for i in range(4):                            # two closed trips, era X
        rows.append([f"178900000{i}.0", f"p{1 + i // 2}",
                     "entry" if i % 2 == 0 else "exit", "BTCUSD",
                     "buy" if i % 2 == 0 else "sell",
                     "0.001", "100.0", "0.10", "X-1"])
    with open(f, "w", newline="") as fh:
        w = csvmod.writer(fh)
        w.writerow(cols)
        w.writerows(rows)
    p = sr.trip_params(f, era="X-1")
    assert p["n"] == 2
    assert abs(p["mean_net"] - (-0.20)) < 1e-9    # two trips, −0.10 fees each


def test_trip_params_excludes_other_eras(tmp_path):
    import csv as csvmod
    f = tmp_path / "fills.csv"
    cols = ["ts", "position_id", "purpose", "symbol", "side",
            "fill_size", "fill_price", "fees_delta_usd", "exec_era"]
    rows = [["1789000000.0", "p1", "entry", "BTCUSD", "buy", "0.001",
             "100.0", "0.10", "X-1"],
            ["1789000001.0", "p1", "exit", "BTCUSD", "sell", "0.001",
             "100.0", "0.10", "X-1"],
            ["1789000002.0", "p2", "entry", "BTCUSD", "buy", "0.001",
             "100.0", "0.05", "OLD-0"]]
    with open(f, "w", newline="") as fh:
        w = csvmod.writer(fh)
        w.writerow(cols)
        w.writerows(rows)
    p = sr.trip_params(f, era="X-1")
    assert p["n"] == 1


# --- 5. end-to-end packet is bounded and honest ---------------------------

def test_report_disclaims_not_the_registration():
    out = sr.build_report(REPO)
    assert "SCALING REPORT" in out
    assert "NOT the era-9 registration" in out
    assert len(out) < 20000
