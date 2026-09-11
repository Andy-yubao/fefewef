# Candidate 038: Task-Queue Directional Sweep

## 1. Architecture

Implemented as a controller independent of the legacy scheduler and candidate 037:

- three phases: `bootstrap`, `initial_outward_service`, and `directional_sweep`;
- a two-kind `TaskQueue`: `ResolveSource(channel)` and `AdvanceCoverage(vertex)`;
- committed `ACTIVE`, with observation-triggered rebuild/reorder limited to `WAITING`;
- lexicographic source ordering by service deadline, sector, completion stage, and next-action distance;
- a fixed Resolve state machine: certified clear, current-position measurement, forward-route measurement, forward-transverse measurement, conservative fallback;
- UNKNOWN-only discovery scans at coverage milestones;
- zero-detour opportunistic measure/clear events that update belief and WAITING without changing ACTIVE;
- conservative certificate-sector membership and a hard rejection of normal dedicated points in completed sectors.

The controller records task start/end/reason, waiting order, phase, sweep sector/direction,
completed sectors, and semantic movement segments for route inspection.

## 2. Baseline protection

- `candidate_020_grid5_center_approach` remains registered to the legacy `SearchController`.
- `candidate_037_route_embedded_sweep` remains registered to `RouteEmbeddedController`.
- Candidate 038 is registered separately as `candidate_038_task_queue_sweep`.
- Neither baseline controller implementation was modified for candidate 038.

## 3. Route behavior

Route figure: [`seed20260911_candidate038_route.png`](../results/figures/task_queue_sweep/seed20260911_candidate038_route.png)

The figure distinguishes Resolve movement, Advance movement, opportunistic events,
task switches, coverage milestones, and the selected CCW direction. In the three final
smoke cases:

- all nonzero movement segments had an ACTIVE `ResolveSource` or `AdvanceCoverage` explanation;
- five milestones were advanced in directional order before all 16 sources were cleared;
- all 16 clears occurred during the sweep;
- completed-sector returns: `0, 0, 0`;
- cleanup movement share: `0, 0, 0`.

The remaining weakness is visible in the long Resolve segments: conservative fallback
service is reliable but movement-heavy. This is a service-point construction/performance
issue, not an ACTIVE-preemption or sweep-reversal failure.

## 4. Three-case smoke

All cases contain 16 sources. Movement is movement time in seconds.

| Seed | Policy | Success | Movement | Virtual time |
|---:|---|:---:|---:|---:|
| 20260911 | candidate 020 | yes | 3678.51 | 4750.51 |
| 20260911 | candidate 037 | yes | 4257.62 | 5325.62 |
| 20260911 | candidate 038 | yes | 6851.30 | 9322.30 |
| 20260912 | candidate 020 | yes | 3722.58 | 4778.58 |
| 20260912 | candidate 037 | yes | 4081.48 | 4918.48 |
| 20260912 | candidate 038 | yes | 6832.29 | 7994.29 |
| 20260913 | candidate 020 | yes | 3365.56 | 4434.56 |
| 20260913 | candidate 037 | yes | 3662.37 | 4378.37 |
| 20260913 | candidate 038 | yes | 6833.54 | 7924.54 |

Candidate 038 behavior diagnostics:

| Seed | Sweep clears | Cleanup movement | Opportunistic measure / clear | Advance / Resolve | Completed-sector return |
|---:|---:|---:|---:|---:|---:|
| 20260911 | 16 | 0.00 | 12 / 0 | 5 / 16 | 0 |
| 20260912 | 16 | 0.00 | 10 / 0 | 5 / 16 | 0 |
| 20260913 | 16 | 0.00 | 19 / 0 | 5 / 16 | 0 |

Raw paired baseline run: [`task_queue_sweep_smoke_020_037_038.jsonl.gz`](../results/raw/optimization/task_queue_sweep_smoke_020_037_038.jsonl.gz)

Final candidate-038 run: [`task_queue_sweep_smoke_038_final.jsonl.gz`](../results/raw/optimization/task_queue_sweep_smoke_038_final.jsonl.gz)

## 5. Tests

The focused suite covers baseline separation/instantiation, ACTIVE commitment,
WAITING reorder, opportunistic non-preemption, UNKNOWN-only milestone scans,
Resolve closure, and completed-sector candidate rejection. Existing controller,
scheduler, and candidate-037 tests are also included in regression verification.

## 6. Judgment

**Yes: TaskQueue + committed ACTIVE task + directional sweep now implements the intended
core route behavior.** The final smoke has stable task commitment, ordered coverage,
16/16 sweep clearing, zero cleanup movement, zero unexplained movement, and zero
completed-sector return.

It is worth continuing with targeted performance work on conservative fallback and
forward measurement geometry. Candidate 038 is not yet competitive with candidate 020
or 037 in movement or virtual time, so it should not replace the reliable baseline.
