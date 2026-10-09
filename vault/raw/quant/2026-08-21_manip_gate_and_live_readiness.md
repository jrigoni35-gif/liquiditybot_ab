# Manipulation-gate efficacy audit + era-4 live-readiness read — 2026-08-21

*Measurement record. Every number below is a run result captured at the stated
time by the stated command; nothing here is recalled. Re-derive before citing —
two of the three sources mutate.*

Repo HEAD at capture: `dae58cf6` (2026-08-21T23:11Z), branch
`claude/claude-rc-f3heik`, deployed head on the PC `dae58cf6`.

---

## 0. Snapshot provenance

| artifact | stamp |
|---|---|
| `outputs/signal_history.csv` snapshot (`sh.csv`) | md5 `a6b83a65e0a037bdc4ad740ae49f1a77`, 11,156,538 bytes, **14,170 rows**, ts range 2026-07-13T12:35:47Z .. **2026-08-21T22:42:22Z** |
| `control/pc_status.json` (`origin/paper-telemetry`) | READ **2026-08-21T23:53:07Z** |
| `scripts/cohort_eval.py` local run | 2026-08-21 ~23:55Z, on `outputs/fills.csv` at that instant |
| injection target | shipped `regime.liquidity_regime.LiquidityRegimeEngine` + live `config.json["liquidity_regime"]` at HEAD `dae58cf6` |

Both live CSVs grow while being read. Every corpus figure below is **as-of the
snapshot**, never "current".

---

## 1. Live state [K — pc_status, read 2026-08-21T23:53:07Z]

```
deploy.head                dae58cf6      auto_update.outcome  current
era4                       {"accrual_n": 33, "target": 50, "signed_continue_n": 100}
status.equity              805.04        runner_state         RUNNING
mode                       DRY_RUN       system.dry_run       true (config.json)
ml.history_rows            14198         labels live/candidate 346 / 13852
ml.drift_share             0.3333        retrain_flag         true
ml.load_stats              rows 3870, mean_uniqueness 0.1303, ess_kish 5667.5
```

**The deploy pipeline is NO LONGER blocked.** `docs/HANDOFF.md` records it as
stuck on a dirty tree + an unpushed local commit (observed 2026-08-20);
`auto_update.outcome` now reads `current` at `dae58cf6` on the `main` channel.
That HANDOFF entry is stale as of this read.

---

## 2. Era-4 gate — where the accrual actually stands

**Double-derived, two independent routes, AGREE:**

| route | value |
|---|---|
| `pc_status.era4.accrual_n` (the running binary's own count) | **33 / 50** |
| `scripts/cohort_eval.py` local re-run over `outputs/fills.csv` | **33 / 50** |

Cohort as-of numbers (**pre-registration forbids reading these as a trend; they
are recorded here only because the readiness question is about the gate's
RESOLVING POWER, not its value**):

```
gross  mean +1.1820%  (SE 0.4669%)  median +0.7977%  win 69.7%
net    mean +0.5117%                median +0.1285%  win 60.6%
EFFECTIVE n: 9.9 of 33 nominal (mean uniqueness 0.301) -> SE optimistic x1.82
resolvable-edge floor ~1.7033%   (the tool's own words, not a derived gloss)
COHORT HOMOGENEITY: MIXED(both)
```

Three structural facts the tool prints about its own population:

1. **Fill axis** — 5 of 33 trips carry a leg written by a binary that predates
   the `exec_era` stamp; the ledger's blank-means-decide-by-ts rule returns the
   WRONG era for exactly those rows.
2. **Model axis** — two champions opened trips in this cohort (`adaptive_gbt`,
   `logistic`); **18 of 33 trips straddle a mid-flight deploy**; 14 deploys are
   enumerated inside the accrual window (2026-08-11T15:03:20Z .. 2026-08-21T11:29:44Z).
3. **Selection axis** — `probe: {'1': 28, '0': 5}` = **85% probe admissions**.
   A probe sets `p_win = max(p_win, ml.exploration.p_win = 0.7)` against a
   derived bar near 0.567, so it clears **by construction** and the model's own
   p is never the admitting quantity. Label axis is mixed too:
   `exit_sim: 17, triple_barrier_h432: 16`.

**The arithmetic that matters for readiness:** the resolvable-edge floor
(~1.7033%) is **above** the observed gross mean (+1.1820%). At n=50 the gate
will fire on a quantity smaller than its own noise — the same shape as owed
item 82, recurring at a different n and a different sign.

---

## 3. Audit A — does the manipulation veto (SZ-045) refuse winners?

Population: the signal-history snapshot above. Counterfactual outcome = the
label the candidate WOULD have earned (rows are logged whether or not the trade
was taken), so a "refused" row still has an outcome.

### A.1 What the gate actually refused

```
SZ-045 stamped rows, corpus-wide:                       454
  by label era: exit_sim 54 | exit_sim_time_stop 19 | triple_barrier 239 | triple_barrier_h432 142
  by asset (h432): MINA 87 | FLOW 54 | ETH 1
veto band (manip_suspect >= 0.9), h432:                 n=239, MINA+FLOW = 229/239 = 95.8%
```

**Route-B double-derive** (pure-stdlib `csv`, era membership from BARRIER
vocabulary `tb_*` + ts window `1786568178..1787350275` inclusive, not the
`label_era` column):

```
era n=3857 wins=1951 wr=0.5058 | manip>=0.9 n=239 wr=0.4519 | SZ-045 n=141 wr=0.5745
```
Pandas route (era = `label_era == triple_barrier_h432`, `exit_price > 0`):
`n=3841`, SZ-045 `n=141`, wr `0.5745`. **The two routes agree** on every
load-bearing figure; the ±4-row spread is the `exit_price>0` filter.

### A.2 The headline that does NOT survive

Direction-adjusted (Mantel-Haenszel), episode-ESS-corrected, era-fenced,
MINA+FLOW:

| instrument | pooled delta (refused − passed) | SE | z | p |
|---|---|---|---|---|
| **disposition** `disp == SZ-045` | **+11.71 pp** | 0.0486 | +2.41 | **0.016** |
| **feature** `manip_suspect >= 0.9` | **+2.80 pp** | 0.0458 | +0.61 | 0.542 |

The two instruments are supposed to be the same event. They are not:

```
both = 277   disp-only = 104   feature-only = 218   Jaccard = 0.462
116 / 454 = 25.6% of SZ-045-stamped rows record a manip_suspect BELOW the veto
threshold (disp-only median 0.858, max 0.900)
```

2×2 decomposition (TB eras, MINA+FLOW, n=1226, ESS-corrected):

```
EFFECT OF THE SCORE, stamp held fixed:
  stamp=True : feat>=0.9 0.4746 vs feat<0.9 0.4272   delta +4.75pp  z=+0.46  p=0.643
  stamp=False: feat>=0.9 0.2976 vs feat<0.9 0.3100   delta -1.24pp  z=-0.11  p=0.915
EFFECT OF THE STAMP, score held fixed:
  feat>=0.9  : stamped 0.4746 vs unstamped 0.2976    delta +17.71pp z=+1.60  p=0.111
  feat<0.9   : stamped 0.4272 vs unstamped 0.3100    delta +11.72pp z=+1.08  p=0.281
```

**The manipulation score explains nothing. The stamp carries the whole effect —
and neither stamp contrast reaches significance on its own.**

### A.3 Placebo — is the elevation specific to the manip stamp?

Every terminal stamp with n>=30 vs all other rows (TB eras, MINA+FLOW):

```
SZ-021  n=  67  win 0.6716  delta +33.51pp  z=+1.53  p=0.126
SZ-045  n= 379  win 0.4617  delta +15.48pp  z=+1.39  p=0.164
capped  n= 354  win 0.3079  delta  -6.59pp  z=-0.44  p=0.662
SZ-022  n= 177  win 0.2429  delta -13.08pp  z=-1.06  p=0.289
SZ-023  n= 235  win 0.2383  delta -14.41pp  z=-1.15  p=0.252
```

A different veto stamp shows a **larger** elevation than the manip stamp. The
elevation is a property of being stamped, not of manipulation.

### A.4 Apples-to-apples, within asset, current label era

Among candidates that actually REACHED the manip gate (h432; 2,186 of 3,841 era
rows reached it — 1,655 died earlier or were undispositioned). Counterfactual
net % per trade uses a flat 0.06% cost:

```
                       refused                    passed                     delta
MINA   n=87 wr 0.563 net +0.7519% | n=114 wr 0.570 net +0.8816% | dWR -0.7pp  dNet -0.13pp
FLOW   n=53 wr 0.604 net +0.9974% | n= 23 wr 0.261 net -1.1768% | dWR +34.3pp dNet +2.17pp
pooled n=141 wr 0.5745 net +0.8276% [95% CI -0.0879, +1.7432]
       vs n=2045 wr 0.5428 net +0.5514% [95% CI +0.3716, +0.7312]
```

MINA — the larger cell — shows **nothing**. FLOW's +34.3pp rides on a control
arm of n=23 whose per-asset effective n is **3.0**.

### A.5 Effective n, stated because the nominal n is a lie here

```
mean per-asset uniqueness 0.0726  (~13.8 same-asset labels concurrent)
median label span 33,669 s (9.4 h)
era n=3841 -> n_eff 279.0 | SZ-045 n=141 -> n_eff 14.7 (episode-ESS 37.5)
veto band n=239 -> n_eff 18.6 | taper band n=395 -> n_eff 28.2
```

### A.6 Dose-response does not survive the label-era change

```
triple_barrier      (<=0.3) 0.2121 | (0.3-0.6) 0.2000 | (0.6-0.9) 0.2663 | (>0.9) 0.3466   MONOTONE
triple_barrier_h432 (<=0.3) 0.5000 | (0.3-0.6) 0.4194 | (0.6-0.9) 0.4684 | (>0.9) 0.4565   FLAT
```

### A.7 Verdict A

**NOT ESTABLISHED — in both directions.** The claim "the manipulation veto is
refusing winners and costing money" is instrument-dependent (survives on the
stamp, dies on the score), non-specific (a placebo stamp scores higher), absent
within the larger asset cell, gone in the current label era, and carried by an
effective n in the teens. **Do not retune the gate on this.** Retuning it would
be cohort-resetting anyway (entry decisioning, era-4 moratorium).

---

## 4. Audit B — CAN the detector tell manipulation from honest repricing?

Static reading of the detector says yes ("large level vanished untouched").
Asking the running object says no. Injection into the **shipped**
`LiquidityRegimeEngine` with the live config: synthetic 15-level book on a 2 bps
grid, $20,000 per level, 80 snapshots at the 30 s cadence, one large level.

### B.1 The controls behave

```
A flat book, no large levels                 spoof 0.000  events   0  liquid
B flat book, large wall rests forever        spoof 0.000  events   0  liquid
D melt-up, large asks LIFTED (consumed)      spoof 0.000  events   0  liquid   <- correct
H melt-up, no large levels at all            spoof 0.000  events   0  liquid
```

### B.2 The false positive

```
E melt-up +15 bps/30s, maker REPRICES its offer with the mid
                                             spoof 0.949  events  79  SPOOFY
F same repricing on a FLAT mid               spoof 0.000  events   0  liquid
```
Nothing is pulled in bad faith in E. A market maker holds an offer 25 bps above
the mid and follows the mid up. `veto_at` is 0.90. **0.949 ≥ 0.90.**

### B.3 It is directional

```
E  melt-up, maker reprices OFFER   spoof 0.949 SPOOFY  |  G  melt-up, reprices BID  0.003
E2 crash,   maker reprices OFFER   spoof 0.003         |  G2 crash,   reprices BID  0.949 SPOOFY
```
The side that has to chase the trend is the side that reads as manipulation.
**The detector fires on the trending side of the book, in either direction.**

### B.4 At matched cadence the two processes are indistinguishable

```
repost EVERY snapshot (30s):  MALICIOUS layering 0.949 SPOOFY | HONEST repricing 0.949 SPOOFY
repost every OTHER (60s):     MALICIOUS layering 0.764 liquid | HONEST repricing 0.000 liquid
```
**Identical score, identical event count, identical label.** What separates the
two in the wild is repost cadence, not intent — and cadence is the attacker's
free parameter.

### B.5 The trip conditions, enumerated

```
trend (honest repriced offer):  0.0 bps/30s -> 0.000 | 1.0..15.0 -> 0.949 | 30.0 -> 0.000
size:  2x,4x,6x,7x -> 0.000 | 8x,9x,12x,20x -> 0.949        (spoof_size_mult = 8, exactly)
distance from mid: +2,+4,+5,+6,+8,+10 bps -> 0.000 | +25 bps -> 0.949 | +100 bps -> 0.000
```
Non-monotone at both extremes because the level leaves the tracked window
(`track_levels = 15`) — the "safe" zones at 30 bps/30 s and +100 bps are
**blind spots, not immunity**.

### B.6 Evasion floor

```
attacker repost every  30s -> 0.949 SPOOFY | 60s -> 0.764 | 90s -> 0.629 | >=120s -> 0.000
```
against `veto_at` 0.90 and `spoof_healthy_book_threshold` 0.85. **A layering
campaign that reposts no faster than every 2 minutes scores zero.**

### B.7 The reach — why this is an entry-path fact, not a telemetry fact

```
spoof_score -> manip_suspect_score = MAX(spoof, whiplash, divergence)   main.py:370-392
            -> risk.manip_gate  downsize_at 0.6 / veto_at 0.9 / min_scale 0.25
                                                                        main.py:1287-1298
            -> SZ-045 entry refusal (new risk only; exits never touched) main.py:4678-4700
0.949 also clears the liquidity-regime spoofy label bar (0.85 on a healthy book)
   -> label "spoofy", size_mult 0.0, reduce_only                regime/liquidity_regime.py:348-352
```

### B.8 Verdict B and what it could not see

**The spoof detector is keyed on a SHAPE — a large near-touch level vanishing
untouched inside 90 s — that honest repricing in a trending tape produces
identically.** It is directional, evadable at ≥120 s repost cadence, and blind
outside its 15-level window.

Could not see: a real Kraken book (many levels, irregular polls, real
cancellations), the production RATE of this false positive, and any interaction
with whiplash or cross-venue divergence — the other two `MAX()` inputs. This
establishes a **capability** (the detector cannot separate the two processes),
not a **frequency**. The corpus half is consistent with it: 95.8% of the era's
veto band is MINA+FLOW, the two widest-spread assets on the book.

---

## 5. Audit C — the adversarial pass on `eeff0f7a` (shipped as `dae58cf6`)

Seven agents (3 hostile personas in independent contexts + 3 verifiers required
to RUN rather than reason + synthesis). Verdict CONCERNS; **zero criticals
survived** — all three personas opened with one, the verifiers killed all three
on executed evidence. Four findings survived, full text in the commit message of
`dae58cf6`:

- **W1** `data/_http.py` — `loads_bounded` never raises, so a rejected hostile
  body fell through the SUCCESS tail: latency sample booked, `retries_recovered`
  incremented, "retry recovered" logged, for a payload that was discarded. The
  only trace named neither venue nor URL, across three feeds sharing one client.
  *The commit that hardened the poison boundary deleted that boundary's only
  venue-identifying alarm.*
- **W2** `core/sanitize.py` — a leading UTF-8 BOM parsed before `eeff0f7a`
  (simplejson) and returned None after (stdlib). Permanent and per-poll: a
  CDN/proxy rewrite would drop a venue from the composite feed forever.
- **W3** `execution/risk_firewall.py` — the code extractor scraped prose on
  faith: "stale book at 12:30 UTC" minted a fake `stale book at 12` code into a
  **hash-chained** record that `verify_chain` still returns `ok=True` on and that
  can never be corrected in place. Now membership-filtered against
  `core.audit._REGISTERED_CODES`. Injection-verified closed.
- **W4** `tests/test_rest_api_matrix.py` — the "constant-time comparison" pin was
  two `inspect.getsource()` substring greps, **satisfied by the string appearing
  in a COMMENT**. Mutation-verified: an implementation whose body is
  `return str(a) == str(b)` passes the entire pin with the suite green. Replaced
  with a sentinel-patch pin that requires the call to route through
  `hmac.compare_digest`.

**Process defect, recorded:** `eeff0f7a` also shipped a new `_token_ok`
authentication primitive in `api/rest_server.py` and `api/grpc_server.py`; its
commit message enumerated four files and mentioned neither. Cause: the diff was
read filtered to the four expected files.

Matrix at `dae58cf6`: 3881 pass / 0 fail, smoke 219/0, assurance 49/0, ruff
clean, compileall OK. All SAFE class.

---

## 6. LIVE-READINESS VERDICT — NOT READY. Remain in DRY_RUN.

The only road to live remains config `dry_run:false` → restart → typed
`ARM LIVE`. **Nothing in this document authorizes any of it**; it records what
would have to be true first. Five blockers, each sufficient alone:

1. **The gate has not read out.** 33/50, double-derived 2026-08-21T23:53Z. The
   readout does not decide either — it names which decision has become
   decidable.
2. **The gate cannot resolve what it will be asked.** Effective n 9.9 of 33;
   resolvable floor ~1.7033% against an observed gross mean of +1.1820%. It will
   fire below its own noise.
3. **The cohort is 85% exploration constant** (28/33 probes, `p_win` forced to
   0.7 against a ~0.567 bar → clears by construction), and mixed on the fill,
   model and label axes as well (`MIXED(both)`, 18/33 straddling a deploy).
   Whatever it reads out is not a statement about the selector.
4. **Two CRITICAL sweep findings are inert ONLY because `dry_run` is true** —
   `risk/leverage.py:75` margin-health veto FAILS OPEN (0.0 means both "API
   failed" and "no margin in use"; a transient TradeBalance failure disables the
   150%/200% block for a full hour), and `execution/inventory.py:134-155` →
   `main.py:2921` derisk force-closing a HEDGE with zero hedge coordination
   (guard-invisible reproduction of the cf454d5 ADA churn, −$318). Flipping
   `dry_run` arms both the same day. Both are BOUNDARY class, docketed for
   readout adjudication, deliberately unfixed.
5. **The entry path's manipulation gate cannot tell honest repricing from
   layering** (§4), is directionally biased against trending tape, and is
   evadable at ≥120 s. Its efficacy on the corpus is unresolved in both
   directions (§3).

Standing, unchanged, and additive: the fee constants are falsified (25/40 bps
shipped vs Tier-1 40/80 — owed 88, batched at the readout boundary), so live
fills would be booked against a cost stack the ledger under-prices.

**Nothing here is a reason to move a threshold.** Items 3 and 4 in particular are
measurement standards and adjudication debts, not tunables.
