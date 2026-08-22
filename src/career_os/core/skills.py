"""Portable Agent Skills discovery, validation, and loading.

The runtime keeps skill metadata cheap to discover and loads the full SKILL.md body
only when a caller asks for a specific skill. No model provider or external service
is required for this layer.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

_NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class SkillError(ValueError):
    """Raised when a skill is missing, malformed, or invalid."""


@dataclass(frozen=True)
class SkillDefinition:
    """A discovered skill with metadata and its instruction body."""

    name: str
    description: str
    path: Path
    instructions: str


class SkillRegistry:
    """Discover and progressively load Agent Skills from a skills directory."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    def discover(self) -> tuple[SkillDefinition, ...]:
        if not self.root.exists():
            return ()
        if not self.root.is_dir():
            raise SkillError(f"Skill root is not a directory: {self.root}")

        skills: list[SkillDefinition] = []
        for skill_dir in sorted(self.root.iterdir(), key=lambda p: p.name):
            if skill_dir.is_dir() and not skill_dir.name.startswith("."):
                skills.append(self._read(skill_dir))
        return tuple(skills)

    def get(self, name: str) -> SkillDefinition:
        if not _NAME_RE.fullmatch(name):
            raise SkillError(f"Invalid skill name: {name!r}")
        path = self.root / name
        if not path.is_dir():
            raise SkillError(f"Unknown skill: {name}")
        return self._read(path)

    def _read(self, skill_dir: Path) -> SkillDefinition:
        name = skill_dir.name
        if not _NAME_RE.fullmatch(name) or len(name) > 64:
            raise SkillError(f"Invalid skill directory name: {name!r}")

        skill_file = skill_dir / "SKILL.md"
        if not skill_file.is_file():
            raise SkillError(f"Skill {name!r} is missing SKILL.md")

        raw = skill_file.read_text(encoding="utf-8")
        metadata, instructions = _parse_skill(raw)
        declared_name = metadata.get("name", "")
        description = metadata.get("description", "")

        if declared_name != name:
            raise SkillError(
                f"Skill {name!r} declares name {declared_name!r}; directory and metadata must match"
            )
        if not description:
            raise SkillError(f"Skill {name!r} requires a non-empty description")
        if len(description) > 1024:
            raise SkillError(f"Skill {name!r} description exceeds 1024 characters")
        if not instructions.strip():
            raise SkillError(f"Skill {name!r} has no instructions")

        return SkillDefinition(name, description, skill_file, instructions.strip())


def _parse_skill(raw: str) -> tuple[dict[str, str], str]:
    """Parse the portable name/description frontmatter without PyYAML."""

    if not raw.startswith("---\n"):
        raise SkillError("SKILL.md must start with YAML frontmatter")

    end = raw.find("\n---\n", 4)
    if end == -1:
        raise SkillError("SKILL.md frontmatter is not closed")

    metadata: dict[str, str] = {}
    for line in raw[4:end].splitlines():
        if not line.strip():
            continue
        key, separator, value = line.partition(":")
        if not separator:
            raise SkillError(f"Invalid frontmatter line: {line!r}")
        key = key.strip()
        value = value.strip()
        if key not in {"name", "description"}:
            # Ignore optional standard metadata so the loader stays portable.
            continue
        if value.startswith(("'", '"')) and value.endswith(value[0]):
            value = value[1:-1]
        metadata[key] = value

    return metadata, raw[end + len("\n---\n") :]
