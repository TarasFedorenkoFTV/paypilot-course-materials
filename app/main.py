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
    saved_profile, saved_extra = defects.current_profile(), None
    out = {}
    try:
        for label, prof in (("clean", "clean"), ("profile", target)):
            defects.set_runtime_profile(prof)
            defects.set_runtime_defects("")
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
        defects.set_runtime_defects(None)
    return out


@app.get("/health")
def health():
    return {"status": "ok", "profile": config.PROFILE,
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
