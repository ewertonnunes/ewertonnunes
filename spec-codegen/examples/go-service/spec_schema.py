"""Strict spec schema for the Go app generator."""
from __future__ import annotations

from pydantic import BaseModel, Field, computed_field


class Project(BaseModel):
    model_config = {"extra": "forbid"}
    module: str = Field(
        ...,
        pattern=r"^[a-z][a-z0-9._/-]{4,200}$",
        description="Go module path, e.g. github.com/org/name",
    )
    name: str = Field(..., pattern=r"^[a-z][a-z0-9-]{1,40}$")
    version: str = Field(..., pattern=r"^\d+\.\d+\.\d+$")
    description: str = Field(..., min_length=10, max_length=200)
    app_name: str = Field(..., min_length=1, max_length=80)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def package_health(self) -> str:
        # All Go imports of the handler package go through this string,
        # derived from module + internal path. Single source = single truth.
        return f"{self.module}/internal/handler"


class Go(BaseModel):
    model_config = {"extra": "forbid"}
    version: str = Field(..., pattern=r"^\d+\.\d+$")
    toolchain: str = Field(..., pattern=r"^go\d+\.\d+\.\d+$")


class Server(BaseModel):
    model_config = {"extra": "forbid"}
    port: int = Field(..., ge=1024, le=65535)
    health_endpoint: str = Field(..., pattern=r"^/[a-z][a-z0-9/_-]*$")
    read_timeout_seconds: int = Field(..., ge=1, le=300)
    write_timeout_seconds: int = Field(..., ge=1, le=300)
    shutdown_timeout_seconds: int = Field(..., ge=1, le=600)


class Build(BaseModel):
    model_config = {"extra": "forbid"}
    binary_name: str = Field(..., pattern=r"^[a-z][a-z0-9_-]{1,40}$")


class Docker(BaseModel):
    model_config = {"extra": "forbid"}
    builder_image: str = Field(..., pattern=r"^[a-z0-9][a-z0-9:._/-]{4,80}$")
    runtime_image: str = Field(..., pattern=r"^[a-z0-9][a-z0-9:._/-]{2,80}$")
    app_user: str = Field(..., pattern=r"^[a-z][a-z0-9]+$")
    app_uid: int = Field(..., ge=1000, le=65535)


class ProjectSpec(BaseModel):
    model_config = {"extra": "forbid"}
    project: Project
    go: Go
    server: Server
    build: Build
    docker: Docker
