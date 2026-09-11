# Tier 1 Deep-Reading Handoff — CUMCM 2026 B题

**What this file is.** The entry point for the Tier 1 full-text deep reading of the
CUMCM 2026 B题 literature. It is a **knowledge handoff**, not a one-shot prompt: it
is meant to be re-read at the start of any future session and still make sense.

**What this file is not.** It contains no full-text content, no summaries of papers
nobody has read yet, and no execution instructions.

---

## A. Context

- **Problem**: CUMCM 2026 B题 — 无线电干扰源的快速自动定位与清除.
  The authority is `problem/B题/B题.md`. Read it before the papers.
- **Round 1 is frozen.** Do not re-run keyword searches, do not re-pick the corpus,
  do not re-rank Tier 1. The corpus, its provenance and the full gap list live in
  `literature_search/cumcm-b-emitter-localization_2026-09-10/`:
  - `summary.md` — the report (corrections, candidate tables, ANCHOR set, gaps).
  - `raw/round1_correction_A.json` — A-cluster supplement provenance + findings.
  - `raw/arxiv.json`, `raw/openalex.json` — Round 1 raw metadata.
  - `raw/round1_correction_A.json` §`revisions` records every later errata fix.
- **Scope of Round 1**: an L1 *controlled probing run* (clusters A/B/C; buckets arXiv
  + OpenAlex; wave 1 only) plus a targeted A-cluster correction pass. It is broad but
  **not exhaustive**.
- **Known blind spot**: Chinese-language sources (**CNKI / 万方 / 维普**) were never
  searched. The 2017 paper carried in `verified_external_records` is a Chinese journal
  article that Round 1's OpenAlex and Crossref queries did not return. Treat every
  statement about Chinese-language literature as a search observation, never as
  non-existence.
- **Round 1 Tier 1 was frozen at six papers** (below). The core reading set was
  expanded post-freeze with Song, Kim & Yi (2012), preserving its teammate-supplied
  provenance. Wave 1 and the obtainable Wave 2 full texts have now been read; Yang
  et al. (2013) remains blocked for lack of lawful full-text access.

### Deep-reading status (2026-09-11)

- **Wave 1 complete:** Isler & Bajcsy (2006), Zhao, Chen & Lee (2013), Reynaud et
  al. (2018). See `deep_reading/wave1_synthesis.md`.
- **Original Wave 2:** Calafiore (2026) and Dehghan et al. (2014) complete;
  Yang et al. (2013) metadata verified but full-text reading **BLOCKED**. IEEE,
  OpenAlex, ResearchGate, SciSpace, DTIC/CiteSeerX and the available browser session
  yielded no lawful 2013 journal full text. Do not treat the 2011 Fusion precursor as
  the journal paper. See `deep_reading/yang_et_al_2013.md`.
- **Supplement complete:** Song, Kim & Yi (2012), a **post-Round-1
  teammate-supplied supplemental anchor**. This is a Tier 1 core reading set
  expansion after the freeze, not a Round 1 retrieval hit.
- **Integrated result:** `deep_reading/wave2_plus_song_synthesis.md`.

### The four questions being modelled

Short form only — the problem statement is the authority.

1. **问题 1** — given several detection points and the 示向度 of one emitter at each,
   give an algorithm for the **diameter of the polygonal localization region** found
   by 交会定位法, and answer whether the circle with that diameter covers the region.
2. **问题 2** — given one bearing measurement at one detection point, give a strategy
   for siting the **second detection point**, and give its candidate region.
3. **问题 3** — unknown count (10–16) of **omnidirectional** emitters; one robot dog
   from the origin, initial channel 1; minimize the time to locate and clear all of
   them; validate in the simulator.
4. **问题 4** — as 问题 3, but the area also holds **directional** emitters whose count
   and pointing directions are unknown.

### Problem facts that constrain every reading

| Fact | Value |
|---|---|
| Target area | circle of radius **1800 m**, origin at its centre, +x east / +y north |
| 示向度 error | **[-1°, +1°]**, hard bound — and **not stochastic at a fixed point**: the same place gives the same error; only across different places does it show statistical regularity |
| Effective receive radius | **1000–1500 m** per emitter |
| Channels | 20, each emitter on a distinct channel; switching between **any two distinct channels costs 1 s flat** — not `\|i−j\|` seconds |
| One bearing measurement | **5 s** (stop moving, switch channel, sweep the antenna) |
| Travel | straight line, **5 m/s**; detection is impossible while moving |
| Optical precise localization | works within **20 m**, costs **3 s** |
| Clearing | **2 s** |
| Special rule | at distance **≤ 5 m** AND inside the emitter's effective coverage angle, 示向度 is unobtainable; may **skip bearing detection** and go straight to 3 s optical + 2 s clear |
| Optical/clearing success | depends **only on distance** — **not** on the emitter's coverage angle |
| Runtime | program ≤ **20 min**, test window **25 min**, earlier deadline wins |
| Emitter count | 10–16, actual number **unknown** |
| Directional emitters | effective coverage = **±90°** about the pointing direction (180° total); omnidirectional = 360° |

---

## B. The six Tier 1 papers

Grades are as assigned in `summary.md` §6; all six are **ANCHOR**.

### 1. Isler & Bajcsy 2006 — *The Sensor Selection Problem for Bounded Uncertainty Sensing Models*

- **Authors**: Volkan Isler; Ruzena Bajcsy
- **Venue / year**: IEEE Transactions on Automation Science and Engineering, 2006
- **DOI**: `10.1109/TASE.2006.876615`
- **Maps to**: 问题 1 (primarily), with a direct extension to 问题 2
- **Why Tier 1**: this is the framework. A bounded-uncertainty measurement is
  represented as a **convex polygonal subset of the plane**; measurements are merged
  by **intersection**; the measurement uncertainty **is the area of the intersection**;
  and a sensor-selection algorithm with a 2-approximation guarantee is given. The
  paper's second part relaxes the goal from a point estimate to a *set* of possible
  locations. That is structurally what 问题 1 asks for, with a different measurable
  and a different sensor model.

### 2. Calafiore 2026 — *Set-Membership Localization via Range Measurements*

- **Authors**: Giuseppe C. Calafiore
- **Year**: 2026 (arXiv preprint)
- **arXiv**: `2603.04867`
- **Maps to**: 问题 1 (closest structural analogue indexed this round)
- **Why Tier 1**: with **unknown-but-bounded** range errors it characterizes the set
  of *all* points consistent with the measurements and their error model, shows it is
  contained in an intersection of closed balls **and a polytope** (the "localization
  set"), then computes a tight **outer-bounding** box or ellipsoid as a *guaranteed
  set-valued estimate*, and poses the inner-approximation problem too. Range-only, not
  bearing-only — the geometry transfers, the measurement model does not.

### 3. Reynaud et al. 2018 — *A set-membership approach to find and track multiple targets using a fleet of UAVs*

- **Authors**: Sebastien Reynaud; Michel Kieffer; Helene Piet-Lahanier; Leon Reboul
- **Venue / year**: IEEE Conference on Decision and Control (CDC), 2018
- **DOI**: `10.1109/CDC.2018.8619672`
- **Maps to**: 问题 3 (decision loop), with the architecture transferring to 问题 4
- **Why Tier 1**: this is the closest published architecture to what 问题 3 asks. All
  perturbations and measurement uncertainties are **bounded sets**; the method
  maintains a set guaranteed to contain the states of already-located targets **plus a
  set containing the states of targets not yet discovered**, and the control input is
  chosen to minimize next-step estimation uncertainty. An a-priori-unknown target
  count is handled by construction.

### 4. Zhao, Chen & Lee 2013 — *Optimal Sensor Placement for Target Localisation and Tracking in 2D and 3D*

- **Authors**: Shiyu Zhao; Ben M. Chen; Tong H. Lee
- **Venue / year**: International Journal of Control, 2013 (preprint `arXiv:1210.7397`)
- **DOI**: `10.1080/00207179.2013.792606`
- **Earlier conference version**: *Optimal placement of bearing-only sensors for target
  localization*, ACC 2012, `10.1109/ACC.2012.6314884`. Same research work — it holds
  **one** deep-reading slot, not two. Consult the conference version only if the
  journal version omits construction details.
- **Maps to**: 问题 2
- **Why Tier 1**: the mathematical core of 问题 2. A frame-theory treatment unifying
  bearing-only / range-only / RSS, giving **necessary and sufficient conditions** for
  optimal placement, the regular/irregular classification, explicit construction
  algorithms, and a gradient control law for the tracking case.

### 5. Yang et al. 2013 — *Optimal Placement of Heterogeneous Sensors for Targets with Gaussian Priors*

- **Authors**: Chun Yang; Lance M. Kaplan; Erik Blasch; Michael Bakich
- **Venue / year**: IEEE Transactions on Aerospace and Electronic Systems, vol. 49,
  no. 3, pp. 1637-1653, July 2013
- **DOI**: `10.1109/TAES.2013.6558009`
- **Maps to**: 问题 2 (*the* prior-aware form of it)
- **Why Tier 1**: it is the one indexed work whose shape is exactly "a measurement has
  already been taken — where does the next sensor go". It starts from an **arbitrary
  Gaussian prior**, includes bearing-only among its heterogeneous sensor types, and
  maximizes the **updated** FIM, with multi-step sequential placement. Note that the
  Gaussian-prior assumption is precisely the thing B题's hard ±1° bound does *not*
  provide (see the caveat in `summary.md` §3).
- **Reading status**: **BLOCKED**. The preceding description is the frozen Round 1
  metadata/abstract assessment, not a full-text conclusion. The 2013 criterion,
  equations, theorem conditions and experiments must be rechecked if lawful full
  text becomes available.

### 6. Dehghan et al. 2014 — *Optimal path planning for DRSSI based localization of an RF source by multiple UAVs*

- **Authors**: Seyyed M. Mehdi Dehghan; Seyyed A. Asghar Shahidian; Hadi Moradi
- **Venue / year**: 2nd RSI/ISM International Conference on Robotics and Mechatronics
  (ICRoM), 2014, pp. 558-563
- **DOI**: `10.1109/ICRoM.2014.6990961`
  (an earlier transcription in this repository mistyped the venue token as "IROM";
  corrected 2026-09-11 — see `raw/round1_correction_A.json` §`revisions`.)
  A predecessor paper by the same group: *Path planning for localization of an RF
  source by multiple UAVs on the Crammer-Rao Lower Bound*, ICRoM 2013,
  `10.1109/ICRoM.2013.6510083`.
- **Maps to**: 问题 3
- **Why Tier 1**: the most concrete implementation of the decision loop — candidate
  waypoints evaluated by a local CRLB at each candidate, discrete candidate set,
  single-step lookahead over an EKF. **Scope warning carried from Round 1**: only the
  *sequential decision architecture* transfers. Its measurement model is DRSSI/RSSI;
  B题's is bearing/AOA with a hard ±1° bound. Do not carry the measurement equations
  across.

### 7. Song, Kim & Yi 2012 — *Simultaneous Localization of Multiple Unknown and Transient Radio Sources Using a Mobile Robot*

- **Provenance**: **post-Round-1 teammate-supplied supplemental anchor**; not a
  Round 1 search result.
- **Authors**: Dezhen Song; Chang-Young Kim; Jingang Yi
- **Venue / year**: IEEE Transactions on Robotics, vol. 28, no. 3, pp. 668-680,
  June 2012
- **DOI**: `10.1109/TRO.2012.2183069`
- **Maps to**: 问题 3 directly; 问题 4 as a belief-update/negative-evidence bridge
- **Deep-reading correction**: SPOG means spatiotemporal probability occupancy grid.
  It updates when a transmission is detected; the paper does **not** supply an
  explicit spatial no-signal update. Its transient source is time-intermittent and
  omnidirectional; it does not solve B题's directional emitter physics.

---

## C. Deep-reading extraction checklist

For each paper, extract — from the full text, not the abstract:

1. The actual problem the paper defines (its assumptions and its scope).
2. The **measurement model** (what is measured; bearing / range / RSS / visibility).
3. The **noise and uncertainty assumptions** (Gaussian, unknown-but-bounded, interval,
   bounded set; what is assumed known).
4. The **state / feasible-set representation** (point estimate, ellipsoid, zonotope,
   polytope, convex polygon, geodesic ball, set of sets).
5. The **objective function** (and, where an information matrix is involved, *which
   scalar criterion*: A-, D-, E-optimality, det, trace, λ_min — never "maximize FIM"
   as a bare phrase).
6. The **theorem / proposition / closed-form result**, with its regularity conditions.
7. The **algorithm / pseudocode**.
8. **Computational complexity** of the algorithm.
9. The **experiment / simulation setup** (what was validated, and how).
10. **What transfers** to B题 — and why.
11. **What does not transfer** — and why.
12. **Concrete implications for 问题 1 / 2 / 3 / 4**, stated as implications, not as hopes.

---

## D. Reading discipline

- **Do not read only the abstract.** Round 1 was built from metadata; the algorithms
  and conditions live in the bodies. Anything asserted from an abstract is a hypothesis.
- **Do not infer formulas from the title.** If a formula is not in the text, it does
  not exist.
- **Do not rewrite a range / RSSI / visibility model as a bearing model.** Three of the
  six (Calafiore; Reynaud; Dehghan) measure something other than bearing. Carry the
  geometry, not the measurement equations.
- **Do not migrate Gaussian-noise conclusions into a hard ±1° bound.** B题's error is a
  deterministic interval, not a variance, and at a fixed detection point it is not
  even random. Any hard-bound → variance mapping is a modelling decision that must be
  argued, not assumed.
- **Separate the paper's own claims from your inferences about B题.** Mark them
  differently in the notes.
- **Anchor every citation of a formula, theorem or result to page / section /
  equation number.**
- **Keep absence claims as search observations.** "Not found in this controlled
  search" is never "does not exist in the literature."

### Traps already known to exist in the Round 1 corpus

Carried here so the deep reading does not inherit them:

- **Dehghan 2014** — the architecture matches; the measurement model does not. Round 1
  initially claimed an "exact structural match" and retracted it.
- **Zhao / Chen / Lee 2012 + 2013** — conference version and journal extension of one
  work. One slot, not two.
- **Ordinary zonotopes are closed under affine maps and Minkowski sums but generally
  NOT under intersection.** Exact intersection needs constrained zonotopes, zonotope
  bundles, or an outer approximation. Do not use zonotope intersection closure to
  justify an angular-sector intersection design.
- **2014 / 2016 / 2017 in the Liu–Zhao–Wu line are three distinct works.** The 2014
  PLANS paper is bearing-only with mixed uncertainty; the 2016 IJDSN paper is *not*
  bearing-only (generic nonlinear system); the 2017 journal paper is bearing-only
  set-membership with ellipsoidal outer bounding.
- **CLOSURE (RSS 2024)** is SE(3) pose from keypoints, not 2D bearing. Its contribution
  here is the *worst-case-error-bound-as-minimum-enclosing-ball* idea.
- **Fisher information is not Gaussian-only.** The limitation is that the FIM/CRLB
  placement/planning works recruited into this corpus use probabilistic noise models
  and generally need a given measurement variance.

---

## E. Recommended reading order

**Wave 1 — establish the three foundations**

| Order | Paper | What it establishes |
|---|---|---|
| 1 | Isler & Bajcsy 2006 | bounded-set geometry: measurement = convex polygon, merge = intersection, uncertainty = set size, plus sensor selection |
| 2 | Zhao, Chen & Lee 2013 | second-point geometry: necessary and sufficient conditions for optimal placement, with explicit constructions |
| 3 | Reynaud et al. 2018 | unknown-target search architecture: the set of not-yet-discovered targets drives the control input |

**Wave 2 — fill in formalism, prior, and implementation**

| Order | Paper | What it adds |
|---|---|---|
| 4 | Calafiore 2026 | set-membership localization formalism: compatible set → polytope → tight outer bounding as a guaranteed estimate |
| 5 | Yang et al. 2013 | prior-aware probabilistic placement: how an existing measurement/prior enters the criterion |
| 6 | Dehghan et al. 2014 | RF/UAV next-waypoint implementation: candidate generation, single-step lookahead, and where its DRSSI model parts company with B题 |

Wave 1 is ordered so that the geometry, the second-observation criterion and the search
architecture are each grounded before the papers that assume them. Wave 2 then supplies
the formalism (Calafiore), the prior-aware criterion (Yang) and a working implementation
sketch (Dehghan).

---

## F. Where the results should land

Deep-reading notes are inputs to modelling, not a paper. Keep the distinction between
*what the literature says* and *what B题 will do* visible in whatever artefact comes
out of this reading — the same evidence chain the repository requires:
`problem/data -> assumptions -> model -> implementation -> experiment -> conclusion`.
