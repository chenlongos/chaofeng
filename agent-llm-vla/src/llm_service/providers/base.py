from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from common.schemas import LLMGenerateRequest, LLMGenerateResponse


class LLMProvider(ABC):
    """定义所有 LLM 后端都必须实现的统一生成接口。"""

    name: str

    def __init__(self, cfg: dict[str, Any]) -> None:
        """保存 LLM 服务配置，供具体 provider 读取模型名或密钥等信息。"""
        self.cfg = cfg

    @abstractmethod
    def generate(self, req: LLMGenerateRequest) -> LLMGenerateResponse:
        """根据用户请求生成文本回答，并返回标准化结果。"""
        raise NotImplementedError
