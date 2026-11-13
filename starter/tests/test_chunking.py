import json
import unittest

from src import config as cfg
from src.chunking import by_paragraph, fixed_size
from src.ingestion import flat, normalize_text
from src.models import DocumentPage


def pages():
    out = []
    with cfg.PAGES_JSONL.open(encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            out.append(DocumentPage(d["document_id"], d["source"], d["page"], d["text"],
                                    {"section": d["section"], "section_title": d["section_title"]}))
    return out


class ChunkingTests(unittest.TestCase):
    def test_corpus_has_at_least_30_pages(self):
        self.assertGreaterEqual(len(pages()), 30)

    def test_fixed_size_bounds_and_no_empty(self):
        for p in pages():
            for c in fixed_size(p, cfg.A_SIZE, cfg.A_OVERLAP):
                self.assertTrue(0 < len(c.text) <= cfg.A_SIZE)
                self.assertEqual(c.page, p.page)

    def test_fixed_size_covers_whole_page(self):
        p = pages()[3]
        cs = fixed_size(p, 500, 50)
        self.assertTrue(flat(p.text).startswith(cs[0].text))
        self.assertTrue(flat(p.text).endswith(cs[-1].text))
        for a, b in zip(cs, cs[1:]):                      # overlap really exists
            self.assertIn(b.text[:30], flat(p.text))

    def test_by_paragraph_bounds_and_metadata(self):
        for p in pages():
            for c in by_paragraph(p, cfg.B_MAX):
                self.assertTrue(0 < len(c.text) <= cfg.B_MAX)
                self.assertEqual((c.document_id, c.page, c.metadata["section"]), (p.document_id, p.page, p.metadata["section"]))
                self.assertIn(c.text, flat(p.text))

    def test_chunk_ids_stable_and_unique(self):
        cs = [c for p in pages() for c in by_paragraph(p, cfg.B_MAX)]
        self.assertEqual(len({c.chunk_id for c in cs}), len(cs))
        self.assertEqual([c.chunk_id for c in cs], [c.chunk_id for p in pages() for c in by_paragraph(p, cfg.B_MAX)])

    def test_normalize_strips_footer(self):
        t = normalize_text("Real sentence here.\nAccess for free at openstax.org\n6.3 ● Processes and Concurrency 259\n")
        self.assertEqual(t, "Real sentence here.")


if __name__ == "__main__":
    unittest.main()
