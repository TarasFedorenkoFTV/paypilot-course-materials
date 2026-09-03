"""System prompt assembly: a versioned base file + defect overlays
(ТЗ §5.1). Spec-level defects are enabled by overlaying fragments onto the
base prompt without editing the base file.

Overlay file format — YAML frontmatter between '---' lines, then a body:
  mode: replace_section   (needs `section:` — the exact heading text)
  mode: append            (body appended at the end)
  mode: remove_text       (body's exact text removed from the prompt)
Overlays compose: they are applied in defect-id order and touch disjoint
parts of the base by construction (combinability requirement, ТЗ §5.8)."""
import re

import hashlib
from pathlib import Path

from app import config, defects

BASE_FILE = config.PROMPTS_DIR / "base.v1.md"
OVERLAYS_DIR = config.PROMPTS_DIR / "overlays"


def _parse_overlay(text: str) -> tuple[dict, str]:
    m = re.match(r"^---\n(.*?)\n---\n?(.*)$", text, re.S)
    if not m:
        raise ValueError("overlay must start with a '---' frontmatter block")
    meta = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip().strip('"')
    return meta, m.group(2).strip()


def _split_sections(base: str) -> list[tuple[str, str]]:
    """[(heading, block)] where block includes the heading line."""
    parts = re.split(r"(?m)^(## .+)$", base)
    sections: list[tuple[str, str]] = [("", parts[0])]  # preamble before first ##
    for i in range(1, len(parts), 2):
        heading = parts[i].removeprefix("## ").strip()
        body = parts[i] + (parts[i + 1] if i + 1 < len(parts) else "")
        sections.append((heading, body))
    return sections


def _apply(base: str, meta: dict, body: str, overlay_name: str) -> str:
    mode = meta.get("mode")
    if mode == "append":
        return base.rstrip() + "\n\n" + body + "\n"
    if mode == "remove_text":
        if body not in base:
            raise ValueError(f"{overlay_name}: remove_text target not found in prompt")
        return base.replace(body, "").rstrip() + "\n"
    if mode == "replace_section":
        target = meta.get("section", "")
        sections = _split_sections(base)
        if target not in [h for h, _ in sections]:
            raise ValueError(f"{overlay_name}: section {target!r} not found")
        out = []
        for heading, block in sections:
            out.append(body + "\n" if heading == target else block)
        return "".join(out).rstrip() + "\n"
    raise ValueError(f"{overlay_name}: unknown overlay mode {mode!r}")


def overlay_slug(defect_id: str) -> str:
    """Stable opaque name for an overlay file.

    The student build renames the overlays to these, because a directory of
    files called D01.md ... D27.md is a register index: it lets anyone grep
    straight to the answer for a given lesson without running anything. The
    file content still has to ship — the stand applies it at runtime, and
    GET /api/_test/prompt shows the assembled prompt anyway when the profile
    is on, by design. What goes away is the shortcut.
    """
    return hashlib.sha1(f"paypilot-overlay-{defect_id}".encode()).hexdigest()[:12]


def _overlay_file(defect_id: str) -> Path | None:
    """Readable name first, opaque name second: one code path for both trees."""
    for name in (f"{defect_id}.md", f"{overlay_slug(defect_id)}.md"):
        candidate = OVERLAYS_DIR / name
        if candidate.exists():
            return candidate
    return None


def active_overlays() -> list[str]:
    """Prompt-layer defects that are active AND have an overlay file."""
    return [d for d in sorted(defects.active()) if _overlay_file(d)]


def build() -> tuple[str, str]:
    """Returns (prompt_text, prompt_version)."""
    base = BASE_FILE.read_text(encoding="utf-8")
    applied = []
    for d in active_overlays():
        meta, body = _parse_overlay(
            _overlay_file(d).read_text(encoding="utf-8"))
        base = _apply(base, meta, body, d)
        applied.append(d)
    version = "base.v1" + ("" if not applied else "+" + "+".join(applied))
    return base, version
