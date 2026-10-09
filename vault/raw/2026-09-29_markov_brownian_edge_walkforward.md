# Raw — markov_edge_report full run (verbatim stdout)

Snapshot: outputs/signal_history.csv copied 2026-09-29T20:10:58Z, sha256 prefix c732f653e3d853b, 34771 lines. Command: python scripts/markov_edge_report.py --history <snapshot> (NULL_REPS 200, SEED 7). Repo: liquiditybot_ab branch claude/claude-rc-8e3b3f on 40658e15d + uncommitted research files.

```
markov_edge - walk-forward, 6929 rows over 22 days; base P(up first) resolved = 0.517
counting CS-1: n=34770 = not_candidate_tb=5203 + pre_era9=22638 + unparseable=0 + burn_in_train_only=2077 + scored=4852 [OK]

spec            variant  days  gain(nats/row)  [95% CI]              null_p  | within-day AUC [95% CI]      null_p  | uplift(bps)  [95% CI]        taken/rows
pooled          static     14  -0.03649  [-0.08326,+0.00845]  1.000  | 0.500 [0.500,0.500]  1.000  |    +19.7  [-43.1,+89.5]  45/4852
pooled          chain      14  -0.03649  [-0.08483,+0.01144]  1.000  | 0.500 [0.500,0.500]  1.000  |    +19.7  [-45.5,+97.0]  45/4852
hmm             static     14  -0.03595  [-0.08411,+0.00334]  1.000  | 0.524 [0.449,0.603]  0.015  |    -11.1  [-71.6,+45.1]  151/4852
hmm             chain      14  -0.03207  [-0.07721,+0.00914]  0.005  | 0.500 [0.420,0.585]  0.990  |    +16.3  [-39.6,+74.9]  28/4852
basis           static     14  -0.03016  [-0.07689,+0.01317]  0.010  | 0.533 [0.508,0.560]  0.010  |    -15.9  [-57.1,+27.5]  323/4852
basis           chain      14  -0.03459  [-0.08183,+0.00886]  0.955  | 0.525 [0.494,0.554]  0.104  |     -1.3  [-53.9,+60.8]  25/4852
disloc          static     14  -0.03655  [-0.07126,-0.00513]  0.876  | 0.488 [0.410,0.559]  0.289  |    -31.5  [-82.1,+15.7]  392/4852
disloc          chain      14  -0.04716  [-0.10547,+0.00434]  1.000  | 0.466 [0.384,0.552]  0.030  |    -40.3  [-87.5,-2.2]  106/4852
basis_x_disloc  static     14  -0.02952  [-0.06000,-0.00044]  0.547  | 0.524 [0.469,0.572]  0.050  |    -47.8  [-88.8,-9.7]  490/4852
basis_x_disloc  chain      14  -0.03736  [-0.08746,+0.00547]  1.000  | 0.466 [0.377,0.551]  0.010  |    -38.9  [-96.7,+0.0]  9/4852
hmm_x_basis     static     14  -0.02337  [-0.05766,+0.00855]  0.612  | 0.558 [0.514,0.603]  0.005  |    -12.0  [-78.7,+49.8]  315/4852
hmm_x_basis     chain      14  -0.02430  [-0.06139,+0.01197]  0.005  | 0.494 [0.412,0.578]  0.627  |     -0.7  [-2.2,+0.0]  13/4852

IN-SAMPLE state tables (descriptive, NOT evidence):
-- pooled
   s0   n= 6929 psi=+0.300 pL=0.466 pS=0.392 p*=0.571 best=skip  ev=  +0.0bps stay=1.00
-- hmm
   s0   n=    0 psi=+0.000 pL=0.429 pS=0.429 p*=0.571 best=skip  ev=  +0.0bps stay=0.17
   s1   n= 3224 psi=-0.075 pL=0.419 pS=0.438 p*=0.571 best=skip  ev=  +0.0bps stay=0.98
   s2   n=  162 psi=-1.375 pL=0.272 pS=0.596 p*=0.571 best=short ev=  +7.9bps stay=0.92
   s3   n= 2329 psi=+0.650 pL=0.509 pS=0.351 p*=0.571 best=skip  ev=  +0.0bps stay=0.98
   s4   n= 1040 psi=+1.275 pL=0.584 pS=0.282 p*=0.571 best=long  ev=  +4.2bps stay=0.96
   s5   n=  174 psi=-0.675 pL=0.348 pS=0.512 p*=0.571 best=skip  ev=  +0.0bps stay=0.97
-- basis
   s0   n= 2310 psi=+0.775 pL=0.524 pS=0.337 p*=0.571 best=skip  ev=  +0.0bps stay=0.39
   s1   n= 2309 psi=-0.225 pL=0.401 pS=0.456 p*=0.571 best=skip  ev=  +0.0bps stay=0.47
   s2   n= 2310 psi=+0.225 pL=0.456 pS=0.401 p*=0.571 best=skip  ev=  +0.0bps stay=0.38
-- disloc
   s0   n= 3600 psi=+0.150 pL=0.447 pS=0.410 p*=0.571 best=skip  ev=  +0.0bps stay=0.99
   s1   n= 1271 psi=+1.625 pL=0.625 pS=0.247 p*=0.571 best=long  ev= +17.0bps stay=0.70
   s2   n= 2058 psi=-0.375 pL=0.383 pS=0.475 p*=0.571 best=skip  ev=  +0.0bps stay=0.81
-- basis_x_disloc
   s0   n= 1203 psi=+0.525 pL=0.493 pS=0.365 p*=0.571 best=skip  ev=  +0.0bps stay=0.40
   s1   n=  461 psi=+1.925 pL=0.658 pS=0.219 p*=0.571 best=long  ev= +27.5bps stay=0.24
   s2   n=  646 psi=+0.275 pL=0.462 pS=0.395 p*=0.571 best=skip  ev=  +0.0bps stay=0.29
   s3   n= 1179 psi=-0.450 pL=0.374 pS=0.484 p*=0.571 best=skip  ev=  +0.0bps stay=0.51
   s4   n=  385 psi=+1.400 pL=0.599 pS=0.269 p*=0.571 best=long  ev=  +8.8bps stay=0.27
   s5   n=  745 psi=-0.950 pL=0.317 pS=0.545 p*=0.571 best=skip  ev=  +0.0bps stay=0.38
   s6   n= 1218 psi=+0.175 pL=0.450 pS=0.407 p*=0.571 best=skip  ev=  +0.0bps stay=0.39
   s7   n=  425 psi=+1.125 pL=0.566 pS=0.298 p*=0.571 best=skip  ev=  +0.0bps stay=0.25
   s8   n=  667 psi=-0.400 pL=0.380 pS=0.478 p*=0.571 best=skip  ev=  +0.0bps stay=0.28
-- hmm_x_basis
   s0   n=    0 psi=+0.000 pL=0.429 pS=0.429 p*=0.571 best=skip  ev=  +0.0bps stay=0.06
   s1   n=    0 psi=+0.000 pL=0.429 pS=0.429 p*=0.571 best=skip  ev=  +0.0bps stay=0.06
   s2   n=    0 psi=+0.000 pL=0.429 pS=0.429 p*=0.571 best=skip  ev=  +0.0bps stay=0.06
   s3   n= 1139 psi=+0.450 pL=0.484 pS=0.374 p*=0.571 best=skip  ev=  +0.0bps stay=0.39
   s4   n=  961 psi=-0.675 pL=0.348 pS=0.512 p*=0.571 best=skip  ev=  +0.0bps stay=0.40
   s5   n= 1124 psi=-0.150 pL=0.410 pS=0.447 p*=0.571 best=skip  ev=  +0.0bps stay=0.38
   s6   n=   76 psi=-0.825 pL=0.331 pS=0.530 p*=0.571 best=skip  ev=  +0.0bps stay=0.41
   s7   n=   29 psi=-0.900 pL=0.322 pS=0.539 p*=0.571 best=skip  ev=  +0.0bps stay=0.16
   s8   n=   57 psi=-1.025 pL=0.309 pS=0.554 p*=0.571 best=skip  ev=  +0.0bps stay=0.31
   s9   n=  624 psi=+1.200 pL=0.575 pS=0.290 p*=0.571 best=long  ev=  +1.3bps stay=0.31
   s10  n= 1064 psi=-0.050 pL=0.422 pS=0.435 p*=0.571 best=skip  ev=  +0.0bps stay=0.56
   s11  n=  641 psi=+0.825 pL=0.530 pS=0.331 p*=0.571 best=skip  ev=  +0.0bps stay=0.32
   s12  n=  395 psi=+1.600 pL=0.622 pS=0.249 p*=0.571 best=long  ev= +16.1bps stay=0.37
   s13  n=  226 psi=+1.050 pL=0.557 pS=0.306 p*=0.571 best=skip  ev=  +0.0bps stay=0.23
   s14  n=  419 psi=+0.775 pL=0.524 pS=0.337 p*=0.571 best=skip  ev=  +0.0bps stay=0.38
   s15  n=   76 psi=-0.475 pL=0.371 pS=0.487 p*=0.571 best=skip  ev=  +0.0bps stay=0.42
   s16  n=   29 psi=-0.025 pL=0.426 pS=0.432 p*=0.571 best=skip  ev=  +0.0bps stay=0.13
   s17  n=   69 psi=-0.750 pL=0.339 pS=0.521 p*=0.571 best=skip  ev=  +0.0bps stay=0.39
rc=0
```
