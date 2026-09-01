"""Provider adapter contract.

Internal message format (provider-neutral, used by the orchestration loop):
  {"role": "user", "content": str}
  {"role": "assistant", "content": str|None, "tool_calls": [ToolCall]|None}
  {"role": "tool", "tool_call_id": str, "name": str, "content": str}

ToolCall: {"id": str, "name": str, "arguments": dict}
Tool specs arrive in the neutral form of tools.specs():
  {"name", "description", "input_schema"}"""
from dataclasses import dataclass, field


@dataclass
class ModelResponse:
    text: str | None = None
    tool_calls: list[dict] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    model: str = ""


class Provider:
    name = "base"

    def complete(self, system: str, messages: list[dict],
                 tools: list[dict]) -> ModelResponse:
        raise NotImplementedError


def get_provider():
    from app import config
    kind = config.LLM_PROVIDER
    if kind == "mock":
        from app.agent.providers.mock import MockProvider
        return MockProvider()
    if kind == "anthropic":
        from app.agent.providers.anthropic_provider import AnthropicProvider
        return AnthropicProvider()
    if kind == "openai":
        from app.agent.providers.openai_provider import OpenAIProvider
        return OpenAIProvider()
    raise ValueError(f"Unknown LLM_PROVIDER={kind!r} (mock | anthropic | openai)")
