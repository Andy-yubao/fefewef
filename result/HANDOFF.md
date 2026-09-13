# Task 4: Mixed-100 vs All-Directional-100 Experiment Data

## Purpose

This directory contains a copied, self-contained data package for the Task 4
comparison requested on 2026-09-13:

- 100 locally generated cases containing a random mixture of omnidirectional
  and directional emitters; and
- 100 locally generated all-directional cases.

No new simulation was run when this package was prepared. The repository
already contained the required experiment outputs, so the relevant data files
were copied without modification.

## Data location

The copied package is under `task4_mixed100_vs_directional100/`:

- `mixed100/`: directional probability `0.5`, seeds `0` through `99`.
- `all_directional100/`: directional probability `1.0`, seeds `0` through
  `99`.

Each scenario contains:

- `manifest.json`: command, seed list, simulator configuration, and strategy
  configuration.
- `paired_cases.csv`: per-seed baseline/candidate comparison.
- `comparison.json` and `comparison.md`: aggregate candidate-minus-baseline
  comparisons.
- `baseline/`: per-case data and summaries for
  `double_ring_optical_clear_probe`.
- `candidate/`: per-case data and summaries for
  `adaptive_double_ring_clear_probe`.

The original source directories are:

- `experiments/t4_analysis/outputs/toward6000_v2/development_mixed100/`
- `experiments/t4_analysis/outputs/toward6000_v2/development_directional100/`

Full regression action logs remain in the original source directories and are
not duplicated here because they are not needed to reproduce the aggregate
statistics below.

## Emitter counts

Emitter counts are computed from the `emitter_count` and `directional_count`
columns in the candidate `cases.csv` files. Baseline and candidate runs use the
same generated case within each scenario, so they must not be double-counted.

| Scenario | Cases | Total emitters | Omnidirectional | Directional |
|---|---:|---:|---:|---:|
| Random mixed (`p=0.5`) | 100 | 1,274 | 611 (47.96%) | 663 (52.04%) |
| All directional (`p=1.0`) | 100 | 1,274 | 0 (0.00%) | 1,274 (100.00%) |
| Combined | 200 | 2,548 | 611 (23.98%) | 1,937 (76.02%) |

## Main results

All 100 cases were fully cleared by both strategies in both scenarios.

| Scenario | Strategy | Fully cleared | Mean time (s) | P95 (s) | Fully cleared within 6,000 s |
|---|---|---:|---:|---:|---:|
| Random mixed | Baseline | 100/100 | 6,735.71 | 7,792.29 | 6/100 |
| Random mixed | Adaptive candidate | 100/100 | 6,436.51 | 7,406.15 | 15/100 |
| All directional | Baseline | 100/100 | 7,418.91 | 8,592.31 | 0/100 |
| All directional | Adaptive candidate | 100/100 | 7,036.46 | 7,909.91 | 2/100 |

For the adaptive candidate, the all-directional sample has a mean time that is
599.94 seconds (9.32%) higher than the mixed sample. Its P95 is 503.76 seconds
higher, and its count of cases fully cleared within 6,000 seconds falls from 15
to 2.

## Evidence boundary

These are deterministic-seed local simulator experiments, not official Task 4
runs. Emitter counts range from 10 to 16. The mixed scenario randomly assigns
emitter type with probability `0.5` under the local generator assumptions.

The two scenarios use the same seed numbers and have the same per-seed emitter
counts, but they are not a strict controlled comparison in which identical
emitter positions, radii, and directions are retained and only emitter type is
changed. Conditional random-number consumption during generation can change
later emitter attributes. Therefore, compare the two scenarios as aggregate
samples, not as case-by-case type-only counterfactual pairs.

These two 100-case sets were development data used during strategy selection.
They are suitable for documenting the requested 100+100 comparison but should
not be presented as untouched holdout evidence. Separate 300-case mixed and
all-directional holdout results remain in the original `toward6000_v2` output
tree.

The adaptive strategy is an independently evaluated candidate. Preparing this
data package did not change the Task 4 CLI default strategy.

---

# Task 3: Candidate 057 Concurrent-100 Experiment Data

## Purpose

This directory also contains the raw output from the Task 3 concurrent-scale
test requested on 2026-09-13. The test evaluated the current strategy,
`candidate_057_posterior_free`, on 100 locally generated scenarios using 100
worker processes.

The copied data file is:

- `candidate057_concurrency100_seed20261310.jsonl.gz`

Its original location is:

- `task3/results/raw/optimization/candidate057_concurrency100_seed20261310.jsonl.gz`

The copy is byte-for-byte identical to the original. Its SHA-256 digest is:

```text
fc2e81dfa8fa7c399ac18d14dbf8ec687906da47a78e9a34364523acacc2d464
```

## Experiment configuration

- Policy: `candidate_057_posterior_free`
- Cases: 100
- Scenario seeds: `20261310` through `20261409`
- Workers: 100
- Available logical CPU cores: 32
- Sources per case: randomly generated from 10 through 16
- Grid step: 5 m
- Action traces: omitted with `--no-actions` to reduce output and I/O
- Simulator: the local Task 3 `MockSimulator`

The experiment was run from the repository root with:

```bash
/usr/bin/time -v task2/.venv/bin/python \
  -m task3.experiments.run_offline \
  --cases 100 \
  --seed 20261310 \
  --workers 100 \
  --grid-step 5 \
  --policies candidate_057_posterior_free \
  --no-actions \
  --output task3/results/raw/optimization/candidate057_concurrency100_seed20261310.jsonl.gz
```

## Main results

The process exited successfully with status 0. The compressed file contains
one metadata record and exactly 100 experiment records.

| Metric | Result |
|---|---:|
| Successful cases | 100/100 |
| Sources cleared | 1,291/1,291 (100%) |
| Unexpected clear failures | 0 |
| Mean virtual time per case | 3,305.03 s |
| Aggregate virtual time per source | 256.01 s |
| Bootstrap 95% CI for time per source | 250.00--261.90 s |
| P95 virtual time per case | 3,703.95 s |
| Maximum virtual time per case | 3,999.60 s |
| End-to-end wall-clock time | 306.67 s |
| Observed throughput | 19.57 cases/min |
| Average CPU utilization reported by GNU `time` | 2,961% |

The bootstrap interval used 5,000 whole-scenario resamples with seed
`20261310`. Completeness and virtual-time accounting were checked with
`task3.experiments.summarize_optimization`.

## Evidence boundary

This is a local stress test, not an official competition result. The 100
workers oversubscribed the machine's 32 logical CPU cores, so wall-clock time,
per-case wall runtime, throughput, and CPU utilization are specific to this
machine and workload. Virtual-time results describe the simulator's modeled
competition time and should not be confused with execution time.

Because the run used `--no-actions`, the package supports result-level and
time-accounting checks but does not contain the per-action trace needed for an
independent action-by-action replay audit. A 100/100 local result also does not
prove zero failure probability outside the sampled scenarios or under the
official simulator.
