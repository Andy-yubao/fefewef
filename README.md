# CUMCM 2026 Team Workspace

From Windows PowerShell:

```powershell
git clone https://github.com/Andy-yubao/CUMCM-2026.git
cd CUMCM-2026
.\scripts\setup.ps1
.\scripts\verify-environment.ps1
codex
```

Then run `/skills` in Codex and confirm that `kflow` and `math-modeling-skill` are available.

`setup.ps1` checks for Python 3.11 or newer, creates/reuses `.venv`, installs the bounded modeling dependencies and commit-pinned KFlow CLI, provisions the commit-pinned Math Modeling Skill locally, initializes KFlow only when necessary, and runs the environment verifier.

Run verification again at any time:

```powershell
.\scripts\verify-environment.ps1
```

## Repository-local Skills

- `.agents/skills/math-modeling-skill`: locally provisioned competition modeling workflow, case library, knowledge, templates, and code scaffolds.
- `.agents/skills/kflow`: rules for reading and maintaining important project knowledge through KFlow.

Start Codex from the repository root so it can discover `.agents/skills/`. The Math Modeling Skill is proprietary and is deliberately absent from this public repository's Git history. `setup.ps1` obtains the fixed upstream commit for authorized users, preserves its license/notice, removes nested Git metadata, and keeps the local copy ignored. Setup does not grant authorization or store credentials.

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
