"""The orchestration loop — owned and fully controlled (ТЗ §4.2).

The model → tool → model cycle is explicit here because two course defects
live inside it:
  D14 — an empty tool result is treated as a transient failure and the same
        call is retried, identical arguments, up to 8 times in a row; state
        stays intact, the cost is paid in latency and tokens;
  D15 — the full set of earlier tool results is re-appended to the context on
        every model call, so input tokens grow with every step.

Session history is kept in memory per session id. Summarization after
SUMMARIZE_AFTER_STEPS is the configured long-history strategy (D06 hooks in
there once live-model calibration starts)."""
import json
import uuid

from app import config, defects
from app.agent import prompt, summarize, tools
from app.agent.providers.base import get_provider
from app.tracing import RequestTrace

_sessions: dict[str, dict] = {}   # session_id -> {"messages": [...], "steps": int}

_EMPTY_RETRY_LIMIT = 8


def _is_empty_result(result: dict) -> bool:
    if not result:
        return True
    for value in result.values():
        if isinstance(value, (list, dict)) and not value:
            return True
    return False


def _session(session_id: str | None) -> tuple[str, dict]:
    sid = session_id or uuid.uuid4().hex[:12]
    state = _sessions.setdefault(sid, {"messages": [], "steps": 0})
    return sid, state


def reset_sessions() -> None:
    _sessions.clear()


def _messages_for_model(state: dict) -> list[dict]:
    messages = [dict(m) for m in state["messages"]]
    if defects.is_on("D15"):
        # re-read of history: every earlier tool result is re-appended to the
        # context on each call, so input tokens grow with each step. Fold the
        # replay into the FIRST user message so the tool_use/tool_result
        # adjacency the provider requires is never broken.
        earlier_tool_msgs = [m for m in messages if m["role"] == "tool"]
        if earlier_tool_msgs:
            replay = "\n\n".join(
                f"[replayed tool result: {m['name']}]\n{m['content']}"
                for m in earlier_tool_msgs)
            for m in messages:
                if m["role"] == "user":
                    m["content"] = f"(context replay)\n{replay}\n\n{m['content']}"
                    break
    return messages


def run_turn(session_id: str | None, user_message: str) -> dict:
    sid, state = _session(session_id)
    state["steps"] += 1
    trace = RequestTrace(sid, state["steps"])
    provider = get_provider()
    system, prompt_version = prompt.build()
    trace.root.attributes["prompt.version"] = prompt_version
    trace.root.attributes["llm.provider"] = provider.name
    # D15 marker: replay kicks in once there are prior-turn tool results to
    # re-append. Recorded so the inflation is detectable, not just visible.
    trace.root.attributes["context.replay_active"] = (
        defects.is_on("D15") and any(m["role"] == "tool" for m in state["messages"]))

    if summarize.should_summarize(state["steps"]) and not state.get("summarized"):
        with trace.span("agent.summarize") as s:
            summary = summarize.summarize_messages(provider, state["messages"])
            s.attributes.update({
                "summary.text": summary,
                "summary.replaced_messages": len(state["messages"]),
            })
        state["messages"] = [{"role": "user",
                              "content": f"(summary of earlier conversation)\n{summary}"}]
        state["summarized"] = True

    state["messages"].append({"role": "user", "content": user_message})
    answer = None
    total_in = total_out = 0

    for step in range(config.MAX_AGENT_STEPS):
        with trace.span("llm.call", **{"agent.loop_step": step}) as s:
            resp = provider.complete(system, _messages_for_model(state),
                                     tools.specs())
            s.attributes.update({
                "gen_ai.request.model": resp.model,
                "gen_ai.usage.input_tokens": resp.input_tokens,
                "gen_ai.usage.output_tokens": resp.output_tokens,
            })
        total_in += resp.input_tokens
        total_out += resp.output_tokens

        if not resp.tool_calls:
            answer = resp.text or ""
            state["messages"].append({"role": "assistant", "content": answer})
            break

        state["messages"].append({"role": "assistant", "content": resp.text,
                                  "tool_calls": resp.tool_calls})
        for tc in resp.tool_calls:
            result = _execute_tool(trace, tc)
            state["messages"].append({
                "role": "tool", "tool_call_id": tc["id"], "name": tc["name"],
                "content": json.dumps(result, ensure_ascii=False)})
            if defects.is_on("D14") and _is_empty_result(result):
                total_in, total_out = _d14_retry_loop(
                    trace, provider, system, state, tc, total_in, total_out)
    else:
        answer = "I could not complete this request within the step budget."
        state["messages"].append({"role": "assistant", "content": answer})

    trace.root.attributes.update({
        "gen_ai.usage.total_input_tokens": total_in,
        "gen_ai.usage.total_output_tokens": total_out,
    })
    tree = trace.finish()
    # elapsed_ms is in the response because latency is a requirement in US-01
    # and there was no surface to assert it on: the duration lived only on the
    # span tree, so a budget case had to fetch the trace to see a number the
    # turn already knew.
    return {"session_id": sid, "request_id": tree["request_id"],
            "answer": answer, "step_number": state["steps"],
            "elapsed_ms": tree.get("duration_ms"),
            "usage": {"input_tokens": total_in, "output_tokens": total_out}}


def _execute_tool(trace: RequestTrace, tc: dict) -> dict:
    """One tool call, recorded with its arguments and its result.

    D14 does NOT loop here. Retrying the tool in place costs nothing measurable
    (the tools are local), so the defect showed up in the trace shape while
    tokens and latency stayed flat — which contradicts what the defect is
    supposed to teach. The retry is driven from the orchestration loop
    instead: see _retry_hint().
    """
    with trace.span(f"tool.{tc['name']}",
                    **{"tool.name": tc["name"],
                       "tool.arguments": tc["arguments"]}) as s:
        result = tools.dispatch(tc["name"], tc["arguments"])
        s.attributes["tool.result"] = result
        if tc["name"] == "search_knowledge_base" and isinstance(result, dict):
            s.attributes.update({
                "retrieval.query": tc["arguments"].get("query"),
                "retrieval.index": result.get("index"),
                "retrieval.fragments": [
                    {"id": f["id"], "score": f["score"]}
                    for f in result.get("fragments", [])],
            })
    return result


def _d14_retry_loop(trace: RequestTrace, provider, system: str, state: dict,
                    tc: dict, total_in: int, total_out: int) -> tuple[int, int]:
    """D14: the orchestrator treats an empty tool result as a transient failure
    and retries the SAME call with the SAME arguments, up to eight times.

    The retry is driven from here, in code, and each attempt goes through the
    model — which is where the latency and the tokens actually go. Two earlier
    versions of this were wrong and are worth naming:

      * retrying only the tool: deterministic, but the tools are local, so
        tokens and latency stayed flat and the defect was invisible in any
        cost model — while ТЗ says it is paid for in exactly those two;
      * handing the model an error and asking it to retry: a well-behaved
        model reports the failure to the customer instead, so the loop never
        happened at all.

    State is untouched throughout: the retries only ever repeat a read.
    """
    for attempt in range(1, _EMPTY_RETRY_LIMIT):
        with trace.span("llm.call", **{"agent.loop_step": f"retry-{attempt}",
                                       "retry.attempt": attempt}) as s:
            probe = provider.complete(system, _messages_for_model(state),
                                      tools.specs())
            s.attributes.update({
                "gen_ai.request.model": probe.model,
                "gen_ai.usage.input_tokens": probe.input_tokens,
                "gen_ai.usage.output_tokens": probe.output_tokens,
            })
        total_in += probe.input_tokens
        total_out += probe.output_tokens

        retry_tc = {"id": uuid.uuid4().hex[:12], "name": tc["name"],
                    "arguments": tc["arguments"]}
        state["messages"].append({"role": "assistant", "content": None,
                                  "tool_calls": [retry_tc]})
        result = _execute_tool(trace, retry_tc)
        state["messages"].append({
            "role": "tool", "tool_call_id": retry_tc["id"],
            "name": retry_tc["name"],
            "content": json.dumps(result, ensure_ascii=False)})
        if not _is_empty_result(result):
            break
    return total_in, total_out
