"""Canonical candidate Source of Truth loader.

The profile is deliberately data-only. External JD research must not mutate it.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


DEFAULT_SOURCE_OF_TRUTH = Path("candidate/source_of_truth.json")


class CandidateSourceOfTruthError(ValueError):
    """Raised when the canonical candidate profile is missing or malformed."""


def load_candidate_source_of_truth(path: Path = DEFAULT_SOURCE_OF_TRUTH) -> dict[str, Any]:
    """Load and validate the canonical candidate evidence profile."""
    if not path.exists():
        raise CandidateSourceOfTruthError(f"candidate Source of Truth not found: {path}")

    try:
        profile = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CandidateSourceOfTruthError(f"invalid candidate Source of Truth JSON: {path}") from exc

    required = {"schema_version", "candidate", "experience", "projects", "skills_and_tools", "truth_and_tailoring_rules"}
    missing = sorted(required - profile.keys())
    if missing:
        raise CandidateSourceOfTruthError(f"candidate Source of Truth missing keys: {', '.join(missing)}")

    if not isinstance(profile["experience"], list) or not isinstance(profile["projects"], list):
        raise CandidateSourceOfTruthError("experience and projects must be lists")

    skills = profile["skills_and_tools"]
    if not isinstance(skills, dict):
        raise CandidateSourceOfTruthError("skills_and_tools must be an object")
    for category in ("professional_experience", "project_experience", "knowledge_and_professional_development"):
        if category not in skills or not isinstance(skills[category], list):
            raise CandidateSourceOfTruthError(f"skills_and_tools.{category} must be a list")

    return profile
