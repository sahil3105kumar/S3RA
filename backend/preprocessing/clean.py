"""clean extracted text before chunking and embedding.

remove repeated headers and footers, page number lines, and hard wraps.
normalize unicode so equivalent words embed consistently.
"""

import re
import unicodedata
from collections import Counter

from preprocessing.extract import PageText
from preprocessing.headings import is_heading_line

_PAGE_NUMBER_RE = re.compile(
    r"^\s*(page\s+)?\d{1,4}(\s*(of|/)\s*\d{1,4})?\s*$"
    r"|^\s*[-–-]\s*\d{1,4}\s*[-–-]\s*$",
    re.IGNORECASE,
)

# line endings that likely close a sentence or paragraph.
_SENTENCE_END_RE = re.compile(r"[.!?:;\"')\]]\s*$")
_BULLET_RE = re.compile(r"^\s*([\-*•‣▪]|\d+[.)]|\([a-zA-Z0-9]+\))\s+")


def strip_running_headers_footers(pages: list[PageText], min_pages: int = 3) -> list[PageText]:
    """remove lines that repeat across many pages.

    this starts only when enough pages exist for stable detection.
    """
    if len(pages) < min_pages:
        return pages

    line_page_counts: Counter[str] = Counter()
    for page in pages:
        # count each distinct line once per page.
        seen_this_page = {line.strip() for line in page.text.splitlines() if line.strip()}
        line_page_counts.update(seen_this_page)

    threshold = max(3, int(len(pages) * 0.5))
    boilerplate = {line for line, count in line_page_counts.items() if count >= threshold}
    if not boilerplate:
        return pages

    cleaned = []
    for page in pages:
        kept_lines = [
            line for line in page.text.splitlines() if line.strip() not in boilerplate
        ]
        cleaned.append(PageText(page_number=page.page_number, text="\n".join(kept_lines)))
    return cleaned


def _fix_line_wraps(text: str) -> str:
    """join hard wrapped lines and keep real paragraph breaks.

    blank lines stay as breaks.
    heading and bullet boundaries are preserved.
    """
    lines = text.split("\n")
    out: list[str] = []
    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            out.append("")  # preserve paragraph break.
            continue

        if is_heading_line(line):
            if out and out[-1] != "":
                out.append("")
            out.append(line)
            out.append("")
            continue

        if not out or out[-1] == "":
            out.append(line)
            continue

        prev = out[-1]
        next_is_bullet = _BULLET_RE.match(line) is not None
        prev_ends_sentence = _SENTENCE_END_RE.search(prev) is not None

        if prev_ends_sentence or next_is_bullet:
            out.append(line)
        else:
            out[-1] = f"{prev} {line}"
    return "\n".join(out)


def clean_page_text(text: str) -> str:
    """clean one page by removing page numbers, fixing wraps, and normalizing unicode."""
    lines = [line for line in text.split("\n") if not _PAGE_NUMBER_RE.match(line)]
    text = "\n".join(lines)
    text = _fix_line_wraps(text)
    text = unicodedata.normalize("NFKC", text)
    # collapse long blank runs to one paragraph break.
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def clean_pages(pages: list[PageText]) -> list[PageText]:
    """run full cleanup pipeline for all pages."""
    pages = strip_running_headers_footers(pages)
    return [
        PageText(page_number=p.page_number, text=clean_page_text(p.text)) for p in pages
    ]