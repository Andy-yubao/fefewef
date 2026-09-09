---
name: math-modeling-review
description: Review a near-final mathematical-modeling competition paper against its official problem statement and rendered submission, producing evidence-backed, prioritized fixes. Use for CUMCM, MCM/ICM, and similar modeling-report self-review; do not use as a modeling solver, paper writer, or automatic editor.
---

# Math Modeling Review

Deliver a compact pre-submission review that helps a competition team fix the few issues most likely to affect judging. Optimize for specific evidence, actionable repairs, and competition outcome rather than academic verbosity.

## Establish the evidence base

Identify these inputs before reviewing:

1. **Problem Statement — required.** Treat the official prompt as the only authority for the requested tasks.
2. **Final Paper — required.** Prefer the final rendered PDF. Treat that rendering as the authority for visual presentation; use `.tex`, `.md`, or `.docx` only as supporting content.
3. **Team Historical Feedback — optional.** Read static feedback when supplied. Use it to raise attention, never to pre-judge the current paper.

Record useful location anchors while reading: PDF page, section/subsection, paragraph opening, equation, figure, or table. Do not invent a location, requirement, paper defect, result, or causal explanation. Distinguish direct observation from inference, and write `Unclear from the provided material` when the evidence cannot resolve a point.

If the problem statement is absent, continue with the supported perspectives and state verbatim:

> Requirement Coverage cannot be completed reliably without the problem statement.

Do not infer the complete task from the paper. If the rendered PDF is absent, continue from the available source or text and state verbatim:

> Visual Communication review is incomplete because the final rendered paper was not provided.

Do not turn extracted text into claims about layout. Missing historical feedback is not an error.

Before substantive review, read [knowledge/review-principles.md](knowledge/review-principles.md) and [knowledge/team-risk-profile.md](knowledge/team-risk-profile.md). When a rendered PDF is available, also read [knowledge/visual-review-guide.md](knowledge/visual-review-guide.md). Use [templates/review-output-template.md](templates/review-output-template.md) when composing the report.

## Build requirement traceability first

When the problem statement is available, extract each explicit deliverable or task as a checkable requirement `R1`, `R2`, `R3`, and so on. Preserve important qualifiers such as scenario, metric, time horizon, comparison, justification, or requested recommendation.

For every requirement, build this mapping:

```text
Requirement → Paper Location → Method / Model → Evidence / Result → Conclusion → Coverage Status
```

Use only `Complete`, `Partial`, `Missing`, or `Unclear`. A method without a result is not complete. A result that is not translated into the requested answer or recommendation is not complete. Cite the mapping in a relevant finding or concise supporting table when a broken link matters.

## Apply the eight fixed perspectives

Apply all eight; do not add, remove, split, or score them. Read [references/reviewer-playbook.md](references/reviewer-playbook.md) for the detailed checks and boundaries.

1. **Judge / Triage** — assess first impression, rapid comprehension, visible response to the prompt, coherent main line, and the most likely reason a time-limited judge would downgrade the paper.
2. **Requirement Coverage** — assess every extracted requirement and whether the paper supplies a method, evidence, and actual answer.
3. **Executive Summary** — assess whether the summary alone conveys the problem, approach, specific key results, and final conclusions consistently with the paper.
4. **Model Logic** — test the chain `Assumptions → Variables → Parameters → Model → Computation → Results → Conclusion` for evident contradictions, unit/range errors, and unsupported inference.
5. **Model Cohesion & Integration** — test why each model exists, how outputs flow between models, and how local results combine into the overall solution.
6. **Robustness** — focus proportionally on consequential sensitivity, uncertainty, validation, error, stability, and failure boundaries; do not demand every technique for every model.
7. **Appropriate Explanation** — challenge consequential choices that say what was done but not why it fits the task, data, or model.
8. **Visual Communication** — inspect the final rendering for hierarchy, figures/tables, layout, legibility, and consistency. Prefer clarity and information transfer over decoration.

Give elevated attention—not an automatic negative finding—to Executive Summary, Model Cohesion & Integration, Sensitivity Analysis within Robustness, and Appropriate Explanations. Do not exempt model selection, model implementation, or tables and figures because they were historical strengths.

## Run exactly two cross-checks

### A. Problem → Model → Evidence → Conclusion

Trace each important requirement through the method, reported result, and final answer. Report consequential breaks such as a result with no conclusion, a recommendation with no model evidence, or a model that serves no requirement.

### B. Claim → Evidence

Audit only important claims, such as superiority, robustness, insensitivity, savings, or generalizability. Locate the supporting comparison, experiment, sensitivity result, validation, or calculation. If support is absent or weaker than the wording, identify the exact claim and propose the smallest repair: add evidence, narrow the wording, quantify uncertainty, or qualify the scope.

## Form findings

Consolidate duplicate reviewer observations around the root cause. Retain issues that change task completion, judge comprehension, model credibility, conclusion support, or professional readability; omit low-value reviewer dump.

Every substantive finding must contain:

```text
[HIGH | MEDIUM | LOW] Category
Location:
Problem:
Why it matters:
Evidence:
Recommended fix:
```

Use only these severities:

- `HIGH`: likely to materially affect task completion, judge comprehension, model credibility, a core conclusion, or overall evaluation.
- `MEDIUM`: does not break the core answer but materially weakens logic, credibility, clarity, or completeness.
- `LOW`: localized expression, visual consistency, readability, or non-core detail.

Do not use vague advice such as “improve robustness” or “make figures better.” Name the affected parameter, claim, result, section, figure, or decision; explain the evidence gap; and specify a feasible edit or test. If a fix would require new analysis, say exactly what to perturb, compare, calculate, or report without fabricating the outcome.

Order findings and final fixes by likely impact and practical repair cost, using `Impact / Fix Cost` as a judgment aid rather than a numeric formula. A fast MEDIUM repair may precede a prohibitively expensive HIGH repair. Preserve the finding's true severity even when priority differs.

## Produce the fixed report

Write in the user's requested language, or the paper's language if no preference is given. Use exactly these four top-level sections:

1. **Overall Verdict** — two to five concise paragraphs covering overall quality, strongest aspect, largest risk, likely point of lost credit, and any submission-level danger.
2. **Prioritized Findings** — only decision-relevant findings, ordered by action priority and using the mandatory fields.
3. **Eight-Reviewer Summary** — list all eight fixed perspectives, each with one of `Strong`, `Acceptable`, `Needs Attention`, or `Weak`, plus concise evidence-based conclusions. Mark unsupported perspectives incomplete rather than pretending they were performed.
4. **Top 5 Fixes Before Submission** — zero to five concrete actions. Never exceed five. Each action identifies the edit/test, its target location, and the expected decision benefit.

Do not append reviewer transcripts, complex scores, or extra report sections. A short requirement traceability table may appear inside `Prioritized Findings` when it is the clearest evidence for a coverage problem.

## V1 boundaries

Do not solve the modeling problem, automatically rewrite or modify the paper, repair LaTeX/PDF, predict awards, detect plagiarism or AI use, create review modes, orchestrate models or agents, build a feedback database or learned team profile, certify all proofs/PDEs/convergence/statistical theory, perform a complete code-paper consistency audit, or conduct deep citation-authenticity research. State mathematical-verification limits when they materially affect confidence.
