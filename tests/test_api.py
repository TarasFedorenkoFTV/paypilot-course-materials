"""Smoke tests over the HTTP surface with the mock provider."""
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_chat_produces_answer_and_trace():
    r = client.post("/chat", json={"message": "What is the balance for CUS-0001?"})
    assert r.status_code == 200
    body = r.json()
    assert body["answer"]
    trace = client.get(f"/api/_test/traces/{body['request_id']}")
    assert trace.status_code == 200
    tree = trace.json()
    names = [c["name"] for c in tree["children"]]
    assert "llm.call" in names
    assert any(n.startswith("tool.") for n in names)


def test_chat_session_continuity():
    r1 = client.post("/chat", json={"message": "Balance for CUS-0001?"})
    sid = r1.json()["session_id"]
    r2 = client.post("/chat", json={"message": "Show transactions for ACC-1001",
                                    "session_id": sid})
    assert r2.json()["session_id"] == sid
    assert r2.json()["step_number"] == 2


def test_defects_endpoint_and_runtime_toggle():
    r = client.get("/api/_test/defects")
    assert r.json()["active"] == []
    r = client.put("/api/_test/defects", json={"defects": "D19,D26"})
    assert r.json()["active"] == ["D19", "D26"]
    r = client.put("/api/_test/defects", json={"defects": "D99"})
    assert r.status_code == 400
    client.put("/api/_test/defects", json={"defects": None})


def test_clock_control():
    r = client.put("/api/_test/clock", json={"now": "2026-11-20T00:00:00Z"})
    assert r.json()["now"].startswith("2026-11-20")
    # 2026-11-20: TX-0401 (2026-07-20) is now far outside the 60-day window
    from app.agent import tools
    check = tools.check_dispute_eligibility("TX-0401", "duplicate_charge")
    assert check["eligible"] is False
    client.put("/api/_test/clock", json={"now": None})


def test_state_and_reset():
    from app.agent import tools
    tools.escalate_to_human("CUS-0001", "test escalation")
    r = client.get("/api/_test/state/escalations")
    assert len(r.json()["rows"]) == 1
    r = client.post("/api/_test/reset")
    assert r.json()["status"] == "reset"
    r = client.get("/api/_test/state/escalations")
    assert r.json()["rows"] == []


def test_prompt_and_tools_endpoints():
    r = client.get("/api/_test/prompt")
    assert r.json()["version"] == "base.v1"
    r = client.get("/api/_test/tools")
    names = {t["name"] for t in r.json()["tools"]}
    assert {"get_account", "quote_fx", "create_dispute",
            "search_knowledge_base"} <= names


# --- chat UI: things a live click-through turned up --------------------------

def _ui() -> str:
    from app import config
    return (config.ROOT / "app" / "static" / "index.html").read_text(encoding="utf-8")


def test_ui_reports_errors_in_the_page_not_in_a_modal():
    """A bad clock value used to raise a native alert() carrying the raw
    response body — a lecturer mid-lesson got a modal dialog full of JSON."""
    ui = _ui()
    assert "alert(" not in ui.replace("// Errors belong in the conversation, not in a modal dialog: alert() blocks the", "")
    assert "function fail(e)" in ui
    assert "j.detail" in ui, "FastAPI's detail field must be unwrapped for the reader"


def test_ui_surfaces_the_retry_signature_in_the_tree():
    """A retry loop renders as nine identical llm.call rows. The loop step and
    the repeated-arguments count are already in the data; without them in the
    tree the lecturer has to click every row to find which is which."""
    ui = _ui()
    assert "agent.loop_step" in ui
    assert "повтор" in ui


def test_ui_survives_a_narrow_screen():
    """At 768px the fixed 400px side panel left the chat 368px wide and clipped
    the clean-vs-profile button — the first move of every lab. And a 760px
    message bubble made the whole page scroll sideways."""
    ui = _ui()
    assert "@media (max-width: 820px)" in ui
    assert "min(760px, 100%)" in ui
    assert "flex-wrap:wrap}" in ui
    media_at = ui.index("@media (max-width: 820px)")
    base_at = ui.index(".side{width:400px")
    assert media_at > base_at, \
        "the media query must come after the base rule or source order defeats it"
