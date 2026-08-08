"""Kubernetes deployment configuration generator.

Produces standard Kubernetes YAML manifests (Deployment, Service, Ingress)
from a :class:`~.config.DeploymentConfig`.

Usage::

    from suyi.deploy import DeploymentConfig, K8sConfigGenerator

    cfg = DeploymentConfig.for_production(image="myapp:v1", replicas=3)
    gen = K8sConfigGenerator(cfg)

    print(gen.deployment_yaml())
    print(gen.service_yaml())
    print(gen.ingress_yaml())
    print(gen.all_manifests())       # combined YAML

    # Or use module-level functions
    from suyi.deploy import generate_k8s_deployment, generate_k8s_service
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .config import DeploymentConfig, Environment


def _yaml_dump(data: Any, indent: int = 0) -> str:
    """Minimal YAML serializer — produces clean, standard YAML.

    Only supports the subset of YAML needed for k8s manifests:
    dicts, lists, strings, ints, bools, None.
    """
    pad = "  " * indent
    lines: List[str] = []

    if isinstance(data, dict):
        for key, value in data.items():
            if value is None:
                lines.append(f"{pad}{key}:")
            elif isinstance(value, bool):
                lines.append(f"{pad}{key}: {'true' if value else 'false'}")
            elif isinstance(value, (int, float)):
                lines.append(f"{pad}{key}: {value}")
            elif isinstance(value, str):
                lines.append(f"{pad}{key}: {value}")
            elif isinstance(value, list):
                if not value:
                    lines.append(f"{pad}{key}: []")
                else:
                    lines.append(f"{pad}{key}:")
                    for item in value:
                        if isinstance(item, dict):
                            sub = _yaml_dump(item, indent + 1)
                            lines.append(f"{pad}  - {sub[2:] if sub.startswith('  ') else sub}")
                            for s in sub.split("\n")[1:]:
                                if s:
                                    lines.append(f"{pad}  {s}")
                        elif isinstance(item, str):
                            lines.append(f"{pad}  - {item}")
                        else:
                            lines.append(f"{pad}  - {item}")
            elif isinstance(value, dict):
                lines.append(f"{pad}{key}:")
                sub = _yaml_dump(value, indent + 1)
                lines.append(sub)
    return "\n".join(lines)


class K8sConfigGenerator:
    """Generate Kubernetes manifests from DeploymentConfig."""

    def __init__(self, config: DeploymentConfig) -> None:
        self.config = config

    # ── Deployment manifest ───────────────────────────────────

    def deployment_dict(self) -> Dict[str, Any]:
        """Build the Deployment manifest as a Python dict."""
        cfg = self.config

        # Container env vars
        env_list: List[Dict[str, Any]] = []
        for var in cfg.env_vars:
            if var.value is not None:
                env_list.append({"name": var.name, "value": str(var.value)})
            elif var.secret_ref:
                parts = var.secret_ref.split("/", 1)
                if len(parts) == 2:
                    env_list.append({
                        "name": var.name,
                        "valueFrom": {
                            "secretKeyRef": {
                                "name": parts[0],
                                "key": parts[1],
                            }
                        },
                    })

        container: Dict[str, Any] = {
            "name": cfg.app_name,
            "image": cfg.image,
            "ports": [{"containerPort": cfg.port}],
        }

        if env_list:
            container["env"] = env_list

        if cfg.command:
            container["command"] = cfg.command
        if cfg.args:
            container["args"] = cfg.args

        # Resources
        res = cfg.resources
        container["resources"] = {
            "requests": {
                "cpu": res.cpu_request,
                "memory": res.memory_request,
            },
            "limits": {
                "cpu": res.cpu_limit,
                "memory": res.memory_limit,
            },
        }

        # Health checks (probes)
        hc = cfg.health_check
        container["livenessProbe"] = {
            "httpGet": {"path": hc.path, "port": cfg.port},
            "initialDelaySeconds": hc.startup_delay,
            "periodSeconds": hc.interval,
            "timeoutSeconds": hc.timeout,
            "failureThreshold": hc.retries,
        }
        container["readinessProbe"] = {
            "httpGet": {"path": hc.path, "port": cfg.port},
            "initialDelaySeconds": hc.startup_delay,
            "periodSeconds": hc.interval,
            "timeoutSeconds": hc.timeout,
            "failureThreshold": hc.retries,
        }

        # Volume mounts
        volume_mounts: List[Dict[str, Any]] = []
        volumes: List[Dict[str, Any]] = []
        for vol_name, mount_path in cfg.volumes.items():
            volume_mounts.append({"name": vol_name, "mountPath": mount_path})
            volumes.append({"name": vol_name, "emptyDir": {}})

        if volume_mounts:
            container["volumeMounts"] = volume_mounts

        spec_containers: List[Dict[str, Any]] = [container]

        pod_spec: Dict[str, Any] = {"containers": spec_containers}
        if volumes:
            pod_spec["volumes"] = volumes

        manifest: Dict[str, Any] = {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {
                "name": cfg.app_name,
                "labels": {
                    "app": cfg.app_name,
                    "environment": cfg.environment.value,
                },
            },
            "spec": {
                "replicas": cfg.replicas,
                "selector": {
                    "matchLabels": {"app": cfg.app_name},
                },
                "template": {
                    "metadata": {
                        "labels": {"app": cfg.app_name},
                    },
                    "spec": pod_spec,
                },
            },
        }

        return manifest

    def deployment_yaml(self) -> str:
        """Return the Deployment manifest as YAML text."""
        import json
        return self._dict_to_yaml(self.deployment_dict())

    # ── Service manifest ──────────────────────────────────────

    def service_dict(self) -> Dict[str, Any]:
        """Build the Service manifest as a Python dict."""
        cfg = self.config
        return {
            "apiVersion": "v1",
            "kind": "Service",
            "metadata": {
                "name": cfg.app_name,
                "labels": {
                    "app": cfg.app_name,
                },
            },
            "spec": {
                "type": "ClusterIP" if cfg.is_production() else "NodePort",
                "selector": {"app": cfg.app_name},
                "ports": [
                    {
                        "port": 80,
                        "targetPort": cfg.port,
                        "protocol": "TCP",
                        "name": "http",
                    }
                ],
            },
        }

    def service_yaml(self) -> str:
        """Return the Service manifest as YAML text."""
        return self._dict_to_yaml(self.service_dict())

    # ── Ingress manifest ──────────────────────────────────────

    def ingress_dict(self) -> Dict[str, Any]:
        """Build the Ingress manifest as a Python dict."""
        cfg = self.config
        host = cfg.extra.get("ingress_host", f"{cfg.app_name}.local")
        return {
            "apiVersion": "networking.k8s.io/v1",
            "kind": "Ingress",
            "metadata": {
                "name": cfg.app_name,
                "labels": {"app": cfg.app_name},
                "annotations": {
                    "nginx.ingress.kubernetes.io/rewrite-target": "/",
                },
            },
            "spec": {
                "rules": [
                    {
                        "host": host,
                        "http": {
                            "paths": [
                                {
                                    "path": "/",
                                    "pathType": "Prefix",
                                    "backend": {
                                        "service": {
                                            "name": cfg.app_name,
                                            "port": {"number": 80},
                                        }
                                    },
                                }
                            ]
                        },
                    }
                ]
            },
        }

    def ingress_yaml(self) -> str:
        """Return the Ingress manifest as YAML text."""
        return self._dict_to_yaml(self.ingress_dict())

    # ── combined ──────────────────────────────────────────────

    def all_manifests(self) -> str:
        """Return all manifests combined with ``---`` separators."""
        parts = [
            self.deployment_yaml(),
            self.service_yaml(),
        ]
        if self.config.is_production():
            parts.append(self.ingress_yaml())
        return "\n---\n".join(parts)

    def to_dict(self) -> Dict[str, str]:
        """Return a dict of kind → YAML string."""
        result: Dict[str, str] = {
            "deployment.yaml": self.deployment_yaml(),
            "service.yaml": self.service_yaml(),
        }
        if self.config.is_production():
            result["ingress.yaml"] = self.ingress_yaml()
        return result

    # ── YAML serializer ───────────────────────────────────────

    @staticmethod
    def _dict_to_yaml(data: Any, indent: int = 0) -> str:
        """Recursive dict→YAML serializer."""
        pad = "  " * indent
        lines: List[str] = []

        if isinstance(data, dict):
            for key, value in data.items():
                if value is None:
                    lines.append(f"{pad}{key}: null")
                elif isinstance(value, bool):
                    lines.append(f"{pad}{key}: {'true' if value else 'false'}")
                elif isinstance(value, (int, float)):
                    lines.append(f"{pad}{key}: {value}")
                elif isinstance(value, str):
                    lines.append(f"{pad}{key}: {value}")
                elif isinstance(value, list):
                    if not value:
                        lines.append(f"{pad}{key}: []")
                    else:
                        lines.append(f"{pad}{key}:")
                        for item in value:
                            if isinstance(item, dict):
                                item_yaml = K8sConfigGenerator._dict_to_yaml(item, indent + 2)
                                first_line = item_yaml.split("\n")[0]
                                lines.append(f"{pad}  - {first_line}")
                                for s in item_yaml.split("\n")[1:]:
                                    if s:
                                        lines.append(f"{pad}  {s}")
                            elif isinstance(item, str):
                                lines.append(f"{pad}  - {item}")
                            else:
                                lines.append(f"{pad}  - {item}")
                elif isinstance(value, dict):
                    lines.append(f"{pad}{key}:")
                    sub = K8sConfigGenerator._dict_to_yaml(value, indent + 1)
                    lines.append(sub)
        return "\n".join(lines)


# ── module-level convenience ────────────────────────────────

def generate_k8s_deployment(config: DeploymentConfig) -> str:
    """Generate a Kubernetes Deployment YAML from *config*."""
    return K8sConfigGenerator(config).deployment_yaml()


def generate_k8s_service(config: DeploymentConfig) -> str:
    """Generate a Kubernetes Service YAML from *config*."""
    return K8sConfigGenerator(config).service_yaml()


def generate_k8s_ingress(config: DeploymentConfig) -> str:
    """Generate a Kubernetes Ingress YAML from *config*."""
    return K8sConfigGenerator(config).ingress_yaml()


def generate_all_k8s(config: DeploymentConfig) -> str:
    """Generate all Kubernetes manifests combined from *config*."""
    return K8sConfigGenerator(config).all_manifests()
