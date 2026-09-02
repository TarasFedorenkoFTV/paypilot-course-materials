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
_runtime_profile: str | None = None      # test-API override, replaces env PROFILE


def _parse_list(raw: str) -> set[str]:
    ids = {x.strip().upper() for x in raw.split(",") if x.strip()}
    unknown = ids - REGISTRY.keys()
    if unknown:
        raise ValueError(f"Unknown defect ids: {sorted(unknown)}")
    return ids


def current_profile() -> str:
    return _runtime_profile if _runtime_profile is not None else config.PROFILE


def _profile_defects() -> set[str]:
    name = current_profile()
    if name not in PROFILES:
        raise ValueError(f"Unknown PROFILE={name!r}. Known: {sorted(PROFILES)}")
    return set(PROFILES[name])


def set_runtime_profile(name: str | None) -> None:
    """Test-API hook: switch the lesson profile without restarting."""
    global _runtime_profile
    if name is not None and name not in PROFILES:
        raise ValueError(f"Unknown profile {name!r}. Known: {sorted(PROFILES)}")
    _runtime_profile = name


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
        "profile": current_profile(),
        "known_profiles": sorted(PROFILES),
        "profile_defects": sorted(_profile_defects()),
        "extra_defects": sorted(
            _runtime_extra if _runtime_extra is not None else _parse_list(config.DEFECTS_ENV)),
        "active": act,
        # Only what the registry actually carries. The student-facing build
        # ships ids without titles or layers, because "what this defect does
        # and where to look for it" is the answer to the homework.
        "details": {d: {k: REGISTRY[d][k]
                        for k in ("title", "layer", "determinism")
                        if k in REGISTRY[d]}
                    for d in act},
    }


def validate_startup() -> None:
    _profile_defects()
    _parse_list(config.DEFECTS_ENV)
