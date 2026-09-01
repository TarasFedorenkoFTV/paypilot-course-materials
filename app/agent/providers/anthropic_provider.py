"""Anthropic Messages API over plain httpx (no SDK dependency)."""
import json

import httpx

from app import config
from app.agent.providers.base import ModelResponse, Provider

API_URL = "https://api.anthropic.com/v1/messages"
DEFAULT_MODEL = "claude-haiku-4-5"


def _to_anthropic(messages: list[dict]) -> list[dict]:
    out = []
    for m in messages:
        if m["role"] == "user":
            out.append({"role": "user", "content": m["content"]})
        elif m["role"] == "assistant":
            blocks = []
            if m.get("content"):
                blocks.append({"type": "text", "text": m["content"]})
            for tc in m.get("tool_calls") or []:
                blocks.append({"type": "tool_use", "id": tc["id"],
                               "name": tc["name"], "input": tc["arguments"]})
            out.append({"role": "assistant", "content": blocks})
        elif m["role"] == "tool":
            out.append({"role": "user", "content": [{
                "type": "tool_result", "tool_use_id": m["tool_call_id"],
                "content": m["content"]}]})
    return out


class AnthropicProvider(Provider):
    name = "anthropic"

    def __init__(self):
        if not config.ANTHROPIC_API_KEY:
            raise RuntimeError("ANTHROPIC_API_KEY is not set")
        self.model = config.LLM_MODEL or DEFAULT_MODEL

    def complete(self, system, messages, tools):
        payload = {
            "model": self.model,
            "max_tokens": 1024,
            "system": system,
            "messages": _to_anthropic(messages),
            "tools": [{"name": t["name"], "description": t["description"],
                       "input_schema": t["input_schema"]} for t in tools],
        }
        resp = httpx.post(API_URL, json=payload, timeout=60, headers={
            "x-api-key": config.ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01"})
        resp.raise_for_status()
        data = resp.json()
        text_parts, tool_calls = [], []
        for block in data.get("content", []):
            if block["type"] == "text":
                text_parts.append(block["text"])
            elif block["type"] == "tool_use":
                tool_calls.append({"id": block["id"], "name": block["name"],
                                   "arguments": block["input"]})
        usage = data.get("usage", {})
        return ModelResponse(
            text="\n".join(text_parts) or None, tool_calls=tool_calls,
            input_tokens=usage.get("input_tokens", 0),
            output_tokens=usage.get("output_tokens", 0),
            model=data.get("model", self.model))
