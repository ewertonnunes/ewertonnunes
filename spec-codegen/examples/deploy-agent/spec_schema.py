"""
Pydantic schema for spec.yaml.

Mirrors the ServiceSpec pattern from the agent itself: strict types,
enums, ranges, extra=forbid. The spec cannot drift outside these
constraints. Schema validation is the first gate of the generator.
"""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, field_validator


class PyVersion(str, Enum):
    PY311 = "3.11"
    PY312 = "3.12"
    PY313 = "3.13"


class License(str, Enum):
    APACHE = "Apache-2.0"
    MIT = "MIT"
    PROPRIETARY = "Proprietary"


class ProjectMeta(BaseModel):
    model_config = {"extra": "forbid"}

    name: str = Field(..., pattern=r"^[a-z][a-z0-9-]{2,40}$")
    version: str = Field(..., pattern=r"^\d+\.\d+\.\d+$")
    description: str = Field(..., min_length=10, max_length=200)
    python_version: PyVersion
    python_requires: str = Field(..., pattern=r"^>=\d+\.\d+$")
    license: License


class CLI(BaseModel):
    model_config = {"extra": "forbid"}
    entry_point: str = Field(..., pattern=r"^[a-z_][a-z0-9_.]+:[a-z_]+$")
    command: str = Field(..., pattern=r"^[a-z][a-z0-9-]+$")


class Evals(BaseModel):
    model_config = {"extra": "forbid"}
    cases_file: str = Field(..., pattern=r"^[a-z_]+\.ya?ml$")
    min_cases: int = Field(..., ge=1, le=100)


class Model(BaseModel):
    model_config = {"extra": "forbid"}
    default: str = Field(..., pattern=r"^claude-(opus|sonnet|haiku)-\d-\d$")
    max_retries: int = Field(..., ge=1, le=10)
    temperature: float = Field(..., ge=0.0, le=1.0)


class CI(BaseModel):
    model_config = {"extra": "forbid"}
    python_versions: list[PyVersion] = Field(..., min_length=1)
    conftest_version: str = Field(..., pattern=r"^\d+\.\d+\.\d+$")
    run_evals_on_pr: bool


# A registry of every module that may appear in the project. Adding a
# new module REQUIRES adding it here AND to files/ - this is intentional
# friction to prevent silent additions.
ALLOWED_MODULES = {
    "schemas",
    "extractor",
    "renderer",
    "validator",
    "git_ops",
    "audit",
}
ALLOWED_TEMPLATES = {"deployment", "service", "configmap", "hpa"}
ALLOWED_POLICIES = {"deployment", "service", "network"}


class ProjectSpec(BaseModel):
    model_config = {"extra": "forbid"}

    project: ProjectMeta
    modules: list[str] = Field(..., min_length=1)
    cli: CLI
    templates: list[str] = Field(..., min_length=1)
    policies: list[str] = Field(..., min_length=1)
    evals: Evals
    runtime_dependencies: list[str] = Field(..., min_length=1)
    dev_dependencies: list[str] = Field(..., min_length=1)
    model: Model
    ci: CI

    @field_validator("modules")
    @classmethod
    def modules_known(cls, v: list[str]) -> list[str]:
        unknown = set(v) - ALLOWED_MODULES
        if unknown:
            raise ValueError(f"unknown modules: {unknown}")
        if len(set(v)) != len(v):
            raise ValueError("duplicate modules")
        return v

    @field_validator("templates")
    @classmethod
    def templates_known(cls, v: list[str]) -> list[str]:
        unknown = set(v) - ALLOWED_TEMPLATES
        if unknown:
            raise ValueError(f"unknown templates: {unknown}")
        return v

    @field_validator("policies")
    @classmethod
    def policies_known(cls, v: list[str]) -> list[str]:
        unknown = set(v) - ALLOWED_POLICIES
        if unknown:
            raise ValueError(f"unknown policies: {unknown}")
        return v

    @field_validator("runtime_dependencies", "dev_dependencies")
    @classmethod
    def deps_pinned(cls, v: list[str]) -> list[str]:
        """Every dep must have a version specifier - no floating deps."""
        import re

        pattern = re.compile(r"^[a-zA-Z][a-zA-Z0-9_-]*\s*[><=!~]+\s*[\d.]+")
        for dep in v:
            if not pattern.match(dep) and "types-" not in dep:
                raise ValueError(f"dependency must be pinned: {dep!r}")
        return v
