"""
Verifier - asserts that regenerating from current sources matches the lockfile.

This is THE drift detector. Run on every PR; any deviation breaks the
build. The only legitimate way for the lockfile to change is to
regenerate it intentionally as part of a spec/files edit.
"""
from __future__ import annotations

import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import TextIO

from spec_codegen.core import Generator
from spec_codegen.lockfile import Lockfile


class VerificationFailure(Exception):
    pass


@dataclass
class VerificationReport:
    expected_count: int
    actual_count: int
    missing: list[str] = field(default_factory=list)
    extra: list[str] = field(default_factory=list)
    mismatched: list[tuple[str, str, str]] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not (self.missing or self.extra or self.mismatched)

    def print_to(self, stream: TextIO) -> None:
        if self.ok:
            stream.write(f"✓ {self.actual_count} files reproduced byte-for-byte\n")
            return
        stream.write("✗ DRIFT DETECTED\n")
        if self.missing:
            stream.write(f"\n  Missing ({len(self.missing)}):\n")
            for p in self.missing[:20]:
                stream.write(f"    - {p}\n")
        if self.extra:
            stream.write(f"\n  Unexpected ({len(self.extra)}):\n")
            for p in self.extra[:20]:
                stream.write(f"    + {p}\n")
        if self.mismatched:
            stream.write(f"\n  Hash mismatch ({len(self.mismatched)}):\n")
            for path, expected, actual in self.mismatched[:20]:
                stream.write(
                    f"    ~ {path}\n"
                    f"      expected {expected[:12]}…  got {actual[:12]}…\n"
                )


class Verifier:
    def __init__(self, generator: Generator, lockfile_path: Path) -> None:
        self.generator = generator
        self.lockfile_path = Path(lockfile_path)

    def verify(self) -> VerificationReport:
        if not self.lockfile_path.exists():
            raise VerificationFailure(
                f"lockfile not found: {self.lockfile_path}. "
                "Run the generator with write_lockfile=True first."
            )
        expected = Lockfile.read(self.lockfile_path).files

        with tempfile.TemporaryDirectory() as tmp:
            result = self.generator.generate(Path(tmp))

        actual = result.hashes
        missing = sorted(set(expected) - set(actual))
        extra = sorted(set(actual) - set(expected))
        mismatched = sorted(
            (p, expected[p], actual[p])
            for p in set(expected) & set(actual)
            if expected[p] != actual[p]
        )
        return VerificationReport(
            expected_count=len(expected),
            actual_count=len(actual),
            missing=missing,
            extra=extra,
            mismatched=mismatched,
        )

    def run_cli(self, stream: TextIO = sys.stderr) -> int:
        try:
            report = self.verify()
        except VerificationFailure as exc:
            stream.write(f"FATAL: {exc}\n")
            return 2
        report.print_to(stream)
        return 0 if report.ok else 1
