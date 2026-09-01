"""Deterministic scripted provider. No key, no network, no cost.

Purpose: development, CI smoke runs and the environment-doctor path. It is a
stand-in for the loop mechanics only — probabilistic defects live in real
model behaviour and are calibrated on a live provider.

Policy: one keyword-routed tool call per user question, then a final answer
that reads the tool result back. Enough to exercise the full
model → tool → model cycle, tracing and the test API."""
import json
import re
import uuid

from app.agent.providers.base import ModelResponse, Provider

_ID_RE = {
    "customer": re.compile(r"\bCUS-\d{4}\b", re.I),
    "account": re.compile(r"\bACC-\d{4}\b", re.I),
    "transaction": re.compile(r"\bTX-\d{4}\b", re.I),
    "email": re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"),
    "amount": re.compile(r"\b(\d+(?:\.\d+)?)\s*(EUR|USD|GBP|PLN|CHF|UAH)\b", re.I),
    "reason": re.compile(r"\b(fraud_card_not_present|goods_not_received|"
                         r"duplicate_charge|service_not_rendered|unauthorized_debit)\b"),
}


def _tokens(text: str) -> int:
    return max(1, len(text) // 4)


class MockProvider(Provider):
    name = "mock"

    def complete(self, system, messages, tools):
        model = "mock-1"
        last = messages[-1]
        input_size = _tokens(system) + sum(_tokens(str(m.get("content") or "")) +
                                           _tokens(json.dumps(m.get("tool_calls") or []))
                                           for m in messages)
        if last["role"] == "tool":
            text = self._answer_from_tool(last)
            return ModelResponse(text=text, input_tokens=input_size,
                                 output_tokens=_tokens(text), model=model)
        call = self._route(str(last.get("content") or ""))
        if call:
            return ModelResponse(tool_calls=[call], input_tokens=input_size,
                                 output_tokens=8, model=model)
        text = ("I can help with balances, fees, limits, currency conversion "
                "and payment disputes. Please share your customer id.")
        return ModelResponse(text=text, input_tokens=input_size,
                             output_tokens=_tokens(text), model=model)

    def _route(self, text: str) -> dict | None:
        t = text.lower()
        cid = _ID_RE["customer"].search(text)
        acc = _ID_RE["account"].search(text)
        tx = _ID_RE["transaction"].search(text)
        reason = _ID_RE["reason"].search(text)
        email = _ID_RE["email"].search(text)

        def call(name, **arguments):
            return {"id": uuid.uuid4().hex[:12], "name": name,
                    "arguments": arguments}

        if ("open" in t or "create" in t or "file" in t) and "dispute" in t and tx:
            return call("create_dispute", transaction_id=tx.group().upper(),
                        reason_code=(reason.group() if reason else "duplicate_charge"))
        if "dispute" in t and tx:
            return call("check_dispute_eligibility",
                        transaction_id=tx.group().upper(),
                        reason_code=(reason.group() if reason else "duplicate_charge"))
        if "statement" in t and acc and email:
            return call("send_statement", account_id=acc.group().upper(),
                        email=email.group())
        if ("human" in t or "escalate" in t) and cid:
            return call("escalate_to_human", customer_id=cid.group().upper(),
                        reason="customer asked for a human")
        if ("convert" in t or "fx" in t or "exchange" in t) and cid:
            m = _ID_RE["amount"].search(text)
            amount = float(m.group(1)) if m else 100.0
            frm = m.group(2).upper() if m else "EUR"
            to = "USD" if frm == "EUR" else "EUR"
            m2 = re.search(r"\b(?:to|into)\s+([A-Z]{3})\b", text, re.I)
            if m2:
                to = m2.group(1).upper()
            return call("quote_fx", customer_id=cid.group().upper(),
                        amount=amount, from_currency=frm, to_currency=to)
        if "limit" in t and cid:
            return call("check_limits", customer_id=cid.group().upper())
        if ("transaction" in t or "history" in t) and acc:
            return call("get_transactions", account_id=acc.group().upper())
        if ("balance" in t or "account" in t) and cid:
            return call("get_account", customer_id=cid.group().upper())
        if any(w in t for w in ("fee", "spread", "rule", "policy", "how", "what", "why")):
            return call("search_knowledge_base", query=text[:120])
        return None

    def _answer_from_tool(self, tool_msg: dict) -> str:
        name = tool_msg.get("name", "tool")
        try:
            data = json.loads(tool_msg["content"])
        except (KeyError, json.JSONDecodeError):
            data = {}
        if isinstance(data, dict) and data.get("error"):
            return f"I could not complete that: {data['error']}"
        if name == "search_knowledge_base":
            frags = (data or {}).get("fragments", [])
            if not frags:
                return "I could not find anything relevant in the documentation."
            quoted = " | ".join(f["text"][:160] for f in frags[:2])
            return f"Here is what the documentation says: {quoted}"
        return f"Result of {name}: {json.dumps(data, ensure_ascii=False)}"
