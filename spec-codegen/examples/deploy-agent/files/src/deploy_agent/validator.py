"""
Manifest validation and drift detection.

Runs AFTER rendering and BEFORE any cluster mutation. If any check
fails, the pipeline halts. No LLM involved - pure deterministic
checks against policies and known-good baselines.

Layers (each must pass):
  1. Structural YAML validity
  2. OPA / conftest policy check
  3. Drift check: server-side dry-run diff must be within allow-list
"""
from __future__ import annotations

import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

import yaml

POLICIES_DIR = Path(__file__).parent.parent.parent / "policies"


@dataclass
class ValidationFailure(Exception):
    stage: str
    details: str

    def __str__(self) -> str:
        return f"[{self.stage}] {self.details}"


def validate_yaml_structure(manifest: str) -> None:
    """Stage 1: every document must be parseable as YAML."""
    try:
        docs = list(yaml.safe_load_all(manifest))
    except yaml.YAMLError as exc:
        raise ValidationFailure("yaml-parse", str(exc)) from exc
    if not docs or any(d is None for d in docs):
        raise ValidationFailure("yaml-parse", "empty or null document")
    for doc in docs:
        if "apiVersion" not in doc or "kind" not in doc:
            raise ValidationFailure(
                "yaml-parse", f"missing apiVersion/kind in {doc!r}"
            )


def validate_policy(manifest: str) -> None:
    """
    Stage 2: conftest against the Rego policies in /policies.
    Requires `conftest` binary on PATH in CI.
    """
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".yaml", delete=False
    ) as tmp:
        tmp.write(manifest)
        tmp_path = tmp.name

    result = subprocess.run(
        [
            "conftest",
            "test",
            tmp_path,
            "--policy",
            str(POLICIES_DIR),
            "--no-color",
        ],
        capture_output=True,
        text=True,
    )
    Path(tmp_path).unlink(missing_ok=True)

    if result.returncode != 0:
        raise ValidationFailure(
            "policy",
            f"conftest failed:\n{result.stdout}\n{result.stderr}",
        )


# Regex for kubectl diff output. Allowed changes are limited to:
#   - image tag (version bump)
#   - replica count
#   - resource requests/limits
# Anything else triggers a drift failure.
_ALLOWED_DIFF_PATHS = re.compile(
    r"^\s*[+-]\s+(image:|replicas:|memory:|cpu:|imagePullPolicy:)"
)


def validate_drift(diff_output: str) -> None:
    """
    Stage 3: parse `kubectl diff` output. Every changed line must match
    the allow-list of fields the agent is permitted to change.
    """
    if not diff_output.strip():
        return  # no diff = no drift

    suspicious: list[str] = []
    for line in diff_output.splitlines():
        if not line.startswith(("+", "-")):
            continue
        if line.startswith(("+++", "---")):
            continue  # diff headers
        if _ALLOWED_DIFF_PATHS.match(line):
            continue
        suspicious.append(line)

    if suspicious:
        raise ValidationFailure(
            "drift",
            "unexpected fields changed:\n" + "\n".join(suspicious[:20]),
        )


def kubectl_diff(manifest: str) -> str:
    """Server-side dry-run diff. Returns the unified diff string."""
    result = subprocess.run(
        ["kubectl", "diff", "-f", "-"],
        input=manifest,
        capture_output=True,
        text=True,
    )
    # kubectl diff returns 1 when there ARE diffs - that's expected
    if result.returncode not in (0, 1):
        raise ValidationFailure("kubectl-diff", result.stderr)
    return result.stdout


def validate_all(manifest: str, *, skip_cluster: bool = False) -> None:
    """Run all validation stages in order."""
    validate_yaml_structure(manifest)
    validate_policy(manifest)
    if not skip_cluster:
        diff = kubectl_diff(manifest)
        validate_drift(diff)
