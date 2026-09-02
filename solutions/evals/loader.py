"""Set loader — the `loader.py` the homework keeps referring to (ДЗ4-ДЗ8).

One loader for every set: the single-reply Golden set (L03), retrieval cases
(L04), dialogs (L05), security cases (L06), tool-call cases (L07) and budget
cases (L08) all go through this. That is the point of a shared schema — the
gate on L13 loads whatever the student added without new code.

Schema (from the ДЗ examples):
  id                required
  input             single-reply cases
  turns             dialog cases: [{"role": ..., "content": ...}]
  expected_output   may be null when only the payload/state is checked
  context           {"customer_id": ..., ...}
  additional_metadata:
      layer         generation | retrieval | memory | action | judge
      oracle        engine | corpus | human
      assertion     name from assertions.NAME_TO_LEVEL
      severity      low | medium | high | critical      (required, 100%)
      source        complaint | engine | red team | ...  (required)
      runs          how many repetitions the case needs
      added_in      lesson id
      gate          daily | release                     (L06 onward)
      vector        user_turn | history | tool_result | retrieval_context
      reference     required for retrieval cases (context recall needs it)
      invariants    dialog cases
      budget        {"identical_tool_calls_max", "tokens_total", "latency_ms"}
"""
import hashlib
import json
from pathlib import Path

from assertions import NAME_TO_LEVEL

REQUIRED = ("id",)
REQUIRED_META = ("layer", "oracle", "assertion", "severity", "source")
LAYERS = {"generation", "retrieval", "memory", "action", "judge", "orchestration"}
ORACLES = {"engine", "corpus", "human"}
SEVERITIES = {"low", "medium", "high", "critical"}
GATES = {"daily", "release"}


class SetError(ValueError):
    pass


def load(path: str | Path) -> list[dict]:
    """Read a .jsonl set and validate it. Raises on the first structural
    problem — a set that loads but is wrong silently poisons every number
    downstream."""
    path = Path(path)
    if not path.exists():
        raise SetError(f"set not found: {path}")
    cases, seen = [], set()
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("//"):
            continue
        try:
            case = json.loads(line)
        except json.JSONDecodeError as e:
            raise SetError(f"{path.name}:{lineno}: bad JSON — {e}") from e
        _validate(case, f"{path.name}:{lineno}")
        if case["id"] in seen:
            raise SetError(f"{path.name}:{lineno}: duplicate id {case['id']}")
        seen.add(case["id"])
        cases.append(case)
    if not cases:
        raise SetError(f"{path.name}: no cases")
    return cases


def _validate(case: dict, where: str) -> None:
    for key in REQUIRED:
        if not case.get(key):
            raise SetError(f"{where}: missing {key}")
    if not case.get("input") and not case.get("turns"):
        raise SetError(f"{where}: needs either input or turns")
    meta = case.get("additional_metadata") or {}
    for key in REQUIRED_META:
        if not meta.get(key):
            raise SetError(f"{where}: additional_metadata.{key} is required")
    if meta["layer"] not in LAYERS:
        raise SetError(f"{where}: unknown layer {meta['layer']!r}")
    if meta["oracle"] not in ORACLES:
        raise SetError(f"{where}: unknown oracle {meta['oracle']!r}")
    if meta["severity"] not in SEVERITIES:
        raise SetError(f"{where}: unknown severity {meta['severity']!r}")
    if meta["assertion"] not in NAME_TO_LEVEL:
        raise SetError(f"{where}: unknown assertion {meta['assertion']!r}")
    if meta.get("gate") and meta["gate"] not in GATES:
        raise SetError(f"{where}: unknown gate {meta['gate']!r}")
    if meta["layer"] == "retrieval" and not meta.get("reference"):
        raise SetError(f"{where}: retrieval cases need a reference "
                       "(context recall cannot be computed without it)")
    if case.get("turns"):
        for t in case["turns"]:
            if t.get("role") not in ("user", "assistant"):
                raise SetError(f"{where}: bad turn role {t.get('role')!r}")


def set_hash(path: str | Path) -> str:
    """Content hash of the set — one of the six fields a run record carries
    (ДЗ12). Adding a case must change it, so two runs can be compared only
    when the hash matches."""
    data = Path(path).read_bytes()
    return hashlib.sha256(data).hexdigest()[:12]


def summarise(cases: list[dict]) -> dict:
    """The coverage numbers the rubrics ask for."""
    meta = [c.get("additional_metadata", {}) for c in cases]
    levels = {NAME_TO_LEVEL[m["assertion"]] for m in meta}
    return {
        "cases": len(cases),
        "layers": _count(m["layer"] for m in meta),
        "oracles": _count(m["oracle"] for m in meta),
        "sources": _count(m["source"] for m in meta),
        "severities": _count(m["severity"] for m in meta),
        "ladder_levels": sorted(levels),
        "gates": _count(m.get("gate", "-") for m in meta),
        "human_oracle_pct": round(
            100 * sum(1 for m in meta if m["oracle"] == "human") / len(meta), 1),
        "severity_filled_pct": round(
            100 * sum(1 for m in meta if m.get("severity")) / len(meta), 1),
    }


def _count(values) -> dict:
    out = {}
    for v in values:
        out[v] = out.get(v, 0) + 1
    return dict(sorted(out.items()))
