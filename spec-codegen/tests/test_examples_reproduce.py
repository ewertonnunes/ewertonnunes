"""
End-to-end test: every example in examples/ must regenerate
byte-for-byte from its own spec + files + lockfile.

This is the META verification: the whole methodology stands or
falls on this test going green.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

from spec_codegen import Generator, Verifier
from spec_codegen.lockfile import Lockfile

EXAMPLES_DIR = Path(__file__).parent.parent / "examples"


def _load_spec_class(spec_schema_path: Path) -> type:
    spec_obj = importlib.util.spec_from_file_location(
        f"spec_schema_{spec_schema_path.parent.name}", spec_schema_path
    )
    assert spec_obj is not None and spec_obj.loader is not None
    module = importlib.util.module_from_spec(spec_obj)
    sys.modules[spec_obj.name] = module
    spec_obj.loader.exec_module(module)
    return module.ProjectSpec


@pytest.fixture(params=[d for d in EXAMPLES_DIR.iterdir() if d.is_dir()])
def example_dir(request: pytest.FixtureRequest) -> Path:
    return request.param


def _make_generator(example_dir: Path) -> Generator:
    return Generator(
        files_dir=example_dir / "files",
        spec_path=example_dir / "spec.yaml",
        spec_class=_load_spec_class(example_dir / "spec_schema.py"),
    )


def test_example_has_required_files(example_dir: Path) -> None:
    assert (example_dir / "spec.yaml").exists()
    assert (example_dir / "spec_schema.py").exists()
    assert (example_dir / "files").is_dir()
    assert (example_dir / "lockfile.json").exists(), (
        f"{example_dir.name}: missing lockfile.json. "
        "Generate it with: spec-codegen generate --write-lockfile"
    )


def test_example_verifies(example_dir: Path, tmp_path: Path) -> None:
    """Every example regenerates byte-for-byte from sources alone."""
    gen = _make_generator(example_dir)
    report = Verifier(gen, example_dir / "lockfile.json").verify()
    assert report.ok, (
        f"{example_dir.name}: drift detected. "
        f"missing={report.missing} extra={report.extra} "
        f"mismatched={[m[0] for m in report.mismatched]}"
    )


def test_example_destroy_recreate_thrice(example_dir: Path, tmp_path: Path) -> None:
    """Three independent regenerations produce identical aggregate hash."""
    gen = _make_generator(example_dir)
    hashes = []
    for i in range(3):
        out = tmp_path / f"run-{i}"
        result = gen.generate(out)
        hashes.append(result.aggregate_hash())
    assert len(set(hashes)) == 1, f"{example_dir.name}: drift across 3 runs: {hashes}"


def test_example_lockfile_is_byte_stable_json(example_dir: Path) -> None:
    """The lockfile itself round-trips through JSON without changing bytes."""
    lockfile_path = example_dir / "lockfile.json"
    original = lockfile_path.read_text(encoding="utf-8")
    parsed = json.loads(original)
    lf = Lockfile(
        file_count=parsed["file_count"],
        files=parsed["files"],
        version=parsed.get("version", 1),
    )
    assert lf.to_json() == original, (
        f"{example_dir.name}: lockfile.json is not byte-stable JSON. "
        "Did you edit it by hand? Regenerate via --write-lockfile."
    )
