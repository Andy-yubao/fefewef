# T4 strategy optimization iterations

All figures are actual local-simulator results. Tuning comparisons use shared seeds; configurations with any observed missed emitter are not recommended.

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
| 10 | Receiver-channel-aware alternating scan order | 1000 | 100% | **9135.6** | **10113.2** | Current best/default |

## Reliability boundary of coverage-point replacement

- 400 m: 1000/1000 tuning and 1000/1000 disjoint holdout all clear.
- 450 m: 999/1000 all clear (failure seed 257).
- 500 m: 1000/1000 all clear, but it lies between settings with observed failures and is not selected conservatively.
- 550 m: 999/1000 all clear (failure seed 918).
- 600--675 m: each had 499/500 all clear.
- 700--750 m: 497/500 all clear.
- 800 m: 199/200 with two replacements; 198/200 with three replacements.

The non-monotonic failures occur because one removed waypoint changes the subsequent rolling route. The 400 m choice is an empirical reliability setting, not a new deterministic coverage proof.

## Final evidence

Final `clear_probe` parameters: lattice spacing 735 m, replacement distance 400 m, at most two replaced waypoints, receiver-aware channel order.

- Seeds 0--999: 1000/1000 all clear; mean 9135.59 s; P95 10113.22 s; max 11820.43 s; mean movement 30669.87 m; mean 495.56 measurements; mean 448.03 no-signals.
- Disjoint seeds 1000--1999 before the channel-order-only change: 1000/1000 all clear; mean 9199.36 s. The final channel ordering changes only switch time, not positions or detection outcomes.
- 500 all-directional cases: 500/500 all clear; mean 10052.9 s.
- 500 all-omnidirectional cases: 500/500 all clear; mean 8257.5 s.
- Seed 42 final local smoke test: 15/15 cleared; 8876.17 s.

Relative to `opportunistic`, final mean time improved by 8.72%, P95 by 7.68%, and movement by 12.76%. Relative to the older `deferred`, mean time improved by 23.48%.

## Why 8000 s was not claimed

Safe full coverage has a substantial route-length floor and absent channels still require repeated negative measurements. Aggressive early stopping and large clear-site replacement move toward 8000--8900 s but produced missed emitters. The project therefore reports 9135.6 s as the current evidence-backed mean instead of selecting a faster unreliable configuration.
