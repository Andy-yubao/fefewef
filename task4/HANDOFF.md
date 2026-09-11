# T4 Engineering Handoff

## Objective

Deliver a runnable CUMCM B Problem 4 robot with an official-compatible seeded local evaluator, a shared local/remote API layer, reproducible strategy experiments, and a safe remote entry point. The current optimization specifically addresses the prior online run's excessive no-signal measurements and end-loaded clearing.

## Current status

The system is implemented and tested. Thirteen strategies are registered, with each concrete strategy in its own file. The latest test suite has 21 unit/integration tests. A further ten optimization iterations are recorded in `experiments/t4_analysis/outputs/iterations/ITERATION_REPORT.md`.

The recommended default is now `clear_probe`: 735 m triangular lattice, rolling joint open-TSP over coverage/clear nodes, reuse of clear positions to replace at most two grid probes within 400 m, and receiver-aware channel ordering. It cleared 1000/1000 tuning cases, 1000/1000 disjoint holdout cases, 500/500 all-directional cases, and 500/500 all-omni cases. Final tuning-set mean is 9135.6 s versus 10008.4 s for the former `opportunistic` default.

## Architecture

`experiments/t4_local/engine.py` owns hidden truth. Strategies only receive the same four methods exposed by `HTTPClient` and `InProcessClient`; they cannot reach simulator truth. `BaseStrategy` owns channel state and common measure/clear handling. Positive bearings produce intersections of +/-1.01 degree wedges, clipped by the arena and the 1500 m positive-range bound. The minimum enclosing circle certifies whether a feasible position region fits inside the optical clearing tolerance.

The 760 m triangular lattice retains an ideal-rule discovery fallback. Any source lies in a triangular cell whose vertices are each less than the spacing away; any half-plane through the source contains a cell vertex. Since 760 < the minimum 1000 m receive radius, both omni and 180-degree directional sources have a detectable lattice vertex. Search may extend outside the source arena, which the problem allows.

Offline analysis is deliberately isolated in `experiments/t4_analysis/`. The log analyzer uses robot-visible request/response data only. The summary comparator consumes persisted JSON only, so it cannot leak hidden truth into a running strategy.

## Important files

- `task4/client.py`: retry-safe official HTTP client and equivalent in-process adapter.
- `task4/geometry.py`: bearings, wedge clipping, convex intersections, enclosing circles.
- `task4/search_patterns.py`: triangular-lattice generator.
- `task4/strategies/base.py`: shared beliefs, results, measure/clear wrappers.
- `task4/strategies/coverage.py`: square-grid baseline.
- `task4/strategies/active.py`: immediate geometry-oriented localization.
- `task4/strategies/reacquire.py`: directional loss recovery.
- `task4/strategies/deferred.py`: old square-grid/deferred-clear reference plus extension hooks.
- `task4/strategies/lattice.py`: triangular coverage.
- `task4/strategies/opportunistic.py`: opportunistic mid-search clearing.
- `task4/strategies/belief.py`: visibility particles and approximate-EIG route ordering.
- `task4/strategies/integrated_route.py`: rolling joint route over search and clear nodes.
- `task4/strategies/clear_probe.py`: current default, clear-site probe reuse.
- `task4/strategies/route_optimized.py`, `local_eig.py`, `rejoin_clear.py`, `early_stop.py`: retained iteration/ablation strategies.
- `task4/strategies/registry.py`: single registry/factory.
- `task4/cli.py`: local, batch, config-check, and explicitly guarded remote commands.
- `experiments/t4_local/engine.py`: seeded evaluator, legality, virtual time, and metrics.
- `experiments/t4_local/benchmark.py`: batch runner and persisted case/tail summaries.
- `experiments/t4_analysis/analyze_action_log.py`: standalone action-log diagnosis.
- `experiments/t4_analysis/compare_summaries.py`: standalone persisted-result comparison.
- `experiments/t4_analysis/plot_action_logs.py`: dependency-free SVG rendering of paths, measurement sites, clears, and post-run local truth.
- `experiments/t4_analysis/analyze_benchmark_features.py`: persisted-CSV distribution, grouping, correlation, tail, and representativeness analysis.
- `experiments/t4_analysis/outputs/`: parameter sweeps and final evidence.
- `task4/README.md`: authoritative Chinese operator documentation.

## Implemented strategies

- `coverage`: 600 m square serpentine baseline, passive bearing intersections.
- `active`: immediately leaves coverage to improve crossing geometry; stops on first loss.
- `reacquire`: tries mirrored lateral/arc probes after directional loss.
- `deferred`: old square-grid method, channel retirement, residual reacquisition, all clearing at the end.
- `lattice`: `deferred` logic with a tuned 760 m triangular lattice.
- `opportunistic`: `lattice` plus mid-search clearing when route insertion cost is at most 1500 m. This is the default recommendation.
- `belief`: `opportunistic` plus deterministic `(x,y,radius,type,direction)` visibility particles. No-signal observations eliminate particles; a score combining visibility probability, binary entropy, active-bearing crossing geometry, and travel penalty chooses the next point.
- `integrated_route`: rolling open-TSP over remaining coverage vertices and located clear targets.
- `clear_probe`: current best; `integrated_route` plus post-clear measurements, conservative nearby waypoint replacement, and receiver-aware alternating channel scans.
- `route_optimized`, `local_eig`, `rejoin_clear`, `early_stop`: negative/ablation strategies retained for reproducibility. Early stop is explicitly unsafe for formal use.

## Online-log diagnosis

The old online case `YJVS-K983-5KCS-NAX5` used `deferred / 600 / 1800`. It had 671 accepted actions, 658 measurements, 611 no-signals (92.86%), and 11 successful clears. There were 49 unique measurement positions. The first clear was action 660, the last measurement action 659, so every clear was end-loaded. There were 170 no-signals on channels that were eventually found. The API does not expose the hidden emitter count, so 11/11 successful attempts is not proof that all case emitters were cleared; GUI confirmation is still needed.

Artifacts:

- Original client log: `task4/outputs/official/YJVS-K983-5KCS-NAX5.json`
- Robot-visible analysis: `experiments/t4_analysis/outputs/YJVS-K983-5KCS-NAX5-analysis.{json,md}`

## Experiments completed

All results below are local-simulator evidence, except the explicitly identified online-log diagnosis.

1. Lattice spacing sweep on seeds 0--99: 700, 725, 750, 760, 770, 775, 780, 790, 800, 850, 900, 950, 980 m. 760 m was best in mean and strong in P95; the non-monotonic result comes from finite-disk lattice topology and route length.
2. Opportunistic threshold sweep on seeds 0--99: 0, 50, 100, 200, 300, 500, 750, 1000, 1500, 3000, 100000 m. 1500 m had the best mean; 3000 m had a slightly better P95.
3. Belief travel-weight sweep on seeds 0--99: 1.5, 2.5, 4, 6, 8, 12, 16, 24, 40, 80. Low weights caused expensive cross-arena jumps; 16 was selected.
4. Disjoint holdout seeds 1000--1199: all four compared methods cleared 200/200. `opportunistic` reduced mean total time 16.05% versus `deferred`; `belief` reduced it 15.91%.
5. Final seeds 0--999: all methods in the table below cleared 1000/1000.
6. Stress seeds 2000--2499: both candidates cleared 500/500 all-directional and 500/500 all-omnidirectional cases.
7. Local HTTP end-to-end, seed 42, `opportunistic`: 15/15 cleared, 466 actions, 9245.444406 s virtual; HTTP and in-process results matched.
8. Three reproducibly randomized visualization cases selected with RNG seed 2026091103: case seeds 869462, 379913, 24546. All 38/38 emitters were cleared; total times were 9185.02, 9594.36, and 9956.30 s. SVGs and summaries are under `experiments/t4_analysis/outputs/random3/figures/`.
9. Feature analysis of the final 1000 `opportunistic` cases: mean/SD total time 10008.4/672.1 s, movement share 70.25%, measurement share 24.26%, mean no-signal rate 90.33%, movement/time correlation 0.856. High directional-fraction cases averaged 592.7 s slower than low-fraction cases. Report: `experiments/t4_analysis/outputs/feature_analysis/feature_report.{json,md}`.

## Key numerical findings

### Final shared 1000-case benchmark

| Strategy | Mean total (s) | vs deferred | P95 (s) | Max (s) | Mean move (m) | Measures | No-signals | First clear (s) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| deferred | 11938.3 | baseline | 12820.7 | 13684.0 | 40812 | 618.8 | 567.4 | 10077.4 |
| lattice | 10619.4 | -11.05% | 11465.1 | 12688.5 | 38201 | 486.0 | 440.1 | 8740.4 |
| opportunistic | **10008.4** | **-16.17%** | **10954.7** | **12002.9** | **35157** | 485.7 | 440.0 | 1099.6 |
| belief | 10051.6 | -15.80% | 11160.8 | 12706.5 | 36772 | **439.0** | **394.6** | **711.4** |

Relative to `opportunistic`, `belief` uses about 9.6% fewer measurements and 10.3% fewer no-signal measurements, and clears first about 388 s earlier, at a 0.43% mean-total-time cost.

### Stress tests

| Strategy | Environment | All clear | Mean total (s) | P95 (s) | Mean measures | First clear (s) |
|---|---|---:|---:|---:|---:|---:|
| opportunistic | all directional | 500/500 | 10682.0 | 11706.0 | 524.7 | 1723.0 |
| belief | all directional | 500/500 | 10812.0 | 11937.2 | 484.0 | 976.3 |
| opportunistic | all omni | 500/500 | 9217.0 | 10073.8 | 438.4 | 788.0 |
| belief | all omni | 500/500 | 9192.5 | 10264.3 | 384.8 | 594.0 |

## Current best strategy/configuration

Use `clear_probe` with `lattice_spacing=735`, `replacement_distance_m=400`, and `max_replaced_waypoints=2`. Final seeds 0--999: 1000/1000 all clear, mean 9135.59 s, P95 10113.22 s, max 11820.43 s, mean movement 30669.87 m. A disjoint 1000-case set and both 500-case type extremes also had zero failures. Larger replacement radii and early stopping were faster but missed emitters, so they are not recommended. The approximately 8000 s target was reached only approximately in all-omni data (8257.5 s), not in the mixed or all-directional distributions.

## Failed or dominated approaches

- `active` and `reacquire` were reliable but much slower because repeated grid-to-source detours increased movement to roughly 60--62 km in the original 100-case comparison.
- A 900 m triangular lattice used fewer points but produced a longer route; on seeds 0--99 its mean was 12548.6 s versus 10683.7 s at 760 m.
- Opportunistic threshold 0 behaved almost like deferred clearing and was slow (12688.3 s); 1500 m was much better (10036.4 s) on the tuning set.
- Belief travel weight 1.5 overvalued information and crossed the arena too often (13444.3 s); weight 16 reduced the tuning-set mean to 10065.2 s.
- Full POMDP planning was not implemented. The lightweight visibility bitset captures useful negative-observation information without compromising the deterministic coverage fallback.

## Known bugs / limitations

- Official generation distributions are hidden. Local source-count, type, position, radius, direction, and error distributions are explicit assumptions, not official facts.
- The local server omits some peripheral official behavior: concurrent-new-action 409 handling, 429 throttling, GUI's 25-minute window, and socket closure after GUI termination.
- The particle prior can be distribution-mismatched. Coverage still guarantees discovery under the modeled ideal geometry, but efficiency could shift online.
- `no_signal` remains inherently ambiguous. The implementation resolves ambiguity only cumulatively: particles visible at a tested point are removed, while remaining particles include far, opposite-half-plane, and other still-consistent explanations. A channel is never declared absent from one negative.
- The new strategies have not yet been run on another online evaluator case. Do not claim local improvements as official scores.

## Important assumptions

Local emitter count is discrete uniform 10--16; channels are sampled without replacement; positions are area-uniform in the 1800 m disk; radii are uniform 1000--1500 m; type is Bernoulli with configurable probability; directions are uniform; bearing error is a deterministic hash mapped to [-1,1] degrees. Only the stated physical ranges/rules are problem facts.

## Next recommended steps

1. Run `config-check` and one official rehearsal with `clear_probe`, preserving the full client log and official encrypted log.
2. Confirm in the GUI that every emitter was cleared; API clear successes alone do not reveal total source count.
3. Analyze that new log with `experiments.t4_analysis.analyze_action_log` and compare no-signal count, first-clear action, total virtual time, and completion against the old online case.
4. If `clear_probe` reveals an official-only miss, fall back to guarantee-preserving `integrated_route` before changing geometry.
5. Do not spend a formal test before checking Problem 4 selection, team/case IDs, port forwarding, output path, countdown, and exact strategy parameters.

## Exact reproduction commands

```bash
python3 -m unittest discover -s task4/tests -v
python3 -m task4.cli run --mode local --strategy clear_probe --seed 42 --output task4/outputs/seed42.json
python3 -m task4.cli batch --strategy clear_probe --seed-start 0 --cases 1000 --output-dir experiments/t4_analysis/outputs/final_optimized1000/clear_probe_final
python3 -m task4.cli batch --strategy opportunistic --seed-start 0 --cases 1000 --output-dir experiments/t4_analysis/outputs/final1000/opportunistic
python3 -m task4.cli batch --strategy belief --seed-start 0 --cases 1000 --output-dir experiments/t4_analysis/outputs/final1000/belief
python3 -m task4.cli batch --strategy opportunistic --seed-start 2000 --cases 500 --directional-probability 1 --output-dir experiments/t4_analysis/outputs/stress500/opp_dir
python3 -m task4.cli batch --strategy belief --seed-start 2000 --cases 500 --directional-probability 0 --output-dir experiments/t4_analysis/outputs/stress500/belief_omni
python3 -m experiments.t4_analysis.analyze_action_log task4/outputs/official/YJVS-K983-5KCS-NAX5.json --output-dir experiments/t4_analysis/outputs
python3 -m experiments.t4_analysis.compare_summaries experiments/t4_analysis/outputs/final1000/deferred/summary.json experiments/t4_analysis/outputs/final1000/lattice/summary.json experiments/t4_analysis/outputs/final1000/opportunistic/summary.json experiments/t4_analysis/outputs/final1000/belief/summary.json --baseline-label deferred --output-dir experiments/t4_analysis/outputs/final1000/comparison
python3 -m experiments.t4_analysis.plot_action_logs experiments/t4_analysis/outputs/random3/seed_869462.json experiments/t4_analysis/outputs/random3/seed_379913.json experiments/t4_analysis/outputs/random3/seed_24546.json --selection-seed 2026091103 --output-dir experiments/t4_analysis/outputs/random3/figures
python3 -m experiments.t4_local.server --seed 42 --port 2027
python3 -m task4.cli config-check --server http://172.26.112.1:2027 --robot-id '<actual-team-id>'
```

Remote execution additionally requires `--mode remote`, an output file, and `--confirm-remote I_UNDERSTAND_THIS_USES_AN_OFFICIAL_TEST`; see the Chinese README. Do not execute it merely to validate configuration.
