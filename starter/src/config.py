"""Shared paths and fixed experiment parameters (single source of truth)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]          # repo root
RAW_PDF = ROOT / "data" / "raw" / "intro-cs.pdf"
PAGES_JSONL = ROOT / "data" / "pages.jsonl"
MANIFEST = ROOT / "data" / "manifest.json"
BENCHMARK = ROOT / "benchmark" / "questions.jsonl"
RESULTS = ROOT / "results"

DOCUMENT_ID = "openstax-intro-cs-ch6"
SOURCE_URL = "https://assets.openstax.org/oscms-prodcms/media/documents/Introduction_To_Computer_Science_-_WEB.pdf"
FIRST_PAGE, LAST_PAGE = 249, 294                    # physical PDF pages, 1-based, inclusive

# Chapter 6 section start pages from the PDF outline (physical page numbers).
SECTION_STARTS = [
    (249, "intro", "Chapter 6 Introduction / Chapter Outline"),
    (250, "6.1", "What Is an Operating System?"),
    (256, "6.2", "Fundamental OS Concepts"),
    (267, "6.3", "Processes and Concurrency"),
    (277, "6.4", "Memory Management"),
    (284, "6.5", "File Systems"),
    (289, "6.6", "Reliability and Security"),
]

EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
EMBEDDING_DIMS = 384

# Strategy parameters (A, B). C reuses B's index and only adds the section filter.
A_SIZE, A_OVERLAP = 500, 50
B_MAX = 800
TOP_K = 3
