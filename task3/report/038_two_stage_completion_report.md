# Candidate 038: two-stage commitment repair and completion-aware sequencing

Two stages, each committed separately. Stage 1 is `1247436`; Stage 2 follows it.
Seed 20260911 is the designated validation seed throughout.

## Stage 1 — task commitment semantics

Two places still let one immediate action stand in for a whole task.

**AdvanceCoverage.** `_execute_advance` also runs en-route opportunistic
observations and an unknown-channel scan at the vertex, so `distance / speed`
was never the cost of the whole task. The coverage vertex and the immediate
movement cost remain known; `completion_known` is now `False` and no completion
cost or endpoint is claimed.

**ResolveSource.** A completion-unknown Resolve already refused to report its
next action as its completion cost, but the selector still ranked candidates by
`estimated_immediate_cost_s`. An intermediate MEASURE sitting on the robot's own
pose therefore cost 5-6 s, won the task-level commitment, and then drove
hundreds of metres. Commitment now follows the sweep planner's stable
`order_key` — required gate first, then geometric forward order. Immediate
previews are still recorded and still executed; they no longer rank tasks.

### Seed 20260911

| metric | HEAD `fd83ae6` | Stage 1 | recovered `8852e56` |
|---|---:|---:|---:|
| virtual time (s) | 5320.1 | **4819.6** | — |
| movement (m) | 21725.5 | **20013.1** | 19261.6 |
| measurements | 156 | **128** | — |
| local leg retraces | 7 / 1990.1 m | **1 / 0.8 m** | — |

16/16 cleared, CCW sweep intact, no macro reversal, no completed-sector return,
no cleanup, no fallback. The route is the pre-sequencer order_key route: it
matches the `a406889` run action-for-action (only wall-clock timestamps differ).

### Stage 1 image review — **improved**, gate passed

1. Commitment is now sector-by-sector: every Resolve belonging to the current
   milestone sector is serviced before the next Advance, and the six blue
   Advance legs form a clean CCW V1→V2→V3→V4→V5→V6 progression. HEAD opened
   with Resolve ch14 *before* the first Advance and later threw ch13 1900 m
   across the field from (-1655,-328) to (136,-888) and back.
2. No red line leaves the current/adjacent sector before its Advance any more;
   local leg retracing fell from 1990 m to 0.8 m.
3. Remaining defects are unchanged resolver-chain shapes, not commitment
   errors: ch15's literal out-and-back at V2 (1228 m for 329 m net), ch7's
   four-step inchworm then a 614 m reversal, and ch13's oscillation around
   x ≈ 140.

Figure: `results/figures/task_queue_sweep/seed20260911_candidate038_stage1_route.png`

## Stage 2 — completion-level preview and gated sequencing

Design: `038_completion_preview_design.md`, written before the code.

`TaskPreview` now carries a `CompletionPreview` with an explicit
`CompletionCertainty`:

- `EXACT` — the next action is the certified clear, so endpoint and cost are
  deterministic.
- `ESTIMATED` — endpoint is the certified clear point or the certificate
  centre, and it is forward-compatible with the sweep frontier.
- `UNKNOWN` — no admissible endpoint. No completion claim at all; the task is
  excluded from sequencing and ranked by `order_key`.

Sequencing fully permutes at most three priced Resolves and prices every leg
against the previous leg's end state (position and the channel the robot then
holds), plus an optional trailing `AdvanceCoverage` positional term. Only
Resolves that already precede Advance under the macro rule
(`order_key < advance.order_key`) may be reordered, so the CW/CCW sweep stays a
hard constraint. Belief is strictly per-channel, so a completed Resolve cannot
move another channel's certificate — the predictable parts are recomputed and
nothing else is invented.

### Preview accuracy on seed 20260911

Prediction at the committing decision versus the executed Resolve.

| | n | endpoint error, median | endpoint error, max | predicted / actual cost |
|---|---:|---:|---:|---:|
| EXACT | 1 | 0 m | 0 m | 1.00 |
| ESTIMATED | 15 | 184 m | 487 m | 1.18 median |
| audited next-action preview (`074afcf`) | 16 | 364-400 m | 1445.6 m | median error 47-54 s |

Endpoint error is roughly halved and its worst case is three times better. The
cost is still an estimate — the resolver's own chain adds measures and detours
the model does not predict — so it is reported as a lower bound, and the
ordering it drives depends on the endpoints, not on the absolute cost.

Exact cost ties among the 57 priced comparisons in the 112 decisions: **0**.
Ordering is decided by completion geometry, never by the label string (the
audit measured 9.7-28.6% exact ties in the old pair comparisons).

### Outcome: the sequencer declines to act, and the route is unchanged

A rollout is accepted only when its predicted gain over the ordering `order_key`
would have produced exceeds the summed belief uncertainty of the endpoints that
gain rests on (`certificate.radius_m + clear_radius_m`, converted to seconds).
That is the answer to "what happens when the prediction is unreliable": fall
back, do not patch with a penalty.

Measured on three seeds with the gate in place, no reorder ever clears the bar.
Stage 2's route is therefore **bit-identical to Stage 1's** on 0911, 0912 and
0913 (verified action-for-action, ignoring wall-clock timestamps). The machinery
is exercised — 32/39/36 full-permutation comparisons per run — and declines
every time.

The ungated counterfactual was measured and is worth recording, because it is
the evidence for keeping the gate:

| seed | Stage 1 virtual (s) | ungated Stage 2 | delta |
|---|---:|---:|---:|
| 20260911 | 4819.6 | 4661.5 | **−158.1** |
| 20260912 | 4759.8 | 5047.1 | **+287.3** |
| 20260913 | 3973.2 | 4083.2 | **+110.0** |

One seed better, two worse, with the sign of the change determined by
reorderings whose predicted advantage was 23-27 s against an endpoint
uncertainty of 111-179 s. Acting on that is acting on noise — which is why the
gate exists, and why the delivered Stage 2 does not override the sweep.

### Stage 2 image review — **neutral**, no regression

1. The 0911 route is unchanged from Stage 1, so the reviewed figure is
   `seed20260911_candidate038_stage1_route.png`; the Stage 2 run renders to the
   same bytes (md5 `191c2ada811d305b25e660d9ac8b58e0`).
2. Macro sweep is intact on all three seeds: CCW, 0 macro backward moves, 0
   cleanup movement, 0 fallback actions, 16/16 cleared.
3. Seed 20260913 (second smoke,
   `seed20260913_candidate038_stage2_route.png`) shows the same clean sector-by-
   sector CCW sweep; local leg retracing 3 / 28.5 m.

## What Stage 2 did not fix

The post-sweep tail remains the weakest part of the route: on 0911 after V6 the
robot services ch4, ch18, ch2, ch9 in that order, a 3.7 km zig-zag through the
arena centre. Completion-level ordering predicts a better order
(`ch18 → ch2 → ch9 → ch4`, 2.2 km) but the gain does not survive the belief
error of the endpoints, and the ungated attempt to take it made the run worse
overall. Closing that gap needs a more accurate endpoint than the current
certificate centre — not a larger weight.

## Tests

```
python -m pytest task3/test/ -q          # 74 passed
python -m task3.experiments.run_offline --cases 1 --seed 20260911 --workers 1 \
  --source-count 16 --policies candidate_038_task_queue_sweep --output <path>
python -m task3.experiments.plot_route <path> --policy candidate_038_task_queue_sweep --output <png>
```

No full benchmark was run. Seeds 20260911/0912/0913 only, all with 16 sources.
