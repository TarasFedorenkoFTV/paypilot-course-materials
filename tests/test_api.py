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
