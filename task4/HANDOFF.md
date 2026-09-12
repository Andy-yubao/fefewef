# T4 Engineering Handoff

Last reviewed: 2026-09-12 (Asia/Shanghai)

## Objective

Deliver a runnable solution for CUMCM Problem B, Task 4: an official-compatible seeded local evaluator, one local/remote robot client, reusable geometry and state handling, independently registered strategies, reproducible experiments, failure analysis, visualizations, and a deliberately guarded official-test entry point. Zero misses remain preferred; the current user-approved acceptance boundary is an estimated incomplete-case probability no greater than 1%, followed by minimum mean virtual time without excessive real runtime.

## Evidence boundary and current status

- The implementation is runnable. There are 27 registered strategies, each with its own concrete strategy file, plus shared behavior in `base.py`.
- The last executed full test suite had 26/26 unit and integration tests passing, including HTTP tests. The CLI-default seed-257 and seed-918 reruns cleared 12/12 in 6933.93 s and 16/16 in 8535.89 s.
- The current CLI default and risk-budgeted local recommendation are `geometry_early_optical_clear_probe` with `lattice_spacing=731`, `replacement_distance_m=550`, `max_replaced_waypoints=2`, `early_clear_radius_m=35`, and `route_length_slack_m=100`.
- A new CLI-registered candidate, `double_ring_optical_clear_probe`, uses a 25-point double-ring discovery cover with no waypoint replacement by default, a certified seven-disk fallback for 35 m feasible regions, and a full positive-bearing optical-strip endgame. A fresh mixed 1000 was 1000/1000 all-clear at mean/P95 6622.84/7716.41 s; a fresh all-directional 300 was 300/300 at 7486.88/8891.01 s. It is not the CLI default because it has not reached the 6000 s mixed mean and has no official run.
- The older `replacement_aware_clear_probe / 731 / 400 / 2` setting was 1000/1000 all-clear on seeds 0--999, 1000/1000 on disjoint seeds 1000--1999, 500/500 in all-directional stress, and 500/500 in all-omnidirectional stress.
- An additional 1000 unique 32-bit seeds selected at run time from operating-system entropy were 1000/1000 all-clear for that older setting: minimum/mean/median/P95/P99/maximum 5527.82/8909.21/8908.40/9967.15/10467.40/11133.29 s. The exact sampled seeds were persisted before execution.
- On those same random 1000, 30 m early optical was also 1000/1000 and reduced mean/P95/maximum to 8353.66/9290.72/10261.54 s. Paired random all-directional and all-omni sets of 200 each were all clear at 9075.41 and 7535.33 s mean.
- Combining early optical with the robot-visible geometry route tie-break passed paired random 100/300 and 100-case directional/omni stresses. Its earlier 400 m version had a fresh OS-entropy random 1000 at 1000/1000 all-clear and minimum/mean/median/P95/P99/maximum 4299.72/8133.23/8186.92/8982.90/9498.41/10731.29 s.
- A fresh OS-entropy all-directional 300 also passed 300/300 at minimum/mean/median/P95/maximum 6552.27/8833.18/8799.38/9812.92/10727.76 s. With zero failures, its one-sided 95% binomial upper bound is about 0.994%; this is evidence only for the stated local distribution.
- At 550 m, a new OS-entropy mixed 1000 was 999/1000 at minimum/mean/median/P95/P99/maximum 5252.97/7878.29/7910.04/8836.33/9343.67/9794.08 s. A new all-directional 1000 was 998/1000 at 6302.65/8674.85/8642.54/9792.46/10302.60/10891.37 s. Their exact one-sided 95% incomplete-case upper bounds are 0.4735% and 0.6282%, below the approved 1% boundary.
- The historical iteration-18 seeds 0--999 mean is 8919.61 s with P95 9911.17 s. This is 2.36% below the prior `clear_probe / 735 / 400 / 2` recommendation, 10.88% below `opportunistic`, and 25.29% below `deferred`.
- One explicitly authorized official run now exists for the optimized default, in addition to the older `deferred` run. Never present local-batch numbers as official scores.
- The official API never reveals the true emitter count. A list of successful clear calls does not prove full completion; the evaluator GUI must be checked.
- The iteration-18--37 implementation, documents, and generated experiment outputs are currently uncommitted. Preserve the pre-existing user change in this handoff file and review `git status` before any commit.

## Rules that drive the design

- The arena is the disk of radius 1800 m. Robot queries may be outside it.
- A case has an unknown 10--16 emitters on unique channels from 1--20. T4 mixes omni and directional emitters.
- Receive radius is in [1000, 1500] m. A directional source covers a 180-degree half-plane with unknown direction.
- A positive measurement returns a bearing with a fixed-at-that-location error in [-1 degree, +1 degree]. Repeating a measurement at the same point does not resample the error.
- A `no_signal` can mean: no uncleared source on the channel, out of range, or outside a directional source's half-plane. One negative is never enough to declare a channel absent.
- At distance <=5 m inside radio coverage, the response is too strong for a bearing and direct optical clearing is appropriate.
- Optical clearing succeeds within 20 m regardless of directional coverage. A failed clear costs 3 s; a successful clear costs 5 s.
- Movement is straight-line at 5 m/s. A measurement costs 5 s, plus 1 s if its channel differs from the receiver's current channel. `/clear` neither switches nor changes the receiver channel.
- The receiver starts on channel 1. Actions are strictly serial. Network retry must reuse the exact same request and `request_id`.
- `/enter` and `/exit` are the only other protocol actions. Real-time limits must use `remaining_real_duration_s`; virtual time is capped at 360000 s.

## Architecture and invariants

`experiments/t4_local/engine.py` owns hidden truth. Strategy code sees only the methods shared by `HTTPClient` and `InProcessClient`. Do not add a strategy path that imports or introspects simulator emitters.

`BaseStrategy` owns channel lifecycle, feasible bearing regions, action accounting, common measurement/clear wrappers, and the receiver's current channel. HTTP/API behavior and geometry must remain single implementations; a strategy should decide what to do next, not duplicate those layers.

Positive bearings are converted to intersections of +/-1.01-degree wedges, clipped to the arena and to the 1500 m positive-range disk. The slight 0.01-degree padding prevents boundary loss from floating-point arithmetic. A minimum enclosing circle with a 19.5 m threshold is used to decide that the feasible region is safe to clear within the official 20 m optical radius.

The 731 m triangular lattice is the current base coverage. Under ideal problem geometry, every point in a triangular cell is within 731 m of all three vertices, and any half-plane through the source contains at least one cell vertex. Because 731 < the minimum 1000 m receive radius, an unmodified lattice supplies a discovery fallback for both omni and 180-degree directional sources. The narrow 730.5--735 m sweep found that 731 m is just above the tested topology transition from 43 to 37 generated points.

Important distinction: `replacement_aware_clear_probe` still removes up to two unvisited lattice points within 400 m of a successful clear. Route awareness changes when clears are visited, not the proof status. Despite zero observed failures over 3000 final-candidate cases, its replacement reliability is empirical. `certified_clear_probe` is the slower alternative whose six-neighbor substitution has a local triangular coverage certificate.

The current fused strategy raises that empirical radius to 550 m under the explicit <=1% incomplete-case allowance. Its mixed and all-directional confidence bounds satisfy that statistical boundary, but it has observed failures and does not restore the triangular-lattice proof.

Offline diagnosis is isolated in `experiments/t4_analysis/`. An analyzer may use local truth only after a run for evaluation/plotting; it must never feed that truth back to a live strategy. The robot-visible log analyzer and persisted-summary comparator do not require simulator truth.

## Important files

- `task4/client.py`: retry-safe official HTTP client and equivalent in-process client.
- `task4/geometry.py`: angles, bearing wedges, polygon intersection, and enclosing circles.
- `task4/search_patterns.py`: coverage-pattern generation.
- `task4/strategies/base.py`: shared channel/belief state and action wrappers.
- `task4/strategies/registry.py`: the only strategy registry/factory.
- `task4/strategies/*.py`: one file per concrete strategy.
- `task4/cli.py`: local, batch, config-check, and guarded remote entry points.
- `task4/tests/`: geometry, engine, strategy, HTTP, and regression tests.
- `experiments/t4_local/engine.py`: seeded environment, legality, time, metrics, and logs.
- `experiments/t4_local/server.py`: official-shaped local HTTP service.
- `experiments/t4_local/benchmark.py`: same-seed batch runner and CSV/JSON/Markdown summaries.
- `experiments/t4_analysis/analyze_action_log.py`: standalone robot-visible log diagnosis.
- `experiments/t4_analysis/analyze_benchmark_features.py`: standalone feature/tail analysis.
- `experiments/t4_analysis/analyze_coverage_failure.py`: post-run local-truth diagnosis of skipped probes and missed emitters; never imported by a strategy.
- `experiments/t4_analysis/random_benchmark.py`: selects unique seeds from operating-system entropy, runs a local batch, and reports minimum/mean/dispersion/tails while preserving the sampled seed manifest.
- `experiments/t4_analysis/compare_summaries.py`: standalone persisted-result comparison.
- `experiments/t4_analysis/plot_action_logs.py`: dependency-free SVG path/probe/clear plots; local truth is shown post-run only.
- `experiments/t4_analysis/outputs/iterations/ITERATION_REPORT.md`: optimization diary and reliability boundary.
- `task4/README.md`: authoritative Chinese operating guide and current recommendation.

## Implemented strategies

- `coverage`: 600 m square serpentine baseline with passive bearing intersections.
- `active`: detours immediately for improved crossing geometry after detection.
- `reacquire`: adds lateral/arc probes after a directional signal loss.
- `deferred`: old square-grid reference; finds first and clears everything at the end.
- `lattice`: deferred behavior on a triangular lattice.
- `opportunistic`: lattice search with insertion-priced mid-search clearing; former default.
- `belief`: deterministic particles over `(x,y,radius,type,direction)`, updated by positive and negative visibility, plus an approximate information/travel score.
- `route_optimized`: fixed open 2-opt coverage route with forced re-entry; retained as an ablation.
- `local_eig`: restricts approximate-EIG selection to nearby/equidistant points; retained as an ablation.
- `rejoin_clear`: prices a clear against the best post-clear coverage re-entry; retained as an ablation.
- `early_stop`: terminates coverage after a discovery drought/minimum-known threshold; unsafe and retained only to reproduce failures.
- `integrated_route`: repeatedly solves a joint open route over unvisited lattice probes and clearable targets. This is the conservative fallback because it does not remove coverage points.
- `clear_probe`: `integrated_route` plus measuring unresolved channels at successful-clear sites, replacing at most two nearby unvisited probes, and alternating scan direction based on the receiver channel. This is the former default.
- `clear_probe_multistart`: multi-start open 2-opt ablation for the rolling joint route.
- `certified_clear_probe`: clear-site substitution only when the clear point and six protected neighbors reconstruct the local triangular fan with every edge below 1000 m.
- `active_clear_probe`: measures active channels at every clear site; it helped directional tail metrics but added too many measurements.
- `endgame_clear_probe`: orders residual active channels by their nearest route-compatible candidate; mixed-set behavior was unchanged.
- `optimized_clear_probe`: combination ablation of multi-start, active clear probes, and endgame ordering; movement fell but extra measurements made it slower than multi-start alone.
- `replacement_aware_clear_probe`: former default; multi-start rolling open 2-opt plans over the node set expected after successful 400 m/two-point clear-site substitutions.
- `early_optical_clear_probe`: conservative fallback; iteration-18 routing plus a 30 m feasible-radius optical target and a 5 m failed-target retry shift.
- `ida_heuristic_clear_probe`: depth-3 IDA*-inspired `g+h`/bearing-geometry route evaluator; rejected after an all-directional random failure.
- `geometry_aware_clear_probe`: chooses among near-equal open routes by robot-visible active-bearing crossing geometry; faster in small batches but unsafe because seed 257 regressed.
- `certified_geometry_clear_probe`: applies that route tie-break to six-neighbor certified substitution; the next proof-oriented candidate for larger validation.
- `geometry_early_optical_clear_probe`: current default; combines 35 m early optical clearing with the active-bearing geometry route tie-break and 100 m route slack.
- `guarded_ida_clear_probe`: applies depth-3 `g+h` only among routes meeting a first-step geometry gate; the safe 100% gate was slightly slower overall.
- `relocate_geometry_clear_probe`: adds Or-opt-1 relocation after open 2-opt; rejected because rolling mean and wall time increased.
- `geometry_replacement_clear_probe`: protects replacement candidates with high active-bearing geometry value; rejected after only a 2.67 s random-300 gain and no reduction in batch failures.
- `double_ring_optical_clear_probe`: 25-point double-ring discovery cover with zero replacements by default, certified 35 m seven-disk clearing, and a full positive-bearing optical-strip fallback after radio reacquisition fails. It is the current sub-7000 candidate, not the CLI default.

## Current `geometry_early_optical_clear_probe` decision loop

1. Maintain all unvisited 731 m triangular-lattice probes and all located-but-uncleared targets.
2. For route scoring, provisionally remove up to two pending probes within 550 m of each located clear target, because a successful clear there will scan unresolved channels and substitute those points. This is an empirically validated risk setting, not a coverage certificate.
3. Build deterministic nearest-neighbor routes from every possible first node and improve each with open 2-opt. Among routes no more than 100 m longer than the shortest, prefer the first node with the best robot-visible active-bearing crossing geometry; recompute after every action, with no forced return to an old route.
4. At a coverage probe, scan only unresolved active/unseen channels; cleared channels are retired.
5. Use bearing-wedge intersection to localize. As soon as the feasible set fits within optical tolerance, add it as a clear target; do not spend time estimating source direction.
6. Only after a clear actually succeeds, scan unresolved channels at the same point and remove its actual nearest eligible probes. Failed clears do not delete coverage nodes.
7. Alternate ascending/descending channel order according to the receiver's current channel. This changes switch time only, not geometry or detection outcomes.
8. If a directional source is lost, record the negative without changing an active channel to absent. The base coverage and final reacquisition helper provide spatially distinct later observations.
9. Once the feasible-region radius reaches 35 m, schedule its center for an optical attempt instead of waiting for 19.5 m. A failed 3 s attempt returns the channel to active status and cannot repeat until the estimated center shifts by 5 m.

## Research-derived lessons actually used

- Bounded +/-1-degree bearing error is handled as set membership, not converted silently to independent Gaussian noise. The final feasible region and clear certificate use hard wedge intersections.
- FIM/CRLB and near-orthogonal lines of sight are useful only as local geometry proxies/candidate generators. They are not hard guarantees under this problem's bounded, location-fixed error.
- Active observation is a joint travel-information problem. One-step EIG can save measurements while increasing total time through extra motion; this happened in `belief`/`local_eig` experiments.
- Negative evidence must respect the observation model. A particle/candidate is eliminated by `no_signal` only if that hypothesized `(position,radius,type,direction)` should have been visible there; far and reverse-half-plane hypotheses remain.
- Directional loss calls for lateral motion or spatially separated follow-up observations, but dedicated reacquisition detours are often more expensive than continuing a well-spaced global route.
- Unknown target count requires retaining an undiscovered-state/coverage mechanism. Early stopping based only on discovery drought or currently known source count created false speedups by missing emitters.
- Once position uncertainty is below the clearing tolerance, source-direction estimation has no objective value because optical clearing ignores the directional pattern.

## Official online evidence

With explicit user authorization on 2026-09-12, the current `geometry_early_optical_clear_probe / 731 / 550 / 2 / 35 m / 100 m` default completed one official run through `http://172.26.112.1:2027`. All 534 requests were accepted. The robot made 520 measurements at 37 distinct positions (31 directions and 489 no-signals), attempted 12 clears, and succeeded on 11 channels: 1, 3, 4, 5, 6, 7, 9, 11, 15, 16, and 17. First clear was at 1271.55 s, movement was 33568.85 m, and final virtual time was 9856.77 s. The API did not disclose the total emitter count, so only the GUI can establish whether the case was fully cleared. The log is `task4/outputs/official-run.json`; robot-visible analysis and the path SVG are under `experiments/t4_analysis/outputs/official-run-analysis/` and `experiments/t4_analysis/outputs/official-run-figures/`. The overwritten prior log was preserved as `task4/outputs/official-run.pre-test-20260912.json`.

The earlier official run used `deferred` with a 600 m grid and 1800 m half-extent on case `YJVS-K983-5KCS-NAX5` through the forwarded endpoint `http://172.26.112.1:2027` with team ID `202609001035`.

It produced 671 accepted actions, 658 measurements, 611 `no_signal` responses (92.86%), and 11 successful clears. There were 49 unique measurement positions. The first clear was action 660 and the last measurement was action 659: every clear was end-loaded. There were 170 no-signals on channels that were eventually found. The API did not reveal total source count, so GUI confirmation is required before stating that this run fully cleared the case.

Artifacts:

- `task4/outputs/official/YJVS-K983-5KCS-NAX5.json`: original client log.
- `experiments/t4_analysis/outputs/YJVS-K983-5KCS-NAX5-analysis.json`
- `experiments/t4_analysis/outputs/YJVS-K983-5KCS-NAX5-analysis.md`

## Experiment history and learning

All results in this section are local-simulator evidence.

### Earlier baseline program

- Lattice spacing sweep on seeds 0--99 tested 700--980 m. The earlier opportunistic program selected 760 m; finite-disk lattice topology makes performance non-monotonic.
- Opportunistic clear-threshold sweep selected 1500 m on seeds 0--99.
- Belief travel-weight sweep selected 16. Low travel weights overvalued information and caused cross-arena jumps.
- Seeds 0--999: `deferred` 11938.3 s, `lattice` 10619.4 s, `opportunistic` 10008.4 s, and `belief` 10051.6 s; all were 1000/1000 all-clear.
- `belief` cut measurements/no-signals by roughly 9.6%/10.3% versus `opportunistic` but cost 0.43% mean total time. Movement dominates the objective more than raw detection count.
- Old `opportunistic` stress: all-directional 10682.0 s and all-omni 9217.0 s over 500 cases each, with zero failures.

### Thirty-seven optimization iterations

| Iteration | Change | Cases | All-clear | Mean (s) | Decision |
|---|---|---:|---:|---:|---|
| Reference | `opportunistic`, spacing 760 | 1000 | 100% | 10008.4 | Former best |
| 1 | Fixed open 2-opt with forced rejoin | 100 | 100% | 10305.8 | Reject: rejoin detours |
| 2 | Nearby/equidistant local EIG | 100 | 100% | 10060.8--10076.2 | Reject: movement exceeds saved probes |
| 3 | Clear priced against best re-entry | 100 | 100% | 10077.3 | Mean worse |
| 4 | Discovery-drought early stop | 200 | 94--96% | 9084.6--9313.7 | Reject: missed emitters |
| 5 | Early stop after 11--15 known | 500 | 95.8--99.4% | 9424.8--9922.6 | Reject: still misses |
| 6 | Rolling joint route | 100 | 100% | 9544.8 | Keep |
| 7 | Joint-route spacing 735 | 100 | 100% | 9345.3 | Keep |
| 8--9 | Clear-site probes and conservative replacement | 100--2000 | varies | 8941.7--9333.0 | Select 400 m / max 2 |
| 10 | Receiver-aware scan order | 1000 | 100% | 9135.6 | Former default |
| 11 | Multi-start rolling open 2-opt | 100 | 100% | 9095.9 | Keep route component |
| 12 | Coverage-certified six-neighbor substitution | 100 + regressions | 100% | 9277.5 | Proven but slower fallback |
| 13--15 | Active clear probes, endgame order, and combination | 100-scale | 100% | 9185.1--9107.6 | Tail help or negative |
| 16 | Replacement-aware joint route | 100 | 100% | 9060.2 | Keep |
| 17 | Narrow lattice spacing sweep | 100 + holdout 100 | 100% | 9139.8 at 731 m | Keep 731 m |
| 18 | Replacement-aware route at 731 m | 1000 + 1000 + 500 + 500 | 100% all sets | 8919.6 / 8905.6 | Current default |
| 19 | Active-bearing geometry route tie-break | 4 x 100 + regressions | seed 257 failed | 8723.6 / 8614.8 | Reject despite faster batches |
| 20 | Geometry-route slack sweep, 0--80 m | seed 257 x 5 | 0/5 all-clear | 8174.1 | Reject |
| 21 | Certified substitution plus geometry tie-break | 4 x 100 + regressions | 100% all sets | 8916.1 / 8757.5 | Promising; expand before promotion |
| 22 | 30 m early optical scheduling | 1000 paired + stresses + regressions | 100% all sets | **8353.7** | Current default |
| 23 | Random certified-geometry check | 100 paired | 100% | 8744.9 | Certified fallback |
| 24 | Depth-3 IDA*-inspired route evaluation | random 100 + 300, stresses | directional 99/100 | 8121.9 on random 300 | Not selected: uncertainty exceeds 1% boundary |
| 25 | Increase optical threshold to 40 m | regressions first | seed 257 failed | 8981.5 failed case | Reject |
| 26 | Combine geometry routing with 30 m early optical | random 100 + 300, 2 x 100 stress, regressions | 100% all sets | 8123.0 on random 300 | Keep |
| 27 | Raise fused optical threshold to 35 m | random 100 + 300, 2 x 100 stress, regressions | 100% all sets | **8095.2** on random 300 | Current speed candidate |
| 28 | Raise fused optical threshold to 40 m | random 100 + regressions | 100% | 8100.7 | Reject: mean/P95 worse |
| 29 | Tighten geometry route slack to 60 m | regressions first | seed 3917738334 failed | 10188.1 failed case | Reject |
| 30 | Depth-1 travel-minus-geometry `f` score | regressions first | seed 3917738334 failed | 10188.1 failed case | Reject |
| 31 | Widen geometry route slack to 120 m | random 100 + regressions | 100% | 8038.2 | Reject: slower than 100 m slack |
| 32 | Guard depth-3 `g+h` with a 90% geometry floor | regressions first | seed 3917738334 failed | 10188.1 failed case | Reject |
| 33 | Tighten guarded IDA* floor to 100% | random 100 + 300, stresses, regressions | 100% all sets | 8098.3 on random 300 | Reject: slightly slower overall |
| 34 | Add Or-opt-1 relocation after open 2-opt | random 100 + regressions | 100% | 8046.2 | Reject: mean/wall time worse |
| 35 | Raise replacement radius to 450 m | paired sets + fresh mixed/directional 1000 + regressions | mixed 1000/1000; directional 999/1000 | 8048.6 fresh mixed | Met risk boundary |
| 36 | Raise replacement radius to 550 m | paired sets + fresh mixed/directional 1000 + regressions | mixed 999/1000; directional 998/1000 | **7878.3 fresh mixed** | Current risk-budgeted default |
| 37 | Geometry-aware replacement ranking | paired random 100/300 + regressions | 100/100; 299/300 | 7849.8 paired 300 | Reject: negligible gain, same failure |

### Final local comparisons

| Strategy/config | Seeds/cases | All-clear | Mean (s) | P95 (s) | Max (s) | Mean move (m) | Measures | No-signals |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `opportunistic`, old default | 0--999 / 1000 | 1000/1000 | 10008.44 | 10954.68 | 12002.85 | 35156.84 | 485.66 | 440.05 |
| `integrated_route`, spacing 735 | 0--999 / 1000 | 1000/1000 | 9281.10 | 10190.03 | 11323.76 | 31266.93 | 494.10 | 447.12 |
| `clear_probe`, iteration 10 | 0--999 / 1000 | 1000/1000 | 9135.59 | 10113.22 | 11820.43 | 30669.87 | 495.56 | 448.03 |
| `clear_probe`, holdout* | 1000--1999 / 1000 | 1000/1000 | 9199.39 | 10268.47 | 11438.56 | 30789.40 | 496.36 | 448.15 |
| `clear_probe`, all directional* | 3000--3499 / 500 | 500/500 | 10052.91 | 11149.53 | 12012.90 | 33664.89 | 542.70 | 496.46 |
| `clear_probe`, all omni* | 3000--3499 / 500 | 500/500 | 8257.52 | 8944.06 | 9429.53 | 27609.60 | 445.22 | 394.85 |
| `replacement_aware_clear_probe`, spacing 731 | 0--999 / 1000 | 1000/1000 | **8919.61** | **9911.17** | **10931.00** | **29679.17** | **492.59** | **444.79** |
| `replacement_aware_clear_probe`, holdout | 1000--1999 / 1000 | 1000/1000 | **8905.56** | **9946.97** | 11743.02 | 29616.46 | 492.26 | 444.12 |
| `replacement_aware_clear_probe`, all directional | 3000--3499 / 500 | 500/500 | **9778.72** | **10800.13** | 12102.41 | 32643.96 | 536.85 | 490.38 |
| `replacement_aware_clear_probe`, all omni | 3000--3499 / 500 | 500/500 | **7876.72** | **8604.61** | 9043.11 | 26075.82 | 438.52 | 387.85 |
| `replacement_aware_clear_probe`, OS-entropy random | 1000 unique / 1000 | 1000/1000 | **8909.21** | **9967.15** | 11133.29 | 29712.95 | 489.53 | 440.80 |
| `early_optical_clear_probe`, paired random | same 1000 / 1000 | 1000/1000 | **8353.66** | **9290.72** | 10261.54 | 28040.92 | 452.33 | 413.11 |
| `early_optical_clear_probe`, all directional | paired random / 200 | 200/200 | **9075.41** | **9918.68** | 10515.01 | -- | 497.67 | 459.79 |
| `early_optical_clear_probe`, all omni | paired random / 200 | 200/200 | **7535.33** | **8344.91** | 8650.84 | -- | 408.00 | 367.99 |
| `geometry_early_optical_clear_probe`, 30 m | paired random / 300 | 300/300 | **8123.04** | **9097.49** | 9900.83 | 27916.35 | 417.96 | 379.47 |
| `geometry_early_optical_clear_probe`, 35 m | paired random / 300 | 300/300 | **8095.16** | **9093.64** | 9890.49 | 27924.85 | 412.88 | 376.33 |
| `geometry_early_optical_clear_probe`, 35 m | fresh OS random / 1000 | 1000/1000 | **8133.23** | **8982.90** | 10731.29 | 27973.86 | 417.66 | 381.30 |
| `geometry_early_optical_clear_probe`, 35 m, all directional | paired random / 100 | 100/100 | **8881.02** | -- | -- | -- | 459.07 | 423.68 |
| `geometry_early_optical_clear_probe`, 35 m, all omni | paired random / 100 | 100/100 | **7259.03** | -- | -- | -- | 366.04 | 329.08 |
| `geometry_early_optical_clear_probe`, 35 m, all directional | fresh OS random / 300 | 300/300 | **8833.18** | **9812.92** | 10727.76 | 30328.83 | 455.99 | -- |
| `geometry_early_optical_clear_probe`, 35 m, 550 m replace | fresh OS mixed / 1000 | 999/1000 | **7878.29** | **8836.33** | 9794.08 | 27063.89 | 405.27 | 368.64 |
| `geometry_early_optical_clear_probe`, 35 m, 550 m replace, all directional | fresh OS random / 1000 | 998/1000 | **8674.85** | **9792.46** | 10891.37 | 29756.53 | 448.50 | 413.10 |

`*` The holdout and stress runs predate the final channel-order-only change. Their positions, measurements, and all-clear outcomes remain applicable; their channel-switch/total-time figures do not include the final small switch saving.

Final `clear_probe` seeds 0--999 additionally had mean average localization-clear time 728.83 s, mean no-signal rate 90.14%, mean 47.53 positive directions, mean 459.44 channel switches, mean first clear at 1136.25 s, and mean program wall time 0.052 s/case. The positive-detection rate improved only slightly versus `opportunistic` (about 9.86% versus 9.67%); most of the total improvement came from 12.76% less movement and avoiding route backtracking.

The old iteration-10 seed-42 result, rerun with the receiver-aware order, is 15/15 in 8841.17 s. The current iteration-18 seed-42 smoke cleared 15/15 in 8180.87 s with 435 actions, 28164.35 m movement, 418 measurements, and 362 no-signals. Its in-process log is `experiments/t4_analysis/outputs/iteration18_final_seed42.json`. An independent local HTTP run produced the identical 15/15 and 8180.87 s through 435 accepted actions; its client log is `experiments/t4_analysis/outputs/iteration18_http_seed42.json`.

Three earlier randomized visualization cases used old `opportunistic`, not `clear_probe`: RNG seed 2026091103 selected case seeds 869462, 379913, and 24546. They cleared 38/38 combined in 9185.02, 9594.36, and 9956.30 s. Their SVGs are under `experiments/t4_analysis/outputs/random3/figures/`; do not use them as visual evidence for the current strategy.

## Observed data characteristics

The standalone feature report is based on the old final-1000 `opportunistic` data, so it diagnoses the task but is not a fresh `clear_probe` report.

- Mean/SD total time: 10008.4/672.1 s.
- Movement used 70.25% of time, measurement 24.26%, channel switching 4.84%, and clearing about 0.64%.
- Movement distance versus total-time correlation was 0.856. This explains why route integration outperformed strategies that merely reduced measurement count.
- Mean no-signal rate was 90.33%. High no-signal count is structural because 20 channels are scanned while only 10--16 exist and directional visibility is partial.
- Cases with a high directional-source fraction averaged 592.7 s slower than low-directional cases. The all-directional final stress remains about 1795 s slower than all-omni.
- First-clear time is right-skewed. Opportunistic/integrated clearing fixes the pathological end-loaded behavior seen online but the directional endgame still drives the tail.
- Source count 16 can look structurally easier once all 16 have been found because the known upper bound certifies that no unseen source remains. This must not be generalized to cases with fewer sources.

## Failed approaches and reliability boundary

- `active`/`reacquire` were reliable but their dedicated source detours drove movement to roughly 60--62 km in the first comparison.
- A coarser lattice is not automatically faster. At 900 m, topology and route length made the old 100-case mean 12548.6 s versus 10683.7 s at 760 m.
- Fixed route optimization followed by forced return creates backtracking. Rolling joint routing is the useful part of the TSP idea.
- EIG/particle scoring reduces probes and starts clearing earlier but, without a strong route constraint, extra travel outweighs its information benefit.
- Early stopping produced 4--6% failures; even requiring 11--15 known sources still produced 0.6--4.2% failures. These apparent 9000 s-class results are invalid for the primary objective.
- Clear-site replacement is non-monotonic because removing one point changes later rolling routes. Historical isolated sweeps found failures at 450/550 m and above. Under the later explicit <=1% risk allowance, the fused 550 m strategy was independently 999/1000 mixed and 998/1000 all-directional, with 95% upper bounds below 1%; use 400 m or a certified strategy when zero observed misses matters more than mean time.
- Post-run failure analysis found different mechanisms: seed 918 had no actually visible executed probe for its missed directional source, while skipped lattice probes would have been visible; seed 257 detected its missed channel but lacked enough directional geometry to certify a clear. The final 731/400/2 candidate clears both regression cases.
- Multi-start routing improved the 0--99 mean by 108.20 s. Making the route anticipate successful substitutions improved it by a further 35.70 s at 735 m. Moving to 731 m then lowered the final main-set mean to 8919.61 s.
- Probing active channels at every clear site reduced the 100-case all-directional P95 and maximum, but extra measurements made the combined mixed-set strategy 11.65 s slower than multi-start alone. Residual-channel ordering had no mixed-set effect and only a 10.09 s all-directional mean improvement.
- The six-neighbor certified substitution cleared both regression seeds and 100/100 tuning cases, but its 9277.52 s tuning mean was 73.38 s slower than the same-set old default. It is a reliability fallback, not the fastest configuration.
- Active-bearing route tie-breaking reduced both 100-case mixed means, but the uncertified form failed seed 257 even with route slack swept from 0 to 80 m. Small mean gains do not override a mandatory regression.
- Combining the same tie-break with six-neighbor certified substitution cleared seeds 257/918 and four 100-case batches. Its main/holdout means were 8916.14/8757.53 s and directional/omni means 9659.16/8058.58 s. This is promising but not enough evidence to supersede a default validated over 3000 cases.
- Full POMDP planning was not implemented. A dense five-dimensional belief per channel would be expensive and highly prior-sensitive. The particle implementation is retained as a tested heuristic/ablation, not the default.
- The local mixed-distribution 8000 s target was reached only after accepting the stated risk budget: the current fresh-random-1000 mean is 7878.29 s with one incomplete case. This remains local evidence, not an official score.

## Current recommendation and fallback

Use `geometry_early_optical_clear_probe` locally with exactly:

```text
lattice_spacing = 731 m
replacement_distance_m = 550 m
max_replaced_waypoints = 2
early_clear_radius_m = 35 m
route_length_slack_m = 100 m
```

It is the best evidence-backed local mean-time choice under the approved risk tolerance: its fresh OS-entropy mixed 1000 was 999/1000 at mean/P95 7878.29/8836.33 s, and its fresh all-directional 1000 was 998/1000 at 8674.85/9792.46 s. The corresponding exact one-sided 95% upper bounds on incomplete-case probability are about 0.4735% and 0.6282%. These bounds do not transfer automatically to the hidden official distribution.

For a longer evidence history with less aggressive routing, use `early_optical_clear_probe / 731 / 400 / 2 / 30 m`: it cleared the paired random 1000 and both random 200-case stress sets, with random-1000 mean/P95 8353.66/9290.72 s.

For the strongest tested substitution proof with the better small-sample mean, expand `certified_geometry_clear_probe / 735` first: its local six-neighbor triangle fan preserves the 1000 m half-plane discovery argument for each removed interior vertex, and it cleared both regressions plus four 100-case batches. Its evidence is still too small for promotion. `certified_clear_probe` is the simpler proof ablation (9277.52 s over 100 tuning cases). For the simplest conservative fallback, use `integrated_route` at 735 m with no coverage-point replacement; it was 1000/1000 locally at mean 9281.10 s and retains the unmodified lattice argument.

## Known limitations and risks

- Official generation distributions are hidden. Local count, type, position, radius, direction, and error distributions are explicit assumptions, not official facts.
- The local evaluator omits peripheral official behavior including concurrent-new-action 409 handling, 429 throttling, the GUI's wall-clock orchestration, and socket closure after GUI termination.
- The local error is a deterministic hash into [-1,1] degrees to reproduce fixed same-location error. Its spatial correlation may differ from the official environment.
- `replacement_aware_clear_probe` has no proof after its empirical 400 m replacement. Zero failures over the tested seed sets does not eliminate adversarial geometric holes; route awareness does not change that evidence boundary.
- The current 550 m fused default deliberately spends the accepted risk budget: observed local failures remain regression evidence, not bugs to omit from reporting.
- `no_signal` remains ambiguous. Belief updates can eliminate only hypotheses that would necessarily have been visible; they cannot prove channel absence without coverage/count logic.
- Neither optimized early-optical strategy has been tested online. Official server semantics, distribution mismatch, or route edge cases may change performance.
- Existing randomized path figures show the former strategy. Generate new `clear_probe` figures before using a path diagram in the paper.
- The current local optimizer is fast, but the official test has a real-time limit and network retries; always respect `remaining_real_duration_s` and retain logs.

## Important local-simulator assumptions

Emitter count is discrete uniform 10--16; channels are sampled without replacement; positions are area-uniform in the 1800 m disk; radii are uniform 1000--1500 m; source type is Bernoulli with configurable directional probability; directions are uniform; bearing error is a deterministic location/source hash mapped to [-1,1] degrees. These distributions are for controlled A/B testing only.

## Next recommended optimization work

1. Do not run another official action-producing command without fresh explicit user authorization. The 2026-09-12 run was individually authorized; that permission does not carry forward. Preserve both client and evaluator logs.
2. Re-run random path visualizations with the current `geometry_early_optical_clear_probe`; the current figures show old `opportunistic` and are stale.
3. Use saved OS-entropy manifests for paired A/B comparisons, then require fresh OS-entropy large batches for promotion. Prefer zero failures; if accepting a nonzero rate, require an estimated incomplete-case probability no greater than 1%, report uncertainty, and rerun both stress sets after any geometry/order change.
4. Expand `certified_geometry_clear_probe / 735` to the full 1000 + 1000 + 500 + 500 protocol before considering promotion; then extend the certificate beyond the current single-clear six-neighbor fan if it remains competitive.
5. Reduce multi-start compute without changing its selected first node, or add a route-aware bounded lookahead that directly prices measurement and replacement effects. Validate virtual movement and real wall time.
6. Analyze the all-directional maximum separately: iteration 18 improved its mean/P95 but increased the observed maximum from 12012.90 to 12102.41 s.
7. Keep seeds 257, 918, and all-directional 3917738334 as mandatory regressions. The latter rejects the IDA*-inspired route evaluator.
8. The fresh mixed mean is now 7878.29 s under the <=1% risk boundary. Further work should reduce replacement-induced directional holes without giving back the sub-8000 mean; do not use an early-stop shortcut.

## Exact reproduction commands

From repository root:

```bash
python3 -m unittest discover -s task4/tests -v
python3 -m task4.cli run --mode local --strategy geometry_early_optical_clear_probe --seed 42 --lattice-spacing 731 --early-clear-radius 35 --route-length-slack 100 --output task4/outputs/seed42.json
python3 -m task4.cli batch --strategy clear_probe --seed-start 0 --cases 1000 --output-dir experiments/t4_analysis/outputs/final_optimized1000/clear_probe_final
python3 -m task4.cli batch --strategy integrated_route --seed-start 0 --cases 1000 --lattice-spacing 735 --output-dir experiments/t4_analysis/outputs/final_optimized1000/integrated735
python3 -m task4.cli batch --strategy clear_probe --seed-start 1000 --cases 1000 --output-dir experiments/t4_analysis/outputs/final_optimized_holdout1000/probe400_rerun
python3 -m task4.cli batch --strategy clear_probe --seed-start 3000 --cases 500 --directional-probability 1 --output-dir experiments/t4_analysis/outputs/final_optimized_stress/probe400_dir_rerun
python3 -m task4.cli batch --strategy clear_probe --seed-start 3000 --cases 500 --directional-probability 0 --output-dir experiments/t4_analysis/outputs/final_optimized_stress/probe400_omni_rerun
python3 -m task4.cli batch --strategy replacement_aware_clear_probe --seed-start 0 --cases 1000 --lattice-spacing 731 --output-dir experiments/t4_analysis/outputs/iteration18_final1000/replacement_aware_s731
python3 -m task4.cli batch --strategy replacement_aware_clear_probe --seed-start 1000 --cases 1000 --lattice-spacing 731 --output-dir experiments/t4_analysis/outputs/iteration18_holdout1000/replacement_aware_s731
python3 -m task4.cli batch --strategy replacement_aware_clear_probe --seed-start 3000 --cases 500 --directional-probability 1 --lattice-spacing 731 --output-dir experiments/t4_analysis/outputs/iteration18_stress500/replacement_aware_s731_dir
python3 -m task4.cli batch --strategy replacement_aware_clear_probe --seed-start 3000 --cases 500 --directional-probability 0 --lattice-spacing 731 --output-dir experiments/t4_analysis/outputs/iteration18_stress500/replacement_aware_s731_omni
python3 -m experiments.t4_analysis.random_benchmark --cases 1000 --strategy replacement_aware_clear_probe --lattice-spacing 731 --replacement-distance 400 --max-replaced-waypoints 2 --output-dir experiments/t4_analysis/outputs/random_large_1000_replacement_aware
python3 -m experiments.t4_analysis.analyze_action_log task4/outputs/official/YJVS-K983-5KCS-NAX5.json --output-dir experiments/t4_analysis/outputs
python3 -m experiments.t4_local.server --seed 42 --port 2027
python3 -m task4.cli config-check --server http://172.26.112.1:2027 --robot-id 202609001035
```

The remote command is intentionally distinct and additionally requires `--mode remote`, `--server`, `--output`, and:

```text
--confirm-remote I_UNDERSTAND_THIS_USES_AN_OFFICIAL_TEST
```

The last supplied official configuration was endpoint `http://172.26.112.1:2027`, team ID `202609001035`, and GUI case code `YJVS-K983-5KCS-NAX5`. The case code is selected in the official GUI and is not sent by this CLI. For reference only, the corresponding **formal action-producing command** is:

```bash
python3 -m task4.cli run --mode remote --strategy early_optical_clear_probe \
  --server http://172.26.112.1:2027 --robot-id 202609001035 \
  --confirm-remote I_UNDERSTAND_THIS_USES_AN_OFFICIAL_TEST \
  --output task4/outputs/official/early-optical-YJVS-K983-5KCS-NAX5.json
```

Do not execute that command as a connectivity check: it calls `/enter` and consumes the active test. Use `config-check` first, then manually confirm the GUI and countdown.

## New-session startup checklist

1. Read `problem/B题/B题.md`, both attachment documents, `task4/README.md`, this file, and `experiments/t4_analysis/outputs/iterations/ITERATION_REPORT.md` before changing rules or claims.
2. Run `git status --short`; the current work may still be untracked and belongs to the user/team.
3. Run the full test suite, then reproduce seeds 257, 918, 3917738334, and the current 550 m failure cases before changing replacement logic.
4. Inspect actual persisted summaries before quoting numbers. Label local and official evidence separately.
5. Keep production changes in `task4/`, simulator changes in `experiments/t4_local/`, and analysis-only programs in `experiments/t4_analysis/`.
6. For every optimization: state a hypothesis, implement one controlled change, compare identical seeds, inspect failures/tails, and update both README and HANDOFF with actual—not planned—results.
