"""Session 领域模型。

Session 是苹果果核心聚合根，所有学习行为在此发生。
生命周期: Created → Intro → Learn → Practice → Reflect → Completed
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal
from uuid import uuid4


SessionStage = Literal["intro", "learn", "practice", "reflect"]


class SessionDomainError(Exception):
    """Session 域业务规则错误。"""

    pass


@dataclass
class SessionStep:
    """Session 任务步骤。"""
    order: int
    description: str
    step_type: Literal["explain", "practice", "review"] = "explain"
    status: Literal["pending", "active", "completed"] = "pending"


@dataclass
class SessionMission:
    """Session 内的任务分解。"""
    title: str
    estimated_minutes: int = 25
    steps: list[SessionStep] = field(default_factory=list)


@dataclass
class Session:
    """学习会话聚合根。

    状态完全由领域方法驱动，每次变更返回领域事件 dict。
    """

    id: str
    learner_id: str
    mission_id: str | None = None
    recommendation_id: str | None = None
    title: str = ""
    estimated_minutes: int = 25
    stage: SessionStage = "intro"
    status: Literal["active", "completed", "cancelled"] = "active"
    started_at: float = 0.0
    finished_at: float | None = None
    conversation_id: str | None = None
    mission: SessionMission | None = None
    reflection_text: str | None = None
    reflection_takeaways: list[str] = field(default_factory=list)
    reflection_next_steps: list[str] = field(default_factory=list)

    # ── 状态机命令 ───────────────────────────────────

    def transition_stage(self, new_stage: SessionStage) -> dict:
        """状态转移。不可逆校验。"""
        if self.status != "active":
            raise SessionDomainError(
                f"Cannot transition stage: session is {self.status}"
            )
        valid_order = {"intro": 0, "learn": 1, "practice": 2, "reflect": 3}
        if valid_order.get(new_stage, -1) <= valid_order.get(self.stage, -1):
            raise SessionDomainError(
                f"Stage transition not allowed: {self.stage} → {new_stage}"
            )
        old_stage = self.stage
        self.stage = new_stage
        return {
            "event_type": "LearningSessionStageChanged",
            "session_id": self.id,
            "learner_id": self.learner_id,
            "old_stage": old_stage,
            "new_stage": new_stage,
        }

    def set_mission(self, title: str, estimated_minutes: int, steps: list[dict]) -> dict:
        """设置 Session 的任务分解。intro 阶段调用。"""
        if self.stage != "intro":
            raise SessionDomainError(
                f"Cannot set mission in stage {self.stage}"
            )
        self.mission = SessionMission(
            title=title,
            estimated_minutes=estimated_minutes,
            steps=[
                SessionStep(
                    order=s.get("order", i + 1),
                    description=s["description"],
                    step_type=s.get("type", "explain"),
                )
                for i, s in enumerate(steps)
            ],
        )
        return {
            "event_type": "LearningSessionMissionUpdated",
            "session_id": self.id,
            "learner_id": self.learner_id,
            "mission_title": title,
            "steps": len(steps),
        }

    def complete(self, reflection: dict | None = None) -> dict:
        """完成 Session。不可逆。"""
        if self.status == "completed":
            raise SessionDomainError("Session already completed")
        if self.status == "cancelled":
            raise SessionDomainError("Cannot complete a cancelled session")

        import time
        self.status = "completed"
        self.finished_at = time.time()
        self.stage = "reflect"  # 强制进入 reflect

        if reflection:
            self.reflection_text = reflection.get("content", "")
            self.reflection_takeaways = reflection.get("key_takeaways", [])
            self.reflection_next_steps = reflection.get("next_steps", [])

        return {
            "event_type": "LearningSessionCompleted",
            "session_id": self.id,
            "learner_id": self.learner_id,
            "mission_id": self.mission_id or "",
            "recommendation_id": self.recommendation_id or "",
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "final_stage": self.stage,
            "title": self.title,
        }

    def cancel(self) -> dict:
        """取消 Session。"""
        if self.status == "completed":
            raise SessionDomainError("Cannot cancel a completed session")
        self.status = "cancelled"
        import time
        self.finished_at = time.time()
        return {
            "event_type": "LearningSessionCancelled",
            "session_id": self.id,
            "learner_id": self.learner_id,
        }


# ── 工厂函数 ───────────────────────────────────────────────

def create_session(
    learner_id: str,
    title: str = "",
    mission_id: str | None = None,
    recommendation_id: str | None = None,
    estimated_minutes: int = 25,
) -> tuple[Session, dict]:
    """创建 Session 实例 + 创建事件。"""
    import time
    session = Session(
        id=f"session_{uuid4().hex[:12]}",
        learner_id=learner_id,
        title=title,
        mission_id=mission_id,
        recommendation_id=recommendation_id,
        estimated_minutes=estimated_minutes,
        started_at=time.time(),
    )
    event = {
        "event_type": "LearningSessionCreated",
        "session_id": session.id,
        "learner_id": learner_id,
        "mission_id": mission_id or "",
        "recommendation_id": recommendation_id or "",
        "title": title,
        "estimated_minutes": estimated_minutes,
    }
    return session, event
