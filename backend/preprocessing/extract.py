"""Extract raw text from source files, keeping page boundaries where they exist.

A .txt file has no notion of pages, so it comes back as a single "page".
A .pdf file comes back as one entry per page, so downstream steps (cleaning,
chunking) can attach an accurate page number to every chunk.
"""

from dataclasses import dataclass
from pathlib import Path


@dataclass
class PageText:
    """Raw text for a single page (or the whole file, for non-paginated formats)."""
    page_number: int  # 1-indexed
    text: str


SUPPORTED_EXTENSIONS = {".txt", ".pdf"}


def extract_pages(path: str) -> list[PageText]:
    """Dispatch to the right extractor based on file extension."""
    ext = Path(path).suffix.lower()
    if ext == ".txt":
        return _extract_txt(path)
    if ext == ".pdf":
        return _extract_pdf(path)
    raise ValueError(
        f"Unsupported file type '{ext}'. Supported: {sorted(SUPPORTED_EXTENSIONS)}"
    )


def _extract_txt(path: str) -> list[PageText]:
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    return [PageText(page_number=1, text=text)]


def _extract_pdf(path: str) -> list[PageText]:
    from pypdf import PdfReader

    reader = PdfReader(path)
    pages = []
    for i, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        pages.append(PageText(page_number=i, text=text))
    return pages
