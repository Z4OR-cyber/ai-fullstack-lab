"""Tests for Deployment Templates (Phase 11)."""

from __future__ import annotations

import pytest

from suyi.deploy import (
    DeploymentConfig,
    Environment,
    EnvVar,
    HealthCheck,
    ResourceLimits,
    DockerConfigGenerator,
    K8sConfigGenerator,
    generate_dockerfile,
    generate_compose,
    generate_k8s_deployment,
    generate_k8s_service,
    generate_k8s_ingress,
    generate_all_k8s,
)


# ── Config tests ──────────────────────────────────────────────

class TestEnvVar:
    def test_basic_env_var(self):
        v = EnvVar("API_KEY", value="secret123")
        assert v.name == "API_KEY"
        assert v.value == "secret123"
        assert v.required is True

    def test_secret_env_var(self):
        v = EnvVar("DB_PASS", secret_ref="secrets/db-pass")
        assert v.secret_ref == "secrets/db-pass"
        assert v.value is None

    def test_env_var_to_dict(self):
        v = EnvVar("KEY", value="val", required=False, description="desc")
        d = v.to_dict()
        assert d["name"] == "KEY"
        assert d["value"] == "val"
        assert d["required"] is False
        assert d["description"] == "desc"


class TestHealthCheck:
    def test_defaults(self):
        hc = HealthCheck()
        assert hc.path == "/health"
        assert hc.port == 8000
        assert hc.interval == 30
        assert hc.timeout == 5
        assert hc.retries == 3

    def test_liveness_dict(self):
        hc = HealthCheck(path="/healthz", port=9000, interval=15)
        d = hc.to_liveness_dict()
        assert d["type"] == "liveness"
        assert d["http_path"] == "/healthz"
        assert d["port"] == 9000
        assert d["interval_seconds"] == 15

    def test_readiness_dict(self):
        hc = HealthCheck()
        d = hc.to_readiness_dict()
        assert d["type"] == "readiness"
        assert d["http_path"] == "/health"


class TestResourceLimits:
    def test_defaults(self):
        r = ResourceLimits()
        assert r.cpu_request == "100m"
        assert r.cpu_limit == "500m"
        assert r.memory_request == "128Mi"
        assert r.memory_limit == "256Mi"

    def test_to_dict(self):
        r = ResourceLimits(cpu_request="200m", cpu_limit="1000m")
        d = r.to_dict()
        assert d["requests"]["cpu"] == "200m"
        assert d["limits"]["cpu"] == "1000m"


class TestDeploymentConfig:
    def test_defaults(self):
        cfg = DeploymentConfig()
        assert cfg.app_name == "suyi-app"
        assert cfg.image == "suyi:latest"
        assert cfg.environment == Environment.DEVELOPMENT
        assert cfg.port == 8000
        assert cfg.replicas == 1

    def test_for_development(self):
        cfg = DeploymentConfig.for_development()
        assert cfg.is_development()
        assert not cfg.is_production()
        assert cfg.replicas == 1
        assert any(v.name == "SUYI_ENV" for v in cfg.env_vars)

    def test_for_production(self):
        cfg = DeploymentConfig.for_production(replicas=5)
        assert cfg.is_production()
        assert cfg.replicas == 5
        assert any(v.name == "OPENAI_API_KEY" for v in cfg.env_vars)

    def test_add_env_var(self):
        cfg = DeploymentConfig()
        cfg.add_env_var(EnvVar("CUSTOM", value="value"))
        assert any(v.name == "CUSTOM" for v in cfg.env_vars)

    def test_to_dict(self):
        cfg = DeploymentConfig(app_name="test", port=9000)
        d = cfg.to_dict()
        assert d["app_name"] == "test"
        assert d["port"] == 9000
        assert "env_vars" in d
        assert "resources" in d

    def test_custom_volumes(self):
        cfg = DeploymentConfig(volumes={"data": "/app/data"})
        assert cfg.volumes["data"] == "/app/data"

    def test_custom_command(self):
        cfg = DeploymentConfig(command=["python", "app.py"])
        assert cfg.command == ["python", "app.py"]


# ── Docker tests ──────────────────────────────────────────────

class TestDockerGenerator:
    def test_dockerfile_basic(self):
        cfg = DeploymentConfig(app_name="myapp", image="myapp:1.0", port=8080)
        gen = DockerConfigGenerator(cfg)
        df = gen.dockerfile()
        assert "FROM python:3.12-slim" in df
        assert "WORKDIR /app" in df
        assert "EXPOSE 8080" in df
        assert "HEALTHCHECK" in df
        assert "suyi" in df  # CMD

    def test_dockerfile_with_env_vars(self):
        cfg = DeploymentConfig(
            env_vars=[EnvVar("FOO", value="bar"), EnvVar("BAZ", value="qux")],
        )
        df = generate_dockerfile(cfg)
        assert "ENV FOO=bar" in df
        assert "ENV BAZ=qux" in df

    def test_dockerfile_labels(self):
        cfg = DeploymentConfig(app_name="testapp", image="testapp:v2")
        df = generate_dockerfile(cfg)
        assert 'LABEL app="testapp"' in df

    def test_dockerfile_custom_command(self):
        cfg = DeploymentConfig(command=["python", "main.py"])
        df = generate_dockerfile(cfg)
        assert "python main.py" in df

    def test_compose_basic(self):
        cfg = DeploymentConfig(app_name="myapp", image="myapp:1.0", port=8080)
        gen = DockerConfigGenerator(cfg)
        compose = gen.compose_yaml()
        assert "version:" in compose
        assert "services:" in compose
        assert "myapp:" in compose
        assert "8080:8080" in compose

    def test_compose_environment(self):
        cfg = DeploymentConfig(
            env_vars=[EnvVar("KEY", value="val")],
        )
        compose = generate_compose(cfg)
        assert "KEY: val" in compose

    def test_compose_volumes(self):
        cfg = DeploymentConfig(volumes={"data_vol": "/app/data"})
        compose = generate_compose(cfg)
        assert "data_vol:/app/data" in compose
        assert "volumes:" in compose.split("myapp:")[-1] or "data_vol" in compose

    def test_compose_restart_policy(self):
        cfg = DeploymentConfig.for_production()
        compose = generate_compose(cfg)
        assert "restart: always" in compose

        cfg_dev = DeploymentConfig.for_development()
        compose_dev = generate_compose(cfg_dev)
        assert "restart: on-failure" in compose_dev

    def test_compose_healthcheck(self):
        cfg = DeploymentConfig()
        compose = generate_compose(cfg)
        assert "healthcheck:" in compose
        assert "interval:" in compose

    def test_to_dict(self):
        cfg = DeploymentConfig()
        gen = DockerConfigGenerator(cfg)
        d = gen.to_dict()
        assert "Dockerfile" in d
        assert "docker-compose.yml" in d

    def test_production_dockerfile(self):
        cfg = DeploymentConfig.for_production(image="prod:v1")
        df = generate_dockerfile(cfg)
        assert "python:3.12-slim" in df
        assert "SUYI_ENV=production" in df


# ── Kubernetes tests ─────────────────────────────────────────

class TestK8sGenerator:
    def test_deployment_dict_basic(self):
        cfg = DeploymentConfig(app_name="test", image="test:1.0", port=8080)
        gen = K8sConfigGenerator(cfg)
        d = gen.deployment_dict()
        assert d["apiVersion"] == "apps/v1"
        assert d["kind"] == "Deployment"
        assert d["metadata"]["name"] == "test"
        assert d["spec"]["replicas"] == 1

    def test_deployment_yaml_basic(self):
        cfg = DeploymentConfig(app_name="test", image="test:1.0")
        gen = K8sConfigGenerator(cfg)
        yml = gen.deployment_yaml()
        assert "apiVersion: apps/v1" in yml
        assert "kind: Deployment" in yml
        assert "test" in yml

    def test_deployment_with_env_vars(self):
        cfg = DeploymentConfig(
            env_vars=[EnvVar("FOO", value="bar")],
        )
        gen = K8sConfigGenerator(cfg)
        d = gen.deployment_dict()
        container = d["spec"]["template"]["spec"]["containers"][0]
        assert any(e["name"] == "FOO" for e in container["env"])

    def test_deployment_with_secret_ref(self):
        cfg = DeploymentConfig(
            env_vars=[EnvVar("SECRET", secret_ref="mysecrets/key")],
        )
        gen = K8sConfigGenerator(cfg)
        d = gen.deployment_dict()
        container = d["spec"]["template"]["spec"]["containers"][0]
        env_entry = [e for e in container["env"] if e["name"] == "SECRET"][0]
        assert "valueFrom" in env_entry
        assert env_entry["valueFrom"]["secretKeyRef"]["name"] == "mysecrets"

    def test_deployment_probes(self):
        cfg = DeploymentConfig()
        gen = K8sConfigGenerator(cfg)
        d = gen.deployment_dict()
        container = d["spec"]["template"]["spec"]["containers"][0]
        assert "livenessProbe" in container
        assert "readinessProbe" in container
        assert container["livenessProbe"]["httpGet"]["path"] == "/health"

    def test_deployment_resources(self):
        cfg = DeploymentConfig()
        gen = K8sConfigGenerator(cfg)
        d = gen.deployment_dict()
        container = d["spec"]["template"]["spec"]["containers"][0]
        res = container["resources"]
        assert "requests" in res
        assert "limits" in res
        assert res["limits"]["cpu"] == "500m"

    def test_deployment_volumes(self):
        cfg = DeploymentConfig(volumes={"data_vol": "/app/data"})
        gen = K8sConfigGenerator(cfg)
        d = gen.deployment_dict()
        pod_spec = d["spec"]["template"]["spec"]
        assert "volumes" in pod_spec
        assert any(v["name"] == "data_vol" for v in pod_spec["volumes"])
        container = pod_spec["containers"][0]
        assert any(vm["name"] == "data_vol" for vm in container["volumeMounts"])

    def test_deployment_replicas(self):
        cfg = DeploymentConfig.for_production(replicas=5)
        gen = K8sConfigGenerator(cfg)
        d = gen.deployment_dict()
        assert d["spec"]["replicas"] == 5

    def test_service_dict(self):
        cfg = DeploymentConfig(app_name="test", port=8080)
        gen = K8sConfigGenerator(cfg)
        d = gen.service_dict()
        assert d["apiVersion"] == "v1"
        assert d["kind"] == "Service"
        assert d["metadata"]["name"] == "test"
        assert d["spec"]["ports"][0]["targetPort"] == 8080

    def test_service_yaml(self):
        cfg = DeploymentConfig()
        gen = K8sConfigGenerator(cfg)
        yml = gen.service_yaml()
        assert "kind: Service" in yml

    def test_service_type_production(self):
        cfg = DeploymentConfig.for_production()
        gen = K8sConfigGenerator(cfg)
        d = gen.service_dict()
        assert d["spec"]["type"] == "ClusterIP"

    def test_service_type_development(self):
        cfg = DeploymentConfig.for_development()
        gen = K8sConfigGenerator(cfg)
        d = gen.service_dict()
        assert d["spec"]["type"] == "NodePort"

    def test_ingress_dict(self):
        cfg = DeploymentConfig.for_production()
        cfg.extra["ingress_host"] = "myapp.example.com"
        gen = K8sConfigGenerator(cfg)
        d = gen.ingress_dict()
        assert d["apiVersion"] == "networking.k8s.io/v1"
        assert d["kind"] == "Ingress"
        assert d["spec"]["rules"][0]["host"] == "myapp.example.com"

    def test_ingress_yaml(self):
        cfg = DeploymentConfig.for_production()
        gen = K8sConfigGenerator(cfg)
        yml = gen.ingress_yaml()
        assert "kind: Ingress" in yml

    def test_all_manifests(self):
        cfg = DeploymentConfig.for_production()
        gen = K8sConfigGenerator(cfg)
        combined = gen.all_manifests()
        assert "---" in combined
        assert "Deployment" in combined
        assert "Service" in combined
        assert "Ingress" in combined

    def test_all_manifests_dev_no_ingress(self):
        cfg = DeploymentConfig.for_development()
        gen = K8sConfigGenerator(cfg)
        combined = gen.all_manifests()
        assert "Deployment" in combined
        assert "Service" in combined
        # Ingress should not be in dev mode
        assert "Ingress" not in combined

    def test_to_dict(self):
        cfg = DeploymentConfig.for_production()
        gen = K8sConfigGenerator(cfg)
        d = gen.to_dict()
        assert "deployment.yaml" in d
        assert "service.yaml" in d
        assert "ingress.yaml" in d

    def test_to_dict_dev(self):
        cfg = DeploymentConfig.for_development()
        gen = K8sConfigGenerator(cfg)
        d = gen.to_dict()
        assert "deployment.yaml" in d
        assert "service.yaml" in d
        assert "ingress.yaml" not in d

    def test_generate_k8s_deployment(self):
        cfg = DeploymentConfig()
        yml = generate_k8s_deployment(cfg)
        assert "Deployment" in yml

    def test_generate_k8s_service(self):
        cfg = DeploymentConfig()
        yml = generate_k8s_service(cfg)
        assert "Service" in yml

    def test_generate_k8s_ingress(self):
        cfg = DeploymentConfig.for_production()
        yml = generate_k8s_ingress(cfg)
        assert "Ingress" in yml

    def test_generate_all_k8s(self):
        cfg = DeploymentConfig.for_production()
        yml = generate_all_k8s(cfg)
        assert "Deployment" in yml
        assert "Service" in yml
        assert "Ingress" in yml

    def test_deployment_with_command(self):
        cfg = DeploymentConfig(command=["python", "main.py"])
        gen = K8sConfigGenerator(cfg)
        d = gen.deployment_dict()
        container = d["spec"]["template"]["spec"]["containers"][0]
        assert container["command"] == ["python", "main.py"]

    def test_deployment_labels(self):
        cfg = DeploymentConfig(app_name="myapp")
        gen = K8sConfigGenerator(cfg)
        d = gen.deployment_dict()
        labels = d["metadata"]["labels"]
        assert labels["app"] == "myapp"
        assert labels["environment"] == "development"

    def test_deployment_selector(self):
        cfg = DeploymentConfig(app_name="myapp")
        gen = K8sConfigGenerator(cfg)
        d = gen.deployment_dict()
        selector = d["spec"]["selector"]
        assert selector["matchLabels"]["app"] == "myapp"

    def test_health_check_custom_path(self):
        cfg = DeploymentConfig(health_check=HealthCheck(path="/healthz"))
        gen = K8sConfigGenerator(cfg)
        d = gen.deployment_dict()
        container = d["spec"]["template"]["spec"]["containers"][0]
        assert container["livenessProbe"]["httpGet"]["path"] == "/healthz"
