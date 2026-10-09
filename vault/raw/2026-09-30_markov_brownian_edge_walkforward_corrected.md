# Raw — markov_edge_report CORRECTED run (verbatim stdout, 2026-09-30)

Same snapshot as raw/2026-09-29_markov_brownian_edge_walkforward.md (copied 2026-09-29T20:10:58Z, sha256 prefix c732f653e3d853b, 34771 lines; as-of = its mtime). Correction: test days younger than day_end + 36 h label horizon are no longer scored (censored toward fast-resolving rows). Adds the forward-registered operator spec (0 days, first mature 2026-10-02T12:00Z).

```
markov_edge - walk-forward, 6929 rows over 22 days; base P(up first) resolved = 0.517; corpus as-of 2026-09-29T20:10:58Z (days younger than day_end + label horizon are not scored)
counting CS-1: n=34770 = not_candidate_tb=5203 + pre_era9=22638 + unparseable=0 + immature_day=497 + burn_in_train_only=2077 + scored=4355 [OK]

spec            variant  days  gain(nats/row)  [95% CI]              null_p  | within-day AUC [95% CI]      null_p  | uplift(bps)  [95% CI]        taken/rows
pooled          static     12  -0.04264  [-0.09853,+0.01144]  1.000  | 0.500 [0.500,0.500]  1.000  |    +30.5  [-38.0,+105.9]  15/4355
pooled          chain      12  -0.04264  [-0.10071,+0.01183]  1.000  | 0.500 [0.500,0.500]  1.000  |    +30.5  [-38.0,+103.8]  15/4355
hmm             static     12  -0.04468  [-0.09204,+0.00195]  1.000  | 0.523 [0.437,0.613]  0.050  |     -9.7  [-80.9,+59.0]  125/4355
hmm             chain      12  -0.03798  [-0.08844,+0.00834]  0.005  | 0.477 [0.395,0.566]  0.587  |    +22.0  [-40.3,+87.4]  13/4355
basis           static     12  -0.03341  [-0.08479,+0.01650]  0.005  | 0.543 [0.515,0.572]  0.020  |    -13.4  [-62.8,+35.7]  265/4355
basis           chain      12  -0.04066  [-0.09450,+0.00908]  0.985  | 0.536 [0.505,0.566]  0.060  |     +6.0  [-60.4,+78.4]  4/4355
disloc          static     12  -0.04301  [-0.08444,-0.00625]  0.935  | 0.485 [0.397,0.565]  0.254  |    -44.1  [-99.5,+8.7]  329/4355
disloc          chain      12  -0.05547  [-0.11875,+0.00080]  1.000  | 0.439 [0.351,0.528]  0.005  |    -41.0  [-100.5,+0.0]  87/4355
basis_x_disloc  static     12  -0.03276  [-0.06915,+0.00093]  0.408  | 0.527 [0.463,0.584]  0.065  |    -54.5  [-100.7,-11.5]  408/4355
basis_x_disloc  chain      12  -0.04428  [-0.09502,+0.00335]  1.000  | 0.437 [0.354,0.532]  0.005  |    -17.1  [-51.4,+0.0]  8/4355
hmm_x_basis     static     12  -0.02970  [-0.06846,+0.00452]  0.766  | 0.562 [0.512,0.615]  0.005  |    -11.9  [-90.2,+60.5]  275/4355
hmm_x_basis     chain      12  -0.02871  [-0.06983,+0.01201]  0.005  | 0.491 [0.398,0.591]  0.781  |     +0.0  [+0.0,+0.0]  0/4355
operator*       static      0  +nan  [+nan,+nan]  nan  | nan [nan,nan]  nan  |     +nan  [+nan,+nan]  0/0
operator*       chain       0  +nan  [+nan,+nan]  nan  | nan [nan,nan]  nan  |     +nan  [+nan,+nan]  0/0
* FORWARD-REGISTERED: scored only on test days from 2026-09-30T00:00Z, first mature 2026-10-02T12:00Z; 0 days = nothing to read yet

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
-- operator
   s0   n= 1471 psi=-1.200 pL=0.290 pS=0.575 p*=0.571 best=short ev=  +1.3bps stay=0.97
   s1   n= 1915 psi=+0.575 pL=0.499 pS=0.360 p*=0.571 best=skip  ev=  +0.0bps stay=0.97
   s2   n= 1676 psi=-0.250 pL=0.398 pS=0.459 p*=0.571 best=skip  ev=  +0.0bps stay=0.98
   s3   n=  653 psi=+2.075 pL=0.674 pS=0.206 p*=0.571 best=long  ev= +32.5bps stay=0.93
   s4   n=  318 psi=+0.800 pL=0.527 pS=0.334 p*=0.571 best=skip  ev=  +0.0bps stay=0.93
   s5   n=  896 psi=+0.950 pL=0.545 pS=0.317 p*=0.571 best=skip  ev=  +0.0bps stay=0.95
rc=0
```
