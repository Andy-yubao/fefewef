# Task 3 Sensitivity Analysis Design

Date: 2026-09-13  
Current policy: `candidate_057_posterior_free`

## Questions

The analysis separates four questions that require different evidence:

1. How stable are the observed clearance and time metrics across the existing
   100 random scenarios?
2. Which observed scenario attributes are associated with performance?
3. How would interface-cost changes affect the already executed trajectories?
4. Which policy mechanisms require controlled reruns before a causal
   sensitivity claim is defensible?

## Phase A: analysis that uses existing runs only

The following analyses do not run the simulator again:

- integrity, clearance, time-accounting, bootstrap, and leave-one-out checks;
- source-count strata for `N=10,...,16`;
- decomposition into movement, measurement, switching, optical, and laser
  time;
- threshold curves for total time and time per source;
- scenario features derived from the frozen source truth: radial distribution,
  reception radius, angular gap, centroid offset, and nearest-neighbor spacing;
- Spearman associations and exploratory HC3 regressions;
- frozen-trajectory counterfactuals for speed and interface durations;
- the existing 30-case paired comparison between candidates 041 and 057;
- five-case development diagnostics for opportunistic probes and posterior
  completion under two route-ordering backgrounds.

The primary data set is the 100-case log beginning at seed `20261310`. The
30-case comparison uses seeds `20261210` through `20261239`. The five-case
mechanism diagnostics use seeds `20261110` through `20261114`.

## Original Phase B: full confirmatory design

These questions change observations or decisions and therefore cannot be
answered by reweighting existing output:

### Policy-parameter design

Use common random numbers and full within-scenario pairing. A screening design
should cover at least:

| Factor | Proposed levels | Reason |
|---|---|---|
| Grid step | 2.5, 5, 10 m | accuracy/runtime and certificate conservatism |
| Opportunistic probe budget | 0, 12, 24, 48 | travel saved versus failed optical probes |
| Optical probe limit | 0, 1, 2, 3 | per-source exploration intensity |
| Completion sample count | 5, 15, 30 | posterior rollout fidelity/runtime |
| Shared stop measurements | off/on | measurement cost versus avoided travel |
| Free coverage order | off/on | route shortening and tail risk |
| Posterior completion | off/on | reception-radius inference value |

A first pass can use a resolution-IV fractional factorial or a deliberately
balanced mechanism ablation. It should use at least 100 base scenarios per
configuration and must retain failed cases. Any promoted setting should then
be checked on a separate 500-case holdout.

### Physical and scenario design

Freeze a latent source template per base seed, then vary one factor without
regenerating unrelated source attributes:

| Factor | Proposed levels |
|---|---|
| Source count | 10, 13, 16 |
| Bearing-error bound | 0.5, 1.0, 1.5 degrees |
| Reception-radius band | [975,1475], [1000,1500], [1100,1600] m |
| Spatial pattern | area-uniform, boundary-heavy, clustered |
| Minimum separation stress | unconstrained, near-coincident pairs |

The core design is `3 source counts × 3 bearing errors × 3 reception bands`,
blocked by base seed. Spatial stress tests should be reported separately
rather than mixed into a single average.

## Executed time-bounded screening design

The user subsequently imposed a 30-minute wall-clock limit. The full design
above was therefore replaced by the following screening design:

- P1: 11 configurations on 12 common random scenarios, 132 runs;
- P2: a balanced three-factor, three-level L9 orthogonal array in 12 seed
  blocks, 108 runs;
- P3: five spatial patterns by three source counts in six seed blocks, 90
  runs.

The formal total is 330 runs. It completed in 432.74 seconds with 30 workers.
An additional 90-run P3 repeat matched the formal P3 output exactly and is
retained as a determinism check, but it is not counted as additional evidence.

The lower reception band starts at 975 m because the current coverage layout's
analytic worst distance is about 968.90 m. A 900 m minimum would be rejected as
an invalid coverage configuration before strategy execution.

This efficient design is suitable for detecting large main effects and
failure modes. With only 12 P1/P2 blocks and six P3 blocks, it is not a
replacement for the full confirmatory sample sizes described above.

## Required reporting

Every phase must report full-clear rate, aggregate seconds per source, mean and
P95 case time, threshold attainment, cost components, algorithm wall time,
bootstrap intervals, seeds, configuration, code hashes, and all failures.
Observed associations, frozen-trajectory accounting effects, and controlled
causal effects must remain explicitly distinguished.
