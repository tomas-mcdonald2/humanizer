"""Detect Humanizer's numbered AI-writing tells in a block of text.

This is a heuristic, dependency-free approximation of the 25 patterns in
`SKILL.md`. It cannot judge meaning the way the skill's own read-and-rewrite
process does, so it under- and over-matches in places. Use it to compare a
before/after pair, not to grade a single text in isolation.

Each pattern has a `tier` that mirrors SKILL.md's own ranking:

- "strong": patterns 1-5, which the skill says "justify an edit on one
  sighting."
- "weak_alone": patterns 8, 9, 10, 11, 21, which the skill marks
  *weak alone* and only counts when several tells share a passage.
- "moderate": every other automated pattern.

Pattern 24 ("a heading repeated in the first sentence") needs structural
context this module does not model, so it is not included here. Treat it as
manual-only.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable

CODE_BLOCK_RE = re.compile(r"```.*?```", re.DOTALL)
INLINE_CODE_RE = re.compile(r"`[^`\n]+`")


def strip_code(text: str) -> str:
    """Remove fenced and inline code so matchers ignore commands, paths, and URLs.

    SKILL.md's own dash and hyphen rules exempt code; the other patterns
    should not fire inside code either.
    """
    text = CODE_BLOCK_RE.sub(" ", text)
    text = INLINE_CODE_RE.sub(" ", text)
    return text


@dataclass
class Match:
    snippet: str


@dataclass
class Pattern:
    number: int
    title: str
    tier: str  # "strong" | "moderate" | "weak_alone"
    matcher: Callable[[str], list[str]]

    def find(self, text: str) -> list[str]:
        return self.matcher(strip_code(text))


TIER_WEIGHT = {"strong": 2.0, "moderate": 1.0, "weak_alone": 0.5}


def _phrase_matcher(phrases: list[str]) -> Callable[[str], list[str]]:
    compiled = [
        re.compile(r"\b" + re.escape(p) + r"\b", re.IGNORECASE)
        if re.match(r"^[\w\s'/-]+$", p)
        else re.compile(re.escape(p), re.IGNORECASE)
        for p in phrases
    ]

    def matcher(text: str) -> list[str]:
        hits: list[str] = []
        for rx in compiled:
            hits.extend(m.group(0) for m in rx.finditer(text))
        return hits

    return matcher


def _regex_matcher(pattern: str, flags: int = re.IGNORECASE) -> Callable[[str], list[str]]:
    rx = re.compile(pattern, flags)

    def matcher(text: str) -> list[str]:
        return [m.group(0) for m in rx.finditer(text)]

    return matcher


def _not_x_but_y(text: str) -> list[str]:
    # Covers "not X but Y", the reversed "X rather than Y", and the "it's not
    # X, it's Y" / "not just X; it's Y" split forms.
    rx = re.compile(
        r"\bnot\b[^.?!\n]{0,60}?(?:\bbut\b[^.?!\n]{0,60}|[,;]\s*it'?s\b[^.?!\n]{0,60})",
        re.IGNORECASE,
    )
    hits = [m.group(0) for m in rx.finditer(text)]
    hits.extend(m.group(0) for m in re.finditer(r"\b\w[\w\s]{0,30}?\brather than\b[\w\s]{0,30}", text, re.IGNORECASE))
    # The same contrast split across two sentences ("This does not mean X.
    # It means Y.") and a clipped negative tail ("..., no guessing.").
    hits.extend(m.group(0) for m in re.finditer(r"\bthis does not mean\b", text, re.IGNORECASE))
    hits.extend(m.group(0) for m in re.finditer(r",\s+no\s+\w+(?:ing)?\.", text, re.IGNORECASE))
    return hits


def _one_line_closers(text: str) -> list[str]:
    hits = _phrase_matcher(
        ["that is the real win", "read that again", "let that sink in"]
    )(text)
    hits.extend(
        m.group(0)
        for m in re.finditer(r"\b(?:\w+\.\s+){2,}\w+\.", text)
    )
    hits.extend(m.group(0) for m in re.finditer(r"\b[A-Z]{4,}\b", text))
    # A row of short fragments, e.g. "No aesthetic prior. No nostalgia."
    hits.extend(
        m.group(0)
        for m in re.finditer(r"\b(?:No|Not)\s+[\w'-]+(?:\s[\w'-]+){0,3}\.\s+(?:No|Not)\s+[\w'-]+(?:\s[\w'-]+){0,3}\.", text)
    )
    return hits


def _forced_triads(text: str) -> list[str]:
    rx = re.compile(
        r"\b[A-Za-z][\w'-]*(?:\s[\w'-]+)?,\s[\w'-]+(?:\s[\w'-]+)?,?\s(?:and|or)\s[\w'-]+(?:\s[\w'-]+)?\b"
    )
    return [m.group(0) for m in rx.finditer(text)]


SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


def _repeated_openings(text: str) -> list[str]:
    sentences = [s.strip() for s in SENTENCE_SPLIT_RE.split(text) if s.strip()]
    hits: list[str] = []
    run: list[str] = []
    prev_word = None
    for sentence in sentences:
        first = re.match(r"[A-Za-z']+", sentence)
        word = first.group(0).lower() if first else None
        if word and word == prev_word:
            run.append(sentence)
        else:
            if len(run) >= 3:
                hits.append(" / ".join(s[:30] for s in run))
            run = [sentence] if word else []
        prev_word = word
    if len(run) >= 3:
        hits.append(" / ".join(s[:30] for s in run))
    return hits


def _dashes(text: str) -> list[str]:
    hits = [m.group(0) for m in re.finditer(r"[–—]", text)]
    hits.extend(m.group(0) for m in re.finditer(r"\s--\s", text))
    return hits


PASSIVE_PARTICIPLES = (
    r"\w+ed|given|made|done|seen|written|known|taken|found|held|kept|left|felt|"
    r"told|sold|sent|spent|built|brought|thought|bought|caught|taught|chosen|"
    r"driven|shown|grown|drawn|needed"
)


def _passive_voice(text: str) -> list[str]:
    rx = re.compile(rf"\b(?:is|are|was|were|been|being)\s+(?:{PASSIVE_PARTICIPLES})\b", re.IGNORECASE)
    return [m.group(0) for m in rx.finditer(text)]


def _bold_decoration(text: str) -> list[str]:
    return [m.group(0) for m in re.finditer(r"\*\*[^*\n]+\*\*", text)]


EMOJI_RE = re.compile(
    "[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF]"
)


def _decorative_headings(text: str) -> list[str]:
    hits: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        m = re.match(r"^(#{1,6})\s+(.+)$", stripped)
        if m:
            heading = m.group(2)
        elif EMOJI_RE.match(stripped) and "**" in stripped:
            # A bold, emoji-led line standing in for a heading, e.g.
            # "🚀 **Launch Phase:** The product launches in Q3".
            heading = stripped
        else:
            continue
        if EMOJI_RE.search(heading) or "→" in heading:
            hits.append(heading)
            continue
        words = [w for w in re.split(r"\s+", heading) if re.match(r"^[A-Za-z]", w)]
        skip = {"a", "an", "the", "of", "in", "on", "for", "and", "or", "to", "with"}
        capitalized = [w for w in words if w not in skip]
        if len(capitalized) >= 3 and all(w[0:1].isupper() for w in capitalized):
            hits.append(heading)
    return hits


def _curly_quotes(text: str) -> list[str]:
    return [m.group(0) for m in re.finditer(r"[“”‘’]", text)]


HYPHENATED_PAIRS = [
    "third-party", "cross-functional", "client-facing", "data-driven",
    "decision-making", "well-known", "high-quality", "real-time",
    "long-term", "end-to-end",
]

OVERUSED_AI_WORDS = [
    "actually", "additionally", "align with", "bolstered", "crucial",
    "deep dive", "delve", "emphasizing", "enduring", "enhance", "fostering",
    "garner", "gating", "highlight", "interplay", "intricate", "intricacies",
    "key", "landscape", "meticulous", "meticulously", "pivotal", "quietly",
    "robust", "showcase", "tapestry", "testament", "underscore", "valuable",
    "vibrant",
]

PATTERNS: list[Pattern] = [
    Pattern(1, "Not X but Y", "strong", _not_x_but_y),
    Pattern(2, "One-line closers and dramatic fragments", "strong", _one_line_closers),
    Pattern(
        3, "Sayings that sound deep", "strong",
        _phrase_matcher([
            "at its core", "the real question is", "what really matters",
            "fundamentally,", "the deeper issue", "the heart of the matter",
            "is the language of", "is the currency of", "is the architecture of",
            "becomes a trap",
        ]),
    ),
    Pattern(
        4, "Staged run-up before the point", "strong",
        _phrase_matcher([
            "let's dive in", "let's explore", "let's break this down",
            "here's what you need to know", "without further ado",
            "heads up,", "quick note:", "here's the thing", "the thing is,",
            "let's be honest", "real talk", "honestly?",
        ]),
    ),
    Pattern(
        5, "Arguing with no one", "strong",
        _phrase_matcher([
            "this isn't mainly about", "this isn't about", "i'm not saying",
            "to be clear,", "don't get me wrong", "this is not to say",
            "a tempting approach would be", "one might be tempted to",
            "an obvious approach would be", "you might think",
            "it would be easy to just",
        ]),
    ),
    Pattern(6, "Forced triads", "moderate", _forced_triads),
    Pattern(7, "Repeated sentence openings", "moderate", _repeated_openings),
    Pattern(8, "Dashes as the universal connector", "weak_alone", _dashes),
    Pattern(
        9, "Stacked qualifiers", "weak_alone",
        _phrase_matcher([
            "to be fair,", "it's also possible", "could potentially",
            "might arguably", "in some cases it may", "this is an inference",
        ]),
    ),
    Pattern(10, "Hyphenated pairs everywhere", "weak_alone", _phrase_matcher(HYPHENATED_PAIRS)),
    Pattern(11, "Passive voice and missing subjects", "weak_alone", _passive_voice),
    Pattern(12, "Overused AI words", "moderate", _phrase_matcher(OVERUSED_AI_WORDS)),
    Pattern(
        13, "Inflated significance", "moderate",
        _phrase_matcher([
            "stands as a testament", "a pivotal moment", "a crucial moment",
            "plays a key role", "marking a", "shaping the",
            "underscores its importance", "reflects a broader",
            "enduring legacy", "lasting legacy", "setting the stage for",
            "evolving landscape", "indelible mark", "continues to thrive",
            "the future looks bright", "exciting times ahead",
            "a step in the right direction",
        ]),
    ),
    Pattern(
        14, "Vague connection or association", "moderate",
        _phrase_matcher([
            "associated with", "in association with", "connected to",
            "in connection with", "linked to", "tied to",
        ]),
    ),
    Pattern(
        15, "Shallow -ing riders", "moderate",
        _phrase_matcher([
            "highlighting", "underscoring", "emphasizing", "ensuring",
            "reflecting", "symbolizing", "contributing to", "cultivating",
            "fostering", "encompassing", "showcasing",
        ]),
    ),
    Pattern(
        16, "Sales language", "moderate",
        _phrase_matcher([
            "boasts", "vibrant", "rich cultural", "profound", "enhancing",
            "exemplifies", "commitment to", "natural beauty", "nestled",
            "in the heart of", "groundbreaking", "renowned", "featuring",
            "diverse array", "breathtaking", "must-visit", "stunning",
        ]),
    ),
    Pattern(
        17, "Borrowed authority", "moderate",
        lambda text: _phrase_matcher([
            "observers have cited", "industry reports", "some critics",
            "several publications", "active social media presence",
        ])(text)
        + _regex_matcher(r"\bexperts?\s+(?:argue|believe|say|suggest|agree|note)\b")(text)
        + _regex_matcher(r"\bover\s+[\d,]+\s+followers\b")(text),
    ),
    Pattern(
        18, "Avoiding is, are, and has", "moderate",
        lambda text: _phrase_matcher([
            "serves as", "stands as", "functions as", "operates as",
            "boasts", "features", "offers", "maintains", "refers to",
        ])(text) + _regex_matcher(r"\b(?:marks|represents)\s+an?\b")(text),
    ),
    Pattern(19, "Bold as decoration", "moderate", _bold_decoration),
    Pattern(20, "Decorative headings", "moderate", _decorative_headings),
    Pattern(21, "Curly quotation marks", "weak_alone", _curly_quotes),
    Pattern(
        22, "Chatbot residue", "moderate",
        _phrase_matcher([
            "i hope this helps", "of course!", "certainly!",
            "great question!", "you're absolutely right", "would you like",
            "want me to", "should i continue", "let me know", "here is a",
            "here is an",
        ]),
    ),
    Pattern(
        23, "Knowledge-limit disclaimers and guesses", "moderate",
        _phrase_matcher([
            "as of my last training update", "up to my last training update",
            "while specific details are limited", "based on available information",
            "not publicly available", "not widely documented",
            "not widely disclosed", "not extensively documented",
            "it appears to have been", "maintains a low profile",
            "keeps personal details private", "it is believed that",
            "likely grew up", "likely studied", "likely began",
        ]),
    ),
    Pattern(
        25, "Writing about the previous version", "moderate",
        _phrase_matcher([
            "was added to replace", "the previous approach of",
            "previously used", "used to require", "in the old version",
            "the old way of", "this replaces the former",
        ]),
    ),
]

PATTERNS_BY_NUMBER = {p.number: p for p in PATTERNS}


@dataclass
class ScoreResult:
    counts: dict[int, list[str]] = field(default_factory=dict)

    def count(self, number: int) -> int:
        return len(self.counts.get(number, []))

    def total(self) -> float:
        return sum(
            TIER_WEIGHT[PATTERNS_BY_NUMBER[n].tier] * len(hits)
            for n, hits in self.counts.items()
        )

    def strong_hits(self) -> int:
        return sum(
            len(hits)
            for n, hits in self.counts.items()
            if PATTERNS_BY_NUMBER[n].tier == "strong"
        )


def score_text(text: str) -> ScoreResult:
    result = ScoreResult()
    for pattern in PATTERNS:
        hits = pattern.find(text)
        if hits:
            result.counts[pattern.number] = hits
    return result
