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


def should_summarize(step_number: int) -> bool:
    return step_number > config.SUMMARIZE_AFTER_STEPS


def summarize_messages(provider, messages: list[dict]) -> str:
    instruction = DEFECT_INSTRUCTION if defects.is_on("D06") else CLEAN_INSTRUCTION
    transcript = []
    for m in messages:
        role = m["role"]
        if role == "tool":
            transcript.append(f"[tool {m.get('name')}] {m['content']}")
        elif m.get("content"):
            transcript.append(f"{role}: {m['content']}")
    body = "\n".join(transcript)
    resp = provider.complete(
        system=instruction,
        messages=[{"role": "user", "content": body}],
        tools=[])
    return resp.text or ""
