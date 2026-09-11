# CUMCM Team Repository Rules

## Project goal

This is a shared repository for the CUMCM mathematical-modeling competition. Work may include problem interpretation, data analysis, mathematical modeling, algorithms, experiments, figures, paper writing, and result checking. Before the formal competition begins, limit work to infrastructure and preparation unless the user explicitly asks otherwise.

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

## GitHub network access (required for push/fetch)

GitHub over HTTPS is **not directly reachable from this machine**. Connecting to
`github.com:443` resets or times out (`Recv failure: Connection was reset`, or
`Failed to connect to github.com port 443`), even though DNS resolves normally and
`api.github.com` responds. Other hosts are unaffected — `arxiv.org` and general web
access work. The block is specific to GitHub.

A local HTTP proxy on port `10809` is the working route. Export it **inline**, for the
single command that needs it:

```bash
export HTTP_PROXY=http://127.0.0.1:10809
export HTTPS_PROXY=http://127.0.0.1:10809
export NO_PROXY=localhost,127.0.0.1,::1
git push origin main
```

Rules:

- **Never persist the proxy** via `git config http.proxy`, a shell profile, or a
  committed `.env`. Keep it inline and per-command. The repository must stay portable
  for teammates and for machines where no proxy exists or where the port differs.
- `NO_PROXY` must include `localhost` and `127.0.0.1`, otherwise local MCP servers and
  the competition simulator get routed through the proxy and fail.
- This proxy address is a loopback endpoint, **not a credential**, so it is safe to
  name in a tracked file. A proxy requiring authentication is different — that goes in
  `.env`, which is ignored.
- If a push or fetch fails, **report the raw error and stop**. Do not silently rewrite
  remotes, switch to SSH, or force-push. Ask the user for the current proxy settings.
- `git fetch` fails the same way, so ahead/behind counts computed while the proxy was
  unset may be **stale**. Re-run `git fetch` after a successful push before reporting
  sync status as verified.
- Confirm a push by exit code and by the `old..new  main -> main` line, not by absence
  of output.

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
