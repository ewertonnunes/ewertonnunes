"""
Append-only audit log.

Every agent run writes a JSON line capturing the full provenance:
  - what the human asked
  - what the LLM extracted (raw + validated)
  - which template version was used
  - the manifest fingerprint
  - the outcome

This makes every deployment trivially auditable and replayable.
"""
from __future__ import annotations

import json
import os
import socket
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class AuditRecord:
    timestamp: str
    actor: str
    host: str
    request: str
    extracted: dict[str, Any]
    attempts: int
    fingerprint: str
    outcome: str  # "pr_opened" | "validation_failed" | "extraction_failed"
    error: str | None = None


def write_audit(record: AuditRecord, *, log_path: Path | None = None) -> None:
    log_path = log_path or Path(
        os.getenv("DEPLOY_AGENT_AUDIT_LOG", "/var/log/deploy-agent/audit.jsonl")
    )
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(asdict(record), separators=(",", ":")) + "\n")


def new_record(
    *,
    request: str,
    extracted: dict[str, Any],
    attempts: int,
    fingerprint: str,
    outcome: str,
    error: str | None = None,
) -> AuditRecord:
    return AuditRecord(
        timestamp=datetime.now(timezone.utc).isoformat(),
        actor=os.getenv("DEPLOY_AGENT_ACTOR", "deploy-agent"),
        host=socket.gethostname(),
        request=request,
        extracted=extracted,
        attempts=attempts,
        fingerprint=fingerprint,
        outcome=outcome,
        error=error,
    )
