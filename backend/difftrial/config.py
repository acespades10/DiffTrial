import os
import tomllib
from pathlib import Path

from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[2]


class Limits(BaseModel):
    attempts: int = Field(default=2, ge=1, le=2)
    run_seconds: int = Field(default=900, ge=30, le=3600)
    command_seconds: int = Field(default=300, ge=5, le=900)
    repository_mb: int = Field(default=20, ge=1, le=100)
    memory_mb: int = Field(default=512, ge=128, le=4096)
    cpus: float = Field(default=1, ge=0.25, le=4)


def data_dir() -> Path:
    path = Path(os.environ.get("DIFFTRIAL_DATA", str(ROOT / "data"))).resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


def local_codex_defaults() -> tuple[str, str]:
    endpoint, model = "", ""
    path = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))) / "config.toml"
    try:
        config = tomllib.loads(path.read_text(encoding="utf-8"))
        provider = config.get("model_providers", {}).get(config.get("model_provider", ""), {})
        if "codex" in config.get("model_provider", "").lower():
            endpoint, model = provider.get("base_url", ""), config.get("model", "")
    except (OSError, ValueError):
        pass
    return endpoint, model
