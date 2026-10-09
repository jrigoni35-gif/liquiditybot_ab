import json, os, sys, collections, datetime as dt, statistics as stt
import numpy as np
SCR = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, SCR)
import s5_replay as R
T = R.trips
utc = lambda x: dt.datetime.fromtimestamp(x, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
def q(xs, f="%.1f"):
    xs = sorted(xs); n = len(xs)
    if not n: return "n=0"
    p = lambda a: xs[int(round(a * (n - 1)))]
    return ("n=%d mean=" + f + " med=" + f + " p10=" + f + " p90=" + f + " min=" + f + " max=" + f) % (n, stt.mean(xs), stt.median(xs), p(.1), p(.9), xs[0], xs[-1])

print("=== population ===")
print("trips replayable", len(T), "primary (exit<=2026-09-27T16:30:00Z)", sum(1 for t in T if t["exit_ts"] <= R.CUT))
print("entry ts bounds [%s, %s]" % (utc(min(t["entry_ts"] for t in T)), utc(max(t["entry_ts"] for t in T))))
print("cost src", collections.Counter(t["cost_src"] for t in T), "MED_COST", R.MED_COST)
print("decision src", collections.Counter(t["decision_src"] for t in T))

print("\n=== instrument checks ===")
# (a) sigma at decision vs signal_history sigma_bar_pct
rs = [R.sigma_at(t["symbol"], t["decision_ts"]) / t["sigma_entry_hist"] for t in T if t["sigma_entry_hist"]]
print("sigma replay/logged ratio", q(rs, "%.3f"))
# (b) path MFE/MAE over the REAL holding window vs trade_paths.csv (bot's own marks)
em, ea = [], []
for t in T:
    D = R.DATA[t["symbol"]]
    i0 = np.searchsorted(D["gt"], t["entry_ts"], "right"); i1 = np.searchsorted(D["gt"], t["first_exit_ts"], "left")
    g = t["dir"] * (D["g"][i0:i1] / t["entry_px"] - 1) * 1e4
    t["path_mfe"] = max(float(g.max()), 0.0); t["path_mae"] = min(float(g.min()), 0.0)
    em.append(t["path_mfe"] - 100 * float(t["tp_mfe"])); ea.append(t["path_mae"] - 100 * float(t["tp_mae"]))
print("MFE 5s-path minus trade_paths (bps)", q(em)); print("MAE 5s-path minus trade_paths (bps)", q(ea))
# same instrument as ml/postmortem._excursions: 30s marks + 8*MAD clip
em2, ea2 = [], []
for t in T:
    D = R.DATA[t["symbol"]]
    i0 = np.searchsorted(D["gt"], t["entry_ts"], "right"); i1 = np.searchsorted(D["gt"], t["first_exit_ts"], "left")
    pr = list(D["g"][i0:i1:6]) or [t["entry_px"]]
    med = sorted(pr)[len(pr) // 2]; dv = sorted(abs(p - med) for p in pr); mad = dv[len(dv) // 2] or med * 1e-4
    cl = [p for p in pr if abs(p - med) <= 8 * mad] or pr
    rel = [t["dir"] * (p - t["entry_px"]) / t["entry_px"] * 1e4 for p in cl]
    em2.append(max(rel + [0.0]) - 100 * float(t["tp_mfe"])); ea2.append(min(rel + [0.0]) - 100 * float(t["tp_mae"]))
print("MFE 30s+MAD-clip path minus trade_paths (bps)", q(em2)); print("MAE 30s+MAD-clip path minus trade_paths (bps)", q(ea2))
# logged high_water at give-back exits vs replay path peak
hw = []
for t in T:
    f = t.get("log_floor")
    if t["exit_reason"] == "tier trail" and f:
        D = R.DATA[t["symbol"]]
        i0 = np.searchsorted(D["gt"], t["entry_ts"], "right"); i1 = np.searchsorted(D["gt"], f["t"], "right")
        seg = D["g"][i0:i1]; pk = seg.max() if t["long"] else seg.min()
        hw.append(t["dir"] * (pk - f["hw"]) / t["entry_px"] * 1e4)
print("replay peak minus LOGGED high_water at trail exit (bps)", q(hw))
# (c) execution slip: trail exits, realized fill vs logged mark at trigger; tb_time realized vs grid mark at exit
s_tr = [t["dir"] * (t["log_floor"]["px"] - t["exit_px"]) / t["entry_px"] * 1e4 for t in T if t["exit_reason"] == "tier trail" and t["log_floor"]]
S_EXEC = stt.mean(s_tr)
print("s_exec (trail: logged trigger mark -> realized fill, bps, + worse)", q(s_tr), "-> S_EXEC=%.2f" % S_EXEC)
s_tm = []
for t in T:
    if t["exit_reason"] == "tb_time":
        D = R.DATA[t["symbol"]]; i = np.searchsorted(D["gt"], t["first_exit_ts"] - 5.0, "right") - 1
        s_tm.append(t["dir"] * (D["g"][i] / t["entry_px"] - 1) * 1e4 - t["dir"] * (t["exit_px"] / t["entry_px"] - 1) * 1e4)
print("tb_time: grid mark one cycle before fill minus realized (bps)", q(s_tm))
dl = [t["first_exit_ts"] - (t["decision_ts"] + R.H36) for t in T if t["exit_reason"] == "tb_time"]
print("tb_time: real first exit fill minus (decision_ts + 36h), s", [round(x, 1) for x in dl])
# (d) real stop level reproduction: nudge(0.75*pt) vs traded stop
ds = [abs(R.stop_price(t, 1.0000001) / R.stop_price(t, 1.0) - 1) * 1e4 for t in T if t["sh_sl"]]
print("stop rebuilt from nudge(0.75*pt) vs traded stop |diff| bps", q(ds, "%.2f"))

VARS = collections.OrderedDict([
    ("V0  live rule (control)", dict(H=R.H36, trail=dict(arm="live"))),
    ("V0s static arm 0.6 (belief)", dict(H=R.H36, trail=dict(arm="static", arm_pct=0.6))),
    ("V0n arm 0.6, NO cost floor", dict(H=R.H36, trail=dict(arm="static", arm_pct=0.6, cost_floor=False))),
    ("V1  barriers x1, no trail", dict(H=R.H36)),
    ("V1L literal 180/135, no trail", dict(H=R.H36, literal=(180, 135))),
    ("V2  arm 1.5 lock .6", dict(H=R.H36, trail=dict(arm="static", arm_pct=1.5))),
    ("V3  x1.5, no trail, 54h", dict(H=R.H36 * 1.5, k=1.5)),
    ("V3L literal 270/203 54h", dict(H=R.H36 * 1.5, literal=(270, 202.5))),
    ("V4  x2, no trail, 72h", dict(H=R.H36 * 2, k=2.0)),
    ("V4L literal 360/270 72h", dict(H=R.H36 * 2, literal=(360, 270))),
    ("V5  V1 + PT maker 15", dict(H=R.H36, pt_fee=R.FEE_MK)),
])
RES = {name: [R.replay(t, V, S_EXEC) for t in T] for name, V in VARS.items()}

print("\n=== CONTROL: V0 vs reality (per trip) ===")
V0 = RES["V0  live rule (control)"]
conf = collections.Counter(); err = []; terr = []; err_by = collections.defaultdict(list)
for t, r in zip(T, V0):
    if r["censored"]:
        conf[(t["exit_reason"], "CENSORED")] += 1; continue
    conf[(t["exit_reason"], r["reason"])] += 1
    e_ = r["gross"] - t["gross_pct"] * 100
    err.append(e_); err_by[t["exit_reason"]].append(e_)
    terr.append((r["t_exit"] - t["first_exit_ts"]) / 60)
    t["v0"] = r
agree = sum(v for (a, b), v in conf.items() if a == b)
print("reason agreement %d/%d" % (agree, sum(conf.values())), dict(conf))
print("gross error sim-real (bps)", q(err)); print("|gross error| bps", q([abs(x) for x in err]))
for k, v in err_by.items(): print("  by real reason", k, q(v))
print("exit time error sim-real (min)", q(terr))
print("share |err|<=10bps: %.2f  <=25bps: %.2f" % (np.mean([abs(x) <= 10 for x in err]), np.mean([abs(x) <= 25 for x in err])))
print("real mean gross %.1f  sim mean gross %.1f (same trips)" % (stt.mean(t["gross_pct"] * 100 for t, r in zip(T, V0) if not r["censored"]), stt.mean(r["gross"] for r in V0 if not r["censored"])))
bad = sorted(((abs(r["gross"] - t["gross_pct"] * 100), t["pid"][:8], t["symbol"], t["exit_reason"], r["reason"], round(t["gross_pct"] * 100, 1), round(r["gross"], 1), round((r["t_exit"] - t["first_exit_ts"]) / 60, 1)) for t, r in zip(T, V0) if not r["censored"]), reverse=True)[:10]
print("worst 10 (|err|, pid, sym, real, sim, real_gross, sim_gross, dt_min):"); [print("  ", b) for b in bad]

# ---- harness mutation checks: the control comparison must go RED on planted defects ----
def ctl(rr):
    ok = [(t, r) for t, r in zip(T, rr) if not r["censored"]]
    ag = sum(1 for t, r in ok if t["exit_reason"] == r["reason"])
    ae = stt.median(abs(r["gross"] - t["gross_pct"] * 100) for t, r in ok)
    return "agree %d/%d  median|err| %.1f bps" % (ag, len(ok), ae)
print("UNMUTATED control     :", ctl(V0))
M1 = [R.replay(dict(t, dir=-t["dir"], long=not t["long"]), VARS["V0  live rule (control)"], S_EXEC) for t in T]
print("M1 direction flipped  :", ctl(M1))
for sh_h in (1, 24):
    M2 = [R.replay(dict(t, entry_ts=t["entry_ts"] + 3600 * sh_h, decision_ts=t["decision_ts"] + 3600 * sh_h), VARS["V0  live rule (control)"], S_EXEC) for t in T]
    print("M2 clock +%dh          :" % sh_h, ctl(M2))
# how often did the vol-scaled arm (2*sigma) exceed the cost-floor arm during a hold?
nv = 0
for t in T:
    D = R.DATA[t["symbol"]]
    i0 = np.searchsorted(D["bclose"], t["entry_ts"], "right") - 1; i1 = np.searchsorted(D["bclose"], t["first_exit_ts"], "right")
    if np.nanmax(2 * D["sig"][i0:i1] * 100) > t["est_cost_bps"] / 0.6: nv += 1
print("trips where 2*sigma arm ever exceeded the cost-floor arm during the hold: %d/%d" % (nv, len(T)))
print("effective arm (cost floor) pct:", q([t["est_cost_bps"] / 0.6 / 100 for t in T], "%.3f"))
print("M3 = V0n (arm floor removed):", ctl(RES["V0n arm 0.6, NO cost floor"]))
M4 = [R.replay(t, dict(H=R.H36, trail=dict(arm="live"), k=1.5), S_EXEC) for t in T]
print("M4 barriers x1.5      :", ctl(M4))

json.dump(dict(RES=RES, S_EXEC=S_EXEC), open(os.path.join(SCR, "results.json"), "w"), default=str)
json.dump(T, open(os.path.join(SCR, "trips5.json"), "w"), default=str)

# ---------------- stats ----------------
def boot(vals, days, reps=4000, seed=7):
    blocks = collections.defaultdict(list)
    for v, d in zip(vals, days): blocks[d].append(v)
    keys = sorted(blocks); B = [np.asarray(blocks[k]) for k in keys]; dN = len(B)
    rng = np.random.default_rng(seed); m = np.empty(reps)
    for i in range(reps):
        idx = rng.integers(0, dN, size=dN); m[i] = np.concatenate([B[j] for j in idx]).mean()
    lo, hi = np.percentile(m, [2.5, 97.5])
    v = np.asarray(vals); neff = len(v) * (v.var(ddof=1) / len(v)) / m.var(ddof=1)
    return float(v.mean()), float(lo), float(hi), dN, float(neff)

def summarize(pop_name, keep):
    print(f"\n=== VARIANTS on {pop_name} ===")
    print("%-30s %4s %4s %6s %7s %8s %7s %7s  %-24s %6s %5s  %s" % ("variant", "n", "cens", "p", "a_eff", "b_eff", "C", "p*", "mean net [95% day-block]", "days", "n_eff", "exit mix"))
    base = None
    for name, rr in RES.items():
        rows = [(t, r) for t, r in zip(T, rr) if keep(t) and not r["censored"]]
        cens = sum(1 for t, r in zip(T, rr) if keep(t) and r["censored"])
        g = [r["gross"] for _, r in rows]; net = [r["net"] for _, r in rows]; C = stt.mean(r["fee"] for _, r in rows)
        w = [x for x in g if x > 0]; l = [x for x in g if x <= 0]
        p = len(w) / len(g); a = stt.mean(w); b = stt.mean(l)
        pstar = (abs(b) + C) / (a + abs(b))
        days = [dt.datetime.fromtimestamp(t["entry_ts"], dt.timezone.utc).strftime("%Y-%m-%d") for t, _ in rows]
        m, lo, hi, dN, neff = boot(net, days)
        mix = collections.Counter(r["reason"] for _, r in rows)
        mixs = " ".join(f"{k.replace('tier trail','trail')}:{v/len(rows):.2f}" for k, v in sorted(mix.items()))
        print("%-30s %4d %4d %6.3f %7.1f %8.1f %7.1f %7.3f  %+6.1f [%+6.1f, %+6.1f] %6d %5.1f  %s" % (name, len(rows), cens, p, a, b, C, pstar, m, lo, hi, dN, neff, mixs))
summarize("PRIMARY 73 (exit<=16:30Z), each variant on its own uncensored trips", lambda t: t["exit_ts"] <= R.CUT)
cm = [all(not RES[n][i]["censored"] for n in RES) for i in range(len(T))]
CM = {T[i]["pid"] for i in range(len(T)) if cm[i]}
summarize(f"COMMON SAMPLE ({sum(1 for t in T if t['pid'] in CM and t['exit_ts'] <= R.CUT)} of 73 uncensored under ALL variants)", lambda t: t["pid"] in CM and t["exit_ts"] <= R.CUT)

# paired differences vs V0 on the common sample, day-block CI
print("\n=== PAIRED net difference vs V0 (common sample, day-block by entry day, 4000 reps seed 7) ===")
idx = [i for i in range(len(T)) if T[i]["pid"] in CM and T[i]["exit_ts"] <= R.CUT]
days = [dt.datetime.fromtimestamp(T[i]["entry_ts"], dt.timezone.utc).strftime("%Y-%m-%d") for i in idx]
for name, rr in RES.items():
    diff = [rr[i]["net"] - V0[i]["net"] for i in idx]
    m, lo, hi, dN, neff = boot(diff, days)
    print("%-30s mean diff %+6.1f bps [%+6.1f, %+6.1f]  n=%d days=%d" % (name, m, lo, hi, len(idx), dN))
# real-ledger reference on the same 73
P = [t for t in T if t["exit_ts"] <= R.CUT]
days = [dt.datetime.fromtimestamp(t["entry_ts"], dt.timezone.utc).strftime("%Y-%m-%d") for t in P]
net_real_spec = [t["gross_pct"] * 100 - (R.FEE_IN + (R.FEE_TK)) for t in P]
m, lo, hi, dN, neff = boot(net_real_spec, days)
print("\nREAL ledger gross, fee spec 15+30: mean net %+.1f [%+.1f, %+.1f] days=%d n_eff=%.1f" % (m, lo, hi, dN, neff))
m, lo, hi, dN, neff = boot([1e4 * t["net_usd"] / t["ticket_usd"] for t in P], days)
print("REAL ledger net as booked: mean %+.1f [%+.1f, %+.1f]" % (m, lo, hi))
print("censored trips per variant (all 74):", {n: [T[i]["pid"][:8] for i in range(len(T)) if RES[n][i]["censored"]] for n in RES})
