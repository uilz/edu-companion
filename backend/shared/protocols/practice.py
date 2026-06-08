"""
Practice Service Protocol — 练习模块对外契约
其他模块只能通过此接口调用练习功能。
实现类: domain/practice/service.py PracticeServiceImpl
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from shared.constants import DEFAULT_USER_ID
from app.schemas.practice import (
    Question,
    PracticeSession,
    KnowledgeState,
)


@runtime_checkable
class PracticeService(Protocol):
    """练习模块对外契约 — 统一入口

    整合了以下子模块的公共方法：
    - practice_service: 认知更新、答案校验、提示、错题本、统计
    - practice_session: 会话管理
    - practice_adaptive: 自适应选题
    - practice_question_gen: AI 出题
    - practice_question_bank: 题库管理
    - practice_question_crud: 题目 CRUD
    - practice_error_book: 错题本查询
    - practice_scheduler: 复习调度
    - practice_exam: 考试模式
    - practice_stats: 统计汇总
    - practice_secretary_integration: 秘书联动
    - practice_recall: 对话中练习回顾
    - practice_integrator: 练习→对话集成
    """

    # ── 核心路径 ──

    async def generate_questions(
        self,
        subject: str,
        topic: str = "",
        level: str = "medium",
        count: int = 5,
        user_id: str = DEFAULT_USER_ID,
    ) -> list[Question]:
        """生成练习题目"""
        ...

    async def create_session(
        self,
        user_id: str,
        question_ids: list[str],
        mode: str = "adaptive",
    ) -> PracticeSession:
        """创建练习会话"""
        ...

    async def submit_answer(
        self,
        session_id: str,
        question_id: str,
        answer: str,
        time_spent: float = 0.0,
        hints_used: int = 0,
        explanation_text: str = "",
    ) -> dict:
        """提交答案 — 核心路径，同步返回 dict"""
        ...

    async def get_hint(
        self,
        question_id: str,
        hint_level: int = 1,
    ) -> dict:
        """获取提示"""
        ...

    async def get_knowledge_state(
        self,
        user_id: str,
        skill_id: str,
    ) -> KnowledgeState | None:
        """查询知识点掌握状态"""
        ...

    async def get_errors(
        self,
        user_id: str,
        resolved: bool | None = None,
        limit: int = 50,
    ) -> list[dict]:
        """获取错题列表"""
        ...

    async def get_summary(
        self,
        branch_id: str,
    ) -> dict:
        """获取分支相关的练习摘要（供对话上下文注入用）"""
        ...

    # ── 认知更新 ──

    def update_cognitive_after_practice(
        self,
        user_id: str,
        skill_id: str,
        is_correct: bool,
        latency_ms: int = 0,
    ) -> dict:
        """练习后更新 CognitiveNode 并发布事件"""
        ...

    # ── 答案校验 ──

    def check_answer(self, user_answer: str, correct_answer: str) -> bool:
        """标准化比较答案"""
        ...

    def build_reply_text(self, is_correct: bool, correct_label: str, explanation: str) -> str:
        """构建内联回复文本"""
        ...

    # ── 提示 ──

    def get_hint_for_question(self, question_id: str, current_level: int) -> dict | None:
        """获取题目提示（逐级提示 → 最终解释）"""
        ...

    def get_inline_hint(self, block_id: str) -> dict | None:
        """获取内联提示"""
        ...

    # ── 错题本 ──

    def query_error_book(
        self,
        user_id: str = DEFAULT_USER_ID,
        resolved: bool | None = None,
        skill_id: str | None = None,
        limit: int = 20,
    ) -> dict:
        """查询错题本（支持过滤）"""
        ...

    def review_error_entry(self, entry_id: str, is_correct: bool = True) -> dict | None:
        """复习错题"""
        ...

    async def analyze_error_entry(self, entry_id: str) -> dict | None:
        """LLM 深度分析单条错题"""
        ...

    def get_error_attribution_stats(self, user_id: str = DEFAULT_USER_ID) -> dict:
        """错因分布统计"""
        ...

    # ── 会话管理 ──

    def list_practice_sessions(self, user_id: str = DEFAULT_USER_ID, limit: int = 20) -> dict:
        """列出用户的所有练习会话"""
        ...

    def complete_practice_session(self, session_id: str) -> dict | None:
        """完成会话，返回会话数据 + 统计"""
        ...

    def record_attempt(
        self,
        user_id: str,
        session_id: str,
        question_id: str,
        answer: str,
        is_correct: bool,
        time_spent_seconds: float,
        hints_used: int,
    ) -> None:
        """记录一次答题"""
        ...

    # ── 统计 ──

    def compute_practice_stats(self, time_range: str = "week", user_id: str = DEFAULT_USER_ID) -> dict:
        """计算练习统计"""
        ...

    def compute_behavior_report_data(self, time_range: str = "week", user_id: str = DEFAULT_USER_ID) -> dict:
        """聚合行为报告数据"""
        ...

    async def get_stats(self, user_id: str, time_range: str = "week") -> dict:
        """从 attempts 表聚合练习统计（异步版）"""
        ...

    async def get_behavior_report(self, user_id: str, time_range: str = "week") -> dict:
        """学习行为分析报告（异步版）"""
        ...

    # ── 自适应选题 ──

    def adaptive_select(
        self,
        bank_id: str,
        user_id: str = DEFAULT_USER_ID,
        count: int = 10,
        mode: str = "adaptive",
        exclude_ids: list[str] | None = None,
        target_difficulty: int | None = None,
        cognitive_node_ids: list[str] | None = None,
        bloom_distribution: dict[str, int] | None = None,
    ) -> list[dict]:
        """自适应选题"""
        ...

    # ── AI 出题 ──

    async def generate_and_save(
        self,
        bank_id: str,
        user_id: str = DEFAULT_USER_ID,
        subject: str = "",
        skill: str = "",
        bloom: str = "understand",
        difficulty: int = 3,
        count: int = 5,
        question_type: str = "choice",
    ) -> list[dict]:
        """AI 生成题目并保存"""
        ...

    # ── 题库管理 ──

    def resolve_bank_for_conversation(self, partition_id: str, topic: str = "") -> str:
        """对话→题库自动映射"""
        ...

    def resolve_bank_for_node(self, node_id: str) -> str:
        """节点→题库映射"""
        ...

    # ── 复习调度 ──

    def get_due_reviews(self, user_id: str = DEFAULT_USER_ID, limit: int = 10) -> list[dict]:
        """获取到期复习题目"""
        ...

    # ── 考试模式 ──

    def create_exam(
        self,
        user_id: str = DEFAULT_USER_ID,
        bank_id: str = "",
        count: int = 20,
        duration_minutes: int = 60,
        config: dict | None = None,
        cognitive_node_ids: list[str] | None = None,
    ) -> dict:
        """创建考试会话"""
        ...

    # ── 秘书联动 ──

    def check_and_generate_proposals(
        self,
        user_id: str,
        session_id: str,
        skill_id: str,
        is_correct: bool,
        proficiency: float,
    ) -> list[dict]:
        """练习后检查并生成秘书提案"""
        ...

    # ── 练习→对话集成 ──

    async def integrate_practice_to_branch(
        self,
        user_id: str,
        session: PracticeSession,
        partition_id: str,
        branch_id: str,
    ) -> dict | None:
        """将练习结果写入对话branch"""
        ...
