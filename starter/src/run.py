"""Day 06 pipeline: ingest strategies A/B, re-ingest check, run A/B/C on the benchmark, save traces + metrics.

    python -m src.run            (from starter/, with Docker postgres up and data/pages.jsonl built)
"""
import json
import os
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from . import config as cfg
from .chunking import by_paragraph, fixed_size
from .embeddings import MyEmbedder
from .evaluation import evaluate_query, summarize
from .models import DocumentPage
from .store import PgVectorStore


def load_pages() -> list[DocumentPage]:
    pages = []
    for line in cfg.PAGES_JSONL.open(encoding="utf-8"):
        d = json.loads(line)
        pages.append(DocumentPage(d["document_id"], d["source"], d["page"], d["text"],
                                  {"section": d["section"], "section_title": d["section_title"], "chars": d["chars"]}))
    return pages


def build_chunks(pages: list[DocumentPage]) -> dict[str, list]:
    return {
        "A": [c for p in pages for c in fixed_size(p, cfg.A_SIZE, cfg.A_OVERLAP, "A")],
        "B": [c for p in pages for c in by_paragraph(p, cfg.B_MAX, "B")],
    }


def length_stats(chunks, embedder) -> dict:
    lens = sorted(len(c.text) for c in chunks)
    tok = embedder._model.tokenizer
    tokens = sum(len(tok(c.text, add_special_tokens=False)["input_ids"]) for c in chunks)
    return {"chunks": len(chunks), "chars_total": sum(lens), "tokens_total_estimate": tokens,
            "len_min": lens[0], "len_median": statistics.median(lens), "len_p95": lens[int(0.95 * (len(lens) - 1))],
            "len_max": lens[-1]}


def main() -> None:
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    url = os.getenv("DATABASE_URL")
    if not url:
        sys.exit("DATABASE_URL missing: copy starter/.env.example to starter/.env")
    cfg.RESULTS.mkdir(parents=True, exist_ok=True)
    pages = load_pages()
    if len(pages) < 30:
        sys.exit(f"only {len(pages)} content pages (need >= 30)")
    questions = [json.loads(x) for x in cfg.BENCHMARK.open(encoding="utf-8") if x.strip()]

    t0 = time.perf_counter()
    embedder = MyEmbedder(cfg.EMBEDDING_MODEL, cfg.EMBEDDING_DIMS)
    model_load_s = time.perf_counter() - t0
    store = PgVectorStore(url, embedder.dimensions)
    store.create_schema()
    strategies = build_chunks(pages)

    # ---- ingest A and B (timed) -------------------------------------------------------------
    ingest = {"model": cfg.EMBEDDING_MODEL, "dimensions": embedder.dimensions, "model_load_seconds": round(model_load_s, 2),
              "cost_usd": 0.0, "pages": len(pages), "run_at": datetime.now(timezone.utc).isoformat()}
    for name, chunks in strategies.items():
        t = time.perf_counter()
        vectors = embedder.embed_documents([c.text for c in chunks])
        embed_s = time.perf_counter() - t
        t = time.perf_counter()
        res = store.upsert(name, chunks, vectors)
        write_s = time.perf_counter() - t
        # ---- re-ingest the very same version: row count must not change --------------------
        before = store.count(name)
        res2 = store.upsert(name, chunks, vectors)
        after = store.count(name)
        ingest[name] = {**length_stats(chunks, embedder), "embed_seconds": round(embed_s, 2), "write_seconds": round(write_s, 2),
                        "ingest_seconds_total": round(embed_s + write_s, 2), "first_load": res,
                        "reingest": {"count_before": before, "count_after": after, "stale_deleted": res2["stale_deleted"],
                                     "duplicates_created": after - before}}
        print(f"[{name}] chunks={len(chunks)} embed={embed_s:.1f}s reingest {before}->{after}")
    (cfg.RESULTS / "ingest_stats.json").write_text(json.dumps(ingest, indent=2), encoding="utf-8")

    # ---- run A, B, C -------------------------------------------------------------------------
    run_plan = [("A", "A", False), ("B", "B", False), ("C", "B", True)]   # (label, index, use_filter)
    traces, search_seconds = [], {}
    for label, index, use_filter in run_plan:
        t = time.perf_counter()
        for q in questions:
            filters = q["filter"] if (use_filter and q.get("filter")) else None
            hits = store.search(index, embedder.embed_query(q["question"]), cfg.TOP_K, filters)
            ev = evaluate_query(q, hits)
            traces.append({"strategy": label, "index": index, "question_id": q["id"], "split": q["split"],
                           "question": q["question"], "filter_used": filters, "gold_page": q["gold_page"],
                           "evidence_quote": q["evidence_quote"], "hits": hits, **ev})
        search_seconds[label] = round(time.perf_counter() - t, 2)
    for label in "ABC":
        with (cfg.RESULTS / f"traces_{label}.jsonl").open("w", encoding="utf-8") as f:
            for t in traces:
                if t["strategy"] == label:
                    f.write(json.dumps(t, ensure_ascii=False) + "\n")
    metrics = {"metrics": summarize(traces), "search_seconds_22_queries": search_seconds,
               "top_k": cfg.TOP_K, "metric": "cosine, exact search (no ANN index)"}
    (cfg.RESULTS / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    for k, v in metrics["metrics"].items():
        print(f"{k:10s} n={v['n']:2d} hit@1={v['hit1']:2d} hit@3={v['hit3']:2d}")


if __name__ == "__main__":
    main()
