"""Controlled time. Scenario correctness depends on the distance between a
transaction date and the dispute window, so 'now' must be pinnable:
priority: runtime override (test API) > CLOCK_OVERRIDE env > real time."""
from datetime import datetime, timezone

from app import config

_runtime_override: datetime | None = None


def _parse(value: str) -> datetime:
    value = value.strip().replace("Z", "+00:00")
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def now() -> datetime:
    if _runtime_override is not None:
        return _runtime_override
    if config.CLOCK_OVERRIDE:
        return _parse(config.CLOCK_OVERRIDE)
    return datetime.now(timezone.utc)


def today():
    return now().date()


def set_override(value: str | None) -> None:
    global _runtime_override
    _runtime_override = _parse(value) if value else None


def describe() -> dict:
    return {
        "now": now().isoformat(),
        "runtime_override": _runtime_override.isoformat() if _runtime_override else None,
        "env_override": config.CLOCK_OVERRIDE or None,
    }
