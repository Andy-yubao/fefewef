"""Attach the GUI-revealed source total to an already completed practice summary."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--summary", type=Path, required=True)
    p.add_argument("--total", type=int, required=True)
    args = p.parse_args()
    if not 10 <= args.total <= 16:
        raise SystemExit("problem-3 total must be in [10, 16]")
    data = json.loads(args.summary.read_text(encoding="utf-8"))
    cleared = int(data["cleared_count"])
    data["known_total"] = args.total
    data["clear_ratio"] = cleared / args.total
    args.summary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"cleared_count": cleared, "known_total": args.total,
                      "clear_ratio": data["clear_ratio"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()

