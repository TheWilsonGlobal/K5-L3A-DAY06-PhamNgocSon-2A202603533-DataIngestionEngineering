"""Extract + normalize the chosen page range and write data/pages.jsonl and data/manifest.json."""
import datetime
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.config import (DOCUMENT_ID, FIRST_PAGE, LAST_PAGE, MANIFEST, PAGES_JSONL, RAW_PDF,  # noqa: E402
                        RESULTS, SECTION_STARTS, SOURCE_URL)
from src.ingestion import load_pdf  # noqa: E402


def main() -> None:
    errors: list[dict] = []
    pages = load_pdf(RAW_PDF, DOCUMENT_ID, SOURCE_URL, FIRST_PAGE, LAST_PAGE, errors)
    PAGES_JSONL.parent.mkdir(parents=True, exist_ok=True)
    RESULTS.mkdir(parents=True, exist_ok=True)
    with PAGES_JSONL.open("w", encoding="utf-8") as f:
        for p in pages:
            f.write(json.dumps({"document_id": p.document_id, "source": p.source, "page": p.page,
                                "text": p.text, **p.metadata}, ensure_ascii=False) + "\n")
    (RESULTS / "errors.log").write_text(
        "\n".join(json.dumps(e) for e in errors) + ("\n" if errors else ""), encoding="utf-8")
    from pypdf import PdfReader
    total = len(PdfReader(str(RAW_PDF)).pages)
    manifest = {
        "documents": [{
            "source_id": DOCUMENT_ID,
            "title": "Introduction to Computer Science (OpenStax), Chapter 6: Infrastructure Abstraction Layer: Operating Systems",
            "source_path_or_url": SOURCE_URL,
            "local_copy": "data/raw/intro-cs.pdf (not committed: CC BY-NC-SA, download with the URL above)",
            "license_or_permission": "CC BY-NC-SA 4.0 (Rice University, OpenStax). Used for non-commercial coursework, not redistributed.",
            "accessed_at": datetime.date.today().isoformat(),
            "pdf_sha256": hashlib.sha256(RAW_PDF.read_bytes()).hexdigest(),
            "physical_pages_in_pdf": total,
            "page_range_considered": [FIRST_PAGE, LAST_PAGE],
            "counting_rule": "Every physical page 249-294 of the PDF (the whole chapter body, from chapter opener to the "
                             "end of 6.6). Excluded: Chapter Review (295+), key terms, quizzes. A page counts only if its "
                             "normalized text has >= 200 characters.",
            "counted_pages": [p.page for p in pages],
            "counted_page_count": len(pages),
            "rejected_pages": errors,
            "chars_per_page": {str(p.page): p.metadata["chars"] for p in pages},
            "total_chars": sum(p.metadata["chars"] for p in pages),
            "section_field": {"source": "PDF outline (bookmarks)", "type": "string",
                              "values": [s[1] for s in SECTION_STARTS],
                              "rule": "section of page = last outline entry whose start page <= page",
                              "limitation": "a heading in mid-page labels the whole page with the new section"},
        }],
    }
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"pages kept: {len(pages)}  rejected: {len(errors)}  chars: {manifest['documents'][0]['total_chars']}")


if __name__ == "__main__":
    main()
