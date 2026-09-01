"""PayPilot stand API: the chat surface + the test/service surface."""
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from app import clock, config, db, defects, tracing
from app.agent import loop, prompt, tools

defects.validate_startup()
db.ensure_seeded()

app = FastAPI(title="PayPilot stand", version="0.1.0")


class ChatIn(BaseModel):
    message: str
    session_id: str | None = None


@app.post("/chat")
def chat(body: ChatIn):
    return loop.run_turn(body.session_id, body.message)


@app.get("/health")
def health():
    return {"status": "ok", "profile": config.PROFILE,
            "provider": config.LLM_PROVIDER}


# --------------------------------------------------------------------------
# Test API (ТЗ §5.7): internal state, defect flags, seed, time control.

@app.get("/api/_test/defects")
def test_defects():
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
