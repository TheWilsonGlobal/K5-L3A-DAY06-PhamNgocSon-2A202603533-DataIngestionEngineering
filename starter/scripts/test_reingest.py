"""Prove re-ingest of a changed document removes stale chunks (uses a throw-away strategy 'TMP')."""
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src import config as cfg  # noqa: E402
from src.chunking import by_paragraph  # noqa: E402
from src.embeddings import MyEmbedder  # noqa: E402
from src.run import load_pages  # noqa: E402
from src.store import PgVectorStore  # noqa: E402

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
emb = MyEmbedder(cfg.EMBEDDING_MODEL, cfg.EMBEDDING_DIMS)
store = PgVectorStore(os.environ["DATABASE_URL"], emb.dimensions)
pages = load_pages()[:6]
v1 = [c for p in pages for c in by_paragraph(p, cfg.B_MAX, "TMP")]
store.upsert("TMP", v1, emb.embed_documents([c.text for c in v1]))
n1 = store.count("TMP")
pages[0].text = pages[0].text + "\n\nAn extra paragraph added in version 2 of the document."     # changed document
v2 = [c for p in pages for c in by_paragraph(p, cfg.B_MAX, "TMP")]
res = store.upsert("TMP", v2, emb.embed_documents([c.text for c in v2]))
n2 = store.count("TMP")
stale_ids = {c.chunk_id for c in v1} - {c.chunk_id for c in v2}
import psycopg
with psycopg.connect(os.environ["DATABASE_URL"]) as c:
    left = c.execute("SELECT count(*) FROM chunks WHERE strategy='TMP' AND chunk_id = ANY(%s)", (list(stale_ids),)).fetchone()[0]
    c.execute("DELETE FROM chunks WHERE strategy='TMP'")
out = {"v1_chunks": len(v1), "count_after_v1": n1, "v2_chunks": len(v2), "count_after_v2": n2,
       "obsolete_chunk_ids": len(stale_ids), "obsolete_left_in_db": left, "stale_deleted_reported": res["stale_deleted"]}
(cfg.RESULTS / "reingest_changed_doc.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
print(out)
assert n2 == len(v2) and left == 0 and res["stale_deleted"] == len(stale_ids)
print("OK: stale chunks removed, no duplicates")
