"""Export the printable code appendix from the canonical release source."""
from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / "paper_appendix_sources.txt"
OUTPUT = ROOT / "paper_appendix" / "code_appendix.md"


def main() -> None:
    files = [Path(line.strip()) for line in MANIFEST.read_text(encoding="utf-8").splitlines()
             if line.strip() and not line.startswith("#")]
    missing = [str(path) for path in files if not (ROOT / path).is_file()]
    if missing:
        raise FileNotFoundError("missing appendix source: " + ", ".join(missing))

    sections = [
        "# 附录：建模所用完整源程序",
        "",
        "本文件由 submission_release/make_paper_appendix.py 从冻结源代码生成。",
        "代码、数据和结果的文件清单见 MANIFEST.csv。",
        "",
    ]
    for path in files:
        suffix = path.suffix.lstrip(".") or "text"
        sections.extend([
            f"## {path}",
            "",
            f"```{suffix}",
            (ROOT / path).read_text(encoding="utf-8"),
            "```",
            "",
        ])
    OUTPUT.parent.mkdir(exist_ok=True)
    OUTPUT.write_text("\n".join(sections), encoding="utf-8")
    print(f"wrote {OUTPUT} ({len(files)} source files)")


if __name__ == "__main__":
    main()
