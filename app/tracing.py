"""Tracing: every request produces a span tree (ТЗ §5.6).

v1 implementation: an in-process tracer that keeps trees in memory and
appends them to traces/traces.jsonl — stable and documented, so students
can write assertions over spans programmatically (test API + file).
OTLP/Jaeger export hooks onto the same Span objects in a later pass.

Span attributes follow the GenAI semantic-convention names where they exist
(gen_ai.usage.input_tokens / output_tokens), plus the course-mandated ones:
tool args AND result, dialog step number, run id, active profile."""
import json
import threading
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field

from app import config, defects, otel

TRACE_FILE = config.TRACES_DIR / "traces.jsonl"
_lock = threading.Lock()
_store: dict[str, dict] = {}   # request_id -> tree (bounded)
_MAX_STORED = 500


@dataclass
class Span:
    name: str
    span_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    started_at: float = field(default_factory=time.time)
    ended_at: float | None = None
    attributes: dict = field(default_factory=dict)
    children: list = field(default_factory=list)

    def end(self) -> None:
        self.ended_at = time.time()

    def as_dict(self) -> dict:
        return {
            "name": self.name, "span_id": self.span_id,
            "started_at": self.started_at, "ended_at": self.ended_at,
            "duration_ms": round((self.ended_at - self.started_at) * 1000, 1)
            if self.ended_at else None,
            "attributes": self.attributes,
            "children": [c.as_dict() for c in self.children],
        }


class RequestTrace:
    def __init__(self, session_id: str, step_number: int):
        self.request_id = uuid.uuid4().hex[:16]
        self.root = Span("agent.request", attributes={
            "session.id": session_id,
            "dialog.step_number": step_number,
            "run.profile": config.PROFILE,
            "run.active_defects": sorted(defects.active()),
        })
        self._stack = [self.root]

    @contextmanager
    def span(self, name: str, **attributes):
        s = Span(name, attributes=attributes)
        self._stack[-1].children.append(s)
        self._stack.append(s)
        try:
            yield s
        finally:
            s.end()
            self._stack.pop()

    def finish(self) -> dict:
        self.root.end()
        tree = {"request_id": self.request_id, **self.root.as_dict()}
        with _lock:
            _store[self.request_id] = tree
            while len(_store) > _MAX_STORED:
                _store.pop(next(iter(_store)))
            with open(TRACE_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(tree, ensure_ascii=False) + "\n")
        otel.export_tree(tree)   # mirror to Phoenix when a collector is set
        return tree


def get(request_id: str) -> dict | None:
    return _store.get(request_id)


def recent(limit: int = 20) -> list[dict]:
    items = list(_store.values())
    return items[-limit:]
