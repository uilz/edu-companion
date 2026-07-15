"""秘书仪表盘聚合服务 (Task #168)

将 `/api/secretary/dashboard` 中的业务编排与数据聚合下沉到服务层，
API 路由仅负责 HTTP 参数校验与调用。
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Any, Callable

from app.domain.secretary.secretary_service import SecretaryService
from app.infrastructure.db.proposal_store import ProposalStore
from app.services.analytics.adaptive_planner import adaptive_planner
from app.services.planning.confirmations import list_confirmations as list_planning_confirmations
from app.services.practice.practice_stats import get_overview as get_practice_overview
from shared.constants import recommend_practice_items
from shared.knowledge_trace import get_all_cognitive_states

logger = logging.getLogger(__name__)

_dashboard_cache: dict[str, tuple[float, dict]] = {}
_DASHBOARD_TTL = 30.0  # 30s


def _greeting(name: str | None) -> str:
    """根据当前时间生成问候语"""
    hour = datetime.now(timezone.utc).hour
    if 5 <= hour < 12:
        prefix = "早上好"
    elif 12 <= hour < 18:
        prefix = "下午好"
    elif 18 <= hour < 23:
        prefix = "晚上好"
    else:
        prefix = "夜深了"
    if name:
        return f"{prefix}，{name}"
    return prefix


def _build_focus(plan_data: dict) -> dict | None:
    """从学习计划中构建今日焦点"""
    plan = plan_data.get("plan") if isinstance(plan_data, dict) else None
    items = plan.get("items") if isinstance(plan, dict) else None
    if not items:
        return None
    pending = next(
        (it for it in items if not it.get("completed") and not it.get("done")),
        None,
    )
    target = pending or items[0]
    return {
        "id": target.get("task_id", ""),
        "type": "plan_item",
        "title": target.get("title", ""),
        "description": target.get("description", ""),
        "estimated_minutes": target.get("estimated_minutes", 0) or 0,
        "action": {
            "type": "navigate",
            "target": f"/practice?node={target.get('skill_id', '')}",
        },
    }


def _build_stats(snapshot: dict, overview: dict) -> list[dict]:
    """构建 8 张统计卡，包含动态优先级"""
    weak_count = int(snapshot.get("weak_count", 0) or 0)
    stagnant_count = int(snapshot.get("stagnant_count", 0) or 0)
    streak_days = int(snapshot.get("streak_days", 0) or 0)
    cognitive_load = float(snapshot.get("cognitive_load", 0) or 0)

    total_questions = int(overview.get("total_questions", 0) or 0)
    study_minutes = float(overview.get("study_minutes", 0) or 0)
    mastered_count = int(overview.get("mastered_count", 0) or 0)
    today_questions = int(overview.get("today_questions", 0) or 0)

    cards = [
        {
            "key": "weak_count",
            "label": "薄弱点",
            "value": weak_count,
            "priority": "high" if weak_count > 0 else "low",
            "icon": "alert",
            "deep_link": "/analytics?tab=weak",
        },
        {
            "key": "stagnant_count",
            "label": "停滞项",
            "value": stagnant_count,
            "priority": "high" if stagnant_count > 0 else "low",
            "icon": "clock",
            "deep_link": "/analytics?tab=stagnant",
        },
        {
            "key": "today_questions",
            "label": "今日题数",
            "value": today_questions,
            "priority": "medium" if today_questions > 0 else "low",
            "icon": "target",
        },
        {
            "key": "cognitive_load",
            "label": "认知负荷",
            "value": f"{int(cognitive_load * 100)}%",
            "priority": "high" if cognitive_load > 0.7 else ("medium" if cognitive_load > 0.3 else "low"),
            "icon": "brain",
        },
        {
            "key": "total_questions",
            "label": "累计练习",
            "value": total_questions,
            "priority": "low",
            "icon": "bar-chart",
        },
        {
            "key": "study_minutes",
            "label": "学习时长",
            "value": f"{int(study_minutes)}m",
            "priority": "low",
            "icon": "clock",
        },
        {
            "key": "mastered_count",
            "label": "已掌握",
            "value": mastered_count,
            "priority": "low",
            "icon": "check-circle",
        },
        {
            "key": "streak_days",
            "label": "连续天数",
            "value": streak_days,
            "priority": "medium" if streak_days > 0 else "low",
            "icon": "flame",
        },
    ]

    priority_order = {"high": 0, "medium": 1, "low": 2}
    order_map = {
        "weak_count": 0,
        "stagnant_count": 1,
        "cognitive_load": 2,
        "today_questions": 3,
        "streak_days": 4,
        "total_questions": 5,
        "study_minutes": 6,
        "mastered_count": 7,
    }
    cards.sort(key=lambda c: (priority_order.get(c["priority"], 9), order_map.get(c["key"], 99)))
    return cards


def _normalize_ts(value: Any) -> float:
    """将 datetime / 时间戳 / 字符串统一为 float 时间戳"""
    if value is None:
        return 0.0
    if isinstance(value, datetime):
        return value.timestamp()
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _build_pending(proposals: list[dict], confirmations: list[dict]) -> dict:
    """统一提案与计划确认为待处理流"""
    items: list[dict] = []
    for p in proposals:
        items.append({
            "id": p.get("id", ""),
            "kind": "proposal",
            "title": p.get("title", ""),
            "description": p.get("description", ""),
            "priority": p.get("priority", 3) or 3,
            "action_type": p.get("action_type", ""),
            "source": p.get("source", "secretary"),
            "created_at": _normalize_ts(p.get("created_at")),
            "tags": ["建议"],
            "emoji": p.get("emoji", "💡"),
            "target": p.get("target") or p.get("payload") or {},
        })
    for c in confirmations:
        items.append({
            "id": c.get("id", ""),
            "kind": "confirmation",
            "title": c.get("title", ""),
            "description": c.get("description", ""),
            "priority": c.get("priority", 3) or 3,
            "action_type": "plan_item_confirmation",
            "source": c.get("source_module", "planning"),
            "created_at": _normalize_ts(c.get("created_at")),
            "tags": ["计划确认"],
            "emoji": "📋",
            "target": {},
        })

    items.sort(key=lambda x: (-int(x.get("priority", 0) or 0), -x.get("created_at", 0.0)))
    return {"items": items, "total": len(items)}


def _build_recommendations(user_id: str) -> dict:
    """聚合 AI 学习建议，融合 Learner Model 画像数据（S2.3）。

    策略：
    - 以 CognitiveNode 状态为底
    - 叠加 Learner Model 的 struggling_skills、subjects
    - 对困难知识点和偏好学科加权
    - 无认知节点时，从 Learner Model 推导兜底推荐
    - 排序确定性：优先级降序 + skill_id 升序
    """
    try:
        # 1. 基础认知状态
        states = get_all_cognitive_states(user_id)
        recs = recommend_practice_items(states, top_n=20)

        # 2. 读取 Learner Model
        from shared.learner_model import get_learner_model

        engine = get_learner_model()
        profile = engine.get_or_create_profile(user_id)
        progress = engine.get_progress_summary(user_id)

        # 3. 兜底：推荐不足时，从 Learner Model 补充
        existing_ids = {r["skill_id"] for r in recs}
        fallback_ids = _derive_fallback_skill_ids(profile, progress, existing_ids)
        for sid in fallback_ids:
            recs.append({
                "skill_id": sid,
                "level": "未接触",
                "priority": 0.3,
                "p_known": 0.0,
            })

        # 4. 加权：困难知识点置顶
        struggling = set(progress.struggling_skills or [])
        for rec in recs:
            if rec["skill_id"] in struggling:
                rec["priority"] = max(rec.get("priority", 0.0), 1.2)

        # 5. 加权：偏好学科优先
        preferred_subjects = set(profile.subjects or [])
        if preferred_subjects:
            from app.domain.knowledge.prerequisites import SKILL_TO_SUBJECT

            for rec in recs:
                if SKILL_TO_SUBJECT.get(rec["skill_id"], "") in preferred_subjects:
                    rec["priority"] = rec.get("priority", 0.0) + 0.4

        # 6. 确定性排序
        recs.sort(key=lambda r: (-r.get("priority", 0.0), r["skill_id"]))

        # 7. 分类输出
        urgent: list[dict] = []
        building: list[dict] = []
        new_topic: list[dict] = []

        from app.domain.knowledge.checker import PrerequisiteChecker
        from app.domain.knowledge.prerequisites import SKILL_TO_SUBJECT
        from app.services.knowledge.knowledge_state import get_knowledge_state as _canonical_get_ks

        class _Adapter:
            async def get_knowledge_state(self, uid, sid):
                return await _canonical_get_ks(uid, sid)

        checker = PrerequisiteChecker(_Adapter())
        for rec in recs[:10]:
            sid = rec["skill_id"]
            entry = {
                "skill_id": sid,
                "label": checker._skill_display_name(sid),
                "level": rec.get("level", ""),
                "p_known": rec.get("p_known", 0),
                "subject": SKILL_TO_SUBJECT.get(sid, "未知"),
            }
            if sid in struggling or rec.get("level") == "接近掌握":
                urgent.append(entry)
            elif rec.get("level") == "发展中":
                building.append(entry)
            else:
                new_topic.append(entry)

        suggestion = _build_recommendation_suggestion(urgent, building, new_topic)

        return {
            "suggestion": suggestion,
            "urgent": urgent[:3],
            "building": building[:3],
            "new_topic": new_topic[:3],
        }
    except Exception as e:
        logger.warning("构建推荐失败: %s", e)
        return {"suggestion": "", "urgent": [], "building": [], "new_topic": []}


def _derive_fallback_skill_ids(
    profile, progress, existing_ids: set[str]
) -> list[str]:
    """当 cognitive 推荐不足时，从 Learner Model 推导兜底技能 ID。"""
    # 优先推荐困难知识点
    result = [
        sid for sid in (progress.struggling_skills or [])
        if sid and sid not in existing_ids
    ]
    if result:
        return result[:5]

    # 其次按学科偏好取入口知识点
    from app.domain.knowledge.prerequisites import SUBJECT_SKILLS

    preferred = profile.subjects or []
    if preferred:
        for subject in preferred:
            for sid in SUBJECT_SKILLS.get(subject, []):
                if sid not in existing_ids:
                    result.append(sid)
        if result:
            return result[:5]

    # 默认：所有学科入口
    for skills in SUBJECT_SKILLS.values():
        for sid in skills:
            if sid not in existing_ids:
                result.append(sid)
    return result[:5]


def _build_recommendation_suggestion(
    urgent: list[dict], building: list[dict], new_topic: list[dict]
) -> str:
    """生成个性化建议文案。"""
    if urgent:
        return f"建议优先突破「{urgent[0]['label']}」"
    if building:
        return f"继续推进「{building[0]['label']}」"
    if new_topic:
        subject = new_topic[0].get("subject")
        prefix = f"在{subject}方面，" if subject else ""
        return f"{prefix}可以从「{new_topic[0]['label']}」开始 🌱"
    return "完成一次学习后，我会更清楚今天该带你学什么。"


def _prioritize_plan_items(items: list[dict], user_id: str) -> list[dict]:
    """用 Learner Model 对计划项重新排序（S2.3）。

    排序优先级：
    1. 困难知识点（struggling_skills）置顶
    2. 偏好学科（profile.subjects）优先
    3. 保留原规划优先级
    4. skill_id 升序保证确定性
    """
    if not items:
        return items

    try:
        from shared.learner_model import get_learner_model

        engine = get_learner_model()
        profile = engine.get_or_create_profile(user_id)
        progress = engine.get_progress_summary(user_id)

        struggling = set(progress.struggling_skills or [])
        preferred_subjects = set(profile.subjects or [])

        def _sort_key(item: dict) -> tuple:
            sid = item.get("skill_id", "")
            subject = item.get("subject", "")
            original_priority = item.get("priority", 0) or 0
            return (
                0 if sid in struggling else 1,
                0 if subject in preferred_subjects else 1,
                -original_priority,
                sid,
            )

        return sorted(items, key=_sort_key)
    except Exception as e:
        logger.warning("Learner Model 排序 plan items 失败: %s", e)
        return items


async def build_dashboard(
    user_id: str,
    service: SecretaryService | None = None,
    activity_list_fn: Callable[[str], list[dict]] | None = None,
) -> dict:
    """聚合秘书仪表盘数据。

    Args:
        user_id: 用户 ID
        service: 可选 SecretaryService 实例
        activity_list_fn: 可选学习活动列表函数，签名 fn(user_id) -> list[dict]
                          用于避免 services 层反向依赖 api/learning_activity
    """
    now = time.time()
    cached = _dashboard_cache.get(user_id)
    if cached and (now - cached[0]) < _DASHBOARD_TTL:
        return cached[1]

    if service is None:
        service = SecretaryService()

    # 并行聚合独立数据源
    assess_task = service.quick_assess(user_id=user_id)
    plan_task = adaptive_planner.generate(user_id=user_id, reason="auto")

    loop = asyncio.get_event_loop()
    store = ProposalStore()
    overview = await loop.run_in_executor(None, get_practice_overview, user_id)
    proposals = await loop.run_in_executor(None, store.get_pending_proposals, user_id)
    confirmations = await loop.run_in_executor(None, list_planning_confirmations, user_id, "pending")

    activities: list[dict] = []
    if activity_list_fn is not None:
        try:
            activities = await loop.run_in_executor(None, activity_list_fn, user_id)
        except Exception as e:
            logger.warning("学习活动流读取失败: %s", e)

    assess = await assess_task
    plan_data = await plan_task

    # S2.3: 用 Learner Model 对今日计划排序，使推荐更个性化
    if isinstance(plan_data, dict) and isinstance(plan_data.get("plan"), dict):
        plan_data["plan"]["items"] = _prioritize_plan_items(
            plan_data["plan"].get("items", []), user_id
        )

    snapshot = {
        "cognitive_load": assess.get("cognitive_load", 0),
        "weak_count": assess.get("weak_count", 0),
        "stagnant_count": assess.get("stagnant_count", 0),
        "streak_days": assess.get("streak_days", 0),
        "summary": assess.get("summary", ""),
    }

    display_name = None
    try:
        from app.services.common import get_data_repo
        data = get_data_repo().load(user_id)
        display_name = data.profile.get("display_name") if hasattr(data, "profile") else None
    except Exception as e:
        logger.debug("读取用户显示名失败: %s", e)

    proposals_list = [p.model_dump() for p in proposals]
    result = {
        "greeting": _greeting(display_name),
        "date": datetime.now(timezone.utc).isoformat()[:10],
        "focus": _build_focus(plan_data),
        "stats": _build_stats(snapshot, overview),
        "pending": _build_pending(proposals_list, confirmations),
        "recommendations": _build_recommendations(user_id),
        "activities": activities,
    }

    _dashboard_cache[user_id] = (now, result)
    return result


def invalidate_dashboard_cache(user_id: str) -> None:
    """使指定用户的仪表盘缓存失效"""
    _dashboard_cache.pop(user_id, None)
