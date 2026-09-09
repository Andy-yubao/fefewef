# CUMCM Team Repository Rules

## Project goal

This is a shared repository for the CUMCM mathematical-modeling competition. Work may include problem interpretation, data analysis, mathematical modeling, algorithms, experiments, figures, paper writing, and result checking. Before the formal competition begins, limit work to infrastructure and preparation unless the user explicitly asks otherwise.

## Skills

- For substantive mathematical-modeling work, consider `$math-modeling-skill` first.
- When `.kflow/project.json` exists and a task involves managed knowledge, derivations, impact, review order, or confirmation state, follow `$kflow`.
- Do not invoke both mechanically. Load only the skill that materially helps the task.
- Repository-local skills live under `.agents/skills/`; do not depend on or modify user-level Codex skills.
- `math-modeling-skill` is provisioned locally by `scripts/setup.ps1` and must remain ignored; never add its proprietary contents to Git.

## Modeling discipline

Do not choose a model reflexively, invent missing data, turn correlation into causation, add complexity for its own sake, report metrics without validation, or give conclusions without reproducible code and data support. Important claims should remain traceable through:

`problem/data -> assumptions -> model -> implementation -> experiment -> conclusion`

Define the evidence boundary, compare defensible alternatives, check assumptions, and match validation to the claim being made.

## Team collaboration

- Check Git status before editing and preserve other members' uncommitted work.
- Do not delete unknown files or perform broad refactors outside the task boundary.
- Never commit secrets, credentials, local environments, caches, or machine-specific runtime state.
- Keep commits focused and avoid force-pushing over work you do not fully understand.
- `prompt/` is temporary user input: never track, commit, move, or delete it.
- Record important experiment commands, configuration, seeds, and output locations.

## Directory responsibilities

- `problem/`: original problem statements and attachments.
- `data/`: source/processed data plus provenance and processing notes.
- `code/`: formal reproducible code.
- `models/`: model definitions, derivations, and core implementations.
- `experiments/`: experiment scripts and configurations.
- `results/`: reproducible numerical outputs.
- `figures/`: publication-ready figures.
- `paper/`: manuscript and final submission materials.
- `docs/`: durable project and process documentation.

Keep transient scratch files and caches out of formal directories.

## KFlow boundaries

KFlow stores only durable knowledge whose origin and downstream impact are worth maintaining: formal problem interpretation, data-processing specifications, core model design, key assumptions, important experimental conclusions, paper-critical conclusions, and decisions with explicit downstream effects.

Do not register a file merely because it exists. Caches, temporary scripts, one-off screenshots, debugging output, download caches, and rebuildable artifacts normally remain ordinary files. KFlow supplies topology and status; the agent must still read, reason about, edit, and validate the real files.
