"""OpenTelemetry export to Arize Phoenix (the tracing UI the course uses).

The in-process tracer in app/tracing.py stays the primary, always-available
source (JSONL + API) so assertions never depend on a running collector. This
module mirrors finished span trees to an OTLP endpoint when one is configured,
using GenAI semantic-convention attribute names.

Enable with OTEL_EXPORTER_OTLP_ENDPOINT (docker compose sets it to Phoenix).
"""
import os

_enabled = False
_tracer = None


def init() -> bool:
    """Best-effort init; the stand must run fine with no collector present."""
    global _enabled, _tracer
    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "")
    if not endpoint:
        return False
    try:
        from opentelemetry import trace
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
            OTLPSpanExporter)
        provider = TracerProvider(resource=Resource.create(
            {"service.name": os.environ.get("OTEL_SERVICE_NAME", "paypilot-stand")}))
        provider.add_span_processor(BatchSpanProcessor(
            OTLPSpanExporter(endpoint=endpoint.rstrip("/") + "/v1/traces")))
        trace.set_tracer_provider(provider)
        _tracer = trace.get_tracer("paypilot.stand")
        _enabled = True
    except Exception:
        _enabled = False
    return _enabled


def _flatten(value):
    if isinstance(value, (str, bool, int, float)) or value is None:
        return value
    import json
    return json.dumps(value, ensure_ascii=False, default=str)


def export_tree(tree: dict) -> None:
    """Mirror one finished request tree into OTLP spans."""
    if not _enabled or _tracer is None:
        return
    try:
        _emit(tree, parent_ctx=None)
    except Exception:
        pass  # tracing must never break a request


def _emit(node: dict, parent_ctx):
    from opentelemetry import trace
    ctx = trace.set_span_in_context(parent_ctx) if parent_ctx else None
    with _tracer.start_as_current_span(node["name"], context=ctx) as span:
        for k, v in (node.get("attributes") or {}).items():
            span.set_attribute(k, _flatten(v))
        for child in node.get("children", []):
            _emit(child, span)
