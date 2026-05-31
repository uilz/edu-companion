"""
应用配置模块
使用 pydantic-settings 从 config.yaml 和 .env 文件加载配置
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

import os

# 项目根目录
BASE_DIR = Path(__file__).resolve().parent.parent

# 全局数据根目录（可通过环境变量 COMPANION_HOME 覆盖）
COMPANION_HOME = Path(os.environ.get("COMPANION_HOME", "~/.companion")).expanduser()


def _load_yaml_config() -> dict[str, Any]:
    """从 config.yaml 加载配置"""
    yaml_path = BASE_DIR / "config.yaml"
    if yaml_path.exists():
        with open(yaml_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}


class Settings(BaseSettings):
    """
    应用全局配置
    优先级：环境变量 > .env 文件 > config.yaml > 默认值
    """

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        extra="ignore",
    )

    # ── 应用基础配置 ──
    app_name: str = Field(default="智能学习伴侣", description="应用名称")
    app_version: str = Field(default="0.1.0", description="版本号")
    debug: bool = Field(default=False, description="调试模式")
    host: str = Field(default="0.0.0.0", description="服务监听地址")
    port: int = Field(default=8000, description="服务端口")

    # ── CORS 配置 ──
    cors_origins: list[str] = Field(
        default=["*"], description="允许的跨域来源"
    )

    # ── LLM 模型配置（OpenAI 兼容格式） ──
    # 文本模型 — 通用对话/讲解
    text_model: str = Field(
        default="openai/gpt-4o-mini",
        description="文本模型 — 通用对话与讲解（env: TEXT_MODEL）",
    )
    # 文本推理模型 — 复杂题讲解/错题分析/学习规划
    text_reasoning_model: str = Field(
        default="openai/gpt-4o",
        description="推理模型 — 复杂问题分析（env: TEXT_REASONING_MODEL）",
    )
    # 文本轻量模型 — 意图识别/情绪分析/分类
    text_fast_model: str = Field(
        default="openai/gpt-4o-mini",
        description="轻量模型 — 意图分类/情绪识别（env: TEXT_FAST_MODEL）",
    )

    # ── 语音识别模型 ──
    whisper_model: str = Field(
        default="whisper-1",
        description="Whisper 语音识别模型（env: WHISPER_MODEL）",
    )

    # OpenAI 兼容 API 配置（唯一 API 格式）
    openai_api_key: str | None = Field(default=None, description="OpenAI API Key（env: OPENAI_API_KEY）")
    openai_api_base: str | None = Field(
        default=None,
        description="OpenAI 兼容 API 端点（env: OPENAI_API_BASE）",
    )

    # ── LiteLLM 代理配置 ──
    litellm_model_list: list[dict[str, Any]] = Field(
        default_factory=list,
        description="LiteLLM模型列表配置",
    )

    # ── 会话管理 ──
    max_history_messages: int = Field(
        default=20, description="保留的最大历史消息数"
    )
    session_timeout_minutes: int = Field(
        default=60, description="会话超时时间（分钟）"
    )

    # ── 内容库（MVP 使用内存） ──
    content_store_type: str = Field(
        default="memory", description="内容存储类型: memory / db"
    )

    def load_from_yaml(self) -> "Settings":
        """从 config.yaml 加载并覆盖默认值（跳过 null 值，不覆盖 env 配置）"""
        yaml_data = _load_yaml_config()
        for key, value in yaml_data.items():
            if hasattr(self, key) and value is not None:
                setattr(self, key, value)
        return self


# ── 全局设置实例 ──
settings = Settings().load_from_yaml()
