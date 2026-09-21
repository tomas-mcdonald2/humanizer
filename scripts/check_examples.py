#!/usr/bin/env python3
"""Regression-test the tell scorer against SKILL.md's own before/after pairs.

SKILL.md embeds one or more before/after blockquote pairs under most of its
25 patterns. This script extracts them and checks that, for each pattern
with an automated matcher, the "after" text scores no higher than the
"before" text on that pattern. That keeps `tell_patterns.py` honest: if a
future edit to the matchers stops catching a tell SKILL.md itself
demonstrates, this fails loudly.

It is intentionally not a claim that the scorer detects every pattern
perfectly, only that it moves in the right direction on the skill's own
examples. A pattern with no automated matcher (currently #24) is reported
as skipped, not failed.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from tell_patterns import PATTERNS_BY_NUMBER, score_text  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SKILL_PATH = ROOT / "SKILL.md"

# Examples that need semantic judgment a regex cannot approximate without
# heavy false positives elsewhere (paragraph-scale patterns, mostly).
# Documented here instead of forced: kept visible, not silently ignored.
KNOWN_LIMITATIONS = {
    (6, "A career can look promising and fail."): (
        "paragraph-scale triad (three parallel sentences, no literal list)"
    ),
}

HEADING_RE = re.compile(r"(?m)^### (\d+)\. ")
PAIR_RE = re.compile(
    r"\*\*Before[^*\n]*\*\*\s*\n((?:^>.*\n?)+)\s*\*\*After[^*\n]*\*\*\s*\n((?:^>.*\n?)+)",
    re.MULTILINE,
)


def dequote(block: str) -> str:
    lines = [re.sub(r"^>\s?", "", line) for line in block.splitlines()]
    return "\n".join(lines).strip()


def extract_pairs(skill_text: str) -> list[tuple[int, str, str]]:
    headings = [(int(m.group(1)), m.start()) for m in HEADING_RE.finditer(skill_text)]
    headings.append((None, len(skill_text)))

    pairs: list[tuple[int, str, str]] = []
    for (number, start), (_, end) in zip(headings, headings[1:]):
        section = skill_text[start:end]
        for match in PAIR_RE.finditer(section):
            before = dequote(match.group(1))
            after = dequote(match.group(2))
            pairs.append((number, before, after))
    return pairs


def main() -> int:
    skill_text = SKILL_PATH.read_text(encoding="utf-8")
    pairs = extract_pairs(skill_text)
    if not pairs:
        print("No before/after pairs found in SKILL.md", file=sys.stderr)
        return 1

    failures: list[str] = []
    skipped: list[int] = []
    known_limitations: list[str] = []
    checked = 0

    for number, before, after in pairs:
        pattern = PATTERNS_BY_NUMBER.get(number)
        if pattern is None:
            if number not in skipped:
                skipped.append(number)
            continue

        limitation_key = next(
            (key for (n, key) in KNOWN_LIMITATIONS if n == number and before.startswith(key)),
            None,
        )
        if limitation_key is not None:
            known_limitations.append(
                f"§{number} {pattern.title}: {KNOWN_LIMITATIONS[(number, limitation_key)]}"
            )
            continue

        checked += 1
        before_count = score_text(before).count(number)
        after_count = score_text(after).count(number)
        if after_count > before_count:
            failures.append(
                f"§{number} {pattern.title}: after-score {after_count} > "
                f"before-score {before_count}\n  before: {before[:100]!r}\n  after:  {after[:100]!r}"
            )
        elif before_count == 0:
            failures.append(
                f"§{number} {pattern.title}: matcher did not fire on the "
                f"skill's own 'before' example\n  before: {before[:100]!r}"
            )

    print(f"Checked {checked} example pair(s) across {len(pairs)} total.")
    if skipped:
        print(f"Skipped (no automated matcher): {', '.join('§' + str(n) for n in sorted(skipped))}")
    if known_limitations:
        print("Known limitations (not scored, documented):")
        for line in known_limitations:
            print(f"  - {line}")

    if failures:
        print(f"\n{len(failures)} failure(s):\n")
        print("\n\n".join(failures))
        return 1

    print("All automated patterns score before >= after on SKILL.md's own examples.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
