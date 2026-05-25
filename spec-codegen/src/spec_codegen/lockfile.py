"""
Lockfile: the byte-stable JSON manifest of the last accepted generation.

This is the equivalent of `package-lock.json` / `Cargo.lock` for
spec-driven generators. The lockfile records the SHA-256 of every
output file. `Verifier` compares regeneration against this file;
any drift is a CI-breaking event.

Stability tricks:
  - sort_keys=True
  - ensure_ascii=True
  - trailing LF newline
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

LOCKFILE_VERSION = 1


@dataclass
class Lockfile:
    file_count: int
    files: dict[str, str]
    version: int = LOCKFILE_VERSION

    @classmethod
    def from_hashes(cls, hashes: dict[str, str]) -> Lockfile:
        return cls(file_count=len(hashes), files=dict(sorted(hashes.items())))

    def to_json(self) -> str:
        payload: dict[str, Any] = {
            "file_count": self.file_count,
            "files": dict(sorted(self.files.items())),
            "version": self.version,
        }
        return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n"

    def write(self, path: Path) -> None:
        Path(path).write_text(self.to_json(), encoding="utf-8")

    @classmethod
    def read(cls, path: Path) -> Lockfile:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(
            file_count=raw["file_count"],
            files=raw["files"],
            version=raw.get("version", LOCKFILE_VERSION),
        )
