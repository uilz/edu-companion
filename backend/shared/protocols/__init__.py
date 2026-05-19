"""
模块接口协议 — Protocol 定义

设计原则:
- 每个模块对外只暴露一个 Protocol
- 只定义方法签名，不暴露实现细节
- 其他模块只 import 这里的 Protocol，不 import 具体实现
- 实现类在 domain/xxx/ 中，通过 DI 容器注入
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from shared.schemas.practice import Question, PracticeSession, SubmitResult, KnowledgeState
    from shared.schemas.conversation import Message, Branch, Partition
    from shared.schemas.learner import StudyPlan, DailyGoal, LearnerProfile, ProgressSummary


# ═══════════════════════════════════════════════════════════
# Practice — 练习系统
# ═══════════════════════════════════════════════════════════

@runtime_checkable
class PracticeService(Protocol):
    """
    练习系统对外契约

    其他模块只能通过此接口调用练习功能。
    实现: domain/practice/service.py
    """

    async def generate_questions(
        self, subject: str, topic: str, level: str, count: int
    ) -> list:  # → list[Question]
        """LLM 生成题目"""
        ...

    async def create_session(
        self, user_id: str, question_ids: list[str], mode: str = "adaptive"
    ) -> dict:  # → PracticeSession
        """创建练习会话"""
        ...

    async def submit_answer(
        self,
        session_id: str,
        question_id: str,
        answer: str,
        time_spent: float = 0.0,
        hints_used: int = 0,
    ) -> dict:  # → SubmitResult
        """
        提交答案 — 核心方法

        返回: {is_correct, feedback, p_known_after, error_entry?}
        副作用: 发布 AnswerSubmitted + ErrorRecorded 事件
        """
        ...

    async def get_knowledge_state(
        self, user_id: str, skill_id: str
    ) -> dict | None:
        """获取知识状态"""
        ...

    async def get_errors(
        self, user_id: str, resolved: bool | None = None, limit: int = 20
    ) -> dict:  # → {entries, total, unresolved_count}
        """获取错题本"""
        ...

    async def get_stats(
        self, user_id: str, time_range: str = "week"
    ) -> dict:
        """获取练习统计"""
        ...

    async def get_behavior_report(
        self, user_id: str, time_range: str = "week"
    ) -> dict:
        """获取行为分析报告"""
        ...


# ═══════════════════════════════════════════════════════════
# Conversation — 对话系统
# ═══════════════════════════════════════════════════════════

@runtime_checkable
class ConversationService(Protocol):
    """对话系统对外契约"""

    async def send_message(
        self, user_id: str, content: str,
        partition_id: str | None = None,
        branch_id: str | None = None,
    ) -> dict:  # → Message
        """发送消息 → LLM 回复"""
        ...

    async def list_partitions(self, user_id: str) -> list:  # → list[Partition]
        """列出用户的所有分区"""
        ...

    async def create_partition(
        self, user_id: str, name: str, topic: str = ""
    ) -> dict:
        """创建分区"""
        ...

    async def create_branch(
        self, partition_id: str, name: str
    ) -> dict:  # → Branch
        """在分区下创建分支"""
        ...

    async def inject_practice_context(
        self, user_id: str, branch_id: str, context: dict
    ) -> None:
        """
        注入练习上下文到对话记忆
        — 由 Practice 的 SessionCompleted 事件触发
        """
        ...


# ═══════════════════════════════════════════════════════════
# Planning — 学习规划
# ═══════════════════════════════════════════════════════════

@runtime_checkable
class PlanningService(Protocol):
    """学习规划对外契约"""

    async def generate_plan(self, user_id: str) -> dict:  # → StudyPlan
        """生成/刷新学习计划"""
        ...

    async def get_daily_goal(self, user_id: str) -> dict:  # → DailyGoal
        """获取今日目标进度"""
        ...

    async def mark_task_complete(
        self, user_id: str, task_id: str
    ) -> dict:
        """标记任务完成"""
        ...

    async def get_plan_progress(self, user_id: str) -> dict:
        """获取计划完成进度"""
        ...


# ═══════════════════════════════════════════════════════════
# Analytics — 行为分析
# ═══════════════════════════════════════════════════════════

@runtime_checkable
class AnalyticsService(Protocol):
    """行为分析对外契约"""

    async def compute_streak(self, user_id: str) -> tuple[int, int]:
        """计算连续学习天数 (current, longest)"""
        ...

    async def find_best_hours(self, user_id: str) -> list[int]:
        """找最佳学习时段"""
        ...

    async def compute_regularity(self, user_id: str) -> float:
        """计算学习规律性 (0-1)"""
        ...


# ═══════════════════════════════════════════════════════════
# Habits — 习惯养成
# ═══════════════════════════════════════════════════════════

@runtime_checkable
class HabitService(Protocol):
    """习惯养成对外契约"""

    async def check_daily_goal(self, user_id: str) -> dict:  # → DailyGoal
        """检查今日目标进度"""
        ...

    async def get_pomodoro_suggestion(
        self, user_id: str
    ) -> dict:  # → {work_minutes, break_minutes, message}
        """获取番茄钟建议"""
        ...

    async def get_tiny_habits(
        self, user_id: str
    ) -> list:  # → list[TinyHabit]
        """获取推荐微习惯"""
        ...


# ═══════════════════════════════════════════════════════════
# Materials — 资料系统
# ═══════════════════════════════════════════════════════════

@runtime_checkable
class MaterialService(Protocol):
    """资料系统对外契约"""

    async def upload(self, user_id: str, file_path: str) -> dict:
        """上传资料 → 触发异步索引"""
        ...

    async def search(
        self, user_id: str, query: str, top_k: int = 10
    ) -> list:  # → list[SearchResult]
        """语义搜索资料"""
        ...

    async def generate_questions(
        self, user_id: str, material_id: str, count: int = 5
    ) -> list:  # → list[Question]
        """从资料生成练习题目"""
        ...


# ═══════════════════════════════════════════════════════════
# Knowledge Graph — 知识图谱
# ═══════════════════════════════════════════════════════════

@runtime_checkable
class KnowledgeGraphService(Protocol):
    """知识图谱对外契约"""

    async def get_graph(self, user_id: str) -> dict:
        """获取用户的知识图谱 (nodes + edges + mastery)"""
        ...

    async def get_prerequisites(self, skill_id: str) -> list[str]:
        """获取某个知识点的前置依赖"""
        ...

    async def can_practice(
        self, user_id: str, skill_id: str
    ) -> tuple[bool, str | None]:
        """
        检查是否满足前置条件
        返回: (can_practice, reason_if_blocked)
        """
        ...

    async def find_learning_path(
        self, user_id: str, target_skill: str
    ) -> list[str]:
        """Dijkstra 最优学习路径"""
        ...


# ═══════════════════════════════════════════════════════════
# Media — 媒体搜索
# ═══════════════════════════════════════════════════════════

@runtime_checkable
class MediaService(Protocol):
    """媒体搜索对外契约"""

    async def search(
        self, query: str, platforms: list[str] | None = None
    ) -> dict:  # → {platform: [urls]}
        """多平台媒体搜索"""
        ...

    async def recommend_for_error(
        self, skill_id: str, error_type: str
    ) -> list:  # → list[VideoResult]
        """根据错题推荐相关视频"""
        ...


# ═══════════════════════════════════════════════════════════
# Repository 协议
# ═══════════════════════════════════════════════════════════

@runtime_checkable
class KnowledgeStateRepository(Protocol):
    """知识状态持久化契约"""

    async def load(self, user_id: str, skill_id: str) -> dict | None: ...
    async def save(self, user_id: str, skill_id: str, state: dict) -> None: ...
    async def load_all(self, user_id: str) -> dict[str, dict]: ...


@runtime_checkable
class QuestionRepository(Protocol):
    """题库持久化契约"""

    async def save(self, question: dict) -> str: ...
    async def find_by_id(self, question_id: str) -> dict | None: ...
    async def find_by_skill(
        self, skill_id: str, limit: int = 20
    ) -> list: ...


@runtime_checkable
class SessionRepository(Protocol):
    """会话持久化契约"""

    async def create(self, user_id: str, question_ids: list[str]) -> str: ...
    async def find_by_id(self, session_id: str) -> dict | None: ...
    async def update_status(self, session_id: str, status: str) -> None: ...
    async def list_by_user(
        self, user_id: str, limit: int = 20
    ) -> list: ...


@runtime_checkable
class ErrorBookRepository(Protocol):
    """错题本持久化契约"""

    async def add(self, entry: dict) -> str: ...
    async def find_unresolved(
        self, user_id: str, limit: int = 20
    ) -> list: ...
    async def mark_resolved(self, entry_id: str) -> None: ...


# ═══════════════════════════════════════════════════════════
# Multimedia — 多媒体服务 (Phase 5)
# ═══════════════════════════════════════════════════════════

from shared.protocols.multimedia import AudioSynthesizer, ImageRenderer  # noqa: E402, F401
