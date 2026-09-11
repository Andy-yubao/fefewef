# Candidate 020 Defer-Regret Audit and Candidate 036 Paired Check

## Scope

- Baseline: `candidate_020_grid5_center_approach`
- Shadow seeds: `321100`, `321101`, `321106`
- Paired seeds: `321100`--`321109`
- Fixed source count: 16
- Defer-regret weight: `lambda = 1.0`
- No detection, local-planner, coverage-point, shortlist, upper-bound, or other scheduler parameter was changed.

The shadow calculation used every LOCALIZE/CLEAR action already generated in the current scheduler decision and did not change candidate generation. For a local action point `a`, it computed

```text
max(0, distance(coverage_next, a) - distance(current_position, a)) / speed
```

and used the maximum over the generated local actions. The shadow artifact is `task3/results/raw/optimization/020_defer_regret_shadow_audit.jsonl.gz`; the decision-level table is `task3/results/tables/defer_regret_036/shadow_search_decisions.csv`.

## Stage 1: shadow audit

| Seed | Comparable SEARCH decisions | Would flip | Flips to reported best LOCALIZE under 500 m |
|---:|---:|---:|---:|
| 321100 | 6 | 6 | 4 |
| 321101 | 6 | 5 | 2 |
| 321106 | 6 | 6 | 4 |
| **Total** | **18** | **17** | **10** |

- All 17 flips were to LOCALIZE; none was to CLEAR.
- Defer regret ranged from 90.885 s to 239.911 s, with a median of 214.222 s.
- Every flipped best local action was closer than the next coverage point, by 227.3 m to 944.2 m.
- Ten flips selected a reported best LOCALIZE under 500 m. The other seven selected a 507.7--751.9 m LOCALIZE while the next coverage point was 1200 m away.
- The only decision that did not flip had a 376.7 m LOCALIZE and a 502.7 m coverage point: adding 99.3 s regret was still insufficient to overcome its 128.5 s original score gap.

The shadow result therefore corrected the intended proximity pattern without flipping toward a farther local action. It passed the stated gate for implementing one candidate, although flipping 17/18 decisions also indicated that the dynamic paired run was essential.

## Stage 2: candidate 036

`candidate_036_grid5_center_defer1` inherits candidate 020's mode, local family, and planner overrides and adds only:

```text
search_defer_regret_weight = 1.0
```

`PlannerConfig` defaults this setting to `0.0`, so existing policies retain their scheduler scores and choices. The SEARCH surcharge uses the maximum regret rather than summing across sources.

## Ten-case paired result

Command:

```text
task2/.venv/Scripts/python.exe -m task3.experiments.run_offline --cases 10 --workers 1 --seed 321100 --source-count 16 --policies candidate_020_grid5_center_approach candidate_036_grid5_center_defer1 --output task3/results/raw/optimization/paired_020_vs_036_defer1_10.jsonl.gz
```

| Policy | Mean virtual time (s) | Median virtual time (s) | Mean movement time (s) | Median movement time (s) | SEARCH | Measurements | Cleared | Early pass then return | Termination |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `candidate_020_grid5_center_approach` | 4628.462 | 4730.082 | 3561.662 | 3684.848 | 60 | 1642 | 160 | 33 | 10/10 `upper_bound_reached` |
| `candidate_036_grid5_center_defer1` | 4881.054 | 4868.899 | 3852.154 | 3860.958 | 60 | 1584 | 160 | 66 | 10/10 `upper_bound_reached` |

- Candidate 036 wins/losses/ties against 020: **2/8/0**.
- Mean paired virtual-time change (`036 - 020`): **+252.592 s** (+5.46%).
- Mean paired movement-time change (`036 - 020`): **+290.492 s** (+8.16%).
- `early_pass_then_return` increased from **33 to 66** (+100%). The diagnostic uses the same 300 m definition as the earlier route diagnosis: an earlier route point was within 300 m of the true source, the route later left that neighborhood, and the robot subsequently returned to clear it.
- Measurements decreased by 58 in total, but that did not compensate for the extra movement.
- Per-seed values are recorded in `task3/results/tables/defer_regret_036/paired_020_vs_036_defer1_10.csv`.

## Conclusion

The static shadow audit looked locally reasonable, but the closed-loop paired experiment falsified the intended mechanism. Candidate 036 increased both movement time and `early_pass_then_return`; its occasional total-time wins do not constitute mechanism validation. Keep the implementation and artifacts only as a reproducible negative result. Do not promote the candidate or continue tuning this direction from the present evidence.

## Tests

- With weight zero, candidate 020 reproduced all 10 prior virtual times and action signatures exactly.
- Targeted scheduler tests: 6 passed.
- Full Q3 suite: 37 passed.
