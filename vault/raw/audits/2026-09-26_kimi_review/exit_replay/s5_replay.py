"""Counterfactual exit replay, era-9 5m trips. Scratch-only; reads scratch copies."""
import json, os, sys, math, glob, collections, datetime as dt, statistics as stt
import numpy as np, pandas as pd
WT = r"C:\Users\haird\Documents\liquiditybot\liquiditybot_ab\.claude\worktrees\vscode-bridge-5548d1"
sys.path.insert(0, WT)
from risk.stop_placement import nudge_stop_off_round  # the live helper, not a copy
SCR = os.path.dirname(os.path.abspath(__file__))
CUT = dt.datetime(2026, 9, 27, 16, 30, tzinfo=dt.timezone.utc).timestamp()
PAIR = {"BTC/USD": "XBTUSD", "ETH/USD": "ETHUSD", "LINK/USD": "LINKUSD", "PAXG/USD": "PAXGUSD"}
GRID = 5.0          # fast-cycle cadence (measured trigger->fill delay 4.5-6.1 s)
BAR = 300
H36 = 432 * BAR
FEE_IN, FEE_TK, FEE_MK = 15.0, 30.0, 15.0
ROUND_BAND, ROUND_OFF = 5.0, 5.0        # config risk.stop_round_*_bps (stable across era)
MAG_BAND = 25.0                          # profit_taking.stop_magnet.band_bps
GB_FRAC, GB_TIGHT_GAIN, GB_TIGHT_FRAC, GB_VOL_MULT = 0.4, 4.0, 0.25, 2.0

trips = json.load(open(os.path.join(SCR, "trips4.json")))
if os.environ.get("ONLY_SYMS"):
    trips = [t for t in trips if t["symbol"] in os.environ["ONLY_SYMS"].split(",")]

# ---------------- price data: Kraken public trades (scratch backfill) --------
def load_pair(p):
    fs = sorted(glob.glob(os.path.join(SCR, "ticks", "kraken", p, "*.parquet")))
    df = pd.concat([pd.read_parquet(f) for f in fs]).drop_duplicates("trade_id").sort_values(["time_s", "trade_id"])
    return df
DATA = {}
ONLY = os.environ.get("ONLY_SYMS")
for sym, p in PAIR.items():
    if ONLY and sym not in ONLY.split(","):
        continue
    df = load_pair(p)
    t = df.time_s.to_numpy(); px = df.price.to_numpy()
    t0 = math.floor(t[0] / BAR) * BAR
    # 5s grid, last trade in (k-1)*5, k*5] -> mark at grid time k*5 (ffill)
    gidx = np.floor((t - t0) / GRID).astype(np.int64) + 1
    n = int(gidx[-1]) + 1
    g = np.full(n, np.nan); g[gidx] = px          # later trades overwrite -> last
    g = pd.Series(g).ffill().to_numpy()
    gt = t0 + np.arange(n) * GRID
    # committed 5m bars
    b = pd.DataFrame({"b": np.floor((t - t0) / BAR).astype(np.int64), "px": px})
    o = b.groupby("b").px.agg(["first", "max", "min", "last"])
    o = o.reindex(np.arange(o.index.min(), o.index.max() + 1))
    o["last"] = o["last"].ffill()
    for c in ("first", "max", "min"):
        o[c] = o[c].fillna(o["last"])
    bt = t0 + o.index.to_numpy() * BAR          # bar open time
    c = o["last"].to_numpy(); h = o["max"].to_numpy(); l = o["min"].to_numpy()
    # sigma over last 100 committed bars, as regime/vol_regime.py (0.5 cc std + 0.5 Parkinson RMS)
    lr = np.diff(np.log(c), prepend=np.nan)
    pk = (np.log(h / l)) ** 2 / (4 * np.log(2))
    cc = pd.Series(lr).rolling(99).std(ddof=0).to_numpy()   # np.std of 99 diffs of 100 closes
    pkr = np.sqrt(pd.Series(pk).rolling(100).mean().to_numpy())
    sig = 100 * (0.5 * cc + 0.5 * pkr)          # pct, available at bar CLOSE = bt+BAR
    DATA[sym] = dict(gt=gt, g=g, bclose=bt + BAR, sig=sig, tmin=t[0], tmax=t[-1], ntr=len(t))
    print(f"{sym} {p}: trades={len(t)} first={dt.datetime.fromtimestamp(t[0], dt.timezone.utc).isoformat()} "
          f"last={dt.datetime.fromtimestamp(t[-1], dt.timezone.utc).isoformat()} grid_n={n} empty_5m_bars={int(b.groupby('b').size().reindex(o.index).isna().sum())}")

def sigma_at(sym, ts):
    D = DATA[sym]; i = np.searchsorted(D["bclose"], ts, side="right") - 1
    return D["sig"][i] if i >= 0 else np.nan

def magnet(direction_long, px):
    """risk/profit_tiers.py ProfitTierEngine._magnet_adjust, vectorized."""
    g = 10.0 ** np.round(np.log10(px) - 2.0)
    if direction_long:
        m = np.ceil(px / g) * g
        hit = (m - px) / px * 1e4 < MAG_BAND
        return np.where(hit, np.minimum(px, m * (1 - MAG_BAND / 1e4)), px)
    m = np.floor(px / g) * g
    hit = (px - m) / px * 1e4 < MAG_BAND
    return np.where(hit, np.maximum(px, m * (1 + MAG_BAND / 1e4)), px)

# ---------------- per-trip inputs ----------------
for t in trips:
    t["long"] = t["dir"] == 1
    t["pt_frac"] = float(t["a_pt061_pt"])
    t["sigma_entry_hist"] = float(t["sh_sigma"]) if t["sh_sigma"] else None
    dec = [a for a in t["a_other"] if a[0] == "ML-070"]
    t["decision_ts"] = dec[0][1] if dec else t["entry_ts"]
    t["decision_src"] = "ML-070" if dec else "first entry fill"
    # est_cost_bps: floor-binding (pt > 8*sigma) -> pt/4 exactly [K-derived]; else median of floor-binding [I]
fb = [t["pt_frac"] * 1e4 / 4 for t in trips if t["sigma_entry_hist"] and 8 * t["sigma_entry_hist"] / 100 < t["pt_frac"] - 1e-5]
MED_COST = float(np.median(fb))
for t in trips:
    if os.environ.get("COST_MODE") == "pt4" or t["sigma_entry_hist"] is None or 8 * t["sigma_entry_hist"] / 100 < t["pt_frac"] - 1e-5:
        t["est_cost_bps"] = t["pt_frac"] * 1e4 / 4; t["cost_src"] = "pt/4 (floor-binding)" if t["sigma_entry_hist"] else "pt/4 (ASSUMED floor-binding, no sh row)"
    else:
        t["est_cost_bps"] = min(MED_COST, t["pt_frac"] * 1e4 / 4); t["cost_src"] = "median floor-binding cost [I]"

def stop_price(t, k, literal=None):
    e = t["entry_px"]
    if literal is None and k == 1.0 and t["sh_sl"]:
        return float(t["sh_entry"]) * (1 - t["dir"] * float(t["sh_sl"]))   # the traded stop, post-nudge
    sl = (literal[1] / 1e4) if literal else 0.75 * t["pt_frac"] * k
    raw = e * (1 - t["dir"] * sl)
    return nudge_stop_off_round(raw, "long" if t["long"] else "short", ROUND_BAND, ROUND_OFF)

def replay(t, V, s_exec):
    D = DATA[t["symbol"]]
    e, d = t["entry_px"], t["dir"]
    H = V["H"]
    deadline = t["decision_ts"] + H
    i0 = np.searchsorted(D["gt"], t["entry_ts"], side="right")        # first cycle after the fill
    i1 = np.searchsorted(D["gt"], deadline, side="left")               # first cycle at/after deadline
    censored = False
    if i1 >= len(D["gt"]) or D["gt"][min(i1, len(D["gt"]) - 1)] > D["tmax"] + GRID:
        censored = True
        i1 = len(D["gt"]) - 1
    gt = D["gt"][i0:i1 + 1]; px = D["g"][i0:i1 + 1]
    gain = d * (px / e - 1) * 1e4                                     # bps
    lit = V.get("literal")
    k = V.get("k", 1.0)
    stop = stop_price(t, k, lit)
    g_stop = d * (stop / e - 1) * 1e4
    pt = (lit[0] / 1e4) if lit else t["pt_frac"] * k
    g_pt = pt * 1e4
    n = len(gt)
    INF = n + 10
    def first(mask):
        w = np.flatnonzero(mask)
        return int(w[0]) if len(w) else INF
    i_sl = first(gain <= g_stop)
    i_pt = first(gain >= g_pt)
    i_tr = INF
    trail_stop = None
    if V.get("trail"):
        hwg = np.maximum.accumulate(np.maximum(gain, 0.0))           # peak gain bps (hw starts at entry)
        tr = V["trail"]
        if tr["arm"] == "live":
            bi = np.searchsorted(D["bclose"], gt, side="right") - 1
            sig = np.where(bi >= 0, D["sig"][np.maximum(bi, 0)], np.nan)
            arm = np.where(np.isfinite(sig), GB_VOL_MULT * sig, 0.6) * 100          # bps
            arm = np.maximum(arm, t["est_cost_bps"] / max(1 - GB_FRAC, 0.05))
        else:
            arm = np.full(n, tr["arm_pct"] * 100.0)
            if tr.get("cost_floor", True):
                arm = np.maximum(arm, t["est_cost_bps"] / max(1 - GB_FRAC, 0.05))
        armed = hwg >= arm
        frac = np.where(hwg >= GB_TIGHT_GAIN * 100, GB_TIGHT_FRAC, GB_FRAC)
        hw_px = e * (1 + d * hwg / 1e4)
        cand_px = e + d * (1 - frac) * np.abs(hw_px - e)
        cand_px = magnet(t["long"], cand_px)
        cand_g = np.where(armed, d * (cand_px / e - 1) * 1e4, -np.inf)
        stop_g = np.maximum.accumulate(cand_g)
        i_tr = first(np.isfinite(stop_g) & (gain <= stop_g))
        trail_stop = stop_g
    # priority inside one cycle: hard stop > give-back floor > pt > deadline
    cand = [(i_sl, 0, "tb_sl"), (i_tr, 1, "tier trail"), (i_pt, 2, "tb_pt")]
    i, _, why = min(cand)
    if i >= INF:
        if censored:
            return dict(censored=True)
        i, why = n - 1, "tb_time"
    if why == "tb_time" and censored:
        return dict(censored=True)
    if why == "tb_sl":
        g_exit = min(g_stop, gain[i]) - s_exec; fee = FEE_TK
    elif why == "tier trail":
        g_exit = min(trail_stop[i], gain[i]) - s_exec; fee = FEE_TK
    elif why == "tb_pt":
        g_exit = g_pt; fee = V.get("pt_fee", FEE_TK)
    else:
        g_exit = gain[i] - s_exec; fee = FEE_TK
    mfe = float(np.max(gain[:i + 1])); mae = float(np.min(gain[:i + 1]))
    return dict(censored=False, reason=why, gross=float(g_exit), net=float(g_exit - FEE_IN - fee), fee=FEE_IN + fee,
                t_exit=float(gt[i]), mfe=mfe, mae=mae, stop=stop, pt=pt)

if __name__ == "__main__":
    pass
