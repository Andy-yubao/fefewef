"""Write SHA-256 checksums for the exact offline implementation and artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", type=Path, default=Path("task3/results/raw/offline_manifest.json"))
    p.add_argument("--optimization", action="store_true",
                   help="include fixed-16 optimization raw files, tables, figures, and report")
    args = p.parse_args()
    paths = sorted(Path("task3/src").glob("*.py")) + [
        Path("task3/experiments/run_offline.py"),
        Path("task3/experiments/analyze_results.py"),
        Path("task3/requirements.txt"),
    ] + [path for pattern in (
        "task3/results/raw/offline_runs.jsonl.gz",
        "task3/results/tables/offline_*.csv",
        "task3/results/figures/offline_*.png",
    ) for path in sorted(Path().glob(pattern))]
    if args.optimization:
        paths += sorted(Path("task3/results/raw/optimization").glob("*"))
        paths += sorted(Path("task3/results/tables").glob("*_probe_*/**/*"))
        paths += sorted(Path("task3/results/figures").glob("*_probe_*/**/*"))
        paths += [Path("task3/report/strategy_optimization.md"), Path("task3/README.md"),
                  Path("task3/HANDOFF.md")]
    paths = [path for path in paths if path.is_file() and path != args.output]
    manifest = {str(path): {"sha256": digest(path), "bytes": path.stat().st_size} for path in paths}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
