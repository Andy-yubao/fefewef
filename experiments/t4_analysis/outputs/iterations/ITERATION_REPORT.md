# T4 strategy optimization iterations

All figures are actual local-simulator results. Tuning comparisons use shared seeds. Zero misses remain preferred; under the current user-approved risk boundary, a candidate may be considered only when its estimated incomplete-case probability is no greater than 1%, with misses and sampling uncertainty reported explicitly.

| Iteration | Hypothesis / implementation | Cases | All-clear | Mean time (s) | P95 (s) | Decision |
|---|---|---:|---:|---:|---:|---|
| Reference | `opportunistic`, 760 m lattice, clear threshold 1500 m | 1000 | 100% | 10008.4 | 10954.7 | Old best |
| 1 | Fixed open 2-opt route with forced rejoin | 100 | 100% | 10305.8 | 11364.7 | Rejected: rejoin creates detours |
| 2 | EIG limited to nearby/equidistant waypoints | 100 | 100% | 10060.8--10076.2 | 10938.4--11085.3 | Rejected: saved probes but added movement |
| 3 | Price clear against best post-clear re-entry | 100 | 100% | 10077.3 | 10924.8 | Kept as experiment; mean worse |
| 4 | Early stop after discovery drought | 200 | 94--96% | 9084.6--9313.7 | 11089.4 | Rejected: false speed from missed emitters |
| 5 | Early stop only after 11--15 known sources | 500 | 95.8--99.4% | 9424.8--9922.6 | 10923.1--11006.7 | Rejected: still missed emitters |
| 6 | Joint rolling open-TSP over coverage and clear targets | 100 | 100% | 9544.8 | 10471.7 | Successful |
| 7 | Retune joint-route lattice to 735 m | 100 | 100% | 9345.3 | 10094.9 | Successful |
| 8 | Probe unresolved channels at clear sites and replace nearby grid points | 100--1000 | varies | 8941.7--9333.0 | varies | Reliability boundary studied |
| 9 | Conservative 400 m replacement, max two points | 1000 + 1000 holdout | 100% + 100% | 9170.4 / 9199.4 | 10148.2 / 10268.5 | New reliable candidate |
| 10 | Receiver-channel-aware alternating scan order | 1000 | 100% | 9135.6 | 10113.2 | Former best/default |
| 11 | Multi-start rolling open 2-opt, no forced rejoin | 100 | 100% | 9095.9 | 9992.0 | Keep route component |
| 12 | Six-neighbor coverage-certified clear-site substitution | 100 + regressions | 100% | 9277.5 | 10343.6 | Proven fallback; slower |
| 13 | Probe active channels at every clear site | 100 + 100 directional | 100% | 9185.1 | 10087.6 | Tail help, mean nearly flat |
| 14 | Nearest-candidate ordering of residual active channels | 100 + 100 directional | 100% | 9204.1 | 10220.5 | No mixed-set effect |
| 15 | Combine multi-start, active clear probes, and endgame order | 100 | 100% | 9107.6 | 10077.5 | Extra measurements erase movement saving |
| 16 | Make joint route aware of future 400 m / two-point substitutions | 100 | 100% | 9060.2 | 9954.7 | Keep |
| 17 | Sweep missed 37-point topology interval, 730.5--735 m | 100 + 100 holdout | 100% | 9139.8 at 731 m | 9947.0 | Select 731 m |
| 18 | Replacement-aware route at 731 m | 1000 + 1000 + 500 + 500 | 100% all sets | **8919.6 / 8905.6** | **9911.2 / 9947.0** | New local recommendation |
| 19 | Break near-equal route ties with active-bearing geometry | 100 + 100 holdout + stresses | 100% batches, but seed 257 failed | 8723.6 / 8614.8 | 9817.1 / 9498.1 | Rejected: regression failure |
| 20 | Sweep geometry-route slack from 0 to 80 m | seed 257 x 5 | 0/5 all-clear | 8174.1 | -- | Rejected: equal-length tie still loses geometry |
| 21 | Combine geometry route ordering with six-neighbor certified substitution | 100 + 100 holdout + 100 + 100 stress + regressions | 100% all sets | 8916.1 / 8757.5 | 9774.9 / 9569.5 | Promising certified candidate; expand before promotion |
| 22 | Schedule optical clears at 30 m feasible-radius instead of 19.5 m | 100 paired + 1000 paired + 200 + 200 stress + regressions | 100% all sets | **8353.7** random 1000 | **9290.7** | New local recommendation |
| 23 | Random validation of `certified_geometry_clear_probe / 735` | 100 paired random | 100% | 8744.9 | 9542.4 | Certified fallback; only 0.89% faster than baseline |
| 24 | IDA*-inspired depth-3 `g+h` route score on top of iteration 22 | 100 + 300 random, 100 + 100 stress, regressions | mixed/omni passed; directional 99/100 | 8121.9 on random 300 | 9003.3 | Not selected: point miss rate is 1%, uncertainty exceeds boundary |
| 25 | Increase early optical radius from 30 to 40 m | regressions first | seed 257 failed 11/12 | 8981.5 on failed case | -- | Rejected before random batch |
| 26 | Combine geometry route ordering with 30 m early optical | random 100 + 300, 2 x 100 stress, regressions | 100% all sets | 8123.0 on random 300 | 9097.5 | Keep |
| 27 | Raise fused early optical radius to 35 m | random 100 + 300, 2 x 100 stress, regressions | 100% all sets | **8095.2** on random 300 | **9093.6** | Current speed candidate |
| 28 | Raise fused early optical radius to 40 m | random 100 + regressions | 100% | 8100.7 | 9179.5 | Rejected: mean and tail worse |
| 29 | Tighten fused geometry slack from 100 to 60 m | regressions first | seed 3917738334 failed 14/15 | 10188.1 on failed case | -- | Rejected |
| 30 | Replace lexicographic geometry choice with depth-1 `g+h` score | regressions first | seed 3917738334 failed 14/15 | 10188.1 on failed case | -- | Rejected |
| 31 | Widen fused geometry slack from 100 to 120 m | random 100 + regressions | 100% | 8038.2 | 9043.9 | Rejected: slower than 100 m slack |
| 32 | Depth-3 `g+h` behind a 90% first-step geometry gate | regressions first | seed 3917738334 failed 14/15 | 10188.1 on failed case | -- | Rejected |
| 33 | Tighten guarded IDA* geometry gate to 100% | random 100 + 300, 2 x 100 stress, regressions | 100% all sets | 8098.3 on random 300 | -- | Rejected: 3.14 s slower than iteration 27 |
| 34 | Or-opt-1 relocation after each open 2-opt candidate | random 100 + regressions | 100% | 8046.2 | 8970.0 | Rejected: mean and wall time worse |
| 35 | Increase fused replacement radius from 400 to 450 m | paired sets + fresh mixed 1000 + directional 1000 + regressions | mixed 1000/1000; directional 999/1000 | 8048.6 on fresh mixed 1000 | 9095.9 | Promoted temporarily under the <=1% risk boundary |
| 36 | Increase fused replacement radius from 450 to 550 m | paired 100/300 + stresses, fresh mixed/directional 1000, regressions | mixed 999/1000; directional 998/1000 | **7878.3** on fresh mixed 1000 | **8836.3** | New risk-budgeted local default; mixed mean below 8000 s |
| 37 | Prefer replacing probes with low active-bearing geometry value | paired random 100/300 + eight regressions | random 100/100; 299/300 | 7849.8 on paired random 300 | 8818.4 | Rejected: only 2.67 s mean gain and same batch failure |

## Reliability boundary of coverage-point replacement

- 400 m: 1000/1000 tuning and 1000/1000 disjoint holdout all clear.
- 450 m: 999/1000 all clear (failure seed 257).
- 500 m: 1000/1000 all clear, but it lies between settings with observed failures and is not selected conservatively.
- 550 m: 999/1000 all clear (failure seed 918).
- 600--675 m: each had 499/500 all clear.
- 700--750 m: 497/500 all clear.
- 800 m: 199/200 with two replacements; 198/200 with three replacements.

The non-monotonic failures occur because one removed waypoint changes the subsequent rolling route. The 400 m choice is an empirical reliability setting, not a new deterministic coverage proof.

## Prior iteration-10 evidence

Final `clear_probe` parameters: lattice spacing 735 m, replacement distance 400 m, at most two replaced waypoints, receiver-aware channel order.

- Seeds 0--999: 1000/1000 all clear; mean 9135.59 s; P95 10113.22 s; max 11820.43 s; mean movement 30669.87 m; mean 495.56 measurements; mean 448.03 no-signals.
- Disjoint seeds 1000--1999 before the channel-order-only change: 1000/1000 all clear; mean 9199.36 s. The final channel ordering changes only switch time, not positions or detection outcomes.
- 500 all-directional cases: 500/500 all clear; mean 10052.9 s.
- 500 all-omnidirectional cases: 500/500 all clear; mean 8257.5 s.
- Seed 42 before the channel-order change was 8876.17 s; the receiver-aware iteration-10 rerun is 8841.17 s. The iteration-18 candidate is 8180.87 s.

Relative to `opportunistic`, final mean time improved by 8.72%, P95 by 7.68%, and movement by 12.76%. Relative to the older `deferred`, mean time improved by 23.48%.

## Iterations 11--18: replacement-aware rolling route

Post-run analysis of the known aggressive-replacement failures separated two mechanisms. At seed 918, the missed directional channel had no visible executed measurement point, while two skipped lattice points would have been visible. At seed 257, the missed channel was detected but the remaining directional observations did not shrink its feasible region enough for clearing. The diagnostic is reproducible with `experiments/t4_analysis/analyze_coverage_failure.py`; it reads local truth only after a run and is never imported by a strategy.

`certified_clear_probe` implements the conservative geometry branch. A lattice vertex is removed only when the clear probe and all six retained lattice neighbors form a fan of triangles whose edges are strictly below the 1000 m minimum receive radius; the six neighbors are then protected from later removal. It cleared seeds 257 and 918 and 100/100 tuning cases. Its tuning mean was 9277.52 s, 73.38 s slower than the same-set 735/400/2 baseline, so it is retained as a proof-oriented fallback rather than the fastest recommendation.

The successful efficiency branch has two parts. Multi-start open 2-opt reduced the 0--99 mean from 9204.14 to 9095.94 s. Making the planner remove the lattice nodes that a pending successful clear is expected to substitute reduced it further to 9060.24 s. A narrow sweep then found that 731 m is the first tested spacing above the topology transition from 43 to 37 lattice points and outperformed 735 m on both seeds 0--99 and the disjoint 1000--1099 subset. Combining replacement-aware planning with 731 m produced 8987.55 s on the tuning 100 and 8895.61 s on the small holdout 100.

Final actual evidence for `replacement_aware_clear_probe / 731 / 400 / 2`:

- Seeds 0--999: 1000/1000 all clear; mean 8919.61 s; P95 9911.17 s; max 10931.00 s; mean movement 29679.17 m; mean 492.59 measurements; mean wall time 0.580 s/case.
- Seeds 1000--1999: 1000/1000 all clear; mean 8905.56 s; P95 9946.97 s; max 11743.02 s.
- Seeds 3000--3499, all directional: 500/500 all clear; mean 9778.72 s; P95 10800.13 s; max 12102.41 s.
- Seeds 3000--3499, all omni: 500/500 all clear; mean 7876.72 s; P95 8604.61 s; max 9043.11 s.
- Regression seeds with the final candidate: seed 257 cleared 12/12 in 8829.27 s; seed 918 cleared 16/16 in 8653.12 s.
- Seed 42 smoke: 15/15 cleared in 8180.87 s.
- Independent local HTTP seed 42: identical 15/15 and 8180.87 s through 435 accepted actions.

Against the former final `clear_probe / 735 / 400 / 2` main-set result, the new main-set mean is 215.98 s (2.36%) lower and P95 is 202.05 s (2.00%) lower. The replacement rule itself remains empirical: route awareness and 731 m spacing do not turn 400 m substitution into a deterministic coverage proof.

## Iterations 19--21: active geometry with and without a certificate

`geometry_aware_clear_probe` keeps routes within 100 m of the shortest multi-start open route, then prefers a first node whose robot-visible bearing geometry is most nearly transverse to active channels. It never reads simulator truth. At 731 m it cleared all four 100-case batches and reduced their mixed means to 8723.56 s (seeds 0--99) and 8614.81 s (1000--1099); the all-directional/all-omni means were 9560.75/7756.70 s. This apparent improvement is invalid as a recommendation because the mandatory seed-257 regression cleared only 11/12. Slack values 0, 20, 40, 60, and 80 m all reproduced the same miss: an exact-length route tie was sufficient to change observation geometry.

`certified_geometry_clear_probe` applies the same active-bearing route tie-break only to `certified_clear_probe`; it may delete a coverage vertex only under the six-neighbor triangular-fan certificate. Actual evidence at 735 m is:

- Seeds 0--99: 100/100 all clear; mean 8916.14 s; P95 9774.94 s; max 10760.72 s.
- Seeds 1000--1099: 100/100 all clear; mean 8757.53 s; P95 9569.47 s; max 9817.67 s.
- Seeds 3000--3099, all directional: 100/100 all clear; mean 9659.16 s; P95 10745.40 s; max 11160.62 s.
- Seeds 3000--3099, all omni: 100/100 all clear; mean 8058.58 s; P95 8608.85 s; max 8938.37 s.
- Seed 257: 12/12 in 8111.27 s; seed 918: 16/16 in 8434.44 s.

The certified candidate beats `replacement_aware_clear_probe / 731` on both tested 100-case mixed subsets, but it has only 400 batch cases versus 3000 for the current default and is slower on the tested all-omni subset. It is therefore retained as the next proof-oriented candidate to expand, not promoted on tuning-scale evidence.

## Iterations 22--25: early optical clearing and bounded heuristic search

Iteration 22 changes only the localization-to-clear threshold. `early_optical_clear_probe` schedules the feasible-region center as a clear target at radius 30 m rather than waiting for 19.5 m. A failed optical attempt costs 3 s and is recorded; the same channel is not rescheduled until its estimated center moves at least 5 m. Coverage, replacement, route generation, and channel ordering are inherited unchanged from `replacement_aware_clear_probe`.

On the same 1000 seeds previously sampled from operating-system entropy, the baseline and candidate were both 1000/1000 all clear. Mean time fell from 8909.21 to 8353.66 s (-6.24%), P95 from 9967.15 to 9290.72 s, and maximum from 11133.29 to 10261.54 s. Mean movement fell from 29712.95 to 28040.92 m and measurements from 489.53 to 452.33; optical attempts rose only from 13.081 to 13.531. Paired random stress results were also all clear: all-directional 200-case mean 9792.67 -> 9075.41 s, and all-omni 7882.99 -> 7535.33 s. Seeds 257 and 918 passed. This is the new evidence-backed local recommendation.

Iteration 23 independently tested the existing coverage-certified candidate on a new paired random 100. `certified_geometry_clear_probe / 735` cleared 100/100 and improved the original baseline mean only from 8823.44 to 8744.85 s. It remains useful when the six-neighbor replacement certificate matters, but is slower than 30 m early optical on the same cases (8309.65 s).

Iteration 24 adds one mechanism on top of iteration 22: an IDA*-inspired depth-3 rolling evaluation. Its `g+h` term is deterministic route/action cost; a bounded discounted credit values robot-visible active-bearing crossing geometry over the next three measurement-capable nodes. It cleared random batches of 100 and 300 with means 8067.46 and 8121.88 s. However, the all-directional random 100 missed one emitter at seed 3917738334. Post-run analysis found that both lattice points actually visible to the missed directional channel had been skipped by empirical clear-site replacement. The iteration-22 baseline cleared the same all-directional case 15/15 in 8340.49 s. The heuristic route is rejected and seed 3917738334 is now mandatory regression evidence.

Iteration 25 changed only the early optical threshold from 30 to 40 m under the same heuristic. It immediately failed seed 257 (11/12); post-run analysis again found a visible skipped lattice point. The random batch was stopped, and 30 m remains the accepted threshold.

## Iterations 26--31: geometry/early-optical fusion and single-factor follow-ups

Iteration 26 directly combines the current early-optical strategy with the robot-visible active-bearing route tie-break. `geometry_early_optical_clear_probe / 731 / 400 / 2 / 30 m / 100 m slack` cleared paired random batches of 100 and 300 at means 8041.52 and 8123.04 s. It also cleared paired all-directional and all-omni sets of 100 each at means 8939.45 and 7348.36 s, and passed seeds 257, 918, and all-directional 3917738334. This demonstrates that the earlier geometry failure was not intrinsic to the geometry score: the 30 m early optical actions change the rolling route and replacement sequence.

Iteration 27 changed only the optical scheduling radius from 30 to 35 m. It cleared the paired random 100 and 300 at means 8027.42 and 8095.16 s, with random-300 P95/maximum 9093.64/9890.49 s. The paired all-directional and all-omni 100-case means were 8881.02 and 7259.03 s, again with zero failures, and all three regressions passed. A fresh OS-entropy mixed 1000 was 1000/1000 all-clear at minimum/mean/median/P95/P99/maximum 4299.72/8133.23/8186.92/8982.90/9498.41/10731.29 s. A separate fresh all-directional 300 was 300/300 at 6552.27/8833.18/8799.38/9812.92/10727.76 s for minimum/mean/median/P95/maximum. The zero-failure one-sided 95% binomial upper bounds are about 0.299% and 0.994%, respectively, only for the stated local distributions. This promoted 35 m/100 m slack to the local default.

Iterations 28--31 each changed one factor. A 40 m radius passed the three regressions and random 100, but worsened mean/P95 to 8100.66/9179.47 s. Tightening the route slack to 60 m failed all-directional seed 3917738334 at 14/15; post-run local-truth analysis showed that two of four replaced lattice points would have been visible to missed directional channel 5. A depth-1 travel-time-minus-geometry score selected the same failing path, showing that a finite geometry credit underprices discovery coverage in this case. Widening slack to 120 m passed the regressions and random 100 but averaged 8038.20 s versus 8027.42 s at 100 m. Thus 35 m/100 m slack remains the candidate. Under the user's revised tolerance, an observed miss probability no greater than 1% may be accepted, but every result continues to report both all-clear case rate and aggregate source clear rate; no failed configuration is hidden by its lower time.

## Iterations 32--37: guarded IDA*, stronger route search, and risk-budgeted replacement

Iteration 32 fused depth-3 `g+h` with the current geometry route by admitting only routes whose first-step geometry was at least 90% of the best eligible value. It still selected the known failing path at all-directional seed 3917738334 and cleared 14/15, so the batch was stopped. Iteration 33 tightened the gate to exactly 100%: all three regressions and random 100/300 plus directional/omni 100 passed. Its random-300 mean was 8098.30 s versus 8095.16 s for iteration 27; directional 100 improved from 8881.02 to 8851.03 s while omni worsened from 7259.03 to 7262.12 s. The reliable fusion exists, but its overall mean did not improve.

Iteration 34 added deterministic Or-opt-1 single-node relocation after every multi-start open 2-opt candidate. It passed the regressions and random 100 but averaged 8046.19 s versus 8027.42 s, and wall time rose from about 0.95 to 1.45 s/case. A shorter static open route can change clear-site substitution timing and lengthen the full rolling trajectory, so the architecture was rejected.

Iteration 35 changes only the replacement radius from 400 to 450 m under the iteration-27 strategy. It passed all three regressions, paired random 100/300, and paired directional/omni 100. Random-100 mean crossed below 8000 at 7968.66 s, but random-300 mean was 8042.76 s; directional/omni means were 8811.27/7188.03 s. A fresh OS-entropy mixed 1000 was 1000/1000 all-clear at minimum/mean/median/P95/P99/maximum 4253.17/8048.58/8053.42/9095.86/9617.29/10428.54 s. The first fresh all-directional 300 had one incomplete case, seed 639107002; 700 additional fresh cases were all clear. Combined directional evidence was therefore 999/1000 with case failure 0.1%, source clear rate 99.9922%, mean 8833.46 s, and P95 9831.36 s. Its exact one-sided 95% failure-rate upper bound is about 0.4735%, so 450 m met the approved risk boundary.

Iteration 36 changes only the replacement radius from 450 to 550 m. It passed paired random 100 at 7821.07 s mean, directional/omni 100 at 8794.30/6956.57 s, and paired random 300 at 7852.46 s; the latter missed one case, seed 3880268419. Fresh OS-entropy mixed 1000 was 999/1000 at minimum/mean/median/P95/P99/maximum 5252.97/7878.29/7910.04/8836.33/9343.67/9794.08 s, with source clear rate 99.9923%. Fresh all-directional 1000 was 998/1000 at 6302.65/8674.85/8642.54/9792.46/10302.60/10891.37 s and source clear rate 99.9846%. Exact one-sided 95% case-failure upper bounds are 0.4735% and 0.6282%, respectively, both below 1%. This is the first large fresh mixed batch below 8000 s and promotes 550 m as the risk-budgeted local default. Post-run diagnosis of seed 3880268419 found a detected-but-not-localized directional channel, two visible executed probes, and two additional visible lattice probes among seven replacements; no truth was exposed to the live policy.

Iteration 37 changes only which eligible probes are replaced: among points within 550 m it protects high active-bearing geometry value and removes low-value points first. It repaired some known failures, including seed 639107002, but not seeds 3880268419 and 289203195. On the same random 100 and 300 manifests as iteration 36 it obtained 7808.72 and 7849.79 s mean; the 300-case gain was only 2.67 s and both strategies failed the same one case. The extra architecture is retained as an ablation, not promoted.

## Non-fixed random validation of the current default

`experiments/t4_analysis/random_benchmark.py` selects unique 32-bit seeds from operating-system entropy without a preset RNG seed and writes the full manifest before execution. The original `replacement_aware_clear_probe / 731 / 400 / 2` run cleared 1000/1000 at minimum/mean/median/P95/P99/maximum 5527.82/8909.21/8908.40/9967.15/10467.40/11133.29 s. The iteration-27 400 m fusion cleared a fresh 1000/1000 at 4299.72/8133.23/8186.92/8982.90/9498.41/10731.29 s. The current iteration-36 550 m setting cleared 999/1000 fresh mixed cases at 5252.97/7878.29/7910.04/8836.33/9343.67/9794.08 s. Artifacts are under `experiments/t4_analysis/outputs/random_large_1000_replacement_aware/`, `iterations/iteration27_geometry_early_optical35/random1000_fresh/`, and `iterations/iteration36_geometry35_replace550/random1000_fresh/`.

## Scope of the mixed-distribution sub-8000 s result

Iteration 36 lowered a fresh OS-entropy mixed 1000 mean to 7878.29 s, so the local mixed-distribution target is reached under the explicitly accepted <=1% incomplete-case risk. This is not a zero-miss result: one case was incomplete and the exact one-sided 95% failure-rate upper bound is 0.4735%. It is evidence only for the recorded local generator, not an official score or a guarantee for the hidden official distribution.
