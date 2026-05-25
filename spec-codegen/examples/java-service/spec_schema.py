"""Strict spec schema for the Java 25 app generator."""
from __future__ import annotations

from pydantic import BaseModel, Field, computed_field


class Project(BaseModel):
    model_config = {"extra": "forbid"}
    group_id: str = Field(..., pattern=r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)*$")
    artifact_id: str = Field(..., pattern=r"^[a-z][a-z0-9-]{1,40}$")
    version: str = Field(..., pattern=r"^\d+\.\d+\.\d+$")
    description: str = Field(..., min_length=10, max_length=200)
    app_name: str = Field(..., min_length=1, max_length=80)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def package(self) -> str:
        # com.example.health-api → com.example.healthapi (Java pkg-safe)
        return f"{self.group_id}.{self.artifact_id.replace('-', '')}"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def package_path(self) -> str:
        return self.package.replace(".", "/")

    @computed_field  # type: ignore[prop-decorator]
    @property
    def main_class(self) -> str:
        # health-api → HealthApiApplication
        camel = "".join(p.title() for p in self.artifact_id.split("-"))
        return f"{camel}Application"


class Java(BaseModel):
    model_config = {"extra": "forbid"}
    version: int = Field(..., ge=17, le=30)
    vendor: str = Field(..., pattern=r"^[a-z][a-z0-9-]{2,20}$")


class SpringBoot(BaseModel):
    model_config = {"extra": "forbid"}
    version: str = Field(..., pattern=r"^\d+\.\d+\.\d+$")
    parent_relative_path: str


class Server(BaseModel):
    model_config = {"extra": "forbid"}
    port: int = Field(..., ge=1024, le=65535)
    health_endpoint: str = Field(..., pattern=r"^/[a-z][a-z0-9/_-]*$")


class Build(BaseModel):
    model_config = {"extra": "forbid"}
    encoding: str = Field(..., pattern=r"^[A-Z][A-Z0-9-]+$")
    finalName: str = Field(..., pattern=r"^[a-z][a-z0-9-]+$")


class Docker(BaseModel):
    model_config = {"extra": "forbid"}
    jdk_image: str = Field(..., min_length=5)
    jre_image: str = Field(..., min_length=5)
    app_user: str = Field(..., pattern=r"^[a-z][a-z0-9]+$")
    app_uid: int = Field(..., ge=1000, le=65535)


class ProjectSpec(BaseModel):
    model_config = {"extra": "forbid"}
    project: Project
    java: Java
    spring_boot: SpringBoot
    server: Server
    build: Build
    docker: Docker
