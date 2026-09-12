# Candidate 038 Short-Horizon Sequencing: Forensic Audit

Read-only diagnosis of why `candidate_038_task_queue_sweep` still detours after
short-horizon route sequencing was added. No production code was changed.

## Scope and artifacts

- Commit under audit: `fdd18cc` ("feat: add short-horizon sequencing to candidate 038")
- Logs analysed (both already existed; nothing was re-run):
  - `task3/results/raw/optimization/task_queue_sweep_038_sequenced_smoke_seed20260911_3case.jsonl.gz` (seeds 20260911, 20260912, 20260913)
  - `task3/results/raw/optimization/task_queue_sweep_038_sequenced_seed20260911.jsonl.gz` (cross-check; identical 0911 numbers)
- Analysis script: `task3/experiments/audit_038_sequence_trace.py` (stdlib only, reads logs, imports no production module)
- Tables: `task3/results/tables/038_sequence_decision_trace.csv`,
  `038_resolve_preview_error.csv`, `038_sequence_plan_stability.csv`
- Reproduce:

```bash
python task3/experiments/audit_038_sequence_trace.py \
  task3/results/raw/optimization/task_queue_sweep_038_sequenced_smoke_seed20260911_3case.jsonl.gz \
  --seeds 20260911,20260912,20260913 --out-dir task3/results/tables
```

### Why the log can be trusted for this question

Two self-checks run on every case and both pass:

1. **Cost model.** Movement, switching, measurement, optical and laser time are
   reconstructed from the logged `task_action` records alone and compared with the
   run's own `time_breakdown`. All five components agree to 1e-6 s for all three
   seeds. Per-task costs quoted below are therefore measured, not estimated.
2. **Preview reconstruction.** Whenever the sequencer logged a resolve-only
   candidate for the task it then committed, that candidate's
   `estimated_end_position` is compared with the first executed action of that
   Resolve. **22 of 22 are bit-identical** (checked=matched for each seed:
   7/7, 8/8, 7/7). `TaskPreview.end_position` is therefore exactly the point of
   the Resolve's *next action*, and the tables can quote it directly.

---

## 1. Executive conclusion

The sequencer is not a short-horizon rollout. It is a permutation search over
frozen single-step proxies, and the proxies are the problem.

1. `TaskPreview.end_position` is the endpoint of the task's **next useful action**
   (`_resolve_preview` -> `_normal_resolve_action`, one tuple), not the Resolve's
   completion point.
2. In 33 of 48 Resolves the next action is `current_position_information` — a
   zero-travel measure at the robot's own pose. The preview therefore reports
   `end_position == current pose` and a cost of **5-6 s** for work that actually
   drives up to 1446 m.
3. Consequence: endpoint prediction error is mean 446-462 m, median 364-400 m,
   max 1446 m; cost prediction error is mean 70-93 s, max 347 s.
4. Later previews are frozen at the planning state: `evaluate` chains *position*
   and *channel* only. In 29-57% of the readable two-task prefixes the second
   task's preview endpoint sits **on the planning pose**, so the rollout's second
   leg is a phantom return trip. In 10-29% of two-task ordering comparisons the
   two orders cost **exactly** the same to the last bit and the tie is broken
   lexicographically by the label string.
5. The horizon collapses exactly where it is needed. `required_before_advance`
   contains ≥3 tasks in 24/38/42 decisions; no ≤2-prefix can cover them, every
   Advance-terminated candidate becomes infeasible, and the sequencer falls back
   to cheapest-single-task. In **all** of those decisions the chosen plan is one
   task. Same for the 19/7/3 decisions made after coverage completes. A genuine
   two-task plan is chosen in only 22/23/22 of 114/107/114 decisions.
6. Sequence instability is **0.0** — but that is guaranteed by construction, not
   evidence the rollout works. Once the first task completes, the second is the
   only task still satisfying `source_sector_rank <= frontier_rank`, and since any
   task inserted ahead of it only adds positive cost, the cheapest covering prefix
   necessarily starts with it. The alternatives that were on offer lose by exactly
   one measure plus one switch: 6.0 s or 7.0 s in 10 of the 11 plans.

---

## 2. Evidence summary

| Suspected cause | Result | Evidence |
|---|---|---|
| A. Preview models only the next action, not Resolve completion | **CONFIRMED** | `task_driven_controller.py:191-208` returns the point of one `_normal_resolve_action`; 22/22 bit-identical reconstruction check; 33/48 Resolves previewed as zero-travel measures with 5-6 s cost; endpoint error median 364-400 m, max 1445.6 m |
| B. Later task previews frozen at the pre-A state | **CONFIRMED** | `short_horizon_sequencer.py:70-101` chains `position` and `channel` only, never recomputes a preview; 29.2-57.1% of readable two-task prefixes have the second endpoint on the planning pose; 9.7-28.6% of pair orderings tie exactly; 0913 d=347 shows two orders at `306.73279873862407` s |
| C. `ready_resolves[:3]` hides useful candidates | **PARTIALLY CONFIRMED** | `task_driven_controller.py:223-226`; 99/114, 88/107, 90/114 decisions had READY > 3 and the top-3 slot was saturated in 72/67/82 of them; the ACTIVE Resolve also occupies a slot (52/47/48 decisions). But no excluded task was chosen within the next two replans (0 cases); median lag to being chosen was 42 replans. Its demonstrable harm is indirect: it helps make `required` unsatisfiable (see D) |
| D. `required_before_advance` mixes ready and not-ready tasks and exceeds the horizon | **CONFIRMED (new)** | `task_driven_controller.py:228-233` has no `ready` filter; `advance_blocked` in 24/38/42 decisions, and in 100% of them `required` provably has ≥3 members, so no ≤2-prefix can cover it. In all 104 of those decisions the chosen plan is a single task |
| E. Top-3 prefilter alone explains the detours | **REJECTED** | No excluded task was chosen soon after; the detours are explained by A and B |
| F. Sequence instability explains the detours | **REJECTED** | instability rate 0.0 for all three seeds; retention is structurally guaranteed by the `required` gate (section 5.4), so 0.0 measures determinism, not prediction |

---

## 3. Seed 20260911 forensic episodes

All coordinates in metres. `pose` is the robot position when the decision was taken.

### EP1 - decision 47, `select_active`, pose (1181.8, 208.4): the free-looking task

State: `frontier_rank` 0, 11 READY Resolves, top-3 saturated, `mode = advance_blocked`,
`required` has 3 members.

| candidate | estimated cost |
|---|---:|
| Resolve ch14 | **6.0** |
| Resolve ch8 | 36.0 |
| Resolve ch11 | 66.9 |
| Resolve ch14 -> Resolve ch8 | 42.0 |
| Resolve ch8 -> Resolve ch14 | 72.0 |
| all nine `... -> Advance V2` orders | infeasible (`would strand required task(s)`) |

Chosen: `Resolve ch14` at 6.0 s. PREVIEW: MEASURE ch14 at (1181.8, 208.4),
reason `current_position_information` - zero travel, 5 s measure + 1 s switch.

ACTUAL chain: `MEASURE current_position_information` (0 m) -> `CLEAR
certified_clear_point` at (1145.0, -130.0).

`endpoint_prediction_error_m` = **340.4**. Preview cost 6.0 s vs 85.1 s actually
consumed before the channel was cleared. The 340.4 m leg was booked to an
opportunistic ch11 measurement that happened to sit on the clear point, which is
why the main chain alone reads 11.0 s.

### EP2 - decision 74, `select_active`, pose (1715.0, 280.0): the chevron

Preview: MEASURE at pose, 6.0 s. Actual chain:

```
MEASURE ch8  (1715.0,  280.0) -> (1715.0,  280.0)   0.0  current_position_information
MEASURE ch8  (1715.0,  280.0) -> (1085.0,  323.3) 631.1  forward_route_measurement
MEASURE ch8  (1085.0,  323.3) -> ( 989.1,  437.6) 150.0  forward_route_measurement
MEASURE ch8  ( 989.1,  437.6) -> (1368.5,  842.1) 553.9  forward_center_measurement
CLEAR   ch8  (1368.5,  842.1) -> (1365.0,  850.0)   7.9  certified_clear_point
```

Path 1342.9 m for 668.9 m of net displacement (`within_task_detour_ratio` 2.01).
Endpoint error **668.9**. Cost 6.0 s predicted vs 294.6 s actual. The two
`forward_route_measurement` steps walk 781 m *away* along the sweep leg, then the
`forward_center_measurement` reverses 554 m to the real certificate centre. This
is the visible chevron.

### EP3 - decision 111, `select_active`, pose (410.4, 1127.6): literal out-and-back

Preview here was *honest* (`forward_center_measurement`, 95.9 s, endpoint
(672.5, 762.5)) - the reversal comes from the resolver, not the preview:

```
MEASURE ch15 (410.4, 1127.6) -> (672.5,  762.5) 449.4  forward_center_measurement
MEASURE ch15 (672.5,  762.5) -> (410.4, 1127.6) 449.4  forward_route_measurement
MEASURE ch15 (410.4, 1127.6) -> (587.5,  850.0) 329.3  forward_center_measurement
CLEAR   ch15 (587.5,  850.0) -> (587.5,  850.0)   0.0  near_immediate
```

Path 1228.2 m, net 329.3 m, ratio **3.73** - the robot returns exactly to the
point it left. Endpoint error 122.0; cost 95.9 s predicted vs 266.6 s actual.
The sequencer cannot see this: its preview only ever describes action 1.

### EP4 - decision 161, `select_active`, pose (-835.0, 547.5): inchworm then a 614 m jump

Preview: MEASURE at pose, 6.0 s. Actual: 7 actions - one zero-travel measure, four
~150 m `forward_route_measurement` steps along the leg (the `linspace(0,1,9)`
bucketing in `_forward_route_measurement`), then a 613.8 m
`forward_center_measurement` to (-1670.0, 240.0) and CLEAR at (-1685.0, 237.5).
Endpoint error **904.8** - the largest in this seed; cost 6.0 s vs 272.6 s.

### EP5 - decision 385, `select_active`, pose (1197.5, -912.5): the tie that decided the tail

By now `coverage_complete` (no Advance task left - `_next_vertex()` is None).

| candidate | cost |
|---|---:|
| Resolve ch4 | 6.0 |
| Resolve ch9 | 6.0 |
| Resolve ch18 | 90.66 |
| Resolve ch4 -> Resolve ch9 | 12.0 |
| Resolve ch9 -> Resolve ch4 | 12.0 |

`Resolve ch4` and `Resolve ch9` both preview as zero-travel measures at the same
pose and tie at exactly 6.0 s. `min(feasible, key=(cost, label))` breaks the tie
by **string comparison**; `"Resolve ch4" < "Resolve ch9"`, so ch4 is taken first.

Reality: ch4 completes at (17.5, -77.5), **1445.6 m** away; ch9 completes at
(697.5, -300.0), 709.3 m away. The sequencer had no information with which to
prefer either. The resulting tail is the long pink line from the lower-right into
the arena centre and back out: 2 -> 4 -> 9 -> 18 =
1445.6 + 709.3 + 898.3 m.

### EP6 - decision 143, `select_active`, pose (-771.3, 919.3): a frozen second step

Chosen plan `Resolve ch10 -> Resolve ch7 -> Advance V4`, cost 252.0 s. The second
task ch7's operative preview turned out to be a zero-travel measure at
(-835.0, 547.5) - the pose ch10 left behind - whereas the plan was formed at
(-771.3, 919.3). ch7's own endpoint error is 904.8 m. ch10 meanwhile was previewed
at 6.0 s and ran 100.6 s over 377.2 m with four actions.

---

## 4. Seed 20260913 forensic episodes

### EP1 - decision 125, `select_active`, pose (1358.4, 960.0): free-looking first, 590 m fold

10 READY, top-3 saturated, `mode = advance_blocked`, `required` has 3 members.

| candidate | cost |
|---|---:|
| Resolve ch7 | **6.0** |
| Resolve ch17 | 85.48 |
| Resolve ch3 | 152.80 |
| Resolve ch7 -> Resolve ch17 | 91.48 |
| Resolve ch17 -> Resolve ch7 | 171.96 |
| Resolve ch17 -> Resolve ch3 | 167.11 |
| Resolve ch3 -> Resolve ch17 | 233.43 |

Chosen `Resolve ch7` at 6.0 s. Actual:

```
MEASURE ch7  (1358.4,  960.0) -> (1358.4,  960.0)   0.0  current_position_information
MEASURE ch17 (1358.4,  960.0) -> ( 918.0,  929.4) 440.7  guaranteed_reception_useful_geometry  (opportunistic)
MEASURE ch7  ( 918.0,  929.4) -> ( 771.3,  919.3) 146.9  forward_route_measurement
CLEAR   ch7  ( 771.3,  919.3) -> (1082.5,  437.5) 573.5  certified_clear_point
```

Path 1161.1 m for 590.5 m net (ratio 1.97): west 587.6 m in two steps, then
573.5 m back east-north. Endpoint error **590.5**; 6.0 s predicted vs 255.2 s
actual. This is the crossing cluster around vertex V2 in the 0913 figure.

### EP2 - decision 347, `select_active`, pose (-140.0, -860.0): the two orders are identical

| candidate | cost |
|---|---:|
| Resolve ch15 -> Resolve ch16 -> Advance V6 | `306.73279873862407` |
| Resolve ch16 -> Resolve ch15 -> Advance V6 | `306.73279873862407` |

Both orderings cost **exactly** the same. When the rollout starts from a pose and
both previews are zero-travel measures at that same pose, every resolve leg is 0
and the pair is degenerate; `min(..., key=(cost, label))` again resolves it by the
label string, so ch15 goes first.

Consequence: the robot drives 1000.5 m south to ch15's clear at (370.0, -1717.5),
and then ch16 - whose own service point is (157.5, -337.5) - drives **1610.8 m
back north** (endpoint error 1396.3, the worst in this seed; 353.2 s). The whole
`15 -> 16` pair is a 2600 m out-and-back that the sequencer ordered on an
alphabetical tie-break.

### EP3 - decision 251, `select_active`, pose (-770.0, 507.5): a readable ordering, still wrong

`Resolve ch19 -> Resolve ch5 -> Advance V4` = 353.79 s vs
`Resolve ch5 -> Resolve ch19 -> Advance V4` = 499.93 s, so here the two previews
differ and the rollout does discriminate. It picks ch19 first, whose preview is a
zero-travel measure at the pose. ch19 then runs 5 actions and 1154.9 m to
(-1335.0, -372.5) with endpoint error **1045.8**; ch5, whose preview was an
accurate `certified_clear_point` at (-1187.5, 605.0) (error 0.0), is deferred.

### EP4 - decision 178, `select_active`, pose (-410.4, 1127.6): stale second step

Plan `Resolve ch13 -> Resolve ch2 -> Advance V3`, cost 252.0 s, second task ch2.
ch2's operative preview is a zero-travel measure at (-537.5, 875.0); planned at
(-410.4, 1127.6). ch13 runs 4 actions, 316.6 m, endpoint error 282.8; ch2 runs
4 actions, 251.0 m, endpoint error 215.0, both previewed at 6.0 s.

### EP5 - the 12/14/6 staircase and the 19/5 pair

`Resolve ch12` (preview 6.0 s) clears at (1002.5, 612.5); `Resolve ch14` (6.0 s)
at (1277.5, 907.5); `Resolve ch6` (6.0 s) at (1357.5, 960.0); then `Resolve ch7`
folds back to (1082.5, 437.5) as in EP1, then `Resolve ch17` clears at
(975.0, 1085.0) and `Resolve ch3` at (525.0, 1002.5). Six consecutive Resolves,
five of them previewed at 6.0 s, weaving north-east then back south-west. Actual
costs for the five: 112.1 + 138.0 + 48.2 + 255.2 + 136.3 + 109.4 = 799.2 s, against
30.0 s of summed preview.

### EP6 - `Resolve ch5`: the counter-example

The one task in this seed whose preview was a real travel action
(`certified_clear_point`, 202.7 s, single CLEAR action) is also the one with
endpoint error 0.0 and cost error 0.0. When the preview describes the *completion*
action instead of the *next* action, the prediction is exact. The defect is the
preview mode, not the cost model.

---

## 5. Quantitative diagnostics

### 5.1 Endpoint prediction error (preview end vs actual Resolve completion), metres

| seed | n | mean | median | P90 | max |
|---|---:|---:|---:|---:|---:|
| 20260911 | 16 | 446.1 | 400.1 | 904.8 | **1445.6** |
| 20260912 | 16 | 457.9 | 363.2 | 927.7 | 1245.6 |
| 20260913 | 16 | 461.9 | 393.7 | 1045.8 | 1396.3 |

Split by preview mode (all three seeds pooled, 48 Resolves):

| preview mode | n | median error | max error |
|---|---:|---:|---:|
| `current_position_information` | 33 | 553.2 | 1445.6 |
| `forward_center_measurement` | 7 | 17.7 | 299.7 |
| `certified_clear_point` | 5 | 0.0 | 0.0 |
| `forward_route_measurement` | 2 | 352.0 | 371.0 |
| `forward_service_approach` | 1 | 114.0 | 114.0 |

The error is concentrated entirely in one mode. Where the preview describes a
travel action it is accurate to within tens of metres; where it describes a
zero-travel measure it is off by hundreds.

### 5.2 Cost prediction error, seconds

Computed from logged movement, switch, measure, optical and laser time (model
validated against `time_breakdown`, section "Scope"). Preview cost is the cost of
the single previewed action; actual is the whole ACTIVE Resolve.

| seed | n | mean | median | P90 | max |
|---|---:|---:|---:|---:|---:|
| 20260911 | 16 | 92.8 | 47.4 | 266.6 | 288.6 |
| 20260912 | 16 | 69.8 | 37.8 | 198.3 | 215.4 |
| 20260913 | 16 | 88.8 | 54.2 | 210.1 | 347.2 |

### 5.3 Actions per Resolve: previewed 1, executed 2-7

`_resolve_preview` returns exactly one action by construction, so the previewed
count is always 1.

| seed | mean actual main actions | median | P90 | max |
|---|---:|---:|---:|---:|
| 20260911 | 3.63 | 3 | 7 | **7** |
| 20260912 | 2.94 | 3 | 4 | 6 |
| 20260913 | 3.06 | 3 | 5 | 6 |

### 5.4 Sequence instability

One row per committed Resolve, attributed to the last decision before it started.

| seed | two-task plans | changed after first task | instability rate |
|---|---:|---:|---:|
| 20260911 | 4 | 0 | **0.0** |
| 20260912 | 3 | 0 | **0.0** |
| 20260913 | 4 | 0 | **0.0** |

Instability is zero, but it carries no evidence of predictive value, and the
mechanism is visible in the follow-up candidate lists. Once the first task has run,
the second is the only task still satisfying `source_sector_rank <= frontier_rank`,
so it is the only one that must precede Advance. Any other task can still be
inserted ahead of it, but inserting one only adds positive cost, so the cheapest
covering prefix necessarily begins with the required task. Retention is therefore
structural.

The margins confirm it. In 10 of the 11 plans the follow-up re-selects the second
task over the alternative order by exactly **6.0 s or 7.0 s** - one measure plus
one channel switch:

| seed | plan | follow-up decision | chosen | next-best alternative | margin |
|---|---|---|---:|---:|---:|
| 0911 | `ch11 -> ch8 -> Advance V2` | 72 | `ch8` | `ch15 -> ch8` 323.15 | 6.0 |
| 0911 | `ch10 -> ch7 -> Advance V4` | 159 | `ch7` | `ch12 -> ch7` 178.33 | 6.0 |
| 0911 | `ch12 -> ch1 -> Advance V5` | 228 | `ch1` | `ch6 -> ch1` 435.06 | 7.0 |
| 0911 | `ch19 -> ch17 -> Advance V6` | 337 | `ch17` | `ch18 -> ch17` 164.42 | 6.0 |
| 0912 | `ch5 -> ch7 -> Advance V3` | 131 | `ch7` | `ch15 -> ch7` 412.14 | 7.0 |
| 0912 | `ch8 -> ch2 -> Advance V6` | 370 | `ch2` | `ch6 -> ch2` 570.53 | 6.0 |
| 0913 | `ch17 -> ch3 -> Advance V2` | 150 | `ch3` | `ch2 -> ch3` 297.63 | 6.0 |
| 0913 | `ch13 -> ch2 -> Advance V3` | 194 | `ch2` | `ch10 -> ch2` 197.42 | 6.0 |
| 0913 | `ch19 -> ch5 -> Advance V4` | 276 | `ch5` | `ch18 -> ch5` 524.72 | 6.0 |
| 0913 | `ch15 -> ch16 -> Advance V6` | 360 | `ch16` | `ch1 -> ch16` 354.72 | 6.0 |

The whole "sequence" comparison reduces to plus-or-minus the cost of a single
previewed action, which is the collapsed-preview cost itself. A metric of 0.0 here
measures determinism, not prediction.

### 5.5 How often the horizon is structurally inert

| mode | 0911 | 0912 | 0913 |
|---|---:|---:|---:|
| `advance_feasible` | 71 | 62 | 69 |
| `advance_blocked` (fallback -> single task) | 24 | 38 | 42 |
| `coverage_complete` (no Advance task) | 19 | 7 | 3 |
| decisions where a 2-task plan was chosen | 22 | 23 | 22 |
| decisions whose chosen plan is 1 resolve (`chosen_effective_steps == 1`) | 67 | 66 | 70 |
| decisions whose chosen plan is Advance only (`== 0`) | 25 | 18 | 22 |

`advance_blocked` means every Advance-terminated candidate was infeasible. In
**100%** of those decisions (24/24, 38/38, 42/42) `required_before_advance`
provably contained ≥3 tasks. Because the fallback branch compares resolve-only
prefixes and every extra task only adds positive cost, the argmin is always a
one-task plan: **0 of 104** blocked decisions chose more than one task.

### 5.6 Top-3 prefilter

| metric | 0911 | 0912 | 0913 |
|---|---:|---:|---:|
| decisions | 114 | 107 | 114 |
| decisions with READY > 3 | 99 | 88 | 90 |
| decisions where the top-3 slot was saturated | 72 | 67 | 82 |
| READY resolves never evaluated (upper bound; includes other sectors) | 440 | 293 | 486 |
| decisions where the ACTIVE Resolve occupied a slot | 52 | 47 | 48 |
| decisions where a *required* task was outside the candidate set | 4 | 20 | 25 |
| excluded task chosen within the next two replans | 0 | 0 | 0 |
| excluded task later chosen (any delay): count / median delay / max | 447 / 42 / 102 | — | 493 / 41 / 111 |

READY > 3 in ~85% of decisions, so the width-3 window is almost always binding.
But excluded tasks are not picked up soon after (median lag 42 replans), so the
prefilter is not the proximate cause of the visible detours. Its demonstrable
harm is that required tasks can fall outside the pool the sequencer evaluates,
which is one of the ways `required_before_advance` becomes unsatisfiable.

### 5.7 Where the driven distance goes

| seed | total in-task path | behind a collapsed preview | share | collapsed tasks |
|---|---:|---:|---:|---:|
| 20260911 | 12589.9 m | 8340.6 m | **66.2%** | 11 / 16 |
| 20260912 | 11216.6 m | 6796.2 m | **60.6%** | 9 / 16 |
| 20260913 | 10421.2 m | 8284.1 m | **79.5%** | 13 / 16 |

Logged previews sitting on the robot's current pose (`preview == pose`):

| seed | previews logged | at current pose | share |
|---|---:|---:|---:|
| 20260911 | 119 | 45 | 37.8% |
| 20260912 | 125 | 39 | 31.2% |
| 20260913 | 129 | 74 | 57.4% |

### 5.8 Frozen second steps

Two measurements over the resolve-only two-task prefixes, the only population
where the sequencer logs a second task's preview endpoint:

| seed | readable two-task prefixes | second preview on the planning pose | share |
|---|---:|---:|---:|
| 20260911 | 224 | 90 | 40.2% |
| 20260912 | 236 | 69 | 29.2% |
| 20260913 | 252 | 144 | 57.1% |

For those pairs the rollout's A->B leg is the distance from the planning pose to
A's endpoint - a phantom return trip that says nothing about B.

Pair orderings whose two orders cost **exactly** the same, so the decision is
made by the label string:

| seed | pair comparisons | exactly tied | share |
|---|---:|---:|---:|
| 20260911 | 77 | 19 | 24.7% |
| 20260912 | 62 | 6 | 9.7% |
| 20260913 | 84 | 24 | 28.6% |

---

## 6. Answers to the framing questions

**Q1. Does `TaskPreview.end_position` mean Resolve completion, or the next useful
action's endpoint?**
The next action's endpoint. `_resolve_preview` (`task_driven_controller.py:191-208`)
calls `_normal_resolve_action(channel)`, which returns a single
`(kind, point, reason, certified)` tuple, and takes `end_position = point`
(line 197/206). The docstring on `TaskPreview` says so directly ("Deterministic
proxy for the next useful action of a resolve task"). Log evidence: the 22/22
bit-identical check, plus 33 of 48 Resolves where the endpoint equals the robot's
own pose while the completion point is up to 1445.6 m away.

**Q2. Is the sequence's second task previewed against the post-A hypothetical
state?**
No. `_sequence_waiting` builds `previews` once (`task_driven_controller.py:224-227`)
and passes the frozen `TaskPreview` objects to `choose_short_horizon_sequence`.
Inside `evaluate` (`short_horizon_sequencer.py:70-101`) the loop carries only
`position` and `channel` forward (lines 81-82); `preview.end_position` and
`preview.operation_time_s` are read from the tuple and never recomputed. There is
no state object, no belief update, and no re-invocation of `_normal_resolve_action`.
Measured bias: 29.2-57.1% of readable two-task prefixes have the second endpoint on
the planning pose, and 9.7-28.6% of pair orderings tie exactly (0913 d=347:
`306.73279873862407` for both orders).

**Q3. How much of the visible detouring is explained by preview endpoint error and
sequence instability?**
Endpoint error explains most of it; sequence instability explains none of it.
Instability is 0.0 for all three seeds. 66.2% / 60.6% / 79.5% of all in-task
driven distance sits inside Resolves whose preview was a zero-travel measure.
Concrete episodes: 0911 EP1 (340.4 m error, 6.0 s -> 85.1 s), EP2 (chevron,
ratio 2.01), EP3 (out-and-back, ratio 3.73), EP4 (904.8 m error, 6.0 s -> 272.6 s),
EP5 (a 6.0 s dead heat resolved alphabetically, sending the robot 1445.6 m before
709.3 m back); 0913 EP1 (590.5 m error, ratio 1.97), EP2 (two identical costings,
then 1000.5 m south and 1610.8 m north), EP3 (1045.8 m error).

Two distinct mechanisms are at work and both are needed to explain the pictures:
(a) the preview collapse makes a far task look free, so it is scheduled early;
(b) the resolver's own chain (`forward_route_measurement` inchworming along the
sweep leg, then a long `forward_center_measurement` reversal) produces the
in-task zig-zags even when the preview was honest - 0911 EP3 is previewed
correctly at 95.9 s and still folds 1228 m over a 329 m net displacement.

**Q4. Does `ready_resolves[:3]` exclude tasks worth considering?**
Yes as a pool restriction, but the logs do not show it as the proximate cause.
The top-3 window is saturated in 72/67/82 of 114/107/114 decisions and READY
exceeds 3 in ~85% of them; the committed ACTIVE Resolve itself occupies a slot in
52/47/48 decisions (e.g. 0911 d=51, where candidates are exactly
`ch11, ch14, ch8` and `ch14` is the running ACTIVE task). Concrete exclusion
evidence: 4/20/25 decisions where a task named in a stranding reason was **not** in
the candidate set (0911 d=257 and 0912 d=160/166), i.e. the Advance gate referred
to a task the sequencer could not evaluate. Against that: 0 cases of an excluded
task being chosen within the next two replans, and a median lag of 42 replans
before an excluded task was chosen at all. So the prefilter costs coverage of the
candidate set - which feeds the unsatisfiable-`required` failure - rather than
directly selecting the wrong next task.

**Q5. Is the sequencer a real short-horizon rollout, or a permutation search over
single-step proxies?**
It is a permutation search over single-step proxies. Three independent proofs:
1. The proxies are frozen. `TaskPreview` is computed once per task per replan from
   the live state and never re-derived for any hypothetical successor state.
2. The "rollout" chains only position and channel, so the second task's cost is
   built from a preview that was never true for the state in which it would run.
3. It is structurally inert exactly where it is needed: in 43/45/45 of
   114/107/114 decisions (blocked + coverage-complete modes) the chosen plan is a
   single task, and in the 24/38/42 blocked decisions that is provably because
   `required` exceeds the horizon. A genuine two-task plan is chosen in 22/23/22
   decisions, and even there the label string decides the order 9.7-28.6% of the
   time.

Additionally, everything past the first element is discarded before it can act:
`_sequence_waiting` uses only `decision.chosen_task.identity` to set
`order_key=(-1,)` (`task_driven_controller.py:273-277`). The horizon can therefore
only influence *which task goes first*; it can never sequence the work that
follows.

---

## 7. Root cause ranking

1. **Resolve completion is predicted by the next single action.**
   `CONFIRMED`. `task_driven_controller.py:191-208`; 22/22 reconstruction check;
   `current_position_information` accounts for 33 of 48 previews at 5-6 s while
   the real tasks run 2-7 actions; endpoint error median 364-400 m, max 1445.6 m;
   66-80% of in-task distance sits behind a collapsed preview.
2. **Later previews are stale, and the rollout is position-only.**
   `CONFIRMED`. `short_horizon_sequencer.py:70-101`; 29-57% of readable two-task
   prefixes have the second endpoint on the planning pose; 9.7-28.6% of pair
   orderings tie exactly and are settled lexicographically.
3. **`required_before_advance` is unfiltered and exceeds the horizon, collapsing
   the sequencer to one step precisely when multi-step planning is needed.**
   `CONFIRMED`. `task_driven_controller.py:228-233` (no `ready` filter);
   `advance_blocked` in 24/38/42 decisions, all of them with `required` ≥ 3 and
   all of them choosing one task; plus 19/7/3 coverage-complete decisions.
4. **The top-3 prefilter and the ACTIVE task occupying a slot shrink the candidate
   pool, and can hide a task the Advance gate requires.**
   `PARTIALLY CONFIRMED`. `task_driven_controller.py:221-226`; top-3 saturated in
   72/67/82 decisions; ACTIVE occupies a slot in 52/47/48; 4/20/25 decisions with a
   stranded task outside the pool. No excluded-task-then-immediately-chosen case
   (0 of 0; median lag 42 replans), so this is not the direct cause of the detours.
5. **The resolver's own action chain produces in-task zig-zags even with an honest
   preview.** `CONFIRMED` as a contributing factor, out of scope for the sequencer.
   0911 EP3 (ratio 3.73, preview error only 122.0 m) and EP2's chevron; the
   four-step `forward_route_measurement` inchworm in 0911 EP4.
6. **Sequence instability abandons the plan's second step.**
   `REJECTED`. Instability rate 0.0 in all three seeds, and retention is
   structurally guaranteed once the `required` set shrinks to the second task
   (`required` items only add cost when reordered, so the follow-up's cheapest
   covering prefix always starts with the same task). This metric therefore cannot
   support the hypothesis that horizon-2 lacks predictive value; the case against
   horizon-2 rests on causes 1-3.
7. **The cost model or the time accounting is wrong.**
   `REJECTED`. The reconstructed five-component time model matches the run's
   `time_breakdown` to 1e-6 s on all three seeds.

---

## 8. Suggested next steps (not implemented)

Each item maps to the ranking above; none of this was written.

1. **For cause 1: give `TaskPreview` a completion-level meaning.** Predict the
   Resolve's termination point and its full remaining action chain, not its next
   action. The evidence is that `certified_clear_point` previews already have 0.0 m
   endpoint error (0913 EP6) - the accuracy is available whenever the preview
   describes the completion action. If a completion-level preview cannot be
   computed cheaply, the honest alternative is to admit the task's cost is unknown
   rather than report 6.0 s.
2. **For cause 2: state-aware rollout, not reused previews.** Re-derive each
   preview against a hypothetical successor state (position *and* the belief
   change the first task's measurements would produce), or restrict the horizon to
   1 and remove the second-step cost term. Either is defensible; what is not
   defensible is adding a second task's travel cost computed from a state that will
   not exist. The exact-cost ties (9.7-28.6%) show the current second step carries
   no information at all in a large minority of cases.
3. **For cause 3: fix the `required` set before touching the horizon.** The
   unfiltered `source_sector_rank <= frontier_rank` predicate over non-ready tasks
   is what makes the Advance gate unsatisfiable and silently converts the horizon
   to 1 in ~40% of decisions. Decide whether a non-ready task may block Advance at
   all; if it may, then both the horizon and the candidate pool have to see it.
4. **For cause 4: replace the old-`order_key` top-3 with a candidate generation
   step that is aware of what the gate needs.** At minimum, guarantee that every
   task in `required_before_advance` is in the evaluated set, and drop the ACTIVE
   task before slicing to three. Note that `required_before_advance` has no `ready`
   filter, so this is the same edit as cause 3 seen from the other side.
5. **For cause 5: treat the in-task chain separately.** The 150 m
   `forward_route_measurement` inchworm and the terminal
   `forward_center_measurement` reversal are resolver behaviour, not sequencing
   behaviour; they need their own audit before being blamed on the sequencer.
6. **Do not tune penalties or add guards first.** Causes 1-3 are representational.
   A penalty term would change which wrong estimate wins, not the fact that the
   estimate is wrong.

---

## 9. Files produced

| path | content |
|---|---|
| `task3/report/038_sequence_forensic_audit.md` | this report |
| `task3/experiments/audit_038_sequence_trace.py` | read-only analysis script (stdlib only) |
| `task3/results/tables/038_sequence_decision_trace.csv` | 335 decision rows: pose, mode, chosen plan, all candidate costs, exclusion bookkeeping |
| `task3/results/tables/038_resolve_preview_error.csv` | 48 Resolve rows: preview mode/endpoint/cost vs actual chain, endpoint and cost error, path/net/ratio |
| `task3/results/tables/038_sequence_plan_stability.csv` | 92 rows: plan vs follow-up choice, retention, second-step operative preview |
