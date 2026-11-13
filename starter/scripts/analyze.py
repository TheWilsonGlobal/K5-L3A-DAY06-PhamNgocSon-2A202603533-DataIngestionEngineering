"""Post-run analysis: truncation check, per-question table, metadata audit, audit-sample material.

Samples are fixed by rule (not by looking at scores):
  coherence : the 10 lowest page IDs (249-258); the position is the middle character of the page's
              whitespace-collapsed text; the chunk covering that position is judged for each strategy.
  metadata/grounding : questions t01-t05 (the first five test ids) x top-3 x {A,B,C}.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src import config as cfg  # noqa: E402
from src.chunking import by_paragraph, fixed_size  # noqa: E402
from src.ingestion import flat, section_for  # noqa: E402
from src.run import load_pages  # noqa: E402

AUDIT_Q = ["t01", "t02", "t03", "t04", "t05"]


def main() -> None:
    pages = load_pages()
    page_flat = {p.page: flat(p.text) for p in pages}
    out = {}

    # 1. embedding truncation (model max_seq_length) -------------------------------------------
    from sentence_transformers import SentenceTransformer
    m = SentenceTransformer(cfg.EMBEDDING_MODEL, device="cpu")
    tok, max_len = m.tokenizer, m.max_seq_length
    chunks = {"A": [c for p in pages for c in fixed_size(p, cfg.A_SIZE, cfg.A_OVERLAP, "A")],
              "B": [c for p in pages for c in by_paragraph(p, cfg.B_MAX, "B")]}
    out["max_seq_length"] = max_len
    out["truncated_chunks"] = {}
    for s, cs in chunks.items():
        tl = [len(tok(c.text, add_special_tokens=True)["input_ids"]) for c in cs]
        out["truncated_chunks"][s] = {"over_limit": sum(t > max_len for t in tl), "total": len(cs), "max_tokens": max(tl)}

    # 2. per-question table ---------------------------------------------------------------------
    traces = {s: [json.loads(x) for x in (cfg.RESULTS / f"traces_{s}.jsonl").open(encoding="utf-8")] for s in "ABC"}
    rows = []
    for i, t in enumerate(traces["A"]):
        row = {"id": t["question_id"], "split": t["split"], "gold_page": t["gold_page"]}
        for s in "ABC":
            tt = traces[s][i]
            row[s] = {"top3_pages": [h["page"] for h in tt["hits"]], "hit1": tt["hit1"], "hit3": tt["hit3"],
                      "split_evidence": tt["split_evidence"], "gold_page_in_top3": tt["gold_page_in_top3"]}
        rows.append(row)
    out["per_question"] = rows

    # 3. metadata audit on t01-t05 x top-3 (automatic, content-position based) --------------------
    def true_section(page: int, text: str) -> str:
        """Section of the text's actual position: headings '6.n Title' inside the page flip the section."""
        pf = page_flat[page]
        pos = pf.find(flat(text)[:60])
        sec = section_for(page - 1)[0] if page > cfg.FIRST_PAGE else "intro"   # section at the page start
        for _, sid, title in cfg.SECTION_STARTS:
            if sid == "intro":
                continue
            h = pf.find(f"{sid} {title}")
            if h != -1 and 0 <= h <= pos:
                sec = sid
        return sec

    meta = []
    for s in "ABC":
        for t in traces[s]:
            if t["question_id"] not in AUDIT_Q:
                continue
            for rank, h in enumerate(t["hits"], 1):
                errs = []
                if h["document_id"] != cfg.DOCUMENT_ID:
                    errs.append("document_id")
                if h["source"] != cfg.SOURCE_URL:
                    errs.append("source")
                if flat(h["text"]) not in page_flat.get(h["page"], ""):
                    errs.append("page: chunk text not on claimed page")
                ts = true_section(h["page"], h["text"])
                if ts != h["section"]:
                    errs.append(f"section label {h['section']} but chunk content lies in {ts}")
                if t["filter_used"] and h["section"] != t["filter_used"]["section"]:
                    errs.append("filter violated")
                meta.append({"strategy": s, "qid": t["question_id"], "rank": rank, "chunk_id": h["chunk_id"],
                             "page": h["page"], "section": h["section"], "true_section": ts,
                             "ok": not errs, "errors": "; ".join(errs)})
    out["metadata_audit"] = meta
    (cfg.RESULTS / "audit").mkdir(parents=True, exist_ok=True)

    # 4. coherence sample material ------------------------------------------------------------
    coh = []
    for s, cs in chunks.items():
        for p in sorted(page_flat)[:10]:
            mid = len(page_flat[p]) // 2
            for c in cs:
                if c.page != p:
                    continue
                st = page_flat[p].find(c.text[:60])
                if st != -1 and st <= mid < st + len(c.text):
                    coh.append({"strategy": s, "page": p, "chunk_id": c.chunk_id, "text": c.text})
                    break
    coh_c = [dict(r, strategy="C") for r in coh if r["strategy"] == "B"]       # C uses B's chunks
    out["coherence_material"] = coh + coh_c
    (cfg.RESULTS / "analysis.json").write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(out["truncated_chunks"]), "max_seq", max_len)
    print("metadata records:", len(meta), "ok:", sum(m["ok"] for m in meta))


if __name__ == "__main__":
    main()
