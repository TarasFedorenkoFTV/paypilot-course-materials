"""The assertion ladder from L03, levels 1-7.

    1. Точна рівність          exact equality
    2. Число з допуском        a number within a tolerance
    3. Підрядок і патерн       substring / regex
    4. Негативна               must NOT appear
    5. Семантична схожість     semantic similarity over a threshold
    6. Статистична             k of n runs agree
    7. LLM-суддя               a judge against a rubric

The point of the ladder is cost: never climb higher than the case needs.
Levels 1-4 are free and deterministic, 5 needs embeddings, 6 needs repeated
runs, 7 needs a model call and carries a measured error of its own (L09).
"""
import re
from dataclasses import dataclass

LEVELS = {
    1: "exact",
    2: "numeric",
    3: "contains",
    4: "not_contains",
    5: "similar",
    6: "k_of_n",
    7: "judge",
}

# assertion name used in the case files -> ladder level
NAME_TO_LEVEL = {
    "equals": 1, "exact": 1, "exact_tool_calls": 1,
    "numeric": 2, "number": 2, "amount": 2, "budget": 2,
    "contains": 3, "regex": 3, "pattern": 3,
    "not_contains": 4, "absent": 4, "no_span": 4, "not_regex": 4,
    "tool_result_numeric": 2, "tool_result_flag": 1, "tool_call_count": 1,
    "similar": 5,
    "k_of_n": 6,
    "judge": 7,
}


@dataclass
class Verdict:
    passed: bool
    level: int
    assertion: str
    detail: str

    def as_dict(self):
        return {"passed": self.passed, "level": self.level,
                "assertion": self.assertion, "detail": self.detail}


_NUM_RE = re.compile(r"-?\d[\d\s,]*(?:\.\d+)?")


def _numbers(text: str) -> list[float]:
    out = []
    for raw in _NUM_RE.findall(text or ""):
        cleaned = raw.replace(",", "").replace(" ", "")
        try:
            out.append(float(cleaned))
        except ValueError:
            continue
    return out


# --------------------------------------------------------------------------
# levels 1-4: free and deterministic

def level1_exact(actual, expected) -> Verdict:
    ok = str(actual).strip() == str(expected).strip()
    return Verdict(ok, 1, "equals",
                   "" if ok else f"expected {expected!r}, got {str(actual)[:120]!r}")


def level2_numeric(answer: str, expected: float, tolerance: float = 0.01) -> Verdict:
    found = _numbers(answer)
    hit = [n for n in found if abs(n - float(expected)) <= tolerance]
    ok = bool(hit)
    return Verdict(ok, 2, "numeric",
                   "" if ok else f"expected {expected} +/-{tolerance}; "
                                 f"numbers in answer: {found[:8]}")


def level3_contains(answer: str, needle: str) -> Verdict:
    ok = needle.lower() in (answer or "").lower()
    return Verdict(ok, 3, "contains",
                   "" if ok else f"{needle!r} not in the answer")


def level3_regex(answer: str, pattern: str) -> Verdict:
    ok = bool(re.search(pattern, answer or "", re.I))
    return Verdict(ok, 3, "regex",
                   "" if ok else f"pattern {pattern!r} did not match")


def level4_not_contains(answer: str, needle: str) -> Verdict:
    ok = needle.lower() not in (answer or "").lower()
    return Verdict(ok, 4, "not_contains",
                   "" if ok else f"forbidden {needle!r} appeared in the answer")


def level4_not_regex(answer: str, pattern: str) -> Verdict:
    """A negative assertion on a PATTERN, not a literal. Needed because the
    agent rephrases freely: "you can dispute" and "you can still dispute" are
    the same verdict, and a literal negative silently passes on the second."""
    m = re.search(pattern, answer or "", re.I)
    return Verdict(not m, 4, "not_regex",
                   "" if not m else f"forbidden pattern matched {m.group(0)!r}")


def level4_no_span(trace: dict, span_name: str) -> Verdict:
    """A defect that is the ABSENCE of an action (D27) — the negative assertion
    the course insists on: you cannot read it from the reply text."""
    present = _has_span(trace, span_name)
    return Verdict(not present, 4, "no_span",
                   "" if not present else f"span {span_name} should not be there")


def _has_span(node: dict, name: str) -> bool:
    if node.get("name") == name:
        return True
    return any(_has_span(c, name) for c in node.get("children", []))


# --------------------------------------------------------------------------
# level 5: semantic similarity (kept dependency-free: token overlap)

def level5_similar(answer: str, reference: str, threshold: float = 0.5) -> Verdict:
    """Token-overlap stand-in for an embedding similarity. Deliberately simple:
    the teaching point is that level 5 costs more and answers a fuzzier
    question than levels 1-4, not which embedding model is best."""
    a = set(re.findall(r"[a-z0-9]+", (answer or "").lower()))
    b = set(re.findall(r"[a-z0-9]+", (reference or "").lower()))
    if not b:
        return Verdict(False, 5, "similar", "empty reference")
    score = len(a & b) / len(b)
    ok = score >= threshold
    return Verdict(ok, 5, "similar",
                   f"overlap {score:.2f} vs threshold {threshold}"
                   if not ok else f"overlap {score:.2f}")


# --------------------------------------------------------------------------
# level 6: statistical — k of n runs

def level6_k_of_n(results: list[bool], k: int) -> Verdict:
    hits = sum(bool(x) for x in results)
    ok = hits >= k
    return Verdict(ok, 6, "k_of_n",
                   f"{hits}/{len(results)} runs agreed, needed {k}")


# --------------------------------------------------------------------------
# level 7: LLM judge

def level7_judge(answer: str, rubric: str, question: str, judge_fn) -> Verdict:
    """`judge_fn(question, answer, rubric) -> (bool, str)` is injected so the
    suite stays runnable without a model (L09 measures the judge's own error
    before anyone trusts this level)."""
    ok, why = judge_fn(question, answer, rubric)
    return Verdict(bool(ok), 7, "judge", why)


# --------------------------------------------------------------------------
# tool-call assertions (L07): the payload, not the prose

def tool_calls_exact(trace: dict, expected: list[str]) -> Verdict:
    actual = _tool_sequence(trace)
    ok = actual == expected
    return Verdict(ok, 1, "exact_tool_calls",
                   "" if ok else f"expected {expected}, called {actual}")


def tool_called_with(trace: dict, tool: str, args: dict,
                     level: int = 1) -> Verdict:
    """Level 1 on an argument the customer named; level 2 when the argument is
    a money figure whose last cent depends on rounding."""
    for span in _spans(trace):
        if span.get("name") != f"tool.{tool}":
            continue
        actual = (span.get("attributes") or {}).get("tool.arguments") or {}
        misses = []
        for key, want in args.items():
            got = actual.get(key)
            if isinstance(want, (int, float)) and isinstance(got, (int, float)):
                if abs(float(got) - float(want)) > 0.01:
                    misses.append(f"{key}={got} != {want}")
            elif str(got) != str(want):
                misses.append(f"{key}={got!r} != {want!r}")
        if not misses:
            return Verdict(True, level, "tool_called_with", f"{tool} args match")
        return Verdict(False, level, "tool_called_with",
                       f"{tool}: " + "; ".join(misses))
    return Verdict(False, level, "tool_called_with", f"{tool} was never called")


def tool_result_numeric(trace: dict, tool: str, field: str,
                        expected: float, tolerance: float = 0.01) -> Verdict:
    """Assert on a field of the tool RESULT, not on the prose.

    A capable agent can recompute a correct answer from other fields the tool
    returned, hiding a lie in one of them (that is how D22 escapes a
    text-level check). The payload is where the defect lives, so that is where
    the assertion belongs."""
    for span in _spans(trace):
        if span.get("name") != f"tool.{tool}":
            continue
        result = (span.get("attributes") or {}).get("tool.result") or {}
        if field not in result:
            return Verdict(False, 2, "tool_result_numeric",
                           f"{tool} result has no field {field!r}")
        got = result[field]
        ok = isinstance(got, (int, float)) and abs(float(got) - float(expected)) <= tolerance
        return Verdict(ok, 2, "tool_result_numeric",
                       f"{tool}.{field} = {got}" if ok else
                       f"{tool}.{field} = {got}, expected {expected}")
    return Verdict(False, 2, "tool_result_numeric", f"{tool} was never called")


def tool_result_flag(trace: dict, tool: str, field: str, expected) -> Verdict:
    for span in _spans(trace):
        if span.get("name") != f"tool.{tool}":
            continue
        result = (span.get("attributes") or {}).get("tool.result") or {}
        got = result.get(field)
        ok = got == expected
        return Verdict(ok, 1, "tool_result_flag",
                       f"{tool}.{field} = {got}" if ok else
                       f"{tool}.{field} = {got!r}, expected {expected!r}")
    return Verdict(False, 1, "tool_result_flag", f"{tool} was never called")


def tool_call_count(trace: dict, tool: str, expected: int) -> Verdict:
    n = sum(1 for s in _spans(trace) if s.get("name") == f"tool.{tool}")
    ok = n == expected
    return Verdict(ok, 1, "tool_call_count",
                   f"{tool} called {n}x, expected {expected}x")


def _spans(node: dict):
    yield node
    for child in node.get("children", []):
        yield from _spans(child)


def _tool_sequence(trace: dict) -> list[str]:
    return [s["name"][5:] for s in _spans(trace)
            if str(s.get("name", "")).startswith("tool.")]
