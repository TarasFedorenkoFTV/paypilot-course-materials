"""Knowledge-base search with two indexes (ТЗ §5.4).

kb_clean  — section-aware chunking with overlap: a table stays with the
            conditions it belongs to.
kb_broken — tiny fixed-size slices without overlap (D16): tables get cut,
            figures arrive without their conditions.

v1 scoring is deterministic lexical overlap (tf on shared terms). The
retriever interface (search() -> fragments with scores) is stable; a vector
backend can replace the scorer later without touching callers."""
import math
import re

from app import config, defects

_WORD_RE = re.compile(r"[a-z0-9_]+")


def _tokens(text: str) -> list[str]:
    return _WORD_RE.findall(text.lower())


def _load_docs() -> list[tuple[str, str]]:
    docs = []
    for path in sorted(config.CORPUS_DIR.glob("*.md")):
        docs.append((path.name, path.read_text(encoding="utf-8")))
    return docs


def _chunk_clean(name: str, text: str) -> list[dict]:
    """Split on '##' sections; keep the doc title with every chunk (overlap)."""
    title = text.splitlines()[0].removeprefix("# ").strip() if text else name
    parts = re.split(r"(?m)^## ", text)
    chunks = []
    for i, part in enumerate(parts[1:], 1):
        chunks.append({"id": f"{name}#s{i}", "doc": name,
                       "text": f"{title}\n## {part.strip()}"})
    return chunks


def _chunk_broken(name: str, text: str, size: int = 160) -> list[dict]:
    """Fixed-size slices, no overlap, no structure awareness (D16)."""
    flat = re.sub(r"\s+", " ", text).strip()
    return [{"id": f"{name}#b{i}", "doc": name, "text": flat[o:o + size]}
            for i, o in enumerate(range(0, len(flat), size), 1)]


def _build_index(kind: str) -> list[dict]:
    chunks = []
    for name, text in _load_docs():
        chunks.extend(_chunk_clean(name, text) if kind == "kb_clean"
                      else _chunk_broken(name, text))
    for c in chunks:
        c["tokens"] = _tokens(c["text"])
    return chunks


_indexes: dict[str, list[dict]] = {}


def _index(kind: str) -> list[dict]:
    if kind not in _indexes:
        _indexes[kind] = _build_index(kind)
    return _indexes[kind]


def active_index_name() -> str:
    if config.KB_INDEX_ENV:
        return config.KB_INDEX_ENV
    return "kb_broken" if defects.is_on("D16") else "kb_clean"


def active_top_k() -> int:
    return 1 if defects.is_on("D17") else config.RAG_TOP_K


def _score(query_tokens: list[str], chunk: dict) -> float:
    if not chunk["tokens"]:
        return 0.0
    hits = sum(chunk["tokens"].count(t) for t in set(query_tokens))
    return hits / math.sqrt(len(chunk["tokens"]))


def search(query: str, top_k: int | None = None, index: str | None = None) -> dict:
    kind = index or active_index_name()
    if kind not in ("kb_clean", "kb_broken"):
        raise ValueError(f"unknown index {kind!r}")
    k = top_k if top_k is not None else active_top_k()
    qt = _tokens(query)
    scored = sorted(((_score(qt, c), c) for c in _index(kind)),
                    key=lambda x: -x[0])
    fragments = [{"id": c["id"], "doc": c["doc"], "score": round(s, 4),
                  "text": c["text"]}
                 for s, c in scored[:k] if s > 0]
    return {"index": kind, "top_k": k, "query": query, "fragments": fragments}
