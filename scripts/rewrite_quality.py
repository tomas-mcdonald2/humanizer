"""Compare a before/after text pair: tell-count deltas and dropped facts.

Shared by `compare_rewrite.py` (a scored report) and `summarize_changes.py`
(a short changelog). Both read-only; neither calls the skill itself, since
Humanizer is a prompt, not code. Run these after using the skill to check
its output, not as part of the rewrite.
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field
from pathlib import Path

from tell_patterns import PATTERNS_BY_NUMBER, ScoreResult, score_text, strip_code

NUMBER_RE = re.compile(r"\b\d[\d,]*(?:\.\d+)?%?\b")
QUOTE_RE = re.compile(r'"([^"\n]{3,80})"')


@dataclass
class FactCheck:
    missing_numbers: list[str] = field(default_factory=list)
    missing_quotes: list[str] = field(default_factory=list)

    @property
    def clean(self) -> bool:
        return not self.missing_numbers and not self.missing_quotes


def check_facts(before: str, after: str) -> FactCheck:
    """Flag standalone numbers and quoted spans from `before` missing in `after`.

    This is a proxy for SKILL.md's own check step ("did the rewrite drop
    any fact, name, number, date, quote, or citation"), not a substitute
    for reading both texts. A false positive (a number that was rephrased,
    e.g. "three" for "3") is expected and not a bug.
    """
    before_clean = strip_code(before)
    after_clean = strip_code(after)

    missing_numbers = [
        n for n in dict.fromkeys(NUMBER_RE.findall(before_clean))
        if n not in after_clean
    ]
    missing_quotes = [
        q for q in dict.fromkeys(QUOTE_RE.findall(before_clean))
        if q not in after_clean
    ]
    return FactCheck(missing_numbers=missing_numbers, missing_quotes=missing_quotes)


@dataclass
class PatternDelta:
    number: int
    title: str
    tier: str
    before: int
    after: int

    @property
    def delta(self) -> int:
        return self.after - self.before


@dataclass
class Comparison:
    before_score: ScoreResult
    after_score: ScoreResult
    deltas: list[PatternDelta]
    facts: FactCheck

    @property
    def regressions(self) -> list[PatternDelta]:
        """Patterns where the after-text has *more* hits than the before-text."""
        return [d for d in self.deltas if d.delta > 0]

    @property
    def remaining_strong(self) -> list[PatternDelta]:
        """Strong (single-sighting) tells still present after the rewrite."""
        return [d for d in self.deltas if d.tier == "strong" and d.after > 0]

    @property
    def passed(self) -> bool:
        return not self.regressions and not self.remaining_strong and self.facts.clean


def compare(before: str, after: str) -> Comparison:
    before_score = score_text(before)
    after_score = score_text(after)
    numbers = sorted(set(before_score.counts) | set(after_score.counts))
    deltas = [
        PatternDelta(
            number=n,
            title=PATTERNS_BY_NUMBER[n].title,
            tier=PATTERNS_BY_NUMBER[n].tier,
            before=before_score.count(n),
            after=after_score.count(n),
        )
        for n in numbers
    ]
    deltas.sort(key=lambda d: d.number)
    return Comparison(
        before_score=before_score,
        after_score=after_score,
        deltas=deltas,
        facts=check_facts(before, after),
    )


def read_text(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def summarize(before: str, after: str) -> str:
    """Build a short Markdown changelog of what a rewrite changed."""
    comparison = compare(before, after)
    lines: list[str] = ["## Rewrite summary", ""]

    cut = [d for d in comparison.deltas if d.delta < 0]
    added = [d for d in comparison.deltas if d.delta > 0]

    if cut:
        lines.append("**Tells removed:**")
        for d in sorted(cut, key=lambda d: d.delta):
            lines.append(f"- §{d.number} {d.title}: {d.before} → {d.after}")
        lines.append("")

    if added:
        lines.append("**⚠ Tells introduced (check these):**")
        for d in added:
            lines.append(f"- §{d.number} {d.title}: {d.before} → {d.after}")
        lines.append("")

    if not cut and not added:
        lines.append("No change in detected tell counts.")
        lines.append("")

    lines.append("**Facts check** (numbers and quoted spans from the original):")
    if comparison.facts.clean:
        lines.append("- All standalone numbers and quotes from the original appear in the rewrite.")
    else:
        for n in comparison.facts.missing_numbers:
            lines.append(f"- ⚠ Number not found in rewrite: `{n}`")
        for q in comparison.facts.missing_quotes:
            lines.append(f'- ⚠ Quote not found in rewrite: "{q}"')
    lines.append("")

    before_sentences = _sentences(before)
    after_sentences = _sentences(after)
    matcher = difflib.SequenceMatcher(a=before_sentences, b=after_sentences)
    removed = sum(1 for tag, i1, i2, j1, j2 in matcher.get_opcodes() if tag in ("delete", "replace") for _ in range(i2 - i1))
    added_s = sum(1 for tag, i1, i2, j1, j2 in matcher.get_opcodes() if tag in ("insert", "replace") for _ in range(j2 - j1))
    unchanged = sum(1 for tag, *_ in matcher.get_opcodes() if tag == "equal")
    lines.append(
        f"**Shape:** {unchanged} sentence(s) unchanged, "
        f"{removed} removed or rewritten, {added_s} added or rewritten."
    )

    return "\n".join(lines)


SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in SENTENCE_SPLIT_RE.split(text) if s.strip()]
