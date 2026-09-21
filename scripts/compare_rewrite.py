#!/usr/bin/env python3
"""Compare a before/after pair and report whether the rewrite held up.

Usage:
    python3 scripts/compare_rewrite.py before.md after.md

Prints a per-pattern delta table, flags any pattern that went up instead of
down, flags any strong (single-sighting) tell still present after the
rewrite, and checks that standalone numbers and quoted spans from the
original survive into the rewrite. Exits 1 if any of those checks fail, so
it can gate a CI step or a pre-commit hook if you want that; the normal use
is just reading the printed report after running the skill by hand.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from rewrite_quality import compare, read_text  # noqa: E402


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__)
        return 1

    before_path, after_path = argv
    before = read_text(before_path)
    after = read_text(after_path)
    comparison = compare(before, after)

    print(f"before: {before_path}")
    print(f"after:  {after_path}\n")
    print(f"{'#':>3}  {'pattern':<40} {'before':>7} {'after':>6} {'Δ':>5}")
    for d in comparison.deltas:
        marker = " ⚠" if d.delta > 0 else ""
        print(f"§{d.number:>2}  {d.title:<40} {d.before:>7} {d.after:>6} {d.delta:>5}{marker}")

    before_total = comparison.before_score.total()
    after_total = comparison.after_score.total()
    print(f"\nWeighted total: {before_total:.1f} → {after_total:.1f}")

    if comparison.regressions:
        print("\n⚠ Patterns that increased:")
        for d in comparison.regressions:
            print(f"  §{d.number} {d.title}: {d.before} → {d.after}")

    if comparison.remaining_strong:
        print("\n⚠ Strong tells (§1-5) still present after the rewrite:")
        for d in comparison.remaining_strong:
            print(f"  §{d.number} {d.title}: {d.after} occurrence(s)")

    if comparison.facts.clean:
        print("\nFacts check: no standalone numbers or quotes from the original are missing.")
    else:
        print("\n⚠ Facts check: possibly dropped from the original:")
        for n in comparison.facts.missing_numbers:
            print(f"  number: {n}")
        for q in comparison.facts.missing_quotes:
            print(f'  quote: "{q}"')

    print(f"\nVerdict: {'PASS' if comparison.passed else 'WARN'}")
    return 0 if comparison.passed else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
