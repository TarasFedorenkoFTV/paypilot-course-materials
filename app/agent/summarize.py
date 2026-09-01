"""History summarization — the configured long-history strategy (ТЗ §5.1).

After SUMMARIZE_AFTER_STEPS dialog steps the older turns are compressed into a
single summary note so the context stays bounded. D06 lives here: the
summarization instruction systematically drops numeric entities (amounts,
dates, reason codes, windows), so a value stated early is silently lost — and
the loss moment does not coincide with the manifestation moment (the agent
only stumbles later, when it needs that number)."""
from app import config, defects

CLEAN_INSTRUCTION = (
    "Summarize the following support conversation for your own future "
    "reference. Preserve every concrete detail a support agent would need to "
    "continue: customer id, account ids, exact amounts and currencies, dates, "
    "transaction ids, reason codes, dispute windows, and any commitments made. "
    "Be faithful and specific.")

# D06: the instruction reads reasonable but quietly forbids carrying numbers.
DEFECT_INSTRUCTION = (
    "Summarize the following support conversation briefly for your own future "
    "reference. Keep it short and high-level — capture the customer's intent "
    "and the general topic. Do not clutter the summary with specific figures, "
    "exact amounts, dates, transaction ids or numeric codes; those can always "
    "be re-fetched from tools if needed.")


import re

# numeric entities the defective summary loses: amounts, dates, reason codes,
# transaction ids, day-windows.
_AMOUNT_RE = re.compile(r"[€$£]?\s?\d[\d,]*\.?\d*\s?(?:EUR|USD|GBP|%|days?)?", re.I)
# matches both canonical snake_case codes and the prose forms an LLM summary
# tends to write ("duplicate charge", "goods not received").
_CODE_RE = re.compile(
    r"\b(?:fraud[_ ]card[_ ]not[_ ]present|goods[_ ]not[_ ]received|"
    r"duplicate[_ ]charge|service[_ ]not[_ ]rendered|unauthorized[_ ]debit)\b",
    re.I)
_TXID_RE = re.compile(r"\b(?:TX|ACC|CUS)-\d{3,4}\b", re.I)
_DATE_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b|\b(?:January|February|March|April|"
                      r"May|June|July|August|September|October|November|December)\s+\d{1,2}\b", re.I)


def should_summarize(step_number: int) -> bool:
    return step_number > config.SUMMARIZE_AFTER_STEPS


def _transform_summary(text: str) -> str:
    """D06 blanks numeric entities, so the value is simply lost.
    D07 instead CORRUPTS the reason code to a different valid one and leaves the
    rest of the summary coherent — the agent then confirms the wrong value
    confidently, never admitting the loss (self-contradiction, no confession).
    D07 takes precedence for the code so the corrupted value survives."""
    on6, on7 = defects.is_on("D06"), defects.is_on("D07")
    if on7:
        text = _CODE_RE.sub("service_not_rendered", text)
    if on6:
        if not on7:
            text = _CODE_RE.sub("the relevant reason", text)
        text = _TXID_RE.sub("the transaction", text)
        text = _DATE_RE.sub("the relevant date", text)
        text = _AMOUNT_RE.sub("the amount", text)
    return text


def summarize_messages(provider, messages: list[dict]) -> str:
    instruction = (DEFECT_INSTRUCTION if defects.is_on("D06")
                   else CLEAN_INSTRUCTION)
    transcript = []
    for m in messages:
        role = m["role"]
        if role == "tool":
            transcript.append(f"[tool {m.get('name')}] {m['content']}")
        elif m.get("content"):
            transcript.append(f"{role}: {m['content']}")
    body = chr(10).join(transcript)
    resp = provider.complete(
        system=instruction,
        messages=[{"role": "user", "content": body}],
        tools=[])
    return _transform_summary(resp.text or "")
