"""
Run the golden-cases eval suite.

This is the only thing standing between you and silent regressions
after a prompt edit or model upgrade. Run on every PR that touches
the agent prompt, schema, or model version.

Exit code:
  0  - all cases passed
  1  - one or more regressions
"""
from __future__ import annotations

import sys
from pathlib import Path

import yaml

from deploy_agent.extractor import ExtractionError, extract_spec

CASES_FILE = Path(__file__).parent / "golden_cases.yaml"


def _check_exact(expected: dict, got: dict) -> list[str]:
    errors: list[str] = []
    for k, v in expected.items():
        actual = got.get(k)
        if actual != v:
            errors.append(f"  {k}: expected {v!r}, got {actual!r}")
    return errors


def main() -> int:
    cases = yaml.safe_load(CASES_FILE.read_text())
    passed = failed = 0

    for case in cases:
        name = case["name"]
        request = case["request"]
        print(f"▶ {name}")

        try:
            result = extract_spec(request)
        except ExtractionError as exc:
            if case.get("expected_outcome") in {
                "low_confidence_or_failure",
                "extraction_failed_or_normalized",
            }:
                print(f"  ✓ acceptable failure: {exc}")
                passed += 1
            else:
                print(f"  ✗ unexpected extraction failure: {exc}")
                failed += 1
            continue

        got = result.raw_input

        if "expected" in case:
            errors = _check_exact(case["expected"], got)
            if errors:
                print("  ✗ mismatch:")
                for e in errors:
                    print(e)
                failed += 1
            else:
                print(f"  ✓ exact match (attempts={result.attempts})")
                passed += 1
        elif case.get("expected_outcome") == "low_confidence_or_failure":
            if got.get("confidence") == "low":
                print("  ✓ low confidence as expected")
                passed += 1
            else:
                print(f"  ✗ expected low confidence, got {got.get('confidence')!r}")
                failed += 1
        elif case.get("expected_outcome") == "extraction_failed_or_normalized":
            if got.get("service_name") in {"payment-api", "payment-api-svc"}:
                print(f"  ✓ normalized to {got['service_name']}")
                passed += 1
            else:
                print(f"  ✗ unexpected service_name: {got.get('service_name')!r}")
                failed += 1

    print(f"\n{passed} passed, {failed} failed")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
