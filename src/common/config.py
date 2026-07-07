from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml


DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[2] / "configs" / "app.yaml"


def _expand_config_value(value: Any) -> Any:
    """递归展开配置里的环境变量和用户目录，例如 ${LEROBOT_HOME} 或 ~/repo。"""
    if isinstance(value, str):
        return os.path.expanduser(os.path.expandvars(value))
    if isinstance(value, list):
        return [_expand_config_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _expand_config_value(item) for key, item in value.items()}
    return value


@lru_cache(maxsize=1)
def load_config() -> dict[str, Any]:
    """读取并缓存全局 YAML 配置，供 Agent、VLA、LLM 三个服务共享。"""
    os.environ.setdefault("LEROBOT_HOME", str(Path.home() / "lerobot"))
    path = Path(os.getenv("AGENT_VLA_CONFIG", DEFAULT_CONFIG_PATH))
    with path.open("r", encoding="utf-8") as f:
        return _expand_config_value(yaml.safe_load(f))


def get_section(name: str) -> dict[str, Any]:
    """从全局配置中取出指定顶层配置段，例如 agent、vla 或 llm。"""
    return load_config().get(name, {})
