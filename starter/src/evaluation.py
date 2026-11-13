"""Automatic retrieval metrics. Manual coherence / grounding labels are NOT inferred here."""
from collections import defaultdict
from typing import Any

from .ingestion import flat


def _gold_pages(question: dict[str, Any]) -> set[int]:
    gp = question["gold_page"]
    return {int(x) for x in (gp if isinstance(gp, list) else [gp])}


def is_hit(question: dict[str, Any], hit: dict[str, Any]) -> bool:
    """Hit = chunk is from gold source+page AND contains the whole normalized evidence quote."""
    return (hit["document_id"] == question["gold_source_id"]
            and int(hit["page"]) in _gold_pages(question)
            and flat(question["evidence_quote"]) in flat(hit["text"]))


def evaluate_query(question: dict[str, Any], hits: list[dict[str, Any]]) -> dict[str, Any]:
    flags = [is_hit(question, h) for h in hits]
    # evidence present on the gold page across top-3 chunks but split between them -> report separately
    on_gold = [h for h in hits if h["document_id"] == question["gold_source_id"] and int(h["page"]) in _gold_pages(question)]
    split_evidence = (not any(flags)) and bool(on_gold) and \
        flat(question["evidence_quote"]) in flat(" ".join(h["text"] for h in on_gold))
    return {"hit1": bool(flags[:1] and flags[0]), "hit3": any(flags[:3]), "hit_flags": flags[:3],
            "gold_page_in_top3": bool(on_gold), "split_evidence": split_evidence}


def summarize(traces: list[dict[str, Any]]) -> dict[str, Any]:
    agg: dict[tuple[str, str], dict[str, int]] = defaultdict(lambda: {"n": 0, "hit1": 0, "hit3": 0})
    for t in traces:
        for split in (t["split"], "all"):
            a = agg[(t["strategy"], split)]
            a["n"] += 1
            a["hit1"] += int(t["hit1"])
            a["hit3"] += int(t["hit3"])
    return {f"{s}/{sp}": {**v, "hit1_rate": round(v["hit1"] / v["n"], 4), "hit3_rate": round(v["hit3"] / v["n"], 4)}
            for (s, sp), v in sorted(agg.items())}
