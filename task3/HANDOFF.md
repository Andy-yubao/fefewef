# Task 3 Agent Handoff

Last updated: 2026-09-11 (Asia/Shanghai)

## Objective and evidence boundary

This directory implements CUMCM Problem B, Question 3: one robot must automatically search for, locate, and clear an unknown number of omnidirectional interference sources. The architecture is a deterministic guarantee layer plus an expected-time acceleration layer.

Do not claim global time optimality. The supported correctness claim is finite-step discovery and clearing under the problem assumptions and normal simulator responses. Particles or probability models may rank actions only; they must never delete hard-feasible locations, certify a clear, or terminate the task.

Before changing behavior, read these sources completely and apply this priority:

1. `problem/B题/B题.md`
2. `problem/B题/附件/附件1.md`
3. `problem/B题/附件/附件2.md`
4. `task3/strategy_design_katex_fixed.md`
5. Relevant `task2/` implementations and experiments

Check `git status --short` before edits. Preserve unrelated work, never modify `prompt/` or `task3/prompt.md`, and never commit credentials or machine-specific runtime configuration.

Do not automatically use `$math-modeling-skill`, `$math-modeling-review`, or `$kflow`. The user must explicitly authorize a specific skill for the current task after its purpose is explained.

## Current implementation

Production code is separated by responsibility:

- `task3/src/client.py`: serial HTTP client, idempotent retries, response validation, time tracking, redacted JSONL logs;
- `task3/src/coverage.py`: seven-point layout, analytic coverage certificate, route orientation;
- `task3/src/geometry.py`: conservative cell outer approximation, bounded-bearing geometry, safe MEC, finite 20 m cover;
- `task3/src/channel_state.py`: per-channel state machine, observation updates, diagnostics, fallback state, termination;
- `task3/src/local_planner.py`: candidate generation and Geometry/E-optimal/expected-diameter/shortlist ranking;
- `task3/src/scheduler.py`: finite-candidate rolling SEARCH/LOCALIZE/CLEAR scheduler and anti-starvation;
- `task3/src/controller.py`: end-to-end execution and time accounting;
- `task3/src/main.py`: generic practice CLI;
- `task3/src/mock_simulator.py`: local simulator using the same controller interface;
- `task3/src/config.py`: physical, planner, and client configuration.

Runtime dependency flow:

```text
run_practice -> main -> SearchController
                       |-- SimulatorClient
                       |-- Scheduler -> LocalPlanner
                       |-- ChannelState -> Geometry
                       `-- Coverage
```

The hard set is a union of closed 20 m square cells. Cell deletion is conservative. Direction updates use the bounded bearing wedge, 1500 m maximum reception distance, greater-than-5 m normal-direction condition, and target disk. `no_signal` removes only cells wholly inside the guaranteed 1000 m reception disk. A safe clear is issued only when the outer-cell MEC radius is at most 19.75 m. Otherwise, the finite cell-center cover guarantees eventual clearing.

Normal completion is allowed only after clearing 16 sources, or after all seven coverage positions are complete, all remaining unknown channels have absence certificates, and all found channels are cleared. Fewer than 10 sources after full coverage is invalid.

## Strategy selection

Strategy selection is two-dimensional:

```text
mode          = two_stage | enroute | rolling_hard | hybrid
local_family  = geometry | e_optimal | expected_diameter | shortlist
```

Validated experiment aliases are defined in `task3/experiments/run_offline.py`:

| Alias | Mode | Local family |
|---|---|---|
| `B0_two_stage` | `two_stage` | `shortlist` |
| `B1_enroute` | `enroute` | `shortlist` |
| `B2_rolling_hard` | `rolling_hard` | `shortlist` |
| `B3_hybrid` | `hybrid` | `shortlist` |
| `A_geometry` | `hybrid` | `geometry` |
| `A_e_optimal` | `hybrid` | `e_optimal` |
| `A_expected_diameter` | `hybrid` | `expected_diameter` |

`task3/experiments/run_practice.py` now exposes `--mode` and `--local-family` and writes a `strategy` object into the summary. The older B3 summary was backfilled with its strategy metadata.

There is no single `--policy A_geometry` practice option yet. If one is added, create one shared registry rather than duplicating aliases across scripts.

## Verification completed

Latest regression:

```bash
task2/.venv/bin/python -m pytest task3/test -q
```

Result: `31 passed in 8.68s`.

Tests cover the analytic seven-point certificate, angle wrapping, direction truth retention, 1000 m-only no-signal deletion, immediate near clearing, nonconvex outer bounds, MEC certification, gap-free finite cover, state transitions, strict termination, `/clear` channel behavior, HTTP retry idempotency, rejection and connection failure, and controller integration.

The offline experiment used seed 20260911, 100 paired scenarios, and 9 configurations (900 runs). Every run cleared 100% and completed coverage:

| Policy | Mean virtual time (s) |
|---|---:|
| B0 two-stage | 6110.3 |
| B1 enroute | 5396.3 |
| B2 rolling-hard | 5441.7 |
| B3 hybrid-shortlist | 5463.8 |
| Geometry | **4973.8** |
| E-optimal | 5511.0 |
| Expected-diameter | 5792.6 |

Offline artifacts:

- `task3/results/raw/offline_runs.jsonl.gz`
- `task3/results/raw/offline_manifest.json`
- `task3/results/tables/offline_strategy_summary.csv`
- `task3/results/tables/offline_paired_vs_two_stage.csv`
- `task3/results/figures/offline_virtual_time_boxplot.png`
- `task3/results/figures/offline_virtual_time_ecdf.png`

## Official simulator practice

Two Problem 3 practice runs completed through a Windows simulator reachable from WSL. Do not persist the runtime team ID, service address, proxy, or credentials. The user must start each new practice in the GUI and provide a fresh case code.

### Practice 1: B3 hybrid-shortlist

- Case: `J2TJ-2H73-YG5X-Y4AZ`
- GUI-confirmed target count: 16
- Cleared: 16 (100%)
- Completion: `upper_bound_reached`
- Coverage: 7/7
- Virtual time: 5903.925815 s
- Average: 368.995363 s/source
- Wall time: 2.910344 s
- Controller actions: 217
- Accepted responses including enter/exit: 219
- Network retries: 0
- Time breakdown: movement 4680.925816, switching 164, measurement 940, optical 87, laser 32 s
- Fallback clear misses: 13
- Certified clear failures: 0
- Raw log: `task3/results/raw/practice/J2TJ-2H73-YG5X-Y4AZ-20260911-132112.jsonl`
- Summary: matching `.summary.json`

### Practice 2: hybrid-geometry

- Case: `WBBE-W933-ZBEX-DQ7B`
- Source count: 12 clears plus full absence certificates; the user confirmed normal simulator completion
- Cleared: 12 (100%)
- Completion: `coverage_certificate_and_all_found_cleared`
- Coverage: 7/7
- Virtual time: 4287.435573 s
- Average: 357.286298 s/source
- Wall time: 1.866658 s
- Controller actions: 185
- Accepted responses including enter/exit: 187
- Network retries: 0
- Time breakdown: movement 3205.435572, switching 157, measurement 865, optical 36, laser 24 s
- Fallback clear misses: 0
- Certified clear failures: 0
- Raw log: `task3/results/raw/practice/WBBE-W933-ZBEX-DQ7B-20260911-145148.jsonl`
- Summary: matching `.summary.json`

The Geometry run improved the cross-case average by 11.709066 s/source (3.17%) and reduced movement from 292.557863 to 267.119631 s/source. It used more measurement and switching time per source. These are different cases, so this is directional evidence, not a paired treatment effect.

The aggregate is `task3/results/tables/practice_summary.csv`; the paper material is `task3/report/problem3_report_katex.md`.

## Working-tree state

Before this documentation request, `git status --short` showed:

```text
M  task3/experiments/run_practice.py
M  task3/report/problem3_report_katex.md
M  task3/results/raw/practice/J2TJ-2H73-YG5X-Y4AZ-20260911-132112.summary.json
M  task3/results/tables/practice_summary.csv
?? task3/results/raw/practice/WBBE-W933-ZBEX-DQ7B-20260911-145148.jsonl
?? task3/results/raw/practice/WBBE-W933-ZBEX-DQ7B-20260911-145148.summary.json
```

`task3/README.md` and this `task3/HANDOFF.md` are also changed/new by the documentation request. Re-run `git status --short` before editing. Do not discard or reset these files. Do not touch `task3/prompt.md`.

## Known performance issues

1. Movement dominates virtual time; it was 79.28% of the first practice.
2. Fixed `max_bearings_before_fallback=6` may trigger finite cover too early. B3 had 13 fallback misses.
3. At each mandatory coverage stop, `SearchController._scan_coverage()` measures every found, unmeasured channel rather than gating by information value.
4. `Scheduler.choose()` builds full local candidates only for the nearest three found channels, creating local-routing bias.
5. The remaining-time proxy is additive by channel and does not jointly optimize a multi-channel route.
6. The 20 m grid is safe for finite clearing but coarse for MEC certification.
7. B3 particle reception radii are an ordering prior, not a calibrated simulator model. Offline Geometry is faster and simpler.

## Recommended next work

1. Run more Geometry practices before freezing the policy. Each run requires the user to start Problem 3 practice and provide a new case code.
2. Preserve paired offline comparisons for every algorithm change; rerun the same 100 seeds.
3. Replace the fixed six-bearing trigger with a cost comparison between another informative bearing and the remaining finite-cover route.
4. Gate opportunistic found-channel measurements at coverage points by geometric information gain and incremental time.
5. Consider joint routing over localization and clear points while preserving anti-starvation and mandatory coverage.
6. Add tests for practice CLI strategy forwarding and summary metadata.
7. Keep hard geometry and termination independent of probabilistic ranking.
8. Expand official practice toward 100 runs if time permits, then report mean, median, P90/P95, maximum, and case-level bootstrap intervals.

## Practice command template

The user must first confirm that the GUI is in Problem 3 practice mode:

```bash
task2/.venv/bin/python -m task3.experiments.run_practice \
  --robot-id '<runtime team id>' \
  --base-url 'http://<runtime Windows address>:<port>' \
  --case-id '<fresh GUI case code>' \
  --mode hybrid \
  --local-family geometry \
  --local-action-limit 3
```

After the GUI reveals the true total:

```bash
task2/.venv/bin/python -m task3.experiments.annotate_practice \
  --summary task3/results/raw/practice/<case-timestamp>.summary.json \
  --total '<GUI total>'

task2/.venv/bin/python -m task3.experiments.analyze_practice
```

## Formal-test protection

No formal test has been authorized or run. Only three formal opportunities exist. Do not invoke or construct a formal-test flow unless the user explicitly authorizes it in the current task. Before a formal run, freeze code and parameters, do not tune after individual results, and preserve simulator-exported encrypted logs without renaming or editing them.
