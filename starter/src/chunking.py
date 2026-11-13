"""Fixed-size and structure-aware chunking. Chunks never cross a page boundary."""
import hashlib
import re

from .models import Chunk, DocumentPage


def _cid(strategy: str, page: DocumentPage, offset: int, text: str) -> str:
    h = hashlib.sha1(f"{strategy}|{page.document_id}|{page.page}|{offset}|{text}".encode()).hexdigest()[:16]
    return f"{strategy}-p{page.page}-{offset}-{h}"


def _mk(strategy: str, page: DocumentPage, offset: int, text: str) -> Chunk:
    md = {"section": page.metadata.get("section"), "section_title": page.metadata.get("section_title"),
          "strategy": strategy, "offset": offset, "chars": len(text)}
    return Chunk(_cid(strategy, page, offset, text), page.document_id, page.source, page.page, text, md)


def fixed_size(page: DocumentPage, size: int, overlap: int, strategy: str = "A") -> list[Chunk]:
    """Overlapping character windows over the whitespace-collapsed page text."""
    assert 0 <= overlap < size
    text = " ".join(page.text.split())
    out, start = [], 0
    while start < len(text):
        piece = text[start:start + size].strip()
        if piece:
            out.append(_mk(strategy, page, start, piece))
        if start + size >= len(text):
            break
        start += size - overlap
    return out


def _split_sentences(par: str, max_size: int) -> list[str]:
    parts, cur = [], ""
    for s in re.split(r"(?<=[.!?])\s+", par):
        if cur and len(cur) + 1 + len(s) > max_size:
            parts.append(cur)
            cur = s
        else:
            cur = f"{cur} {s}".strip()
        while len(cur) > max_size:            # one over-long sentence: hard split on a space
            cut = cur.rfind(" ", 0, max_size)
            cut = cut if cut > 0 else max_size
            parts.append(cur[:cut])
            cur = cur[cut:].strip()
    if cur:
        parts.append(cur)
    return parts


def by_paragraph(page: DocumentPage, max_size: int, strategy: str = "B") -> list[Chunk]:
    """Pack whole paragraphs up to max_size; a heading line is glued to the paragraph after it."""
    paras = [p.strip() for p in page.text.split("\n\n") if p.strip()]
    units: list[str] = []
    for p in paras:
        units.extend([p] if len(p) <= max_size else _split_sentences(p, max_size))
    glued: list[str] = []
    i = 0
    while i < len(units):
        u = units[i]
        if (len(u) < 70 and not re.search(r"[.!?:)]$", u) and i + 1 < len(units)
                and len(u) + 1 + len(units[i + 1]) <= max_size):
            glued.append(f"{u} {units[i + 1]}")
            i += 2
        else:
            glued.append(u)
            i += 1
    out, cur, offset, pos = [], "", 0, 0
    for u in glued:
        if cur and len(cur) + 1 + len(u) > max_size:
            out.append(_mk(strategy, page, offset, cur))
            cur, offset = u, pos
        else:
            if not cur:
                offset = pos
            cur = f"{cur} {u}".strip()
        pos += len(u) + 1
    if cur:
        out.append(_mk(strategy, page, offset, cur))
    return out
