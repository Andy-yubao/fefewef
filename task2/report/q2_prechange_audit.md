# Q2 pre-change audit (2026-09-11)

This record freezes the implementation state inspected before the Q2 repair.

## Mathematical and implementation state

- **Problem facts:** the target is in the radius-1800 m disk; bearing error is
  bounded by +/-1 degree; an omnidirectional source has an unknown reception
  radius in [1000,1500] m; within 5 m a bearing is unavailable and optical
  localization may start.
- **First feasible region:** the target disk intersected with the first bearing
  sector, conservatively capped at 1500 m and excluding the 5 m near disk.
- **Candidate region:** a 250 m grid inside the target disk. The old practical
  pool imposed `p_det >= 0.25` and median `|sin(alpha)| >= 0.12`. The disk and
  thresholds are modeling/computational choices, not problem facts.
- **Expected/Minimax Diameter:** bounded-linearization proxy on the full grid,
  six-point shortlist, then exact set diameter with 10 target particles and
  three error nodes. The sampled hidden radius generated the outcome and was
  incorrectly reused as a known posterior range/removal radius.
- **Geometry:** a detection-weighted intersection-angle/range heuristic. It is
  our heuristic, motivated but not proved optimal by bearing-only literature.
- **GDOP/FIM:** local Gaussian information approximations over posterior
  particles, with a first-region-diameter no-bearing penalty. They are baseline
  structures under extra local/Gaussian assumptions, not hard-bound guarantees.
- **EIG:** discretized bearing/no-signal/near expected information under our
  posterior and binning assumptions. **Random:** sampled the same pruned grid.
- **Experiment/figures:** 400 base scenarios x 25 replicates, seed 20260911,
  ten strategies and 100000 evaluator rows. Figures came from raw CSVs through
  `make_figures.py`.
- **Old report conclusion:** Expected Diameter had the lowest mean (53.01 m),
  but that result was not admissible as final evidence because its planner and
  the already-conservative evaluator used different information models.

## Evidence boundary

- **Literature:** Isler & Bajcsy support bounded consistency sets/intersection;
  Calafiore supports containment terminology; Reynaud et al. support predicted
  future set-size actions and negative information under a declared detection
  model; Zhao et al. support local bearing-only FIM and conditional orthogonal
  geometry.
- **Our assumptions:** area-uniform position prior in F1, conditional-uniform
  radius prior, probability weights inside the hard bearing bound, finite
  candidate domains, grids, pruning thresholds and quadrature/Monte Carlo.
- **Our algorithms:** expected Q1 diameter utility, outcome-aware hard-bound
  action scoring, coarse-to-fine refinement and the benchmark/ablation design.

The repair therefore keeps hidden radius only in the outcome simulator. A
bearing update uses the observable 1500 m conservative cap, no-signal removes
only the guaranteed 1000 m disk, and near/optical has Q2 diameter and area zero.
