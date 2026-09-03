"""PayPilot stand API: the chat surface + the test/service surface."""
import os

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app import clock, config, db, defects, otel, tracing
from app.agent import loop, prompt, tools

defects.validate_startup()
db.ensure_seeded()
otel.init()   # no-op unless OTEL_EXPORTER_OTLP_ENDPOINT is set

app = FastAPI(title="PayPilot stand", version="0.1.0")

STATIC_DIR = config.ROOT / "app" / "static"


@app.get("/", include_in_schema=False)
def chat_ui():
    """Minimal chat surface (ТЗ §3.2): chat + profile/defect controls + trace."""
    return FileResponse(STATIC_DIR / "index.html")


class ChatIn(BaseModel):
    message: str
    session_id: str | None = None


@app.post("/chat")
def chat(body: ChatIn):
    return loop.run_turn(body.session_id, body.message)


class CompareIn(BaseModel):
    message: str
    profile: str | None = None     # defaults to the currently active profile


@app.post("/api/_test/compare")
def test_compare(body: CompareIn):
    """Run the same question on clean and on a defect profile, side by side.

    This is the first move of every lab (ТЗ §5.8: clean is the control
    profile), so the stand does it in one call instead of making the student
    flip flags twice and hope nothing else changed in between."""
    target = body.profile or defects.current_profile()
    saved_profile = defects.current_profile()
    # Defects pinned individually (the chips in the UI) are part of what the
    # lecturer is demonstrating. compare used to wipe them for both arms and
    # then reset to the environment, so a pinned defect vanished for good and
    # "clean vs D19 on the clean profile" compared clean against clean.
    saved_extra = ",".join(defects.describe()["extra_defects"])
    out = {}
    try:
        for label, prof, extra in (("clean", "clean", ""),
                                   ("profile", target, saved_extra)):
            defects.set_runtime_profile(prof)
            defects.set_runtime_defects(extra)
            loop.reset_sessions()
            res = loop.run_turn(None, body.message)
            out[label] = {
                "profile": prof,
                "active_defects": sorted(defects.active()),
                "answer": res["answer"],
                "request_id": res["request_id"],
                "usage": res["usage"],
            }
    except ValueError as e:
        raise HTTPException(400, str(e))
    finally:
        defects.set_runtime_profile(saved_profile)
        defects.set_runtime_defects(saved_extra)
    return out


@app.get("/health")
def health():
    # the live profile, not the import-time one: /health is what a lecturer
    # checks after switching profiles from the UI
    return {"status": "ok", "profile": defects.current_profile(),
            "startup_profile": config.PROFILE,
            "active_defects": sorted(defects.active()),
            "provider": config.LLM_PROVIDER,
            "otlp": bool(os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"))}


# --------------------------------------------------------------------------
# Test API (ТЗ §5.7): internal state, defect flags, seed, time control.

@app.get("/api/_test/defects")
def test_defects():
    return defects.describe()


class ProfileIn(BaseModel):
    profile: str | None = None   # null -> back to the env PROFILE


@app.put("/api/_test/profile")
def test_set_profile(body: ProfileIn):
    try:
        defects.set_runtime_profile(body.profile)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return defects.describe()


class DefectsIn(BaseModel):
    defects: str | None = None   # "D19,D26"; null -> back to env value


@app.put("/api/_test/defects")
def test_set_defects(body: DefectsIn):
    try:
        defects.set_runtime_defects(body.defects)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return defects.describe()


@app.get("/api/_test/state/{table}")
def test_state(table: str):
    try:
        return {"table": table, "rows": db.table_dump(table)}
    except ValueError as e:
        raise HTTPException(404, str(e))


@app.get("/api/_test/seed")
def test_seed():
    from app import seed
    return {"seed_version": seed.SEED_VERSION,
            "customers": db.table_dump("customers"),
            "accounts": db.table_dump("accounts"),
            "transaction_count": len(db.table_dump("transactions"))}


@app.get("/api/_test/clock")
def test_clock():
    return clock.describe()


class ClockIn(BaseModel):
    now: str | None = None   # ISO datetime; null -> drop runtime override


@app.post("/api/_test/clock")          # longreads use POST; PUT kept as an alias
@app.put("/api/_test/clock")
def test_set_clock(body: ClockIn):
    try:
        clock.set_override(body.now)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return clock.describe()


@app.get("/api/_test/retrieval")
def test_retrieval():
    from app.rag import retriever
    return {"index": retriever.active_index_name(),
            "top_k": retriever.active_top_k(),
            "index_env": config.KB_INDEX_ENV, "rag_top_k": config.RAG_TOP_K}


class RetrievalIn(BaseModel):
    top_k: int | None = None       # None -> leave unchanged
    index: str | None = None       # "kb_clean" | "kb_broken" | "" -> defect-driven


@app.put("/api/_test/retrieval")
def test_set_retrieval(body: RetrievalIn):
    """Make the retrieval knobs reachable from the stand surface.

    retriever.active_top_k() and active_index_name() both read config at call
    time, so this changes what the *agent* retrieves on the next /chat call —
    which is what L04 needs. Before this, measuring the k trade-off or
    comparing kb_clean against kb_broken meant editing the environment and
    restarting, and the only proof in the walkthrough was an in-process call
    to retriever.search() that the agent itself never went through.
    """
    from app.rag import retriever
    if body.top_k is not None:
        if not 1 <= body.top_k <= 20:
            raise HTTPException(400, "top_k must be between 1 and 20")
        config.RAG_TOP_K = body.top_k
    if body.index is not None:
        if body.index not in ("kb_clean", "kb_broken", ""):
            raise HTTPException(400, "index must be kb_clean, kb_broken or \"\"")
        config.KB_INDEX_ENV = body.index
    return {"index": retriever.active_index_name(),
            "top_k": retriever.active_top_k(),
            "index_env": config.KB_INDEX_ENV, "rag_top_k": config.RAG_TOP_K}


@app.get("/api/_test/summarize_after")
def test_summarize_after():
    return {"summarize_after_steps": config.SUMMARIZE_AFTER_STEPS}


class SummarizeIn(BaseModel):
    steps: int   # dialog step after which history is folded into a summary


@app.put("/api/_test/summarize_after")
def test_set_summarize_after(body: SummarizeIn):
    """Lower the fold threshold so the memory lesson is reachable in a
    four-step dialog instead of a nine-step one.

    summarize.should_summarize() reads config at call time, so this takes
    effect on the next request with no restart. Without this endpoint L05
    (D06/D07) required setting SUMMARIZE_AFTER_STEPS in the environment and
    restarting the stand, and docker-compose did not even pass the variable
    through.
    """
    if body.steps < 1:
        raise HTTPException(400, "steps must be >= 1")
    config.SUMMARIZE_AFTER_STEPS = body.steps
    return {"summarize_after_steps": config.SUMMARIZE_AFTER_STEPS}


@app.post("/api/_test/reset")
def test_reset():
    info = db.reset()
    loop.reset_sessions()
    return {"status": "reset", **info}


@app.get("/api/_test/prompt")
def test_prompt():
    text, version = prompt.build()
    return {"version": version, "overlays": prompt.active_overlays(),
            "text": text}


@app.get("/api/_test/specs")
def test_specs():
    """Requirement documents students audit alongside the prompt (L01)."""
    out = {}
    for path in sorted((config.ROOT / "specs" / "requirements").glob("*.md")):
        out[path.name] = path.read_text(encoding="utf-8")
    return {"requirements": out}


@app.get("/api/_test/tools")
def test_tools():
    return {"tools": tools.specs()}


@app.get("/api/_test/traces")
def test_traces(limit: int = 20):
    return {"traces": tracing.recent(limit)}


@app.get("/api/_test/traces/{request_id}")
def test_trace(request_id: str):
    tree = tracing.get(request_id)
    if not tree:
        raise HTTPException(404, f"no trace for request {request_id}")
    return tree
