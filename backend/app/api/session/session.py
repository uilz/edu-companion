"""Session API — 学习会话的 REST 接口。

所有学习 Session 通过此 API 管理。
Conversation 是 Session 的内部实现，不暴露独立 API。
"""

import json
import time
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.domain.auth.dependencies import current_user_id
from app.domain.session import SessionService, SessionDomainError
from app.domain.growth.service import GrowthService
from app.application.di import get_session_service, get_growth_service
from app.infrastructure.db.database import get_db
from app.services.analysis.mission_analyzer import get_mission_analyzer
from app.services.analysis.understanding_analyzer import get_understanding_analyzer
from app.services.memory.learner_memory_updater import get_memory_updater
from app.domain.session.repository import get_session_repo


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/session", tags=["session"])


# ── 请求模型 ──

class CreateSessionRequest(BaseModel):
    title: str = ""
    focus: str = ""
    goal: str = ""
    estimated_minutes: int = 25
    recommendation_id: str | None = None
    mission_id: str | None = None
    source: str = ""  # "welcome_back" → S3.2 Mission 增强


class TransitionStageRequest(BaseModel):
    new_stage: str  # "intro" | "learn" | "practice" | "reflect"


class SetMissionRequest(BaseModel):
    title: str
    estimated_minutes: int = 25
    steps: list[dict] = []  # [{order, description, type}]


class CompleteSessionRequest(BaseModel):
    reflection: dict | None = None  # {content, key_takeaways, next_steps}


class MechanismEventItem(BaseModel):
    event: str
    timestamp: str
    seq: int
    payload: dict = {}


class MechanismEventsRequest(BaseModel):
    events: list[MechanismEventItem]


class AnalyzeUnderstandingRequest(BaseModel):
    """LI-02：用户写的理解 + 参考材料。"""
    user_text: str
    reference_text: str = ""
    mission_analysis_str: str = ""


# ── API 端点 ──

@router.post("", response_model=dict)
async def create_session(
    body: CreateSessionRequest,
    user_id: str = Depends(current_user_id),
    service: SessionService = Depends(get_session_service),
):
    """创建学习 Session。

    Today 页面点击"开始今天"时调用。
    关联 Conversation 作为内部交互组件。
    """
    if not user_id:
        raise HTTPException(status_code=401, detail="请先登录")

    try:
        result = await service.create_session(
            user_id=user_id,
            title=body.title,
            focus=body.focus,
            goal=body.goal,
            estimated_minutes=body.estimated_minutes,
            recommendation_id=body.recommendation_id,
            mission_id=body.mission_id,
            source=body.source,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/active", response_model=list[dict])
async def list_active_sessions(
    user_id: str = Depends(current_user_id),
    service: SessionService = Depends(get_session_service),
):
    """获取用户当前活跃的 Session 列表。"""
    if not user_id:
        return []
    return await service.list_active_sessions(user_id)


def _derive_topic_status(skill_gains: list[dict]) -> str | None:
    """从最新 GrowthRecord 的 skill_gains 推导「苹果果对你的理解」标签。

    取第一个技能的 mastery after 值，映射为中文状态标签。
    V1 规则：after >= 0.8 → 很稳 / >= 0.6 → 比较熟了 / >= 0.4 → 正在巩固
    / >= 0.2 → 刚开始 / < 0.2 → 新朋友 / 无数据 → None
    """
    if not skill_gains:
        return None
    first = skill_gains[0]
    after = first.get("after", 0)
    if after >= 0.8:
        return "很稳"
    if after >= 0.6:
        return "比较熟了"
    if after >= 0.4:
        return "正在巩固"
    if after >= 0.2:
        return "刚开始"
    return "新朋友"


@router.get("/continue", response_model=dict)
async def get_continue_context(
    user_id: str = Depends(current_user_id),
    session_service: SessionService = Depends(get_session_service),
    growth_service: GrowthService = Depends(get_growth_service),
):
    """获取「继续学习」上下文。

    优先级：
    1. 当前有活跃 Session → 继续当前学习（type=active_session）
    2. 最近有已完成的学习记录且不是今天：
       - days_ago >= 3 → 欢迎回来（type=welcome_back，S3.1）
       - days_ago 1-2  → 继续昨天（type=yesterday，S2.1）
    3. 否则 → 无继续上下文（type=none）
    """
    if not user_id:
        return {"type": "none"}

    # 1. 优先返回活跃 Session
    active = await session_service.list_active_sessions(user_id)
    if active:
        s = active[0]
        return {
            "type": "active_session",
            "session_id": s["id"],
            "title": s["title"] or "学习 Session",
            "stage": s["stage"],
        }

    # 2. 否则基于最新 GrowthRecord 恢复上下文
    latest = await growth_service.get_latest_growth(user_id)
    if not latest:
        return {"type": "none"}

    now_day = int(time.time() // 86400)
    record_day = int(latest.get("session_started_at", 0) // 86400)
    if record_day >= now_day:
        # 最新记录就是今天，不需要「继续」
        return {"type": "none"}

    days_ago = now_day - record_day

    key_takeaways = latest.get("key_takeaways", [])[:3]
    reflection_snippet = latest.get("reflection_snippet", "")
    title = latest.get("session_title") or "一次学习"

    skills = [
        g["skill"]
        for g in latest.get("skill_gains", [])
        if g.get("skill")
    ]

    topic_status = _derive_topic_status(latest.get("skill_gains", []))

    # S3.1: 间隔 >= 3 天 → 欢迎回来（不暴露天数）
    if days_ago >= 3:
        # 异常流程：只有一次 Session 且无有效记忆 → 不伪造熟悉感
        if not key_takeaways and not reflection_snippet:
            return {"type": "none"}

        return {
            "type": "welcome_back",
            "session_id": latest.get("session_id", ""),
            "title": title,
            "key_takeaways": key_takeaways,
            "reflection_snippet": reflection_snippet,
            "skills": skills,
            "topic_status": topic_status,
            "started_at": latest.get("session_started_at", 0),
        }

    # S2.1: 间隔 1-2 天 → 继续昨天
    if days_ago == 1:
        date_label = "昨天"
    else:
        date_label = "前天"

    return {
        "type": "yesterday",
        "session_id": latest.get("session_id", ""),
        "title": title,
        "key_takeaways": key_takeaways,
        "reflection_snippet": reflection_snippet,
        "skills": skills,
        "topic_status": topic_status,
        "date_label": date_label,
        "started_at": latest.get("session_started_at", 0),
    }


@router.get("/recent", response_model=list[dict])
async def list_recent_sessions(
    user_id: str = Depends(current_user_id),
    service: SessionService = Depends(get_session_service),
    limit: int = 10,
):
    """获取用户最近的 Session 列表。"""
    if not user_id:
        return []
    return await service.list_recent_sessions(user_id, limit)


@router.get("/{session_id}", response_model=dict)
async def get_session(
    session_id: str,
    user_id: str = Depends(current_user_id),
    service: SessionService = Depends(get_session_service),
):
    """获取 Session 当前状态。"""
    result = await service.get_session(session_id)
    if not result:
        raise HTTPException(status_code=404, detail="Session not found")
    return result


@router.patch("/{session_id}/stage", response_model=dict)
async def transition_stage(
    session_id: str,
    body: TransitionStageRequest,
    user_id: str = Depends(current_user_id),
    service: SessionService = Depends(get_session_service),
):
    """Session 阶段转移 (intro → learn → practice → reflect)。"""
    if not user_id:
        raise HTTPException(status_code=401, detail="请先登录")

    try:
        return await service.transition_stage(session_id, body.new_stage)
    except SessionDomainError as e:
        raise HTTPException(status_code=409, detail=str(e))


# ── Mechanism Events（EXP-04 Instrumentation） ──

@router.post("/{session_id}/events", response_model=dict)
async def record_mechanism_events(
    session_id: str,
    body: MechanismEventsRequest,
    user_id: str = Depends(current_user_id),
):
    """记录 EXP-04 机制事件。

    用于验证 Safety → Search → Self-resolution 链路。
    不是产品数据、不是运营指标。
    """
    if not user_id:
        raise HTTPException(status_code=401, detail="请先登录")

    db = get_db()
    try:
        # 确保表存在
        db.execute("""
            CREATE TABLE IF NOT EXISTS mechanism_events (
                id SERIAL PRIMARY KEY,
                session_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                event TEXT NOT NULL,
                seq INTEGER NOT NULL,
                payload JSONB DEFAULT '{}',
                created_at TEXT NOT NULL
            )
        """)
        db.execute("""
            CREATE INDEX IF NOT EXISTS idx_mech_events_session
            ON mechanism_events(session_id)
        """)
        db.execute("""
            CREATE INDEX IF NOT EXISTS idx_mech_events_event
            ON mechanism_events(event)
        """)

        for evt in body.events:
            db.execute(
                """
                INSERT INTO mechanism_events (session_id, user_id, event, seq, payload, created_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                [
                    session_id,
                    user_id,
                    evt.event,
                    evt.seq,
                    json.dumps(evt.payload, ensure_ascii=False),
                    evt.timestamp,
                ],
            )
        db.commit()
        logger.debug(
            f"[mechanism] Recorded {len(body.events)} events for session {session_id}"
        )
        return {"recorded": len(body.events)}
    except Exception as e:
        db.rollback()
        logger.warning(f"[mechanism] Failed to record events: {e}")
        # 不抛出错误 — 事件采集失败不影响 Session 主流程
        return {"recorded": 0, "error": str(e)}


@router.put("/{session_id}/mission", response_model=dict)
async def set_mission(
    session_id: str,
    body: SetMissionRequest,
    user_id: str = Depends(current_user_id),
    service: SessionService = Depends(get_session_service),
):
    """设置 Session 的任务分解（intro 阶段调用）。"""
    if not user_id:
        raise HTTPException(status_code=401, detail="请先登录")

    try:
        return await service.set_mission(
            session_id=session_id,
            title=body.title,
            estimated_minutes=body.estimated_minutes,
            steps=body.steps,
        )
    except SessionDomainError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/{session_id}/complete", response_model=dict)
async def complete_session(
    session_id: str,
    body: CompleteSessionRequest | None = None,
    user_id: str = Depends(current_user_id),
    service: SessionService = Depends(get_session_service),
):
    """完成 Session。

    发布 LearningSessionCompleted 事件，Growth Engine 监听并生成 GrowthSummary。
    """
    if not user_id:
        raise HTTPException(status_code=401, detail="请先登录")

    try:
        reflection = body.reflection if body else None
        return await service.complete_session(session_id, reflection)
    except SessionDomainError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/{session_id}/analyze-mission", response_model=dict)
async def analyze_mission(
    session_id: str,
    user_id: str = Depends(current_user_id),
):
    """LI-01: 分析 Mission，输出结构化的 MissionAnalysis。

    在 Session 创建后、ENTER 屏渲染前调用。
    结果存储在 session.mission_analysis 中，Assembler 会加载。
    """
    if not user_id:
        raise HTTPException(status_code=401, detail="请先登录")

    # 1. 获取 Session
    repo = get_session_repo()
    session = repo.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    title = session.title or ""
    if session.mission and session.mission.title:
        title = session.mission.title

    if not title:
        raise HTTPException(status_code=400, detail="Session has no mission title")

    # 2. 加载上次学习的 GrowthRecord（G6: 跨 Session Memory）
    previous_context = ""
    try:
        from app.domain.growth import get_growth_repo
        growth_repo = get_growth_repo()
        last_record = growth_repo.get_latest(user_id)
        if last_record:
            parts = []
            if last_record.summary:
                parts.append(f"总结：{last_record.summary[:200]}")
            if last_record.key_takeaways:
                parts.append(f"收获：{'；'.join(last_record.key_takeaways[:3])}")
            if last_record.reflection_snippet:
                parts.append(f"反思：{last_record.reflection_snippet[:200]}")
            if parts:
                previous_context = "\n".join(parts)
    except Exception:
        logger.debug("Failed to load previous growth record", exc_info=True)

    # 3. 调用 MissionAnalyzer
    analyzer = get_mission_analyzer()
    analysis = await analyzer.analyze(
        mission_title=title,
        previous_growth_context=previous_context,
    )

    # 4. 持久化
    if analysis is not None:
        session.mission_analysis = analysis.model_dump(mode="json")
        repo.save(session)
        return {"status": "ok", "analysis": session.mission_analysis}
    else:
        # LLM 失败或解析失败 → mission_analysis 保持 null
        logger.warning("Mission analysis failed for session %s, keeping null", session_id)
        return {"status": "failed", "analysis": None}


@router.post("/{session_id}/analyze-understanding", response_model=dict)
async def analyze_understanding(
    session_id: str,
    body: AnalyzeUnderstandingRequest,
    user_id: str = Depends(current_user_id),
):
    """LI-02: 分析用户写的理解，输出 UnderstandingAnalysis。

    用户在 SELF_VALIDATION 写完理解后调用。
    """
    if not user_id:
        raise HTTPException(status_code=401, detail="请先登录")

    if not body.user_text.strip():
        return {"status": "ok", "analysis": None, "reason": "empty_text"}

    # 1. 获取 Session
    repo = get_session_repo()
    session = repo.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    title = session.title or ""
    if session.mission and session.mission.title:
        title = session.mission.title

    ma_str = body.mission_analysis_str
    # fallback: 从 session 取已缓存的 MissionAnalysis
    if not ma_str and session.mission_analysis:
        ma_str = json.dumps(session.mission_analysis, ensure_ascii=False, indent=2)

    # 2. 调用 UnderstandingAnalyzer
    analyzer = get_understanding_analyzer()
    analysis = await analyzer.analyze(
        mission_title=title,
        mission_analysis_str=ma_str,
        user_text=body.user_text,
        reference_text=body.reference_text,
    )

    # 3. 持久化并返回
    if analysis is not None:
        analysis_dict = analysis.model_dump(mode="json")
        session.understanding_analysis = analysis_dict
        repo.save(session)

        # 提取 guidance_question
        guidance = analysis_dict.get("guidance_question")
        return {
            "status": "ok",
            "analysis": analysis_dict,
            "guidance_question": guidance,
        }
    else:
        logger.warning("Understanding analysis failed for session %s", session_id)
        return {"status": "failed", "analysis": None}


class UpdateMemoryRequest(BaseModel):
    """LI-03：触发 Learner Memory 更新。"""
    reflection: dict | None = None  # {content, key_takeaways}


class ToolStateUpdateRequest(BaseModel):
    """EXP-04：工具托盘状态更新（增量合并）。"""
    tool_state: dict = {}


class SessionFlashcardCreateRequest(BaseModel):
    """EXP-04：在 Session 内创建 FlashCard。"""
    front_text: str
    back_text: str = ""
    type: int = 1
    tags: list[str] = []
    linked_node_ids: list[str] = []
    back_context: str = ""


@router.post("/{session_id}/update-memory", response_model=dict)
async def update_learner_memory(
    session_id: str,
    body: UpdateMemoryRequest | None = None,
    user_id: str = Depends(current_user_id),
):
    """LI-03: 将 Session 中的观察结果持久化到 BKT + GrowthRecord。

    在 Session 完成后调用。
    """
    if not user_id:
        raise HTTPException(status_code=401, detail="请先登录")

    repo = get_session_repo()
    session = repo.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # 读取 LI-02 产出的 learner_delta
    learner_delta = None
    if session.understanding_analysis:
        try:
            from app.domain.session.runtime_context import LearnerDelta, UnderstandingAnalysis
            ua = UnderstandingAnalysis(**session.understanding_analysis)
            learner_delta = ua.learner_delta
        except Exception:
            logger.warning("Failed to parse understanding_analysis for session %s", session_id)

    # 获取 reflection
    reflection = body.reflection if body and body.reflection else None
    if not reflection and session.reflection_text:
        reflection = {
            "content": session.reflection_text,
            "key_takeaways": session.reflection_takeaways,
        }

    # 调用 LI-03
    updater = get_memory_updater()
    result = await updater.apply_learner_delta(
        user_id=user_id,
        session_id=session_id,
        session_title=session.title or "",
        session_started_at=session.started_at,
        learner_delta=learner_delta,
        reflection=reflection,
    )

    return {
        "status": "ok",
        "result": result,
    }


@router.post("/{session_id}/cancel", response_model=dict)
async def cancel_session(
    session_id: str,
    user_id: str = Depends(current_user_id),
    service: SessionService = Depends(get_session_service),
):
    """取消 Session。"""
    if not user_id:
        raise HTTPException(status_code=401, detail="请先登录")

    try:
        return await service.cancel_session(session_id)
    except SessionDomainError as e:
        raise HTTPException(status_code=409, detail=str(e))


# ════════════════════════════════════════════════════════════════════
# EXP-04 工具托盘 / 闪卡打通
# ════════════════════════════════════════════════════════════════════

@router.get("/{session_id}/tool-state", response_model=dict)
async def get_tool_state(
    session_id: str,
    user_id: str = Depends(current_user_id),
    service: SessionService = Depends(get_session_service),
):
    """获取 Session 工具托盘状态。"""
    if not user_id:
        raise HTTPException(status_code=401, detail="请先登录")

    try:
        return {"session_id": session_id, "tool_state": service.get_tool_state(session_id)}
    except SessionDomainError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{session_id}/tool-state", response_model=dict)
async def update_tool_state(
    session_id: str,
    body: ToolStateUpdateRequest,
    user_id: str = Depends(current_user_id),
    service: SessionService = Depends(get_session_service),
):
    """更新 Session 工具托盘状态（增量合并）。"""
    if not user_id:
        raise HTTPException(status_code=401, detail="请先登录")

    try:
        merged = service.update_tool_state(session_id, body.tool_state)
        return {"session_id": session_id, "tool_state": merged}
    except SessionDomainError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{session_id}/flashcards", response_model=dict)
async def create_session_flashcard(
    session_id: str,
    body: SessionFlashcardCreateRequest,
    user_id: str = Depends(current_user_id),
    service: SessionService = Depends(get_session_service),
):
    """在 Session 内创建 FlashCard 并建立关联。"""
    if not user_id:
        raise HTTPException(status_code=401, detail="请先登录")

    if not body.front_text.strip():
        raise HTTPException(status_code=400, detail="front_text 不能为空")

    try:
        return service.add_session_flashcard(session_id, body.model_dump())
    except SessionDomainError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
