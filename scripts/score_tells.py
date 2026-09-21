#!/usr/bin/env python3
"""Score a text file for Humanizer's numbered AI-writing tells.

Usage:
    python3 scripts/score_tells.py file1.md [file2.md ...]

This is a heuristic approximation, not the skill itself; see
`tell_patterns.py` for what it can and cannot detect. Useful on its own to
spot-check a draft, but most useful paired with `compare_rewrite.py` on a
before/after pair.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from tell_patterns import PATTERNS, score_text  # noqa: E402


def report(path: str) -> None:
    text = Path(path).read_text(encoding="utf-8")
    result = score_text(text)
    print(f"\n{path}")
    print("-" * len(path))
    if not result.counts:
        print("  No tells detected.")
    for pattern in PATTERNS:
        count = result.count(pattern.number)
        if count:
            tag = f" [{pattern.tier}]" if pattern.tier != "moderate" else ""
            print(f"  §{pattern.number:>2} {pattern.title}{tag}: {count}")
    print(f"  Total weighted score: {result.total():.1f}  (strong hits: {result.strong_hits()})")


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 1
    for path in argv:
        report(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
