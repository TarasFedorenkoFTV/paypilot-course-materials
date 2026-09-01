"""Central configuration. Everything is read from the environment once at import
time, except the pieces the test API is allowed to mutate at runtime
(clock override, defect set) — those live in mutable module state."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROMPTS_DIR = ROOT / "prompts"
PROFILES_FILE = ROOT / "profiles" / "profiles.yaml"
DEFECTS_FILE = ROOT / "profiles" / "defects.yaml"
CORPUS_DIR = ROOT / "app" / "rag" / "corpus"
DATA_DIR = ROOT / "data"
TRACES_DIR = ROOT / "traces"

PROFILE = os.environ.get("PROFILE", "clean")
DEFECTS_ENV = os.environ.get("DEFECTS", "")

LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "mock")
LLM_MODEL = os.environ.get("LLM_MODEL", "")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

MAX_AGENT_STEPS = int(os.environ.get("MAX_AGENT_STEPS", "12"))
SUMMARIZE_AFTER_STEPS = int(os.environ.get("SUMMARIZE_AFTER_STEPS", "8"))

KB_INDEX_ENV = os.environ.get("KB_INDEX", "")
RAG_TOP_K = int(os.environ.get("RAG_TOP_K", "4"))

CLOCK_OVERRIDE = os.environ.get("CLOCK_OVERRIDE", "")

DATA_DIR.mkdir(exist_ok=True)
TRACES_DIR.mkdir(exist_ok=True)
