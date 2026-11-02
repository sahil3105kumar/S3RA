"""split cleaned text into embedding ready chunks.

chunking keeps paragraph boundaries, tracks section headings, and uses token limits.
small overlap keeps context across chunk boundaries.
max tokens should come from callers, defaults here are fallback only.
"""

from collections.abc import Callable
from dataclasses import dataclass

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
    """fallback token estimate when no tokenizer is supplied."""
    return max(1, round(len(text.split()) / 0.75))


def _is_heading(paragraph: str) -> bool:
    # heading lines should be isolated by clean.py.
    # multiline paragraphs are treated as body text.
    if "\n" in paragraph.strip():
        return False
    return is_heading_line(paragraph)


def _split_into_paragraphs(page: PageText) -> list[tuple[int, str]]:
    """return page number and paragraph text pairs without empty entries."""
    paragraphs = [p.strip() for p in page.text.split("\n\n")]
    return [(page.page_number, p) for p in paragraphs if p]


def _split_oversized_paragraph(
    paragraph: str, max_tokens: int, count_tokens: CountTokens
) -> list[str]:
    """split one oversized paragraph into smaller pieces.

    use word estimate first, then recheck with tokenizer.
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
        # shrink until the piece fits the token limit.
        piece_words = words[i : i + words_per_piece]
        while len(piece_words) > 1 and count_tokens(" ".join(piece_words)) > max_tokens:
            piece_words = piece_words[: len(piece_words) // 2]
        piece = " ".join(piece_words)
        pieces.append(piece)
        i += len(piece_words) if piece_words else words_per_piece
    return pieces


def _overlap_tail(text: str, overlap_tokens: int, count_tokens: CountTokens) -> str:
    """get a tail slice close to overlap token budget."""
    words = text.split()
    if not words:
        return ""
    total_tokens = count_tokens(text)
    tokens_per_word = total_tokens / len(words) if words else 1
    tail_word_count = max(1, min(len(words), int(overlap_tokens / tokens_per_word)))
    tail = " ".join(words[-tail_word_count:])
    # recheck tail size with real tokenizer.
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
    """chunk cleaned pages into section aware token bounded chunks."""
    count_tokens = count_tokens or _default_count_tokens

    all_paragraphs: list[tuple[int, str]] = []
    for page in pages:
        all_paragraphs.extend(_split_into_paragraphs(page))

    chunks: list[Chunk] = []
    buffer_parts: list[str] = []
    buffer_page_start: int | None = None
    buffer_page_end: int | None = None
    current_section: str | None = None
    buffer_section: str | None = None  # section active when this buffer started.

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
        # overlap tail keeps the section active at flush time.
        buffer_section = current_section

    for page_number, paragraph in all_paragraphs:
        if _is_heading(paragraph):
            current_section = paragraph
            if not buffer_parts:
                buffer_section = current_section
            # keep headings with following content instead of isolated chunks.
            continue

        para_tokens = count_tokens(paragraph)
        pieces = (
            [paragraph]
            if para_tokens <= max_tokens
            else _split_oversized_paragraph(paragraph, max_tokens, count_tokens)
        )

        for piece in pieces:
            # check token count on final joined text, not per piece sums.
            candidate = "\n\n".join(buffer_parts + [piece]) if buffer_parts else piece
            if buffer_parts and count_tokens(candidate) > max_tokens:
                flush()
                # flush keeps overlap tail in buffer.
                # if tail plus new piece still overflows, drop tail once.
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