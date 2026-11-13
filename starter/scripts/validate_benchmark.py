"""Check benchmark structure and verify every evidence quote against the normalized pages."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.config import BENCHMARK, PAGES_JSONL  # noqa: E402
from src.ingestion import flat  # noqa: E402


def main() -> int:
    pages = {}
    for line in PAGES_JSONL.open(encoding="utf-8"):
        d = json.loads(line)
        pages[(d["document_id"], d["page"])] = d
    qs = [json.loads(x) for x in BENCHMARK.open(encoding="utf-8") if x.strip()]
    problems = []
    ids = [q["id"] for q in qs]
    if len(ids) != len(set(ids)):
        problems.append("duplicate ids")
    dev = [q for q in qs if q["split"] == "dev"]
    test = [q for q in qs if q["split"] == "test"]
    filt = [q for q in qs if q.get("filter")]
    if len(qs) < 20 or len(dev) < 15 or len(test) < 5:
        problems.append(f"counts: total={len(qs)} dev={len(dev)} test={len(test)}")
    if len(filt) < 3 or not any(q["split"] == "test" for q in filt):
        problems.append("need >=3 filter questions with >=1 in test")
    dev_pages = {q["gold_page"] for q in dev}
    leak = [q["id"] for q in test if q["gold_page"] in dev_pages]
    if leak:
        problems.append(f"test questions sharing a gold page with dev: {leak}")
    for q in qs:
        gp = q["gold_page"] if isinstance(q["gold_page"], list) else [q["gold_page"]]
        quote = flat(q["evidence_quote"])
        found_on = [p for (doc, p), d in pages.items() if doc == q["gold_source_id"] and quote in flat(d["text"])]
        if not any(p in found_on for p in gp):
            problems.append(f"{q['id']}: quote not on gold page(s) {gp} (found on {found_on})")
        if set(found_on) - set(gp):
            problems.append(f"{q['id']}: quote also appears on {sorted(set(found_on) - set(gp))} -> add to gold_page")
        if q.get("filter"):
            for p in gp:
                sec = pages[(q["gold_source_id"], p)]["section"]
                if sec != q["filter"]["section"]:
                    problems.append(f"{q['id']}: filter {q['filter']} excludes gold page {p} (section {sec})")
    print(f"questions={len(qs)} dev={len(dev)} test={len(test)} filter={len(filt)} "
          f"(filter in test: {sum(1 for q in filt if q['split'] == 'test')})")
    for p in problems:
        print("PROBLEM:", p)
    print("benchmark OK" if not problems else f"{len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
