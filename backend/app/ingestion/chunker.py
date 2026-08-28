"""
Semantic text chunker for transcript processing.

Chunks are packed from whole paragraphs so a chunk rarely cuts mid-thought,
which keeps retrieved passages readable as citations. Paragraphs larger than
the token budget are bisected on the best available boundary (sentence, then
whitespace) rather than on a raw token offset.

Character offsets are exact slices of the source text, so a citation can be
traced back to its position in the original transcript.
"""
from dataclasses import dataclass
from typing import List, Tuple
import re
import tiktoken

_ENCODING = tiktoken.get_encoding("cl100k_base")

_PARAGRAPH_BREAK = re.compile(r"\n[ \t]*\n\s*")
_SENTENCE_BREAK = re.compile(r"(?<=[.!?])\s+")
_WHITESPACE = re.compile(r"\s+")


@dataclass
class Chunk:
    """Represents a text chunk with metadata."""
    content: str
    token_count: int
    start_char: int
    end_char: int
    chunk_index: int = 0


def _count(text: str) -> int:
    return len(_ENCODING.encode(text))


def _split_point(text: str, start: int, end: int) -> int:
    """
    Best boundary strictly inside (start, end), preferring semantic breaks.

    Always returns a position that makes both halves non-empty, so recursive
    bisection is guaranteed to terminate.
    """
    middle = (start + end) // 2
    for pattern in (_PARAGRAPH_BREAK, _SENTENCE_BREAK, _WHITESPACE):
        best = None
        for match in pattern.finditer(text, start, end):
            if start < match.end() < end:
                if best is None or abs(match.end() - middle) < abs(best - middle):
                    best = match.end()
        if best is not None:
            return best
    return middle if start < middle < end else start + 1


def _fit_spans(text: str, start: int, end: int, max_tokens: int) -> List[Tuple[int, int, int]]:
    """Bisect [start, end) until every span fits in max_tokens."""
    spans: List[Tuple[int, int, int]] = []
    pending = [(start, end)]

    while pending:
        span_start, span_end = pending.pop()
        token_count = _count(text[span_start:span_end])

        if token_count <= max_tokens or span_end - span_start <= 1:
            spans.append((span_start, span_end, token_count))
            continue

        middle = _split_point(text, span_start, span_end)
        pending.append((middle, span_end))
        pending.append((span_start, middle))

    spans.sort()
    return spans


def _segment(text: str, lo: int, hi: int, max_tokens: int) -> List[Tuple[int, int, int]]:
    """
    Tile [lo, hi) into contiguous spans of at most max_tokens.

    Spans tile without gaps, so slicing from one span's start to another's end
    reproduces the source text exactly.
    """
    boundaries = [lo]
    for match in _PARAGRAPH_BREAK.finditer(text, lo, hi):
        if lo < match.end() < hi:
            boundaries.append(match.end())
    boundaries.append(hi)

    segments: List[Tuple[int, int, int]] = []
    for span_start, span_end in zip(boundaries, boundaries[1:]):
        if span_start == span_end:
            continue
        segments.extend(_fit_spans(text, span_start, span_end, max_tokens))

    return segments


def chunk_text(
    text: str,
    min_tokens: int = 800,
    max_tokens: int = 1200,
    overlap_tokens: int = 200,
) -> List[Chunk]:
    """
    Split text into overlapping chunks aligned to paragraph boundaries.

    Args:
        text: Text to chunk
        min_tokens: Chunks below this are merged into the previous chunk when
            the result still fits max_tokens; otherwise a shorter final chunk
            is emitted
        max_tokens: Hard upper bound on tokens per chunk
        overlap_tokens: Tokens of trailing context repeated in the next chunk

    Returns:
        List of Chunk objects, ordered, with exact character offsets
    """
    if max_tokens < 1:
        raise ValueError("max_tokens must be positive")
    if min_tokens > max_tokens:
        raise ValueError("min_tokens cannot exceed max_tokens")

    if not text.strip():
        return []

    lo = len(text) - len(text.lstrip())
    hi = len(text.rstrip())
    stripped = text[lo:hi]

    total_tokens = _count(stripped)
    if total_tokens <= max_tokens:
        return [Chunk(stripped, total_tokens, lo, hi, 0)]

    segments = _segment(text, lo, hi, max_tokens)
    chunks: List[Chunk] = []
    index = 0

    while index < len(segments):
        # Pack greedily by segment totals, then trim against the true token
        # count: tokenisation is not additive across span boundaries.
        end = index
        packed = 0
        while end < len(segments) and (end == index or packed + segments[end][2] <= max_tokens):
            packed += segments[end][2]
            end += 1

        start_char = segments[index][0]
        end_char = segments[end - 1][1]
        content = text[start_char:end_char]
        token_count = _count(content)

        while token_count > max_tokens and end > index + 1:
            end -= 1
            end_char = segments[end - 1][1]
            content = text[start_char:end_char]
            token_count = _count(content)

        chunks.append(Chunk(content, token_count, start_char, end_char, len(chunks)))

        if end >= len(segments):
            break

        # Rewind far enough to repeat overlap_tokens of context, but always
        # land past this chunk's first segment so the cursor cannot stall.
        rewind = end
        carried = 0
        while rewind > index + 1 and carried < overlap_tokens:
            rewind -= 1
            carried += segments[rewind][2]

        index = max(rewind, index + 1)

    if len(chunks) > 1 and chunks[-1].token_count < min_tokens:
        tail = chunks.pop()
        merged_content = text[chunks[-1].start_char:tail.end_char]
        merged_tokens = _count(merged_content)

        if merged_tokens <= max_tokens:
            chunks[-1] = Chunk(
                merged_content,
                merged_tokens,
                chunks[-1].start_char,
                tail.end_char,
                chunks[-1].chunk_index,
            )
        else:
            chunks.append(tail)

    return chunks
