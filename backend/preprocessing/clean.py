"""Clean raw extracted text before it gets chunked and embedded.

Handles the mess that PDF extraction typically leaves behind:
- Running headers/footers that repeat on (almost) every page
- Standalone page-number lines ("12", "Page 12 of 40", "- 12 -")
- Hard line-wraps in the middle of sentences (PDF text is wrapped to the
  page width, not to sentence boundaries)
- Non-canonical unicode (e.g. ligatures, fancy quotes, decomposed accents)
  via NFKC normalization, so the same word always embeds the same way
"""

import re
import unicodedata
from collections import Counter

from preprocessing.extract import PageText
from preprocessing.headings import is_heading_line

_PAGE_NUMBER_RE = re.compile(
    r"^\s*(page\s+)?\d{1,4}(\s*(of|/)\s*\d{1,4})?\s*$"
    r"|^\s*[-–—]\s*\d{1,4}\s*[-–—]\s*$",
    re.IGNORECASE,
)

# A line that looks like a paragraph should end here (sentence punctuation,
# closing bracket/quote, or a bullet/list marker starting the NEXT line).
_SENTENCE_END_RE = re.compile(r"[.!?:;\"')\]]\s*$")
_BULLET_RE = re.compile(r"^\s*([\-*•‣▪]|\d+[.)]|\([a-zA-Z0-9]+\))\s+")


def strip_running_headers_footers(pages: list[PageText], min_pages: int = 3) -> list[PageText]:
    """Remove lines that repeat near-verbatim across most pages (running headers/footers).

    Only kicks in once there's enough pages to distinguish "boilerplate that
    repeats" from "text that happens to repeat once".
    """
    if len(pages) < min_pages:
        return pages

    line_page_counts: Counter[str] = Counter()
    for page in pages:
        # Count each distinct line at most once per page, so a line repeated
        # within a single page doesn't inflate its cross-page count.
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
    """Join hard-wrapped lines back into paragraphs, keeping real paragraph breaks.

    A blank line stays a paragraph break. A single newline gets collapsed
    into a space UNLESS the line before it looks like the end of a
    sentence/paragraph, or the line after it looks like a new bullet/heading.

    Headings get special handling: PDFs rarely leave a blank line between a
    heading and the body text that follows it, so without this a heading
    would get merged straight into the next paragraph. A heading line is
    always forced onto its own paragraph, in both directions.
    """
    lines = text.split("\n")
    out: list[str] = []
    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            out.append("")  # preserve paragraph break
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
    """Per-page cleanup: drop page-number lines, fix wraps, normalize unicode."""
    lines = [line for line in text.split("\n") if not _PAGE_NUMBER_RE.match(line)]
    text = "\n".join(lines)
    text = _fix_line_wraps(text)
    text = unicodedata.normalize("NFKC", text)
    # Collapse 3+ blank lines down to a single paragraph break.
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def clean_pages(pages: list[PageText]) -> list[PageText]:
    """Full cleaning pipeline: cross-page boilerplate removal, then per-page cleanup."""
    pages = strip_running_headers_footers(pages)
    return [
        PageText(page_number=p.page_number, text=clean_page_text(p.text)) for p in pages
    ]
