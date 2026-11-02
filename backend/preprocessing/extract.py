"""extract raw text and keep page boundaries when available.

txt files return one page entry.
pdf files return one entry per page for clean chunk mapping.
"""

from dataclasses import dataclass
from pathlib import Path


@dataclass
class PageText:
    """raw text for one page, or full file for non paged formats."""
    page_number: int  # 1 indexed
    text: str


SUPPORTED_EXTENSIONS = {".txt", ".pdf"}


def extract_pages(path: str) -> list[PageText]:
    """dispatch to the right extractor by file extension."""
    ext = Path(path).suffix.lower()
    if ext == ".txt":
        return _extract_txt(path)
    if ext == ".pdf":
        return _extract_pdf(path)
    raise ValueError(
        f"Unsupported file type '{ext}'. Supported: {sorted(SUPPORTED_EXTENSIONS)}"
    )


def _extract_txt(path: str) -> list[PageText]:
    with open(path, encoding="utf-8") as f:
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
