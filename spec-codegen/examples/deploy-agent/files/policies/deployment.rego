package main

# Hard requirements that EVERY deployment must satisfy. These are
# non-negotiable: the agent cannot bypass them because conftest blocks
# the pipeline before kubectl apply runs.

deny[msg] {
  input.kind == "Deployment"
  not input.spec.template.spec.containers[_].resources.limits.memory
  msg := "containers must declare memory limits"
}

deny[msg] {
  input.kind == "Deployment"
  not input.spec.template.spec.containers[_].resources.limits.cpu
  msg := "containers must declare cpu limits"
}

deny[msg] {
  input.kind == "Deployment"
  not input.spec.template.spec.containers[_].livenessProbe
  msg := "containers must declare a livenessProbe"
}

deny[msg] {
  input.kind == "Deployment"
  not input.spec.template.spec.containers[_].readinessProbe
  msg := "containers must declare a readinessProbe"
}

deny[msg] {
  input.kind == "Deployment"
  not input.spec.template.spec.containers[_].securityContext.runAsNonRoot
  msg := "containers must run as non-root"
}

deny[msg] {
  input.kind == "Deployment"
  input.spec.template.spec.containers[_].securityContext.allowPrivilegeEscalation == true
  msg := "privilege escalation is forbidden"
}

deny[msg] {
  input.kind == "Deployment"
  endswith(input.spec.template.spec.containers[_].image, ":latest")
  msg := "the :latest tag is forbidden - pin a semver version"
}

deny[msg] {
  input.kind == "Deployment"
  input.metadata.namespace == "prod"
  input.spec.replicas < 2
  msg := "prod deployments require >=2 replicas (HA)"
}

deny[msg] {
  input.kind == "Deployment"
  not input.metadata.labels.team
  msg := "deployments must have a team label for ownership"
}

deny[msg] {
  input.kind == "Deployment"
  not input.metadata.labels["app.kubernetes.io/managed-by"]
  msg := "must be labeled managed-by"
}

deny[msg] {
  input.kind == "Deployment"
  input.metadata.labels["app.kubernetes.io/managed-by"] != "deploy-agent"
  msg := "managed-by label must be deploy-agent"
}
