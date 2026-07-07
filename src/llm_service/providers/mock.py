from __future__ import annotations

from common.schemas import LLMGenerateRequest, LLMGenerateResponse
from llm_service.providers.base import LLMProvider


class MockLLMProvider(LLMProvider):
    """提供不调用真实大模型的 LLM 假实现，方便接口联调。"""

    name = "mock"

    def generate(self, req: LLMGenerateRequest) -> LLMGenerateResponse:
        """模拟生成回答，对部分示例问题返回固定答案。"""
        text = req.user_text.strip()
        if "北京" in text and "景点" in text:
            answer = "北京常见旅游景点包括故宫、天安门广场、颐和园、长城、天坛、北海公园、什刹海和国家博物馆。"
        else:
            answer = f"[MOCK LLM] 我收到了你的问题：{text}"
        return LLMGenerateResponse(
            ok=True,
            provider=self.name,
            model=self.cfg.get("model", "mock"),
            answer=answer,
        )
