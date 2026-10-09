# Four criminology lenses on crypto market manipulation â effect on liquiditybot's defenses

## Why the operator should care which theory is true

A paper-trading bot does not need a theory of crime to survive a spoofed
book â it needs a detector. But *which* detector to build next, and
whether today's detectors will still work in a year, depends on why
manipulators do what they do. If differential association theory (DAT)
is right, crypto pump-and-dump crews are social networks that teach
technique and recruit continuously â the threat is a growing population,
and defenses should assume novices arrive with borrowed playbooks. If
rational choice theory (RCT) is right, spoofing and layering persist
because detection probability is low and expected value is positive â
the fix is raising the manipulator's cost against *this* counterparty,
which is an engineering problem the bot can actually solve. If strain
theory (ST) is right, retail-side manipulation is cyclical, driven by
macro loss and desperation, and will wax and wane with the market rather
than respond to any detector at all. If labelling theory (LT) is right,
crypto's cultural reframing of recklessness as "degen" identity has
disabled the informal shame-based social control that would otherwise
check retail complicity â meaning community self-policing cannot be
relied on as a background defense. Each theory names a different
mechanism and predicts a different persistence curve; a bot built to the
wrong one over-invests in detectors that never bite and under-invests
in the one lever that would.

## Differential Association Theory (DAT)

**Mechanism.** Sutherland's DAT (*Principles of Criminology*, 4th ed.,
1947) holds that criminal behavior is *learned* through communication in
intimate groups: technique, motive, and rationalization ("everyone
pumps, it's not really fraud") are transmitted with the frequency,
duration, priority, and intensity of the associations, not innate to the
individual.

**Crypto evidence.** Pump-and-dump groups are DAT's textbook case
transplanted onto Telegram: Xu & Livshits (USENIX Security 2019,
"The Anatomy of a Cryptocurrency Pump-and-Dump Scheme") document
hundreds of self-organized channels running identical coordinated
scripts; Kamps & Kleinberg (*Crime Science* 7:18, 2018, "To the moon:
defining and detecting cryptocurrency pump-and-dumps") frame this
explicitly in criminological terms, including repeat-victimization
patterns in which successful groups re-target the same illiquid coins.
Coordination scale (channel membership, publicly, has run into the
millions) is the DAT signature: technique diffuses through the network
faster than any single regulator can track membership.

**Bot angle.** Nothing in liquiditybot ingests Telegram/Discord feeds â
by CLAUDE.md invariant 3, non-Kraken venues are read-only *market* data
(OKX, Binance.US, moomoo), not social data, so DAT's actual mechanism
(technique transmission through a chat network) sits entirely outside
the bot's observation surface, and that is a deliberate scope boundary,
not a gap. What the bot *does* have is defense against being pulled in
as the pump's marginal counterparty: `sentiment/fear_filter.py`'s
`NarrativeFilter.evaluate` fades crowd euphoria only when structure
stays calm (`euphoria_fade`, risk multiplier 0.9,
`sentiment/fear_filter.py:110-113`) â exactly the moment a P&D group's
broadcast narrative is loudest and the order book hasn't moved yet â and
`manip_suspect_score`'s divergence term (`main.py:292-313`) would flag a
single-venue price spike that the composite cross-venue book doesn't
corroborate (`main.py:383-396`, `_composite_imbalance`). The v9
liquidity-tier isolation (`regime/liquidity_regime.py:162-`) judges thin
altcoins â DAT's preferred target, being cheap to move â on their own
depth scale rather than exempting them from the executability floor.
None of this *detects* a pump-and-dump group; all of it limits the
bot's exposure if one is running. DAT predicts this manipulation class
will persist and adapt (new platforms, new coordination tooling,
generational turnover of recruits) regardless of any single venue's
countermeasures, because the mechanism is social, not microstructural â
consistent with the bot's posture of exposure-limiting rather than
group-detecting.

## Rational Choice Theory (RCT)

**Mechanism.** Becker's economic theory of crime ("Crime and Punishment:
An Economic Approach," *Journal of Political Economy* 76(2), 1968)
models an offense as chosen when expected utility exceeds it: gain
minus (probability of detection Ã penalty), net of the cost of the
tactic itself.

**Crypto evidence.** Spoofing/layering economics are explicitly costed
in the market-microstructure literature the bot already cites: Cartea,
Jaimungal & Wang (spoofing through top-of-book imbalance) and
Cont-Kukanov-Stoikov-style analyses note that resting size *away* from
the touch is nearly free to place and cancel (it is never at execution
risk), while size *at* the touch carries real fill risk â the cost
asymmetry RCT predicts a rational manipulator exploits. Enforcement
data confirms the other half of the equation: CFTC's own reporting
shows crypto-sector spoofing/fraud actions dropping in recent fiscal
years even as digital-asset case *counts* rose in earlier years (Paul
Hastings, "CFTC's High-Profile Crypto Cases Lead to Massive Recoveries
but Far Fewer Enforcement Actions") â low, falling detection probability
against a 24/7, fragmented, largely unregulated spot market is exactly
the condition under which RCT predicts the tactic should persist and
even intensify, in contrast to CME-regulated futures where the same
tactic has drawn nine-figure penalties (JPMorgan $920.2M, 2020;
Deutsche Bank $30M) â the same statute, wildly different realized
detection probability.

**Bot angle.** This is where liquiditybot's defenses are both densest
and most precisely targeted, because RCT's mechanism â an adversary
optimizing a computable cost/benefit against a specific counterparty â
is exactly what the v8 anti-predation stack is built to erode. TH-017
spoof-flicker (`strategies/thales.py:307-351`, docstring
`strategies/thales.py:129-136`) detects the RCT-predicted footprint
directly: a level much larger than its neighbors appears, then vanishes
without the mid crossing it â cheap to paint, pulled before cost is
paid. The v8 distance-decayed order-book imbalance
(`regime/liquidity_regime.py:101-124`, `_decayed_notional`/`_imbalance`,
citing Stoikov 2018/Cont-Kukanov-Stoikov) doesn't just detect this, it
*devalues* it: notional far from the touch decays toward zero weight in
the imbalance the model reads, so painting a wall away from the touch â
the RCT-optimal, low-cost tactic â stops paying off against this bot
specifically. That is cost-imposition, not just detection: the
manipulator is pushed toward painting *at* the touch, where the tactic
becomes expensive (real fill risk), which is the only lever a single
market participant actually has over another actor's RCT calculus.
`manip_suspect_score` (`main.py:292-313`) and `manip_entry_scale`
(`main.py:316-338`), wired through `risk.manip_gate`
(`main.py:940-944`, live at `main.py:3068-3099` and
`main.py:3883-3918`, reason code `SZ_MANIP_SUSPECT`), operationalize the
same logic on the bot's own order-placement decision: downsize past
`downsize_at=0.6`, veto past `veto_at=0.9` â refuse to post fresh
liquidity into a book a bigger, cheaper-cost actor is painting, which
directly zeroes the manipulator's expected gain *from this specific
counterparty*. Osler's round-number stop-cascade economics
(`main.py:267-289`, `nudge_stop_off_round_number`) is the same
RCT-symmetric logic applied to the bot's own exits: don't rest where the
herd's stop-cascade would trigger against you. On persistence: RCT
predicts spoofing/wash-adjacent tactics continue at the market-wide
level indefinitely â the bot cannot change other actors' detection
probability, only its own exposure â but predicts that *this specific
book*, targeted repeatedly at this bot, becomes a losing proposition for
the manipulator, which is the correct and only scope for a single
participant's defenses. THALES's V2 reliability ledger
(`strategies/thales.py:164-211`, Wilson-LCB evidence weighting) is the
right response to RCT's implied arms race: a detector whose signal
stops earning its keep against an adapting adversary is muted
automatically rather than hand-tuned, so tactic-shift is handled without
a fitted-literal edit.

## Strain Theory (ST)

**Mechanism.** Merton's strain theory ("Social Structure and Anomie,"
*American Sociological Review* 3(5), 1938) holds that a gap between
culturally prescribed goals (wealth) and legitimate means to reach them
produces "innovation" â illegitimate means substituted for blocked
legitimate ones. Agnew's General Strain Theory ("Foundation for a
General Strain Theory of Crime and Delinquency," *Criminology* 30(1),
1992) extends this to acute strain from loss of valued stimuli
(crypto-crash drawdowns) and presentation of noxious stimuli
(post-2021/2022 real-wage stagnation, housing unaffordability), both of
which predict a turn toward high-variance, rule-bending strategies to
recoup losses fast.

**Crypto evidence.** The retail cohort recruited into pump-and-dump
groups and meme-coin speculation is disproportionately drawn from
exactly this strained population â the Terra/Luna and FTX collapses
(2022) produced mass realized losses, and the subsequent meme-coin
speculation wave is consistent with Agnew's innovation-under-strain
prediction, though I found no criminology-journal paper that names
crypto retail traders explicitly (a gap in the literature, not a claim
I can source further than the general ST corpus above). This is a
background-conditions theory: it explains the *supply* of participants
DAT's networks recruit, not a microstructure mechanism observable
tick-by-tick.

**Bot angle.** Strain is a psychological/economic state of a trader, not
a feature of an order book â nothing in `strategies/thales.py` or
`ml/features.py` observes it, and nothing should try to; inferring an
individual's financial desperation from public market data would be
both infeasible and a fitted-literal invitation to overfit on noise.
The one honest proxy already in the codebase is aggregate, not
individual: `sentiment/fear_filter.py`'s structural stress index
(`structural_stress`, `sentiment/fear_filter.py:64-83`) reads realized
vol percentile, depth collapse, funding extremes, turbulence, and
perp/spot basis â the *market-level echo* of mass strain-driven
capitulation â and the `confirmed_stress` branch
(`sentiment/fear_filter.py:100-105`) de-risks the bot into it (0.6Ã
size, â0.10 confidence tilt) rather than trading against a market that
is capitulating for structural, not narrative, reasons. Separately, the
bot is structurally strain-immune by construction regardless of what
theory is true of its counterparties: `system.dry_run` defaults true
with a typed `ARM LIVE` ceremony (CLAUDE.md invariant 1), and the
CVaR/gap/budget/heat protocol stack plus inventory caps
(`docs/compliance_market_conduct.md:105-111`) mean the bot itself never
needs a "recoup losses fast" strategy â the exact opposite of what ST
predicts a strained human trader reaches for. Nothing here is a
detector aimed at strain; it is a design that never puts the bot into
the state strain theory explains. ST predicts the retail-coordination
manipulation layer will be cyclical â worse after crashes, quieter in
sustained bull markets â which is a testable divergence from RCT's
prediction of roughly constant pressure gated only by enforcement.

## Labelling Theory (LT)

**Mechanism.** Becker's labelling theory (*Outsiders: Studies in the
Sociology of Deviance*, 1963) holds that deviance is not inherent to an
act but constituted by social reaction to it; stigmatizing labels
produce secondary deviance (the labelled person adopts the deviant
identity). Sykes & Matza's techniques of neutralization ("Techniques of
Neutralization: A Theory of Delinquency," *American Sociological
Review* 22(6), 1957) describe the adjacent mechanism by which offenders
rationalize away the moral weight of a label before or after the act.

**Crypto evidence.** Crypto culture runs LT in reverse. "Degen" â
originally a stigmatizing label for compulsive gambling behavior â has
been reclaimed as an in-group status marker on crypto Twitter and
Discord: self-identifying as a degen signals savvy risk tolerance
rather than shame (documented across trade-press and clinical-adjacent
coverage, e.g. *The Conversation*'s "If crypto platforms feel like
gambling it's because it is," and European Gaming Industry News' "The
Psychology of the 'Degen'"). This status inversion matters specifically
for manipulation because pump-and-dump participation, self-shilling, and
wash-selling one's own bags get absorbed into the same reclaimed
identity â the community reframes complicity as savvy rather than
wrongdoing, and reframes enforcement or exposure ("rugged," "fudded") as
the outsider's fault rather than the group's. LT predicts this disables
the informal shame-based social control that would normally check
deviance in a tight community, because the stigma the label would
otherwise carry has been pre-emptively stripped.

**Bot angle.** Labelling operates on human identity and community norms
â it is not observable in an order book, a candle series, or a
sentiment score, and no detector in `strategies/thales.py` or
`sentiment/fear_filter.py` reads trader identity or reputation. Honest
assessment: nothing here is actionable on the manipulator-facing side,
and building anything would be mandate creep with no validation path.
The one place LT actually binds is the bot's *own* legal exposure, which
`docs/compliance_market_conduct.md` addresses as a mirror-image
application of the same theory: under an inferred-intent standard
(Rule 575's "more likely than not intended"), the bot's defense against
ever being *labelled* a manipulator is a complete, reconstructable
record â "the answer is a file, not a recollection"
(`docs/compliance_market_conduct.md:118-119`; the hash-chained audit
trail and reason codes are the documented "intent record,"
`docs/compliance_market_conduct.md:47-50`). LT predicts the
retail-coordination manipulation layer fades only if "degen" loses
cultural cachet â a generational/cultural shift, not a response to any
enforcement action or detector â which is an orthogonal persistence
driver from both RCT (enforcement-gated) and ST (loss-cycle-gated).

## Comparative verdict

RCT best explains the layer liquiditybot actually transacts against
tick-by-tick â algorithmic/professional spoofing and layering â because
detection probability in fragmented, 24/7 crypto spot markets is
genuinely low relative to CME-regulated futures for the same statute,
and because the tactic's cost/benefit is exactly what the v8
distance-decay imbalance, TH-017 spoof-flicker, and the manip gate are
engineered to erode. This is also the theory with the tightest bot-side
match: every mechanism it names has a corresponding file:line. DAT best
explains the retail pump-and-dump coordination layer's *persistence and
adaptation* â social transmission through Telegram/Discord recruits
continuously regardless of any single venue's countermeasures â but the
bot only touches this layer's edge (fear filter, liquidity tiers,
manip-gate exposure limits), by design, since chat-network surveillance
is outside the read-only-venue mandate. ST is a background-conditions
theory: it explains DAT's recruitment pool and predicts cyclicality
(worse post-crash) rather than a mechanism the bot can observe or gate
on directly. LT explains why the retail layer resists informal
self-policing (status-inverted labelling strips the shame deterrent)
but has no purchase on the professional/algorithmic layer, where actors
are pseudonymous and never needed a community label to begin with â
and its one genuine bind on this codebase is reflexive (the audit trail
protects the *bot* from mislabelling), not manipulator-facing.

**One actionable implication per theory:**
- **DAT** â nothing actionable beyond current scope: a social-feed
  pump-and-dump scanner would be genuine mandate creep past the
  read-only-venue invariant and would need its own overfit-discipline
  validation path before it could ship; the existing
  euphoria-fade/liquidity-tier combination is the correctly-sized
  exposure defense for a bot that is a counterparty, not a surveillance
  system.
- **RCT** â already covered structurally; the actionable item is
  governance, not a new mechanism: any future retuning of
  `imbalance_decay_bps`, `spoof_touch_buffer_bps`, or
  `imbalance_whiplash_threshold` (`regime/liquidity_regime.py:132-160`)
  in response to adversary adaptation must clear `scripts/
  overfit_check.py`'s PBO/DSR gates like any other tunable â RCT
  predicts an arms race, and the THALES V2 reliability ledger is
  already the correctly-shaped automatic response to it.
- **ST** â nothing actionable: strain is not observable in market data,
  and the existing `NarrativeFilter` structural-stress index is the
  correctly-scoped aggregate proxy; building an individual-level
  strain detector would be infeasible and against the no-fitted-
  literals discipline.
- **LT** â nothing actionable on the manipulator side (out of the
  mechanism's scope entirely); the one real implication is defensive
  and already shipped: keep the hash-chained audit trail and reason
  codes as the top-priority invariant, since it is the bot's actual
  defense against being mislabelled under an inferred-intent standard â
  protect it, don't extend it.

## Sources

- Sutherland, E.H. (1947). *Principles of Criminology*, 4th ed.
  (differential association).
- Xu, J. & Livshits, B. (2019). "The Anatomy of a Cryptocurrency
  Pump-and-Dump Scheme." USENIX Security Symposium.
  https://www.usenix.org/conference/usenixsecurity19/presentation/xu-jiahua
- Kamps, J. & Kleinberg, B. (2018). "To the moon: defining and
  detecting cryptocurrency pump-and-dumps." *Crime Science* 7:18.
  https://link.springer.com/article/10.1186/s40163-018-0093-5
- Becker, G.S. (1968). "Crime and Punishment: An Economic Approach."
  *Journal of Political Economy* 76(2), 169-217.
- CFTC enforcement releases: JPMorgan spoofing order (2020),
  https://www.cftc.gov/PressRoom/PressReleases/8260-20 ; Deutsche
  Bank/HSBC/UBS anti-spoofing actions,
  https://www.cftc.gov/PressRoom/PressReleases/7681-18
- Paul Hastings LLP, "CFTC's High-Profile Crypto Cases Lead to Massive
  Recoveries but Far Fewer Enforcement Actions."
  https://www.paulhastings.com/insights/client-alerts/cftcs-high-profile-crypto-cases-lead-to-massive-recoveries-but-far-fewer-enforcement-actions
- Merton, R.K. (1938). "Social Structure and Anomie." *American
  Sociological Review* 3(5), 672-682.
- Agnew, R. (1992). "Foundation for a General Strain Theory of Crime
  and Delinquency." *Criminology* 30(1), 47-87.
- Becker, H.S. (1963). *Outsiders: Studies in the Sociology of
  Deviance*. Free Press.
- Sykes, G.M. & Matza, D. (1957). "Techniques of Neutralization: A
  Theory of Delinquency." *American Sociological Review* 22(6),
  664-670.
- The Conversation, "If crypto platforms feel like gambling it's
  because it is: Users drawn to high-risk behaviour" (2026).
  https://theconversation.com/crypto-platforms-feel-like-gambling-because-they-are-users-are-drawn-to-high-risk-behaviour-256057
- European Gaming Industry News, "The Psychology of the 'Degen':
  Differentiating Compulsive Gambling from Aggressive Altcoin
  Speculation" (2025).
  https://europeangaming.eu/portal/latest-news/2025/11/21/196847/the-psychology-of-the-degen-differentiating-compulsive-gambling-from-aggressive-altcoin-speculation/
- Cong, L.W., Li, X., Tang, K. & Yang, Y. (2023). "Crypto Wash
  Trading." *Management Science* (cited defensively in
  `ml/features.py:74-83` and `docs/compliance_market_conduct.md:73-75`).
- Cartea, A., Jaimungal, S. & Wang, J. â spoofing through top-of-book
  imbalance (cited in `strategies/thales.py:129-136`).
- Stoikov, S. (2018); Cont, R., Kukanov, A. & Stoikov, S. â spoof
  economics of near-touch vs. far-touch resting size (cited in
  `regime/liquidity_regime.py:101-114`, `ml/features.py:82-83`).
- Easley, D., LÃ³pez de Prado, M. & O'Hara, M. (2012). "Flow Toxicity
  and Liquidity in a High-Frequency World." *Review of Financial
  Studies* (cited in `ml/features.py:264-266`, VPIN).
- Osler, C. (2005). "Stop-Loss Orders and Price Cascades in Currency
  Markets." *Journal of International Money and Finance* (cited in
  `main.py:269-274`).
