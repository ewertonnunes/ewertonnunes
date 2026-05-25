"""
CLI entry point.

Pipeline:
  request (NL)  ─►  extractor (LLM)  ─►  spec
                                          │
                                          ▼
                                    renderer (Jinja2)
                                          │
                                          ▼
                                       manifest
                                          │
                       ┌──────────────────┼──────────────────┐
                       ▼                  ▼                  ▼
                  yaml-parse           policy           kubectl diff
                       └──────────────────┼──────────────────┘
                                          ▼
                                       git PR
                                          │
                                          ▼
                                      audit log

The LLM appears exactly once (extractor). Every later stage is
deterministic, idempotent, and gated.
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from .audit import new_record, write_audit
from .extractor import ExtractionError, extract_spec
from .git_ops import create_pull_request
from .renderer import manifest_fingerprint, render_manifest
from .validator import ValidationFailure, validate_all


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="deploy-agent")
    parser.add_argument("request", help="Natural language deployment request")
    parser.add_argument(
        "--repo",
        type=Path,
        required=True,
        help="Path to the manifests Git repo (already cloned)",
    )
    parser.add_argument(
        "--skip-cluster",
        action="store_true",
        help="Skip kubectl diff (use in CI without cluster access)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Render and validate but do not open a PR",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    # ── 1. Extract ────────────────────────────────────────────────────
    try:
        result = extract_spec(args.request)
    except ExtractionError as exc:
        write_audit(
            new_record(
                request=args.request,
                extracted={},
                attempts=0,
                fingerprint="",
                outcome="extraction_failed",
                error=str(exc),
            )
        )
        print(f"EXTRACTION FAILED: {exc}", file=sys.stderr)
        return 2

    spec = result.spec
    print(f"Extracted spec (confidence={spec.confidence}): {spec.service_name} "
          f"v{spec.version} -> {spec.environment.value}")

    # ── 2. Render ─────────────────────────────────────────────────────
    manifest = render_manifest(spec)
    fingerprint = manifest_fingerprint(manifest)

    # ── 3. Validate ───────────────────────────────────────────────────
    try:
        validate_all(manifest, skip_cluster=args.skip_cluster)
    except ValidationFailure as exc:
        write_audit(
            new_record(
                request=args.request,
                extracted=result.raw_input,
                attempts=result.attempts,
                fingerprint=fingerprint,
                outcome="validation_failed",
                error=str(exc),
            )
        )
        print(f"VALIDATION FAILED: {exc}", file=sys.stderr)
        return 3

    if args.dry_run:
        print(manifest)
        print(f"\n# fingerprint: {fingerprint}", file=sys.stderr)
        return 0

    # ── 4. Open PR ────────────────────────────────────────────────────
    pr = create_pull_request(spec, manifest, repo_path=args.repo)
    write_audit(
        new_record(
            request=args.request,
            extracted=result.raw_input,
            attempts=result.attempts,
            fingerprint=fingerprint,
            outcome="pr_opened",
        )
    )

    print(f"branch pushed: {pr.branch}")
    print(f"title: {pr.title}")
    print(f"fingerprint: {pr.fingerprint}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
