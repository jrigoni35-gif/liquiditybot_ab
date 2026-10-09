# RAW — 2026-09-12/13 session, measured outputs

Captured verbatim so the source page's claims have a primary artifact behind
them. Repo `main` = `2dec30a3`. Every live-file value is AS-OF its stamp.

---

## A. NaN fail-open, live PreTradeGate from the shipped config

```
=== does a NaN config knob flip a REJECT into an APPROVE? ===
  BASELINE (shipped)                 approved=False  cost=54.300    edge=40.000
  impact_eta = NaN                   approved=True   cost=nan       edge=40.000
  adverse_selection_kappa = NaN      approved=True   cost=nan       edge=40.000
  maker_fill_p0 = NaN                approved=False  cost=54.300    edge=40.000
  miss_cost_bps = NaN                approved=False  cost=54.300    edge=40.000
```
(the two that do NOT flip feed PT-040, independently established unreachable)

```
=== config_guard, BEFORE the fix ===
  pretrade.impact_eta               NaN -> FATALs naming it: 0
  pretrade.maker_fill_p0            NaN -> FATALs naming it: 0
  pretrade.p_fill_floor             NaN -> FATALs naming it: 0
  pretrade.adverse_selection_kappa  NaN -> FATALs naming it: 0
  pretrade.miss_cost_bps            NaN -> FATALs naming it: 0

  json.loads({"x": NaN}) -> {'x': nan}  isnan= True
  json.dumps({"x": float("nan")}) -> {"x": NaN}
```

## B. Threshold fail-open, exploring lane

```
A) HIGH EDGE so PT-041 cannot mask the missing veto (alpha=5000):
    stale 1e6 ms, threshold OK                 approved=False  ['PT-020: 1000000ms']
    stale 1e6 ms, max_data_staleness_ms=NaN    approved=True   ['PT-000: edge 5010.0 / cost 54.']
    size 0.0001, min_order_usd=NaN             approved=True   ['PT-000: edge 5010.0 / cost 54.']

B) EXPLORING=True - the lane era-9 entries actually use:
    stale 1e6 ms, threshold OK                 approved=False  ['PT-020: 1000000ms']
    stale 1e6 ms, max_data_staleness_ms=NaN    approved=True   ['PT-050: edge 40.0/cost 54.3 EV']
    size 0.0001, min_order_usd=NaN             approved=True   ['PT-050: edge 40.0/cost 54.1 EV']

C) ml.exploration.enabled = True   bypass_pretrade_ev = True
```

## C. Validator crash

```
  float(10**400) RAISES OverflowError: int too large to convert to float
  validate() RAISES OverflowError: int too large to convert to float
  json.loads(400-digit literal) -> type int len 400
  json.loads(1e400) -> inf  (float - handled)

traceback sites, found one at a time:
  config_guard.py:686  val = float(raw)                      (clamped loop)
  config_guard.py:734  if raw is not None and float(raw)==0  (disabling-zero)
  + the sweep added the same day (guarded first, was not the live crash)

AFTER the class fix:
  10**400 huge int   -> FATAL:2 WARN:0  no crash
  -10**400           -> FATAL:2 WARN:0  no crash
  inf                -> FATAL:2 WARN:0  no crash
  nan                -> FATAL:2 WARN:0  no crash
  string 0.8x        -> FATAL:1 WARN:0  no crash
  0.8 normal         -> FATAL:0 WARN:0  no crash
  0.0 disabling      -> FATAL:0 WARN:1  no crash   <- the arm the fix could have swallowed
  shipped FATALs: 0
```

## D. OF-3 row sensitivity (scripts/pbo_row_sensitivity.py)

```
corpus: live history (18043 rows)   T=18043   n_live=63   adaptive_rung=in
DETERMINISM CONTROL  same array twice -> 0.128571 vs 0.128571   identical=True

     rows       pbo   ncfg   median_lambda  verdict
    18043    0.1286      6         +1.7918  green
    18042    0.1286      6         +1.7918  green
    18041    0.1143      6         +1.7918  green
    18040    0.1143      6         +1.7918  green
    18038    0.1143      6         +1.7918  green
    18033    0.3000      6         +1.7918  green
  band over the sweep = 0.1857     gate = 0.5      0/6 RED
```
Earlier the same day, at T=18,020: 0.1857 / 0.1857 / 0.1857 / **0.9000** /
0.9000 / 0.6286 — band **0.7143**, 3 of 6 RED. Both deterministic.

## E. Horizon re-read (scripts/horizon_report.py, 52,402 rows)

```
best horizon per asset (by mean net return, >= 20 samples):
  ADA 108 -0.529% | ARB 216 -0.364% | AVAX 432 -0.439% | BTC 108 -0.524%
  DOGE 216 -0.369% | DOT 432 -0.267% | ETH 108 -0.600% | FLOW 108 -0.864%
  LINK 216 -0.541% | LTC 108 -0.429% | MINA 432 -0.555% | PAXG 432 -0.503%
  SOL 216 -0.376% | SUI 216 -0.489% | XRP 216 -0.292%

  assets: 15  best-horizon counts: {'108': 5, '216': 6, '432': 4}
    H=108  wins  5/15 = 33%   (chance = 33%)
    H=216  wins  6/15 = 40%   (chance = 33%)
    H=432  wins  4/15 = 27%   (chance = 33%)
```
45 of 45 asset×horizon cells negative.

## F. Panel 43

```
shipped: "expr": "max(liquiditybot_overfit_rung_passed{job=\"liquiditybot\"})"
legend : {{rung}}
rung values today: {dof:1, dsr:0, pbo:1, purge:1, shuffle:1}  -> renders ONE bar at 1.0
fixed  : "max by (rung) (liquiditybot_overfit_rung_passed{job=\"liquiditybot\"})"
blast radius: 120 panels scanned INCLUDING 9 nested in collapsed rows -> 0 other offenders
```

## G. E_net error budget, shipped geometry (day-block CIs)

```
ERROR BUDGET - candidate, PT=180bps SL=135bps, n=553   <== SHIPPED GEOMETRY
  outcome mix: PT 0.2676 | SL 0.6203 | timeout 0.1121   (5 day blocks)
  win capture   p1*P    +48.2   [ +20.9, +62.9]
  loss          -p2*S   -83.7   [ -96.0, -71.5]
  timeout drift  p3*T    +1.0   [  +0.2,  +3.9]
  cost          -c      -45.0   [ -45.0, -45.0]
  E_net TOTAL           -79.5   [-115.1, -62.1]
    cost -> 0 (zero-fee fantasy) =    -34.5 bps   <-- STILL NEGATIVE
    resolved hit rate q=0.3014  required q*=0.5858
```
Validation gate: 14 of 14 segments reconciled on two independent cost routes.

## H. Process window — 14 geometries the corpus actually ran

```
   geometries scanned: 14     POSITIVE E_net: 0     NEGATIVE: 14
   corr(PT width, E_net) = -0.573  (confounded with regime; 14 points)
```
Caveat carried: the "would open at zero cost" column is misleading — at zero
cost the σ floor stops binding and the geometry becomes σ-driven, a different
process.

## I. MEEF — fee → label amplification

```
  cost%   PT bps   SL bps   dPT/dcost   PT/cost   two-outcome p*
   0.30    120.0     90.0                  4.00   0.571429
   0.45    180.0    135.0        4.00      4.00   0.571429
   1.20    480.0    360.0        4.00      4.00   0.571429
```
dPT/dcost = 4.00 exactly. Break-even 4/7 INDEPENDENT of c at the floor.
Predicts cut #10's error: 10 bp fee mis-book → 40 bp label error; observed
220 → 180 = exactly 40.

## J. Exit legs

```
era 12-10d4d0c2: exits 17/17 booked TAKER 30bps, 0 post_only
                 entries 16/18 post_only, booked MAKER 15bps
realized round trip = 15 + 30 = 45.00 bps == label_round_trip_cost_pct
zero market orders in 1,297 fill rows, any era
maker_first_profit_exits=true reaches only tb_pt (1 of 17 exits);
  "tier trail" is 7 of 17 and goes marketable, because is_profit_take is set
  ONLY in the tier-FIRED branch (risk/profit_tiers.py:820-822)
```

## K. Kraken websocket stability (full-range, 1,335,373 log lines)

```
checksum              0
resubscribe           0
ws disconnects        ~5-12/day, EVERY one logged "attempt 1"
since the 18:29 restart: 0
kraken_max_book_age_sec 3.5 < pretrade.max_data_staleness_ms 4.0  OK
```
