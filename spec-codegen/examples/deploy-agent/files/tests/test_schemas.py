"""Schema-level tests. These are the contract the LLM cannot violate."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from deploy_agent.schemas import ServiceSpec


def _base() -> dict:
    return {
        "service_name": "payment-api",
        "environment": "staging",
        "team": "payments",
        "image": "payments/payment-api",
        "version": "v1.2.3",
        "replicas": 2,
        "memory": "512Mi",
        "cpu": "250m",
        "port": 8080,
        "confidence": "high",
    }


def test_happy_path() -> None:
    spec = ServiceSpec.model_validate(_base())
    assert spec.service_name == "payment-api"


@pytest.mark.parametrize(
    "field,value",
    [
        ("service_name", "Payment_API"),       # uppercase + underscore
        ("service_name", "ab"),                # too short
        ("service_name", "x" * 32),            # too long
        ("environment", "production"),         # not in enum
        ("team", "growth"),                    # unknown team
        ("version", "1.2.3"),                  # missing v prefix
        ("version", "v1.2"),                   # incomplete semver
        ("replicas", 0),                       # below min
        ("replicas", 11),                      # above max
        ("memory", "3Gi"),                     # not an allowed size
        ("cpu", "750m"),                       # not an allowed size
        ("port", 80),                          # below 1024
        ("port", 70000),                       # above 65535
        ("confidence", "definitely"),          # not high/medium/low
    ],
)
def test_field_rejects_invalid(field: str, value: object) -> None:
    payload = _base()
    payload[field] = value
    with pytest.raises(ValidationError):
        ServiceSpec.model_validate(payload)


def test_prod_requires_two_replicas() -> None:
    payload = _base()
    payload["environment"] = "prod"
    payload["replicas"] = 1
    with pytest.raises(ValidationError, match="prod requires"):
        ServiceSpec.model_validate(payload)


def test_extra_fields_forbidden() -> None:
    """The LLM cannot smuggle extra fields past the schema."""
    payload = _base()
    payload["sudo"] = True
    payload["debug_mode"] = "yes"
    with pytest.raises(ValidationError):
        ServiceSpec.model_validate(payload)
