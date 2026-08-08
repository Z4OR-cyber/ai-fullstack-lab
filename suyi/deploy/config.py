"""Deployment configuration — environment variables, health checks, resource limits.

This module defines data structures that the Docker and Kubernetes generators
consume to produce final configuration files.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class Environment(str, Enum):
    """Deployment environment."""

    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


@dataclass
class EnvVar:
    """An environment variable mapping.

    Attributes:
        name: The variable name (e.g. ``OPENAI_API_KEY``).
        value: A literal default value (use ``secret_ref`` for secrets).
        secret_ref: Reference to a secret, *not* the literal value.
        required: Whether the variable must be set at deploy time.
        description: Human-readable description.
    """

    name: str
    value: Optional[str] = None
    secret_ref: Optional[str] = None
    required: bool = True
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "name": self.name,
            "required": self.required,
        }
        if self.value is not None:
            d["value"] = self.value
        if self.secret_ref is not None:
            d["secret_ref"] = self.secret_ref
        if self.description:
            d["description"] = self.description
        return d


@dataclass
class HealthCheck:
    """Container health-check configuration.

    Attributes:
        path: HTTP path for liveness/readiness probe.
        port: Port number.
        interval: Probe interval in seconds.
        timeout: Probe timeout in seconds.
        retries: Number of consecutive failures before marking unhealthy.
        startup_delay: Initial delay before first probe (seconds).
    """

    path: str = "/health"
    port: int = 8000
    interval: int = 30
    timeout: int = 5
    retries: int = 3
    startup_delay: int = 10

    def to_liveness_dict(self) -> Dict[str, Any]:
        return {
            "type": "liveness",
            "http_path": self.path,
            "port": self.port,
            "interval_seconds": self.interval,
            "timeout_seconds": self.timeout,
            "failure_threshold": self.retries,
            "initial_delay_seconds": self.startup_delay,
        }

    def to_readiness_dict(self) -> Dict[str, Any]:
        return {
            "type": "readiness",
            "http_path": self.path,
            "port": self.port,
            "interval_seconds": self.interval,
            "timeout_seconds": self.timeout,
            "failure_threshold": self.retries,
            "initial_delay_seconds": self.startup_delay,
        }


@dataclass
class ResourceLimits:
    """CPU and memory limits / requests.

    Attributes:
        cpu_request: CPU request (e.g. ``"100m"``).
        cpu_limit: CPU limit (e.g. ``"500m"``).
        memory_request: Memory request (e.g. ``"128Mi"``).
        memory_limit: Memory limit (e.g. ``"256Mi"``).
    """

    cpu_request: str = "100m"
    cpu_limit: str = "500m"
    memory_request: str = "128Mi"
    memory_limit: str = "256Mi"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "requests": {"cpu": self.cpu_request, "memory": self.memory_request},
            "limits": {"cpu": self.cpu_limit, "memory": self.memory_limit},
        }


@dataclass
class DeploymentConfig:
    """Master configuration object for deployment generation.

    Attributes:
        app_name: Application / service name.
        image: Container image (e.g. ``myapp:latest``).
        environment: Target environment.
        port: Container listening port.
        env_vars: List of environment variable mappings.
        health_check: Health check configuration.
        resources: Resource limits.
        replicas: Number of replicas (production only).
        command: Optional container entrypoint override.
        args: Optional container args override.
        volumes: List of volume mounts (name → mount_path).
        extra: Additional framework-specific metadata.
    """

    app_name: str = "suyi-app"
    image: str = "suyi:latest"
    environment: Environment = Environment.DEVELOPMENT
    port: int = 8000
    env_vars: List[EnvVar] = field(default_factory=list)
    health_check: HealthCheck = field(default_factory=HealthCheck)
    resources: ResourceLimits = field(default_factory=ResourceLimits)
    replicas: int = 1
    command: Optional[List[str]] = None
    args: Optional[List[str]] = None
    volumes: Dict[str, str] = field(default_factory=dict)
    extra: Dict[str, Any] = field(default_factory=dict)

    # ── factories ─────────────────────────────────────────────

    @classmethod
    def for_development(
        cls,
        app_name: str = "suyi-app",
        image: str = "suyi:dev",
        port: int = 8000,
    ) -> "DeploymentConfig":
        """Create a development-mode config (1 replica, relaxed resources)."""
        return cls(
            app_name=app_name,
            image=image,
            environment=Environment.DEVELOPMENT,
            port=port,
            replicas=1,
            resources=ResourceLimits(
                cpu_request="50m",
                cpu_limit="250m",
                memory_request="64Mi",
                memory_limit="128Mi",
            ),
            env_vars=[
                EnvVar("SUYI_ENV", value="development", required=False),
                EnvVar("SUYI_LOG_LEVEL", value="DEBUG", required=False),
            ],
        )

    @classmethod
    def for_production(
        cls,
        app_name: str = "suyi-app",
        image: str = "suyi:latest",
        port: int = 8000,
        replicas: int = 3,
    ) -> "DeploymentConfig":
        """Create a production-mode config (N replicas, strict resources)."""
        return cls(
            app_name=app_name,
            image=image,
            environment=Environment.PRODUCTION,
            port=port,
            replicas=replicas,
            resources=ResourceLimits(
                cpu_request="250m",
                cpu_limit="1000m",
                memory_request="256Mi",
                memory_limit="512Mi",
            ),
            env_vars=[
                EnvVar("SUYI_ENV", value="production"),
                EnvVar("SUYI_LOG_LEVEL", value="INFO"),
                EnvVar("OPENAI_API_KEY", secret_ref="api-keys/openai", required=True),
            ],
        )

    # ── convenience ───────────────────────────────────────────

    def add_env_var(self, var: EnvVar) -> None:
        self.env_vars.append(var)

    def is_production(self) -> bool:
        return self.environment == Environment.PRODUCTION

    def is_development(self) -> bool:
        return self.environment == Environment.DEVELOPMENT

    def to_dict(self) -> Dict[str, Any]:
        return {
            "app_name": self.app_name,
            "image": self.image,
            "environment": self.environment.value,
            "port": self.port,
            "env_vars": [v.to_dict() for v in self.env_vars],
            "health_check": self.health_check.to_liveness_dict(),
            "resources": self.resources.to_dict(),
            "replicas": self.replicas,
            "command": self.command,
            "args": self.args,
            "volumes": dict(self.volumes),
            "extra": dict(self.extra),
        }
