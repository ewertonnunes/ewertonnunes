"""
The deterministic generator core.

Pipeline (no LLM, no randomness, no fs-order dependence):
    spec.yaml
        ↓
    Pydantic validation
        ↓
    sorted walk of files/ tree
        ↓
    for each file:
       - render path with {{ var }} if present
       - if .tmpl suffix: render content with Jinja
       - else: copy bytes verbatim
        ↓
    SHA-256 every output
        ↓
    return GenerationResult

Determinism guarantees baked in:
  - sorted(rglob) - filesystem order ignored
  - StrictUndefined - missing vars are loud
  - keep_trailing_newline=True - no newline drift
  - .tmpl marker (not .j2, which is reserved for the project's own
    runtime Jinja templates - see DESIGN.md)
  - .keep marker files for empty directories
"""
from __future__ import annotations

import hashlib
import shutil
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from jinja2 import Environment, FileSystemLoader, StrictUndefined
from pydantic import BaseModel

from spec_codegen.filters import register_default_filters

TEMPLATE_SUFFIX = ".tmpl"
KEEP_FILE = ".keep"


@dataclass
class GenerationResult:
    """The output of a generation run."""

    output_dir: Path
    file_count: int
    hashes: dict[str, str] = field(default_factory=dict)

    def aggregate_hash(self) -> str:
        """Single SHA-256 over the entire ordered file set."""
        h = hashlib.sha256()
        for path in sorted(self.hashes):
            h.update(path.encode("utf-8"))
            h.update(b"\0")
            h.update(self.hashes[path].encode("ascii"))
            h.update(b"\n")
        return h.hexdigest()


class Generator:
    """
    Render a project from a spec + files tree.

    Typical use::

        from pydantic import BaseModel
        from spec_codegen import Generator

        class MySpec(BaseModel):
            name: str
            version: str

        gen = Generator(
            files_dir=Path("./files"),
            spec_path=Path("./spec.yaml"),
            spec_class=MySpec,
        )
        result = gen.generate(output_dir=Path("./output"))
        print(result.aggregate_hash())
    """

    def __init__(
        self,
        files_dir: Path,
        spec_path: Path,
        spec_class: type[BaseModel],
        *,
        context_builder: Callable[[BaseModel], dict[str, Any]] | None = None,
        extra_filters: dict[str, Callable[..., Any]] | None = None,
    ) -> None:
        self.files_dir = Path(files_dir)
        self.spec_path = Path(spec_path)
        self.spec_class = spec_class
        self._context_builder = context_builder or self._default_context
        self._extra_filters = extra_filters or {}

        if not self.files_dir.is_dir():
            raise FileNotFoundError(f"files_dir not found: {self.files_dir}")
        if not self.spec_path.is_file():
            raise FileNotFoundError(f"spec_path not found: {self.spec_path}")

    # ─────────────────────────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────────────────────────

    def generate(
        self,
        output_dir: Path,
        *,
        clean: bool = True,
    ) -> GenerationResult:
        spec = self.load_spec()
        output_dir = Path(output_dir)

        if clean and output_dir.exists():
            shutil.rmtree(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        env = self._build_environment()
        context = self._context_builder(spec)
        hashes: dict[str, str] = {}

        for src in sorted(self.files_dir.rglob("*")):
            if not src.is_file():
                continue
            rel = src.relative_to(self.files_dir)
            rendered_rel = self._render_path(str(rel), env, context)

            if src.name == KEEP_FILE:
                (output_dir / Path(rendered_rel).parent).mkdir(
                    parents=True, exist_ok=True
                )
                continue

            if src.suffix == TEMPLATE_SUFFIX:
                template_name = str(rel)
                content = (
                    env.get_template(template_name).render(**context).encode("utf-8")
                )
                out_rel = Path(rendered_rel).with_suffix("")
            else:
                content = src.read_bytes()
                out_rel = Path(rendered_rel)

            dst = output_dir / out_rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(content)
            hashes[str(out_rel)] = hashlib.sha256(content).hexdigest()

        return GenerationResult(
            output_dir=output_dir, file_count=len(hashes), hashes=hashes
        )

    def load_spec(self) -> BaseModel:
        raw = yaml.safe_load(self.spec_path.read_text(encoding="utf-8"))
        return self.spec_class.model_validate(raw)

    # ─────────────────────────────────────────────────────────────────
    # Internals
    # ─────────────────────────────────────────────────────────────────

    def _build_environment(self) -> Environment:
        env = Environment(
            loader=FileSystemLoader(str(self.files_dir)),
            undefined=StrictUndefined,
            keep_trailing_newline=True,
            autoescape=False,
        )
        register_default_filters(env)
        for name, fn in self._extra_filters.items():
            env.filters[name] = fn
        return env

    @staticmethod
    def _default_context(spec: BaseModel) -> dict[str, Any]:
        """Top-level model fields, JSON-serialized for enum/datetime safety."""
        return spec.model_dump(mode="json")

    @staticmethod
    def _render_path(path_str: str, env: Environment, ctx: dict[str, Any]) -> str:
        if "{{" not in path_str:
            return path_str
        return env.from_string(path_str).render(**ctx)
