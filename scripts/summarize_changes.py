#!/usr/bin/env python3
"""Write a short Markdown changelog of what a Humanizer rewrite changed.

Usage:
    python3 scripts/summarize_changes.py before.md after.md [--out summary.md]

Without --out, prints the summary to stdout. Meant to give a reader (or a
PR description) a quick account of what moved, without re-reading both
texts side by side.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from rewrite_quality import read_text, summarize  # noqa: E402


def main(argv: list[str]) -> int:
    if len(argv) not in (2, 4) or (len(argv) == 4 and argv[2] != "--out"):
        print(__doc__)
        return 1

    before_path, after_path = argv[0], argv[1]
    out_path = argv[3] if len(argv) == 4 else None

    before = read_text(before_path)
    after = read_text(after_path)
    summary = summarize(before, after)

    if out_path:
        Path(out_path).write_text(summary + "\n", encoding="utf-8")
        print(f"Wrote {out_path}")
    else:
        print(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
