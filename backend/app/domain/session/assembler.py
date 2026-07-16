"""
Runtime Assembler — 将持久层数据组装为 RuntimeContext。

职责（一句话）：
  把持久层的数据组装成 RuntimeContext。

不做：
  - 不分析 Mission（那是 LI-01）
  - 不推断 Learner 画像（那是 LI-03）
  - 不访问 LLM
  - 不修改任何持久层数据

原则：
  P4 — 共享 Context，隔离 Capability
  P8 — RuntimeContext 是 Session 内唯一可变对象
  纯函数 — 相同输入总是返回等价的 RuntimeContext
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from app.domain.cognitive import get_repo as get_cognitive_repo
from app.domain.growth.repository import get_growth_repo
from app.domain.session.repository import get_session_repo
from app.domain.session.runtime_context import (
    ChatMessage,
    ConceptItem,
    ConversationContext,
    DependencyItem,
    DifficultySpot,
    Exp04Stage,
    FlowContext,
    GrowthRecord,
    GrowthSignals,
    LearnerContext,
    LearnerProfile,
    MissionAnalysis,
    MissionContext,
    MissionSource,
    PracticeStrategy,
    ReasoningPattern,
    ReflectionContext,
    RuntimeContext,
    SkillState,
    UnderstandingContext,
)
from shared.learner_model import get_learner_model

logger = logging.getLogger(__name__)


# ── Stage mapping ──────────────────────────────────────────

_BACKEND_STAGE_TO_EXP04 = {
    "intro": Exp04Stage.ENTER,
    "learn": Exp04Stage.LEARN,
    "practice": Exp04Stage.SELF_VALIDATION,
    "reflect": Exp04Stage.REFLECTION,
}


def _map_stage(backend_stage: str) -> Exp04Stage:
    """将后端 SessionStage 映射到 EXP-04 的 Exp04Stage。

    无法映射时默认 ENTER（不崩溃原则）。
    """
    return _BACKEND_STAGE_TO_EXP04.get(backend_stage, Exp04Stage.ENTER)


def _classify_source(session) -> MissionSource:
    """根据 Session 上下文推断 MissionSource。"""
    # 简单策略：有 welcome_back 标志或 continuation 特征时判定
    # 当前简化处理，全部返回 user_topic
    return MissionSource.USER_TOPIC


def _infer_trend(node) -> str:
    """从 CognitiveNode 推断 SkillState.trend。"""
    if node.trend and node.trend.direction:
        direction = node.trend.direction.lower()
        if direction in ("ascending", "stable", "declining"):
            return direction
    return "stable"


def _load_reasoning_patterns(user_id: str) -> Optional[ReasoningPattern]:
    """加载推理模式（从 LearnerProfile JSONB 累积）。

    当前返回 None（LI-03 累积后填充）。
    这是一个可选字段，不存在时不崩溃。
    """
    return None


# ── Main Assembler ────────────────────────────────────────


class RuntimeAssembler:
    """RuntimeContext 组装器。

    纯函数风格：assemble() 读取多个数据源，返回一个 RuntimeContext。
    无副作用：不修改任何持久层数据。
    """

    def __init__(
        self,
        session_repo=None,
        cognitive_repo=None,
        growth_repo=None,
        learner_engine=None,
    ):
        """依赖注入，方便测试。

        如果不传参，使用生产环境的单例。
        """
        self._session_repo = session_repo or get_session_repo()
        self._cognitive_repo = cognitive_repo or get_cognitive_repo()
        self._growth_repo = growth_repo or get_growth_repo()
        self._learner_engine = learner_engine or get_learner_model()

    async def assemble(self, user_id: str, session_id: str) -> RuntimeContext:
        """组装 RuntimeContext。

        Args:
            user_id: 用户 ID（必须存在）
            session_id: Session ID（必须存在）

        Returns:
            RuntimeContext: 完整的运行时上下文，8 个命名空间全部有值。

        Raises:
            AssemblerNotFoundError: user_id 或 session_id 不存在时。
        """
        # 1. 加载 Session（必需）
        session = self._session_repo.get(session_id)
        if session is None:
            raise AssemblerNotFoundError(f"Session not found: {session_id}")

        # 2. 加载 LearnerProfile（必需）
        try:
            profile = self._learner_engine.get_or_create_profile(user_id)
        except Exception as e:
            raise AssemblerNotFoundError(f"Learner not found: {user_id}") from e

        # 3. 加载 BKT 知识状态（可选：表为空时不崩溃）
        try:
            nodes = self._cognitive_repo.list_all_nodes(user_id)
        except Exception:
            logger.warning("Failed to load cognitive nodes for user %s", user_id, exc_info=True)
            nodes = []

        knowledge = {}
        for node in nodes:
            if node.belief and node.belief.proficiency_mean is not None:
                knowledge[node.id] = SkillState(
                    proficiency=node.belief.proficiency_mean,
                    precision=node.belief.proficiency_precision or 0.5,
                    trend=_infer_trend(node),
                    last_active=(
                        datetime.fromtimestamp(node.belief.last_updated)
                        if node.belief.last_updated
                        else None
                    ),
                )

        # 4. 加载最近成长记录（可选）
        try:
            growth = self._growth_repo.get_latest(user_id)
        except Exception:
            logger.warning("Failed to load growth records for user %s", user_id, exc_info=True)
            growth = None

        recent_growth = None
        if growth:
            recent_growth = GrowthRecord(
                session_id=growth.session_id,
                skill_gains=[str(g) for g in growth.skill_gains],
                summary=growth.summary or "",
                key_takeaways=list(growth.key_takeaways) if growth.key_takeaways else [],
                reflection_snippet=growth.reflection_snippet,
                created_at=(
                    datetime.fromtimestamp(growth.created_at)
                    if growth.created_at
                    else datetime.now()
                ),
            )

        # 5. 加载推理模式（可选）
        patterns = _load_reasoning_patterns(user_id)

        # 6. 构造 Mission context
        mission_title = session.title or ""
        # 优先使用 session.mission.title（更具体），否则用 session.title
        if session.mission and session.mission.title:
            mission_title = session.mission.title

        mission = MissionContext(
            title=mission_title,
            source=_classify_source(session),
            analysis=None,  # 如果有缓存的 analysis 则填充
        )

        # 尝试加载缓存的 MissionAnalysis
        if session.mission_analysis:
            try:
                from app.domain.session.runtime_context import MissionAnalysis as MA
                mission.analysis = MA(**session.mission_analysis)
            except Exception:
                logger.warning("Failed to load cached mission_analysis for session %s", session_id)

        # 7. 构造 Learner context
        learner_profile = LearnerProfile(
            subjects=getattr(profile, "subjects", []),
            grade_level=getattr(profile, "grade_level", ""),
            learning_style=(
                getattr(profile, "learning_style", None)
                or getattr(profile, "learning_style_preference", None)
            ),
        )

        learner = LearnerContext(
            knowledge=knowledge,
            profile=learner_profile,
            recent_growth=recent_growth,
            patterns=patterns,
        )

        # 8. 构造 Flow context
        flow = FlowContext(
            current_stage=_map_stage(session.stage),
        )

        # 9. 构造其他默认 context
        understanding = UnderstandingContext(
            user_text="",
            reference_text="",
        )
        reflection = ReflectionContext()
        conversation = ConversationContext()

        # 10. 组装
        return RuntimeContext(
            session_id=session_id,
            user_id=user_id,
            mission=mission,
            learner=learner,
            flow=flow,
            understanding=understanding,
            reflection=reflection,
            conversation=conversation,
        )


# ── Errors ────────────────────────────────────────────────


class AssemblerError(Exception):
    """Assembler 异常基类。"""


class AssemblerNotFoundError(AssemblerError):
    """数据源不存在。"""


# ── Module-level convenience ──────────────────────────────

_assembler: Optional[RuntimeAssembler] = None


def get_assembler() -> RuntimeAssembler:
    """获取全局 Assembler 单例。"""
    global _assembler
    if _assembler is None:
        _assembler = RuntimeAssembler()
    return _assembler
