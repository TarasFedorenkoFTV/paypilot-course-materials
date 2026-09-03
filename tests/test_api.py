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


def test_ui_diffs_the_tool_payloads_after_a_compare():
    """Walking the documented 60-second check turned up that both columns show
    the same number — correctly, because the agent recomputes it — so the
    divergence had to be hunted by loading each trace and clicking spans. The
    compare view now diffs the tool results itself."""
    ui = _ui()
    assert "showPayloadDiff" in ui
    assert "toolIndex" in ui
    assert "pdiff" in ui


def test_ui_shows_latency_beside_the_token_count():
    """POST /chat returns elapsed_ms; without it on screen a budget case had to
    fetch a trace to read a number the reply already carried."""
    assert "res.elapsed_ms" in _ui()


def test_ui_reports_the_clock_the_stand_actually_applied():
    """Resetting the clock said "реальний" while CLOCK_OVERRIDE from the
    environment — the documented default — was still in force, so the message
    contradicted the header right next to it."""
    ui = _ui()
    assert "st.now" in ui
    assert "'Час прогону: ' + (v || 'реальний')" not in ui


def test_ui_controls_the_knobs_the_lessons_need():
    """The memory lesson cannot happen without lowering the fold threshold and
    the retrieval lesson needs top_k and the index — both were API-only, so the
    runbook sent a lecturer to a terminal mid-class. L01 audits the prompt as
    an artefact and it had no on-screen surface at all."""
    ui = _ui()
    for handler in ("setSummarize", "setRetrieval", "togglePrompt"):
        assert f"function {handler}" in ui, handler
    for endpoint in ("_test/summarize_after", "_test/retrieval", "_test/prompt"):
        assert endpoint in ui, endpoint


def test_ui_renders_markdown_without_parsing_model_html():
    """The model answers in markdown and the page showed the asterisks, which
    buries the numbers on a projector. It must not be fixed with innerHTML:
    this stand deliberately carries prompt-injection payloads, so parsing HTML
    out of model output would be a real hole."""
    ui = _ui()
    assert "function renderRich" in ui
    assert "createElement" in ui
    body = ui.split("function renderRich")[1].split("function addMsg")[0]
    assert "innerHTML" not in body, "model output must never reach innerHTML"


def test_ui_shows_the_real_knob_state_not_placeholders():
    """The stand was folding at 3 and searching kb_broken while every panel
    field sat empty behind placeholders reading 8 and 4. A lecturer glancing at
    it would have believed the defaults were in force — the same failure the
    course teaches, with the display right and the state wrong. The fields are
    filled from the server, and a knob off its default also raises a header
    pill so it cannot hide behind a closed panel."""
    ui = _ui()
    assert "api('/api/_test/summarize_after')" in ui
    assert "api('/api/_test/retrieval')" in ui
    assert "$('sumInp').value = sum.summarize_after_steps" in ui
    assert "$('topkInp').value = ret.top_k" in ui
    assert "pKnobs" in ui


def test_ui_explains_a_hung_provider_instead_of_showing_a_dot():
    """Measured during a click-through: the TLS handshake to the provider timed
    out and the reply bubble sat on '…' with nothing said. The client timeout
    is 90s per model call and a retry loop makes up to nine, so "stuck" can
    mean minutes of a page that looks frozen for no stated reason."""
    ui = _ui()
    assert "чекаю на провайдера" in ui
    assert "stopWaiting" in ui
    # cleared on both the success and the failure path, or the message would
    # overwrite a finished answer
    assert ui.count("stopWaiting()") >= 2
