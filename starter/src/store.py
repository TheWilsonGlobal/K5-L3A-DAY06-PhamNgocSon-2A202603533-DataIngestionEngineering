"""PostgreSQL + pgvector store: exact cosine search (no ANN index), metadata filter in SQL."""
import json
from typing import Any

import psycopg

from .models import Chunk

# Only these metadata keys may be used as SQL filters (column names are never taken from user input).
_FILTERABLE = {"section", "document_id", "page"}


class PgVectorStore:
    def __init__(self, database_url: str, dimensions: int) -> None:
        self.database_url = database_url
        self.dimensions = dimensions

    def _conn(self) -> psycopg.Connection:
        return psycopg.connect(self.database_url, connect_timeout=5)  # raises if backend is down

    def create_schema(self) -> None:
        with self._conn() as c:
            c.execute("CREATE EXTENSION IF NOT EXISTS vector")
            c.execute(f"""
                CREATE TABLE IF NOT EXISTS chunks (
                    chunk_id    text PRIMARY KEY,
                    strategy    text NOT NULL,
                    document_id text NOT NULL,
                    source      text NOT NULL,
                    page        int  NOT NULL,
                    section     text,
                    text        text NOT NULL,
                    metadata    jsonb NOT NULL DEFAULT '{{}}',
                    embedding   vector({self.dimensions}) NOT NULL
                )""")
            c.execute("CREATE INDEX IF NOT EXISTS chunks_strategy_section ON chunks (strategy, section)")
            c.execute("CREATE INDEX IF NOT EXISTS chunks_strategy_doc ON chunks (strategy, document_id)")
            # Deliberately NO ivfflat/hnsw index: corpus is tiny, search is exact.

    def upsert(self, strategy: str, chunks: list[Chunk], vectors: list[list[float]]) -> dict[str, int]:
        if len(chunks) != len(vectors):
            raise ValueError("chunks/vectors length mismatch")
        for v in vectors:
            if len(v) != self.dimensions:
                raise ValueError(f"vector has {len(v)} dims, store expects {self.dimensions}")
        ids = [c.chunk_id for c in chunks]
        docs = sorted({c.document_id for c in chunks})
        with self._conn() as c:
            # stale chunks of the same strategy+document that are not in this load are removed
            deleted = c.execute(
                "DELETE FROM chunks WHERE strategy = %s AND document_id = ANY(%s) AND NOT (chunk_id = ANY(%s))",
                (strategy, docs, ids)).rowcount
            with c.cursor() as cur:
                cur.executemany(
                    """INSERT INTO chunks (chunk_id, strategy, document_id, source, page, section, text, metadata, embedding)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s::vector)
                       ON CONFLICT (chunk_id) DO UPDATE SET text = EXCLUDED.text, metadata = EXCLUDED.metadata,
                           section = EXCLUDED.section, embedding = EXCLUDED.embedding""",
                    [(ch.chunk_id, strategy, ch.document_id, ch.source, ch.page, ch.metadata.get("section"),
                      ch.text, json.dumps(ch.metadata), "[" + ",".join(f"{x:.7f}" for x in v) + "]")
                     for ch, v in zip(chunks, vectors)])
        return {"written": len(chunks), "stale_deleted": deleted}

    def count(self, strategy: str) -> int:
        with self._conn() as c:
            return c.execute("SELECT count(*) FROM chunks WHERE strategy = %s", (strategy,)).fetchone()[0]

    def search(self, strategy: str, query_vector: list[float], top_k: int = 3,
               filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        if len(query_vector) != self.dimensions:
            raise ValueError("query vector dimension mismatch")
        where, params = ["strategy = %s"], [strategy]
        for key, value in (filters or {}).items():
            if key not in _FILTERABLE:
                raise ValueError(f"filter field {key!r} not allowed")
            where.append(f"{key} = %s")
            params.append(value)
        qv = "[" + ",".join(f"{x:.7f}" for x in query_vector) + "]"
        sql = f"""SELECT chunk_id, document_id, source, page, section, text, metadata,
                         1 - (embedding <=> %s::vector) AS score
                  FROM chunks WHERE {' AND '.join(where)}
                  ORDER BY embedding <=> %s::vector LIMIT %s"""
        with self._conn() as c:
            rows = c.execute(sql, [qv, *params, qv, top_k]).fetchall()
        return [{"chunk_id": r[0], "document_id": r[1], "source": r[2], "page": r[3], "section": r[4],
                 "text": r[5], "metadata": r[6], "score": float(r[7])} for r in rows]
