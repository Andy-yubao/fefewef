# Tooling Sources

Last updated: 2026-09-09

## Math Modeling Skill

- Upstream: https://github.com/skillforCUMCM/math-modeling-skill-pro
- Pinned commit: `88e97054bddc789239b66b38485469d5d1b6e09e`
- Latest tag visible at selection time: `v1.0.0` (the pin intentionally uses the later reviewed `main` commit above)
- Provisioning: `scripts/setup.ps1`
- Runtime local path: `.agents/skills/math-modeling-skill`
- Git tracked: **NO**
- License: proprietary; setup preserves LICENSE and THIRD-PARTY-NOTICE in the ignored local copy. Access and use require upstream authorization; no credentials are stored in this repository.

## KFlow

- Upstream: https://github.com/Andy-yubao/KFlow
- Pinned commit: `2de99bb0b7caf864de3e837153893e4bb48d3c96`
- CLI installation: `requirements-tools.txt`
- Skill path: `.agents/skills/kflow`
- Selection basis: a committed `main` HEAD matching the existing `origin/main` ref. No uncommitted KFlow working-tree content was used.

## MathModelingReview

- Upstream: https://github.com/Andy-yubao/MathModelingReview
- Pinned deployment source: `0e3828d88395f6eabf3842b284ce5f494c23880d`
- Runtime path: `.agents/skills/math-modeling-review`
- Git tracked: **YES**
- Purpose: near-final mathematical-modeling competition paper self-review.
- Deployment: copied from the fixed reviewed commit and available without dynamic upstream access during the competition.
