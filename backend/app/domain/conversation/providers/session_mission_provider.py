"""LI-04 Session Mission Provider — 为对话注入当前 Session 的 Mission 上下文。

职责:
  让 💬 对话知道用户当前在学什么。

注入内容:
  - Mission 标题 + 结构化分析 (concepts, dependencies, objectives, difficulty_spots)
  - 用户当前阶段 (stage)
  - 学习目标 (learning objectives)
  - 引导原则: 不直接给答案，用提问帮用户自己发现

原则:
  P2 — 理解先于干预（没有 Mission Context 就不生成对话上下文）
  P4 — 隔离能力（只注入 mission 上下文，不碰其他模块）
  P6 — 沉默是一种能力（没有活跃 Session 时不注入）
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

from app.domain.conversation.context_pipeline import (
    ContextInput,
    ContextOutput,
    SystemChunk,
)
from app.domain.session.repository import get_session_repo

logger = logging.getLogger(__name__)


class SessionMissionProvider:
    """注入当前 Session 的 Mission 上下文到对话管线。

    在 Context Pipeline 中作为 Provider 运行。
    没有活跃 Session 时返回 None（不产生额外上下文）。
    """

    def __init__(self, session_repo=None):
        self._session_repo = session_repo

    def _ensure_deps(self):
        if self._session_repo is None:
            self._session_repo = get_session_repo()

    async def build(self, input: ContextInput) -> ContextOutput | None:
        """构建 Mission 上下文。

        Args:
            input: ContextInput (user_id, dir_id, user_text, conv_id, ...)

        Returns:
            SystemChunk 包含 Mission 上下文，或 None（无活跃 Session）
        """
        self._ensure_deps()

        # 1. 查找用户的活跃 Session
        try:
            sessions = self._session_repo.list_active_by_learner(input.user_id)
        except Exception:
            logger.debug("SessionMissionProvider: no active sessions for %s", input.user_id)
            return None

        if not sessions:
            return None

        session = sessions[0]  # 取最近的活跃 Session
        title = session.title or ""
        if session.mission and session.mission.title:
            title = session.mission.title

        if not title:
            return None

        # 2. 构建 Mission 上下文文本
        parts = [f"## 当前学习任务\n主题：{title}"]

        # 注入 MissionAnalysis（如果已有）
        if session.mission_analysis:
            try:
                ma = session.mission_analysis
                parts.append(f"\n### 核心概念")
                concepts = ma.get("concepts", [])
                for c in concepts:
                    parts.append(f"- {c.get('name', '')}（{c.get('importance', 'medium')}）: {c.get('description', '')}")

                objectives = ma.get("learning_objectives", [])
                if objectives:
                    parts.append(f"\n### 学习目标")
                    for obj in objectives:
                        parts.append(f"- {obj}")

                difficulty_spots = ma.get("difficulty_spots", [])
                if difficulty_spots:
                    parts.append(f"\n### 学习难点")
                    for d in difficulty_spots:
                        parts.append(f"- {d.get('point', '')}（难度 {d.get('difficulty_level', 3)}）")
                        if d.get("common_misconception"):
                            parts.append(f"  · 常见误区：{d['common_misconception']}")
            except Exception:
                logger.debug("SessionMissionProvider: failed to parse mission_analysis", exc_info=True)

        # 3. 注入当前阶段
        parts.append(f"\n### 当前阶段\n{session.stage}")

        # 4. 注入引导原则
        parts.append("""
### 对话原则
- 用户正在独立完成学习任务，你的角色是引导思考，不是提供答案
- 当用户提出与当前 Mission 相关的问题时，优先用提问帮用户自己发现
- 不要替用户总结、不要替用户做练习
- 每次只回应一个方向，不要一次性给出多个提示""")

        # 5. 返回 SystemChunk
        return SystemChunk(text="\n".join(parts))
