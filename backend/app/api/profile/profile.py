"""Profile API — 学习者画像查询接口。

供 Profile 页面消费。回答「苹果果现在怎么看我？」
而非「数据库里存了什么」。
"""

from fastapi import APIRouter, Depends, HTTPException

from app.domain.auth.dependencies import current_user_id
from app.domain.growth.service import GrowthService
from app.application.di import get_growth_service

router = APIRouter(prefix="/api/profile", tags=["profile"])


@router.get("", response_model=dict)
async def get_profile(
    user_id: str = Depends(current_user_id),
    growth_service: GrowthService = Depends(get_growth_service),
):
    """获取学习者完整画像。

    返回四块叙事：苹果果眼中的你 + 你的成长 + 正在努力 + 最近学会了什么。
    """
    if not user_id:
        raise HTTPException(status_code=401, detail="请先登录")

    profile = _get_learner_profile(user_id)
    goals = _get_goals(user_id)
    growth_summary = await growth_service.get_growth_summary(user_id)

    # ── Narrative：苹果果眼中的你（V1 rule-based → V2 AI-generated）──
    narrative = _generate_narrative(profile, goals, growth_summary)

    # ── Growth narrative：一句话总结成长 ──
    growth_narrative = _generate_growth_narrative(growth_summary)

    # ── Timeline：最近学会了什么 ──
    timeline = _build_timeline(growth_summary)

    return {
        "narrative": narrative,
        "profile": profile,
        "goals": goals,
        "growth_summary": growth_summary,
        "growth_narrative": growth_narrative,
        "timeline": timeline,
    }


# ── Narrative 生成（V1 rule-based） ──────────────────────────

_PERSONA_NARRATIVES: dict[str, str] = {
    "explorer": "你对新知识充满好奇心，喜欢广泛涉猎不同的领域。",
    "practitioner": "你相信「做中学」，通过反复练习来真正掌握知识。",
    "exam_driven": "你是目标导向的学习者，善于围绕考试大纲系统推进。",
    "researcher": "你喜欢深挖问题的本质，不满足于表面的答案。",
    "social": "你在交流和讨论中吸收知识，和别人一起学习时状态最好。",
    "systematic": "你喜欢按部就班地推进，每一步都走得扎实。",
}

_STYLE_NARRATIVES: dict[str, str] = {
    "visual": "你更喜欢通过图表和示意图来理解概念。",
    "auditory": "你更喜欢通过听讲和讨论来吸收知识。",
    "reading": "你更喜欢先阅读材料、理解原理之后再开始练习。",
    "kinesthetic": "你更喜欢亲自动手操作，在实践中学习。",
}


def _generate_narrative(
    profile: dict,
    goals: list[dict],
    growth_summary: dict,
) -> str:
    """V1: 基于现有数据生成「苹果果眼中的你」叙事。

    Future: 由 Memory + Persona + History + Growth + Goals 综合推导。
    """
    parts: list[str] = []

    # 1. Persona → learning personality
    persona_type = profile.get("persona", {}).get("type", "explorer")
    persona_text = _PERSONA_NARRATIVES.get(persona_type, "你是一个独特的学习者。")
    parts.append(persona_text)

    # 2. Learning style → how they prefer to learn
    style = profile.get("learning_style", "")
    style_text = _STYLE_NARRATIVES.get(style)
    if style_text:
        parts.append(style_text)

    # 3. Streak → consistency observation
    streak = growth_summary.get("streak_days", 0)
    if streak >= 14:
        parts.append(f"过去30天，你已经连续学习了{streak}天，学习节奏非常稳定。")
    elif streak >= 7:
        parts.append(f"过去30天里你坚持了{streak}天，正在养成稳定的学习习惯。")
    elif streak >= 3:
        parts.append(f"最近你开始了{streak}天的连续学习，是个不错的开始。")
    elif streak > 0:
        parts.append("你刚刚开始建立学习节奏，苹果果会陪着你。")

    # 4. Subjects → what they're exploring
    subjects = profile.get("subjects", [])
    if subjects:
        parts.append(f"你目前主要在探索{' 和 '.join(subjects)}。")

    # 5. Goals → what they're working toward
    active_goals = [g for g in goals if g.get("status") == "active"]
    if len(active_goals) == 1:
        parts.append(f"你正在为一个目标持续努力。")
    elif len(active_goals) > 1:
        parts.append(f"你同时在推进{len(active_goals)}个学习目标。")

    return "".join(parts)


def _generate_growth_narrative(growth_summary: dict) -> str:
    """生成「你的成长」一句话叙事。"""
    total = growth_summary.get("total_sessions", 0)
    streak = growth_summary.get("streak_days", 0)
    score = growth_summary.get("total_gain_score", 0)

    if total == 0:
        return "你刚刚开始认识苹果果，完成第一次学习后，这里会开始记录你的成长。"

    parts: list[str] = []
    parts.append(f"你已经完成了{total}次学习。")

    if streak >= 7:
        parts.append(f"连续{streak}天的坚持，说明你正在认真对待自己的成长。")
    elif streak >= 3:
        parts.append(f"过去几天你保持了{streak}天连续学习，节奏正在形成。")

    if score > 0:
        parts.append(f"累计收获了{score}点成长积分。")

    return "".join(parts)


def _build_timeline(growth_summary: dict) -> list[dict]:
    """从最近 GrowthRecords 构建「最近学会了什么」时间线。"""
    records = growth_summary.get("recent_records", [])
    result: list[dict] = []
    for r in records[:5]:
        entry: dict = {
            "date": r.get("session_started_at", ""),
            "title": r.get("session_title", ""),
            "summary": r.get("summary", ""),
            "key_takeaways": r.get("key_takeaways", []),
        }
        result.append(entry)
    return result


def _get_learner_profile(user_id: str) -> dict:
    """从 LearnerModelEngine 获取画像，补充 Persona 默认值。"""
    try:
        from shared.learner_model import get_learner_model
        engine = get_learner_model()
        profile = engine.get_or_create_profile(user_id)
        return {
            "user_id": profile.user_id,
            "nickname": profile.nickname or "学习者",
            "subjects": profile.subjects or [],
            "learning_style": profile.learning_style.value
                if hasattr(profile.learning_style, "value") else str(profile.learning_style),
            "persona": {
                "type": "explorer",           # V1 默认值，未来由 PersonaAnalyzer 计算
                "confidence": 0.0,
            },
            "updated_at": profile.updated_at.isoformat()
                if profile.updated_at else None,
        }
    except Exception:
        return {
            "user_id": user_id,
            "nickname": "学习者",
            "subjects": [],
            "learning_style": "reading",
            "persona": {"type": "explorer", "confidence": 0.0},
            "updated_at": None,
        }


def _get_goals(user_id: str) -> list[dict]:
    """从 Planning 服务获取目标列表。"""
    try:
        from app.services.planning.goals import list_goals
        goals = list_goals(user_id, status=None)
        return [
            {
                "id": g["id"],
                "title": g.get("title", ""),
                "status": g.get("status", "active"),
                "progress_pct": g.get("progress_pct", 0.0),
            }
            for g in (goals or [])
        ]
    except Exception:
        return []
