# Candidate 020 Scheduler Decision Audit

## Cases

- Seeds: `321100`, `321101`, `321106`
- Policy: `candidate_020_grid5_center_approach`
- Fixed source count: 16; workers: 1
- Planner seed: `321100`, matching the original paired run
- Audit artifact: `task3/results/raw/optimization/020_scheduler_decision_audit.jsonl.gz`
- Reproduction entry point: `task3.experiments.run_offline.run_case((seed, 321100, 20.0, True, 16, ["candidate_020_grid5_center_approach"]))`

## SEARCH vs nearby local actions

| seed | Scheduler decisions | SEARCH | SEARCH with LOCALIZE/CLEAR available | nearby LOCALIZE (<500 m) | nearby CLEAR (<500 m) | `coverage_forced` |
|---:|---:|---:|---:|---:|---:|---:|
| 321100 | 47 | 6 | 6 | 4 | 0 | 0 |
| 321101 | 79 | 6 | 6 | 3 | 0 | 0 |
| 321106 | 65 | 6 | 6 | 5 | 1 | 0 |
| **Total** | **191** | **18** | **18** | **12** | **1** | **0** |

All 12 nearby LOCALIZE candidates were closer than the next coverage point, but SEARCH still had the lower score. The LOCALIZE-minus-SEARCH score gap ranged from 0.672 s to 128.452 s (median 27.873 s). The single nearby CLEAR candidate was 385.1 m away while the next coverage point was 1063.1 m away; SEARCH still scored 134.746 s lower.

No SEARCH decision with `found_count > 0` lacked both a LOCALIZE and a CLEAR candidate in these cases.

## Representative decisions

`score gap` is best-local-action score minus SEARCH score, so a positive value means the scheduler favors SEARCH.

| seed / decision | current position (m) | coverage distance / score | best LOCALIZE channel / distance / score | best CLEAR channel / distance / score | score gap (s) | chosen |
|---|---|---|---|---|---:|---|
| 321100 / 6 | (-1122.0, -255.9) | 468.1 / 1342.0 | 16 / 18.3 / 1342.7 | 9 / 2177.2 / 2129.4 | 0.7 | SEARCH |
| 321100 / 2 | (712.9, -239.3) | 469.9 / 2825.0 | 9 / 242.6 / 2850.0 | — | 25.0 | SEARCH |
| 321100 / 9 | (-410.4, 1127.6) | 1200.0 / 731.2 | 10 / 255.8 / 737.7 | 5 / 1137.7 / 945.8 | 6.5 | SEARCH |
| 321101 / 6 | (-496.2, 1118.8) | 502.7 / 1409.4 | 11 / 376.7 / 1537.9 | — | 128.5 | SEARCH |
| 321101 / 4 | (-1039.2, -600.0) | 1200.0 / 1824.8 | 9 / 434.9 / 1833.8 | — | 9.0 | SEARCH |
| 321101 / 2 | (1039.2, -600.0) | 1200.0 / 2822.4 | 17 / 464.6 / 2853.2 | — | 30.8 | SEARCH |
| 321106 / 4 | (627.5, 897.5) | 1063.1 / 2783.7 | 7 / 147.7 / 2795.9 | 12 / 385.1 / 2918.4 | 12.2 / 134.7 | SEARCH |
| 321106 / 6 | (-1181.8, 208.4) | 1200.0 / 1588.5 | 15 / 256.1 / 1595.0 | 12 / 2030.4 / 2189.1 | 6.5 | SEARCH |
| 321106 / 5 | (-410.4, 1127.6) | 1200.0 / 2108.2 | 9 / 307.8 / 2163.4 | 12 / 1351.7 / 2544.7 | 55.2 | SEARCH |

## Main pattern

The evidence supports **A: the score systematically favors coverage**, not B or C.

Candidate generation is working at the relevant decisions: every SEARCH decision had a LOCALIZE or CLEAR alternative, and 12 had a LOCALIZE alternative within 500 m. These targets were already FOUND, so missing opportunistic detection does not explain the observed deferral.

The asymmetry is in the finite-horizon proxy. A LOCALIZE/CLEAR action pays its immediate movement and then the remaining coverage route from the local point. SEARCH completes the coverage route first and adds `_found_cost(found)` as a position-independent tail. That tail estimates localization/clearing work but does not explicitly charge the spatial return from the later coverage endpoint to deferred FOUND sources. Consequently, even a much closer local action can score slightly or substantially worse than coverage.

## Behavior preservation

| seed | virtual time before / after (s) | cleared | termination | action count before / after | action signature |
|---:|---:|---:|---|---:|---|
| 321100 | 4890.066462 / 4890.066462 | 16/16 | `upper_bound_reached` | 182 / 182 | identical |
| 321101 | 4868.172927 / 4868.172927 | 16/16 | `upper_bound_reached` | 215 / 215 | identical |
| 321106 | 4390.462426 / 4390.462426 | 16/16 | `upper_bound_reached` | 200 / 200 | identical |

The compared action signature includes path, channel, position, measurement result, and clear result. Only simulator real-time timestamps differ. All 191 audit records contain the required fields, and every audit choice matches the existing decision record.

## Conclusion

The current evidence most strongly supports **A**. The nearby targets are generated and eligible, but the coverage action is undercharged for later spatial return, so its score remains lower.

The single most valuable next direction is to test an explicit **defer/return cost for coverage**. No such change is implemented in this audit task.
