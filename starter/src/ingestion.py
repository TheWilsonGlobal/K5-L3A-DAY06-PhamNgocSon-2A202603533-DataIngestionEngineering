"""Read and normalize source data."""
import re
import unicodedata
from pathlib import Path

from .config import SECTION_STARTS
from .models import DocumentPage

_FOOTER = [
    re.compile(r"^access for free at openstax\.org\s*$", re.I),
    re.compile(r"^\d\.\d\s*\W?\s*[^\d].{0,70}?\s+\d{3}\s*$"),      # "6.3 ? Processes and Concurrency 259"
    re.compile(r"^\d{3}\s+\d\s*\W?\s*.{0,80}$"),                   # "258 6 * Infrastructure ..." (even pages)
    re.compile(r"^\d{1,2}\s*$"),                                   # lone chapter number at page end
]
_HEADING = re.compile(r"^[A-Z0-9][A-Za-z0-9 ,&'/\-]{2,68}[A-Za-z0-9?]$")
_END = re.compile(r"[.!?:)]$")


def section_for(page: int) -> tuple[str, str]:
    """Section whose outline start page is the latest one <= page. Known limitation: when a
    section heading sits mid-page, the earlier part of that page is labelled with the new section."""
    cur = SECTION_STARTS[0]
    for entry in SECTION_STARTS:
        if entry[0] <= page:
            cur = entry
    return cur[1], cur[2]


def normalize_text(text: str) -> str:
    """NFC, drop running headers/footers, repair U+FFFD, re-join wrapped lines.

    Paragraphs are separated by a blank line; short heading-like lines get their own paragraph.
    """
    text = unicodedata.normalize("NFC", text)
    # pypdf emits U+FFFD for typographic quotes/bullets/dashes: letter?letter -> apostrophe, else drop.
    text = re.sub(r"(?<=[A-Za-z])�(?=[A-Za-z])", "'", text)
    text = text.replace("�", " ")
    lines = [ln.strip() for ln in text.replace("\r", "").split("\n") if ln.strip()]
    lines = [ln for ln in lines if not any(p.match(ln) for p in _FOOTER)]
    paras: list[list[str]] = []
    cur: list[str] = []
    for s in lines:
        is_heading = bool(_HEADING.match(s)) and len(s.split()) <= 9 and not _END.search(s)
        if is_heading:
            if cur:
                paras.append(cur)
            paras.append([s])
            cur = []
            continue
        cur.append(s)
        if len(s) < 90 and _END.search(s):
            paras.append(cur)
            cur = []
    if cur:
        paras.append(cur)
    out = [re.sub(r"[ \t]+", " ", " ".join(p)).strip() for p in paras]
    return "\n\n".join(x for x in out if x)


def flat(text: str) -> str:
    """Whitespace-collapsed form used for every evidence/quote comparison."""
    return " ".join(unicodedata.normalize("NFC", text).split())


def load_pdf(path: Path, document_id: str, source: str,
             first_page: int = 1, last_page: int | None = None,
             errors: list[dict] | None = None) -> list[DocumentPage]:
    """Extract each physical page (1-based, inclusive); record empty/failed pages in `errors`."""
    from pypdf import PdfReader
    reader = PdfReader(str(path))
    last = last_page or len(reader.pages)
    errors = errors if errors is not None else []
    pages: list[DocumentPage] = []
    for n in range(first_page, last + 1):
        try:
            raw = reader.pages[n - 1].extract_text() or ""
        except Exception as exc:  # report, never swallow silently
            errors.append({"page": n, "error": f"extract failed: {exc!r}"})
            continue
        text = normalize_text(raw)
        if len(flat(text)) < 200:
            errors.append({"page": n, "error": "empty or near-empty page", "chars": len(flat(text))})
            continue
        sid, stitle = section_for(n)
        pages.append(DocumentPage(document_id, source, n, text,
                                  {"section": sid, "section_title": stitle, "chars": len(flat(text))}))
    return pages
