"""Renderer determinism tests."""
from __future__ import annotations

import yaml

from deploy_agent.renderer import manifest_fingerprint, render_manifest
from deploy_agent.schemas import ServiceSpec


def _spec(**overrides: object) -> ServiceSpec:
    base: dict = {
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
    base.update(overrides)
    return ServiceSpec.model_validate(base)


def test_renderer_is_byte_for_byte_deterministic() -> None:
    spec = _spec()
    a = render_manifest(spec)
    b = render_manifest(spec)
    assert a == b
    assert manifest_fingerprint(a) == manifest_fingerprint(b)


def test_different_specs_have_different_fingerprints() -> None:
    fp_a = manifest_fingerprint(render_manifest(_spec(replicas=2)))
    fp_b = manifest_fingerprint(render_manifest(_spec(replicas=3)))
    assert fp_a != fp_b


def test_manifest_has_required_kubernetes_fields() -> None:
    manifest = render_manifest(_spec())
    docs = list(yaml.safe_load_all(manifest))
    kinds = {d["kind"] for d in docs}
    assert kinds == {"Deployment", "Service"}

    deployment = next(d for d in docs if d["kind"] == "Deployment")
    container = deployment["spec"]["template"]["spec"]["containers"][0]
    assert container["resources"]["limits"]["memory"] == "512Mi"
    assert container["resources"]["limits"]["cpu"] == "250m"
    assert container["securityContext"]["runAsNonRoot"] is True
    assert container["livenessProbe"]["httpGet"]["path"] == "/healthz"


def test_image_tag_is_never_latest() -> None:
    """Anti-regression: the template must always pin a version."""
    manifest = render_manifest(_spec())
    assert ":latest" not in manifest
    assert ":v1.2.3" in manifest
