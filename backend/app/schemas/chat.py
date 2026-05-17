"""
聊天相关的Pydantic数据模型
定义WebSocket消息、聊天请求/响应的数据结构
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


# ──────────────────────────────────────────────
# 消息类型枚举
# ──────────────────────────────────────────────
class MessageRole(str, Enum):
    """消息角色：用户/助手/系统"""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class MessageType(str, Enum):
    """消息内容类型：文本/语音/图片"""
    TEXT = "text"
    VOICE = "voice"
    IMAGE = "image"


class WSMessageType(str, Enum):
    """WebSocket 消息协议类型"""
    # 客户端 -> 服务端
    CHAT = "chat"               # 发送聊天消息
    VOICE = "voice"             # 发送语音消息（base64）
    PING = "ping"               # 心跳
    # 服务端 -> 客户端
    STREAM = "stream"           # 流式文本片段
    DONE = "done"               # 流式结束标记
    ERROR = "error"             # 错误信息
    STATUS = "status"           # 状态通知（如：正在思考…）
    PONG = "pong"               # 心跳响应


# ──────────────────────────────────────────────
# WebSocket 消息载荷
# ──────────────────────────────────────────────
class WSIncomingMessage(BaseModel):
    """客户端发送到服务端的WebSocket消息"""
    type: WSMessageType
    payload: dict[str, Any] = Field(default_factory=dict)
    request_id: Optional[str] = Field(
        default=None, description="请求ID，用于关联流式响应"
    )


class WSOutgoingMessage(BaseModel):
    """服务端发送到客户端的WebSocket消息"""
    type: WSMessageType
    payload: dict[str, Any] = Field(default_factory=dict)
    request_id: Optional[str] = Field(default=None)


# ──────────────────────────────────────────────
# 聊天数据模型
# ──────────────────────────────────────────────
class ChatMessage(BaseModel):
    """单条聊天消息"""
    role: MessageRole
    content: str
    message_type: MessageType = MessageType.TEXT
    timestamp: datetime = Field(default_factory=datetime.now)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChatRequest(BaseModel):
    """HTTP方式的聊天请求（备用）"""
    user_id: str
    messages: list[ChatMessage]
    subject: Optional[str] = Field(default=None, description="学科")
    stream: bool = True


class ChatResponse(BaseModel):
    """聊天响应"""
    reply: str
    agent_used: Optional[str] = Field(default=None, description="使用的Agent类型")
    intent_detected: Optional[str] = Field(default=None, description="检测到的意图")
    emotion_detected: Optional[str] = Field(default=None, description="检测到的情绪")
    confidence: float = Field(default=0.0, description="响应置信度")


class StreamChunk(BaseModel):
    """流式输出的单个片段"""
    content: str
    done: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


# ──────────────────────────────────────────────
# 会话上下文
# ──────────────────────────────────────────────
class ConversationContext(BaseModel):
    """会话上下文，包含当前对话的完整信息"""
    user_id: str
    session_id: str
    subject: Optional[str] = None
    messages: list[ChatMessage] = Field(default_factory=list)
    current_topic: Optional[str] = None
    difficulty_level: float = Field(default=0.5, ge=0.0, le=1.0)
