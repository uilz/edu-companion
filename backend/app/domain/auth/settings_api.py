"""
用户设置 API — LLM 自定义配置 + 统一偏好 (Task #84)

路由前缀: /api/settings

端点:
  - /api/settings/llm           GET/PUT/DELETE  LLM 自定义配置 (api_base / api_key / model_name)
  - /api/settings/llm-behavior  GET/PUT         LLM 行为参数 (temperature / max_tokens / system_prompt)
  - /api/settings/ui            GET/PUT         UI 偏好 (theme / style)
  - /api/settings/learning      GET/PUT         学习偏好 (socratic / auto_scroll)
  - /api/settings/view/{pid}    GET/PUT         项目详情页视图偏好 (Task #89: per-user × per-project)
  - /api/settings/all           GET             全部偏好 (D16 JSONB)

设计:
  - 所有偏好统一写到 user_settings (D16 JSONB 表)
  - 写入时发布 UserPreferencesUpdated 事件 (Task #84)
  - 旧 API 完全保留 (向后兼容)
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, field_validator

from app.domain.auth.user_llm_repo import get_user_llm_config_repo
from app.infrastructure.db.user_settings_repo import get_user_settings_repo

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


class LlmBehaviorRequest(BaseModel):
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, ge=64, le=8192)
    system_prompt: str | None = Field(default=None, max_length=4000)


class LlmBehaviorResponse(BaseModel):
    temperature: float = 0.7
    max_tokens: int = 2048
    system_prompt: str = ""


class UiPrefsRequest(BaseModel):
    theme: str | None = Field(default=None, description="dark / light")
    style: str | None = Field(default=None, description="professional / playful / knowledge / soft-data / gamified")
    serif_font: bool | None = Field(default=None, description="AI 消息使用衬线字体")

    @field_validator("theme")
    @classmethod
    def _validate_theme(cls, v: str | None) -> str | None:
        if v is not None and v not in ("dark", "light"):
            raise ValueError(f"theme 必须是 dark 或 light, 当前: {v}")
        return v

    @field_validator("style")
    @classmethod
    def _validate_style(cls, v: str | None) -> str | None:
        valid = ("professional", "playful", "knowledge", "soft-data", "gamified")
        if v is not None and v not in valid:
            raise ValueError(f"style 必须是 {valid} 之一, 当前: {v}")
        return v


class UiPrefsResponse(BaseModel):
    theme: str = "dark"
    style: str = "professional"
    serif_font: bool = False


class LearningPrefsRequest(BaseModel):
    socratic_mode: bool | None = None
    socratic_follow_up_mode: bool | None = None
    auto_scroll_on_load: bool | None = None


class LearningPrefsResponse(BaseModel):
    socratic_mode: bool = False
    socratic_follow_up_mode: bool = False
    auto_scroll_on_load: bool = True


def _mask_api_key(key: str) -> str:
    """脱敏 API Key：只显示前8位和后4位"""
    if not key:
        return ""
    if len(key) <= 12:
        return key[:4] + "****" + key[-4:] if len(key) > 8 else key
    return key[:8] + "****" + key[-4:]


def _require_user(request: Request) -> dict:
    """从请求状态获取当前用户，未登录则抛 401"""
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="未登录")
    return user


def _publish_prefs_event(user_id: str, changed_keys: list[str], source: str = "api") -> None:
    """统一发布 UserPreferencesUpdated 事件 (Task #84)."""
    try:
        from app.infrastructure.event_bus_utils import publish_event_safe
        from shared.events import UserPreferencesUpdated
        publish_event_safe(UserPreferencesUpdated(
            user_id=user_id,
            changed_keys=changed_keys,
            source=source,
        ))
    except Exception as e:
        logger.debug("UserPreferencesUpdated 事件发布失败: %s", e)


# ═══════════════════════════════════════════
# LLM 自定义配置 (api_base / api_key / model_name)
# ═══════════════════════════════════════════


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
    """保存当前用户的 LLM 自定义配置（API Key 加密存储）

    同步发布 UserPreferencesUpdated 事件 (Task #84).
    """
    user = _require_user(request)
    repo = get_user_llm_config_repo()
    repo.save(
        user_id=user["user_id"],
        api_base=body.api_base.strip(),
        api_key=body.api_key.strip(),
        model_name=body.model_name.strip(),
    )
    _publish_prefs_event(user["user_id"], changed_keys=["llm_config"])
    return {"ok": True, "message": "LLM 配置已保存"}


@router.delete("/llm", summary="重置用户 LLM 配置为默认")
async def reset_llm_config(request: Request):
    """删除当前用户的 LLM 自定义配置，恢复为系统默认"""
    user = _require_user(request)
    repo = get_user_llm_config_repo()
    repo.delete(user["user_id"])
    _publish_prefs_event(user["user_id"], changed_keys=["llm_config"], source="reset")
    return {"ok": True, "message": "已恢复为系统默认配置"}


# ═══════════════════════════════════════════
# LLM 行为参数 (temperature / max_tokens / system_prompt)
# Task #84: 从 localStorage 迁移到 user_settings JSONB
# ═══════════════════════════════════════════


@router.get("/llm-behavior", response_model=LlmBehaviorResponse, summary="获取 LLM 行为参数")
async def get_llm_behavior(request: Request):
    """获取 LLM 行为参数 (温度 / 最大回复长度 / 系统提示词)"""
    user = _require_user(request)
    repo = get_user_settings_repo()
    data = repo.get_llm_behavior(user["user_id"])
    return LlmBehaviorResponse(**data)


@router.put("/llm-behavior", response_model=LlmBehaviorResponse, summary="保存 LLM 行为参数")
async def save_llm_behavior(body: LlmBehaviorRequest, request: Request):
    """保存 LLM 行为参数 (Task #84: 跨设备一致)"""
    user = _require_user(request)
    repo = get_user_settings_repo()
    payload = {k: v for k, v in body.model_dump(exclude_unset=True).items() if v is not None}
    saved = repo.set_llm_behavior(user["user_id"], payload)
    _publish_prefs_event(user["user_id"], changed_keys=["llm_behavior"])
    return LlmBehaviorResponse(**saved)


# ═══════════════════════════════════════════
# UI 偏好 (theme / style)
# Task #84: 从 localStorage 迁移到 user_settings JSONB
# ═══════════════════════════════════════════


@router.get("/ui", response_model=UiPrefsResponse, summary="获取 UI 偏好")
async def get_ui_prefs(request: Request):
    """获取 UI 偏好 (主题 / 设计风格) — Task #84: 跨设备一致"""
    user = _require_user(request)
    repo = get_user_settings_repo()
    data = repo.get_ui_prefs(user["user_id"])
    return UiPrefsResponse(**data)


@router.put("/ui", response_model=UiPrefsResponse, summary="保存 UI 偏好")
async def save_ui_prefs(body: UiPrefsRequest, request: Request):
    """保存 UI 偏好 (主题 / 设计风格) — Task #84: 跨设备一致"""
    user = _require_user(request)
    repo = get_user_settings_repo()
    payload = {k: v for k, v in body.model_dump(exclude_unset=True).items() if v is not None}
    saved = repo.set_ui_prefs(user["user_id"], payload)
    _publish_prefs_event(user["user_id"], changed_keys=["ui"])
    return UiPrefsResponse(**saved)


# ═══════════════════════════════════════════
# 学习偏好 (socratic / auto_scroll)
# Task #84: 从 localStorage 迁移到 user_settings JSONB
# ═══════════════════════════════════════════


@router.get("/learning", response_model=LearningPrefsResponse, summary="获取学习偏好")
async def get_learning_prefs(request: Request):
    """获取学习偏好 (苏格拉底/追问/自动滚动) — Task #84: 跨设备一致"""
    user = _require_user(request)
    repo = get_user_settings_repo()
    data = repo.get_learning_prefs(user["user_id"])
    return LearningPrefsResponse(**data)


@router.put("/learning", response_model=LearningPrefsResponse, summary="保存学习偏好")
async def save_learning_prefs(body: LearningPrefsRequest, request: Request):
    """保存学习偏好 (苏格拉底/追问/自动滚动) — Task #84: 跨设备一致"""
    user = _require_user(request)
    repo = get_user_settings_repo()
    payload = {k: v for k, v in body.model_dump(exclude_unset=True).items() if v is not None}
    saved = repo.set_learning_prefs(user["user_id"], payload)
    _publish_prefs_event(user["user_id"], changed_keys=["learning"])
    return LearningPrefsResponse(**saved)


# ═══════════════════════════════════════════
# 全部偏好 (D16 兼容)
# ═══════════════════════════════════════════


@router.get("/all", summary="获取用户全部偏好 (D16 JSONB)")
async def get_all_preferences(request: Request):
    """获取用户全部偏好 (D16 JSONB 兼容接口)"""
    user = _require_user(request)
    repo = get_user_settings_repo()
    return {"ok": True, "settings": repo.get_all(user["user_id"])}


# ════════════════════════════════════════════
# 项目视图偏好 (Task #89: per-user × per-project)
# ════════════════════════════════════════════


class ProjectViewPrefRequest(BaseModel):
    view: str = Field(
        ...,
        description="document | outline | kanban | knowledge | activity",
    )

    @field_validator("view")
    @classmethod
    def _validate_view(cls, v: str) -> str:
        valid = ("document", "outline", "kanban", "knowledge", "activity")
        if v not in valid:
            raise ValueError(f"view 必须是 {valid} 之一, 当前: {v}")
        return v


class ProjectViewPrefResponse(BaseModel):
    project_id: str
    view: str


@router.get(
    "/view/{project_id}",
    response_model=ProjectViewPrefResponse,
    summary="获取项目详情页视图偏好 (Task #89)",
)
async def get_view_pref(project_id: str, request: Request):
    """读取当前用户在指定项目详情页的视图偏好。

    跨设备一致：存储在 user_settings JSONB。
    若未设置则返回默认值 "document" (手稿视图)。
    """
    user = _require_user(request)
    repo = get_user_settings_repo()
    view = repo.get_view_pref(user["user_id"], project_id, default="document")
    return ProjectViewPrefResponse(project_id=project_id, view=view)


@router.put(
    "/view/{project_id}",
    response_model=ProjectViewPrefResponse,
    summary="保存项目详情页视图偏好 (Task #89)",
)
async def set_view_pref(
    project_id: str,
    body: ProjectViewPrefRequest,
    request: Request,
):
    """保存当前用户在指定项目详情页的视图偏好。

    写入后立即可用于下次访问；同步发布 UserPreferencesUpdated 事件 (Task #84)。
    """
    user = _require_user(request)
    repo = get_user_settings_repo()
    try:
        saved = repo.set_view_pref(user["user_id"], project_id, body.view)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    _publish_prefs_event(user["user_id"], changed_keys=[f"view.{project_id}"])
    return ProjectViewPrefResponse(project_id=project_id, view=saved)