# Candidate 020 vs Geometry Champion: 10-case paired route check

## Scope and reproducibility

This is an additional small paired sample, not a promotion or statistical proof. Seeds `321100` through `321109` were not present in the existing candidate 020 optimization results and are outside the registered development, stability, and final-holdout ranges. Both policies were run in the same command for each fixed 16-source scenario, with actions retained:

```text
task2/.venv/Scripts/python.exe -m task3.experiments.run_offline --cases 10 --workers 1 --seed 321100 --source-count 16 --policies champion_000_geometry_baseline candidate_020_grid5_center_approach --output task3/results/raw/optimization/paired_020_vs_champion_visual_10.jsonl.gz
```

All 20 policy runs succeeded, cleared 16/16 sources, completed all seven coverage positions, and terminated with `upper_bound_reached`.

## Summary

| Policy | Mean virtual time (s) | Median virtual time (s) | Mean movement time (s) | Median movement time (s) |
|---|---:|---:|---:|---:|
| `champion_000_geometry_baseline` | 5335.888 | 5452.283 | 4181.288 | 4280.283 |
| `candidate_020_grid5_center_approach` | 4628.462 | 4730.082 | 3561.662 | 3684.848 |

- Candidate 020 wins: 10/10; Champion wins: 0/10; ties: 0/10.
- Mean paired difference (`020 - champion`): -707.426 s.
- Mean movement reduction: 619.626 s, about 87.6% of the mean virtual-time difference.
- Per-case values are in `task3/results/tables/paired_020_vs_champion_visual_10.csv`.

## Route observations

- All five plotted pairs (`321100` through `321104`) show lower movement time for candidate 020, consistent with the shorter-looking routes.
- In `321100`, candidate 020 removes several short loops and backtracks visible in the Champion route, especially near the southern and south-eastern boundary.
- In `321101`, the Champion makes pronounced left-side and right-side excursions before rejoining the coverage backbone; candidate 020 trims these excursions while retaining the same cleared sources.
- In `321103`, both routes still contain cross-field travel, but candidate 020 uses tighter local approaches; this is also the smallest advantage among the five plotted cases.
- The visual differences support a movement-cost explanation rather than a success/coverage tradeoff: both policies clear the same 16 sources and complete coverage.
- No plotted or unplotted case favors the Champion in virtual time, so this sample provides additional paired evidence for candidate 020 but does not establish stable superiority or justify promotion.
