"""The stand is single-tenant, and that is a deployment constraint rather than
a bug — but it has to stay documented, because the failure it produces is
silent. One student switching profile changes everyone's stand, and neither
of them sees why their exercise stopped making sense.

Measured on a live stand: profile, clock, the retrieval knobs, the fold
threshold and the database are all shared; only dialogue history is keyed by
session.
"""
from fastapi.testclient import TestClient

from app import config, defects
from app.main import app

client = TestClient(app)


def teardown_function():
    defects.set_runtime_profile("clean")
    defects.set_runtime_defects("")
    config.SUMMARIZE_AFTER_STEPS = 8
    config.RAG_TOP_K = 4
    config.KB_INDEX_ENV = ""


def test_profile_is_global_not_per_session():
    client.put("/api/_test/profile", json={"profile": "lesson-03"})
    client.put("/api/_test/profile", json={"profile": "lesson-06"})
    # a second "user" reading /health sees what the last writer chose
    assert client.get("/health").json()["profile"] == "lesson-06"


def test_knobs_are_global_not_per_session():
    client.put("/api/_test/retrieval", json={"top_k": 1, "index": "kb_broken"})
    client.put("/api/_test/summarize_after", json={"steps": 2})
    assert client.get("/api/_test/retrieval").json()["top_k"] == 1
    assert client.get("/api/_test/summarize_after").json()["summarize_after_steps"] == 2


def test_dialogue_history_is_the_only_isolated_state():
    a = client.post("/chat", json={"session_id": "student-a", "message": "hi"}).json()
    b = client.post("/chat", json={"session_id": "student-b", "message": "hi"}).json()
    assert a["session_id"] != b["session_id"]
    assert a["step_number"] == 1 and b["step_number"] == 1
    again = client.post("/chat", json={"session_id": "student-a", "message": "hi"}).json()
    assert again["step_number"] == 2, "history must be per session"


def test_the_constraint_is_written_down():
    """If this ever stops being documented, someone will put a class on one
    instance and spend a lesson debugging each other's state."""
    text = (config.ROOT / "docs" / "ONBOARDING.md").read_text(encoding="utf-8")
    assert "Один стенд на студента" in text
    assert "не мультитенантний" in text
