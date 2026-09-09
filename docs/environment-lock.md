# Pre-competition Environment Lock

Last verified: 2026-09-09

- Python minimum: 3.11
- KFlow pinned commit: `2de99bb0b7caf864de3e837153893e4bb48d3c96`
- Math Modeling Skill pinned commit: `88e97054bddc789239b66b38485469d5d1b6e09e` (locally provisioned by `scripts/setup.ps1`, never Git-tracked here)
- MathModelingReview deployed source commit: `0e3828d88395f6eabf3842b284ce5f494c23880d` (tracked directly in this repository)
- Important Python requirements: NumPy, pandas, SciPy, Matplotlib, scikit-learn, NetworkX, openpyxl, and PyYAML, bounded in `requirements.txt`.

After the competition starts, do not upgrade KFlow, the provisioned Math Modeling Skill, MathModelingReview, or foundational dependencies unless a clearly identified blocking problem requires it. Record and validate any necessary change before sharing it with the team.
