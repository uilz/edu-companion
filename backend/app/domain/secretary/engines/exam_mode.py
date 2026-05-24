"""备考模式模块 — 日历考试事件检测 + 冲刺清单生成

触发条件:
  - 用户主动启用（settings中开关）
  - 日历中有近7天的考试事件（需 opt-in）
  - 考试临近3天内自动提升相关知识点优先级

功能:
  - 检测即将到来的考试
  - 生成冲刺复习清单
  - 高优先级标记相关知识点
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from ..models import Proposal
from .module_registry import SecretaryModule, ModuleMeta
from .context_engine import SessionContext

logger = logging.getLogger(__name__)


class ExamModeModule(SecretaryModule):
    """备考模式 — 考试检测 + 冲刺清单"""

    @property
    def meta(self) -> ModuleMeta:
        return ModuleMeta(
            name="exam_mode",
            display_name="备考模式",
            emoji="📚",
            description="检测考试事件，生成冲刺复习清单",
            default_enabled=False,  # 默认关闭，需 opt-in
            run_interval_seconds=3600,  # 每小时检查一次
            version="1.0.0",
            author="系统内置",
        )

    async def run_check(self, user_id: str, ctx: SessionContext | None = None) -> list[Proposal]:
        proposals = []

        # 检查是否有考试信息（未来可接入日历）
        upcoming_exams = self._detect_upcoming_exams(user_id, ctx)

        for exam in upcoming_exams:
            days_left = exam["days_left"]
            if days_left <= 7:
                urgency = "high" if days_left <= 3 else "medium"
                priority = 1 if urgency == "high" else 3

                proposals.append(Proposal(
                    id=f"exam_{exam['name']}_{datetime.now().timestamp():.0f}",
                    emoji="📚",
                    title=f"📚 {exam['name']} 备考冲刺",
                    description=f"距 {exam['name']} 还有{days_left}天，"
                               f"已进入{'冲刺阶段' if urgency == 'high' else '备考期'}。"
                               f"建议优先复习相关的高频考点和薄弱点。",
                    action_type="review",
                    payload={"exam_name": exam["name"], "exam_date": exam["date"],
                             "days_left": days_left, "urgency": urgency},
                    priority=priority,
                    generated_by="exam_mode",
                    overrideable=True,
                ))

        return proposals

    def _detect_upcoming_exams(self, user_id: str, ctx: SessionContext | None = None) -> list[dict]:
        """检测即将到来的考试

        当前使用静态考试信息，后续可集成日历API。
        如果用户未 opt-in 日历，返回空列表。
        """
        # 从用户偏好中读取考试信息
        # 当前返回空（用户手动设置入口待添加）
        return []
