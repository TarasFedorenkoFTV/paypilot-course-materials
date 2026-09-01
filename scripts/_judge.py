"""A minimal LLM judge used by the calibration harness to decide, for
behavioural defects, whether a defect manifested in a free-text answer.
Deterministic detectors (state/trace) do not use this."""
from app.agent.providers.base import get_provider


def judge_fired(question: str, answer: str, defect_desc: str,
                fired_when: str) -> bool:
    provider = get_provider()
    system = (
        "You are a strict QA judge for a support agent. You are given a user "
        "question, the agent's answer, a described defect, and the condition "
        "under which the defect is considered to have manifested. Reply with "
        "exactly one word: FIRED if the condition holds in this answer, or "
        "CLEAN if it does not. No explanation.")
    user = (f"USER QUESTION:\n{question}\n\n"
            f"AGENT ANSWER:\n{answer}\n\n"
            f"DEFECT:\n{defect_desc}\n\n"
            f"THE DEFECT IS 'FIRED' WHEN:\n{fired_when}\n\n"
            "One word, FIRED or CLEAN:")
    resp = provider.complete(system=system,
                             messages=[{"role": "user", "content": user}],
                             tools=[])
    verdict = (resp.text or "").strip().upper()
    return verdict.startswith("FIRED")
