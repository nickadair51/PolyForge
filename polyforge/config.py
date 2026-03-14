"""Configuration loading for PolyForge.

Reads ~/.polyforge/config.toml for behavioral settings.
API keys are read exclusively from environment variables — never from config.
"""

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

import tomli_w


CONFIG_DIR = Path.home() / ".polyforge"
CONFIG_PATH = CONFIG_DIR / "config.toml"

_DEFAULT_CONFIG = {
    "execution": {
        "llm_timeout_seconds": 150,
        "docker_timeout_seconds": 120,
        "max_files": 5,
        "cost_warning_threshold": 0.50,
    },
    "docker": {
        "memory_limit": "2g",
        "cpu_cores": 2,
    },
    "llm_components": {
        "file_selection_enabled": True,
        "synthesis_enabled": True,
    },
    "workspace": {
        "base_path": str(Path.home() / ".polyforge" / "workspaces"),
        "auto_cleanup": True,
    },
}


@dataclass
class ExecutionConfig:
    llm_timeout_seconds:    int   = 150
    docker_timeout_seconds: int   = 120
    max_files:              int   = 5
    cost_warning_threshold: float = 0.50


@dataclass
class DockerConfig:
    memory_limit: str = "2g"
    cpu_cores:    int = 2


@dataclass
class LLMComponentsConfig:
    file_selection_enabled: bool = True
    synthesis_enabled:      bool = True


@dataclass
class WorkspaceConfig:
    base_path:    str  = str(Path.home() / ".polyforge" / "workspaces")
    auto_cleanup: bool = True


@dataclass
class ProjectOverride:
    """Optional per-project overrides. Only set if auto-detection fails."""
    type:         str | None = None
    test_cmd:     str | None = None
    docker_image: str | None = None


@dataclass
class PolyForgeConfig:
    execution:      ExecutionConfig      = field(default_factory=ExecutionConfig)
    docker:         DockerConfig         = field(default_factory=DockerConfig)
    llm_components: LLMComponentsConfig  = field(default_factory=LLMComponentsConfig)
    workspace:      WorkspaceConfig      = field(default_factory=WorkspaceConfig)
    project:        ProjectOverride      = field(default_factory=ProjectOverride)


def _ensure_config_exists() -> None:
    """Write default config.toml if it doesn't exist yet."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if not CONFIG_PATH.exists():
        with open(CONFIG_PATH, "wb") as f:
            tomli_w.dump(_DEFAULT_CONFIG, f)


def load_config() -> PolyForgeConfig:
    """Load config from ~/.polyforge/config.toml, creating it if absent."""
    _ensure_config_exists()
    with open(CONFIG_PATH, "rb") as f:
        raw = tomllib.load(f)

    ex = raw.get("execution", {})
    dk = raw.get("docker", {})
    lc = raw.get("llm_components", {})
    ws = raw.get("workspace", {})
    pr = raw.get("project", {})

    return PolyForgeConfig(
        execution=ExecutionConfig(
            llm_timeout_seconds=ex.get("llm_timeout_seconds", 150),
            docker_timeout_seconds=ex.get("docker_timeout_seconds", 120),
            max_files=ex.get("max_files", 5),
            cost_warning_threshold=ex.get("cost_warning_threshold", 0.50),
        ),
        docker=DockerConfig(
            memory_limit=dk.get("memory_limit", "2g"),
            cpu_cores=dk.get("cpu_cores", 2),
        ),
        llm_components=LLMComponentsConfig(
            file_selection_enabled=lc.get("file_selection_enabled", True),
            synthesis_enabled=lc.get("synthesis_enabled", True),
        ),
        workspace=WorkspaceConfig(
            base_path=ws.get("base_path", str(Path.home() / ".polyforge" / "workspaces")),
            auto_cleanup=ws.get("auto_cleanup", True),
        ),
        project=ProjectOverride(
            type=pr.get("type"),
            test_cmd=pr.get("test_cmd"),
            docker_image=pr.get("docker_image"),
        ),
    )
