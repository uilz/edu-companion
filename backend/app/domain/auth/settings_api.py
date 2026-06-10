"""
用户设置 API — LLM 自定义配置

路由前缀: /api/settings
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.domain.auth.user_llm_repo import get_user_llm_config_repo

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/settings", tags=["用户设置"])


# ── 请求/响应模型 ──

class LlmConfigRequest(BaseModel):
    api_base: str = Field(default="", max_length=512, description="OpenAI 兼容 API 端点")
    api_key: str = Field(default="", max_length=512, description="API Key（服务端加密存储）")
    model_name: str = Field(default="", max_length=128, description="模型名称，如 gpt-4o")


class LlmConfigResponse(BaseModel):
    api_base: str = ""
    api_key: str = ""  # 返回时脱敏
    model_name: str = ""
    has_custom_config: bool = False


def _mask_api_key(key: str) -> str:
    """脱敏 API Key：只显示前8位和后4位"""
    if len(key) <= 12:
        return key[:4] + "****" + key[-4:] if len(key) > 8 else key
    return key[:8] + "****" + key[-4:]


def _require_user(request: Request) -> dict:
    """从请求状态获取当前用户，未登录则抛 401"""
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="未登录")
    return user


@router.get("/llm", summary="获取用户自定义 LLM 配置")
async def get_llm_config(request: Request):
    """获取当前用户的 LLM 自定义配置（API Key 脱敏返回）"""
    user = _require_user(request)
    repo = get_user_llm_config_repo()
    config = repo.get(user["user_id"])

    if config and config.get("model_name"):
        return LlmConfigResponse(
            api_base=config.get("api_base", ""),
            api_key=_mask_api_key(config.get("api_key", "")),
            model_name=config.get("model_name", ""),
            has_custom_config=True,
        )
    return LlmConfigResponse(has_custom_config=False)


@router.put("/llm", summary="保存用户自定义 LLM 配置")
async def save_llm_config(body: LlmConfigRequest, request: Request):
    """保存当前用户的 LLM 自定义配置（API Key 加密存储）"""
    user = _require_user(request)
    repo = get_user_llm_config_repo()
    repo.save(
        user_id=user["user_id"],
        api_base=body.api_base.strip(),
        api_key=body.api_key.strip(),
        model_name=body.model_name.strip(),
    )
    return {"ok": True, "message": "LLM 配置已保存"}


@router.delete("/llm", summary="重置用户 LLM 配置为默认")
async def reset_llm_config(request: Request):
    """删除当前用户的 LLM 自定义配置，恢复为系统默认"""
    user = _require_user(request)
    repo = get_user_llm_config_repo()
    repo.delete(user["user_id"])
    return {"ok": True, "message": "已恢复为系统默认配置"}