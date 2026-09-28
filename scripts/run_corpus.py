#!/usr/bin/env python3
"""Score saved rewrites of the fixed corpus and compare skill versions.

Usage:
    python3 scripts/run_corpus.py tests/rewrite-corpus OUT_DIR [OUT_DIR ...]

Each OUT_DIR holds one rewrite per corpus draft, with the same file name
(for example `out/old-run1/travel-blog.md`). Files ending in `.context.md`
are background for the rewriter, not drafts, so they are skipped.

This script does not run the skill. Produce the rewrites first, with the
same agent and model for every OUT_DIR, then run this to compare them. For
each draft and OUT_DIR it prints the weighted tell score after the rewrite
and whether `compare_rewrite.py` would pass. It exits 1 if any rewrite
fails that check or is missing.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from rewrite_quality import compare, read_text  # noqa: E402


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 1

    corpus = Path(argv[0])
    out_dirs = [Path(d) for d in argv[1:]]
    drafts = sorted(p for p in corpus.glob("*.md") if not p.name.endswith(".context.md"))
    if not drafts:
        print(f"No drafts found in {corpus}")
        return 1

    width = max(len(p.stem) for p in drafts)
    labels = [d.name for d in out_dirs]
    col = max(12, *(len(label) for label in labels))
    print(f"{'draft':<{width}}  {'before':>6}  " + "  ".join(f"{label:>{col}}" for label in labels))

    totals = [0.0] * len(out_dirs)
    before_total = 0.0
    failures: list[str] = []
    for draft in drafts:
        before = read_text(str(draft))
        cells: list[str] = []
        before_score = None
        for i, out_dir in enumerate(out_dirs):
            rewrite = out_dir / draft.name
            if not rewrite.exists():
                cells.append(f"{'missing':>{col}}")
                failures.append(f"{out_dir.name}/{draft.name}: missing")
                continue
            comparison = compare(before, read_text(str(rewrite)))
            before_score = comparison.before_score.total()
            after = comparison.after_score.total()
            totals[i] += after
            verdict = "ok" if comparison.passed else "WARN"
            if not comparison.passed:
                reasons = [f"§{d.number} up" for d in comparison.regressions]
                reasons += [f"§{d.number} left" for d in comparison.remaining_strong]
                reasons += [f"number {n}" for n in comparison.facts.missing_numbers]
                reasons += [f'quote "{q}"' for q in comparison.facts.missing_quotes]
                failures.append(f"{out_dir.name}/{draft.name}: " + ", ".join(reasons))
            cells.append(f"{after:>{col - 5}.1f} {verdict:>4}")
        before_total += before_score or 0.0
        print(f"{draft.stem:<{width}}  {before_score or 0:>6.1f}  " + "  ".join(cells))

    print(f"{'TOTAL':<{width}}  {before_total:>6.1f}  " + "  ".join(f"{t:>{col - 5}.1f}     " for t in totals))

    if failures:
        print("\nChecks that did not pass:")
        for failure in failures:
            print(f"  {failure}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
