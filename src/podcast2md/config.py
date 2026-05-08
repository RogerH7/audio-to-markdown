from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Mapping

import yaml


ENV_PATTERN = re.compile(r"^\$\{([A-Z0-9_]+)\}$")


def load_dotenv(path: str | Path = ".env") -> None:
    dotenv_path = Path(path)
    if not dotenv_path.exists():
        return

    for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue
        if (value.startswith('"') and value.endswith('"')) or (
            value.startswith("'") and value.endswith("'")
        ):
            value = value[1:-1]
        os.environ.setdefault(key, value)


def _expand_env(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _expand_env(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_expand_env(v) for v in value]
    if isinstance(value, str):
        match = ENV_PATTERN.match(value)
        if match:
            return os.getenv(match.group(1), "")
    return value


def load_config(path: str | Path = "config/config.yaml") -> dict[str, Any]:
    load_dotenv()
    config_path = Path(path)
    if not config_path.exists():
        example = Path("config/config.example.yaml")
        raise FileNotFoundError(
            f"Config file not found: {config_path}. Copy {example} to {config_path} first."
        )

    with config_path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return _expand_env(data)


def ensure_paths(config: Mapping[str, Any]) -> None:
    paths = config.get("paths", {})
    for key in ["data_dir", "audio_dir", "asr_json_dir", "output_dir", "log_dir"]:
        value = paths.get(key)
        if value:
            Path(value).mkdir(parents=True, exist_ok=True)
