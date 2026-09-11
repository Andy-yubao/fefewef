# Candidate 038: Recovered Task-Queue Directional Sweep

## Root cause

The paused implementation failed for three structural reasons:

1. A source being present in the Todo list was treated too much like permission to
   activate it. Wide certificates were promoted early and Resolve could suppress
   continued coverage.
2. The resolver selected fresh transverse points after every belief update. The
   target could flip across the certificate and create long dedicated zigzags.
3. Direction was inferred from completed-sector bookkeeping and the robot's current
   projection. Local detours could therefore be mistaken for macro progress, while
   sources near the rank-5/rank-0 boundary could be mistaken for backward work.

## Final architecture

- **Bootstrap:** scan every channel at the origin, retain both direction and
  no-signal evidence, then choose the outward orientation and CW/CCW traversal.
- **Initial outward service:** keep the first coverage vertex as a discovery
  obligation, but allow zero-detour observations while moving outward.
- **Directional sweep:** advance through the six ordered coverage milestones. The
  milestone sequence supplies the discovery guarantee; it is not a mandatory path
  to which the robot must return after every source.
- **TaskQueue:** every found channel has a `ResolveSource` Todo. Not-ready Resolve
  tasks remain WAITING and cannot block the next `AdvanceCoverage`. ACTIVE remains
  committed while ordinary observations only rebuild/reorder WAITING.
- **ResolveSource:** clear immediately when certified; otherwise use the current
  position, fixed forward-edge checkpoints, then a stable certificate-center
  approach. Current-sector Todos are ordered by their forward-edge approach
  position, preventing a later source from making the robot pass an earlier one.
- **Opportunistic observer:** measure or certified-clear other channels on an
  already-required movement segment without switching ACTIVE.
- **Direction:** an explicit per-leg progress variable changes only on forward-route
  progress or milestone completion. Local detours do not advance the macro
  frontier. Rank 5 to rank 0 is treated as the adjacent forward wrap.
- **Fallback:** finite cover remains gated by the existing bearing limit and may use
  only a forward-compatible point. It was unused in all final smoke cases.

## What changed

The recovery changed only candidate-038-specific code:

- `task_queue.py`: separates task existence from activation readiness.
- `task_sweep_planner.py`: center-based service windows, explicit CW/CCW traversal
  ranks, circular forward compatibility, and forward-only service geometry.
- `task_driven_controller.py`: stable leg progress, approach-ordered WAITING,
  committed center-approach Resolve, fallback gating, and behavior diagnostics.
- `opportunistic_observer.py`: bearing-limit accounting uses actual bearings rather
  than all history entries.
- `test_task_queue_sweep.py`: focused READY/WAITING, fallback, rank, deadline, and
  baseline-separation tests.

The legacy scheduler, candidate 020, ChannelState geometry, coverage certificate,
and offline simulator were not changed.

## Seed 20260911 route

Final route figure:
[`seed20260911_candidate038_recovered_route.png`](../results/figures/task_queue_sweep/seed20260911_candidate038_recovered_route.png)

The route visibly leaves the origin, reaches V1, and progresses CCW through V6.
Resolve movements are concentrated in the current/adjacent service region; there is
no return to a passed macro region, no fallback, and no post-sweep cleanup. Longer
radial legs in the final sector are committed service for sources in that sector,
not cross-field returns.

## Three-case smoke

All cases use 16 sources. Movement is movement time in seconds.

| Seed | Policy | Success | Movement | Virtual time |
|---:|---|:---:|---:|---:|
| 20260911 | candidate 020 | yes | 3678.51 | 4750.51 |
| 20260911 | candidate 038 | yes | 3852.31 | 4651.31 |
| 20260912 | candidate 020 | yes | 3722.58 | 4778.58 |
| 20260912 | candidate 038 | yes | 4030.19 | 4918.19 |
| 20260913 | candidate 020 | yes | 3365.56 | 4434.56 |
| 20260913 | candidate 038 | yes | 3298.53 | 4022.53 |

Candidate 038 averaged 3727.01 s movement and 4530.68 s virtual time. Against
candidate 020, that is about 3.8% more movement but 2.7% less virtual time. It beat
candidate 020 on both metrics in seed 20260913.

| Seed | Resolve | Advance | Opportunistic measure / clear | Fallback count / movement | Cleanup movement | Macro reversal |
|---:|---:|---:|---:|---:|---:|---:|
| 20260911 | 16 | 6 | 9 / 0 | 0 / 0.00 | 0.00 | 0 |
| 20260912 | 16 | 6 | 21 / 0 | 0 / 0.00 | 0.00 | 0 |
| 20260913 | 16 | 6 | 18 / 0 | 0 / 0.00 | 0.00 | 0 |

Raw paired run:
[`task_queue_sweep_recovery_smoke_020_038.jsonl.gz`](../results/raw/optimization/task_queue_sweep_recovery_smoke_020_038.jsonl.gz)

## Judgment

Candidate 038 now behaves as the intended explainable architecture: establish global
information, move outward, sweep in one macro direction, commit only a ready source,
and exploit observations made along required travel. It is a viable Q3 candidate,
although candidate 020 remains the lower-risk baseline. The single main remaining
bottleneck is radial service distance for sources far from the milestone corridor;
the three-case result does not justify a larger benchmark or another broad redesign.
