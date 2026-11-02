"""shared rule for heading line detection.

clean.py and chunk.py both use this so heading behavior stays consistent.
"""

import re

_MARKDOWN_HEADING_RE = re.compile(r"^#{1,6}\s+.+$")
_NUMBERED_HEADING_RE = re.compile(r"^\d+(\.\d+)*\.?\s+[A-Z].{0,80}$")
_SENTENCE_END_RE = re.compile(r"[.!?]\s*$")

# short connector words can stay lowercase and still look like title case.
_LOWERCASE_STOPWORDS = {
    "a", "an", "and", "as", "at", "but", "by", "for", "in", "of", "on",
    "or", "the", "to", "with", "vs",
}


def _is_title_or_upper_case(line: str) -> bool:
    words = re.findall(r"[A-Za-z']+", line)
    if not words:
        return False
    significant = [w for w in words if w.lower() not in _LOWERCASE_STOPWORDS]
    if not significant:
        significant = words
    capitalized = sum(1 for w in significant if w[0].isupper())
    return capitalized / len(significant) >= 0.8


def is_heading_line(line: str) -> bool:
    line = line.strip()
    if not line:
        return False
    if len(line) > 90 or len(line.split()) > 12:
        return False
    if _SENTENCE_END_RE.search(line):
        return False

    if _MARKDOWN_HEADING_RE.match(line) or _NUMBERED_HEADING_RE.match(line):
        return True

    return _is_title_or_upper_case(line)
