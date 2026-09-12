# Candidate 038 — completion-level preview and local route sequencing (design)

Written before implementation, per the Stage 2A requirement.

1. **What the preview predicts.** For `ResolveSource`, where the task terminates
   and what the remaining work costs from here — not the next action.
2. **Endpoint.** `safe_clear_point()` when the certificate is already clearable,
   else `certificate().center`. Both are the points `_normal_resolve_action`
   itself drives to, so the endpoint is belief-derived, never ground truth.
3. **Cost.** Straight-line travel pose→endpoint at `speed_mps`, plus a channel
   switch when the remaining work measures the channel, plus the remaining
   operations: one measurement and the terminal optical+laser. Travel dominates;
   the operation term is a minimum, not a tuned penalty.
4. **Exact / estimated / unknown.** `EXACT` — the next action is the certified
   clear, so endpoint and cost are deterministic. `ESTIMATED` — endpoint comes
   from the certificate and is forward-compatible with the sweep frontier.
   `UNKNOWN` — no admissible endpoint (nothing forward of the frontier), so no
   completion claim at all.
5. **Second task.** Belief is strictly per-channel (`ChannelState.apply_observation`
   touches one channel, `_measure` touches one state), so A's completion cannot
   move B's certificate. What *is* predictable is recomputed: B's travel starts
   at A's endpoint, and B's switch is priced against the channel the robot holds
   after A. Nothing else is invented.
6. **Sequencing scope.** At most 3 eligible Resolves, fully ordered (≤6
   permutations), plus an optional trailing `AdvanceCoverage` positional term.
   Only Resolves that already precede Advance under the macro rule
   (`order_key < advance.order_key`) may be sequenced, so the CW/CCW sweep stays
   a hard constraint rather than a penalty term.
7. **Fallback.** Fewer than two trustworthy completions, or an unpriced leg ⇒ no
   rollout is fabricated: commitment reverts to Stage 1's `order_key`, and
   `AdvanceCoverage` (whose completion is unknown) can only end a sequence. A
   rollout is also refused when its predicted gain over the ordering `order_key`
   would have produced does not exceed the summed belief uncertainty of the
   endpoints that gain rests on — see `038_two_stage_completion_report.md`.
