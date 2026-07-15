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
        source: str = "",
    ) -> dict:
        """创建 Session。

        1. 创建 Session 实体
        2. 基于 Learner Model 生成默认 Mission
        3. 在 Conversation 树中创建目录 + 对话
        4. 保存并发布 LearningSessionCreated 事件
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

        # 2. 基于 Learner Model 生成默认 Mission（S2.2 / S3.2）
        try:
            mission_title, mission_minutes, mission_steps = (
                self._build_mission_from_learner_model(
                    user_id=user_id,
                    topic=topic,
                    estimated_minutes=estimated_minutes,
                    source=source,
                )
            )
            session.set_mission(mission_title, mission_minutes, mission_steps)
        except Exception as e:
            logger.warning("基于 Learner Model 生成 Mission 失败，使用默认空 Mission: %s", e)

        # 3. 在 Conversation 中创建关联
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

        # 4. 保存 + 发布事件
        self._repo.save(session)
        await self._publish(created_event)
        logger.info(
            "SessionCreated session=%s learner=%s title=%s",
            session.id, user_id, session_title,
        )

        result = {
            "session_id": session.id,
            "title": session.title,
            "stage": session.stage,
            "conversation_id": session.conversation_id,
            "estimated_minutes": session.estimated_minutes,
        }
        if session.mission:
            result["mission"] = {
                "title": session.mission.title,
                "estimated_minutes": session.mission.estimated_minutes,
                "steps": [
                    {"order": s.order, "description": s.description,
                     "type": s.step_type, "status": s.status}
                    for s in session.mission.steps
                ],
            }
        return result

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

    def _build_mission_from_learner_model(
        self,
        user_id: str,
        topic: str,
        estimated_minutes: int,
        source: str = "",
    ) -> tuple[str, int, list[dict]]:
        """基于 Learner Model 生成 Session 默认 Mission（S2.2 / S3.2）。

        策略：
        - 优先使用用户传入的 topic 作为 Mission 主题
        - 读取 LearnerProfile 的 subjects / learning_style 做个性化微调
        - 读取 ProgressSummary 的 struggling_skills，若 topic 与某个困难知识点
          相关，则增加 review 步骤的比重
        - 默认三步：explain → practice → review
        - S3.2: source="welcome_back" 时，读取上次 GrowthRecord 的
          key_takeaways / reflection，用"我们聊到了"体现成长连续
        """
        from shared.learner_model import get_learner_model

        engine = get_learner_model()
        profile = engine.get_or_create_profile(user_id)
        progress = engine.get_progress_summary(user_id)

        # 主题：用户传入 topic 优先；若为空则使用 learner 的学科或默认主题
        mission_topic = topic or (
            profile.subjects[0] if profile.subjects else "今天的学习"
        )
        subject = (profile.subjects[0] if profile.subjects else "学习") or "学习"

        # 判断是否命中困难知识点
        struggling = [s for s in (progress.struggling_skills or []) if s]
        is_struggling = any(mission_topic in s or s in mission_topic for s in struggling)

        # 根据 learning_style 微调步骤文案（CPO Note: 内部概念，不暴露为用户标签）
        style = profile.learning_style or "reading"
        style_hint = {
            "visual": "看图/示例",
            "auditory": "听讲解",
            "reading": "阅读关键概念",
            "kinesthetic": "动手尝试",
        }.get(style, "阅读关键概念")

        # ── S3.2: 从上次 GrowthRecord 提取成长上下文 ──
        last_takeaway = ""
        last_reflection = ""
        if source == "welcome_back":
            try:
                from app.domain.growth.repository import GrowthRepository

                repo = GrowthRepository()
                latest_record = repo.get_latest(user_id)
                if latest_record:
                    last_takeaway = (
                        latest_record.key_takeaways[0]
                        if latest_record.key_takeaways else ""
                    )
                    last_reflection = latest_record.reflection_snippet or ""
            except Exception as e:
                logger.warning("S3.2 读取上次 GrowthRecord 失败: %s", e)

        # ── 构建 Mission 步骤 ──
        title = f"{subject}：{mission_topic}"

        # S3.2: explain 步骤引用上次学习（成长方式连续）
        if source == "welcome_back" and last_takeaway:
            step1_desc = (
                f"上次我们聊到了「{mission_topic}」，发现了 {last_takeaway}。"
                f"今天从这里继续。"
            )
        elif source == "welcome_back" and mission_topic != "今天的学习":
            step1_desc = f"上次我们聊到了「{mission_topic}」。今天从这里继续。"
        else:
            step1_desc = f"先{style_hint}，理解「{mission_topic}」的核心"

        steps: list[dict] = [
            {
                "order": 1,
                "description": step1_desc,
                "type": "explain",
            },
            {
                "order": 2,
                "description": f"做一道小题，检验对「{mission_topic}」的理解",
                "type": "practice",
            },
        ]

        # S3.2: review 步骤引用 reflection 中的学习方式发现
        if source == "welcome_back" and last_reflection:
            # 清理 reflection 中的"今天"等时间词，避免与"上次"冲突
            clean_reflection = last_reflection.replace("今天", "").replace("刚刚", "").strip()
            steps.append({
                "order": 3,
                "description": f"上次你提到「{clean_reflection[:40]}」——今天看看是否还有效。",
                "type": "review",
            })
        elif is_struggling:
            steps.append({
                "order": 3,
                "description": f"回头复习：你之前对「{mission_topic}」相关的知识点有些吃力，再巩固一下",
                "type": "review",
            })
        else:
            steps.append({
                "order": 3,
                "description": f"总结今天关于「{mission_topic}」的关键收获",
                "type": "review",
            })

        return title, estimated_minutes, steps

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
