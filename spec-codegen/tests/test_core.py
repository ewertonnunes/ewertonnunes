"""Tests for spec_codegen.core."""
from __future__ import annotations

import io
from pathlib import Path

import pytest
from pydantic import BaseModel

from spec_codegen import Generator, Lockfile, Verifier


class SimpleSpec(BaseModel):
    model_config = {"extra": "forbid"}
    name: str
    version: str
    port: int


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    """A tiny but complete spec-codegen workspace."""
    files = tmp_path / "files"
    files.mkdir()

    (files / "README.md.tmpl").write_text(
        "# {{ name }}\n\nVersion: {{ version }}\n", encoding="utf-8"
    )
    (files / "config.yaml.tmpl").write_text(
        "name: {{ name }}\nport: {{ port }}\n", encoding="utf-8"
    )
    (files / "static.txt").write_text("verbatim content\n", encoding="utf-8")
    (tmp_path / "spec.yaml").write_text(
        "name: my-app\nversion: 1.2.3\nport: 8080\n", encoding="utf-8"
    )
    return tmp_path


def _make_gen(workspace: Path) -> Generator:
    return Generator(
        files_dir=workspace / "files",
        spec_path=workspace / "spec.yaml",
        spec_class=SimpleSpec,
    )


# ── Determinism ──────────────────────────────────────────────────────


def test_generation_is_byte_stable(workspace: Path) -> None:
    gen = _make_gen(workspace)
    r1 = gen.generate(workspace / "out1")
    r2 = gen.generate(workspace / "out2")
    assert r1.aggregate_hash() == r2.aggregate_hash()
    assert r1.hashes == r2.hashes


def test_destroy_and_recreate(workspace: Path) -> None:
    gen = _make_gen(workspace)
    h1 = gen.generate(workspace / "out").aggregate_hash()
    import shutil
    shutil.rmtree(workspace / "out")
    h2 = gen.generate(workspace / "out").aggregate_hash()
    assert h1 == h2


def test_three_runs_identical(workspace: Path) -> None:
    gen = _make_gen(workspace)
    hashes = [gen.generate(workspace / f"out{i}").aggregate_hash() for i in range(3)]
    assert len(set(hashes)) == 1


# ── Schema validation ────────────────────────────────────────────────


def test_invalid_spec_rejected(workspace: Path) -> None:
    (workspace / "spec.yaml").write_text("name: my-app\nport: 8080\n")  # missing version
    gen = _make_gen(workspace)
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        gen.generate(workspace / "out")


def test_extra_fields_rejected(workspace: Path) -> None:
    (workspace / "spec.yaml").write_text(
        "name: my-app\nversion: 1.0.0\nport: 8080\nsudo: true\n"
    )
    gen = _make_gen(workspace)
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        gen.generate(workspace / "out")


# ── Template handling ────────────────────────────────────────────────


def test_tmpl_files_are_rendered(workspace: Path) -> None:
    gen = _make_gen(workspace)
    result = gen.generate(workspace / "out")
    readme = (result.output_dir / "README.md").read_text()
    assert "# my-app" in readme
    assert "Version: 1.2.3" in readme


def test_non_tmpl_files_copied_verbatim(workspace: Path) -> None:
    gen = _make_gen(workspace)
    result = gen.generate(workspace / "out")
    assert (result.output_dir / "static.txt").read_text() == "verbatim content\n"


def test_missing_variable_is_strict(workspace: Path) -> None:
    (workspace / "files" / "bad.tmpl").write_text("{{ undefined_var }}\n")
    gen = _make_gen(workspace)
    from jinja2.exceptions import UndefinedError
    with pytest.raises(UndefinedError):
        gen.generate(workspace / "out")


def test_path_templating(workspace: Path) -> None:
    """{{ name }} in a directory name renders correctly."""
    nested = workspace / "files" / "pkg" / "{{name}}"
    nested.mkdir(parents=True)
    (nested / "info.txt.tmpl").write_text("hello {{ name }}\n", encoding="utf-8")

    gen = _make_gen(workspace)
    result = gen.generate(workspace / "out")
    assert (result.output_dir / "pkg" / "my-app" / "info.txt").exists()


def test_keep_marker_creates_empty_dir(workspace: Path) -> None:
    empty_marker = workspace / "files" / "tests" / "fixtures" / ".keep"
    empty_marker.parent.mkdir(parents=True)
    empty_marker.touch()

    gen = _make_gen(workspace)
    result = gen.generate(workspace / "out")
    assert (result.output_dir / "tests" / "fixtures").is_dir()
    assert not (result.output_dir / "tests" / "fixtures" / ".keep").exists()


# ── Lockfile + Verifier ──────────────────────────────────────────────


def test_lockfile_roundtrip(workspace: Path) -> None:
    gen = _make_gen(workspace)
    result = gen.generate(workspace / "out")
    lockfile_path = workspace / "lockfile.json"
    Lockfile.from_hashes(result.hashes).write(lockfile_path)
    loaded = Lockfile.read(lockfile_path)
    assert loaded.files == result.hashes


def test_verifier_passes_on_no_drift(workspace: Path) -> None:
    gen = _make_gen(workspace)
    result = gen.generate(workspace / "out")
    lockfile_path = workspace / "lockfile.json"
    Lockfile.from_hashes(result.hashes).write(lockfile_path)

    report = Verifier(gen, lockfile_path).verify()
    assert report.ok


def test_verifier_detects_content_drift(workspace: Path) -> None:
    gen = _make_gen(workspace)
    result = gen.generate(workspace / "out")
    lockfile_path = workspace / "lockfile.json"
    Lockfile.from_hashes(result.hashes).write(lockfile_path)

    # Modify a template — should now produce different bytes
    (workspace / "files" / "README.md.tmpl").write_text("# CHANGED {{ name }}\n")

    report = Verifier(gen, lockfile_path).verify()
    assert not report.ok
    assert any("README.md" in p for p, _, _ in report.mismatched)


def test_verifier_detects_new_file(workspace: Path) -> None:
    gen = _make_gen(workspace)
    result = gen.generate(workspace / "out")
    lockfile_path = workspace / "lockfile.json"
    Lockfile.from_hashes(result.hashes).write(lockfile_path)

    (workspace / "files" / "newfile.txt").write_text("surprise!\n")

    report = Verifier(gen, lockfile_path).verify()
    assert not report.ok
    assert "newfile.txt" in report.extra


def test_verifier_detects_deleted_file(workspace: Path) -> None:
    gen = _make_gen(workspace)
    result = gen.generate(workspace / "out")
    lockfile_path = workspace / "lockfile.json"
    Lockfile.from_hashes(result.hashes).write(lockfile_path)

    (workspace / "files" / "static.txt").unlink()

    report = Verifier(gen, lockfile_path).verify()
    assert not report.ok
    assert "static.txt" in report.missing


def test_verifier_cli_returns_codes(workspace: Path) -> None:
    gen = _make_gen(workspace)
    result = gen.generate(workspace / "out")
    lockfile_path = workspace / "lockfile.json"
    Lockfile.from_hashes(result.hashes).write(lockfile_path)

    verifier = Verifier(gen, lockfile_path)

    # Pass
    buf = io.StringIO()
    assert verifier.run_cli(buf) == 0
    assert "byte-for-byte" in buf.getvalue()

    # Fail after drift
    (workspace / "files" / "README.md.tmpl").write_text("# DRIFT\n")
    buf = io.StringIO()
    assert verifier.run_cli(buf) == 1
    assert "DRIFT DETECTED" in buf.getvalue()


# ── Filters ──────────────────────────────────────────────────────────


def test_pynum_filter_renders_whole_floats(workspace: Path) -> None:
    """pynum: 0.0 → "0", 0.5 → "0.5". Avoids 'temperature=0.0' drift."""
    (workspace / "files" / "render.txt.tmpl").write_text("{{ 0.0 | pynum }}\n")
    gen = _make_gen(workspace)
    result = gen.generate(workspace / "out")
    assert (result.output_dir / "render.txt").read_text() == "0\n"


def test_pynum_preserves_fractional(workspace: Path) -> None:
    (workspace / "files" / "render.txt.tmpl").write_text("{{ 0.5 | pynum }}\n")
    gen = _make_gen(workspace)
    result = gen.generate(workspace / "out")
    assert (result.output_dir / "render.txt").read_text() == "0.5\n"
