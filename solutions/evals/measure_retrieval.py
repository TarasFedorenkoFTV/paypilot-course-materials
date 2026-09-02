"""Measure retrieval on both indexes at several n_results (L04).

Context recall and precision, computed against the `reference` field of the
l04 set — which is why that field is mandatory in the loader: without a
reference there is nothing to compute recall against.

Definitions used here, stated because the words are overloaded:

  recall     did ANY returned fragment carry the answer? (the figure from the
             reference appears in a fragment)
  precision  what share of the returned fragments carried any part of the
             reference? A high-k retrieval that buries one good fragment in
             four irrelevant ones has good recall and poor precision, and the
             generation step pays for the difference.

No model calls: this is a property of the index, so it is free and
deterministic.

    python measure_retrieval.py
"""
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import os  # noqa: E402
os.environ.setdefault("LLM_PROVIDER", "mock")
os.environ.setdefault("CLOCK_OVERRIDE", "2026-09-15T10:00:00Z")

from app.rag import retriever  # noqa: E402
from loader import load  # noqa: E402

KS = (1, 3, 5)
INDEXES = ("kb_clean", "kb_broken")


def _keys(reference: str) -> list[str]:
    """The atoms of a reference: the figures and the condition words that must
    travel together. A figure without its condition is the chunking defect."""
    figures = re.findall(r"\d[\d,]*(?:\.\d+)?%?", reference)
    words = [w for w in re.findall(r"[A-Za-z]{4,}", reference)
             if w.lower() not in ("must", "days", "than", "above", "with",
                                  "that", "this", "have", "into", "from")]
    return figures + words[:3]


def score(case: dict, index: str, k: int) -> tuple[float, float]:
    meta = case["additional_metadata"]
    reference = meta["reference"]
    keys = _keys(reference)
    if not keys:
        return (0.0, 0.0)
    result = retriever.search(case["input"], top_k=k, index=index)
    frags = result["fragments"]
    if not frags:
        return (0.0, 0.0)

    # recall: the answer figure is present in at least one fragment
    answer_key = case.get("expected_output") or keys[0]
    recall = 1.0 if any(str(answer_key).lower() in f["text"].lower()
                        for f in frags) else 0.0
    # precision: fragments carrying any reference atom
    relevant = sum(1 for f in frags
                   if any(str(key).lower() in f["text"].lower() for key in keys))
    precision = relevant / len(frags)
    return (recall, precision)


def main() -> int:
    cases = [c for c in load(HERE / "sets" / "l04_reference.jsonl")
             if c["additional_metadata"].get("reference")]
    print(f"{len(cases)} retrieval cases, indexes {INDEXES}, k in {KS}\n")
    print(f"{'index':<11}{'k':<4}{'recall':<10}{'precision':<12}{'frags/query'}")
    print("-" * 52)

    table = {}
    for index in INDEXES:
        for k in KS:
            rs, ps, ns = [], [], []
            for case in cases:
                r, p = score(case, index, k)
                rs.append(r)
                ps.append(p)
                ns.append(len(retriever.search(case["input"], top_k=k,
                                               index=index)["fragments"]))
            recall = sum(rs) / len(rs)
            precision = sum(ps) / len(ps)
            table[(index, k)] = {"recall": round(recall, 3),
                                 "precision": round(precision, 3),
                                 "frags": round(sum(ns) / len(ns), 1)}
            print(f"{index:<11}{k:<4}{recall:<10.1%}{precision:<12.1%}"
                  f"{sum(ns)/len(ns):.1f}")

    print("\nper-case recall, kb_clean k=3 vs kb_broken k=3:")
    for case in cases:
        rc, _ = score(case, "kb_clean", 3)
        rb, _ = score(case, "kb_broken", 3)
        if rc != rb:
            print(f"  {case['id']:<10} clean {'hit' if rc else 'miss':<5} "
                  f"broken {'hit' if rb else 'miss':<5} "
                  f"expected {case.get('expected_output')!r}")

    out = HERE / "reports" / "retrieval-measurement.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(
        {"cases": len(cases),
         "table": {f"{i}@{k}": v for (i, k), v in table.items()}},
        indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n-> {out.relative_to(HERE)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
