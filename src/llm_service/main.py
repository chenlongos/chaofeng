from __future__ import annotations

from fastapi import FastAPI, HTTPException

from common.config import get_section
from common.schemas import HealthResponse, LLMGenerateRequest, LLMGenerateResponse
from llm_service.providers.mock import MockLLMProvider


app = FastAPI(title="LLM Service", version="0.1.0")


def get_provider():
    """根据配置选择当前 LLM 后端，例如 mock 或未来的真实大模型。"""
    cfg = get_section("llm")
    provider = cfg.get("provider", "mock")
    if provider == "mock":
        return MockLLMProvider(cfg)
    raise RuntimeError(f"Unsupported LLM provider: {provider}")


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """返回 LLM Service 的健康状态和当前 provider 名称。"""
    return HealthResponse(service="llm_service", status="ok", detail=f"provider={get_section('llm').get('provider')}")


@app.post("/v1/generate", response_model=LLMGenerateResponse)
def generate(req: LLMGenerateRequest) -> LLMGenerateResponse:
    """接收通用问答请求，并交给当前 LLM provider 生成回答。"""
    try:
        return get_provider().generate(req)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
