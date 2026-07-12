"""秘书系统 API 端点

提供: 秘书偏好管理、提案查询/采纳/拒绝/暂缓、快照获取、简报、LLM 提案生成
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.domain.auth.dependencies import current_user_id
from app.domain.secretary.secretary_service import SecretaryService
from app.domain.secretary.models import Proposal, ScopeSpec, SecretaryPrefs, UserOrchestrationProfile
from app.infrastructure.db.proposal_store import ProposalStore
from app.infrastructure.db.silent_task_store import SilentTaskStore
from app.infrastructure.db.user_profile_store import UserOrchestrationProfileStore

# Dashboard aggregation imports
from app.services.secretary.dashboard import build_dashboard as _build_dashboard

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/secretary", tags=["秘书系统"])


# ── 辅助函数 ──


def _load_prefs(user_id: str) -> dict:
    """加载用户偏好（从 DataRepository 读取）

    默认值与 SecretaryPrefs 模型保持一致 (Task #83 B-22):
      enabled_extensions = ["review_reminder", "fatigue_manager", "daily_brief"]
    """
    from app.services.common import get_data_repo
    data = get_data_repo().load(user_id)
    return data.secretary_prefs or {
        "enabled_extensions": [
            "review_reminder", "fatigue_manager", "daily_brief"
        ],
        "quiet_hours_start": "22:00",
        "quiet_hours_end": "08:00",
        "max_proactive_per_day": 5,
    }


def _save_prefs(user_id: str, prefs: dict) -> None:
    """保存用户偏好（通过 DataRepository 持久化）"""
    from app.services.common import get_data_repo
    data = get_data_repo().load(user_id)
    data.secretary_prefs = prefs
    get_data_repo().save(user_id, data)


def _get_proposal_by_id(store: ProposalStore, proposal_id: str, user_id: str) -> Proposal | None:
    """通过 ID 获取提案对象"""
    try:
        db = store._get_db()
        row = db.fetchone(
            "SELECT * FROM secretary_proposals WHERE id = %s AND user_id = %s",
            (proposal_id, user_id),
        )
        if row:
            from app.domain.secretary.models import Proposal

            # created_at: DB 返回 datetime → 转为 float 时间戳 (匹配 Proposal 模型)
            created_at_raw = row.get("created_at")
            if created_at_raw is None:
                created_at_val = time.time()
            elif isinstance(created_at_raw, datetime):
                created_at_val = created_at_raw.timestamp()
            else:
                created_at_val = float(created_at_raw)

            # expires_at: 同上
            expires_at_raw = row.get("expires_at")
            if expires_at_raw is None:
                expires_at_val = None
            elif isinstance(expires_at_raw, datetime):
                expires_at_val = expires_at_raw.timestamp()
            else:
                expires_at_val = float(expires_at_raw)

            # payload 可能是 JSON 字符串或已解析的 dict
            payload_raw = row.get("payload")
            if isinstance(payload_raw, str):
                try:
                    payload_val = json.loads(payload_raw)
                except (json.JSONDecodeError, TypeError):
                    payload_val = {}
            elif payload_raw is None:
                payload_val = {}
            else:
                payload_val = payload_raw

            return Proposal(
                id=row["id"],
                emoji=row.get("emoji", "💡") or "💡",
                title=row["title"],
                description=row.get("description", "") or "",
                action_type=row["action_type"],
                payload=payload_val,
                priority=row.get("priority", 3) or 3,
                generated_by=row.get("generated_by", "") or "",
                overrideable=row.get("overrideable", True),
                created_at=created_at_val,
                expires_at=expires_at_val,
            )
    except Exception as e:
        logger.debug("获取提案失败: %s", e)
    return None


async def _ensure_db_schema(store: ProposalStore):
    """确保数据库 secretary_proposals 表存在 (Task #83 B-1/B-2 修复)

    委托给 ProposalStore._ensure_table() 静态方法, 统一 schema 入口。
    """
    try:
        ProposalStore._ensure_table()
    except Exception as e:
        logger.debug("_ensure_table 调用失败 (表可能已存在): %s", e)


# ── 依赖 ──


def _get_service() -> SecretaryService:
    return SecretaryService()


def _get_store() -> ProposalStore:
    return ProposalStore()


def _get_silent_task_store() -> SilentTaskStore:
    return SilentTaskStore()


def _get_profile_store() -> UserOrchestrationProfileStore:
    return UserOrchestrationProfileStore()


# ═══════════════════════════════════════════
# 偏好
# ═══════════════════════════════════════════


@router.get("/preferences")
async def get_preferences(
    user_id: str = Depends(current_user_id),
) -> dict:
    """获取用户秘书偏好"""
    prefs = _load_prefs(user_id)
    return {
        "enabled_extensions": prefs.get("enabled_extensions", []),
        "quiet_hours_start": prefs.get("quiet_hours_start", "22:00"),
        "quiet_hours_end": prefs.get("quiet_hours_end", "08:00"),
        "max_proactive_per_day": prefs.get("max_proactive_per_day", 5),
        "check_interval": prefs.get("check_interval", None),  # Task #83 B-3
    }


# ═══════════════════════════════════════════
# 用户编排画像
# ═══════════════════════════════════════════


@router.get("/profile")
async def get_profile(
    user_id: str = Depends(current_user_id),
    store: UserOrchestrationProfileStore = Depends(_get_profile_store),
) -> dict:
    """获取用户编排画像"""
    profile = store.get_profile(user_id)
    return profile.model_dump()


@router.put("/profile")
async def update_profile(
    body: dict,
    user_id: str = Depends(current_user_id),
    store: UserOrchestrationProfileStore = Depends(_get_profile_store),
) -> dict:
    """更新用户编排画像（仅允许更新白名单字段）"""
    allowed = {
        "trust_score", "fatigue_score", "proactive_quota_today",
        "enabled_modules", "quiet_hours_start", "quiet_hours_end",
    }
    profile = store.get_profile(user_id)
    for key, val in body.items():
        if key in allowed and hasattr(profile, key):
            setattr(profile, key, val)
    store.save_profile(profile)
    return profile.model_dump()


# ═══════════════════════════════════════════
# 诊断与快照
# ═══════════════════════════════════════════


# ── 短期内存缓存 (Task #83 B-18) ──
_snapshot_cache: dict[str, tuple[float, dict]] = {}
_SNAPSHOT_TTL = 30.0  # 30s


@router.get("/snapshot")
async def get_snapshot(
    user_id: str = Depends(current_user_id),
    service: SecretaryService = Depends(_get_service),
) -> dict:
    """获取当前学习状态快照 (Task #83 B-18: 30s 内存缓存)"""
    now = time.time()
    cached = _snapshot_cache.get(user_id)
    if cached and (now - cached[0]) < _SNAPSHOT_TTL:
        return cached[1]
    assess = await service.quick_assess(user_id=user_id)
    result = {
        "cognitive_load": assess.get("cognitive_load", 0),
        "weak_count": assess.get("weak_count", 0),
        "stagnant_count": assess.get("stagnant_count", 0),
        "streak_days": assess.get("streak_days", 0),
        "summary": assess.get("summary", ""),
    }
    _snapshot_cache[user_id] = (now, result)
    return result


@router.get("/context")
async def get_conversation_context(
    conv_id: str | None = None,
    user_id: str = Depends(current_user_id),
    service: SecretaryService = Depends(_get_service),
) -> dict:
    """获取注入对话壳的上下文包（同时发布 ConversationContextInjected 事件）"""
    from app.application.di import get_event_bus
    try:
        event_bus = get_event_bus()
    except Exception:
        event_bus = None
    return await service.get_conversation_context(user_id=user_id, conv_id=conv_id, event_bus=event_bus)


# ═══════════════════════════════════════════
# 提案 CRUD
# ═══════════════════════════════════════════


@router.get("/proposals/pending")
async def get_pending_proposals(
    user_id: str = Depends(current_user_id),
    source_module: str | None = None,
    action_type: str | None = None,
    priority_min: int | None = None,
    priority_max: int | None = None,
    search: str | None = None,
    store: ProposalStore = Depends(_get_store),
) -> list[dict]:
    """获取待处理提案（支持筛选参数）"""
    await _ensure_db_schema(store)
    proposals = store.get_pending_proposals(
        user_id=user_id,
        source_module=source_module,
        action_type=action_type,
        priority_min=priority_min,
        priority_max=priority_max,
        search=search,
    )
    return [p.model_dump() for p in proposals]


@router.get("/proposals/history")
async def get_proposal_history(
    user_id: str = Depends(current_user_id),
    days: int = 7,
    source_module: str | None = None,
    action_type: str | None = None,
    page: int = 1,
    page_size: int = 50,
    store: ProposalStore = Depends(_get_store),
) -> list[dict]:
    """获取提案历史（支持筛选与分页）"""
    return store.get_history(
        user_id=user_id, days=days,
        source_module=source_module, action_type=action_type,
        page=page, page_size=page_size,
    )


@router.post("/proposals/{proposal_id}/accept")
async def accept_proposal(
    proposal_id: str,
    user_id: str = Depends(current_user_id),
    store: ProposalStore = Depends(_get_store),
) -> dict:
    """采纳提案 — 更新状态 + 触发对应系统动作"""
    # 先获取提案详情
    try:
        proposal = _get_proposal_by_id(store, proposal_id, user_id)
        if not proposal:
            raise HTTPException(404, "提案不存在或已处理")
    except HTTPException:
        raise
    except Exception as e:
        logger.warning("获取提案详情失败: %s", e)
        proposal = None

    ok = store.update_status(proposal_id, "accepted", user_id, {"action": "user_accepted", "timestamp": time.time()})
    if not ok:
        raise HTTPException(404, "提案不存在或已处理")

    from app.services.secretary.proposal_actions import execute_accepted_action
    return await execute_accepted_action(proposal, user_id)


@router.post("/proposals/{proposal_id}/present")
async def present_proposal(
    proposal_id: str,
    user_id: str = Depends(current_user_id),
    store: ProposalStore = Depends(_get_store),
) -> dict:
    """将提案标记为已展示（pending → presented）"""
    ok = store.mark_presented(proposal_id, user_id)
    if not ok:
        raise HTTPException(404, "提案不存在或状态不可展示")
    return {"status": "presented"}


@router.post("/proposals/{proposal_id}/dismiss")
async def dismiss_proposal(
    proposal_id: str,
    user_id: str = Depends(current_user_id),
    reason: str = "",
    store: ProposalStore = Depends(_get_store),
) -> dict:
    """忽略提案 — 更新状态 + 记录关系记忆"""
    ok = store.update_status(proposal_id, "dismissed", user_id, {"action": "user_dismissed", "reason": reason})
    if not ok:
        raise HTTPException(404, "提案不存在或已处理")

    proposal = _get_proposal_by_id(store, proposal_id, user_id)
    from app.services.secretary.proposal_actions import record_dismiss
    policy_result = await record_dismiss(proposal, user_id)
    return policy_result if policy_result else {"status": "dismissed"}


# ═══════════════════════════════════════════
# 新操作: 延后 / 删除 / 恢复 / 批量
# ═══════════════════════════════════════════


@router.post("/proposals/{proposal_id}/snooze")
async def snooze_proposal(
    proposal_id: str,
    user_id: str = Depends(current_user_id),
    store: ProposalStore = Depends(_get_store),
    until: float | None = None,
) -> dict:
    """延后提案 — 状态设为 snoozed，可选指定唤醒时间"""
    ok = store.snooze_proposal(proposal_id, user_id, until_timestamp=until)
    if not ok:
        raise HTTPException(404, "提案不存在")
    # WS 已移除，跳过广播（由 TokenBuffer 等机制取代）
    return {"status": "snoozed"}


@router.post("/proposals/{proposal_id}/delete")
async def delete_proposal(
    proposal_id: str,
    user_id: str = Depends(current_user_id),
    store: ProposalStore = Depends(_get_store),
) -> dict:
    """删除提案 — 状态设为 deleted"""
    ok = store.delete_proposal(proposal_id, user_id)
    if not ok:
        raise HTTPException(404, "提案不存在")
    # WS 已移除，跳过广播（由 TokenBuffer 等机制取代）
    return {"status": "deleted"}


@router.post("/proposals/{proposal_id}/restore")
async def restore_proposal(
    proposal_id: str,
    user_id: str = Depends(current_user_id),
    store: ProposalStore = Depends(_get_store),
) -> dict:
    """恢复提案 — snoozed/deleted → pending"""
    ok = store.restore_proposal(proposal_id, user_id)
    if not ok:
        raise HTTPException(404, "提案不存在或状态不可恢复")
    # WS 已移除，跳过广播（由 TokenBuffer 等机制取代）
    return {"status": "restored"}


@router.post("/proposals/batch-accept")
async def batch_accept_proposals(
    ids: list[str],
    user_id: str = Depends(current_user_id),
    store: ProposalStore = Depends(_get_store),
) -> dict:
    """批量采纳提案"""
    count = store.batch_update_status(ids, "accepted", user_id)
    # WS 已移除，跳过广播（由 TokenBuffer 等机制取代）
    return {"status": "ok", "count": count}


@router.post("/proposals/batch-dismiss")
async def batch_dismiss_proposals(
    ids: list[str],
    user_id: str = Depends(current_user_id),
    store: ProposalStore = Depends(_get_store),
) -> dict:
    """批量忽略提案"""
    count = store.batch_update_status(ids, "dismissed", user_id)
    # WS 已移除，跳过广播（由 TokenBuffer 等机制取代）
    return {"status": "ok", "count": count}


# ═══════════════════════════════════════════
# 静默后台任务
# ═══════════════════════════════════════════


@router.get("/silent-tasks")
async def get_silent_tasks(
    user_id: str = Depends(current_user_id),
    status: str | None = None,
    task_type: str | None = None,
    limit: int = 50,
    store: SilentTaskStore = Depends(_get_silent_task_store),
) -> list[dict]:
    """获取静默任务列表"""
    tasks = store.list_tasks(
        user_id=user_id,
        status=status,
        task_type=task_type,
        limit=limit,
    )
    return [t.model_dump() for t in tasks]


@router.get("/silent-tasks/{task_id}")
async def get_silent_task(
    task_id: str,
    user_id: str = Depends(current_user_id),
    store: SilentTaskStore = Depends(_get_silent_task_store),
) -> dict:
    """获取单个静默任务"""
    task = store.get_task(task_id, user_id=user_id)
    if not task:
        raise HTTPException(404, "任务不存在")
    return task.model_dump()


@router.post("/silent-tasks/{task_id}/run")
async def run_silent_task(
    task_id: str,
    user_id: str = Depends(current_user_id),
    store: SilentTaskStore = Depends(_get_silent_task_store),
) -> dict:
    """手动触发执行单个静默任务"""
    task = store.get_task(task_id, user_id=user_id)
    if not task:
        raise HTTPException(404, "任务不存在")

    from app.domain.secretary.engines.silent_task_manager import silent_task_manager
    try:
        completed = await silent_task_manager.execute(task)
        return completed.model_dump()
    except Exception as e:
        logger.warning("手动执行静默任务失败: %s", e)
        raise HTTPException(500, f"任务执行失败: {e}")


@router.post("/silent-tasks/run-pending")
async def run_pending_silent_tasks(
    user_id: str = Depends(current_user_id),
    task_type: str | None = None,
    max_tasks: int = 5,
) -> dict:
    """手动触发执行所有 pending 静默任务"""
    from app.domain.secretary.engines.silent_task_manager import silent_task_manager
    try:
        completed = await silent_task_manager.run_pending(
            user_id=user_id,
            task_type=task_type,
            max_tasks=min(max_tasks, 10),
        )
        return {"status": "ok", "count": len(completed), "tasks": [t.model_dump() for t in completed]}
    except Exception as e:
        logger.warning("批量执行静默任务失败: %s", e)
        raise HTTPException(500, f"批量执行失败: {e}")


# ═══════════════════════════════════════════
# LLM 生成
# ═══════════════════════════════════════════


@router.post("/generate-llm-proposals")
async def generate_llm_proposals(
    user_id: str = Depends(current_user_id),
    service: SecretaryService = Depends(_get_service),
    store: ProposalStore = Depends(_get_store),
) -> list[dict]:
    """使用 LLM 生成润色提案 (Task #83 B-15/B-23: try/except 包裹整体)"""
    try:
        report = await service.diagnose(user_id=user_id)
    except Exception as e:
        logger.warning("诊断失败，返回空列表: %s", e)
        return []

    from app.domain.secretary.engines.llm_proposal_generator import LLMProposalGenerator
    llm = None
    try:
        from app.infrastructure.llm.llm_service import llm_service
        llm = llm_service
    except Exception as e:
        logger.warning("LLM service unavailable, proceeding without LLM: %s", e)

    try:
        gen = LLMProposalGenerator(llm_service=llm)
        proposals = await gen.generate_suggestion(report, max_proposals=3)
    except Exception as e:
        logger.warning("LLM 提案生成失败，返回空列表: %s", e)
        return []

    for p in proposals:
        try:
            store.save_proposal(p, user_id=user_id, session_id="api")
        except Exception as e:
            logger.debug("提案保存失败: %s", e)

    return [p.model_dump() for p in proposals]


# ═══════════════════════════════════════════
# 模块管理
# ═══════════════════════════════════════════


@router.get("/modules")
async def list_modules(
    user_id: str = Depends(current_user_id),
) -> list[dict]:
    """列出所有秘书模块及其状态"""
    from app.domain.secretary.engines.module_registry import module_registry
    if not module_registry._modules:
        module_registry.discover_builtin()
    modules = module_registry.list_modules()
    # 恢复用户偏好覆盖
    try:
        prefs = _load_prefs(user_id)
        if prefs.get("enabled_extensions"):
            module_registry.apply_prefs(prefs["enabled_extensions"])
            modules = module_registry.list_modules()
    except Exception as e:
        logger.warning("Failed to load/apply user prefs for %s: %s", user_id, e)
    return modules


@router.post("/modules/toggle")
async def toggle_module(
    name: str,
    enabled: bool,
    user_id: str = Depends(current_user_id),
) -> dict:
    """启用/禁用指定模块"""
    from app.domain.secretary.engines.module_registry import module_registry
    if not module_registry._modules:
        module_registry.discover_builtin()

    if enabled:
        module_registry.enable(name)
    else:
        module_registry.disable(name)

    # 持久化偏好
    prefs = _load_prefs(user_id)
    prefs["enabled_extensions"] = module_registry.to_prefs_list()
    _save_prefs(user_id, prefs)

    return {
        "status": "ok",
        "module": name,
        "enabled": enabled,
    }


# ═══════════════════════════════════════════
# 主动检查器控制
# ═══════════════════════════════════════════


@router.post("/checker/run")
async def run_checker(
    user_id: str = Depends(current_user_id),
) -> dict:
    """手动触发一次主动检查"""
    from app.domain.secretary.engines.active_checker import active_checker
    try:
        findings = await active_checker.run_check(user_id=user_id)
        return {
            "status": "ok",
            "modules_run": findings.get("modules_run", 0),
            "proposals_generated": findings.get("proposals_generated", 0),
            "reasons": findings.get("reasons", []),
        }
    except Exception as e:
        logger.warning("主动检查执行失败: %s", e)
        return {"status": "error", "detail": str(e)}


@router.get("/checker/status")
async def get_checker_status(
    user_id: str = Depends(current_user_id),
) -> dict:
    """获取主动检查器状态"""
    from app.domain.secretary.engines.active_checker import active_checker
    from app.domain.secretary.engines.module_registry import module_registry

    modules = module_registry.list_modules()
    return {
        "running": active_checker._running if hasattr(active_checker, '_running') else False,
        "check_interval": active_checker._check_interval if hasattr(active_checker, '_check_interval') else 600,
        "modules": modules,
        "module_count": len(modules),
        "enabled_modules": [m["name"] for m in modules if m.get("enabled")],
    }


@router.post("/checker/configure")
async def configure_checker(
    body: dict,
    user_id: str = Depends(current_user_id),
) -> dict:
    """配置主动检查器

    Body:
        check_interval: int | None — 检查间隔（秒），默认 600
        enable_modules: list[str] | None — 启用模块列表

    Task #83 B-3: 持久化 check_interval 到 user_settings.secretary_prefs
    """
    from app.domain.secretary.engines.active_checker import active_checker
    from app.domain.secretary.engines.module_registry import module_registry

    interval = body.get("check_interval")
    if interval and isinstance(interval, (int, float)) and 60 <= interval <= 3600:
        active_checker._check_interval = int(interval)
        # 持久化偏好 (Task #83 B-3)
        try:
            prefs = _load_prefs(user_id)
            prefs["check_interval"] = int(interval)
            _save_prefs(user_id, prefs)
        except Exception as e:
            logger.debug("持久化 check_interval 失败: %s", e)
        logger.info("主动检查间隔已更新: %ds", interval)

    enable_modules = body.get("enable_modules")
    if enable_modules and isinstance(enable_modules, list):
        for name in module_registry._modules:
            enabled = name in enable_modules
            module_registry._enabled[name] = enabled
        # 持久化 enable_modules
        try:
            prefs = _load_prefs(user_id)
            prefs["enabled_extensions"] = list(enable_modules)
            _save_prefs(user_id, prefs)
        except Exception as e:
            logger.debug("持久化 enabled_extensions 失败: %s", e)

    return {
        "status": "ok",
        "check_interval": active_checker._check_interval,
        "enabled_modules": [n for n, e in module_registry._enabled.items() if e],
    }


# ═══════════════════════════════════════════
# 冷启动引导
# ═══════════════════════════════════════════


@router.get("/onboarding")
async def get_onboarding_status(
    user_id: str = Depends(current_user_id),
) -> dict:
    """获取冷启动状态与引导信息 (Task #83 B-5 / Task #168)"""
    from app.services.secretary.onboarding import get_onboarding_status as _get_onboarding_status
    return await _get_onboarding_status(user_id)


# ═══════════════════════════════════════════
# 执行结果回传
# ═══════════════════════════════════════════


@router.post("/proposals/{proposal_id}/execution-result")
async def report_execution_result(
    proposal_id: str,
    body: dict,
    user_id: str = Depends(current_user_id),
    store: ProposalStore = Depends(_get_store),
) -> dict:
    """用户完成提案动作后回传执行结果

    Body:
        success: bool
        message: str
        details: str | None
        completed_at: int (epoch ms)
    """
    from app.services.secretary.proposal_actions import build_execution_result_payload
    try:
        result_payload = build_execution_result_payload(body)
        # 直接更新 metadata 中的 execution_result（顶级字段）
        db = store._get_db()
        db.execute(
            "UPDATE secretary_proposals SET "
            "metadata = COALESCE(metadata, '{}'::jsonb) || %s::jsonb "
            "WHERE id = %s AND user_id = %s",
            (json.dumps({"execution_result": result_payload}), proposal_id, user_id),
        )
        logger.info(
            "提案执行结果回传: proposal=%s user=%s success=%s",
            proposal_id, user_id, result_payload["success"],
        )
        return {"status": "ok", "result": result_payload}
    except Exception as e:
        logger.warning("执行结果回传失败: %s", e)
        return {"status": "error", "detail": str(e)}


# ═══════════════════════════════════════════
# 数据导出/删除 (遗忘权)
# ═══════════════════════════════════════════


@router.get("/data/export")
async def export_secretary_data(user_id: str = Depends(current_user_id)) -> dict:
    """导出所有秘书相关个人数据 (Task #168)"""
    from app.services.secretary.data_lifecycle import export_secretary_data as _export_secretary_data
    return _export_secretary_data(user_id)


@router.delete("/data/delete")
async def delete_secretary_data(user_id: str = Depends(current_user_id)) -> dict:
    """删除所有秘书相关个人数据 (遗忘权) (Task #168)"""
    from app.services.secretary.data_lifecycle import delete_secretary_data as _delete_secretary_data
    return _delete_secretary_data(user_id)


# ══════════════════════════════════════════════════════════════
#  Agent 助手 — 意图路由 + 对话
# ══════════════════════════════════════════════════════════════

from pydantic import BaseModel, Field


# ══════════════════════════════════════════════════════════════
#  事件流 — EventSystem v2
# ══════════════════════════════════════════════════════════════


@router.get("/events/stream")
async def get_event_stream(
    user_id: str = Depends(current_user_id),
    stream_type: str = "",
    stream_id: str = "",
    event_type: str = "",
    limit: int = 50,
    since: float = 0.0,
    until: float = 0.0,
) -> list[dict]:
    """获取用户事件流

    支持按 stream_type, stream_id, event_type 过滤，
    按时间倒序排列，支持时间范围查询。

    Query params:
        stream_type: conversation | practice | knowledge | secretary | system
        stream_id: 流内实体ID
        event_type: 事件类型名
        limit: 返回条数 (默认50, 最大200)
        since: 起始时间戳 (epoch float)
        until: 结束时间戳
    """
    from app.infrastructure.event_store import get_event_store
    store = get_event_store()
    events = await store.query(
        user_id,
        stream_type=stream_type,
        stream_id=stream_id,
        event_type=event_type,
        limit=min(limit, 200),
        since=since,
        until=until,
    )
    return [e.to_dict() for e in events]


@router.get("/events/stream/{stream_type}/{stream_id}")
async def get_specific_stream(
    stream_type: str,
    stream_id: str,
    user_id: str = Depends(current_user_id),
    limit: int = 100,
) -> list[dict]:
    """获取指定流的所有事件 (时间正序)

    Path params:
        stream_type: conversation | practice | knowledge | secretary | system
        stream_id: 流内实体ID
    """
    from app.infrastructure.event_store import get_event_store
    store = get_event_store()
    events = await store.stream(stream_type, stream_id, limit=min(limit, 200))
    return [e.to_dict() for e in events]


@router.get("/events/recent")
async def get_recent_events(
    user_id: str = Depends(current_user_id),
    limit: int = 10,
) -> list[dict]:
    """获取最近事件 (Dashboard 跨系统时间线)

    返回按时间倒序的最近事件，包含摘要和来源信息。
    """
    import time
    from app.infrastructure.event_store import get_event_store
    store = get_event_store()

    # 默认最近 24 小时
    since = time.time() - 86400
    events = await store.replay(user_id, since=since, limit=min(limit, 50))
    return [
        {
            "event_type": e.event_type,
            "occurred_at": e.created_at or "",
            "summary": e.summary or e.event_type,
            "stream_type": e.stream_type or "system",
            "stream_id": e.stream_id or "",
        }
        for e in events
    ]


@router.get("/events/summary")
async def get_event_summary(
    user_id: str = Depends(current_user_id),
) -> dict:
    """获取事件系统摘要统计

    返回各类事件计数、最近活动时间、每日事件趋势。
    """
    from app.infrastructure.event_store import get_event_store
    store = get_event_store()

    # 统计各类型事件数量
    types = ["AssistantReplied", "AnswerSubmitted", "SessionCompleted",
             "CognitiveNodeMetadataChanged", "CognitiveNodeLinked", "NodeCreated",
             "EpisodeDigest", "TopicDigest", "TypeDigest",
             "PracticeSessionSummary", "DailyDigest"]
    counts = {}
    for t in types:
        counts[t] = await store.count(user_id, event_type=t)

    total = sum(counts.values())

    # 最近事件时间
    latest = await store.get_latest(user_id)
    last_active = latest.created_at if latest else 0

    # 最近24小时事件数
    import time
    day_ago = time.time() - 86400
    recent_24h = await store.query(user_id, since=day_ago, limit=1)
    recent_count = len(recent_24h)

    return {
        "total_events": total,
        "counts": counts,
        "last_active": last_active,
        "recent_24h": recent_count,
    }


# ══════════════════════════════════════════════════════════════
#  事件层次查询 — EventSystem v2
# ══════════════════════════════════════════════════════════════


@router.get("/events/top-level")
async def get_top_level_events(
    user_id: str = Depends(current_user_id),
    dimension: str = "",
    stream_type: str = "",
    limit: int = 50,
) -> list[dict]:
    """获取顶层事件 (没有父节点的事件)

    聚合流视图: 仅显示未被折叠的事件。

    Query params:
        dimension: mixed | topic | type (空=全部)
        stream_type: 按流类型过滤 (aggregate=仅聚合事件)
        limit: 返回条数 (默认50, 最大200)
    """
    from app.infrastructure.event_aggregator import (
        get_top_level_events as _top_level,
        get_top_level_by_dimension as _top_by_dim,
    )

    if dimension and dimension in ("mixed", "topic", "type"):
        rows = _top_by_dim(user_id, dimension, min(limit, 200), stream_type=stream_type)
    else:
        rows = _top_level(user_id, min(limit, 200), stream_type=stream_type)

    return rows


@router.get("/events/{event_id}/children")
async def get_event_children(
    event_id: str,
    user_id: str = Depends(current_user_id),
) -> list[dict]:
    """获取聚合事件的子节点 (下钻)

    展开一个聚合事件，显示其包含的子事件。
    """
    from app.infrastructure.event_aggregator import get_children as _children
    return _children(event_id)


@router.get("/events/{event_id}/ancestors")
async def get_event_ancestors(
    event_id: str,
    user_id: str = Depends(current_user_id),
) -> list[dict]:
    """获取事件的所有祖先 (CTE 递归)

    从原始事件向上追溯，显示所有聚合层级。
    """
    from app.infrastructure.event_aggregator import get_ancestors as _ancestors
    return _ancestors(event_id)


class AgentChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    current_page: str = "/"
    conv_id: str | None = None


@router.post("/agent/chat")
async def agent_chat(body: AgentChatRequest, user_id: str = Depends(current_user_id)):
    """Agent 助手对话 — SSE 流式返回

    流程: 用户输入 → 加载工具 schema → LLM 分析意图 → 流式返回 token + tool_call 事件

    Task #83 B-13: 移除多余的 `if user_id is None` 检查 (Depends 已保证非 None)
    """

    from app.domain.secretary.tools.tool_registry import ToolRegistry
    from app.services.common import get_data_repo
    from app.schemas.directory_node import DirectoryNode

    # ── 创建/复用 secretary 类型会话 ──
    conv_id = body.conv_id
    if not conv_id:
        data = get_data_repo().load(user_id)
        conv = DirectoryNode(
            node_type="conv",
            kind="secretary",
            parent_id=None,
            name="AI 秘书对话",
            metadata={},
        )
        data.directory_nodes[conv.id] = conv
        get_data_repo().save(user_id, data)
        conv_id = conv.id

    # ── 加载 tools schema ──
    registry = ToolRegistry()
    tools_dir = Path(__file__).resolve().parent.parent.parent.parent / "app" / "domain" / "secretary" / "tools"
    registry.discover(str(tools_dir))
    tool_schemas = registry.get_schema()

    async def event_stream():
        # 返回 conv_id 事件
        yield f"event: conversation\ndata: {json.dumps({'conv_id': conv_id})}\n\n"

        # ── 调用 Agent LLM 进行意图分析 ──
        try:
            from app.domain.secretary.agent_llm import agent_generate_stream

            async for event in agent_generate_stream(
                user_message=body.message,
                current_page=body.current_page,
                tool_schemas=tool_schemas,
                user_id=user_id,
            ):
                if event["type"] == "token":
                    yield f"event: token\ndata: {json.dumps({'delta': event['delta']})}\n\n"
                elif event["type"] == "tool_call":
                    tc = event["tool_call"]
                    if not isinstance(tc, dict):
                        tc = {"name": str(tc), "arguments": {}}
                    tool_name = tc.get("name", "")
                    tool_args = tc.get("arguments", {})

                    # 执行工具获取真实结果（confirmation_text + route）
                    tool_def = registry.get_tool(tool_name)
                    route = tool_def.route if tool_def else None
                    confirmation_text = f'即将执行 {tool_name}'
                    require_confirmation = tool_def.require_confirmation if tool_def else True
                    tool_result_data = None

                    if tool_def:
                        try:
                            tool_result = await registry.execute(tool_name, tool_args)
                            # 使用工具执行结果中的实际值
                            confirmation_text = tool_result.confirmation_text or confirmation_text
                            if tool_result.route_target:
                                route = {
                                    "target": tool_result.route_target,
                                    "params": tool_result.route_params or {},
                                }
                            tool_result_data = tool_result.data
                        except Exception:
                            pass  # 执行失败时使用默认值

                    tool_data = {
                        'name': tool_name,
                        'arguments': tool_args,
                        'confidence': tc.get('confidence', 0.8),
                        'require_confirmation': require_confirmation,
                        'route': route,
                        'confirmation_text': confirmation_text,
                    }
                    yield f"event: tool_call\ndata: {json.dumps(tool_data)}\n\n"

                    # 基于工具结果让 LLM 生成后续回复
                    if tool_result_data is not None:
                        try:
                            from app.domain.secretary.agent_llm import agent_generate_followup
                            async for followup_event in agent_generate_followup(
                                user_message=body.message,
                                tool_name=tool_name,
                                tool_result=tool_result_data,
                                user_id=user_id,
                            ):
                                if followup_event["type"] == "token":
                                    yield f"event: token\ndata: {json.dumps({'delta': followup_event['delta']})}\n\n"
                        except Exception:
                            pass  # 后续回复失败不影响主流程
                elif event["type"] == "done":
                    pass  # 最后统一发送 done

        except Exception as e:
            logger = __import__("logging").getLogger(__name__)
            logger.error("Agent LLM 调用失败: %s", e)
            yield f"event: token\ndata: {json.dumps({'delta': '抱歉，AI 服务暂时不可用，请稍后重试。'})}\n\n"

        yield "event: done\ndata: {}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ══════════════════════════════════════════════════════════════
#  Agent 偏好
# ══════════════════════════════════════════════════════════════

class AgentPreferencesRequest(BaseModel):
    confirm_mode: str = "smart"
    auto_jump_threshold: float = 0.85


@router.get("/agent/preferences")
async def get_agent_preferences(user_id: str = Depends(current_user_id)):
    """获取 Agent 助手偏好"""
    from app.services.common import get_data_repo
    data = get_data_repo().load(user_id)
    prefs = data.secretary_prefs.get("agent", {})
    return {
        "confirm_mode": prefs.get("confirm_mode", "smart"),
        "auto_jump_threshold": prefs.get("auto_jump_threshold", 0.85),
    }


@router.post("/agent/preferences")
async def set_agent_preferences(
    body: AgentPreferencesRequest,
    user_id: str = Depends(current_user_id),
):
    """设置 Agent 助手偏好

    Task #83 B-6: 发布 UserPreferencesUpdated 事件用于跨模块联动
    """
    # Pydantic 字段已用 Literal 约束, 但保留手动验证以兼容老版本
    valid_modes = {"smart", "always", "never"}
    if body.confirm_mode not in valid_modes:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid confirm_mode. Must be one of: {valid_modes}",
        )

    from app.services.common import get_data_repo
    data = get_data_repo().load(user_id)
    if "agent" not in data.secretary_prefs:
        data.secretary_prefs["agent"] = {}
    data.secretary_prefs["agent"]["confirm_mode"] = body.confirm_mode
    data.secretary_prefs["agent"]["auto_jump_threshold"] = body.auto_jump_threshold
    get_data_repo().save(user_id, data)

    # 发布 UserPreferencesUpdated 事件 (B-6)
    try:
        from app.infrastructure.event_bus_utils import publish_event_safe
        from shared.events import UserPreferencesUpdated
        publish_event_safe(UserPreferencesUpdated(
            user_id=user_id,
            changed_keys=["agent.confirm_mode", "agent.auto_jump_threshold"],
            source="secretary_api",
        ))
    except Exception as e:
        logger.debug("UserPreferencesUpdated 发布失败: %s", e)

    return {
        "confirm_mode": body.confirm_mode,
        "auto_jump_threshold": body.auto_jump_threshold,
    }


# ══════════════════════════════════════════════════════════════
#  仪表盘聚合 (Task #120 / Task #168)
# ══════════════════════════════════════════════════════════════


@router.get("/dashboard")
async def get_dashboard(
    user_id: str = Depends(current_user_id),
    service: SecretaryService = Depends(_get_service),
    store: ProposalStore = Depends(_get_store),
) -> dict:
    """秘书仪表盘聚合数据 (Task #120)

    聚合逻辑已下沉到 app.services.secretary.dashboard。
    """
    from app.api.learning_activity import service as activity_service
    await _ensure_db_schema(store)
    return await _build_dashboard(
        user_id=user_id,
        service=service,
        activity_list_fn=activity_service.list_activities,
    )


