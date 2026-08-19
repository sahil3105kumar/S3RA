"""Split cleaned document text into embedding-ready chunks.

Replaces naive fixed-word-count chunking with something that:
  - respects paragraph boundaries instead of cutting mid-paragraph
  - tracks the nearest preceding heading as a "section" label
  - sizes chunks against the embedding model's own tokenizer, so we stay
    under its max sequence length instead of guessing with a word count
  - carries a small overlap between consecutive chunks so context isn't
    lost right at a chunk boundary

The embedding model's real max sequence length isn't hardcoded here --
callers (see ingest.py) should derive it from the model/tokenizer at
runtime and pass it in as `max_tokens`, since different models (or even
different versions of the same one) don't all report the same limit.
DEFAULT_MAX_TOKENS below is only a fallback for standalone/testing use.
"""

from dataclasses import dataclass
from typing import Callable

from preprocessing.extract import PageText
from preprocessing.headings import is_heading_line

DEFAULT_MAX_TOKENS = 200
DEFAULT_OVERLAP_TOKENS = 40

CountTokens = Callable[[str], int]


@dataclass
class Chunk:
    text: str
    page_start: int
    page_end: int
    section: str | None


def _default_count_tokens(text: str) -> int:
    """Fallback token counter (roughly 0.75 words/token) when no tokenizer is supplied."""
    return max(1, round(len(text.split()) / 0.75))


def _is_heading(paragraph: str) -> bool:
    # A heading is always a single isolated line by the time it reaches
    # chunking -- clean.py's line-wrap fixer guarantees that. A multi-line
    # paragraph is never a heading, even if its first line looks like one.
    if "\n" in paragraph.strip():
        return False
    return is_heading_line(paragraph)


def _split_into_paragraphs(page: PageText) -> list[tuple[int, str]]:
    """Return (page_number, paragraph_text) pairs, dropping empty paragraphs."""
    paragraphs = [p.strip() for p in page.text.split("\n\n")]
    return [(page.page_number, p) for p in paragraphs if p]


def _split_oversized_paragraph(
    paragraph: str, max_tokens: int, count_tokens: CountTokens
) -> list[str]:
    """Word-chunk a single paragraph that's too big to fit in one chunk on its own.

    Uses a word-count estimate to pick a starting split point, then verifies
    each piece against the real tokenizer and shrinks further if needed --
    word-to-token ratio isn't constant, so the estimate alone isn't trustworthy.
    """
    words = paragraph.split()
    total_tokens = count_tokens(paragraph)
    if total_tokens <= max_tokens or not words:
        return [paragraph]

    tokens_per_word = total_tokens / len(words)
    words_per_piece = max(1, int(max_tokens / tokens_per_word))

    pieces = []
    i = 0
    while i < len(words):
        piece = " ".join(words[i : i + words_per_piece])
        # Shrink until the piece actually fits -- don't trust the estimate blindly.
        piece_words = words[i : i + words_per_piece]
        while len(piece_words) > 1 and count_tokens(" ".join(piece_words)) > max_tokens:
            piece_words = piece_words[: len(piece_words) // 2]
        piece = " ".join(piece_words)
        pieces.append(piece)
        i += len(piece_words) if piece_words else words_per_piece
    return pieces


def _overlap_tail(text: str, overlap_tokens: int, count_tokens: CountTokens) -> str:
    """Grab roughly the last `overlap_tokens` worth of words from `text`."""
    words = text.split()
    if not words:
        return ""
    total_tokens = count_tokens(text)
    tokens_per_word = total_tokens / len(words) if words else 1
    tail_word_count = max(1, min(len(words), int(overlap_tokens / tokens_per_word)))
    tail = " ".join(words[-tail_word_count:])
    # Verify against the real tokenizer -- word/token ratio is only an estimate.
    while tail_word_count > 1 and count_tokens(tail) > overlap_tokens:
        tail_word_count -= 1
        tail = " ".join(words[-tail_word_count:])
    return tail


def chunk_pages(
    pages: list[PageText],
    count_tokens: CountTokens | None = None,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    overlap_tokens: int = DEFAULT_OVERLAP_TOKENS,
) -> list[Chunk]:
    """Chunk cleaned pages into paragraph-aware, section-tagged, token-bounded chunks."""
    count_tokens = count_tokens or _default_count_tokens

    all_paragraphs: list[tuple[int, str]] = []
    for page in pages:
        all_paragraphs.extend(_split_into_paragraphs(page))

    chunks: list[Chunk] = []
    buffer_parts: list[str] = []
    buffer_page_start: int | None = None
    buffer_page_end: int | None = None
    current_section: str | None = None
    buffer_section: str | None = None  # section active when this buffer started

    def flush() -> None:
        nonlocal buffer_parts, buffer_page_start, buffer_page_end, buffer_section
        if not buffer_parts:
            return
        text = "\n\n".join(buffer_parts)
        chunks.append(
            Chunk(
                text=text,
                page_start=buffer_page_start or 1,
                page_end=buffer_page_end or buffer_page_start or 1,
                section=buffer_section,
            )
        )
        tail = _overlap_tail(text, overlap_tokens, count_tokens)
        buffer_parts = [tail] if tail else []
        buffer_page_start = buffer_page_end
        # The carried-over overlap tail still belongs to the section that
        # was active when the chunk we just flushed was built.
        buffer_section = current_section

    for page_number, paragraph in all_paragraphs:
        if _is_heading(paragraph):
            current_section = paragraph
            if not buffer_parts:
                buffer_section = current_section
            # A heading alone isn't useful as its own chunk; fold it into
            # whatever comes next rather than flushing here.
            continue

        para_tokens = count_tokens(paragraph)
        pieces = (
            [paragraph]
            if para_tokens <= max_tokens
            else _split_oversized_paragraph(paragraph, max_tokens, count_tokens)
        )

        for piece in pieces:
            # Check the REAL token count of what the chunk text would become
            # if we added this piece -- not a running sum of separately
            # counted pieces. Tokenizing "\n\n".join(parts) as one string
            # does not equal the sum of each part's isolated token count
            # (word-piece merging behaves differently at real vs. fake
            # boundaries), and that drift compounds as more pieces are added.
            candidate = "\n\n".join(buffer_parts + [piece]) if buffer_parts else piece
            if buffer_parts and count_tokens(candidate) > max_tokens:
                flush()
                # flush() doesn't empty buffer_parts -- it seeds it with the
                # overlap tail from the chunk we just closed. If that tail is
                # already sizeable and `piece` is itself close to max_tokens,
                # tail + piece can *still* overflow even though we just
                # flushed. Re-check against the post-flush buffer, and if it
                # still doesn't fit, drop the tail for this one boundary
                # rather than silently exceeding the model's real limit.
                candidate = "\n\n".join(buffer_parts + [piece]) if buffer_parts else piece
                if buffer_parts and count_tokens(candidate) > max_tokens:
                    buffer_parts = []
                    buffer_page_start = None
            if not buffer_parts:
                buffer_section = current_section
            if buffer_page_start is None:
                buffer_page_start = page_number
            buffer_page_end = page_number
            buffer_parts.append(piece)

    flush()
    return [c for c in chunks if c.text.strip()]