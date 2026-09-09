# CUMCM 2026 Team Workspace

From Windows PowerShell:

```powershell
git clone https://github.com/Andy-yubao/CUMCM-2026.git
cd CUMCM-2026
.\scripts\setup.ps1
.\scripts\verify-environment.ps1
codex
```

Then run `/skills` in Codex and confirm that `kflow`, `math-modeling-skill`, and `math-modeling-review` are available.

`setup.ps1` checks for Python 3.11 or newer, creates/reuses `.venv`, installs the bounded modeling dependencies and commit-pinned KFlow CLI, provisions the commit-pinned Math Modeling Skill locally, initializes KFlow only when necessary, and runs the environment verifier.

Run verification again at any time:

```powershell
.\scripts\verify-environment.ps1
```

## Repository-local Skills

- `.agents/skills/math-modeling-skill`: locally provisioned support for problem interpretation, model selection, modeling workflow, experiments, algorithms, and general competition problem solving.
- `.agents/skills/math-modeling-review`: repository-tracked near-final paper reviewer for requirement coverage, summary quality, model logic and integration, robustness, explanation, rendered-PDF communication, and prioritized submission checks. It is not a modeling solver or automatic paper editor.
- `.agents/skills/kflow`: rules for maintaining durable project knowledge, derivations, impact relationships, review order, and confirmation state through KFlow.

Start Codex from the repository root so it can discover `.agents/skills/`. The Math Modeling Skill is proprietary and is deliberately absent from this public repository's Git history. `setup.ps1` obtains the fixed upstream commit for authorized users, preserves its license/notice, removes nested Git metadata, and keeps the local copy ignored. Setup does not grant authorization or store credentials.

These three skills are optional and must never be invoked automatically. Before using any one of them, Codex must explain why it may help and ask the user for permission; explicit agreement is required for the current task. Do not load all three mechanically.

Minimal review request after agreeing to use the review skill:

```text
Use $math-modeling-review.

Problem statement: problem/...
Final paper PDF: paper/...
Optional team feedback: ...
```

The review output contains `Overall Verdict`, `Prioritized Findings`, `Eight-Reviewer Summary`, and `Top 5 Fixes Before Submission`.

## KFlow

KFlow records durable knowledge nodes, explicit derivations, review state, and impact relationships under `.kflow/`. Project facts are version-controlled; disposable runtime state is ignored. KFlow does not replace reading files or doing mathematical reasoning, and ordinary files should not be registered automatically.

## Main directories

| Path | Purpose |
| --- | --- |
| `problem/` | Original problem and attachments |
| `data/` | Data and provenance notes |
| `code/` | Reproducible code |
| `models/` | Model definitions and derivations |
| `experiments/` | Experiment scripts and configs |
| `results/` | Reproducible outputs |
| `figures/` | Final figures |
| `paper/` | Paper and submission materials |
| `docs/` | Durable project documentation |

## Git collaboration

Keep `main` basically runnable. Use short-lived `model/...`, `data/...`, `paper/...`, or `fix/...` branches for larger work, synchronize before pushing, resolve conflicts deliberately, and never force-push over work you do not understand. Do not commit `.venv`, secrets, caches, or `prompt/`. See `docs/collaboration.md`.
