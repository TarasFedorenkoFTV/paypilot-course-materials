import os

# Pin the environment BEFORE app modules are imported: clean profile,
# fixed clock, mock provider — tests must be deterministic and keyless.
os.environ.setdefault("PROFILE", "clean")
os.environ.setdefault("DEFECTS", "")
os.environ.setdefault("CLOCK_OVERRIDE", "2026-09-15T10:00:00Z")
os.environ.setdefault("LLM_PROVIDER", "mock")

import pytest

from app import db, defects
from app.agent import loop


@pytest.fixture(autouse=True)
def fresh_state():
    db.reset()
    loop.reset_sessions()
    defects.set_runtime_defects(None)
    yield
    defects.set_runtime_defects(None)


@pytest.fixture
def enable():
    def _enable(*ids):
        defects.set_runtime_defects(",".join(ids))
    return _enable
