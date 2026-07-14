"""Session 领域服务。

协调 Session 聚合根、Conversation 创建和事件发布。
Conversation 是 Session 内部实现细节，不暴露为产品概念。
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.domain.session.models import (
    Session,
    SessionDomainError,
    create_session,
)

if TYPE_CHECKING:
    from app.infrastructure.event_bus import EventBus
    from app.domain.session.repository import SessionRepository

logger = logging.getLogger("domain.session")

# ── Session 的默认对话目录名 ──
SESSION_DIR_NAME = "🎯 学习 Session"


class SessionService:
    """Session 领域服务。

    职责:
    1. 创建 Session（含关联 Conversation）
    2. 管理 Session 生命周期（阶段转移、完成、取消）
    3. 发布领域事件
    """

    def __init__(
        self,
        repo: SessionRepository,
        event_bus: EventBus,
    ):
        self._repo = repo
        self._bus = event_bus

    # ═══════════════════════════════════════════════════════
    # Session 生命周期
    # ═══════════════════════════════════════════════════════

    async def create_session(
        self,
        user_id: str,
        title: str = "",
        focus: str = "",
        goal: str = "",
        estimated_minutes: int = 25,
        recommendation_id: str | None = None,
        mission_id: str | None = None,
    ) -> dict:
        """创建 Session。

        1. 创建 Session 实体
        2. 在 Conversation 树中创建目录 + 对话
        3. 发布 LearningSessionCreated 事件
        """
        from app.domain.conversation.tree_store import get_tree_store

        topic = focus or title or "学习"
        session_title = title or focus or "今天的学习"

        # 1. 创建 Session 实体
        session, created_event = create_session(
            learner_id=user_id,
            title=session_title,
            mission_id=mission_id,
            recommendation_id=recommendation_id,
            estimated_minutes=estimated_minutes,
        )

        # 2. 在 Conversation 中创建关联
        try:
            tree = get_tree_store()
            # 找到或创建 Session 目录
            dir_id = await self._ensure_session_dir(tree, user_id)
            # 创建对话
            conv_id = tree.mutate.create_conv(
                user_id=user_id,
                parent_id=dir_id,
                name=f"学习：{topic}",
                kind="general",
            )
            session.conversation_id = conv_id

            # 如果有目标，自动发送首条消息
            if goal:
                await self._send_initial_message(user_id, conv_id, goal, estimated_minutes)

        except Exception as e:
            logger.warning(f"Conversation 关联失败（Session 仍创建）: {e}")

        # 3. 保存 + 发布事件
        self._repo.save(session)
        await self._publish(created_event)
        logger.info(
            "SessionCreated session=%s learner=%s title=%s",
            session.id, user_id, session_title,
        )

        return {
            "session_id": session.id,
            "title": session.title,
            "stage": session.stage,
            "conversation_id": session.conversation_id,
            "estimated_minutes": session.estimated_minutes,
        }

    async def get_session(self, session_id: str) -> dict | None:
        """获取 Session 当前状态。"""
        session = self._repo.get(session_id)
        if not session:
            return None
        return self._to_dict(session)

    async def list_active_sessions(self, user_id: str) -> list[dict]:
        """获取用户当前活跃的 Session。"""
        sessions = self._repo.list_active_by_learner(user_id)
        return [self._to_dict(s) for s in sessions]

    async def list_recent_sessions(self, user_id: str, limit: int = 10) -> list[dict]:
        """获取用户最近的 Session。"""
        sessions = self._repo.list_by_learner(user_id, limit)
        return [self._to_dict(s) for s in sessions]

    async def transition_stage(
        self,
        session_id: str,
        new_stage: str,
    ) -> dict:
        """Session 阶段转移。"""
        session = self._repo.get(session_id)
        if not session:
            raise SessionDomainError(f"Session not found: {session_id}")

        event_data = session.transition_stage(new_stage)
        self._repo.save(session)
        await self._publish(event_data)
        logger.info(
            "SessionStageChanged session=%s stage=%s→%s",
            session_id, event_data["old_stage"], new_stage,
        )
        return {
            "session_id": session_id,
            "stage": new_stage,
            "previous_stage": event_data["old_stage"],
        }

    async def set_mission(
        self,
        session_id: str,
        title: str,
        estimated_minutes: int,
        steps: list[dict],
    ) -> dict:
        """设置 Session 任务分解。"""
        session = self._repo.get(session_id)
        if not session:
            raise SessionDomainError(f"Session not found: {session_id}")

        event_data = session.set_mission(title, estimated_minutes, steps)
        self._repo.save(session)
        await self._publish(event_data)

        return {
            "session_id": session_id,
            "mission": {
                "title": title,
                "estimated_minutes": estimated_minutes,
                "steps": [
                    {"order": s.order, "description": s.description,
                     "type": s.step_type, "status": s.status}
                    for s in (session.mission.steps if session.mission else [])
                ],
            },
        }

    async def complete_session(
        self,
        session_id: str,
        reflection: dict | None = None,
    ) -> dict:
        """完成 Session。

        1. 标记 Session 完成
        2. 发布 LearningSessionCompleted 事件
        3. Growth Engine 监听此事件后将生成 GrowthSummary
        """
        session = self._repo.get(session_id)
        if not session:
            raise SessionDomainError(f"Session not found: {session_id}")

        event_data = session.complete(reflection)
        self._repo.save(session)

        # 输出完成事件（Growth Engine 将监听）
        await self._publish(event_data)

        # 如果有反思内容，输出额外的反思事件
        if reflection:
            reflection_event = {
                "event_type": "ReflectionGenerated",
                "session_id": session_id,
                "learner_id": session.learner_id,
                "content": reflection.get("content", ""),
                "key_takeaways": reflection.get("key_takeaways", []),
                "next_steps": reflection.get("next_steps", []),
            }
            await self._publish(reflection_event)

        logger.info("SessionCompleted session=%s learner=%s", session_id, session.learner_id)

        return self._to_dict(session)

    async def cancel_session(self, session_id: str) -> dict:
        """取消 Session。"""
        session = self._repo.get(session_id)
        if not session:
            raise SessionDomainError(f"Session not found: {session_id}")

        event_data = session.cancel()
        self._repo.save(session)
        await self._publish(event_data)

        return self._to_dict(session)

    # ═══════════════════════════════════════════════════════
    # 内部辅助
    # ═══════════════════════════════════════════════════════

    async def _ensure_session_dir(self, tree, user_id: str) -> str:
        """查找或创建 Session 目录。

        根目录是 parent_id 为 None 的 dir 节点（TreeDirectory 内部约定），
        不是 id="root" 的硬编码节点。
        """
        from app.services.common import get_data_repo
        data = get_data_repo().load(user_id)
        root = next(
            (dn for dn in data.directory_nodes.values()
             if dn.node_type == "dir" and dn.parent_id is None),
            None,
        )
        if root is None:
            # 懒创建根目录（与 TreeDirectory._ensure_root 行为一致）
            from app.schemas.directory_node import DirectoryNode
            root = DirectoryNode(
                user_id=user_id,
                parent_id=None,
                node_type="dir",
                kind="general",
                name="我的知识库",
            )
            data.directory_nodes[root.id] = root
            get_data_repo().save(user_id, data)

        children = tree.query.list_children(user_id, root.id)
        for child in children:
            if child.name == SESSION_DIR_NAME:
                return child.id

        # 创建新目录
        return tree.mutate.create_dir(
            user_id=user_id,
            parent_id=root.id,
            name=SESSION_DIR_NAME,
            kind="general",
        )

    async def _send_initial_message(
        self, user_id: str, conv_id: str, goal: str, estimated_minutes: int,
    ):
        """（简化版）发送首条上下文消息，将 Today 的目标传递到 Session。"""
        # 记录初始消息（通过 tree store add_message）
        from app.domain.conversation.tree_store import get_tree_store
        try:
            tree = get_tree_store()
            # 添加系统消息记录目标
            tree.mutate.add_message(
                user_id=user_id,
                conv_id=conv_id,
                role="system",
                text=f"Today's goal: {goal} (est. {estimated_minutes}min)",
            )
        except Exception as e:
            logger.warning(f"Failed to add initial message: {e}")

    # ═══════════════════════════════════════════════════════
    # 事件 + 序列化
    # ═══════════════════════════════════════════════════════

    async def _publish(self, event_data: dict):
        """根据 event_data['event_type'] 发布对应事件。"""
        event_type = event_data.pop("event_type", "")

        if event_type == "LearningSessionCreated":
            from shared.events import LearningSessionCreated
            event = LearningSessionCreated(**event_data)
        elif event_type == "LearningSessionStageChanged":
            from shared.events import LearningSessionStageChanged
            event = LearningSessionStageChanged(**event_data)
        elif event_type == "LearningSessionCompleted":
            from shared.events import LearningSessionCompleted
            event = LearningSessionCompleted(**event_data)
        elif event_type == "LearningSessionCancelled":
            from shared.events import LearningSessionCancelled
            event = LearningSessionCancelled(**event_data)
        elif event_type == "ReflectionGenerated":
            from shared.events import ReflectionGenerated
            event = ReflectionGenerated(**event_data)
        elif event_type == "LearningSessionMissionUpdated":
            from shared.events import LearningSessionMissionUpdated
            event = LearningSessionMissionUpdated(**event_data)
        else:
            logger.warning(f"Unknown event type: {event_type}")
            return

        await self._bus.publish(event)

    @staticmethod
    def _to_dict(session: Session) -> dict:
        """Session → API 响应 dict。"""
        data = {
            "id": session.id,
            "learner_id": session.learner_id,
            "title": session.title,
            "stage": session.stage,
            "status": session.status,
            "estimated_minutes": session.estimated_minutes,
            "started_at": session.started_at,
            "finished_at": session.finished_at,
            "conversation_id": session.conversation_id,
            "mission_id": session.mission_id,
            "recommendation_id": session.recommendation_id,
        }
        if session.mission:
            data["mission"] = {
                "title": session.mission.title,
                "estimated_minutes": session.mission.estimated_minutes,
                "steps": [
                    {
                        "order": s.order,
                        "description": s.description,
                        "type": s.step_type,
                        "status": s.status,
                    }
                    for s in session.mission.steps
                ],
            }
        if session.reflection_text:
            data["reflection"] = {
                "content": session.reflection_text,
                "key_takeaways": session.reflection_takeaways,
                "next_steps": session.reflection_next_steps,
            }
        return data
