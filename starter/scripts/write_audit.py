"""Write manual-audit CSVs. The 0/1/2 labels below were assigned by reading the chunk texts in
results/analysis.json and results/traces_*.jsonl (labeller: Claude, AI-assisted, to be reviewed by the author).
Scores are not derived from Hit@k. Rubric: GUIDE.md section 4 (coherence & grounding, scale 0-2)."""
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src import config as cfg  # noqa: E402

AUDIT = cfg.RESULTS / "audit"
AUDIT.mkdir(parents=True, exist_ok=True)

# page -> (A score, A reason) / (B score, B reason); C uses B's chunks (identical text) -> same label
COH_A = {
    249: (0, "starts mid-word ('ss the security...') and stops at 'by asking': the two-factor idea is cut off"),
    250: (1, "starts mid-sentence, ends mid-word 'ne'; gist about OS families understandable"),
    251: (1, "starts mid-word ('s monitoring...'), ends 'access levels and a'; gist ok, context missing"),
    252: (1, "table tail + heading + paragraph cut mid-sentence; mixes two topics"),
    253: (1, "starts mid-sentence ('cal computer and...'), ends mid-word; VM idea partly there"),
    254: (0, "starts 'It also consists of address space' with unresolved 'It'; ends mid-sentence"),
    255: (1, "starts mid-word ('iles (i.e., streams)'); abstractions idea understandable"),
    256: (1, "ends open-source discussion and starts 'Protected Sharing', cut mid-sentence at both ends"),
    257: (1, "starts mid-word, ends with dangling heading 'Process Management and Threads'"),
    258: (1, "table fragment then definition; cut mid-sentence at both ends"),
}
COH_B = {
    249: (2, "whole introduction paragraph(s), self-contained (stops before the two solutions)"),
    250: (2, "heading + complete paragraph about OS families"),
    251: (2, "complete paragraph on authentication; lacks the heading 'Monitoring Access' but readable"),
    252: (2, "complete paragraph; heading sits in previous chunk but the content stands alone"),
    253: (2, "heading + virtualization definitions, whole paragraph kept"),
    254: (2, "complete paragraph about processes"),
    255: (2, "complete paragraph about isolating hardware from programs"),
    256: (2, "heading + complete 'Protected Sharing' paragraph"),
    257: (1, "starts with 'For example, in Figure 6.5' (refers to a sentence in previous chunk) and ends with a dangling heading"),
    258: (2, "complete definitions of program/process/processor"),
}
# (strategy, qid) -> (score, reason) for top-3 evidence sufficiency
GROUND = {
    ("A", "t01"): (0, "chunk 1 is the right passage but is cut right before 'zombie state'; the definition is not in top-3"),
    ("B", "t01"): (2, "top-1 holds the complete zombie-state sentence and the process-table explanation"),
    ("C", "t01"): (2, "same chunks as B"),
    ("A", "t02"): (2, "top-1/2 define thrashing and its cause (definition cut at the very end of chunk 1 but sufficient)"),
    ("B", "t02"): (2, "chunk 3 gives the cycle 'more time moving data than executing processes' + cause; chunk 1 explains the effect"),
    ("C", "t02"): (2, "filter keeps the thrashing chunks from 6.4; evidence sufficient"),
    ("A", "t03"): (2, "top-1 lists status/command/data registers with descriptions"),
    ("B", "t03"): (2, "top-1 states the three register types"),
    ("C", "t03"): (2, "same chunks as B"),
    ("A", "t04"): (1, "chunk 3 starts the right sentence but is cut before 'simple in programming and small in size'; condition missing"),
    ("B", "t04"): (2, "chunk 3 contains the full access-enforcement sentence with the 'simple and small' requirement"),
    ("C", "t04"): (2, "same chunks as B (all already in 6.6)"),
    ("A", "t05"): (2, "top-1 states GUI or command line (DOS)"),
    ("B", "t05"): (2, "rank-2 chunk contains 'or a command line (e.g., DOS)'; rank 1 gives surrounding context"),
    ("C", "t05"): (2, "same chunks as B"),
}


def main() -> None:
    an = json.loads((cfg.RESULTS / "analysis.json").read_text(encoding="utf-8"))
    with (AUDIT / "coherence.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["strategy", "page", "chunk_id", "score_0_2", "reason"])
        for r in an["coherence_material"]:
            sc, why = (COH_A if r["strategy"] == "A" else COH_B)[r["page"]]
            w.writerow([r["strategy"], r["page"], r["chunk_id"], sc, why])
    with (AUDIT / "metadata.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["strategy", "qid", "rank", "chunk_id", "page", "section_label", "section_true", "ok", "errors"])
        for m in an["metadata_audit"]:
            w.writerow([m["strategy"], m["qid"], m["rank"], m["chunk_id"], m["page"], m["section"], m["true_section"],
                        int(m["ok"]), m["errors"]])
    with (AUDIT / "grounding.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["strategy", "qid", "score_0_2", "reason"])
        for (s, q), (sc, why) in sorted(GROUND.items()):
            w.writerow([s, q, sc, why])
    print("audit CSVs written")


if __name__ == "__main__":
    main()
