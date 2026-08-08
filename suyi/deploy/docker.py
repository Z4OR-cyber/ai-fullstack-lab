"""Docker deployment configuration generator.

Produces a standard ``Dockerfile`` and ``docker-compose.yml`` from a
:class:`~.config.DeploymentConfig`.

Usage::

    from suyi.deploy import DeploymentConfig, generate_dockerfile, generate_compose

    cfg = DeploymentConfig.for_production(image="myapp:v1")
    dockerfile = generate_dockerfile(cfg)
    compose = generate_compose(cfg)

    # Or use the class
    gen = DockerConfigGenerator(cfg)
    print(gen.dockerfile())
    print(gen.compose_yaml())
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .config import DeploymentConfig, Environment


class DockerConfigGenerator:
    """Generate Dockerfile and docker-compose.yml from DeploymentConfig."""

    def __init__(self, config: DeploymentConfig) -> None:
        self.config = config

    # ── Dockerfile ────────────────────────────────────────────

    def dockerfile(self) -> str:
        """Generate a Dockerfile string."""
        lines: List[str] = []
        cfg = self.config

        # Base image
        lines.append(f"FROM python:3.12-slim")
        lines.append("")

        # Labels
        lines.append(f'LABEL app="{cfg.app_name}"')
        lines.append(f'LABEL environment="{cfg.environment.value}"')
        lines.append(f'LABEL version="{cfg.image.split(":")[-1] if ":" in cfg.image else "latest"}"')
        lines.append("")

        # Working directory
        lines.append("WORKDIR /app")
        lines.append("")

        # System deps (minimal)
        lines.append("RUN apt-get update && apt-get install -y --no-install-recommends \\")
        lines.append("    gcc g++ && rm -rf /var/lib/apt/lists/*")
        lines.append("")

        # Copy and install
        lines.append("COPY pyproject.toml .")
        lines.append("COPY suyi/ ./suyi/")
        lines.append("RUN pip install --no-cache-dir .")
        lines.append("")

        # Copy app code
        lines.append("COPY . .")
        lines.append("")

        # Environment variables
        if cfg.env_vars:
            for var in cfg.env_vars:
                if var.value is not None:
                    lines.append(f"ENV {var.name}={var.value}")
            lines.append("")

        # Port
        lines.append(f"EXPOSE {cfg.port}")
        lines.append("")

        # Health check
        hc = cfg.health_check
        lines.append(
            f"HEALTHCHECK --interval={hc.interval}s --timeout={hc.timeout}s "
            f"--retries={hc.retries} --start-period={hc.startup_delay}s \\"
        )
        lines.append(
            f"  CMD python -c \"import urllib.request; "
            f"urllib.request.urlopen('http://localhost:{hc.port}{hc.path}')\" || exit 1"
        )
        lines.append("")

        # Entrypoint
        if cfg.command:
            cmd_str = " ".join(cfg.command)
            lines.append(f'CMD ["{cmd_str}"]')
        else:
            lines.append(f'CMD ["suyi", "serve", "--port", "{cfg.port}"]')
        lines.append("")

        return "\n".join(lines)

    # ── docker-compose.yml ───────────────────────────────────

    def compose_yaml(self) -> str:
        """Generate a docker-compose.yml string."""
        cfg = self.config
        lines: List[str] = []
        lines.append("version: \"3.9\"")
        lines.append("")
        lines.append("services:")
        lines.append(f"  {cfg.app_name}:")

        # Image
        lines.append(f"    image: {cfg.image}")
        lines.append(f"    build:")
        lines.append(f"      context: .")
        lines.append(f"      dockerfile: Dockerfile")
        lines.append(f"    container_name: {cfg.app_name}")

        # Ports
        lines.append(f"    ports:")
        lines.append(f'      - "{cfg.port}:{cfg.port}"')

        # Environment
        if cfg.env_vars:
            lines.append("    environment:")
            for var in cfg.env_vars:
                if var.value is not None:
                    lines.append(f"      {var.name}: {var.value}")
                elif var.secret_ref:
                    lines.append(f'      {var.name}: ${{{var.secret_ref}}}')

        # Volumes
        if cfg.volumes:
            lines.append("    volumes:")
            for vol_name, mount_path in cfg.volumes.items():
                lines.append(f"      - {vol_name}:{mount_path}")

        # Restart policy
        if cfg.is_production():
            lines.append("    restart: always")
        else:
            lines.append("    restart: on-failure")

        # Resources
        lines.append("    deploy:")
        lines.append("      resources:")
        res = cfg.resources
        lines.append("        limits:")
        lines.append(f'          cpus: "{res.cpu_limit}"')
        lines.append(f'          memory: {res.memory_limit}')
        lines.append("        reservations:")
        lines.append(f'          cpus: "{res.cpu_request}"')
        lines.append(f'          memory: {res.memory_request}')

        # Health check
        hc = cfg.health_check
        lines.append("    healthcheck:")
        lines.append(f"      test: [\"CMD\", \"python\", \"-c\", \"import urllib.request; urllib.request.urlopen('http://localhost:{hc.port}{hc.path}')\"]")
        lines.append(f"      interval: {hc.interval}s")
        lines.append(f"      timeout: {hc.timeout}s")
        lines.append(f"      retries: {hc.retries}")
        lines.append(f"      start_period: {hc.startup_delay}s")

        # Replicas (only in swarm mode)
        if cfg.is_production() and cfg.replicas > 1:
            lines.append("    deploy:")
            lines.append(f"      replicas: {cfg.replicas}")

        # Volumes definition
        if cfg.volumes:
            lines.append("")
            lines.append("volumes:")
            for vol_name in cfg.volumes:
                lines.append(f"  {vol_name}:")

        lines.append("")
        return "\n".join(lines)

    # ── convenience ───────────────────────────────────────────

    def to_dict(self) -> Dict[str, str]:
        """Return a dict of filename → content."""
        return {
            "Dockerfile": self.dockerfile(),
            "docker-compose.yml": self.compose_yaml(),
        }


# ── module-level convenience functions ─────────────────────

def generate_dockerfile(config: DeploymentConfig) -> str:
    """Generate a Dockerfile from *config*."""
    return DockerConfigGenerator(config).dockerfile()


def generate_compose(config: DeploymentConfig) -> str:
    """Generate a docker-compose.yml from *config*."""
    return DockerConfigGenerator(config).compose_yaml()
