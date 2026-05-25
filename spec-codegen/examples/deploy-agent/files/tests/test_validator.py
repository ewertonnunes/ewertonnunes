"""Validator tests - especially drift detection."""
from __future__ import annotations

import pytest

from deploy_agent.validator import ValidationFailure, validate_drift, validate_yaml_structure


def test_validate_yaml_accepts_valid_manifest() -> None:
    validate_yaml_structure(
        "apiVersion: v1\nkind: Service\nmetadata:\n  name: foo\n"
    )


def test_validate_yaml_rejects_malformed() -> None:
    with pytest.raises(ValidationFailure):
        validate_yaml_structure("{not: valid: yaml")


def test_validate_yaml_rejects_missing_kind() -> None:
    with pytest.raises(ValidationFailure):
        validate_yaml_structure("apiVersion: v1\nname: foo\n")


def test_drift_allows_empty() -> None:
    validate_drift("")


def test_drift_allows_image_bump() -> None:
    diff = """\
--- old
+++ new
@@ -1,3 +1,3 @@
-          image: payments/api:v1.0.0
+          image: payments/api:v1.1.0
"""
    validate_drift(diff)


def test_drift_allows_replica_change() -> None:
    diff = """\
--- old
+++ new
-  replicas: 2
+  replicas: 3
"""
    validate_drift(diff)


def test_drift_rejects_namespace_change() -> None:
    diff = """\
--- old
+++ new
-  namespace: staging
+  namespace: prod
"""
    with pytest.raises(ValidationFailure, match="drift"):
        validate_drift(diff)


def test_drift_rejects_new_volume_mount() -> None:
    diff = """\
--- old
+++ new
+          volumeMounts:
+            - name: secrets
+              mountPath: /etc/secrets
"""
    with pytest.raises(ValidationFailure, match="drift"):
        validate_drift(diff)


def test_drift_rejects_security_context_change() -> None:
    diff = """\
--- old
+++ new
-            runAsNonRoot: true
+            runAsNonRoot: false
"""
    with pytest.raises(ValidationFailure, match="drift"):
        validate_drift(diff)
