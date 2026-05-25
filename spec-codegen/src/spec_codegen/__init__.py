"""
spec-codegen: deterministic, spec-driven project generation.

The library that distills the pattern: spec.yaml + Pydantic schema +
files/ templates → byte-identical project, every time, anywhere.

Public API:
    Generator   - render a project from spec + files
    Verifier    - assert a generated project matches a lockfile
    Filters     - registry of Jinja filters (pynum, etc.)
"""
from __future__ import annotations

from spec_codegen.core import GenerationResult, Generator
from spec_codegen.filters import register_default_filters
from spec_codegen.lockfile import Lockfile
from spec_codegen.verify import VerificationFailure, Verifier

__version__ = "1.0.0"
__all__ = [
    "GenerationResult",
    "Generator",
    "Lockfile",
    "VerificationFailure",
    "Verifier",
    "register_default_filters",
]
