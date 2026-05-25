"""
Deterministic template rendering.

No LLM is involved here. Same spec in → same manifest out, byte-for-byte.
The template is the contract; the spec only fills in the blanks.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from .schemas import ServiceSpec

TEMPLATES_DIR = Path(__file__).parent.parent.parent / "templates" / "kubernetes"

_env = Environment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)),
    undefined=StrictUndefined,  # fail loudly on missing vars
    keep_trailing_newline=True,
    autoescape=False,  # YAML, not HTML
)


def render_manifest(spec: ServiceSpec) -> str:
    """Render the full multi-document manifest (Deployment + Service)."""
    # mode="json" coerces enums to their string values so Jinja
    # writes "512Mi", not "MemorySize.S".
    vars_ = spec.model_dump(mode="json")
    deployment = _env.get_template("deployment.yaml.j2").render(**vars_)
    service = _env.get_template("service.yaml.j2").render(**vars_)
    return f"{deployment}---\n{service}"


def manifest_fingerprint(manifest: str) -> str:
    """
    SHA-256 of the rendered manifest. Used to verify that the same spec
    always produces the same output, and to track exact-match across
    destroy/recreate cycles.
    """
    return hashlib.sha256(manifest.encode("utf-8")).hexdigest()
