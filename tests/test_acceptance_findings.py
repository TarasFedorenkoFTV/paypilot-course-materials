"""Regression tests for the findings of the customer acceptance review
(docs/acceptance-review-customer.md). Each test fails on the code as it was
before that review.
"""
import json
import os

from fastapi.testclient import TestClient

from app import config, defects, tracing
from app.main import app

client = TestClient(app)


def teardown_function():
    defects.set_runtime_profile("clean")
    defects.set_runtime_defects("")
    config.SUMMARIZE_AFTER_STEPS = 8
    config.RAG_TOP_K = 4
    config.KB_INDEX_ENV = ""


# --- finding 5: run.profile lied after a runtime profile switch --------------

def test_trace_profile_follows_runtime_switch():
    """tracing read config.PROFILE, the import-time value, so a trace taken on
    lesson-07 was stamped 'clean' — and L12 versions run records by profile."""
    defects.set_runtime_profile("lesson-07")
    t = tracing.RequestTrace("sess", 1)
    assert t.root.attributes["run.profile"] == "lesson-07"
    assert "D11" in t.root.attributes["run.active_defects"]


def test_health_and_trace_agree_on_profile():
    client.put("/api/_test/profile", json={"profile": "lesson-03"})
    assert client.get("/health").json()["profile"] == "lesson-03"
    assert tracing.RequestTrace("s", 1).root.attributes["run.profile"] == "lesson-03"


# --- finding 3: L05 was unreachable without a restart -----------------------

def test_summarize_threshold_is_settable_at_runtime():
    assert client.get("/api/_test/summarize_after").json()[
        "summarize_after_steps"] == 8
    r = client.put("/api/_test/summarize_after", json={"steps": 2})
    assert r.status_code == 200
    from app.agent import summarize
    assert summarize.should_summarize(3) is True
    assert summarize.should_summarize(2) is False
    assert client.put("/api/_test/summarize_after",
                      json={"steps": 0}).status_code == 400


def test_compose_passes_the_loop_knobs():
    """docker-compose did not forward SUMMARIZE_AFTER_STEPS, so the memory
    lesson could not be configured at all inside the container."""
    compose = (config.ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    for var in ("SUMMARIZE_AFTER_STEPS", "MAX_AGENT_STEPS", "RAG_TOP_K",
                "KB_INDEX", "CLOCK_OVERRIDE", "PROFILE", "DEFECTS"):
        assert f"{var}=" in compose, f"{var} not forwarded by docker-compose"


# --- L04: retrieval knobs had no surface on the stand -----------------------

def test_retrieval_knobs_are_settable_at_runtime():
    from app.rag import retriever
    r = client.put("/api/_test/retrieval",
                   json={"top_k": 2, "index": "kb_broken"}).json()
    assert r["top_k"] == 2 and r["index"] == "kb_broken"
    assert retriever.search("transfer limits")["top_k"] == 2
    assert retriever.search("transfer limits")["index"] == "kb_broken"
    assert client.put("/api/_test/retrieval",
                      json={"index": "nope"}).status_code == 400
    assert client.put("/api/_test/retrieval",
                      json={"top_k": 99}).status_code == 400


# --- finding 4: the app ignored .env ----------------------------------------

def test_dotenv_loader_does_not_override_real_env(tmp_path, monkeypatch):
    """`cp .env.example .env && make dev` used to come up on the mock provider
    with an empty clock, because only the scripts read .env."""
    assert hasattr(config, "_load_dotenv")
    monkeypatch.setenv("PAYPILOT_TEST_KEY", "from-environment")
    env = config.ROOT / ".env"
    if env.exists():                       # a real .env must win over defaults
        assert config.LLM_PROVIDER == os.environ["LLM_PROVIDER"]
    config._load_dotenv()
    assert os.environ["PAYPILOT_TEST_KEY"] == "from-environment"


# --- traces survive a restart ----------------------------------------------

def test_trace_lookup_falls_back_to_the_file(tmp_path, monkeypatch):
    tree = {"request_id": "feedfacefeedface", "name": "agent.request",
            "attributes": {}, "children": []}
    f = tmp_path / "traces.jsonl"
    f.write_text(json.dumps(tree) + "\n", encoding="utf-8")
    monkeypatch.setattr(tracing, "TRACE_FILE", f)
    monkeypatch.setattr(tracing, "_store", {})
    assert tracing.get("feedfacefeedface")["request_id"] == "feedfacefeedface"
    assert tracing.get("0000000000000000") is None


# --- finding 2: corridors must be declared before the run -------------------

def test_corridors_are_declared_up_front():
    import yaml
    data = yaml.safe_load(
        (config.ROOT / "profiles" / "corridors.yaml").read_text(encoding="utf-8"))
    assert data["frozen_at"], "a corridor file with no freeze date proves nothing"
    report = json.loads((config.ROOT / "docs" / "calibration-report.json")
                        .read_text(encoding="utf-8"))
    probabilistic = {r["defect"] for r in report["results"]
                     if r["declared"] == "probabilistic"}
    missing = probabilistic - set(data["corridors"])
    assert not missing, f"probabilistic defects with no declared corridor: {missing}"
    for did, c in data["corridors"].items():
        assert 0 <= c["low_pct"] <= c["high_pct"] <= 100, did
        assert c["low_pct"] >= 30, f"{did}: a defect below 30% is not teachable"


# --- round 2: compare wiped the defects the lecturer had pinned -------------

def test_compare_keeps_pinned_defects():
    """The runbook tells lecturers to pin a defect and then hit compare.
    compare used to clear the pinned set for both arms and reset to the
    environment afterwards, so the pin was lost and clean was compared against
    clean."""
    client.put("/api/_test/profile", json={"profile": "clean"})
    client.put("/api/_test/defects", json={"defects": "D19,D26"})
    before = client.get("/api/_test/defects").json()["active"]
    assert sorted(before) == ["D19", "D26"]

    r = client.post("/api/_test/compare",
                    json={"message": "hi", "profile": "clean"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["clean"]["active_defects"] == []
    assert sorted(body["profile"]["active_defects"]) == ["D19", "D26"]

    after = client.get("/api/_test/defects").json()["active"]
    assert sorted(after) == ["D19", "D26"], "compare lost the pinned defects"


def test_every_scenario_measures_on_a_profile():
    """Six defects sat in two profiles each, so the harness could not pick one
    and silently fell back to measuring them in isolation over clean — which is
    the arm the previous round rejected."""
    import sys
    sys.path.insert(0, str(config.ROOT))
    from scripts.calibrate import profile_for
    from scripts.scenarios import SCENARIOS
    isolation = [s["defect"] for s in SCENARIOS if not profile_for(s)]
    assert not isolation, f"still measured in isolation: {isolation}"
