"""Deployment Templates — Docker and Kubernetes configuration generation.

Public API:
    - DeploymentConfig: master config (environment, health check, resources)
    - Environment: deployment environment enum
    - EnvVar: environment variable mapping
    - HealthCheck: health probe configuration
    - ResourceLimits: CPU/memory limits
    - DockerConfigGenerator: Dockerfile + docker-compose.yml generator
    - K8sConfigGenerator: Kubernetes manifest generator
    - generate_dockerfile / generate_compose: convenience functions
    - generate_k8s_deployment / generate_k8s_service / generate_k8s_ingress
    - generate_all_k8s
"""

from .config import (
    DeploymentConfig,
    Environment,
    EnvVar,
    HealthCheck,
    ResourceLimits,
)
from .docker import (
    DockerConfigGenerator,
    generate_dockerfile,
    generate_compose,
)
from .k8s import (
    K8sConfigGenerator,
    generate_k8s_deployment,
    generate_k8s_service,
    generate_k8s_ingress,
    generate_all_k8s,
)

__all__ = [
    "DeploymentConfig",
    "Environment",
    "EnvVar",
    "HealthCheck",
    "ResourceLimits",
    "DockerConfigGenerator",
    "K8sConfigGenerator",
    "generate_dockerfile",
    "generate_compose",
    "generate_k8s_deployment",
    "generate_k8s_service",
    "generate_k8s_ingress",
    "generate_all_k8s",
]
