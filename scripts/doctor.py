"""Environment diagnostics (ТЗ §5.9): checks dependencies, keys, versions,
model access — and says in plain words what is missing. Exit code 0 = green."""
import importlib
import os
import sys

OK, WARN, FAIL = "OK", "WARN", "FAIL"
results: list[tuple[str, str, str]] = []


def check(name: str, status: str, detail: str = ""):
    results.append((name, status, detail))


def main() -> int:
    if sys.version_info >= (3, 10):
        check("python", OK, sys.version.split()[0])
    else:
        check("python", FAIL, f"{sys.version.split()[0]} — need 3.10+")

    for mod in ("fastapi", "uvicorn", "pydantic", "yaml", "httpx", "pytest"):
        try:
            importlib.import_module(mod)
            check(f"dependency: {mod}", OK)
        except ImportError:
            check(f"dependency: {mod}", FAIL,
                  "run: pip install -r requirements.txt")

    provider = os.environ.get("LLM_PROVIDER", "mock")
    if provider == "mock":
        check("llm provider", WARN,
              "mock — free and deterministic, but probabilistic defects need "
              "a live provider; set LLM_PROVIDER=anthropic|openai")
    elif provider == "anthropic":
        key = os.environ.get("ANTHROPIC_API_KEY", "")
        check("llm provider", OK if key else FAIL,
              "anthropic" if key else "ANTHROPIC_API_KEY is empty")
        if key:
            _probe_anthropic(key)
    elif provider == "openai":
        key = os.environ.get("OPENAI_API_KEY", "")
        check("llm provider", OK if key else FAIL,
              "openai" if key else "OPENAI_API_KEY is empty")
        if key:
            _probe_openai(key)
    else:
        check("llm provider", FAIL,
              f"unknown LLM_PROVIDER={provider!r} (mock | anthropic | openai)")

    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "")
    if endpoint:
        try:
            import httpx
            r = httpx.get(endpoint.rstrip("/"), timeout=5)
            check("phoenix (trace UI)", OK if r.status_code < 500 else WARN,
                  endpoint)
        except Exception:
            check("phoenix (trace UI)", WARN,
                  f"{endpoint} unreachable — traces still land in traces/traces.jsonl "
                  "and /api/_test/traces")
    else:
        check("phoenix (trace UI)", WARN,
              "OTEL_EXPORTER_OTLP_ENDPOINT not set; the JSONL/API trace surface "
              "still works")

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for artefact in ("prompts/base.v1.md", "specs/requirements/US-01.md"):
        path = os.path.join(root, artefact)
        check(f"artefact: {artefact}", OK if os.path.exists(path) else FAIL,
              "" if os.path.exists(path) else "missing — L01 lab needs it")

    clock = os.environ.get("CLOCK_OVERRIDE", "")
    check("clock override", OK if clock else WARN,
          clock or "not set — window-sensitive cases will drift with real time")

    profile = os.environ.get("PROFILE", "clean")
    try:
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from app import defects
        defects.validate_startup()
        check("profile/defects config", OK,
              f"PROFILE={profile} DEFECTS={os.environ.get('DEFECTS', '') or '-'}")
    except Exception as e:
        check("profile/defects config", FAIL, str(e))

    width = max(len(n) for n, _, _ in results) + 2
    worst = OK
    for name, status, detail in results:
        print(f"{name:<{width}} [{status}] {detail}")
        if status == FAIL:
            worst = FAIL
        elif status == WARN and worst != FAIL:
            worst = WARN
    print()
    print({"OK": "Environment is ready.",
           "WARN": "Usable with warnings — read the lines above.",
           "FAIL": "Environment is NOT ready — fix the [FAIL] lines above."}[worst])
    return 1 if worst == FAIL else 0


def _probe_anthropic(key: str):
    try:
        import httpx
        r = httpx.post("https://api.anthropic.com/v1/messages",
                       headers={"x-api-key": key,
                                "anthropic-version": "2023-06-01"},
                       json={"model": "claude-haiku-4-5", "max_tokens": 1,
                             "messages": [{"role": "user", "content": "ping"}]},
                       timeout=15)
        check("anthropic api reachable", OK if r.status_code == 200
              else FAIL, f"HTTP {r.status_code}" +
              ("" if r.status_code == 200 else f": {r.text[:120]}"))
    except Exception as e:
        check("anthropic api reachable", FAIL, str(e))


def _probe_openai(key: str):
    try:
        import httpx
        r = httpx.get("https://api.openai.com/v1/models",
                      headers={"Authorization": f"Bearer {key}"}, timeout=15)
        check("openai api reachable", OK if r.status_code == 200 else FAIL,
              f"HTTP {r.status_code}")
    except Exception as e:
        check("openai api reachable", FAIL, str(e))


if __name__ == "__main__":
    sys.exit(main())
