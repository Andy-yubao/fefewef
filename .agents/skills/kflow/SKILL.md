---
name: kflow
description: Use KFlow for repositories initialized with .kflow/project.json when tasks involve KFlow-managed knowledge, derivations, impact, review order, or confirmation state.
---

# KFlow Agent Skill

This repository pins KFlow at commit `2de99bb0b7caf864de3e837153893e4bb48d3c96`. Use only commands documented here for that version.

## Purpose and boundary

KFlow is external memory for the topology and impact range of important project files. It provides Nodes, complete Derivations, registered paths, status, review order, and validation issues. It does not read real files for you, perform mathematical reasoning, decide whether a conclusion is correct, or turn every file into managed knowledge.

Use KFlow only when `.kflow/project.json` exists and the task concerns managed knowledge. Do not silently initialize it, infer relationships, or register ordinary files.

## Choose queries by the information needed

- Unfamiliar project or multiple knowledge areas: `kflow overview -p`.
- Full graph with current status: `kflow overview --status -p`.
- Current review work: `kflow review-order [NODE]`.
- One Node's producer and direct consumers: `kflow context NODE -p`.
- Structural downstream range: `kflow impact NODE -p`.
- After actually checking one Node: `kflow confirm NODE`.
- Before finishing: `kflow review-order` and `kflow validate`.

Do not run every query mechanically. Use `-p`/`--prose` for semantic prose and `--json` only when stable fields are genuinely needed; they are mutually exclusive. A query should provide the minimum necessary structure, not dump the whole graph into context.

## What belongs in KFlow

Register complete files only when their durable knowledge is repeatedly used, has explicit derivation relationships, or requires downstream review when it changes. Examples may include formal problem interpretation, data-processing specifications, core model design, key assumptions, important experimental conclusions, and paper-critical conclusions.

Temporary drafts, caches, logs, build products, rebuildable outputs, bulk ordinary source files, and files connected only by topic normally remain unregistered. When uncertain, keep the file ordinary.

- New durable entity: `kflow node add NAME --file PATH [--file PATH ...]`.
- Replace a Node's complete name/files definition: `kflow node edit OLD --name NAME --file PATH [--file PATH ...]`.
- New explicit N-to-M derivation: `kflow derivation add` with complete roles.
- Replace a Derivation's name, short/detail, or complete roles: `kflow derivation edit`.
- Remove a stale relationship: `kflow derivation remove`.
- Remove an unreferenced Node that no longer belongs: `kflow node remove`.

`edit` is complete replacement: restate every file or role. If only a registered file's body changes and the entity definition is unchanged, do not call `edit`; inspect impact/context as needed, update the real file, validate it, and follow the review/confirm workflow.

## Interpret results correctly

- `overview -p` expresses each complete Derivation as inputs used to produce outputs and then maps Nodes to files. Standalone Nodes remain standalone.
- `context NODE -p` is one hop and preserves all roles in producer and consumer Derivations.
- `impact NODE -p` shows direct complete Derivations and further downstream Nodes in topological order.
- `review-order` lists only Nodes that still need checking. Reasons are `unconfirmed`, `files_changed`, `derivation_changed`, or `input_changed`; they identify a review condition, not a proven error.

Read only registered files needed for the current task. For a derived Node, check its producer and direct input conditions. Confirm a Node only after a real semantic check and relevant validation.

## Downstream confirmation is restricted

Normal `kflow confirm NODE` confirms one inspected Node and is the default.

`kflow confirm NODE --downstream` is an explicit batch assertion over the Node and every reachable downstream Node that still needs review. KFlow writes confirmations in stable topological order but makes no semantic judgment. The operation is not atomic: confirmations written before a failure remain.

Use `--downstream` only when the entire scope is already known to be mechanically affected without changes to meaning, interfaces, constraints, behavior, or conclusions—for example, a pure spelling/format/path rename—or when the entire scope has already been reviewed together.

Never use it for requirement, interface, architecture, algorithm, constraint, behavior, data-format, dependency, or potentially semantic changes. If you would need to open downstream Nodes individually to know they remain correct, use normal `review-order` plus single-Node `confirm`. Uncertainty means do not batch-confirm.

## Prohibited behavior

- Confirming without reading and checking the target files.
- Automatically cascading confirmations.
- Treating `affected` as proof of error or `current` as proof of correctness.
- Treating visual/prose output as a stable machine protocol.
- Auto-registering untracked files or asking KFlow to return file bodies, summaries, or prompts.
- Replacing explicit complete Derivations with inferred binary edges, similarity, or fixed relation labels.
