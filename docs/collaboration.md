# Lightweight Git Collaboration

Use a simple branch model suited to a time-limited competition:

```text
main
├─ model/...
├─ data/...
├─ paper/...
└─ fix/...
```

- Keep `main` basically runnable and reproducible.
- Use short-lived feature branches for substantial model, data, and paper changes.
- Small urgent fixes may be handled directly only according to the team's current agreement.
- Before pushing, pull/rebase as agreed and resolve conflicts intentionally.
- Never force-push when another member's work may be overwritten.
- Do not commit secrets, local environments, caches, unrelated large binaries, or anything under `prompt/`.
- For important experiments, record the command, input version, configuration/seed, and result location.
- Prefer focused commits whose purpose is clear from the subject.
