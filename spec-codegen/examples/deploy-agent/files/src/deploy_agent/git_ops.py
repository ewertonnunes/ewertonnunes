"""
Git operations for the GitOps flow.

The agent NEVER applies manifests directly to a cluster. It opens a PR
against the manifests repo. A separate controller (ArgoCD/Flux) reads
the merged state from Git and reconciles the cluster. This means:

  - All changes are reviewed (PR diff)
  - All changes are auditable (Git history)
  - All changes are reversible (git revert)
  - Drift is auto-corrected by the controller
"""
from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .renderer import manifest_fingerprint
from .schemas import ServiceSpec

logger = logging.getLogger(__name__)


@dataclass
class PullRequest:
    branch: str
    title: str
    body: str
    manifest_path: Path
    fingerprint: str


def _run(cmd: list[str], cwd: Path) -> str:
    """Run a git command, raise on non-zero exit."""
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"command failed {cmd}: {result.stderr}")
    return result.stdout


def create_pull_request(
    spec: ServiceSpec,
    manifest: str,
    *,
    repo_path: Path,
    base_branch: str = "main",
    actor: str = "deploy-agent",
) -> PullRequest:
    """
    Write the manifest to <repo>/apps/<env>/<service>.yaml, commit it
    on a fresh branch, and push. The PR itself is opened by the calling
    CI step (or `gh pr create`) using the returned metadata.
    """
    branch = f"deploy/{spec.environment.value}/{spec.service_name}-{spec.version}"
    rel_path = Path("apps") / spec.environment.value / f"{spec.service_name}.yaml"
    abs_path = repo_path / rel_path

    abs_path.parent.mkdir(parents=True, exist_ok=True)
    abs_path.write_text(manifest, encoding="utf-8")

    fp = manifest_fingerprint(manifest)
    title = (
        f"deploy({spec.environment.value}): {spec.service_name} "
        f"-> {spec.version}"
    )
    body = (
        f"Automated deployment PR opened by {actor}.\n\n"
        f"- Service: `{spec.service_name}`\n"
        f"- Environment: `{spec.environment.value}`\n"
        f"- Version: `{spec.version}`\n"
        f"- Replicas: `{spec.replicas}`\n"
        f"- Resources: `{spec.cpu}` cpu / `{spec.memory}` memory\n"
        f"- Manifest fingerprint: `{fp}`\n\n"
        "This PR was rendered from the golden template. Any diff "
        "outside the allow-list (image, replicas, resources) is a bug."
    )

    _run(["git", "checkout", "-B", branch, f"origin/{base_branch}"], cwd=repo_path)
    _run(["git", "add", str(rel_path)], cwd=repo_path)
    _run(
        [
            "git",
            "-c",
            f"user.name={actor}",
            "-c",
            "user.email=deploy-agent@example.com",
            "commit",
            "-m",
            title,
            "-m",
            f"fingerprint: {fp}",
        ],
        cwd=repo_path,
    )
    _run(["git", "push", "-u", "origin", branch, "--force-with-lease"], cwd=repo_path)

    logger.info("opened branch %s with fingerprint %s", branch, fp)
    return PullRequest(
        branch=branch,
        title=title,
        body=body,
        manifest_path=abs_path,
        fingerprint=fp,
    )
