"""
Strict schemas for deployment parameters.

These schemas are the single source of truth for what the LLM is allowed
to produce. Every field has a tight type, enum, or pattern. The LLM
*cannot* invent values outside these constraints - the Anthropic tool-use
API enforces the JSON schema at the model level, and Pydantic validates
again on our side as defense in depth.
"""
from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class Environment(str, Enum):
    DEV = "dev"
    STAGING = "staging"
    PROD = "prod"


class Team(str, Enum):
    PAYMENTS = "payments"
    AUTH = "auth"
    DATA = "data"
    PLATFORM = "platform"
    CHECKOUT = "checkout"


class MemorySize(str, Enum):
    XS = "256Mi"
    S = "512Mi"
    M = "1Gi"
    L = "2Gi"
    XL = "4Gi"


class CPUSize(str, Enum):
    XS = "100m"
    S = "250m"
    M = "500m"
    L = "1000m"
    XL = "2000m"


class ServiceSpec(BaseModel):
    """
    The only thing the LLM can output. Every change to production
    flows through these fields. Anything outside this schema is
    rejected before reaching the renderer.
    """

    model_config = {"extra": "forbid"}  # reject unknown fields

    service_name: str = Field(
        ...,
        pattern=r"^[a-z][a-z0-9-]{2,30}$",
        description="Kebab-case service name, 3-31 chars, lowercase",
    )
    environment: Environment = Field(..., description="Target environment")
    team: Team = Field(..., description="Owning team")
    image: str = Field(
        ...,
        pattern=r"^[a-z0-9][a-z0-9._/-]{1,100}$",
        description="Container image name without tag",
    )
    version: str = Field(
        ...,
        pattern=r"^v\d+\.\d+\.\d+$",
        description="Semver tag with v prefix, e.g. v1.2.3",
    )
    replicas: int = Field(..., ge=1, le=10, description="Replica count, 1-10")
    memory: MemorySize = Field(..., description="Memory limit (T-shirt size)")
    cpu: CPUSize = Field(..., description="CPU limit (T-shirt size)")
    port: int = Field(..., ge=1024, le=65535, description="Container port")
    confidence: str = Field(
        ...,
        description="LLM's confidence in the extraction",
    )

    @field_validator("confidence")
    @classmethod
    def confidence_must_be_known(cls, v: str) -> str:
        if v not in {"high", "medium", "low"}:
            raise ValueError("confidence must be high|medium|low")
        return v

    @field_validator("replicas")
    @classmethod
    def prod_min_replicas(cls, v: int, info: Any) -> int:
        env = info.data.get("environment")
        if env == Environment.PROD and v < 2:
            raise ValueError("prod requires >=2 replicas (HA)")
        return v


def anthropic_tool_schema() -> dict[str, Any]:
    """
    Convert the Pydantic schema into the format Anthropic's tool-use API
    expects. The model is forced to call this tool, so its output is
    guaranteed to match the schema (modulo the validators above).
    """
    schema = ServiceSpec.model_json_schema()
    # Anthropic expects input_schema, not the full JSON-schema envelope.
    return {
        "name": "build_service_spec",
        "description": (
            "Extract Kubernetes service parameters from a deployment "
            "request. Use ONLY values present in the user request or "
            "team conventions. Never invent service names or versions."
        ),
        "input_schema": {
            "type": "object",
            "properties": schema["properties"],
            "required": schema["required"],
            "additionalProperties": False,
        },
    }
