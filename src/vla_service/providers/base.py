from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from common.schemas import VLAExecuteRequest, VLAExecuteResponse


class VLAProvider(ABC):
    """定义所有 VLA 后端都必须实现的统一执行接口。"""

    name: str

    def __init__(self, cfg: dict[str, Any]) -> None:
        """保存 VLA 服务配置，供具体 provider 构造命令或连接后端使用。"""
        self.cfg = cfg

    @abstractmethod
    def execute(self, req: VLAExecuteRequest) -> VLAExecuteResponse:
        """执行一个 VLA 技能请求，并返回标准化执行结果。"""
        raise NotImplementedError
