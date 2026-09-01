"""Defect system: profiles + per-defect flags.

Active set = profile defects ∪ DEFECTS env ∪ runtime override (test API).
Unknown ids or unknown profile fail loudly at startup — a misconfigured
combination must be an explicit error, never silent behaviour."""
import os

import yaml

from app import config

with open(config.DEFECTS_FILE, encoding="utf-8") as f:
    REGISTRY: dict[str, dict] = yaml.safe_load(f)["defects"]

with open(config.PROFILES_FILE, encoding="utf-8") as f:
    PROFILES: dict[str, list[str]] = yaml.safe_load(f)["profiles"]

_runtime_extra: set[str] | None = None  # test-API override, replaces env DEFECTS


def _parse_list(raw: str) -> set[str]:
    ids = {x.strip().upper() for x in raw.split(",") if x.strip()}
    unknown = ids - REGISTRY.keys()
    if unknown:
        raise ValueError(f"Unknown defect ids: {sorted(unknown)}")
    return ids


def _profile_defects() -> set[str]:
    if config.PROFILE not in PROFILES:
        raise ValueError(
            f"Unknown PROFILE={config.PROFILE!r}. Known: {sorted(PROFILES)}")
    return set(PROFILES[config.PROFILE])


def active() -> set[str]:
    extra = _runtime_extra if _runtime_extra is not None else _parse_list(config.DEFECTS_ENV)
    return _profile_defects() | extra


def is_on(defect_id: str) -> bool:
    return defect_id in active()


def set_runtime_defects(raw: str | None) -> None:
    """Test-API hook: override the extra-defects set without restarting."""
    global _runtime_extra
    _runtime_extra = None if raw is None else _parse_list(raw)


def describe() -> dict:
    act = sorted(active())
    return {
        "profile": config.PROFILE,
        "profile_defects": sorted(_profile_defects()),
        "extra_defects": sorted(
            _runtime_extra if _runtime_extra is not None else _parse_list(config.DEFECTS_ENV)),
        "active": act,
        "details": {d: {k: REGISTRY[d][k] for k in ("title", "layer", "determinism")}
                    for d in act},
    }


def validate_startup() -> None:
    _profile_defects()
    _parse_list(config.DEFECTS_ENV)
