# Reviewer Playbook

Use this playbook during substantive review. Report only supported, decision-relevant findings; these are diagnostic prompts, not a requirement to manufacture one issue per reviewer.

## 1. Judge / Triage

Read the summary and structural signposts as a time-limited judge would. Ask whether the paper's main contribution, answer to the prompt, and reason to keep reading are immediately visible. Flag a confusing main line, contribution buried under machinery, or complexity disproportionate to what is delivered. Leave detailed coverage, mathematics, and layout diagnoses to their owners.

## 2. Requirement Coverage

Extract explicit tasks before judging the paper. Preserve nested asks: a request to construct, validate, compare, and recommend may create several independently checkable requirements. For each requirement, locate method, evidence/result, and conclusion. Typical failures are total omission, a proposed model without output, a result without the requested interpretation, and prose that gestures toward a task without completing it.

## 3. Executive Summary — elevated attention

Judge the summary as a standalone decision document for a non-specialist evaluator. Check that it identifies the actual problem, explains the approach beyond model-name listing, gives concrete key values or comparisons, and states the final recommendation or answer. Detect excess prompt restatement, implementation detail that displaces results, and disagreement with the body.

## 4. Model Logic

Follow `Assumptions → Variables → Parameters → Model → Computation → Results → Conclusion`. Check whether assumptions enter the equations, symbols and units remain stable, parameter sources and ranges are plausible, objective and constraints match the task, the prose and mathematics describe the same operation, outputs respect declared domains, and conclusions stay within what the model establishes. Report obvious contradictions; do not claim exhaustive proof or theory verification.

## 5. Model Cohesion & Integration — elevated attention

For every model, write down its input, output, downstream consumer, and contribution to a requirement. Ask whether Model A's output enters Model B, why B needs A, and how all local conclusions reach the final answer. Flag parallel model stacking, unused intermediate outputs, independent chapter conclusions without synthesis, unexplained conflicts, and models removable without changing the solution.

## 6. Robustness — sensitivity receives elevated attention

Identify assumptions, data, and parameters with the greatest leverage on the final ranking, policy, forecast, or recommendation. Check whether the paper explains why those factors were tested, uses defensible perturbation ranges, and reports whether core decisions change—not merely whether plotted values move. Check proportionally for uncertainty, measurement/estimation error, validation, stability, and failure boundaries. Do not mechanically demand every method for every model.

## 7. Appropriate Explanation — elevated attention

Locate consequential choices of parameter values, data inclusion/exclusion, cleaning, normalization, model family, indicators, weights, thresholds, initial/boundary conditions, evaluation metrics, objective, and classification. Ask why each choice fits the task and how changing it could affect the result. Do not demand lengthy explanations for routine operations with no meaningful decision impact.

## 8. Visual Communication

Use the rendered PDF and the visual guide. Inspect hierarchy; figure/table legibility and takeaways; caption, axis, unit, legend, precision, and color clarity; page density and whitespace; float placement, breaks, overflow, image quality, and font size; and consistency of notation and visual styling. Confirm that prose explains important visuals. Do not recommend decoration that harms density or clarity.

## Duplicate handling

Assign a finding to the reviewer that owns the root cause. For example, an unsupported “robust” claim belongs primarily to Robustness and may cite the Claim → Evidence cross-check; do not repeat it as separate Robustness, Summary, and Explanation findings. Mention downstream effects within one finding.
